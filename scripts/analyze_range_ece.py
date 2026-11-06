#!/usr/bin/env python3
"""Print offline Range V2 NLL and bucket ECE analysis."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pf_entertainment.range_nll import DEFAULT_RUNTIME_ROOT, range_nll_payload


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--runtime-root",
        type=Path,
        default=DEFAULT_RUNTIME_ROOT,
        help="runtime_calibration directory containing bb_*/*.rows.jsonl",
    )
    parser.add_argument("--json", action="store_true", help="print full JSON payload")
    args = parser.parse_args()

    payload = range_nll_payload(args.runtime_root)
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return

    summary = payload.get("summary") or {}
    calibration = payload.get("calibration") or {}
    overall = calibration.get("overall") or {}
    cec = payload.get("cec_integration") or {}
    cec_overall = cec.get("overall") or {}
    print("Range NLL / ECE")
    print(f"runtime_root: {summary.get('runtime_root')}")
    print(
        "rows={rows} exact={count} hands={hands} skipped={skipped}".format(
            rows=summary.get("rows", 0),
            count=summary.get("count", 0),
            hands=summary.get("hands", 0),
            skipped=summary.get("skipped", 0),
        )
    )
    print(
        "avg_delta_nll={delta} positive_rate={pos} winner={winner}".format(
            delta=_fmt(summary.get("avg_delta_nll")),
            pos=_pct(summary.get("positive_rate")),
            winner=summary.get("winner", "-"),
        )
    )
    print(
        "bucket_ece={ece} top_bucket_accuracy={top}".format(
            ece=_fmt(overall.get("ece")),
            top=_pct(overall.get("top_bucket_accuracy")),
        )
    )
    print(
        "cec_integration nll_gain={nll} ece_gain={ece} winner={winner}".format(
            nll=_signed(cec_overall.get("nll_gain")),
            ece=_signed(cec_overall.get("ece_gain")),
            winner=cec_overall.get("winner", "-"),
        )
    )
    print()
    print("Calibration hotspots:")
    for item in list(calibration.get("hotspots") or [])[:12]:
        print(
            "  {source}:{key} points={points} ece={ece} pred={pred} actual={actual} bias={bias} {label}".format(
                source=item.get("source", "-"),
                key=item.get("key", "-"),
                points=item.get("points", 0),
                ece=_fmt(item.get("ece")),
                pred=_pct(item.get("avg_pred")),
                actual=_pct(item.get("empirical")),
                bias=_signed_pct(item.get("bias")),
                label=item.get("bias_label", "-"),
            )
        )
    print()
    print("CEC integration hotspots:")
    for item in list(cec.get("hotspots") or [])[:12]:
        print(
            "  {source}:{key} n={count} nll_gain={nll} ece_gain={ece} rel={rel} winner={winner}".format(
                source=item.get("source", "-"),
                key=item.get("key", "-"),
                count=item.get("count", 0),
                nll=_signed(item.get("nll_gain")),
                ece=_signed(item.get("ece_gain")),
                rel=_pct(item.get("avg_reliability")),
                winner=item.get("winner", "-"),
            )
        )


def _fmt(value: object) -> str:
    if value is None:
        return "-"
    try:
        return f"{float(value):.4f}"
    except Exception:
        return "-"


def _pct(value: object) -> str:
    if value is None:
        return "-"
    try:
        return f"{float(value) * 100.0:.1f}%"
    except Exception:
        return "-"


def _signed_pct(value: object) -> str:
    if value is None:
        return "-"
    try:
        raw = float(value) * 100.0
    except Exception:
        return "-"
    return f"{raw:+.1f}%"


def _signed(value: object) -> str:
    if value is None:
        return "-"
    try:
        raw = float(value)
    except Exception:
        return "-"
    return f"{raw:+.4f}"


if __name__ == "__main__":
    main()
