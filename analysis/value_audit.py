"""Missed-value audit on the river (heads-up), using showdown truth only.

Step 1 (pool model, hero-independent): how does a pool player who CHECKED the river respond
        to a bet, by his own strength class?  Uses
          D_check(k)  class mix of river checkers seen at check-check showdowns,
          D_call(k)   class mix of checkers who called a bet (shown at showdown),
          P(call), P(raise), P(fold) after checking.
        P(call | k) = P(call)·D_call(k) / D_check(k)       (Bayes; bettor's choice to bet is
        independent of the checker's cards).
Step 2 (hero): every hero river check-behind (in position, closing the action) that reached
        showdown has the villain's real hand.  EV gain of a bet of size b over checking:
          villain worse & calls :  +b·(2·0.91 − 1) = +0.82·b   (9% rake on the extra 2b)
          villain better & calls/raises : −b
          villain folds : 0  (hero would have won the same pot at showdown)

    .venv/bin/python -m analysis.value_audit <log> [<log> ...] [--since ISO] [--bet 0.5]
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict

import eval7

from analysis import pflog
from analysis.features import fmt_rate, mean_se, postflop_spots, size_bucket, usable
from analysis.truth import board_cards, strength_class, type_rank

KEEP = 0.91
CLS = ("air(不超过公共牌)", "一对级", "两对+")


def score(cards, board):
    return eval7.evaluate([eval7.Card(c) for c in cards + board])


def river_hu_lines(hands):
    """Yield (hand, river spots) for hands that were heads-up on the river with a full board."""
    for h in hands:
        if not h.get("result") or h.get("street_mismatch") or h["last_street"] != "river":
            continue
        ss = [s for s in postflop_spots(h) if s["street"] == "river"]
        if not ss or ss[0]["n_active"] != 2:
            continue
        b = board_cards(h, "river")
        if len(b) != 5:
            continue
        yield h, ss, b


def pool_response_model(hands, exclude_hero_checker=True):
    d_check = Counter()   # class of the first-to-act checker at check-check showdowns
    d_call = defaultdict(Counter)
    d_raise = defaultdict(Counter)
    resp = defaultdict(Counter)
    for h, ss, b in river_hu_lines(hands):
        if len(ss) < 2 or ss[0]["act"] != "check":
            continue
        checker = ss[0]
        if checker["hero"] and exclude_hero_checker:
            continue
        btr = type_rank(b)
        shown = h["result"]["showdown_hands"].get(checker["who"])
        cls = strength_class(type_rank(shown + b), btr) if shown and len(shown) == 2 else None
        second = ss[1]
        if second["act"] == "check":
            if cls:
                d_check[cls] += 1
            continue
        if second["kind"] != "bet" or len(ss) < 3:
            continue
        r = ss[2]
        sz = size_bucket(second.get("size_pot"))
        resp[sz][r["act"]] += 1
        resp["all"][r["act"]] += 1
        if r["act"] == "call" and cls:
            d_call[sz][cls] += 1
            d_call["all"][cls] += 1
        if r["act"] == "raise" and cls:
            d_raise["all"][cls] += 1
    return d_check, d_call, d_raise, resp


def continue_probabilities(hands) -> tuple[dict, dict]:
    """P(villain continues | his strength class) on the river, heads-up, pool players only.

    Returns ``(after_check, facing_lead)``:
      after_check  - villain checked first and then faces a bet (hero in position);
      facing_lead  - villain is in position and faces a lead (hero out of position). The
                     in-position player's whole range is approximated as 40% "bets when
                     checked to" (pool river bet composition) + 60% "checks behind".
    Both are Bayes inversions of showdown class mixes; they reproduce the measured overall
    continue rate by construction.
    """
    from analysis.truth import pool_bet_composition  # local import: avoids a cycle at module load

    hands = [h for h in hands if h.get("result")]
    d_check, d_call, d_raise, resp = pool_response_model(hands)
    n_chk = sum(d_check.values())
    c = resp["all"]
    n = sum(c.values())
    nc, nr = sum(d_call["all"].values()), sum(d_raise["all"].values())
    after_check = {}
    for k in CLS:
        prior = d_check[k] / n_chk if n_chk else 0.0
        post = (c["call"] / n) * (d_call["all"][k] / nc) + ((c["raise"] / n) * (d_raise["all"][k] / nr) if nr else 0.0)
        after_check[k] = min(1.0, post / prior) if prior > 0 else 0.0

    ip_resp, ip_call, ip_raise, ip_back = Counter(), Counter(), Counter(), Counter()
    for h, ss, b in river_hu_lines(hands):
        if len(ss) < 2:
            continue
        btr = type_rank(b)
        first, second = ss[0], ss[1]

        def cls_of(who):
            shown = h["result"]["showdown_hands"].get(who)
            return strength_class(type_rank(shown + b), btr) if shown and len(shown) == 2 else None

        if first["kind"] == "bet" and not second["hero"]:
            ip_resp[second["act"]] += 1
            k = cls_of(second["who"])
            if k and second["act"] == "call":
                ip_call[k] += 1
            if k and second["act"] == "raise":
                ip_raise[k] += 1
        if first["act"] == "check" and second["act"] == "check" and not second["hero"]:
            k = cls_of(second["who"])
            if k:
                ip_back[k] += 1
    comp = Counter(r["cls"] for r in pool_bet_composition(hands)
                   if r["street"] == "river" and r["kind"] == "bet" and r["hu"])
    nb, na = sum(comp.values()), sum(ip_back.values())
    n = sum(ip_resp.values())
    facing_lead = {}
    for k in CLS:
        whole = 0.40 * comp[k] / nb + 0.60 * ip_back[k] / na
        post = (ip_resp["call"] / n) * (ip_call[k] / sum(ip_call.values())) \
            + (ip_resp["raise"] / n) * (ip_raise[k] / sum(ip_raise.values()))
        facing_lead[k] = min(1.0, post / whole) if whole > 0 else 0.0
    return after_check, facing_lead


def bet_gain_vs_showdown(bet_bb: float, ahead: float, p_continue: float) -> float:
    """EV of a river bet relative to checking the hand down, given the villain's real hand:
    worse hand continues -> +0.82*b (9% rake on the extra 2b); better hand continues -> -b."""
    if ahead == 1:
        return p_continue * (2 * KEEP - 1) * bet_bb
    if ahead == 0:
        return -p_continue * bet_bb
    return -p_continue * bet_bb * (1 - KEEP)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("logs", nargs="+")
    ap.add_argument("--since", default="", help="only score hero decisions from this timestamp (pool model uses all logs)")
    ap.add_argument("--bet", type=float, default=0.5, help="hypothetical value-bet size as a fraction of the pot")
    args = ap.parse_args(argv)
    hands, _ = pflog.load(args.logs)
    pflog.validate(hands)
    d_check, d_call, d_raise, resp = pool_response_model(hands)
    n_chk = sum(d_check.values())
    print(f"== 对手池：河牌先过牌的一方（单挑）==  check-check 摊牌 n={n_chk}")
    print("   过牌范围构成: " + "  ".join(f"{k} {fmt_rate(d_check[k], n_chk)}" for k in CLS))
    for sz in ("≤40%", "40-70%", "70-105%", ">105%", "all"):
        c = resp[sz]
        n = sum(c.values())
        if n:
            print(f"   过牌后面对下注[{sz}] n={n}: 弃 {100 * c['fold'] / n:4.1f}%  跟 {100 * c['call'] / n:4.1f}%  加注 {100 * c['raise'] / n:4.1f}%")
    c = resp["all"]
    n = sum(c.values())
    p_call, p_raise = c["call"] / n, c["raise"] / n
    nc = sum(d_call["all"].values())
    nr = sum(d_raise["all"].values())
    print(f"   跟注者构成(摊牌 n={nc}): " + "  ".join(f"{k} {100 * d_call['all'][k] / nc:4.1f}%" for k in CLS))
    if nr:
        print(f"   加注者构成(摊牌 n={nr}): " + "  ".join(f"{k} {100 * d_raise['all'][k] / nr:4.1f}%" for k in CLS))
    p_cont = {}
    for k in CLS:
        prior = d_check[k] / n_chk
        post_call = d_call["all"][k] / nc
        post_raise = (d_raise["all"][k] / nr) if nr else 0.0
        p_cont[k] = min(1.0, (p_call * post_call + p_raise * post_raise) / prior) if prior > 0 else 0.0
    print("   ⇒ P(继续 | 过牌者牌力): " + "  ".join(f"{k} {100 * p_cont[k]:4.1f}%" for k in CLS))

    # ---- hero river checks
    rows = []
    for h, ss, b in river_hu_lines(hands):
        if not (h.get("dealt") and (h["ts"] or "") >= args.since):
            continue
        hero = h["hero_name"]
        hs = [s for s in ss if s["hero"]]
        if not hs:
            continue
        s = hs[0]
        if s["facing"] or s["bets_before"] > 0:
            continue
        btr = type_rank(b)
        ht = type_rank(h["hole"] + b)
        hcls = strength_class(ht, btr)
        ip = s["n_acted"] >= 1
        shown = None
        for n, c in h["result"]["showdown_hands"].items():
            if n != hero and len(c) == 2:
                shown = c
        row = dict(key=h["key"], ip=ip, act=s["kind"], hcls=hcls, pot=s["pot_bb"], src=s["dec"].get("decision_source"),
                   eq=s["dec"].get("equity"), cfr=s["dec"].get("realtime_cfr"), frac=s.get("size_pot"),
                   sd=h["hero_at_showdown"], hand=h["hole"], board=b, shown=shown, delta=h["delta_bb"],
                   rule_engine_shadow=s["dec"].get("rule_engine_shadow_action"), bucket=s["dec"].get("hero_bucket"))
        if shown:
            hs_, vs_ = score(h["hole"], b), score(shown, b)
            row["ahead"] = 1 if hs_ > vs_ else (0 if hs_ < vs_ else 0.5)
            row["vcls"] = strength_class(type_rank(shown + b), btr)
        rows.append(row)
    print(f"\n== hero 河牌（单挑、无人下注时）决策 n={len(rows)}  since={args.since or '-'} ==")
    for ip in (True, False):
        for hcls in CLS:
            rs = [r for r in rows if r["ip"] == ip and r["hcls"] == hcls]
            if not rs:
                continue
            nb = sum(1 for r in rs if r["act"] == "bet")
            print(f"  {'有位置(对手已过牌)' if ip else '无位置(先行动)'} hero={hcls:<12} n={len(rs):3d} 下注 {fmt_rate(nb, len(rs))}")
    print(f"\n== 有位置过牌到摊牌（check-behind）：假设改为下注 {args.bet:.0%} 底池的 EV 增量 ==")
    tot_gain = 0.0
    for hcls in CLS:
        rs = [r for r in rows if r["ip"] and r["act"] == "check" and r["hcls"] == hcls and r.get("shown")]
        if not rs:
            continue
        gains = []
        for r in rs:
            b_ = args.bet * r["pot"]
            pc = p_cont[r["vcls"]]
            if r["ahead"] == 1:
                g = pc * (2 * KEEP - 1) * b_
            elif r["ahead"] == 0:
                g = -pc * b_
            else:
                g = -pc * b_ * (1 - KEEP)
            gains.append(g)
        m, se, n = mean_se(gains)
        ahead = sum(r["ahead"] for r in rs)
        vc = Counter(r["vcls"] for r in rs)
        tot_gain += sum(gains)
        print(f"  hero={hcls:<12} n={n:3d} 摊牌领先 {ahead:.1f}/{n} ({100 * ahead / n:.0f}%) 对手牌力: " + " ".join(f"{k[:3]}={vc[k]}" for k in CLS)
              + f" | 平均底池 {sum(r['pot'] for r in rs) / n:.1f}bb | EV增量 合计 {sum(gains):+.1f}bb, 每次 {m:+.2f} ± {1.96 * se if se == se else 0:.2f}bb")
    nh = sum(1 for h in hands if usable(h) and (h["ts"] or "") >= args.since)
    print(f"  合计 {tot_gain:+.1f}bb / {nh} 手 = {100 * tot_gain / nh:+.2f} bb/100")
    return rows, p_cont


if __name__ == "__main__":
    main()
