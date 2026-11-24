"""What the client's tables say about activities: every period, its window, its tasks.

Client knowledge only; nothing here knows the bot's workers.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from pf_intercept.headless.lobby.core.base import UTC8, _int
from pf_intercept.headless.lobby.core.needs import thing_of
from pf_reverse.tables import TABLES

DAY = 86400
GOODS = ("shop_", "props")      # tables with windows that are goods on sale, not activities
# How a period's tasks are found: activity table -> [(task tables, the column linking them,
# the period's column that lists the linked values or None for the period's own id, days a
# task of it runs: None for the whole period)].
TASK_LINKS = {
    "theme_activity": [(("theme_task",), "group", "task", None)],
    "monopoly_activity": [(("monopoly_task",), "group", "task", None)],
    "festival_activity": [(("festival_task",), "group", "task", None)],
    "creator_activity": [(("creator_activity_task",), "group", "daily_task", 1),
                         (("creator_activity_task",), "group", "version_task", None),
                         (("creator_activity_task",), "group", "creator_task", None)],
    "battle_pass_info": [(("battle_pass_tasks_week",), "battle_pass_id", None, 7),
                         (("battle_pass_tasks_period",), "battle_pass_id", None, None)],
    "invite_rules": [(("invite_task",), "invite_activity_id", None, None)],
}
# The lists the bot works for every day, and how long a task of each runs (the challenges run
# for ever, like achievements, and are left out).
ROUTINE_TASKS = (("dailytasks", "每日任务", 1), ("weeklytasks", "每周任务", 7))
KIND_NAMES = {"theme_activity": "主题活动", "monopoly_activity": "大富翁", "festival_activity": "节日活动",
              "creator_activity": "创作者活动", "battle_pass_info": "通行证", "event_check_in": "累签活动",
              "invite_rules": "邀请活动", "constdata:Dispatch": "协会经营（派遣）"}


def stamp(ts) -> str:
    return datetime.fromtimestamp(ts, UTC8).strftime("%m-%d %H:%M") if ts else "-"


@dataclass(frozen=True)
class Seen:
    """A period as the client's tables have it."""
    table: str
    ident: int
    title: str
    testers: float          # white_list_start: from then on it is in the client (0: not said)
    start: float
    end: float

    def state(self, now) -> str:
        if now > self.end:
            return "ended"
        return "open" if now >= self.start else "upcoming"

    @property
    def kind(self) -> str:
        return KIND_NAMES.get(self.table, f"tpl_{self.table}")

    @property
    def days(self) -> float:
        return max(1.0, (self.end - self.start) / DAY)


def calendar(tables=TABLES):
    """Every period of every activity table, in start order."""
    found = []
    for name in tables.names():
        if name.startswith(GOODS):
            continue
        rows = tables.rows(name)
        if not rows or "time_start" not in rows[0] or "time_end" not in rows[0]:
            continue
        for row in rows:
            start, end = _int(row.get("time_start")), _int(row.get("time_end"))
            if start <= 0 or end <= 0:
                continue
            ident = next(iter(row.values()))
            title = (tables.text(row.get("name")) if isinstance(row.get("name"), str)
                     else f"{KIND_NAMES.get(name, name)} {ident}")
            found.append(Seen(name, _int(ident), title, _int(row.get("white_list_start")), start, end))
    constants = tables.constants()
    for key, value in constants.items():
        if isinstance(key, str) and key.endswith("_Start") and isinstance(value, int):
            base = key[:-len("_Start")]
            end = constants.get(base + "_End")
            if isinstance(end, int) and end > 0:
                found.append(Seen(f"constdata:{base}", 0, KIND_NAMES.get(f"constdata:{base}", base),
                                  _int(constants.get(base + "_Start_Whitelist")), value, end))
    return sorted(found, key=lambda s: (s.start, s.table, s.ident))


def tasks_of(seen, tables=TABLES):
    """[(task row, days it runs)] of a period."""
    row = tables.row(seen.table, seen.ident) or {}
    out = []
    for names, column, listed, days in TASK_LINKS.get(seen.table, ()):
        if listed is None:
            wanted = {seen.ident}
        else:
            value = row.get(listed)
            wanted = {_int(v) for v in (value if isinstance(value, list) else [value]) if v is not None}
        span = days or seen.days
        out += [(task, span) for name in names for task in tables.rows(name) if _int(task.get(column)) in wanted]
    return out


def thing_name(thing, tables=TABLES):
    if thing is None:
        return ""
    jump = tables.row("task_type_info", thing)
    if jump:
        return tables.text(jump.get("name"))
    item = tables.row("props", thing)
    if item:
        return tables.text(item.get("name"))
    return str(thing)


def count_of(task) -> int:
    """What a task asks for: the last of its value."""
    value = task.get("value") if isinstance(task.get("value"), list) else []
    return _int(value[-1]) if value else 0


def describe(task, tables=TABLES) -> str:
    """The task's text as the client shows it ("打100手德州扑克"); "" when the client has none."""
    _, thing = thing_of(task.get("task_type"), task.get("value"))
    text = tables.text(task.get("dec") or task.get("des") or "")
    return text.replace("{p1}", str(count_of(task))).replace("{p2}", thing_name(thing, tables))
