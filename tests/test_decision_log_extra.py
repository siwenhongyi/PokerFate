"""Structured log carries engine diagnostics and the tracker layer trace."""

import json

from pokerfate.api import ActionEvent, PlayerInfo, PokerFateAPI


def _api(log_path):
    api = PokerFateAPI(
        my_player_id=0, big_blind=2.0, small_blind=1.0, equity_iterations=50,
        verbose=False, log_file=str(log_path), decision_seed=3,
    )
    api.new_hand(
        players=[
            PlayerInfo(0, "Hero", 200.0, "BB"),
            PlayerInfo(1, "Vil", 200.0, "BTN"),
            PlayerInfo(2, "Sb", 200.0, "SB"),
        ],
        dealer_id=1,
    )
    return api


def _rows(log_path):
    return [json.loads(l) for l in log_path.read_text(encoding="utf-8").splitlines() if l.strip()]


def test_decision_record_has_source_purpose_and_calibration(tmp_path):
    log_path = tmp_path / "pf.log"
    api = _api(log_path)
    api.deal_hole_cards(["Ah", "Kd"])
    api.notify_action(ActionEvent(player_id=1, action="raise", amount=5.0, street="preflop"))
    api.notify_action(ActionEvent(player_id=2, action="fold", amount=0.0, street="preflop"))
    api.request_action(street="preflop", pot=8.0, current_bet=5.0, to_call=3.0, my_stack=198.0,
                       num_active_opponents=1, my_current_bet_this_street=2.0)
    api.deal_board(["Ac", "7s", "2d"], street="flop")
    api.request_action(street="flop", pot=11.0, current_bet=0.0, to_call=0.0, my_stack=195.0,
                       num_active_opponents=1, my_current_bet_this_street=0.0)
    decisions = [r for r in _rows(log_path) if r.get("event") == "decision"]
    assert len(decisions) == 2
    pre, flop = decisions
    assert pre["decision_source"] == "rule_engine"
    assert pre.get("facing_action") == "open"
    assert flop["decision_source"] == "rule_engine"
    assert flop.get("final_purpose")
    assert "equity_calibration" in flop
    assert set(flop["equity_calibration"]) >= {"raw", "final", "online_bias"}


def test_river_opponent_action_has_layer_trace(tmp_path):
    log_path = tmp_path / "pf.log"
    api = _api(log_path)
    api.deal_hole_cards(["Ah", "Kd"])
    api.notify_action(ActionEvent(player_id=1, action="raise", amount=5.0, street="preflop"))
    api.notify_action(ActionEvent(player_id=2, action="fold", amount=0.0, street="preflop"))
    api.request_action(street="preflop", pot=8.0, current_bet=5.0, to_call=3.0, my_stack=198.0,
                       num_active_opponents=1, my_current_bet_this_street=2.0)
    api.deal_board(["Ac", "7s", "2d"], street="flop")
    api.request_action(street="flop", pot=11.0, current_bet=0.0, to_call=0.0, my_stack=195.0,
                       num_active_opponents=1, my_current_bet_this_street=0.0)
    api.notify_action(ActionEvent(player_id=1, action="check", amount=0.0, street="flop"))
    api.deal_board(["9h"], street="turn")
    api.request_action(street="turn", pot=11.0, current_bet=0.0, to_call=0.0, my_stack=195.0,
                       num_active_opponents=1, my_current_bet_this_street=0.0)
    api.notify_action(ActionEvent(player_id=1, action="check", amount=0.0, street="turn"))
    api.deal_board(["3c"], street="river")
    api.request_action(street="river", pot=11.0, current_bet=0.0, to_call=0.0, my_stack=195.0,
                       num_active_opponents=1, my_current_bet_this_street=0.0)
    api.notify_action(ActionEvent(player_id=1, action="raise", amount=8.0, street="river"))
    opp = [r for r in _rows(log_path) if r.get("event") == "opponent_action"]
    river = [r for r in opp if r["street"] == "river"][-1]
    trace = river["layer_trace"]
    assert trace["street"] == "river" and trace["action"] == "raise"
    layers = trace["layers"]
    assert set(layers) == {"pre", "likelihood", "uniform", "floor", "bucket_cal"}
    for entry in layers.values():
        assert "loss" in entry and 0.0 <= entry["loss"] <= 1.0
        assert "nuts" in entry
    assert "lam" in trace and trace["features"]["size_none"] == 0.0
    # Preflop actions carry no trace (no board yet).
    assert all(r.get("layer_trace") is None for r in opp if r["street"] == "preflop")
