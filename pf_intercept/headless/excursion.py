"""蓝湾漫游 (30001). Requests and payout tables from client 1.7.5.

Only run the ordinary hand-count tasks of the two side games, using the
cheapest advertised stake and the daily turnover limit. Never chase losses.
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timedelta
import uuid

from pf_intercept.headless.rewards import GOLD, RewardAPIError, UTC8
from pf_entertainment.color_game import color_bet, color_profit

log = logging.getLogger("pf_rewards")
ACTIVITY = 30001
START, END = 1794448800, 1795633200
DIE = 10420002
COLOR, PINBALL = 30030101, 30080101
MAX_BET = 1000
MAX_PLAYS = 24
# Keys are the 1-based index and progress ID in the official board tables.
GRID_CHIPS = {3: 50000, 6: 100000, 8: 20000, 12: 100000, 15: 50000,
              17: 10000, 20: 20000, 23: 10000}
MILESTONES = (50, 100, 150, 200, 300, 400, 500)
MILESTONE_CHIPS = {2: 50000, 4: 150000}


def activity_day(now):
    return (datetime.fromtimestamp(now, UTC8) - timedelta(hours=3)).date().isoformat()


def minimum_bet(conf, game, wallet):
    if game == PINBALL and 1 not in conf.get('balls', []):
        return None
    levels = conf['tpl_conf']
    if isinstance(levels, dict):
        levels = levels.values()
    # The client preselects the highest unlocked tier. The wire request carries
    # an explicit level, and the old Web used level 1 even with a large wallet.
    offers = []
    for row in levels:
        if int(row['balance']) > wallet:
            continue
        stakes = [row['chips1']] if game == COLOR else row['chips']
        for value in stakes:
            stake = int(value)
            if 0 < stake <= min(wallet, MAX_BET):
                offers.append((stake, int(row['id'])))
    if not offers:
        return None
    stake, level = min(offers)
    return level, stake


class Excursion:
    def __init__(self, service, session):
        self.service = service
        self.session = session
        self.day = None
        self.plays = {}
        self.emoji_attempted = False
        self.emoji_report_due = False
        self.pending_award = None

    def load_budget(self):
        day = activity_day(self.service.now())
        if self.day == day:
            return
        self.day = day
        self.plays = {COLOR: 0, PINBALL: 0}
        self.emoji_attempted = False
        self.emoji_report_due = False
        path = self.service._journal_path
        if not path.exists():
            return
        for line in path.read_text(encoding='utf-8').splitlines():
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if row.get('uid') != self.service.uid:
                continue
            if row.get('event') == 'excursion_intent' and row.get('activity') == ACTIVITY:
                self.pending_award = row
            elif self.pending_award and row.get('intent') == self.pending_award['intent']:
                self.pending_award = None
            if row.get('day') != day:
                continue
            if row.get('event') == 'sidegame_attempt' and row.get('game') in self.plays:
                self.plays[row['game']] += 1
            elif row.get('event') == 'sidegame_skipped' and row.get('game') in self.plays:
                self.plays[row['game']] = MAX_PLAYS
            if row.get('event') == 'emoji_attempt':
                self.emoji_attempted = True
            elif row.get('event') == 'emoji_sent':
                self.emoji_report_due = True
            elif row.get('event') == 'emoji_reported':
                self.emoji_report_due = False

    async def tasks(self):
        return (await self.service._request('/task/monopolyTaskList', {})).get('list') or []

    async def collect(self, rows):
        attempted = set()
        while rows:
            ids = {int(r['id']) for r in rows if r['status'] == 2} - attempted
            if not ids:
                break
            attempted.update(ids)
            result = await self.service._request('/task/recMonopolyTaskRw', {'id_arr': sorted(ids)})
            items = result.get('item_list') or []
            count = sum(int(i['num']) for i in items if int(i['item_id']) == DIE)
            self.service._record('excursion_task_claim', ids=sorted(ids), dice=count)
            # These tasks pay dice. Should one ever pay chips, they count as a reward.
            chips = int(result.get('reward_chips') or 0) + sum(
                int(i['num']) for i in items if int(i['item_id']) == GOLD)
            if chips > 0:
                await self.service.activity_payout('excursion_task', chips, ids=sorted(ids))
            rows = await self.tasks()
        return rows

    async def check(self):
        svc, session = self.service, self.session
        if not START <= svc.now() < END:
            return
        self.load_budget()
        rpc = session.activity_request
        state = await rpc('GetMonopolyActData', {})
        if int(state.get('act_id', 0)) != ACTIVITY:
            return
        if self.pending_award:
            await self.resolve_award(state)
        rows = await self.tasks()
        if any(r['task_id'] == 100101 and r['status'] == 1 for r in rows):
            await svc._request('/task/report', {'task_type': 302, 'id': 19005})
            rows = await self.tasks()
        rows = await self.collect(rows)
        bag = await rpc('ItemList', {})
        items = {}
        for item in bag.get('item_list', []):
            expiry = int(item.get('deadline', 0))
            if expiry == 0 or expiry > svc.now():
                key = int(item['item_id'])
                items[key] = items.get(key, 0) + int(item['num'])
        # Limit work per pass so fund/task checks still get time on busy days.
        dice = items.get(DIE, 0)
        for _ in range(min(dice, 16)):
            state = await self.roll(state)
            await asyncio.sleep(1)
        await self.milestones(state)
        if dice:
            rows = await self.collect(await self.tasks())
            if dice > 16 or any(r['task_type'] == 312 and r['status'] == 3 for r in rows):
                svc.wake_excursion(5)
        if any(r['task_id'] == 100103 and r['status'] == 1 for r in rows):
            await self.free_emoji()
        for game in (COLOR, PINBALL):
            if self.plays[game] >= MAX_PLAYS:
                continue
            goals = [r for r in rows if r['task_type'] == 101 and r['value'][0] == game and r['status'] == 1]
            if goals:
                remaining = int(goals[0]['value'][1]) - int(goals[0]['current_value'])
                if remaining > 0:
                    await self.play_cheap(game, min(remaining, MAX_PLAYS - self.plays[game], 2))

    async def free_emoji(self):
        svc, session = self.service, self.session
        if not self.emoji_attempted:
            room, target = session.activity_table()
            if not room or not target:
                return
            player = await session.activity_request('SelfUserInfo', {})
            if int(player.get('emoji_free_times', 0)) <= 0 or session.activity_table() != (room, target):
                return
            svc._record('emoji_attempt', day=self.day, required=True)
            self.emoji_attempted = True
            await session.activity_request('SendEmoji', {'id': 1, 'to_uid': target}, room)
            svc._record('emoji_sent', day=self.day, required=True)
            self.emoji_report_due = True
        # The client reports TableChat / EmojiAni after SendEmojiRSP succeeds.
        # If HTTP fails, only retry the report while this task is incomplete.
        if self.emoji_report_due:
            await svc._request('/task/report', {'task_type': 304, 'id': 3})
            self.emoji_report_due = False
            svc._record('emoji_reported', day=self.day)
            svc.wake_excursion(1)

    def start_award(self, action, state):
        intent = dict(intent=uuid.uuid4().hex, activity=ACTIVITY, action=action,
                      used=int(state.get('all_cost_num', 0)), progress=int(state.get('progress', 0)))
        self.service._record('excursion_intent', **intent, required=True)
        self.pending_award = intent

    async def resolve_award(self, state):
        intent = self.pending_award
        if int(state.get('act_id', 0)) != ACTIVITY:
            raise RewardAPIError('GetMonopolyActData', 'activity changed')
        consumed = int(state.get('all_cost_num', 0))
        progress = int(state.get('progress', 0))
        if intent['action'] == 'roll':
            pos = int(state.get('index', 0))
            if consumed == intent['used']:
                self.service._record('excursion_not_applied', intent=intent['intent'])
            elif consumed == intent['used'] + 1 and 1 <= pos <= 24:
                await self.service.activity_payout('excursion_roll', GRID_CHIPS.get(pos, 0),
                                                   position=pos, used=consumed, intent=intent['intent'])
            else:
                await self.service.activity_uncertain('excursion_roll', intent=intent['intent'])
        elif progress == intent['progress']:
            self.service._record('excursion_not_applied', intent=intent['intent'])
        elif intent['progress'] < progress <= sum(consumed >= n for n in MILESTONES):
            chips = sum(MILESTONE_CHIPS.get(i, 0) for i in range(intent['progress'] + 1, progress + 1))
            await self.service.activity_payout('excursion_milestone', chips, progress=progress,
                                               used=consumed, intent=intent['intent'])
        else:
            await self.service.activity_uncertain('excursion_milestone', intent=intent['intent'])
        self.pending_award = None

    async def award_request(self, action, state, name, fields):
        self.start_award(action, state)
        try:
            after = await self.session.activity_request(name, fields)
        except RewardAPIError as exc:
            if exc.code is not None:
                self.service._record('excursion_rejected', intent=self.pending_award['intent'], code=exc.code)
                self.pending_award = None
            # If delivery is ambiguous, resolve from authoritative state on
            # a later pass, including after reconnecting or restarting.
            raise
        merged = {**state, **after}
        if (action == 'roll' and ('all_cost_num' not in after or 'index' not in after)
                or action == 'milestone' and 'progress' not in after):
            raise RewardAPIError(name, 'incomplete response')
        await self.resolve_award(merged)
        return merged

    async def roll(self, state):
        return await self.award_request('roll', state, 'ThrowDice', {'multiple': 1})

    async def milestones(self, state):
        ready = sum(int(state.get('all_cost_num', 0)) >= n for n in MILESTONES)
        while int(state.get('progress', 0)) < ready:
            old = int(state.get('progress', 0))
            state = await self.award_request('milestone', state, 'GetProgressReward', {})
            if int(state.get('progress', 0)) <= old:
                raise RewardAPIError('GetProgressReward', 'progress not advanced')

    def skip_game(self, game, reason):
        """Nothing to play today: say so once instead of asking for the config on every pass."""
        self.plays[game] = MAX_PLAYS
        self.service._record('sidegame_skipped', day=self.day, game=game, reason=reason)

    async def play_cheap(self, game, rounds):
        session, svc = self.session, self.service
        wallet = session.bankroll_dashboard().get('wallet_chips')
        if wallet is None:
            return
        conf = await session.activity_request('GetSideGameConf', {'game_type': game})
        if int(conf.get('game_type', 0)) != game:
            return self.skip_game(game, 'config is for another game')
        limit = minimum_bet(json.loads(conf['conf']), game, int(wallet))
        if not limit:
            return self.skip_game(game, f'no stake up to {MAX_BET} chips')
        level, stake = limit
        for _ in range(rounds):
            source = 10010101 if session.current_room_id() else 0
            self.plays[game] += 1
            svc._record('sidegame_attempt', day=self.day, game=game, level=level, stake=stake, required=True)
            try:
                if game == COLOR:
                    result = await session.activity_request('ColorGameAction', color_bet(level, stake, source))
                    net = color_profit(result, stake)
                else:
                    result = await session.activity_request('PinballAction', {
                        'lvl':level, 'from_game_type':source, 'per_bet':stake, 'ball_num':1})
                    balls = result['action_result']['balls']
                    if len(balls) != 1:
                        raise ValueError('expected one pinball')
                    net = int(balls[0].get('reward', 0)) - stake
            except (KeyError, ValueError, RewardAPIError) as exc:
                if not isinstance(exc, RewardAPIError) or exc.code is None:
                    # The round may have been played; only the side-game total is in doubt.
                    await svc.activity_uncertain('sidegame')
                raise
            svc._record('sidegame_result', game=game, stake=stake, net=net)
            await session.on_sidegame_result(net)
            await asyncio.sleep(1)
        svc.wake_excursion(15)
