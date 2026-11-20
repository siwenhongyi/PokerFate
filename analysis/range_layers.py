"""How far is each step of a range update from the hands we get to see at showdown?

    # 1. rows with the bucket model off (the formula layer alone), following the table rule
    .venv/bin/python -m scripts.json_log_to_replay --json-log <logs...> --out replay.jsonl
    DECISION_ENGINE=local PF_BUCKET_ML=off PF_G5_SHADOW_ENABLED=0 \\
        .venv/bin/python -m scripts.extract_range_calibration_rows_parallel \\
        --replay replay.jsonl --mode bucket --out rows.jsonl --parts-dir parts
    # 2. this report
    .venv/bin/python -m analysis.range_layers rows.jsonl

An opponent's range is updated on every action: fitted action likelihood -> floor mixing
(-> bucket model, which is fitted on top and has to be retrained whenever anything below
changes).  For every action row the extractor keeps the bucket shares before the action and
after each step; this prints, per (street, action), how far the strong + nuts share is from
the share actually held, then the same by bet size, kind of opponent and players in the pot.
Bets nobody called are scored by ``python -m analysis.type_truth``.
"""
from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from pathlib import Path

LAYERS = ("pre", "likelihood", "floor")
STREETS = {"flop": 0, "turn": 1, "river": 2}


def iter_rows(paths):
    dec = json.JSONDecoder()
    for path in paths:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                i = 0
                while i < len(line):                   # part files may hold several records per line
                    if line[i] != "{":
                        i += 1
                        continue
                    try:
                        row, i = dec.raw_decode(line, i)
                    except json.JSONDecodeError:
                        break
                    yield row


def slice_names(action: str, features: dict) -> list:
    """The cuts the acceptance test looks at besides (street, action): bet size, who, how many."""
    features = features or {}
    names = []
    if action in ("bet", "raise_over"):
        size = ("小注" if features.get("size_small") else "三分之二池" if features.get("size_two_third")
                else "满池及以上" if features.get("size_pot") else "半池")
        names.append(f"尺寸 {size}")
        names.append(f"人数 {action} " + ("4人以上" if features.get("pot_four_plus") else "2-3人"))
    if action in ("bet", "call"):
        who = ("不认识(<30手)" if float(features.get("known") or 0.0) < 0.5
               else "紧手" if float(features.get("tight") or 0.0) > 0 else "松手")
        names.append(f"对手 {action} {who}")
    return names


def collect(rows):
    """(by cell, by slice); each value = [n, held, {layer: [sum of (pred - held), sum of squares]}]."""
    def new():
        return [0, 0.0, {name: [0.0, 0.0] for name in LAYERS}]
    cells, cuts = defaultdict(new), defaultdict(new)
    for row in rows:
        layers = row.get("layers")
        if not layers or row.get("street") not in STREETS or not row.get("actual_bucket"):
            continue
        if any("strong" not in (layers.get(name) or {}) for name in LAYERS):
            continue
        held = 1.0 if row["actual_bucket"] in ("nuts", "strong") else 0.0
        action = str(row.get("trigger") or "").split(":", 1)[-1]
        targets = [(cells, (row["street"], action))]
        targets += [(cuts, name) for name in slice_names(action, row.get("features"))]
        for store, key in targets:
            acc = store[key]
            acc[0] += 1
            acc[1] += held
            for name in LAYERS:
                diff = layers[name]["nuts"] + layers[name]["strong"] - held
                acc[2][name][0] += diff
                acc[2][name][1] += diff * diff
    return cells, cuts


def bias(acc, name):
    """(mean of predicted - held in points, standard error)."""
    n = acc[0]
    mean = acc[2][name][0] / n
    return 100 * mean, 100 * math.sqrt(max(acc[2][name][1] / n - mean * mean, 0.0) / n)


def report(cells, cuts, min_rows: int) -> None:
    print("强牌+坚果占比：每一步之后的预测减实际（百分点）。\n")
    print(f"{'街道 动作':16s} {'行数':>6s} {'实际':>6s} | {'动作前':>7s} {'似然后':>7s} {'下限混合后':>9s} (标准误)")
    for key in sorted(cells, key=lambda k: (STREETS[k[0]], k[1])):
        acc = cells[key]
        if acc[0] < min_rows:
            continue
        values = [bias(acc, name) for name in LAYERS]
        print(f"{key[0] + ' ' + key[1]:18s} {acc[0]:6d} {100 * acc[1] / acc[0]:6.1f} | "
              + " ".join(f"{v[0]:+9.1f}" for v in values) + f"   ({values[-1][1]:.1f})")
    if cuts:
        print("\n按下注尺寸、对手类型、池内人数切（公式层输出，预测减实际，百分点）\n")
        for name in sorted(cuts):
            acc = cuts[name]
            if acc[0] < min_rows:
                continue
            value, se = bias(acc, "floor")
            flag = "  <<" if abs(value) > 3 and abs(value) > 2 * se else ""
            print(f"{name:30s} {acc[0]:6d} {100 * acc[1] / acc[0]:6.1f} | {value:+8.1f}   ({se:.1f}){flag}")


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("rows", nargs="+", type=Path, help="bucket-mode rows extracted with PF_BUCKET_ML=off")
    ap.add_argument("--min-rows", type=int, default=100)
    args = ap.parse_args(argv)
    report(*collect(iter_rows(args.rows)), args.min_rows)


if __name__ == "__main__":
    main()
