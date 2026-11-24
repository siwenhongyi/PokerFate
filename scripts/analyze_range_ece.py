#!/usr/bin/env python3
"""Is the opponent-range model calibrated in live play?  (the web console's 校准评估 tab)

    .venv/bin/python scripts/analyze_range_ece.py                    # rows since the deployed bucket model
    .venv/bin/python scripts/analyze_range_ece.py --since 2026-11-13 # another window (date or epoch)
    .venv/bin/python scripts/analyze_range_ece.py --since 0          # everything, old models included

Reads local/training/*.rows.jsonl; rows about house robots are always left out.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pf_entertainment.range_nll import DEFAULT_RUNTIME_ROOT, range_nll_payload


def _since(text: str) -> float:
    try:
        return float(text)
    except ValueError:
        pass
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return time.mktime(time.strptime(text, fmt))
        except ValueError:
            continue
    raise argparse.ArgumentTypeError(f"not a date or epoch: {text!r}")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--runtime-root",
        type=Path,
        default=DEFAULT_RUNTIME_ROOT,
        help="runtime_calibration directory containing *.rows.jsonl",
    )
    parser.add_argument(
        "--since",
        type=_since,
        default=None,
        help="count rows recorded from this local date (YYYY-MM-DD[ HH:MM]) or epoch; "
             "default: when the deployed bucket model was written",
    )
    parser.add_argument("--json", action="store_true", help="print the full JSON payload")
    args = parser.parse_args(argv)

    payload = range_nll_payload(args.runtime_root, since=args.since)
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return

    for line in payload["conclusion"]:
        print(line)
    calibration = payload["calibration"]
    if calibration["by_bucket"]:
        print("\nbucket      rows   predicted  actual   bias")
        for row in calibration["by_bucket"]:
            print(f"  {row['key']:<9} {row['points']:>6}  {_pct(row['avg_pred']):>8}  {_pct(row['empirical']):>6}  {_signed(row['bias'])}")
    if calibration["by_cell"]:
        print("\nstrong+nuts share by street x action   rows  predicted  actual   diff (se)")
        for row in calibration["by_cell"]:
            flag = "" if row["label"] == "ok" else "  <-- outside tolerance"
            print(
                f"  {row['street']:<6} {row['action']:<11} {row['rows']:>6}  {_pct(row['predicted']):>8}  "
                f"{_pct(row['actual']):>6}  {_signed(row['diff'])} ({row['se'] * 100:.1f}){flag}"
            )
    if payload["by_street"]:
        print("\nrange updates (static NLL - updated NLL)   rows  improved   mean")
        for row in payload["by_street"]:
            print(f"  {row['key']:<8} {row['count']:>6}  {_pct(row['positive_rate']):>7}  {row['avg_delta_nll']:+.3f}")


def _pct(value: float) -> str:
    return f"{value * 100.0:.1f}%"


def _signed(value: float) -> str:
    return f"{value * 100.0:+.1f}"


if __name__ == "__main__":
    main()
