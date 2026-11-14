"""Ground truth that does not depend on the bot's own range model.

The server reports the winner's hand *type* (高牌/一对/两对/…) in ``hand_result.hand_combos``
even when the pot is won without showdown (verified: 136/136 hero non-showdown wins and
1101/1101 shown hands match eval7). Together with shown cards this gives, for every pot that
ended after the flop, the strength class of the *last aggressor* whether or not he was called —
i.e. an unbiased look at what pool bets are made of, and whether hero's folds were folds of
the best hand.

    .venv/bin/python -m analysis.truth pokerfate/logs/pokerfate.log [more logs ...]
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict

import eval7

from analysis import pflog
from analysis.features import fmt_rate, postflop_spots, size_bucket, usable, wilson

TYPE_ORDER = ["高牌", "一对", "两对", "三条", "顺子", "同花", "葫芦", "四条", "同花顺"]
TYPE_RANK = {t: i for i, t in enumerate(TYPE_ORDER)}
_EVAL7_TYPES = {"High Card": 0, "Pair": 1, "Two Pair": 2, "Trips": 3, "Straight": 4, "Flush": 5,
                "Full House": 6, "Quads": 7, "Straight Flush": 8}


def board_cards(h, upto: str) -> list:
    out = []
    for s in ("flop", "turn", "river"):
        out += h["board"].get(s, [])
        if s == upto:
            break
    return out


def type_rank(cards: list) -> int:
    """Hand-type rank (0 high card … 8 straight flush) of 3..7 cards."""
    if len(cards) >= 5:
        return _EVAL7_TYPES[eval7.handtype(eval7.evaluate([eval7.Card(c) for c in cards]))]
    counts = sorted(Counter(c[0] for c in cards).values(), reverse=True)
    if not counts:
        return 0
    if counts[0] == 4:
        return 7
    if counts[0] == 3:
        return 3
    if counts[0] == 2:
        return 2 if len(counts) > 1 and counts[1] == 2 else 1
    return 0


def label_rank(label: str):
    t = (label or "").split(" ")[0]
    return TYPE_RANK.get(t)


def final_aggression(h):
    """Describe how the hand ended postflop.

    Returns None if the hand ended preflop, else a dict with the last street, the last
    bet/raise on it (if any) and who folded / called afterwards.
    """
    post = [a for a in h["actions"] if a["street"] != "preflop"]
    if not post:
        return None
    last_street = post[-1]["street"]
    on_street = [a for a in post if a["street"] == last_street]
    aggr = None
    for a in on_street:
        if a["act"] == "raise":
            aggr = a
    if aggr is None:
        return {"street": last_street, "aggr": None}
    after = [a for a in on_street if a["i"] > aggr["i"]]
    return {
        "street": last_street, "aggr": aggr,
        "folders": [a for a in after if a["act"] == "fold"],
        "callers": [a for a in after if a["act"] == "call"],
        "first_bet": aggr["kind"] == "bet",
        "n_active": aggr["n_active"],
    }


def strength_class(tr: int, board_tr: int) -> str:
    """Coarse strength of a hand type relative to what the board alone gives everybody."""
    d = tr - board_tr
    if d <= 0:
        return "air(不超过公共牌)"
    if tr <= 1 or (board_tr >= 1 and d == 1 and tr <= 2):
        return "一对级"
    return "两对+"


def pool_bet_composition(hands, min_street="river"):
    """What are pool bets made of?  Last aggressor on the last street, called or not."""
    rows = []
    for h in hands:
        fa = final_aggression(h)
        if not fa or not fa["aggr"]:
            continue
        a = fa["aggr"]
        if a["hero"]:
            continue
        st = fa["street"]
        res = h["result"]
        b = board_cards(h, st)
        btr = type_rank(b)
        who = a["who"]
        shown = res["showdown_hands"].get(who)
        tr = None
        src = None
        if shown and len(shown) == 2 and st == "river":
            tr = type_rank(shown + b)
            src = "shown"
        elif not fa["callers"] and who in res["winners"]:
            tr = label_rank(res["hand_combos"].get(who, ""))
            src = "uncalled"
        elif shown and len(shown) == 2:
            tr = type_rank(shown + b)  # all-in before the river: strength at the time of the bet
            src = "shown_allin"
        if tr is None:
            continue
        frac = a.get("size_pot")
        rows.append(dict(key=h["key"], street=st, who=who, kind=a["kind"], frac=frac, hu=fa["n_active"] == 2,
                         tr=tr, btr=btr, cls=strength_class(tr, btr), src=src, called=bool(fa["callers"]),
                         hero_folded=any(x["hero"] for x in fa["folders"]),
                         hero_called=any(x["hero"] for x in fa["callers"]), allin=bool(a.get("allin")),
                         pot_bb=a["pot_before"] / h["bb"]))
    return rows


def hero_fold_truth(hands):
    """For hero folds that ended the hand: was hero's hand type better than the winner's?"""
    rows = []
    for h in hands:
        fa = final_aggression(h)
        if not fa or not fa["aggr"] or fa["aggr"]["hero"]:
            continue
        hf = [x for x in fa["folders"] if x["hero"]]
        if not hf:
            continue
        a = fa["aggr"]
        res = h["result"]
        st = fa["street"]
        b = board_cards(h, st)
        if fa["callers"] or len(res["winners"]) != 1 or a["who"] not in res["winners"]:
            continue  # someone else continued; winner's type is not the bettor's uncalled type
        vt = label_rank(res["hand_combos"].get(a["who"], ""))
        if vt is None:
            continue
        ht = type_rank(h["hole"] + b)
        btr = type_rank(b)
        d = hf[0]["dec"]
        pot, tc = d["pot"], d["to_call"]
        need = tc / ((pot + tc) * 0.91) if pot + tc > 0 else None
        rows.append(dict(key=h["key"], street=st, hu=fa["n_active"] == 2, hero_t=ht, vil_t=vt, board_t=btr,
                         verdict=("ahead" if ht > vt else ("behind" if ht < vt else "same_type")),
                         eq=d.get("equity"), need=need, pot_bb=pot / h["bb"], tc_bb=tc / h["bb"],
                         src=d.get("decision_source"), kind=a["kind"], frac=a.get("size_pot"),
                         vil_cls=strength_class(vt, btr), hero_cls=strength_class(ht, btr),
                         bucket=d.get("hero_bucket"), hand=h["hole"], board=b))
    return rows


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("logs", nargs="+")
    args = ap.parse_args(argv)
    hands, _ = pflog.load(args.logs)
    pflog.validate(hands)
    report(hands)


def report(hands):
    hands = [h for h in hands if h.get("result") and not h.get("street_mismatch")]
    print(f"hands {len(hands)}")
    rows = pool_bet_composition(hands)
    print(f"\n== 对手池“最后一次下注/加注”的牌力构成（被跟注摊牌 + 无人跟注时的赢家牌型），n={len(rows)} ==")
    for st in ("flop", "turn", "river"):
        for kind in ("bet", "raise"):
            for hu in (True, False):
                rs = [r for r in rows if r["street"] == st and r["kind"] == kind and r["hu"] == hu]
                if not rs:
                    continue
                c = Counter(r["cls"] for r in rs)
                n = len(rs)
                called = sum(1 for r in rs if r["called"])
                print(f"  {st:<5} {kind:<5} {'单挑' if hu else '多人'} n={n:4d} 被跟注={called:4d} | "
                      + "  ".join(f"{k}: {fmt_rate(c[k], n)}" for k in ("air(不超过公共牌)", "一对级", "两对+")))
    print("\n  -- 河牌首次下注（单挑），按尺度")
    for sb in ("≤40%", "40-70%", "70-105%", ">105%"):
        rs = [r for r in rows if r["street"] == "river" and r["kind"] == "bet" and r["hu"] and size_bucket(r["frac"]) == sb]
        if rs:
            c = Counter(r["cls"] for r in rs)
            print(f"     {sb:<8} n={len(rs):4d} | " + "  ".join(f"{k}: {fmt_rate(c[k], len(rs))}" for k in ("air(不超过公共牌)", "一对级", "两对+")))
    fr = hero_fold_truth(hands)
    print(f"\n== hero 弃牌后对手独赢：hero 当时的牌型 vs 对手牌型，n={len(fr)} ==")
    for st in ("flop", "turn", "river"):
        for hu in (True, False):
            rs = [r for r in fr if r["street"] == st and r["hu"] == hu]
            if not rs:
                continue
            c = Counter(r["verdict"] for r in rs)
            n = len(rs)
            print(f"  {st:<5} {'单挑' if hu else '多人'} n={n:3d}  hero领先 {fmt_rate(c['ahead'], n)}  同牌型 {c['same_type']}  落后 {c['behind']}")


if __name__ == "__main__":
    main()
