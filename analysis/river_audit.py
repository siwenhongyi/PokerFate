"""River decision audit against ground truth (showdowns + winner hand types).

River has no future cards, so every hero river decision can be scored exactly once the
villain's strength is known:
  * hero folds  → villain wins uncalled → villain's hand TYPE is in hand_combos;
                  hero wins the counterfactual call if his type is higher (1), loses if lower (0),
                  same type counted 0.5 (unknown kicker / pair rank).
  * hero calls  → showdown → real result.
EV(call) = w · 0.91 · (pot + to_call) − to_call   (bb, relative to folding).

    .venv/bin/python -m analysis.river_audit <log> [<log> ...] [--since ISO] [--street river|turn|flop]
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict

from analysis import pflog
from analysis.features import fmt_rate, mean_se, postflop_spots, size_bucket
from analysis.truth import board_cards, label_rank, strength_class, type_rank, TYPE_ORDER

KEEP = 0.91


def collect(hands, street="river"):
    rows = []
    for h in hands:
        if not (h.get("result") and h.get("dealt")) or h.get("street_mismatch"):
            continue
        res = h["result"]
        bb = h["bb"]
        hero = h["hero_name"]
        spots = [s for s in postflop_spots(h) if s["street"] == street]
        if not spots:
            continue
        last_street = h["last_street"] == street
        b = board_cards(h, street)
        if len(b) < 3:
            continue
        ht = type_rank(h["hole"] + b)
        btr = type_rank(b)
        hero_spots = [s for s in spots if s["hero"]]
        for k, s in enumerate(hero_spots):
            d = s["dec"]
            pot, tc = d["pot"] / bb, d["to_call"] / bb
            later = [x for x in spots if x["i"] > s["i"]]
            row = dict(key=h["key"], ts=h["ts"], street=street, act=s["act"], kind=s["kind"], facing=s["facing"],
                       hu=s["n_active"] == 2, pot=pot, tc=tc, eq=d.get("equity"), src=d.get("decision_source"),
                       hero_t=ht, board_t=btr, hero_cls=strength_class(ht, btr), bucket=d.get("hero_bucket"),
                       bet_frac=s["bet_frac"], size_pot=s.get("size_pot"), bets_before=s["bets_before"],
                       hand=h["hole"], board=b, delta=h["delta_bb"], is_last=(k == len(hero_spots) - 1),
                       rule_engine_shadow=d.get("rule_engine_shadow_action"), purpose=d.get("final_purpose"),
                       hero_bet_earlier=any(x["hero"] and x["act"] == "raise" and x["i"] < s["i"] for x in spots),
                       need=(tc / ((pot + tc) * KEEP) if tc > 0 else None), allin_call=tc >= s["stack_bb"] - 0.01,
                       cfr=d.get("realtime_cfr"), w=None, truth=None, vil_t=None, last_street=last_street)
            if not last_street:
                rows.append(row)  # e.g. all-in on an earlier street; no clean truth
                continue
            opp = [p["name"] for p in h["players"] if p["name"] != hero and p["name"] not in h["folded"]]
            if s["act"] == "fold":
                # who won, with what type
                if len(res["winners"]) == 1 and not h["showdown"]:
                    vt = label_rank(res["hand_combos"].get(res["winners"][0], ""))
                    if vt is not None:
                        row["vil_t"] = vt
                        row["w"] = 1.0 if ht > vt else (0.0 if ht < vt else 0.5)
                        row["truth"] = "type"
                elif h["showdown"]:
                    # multiway: someone else called; compare against the best shown hand type
                    best = max((type_rank(c + b) for c in res["showdown_hands"].values() if len(c) == 2), default=None)
                    if best is not None:
                        row["vil_t"] = best
                        row["w"] = 1.0 if ht > best else (0.0 if ht < best else 0.5)
                        row["truth"] = "shown_others"
            elif h["hero_at_showdown"] and row["is_last"]:
                won = hero in res["winners"]
                split = won and len(res["winners"]) > 1
                row["w"] = 0.5 if split else (1.0 if won else 0.0)
                row["truth"] = "showdown"
                vts = [type_rank(c + b) for n, c in res["showdown_hands"].items() if n != hero and len(c) == 2]
                row["vil_t"] = max(vts) if vts else None
            elif row["is_last"] and s["act"] == "raise" and not h["showdown"]:
                row["truth"] = "villain_folded"
            rows.append(row)
    return rows


def ev_call(r):
    return r["w"] * KEEP * (r["pot"] + r["tc"]) - r["tc"]


def report(rows, title):
    print(f"\n######## {title}  (hero {rows[0]['street'] if rows else ''} 决策 n={len(rows)}) ########")
    hu = [r for r in rows if r["hu"]]
    fac = [r for r in hu if r["facing"] and r["w"] is not None and r["act"] in ("fold", "call")]
    print(f"-- 单挑·面对下注/加注，有真相的 fold/call: n={len(fac)}")

    def block(label, rs):
        if not rs:
            return
        folds = [r for r in rs if r["act"] == "fold"]
        calls = [r for r in rs if r["act"] == "call"]
        fw = sum(r["w"] for r in folds)
        cw = sum(r["w"] for r in calls)
        f_ev = [ev_call(r) for r in folds]
        c_ev = [ev_call(r) for r in calls]
        need_f = sum(r["need"] for r in folds) / len(folds) if folds else float("nan")
        need_c = sum(r["need"] for r in calls) / len(calls) if calls else float("nan")
        eq_f = [r["eq"] for r in folds if r["eq"] is not None]
        eq_c = [r["eq"] for r in calls if r["eq"] is not None]
        mf, sf, _ = mean_se(f_ev)
        mc, sc, _ = mean_se(c_ev)
        print(f"   {label:<34} fold n={len(folds):3d} 真实胜率={fw / len(folds) if folds else float('nan'):.2f} 需要={need_f:.2f} bot估={sum(eq_f) / len(eq_f) if eq_f else float('nan'):.2f} "
              f"若跟注EV合计={sum(f_ev):+7.1f}bb (均{mf:+.2f}±{1.96 * sf if sf == sf else 0:.2f})"
              f" | call n={len(calls):3d} 真实胜率={cw / len(calls) if calls else float('nan'):.2f} 需要={need_c:.2f} bot估={sum(eq_c) / len(eq_c) if eq_c else float('nan'):.2f} 跟注EV合计={sum(c_ev):+7.1f}bb (均{mc:+.2f}±{1.96 * sc if sc == sc else 0:.2f})")

    block("全部", fac)
    block("面对首次下注", [r for r in fac if r["bets_before"] == 1])
    block("面对加注(hero 已下注)", [r for r in fac if r["bets_before"] >= 2])
    for src in ("realtime_cfr", "rule_engine", "flop_book"):
        block(f"来源={src}", [r for r in fac if r["src"] == src])
    for cls in ("air(不超过公共牌)", "一对级", "两对+"):
        block(f"hero牌力={cls}", [r for r in fac if r["hero_cls"] == cls])
    for sb in ("≤40%", "40-70%", "70-105%", ">105%"):
        block(f"下注尺度={sb}", [r for r in fac if r["bets_before"] == 1 and size_bucket(r["bet_frac"]) == sb])
    # calibration of bot equity on facing-bet rows (fold+call), by predicted bin
    print("   -- bot 估计胜率 vs 真实胜率（面对下注，fold+call 合并）")
    for lo, hi in ((0, .15), (.15, .3), (.3, .45), (.45, .6), (.6, 1.01)):
        rs = [r for r in fac if r["eq"] is not None and lo <= r["eq"] < hi]
        if rs:
            m = sum(r["w"] for r in rs) / len(rs)
            p = sum(r["eq"] for r in rs) / len(rs)
            print(f"      估∈[{lo:.2f},{hi:.2f}) n={len(rs):3d} 估均值={p:.2f} 真实={m:.2f}  其中fold={sum(1 for r in rs if r['act'] == 'fold')}")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("logs", nargs="+")
    ap.add_argument("--since", default="")
    ap.add_argument("--until", default="")
    ap.add_argument("--street", default="river")
    args = ap.parse_args(argv)
    hands, _ = pflog.load(args.logs)
    pflog.validate(hands)
    if args.since:
        hands = [h for h in hands if (h["ts"] or "") >= args.since]
    if args.until:
        hands = [h for h in hands if (h["ts"] or "") < args.until]
    rows = collect(hands, args.street)
    report(rows, f"{args.street} since={args.since or '-'} until={args.until or '-'}")


if __name__ == "__main__":
    main()
