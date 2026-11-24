"""每日签到: scripted server replies, no real game requests."""
from __future__ import annotations

import asyncio

import pytest

from pf_intercept.headless.lobby.core import base as lb
from pf_intercept.headless.lobby.routine import fund as fd
from pf_intercept.headless.lobby.core import needs as nd
from pf_intercept.headless.lobby.core import service as sv
from pf_intercept.headless.lobby.routine import tasks as tk
from pf_intercept.headless.lobby.routine import signin as si
from tests.test_dispatch import TPL, ScriptedHTTP, journal

NOW = 1795400000
CYCLE = NOW - 3 * 86400 - 5000      # the cycle began three days and a bit ago: today is day 4
MIDNIGHT = NOW + 40000              # when the server says the next sign-in opens
DATA, SIGN = "/activity/sevenSignData", "/activity/sevenSign"
GOLD = 10100001


def setup(tmp_path, replies, now=NOW):
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
    svc.first_pass.set()        # the reward service has run every check once
    return si.SignIn(svc, None), http, credits, clock


def state(days, *, next_ts=NOW - 100, **extra):
    return (DATA, {"code": 0, "days": list(days), "next_sign_ts": next_ts, "miss_sign_cnt": 0,
                   "cur_ts": NOW, "cycle_ts": CYCLE, "sign_item_list": [], "total_item_list": [], **extra})


def signed(days, **rewards):
    return (SIGN, {"code": 0, "days": list(days), "next_sign_ts": MIDNIGHT, "miss_sign_cnt": 0, **rewards})


def test_the_requests_are_the_clients():
    model = TPL.parent / "app" / "model" / "SignInModel.lua"
    if not model.exists():
        pytest.skip("client code not checked out")
    source = model.read_text(encoding="utf-8")
    assert 'Net:post("activity/sevenSignData", nil,' in source
    assert 'Net:post("activity/sevenSign", {day = day or 0},' in source
    assert "math.ceil((data.cur_ts - data.cycle_ts) / 86400)" in source
    page = (TPL.parent / "app" / "views" / "Activity" / "ActivitySignIn.lua").read_text(encoding="utf-8")
    assert "SignInModel:sendSignIn(0)" in page       # what opening the page sends for today


@pytest.mark.parametrize("cur, cycle, day", [
    (NOW, NOW - 1, 1), (NOW, NOW - 86400, 1), (NOW, NOW - 86401, 2), (NOW, CYCLE, 4),
    (NOW, NOW, 0), (NOW, NOW + 5, 0), (NOW, 0, 0), (0, CYCLE, 0), (None, None, 0), ("x", CYCLE, 0),
])
def test_today(cur, cycle, day):
    assert si.today({"cur_ts": cur, "cycle_ts": cycle}) == day


def test_the_day_is_signed_once_and_every_chip_of_it_is_reward_money(tmp_path):
    async def run():
        worker, http, credits, clock = setup(tmp_path, [
            state([1, 3]),                  # day 2 was missed; today is day 4
            signed([1, 3, 4], item_list=[{"item_id": GOLD, "num": 2000}, {"item_id": 11400001, "num": 1}],
                   total_item_list={"a": {"item_id": GOLD, "num": 500}},
                   ext_item_list=[{"item_id": GOLD, "num": "300"}]),
        ])
        await worker.check()
        assert not http.replies
        # Today only: the missed day is not made up.
        assert http.calls == [(DATA, {}), (SIGN, {"day": 0})]
        assert credits == [(2800, False)] and worker.service.confirmed_chips == 2800
        claimed, = journal(tmp_path, "claimed")
        assert (claimed["kind"], claimed["chips"], claimed["day"]) == ("signin", 2800, 4)
        assert claimed["items"] == [[GOLD, 2000], [11400001, 1], [GOLD, 500], [GOLD, 300]]
        said, = journal(tmp_path, "signin_state")
        assert (said["day"], said["days"], said["made_up"]) == (4, [1, 3], 0) and "cycle_ts" in said["fields"]
        # Nothing is asked again before the time the server gave for the next sign-in.
        clock[0] = MIDNIGHT - 1
        await worker.check()
        assert not http.replies
        clock[0] = MIDNIGHT + 1
        http.replies.append(state([1, 3, 4], next_ts=MIDNIGHT + 86400))
        await worker.check()
        assert not http.replies and credits == [(2800, False)]
    asyncio.run(run())


def test_the_sign_in_waits_until_every_task_list_was_read_in_the_new_day(tmp_path):
    """A list may start its day or week when it is first read; a sign-in before that is lost."""
    async def run():
        start = lb.day_start(NOW)                           # 03:00 UTC+8 of the game day
        worker, http, credits, clock = setup(tmp_path, [state([]), state([])], now=start + 120)
        svc = worker.service
        svc.first_pass.clear()                              # a fresh start: not every check has run yet
        svc.due["signin"] = start + 400                       # as the worker loop sets it before a check
        await worker.check()
        assert [endpoint for endpoint, _ in http.calls] == [DATA] and svc.due["signin"] == start + 120 + si.WAIT_SEC
        svc.first_pass.set()
        # The board holds two lists; the pass's was last read a minute before the day turned.
        clock[0] = start - 60
        svc.needs.want("battlepass", [])
        clock[0] = start + 130
        svc.needs.want("tasks", [])
        for kind in ("tasks", "battlepass"):
            svc.due[kind] = start + 400
        await worker.check()
        assert [endpoint for endpoint, _ in http.calls] == [DATA, DATA]   # not signed yet
        assert svc.due["battlepass"] == svc.due["tasks"] == start + 130       # both asked to read again
        assert journal(tmp_path, "signin_waiting")[-1]["for_lists"] == ["battlepass"]
        # The pass reads its list: now the day is signed.
        svc.needs.want("battlepass", [])
        http.replies.extend([state([]), signed([4], item_list=[{"item_id": GOLD, "num": 100}])])
        await worker.check()
        assert not http.replies and http.calls[-1] == (SIGN, {"day": 0}) and credits == [(100, False)]
    asyncio.run(run())


def test_a_signed_day_is_left_alone(tmp_path):
    async def run():
        # Signed already; the server names no later time, so it is looked at again in an hour.
        worker, http, credits, clock = setup(tmp_path, [state([4])])
        await worker.check()
        await worker.check()
        clock[0] += si.RECHECK_SEC - 1
        await worker.check()
        assert not http.replies and http.calls == [(DATA, {})] and credits == []
        clock[0] += 2
        http.replies.append(state([4], next_ts=MIDNIGHT))
        await worker.check()
        clock[0] = MIDNIGHT - 1
        await worker.check()
        assert not http.replies and len(http.calls) == 2
        assert not journal(tmp_path, "claimed", "activity_result")
    asyncio.run(run())


def test_a_sign_in_without_chips_is_a_result_not_money(tmp_path):
    async def run():
        worker, http, credits, _ = setup(tmp_path, [state([]), signed([4], item_list=[{"item_id": 11400001, "num": 2}])])
        await worker.check()
        result, = journal(tmp_path, "activity_result")
        assert (result["kind"], result["chips"], result["items"]) == ("signin", 0, [[11400001, 2]])
        assert credits == []
    asyncio.run(run())


@pytest.mark.parametrize("reply", [
    (DATA, {"code": 0, "days": [1], "next_sign_ts": 0}),                             # no cycle in the answer
    (DATA, {"code": 0, "days": [1], "cur_ts": NOW, "cycle_ts": NOW + 9}),            # a cycle that has not begun
])
def test_nothing_is_signed_when_the_day_cannot_be_told(tmp_path, reply):
    async def run():
        worker, http, credits, _ = setup(tmp_path, [reply, reply])
        await worker.check()
        await worker.check()
        assert not http.replies and [endpoint for endpoint, _ in http.calls] == [DATA, DATA]
        assert journal(tmp_path, "signin_state")[0]["day"] == 0 and credits == []
    asyncio.run(run())


def test_a_refused_sign_in_is_left_alone_even_after_a_restart(tmp_path):
    async def run():
        worker, http, credits, clock = setup(tmp_path, [state([]), (SIGN, {"code": -3001}), state([])])
        await worker.check()
        await worker.check()        # still unsigned; the request is not sent again
        assert not http.replies and credits == []
        blocked, = journal(tmp_path, "signin_blocked")
        assert (blocked["action"], blocked["code"], blocked["until"]) == ("sign", -3001, NOW + lb.BLOCK_SEC)
        restarted = si.SignIn(worker.service, None)
        clock[0] = NOW + lb.BLOCK_SEC - 1
        http.replies.append(state([]))
        await restarted.check()
        assert not http.replies
        clock[0] = NOW + lb.BLOCK_SEC + 1
        http.replies.extend([state([]), signed([4])])
        await restarted.check()
        assert not http.replies and http.calls[-1] == (SIGN, {"day": 0})
    asyncio.run(run())


def test_a_refused_read_stops_everything(tmp_path):
    async def run():
        worker, http, _, _ = setup(tmp_path, [(DATA, {"code": -1})])
        await worker.check()
        await worker.check()
        assert not http.replies and journal(tmp_path, "signin_blocked")[0]["action"] == "data"
    asyncio.run(run())


def test_an_answer_that_leaves_the_day_open_is_not_repeated(tmp_path):
    async def run():
        worker, http, credits, _ = setup(tmp_path, [
            state([1]), signed([1], item_list=[{"item_id": GOLD, "num": 100}]), state([1])])
        await worker.check()
        await worker.check()
        assert not http.replies and credits == [(100, False)]
        blocked, = journal(tmp_path, "signin_blocked")
        assert (blocked["action"], blocked["code"]) == ("sign", "still due: day 4")
    asyncio.run(run())


def test_an_unanswered_or_unreadable_sign_in_is_doubted_and_read_again(tmp_path):
    async def run(folder, answer):
        worker, http, credits, _ = setup(folder, [state([]), (SIGN, answer)])
        with pytest.raises(lb.RewardAPIError):
            await worker.check()
        assert credits == [(0, True)] and worker.service.uncertain
        assert journal(folder, "claim_uncertain")[0]["kind"] == "signin"
        assert not journal(folder, "signin_blocked")
        # The next pass reads the state first; the day now shows as signed and is not signed again.
        http.replies.append(state([4], next_ts=MIDNIGHT))
        await worker.check()
        assert not http.replies and http.calls[-1] == (DATA, {})
    asyncio.run(run(tmp_path / "lost", None))
    asyncio.run(run(tmp_path / "amount", {"code": 0, "days": [4], "item_list": [{"item_id": GOLD, "num": -1}]}))
    asyncio.run(run(tmp_path / "shape", {"code": 0, "days": [4], "item_list": [{"num": 5}]}))


def test_it_runs_in_the_reward_worker_before_the_activities_and_backs_off(tmp_path, monkeypatch):
    from pf_intercept.headless.lobby.activities import battlepass as bp
    from tests.test_headless_rewards import eventually, task_list

    async def run():
        monkeypatch.setattr(sv, "RETRY_SEC", .02)
        monkeypatch.setattr(sv, "RETRY_MAX_SEC", .08)
        calls = []
        down = [False]

        def post(url, payload, **kwargs):
            endpoint = url.removeprefix("https://game.example")
            calls.append(endpoint)
            if endpoint == "/task/list":
                return task_list()
            if endpoint == DATA:
                return None if down[0] else state([4], next_ts=0)[1]
            if endpoint == "/task/battlePassDetail":
                return {"code": 0}
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
        svc.attach(si.SignIn(svc, None))
        svc.attach(bp.BattlePass(svc, None))
        svc.start()
        await eventually(lambda: "/task/battlePassDetail" in calls)
        assert calls.index("/task/list") < calls.index(DATA) < calls.index("/task/battlePassDetail")
        down[0] = True
        svc.workers["signin"].signed_until = 0
        svc.due["signin"] = 0
        svc._wake.set()
        await asyncio.sleep(.5)
        await svc.close()
        failed = [r for r in journal(tmp_path, "check_failed") if r["kind"] == "signin"]
        assert 3 <= len(failed) <= 12 and failed[0]["endpoint"] == DATA and failed[0]["code"] is None
    asyncio.run(run())
