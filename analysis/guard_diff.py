"""Offline decision diff for the two river guards added on 2026-11-12, run through the
PRODUCTION functions on the solver outputs stored in the decision log.

  * value-bet floor      (realtime_cfr._apply_value_bet_floor)
  * tracker-backed call  (realtime_cfr._apply_overvalue_cheap_call_guard, tracker path)

Each logged river CFR decision carries the solver strategy, GTO EVs, exploit-adjusted EVs and
the safety records, so the guards can be re-applied without re-solving. The pre-guard
selection is the argmax of the logged exploit-adjusted EVs (or the gto_ev_floor target).
Inputs the log does not carry are approximated and say so:
  - hero's showdown value: the tracker's P(hero wins) logged on the villain's preceding river
    action when there is one, otherwise the decision's logged equity;
  - the opponent prior of the call guard is neutral (overvalue = nut_heavy = 0), i.e. only the
    tracker path can fire.

    .venv/bin/python -m analysis.guard_diff pokerfate/logs/archive/*.pokerfate.bak.log pokerfate/logs/pokerfate.log
"""
from __future__ import annotations

import argparse
import os
from collections import Counter
from types import SimpleNamespace

os.environ.setdefault("PYTEST_CURRENT_TEST", "analysis/guard_diff.py")  # no autosave / log files

from pokerfate.core.card import Card  # noqa: E402
from pokerfate.decision import realtime_cfr as rc  # noqa: E402

from analysis import pflog  # noqa: E402
from analysis.features import mean_se, postflop_spots, usable  # noqa: E402
from analysis.river_audit import KEEP  # noqa: E402
from analysis.truth import board_cards, label_rank, type_rank  # noqa: E402
from analysis.truth import strength_class  # noqa: E402
from analysis.value_audit import bet_gain_vs_showdown, continue_probabilities, score  # noqa: E402

NEUTRAL_PRIOR = SimpleNamespace(overvalue_score=0.0, nut_heavy_score=0.0)


def pre_guard_selection(cfr: dict) -> str:
    final = cfr.get("final_action_evs_bb") or {}
    strategy = cfr.get("strategy") or {}
    safety = cfr.get("safety") or {}
    if not final:
        return str(cfr.get("selected_label") or "")
    label = max(final.items(), key=lambda kv: (kv[1], strategy.get(kv[0], 0.0)))[0]
    floor = safety.get("gto_ev_floor")
    if isinstance(floor, dict) and floor.get("to"):
        label = str(floor["to"])
    return label


def collect(hands, options: rc.RealtimeCFROptions):
    rows = []
    for h in hands:
        if not usable(h):
            continue
        bb = h["bb"]
        hero = h["hero_name"]
        spots = [s for s in postflop_spots(h) if s["street"] in ("turn", "river")]
        acts = {a["i"]: a for a in h["actions"]}
        for s in spots:
            if not s["hero"]:
                continue
            d = s["dec"]
            cfr = d.get("realtime_cfr")
            if not cfr or cfr.get("status") != "ok" or not cfr.get("strategy"):
                continue
            street = s["street"]
            board = board_cards(h, street)
            prev = acts.get(s["i"] - 1)
            vs = (prev or {}).get("vs_hero") if prev and not prev["hero"] and prev["street"] == street else None
            sv = float(vs["win"]) + 0.5 * float(vs.get("tie") or 0.0) if isinstance(vs, dict) and vs.get("win") is not None else None
            sv_src = "tracker_row" if sv is not None else "equity"
            if sv is None:
                sv = d.get("equity")
            line = {
                "street": street,
                "current_pot_bb": d["pot"] / bb,
                "current_to_call_bb": d["to_call"] / bb,
                "hero_current_bet_bb": s["pot_bb"] * 0.0,
                "effective_stack_bb": float(cfr.get("effective_stack_bb") or 0.0),
            }
            if s["facing"]:
                # chips hero already has in front on this street
                line["hero_current_bet_bb"] = sum(
                    a["add"] for a in h["actions"] if a["hero"] and a["street"] == street and a["i"] < s["i"]) / bb
            if street == "river" and sv is not None:
                line["range_v2"] = {"vs_hero": {"win": float(sv), "tie": 0.0, "loss": 1.0 - float(sv)}}
            strategy = dict(cfr["strategy"])
            final = dict(cfr.get("final_action_evs_bb") or {})
            gto = dict(cfr.get("action_evs_bb") or {})
            safety = dict(cfr.get("safety") or {})
            pre = pre_guard_selection(cfr)
            logged = str(cfr.get("selected_label") or "")
            new = pre
            guard = ""
            detail = {}
            if final:
                made_rank = rc._hero_made_rank([Card.from_str(c) for c in h["hole"]], [Card.from_str(c) for c in board])
                s2 = dict(safety)
                called = rc._apply_overvalue_cheap_call_guard(
                    pre, final, gto, prior=NEUTRAL_PRIOR, street=street, line_context=line,
                    hero_made_rank=made_rank, confidence=float(cfr.get("exploit_confidence") or 0.0), safety=s2,
                    pot_tolerance=options.cheap_call_pot_tolerance,
                    min_showdown_value=options.cheap_call_min_showdown_value,
                )
                if called != pre:
                    new, guard, detail = called, "cheap_call", s2.get("overvalue_cheap_call_guard") or {}
                else:
                    s3 = dict(safety)
                    floored, applied = rc._apply_value_bet_floor(
                        pre, final, strategy, street=street, line_context=line, safety=s3, rng=None,
                        enabled=options.value_bet_floor_enabled,
                        min_bet_freq=options.value_bet_floor_min_bet_freq,
                        min_showdown_value=options.value_bet_floor_min_showdown_value,
                        max_pot_ratio=options.value_bet_floor_max_pot_ratio,
                    )
                    if applied:
                        new, guard, detail = floored, "value_floor", s3.get("value_bet_floor") or {}
            # truth
            shown = None
            for n, c in h["result"]["showdown_hands"].items():
                if n != hero and len(c) == 2:
                    shown = c
            ahead = None
            vcls = None
            actual_gain = None
            if street == "river" and len(board) == 5 and h["last_street"] == "river":
                btr = type_rank(board)
                if shown:
                    a_, b_ = score(h["hole"], board), score(shown, board)
                    ahead = 1.0 if a_ > b_ else (0.0 if a_ < b_ else 0.5)
                    vcls = strength_class(type_rank(shown + board), btr)
                elif hero in h["folded"] and h["result"]["winners"]:
                    vt = label_rank(h["result"]["hand_combos"].get(h["result"]["winners"][0], ""))
                    if vt is not None:
                        ht = type_rank(h["hole"] + board)
                        ahead = 1.0 if ht > vt else (0.0 if ht < vt else 0.5)
                        vcls = strength_class(vt, btr)
                if ahead is not None and not s["facing"]:
                    hero_riv = sum(a["add"] for a in h["actions"] if a["street"] == "river" and a["hero"]) / bb
                    inv_before = h["invested"][hero] / bb - hero_riv
                    # what the river street actually added on top of checking the hand down
                    actual_gain = h["delta_bb"] - (ahead * KEEP * (d["pot"] / bb) - inv_before)
            rows.append(dict(key=h["key"], ts=h["ts"], street=street, facing=s["facing"], pre=pre, logged=logged, new=new,
                             guard=guard, detail=detail, sv=sv, sv_src=sv_src, pot=d["pot"] / bb, tc=d["to_call"] / bb,
                             ahead=ahead, vcls=vcls, actual_gain=actual_gain, ip=s["n_acted"] >= 1,
                             hand=h["hole"], board=board, shown=shown, logged_mixed="mixed_sample" in safety,
                             bet_freq=sum(v for k, v in strategy.items() if rc._action_kind(k) in {"Bet", "AllIn"})))
    return rows


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("logs", nargs="+")
    ap.add_argument("--since", default="")
    ap.add_argument("--list", action="store_true", help="print every changed decision")
    args = ap.parse_args(argv)
    hands, _ = pflog.load(args.logs)
    pflog.validate(hands)
    all_hands = hands  # the pool response model always uses every log passed in
    hands = [h for h in hands if (h["ts"] or "") >= args.since]
    opts = rc.RealtimeCFROptions()
    print("options:", {k: getattr(opts, k) for k in (
        "value_bet_floor_enabled", "value_bet_floor_min_bet_freq", "value_bet_floor_min_showdown_value",
        "value_bet_floor_max_pot_ratio", "cheap_call_pot_tolerance", "cheap_call_min_showdown_value")})
    rows = collect(hands, opts)
    n_hands = sum(1 for h in hands if usable(h))
    print(f"手数 {n_hands}；有 solver 输出的 CFR 决策 {len(rows)} "
          f"(turn {sum(1 for r in rows if r['street'] == 'turn')}, river {sum(1 for r in rows if r['street'] == 'river')})")
    same_pre = sum(1 for r in rows if r["pre"] == r["logged"])
    print(f"由日志重建的'守卫前选择'与日志最终动作一致: {same_pre}/{len(rows)}"
          f"（不一致的 {len(rows) - same_pre} 个里 {sum(1 for r in rows if r['pre'] != r['logged'] and r['logged_mixed'])} 个是日志里的近似平局混合抽样）")
    fired = [r for r in rows if r["guard"]]
    changed = [r for r in fired if r["new"] != r["pre"]]
    print(f"\n守卫触发 {len(fired)}，其中改变动作 {len(changed)}；按 (街, 是否面对下注, 守卫, 前→后) 计数：")
    for k, v in sorted(Counter((r["street"], "面对下注" if r["facing"] else "无人下注", r["guard"],
                                rc._action_kind(r["pre"]) + "→" + rc._action_kind(r["new"])) for r in fired).items()):
        print("   ", k, v)
    untouched = Counter((r["street"], "面对下注" if r["facing"] else "无人下注") for r in rows if not r["guard"])
    print("未触发（动作不变）:", dict(untouched))

    vf = [r for r in fired if r["guard"] == "value_floor"]
    if vf:
        exp_bet = sum(1.0 - r["detail"]["candidates"].get("Check", 0.0) for r in vf)
        print(f"\n== 价值下注下限：触发 {len(vf)} 次（{100 * len(vf) / n_hands:.2f} 次/100手）；按 solver 混合抽样的期望下注次数 {exp_bet:.1f} ==")
        print("   showdown value 来源:", dict(Counter(r["sv_src"] for r in vf)))
        truth = [r for r in vf if r["ahead"] is not None and r["actual_gain"] is not None]
        print(f"   有真相 {len(truth)}：hero 领先 {sum(r['ahead'] for r in truth):.1f}/{len(truth)}；有位置 {sum(1 for r in vf if r['ip'])} / 无位置 {sum(1 for r in vf if not r['ip'])}")
        after_check, facing_lead = continue_probabilities(all_hands)
        gains = []
        for r in truth:
            pc = (after_check if r["ip"] else facing_lead)[r["vcls"]]
            g = 0.0
            for lab, w in r["detail"]["candidates"].items():
                if lab == "Check":
                    continue
                risk = rc._candidate_action_context(lab, {"current_pot_bb": r["pot"], "hero_current_bet_bb": 0.0})["risk_bb"]
                g += w * (bet_gain_vs_showdown(risk, r["ahead"], pc) - r["actual_gain"])
            gains.append(g)
        m, se, n = mean_se(gains)
        print(f"   按 solver 混合与其尺度、对手真实牌力估算的 EV 变化: 合计 {sum(gains):+.1f}bb，每次触发 {m:+.2f} ± {1.96 * se:.2f}bb"
              f"（{100 * sum(gains) / n_hands:+.2f} bb/100，区间 ±{100 * 1.96 * se * n / n_hands:.2f}）")
        sizes = Counter()
        for r in vf:
            for lab, w in r["detail"]["candidates"].items():
                if lab != "Check":
                    ratio = rc._candidate_action_context(lab, {"current_pot_bb": r["pot"], "hero_current_bet_bb": 0.0})["pot_ratio"]
                    sizes["≤40%" if ratio <= 0.4 else "40-70%" if ratio <= 0.7 else "70-100%"] += w
        tot = sum(sizes.values())
        print("   下注尺度分布(按权重):", {k: f"{100 * v / tot:.0f}%" for k, v in sizes.items()})
    cc = [r for r in fired if r["guard"] == "cheap_call"]
    if cc:
        print(f"\n== 便宜跟注（tracker 证据）：Fold→Call {len(cc)} 次 ==")
        ev = []
        for r in cc:
            w = r["ahead"]
            e = None if w is None else w * KEEP * (r["pot"] + r["tc"]) - r["tc"]
            ev.append(e)
            print(f"   {r['key']:<34} pot={r['pot']:.1f} call={r['tc']:.1f} sv={r['sv']:.2f}({r['sv_src']}) gap={r['detail'].get('gto_gap_bb')} tol={r['detail'].get('gto_tolerance_bb')} "
                  f"真相胜={w} EV(call)={'%+.1f' % e if e is not None else '?'}bb")
        known = [e for e in ev if e is not None]
        if known:
            print(f"   真相 EV 合计 {sum(known):+.1f}bb / {len(known)} 次")
    if args.list:
        print("\n== 明细 ==")
        for r in fired:
            print(f"  {r['key']:<34} {r['street']} {r['guard']:<11} {r['pre']}→{r['new']} sv={r['sv']:.2f} bet_freq={r['bet_freq']:.2f} "
                  f"pot={r['pot']:.1f} {r['hand']} {r['board']} villain={r['shown']} ahead={r['ahead']} {r['detail'].get('candidates', '')}")


if __name__ == "__main__":
    main()
