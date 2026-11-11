from pathlib import Path
import threading

from pokerfate.core.game_state import Action, ActionType
from pokerfate.decision.g5_model import G5ActionModel, stable_player_name


def test_background_checkpoint_is_frozen_coalesced_and_flushed(tmp_path, monkeypatch):
    model = G5ActionModel()
    a = model.get_or_create("uid:1")
    b = model.get_or_create("uid:2")
    a.vpip_total = 1
    entered, release = threading.Event(), threading.Event()
    writes = []
    original = model._write_checkpoint

    def blocked_write(path, header, players):
        writes.append(players)
        entered.set()
        assert release.wait(5)
        original(path, header, players)

    monkeypatch.setattr(model, "_write_checkpoint", blocked_write)
    path = tmp_path / "g5.json"
    model.save_async(path)
    try:
        assert entered.wait(2)
        a.vpip_total = 2
        model.save_async(path, player_names=["uid:1"])
        b.vpip_positive = 3
        b.preflop[9].br = 7
        model.save_async(path, player_names=["uid:2"])
        # A later mutation must not leak into the accepted snapshot.
        a.vpip_total = 999
        assert len(writes) == 1
    finally:
        release.set()
        model.close_writer()
    loaded = G5ActionModel.load(path)
    assert len(writes) == 2
    assert loaded.players["uid:1"].vpip_total == 2
    assert loaded.players["uid:2"].vpip_positive == 3
    assert loaded.players["uid:2"].preflop[9].br == 7


def test_background_update_does_not_reserialize_unchanged_players(tmp_path, monkeypatch):
    path = tmp_path / "g5.json"
    original = G5ActionModel()
    original.get_or_create("uid:1").vpip_total = 20
    original.get_or_create("uid:2").vpip_total = 40
    original.save(path)
    loaded = G5ActionModel.load(path, prepare_save_cache=True)
    def unexpected():
        raise AssertionError("unchanged historical player serialized in live handler")
    monkeypatch.setattr(loaded.players["uid:2"], "to_json", unexpected)
    loaded.players["uid:1"].vpip_total = 21
    loaded.save_async(path, player_names=["uid:1"])
    loaded.close_writer()
    saved = G5ActionModel.load(path)
    assert saved.players["uid:1"].vpip_total == 21
    assert saved.players["uid:2"].vpip_total == 40


def test_background_checkpoint_failure_keeps_previous_file(tmp_path, monkeypatch):
    path = tmp_path / "g5.json"
    model = G5ActionModel()
    model.get_or_create("uid:1").vpip_total = 20
    model.save(path)
    before = path.read_bytes()
    def fail(*args):
        raise OSError("test disk failure")
    errors = []
    monkeypatch.setattr(model, "_write_checkpoint", fail)
    model.save_async(path, on_saved=lambda error, ms: errors.append(error))
    model.close_writer()
    assert errors == ["test disk failure"]
    assert path.read_bytes() == before


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
