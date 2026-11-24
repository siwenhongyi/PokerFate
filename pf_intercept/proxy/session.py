"""Headless game/session logic driven by the client's existing MITM socket.

The proxy owns transport and login; this adapter owns no second game connection.
CFR runs on the shared session's serial bridge thread in the worker process.
"""
from __future__ import annotations

import asyncio
import logging
import time
import uuid
from pathlib import Path
from urllib.parse import urlsplit

from pf_entertainment.live_table import LiveTableObserver
from pf_intercept import config
from pf_intercept.headless.login import LoginResult, load_session
from pf_intercept.headless.network import configure_server_proxy_bypass
from pf_intercept.headless.session import HeadlessSession
from pf_intercept.headless.lobby.core.base import RewardAPIError
from pf_intercept.headless.lobby.doers import taskhands
from pf_intercept.table_policy import configured_policy

log = logging.getLogger("pf_proxy_session")
_DEFAULT_SESSION = Path(__file__).resolve().parents[2] / "local/secrets/headless_session.json"
TABLE_REQUESTS = frozenset({"pb.LeaveRoomREQ", "pb.DelayLeaveRoomREQ", "pb.StandUpREQ",
                            "pb.QuickStartREQ", "pb.EnterRoomREQ"})


class _Transport:
    async def close(self, **kwargs):
        pass


class ProxySession(HeadlessSession):
    def __init__(self, bridge, options, emit):
        self.options, self.emit = options, emit
        super().__init__(LoginResult(0, "", ""), bridge=bridge,
                         auto_rewards=not options.no_auto_rewards, off=options.off,
                         auto_taskhands=not options.no_task_hands, reconnect_enabled=True,
                         on_frame=self._observe)
        self.session_id = 0
        self.upstream = ""
        self.observer = LiveTableObserver(reward_source=self.live_reward_totals,
                                         chips_source=self.live_total_chips,
                                         decision_source=self.live_decisions)
        self._wire_pending = {}
        self._client_pending = {}
        self._background = set()
        self._leave_done = asyncio.Event()
        self._closed.set()
        self._close_done.set()
        self._bootstrapped = False
        self._requested_cash_bb = options.bb
        if options.bb:
            bridge.configure_table_policy(configured_policy(options.bb, options.buyin_bb, options.stakes))

    def spawn(self, coroutine):
        async def run():
            try:
                return await coroutine
            except Exception as exc:
                log.exception("[PROXY_SESSION] background operation failed")
                if self.fatal_error:
                    self.begin_shutdown()
                if self.connected:
                    await self._connection_lost(str(exc))
        task = asyncio.create_task(run())
        self._background.add(task)
        task.add_done_callback(self._background.discard)
        return task

    async def attach(self, ident, upstream=""):
        if self.connected:
            await self.detach(self.session_id)
        self.session_id, self.upstream = ident, upstream
        self._generation += 1
        self._closed.clear()
        self._close_done.clear()
        self._login_done.clear()
        self._location_done.clear()
        self._room_ready.clear()
        self._login_code = None
        self.fatal_error = None
        self._wire_room_id = None
        self._restoring = True
        self._bootstrapped = False
        self._seat = None
        self._ws = _Transport()
        self._bridge_queue = asyncio.Queue()
        self._tasks = [asyncio.create_task(self._bridge_worker()), asyncio.create_task(self._tick())]
        self.observer.set_connection_status("restoring")

    async def detach(self, ident):
        if ident != self.session_id:
            return
        self._client_pending.clear()
        for f in self._wire_pending.values():
            if not f.done():
                f.set_result(False)
        self._wire_pending.clear()
        await super().disconnect("client transport closed")
        for t in tuple(self._background):
            if t is not asyncio.current_task():
                t.cancel()
        await asyncio.gather(*(t for t in tuple(self._background) if t is not asyncio.current_task()),
                             return_exceptions=True)
        self.observer.set_connection_status("reconnecting" if not self._stopping else "disconnected")

    async def identify(self, msg):
        uid = int(msg.get("uid", 0) or 0)
        if self.login.uid and uid != self.login.uid:
            self.begin_shutdown()
            raise RuntimeError("代理账号已改变，请重启以开始新一轮资金统计")
        self.login = LoginResult(uid, str(msg.get("key", "")), "")
        self.chnl = int(msg.get("chnl", config.GAMEDATA_CHNL))
        self.client_version = str(msg.get("ver", config.GAME_HTTP_VERSION))
        try:
            captured, chnl, version = load_session(self.options.session_file or _DEFAULT_SESSION)
            if captured.uid != uid or captured.rdkey != self.login.rdkey:
                raise ValueError("捕获凭证与当前客户端登录不匹配")
            self.login, self.chnl, self.client_version = captured, chnl, version
            configure_server_proxy_bypass(captured.servers, http_fallback=config.GAMEDATA_HTTP_HOST)
        except (OSError, ValueError, RuntimeError) as exc:
            log.warning("[LOBBY] 无法使用当前登录的 HTTP 凭证：%s；请通过登录代理重新登录", exc)
        self.observer.my_uid = str(uid)
        servers = self.login.servers
        host = urlsplit(self.upstream).hostname
        selected = next((s for s in servers if urlsplit(s.server_host).hostname == host), None)
        selected = selected or (servers[0] if servers else None)
        base = (selected.http_host if selected else "") or f"https://{config.GAMEDATA_HTTP_HOST}"
        if self._rewards is not None:
            self._rewards.update_credentials(self.login.authorization, self.chnl, self.client_version)
        self.configure_lobby(base)

    async def send(self, type_name, fields, room_id=None):
        if not self.connected:
            return False
        if self._stopping and type_name in {"pb.QuickStartREQ", "pb.EnterRoomREQ", "pb.RebyREQ", "pb.SetRebyREQ"}:
            return False
        rid = self.current_room_id() if room_id is None else room_id
        if type_name in {"pb.UserValueREQ", "pb.SelfUserInfoREQ", "pb.QuickStartREQ"}:
            rid = 0
        ident = uuid.uuid4().hex
        future = asyncio.get_running_loop().create_future()
        self._wire_pending[ident] = future
        self.emit({"kind": "inject", "session_id": self.session_id, "type_name": type_name,
                   "fields": fields, "room_id": int(rid), "send_id": ident, "created_at": time.monotonic()})
        try:
            return bool(await asyncio.wait_for(future, 8))
        except asyncio.TimeoutError:
            return False
        finally:
            self._wire_pending.pop(ident, None)

    def sent(self, ident, ok):
        f = self._wire_pending.get(ident)
        if f is not None and not f.done():
            f.set_result(ok)

    async def activity_request(self, name, fields, room=None):
        reply = f"pb.{name}RSP"
        if time.monotonic() < self._client_pending.get(reply, 0):
            raise RewardAPIError(name, "client request outstanding")
        return await super().activity_request(name, fields, room)

    async def client_request(self, name, msg):
        if name == "pb.UserLoginREQ":
            await self.identify(msg)
            return True
        if name in TABLE_REQUESTS:
            if self._stopping or self._seat is not None or self._match_lock.locked():
                return False
            if name == "pb.EnterRoomREQ" and self._restoring and self.options.bb:
                return False  # restore_or_start is the one owner of room restoration
            if name == "pb.QuickStartREQ" and int(msg.get("game_type", 0)) == 10010101:
                self.spawn(self._client_match(msg))
                return False
            self._bridge_queue.put_nowait(("pf.ClientRequest", {"type_name": name, "msg": msg},
                                            self.current_room_id(), time.monotonic(), self._wire_turn))
        if name.endswith("REQ"):
            reply = name[:-3] + "RSP"
            if reply in self._activity_pending:
                # No request IDs: the in-flight bot response is also forwarded to the client.
                return False
            self._client_pending[reply] = time.monotonic() + 60
        return True

    async def _client_match(self, msg):
        if self._match_lock.locked():
            return
        generation = self._generation
        bb = self.options.bb or int(msg.get("boot", 0) or 0)
        if bb <= 0:
            raise ValueError("现金桌匹配缺少有效大盲")
        self._requested_cash_bb = bb
        async with self._match_lock:
            if self._task_hands is not None and not self.current_room_id():
                await self._task_hands.run()
            if self._stopping or not self.connected or generation != self._generation:
                return
            async with self._bridge_lock:
                if self.bridge._table_policy is None:
                    self.bridge.configure_table_policy(configured_policy(bb, self.options.buyin_bb, self.options.stakes))
            await self.quick_start(big_blind=bb, buyin_bb=self.options.buyin_bb)

    def _observe(self, name, msg):
        self.observer.observe(name, msg)
        if name == "pb.LeaveRoomRSP" and int(msg.get("code", 0) or 0) in (0, 2, 3):
            self._leave_done.set()

    async def feed_message(self, name, room, msg):
        self._client_pending.pop(name, None)
        if name == "pb.LeaveRoomRSP" and int(msg.get("code", 0) or 0) in (0, 2, 3):
            self._leave_done.set()
        if name == "pb.UserLoginRSP" and int(msg.get("code", 0) or 0) == 0 and not self._bootstrapped:
            self._bootstrapped = True
            if self._rewards is not None:
                self._rewards.start()
            self.spawn(self.send("pb.UserValueREQ", {"type": 10100001}, 0))
            if self.options.bb:
                self.spawn(self.restore_or_start(big_blind=self.options.bb, buyin_bb=self.options.buyin_bb))
        if not self.options.bb and name in {"pb.UserLocationRSP", "pb.EnterRoomRSP"}:
            # Manual entry still needs an authoritative wallet/table baseline before rewards.
            if name == "pb.EnterRoomRSP" or int(msg.get("roomid", 0) or 0) == 0:
                self._restoring = False
                self.spawn(self.send("pb.UserValueREQ", {"type": 10100001}, 0))
        old_seat = self._seat
        await super().feed_message(name, room, msg)
        if old_seat is None and self._seat is not None and not self.options.bb:
            self.spawn(self._restore_task_seat(self._seat))
        if self.logged_in and not self._restoring:
            self.observer.set_connected(True)

    async def _restore_task_seat(self, seat):
        """A client reconnect can restore the task table whose coroutine was cancelled."""
        await seat.leave()
        if self._seat is seat:
            self._seat = None
        if seat.net:
            await self.on_sidegame_result(seat.net)
        async with self._bridge_lock:
            can_match = self.bridge.restore_lobby_after_disconnect()
            self._refresh_bankroll_snapshot()
        await self.lobby_baseline()
        await asyncio.wait_for(self._bankroll_ready.wait(), 15)
        if can_match and self._requested_cash_bb and not self._stopping:
            await self._client_match({"boot": self._requested_cash_bb})

    async def _tick(self):
        while self.connected:
            await asyncio.sleep(1)
            if self.logged_in and not self._restoring and self._seat is None and self.bridge.wants_tick():
                self._bridge_queue.put_nowait(("pf.Tick", {"now": time.time()}, 0, time.monotonic(), self._wire_turn))
            if self._task_hands is not None and self.logged_in and self._task_hands.wants_break():
                self._bridge_queue.put_nowait(("pf.Errand", {"reason": "task_hands"}, 0, time.monotonic(), self._wire_turn))

    async def graceful_leave(self, timeout=45):
        self.begin_shutdown()
        self._leave_done.clear()
        room = self.current_room_id()
        if not room or not self.connected:
            return
        if await self.send("pb.DelayLeaveRoomREQ", {"flag": True}, room):
            try:
                await asyncio.wait_for(self._leave_done.wait(), timeout)
            except asyncio.TimeoutError:
                log.warning("[PROXY] 等待离桌确认超时")

    async def _connection_lost(self, reason):
        self.emit({"kind": "close_transport", "session_id": self.session_id})
        await super()._connection_lost(reason)

    async def close(self, reason=""):
        self.begin_shutdown()
        await self.detach(self.session_id)
        await super().close(reason)
