import pytest

from pokerfate.core.game_state import ActionType, GameState, Player, Street
from pokerfate.decision.g5_model import G5ActionModel
from pokerfate.decision.g5_engine import DecisionEngineError, G5EngineOptions, G5JsonDecisionEngine
from scripts.g5_json_worker import G5Worker


def _engine() -> G5JsonDecisionEngine:
    return G5JsonDecisionEngine(G5EngineOptions(worker_cmd="unused-worker"))


def _state(*, current_bet: float, hero_bet: float, hero_stack: float = 100.0) -> GameState:
    return GameState(
        players=[
            Player(0, "Hero", hero_stack, current_bet=hero_bet),
            Player(1, "Villain", 100.0, current_bet=current_bet),
        ],
        street=Street.PREFLOP,
        current_bet=current_bet,
    )


def test_g5_raise_by_amount_converts_to_total_street_bet():
    action = _engine()._action_from_result(
        {"actionType": 4, "byAmount": 10},
        gs=_state(current_bet=2, hero_bet=2),
        hero_player_id=0,
        my_current_bet_this_street=2,
    )

    assert action.action_type == ActionType.RAISE
    assert action.amount == 12


def test_g5_raise_ignores_total_hand_money_in_pot_for_street_bet():
    action = _engine()._action_from_result(
        {"action": "Raise", "byAmount": 20, "heroMoneyInPot": 130},
        gs=_state(current_bet=0, hero_bet=0),
        hero_player_id=0,
        my_current_bet_this_street=0,
    )

    assert action.action_type == ActionType.RAISE
    assert action.amount == 20


def test_g5_raise_adds_by_amount_to_current_street_bet_only():
    action = _engine()._action_from_result(
        {"action": "Raise", "byAmount": 30, "heroMoneyInPot": 105},
        gs=_state(current_bet=10, hero_bet=5),
        hero_player_id=0,
        my_current_bet_this_street=5,
    )

    assert action.action_type == ActionType.RAISE
    assert action.amount == 35


def test_g5_fold_with_no_call_is_check():
    action = _engine()._action_from_result(
        {"action": "Fold", "byAmount": 0},
        gs=_state(current_bet=0, hero_bet=0),
        hero_player_id=0,
        my_current_bet_this_street=0,
    )

    assert action.action_type == ActionType.CHECK


def test_g5_action_conversion_trusts_server_to_call_over_g5_amount_to_call():
    action = _engine()._action_from_result(
        {"action": "Fold", "byAmount": 0, "amountToCall": 10},
        gs=_state(current_bet=10, hero_bet=10),
        hero_player_id=0,
        my_current_bet_this_street=10,
    )

    assert action.action_type == ActionType.CHECK


def test_g5_raise_not_above_current_bet_degrades_to_call():
    action = _engine()._action_from_result(
        {"action": "Raise", "byAmount": 1},
        gs=_state(current_bet=10, hero_bet=2),
        hero_player_id=0,
        my_current_bet_this_street=2,
    )

    assert action.action_type == ActionType.CALL


def test_g5_close_forgets_created_game_signature():
    engine = _engine()
    engine._created_signature = (("same-table"),)

    engine.close()

    assert engine._created_signature is None


def test_g5_start_hand_seeds_stats_before_start_hand(tmp_path):
    model_path = tmp_path / "g5_stats.json"
    model = G5ActionModel()
    stats = model.get_or_create("uid:1", display_name="Villain")
    stats.vpip_positive = 4
    stats.vpip_total = 10
    model.save(model_path)

    calls = []

    class FakeEngine(G5JsonDecisionEngine):
        def _rpc(self, method, params, *, timeout_sec=None):
            calls.append((method, params))
            if method == "create_game":
                return {"ok": True}
            if method == "seed_player_stats":
                return {"seeded": len(params["players"])}
            if method == "start_hand":
                return {"player_to_act": 0}
            return {}

    engine = FakeEngine(G5EngineOptions(worker_cmd="unused", model_file=str(model_path)))
    engine.start_hand(
        players=[
            Player(0, "Hero", 100),
            Player(1, "Villain", 100),
            Player(2, "Other", 100),
        ],
        dealer_id=2,
        hand_number=7,
        hero_player_id=0,
        big_blind=10,
        small_blind=5,
    )

    methods = [method for method, _ in calls]
    assert methods == ["create_game", "seed_player_stats", "start_hand"]
    seed = calls[1][1]["players"]
    assert seed[0]["name"] == "uid:1"
    assert seed[0]["vpip_positive"] == 4


def test_g5_start_hand_preserves_physical_seats_with_sitting_out_placeholders():
    calls = []

    class FakeEngine(G5JsonDecisionEngine):
        def _rpc(self, method, params, *, timeout_sec=None):
            calls.append((method, params))
            if method == "start_hand":
                return {"player_to_act": 0}
            return {}

    engine = FakeEngine(G5EngineOptions(worker_cmd="unused"))
    engine.start_hand(
        players=[
            Player(100, "Hero", 100),
            Player(200, "Villain", 100),
            Player(500, "Button", 100),
        ],
        dealer_id=500,
        seat_indices={100: 0, 200: 2, 500: 5},
        dealer_seat_index=5,
        hand_number=8,
        hero_player_id=100,
        big_blind=10,
        small_blind=5,
    )

    create_params = calls[0][1]
    start_params = calls[1][1]
    assert [p["player_id"] for p in create_params["players"]] == [100, -2, 200, -4, -5, 500]
    assert [p["display_name"] for p in create_params["players"]] == [
        "Hero",
        "seat:1",
        "Villain",
        "seat:3",
        "seat:4",
        "Button",
    ]
    assert create_params["hero_index"] == 0
    assert create_params["button_index"] == 5
    assert start_params["sitting_out_indices"] == [1, 3, 4]


def test_g5_worker_unexpected_exit_disables_respawn_loop():
    class DeadProc:
        def poll(self):
            return -10

    engine = _engine()
    engine._proc = DeadProc()

    with pytest.raises(Exception) as exc:
        engine._ensure_process()

    assert "disabling g5" in str(exc.value)
    assert engine._worker_disabled_reason


def test_g5_worker_timeout_disables_respawn_loop():
    engine = _engine()
    reason = engine._disable_worker("g5 worker timeout on decide", method="decide")

    assert "disabling g5" in reason
    with pytest.raises(DecisionEngineError):
        engine._ensure_process()


def test_g5_worker_normalizes_range_keys_to_169_categories():
    assert G5Worker._normalize_range_key("AceKingo") == "AKo"
    assert G5Worker._normalize_range_key("KingAces") == "AKs"
    assert G5Worker._normalize_range_key("TenTen") == "TT"

    normalized = G5Worker._normalize_range_map({
        "AceKingo": 2,
        "KingAces": 1,
        "TenTen": 1,
        "bad": 99,
    })

    assert normalized == {"AKo": 0.5, "AKs": 0.25, "TT": 0.25}


def test_g5_engine_maps_worker_ranges_by_player_id():
    engine = _engine()
    engine._player_ids = [10, 20]

    result = engine._with_player_id_ranges({
        "ranges": [
            {"player_index": 0, "range_169": {"AA": 1.0}},
            {"player_index": 1, "range_169": {"AKo": 0.25}},
        ],
    })

    assert result["ranges_by_player_id"] == {
        "10": {"AA": 1.0},
        "20": {"AKo": 0.25},
    }
