"""PokerFate 结构化决策日志（pokerfate.log, JSONL）→ 每手 / 每动作 结构化数据。

只读日志，不 import 策略代码，可单独运行：

    .venv/bin/python -m analysis.pflog pokerfate/logs/pokerfate.log            # 打印校验摘要
    .venv/bin/python -m analysis.pflog <log> --out hands.jsonl                 # 另存每手一行

日志语义（已对照 hand_result 验证）：
  * 所有筹码单位是 chips；``opponent_action.amount``/``decision.amount`` 对 raise 是
    “本街加到的总额”，对 call 是“本次补入”。翻后第一次下注也记为 raise。
  * ``hand_result.pot`` 是抽水后的底池；``my_delta`` 是 hero 本手净输赢（chips）。
  * 同一个文件里可能有多次进程启动（``decision_engine_enabled``），hand 号每次重新计数，
    所以一手牌的唯一键是 (file, session, hand)。
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterable, Optional

HERO_NAMES = {"Royal Police", "斯文红衣"}
STREETS = ("preflop", "flop", "turn", "river")
RAKE = 0.09


def _load_hero_names() -> set:
    p = Path(__file__).resolve().parents[1] / "local" / "state" / "hero_names.json"
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
        return {d.get("current", "")} | set(d.get("aliases") or [])
    except Exception:
        return set(HERO_NAMES)


def iter_events(path: Path) -> Iterable[dict]:
    with open(path, encoding="utf-8") as f:
        for ln, raw in enumerate(f, 1):
            raw = raw.strip()
            if not raw:
                continue
            try:
                d = json.loads(raw)
            except json.JSONDecodeError:
                yield {"event": "__bad__", "_line": ln}
                continue
            d["_line"] = ln
            yield d


class Hand(dict):
    """dict with attribute access; kept JSON-serialisable."""
    __getattr__ = dict.get


def _infer_bb(hands: list) -> None:
    """Per-session big blind = mode of (min preflop pot / 1.5)."""
    by_s = defaultdict(Counter)
    for h in hands:
        pots = h.pop("_pf_pots", [])
        if pots:
            by_s[h["session"]][float(f"{min(pots) / 1.5:.3g}")] += 1
    for h in hands:
        c = by_s.get(h["session"])
        h["bb"] = c.most_common(1)[0][0] if c else 0.0


def parse_file(path: Path, hero_names: Optional[set] = None, file_tag: str = "") -> tuple[list, dict]:
    hero_names = hero_names or _load_hero_names()
    tag = file_tag or path.name
    stats = Counter()
    hands: list = []
    cur: Optional[Hand] = None
    session = 0
    session_cfg: dict = {}
    pending_fallbacks: list = []

    def close(reason: str):
        nonlocal cur
        if cur is not None:
            stats[f"hand_unclosed_{reason}"] += 1
            cur["incomplete"] = True
            hands.append(cur)
            cur = None

    for d in iter_events(path):
        e = d.get("event")
        if e == "__bad__":
            stats["bad_json_lines"] += 1
            continue
        stats["events"] += 1
        if e == "decision_engine_enabled":
            close("session_restart")
            session += 1
            session_cfg = {"engine": d.get("engine"), "start_ts": d.get("ts")}
            continue
        if e == "session_config":
            session_cfg = dict(session_cfg, resolved=d.get("resolved") or {}, env=d.get("env") or {})
            continue
        if e == "hand_start":
            close("new_hand_start")
            players = [dict(id=p["id"], name=p["name"], stack=float(p["stack"]), pos=p.get("pos"),
                            pos_raw=p.get("pos_raw")) for p in d["players"]]
            cur = Hand(
                file=tag, session=session, hand=d["hand"], ts=d.get("ts"), dealer_id=d.get("dealer_id"),
                players=players, n=len(players), hole=None, board={}, raw=[], result=None,
                cfg=session_cfg.get("resolved") or {}, engine=session_cfg.get("engine"),
                _pf_pots=[], fallbacks=[], incomplete=False,
            )
            cur["key"] = f"{tag}#{session}:{d['hand']}"
            continue
        if e == "decision_engine_fallback":
            pending_fallbacks.append({"component": d.get("component"), "reason": d.get("reason"), "ts": d.get("ts")})
            continue
        if cur is None or d.get("hand") != cur["hand"]:
            if e in ("hole_cards", "board", "opponent_action", "decision", "hand_result"):
                stats["orphan_events"] += 1
            continue
        if e == "hole_cards":
            cur["hole"] = list(d.get("cards") or [])
        elif e == "hero_execution":
            # the server's confirmation of hero's last decision on this street
            for r in reversed(cur["raw"]):
                if r.get("hero") and r["street"] == d.get("street") and "executed" not in r["dec"]:
                    r["dec"]["executed"] = {k: d.get(k) for k in ("amount_added", "total_bet_after")}
                    break
        elif e == "board":
            cur["board"][d["street"]] = list(d["cards"])
            cur["raw"].append({"t": "board", "street": d["street"], "cards": list(d["cards"]), "ts": d.get("ts")})
        elif e == "opponent_action":
            if d.get("street") == "preflop" and d.get("pot_before_action"):
                cur["_pf_pots"].append(float(d["pot_before_action"]))
            cur["raw"].append({
                "t": "act", "hero": False, "who": d["player"], "street": d["street"], "act": d["action"],
                "amt": float(d.get("amount") or 0), "pot_logged": float(d.get("pot_before_action") or 0),
                "range_pct": d.get("range_pct"), "bucket_dist": d.get("bucket_dist"), "vs_hero": d.get("vs_hero"),
                "pattern": (d.get("layer_trace") or {}).get("pattern") if d.get("layer_trace") else None,
                "ts": d.get("ts"),
            })
        elif e == "decision":
            if d.get("street") == "preflop" and d.get("pot"):
                cur["_pf_pots"].append(float(d["pot"]))
            dec = {k: v for k, v in d.items() if k not in ("event", "hand", "_line")}
            dec["fallbacks"] = pending_fallbacks
            pending_fallbacks = []
            cur["raw"].append({
                "t": "act", "hero": True, "who": "__hero__", "street": d["street"], "act": d["action"],
                "amt": float(d.get("amount") or 0), "pot_logged": float(d.get("pot") or 0),
                "to_call_logged": float(d.get("to_call") or 0), "dec": dec, "ts": d.get("ts"),
            })
        elif e == "hand_result":
            cur["result"] = {
                "winners": d.get("winners") or [], "pot": float(d.get("pot") or 0),
                "my_delta": float(d.get("my_delta") or 0), "final_stacks": d.get("final_stacks") or {},
                "showdown_hands": d.get("showdown_hands") or {}, "hand_combos": d.get("hand_combos") or {},
                "my_combo": d.get("my_combo") or "", "ts": d.get("ts"),
            }
            hands.append(cur)
            cur = None
    close("eof")
    _infer_bb(hands)
    for h in hands:
        _reconstruct(h, hero_names, stats)
    stats["hands"] = len(hands)
    return hands, dict(stats)


def _reconstruct(h: Hand, hero_names: set, stats: Counter) -> None:
    """Turn the raw event stream into an ordered action list with chip accounting.

    Chip truth, in order of trust:
      1. hero ``decision.pot`` / ``to_call`` / ``current_bet`` / ``my_current_bet`` (server values
         handed to request_action) and ``hero_execution`` (server-confirmed hero chips);
      2. our own replay of opponent actions (raise = street total, call = chips added);
      3. ``opponent_action.pot_before_action`` — the bot's estimate, NOT trusted: it double-counts
         a blind when a blind seat raises and misses out-of-turn posts.
    The replayed pot is re-synchronised to (1) at every hero decision; the size of each
    correction is kept in ``pot_sync`` for validation.
    """
    bb = h["bb"] or 1.0
    name2p = {p["name"]: p for p in h["players"]}
    hero = next((p for p in h["players"] if p["name"] in hero_names), None)
    h["hero_name"] = hero["name"] if hero else None
    h["hero_pos"] = hero["pos"] if hero else None
    h["hero_stack_bb"] = hero["stack"] / bb if hero else None
    h["dealt"] = bool(h["hole"])
    pos_of = {p["name"]: p["pos"] for p in h["players"]}
    stack = {p["name"]: p["stack"] for p in h["players"]}
    invested = {p["name"]: 0.0 for p in h["players"]}
    folded: set = set()
    allin: set = set()
    street_bet: dict = defaultdict(float)
    for p in h["players"]:
        if p["pos"] == "SB":
            street_bet[p["name"]] = min(0.5 * bb, p["stack"])
        elif p["pos"] == "BB":
            street_bet[p["name"]] = min(1.0 * bb, p["stack"])
    if h["n"] == 2:  # heads-up: labels are BTN/BB, the BTN posts the small blind
        for p in h["players"]:
            if p["pos"] == "BTN":
                street_bet[p["name"]] = min(0.5 * bb, p["stack"])
    for nm, v in street_bet.items():
        invested[nm] = v
    pot = sum(street_bet.values())
    street = "preflop"
    actions: list = []
    n_raises = {s: 0 for s in STREETS}
    last_aggr = {s: None for s in STREETS}
    seen_flop_players = None
    pot_sync: list = []
    hero_name = h["hero_name"]
    hero_first = True

    for r in h["raw"]:
        if r["t"] == "board":
            street = r["street"]
            street_bet = defaultdict(float)
            if street == "flop":
                seen_flop_players = [n for n in invested if n not in folded]
            continue
        who = hero_name if r["hero"] else r["who"]
        if who not in name2p:
            stats["action_unknown_player"] += 1
            continue
        st = r["street"]
        if st != street:
            stats["street_label_mismatch"] += 1
            h["street_mismatch"] = True
        act = r["act"]
        amt = r["amt"]
        cur_max = max(street_bet.values()) if street_bet else 0.0
        ex = {}
        if r["hero"]:
            dec = r["dec"]
            ex = dec.get("executed") or {}
            ctx = {k: dec[k] for k in ("current_bet", "my_current_bet") if k in dec}
            logged_pot = r.get("pot_logged") or 0.0
            logged_tc = r.get("to_call_logged") or 0.0
            if "my_current_bet" in ctx and "current_bet" in ctx:
                my_bet = float(ctx["my_current_bet"] or 0.0)
                true_max = max(float(ctx["current_bet"] or 0.0), my_bet + logged_tc)
            else:
                my_bet = max(0.0, cur_max - logged_tc)
                true_max = my_bet + logged_tc
            # hero's own forced post is whatever the server says is already in front of him
            if abs(street_bet[who] - my_bet) > 1.0:
                if hero_first and st == "preflop":
                    invested[who] += my_bet - street_bet[who]
                    h["hero_post_fix"] = my_bet - street_bet[who]
                street_bet[who] = my_bet
            if abs(true_max - cur_max) > 1.0:
                h["curmax_sync"] = h.get("curmax_sync", 0) + 1
                cur_max = true_max
            if logged_pot > 0:
                off = logged_pot - pot
                if abs(off) > max(2.0, 0.002 * logged_pot):
                    pot_sync.append({"i": len(actions), "street": street, "off": off})
                pot = logged_pot
            hero_first = False
        mine = street_bet[who]
        to_call = max(0.0, cur_max - mine)
        remaining_before = stack[who] - invested[who]
        # A non-hero player who "checks" preflop while facing a bet posted a live blind out
        # of turn (new player posting to enter); the bot only learns about it at this action.
        if (not r["hero"]) and st == "preflop" and act == "check" and to_call > 0:
            street_bet[who] = cur_max
            invested[who] += to_call
            pot += to_call
            mine = cur_max
            to_call = 0.0
            remaining_before = stack[who] - invested[who]
            h["posted_blind"] = h.get("posted_blind", 0) + 1
        add = 0.0
        if act == "call":
            if r["hero"]:
                add = float(ex.get("amount_added", 0) or 0) or min(to_call, remaining_before)
            else:
                add = amt
                if mine + add > cur_max + 1.0 and street == "preflop":
                    # phantom blind: we assumed a post that never happened (dead SB, heads-up)
                    phantom = min(mine, mine + add - cur_max)
                    invested[who] -= phantom
                    pot -= phantom
                    mine -= phantom
                    street_bet[who] = mine
                    to_call = max(0.0, cur_max - mine)
                    h["phantom_blind"] = h.get("phantom_blind", 0) + phantom
        elif act == "raise":
            target = amt
            if r["hero"] and ex.get("total_bet_after"):
                target = float(ex["total_bet_after"])
            add = max(0.0, target - mine)
            if r["hero"] and ex.get("amount_added"):
                add = float(ex["amount_added"])
        remaining_before = stack[who] - invested[who]
        if add > remaining_before + 1.0:
            stats["add_exceeds_stack"] += 1
            add = max(0.0, remaining_before)
        active_before = [n for n in invested if n not in folded]
        live_before = [n for n in active_before if n not in allin]
        pot_before = pot
        a = {
            "i": len(actions), "street": street, "who": who, "pos": pos_of.get(who), "hero": bool(r["hero"]),
            "act": act, "amt": amt, "add": add, "to_call": to_call, "pot_before": pot_before,
            "cur_max": cur_max, "n_active": len(active_before), "n_live": len(live_before),
            "stack_before": remaining_before, "ts": r.get("ts"), "raises_before": n_raises[street],
        }
        if act == "raise":
            a["kind"] = "bet" if (street != "preflop" and cur_max <= 0) else "raise"
            a["to"] = mine + add
            # size as a fraction of the pot after calling (standard "pot-sized raise" convention)
            a["size_pot"] = (add - to_call) / (pot_before + to_call) if (pot_before + to_call) > 0 else None
            n_raises[street] += 1
            last_aggr[street] = who
        elif act == "call":
            a["kind"] = "call"
        else:
            a["kind"] = act
        if not r["hero"]:
            a["range_pct"] = r.get("range_pct")
            a["bucket_dist"] = r.get("bucket_dist")
            a["vs_hero"] = r.get("vs_hero")
            a["pattern"] = r.get("pattern")
            a["pot_bot_est"] = r.get("pot_logged")
        else:
            a["dec"] = r["dec"]
        street_bet[who] = mine + add
        invested[who] += add
        pot += add
        if act == "fold":
            folded.add(who)
        if act in ("call", "raise") and (stack[who] - invested[who]) <= 1.0:
            allin.add(who)
            a["allin"] = True
        actions.append(a)

    h["actions"] = actions
    h["invested"] = invested
    h["folded"] = sorted(folded)
    h["allin"] = sorted(allin)
    h["pot_final_recon"] = pot
    h["pot_sync"] = pot_sync
    h["pf_raises"] = n_raises["preflop"]
    h["pfr_last"] = last_aggr["preflop"]
    h["flop_players"] = seen_flop_players or []
    h["last_street"] = street
    res = h.get("result")
    if res:
        h["delta_bb"] = res["my_delta"] / bb
        remaining = [n for n in invested if n not in folded]
        h["remaining"] = remaining
        h["showdown"] = len(remaining) >= 2 and bool(res["showdown_hands"])
        h["hero_at_showdown"] = bool(h["showdown"] and hero_name in remaining and h["dealt"])
        # uncalled part of the last bet is returned before rake, except a walk
        # (everyone folds to the BB): the whole SB+BB pot is raked.
        inv_sorted = sorted(invested.values(), reverse=True)
        uncalled = inv_sorted[0] - inv_sorted[1] if len(inv_sorted) >= 2 else 0.0
        h["pot_contested_recon"] = pot - uncalled
        tot, con = pot, pot - uncalled
        rp = res["pot"]
        h["rake_ok"] = bool(rp > 0 and (abs(rp - (1 - RAKE) * con) <= max(3.0, 0.003 * con)
                                        or abs(rp - (1 - RAKE) * tot) <= max(3.0, 0.003 * tot)))
    del h["raw"]


def load(paths: Iterable, hero_names: Optional[set] = None) -> tuple[list, dict]:
    all_hands, all_stats = [], Counter()
    for p in paths:
        hs, st = parse_file(Path(p), hero_names)
        all_hands.extend(hs)
        all_stats.update(st)
    return all_hands, dict(all_stats)


def validate(hands: list) -> dict:
    """Data-quality checks: completeness, pot reconciliation, hero chip accounting, continuity."""
    out = Counter()
    keys = Counter(h["key"] for h in hands)
    out["hands_total"] = len(hands)
    out["duplicate_keys"] = sum(1 for v in keys.values() if v > 1)
    out["incomplete_no_result"] = sum(1 for h in hands if not h.get("result"))
    out["hero_not_dealt"] = sum(1 for h in hands if h.get("result") and not h["dealt"])
    ok = [h for h in hands if h.get("result") and h["dealt"]]
    out["hands_dealt_complete"] = len(ok)
    out["hands_pot_resynced_at_hero_decision"] = sum(1 for h in ok if h["pot_sync"])
    out["hands_hero_post_fixed"] = sum(1 for h in ok if h.get("hero_post_fix"))
    out["hands_out_of_turn_post"] = sum(1 for h in ok if h.get("posted_blind"))
    out["hands_phantom_blind"] = sum(1 for h in ok if h.get("phantom_blind"))
    out["hands_street_label_mismatch"] = sum(1 for h in ok if h.get("street_mismatch"))
    bad_delta = 0
    for h in ok:
        hero = h["hero_name"]
        inv = h["invested"].get(hero, 0.0)
        d = h["result"]["my_delta"]
        if hero in h["folded"] and abs(d + inv) > max(2.0, 0.002 * inv):
            bad_delta += 1
            h["delta_mismatch"] = d + inv
    out["hero_fold_delta_ne_invested"] = bad_delta
    out["result_pot_not_0.91x_recon"] = sum(1 for h in ok if not h.get("rake_ok"))
    prev = None
    cont_bad = 0
    resets = 0
    for h in hands:
        if not h.get("result"):
            prev = None
            continue
        hero = next((p for p in h["players"] if p["name"] == h["hero_name"]), None)
        if hero is None:
            prev = None
            continue
        if prev is not None and prev["session"] == h["session"] and prev["file"] == h["file"]:
            expect = prev["result"]["final_stacks"].get(prev["hero_name"])
            if expect is not None and abs(expect - hero["stack"]) > 2.0:
                resets += 1  # rebuy / profit-lock re-entry / top-up
                h["stack_reset"] = hero["stack"] - expect
            start = next(p["stack"] for p in prev["players"] if p["name"] == prev["hero_name"])
            if expect is not None and abs(start + prev["result"]["my_delta"] - expect) > 2.0:
                cont_bad += 1
        prev = h
    out["stack_resets_between_hands"] = resets
    out["final_stack_ne_start_plus_delta"] = cont_bad
    return dict(out)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("logs", nargs="+")
    ap.add_argument("--out", default="")
    args = ap.parse_args(argv)
    hands, stats = load(args.logs)
    v = validate(hands)
    print("== parse stats ==")
    for k, val in sorted(stats.items()):
        print(f"  {k}: {val}")
    print("== validation ==")
    for k, val in v.items():
        print(f"  {k}: {val}")
    if hands:
        print(f"  ts range: {hands[0]['ts']} → {hands[-1]['ts']}")
        print(f"  sessions: {len({(h['file'], h['session']) for h in hands})}; bb values: {Counter(h['bb'] for h in hands).most_common(5)}")
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            for h in hands:
                f.write(json.dumps(h, ensure_ascii=False) + "\n")
        print(f"wrote {len(hands)} hands → {args.out}")


if __name__ == "__main__":
    sys.exit(main())
