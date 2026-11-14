"""Audit of hero's own bets and checks: fold equity actually obtained, value extracted,
and the pool's elasticity to bet size.

    .venv/bin/python -m analysis.bet_audit <log> [<log> ...] [--since ISO]
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict

from analysis import pflog
from analysis.features import fmt_rate, mean_se, postflop_spots, size_bucket, usable, pot_type
from analysis.truth import board_cards, strength_class, type_rank

KEEP = 0.91


def collect(hands):
    """One row per postflop street on which a player was first to put money in (a bet)."""
    rows = []
    for h in hands:
        if not usable(h):
            continue
        bb = h["bb"]
        hero = h["hero_name"]
        spots = postflop_spots(h)
        inv_before = {}
        run = 0.0
        # hero chips invested before each action index
        hero_inv = 0.0
        inv_at = {}
        for a in h["actions"]:
            inv_at[a["i"]] = hero_inv
            if a["hero"]:
                hero_inv += a["add"]
        by_street = defaultdict(list)
        for s in spots:
            by_street[s["street"]].append(s)
        for st, ss in by_street.items():
            b = board_cards(h, st)
            btr = type_rank(b)
            for k, s in enumerate(ss):
                if s["kind"] != "bet":
                    continue
                later = ss[k + 1:]
                resp = [x for x in later if x["who"] != s["who"]]
                first_resp = None
                n_fold = sum(1 for x in resp if x["act"] == "fold")
                n_call = sum(1 for x in resp if x["act"] == "call")
                n_raise = sum(1 for x in resp if x["act"] == "raise")
                opp_n = s["n_active"] - 1
                outcome = "raise" if n_raise else ("call" if n_call else ("fold" if n_fold >= opp_n else "?"))
                row = dict(key=h["key"], ts=h["ts"], street=st, hero=s["hero"], who=s["who"], hu=s["n_active"] == 2,
                           frac=s.get("size_pot"), size=size_bucket(s.get("size_pot")), outcome=outcome,
                           pot=s["pot_bb"], is_pfr=s["is_pfr"], prev_aggr=s["prev_aggr"], ptype=s["ptype"],
                           n_active=s["n_active"], allin=s["allin"])
                if s["hero"]:
                    d = s["dec"]
                    ht = type_rank(h["hole"] + b)
                    row.update(hero_cls=strength_class(ht, btr), bucket=d.get("hero_bucket"), eq=d.get("equity"),
                               purpose=d.get("final_purpose"), src=d.get("decision_source"),
                               V=h["delta_bb"] + inv_at[s["i"]] / bb, hand=h["hole"], board=b,
                               won=hero in h["result"]["winners"], sd=h["hero_at_showdown"])
                rows.append(row)
    return rows


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("logs", nargs="+")
    ap.add_argument("--since", default="")
    args = ap.parse_args(argv)
    hands, _ = pflog.load(args.logs)
    pflog.validate(hands)
    if args.since:
        hands = [h for h in hands if (h["ts"] or "") >= args.since]
    rows = collect(hands)
    hero = [r for r in rows if r["hero"]]
    pool = [r for r in rows if not r["hero"]]
    print(f"hands={sum(1 for h in hands if usable(h))} hero bets={len(hero)} pool bets={len(pool)}")

    print("\n== 对手面对【hero 下注】的反应，按街/尺度（单挑）==")
    for st in ("flop", "turn", "river"):
        for sz in ("≤40%", "40-70%", "70-105%", ">105%"):
            rs = [r for r in hero if r["street"] == st and r["hu"] and r["size"] == sz and r["outcome"] != "?"]
            if not rs:
                continue
            c = Counter(r["outcome"] for r in rs)
            n = len(rs)
            print(f"  {st:<5} {sz:<8} 弃牌 {fmt_rate(c['fold'], n)}  跟注 {100 * c['call'] / n:4.1f}%  加注 {100 * c['raise'] / n:4.1f}%")
    print("\n== 对手面对【其他对手下注】的反应（单挑；对手池内部，样本大）==")
    for st in ("flop", "turn", "river"):
        for sz in ("≤40%", "40-70%", "70-105%", ">105%"):
            rs = [r for r in pool if r["street"] == st and r["hu"] and r["size"] == sz and r["outcome"] != "?"]
            if not rs:
                continue
            c = Counter(r["outcome"] for r in rs)
            n = len(rs)
            print(f"  {st:<5} {sz:<8} 弃牌 {fmt_rate(c['fold'], n)}  跟注 {100 * c['call'] / n:4.1f}%  加注 {100 * c['raise'] / n:4.1f}%")

    print("\n== hero 下注：按街 × 牌力（牌型相对公共牌）× 尺度 ==")
    for st in ("flop", "turn", "river"):
        for hu in (True, False):
            for cls in ("air(不超过公共牌)", "一对级", "两对+"):
                rs = [r for r in hero if r["street"] == st and r["hu"] == hu and r["hero_cls"] == cls]
                if not rs:
                    continue
                c = Counter(r["outcome"] for r in rs)
                n = len(rs)
                szc = Counter(r["size"] for r in rs)
                V, se, _ = mean_se([r["V"] for r in rs])
                avg_frac = sum((r["frac"] or 0) for r in rs) / n
                print(f"  {st:<5} {'单挑' if hu else '多人'} {cls:<12} n={n:3d} 平均尺度={100 * avg_frac:3.0f}%pot 弃={100 * c['fold'] / n:3.0f}% 跟={100 * c['call'] / n:3.0f}% 被加注={100 * c['raise'] / n:3.0f}%"
                      f"  自此点净值V={V:+5.1f}±{1.96 * se if se == se else 0:4.1f}bb  尺度分布={dict(szc)}")

    print("\n== hero 下注尺度 × bot 自评桶（local 引擎才有桶）==")
    for st in ("flop", "turn", "river"):
        acc = defaultdict(list)
        for r in hero:
            if r["street"] == st and r.get("bucket"):
                acc[r["bucket"]].append(r["frac"] or 0)
        for b in ("nuts", "strong", "medium", "draw", "weak_draw", "air"):
            v = sorted(acc.get(b, []))
            if v:
                q = lambda p: v[int(p * (len(v) - 1))]
                print(f"  {st:<5} {b:<9} n={len(v):3d} 尺度 %pot: 25%={100 * q(.25):3.0f} 中位={100 * q(.5):3.0f} 75%={100 * q(.75):3.0f}")


if __name__ == "__main__":
    main()
