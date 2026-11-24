"""Table selection: leave tables without humans (or with fewer humans than robots)."""

import random

import pytest

from pf_intercept.bot import BotBridge
from pf_intercept.table_policy import (
    ALLOWED_STAKES, IDLE, LEAVING, MATCHING, PROBING, SCHEDULED, SEATED, STOPPED,
    TablePolicy, TablePolicyConfig, default_ladder, parse_ladder, verdict,
)
from pokerfate.core import robots as robots_mod
from pokerfate.core.robots import ROBOT

ME = "10262053"


def _policy(**kw) -> TablePolicy:
    cfg = TablePolicyConfig(home_bb=10000, hop_delay=(60.0, 60.0), **kw)
    return TablePolicy(cfg, rng=random.Random(1))


def _search(p: TablePolicy, good, *, max_asks: int = 200):
    """Run the lobby loop from SCHEDULED until we sit at an acceptable table, the policy
    stops, or ``max_asks`` matches were requested.  ``good(bb, now)`` says whether tables at
    that stake currently have humans.  Returns (asked stakes, time, stop step or None)."""
    asked = []
    now = p.next_match_at
    while len(asked) < max_asks:
        assert p.state == SCHEDULED
        now = p.next_match_at
        step = p.on_tick(now)
        assert step.kind == "match" and p.state == MATCHING
        asked.append(step.bb)
        if good(step.bb, now):
            assert not p.on_enter(step.bb, 3, 0, now)
            return asked, now, None
        leave = p.on_enter(step.bb, 0, 2, now)
        assert (leave.kind, leave.reason, leave.delayed) == ("leave", "no_humans", False)
        stop = p.on_left(now, ours=True)
        if stop:
            return asked, now, stop
    return asked, now, None


def _reject_first_table(p: TablePolicy, now: float = 0.0) -> None:
    step = p.on_enter(p.current_bb(), 0, 2, now)
    assert (step.kind, step.reason, step.delayed) == ("leave", "no_humans", False)
    assert p.state == LEAVING
    assert not p.on_left(now, ours=True)               # nothing to send yet: the match is timed
    assert p.state == SCHEDULED
    assert not p.on_tick(p.next_match_at - 1)          # too early


# ── pure policy ──────────────────────────────────────────────────────────────

def test_ladder_is_a_preference_order_nearest_first_and_inside_the_allowed_stakes():
    # home, then the nearest stakes with the higher one first: never a pure walk downwards
    assert default_ladder(10000) == (10000, 20000, 5000, 2000, 1000)
    assert default_ladder(5000) == (5000, 10000, 2000, 20000, 1000)
    assert default_ladder(1000) == (1000, 2000, 5000, 10000, 20000)
    assert default_ladder(20000) == (20000, 10000, 5000, 2000, 1000)
    assert parse_ladder("", 5000) == default_ladder(5000)
    assert parse_ladder("10000, 5000,10000", 10000) == (10000, 5000)      # the user's order wins
    with pytest.raises(ValueError):
        parse_ladder("10000,50000", 10000)       # above the user's cap
    assert max(ALLOWED_STAKES) == 20000 and min(ALLOWED_STAKES) == 1000


@pytest.mark.parametrize("humans,robots,expected", [
    (0, 0, "empty"), (0, 1, "no_humans"), (0, 2, "no_humans"),
    (1, 2, "outnumbered"), (1, 1, "stay"), (2, 1, "stay"), (2, 2, "stay"), (5, 0, "stay"), (1, 0, "stay"),
])
def test_verdict(humans, robots, expected):
    assert verdict(humans, robots) == expected


def test_dead_lobby_search_follows_the_preference_order_and_comes_back_to_home_first():
    p = _policy()                                      # 60 s between matches, cool-down 900 s → 3600 s
    _reject_first_table(p)                             # 1st of 3 tries at home
    asked, now, stop = _search(p, lambda bb, t: False, max_asks=20)
    assert stop is None
    assert asked == [10000, 10000,                     # home: tries 2 and 3
                     20000, 20000, 20000, 5000, 5000, 5000, 2000, 2000, 2000, 1000, 1000, 1000,
                     10000, 10000, 10000,              # home's cool-down ran out first: back to home,
                     20000, 20000, 20000]              # then again in preference order
    assert p.fail_rounds[10000] == 2 and p.fail_rounds[1000] == 1
    # second failure doubles the cool-down
    assert p._cooldown(1) == 900 and p._cooldown(2) == 1800 and p._cooldown(3) == 3600 and p._cooldown(9) == 3600


def test_every_stake_failing_three_rounds_stops_the_search():
    p = _policy(tries_per_stake=1, ladder=(10000, 5000), stake_retry=(100.0, 400.0))
    p.on_enter(10000, 0, 1, 0.0)
    assert not p.on_left(0.0, ours=True)
    asked, now, stop = _search(p, lambda bb, t: False)
    assert stop.kind == "stop" and p.state == STOPPED and p.stopped
    assert p.fail_rounds == {10000: 3, 5000: 3}
    assert asked == [5000, 10000, 5000, 10000, 5000]   # with the first table: three rounds each
    assert not p.on_tick(now + 10_000)                 # stays stopped


def test_fallback_stake_is_never_permanent():
    """Home and 20k have no humans for a while, 5k always has: we play 5k but keep going back."""
    home_alive_from = 6000.0
    good = lambda bb, t: bb == 5000 or (bb == 10000 and t >= home_alive_from)
    p = _policy()
    _reject_first_table(p)
    asked, now, _ = _search(p, good)
    assert asked == [10000, 10000, 20000, 20000, 20000, 5000] and p.state == SEATED
    assert p.current_bb() == 5000 and p.fail_rounds[5000] == 0
    home_retry = p.retry_at[10000]
    assert home_retry == 120.0 + 900.0                 # home failed at t=120
    p.on_dealt()
    assert not p.on_hand_end(3, 0, home_retry - 1)     # home still cooling down: keep playing
    step = p.on_hand_end(3, 0, home_retry + 5)         # cool-down over: leave this good table
    assert (step.kind, step.reason, step.delayed) == ("leave", "better_stake", True)
    assert not p.on_left(home_retry + 20, ours=True)
    asked, now, _ = _search(p, good)
    # one trip: home (2 tables), then 20k whose cool-down ends within minutes (2 tables), then
    # straight back to the stake that worked — no second trip for 20k a few minutes later
    assert asked == [10000, 10000, 20000, 20000, 5000]
    assert p.current_bb() == 5000 and p.fail_rounds[10000] == 2 and p.fail_rounds[20000] == 2
    assert p.retry_at[10000] - home_retry > 1800       # the second cool-down is twice as long
    assert not p.on_hand_end(3, 0, now + 600)          # back at 5k: nothing is due for a while
    # much later home has humans again
    p.on_dealt()
    assert not p.on_hand_end(3, 0, p.retry_at[10000] - 1)
    later = max(p.retry_at[10000], home_alive_from) + 1
    assert p.on_hand_end(3, 0, later).reason == "better_stake"
    assert not p.on_left(later + 10, ours=True)
    asked, now, _ = _search(p, good)
    assert asked == [10000] and p.current_bb() == 10000 and p.fail_rounds[10000] == 0
    p.on_dealt()
    assert not p.on_hand_end(3, 0, now + 99_999)       # at home there is nothing better to probe


def test_broken_fallback_table_does_not_drag_us_through_stakes_that_are_cooling_down():
    good = lambda bb, t: bb == 5000
    p = _policy()
    _reject_first_table(p)
    _search(p, good)                                   # seated at 5000; home and 20k cooling down
    p.on_dealt()
    step = p.on_seats_changed(0, 2, 700.0)             # the humans left this 5k table
    assert (step.kind, step.reason) == ("leave", "no_humans")
    assert not p.on_left(710.0, ours=True)
    asked, now, _ = _search(p, good)
    assert asked == [5000]                             # not 10000 / 20000: their cool-downs are running


def test_good_table_resets_the_search_and_is_judged_at_hand_ends():
    p = _policy()
    p.on_enter(10000, 0, 2, 0.0)
    p.on_left(0.0, ours=True)
    p.on_tick(p.next_match_at)
    assert not p.on_enter(10000, 2, 1, 100.0)          # 2 humans, 1 robot: stay
    assert (p.state, p.tries, p.fail_rounds.get(10000, 0)) == (SEATED, 0, 0)
    p.on_dealt()
    assert not p.on_hand_end(2, 1, 110.0)
    # humans < robots must hold on two consecutive hand ends
    assert not p.on_hand_end(1, 2, 120.0)
    assert not p.on_hand_end(1, 1, 130.0)              # recovered: streak cleared
    assert not p.on_hand_end(1, 2, 140.0)
    step = p.on_hand_end(1, 2, 150.0)
    assert (step.kind, step.reason, step.delayed) == ("leave", "outnumbered", True)
    assert p.tries == 0                                # a table that went bad is not a rejected try


def test_last_human_leaving_means_leave_after_this_hand():
    p = _policy()
    p.on_enter(10000, 1, 1, 0.0)
    p.on_dealt()
    step = p.on_seats_changed(0, 2, 5.0)               # the human left mid-hand
    assert (step.kind, step.reason, step.delayed) == ("leave", "no_humans", True)
    assert not p.on_hand_end(0, 2, 6.0)                # already leaving: no second request
    retry = p.on_tick(5.0 + p.cfg.leave_retry_sec)     # server never answered: ask again
    assert (retry.kind, retry.delayed) == ("leave", True)


def test_empty_table_waits_for_the_first_arrival():
    p = _policy()
    assert not p.on_enter(10000, 0, 0, 0.0)
    assert p.state == PROBING
    assert not p.on_tick(9.9)                          # inside the grace period
    step = p.on_seats_changed(0, 1, 9.99)              # a robot sat down first
    assert (step.kind, step.reason, step.delayed) == ("leave", "no_humans", False)

    p = _policy()
    p.on_enter(10000, 0, 0, 0.0)
    assert not p.on_seats_changed(1, 0, 9.0)           # a human sat down first
    assert p.state == SEATED

    p = _policy()
    p.on_enter(10000, 0, 0, 0.0)
    step = p.on_tick(10.0)                             # nobody came
    assert (step.kind, step.reason) == ("leave", "empty_timeout")


def test_empty_table_after_play_survives_duplicate_events_and_restarts_on_next_vacancy():
    p = _policy()
    p.on_enter(10000, 1, 0, 0.0)
    p.on_dealt()
    assert not p.on_seats_changed(0, 0, 10.0)
    assert not p.on_seats_changed(1, 0, 16.0)          # a human returns after 6 s
    assert not p.on_tick(70.0, 1, 0)
    assert p.state == SEATED

    assert not p.on_seats_changed(0, 0, 80.0)
    assert not p.on_hand_end(0, 0, 82.0)
    assert not p.on_seats_changed(0, 0, 85.0)
    assert not p.on_tick(89.9, 0, 0)
    step = p.on_tick(90.0, 0, 0)
    assert (step.kind, step.reason, step.delayed, p.tries) == ("leave", "empty_timeout", False, 0)
    assert not p.on_tick(91.0, 0, 0)


def test_reconnect_to_empty_table_with_cards_rechecks_arrivals_before_leaving():
    p = _policy()
    p.on_enter(10000, 0, 0, 0.0, dealt=True)
    assert p.state == PROBING
    assert not p.on_tick(60.0, 1, 2)                   # occupied again; use the played-table rules
    assert p.state == SEATED
    assert not p.on_hand_end(1, 2, 61.0)
    assert p.on_hand_end(1, 2, 70.0).reason == "outnumbered"


def test_outnumbered_at_entry_is_left_at_once_but_not_once_dealt_in():
    p = _policy()
    step = p.on_enter(10000, 1, 2, 0.0)
    assert (step.kind, step.reason, step.delayed) == ("leave", "outnumbered", False)
    p = _policy()
    assert not p.on_enter(10000, 1, 2, 0.0, dealt=True)   # reconnect mid-hand: judge at hand end
    assert p.state == SEATED and p.dealt


def test_refused_stake_is_skipped_for_the_rest_of_the_run():
    p = _policy(ladder=(10000, 20000, 5000))
    _reject_first_table(p)
    for _ in range(2):                                 # tries 2 and 3 at home
        now = p.next_match_at
        assert p.on_tick(now).bb == 10000
        p.on_enter(10000, 0, 1, now)
        p.on_left(now, ours=True)
    now = p.next_match_at
    assert p.on_tick(now).bb == 20000                  # home's round failed: next preference
    assert not p.on_match_failed(1234, now + 1)        # e.g. not enough chips for 20k
    assert p.current_bb() == 5000 and 20000 in p.unavailable
    assert 20000 not in p.fail_rounds                  # refused is not "no humans there"
    step = p.on_tick(p.next_match_at)
    assert step.kind == "match" and step.bb == 5000
    # 20k is never asked for again, not even as a "better stake" while we play 5k
    assert not p.on_enter(5000, 3, 0, now + 100)
    p.on_dealt()
    p.retry_at[10000] = now + 10_000
    assert not p.on_hand_end(3, 0, now + 5_000)


def test_match_fields_force_wait_for_blind_and_follow_the_search_stake():
    p = _policy()
    base = {"boot": 10000, "game_type": 10010101, "lobby_coin": 10100001, "byin_chips": 500000,
            "wait_blind": False, "ip": "1.2.3.4"}
    out = p.match_fields(base)
    assert out["wait_blind"] is True and out["boot"] == 10000 and out["byin_chips"] == 1_000_000
    p.stake_idx = 2
    p.state = SCHEDULED
    out = p.match_fields(base)
    assert (out["boot"], out["byin_chips"]) == (5000, 500_000)
    assert base["wait_blind"] is False                 # input untouched
    p.state = SEATED                                   # a re-match made while seated keeps its own stake
    assert p.match_fields(dict(base, boot=20000, byin_chips=7))["boot"] == 20000


def test_foreign_leave_hands_the_table_back_without_scheduling():
    p = _policy()
    p.on_enter(10000, 3, 0, 0.0)
    assert not p.on_left(5.0, ours=False)              # profit lock / kick: other flows re-enter
    assert p.state == IDLE and not p.on_tick(10_000.0)


# ── bridge wiring ────────────────────────────────────────────────────────────

ROBOTS = ("10334071", "10334073", "10334126", "10334135", "10334177")


def _bridge(monkeypatch, **kw) -> BotBridge:
    reg = robots_mod.default_registry()
    for uid in ROBOTS:
        reg.confirm(uid, ROBOT, "test")
    b = BotBridge(max_auto_rebuy=0)
    b.set_session_uid(int(ME))
    monkeypatch.setattr(b, "_runtime_calibration_should_pause_play", lambda: None)
    b.configure_auto_rejoin({"boot": 10000, "game_type": 10010101, "lobby_coin": 10100001,
                            "byin_chips": 1000000, "wait_blind": False, "ip": "9.9.9.9"})
    b.configure_table_policy(TablePolicyConfig(home_bb=10000, hop_delay=(60.0, 60.0), **kw))
    return b


def _enter(uids, room=21203448, bb=10000):
    seats = [{"seatid": i, "player": {"uid": u, "name": f"p{u}"}, "hand_chips": "1000000"}
             for i, u in enumerate(uids)]
    return {"code": 0, "roomid": room, "game_type": 10010101,
            "room_info": {"bb": str(bb), "sb": str(bb // 2), "lobby_coin": 10100001},
            "table_status": {"seat": seats}}


def test_bridge_leaves_a_robot_table_and_rematches_waiting_for_the_blind(monkeypatch):
    b = _bridge(monkeypatch)
    clock = [1000.0]
    monkeypatch.setattr("pf_intercept.bot.time.time", lambda: clock[0])
    out = b.handle("pb.EnterRoomRSP", _enter([ME, ROBOTS[0], ROBOTS[1]]))
    assert out == ("pb.LeaveRoomREQ", {"seat_reserve": False, "is_switch_room": True}, 0.0)
    # the leave is ours: no "unexpected leave" re-match, only a wallet refresh
    sample = b.handle("pb.LeaveRoomRSP", {"roomid": 21203448})
    assert sample[0] == "pb.UserValueREQ"
    assert b.handle("pb.UserValueRSP", {"type": 10100001, "value": "50000000"}) is None
    assert b._table_policy.state == SCHEDULED
    assert b.handle("pf.Tick", {"now": 1030.0}) is None
    match = b.handle("pf.Tick", {"now": 1061.0})
    assert match[0] == "pb.QuickStartREQ"
    assert match[1] == {"boot": 10000, "game_type": 10010101, "lobby_coin": 10100001,
                        "byin_chips": 1000000, "wait_blind": True, "ip": "9.9.9.9"}
    # a table with two humans and one robot is kept
    assert b.handle("pb.EnterRoomRSP", _enter([ME, "10700890", "10774146", ROBOTS[2]])) is None
    assert b._table_policy.state == SEATED
    comp = b._table_composition()
    assert (comp["humans"], comp["robots"]) == (2, 1)


def test_bridge_uses_the_server_count_and_grows_the_registry(monkeypatch):
    b = _bridge(monkeypatch)
    reg = robots_mod.default_registry()
    # two accounts nobody has proven yet, outside every robot block: counted as human at first
    assert b.handle("pb.EnterRoomRSP", _enter([ME, "20000001", "20000002", "10700890"])) is None
    b.handle("pb.SitDownRSP", {"seatid": 0})
    # the human leaves; the server says both remaining accounts are robots
    out = b.handle("pb.OtherLeaveRoomBRC", {"uid": "10700890", "num": 3, "rb_num": 2})
    assert reg.label("20000001") == ROBOT and reg.label("20000002") == ROBOT
    assert out == ("pb.LeaveRoomREQ", {"seat_reserve": False, "is_switch_room": True}, 0.0)


def test_bridge_rematches_when_last_opponent_leaves_a_played_table(monkeypatch):
    b = _bridge(monkeypatch)
    clock = [1000.0]
    monkeypatch.setattr("pf_intercept.bot.time.time", lambda: clock[0])
    opponent = "10700890"
    b.handle("pb.EnterRoomRSP", _enter([ME, opponent]))
    b.handle("pb.SitDownRSP", {"seatid": 0})
    b._table_policy.on_dealt()
    assert b.handle("pb.OtherLeaveRoomBRC", {"uid": opponent, "num": 1}) is None
    clock[0] += 10
    leave = b.handle("pf.Tick", {"now": clock[0]})
    assert leave == ("pb.LeaveRoomREQ", {"seat_reserve": False, "is_switch_room": True}, 0.0)
    assert b._table_switch["reason"] == "empty_timeout"
    b.handle("pb.LeaveRoomRSP", {"roomid": 21203448})
    match = b.handle("pf.Tick", {"now": b._table_policy.next_match_at})
    assert match[0] == "pb.QuickStartREQ"
    assert b._auto_rebuy_done == 0


def test_profit_lock_owns_leave_even_if_empty_table_timer_expires(monkeypatch):
    b = _bridge(monkeypatch)
    b.handle("pb.EnterRoomRSP", _enter([ME, "10700890"]))
    b.handle("pb.SitDownRSP", {"seatid": 0})
    b._table_policy.on_dealt()
    b.handle("pb.OtherLeaveRoomBRC", {"uid": "10700890", "num": 1})
    assert b._maybe_profit_lock_leave_reenter({0: 2_000_000})[0] == "pb.DelayLeaveRoomREQ"
    assert b.handle("pf.Tick", {"now": b._table_policy.deadline}) is None
    assert b._table_switch is None


def test_bridge_falls_back_to_leave_after_hand_when_the_server_refuses(monkeypatch):
    b = _bridge(monkeypatch)
    b.handle("pb.EnterRoomRSP", _enter([ME, ROBOTS[0]]))
    out = b.handle("pb.LeaveRoomRSP", {"code": 121})
    assert out == ("pb.DelayLeaveRoomREQ", {"flag": True}, 0.0)
    assert b._table_switch["mode"] == "delay"
    assert b.handle("pb.LeaveRoomRSP", {"roomid": 21203448})[0] == "pb.UserValueREQ"


def test_bridge_hand_end_leave_and_profit_lock_do_not_collide(monkeypatch):
    b = _bridge(monkeypatch)
    b.handle("pb.EnterRoomRSP", _enter([ME, "10700890", ROBOTS[0]]))
    b.handle("pb.SitDownRSP", {"seatid": 0})
    b._table_policy.on_dealt()
    # the human leaves between hands -> leave after the current hand, robots are never "played"
    out = b.handle("pb.OtherLeaveRoomBRC", {"uid": "10700890", "num": 2, "rb_num": 1})
    assert out == ("pb.DelayLeaveRoomREQ", {"flag": True}, 0.0)
    assert b._maybe_profit_lock_leave_reenter({0: 10 ** 12}) is None   # no second leave flow
    assert b._table_event("hand_end") is None


def test_leaving_a_played_table_reports_the_running_result(monkeypatch):
    sent = []
    monkeypatch.setattr("pf_intercept.bot.notify", lambda event, **f: sent.append((event, f)))
    b = _bridge(monkeypatch)
    b.handle("pb.EnterRoomRSP", _enter([ME, "10700890", ROBOTS[0]]))
    b.handle("pb.SitDownRSP", {"seatid": 0})
    b._table_policy.on_dealt()
    b._session_poker_pnl = -235_066
    leave = b.handle("pb.OtherLeaveRoomBRC", {"uid": "10700890", "num": 2, "rb_num": 1})
    assert leave == ("pb.DelayLeaveRoomREQ", {"flag": True}, 0.0)
    # the server never answers: the retry is still the same leave, for the same reason
    retry = b.handle("pf.Tick", {"now": b._table_policy.deadline})
    assert retry == ("pb.DelayLeaveRoomREQ", {"flag": True}, 0.0) and b._table_switch["reason"] == "retry"
    assert sent == []                                  # nothing before the server confirms
    b.handle("pb.LeaveRoomRSP", {"roomid": 21203448})
    assert sent == [("table_leave", {"reason": "no_humans", "session_delta_chips": -235_066})]


def test_an_errand_leaves_a_played_table_after_the_hand_and_matches_again(monkeypatch):
    """The session has something to do away from the table (the tasks' Omaha / AOF hands)."""
    sent = []
    monkeypatch.setattr("pf_intercept.bot.notify", lambda event, **f: sent.append((event, f)))
    b = _bridge(monkeypatch)
    assert b.handle("pf.Errand", {}) is None                # in the lobby: a match is on its way anyway
    b.handle("pb.EnterRoomRSP", _enter([ME, "10700890", "10774146"]))
    b.handle("pb.SitDownRSP", {"seatid": 0})
    assert b.handle("pf.Errand", {}) is None                # not dealt in yet: the table is still being judged
    b._table_policy.on_dealt()
    b._session_poker_pnl = 12_000
    assert b.handle("pf.Errand", {}) == ("pb.DelayLeaveRoomREQ", {"flag": True}, 0.0)
    assert (b._table_switch["reason"], b._table_policy.state) == ("errand", LEAVING)
    assert b.handle("pf.Errand", {}) is None                # one leave at a time
    b.handle("pb.LeaveRoomRSP", {"roomid": 21203448})
    assert sent == [("table_leave", {"reason": "errand", "session_delta_chips": 12_000})]
    # A table that was fine: no stake is marked down, the search starts over at the same one.
    p = b._table_policy
    assert (p.state, p.tries, p.current_bb(), p.unavailable) == (SCHEDULED, 0, 10000, set())
    assert not any(p.fail_rounds.values()) and not any(p.retry_at.values())
    assert b.handle("pf.Tick", {"now": p.next_match_at})[0] == "pb.QuickStartREQ"


def test_an_errand_waits_while_another_leave_owns_the_table(monkeypatch):
    b = _bridge(monkeypatch)
    b.handle("pb.EnterRoomRSP", _enter([ME, "10700890"]))
    b.handle("pb.SitDownRSP", {"seatid": 0})
    b._table_policy.on_dealt()
    assert b._maybe_profit_lock_leave_reenter({0: 2_000_000})[0] == "pb.DelayLeaveRoomREQ"
    assert b.handle("pf.Errand", {}) is None and b._table_switch is None


def test_rejecting_a_table_on_arrival_sends_nothing(monkeypatch):
    sent = []
    monkeypatch.setattr("pf_intercept.bot.notify", lambda event, **f: sent.append((event, f)))
    b = _bridge(monkeypatch)
    b.handle("pb.EnterRoomRSP", _enter([ME, ROBOTS[0], ROBOTS[1]]))
    b.handle("pb.LeaveRoomRSP", {"roomid": 21203448})
    assert sent == [] and b._table_policy.state == SCHEDULED


def test_stop_notifies_once_and_blocks_reconnect_rematch(monkeypatch):
    sent = []
    monkeypatch.setattr("pf_intercept.bot.notify", lambda event, **f: sent.append((event, f)))
    b = _bridge(monkeypatch, tries_per_stake=1, max_fail_rounds=1, ladder=(10000,))
    b.handle("pb.EnterRoomRSP", _enter([ME, ROBOTS[0]]))
    b.handle("pb.LeaveRoomRSP", {"roomid": 21203448})
    assert b._table_policy.stopped
    assert [e for e, _ in sent] == ["codex_done"] and "已停止" in sent[0][1]["title"]
    assert b.handle("pf.Tick", {"now": 9e9}) is None
    b.prepare_transport_reconnect()
    assert b.restore_lobby_after_disconnect() is False


def test_table_switch_buy_in_stays_under_the_net_loss_cap(monkeypatch):
    # home stake 10000, --max-auto-rebuy 0: the start may lose 1,000,000 in all
    def leave_and_tick(net):
        b = _bridge(monkeypatch)
        monkeypatch.setattr("pf_intercept.bot.time.time", lambda: 1000.0)
        b.handle("pb.EnterRoomRSP", _enter([ME, ROBOTS[0], ROBOTS[1]]))
        b.handle("pb.LeaveRoomRSP", {"roomid": 21203448})
        b.handle("pb.UserValueRSP", {"type": 10100001, "value": "50000000"})
        b._session_poker_pnl = net
        return b, b.handle("pf.Tick", {"now": 1061.0})

    sent = []
    monkeypatch.setattr("pf_intercept.bot.notify", lambda event, **f: sent.append((event, f)))
    _, match = leave_and_tick(+300_000)
    assert match[1]["byin_chips"] == 1_000_000              # ahead: a full buy-in
    b, match = leave_and_tick(-20_000)
    assert match[0] == "pb.QuickStartREQ" and match[1]["byin_chips"] == 900_000    # 98BB of room → 90BB
    assert b._auto_rejoin_fields["byin_chips"] == 1_000_000 and not b._loss_stop
    b, match = leave_and_tick(-990_000)                     # 1BB of room: the start is over
    assert match is None and b._loss_stop
    assert [e for e, _ in sent] == ["loss_stop"]
    assert b.handle("pf.Tick", {"now": 9e9}) is None        # and it does not keep trying
    b.prepare_transport_reconnect()
    assert b.restore_lobby_after_disconnect() is False


def test_the_loss_cap_is_counted_at_the_home_stake_whatever_table_we_sit_at(monkeypatch):
    b = _bridge(monkeypatch)                                # home 10000, N = 0
    b._bb = 2000.0                                          # playing a fallback stake
    assert b._loss_cap_chips() == 1_000_000
    b._session_poker_pnl = -100_000
    assert b._capped_buyin(200_000, 2000.0) == 200_000      # 100BB at the 2000 blind fits easily
    b._bb = 20000.0
    # at the 20000 blind the 900,000 of room is 45BB: the largest amount on offer below it is 40BB
    assert b._capped_buyin(2_000_000, 20000.0) == 800_000


def test_policy_off_changes_nothing(monkeypatch):
    b = BotBridge(max_auto_rebuy=0)
    b.set_session_uid(int(ME))
    assert not b.wants_tick()
    assert b.handle("pb.EnterRoomRSP", _enter([ME, ROBOTS[0], ROBOTS[1]])) is None
    assert b.adjust_match_fields({"wait_blind": False}) == {"wait_blind": False}


@pytest.mark.parametrize("proxy", [False, True], ids=["headless", "proxy"])
def test_both_entries_follow_the_same_cash_table_lifecycle(monkeypatch, proxy):
    from pf_intercept import config
    from pf_intercept.table_policy import configured_policy

    for uid in ROBOTS:
        robots_mod.default_registry().confirm(uid, ROBOT, "test")
    monkeypatch.setattr(config, "TABLE_SELECT_HOP_DELAY_SEC", (5.0, 5.0))
    clock = [1000.0]
    monkeypatch.setattr("pf_intercept.bot.time.time", lambda: clock[0])
    b = BotBridge(max_auto_rebuy=5, auto_table_selection=proxy)
    b.set_session_uid(int(ME))
    monkeypatch.setattr(b, "_runtime_calibration_should_pause_play", lambda: None)
    if not proxy:
        b.configure_table_policy(configured_policy(5000))

    leave = b.handle("pb.EnterRoomRSP", _enter([ME, ROBOTS[0]], bb=5000))
    assert leave[0] == "pb.LeaveRoomREQ"
    p = b._table_policy
    assert p.cfg == configured_policy(5000)
    loss_cap = b._loss_cap_chips()
    assert b.handle("pb.LeaveRoomRSP", {})[0] == "pb.UserValueREQ"
    b.handle("pb.UserValueRSP", {"type": 10100001, "value": "50000000"})
    assert b.handle("pf.Tick", {"now": 1004.0}) is None
    match = b.handle("pf.Tick", {"now": 1005.0})
    assert match[0] == "pb.QuickStartREQ"
    assert match[1]["boot"] == 5000
    assert match[1]["byin_chips"] == 500000
    assert match[1]["wait_blind"] is True
    assert b._auto_rebuy_done == 0

    # A server rejection advances the common ladder. A fallback table does not
    # change the run's home stake or grant another loss budget.
    b.handle("pb.QuickStartRSP", {"code": 123})
    assert b.handle("pf.Tick", {"now": p.next_match_at})[1]["boot"] == 10000
    assert b.handle("pb.EnterRoomRSP", _enter([ME, "20000001"], bb=10000)) is None
    assert b._table_policy is p and p.cfg.home_bb == 5000
    assert b._loss_cap_chips() == loss_cap

    # The same empty-table timer also operates after a hand/table change.
    b.handle("pb.OtherLeaveRoomBRC", {"uid": "20000001"})
    assert b.handle("pf.Tick", {"now": p.deadline})[0] == "pb.LeaveRoomREQ"
    b.stop_auto_rejoin()
    assert b.handle("pf.Tick", {"now": 9e9}) is None


@pytest.mark.parametrize("kind", ["spectator", "friend", "tournament", "practice", "failed"])
def test_proxy_only_enables_selection_for_a_seated_cash_player(monkeypatch, kind):
    b = BotBridge(auto_table_selection=True)
    b.set_session_uid(int(ME))
    msg = _enter([ME, ROBOTS[0]])
    if kind == "spectator":
        msg = _enter([ROBOTS[0]])
    elif kind == "friend":
        msg["friend_room_info"] = {"owner": ME}
    elif kind == "tournament":
        msg["sngroom_info"] = {"id": 1}
    elif kind == "practice":
        msg["game_type"] = 10010102
    else:
        msg["code"] = 123
    b.handle("pb.EnterRoomRSP", msg)
    assert not b.wants_tick()
    assert b.handle("pf.Tick", {"now": 9e9}) is None


def test_proxy_spectator_sits_then_manual_leave_does_not_rematch(monkeypatch):
    b = BotBridge(auto_table_selection=True)
    b.set_session_uid(int(ME))
    monkeypatch.setattr(b, "_runtime_calibration_should_pause_play", lambda: None)
    b.handle("pb.EnterRoomRSP", _enter(["20000001"]))
    b.handle("pb.SitDownRSP", {"seatid": 1, "chips": "1000000"})
    assert b.wants_tick() and b._table_policy.state == SEATED
    # Match fields can have been populated by an earlier automatic switch.
    b._auto_rejoin_fields = b._table_match_fields(10000)
    b.note_client_table_request("pb.LeaveRoomREQ", {})
    b.handle("pb.LeaveRoomRSP", {})
    assert b._bankroll_pending_action is None
    assert b.handle("pf.Tick", {"now": 9e9}) is None
    assert b.handle("pb.QuickStartRSP", {"code": 123}) is None
    b.handle("pb.EnterRoomRSP", _enter([ME, "20000001"]))
    assert b._table_policy.state == SEATED


def test_proxy_manual_delayed_leave_can_be_cancelled(monkeypatch):
    b = BotBridge(auto_table_selection=True)
    b.set_session_uid(int(ME))
    monkeypatch.setattr(b, "_runtime_calibration_should_pause_play", lambda: None)
    b.handle("pb.EnterRoomRSP", _enter([ME, "20000001"]))
    b.note_client_table_request("pb.DelayLeaveRoomREQ", {"flag": True})
    assert b.handle("pf.Tick", {"now": 9e9}) is None
    b.note_client_table_request("pb.DelayLeaveRoomREQ", {"flag": False})
    assert b._table_policy.state == SEATED
    assert b._auto_rejoin_fields["boot"] == 10000
    b.handle("pb.OtherLeaveRoomBRC", {"uid": "20000001"})
    assert b.handle("pf.Tick", {"now": b._table_policy.deadline})[0] == "pb.LeaveRoomREQ"


@pytest.mark.parametrize("manual_stop", [False, True])
def test_proxy_lobby_reconnect_preserves_budget_and_manual_stop(monkeypatch, manual_stop):
    b = BotBridge(max_auto_rebuy=0, auto_table_selection=True)
    b.set_session_uid(int(ME))
    monkeypatch.setattr(b, "_runtime_calibration_should_pause_play", lambda: None)
    b.handle("pb.EnterRoomRSP", _enter([ME, "20000001"], bb=5000))
    b._session_poker_pnl = -100000
    if manual_stop:
        b.note_client_table_request("pb.LeaveRoomREQ", {})
    b.prepare_transport_reconnect()
    # An existing room is restored by the client, without a new buy-in.
    assert b.handle("pb.UserLocationRSP", {"roomid": 90}) is None
    out = b.handle("pb.UserLocationRSP", {"roomid": 0})
    if manual_stop:
        assert out is None
    else:
        assert out[0] == "pb.QuickStartREQ"
        assert out[1]["boot"] == 5000
        assert 0 < out[1]["byin_chips"] <= 400000
    assert b._auto_rebuy_done == 0
    assert b._loss_cap_chips() == 500000


def test_proxy_unexpected_leave_uses_the_shared_cash_recovery(monkeypatch):
    b = BotBridge(max_auto_rebuy=5, auto_table_selection=True)
    b.set_session_uid(int(ME))
    monkeypatch.setattr(b, "_runtime_calibration_should_pause_play", lambda: None)
    b.handle("pb.EnterRoomRSP", _enter([ME, "20000001"], bb=5000))
    assert b.handle("pb.LeaveRoomRSP", {})[0] == "pb.UserValueREQ"
    out = b.handle("pb.UserValueRSP", {"type": 10100001, "value": "50000000"})
    assert out[0] == "pb.QuickStartREQ" and out[1]["boot"] == 5000
    assert b._auto_rebuy_done == 0
