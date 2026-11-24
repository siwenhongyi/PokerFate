"""Replay logged flop decision points through a flop book (no solver, light CPU).

Walks hands with the regular replay harness, but turn/river realtime CFR is switched off, so
only the flop book lookup and the rule engine run. For every hero flop decision it records
whether the book answered, with which scenario/depth and action, or why it fell back.

    .venv/bin/python -m analysis.flop_book_replay --book pokerfate/data/flop_book/v3 \
        --json-log pokerfate/logs/pokerfate.log --out /path/rows.jsonl [--opponents-model snapshot.json]

Compare two books by running it twice and passing both outputs to --compare.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from pathlib import Path

os.environ.setdefault("PYTEST_CURRENT_TEST", "analysis/flop_book_replay.py")  # no autosave / log files


def run(book_dir: str, logs: list, out: Path, opponents_model: str = "", seed: int = 42, since: str = "") -> list:
    os.environ["PF_FLOP_BOOK_DIR"] = str(Path(book_dir).resolve())
    from pokerfate.api import PokerFateAPI
    from scripts.hero_name import load_hero_names
    from scripts.json_log_to_replay import parse_json_log
    from scripts.replay_and_compare import _hero_id, _replay_hand

    hero_names = load_hero_names()
    hands = []
    offset = 0
    for log in logs:
        parsed = parse_json_log(Path(log), hero_names)
        for h in parsed:
            h["session"] += offset
            h["source_log"] = str(log)
        if parsed:
            offset = max(h["session"] for h in parsed)
        hands.extend(parsed)

    rows: list = []
    api = None
    last_key = None
    for hand in hands:
        hero_id = _hero_id(hand["players"], hero_names)
        if hero_id is None:
            continue
        bb = float(hand.get("big_blind") or 2.0)
        key = (hand.get("session"), hero_id, bb)
        if api is None or key != last_key:
            api = PokerFateAPI(
                my_player_id=hero_id, big_blind=bb, small_blind=bb / 2.0, autosave_path=None, log_file=None,
                verbose=False, equity_iterations=200, enable_showdown_calibration=False,
                decision_seed=seed, decision_engine="cfr",
            )
            api._log._console = False
            api._decide_with_realtime_cfr = lambda gs, street: None  # flop book + rule engine only
            if opponents_model:
                api._load_persisted_model(opponents_model)
            assert api._flop_book_engine is not None, f"flop book did not load from {book_dir}: {api._flop_book_error}"
            original = api.request_action
            state = {"hand": None}

            def wrapped(street, *a, _orig=original, _api=api, _state=state, **k):
                decision = _orig(street, *a, **k)
                if str(street).lower() == "flop":
                    res = _api._flop_book_engine.last_result or {}
                    hit = res.get("status") == "ok"
                    rows.append({
                        "session": _state["hand"].get("session"), "hand": _state["hand"].get("hand"),
                        "log": _state["hand"].get("source_log"),
                        "hit": bool(hit), "reason": "" if hit else str(res.get("reason") or _api._flop_book_error or "?"),
                        "scenario": res.get("scenario"), "book_depth_bb": res.get("book_depth_bb"),
                        "effective_stack_bb": res.get("effective_stack_bb"), "pot_bb": res.get("pot_bb"),
                        "expected_pot_bb": res.get("expected_pot_bb"), "node_path": res.get("node_path"),
                        "selected_label": res.get("selected_label") if hit else None,
                        "strategy": res.get("strategy") if hit else None, "exact": res.get("exact"),
                        "new_action": decision.action, "new_amount": float(decision.amount or 0.0),
                        "detail": str(res.get("detail") or "")[:120] if not hit else "",
                    })
                return decision

            api.request_action = wrapped
            api._flop_state = state
            last_key = key
        api._flop_state["hand"] = hand
        before = len(rows)
        comps = _replay_hand(api, hand, hero_id)
        flop_hist = [c["hist"] for c in comps if c.get("street") == "flop"]
        for r, hist in zip(rows[before:], flop_hist):
            r["hist_action"] = hist.get("action")
            r["hist_amount"] = float(hist.get("amount") or 0.0)
            r["big_blind"] = bb
    if since:
        pass
    if out:
        with open(out, "w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
    return rows


def summarize(rows: list, label: str) -> None:
    n = len(rows)
    hits = [r for r in rows if r["hit"]]
    print(f"== {label}: 翻牌决策 {n}，查书命中 {len(hits)} ({100 * len(hits) / max(n, 1):.1f}%) ==")
    print("   命中场景:", dict(sorted(Counter(r["scenario"] for r in hits).items())))
    print("   回退原因:", dict(Counter(r["reason"] for r in rows if not r["hit"]).most_common()))
    if hits:
        same = sum(1 for r in hits if r.get("hist_action") == r["new_action"])
        print(f"   命中时与日志实际动作类型一致 {same}/{len(hits)}；书的动作标签分布: {dict(Counter(r['selected_label'] for r in hits).most_common())}")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--book", default="")
    ap.add_argument("--json-log", action="append", default=[])
    ap.add_argument("--out", default="")
    ap.add_argument("--opponents-model", default="")
    ap.add_argument("--compare", nargs=2, metavar=("OLD_ROWS", "NEW_ROWS"))
    args = ap.parse_args(argv)
    if args.compare:
        old = [json.loads(l) for l in open(args.compare[0], encoding="utf-8")]
        new = [json.loads(l) for l in open(args.compare[1], encoding="utf-8")]
        assert len(old) == len(new), (len(old), len(new))
        summarize(old, "旧书")
        summarize(new, "新书")
        trans = Counter()
        for a, b in zip(old, new):
            assert (a["session"], a["hand"]) == (b["session"], b["hand"])
            trans[("命中" if a["hit"] else a["reason"], "命中" if b["hit"] else b["reason"])] += 1
        print("== 同一决策点 旧书→新书 ==")
        for (x, y), v in trans.most_common():
            if x != y:
                print(f"   {v:4d}  {x}  →  {y}")
        both = [(a, b) for a, b in zip(old, new) if a["hit"] and b["hit"]]
        diff = sum(1 for a, b in both if a["new_action"] != b["new_action"])
        print(f"   两本书都命中 {len(both)}，其中动作类型不同 {diff}")
        return
    rows = run(args.book, args.json_log, Path(args.out) if args.out else None, args.opponents_model)
    summarize(rows, args.book)


if __name__ == "__main__":
    main()
