"""协会经营 (派遣): scripted server replies, no real game requests."""
from __future__ import annotations

import asyncio
import copy
import json
import re
from collections import deque
from pathlib import Path

import pytest

from pf_intercept.headless.lobby.activities import dispatch as dp
from pf_intercept.headless.lobby.core import base as lb
from pf_intercept.headless.lobby.routine import fund as fd
from pf_intercept.headless.lobby.core import needs as nd
from pf_intercept.headless.lobby.core import service as sv
from pf_intercept.headless.lobby.routine import tasks as tk
from pf_intercept.wire import codec

NOW = dp.season()[0] + 30 * 86400
TPL = Path(__file__).resolve().parents[1] / "pf_reverse" / "output" / "lua" / "src" / "tpl"


class ScriptedHTTP:
    """Replies in the order given; any request outside the script fails the test."""

    def __init__(self, replies):
        self.replies = deque(replies)
        self.calls = []

    def __call__(self, url, payload, **kwargs):
        # pytest.fail is not an Exception, so the worker cannot take it for a network error.
        if not self.replies or url != "https://game.example" + self.replies[0][0]:
            pytest.fail(f"unexpected request {url} {payload}")
        endpoint, response = self.replies.popleft()
        self.calls.append((endpoint, payload))
        return copy.deepcopy(response)


class Game:
    """The socket side: the players of the account and its bag."""

    def __init__(self, skins, tickets):
        self.skins, self.tickets, self.asked = skins, tickets, []

    async def activity_request(self, name, fields):
        self.asked.append(name)
        assert fields == {}
        if name == "RoleList":
            reply = {"role_list": [{"role_id": role, "skin_info": {"skin_id": skin, "owned_skin_ids": owned}}
                                   for role, (skin, owned) in self.skins.items()]}
        else:
            assert name == "ItemList"
            reply = {"item_list": [{"item_id": dp.ORDINARY, "num": self.tickets},
                                   {"item_id": dp.ORDINARY, "num": 50, "deadline": NOW - 1}]}
        # What the worker gets is the decoded frame: 64-bit counts arrive as strings.
        return codec.decode(f"pb.{name}RSP", codec.encode(f"pb.{name}RSP", reply))


def setup(tmp_path, replies, *, skins=None, tickets=5, now=NOW):
    http = ScriptedHTTP(replies)
    credits = []

    async def credit(chips, uncertain):
        credits.append((chips, uncertain))

    ready = asyncio.Event()
    ready.set()
    svc = sv.RewardService(uid=42, authorization="session-secret", http_base="https://game.example",
                           chnl=3, version="1.7.0", on_credit=credit, ready=ready, post=http,
                           journal_path=tmp_path / "rewards.jsonl")
    clock = [now]
    svc.now = lambda: clock[0]
    game = Game(skins if skins is not None else {1001: (100101, [100101])}, tickets)
    worker = dp.Dispatch(svc, game)
    worker.pass_due = worker.tasks_due = False
    return worker, http, game, credits, clock


def journal(tmp_path, *events):
    path = tmp_path / "rewards.jsonl"
    rows = [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []
    return [row for row in rows if not events or row["event"] in events]


def row(ident, event_id, status=dp.NOT_SENT, end=0, role=0):
    return {"id": ident, "event_id": event_id, "status": status, "end_ts": end, "role_id": role}


def listing(*rows, sends=9, refreshes=3, roles=(), camps=((0, 1),)):
    return {"code": 0, "event_list": list(rows), "remain_free_dispatch_times": sends,
            "remain_free_refresh_times": refreshes, "role_list": list(roles),
            "camp_list": [{"camp_id": camp, "camp_level": level} for camp, level in camps]}


def lua_table(name):
    """Rows of a tpl_*.lua config table as {column: raw Lua text}."""
    path = TPL / f"tpl_{name}.lua"
    if not path.exists():
        pytest.skip("client tables not checked out")
    lines = path.read_text(encoding="utf-8").splitlines()
    keys = next(re.findall(r"'([^']+)'", line) for line in lines if "local keys" in line)
    table = []
    for line in lines:
        line = line.strip().rstrip(",")
        if not (line.startswith("{") and line.endswith("}")):
            continue
        cells, cell, depth, quoted = [], "", 0, False
        for ch in line[1:-1]:
            if ch == '"':
                quoted = not quoted
            depth += (ch == "{") - (ch == "}") if not quoted else 0
            if ch == "," and not depth and not quoted:
                cells.append(cell)
                cell = ""
            else:
                cell += ch
        table.append(dict(zip(keys, cells + [cell])))
    return table


@pytest.fixture(autouse=True)
def no_pauses(monkeypatch):
    monkeypatch.setattr(dp, "PAUSE_SEC", 0)


def test_tables_are_read_from_the_client():
    events = lua_table("event_info")
    assert {int(r["id"]): (int(r["campInt"]), int(r["event_level"])) for r in events} == dp.events()
    # The star a player needs is the level, and only levels 4 and 5 have an egg reward.
    assert all(int(r["character_level"]) == int(r["event_level"]) for r in events)
    assert all((r["reward_bonus_item"] != "nil") == (int(r["event_level"]) >= 4) for r in events)
    assert {int(r["id"]): int(r["campInt"]) for r in lua_table("character")} == dp.role_camp()
    assert {int(r["id"]): (int(r["role"]), int(r["avatar"])) for r in lua_table("character_skin")} == dp.outfits()
    passes = lua_table("passcard_info")
    assert [int(r["level"]) for r in passes] == list(range(len(dp.pass_costs())))
    assert tuple(int(r["level_up_cost"]) for r in passes) == dp.pass_costs()
    assert not any("10100001" in r["ordinary_rewards"] + r["advanced_rewards"] for r in passes)
    const = (TPL / "tpl_constdata.lua").read_text(encoding="utf-8")
    start, end = dp.season()
    for name, value in [("Dispatch_Start", start), ("Dispatch_End", end),
                        ("Dispatch_Event_Num", dp.EVENT_SLOTS), ("Dispatch_Free_Refresh", dp.MAX_REFRESHES),
                        ("Dispatch_Ordinary_Character_Num", dp.ROLE_SENDS),
                        ("Dispatch_Ordinary_Skin_Num", dp.SKIN_SENDS)]:
        assert re.search(rf"\b{name} = {value},", const), name


def test_nothing_is_sent_outside_the_season(tmp_path):
    async def run():
        worker, http, *_ = setup(tmp_path, [], now=dp.season()[1] + 1)
        await worker.check()
        assert not http.calls
        assert journal(tmp_path, "dispatch_season")[-1]["open"] is False
    asyncio.run(run())


def test_role_list_request_is_in_the_protocol():
    assert codec.encode("pb.RoleListREQ", {}) == b""
    reply = {"role_list": [{"role_id": 1003, "skin_info": {"skin_id": 100304, "owned_skin_ids": [100301, 100304]}}]}
    assert codec.decode("pb.RoleListRSP", codec.encode("pb.RoleListRSP", reply)) == reply


@pytest.mark.parametrize("summaries, level", [(0, 0), (14999, 0), (15000, 1), (94999, 5), (95000, 6),
                                              (3800000, 60), (10 ** 9, 60)])
def test_pass_level(summaries, level):
    assert dp.pass_level(summaries) == level


def test_finished_assignments_are_collected_and_only_egg_chips_are_money(tmp_path):
    async def run():
        after = listing(row(13, 100002, dp.RUNNING, NOW + 120, 1004), sends=0)
        worker, http, game, credits, _ = setup(tmp_path, [
            ("/afk/eventList", listing(
                row(11, 100005, dp.FINISHED, NOW - 60, 1001),     # SS, own camp: egg
                row(12, 100001, dp.RUNNING, NOW - 1, 1003),       # time is up, status not yet moved
                row(13, 100002, dp.RUNNING, NOW + 120, 1004),
                row(14, 100007, 3, NOW - 5000, 1002),             # already collected
                row(15, 100008))),
            ("/afk/recReward", {"code": 0, "exp": 300, "camp_quality": 4000, "star_exp": 4000,
                                "reward_bonus": [10440006, 20000, 10100001, 500000]}),
            ("/afk/recReward", {"code": 0, "camp_quality": 1000, "reward_bonus": {}}),
            ("/afk/eventList", after),
            ("/afk/passCardData", {"code": 0, "item_num": 5000, "data": {"ordinary": [0], "advanced": []}}),
            ("/task/dispatchTaskList", {"code": 0, "list": [{"id": 1, "status": 1}]}),
        ])
        worker.service.due["dispatch"] = NOW + 300
        await worker.check()
        assert not http.replies
        assert http.calls[0] == ("/afk/eventList", {"rec_item": True, "immediately": True})
        assert http.calls[1:4] == [("/afk/recReward", {"id": 11}), ("/afk/recReward", {"id": 12}),
                                   ("/afk/eventList", {"immediately": True})]
        assert credits == [(500000, False)]
        assert worker.service.confirmed_chips == 500000 and not worker.service.uncertain
        claimed, other = journal(tmp_path, "claimed", "activity_result")
        assert (claimed["kind"], claimed["chips"], claimed["id"], claimed["role_id"]) == ("dispatch", 500000, 11, 1001)
        assert claimed["rewards"]["camp_quality"] == 4000
        assert (other["chips"], other["id"], other["rewards"]) == (0, 12, {"camp_quality": 1000})
        # Nothing may be sent today, so the bag and the players are not asked for.
        assert game.asked == []
        # What the list said is journalled when it changes, with the field names the server used.
        first, second = journal(tmp_path, "dispatch_state")
        assert first["events"] == {"0": 1, "1": 2, "2": 1, "3": 1} and second["events"] == {"1": 1}
        assert (first["sends_left"], first["refreshes_left"], first["camps"], first["unknown"]) == (9, 3, {"0": 1}, 0)
        assert first["row_fields"] == ["end_ts", "event_id", "id", "role_id", "status"]
        assert "remain_free_dispatch_times" in first["fields"]
        # Woken when the running assignment ends instead of at the next poll.
        assert worker.service.due["dispatch"] == NOW + 125
    asyncio.run(run())


def test_an_assignment_id_goes_back_to_the_server_as_it_came(tmp_path):
    """Live on 2026-11-21 the list held four finished assignments and not one was asked for:
    the id of a row is the server's own text, not a number."""
    async def run():
        first, second = "6740f2c1a8b3d94e5f001a2b", "6740f2c1a8b3d94e5f001a2c"
        left = [row(second, 100002, dp.FINISHED, NOW - 60, 1003), row(None, 100007, dp.FINISHED, NOW - 60, 1004)]
        worker, http, _, credits, _ = setup(tmp_path, [
            ("/afk/eventList", listing(row(first, 100001, dp.FINISHED, NOW - 60, 1001), *left, sends=0)),
            ("/afk/recReward", {"code": 0, "exp": 300}),
            ("/afk/recReward", {"code": -855}),
            ("/afk/eventList", listing(*left, sends=0)),
            ("/afk/passCardData", {"code": 0, "item_num": 20000, "has_pass_card": False,
                                   "data": {"ordinary": [0, 1], "advanced": []}}),
            ("/task/dispatchTaskList", {"code": 0, "season_reward": False, "list": [
                {"id": 1, "status": 1, "task_id": 101000101, "current_value": 37},
                {"id": 2, "status": 3, "task_id": 102100101, "current_value": 1}]}),
        ])
        await worker.check()
        assert not http.replies and credits == []
        assert http.calls[1:3] == [("/afk/recReward", {"id": first}), ("/afk/recReward", {"id": second})]
        assert journal(tmp_path, "activity_result")[0]["id"] == first
        assert journal(tmp_path, "dispatch_state")[0]["id_types"] == ["NoneType", "str"]
        # A reward that waits and cannot be asked for is said, once.
        unreadable, = journal(tmp_path, "dispatch_unreadable")
        assert (unreadable["field"], unreadable["type"]) == ("id", "NoneType")
        assert journal(tmp_path, "dispatch_blocked")[0]["action"] == f"collect:{second}"
        # What the pass and the goals said is journalled too.
        card, = journal(tmp_path, "dispatch_pass")
        assert (card["summaries"], card["level"], card["paid"], card["ordinary"]) == (20000, 1, False, 2)
        assert card["taken_fields"] == ["advanced", "ordinary"] and "item_num" in card["fields"]
        goals, = journal(tmp_path, "dispatch_goals")
        assert (goals["goals"], goals["season"], goals["id_types"]) == ({"1": 1, "3": 1}, False, ["int"])
        assert goals["rows"] == [[101000101, 1, 37], [102100101, 3, 1]]     # goal, status, progress
        http.replies.append(("/afk/eventList", listing(*left, sends=0)))
        await worker.check()        # the refused one is left alone
        assert not http.replies and len(journal(tmp_path, "dispatch_unreadable")) == 1
    asyncio.run(run())


def test_idle_players_are_sent_with_the_clients_choice_and_request(tmp_path):
    async def run():
        skins = {1001: (100101, [100101]), 1003: (100304, [100301, 100304]), 1004: (100401, [100401]),
                 1006: (999999, [100601]), 1007: (100701, [100701]), 9999: (1, [1])}
        before = listing(
            row(21, 100001), row(22, 101003), row(23, 100002), row(24, 100008, dp.RUNNING, NOW + 900, 1007),
            row(25, 199999),                                      # an assignment the table does not know
            sends=9, camps=((0, 1), (1, 2)),
            roles=[{"role_id": 1001, "role_star": 1, "remain_dispatch_times": 2},
                   {"role_id": 1003, "role_star": 2, "remain_dispatch_times": 1},
                   {"role_id": 1004, "role_star": 5}])            # no sends left today
        worker, http, game, credits, _ = setup(tmp_path, [
            ("/afk/eventList", before),
            ("/afk/dispatch", {"code": 0}),
            ("/afk/dispatch", {"code": 0}),
            ("/afk/eventList", listing(row(24, 100008, dp.RUNNING, NOW + 900, 1007), sends=7)),
        ], skins=skins, tickets=2)
        await worker.check()
        assert not http.replies and credits == []
        # Highest level first, to the only two-star player; then own camp before another camp.
        assert http.calls[1:3] == [
            ("/afk/dispatch", {"event_id": 101003, "role_id_arr": [1003], "item_id": 10440001,
                               "avatar_arr": [20110302], "skin_id_arr": [100304]}),
            ("/afk/dispatch", {"event_id": 100001, "role_id_arr": [1001], "item_id": 10440001,
                               "avatar_arr": [20110101], "skin_id_arr": [100101]}),
        ]
        # Two tickets, two sends: 1006 (unknown skin -> first skin, another camp) stays home.
        assert game.asked == ["RoleList", "ItemList"]
        assert worker.roster[1006] == (100601, 20110601, 1) and 9999 not in worker.roster
        assert [r["event_id"] for r in journal(tmp_path, "dispatch_attempt")] == [101003, 100001]
        assert [r["role_id"] for r in journal(tmp_path, "dispatched")] == [1003, 1001]
    asyncio.run(run())


def test_a_player_without_a_server_record_has_the_full_daily_count(tmp_path):
    async def run():
        skins = {1006: (100601, [100601]), 1001: (100104, [100101, 100104])}
        worker, http, *_ = setup(tmp_path, [
            ("/afk/eventList", listing(row(31, 103001), row(32, 103002), camps=((3, 1),))),
            ("/afk/dispatch", {"code": 0}),
            ("/afk/dispatch", {"code": 0}),
            ("/afk/eventList", listing(sends=0)),
        ], skins=skins)
        await worker.check()
        assert [(p["event_id"], p["role_id_arr"], p["skin_id_arr"]) for e, p in http.calls if e == "/afk/dispatch"] == [
            (103001, [1006], [100601]), (103002, [1001], [100104])]
        # Which players the account has is journalled as the server listed them.
        roster, = journal(tmp_path, "dispatch_roster")
        assert roster["roles"] == roster["usable"] == [1001, 1006]
    asyncio.run(run())


@pytest.mark.parametrize("state, tickets, idle", [
    (listing(row(21, 100001), sends=0), 5, []),                                  # daily count used up
    (listing(row(21, 100001)), 0, [(1, 0)]),                                     # no ticket (expired ones ignored)
    (listing(row(21, 100004)), 5, []),                                           # needs three stars
    (listing(row(21, 100001), row(22, 100002, dp.RUNNING, NOW + 60, 1001)), 5, [(0, 0)]),   # the only player is away
    (listing(row(21, 100001), row(21, 100001, dp.RUNNING, NOW + 60, 1003), refreshes=0), 5, []),  # under way
    (listing(row(21, 100001), roles=[{"role_id": 1001, "role_star": 3}]), 5, [(0, 0)]),     # record without sends left
])
def test_nothing_is_sent_without_count_ticket_player_or_star(tmp_path, state, tickets, idle):
    async def run():
        worker, http, *_ = setup(tmp_path, [("/afk/eventList", state), ("/afk/eventList", state)], tickets=tickets)
        await worker.check()
        await worker.check()
        assert not http.replies and not journal(tmp_path, "dispatch_attempt")
        # What the list said, and why nothing went out, is journalled once, not on every pass.
        assert len(journal(tmp_path, "dispatch_state")) == 1
        assert [(r["players"], r["tickets"]) for r in journal(tmp_path, "dispatch_idle")] == idle
    asyncio.run(run())


def test_a_refused_send_is_not_repeated_even_after_a_restart(tmp_path):
    async def run():
        state = listing(row(21, 100001), row(22, 100002))
        skins = {1001: (100101, [100101]), 1002: (100201, [100201])}
        worker, http, game, credits, clock = setup(tmp_path, [
            ("/afk/eventList", state),
            ("/afk/dispatch", {"code": -859}),
            ("/afk/eventList", state),
            ("/afk/eventList", state),
        ], skins=skins)
        await worker.check()          # the second assignment is not tried after the refusal
        await worker.check()
        blocked, = journal(tmp_path, "dispatch_blocked")
        assert (blocked["action"], blocked["code"], blocked["until"], blocked["reply"]) == (
            "send", -859, NOW + lb.BLOCK_SEC, {"code": -859})
        assert len(journal(tmp_path, "dispatch_attempt")) == 1 and credits == []

        restarted = dp.Dispatch(worker.service, game)
        restarted.pass_due = restarted.tasks_due = False
        clock[0] = NOW + lb.BLOCK_SEC - 1
        await restarted.check()
        assert not http.replies

        http.replies.extend([("/afk/eventList", state), ("/afk/dispatch", {"code": 0}),
                             ("/afk/dispatch", {"code": 0}), ("/afk/eventList", listing(sends=7))])
        clock[0] = NOW + lb.BLOCK_SEC + 1
        await restarted.check()
        assert not http.replies
    asyncio.run(run())


def test_a_send_without_an_answer_reads_the_list_again_and_sends_are_bounded(tmp_path):
    async def run():
        state = listing(row(21, 100001))
        worker, http, game, _, clock = setup(tmp_path, [("/afk/eventList", state), ("/afk/dispatch", None)])
        with pytest.raises(lb.RewardAPIError) as failure:
            await worker.check()
        assert failure.value.code is None and not journal(tmp_path, "dispatch_blocked", "dispatched")
        # The next pass finds the assignment under way: it was sent after all.
        http.replies.append(("/afk/eventList", listing(row(21, 100001, dp.RUNNING, NOW + 900, 1001), sends=8)))
        await worker.check()
        assert not http.replies and len(journal(tmp_path, "dispatch_attempt")) == 1

        for _ in range(dp.MAX_SENDS - 1):
            worker.service._record("dispatch_attempt", event_id=100001, role_id=1001)
        capped = dp.Dispatch(worker.service, game)
        capped.pass_due = capped.tasks_due = False
        http.replies.append(("/afk/eventList", state))
        await capped.check()
        clock[0] = NOW + 86400 + 1    # a day later the count is free again
        http.replies.extend([("/afk/eventList", state), ("/afk/dispatch", {"code": 0}),
                             ("/afk/eventList", listing(sends=8))])
        await capped.check()
        assert not http.replies
    asyncio.run(run())


def test_collect_refused_once_and_unanswered_collect_only_doubts_possible_chips(tmp_path):
    async def run():
        state = listing(row(11, 100001, dp.FINISHED, NOW - 9, 1001), row(12, 100006, dp.FINISHED, NOW - 9, 1003),
                        row(13, 100006, dp.FINISHED, NOW - 9, 1001), sends=0)
        worker, http, _, credits, _ = setup(tmp_path, [
            ("/afk/eventList", state),
            ("/afk/recReward", {"code": -862}),     # refused: skipped from now on
            ("/afk/recReward", None),               # SSS by a player of another camp: no egg, no chips
        ])
        with pytest.raises(lb.RewardAPIError):
            await worker.check()
        assert credits == [] and not worker.service.uncertain
        assert [r["action"] for r in journal(tmp_path, "dispatch_blocked")] == ["collect:11"]

        http.replies.extend([("/afk/eventList", state), ("/afk/recReward", {"code": 0, "camp_quality": 6000}),
                             ("/afk/recReward", None)])   # SSS by a player of the camp: chips possible
        with pytest.raises(lb.RewardAPIError):
            await worker.check()
        assert credits == [(0, True)] and worker.service.uncertain
        assert [e for e, _ in http.calls].count("/afk/recReward") == 4

        http.replies.extend([("/afk/eventList", listing(row(13, 100006, dp.FINISHED, NOW - 9, 1001), sends=0)),
                             ("/afk/recReward", {"code": 0, "reward_bonus": [10100001]})])   # unreadable egg
        with pytest.raises(lb.RewardAPIError):
            await worker.check()
        assert credits == [(0, True), (0, True)] and worker.service.confirmed_chips == 0
    asyncio.run(run())


def test_a_used_up_list_is_drawn_again_with_a_free_refresh_only(tmp_path):
    async def run():
        used = [row(i, event, 3, NOW - 100, 1001) for i, event in enumerate((100001, 100002, 100007, 100008), 1)]
        worker, http, _, _, clock = setup(tmp_path, [
            ("/afk/eventList", listing(*used, sends=5, refreshes=2, camps=((2, 0), (0, 1)))),
            ("/afk/refresh", {"code": 0}),
            ("/afk/eventList", listing(row(9, 100001), sends=5, refreshes=1)),
        ])
        worker.service.due["dispatch"] = NOW + 300
        await worker.check()
        assert http.calls[1] == ("/afk/refresh", {"camp_id": 0, "item_id": 0})
        assert worker.service.due["dispatch"] == NOW + 5      # the new list is sent out on the next pass
        assert not journal(tmp_path, "dispatch_attempt")

        for state in (
            listing(*used, sends=5, refreshes=0),                                   # no free refresh left
            listing(*used, sends=0, refreshes=2),                                   # nothing may be sent anyway
            listing(*used, sends=5, refreshes=2, camps=((0, 0),)),                  # camp not unlocked
            listing(*used, row(8, 199999), sends=5, refreshes=2),                   # a list the table cannot read
            listing(*[row(i, e, dp.RUNNING, NOW + 99, 1002) for i, e in enumerate((100001, 100002, 100007, 100008), 1)],
                    sends=5, refreshes=2),                                          # every slot under way
        ):
            http.replies.append(("/afk/eventList", state))
            await worker.check()
            assert not http.replies

        # Three refreshes in a day at most, and a refused one is not repeated.
        http.replies.extend([("/afk/eventList", listing(*used, sends=5)), ("/afk/refresh", {"code": -864}),
                             ("/afk/eventList", listing(*used, sends=5))])
        await worker.check()
        await worker.check()
        assert not http.replies and journal(tmp_path, "dispatch_blocked")[0]["action"] == "refresh"
        clock[0] += lb.BLOCK_SEC + 1
        http.replies.extend([("/afk/eventList", listing(*used, sends=5)), ("/afk/refresh", {"code": 0}),
                             ("/afk/eventList", listing(*used, sends=5)),
                             ("/afk/eventList", listing(*used, sends=5))])
        await worker.check()
        await worker.check()
        assert not http.replies and len(journal(tmp_path, "dispatch_refresh")) == dp.MAX_REFRESHES
    asyncio.run(run())


@pytest.mark.parametrize("card, expect_claim", [
    ({"item_num": 31000, "data": {"ordinary": [0, 1], "advanced": []}}, True),           # level 2 is new
    ({"item_num": 31000, "data": {"ordinary": [0, 1, 2], "advanced": []}}, False),
    ({"item_num": 31000, "has_pass_card": True, "data": {"ordinary": [0, 1, 2], "advanced": [0, 1]}}, True),
    ({"item_num": 0, "data": {}}, True),                                                 # level 0 pays a ticket
    ({"item_num": 0, "data": {"ordinary": [0]}}, False),
])
def test_pass_rewards_use_the_claim_all_button_when_a_level_is_open(tmp_path, card, expect_claim):
    async def run():
        replies = [("/afk/eventList", listing(sends=0)), ("/afk/passCardData", {"code": 0, **card})]
        if expect_claim:
            replies.append(("/afk/recPassCardReward", {"code": 0, "item_list": [{"item_id": 10440001, "num": 3}]}))
        worker, http, _, credits, _ = setup(tmp_path, replies)
        worker.pass_due = True
        await worker.check()
        assert not http.replies and not worker.pass_due
        assert http.calls[1] == ("/afk/passCardData", {"t": 1, "immediately": True})
        if expect_claim:
            assert http.calls[2] == ("/afk/recPassCardReward", {"level": 1, "advanced": True, "all": True})
            assert credits == [(0, False)] and journal(tmp_path, "claimed")[0]["kind"] == "dispatch_pass"
        http.replies.append(("/afk/eventList", listing(sends=0)))
        await worker.check()          # not asked again until something was collected
        assert not http.replies
    asyncio.run(run())


def test_goal_rewards_then_the_season_title_and_refusals_stop(tmp_path):
    async def run():
        idle = ("/afk/eventList", listing(sends=0))
        worker, http, _, credits, _ = setup(tmp_path, [
            idle,
            ("/task/dispatchTaskList", {"code": 0, "list": [{"id": 7, "status": 2}, {"id": 8, "status": 2},
                                                             {"id": 9, "status": 3}]}),
            ("/task/recDispatchTaskRw", {"code": 0, "item_list": [{"item_id": 10100001, "num": 20000}]}),
            ("/task/dispatchTaskList", {"code": 0, "list": [{"id": i, "status": 3} for i in (7, 8, 9)]}),
            ("/afk/recSeasonReward", {"code": 0, "season_reward": True, "item_list": [{"item_id": 20406001, "num": 1}]}),
        ])
        worker.tasks_due = True
        await worker.check()
        assert not http.replies and not worker.tasks_due
        assert http.calls[1:] == [("/task/dispatchTaskList", {}), ("/task/recDispatchTaskRw", {"id_arr": [7, 8]}),
                                  ("/task/dispatchTaskList", {}), ("/afk/recSeasonReward", {})]
        assert credits == [(20000, False), (0, False)]

        # A goal still open, or the title already taken: nothing more to ask for.
        for goals in ({"list": [{"id": 7, "status": 3}, {"id": 8, "status": 1}]},
                      {"list": {"a": {"id": 7, "status": 3}}, "season_reward": True}, {"list": []}):
            worker.tasks_due = True
            http.replies.extend([idle, ("/task/dispatchTaskList", {"code": 0, **goals})])
            await worker.check()
            assert not http.replies

        worker.tasks_due = True
        http.replies.extend([idle, ("/task/dispatchTaskList", {"code": 0, "list": [{"id": 5, "status": 2}]}),
                             ("/task/recDispatchTaskRw", {"code": -30}), idle])
        await worker.check()
        await worker.check()
        assert not http.replies and journal(tmp_path, "dispatch_blocked")[0]["action"] == "goals"
    asyncio.run(run())


def test_outside_the_season_or_once_the_list_is_refused_nothing_is_asked(tmp_path):
    async def run():
        # 2026-08-27 10:00 to 2026-11-25 23:00 (UTC+8), as in the client's tpl_constdata.
        for now in (1787795999, 1795618801):
            worker, http, game, *_ = setup(tmp_path, [], now=now)
            worker.pass_due = worker.tasks_due = True
            await worker.check()
            assert not http.calls and not game.asked
        worker, http, _, _, clock = setup(tmp_path, [("/afk/eventList", {"code": -851})], now=1795618800)
        worker.pass_due = worker.tasks_due = True
        await worker.check()
        await worker.check()
        assert not http.replies and journal(tmp_path, "dispatch_blocked")[0]["action"] == "list"
    asyncio.run(run())


def test_the_reward_worker_runs_dispatch_wakes_on_its_push_and_backs_off(tmp_path, monkeypatch):
    from tests.test_headless_rewards import eventually, task_list

    async def run():
        monkeypatch.setattr(sv, "RETRY_SEC", .02)
        monkeypatch.setattr(sv, "RETRY_MAX_SEC", .08)
        calls = []
        down = [False]

        def post(url, payload, **kwargs):
            endpoint = url.removeprefix("https://game.example")
            calls.append(endpoint)
            assert kwargs["token"] == "session-secret" and kwargs["extra_headers"]["Version"] == "1.7.0"
            if endpoint == "/task/list":
                return task_list()
            if endpoint == "/afk/eventList":
                return None if down[0] else listing(sends=0)
            if endpoint == "/afk/passCardData":
                return {"code": 0, "item_num": 0, "data": {"ordinary": [0]}}
            if endpoint == "/task/dispatchTaskList":
                return {"code": 0, "list": [{"id": 1, "status": 1}]}
            assert endpoint == "/activity/rebateStatus", endpoint
            return {"code": 0, "status": 0}

        async def credit(chips, uncertain):
            raise AssertionError("no reward in this script")

        ready = asyncio.Event()
        ready.set()
        svc = sv.RewardService(uid=42, authorization="session-secret", http_base="https://game.example",
                               chnl=3, version="1.7.0", on_credit=credit, ready=ready, post=post,
                               journal_path=tmp_path / "rewards.jsonl")
        svc.observe_server_time(NOW)
        svc.attach(fd.Fund(svc, None))
        svc.attach(tk.Tasks(svc, None))
        svc.attach(dp.Dispatch(svc, Game({}, 0)))
        svc.start()
        await eventually(lambda: "/task/dispatchTaskList" in calls)
        assert calls.count("/afk/eventList") == 1 and calls.count("/afk/passCardData") == 1
        svc.notify(dp.DISPATCH_TASK_REFRESH)          # a goal moved: the goals are read again
        await eventually(lambda: calls.count("/task/dispatchTaskList") == 2)
        assert calls.count("/afk/passCardData") == 1 and calls.count("/task/list") == 1
        down[0] = True
        svc.wake("dispatch", 0)
        await asyncio.sleep(.5)
        await svc.close()
        failed = [r for r in journal(tmp_path, "check_failed") if r["kind"] == "dispatch"]
        assert 3 <= len(failed) <= 12 and failed[0]["endpoint"] == "/afk/eventList" and failed[0]["code"] is None
    asyncio.run(run())
