"""
PokerFate WSS MITM Proxy  (hosts-redirect edition)

Setup (one-time):
    1. python -m pf_intercept.gen_cert           # generate certs/
    2. Install certs/ca.crt into Windows Trusted Root CAs
    3. Add to C:\\Windows\\System32\\drivers\\etc\\hosts:
           127.0.0.1  <SERVER_HOST>
    4. python -m pf_intercept.proxy
       (Seat ID and blinds are auto-detected from game messages)
       Bark: device key in data/bark_key.txt (first line)

Traffic flow:
    Game  ->  127.0.0.1:9012  (TLS, WSS MITM)  ->  Real Server :9012
"""

import argparse
import asyncio
import os
import time
from pathlib import Path

import websockets

from pf_intercept.config import (
    PROXY_HOST, WSS_PORT, PASSTHROUGH_PORTS,
    SERVER_HOST, SERVER_WSS_PORT,
    SERVER_CERT,
    WATCH_S2C, WATCH_C2S,
    PREFERRED_WSS_HOSTS,
)
from pf_intercept.wire.framing import FrameBuffer, encode_frame
from pf_intercept.robot.tracker import RobotTracker
from pf_intercept.proxy.bot_worker import BotWorkerClient
from pf_intercept.proxy.heartbeat import HeartbeatTrace
from pf_intercept.proxy.logging_setup import (
    _ExpectedHandshakeNoiseFilter,
    configure_proxy_logging,
)
from pf_intercept.proxy.monitors import (
    start_calibration_spool_worker,
    stop_calibration_spool_worker,
)
from pf_intercept.proxy.passthrough import handle_passthrough
from pf_intercept.proxy.routes import (
    ProbedRoute,
    RuntimeRoute,
    ServerRouteCandidate,
    _choose_probed_route,
    _host_ok_ip_cache,
    _parse_server_route_candidates,
    _persist_ip_cache,
    _select_upstream_route,
)
from pf_intercept.proxy.tls import _make_client_ssl, _make_server_ssl
from pf_entertainment import EntertainmentRuntime
from pf_notify.client import notify
from pf_notify.config import load_bark_key_file, set_bark_key
from pokerfate.logger import archive_runtime_logs_on_startup

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_INTERCEPT_ROOT = _PROJECT_ROOT / "pf_intercept"
_DEFAULT_BARK_KEY_FILE = _PROJECT_ROOT / "data" / "bark_key.txt"


def _wss_close_is_abnormal(code: int | None) -> bool:
    return code is not None and code not in (1000, 1001)


_LOGS_DIR = _INTERCEPT_ROOT / "logs"

_DATA_DIR = _PROJECT_ROOT / "data"
_DATA_DIR.mkdir(exist_ok=True)
_WSS_GAP_WARN_SEC = float(os.environ.get("PF_WSS_GAP_WARN_SEC", "4.0"))
_EVENT_LOOP_LAG_WARN_SEC = float(os.environ.get("PF_EVENT_LOOP_LAG_WARN_SEC", "1.0"))
_BOT_INJECT_TTL_SEC = float(os.environ.get("PF_BOT_INJECT_TTL_SEC", "12.0"))


log, tcp_log = configure_proxy_logging(_LOGS_DIR)

from pf_intercept import config
from pf_intercept.wire import codec


# ── Bot worker client (constructed in main() with CLI options) ────────────────
_bot: BotWorkerClient | None = None
_entertainment: EntertainmentRuntime | None = None
_robot_tracker = RobotTracker(_DATA_DIR)

# ── Server state ──────────────────────────────────────────────────────────────
_real_server_sni: str = SERVER_HOST       # fallback SNI when Host header is absent
_wss_down_notice_active: bool = False
_active_wss_session_id: int = 0
_active_client_ws = None
_active_server_ws = None


def _is_active_wss_session(session_id: int) -> bool:
    return session_id == _active_wss_session_id


def _force_transport_close(ws) -> None:
    transport = getattr(ws, "transport", None)
    if transport is not None:
        try:
            transport.close()
        except Exception:
            log.debug("[WSS] transport.close ignored", exc_info=True)


async def _close_ws_quietly(
    ws,
    *,
    code: int = 1001,
    reason: str = "",
    timeout: float = 0.75,
) -> None:
    if ws is None:
        return
    try:
        await asyncio.wait_for(ws.close(code=code, reason=reason), timeout=timeout)
    except asyncio.TimeoutError:
        log.debug("[WSS] close timeout; force transport close (%s)", reason)
        _force_transport_close(ws)
    except Exception as exc:
        log.debug("[WSS] close ignored: %s", exc)


def _schedule_ws_close(ws, *, code: int = 1001, reason: str = "") -> None:
    if ws is None:
        return
    asyncio.create_task(_close_ws_quietly(ws, code=code, reason=reason))


# ── WSS MITM ──────────────────────────────────────────────────────────────────


async def _do_inject(
    server_ws,
    bot: BotWorkerClient,
    inject: dict,
    session_id: int,
) -> None:
    """Fire-and-forget coroutine: encode and send a bot action to the server."""
    if not _is_active_wss_session(session_id):
        log.info("[BOT→S] skip injection from stale WSS session #%s", session_id)
        return

    inject_type = str(inject.get("type_name") or "")
    inject_fields = dict(inject.get("fields") or {})
    inject_room_id = int(inject.get("room_id") or 0)
    delay_sec = max(0.0, float(inject.get("delay_sec") or 0.0))
    inject_guard = inject.get("guard")
    created_at = float(inject.get("created_at") or time.monotonic())

    def _expired() -> bool:
        return (time.monotonic() - created_at) > (delay_sec + _BOT_INJECT_TTL_SEC)

    if delay_sec and delay_sec > 0:
        await asyncio.sleep(float(delay_sec))
        if not _is_active_wss_session(session_id):
            log.info("[BOT→S] skip delayed injection from stale WSS session #%s", session_id)
            return
        if _expired():
            log.warning(
                "[BOT→S] skip expired delayed injection type=%s age=%.1fs delay=%.1fs",
                inject_type,
                time.monotonic() - created_at,
                delay_sec,
            )
            return

    if inject_guard is not None and not await bot.injection_guard_is_current(inject_guard):
        return
    if _expired():
        log.warning(
            "[BOT→S] skip expired injection type=%s age=%.1fs delay=%.1fs",
            inject_type,
            time.monotonic() - created_at,
            delay_sec,
        )
        return

    pb_body = codec.encode(inject_type, inject_fields)
    if pb_body is None:
        log.warning(
            "[BOT→S] %s encode failed (pb2 missing / ParseDict error) — skipping injection",
            inject_type,
        )
        bot.notify_inject_failed(inject_type)
        return

    if inject_type == "pb.UserValueREQ":
        inject_room_id = 0

    if inject_room_id == 0 and inject_type in (
        "pb.DelayLeaveRoomREQ",
        "pb.LeaveRoomREQ",
        "pb.EnterRoomREQ",
        "pb.QuickStartREQ",
        "pb.RebyREQ",
        "pb.ShowMyCardREQ",
    ):
        log.warning(
            "[BOT→S] %s 使用 room_id=0，服务器通常会忽略；"
            "请确认日志里出现过 EnterRoomRSP 且含 roomid，或 S2C 帧头曾出现非 0 room_id。",
            inject_type,
        )

    wire = encode_frame(inject_type, inject_room_id, pb_body)
    log.info("[BOT→S] %s room_id=%s %s", inject_type, inject_room_id, inject_fields)
    try:
        await server_ws.send(wire)
    except Exception as exc:
        log.warning("[BOT→S] inject send failed: %s", exc)
        bot.notify_inject_failed(inject_type)


def _make_entertainment_sender(server_ws):
    async def _send(type_name: str, fields: dict, room_id: int) -> None:
        pb_body = codec.encode(type_name, fields)
        if pb_body is None:
            raise RuntimeError(f"{type_name} encode failed")
        wire = encode_frame(type_name, int(room_id), pb_body)
        log.info("[ENT→S] %s room_id=%s %s", type_name, room_id, fields)
        await server_ws.send(wire)

    return _send


async def _c2s_analysis_worker(
    buf: FrameBuffer,
    queue: asyncio.Queue,
    session_id: int,
    heartbeat: HeartbeatTrace,
) -> None:
    """Consume raw C2S bytes and log watched message types (runs concurrently with forwarding)."""
    while True:
        raw = await queue.get()
        if raw is None:
            break
        for frame in buf.feed(raw):
            if frame.type_name == "pb.HeartBeatREQ":
                _seq, pending = heartbeat.note_req()
                if pending >= 2:
                    log.warning(
                        "[HB] session #%s heartbeat request pending=%d; %s",
                        heartbeat.session_id,
                        pending,
                        heartbeat.summary(),
                    )
            if frame.type_name in WATCH_C2S:
                msg = codec.decode(frame.type_name, frame.pb_body)
                log.debug("[C→S] %s  %s", frame.type_name, msg)


async def _s2c_analysis_worker(
    server_ws,
    buf: FrameBuffer,
    bot: BotWorkerClient,
    queue: asyncio.Queue,
    session_id: int,
    heartbeat: HeartbeatTrace,
) -> None:
    """Consume raw S2C bytes, parse frames, run bot logic, spawn inject tasks.

    Runs concurrently with the forwarding loop — the main loop forwards each
    message to the client immediately and only queues bytes here for analysis.
    Inject tasks are spawned as independent asyncio tasks so a delayed inject
    (e.g. sleep before action) never stalls analysis of subsequent messages.
    """
    while True:
        raw = await queue.get()
        if raw is None:
            break
        if not _is_active_wss_session(session_id):
            log.info("[WSS] stop analysis for stale session #%s", session_id)
            break
        for frame in buf.feed(raw):
            if frame.type_name == "pb.HeartBeatRSP":
                rtt_ms, pending = heartbeat.note_rsp()
                if rtt_ms is None:
                    log.warning(
                        "[HB] session #%s heartbeat response without tracked request; %s",
                        session_id,
                        heartbeat.summary(),
                    )
                elif rtt_ms >= 2000:
                    log.warning(
                        "[HB] session #%s heartbeat slow rtt=%.0fms client_pending=%d; %s",
                        session_id,
                        rtt_ms,
                        pending,
                        heartbeat.summary(),
                    )
            bot.submit_room_seen(session_id=session_id, room_id=frame.room_id)
            ent_msg = None
            if _entertainment is not None:
                _entertainment.note_room_id(frame.room_id)
                if frame.type_name in _entertainment.watched_s2c_types:
                    ent_msg = codec.decode(frame.type_name, frame.pb_body)
                    if ent_msg is not None:
                        _entertainment.observe_s2c(frame.type_name, ent_msg)
            if frame.type_name not in WATCH_S2C:
                continue
            msg = ent_msg if ent_msg is not None else codec.decode(frame.type_name, frame.pb_body)
            if msg is None:
                log.warning("[S→C] %s  (decode failed — run pf_intercept/tools/gen_pb2.sh first)", frame.type_name)
                continue
            if frame.type_name == "pb.SelfUserInfoRSP":
                brief = msg.get("brief") or {}
                uid = brief.get("uid")
                if uid is not None:
                    _robot_tracker.set_self_uid(uid)
            _robot_tracker.observe(frame.type_name, msg, room_id=frame.room_id)
            log.info("[S→C] %s  %s", frame.type_name, msg)
            bot.submit_s2c(
                session_id=session_id,
                type_name=frame.type_name,
                msg=msg,
                room_id=frame.room_id,
            )


async def _pipe_c2s(
    client_ws,
    server_ws,
    buf: FrameBuffer,
    session_id: int,
    heartbeat: HeartbeatTrace,
) -> None:
    """Game client → real server: forward immediately, analyze asynchronously."""
    analysis_queue: asyncio.Queue = asyncio.Queue()
    analysis_task = asyncio.create_task(
        _c2s_analysis_worker(buf, analysis_queue, session_id, heartbeat)
    )
    msg_count = 0
    try:
        async for raw in client_ws:
            msg_count += 1
            if isinstance(raw, str):
                raw = raw.encode()
            # Forward first — analysis must not block the relay path
            send_started = time.monotonic()
            await server_ws.send(raw)
            send_ms = (time.monotonic() - send_started) * 1000.0
            if send_ms >= 500:
                log.warning(
                    "[WSS] session #%s c2s send to upstream slow %.0fms bytes=%d; %s",
                    session_id,
                    send_ms,
                    len(raw),
                    heartbeat.summary(),
                )
            analysis_queue.put_nowait(raw)
    finally:
        analysis_queue.put_nowait(None)   # signal worker to exit
        await analysis_task
        log.info("[WSS] session #%s pipe c2s ended; messages=%d", session_id, msg_count)


async def _pipe_s2c(
    client_ws,
    server_ws,
    buf: FrameBuffer,
    session_id: int,
    heartbeat: HeartbeatTrace,
) -> None:
    """Real server → game client: forward immediately, analyze + inject asynchronously."""
    bot = _bot
    if bot is None:
        raise RuntimeError("BotWorker not initialised (main() must run first)")

    analysis_queue: asyncio.Queue = asyncio.Queue()
    analysis_task = asyncio.create_task(
        _s2c_analysis_worker(server_ws, buf, bot, analysis_queue, session_id, heartbeat)
    )
    msg_count = 0
    last_recv_at = time.monotonic()
    try:
        async for raw in server_ws:
            now = time.monotonic()
            gap_sec = now - last_recv_at
            last_recv_at = now
            msg_count += 1
            if isinstance(raw, str):
                raw = raw.encode()
            if gap_sec >= _WSS_GAP_WARN_SEC:
                log.info(
                    "[WSS] session #%s upstream s2c idle gap %.1fs before raw message "
                    "bytes=%d; %s",
                    session_id,
                    gap_sec,
                    len(raw),
                    heartbeat.summary(),
                )
            send_started = time.monotonic()
            await client_ws.send(raw)
            send_ms = (time.monotonic() - send_started) * 1000.0
            if send_ms >= 500:
                log.warning(
                    "[WSS] session #%s s2c send to client slow %.0fms bytes=%d; %s",
                    session_id,
                    send_ms,
                    len(raw),
                    heartbeat.summary(),
                )
            analysis_queue.put_nowait(raw)
    finally:
        analysis_queue.put_nowait(None)   # signal worker to exit
        await analysis_task
        log.info("[WSS] session #%s pipe s2c ended; messages=%d", session_id, msg_count)


async def _bot_inject_worker(
    server_ws,
    bot: BotWorkerClient,
    queue: asyncio.Queue,
    session_id: int,
) -> None:
    while True:
        inject = await queue.get()
        if inject is None:
            return
        if not _is_active_wss_session(session_id):
            log.info("[BOT→S] stop injection worker for stale WSS session #%s", session_id)
            return
        asyncio.create_task(_do_inject(server_ws, bot, inject, session_id))


async def _event_loop_lag_watch(session_id: int) -> None:
    """Log when synchronous work stalls the asyncio event loop."""
    interval = 0.5
    loop = asyncio.get_running_loop()
    expected = loop.time() + interval
    while True:
        await asyncio.sleep(interval)
        now = loop.time()
        lag_sec = now - expected
        if lag_sec >= _EVENT_LOOP_LAG_WARN_SEC:
            log.warning("[LOOP] session #%s event loop lag %.2fs", session_id, lag_sec)
        expected = now + interval


async def _run_wss_pair(client_ws, server_ws, session_id: int) -> None:
    bot = _bot
    if bot is None:
        raise RuntimeError("BotWorker not initialised (main() must run first)")
    inject_queue = bot.register_session(session_id)
    ent_token = None
    if _entertainment is not None:
        ent_token = _entertainment.attach_session(
            _make_entertainment_sender(server_ws)
        )
    tasks: dict[asyncio.Task, str] = {}
    lag_task = asyncio.create_task(_event_loop_lag_watch(session_id))
    inject_task = asyncio.create_task(
        _bot_inject_worker(server_ws, bot, inject_queue, session_id)
    )
    heartbeat = HeartbeatTrace(session_id)
    try:
        tasks = {
            asyncio.create_task(_pipe_c2s(client_ws, server_ws, FrameBuffer(), session_id, heartbeat)): "c2s",
            asyncio.create_task(_pipe_s2c(client_ws, server_ws, FrameBuffer(), session_id, heartbeat)): "s2c",
            inject_task: "bot_inject",
        }
        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for task in done:
            name = tasks.get(task, "?")
            try:
                exc = task.exception()
            except asyncio.CancelledError:
                exc = None
            if exc is None:
                log.info("[WSS] session #%s pipe %s stopped first; closing paired sockets", session_id, name)
            else:
                log.info(
                    "[WSS] session #%s pipe %s failed first (%s: %s); closing paired sockets",
                    session_id,
                    name,
                    type(exc).__name__,
                    exc,
                )

        await asyncio.gather(
            _close_ws_quietly(client_ws, reason="paired pipe stopped"),
            _close_ws_quietly(server_ws, reason="paired pipe stopped"),
            return_exceptions=True,
        )

        if pending:
            try:
                await asyncio.wait_for(
                    asyncio.gather(*pending, return_exceptions=True),
                    timeout=1.5,
                )
            except asyncio.TimeoutError:
                for task in pending:
                    log.info("[WSS] cancelling stuck pipe %s", tasks.get(task, "?"))
                    task.cancel()
                await asyncio.gather(*pending, return_exceptions=True)
    finally:
        lag_task.cancel()
        await asyncio.gather(lag_task, return_exceptions=True)
        log.info("[WSS] session #%s heartbeat summary: %s", session_id, heartbeat.summary())
        for task in tasks:
            if not task.done():
                task.cancel()
        bot.unregister_session(session_id)
        if _entertainment is not None and ent_token is not None:
            _entertainment.detach_session(ent_token)


async def _handle_wss(client_ws) -> None:
    """Handle one WSS MITM session."""
    global _wss_down_notice_active, _active_wss_session_id, _active_client_ws, _active_server_ws

    client_ssl = _make_client_ssl()
    server_ws = None

    prev_client_ws = _active_client_ws
    prev_server_ws = _active_server_ws
    _active_wss_session_id += 1
    session_id = _active_wss_session_id
    _active_client_ws = client_ws
    _active_server_ws = None
    if prev_client_ws is not None or prev_server_ws is not None:
        log.info("[WSS] session #%s supersedes previous WSS session", session_id)
        _schedule_ws_close(prev_client_ws, reason="superseded by reconnect")
        _schedule_ws_close(prev_server_ws, reason="superseded by reconnect")

    req = getattr(client_ws, "request", None)
    path = (req.path if req else None) or "/"
    req_headers = getattr(req, "headers", None)

    def _hdr(name: str) -> str | None:
        if req_headers is None:
            return None
        try:
            v = req_headers.get(name)
            if v is not None:
                return str(v)
        except Exception:
            log.exception("[WSS] failed to read client header %s", name)
        return None

    # Mirror client headers to upstream as much as possible.
    # Keep protocol-managed handshake headers under websockets' control.
    skip_headers = {
        "host",
        "connection",
        "upgrade",
        "sec-websocket-key",
        "sec-websocket-version",
        "sec-websocket-extensions",
        "sec-websocket-protocol",
    }
    additional_headers: list[tuple[str, str]] = []
    if req_headers is not None:
        try:
            for name, value in req_headers.raw_items():
                if str(name).lower() in skip_headers:
                    continue
                additional_headers.append((str(name), str(value)))
        except Exception:
            log.exception("[WSS] failed to mirror client headers")
            additional_headers = []

    subprotocols: list[str] | None = None
    proto_hdr = _hdr("Sec-WebSocket-Protocol")
    if proto_hdr:
        parsed = [p.strip() for p in proto_hdr.split(",") if p.strip()]
        if parsed:
            subprotocols = parsed

    # Upstream domain: read from client Host header (supports all PREFERRED_WSS_HOSTS),
    # fall back to global default.
    upstream_host = _hdr("host") or _real_server_sni
    if ":" in upstream_host:
        upstream_host = upstream_host.split(":")[0]
    route = await _select_upstream_route(upstream_host)
    upstream_uri = f"wss://{route.wss_upstream_host}:{route.wss_tcp_port}{path}"

    log.info(
        "[WSS] session #%s client connected, path=%s → %s "
        "(route=%s tcp=%s:%d latency=%s, fwd_headers=%d, subprotocols=%s)",
        session_id, path, upstream_uri,
        route.mode,
        route.wss_tcp_host,
        route.wss_tcp_port,
        f"{route.wss_latency_ms:.0f}ms" if route.wss_latency_ms is not None else "-",
        len(additional_headers), subprotocols,
    )
    print(f"[proxy] WSS 已连接  {upstream_uri}  (route={route.mode} tcp={route.wss_tcp_host}:{route.wss_tcp_port})")

    def _connect_kwargs(selected: RuntimeRoute):
        return dict(
            host=selected.wss_tcp_host,
            port=selected.wss_tcp_port,
            ssl=client_ssl,
            server_hostname=None if selected.mode == "ip" else selected.wss_upstream_host,
            additional_headers=additional_headers or None,
            subprotocols=subprotocols,
            user_agent_header=None,
            ping_interval=None, ping_timeout=None, open_timeout=15,
            close_timeout=2,  # don't block 10s waiting for server close-frame
        )

    try:
        try:
            async with websockets.connect(upstream_uri, **_connect_kwargs(route)) as upstream_ws:
                if not _is_active_wss_session(session_id):
                    await _close_ws_quietly(upstream_ws, reason="stale session")
                    return
                if route.mode == "host":
                    _host_ok_ip_cache[upstream_host] = route.wss_tcp_host
                    _persist_ip_cache()
                if _wss_down_notice_active:
                    notify("wss_reconnected")
                    _wss_down_notice_active = False
                server_ws = upstream_ws
                _active_server_ws = upstream_ws
                await _run_wss_pair(client_ws, server_ws, session_id)
        except (OSError, asyncio.TimeoutError) as net_err:
            # Network-level failure (TCP connect / TLS timeout): refresh DNS and retry once.
            log.warning(
                "[WSS] connect to %s via %s:%d failed: %s; refreshing route and retrying",
                upstream_host, route.wss_tcp_host, route.wss_tcp_port, net_err,
            )
            print(f"[proxy] WSS 连接失败 {upstream_host} ({route.wss_tcp_host}:{route.wss_tcp_port})，正在刷新线路重试...")
            fresh_route = await _select_upstream_route(upstream_host, force_refresh=True)
            if (fresh_route.wss_tcp_host, fresh_route.wss_tcp_port) != (route.wss_tcp_host, route.wss_tcp_port):
                log.info(
                    "[WSS] retry with fresh route: %s → %s:%d (%s)",
                    upstream_host,
                    fresh_route.wss_tcp_host,
                    fresh_route.wss_tcp_port,
                    fresh_route.mode,
                )
                async with websockets.connect(upstream_uri, **_connect_kwargs(fresh_route)) as upstream_ws:
                    if not _is_active_wss_session(session_id):
                        await _close_ws_quietly(upstream_ws, reason="stale session")
                        return
                    if fresh_route.mode == "host":
                        _host_ok_ip_cache[upstream_host] = fresh_route.wss_tcp_host
                        _persist_ip_cache()
                    if _wss_down_notice_active:
                        notify("wss_reconnected")
                        _wss_down_notice_active = False
                    server_ws = upstream_ws
                    _active_server_ws = upstream_ws
                    await _run_wss_pair(client_ws, server_ws, session_id)
            else:
                raise
    except websockets.exceptions.ConnectionClosed as exc:
        log.info(
            "[WSS] connection closed: type=%s code=%s reason=%r",
            type(exc).__name__,
            getattr(exc, "code", None),
            getattr(exc, "reason", None),
        )
    except Exception:
        log.exception("[WSS] session error")
    finally:
        _cc = getattr(client_ws, "close_code", None)
        _uc = getattr(server_ws, "close_code", None) if server_ws is not None else None
        log.info(
            "[WSS] session #%s ended; client(code=%s reason=%r state=%s) upstream(code=%s reason=%r state=%s)",
            session_id,
            _cc,
            getattr(client_ws, "close_reason", None),
            getattr(client_ws, "state", None),
            _uc,
            getattr(server_ws, "close_reason", None) if server_ws is not None else None,
            getattr(server_ws, "state", None) if server_ws is not None else None,
        )
        abnormal = _wss_close_is_abnormal(_cc) or _wss_close_is_abnormal(_uc)
        print(f"[proxy] WSS 已断开  client_code={_cc}  upstream_code={_uc}"
              + ("  ⚠️ 异常断开" if abnormal else ""))
        if abnormal and not _wss_down_notice_active:
            notify("wss_disconnected")
            _wss_down_notice_active = True
        if _is_active_wss_session(session_id):
            _active_client_ws = None
            _active_server_ws = None


# ── Entry point ───────────────────────────────────────────────────────────────

def _load_bark_key_from_file() -> None:
    key = load_bark_key_file(_DEFAULT_BARK_KEY_FILE)
    set_bark_key(key)
    if key:
        log.info("[Bark] key loaded from %s; proxy push enabled", _DEFAULT_BARK_KEY_FILE)
    else:
        log.info("[Bark] no key in %s; push disabled", _DEFAULT_BARK_KEY_FILE)


async def main(
    max_auto_rebuy: int = 1,
    profit_lock_bb: int | None = None,
    use_range_equity: bool = True,
    entertainment_web_host: str | None = config.ENTERTAINMENT_WEB_HOST,
    entertainment_web_port: int | None = config.ENTERTAINMENT_WEB_PORT,
) -> None:
    global _bot, _entertainment
    archive_runtime_logs_on_startup(_PROJECT_ROOT / "pokerfate" / "logs")
    _load_bark_key_from_file()
    if not Path(SERVER_CERT).exists():
        print("ERROR: certs not found. Run:  python -m pf_intercept.gen_cert")
        return

    if profit_lock_bb is not None:
        config.PROFIT_LOCK_BB_THRESHOLD = profit_lock_bb

    _bot = BotWorkerClient(
        max_auto_rebuy=max_auto_rebuy,
        profit_lock_bb=profit_lock_bb,
        use_range_equity=use_range_equity,
    )
    await _bot.start()
    start_calibration_spool_worker()
    _entertainment = EntertainmentRuntime(
        web_host=entertainment_web_host,
        web_port=entertainment_web_port,
    )
    _entertainment.set_bot_settings_handlers(
        _bot.runtime_settings,
        lambda payload: _bot.update_runtime_settings(
            profit_lock_bb=payload.get("profit_lock_bb"),
            decision_engine=payload.get("decision_engine"),
            preflop_sticky_pool_adjust=payload.get("preflop_sticky_pool_adjust"),
        ),
    )
    _entertainment.set_bot_dashboard_handler(_bot.bankroll_dashboard)
    await _entertainment.start()
    log.info(
        "[BOT] Waiting for SitDownRSP and EnterRoomRSP to detect seat / blinds "
        "(max_auto_rebuy=%d, profit_lock_bb=%d)",
        max_auto_rebuy,
        config.PROFIT_LOCK_BB_THRESHOLD,
    )
    log.info(
        "[HB] heartbeat trace enabled; wss_gap_warn=%.1fs loop_lag_warn=%.1fs",
        _WSS_GAP_WARN_SEC,
        _EVENT_LOOP_LAG_WARN_SEC,
    )
    print(
        f"[proxy] Bot 初始化完成  max_rebuy={max_auto_rebuy}  "
        f"profit_lock={config.PROFIT_LOCK_BB_THRESHOLD}BB  "
        f"equity_mode={'range' if use_range_equity else 'eqr'}"
    )
    print(f"[proxy] BotWorker 已启动  pid={_bot.pid}  日志={_LOGS_DIR / 'bot_worker.log'}")
    print(
        f"[proxy] 心跳监控  wss_gap_warn={_WSS_GAP_WARN_SEC:.1f}s  "
        f"loop_lag_warn={_EVENT_LOOP_LAG_WARN_SEC:.1f}s"
    )
    if entertainment_web_host is not None and entertainment_web_port is not None:
        urls = _entertainment.status_data().get("web_urls", [])
        print(f"[proxy] 娱乐游戏 Web {', '.join(urls) or '-'}")

    server_ssl = _make_server_ssl()

    await websockets.serve(
        _handle_wss,
        PROXY_HOST,
        WSS_PORT,
        ssl=server_ssl,
        # The game has its own heartbeat. Avoid proxy-initiated pings killing
        # the phone side on jittery office Wi-Fi.
        ping_interval=None,
        ping_timeout=None,
    )
    log.info("WSS MITM   %s:%d  →  wss://<domain>:%d  (dynamic per-connection)", PROXY_HOST, WSS_PORT, SERVER_WSS_PORT)
    print(f"[proxy] WSS MITM 已启动  {PROXY_HOST}:{WSS_PORT}  →  wss://<domain>:{SERVER_WSS_PORT}")

    for port in PASSTHROUGH_PORTS:
        if port == WSS_PORT:
            log.warning("Skipping passthrough on WSS port %d", WSS_PORT)
            continue
        await asyncio.start_server(
            lambda r, w, p=port: handle_passthrough(
                r,
                w,
                p,
                real_server_sni=lambda: _real_server_sni,
                log=log,
                tcp_log=tcp_log,
            ),
            PROXY_HOST, port,
        )
        log.info("TCP passthrough %s:%d  (target host from SNI/Host)", PROXY_HOST, port)
        print(f"[proxy] TCP passthrough 已启动  {PROXY_HOST}:{port}")

    for _h in PREFERRED_WSS_HOSTS:
        log.info("hosts entry:  127.0.0.1  %s", _h)
        print(f"[proxy] hosts entry:  127.0.0.1  {_h}")
    print("[proxy] 等待连接中... (Ctrl+C 停止)")
    try:
        await asyncio.Future()
    finally:
        stop_calibration_spool_worker()
        if _bot is not None:
            await _bot.stop()


def _parse_proxy_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="PokerFate WSS MITM proxy (auto seat/blinds; optional auto-rebuy cap)",
    )
    p.add_argument(
        "--max-auto-rebuy",
        type=int,
        default=1,
        metavar="N",
        choices=range(1, 21),
        help="本房间筹码清零时最多自动续入次数（1–20，默认 1）",
    )
    p.add_argument(
        "--profit-lock-bb",
        type=int,
        default=None,
        metavar="BB",
        help=f"盈利锁仓阈值（大盲倍数），达到后离桌再以 100BB 进房（默认用 pf_intercept.config 的值 {config.PROFIT_LOCK_BB_THRESHOLD}）",
    )
    p.add_argument(
        "--equity-mode",
        choices=["range", "eqr"],
        default="range",
        help="胜率模型：range=两阶段Range估算（默认），eqr=GTO+EQR（同mingli分支）",
    )
    p.add_argument(
        "--entertainment-web-host",
        default=config.ENTERTAINMENT_WEB_HOST,
        help=f"娱乐小游戏 Web 监听地址（默认 {config.ENTERTAINMENT_WEB_HOST}）",
    )
    p.add_argument(
        "--entertainment-web-port",
        type=int,
        default=config.ENTERTAINMENT_WEB_PORT,
        help=f"娱乐小游戏 Web 监听端口（默认 {config.ENTERTAINMENT_WEB_PORT}）",
    )
    p.add_argument(
        "--no-entertainment-web",
        action="store_true",
        help="不启动娱乐小游戏 Web",
    )
    return p.parse_args()


if __name__ == "__main__":
    _args = _parse_proxy_args()
    asyncio.run(
        main(
            max_auto_rebuy=_args.max_auto_rebuy,
            profit_lock_bb=_args.profit_lock_bb,
            use_range_equity=(_args.equity_mode == "range"),
            entertainment_web_host=(
                None if _args.no_entertainment_web else _args.entertainment_web_host
            ),
            entertainment_web_port=(
                None if _args.no_entertainment_web else _args.entertainment_web_port
            ),
        )
    )
