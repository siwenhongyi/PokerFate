"""How much did house robots distort what the bot has learned?  Rebuild without them and compare.

    .venv/bin/python -m analysis.robot_relearn calibrator            # online hero-equity calibrator
    .venv/bin/python -m analysis.robot_relearn calibrator --out /path/human_only.json
    .venv/bin/python -m analysis.robot_relearn empirical A.json B.json   # two empirical-model builds
    .venv/bin/python -m analysis.robot_relearn score rowsA.jsonl rowsB.jsonl   # which predicts humans better
    .venv/bin/python -m analysis.robot_relearn rows [--apply]         # training rows written before the table rule

``calibrator`` looks at the online hero-equity calibrator the bot loads from opponents.json.
Its window holds (predicted, actual) pairs only, but each pair was also written as a training
row (local/training/*.rows.jsonl) with the opponent's uid, so every sample can be
traced back to a robot or a human.  It reports the share of robot samples and how the applied
corrections change without them.  ``--out`` writes the robot-free state to a file;
``--apply`` swaps it into opponents.json (keeping a backup).  Without those nothing is modified.

What counts as polluted follows the table rule the strategy applies since 2026-11-14
(``PokerFateAPI._hand_skip_learning``), judged per hand from the strategy log's dealt-in list:
a row about a robot; any row from a hand at a table the bot would leave (no human, or fewer
humans than robots); and, for the hero-equity calibrator only, any sample from a hand with a
robot dealt in (the robot may still have been in the pot).  ``rows`` removes the first two
kinds from local/training/*.rows.jsonl (``--apply`` rewrites the files and keeps the
originals as ``*.before-robot-clean-<time>``).  Run ``calibrator --apply`` before
``rows --apply``: it traces samples through those rows.  Both only while the bot is stopped.
"""
from __future__ import annotations

import argparse
import json
import math
import shutil
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from analysis import pflog
from pokerfate.core.robots import RobotRegistry, table_verdict
from pokerfate.strategy.range_v2.hero_eq_calibrator import (
    HeroEquityCalibrator, _BIAS_SHRINK_K, _MAX_SHIFT, _MIN_SAMPLES, _make_key,
    classify_action_ctx_from_trigger,
)

ROOT = Path(__file__).resolve().parents[1]
ROWS = [ROOT / "local" / "training" / "train.rows.jsonl",
        ROOT / "local" / "training" / "val.rows.jsonl"]
OPPONENTS = ROOT / "local" / "models" / "opponents.json"
LOGS = sorted((ROOT / "pokerfate" / "logs" / "archive").glob("*.pokerfate.bak.log")) + [
    ROOT / "pokerfate" / "logs" / "pokerfate.log"]
_NEEDED = ("player_uid", "recorded_at", "hero_bucket", "street", "active_player_count",
           "predicted_hero_eq_multi", "actual_hero_eq_street_multi", "trigger", "hand")
_SPOOL_LAG_SEC = 6 * 3600        # a row is written after its hand, at most this much later


class HandTables:
    """Who was dealt into each logged hand, to judge a training row's hand by the table rule."""

    def __init__(self, registry, logs=None) -> None:
        self.by_number = defaultdict(list)             # hand number -> [(start, uids, humans, robots)]
        hands, _ = pflog.load([p for p in (logs or LOGS) if Path(p).exists()])
        for h in hands:
            try:
                start = datetime.fromisoformat(str(h["ts"])).timestamp()
            except (TypeError, ValueError):
                continue
            others = {str(p["id"]) for p in h["players"] if p["name"] != h["hero_name"]}
            robots = sum(1 for uid in others if registry.is_robot(uid))
            self.by_number[int(h["hand"])].append((start, others, len(others) - robots, robots))
        for found in self.by_number.values():
            found.sort(key=lambda x: x[0])
        self.first = min((f[0][0] for f in self.by_number.values()), default=float("inf"))

    def kind(self, row) -> str:
        """clean / mixed (robots dealt in, the bot stays) / leave / unknown (not in the logs)."""
        at, uid = float(row.get("recorded_at") or 0), str(row.get("player_uid") or "")
        hit = None
        for start, uids, humans, robots in self.by_number.get(int(row.get("hand") or 0), ()):
            if start <= at + 5 and at - start < _SPOOL_LAG_SEC and uid in uids:
                hit = (humans, robots)                 # hand numbers repeat between runs: latest wins
        if hit is None:
            return "unknown"
        if not hit[1]:
            return "clean"
        return "mixed" if table_verdict(*hit) == "stay" else "leave"


def _iter_rows(paths):
    for path in paths:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                if '"predicted_hero_eq_multi"' not in line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                yield {k: row.get(k) for k in _NEEDED}


def _applied_bias(samples) -> float:
    """The shift ``HeroEquityCalibrator.calibrate`` adds for a key holding these samples."""
    if len(samples) < _MIN_SAMPLES:
        return 0.0
    bias = sum(a - p for p, a in samples) / len(samples)
    bias = max(-_MAX_SHIFT, min(_MAX_SHIFT, bias))
    return bias * len(samples) / (len(samples) + _BIAS_SHRINK_K)


def calibrator(args) -> None:
    """Which samples in the deployed calibrator came from robots, and what do they change?"""
    registry = RobotRegistry(args.registry, autosave=False)
    rows = [r for r in _iter_rows(args.rows)
            if r["predicted_hero_eq_multi"] is not None and r["actual_hero_eq_street_multi"] is not None
            and r["hero_bucket"] and r["street"]]
    rows.sort(key=lambda r: r["recorded_at"] or 0)
    stream = defaultdict(list)                 # key -> [(predicted, actual, polluted, ts)] in time order
    is_robot = {}
    tables = HandTables(registry)
    why = defaultdict(int)
    for r in rows:
        uid = str(r["player_uid"] or "")
        if uid not in is_robot:
            is_robot[uid] = bool(uid) and registry.is_robot(uid)
        predicted, actual = float(r["predicted_hero_eq_multi"]), float(r["actual_hero_eq_street_multi"])
        if not (0.0 <= predicted <= 1.0) or not (0.0 <= actual <= 1.0):
            continue
        key = _make_key(r["hero_bucket"], r["street"], int(r["active_player_count"] or 0),
                        classify_action_ctx_from_trigger(r["trigger"]))
        # Hero's "actual equity" in a hand with a robot is decided by the robot's cards.
        kind = "robot" if is_robot[uid] else tables.kind(r)
        why[kind] += 1
        stream[key].append((predicted, actual, kind in ("robot", "leave", "mixed"), r["recorded_at"] or 0))
    print("可追溯的样本行：" + "，".join(f"{k} {v}" for k, v in sorted(why.items()))
          + "（robot=对手是人机，leave=需要离桌的牌局，mixed=留桌但发给了人机，unknown=日志里找不到这手）")

    raw = json.loads(Path(args.opponents).read_text(encoding="utf-8"))
    deployed = HeroEquityCalibrator.from_dict((raw.get("showdown") or {}).get("hero_eq_calibrator") or {})._samples
    cleaned, table = {}, []
    total = matched = robots = 0
    oldest = None
    for key, samples in deployed.items():
        # The calibrator stores (predicted, actual) only; every sample was also written as a
        # training row with the opponent's uid, so walk both backwards to recover who it was.
        recorded = stream.get(key, [])
        j = len(recorded) - 1
        flags = [None] * len(samples)
        for i in range(len(samples) - 1, -1, -1):
            predicted, actual = samples[i]
            jj = j
            while jj >= 0 and not (abs(recorded[jj][0] - predicted) < 1e-9 and abs(recorded[jj][1] - actual) < 1e-9):
                jj -= 1
            if jj >= 0:
                flags[i] = recorded[jj][2]
                oldest = recorded[jj][3] if oldest is None else min(oldest, recorded[jj][3])
                j = jj - 1
        human = [smp for smp, f in zip(samples, flags) if f is not True]
        cleaned[key] = human
        total += len(samples)
        matched += sum(f is not None for f in flags)
        robots += sum(f is True for f in flags)
        table.append((key, len(samples), sum(f is True for f in flags), _applied_bias(samples), _applied_bias(human)))

    print(f"部署中的 hero 胜率自校准器：{len(deployed)} 个键、{total} 个样本；能对上训练行的 {matched} 个"
          f"（{100 * matched / max(1, total):.1f}%），其中要去掉的 {robots} 个（{100 * robots / max(1, total):.1f}%）")
    if oldest:
        print(f"窗口内最早的样本记录于 {time.strftime('%Y-%m-%d %H:%M', time.gmtime(oldest))} UTC")
    active = [t for t in table if t[1] >= _MIN_SAMPLES]
    diffs = [abs(t[4] - t[3]) for t in active]
    if not active:
        return
    print(f"生效的键 {len(active)} 个：去掉这些样本后，修正量平均改变 {100 * sum(diffs) / len(diffs):.2f} 个百分点；"
          f"改变 ≥2 个百分点的 {sum(d >= .02 for d in diffs)} 个，≥5 的 {sum(d >= .05 for d in diffs)} 个，"
          f"最大 {100 * max(diffs):.1f}")
    by_opp = defaultdict(list)
    for t in active:
        by_opp[t[0].split("|")[2]].append((abs(t[4] - t[3]), t[2] / t[1]))
    for opp in sorted(by_opp):
        v = by_opp[opp]
        print(f"   对手数 {opp:>2s}：{len(v):3d} 个键，窗口内要去掉的样本平均占 {100 * sum(x[1] for x in v) / len(v):.0f}%，"
              f"修正量平均改变 {100 * sum(x[0] for x in v) / len(v):.2f}，最大 {100 * max(x[0] for x in v):.1f}")
    print("\n改变最大的键（修正量 = 加到 hero 胜率上的偏移，百分点）")
    print(f"   {'hero桶|街|对手数|情境':28s} 样本  去掉   现在 → 清理后")
    for t in sorted(active, key=lambda t: -abs(t[4] - t[3]))[:14]:
        print(f"   {t[0]:30s} {t[1]:4d}  {t[2]:6d}   {100 * t[3]:+6.1f} → {100 * t[4]:+6.1f}")

    state = {k: [[p_, a_] for p_, a_ in v] for k, v in cleaned.items() if v}
    if args.out:
        Path(args.out).write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
        print(f"\n清理后的校准器状态已写入 {args.out}（未改动 opponents.json）")
    if args.apply:
        backup = Path(str(args.opponents) + f".before-robot-clean-{int(time.time())}")
        shutil.copy2(args.opponents, backup)
        raw.setdefault("showdown", {})["hero_eq_calibrator"] = state
        tmp = Path(str(args.opponents) + ".tmp")
        tmp.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
        tmp.replace(args.opponents)
        print(f"\n已替换 {args.opponents} 里的校准器状态；原文件备份为 {backup}")


def clean_rows(args) -> None:
    """Drop rows about robots and rows from hands at tables the bot would leave."""
    registry = RobotRegistry(args.registry, autosave=False)
    tables = HandTables(registry)
    is_robot = {}
    stamp = int(time.time())
    for path in args.rows:
        counts = defaultdict(int)
        tmp = Path(str(path) + ".tmp")
        out = tmp.open("w", encoding="utf-8") if args.apply else None
        try:
            with open(path, encoding="utf-8") as fh:
                for line in fh:
                    try:
                        row = json.loads(line)
                    except json.JSONDecodeError:
                        counts["unreadable (kept)"] += 1
                        row = None
                    kind = "kept"
                    if row is not None:
                        uid = str(row.get("player_uid") or "")
                        if uid not in is_robot:
                            is_robot[uid] = bool(uid) and registry.is_robot(uid)
                        if is_robot[uid]:
                            kind = "robot"
                        elif float(row.get("recorded_at") or 0) >= tables.first and tables.kind(row) == "leave":
                            kind = "leave"
                    counts[kind] += 1
                    if out is not None and kind == "kept":
                        out.write(line)
        finally:
            if out is not None:
                out.close()
        total = sum(counts.values())
        print(f"{path.name}: {total:,} 行；保留 {counts['kept']:,}，对手是人机 {counts['robot']:,}，"
              f"需要离桌的牌局 {counts['leave']:,}" + (f"，无法解析 {counts['unreadable (kept)']:,}" if counts["unreadable (kept)"] else ""))
        if args.apply:
            backup = Path(str(path) + f".before-robot-clean-{stamp}")
            Path(path).rename(backup)
            tmp.rename(path)
            print(f"   已重写；原文件保留为 {backup.name}")
    if not args.apply:
        print("（试运行，未改动文件；加 --apply 才重写）")


def _flat(d, pre=""):
    out = {}
    for k, v in d.items():
        if isinstance(v, dict):
            out.update(_flat(v, pre + str(k) + "|"))
        elif isinstance(v, (int, float)):
            out[pre + str(k)] = float(v)
    return out


def empirical(args) -> None:
    a = json.loads(Path(args.a).read_text(encoding="utf-8"))
    b = json.loads(Path(args.b).read_text(encoding="utf-8"))
    print(f"A = {args.a}\nB = {args.b}")
    print(f"训练行 {a['sources']['structured_rows']} → {b['sources']['structured_rows']}；"
          f"对手账号 {a['sources']['opponents_players']} → {b['sources']['opponents_players']}")
    print("\n对手池比率  A → B（差，百分点）")
    for k in sorted(a["population_rates"]):
        x, y = a["population_rates"][k]["mean"], b["population_rates"].get(k, {}).get("mean", float("nan"))
        print(f"   {k:22s} {x:.3f} → {y:.3f}  ({100 * (y - x):+.2f})")
    for name, leaf in (("action_likelihoods", "cat_probs"), ("preflop_bucket_priors", "dist")):
        fa = {k: v for k, v in _flat(a[name]).items() if f"|{leaf}|" in k}
        fb = {k: v for k, v in _flat(b[name]).items() if f"|{leaf}|" in k}
        common = sorted(set(fa) & set(fb))
        d = sorted(((abs(fa[k] - fb[k]), k) for k in common), reverse=True)
        print(f"\n{name}：可比概率 {len(d)} 个，平均绝对差 {100 * sum(x for x, _ in d) / max(1, len(d)):.2f} 个百分点，"
              f"差 ≥2 个百分点的 {sum(x >= .02 for x, _ in d)} 个；只在 A 中的条目 {len(set(a[name]) - set(b[name]))}")
        for x, k in d[:5]:
            print(f"   {100 * x:5.2f}pp  {k}  {fa[k]:.3f} → {fb[k]:.3f}")


CAT_ORDER = ("nuts", "strong", "medium", "draw", "weak_draw", "air")


def _bucket_rows(path, registry):
    """key -> (probability vector, actual index) for postflop rows about humans."""
    out = {}
    dec = json.JSONDecoder()
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            i = 0
            while i < len(line):                      # part files may hold several records per line
                if line[i] != "{":
                    i += 1
                    continue
                try:
                    row, i = dec.raw_decode(line, i)
                except json.JSONDecodeError:
                    break
                if row.get("street") not in ("flop", "turn", "river") or row.get("actual_bucket") not in CAT_ORDER:
                    continue
                dist = row.get("bucket_dist") or {}
                if not dist or registry.is_robot(str(row.get("player_uid") or "0")):
                    continue
                vec = [max(0.0, float(dist.get(c, 0.0) or 0.0)) for c in CAT_ORDER]
                total = sum(vec) or 1.0
                key = (row.get("session_id"), row.get("hand"), str(row.get("player_uid")), row.get("street"),
                       row.get("trigger"), tuple(row.get("board") or []), row.get("action_sequence"))
                out[key] = ([v / total for v in vec], CAT_ORDER.index(row["actual_bucket"]))
    return out


def _row_scores(vec, actual):
    nll = -math.log(max(vec[actual], 1e-6))
    brier = sum((v - (1.0 if j == actual else 0.0)) ** 2 for j, v in enumerate(vec))
    strong = vec[0] + vec[1]
    return nll, brier, strong, 1.0 if actual in (0, 1) else 0.0


def score(args) -> None:
    """Paired comparison of two row extractions on the same human showdown rows."""
    registry = RobotRegistry(args.registry, autosave=False)
    a, b = _bucket_rows(args.a, registry), _bucket_rows(args.b, registry)
    keys = sorted(set(a) & set(b), key=str)
    if args.last_session:
        last = max(k[0] for k in keys if k[0] is not None) if any(k[0] for k in keys) else None
        keys = [k for k in keys if k[0] == last] if last else keys
    if not keys:
        print("没有可配对的行")
        return
    da, db, dn, dbr = [], [], [], []
    for k in keys:
        sa, sb = _row_scores(*a[k]), _row_scores(*b[k])
        da.append(sa)
        db.append(sb)
        dn.append(sb[0] - sa[0])
        dbr.append(sb[1] - sa[1])
    n = len(keys)
    mean = lambda xs: sum(xs) / len(xs)
    se = lambda xs: (sum((x - mean(xs)) ** 2 for x in xs) / (len(xs) - 1) / len(xs)) ** 0.5
    print(f"A = {args.a}\nB = {args.b}\n配对的真人翻后行 {n} 条" + ("（仅最后一个会话）" if args.last_session else ""))
    for name, d in (("A", da), ("B", db)):
        bias = 100 * (mean([x[2] for x in d]) - mean([x[3] for x in d]))
        print(f"   {name}: NLL {mean([x[0] for x in d]):.4f}  Brier {mean([x[1] for x in d]):.4f}  强牌总量偏差 {bias:+.2f} 个百分点")
    print(f"   B − A: NLL {mean(dn):+.4f} ± {1.96 * se(dn):.4f}，Brier {mean(dbr):+.4f} ± {1.96 * se(dbr):.4f}"
          f"（负数表示 B 更准；差值 / 标准误 = {mean(dbr) / se(dbr):+.1f}）")


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("calibrator")
    c.add_argument("--rows", type=Path, action="append", default=None)
    c.add_argument("--opponents", type=Path, default=OPPONENTS)
    c.add_argument("--registry", type=Path, default=None)
    c.add_argument("--out", type=Path, default=None, help="write the robot-free calibrator state here")
    c.add_argument("--apply", action="store_true",
                   help="replace the calibrator state inside opponents.json (a backup copy is kept); "
                        "only while the bot is stopped")
    c.set_defaults(fn=calibrator)
    e = sub.add_parser("empirical")
    e.add_argument("a", type=Path)
    e.add_argument("b", type=Path)
    e.set_defaults(fn=empirical)
    sc = sub.add_parser("score", help="paired NLL / Brier of two row extractions on human rows")
    sc.add_argument("a", type=Path)
    sc.add_argument("b", type=Path)
    sc.add_argument("--registry", type=Path, default=None)
    sc.add_argument("--last-session", action="store_true", help="only the most recent session (hold-out)")
    sc.set_defaults(fn=score)
    cr = sub.add_parser("rows", help="drop rows about robots / from tables the bot would leave")
    cr.add_argument("--rows", type=Path, action="append", default=None)
    cr.add_argument("--registry", type=Path, default=None)
    cr.add_argument("--apply", action="store_true",
                    help="rewrite the row files (originals kept as *.before-robot-clean-<time>); "
                         "only while the bot is stopped")
    cr.set_defaults(fn=clean_rows)
    args = ap.parse_args(argv)
    if getattr(args, "rows", "x") is None:
        args.rows = ROWS
    args.fn(args)


if __name__ == "__main__":
    main()
