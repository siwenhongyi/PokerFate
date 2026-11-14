"""Hero against humans only: where the money goes, and how noisy the result is.

    .venv/bin/python -m analysis.human_only pokerfate/logs/archive/2026-11-*.pokerfate.bak.log pokerfate/logs/pokerfate.log [--since ISO]

Only hands at tables without any house robot (robot registry: proven, or inside a robot UID
block) are used, so the "pool" in every table below is the human pool.

Sections
  1  baseline, per-hand spread, and how many hands a given improvement needs to be seen
  2  by table size
  3  by hero's preflop line (contribution to bb/100, after / before rake)
  4  showdown vs non-showdown winnings
  5  hero vs the human pool: frequencies
  6  river: what humans bet with, what hero's folds would have won, value-bet size curve
"""
from __future__ import annotations

import argparse
import math
from collections import Counter, defaultdict

from analysis import pflog
from analysis.breakdown import hero_preflop_line, table
from analysis.features import mean_se, wilson
from analysis.rake import collect
from analysis.robot_logs import is_robot


def human_table(h) -> bool:
    return not any(is_robot(p["id"]) for p in h["players"] if p["name"] != h["hero_name"])


def fmt(xs, scale=100.0):
    m, se, n = mean_se(xs)
    return f"{scale * m:+7.1f} ± {scale * 1.96 * se:5.1f} (n={n})" if n > 1 else f"n={n}"


def rows_for(hands):
    by_key = {h["key"] + "|" + str(h["ts"]): h for h in hands}
    raw, _bad = collect(hands)
    rows = []
    for r in raw:
        if not r["hero_dealt"]:
            continue
        h = by_key.get(r["key"] + "|" + str(r["ts"]))
        if h is None:
            continue
        rows.append(dict(r, h=h, pos=h["hero_pos"], line=hero_preflop_line(h),
                         saw=h["hero_name"] in (h.get("flop_players") or []),
                         n_flop=len(h.get("flop_players") or []),
                         sd=bool(h.get("hero_at_showdown"))))
    return rows


def baseline(rows, adj=None):
    print("== 1 基线与噪声（只算没有人机的牌桌）==")
    post = [r["hero_delta"] for r in rows]
    pre = [r["hero_delta"] + r["hero_paid"] for r in rows]
    m, se, n = mean_se(post)
    sd = se * math.sqrt(n)
    print(f"  手数 {n}：抽水后 {fmt(post)} bb/100，抽水前 {fmt(pre)}，被抽 {100 * sum(r['hero_paid'] for r in rows) / n:.1f} bb/100")
    print(f"  单手输赢的标准差 {sd:.1f}bb（每 100 手的 95% 区间半宽 = {196 * sd / 10:.0f} bb/100）")
    if adj is not None:
        xs = list(adj.adj.values())
        m2, se2, n2 = mean_se(xs)
        sd = se2 * math.sqrt(n2)
        luck = sum(c["raw"] - c["adj"] for c in adj.changed)
        print(f"  全下运气修正后 {100 * m2:+7.1f} ± {196 * se2:5.1f} bb/100（{len(adj.changed)} 个河牌前全下并摊牌的底池按胜率计；"
              f"这些底池的运气合计 {luck:+.0f}bb），单手标准差降到 {sd:.1f}bb")
        print("  下面“需要多少手”按修正后的标准差计算")
    for gain in (5, 10, 20):
        need = (1.96 * sd * 100 / gain) ** 2
        need2 = 2 * need           # before/after comparison of two independent samples
        print(f"  要看出 {gain:>2d} bb/100 的差别：单看一段需要约 {need:,.0f} 手；改动前后各一段对比，每段约 {need2:,.0f} 手")
    for n_h in (1000, 5000, 20000):
        print(f"  打 {n_h:>6,d} 手时的 95% 区间：± {196 * sd / math.sqrt(n_h):.0f} bb/100")


def by_size(rows):
    print("\n== 2 按桌上人数（含 hero）==")
    g = defaultdict(list)
    for r in rows:
        g[r["n"]].append(r)
    for k in sorted(g):
        rs = g[k]
        print(f"  {k} 人桌  抽水后 {fmt([r['hero_delta'] for r in rs])}   抽水前 {fmt([r['hero_delta'] + r['hero_paid'] for r in rs])}"
              f"   被抽 {100 * sum(r['hero_paid'] for r in rs) / len(rs):5.1f}   盲注成本 {150 / k:4.0f} bb/100")


def showdown_split(rows):
    print("\n== 4 摊牌 / 非摊牌 盈亏（bb/100，按全部手数摊）==")
    n = len(rows)
    for label, sel in (("到摊牌的手", lambda r: r["sd"]), ("看到翻牌但没到摊牌", lambda r: r["saw"] and not r["sd"]),
                       ("翻前就结束", lambda r: not r["saw"])):
        rs = [r for r in rows if sel(r)]
        net = sum(r["hero_delta"] for r in rs)
        paid = sum(r["hero_paid"] for r in rs)
        m, se, k = mean_se([r["hero_delta"] for r in rs])
        print(f"  {label:10s} {k:5d} 手（{100 * k / n:4.1f}%）  每手 {m:+6.2f} ± {1.96 * se:4.2f}bb   贡献 抽水后 {100 * net / n:+6.1f} / 抽水前 {100 * (net + paid) / n:+6.1f}")
    sd = [r for r in rows if r["sd"]]
    saw = [r for r in rows if r["saw"]]
    won = sum(1 for r in sd if r["hero_delta"] > 0)
    lo, hi = wilson(won, len(sd))
    print(f"  看翻牌率 {100 * len(saw) / n:.1f}%，看到翻牌后去摊牌 {100 * len(sd) / max(1, len(saw)):.1f}%，摊牌赢率 {100 * won / max(1, len(sd)):.1f}% [{100 * lo:.0f},{100 * hi:.0f}]")


def frequencies(hands):
    from analysis import overview
    print("\n== 5 hero 与真人对手池的频率对比 ==")
    usable = [h for h in hands if overview.usable(h)]
    overview.preflop(usable)
    overview.postflop(usable)


def river(hands):
    from analysis import truth, value_size
    print("\n== 6 真人对手池下注的真实牌力、hero 弃牌的真相、河牌价值下注尺度 ==")
    truth.report(hands)
    print()
    value_size.report(hands)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("logs", nargs="+")
    ap.add_argument("--since", default="")
    ap.add_argument("--brief", action="store_true", help="sections 1-4 only")
    args = ap.parse_args(argv)
    hands, _ = pflog.load(args.logs)
    pflog.validate(hands)
    hands = [h for h in hands if h.get("players") and (h["ts"] or "") >= args.since]
    humans = [h for h in hands if human_table(h)]
    print(f"全部 {len(hands)} 手，其中没有人机的牌桌 {len(humans)} 手\n")
    from analysis.allin_ev import Adjuster      # imported here: allin_ev uses human_table from this module

    rows = rows_for(humans)
    baseline(rows, Adjuster(humans))
    by_size(rows)
    table(rows, lambda r: r["line"], "3 按 hero 翻前路线")
    showdown_split(rows)
    if not args.brief:
        frequencies(humans)
        river(humans)


if __name__ == "__main__":
    main()
