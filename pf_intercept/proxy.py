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
import json
import logging
import socket
import ssl
import struct
import sys
from pathlib import Path

import websockets
import websockets.exceptions

from pf_intercept.config import (
    PROXY_HOST, WSS_PORT, PASSTHROUGH_PORTS,
    SERVER_HOST, SERVER_WSS_PORT, EXTERNAL_DNS_SERVERS,
    SERVER_CERT, SERVER_KEY,
    WATCH_S2C, WATCH_C2S,
    PREFERRED_WSS_HOSTS,
)
from pf_intercept.framing import Frame, FrameBuffer, encode_frame
from pf_intercept.bot import BotBridge
from pf_entertainment import EntertainmentRuntime
from pf_notify import notify, set_bark_key, load_bark_key_file

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_BARK_KEY_FILE = _PROJECT_ROOT / "data" / "bark_key.txt"


def _wss_close_is_abnormal(code: int | None) -> bool:
    return code is not None and code not in (1000, 1001)


_LOGS_DIR = Path(__file__).parent / "logs"
_LOGS_DIR.mkdir(exist_ok=True)

_DATA_DIR = Path(__file__).parent.parent / "data"
_DATA_DIR.mkdir(exist_ok=True)
_IP_CACHE_FILE = _DATA_DIR / "ip_cache.json"


def _load_ip_cache() -> dict[str, str]:
    try:
        return json.loads(_IP_CACHE_FILE.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except Exception:
        logging.getLogger("pf_proxy").exception(
            "[IP cache] failed to load %s", _IP_CACHE_FILE
        )
        return {}


def _persist_ip_cache() -> None:
    try:
        _IP_CACHE_FILE.write_text(
            json.dumps(_host_ok_ip_cache, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    except Exception as exc:
        log.warning("[IP cache] persist failed for %s: %s", _IP_CACHE_FILE, exc)


_LOG_FMT = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")

def _fh(filename: str) -> logging.Handler:
    # 每次启动覆盖，不追加。
    h = logging.FileHandler(_LOGS_DIR / filename, mode="w", encoding="utf-8")
    h.setFormatter(_LOG_FMT)
    return h

def _console_warnings_handler() -> logging.Handler:
    h = logging.StreamHandler(sys.stderr)
    h.setLevel(logging.WARNING)
    h.setFormatter(_LOG_FMT)
    return h

# INFO still goes to proxy.log only; warnings/errors are mirrored to stderr so
# recoverable exceptions are visible in the console.
_root_logger = logging.getLogger()
_root_logger.setLevel(logging.INFO)
_root_logger.addHandler(_fh("proxy.log"))
_root_logger.addHandler(_console_warnings_handler())

# Dedicated TCP passthrough logger → tcp.log only (not mixed into proxy.log)
tcp_log = logging.getLogger("pf_tcp")
tcp_log.setLevel(logging.INFO)
tcp_log.propagate = False          # don't bubble up to root → proxy.log stays clean
tcp_log.addHandler(_fh("tcp.log"))
tcp_log.addHandler(_console_warnings_handler())

log = logging.getLogger("pf_proxy")

from pf_intercept import codec, config

# ── Bot singleton (constructed in main() with CLI options) ────────────────────
_bot: BotBridge | None = None
_entertainment: EntertainmentRuntime | None = None

# Set from pb.SelfUserInfoRSP.brief.uid so pb.EnterRoomRSP can patch table_status.seat[].player
_spoof_account_uid: str | None = None

# ── Server state ──────────────────────────────────────────────────────────────
_real_server_sni: str = SERVER_HOST       # fallback SNI when Host header is absent
_host_ok_ip_cache: dict[str, str] = _load_ip_cache()
_host_dns_cache: dict[str, list[str]] = {}
_host_connect_locks: dict[str, asyncio.Lock] = {}
_wss_down_notice_active: bool = False
_active_wss_session_id: int = 0
_active_client_ws = None
_active_server_ws = None


def _get_host_lock(hostname: str) -> asyncio.Lock:
    lock = _host_connect_locks.get(hostname)
    if lock is None:
        lock = asyncio.Lock()
        _host_connect_locks[hostname] = lock
    return lock


def _is_active_wss_session(session_id: int) -> bool:
    return session_id == _active_wss_session_id


async def _close_ws_quietly(ws, *, code: int = 1001, reason: str = "") -> None:
    if ws is None:
        return
    try:
        await ws.close(code=code, reason=reason)
    except Exception as exc:
        log.debug("[WSS] close ignored: %s", exc)


def _dns_query_a(hostname: str, nameserver: str) -> list[str]:
    """Direct UDP DNS A-record query bypassing OS resolver / hosts file."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(3.0)
    ips: list[str] = []
    try:
        qname = b"".join(bytes([len(p)]) + p.encode() for p in hostname.split(".")) + b"\x00"
        query = b"\x12\x34\x01\x00\x00\x01\x00\x00\x00\x00\x00\x00" + qname + b"\x00\x01\x00\x01"
        sock.sendto(query, (nameserver, 53))
        data, _ = sock.recvfrom(512)
        pos = 12 + len(qname) + 4          # skip header + question section
        for _ in range(struct.unpack(">H", data[6:8])[0]):
            if data[pos] & 0xC0 == 0xC0:   # compressed name pointer
                pos += 2
            else:
                while data[pos]:
                    pos += data[pos] + 1
                pos += 1
            rtype, _, _, rdlen = struct.unpack(">HHIH", data[pos:pos+10])
            pos += 10
            if rtype == 1 and rdlen == 4:  # A record
                ip = socket.inet_ntoa(data[pos:pos+4])
                if ip not in ips:
                    ips.append(ip)
            pos += rdlen
    except Exception as exc:
        log.debug("[DNS] query failed for %s: %s", hostname, exc)
    finally:
        sock.close()
    return ips



def _extract_sni_hostname(data: bytes) -> str | None:
    """
    Best-effort parse TLS ClientHello SNI hostname from raw bytes.
    """
    try:
        if len(data) < 5 or data[0] != 0x16:  # TLS handshake record
            return None
        rec_len = int.from_bytes(data[3:5], "big")
        if len(data) < 5 + rec_len:
            return None
        if data[5] != 0x01:  # ClientHello
            return None
        hs_len = int.from_bytes(data[6:9], "big")
        body_start = 9
        body_end = body_start + hs_len
        if body_end > len(data):
            return None
        p = body_start

        p += 2   # version
        p += 32  # random
        if p >= body_end:
            return None

        sid_len = data[p]
        p += 1 + sid_len
        if p + 2 > body_end:
            return None

        cs_len = int.from_bytes(data[p:p+2], "big")
        p += 2 + cs_len
        if p >= body_end:
            return None

        comp_len = data[p]
        p += 1 + comp_len
        if p + 2 > body_end:
            return None

        ext_len = int.from_bytes(data[p:p+2], "big")
        p += 2
        ext_end = p + ext_len
        if ext_end > body_end:
            return None

        while p + 4 <= ext_end:
            etype = int.from_bytes(data[p:p+2], "big")
            elen = int.from_bytes(data[p+2:p+4], "big")
            p += 4
            if p + elen > ext_end:
                return None
            if etype == 0x0000:  # server_name
                if elen < 2:
                    return None
                q = p + 2
                list_end = p + elen
                while q + 3 <= list_end:
                    ntype = data[q]
                    nlen = int.from_bytes(data[q+1:q+3], "big")
                    q += 3
                    if q + nlen > list_end:
                        return None
                    if ntype == 0:
                        return data[q:q+nlen].decode("ascii", errors="ignore")
                    q += nlen
            p += elen
    except Exception:
        log.exception("[TLS] failed to extract SNI from initial client bytes")
        return None
    return None


def _extract_http_host(data: bytes) -> str | None:
    """
    Best-effort parse HTTP Host header from raw bytes.
    """
    try:
        text = data.decode("iso-8859-1", errors="ignore")
        if "\r\n" not in text:
            return None
        lines = text.split("\r\n")
        if not lines or "HTTP/" not in lines[0]:
            return None
        for line in lines[1:]:
            if not line:
                break
            if line.lower().startswith("host:"):
                host = line.split(":", 1)[1].strip()
                return host
    except Exception:
        log.exception("[HTTP] failed to extract Host header")
        return None
    return None


def _extract_http_path(data: bytes) -> str | None:
    """Extract request path from plain HTTP request line (e.g. GET /api/login HTTP/1.1)."""
    try:
        line = data.split(b"\r\n", 1)[0].decode("iso-8859-1")
        parts = line.split(" ")
        if len(parts) >= 2 and parts[0] in (
            "GET", "POST", "PUT", "DELETE", "HEAD", "OPTIONS", "PATCH", "CONNECT"
        ):
            return parts[1]
    except Exception:
        log.exception("[HTTP] failed to extract request path")
    return None


def _resolve_host_candidates(hostname: str, force_refresh: bool = False) -> list[str]:
    """
    Resolve host from external DNS servers + system resolver fallback.
    By default, returns cached candidates without refreshing DNS.
    """
    cached = _host_dns_cache.get(hostname)
    if cached and not force_refresh:
        return list(cached)

    candidates: list[str] = []
    for dns in EXTERNAL_DNS_SERVERS:
        for ip in _dns_query_a(hostname, dns):
            if ip not in candidates:
                candidates.append(ip)

    try:
        infos = socket.getaddrinfo(hostname, None, socket.AF_INET, socket.SOCK_STREAM)
        for info in infos:
            ip = info[4][0]
            if ip not in candidates and not ip.startswith("127."):
                candidates.append(ip)
    except OSError as exc:
        log.warning("[DNS] system resolver failed for %s: %s", hostname, exc)
    except Exception:
        log.exception("[DNS] unexpected resolver failure for %s", hostname)

    _host_dns_cache[hostname] = list(candidates)
    return candidates


async def _connect_first_success(ips: list[str], port: int, timeout: float) -> tuple[str, asyncio.StreamReader, asyncio.StreamWriter] | None:
    """
    Attempt multiple upstream TCP connections concurrently and return first success.
    """
    if not ips:
        return None

    async def _one(ip: str):
        conn = asyncio.open_connection(ip, port)
        reader, writer = await asyncio.wait_for(conn, timeout=timeout)
        return ip, reader, writer

    tasks = [asyncio.create_task(_one(ip)) for ip in ips]
    try:
        pending = set(tasks)
        while pending:
            done, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
            for d in done:
                exc = d.exception()
                if exc is None:
                    ip, reader, writer = d.result()
                    for p in pending:
                        p.cancel()
                    if pending:
                        await asyncio.gather(*pending, return_exceptions=True)
                    return ip, reader, writer
        return None
    finally:
        for t in tasks:
            if not t.done():
                t.cancel()



# ── SSL contexts ──────────────────────────────────────────────────────────────

def _make_server_ssl() -> ssl.SSLContext:
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(certfile=SERVER_CERT, keyfile=SERVER_KEY)
    return ctx


def _make_client_ssl() -> ssl.SSLContext:
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE   # we connect by IP; real cert verified via SNI hostname match
    return ctx


# ── WSS MITM ──────────────────────────────────────────────────────────────────

def _patch_spoof_role_skin_frame(frame: Frame) -> Frame:
    """Rewrite SelfUserInfoRSP + EnterRoomRSP role_id / skin_id for local client display."""
    global _spoof_account_uid
    role = getattr(config, "SPOOF_USER_BRIEF_ROLE_ID", None)
    skin = getattr(config, "SPOOF_USER_BRIEF_SKIN_ID", None)
    if role is None and skin is None:
        return frame
    if frame.type_name not in ("pb.SelfUserInfoRSP", "pb.EnterRoomRSP"):
        return frame
    msg = codec.decode(frame.type_name, frame.pb_body)
    if not msg:
        return frame

    if frame.type_name == "pb.SelfUserInfoRSP":
        brief = msg.get("brief")
        if isinstance(brief, dict) and brief.get("uid") is not None:
            _spoof_account_uid = str(brief["uid"])
        if isinstance(brief, dict):
            if role is not None:
                brief["role_id"] = int(role)
            if skin is not None:
                brief["skin_id"] = int(skin)
        pb = codec.encode("pb.SelfUserInfoRSP", msg)
    else:
        if _spoof_account_uid:
            table = msg.get("table_status") or {}
            for seat in table.get("seat") or []:
                player = seat.get("player")
                if not isinstance(player, dict):
                    continue
                if str(player.get("uid")) != _spoof_account_uid:
                    continue
                if role is not None:
                    player["role_id"] = int(role)
                if skin is not None:
                    player["skin_id"] = int(skin)
                break
        pb = codec.encode("pb.EnterRoomRSP", msg)

    if pb is None:
        return frame
    return Frame(frame.type_name, frame.room_id, pb)


async def _do_inject(
    server_ws,
    bridge: "BotBridge",
    inject: tuple,
    inject_room_id: int,
    session_id: int,
) -> None:
    """Fire-and-forget coroutine: encode and send a bot action to the server."""
    if not _is_active_wss_session(session_id):
        log.info("[BOT→S] skip injection from stale WSS session #%s", session_id)
        return

    if len(inject) == 3:
        inject_type, inject_fields, delay_sec = inject
    else:
        inject_type, inject_fields = inject
        delay_sec = 0.0

    if delay_sec and delay_sec > 0:
        await asyncio.sleep(float(delay_sec))
        if not _is_active_wss_session(session_id):
            log.info("[BOT→S] skip delayed injection from stale WSS session #%s", session_id)
            return

    pb_body = codec.encode(inject_type, inject_fields)
    if pb_body is None:
        log.warning(
            "[BOT→S] %s encode failed (pb2 missing / ParseDict error) — skipping injection",
            inject_type,
        )
        bridge.notify_inject_failed(inject_type)
        return

    if inject_room_id == 0 and inject_type in (
        "pb.LeaveRoomREQ",
        "pb.EnterRoomREQ",
        "pb.QuickStartREQ",
        "pb.RebyREQ",
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


def _make_entertainment_sender(server_ws):
    async def _send(type_name: str, fields: dict, room_id: int) -> None:
        pb_body = codec.encode(type_name, fields)
        if pb_body is None:
            raise RuntimeError(f"{type_name} encode failed")
        wire = encode_frame(type_name, int(room_id), pb_body)
        log.info("[ENT→S] %s room_id=%s %s", type_name, room_id, fields)
        await server_ws.send(wire)

    return _send


async def _c2s_analysis_worker(buf: FrameBuffer, queue: asyncio.Queue) -> None:
    """Consume raw C2S bytes and log watched message types (runs concurrently with forwarding)."""
    while True:
        raw = await queue.get()
        if raw is None:
            break
        for frame in buf.feed(raw):
            if frame.type_name in WATCH_C2S:
                msg = codec.decode(frame.type_name, frame.pb_body)
                log.debug("[C→S] %s  %s", frame.type_name, msg)


async def _s2c_analysis_worker(
    server_ws,
    buf: FrameBuffer,
    bridge: "BotBridge",
    queue: asyncio.Queue,
    session_id: int,
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
            bridge.note_seen_room_id(frame.room_id)
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
                log.warning("[S→C] %s  (decode failed — run gen_pb2.sh first)", frame.type_name)
                continue
            log.info("[S→C] %s  %s", frame.type_name, msg)
            result = bridge.handle(frame.type_name, msg)
            if result is not None:
                inject_room_id = bridge.room_id_for_c2s(frame.room_id)
                asyncio.create_task(_do_inject(server_ws, bridge, result, inject_room_id, session_id))


async def _pipe_c2s(client_ws, server_ws, buf: FrameBuffer) -> None:
    """Game client → real server: forward immediately, analyze asynchronously."""
    analysis_queue: asyncio.Queue = asyncio.Queue()
    analysis_task = asyncio.create_task(_c2s_analysis_worker(buf, analysis_queue))
    msg_count = 0
    try:
        async for raw in client_ws:
            msg_count += 1
            if isinstance(raw, str):
                raw = raw.encode()
            # Forward first — analysis must not block the relay path
            await server_ws.send(raw)
            analysis_queue.put_nowait(raw)
    finally:
        analysis_queue.put_nowait(None)   # signal worker to exit
        await analysis_task
        log.info("[WSS] pipe c2s ended; messages=%d", msg_count)


async def _pipe_s2c(client_ws, server_ws, buf: FrameBuffer, session_id: int) -> None:
    """Real server → game client: forward immediately, analyze + inject asynchronously."""
    bridge = _bot
    if bridge is None:
        raise RuntimeError("BotBridge not initialised (main() must run first)")

    analysis_queue: asyncio.Queue = asyncio.Queue()
    analysis_task = asyncio.create_task(
        _s2c_analysis_worker(server_ws, buf, bridge, analysis_queue, session_id)
    )
    msg_count = 0
    use_spoof = (
        getattr(config, "SPOOF_USER_BRIEF_ROLE_ID", None) is not None
        or getattr(config, "SPOOF_USER_BRIEF_SKIN_ID", None) is not None
    )
    forward_buf = FrameBuffer() if use_spoof else None
    if use_spoof:
        global _spoof_account_uid
        _spoof_account_uid = None
    try:
        async for raw in server_ws:
            msg_count += 1
            if isinstance(raw, str):
                raw = raw.encode()
            if use_spoof and forward_buf is not None:
                frames = forward_buf.feed(raw)
                parts: list[bytes] = []
                for frame in frames:
                    frame = _patch_spoof_role_skin_frame(frame)
                    parts.append(encode_frame(frame.type_name, frame.room_id, frame.pb_body))
                await client_ws.send(b"".join(parts) + forward_buf.pending)
            else:
                await client_ws.send(raw)
            analysis_queue.put_nowait(raw)
    finally:
        analysis_queue.put_nowait(None)   # signal worker to exit
        await analysis_task
        log.info("[WSS] pipe s2c ended; messages=%d", msg_count)


async def _run_wss_pair(client_ws, server_ws, session_id: int) -> None:
    ent_token = None
    if _entertainment is not None:
        ent_token = _entertainment.attach_session(
            _make_entertainment_sender(server_ws)
        )
    try:
        await asyncio.gather(
            _pipe_c2s(client_ws, server_ws, FrameBuffer()),
            _pipe_s2c(client_ws, server_ws, FrameBuffer(), session_id),
        )
    finally:
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
        await _close_ws_quietly(prev_client_ws, reason="superseded by reconnect")
        await _close_ws_quietly(prev_server_ws, reason="superseded by reconnect")

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
    upstream_uri = f"wss://{upstream_host}:{SERVER_WSS_PORT}{path}"

    # IP resolution: cached good IP first, then DNS candidates, DNS refresh only on failure.
    def _pick_ip(force_refresh: bool = False) -> str | None:
        if not force_refresh:
            cached = _host_ok_ip_cache.get(upstream_host)
            if cached:
                return cached
        candidates = _resolve_host_candidates(upstream_host, force_refresh=force_refresh)
        return candidates[0] if candidates else None

    upstream_ip = _pick_ip() or upstream_host

    log.info(
        "[WSS] session #%s client connected, path=%s → %s (tcp=%s:%d, fwd_headers=%d, subprotocols=%s)",
        session_id, path, upstream_uri, upstream_ip, SERVER_WSS_PORT,
        len(additional_headers), subprotocols,
    )
    print(f"[proxy] WSS 已连接  {upstream_uri}  (ip={upstream_ip})")

    def _connect_kwargs(ip: str):
        return dict(
            host=ip,
            port=SERVER_WSS_PORT,
            ssl=client_ssl,
            server_hostname=upstream_host,
            additional_headers=additional_headers or None,
            subprotocols=subprotocols,
            user_agent_header=None,
            ping_interval=None, ping_timeout=None, open_timeout=15,
            close_timeout=2,  # don't block 10s waiting for server close-frame
        )

    try:
        try:
            async with websockets.connect(upstream_uri, **_connect_kwargs(upstream_ip)) as upstream_ws:
                if not _is_active_wss_session(session_id):
                    await _close_ws_quietly(upstream_ws, reason="stale session")
                    return
                _host_ok_ip_cache[upstream_host] = upstream_ip
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
                "[WSS] connect to %s (%s) failed: %s; refreshing DNS and retrying",
                upstream_host, upstream_ip, net_err,
            )
            print(f"[proxy] WSS 连接失败 {upstream_host} ({upstream_ip})，正在刷新 DNS 重试...")
            fresh_ip = _pick_ip(force_refresh=True)
            if fresh_ip and fresh_ip != upstream_ip:
                log.info("[WSS] retry with fresh IP: %s → %s", upstream_host, fresh_ip)
                async with websockets.connect(upstream_uri, **_connect_kwargs(fresh_ip)) as upstream_ws:
                    if not _is_active_wss_session(session_id):
                        await _close_ws_quietly(upstream_ws, reason="stale session")
                        return
                    _host_ok_ip_cache[upstream_host] = fresh_ip
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


# ── TCP pass-through (non-WSS ports) ─────────────────────────────────────────

async def _pipe_raw(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    try:
        while True:
            data = await reader.read(65536)
            if not data:
                break
            writer.write(data)
            await writer.drain()
    except (ConnectionResetError, asyncio.IncompleteReadError):
        pass
    finally:
        writer.close()


async def _handle_passthrough(
    client_reader: asyncio.StreamReader,
    client_writer: asyncio.StreamWriter,
    real_port: int,
) -> None:
    peer = client_writer.get_extra_info("peername")
    initial = b""
    try:
        initial = await asyncio.wait_for(client_reader.read(4096), timeout=0.2)
    except TimeoutError:
        initial = b""
    except Exception:
        log.exception("[TCP] failed to read initial client bytes from %s", peer)
        initial = b""

    target_host = _extract_sni_hostname(initial) or _extract_http_host(initial) or _real_server_sni or SERVER_HOST
    if ":" in target_host:
        target_host = target_host.split(":", 1)[0]

    srv_reader: asyncio.StreamReader | None = None
    srv_writer: asyncio.StreamWriter | None = None
    chosen_ip: str | None = None

    # Try cached-good IP first; this avoids DNS + candidate racing for stable hosts.
    cached = _host_ok_ip_cache.get(target_host)
    if cached:
        try:
            conn = asyncio.open_connection(cached, real_port)
            srv_reader, srv_writer = await asyncio.wait_for(conn, timeout=2.5)
            chosen_ip = cached
        except (OSError, asyncio.TimeoutError) as exc:
            tcp_log.warning("[TCP] cached upstream %s:%d failed: %s", cached, real_port, exc)
        except Exception:
            log.exception("[TCP] unexpected cached upstream failure %s:%d", cached, real_port)

    candidates: list[str] = []

    # Fallback: one coroutine per host computes candidates / selects reachable IP,
    # others wait and then consume the updated cache.
    if srv_writer is None:
        lock = _get_host_lock(target_host)
        async with lock:
            cached = _host_ok_ip_cache.get(target_host)
            if cached:
                try:
                    conn = asyncio.open_connection(cached, real_port)
                    srv_reader, srv_writer = await asyncio.wait_for(conn, timeout=2.5)
                    chosen_ip = cached
                except (OSError, asyncio.TimeoutError) as exc:
                    tcp_log.warning("[TCP] cached upstream %s:%d failed: %s", cached, real_port, exc)
                except Exception:
                    log.exception("[TCP] unexpected cached upstream failure %s:%d", cached, real_port)

            if srv_writer is None:
                if cached:
                    candidates.append(cached)
                for ip in _resolve_host_candidates(target_host, force_refresh=False):
                    if ip not in candidates:
                        candidates.append(ip)
                raced = await _connect_first_success(candidates, real_port, timeout=5.0)
                if raced is None:
                    # Only refresh DNS when current recorded candidates fail.
                    refreshed: list[str] = []
                    for ip in _resolve_host_candidates(target_host, force_refresh=True):
                        if ip not in refreshed:
                            refreshed.append(ip)
                    if refreshed:
                        candidates = refreshed
                        raced = await _connect_first_success(candidates, real_port, timeout=5.0)

                if raced is not None:
                    chosen_ip, srv_reader, srv_writer = raced
                    _host_ok_ip_cache[target_host] = chosen_ip
                    _persist_ip_cache()

    if srv_writer is None or srv_reader is None or chosen_ip is None:
        tcp_log.warning(
            "[TCP] no reachable upstream for %s:%d; host=%s; candidates=%s",
            peer, real_port, target_host, candidates
        )
        client_writer.close()
        return

    path = _extract_http_path(initial) if initial and not initial[0:1] == b"\x16" else None
    protocol = "TLS" if initial and initial[0:1] == b"\x16" else "HTTP"
    if path:
        tcp_log.info("[TCP] %s → %s:%d (%s)  %s %s",
                     peer, target_host, real_port, chosen_ip, protocol, path)
    else:
        tcp_log.info("[TCP] %s → %s:%d (%s)  [%s]",
                     peer, target_host, real_port, chosen_ip, protocol)
    _host_ok_ip_cache[target_host] = chosen_ip
    _persist_ip_cache()

    t0 = asyncio.get_event_loop().time()
    try:
        if initial:
            srv_writer.write(initial)
            await srv_writer.drain()
        await asyncio.gather(
            _pipe_raw(client_reader, srv_writer),
            _pipe_raw(srv_reader,    client_writer),
        )
    except Exception as exc:
        tcp_log.warning("[TCP] pass-through error: %s", exc)
    finally:
        elapsed = asyncio.get_event_loop().time() - t0
        tcp_log.info("[TCP] closed %s → %s:%d  (%.1fs)",
                     peer, target_host, real_port, elapsed)
        client_writer.close()


# ── Entry point ───────────────────────────────────────────────────────────────

def _load_bark_key_from_file() -> None:
    key = load_bark_key_file(_DEFAULT_BARK_KEY_FILE)
    set_bark_key(key)
    if not key:
        log.info("[Bark] no key in %s; push disabled", _DEFAULT_BARK_KEY_FILE)


async def main(
    max_auto_rebuy: int = 1,
    profit_lock_bb: int | None = None,
    spoof_role_id: int | None = None,
    spoof_skin_id: int | None = None,
    use_range_equity: bool = True,
    entertainment_web_host: str | None = config.ENTERTAINMENT_WEB_HOST,
    entertainment_web_port: int | None = config.ENTERTAINMENT_WEB_PORT,
) -> None:
    global _bot, _entertainment
    _load_bark_key_from_file()
    if not Path(SERVER_CERT).exists():
        print("ERROR: certs not found. Run:  python -m pf_intercept.gen_cert")
        return

    if profit_lock_bb is not None:
        config.PROFIT_LOCK_BB_THRESHOLD = profit_lock_bb

    if spoof_role_id is not None:
        config.SPOOF_USER_BRIEF_ROLE_ID = spoof_role_id
    if spoof_skin_id is not None:
        config.SPOOF_USER_BRIEF_SKIN_ID = spoof_skin_id

    _bot = BotBridge(max_auto_rebuy=max_auto_rebuy, use_range_equity=use_range_equity)
    _entertainment = EntertainmentRuntime(
        host=config.ENTERTAINMENT_CMD_HOST,
        port=config.ENTERTAINMENT_CMD_PORT,
        web_host=entertainment_web_host,
        web_port=entertainment_web_port,
    )
    await _entertainment.start()
    log.info(
        "[BOT] Waiting for SitDownRSP and EnterRoomRSP to detect seat / blinds "
        "(max_auto_rebuy=%d, profit_lock_bb=%d, spoof_role_id=%s, spoof_skin_id=%s)",
        max_auto_rebuy,
        config.PROFIT_LOCK_BB_THRESHOLD,
        config.SPOOF_USER_BRIEF_ROLE_ID,
        config.SPOOF_USER_BRIEF_SKIN_ID,
    )
    print(
        f"[proxy] Bot 初始化完成  max_rebuy={max_auto_rebuy}  "
        f"profit_lock={config.PROFIT_LOCK_BB_THRESHOLD}BB  "
        f"equity_mode={'range' if use_range_equity else 'eqr'}"
    )
    print(
        "[proxy] 娱乐游戏指令端口 "
        f"{config.ENTERTAINMENT_CMD_HOST}:{config.ENTERTAINMENT_CMD_PORT}；"
        "示例：python3 -m pf_entertainment.cli color red=1000 lvl=1"
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
            lambda r, w, p=port: _handle_passthrough(r, w, p),
            PROXY_HOST, port,
        )
        log.info("TCP passthrough %s:%d  (target host from SNI/Host)", PROXY_HOST, port)
        print(f"[proxy] TCP passthrough 已启动  {PROXY_HOST}:{port}")

    for _h in PREFERRED_WSS_HOSTS:
        log.info("hosts entry:  127.0.0.1  %s", _h)
        print(f"[proxy] hosts entry:  127.0.0.1  {_h}")
    print("[proxy] 等待连接中... (Ctrl+C 停止)")
    await asyncio.Future()


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
        help=f"盈利锁仓阈值（大盲倍数），达到后离桌再以 100BB 进房（默认用 config.py 里的值 {config.PROFIT_LOCK_BB_THRESHOLD}）",
    )
    p.add_argument(
        "--role-id",
        type=int,
        default=None,
        metavar="ID",
        help="篡改 SelfUserInfoRSP.brief 与 EnterRoomRSP 内本人座位的 player.role_id（本地展示）",
    )
    p.add_argument(
        "--skin-id",
        type=int,
        default=None,
        metavar="ID",
        help="篡改 SelfUserInfoRSP.brief 与 EnterRoomRSP 内本人座位的 player.skin_id（本地展示）",
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
            spoof_role_id=_args.role_id,
            spoof_skin_id=_args.skin_id,
            use_range_equity=(_args.equity_mode == "range"),
            entertainment_web_host=(
                None if _args.no_entertainment_web else _args.entertainment_web_host
            ),
            entertainment_web_port=(
                None if _args.no_entertainment_web else _args.entertainment_web_port
            ),
        )
    )
