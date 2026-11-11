"""Closed-loop scoring of bucket-calibration rows against revealed showdown hands.

Workflow (the acceptance test for any bucket-ML candidate, see
docs/range_v2_bucket_ml.md):

  1. python -m scripts.extract_range_calibration_rows_parallel --replay R.jsonl --mode bucket \\
         --bucket-calibration current --out rows_off.jsonl      (PF_BUCKET_ML=off)
  2. PF_BUCKET_ML=lgbm PF_BUCKET_ML_MODEL_PATH=candidate.json  ... --out rows_on.jsonl
  3. python -m scripts.score_bucket_rows rows_off.jsonl rows_on.jsonl [more.jsonl ...]

Rows are joined on (hand, player, street, trigger, board). The first file is the
baseline; every other file is reported as a paired difference against it:
bucket Brier, bucket NLL, and the strong+nuts mass bias per (street, trigger)
cell. Because the extractor runs the real tracker (hook fires after the
bucket-ML overlay), this measures exactly what the bot would have believed live.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

CAT_ORDER = ("nuts", "strong", "medium", "draw", "weak_draw", "air")
EPS = 1e-6


def _iter_rows(path: Path):
    dec = json.JSONDecoder()
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            s = line.strip()
            i = 0
            while i < len(s):
                if s[i] != "{":
                    i += 1
                    continue
                try:
                    obj, j = dec.raw_decode(s, i)
                except Exception:
                    break
                i = j
                yield obj


def load(path: Path, streets: set[str]) -> dict[tuple, dict[str, Any]]:
    out: dict[tuple, dict[str, Any]] = {}
    for r in _iter_rows(path):
        if r.get("street") not in streets or not r.get("actual_bucket"):
            continue
        key = (r.get("hand"), str(r.get("player_uid")), r.get("street"), r.get("trigger"), tuple(r.get("board") or []))
        out[key] = r
    return out


def _probs(r: dict[str, Any]) -> list[float]:
    d = r.get("bucket_dist") or {}
    p = [max(0.0, float(d.get(c, 0.0) or 0.0)) for c in CAT_ORDER]
    t = sum(p)
    return [x / t for x in p] if t > 0 else [1.0 / len(CAT_ORDER)] * len(CAT_ORDER)


def brier(r: dict[str, Any]) -> float:
    p = _probs(r)
    y = r["actual_bucket"]
    return sum((pi - (1.0 if c == y else 0.0)) ** 2 for pi, c in zip(p, CAT_ORDER))


def nll(r: dict[str, Any]) -> float:
    p = dict(zip(CAT_ORDER, _probs(r)))
    return -math.log(max(EPS, p.get(r["actual_bucket"], 0.0)))


def mass(r: dict[str, Any]) -> float:
    p = dict(zip(CAT_ORDER, _probs(r)))
    return p["nuts"] + p["strong"]


def paired(a: list[float], b: list[float]) -> tuple[float, float]:
    d = [y - x for x, y in zip(a, b)]
    n = len(d)
    if n < 2:
        return (sum(d) / n if n else 0.0), 0.0
    m = sum(d) / n
    se = math.sqrt(sum((x - m) ** 2 for x in d) / (n - 1) / n)
    return m, se


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("rows", nargs="+", type=Path, help="baseline rows first, then candidates")
    ap.add_argument("--streets", default="flop,turn,river")
    ap.add_argument("--min-cell-rows", type=int, default=50)
    ap.add_argument("--json-out", type=Path)
    args = ap.parse_args()
    streets = {s.strip() for s in args.streets.split(",") if s.strip()}
    data = [load(p, streets) for p in args.rows]
    labels = [p.stem for p in args.rows]
    common = set(data[0])
    for d in data[1:]:
        common &= set(d)
    keys = sorted(common, key=lambda k: (str(k[0]), k[1], k[2], k[3]))
    print(f"common rows: {len(keys)}")
    report: dict[str, Any] = {"common_rows": len(keys), "cells": {}, "paired": {}}

    cells: dict[tuple, list] = defaultdict(list)
    for k in keys:
        cells[(k[2], k[3])].append(k)
    base = data[0]
    header = f"{'street trigger':26s} {'n':>5s} {'actual':>7s} | " + " | ".join(f"{lab[:14]:>14s}" for lab in labels)
    print(header)
    print("  (mean predicted strong+nuts mass; actual = share of revealed hands in strong/nuts)")
    for cell in sorted(cells):
        ks = cells[cell]
        if len(ks) < args.min_cell_rows:
            continue
        actual = sum(1 for k in ks if base[k]["actual_bucket"] in ("nuts", "strong")) / len(ks)
        preds = [sum(mass(d[k]) for k in ks) / len(ks) for d in data]
        report["cells"][f"{cell[0]} {cell[1]}"] = {"n": len(ks), "actual": actual, "pred": dict(zip(labels, preds))}
        print(f"{cell[0]:5s} {cell[1]:20s} {len(ks):5d} {actual:7.3f} | " + " | ".join(f"{p:14.3f}" for p in preds))

    print("\npaired differences vs baseline (negative = candidate better):")
    for lab, d in zip(labels[1:], data[1:]):
        out = {}
        for name, fn in (("brier", brier), ("nll", nll)):
            m, se = paired([fn(base[k]) for k in keys], [fn(d[k]) for k in keys])
            out[name] = {"delta": m, "se": se}
        bias_b = sum(mass(base[k]) for k in keys) / len(keys) - sum(1 for k in keys if base[k]["actual_bucket"] in ("nuts", "strong")) / len(keys)
        bias_c = sum(mass(d[k]) for k in keys) / len(keys) - sum(1 for k in keys if base[k]["actual_bucket"] in ("nuts", "strong")) / len(keys)
        out["mass_bias"] = {"baseline": bias_b, "candidate": bias_c}
        report["paired"][lab] = out
        print(f"  {lab:24s} ΔBrier {out['brier']['delta']:+.4f} ± {out['brier']['se']:.4f}   ΔNLL {out['nll']['delta']:+.4f} ± {out['nll']['se']:.4f}   mass bias {bias_b:+.3f} → {bias_c:+.3f}")
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
