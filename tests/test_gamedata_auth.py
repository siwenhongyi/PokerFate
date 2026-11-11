"""History query credentials and failure handling; all HTTP and pushes are mocked."""

import asyncio
from types import SimpleNamespace

import pytest

import pf_intercept.bot as bot_mod
from pf_intercept.game_api import gamedata
from pf_intercept.headless import session as hs
from pf_intercept.headless.login import LoginResult, ServerEntry
from pokerfate.bot.opponent_model import OpponentModel


@pytest.fixture
def bridge(monkeypatch):
    b = bot_mod.BotBridge()
    b._api = SimpleNamespace(_bot=SimpleNamespace(opponent_model=OpponentModel()))
    b._my_uid = "42"
    b._seat_uids = {0: "42", 2: "1001", 3: "1002"}
    b._uid_to_seat = {"42": 0, "1001": 2, "1002": 3}
    b._seat_names = {2: "Villain", 3: "Other"}
    b._all_seats = [0, 2, 3]
    b.notices = []
    monkeypatch.setattr(b, "_notify", lambda event, **fields: b.notices.append(event))
    monkeypatch.setattr(bot_mod, "load_auth_token", lambda: "legacy-token")
    monkeypatch.setattr(bot_mod, "_sync_fetch", lambda *a, **kw: pytest.fail("unmocked HTTP"))
    # Exercise the real sync fetch/result code without spawning background jobs.
    monkeypatch.setattr(b, "_start_gamedata_fetch_thread", b._do_gamedata_fetch_sync)
    b.set_gamedata_session(authorization="session-token", http_base="https://line.example:8443/",
                           chnl=7, version="session-version")
    return b


def trigger(b, uid=1001, seat=2):
    b._trigger_gamedata_fetch({"seatid": seat, "player": {"uid": uid, "name": "Villain"}})


def success(hands=126):
    return {"code": 0, "data": {"play_times": hands, "pool_entry_rate": 4000,
                                "add_before_flipping_rate": 2000,
                                "show_hand_rate": 2500, "active_rate": 1500}}


@pytest.mark.parametrize("asynchronous", [False, True])
def test_current_session_credentials_seed_history(bridge, monkeypatch, asynchronous):
    calls = []

    def fetch(uid, host, chnl, game_type, token, *, version=None):
        calls.append((uid, host, chnl, token, version))
        return success()

    monkeypatch.setattr(bot_mod, "_sync_fetch", fetch)
    monkeypatch.setattr(bot_mod, "load_auth_token", lambda: pytest.fail("read stale file"))
    if asynchronous:
        asyncio.run(bridge._do_gamedata_fetch(1001, 2, "Villain"))
    else:
        trigger(bridge)
    trigger(bridge)
    assert calls == [(1001, "https://line.example:8443/", 7, "session-token", "session-version")]
    assert bridge._api._bot.opponent_model.get(1001).hands_seen == 126
    assert bridge._fetched_uids == {"1001"}
    assert not bridge.notices


def test_auth_failure_is_not_no_history_and_new_credentials_resume(bridge, monkeypatch):
    calls = []

    def fetch(*args, **kwargs):
        calls.append(args)
        return {"code": -2} if args[4] == "session-token" else success()

    monkeypatch.setattr(bot_mod, "_sync_fetch", fetch)
    trigger(bridge)
    bridge._gamedata_retry_at["1001"] = 0
    trigger(bridge)
    trigger(bridge, 1002, 3)
    # A concurrently completed failed request must not send another warning.
    bridge._apply_gamedata_fetch_result(1002, 3, "Other", {"code": -2}, context=bridge._gamedata_context())
    assert len(calls) == 1
    assert not bridge._fetched_uids
    assert bridge.notices == ["gamedata_auth_failed"]
    assert not bridge._gamedata_no_history_notified
    bridge.set_gamedata_session(authorization="new-token", http_base="https://new-line.example/",
                                chnl=8, version="new-version")
    bridge._on_round_start({"stage": 1})
    assert len(calls) == 3
    assert bridge._fetched_uids == {"1001", "1002"}
    assert calls[-1][1:3] == ("https://new-line.example/", 8)


@pytest.mark.parametrize("bad_response", [None, {"code": 99}, {"code": 0},
                                         {"code": 0, "data": {}},
                                         {"code": 0, "data": {"play_times": "bad"}}])
def test_transient_failure_retries_after_cooldown_on_new_hand(bridge, monkeypatch, bad_response):
    clock = [100.0]
    monkeypatch.setattr(bot_mod.time, "monotonic", lambda: clock[0])
    responses = iter([bad_response, success()])
    calls = []

    def fetch(*args, **kwargs):
        calls.append(args)
        return next(responses)

    monkeypatch.setattr(bot_mod, "_sync_fetch", fetch)
    trigger(bridge)
    assert not bridge._fetched_uids and not bridge._gamedata_inflight
    bridge._on_round_start({"stage": 1})
    assert len(calls) == 1
    clock[0] += 31
    bridge._on_round_start({"stage": 1})
    assert len(calls) == 2
    assert bridge._fetched_uids == {"1001"}
    assert not bridge.notices


def test_request_exception_releases_inflight(bridge, monkeypatch):
    def fail(*args, **kwargs):
        raise TimeoutError("simulated timeout")

    monkeypatch.setattr(bot_mod, "_sync_fetch", fail)
    trigger(bridge)
    assert not bridge._gamedata_inflight and not bridge._fetched_uids
    assert "1001" in bridge._gamedata_retry_at


def test_only_successful_zero_history_sends_history_notice(bridge, monkeypatch):
    monkeypatch.setattr(bot_mod, "_sync_fetch", lambda *a, **kw: success(0))
    trigger(bridge)
    trigger(bridge, 1002, 3)
    assert bridge.notices == ["gamedata_no_history"]
    assert bridge._fetched_uids == {"1001", "1002"}


def test_missing_session_token_never_falls_back_to_legacy(bridge, monkeypatch):
    bridge.set_gamedata_session(authorization="", http_base="https://line.example/", chnl=7, version="v")
    monkeypatch.setattr(bot_mod, "load_auth_token", lambda: pytest.fail("read legacy credentials"))
    trigger(bridge)
    assert not bridge._fetched_uids and not bridge.notices
    assert not bridge._gamedata_inflight


def test_stale_inflight_auth_response_cannot_block_updated_credentials(bridge):
    old = bridge._gamedata_context()
    bridge.set_gamedata_session(authorization="new", http_base="https://line.example/", chnl=7, version="v")
    bridge._apply_gamedata_fetch_result(1001, 2, "Villain", {"code": -2}, context=old)
    assert bridge._gamedata_failed_auth is None
    assert not bridge.notices


def test_inflight_dedup_and_no_retry_for_departed_player(bridge, monkeypatch):
    requests = []
    monkeypatch.setattr(bridge, "_start_gamedata_fetch_thread", lambda *args: requests.append(args))
    trigger(bridge)
    trigger(bridge)
    assert len(requests) == 1
    bridge._finish_gamedata_fetch(1001)
    bridge._gamedata_retry_at["1001"] = 0
    bridge._all_seats.remove(2)
    bridge._on_round_start({"stage": 1})
    assert len(requests) == 1


def test_seat_change_keeps_fetching_but_shutdown_stops_it(bridge, monkeypatch):
    monkeypatch.setattr(bot_mod, "_sync_fetch", lambda *a, **kw: success())
    bridge._set_my_seat(0, "test")
    trigger(bridge)
    assert bridge._fetched_uids == {"1001"}
    bridge.close()
    trigger(bridge, 1002, 3)
    assert bridge._fetched_uids == {"1001"}


def test_legacy_proxy_mode_can_recover_after_token_file_refresh(monkeypatch):
    b = bot_mod.BotBridge()
    token = ["old"]
    monkeypatch.setattr(bot_mod, "load_auth_token", lambda: token[0])
    monkeypatch.setattr(b, "_notify", lambda *a, **kw: None)
    monkeypatch.setattr(b, "_start_gamedata_fetch_thread", b._do_gamedata_fetch_sync)
    monkeypatch.setattr(bot_mod, "_sync_fetch", lambda *a, **kw: {"code": -2} if a[4] == "old" else success())
    trigger(b)
    token[0] = "fresh"
    b._gamedata_retry_at["1001"] = 0
    trigger(b)
    assert b._fetched_uids == {"1001"}
    assert b._pending_seeds[1001]["data"]["play_times"] == 126


def test_http_request_uses_line_url_channel_and_version(monkeypatch):
    requests = []
    monkeypatch.setattr(gamedata, "signed_post_json", lambda *a, **kw: requests.append((a, kw)) or success())
    gamedata._sync_fetch(1001, "https://line.example:8443/", 7, 10010101, "session", version="v2")
    args, kwargs = requests[0]
    assert args[0] == "https://line.example:8443/player/gameData"
    assert kwargs["token"] == "session" and kwargs["chnl"] == 7
    assert kwargs["extra_headers"] == {"Version": "v2"}


def test_headless_binds_selected_line_before_websocket(monkeypatch):
    b = bot_mod.BotBridge()
    login = LoginResult(uid=42, rdkey="test", authorization="session-token", servers=[
        ServerEntry("wss://first.example:9012", "https://first-api.example/"),
        ServerEntry("wss://second.example:9012", "https://second-api.example/"),
    ])
    monkeypatch.setattr(hs, "configure_server_proxy_bypass", lambda *a, **kw: None)

    async def fake_connect(*args, **kwargs):
        context = b._gamedata_context()
        assert context.http_base == "https://second-api.example/"
        assert context.authorization == "session-token"
        assert context.chnl == 7 and context.version == "session-version"
        raise RuntimeError("simulated connection")

    monkeypatch.setattr(hs.websockets, "connect", fake_connect)
    session = hs.HeadlessSession(login, bridge=b, chnl=7, client_version="session-version", auto_rewards=False)
    with pytest.raises(RuntimeError, match="simulated connection"):
        asyncio.run(session.connect(server_index=1))
