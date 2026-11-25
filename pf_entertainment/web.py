from __future__ import annotations

import asyncio
import json
import socket
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

from pf_entertainment.hand_preview import hand_detail_payload, hand_list_payload
from pf_entertainment.logger import get_logger


# Front-end is served as plain static files (see pf_entertainment/static/).
_STATIC_DIR = Path(__file__).resolve().parent / "static"
_STATIC_MIME = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".map": "application/json; charset=utf-8",
    ".svg": "image/svg+xml",
    ".ico": "image/x-icon",
}


def web_access_urls(host: str | None, port: int | None) -> list[str]:
    """Addresses to display for a local Web listener, shared by both entry points."""
    if host is None or port is None:
        return []
    hosts = [*_local_lan_ipv4_addresses(), "127.0.0.1"] if host in ("0.0.0.0", "::", "") else [host]
    return [f"http://{'[' + h + ']' if ':' in h else h}:{port}" for h in dict.fromkeys(hosts)]


def _local_lan_ipv4_addresses() -> list[str]:
    ips: set[str] = set()
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("223.5.5.5", 80))
            ips.add(sock.getsockname()[0])
    except OSError:
        pass
    try:
        ips.update(socket.gethostbyname_ex(socket.gethostname())[2])
    except OSError:
        pass
    return sorted((ip for ip in ips if _is_lan_ipv4(ip)), key=_ipv4_display_sort_key)


def _ipv4_display_sort_key(ip: str) -> tuple[int, str]:
    if ip.startswith("192.168."):
        group = 0
    elif ip.startswith("10."):
        group = 1
    else:
        group = 2
    return (group, ip)


def _is_lan_ipv4(ip: str) -> bool:
    try:
        parts = [int(part) for part in ip.split(".")]
    except ValueError:
        return False
    if len(parts) != 4 or any(part < 0 or part > 255 for part in parts):
        return False
    return (
        parts[0] == 10
        or (parts[0] == 192 and parts[1] == 168)
        or (parts[0] == 172 and 16 <= parts[1] <= 31)
    )


@dataclass
class _HttpRequest:
    method: str
    target: str
    path: str
    query: dict[str, list[str]]
    headers: dict[str, str]
    body: bytes


class EntertainmentWebServer:
    def __init__(
        self,
        *,
        runtime: Any,
        host: str = "127.0.0.1",
        port: int = 9022,
        live_source: Any = None,
    ) -> None:
        self.runtime = runtime
        self.host = host
        self.port = port
        # Optional callable returning the live-table snapshot dict for /api/live
        # (set in headless play so the web can draw the table without the client).
        self.live_source = live_source
        self.log = get_logger()
        self._server: asyncio.AbstractServer | None = None

    async def start(self) -> None:
        if self._server is not None:
            return
        self._server = await asyncio.start_server(
            self._handle_client,
            self.host,
            self.port,
        )
        if self.port == 0 and self._server.sockets:
            self.port = int(self._server.sockets[0].getsockname()[1])
        self.log.info("[牌局 Web] Web 已启动 http://%s:%d", self.host, self.port)
        self.log.info("[牌局 Web] Web 可访问地址: %s", ", ".join(web_access_urls(self.host, self.port)))

    async def _handle_client(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        try:
            request = await self._read_request(reader)
            status, headers, body = await self._route(request)
        except (asyncio.IncompleteReadError, ConnectionError):
            # Browser/phone dropped the connection mid-request (page switched or
            # refreshed while polling) — normal, nothing to answer.
            writer.close()
            return
        except Exception as exc:
            self.log.exception("[牌局 Web] Web 请求失败")
            status, headers, body = self._json_response(
                {"ok": False, "error": str(exc)},
                status=500,
            )
        try:
            writer.write(self._build_response(status, headers, body))
            await writer.drain()
        except (ConnectionError, OSError):
            pass  # peer went away before we finished writing (BrokenPipe etc.)
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass

    async def _read_request(self, reader: asyncio.StreamReader) -> _HttpRequest:
        header_bytes = await reader.readuntil(b"\r\n\r\n")
        header_text = header_bytes.decode("iso-8859-1")
        lines = header_text.split("\r\n")
        request_line = lines[0].split()
        if len(request_line) < 2:
            raise ValueError("bad request line")
        method = request_line[0].upper()
        target = request_line[1]
        headers: dict[str, str] = {}
        for line in lines[1:]:
            if not line or ":" not in line:
                continue
            key, value = line.split(":", 1)
            headers[key.strip().lower()] = value.strip()

        content_length = int(headers.get("content-length") or 0)
        body = await reader.readexactly(content_length) if content_length > 0 else b""
        parsed = urlsplit(target)
        return _HttpRequest(
            method=method,
            target=target,
            path=parsed.path or "/",
            query=parse_qs(parsed.query),
            headers=headers,
            body=body,
        )

    async def _route(self, request: _HttpRequest) -> tuple[int, dict[str, str], bytes]:
        if request.method == "GET" and request.path == "/":
            return self._serve_static("index.html")
        if request.method == "GET" and request.path.startswith("/static/"):
            return self._serve_static(request.path[len("/static/"):])
        if request.method == "GET" and request.path == "/api/status":
            return self._json_response(
                {
                    "ok": True,
                    "runtime": self.runtime.status_data(),
                }
            )
        if request.method == "GET" and request.path == "/api/live":
            live = {}
            if callable(self.live_source):
                try:
                    live = self.live_source() or {}
                except Exception as exc:
                    return self._json_response({"ok": False, "error": str(exc)})
            return self._json_response({"ok": True, "live": live, "available": bool(self.live_source)})
        if request.method == "GET" and request.path == "/api/hands":
            return self._json_response(
                {
                    "ok": True,
                    **hand_list_payload(
                        hand_no=self._str_query(request, "hand_no", ""),
                        board=self._str_query(request, "board", ""),
                        position=self._str_query(request, "position", "all"),
                        vpip=self._str_query(request, "vpip", "all"),
                        result=self._str_query(request, "result", "all"),
                        bb_k=self._str_query(request, "bb_k", "all"),
                        page=self._int_query(request, "page", 1),
                        page_size=self._int_query(request, "page_size", 30),
                    ),
                }
            )
        if request.method == "GET" and request.path == "/api/hand":
            hand_id = self._int_query(request, "id", 0)
            try:
                return self._json_response({"ok": True, **hand_detail_payload(hand_id)})
            except KeyError as exc:
                return self._json_response({"ok": False, "error": str(exc)}, status=404)
        return self._json_response({"ok": False, "error": "not found"}, status=404)

    def _int_query(self, request: _HttpRequest, name: str, default: int) -> int:
        values = request.query.get(name)
        if not values:
            return default
        try:
            return int(values[0])
        except ValueError:
            return default

    def _str_query(self, request: _HttpRequest, name: str, default: str = "") -> str:
        values = request.query.get(name)
        if not values:
            return default
        return str(values[0])

    def _serve_static(self, name: str) -> tuple[int, dict[str, str], bytes]:
        # Only a bare filename under static/ is allowed (no traversal).
        safe = Path(name).name
        path = _STATIC_DIR / safe
        if not safe or not path.is_file():
            return self._json_response({"ok": False, "error": "not found"}, status=404)
        ctype = _STATIC_MIME.get(path.suffix.lower(), "application/octet-stream")
        # Local tool, tiny files: never cache, so UI edits always show on reload.
        return (200, {"Content-Type": ctype, "Cache-Control": "no-store"}, path.read_bytes())

    def _json_response(
        self,
        payload: dict,
        *,
        status: int = 200,
    ) -> tuple[int, dict[str, str], bytes]:
        return (
            status,
            {
                "Content-Type": "application/json; charset=utf-8",
                "Cache-Control": "no-store",
            },
            json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        )

    def _build_response(
        self,
        status: int,
        headers: dict[str, str],
        body: bytes,
    ) -> bytes:
        reason = {
            200: "OK",
            400: "Bad Request",
            404: "Not Found",
            409: "Conflict",
            500: "Internal Server Error",
        }.get(status, "OK")
        base_headers = {
            "Content-Length": str(len(body)),
            "Connection": "close",
        }
        base_headers.update(headers)
        header_lines = [f"HTTP/1.1 {status} {reason}"]
        header_lines.extend(f"{key}: {value}" for key, value in base_headers.items())
        return ("\r\n".join(header_lines) + "\r\n\r\n").encode("utf-8") + body


# INDEX_HTML extracted to pf_entertainment/static/ (served via _serve_static)
