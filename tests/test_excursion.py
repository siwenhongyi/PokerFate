import asyncio
import json
from unittest.mock import AsyncMock, Mock

import pytest

from pf_intercept.headless.excursion import ACTIVITY, COLOR, MAX_PLAYS, PINBALL, DIE, Excursion, minimum_bet
from pf_intercept.headless.rewards import RewardService, RewardAPIError
from pf_intercept.bot import BotBridge
from pf_intercept.wire import codec


def test_emoji_reports_only_after_a_free_send_and_can_retry_without_resending(tmp_path):
    async def run():
        svc = RewardService(uid=5, authorization='test', http_base='', chnl=1, version='1',
                            on_credit=AsyncMock(), ready=asyncio.Event(), journal_path=tmp_path/'rewards')
        session = Mock()
        session.activity_table.return_value = (123, 456)
        session.activity_request = AsyncMock(side_effect=[
            {'emoji_free_times': 0}, {'emoji_free_times': 1}, {'emoji_free_times': 0},
        ])
        e = Excursion(svc, session)
        e.load_budget()
        svc._request = AsyncMock(side_effect=[RewardAPIError('report'), {'code': 0}])
        await e.free_emoji()
        assert not svc._journal_path.exists()
        with pytest.raises(RewardAPIError):
            await e.free_emoji()
        resumed = Excursion(svc, session)
        resumed.load_budget()
        await resumed.free_emoji()
        await resumed.free_emoji()
        assert [c.args for c in session.activity_request.await_args_list] == [
            ('SelfUserInfo', {}), ('SelfUserInfo', {}), ('SendEmoji', {'id': 1, 'to_uid': 456}, 123)]
        assert all(c.args == ('/task/report', {'task_type': 304, 'id': 3})
                   for c in svc._request.await_args_list)
        assert [json.loads(line)['event'] for line in svc._journal_path.read_text().splitlines()] == [
            'emoji_attempt', 'emoji_sent', 'emoji_reported']
    asyncio.run(run())


def test_side_games_keep_lowest_stake_as_wallet_grows():
    for game in (COLOR, PINBALL):
        conf = {'balls': [1], 'tpl_conf': [
            {'id': 4, 'balance': 100000000, 'chips1': 100000, 'chips': [100000]},
            {'id': 2, 'balance': 1000000, 'chips1': 1000, 'chips': [1000]},
            {'id': 1, 'balance': 0, 'chips1': 1000, 'chips': [1000]},
        ]}
        assert minimum_bet(conf, game, 500) is None
        assert minimum_bet(conf, game, 1000) == (1, 1000)
        assert minimum_bet(conf, game, 100000001) == (1, 1000)
        conf['tpl_conf'] = conf['tpl_conf'][:1]
        assert minimum_bet(conf, game, 100000001) is None


def test_ambiguous_roll_recovers_after_restart_then_claims_milestones(tmp_path):
    ready = asyncio.Event()
    ready.set()
    payouts = []
    async def credit(amount, uncertain):
        payouts.append((amount, uncertain))
    def service():
        return RewardService(uid=5, authorization='test', http_base='', chnl=1, version='1',
                             on_credit=credit, ready=ready, journal_path=tmp_path/'rewards')
    state = {'act_id': ACTIVITY, 'all_cost_num': 199, 'progress': 1, 'index': 10}
    class Session:
        async def activity_request(self, name, fields):
            if name == 'ThrowDice':
                state.update(all_cost_num=200, index=12)
                raise RewardAPIError(name)
            assert name == 'GetProgressReward'
            return {'progress': 4}

    async def run():
        sess = Session()
        e = Excursion(service(), sess)
        try:
            await e.roll(dict(state))
        except RewardAPIError:
            pass
        else:
            assert False, 'lost reply must not be retried'
        recovered = Excursion(service(), sess)
        recovered.load_budget()
        await recovered.resolve_award(state)
        await recovered.milestones(state)
        assert payouts == [(100000, False), (200000, False)]
        again = Excursion(service(), sess)
        again.load_budget()
        assert again.pending_award is None
    asyncio.run(run())


def test_board_protocol_and_three_separate_ledgers():
    for name, fields in [('ThrowDiceREQ', {'multiple': 1}), ('GetProgressRewardRSP', {'progress': 2}),
                         ('GetMonopolyActDataRSP', {'act_id': ACTIVITY, 'index': 1})]:
        assert codec.decode('pb.'+name, codec.encode('pb.'+name, fields)) == fields
    b = BotBridge()
    b._my_uid = '7'
    def wallet(value):
        b.handle('pb.UserValueRSP', {'type': 10100001, 'value': value})
    wallet(10000)
    b.record_sidegame_result(-1000)
    b.record_reward_credit(20000)
    wallet(29000)
    d = b.bankroll_dashboard()
    assert (d['session_delta_chips'], d['reward_chips'], d['sidegame_net_chips']) == (0, 20000, -1000)
    # A side-game round whose result never arrived leaves the poker PnL readable.
    b.record_reward_credit(0, uncertain=True)
    b.handle('pb.WinnerRSP', {'winner': [], 'profit': [{'uid': '7', 'chips': 500}]})
    d = b.bankroll_dashboard()
    assert d['session_delta_chips'] == 500 and d['rewards_uncertain']
    assert (d['reward_chips'], d['sidegame_net_chips'], d['wallet_chips']) == (20000, -1000, 29000)


def test_a_losing_colour_round_is_a_known_result(tmp_path):
    """The wire format drops zero fields, so the colour that lost carries no ``profit``."""
    async def run():
        credit = AsyncMock()
        session = Mock()
        session.bankroll_dashboard.return_value = {'wallet_chips': 5_000_000}
        session.current_room_id.return_value = 0
        session.on_sidegame_result = AsyncMock()
        conf = {'tpl_conf': [{'id': 1, 'balance': 0, 'chips1': 1000}]}
        bet = [{'id': 101, 'value': 1000}]
        session.activity_request = AsyncMock(side_effect=[
            {'game_type': COLOR, 'conf': json.dumps(conf)},
            {'bets': bet, 'profits': [{'id': 101}], 'ids': [102, 103, 104]},
            {'bets': bet, 'profits': [{'id': 101, 'profit': 3000}], 'ids': [101, 101, 105]},
        ])
        svc, e = _excursion(tmp_path, session, credit)
        await e.play_cheap(COLOR, 2)
        rows = [json.loads(line) for line in svc._journal_path.read_text().splitlines()]
        assert [(r['event'], r.get('net')) for r in rows] == [
            ('sidegame_attempt', None), ('sidegame_result', -1000),
            ('sidegame_attempt', None), ('sidegame_result', 2000)]
        assert [c.args for c in session.on_sidegame_result.await_args_list] == [(-1000,), (2000,)]
        credit.assert_not_awaited()                      # nothing uncertain, nothing claimed
        assert not svc.uncertain
    asyncio.run(run())


def _excursion(tmp_path, session, credit=None):
    ready = asyncio.Event()
    ready.set()
    svc = RewardService(uid=5, authorization='test', http_base='', chnl=1, version='1',
                        on_credit=credit or AsyncMock(), ready=ready, journal_path=tmp_path/'rewards')
    e = Excursion(svc, session)
    e.load_budget()
    return svc, e


def test_side_game_without_a_cheap_stake_is_skipped_for_the_day(tmp_path):
    async def run():
        session = Mock()
        session.bankroll_dashboard.return_value = {'wallet_chips': 5_000_000}
        conf = {'tpl_conf': [{'id': 3, 'balance': 0, 'chips1': 10000}]}
        session.activity_request = AsyncMock(return_value={'game_type': COLOR, 'conf': json.dumps(conf)})
        svc, e = _excursion(tmp_path, session)
        await e.play_cheap(COLOR, 2)
        assert e.plays[COLOR] >= MAX_PLAYS            # check() stops asking for this game today
        assert session.activity_request.await_count == 1
        rows = [json.loads(line) for line in svc._journal_path.read_text().splitlines()]
        assert [(r['event'], r['game']) for r in rows] == [('sidegame_skipped', COLOR)]
        _, restarted = _excursion(tmp_path, session)
        assert restarted.plays == {COLOR: MAX_PLAYS, PINBALL: 0}
        # No wallet reading yet: nothing is asked, nothing is given up for the day.
        session.bankroll_dashboard.return_value = {}
        await restarted.play_cheap(PINBALL, 2)
        assert restarted.plays[PINBALL] == 0 and session.activity_request.await_count == 1
    asyncio.run(run())


def test_chips_in_an_excursion_task_reward_are_credited_as_rewards(tmp_path):
    async def run():
        credits = []
        async def credit(chips, uncertain):
            credits.append((chips, uncertain))
        svc, e = _excursion(tmp_path, Mock(), credit)
        svc._request = AsyncMock(side_effect=[
            {'code': 0, 'item_list': [{'item_id': DIE, 'num': 2}, {'item_id': 10100001, 'num': 5000}]},
            {'code': 0, 'list': [{'id': 7, 'status': 3}]},
        ])
        assert await e.collect([{'id': 7, 'status': 2}]) == [{'id': 7, 'status': 3}]
        assert credits == [(5000, False)]
        events = [json.loads(line) for line in svc._journal_path.read_text().splitlines()]
        assert [(r['event'], r.get('dice'), r.get('chips')) for r in events] == [
            ('excursion_task_claim', 2, None), ('claimed', None, 5000)]
    asyncio.run(run())
