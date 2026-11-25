import asyncio
import base64
import io
import json
import re
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

from pf_entertainment.remote_live import money as money_frame
from pf_entertainment.remote_live import publisher as publisher_module
from pf_entertainment.remote_live.config import PublishConfig, ssh_args
from pf_entertainment.remote_live.deploy import bundle
from pf_entertainment.remote_live.publisher import RemotePublisher, http_money_source, http_source, start_remote_live
from pf_entertainment.remote_live.server import LatestTable, LiveServer, MAX_FRAME, STATIC, encode
from pf_entertainment.remote_live.viewer_auth import COOKIE, REMEMBER_SECONDS, ViewerAuth, credentials_for


LIVE = {"connected": True, "room_id": 42, "hand_no": 5, "board": [], "seats": []}
FACTS = {"session_delta_chips": -5, "wallet_chips": 9, "base_at": 100.5}


def _hand(n):
    """A hand point as the console's dashboard carries it."""
    return {"ts": 1000.9 + n, "hand_delta_bb": n / 20000, "delta_chips": n, "gameid": f"g{n}",
            "wallet_chips": 7, "reason_text": f"第 {n} 手"}


def test_money_part_is_the_view_figures_and_the_hands_not_yet_delivered():
    dashboard = {**FACTS, "samples": [{"reason_text": "买入"}], "pending_reason": "x", "base_total_chips": 1,
                 "hand_points": [_hand(12345), {"ts": 2000.2, "hand_delta_bb": None, "delta_chips": -5}]}
    first = money_frame.next_part(dashboard, 0, None)
    assert set(first["facts"]) == set(money_frame.FACTS)
    assert {key: first["facts"][key] for key in FACTS} == FACTS and first["facts"]["table_chips"] is None
    assert (first["from"], first["points"]) == (0, [[13345, 0.61725, 12345], [2000, None, -5]])
    facts = first["facts"]
    grown = {**dashboard, "hand_points": dashboard["hand_points"] + [_hand(3)]}
    for board, sent, expected in [
        (dashboard, 2, None),                                               # nothing new
        ({**dashboard, "wallet_chips": 8}, 2, (2, 0)),                      # a figure changed
        (grown, 2, (2, 1)),                                                 # one more hand
        ({**dashboard, "hand_points": []}, 2, (0, 0)),                      # fewer hands: another session
        ({**grown, "base_at": 200.0}, 2, (0, 3)),                           # another start: another session
        ({**dashboard, "hand_points": [_hand(1)] * (money_frame.CHUNK + 5)}, 2, (2, money_frame.CHUNK)),
        ({**dashboard, "hand_points": [_hand(1)] * (money_frame.MAX_POINTS + 5)}, money_frame.MAX_POINTS - 1,
         (money_frame.MAX_POINTS - 1, 1)),
        (None, 0, None), ({}, 0, None),                                     # the bot has no figures yet
    ]:
        part = money_frame.next_part(board, sent, facts)
        assert (part and (part["from"], len(part["points"]))) == expected
    assert money_frame.checked(json.loads(encode(first))) == (first["facts"], 0, first["points"])


def test_money_arrives_as_tails_and_leaves_with_the_table():
    now = [10.0]
    store = LatestTable(15, clock=lambda: now[0])
    lease = store.begin()
    store.update(lease, {"sequence": 1, "live": LIVE})
    assert store.money() == {"ok": True, "stale": False, "money": None}        # a bot that sends the table only
    store.update(lease, {"sequence": 2, "live": LIVE, "money": {"facts": FACTS, "from": 0, "points": [[1, 0.5, 10]]}})
    store.update(lease, {"sequence": 3, "live": LIVE,
                         "money": {"facts": {**FACTS, "wallet_chips": 8}, "from": 1, "points": [[2, None, 5], [3, -1.0, 0]]}})
    whole = store.money()["money"]
    assert whole["facts"]["wallet_chips"] == 8 and whole["from"] == 0
    assert whole["points"] == [[1, 0.5, 10], [2, None, 5], [3, -1.0, 0]]
    # a reader holding two hands of this list gets the third; any other position gets all of it
    assert store.money(whole["epoch"], 2)["money"]["points"] == [[3, -1.0, 0]]
    assert store.money(whole["epoch"], 3)["money"]["points"] == []
    for epoch, held in [("other", 2), (whole["epoch"], 4)]:
        assert (store.money(epoch, held)["money"]["from"], len(store.money(epoch, held)["money"]["points"])) == (0, 3)
    # a tail from 0 replaces the hands and renames the list
    store.update(lease, {"sequence": 4, "live": LIVE, "money": {"facts": FACTS, "from": 0, "points": [[9, 1.0, 1]]}})
    again = store.money(whole["epoch"], 3)["money"]
    assert again["epoch"] != whole["epoch"] and (again["from"], again["points"]) == (0, [[9, 1.0, 1]])
    now[0] = 25
    assert store.money() == {"ok": True, "stale": True, "money": None}
    lease = store.begin()
    store.update(lease, {"sequence": 1, "live": LIVE, "money": {"facts": FACTS, "from": 0, "points": []}})
    assert store.money()["money"]["epoch"] != again["epoch"]
    store.end(lease)
    assert store.money()["money"] is None and store.money()["stale"]


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
                                     {"sequence": 1, "live": {"seats": [{}] * 13}},
                                     *({"sequence": 2, "live": {**LIVE, "hand_no": 6}, "money": money} for money in (
                                         [], {"facts": FACTS, "from": 0},
                                         {"facts": {**FACTS, "samples": []}, "from": 0, "points": []},
                                         {"facts": {**FACTS, "wallet_chips": "9"}, "from": 0, "points": []},
                                         {"facts": {**FACTS, "base_at": float("inf")}, "from": 0, "points": []},
                                         {"facts": FACTS, "from": 0, "points": [[1, 0.5]]},
                                         {"facts": FACTS, "from": 0, "points": [[1, "0.5", 10]]},
                                         {"facts": FACTS, "from": 0, "points": [[1, 0.5, 10]] * (money_frame.CHUNK + 1)},
                                         {"facts": FACTS, "from": 5, "points": []}))])
def test_bad_upload_does_not_replace_cache(frame):
    store = LatestTable()
    lease = store.begin()
    store.update(lease, {"sequence": 1, "live": LIVE, "money": {"facts": FACTS, "from": 0, "points": [[1, 0.5, 10]]}})
    with pytest.raises(ValueError):
        store.update(lease, frame)
    assert store.snapshot()["live"] == LIVE
    assert store.money()["money"]["points"] == [[1, 0.5, 10]]


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
        child.stdin.write(encode({"sequence": 1, "live": LIVE,
                                  "money": {"facts": FACTS, "from": 0, "points": [[1, 0.5, 10], [2, -1.0, 5]]}}))
        child.stdin.flush()
        assert json.loads(child.stdout.readline())["sequence"] == 1
        opener = build_opener(ProxyHandler({}))
        opener.addheaders = [("Cookie", COOKIE + "=" + server.http.auth.issue(False))]
        base = f"http://127.0.0.1:{server.http.server_port}"
        with opener.open(base + "/api/live") as response:
            assert response.headers["Cache-Control"] == "no-store"
            assert json.load(response)["live"] == LIVE
        with opener.open(base + "/api/money") as response:
            assert response.headers["Cache-Control"] == "no-store"
            money = json.load(response)["money"]
            assert money["facts"] == FACTS and len(money["points"]) == 2
        with opener.open(base + f"/api/money?from=1&epoch={money['epoch']}") as response:
            assert json.load(response)["money"]["points"] == [[2, -1.0, 5]]
        with opener.open(base + "/api/money?from=x&epoch=") as response:
            assert len(json.load(response)["money"]["points"]) == 2
        with opener.open(base + "/") as response:
            html = response.read().decode()
            assert "tab-dashboard" not in html and "tab-bot" not in html
        # every file the page asks for is in the deployed bundle and served; the console's are not
        with tarfile.open(fileobj=io.BytesIO(bundle())) as archive:
            bundled = archive.getnames()
        asked = re.findall(r'(?:src|href)="(/static/[^"]+)"', html)
        assert len(asked) == 5
        for path in asked:
            assert "pf_entertainment" + path in bundled
            with opener.open(base + path) as response:
                assert response.read() == (STATIC / path.rsplit("/", 1)[1]).read_bytes()
        # the hands stay on the local console: no list, no detail, no log, no console page
        for route in ("/api/records", "/api/hands", "/api/hand?id=1", "/api/status", "/api/bot/settings",
                      "/static/app.js", "/static/index.html", "/static/../remote_live/config.py"):
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


def test_publisher_delivers_money_as_a_tail_and_from_the_start_on_a_new_connection(tmp_path, monkeypatch):
    cfg = tmp_path / "config.json"
    cfg.write_text('{"ssh_host":"test","interval":0.25,"timeout":1}')
    seen = tmp_path / "frames.jsonl"
    child = f'''import sys,json
print(json.dumps({{"ok":True,"ready":True,"protocol":1}}),flush=True)
for line in sys.stdin:
 f=json.loads(line)
 open({str(seen)!r},"a").write(json.dumps(f.get("money"))+"\\n")
 print(json.dumps({{"ok":True,"sequence":f["sequence"]}}),flush=True)
'''
    real_exec = asyncio.create_subprocess_exec

    async def local_exec(*args, **kwargs):
        return await real_exec(sys.executable, "-u", "-c", child, **kwargs)
    monkeypatch.setattr(asyncio, "create_subprocess_exec", local_exec)
    monkeypatch.setattr(publisher_module, "MONEY_EVERY", 0)
    dashboard = {**FACTS, "hand_points": [_hand(1), _hand(2)]}

    def money():
        if dashboard.get("broken"):
            raise RuntimeError("no figures")
        return dashboard

    def parts():
        return [part for part in map(json.loads, seen.read_text().splitlines()) if part] if seen.exists() else []

    async def check():
        pub = RemotePublisher(lambda: dict(LIVE), money_source=money, config_path=cfg).start()
        try:
            async def wait(predicate):
                for _ in range(250):
                    if predicate():
                        return
                    await asyncio.sleep(0.02)
                pytest.fail("publisher did not deliver")
            await wait(lambda: len(seen.read_text().splitlines()) >= 3 if seen.exists() else False)
            assert [(part["from"], len(part["points"])) for part in parts()] == [(0, 2)]     # once, not with every frame
            dashboard["hand_points"] = dashboard["hand_points"] + [_hand(3)]
            await wait(lambda: len(parts()) == 2)
            assert (parts()[1]["from"], parts()[1]["points"]) == (2, money_frame.points([_hand(3)]))
            # figures that cannot be read hold nothing back: the table keeps going up
            dashboard["broken"] = True
            frames = len(seen.read_text().splitlines())
            await wait(lambda: len(seen.read_text().splitlines()) >= frames + 2)
            del dashboard["broken"]
            pub.process.kill()
            await pub.process.wait()
            await wait(lambda: len(parts()) == 3)
            assert (parts()[2]["from"], len(parts()[2]["points"])) == (0, 3)
        finally:
            await pub.close()
    asyncio.run(check())


def test_bundle_is_standalone_and_has_no_local_data():
    with tarfile.open(fileobj=io.BytesIO(bundle())) as archive:
        names = archive.getnames()
    assert "pf_entertainment/static/live-table.js" in names
    assert not any("data/" in name or "pf_intercept" in name or "pokerfate/" in name for name in names)
    assert not any(part in name for name in names for part in ("app.js", "index.html", "hand_preview", "web.py"))
    result = subprocess.run([sys.executable, "-S", "-m", "pf_entertainment.remote_live", "--help"],
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("source", [http_source, http_money_source])
def test_sidecar_refuses_nonlocal_sources(source):
    with pytest.raises(ValueError, match="回环"):
        source("https://example.com/api/live")


def test_sidecar_reads_the_table_and_the_money_from_the_console():
    from pf_entertainment.live_table import LiveTableObserver, start_live_web

    async def check():
        web = await start_live_web(LiveTableObserver(my_uid=1), host="127.0.0.1", port=0,
                                   bankroll_source=lambda: {**FACTS, "hand_points": [_hand(1)]})
        try:
            url = f"http://127.0.0.1:{web.port}/api/live"
            assert (await http_source(url)())["connected"] is False
            assert (await http_money_source(url)())["hand_points"] == [_hand(1)]
        finally:
            web._server.close()
            await web._server.wait_closed()
    asyncio.run(check())


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
    assert request("GET", "/api/live")[0] == 401 and request("GET", "/api/money")[0] == 401
    basic = "Basic " + base64.b64encode(b"viewer:test viewer password").decode()
    assert request("GET", "/api/live", Authorization=basic)[0] == 200
    # a script's Basic credentials open the table only; the money and the page need the sign-in
    assert request("GET", "/api/money", Authorization=basic)[0] == 401
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
    assert request("GET", "/api/live", **saved)[0] == 200 and request("GET", "/api/money", **saved)[0] == 200
    code, headers, body = request("GET", "/", **saved)
    assert code == 200 and headers["Referrer-Policy"] == "same-origin" and b'action="/logout"' in body
    assert request("POST", "/logout", {}, Host=host, Origin="https://" + host, **saved)[1]["Location"] == "/login"
    assert request("GET", "/api/live", **saved)[0] == 401 and request("GET", "/api/money", **saved)[0] == 401
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
