"""任务上报: scripted replies, no real game requests."""
import asyncio
import json
from unittest.mock import AsyncMock, Mock

import pytest

from pf_intercept.headless.lobby.doers import reports as rp
from pf_intercept.headless.lobby.core.base import RewardAPIError
from pf_intercept.headless.lobby.core.service import RewardService

NOW = 1795500000


def setup(tmp_path, rows):
    svc = RewardService(uid=5, authorization='test', http_base='', chnl=1, version='1',
                        on_credit=AsyncMock(), ready=asyncio.Event(), journal_path=tmp_path / 'rewards')
    svc.now = lambda: NOW
    svc.needs.want('tasks', rows)
    svc._request = AsyncMock(return_value={'code': 0})
    session = Mock()
    session.activity_table.return_value = (123, 456)
    session.activity_request = AsyncMock(return_value={'emoji_free_times': 1})
    return svc, session, rp.Reports(svc, session)


def row(kind, value, done=0):
    return {'task_type': kind, 'status': 1, 'value': value, 'current_value': done}


def test_a_page_and_the_lobby_are_reported_as_the_client_reports_them(tmp_path):
    async def run():
        svc, session, worker = setup(tmp_path, [row(302, [101, 1]), row(303, [1]), row(201, [3])])
        await worker.check()
        assert sorted((c.args for c in svc._request.await_args_list), key=lambda a: a[1]["task_type"]) == [
            ('/task/report', {'task_type': 302, 'id': 101}), ('/task/report', {'task_type': 303, 'id': 0})]
        assert svc.needs.lacking('task_type:302:101') == {} and not session.activity_request.await_count
    asyncio.run(run())


def test_each_kind_is_reported_at_most_max_per_day_across_restarts(tmp_path):
    async def run():
        svc, _, worker = setup(tmp_path, [row(302, [101, 1])])
        for _ in range(rp.MAX_PER_DAY + 2):
            svc.needs.want('tasks', [row(302, [101, 1])])       # the server never counts it
            await worker.check()
        assert svc._request.await_count == rp.MAX_PER_DAY
        restarted = rp.Reports(svc, Mock())
        svc.needs.want('tasks', [row(302, [101, 1])])
        await restarted.check()
        assert svc._request.await_count == rp.MAX_PER_DAY
    asyncio.run(run())


def test_the_emoji_is_sent_before_its_report_and_a_failed_report_is_retried_alone(tmp_path):
    async def run():
        svc, session, worker = setup(tmp_path, [row(304, [3, 1])])
        svc._request = AsyncMock(side_effect=[RewardAPIError('report'), {'code': 0}])
        with pytest.raises(RewardAPIError):
            await worker.check()
        resumed = rp.Reports(svc, session)
        await resumed.check()
        assert [c.args for c in session.activity_request.await_args_list] == [
            ('SelfUserInfo', {}), ('SendEmoji', {'id': 1, 'to_uid': 456}, 123)]
        assert all(c.args == ('/task/report', {'task_type': 304, 'id': 3}) for c in svc._request.await_args_list)
        events = [json.loads(line)['event'] for line in svc._journal_path.read_text().splitlines()]
        assert events == ['emoji_attempt', 'emoji_sent', 'emoji_reported']
    asyncio.run(run())
