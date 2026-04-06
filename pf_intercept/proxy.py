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
import logging.handlers
import socket
import ssl
import struct
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
from pf_intercept import codec, config
from pf_intercept.bot import BotBridge
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
    except Exception:
        return {}


def _persist_ip_cache() -> None:
    try:
        _IP_CACHE_FILE.write_text(
            json.dumps(_host_ok_ip_cache, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    except Exception as exc:
        log.debug("[IP cache] persist failed: %s", exc)


_LOG_FMT = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")

def _fh(filename: str) -> logging.Handler:
    h = logging.handlers.RotatingFileHandler(
        _LOGS_DIR / filename, maxBytes=10 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    h.setFormatter(_LOG_FMT)
    return h

# Console + proxy.log for all non-TCP logs.
# Use explicit setup instead of basicConfig() to avoid silent no-op when
# third-party libraries (websockets, asyncio) pre-register handlers before import.
_root_logger = logging.getLogger()
_root_logger.setLevel(logging.INFO)
_root_console = logging.StreamHandler()
_root_console.setFormatter(_LOG_FMT)
_root_logger.addHandler(_root_console)
_root_logger.addHandler(_fh("proxy.log"))

# Dedicated TCP passthrough logger → tcp.log only (not mixed into proxy.log)
tcp_log = logging.getLogger("pf_tcp")
tcp_log.setLevel(logging.INFO)
tcp_log.propagate = False          # don't bubble up to root → proxy.log stays clean
tcp_log.addHandler(_fh("tcp.log"))

log = logging.getLogger("pf_proxy")

# ── Bot singleton (constructed in main() with CLI options) ────────────────────
_bot: BotBridge | None = None

# Set from pb.SelfUserInfoRSP.brief.uid so pb.EnterRoomRSP can patch table_status.seat[].player
_spoof_account_uid: str | None = None

# ── Server state ──────────────────────────────────────────────────────────────
_real_server_sni: str = SERVER_HOST       # fallback SNI when Host header is absent
_host_ok_ip_cache: dict[str, str] = _load_ip_cache()
_host_dns_cache: dict[str, list[str]] = {}
_host_connect_locks: dict[str, asyncio.Lock] = {}


def _get_host_lock(hostname: str) -> asyncio.Lock:
    lock = _host_connect_locks.get(hostname)
    if lock is None:
        lock = asyncio.Lock()
        _host_connect_locks[hostname] = lock
    return lock


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
        pass
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
    except Exception:
        pass

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
) -> None:
    """Fire-and-forget coroutine: encode and send a bot action to the server."""
    if len(inject) == 3:
        inject_type, inject_fields, delay_sec = inject
    else:
        inject_type, inject_fields = inject
        delay_sec = 0.0

    if delay_sec and delay_sec > 0:
        await asyncio.sleep(float(delay_sec))

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
        for frame in buf.feed(raw):
            bridge.note_seen_room_id(frame.room_id)
            if frame.type_name not in WATCH_S2C:
                continue
            msg = codec.decode(frame.type_name, frame.pb_body)
            if msg is None:
                log.warning("[S→C] %s  (decode failed — run gen_pb2.sh first)", frame.type_name)
                continue
            log.info("[S→C] %s  %s", frame.type_name, msg)
            result = bridge.handle(frame.type_name, msg)
            if result is not None:
                inject_room_id = bridge.room_id_for_c2s(frame.room_id)
                asyncio.create_task(_do_inject(server_ws, bridge, result, inject_room_id))


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


async def _pipe_s2c(client_ws, server_ws, buf: FrameBuffer) -> None:
    """Real server → game client: forward immediately, analyze + inject asynchronously."""
    bridge = _bot
    if bridge is None:
        raise RuntimeError("BotBridge not initialised (main() must run first)")

    analysis_queue: asyncio.Queue = asyncio.Queue()
    analysis_task = asyncio.create_task(
        _s2c_analysis_worker(server_ws, buf, bridge, analysis_queue)
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


async def _handle_wss(client_ws) -> None:
    """Handle one WSS MITM session."""
    client_ssl = _make_client_ssl()
    server_ws = None

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
            pass
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
        "[WSS] client connected, path=%s → %s (tcp=%s:%d, fwd_headers=%d, subprotocols=%s)",
        path, upstream_uri, upstream_ip, SERVER_WSS_PORT,
        len(additional_headers), subprotocols,
    )

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
                _host_ok_ip_cache[upstream_host] = upstream_ip
                _persist_ip_cache()
                server_ws = upstream_ws
                await asyncio.gather(
                    _pipe_c2s(client_ws, server_ws, FrameBuffer()),
                    _pipe_s2c(client_ws, server_ws, FrameBuffer()),
                )
        except (OSError, asyncio.TimeoutError) as net_err:
            # Network-level failure (TCP connect / TLS timeout): refresh DNS and retry once.
            log.warning(
                "[WSS] connect to %s (%s) failed: %s; refreshing DNS and retrying",
                upstream_host, upstream_ip, net_err,
            )
            fresh_ip = _pick_ip(force_refresh=True)
            if fresh_ip and fresh_ip != upstream_ip:
                log.info("[WSS] retry with fresh IP: %s → %s", upstream_host, fresh_ip)
                async with websockets.connect(upstream_uri, **_connect_kwargs(fresh_ip)) as upstream_ws:
                    _host_ok_ip_cache[upstream_host] = fresh_ip
                    _persist_ip_cache()
                    server_ws = upstream_ws
                    await asyncio.gather(
                        _pipe_c2s(client_ws, server_ws, FrameBuffer()),
                        _pipe_s2c(client_ws, server_ws, FrameBuffer()),
                    )
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
            "[WSS] session ended; client(code=%s reason=%r state=%s) upstream(code=%s reason=%r state=%s)",
            _cc,
            getattr(client_ws, "close_reason", None),
            getattr(client_ws, "state", None),
            _uc,
            getattr(server_ws, "close_reason", None) if server_ws is not None else None,
            getattr(server_ws, "state", None) if server_ws is not None else None,
        )
        if _wss_close_is_abnormal(_cc) or _wss_close_is_abnormal(_uc):
            notify("wss_disconnected")


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
        except Exception:
            pass

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
                except Exception:
                    pass

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
        log.debug("[TCP] pass-through error: %s", exc)
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
) -> None:
    global _bot
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

    _bot = BotBridge(max_auto_rebuy=max_auto_rebuy)
    log.info(
        "[BOT] Waiting for SitDownRSP and EnterRoomRSP to detect seat / blinds "
        "(max_auto_rebuy=%d, profit_lock_bb=%d, spoof_role_id=%s, spoof_skin_id=%s)",
        max_auto_rebuy,
        config.PROFIT_LOCK_BB_THRESHOLD,
        config.SPOOF_USER_BRIEF_ROLE_ID,
        config.SPOOF_USER_BRIEF_SKIN_ID,
    )

    server_ssl = _make_server_ssl()

    await websockets.serve(
        _handle_wss,
        PROXY_HOST,
        WSS_PORT,
        ssl=server_ssl,
        # Send WebSocket PING to phone every 20s to prevent NAT idle timeout.
        ping_interval=20,
        ping_timeout=10,
    )
    log.info("WSS MITM   %s:%d  →  wss://<domain>:%d  (dynamic per-connection)", PROXY_HOST, WSS_PORT, SERVER_WSS_PORT)

    for port in PASSTHROUGH_PORTS:
        if port == WSS_PORT:
            log.warning("Skipping passthrough on WSS port %d", WSS_PORT)
            continue
        await asyncio.start_server(
            lambda r, w, p=port: _handle_passthrough(r, w, p),
            PROXY_HOST, port,
        )
        log.info("TCP passthrough %s:%d  (target host from SNI/Host)", PROXY_HOST, port)

    for _h in PREFERRED_WSS_HOSTS:
        log.info("hosts entry:  127.0.0.1  %s", _h)
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
    return p.parse_args()


if __name__ == "__main__":
    _args = _parse_proxy_args()
    asyncio.run(
        main(
            max_auto_rebuy=_args.max_auto_rebuy,
            profit_lock_bb=_args.profit_lock_bb,
            spoof_role_id=_args.role_id,
            spoof_skin_id=_args.skin_id,
        )
    )
