import pytest

from pokerfate.core.card import Card
from pokerfate.core.game_state import Action, ActionType, GameState, Player, Street
from pokerfate.decision.realtime_cfr import (
    RealtimeCFRDecisionContext,
    RealtimeCFRDecisionEngine,
    RealtimeCFROptions,
    RealtimeCFRState,
    _build_solver_args,
    _locate_node,
    _select_exploit_action,
)
from pokerfate.decision.opponent_numeric_prior import build_numeric_prior
from pokerfate.strategy.range_v2.action_model import PlayerProfile
from pokerfate.strategy.range_v2 import hand_combo_map as hcm
from pokerfate.strategy.v3 import hero_range
from pokerfate.api import PokerFateAPI


def _cards(*values: str) -> list[Card]:
    return [Card.from_str(v) for v in values]


def _combo_index(combo: str) -> int:
    c1 = hcm.card_to_int(Card.from_str(combo[:2]))
    c2 = hcm.card_to_int(Card.from_str(combo[2:]))
    return hcm.COMBO_TO_IDX[tuple(sorted((c1, c2)))]


def _weights(*combos: str) -> list[float]:
    out = [0.0] * len(hcm.ALL_COMBOS)
    for combo in combos:
        out[_combo_index(combo)] = 1.0
    return out


def test_realtime_cfr_turn_decision_uses_solver_strategy(monkeypatch):
    hero = Player(0, "Hero", 1000.0, hole_cards=_cards("As", "Ah"), current_bet=0.0)
    villain = Player(1, "Villain", 940.0, current_bet=60.0)
    gs = GameState(
        players=[hero, villain],
        dealer_pos=0,
        street=Street.TURN,
        board=_cards("Kh", "7d", "2c", "9s"),
        pot=260.0,
        current_bet=60.0,
        big_blind=10.0,
        small_blind=5.0,
        player_positions={0: "BTN", 1: "BB"},
        action_history=[(1, Action(ActionType.RAISE, 60.0), "turn")],
    )

    def fake_solve(state, **_kwargs):
        assert state.board == "Kh7d2c9s"
        assert state.prefix == [("bet", 6.0)]
        assert state.pot_bb == 20.0
        assert state.effective_stack_bb == 100.0
        assert "QcQd" in state.oop_range
        assert state.ip_range == "AsAh"
        return {
            "node": {
                "path": "r:Bet(60)",
                "player": 1,
                "actions": ["Fold", "Call", "Raise(90)"],
                "num_hands": 1,
                "strategy": [0.05, 0.15, 0.80],
            },
            "oop_hands": ["QcQd"],
            "ip_hands": ["AsAh"],
            "exploitability_pct": 0.42,
        }

    monkeypatch.setattr("pokerfate.decision.realtime_cfr.solve_realtime_cfr", fake_solve)
    engine = RealtimeCFRDecisionEngine(RealtimeCFROptions(timeout_sec=0.1))
    action = engine.decide(
        RealtimeCFRDecisionContext(
            gs=gs,
            hero_player_id=0,
            street_start_pot=200.0,
            range_provider=lambda player_id: _weights("QcQd") if player_id == 1 else _weights(),
        )
    )

    assert action is not None
    assert action.action_type == ActionType.RAISE
    assert action.amount == 90.0
    assert engine.last_result["status"] == "ok"
    assert engine.last_result["selected_label"] == "Raise(90)"


def test_realtime_cfr_uses_hero_reach_range_provider(monkeypatch):
    hero = Player(0, "Hero", 1000.0, hole_cards=_cards("As", "Ah"), current_bet=0.0)
    villain = Player(1, "Villain", 940.0, current_bet=60.0)
    gs = GameState(
        players=[hero, villain],
        dealer_pos=0,
        street=Street.TURN,
        board=_cards("Kh", "7d", "2c", "9s"),
        pot=260.0,
        current_bet=60.0,
        big_blind=10.0,
        small_blind=5.0,
        player_positions={0: "BTN", 1: "BB"},
        action_history=[(1, Action(ActionType.RAISE, 60.0), "turn")],
    )

    def fake_solve(state, **_kwargs):
        assert "QcQd" in state.oop_range
        entries = state.ip_range.split(",")
        assert any(entry.startswith(("AsAh:", "AhAs:")) for entry in entries)
        assert any(entry.startswith("AsKs:") for entry in entries)
        assert not any(entry.startswith("KsAs:") for entry in entries)
        assert state.ip_range != "AsAh"
        return {
            "node": {
                "path": "r:Bet(60)",
                "player": 1,
                "actions": ["Fold", "Call", "Raise(90)"],
                "num_hands": 2,
                "strategy": [0.05, 0.50, 0.15, 0.40, 0.80, 0.10],
            },
            "oop_hands": ["QcQd"],
            "ip_hands": ["AsAh", "AsKs"],
            "exploitability_pct": 0.42,
        }

    monkeypatch.setattr("pokerfate.decision.realtime_cfr.solve_realtime_cfr", fake_solve)
    engine = RealtimeCFRDecisionEngine(RealtimeCFROptions(timeout_sec=0.1))
    action = engine.decide(
        RealtimeCFRDecisionContext(
            gs=gs,
            hero_player_id=0,
            street_start_pot=200.0,
            range_provider=lambda player_id: _weights("QcQd") if player_id == 1 else _weights(),
            hero_range_provider=lambda _player_id: _weights("AsAh", "AsKs"),
        )
    )

    assert action is not None
    assert action.action_type == ActionType.RAISE
    assert action.amount == 90.0
    assert engine.last_result["range_counts"]["ip"] == 2


def test_realtime_cfr_prefix_skips_folded_non_hu_player(monkeypatch):
    hero = Player(0, "Hero", 1000.0, hole_cards=_cards("As", "Ah"), current_bet=0.0)
    villain = Player(1, "Villain", 940.0, current_bet=60.0)
    folded = Player(2, "Folded", 1000.0, is_folded=True)
    gs = GameState(
        players=[hero, villain, folded],
        dealer_pos=1,
        street=Street.TURN,
        board=_cards("Kh", "7d", "2c", "9s"),
        pot=260.0,
        current_bet=60.0,
        big_blind=10.0,
        small_blind=5.0,
        player_positions={0: "BB", 1: "BTN", 2: "SB"},
        action_history=[
            (0, Action(ActionType.CHECK, 0.0), "turn"),
            (1, Action(ActionType.RAISE, 60.0), "turn"),
            (2, Action(ActionType.FOLD, 0.0), "turn"),
        ],
    )

    def fake_solve(state, **_kwargs):
        assert state.prefix == [("check", 0.0), ("bet", 6.0)]
        return {
            "node": {
                "path": "r:Check:Bet(60)",
                "player": 0,
                "actions": ["Fold", "Call"],
                "num_hands": 1,
                "strategy": [0.0, 1.0],
            },
            "oop_hands": ["AsAh"],
            "ip_hands": ["QcQd"],
            "exploitability_pct": 0.1,
        }

    monkeypatch.setattr("pokerfate.decision.realtime_cfr.solve_realtime_cfr", fake_solve)
    engine = RealtimeCFRDecisionEngine(RealtimeCFROptions(timeout_sec=0.1))
    action = engine.decide(
        RealtimeCFRDecisionContext(
            gs=gs,
            hero_player_id=0,
            street_start_pot=200.0,
            range_provider=lambda player_id: _weights("QcQd") if player_id == 1 else _weights(),
        )
    )

    assert action == Action(ActionType.CALL, 0.0)
    assert engine.last_result["status"] == "ok"


def test_realtime_cfr_solver_failure_keeps_specific_reason(monkeypatch):
    hero = Player(0, "Hero", 1000.0, hole_cards=_cards("As", "Ah"), current_bet=0.0)
    villain = Player(1, "Villain", 940.0, current_bet=60.0)
    gs = GameState(
        players=[hero, villain],
        dealer_pos=0,
        street=Street.TURN,
        board=_cards("Kh", "7d", "2c", "9s"),
        pot=260.0,
        current_bet=60.0,
        big_blind=10.0,
        small_blind=5.0,
        player_positions={0: "BTN", 1: "BB"},
        action_history=[(1, Action(ActionType.RAISE, 60.0), "turn")],
    )

    def fake_solve(_state, **_kwargs):
        return None

    fake_solve.last_error = "solver_worker_error"
    fake_solve.last_error_detail = {"error": "range parser failed"}
    monkeypatch.setattr("pokerfate.decision.realtime_cfr.solve_realtime_cfr", fake_solve)
    engine = RealtimeCFRDecisionEngine(RealtimeCFROptions(timeout_sec=0.1))

    action = engine.decide(
        RealtimeCFRDecisionContext(
            gs=gs,
            hero_player_id=0,
            street_start_pot=200.0,
            range_provider=lambda player_id: _weights("QcQd") if player_id == 1 else _weights(),
        )
    )

    assert action is None
    assert engine.last_result["reason"] == "solver_worker_error"
    assert engine.last_result["solver_error"]["error"] == "range parser failed"


def test_realtime_cfr_range_weights_do_not_use_scientific_notation():
    weights = [0.0] * len(hcm.ALL_COMBOS)
    weights[_combo_index("AsAh")] = 1.0
    weights[_combo_index("8h4s")] = 0.0000638744502513

    engine = RealtimeCFRDecisionEngine()
    range_text = engine._weights_to_range(weights, set(), hero=None)

    small_entry = next(entry for entry in range_text.split(",") if entry.startswith("8h4s:"))
    assert small_entry.startswith("8h4s:0.0000")
    assert "e-" not in range_text.lower()


def test_realtime_cfr_locates_live_raise_merged_to_all_in_node():
    nodes = [
        {"path": "r", "actions": ["Check", "Bet(118)", "Bet(268)", "Bet(536)"]},
        {
            "path": "r:Bet(118)",
            "actions": ["Fold", "Call", "Raise(260)", "Raise(354)", "AllIn(868)"],
        },
        {"path": "r:Bet(118):AllIn(868)", "actions": ["Fold", "Call"]},
    ]
    matches: list[dict] = []

    node = _locate_node(
        nodes,
        [("Bet", 118), ("Raise", 711)],
        path_matches=matches,
    )

    assert node is not None
    assert node["path"] == "r:Bet(118):AllIn(868)"
    assert matches[0]["match"] == "exact"
    assert matches[1]["match"] == "nearest"
    assert matches[1]["selected"] == "AllIn(868)"


def test_hero_combo_weights_keep_public_reach_range_not_exact_hand():
    weights = hero_range.combo_weights(
        position="BTN",
        facing="none",
        board=_cards("Kh", "7d", "2c", "9s"),
        hero_known_cards=_cards("As", "Ah"),
        my_prev_actions={"flop": "check"},
        is_pfr=True,
        force_include_cards=_cards("As", "Ah"),
    )

    assert sum(weights) == pytest.approx(1.0)
    assert weights[_combo_index("AsAh")] > 0.0
    assert weights[_combo_index("AsKs")] > 0.0
    assert weights[_combo_index("KhKd")] == 0.0


def test_realtime_cfr_solver_menu_matches_realtime_book():
    turn_state = RealtimeCFRState(
        board="Kh7d2c9s",
        oop_range="QcQd",
        ip_range="AsAh",
        pot_bb=20.0,
        effective_stack_bb=100.0,
    )
    turn_args, _ = _build_solver_args(turn_state, accuracy=1.5, max_iterations=1000)

    assert turn_args["turn_bets"] == "33%, 75%, 150%"
    assert turn_args["turn_bets_ip"] == "33%, 75%, 150%"
    assert turn_args["river_bets"] == "66%, 150%"
    assert turn_args["raises"] == "2.2x, 3x"
    assert turn_args["raises_ip"] == "2.2x, 3x"
    assert turn_args["include_evs"] is True

    river_state = RealtimeCFRState(
        board="Kh7d2c9s3c",
        oop_range="QcQd",
        ip_range="AsAh",
        pot_bb=20.0,
        effective_stack_bb=100.0,
    )
    river_args, _ = _build_solver_args(river_state, accuracy=1.0, max_iterations=1000)

    assert river_args["river_bets"] == "33%, 66%, 100%, 150%"
    assert river_args["river_bets_ip"] == "33%, 66%, 100%, 150%"
    assert river_args["raises"] == "2.2x, 3x"
    assert river_args["include_evs"] is True


def _bluff_spot(fold_eq=0.30):
    """Hero (in position) holds air on the turn: pot 20bb, a 10bb bet. Values as the solver
    reports them: an action's own EV is net of the bet, the value after each answer still
    counts the bet as hero's (fold: pot after rake + bet = 28.2bb, called: 0)."""
    bet_ev = fold_eq * 18.2 - (1.0 - fold_eq) * 10.0
    root = {
        "path": "r", "player": 1, "actions": ["Check", "Bet(100)"], "num_hands": 1,
        "strategy": [0.70, 0.30], "evs": [0.0, bet_ev * 10.0],
    }
    return {
        "node": root,
        "nodes": [
            root,
            {
                "path": "r:Bet(100)", "player": 0, "actions": ["Fold", "Call"], "num_hands": 2,
                "strategy": [fold_eq, fold_eq, 1.0 - fold_eq, 1.0 - fold_eq], "weights": [0.50, 0.50],
                "opponent_num_hands": 1, "opponent_evs": [282.0, 0.0],
            },
        ],
        "oop_hands": ["QcQd", "JcJd"],
        "ip_hands": ["7s6s"],
    }


_KNOWN_PLAYER = dict(name="regular", hands_seen=600, flop_seen_count=200, vpip=0.30, pfr=0.20, af=1.5,
                     fold_to_cbet=0.45, fold_to_cbet_opps=60, wtsd=0.25, turn_action_count=150)
_TURN_BLUFF_CONTEXT = {
    "street": "turn", "current_pot_bb": 20.0, "hero_current_bet_bb": 0.0, "current_to_call_bb": 0.0,
    "effective_stack_bb": 100.0, "hero_actions": [], "villain_actions": [("turn", "check")],
    "range_v2": {"bucket_dist": {"medium": 0.5, "air": 0.5}},
}


def _use_response_model(monkeypatch, tmp_path, models):
    """Point the response model at a file holding ``models`` ({kind: {street: spec}})."""
    import json as _json
    path = tmp_path / "response_model.json"
    path.write_text(_json.dumps({"version": 1, "models": models}), encoding="utf-8")
    monkeypatch.setenv("PF_RESPONSE_MODEL_PATH", str(path))
    return path


def _constant_answers(fold, call, raise_=1e-9):
    """A facing-bet model that answers fold / call / raise with these frequencies whatever the spot."""
    import math as _math
    return {"call": {"intercept": _math.log(call / fold), "weights": {}},
            "raise": {"intercept": _math.log(raise_ / fold), "weights": {}}}


def test_bet_value_follows_the_fitted_fold_frequency(monkeypatch, tmp_path):
    # Equilibrium folds 32%, which makes the bluff lose 0.98bb. The fitted model says this
    # opponent folds 60%: (0.60 - 0.32) x (18.2 + 10) = +7.90bb.
    _use_response_model(monkeypatch, tmp_path, {"facing_bet": {"turn": _constant_answers(0.6, 0.4)}})
    selection = _select_exploit_action(
        _bluff_spot(fold_eq=0.32), hero_combo="7s6s", hero_side="ip", street="turn",
        gto_strategy={"Check": 0.70, "Bet(100)": 0.30}, profile=PlayerProfile(**_KNOWN_PLAYER),
        adjustments={}, max_confidence=0.45, enabled=True, line_context=dict(_TURN_BLUFF_CONTEXT),
    )
    exploit = selection["exploit"]
    assert exploit["used"] is True
    assert exploit["gto_action_evs_bb"]["Bet(100)"] == pytest.approx(-0.976, abs=1e-3)
    assert exploit["adjusted_action_evs_bb"]["Bet(100)"] == pytest.approx(6.92, abs=1e-3)
    answers = exploit["response_summaries"]["Bet(100)"]
    assert answers["response"]["model"] is True
    assert answers["response"]["equilibrium"] == {"fold": 0.32, "call": 0.68}
    assert answers["response"]["fitted"] == {"fold": pytest.approx(0.6, abs=1e-4), "call": pytest.approx(0.4, abs=1e-4)}
    assert answers["response"]["size"] == pytest.approx(0.5)
    assert answers["adj"]["Fold"] == pytest.approx(0.6, abs=1e-4)
    # blended with the confidence in the read, the bluff is now better than checking
    confidence = exploit["confidence"]
    assert exploit["final_action_evs_bb"]["Bet(100)"] == pytest.approx((1 - confidence) * -0.976 + confidence * 6.92, abs=2e-3)
    assert selection["selected_label"] == "Bet(100)"


def test_fitted_answers_cannot_lift_an_action_the_solver_rates_far_below_its_best(monkeypatch, tmp_path):
    # Same spot with a 25% equilibrium fold rate: the bluff is 2.95bb worse than checking,
    # beyond the GTO leash, so no expected fold frequency makes it the choice.
    _use_response_model(monkeypatch, tmp_path, {"facing_bet": {"turn": _constant_answers(0.9, 0.1)}})
    selection = _select_exploit_action(
        _bluff_spot(fold_eq=0.25), hero_combo="7s6s", hero_side="ip", street="turn",
        gto_strategy={"Check": 0.70, "Bet(100)": 0.30}, profile=PlayerProfile(**_KNOWN_PLAYER),
        adjustments={}, max_confidence=0.45, enabled=True, line_context=dict(_TURN_BLUFF_CONTEXT),
    )
    assert selection["exploit"]["adjusted_action_evs_bb"]["Bet(100)"] > 10.0
    assert selection["exploit"]["safety"]["gto_leash"][0]["action"] == "Bet(100)"
    assert selection["selected_label"] == "Check"


def test_bet_keeps_its_solver_value_where_the_model_has_nothing_to_say(monkeypatch, tmp_path):
    spot = dict(result=_bluff_spot(), hero_combo="7s6s", hero_side="ip", street="turn",
                gto_strategy={"Check": 0.70, "Bet(100)": 0.30}, profile=PlayerProfile(**_KNOWN_PLAYER),
                adjustments={}, max_confidence=0.45, enabled=True)

    def bet_values(context, reason):
        selection = _select_exploit_action(spot["result"], line_context=context,
                                           **{k: v for k, v in spot.items() if k != "result"})
        exploit = selection["exploit"]
        assert exploit["response_summaries"]["Bet(100)"]["response"]["model"] is False
        assert exploit["response_summaries"]["Bet(100)"]["response"]["reason"] == reason
        assert exploit["adjusted_action_evs_bb"]["Bet(100)"] == pytest.approx(exploit["gto_action_evs_bb"]["Bet(100)"])
        assert selection["selected_label"] == "Check"

    _use_response_model(monkeypatch, tmp_path, {"facing_bet": {"turn": _constant_answers(0.6, 0.4)}})
    robot = dict(_TURN_BLUFF_CONTEXT, range_v2={"bucket_dist": {"medium": 0.5, "air": 0.5}, "villain_is_robot": True})
    bet_values(robot, "robot")                                   # a house robot is not in the fit
    bet_values({k: v for k, v in _TURN_BLUFF_CONTEXT.items() if k != "range_v2"}, "no_range")
    _use_response_model(monkeypatch, tmp_path, {"facing_bet": {"river": _constant_answers(0.6, 0.4)}})
    bet_values(dict(_TURN_BLUFF_CONTEXT), "no_model")            # no model for this street
    monkeypatch.setenv("PF_RESPONSE_MODEL_PATH", "off")
    bet_values(dict(_TURN_BLUFF_CONTEXT), "no_model")


def test_answers_to_a_bet_are_read_net_of_the_bet(monkeypatch):
    from pokerfate.decision.realtime_cfr import _response_adjusted_ev_detail_from_result

    monkeypatch.setenv("PF_RESPONSE_MODEL_PATH", "off")
    result = _bluff_spot()
    detail = _response_adjusted_ev_detail_from_result(
        result, result["nodes"][1], hero_combo="7s6s", hero_side="ip", profile=None,
        street="turn", hero_action_label="Bet(100)", line_context=dict(_TURN_BLUFF_CONTEXT),
    )
    assert detail is not None
    assert detail["response_evs"] == {"Fold": pytest.approx(18.2), "Call": pytest.approx(-10.0)}
    assert detail["ev"] == pytest.approx(-1.54, abs=1e-3)

    # values that do not add up to the action's own EV once the bet is taken off are not used
    result["nodes"][1]["opponent_evs"] = [182.0, -100.0]
    assert _response_adjusted_ev_detail_from_result(
        result, result["nodes"][1], hero_combo="7s6s", hero_side="ip", profile=None,
        street="turn", hero_action_label="Bet(100)", line_context=dict(_TURN_BLUFF_CONTEXT),
    ) is None


def test_realtime_cfr_exploit_low_data_prior_is_capped():
    result = {
        "node": {
            "path": "r",
            "player": 1,
            "actions": ["Check", "Bet(100)"],
            "num_hands": 1,
            "strategy": [0.70, 0.30],
            "evs": [100.0, 98.0],
        },
        "nodes": [
            {
                "path": "r",
                "player": 1,
                "actions": ["Check", "Bet(100)"],
                "num_hands": 1,
                "strategy": [0.70, 0.30],
                "evs": [100.0, 98.0],
            },
            {
                "path": "r:Bet(100)",
                "player": 0,
                "actions": ["Fold", "Call"],
                "num_hands": 2,
                "strategy": [0.30, 0.30, 0.70, 0.70],
                "weights": [0.50, 0.50],
                "opponent_num_hands": 1,
                "opponent_evs": [180.0, 20.0],
            },
        ],
        "oop_hands": ["QcQd", "JcJd"],
        "ip_hands": ["AsAh"],
    }
    profile = PlayerProfile(
        name="thin_sample",
        hands_seen=12,
        fold_to_cbet=0.90,
        fold_to_cbet_opps=6,
        wtsd=0.12,
        turn_action_count=4,
    )

    selection = _select_exploit_action(
        result,
        hero_combo="AsAh",
        hero_side="ip",
        street="turn",
        gto_strategy={"Check": 0.70, "Bet(100)": 0.30},
        profile=profile,
        adjustments={"bluff_ag_scale": 1.10, "value_ag_scale": 0.55},
        max_confidence=0.45,
        enabled=True,
    )

    assert selection["selected_label"] == "Check"
    assert selection["exploit"]["used"] is True
    assert "cluster" not in selection["exploit"]
    assert selection["exploit"]["numeric_prior"]["source"] in {"pool", "knn", "player_knn"}
    assert selection["exploit"]["confidence"] <= 0.10


def test_realtime_cfr_exploit_numeric_prior_replaces_label_bias():
    result = {
        "node": {
            "path": "r",
            "player": 1,
            "actions": ["Check", "Bet(100)"],
            "num_hands": 1,
            "strategy": [0.70, 0.30],
            "evs": [100.0, 98.0],
        },
        "nodes": [],
        "oop_hands": ["QcQd"],
        "ip_hands": ["AsAh"],
    }
    profile = PlayerProfile(
        name="neutral",
        hands_seen=240,
        af=1.5,
        wtsd=0.25,
        turn_action_count=90,
    )

    selection = _select_exploit_action(
        result,
        hero_combo="AsAh",
        hero_side="ip",
        street="turn",
        gto_strategy={"Check": 0.70, "Bet(100)": 0.30},
        profile=profile,
        adjustments={"bluff_ag_scale": 0.55, "value_ag_scale": 0.85},
        max_confidence=0.45,
        enabled=True,
    )

    assert selection["selected_label"] == "Check"
    assert selection["exploit"]["used"] is True
    assert "cluster" not in selection["exploit"]
    assert selection["exploit"]["numeric_prior"]["source"] == "player_knn"


def test_realtime_cfr_exploit_no_profile_and_no_line_does_not_mark_used():
    result = {
        "node": {
            "path": "r",
            "player": 1,
            "actions": ["Check", "Bet(100)"],
            "num_hands": 1,
            "strategy": [0.70, 0.30],
            "evs": [100.0, 98.0],
        },
        "nodes": [],
        "oop_hands": ["QcQd"],
        "ip_hands": ["AsAh"],
    }

    selection = _select_exploit_action(
        result,
        hero_combo="AsAh",
        hero_side="ip",
        street="turn",
        gto_strategy={"Check": 0.70, "Bet(100)": 0.30},
        profile=None,
        adjustments={},
        max_confidence=0.45,
        enabled=True,
    )

    assert selection["selected_label"] == "Check"
    assert selection["exploit"]["used"] is False


def test_realtime_cfr_underbluff_profile_can_promote_close_call_without_mdf_guard():
    """A strong 'villain rarely bets without it' read turns a marginal GTO
    fold into a call through the response/EV path alone; there is no
    per-combo MDF cap any more (MDF is a range property the solver already
    satisfies)."""
    result = {
        "node": {
            "path": "r",
            "player": 1,
            "actions": ["Fold", "Call"],
            "num_hands": 1,
            "strategy": [0.80, 0.20],
            "evs": [0.0, -0.5],
        },
        "nodes": [],
        "oop_hands": ["QcQd"],
        "ip_hands": ["AsAh"],
    }
    profile = PlayerProfile(
        name="underbluffer",
        hands_seen=240,
        af=1.5,
        wtsd=0.25,
        river_action_count=90,
    )

    selection = _select_exploit_action(
        result,
        hero_combo="AsAh",
        hero_side="ip",
        street="river",
        gto_strategy={"Fold": 0.80, "Call": 0.20},
        profile=profile,
        adjustments={"river_bet_rare": True},
        max_confidence=0.45,
        enabled=True,
    )

    assert selection["exploit"]["used"] is True
    assert "defense_mdf" not in selection["exploit"]["safety"]
    # river_bet_rare lowers Call EV and raises Fold EV; Fold must stay selected.
    assert selection["selected_label"] == "Fold"


def test_realtime_cfr_gto_leash_excludes_far_below_actions():
    """An action the solver rates far below its best cannot be promoted above
    the solver's best action by exploit EV alone (capped under its final EV)."""
    result = {
        "node": {
            "path": "r",
            "player": 1,
            "actions": ["Fold", "Call", "Raise(300)"],
            "num_hands": 1,
            "strategy": [1.0, 0.0, 0.0],
            "evs": [0.0, -5.0, -40.0],
        },
        "nodes": [],
        "oop_hands": ["QcQd"],
        "ip_hands": ["AsAh"],
    }
    profile = PlayerProfile(name="foldy", hands_seen=300, af=0.6, wtsd=0.15, river_action_count=120,
                            river_fold_rate=0.9)
    selection = _select_exploit_action(
        result,
        hero_combo="AsAh",
        hero_side="ip",
        street="river",
        gto_strategy={"Fold": 1.0, "Call": 0.0, "Raise(300)": 0.0},
        profile=profile,
        adjustments={"value_ag_scale": 0.3, "bluff_ag_scale": 0.2},
        max_confidence=0.45,
        enabled=True,
        line_context={"current_pot_bb": 20.0},
    )
    assert selection["selected_label"] == "Fold"
    leashed = {row["action"] for row in selection["exploit"]["safety"].get("gto_leash", [])}
    assert "Raise(300)" in leashed
    final = selection["exploit"]["final_action_evs_bb"]
    assert final["Raise(300)"] < final["Fold"]


def test_realtime_cfr_near_ev_actions_are_mixed_with_seed():
    result = {
        "node": {
            "path": "r",
            "player": 1,
            "actions": ["Check", "Bet(100)"],
            "num_hands": 1,
            "strategy": [0.55, 0.45],
            "evs": [100.0, 99.5],
        },
        "nodes": [],
        "oop_hands": ["QcQd"],
        "ip_hands": ["AsAh"],
    }
    picks = set()
    for seed in range(1, 40):
        selection = _select_exploit_action(
            result,
            hero_combo="AsAh",
            hero_side="ip",
            street="river",
            gto_strategy={"Check": 0.55, "Bet(100)": 0.45},
            profile=None,
            adjustments={},
            max_confidence=0.45,
            enabled=True,
            line_context={"current_pot_bb": 10.0},
            decision_seed=seed,
        )
        picks.add(selection["selected_label"])
    assert picks == {"Check", "Bet(100)"}
    # Same seed → same pick (reproducible mixing).
    a = _select_exploit_action(result, hero_combo="AsAh", hero_side="ip", street="river",
                               gto_strategy={"Check": 0.55, "Bet(100)": 0.45}, profile=None,
                               adjustments={}, max_confidence=0.45, enabled=True,
                               line_context={"current_pot_bb": 10.0}, decision_seed=7)
    b = _select_exploit_action(result, hero_combo="AsAh", hero_side="ip", street="river",
                               gto_strategy={"Check": 0.55, "Bet(100)": 0.45}, profile=None,
                               adjustments={}, max_confidence=0.45, enabled=True,
                               line_context={"current_pot_bb": 10.0}, decision_seed=7)
    assert a["selected_label"] == b["selected_label"]
    # Without a seed the EV-best action is chosen deterministically.
    c = _select_exploit_action(result, hero_combo="AsAh", hero_side="ip", street="river",
                               gto_strategy={"Check": 0.55, "Bet(100)": 0.45}, profile=None,
                               adjustments={}, max_confidence=0.45, enabled=True,
                               line_context={"current_pot_bb": 10.0})
    assert c["selected_label"] == "Check"


def test_realtime_cfr_overvalue_profile_does_not_treat_underbluff_as_nuts():
    result = {
        "node": {
            "path": "r:Bet(355):AllIn(697)",
            "player": 1,
            "actions": ["Fold", "Call"],
            "num_hands": 1,
            "strategy": [0.68, 0.32],
            "evs": [0.0, -0.7],
        },
        "nodes": [],
        "oop_hands": ["QcJs"],
        "ip_hands": ["JcQs"],
    }
    profile = PlayerProfile(
        name="loose_passive_overvalue",
        hands_seen=1500,
        vpip=0.61,
        pfr=0.09,
        af=0.75,
        flop_seen_count=120,
        showdown_count=32,
        showdown_win_count=8,
        wtsd=0.48,
        wmsd=0.25,
        river_afq=0.35,
        river_bet_freq=0.50,
        bluff_win_rate=0.10,
        bet_win_count=8,
        river_bet_count=4,
        river_check_count=4,
        river_action_count=8,
        server_af_prior=0.75,
        server_wtsd_prior=0.48,
    )

    selection = _select_exploit_action(
        result,
        hero_combo="JcQs",
        hero_side="ip",
        street="river",
        gto_strategy={"Fold": 0.68, "Call": 0.32},
        profile=profile,
        adjustments={"bluff_ag_scale": 0.10, "value_ag_scale": 0.86},
        max_confidence=0.45,
        enabled=True,
        line_context={
            "street": "river",
            "current_pot_bb": 158.9757,
            "current_to_call_bb": 34.1757,
            "hero_current_bet_bb": 35.5,
            "effective_stack_bb": 95.2,
        },
        hero_made_rank="two_pair",
    )

    scores = selection["exploit"]["numeric_prior"]["scores"]
    assert scores["overvalue"] > 0.70
    assert scores["nut_heavy"] < 0.20
    assert selection["selected_label"] == "Call"


def test_realtime_cfr_nut_heavy_profile_still_respects_value_raise():
    result = {
        "node": {
            "path": "r:Bet(355):AllIn(697)",
            "player": 1,
            "actions": ["Fold", "Call"],
            "num_hands": 1,
            "strategy": [0.68, 0.32],
            "evs": [0.0, -0.7],
        },
        "nodes": [],
        "oop_hands": ["QcJs"],
        "ip_hands": ["JcQs"],
    }
    profile = PlayerProfile(
        name="tight_nut_heavy",
        hands_seen=1500,
        vpip=0.18,
        pfr=0.15,
        af=1.0,
        flop_seen_count=180,
        showdown_count=70,
        showdown_win_count=49,
        fold_to_cbet=0.70,
        fold_to_cbet_opps=50,
        wtsd=0.20,
        wmsd=0.70,
        river_afq=0.12,
        river_bet_freq=0.12,
        bluff_win_rate=0.02,
        bet_win_count=20,
        river_bet_count=2,
        river_check_count=20,
        river_action_count=30,
        server_af_prior=1.0,
        server_wtsd_prior=0.20,
    )

    selection = _select_exploit_action(
        result,
        hero_combo="JcQs",
        hero_side="ip",
        street="river",
        gto_strategy={"Fold": 0.68, "Call": 0.32},
        profile=profile,
        adjustments={
            "river_bet_rare": True,
            "bluff_ag_scale": 0.10,
            "value_ag_scale": 0.86,
        },
        max_confidence=0.45,
        enabled=True,
        line_context={
            "street": "river",
            "current_pot_bb": 158.9757,
            "current_to_call_bb": 34.1757,
            "hero_current_bet_bb": 35.5,
            "effective_stack_bb": 95.2,
        },
        hero_made_rank="two_pair",
    )

    scores = selection["exploit"]["numeric_prior"]["scores"]
    assert scores["nut_heavy"] > 0.60
    assert scores["overvalue"] < 0.20
    assert selection["selected_label"] == "Fold"


def test_realtime_cfr_range_v2_bucket_prior_protects_cheap_showdown_call():
    result = {
        "node": {
            "path": "r",
            "player": 1,
            "actions": ["Fold", "Call"],
            "num_hands": 1,
            "strategy": [0.62, 0.38],
            "evs": [0.0, -0.3],
        },
        "nodes": [],
        "oop_hands": ["QcJs"],
        "ip_hands": ["JcQs"],
    }

    selection = _select_exploit_action(
        result,
        hero_combo="JcQs",
        hero_side="ip",
        street="river",
        gto_strategy={"Fold": 0.62, "Call": 0.38},
        profile=None,
        adjustments={},
        max_confidence=0.45,
        enabled=True,
        line_context={
            "street": "river",
            "current_pot_bb": 100.0,
            "current_to_call_bb": 15.0,
            "hero_current_bet_bb": 30.0,
            "effective_stack_bb": 100.0,
            "range_v2": {
                "bucket_dist": {"strong": 0.42, "medium": 0.30, "air": 0.18, "nuts": 0.10},
                "vs_hero": {"win": 0.70, "tie": 0.02, "loss": 0.28},
                "action_context": {"action": "raise", "bet_ratio": 0.65, "is_raise_over": True},
                "action_likelihood": {
                    "action": "raise",
                    "dist": {"strong": 0.55, "medium": 0.35, "air": 0.22, "nuts": 0.60},
                    "blend": 0.06,
                    "key": "knn:river|two_third|1:raise_over",
                    "n": 42,
                },
            },
        },
        hero_made_rank="two_pair",
    )

    assert selection["selected_label"] == "Call"
    assert selection["exploit"]["used"] is True
    assert selection["exploit"]["line_context"]["range_v2"]["action_likelihood"]["key"].startswith("knn:")


def test_numeric_prior_wmsd_confidence_uses_showdown_samples():
    thin = PlayerProfile(
        name="thin_showdown",
        hands_seen=1200,
        flop_seen_count=220,
        showdown_count=0,
        showdown_win_count=0,
        vpip=0.24,
        pfr=0.18,
        af=1.1,
        wtsd=0.22,
        wmsd=0.90,
        river_action_count=80,
    )
    proven = PlayerProfile(
        name="proven_showdown",
        hands_seen=1200,
        flop_seen_count=220,
        showdown_count=80,
        showdown_win_count=72,
        vpip=0.24,
        pfr=0.18,
        af=1.1,
        wtsd=0.22,
        wmsd=0.90,
        river_action_count=80,
    )

    thin_prior = build_numeric_prior(thin, {}, "river")
    proven_prior = build_numeric_prior(proven, {}, "river")

    assert proven_prior.nut_heavy_score > thin_prior.nut_heavy_score + 0.10


def test_realtime_cfr_river_call_chain_reprices_big_bluff():
    result = {
        "node": {
            "path": "r",
            "player": 1,
            "actions": ["Check", "Bet(300)"],
            "num_hands": 1,
            "strategy": [0.40, 0.60],
            "evs": [100.0, 102.0],
        },
        "nodes": [
            {
                "path": "r",
                "player": 1,
                "actions": ["Check", "Bet(300)"],
                "num_hands": 1,
                "strategy": [0.40, 0.60],
                "evs": [100.0, 102.0],
            },
            {
                "path": "r:Bet(300)",
                "player": 0,
                "actions": ["Fold", "Call"],
                "num_hands": 1,
                "strategy": [0.50, 0.50],
                "weights": [1.0],
                "opponent_num_hands": 1,
                "opponent_evs": [200.0, 0.0],
            },
        ],
        "oop_hands": ["QcQd"],
        "ip_hands": ["AsAh"],
    }

    selection = _select_exploit_action(
        result,
        hero_combo="AsAh",
        hero_side="ip",
        street="river",
        gto_strategy={"Check": 0.40, "Bet(300)": 0.60},
        profile=None,
        adjustments={},
        max_confidence=0.45,
        enabled=True,
        line_context={
            "street": "river",
            "villain_called_flop": True,
            "villain_called_turn": True,
            "villain_call_chain": 2,
            "villain_called_large_turn": True,
            "current_pot_bb": 20.0,
            "hero_current_bet_bb": 0.0,
            "current_to_call_bb": 0.0,
            "effective_stack_bb": 100.0,
        },
    )

    assert selection["selected_label"] == "Check"
    assert selection["exploit"]["used"] is True
    # no range from the tracker here: the answers stay at the equilibrium frequencies and
    # the repricing is the risk guard's (its own estimate of the folds after two calls)
    summary = selection["exploit"]["response_summaries"]["Bet(300)"]
    assert summary["response"]["model"] is False
    assert summary["adj"] == summary["eq"]
    assert selection["exploit"]["safety"]["river_aggression_risk"][0]["discount_bb"] > 0.0


def test_realtime_cfr_river_call_chain_keeps_value_big_bet():
    result = {
        "node": {
            "path": "r",
            "player": 1,
            "actions": ["Check", "Bet(300)"],
            "num_hands": 1,
            "strategy": [0.40, 0.60],
            "evs": [100.0, 190.0],
        },
        "nodes": [
            {
                "path": "r",
                "player": 1,
                "actions": ["Check", "Bet(300)"],
                "num_hands": 1,
                "strategy": [0.40, 0.60],
                "evs": [100.0, 190.0],
            },
            {
                "path": "r:Bet(300)",
                "player": 0,
                "actions": ["Fold", "Call"],
                "num_hands": 1,
                "strategy": [0.50, 0.50],
                "weights": [1.0],
                "opponent_num_hands": 1,
                "opponent_evs": [200.0, 180.0],
            },
        ],
        "oop_hands": ["QcQd"],
        "ip_hands": ["AsAh"],
    }

    selection = _select_exploit_action(
        result,
        hero_combo="AsAh",
        hero_side="ip",
        street="river",
        gto_strategy={"Check": 0.40, "Bet(300)": 0.60},
        profile=None,
        adjustments={},
        max_confidence=0.45,
        enabled=True,
        line_context={
            "street": "river",
            "villain_called_flop": True,
            "villain_called_turn": True,
            "villain_call_chain": 2,
            "villain_called_large_turn": True,
            "current_pot_bb": 20.0,
            "hero_current_bet_bb": 0.0,
            "current_to_call_bb": 0.0,
            "effective_stack_bb": 100.0,
        },
        hero_made_rank="full_house",
    )

    # The risk guard judges the bet by hero's own hand (it is not given the opponent's
    # answers): a full house keeps the big bet after two calls.
    assert selection["selected_label"] == "Bet(300)"
    assert selection["exploit"]["used"] is True
    risk = selection["exploit"]["safety"]["river_aggression_risk"][0]
    assert risk["value_supported"] is True


def test_realtime_cfr_large_size_support_blocks_unsupported_thin_value():
    result = {
        "node": {
            "path": "r",
            "player": 1,
            "actions": ["Check", "Bet(300)"],
            "num_hands": 1,
            "strategy": [0.02, 0.98],
            "evs": [100.0, 125.0],
        },
        "nodes": [
            {
                "path": "r",
                "player": 1,
                "actions": ["Check", "Bet(300)"],
                "num_hands": 1,
                "strategy": [0.02, 0.98],
                "evs": [100.0, 125.0],
            },
            {
                "path": "r:Bet(300)",
                "player": 0,
                "actions": ["Fold", "Call"],
                "num_hands": 1,
                "strategy": [0.55, 0.45],
                "weights": [1.0],
                "opponent_num_hands": 1,
                "opponent_evs": [140.0, 70.0],
            },
        ],
        "oop_hands": ["JcTc"],
        "ip_hands": ["KhKs"],
    }

    selection = _select_exploit_action(
        result,
        hero_combo="KhKs",
        hero_side="ip",
        street="river",
        gto_strategy={"Check": 0.02, "Bet(300)": 0.98},
        profile=None,
        adjustments={},
        max_confidence=0.45,
        enabled=True,
        line_context={
            "street": "river",
            "board": ["Ad", "As", "7h", "7c", "Qd"],
            "hero_combo": "KhKs",
            "villain_call_chain": 0,
            "current_pot_bb": 20.0,
            "hero_current_bet_bb": 0.0,
            "current_to_call_bb": 0.0,
            "effective_stack_bb": 100.0,
            "range_v2": {
                "bucket_dist": {
                    "nuts": 0.18,
                    "strong": 0.42,
                    "medium": 0.25,
                    "draw": 0.05,
                    "weak_draw": 0.03,
                    "air": 0.07,
                },
                "vs_hero": {"win": 0.42, "tie": 0.02, "loss": 0.56},
            },
        },
        hero_made_rank="two_pair",
    )

    assert selection["selected_label"] == "Check"
    support = selection["exploit"]["safety"]["large_size_support"][0]
    assert support["blocked"] is True
    assert support["support"]["value"] is False
    assert support["support"]["fold_equity"] is False
    assert support["support"]["ev"] is False
    assert selection["exploit"]["final_action_evs_bb"]["Bet(300)"] < selection["exploit"]["final_action_evs_bb"]["Check"]


def test_realtime_cfr_large_size_support_keeps_supported_value_bet():
    result = {
        "node": {
            "path": "r",
            "player": 1,
            "actions": ["Check", "Bet(300)"],
            "num_hands": 1,
            "strategy": [0.02, 0.98],
            "evs": [100.0, 160.0],
        },
        "nodes": [
            {
                "path": "r",
                "player": 1,
                "actions": ["Check", "Bet(300)"],
                "num_hands": 1,
                "strategy": [0.02, 0.98],
                "evs": [100.0, 160.0],
            },
            {
                "path": "r:Bet(300)",
                "player": 0,
                "actions": ["Fold", "Call"],
                "num_hands": 1,
                "strategy": [0.30, 0.70],
                "weights": [1.0],
                "opponent_num_hands": 1,
                "opponent_evs": [140.0, 165.0],
            },
        ],
        "oop_hands": ["JcTc"],
        "ip_hands": ["KhKs"],
    }

    selection = _select_exploit_action(
        result,
        hero_combo="KhKs",
        hero_side="ip",
        street="river",
        gto_strategy={"Check": 0.02, "Bet(300)": 0.98},
        profile=None,
        adjustments={},
        max_confidence=0.45,
        enabled=True,
        line_context={
            "street": "river",
            "board": ["Kd", "Ks", "7h", "7c", "Qd"],
            "hero_combo": "KhKs",
            "villain_call_chain": 0,
            "current_pot_bb": 20.0,
            "hero_current_bet_bb": 0.0,
            "current_to_call_bb": 0.0,
            "effective_stack_bb": 100.0,
            "range_v2": {
                "bucket_dist": {
                    "nuts": 0.06,
                    "strong": 0.24,
                    "medium": 0.46,
                    "draw": 0.04,
                    "weak_draw": 0.02,
                    "air": 0.18,
                },
                "vs_hero": {"win": 0.72, "tie": 0.04, "loss": 0.24},
            },
        },
        hero_made_rank="full_house",
    )

    assert selection["selected_label"] == "Bet(300)"
    assert "large_size_support" not in selection["exploit"]["safety"]


def test_raise_exposure_guard_prices_a_bet_that_folds_to_a_raise():
    from pokerfate.decision.realtime_cfr import _raise_exposure_risk_discount

    context = {
        "street": "river",
        "board": ["Ks", "Qd", "8h", "8c", "2d"],
        "hero_combo": "AhAd",
        "current_pot_bb": 20.0,
        "hero_current_bet_bb": 0.0,
        "current_to_call_bb": 0.0,
        "effective_stack_bb": 100.0,
        "range_v2": {
            "bucket_dist": {"nuts": 0.12, "strong": 0.42, "medium": 0.26, "draw": 0.0, "weak_draw": 0.0, "air": 0.20},
            "vs_hero": {"win": 0.41, "tie": 0.02, "loss": 0.57},
        },
    }
    # hero's values after each answer, net of the 8bb bet: fold +10, call +5.5, raise -2
    answers = {
        "adj_probs": {"Fold": 0.35, "Call": 0.45, "Raise(240)": 0.20},
        "response_evs": {"Fold": 10.0, "Call": 5.5, "Raise(240)": -2.0},
    }
    risk = _raise_exposure_risk_discount(
        "Bet(80)", street="river", line_context=context, response_detail=answers,
        best_passive_gto_ev=5.0, hero_combo="AhAd", hero_made_rank="one_pair", numeric_prior=None,
    )
    assert risk["raise_mass"] >= 0.15
    assert risk["ev_gap_bb"] > 0.0
    assert risk["discount_bb"] > 0.0
    # Without the opponent's answers it has nothing to price. That is how it has always
    # run inside the selection: every bet's answers failed the consistency check there, so
    # this guard never fired in live play (0 of 2,889 solver decisions, 2026-11-09..18).
    # The selection still gives it none while the risk guards wait for their review.
    assert _raise_exposure_risk_discount(
        "Bet(80)", street="river", line_context=context, response_detail={},
        best_passive_gto_ev=5.0, hero_combo="AhAd", hero_made_rank="one_pair", numeric_prior=None,
    ) is None


def test_realtime_cfr_calloff_risk_blocks_unsupported_large_call():
    result = {
        "node": {
            "path": "r:Bet(80):Raise(230)",
            "player": 1,
            "actions": ["Fold", "Call"],
            "num_hands": 1,
            "strategy": [0.10, 0.90],
            "evs": [0.0, 15.0],
        },
        "nodes": [
            {
                "path": "r:Bet(80):Raise(230)",
                "player": 1,
                "actions": ["Fold", "Call"],
                "num_hands": 1,
                "strategy": [0.10, 0.90],
                "evs": [0.0, 15.0],
            },
        ],
        "oop_hands": ["JcTc"],
        "ip_hands": ["AhAd"],
    }

    selection = _select_exploit_action(
        result,
        hero_combo="AhAd",
        hero_side="ip",
        street="river",
        gto_strategy={"Fold": 0.10, "Call": 0.90},
        profile=None,
        adjustments={},
        max_confidence=0.45,
        enabled=True,
        line_context={
            "street": "river",
            "board": ["Ks", "Qs", "8s", "8c", "2d"],
            "hero_combo": "AhAd",
            "current_pot_bb": 30.0,
            "hero_current_bet_bb": 8.0,
            "current_to_call_bb": 15.0,
            "effective_stack_bb": 15.0,
            "range_v2": {
                "bucket_dist": {
                    "nuts": 0.18,
                    "strong": 0.52,
                    "medium": 0.18,
                    "draw": 0.0,
                    "weak_draw": 0.0,
                    "air": 0.12,
                },
                "vs_hero": {"win": 0.18, "tie": 0.02, "loss": 0.80},
                "action_context": {
                    "street": "river",
                    "action": "raise",
                    "is_raise_over": True,
                    "bet_ratio": 0.76,
                },
            },
        },
        hero_made_rank="one_pair",
    )

    assert selection["selected_label"] == "Fold"
    risk = selection["exploit"]["safety"]["calloff_risk"][0]
    assert risk["is_raise_over"] is True
    assert risk["all_in"] is True
    assert risk["showdown_equity"] < risk["required_equity"]
    assert selection["exploit"]["final_action_evs_bb"]["Call"] < selection["exploit"]["final_action_evs_bb"]["Fold"]


def test_realtime_cfr_river_large_turn_call_blocks_unbacked_jam_without_child_response():
    result = {
        "node": {
            "path": "r",
            "player": 1,
            "actions": ["Check", "AllIn(1095)"],
            "num_hands": 1,
            "strategy": [0.0, 1.0],
            "evs": [0.0, 90.0],
        },
        "nodes": [],
        "oop_hands": ["JcTc"],
        "ip_hands": ["5h4h"],
    }

    selection = _select_exploit_action(
        result,
        hero_combo="5h4h",
        hero_side="ip",
        street="river",
        gto_strategy={"Check": 0.0, "AllIn(1095)": 1.0},
        profile=None,
        adjustments={},
        max_confidence=0.45,
        enabled=True,
        line_context={
            "street": "river",
            "board": ["8d", "Qs", "Ah", "9d", "9h"],
            "hero_combo": "5h4h",
            "villain_called_flop": True,
            "villain_called_turn": True,
            "villain_call_chain": 2,
            "villain_called_large_turn": True,
            "hero_turn_bet_bb": 21.2,
            "estimated_turn_start_pot_bb": 14.11,
            "turn_bet_pot_ratio": 1.50,
            "current_pot_bb": 56.51,
            "hero_current_bet_bb": 0.0,
            "current_to_call_bb": 0.0,
            "effective_stack_bb": 109.5,
            "range_v2": {
                "bucket_dist": {"strong": 0.618, "air": 0.340, "nuts": 0.042},
                "vs_hero": {"win": 0.0, "tie": 0.109, "loss": 0.891},
            },
        },
        hero_made_rank="one_pair",
    )

    assert selection["selected_label"] == "Check"
    risk = selection["exploit"]["safety"]["river_aggression_risk"][0]
    assert risk["fe_source"] == "range_line_estimate"
    assert risk["quality"]["blocker_score"] == 0.0
    assert risk["discount_bb"] > 8.0
    gate = selection["exploit"]["safety"]["strict_bluff_gate"][0]
    assert gate["blocked"] is True
    assert gate["showdown_equity"] < 0.35
    assert selection["exploit"]["final_action_evs_bb"]["AllIn(1095)"] < selection["exploit"]["final_action_evs_bb"]["Check"]


def test_realtime_cfr_strict_bluff_gate_does_not_touch_borderline_equity():
    result = {
        "node": {
            "path": "r",
            "player": 1,
            "actions": ["Check", "Bet(120)"],
            "num_hands": 1,
            "strategy": [0.10, 0.90],
            "evs": [0.0, 20.0],
        },
        "nodes": [],
        "oop_hands": ["JcTc"],
        "ip_hands": ["QhJh"],
    }

    selection = _select_exploit_action(
        result,
        hero_combo="QhJh",
        hero_side="ip",
        street="turn",
        gto_strategy={"Check": 0.10, "Bet(120)": 0.90},
        profile=None,
        adjustments={},
        max_confidence=0.45,
        enabled=True,
        line_context={
            "street": "turn",
            "board": ["8d", "Qs", "Ah", "9d"],
            "hero_combo": "QhJh",
            "villain_called_flop": True,
            "villain_call_chain": 1,
            "current_pot_bb": 14.0,
            "hero_current_bet_bb": 0.0,
            "current_to_call_bb": 0.0,
            "effective_stack_bb": 80.0,
            "range_v2": {
                "bucket_dist": {
                    "nuts": 0.08,
                    "strong": 0.27,
                    "medium": 0.35,
                    "draw": 0.10,
                    "weak_draw": 0.08,
                    "air": 0.12,
                },
                "vs_hero": {"win": 0.36, "tie": 0.0, "loss": 0.64},
            },
        },
        hero_made_rank="one_pair",
    )

    assert "strict_bluff_gate" not in selection["exploit"]["safety"]


def test_realtime_cfr_turn_large_barrel_needs_value_draw_or_blockers():
    result = {
        "node": {
            "path": "r:Check",
            "player": 1,
            "actions": ["Check", "Bet(212)"],
            "num_hands": 1,
            "strategy": [0.0, 1.0],
            "evs": [0.0, 40.0],
        },
        "nodes": [],
        "oop_hands": ["JcTc"],
        "ip_hands": ["5h4h"],
    }

    selection = _select_exploit_action(
        result,
        hero_combo="5h4h",
        hero_side="ip",
        street="turn",
        gto_strategy={"Check": 0.0, "Bet(212)": 1.0},
        profile=None,
        adjustments={},
        max_confidence=0.45,
        enabled=True,
        line_context={
            "street": "turn",
            "board": ["8d", "Qs", "Ah", "9d"],
            "hero_combo": "5h4h",
            "villain_called_flop": True,
            "villain_call_chain": 1,
            "current_pot_bb": 14.11,
            "hero_current_bet_bb": 0.0,
            "current_to_call_bb": 0.0,
            "effective_stack_bb": 130.0,
            "range_v2": {
                "bucket_dist": {
                    "nuts": 0.02,
                    "strong": 0.28,
                    "medium": 0.41,
                    "draw": 0.09,
                    "weak_draw": 0.09,
                    "air": 0.11,
                },
            },
        },
        hero_made_rank="high_card",
    )

    assert selection["selected_label"] == "Check"
    risk = selection["exploit"]["safety"]["turn_barrel_quality"][0]
    assert risk["quality"]["value_score"] == 0.0
    assert risk["quality"]["draw_score"] < 0.2
    assert risk["discount_bb"] > 0.0


def test_realtime_cfr_sticky_pool_blocks_unbacked_turn_pressure():
    result = {
        "node": {
            "path": "r",
            "player": 1,
            "actions": ["Check", "Bet(90)"],
            "num_hands": 1,
            "strategy": [0.05, 0.95],
            "evs": [0.0, 28.0],
        },
        "nodes": [
            {
                "path": "r",
                "player": 1,
                "actions": ["Check", "Bet(90)"],
                "num_hands": 1,
                "strategy": [0.05, 0.95],
                "evs": [0.0, 28.0],
            },
            {
                "path": "r:Bet(90)",
                "player": 0,
                "actions": ["Fold", "Call"],
                "num_hands": 1,
                "strategy": [0.24, 0.76],
                "weights": [1.0],
                "opponent_num_hands": 1,
                "opponent_evs": [90.0, -20.0],
            },
        ],
        "oop_hands": ["JcTc"],
        "ip_hands": ["5h4h"],
    }
    profile = PlayerProfile(
        name="sticky",
        hands_seen=220,
        flop_seen_count=120,
        vpip=0.58,
        pfr=0.10,
        af=0.7,
        fold_to_cbet=0.16,
        fold_to_cbet_opps=80,
        wtsd=0.43,
        turn_action_count=90,
        river_action_count=60,
        river_fold_rate=0.18,
    )

    selection = _select_exploit_action(
        result,
        hero_combo="5h4h",
        hero_side="ip",
        street="turn",
        gto_strategy={"Check": 0.05, "Bet(90)": 0.95},
        profile=profile,
        adjustments={"bluff_ag_scale": 0.12, "value_ag_scale": 1.12},
        max_confidence=0.45,
        enabled=True,
        line_context={
            "street": "turn",
            "board": ["8d", "Qs", "Ah", "9d"],
            "hero_combo": "5h4h",
            "villain_call_chain": 0,
            "current_pot_bb": 20.0,
            "hero_current_bet_bb": 0.0,
            "current_to_call_bb": 0.0,
            "effective_stack_bb": 90.0,
            "range_v2": {
                "bucket_dist": {
                    "nuts": 0.06,
                    "strong": 0.34,
                    "medium": 0.35,
                    "draw": 0.08,
                    "weak_draw": 0.05,
                    "air": 0.12,
                },
                "vs_hero": {"win": 0.38, "tie": 0.0, "loss": 0.62},
            },
        },
        hero_made_rank="high_card",
    )

    assert selection["selected_label"] == "Check"
    sticky = selection["exploit"]["safety"]["sticky_aggression"][0]
    assert sticky["blocked"] is True
    assert sticky["support"]["value"] is False
    assert sticky["support"]["draw"] is False
    assert sticky["adjusted_fe"] < sticky["required_fe"] + sticky["fe_margin"]


def test_realtime_cfr_ignores_flop():
    gs = GameState(
        players=[
            Player(0, "Hero", 100.0, hole_cards=_cards("As", "Ah")),
            Player(1, "Villain", 100.0),
        ],
        street=Street.FLOP,
        board=_cards("Kh", "7d", "2c"),
    )

    engine = RealtimeCFRDecisionEngine()
    action = engine.decide(
        RealtimeCFRDecisionContext(
            gs=gs,
            hero_player_id=0,
            street_start_pot=20.0,
            range_provider=lambda _player_id: _weights("QcQd"),
        )
    )

    assert action is None
    assert engine.last_result["reason"] == "street_not_supported"


def test_hero_range_follows_actual_preflop_line():
    from pokerfate.core.card import Card
    from pokerfate.core.game_state import Action, ActionType

    history = [
        (1, Action(ActionType.RAISE, 25.0), "preflop"),   # BTN opens
        (0, Action(ActionType.CALL, 0.0), "preflop"),     # hero BB calls
    ]
    line = hero_range.describe_preflop_line(history, 0, {1: "BTN", 0: "BB"})
    assert line["hero_action"] == "call"
    assert line["raises_before"] == 1
    assert line["opener_pos"] == "BTN"
    rng = hero_range._range_for("BB", "none", line)
    assert "72o" not in rng and "T7o" in rng  # BB vs BTN defend, not an RFI range

    history_3bet = [
        (1, Action(ActionType.RAISE, 25.0), "preflop"),
        (0, Action(ActionType.RAISE, 90.0), "preflop"),
    ]
    line_3bet = hero_range.describe_preflop_line(history_3bet, 0, {1: "CO", 0: "BTN"})
    rng_3bet = hero_range._range_for("BTN", "none", line_3bet)
    assert "AA" in rng_3bet and "A5s" in rng_3bet and "T7o" not in rng_3bet
    # The hero combo is always force-included even if outside the heuristic range.
    board = [Card.from_str(c) for c in ["Kh", "7d", "2c", "9s"]]
    weights = hero_range.combo_weights(
        "BTN", "none", board, preflop_line=line_3bet,
        force_include_cards=[Card.from_str("7h"), Card.from_str("2h")],
    )
    assert sum(1 for w in weights if w > 0) > 50


def test_hero_range_prior_street_call_narrows_range():
    from pokerfate.core.card import Card

    board = [Card.from_str(c) for c in ["Kh", "7d", "2c", "9s"]]
    base = hero_range.distribution("BB", "bb_defend", board)
    called = hero_range.distribution("BB", "bb_defend", board, my_prev_actions={"flop": "call"})
    # Calling a flop bet should leave relatively less air in hero's range.
    assert called["air"] < base["air"]


def test_hero_range_uses_solver_street_filter_when_present():
    from pokerfate.core.card import Card
    from pokerfate.strategy.range_v2 import hand_combo_map as hcm

    board = [Card.from_str(c) for c in ["Kh", "7d", "2c", "9s"]]
    keep = hcm.COMBO_TO_IDX[tuple(sorted((hcm.card_to_int(Card.from_str("Ks")), hcm.card_to_int(Card.from_str("Qs")))))]
    weights = hero_range.combo_weights(
        "BTN", "none", board,
        my_prev_actions={"flop": "bet"},
        street_filters={"flop": {keep: 1.0}},
        force_include_cards=[Card.from_str("Ks"), Card.from_str("Qs")],
    )
    assert weights[keep] == pytest.approx(1.0)
    assert sum(1 for w in weights if w > 1e-9) == 1


def test_response_evs_ignored_when_hero_combo_never_takes_action(monkeypatch):
    """Solver EVs at a child node are conditional on reach; with ~0 reach they
    have been garbage. Such an action keeps its solver value."""
    from pokerfate.decision.realtime_cfr import _response_adjusted_ev_detail_from_result

    monkeypatch.setenv("PF_RESPONSE_MODEL_PATH", "off")
    result = {
        "node": {
            "path": "r:Check:Bet(120)",
            "player": 0,
            "actions": ["Fold", "Call", "Raise(264)"],
            "num_hands": 1,
            "strategy": [1.0, 0.0, 0.0],
            "evs": [0.0, -3.4, -5.7],
        },
        "oop_hands": ["9s7s"],
        "ip_hands": ["AcKc"],
    }
    child = {
        "path": "r:Check:Bet(120):Raise(264)",
        "player": 1,
        "actions": ["Fold", "Call", "AllIn(420)"],
        "num_hands": 1,
        "strategy": [0.42, 0.11, 0.47],
        "weights": [1.0],
        "opponent_num_hands": 1,
        "opponent_evs": [365.0, 4000.0, -264.0],  # 4000 = reach-normalised garbage
    }
    context = {"current_pot_bb": 36.5, "current_to_call_bb": 12.0, "hero_current_bet_bb": 0.0}

    def detail():
        return _response_adjusted_ev_detail_from_result(
            result, child, hero_combo="9s7s", hero_side="oop", profile=None,
            street="turn", hero_action_label="Raise(264)", line_context=context,
        )

    assert detail() is None

    # With real reach the garbage is still caught: the values do not add up to the raise's own EV.
    result["node"]["strategy"] = [0.5, 0.2, 0.3]
    result["node"]["evs"] = [0.0, -3.4, 30.4]
    assert detail() is None

    # Self-consistent values are used. They count the 26.4bb of the raise as hero's:
    # (56.64 x .42 + 30 x .11 + 5 x .47) - 26.4 = 3.04bb, the raise's own EV.
    child["opponent_evs"] = [566.4, 300.0, 50.0]
    out = detail()
    assert out is not None
    assert out["ev"] == pytest.approx(3.04, abs=1e-6)
    assert out["response_evs"]["Fold"] == pytest.approx(56.64 - 26.4)


# ---------------------------------------------------------------------------
# River guards (2026-11-12): tracker-backed cheap call.
# Inputs are the solver outputs logged for real hands in pokerfate.log
# (session 2026-11-11T18:03Z); node EVs are in tenths of a big blind.
# ---------------------------------------------------------------------------

# The river fold rate is the villain's own (80 river bets faced).  Left to the pool it made
# Check and the overbet differ by under 0.01bb, and the test flipped with the pool rates.
_STICKY_PROFILE = dict(
    name="sticky", hands_seen=600, flop_seen_count=200, vpip=0.55, pfr=0.10, af=0.9,
    fold_to_cbet=0.25, fold_to_cbet_opps=120, wtsd=0.45, turn_action_count=150,
    river_action_count=90, river_bet_freq=0.55, river_afq=0.50,
    river_fold_rate=0.20, river_facing_bet_opps=80,
)


def _hand_1260_selection(options, *, win=0.936, seed=None):
    """Hand #1260: hero 8h9s on 9dJcKc9h2h, first to act on the river, pot 16.5bb.

    Strategy and EVs at hero's node are the logged solver output; the sticky
    profile stands in for the live villain.
    """
    actions = ["Check", "Bet(54)", "Bet(109)", "Bet(165)", "Bet(248)"]
    strategy = [0.1664, 0.0183, 0.2285, 0.1883, 0.3985]
    evs = [174.755, 166.274, 171.013, 173.719, 176.174]
    result = {
        "node": {"path": "r", "player": 0, "actions": actions, "num_hands": 1,
                 "strategy": strategy, "evs": evs},
        "nodes": [],
        "oop_hands": ["8h9s"],
        "ip_hands": ["8dTs"],
    }
    return _select_exploit_action(
        result,
        hero_combo="8h9s",
        hero_side="oop",
        street="river",
        gto_strategy=dict(zip(actions, strategy)),
        profile=PlayerProfile(**_STICKY_PROFILE),
        adjustments={"bluff_ag_scale": 0.6, "value_ag_scale": 1.1},
        max_confidence=0.45,
        enabled=True,
        hero_made_rank="three_of_a_kind",
        decision_seed=seed,
        options=options,
        line_context={
            "street": "river",
            "board": ["9d", "Jc", "Kc", "9h", "2h"],
            "hero_combo": "8h9s",
            "current_pot_bb": 16.5,
            "current_to_call_bb": 0.0,
            "hero_current_bet_bb": 0.0,
            "effective_stack_bb": 95.0,
            "range_v2": {
                "bucket_dist": {"air": 0.45, "strong": 0.25, "medium": 0.22, "nuts": 0.08},
                "vs_hero": {"win": win, "tie": 0.0, "loss": 1.0 - win},
            },
        },
    )


def test_bet_without_answers_in_the_tree_keeps_its_solver_value():
    # The logged node carries no opponent decisions, so nothing is known about the answers
    # to a bet and each bet keeps its solver value; the pot-size overbet is the solver's
    # best action for this hand by 0.14bb and the tracker rates the hand as value, so the
    # risk guards leave it alone. (Until 2026-11-19 a hand-written penalty on bets against
    # a sticky opponent turned this into a check, and from 2026-11-12 to 11-18 a river
    # "value-bet floor" turned it back: docs/candidates/value_bet_floor_removal_2026-11-18/.)
    selection = _hand_1260_selection(RealtimeCFROptions())
    exploit = selection["exploit"]
    assert selection["selected_label"] == "Bet(248)"
    for label in ("Bet(54)", "Bet(109)", "Bet(165)", "Bet(248)"):
        assert exploit["adjusted_action_evs_bb"][label] == pytest.approx(exploit["gto_action_evs_bb"][label])
    assert "value_bet_floor" not in exploit["safety"]


def _river_facing_selection(options, *, pot, to_call, call_ev_bb, win, rank="two_pair",
                            hero_bet=0.0, strategy=(0.5, 0.5), path="r:Bet(100)"):
    actions = ["Fold", "Call"]
    result = {
        "node": {"path": path, "player": 1, "actions": actions, "num_hands": 1,
                 "strategy": list(strategy), "evs": [0.0, call_ev_bb * 10.0]},
        "nodes": [],
        "oop_hands": ["KhJh"],
        "ip_hands": ["AsQs"],
    }
    return _select_exploit_action(
        result,
        hero_combo="AsQs",
        hero_side="ip",
        street="river",
        gto_strategy=dict(zip(actions, strategy)),
        profile=None,
        adjustments={},
        max_confidence=0.45,
        enabled=True,
        hero_made_rank=rank,
        options=options,
        line_context={
            "street": "river",
            "board": ["4c", "4d", "Td", "6h", "Ad"],
            "hero_combo": "AsQs",
            "current_pot_bb": pot,
            "current_to_call_bb": to_call,
            "hero_current_bet_bb": hero_bet,
            "effective_stack_bb": 37.44,
            "range_v2": {
                "bucket_dist": {"nuts": 0.45, "strong": 0.40, "air": 0.15},
                "vs_hero": {"win": win, "tie": 0.0, "loss": 1.0 - win},
                "action_context": {"action": "raise", "bet_ratio": 0.16, "is_raise_over": True},
            },
        },
    )


def _hand_383(options, **overrides):
    """Hand #383: AsQs bets the river, villain shoves for 13.1bb more into 96.7bb."""
    params = dict(pot=96.7, to_call=13.1, call_ev_bb=-4.9637, win=0.53, hero_bet=23.8,
                  strategy=(0.2344, 0.7656), path="r:Check:Bet(238):AllIn(374)")
    params.update(overrides)
    return _river_facing_selection(options, **params)


def test_cheap_call_guard_accepts_tracker_evidence_with_pot_scaled_tolerance():
    # Old behaviour: solver EV(call) = -4.96bb, the leash caps Call under Fold.
    for old_options in (
        RealtimeCFROptions(cheap_call_pot_tolerance=0.0),
        RealtimeCFROptions(cheap_call_min_showdown_value=0.0),
    ):
        old = _hand_383(old_options)
        assert old["selected_label"] == "Fold"
        assert "overvalue_cheap_call_guard" not in old["exploit"]["safety"]

    new = _hand_383(RealtimeCFROptions())
    assert new["selected_label"] == "Call"
    guard = new["exploit"]["safety"]["overvalue_cheap_call_guard"]
    assert "tracker" in guard["evidence"]
    assert guard["pot_odds"] == pytest.approx(13.1 / (96.7 + 13.1), abs=1e-3)
    assert guard["showdown_value"] == pytest.approx(0.53)
    # 6% of the 96.7bb pot replaces the ~2bb absolute tolerance.
    assert guard["gto_tolerance_bb"] == pytest.approx(0.06 * 96.7, abs=1e-3)
    assert guard["gto_gap_bb"] < guard["gto_tolerance_bb"]


def test_cheap_call_guard_tracker_path_keeps_its_limits():
    options = RealtimeCFROptions()
    # Solver gap beyond 6% of the pot.
    assert _hand_383(options, call_ev_bb=-8.0)["selected_label"] == "Fold"
    # Tracker itself rates the hand below the calibrated band.
    assert _hand_383(options, win=0.30)["selected_label"] == "Fold"
    # Made-hand gate of the guard is unchanged.
    assert _hand_383(options, rank="one_pair")["selected_label"] == "Fold"
    # Hand #419: J6 two pair facing a pot-size bet (33% pot odds) - not cheap.
    not_cheap = _river_facing_selection(
        options, pot=61.7, to_call=30.8, call_ev_bb=-6.5591, win=0.61,
        strategy=(0.455, 0.545), path="r:Bet(308)",
    )
    assert not_cheap["selected_label"] == "Fold"


def _unreached_result(hero_weight: float, other_weight: float, opponent_weights=None, call_ev: float = 0.0) -> dict:
    """Hero (OOP) bet, the opponent moved all in; hero's combo is the first of two hands at the node.

    ``weights`` is each hand's own reach times the opponent's. A binding without
    ``opponent_weights`` reports 0 for every action of a hand whose weight is 0."""
    node = {
        "path": "r:Bet(160):AllIn(278)",
        "player": 0,
        "actions": ["Fold", "Call"],
        "num_hands": 2,
        "strategy": [0.0, 0.6, 1.0, 0.4],
        "evs": [0.0, 0.0, call_ev if opponent_weights else (0.0 if hero_weight <= 0.0 else 500.0),
                0.0 if other_weight <= 0.0 else -30.0],
        "weights": [hero_weight, other_weight],
    }
    if opponent_weights is not None:
        node["opponent_weights"] = list(opponent_weights)
    return {"node": node, "nodes": [node], "oop_hands": ["Ad4d", "KcQh"], "ip_hands": ["7c7s"]}


def _nut_heavy_caller_profile() -> PlayerProfile:
    return PlayerProfile(
        name="loose_passive",
        hands_seen=1976,
        flop_seen_count=40,
        vpip=0.74,
        pfr=0.14,
        af=0.53,
        fold_to_cbet=0.43,
        fold_to_cbet_opps=20,
        wtsd=0.39,
        turn_action_count=27,
    )


_ALL_IN_OVER_HERO_BET = {
    "street": "turn",
    "hero_turn_bet_bb": 16.0,
    "current_pot_bb": 59.78,
    "current_to_call_bb": 11.78,
    "hero_current_bet_bb": 16.0,
    "effective_stack_bb": 27.78,
    "range_v2": {
        "bucket_dist": {"nuts": 0.29, "strong": 0.28, "medium": 0.27, "draw": 0.11, "weak_draw": 0.02, "air": 0.03},
        "action_context": {
            "action": "raise", "street": "turn", "is_ip": True, "is_raise_over": True,
            "bet_ratio": 0.87, "facing_action": "bet",
        },
    },
}


def _select_at_all_in(result: dict) -> dict:
    return _select_exploit_action(
        result,
        hero_combo="4dAd",
        hero_side="oop",
        street="turn",
        gto_strategy={"Fold": 0.0, "Call": 1.0},
        profile=_nut_heavy_caller_profile(),
        adjustments={"value_ag_scale": 0.73, "bluff_ag_scale": 0.63, "river_bet_rare": True},
        max_confidence=0.45,
        enabled=True,
        big_blind=5000.0,
        hero_made_rank="flush",
        line_context=dict(_ALL_IN_OVER_HERO_BET),
        decision_seed=7,
    )


def test_zero_evs_of_a_combo_that_does_not_reach_the_node_are_not_read_as_evs():
    # Live 2026-11-17: hero bet the turn with the nut flush through the rule
    # engine; the solver never bets that size with it, so at the node after the
    # opponent's all-in the combo had reach 0 and "EVs" Fold 0 / Call 0. The
    # exploit nudges alone then chose Fold against a 100% Call strategy.
    selection = _select_at_all_in(_unreached_result(0.0, 0.004))

    assert selection["selected_label"] == "Call"
    assert selection["exploit"]["used"] is False
    assert selection["exploit"]["reason"] == "hero_combo_unreached"
    assert "action_evs_bb" not in selection


def test_real_evs_of_a_combo_that_reaches_the_node_are_still_used():
    selection = _select_at_all_in(_unreached_result(0.002, 0.004))

    assert selection["selected_label"] == "Call"
    assert selection["action_evs_bb"] == {"Fold": 0.0, "Call": 50.0}
    assert selection["exploit"]["used"] is True


def test_a_combo_off_the_solver_line_keeps_its_real_evs_when_the_binding_reports_them():
    # The patched binding divides by the opponent's weight, so the combo has a
    # real EV although its own reach is 0; the exploit layer then works as usual
    # and cannot talk itself out of a +51bb call.
    selection = _select_at_all_in(_unreached_result(0.0, 0.004, opponent_weights=[0.36, 0.36], call_ev=512.86))

    assert selection["selected_label"] == "Call"
    assert selection["action_evs_bb"] == {"Fold": 0.0, "Call": 51.286}
    assert selection["exploit"]["used"] is True
    assert selection["exploit"]["final_action_evs_bb"]["Call"] > 25.0


def test_a_node_no_opponent_hand_reaches_has_no_values_even_with_the_patched_binding():
    selection = _select_at_all_in(_unreached_result(0.0, 0.0, opponent_weights=[0.0, 0.0]))

    assert selection["exploit"]["used"] is False
    assert selection["exploit"]["reason"] == "solver_node_unreached"
    assert "action_evs_bb" not in selection


@pytest.mark.parametrize(
    "weights, reason",
    [([0.0, 0.2], "hero_combo_unreached"), ([0.0, 0.0], "solver_node_unreached")],
)
def test_realtime_cfr_falls_back_when_the_solver_has_no_values_for_the_hand(monkeypatch, weights, reason):
    hero = Player(0, "Hero", 1000.0, hole_cards=_cards("As", "Ah"), current_bet=0.0)
    villain = Player(1, "Villain", 940.0, current_bet=60.0)
    gs = GameState(
        players=[hero, villain],
        dealer_pos=0,
        street=Street.TURN,
        board=_cards("Kh", "7d", "2c", "9s"),
        pot=260.0,
        current_bet=60.0,
        big_blind=10.0,
        small_blind=5.0,
        player_positions={0: "BTN", 1: "BB"},
        action_history=[(1, Action(ActionType.RAISE, 60.0), "turn")],
    )

    def fake_solve(state, **_kwargs):
        return {
            "node": {
                "path": "r:Bet(60)",
                "player": 1,
                "actions": ["Fold", "Call"],
                "num_hands": 2,
                "strategy": [0.0, 0.5, 1.0, 0.5],
                "evs": [0.0, 0.0, 0.0, 0.0],
                "weights": weights,
            },
            "oop_hands": ["QcQd"],
            "ip_hands": ["AsAh", "KsKh"],
            "exploitability_pct": 0.42,
        }

    monkeypatch.setattr("pokerfate.decision.realtime_cfr.solve_realtime_cfr", fake_solve)
    engine = RealtimeCFRDecisionEngine(RealtimeCFROptions(timeout_sec=0.1))
    action = engine.decide(
        RealtimeCFRDecisionContext(
            gs=gs,
            hero_player_id=0,
            street_start_pot=200.0,
            range_provider=lambda player_id: _weights("QcQd") if player_id == 1 else _weights(),
        )
    )

    assert action is None
    assert engine.last_result["status"] == "fallback"
    assert engine.last_result["reason"] == reason
    assert engine.last_result["strategy"] == {"Fold": 0.0, "Call": 1.0}
    assert engine.last_hero_reach_update == {}
