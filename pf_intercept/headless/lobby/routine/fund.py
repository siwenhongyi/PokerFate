"""蓝湾发展基金 (the development fund): collect its dividend. Requests from DevelopmentFund.lua.

The fund pays out per phase; phases end at 07:00 and 19:00 UTC+8, and the server settles
for a while after each end (GAME_REBATE_SETTLE, 10082, is pushed when it is done). So the
check runs at every phase end, retries every ``RETRY_SEC`` while the phase settles, and
otherwise every ``POLL_SEC``. Never a second claim right after one: a fresh status read
follows instead, even when the read lags the write.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from pf_intercept.headless.lobby.core.base import POLL_SEC, UTC8, Worker, _int

GAME_REBATE_SETTLE = 10082
RETRY_SEC = 30.0
SETTLE_SEC = 600.0


def next_boundary(now: float) -> float:
    """Fund phases end at 07:00 / 19:00 UTC+8, independent of host timezone."""
    local = datetime.fromtimestamp(now, UTC8)
    for hour in (7, 19):
        boundary = local.replace(hour=hour, minute=0, second=0, microsecond=0)
        if boundary.timestamp() > now:
            return boundary.timestamp()
    return (local + timedelta(days=1)).replace(hour=7, minute=0, second=0, microsecond=0).timestamp()


class Fund(Worker):
    name = "fund"
    title = "蓝湾发展基金"
    pushes = (GAME_REBATE_SETTLE,)
    does = {(132, None): "领取发展基金分红"}

    def __init__(self, service, session):
        super().__init__(service, session)
        self.boundary = 0.0         # end of the current phase
        self.settling_until = 0.0   # until then the check runs every RETRY_SEC

    def tick(self, now):
        if not self.boundary:
            self.boundary = next_boundary(now)
        elif now >= self.boundary:
            self.boundary = next_boundary(now)
            self.settling_until = now + SETTLE_SEC
            self.service.due[self.name] = 0.0

    def deadline(self):
        return self.boundary or float("inf")

    def interval(self):
        return RETRY_SEC if self.service.now() < self.settling_until else POLL_SEC

    def pushed(self, notice_type):
        svc = self.service
        svc.due[self.name] = 0.0
        self.settling_until = max(self.settling_until, svc.now() + SETTLE_SEC)

    async def check(self):
        svc = self.service
        status = await svc._request("/activity/rebateStatus", {"t": 1})
        if _int(status.get("status")) != 1:
            return
        data = await svc._claim("/activity/rebate", {"t": 1, "immediately": True}, "fund")
        if _int(data.get("status")) == 2:
            self.settling_until = max(self.settling_until, svc.now() + SETTLE_SEC)
            svc.due[self.name] = min(svc.due[self.name], svc.now() + RETRY_SEC)
        if not svc._stopping:
            # No immediate second claim, even if read-after-write is stale.
            await svc._request("/activity/rebateStatus", {"t": 1})
