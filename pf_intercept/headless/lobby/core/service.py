"""The reward service: runs the lobby workers, owns their HTTP line, their journal and the
reward ledger. It knows no worker by name.

One background task runs a pass over the attached workers in the registry's order: a worker
whose time has come runs its ``check``. A server push wakes the workers that listen to it.
Every HTTP call goes through here, one at a time; every retry re-reads server state; an
ambiguous claim response is journalled, never blindly replayed. Chips a worker confirms reach
the bankroll through ``on_credit`` as rewards, never as poker profit.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from pathlib import Path
from typing import Awaitable, Callable

from pf_intercept.game_api.http import signed_post_json
from pf_intercept.headless.lobby.core.base import RewardAPIError, _int, claimed_chips
from pf_intercept.headless.lobby.core.needs import Needs

log = logging.getLogger("pf_rewards")
RETRY_SEC = 30.0
RETRY_MAX_SEC = 1800.0     # a check that keeps failing backs off to this
HTTP_TIMEOUT_SEC = 8.0
ALERT_MEMORY_SEC = 30 * 86400   # an alert sent within this is not sent again after a restart
JOURNAL_PATH = Path(__file__).resolve().parents[3] / "logs" / "rewards.jsonl"     # pf_intercept/logs


class RewardService:
    def __init__(
        self, *, uid: int, authorization: str, http_base: str,
        chnl: int, version: str,
        on_credit: Callable[[int, bool], Awaitable[None]],
        ready: asyncio.Event,
        journal_path: Path = JOURNAL_PATH,
        post: Callable = signed_post_json,
        alert: Callable | None = None,
    ) -> None:
        self.uid = uid
        self._authorization = authorization
        self._http_base = http_base.rstrip("/")
        self._chnl = chnl
        self._version = version
        self._post = post
        self._on_credit = on_credit
        self._ready = ready
        self._journal_path = journal_path
        self._alert = alert             # (title, body) -> the phone; None: journal only
        self._run_id = uuid.uuid4().hex[:12]
        self._wake = asyncio.Event()
        self._stopping = False
        self._task: asyncio.Task | None = None
        self._server_time: tuple[float, float] | None = None
        self.workers = {}               # name -> worker, in the order of a pass
        self.due = {}                   # name -> server time of its next check
        self.needs = Needs(self)        # what the task lists lack; every source reports, every player reads
        self.first_pass = asyncio.Event()   # every check has run once: the board is filled
        self._failures: dict[str, int] = {}   # consecutive failed passes per check
        self._alerted = None            # alert keys already sent (None: not read from the journal yet)
        self._auth_failed = False
        self.confirmed_chips = 0
        self.claims = 0
        self.uncertain = False

    def attach(self, worker):
        """Run ``worker`` in every pass from now on, after those attached before it."""
        self.workers[worker.name] = worker
        self.due.setdefault(worker.name, 0.0)
        return worker

    def now(self) -> float:
        if self._server_time is None:
            return time.time()
        stamp, monotonic = self._server_time
        return stamp + (time.monotonic() - monotonic)

    def observe_server_time(self, timestamp) -> None:
        stamp = _int(timestamp)
        if stamp <= 0:
            return
        # Protocol is seconds; tolerate millisecond timestamps on newer clients.
        if stamp > 100_000_000_000:
            stamp /= 1000
        self._server_time = (stamp, time.monotonic())
        self._wake.set()

    def notify(self, notice_type: int) -> None:
        """A server push (NotifyBRC type): it wakes every worker that listens to it."""
        if self._stopping or self._auth_failed:
            return
        heard = False
        for worker in self.workers.values():
            if notice_type in worker.pushes:
                worker.pushed(notice_type)
                heard = True
        if heard:
            self._wake.set()

    def wake(self, name, delay):
        """Run the check of worker ``name`` no later than ``delay`` seconds from now."""
        if name in self.due:        # a name that is not a worker has nothing to wake
            self.due[name] = min(self.due[name], self.now() + delay)
            self._wake.set()

    def alert(self, key, title, body, every=None):
        """Something the user has to act on: journalled, and sent to the phone. ``every`` None:
        once per key (an event: an activity ended, a hot update); seconds: again whenever the last
        one is older than that (something left undone, told until it is done or ignored). Across
        restarts too: the journal's alerts of the last ``ALERT_MEMORY_SEC`` are read once."""
        if self._alerted is None:
            self._alerted = self._journalled_alerts()
        last = self._alerted.get(key)
        if last is not None and (every is None or self.now() - last < every):
            return
        self._alerted[key] = self.now()
        self._record("alert", key=key, title=title, body=body)
        if self._alert is not None:
            try:
                self._alert(title, body)
            except Exception:
                log.exception("[REWARDS] alert failed")

    def _journalled_alerts(self):
        """{key: server time it was last sent} from the journal."""
        sent = {}
        try:
            lines = self._journal_path.read_text(encoding="utf-8").splitlines()
        except OSError:
            return sent
        floor = self.now() - ALERT_MEMORY_SEC
        for line in lines:
            if '"alert"' not in line:
                continue
            try:
                row = json.loads(line)
            except ValueError:
                continue
            at = float(row.get("server_ts") or 0)
            if row.get("event") == "alert" and row.get("uid") == self.uid and at >= floor:
                sent[row.get("key")] = max(at, sent.get(row.get("key"), 0.0))
        return sent

    def start(self) -> None:
        if self._task is not None:
            return
        if not self._authorization:
            log.warning("[REWARDS] 缺少会话 HTTP 凭证，自动领取关闭")
            return
        self._task = asyncio.create_task(self._run(), name="headless-rewards")

    def set_http_base(self, http_base: str) -> None:
        # Keep claim/uncertainty state across a WSS reconnection or line change.
        self._http_base = http_base.rstrip("/")

    def update_credentials(self, authorization: str, chnl: int, version: str) -> None:
        """Refresh the same account after client re-login, preserving the run's ledger."""
        self._authorization, self._chnl, self._version = authorization, chnl, version
        self._auth_failed = not bool(authorization)
        if self._task is not None and self._task.done():
            self._task = None
        self._wake.set()

    async def close(self) -> None:
        self._stopping = True
        self._wake.set()
        self._ready.set()
        # Do not cancel to_thread(): a claim may already have reached the server.
        # Let the one in-flight request finish and record its outcome first.
        if self._task is not None and self._task is not asyncio.current_task():
            await self._task
        log.info("[REWARDS] stopped claims=%d chips=%d uncertain=%s",
                 self.claims, self.confirmed_chips, self.uncertain)

    def _record(self, event: str, *, required=False, **fields) -> None:
        record = {"ts": time.time(), "server_ts": self.now(), "run_id": self._run_id,
                  "uid": self.uid, "event": event, **fields}
        line = json.dumps(record, ensure_ascii=False)
        log.info("[REWARDS] %s", line)
        try:
            self._journal_path.parent.mkdir(parents=True, exist_ok=True)
            with self._journal_path.open("a", encoding="utf-8") as fh:
                fh.write(line + "\n")
        except OSError:
            log.exception("[REWARDS] journal write failed")
            if required:
                raise RewardAPIError("reward journal", "write failed")

    async def _request(self, endpoint: str, payload: dict) -> dict:
        if self._stopping or self._auth_failed:
            raise RewardAPIError(endpoint, "stopped")
        if self._task is not None and not self._ready.is_set():
            # A request already sent still finishes and records its outcome;
            # stop the next HTTP step while the socket/bankroll is recovering.
            raise RewardAPIError(endpoint, "connection unavailable")
        try:
            data = await asyncio.to_thread(
                self._post, self._http_base + endpoint, payload,
                token=self._authorization, chnl=self._chnl, timeout=HTTP_TIMEOUT_SEC,
                extra_headers={"Version": self._version, "Lang": "en"},
            )
        except Exception as exc:
            # Do not log request payloads or credentials.
            log.warning("[REWARDS] %s request error: %s", endpoint, type(exc).__name__)
            data = None
        code = data.get("code") if isinstance(data, dict) else None
        if code == -2:
            self._auth_failed = True
            self._record("auth_failed", endpoint=endpoint)
            log.warning("[REWARDS] HTTP 登录态失效，暂停自动领取；更新凭证后重启生效")
        if code != 0:
            raise RewardAPIError(endpoint, code, data if isinstance(data, dict) else None)
        return data

    def _retry_delay(self, kind: str) -> float:
        """30s after the first failure, doubling while the same check keeps failing."""
        failures = self._failures[kind] = self._failures.get(kind, 0) + 1
        return min(RETRY_SEC * 2 ** (failures - 1), RETRY_MAX_SEC)

    async def activity_uncertain(self, kind, **details):
        self.uncertain = True
        self._record("claim_uncertain", kind=kind, **details)
        await self._on_credit(0, True)

    async def activity_payout(self, kind, chips, **details):
        self.confirmed_chips += chips
        self.claims += int(chips > 0)
        self._record("claimed" if chips else "activity_result", kind=kind,
                     chips=chips, total_chips=self.confirmed_chips, **details)
        if chips:
            await self._on_credit(chips, False)

    async def _claim(self, endpoint: str, payload: dict, kind: str) -> dict:
        try:
            data = await self._request(endpoint, payload)
            try:
                chips = claimed_chips(data, kind)
            except (ValueError, TypeError, KeyError, OverflowError):
                # A success code with an unreadable amount is not a zero award.
                raise RewardAPIError(endpoint) from None
        except RewardAPIError as exc:
            if exc.code is None:
                self.uncertain = True
                self._record("claim_uncertain", kind=kind, endpoint=endpoint, request=payload)
                await self._on_credit(0, True)
            raise
        if chips is None:  # fund is accumulating / settling
            return data
        self.confirmed_chips += chips
        self.claims += 1
        self._record("claimed", kind=kind, endpoint=endpoint, request=payload,
                     chips=chips, points=data.get("reward_point", 0),
                     items=data.get("item_list") or [], total_chips=self.confirmed_chips)
        await self._on_credit(chips, False)
        return data

    async def _run(self) -> None:
        # A pre-claim wallet baseline prevents startup rewards becoming PnL.
        await self._ready.wait()
        if self._stopping:
            return
        self._record("started", workers=list(self.workers))
        while not self._stopping and not self._auth_failed:
            await self._ready.wait()
            if self._stopping:
                break
            self._wake.clear()
            for worker in self.workers.values():
                worker.tick(self.now())
            for name, worker in list(self.workers.items()):
                if self._stopping or self._auth_failed:
                    break
                if self.now() < self.due[name]:
                    continue
                # Set before awaiting so a push during an HTTP call is retained.
                self.due[name] = self.now() + worker.interval()
                try:
                    await worker.check()
                    self._failures.pop(name, None)
                except RewardAPIError as exc:
                    if exc.code != "stopped":
                        self._record("check_failed", kind=name, endpoint=exc.endpoint, code=exc.code)
                        self.due[name] = self.now() + self._retry_delay(name)
                except Exception as exc:
                    log.exception("[REWARDS] %s check failed", name)
                    self._record("check_failed", kind=name, error=type(exc).__name__)
                    self.due[name] = self.now() + self._retry_delay(name)
            self.first_pass.set()
            if self._stopping or self._auth_failed:
                break
            wake_at = min([*self.due.values(), *(w.deadline() for w in self.workers.values()), self.now() + 3600])
            try:
                await asyncio.wait_for(self._wake.wait(), timeout=max(0.01, wake_at - self.now()))
            except asyncio.TimeoutError:
                pass
