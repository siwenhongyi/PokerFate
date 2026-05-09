"""Replay console-derived hands and recompute Range V2 calibration metrics.

Use this after `scripts.parse_console_to_replay` has produced replay JSONL
with `result.showdown_hands` populated from the `◈ 学习` lines.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Optional

os.environ.setdefault("PYTEST_CURRENT_TEST", "scripts/replay_range_calibration.py")

from scripts.analyze_range_calibration import CalRow, render_markdown, summarize
from scripts.hero_name import load_hero_name
from scripts.replay_and_compare import _hero_id, _replay_hand, load_replay


class CalibrationCollector:
    def __init__(self) -> None:
        self.results = []

    def calibration_result(self, result) -> None:
        self.results.append(result)


def _cards_str(cards) -> str:
    return "".join(str(c) for c in cards)


def _rows_from_results(results: list, source: str) -> list[CalRow]:
    rows: list[CalRow] = []
    for idx, result in enumerate(results, 1):
        rec = result.record
        if rec.predicted_hero_eq is None or result.actual_hero_eq_street is None:
            continue
        rows.append(CalRow(
            source=source,
            line_no=idx,
            street=rec.street,
            player=rec.player_name,
            trigger=rec.trigger,
            bucket=result.actual_bucket,
            cards=_cards_str(result.actual_cards),
            bucket_pct=float(result.predicted_bucket_prob or 0.0),
            pred_hu=float(rec.predicted_hero_eq),
            actual_hu=float(result.actual_hero_eq_street),
            pred_multi=(
                float(rec.predicted_hero_eq_multi)
                if rec.predicted_hero_eq_multi is not None else None
            ),
            actual_multi=(
                float(result.actual_hero_eq_street_multi)
                if result.actual_hero_eq_street_multi is not None else None
            ),
        ))
    return rows


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--replay", type=Path, required=True)
    ap.add_argument("--max-hands", type=int, default=0)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--equity-iterations", type=int, default=200)
    ap.add_argument("--sample-scale", type=float, default=1.0,
                    help="scale ShowdownCalibrator MC samples for faster sweeps")
    ap.add_argument("--format", choices=("markdown", "json"), default="markdown")
    ap.add_argument("--top", type=int, default=20)
    ap.add_argument("--min-n", type=int, default=20)
    ap.add_argument("--progress-every", type=int, default=100)
    args = ap.parse_args()

    try:
        hero_name = load_hero_name()
    except RuntimeError as exc:
        ap.error(str(exc))

    if args.sample_scale != 1.0:
        scale = max(0.02, float(args.sample_scale))
        sample_defaults = {
            "PF_CAL_PRED_EQ_SAMPLES": 500,
            "PF_CAL_ACTUAL_EQ_PREFLOP_SAMPLES": 3000,
            "PF_CAL_ACTUAL_EQ_FLOP_SAMPLES": 1800,
            "PF_CAL_ACTUAL_EQ_TURN_SAMPLES": 1200,
            "PF_CAL_ACTUAL_EQ_RIVER_UNSHOWN_SAMPLES": 2000,
        }
        for key, default in sample_defaults.items():
            os.environ[key] = str(max(20, int(default * scale)))

    from pokerfate.api import PokerFateAPI

    hands = load_replay(args.replay)
    if args.max_hands > 0:
        hands = hands[:args.max_hands]

    collector = CalibrationCollector()
    last_session = None
    api: Optional[PokerFateAPI] = None
    played = 0
    skipped_no_hero = 0

    for idx, hand in enumerate(hands, 1):
        hero_id = _hero_id(hand.get("players", []), hero_name)
        if hero_id is None:
            skipped_no_hero += 1
            continue
        session = hand.get("session", 0)
        if session != last_session or api is None or hero_id != api.my_player_id:
            api = PokerFateAPI(
                my_player_id=hero_id,
                big_blind=2.0,
                autosave_path=None,
                log_file=None,
                verbose=False,
                equity_iterations=args.equity_iterations,
                enable_showdown_calibration=True,
                decision_seed=args.seed,
            )
            api._log._console = False
            if api._calibrator is not None:
                api._calibrator._logger = collector
            last_session = session

        _replay_hand(api, hand, hero_id)
        played += 1
        if args.progress_every > 0 and played % args.progress_every == 0:
            print(
                f"replayed {played}/{len(hands)} hands, "
                f"cal_rows={len(collector.results)}",
                file=sys.stderr,
                flush=True,
            )

    rows = _rows_from_results(collector.results, str(args.replay))
    summary = summarize(rows)
    summary["_meta"] = {
        "replay": str(args.replay),
        "hands_seen": len(hands),
        "hands_replayed": played,
        "skipped_no_hero": skipped_no_hero,
        "calibration_results": len(collector.results),
        "rows": len(rows),
        "equity_iterations": args.equity_iterations,
        "sample_scale": args.sample_scale,
    }

    if args.format == "json":
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print(render_markdown(summary, top=args.top, min_n=args.min_n))
        print(
            "\n_meta: "
            + json.dumps(summary["_meta"], ensure_ascii=False, sort_keys=True)
        )


if __name__ == "__main__":
    main()
