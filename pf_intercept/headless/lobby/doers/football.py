"""足球竞猜 (the football predictor), bet on only to take part.

Requests from the client's SoccerGuessingModel.lua and SoccerMain.lua, stakes from
tpl_predictor_bet. Tasks count bets ("参与足球竞猜 N 次" in the battle pass) and say so on the
board every source of tasks reports to (``rewards.Needs``): this module knows none of them.

One bet at a time, on a match it has not bet on, on the result most of the pool is on, of
``STAKE`` chips (100k, the user's decision of 2026-11-24). The server takes only what the client
can make from the chips it offers for the wallet: at a wallet over 100M it refused 1k and 10k
with -1 and took 100k. So the stake is sent only when it is a sum of those chips; 100k is, for
every wallet under 1B. After a bet the lists are read again; a bet they do not show is not
repeated for ``rewards.BLOCK_SEC``, and a refused one neither.

The client's rules: winners share the losers' pool in proportion to their stakes, less a 10%
fee on that pool; winnings, and refunds of cancelled matches, come by mail. The match list is
journalled as it came (``football_matches``: teams, pools, kick-off), each request with its
payload (``football_attempt``), a refusal with the server's whole answer (``football_blocked``).
A stake is journalled as it leaves (``football_bet``), what the server reports for past bets as
``football_history``, and what the mails bring as ``football_payout`` (mail.py); none of these
enters the poker, reward or side-game ledgers.

Written from the client's code; the server's answers were never seen on the wire.
"""
from __future__ import annotations

from pf_intercept.headless.lobby.core.base import Activity, RewardAPIError, _int, rows_of
from pf_intercept.headless.lobby.core.needs import task_key
from pf_reverse.tables import TABLES

KEY = task_key(322)           # "参与足球竞猜 N 次"
STAKE = 100_000                     # every bet (the user's); sent only when the client can make it
OPEN, LOCKED = 0, 1                 # SoccerStatus.Normal; lock
SETTLED, CANCELLED = 1, 2           # SoccerStatus.End (with is_settled), Removed
AREAS = (1, 2, 3)                   # AreaType: team 1, team 2, draw
KICKOFF_MARGIN_SEC = 120.0          # no bet on a match about to start: betting stops at kick-off
QUIET_SEC = 1800.0                  # nothing to bet on: look again this much later
COMEBACK_SEC = 3                    # after a bet the lists are read again


def is_open(status):
    """LobbyLayer:evt_BetStatusUpdate shows the predictor when betStatus's ``open`` is 0: a status
    code, 0 for open, not a flag. Lua takes neither false nor "0" for 0."""
    value = status.get("open")
    return isinstance(value, (int, float)) and not isinstance(value, bool) and value == 0


def tiers():
    """tpl_predictor_bet: (balance from which the tier is the client's, its smallest chip). Every
    chip of a tier is a multiple of its smallest, so the smallest says which amounts it can make."""
    return tuple((_int(r["balance"]), _int(r["chips1"])) for r in TABLES.rows("predictor_bet"))


def smallest_chip(wallet):
    """SoccerMain:setBetInfo: the highest tier the wallet reaches, and its smallest chip."""
    offered = tiers()
    return max((chip for balance, chip in offered if wallet >= balance), default=offered[0][1] if offered else 0)


def can_make(stake, wallet):
    """Whether the client could put ``stake`` together from the chips it offers for the wallet."""
    chip = smallest_chip(wallet)
    return chip <= stake <= wallet and stake % chip == 0


def favourite(match):
    """(area, {area: pool}): the result most of the pool is on, team 1 first on a tie. The fee is
    taken from the losers' pool only, so this side costs least."""
    pools = {}
    for area in rows_of(match.get("bet_area")):
        if isinstance(area, dict) and _int(area.get("type")) in AREAS:
            pools[_int(area["type"])] = _int(area.get("amount"))
    if not pools:
        return None, {}
    return max(sorted(pools), key=lambda kind: pools[kind]), pools


class Football(Activity):
    name = "football"
    title = "足球竞猜"
    switch = ("football", "不为任务下注足球竞猜，其余奖励照常")
    does = {(322, None): "按任务缺口下注热门方"}

    def __init__(self, service, session):
        super().__init__(service, session)
        self.pending = None         # (board order at the last bet, {source: count} before it)
        self.quiet_until = 0.0

    async def check(self):
        svc = self.service
        self.load()
        lacking = svc.needs.lacking(KEY)
        if self.pending is not None:
            order, before = self.pending
            after = svc.needs.settled(KEY, order)
            if after is None:
                return              # the lists have not been read since the bet
            self.pending = None
            now_done = svc.needs.done(KEY)
            if before and not any(now_done.get(source, 0) > count for source, count in before.items()):
                # Placed, and no list counted it: such a bet does not count.
                self.block("bet", RewardAPIError("/activity/bet", f"not counted: {before}"))
            lacking = after
        if not lacking or self.blocked("bet") or self.blocked("list") or svc.now() < self.quiet_until:
            return
        wallet = self.session.bankroll_dashboard().get("wallet_chips")
        if wallet is None:
            return
        stake, chip = STAKE, smallest_chip(int(wallet))
        if not can_make(stake, int(wallet)):
            self.tell("football_skipped", reason="the client cannot make the stake from this wallet",
                      stake=stake, client_chip=chip)
            return
        self.told.pop("football_skipped", None)
        status = await self.ask("list", "/activity/betStatus", {})
        if status is None:
            return
        if not is_open(status):
            self.tell("football_state", open=False, raw_open=status.get("open"), fields=sorted(map(str, status)))
            self.quiet_until = svc.now() + QUIET_SEC
            return
        listing = await self.ask("list", "/activity/betList", {})
        if listing is None:
            return
        history = await self.ask("list", "/activity/betHistory", {})
        if history is None:
            return
        mine = self.tell_history(history)
        now = svc.now()
        matches = [row for row in rows_of(listing.get("list")) if isinstance(row, dict)]
        ready = sorted((row for row in matches
                        if _int(row.get("status"), -1) == OPEN and _int(row.get("lock")) != LOCKED
                        and _int(row.get("game_start_time")) > now + KICKOFF_MARGIN_SEC
                        and str(row.get("bet_id")) not in mine and favourite(row)[0] is not None),
                       key=lambda row: (_int(row.get("game_start_time")), str(row.get("bet_id"))))
        self.tell("football_state", open=True, matches=len(matches), to_bet=len(ready),
                  fields=sorted(map(str, listing)), row_fields=sorted(map(str, matches[0])) if matches else [])
        # The list as it came: teams (bet_area[].name), pools, kick-off, lock, of every match.
        self.tell("football_matches", rows=matches)
        if not ready:
            self.quiet_until = now + QUIET_SEC
            return
        match = ready[0]
        area, pools = favourite(match)
        bet_id = match.get("bet_id")        # the server's own id, passed back as it came
        payload = {"bet_id": bet_id, "areas": [{"bet_area": area, "amount": stake}]}
        svc._record("football_attempt", bet_id=bet_id, area=area, stake=stake, client_chip=chip,
                    pools={str(kind): amount for kind, amount in pools.items()},
                    kickoff=_int(match.get("game_start_time")), wanted=lacking, payload=payload,
                    required=True)
        try:
            if await self.ask("bet", "/activity/bet", payload) is None:
                return              # refused (the answer is in football_blocked): left alone for a while
        except RewardAPIError:
            # No answer: the stake may have left. The history read on the next pass tells,
            # and a match bet on is not bet on again.
            svc._record("football_uncertain", bet_id=bet_id, stake=stake)
            raise
        svc._record("football_bet", bet_id=bet_id, area=area, stake=stake)
        self.pending = (svc.needs.order, svc.needs.done(KEY))
        svc.needs.played(KEY, 1, COMEBACK_SEC)
        svc.wake("football", COMEBACK_SEC + 2)

    def tell_history(self, history):
        """What the server reports about past bets; returns the ids of the matches bet on."""
        rows = [row for row in rows_of(history.get("list")) if isinstance(row, dict)]
        staked = paid = settled = cancelled = 0
        for row in rows:
            areas = [area for area in rows_of(row.get("bet_area")) if isinstance(area, dict)]
            staked += sum(_int(area.get("amount")) for area in areas)
            paid += sum(_int(area.get("reward")) for area in areas)
            settled += _int(row.get("status"), -1) == SETTLED and _int(row.get("is_settled")) == 1
            cancelled += _int(row.get("status"), -1) == CANCELLED
        self.tell("football_history", bets=len(rows), settled=settled, cancelled=cancelled,
                  staked=staked, paid=paid, row_fields=sorted(map(str, rows[0])) if rows else [])
        return {str(row.get("bet_id")) for row in rows}
