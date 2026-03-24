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
import socket
import ssl
import struct
from pathlib import Path

import websockets
import websockets.exceptions

from pf_intercept.config import (
    PROXY_HOST, WSS_PORT, PASSTHROUGH_PORTS,
    SERVER_HOST, SERVER_WSS_PORT, REAL_SERVER_URI, EXTERNAL_DNS,
    SERVER_CERT, SERVER_KEY,
    WATCH_S2C, WATCH_C2S,
)
from pf_intercept.framing import FrameBuffer, encode_frame
from pf_intercept import codec
from pf_intercept.bot import BotBridge

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
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


def _dns_query_a(hostname: str, nameserver: str = EXTERNAL_DNS) -> str | None:
    """Direct UDP DNS A-record query bypassing OS resolver / hosts file."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(3.0)
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
                return socket.inet_ntoa(data[pos:pos+4])
            pos += rdlen
    except Exception as exc:
        log.debug("[DNS] query failed for %s: %s", hostname, exc)
    finally:
        sock.close()
    return None


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
            host = parts[0]
            port = int(parts[1]) if len(parts) > 1 else SERVER_WSS_PORT
            log.info("[SERVER] Using discovered server: %s:%d", host, port)
        except Exception as exc:
            log.warning("[SERVER] Could not read discovered_server.json: %s", exc)

    # 2. Resolve host → real IP via external DNS (bypass hosts file)
    ip = _dns_query_a(host)
    if ip:
        log.info("[SERVER] Resolved %s → %s via %s", host, ip, EXTERNAL_DNS)
        _real_server_uri = f"wss://{ip}:{port}"
        _real_server_sni = host
        _real_server_ip  = ip
    else:
        log.warning("[SERVER] DNS resolution failed, using hostname directly: %s:%d", host, port)
        _real_server_uri = f"wss://{host}:{port}"
        _real_server_sni = host
        _real_server_ip  = host


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
    async for raw in client_ws:
        if isinstance(raw, str):
            raw = raw.encode()
        for frame in buf.feed(raw):
            if frame.type_name in WATCH_C2S:
                msg = codec.decode(frame.type_name, frame.pb_body)
                log.debug("[C→S] %s  %s", frame.type_name, msg)
        await server_ws.send(raw)


async def _pipe_s2c(client_ws, server_ws, buf: FrameBuffer) -> None:
    """Real server → game client, with bot action injection."""
    async for raw in server_ws:
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


async def _handle_wss(client_ws) -> None:
    """Handle one WSS MITM session."""
    client_ssl = _make_client_ssl()
    log.info("[WSS] client connected → %s (sni=%s)", _real_server_uri, _real_server_sni)
    try:
        async with websockets.connect(
            _real_server_uri, ssl=client_ssl, server_hostname=_real_server_sni
        ) as server_ws:
            await asyncio.gather(
                _pipe_c2s(client_ws, server_ws, FrameBuffer()),
                _pipe_s2c(client_ws, server_ws, FrameBuffer()),
            )
    except websockets.exceptions.ConnectionClosed:
        pass
    except Exception:
        log.exception("[WSS] session error")
    finally:
        log.info("[WSS] session ended")


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
    # Use resolved IP to avoid hosts-file loopback on Windows
    target = _real_server_ip or SERVER_HOST
    log.info("[TCP] %s → %s:%d", peer, target, real_port)
    try:
        srv_reader, srv_writer = await asyncio.open_connection(target, real_port)
        await asyncio.gather(
            _pipe_raw(client_reader, srv_writer),
            _pipe_raw(srv_reader,    client_writer),
        )
    except Exception as exc:
        log.debug("[TCP] pass-through error: %s", exc)
    finally:
        client_writer.close()


# ── Entry point ───────────────────────────────────────────────────────────────

async def main() -> None:
    if not Path(SERVER_CERT).exists():
        print("ERROR: certs not found. Run:  python -m pf_intercept.gen_cert")
        return

    _init_real_server()

    server_ssl = _make_server_ssl()

    await websockets.serve(_handle_wss, PROXY_HOST, WSS_PORT, ssl=server_ssl)
    log.info("WSS MITM   %s:%d  →  %s", PROXY_HOST, WSS_PORT, _real_server_uri)

    for port in PASSTHROUGH_PORTS:
        await asyncio.start_server(
            lambda r, w, p=port: _handle_passthrough(r, w, p),
            PROXY_HOST, port,
        )
        log.info("TCP tunnel %s:%d  →  %s:%d", PROXY_HOST, port, _real_server_ip or SERVER_HOST, port)

    log.info("hosts entry:  127.0.0.1  %s", _real_server_sni)
    await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())
