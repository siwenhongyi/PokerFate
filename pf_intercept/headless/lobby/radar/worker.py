"""The radar inside the bot: a worker that runs the radar's command line in a subprocess.

Every ``RADAR_SEC`` it starts ``python -m pf_intercept.headless.lobby --json`` in the
background (the download and the decryption never share a process with the poker); the moment
the scan ends it wakes this worker, which reads what it printed and tells the phone: what is
left undone on every run, what happened once. The reward journal remembers what was sent,
across restarts too.

Six hours is enough: the radar only reads what the client downloads (the hot update) and holds
the client's tables against the registry, and a period reaches the tables weeks before it
opens. Whether the server has actually opened a period is not the radar's to watch: each
activity worker asks the server itself, every pass.
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

from pf_intercept.headless.lobby.core.base import REPEAT_SEC, Worker
from pf_intercept.headless.lobby.radar.findings import Finding

RADAR_SEC = 6 * 3600.0
RUN_TIMEOUT_SEC = 900.0
PROJECT_ROOT = Path(__file__).resolve().parents[4]


class Radar(Worker):
    name = "radar"
    title = "活动雷达"
    switch = ("radar", "不跑活动雷达（热更新同步、活动日历、能力和额度缺口提醒）")

    def __init__(self, service, session):
        super().__init__(service, session)
        self.job = None
        self.started = 0.0          # server time the running (or last) scan was started

    def interval(self):
        return RADAR_SEC

    async def check(self):
        """Start a scan; when it is done (its end wakes this check at once), tell what it found.
        The next scan starts ``RADAR_SEC`` after the last one started."""
        svc = self.service
        if self.job is None:
            self.started = svc.now()
            self.job = asyncio.create_task(self.scan(), name="lobby-radar")
            self.job.add_done_callback(lambda _: svc.wake(self.name, 0))
            return
        if not self.job.done():
            return
        job, self.job = self.job, None
        svc.due[self.name] = self.started + RADAR_SEC
        try:
            report = job.result()
        except Exception as exc:
            svc._record("radar_failed", error=f"{type(exc).__name__}: {exc}"[:300])
            return
        self.tell_findings(report)

    async def scan(self):
        proc = await asyncio.create_subprocess_exec(
            sys.executable, "-m", "pf_intercept.headless.lobby", "--json", cwd=str(PROJECT_ROOT),
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        try:
            out, err = await asyncio.wait_for(proc.communicate(), RUN_TIMEOUT_SEC)
        except asyncio.TimeoutError:
            proc.kill()
            raise
        if proc.returncode != 0:
            raise RuntimeError(f"radar exited {proc.returncode}: {err.decode('utf-8', 'replace')[-300:]}")
        return json.loads(out.decode("utf-8").strip().splitlines()[-1])

    def tell_findings(self, report):
        svc = self.service
        found = [Finding(**f) for f in report.get("findings") or []]
        told = [f for f in found if not f.muted]
        svc._record("radar_run", update=report.get("update"), error=report.get("error"),
                    findings=len(found), told=[f.key for f in told])
        for f in told:
            if f.repeat:
                svc.alert(f"radar:{f.key}", f.title, f.body, every=REPEAT_SEC)
            else:
                svc.alert(f"radar:{f.key}:{f.digest}", f.title, f.body)
