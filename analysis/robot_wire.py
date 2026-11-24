"""Replay the headless wire log through the rb_num inference and (optionally) write the registry.

    .venv/bin/python -m analysis.robot_wire                       # report only
    .venv/bin/python -m analysis.robot_wire --write               # also (re)build robots.json
    .venv/bin/python -m analysis.robot_wire --log other.log --registry /tmp/r.json --write

The live client keeps the registry up to date by itself; this is for bootstrapping it from
history and for checking what the counter says about a UID range.
"""
from __future__ import annotations

import argparse
import ast
import re
import tempfile
import time
from collections import Counter
from pathlib import Path

from pokerfate.core.robots import DEFAULT_PATH, HUMAN, ROBOT, RobotRegistry, RoomRobotTracker

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LOG = ROOT / "pf_intercept" / "logs" / "headless.log"
_TYPES = ("pb.EnterRoomRSP", "pb.SitDownBRC", "pb.OtherLeaveRoomBRC", "pb.OtherEnterRoomBRC",
          "pb.LeaveRoomRSP", "pb.SelfUserInfoRSP")
_LINE = re.compile(r"^(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d),\d+ \[\w+\] \S+ \[S→C\] (pb\.\w+) (\{.*\})\s*$")


def iter_events(path: Path):
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if "[S→C] pb." not in line or not any(t in line for t in _TYPES):
                continue
            m = _LINE.match(line)
            if not m or m.group(2) not in _TYPES:
                continue
            try:
                msg = ast.literal_eval(m.group(3))
            except (ValueError, SyntaxError):
                continue
            yield time.mktime(time.strptime(m.group(1), "%Y-%m-%d %H:%M:%S")), m.group(2), msg


def replay(path: Path, registry: RobotRegistry, my_uid: str = "") -> dict:
    tracker = RoomRobotTracker(registry, my_uid or None)
    seen, stats = set(), Counter()
    for ts, kind, msg in iter_events(path):
        if kind == "pb.SelfUserInfoRSP":
            uid = (msg.get("brief") or msg.get("user") or msg).get("uid")
            if uid:
                tracker.set_my_uid(uid)
        elif kind == "pb.EnterRoomRSP":
            if int(msg.get("code", 0) or 0) != 0:
                continue
            seats = [s.get("player", {}).get("uid") for s in (msg.get("table_status") or {}).get("seat", [])]
            seats = [s for s in seats if s]
            tracker.reset(seats)
            seen.update(str(s) for s in seats)
            stats["enter_room"] += 1
        elif kind == "pb.SitDownBRC":
            uid = ((msg.get("status") or {}).get("player") or {}).get("uid")
            if uid:
                tracker.sat_down(uid)
                seen.add(str(uid))
        elif kind == "pb.OtherEnterRoomBRC":
            uid = (msg.get("user") or {}).get("uid")
            if uid:
                tracker.entered(uid)
                seen.add(str(uid))
                stats["enter_counts"] += 1
        elif kind == "pb.OtherLeaveRoomBRC":
            uid = msg.get("uid")
            if uid is None:
                continue
            if str(uid) == tracker.my_uid:
                tracker.reset()
                continue
            tracker.left(uid, msg.get("num", 0), msg.get("rb_num", 0), ts=ts)
            stats["leave_counts"] += 1
        elif kind == "pb.LeaveRoomRSP":
            if int(msg.get("code", 0) or 0) in (0, 2, 3):
                tracker.reset()
    seen.discard(tracker.my_uid)
    stats["count_events"] = tracker.events
    stats["count_events_skipped"] = tracker.skipped
    stats["count_mismatches"] = tracker.mismatches
    return {"seen": seen, "stats": stats}


def report(registry: RobotRegistry, seen: set, stats: Counter) -> None:
    robots, humans = registry.robots(), registry.humans()
    print(f"房内计数事件 {stats['count_events']} 次（其中人数对不上、未用于推断 {stats['count_events_skipped']} 次，"
          f"与已有标签矛盾 {stats['count_mismatches']} 次），进桌 {stats['enter_room']} 次")
    print(f"同桌出现过的账号 {len(seen)} 个：证实人机 {len(robots & seen)}，证实真人 {len(humans & seen)}，"
          f"未证实 {len(seen - robots - humans)}，互相矛盾 {registry.counts()['conflict']}")
    ids = sorted(int(u) for u in robots)
    if not ids:
        return
    print(f"\n证实人机的 UID：最小 {ids[0]}，最大 {ids[-1]}，跨度 {ids[-1] - ids[0] + 1} 个号，实际出现 {len(ids)} 个"
          f"（占 {100 * len(ids) / (ids[-1] - ids[0] + 1):.1f}%）")
    gaps = [b - a for a, b in zip(ids, ids[1:])]
    if gaps:
        gaps_sorted = sorted(gaps)
        print(f"相邻两个人机 UID 的间隔：中位 {gaps_sorted[len(gaps) // 2]}，90% 分位 {gaps_sorted[int(.9 * len(gaps))]}，"
              f"最大 {gaps_sorted[-1]}")
    # 只是观察，不参与任何判定：证实人机的 UID 聚成几段，段内没被证实的账号只能算疑似
    # （UID 看起来按注册顺序发放，段内可以夹着真人）。
    runs, run = [], [ids[0]]
    for value in ids[1:]:
        if value - run[-1] <= 2000:
            run.append(value)
        else:
            runs.append(run)
            run = [value]
    runs.append(run)
    for run in runs:
        lo, hi = run[0], run[-1]
        in_h = sorted(int(u) for u in humans if lo <= int(u) <= hi)
        unproven = [u for u in seen if u.isdigit() and lo <= int(u) <= hi and registry.label(u) is None]
        print(f"证实人机聚集的 UID 段（仅供参考）{lo}–{hi}：证实人机 {len(run)}，证实真人 {len(in_h)}"
              f"{' ' + str(in_h[:5]) if in_h else ''}，段内出现过但未证实（疑似） {len(unproven)}")
    hum = sorted(int(u) for u in humans)
    if hum:
        print(f"证实真人 {len(hum)} 个，UID 范围 {hum[0]}–{hum[-1]}")
    how = Counter((registry._labels[u]["label"], registry._labels[u].get("how", "")) for u in registry._labels)
    for (label, reason), n in how.most_common():
        print(f"   {label:5s} {n:4d}  首次依据：{reason}")


def main(argv=None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--log", type=Path, default=DEFAULT_LOG)
    ap.add_argument("--registry", type=Path, default=None, help="registry file to (re)build; default robots.json")
    ap.add_argument("--my-uid", default="", help="hero uid (read from SelfUserInfoRSP when omitted)")
    ap.add_argument("--write", action="store_true", help="write the registry file (default: report only)")
    args = ap.parse_args(argv)
    if args.write:
        target = args.registry or DEFAULT_PATH
        registry = RobotRegistry(target, autosave=False)
    else:
        registry = RobotRegistry(Path(tempfile.mkdtemp()) / "robots.json", autosave=False)
    out = replay(args.log, registry, args.my_uid)
    report(registry, out["seen"], out["stats"])
    if args.write:
        registry.save(force=True)
        print(f"\n已写入 {registry.path}：{registry.counts()}")


if __name__ == "__main__":
    main()
