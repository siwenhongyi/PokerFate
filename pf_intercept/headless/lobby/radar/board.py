"""What the console's 雷达 tab shows and changes.

``state()`` is the radar's findings item by item (what is left undone, what is ignored and on
whose decision) and every decision of the ignore list; ``change()`` writes one decision of the
user into the external ignore file and answers the new state. The web server knows nothing of
the lobby: the headless entry point hands it a Board.

Reading the findings takes the client's tables (cached; well under a second once read), so the
web server calls these from a thread, never on the event loop the poker runs on.
"""
from __future__ import annotations

import time

from pf_intercept.headless.lobby.core.ignore import IGNORES, valid_key
from pf_intercept.headless.lobby.radar.calendar import KIND_NAMES, count_of, describe, thing_name
from pf_intercept.headless.lobby.radar.findings import findings
from pf_reverse.hotupdate import REMOTE, load_manifest
from pf_reverse.tables import TABLES

# The task lists the bot works for (not the achievements, which run for ever).
TASK_TABLES = ("dailytasks", "weeklytasks", "battle_pass_tasks_week", "battle_pass_tasks_period", "theme_task",
               "monopoly_task", "creator_activity_task", "festival_task", "invite_task")


def label(key, tables=TABLES):
    """What a key means, in the client's words: "task:105" -> "类型 105 的任务，例：玩1场SNG"."""
    kind, _, rest = key.partition(":")
    if kind in ("task", "limit"):
        type_, _, thing = rest.partition(":")
        rows = []
        for name in TASK_TABLES:
            for row in tables.rows(name):
                value = row.get("value") if isinstance(row.get("value"), list) else []
                if str(row.get("task_type")) == type_ and (not thing or (len(value) >= 2 and str(value[0]) == thing)):
                    rows.append(row)
        if not rows:
            return f"任务类型 {type_}" + (f" · {thing}" if thing else "")
        # A limit is about the most a task asks for; a kind of task is shown by its first step.
        row = max(rows, key=count_of) if kind == "limit" else min(rows, key=count_of)
        text = describe(row, tables) or f"类型 {type_}"
        if kind == "limit":
            what = thing_name(int(thing), tables) if thing else f"类型 {type_}"
            return f"{what}每天的上限（任务最多要 {count_of(row)}，类型 {type_}）"
        return f"{text}（类型 {type_}）" if thing else f"类型 {type_} 的任务，例：{text}"
    if kind == "table":
        return f"{KIND_NAMES.get(rest, 'tpl_' + rest)}（整张表的每一期）"
    if kind == "period":
        table, _, ident = rest.rpartition(":")
        row = tables.row(table, int(ident)) if ident.isdigit() else None
        name = tables.text(row.get("name")) if row and isinstance(row.get("name"), str) else ident
        return f"{KIND_NAMES.get(table, 'tpl_' + table)} · {name}"
    return key


class Board:
    def __init__(self, ignores=IGNORES, workers=None):
        self.ignores = ignores
        self.workers = workers          # (workers, extra); None: the registry

    def state(self, now=None) -> dict:
        from pf_intercept.headless.lobby.radar.cli import registry
        workers, extra = self.workers or registry()
        found = findings(time.time() if now is None else now, workers, extra=extra, ignores=self.ignores)
        manifest = load_manifest(REMOTE)
        return {
            "findings": [{"key": f.key, "title": f.title, "when": f.when, "muted": f.muted, "items": f.items}
                         for f in found if f.repeat],
            "events": [{"key": f.key, "title": f.title, "body": f.body} for f in found if not f.repeat],
            "ignores": [{**entry, "label": label(entry["key"])} for entry in self.ignores.entries()],
            "file": str(self.ignores.external_path or ""),
            "res": manifest.get("res", ""),        # the client version the tables are from
        }

    def change(self, body: dict) -> dict:
        """{"action": "ignore", "key", "reason"} · {"action": "unignore", "key"} (take back one of the
        project's) · {"action": "reset", "key"} (forget the user's decision)."""
        key, action = body.get("key"), body.get("action")
        if not valid_key(key):
            raise ValueError("不认识的忽略键")
        if action == "ignore":
            self.ignores.set(key, True, body.get("reason") or "")
        elif action == "unignore":
            self.ignores.set(key, False, body.get("reason") or "")
        elif action == "reset":
            self.ignores.drop(key)
        else:
            raise ValueError("不认识的操作")
        return self.state()
