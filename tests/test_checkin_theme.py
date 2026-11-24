"""累签活动 and 主题活动: scripted replies, no real game requests."""
import asyncio
import json
from unittest.mock import AsyncMock

import pytest

from pf_intercept.headless.lobby.activities import checkin as ci
from pf_intercept.headless.lobby.activities import theme as th
from pf_intercept.headless.lobby.core.base import GOLD
from pf_intercept.headless.lobby.core.service import RewardService
from tests.test_dispatch import TPL, ScriptedHTTP, journal


def latest(table):
    """(id, a moment inside it) of the last period of an activity table in the installer's tables."""
    from pf_reverse.tables import TABLES
    row = TABLES.rows(table)[-1]
    return next(iter(row.values())), row["time_start"] + 3600


class Bag:
    """The game socket: a bag holding ``tokens`` of every item asked about."""

    def __init__(self, held=None):
        self.held = held or {}

    async def activity_request(self, name, fields):
        assert name == "ItemList"
        return {"item_list": [{"item_id": item, "num": num} for item, num in self.held.items()]}


def setup(tmp_path, replies, kind, now, bag=None):
    http = ScriptedHTTP(replies)
    credits = []

    async def credit(chips, uncertain):
        credits.append((chips, uncertain))
    ready = asyncio.Event()
    ready.set()
    svc = RewardService(uid=42, authorization="session-secret", http_base="https://game.example",
                        chnl=3, version="1.7.0", on_credit=credit, ready=ready, post=http,
                        journal_path=tmp_path / "rewards.jsonl")
    svc.now = lambda: now
    return svc.attach(kind(svc, bag or Bag())), http, credits


def test_the_requests_are_the_clients():
    model = (TPL.parent / "app" / "model" / "activity" / "ActivityNewmanCheckinModel.lua").read_text(encoding="utf-8")
    assert f'Net:post("{ci.DATA}", {{t = 1}}' in model and f'Net:post("{ci.CLAIM}", {{id = self._checkinId}}' in model
    theme = (TPL.parent / "app" / "model" / "activity" / "ThemeModel.lua").read_text(encoding="utf-8")
    assert f'Net:post("{th.DATA}", {{t = 1}}' in theme and f'Net:post("{th.TASKS}", {{id = self:getConfId()}}' in theme
    assert 'Net:post("/task/recReward", {id_arr = id_arr, task_cate = 4, all = nil ~= ids, mask = "reward"}' in theme


@pytest.mark.parametrize("raw, days", [({"1": 2, "2": 1}, {1: 2, 2: 1}), ([2, 1, 0], {1: 2, 2: 1, 3: 0}), (None, {})])
def test_days_of(raw, days):
    assert ci.days_of({"data": raw}) == days


def test_a_ready_day_is_collected_once_and_read_back(tmp_path):
    CHECKIN_PERIOD, now = latest("event_check_in")

    async def run():
        worker, http, credits = setup(tmp_path, [
            (ci.DATA, {"code": 0, "id": CHECKIN_PERIOD, "data": {"1": 2, "2": 1}}),
            (ci.CLAIM, {"code": 0, "item_list": [{"item_id": GOLD, "num": 30000}]}),
            (ci.DATA, {"code": 0, "id": CHECKIN_PERIOD, "data": {"1": 2, "2": 2}}),
        ], ci.CheckIn, now)
        await worker.check()
        assert [call for call in http.calls if call[0] == ci.CLAIM] == [(ci.CLAIM, {"id": CHECKIN_PERIOD})]
        assert credits == [(30000, False)] and not http.replies
    asyncio.run(run())


def test_a_period_the_tables_lack_is_told_and_left_alone(tmp_path):
    async def run():
        worker, http, _ = setup(tmp_path, [(ci.DATA, {"code": 0, "id": 99, "data": {"1": 1}})], ci.CheckIn,
                                latest("event_check_in")[1])
        await worker.check()
        assert [call[0] for call in http.calls] == [ci.DATA]
        assert journal(tmp_path, "checkin_period")[-1] == {**journal(tmp_path, "checkin_period")[-1],
                                                           "ident": 99, "known": False}
        assert journal(tmp_path, "alert")[-1]["key"] == "period:event_check_in:99"
    asyncio.run(run())


def test_finished_theme_tasks_are_claimed_and_its_rows_go_on_the_board(tmp_path):
    THEME_PERIOD, now = latest("theme_activity")

    async def run():
        rows = [{"id": 5, "task_id": 100101, "task_type": 302, "status": 2, "value": [10001, 1], "current_value": 1},
                {"id": 6, "task_id": 100201, "task_type": 101, "status": 1, "value": [30030101, 10], "current_value": 4}]
        after = [dict(rows[0], status=3), rows[1]]
        worker, http, credits = setup(tmp_path, [
            (th.DATA, {"code": 0, "data": {"id": THEME_PERIOD, "start_ts": 1, "end_ts": 2}}),
            (th.TASKS, {"code": 0, "list": rows}),
            (th.CLAIM, {"code": 0, "item_list": [{"item_id": 10410010, "num": 20}]}),
            (th.TASKS, {"code": 0, "list": after}),
        ], th.Theme, now)
        await worker.check()
        assert (th.CLAIM, {"id_arr": [5], "task_cate": 4, "all": True, "mask": "reward"}) in http.calls
        assert worker.service.needs.lacking(30030101) == {"theme": 6} and credits == [(0, False)]
        assert json.dumps(journal(tmp_path, "claimed")[-1]["items"]) == '[{"item_id": 10410010, "num": 20}]'
    asyncio.run(run())
