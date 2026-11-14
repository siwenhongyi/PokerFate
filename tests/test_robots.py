"""Robot registry: labels are proven by the server's rb_num counter, never guessed."""

import json

from pokerfate.core.robots import HUMAN, ROBOT, SUSPECT, UNKNOWN, RobotRegistry, RoomRobotTracker, load_robot_uids

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


def test_enter_broadcast_counts_the_newcomer(tmp_path):
    reg, tr = _tracker(tmp_path, [ME, "A"])
    tr.entered("X", num=3, rb_num=1)        # first count: one robot among A, X
    tr.entered("Y", num=4, rb_num=2)        # rose -> Y robot
    tr.entered("Z", num=5, rb_num=2)        # unchanged -> Z human
    assert reg.label("Y") == ROBOT and reg.label("Z") == HUMAN
    tr.sat_down("Y")                        # sitting down after entering changes nothing
    assert tr.joined == set()


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


def test_blocks_make_unproven_neighbours_suspect(tmp_path):
    reg = RobotRegistry(tmp_path / "robots.json", autosave=False)
    for uid in (1000, 1010, 1100, 1300, 1650, 9000):
        reg.confirm(uid, ROBOT)
    assert reg.blocks() == [(1000, 1650, 5)]          # 9000 is alone: no block
    assert reg.status(1200) == SUSPECT and reg.is_robot(1200)
    assert not reg.is_robot(1200, include_suspect=False)
    assert reg.status(999) == UNKNOWN and reg.status(9001) == UNKNOWN
    assert reg.status(9000) == ROBOT
    reg.confirm(1200, HUMAN)                          # a proven human overrides the block for itself…
    assert reg.status(1200) == HUMAN and not reg.is_robot(1200)
    assert reg.blocks() == []                         # …and one human in six is too many to trust the block
    assert reg.status(1201) == UNKNOWN


def test_registry_round_trip_and_offline_loader(tmp_path):
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
    assert load_robot_uids(path, include_suspect_of=[507, 42, 900]) == {"500", "505", "510", "515", "520", "507"}


def test_composition_prefers_the_server_count(tmp_path):
    reg, tr = _tracker(tmp_path, [ME, "A", "B", "C"])
    # no count yet: only labels (nothing proven, nothing suspect) -> everybody counts as human
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
    rows = [{"player_uid": "505", "x": 1}, {"player_uid": "507", "x": 2},      # proven, suspect
            {"player_uid": "42", "x": 3}, {"player_uid": "", "x": 4}, {"x": 5}]  # human / no uid: kept
    kept, dropped = drop_robot_rows(rows, reg)
    assert dropped == 2 and [r["x"] for r in kept] == [3, 4, 5]
