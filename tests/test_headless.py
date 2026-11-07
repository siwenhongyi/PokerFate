"""Headless client: login payload/signing, response parsing, WSS session."""

from __future__ import annotations

import asyncio
import hashlib
import json

import pytest

from pf_intercept.headless import login as hl
from pf_intercept.headless import session as hs
from pf_intercept.headless.credentials import (
    LOGIN_TYPE_EMAIL,
    LOGIN_TYPE_GUEST,
    Account,
    AccountError,
    load_account,
)
from pf_intercept.wire import codec
from pf_intercept.wire.framing import FrameBuffer, encode_frame


# ── credentials ───────────────────────────────────────────────────────────

def test_load_email_account_persists_generated_device_id(tmp_path):
    path = tmp_path / "acc.json"
    path.write_text(json.dumps({"type": "email", "email": "a@b.c", "password": "pw"}))
    acc = load_account(path)
    assert acc.login_type == LOGIN_TYPE_EMAIL
    assert acc.token == "a@b.c" and acc.secret == "pw"
    assert len(acc.device_id) == 32
    assert json.loads(path.read_text())["device_id"] == acc.device_id
    assert "pw" not in acc.redacted()


def test_load_guest_account_uses_device_id_as_token(tmp_path):
    path = tmp_path / "acc.json"
    path.write_text(json.dumps({"type": "guest", "device_id": "dev-1", "lang": "zh_CN", "chnl": 5}))
    acc = load_account(path)
    assert acc.login_type == LOGIN_TYPE_GUEST
    assert acc.token == "dev-1" and acc.lang == "zh_CN" and acc.chnl == 5


def test_load_account_rejects_bad_type(tmp_path):
    path = tmp_path / "acc.json"
    path.write_text(json.dumps({"type": "steam"}))
    with pytest.raises(AccountError):
        load_account(path)


# ── login payload ─────────────────────────────────────────────────────────

def test_email_payload_matches_lua_fields():
    acc = Account(LOGIN_TYPE_EMAIL, "a@b.c", "secret", "dev-1", os="android", lang="en", chnl=5)
    body = hl.build_login_payload(acc)
    assert body["type"] == 2 and body["token"] == "a@b.c" and body["verify"] == "secret"
    assert body["imei"] == "dev-1" and body["os"] == "android"
    risk = body["yidun_risk_check"]
    assert risk["token"] == "" and risk["sceneData"]["operationType"] == "log"


def test_guest_verify_is_md5_of_os_imei_and_salt():
    acc = Account(LOGIN_TYPE_GUEST, "dev-1", "", "dev-1")
    body = hl.build_login_payload(acc)
    expect = hashlib.md5(("androiddev-1" + hl._CHECK_SALT).encode()).hexdigest()
    assert body["verify"] == expect


def test_http_login_posts_signed_body_and_saves_token(monkeypatch, tmp_path):
    captured = {}

    def fake_post(url, body, headers, timeout):
        captured["url"] = url
        captured["body"] = body
        captured["headers"] = headers
        return {
            "code": 0, "uid": 42, "rdkey": "rk", "authorization": "auth-token",
            "login_ip": "1.2.3.4",
            "server": {"server": [{"server_host": "wss://10.0.0.1:9013", "http_host": "http://10.0.0.1:8888/"}]},
        }

    monkeypatch.setattr(hl, "_post_json", fake_post)
    monkeypatch.setattr(hl, "_TOKEN_FILE", tmp_path / "auth_token.txt")
    acc = Account(LOGIN_TYPE_EMAIL, "a@b.c", "pw", "dev-1", chnl=7)

    res = hl.http_login(acc, hosts=("https://h1.example/",))

    assert captured["url"] == "https://h1.example/login"
    body = captured["body"]
    assert body["chnl"] == 7 and len(body["random"]) == 6
    assert body["sign"] == hl.add_signed_args.__globals__["sign_request"](body["random"], body["ts"])
    assert captured["headers"]["Version"] == hl.config.GAME_HTTP_VERSION
    assert captured["headers"]["Authorization"] == ""
    assert res.uid == 42 and res.rdkey == "rk" and res.login_ip == "1.2.3.4"
    assert res.servers[0].server_host == "wss://10.0.0.1:9013"
    assert (tmp_path / "auth_token.txt").read_text() == "auth-token"


def test_http_login_falls_through_hosts_then_raises(monkeypatch):
    calls = []

    def fake_post(url, body, headers, timeout):
        calls.append(url)
        raise OSError("down")

    monkeypatch.setattr(hl, "_post_json", fake_post)
    acc = Account(LOGIN_TYPE_GUEST, "d", "", "d")
    with pytest.raises(hl.LoginError):
        hl.http_login(acc, hosts=("https://a/", "https://b/"), save_token=False)
    assert calls == ["https://a/login", "https://b/login"]


def test_parse_login_response_rejects_error_code():
    with pytest.raises(hl.LoginError) as ei:
        hl.parse_login_response({"code": -5, "reason": "key"})
    assert ei.value.code == -5


def test_parse_login_response_accepts_risk_warning_minus_6():
    res = hl.parse_login_response({
        "code": -6, "uid": 1, "rdkey": "k", "authorization": "a",
        "server": {"server": [{"server_host": "wss://1.1.1.1:9013"}]},
    })
    assert res.code == -6 and res.uid == 1


# ── WSS session ───────────────────────────────────────────────────────────

class _FakeWS:
    """Minimal async websocket double: records sends, replays scripted frames."""

    def __init__(self):
        self.sent: list[tuple[str, int, dict]] = []
        self._incoming: asyncio.Queue = asyncio.Queue()
        self.closed = False

    answer_heartbeats = True

    async def send(self, data: bytes):
        buf = FrameBuffer()
        for f in buf.feed(data):
            self.sent.append((f.type_name, f.room_id, codec.decode(f.type_name, f.pb_body) or {}))
            if f.type_name == "pb.HeartBeatREQ" and self.answer_heartbeats:
                self.push("pb.HeartBeatRSP", {"server_timestamp": 1})

    def push(self, type_name: str, fields: dict, room_id: int = 0):
        self._incoming.put_nowait(encode_frame(type_name, room_id, codec.encode(type_name, fields)))

    def __aiter__(self):
        return self

    async def __anext__(self):
        item = await self._incoming.get()
        if item is None:
            raise StopAsyncIteration
        return item

    async def close(self, code=1000, reason=""):
        self.closed = True
        self._incoming.put_nowait(None)

    def sent_types(self):
        return [t for t, _, _ in self.sent]


class _RecordingBridge:
    def __init__(self):
        self.handled: list[tuple[str, dict]] = []
        self.room_ids: list[int] = []
        self.injects: dict[str, list] = {}

    def note_seen_room_id(self, rid):
        self.room_ids.append(rid)

    def room_id_for_c2s(self, frame_room_id):
        return frame_room_id or (self.room_ids[-1] if self.room_ids else 0)

    def handle(self, type_name, msg):
        self.handled.append((type_name, msg))
        return self.injects.get(type_name)

    def injection_guard_for(self, inject):
        return None

    def injection_guard_is_current(self, guard):
        return True

    def notify_inject_failed(self, type_name):
        pass


def _login_result():
    return hl.LoginResult(uid=42, rdkey="rk", authorization="a", login_ip="9.9.9.9",
                          servers=[hl.ServerEntry("wss://10.0.0.1:9013", "")])


async def _connect_with_fake(monkeypatch, bridge, login_code=0):
    ws = _FakeWS()

    async def fake_connect(uri, **kwargs):
        assert uri == "wss://10.0.0.1:9013"
        return ws

    monkeypatch.setattr(hs.websockets, "connect", fake_connect)
    monkeypatch.setattr(hs, "HEARTBEAT_INTERVAL_SEC", 0.05)
    sess = hs.HeadlessSession(_login_result(), bridge=bridge, chnl=5, client_version="1.7.0")
    ws.push("pb.UserLoginRSP", {"code": login_code, "server_timestamp": 1})
    await sess.connect()
    return sess, ws


def test_session_login_handshake_and_bootstrap(monkeypatch):
    async def run():
        bridge = _RecordingBridge()
        sess, ws = await _connect_with_fake(monkeypatch, bridge)
        try:
            assert sess.logged_in
            login = ws.sent[0]
            assert login[0] == "pb.UserLoginREQ" and login[1] == 0
            assert login[2] == {"uid": "42", "key": "rk", "ver": "1.7.0", "chnl": 5}
            assert ws.sent_types()[1:3] == ["pb.SelfUserInfoREQ", "pb.UserValueREQ"]
            # UserLoginRSP is in WATCH_S2C, so the bridge saw it too.
            assert bridge.handled[0][0] == "pb.UserLoginRSP"
        finally:
            await sess.close()
    asyncio.run(run())


def test_session_rejects_bad_login_code(monkeypatch):
    async def run():
        with pytest.raises(hs.SessionClosed):
            await _connect_with_fake(monkeypatch, _RecordingBridge(), login_code=1001)
    asyncio.run(run())


def test_session_feeds_bridge_and_sends_injects_with_room_id(monkeypatch):
    async def run():
        bridge = _RecordingBridge()
        bridge.injects["pb.ActionNotifyBRC"] = ("pb.ActionREQ", {"action_type": 3, "chips": 50}, 0.0)
        sess, ws = await _connect_with_fake(monkeypatch, bridge)
        try:
            ws.push("pb.ActionNotifyBRC", {"seatid": 0, "call_need_chips": 50}, room_id=777)
            for _ in range(50):
                await asyncio.sleep(0.01)
                if any(t == "pb.ActionREQ" for t, _, _ in ws.sent):
                    break
            action = [s for s in ws.sent if s[0] == "pb.ActionREQ"]
            assert action and action[0][1] == 777
            assert action[0][2]["action_type"] == 3
            assert sess.stats.injects_sent == 1
            # non-watched frames (e.g. chat) never reach the bridge
            ws.push("pb.HeartBeatRSP", {"server_timestamp": 2})
            await asyncio.sleep(0.02)
            assert all(t != "pb.HeartBeatRSP" for t, _ in bridge.handled)
        finally:
            await sess.close()
    asyncio.run(run())


def test_session_heartbeat_and_quick_start(monkeypatch):
    async def run():
        bridge = _RecordingBridge()
        sess, ws = await _connect_with_fake(monkeypatch, bridge)
        try:
            await asyncio.sleep(0.2)
            assert ws.sent_types().count("pb.HeartBeatREQ") >= 2
            assert await sess.quick_start(big_blind=1000, buyin_bb=100)
            qs = [s for s in ws.sent if s[0] == "pb.QuickStartREQ"][0]
            assert qs[1] == 0
            assert qs[2]["boot"] == "1000" and qs[2]["byin_chips"] == "100000"
            assert qs[2]["game_type"] == hs.LOBBY_HOLDEM_GAME_TYPE and qs[2]["ip"] == "9.9.9.9"
        finally:
            await sess.close()
    asyncio.run(run())


def test_session_closes_after_missed_heartbeats(monkeypatch):
    async def run():
        bridge = _RecordingBridge()
        sess, ws = await _connect_with_fake(monkeypatch, bridge)
        ws.answer_heartbeats = False
        await asyncio.wait_for(sess.wait_closed(), timeout=2.0)
        assert ws.closed
        assert sess.stats.heartbeats_missed == 1
    asyncio.run(run())
