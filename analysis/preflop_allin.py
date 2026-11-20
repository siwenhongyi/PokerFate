"""Preflop calls that end the betting: are they priced right, and what the pricing rests on.

When a call leaves hero nothing to bet against anyone still in the hand, the hand is decided at
showdown and the only question is the price:  equity x 0.91 x (pot + call)  against  call.
``PreflopStrategy`` prices those spots (``showdown_call_ev``).  This tool measures the inputs and
audits the result on logs.

    # logs only: audit of hero's preflop calls / folds against a raise, and how often the players
    # still to act behind a raise continue (the pricing's continue rates)
    .venv/bin/python -m analysis.preflop_allin pokerfate/logs/archive/2026-11-*.pokerfate.bak.log pokerfate/logs/pokerfate.log

    # with extractor rows (bucket mode): is the tracker's range for a shover right?  (the pricing's
    # equity margin)  Shown shoves are an unbiased sample: a called shove is shown whatever it is.
    .venv/bin/python -m analysis.preflop_allin <logs> --rows rows.jsonl [more_rows.jsonl ...]

Sections
  1  audit: big calls below the price, cheap folds with most of the remaining stack at stake
  2  continue rate behind a raise, by raise size and by what the player did earlier in the hand
  3  (--rows) predicted against actual equity of a panel of hands versus the shoves shown
"""
from __future__ import annotations

import argparse
import json
import math
import random
import re
from collections import defaultdict

from analysis import pflog
from analysis.features import usable, wilson

RAKE = 0.09
_PRICED = re.compile(r"showdown_price:\w+ .*?eq=(\d+)%")
PANEL = ("QQ", "JJ", "TT", "99", "88", "77", "55", "22", "AKs", "AKo", "AQs", "AQo", "AJs", "ATs",
         "A5s", "KQs", "KQo", "KJs", "QJs", "JTs", "T9s", "87s", "A9o", "KTo")


# ── 1. audit ────────────────────────────────────────────────────────────────────────────

def priced_decisions(hands):
    """Hero's preflop calls and folds against a raise, with the raked break-even equity and the
    equity the bot logged: against every opponent still in (its own range each), or, where the
    call was decided on its price, against the players in for the raise."""
    for h in hands:
        bb = h["bb"]
        for a in h["actions"]:
            if a["street"] != "preflop" or not a["hero"] or a["act"] not in ("call", "fold") or a["to_call"] <= 0:
                continue
            dec = a.get("dec") or {}
            if dec.get("equity") is None:
                continue
            stack, raw = a["stack_before"], a["to_call"]
            call = min(raw, stack)
            pot = a["pot_before"] - max(0.0, raw - call)          # chips above hero's all-in cannot be won
            if call <= 0 or pot <= 0:
                continue
            eq = float(dec["equity"])
            reason = dec.get("preflop_expand_reason") or ""
            priced = _PRICED.search(reason)
            if priced:                      # decided on its price: the equity that was priced is the one to audit
                eq = int(priced.group(1)) / 100.0
            yield {
                "hand": h["hand"], "ts": h["ts"][:16], "cards": "".join(h.get("hole") or []), "act": a["act"],
                "call_bb": call / bb, "pot_bb": pot / bb, "need": call / ((1 - RAKE) * (pot + call)), "eq": eq,
                "ev_bb": (eq * (1 - RAKE) * (pot + call) - call) / bb, "commit": call / stack if stack else 1.0,
                "facing": dec.get("facing_action"), "reason": reason[:70], "delta": h["delta_bb"],
            }


def audit(hands, show: int = 12) -> None:
    rows = list(priced_decisions(hands))
    calls = [r for r in rows if r["act"] == "call"]
    folds = [r for r in rows if r["act"] == "fold"]
    big = [r for r in calls if r["call_bb"] >= 15]
    bad = [r for r in big if r["eq"] < r["need"] - 0.05]
    cheap = [r for r in folds if r["need"] <= 0.25 and r["commit"] >= 0.6 and r["call_bb"] >= 2]
    print(f"\n== 1. 审计：hero 面对加注的翻前跟注 {len(calls)} 次、弃牌 {len(folds)} 次（{len(hands)} 手）")
    print(f"  15bb 以上的跟注 {len(big)} 次；记录的胜率比保本线低 5 点以上的 {len(bad)} 次，"
          f"按记录的胜率合计 {sum(r['ev_bb'] for r in bad):+.1f}bb（实际结果合计 {sum(r['delta'] for r in bad):+.1f}bb）")
    for r in sorted(bad, key=lambda r: r["ev_bb"])[:show]:
        print(f"     {r['ts']} #{r['hand']:<5d} {r['cards']:5s} 跟 {r['call_bb']:5.1f}bb 底池 {r['pot_bb']:6.1f} "
              f"保本 {100 * r['need']:3.0f}% 胜率 {100 * r['eq']:3.0f}% EV {r['ev_bb']:+6.1f}  {r['facing']} {r['reason']}")
    print(f"  要投入剩余筹码六成以上、保本线不到 25% 却弃牌 {len(cheap)} 次，"
          f"按记录的胜率放弃的 EV 合计 {sum(max(0.0, r['ev_bb']) for r in cheap):+.1f}bb")
    for r in sorted(cheap, key=lambda r: -r["ev_bb"])[:show]:
        print(f"     {r['ts']} #{r['hand']:<5d} {r['cards']:5s} 弃；跟 {r['call_bb']:5.1f}bb 底池 {r['pot_bb']:6.1f} "
              f"保本 {100 * r['need']:3.0f}% 胜率 {100 * r['eq']:3.0f}% 放弃 {r['ev_bb']:+6.1f}  {r['facing']} {r['reason']}")


# ── 2. continue rate behind a raise ─────────────────────────────────────────────────────

EARLIER = (("raised", "加过注"), ("called", "跟过/平跟过"), ("none", "还没动作"))


def continue_decisions(hands):
    """One row per player still to act behind a preflop raise (hero's own decisions left out):
    the raise, what the player had done earlier in the hand, and whether he continued."""
    for h in hands:
        bb = h["bb"]
        acts = [a for a in h["actions"] if a["street"] == "preflop"]
        earlier = {}
        for i, a in enumerate(acts):
            if a["act"] == "raise":
                level = a.get("to") or a["amt"]
                seen, callers = {a["who"]}, 0
                for b in acts[i + 1:]:
                    if b["who"] not in seen:
                        seen.add(b["who"])
                        if not b["hero"]:
                            yield {"day": h["ts"][:10], "to_bb": level / bb, "allin": a["add"] >= a["stack_before"] - 1e-6,
                                   "earlier": earlier.get(b["who"], "none"), "callers": callers,
                                   "go": b["act"] in ("call", "raise")}
                        callers += b["act"] == "call"
                    if b["act"] == "raise" and (b.get("to") or b["amt"]) > level + 1e-6:
                        break
                earlier[a["who"]] = "raised"
            elif a["act"] == "call":
                earlier.setdefault(a["who"], "called")


SIZES = ("small", "medium", "big")
FLAT_RATES_BEFORE = (0.30, 0.49)        # what the pricing used until 2026-11-16: 20bb and more / smaller


def _continue_model(rows, caller_effect: bool = True):
    """One logistic model over the decisions: a level per (raise size, earlier action) and, with
    ``caller_effect``, what a caller in front changes for players who had called and for players
    who had not acted (for players who had raised it changes nothing measurable).
    Returns the weights: 9 levels, then the two caller effects in log-odds."""
    import numpy as np

    earlier = [name for name, _ in EARLIER]
    x = np.zeros((len(rows), 11))
    y = np.array([float(r["go"]) for r in rows])
    for i, r in enumerate(rows):
        e = earlier.index(r["earlier"])
        x[i, SIZES.index(r["size"]) * 3 + e] = 1.0
        if caller_effect and e and r["callers"] > 0:
            x[i, 8 + e] = 1.0
    w = np.zeros(x.shape[1])
    for _ in range(60):                                   # Newton steps; a touch of ridge keeps empty cells finite
        prob = 1.0 / (1.0 + np.exp(-x @ w))
        hess = (x * (prob * (1.0 - prob))[:, None]).T @ x + 1e-3 * np.eye(len(w))
        w -= np.linalg.solve(hess, x.T @ (prob - y) + 1e-3 * w)
    return [float(v) for v in w]


def _continue_probability(w, size: str, earlier: str, caller_in_front: bool) -> float:
    e = [name for name, _ in EARLIER].index(earlier)
    z = w[SIZES.index(size) * 3 + e] + (w[8 + e] if e and caller_in_front else 0.0)
    return 1.0 / (1.0 + math.exp(-z))


def fit_continue_rates(rows):
    """Continue rate once somebody has called the raise - which is where the pricing stands:
    hero's own call comes first.  Returns ({size: {earlier: rate}}, the two caller effects)."""
    w = _continue_model(rows)
    table = {size: {name: _continue_probability(w, size, name, True) for name, _ in EARLIER} for size in SIZES}
    return table, (w[9], w[10])


def left_out_log_loss(rows) -> dict:
    """How well each description predicts decisions it has not seen: fit on all days but one, score
    that day's decisions with a caller in front, for every day in turn."""
    loss = {"两个固定比例（原来）": [], "按尺寸 × 之前的动作": [], "再加上前面有人跟注的影响": []}
    for day in sorted({r["day"] for r in rows}):
        test = [r for r in rows if r["day"] == day and r["callers"] > 0]
        train = [r for r in rows if r["day"] != day]
        if not test or not train:
            continue
        plain, full = _continue_model(train, caller_effect=False), _continue_model(train)
        for r in test:
            guesses = (FLAT_RATES_BEFORE[0] if r["size"] == "big" else FLAT_RATES_BEFORE[1],
                       _continue_probability(plain, r["size"], r["earlier"], False),
                       _continue_probability(full, r["size"], r["earlier"], True))
            for name, guess in zip(loss, guesses):
                loss[name].append(-math.log(min(max(guess if r["go"] else 1.0 - guess, 1e-4), 1.0)))
    return {name: (sum(v) / len(v), len(v)) for name, v in loss.items() if v}


def continue_rate(hands) -> None:
    """The table the pricing uses (``preflop.SHOWDOWN_CONTINUE_RATE``), measured again."""
    from pokerfate.strategy.preflop import SHOWDOWN_CONTINUE_RATE, SHOWDOWN_RAISE_SIZE_BB

    small, big = SHOWDOWN_RAISE_SIZE_BB
    labels = {"small": f"加到 {small:g}bb 以下", "medium": f"{small:g}bb 到 {big:g}bb", "big": f"{big:g}bb 及以上"}
    rows = list(continue_decisions(hands))
    for r in rows:
        r["size"] = "big" if r["to_bb"] >= big else "medium" if r["to_bb"] >= small else "small"

    def cells(pick) -> str:
        out = ""
        for e, _ in EARLIER:
            chosen = [r["go"] for r in rows if r["earlier"] == e and pick(r)]
            n, go = len(chosen), sum(chosen)
            out += f"{(f'{100 * go / n:3.0f}% ({go}/{n})' if n else '  - (0/0)'):<24s}"
        return out

    head = "".join(f"{name:<22s}" for _, name in EARLIER)
    print(f"\n== 2. 翻前有人加注之后，后面还没行动的人继续（跟注或再加注）的比例（{len(rows)} 次决定）")
    print(f"  {'加注尺寸':<12s}{head}")
    for size in SIZES:
        print(f"  {labels[size]:<14s}{cells(lambda r: r['size'] == size)}")
    print("  其中前面已经有人跟注了这个加注的（定价时 hero 的跟注在前，属于这种情况）：")
    for size in SIZES:
        print(f"  {labels[size]:<14s}{cells(lambda r: r['size'] == size and r['callers'] > 0)}")
    print(f"  核对（不进定价）：{labels['big']}·全下    {cells(lambda r: r['size'] == 'big' and r['allin'])}")
    print(f"  {'':<18s}{labels['big']}·非全下  {cells(lambda r: r['size'] == 'big' and not r['allin'])}")
    table, (called_shift, none_shift) = fit_continue_rates(rows)
    print(f"  拟合（每格一个水平；有人已跟注时，跟过的人 {called_shift:+.2f}、没动作的人 {none_shift:+.2f} 对数几率）"
          "→ 有人已跟注时的比例，括号里是定价现在用的：")
    for size in SIZES:
        print(f"  {labels[size]:<14s}" + "".join(
            f"{f'{100 * table[size][e]:3.0f}% ({100 * SHOWDOWN_CONTINUE_RATE[size][e]:.0f}%)':<24s}" for e, _ in EARLIER))
    print("  留一天验证（用其余各天拟合，预测这一天里前面已有人跟注的决定；对数损失越低越准）：")
    for name, (value, n) in left_out_log_loss(rows).items():
        print(f"    {name:<16s} {value:.4f}  （{n} 次决定）")


# ── 3. equity against shown shoves ──────────────────────────────────────────────────────

def _class_combos(cls: str):
    suits = "cdhs"
    a, b = cls[0], cls[1]
    if len(cls) == 2:
        return [(a + s1, b + s2) for i, s1 in enumerate(suits) for s2 in suits[i + 1:]]
    if cls[2] == "s":
        return [(a + s, b + s) for s in suits]
    return [(a + s1, b + s2) for s1 in suits for s2 in suits if s1 != s2]


def _showdown(hero, villain, rng, boards: int) -> float:
    import eval7

    deck = [eval7.Card(r + s) for r in "23456789TJQKA" for s in "cdhs"]
    hc, vc = [eval7.Card(c) for c in hero], [eval7.Card(c) for c in villain]
    dead = set(hero) | set(villain)
    rest = [c for c in deck if str(c) not in dead]
    total = 0.0
    for _ in range(boards):
        board = rng.sample(rest, 5)
        x, y = eval7.evaluate(hc + board), eval7.evaluate(vc + board)
        total += 1.0 if x > y else 0.5 if x == y else 0.0
    return total / boards


def shove_equity(row_paths, seed: int = 7) -> None:
    """Predicted (tracker's range for the shover) against actual (cards shown) equity of PANEL.

    The preflop range is constant inside each preflop-strength bin, so the prediction is
    ``sum_b share[b] * equity(hand vs a uniform draw from bin b)``.
    """
    import numpy as np
    from pokerfate.strategy.range_v2 import hand_combo_map as hcm
    from pokerfate.strategy.range_v2.fitted_likelihood import PREFLOP_BINS, preflop_bin_index

    rng = random.Random(seed)
    shoves = []
    for path in row_paths:
        with open(path, encoding="utf-8") as f:
            for line in f:
                if '"preflop_label"' not in line:
                    continue
                r = json.loads(line)
                share = (r.get("layers") or {}).get("floor")
                if (r.get("preflop_label") not in ("open", "reraise") or not share or not r.get("actual_cards")
                        or float((r.get("features") or {}).get("size_shove") or 0.0) < 0.5):
                    continue
                shoves.append((np.array([share.get(b, 0.0) for b in PREFLOP_BINS]), tuple(r["actual_cards"]),
                               str(r.get("player_uid")), r["preflop_label"]))
    print(f"\n== 3. 亮牌的翻前全下 / 超大加注 {len(shoves)} 次（{len({s[2] for s in shoves})} 个玩家；"
          f"率先加注型 {sum(s[3] == 'open' for s in shoves)}，再加注型 {sum(s[3] == 'reraise' for s in shoves)}）")
    if len(shoves) < 10:
        print("  太少，不报告")
        return
    bins = preflop_bin_index()
    by_bin = defaultdict(list)
    for i, (c1, c2) in enumerate(hcm.ALL_COMBOS):
        by_bin[int(bins[i])].append((str(hcm.int_to_card(c1)), str(hcm.int_to_card(c2))))
    cache = {}

    def actual(cls, cards):
        if (cls, cards) not in cache:
            free = [h for h in _class_combos(cls) if not set(h) & set(cards)]
            cache[(cls, cards)] = sum(_showdown(h, cards, rng, 600) for h in free[:4]) / len(free[:4]) if free else None
        return cache[(cls, cards)]

    print(f"  {'手牌':5s} {'预测%':>6s} {'实际%':>6s} {'预测-实际':>9s}  (标准误，按玩家聚类)")
    gaps = []
    for cls in PANEL:
        hero = _class_combos(cls)[0]
        vs_bin = np.array([
            sum(_showdown(hero, rng.choice([v for v in by_bin[b] if not set(v) & set(hero)]), rng, 1) for _ in range(2000)) / 2000
            for b in range(len(PREFLOP_BINS))
        ])
        pred, act, who = [], [], []
        for share, cards, uid, _label in shoves:
            a = actual(cls, cards)
            if a is not None:
                pred.append(float(share @ vs_bin) / float(share.sum())); act.append(a); who.append(uid)
        gap = np.array(pred) - np.array(act)
        _, idx = np.unique(np.array(who), return_inverse=True)
        sums = np.bincount(idx, weights=gap - gap.mean())
        se = math.sqrt(len(sums) / (len(sums) - 1) * float((sums ** 2).sum())) / len(gap) if len(sums) > 1 else 0.0
        gaps.append(float(gap.mean()))
        print(f"  {cls:5s} {100 * np.mean(pred):6.1f} {100 * np.mean(act):6.1f} {100 * gap.mean():+9.1f}  ({100 * se:.1f})")
    print(f"  全部手牌平均：预测-实际 {100 * sum(gaps) / len(gaps):+.1f} 点（{100 * min(gaps):+.1f} ~ {100 * max(gaps):+.1f}）")


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("logs", nargs="*")
    ap.add_argument("--rows", nargs="*", default=[], help="bucket-mode extractor rows (scripts.extract_range_calibration_rows_parallel)")
    args = ap.parse_args(argv)
    if args.logs:
        hands, _ = pflog.load(args.logs)
        pflog.validate(hands)
        hands = [h for h in hands if usable(h)]
        print(f"可用手数 {len(hands)}  时间 {hands[0]['ts'][:19]} → {hands[-1]['ts'][:19]}")
        audit(hands)
        continue_rate(hands)
    if args.rows:
        shove_equity(args.rows)


if __name__ == "__main__":
    main()
