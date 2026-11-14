"""Print one or more hands in a compact, reviewable form.

    .venv/bin/python -m analysis.show_hand pokerfate/logs/pokerfate.log 383 419
    .venv/bin/python -m analysis.show_hand <log> 2:17        # session:hand
"""
from __future__ import annotations

import json
import sys

from analysis import pflog


def fmt_dec(d: dict, bb: float, verbose: bool = True) -> str:
    parts = [f"src={d.get('decision_source')}"]
    if d.get("equity") is not None:
        parts.append(f"eq={d['equity']:.3f}")
    if d.get("equity_random") is not None:
        parts.append(f"eq_rand={d['equity_random']:.3f}")
    for k in ("hero_bucket", "hero_made_subtype", "final_purpose", "arbitration_mode", "preflop_expand_reason"):
        if d.get(k):
            parts.append(f"{k}={d[k]}")
    if d.get("purpose_candidates"):
        parts.append("cands=" + ",".join(f"{c['purpose']}:{c['prob']:.2f}" for c in d["purpose_candidates"]))
    if d.get("strategy_gates"):
        parts.append("gates=" + " | ".join(d["strategy_gates"]))
    if d.get("decision_reason") and verbose:
        parts.append("reason=" + str(d["decision_reason"])[:160])
    out = "      " + "  ".join(parts)
    r = d.get("realtime_cfr")
    if r and verbose:
        keep = {k: r.get(k) for k in ("status", "hero_side", "node_path", "pot_bb", "effective_stack_bb", "range_counts",
                                     "selected_label", "selected_prob", "strategy", "action_evs_bb", "exploit_used",
                                     "exploit_confidence", "final_action_evs_bb")}
        out += "\n      cfr=" + json.dumps(keep, ensure_ascii=False)
        if r.get("safety"):
            out += "\n      safety=" + json.dumps(r["safety"], ensure_ascii=False)[:900]
    if d.get("flop_book") and verbose:
        out += "\n      book=" + json.dumps(d["flop_book"], ensure_ascii=False)[:500]
    if d.get("local_shadow_action"):
        out += f"\n      local_shadow={d['local_shadow_action']} {d.get('local_shadow_amount')}"
    if d.get("river_relative") and verbose:
        out += "\n      river_relative=" + json.dumps(d["river_relative"], ensure_ascii=False)[:300]
    if d.get("fallbacks"):
        out += "\n      fallbacks=" + ",".join(f"{f.get('component')}:{f.get('reason')}" for f in d["fallbacks"])
    return out


def show(h, verbose: bool = True) -> None:
    bb = h["bb"]
    print(f"=== {h['key']}  {h['ts'][:19]}  {h['n']}人桌  hero={h['hero_pos']} {h['hole']}  stack={h['hero_stack_bb']:.0f}bb")
    print("    seats: " + "  ".join(f"{p['pos']}:{p['name']}({p['stack'] / bb:.0f}bb)" for p in h["players"]))
    street = None
    for a in h["actions"]:
        if a["street"] != street:
            street = a["street"]
            board = []
            for s in ("flop", "turn", "river"):
                if s in h["board"]:
                    board += h["board"][s]
                if s == street:
                    break
            print(f"  -- {street} {' '.join(board) if street != 'preflop' else ''}  pot={a['pot_before'] / bb:.1f}bb  active={a['n_active']}")
        who = "HERO" if a["hero"] else a["who"]
        desc = a["act"]
        if a["act"] == "raise":
            desc = f"{a['kind']} to {a['to'] / bb:.1f}bb" + (f" ({100 * a['size_pot']:.0f}% pot)" if a.get("size_pot") is not None and street != "preflop" else "")
        elif a["act"] == "call":
            desc = f"call {a['add'] / bb:.1f}bb"
        extra = " ALL-IN" if a.get("allin") else ""
        line = f"    {a['pos'] or '?':<3} {who:<14} {desc}{extra}   [pot {a['pot_before'] / bb:.1f}, to_call {a['to_call'] / bb:.1f}]"
        if not a["hero"] and a.get("bucket_dist"):
            bd = a["bucket_dist"]
            line += "  est: " + " ".join(f"{k[:3]}={v:.2f}" for k, v in sorted(bd.items(), key=lambda kv: -kv[1])[:4])
            if a.get("vs_hero"):
                line += f"  P(hero wins)={a['vs_hero'].get('win')}"
        print(line)
        if a["hero"]:
            print(fmt_dec(a["dec"], bb, verbose))
    r = h.get("result") or {}
    print(f"  => delta {h.get('delta_bb', 0):+.1f}bb  winners={r.get('winners')}  showdown={r.get('showdown_hands')}  combos={r.get('hand_combos')}")


def main(argv=None):
    argv = argv or sys.argv[1:]
    log = argv[0]
    wanted = argv[1:]
    hands, _ = pflog.load([log])
    for w in wanted:
        if ":" in w:
            s, n = w.split(":")
            sel = [h for h in hands if h["session"] == int(s) and h["hand"] == int(n)]
        else:
            sel = [h for h in hands if h["hand"] == int(w)]
        for h in sel:
            show(h)
            print()


if __name__ == "__main__":
    main()
