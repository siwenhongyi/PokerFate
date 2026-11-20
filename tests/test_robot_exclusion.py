"""House robots are played against but never learned from; at a table the bot would leave, nobody is."""

import json
from unittest.mock import Mock

from pokerfate.api import PlayerInfo, PokerFateAPI
from pokerfate.decision.g5_model import stable_player_name

HERO, HUMAN_ID, ROBOT_ID = 10262053, 10700890, 10334071


def _api(tmp_path) -> PokerFateAPI:
    return PokerFateAPI(
        my_player_id=HERO, big_blind=10000, small_blind=5000, autosave_path=None,
        log_file=str(tmp_path / "pf.log"), enable_showdown_calibration=True,
        decision_engine="local", g5_model_path=None,
    )


def _players(robots=1):
    return [
        PlayerInfo(HERO, "hero", 1_000_000, seat_index=0),
        PlayerInfo(HUMAN_ID, "human", 1_000_000, seat_index=1),
        *[PlayerInfo(ROBOT_ID + i, f"robot{i}", 1_000_000, seat_index=2 + i, is_robot=True) for i in range(robots)],
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


def test_calibration_predictions_follow_the_table_rule(tmp_path):
    api = _api(tmp_path)
    seen = []
    api._calibrator.record_prediction = lambda **kw: seen.append((kw["player_id"], kw.get("hero_eq_sample", True)))
    hook = api._bot._range_tracker._prediction_hook

    # A table the bot stays at (humans >= robots): the human is recorded and the robot is not;
    # while the robot is still in the pot the prediction is a training row but no hero-equity sample.
    api.new_hand(_players(), dealer_id=HERO, hand_number=1)
    assert not api._hand_skip_learning
    seen.clear()
    hook(player_id=ROBOT_ID, active_weights={})
    hook(player_id=HUMAN_ID, active_weights={HERO: 1, HUMAN_ID: 1, ROBOT_ID: 1})
    hook(player_id=HUMAN_ID, active_weights={HERO: 1, HUMAN_ID: 1})          # the robot has folded
    hook(player_id=HERO, active_weights={})
    assert seen == [(HUMAN_ID, False), (HUMAN_ID, True)]

    # A table it would leave: fewer humans than robots, or no human at all. Nothing is recorded.
    for players in (_players(robots=2), [_players()[0], _players()[2]]):
        seen.clear()
        api.new_hand(players, dealer_id=HERO, hand_number=2)
        assert api._hand_skip_learning
        hook(player_id=HUMAN_ID, active_weights={HERO: 1, HUMAN_ID: 1})
        assert seen == []

    # No robot: everything as usual (the tracker also predicts on its own when the hand starts).
    api.new_hand(_players(robots=0), dealer_id=HERO, hand_number=3)
    hook(player_id=HUMAN_ID, active_weights={HERO: 1, HUMAN_ID: 1})
    assert seen and {uid for uid, _ in seen} == {HUMAN_ID} and all(sample for _, sample in seen)


def test_a_prediction_made_with_a_robot_in_the_pot_is_no_hero_equity_sample():
    import numpy as np
    from pokerfate.calibration.showdown_calibration import ShowdownCalibrator
    from pokerfate.core.card import Card

    cards = lambda text: [Card.from_str(c) for c in text.split()]
    board, hero = cards("Ah 7d 2c Ks 9h"), cards("Ac Kd")
    weights = np.ones(1326)
    kept = {}
    for flag in (True, False):
        cal = ShowdownCalibrator(logger=None)
        cal.start_hand(1)
        cal.record_prediction(player_id=HUMAN_ID, player_name="human", street="river", board=board,
                              weights=weights, hero_cards=hero, trigger="action:bet",
                              active_weights={HUMAN_ID: weights, ROBOT_ID: weights}, hero_eq_sample=flag)
        kept[flag] = cal._hand_predictions[HUMAN_ID][-1]
    assert kept[True].predicted_hero_eq_multi is not None
    assert kept[False].predicted_hero_eq_multi is None                      # nothing to calibrate against
    assert kept[False].active_player_ids == kept[True].active_player_ids    # the row still says who was in
    assert kept[False].bucket_dist == kept[True].bucket_dist


def test_a_flagged_hero_is_never_treated_as_a_robot(tmp_path):
    api = _api(tmp_path)
    players = _players()
    players[0] = PlayerInfo(HERO, "hero", 1_000_000, seat_index=0, is_robot=True)
    api.new_hand(players, dealer_id=HERO, hand_number=1)
    assert HERO not in api._hand_robot_ids


def test_player_statistics_and_g5_profiles_follow_the_table_rule(tmp_path):
    api = _api(tmp_path)
    profiled = []
    api._g5_model_path = "unused"
    api._g5_action_model = Mock(record_hand=lambda **kw: profiled.append(set(kw["skip_names"])) and False)
    stats = api._bot.opponent_model

    api.new_hand(_players(robots=2), dealer_id=HERO, hand_number=1)          # outnumbered: leave
    assert stats.frozen
    stats.record_vpip(HUMAN_ID)
    stats.record_action(HUMAN_ID, "call", "flop")
    stats.record_showdown(HUMAN_ID, won=True)
    api._record_g5_action_model_hand()
    human = stats.get(HUMAN_ID)
    assert (human.hands_seen, human.vpip_count, human.showdown_count) == (0, 0, 0) and profiled == []

    api.new_hand(_players(), dealer_id=HERO, hand_number=2)                  # one human, one robot: stay
    assert not stats.frozen
    stats.record_vpip(HUMAN_ID)
    api._record_g5_action_model_hand()
    human = stats.get(HUMAN_ID)
    assert (human.hands_seen, human.vpip_count) == (1, 1)
    assert profiled == [{stable_player_name(ROBOT_ID)}]                      # the robot itself is not profiled


def test_a_replayed_hand_flags_robots_like_a_live_one(tmp_path):
    import pokerfate.core.robots as robots
    from scripts.replay_and_compare import _replay_hand

    for uid in (ROBOT_ID, ROBOT_ID + 5, ROBOT_ID + 10, ROBOT_ID + 15, ROBOT_ID + 20):
        robots.default_registry().confirm(uid, "robot", "test")
    seat = lambda uid, name: {"id": uid, "name": name, "stack": 1_000_000}
    hand = {"players": [seat(HERO, "hero"), seat(HUMAN_ID, "human"), seat(ROBOT_ID + 7, "robot")],   # unproven, in the block
            "dealer_id": HERO, "hole_cards": [], "events": []}
    api = _api(tmp_path)
    _replay_hand(api, hand, hero_id=HERO)
    assert api._hand_robot_ids == {ROBOT_ID + 7} and not api._hand_skip_learning
    hand["players"].append(seat(ROBOT_ID + 8, "robot2"))                     # now outnumbered
    _replay_hand(api, hand, hero_id=HERO)
    assert api._hand_skip_learning and api._bot.opponent_model.frozen


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


def test_training_row_extraction_uses_the_same_filter_as_live_play(tmp_path):
    from scripts.extract_range_calibration_rows_parallel import _attach_inline_calibrator

    api = _api(tmp_path)
    seen = []
    _attach_inline_calibrator(api, Mock(record_prediction=lambda **kw: seen.append(kw["player_id"])))
    hook = api._bot._range_tracker._prediction_hook
    api.new_hand(_players(robots=2), dealer_id=HERO, hand_number=1)          # a table the bot would leave
    hook(player_id=HUMAN_ID, active_weights={})
    assert seen == []
    api.new_hand(_players(), dealer_id=HERO, hand_number=2)
    seen.clear()
    for uid in (HUMAN_ID, ROBOT_ID, HERO):
        hook(player_id=uid, active_weights={})
    assert seen == [HUMAN_ID]
