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


def test_realtime_cfr_reasoning_includes_cec_summary():
    reasoning = PokerFateAPI._realtime_cfr_decision_reasoning({
        "selected_label": "Call",
        "selected_prob": 0.92,
        "exploitability_pct": 0.27,
        "elapsed_ms": 1100,
        "node_path": "r:AllIn(501)",
        "exploit": {
            "line_context": {
                "range_v2": {
                    "raw_bucket_dist": {
                        "nuts": 0.08,
                        "strong": 0.25,
                        "medium": 0.34,
                        "draw": 0.07,
                        "weak_draw": 0.06,
                        "air": 0.20,
                    },
                    "bucket_dist": {
                        "nuts": 0.10,
                        "strong": 0.21,
                        "medium": 0.30,
                        "draw": 0.09,
                        "weak_draw": 0.07,
                        "air": 0.23,
                    },
                    "cec_calibration": {
                        "used": True,
                        "level": "line",
                        "rows": 123,
                        "raw_reliability": 0.84,
                    },
                },
            },
        },
    })

    assert "cec=line n=123 rel=84%" in reasoning
    assert "N8/S25/M34/D7/W6/A20→N10/S21/M30/D9/W7/A23" in reasoning


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


def test_realtime_cfr_exploit_uses_response_evs_against_overfolder():
    result = {
        "node": {
            "path": "r",
            "player": 1,
            "actions": ["Check", "Bet(100)"],
            "num_hands": 1,
            "strategy": [0.70, 0.30],
            "evs": [100.0, 99.5],
        },
        "nodes": [
            {
                "path": "r",
                "player": 1,
                "actions": ["Check", "Bet(100)"],
                "num_hands": 1,
                "strategy": [0.70, 0.30],
                "evs": [100.0, 99.5],
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
        name="overfolder",
        hands_seen=240,
        flop_seen_count=80,
        vpip=0.24,
        pfr=0.18,
        af=1.4,
        fold_to_cbet=0.82,
        fold_to_cbet_opps=90,
        wtsd=0.16,
        turn_action_count=90,
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

    assert selection["selected_label"] == "Bet(100)"
    assert selection["exploit"]["used"] is True
    assert selection["exploit"]["confidence"] > 0.10
    assert (
        selection["exploit"]["adjusted_action_evs_bb"]["Bet(100)"]
        > selection["exploit"]["gto_action_evs_bb"]["Bet(100)"]
    )
    assert (
        selection["exploit"]["response_summaries"]["Bet(100)"]["adj"]["Fold"]
        > selection["exploit"]["response_summaries"]["Bet(100)"]["eq"]["Fold"]
    )


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


def test_realtime_cfr_defense_mdf_guard_keeps_close_call_available():
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
        defense_fold_cap=0.35,
    )

    assert selection["selected_label"] == "Call"
    assert selection["exploit"]["used"] is True
    assert selection["exploit"]["safety"]["defense_mdf"]["applied"] is True
    assert selection["exploit"]["final_strategy"]["Fold"] <= 0.35


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

    thin_prior = build_numeric_prior(thin, {}, "river", 10000)
    proven_prior = build_numeric_prior(proven, {}, "river", 10000)

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
    summary = selection["exploit"]["response_summaries"]["Bet(300)"]
    assert summary["adj"]["Fold"] < summary["eq"]["Fold"]
    assert selection["exploit"]["safety"]["river_aggression_risk"][0]["discount_bb"] > 0.0


def test_realtime_cfr_river_call_chain_keeps_value_big_bet():
    result = {
        "node": {
            "path": "r",
            "player": 1,
            "actions": ["Check", "Bet(300)"],
            "num_hands": 1,
            "strategy": [0.40, 0.60],
            "evs": [100.0, 170.0],
        },
        "nodes": [
            {
                "path": "r",
                "player": 1,
                "actions": ["Check", "Bet(300)"],
                "num_hands": 1,
                "strategy": [0.40, 0.60],
                "evs": [100.0, 170.0],
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
    )

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


def test_realtime_cfr_raise_exposure_penalizes_bet_fold_trap():
    result = {
        "node": {
            "path": "r",
            "player": 1,
            "actions": ["Check", "Bet(80)"],
            "num_hands": 1,
            "strategy": [0.05, 0.95],
            "evs": [50.0, 70.0],
        },
        "nodes": [
            {
                "path": "r",
                "player": 1,
                "actions": ["Check", "Bet(80)"],
                "num_hands": 1,
                "strategy": [0.05, 0.95],
                "evs": [50.0, 70.0],
            },
            {
                "path": "r:Bet(80)",
                "player": 0,
                "actions": ["Fold", "Call", "Raise(240)"],
                "num_hands": 1,
                "strategy": [0.35, 0.45, 0.20],
                "weights": [1.0],
                "opponent_num_hands": 1,
                "opponent_evs": [100.0, 55.0, -20.0],
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
        gto_strategy={"Check": 0.05, "Bet(80)": 0.95},
        profile=None,
        adjustments={},
        max_confidence=0.45,
        enabled=True,
        line_context={
            "street": "river",
            "board": ["Ks", "Qd", "8h", "8c", "2d"],
            "hero_combo": "AhAd",
            "current_pot_bb": 20.0,
            "hero_current_bet_bb": 0.0,
            "current_to_call_bb": 0.0,
            "effective_stack_bb": 100.0,
            "range_v2": {
                "bucket_dist": {
                    "nuts": 0.12,
                    "strong": 0.42,
                    "medium": 0.26,
                    "draw": 0.0,
                    "weak_draw": 0.0,
                    "air": 0.20,
                },
                "vs_hero": {"win": 0.41, "tie": 0.02, "loss": 0.57},
            },
        },
        hero_made_rank="one_pair",
    )

    assert selection["selected_label"] == "Check"
    risk = selection["exploit"]["safety"]["raise_exposure_risk"][0]
    assert risk["raise_mass"] >= 0.15
    assert risk["ev_gap_bb"] > 0.0
    assert selection["exploit"]["final_action_evs_bb"]["Bet(80)"] < selection["exploit"]["final_action_evs_bb"]["Check"]


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
