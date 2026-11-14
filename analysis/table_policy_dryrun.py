"""Dry run of robot identification + table rule on the recorded wire log.

    .venv/bin/python -m analysis.table_policy_dryrun [--log pf_intercept/logs/headless.log]

For every hand in the log it asks: with what could be known at that moment, what would the
table rule have said (stay / leave), and what is the truth according to the final registry?
Two runs: "cold" starts with an empty registry and learns only from the rb_num counts it has
seen so far; "warm" starts from the registry as it is on disk today.  Nothing is sent anywhere.
"""
from __future__ import annotations

import argparse
import tempfile
from collections import Counter
from pathlib import Path

from analysis.robot_wire import DEFAULT_LOG, _LINE
from pf_intercept.table_policy import verdict
from pokerfate.core.robots import RobotRegistry, RoomRobotTracker

import ast

_TYPES = ("pb.EnterRoomRSP", "pb.SitDownBRC", "pb.OtherLeaveRoomBRC", "pb.OtherEnterRoomBRC",
          "pb.LeaveRoomRSP", "pb.SelfUserInfoRSP", "pb.DealerInfoRSP")


def _events(path: Path):
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if "[S→C] pb." not in line or not any(t in line for t in _TYPES):
                continue
            m = _LINE.match(line)
            if not m or m.group(2) not in _TYPES:
                continue
            try:
                yield m.group(2), ast.literal_eval(m.group(3))
            except (ValueError, SyntaxError):
                continue


def _feed(tracker: RoomRobotTracker, kind: str, msg: dict) -> None:
    if kind == "pb.SelfUserInfoRSP":
        uid = (msg.get("brief") or {}).get("uid")
        if uid:
            tracker.set_my_uid(uid)
    elif kind == "pb.EnterRoomRSP":
        if int(msg.get("code", 0) or 0) == 0:
            seats = [s.get("player", {}).get("uid") for s in (msg.get("table_status") or {}).get("seat", [])]
            tracker.reset([s for s in seats if s])
    elif kind == "pb.SitDownBRC":
        uid = ((msg.get("status") or {}).get("player") or {}).get("uid")
        if uid:
            tracker.sat_down(uid)
    elif kind == "pb.OtherEnterRoomBRC":
        uid = (msg.get("user") or {}).get("uid")
        if uid:
            tracker.entered(uid, msg.get("num", 0), msg.get("rb_num", 0))
    elif kind == "pb.OtherLeaveRoomBRC":
        uid = msg.get("uid")
        if uid is not None:
            if str(uid) == tracker.my_uid:
                tracker.reset()
            else:
                tracker.left(uid, msg.get("num", 0), msg.get("rb_num", 0))
    elif kind == "pb.LeaveRoomRSP":
        if int(msg.get("code", 0) or 0) in (0, 2, 3):
            tracker.reset()


def run(log: Path, truth: RobotRegistry, start: RobotRegistry) -> Counter:
    tracker = RoomRobotTracker(start)
    out = Counter()
    for kind, msg in _events(log):
        if kind != "pb.DealerInfoRSP":
            _feed(tracker, kind, msg)
            continue
        members = set(tracker.members)
        if not members:
            continue
        comp = tracker.composition(members)
        said = verdict(comp["humans"], comp["robots"])
        true_robots = sum(1 for u in members if truth.is_robot(u))
        real = verdict(len(members) - true_robots, true_robots)
        out[(real, said)] += 1
        out[("source", comp["source"])] += 1
    return out


def show(title: str, c: Counter) -> None:
    print(f"\n{title}")
    labels = {"stay": "该留", "no_humans": "全是人机", "outnumbered": "真人少于人机", "empty": "空桌"}
    for real in ("no_humans", "outnumbered", "stay"):
        n = sum(v for (r, s), v in c.items() if r == real)
        if not n:
            continue
        right = c[(real, real)]
        parts = "，".join(f"判成{labels.get(s, s)} {v}" for (r, s), v in sorted(c.items())
                         if r == real and s != real and r != "source")
        print(f"   实际{labels[real]}的 {n} 手：当时判对 {right}（{100 * right / n:.1f}%）{'；' + parts if parts else ''}")
    src = {s: v for (r, s), v in c.items() if r == "source"}
    tot = sum(src.values()) or 1
    print(f"   判定依据：服务器计数 {100 * src.get('rb_num', 0) / tot:.0f}%，名单与号段 {100 * src.get('labels', 0) / tot:.0f}%")


def main(argv=None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--log", type=Path, default=DEFAULT_LOG)
    ap.add_argument("--registry", type=Path, default=None)
    args = ap.parse_args(argv)
    truth = RobotRegistry(args.registry, autosave=False)
    print(f"真相取自当前名单：{truth.counts()}，号段 {truth.blocks()}")
    cold = RobotRegistry(Path(tempfile.mkdtemp()) / "cold.json", autosave=False)
    show("冷启动（名单从空开始，只用回放到当时为止的服务器计数）", run(args.log, truth, cold))
    warm = RobotRegistry(Path(tempfile.mkdtemp()) / "warm.json", autosave=False)
    warm._labels = {k: dict(v) for k, v in truth._labels.items()}
    show("名单已建好（今天磁盘上的名单）", run(args.log, truth, warm))


if __name__ == "__main__":
    main()
