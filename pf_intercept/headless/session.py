"""WSS session driver: connect, login, heartbeat, feed BotBridge, send injects.

Message flow after the HTTP login (see LoginModel:reConnect / net_game.lua):

    -> pb.UserLoginREQ {uid, key=rdkey, ver, chnl}
    <- pb.UserLoginRSP code 0  (1002 = login queue: keep heart-beating, wait)
    -> pb.SelfUserInfoREQ {}         (bridge learns our uid)
    -> pb.UserValueREQ {type=Gold}   (bankroll sample; bridge also asks)
    -> pb.HeartBeatREQ {} every 5s   (server drops the socket after 2 misses)
    -> pb.QuickStartREQ {...}        (lobby cash table; server then pushes
                                      EnterRoomRSP / SitDownRSP / DealerInfoRSP…)

Every decoded S2C frame in WATCH_S2C goes to ``BotBridge.handle`` exactly as
the proxy did; returned injects are encoded and sent back on the same socket
after their delay, guarded by the bridge's hand/gameid guard.
"""

from __future__ import annotations

import asyncio
import logging
import ssl
import time
from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Awaitable, Callable
from urllib.parse import urlparse

import websockets

from pf_intercept import config
from pf_intercept.bot import BotBridge
from pf_intercept.headless.login import LoginResult, ServerEntry
from pf_intercept.headless.network import configure_server_proxy_bypass
from pf_intercept.headless import lobby
from pf_intercept.headless.lobby.doers import taskhands
from pf_intercept.headless.lobby.core.base import RewardAPIError
from pf_intercept.headless.lobby.core.service import RewardService
from pf_intercept.wire import codec
from pf_intercept.wire.framing import FrameBuffer, encode_frame

log = logging.getLogger("pf_headless")

HEARTBEAT_INTERVAL_SEC = 5.0          # MainScene.lua: bee.schedule(5, …)
HEARTBEAT_MISS_LIMIT = 2              # client gives up after 2 unanswered beats
LOGIN_RSP_TIMEOUT_SEC = 15.0
LOGIN_QUEUE_CODE = 1002               # LOGIN_ERR_ENTER_QUEUE
LOBBY_HOLDEM_GAME_TYPE = 10010101     # GAME_GAME_TYPE.LOBBY_HOLDEM_GAME
_INJECT_TTL_SEC = 20.0
_ACTIVITY_REPLY_TIMEOUT_SEC = 8.0
_ACTIVITY_LATE_REPLY_SEC = 60.0      # how long a timed-out activity reply is still awaited
STATE_TIMEOUT_SEC = 15.0
ROOM_SYNC_TIMEOUT_SEC = 45.0

# S2C frames the session itself reacts to, on top of the bridge's WATCH_S2C.
_SESSION_TYPES = frozenset({"pb.UserLoginRSP", "pb.HeartBeatRSP", "pb.QuickStartRSP", "pb.NoticeBRC",
                            "pb.UserLocationRSP", "pb.UserLogoutRSP", "pb.ServerStopBRC"})


class SessionClosed(RuntimeError):
    pass


class LoginRejected(SessionClosed):
    """Explicit server rejection; retrying the same credentials won't help."""


@dataclass
class SessionStats:
    frames_in: int = 0
    frames_bot: int = 0
    injects_sent: int = 0
    injects_dropped: int = 0
    heartbeats_sent: int = 0
    heartbeats_missed: int = 0
    last_rx_at: float = 0.0


def _lobby_alert(title: str, body: str) -> None:
    """A lobby finding the user has to act on, to the phone (nothing without a Bark key)."""
    from pf_notify.client import notify
    notify("lobby_alert", title=title, body=body)


def _ws_ssl_context() -> ssl.SSLContext:
    # Game servers are addressed by raw IP (wss://1.2.3.4:9013) with a
    # certificate for the domain, so hostname/CA verification cannot pass.
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def _split_wss(url: str) -> tuple[str, int]:
    parsed = urlparse(url if "://" in url else f"wss://{url}")
    host = parsed.hostname or ""
    port = parsed.port or (443 if parsed.scheme == "wss" else 80)
    if not host:
        raise ValueError(f"bad server_host: {url!r}")
    return host, port


class HeadlessSession:
    """One bot run, retaining its bridge across successive WSS connections."""

    def __init__(
        self,
        login: LoginResult,
        *,
        bridge: BotBridge | None = None,
        chnl: int = int(config.GAMEDATA_CHNL),
        client_version: str = str(config.GAME_HTTP_VERSION),
        max_auto_rebuy: int | None = None,
        auto_rewards: bool = True,
        off=(),
        auto_taskhands: bool = True,
        reconnect_enabled: bool = False,
        on_frame: Callable[[str, dict], Awaitable[None] | None] | None = None,
        table_policy=None,
        options=None,
    ) -> None:
        self.login = login
        self.bridge = bridge if bridge is not None else BotBridge(max_auto_rebuy=max_auto_rebuy, options=options)
        if table_policy is not None:
            configure_policy = getattr(self.bridge, "configure_table_policy", None)
            if callable(configure_policy):
                configure_policy(table_policy)
        self.chnl = int(chnl)
        self.client_version = str(client_version)
        self.stats = SessionStats()
        self.on_frame = on_frame
        self._ws = None
        self._server: ServerEntry | None = None
        self._login_done = asyncio.Event()
        self._login_code: int | None = None
        self._queue_pos: int | None = None
        self._closed = asyncio.Event()
        self._close_done = asyncio.Event()
        self._bridge_lock = asyncio.Lock()
        # Frames for the bot are queued and handled by a dedicated worker, so a
        # slow handler never blocks the receive loop (and with it HeartBeatRSP).
        self._bridge_queue: asyncio.Queue = asyncio.Queue()
        self._pending_hb = 0
        self._tasks: list[asyncio.Task] = []
        self._auto_rewards = auto_rewards
        self._off = frozenset(off)      # switches of lobby workers turned off (lobby.switches())
        # The tasks' Omaha / AOF hands, played once per start before the real game.
        self._task_hands = taskhands.TaskHands(self) if auto_taskhands else None
        self._seat = None       # taskhands.Seat while the bot sits at a task table: nothing of it reaches the bridge
        self._match_lock = asyncio.Lock()   # held from the errand to the real match request it precedes
        self._rewards: RewardService | None = None
        self._bankroll_ready = asyncio.Event()
        self._activity_pending: dict[str, asyncio.Future] = {}
        self._activity_late: dict[str, float] = {}   # reply type -> until when a timed-out reply is awaited
        self._bankroll_snapshot: dict = {}
        self._stopping = False
        self._wire_turn = 0
        self._wire_room_id: int | None = None
        self.reconnect_enabled = reconnect_enabled
        self.disconnect_reason = ""
        self.fatal_error: str | None = None
        self._finalized = False
        self._generation = 0
        self._inject_tasks: set[asyncio.Task] = set()
        self._location_done = asyncio.Event()
        self._location: dict | None = None
        self._room_ready = asyncio.Event()
        self._room_code: int | None = None
        self._restoring = False
        self._refresh_bankroll_snapshot()

    def live_reward_totals(self) -> tuple[int, bool]:
        """Only confirmed reward chips and any unresolved claim go to the public viewer."""
        rewards = self._rewards
        return (rewards.confirmed_chips, rewards.uncertain) if rewards else (0, False)

    def live_total_chips(self) -> int | None:
        """The account's chips for the live view: the wallet as the server last told it plus
        the chips on the table. None until the first wallet answer."""
        return self._bankroll_snapshot.get("current_total_chips")

    def live_decisions(self) -> tuple:
        """What the bot decided in the hand being played, for the live view (no bridge lock)."""
        return tuple(getattr(self.bridge, "live_decisions", ()) or ())

    def bankroll_dashboard(self) -> dict:
        """Read the last completed bridge snapshot without waiting for the bot.

        Web polling must neither read halfway through a handler nor wait for
        CFR/learning to release the bridge lock. Snapshots belong to this session.
        """
        return deepcopy(self._bankroll_snapshot)

    def _refresh_bankroll_snapshot(self) -> None:
        try:
            self._bankroll_snapshot = self.bridge.bankroll_dashboard()
        except Exception:
            # A display failure must not discard an action returned by handle().
            log.exception("[BOT] bankroll snapshot failed")

    async def _on_reward_credit(self, chips: int, uncertain: bool) -> None:
        async with self._bridge_lock:
            self.bridge.record_reward_credit(chips, uncertain)
            self._refresh_bankroll_snapshot()
        if self.connected:
            await self.send("pb.UserValueREQ", {"type": int(config.PROFIT_LOCK_FALLBACK_LOBBY_COIN)})

    # ── lifecycle ─────────────────────────────────────────────────────────

    @property
    def connected(self) -> bool:
        return self._ws is not None and not self._closed.is_set()

    @property
    def logged_in(self) -> bool:
        return self.connected and self._login_done.is_set() and self._login_code == 0

    async def connect(self, server_index: int = 0) -> None:
        """Open the socket and complete pb.UserLoginREQ; raises on failure."""
        if self._stopping or self._finalized:
            raise SessionClosed("会话正在停止")
        if self.fatal_error:
            raise LoginRejected(self.fatal_error)
        self._generation += 1
        self._pending_hb = 0
        self._closed.clear()
        self._close_done.clear()
        self._login_done.clear()
        self._login_code = None
        self._location_done.clear()
        self._location = None
        self._room_ready.clear()
        self._room_code = None
        self._restoring = self.reconnect_enabled
        self._wire_room_id = None
        self._seat = None       # a new connection asks the server where the bot sits
        self._bridge_queue = asyncio.Queue()
        servers = self.login.servers
        if not servers:
            raise SessionClosed("登录结果里没有服务器")
        # Also cover callers that construct HeadlessSession without the CLI,
        # and a refreshed server list on a later connection attempt.
        configure_server_proxy_bypass(servers, http_fallback=config.GAMEDATA_HTTP_HOST)
        self._server = servers[server_index % len(servers)]
        http_base = self._server.http_host or f"https://{config.GAMEDATA_HTTP_HOST}"
        self.configure_lobby(http_base)
        host, port = _split_wss(self._server.server_host)
        log.info("[WSS] connecting %s:%d", host, port)
        self._ws = await websockets.connect(
            f"wss://{host}:{port}",
            ssl=_ws_ssl_context(),
            user_agent_header=None,
            ping_interval=None,
            ping_timeout=None,
            open_timeout=15,
            close_timeout=2,
            max_size=8 * 1024 * 1024,
        )
        self._tasks = [
            asyncio.create_task(self._recv_loop(), name="headless-recv"),
            asyncio.create_task(self._heartbeat_loop(), name="headless-heartbeat"),
            asyncio.create_task(self._bridge_worker(), name="headless-bridge"),
        ]
        await self.send("pb.UserLoginREQ", {
            "uid": int(self.login.uid),
            "key": self.login.rdkey,
            "ver": self.client_version,
            "chnl": self.chnl,
        })
        await self._wait_login()
        # Same bootstrap the client does in net_game.UserLoginRSP (bot subset).
        await self.send("pb.SelfUserInfoREQ", {})
        await self.send("pb.UserValueREQ", {"type": int(config.PROFIT_LOCK_FALLBACK_LOBBY_COIN)})
        if self._rewards is not None:
            self._rewards.start()

    def configure_lobby(self, http_base: str) -> None:
        bind_gamedata = getattr(self.bridge, "set_gamedata_session", None)
        if callable(bind_gamedata):
            bind_gamedata(authorization=self.login.authorization, http_base=http_base,
                          chnl=self.chnl, version=self.client_version)
        bind_uid = getattr(self.bridge, "set_session_uid", None)
        if callable(bind_uid):
            bind_uid(self.login.uid)
        if self._auto_rewards and self._rewards is None:
            self._rewards = RewardService(
                uid=self.login.uid, authorization=self.login.authorization,
                http_base=http_base,
                chnl=self.chnl, version=self.client_version,
                on_credit=self._on_reward_credit, ready=self._bankroll_ready,
                alert=_lobby_alert,
            )
            # Every registered worker (lobby/__init__.py) whose switch is not off.
            lobby.attach(self._rewards, self, self._off)
        elif self._rewards is not None:
            self._rewards.set_http_base(http_base)

    async def _wait_login(self) -> None:
        deadline = time.monotonic() + LOGIN_RSP_TIMEOUT_SEC
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise SessionClosed("等待 UserLoginRSP 超时")
            try:
                await asyncio.wait_for(self._login_done.wait(), timeout=remaining)
            except asyncio.TimeoutError:
                continue
            if self.fatal_error:
                raise LoginRejected(self.fatal_error)
            if self._login_code == 0:
                return
            if self._login_code == LOGIN_QUEUE_CODE:
                # Login queue: server will send another UserLoginRSP when it is
                # our turn; keep the socket (and heartbeat) alive meanwhile.
                log.warning("[WSS] 登录排队中 pos=%s，继续等待", self._queue_pos)
                self._login_done.clear()
                deadline = time.monotonic() + 600
                continue
            if self.connected and self._login_code is not None:
                self.fatal_error = f"UserLoginRSP code={self._login_code}，停止自动重连，请检查登录态"
                raise LoginRejected(self.fatal_error)
            raise SessionClosed(f"UserLoginRSP code={self._login_code}")

    async def close(self, reason: str = "") -> None:
        if self._finalized:
            return
        self.begin_shutdown()
        await self.disconnect(reason)
        await self._close_done.wait()
        if self._rewards is not None:
            await self._rewards.close()
        close_bridge = getattr(self.bridge, "close", None)
        if callable(close_bridge):
            await asyncio.to_thread(close_bridge)
        self._finalized = True

    async def _connection_lost(self, reason: str) -> None:
        if self._closed.is_set():
            return
        if self.reconnect_enabled:
            await self.disconnect(reason)
        else:
            await self.close(reason)

    async def disconnect(self, reason: str = "") -> None:
        """Close this transport, retaining models, bankroll, budgets and rewards."""
        if self._closed.is_set():
            return
        self.disconnect_reason = reason
        for future in self._activity_pending.values():
            if not future.done():
                future.set_exception(RewardAPIError("activity socket disconnected"))
        self._activity_pending.clear()
        self._activity_late.clear()
        self._closed.set()
        self._wire_turn += 1
        self._generation += 1
        self._bankroll_ready.clear()
        try:
            tasks = [t for t in [*self._tasks, *self._inject_tasks] if t is not asyncio.current_task()]
            for t in tasks:
                t.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            self._tasks = []
            self._inject_tasks.clear()
            if not self._login_done.is_set():
                self._login_code = -1
                self._login_done.set()
            prepare = getattr(self.bridge, "prepare_transport_reconnect", None)
            if callable(prepare) and not self._stopping:
                async with self._bridge_lock:
                    await asyncio.to_thread(prepare)
                    self._refresh_bankroll_snapshot()
        finally:
            if self._ws is not None:
                try:
                    await self._ws.close(code=1000, reason=reason[:100])
                except Exception:
                    pass
            self._ws = None
            self._close_done.set()
            log.info("[WSS] closed (%s) %s", reason or "-", self.stats)

    async def wait_closed(self) -> None:
        await self._close_done.wait()

    async def _wait_state(self, event: asyncio.Event, name: str, timeout: float | None = None) -> None:
        ready = asyncio.create_task(event.wait())
        closed = asyncio.create_task(self._close_done.wait())
        try:
            await asyncio.wait({ready, closed}, timeout=STATE_TIMEOUT_SEC if timeout is None else timeout,
                               return_when=asyncio.FIRST_COMPLETED)
            if not self.connected:
                raise SessionClosed(self.disconnect_reason)
            if not event.is_set():
                raise SessionClosed(f"等待 {name} 超时，保持未知位置，不盲目买入")
        finally:
            ready.cancel()
            closed.cancel()
            await asyncio.gather(ready, closed, return_exceptions=True)

    async def restore_or_start(self, *, big_blind: int, buyin_bb: int = 100) -> None:
        """Follow the client's UserLocationRSP -> EnterRoomREQ recovery flow."""
        await self._wait_state(self._location_done, "UserLocationRSP")
        if big_blind > 0:
            self._match_fields(big_blind=big_blind, buyin_bb=buyin_bb)
        location = self._location or {}
        room_id = int(location.get("roomid", 0) or 0)
        if room_id > 0:
            self._room_ready.clear()
            # No byin_chips: restore existing seat, never make a second buy-in.
            fields = {"roomid": room_id}
            if not await self.send("pb.EnterRoomREQ", fields, room_id=0):
                raise SessionClosed("恢复牌桌请求未送达")
            await self._wait_state(self._room_ready, "EnterRoomRSP", ROOM_SYNC_TIMEOUT_SEC)
            if self._room_code != 0:
                raise SessionClosed(f"恢复牌桌失败 code={self._room_code}")
            if self._seat is not None:
                # The seat is at a task table (left there by a crash or a lost connection): the
                # strategy engine never plays it. Stand up and go on as from the lobby.
                log.warning("[RECONNECT] 原座位在任务桌 room=%d，先离桌", room_id)
                await self._seat.leave()
                self._seat = None
                room_id = 0
            else:
                log.info("[RECONNECT] 已恢复原牌桌 room=%d，未请求额外买入", room_id)
        if room_id <= 0:
            async with self._bridge_lock:
                lobby = getattr(self.bridge, "restore_lobby_after_disconnect", None)
                can_match = await asyncio.to_thread(lobby) if callable(lobby) else True
                self._refresh_bankroll_snapshot()
            if big_blind > 0 and can_match and not self._stopping:
                if self._task_hands is not None:
                    async with self._match_lock:
                        await self._task_hands.run()    # the tasks' Omaha / AOF hands; the real game comes after
                self._room_ready.clear()
                if not await self.quick_start(big_blind=big_blind, buyin_bb=buyin_bb):
                    raise SessionClosed("重新匹配请求未送达")
                await self._wait_state(self._room_ready, "匹配后的 EnterRoomRSP", ROOM_SYNC_TIMEOUT_SEC)
                if self._room_code != 0:
                    self.fatal_error = f"匹配被拒绝 code={self._room_code}，停止重试"
                    raise SessionClosed(self.fatal_error)
            else:
                log.info("[RECONNECT] 已回大厅，保留原停止/破产限制，不自动买入")
        self._restoring = False
        await self.send("pb.UserValueREQ", {"type": int(config.PROFIT_LOCK_FALLBACK_LOBBY_COIN)}, room_id=0)

    # ── sending ───────────────────────────────────────────────────────────

    async def send(self, type_name: str, fields: dict[str, Any], room_id: int | None = None) -> bool:
        if self._ws is None or self._closed.is_set():
            return False
        body = codec.encode(type_name, fields)
        if body is None:
            log.warning("[C→S] %s encode failed fields=%r", type_name, fields)
            return False
        rid = int(room_id if room_id is not None else self.bridge.room_id_for_c2s(0))
        if type_name in ("pb.UserValueREQ", "pb.UserLoginREQ", "pb.SelfUserInfoREQ", "pb.HeartBeatREQ"):
            rid = 0
        if type_name != "pb.HeartBeatREQ":
            log.info("[C→S] %s room_id=%s %s", type_name, rid, fields)
        try:
            await self._ws.send(encode_frame(type_name, rid, body))
        except Exception as exc:
            log.warning("[C→S] send failed %s: %s", type_name, exc)
            await self._connection_lost(f"send failed: {exc}")
            return False
        return True

    async def activity_request(self, name, fields, room=None):
        """One request / reply pair on the game socket, for the reward worker.

        Replies carry no request id, so one request per reply type may be
        outstanding. After a timeout the type stays reserved for
        ``_ACTIVITY_LATE_REPLY_SEC`` so that a late reply is dropped instead of
        answering the next request; a reply still missing by then is lost.
        ``RewardAPIError.code`` is None only if the request may have reached the
        server.
        """
        reply_name = f"pb.{name}RSP"
        if self._stopping or not self.connected or not self._bankroll_ready.is_set():
            raise RewardAPIError(name, "offline")
        if reply_name in self._activity_pending:
            if time.monotonic() < self._activity_late.get(reply_name, float("inf")):
                raise RewardAPIError(name, "waiting for late response")
            del self._activity_pending[reply_name]
        self._activity_late.pop(reply_name, None)
        if codec.encode(f"pb.{name}REQ", fields) is None:
            raise RewardAPIError(name, "encode failed")
        future = asyncio.get_running_loop().create_future()
        self._activity_pending[reply_name] = future
        try:
            if not await self.send(f"pb.{name}REQ", fields, self.current_room_id() if room is None else room):
                # Nothing is on the wire, or the socket is gone: no reply to wait for.
                if self._activity_pending.get(reply_name) is future:
                    del self._activity_pending[reply_name]
                raise RewardAPIError(name)
            reply = await asyncio.wait_for(future, timeout=_ACTIVITY_REPLY_TIMEOUT_SEC)
        except asyncio.TimeoutError:
            if self._activity_pending.get(reply_name) is future:
                self._activity_late[reply_name] = time.monotonic() + _ACTIVITY_LATE_REPLY_SEC
            raise RewardAPIError(name) from None
        finally:
            if future.done() and not future.cancelled():
                future.exception()
        if int(reply.get("code", 0)) != 0:
            raise RewardAPIError(name, reply["code"], reply)
        return reply

    def activity_table(self):
        room = self.current_room_id()
        if not room or self.bridge.room_id_for_c2s(0) != room:
            return 0, None
        return room, self.bridge.activity_emoji_target()

    async def lobby_baseline(self) -> None:
        """In the lobby the wallet alone is the bankroll. Taking the baseline here lets the
        reward worker run before a table is joined."""
        self._restoring = False
        await self.send("pb.UserValueREQ", {"type": int(config.PROFIT_LOCK_FALLBACK_LOBBY_COIN)}, room_id=0)

    def table_game(self) -> int:
        """The game of the table the bot sits at, 0 in the lobby."""
        if self._seat is not None:
            return self._seat.game
        return LOBBY_HOLDEM_GAME_TYPE if self.current_room_id() else 0

    async def on_sidegame_result(self, net):
        async with self._bridge_lock:
            self.bridge.record_sidegame_result(net)
            self._refresh_bankroll_snapshot()
        if self.connected:
            await self.send("pb.UserValueREQ", {"type": int(config.PROFIT_LOCK_FALLBACK_LOBBY_COIN)})

    async def quick_start(self, *, big_blind: int, buyin_bb: int = 100, wait_blind: bool = False) -> bool:
        """Ask the lobby for a cash table (LobbyByinDialog StartButton)."""
        fields = self._match_fields(big_blind=big_blind, buyin_bb=buyin_bb, wait_blind=wait_blind)
        # The buy-in sent may be smaller than the configured one: the loss cap of this start.
        cap = getattr(self.bridge, "cap_match_buyin", None)
        if callable(cap):
            fields = cap(fields)
            if int(fields.get("byin_chips", 0) or 0) <= 0:
                log.warning("[MATCH] 净亏损上限下放不下买入，不匹配")
                return False
        ok = await self.send("pb.QuickStartREQ", fields, room_id=0)
        note = getattr(self.bridge, "note_match_sent", None)
        if ok and callable(note):
            note()
        return ok

    def _match_fields(self, *, big_blind: int, buyin_bb: int, wait_blind: bool = False) -> dict:
        fields = {
            "boot": int(big_blind),
            "game_type": LOBBY_HOLDEM_GAME_TYPE,
            "lobby_coin": int(config.PROFIT_LOCK_FALLBACK_LOBBY_COIN),
            "byin_chips": int(big_blind) * int(buyin_bb),
            "wait_blind": bool(wait_blind),
            "ip": self.login.login_ip or "",
        }
        # Table selection may move us to another stake and makes us wait for the big blind.
        adjust = getattr(self.bridge, "adjust_match_fields", None)
        if callable(adjust):
            fields = adjust(fields)
        configure = getattr(self.bridge, "configure_auto_rejoin", None)
        if callable(configure):
            configure(fields)
        return fields

    def begin_shutdown(self) -> None:
        self._stopping = True
        stop_rejoin = getattr(self.bridge, "stop_auto_rejoin", None)
        if callable(stop_rejoin):
            stop_rejoin()

    def current_room_id(self) -> int:
        if self._wire_room_id is not None:
            return self._wire_room_id
        return self.bridge.room_id_for_c2s(0)

    # ── receiving ─────────────────────────────────────────────────────────

    async def _recv_loop(self) -> None:
        buf = FrameBuffer()
        ws = self._ws
        try:
            async for raw in ws:
                if isinstance(raw, str):
                    raw = raw.encode("utf-8")
                for frame in buf.feed(raw):
                    self.stats.frames_in += 1
                    self.stats.last_rx_at = time.monotonic()
                    await self._on_s2c(frame.type_name, frame.room_id, frame.pb_body)
                    if self._closed.is_set():
                        return
        except asyncio.CancelledError:
            raise
        except websockets.ConnectionClosed as exc:
            log.warning("[WSS] connection closed by peer code=%s reason=%r", exc.code, exc.reason)
        except Exception:
            log.exception("[WSS] recv loop error")
        finally:
            if self._ws is ws:
                if not self._login_done.is_set():
                    self._login_code = self._login_code or -1
                    self._login_done.set()
                await self._connection_lost("recv loop ended")

    async def _on_s2c(self, type_name: str, room_id: int, pb_body: bytes) -> None:
        if (type_name not in _SESSION_TYPES and type_name not in config.WATCH_S2C
                and type_name not in self._activity_pending):
            return
        msg = codec.decode(type_name, pb_body)
        if msg is None:
            future = self._activity_pending.pop(type_name, None)
            if future is not None and not future.done():
                future.set_exception(RewardAPIError(type_name))
            log.warning("[S→C] %s decode failed (%d bytes)", type_name, len(pb_body))
            return
        await self.feed_message(type_name, room_id, msg)

    async def feed_message(self, type_name: str, room_id: int, msg: dict) -> None:
        if type_name == "pb.HeartBeatRSP":
            self._pending_hb = 0
            if self._rewards is not None:
                self._rewards.observe_server_time(msg.get("server_timestamp"))
            return
        future = self._activity_pending.pop(type_name, None)
        if future is not None:
            self._activity_late.pop(type_name, None)
            if not future.done():
                future.set_result(msg)
        if type_name not in _SESSION_TYPES and type_name not in config.WATCH_S2C:
            return
        log.info("[S→C] %s %s", type_name, msg)
        if type_name in {"pb.UserLogoutRSP", "pb.ServerStopBRC"}:
            self.fatal_error = f"{type_name} code={msg.get('code', 0)}，服务器要求退出，停止自动重连"
            log.error("[RECONNECT] %s", self.fatal_error)
            await self._connection_lost(self.fatal_error)
            return
        received_at = time.monotonic()
        if type_name in {"pb.ActionNotifyBRC", "pb.ActionBRC", "pb.DealerInfoRSP",
                         "pb.RoundStartBRC", "pb.WinnerRSP", "pb.EnterRoomRSP", "pb.LeaveRoomRSP"}:
            # Advance on receipt, not when a potentially backlogged bridge
            # finally processes the frame. A system fold must cancel old bets.
            self._wire_turn += 1
        if type_name == "pb.EnterRoomRSP" and int(msg.get("code", 0) or 0) == 0:
            self._wire_room_id = int(msg.get("roomid", room_id) or room_id)
        elif type_name == "pb.LeaveRoomRSP" and int(msg.get("code", 0) or 0) in (0, 2, 3):
            self._wire_room_id = 0

        if type_name == "pb.UserLoginRSP":
            self._login_code = int(msg.get("code", 0) or 0)
            if self._login_code not in (0, LOGIN_QUEUE_CODE):
                self.fatal_error = f"UserLoginRSP code={self._login_code}，停止自动重连，请检查登录态"
            self._queue_pos = msg.get("pos")
            self._login_done.set()
            if self._rewards is not None:
                self._rewards.observe_server_time(msg.get("server_timestamp"))
        elif type_name == "pb.UserLocationRSP":
            self._location = dict(msg)
            self._wire_room_id = int(msg.get("roomid", 0) or 0)
            self._location_done.set()
        elif type_name == "pb.NoticeBRC":
            if self._rewards is not None:
                self._rewards.notify(int(msg.get("type", 0)))
        elif type_name == "pb.QuickStartRSP":
            code = int(msg.get("code", 0) or 0)
            if code != 0:
                log.warning("[WSS] QuickStartRSP code=%s（进桌失败）", code)
                self._room_code = code
                self._room_ready.set()

        if self._seat is None and type_name == "pb.EnterRoomRSP" and taskhands.is_task_table(msg):
            # Restored into a task table, which nobody here asked for: restore_or_start gives it up.
            self._seat = taskhands.Seat(self, int(msg.get("game_type", 0) or 0))
            self._seat.room = int(msg.get("roomid", room_id) or room_id)
            self._room_code = int(msg.get("code", 0) or 0)
            self._room_ready.set()
        if self._seat is not None and (type_name in taskhands.FRAMES or type_name == "pb.UserValueRSP"):
            # A task table is not the strategy engine's, nor the live view's; and the wallet while
            # chips sit there is no bankroll sample.
            if type_name in taskhands.FRAMES:
                self._seat.feed(type_name, msg)
            return

        if self.on_frame is not None:
            out = self.on_frame(type_name, msg)
            if asyncio.iscoroutine(out):
                await out

        if type_name not in config.WATCH_S2C:
            return
        if type_name == "pb.UserValueRSP" and self._restoring:
            # Wallet + stale table chips is not a valid bankroll sample.
            # Query again after the authoritative location/table snapshot.
            return
        self.stats.frames_bot += 1
        # Hand off to the bridge worker: handlers (CFR / equity, and the post-
        # showdown learning after WinnerRSP, which took 10s+ live) can be slow,
        # and the receive loop must keep reading so HeartBeatRSP is consumed.
        self._bridge_queue.put_nowait((type_name, msg, room_id, received_at, self._wire_turn))

    async def _bridge_worker(self) -> None:
        """Process bot-bound frames one at a time, in arrival order."""
        try:
            while True:
                type_name, msg, room_id, received_at, wire_turn = await self._bridge_queue.get()
                try:
                    async with self._bridge_lock:
                        if type_name == "pb.ActionNotifyBRC" and wire_turn != self._wire_turn:
                            log.warning("[BOT] 丢弃过期行动通知：服务器已进入后续行动，排队 %.0fms",
                                        (time.monotonic() - received_at) * 1000)
                            self.stats.injects_dropped += 1
                            # Nothing to decide any more, but the notice still says whether the
                            # action that overtook it was pre-selected - and a pre-selected action
                            # always overtakes its notice.
                            self.bridge.note_pre_action(msg)
                            continue
                        started = time.monotonic()
                        self.bridge.note_seen_room_id(room_id)
                        handler = asyncio.create_task(asyncio.to_thread(self.bridge.handle, type_name, msg))
                        try:
                            result = await asyncio.shield(handler)
                        except asyncio.CancelledError:
                            # Cancelling to_thread does not stop its thread.
                            # Finish it before close() flushes model writers.
                            await handler
                            raise
                        elapsed = time.monotonic() - started
                        queued = started - received_at
                        if elapsed > 0.5 or queued > 0.5:
                            log.warning("[BOT] handler=%s queue_ms=%.0f handle_ms=%.0f backlog=%d",
                                        type_name, queued * 1000, elapsed * 1000, self._bridge_queue.qsize())
                        self._refresh_bankroll_snapshot()
                        if self._bankroll_snapshot.get("base_total_chips") is not None:
                            if not self._restoring and (not self.reconnect_enabled or type_name == "pb.UserValueRSP"):
                                self._bankroll_ready.set()
                        if type_name == "pb.EnterRoomRSP":
                            self._room_code = int(msg.get("code", 0) or 0)
                            self._room_ready.set()
                    for inject in _iter_injects(result):
                        task = asyncio.create_task(self._inject(inject, room_id, received_at=received_at,
                                                   wire_turn=wire_turn, generation=self._generation), name="headless-inject")
                        self._inject_tasks.add(task)
                        task.add_done_callback(self._inject_tasks.discard)
                except asyncio.CancelledError:
                    raise
                except Exception:
                    log.exception("[BOT] bridge handler failed on %s", type_name)
        except asyncio.CancelledError:
            raise

    async def _inject(self, inject: tuple, frame_room_id: int, *, received_at=None, wire_turn=None, generation=None) -> None:
        type_name = str(inject[0])
        fields = dict(inject[1] or {}) if len(inject) >= 2 else {}
        delay = float(inject[2] or 0.0) if len(inject) >= 3 else 0.0
        guard = self.bridge.injection_guard_for(inject)
        created = time.monotonic()
        if delay > 0:
            await asyncio.sleep(delay)
        if generation is not None and generation != self._generation:
            self.stats.injects_dropped += 1
            return
        if self._stopping and type_name in {"pb.QuickStartREQ", "pb.EnterRoomREQ", "pb.RebyREQ", "pb.SetRebyREQ", "pb.SitDownREQ"}:
            self.stats.injects_dropped += 1
            return
        if type_name == "pb.ActionREQ" and (
            (wire_turn is not None and wire_turn != self._wire_turn)
            or (received_at is not None and time.monotonic() - received_at > _INJECT_TTL_SEC)
        ):
            self.stats.injects_dropped += 1
            log.warning("[BOT] 丢弃过期 ActionREQ：轮次已变化或通知已超时")
            return
        if self._closed.is_set() or (time.monotonic() - created) > delay + _INJECT_TTL_SEC:
            self.stats.injects_dropped += 1
            return
        if guard is not None and not self.bridge.injection_guard_is_current(guard):
            self.stats.injects_dropped += 1
            return
        if type_name == "pb.QuickStartREQ" and self._task_hands is not None:
            # A new table is being matched: the tasks' Omaha / AOF hands are played first.
            if self._match_lock.locked():
                # An earlier match request is on that errand already; this one repeats it.
                self.stats.injects_dropped += 1
                return
            async with self._match_lock:
                try:
                    await self._task_hands.run()
                except ConnectionError as exc:
                    await self._connection_lost(str(exc))
                if self._closed.is_set() or self._stopping or (
                        generation is not None and generation != self._generation):
                    self.stats.injects_dropped += 1
                    return
        rid = 0 if type_name == "pb.QuickStartREQ" else self.bridge.room_id_for_c2s(frame_room_id)
        ok = await self.send(type_name, fields, room_id=rid)
        if ok:
            self.stats.injects_sent += 1
        else:
            self.stats.injects_dropped += 1
            self.bridge.notify_inject_failed(type_name)

    # ── heartbeat ─────────────────────────────────────────────────────────

    async def _heartbeat_loop(self) -> None:
        try:
            while not self._closed.is_set():
                await asyncio.sleep(HEARTBEAT_INTERVAL_SEC)
                if self._pending_hb >= HEARTBEAT_MISS_LIMIT:
                    self.stats.heartbeats_missed += 1
                    log.warning("[WSS] heartbeat lost x%d, last_rx_age=%.1fs, disconnecting", self._pending_hb,
                                time.monotonic() - self.stats.last_rx_at)
                    await self._connection_lost("heartbeat lost")
                    return
                self._pending_hb += 1
                self.stats.heartbeats_sent += 1
                await self.send("pb.HeartBeatREQ", {}, room_id=0)
                # Clock for the table policy (timed re-match, empty-table grace, leave retry).
                # It goes through the bridge queue so it is serialised with real frames.
                wants_tick = getattr(self.bridge, "wants_tick", None)
                if callable(wants_tick) and wants_tick() and self.logged_in and not self._stopping:
                    self._bridge_queue.put_nowait(
                        ("pf.Tick", {"now": time.time()}, 0, time.monotonic(), self._wire_turn))
                if self._task_hands is not None and self.logged_in and self._task_hands.wants_break():
                    # A new game day's task hands: ask the table to be left when this hand ends.
                    # The match that follows goes through the errand first.
                    self._bridge_queue.put_nowait(
                        ("pf.Errand", {"reason": "task_hands"}, 0, time.monotonic(), self._wire_turn))
        except asyncio.CancelledError:
            raise


def _iter_injects(result: Any) -> tuple[tuple, ...]:
    if result is None:
        return ()
    if isinstance(result, list):
        return tuple(item for item in result if item)
    if isinstance(result, tuple) and result and isinstance(result[0], tuple):
        return tuple(item for item in result if item)
    return (result,)
