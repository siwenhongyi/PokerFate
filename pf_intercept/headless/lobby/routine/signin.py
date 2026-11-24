"""每日签到 (the seven-day sign-in). Requests from the client's SignInModel.lua and ActivitySignIn.lua.

Opening the sign-in page signs the day in; this does the same once a day. It is part of the
daily routine, like the task rewards, and depends on no activity: activities come and go, the
sign-in stays. A day that was missed is not made up: that spends the monthly card's allowance.

Tasks count the sign-in (the daily "签到 1 次", an activity's weekly chain), and a list may start
its day or week only when it is first read: a sign-in before that is lost (seen live on Monday
2026-11-23). The client reads its lists at login and signs in after; so does this: it signs in
once the reward service has run every check once and every source on the needs board has read
its list since the game day began. It asks them to read again if they have not.

Seen live since 2026-11-23: the state, the sign-in, and the reward in its answer. An action the
server refuses is not repeated for ``rewards.BLOCK_SEC``, a sign-in whose answer does not show
the day as signed is not repeated either, and what the server said is journalled when it changes.
"""
from __future__ import annotations

from pf_intercept.headless.lobby.core.base import GOLD, Activity, RewardAPIError, _amount, _int, day_start, rows_of

SIGN = "/activity/sevenSign"
RECHECK_SEC = 3600.0        # signed, and the server names no later time to come back at
WAIT_SEC = 10.0             # for the task lists to be read before signing


def signed_days(data):
    return sorted({_int(day) for day in rows_of(data.get("days")) if _int(day) > 0})


def today(data):
    """SignInModel._curSignInDay: the day of the running cycle, from 1; 0 when it cannot be told."""
    now, cycle = _int(data.get("cur_ts")), _int(data.get("cycle_ts"))
    return -(-(now - cycle) // 86400) if now > 0 and 0 < cycle < now else 0


def reward(answer):
    """Chips and every item of a sign-in: the day's, the running total's and the monthly card's."""
    items = [item for name in ("item_list", "total_item_list", "ext_item_list") for item in rows_of(answer.get(name))]
    chips = sum(_amount(item["num"]) for item in items if _int(item["item_id"]) == GOLD)
    return chips, [[_int(item["item_id"]), _amount(item["num"])] for item in items]


class SignIn(Activity):
    name = "signin"
    title = "七日签到"
    does = {(301, None): "每天签到"}

    def __init__(self, service, session):
        super().__init__(service, session)
        self.signed_until = 0.0     # server time before which there is nothing to do

    async def check(self):
        svc = self.service
        if svc.now() < self.signed_until:
            return
        self.load()
        if self.blocked("data"):
            return
        data = await self.ask("data", "/activity/sevenSignData", {})
        if data is None:
            return
        day, days = today(data), signed_days(data)
        self.tell("signin_state", day=day, days=days, next_sign_ts=_int(data.get("next_sign_ts")),
                  made_up=_int(data.get("miss_sign_cnt")), fields=sorted(map(str, data)))
        if day <= 0:
            return                  # which day it is cannot be told: nothing is signed blindly
        if day in days:
            self.rest(data)
            return
        if self.blocked("sign"):
            return
        needs = svc.needs
        if not svc.first_pass.is_set() or not needs.read_since(day_start(svc.now())):
            stale = sorted(source for source, (at, *_) in needs.reports.items() if at < day_start(svc.now()))
            self.tell("signin_waiting", day=day, for_lists=stale)
            needs.refresh()
            svc.wake("signin", WAIT_SEC)
            return
        # What ActivitySignIn sends when the page opens: day 0 is today.
        try:
            answer = await self.ask("sign", SIGN, {"day": 0})
            if answer is None:
                return
            try:
                chips, items = reward(answer)
            except (ValueError, TypeError, KeyError, OverflowError):
                raise RewardAPIError(SIGN) from None     # signed, with an amount that cannot be read
        except RewardAPIError as exc:
            if exc.code is None:    # it may have reached the server, and the reward may hold chips
                await svc.activity_uncertain("signin", day=day)
            raise
        await svc.activity_payout("signin", chips, day=day, items=items)
        if day in signed_days(answer):
            self.rest(answer)
        else:
            # Answered as signed and the day is still open: this worker misreads the sign-in.
            self.block("sign", RewardAPIError(SIGN, f"still due: day {day}"))

    def rest(self, data):
        """Signed for today: nothing more until the time the server gives for the next one."""
        now = self.service.now()
        ahead = _int(data.get("next_sign_ts"))
        self.signed_until = ahead if ahead > now else now + RECHECK_SEC
