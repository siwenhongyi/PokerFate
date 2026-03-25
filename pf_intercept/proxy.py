"""
PokerFate WSS MITM Proxy  (hosts-redirect edition)

Setup (one-time):
    1. python -m pf_intercept.gen_cert           # generate certs/
    2. Install certs/ca.crt into Windows Trusted Root CAs
    3. Add to C:\\Windows\\System32\\drivers\\etc\\hosts:
           127.0.0.1  <SERVER_HOST>
    4. python -m pf_intercept.proxy
       (Seat ID and blinds are auto-detected from game messages)

Traffic flow:
    Game  ->  127.0.0.1:9012  (TLS, WSS MITM)  ->  Real Server :9012
"""

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
    SERVER_HOST, SERVER_WSS_PORT, REAL_SERVER_URI, EXTERNAL_DNS_SERVERS,
    SERVER_CERT, SERVER_KEY,
    WATCH_S2C, WATCH_C2S,
    PREFERRED_WSS_HOSTS,
)
from pf_intercept.framing import FrameBuffer, encode_frame
from pf_intercept import codec
from pf_intercept.bot import BotBridge

_LOGS_DIR = Path(__file__).parent / "logs"
_LOGS_DIR.mkdir(exist_ok=True)

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

# ── Bot singleton ─────────────────────────────────────────────────────────────
_bot = BotBridge()
log.info("[BOT] Waiting for SitDownRSP and EnterRoomRSP to detect seat / blinds")

# ── Dynamic server discovery ──────────────────────────────────────────────────
# Written by force_domain.py (mitmweb addon) when it intercepts the login response.
# Proxy reads this to learn the actual WSS server, then resolves via external DNS
# to bypass the local hosts-file redirect.
_DISCOVERED_FILE = Path(__file__).parent / "discovered_server.json"

_real_server_uri: str = REAL_SERVER_URI   # updated in _init_real_server()
_real_server_sni: str = SERVER_HOST       # TLS SNI hostname
_real_server_ip:  str = ""               # resolved real IP for passthrough
_host_ok_ip_cache: dict[str, str] = {}
_host_dns_cache: dict[str, list[str]] = {}
_host_connect_locks: dict[str, asyncio.Lock] = {}
_PREFERRED_WSS_HOSTS = set(PREFERRED_WSS_HOSTS)


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


def _probe_wss_endpoint(ip: str, port: int, sni_host: str) -> bool:
    """
    Probe whether endpoint responds like an HTTPS/WSS server.
    """
    req = (
        "GET / HTTP/1.1\r\n"
        f"Host: {sni_host}\r\n"
        "Upgrade: websocket\r\n"
        "Connection: Upgrade\r\n"
        "Sec-WebSocket-Key: SGVsbG9XZWJTb2NrZXQ=\r\n"
        "Sec-WebSocket-Version: 13\r\n\r\n"
    ).encode("ascii")
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    try:
        with socket.create_connection((ip, port), timeout=3.0) as raw_sock:
            with ctx.wrap_socket(raw_sock, server_hostname=sni_host) as tls_sock:
                tls_sock.settimeout(3.0)
                tls_sock.sendall(req)
                head = tls_sock.recv(32)
                return head.startswith(b"HTTP/1.")
    except Exception as exc:
        log.debug("[PROBE] %s:%d (%s) rejected: %s", ip, port, sni_host, exc)
        return False


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


def _init_real_server() -> None:
    """Resolve the real server URI, bypassing local hosts/dnsmasq."""
    global _real_server_uri, _real_server_sni, _real_server_ip

    host, port = SERVER_HOST, SERVER_WSS_PORT

    # 1. Check if force_domain.py wrote a discovered server
    if _DISCOVERED_FILE.exists():
        try:
            info = json.loads(_DISCOVERED_FILE.read_text())
            server_host_url = info.get("server_host", "")
            url = server_host_url.replace("wss://", "").replace("ws://", "")
            parts = url.split(":")
            discovered_host = parts[0]
            discovered_port = int(parts[1]) if len(parts) > 1 else SERVER_WSS_PORT
            if discovered_host in _PREFERRED_WSS_HOSTS:
                host = discovered_host
                port = discovered_port
                log.info("[SERVER] Using discovered server: %s:%d", host, port)
            else:
                log.warning(
                    "[SERVER] Ignoring discovered non-preferred host: %s:%d",
                    discovered_host, discovered_port
                )
        except Exception as exc:
            log.warning("[SERVER] Could not read discovered_server.json: %s", exc)

    # 2. Resolve host → real IP via external DNS servers (bypass hosts file)
    ip = None
    used_dns = None
    for dns in EXTERNAL_DNS_SERVERS:
        candidates = _dns_query_a(host, dns)
        if not candidates:
            continue
        log.info("[DNS] %s -> %s via %s", host, candidates, dns)
        for candidate_ip in candidates:
            if _probe_wss_endpoint(candidate_ip, port, host):
                ip = candidate_ip
                used_dns = dns
                break
        if ip:
            break
    if ip:
        log.info("[SERVER] Resolved %s → %s via %s", host, ip, used_dns)
        _real_server_uri = f"wss://{ip}:{port}"
        _real_server_sni = host
        _real_server_ip  = ip
    else:
        raise RuntimeError(
            "[SERVER] DNS resolution failed for "
            f"{host}. Refusing hostname fallback to avoid hosts-loopback."
        )


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

async def _pipe_c2s(client_ws, server_ws, buf: FrameBuffer) -> None:
    """Game client → real server."""
    msg_count = 0
    try:
        async for raw in client_ws:
            msg_count += 1
            if isinstance(raw, str):
                raw = raw.encode()
            for frame in buf.feed(raw):
                if frame.type_name in WATCH_C2S:
                    msg = codec.decode(frame.type_name, frame.pb_body)
                    log.debug("[C→S] %s  %s", frame.type_name, msg)
            await server_ws.send(raw)
    finally:
        log.info("[WSS] pipe c2s ended; messages=%d", msg_count)


async def _pipe_s2c(client_ws, server_ws, buf: FrameBuffer) -> None:
    """Real server → game client, with bot action injection."""
    msg_count = 0
    try:
        async for raw in server_ws:
            msg_count += 1
            if isinstance(raw, str):
                raw = raw.encode()

            inject: tuple[int, int] | None = None
            inject_room_id: int = 0

            for frame in buf.feed(raw):
                if frame.type_name not in WATCH_S2C:
                    continue

                msg = codec.decode(frame.type_name, frame.pb_body)
                if msg is None:
                    log.warning("[S→C] %s  (decode failed — run gen_pb2.sh first)", frame.type_name)
                    continue

                log.info("[S→C] %s  %s", frame.type_name, msg)

                result = _bot.handle(frame.type_name, msg)
                if result is not None:
                    inject = result
                    inject_room_id = frame.room_id

            # Forward original server message to the game client
            await client_ws.send(raw)

            # Inject bot action to the real server (after client got the notify)
            if inject is not None:
                action_type, chips = inject
                pb_body = codec.encode("pb.ActionREQ", {
                    "action_type": action_type,
                    "chips": chips,
                })
                if not pb_body:
                    log.warning("[BOT→S] ActionREQ encode failed (pb2 not compiled?) — skipping injection")
                else:
                    wire = encode_frame("pb.ActionREQ", inject_room_id, pb_body)
                    log.info("[BOT→S] ActionREQ  action_type=%d  chips=%d", action_type, chips)
                    await server_ws.send(wire)
    finally:
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
            # Best effort only; if request headers are unavailable, continue safely.
            additional_headers = []

    # Pass through requested subprotocols via dedicated argument.
    subprotocols: list[str] | None = None
    proto_hdr = _hdr("Sec-WebSocket-Protocol")
    if proto_hdr:
        parsed = [p.strip() for p in proto_hdr.split(",") if p.strip()]
        if parsed:
            subprotocols = parsed
    # Keep URI host as domain so websockets sends the correct HTTP Host header.
    # Override TCP destination with resolved IP to avoid local hosts-loopback.
    upstream_uri = f"wss://{_real_server_sni}:{SERVER_WSS_PORT}{path}"
    tcp_target = _real_server_ip or _real_server_sni
    log.info(
        "[WSS] client connected, path=%s → %s (tcp=%s:%d, sni=%s, fwd_header_count=%d, fwd_headers=%s, subprotocols=%s)",
        path, upstream_uri, tcp_target, SERVER_WSS_PORT, _real_server_sni,
        len(additional_headers),
        sorted({name for name, _ in additional_headers}),
        subprotocols,
    )
    try:
        async with websockets.connect(
            upstream_uri,
            host=tcp_target,
            port=SERVER_WSS_PORT,
            ssl=client_ssl,
            server_hostname=_real_server_sni,
            additional_headers=additional_headers or None,
            subprotocols=subprotocols,
            # Disable proxy-initiated keepalive; keep this layer forwarding-only.
            user_agent_header=None,
            ping_interval=None, ping_timeout=None, open_timeout=15,
        ) as upstream_ws:
            server_ws = upstream_ws
            await asyncio.gather(
                _pipe_c2s(client_ws, server_ws, FrameBuffer()),
                _pipe_s2c(client_ws, server_ws, FrameBuffer()),
            )
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
        log.info(
            "[WSS] session ended; client(code=%s reason=%r state=%s) upstream(code=%s reason=%r state=%s)",
            getattr(client_ws, "close_code", None),
            getattr(client_ws, "close_reason", None),
            getattr(client_ws, "state", None),
            getattr(server_ws, "close_code", None) if server_ws is not None else None,
            getattr(server_ws, "close_reason", None) if server_ws is not None else None,
            getattr(server_ws, "state", None) if server_ws is not None else None,
        )


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
                if not candidates and target_host == _real_server_sni and _real_server_ip:
                    candidates.append(_real_server_ip)

                raced = await _connect_first_success(candidates, real_port, timeout=5.0)
                if raced is None:
                    # Only refresh DNS when current recorded candidates fail.
                    refreshed: list[str] = []
                    for ip in _resolve_host_candidates(target_host, force_refresh=True):
                        if ip not in refreshed:
                            refreshed.append(ip)
                    if not refreshed and target_host == _real_server_sni and _real_server_ip:
                        refreshed.append(_real_server_ip)
                    if refreshed:
                        candidates = refreshed
                        raced = await _connect_first_success(candidates, real_port, timeout=5.0)

                if raced is not None:
                    chosen_ip, srv_reader, srv_writer = raced
                    _host_ok_ip_cache[target_host] = chosen_ip

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

async def main() -> None:
    if not Path(SERVER_CERT).exists():
        print("ERROR: certs not found. Run:  python -m pf_intercept.gen_cert")
        return

    _init_real_server()

    server_ssl = _make_server_ssl()

    await websockets.serve(
        _handle_wss,
        PROXY_HOST,
        WSS_PORT,
        ssl=server_ssl,
        # Disable proxy-side pings toward the game client as well.
        ping_interval=None,
        ping_timeout=None,
    )
    log.info("WSS MITM   %s:%d  →  %s", PROXY_HOST, WSS_PORT, _real_server_uri)

    for port in PASSTHROUGH_PORTS:
        if port == WSS_PORT:
            log.warning("Skipping passthrough on WSS port %d", WSS_PORT)
            continue
        await asyncio.start_server(
            lambda r, w, p=port: _handle_passthrough(r, w, p),
            PROXY_HOST, port,
        )
        log.info("TCP passthrough %s:%d  (target host from SNI/Host)", PROXY_HOST, port)

    log.info("hosts entry:  127.0.0.1  %s", _real_server_sni)
    await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())
