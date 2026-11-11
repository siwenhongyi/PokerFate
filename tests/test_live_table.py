import pytest

from pf_entertainment.live_table import LiveTableObserver


def test_hero_leave_clears_table_and_reenter_replaces_snapshot(observer):
    observer.set_connected(True)
    observer.observe("pb.HandCardRSP", {"card1": 1037, "card2": 267})
    observer.observe("pb.ActionNotifyBRC", {"seatid": 0})
    observer.observe("pb.LeaveRoomRSP", {"roomid": 21205174})
    snapshot = observer.snapshot()
    assert snapshot["connected"] is True
    assert snapshot["room_id"] == 0
    assert snapshot["my_seat"] is None and snapshot["action_seat"] is None
    assert snapshot["board"] == snapshot["my_hole"] == []
    assert snapshot["pot"] == 0
    assert all(s["empty"] and not s.get("acting") for s in snapshot["seats"])
    observer.observe("pb.EnterRoomRSP", {
        "roomid": 123, "table_status": {"seat": [
            {"seatid": 2, "player": {"uid": "10262053", "name": "Hero"}, "hand_chips": "1000000"},
        ]},
    })
    snapshot = observer.snapshot()
    assert snapshot["room_id"] == 123 and snapshot["my_seat"] == 2
    assert all(s["empty"] for s in snapshot["seats"] if s["seatid"] != 2)


@pytest.mark.parametrize("msg", [{"code": 121}, {"roomid": 9999}])
def test_failed_or_other_room_leave_keeps_table(observer, msg):
    before = observer.snapshot()
    observer.observe("pb.LeaveRoomRSP", msg)
    after = observer.snapshot()
    assert after["room_id"] == before["room_id"]
    assert after["seats"] == before["seats"]


def test_reconnect_status_retains_snapshot_until_authoritative_lobby(observer):
    observer.observe("pb.ActionNotifyBRC", {"seatid": 0})
    observer.set_connection_status("reconnecting")
    snap = observer.snapshot()
    assert not snap["connected"] and snap["connection_status"] == "reconnecting"
    assert snap["room_id"] == 21205174
    assert snap["action_seat"] is None
    observer.observe("pb.UserLocationRSP", {})
    assert observer.snapshot()["room_id"] == 0
    assert all(s["empty"] for s in observer.snapshot()["seats"])


@pytest.fixture
def observer():
    obs = LiveTableObserver(my_uid=10262053)
    obs.observe("pb.EnterRoomRSP", {
        "roomid": 21205174,
        "table_status": {"seat": [
            {"player": {"uid": "10262053", "name": "Hero"},
             "hand_chips": "1000000"},
            {"seatid": 3, "player": {"uid": "10689400", "name": "Opponent"},
             "hand_chips": "500000"},
        ]},
    })
    return obs


@pytest.mark.parametrize("uid", ["10689400", 10689400])
def test_other_player_leave_preserves_hero_and_clears_matching_seat(observer, uid):
    # Actual wire message: OtherLeaveRoomBRC has no seatid field in its schema.
    hero = observer.snapshot()["seats"][0]
    observer.observe("pb.OtherLeaveRoomBRC", {
        "uid": uid, "num": 5, "roomid": 21205174,
    })
    seats = observer.snapshot()["seats"]
    assert seats[0] == hero
    assert seats[3]["empty"] is True
    assert seats[3]["uid"] == ""
    assert seats[3]["stack"] == 0

    observer.observe("pb.DealerInfoRSP", {"start_info": [{"chips": "951450"}]})
    observer.observe("pb.ActionBRC", {
        "action_type": 3, "chips": "40000", "hand_chips": "911450",
    })
    hero = observer.snapshot()["seats"][0]
    assert hero["is_me"] is True
    assert hero["empty"] is False
    assert hero["name"] == "Hero"
    assert hero["stack"] == 911450


def test_uid_leave_can_clear_seat_zero(observer):
    other = observer.snapshot()["seats"][3]
    observer.observe("pb.OtherLeaveRoomBRC", {"uid": "10262053"})
    seats = observer.snapshot()["seats"]
    assert seats[0]["empty"] is True
    assert seats[3] == other


@pytest.mark.parametrize("message", [
    {}, {"uid": "unknown"}, {"uid": "unknown", "seatid": 0},
    {"seatid": None}, {"seatid": "invalid"}, {"seatid": -1},
])
def test_unidentified_leave_does_not_clear_any_seat(observer, message):
    seats = observer.snapshot()["seats"]
    observer.observe("pb.OtherLeaveRoomBRC", message)
    assert observer.snapshot()["seats"] == seats


def test_explicit_seat_leave_still_clears_seat_zero(observer):
    observer.observe("pb.LeaveRoomBRC", {"seatid": 0})
    assert observer.snapshot()["seats"][0]["empty"] is True


@pytest.mark.parametrize("action_type", [17, 3, 8])
def test_action_with_omitted_zero_remaining_chips_clears_stack(observer, action_type):
    # Going all-in can also be encoded as a call or a forced blind.
    observer.observe("pb.ActionBRC", {"action_type": action_type, "chips": "1000000"})
    assert observer.snapshot()["seats"][0]["stack"] == 0


@pytest.mark.parametrize("pool,expected", [
    (["810000"], 810000), (["600000", "210000"], 810000), ([], 0),
])
def test_round_over_uses_server_pots_after_uncalled_bet_return(observer, pool, expected):
    observer.observe("pb.ActionBRC", {
        "action_type": 7, "chips": "2397700", "hand_chips": "10000",
    })
    observer.observe("pb.RoundOverBRC", {"pool": pool})
    snap = observer.snapshot()
    assert snap["pot"] == expected
    assert snap["seats"][0]["bet"] == 0
    observer.observe("pb.RoundStartBRC", {"stage": 4})
    observer.observe("pb.ActionBRC", {
        "seatid": 3, "action_type": 7, "chips": "10000", "hand_chips": "490000",
    })
    assert observer.snapshot()["pot"] == expected + 10000


def test_round_over_without_pool_does_not_erase_known_pot(observer):
    observer.observe("pb.ActionBRC", {
        "action_type": 7, "chips": "10000", "hand_chips": "990000",
    })
    observer.observe("pb.RoundOverBRC", {})
    assert observer.snapshot()["pot"] == 10000


def test_winner_updates_stacks_with_net_profit_including_refund_and_rake(observer):
    observer.observe("pb.DealerInfoRSP", {"start_info": [
        {"chips": "1000000"}, {"seatid": 3, "chips": "500000"},
    ]})
    observer.observe("pb.ActionBRC", {"action_type": 17, "chips": "1000000"})
    observer.observe("pb.ActionBRC", {
        "seatid": 3, "action_type": 3, "chips": "400000", "hand_chips": "100000",
    })
    observer.observe("pb.RoundOverBRC", {"pool": ["800000"]})
    result = {
        "winner": [{"uid": "10262053", "chips": "728000"}],
        "profit": [
            {"uid": "10262053", "chips": "328000"},
            {"seatid": 3, "uid": "10689400", "chips": "-400000"},
        ],
    }
    observer.observe("pb.WinnerRSP", result)
    snap = observer.snapshot()
    assert snap["seats"][0]["stack"] == 1328000
    assert snap["seats"][3]["stack"] == 100000
    # Repeated settlement must not pay out twice.
    observer.observe("pb.WinnerRSP", result)
    assert observer.snapshot()["seats"] == snap["seats"]

    observer.observe("pb.DealerInfoRSP", {"start_info": [{"chips": "1328000"}]})
    observer.observe("pb.ActionBRC", {
        "action_type": 8, "chips": "5000", "hand_chips": "1323000",
    })
    observer.observe("pb.WinnerRSP", {"profit": [{"uid": "10262053", "chips": "-5000"}]})
    assert observer.snapshot()["seats"][0]["stack"] == 1323000


@pytest.mark.parametrize("profit", ["200000", None])
def test_midhand_entry_uses_begin_chips_for_settlement(observer, profit):
    observer.observe("pb.EnterRoomRSP", {"roomid": 2, "table_status": {"seat": [
        {"seatid": 3, "player": {"uid": "10689400", "name": "Opponent"},
         "hand_chips": "300000", "begin_chips": "500000"},
    ]}})
    entry = {"uid": "10689400"}  # Resolve identity even without seatid.
    if profit is not None:
        entry["chips"] = profit
    observer.observe("pb.WinnerRSP", {"profit": [entry]})
    assert observer.snapshot()["seats"][3]["stack"] == 500000 + int(profit or 0)


def test_settlement_does_not_apply_old_players_baseline_to_new_occupant(observer):
    observer.observe("pb.DealerInfoRSP", {"start_info": [{"chips": "1000000"}]})
    observer.observe("pb.OtherLeaveRoomBRC", {"uid": "10262053"})
    observer.observe("pb.SitDownBRC", {"status": {
        "player": {"uid": "999", "name": "New player"}, "hand_chips": "200000",
    }})
    observer.observe("pb.WinnerRSP", {"profit": [{"uid": "10262053", "chips": "100000"}]})
    assert observer.snapshot()["seats"][0]["stack"] == 200000


def test_new_hand_discards_baselines_of_absent_players(observer):
    observer.observe("pb.DealerInfoRSP", {"start_info": [{"seatid": 3, "chips": "500000"}]})
    observer.observe("pb.DealerInfoRSP", {"start_info": [{"chips": "1000000"}]})
    observer.observe("pb.ActionBRC", {
        "seatid": 3, "action_type": 3, "chips": "10000", "hand_chips": "190000",
    })
    observer.observe("pb.WinnerRSP", {"profit": [{"seatid": 3, "uid": "10689400", "chips": "-10000"}]})
    assert observer.snapshot()["seats"][3]["stack"] == 190000
