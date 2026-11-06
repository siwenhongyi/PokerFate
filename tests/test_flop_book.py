import pytest

from pokerfate.api import ActionEvent, PlayerInfo, PokerFateAPI
from pokerfate.core.game_state import Action, ActionType
from pokerfate.decision.flop_book import FlopBook


def test_flop_book_reads_copied_strategy_matrix():
    book = FlopBook()
    try:
        result = book.lookup("BTNvBB_srp100", "4c4d3c", "As2s", [])
    finally:
        book.close()

    assert result["scenario"] == "BTNvBB_srp100"
    assert result["node_path"] == "r"
    assert result["actor"] == 0
    assert result["flop_representative"] == "4c4d3c"
    assert result["strategy"]["x"] == pytest.approx(0.9984740978)
    assert sum(result["strategy"].values()) == pytest.approx(1.0)


def test_flop_book_walks_checked_prefix_to_ip_node():
    book = FlopBook()
    try:
        result = book.lookup("BTNvBB_srp100", "4c4d3c", "As2s", [("check", 0.0)])
    finally:
        book.close()

    assert result["node_path"] == "r:x"
    assert result["actor"] == 1
    assert set(result["actions"]) == {"x", "b33", "b100"}
    assert result["strategy"]["x"] == pytest.approx(0.5485313191)
    assert result["strategy"]["b33"] == pytest.approx(0.4514686809)


def test_cfr_decision_engine_uses_flop_book(monkeypatch):
    api = PokerFateAPI(
        my_player_id=0,
        big_blind=10_000,
        small_blind=5_000,
        autosave_path=None,
        decision_engine="cfr",
        equity_iterations=5,
    )
    monkeypatch.setattr(api, "_local_shadow_decide", lambda *args, **kwargs: None)
    api.new_hand(
        players=[
            PlayerInfo(1, "BTN", 975_000, "BTN"),
            PlayerInfo(0, "Hero", 975_000, "BB"),
        ],
        dealer_id=1,
    )
    api.deal_hole_cards(["As", "2s"])
    api.notify_action(ActionEvent(1, "raise", 25_000, "preflop"))
    api._action_history.append((0, Action(ActionType.CALL, 0.0), "preflop"))
    api.deal_board(["4c", "4d", "3c"], street="flop", pot=55_000)

    decision = api.request_action(
        "flop",
        pot=55_000,
        current_bet=0,
        to_call=0,
        my_stack=975_000,
        my_current_bet_this_street=0,
    )

    diagnostics = api.last_decision_diagnostics()
    status = api.decision_engine_status()
    assert decision.action == "check"
    assert diagnostics["decision_source"] == "flop_book"
    assert diagnostics["flop_book"]["status"] == "ok"
    assert diagnostics["flop_book"]["scenario"] == "BTNvBB_srp100"
    assert diagnostics["flop_book"]["selected_label"] == "x"
    assert diagnostics["flop_book"]["exploit"]["mode"] == "probability_bias_no_evs"
    assert status["requested"] == "cfr"
    assert status["engine"] == "cfr"
    assert status["mode"] == "flop_book_turn_river"
    assert status["flop_book"] is True
    assert status["realtime_cfr"] is True


def test_cfr_flop_book_miss_falls_back_to_local(monkeypatch):
    api = PokerFateAPI(
        my_player_id=0,
        big_blind=10_000,
        small_blind=5_000,
        autosave_path=None,
        decision_engine="cfr",
        equity_iterations=5,
    )
    monkeypatch.setattr(
        api._bot,
        "decide",
        lambda gs, player_id, is_bb_option=False: Action(ActionType.CHECK, 0.0),
    )
    api.new_hand(
        players=[
            PlayerInfo(1, "BTN", 975_000, "BTN"),
            PlayerInfo(2, "SB", 975_000, "SB"),
            PlayerInfo(0, "Hero", 975_000, "BB"),
        ],
        dealer_id=1,
    )
    api.deal_hole_cards(["As", "2s"])
    api.notify_action(ActionEvent(1, "raise", 25_000, "preflop"))
    api.notify_action(ActionEvent(2, "call", 25_000, "preflop"))
    api._action_history.append((0, Action(ActionType.CALL, 0.0), "preflop"))
    api.deal_board(["4c", "4d", "3c"], street="flop", pot=80_000)

    decision = api.request_action(
        "flop",
        pot=80_000,
        current_bet=0,
        to_call=0,
        my_stack=975_000,
        my_current_bet_this_street=0,
    )

    assert decision.action == "check"
    assert api.last_decision_diagnostics()["decision_source"] == "pokerfate"
    assert api._flop_book_error == "requires_heads_up_active_players"
