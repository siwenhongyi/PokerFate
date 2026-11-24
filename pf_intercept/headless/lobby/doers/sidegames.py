"""彩球机 and 弹球 (the side games): the one place that plays them.

What to play comes from the board every source of tasks reports to
(``rewards.Needs``): per game the largest gap among the sources, never the
sum. This module knows none of the sources.

The limits hold for all of them together: the cheapest advertised stake, never
above ``MAX_BET`` a round, and ``MAX_PLAYS`` rounds of each game per game day,
which turns at 03:00 UTC+8. Never chase losses. What was played is in the
reward journal, so the day's count survives a restart.
"""
from __future__ import annotations

import asyncio
import json

from pf_entertainment.color_game import color_bet, color_profit
from pf_intercept.headless.lobby.core.base import RewardAPIError, Worker, game_day

COLOR, PINBALL = 30030101, 30080101
MAX_BET = 1000
MAX_PLAYS = 100
ROUNDS_PER_PASS = 5     # of each game; the rest follows in the next pass, so the reward worker is never held long
COMEBACK_SEC = 15       # after rounds: the sources read their lists again, then the next rounds


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


class SideGames(Worker):
    name = "sidegames"
    title = "彩球机 / 弹球"
    switch = ("side-games", "不玩彩球机和弹球：任务和活动都不为它们下注，其余奖励照常")
    does = {(101, COLOR): "按任务缺口玩彩球机", (101, PINBALL): "按任务缺口玩弹球"}
    limits = {(101, COLOR): MAX_PLAYS, (101, PINBALL): MAX_PLAYS}      # rounds a game day
    GAMES = (COLOR, PINBALL)

    def __init__(self, service, session):
        super().__init__(service, session)
        self.day = None
        self.plays = {}

    async def check(self):
        """Play what the task lists lack: per game the largest gap, within the day's limit."""
        needs = self.service.needs
        played = False
        for game in self.GAMES:
            lacking = needs.lacking(game)
            if not lacking or not self.left(game):
                continue
            rounds = await self.play(game, max(lacking.values()))
            if rounds:
                self.service._record('sidegame_demand', day=self.day, game=game, rounds=rounds, wanted=lacking)
                needs.played(game, rounds, COMEBACK_SEC)
                played = True
        if played:
            self.service.wake(self.name, COMEBACK_SEC)

    def load(self):
        """The rounds of the current game day, from the journal when the day is new."""
        day = game_day(self.service.now())
        if self.day == day:
            return
        self.day = day
        self.plays = {game: 0 for game in self.GAMES}
        path = self.service._journal_path
        if not path.exists():
            return
        for line in path.read_text(encoding='utf-8').splitlines():
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if row.get('uid') != self.service.uid or row.get('day') != day or row.get('game') not in self.plays:
                continue
            if row.get('event') == 'sidegame_attempt':
                self.plays[row['game']] += 1
            elif row.get('event') == 'sidegame_skipped':
                self.plays[row['game']] = MAX_PLAYS

    def left(self, game):
        """Rounds of a game that may still be played today."""
        self.load()
        return max(0, MAX_PLAYS - self.plays[game])

    def skip(self, game, reason):
        """Nothing to play today: say so once instead of asking for the config on every pass."""
        self.plays[game] = MAX_PLAYS
        self.service._record('sidegame_skipped', day=self.day, game=game, reason=reason)

    async def play(self, game, rounds):
        """Play up to ``rounds`` rounds of a game, a few per pass and within the day's limit.
        Returns how many were played."""
        session, svc = self.session, self.service
        rounds = min(rounds, self.left(game), ROUNDS_PER_PASS)
        if rounds <= 0:
            return 0
        wallet = session.bankroll_dashboard().get('wallet_chips')
        if wallet is None:
            return 0
        conf = await session.activity_request('GetSideGameConf', {'game_type': game})
        if int(conf.get('game_type', 0)) != game:
            self.skip(game, 'config is for another game')
            return 0
        limit = minimum_bet(json.loads(conf['conf']), game, int(wallet))
        if not limit:
            self.skip(game, f'no stake up to {MAX_BET} chips')
            return 0
        level, stake = limit
        for _ in range(rounds):
            source = session.table_game()       # the game the round is opened from, 0 in the lobby
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
        return rounds
