"""
PokerFate WSS MITM Proxy  (hosts-redirect edition)

Setup (one-time):
    1. python -m pf_intercept.gen_cert           # generate certs/
    2. Install certs/ca.crt as a trusted root CA on the device that runs the game client
    3. Point <SERVER_HOST> at this machine: the fake DNS (pf_intercept.dns_server),
       or the client's hosts file
    4. python -m pf_intercept.proxy           # or pf_intercept.launcher (macOS / Linux only)
       (Seat ID and blinds are auto-detected from game messages)
       Bark: device key in local/secrets/bark_key.txt (first line)

Traffic flow:
    Game  ->  this machine :9012  (TLS, WSS MITM)  ->  Real Server :9012
"""

import argparse
import asyncio
import os
import logging
import signal
import time
from pathlib import Path

import websockets

from pf_intercept.config import (
    PROXY_HOST, WSS_PORT, PASSTHROUGH_PORTS,
    SERVER_HOST, SERVER_WSS_PORT,
    SERVER_CERT,
    PREFERRED_WSS_HOSTS,
)
from pf_intercept.wire.framing import FrameBuffer, encode_frame
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
from pf_intercept.options import RunOptions, add_run_arguments
from pf_intercept.headless.process import RunningProcess, request_stop, ProcessControlError
from pf_notify.client import notify
from pf_notify.config import load_bark_key_file, set_bark_key
from pokerfate.logger import archive_runtime_logs_on_startup

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_INTERCEPT_ROOT = _PROJECT_ROOT / "pf_intercept"
_DEFAULT_BARK_KEY_FILE = _PROJECT_ROOT / "local" / "secrets" / "bark_key.txt"


def _wss_close_is_abnormal(code: int | None) -> bool:
    return code is not None and code not in (1000, 1001)


_LOGS_DIR = _INTERCEPT_ROOT / "logs"

_WSS_GAP_WARN_SEC = float(os.environ.get("PF_WSS_GAP_WARN_SEC", "4.0"))
_EVENT_LOOP_LAG_WARN_SEC = float(os.environ.get("PF_EVENT_LOOP_LAG_WARN_SEC", "1.0"))
_BOT_INJECT_TTL_SEC = float(os.environ.get("PF_BOT_INJECT_TTL_SEC", "12.0"))


log, tcp_log = logging.getLogger("pf_proxy"), logging.getLogger("pf_tcp")

from pf_intercept.wire import codec


# ── Bot worker client (constructed in main() with CLI options) ────────────────
_bot: BotWorkerClient | None = None
_entertainment: EntertainmentRuntime | None = None

# ── Server state ──────────────────────────────────────────────────────────────
_real_server_sni: str = SERVER_HOST       # fallback SNI when Host header is absent
_wss_down_notice_active: bool = False
_active_wss_session_id: int = 0
_active_client_ws = None
_active_server_ws = None


def _in_tournament_room() -> bool:
    """SNG/MTT tables are played by hand: the proxy stays silent there too."""
    settings = _bot.runtime_settings() if _bot is not None else None
    return bool((settings or {}).get("tournament_passthrough"))


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
) -> bool:
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
        return

    if inject_type in {"pb.UserValueREQ", "pb.QuickStartREQ"}:
        inject_room_id = 0

    if inject_room_id == 0 and inject_type in (
        "pb.DelayLeaveRoomREQ",
        "pb.LeaveRoomREQ",
        "pb.EnterRoomREQ",
        "pb.RebyREQ",
        "pb.SetRebyREQ",
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
        return True
    except Exception as exc:
        log.warning("[BOT→S] inject send failed: %s", exc)




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
            msg = codec.decode(frame.type_name, frame.pb_body)
            if msg is None:
                log.warning("[S→C] %s  (decode failed — run pf_intercept/tools/gen_pb2.sh first)", frame.type_name)
                continue
            log.info("[S→C] %s  %s", frame.type_name, msg)
            bot.submit_s2c(
                session_id=session_id,
                type_name=frame.type_name,
                msg=msg,
                room_id=frame.room_id,
            )


async def _pipe_c2s(client_ws, server_ws, buf, session_id, heartbeat) -> None:
    async for raw in client_ws:
        if not _is_active_wss_session(session_id):
            return
        if isinstance(raw, str):
            raw = raw.encode()
        for frame in buf.feed(raw):
            name = frame.type_name
            if name == "pb.HeartBeatREQ":
                heartbeat.note_req()
            elif name.endswith("REQ") and name != "pb.ActionREQ":
                msg = codec.decode(name, frame.pb_body)
                if msg is not None:
                    allowed = await _bot.call("client_request", {"session_id": session_id,
                                              "type_name": name, "msg": msg}, timeout=15)
                    if not allowed:
                        log.info("[C→S] %s handled by shared session", name)
                        continue
            await server_ws.send(encode_frame(name, frame.room_id, frame.pb_body))


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
    async def deliver(inject):
        ok = False
        try:
            ok = bool(await _do_inject(server_ws, bot, inject, session_id))
        finally:
            if inject.get("send_id"):
                bot.notify_wire_sent(session_id, inject["send_id"], ok)
    pending = set()
    try:
        while True:
            inject = await queue.get()
            if inject is None or not _is_active_wss_session(session_id):
                return
            if inject.get("kind") == "close_transport":
                await _close_ws_quietly(server_ws, reason="session recovery")
                return
            task = asyncio.create_task(deliver(inject))
            pending.add(task)
            task.add_done_callback(pending.discard)
    finally:
        for task in pending:
            task.cancel()
        await asyncio.gather(*pending, return_exceptions=True)


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


async def _run_wss_pair(client_ws, server_ws, session_id: int, upstream: str = "") -> None:
    bot = _bot
    if bot is None:
        raise RuntimeError("BotWorker not initialised (main() must run first)")
    inject_queue = bot.register_session(session_id, upstream)
    ent_token = None
    if _entertainment is not None:
        ent_token = _entertainment.attach_session()
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
                await _run_wss_pair(client_ws, server_ws, session_id, upstream_uri)
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
                    await _run_wss_pair(client_ws, server_ws, session_id,
                                        f"wss://{fresh_route.wss_upstream_host}:{fresh_route.wss_tcp_port}")
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
            if _in_tournament_room():
                log.info("[Bark] tournament room: skip wss_disconnected notify")
            else:
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


async def main(options: RunOptions | None = None, stop: asyncio.Event | None = None) -> None:
    global _bot, _entertainment
    from pf_entertainment.remote_live.publisher import start_remote_live
    from pf_intercept.headless.lobby.radar.board import Board as RadarBoard
    options = options or RunOptions()
    stop = stop or asyncio.Event()
    archive_runtime_logs_on_startup(_PROJECT_ROOT / "pokerfate" / "logs")
    if options.no_notify:
        set_bark_key(None)
    else:
        _load_bark_key_from_file()
    if not Path(SERVER_CERT).exists():
        raise FileNotFoundError("certs not found. Run: python -m pf_intercept.gen_cert")
    _bot = BotWorkerClient(options=options)
    servers, publisher = [], None
    try:
        await _bot.start()
        start_calibration_spool_worker()
        _entertainment = EntertainmentRuntime(
            web_host=None if options.no_web else options.web_host, web_port=options.web_port,
            live_source=_bot.live_snapshot, radar_board=RadarBoard())
        _entertainment.set_bot_dashboard_handler(_bot.bankroll_dashboard)
        await _entertainment.start()
        publisher = start_remote_live(_bot.live_snapshot, money_source=_bot.bankroll_dashboard,
                                      enabled=not options.no_remote_live)
        servers.append(await websockets.serve(_handle_wss, PROXY_HOST, WSS_PORT, ssl=_make_server_ssl(),
                                              ping_interval=None, ping_timeout=None))
        for port in PASSTHROUGH_PORTS:
            if port == WSS_PORT:
                continue
            servers.append(await asyncio.start_server(
                lambda r, w, p=port: handle_passthrough(r, w, p, real_server_sni=lambda: _real_server_sni,
                                                       log=log, tcp_log=tcp_log), PROXY_HOST, port))
        log.info("[RUN_OPTIONS] %s", options)
        print(f"[proxy] 已启动 pid={os.getpid()} worker={_bot.pid}；等待客户端登录")
        waits = [asyncio.create_task(stop.wait()), asyncio.create_task(_bot.failed.wait())]
        try:
            await asyncio.wait(waits, return_when=asyncio.FIRST_COMPLETED)
            if _bot.failed.is_set():
                raise RuntimeError("bot 工作进程已退出，停止代理与上传")
        finally:
            for task in waits:
                task.cancel()
            await asyncio.gather(*waits, return_exceptions=True)
        if _active_server_ws is not None:
            try:
                await _bot.call("graceful_leave", timeout=55)
            except Exception:
                log.exception("[proxy] 优雅离桌未完成，关闭连接")
    finally:
        for server in servers:
            server.close()
        await asyncio.gather(*(server.wait_closed() for server in servers), return_exceptions=True)
        await _close_ws_quietly(_active_client_ws, reason="proxy stopped")
        await _close_ws_quietly(_active_server_ws, reason="proxy stopped")
        if publisher is not None:
            await publisher.close()
        if _entertainment is not None:
            await _entertainment.close()
        stop_calibration_spool_worker()
        await _bot.stop()


def _parse_proxy_args(argv=None) -> argparse.Namespace:
    return add_run_arguments(argparse.ArgumentParser(description="PokerFate MITM 代理")).parse_args(argv)


_PID_FILE = _LOGS_DIR / "proxy.pid"


def run(args=None, before_start=None, cleanup=None) -> int:
    """Parse/stop/lock before launching helpers, then handle signals through graceful leave."""
    args = args or _parse_proxy_args()
    if args.stop:
        try:
            pid = request_stop(_PID_FILE)
            print(f"[proxy] 已向 PID {pid} 请求优雅停止" if pid else "[proxy] 没有运行实例")
            return 0
        except (ProcessControlError, OSError) as exc:
            print(f"[proxy] 停止失败：{exc}")
            return 2
    stop = asyncio.Event()
    previous = {sig: signal.signal(sig, lambda *_: stop.set()) for sig in (signal.SIGINT, signal.SIGTERM)}
    try:
        with RunningProcess(_PID_FILE):
            configure_proxy_logging(_LOGS_DIR, verbose=args.verbose)
            if before_start is not None and not stop.is_set():
                before_start()
            if not stop.is_set():
                asyncio.run(main(RunOptions.from_namespace(args), stop))
        return 0
    except (ProcessControlError, OSError, RuntimeError) as exc:
        log.error("[proxy] 启动失败：%s", exc)
        return 2
    finally:
        if cleanup is not None:
            cleanup()
        for sig, handler in previous.items():
            signal.signal(sig, handler)


if __name__ == "__main__":
    raise SystemExit(run())
