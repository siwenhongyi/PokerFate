import json

from pf_intercept.robot.tracker import RobotTracker


def test_robot_tracker_does_not_mark_self_uid(tmp_path):
    tracker = RobotTracker(tmp_path)
    tracker.set_self_uid("99")

    tracker.observe(
        "pb.OtherEnterRoomBRC",
        {"user": {"uid": "88", "name": "first"}, "rb_num": 1},
        room_id=1,
        observed_at="2026-05-23T00:00:00+08:00",
    )
    tracker.observe(
        "pb.OtherEnterRoomBRC",
        {"user": {"uid": "99", "name": "me"}, "rb_num": 2},
        room_id=1,
        observed_at="2026-05-23T00:00:01+08:00",
    )

    summary_path = tmp_path / "robot_players.json"
    data = json.loads(summary_path.read_text(encoding="utf-8")) if summary_path.exists() else {"robots": {}}
    assert "99" not in data.get("robots", {})


def test_robot_tracker_does_not_mark_robot_from_enter_increase(tmp_path):
    tracker = RobotTracker(tmp_path)

    tracker.observe(
        "pb.OtherEnterRoomBRC",
        {"user": {"uid": "88", "name": "first"}, "rb_num": 1},
        room_id=1,
        observed_at="2026-05-23T00:00:00+08:00",
    )
    tracker.observe(
        "pb.OtherEnterRoomBRC",
        {"user": {"uid": "77", "name": "second"}, "rb_num": 2},
        room_id=1,
        observed_at="2026-05-23T00:00:01+08:00",
    )

    summary_path = tmp_path / "robot_players.json"
    data = json.loads(summary_path.read_text(encoding="utf-8")) if summary_path.exists() else {"robots": {}}
    assert data.get("robots", {}) == {}

    events = [
        json.loads(line)
        for line in (tmp_path / "robot_events.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert events[-1]["inference"] == "rb_count_increased_on_enter"


def test_robot_tracker_marks_robot_from_leave_decrease(tmp_path):
    tracker = RobotTracker(tmp_path)

    tracker.observe(
        "pb.OtherEnterRoomBRC",
        {"user": {"uid": "88", "name": "first"}, "rb_num": 1},
        room_id=1,
        observed_at="2026-05-23T00:00:00+08:00",
    )
    tracker.observe(
        "pb.SitDownBRC",
        {"status": {"seatid": 2, "player": {"uid": "88", "name": "first"}}},
        room_id=1,
        observed_at="2026-05-23T00:00:01+08:00",
    )
    tracker.observe(
        "pb.OtherLeaveRoomBRC",
        {"uid": "88", "rb_num": 0},
        room_id=1,
        observed_at="2026-05-23T00:00:02+08:00",
    )

    data = json.loads((tmp_path / "robot_players.json").read_text(encoding="utf-8"))
    assert set(data.get("robots", {})) == {"88"}
    assert data["robots"]["88"]["evidence"][0]["event"] == "leave"


def test_robot_tracker_purges_self_uid_from_existing_summary(tmp_path):
    summary_path = tmp_path / "robot_players.json"
    summary_path.write_text(
        json.dumps(
            {"robots": {"99": {"uid": "99", "name": "me", "evidence_count": 1}}},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    tracker = RobotTracker(tmp_path)
    tracker.set_self_uid("99")

    data = json.loads(summary_path.read_text(encoding="utf-8"))
    assert "99" not in data.get("robots", {})
