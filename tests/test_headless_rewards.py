"""Reward lifecycle tests: scripted server replies, no real game requests."""
from __future__ import annotations

import asyncio
import copy
import json
import threading
from collections import deque
from datetime import datetime

import pytest

from pf_intercept.headless import rewards as rw


def task_list(**updates):
    return {"code": 0, "daily_list": [], "weekly_list": [], "challenge_list": [],
            "point_data": {}, "daily_point_conf_list": [], "weekly_point_conf_list": [], **updates}


class ScriptedHTTP:
    def __init__(self, replies):
        self.replies = deque(replies)
        self.calls = []

    def __call__(self, url, payload, **kwargs):
        self.calls.append((url, payload, kwargs))
        endpoint, response = self.replies.popleft()
        assert url == "https://game.example" + endpoint
        return copy.deepcopy(response)


def service(tmp_path, post):
    credits = []

    async def credit(chips, uncertain):
        credits.append((chips, uncertain))

    ready = asyncio.Event()
    s = rw.RewardService(uid=42, authorization="session-secret", http_base="https://game.example/",
                         chnl=3, version="1.7.4", on_credit=credit, ready=ready,
                         post=post, journal_path=tmp_path / "rewards.jsonl")
    return s, ready, credits


async def eventually(predicate, timeout=2):
    async def wait():
        while not predicate():
            await asyncio.sleep(.005)
    await asyncio.wait_for(wait(), timeout)


@pytest.mark.parametrize("stamp, expected", [
    ("2026-11-09T06:59:59+08:00", "2026-11-09T07:00:00+08:00"),
    ("2026-11-09T07:00:00+08:00", "2026-11-09T19:00:00+08:00"),
    ("2026-11-09T18:59:59+08:00", "2026-11-09T19:00:00+08:00"),
    ("2026-11-09T19:00:00+08:00", "2026-11-10T07:00:00+08:00"),
])
def test_fund_boundaries_are_utc8(stamp, expected):
    assert rw.next_fund_boundary(datetime.fromisoformat(stamp).timestamp()) == datetime.fromisoformat(expected).timestamp()


def test_fund_claim_credentials_logging_and_state_recheck(tmp_path):
    async def run():
        http = ScriptedHTTP([
            ("/activity/rebateStatus", {"code": 0, "status": 1}),
            ("/activity/rebate", {"code": 0, "status": 1, "reward": 1234}),
            ("/activity/rebateStatus", {"code": 0, "status": 0}),
            ("/activity/rebateStatus", {"code": 0, "status": 0}),
        ])
        s, _, credits = service(tmp_path, http)
        await s.check_fund()
        await s.check_fund()
        assert credits == [(1234, False)]
        assert s.claims == 1
        assert http.calls[1][1] == {"t": 1, "immediately": True}
        for _, _, args in http.calls:
            assert args["token"] == "session-secret"
            assert args["chnl"] == 3
            assert args["extra_headers"]["Version"] == "1.7.4"
        journal = (tmp_path / "rewards.jsonl").read_text()
        assert "session-secret" not in journal
        assert json.loads(journal)["chips"] == 1234
    asyncio.run(run())


def test_fund_settling_waits_then_claims(tmp_path):
    async def run():
        http = ScriptedHTTP([
            ("/activity/rebateStatus", {"code": 0, "status": 1}),
            ("/activity/rebate", {"code": 0, "status": 2}),
            ("/activity/rebateStatus", {"code": 0, "status": 0}),
        ])
        s, _, credits = service(tmp_path, http)
        s._fund_due = s.now() + 300
        await s.check_fund()
        assert not credits
        assert s._fund_due <= s.now() + rw.RETRY_SEC
        assert s._settling_until > s.now()
    asyncio.run(run())


@pytest.mark.parametrize("card_exp, expected_ids", [(0, [71]), (4_000_000_000, [71, 72])])
def test_tasks_filter_eligibility_use_instance_ids_and_claim_new_point_chests(tmp_path, card_exp, expected_ids):
    async def run():
        initial = task_list(
            daily_list=[{"id": 71, "task_id": 10, "status": 2},
                        {"id": 72, "task_id": 11, "status": 2, "monthly_card_task": True},
                        {"id": 73, "status": 1}, {"id": 74, "status": 3}],
            weekly_list=[{"id": 81, "status": 2}],
            challenge_list=[{"id": 91, "status": 2}],
        )
        after_daily = task_list(
            weekly_list=[{"id": 81, "status": 2}],
            point_data={"daily_point": 60, "daily_reward_id_list": [1]},
            daily_point_conf_list=[{"id": 1, "reward_point": 30}, {"id": 2, "reward_point": 60},
                                   {"id": 3, "reward_point": 100}],
        )
        after_chest = copy.deepcopy(after_daily)
        after_chest["point_data"]["daily_reward_id_list"] = [1, 2]
        http = ScriptedHTTP([
            ("/task/list", initial),
            ("/player/payInfo", {"code": 0, "data": {"monthly_card_exp": card_exp}}),
            ("/task/recReward", {"code": 0, "reward_chips": 100, "reward_point": 30, "item_list": []}),
            ("/task/list", after_daily),
            ("/task/recPointReward", {"code": 0, "item_list": [{"item_id": rw.GOLD, "num": 200}, {"item_id": 99, "num": 3}]}),
            ("/task/list", after_chest),
            ("/task/recReward", {"code": 0, "reward_chips": 300, "item_list": []}),
            ("/task/list", task_list()),
        ])
        s, _, credits = service(tmp_path, http)
        await s.check_tasks()
        assert http.calls[2][1] == {"task_cate": 1, "id_arr": expected_ids, "all": False}
        assert http.calls[4][1] == {"id": 2, "task_cate": 1}
        assert http.calls[6][1] == {"task_cate": 2, "id_arr": [81], "all": False}
        assert credits == [(100, False), (200, False), (300, False)]
        assert not http.replies
    asyncio.run(run())


def test_claim_timeout_requeries_instead_of_replaying_and_flags_unknown_profit(tmp_path):
    async def run():
        http = ScriptedHTTP([
            ("/task/list", task_list(daily_list=[{"id": 7, "status": 2}])),
            ("/task/recReward", None),  # server may have credited despite lost reply
            ("/task/list", task_list(daily_list=[{"id": 7, "status": 3}])),
        ])
        s, _, credits = service(tmp_path, http)
        with pytest.raises(rw.RewardAPIError):
            await s.check_tasks()
        await s.check_tasks()
        assert credits == [(0, True)]
        assert s.uncertain and s.claims == 0
        assert sum(url.endswith('/task/recReward') for url, *_ in http.calls) == 1
    asyncio.run(run())


def test_challenge_and_chest_credit_confirmed_chips_only(tmp_path):
    async def run():
        pending = task_list(challenge_list=[
            {"id": 91, "task_id": 7, "status": 2},
            {"id": 92, "status": 2, "monthly_card_task": True},
            {"id": 93, "status": 1},
        ])
        chest = task_list(point_data={"challenge_point": 20, "challenge_reward_id_list": [1]},
                          challenge_point_conf_list=[{"id": 1, "reward_point": 10},
                                                     {"id": 2, "reward_point": 20}])
        http = ScriptedHTTP([
            ("/task/list", pending), ("/player/payInfo", {"code": 0, "data": {"monthly_card_exp": 0}}),
            ("/task/recReward", {"code": 0, "reward_chips": 120, "reward_point": 20}),
            ("/task/list", chest),
            ("/task/recPointReward", {"code": 0, "item_list": [{"item_id": rw.GOLD, "num": 250},
                                                               {"item_id": 99, "num": 10}]}),
            ("/task/list", task_list()),
        ])
        s, _, credits = service(tmp_path, http)
        await s.check_tasks()
        assert http.calls[2][1] == {"task_cate": 6, "id_arr": [91], "all": False}
        assert http.calls[4][1] == {"task_cate": 6, "id": 2}
        assert credits == [(120, False), (250, False)] and s.confirmed_chips == 370
        assert not http.replies
    asyncio.run(run())


def test_auth_failure_pauses_http_until_new_session(tmp_path):
    async def run():
        http = ScriptedHTTP([("/activity/rebateStatus", {"code": -2})])
        s, ready, credits = service(tmp_path, http)
        ready.set()
        s.start()
        await eventually(lambda: s._task.done())
        s.notify(rw.TASK_REFRESH)
        s.notify(rw.GAME_REBATE_SETTLE)
        await s.close()
        assert len(http.calls) == 1 and not credits
        assert s._auth_failed
    asyncio.run(run())


def test_startup_waits_for_baseline_then_pushes_wake_and_coalesce(tmp_path):
    async def run():
        http = ScriptedHTTP([
            ("/activity/rebateStatus", {"code": 0, "status": 0}),
            ("/task/list", task_list()),
            ("/task/list", task_list()),
            ("/activity/rebateStatus", {"code": 0, "status": 1}),
            ("/activity/rebate", {"code": 0, "status": 1, "reward": 10}),
            ("/activity/rebateStatus", {"code": 0, "status": 0}),
        ])
        s, ready, credits = service(tmp_path, http)
        s.start()
        await asyncio.sleep(.02)
        assert not http.calls
        ready.set()
        await eventually(lambda: len(http.calls) == 2)
        for _ in range(20):
            s.notify(rw.TASK_REFRESH)
        await eventually(lambda: len(http.calls) == 3)
        s.notify(rw.GAME_REBATE_SETTLE)
        await eventually(lambda: len(http.calls) == 6)
        await s.close()
        assert credits == [(10, False)]
        assert not http.replies
    asyncio.run(run())


def test_cross_phase_and_poll_fallback_without_push(tmp_path, monkeypatch):
    async def run():
        http = ScriptedHTTP([
            ("/activity/rebateStatus", {"code": 0, "status": 0}),
            ("/task/list", task_list()),
            ("/activity/rebateStatus", {"code": 0, "status": 0}),
            ("/task/list", task_list()),
        ])
        s, ready, _ = service(tmp_path, http)
        monkeypatch.setattr(rw, 'POLL_SEC', .08)
        ready.set()
        s.start()
        await eventually(lambda: len(http.calls) == 2)
        s._boundary = s.now() - 1
        s._wake.set()
        await eventually(lambda: len(http.calls) == 4)
        await s.close()
        assert s._settling_until > s.now()
    asyncio.run(run())


def test_close_drains_inflight_claim_and_sends_no_followup(tmp_path):
    async def run():
        started, release = threading.Event(), threading.Event()
        calls = []

        def post(url, payload, **kwargs):
            calls.append(url)
            if url.endswith('/activity/rebateStatus'):
                return {"code": 0, "status": 1}
            started.set()
            assert release.wait(2)
            return {"code": 0, "status": 1, "reward": 88}

        s, ready, credits = service(tmp_path, post)
        ready.set()
        s.start()
        await eventually(started.is_set)
        closing = asyncio.create_task(s.close())
        await asyncio.sleep(.02)
        assert not closing.done()
        release.set()
        await asyncio.wait_for(closing, 2)
        assert len(calls) == 2
        assert credits == [(88, False)]
        assert json.loads((tmp_path / 'rewards.jsonl').read_text().splitlines()[-1])['event'] == 'claimed'
    asyncio.run(run())


def test_poker_pnl_is_the_settled_hands_and_nothing_else():
    from pf_intercept.bot import BotBridge
    b = BotBridge()
    b._my_uid = '7'
    b.handle('pb.UserValueRSP', {'type': rw.GOLD, 'value': 1000})
    # A reward reaches the wallet, a side-game round is lost, another round's result is unknown:
    # none of it is poker.
    b.record_reward_credit(100)
    b.handle('pb.UserValueRSP', {'type': rw.GOLD, 'value': 1100})
    b.record_sidegame_result(-30)
    b.record_reward_credit(0, uncertain=True)
    assert b.bankroll_dashboard()['session_delta_chips'] == 0
    assert b.bankroll_dashboard()['samples'][-1]['delta_chips'] == 0

    won = {'winner': [], 'profit': [{'uid': '7', 'chips': '250'}, {'uid': '8', 'chips': '-250'}]}
    b._current_gameid = 'g1'
    b.handle('pb.WinnerRSP', won)
    b.handle('pb.WinnerRSP', won)                                         # replayed after a reconnect
    b._current_gameid = 'g2'
    b.handle('pb.WinnerRSP', {'winner': [], 'profit': [{'uid': '7'}]})    # broke even: field left out
    b._current_gameid = 'g3'
    b.handle('pb.WinnerRSP', {'winner': [], 'profit': [{'uid': '8', 'chips': '90'}]})   # not in the hand
    b._current_gameid = 'g4'
    b.handle('pb.WinnerRSP', {'winner': [], 'profit': [{'uid': '7', 'chips': '-40'}]})

    d = b.bankroll_dashboard()
    assert d['session_delta_chips'] == 210
    assert (d['reward_chips'], d['sidegame_net_chips'], d['rewards_uncertain']) == (100, -30, True)
    b.handle('pb.UserValueRSP', {'type': rw.GOLD, 'value': 5000})         # whatever the wallet says
    assert b.bankroll_dashboard()['samples'][-1]['delta_chips'] == 210


@pytest.mark.parametrize('result', [
    {'code': 0},
    {'code': 0, 'reward_chips': 'unreadable'},
    {'code': 0, 'item_list': [{'item_id': rw.GOLD}]},
])
def test_malformed_success_is_uncertain_not_zero_reward(tmp_path, result):
    async def run():
        http = ScriptedHTTP([
            ('/task/list', task_list(daily_list=[{'id': 1, 'status': 2}])),
            ('/task/recReward', result),
        ])
        s, _, credits = service(tmp_path, http)
        with pytest.raises(rw.RewardAPIError):
            await s.check_tasks()
        assert credits == [(0, True)]
        assert s.claims == 0
    asyncio.run(run())


def test_retry_delay_doubles_to_the_cap_per_check(tmp_path):
    s, _, _ = service(tmp_path, ScriptedHTTP([]))
    assert [s._retry_delay("fund") for _ in range(8)] == [30, 60, 120, 240, 480, 960, 1800, 1800]
    assert s._retry_delay("tasks") == 30


def test_failing_checks_back_off_and_unexpected_errors_reach_the_journal(tmp_path, monkeypatch):
    async def run():
        monkeypatch.setattr(rw, "RETRY_SEC", .02)
        monkeypatch.setattr(rw, "RETRY_MAX_SEC", .08)
        s, ready, _ = service(tmp_path, ScriptedHTTP([]))
        task_passes = []

        async def rejected():
            raise rw.RewardAPIError("/activity/rebateStatus", 500)

        async def broken_twice():
            task_passes.append(1)
            if len(task_passes) <= 2:
                raise KeyError("status")

        s.check_fund, s.check_tasks = rejected, broken_twice
        ready.set()
        s.start()
        await asyncio.sleep(.5)
        await s.close()
        rows = [json.loads(line) for line in (tmp_path / "rewards.jsonl").read_text().splitlines()]
        fund = [r for r in rows if r["event"] == "check_failed" and r["kind"] == "fund"]
        tasks = [r for r in rows if r["event"] == "check_failed" and r["kind"] == "tasks"]
        assert 3 <= len(fund) <= 12                 # every 20ms without back-off: about 25
        assert fund[0]["code"] == 500
        assert [r["error"] for r in tasks] == ["KeyError", "KeyError"]
        assert len(task_passes) == 3 and "tasks" not in s._failures      # success resets the back-off
    asyncio.run(run())
