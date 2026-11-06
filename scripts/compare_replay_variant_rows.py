"""Compare two replay row files: baseline strategy vs variant strategy.

Inputs are per-decision JSONL files emitted by scripts.replay_parallel or
scripts.replay_and_compare with the same replay source. The comparison is
baseline "new decision" versus variant "new decision"; historical actions are
used only to attach the realized hand result.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


def _load_rows(path: Path) -> dict[tuple[Any, ...], dict[str, Any]]:
    rows: dict[tuple[Any, ...], dict[str, Any]] = {}
    with path.open("r", encoding="utf-8") as fh:
        for line_no, raw in enumerate(fh, 1):
            raw = raw.strip()
            if not raw:
                continue
            row = json.loads(raw)
            key = (
                row.get("source_log", ""),
                row.get("session", 0),
                row.get("hand"),
                row.get("event_index"),
            )
            if key in rows:
                key = (*key, line_no)
            rows[key] = row
    return rows


def _load_replay_meta(path: Path) -> dict[tuple[Any, ...], dict[str, Any]]:
    meta: dict[tuple[Any, ...], dict[str, Any]] = {}
    with path.open("r", encoding="utf-8") as fh:
        for raw in fh:
            raw = raw.strip()
            if not raw:
                continue
            hand = json.loads(raw)
            source = hand.get("source_log", "")
            session = hand.get("session", 0)
            hand_no = hand.get("hand")
            result = hand.get("result") or {}
            for idx, ev in enumerate(hand.get("events") or []):
                if ev.get("type") != "decision":
                    continue
                meta[(source, session, hand_no, idx)] = {
                    "bb": _bb_bucket(float(hand.get("big_blind") or 0.0)),
                    "big_blind": float(hand.get("big_blind") or 0.0),
                    "street": ev.get("street", ""),
                    "hist_delta": int(result.get("my_delta") or 0),
                }
    return meta


def _bb_bucket(bb: float) -> str:
    if 7000 <= bb <= 15000:
        return "10k"
    if 35000 <= bb <= 65000:
        return "50k"
    if bb > 0:
        return str(int(round(bb)))
    return "unknown"


def _decision_tag(row: dict[str, Any]) -> tuple[str, float]:
    new = row.get("new") or {}
    return str(new.get("action") or ""), float(new.get("amount") or 0.0)


def _change_tag(base: dict[str, Any], variant: dict[str, Any]) -> str:
    ba, bm = _decision_tag(base)
    va, vm = _decision_tag(variant)
    if ba == va:
        if ba == "raise" and abs(vm - bm) > max(1.0, bm * 0.15):
            return "raise→raise-bigger" if vm > bm else "raise→raise-smaller"
        return "unchanged"
    return f"{ba}→{va}"


def _purpose(row: dict[str, Any]) -> str:
    diag = row.get("diagnostics") or {}
    return str(diag.get("final_purpose") or diag.get("purpose") or diag.get("action") or "unknown")


def _bucket_direction(tag: str, hist_delta: int) -> str:
    active_more = tag in {"check→raise", "fold→raise", "call→raise", "raise→raise-bigger"}
    active_less = tag in {"raise→check", "raise→fold", "raise→call", "raise→raise-smaller"}
    if active_more:
        if hist_delta > 0:
            return "active_more_won"
        if hist_delta < 0:
            return "active_more_lost"
        return "active_more_flat"
    if active_less:
        if hist_delta < 0:
            return "active_less_lost"
        if hist_delta > 0:
            return "active_less_won"
        return "active_less_flat"
    return "other"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--replay", type=Path, required=True)
    ap.add_argument("--baseline", type=Path, required=True)
    ap.add_argument("--variant", type=Path, required=True)
    ap.add_argument("--out", type=Path, help="write changed decision rows as JSONL")
    args = ap.parse_args()

    baseline = _load_rows(args.baseline)
    variant = _load_rows(args.variant)
    meta = _load_replay_meta(args.replay)

    changed_rows: list[dict[str, Any]] = []
    agg = defaultdict(lambda: {"decisions": 0, "hands": set(), "net_bb": 0.0})
    change_counts: Counter[str] = Counter()
    direction_counts: Counter[str] = Counter()

    for key, base_row in baseline.items():
        var_row = variant.get(key)
        if var_row is None:
            continue
        tag = _change_tag(base_row, var_row)
        if tag == "unchanged":
            continue
        m = meta.get(key, {})
        bb = m.get("bb", "unknown")
        big_blind = float(m.get("big_blind") or 0.0)
        hist_delta = int(m.get("hist_delta") or base_row.get("hist_hand_delta") or 0)
        direction = _bucket_direction(tag, hist_delta)
        purpose = _purpose(var_row)
        street = m.get("street") or base_row.get("street") or "?"
        hand_id = (key[0], key[1], key[2])
        net_bb = hist_delta / big_blind if big_blind > 0 else 0.0

        for agg_key in [
            (bb, direction),
            (bb, street, direction),
            (bb, purpose, direction),
        ]:
            row = agg[agg_key]
            row["decisions"] += 1
            if hand_id not in row["hands"]:
                row["hands"].add(hand_id)
                row["net_bb"] += net_bb

        change_counts[tag] += 1
        direction_counts[direction] += 1
        changed_rows.append({
            "key": key,
            "bb": bb,
            "street": street,
            "purpose": purpose,
            "change": tag,
            "direction": direction,
            "hist_delta": hist_delta,
            "hist_delta_bb": round(net_bb, 2),
            "baseline_new": base_row.get("new"),
            "variant_new": var_row.get("new"),
            "baseline_diag": base_row.get("diagnostics"),
            "variant_diag": var_row.get("diagnostics"),
        })

    summary = {
        "baseline_rows": len(baseline),
        "variant_rows": len(variant),
        "changed": len(changed_rows),
        "change_counts": dict(change_counts.most_common()),
        "direction_counts": dict(direction_counts.most_common()),
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False))

    print("\n| 分组 | 决策数 | 手数 | 历史净结果 |")
    print("|---|---:|---:|---:|")
    for key, row in sorted(agg.items(), key=lambda kv: (str(kv[0]), -kv[1]["decisions"])):
        label = " / ".join(str(x) for x in key)
        print(f"| {label} | {row['decisions']} | {len(row['hands'])} | {row['net_bb']:+.2f}bb |")

    if args.out:
        with args.out.open("w", encoding="utf-8") as fh:
            for row in changed_rows:
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
