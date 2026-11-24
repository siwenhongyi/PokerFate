"""Robot registry: labels are proven by the server's rb_num counter, never guessed."""

import json

from pokerfate.core.robots import HUMAN, ROBOT, UNKNOWN, RobotRegistry, RoomRobotTracker

ME = "10262053"


def _tracker(tmp_path, seats=()):
    reg = RobotRegistry(tmp_path / "robots.json", autosave=False)
    tr = RoomRobotTracker(reg, ME)
    tr.reset(seats)
    return reg, tr


def test_count_rule_last_opponent_is_the_robot(tmp_path):
    # The situation the first report used: somebody leaves, 2 people remain, 1 of them a robot.
    reg, tr = _tracker(tmp_path, [ME, "A", "B"])
    tr.left("B", num=2, rb_num=1)
    assert reg.label("A") == ROBOT
    assert reg.label("B") is None           # nothing proves what the leaver was


def test_count_rule_zero_robots_means_everybody_is_human(tmp_path):
    reg, tr = _tracker(tmp_path, [ME, "A", "B", "C"])
    tr.left("C", num=3, rb_num=0)
    assert reg.label("A") == HUMAN and reg.label("B") == HUMAN


def test_change_rule_on_leave(tmp_path):
    reg, tr = _tracker(tmp_path, [ME, "A", "B", "C"])
    tr.left("C", num=3, rb_num=1)           # one robot among A, B: undecided
    assert reg.label("A") is None and reg.label("B") is None
    tr.left("A", num=2, rb_num=0)           # counter fell when A left -> A was the robot
    assert reg.label("A") == ROBOT
    assert reg.label("B") == HUMAN


def test_change_rule_counter_unchanged_on_leave_is_human(tmp_path):
    reg, tr = _tracker(tmp_path, [ME, "A", "B", "C"])
    tr.left("C", num=3, rb_num=1)
    tr.left("A", num=2, rb_num=1)           # unchanged -> A human, and B is the remaining robot
    assert reg.label("A") == HUMAN
    assert reg.label("B") == ROBOT


def test_change_rule_on_join_between_two_counts(tmp_path):
    reg, tr = _tracker(tmp_path, [ME, "A", "B"])
    tr.left("B", num=2, rb_num=1)           # A robot
    tr.sat_down("C")
    tr.sat_down("D")
    tr.left("A", num=3, rb_num=1)           # A (robot) left, counter still 1 -> one robot among C, D
    assert reg.label("C") is None and reg.label("D") is None
    tr.sat_down("E")
    tr.left("C", num=3, rb_num=2)           # E joined, C left, counter rose: E robot and C human
    assert reg.label("E") == ROBOT and reg.label("C") == HUMAN
    assert reg.label("D") == ROBOT          # 2 robots among D, E


def test_entering_is_judged_at_the_next_count(tmp_path):
    reg, tr = _tracker(tmp_path, [ME, "A", "B"])
    tr.left("B", num=2, rb_num=0)           # A human
    tr.entered("X")                         # the enter broadcast carries no robot count
    tr.sat_down("X")                        # sitting down after entering changes nothing
    assert reg.label("X") is None and tr.joined == {"X"} and tr.events == 1
    tr.left("A", num=2, rb_num=1)           # X joined, A (human) left, counter rose -> X robot
    assert reg.label("X") == ROBOT


def test_count_that_the_labels_cannot_explain_is_reported(tmp_path):
    seen = []
    reg = RobotRegistry(tmp_path / "robots.json", autosave=False)
    tr = RoomRobotTracker(reg, ME, on_mismatch=lambda members, rb_num: seen.append((members, rb_num)))
    reg.confirm("A", HUMAN)
    reg.confirm("B", HUMAN)
    tr.reset([ME, "A", "B", "C"])
    tr.left("C", num=3, rb_num=1)           # one robot among two accounts labelled human
    assert seen == [(["A", "B"], 1)] and tr.mismatches == 1
    assert reg.label("A") == HUMAN and reg.label("B") == HUMAN


def test_no_inference_when_people_are_unaccounted_for(tmp_path):
    reg, tr = _tracker(tmp_path, [ME, "A", "B"])
    tr.left("B", num=4, rb_num=1)           # two people in the room we never saw
    assert reg.counts() == {"robot": 0, "human": 0, "conflict": 0}
    assert tr.skipped == 1
    tr.left("A", num=1, rb_num=0)           # consistent again, but the base count was lost
    assert reg.label("A") is None


def test_conflicting_proofs_cancel_out(tmp_path):
    reg = RobotRegistry(tmp_path / "robots.json", autosave=False)
    assert reg.confirm("7", ROBOT, "x") is True
    assert reg.confirm("7", ROBOT, "x") is False
    assert reg.confirm("7", HUMAN, "y") is True
    assert reg.label("7") is None
    assert reg.counts()["conflict"] == 1
    assert reg.confirm("7", ROBOT, "x") is False     # stays a conflict


def test_only_a_proven_uid_is_a_robot(tmp_path):
    reg = RobotRegistry(tmp_path / "robots.json", autosave=False)
    for uid in (1000, 1010, 1100, 1300, 1650):
        reg.confirm(uid, ROBOT)
    reg.confirm(1200, HUMAN)
    assert reg.is_robot(1010) and reg.status(1010) == ROBOT
    assert not reg.is_robot(1200) and reg.status(1200) == HUMAN
    assert not reg.is_robot(1005) and reg.status(1005) == UNKNOWN     # between proven robots, proven nothing


def test_registry_round_trip(tmp_path):
    path = tmp_path / "robots.json"
    reg = RobotRegistry(path, autosave=False)
    for uid in (500, 505, 510, 515, 520):
        reg.confirm(uid, ROBOT, "rb_num rose on join", ts=1.0)
    reg.confirm(42, HUMAN, "room robot count", ts=2.0)
    reg.save(force=True)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["counts"] == {"robot": 5, "human": 1, "conflict": 0}
    again = RobotRegistry(path, autosave=False)
    assert again.robots() == {"500", "505", "510", "515", "520"} and again.humans() == {"42"}


def test_composition_prefers_the_server_count(tmp_path):
    reg, tr = _tracker(tmp_path, [ME, "A", "B", "C"])
    # no count yet: only labels (nothing proven) -> everybody counts as human
    assert tr.composition(tr.members) == {"humans": 3, "robots": 0, "total": 3, "source": "labels", "unproven": 3}
    tr.left("C", num=3, rb_num=1)
    comp = tr.composition(tr.members)
    assert (comp["humans"], comp["robots"], comp["source"]) == (1, 1, "rb_num")
    tr.sat_down("D")                         # somebody new: the count is stale, fall back to labels
    assert tr.composition(tr.members)["source"] == "labels"


def test_training_rows_about_robots_are_dropped(tmp_path):
    from scripts.range_calibration_meta import drop_robot_rows

    reg = RobotRegistry(tmp_path / "robots.json", autosave=False)
    for uid in (500, 505, 510, 515, 520):
        reg.confirm(uid, ROBOT)
    rows = [{"player_uid": "505", "x": 1}, {"player_uid": "507", "x": 2},      # proven robot / not proven: kept
            {"player_uid": "42", "x": 3}, {"player_uid": "", "x": 4}, {"x": 5}]  # human / no uid: kept
    kept, dropped = drop_robot_rows(rows, reg)
    assert dropped == 1 and [r["x"] for r in kept] == [2, 3, 4, 5]


def test_learning_uses_the_table_rule():
    from pf_intercept.table_policy import verdict
    from pokerfate.core.robots import table_verdict

    assert verdict is table_verdict
    assert [table_verdict(h, r) for h, r in ((0, 0), (0, 2), (1, 2), (2, 2), (3, 1), (2, 0))] == [
        "empty", "no_humans", "outnumbered", "stay", "stay", "stay"]
