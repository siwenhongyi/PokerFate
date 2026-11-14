"""All-in luck adjustment: replace the result of an all-in showdown by its expectation.

When the money goes in before the river and both hands are shown, what hero won or lost was
decided by cards nobody could influence.  For those pots (heads-up at showdown, every card
known) the result is replaced by

    P(win) · W  +  P(tie) · T  +  P(lose) · L

with the probabilities computed from the two hands and the board at the moment the betting
ended, W / T / L the stack change in each case under the actual rake rule (9% of the whole
pot, borne by the winner).  Everything else is left untouched.  The adjusted number has the
same expectation as the raw one and a smaller variance, so it needs fewer hands to show a
difference.

    .venv/bin/python -m analysis.allin_ev pokerfate/logs/archive/2026-11-*.pokerfate.bak.log pokerfate/logs/pokerfate.log [--since ISO]
"""
from __future__ import annotations

import argparse
import itertools
import math
import random

import eval7

from analysis import pflog
from analysis.features import mean_se, usable
from analysis.human_only import human_table
from analysis.rake import collect

RAKE = 0.09
_DECK = [r + s for r in "23456789TJQKA" for s in "cdhs"]


def win_tie_lose(hero: list, opp: list, board: list, rng: random.Random, samples: int = 20000) -> tuple:
    """(P win, P tie, P lose) for hero; exact from the flop on, Monte Carlo before the flop."""
    dead = set(hero) | set(opp) | set(board)
    rest = [eval7.Card(c) for c in _DECK if c not in dead]
    hc = [eval7.Card(c) for c in hero]
    oc = [eval7.Card(c) for c in opp]
    bc = [eval7.Card(c) for c in board]
    need = 5 - len(bc)
    if need == 0:
        runs = [()]
    elif need <= 2:
        runs = itertools.combinations(rest, need)
    else:
        runs = (rng.sample(rest, need) for _ in range(samples))
    w = t = n = 0
    for run in runs:
        full = bc + list(run)
        a = eval7.evaluate(hc + full)
        b = eval7.evaluate(oc + full)
        n += 1
        if a > b:
            w += 1
        elif a == b:
            t += 1
    return w / n, t / n, (n - w - t) / n


def adjust(h, rng: random.Random):
    """Hero's all-in-adjusted stack change in chips, or None when the hand does not qualify."""
    hero = h["hero_name"]
    res = h.get("result")
    if not res or not h.get("showdown") or not h.get("dealt") or not h["actions"]:
        return None
    ended = h["actions"][-1]["street"]          # street of the last bet / call, not of the last board card
    if ended == "river":
        return None
    rem = h.get("remaining") or []
    if hero not in rem or len(rem) != 2:
        return None
    opp = rem[0] if rem[1] == hero else rem[1]
    if hero not in h["allin"] and opp not in h["allin"]:
        return None
    oc = res["showdown_hands"].get(opp)
    hole = h.get("hole") or []
    if not oc or len(oc) != 2 or len(hole) != 2:
        return None
    inv = h["invested"]
    x = min(inv[hero], inv[opp])
    dead = sum(v for n, v in inv.items() if n not in (hero, opp))
    pot = 2 * x + dead
    win = pot * (1 - RAKE) - x
    tie = pot * (1 - RAKE) / 2 - x
    order = ["preflop", "flop", "turn"]
    board = []
    for st in order[1:order.index(ended) + 1]:   # the board that was out when the betting ended
        board += h["board"].get(st, [])
    pw, pt, pl = win_tie_lose(hole, oc, board, rng)
    return dict(adj=pw * win + pt * tie - pl * x, win=win, lose=-x, p_win=pw, p_tie=pt, street=ended, opp=opp,
                rake=(pw + pt / 2) * pot * RAKE)       # the rake hero expects to pay in this pot


class Adjuster:
    """Hero's result per hand (bb): raw and all-in adjusted."""

    def __init__(self, hands, seed: int = 11):
        rng = random.Random(seed)
        rows, _bad = collect(hands)
        self.raw = {(r["key"], str(r["ts"])): r["hero_delta"] for r in rows if r["hero_dealt"]}
        self.adj = dict(self.raw)
        self.paid = {(r["key"], str(r["ts"])): r["hero_paid"] for r in rows if r["hero_dealt"]}   # rake borne by hero
        self.changed = []
        self.model_err = []
        for h in hands:
            k = (h["key"], str(h["ts"]))
            if k not in self.raw:
                continue
            a = adjust(h, rng)
            if a is None:
                continue
            bb = h["bb"]
            raw = self.raw[k]
            # the win / lose amounts must reproduce what actually happened
            expect = a["win"] / bb if raw > 0 else a["lose"] / bb
            if raw != 0 and abs(expect - raw) > max(0.6, 0.02 * abs(expect)) and not (0 < a["p_tie"] and abs(raw) < 1):
                self.model_err.append((h["key"], raw, expect))
                continue
            self.adj[k] = a["adj"] / bb
            self.paid[k] = a["rake"] / bb
            self.changed.append(dict(key=h["key"], ts=h["ts"], raw=raw, adj=a["adj"] / bb, p_win=a["p_win"], street=a["street"],
                                     hole=h["hole"], opp=h["result"]["showdown_hands"][a["opp"]]))

    def get(self, h, adjusted=True):
        return (self.adj if adjusted else self.raw).get((h["key"], str(h["ts"])))

    def before_rake(self, h):
        """Adjusted result with the rake hero paid (or expected to pay) added back."""
        k = (h["key"], str(h["ts"]))
        return self.adj[k] + self.paid[k] if k in self.adj else None


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("logs", nargs="+")
    ap.add_argument("--since", default="")
    args = ap.parse_args(argv)
    hands, _ = pflog.load(args.logs)
    pflog.validate(hands)
    hands = [h for h in hands if h.get("players") and usable(h) and human_table(h) and (h["ts"] or "") >= args.since]
    adj = Adjuster(hands)
    raw = list(adj.raw.values())
    new = list(adj.adj.values())
    m0, se0, n = mean_se(raw)
    m1, se1, _ = mean_se(new)
    sd0, sd1 = se0 * math.sqrt(n), se1 * math.sqrt(n)
    print(f"真人桌 {n} 手；符合条件并已修正的全下摊牌 {len(adj.changed)} 手（金额对不上而跳过 {len(adj.model_err)} 手）")
    print(f"  原始结果      {100 * m0:+6.1f} ± {196 * se0:4.1f} bb/100   单手标准差 {sd0:.2f}bb")
    print(f"  全下运气修正后 {100 * m1:+6.1f} ± {196 * se1:4.1f} bb/100   单手标准差 {sd1:.2f}bb")
    print(f"  这些全下底池：实际 {sum(c['raw'] for c in adj.changed):+.1f}bb，按胜率应得 {sum(c['adj'] for c in adj.changed):+.1f}bb"
          f"（运气 {sum(c['raw'] - c['adj'] for c in adj.changed):+.1f}bb）")
    print(f"  同样的把握所需手数变为原来的 {100 * (sd1 / sd0) ** 2:.0f}%")
    print("  -- 运气成分最大的 10 手")
    for c in sorted(adj.changed, key=lambda c: abs(c["raw"] - c["adj"]), reverse=True)[:10]:
        print(f"     {str(c['ts'])[:16]} {c['street']:<7} {''.join(c['hole'])} vs {''.join(c['opp'])}  胜率 {100 * c['p_win']:4.1f}%  实际 {c['raw']:+7.1f}  应得 {c['adj']:+7.1f}")
    for k, raw_d, exp in adj.model_err[:5]:
        print(f"     [跳过] {k} 实际 {raw_d:+.1f} 与按规则推算的 {exp:+.1f} 不符")


if __name__ == "__main__":
    main()
