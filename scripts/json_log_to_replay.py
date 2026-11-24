"""把 PokerFate 的结构化决策日志（pokerfate.log / archive/*.pokerfate.bak.log，JSONL）
转成 replay JSONL，供 scripts.replay_and_compare / replay_parallel 回放。

输出 JSONL 每行一手：
    {"hand": N, "session": k, "big_blind": bb, "dealer_id": id,
     "players": [...], "hole_cards": [...], "events": [...], "result": {...}}

用法：
    .venv/bin/python -m scripts.json_log_to_replay \
        --json-log pokerfate/logs/archive/2026-11-07.pokerfate.bak.log \
        --json-log pokerfate/logs/pokerfate.log \
        --out /path/to/replay.jsonl --source-label latest

注意单位：日志里所有筹码数字都是 chips（不是 BB）。replay 也用 chips。
旧的 console 文本解析器已删除：console 日志是给人看的渲染结果，时间戳格式一变
就全部失配（2026-11 实测 0 个决策点），JSON 日志才是唯一权威数据源。
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Optional

from scripts.hero_name import HeroNames, load_hero_names

# Windows 兜底：强制 stdout/stderr UTF-8
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except (AttributeError, OSError):
        pass


def parse_json_log(log_path: Path, hero_names: HeroNames, big_blind: float = 0.0) -> list[dict]:
    """把 pokerfate.log（结构化 JSONL 决策日志）转成 replay JSONL。

    与 console 解析器输出同一格式。JSON 日志里 ``opponent_action.amount`` 对
    call 是本次补入筹码、对 raise 是加注到的总额；replay 需要“跟到的总额”，
    这里按街累计换算。大盲按 session 取众数：每手先用翻前最小
    ``pot_before_action``/``decision.pot`` 除以 1.5 得到候选值，再用同一
    session（同一次 ``decision_engine_enabled``）内的众数覆盖。单手推断在
    hero 补盲入座（底池 2.5bb）或死盲（底池 1bb）时会差 1.67×/0.67×
    （2026-11-07..09 日志 3947 手里有 137 手），桌级盲注在一个 session 内不变。
    ``big_blind`` 参数非 0 时直接覆盖所有手。
    """
    hands: list[dict] = []
    cur: Optional[dict] = None
    session = 0
    with open(log_path, encoding="utf-8") as f:
        for raw in f:
            raw = raw.strip()
            if not raw.startswith("{"):
                continue
            try:
                r = json.loads(raw)
            except json.JSONDecodeError:
                continue
            e = r.get("event")
            if e == "decision_engine_enabled":
                session += 1
            if e == "hand_start":
                cur = {
                    "hand": r["hand"], "session": session, "dealer_id": r.get("dealer_id"),
                    "players": [
                        {"id": p["id"], "name": p["name"], "stack": p["stack"], "pos": p.get("pos")}
                        for p in r["players"]
                    ],
                    "hole_cards": [], "events": [], "_street_bets": {}, "_pots": [],
                }
                continue
            if cur is None:
                continue
            name_to_id = {p["name"]: p["id"] for p in cur["players"]}
            hero_id = next((p["id"] for p in cur["players"] if hero_names.matches(p["name"])), None)
            if e == "hole_cards":
                cur["hole_cards"] = list(r.get("cards") or [])
            elif e == "board":
                cur["events"].append({"type": "board", "street": r["street"], "cards": r["cards"]})
                cur["_street_bets"] = {}
            elif e == "opponent_action":
                pid = name_to_id.get(r["player"])
                if pid is None:
                    continue
                amt = float(r.get("amount") or 0)
                if r.get("street") == "preflop" and r.get("pot_before_action"):
                    cur["_pots"].append(float(r["pot_before_action"]))
                bets = cur["_street_bets"]
                if r["action"] == "call":
                    amt = bets.get(pid, 0.0) + amt
                    bets[pid] = amt
                elif r["action"] == "raise":
                    bets[pid] = amt
                opp_event = {"type": "opp_action", "pid": pid, "action": r["action"],
                             "amount": amt, "street": r["street"]}
                if r.get("pre_action"):
                    # ActionNotifyBRC.pre_action_result (1 reset, 2 pre-selected), logged since 2026-11-22
                    opp_event["pre_action"] = int(r["pre_action"])
                cur["events"].append(opp_event)
            elif e == "decision":
                if r.get("street") == "preflop" and r.get("pot"):
                    cur["_pots"].append(float(r["pot"]))
                cur["events"].append({"type": "decision", "street": r["street"], "pot": r["pot"],
                                      "to_call": r["to_call"], "action": r["action"],
                                      "amount": r["amount"], "equity": r.get("equity")})
                if r["action"] == "raise" and hero_id is not None:
                    cur["_street_bets"][hero_id] = float(r["amount"])
            elif e == "hand_result":
                cur["result"] = {
                    "winners": r.get("winners") or [], "pot": r.get("pot"),
                    "my_delta": r.get("my_delta"), "final_stacks": r.get("final_stacks") or {},
                    "showdown_hands": r.get("showdown_hands") or {},
                    # The server names the winner's hand type (高牌 / 一对 / ...) even when the
                    # pot is won without showdown: truth about bets nobody called.
                    "hand_combos": r.get("hand_combos") or {},
                }
                pots = [p for p in cur.pop("_pots") if p > 0]
                cur.pop("_street_bets", None)
                cur["big_blind"] = (min(pots) / 1.5) if pots else 0.0
                if cur["big_blind"] > 0:
                    hands.append(cur)
                cur = None
    _apply_session_big_blind(hands, big_blind)
    return hands


def _apply_session_big_blind(hands: list[dict], big_blind: float = 0.0) -> None:
    """Replace per-hand blind guesses with the session mode (or an override)."""
    if big_blind > 0:
        for h in hands:
            h["big_blind"] = float(big_blind)
        return
    by_session: dict[int, Counter] = {}
    for h in hands:
        # Round to 3 significant digits so 10000.0 and 10000.0000001 agree.
        guess = float(f"{h['big_blind']:.3g}")
        by_session.setdefault(h["session"], Counter())[guess] += 1
    for h in hands:
        counts = by_session.get(h["session"])
        if counts:
            h["big_blind"] = counts.most_common(1)[0][0]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json-log", action="append", required=True,
                    help="structured pokerfate.log (JSONL) file; can be passed multiple times")
    ap.add_argument("--out", required=True, help="replay JSONL output")
    ap.add_argument("--source-label", default="",
                    help="single source_log label written to every hand")
    ap.add_argument("--big-blind", type=float, default=0.0,
                    help="override the table big blind (chips) for every hand; "
                         "default infers the per-session mode from preflop pots")
    args = ap.parse_args()
    try:
        hero_names = load_hero_names()
    except RuntimeError as exc:
        ap.error(str(exc))

    hands = []
    session_offset = 0
    for log in args.json_log:
        parsed = parse_json_log(Path(log), hero_names, big_blind=args.big_blind)
        source = args.source_label or str(log)
        # Session numbers restart per file; make them unique across files so
        # the replay harness resets its API at every real process boundary
        # and (session, hand) identifies a hand across the whole replay.
        for h in parsed:
            h["source_log"] = source
            h["session"] += session_offset
        if parsed:
            session_offset = max(h["session"] for h in parsed)
        hands.extend(parsed)

    with open(args.out, "w", encoding='utf-8') as f:
        for h in hands:
            f.write(json.dumps(h, ensure_ascii=False) + "\n")

    print(f"解析 {len(hands)} 手 → {args.out}")
    decisions = sum(1 for h in hands for ev in h.get("events", []) if ev.get("type") == "decision")
    print(f"  决策点：{decisions}")
    if hands:
        print(f"  hand_no 范围：{min(h['hand'] for h in hands)} - {max(h['hand'] for h in hands)}")
        sources = sorted({h.get('source_log', '') for h in hands})
        print(f"  source_log：{', '.join(sources)}")


if __name__ == "__main__":
    main()
