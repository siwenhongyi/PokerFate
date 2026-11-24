"""How the reads from pre-selected actions do in live play, from the bot's own log.

    .venv/bin/python -m analysis.pre_action_live pokerfate/logs/pokerfate.log [more logs ...]

The log carries the table's flag on every opponent action since 2026-11-22
(``opponent_action.pre_action``); the reads are rebuilt from it with the bot's own rule
(``pre_action.update_read``).  Counted on hero's bets into a field in which somebody
pre-selected a check:

* how often such a player folds to the bet (fitted: about 4 in 5);
* how often everybody folds, against the fitted probability (``pre_action.field_fold_prob``);
* the same for the bets made by the ``read_stab`` purpose alone.

Stop rules agreed on 2026-11-22 (switch off with ``PF_PRE_ACTION=off`` and refit when one
fires): the players with a read fold under 60% of at least 150 answers; or everybody folds
to at least 120 ``read_stab`` bets more than 12 points less often than fitted.
"""
from __future__ import annotations

import json
import math
import sys
from collections import Counter
from pathlib import Path
from typing import Dict, List, Optional

from analysis.pflog import _load_hero_names
from pokerfate.strategy import pre_action

MIN_ANSWERS, MIN_FOLD_RATE = 150, 0.60
MIN_STABS, MAX_SHORTFALL = 120, 0.12


def _events(path: Path):
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if line.startswith("{"):
                try:
                    yield json.loads(line)
                except ValueError:
                    continue


def collect(paths: List[Path]) -> Counter:
    hero_names = _load_hero_names()
    out: Counter = Counter()
    for path in paths:
        hand = None
        live: set = set()
        reads: Dict[str, Optional[pre_action.Read]] = {}
        open_bet: Optional[dict] = None       # hero's bet waiting for the field's answers

        def settle() -> None:
            nonlocal open_bet
            if open_bet is None:
                return
            b = open_bet
            open_bet = None
            everyone = not b["stayed"] and b["folded"] >= b["field"]
            for tag in b["tags"]:
                out[tag + "_bets"] += 1
                out[tag + "_all_fold"] += everyone
                out[tag + "_fitted"] += b["fitted"]

        for d in _events(path):
            e = d.get("event")
            if e == "hand_start":
                settle()
                hand = d.get("hand")
                live = {p["name"] for p in d.get("players", []) if p["name"] not in hero_names}
                reads = {}
                out["hands"] += 1
            elif d.get("hand") != hand:
                continue
            elif e in ("board", "hand_result"):
                settle()
            elif e == "opponent_action":
                who, street, action = d.get("player"), str(d.get("street") or ""), str(d.get("action") or "")
                key = pre_action.read_key(reads.get(who), street)
                if open_bet is not None and who in open_bet["waiting"]:
                    open_bet["waiting"].discard(who)
                    folded = action == "fold"
                    open_bet["folded"] += folded
                    open_bet["stayed"] += not folded
                    if key in pre_action.WEAK_KEYS:
                        out["answers"] += 1
                        out["answers_fold"] += folded
                        out["answers_" + key] += 1
                        out["answers_fold_" + key] += folded
                reads[who] = pre_action.update_read(reads.get(who), street=street, action=action,
                                                    pre_action=int(d.get("pre_action") or 0))
                if action == "fold":
                    live.discard(who)
            elif e == "decision":
                settle()
                street = str(d.get("street") or "")
                if street == "preflop" or not live:
                    continue
                keys = [pre_action.read_key(reads.get(name), street) for name in sorted(live)]
                weak = sum(k in pre_action.WEAK_KEYS for k in keys)
                if not weak:
                    continue
                out["read_spots"] += 1
                pot, bet = float(d.get("pot") or 0), float(d.get("amount") or 0)
                if float(d.get("to_call") or 0) > 0 or pot <= 0:
                    continue
                out["read_spots_open"] += 1
                if d.get("action") != "raise" or bet <= 0:
                    continue
                fitted = pre_action.field_fold_prob(street, keys[:4], bet / pot)
                tags = ["read"] + (["stab"] if d.get("final_purpose") == "read_stab" else [])
                open_bet = {"waiting": set(live), "field": len(live), "folded": 0, "stayed": 0,
                            "fitted": float(fitted or 0.0), "tags": tags}
        settle()
    return out


def _rate(k: int, n: int) -> str:
    if not n:
        return "n/a"
    p = k / n
    return f"{100 * p:.1f}% ± {196 * math.sqrt(p * (1 - p) / n):.1f} ({k}/{n})"


def report(c: Counter) -> None:
    print(f"hands {c['hands']} | decisions with a pre-selected checker in the field {c['read_spots']}"
          f" | of them with nothing to call {c['read_spots_open']}")
    print("players with a read answering hero's bet: fold", _rate(c["answers_fold"], c["answers"]))
    for key in pre_action.WEAK_KEYS:
        if c["answers_" + key]:
            print(f"    {key}: fold", _rate(c["answers_fold_" + key], c["answers_" + key]))
    for tag, title in (("read", "hero's bets into such a field"), ("stab", "read_stab bets")):
        n = c[tag + "_bets"]
        fitted = f"{100 * c[tag + '_fitted'] / n:.1f}%" if n else "n/a"
        print(f"{title}: everybody folded", _rate(c[tag + "_all_fold"], n), "| fitted", fitted)
    rule1 = c["answers"] >= MIN_ANSWERS and c["answers_fold"] / c["answers"] < MIN_FOLD_RATE
    stabs = c["stab_bets"]
    rule2 = stabs >= MIN_STABS and (c["stab_fitted"] - c["stab_all_fold"]) / stabs > MAX_SHORTFALL
    print(f"stop rule 1 (fold rate under {MIN_FOLD_RATE:.0%} after {MIN_ANSWERS} answers):",
          "FIRES" if rule1 else ("holds" if c["answers"] >= MIN_ANSWERS else f"too early ({c['answers']}/{MIN_ANSWERS})"))
    print(f"stop rule 2 (everybody folds {MAX_SHORTFALL:.0%} under fitted after {MIN_STABS} stabs):",
          "FIRES" if rule2 else ("holds" if stabs >= MIN_STABS else f"too early ({stabs}/{MIN_STABS})"))


def main(argv: Optional[list] = None) -> None:
    paths = [Path(p) for p in (argv if argv is not None else sys.argv[1:])]
    if not paths:
        raise SystemExit(__doc__)
    report(collect(paths))


if __name__ == "__main__":
    main()
