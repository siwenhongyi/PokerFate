"""Headless lobby rewards, following DevelopmentFund.lua and TaskModel.lua.

Only claims existing entitlements: no task/report, purchases, or AFK dispatch.
One background worker serializes all HTTP calls. Every retry re-reads server
state; an ambiguous claim response is journalled, never blindly replayed.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Awaitable, Callable

from pf_intercept.game_api.http import signed_post_json

log = logging.getLogger("pf_rewards")
GAME_REBATE_SETTLE = 10082
TASK_REFRESH = 10030
GOLD = 10100001
TASK_CATEGORIES = ((1, "daily"), (2, "weekly"), (6, "challenge"))
POLL_SEC = 300.0
RETRY_SEC = 30.0
HTTP_TIMEOUT_SEC = 8.0
UTC8 = timezone(timedelta(hours=8))
JOURNAL_PATH = Path(__file__).resolve().parents[1] / "logs" / "rewards.jsonl"


def next_fund_boundary(now: float) -> float:
    """Fund phases end at 07:00 / 19:00 UTC+8, independent of host timezone."""
    local = datetime.fromtimestamp(now, UTC8)
    for hour in (7, 19):
        boundary = local.replace(hour=hour, minute=0, second=0, microsecond=0)
        if boundary.timestamp() > now:
            return boundary.timestamp()
    return (local + timedelta(days=1)).replace(
        hour=7, minute=0, second=0, microsecond=0,
    ).timestamp()


def _int(value, default: int = 0) -> int:
    try:
        return int(value)
    except (ValueError, TypeError, OverflowError):
        return default


def _amount(value) -> int:
    amount = int(value)
    if amount < 0 or (isinstance(value, float) and amount != value):
        raise ValueError("invalid reward amount")
    return amount


def claimed_chips(data: dict, kind: str) -> int | None:
    if kind == "fund":
        status = _int(data.get("status"), -1)
        if status in (0, 2):
            return None
        if status != 1:
            raise ValueError("unknown fund status")
        return _amount(data["reward"])
    if not any(key in data for key in ("reward_chips", "reward_point", "item_list")):
        raise ValueError("missing reward fields")
    # TaskModel renders reward_chips and item_list as separate rewards.
    chips = _amount(data.get("reward_chips", 0))
    items = data.get("item_list") or []
    if not isinstance(items, list):
        raise ValueError("invalid reward items")
    for item in items:
        if not isinstance(item, dict) or "item_id" not in item:
            raise ValueError("invalid reward item")
        if _int(item["item_id"]) == GOLD:
            chips += _amount(item["num"])
    return chips


class RewardAPIError(RuntimeError):
    def __init__(self, endpoint: str, code=None):
        self.endpoint = endpoint
        self.code = code
        super().__init__(f"{endpoint} code={code}")


class RewardService:
    def __init__(
        self, *, uid: int, authorization: str, http_base: str,
        chnl: int, version: str,
        on_credit: Callable[[int, bool], Awaitable[None]],
        ready: asyncio.Event,
        on_claim_state: Callable[[bool], Awaitable[None]] | None = None,
        journal_path: Path = JOURNAL_PATH,
        post: Callable = signed_post_json,
    ) -> None:
        self.uid = uid
        self._authorization = authorization
        self._http_base = http_base.rstrip("/")
        self._chnl = chnl
        self._version = version
        self._post = post
        self._on_credit = on_credit
        self._on_claim_state = on_claim_state
        self._ready = ready
        self._journal_path = journal_path
        self._run_id = uuid.uuid4().hex[:12]
        self._wake = asyncio.Event()
        self._stopping = False
        self._task: asyncio.Task | None = None
        self._server_time: tuple[float, float] | None = None
        self._fund_due = 0.0
        self._tasks_due = 0.0
        self._boundary = 0.0
        self._settling_until = 0.0
        self._auth_failed = False
        self.confirmed_chips = 0
        self.claims = 0
        self.uncertain = False

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
        first = self._server_time is None
        self._server_time = (stamp, time.monotonic())
        if first:
            self._boundary = next_fund_boundary(self.now())
        self._wake.set()

    def notify(self, notice_type: int) -> None:
        if self._stopping or self._auth_failed:
            return
        if notice_type == GAME_REBATE_SETTLE:
            self._fund_due = 0.0
            self._settling_until = max(self._settling_until, self.now() + 600)
        elif notice_type == TASK_REFRESH:
            # Coalesce bursts without postponing an already scheduled refresh.
            self._tasks_due = min(self._tasks_due, self.now() + 0.5)
        else:
            return
        self._wake.set()

    def start(self) -> None:
        if self._task is not None:
            return
        if not self._authorization:
            log.warning("[REWARDS] 缺少会话 HTTP 凭证，自动领取关闭")
            return
        self._boundary = next_fund_boundary(self.now())
        self._task = asyncio.create_task(self._run(), name="headless-rewards")

    def set_http_base(self, http_base: str) -> None:
        # Keep claim/uncertainty state across a WSS reconnection or line change.
        self._http_base = http_base.rstrip("/")

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

    def _record(self, event: str, **fields) -> None:
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
        except Exception:
            # Do not log request payloads or credentials.
            data = None
        code = data.get("code") if isinstance(data, dict) else None
        if code == -2:
            self._auth_failed = True
            self._record("auth_failed", endpoint=endpoint)
            log.warning("[REWARDS] HTTP 登录态失效，暂停自动领取；更新凭证后重启生效")
        if code != 0:
            raise RewardAPIError(endpoint, code)
        return data

    async def _claim(self, endpoint: str, payload: dict, kind: str) -> dict:
        if self._on_claim_state is not None:
            await self._on_claim_state(True)
        try:
            return await self._claim_and_record(endpoint, payload, kind)
        finally:
            if self._on_claim_state is not None:
                await self._on_claim_state(False)

    async def _claim_and_record(self, endpoint: str, payload: dict, kind: str) -> dict:
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

    async def check_fund(self) -> None:
        status = await self._request("/activity/rebateStatus", {"t": 1})
        if _int(status.get("status")) != 1:
            return
        data = await self._claim("/activity/rebate", {"t": 1, "immediately": True}, "fund")
        if _int(data.get("status")) == 2:
            self._settling_until = max(self._settling_until, self.now() + 600)
            self._fund_due = min(self._fund_due, self.now() + RETRY_SEC)
        if not self._stopping:
            # No immediate second claim, even if read-after-write is stale.
            await self._request("/activity/rebateStatus", {"t": 1})

    async def check_tasks(self) -> None:
        data = await self._request("/task/list", {})
        rows = (row for _, name in TASK_CATEGORIES for row in data.get(name + "_list") or [])
        needs_card = any(row.get("monthly_card_task") and _int(row.get("status")) == 2 for row in rows)
        monthly_card = False
        if needs_card:
            try:
                pay = await self._request("/player/payInfo", {})
                monthly_card = _int((pay.get("data") or {}).get("monthly_card_exp")) > self.now()
            except RewardAPIError:
                # Unknown eligibility must not prevent ordinary task claims.
                if self._auth_failed or self._stopping:
                    raise
        for category, name in TASK_CATEGORIES:
            ids = sorted({_int(row.get("id")) for row in data.get(name + "_list") or []
                          if _int(row.get("status")) == 2 and _int(row.get("id")) > 0
                          and (not row.get("monthly_card_task") or monthly_card)})
            if ids:
                await self._claim("/task/recReward", {"task_cate": category, "id_arr": ids, "all": False}, name)
                data = await self._request("/task/list", {})
            # Task claims can unlock point chests in the same pass. Read again
            # after every chest; never retry the same chest within this pass.
            attempted = set()
            while not self._stopping:
                points = data.get("point_data") or {}
                received = {_int(i) for i in points.get(name + "_reward_id_list") or []}
                available = sorted(
                    (_int(c.get("reward_point")), _int(c.get("id")))
                    for c in data.get(name + "_point_conf_list") or []
                    if _int(c.get("id")) > 0 and "reward_point" in c
                    and _int(c.get("reward_point")) <= _int(points.get(name + "_point"))
                    and _int(c.get("id")) not in received | attempted
                )
                if not available:
                    break
                _, chest_id = available[0]
                attempted.add(chest_id)
                await self._claim("/task/recPointReward", {"id": chest_id, "task_cate": category}, name + "_points")
                data = await self._request("/task/list", {})

    async def _run(self) -> None:
        # A pre-claim wallet baseline prevents startup rewards becoming PnL.
        await self._ready.wait()
        if self._stopping:
            return
        self._record("started", fund=True, daily=True, weekly=True, challenge=True, poll_sec=POLL_SEC)
        while not self._stopping and not self._auth_failed:
            await self._ready.wait()
            if self._stopping:
                break
            self._wake.clear()
            now = self.now()
            if now >= self._boundary:
                self._boundary = next_fund_boundary(now)
                self._settling_until = now + 600
                self._fund_due = 0
            for kind in ("fund", "tasks"):
                if self._stopping or self._auth_failed:
                    break
                attr = "_" + kind + "_due"
                if self.now() < getattr(self, attr):
                    continue
                interval = RETRY_SEC if kind == "fund" and self.now() < self._settling_until else POLL_SEC
                # Set before awaiting so a push during an HTTP call is retained.
                setattr(self, attr, self.now() + interval)
                try:
                    await (self.check_fund() if kind == "fund" else self.check_tasks())
                except RewardAPIError as exc:
                    if exc.code != "stopped":
                        self._record("check_failed", kind=kind, endpoint=exc.endpoint, code=exc.code)
                        setattr(self, attr, self.now() + RETRY_SEC)
                except Exception:
                    log.exception("[REWARDS] %s check failed", kind)
                    setattr(self, attr, self.now() + RETRY_SEC)
            if self._stopping or self._auth_failed:
                break
            delay = max(0.01, min(self._fund_due, self._tasks_due, self._boundary) - self.now())
            try:
                await asyncio.wait_for(self._wake.wait(), timeout=delay)
            except asyncio.TimeoutError:
                pass
