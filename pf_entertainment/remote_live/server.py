from __future__ import annotations

import json
import logging
import os
import socket
import socketserver
import threading
import time
import uuid
from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from http.cookies import CookieError, SimpleCookie
from pathlib import Path
from urllib.parse import parse_qs

from .viewer_auth import COOKIE, REMEMBER_SECONDS, ViewerAuth

MAX_FRAME = 128 * 1024
STATIC = Path(__file__).resolve().parents[1] / "static"
log = logging.getLogger("pf_remote_live")


def encode(value: dict) -> bytes:
    return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode() + b"\n"


class LatestTable:
    """A single in-memory snapshot; an active SSH connection owns its lease."""

    def __init__(self, ttl: float = 15, clock=time.monotonic):
        self.ttl, self.clock = ttl, clock
        self.lock = threading.Lock()
        self.lease = ""
        self.sequence = -1
        self.live = None
        self.received = 0.0

    def begin(self) -> str:
        with self.lock:
            self.lease = uuid.uuid4().hex
            self.sequence = -1
            self.live = None
            return self.lease

    def update(self, lease: str, frame: dict) -> None:
        if not isinstance(frame, dict) or type(frame.get("sequence")) is not int:
            raise ValueError("invalid sequence")
        live = frame.get("live")
        if not isinstance(live, dict) or not isinstance(live.get("seats"), list) or len(live["seats"]) > 12:
            raise ValueError("invalid live snapshot")
        if any(not isinstance(seat, dict) for seat in live["seats"]):
            raise ValueError("invalid seat")
        if not isinstance(live.get("board", []), list) or not isinstance(live.get("feed", []), list):
            raise ValueError("invalid cards or action feed")
        # JSON NaN/Infinity are accepted by Python's decoder but not browsers.
        if len(encode(live)) > MAX_FRAME:
            raise ValueError("snapshot too large")
        with self.lock:
            if lease != self.lease:
                raise ValueError("publisher superseded")
            if frame["sequence"] <= self.sequence:
                raise ValueError("out-of-order snapshot")
            self.sequence = frame["sequence"]
            self.live = live
            self.received = self.clock()

    def end(self, lease: str) -> None:
        with self.lock:
            if lease == self.lease:
                self.live = None

    def snapshot(self) -> dict:
        with self.lock:
            age = max(0, self.clock() - self.received)
            if age >= self.ttl:
                self.live = None
            return {"ok": True, "available": True, "live": self.live or {},
                    "stale": self.live is None, "age_sec": round(age, 2) if self.live else None,
                    "expires_in_sec": max(0, self.ttl - age) if self.live else 0,
                    "ttl_sec": self.ttl}


class _IngestHandler(socketserver.StreamRequestHandler):
    def handle(self):
        store = self.server.store
        lease = None
        self.connection.settimeout(store.ttl)
        try:
            hello = self.rfile.readline(1024)
            if not hello:
                return
            if json.loads(hello) != {"protocol": 1, "type": "hello"}:
                raise ValueError("invalid handshake")
            lease = store.begin()
            self.wfile.write(encode({"ok": True, "ready": True, "protocol": 1}))
            self.wfile.flush()
            while True:
                line = self.rfile.readline(MAX_FRAME + 1)
                if not line:
                    break
                if len(line) > MAX_FRAME or not line.endswith(b"\n"):
                    raise ValueError("snapshot too large")
                frame = json.loads(line)
                store.update(lease, frame)
                self.wfile.write(encode({"ok": True, "sequence": frame["sequence"]}))
                self.wfile.flush()
        except (ValueError, OSError) as exc:
            try:
                self.wfile.write(encode({"ok": False, "error": str(exc)}))
                self.wfile.flush()
            except OSError:
                pass
        finally:
            if lease:
                store.end(lease)


class _IngestServer(socketserver.ThreadingUnixStreamServer):
    daemon_threads = True


class _ReadHandler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass  # no per-poll logs, no cards or credentials written to disk

    def _token(self):
        cookies = SimpleCookie()
        try:
            cookies.load(self.headers.get("Cookie", ""))
        except CookieError:
            return ""
        return cookies[COOKIE].value if COOKIE in cookies else ""

    def _login_page(self, status=200, message=""):
        page = (STATIC / "live-login.html").read_bytes()
        if message:
            page = page.replace(b"<!-- login-error -->", f'<p role="alert">{escape(message)}</p>'.encode())
        self._send(status, page, "text/html; charset=utf-8")

    def _redirect(self, path, *, cookie=None):
        label = "进入直播" if path == "/" else "返回登录页"
        page = (f'<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>{label}</title>'
                f'<p><a href="{escape(path)}">{label}</a></p></html>').encode()
        self._send(303, page, "text/html; charset=utf-8", location=path, cookie=cookie)

    def do_POST(self):
        path = self.path.split("?", 1)[0]
        if path not in ("/login", "/logout"):
            return self._send(405)
        origin = self.headers.get("Origin")
        if (origin is not None and origin != "https://" + self.headers.get("Host", "")) or self.headers.get("Sec-Fetch-Site") == "cross-site":
            return self._login_page(403, "无法确认请求来自直播页面。请从本页重新登录。")
        flags = "; Path=/; Secure; HttpOnly; SameSite=Lax"
        if path == "/logout":
            self.server.auth.revoke(self._token())
            return self._redirect("/login", cookie=COOKIE + "=; Max-Age=0" + flags)
        if self.headers.get_content_type() != "application/x-www-form-urlencoded":
            return self._login_page(415, "无法读取登录表单，请重新提交。")
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 < size <= 4096:
                raise ValueError("invalid form length")
            fields = parse_qs(self.rfile.read(size).decode(), max_num_fields=3, strict_parsing=True)
        except (UnicodeError, ValueError):
            return self._login_page(400, "登录表单不完整，请重新提交。")
        username = fields.get("username", [""])[0]
        password = fields.get("password", [""])[0]
        if not self.server.auth.authenticate(username, password):
            return self._login_page(401, "账号或密码不正确")
        remember = fields.get("remember") == ["yes"]
        token = self.server.auth.issue(remember)
        cookie = COOKIE + "=" + token + flags
        if remember:
            cookie += f"; Max-Age={REMEMBER_SECONDS}"
        self._redirect("/", cookie=cookie)

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        files = {"/": ("live.html", "text/html; charset=utf-8"),
                 "/static/live-table.js": ("live-table.js", "text/javascript; charset=utf-8"),
                 "/static/live-remote.js": ("live-remote.js", "text/javascript; charset=utf-8"),
                 "/static/styles.css": ("styles.css", "text/css; charset=utf-8")}
        if path == "/healthz":
            return self._send(200, encode({"ok": True, "protocol": 1}), "application/json")
        if path == "/login":
            if self.server.auth.valid(self._token()):
                return self._redirect("/")
            return self._login_page()
        if path not in files and path != "/api/live":
            return self._send(404)
        if path != "/static/styles.css" and not self.server.auth.valid(self._token()):
            if path == "/":
                return self._redirect("/login")
            if path != "/api/live" or not self.server.auth.api_credentials_valid(self.headers.get("Authorization", "")):
                return self._send(401, encode({"error": "login_required"}), "application/json")
        if path == "/api/live":
            return self._send(200, encode(self.server.store.snapshot()), "application/json")
        name, content_type = files[path]
        self._send(200, (STATIC / name).read_bytes(), content_type)

    def _send(self, status, body=b"", content_type="text/plain", *, location=None, cookie=None):
        self.send_response(status)
        if location:
            self.send_header("Location", location)
        if cookie:
            self.send_header("Set-Cookie", cookie)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        # A native form POST with no-referrer can send Origin: null, even to itself.
        self.send_header("Referrer-Policy", "same-origin")
        self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self' 'unsafe-inline'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'")
        self.end_headers()
        try:
            self.wfile.write(body)
        except OSError:
            pass


class LiveServer:
    def __init__(self, socket_path: Path, *, auth: ViewerAuth, port: int = 9023, ttl: float = 15):
        self.socket_path = socket_path
        self.store = LatestTable(ttl)
        socket_path.parent.mkdir(parents=True, exist_ok=True)
        if socket_path.exists():
            # Only remove an abandoned Unix socket, never another active service.
            with socket.socket(socket.AF_UNIX) as probe:
                try:
                    probe.connect(str(socket_path))
                except ConnectionRefusedError:
                    socket_path.unlink()
                else:
                    raise RuntimeError(f"ingest socket already active: {socket_path}")
        self.ingest = _IngestServer(str(socket_path), _IngestHandler)
        os.chmod(socket_path, 0o600)
        self.ingest.store = self.store
        try:
            self.http = ThreadingHTTPServer(("127.0.0.1", port), _ReadHandler)
        except Exception:
            self.ingest.server_close()
            socket_path.unlink(missing_ok=True)
            raise
        self.http.daemon_threads = True
        self.http.auth = auth
        self.http.store = self.store
        self.stop = threading.Event()
        self.threads = []

    def start(self):
        def expire():
            while not self.stop.wait(1):
                self.store.snapshot()
        for target in (self.ingest.serve_forever, self.http.serve_forever, expire):
            thread = threading.Thread(target=target, daemon=True)
            thread.start()
            self.threads.append(thread)

    def close(self):
        self.stop.set()
        self.http.shutdown()
        self.ingest.shutdown()
        self.http.server_close()
        self.ingest.server_close()
        self.socket_path.unlink(missing_ok=True)
        for thread in self.threads:
            thread.join(timeout=2)


def relay_stdin(socket_path: Path, stdin, stdout) -> None:
    """SSH is the sole upload authentication; ingestion is never an HTTP route."""
    with socket.socket(socket.AF_UNIX) as sock:
        sock.settimeout(10)
        sock.connect(str(socket_path))
        sock.sendall(encode({"protocol": 1, "type": "hello"}))
        with sock.makefile("rb") as reader:
            stdout.write(reader.readline(MAX_FRAME + 1))
            stdout.flush()
            while True:
                line = stdin.readline(MAX_FRAME + 1)
                if not line:
                    return
                if len(line) > MAX_FRAME or not line.endswith(b"\n"):
                    raise ValueError("snapshot too large")
                sock.sendall(line)
                ack = reader.readline(MAX_FRAME + 1)
                if not ack:
                    raise ConnectionError("live service closed ingestion")
                stdout.write(ack)
                stdout.flush()
