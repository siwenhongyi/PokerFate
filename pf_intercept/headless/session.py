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
from dataclasses import dataclass
from typing import Any, Awaitable, Callable
from urllib.parse import urlparse

import websockets

from pf_intercept import config
from pf_intercept.bot import BotBridge
from pf_intercept.headless.login import LoginResult, ServerEntry
from pf_intercept.wire import codec
from pf_intercept.wire.framing import FrameBuffer, encode_frame

log = logging.getLogger("pf_headless")

HEARTBEAT_INTERVAL_SEC = 5.0          # MainScene.lua: bee.schedule(5, …)
HEARTBEAT_MISS_LIMIT = 2              # client gives up after 2 unanswered beats
LOGIN_RSP_TIMEOUT_SEC = 15.0
LOGIN_QUEUE_CODE = 1002               # LOGIN_ERR_ENTER_QUEUE
LOBBY_HOLDEM_GAME_TYPE = 10010101     # GAME_GAME_TYPE.LOBBY_HOLDEM_GAME
_INJECT_TTL_SEC = 20.0

# S2C frames the session itself reacts to, on top of the bridge's WATCH_S2C.
_SESSION_TYPES = frozenset({"pb.UserLoginRSP", "pb.HeartBeatRSP", "pb.QuickStartRSP"})


class SessionClosed(RuntimeError):
    pass


@dataclass
class SessionStats:
    frames_in: int = 0
    frames_bot: int = 0
    injects_sent: int = 0
    injects_dropped: int = 0
    heartbeats_sent: int = 0
    heartbeats_missed: int = 0
    last_rx_at: float = 0.0


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
    """One WSS connection driving one BotBridge."""

    def __init__(
        self,
        login: LoginResult,
        *,
        bridge: BotBridge | None = None,
        chnl: int = int(config.GAMEDATA_CHNL),
        client_version: str = str(config.GAME_HTTP_VERSION),
        max_auto_rebuy: int = 1,
        on_frame: Callable[[str, dict], Awaitable[None] | None] | None = None,
    ) -> None:
        self.login = login
        self.bridge = bridge if bridge is not None else BotBridge(max_auto_rebuy=max_auto_rebuy)
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
        self._bridge_lock = asyncio.Lock()
        self._pending_hb = 0
        self._tasks: list[asyncio.Task] = []

    # ── lifecycle ─────────────────────────────────────────────────────────

    @property
    def connected(self) -> bool:
        return self._ws is not None and not self._closed.is_set()

    @property
    def logged_in(self) -> bool:
        return self._login_done.is_set() and self._login_code == 0

    async def connect(self, server_index: int = 0) -> None:
        """Open the socket and complete pb.UserLoginREQ; raises on failure."""
        servers = self.login.servers
        if not servers:
            raise SessionClosed("登录结果里没有服务器")
        self._server = servers[server_index % len(servers)]
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
        self._closed.clear()
        self._login_done.clear()
        self._login_code = None
        self._tasks = [
            asyncio.create_task(self._recv_loop(), name="headless-recv"),
            asyncio.create_task(self._heartbeat_loop(), name="headless-heartbeat"),
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
            if self._login_code == 0:
                return
            if self._login_code == LOGIN_QUEUE_CODE:
                # Login queue: server will send another UserLoginRSP when it is
                # our turn; keep the socket (and heartbeat) alive meanwhile.
                log.warning("[WSS] 登录排队中 pos=%s，继续等待", self._queue_pos)
                self._login_done.clear()
                deadline = time.monotonic() + 600
                continue
            raise SessionClosed(f"UserLoginRSP code={self._login_code}")

    async def close(self, reason: str = "") -> None:
        if self._closed.is_set():
            return
        self._closed.set()
        for t in self._tasks:
            t.cancel()
        self._tasks = []
        if self._ws is not None:
            try:
                await self._ws.close(code=1000, reason=reason[:100])
            except Exception:
                pass
        log.info("[WSS] closed (%s) %s", reason or "-", self.stats)

    async def wait_closed(self) -> None:
        await self._closed.wait()

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
            await self.close(f"send failed: {exc}")
            return False
        return True

    async def quick_start(self, *, big_blind: int, buyin_bb: int = 100, wait_blind: bool = False) -> bool:
        """Ask the lobby for a cash table (LobbyByinDialog StartButton)."""
        return await self.send("pb.QuickStartREQ", {
            "boot": int(big_blind),
            "game_type": LOBBY_HOLDEM_GAME_TYPE,
            "lobby_coin": int(config.PROFIT_LOCK_FALLBACK_LOBBY_COIN),
            "byin_chips": int(big_blind) * int(buyin_bb),
            "wait_blind": bool(wait_blind),
            "ip": self.login.login_ip or "",
        }, room_id=0)

    # ── receiving ─────────────────────────────────────────────────────────

    async def _recv_loop(self) -> None:
        buf = FrameBuffer()
        try:
            async for raw in self._ws:
                if isinstance(raw, str):
                    raw = raw.encode("utf-8")
                for frame in buf.feed(raw):
                    self.stats.frames_in += 1
                    self.stats.last_rx_at = time.monotonic()
                    self.bridge.note_seen_room_id(frame.room_id)
                    await self._on_s2c(frame.type_name, frame.room_id, frame.pb_body)
        except asyncio.CancelledError:
            raise
        except websockets.ConnectionClosed as exc:
            log.warning("[WSS] connection closed by peer code=%s reason=%r", exc.code, exc.reason)
        except Exception:
            log.exception("[WSS] recv loop error")
        finally:
            if not self._login_done.is_set():
                self._login_code = self._login_code or -1
                self._login_done.set()
            await self.close("recv loop ended")

    async def _on_s2c(self, type_name: str, room_id: int, pb_body: bytes) -> None:
        if type_name == "pb.HeartBeatRSP":
            self._pending_hb = 0
            return
        if type_name not in _SESSION_TYPES and type_name not in config.WATCH_S2C:
            return
        msg = codec.decode(type_name, pb_body)
        if msg is None:
            log.warning("[S→C] %s decode failed (%d bytes)", type_name, len(pb_body))
            return
        log.info("[S→C] %s %s", type_name, msg)

        if type_name == "pb.UserLoginRSP":
            self._login_code = int(msg.get("code", 0) or 0)
            self._queue_pos = msg.get("pos")
            self._login_done.set()
        elif type_name == "pb.QuickStartRSP":
            code = int(msg.get("code", 0) or 0)
            if code != 0:
                log.warning("[WSS] QuickStartRSP code=%s（进桌失败）", code)

        if self.on_frame is not None:
            out = self.on_frame(type_name, msg)
            if asyncio.iscoroutine(out):
                await out

        if type_name not in config.WATCH_S2C:
            return
        self.stats.frames_bot += 1
        # Bridge work (equity / CFR) can take seconds; keep heartbeat + recv alive.
        async with self._bridge_lock:
            result = await asyncio.to_thread(self.bridge.handle, type_name, msg)
        for inject in _iter_injects(result):
            asyncio.create_task(self._inject(inject, room_id), name="headless-inject")

    async def _inject(self, inject: tuple, frame_room_id: int) -> None:
        type_name = str(inject[0])
        fields = dict(inject[1] or {}) if len(inject) >= 2 else {}
        delay = float(inject[2] or 0.0) if len(inject) >= 3 else 0.0
        guard = self.bridge.injection_guard_for(inject)
        created = time.monotonic()
        if delay > 0:
            await asyncio.sleep(delay)
        if self._closed.is_set() or (time.monotonic() - created) > delay + _INJECT_TTL_SEC:
            self.stats.injects_dropped += 1
            return
        if guard is not None and not self.bridge.injection_guard_is_current(guard):
            self.stats.injects_dropped += 1
            return
        ok = await self.send(type_name, fields, room_id=self.bridge.room_id_for_c2s(frame_room_id))
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
                    log.warning("[WSS] heartbeat lost x%d, closing", self._pending_hb)
                    await self.close("heartbeat lost")
                    return
                self._pending_hb += 1
                self.stats.heartbeats_sent += 1
                await self.send("pb.HeartBeatREQ", {}, room_id=0)
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
