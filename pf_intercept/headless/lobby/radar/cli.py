"""The radar's command line: ``python -m pf_intercept.headless.lobby``.

    python -m pf_intercept.headless.lobby              # sync the hot update, print the calendar and the findings
    python -m pf_intercept.headless.lobby --no-sync    # the tables as they are
    python -m pf_intercept.headless.lobby --json       # what the bot reads
    python -m pf_intercept.headless.lobby --ignore-file my_ignores.json   # an external ignore list
"""
from __future__ import annotations

import argparse
import time
from dataclasses import asdict

from pf_intercept.headless.lobby.core import ignore
from pf_intercept.headless.lobby.radar.calendar import calendar, stamp
from pf_intercept.headless.lobby.radar.findings import coverage, findings


def registry():
    """(the registered workers, the capabilities outside the registry: the task hands)."""
    from pf_intercept.headless.lobby import WORKERS
    from pf_intercept.headless.lobby.doers import taskhands
    return list(WORKERS), (("任务手数", taskhands.DOES, taskhands.LIMITS),)


def run(sync=True, now=None, ignores=None):
    """One radar run: (hot update summary, its error, findings)."""
    update, error = None, None
    if sync:
        try:
            from pf_reverse.hotupdate import sync as hot_sync
            update = hot_sync().summary()
        except Exception as exc:        # the calendar still comes from the tables there are
            error = f"{type(exc).__name__}: {exc}"
    workers, extra = registry()
    return update, error, findings(time.time() if now is None else now, workers, extra=extra, update=update,
                                   ignores=ignores or ignore.IGNORES)


def print_report(update, error, found, now):
    if error:
        print(f"热更新同步失败：{error}")
    elif update:
        print(f"资源版本：{update['res_from'] or '无记录'} → {update['res_to']}，下载 {update['downloaded']} 个包，"
              f"热更新层与安装包不同的文件 {update.get('differ', 0)} 个")
    workers, _ = registry()
    played = coverage(workers)
    print("\n活动日历（UTC+8）：")
    for seen in calendar():
        if seen.state(now) == "ended" and now - seen.end > 30 * 86400:
            continue
        state = {"ended": "已结束", "open": "进行中", "upcoming": "未开始"}[seen.state(now)]
        who = played.get(seen.table)
        print(f"  {state:4} {stamp(seen.start)} → {stamp(seen.end)}  {seen.title}（tpl_{seen.table} {seen.ident}）"
              f"  {'由 ' + who.title + ' 处理' if who else '没有代码'}")
    print(f"\n发现 {len(found)} 条：")
    for f in found:
        mark = f"（已忽略：{f.muted}）" if f.muted else ("（每次都发，直到做了或忽略）" if f.repeat else "（只发一次）")
        print(f"\n■ {f.title}{mark}")
        print(f.body)
        if f.ignored:
            print("已忽略：\n" + "\n".join(f.ignored))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="活动雷达：热更新同步 + 活动日历 + 能力和额度缺口")
    ap.add_argument("--no-sync", action="store_true", help="不访问 CDN，只读已同步的表")
    ap.add_argument("--json", action="store_true", help="输出给 bot 读的 JSON")
    ap.add_argument("--ignore-file", default=None, help="外部忽略列表（JSON），优先于内部的")
    args = ap.parse_args(argv)
    now = time.time()
    ignores = ignore.Ignores(external_path=args.ignore_file) if args.ignore_file else None
    update, error, found = run(sync=not args.no_sync, now=now, ignores=ignores)
    if args.json:
        import json
        print(json.dumps({"update": update, "error": error, "findings": [asdict(f) for f in found]},
                         ensure_ascii=False))
    else:
        print_report(update, error, found, now)
    return 0
