import asyncio
import base64
import io
import json
import socket
import subprocess
import sys
import tarfile
import tempfile
from http.client import HTTPConnection
from http.cookies import SimpleCookie
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import ProxyHandler, build_opener
from urllib.parse import urlencode

import pytest

from pf_entertainment.remote_live.config import PublishConfig, ssh_args
from pf_entertainment.remote_live.deploy import bundle
from pf_entertainment.remote_live.publisher import RemotePublisher, http_source, start_remote_live
from pf_entertainment.remote_live.server import LatestTable, LiveServer, MAX_FRAME, encode
from pf_entertainment.remote_live.viewer_auth import COOKIE, REMEMBER_SECONDS, ViewerAuth, credentials_for


LIVE = {"connected": True, "room_id": 42, "hand_no": 5, "board": [], "seats": [], "feed": []}


def test_cache_expires_even_when_no_viewer_and_rejects_old_publisher():
    now = [10.0]
    store = LatestTable(15, clock=lambda: now[0])
    first = store.begin()
    store.update(first, {"sequence": 1, "live": LIVE})
    assert store.snapshot()["live"] == LIVE
    with pytest.raises(ValueError, match="out-of-order"):
        store.update(first, {"sequence": 1, "live": LIVE})
    now[0] = 24.9
    assert not store.snapshot()["stale"]
    now[0] = 25
    assert store.snapshot()["stale"] and store.live is None
    second = store.begin()
    with pytest.raises(ValueError, match="superseded"):
        store.update(first, {"sequence": 9, "live": LIVE})
    store.update(second, {"sequence": 1, "live": LIVE})
    store.end(first)
    assert store.snapshot()["live"] == LIVE
    store.end(second)
    assert store.snapshot()["stale"]


@pytest.mark.parametrize("frame", [{}, {"sequence": True, "live": LIVE}, {"sequence": 1, "live": []},
                                     {"sequence": 1, "live": {"seats": [1]}},
                                     {"sequence": 1, "live": {"seats": [{}] * 13}}])
def test_bad_upload_does_not_replace_cache(frame):
    store = LatestTable()
    lease = store.begin()
    store.update(lease, {"sequence": 1, "live": LIVE})
    with pytest.raises(ValueError):
        store.update(lease, frame)
    assert store.snapshot()["live"] == LIVE


@pytest.fixture
def server():
    # Darwin sockaddr_un paths are limited to 104 bytes; pytest paths exceed it.
    with tempfile.TemporaryDirectory(dir="/tmp", prefix="pf-live-") as folder:
        credentials = Path(folder) / "viewer.json"
        credentials.write_text(json.dumps(credentials_for("test viewer password", credentials)))
        auth = ViewerAuth(credentials, Path(folder) / "sessions.db")
        server = LiveServer(Path(folder) / "ingest.sock", auth=auth, port=0)
        server.start()
        yield server
        server.close()


def test_real_ssh_stdin_relay_and_http_only_live_routes(server):
    child = subprocess.Popen([sys.executable, "-B", "-S", "-m", "pf_entertainment.remote_live", "ingest",
                              "--socket", str(server.socket_path)],
                             stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        ready = json.loads(child.stdout.readline())
        assert ready["ready"]
        child.stdin.write(encode({"sequence": 1, "live": LIVE}))
        child.stdin.flush()
        assert json.loads(child.stdout.readline())["sequence"] == 1
        opener = build_opener(ProxyHandler({}))
        opener.addheaders = [("Cookie", COOKIE + "=" + server.http.auth.issue(False))]
        base = f"http://127.0.0.1:{server.http.server_port}"
        with opener.open(base + "/api/live") as response:
            assert response.headers["Cache-Control"] == "no-store"
            assert json.load(response)["live"] == LIVE
        with opener.open(base + "/") as response:
            html = response.read().decode()
            assert "live-table.js" in html and "live-remote.js" in html
            assert "tab-dashboard" not in html and "tab-bot" not in html
        for route in ("/api/records", "/api/hand", "/api/bot/settings", "/static/../remote_live/config.py"):
            with pytest.raises(HTTPError) as exc:
                opener.open(base + route)
            assert exc.value.code == 404
        child.stdin.close()
        child.wait(timeout=3)
        assert child.returncode == 0, child.stderr.read().decode()
        # Allow the Unix reader to observe EOF.
        import time
        for _ in range(100):
            if server.store.snapshot()["stale"]:
                break
            time.sleep(0.01)
        assert server.store.snapshot()["stale"]
    finally:
        if child.poll() is None:
            child.kill()
            child.wait(timeout=3)


def test_probe_does_not_clear_active_snapshot_and_oversize_rejected(server):
    lease = server.store.begin()
    server.store.update(lease, {"sequence": 1, "live": LIVE})
    with socket.socket(socket.AF_UNIX) as probe:
        probe.connect(str(server.socket_path))
    assert server.store.snapshot()["live"] == LIVE
    with socket.socket(socket.AF_UNIX) as sock:
        sock.settimeout(2)
        sock.connect(str(server.socket_path))
        sock.sendall(encode({"protocol": 1, "type": "hello"}))
        with sock.makefile("rb") as reader:
            assert json.loads(reader.readline())["ready"]
            sock.sendall(b"x" * (MAX_FRAME + 1))
            assert "too large" in json.loads(reader.readline())["error"]


@pytest.mark.parametrize("changes", [{"ssh_host": "-oProxyCommand=oops"}, {"remote_dir": "relative"},
                                       {"interval": 0}, {"timeout": 60}, {"interval": "0.7"}, {"timeout": True}])
def test_config_validation(tmp_path, changes):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"ssh_host": "my-vps", **changes}))
    with pytest.raises(ValueError):
        PublishConfig.load(path)


def test_ssh_never_prompts_or_trusts_new_host_automatically():
    command = ssh_args("my-vps")
    for option in ("BatchMode=yes", "PasswordAuthentication=no", "StrictHostKeyChecking=yes",
                   "KbdInteractiveAuthentication=no", "ClearAllForwardings=yes"):
        assert option in command


def test_disabled_or_missing_config_does_not_connect(tmp_path, monkeypatch, caplog):
    async def fail(*args):
        pytest.fail("disabled/missing config attempted SSH")
    monkeypatch.setattr(RemotePublisher, "_connect", fail)

    async def check():
        assert start_remote_live(None, enabled=False) is None
        pub = start_remote_live(lambda: LIVE, config_path=tmp_path / "missing.json")
        await asyncio.wait_for(pub.task, timeout=1)
        await pub.close()
    asyncio.run(check())
    assert "FileNotFoundError" in caplog.text and "SSH 免密登录" in caplog.text


def test_ssh_startup_failure_is_optional_and_does_not_block(tmp_path, monkeypatch, caplog):
    path = tmp_path / "config.json"
    path.write_text('{"ssh_host":"my-vps"}')
    entered = []

    async def fail(self):
        entered.append(True)
        await asyncio.sleep(0.05)
        raise ConnectionError("Permission denied (publickey)")
    monkeypatch.setattr(RemotePublisher, "_connect", fail)

    async def check():
        pub = start_remote_live(lambda: LIVE, config_path=path)
        assert not entered  # start() schedules, never waits for authentication
        await asyncio.wait_for(pub.task, 1)
        assert pub.lock_file is None
    asyncio.run(check())
    assert "Permission denied" in caplog.text and "不影响 bot" in caplog.text


def test_publisher_real_child_recovers_and_sends_latest_only(tmp_path, monkeypatch):
    cfg = tmp_path / "config.json"
    cfg.write_text('{"ssh_host":"test","interval":0.25,"timeout":1}')
    latest = dict(LIVE)
    received = []
    attempts = []
    real_exec = asyncio.create_subprocess_exec
    child = '''import sys,json
print(json.dumps({"ok":True,"ready":True,"protocol":1}),flush=True)
for line in sys.stdin:
 f=json.loads(line)
 print(json.dumps({"ok":True,"sequence":f["sequence"]}),flush=True)
'''

    async def local_exec(*args, **kwargs):
        attempts.append(args)
        return await real_exec(sys.executable, "-u", "-c", child, **kwargs)
    monkeypatch.setattr(asyncio, "create_subprocess_exec", local_exec)
    original = RemotePublisher._publish

    async def record(self):
        await original(self)
        received.append(latest["hand_no"])
    monkeypatch.setattr(RemotePublisher, "_publish", record)

    async def check():
        pub = RemotePublisher(lambda: dict(latest), config_path=cfg).start()
        try:
            async def wait(predicate):
                for _ in range(250):
                    if predicate():
                        return
                    await asyncio.sleep(0.02)
                pytest.fail("publisher did not recover")
            await wait(lambda: bool(received))
            old = pub.process
            old.kill()
            await old.wait()
            latest["hand_no"] = 100
            await wait(lambda: len(attempts) >= 2 and 100 in received)
            assert received[0] == 5 and received[-1] == 100
            active = pub.process
        finally:
            await pub.close()
        assert active.returncode is not None and pub.lock_file is None
    asyncio.run(check())


def test_bundle_is_standalone_and_has_no_local_data():
    with tarfile.open(fileobj=io.BytesIO(bundle())) as archive:
        names = archive.getnames()
    assert "pf_entertainment/static/live-table.js" in names
    assert not any("data/" in name or "pf_intercept" in name or "pokerfate/" in name for name in names)
    result = subprocess.run([sys.executable, "-S", "-m", "pf_entertainment.remote_live", "--help"],
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_sidecar_refuses_nonlocal_sources():
    with pytest.raises(ValueError, match="回环"):
        http_source("https://example.com/api/live")


def test_deploy_self_signed_only_opens_selected_tls_port():
    from pf_entertainment.remote_live.install import nginx_config
    config = nginx_config("192.0.2.5", tls=True, port=8443, mode="self-signed")
    assert "listen 8443 ssl" in config
    assert "listen 80;" not in config and "listen 443 ssl" not in config
    assert "auth_basic" not in config and "limit_except GET" in config
    assert "location = /login" in config and "limit_req zone=pf_viewer_login" in config
    assert "/etc/pokerfate-live/tls/cert.pem" in config


def test_nonfinite_json_cannot_break_browser(server):
    lease = server.store.begin()
    with pytest.raises(ValueError):
        server.store.update(lease, {"sequence": 1, "live": {**LIVE, "pot": float("nan")}})
    assert server.store.snapshot()["stale"]


def test_remembered_login_survives_restart_and_logout_revokes_session(server):
    def request(method, path, fields=None, **headers):
        client = HTTPConnection("127.0.0.1", server.http.server_port, timeout=3)
        if fields is not None:
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        try:
            client.request(method, path, urlencode(fields) if fields is not None else None, headers)
            response = client.getresponse()
            return response.status, dict(response.getheaders()), response.read()
        finally:
            client.close()

    assert request("GET", "/")[1]["Location"] == "/login"
    code, headers, body = request("GET", "/login")
    assert code == 200 and b'autocomplete="current-password"' in body
    assert "WWW-Authenticate" not in headers
    # Browsers use the document's referrer policy to generate Origin for native form POSTs.
    assert headers["Referrer-Policy"] == "same-origin"
    assert request("GET", "/api/live")[0] == 401
    basic = "Basic " + base64.b64encode(b"viewer:test viewer password").decode()
    assert request("GET", "/api/live", Authorization=basic)[0] == 200
    assert request("GET", "/", Authorization=basic)[1]["Location"] == "/login"
    fields = {"username": "viewer", "password": "test viewer password", "remember": "yes"}
    host = "viewer.example:8443"
    for origin in ("null", "https://different.example"):
        code, headers, body = request("POST", "/login", fields, Host=host, Origin=origin)
        assert code == 403 and "Set-Cookie" not in headers
        assert headers["Content-Type"].startswith("text/html") and b'role="alert"' in body
    assert request("POST", "/login", {**fields, "password": "wrong"})[0] == 401
    code, headers, body = request("POST", "/login", fields, Host=host, Origin="https://" + host,
                                  **{"Sec-Fetch-Site": "same-origin"})
    assert code == 303 and headers["Location"] == "/"
    assert headers["Content-Type"].startswith("text/html") and b'href="/"' in body
    cookie = SimpleCookie(headers["Set-Cookie"])[COOKIE]
    assert cookie["max-age"] == str(REMEMBER_SECONDS)
    assert cookie["secure"] and cookie["httponly"] and cookie["path"] == "/" and not cookie["domain"]
    assert cookie["samesite"] == "Lax"
    saved = {"Cookie": f"{COOKIE}={cookie.value}"}
    credentials = server.socket_path.parent / "viewer.json"
    old_record = json.loads(credentials.read_text())
    assert credentials_for(fields["password"], credentials) == old_record
    server.http.auth = ViewerAuth(credentials, server.http.auth.sessions)
    assert request("GET", "/api/live", **saved)[0] == 200
    code, headers, body = request("GET", "/", **saved)
    assert code == 200 and headers["Referrer-Policy"] == "same-origin" and b'action="/logout"' in body
    assert request("POST", "/logout", {}, Host=host, Origin="https://" + host, **saved)[1]["Location"] == "/login"
    assert request("GET", "/api/live", **saved)[0] == 401
    del fields["remember"]
    session = SimpleCookie(request("POST", "/login", fields)[1]["Set-Cookie"])[COOKIE]
    assert not session["max-age"]
    credentials.write_text(json.dumps(credentials_for("rotated test password", credentials)))
    server.http.auth = ViewerAuth(credentials, server.http.auth.sessions)
    assert request("GET", "/api/live", Cookie=f"{COOKIE}={session.value}")[0] == 401


def test_expired_viewer_session_is_rejected(server, monkeypatch):
    from pf_entertainment.remote_live import viewer_auth
    now = 1700000000
    monkeypatch.setattr(viewer_auth.time, "time", lambda: now)
    token = server.http.auth.issue(True)
    assert server.http.auth.valid(token)
    now += REMEMBER_SECONDS
    assert not server.http.auth.valid(token)
