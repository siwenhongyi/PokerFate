"""Analyze Range V2 showdown calibration lines from console logs.

The input is the human console log line emitted as:
    ⚖ river name action:check 实际桶=坚果(...,此桶=12%) ...

This script is intentionally streaming: large archived logs can be scanned
without loading whole hands into memory.
"""

from __future__ import annotations

import argparse
import json
import math
import re
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable


CAL_RE = re.compile(
    r"⚖\s+"
    r"(?P<street>\w+)\s+"
    r"(?P<player>.+?)\s+"
    r"(?P<trigger>(?:action|board):\w+|reset)\s+"
    r"实际桶=(?P<bucket>[^\s(]+)"
    r"\((?P<cards>[^,]+),此桶=(?P<bucket_pct>\d+)%\)\s+"
    r"eq预单挑=(?P<pred_hu>\d+)%\s+"
    r"实单挑=(?P<actual_hu>\d+)%\s+"
    r"Δ=(?P<delta>[+-]?\d+)%[✓↑↓]"
    r"(?:\s+预全场=(?P<pred_multi>\d+)%\s+"
    r"实全场=(?:(?P<actual_multi>\d+)%|(?P<actual_multi_dash>—)))?"
)


@dataclass
class CalRow:
    source: str
    line_no: int
    street: str
    player: str
    trigger: str
    bucket: str
    cards: str
    bucket_pct: float
    pred_hu: float
    actual_hu: float
    pred_multi: float | None
    actual_multi: float | None

    @property
    def err_hu(self) -> float:
        return self.pred_hu - self.actual_hu

    @property
    def err_multi(self) -> float | None:
        if self.pred_multi is None or self.actual_multi is None:
            return None
        return self.pred_multi - self.actual_multi


class Stat:
    def __init__(self) -> None:
        self.n = 0
        self.sum_err = 0.0
        self.sum_abs = 0.0
        self.sum_sq = 0.0
        self.sum_pred = 0.0
        self.sum_actual = 0.0
        self.sum_bucket_pct = 0.0
        self.false_high = 0
        self.false_low = 0
        self.bucket_under_10 = 0
        self.multi_n = 0
        self.multi_sum_err = 0.0
        self.multi_sum_abs = 0.0

    def add(self, row: CalRow) -> None:
        err = row.err_hu
        self.n += 1
        self.sum_err += err
        self.sum_abs += abs(err)
        self.sum_sq += err * err
        self.sum_pred += row.pred_hu
        self.sum_actual += row.actual_hu
        self.sum_bucket_pct += row.bucket_pct
        if row.pred_hu >= 0.65 and row.actual_hu <= 0.20:
            self.false_high += 1
        if row.pred_hu <= 0.20 and row.actual_hu >= 0.65:
            self.false_low += 1
        if row.bucket_pct < 0.10:
            self.bucket_under_10 += 1
        err_m = row.err_multi
        if err_m is not None:
            self.multi_n += 1
            self.multi_sum_err += err_m
            self.multi_sum_abs += abs(err_m)

    def to_dict(self) -> dict:
        return {
            "n": self.n,
            "bias_pp": _pp(self.sum_err / self.n) if self.n else 0.0,
            "mae_pp": _pp(self.sum_abs / self.n) if self.n else 0.0,
            "rmse_pp": _pp(math.sqrt(self.sum_sq / self.n)) if self.n else 0.0,
            "pred_avg_pct": _pct(self.sum_pred / self.n) if self.n else 0.0,
            "actual_avg_pct": _pct(self.sum_actual / self.n) if self.n else 0.0,
            "bucket_avg_pct": _pct(self.sum_bucket_pct / self.n) if self.n else 0.0,
            "bucket_under_10": self.bucket_under_10,
            "false_high": self.false_high,
            "false_low": self.false_low,
            "multi_n": self.multi_n,
            "multi_bias_pp": (
                _pp(self.multi_sum_err / self.multi_n) if self.multi_n else None
            ),
            "multi_mae_pp": (
                _pp(self.multi_sum_abs / self.multi_n) if self.multi_n else None
            ),
        }


def _pct(x: float) -> float:
    return round(x * 100.0, 1)


def _pp(x: float) -> float:
    return round(x * 100.0, 1)


def _fmt_pp(x: float | None) -> str:
    if x is None:
        return "-"
    return f"{x:+.1f}pp"


def _fmt_pct(x: float | None) -> str:
    if x is None:
        return "-"
    return f"{x:.1f}%"


def iter_rows(paths: Iterable[Path]) -> tuple[list[CalRow], int]:
    rows: list[CalRow] = []
    parse_failures = 0
    for path in paths:
        with path.open("r", encoding="utf-8", errors="replace") as f:
            for line_no, line in enumerate(f, 1):
                if "⚖" not in line:
                    continue
                m = CAL_RE.search(line)
                if not m:
                    parse_failures += 1
                    continue
                gd = m.groupdict()
                pred_multi = (
                    int(gd["pred_multi"]) / 100.0
                    if gd.get("pred_multi") is not None else None
                )
                actual_multi = (
                    int(gd["actual_multi"]) / 100.0
                    if gd.get("actual_multi") is not None else None
                )
                rows.append(CalRow(
                    source=str(path),
                    line_no=line_no,
                    street=gd["street"],
                    player=gd["player"],
                    trigger=gd["trigger"],
                    bucket=gd["bucket"],
                    cards=gd["cards"],
                    bucket_pct=int(gd["bucket_pct"]) / 100.0,
                    pred_hu=int(gd["pred_hu"]) / 100.0,
                    actual_hu=int(gd["actual_hu"]) / 100.0,
                    pred_multi=pred_multi,
                    actual_multi=actual_multi,
                ))
    return rows, parse_failures


def add_group(groups: dict[str, Stat], key: str, row: CalRow) -> None:
    groups[key].add(row)


def summarize(rows: list[CalRow]) -> dict:
    groups: dict[str, dict[str, Stat]] = {
        "street": defaultdict(Stat),
        "trigger": defaultdict(Stat),
        "street_trigger": defaultdict(Stat),
        "street_bucket": defaultdict(Stat),
        "trigger_bucket": defaultdict(Stat),
        "player": defaultdict(Stat),
    }
    overall = Stat()
    for row in rows:
        overall.add(row)
        add_group(groups["street"], row.street, row)
        add_group(groups["trigger"], row.trigger, row)
        add_group(groups["street_trigger"], f"{row.street} {row.trigger}", row)
        add_group(groups["street_bucket"], f"{row.street} {row.bucket}", row)
        add_group(groups["trigger_bucket"], f"{row.trigger} {row.bucket}", row)
        add_group(groups["player"], row.player, row)
    return {
        "overall": overall.to_dict(),
        "groups": {
            name: {key: stat.to_dict() for key, stat in stats.items()}
            for name, stats in groups.items()
        },
        "extremes": {
            "false_high": [asdict(r) for r in _extreme(rows, "false_high")],
            "false_low": [asdict(r) for r in _extreme(rows, "false_low")],
            "abs_error": [asdict(r) for r in _extreme(rows, "abs_error")],
        },
    }


def _extreme(rows: list[CalRow], mode: str, limit: int = 20) -> list[CalRow]:
    if mode == "false_high":
        picked = [r for r in rows if r.pred_hu >= 0.65 and r.actual_hu <= 0.20]
        return sorted(picked, key=lambda r: r.err_hu, reverse=True)[:limit]
    if mode == "false_low":
        picked = [r for r in rows if r.pred_hu <= 0.20 and r.actual_hu >= 0.65]
        return sorted(picked, key=lambda r: r.err_hu)[:limit]
    return sorted(rows, key=lambda r: abs(r.err_hu), reverse=True)[:limit]


def _stat_rows(group: dict[str, dict], *, limit: int,
               min_n: int = 1, sort_key: str = "mae_pp") -> list[list[str]]:
    items = [
        (key, stat) for key, stat in group.items()
        if int(stat["n"]) >= min_n
    ]
    items.sort(key=lambda kv: (kv[1].get(sort_key) or 0, kv[1]["n"]),
               reverse=True)
    out: list[list[str]] = []
    for key, stat in items[:limit]:
        out.append([
            key,
            str(stat["n"]),
            _fmt_pp(stat["bias_pp"]),
            _fmt_pp(stat["mae_pp"]).replace("+", ""),
            str(stat["false_high"]),
            str(stat["false_low"]),
            _fmt_pct(stat["bucket_avg_pct"]),
            str(stat["bucket_under_10"]),
        ])
    return out


def _table(headers: list[str], rows: list[list[str]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def render_markdown(summary: dict, *, top: int, min_n: int) -> str:
    overall = summary["overall"]
    groups = summary["groups"]
    lines = [
        "# Range V2 Calibration Analysis",
        "",
        "## Overall",
        "",
        _table(
            ["rows", "bias", "MAE", "RMSE", "false-high", "false-low"],
            [[
                str(overall["n"]),
                _fmt_pp(overall["bias_pp"]),
                _fmt_pp(overall["mae_pp"]).replace("+", ""),
                _fmt_pp(overall["rmse_pp"]).replace("+", ""),
                str(overall["false_high"]),
                str(overall["false_low"]),
            ]],
        ),
        "",
        "## By Street",
        "",
        _table(
            ["key", "n", "bias", "MAE", "false-high", "false-low",
             "bucket avg", "bucket<10"],
            _stat_rows(groups["street"], limit=top, min_n=min_n),
        ),
        "",
        "## High-Risk Street/Trigger",
        "",
        _table(
            ["key", "n", "bias", "MAE", "false-high", "false-low",
             "bucket avg", "bucket<10"],
            _stat_rows(groups["street_trigger"], limit=top, min_n=min_n),
        ),
        "",
        "## Street/Bucket",
        "",
        _table(
            ["key", "n", "bias", "MAE", "false-high", "false-low",
             "bucket avg", "bucket<10"],
            _stat_rows(groups["street_bucket"], limit=top, min_n=min_n),
        ),
        "",
        "## False-High Samples",
        "",
        _sample_table(summary["extremes"]["false_high"][:top]),
        "",
        "## False-Low Samples",
        "",
        _sample_table(summary["extremes"]["false_low"][:top]),
    ]
    return "\n".join(lines)


def _sample_table(rows: list[dict]) -> str:
    body = []
    for r in rows:
        err = float(r["pred_hu"]) - float(r["actual_hu"])
        body.append([
            f"{Path(r['source']).name}:{r['line_no']}",
            r["street"],
            r["trigger"],
            r["bucket"],
            r["cards"],
            _fmt_pct(_pct(r["pred_hu"])),
            _fmt_pct(_pct(r["actual_hu"])),
            _fmt_pp(_pp(err)),
            _fmt_pct(_pct(r["bucket_pct"])),
            r["player"],
        ])
    return _table(
        ["loc", "street", "trigger", "bucket", "cards", "pred", "actual",
         "err", "bucket%", "player"],
        body,
    )


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--log", action="append", required=True,
                    help="console log path; may be passed multiple times")
    ap.add_argument("--format", choices=("markdown", "json"),
                    default="markdown")
    ap.add_argument("--top", type=int, default=20)
    ap.add_argument("--min-n", type=int, default=20,
                    help="minimum group sample count in markdown tables")
    args = ap.parse_args()

    rows, failures = iter_rows(Path(p) for p in args.log)
    summary = summarize(rows)
    summary["parse_failures"] = failures
    summary["sources"] = args.log

    if args.format == "json":
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print(render_markdown(summary, top=args.top, min_n=args.min_n))
        if failures:
            print(f"\nparse_failures: {failures}")


if __name__ == "__main__":
    main()
