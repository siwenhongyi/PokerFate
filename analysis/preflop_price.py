"""BB closing the action against a cheap open: is the fold priced correctly?

For every hero BB fold facing a single open (hero closes the action), compute with Monte Carlo
(eval7) hero's showdown equity share against assumed pool ranges and compare with the raked
break-even equity  need = call / ((pot + call) · 0.91).

Range assumptions (stated, adjustable): opener = top OPEN_PCT of hands by all-in equity vs a
random hand; each cold caller = hands ranked between CALL_LO and CALL_HI.  A realisation
factor R (<1, out of position, no initiative) scales raw equity.

    .venv/bin/python -m analysis.preflop_price <log> [<log> ...] [--open-pct 0.2] [--R 0.7]
"""
from __future__ import annotations

import argparse
import itertools
import random
from collections import Counter, defaultdict

import eval7

from analysis import pflog
from analysis.features import preflop_spots, usable

RANKS = "23456789TJQKA"
DECK = [eval7.Card(r + s) for r in RANKS for s in "cdhs"]


def cls_of(c1: str, c2: str) -> str:
    r1, r2 = c1[0], c2[0]
    if RANKS.index(r1) < RANKS.index(r2):
        r1, r2 = r2, r1
    if r1 == r2:
        return r1 + r2
    return r1 + r2 + ("s" if c1[1] == c2[1] else "o")


def combos_of(cls: str) -> list:
    r1, r2 = cls[0], cls[1]
    out = []
    if len(cls) == 2:
        for s1, s2 in itertools.combinations("cdhs", 2):
            out.append((r1 + s1, r2 + s2))
    elif cls[2] == "s":
        for s in "cdhs":
            out.append((r1 + s, r2 + s))
    else:
        for s1 in "cdhs":
            for s2 in "cdhs":
                if s1 != s2:
                    out.append((r1 + s1, r2 + s2))
    return out


ALL_CLASSES = [a + a for a in RANKS] + [RANKS[i] + RANKS[j] + t for i in range(12, -1, -1) for j in range(i - 1, -1, -1) for t in "so"]


def rank_classes(iters: int = 1500, seed: int = 7) -> list:
    """169 classes ordered by all-in equity vs a random hand (Monte Carlo)."""
    rng = random.Random(seed)
    out = []
    for cls in ALL_CLASSES:
        c1, c2 = combos_of(cls)[0]
        h = [eval7.Card(c1), eval7.Card(c2)]
        rest = [c for c in DECK if c not in h]
        win = 0.0
        for _ in range(iters):
            s = rng.sample(rest, 7)
            a = eval7.evaluate(h + s[2:])
            b = eval7.evaluate(s[:2] + s[2:])
            win += 1.0 if a > b else (0.5 if a == b else 0.0)
        out.append((win / iters, cls))
    out.sort(reverse=True)
    return [c for _e, c in out]


def pct_range(order: list, lo: float, hi: float) -> list:
    """Combos of the classes whose cumulative combo share lies in (lo, hi]."""
    total = 1326
    acc = 0
    out = []
    for cls in order:
        cs = combos_of(cls)
        mid = (acc + len(cs) / 2) / total
        if lo <= mid < hi:
            out.extend(cs)
        acc += len(cs)
    return out


def equity_share(hero: list, ranges: list, iters: int, rng: random.Random) -> float:
    hc = [eval7.Card(c) for c in hero]
    dead0 = set(hero)
    tot = 0.0
    n = 0
    for _ in range(iters):
        dead = set(dead0)
        opp = []
        ok = True
        for rg in ranges:
            for _try in range(20):
                a, b = rg[rng.randrange(len(rg))]
                if a not in dead and b not in dead:
                    dead.add(a)
                    dead.add(b)
                    opp.append([eval7.Card(a), eval7.Card(b)])
                    break
            else:
                ok = False
                break
        if not ok:
            continue
        rest = [c for c in DECK if str(c) not in dead]
        board = rng.sample(rest, 5)
        hs = eval7.evaluate(hc + board)
        os_ = [eval7.evaluate(o + board) for o in opp]
        best = max(os_)
        if hs > best:
            tot += 1.0
        elif hs == best:
            tot += 1.0 / (1 + sum(1 for x in os_ if x == best))
        n += 1
    return tot / max(1, n)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("logs", nargs="+")
    ap.add_argument("--open-pct", type=float, default=0.20)
    ap.add_argument("--call-lo", type=float, default=0.08)
    ap.add_argument("--call-hi", type=float, default=0.55)
    ap.add_argument("--R", type=float, default=0.70)
    ap.add_argument("--iters", type=int, default=4000)
    ap.add_argument("--max-open-bb", type=float, default=2.5)
    args = ap.parse_args(argv)
    hands, _ = pflog.load(args.logs)
    pflog.validate(hands)
    hands = [h for h in hands if usable(h)]
    order = rank_classes()
    opener = pct_range(order, 0.0, args.open_pct)
    caller = pct_range(order, args.call_lo, args.call_hi)
    rng = random.Random(11)
    rows = []
    for h in hands:
        for s in preflop_spots(h):
            if not (s["hero"] and s["pos"] == "BB" and s["sit"] == "vs_open" and s["first_action"]):
                continue
            if s["open_to_bb"] > args.max_open_bb:
                continue
            pot, tc = s["pot_bb"], s["to_call_bb"]
            if tc <= 0:
                continue
            need = tc / ((pot + tc) * 0.91)
            rgs = [opener] + [caller] * s["callers"]
            eq = equity_share(h["hole"], rgs, args.iters, rng)
            rows.append(dict(key=h["key"], hand=cls_of(*h["hole"]), act=s["act"], callers=s["callers"], pot=pot, tc=tc,
                             need=need, eq=eq, reason=(s["dec"] or {}).get("preflop_expand_reason", "")))
    print(f"hero BB 面对 ≤{args.max_open_bb}bb 开池且自己收尾: n={len(rows)}  (opener=top {args.open_pct:.0%}, caller={args.call_lo:.0%}-{args.call_hi:.0%}, R={args.R})")
    for mw in (False, True):
        rs = [r for r in rows if (r["callers"] > 0) == mw]
        if not rs:
            continue
        folds = [r for r in rs if r["act"] == "fold"]
        prof = [r for r in folds if r["eq"] * args.R >= r["need"]]
        ev = sum(r["eq"] * args.R * 0.91 * (r["pot"] + r["tc"]) - r["tc"] for r in prof)
        print(f"  {'有冷跟注者(多人)' if mw else '单挑'}: n={len(rs)} 弃牌={len(folds)}  其中 eq×R ≥ need 的弃牌={len(prof)}  这些弃牌若跟注的模型EV合计={ev:+.2f}bb (平均 {ev / len(prof) if prof else 0:+.2f}bb)")
        print(f"     平均 need={sum(r['need'] for r in rs) / len(rs):.3f}  平均底池={sum(r['pot'] for r in rs) / len(rs):.1f}bb")
        for r in sorted(prof, key=lambda r: -(r["eq"] * args.R - r["need"]))[:12]:
            print(f"       {r['key']:<28} {r['hand']:<4} 冷跟={r['callers']} pot={r['pot']:.1f} call={r['tc']:.1f} need={r['need']:.3f} raw_eq={r['eq']:.3f} eq×R={r['eq'] * args.R:.3f}  {r['reason'][:70]}")


if __name__ == "__main__":
    main()
