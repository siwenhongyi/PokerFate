"""The radar's findings: the client's calendar held against what the registry can do.

A worker says which activity tables it plays (``tables``), which task types it does (``does``),
how many of them it does a day at most (``limits``) and what it leaves alone (``leaves``).
From that, for every period in the calendar and every task of the daily and weekly lists:

    uncovered   a period no worker plays: new code is needed
    gaps        tasks nobody does, and tasks somebody does but not as many as asked within the
                task's time (capacity)
    ended       a period a worker played has ended (its code went quiet by itself)
    hotupdate   the client changed: new tables, new pages, a changed protocol

A finding carries its ``items``, one per kind of task (its type and the thing it counts; its
steps are one item) or one for the period itself, each with the ignore key that would leave it
alone: the console's 雷达 tab works on them, the phone gets the text built from them.

What is left undone (uncovered, gaps) is told on every radar run until it is done or ignored
(``repeat``): a gap told once is easily forgotten. What happened (ended, hotupdate) is told
once; its digest comes from the facts, never from text that moves by itself. What the ignore
list (``core/ignore.py``, internal and external) covers stays out of the phone and is kept in the
report with its reason. A worker's ``leaves`` are its own decisions: shown, never a reason to tell.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path

from pf_intercept.headless.lobby.core.ignore import IGNORES
from pf_intercept.headless.lobby.core.needs import thing_of
from pf_intercept.headless.lobby.radar.calendar import (DAY, ROUTINE_TASKS, calendar, count_of, describe, stamp,
                                                        tasks_of)
from pf_reverse.tables import TABLES

AHEAD_SEC = 45 * DAY            # a period starting within this is told even before testers see it
ENDED_SEC = 3 * DAY             # a period that ended this recently is told as ended
LINES = 8                       # gap lines in a phone message; the rest are counted
HOLDEM = 10010101
# What the poker play itself does for tasks: hands, bets, wins, profit of the lobby hold'em.
PLAY = {(101, HOLDEM): "正式对局打手数", (103, HOLDEM): "正式对局下注", (104, HOLDEM): "正式对局赢牌",
        (102, HOLDEM): "正式对局盈利（看输赢）", (114, None): "全下获胜（看输赢）"}


@dataclass
class Finding:
    key: str
    title: str
    body: str               # what the phone shows
    facts: str = ""         # what the digest is taken from: the body without what moves by itself
    ignored: list = field(default_factory=list)     # lines left out on purpose (report only)
    muted: str = ""         # why the whole finding is not told (the ignore list), "" when it is
    repeat: bool = False    # something left undone: told on every run, not once
    items: list = field(default_factory=list)       # what the 雷达 tab shows and ignores, item by item
    when: str = ""          # the period's window, for the tab

    @property
    def digest(self) -> str:
        return hashlib.sha1((self.title + "\n" + (self.facts or self.body)).encode("utf-8")).hexdigest()[:12]


def capabilities(workers, extra=()):
    """(task_type, thing or None) -> (who, how, daily limit or None)."""
    found = {key: ("正式对局", how, None) for key, how in PLAY.items()}
    for who, does, limits in extra:
        found.update((key, (who, how, limits.get(key))) for key, how in does.items())
    for worker in workers:
        limits = getattr(worker, "limits", {}) or {}
        found.update((key, (worker.title or worker.name, how, limits.get(key))) for key, how in worker.does.items())
    return found


def coverage(workers):
    """Activity table -> the worker that plays its periods."""
    return {table: worker for worker in workers for table in worker.tables}


def who_does(task, able):
    key = thing_of(task.get("task_type"), task.get("value"))
    return able.get(key) or able.get((key[0], None))


def span_name(days):
    return "每日" if days <= 1 else ("每周" if days <= 7 else f"{days:.0f} 天内")


def task_item(kind, thing, what, steps, text, ignored, detail=""):
    prefix = "task" if what == "gap" else "limit"
    return {"key": f"{prefix}:{kind}" + (f":{thing}" if thing is not None else ""),
            "kind_key": f"{prefix}:{kind}" if thing is not None else None,
            "type": kind, "thing": thing, "what": what, "steps": steps, "text": text or "客户端没有说明",
            "detail": detail, "ignored": ignored}


def review(tasks, able, tables=TABLES, ignores=IGNORES):
    """Items for [(task, days it runs)]: what nobody does ("gap") and what somebody does but not
    as many as asked in the task's time ("limit"), one per kind of task."""
    gaps, short = {}, {}
    for task, days in tasks:
        key = thing_of(task.get("task_type"), task.get("value"))
        doer = who_does(task, able)
        if doer is None:
            gaps.setdefault(key, []).append((count_of(task), describe(task, tables)))
            continue
        who, _, per_day = doer
        if per_day and count_of(task) > per_day * days:
            worst = short.get(key)
            if worst is None or count_of(task) > worst[0]:
                short[key] = (count_of(task), describe(task, tables), who, per_day, days)
    order = lambda item: (item[0][0], item[0][1] or 0)      # noqa: E731
    items = []
    for (kind, thing), steps in sorted(gaps.items(), key=order):
        steps.sort()
        reason = ignores.task(kind, thing)
        items.append(task_item(kind, thing, "gap", len(steps), steps[0][1],
                               {"reason": reason[0], "by": reason[1]} if reason else None))
    for (kind, thing), (_, text, who, per_day, days) in sorted(short.items(), key=order):
        reason = ignores.limit(kind, thing)
        items.append(task_item(kind, thing, "limit", 1, text,
                               {"reason": reason[0], "by": reason[1]} if reason else None,
                               f"{who}每天最多 {per_day}，{span_name(days)}只能做到 {per_day * days:.0f}"))
    return items


def line(item):
    more = f"，共 {item['steps']} 档" if item["steps"] > 1 else ""
    text = f"· {item['text']}（类型 {item['type']}{more}）"
    if item["detail"]:
        text += f"：{item['detail']}"
    if item["ignored"]:
        text += f" —— {item['ignored']['reason']}（{item['ignored']['by']}）"
    return text


def lines(items, limit=LINES):
    out = [line(item) for item in items]
    return out[:limit] + ([f"· 另有 {len(out) - limit} 类"] if len(out) > limit else [])


def split(items):
    """(gaps, limits, ignored) of a finding's task items."""
    open_ = [i for i in items if not i["ignored"]]
    return ([i for i in open_ if i["what"] == "gap"], [i for i in open_ if i["what"] == "limit"],
            [i for i in items if i["ignored"]])


def count(items):
    return sum(item["steps"] for item in items)


def findings(now, workers, *, tables=TABLES, extra=(), update=None, ignores=IGNORES):
    """What the user should hear about, given the tables, the registry and the last sync."""
    able, played = capabilities(workers, extra), coverage(workers)
    out = []
    for seen in calendar(tables):
        state = seen.state(now)
        worker = played.get(seen.table)
        when = f"{stamp(seen.start)} → {stamp(seen.end)}（UTC+8）"
        head = f"{seen.kind} tpl_{seen.table} {seen.ident}\n{when}"
        if state == "ended":
            if worker is not None and now - seen.end <= ENDED_SEC:
                out.append(Finding(f"ended:{seen.table}:{seen.ident}", f"活动结束 · {seen.title}",
                                   f"{seen.kind}，{when}。\n{worker.title}的代码按表里的时间自己停了，不用删；"
                                   "下一期进表后自动接上。", when=when))
            continue
        if state == "upcoming" and seen.start - now > AHEAD_SEC and not 0 < seen.testers <= now:
            continue
        lead = "进行中" if state == "open" else f"{max(0, int((seen.start - now) // DAY))} 天后开始"
        items = review(tasks_of(seen, tables), able, tables, ignores)
        gaps, short, ignored = split(items)
        if worker is None:
            reason = ignores.period(seen.table, seen.ident)
            period = {"key": f"period:{seen.table}:{seen.ident}", "kind_key": f"table:{seen.table}",
                      "type": None, "thing": None, "what": "period", "steps": 1, "detail": "",
                      "text": f"整个活动（{seen.kind}）",
                      "ignored": {"reason": reason[0], "by": reason[1]} if reason else None}
            facts = head + "\n没有处理它的代码。" + ("\n现有能力做不了的任务：\n" + "\n".join(lines(gaps)) if gaps else "")
            out.append(Finding(f"uncovered:{seen.table}:{seen.ident}", f"新活动 · {seen.title}（还没有代码）",
                               head + f"，{lead}\n没有处理它的代码：要做的话需要新写一个模块。"
                               + (f"\n现有能力做不了的任务 {count(gaps)} 个：\n" + "\n".join(lines(gaps)) if gaps else ""),
                               facts, ignored=lines(ignored, limit=99),
                               muted=f"{reason[0]}（{reason[1]}）" if reason else "", repeat=True,
                               items=[period] + items, when=f"{when}，{lead}"))
            continue
        notes = [f"由「{worker.title}」处理。"]
        if worker.leaves:
            notes.append("有意不做：" + "；".join(worker.leaves))
        if gaps:
            notes.append(f"做不了的任务 {count(gaps)} 个：\n" + "\n".join(lines(gaps)))
        if short:
            notes.append("能做但额度不够：\n" + "\n".join(lines(short)))
        if gaps or short or ignored:
            body = "\n".join(notes)
            out.append(Finding(f"gaps:{seen.table}:{seen.ident}", f"活动缺口 · {seen.title}",
                               head + f"，{lead}\n" + body, head + "\n" + body, ignored=lines(ignored, limit=99),
                               muted="" if gaps or short else "都已忽略", repeat=True, items=items,
                               when=f"{when}，{lead}"))
    routine, routine_items = [], []
    for name, label, days in ROUTINE_TASKS:
        items = review([(t, days) for t in tables.rows(name)], able, tables, ignores)
        for item in items:
            item["list"] = label
        gaps, short, _ = split(items)
        if gaps:
            routine.append(f"{label}做不了 {count(gaps)} 个：\n" + "\n".join(lines(gaps, 6)))
        if short:
            routine.append(f"{label}能做但额度不够：\n" + "\n".join(lines(short, 6)))
        routine_items += items
    if routine_items:
        out.append(Finding("gaps:routine", "日常任务缺口", "\n".join(routine), ignored=lines(split(routine_items)[2], 99),
                           muted="" if routine else "都已忽略", repeat=True, items=routine_items,
                           when="每日任务、每周任务"))
    if update and update.get("res_from") != update.get("res_to"):
        out.append(hot_update_finding(update))
    return out


def told(found):
    """The findings that go to the phone: not those the ignore list covers whole."""
    return [f for f in found if not f.muted]


def hot_update_finding(update):
    changed, added, removed = update.get("changed") or [], update.get("added") or [], update.get("removed") or []
    lua = [p for p in changed if p.startswith("lua/")]
    proto = [p for p in changed + removed if p.startswith("proto/")]
    new_tables = sorted(Path(p).stem for p in added if p.startswith("lua/src/tpl/"))
    pages = sorted({"/".join(p.split("/")[3:5]) for p in added if p.startswith("lua/src/app/views/")})
    models = sorted(Path(p).stem for p in added if p.startswith("lua/src/app/model/"))
    text = [f"热更新层（pf_reverse/remote_res）现在和安装包基线不同的有 {update.get('differ', 0)} 个文件；"
            f"这次变了 {len(lua)} 个 lua、{len(proto)} 个 proto，删了 {len(removed)} 个。"]
    if new_tables:
        text.append("新表：" + "、".join(new_tables[:10]) + ("…" if len(new_tables) > 10 else ""))
    if pages:
        text.append("新界面（可能是新玩法）：" + "、".join(pages[:10]))
    if models:
        text.append("新数据模型：" + "、".join(models[:10]))
    if proto:
        text.append("协议变了：pf_intercept/wire/pb 是按安装包基线生成的，要不要跟进由你决定（gen_pb2.sh，重启生效）。")
    text.append("表里的数据 bot 不用重启就能读到；代码和协议的变化要重启才生效。")
    title = f"热更新 · {update.get('res_from') or '首次同步'} → {update.get('res_to')}"
    return Finding(f"hotupdate:{update.get('res_to')}", title, "\n".join(text))
