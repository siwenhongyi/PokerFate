"""灵猫风尚志 (the battle pass): scripted server replies, no real game requests."""
from __future__ import annotations

import asyncio
import re

import pytest

from pf_intercept.headless.lobby.activities import battlepass as bp
from pf_intercept.headless.lobby.core import base as lb
from pf_intercept.headless.lobby.routine import fund as fd
from pf_intercept.headless.lobby.core import needs as nd
from pf_intercept.headless.lobby.core import service as sv
from pf_intercept.headless.lobby.routine import tasks as tk
from pf_intercept.wire import codec
from tests.test_dispatch import TPL, ScriptedHTTP, journal, lua_table

NOW = 1795400000        # inside pass 1001
DETAIL, CLAIM, SHOP = "/task/battlePassDetail", "/task/battlePassClaimReward", "/shop/limit"
GOLD = 10100001
NO_EDITION = (SHOP, {"code": 0, "list": [{"shop_type": 25, "id": 100103, "count": 1},     # the upgrade alone
                                         {"shop_type": 3, "id": 100101, "count": 2},      # another shop
                                         {"shop_type": 25, "id": 100101, "count": 0}]})


class Bag:
    """The socket side: the bag, which holds the pass's inspiration."""

    def __init__(self, exp):
        self.exp, self.asked, self.fail = exp, [], None

    async def activity_request(self, name, fields):
        self.asked.append(name)
        assert (name, fields) == ("ItemList", {})
        if self.fail:
            raise self.fail
        reply = {"item_list": [{"item_id": bp.EXP, "num": self.exp},
                               {"item_id": bp.EXP, "num": 900000, "deadline": NOW - 1},
                               {"item_id": GOLD, "num": 5}]}
        # What the worker gets is the decoded frame: 64-bit counts arrive as strings.
        return codec.decode("pb.ItemListRSP", codec.encode("pb.ItemListRSP", reply))


def setup(tmp_path, replies, *, exp=0, now=NOW):
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
    bag = Bag(exp)
    return bp.BattlePass(svc, bag), http, bag, credits, clock


def task(ident, status):
    return {"id": ident, "task_id": 1010101, "status": status}


def detail(*, free=(), paid=(), weekly=(), season=(), loops=(0, 0), pass_id=1001):
    return (DETAIL, {"code": 0, "battle_pass_id": pass_id, "weekly_list": list(weekly), "list": list(season),
                     "level_free_reward_ids": list(free), "level_paid_reward_ids": list(paid),
                     "loop_times_free": loops[0], "loop_times_paid": loops[1]})


def test_tables_are_read_from_the_client():
    info = lua_table("battle_pass_info")
    assert {int(r["exp_item"]) for r in info} == {bp.EXP}
    levels = {}
    for r in lua_table("battle_pass_level"):
        levels.setdefault(int(r["battle_pass_id"]), []).append((int(r["id"]), int(r["level"]), int(r["exp"])))
    assert levels and all(bp.levels(key) == tuple(rows) for key, rows in levels.items())
    # What the level arithmetic relies on: rising totals, then the single repeating row.
    for rows in levels.values():
        assert [level for _, level, _ in rows] == [*range(1, len(rows)), -1]
        assert [need for _, _, need in rows[:-1]] == sorted({need for _, _, need in rows[:-1]})
    editions = {}
    for r in lua_table("shop_battle_pass"):
        if int(r["level_type"]) in (1, 2):
            shop, goods = editions.setdefault(int(r["battle_pass_id"]), (int(r["shop_type"]), ()))
            assert shop == int(r["shop_type"])
            editions[int(r["battle_pass_id"])] = (shop, goods + (int(r["id"]),))
    assert editions and all(bp.editions(key) == value for key, value in editions.items())
    # The tasks pay inspiration and nothing else, so a task claim is never chips.
    for name in ("battle_pass_tasks_week", "battle_pass_tasks_period"):
        assert all(re.fullmatch(rf"\{{{bp.EXP},\d+\}}", r["rewards"]) for r in lua_table(name))
    enum = (TPL.parent / "app" / "EnumConfig.lua").read_text(encoding="utf-8")
    assert re.search(rf"\bBattlePassExp = {bp.EXP},", enum)
    assert re.search(rf"TaskStatus = \{{[^}}]*\bCompleted = {bp.COMPLETED},", enum)
    pushes = (TPL / "tpl_PushConsts.lua").read_text(encoding="utf-8")
    assert tuple(int(re.search(rf'"{name}",(\d+)', pushes).group(1))
                 for name in ("PASSCARD_TASK_REFRESH", "BATTLE_PASS_START")) == bp.BATTLE_PASS_PUSHES


@pytest.mark.parametrize("exp, free, paid, loops, expect", [
    (0, [], [], (0, 0), ([], [], 0, 0)),
    (999, [], [], (0, 0), ([], [], 0, 0)),
    (1000, [], [], (0, 0), ([1], [], 1, 0)),
    (3500, [1], [], (0, 0), ([2, 3], [1], 3, 0)),                 # level 1's paid reward waits for an owner
    (3500, [1, 2, 3], [1, 2, 3], (0, 0), ([], [], 3, 0)),
    (70999, range(1, 71), range(1, 71), (0, 0), ([], [], 70, 0)),  # past the last level, no repeat yet
    (72999, range(1, 71), range(1, 71), (1, 1), ([71], [], 70, 2)),
    (72999, range(1, 71), range(1, 71), (2, 1), ([], [71], 70, 2)),
    (72999, range(1, 71), range(1, 71), (2, 2), ([], [], 70, 2)),
    (10 ** 7, [], [], (0, 0), ([*range(1, 72)], [], 70, 9930)),
])
def test_levels_due(exp, free, paid, loops, expect):
    state = detail(free=free, paid=paid, loops=loops)[1]
    assert bp.levels_due(state, exp) == expect
    # The client walks these lists with pairs(): a map of the same values reads the same.
    state.update(level_free_reward_ids={str(n): v for n, v in enumerate(free)},
                 level_paid_reward_ids={str(n): v for n, v in enumerate(paid)})
    assert bp.levels_due(state, exp) == expect


def test_finished_tasks_are_collected_with_the_claim_all_request(tmp_path):
    async def run():
        worker, http, bag, credits, _ = setup(tmp_path, [
            detail(weekly=[task(7, 2), task(8, 1)], season=[task(9, 2), task(10, 3)]),
            (CLAIM, {"code": 0}),
            detail(weekly=[task(7, 3), task(8, 1)], season=[task(9, 3), task(10, 3)]),
        ], exp=500)
        await worker.check()
        assert not http.replies
        assert http.calls == [(DETAIL, {}), (CLAIM, {"type": 0}), (DETAIL, {})]
        # Inspiration is not money.
        assert credits == [] and worker.service.confirmed_chips == 0 and not worker.service.uncertain
        result, = journal(tmp_path, "activity_result")
        assert (result["kind"], result["chips"], result["tasks"]) == ("battlepass_tasks", 0, 2)
        # What the answers said is journalled when it changes, with the field names the server used.
        first, second = journal(tmp_path, "battlepass_state")
        assert (first["pass_id"], first["known"], first["tasks"]) == (1001, True, {"1": 1, "2": 2, "3": 1})
        assert second["tasks"] == {"1": 1, "3": 3}
        assert first["row_fields"] == ["id", "status", "task_id"] and "level_free_reward_ids" in first["fields"]
        levels, = journal(tmp_path, "battlepass_levels")
        assert (levels["exp"], levels["level"], levels["due"]) == (500, 0, [])
        assert bag.asked == ["ItemList"]
        assert not journal(tmp_path, "battlepass_blocked")
    asyncio.run(run())


def test_each_tasks_standing_is_journalled_when_a_status_changes_not_with_every_hand(tmp_path):
    def hands(done, status):
        return {"id": 5, "task_id": 1010201, "status": status, "current_value": done, "value": [10010101, 10]}

    async def run():
        signed = {"id": 4, "task_id": 1010101, "status": 1, "current_value": 1, "value": [2]}
        worker, http, _, _, _ = setup(tmp_path, [
            detail(weekly=[hands(3, 1), signed]),
            detail(weekly=[hands(7, 1), signed]),       # four more hands: progress only
            detail(weekly=[hands(10, 2), signed]), (CLAIM, {"code": 0}), detail(weekly=[hands(10, 3), signed]),
        ])
        await worker.check()
        await worker.check()
        first, = journal(tmp_path, "battlepass_tasks")
        assert first["rows"] == [[1010101, 1, 1, [2]], [1010201, 1, 3, [10010101, 10]]]
        await worker.check()
        assert [entry["rows"][1][:3] for entry in journal(tmp_path, "battlepass_tasks")] == [
            [1010201, 1, 3], [1010201, 2, 10], [1010201, 3, 10]]
        # A restart says it again.
        http.replies.append(detail(weekly=[hands(10, 3), signed]))
        await bp.BattlePass(worker.service, worker.session).check()
        assert not http.replies and len(journal(tmp_path, "battlepass_tasks")) == 4
    asyncio.run(run())


def test_reached_levels_are_collected_and_their_chips_are_reward_money(tmp_path):
    async def run():
        worker, http, bag, credits, clock = setup(tmp_path, [
            detail(free=[1]),
            NO_EDITION,
            (CLAIM, {"code": 0, "item_list": [{"item_id": 30200002, "num": 1}, {"item_id": GOLD, "num": 30000}]}),
            detail(free=[1, 2, 3]),
        ], exp=3500)
        await worker.check()
        assert not http.replies
        # The expired pieces in the bag do not count: 3500, level 3.
        assert http.calls[1:3] == [(SHOP, {"mask": "shopLimit"}), (CLAIM, {"type": 3, "id_arr": [2, 3]})]
        assert credits == [(30000, False)] and worker.service.confirmed_chips == 30000
        claimed, = journal(tmp_path, "claimed")
        assert (claimed["kind"], claimed["chips"], claimed["request"]) == (
            "battlepass_levels", 30000, {"type": 3, "id_arr": [2, 3]})
        levels, = journal(tmp_path, "battlepass_levels")
        assert (levels["exp"], levels["level"], levels["due"], levels["owned"]) == (3500, 3, [2, 3], False)
        # Nothing new: one read. "No paid edition" is believed for an hour, then asked again.
        http.replies.append(detail(free=[1, 2, 3]))
        await worker.check()
        clock[0] += bp.UNLOCK_TTL_SEC + 1
        http.replies.extend([detail(free=[1, 2, 3]), NO_EDITION])
        await worker.check()
        assert not http.replies and credits == [(30000, False)] and bag.asked == ["ItemList"] * 3
    asyncio.run(run())


def test_an_owner_of_a_paid_edition_also_collects_the_paid_rewards(tmp_path):
    async def run():
        worker, http, _, credits, clock = setup(tmp_path, [
            detail(free=[1]),
            (SHOP, {"code": 0, "list": {"a": {"shop_type": 25, "id": 100102, "count": 1}}}),
            (CLAIM, {"code": 0, "reward_chips": 150000, "item_list": [{"item_id": 30200003, "num": 1}]}),
            # Level 2 was asked for both rewards and only the free one came.
            detail(free=[1, 2], paid=[1]),
        ], exp=2000)
        await worker.check()
        assert http.calls[2] == (CLAIM, {"type": 3, "id_arr": [1, 2]}) and credits == [(150000, False)]
        assert not journal(tmp_path, "battlepass_blocked")
        # It is asked for again as the owner's; the purchase is not looked up a second time.
        clock[0] += 10 * bp.UNLOCK_TTL_SEC
        http.replies.extend([detail(free=[1, 2], paid=[1]),
                             (CLAIM, {"code": 0, "item_list": [{"item_id": 30200004, "num": 1}]}),
                             detail(free=[1, 2], paid=[1, 2])])
        await worker.check()
        assert not http.replies and http.calls[-2] == (CLAIM, {"type": 3, "id_arr": [2]})
        assert journal(tmp_path, "battlepass_levels")[-1]["owned"] is True
        assert not journal(tmp_path, "battlepass_blocked")
    asyncio.run(run())


def test_the_repeating_reward_is_asked_for_when_a_repeat_was_earned(tmp_path):
    async def run():
        full = list(range(1, 71))
        worker, http, _, credits, _ = setup(tmp_path, [
            detail(free=full, loops=(1, 0)),
            NO_EDITION,
            (CLAIM, {"code": 0, "item_list": [{"item_id": GOLD, "num": 10000}]}),
            detail(free=full, loops=(2, 0)),
            detail(free=full, loops=(2, 0)),
        ], exp=72999)
        await worker.check()
        assert http.calls[2] == (CLAIM, {"type": 3, "id_arr": [71]}) and credits == [(10000, False)]
        await worker.check()        # two repeats earned, two collected: nothing to ask for
        assert not http.replies and not journal(tmp_path, "battlepass_blocked")
    asyncio.run(run())


@pytest.mark.parametrize("reply, now, known", [
    ((DETAIL, {"code": 0}), NOW, False),                        # no pass is running
    (detail(pass_id=1002, weekly=[task(7, 2)]), NOW, False),    # a pass this table does not have
    (detail(weekly=[task(7, 2)]), 1800212401, True),            # over: 2027-01-18 03:00:01 UTC+8
])
def test_without_a_pass_this_worker_knows_nothing_more_is_asked(tmp_path, reply, now, known):
    async def run():
        worker, http, bag, credits, _ = setup(tmp_path, [reply, reply], exp=5000, now=now)
        await worker.check()
        await worker.check()
        assert not http.replies and [endpoint for endpoint, _ in http.calls] == [DETAIL, DETAIL]
        assert bag.asked == [] and credits == []
        state, = journal(tmp_path, "battlepass_state")     # said once, not on every pass
        assert state["known"] is known
    asyncio.run(run())


def test_the_last_second_of_the_pass_still_counts(tmp_path):
    async def run():
        worker, http, _, _, _ = setup(tmp_path, [detail(weekly=[task(7, 2)]), (CLAIM, {"code": 0}),
                                                 detail(weekly=[task(7, 3)])], now=1800212400)
        await worker.check()
        assert not http.replies
    asyncio.run(run())


def test_a_refused_claim_is_left_alone_even_after_a_restart(tmp_path):
    async def run():
        ready = detail(weekly=[task(7, 2)])
        worker, http, bag, _, clock = setup(tmp_path, [ready, (CLAIM, {"code": -9001}), ready], exp=0)
        await worker.check()
        await worker.check()        # the task still waits; the claim is not sent again
        assert not http.replies
        blocked, = journal(tmp_path, "battlepass_blocked")
        assert (blocked["action"], blocked["code"], blocked["until"]) == ("tasks", -9001, NOW + lb.BLOCK_SEC)
        # The levels are a different action and went on.
        assert bag.asked == ["ItemList"] * 2
        restarted = bp.BattlePass(worker.service, bag)
        clock[0] = NOW + lb.BLOCK_SEC - 1
        http.replies.append(ready)
        await restarted.check()
        assert not http.replies
        clock[0] = NOW + lb.BLOCK_SEC + 1
        http.replies.extend([ready, (CLAIM, {"code": 0}), detail(weekly=[task(7, 3)])])
        await restarted.check()
        assert not http.replies
    asyncio.run(run())


def test_a_refused_read_stops_everything(tmp_path):
    async def run():
        worker, http, bag, _, _ = setup(tmp_path, [(DETAIL, {"code": -1})], exp=5000)
        await worker.check()
        await worker.check()
        assert not http.replies and bag.asked == []
        assert journal(tmp_path, "battlepass_blocked")[0]["action"] == "detail"
    asyncio.run(run())


def test_a_claim_that_leaves_its_reward_due_is_not_repeated(tmp_path):
    async def run():
        ready = detail(weekly=[task(7, 2), task(8, 2)])
        worker, http, _, credits, _ = setup(tmp_path, [
            ready, (CLAIM, {"code": 0}), detail(weekly=[task(7, 2), task(8, 3)]),      # 7 was not collected
            (CLAIM, {"code": 0, "item_list": [{"item_id": GOLD, "num": 30000}]}),
            detail(weekly=[task(7, 2), task(8, 3)], free=[1]),                         # nor were levels 2 and 3
        ], exp=3000)
        worker.edition = (1001, False, NOW)
        await worker.check()
        assert not http.replies and credits == [(30000, False)]
        tasks, levels = journal(tmp_path, "battlepass_blocked")
        assert (tasks["action"], tasks["code"]) == ("tasks", "still due: 7")
        assert (levels["action"], levels["code"]) == ("levels", "still due: 2,3")
        http.replies.append(detail(weekly=[task(7, 2), task(8, 3)], free=[1]))
        await worker.check()        # both wait; neither claim is sent again
        assert not http.replies and len(journal(tmp_path, "battlepass_blocked")) == 2
    asyncio.run(run())


def test_an_unanswered_level_claim_is_doubted_and_an_unanswered_task_claim_is_not(tmp_path):
    async def run():
        worker, http, _, credits, _ = setup(tmp_path, [detail(), (CLAIM, None)], exp=1000)
        worker.edition = (1001, False, NOW)
        with pytest.raises(lb.RewardAPIError):
            await worker.check()
        assert credits == [(0, True)] and worker.service.uncertain
        assert journal(tmp_path, "claim_uncertain")[0]["kind"] == "battlepass_levels"
        assert not journal(tmp_path, "battlepass_blocked")
        # The next pass reads the pass again; the levels the read shows as taken are not asked for.
        http.replies.append(detail(free=[1]))
        await worker.check()
        assert not http.replies and http.calls[-1] == (DETAIL, {})
    asyncio.run(run())

    async def tasks():
        worker, http, _, credits, _ = setup(tmp_path / "tasks", [detail(weekly=[task(7, 2)]), (CLAIM, None)])
        with pytest.raises(lb.RewardAPIError):
            await worker.check()
        assert credits == [] and not worker.service.uncertain       # a task pays no chips
    asyncio.run(tasks())


def test_a_task_answer_with_an_unreadable_amount_is_doubted(tmp_path):
    async def run():
        worker, http, _, credits, _ = setup(tmp_path, [
            detail(weekly=[task(7, 2)]), (CLAIM, {"code": 0, "item_list": [{"item_id": GOLD, "num": -5}]})])
        with pytest.raises(lb.RewardAPIError):
            await worker.check()
        assert credits == [(0, True)] and worker.service.uncertain
    asyncio.run(run())

    async def chips():
        worker, http, _, credits, _ = setup(tmp_path / "chips", [
            detail(weekly=[task(7, 2)]), (CLAIM, {"code": 0, "reward_chips": 700, "item_list": []}),
            detail(weekly=[task(7, 3)])])
        await worker.check()
        assert credits == [(700, False)] and journal(tmp_path / "chips", "claimed")[0]["kind"] == "battlepass_tasks"
    asyncio.run(chips())


def test_a_bag_that_cannot_be_read_does_not_hold_back_the_tasks(tmp_path):
    async def run():
        worker, http, bag, _, _ = setup(tmp_path, [
            detail(weekly=[task(7, 2)]), (CLAIM, {"code": 0}), detail(weekly=[task(7, 3)])], exp=9000)
        bag.fail = lb.RewardAPIError("ItemList", "offline")
        with pytest.raises(lb.RewardAPIError):
            await worker.check()
        assert not http.replies and [endpoint for endpoint, _ in http.calls] == [DETAIL, CLAIM, DETAIL]
    asyncio.run(run())


def test_the_reward_worker_runs_the_pass_wakes_on_its_pushes_and_backs_off(tmp_path, monkeypatch):
    from tests.test_headless_rewards import eventually, task_list

    async def run():
        monkeypatch.setattr(sv, "RETRY_SEC", .02)
        monkeypatch.setattr(sv, "RETRY_MAX_SEC", .08)
        calls = []
        down = [False]

        def post(url, payload, **kwargs):
            endpoint = url.removeprefix("https://game.example")
            calls.append(endpoint)
            assert kwargs["token"] == "session-secret"
            if endpoint == "/task/list":
                return task_list()
            if endpoint == DETAIL:
                return None if down[0] else detail()[1]
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
        svc.attach(bp.BattlePass(svc, Bag(0)))
        svc.start()
        await eventually(lambda: calls.count(DETAIL) == 1)
        for push in (10039, 10085):             # a task moved, or a pass started: read again
            before = calls.count(DETAIL)
            svc.notify(push)
            await eventually(lambda: calls.count(DETAIL) == before + 1)
        assert calls.count("/task/list") == 1
        down[0] = True
        svc.wake("battlepass", 0)
        await asyncio.sleep(.5)
        await svc.close()
        failed = [r for r in journal(tmp_path, "check_failed") if r["kind"] == "battlepass"]
        assert 3 <= len(failed) <= 12 and failed[0]["endpoint"] == DETAIL and failed[0]["code"] is None
    asyncio.run(run())
