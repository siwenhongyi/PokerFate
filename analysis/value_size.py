"""River value-bet size curve from ground truth (heads-up pots, first bet on the river).

For every river bet whose bettor's strength is known (shown at showdown, or the winner's hand
type when nobody called) it records the response and what the river street added for the
bettor relative to checking the hand down:
    villain folds            ->  0      (a value hand wins the same pot at showdown)
    called by a worse hand   -> +0.82·b (9% rake on the extra 2b)
    called by a better hand  -> -b
    raised                   -> settled on the chips both players put in on the river
Only meaningful for value hands; bluffs need the opposite fold convention and are not shown.

    .venv/bin/python -m analysis.value_size pokerfate/logs/archive/*.pokerfate.bak.log pokerfate/logs/pokerfate.log
"""
from __future__ import annotations

import argparse
from collections import Counter

from analysis import pflog
from analysis.features import mean_se, size_bucket
from analysis.truth import label_rank, strength_class, type_rank
from analysis.value_audit import river_hu_lines

KEEP = 0.91
SIZES = ("≤40%", "40-70%", "70-105%", ">105%")


def collect(hands):
    rows = []
    for h, ss, b in river_hu_lines(hands):
        btr = type_rank(b)
        bb = h["bb"]
        res = h["result"]
        bets = [s for s in ss if s["kind"] == "bet"]
        if not bets:
            continue
        s = bets[0]
        who = s["who"]
        later = [x for x in ss if x["i"] > s["i"]]
        if not later:
            continue
        resp = later[0]
        shown = h["hole"] if s["hero"] else res["showdown_hands"].get(who)
        cls = None
        if shown and len(shown) == 2:
            cls = strength_class(type_rank(shown + b), btr)
        elif resp["act"] == "fold" and who in res["winners"]:
            t = label_rank(res["hand_combos"].get(who, ""))
            if t is not None:
                cls = strength_class(t, btr)
        if cls is None:
            continue
        won = who in res["winners"]
        split = won and len(res["winners"]) > 1
        bet_bb = s["pot_bb"] * (s["size_pot"] or 0.0)
        if resp["act"] == "fold":
            gain = 0.0
        elif resp["act"] == "call":
            gain = 0.0 if split else ((2 * KEEP - 1) * bet_bb if won else -bet_bb)
        else:
            mine = sum(a["add"] for a in h["actions"] if a["street"] == "river" and a["who"] == who) / bb
            theirs = sum(a["add"] for a in h["actions"] if a["street"] == "river" and a["who"] != who) / bb
            matched = min(mine, theirs)
            if who in h["folded"]:
                gain = -mine
            elif split:
                gain = 0.0
            else:
                gain = (2 * KEEP - 1) * matched if won else -matched
        rows.append(dict(ts=h["ts"], hero=s["hero"], resp_hero=resp["hero"], cls=cls, frac=s["size_pot"] or 0.0,
                         size=size_bucket(s["size_pot"]), resp=resp["act"], won=won, gain=gain, pot=s["pot_bb"],
                         ip=s["n_acted"] >= 1))
    return rows


def curve(rows, label):
    print(f"   {label}")
    for sz in SIZES:
        rs = [r for r in rows if r["size"] == sz]
        if len(rs) < 8:
            continue
        n = len(rs)
        c = Counter(r["resp"] for r in rs)
        called = [r for r in rs if r["resp"] == "call"]
        m, se, _ = mean_se([r["gain"] / r["pot"] for r in rs])
        flag = " 低置信" if n < 30 else ""
        print(f"     {sz:<8} n={n:4d} 平均 {100 * sum(r['frac'] for r in rs) / n:3.0f}%pot | 弃 {100 * c['fold'] / n:3.0f}% 跟 {100 * c['call'] / n:3.0f}% 加注 {100 * c['raise'] / n:3.0f}%"
              f" | 被跟时赢 {sum(1 for r in called if r['won'])}/{len(called)} | 河牌街净增值 {m:+.3f} ± {1.96 * se:.3f} 底池{flag}")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("logs", nargs="+")
    ap.add_argument("--since", default="", help="only for the hero rows; the pool curve always uses every log")
    args = ap.parse_args(argv)
    hands, _ = pflog.load(args.logs)
    pflog.validate(hands)
    report(hands, args.since)


def report(hands, since=""):
    rows = collect([h for h in hands if h.get("result")])
    value = [r for r in rows if r["cls"] == "两对+"]
    print(f"河牌单挑首次下注且下注者牌力已知 {len(rows)} 次；其中两对以上 {len(value)} 次")
    print("\n== 两对以上的价值下注：对手池的回应与收益，按尺度 ==")
    curve([r for r in value if not r["resp_hero"]], "全部下注者（回应者是对手池）")
    curve([r for r in value if not r["resp_hero"] and not r["hero"]], "只看对手池之间")
    curve([r for r in value if not r["resp_hero"] and r["ip"]], "下注者有位置")
    curve([r for r in value if not r["resp_hero"] and not r["ip"]], "下注者无位置")
    curve([r for r in value if not r["resp_hero"] and r["pot"] >= 10], "底池 ≥ 10bb")
    thin = [r for r in rows if r["cls"] == "一对级" and not r["resp_hero"]]
    print("\n== 一对级的薄价值下注 ==")
    curve(thin, "全部下注者")
    mine = [r for r in value if r["hero"] and (r["ts"] or "") >= since]
    print(f"\n== hero 自己的两对以上河牌下注 n={len(mine)}（since={since or '-'}）==")
    for ip in (True, False):
        rs = [r for r in mine if r["ip"] == ip]
        if not rs:
            continue
        c = Counter(r["size"] for r in rs)
        m, se, n = mean_se([r["gain"] / r["pot"] for r in rs])
        rc = Counter(r["resp"] for r in rs)
        print(f"   {'有位置' if ip else '无位置'} n={n} 尺度 { {k: c[k] for k in SIZES} } 平均 {100 * sum(r['frac'] for r in rs) / n:.0f}%pot，平均底池 {sum(r['pot'] for r in rs) / n:.1f}bb；"
              f"对手 弃 {rc['fold']} 跟 {rc['call']} 加注 {rc['raise']}；净增值 {m:+.3f} ± {1.96 * se:.3f} 底池")
    small = [r for r in mine if r["size"] == "≤40%"]
    if small:
        print(f"   其中 ≤40% 底池的小尺度下注 {len(small)} 次，平均底池 {sum(r['pot'] for r in small) / len(small):.1f}bb")


if __name__ == "__main__":
    main()
