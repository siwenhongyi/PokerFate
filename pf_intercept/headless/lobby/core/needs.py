"""What the task lists still lack: the board between those who read tasks and those who act.

The server counts one round of a side game, one hand of a poker game, one bet, one page
opened, for every task that counts it, whichever list the task is in. So nobody acts for a
list of its own. Each source of tasks (the daily and weekly tasks, the battle pass, an
activity) hands over the rows it has just read with ``want``. Whoever acts asks ``lacking``
what each source lacks and acts for the largest gap, never the sum: a hundred for one source
are also the fifteen another one lacks. ``played`` takes what was done off every gap at once.

A source that stops reporting (an activity that ended, a worker switched off) drops out by
itself after ``STALE_SEC``; a new one only has to call ``want``. Neither side knows the other.

Every task that counts something is on the board, keyed by ``key_of``: rounds or hands of a
game by the game, a count about one thing ("查看 X 界面", "牌局内使用 N 次表情", "投掷 N 颗骰子")
by ``task_key(type, thing)``, an exchange in a shop ("在礼物碎片商城兑换结缘晶片 N 次") by
``shop_key(shop, good)``, any other count ("参与足球竞猜 N 次", "签到 N 次") by
``task_key(type)``. A task that counts chips bet moves with the same play and is never a
reason to play more.
"""
from __future__ import annotations

from pf_intercept.headless.lobby.core.base import _int

COUNTS = 101            # task_type "玩 N 次 / 手": value = [game, count]
IN_PROGRESS = 1         # TaskStatus.InProgress
# Task types whose value is [the thing counted, ..., count] (the census of the client's task tables).
ABOUT = {101, 102, 103, 104, 108, 111, 112, 117, 119, 120, 123, 126, 127, 128, 302, 304, 311, 312, 313, 321, 401}
# Of those, the ones on the board besides the games: a count about one thing someone here can do.
# Profit, chips bet, hands won move with the same play and are never a reason to play more.
ON_BOARD = {302, 304, 312}
EXCHANGE = 313                  # "在 X 商店兑换 N 次": value = [shop, good (0: anything), ..., count]


def task_key(task_type, thing=None) -> str:
    """The board's key for tasks that count something other than a game's rounds or hands."""
    return f"task_type:{int(task_type)}" if thing is None else f"task_type:{int(task_type)}:{int(thing)}"


def shop_key(shop, good=0) -> str:
    """The board's key for "exchange N times in shop ``shop``" (``good`` 0: anything of it)."""
    return f"task_type:313:{int(shop)}:{int(good)}"


def key_of(row):
    """(key, count asked for) of a task row that counts something, else None. Every task list has
    rows of this shape: ``task_type``, ``status``, ``value`` and ``current_value``."""
    value = row.get("value") if isinstance(row, dict) else None
    if not isinstance(value, list):
        return None
    kind = _int(row.get("task_type"))
    if kind == COUNTS and len(value) == 2 and _int(value[0]) > 0:
        return _int(value[0]), _int(value[1])
    if kind == EXCHANGE and len(value) >= 3:
        # [shop, good, (shop, good, ...), count]: the first shop the client's jump opens
        return shop_key(_int(value[0]), _int(value[1])), _int(value[-1])
    if kind in ON_BOARD and len(value) == 2:
        return task_key(kind, _int(value[0])), _int(value[1])
    if kind > 0 and kind not in ABOUT and len(value) == 1:
        return task_key(kind), _int(value[0])
    return None


def thing_of(task_type, value):
    """(task_type, the thing it counts or None): how the radar looks a task up in ``Worker.does``."""
    value = value if isinstance(value, list) else []
    if _int(task_type) in ABOUT and len(value) >= 2:
        return _int(task_type), _int(value[0])
    return _int(task_type), None


class Needs:
    STALE_SEC = 900.0
    COUNTS, IN_PROGRESS = COUNTS, IN_PROGRESS
    task_key = staticmethod(task_key)
    key_of = staticmethod(key_of)

    def __init__(self, service):
        self.service = service
        # source -> (server time of its report, {key: what it lacks}, its order, {key: count so far})
        self.reports = {}
        self.order = 0          # counts the reports: "read again since" is told by it, not by a clock

    @staticmethod
    def gaps(rows):
        """Per thing counted, the largest gap in ``rows``. A chain shows its current step, so the
        gap is to that step; the next one shows in the next read."""
        lacking = {}
        for row in rows or ():
            got = key_of(row)
            if got is None or _int(row.get("status")) != IN_PROGRESS:
                continue
            key, need = got
            gap = need - _int(row.get("current_value"))
            if gap > lacking.get(key, 0):
                lacking[key] = gap
        return lacking

    @staticmethod
    def counted(rows):
        """Per thing counted, how far the count has got in ``rows``, whatever the status. A
        chain's steps share one count, so this moves when the step a gap was read from is done."""
        done = {}
        for row in rows or ():
            got = key_of(row)
            if got is not None:
                done[got[0]] = max(done.get(got[0], 0), _int(row.get("current_value")))
        return done

    def want(self, source, rows):
        """A source's task rows, as it has just read them. ``source`` is the name of the
        reward-service check that read them: it is woken to read again after play."""
        self.order += 1
        rows = list(rows or ())
        self.reports[source] = (self.service.now(), self.gaps(rows), self.order, self.counted(rows))

    def drop_stale(self):
        now = self.service.now()
        for source in [name for name, (at, *_) in self.reports.items() if now - at > self.STALE_SEC]:
            del self.reports[source]

    def lacking(self, key):
        """What each source that still reports lacks: {source: count}."""
        self.drop_stale()
        return {source: gap[key] for source, (_, gap, *_) in self.reports.items() if gap.get(key, 0) > 0}

    def keys(self):
        """Every key some source still lacks."""
        self.drop_stale()
        return sorted({key for _, gap, *_ in self.reports.values() for key, left in gap.items() if left > 0},
                      key=str)

    def done(self, key):
        """How far each source that still reports has counted: {source: count}."""
        self.drop_stale()
        return {source: done[key] for source, (*_, done) in self.reports.items() if key in done}

    def read_since(self, moment) -> bool:
        """Every source that still reports has read its list at or after ``moment`` (server time)."""
        self.drop_stale()
        return all(at >= moment for at, *_ in self.reports.values())

    def refresh(self):
        """Ask every source to read its list again now."""
        for source in list(self.reports):
            self.service.wake(source, 0)

    def settled(self, key, since):
        """What each source lacks once the lists say so themselves: None until every source that
        follows ``key`` has read its list after ``since`` (a value of ``order``). Until then a
        gap is only what this side worked out by taking off what it played."""
        lacking = self.lacking(key)     # also drops the sources that stopped reporting
        if any(order <= since for _, gap, order, _ in self.reports.values() if key in gap):
            return None
        return lacking

    def played(self, key, count, comeback):
        """``count`` was done: it counted for every source, so nobody is still owed it. The
        sources that lacked some read their lists again in ``comeback`` seconds."""
        served = self.lacking(key)
        for _, gap, *_ in self.reports.values():
            if key in gap:
                gap[key] = max(0, gap[key] - count)
        for source in served:
            self.service.wake(source, comeback)
        return served
