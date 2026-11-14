"""House robots are played against but never learned from."""

import json

from pokerfate.api import ActionEvent, PlayerInfo, PokerFateAPI
from pokerfate.core.game_state import Action, ActionType
from pokerfate.decision.g5_model import G5ActionModel, stable_player_name

HERO, HUMAN_ID, ROBOT_ID = 10262053, 10700890, 10334071


def _api(tmp_path) -> PokerFateAPI:
    return PokerFateAPI(
        my_player_id=HERO, big_blind=10000, small_blind=5000, autosave_path=None,
        log_file=str(tmp_path / "pf.log"), enable_showdown_calibration=True,
        decision_engine="local", g5_model_path=None,
    )


def _players():
    return [
        PlayerInfo(HERO, "hero", 1_000_000, seat_index=0),
        PlayerInfo(HUMAN_ID, "human", 1_000_000, seat_index=1),
        PlayerInfo(ROBOT_ID, "robot", 1_000_000, seat_index=2, is_robot=True),
    ]


def test_hand_start_log_marks_robots_and_only_robots(tmp_path):
    api = _api(tmp_path)
    api.new_hand(_players(), dealer_id=HERO, hand_number=1)
    assert api._hand_robot_ids == {ROBOT_ID}
    rows = [json.loads(line) for line in (tmp_path / "pf.log").read_text(encoding="utf-8").splitlines()]
    start = next(r for r in rows if r.get("event") == "hand_start")
    flags = {p["id"]: p.get("robot", False) for p in start["players"]}
    assert flags == {HERO: False, HUMAN_ID: False, ROBOT_ID: True}
    # the flag is per hand: the next hand without the robot clears it
    api.new_hand(_players()[:2], dealer_id=HERO, hand_number=2)
    assert api._hand_robot_ids == set()


def test_no_calibration_prediction_is_recorded_about_a_robot(tmp_path):
    api = _api(tmp_path)
    seen = []
    api._calibrator.record_prediction = lambda **kw: seen.append(kw["player_id"])
    api.new_hand(_players(), dealer_id=HERO, hand_number=1)
    hook = api._bot._range_tracker._prediction_hook
    hook(player_id=ROBOT_ID, active_weights={})
    hook(player_id=HUMAN_ID, active_weights={HERO: 1, HUMAN_ID: 1, ROBOT_ID: 1})
    hook(player_id=HERO, active_weights={})
    # the tracker also predicts on its own (e.g. when the hand starts): only the human shows up
    assert seen and set(seen) == {HUMAN_ID}


def test_a_flagged_hero_is_never_treated_as_a_robot(tmp_path):
    api = _api(tmp_path)
    players = _players()
    players[0] = PlayerInfo(HERO, "hero", 1_000_000, seat_index=0, is_robot=True)
    api.new_hand(players, dealer_id=HERO, hand_number=1)
    assert HERO not in api._hand_robot_ids


def test_g5_model_does_not_profile_skipped_players():
    model = G5ActionModel()
    players = [
        {"player_id": pid, "name": stable_player_name(pid), "stack": 1_000_000.0, "position": pos,
         "seat_index": i}
        for i, (pid, pos) in enumerate(((HERO, "BTN"), (HUMAN_ID, "SB"), (ROBOT_ID, "BB")))
    ]
    history = [
        (HERO, Action(ActionType.RAISE, 30000), "preflop"),
        (HUMAN_ID, Action(ActionType.CALL, 25000), "preflop"),
        (ROBOT_ID, Action(ActionType.FOLD), "preflop"),
    ]
    assert model.record_hand(players=players, dealer_id=HERO, action_history=history,
                             big_blind=10000, small_blind=5000,
                             skip_names={stable_player_name(ROBOT_ID)})
    names = set(model.players)
    assert stable_player_name(HUMAN_ID) in names and stable_player_name(HERO) in names
    assert stable_player_name(ROBOT_ID) not in names


def test_cfr_opponent_prior_library_leaves_robots_out(tmp_path, monkeypatch):
    """Pool rates and nearest neighbours of the CFR opponent prior come from humans only."""
    import pokerfate.core.robots as robots
    import pokerfate.decision.opponent_numeric_prior as onp

    def stats(hands, vpip, fold_cbet):
        return {"hands_seen": hands, "vpip_count": int(hands * vpip), "pfr_count": int(hands * 0.1),
                "fold_to_cbet_count": int(40 * fold_cbet), "fold_to_cbet_opps": 40,
                "flop_seen_count": hands // 2, "showdown_count": hands // 6}

    humans = {str(20000000 + i): {"name": f"h{i}", "stats": stats(200, 0.30, 0.40)} for i in range(6)}
    bots = {str(uid): {"name": f"r{uid}", "stats": stats(200, 0.90, 0.95)} for uid in (500, 505, 510, 515, 520)}
    suspect = {"507": {"name": "r507", "stats": stats(200, 0.90, 0.95)}}        # unproven, inside the block
    (tmp_path / onp.OPPONENT_MODEL_FILE).write_text(
        json.dumps({"players": {**humans, **bots, **suspect}}), encoding="utf-8")
    monkeypatch.setattr(onp, "MODEL_DIR", tmp_path)
    for uid in bots:
        robots.default_registry().confirm(uid, "robot", "test")

    onp._load_model.cache_clear()
    try:
        model = onp._load_model()
        assert model.player_count == 6
        assert abs(model.pool["vpip"] - 0.30) < 1e-9 and abs(model.pool["fold_to_cbet"] - 0.40) < 1e-9
    finally:
        onp._load_model.cache_clear()
