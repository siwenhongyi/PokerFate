"""The two transports share game/lobby semantics; all wire/HTTP requests are local fakes."""
import asyncio
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from pf_intercept.bot import BotBridge
from pf_intercept.options import RunOptions
from pf_intercept.proxy.session import ProxySession
from pf_intercept.headless.login import LoginResult, ServerEntry
from pf_intercept.headless.lobby.core.base import RewardAPIError
from pf_intercept.headless import lobby


async def eventually(check):
    for _ in range(100):
        if check():
            return
        await asyncio.sleep(.01)
    assert check()


def fixture_session(monkeypatch, tmp_path, **values):
    from pf_intercept.proxy import session as module
    options = RunOptions(no_notify=True, no_task_hands=True, **values)
    login = LoginResult(10, "key", "fake-token", [ServerEntry("wss://127.0.0.1:9012", "http://127.0.0.1")])
    monkeypatch.setattr(module, 'load_session', lambda _: (login, 10, '1.7.0'))
    monkeypatch.setattr(module, 'configure_server_proxy_bypass', lambda *a, **k: None)
    bridge = BotBridge(options=options, auto_table_selection=not bool(options.bb))
    sent = []
    def emit(payload):
        sent.append(payload)
        if payload.get('send_id'):
            asyncio.get_running_loop().call_soon(session.sent, payload['send_id'], True)
    session = ProxySession(bridge, options, emit)
    return session, sent


async def login(session):
    await session.attach(1, 'wss://127.0.0.1:9012')
    await session.client_request('pb.UserLoginREQ', {'uid': 10, 'key': 'key', 'chnl': 10})


ROOM = {'roomid': 90, 'game_type': 10010101,
        'room_info': {'bb': '5000', 'sb': '2500', 'lobby_coin': 10100001},
        'table_status': {'seat': []}}


def test_shared_lobby_registry_credentials_and_switches(monkeypatch, tmp_path):
    async def run():
        session, sent = fixture_session(monkeypatch, tmp_path, off=('monopoly',))
        await login(session)
        svc = session._rewards
        assert svc._authorization == 'fake-token'
        assert svc._http_base == 'http://127.0.0.1'
        expected = {kind.name for kind in lobby.WORKERS if not kind.switch or kind.switch[0] != 'monopoly'}
        assert set(svc.workers) == expected
        await session.close()
    asyncio.run(run())


def test_reward_credit_waits_for_authoritative_baseline_and_survives_reconnect(monkeypatch, tmp_path):
    async def run():
        session, sent = fixture_session(monkeypatch, tmp_path)
        await login(session)
        svc = session._rewards
        svc.workers.clear()
        svc.due.clear()
        svc._journal_path = tmp_path / 'rewards.jsonl'
        svc._post = lambda *a, **k: {'code': 0, 'reward_chips': 123}
        await session.feed_message('pb.UserLoginRSP', 0, {'code': 0})
        await session.feed_message('pb.UserValueRSP', 0, {'type': 10100001, 'value': '1000000'})
        assert not session._bankroll_ready.is_set()
        await session.feed_message('pb.UserLocationRSP', 0, {'roomid': 0})
        await session.feed_message('pb.UserValueRSP', 0, {'type': 10100001, 'value': '1000000'})
        await eventually(session._bankroll_ready.is_set)
        await svc._claim('/task/reward', {}, 'task')
        assert session.live_reward_totals() == (123, False)
        assert session.bankroll_dashboard()['session_delta_chips'] == 0
        before = session.bankroll_dashboard()
        await session.detach(1)
        assert not session._bankroll_ready.is_set()
        await session.attach(2)
        await session.client_request('pb.UserLoginREQ', {'uid': 10, 'key': 'key'})
        assert session._rewards is svc
        assert svc.confirmed_chips == 123
        assert session.bankroll_dashboard()['base_total_chips'] == before['base_total_chips']
        await session.close()
    asyncio.run(run())


def test_client_and_activity_requests_cannot_steal_each_others_replies(monkeypatch, tmp_path):
    async def run():
        session, sent = fixture_session(monkeypatch, tmp_path, no_auto_rewards=True)
        await login(session)
        session._bankroll_ready.set()
        assert await session.client_request('pb.SendEmojiREQ', {'id': 1, 'to_uid': 20})
        with pytest.raises(RewardAPIError, match='client request outstanding'):
            await session.activity_request('SendEmoji', {'id': 1, 'to_uid': 20})
        await session.feed_message('pb.SendEmojiRSP', 0, {'code': 0})
        call = asyncio.create_task(session.activity_request('SendEmoji', {'id': 1, 'to_uid': 20}))
        await eventually(lambda: 'pb.SendEmojiRSP' in session._activity_pending)
        assert not await session.client_request('pb.SendEmojiREQ', {'id': 2, 'to_uid': 30})
        await session.feed_message('pb.SendEmojiRSP', 0, {'code': 0, 'marker': 'bot'})
        assert (await call)['marker'] == 'bot'
        assert sum(p.get('type_name') == 'pb.SendEmojiREQ' for p in sent) == 1
        await session.close()
    asyncio.run(run())


def test_live_updates_before_slow_bridge_and_disconnect_clears_connection(monkeypatch, tmp_path):
    async def run():
        session, sent = fixture_session(monkeypatch, tmp_path, no_auto_rewards=True)
        await login(session)
        await session.feed_message('pb.EnterRoomRSP', 90, ROOM)
        assert session.observer.snapshot()['room_id'] == 90
        await session.feed_message('pb.LeaveRoomRSP', 90, {'code': 0})
        assert session.observer.snapshot()['room_id'] == 0
        await session.detach(1)
        assert session.observer.snapshot()['connected'] is False
        assert session.observer.snapshot()['connection_status'] == 'reconnecting'
        await session.close()
    asyncio.run(run())


def test_graceful_stop_keeps_socket_until_leave_and_prevents_new_matches(monkeypatch, tmp_path):
    async def run():
        session, sent = fixture_session(monkeypatch, tmp_path, no_auto_rewards=True)
        await login(session)
        await session.feed_message('pb.EnterRoomRSP', 90, ROOM)
        stop = asyncio.create_task(session.graceful_leave(timeout=1))
        await eventually(lambda: any(p.get('type_name') == 'pb.DelayLeaveRoomREQ' for p in sent))
        assert session.connected and not stop.done()
        assert not await session.send('pb.QuickStartREQ', {'boot': 5000})
        await session.feed_message('pb.LeaveRoomRSP', 90, {'code': 0})
        await stop
        assert session.bridge._shutdown_requested
        await session.close()
    asyncio.run(run())


def test_client_match_uses_configured_buyin_and_runs_taskhands_first(monkeypatch, tmp_path):
    async def run():
        session, sent = fixture_session(monkeypatch, tmp_path, no_auto_rewards=True, buyin_bb=80)
        await login(session)
        order = []
        async def errands():
            order.append('tasks')
        session._task_hands = SimpleNamespace(run=errands)
        async def match(**fields):
            assert fields == {'big_blind': 5000, 'buyin_bb': 80}
            order.append('match')
        monkeypatch.setattr(session, 'quick_start', match)
        allowed = await session.client_request('pb.QuickStartREQ', {'game_type': 10010101, 'boot': 5000})
        assert not allowed
        await eventually(lambda: order == ['tasks', 'match'])
        await session.close()
    asyncio.run(run())


def test_bad_capture_does_not_use_another_accounts_http_token(monkeypatch, tmp_path, caplog):
    from pf_intercept.proxy import session as module
    async def run():
        session, sent = fixture_session(monkeypatch, tmp_path)
        wrong = LoginResult(99, 'key', 'another-account-token', [ServerEntry('wss://127.0.0.1', '')])
        monkeypatch.setattr(module, 'load_session', lambda _: (wrong, 10, '1.7.0'))
        await login(session)
        assert session.login.uid == 10
        assert session._rewards._authorization == ''
        assert '不匹配' in caplog.text
        await session.close()
    asyncio.run(run())


def test_worker_options_are_not_global_config(monkeypatch):
    a = BotBridge(options=RunOptions(profit_lock_bb=140, topup_below_bb=0, buyin_bb=60, stakes='5000,1000'),
                  auto_table_selection=True)
    b = BotBridge()
    assert a.options.profit_lock_bb == 140 and b.options.profit_lock_bb == 200
    a._my_seat, a._bb, a._table_room_id = 0, 5000, 90
    a._session_game_type, a._session_lobby_coin = 10010101, 10100001
    assert a._enable_detected_table_policy()
    assert a._table_policy.cfg.buyin_bb == 60
    assert a._table_policy.cfg.ladder == (5000, 1000)


def test_reconnected_task_table_is_left_then_cash_match_resumes(monkeypatch, tmp_path):
    from pf_intercept.headless.lobby.doers.taskhands import Seat
    async def run():
        session, sent = fixture_session(monkeypatch, tmp_path, no_auto_rewards=True)
        await login(session)
        session._requested_cash_bb = 5000
        order = []
        async def leave(seat):
            order.append('leave')
            seat.gone = True
            session._wire_room_id = 0
        async def baseline():
            order.append('baseline')
            session._bankroll_ready.set()
        async def match(msg):
            assert msg['boot'] == 5000
            order.append('match')
        monkeypatch.setattr(Seat, 'leave', leave)
        monkeypatch.setattr(session, 'lobby_baseline', baseline)
        monkeypatch.setattr(session, '_client_match', match)
        await session.feed_message('pb.EnterRoomRSP', 77, {'roomid':77,'game_type':10020101})
        await eventually(lambda: order == ['leave','baseline','match'])
        assert session._seat is None
        assert session.observer.snapshot()['room_id'] == 0
        await session.close()
    asyncio.run(run())
