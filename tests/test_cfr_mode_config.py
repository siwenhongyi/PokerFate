"""CFR routing and the independently logged flop-book experiment switch."""

import pytest

from pokerfate.api import PlayerInfo, PokerFateAPI
from pokerfate.core.game_state import Action, ActionType


@pytest.mark.parametrize(
    "raw,override,expected",
    [
        (None, None, True),
        ("0", None, False),
        (" false ", None, False),
        ("off", None, False),
        ("1", None, True),
        ("ON", None, True),
        ("1", False, False),
        ("0", True, True),
    ],
)
def test_session_config_logs_effective_book_switch(monkeypatch, raw, override, expected):
    if raw is None:
        monkeypatch.delenv("PF_CFR_FLOP_BOOK_ENABLED", raising=False)
    else:
        monkeypatch.setenv("PF_CFR_FLOP_BOOK_ENABLED", raw)
    # Constructor arguments are authoritative even when the environment differs.
    monkeypatch.setenv("DECISION_ENGINE", "local")
    events = []
    monkeypatch.setattr("pokerfate.api.PokerLogger.raw", lambda self, event: events.append(event))
    api = PokerFateAPI(
        decision_engine="cfr",
        cfr_flop_book_enabled=override,
        enable_showdown_calibration=False,
    )
    config_event = next(event for event in events if event["event"] == "session_config")
    enabled_event = next(event for event in events if event["event"] == "decision_engine_enabled")
    assert config_event["env"].get("PF_CFR_FLOP_BOOK_ENABLED") == raw
    assert config_event["resolved"]["PF_CFR_FLOP_BOOK_ENABLED"] is expected
    assert config_event["resolved"]["DECISION_ENGINE"] == "cfr"
    assert enabled_event["engine"] == "cfr"
    assert enabled_event["flop_book"] is expected
    assert enabled_event["flop_book_requested"] is expected
    assert api.decision_engine_status()["flop_book"] is expected

    events.clear()
    api.set_decision_engine("local")
    api.set_decision_engine("cfr")
    snapshots = [event for event in events if event["event"] == "session_config"]
    assert [event["resolved"]["DECISION_ENGINE"] for event in snapshots] == ["local", "cfr"]
    assert all(event["resolved"]["PF_CFR_FLOP_BOOK_ENABLED"] is expected for event in snapshots)


def test_book_off_uses_local_flop_and_cfr_on_both_later_streets(monkeypatch):
    api = PokerFateAPI(
        my_player_id=0,
        decision_engine="cfr",
        cfr_flop_book_enabled=False,
        enable_showdown_calibration=False,
    )
    calls = []

    def local_decide(gs, player_id, is_bb_option=False):
        calls.append("local")
        return Action(ActionType.CHECK)

    def cfr_decide(ctx):
        calls.append("cfr")
        return Action(ActionType.CHECK)

    monkeypatch.setattr(api._bot, "decide", local_decide)
    monkeypatch.setattr(api._realtime_cfr_engine, "decide", cfr_decide)
    monkeypatch.setattr(api, "_local_shadow_decide", lambda *args, **kwargs: None)
    api.new_hand(
        [PlayerInfo(0, "Hero", 200.0, "BTN"), PlayerInfo(1, "Villain", 200.0, "BB")],
        dealer_id=0,
    )
    api.deal_hole_cards(["As", "Ah"])
    for street, board, expected_source in [
        ("flop", ["Kh", "2c", "3d"], "pokerfate"),
        ("turn", ["9s"], "realtime_cfr"),
        ("river", ["Tc"], "realtime_cfr"),
    ]:
        api.deal_board(board, street=street, pot=20.0)
        api.request_action(street, pot=20.0, current_bet=0, to_call=0, my_stack=200.0)
        assert api.last_decision_diagnostics()["decision_source"] == expected_source
    assert calls == ["local", "cfr", "cfr"]
    assert api._flop_book_engine is None


def test_session_config_distinguishes_g5_all_from_g5(monkeypatch):
    class FakeG5:
        def __init__(self, options):
            pass

        def preflight(self):
            return {}

    events = []
    monkeypatch.setattr("pokerfate.api.G5JsonDecisionEngine", FakeG5)
    monkeypatch.setattr("pokerfate.api.PokerLogger.raw", lambda self, event: events.append(event))
    PokerFateAPI(decision_engine="g5_all", enable_showdown_calibration=False)
    snapshot = next(event for event in events if event["event"] == "session_config")
    assert snapshot["resolved"]["DECISION_ENGINE"] == "g5_all"


def test_bridge_passes_book_switch_to_api(monkeypatch):
    from pf_intercept import config
    from pf_intercept.bot.bridge import BotBridge

    monkeypatch.setattr(config, "DECISION_ENGINE", "cfr")
    monkeypatch.setattr(config, "PF_CFR_FLOP_BOOK_ENABLED", False)
    # The bridge's resolved config must win over a different process environment.
    monkeypatch.setenv("PF_CFR_FLOP_BOOK_ENABLED", "1")
    bridge = BotBridge(max_auto_rebuy=0)
    bridge._my_seat = 0
    bridge._bb = 10000.0
    assert bridge._ensure_api() is True
    status = bridge._api.decision_engine_status()
    assert status["engine"] == "cfr"
    assert status["flop_book"] is False
    assert status["realtime_cfr"] is True


