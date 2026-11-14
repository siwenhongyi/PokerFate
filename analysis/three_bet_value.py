"""Thin value 3-bets against the pool: the evidence behind ``_POOL_VALUE_3BET_HANDS`` and its tracking.

Sections 1–3 are pool-level evidence and grow with the logs: how a first-in opener answers a
clean 3-bet (nobody else in the pot), which hands openers show after continuing, and how each
candidate hand fares against those hands once the 9% rake is paid.  Section 4 follows the spots
the widened 3-bet applies to, before and after the switch, and states the guard-rail.

    .venv/bin/python -m analysis.three_bet_value pokerfate/logs/archive/2026-11-*.pokerfate.bak.log pokerfate/logs/pokerfate.log [--hero-since ISO]
"""
from __future__ import annotations

import argparse
import random
from collections import Counter

import eval7
import numpy as np

from analysis import pflog
from analysis.allin_ev import win_tie_lose
from analysis.features import mean_se, usable, wilson
from analysis.human_only import human_table
from analysis.preflop_price import cls_of, combos_of
from analysis.preflop_rake import Book, hero_cls, preflop_view
from pokerfate.core.position import normalize_position
from pokerfate.data import lookup_gto
from pokerfate.strategy import preflop as pf

KEEP = 0.91                                   # the winner keeps 91% of the matched pot
VALUE_TIER = ["TT", "AQo", "AJs", "KQs"]      # weakest hands of the existing value 3-bet range
WIDENED = [c for c in ("99", "88", "AJo", "ATs", "77", "KQo", "KJs") if c in pf._POOL_VALUE_3BET_HANDS]
NOT_WIDENED = [c for c in ("77", "KQo", "KJs", "66", "ATo", "A9s") if c not in pf._POOL_VALUE_3BET_HANDS]
GUARD_MIN_N = 30
_CARDS = {r + s: eval7.Card(r + s) for r in "23456789TJQKA" for s in "cdhs"}
_DECK = list(_CARDS)


def rate(k: int, n: int) -> str:
    if not n:
        return "    –"
    lo, hi = wilson(k, n)
    return f"{100 * k / n:5.1f}% [{100 * lo:4.1f},{100 * hi:4.1f}]"


def stack_bb(h, name) -> float:
    p = next((p for p in h["players"] if p["name"] == name), None)
    return p["stack"] / h["bb"] if p else 0.0


# ---------------------------------------------------------------------------
# 1–2  the pool's answer to a clean 3-bet and the hands it shows afterwards
# ---------------------------------------------------------------------------
def opener_answers(hands) -> tuple:
    """(Counter per context, classes shown after a call, classes shown after a 4-bet)."""
    ctx = {k: Counter() for k in ("全部", "3bet 者有位置", "3bet 者在盲注位")}
    called, four = [], []
    for h in hands:
        v = preflop_view(h)
        f, t = v["first"], v.get("three")
        if f is None or t is None or v["kind"] != "open" or f["hero"]:
            continue
        if any(s["act"] == "call" and s["i"] < t["i"] for s in v["answers"]):
            continue                                    # a squeeze: different spot
        mine = [s for s in v["vs3"] if s["who"] == f["who"]]
        if not mine:
            continue
        act = mine[0]["act"]
        ctx["全部"][act] += 1
        ctx["3bet 者在盲注位" if t["pos"] in ("SB", "BB") else "3bet 者有位置"][act] += 1
        cards = h["result"]["showdown_hands"].get(f["who"])
        if cards and len(cards) == 2 and act != "fold":
            (called if act == "call" else four).append(cls_of(cards[0], cards[1]))
    return ctx, called, four


# ---------------------------------------------------------------------------
# 3  equity of a hand class against the shown hands
# ---------------------------------------------------------------------------
def class_equity(a: str, b: str, rng: random.Random, samples: int) -> tuple:
    """(all-in equity of class ``a`` against class ``b``, share of b's combos a leaves possible)."""
    pairs = [(x, y) for x in combos_of(a) for y in combos_of(b) if not {*x} & {*y}]
    if not pairs:
        return 0.5, 0.0
    won = 0.0
    for _ in range(samples):
        x, y = rng.choice(pairs)
        dead = {*x, *y}
        board = rng.sample(_DECK, 5)
        while dead & set(board):
            board = rng.sample(_DECK, 5)
        bc = [_CARDS[c] for c in board]
        s1 = eval7.evaluate([_CARDS[x[0]], _CARDS[x[1]]] + bc)
        s2 = eval7.evaluate([_CARDS[y[0]], _CARDS[y[1]]] + bc)
        won += 1.0 if s1 > s2 else 0.5 if s1 == s2 else 0.0
    return won / samples, len(pairs) / (len(combos_of(a)) * len(combos_of(b)))


class Against:
    """Equity of hero classes against a list of shown classes, with a bootstrap over the list."""

    def __init__(self, heroes, shown, seed=3, samples=1500, boot=2000):
        rng = random.Random(seed)
        cache = {}
        self.shown = shown
        self.eq, self.w = {}, {}
        for a in heroes:
            for b in set(shown):
                cache[(a, b)] = class_equity(a, b, rng, samples)
            self.eq[a] = np.array([cache[(a, b)][0] for b in shown])
            self.w[a] = np.array([cache[(a, b)][1] for b in shown])      # card removal
        self.idx = np.random.default_rng(seed).integers(0, len(shown), size=(boot, len(shown))) if shown else None

    def mean(self, a) -> float:
        return float((self.eq[a] * self.w[a]).sum() / self.w[a].sum())

    def boot(self, a) -> np.ndarray:
        e, w = self.eq[a] * self.w[a], self.w[a]
        return e[self.idx].sum(axis=1) / w[self.idx].sum(axis=1)

    def interval(self, a) -> tuple:
        lo, hi = np.percentile(self.boot(a), [2.5, 97.5])
        return float(lo), float(hi)


def no_postflop_edge(e: float, f: float, c: float, r: float, three: float, open_bb: float, posted: float, dead: float) -> float:
    """bb per 3-bet relative to folding when a called pot is simply checked down.

    Everybody folds: hero collects the open and the dead blinds, less the rake on the matched
    part.  4-bet: hero folds.  Called: hero wins the raked pot with probability ``e``.
    """
    win = open_bb + dead + posted - (1 - KEEP) * (2 * open_bb + dead)
    pot = 2 * three + dead
    return f * win - r * (three - posted) + c * (e * KEEP * pot - (three - posted))


def break_even(f, c, r, three, open_bb, posted, dead) -> float:
    lo, hi = 0.0, 1.0
    for _ in range(40):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if no_postflop_edge(mid, f, c, r, three, open_bb, posted, dead) < 0 else (lo, mid)
    return hi


def sec_evidence(hands) -> dict:
    ctx, called, four = opener_answers(hands)
    print("== 1 对手首加者面对一个干净的 3bet（真人桌，无人先跟注）==")
    freq = {}
    for k, c in ctx.items():
        n = sum(c.values())
        freq[k] = (c["fold"] / n, c["call"] / n, c["raise"] / n) if n else (0.0, 0.0, 0.0)
        print(f"   {k:<10} n={n:4d}  弃 {rate(c['fold'], n)}  跟 {100 * freq[k][1]:5.1f}%  4bet {100 * freq[k][2]:5.1f}%")
    print(f"\n== 2 继续之后亮出的牌：跟注 {len(called)} 手，4bet {len(four)} 手 ==")
    for name, lst in (("跟注", called), ("4bet", four)):
        c = Counter(lst)
        pairs = sum(v for k, v in c.items() if len(k) == 2)
        print(f"   {name} 口袋对 {100 * pairs / max(1, len(lst)):.0f}%：" + " ".join(f"{k}×{v}" for k, v in c.most_common(24)) + " …")
    if len(called) < 20:
        print("   亮牌太少，无法估计。")
        return {}

    heroes = VALUE_TIER + WIDENED + NOT_WIDENED
    vs_call, vs_four = Against(heroes, called), Against(heroes, four) if four else None
    strat = pf.PreflopStrategy()
    open_bb = 3.0
    ip = dict(three=strat.three_bet_size(open_bb, True, 1.0, "CO", "BTN"), open_bb=open_bb, posted=0.0, dead=1.5)
    sb = dict(three=strat.three_bet_size(open_bb, False, 1.0, "BTN", "SB"), open_bb=open_bb, posted=0.5, dead=1.0)
    f_ip, f_sb = freq["3bet 者有位置"], freq["3bet 者在盲注位"]
    be_ip, be_sb = break_even(*f_ip, **ip), break_even(*f_sb, **sb)
    print("\n== 3 各手牌对“跟注 3bet 的范围”的全下胜率，以及不计翻后的每次 3bet 结果 ==")
    print(f"   抽水 9%：被跟注的钱要赚，胜率须高于 1/(2×0.91) = {100 / (2 * KEEP):.1f}%。")
    print(f"   不计翻后（跟注后一路过牌到摊牌、被 4bet 就弃）相对弃牌的盈亏平衡胜率：")
    print(f"     按钮位对 CO {open_bb:.0f}bb（3bet 到 {ip['three']:.1f}bb）{100 * be_ip:.1f}%；小盲对按钮 {open_bb:.0f}bb（3bet 到 {sb['three']:.1f}bb）{100 * be_sb:.1f}%")
    print(f"   {'':<6}{'对跟注范围 [95% 区间]':<26}{'对 4bet 范围':<12}{'按钮位 bb/次':>12}{'小盲 bb/次':>12}")
    out = {}
    for title, group in (("现有价值档最弱的几手", VALUE_TIER), ("已放宽", WIDENED), ("未放宽", NOT_WIDENED)):
        print(f"   -- {title}")
        for a in group:
            e = vs_call.mean(a)
            lo, hi = vs_call.interval(a)
            four_txt = f"{100 * vs_four.mean(a):5.1f}%" if vs_four else "   –"
            out[a] = dict(e=e, lo=lo, hi=hi, ip=no_postflop_edge(e, *f_ip, **ip), sb=no_postflop_edge(e, *f_sb, **sb))
            print(f"   {a:<6}{100 * e:5.1f}% [{100 * lo:4.1f},{100 * hi:4.1f}]{'':<8}{four_txt:<12}{out[a]['ip']:>+10.2f}{out[a]['sb']:>+12.2f}")
    print("   读法：最后两列是下限口径。hero 现有价值档 3bet 的实际结果高于这个口径，差额来自翻后；")
    print("         放宽的牌要靠同样的翻后优势才明显为正，否则约等于 0。")
    return out


# ---------------------------------------------------------------------------
# 4  the widened spot, before and after
# ---------------------------------------------------------------------------
def widened_spots(book, since: str) -> list:
    rows = []
    for h in book.hands:
        if (h["ts"] or "") < since:
            continue
        v = preflop_view(h)
        f = v["first"]
        if f is None or f["hero"] or v["kind"] != "open":
            continue
        mine = [s for s in v["answers"] if s["hero"] and s["first_action"]]
        cls = hero_cls(h)
        if not mine or cls not in pf._POOL_VALUE_3BET_HANDS or mine[0]["callers"]:
            continue
        s = mine[0]
        dec = s.get("dec") if isinstance(s.get("dec"), dict) else {}
        reason = str(dec.get("preflop_expand_reason") or "")
        tagged = reason.startswith("pool_value_3bet")
        eff = min(stack_bb(h, h["hero_name"]), stack_bb(h, f["who"]))
        key = f"{normalize_position(dec.get('position') or s['pos'])}-vs-open-{normalize_position(f['pos'])}"
        chart = lookup_gto(key, cls).get("primary")
        in_spot = chart == "raise" and eff >= pf._POOL_VALUE_3BET_MIN_EFFECTIVE_BB and 1 < f["to_bb"] <= pf._POOL_VALUE_3BET_MAX_OPEN_BB
        d = book.delta(h, h["hero_name"])
        if d is None or not (tagged or in_spot):
            continue
        after = [x for x in v["spots"] if x["i"] > s["i"]]
        branch = "–"
        if s["act"] == "raise":
            branch = "被4bet" if any(x["act"] == "raise" for x in after) else "被跟注" if any(x["act"] == "call" for x in after) else "全弃"
        rows.append(dict(h=h, cls=cls, key=key, act=s["act"], d=d, tagged=tagged, branch=branch, eff=eff, size=f["to_bb"], reason=reason))
    return rows


def sec_tracking(book, since: str, n_hero: int) -> None:
    rows = widened_spots(book, since)
    old = [r for r in rows if not r["tagged"]]
    new = [r for r in rows if r["tagged"]]
    print(f"\n== 4 放宽场景的跟踪（{since[:10]} 起，hero {n_hero} 手）==")
    print(f"   场景：{'/'.join(WIDENED)}，面对单个率先加注（≤{pf._POOL_VALUE_3BET_MAX_OPEN_BB:.0f}bb）、无人先入池、"
          f"有效筹码 ≥{pf._POOL_VALUE_3BET_MIN_EFFECTIVE_BB:.0f}bb、谱为 3bet、桌上无人机")
    print(f"   出现频率：{len(rows)} 次，每 100 手 {100 * len(rows) / max(1, n_hero):.2f} 次")
    for title, rs in (("旧逻辑（削减层生效）", old), ("放宽后（决策带 pool_value_3bet 标记）", new)):
        c = Counter(r["act"] for r in rs)
        m, se, n = mean_se([r["d"] for r in rs])
        tail = f"每次 {m:+.2f} ± {1.96 * se:.2f}bb（全下运气修正后）" if n > 1 else ""
        print(f"   -- {title}：{n} 次  3bet {c['raise']}  跟 {c['call']}  弃 {c['fold']}  {tail}")
        for r in rs:
            print(f"        {str(r['h']['ts'])[5:16]} {r['cls']:<4} {r['key']:<16} 加注到 {r['size']:.1f}bb 有效 {r['eff']:5.1f}bb  {r['act']:<5} {r['branch']:<5} {r['d']:+7.2f}")
    if new:
        c = Counter(r["branch"] for r in new)
        print(f"   放宽后的对手应对：全弃 {c['全弃']}  被跟注 {c['被跟注']}  被4bet {c['被4bet']}（对照第 1 节的比例）")
        rng = random.Random(5)
        eqs = []
        for r in new:
            h = r["h"]
            for name, cards in h["result"]["showdown_hands"].items():
                if name != h["hero_name"] and cards and len(cards) == 2 and len(h.get("hole") or []) == 2:
                    w, t, _l = win_tie_lose(h["hole"], cards, [], rng, samples=4000)
                    eqs.append(w + t / 2)
        if eqs:
            print(f"   对亮出的继续牌，hero 这些牌的翻前胜率平均 {100 * sum(eqs) / len(eqs):.1f}%（n={len(eqs)}；要求见第 3 节的盈亏平衡线）")
    m, se, n = mean_se([r["d"] for r in new if r["act"] == "raise"])
    print("   停止规则：")
    print(f"     1) 放宽后的 3bet 满 {GUARD_MIN_N} 次时，若“均值 + 1.28×标准误”仍小于 0，关掉 PF_3BET_VALUE_EXPAND。")
    print("     2) 第 3 节里某手已放宽的牌，对跟注范围胜率的 95% 上界跌破按钮位盈亏平衡线，就把它移出。")
    if n >= GUARD_MIN_N:
        verdict = "触发：关掉" if m + 1.28 * se < 0 else "未触发：保留"
        print(f"     现状：{n} 次，{m:+.2f} ± {1.96 * se:.2f}bb → {verdict}")
    else:
        need = (GUARD_MIN_N - n) / max(1e-9, len(rows) / max(1, n_hero)) if rows else float("inf")
        print(f"     现状：{n} 次，未到 {GUARD_MIN_N} 次；按现在的频率还要约 {need:,.0f} 手。")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("logs", nargs="+")
    ap.add_argument("--hero-since", default="2026-11-09")
    args = ap.parse_args(argv)
    hands, _ = pflog.load(args.logs)
    pflog.validate(hands)
    hands = [h for h in hands if h.get("players") and usable(h) and human_table(h)]
    print(f"真人桌 {len(hands)} 手\n")
    sec_evidence(hands)
    n_hero = sum(1 for h in hands if (h["ts"] or "") >= args.hero_since)
    sec_tracking(Book(hands), args.hero_since, n_hero)


if __name__ == "__main__":
    main()
