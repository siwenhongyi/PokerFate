"""Preflop under a 9% uncapped rake: how the human pool answers raises, and what hero's
preflop lines earn.

    .venv/bin/python -m analysis.preflop_rake pokerfate/logs/archive/2026-11-*.pokerfate.bak.log pokerfate/logs/pokerfate.log [--hero-since ISO]

Only hands at tables without a house robot are used.  Two kinds of numbers, kept apart:

* pool response curves (fold / call / re-raise against a raise of a given size) use every
  human-table hand and every raiser.  The responders cannot see the raiser's cards, so these
  frequencies do not depend on who raised or with what - they are what hero should expect.
* hero's own results (bb per decision, after rake) use hands from --hero-since on; they are
  the noisy part and always carry a 95% interval.

A range estimator that needs no showdown: when a pot ends before the flop the server still
reports the winner's hand type, i.e. whether he holds a pocket pair (checked against hero's
own preflop wins).  Pairs are 5.9% of all hands, so the pair share of *uncalled* raises
tells how narrow the raising range is (QQ+/AK = 53% pairs, a top-15% range ≈ 39%).

Sections
  1  the rake on a steal
  2  pool answers to a first-in raise, by size
  3  hero's first-in raises: by position and hand tier, split into branches
  4  hero's raise gets re-raised: what pool 3-bets are, and hero's answers
  5  hero facing a raise: fold / call / 3-bet by hand tier, and what each earned
  6  limped pots: how limpers answer an isolation raise, hero's isolation raises
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict

from analysis import pflog
from analysis.allin_ev import Adjuster
from analysis.features import mean_se, preflop_spots, usable, wilson
from analysis.human_only import human_table
from analysis.preflop_price import ALL_CLASSES, cls_of, combos_of
from analysis.rake import collect

# Hand tiers follow the bot's own nested preflop ranges, so a tier means the same thing as in
# pokerfate/strategy/preflop.py: what it continues with under pressure, what it opens from
# early position, what it adds in the cut-off, and what it only plays as a steal.
TIER_NAMES = ["顶级 QQ+/AK", "强牌 TT-JJ/AQ/AJs/KQs", "前位开池牌", "中后位加开的牌", "偷盲牌", "范围外"]
TOP, STRONG = TIER_NAMES[0], TIER_NAMES[1]
PAIR_SHARE_ALL = 78 / 1326


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def hand_tiers() -> dict:
    """Hand class ('AKs', '77', 'T9o') -> tier name."""
    from pokerfate.strategy import preflop as pf

    top = pf._PRESSURE_PREMIUM_CONTINUE
    strong = pf._PRESSURE_STRONG_CONTINUE
    steal = pf._BTN_RANGE | pf._SB_RANGE | pf._SB_STEAL_VS_BB
    out = {}
    for cls in ALL_CLASSES:
        if cls in top:
            out[cls] = TIER_NAMES[0]
        elif cls in strong:
            out[cls] = TIER_NAMES[1]
        elif cls in pf._UTG_RANGE:
            out[cls] = TIER_NAMES[2]
        elif cls in pf._CO_RANGE:
            out[cls] = TIER_NAMES[3]
        elif cls in steal:
            out[cls] = TIER_NAMES[4]
        else:
            out[cls] = TIER_NAMES[5]
    return out


def tier_of(tier: str) -> str:
    return tier


def size_bucket(x: float) -> str:
    if x < 2.25:
        return "2x"
    if x < 2.75:
        return "2.5x"
    if x < 3.25:
        return "3x"
    if x < 3.75:
        return "3.5x"
    if x < 4.5:
        return "4x"
    return "5x+"


SIZES = ["2x", "2.5x", "3x", "3.5x", "4x", "5x+"]


def rate(k: int, n: int) -> str:
    if n == 0:
        return "      –      "
    lo, hi = wilson(k, n)
    return f"{100 * k / n:5.1f}% [{100 * lo:4.1f},{100 * hi:4.1f}]"


def ev(xs, unit="bb") -> str:
    m, se, n = mean_se(xs)
    if n == 0:
        return "–"
    if n < 2:
        return f"{m:+6.2f}{unit} (n=1)"
    return f"{m:+6.2f} ± {1.96 * se:4.2f}{unit} (n={n})"


class Book:
    """Hands plus per-player money (bb, after rake) and the rake each winner paid.

    Hero's results are all-in adjusted (analysis.allin_ev) unless ``raw`` is set: a pot that
    got all in before the river counts for its expectation, not for how the cards fell."""

    def __init__(self, hands, raw=False):
        self.hands = hands
        rows, _bad = collect(hands)
        self.money = {(r["key"], str(r["ts"])): r for r in rows}
        self.adj = None if raw else Adjuster(hands)

    def delta(self, h, name):
        r = self.money.get((h["key"], str(h["ts"])))
        if r is None:
            return None
        if self.adj is not None and name == h["hero_name"]:
            return self.adj.get(h)
        return r["deltas"].get(name)

    def delta_pre(self, h, name):
        """Result before rake: the winners bear the rake pro rata."""
        r = self.money.get((h["key"], str(h["ts"])))
        if r is None or name not in r["deltas"]:
            return None
        if self.adj is not None and name == h["hero_name"]:
            return self.adj.before_rake(h)
        d = r["deltas"][name]
        gross = sum(v for v in r["deltas"].values() if v > 0)
        return d + (r["rake"] * d / gross if d > 0 and gross > 0 else 0.0)


def preflop_view(h):
    """Structure of the preflop round: the first raise, its answers, the re-raise, …"""
    spots = preflop_spots(h)
    first = next((s for s in spots if s["act"] == "raise"), None)
    if first is None:
        return dict(spots=spots, first=None)
    kind = "open" if first["sit"] == "unopened" else "iso"
    # answers to the first raise, before anybody re-raises
    answers = [s for s in spots if s["i"] > first["i"] and s["raises"] == 1]
    three = next((s for s in spots if s["i"] > first["i"] and s["act"] == "raise"), None)
    vs3 = [s for s in spots if three is not None and s["i"] > three["i"] and s["raises"] == 2]
    four = next((s for s in spots if three is not None and s["i"] > three["i"] and s["act"] == "raise"), None)
    callers = [s for s in answers if s["act"] == "call"]
    return dict(spots=spots, first=first, kind=kind, answers=answers, three=three, vs3=vs3, four=four,
                callers=callers, steal=(three is None and not callers),
                behind=sum(1 for s in answers if s["first_action"]) if three is None else None)


def hero_cls(h):
    hole = h.get("hole") or []
    return cls_of(hole[0], hole[1]) if len(hole) == 2 else None


def uncalled_pair_share(book, pick):
    """Pair share among raises that everybody folded to.  ``pick(h, view)`` returns the raiser's
    name when the hand qualifies (pot ended preflop and he is the only winner)."""
    k = n = 0
    for h in book.hands:
        if "flop" in h["board"]:
            continue
        v = preflop_view(h)
        who = pick(h, v)
        if not who:
            continue
        res = h["result"]
        if res["winners"] != [who]:
            continue
        lab = (res["hand_combos"].get(who) or "").split(" ")[0]
        if lab not in ("一对", "高牌"):
            continue
        n += 1
        k += 1 if lab == "一对" else 0
    return k, n


def implied_range(k, n):
    """Width of a range holding every pocket pair that would show this pair share."""
    if not n or not k:
        return "–"
    lo, hi = wilson(k, n)
    f = lambda p: 100 * PAIR_SHARE_ALL / p if p > 0 else float("inf")
    return f"口袋对 {100 * k / n:.0f}% → 若包含全部对子，范围约为前 {f(k / n):.0f}%（区间 {f(hi):.0f}–{f(lo):.0f}%）"


# ---------------------------------------------------------------------------
# 1  rake on a steal
# ---------------------------------------------------------------------------
def sec_rake(book):
    print("== 1 抽水规则（翻前结束的底池也抽）==")
    by = defaultdict(list)
    for r in book.money.values():
        if not r["saw_flop"] and r["moved"] > 0:
            by[round(r["moved"], 1)].append(r["rake"])
    for k in (0.5, 1.5, 2.5):
        if by.get(k):
            xs = by[k]
            print(f"  输家共投入 {k:.1f}bb 的翻前底池 {len(xs):4d} 个：平均抽水 {sum(xs) / len(xs):.3f}bb")
    print("  规则：抽整个被跟平的底池的 9%（含赢家自己被跟平的那部分），由赢家出。")
    print("  所以偷到盲注（1.5bb）实得 1.275bb；小盲弃给大盲，大盲实得 0.365bb。")


# ---------------------------------------------------------------------------
# 2  pool answers to a first-in raise
# ---------------------------------------------------------------------------
def sec_open_answers(book):
    print("\n== 2 真人对手池怎样回应“率先加注”（全部真人桌、全部加注者）==")
    per = defaultdict(Counter)     # (role, size, callers_before>0) -> fold/call/raise
    opens = defaultdict(list)      # size -> list of dict
    for h in book.hands:
        v = preflop_view(h)
        if v["first"] is None or v["kind"] != "open":
            continue
        f = v["first"]
        sb = size_bucket(f["to_bb"])
        for s in v["answers"]:
            if s["hero"]:
                continue               # hero's own answers are not the pool's
            role = s["pos"] if s["pos"] in ("SB", "BB") else "其他"
            per[(role, sb, s["callers"] > 0)][s["act"]] += 1
            per[(role, "全部", s["callers"] > 0)][s["act"]] += 1
        behind = h["n"] - 1 - sum(1 for s in v["spots"] if s["i"] < f["i"])
        opens[sb].append(dict(hero=f["hero"], behind=behind, steal=v["steal"], three=v["three"] is not None,
                              callers=len(v["callers"]), flop_n=len(h.get("flop_players") or []),
                              d=book.delta(h, f["who"]), pos=f["pos"]))
    print("  -- 每个面对加注的人（前面还没人跟注时）：弃 / 跟 / 再加注")
    for role in ("其他", "SB", "BB"):
        for sb in SIZES + ["全部"]:
            c = per[(role, sb, False)]
            n = sum(c.values())
            if n < 30:
                continue
            print(f"     {role:<3} 加注到{sb:<5} n={n:4d}  弃 {rate(c['fold'], n)}  跟 {100 * c['call'] / n:5.1f}%  再加注 {100 * c['raise'] / n:4.1f}%")
    print("  -- 前面已有人跟注时")
    for role in ("其他", "SB", "BB"):
        c = per[(role, "全部", True)]
        n = sum(c.values())
        if n:
            print(f"     {role:<3} n={n:4d}  弃 {rate(c['fold'], n)}  跟 {100 * c['call'] / n:5.1f}%  再加注 {100 * c['raise'] / n:4.1f}%")
    print("  -- 每次率先加注的结局（按尺度；身后还有 ≥3 人 / ≤2 人）")
    for many in (True, False):
        print(f"     身后{'≥3' if many else '≤2'}人：")
        for sb in SIZES:
            rs = [o for o in opens[sb] if (o["behind"] >= 3) == many]
            n = len(rs)
            if n < 25:
                continue
            st = sum(o["steal"] for o in rs)
            th = sum(o["three"] for o in rs)
            called = [o for o in rs if not o["steal"] and not o["three"]]
            multi = sum(1 for o in called if o["callers"] >= 2)
            print(f"       加注到{sb:<5} n={n:4d}  全弃 {rate(st, n)}  被再加注 {100 * th / n:4.1f}%  被跟注 {100 * len(called) / n:4.1f}%"
                  f"（其中≥2人跟 {100 * multi / max(1, len(called)):3.0f}%）")
    k, n = uncalled_pair_share(book, lambda h, v: v["first"]["who"] if v["first"] and v["kind"] == "open" and v["steal"]
                               and not v["first"]["hero"] else None)
    print(f"  -- 对手池率先加注的范围有多宽（无人跟注的 {n} 次）：{implied_range(k, n)}")
    for sb in SIZES:
        k, n = uncalled_pair_share(book, lambda h, v, sb=sb: v["first"]["who"] if v["first"] and v["kind"] == "open" and v["steal"]
                                   and not v["first"]["hero"] and size_bucket(v["first"]["to_bb"]) == sb else None)
        if n >= 25:
            print(f"       加注到{sb:<5} n={n:4d}  {implied_range(k, n)}")
    return opens


# ---------------------------------------------------------------------------
# 3  hero's first-in raises
# ---------------------------------------------------------------------------
def hero_opens(book, since, pct):
    rows = []
    for h in book.hands:
        if (h["ts"] or "") < since:
            continue
        v = preflop_view(h)
        f = v["first"]
        if f is None or v["kind"] != "open" or not f["hero"]:
            continue
        d = book.delta(h, h["hero_name"])
        cls = hero_cls(h)
        if d is None or cls is None:
            continue
        branch = "全弃" if v["steal"] else ("被再加注" if v["three"] is not None else "被跟注")
        resp = None
        if v["three"] is not None:
            mine = [s for s in v["vs3"] if s["hero"]]
            resp = mine[0]["act"] if mine else None
        rows.append(dict(pos=f["pos"], size=f["to_bb"], cls=cls, pct=pct[cls], tier=tier_of(pct[cls]), branch=branch,
                         d=d, pre=book.delta_pre(h, h["hero_name"]), callers=len(v["callers"]), resp=resp, n=h["n"],
                         three_to=(v["three"]["to_bb"] if v["three"] else None), h=h, v=v))
    return rows


def branch_table(rows, key, order, base=lambda r: 0.0, min_n=8):
    w = max(8, max(len(str(k)) for k in order) + 1)
    for k in order:
        rs = [r for r in rows if key(r) == k]
        n = len(rs)
        if n < min_n:
            continue
        parts = []
        for b in ("全弃", "被跟注", "被再加注"):
            bs = [r for r in rs if r["branch"] == b]
            m = sum(r["d"] for r in bs) / len(bs) if bs else float("nan")
            parts.append(f"{b} {100 * len(bs) / n:4.1f}%×{m:+5.2f}")
        rel = [r["d"] - base(r) for r in rs]
        print(f"     {k:<{w}} n={n:3d}  {'  '.join(parts)}  | 每次 {ev([r['d'] for r in rs])}  抽水前 {sum(r['pre'] for r in rs) / n:+5.2f}"
              f"  相对弃牌 {sum(rel) / n:+5.2f}")


def sec_hero_opens(book, since, pct):
    rows = hero_opens(book, since, pct)
    n_hands = sum(1 for h in book.hands if (h["ts"] or "") >= since and h.get("dealt"))
    print(f"\n== 3 hero 的率先加注（{since[:10]} 起，{len(rows)} 次；单位 bb，抽水后）==")
    print("  每行：三种结局各自的 概率×平均结果，然后是每次加注的平均收益。相对弃牌：小盲弃牌是 −0.5，其余位置是 0。")
    base = lambda r: -0.5 if r["pos"] == "SB" else (-1.0 if r["pos"] == "BB" else 0.0)
    print("  -- 按位置")
    branch_table(rows, lambda r: r["pos"], ["UTG", "UTG+1", "MP", "CO", "BTN", "SB"], base)
    print("  -- 按牌力档（档位取自 bot 自己的翻前范围表）")
    branch_table(rows, lambda r: r["tier"], TIER_NAMES, base)
    print("  -- 位置组 × 牌力档")
    grp = lambda r: {"UTG": "前位", "UTG+1": "前位", "MP": "前位", "CO": "后位", "BTN": "后位", "SB": "小盲"}.get(r["pos"], "其他")
    for g in ("前位", "后位", "小盲"):
        print(f"    {g}:")
        branch_table([r for r in rows if grp(r) == g], lambda r: r["tier"], TIER_NAMES, base, min_n=6)
    print("  -- 被跟注后：单挑 / 多人")
    for label, sel in (("1 人跟注", lambda r: r["callers"] == 1), ("≥2 人跟注", lambda r: r["callers"] >= 2)):
        rs = [r for r in rows if r["branch"] == "被跟注" and sel(r)]
        print(f"     {label:<8} 每次 {ev([r['d'] for r in rs])}  抽水前 {sum(r['pre'] for r in rs) / max(1, len(rs)):+5.2f}")
    k = Counter((r["pos"], round(r["size"], 1)) for r in rows)
    print("  -- hero 的加注尺度:", ", ".join(f"{p} {s}bb×{c}" for (p, s), c in sorted(k.items())))
    print("  -- 合计")
    for label, sel in (("全部", lambda r: True), ("去掉顶级牌", lambda r: r["tier"] != TOP), ("前位", lambda r: grp(r) == "前位"),
                       ("后位", lambda r: grp(r) == "后位"), ("小盲", lambda r: grp(r) == "小盲")):
        rs = [r for r in rows if sel(r)]
        if rs:
            print(f"     {label:<10} 每次 {ev([r['d'] for r in rs])}  抽水前 {sum(r['pre'] for r in rs) / len(rs):+5.2f}"
                  f"  相对弃牌 {sum(r['d'] - base(r) for r in rs) / len(rs):+5.2f}  → 对总成绩 {100 * sum(r['d'] - base(r) for r in rs) / max(1, n_hands):+5.1f} bb/100")
    print("  -- 盈亏平衡：一手“被 3bet 就弃”的牌，被跟注后平均要拿到多少才不亏（用 hero 该位置的三种结局频率）")
    for g in ("前位", "后位", "小盲"):
        rs = [r for r in rows if grp(r) == g]
        n = len(rs)
        if n < 20:
            continue
        st = [r for r in rs if r["branch"] == "全弃"]
        th = [r for r in rs if r["branch"] == "被再加注"]
        ca = [r for r in rs if r["branch"] == "被跟注"]
        size = sum(r["size"] for r in rs) / n
        fold_val = -0.5 if g == "小盲" else 0.0
        steal = sum(r["d"] for r in st) / max(1, len(st))
        lose = -size if g != "小盲" else -size       # stack change when folding to the 3-bet
        need = (fold_val * n - len(st) * steal - len(th) * lose) / max(1, len(ca))
        weak = [r["d"] for r in ca if r["tier"] not in (TOP, STRONG)]
        print(f"     {g}（加到 {size:.1f}bb）全弃 {100 * len(st) / n:4.1f}%  被再加注 {100 * len(th) / n:4.1f}%  被跟注 {100 * len(ca) / n:4.1f}%"
              f"  → 被跟注后需要 ≥ {need:+.2f}bb；实际：全部牌 {ev([r['d'] for r in ca])}，顶级和强牌以外 {ev(weak)}")
    return rows


# ---------------------------------------------------------------------------
# 4  re-raised
# ---------------------------------------------------------------------------
def sec_three_bets(book, since, pct, opens_hero):
    print("\n== 4 被再加注（3bet）==")
    # pool-wide: what the first raiser does against a 3-bet, by 3-bet size relative to the open
    resp = defaultdict(Counter)
    ratios = []
    for h in book.hands:
        v = preflop_view(h)
        if v["first"] is None or v["three"] is None:
            continue
        f, t = v["first"], v["three"]
        if f["to_bb"] <= 0:
            continue
        ratio = t["to_bb"] / f["to_bb"]
        rb = "<2.5倍" if ratio < 2.5 else ("2.5-3.5倍" if ratio < 3.5 else "≥3.5倍")
        mine = [s for s in v["vs3"] if s["who"] == f["who"]]
        if not mine:
            continue
        if not t["hero"]:
            ratios.append(ratio)
        if f["hero"]:
            continue
        resp[rb][mine[0]["act"]] += 1
        resp["全部"][mine[0]["act"]] += 1
    print("  -- 对手池里的首加者面对 3bet（全部真人桌）")
    for rb in ("<2.5倍", "2.5-3.5倍", "≥3.5倍", "全部"):
        c = resp[rb]
        n = sum(c.values())
        if n:
            print(f"     3bet 为首加的{rb:<8} n={n:4d}  弃 {rate(c['fold'], n)}  跟 {100 * c['call'] / n:5.1f}%  4bet {100 * c['raise'] / n:4.1f}%")
    ratios.sort()
    if ratios:
        print(f"  -- 对手池 3bet 的尺度：中位数为首加的 {ratios[len(ratios) // 2]:.1f} 倍（n={len(ratios)}）")
    # how narrow are pool 3-bets?  pair share when everybody folds
    k, n = uncalled_pair_share(book, lambda h, v: v["three"]["who"] if v["first"] and v["three"] is not None and v["four"] is None
                               and not v["three"]["hero"] and not any(s["act"] == "call" for s in v["vs3"]) else None)
    print(f"  -- 对手池 3bet 的范围（所有人都弃牌的 {n} 次，无偏）：{implied_range(k, n)}")
    print("       参照：QQ+/AK 是 53% 口袋对，TT+/AQ+ 是 48%，随机两张 5.9%")
    shown = Counter()
    shown_n = 0
    for h in book.hands:
        v = preflop_view(h)
        if v["first"] is None or v["three"] is None or v["three"]["hero"]:
            continue
        cards = h["result"]["showdown_hands"].get(v["three"]["who"])
        if cards and len(cards) == 2:
            shown[tier_of(pct[cls_of(cards[0], cards[1])])] += 1
            shown_n += 1
    if shown_n:
        print(f"  -- 对手池 3bet 后摊牌亮出的牌（{shown_n} 次，偏向被跟注到底的那部分）：" + "  ".join(f"{t} {100 * shown[t] / shown_n:.0f}%" for t in TIER_NAMES))
    # hero's answers
    rs = [r for r in opens_hero if r["branch"] == "被再加注" and r["resp"]]
    print(f"  -- hero 首加后被 3bet（{len(rs)} 次）：按牌力档的应对与结果")
    for t in TIER_NAMES:
        ts = [r for r in rs if r["tier"] == t]
        if not ts:
            continue
        c = Counter(r["resp"] for r in ts)
        line = f"     {t:<12} n={len(ts):3d}  弃 {c['fold']:2d}  跟 {c['call']:2d}  4bet {c['raise']:2d}"
        for a, name in (("call", "跟注"), ("raise", "4bet")):
            xs = [r["d"] for r in ts if r["resp"] == a]
            if xs:
                line += f"  | {name} {ev(xs)}"
        print(line)
    for a, name in (("fold", "弃牌"), ("call", "跟注"), ("raise", "4bet")):
        xs = [r["d"] for r in rs if r["resp"] == a]
        if xs:
            print(f"     合计 {name} {ev(xs)}")
    need = [r for r in rs if r["three_to"]]
    if need:
        avg_open = sum(r["size"] for r in need) / len(need)
        avg_three = sum(r["three_to"] for r in need) / len(need)
        print(f"     平均：hero 加到 {avg_open:.1f}bb，对手 3bet 到 {avg_three:.1f}bb；被 3bet 的比例 {100 * len(rs) / max(1, len(opens_hero)):.0f}%")


# ---------------------------------------------------------------------------
# 5  hero facing a raise
# ---------------------------------------------------------------------------
def sec_vs_open(book, since, pct):
    print(f"\n== 5 hero 面对别人的率先加注（{since[:10]} 起，hero 第一次行动）==")
    rows = []
    for h in book.hands:
        if (h["ts"] or "") < since:
            continue
        v = preflop_view(h)
        f = v["first"]
        if f is None or f["hero"]:
            continue
        mine = [s for s in v["answers"] if s["hero"] and s["first_action"]]
        if not mine:
            continue
        s = mine[0]
        d = book.delta(h, h["hero_name"])
        cls = hero_cls(h)
        if d is None or cls is None:
            continue
        rows.append(dict(pos=s["pos"], act=s["act"], d=d, pre=book.delta_pre(h, h["hero_name"]), tier=tier_of(pct[cls]), cls=cls,
                         kind=v["kind"], size=f["to_bb"], callers=s["callers"], limpers=s["limpers"], to_call=s["to_call_bb"],
                         pot=s["pot_bb"], h=h, v=v))
    base = {"SB": -0.5, "BB": -1.0}
    for where, sel in (("不在盲注位", lambda r: r["pos"] not in ("SB", "BB")), ("小盲", lambda r: r["pos"] == "SB"), ("大盲", lambda r: r["pos"] == "BB")):
        rs = [r for r in rows if sel(r)]
        if not rs:
            continue
        b = base.get(rs[0]["pos"], 0.0)
        print(f"  -- {where}（{len(rs)} 次；弃牌的结果固定为 {b:+.1f}bb）")
        for t in TIER_NAMES:
            ts = [r for r in rs if r["tier"] == t]
            if not ts:
                continue
            c = Counter(r["act"] for r in ts)
            line = f"     {t:<12} n={len(ts):4d}  弃 {100 * c['fold'] / len(ts):5.1f}%  跟 {100 * c['call'] / len(ts):5.1f}%  3bet {100 * c['raise'] / len(ts):5.1f}%"
            for a, name in (("call", "跟注"), ("raise", "3bet")):
                xs = [r["d"] for r in ts if r["act"] == a]
                if len(xs) >= 3:
                    line += f"  | {name} {ev(xs)}"
            print(line)
        for a, name in (("call", "跟注"), ("raise", "3bet")):
            xs = [r["d"] for r in rs if r["act"] == a]
            if xs:
                m, se, n = mean_se(xs)
                print(f"     合计 {name} {ev(xs)}  相对弃牌 {m - b:+.2f}  抽水前 {sum(r['pre'] for r in rs if r['act'] == a) / n:+.2f}")
    bb = [r for r in rows if r["pos"] == "BB" and r["kind"] == "open"]
    print("  -- 大盲面对率先加注，按对方尺度和前面跟注人数")
    for sb in SIZES:
        for multi in (False, True):
            rs = [r for r in bb if size_bucket(r["size"]) == sb and (r["callers"] > 0) == multi]
            if len(rs) < 15:
                continue
            c = Counter(r["act"] for r in rs)
            need = sum(r["to_call"] / ((r["pot"] + r["to_call"]) * 0.91) for r in rs) / len(rs)
            xs = [r["d"] for r in rs if r["act"] == "call"]
            print(f"     加注到{sb:<5} {'已有人跟' if multi else '无人跟  '} n={len(rs):3d}  弃 {100 * c['fold'] / len(rs):5.1f}%  跟 {100 * c['call'] / len(rs):5.1f}%"
                  f"  3bet {100 * c['raise'] / len(rs):4.1f}%  跟注所需胜率(含抽水) {100 * need:4.1f}%  跟注结果 {ev(xs)}")
    # hero's 3-bets, split by what happened next
    tb = [r for r in rows if r["act"] == "raise" and r["kind"] == "open"]
    print(f"  -- hero 的 3bet（{len(tb)} 次）之后")
    c = Counter()
    res = defaultdict(list)
    for r in tb:
        v = r["v"]
        after = [s for s in v["spots"] if s["i"] > v["three"]["i"]] if v["three"] is not None and v["three"]["hero"] else None
        if after is None:
            c["不是第一个3bet"] += 1
            continue
        if any(s["act"] == "raise" for s in after):
            b = "被4bet"
        elif any(s["act"] == "call" for s in after):
            b = "被跟注"
        else:
            b = "全弃"
        c[b] += 1
        res[b].append(r["d"])
    n = sum(c.values())
    for b in ("全弃", "被跟注", "被4bet"):
        if c[b]:
            print(f"     {b:<5} {100 * c[b] / n:5.1f}%  每次 {ev(res[b])}")
    print(f"     合计每次 {ev([r['d'] for r in tb])}；3bet 的牌：" + "  ".join(f"{t} {sum(1 for r in tb if r['tier'] == t)}" for t in TIER_NAMES))
    return rows


# ---------------------------------------------------------------------------
# 6  limped pots
# ---------------------------------------------------------------------------
def sec_limped(book, since, pct, vs_rows):
    print("\n== 6 平跟（limp）池 ==")
    per = defaultdict(Counter)
    outcome = defaultdict(Counter)
    for h in book.hands:
        v = preflop_view(h)
        f = v["first"]
        if f is None or v["kind"] != "iso":
            continue
        nl = f["limpers"]
        key = "1个平跟者" if nl == 1 else "≥2个平跟者"
        per_bb = f["to_bb"]
        sb = "≤4bb" if per_bb <= 4.2 else ("4-6bb" if per_bb <= 6.2 else ">6bb")
        for s in v["answers"]:
            if s["hero"] or s["first_action"]:
                continue            # only the limpers themselves
            per[sb][s["act"]] += 1
            per["全部"][s["act"]] += 1
        o = "全弃" if v["steal"] else ("被再加注" if v["three"] is not None else "被跟注")
        outcome[(key, sb)][o] += 1
        outcome[(key, "全部")][o] += 1
    print("  -- 平跟者面对隔离加注（全部真人桌）")
    for sb in ("≤4bb", "4-6bb", ">6bb", "全部"):
        c = per[sb]
        n = sum(c.values())
        if n:
            print(f"     加注到{sb:<6} n={n:4d}  弃 {rate(c['fold'], n)}  跟 {100 * c['call'] / n:5.1f}%  再加注 {100 * c['raise'] / n:4.1f}%")
    print("  -- 每次隔离加注的结局")
    for key in ("1个平跟者", "≥2个平跟者"):
        for sb in ("≤4bb", "4-6bb", ">6bb", "全部"):
            c = outcome[(key, sb)]
            n = sum(c.values())
            if n >= 20:
                print(f"     {key} 加注到{sb:<6} n={n:4d}  全弃 {rate(c['全弃'], n)}  被跟注 {100 * c['被跟注'] / n:5.1f}%  被再加注 {100 * c['被再加注'] / n:4.1f}%")
    # hero in limped pots: first action
    rows = []
    for h in book.hands:
        if (h["ts"] or "") < since:
            continue
        v = preflop_view(h)
        mine = [s for s in v["spots"] if s["hero"] and s["first_action"]]
        if not mine or mine[0]["sit"] != "limped":
            continue
        s = mine[0]
        d = book.delta(h, h["hero_name"])
        cls = hero_cls(h)
        if d is None or cls is None:
            continue
        branch = None
        if s["act"] == "raise":
            branch = "全弃" if v["steal"] else ("被再加注" if v["three"] is not None else "被跟注")
        rows.append(dict(pos=s["pos"], act=s["act"], d=d, pre=book.delta_pre(h, h["hero_name"]), tier=tier_of(pct[cls]),
                         limpers=s["limpers"], size=s["to_bb"], branch=branch))
    print(f"  -- hero 面对平跟者的第一次行动（{since[:10]} 起，{len(rows)} 次）")
    for where, sel, b in (("不在盲注位", lambda r: r["pos"] not in ("SB", "BB"), 0.0), ("小盲", lambda r: r["pos"] == "SB", -0.5),
                          ("大盲", lambda r: r["pos"] == "BB", -1.0)):
        rs = [r for r in rows if sel(r)]
        if not rs:
            continue
        print(f"    {where}（{len(rs)} 次）")
        for t in TIER_NAMES:
            ts = [r for r in rs if r["tier"] == t]
            if not ts:
                continue
            c = Counter(r["act"] for r in ts)
            line = f"     {t:<12} n={len(ts):4d}  弃 {c['fold']:3d}  过牌 {c['check']:3d}  跟 {c['call']:3d}  加注 {c['raise']:3d}"
            xs = [r["d"] for r in ts if r["act"] == "raise"]
            if len(xs) >= 3:
                line += f"  | 加注 {ev(xs)}"
            xs = [r["d"] for r in ts if r["act"] == "check"]
            if len(xs) >= 3:
                line += f"  | 过牌 {ev(xs)}"
            print(line)
    iso = [r for r in rows if r["act"] == "raise"]
    print(f"  -- hero 的隔离加注合计（{len(iso)} 次）")
    for b in ("全弃", "被跟注", "被再加注"):
        xs = [r["d"] for r in iso if r["branch"] == b]
        if xs:
            print(f"     {b:<5} {100 * len(xs) / len(iso):5.1f}%  每次 {ev(xs)}")
    print(f"     合计每次 {ev([r['d'] for r in iso])}  抽水前 {sum(r['pre'] for r in iso) / max(1, len(iso)):+.2f}；"
          f"尺度 {dict(sorted(Counter(round(r['size']) for r in iso).items()))} bb")
    for nl, name in ((1, "1个平跟者"), (2, "≥2个平跟者")):
        xs = [r["d"] for r in iso if (r["limpers"] == 1) == (nl == 1)]
        if xs:
            print(f"     {name}  每次 {ev(xs)}")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("logs", nargs="+")
    ap.add_argument("--hero-since", default="2026-11-09", help="hero's own results use hands from here on")
    ap.add_argument("--raw", action="store_true", help="hero's results as they fell, without the all-in luck adjustment")
    args = ap.parse_args(argv)
    hands, _ = pflog.load(args.logs)
    pflog.validate(hands)
    hands = [h for h in hands if h.get("players") and usable(h) and human_table(h)]
    book = Book(hands, raw=args.raw)
    n_hero = sum(1 for h in hands if (h["ts"] or "") >= args.hero_since)
    print(f"真人桌 {len(hands)} 手（对手池的反应曲线用全部；hero 自己的收益只用 {args.hero_since[:10]} 起的 {n_hero} 手）")
    print("hero 的收益" + ("为实际结果" if args.raw else "已做全下运气修正（河牌前全下并摊牌的底池按胜率计，不按实际发牌计）") + "\n")
    pct = hand_tiers()
    sec_rake(book)
    sec_open_answers(book)
    opens_hero = sec_hero_opens(book, args.hero_since, pct)
    sec_three_bets(book, args.hero_since, pct, opens_hero)
    vs_rows = sec_vs_open(book, args.hero_since, pct)
    sec_limped(book, args.hero_since, pct, vs_rows)


if __name__ == "__main__":
    main()
