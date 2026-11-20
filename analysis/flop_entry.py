"""How good is the range the preflop layer hands over when the flop is dealt?

    .venv/bin/python -m analysis.flop_entry rows.jsonl [more rows ...]

Rows: the extractor in bucket mode (command in analysis/range_layers.py).  For every hand shown
at showdown it keeps the range at the moment the flop came — its mass per tenth of preflop
strength — and where the cards actually shown fall (``flop_entry``).  This prints, overall and
per preflop line, kind of opponent and position: what the range said, what was shown, and how
much more probability the range gave the shown hand than a range that knows nothing
(positive = better than uniform; before the preflop rewrite of 2026-11-15 it was -1.9).

Shown hands got to showdown, but that barely selects on preflop strength (a big blind who
checked his option shows close to random cards), so the comparison is fair.
"""
from __future__ import annotations

import math
import sys
from collections import defaultdict

import numpy as np

from analysis.range_layers import iter_rows


def clustered(values, clusters):
    values = np.asarray(values, dtype=float)
    mean = float(values.mean())
    _, index = np.unique(np.asarray(clusters), return_inverse=True)
    sums = np.bincount(index, weights=values - mean)
    g = len(sums)
    return mean, (float(math.sqrt(g / (g - 1) * float((sums ** 2).sum())) / len(values)) if g > 1 else 0.0)


def who(profile):
    hands = float(profile.get("hands_seen") or 0.0)
    if hands < 30:
        return "不认识"
    return "紧手" if float(profile.get("vpip") or 0.0) < 0.45 else "松手"


def main(paths, min_rows=150):
    groups = defaultdict(list)
    for row in iter_rows(paths):
        e = row.get("flop_entry")
        if not e:
            continue
        line = row.get("preflop_action_type") or "?"
        item = (np.array(e["decile_mass"]), e["actual_decile"], e["p_actual"], e["live_combos"], row.get("player_uid"),
                np.array(e["decile_live"], dtype=float))
        for key in ("全部", f"翻前动作 {line}", f"对手 {who(row.get('player_profile') or {})}",
                    f"位置 {row.get('position') or '?'}"):
            groups[key].append(item)
    print("翻牌发出时的范围，对照摊牌亮出的底牌（按翻前牌力分 10 档，0 = 最弱的一成，9 = 最强的一成）\n")
    for key in sorted(groups, key=lambda k: (k != "全部", k)):
        items = groups[key]
        if len(items) < min_rows:
            continue
        mass = np.array([i[0] for i in items]); actual = np.array([i[1] for i in items])
        p = np.array([i[2] for i in items]); live = np.array([i[3] for i in items]); uid = [i[4] for i in items]
        uni = np.array([i[5] for i in items]); uni = uni / uni.sum(axis=1, keepdims=True)
        gain, se = clustered(np.log(np.maximum(p, 1e-12)) - np.log(1.0 / live), uid)       # vs knowing nothing
        held = np.bincount(actual, minlength=10) / len(actual)
        print(f"== {key}  （{len(items)} 手，{len(set(uid))} 个玩家）  比“完全不知道”多出的信息：{gain:+.3f} ± {se:.3f} nats")
        print("   档        " + " ".join(f"{d:6d}" for d in range(10)) + "    最弱三档合计")
        print("   范围说    " + " ".join(f"{100 * v:6.1f}" for v in mass.mean(axis=0)) + f"    {100 * mass.mean(axis=0)[:3].sum():6.1f}")
        print("   实际亮出  " + " ".join(f"{100 * v:6.1f}" for v in held) + f"    {100 * held[:3].sum():6.1f}")
        print("   均匀发牌  " + " ".join(f"{100 * v:6.1f}" for v in uni.mean(axis=0)) + f"    {100 * uni.mean(axis=0)[:3].sum():6.1f}\n")


if __name__ == "__main__":
    main(sys.argv[1:])
