from pathlib import Path

from pokerfate.core.game_state import Action, ActionType
from pokerfate.decision.g5_model import G5ActionModel, stable_player_name


def _players():
    # Physical order with dealer at the last player produces g5 hand order:
    # SB, BB, UTG, HJ, CutOff, Button.
    return [
        {"player_id": 1, "name": "SB", "stack": 1000},
        {"player_id": 2, "name": "BB", "stack": 1000},
        {"player_id": 3, "name": "UTG", "stack": 1000},
        {"player_id": 4, "name": "HJ", "stack": 1000},
        {"player_id": 5, "name": "CO", "stack": 1000},
        {"player_id": 6, "name": "BTN", "stack": 1000},
    ]


def test_g5_model_records_preflop_context_indices_one_to_one():
    model = G5ActionModel()

    model.record_hand(
        players=_players(),
        dealer_id=6,
        big_blind=10,
        small_blind=5,
        action_history=[
            (3, Action(ActionType.RAISE, 30), "preflop"),
            (4, Action(ActionType.CALL, 30), "preflop"),
            (5, Action(ActionType.FOLD, 0), "preflop"),
            (6, Action(ActionType.CALL, 30), "preflop"),
            (1, Action(ActionType.FOLD, 0), "preflop"),
            (2, Action(ActionType.CALL, 30), "preflop"),
        ],
    )

    utg = model.players[stable_player_name(3)]
    hj = model.players[stable_player_name(4)]
    co = model.players[stable_player_name(5)]
    btn = model.players[stable_player_name(6)]

    assert utg.vpip_positive == 1
    assert utg.vpip_total == 1
    assert utg.preflop[10].br == 1  # UTG, no limpers, no raises
    assert hj.preflop[17].cc == 1   # HJ facing one raise, no callers
    assert co.preflop[23].fold == 1 # CO facing one raise plus caller
    assert btn.preflop[28].cc == 1  # BTN facing one raise plus caller


def test_g5_model_persists_and_exports_seed_payload(tmp_path: Path):
    path = tmp_path / "g5_stats.json"
    model = G5ActionModel()
    stats = model.get_or_create("uid:42", display_name="Villain")
    stats.vpip_positive = 3
    stats.vpip_total = 10
    stats.postflop[0].cc = 2
    model.save(path)

    loaded = G5ActionModel.load(path)
    payload = loaded.seed_payload_for(["uid:42", "uid:99"], table_type="SixMax")

    assert len(payload) == 1
    assert payload[0]["name"] == "uid:42"
    assert payload[0]["vpip_positive"] == 3
    assert payload[0]["vpip_total"] == 10
    assert payload[0]["postflop"][0]["cc"] == 2
