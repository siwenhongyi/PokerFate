#!/usr/bin/env python3
"""Refill the online hero-equity calibrator after the range stack below it has changed.

The calibrator keeps (predicted, actual) hero-equity pairs measured with the range model that
was running when they were recorded.  Once the formula layer or the bucket model is replaced,
those pairs describe a stack that no longer exists.  This refills it from a full-mode replay
of the logs with the new stack in place (extractor ``--mode full``, parts in session order):

    .venv/bin/python -m scripts.refill_hero_eq --rows parts_full/task_*.jsonl [--apply]

``--apply`` swaps the refilled state into opponents.json and keeps a backup; only while the bot
is stopped.  It is the last step of a refit of the range stack (docs/range_v2_bucket_ml.md).
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from analysis.range_layers import iter_rows  # noqa: E402


def rebuild_hero_eq(rows: Iterable[dict[str, Any]], opponents: Path, apply: bool) -> None:
    """Refill the hero-equity calibrator from replayed rows, in the order they were played."""
    from analysis.robot_relearn import _applied_bias
    from pokerfate.strategy.range_v2.hero_eq_calibrator import (
        _MIN_SAMPLES, HeroEquityCalibrator, classify_action_ctx_from_trigger)

    fresh = HeroEquityCalibrator()
    used = 0
    for row in rows:
        predicted, actual = row.get("predicted_hero_eq_multi"), row.get("actual_hero_eq_street_multi")
        if predicted is None or actual is None or not row.get("hero_bucket") or not row.get("street"):
            continue
        fresh.record(bucket=row["hero_bucket"], street=row["street"],
                     num_opp=int(row.get("active_player_count") or 0),
                     predicted=float(predicted), actual=float(actual),
                     action_ctx=classify_action_ctx_from_trigger(str(row.get("trigger") or "")))
        used += 1
    raw = json.loads(opponents.read_text(encoding="utf-8"))
    old = HeroEquityCalibrator.from_dict((raw.get("showdown") or {}).get("hero_eq_calibrator") or {})._samples
    new = fresh._samples
    count = lambda state: sum(len(v) for v in state.values())
    active = lambda state: {k: _applied_bias(v) for k, v in state.items() if len(v) >= _MIN_SAMPLES}
    before, after = active(old), active(new)
    mean_abs = lambda biases: 100 * sum(abs(b) for b in biases.values()) / max(1, len(biases))
    print(f"回放样本 {used:,} 条。校准器：{len(old)} 个键 / {count(old):,} 个样本 → {len(new)} 个键 / {count(new):,} 个样本")
    print(f"生效的键 {len(before)} → {len(after)} 个；修正量绝对值的平均 {mean_abs(before):.2f} → {mean_abs(after):.2f} 个百分点")
    print(f"   {'hero桶|街|对手数|情境':30s} 旧样本 新样本   旧修正 → 新修正（加到 hero 胜率上的偏移，百分点）")
    for key in sorted(set(before) | set(after), key=lambda k: -abs(after.get(k, 0.0) - before.get(k, 0.0)))[:14]:
        print(f"   {key:32s} {len(old.get(key, [])):5d} {len(new.get(key, [])):5d}   "
              f"{100 * before.get(key, 0.0):+6.1f} → {100 * after.get(key, 0.0):+6.1f}")
    if not apply:
        print("（试运行，未改动文件；加 --apply 才替换）")
        return
    backup = Path(str(opponents) + f".before-range-refit-{int(time.time())}")
    backup.write_bytes(opponents.read_bytes())
    raw.setdefault("showdown", {})["hero_eq_calibrator"] = {k: [[p, a] for p, a in v] for k, v in new.items() if v}
    tmp = Path(str(opponents) + ".tmp")
    tmp.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    tmp.replace(opponents)
    print(f"已替换 {opponents} 里的校准器状态；原文件备份为 {backup.name}")


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rows", type=Path, nargs="+", required=True,
                    help="full-mode rows, in the order they were played")
    ap.add_argument("--opponents", type=Path,
                    default=ROOT / "pokerfate" / "data" / "local_models" / "opponents.json")
    ap.add_argument("--apply", action="store_true", help="replace the state in opponents.json (backup kept)")
    args = ap.parse_args(argv)
    rebuild_hero_eq(iter_rows(args.rows), args.opponents, args.apply)


if __name__ == "__main__":
    main()
