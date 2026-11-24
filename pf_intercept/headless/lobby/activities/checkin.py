"""累签活动 (event check-in: 天使祈祷中 is period 11). Requests from ActivityNewmanCheckinModel.lua.

Every period, not one: the server names the period that runs (``eventCheckInData.id``) and
the client's tpl_event_check_in says when it runs and what each day pays. The server keeps a
status per day: 1 is ready to collect, 2 collected (the client turns every 1 into 2 after
``recEventCheckIn``, which collects them all at once). So a pass reads the days and, when one
is ready, presses the page's button once; a fresh read has to show it collected.

Written from the client's code; the server's answers were never seen on the wire. So an action
the server refuses is not repeated for ``BLOCK_SEC`` and what the answers said is journalled.
"""
from __future__ import annotations

from pf_intercept.headless.lobby.core.base import Activity, RewardAPIError, _int

DATA, CLAIM = "/activity/eventCheckInData", "/activity/recEventCheckIn"
READY, COLLECTED = 1, 2
RECHECK_SEC = 3600.0            # the client reads the days once per login; this, once an hour


def days_of(data):
    """{day: status} from the answer's ``data`` (a map keyed by the day, or a list from day 1)."""
    raw = data.get("data")
    if isinstance(raw, list):
        return {day: _int(status) for day, status in enumerate(raw, 1)}
    if isinstance(raw, dict):
        return {_int(day): _int(status) for day, status in raw.items() if _int(day) > 0}
    return {}


class CheckIn(Activity):
    name = "checkin"
    title = "累签活动"
    switch = ("checkin", "不领累签活动（天使祈祷中等）的签到奖励，其余奖励照常")
    tables = ("event_check_in",)

    def interval(self):
        return RECHECK_SEC

    async def check(self):
        self.load()
        if self.blocked("data"):
            return
        data = await self.ask("data", DATA, {"t": 1})
        if data is None:
            return
        days = days_of(data)
        self.tell("checkin_state", id=_int(data.get("id")), days={str(d): s for d, s in sorted(days.items())},
                  fields=sorted(map(str, data)))
        found = self.period(data.get("id"))
        ready = sorted(day for day, status in days.items() if status == READY)
        if found is None or not ready or self.blocked("claim"):
            return
        if await self.ask("claim", CLAIM, {"id": found.ident}, claim=True) is None:
            return
        after = await self.ask("data", DATA, {"t": 1})
        if after is None:
            return
        still = sorted(day for day, status in days_of(after).items() if status == READY and day in ready)
        if still:
            # Answered as collected and still ready: this worker misreads the page.
            self.block("claim", RewardAPIError(CLAIM, "still ready: " + ",".join(map(str, still))))
