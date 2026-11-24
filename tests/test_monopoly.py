"""大富翁 (monopoly): scripted replies, no real game requests."""
import asyncio
import json
from unittest.mock import AsyncMock, Mock

from pf_intercept.bot import BotBridge
from pf_intercept.headless.lobby.activities import monopoly as mo
from pf_intercept.headless.lobby.core.base import GOLD, RewardAPIError
from pf_intercept.headless.lobby.core.service import RewardService
from pf_intercept.wire import codec

PERIOD = 30001                  # 蓝湾漫游 in the client's tables
DICE = 10420002
INSIDE = 1795500000             # 2026-11-24, inside 30001


def service(tmp_path, credit=None, now=INSIDE):
    ready = asyncio.Event()
    ready.set()
    svc = RewardService(uid=5, authorization='test', http_base='', chnl=1, version='1',
                        on_credit=credit or AsyncMock(), ready=ready, journal_path=tmp_path / 'rewards')
    svc.now = lambda: now
    return svc


def test_board_and_milestones_are_the_periods_tables():
    squares, chips = mo.board(PERIOD)
    assert squares == 24 and chips == {3: 50000, 6: 100000, 8: 20000, 12: 100000, 15: 50000,
                                       17: 10000, 20: 20000, 23: 10000}
    assert mo.milestones(PERIOD) == ((50, 100, 150, 200, 300, 400, 500), {2: 50000, 4: 150000})
    assert mo.board(1) == (0, {}) and mo.milestones(1) == ((), {})


def test_reward_chips():
    assert mo.reward_chips([GOLD, 500, 10200001, 1, GOLD, 20]) == 520
    assert mo.reward_chips(None) == 0


def test_the_period_the_server_names_is_played_and_none_is_left_alone(tmp_path):
    async def run():
        for act_id, now, played in ((PERIOD, INSIDE, True), (0, INSIDE, False), (PERIOD, 1795633200 + 1, False)):
            svc = service(tmp_path, now=now)
            session = Mock()
            session.activity_request = AsyncMock(side_effect=lambda name, fields: (
                {'act_id': act_id} if name == 'GetMonopolyActData' else {'item_list': []}))
            worker = mo.Monopoly(svc, session)
            worker.tasks = AsyncMock(return_value=[
                {'id': 1, 'task_type': 101, 'status': 1, 'value': [30030101, 30], 'current_value': 12}])
            await worker.check()
            assert worker.tasks.await_count == int(played)
            assert ('monopoly' in svc.needs.reports) is played
            assert worker.interval() == (300.0 if played else 3600.0)
    asyncio.run(run())


def test_ambiguous_roll_recovers_after_restart_then_claims_milestones(tmp_path):
    payouts = []

    async def credit(amount, uncertain):
        payouts.append((amount, uncertain))

    state = {'act_id': PERIOD, 'all_cost_num': 199, 'progress': 1, 'index': 10}

    class Session:
        async def activity_request(self, name, fields):
            if name == 'ThrowDice':
                state.update(all_cost_num=200, index=12)
                raise RewardAPIError(name)
            assert name == 'GetProgressReward'
            return {'progress': 4}

    async def run():
        sess = Session()
        worker = mo.Monopoly(service(tmp_path, credit), sess)
        try:
            await worker.roll(dict(state))
        except RewardAPIError:
            pass
        else:
            assert False, 'lost reply must not be retried'
        recovered = mo.Monopoly(service(tmp_path, credit), sess)
        recovered.load()
        await recovered.resolve_award(state)
        await recovered.take_milestones(state)
        assert payouts == [(100000, False), (200000, False)]
        again = mo.Monopoly(service(tmp_path, credit), sess)
        again.load()
        assert again.pending_award is None
    asyncio.run(run())


def test_chips_in_a_task_reward_are_credited_as_rewards(tmp_path):
    async def run():
        credits = []

        async def credit(chips, uncertain):
            credits.append((chips, uncertain))
        svc = service(tmp_path, credit)
        worker = mo.Monopoly(svc, Mock())
        svc._request = AsyncMock(side_effect=[
            {'code': 0, 'item_list': [{'item_id': DICE, 'num': 2}, {'item_id': GOLD, 'num': 5000}]},
            {'code': 0, 'list': [{'id': 7, 'status': 3}]},
        ])
        assert await worker.collect([{'id': 7, 'status': 2}], DICE) == [{'id': 7, 'status': 3}]
        assert credits == [(5000, False)]
        events = [json.loads(line) for line in svc._journal_path.read_text().splitlines()]
        assert [(r['event'], r.get('dice'), r.get('chips')) for r in events] == [
            ('monopoly_task_claim', 2, None), ('claimed', None, 5000)]
    asyncio.run(run())


def test_board_protocol_and_three_separate_ledgers():
    for name, fields in [('ThrowDiceREQ', {'multiple': 1}), ('GetProgressRewardRSP', {'progress': 2}),
                         ('GetMonopolyActDataRSP', {'act_id': PERIOD, 'index': 1})]:
        assert codec.decode('pb.' + name, codec.encode('pb.' + name, fields)) == fields
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
