"""What every piece of lobby work shares: errors, reading the server's answers, the game's
clock, and the two base classes.

``Worker`` is one kind of lobby work the reward service runs in its pass. It says about
itself what the service, the command line and the radar need to know: its name, the server
pushes that wake it, the switch that turns it off, the client tables whose periods it plays
and the task types it can do. Nothing else knows a worker by name: the registry in
``lobby/__init__.py`` lists them, one line each.

``Activity`` is a worker written from the client's code, whose requests were not seen on the
wire first: an action the server refuses is left alone for ``BLOCK_SEC``, across restarts
too, and an answer that never arrived is raised for the caller to follow with a fresh read.

An activity that comes back in periods works as the client does (ActivityBase.lua and the
models built on it): the server names the period that runs (an id), the client's table for
that kind of activity says when it runs and what it pays. ``Activity.period`` reads it, so a
new period needs a table sync, not new code, and a period that is over is left alone without
anyone switching it off.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from pf_reverse.tables import TABLES

GOLD = 10100001                 # the chips item
POLL_SEC = 300.0                # a worker's check runs at least this often
BLOCK_SEC = 6 * 3600.0          # an activity action the server refused is left alone for this long
IDLE_SEC = 3600.0               # an activity with no period running is looked at this often
REPEAT_SEC = 5.5 * 3600         # something left undone is told again after this: once per radar run (6 h)
UTC8 = timezone(timedelta(hours=8))


def game_day(now: float) -> str:
    """The game's day, which turns at 03:00 UTC+8: daily tasks and daily limits follow it."""
    return (datetime.fromtimestamp(now, UTC8) - timedelta(hours=3)).date().isoformat()


def day_start(now: float) -> float:
    """Server time at which the current game day began (03:00 UTC+8)."""
    local = datetime.fromtimestamp(now, UTC8) - timedelta(hours=3)
    return local.replace(hour=3, minute=0, second=0, microsecond=0).timestamp()


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


def rows_of(value):
    """A list from the server, which the client walks with pairs(): array or map alike."""
    if isinstance(value, dict):
        value = list(value.values())
    return value if isinstance(value, list) else []


def claimed_chips(data: dict, kind: str) -> int | None:
    """Chips in a claim's answer. None for a fund that is still accumulating or settling."""
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
    def __init__(self, endpoint: str, code=None, reply=None):
        self.endpoint = endpoint
        self.code = code
        self.reply = reply      # the server's whole answer to a refused request, when there was one
        super().__init__(f"{endpoint} code={code}")


def refused(exc) -> bool:
    """The server answered with an error code; -2 (login expired) is the service's to handle."""
    return isinstance(exc.code, int) and not isinstance(exc.code, bool) and exc.code != -2


@dataclass(frozen=True)
class Period:
    """One period of an activity: the client's table row for the id the server named."""
    table: str
    ident: int
    row: dict
    start: float
    end: float

    def open(self, now) -> bool:
        # The client's isActivityOpen: start <= now <= end.
        return self.start <= now <= self.end

    @property
    def title(self) -> str:
        return TABLES.text(self.row.get("name")) if self.row.get("name") else f"{self.table} {self.ident}"


def period(table, ident, tables=TABLES):
    """The period ``ident`` of the activity kept in ``table`` (time_start / time_end), else None."""
    row = tables.row(table, ident)
    if row is None or _int(row.get("time_start")) <= 0:
        return None
    return Period(table, ident, row, float(row["time_start"]), float(row["time_end"]))


class Worker:
    """One kind of lobby work: ``check`` runs in the reward service's pass."""

    name = ""           # its check, the prefix of its journal events, its source on the needs board
    title = ""          # what the game calls it, for the radar and the logs
    switch = None       # (flag, help): ``--no-<flag>`` leaves it out; None = always on
    pushes = ()         # server pushes (NotifyBRC types) that wake it
    tables = ()         # client tables whose periods it plays: the radar's coverage
    does = {}           # (task_type, what or None) -> what it does: the radar's capabilities
    leaves = ()         # parts of its activity it leaves alone on purpose, said by the radar

    def __init__(self, service, session):
        self.service = service
        self.session = session

    async def check(self):
        raise NotImplementedError

    def pushed(self, notice_type):
        """A push it listens to arrived: by default it runs again within a second."""
        self.service.wake(self.name, 1)

    def interval(self) -> float:
        """Seconds until its next routine check; a push or a wake comes sooner."""
        return POLL_SEC

    def tick(self, now):
        """Called at the start of every pass, before any check."""

    def deadline(self) -> float:
        """Server time at which the service has to wake whatever else is due (inf: none)."""
        return float("inf")


class Activity(Worker):
    """A worker written from the client's code; see the module's docstring."""

    def __init__(self, service, session):
        super().__init__(service, session)
        self.blocks = {}        # action -> server time until which it is not tried again
        self.told = {}          # journal event -> what it last said
        self.loaded = False
        self.running = None     # whether the last read found a period of it running (None: not read)

    def load(self):
        """Read this account's journal rows of the last 24 h once: refusals, and ``replay``."""
        if self.loaded:
            return
        self.loaded = True
        path = self.service._journal_path
        if not path.exists():
            return
        floor = self.service.now() - 86400
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                row = json.loads(line)
                if row.get("uid") != self.service.uid or float(row["server_ts"]) < floor:
                    continue
                if row["event"] == self.name + "_blocked":
                    self.blocks[str(row["action"])] = float(row["until"])
                else:
                    self.replay(row)
            except (ValueError, TypeError, KeyError, AttributeError):
                continue

    def replay(self, row):
        """What else a worker keeps across a restart."""

    def blocked(self, action):
        return self.service.now() < self.blocks.get(action, 0)

    def block(self, action, exc):
        until = self.service.now() + BLOCK_SEC
        self.blocks[action] = until
        self.service._record(self.name + "_blocked", action=action, endpoint=exc.endpoint,
                             code=exc.code, until=until, reply=exc.reply)

    async def ask(self, action, endpoint, payload, claim=False):
        """One request. A refusal blocks the action and returns None; no answer raises."""
        try:
            if claim:
                # Answered with reward_chips / item_list, like the task rewards.
                return await self.service._claim(endpoint, payload, f"{self.name}_{action}")
            return await self.service._request(endpoint, payload)
        except RewardAPIError as exc:
            if not refused(exc):
                raise
            self.block(action, exc)
            return None

    def tell(self, event, **fields):
        """Journal a condition when it changes, not on every pass."""
        if self.told.get(event) != fields:
            self.told[event] = fields
            self.service._record(event, **fields)

    async def held(self, item):
        """Pieces of an item in the bag that have not expired, read over the game socket."""
        bag = await self.session.activity_request("ItemList", {})
        now = self.service.now()
        return sum(_int(row.get("num")) for row in bag.get("item_list") or []
                   if _int(row.get("item_id")) == item
                   and (_int(row.get("deadline")) == 0 or _int(row.get("deadline")) > now))

    def interval(self):
        """Outside a period an activity is looked at once an hour (the client looks once per login)."""
        return POLL_SEC if self.running is not False else IDLE_SEC

    def period(self, ident, table=None):
        """The period the server named, if it runs now; else None, and nothing is done.

        No id (0) is no period. An id the client's table lacks means the tables are behind the
        server (a hot update not yet synced): said once in the journal and to the phone, so
        the period is not missed in silence."""
        table = table or self.tables[0]
        ident = _int(ident)
        self.running = False
        if ident <= 0:
            self.tell(f"{self.name}_period", table=table, ident=0)
            return None
        found = period(table, ident)
        if found is None:
            self.tell(f"{self.name}_period", table=table, ident=ident, known=False)
            self.service.alert(f"period:{table}:{ident}", "活动 · 服务器开了表里没有的一期",
                               f"{self.title or self.name}：服务器说当前是第 {ident} 期，"
                               f"客户端表 tpl_{table} 里没有。热更新同步后自动接上。", every=REPEAT_SEC)
            return None
        now = self.service.now()
        self.tell(f"{self.name}_period", table=table, ident=ident, start=found.start, end=found.end,
                  open=found.open(now))
        self.running = found.open(now)
        return found if self.running else None
