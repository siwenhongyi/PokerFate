from __future__ import annotations

import json
import math
import time
from pathlib import Path
from statistics import median
from typing import Any

from pokerfate.strategy.range_v2.cec_calibration import (
    calibrate_bucket_dist,
    row_context,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RUNTIME_ROOT = ROOT / "data" / "runtime_calibration"
BUCKET_ORDER = ("nuts", "strong", "medium", "draw", "weak_draw", "air")


def range_nll_payload(
    runtime_root: Path | str = DEFAULT_RUNTIME_ROOT,
) -> dict[str, Any]:
    """Analyze runtime exact-combo NLL rows written by Range V2 calibration."""
    root = Path(runtime_root)
    files = sorted(root.glob("bb_*/*.rows.jsonl"))
    overall = _new_acc()
    by_street: dict[str, dict[str, Any]] = {}
    by_bucket: dict[str, dict[str, Any]] = {}
    by_player: dict[str, dict[str, Any]] = {}
    bucket_cal = _new_bucket_calibration()
    cec_integration = _new_cec_integration()
    improved_examples: list[dict[str, Any]] = []
    worse_examples: list[dict[str, Any]] = []

    rows = 0
    skipped = 0
    bad_lines = 0
    hands: set[str] = set()

    for path in files:
        with path.open("r", encoding="utf-8") as fh:
            for line_no, line in enumerate(fh, start=1):
                text = line.strip()
                if not text:
                    continue
                try:
                    row = json.loads(text)
                except json.JSONDecodeError:
                    bad_lines += 1
                    continue
                rows += 1
                _add_bucket_calibration(bucket_cal, row)
                _add_cec_integration(cec_integration, row, runtime_root=root)
                item = _nll_item(row, path=path, line_no=line_no)
                if item is None:
                    skipped += 1
                    continue
                if item["hand_id"]:
                    hands.add(item["hand_id"])
                _add_acc(overall, item)
                _add_acc(
                    by_street.setdefault(item["street"] or "unknown", _new_acc()),
                    item,
                )
                _add_acc(
                    by_bucket.setdefault(item["actual_bucket"] or "unknown", _new_acc()),
                    item,
                )
                _add_acc(
                    by_player.setdefault(item["player"] or item["player_uid"], _new_acc()),
                    item,
                )
                _push_example(improved_examples, item, reverse=True)
                _push_example(worse_examples, item, reverse=False)

    calibration = _finalize_bucket_calibration(bucket_cal)
    overall_cal = calibration.get("overall") if isinstance(calibration, dict) else {}
    summary = _finalize_acc(overall)
    summary.update({
        "files": len(files),
        "rows": rows,
        "hands": len(hands),
        "skipped": skipped,
        "bad_lines": bad_lines,
        "runtime_root": str(root),
        "generated_at": int(time.time()),
    })
    if isinstance(overall_cal, dict):
        summary.update({
            "bucket_ece": overall_cal.get("ece"),
            "bucket_points": overall_cal.get("points"),
            "top_bucket_accuracy": overall_cal.get("top_bucket_accuracy"),
        })
    return {
        "ok": True,
        "summary": summary,
        "conclusion": _conclusion(summary),
        "by_street": _finalized_table(by_street, min_count=1, limit=12),
        "by_category": _finalized_table(by_bucket, min_count=1, limit=18),
        "by_player": _finalized_table(by_player, min_count=2, limit=18),
        "calibration": calibration,
        "cec_integration": _finalize_cec_integration(cec_integration),
        "examples": {
            "improved": sorted(
                improved_examples, key=lambda x: x["delta_nll"], reverse=True,
            )[:10],
            "worse": sorted(worse_examples, key=lambda x: x["delta_nll"])[:10],
        },
        "files": [str(path) for path in files],
    }


def _nll_item(row: dict[str, Any], *, path: Path, line_no: int) -> dict[str, Any] | None:
    trigger = str(row.get("trigger") or "")
    if trigger == "reset":
        return None
    nll_static = _float_or_none(row.get("nll_static"))
    nll_bayes = _float_or_none(row.get("nll_bayes"))
    if nll_static is None or nll_bayes is None:
        static_prob = _float_or_none(row.get("static_combo_prob"))
        bayes_prob = _float_or_none(row.get("bayes_combo_prob"))
        if static_prob is None or bayes_prob is None:
            return None
        nll_static = -math.log(max(static_prob, 1e-12))
        nll_bayes = -math.log(max(bayes_prob, 1e-12))
    delta = _float_or_none(row.get("delta_nll"))
    if delta is None:
        delta = nll_static - nll_bayes
    if not all(math.isfinite(v) for v in (nll_static, nll_bayes, delta)):
        return None

    hand_id = str(row.get("hand") or row.get("hand_id") or "")
    player_uid = str(row.get("player_uid") or row.get("player_id") or "")
    player_name = str(row.get("player_name") or "")
    player = player_name or player_uid
    return {
        "hand_id": hand_id,
        "street": str(row.get("street") or ""),
        "player_uid": player_uid,
        "player": player,
        "trigger": trigger,
        "actual_cards": list(row.get("actual_cards") or []),
        "actual_combo": str(row.get("actual_combo") or ""),
        "actual_bucket": str(row.get("actual_bucket") or ""),
        "static_combo_prob": _float(row.get("static_combo_prob"), 0.0),
        "bayes_combo_prob": _float(row.get("bayes_combo_prob"), 0.0),
        "nll_static": nll_static,
        "nll_bayes": nll_bayes,
        "delta_nll": delta,
        "file": str(path),
        "line": line_no,
    }


def _new_acc() -> dict[str, Any]:
    return {
        "count": 0,
        "improved": 0,
        "worse": 0,
        "tie": 0,
        "static_prob_sum": 0.0,
        "bayes_prob_sum": 0.0,
        "static_nll_sum": 0.0,
        "bayes_nll_sum": 0.0,
        "delta_sum": 0.0,
        "delta_values": [],
    }


def _add_acc(acc: dict[str, Any], item: dict[str, Any]) -> None:
    delta = float(item["delta_nll"])
    acc["count"] += 1
    if delta > 1e-9:
        acc["improved"] += 1
    elif delta < -1e-9:
        acc["worse"] += 1
    else:
        acc["tie"] += 1
    acc["static_prob_sum"] += float(item["static_combo_prob"])
    acc["bayes_prob_sum"] += float(item["bayes_combo_prob"])
    acc["static_nll_sum"] += float(item["nll_static"])
    acc["bayes_nll_sum"] += float(item["nll_bayes"])
    acc["delta_sum"] += delta
    acc["delta_values"].append(delta)


def _finalize_acc(acc: dict[str, Any]) -> dict[str, Any]:
    count = int(acc.get("count", 0) or 0)
    if count <= 0:
        return {
            "count": 0,
            "improved": 0,
            "worse": 0,
            "tie": 0,
            "avg_static_prob": None,
            "avg_bayes_prob": None,
            "avg_static_nll": None,
            "avg_bayes_nll": None,
            "avg_delta_nll": None,
            "median_delta_nll": None,
            "positive_rate": None,
            "winner": "none",
        }
    avg_delta = acc["delta_sum"] / count
    if avg_delta > 0.02:
        winner = "bayes"
    elif avg_delta < -0.02:
        winner = "static"
    else:
        winner = "tie"
    return {
        "count": count,
        "improved": int(acc["improved"]),
        "worse": int(acc["worse"]),
        "tie": int(acc["tie"]),
        "avg_static_prob": acc["static_prob_sum"] / count,
        "avg_bayes_prob": acc["bayes_prob_sum"] / count,
        "avg_static_nll": acc["static_nll_sum"] / count,
        "avg_bayes_nll": acc["bayes_nll_sum"] / count,
        "avg_delta_nll": avg_delta,
        "median_delta_nll": float(median(acc["delta_values"])),
        "positive_rate": acc["improved"] / count,
        "winner": winner,
    }


def _finalized_table(
    groups: dict[str, dict[str, Any]],
    *,
    min_count: int,
    limit: int,
) -> list[dict[str, Any]]:
    rows = []
    for key, acc in groups.items():
        item = _finalize_acc(acc)
        if item["count"] < min_count:
            continue
        item["key"] = key
        rows.append(item)
    rows.sort(
        key=lambda r: (
            r["count"],
            abs(float(r.get("avg_delta_nll") or 0.0)),
        ),
        reverse=True,
    )
    return rows[:limit]


def _push_example(
    examples: list[dict[str, Any]],
    item: dict[str, Any],
    *,
    reverse: bool,
) -> None:
    delta = float(item["delta_nll"])
    if reverse and delta <= 0:
        return
    if not reverse and delta >= 0:
        return
    examples.append({
        "hand_id": item["hand_id"],
        "street": item["street"],
        "player": item["player"],
        "trigger": item["trigger"],
        "actual_cards": list(item["actual_cards"]),
        "actual_combo": item["actual_combo"],
        "actual_bucket": item["actual_bucket"],
        "static_combo_prob": item["static_combo_prob"],
        "bayes_combo_prob": item["bayes_combo_prob"],
        "nll_static": item["nll_static"],
        "nll_bayes": item["nll_bayes"],
        "delta_nll": delta,
    })
    if len(examples) > 200:
        examples.sort(key=lambda x: x["delta_nll"], reverse=reverse)
        del examples[80:]


def _new_bucket_calibration() -> dict[str, Any]:
    return {
        "overall": _new_cal_acc(),
        "groups": {
            "by_bucket": {},
            "by_street": {},
            "by_action": {},
            "by_size": {},
            "by_line": {},
        },
    }


def _add_bucket_calibration(acc: dict[str, Any], row: dict[str, Any]) -> None:
    actual = str(row.get("actual_bucket") or "")
    dist_raw = row.get("bucket_dist")
    if not actual or not isinstance(dist_raw, dict):
        return
    dist: dict[str, float] = {}
    for key, value in dist_raw.items():
        p = _float_or_none(value)
        if p is None:
            continue
        dist[str(key)] = min(max(p, 0.0), 1.0)
    if not dist:
        return

    top_bucket, _top_prob = max(dist.items(), key=lambda kv: kv[1])
    row_group_keys = _calibration_group_keys(row)
    row_accs = [acc["overall"]]
    groups = acc.get("groups") if isinstance(acc.get("groups"), dict) else {}
    for group_name, key in row_group_keys.items():
        bucket = groups.setdefault(group_name, {})
        row_accs.append(bucket.setdefault(key, _new_cal_acc()))

    for item in row_accs:
        _add_cal_top(item, top_bucket == actual)

    for bucket in sorted(set(dist) | {actual}):
        prob = min(max(float(dist.get(bucket, 0.0)), 0.0), 1.0)
        target = 1.0 if bucket == actual else 0.0
        _add_cal_point(acc["overall"], prob, target)
        by_bucket = groups.setdefault("by_bucket", {})
        _add_cal_point(by_bucket.setdefault(bucket, _new_cal_acc()), prob, target)
        for group_name, key in row_group_keys.items():
            _add_cal_point(
                groups.setdefault(group_name, {}).setdefault(key, _new_cal_acc()),
                prob,
                target,
            )


def _finalize_bucket_calibration(acc: dict[str, Any]) -> dict[str, Any]:
    overall = _finalize_cal_acc(acc.get("overall") or {})
    groups = acc.get("groups") if isinstance(acc.get("groups"), dict) else {}
    by_bucket = _finalize_cal_group(groups.get("by_bucket") or {}, min_points=1, limit=18)
    by_street = _finalize_cal_group(groups.get("by_street") or {}, min_points=1, limit=12)
    by_action = _finalize_cal_group(groups.get("by_action") or {}, min_points=1, limit=12)
    by_size = _finalize_cal_group(groups.get("by_size") or {}, min_points=1, limit=12)
    by_line = _finalize_cal_group(groups.get("by_line") or {}, min_points=1, limit=24)
    hotspots = sorted(
        [
            {**item, "source": source}
            for source, rows in (
                ("street", by_street),
                ("action", by_action),
                ("size", by_size),
                ("line", by_line),
                ("bucket", by_bucket),
            )
            for item in rows
        ],
        key=lambda item: (
            int(item.get("points") or 0) >= 30,
            abs(float(item.get("bias") or 0.0)),
            float(item.get("ece") or 0.0),
            int(item.get("points") or 0),
        ),
        reverse=True,
    )[:24]
    return {
        "overall": overall,
        "by_bucket": by_bucket,
        "by_street": by_street,
        "by_action": by_action,
        "by_size": by_size,
        "by_line": by_line,
        "hotspots": hotspots,
    }


def _new_cal_acc() -> dict[str, Any]:
    return {
        "points": 0,
        "rows": 0,
        "top_total": 0,
        "top_hits": 0,
        "prob_sum": 0.0,
        "actual_sum": 0.0,
        "brier_sum": 0.0,
        "bins": [
            {"count": 0, "prob_sum": 0.0, "actual_sum": 0.0}
            for _ in range(10)
        ],
    }


def _add_cal_top(acc: dict[str, Any], hit: bool) -> None:
    acc["rows"] += 1
    acc["top_total"] += 1
    if hit:
        acc["top_hits"] += 1


def _add_cal_point(acc: dict[str, Any], prob: float, actual: float) -> None:
    prob = min(max(float(prob), 0.0), 1.0)
    actual = min(max(float(actual), 0.0), 1.0)
    bin_idx = min(9, max(0, int(prob * 10)))
    b = acc["bins"][bin_idx]
    b["count"] += 1
    b["prob_sum"] += prob
    b["actual_sum"] += actual
    acc["points"] += 1
    acc["prob_sum"] += prob
    acc["actual_sum"] += actual
    acc["brier_sum"] += (prob - actual) * (prob - actual)


def _finalize_cal_acc(acc: dict[str, Any]) -> dict[str, Any]:
    points = int(acc.get("points", 0) or 0)
    rows = int(acc.get("rows", 0) or 0)
    top_total = int(acc.get("top_total", 0) or 0)
    if points <= 0:
        return {
            "points": 0,
            "rows": rows,
            "ece": None,
            "avg_pred": None,
            "empirical": None,
            "bias": None,
            "brier": None,
            "bias_label": "none",
            "top_bucket_accuracy": (
                float(acc.get("top_hits", 0) / top_total) if top_total > 0 else None
            ),
            "bins": [],
        }
    ece_total = 0.0
    bins = []
    for idx, b in enumerate(acc.get("bins") or []):
        count = int(b.get("count", 0) or 0)
        if count <= 0:
            continue
        avg_prob = float(b.get("prob_sum", 0.0)) / count
        empirical = float(b.get("actual_sum", 0.0)) / count
        gap = avg_prob - empirical
        ece_total += (count / points) * abs(gap)
        bins.append({
            "bin": f"{idx * 10}-{(idx + 1) * 10}%",
            "count": count,
            "avg_pred": avg_prob,
            "empirical": empirical,
            "gap": gap,
            "bias_label": _bias_label(gap),
        })
    avg_pred = float(acc.get("prob_sum", 0.0)) / points
    empirical = float(acc.get("actual_sum", 0.0)) / points
    bias = avg_pred - empirical
    return {
        "points": points,
        "rows": rows,
        "ece": ece_total,
        "avg_pred": avg_pred,
        "empirical": empirical,
        "bias": bias,
        "brier": float(acc.get("brier_sum", 0.0)) / points,
        "bias_label": _bias_label(bias),
        "top_bucket_accuracy": (
            float(acc.get("top_hits", 0) / top_total) if top_total > 0 else None
        ),
        "bins": bins,
    }


def _finalize_cal_group(
    groups: dict[str, dict[str, Any]],
    *,
    min_points: int,
    limit: int,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for key, raw in groups.items():
        item = _finalize_cal_acc(raw)
        if int(item.get("points") or 0) < min_points:
            continue
        item["key"] = str(key)
        rows.append(item)
    rows.sort(
        key=lambda item: (
            int(item.get("points") or 0),
            float(item.get("ece") or 0.0),
            abs(float(item.get("bias") or 0.0)),
        ),
        reverse=True,
    )
    return rows[:limit]


def _calibration_group_keys(row: dict[str, Any]) -> dict[str, str]:
    street = str(row.get("street") or "unknown")
    action = _action_ctx(str(row.get("trigger") or ""))
    size = str(row.get("bet_size_bucket") or "") or _size_bucket(row.get("action_bet_ratio"))
    if action in {"check", "call", "fold_other", "board", "passive"} and size == "none":
        size = action
    raise_flag = "raise_over" if bool(row.get("is_raise_over")) else "single"
    return {
        "by_street": street,
        "by_action": action,
        "by_size": size,
        "by_line": f"{street}|{action}|{size}|{raise_flag}",
    }


def _action_ctx(trigger: str) -> str:
    if trigger in {"action:raise", "action:raise_over"}:
        return "raise"
    if trigger == "action:bet":
        return "bet"
    if trigger == "action:call":
        return "call"
    if trigger == "action:check":
        return "check"
    if trigger == "action:fold":
        return "fold"
    if trigger == "action:fold_other":
        return "fold_other"
    if trigger.startswith("board:"):
        return "board"
    return "passive"


def _size_bucket(value: Any) -> str:
    ratio = _float(value, 0.0)
    if ratio <= 0.0:
        return "none"
    if ratio <= 0.25:
        return "small"
    if ratio <= 0.40:
        return "third"
    if ratio <= 0.55:
        return "half"
    if ratio <= 0.80:
        return "two_third"
    if ratio <= 1.10:
        return "pot"
    if ratio <= 1.75:
        return "overpot"
    return "huge"


def _bias_label(value: float | None) -> str:
    if value is None:
        return "none"
    if value > 0.03:
        return "overconfident"
    if value < -0.03:
        return "underconfident"
    return "ok"


def _new_cec_integration() -> dict[str, Any]:
    return {
        "overall": _new_cec_acc(),
        "groups": {
            "by_street": {},
            "by_action": {},
            "by_size": {},
            "by_line": {},
        },
        "improved_examples": [],
        "worse_examples": [],
    }


def _new_cec_acc() -> dict[str, Any]:
    return {
        "count": 0,
        "improved": 0,
        "worse": 0,
        "tie": 0,
        "raw_prob_sum": 0.0,
        "cec_prob_sum": 0.0,
        "raw_nll_sum": 0.0,
        "cec_nll_sum": 0.0,
        "raw_brier_sum": 0.0,
        "cec_brier_sum": 0.0,
        "raw_top_hits": 0,
        "cec_top_hits": 0,
        "reliability_sum": 0.0,
        "raw_cal": _new_cal_acc(),
        "cec_cal": _new_cal_acc(),
    }


def _add_cec_integration(
    acc: dict[str, Any],
    row: dict[str, Any],
    *,
    runtime_root: Path,
) -> None:
    trigger = str(row.get("trigger") or "")
    if trigger == "reset":
        return
    actual = str(row.get("actual_bucket") or "")
    raw = _normalize_dist(row.get("bucket_dist"))
    if actual not in BUCKET_ORDER or not raw:
        return
    cec, diag = calibrate_bucket_dist(
        raw,
        context=row_context(row),
        big_blind=row.get("bb"),
        runtime_root=runtime_root,
    )
    if not cec:
        return

    targets = [acc["overall"]]
    keys = _calibration_group_keys(row)
    groups = acc.get("groups") if isinstance(acc.get("groups"), dict) else {}
    for group_name, key in keys.items():
        if group_name not in groups:
            continue
        targets.append(groups[group_name].setdefault(key, _new_cec_acc()))
    for target in targets:
        _add_cec_acc_row(target, raw, cec, actual, diag)

    item = {
        "hand_id": str(row.get("hand") or row.get("hand_id") or ""),
        "street": str(row.get("street") or ""),
        "trigger": trigger,
        "player": str(row.get("player_name") or row.get("player_uid") or ""),
        "actual_bucket": actual,
        "raw_prob": float(raw.get(actual, 0.0)),
        "cec_prob": float(cec.get(actual, 0.0)),
        "delta_prob": float(cec.get(actual, 0.0)) - float(raw.get(actual, 0.0)),
        "cec": {
            "level": diag.get("level"),
            "key": diag.get("key"),
            "rows": diag.get("rows"),
            "ece": diag.get("ece"),
            "raw_reliability": diag.get("raw_reliability"),
        },
    }
    if item["delta_prob"] > 0:
        _push_cec_example(acc["improved_examples"], item, reverse=True)
    elif item["delta_prob"] < 0:
        _push_cec_example(acc["worse_examples"], item, reverse=False)


def _add_cec_acc_row(
    acc: dict[str, Any],
    raw: dict[str, float],
    cec: dict[str, float],
    actual: str,
    diag: dict[str, Any],
) -> None:
    raw_prob = max(float(raw.get(actual, 0.0)), 1e-12)
    cec_prob = max(float(cec.get(actual, 0.0)), 1e-12)
    acc["count"] += 1
    if cec_prob > raw_prob + 1e-12:
        acc["improved"] += 1
    elif cec_prob < raw_prob - 1e-12:
        acc["worse"] += 1
    else:
        acc["tie"] += 1
    acc["raw_prob_sum"] += raw_prob
    acc["cec_prob_sum"] += cec_prob
    acc["raw_nll_sum"] += -math.log(raw_prob)
    acc["cec_nll_sum"] += -math.log(cec_prob)
    acc["raw_brier_sum"] += _brier(raw, actual)
    acc["cec_brier_sum"] += _brier(cec, actual)
    if max(raw.items(), key=lambda item: item[1])[0] == actual:
        acc["raw_top_hits"] += 1
    if max(cec.items(), key=lambda item: item[1])[0] == actual:
        acc["cec_top_hits"] += 1
    acc["reliability_sum"] += _float(diag.get("raw_reliability"), DEFAULT_CEC_RELIABILITY)
    _add_cal_top(acc["raw_cal"], max(raw.items(), key=lambda item: item[1])[0] == actual)
    _add_cal_top(acc["cec_cal"], max(cec.items(), key=lambda item: item[1])[0] == actual)
    for bucket in BUCKET_ORDER:
        target = 1.0 if bucket == actual else 0.0
        _add_cal_point(acc["raw_cal"], float(raw.get(bucket, 0.0)), target)
        _add_cal_point(acc["cec_cal"], float(cec.get(bucket, 0.0)), target)


DEFAULT_CEC_RELIABILITY = 0.85


def _finalize_cec_integration(acc: dict[str, Any]) -> dict[str, Any]:
    groups = acc.get("groups") if isinstance(acc.get("groups"), dict) else {}
    by_street = _finalize_cec_group(groups.get("by_street") or {}, limit=12)
    by_action = _finalize_cec_group(groups.get("by_action") or {}, limit=12)
    by_size = _finalize_cec_group(groups.get("by_size") or {}, limit=12)
    by_line = _finalize_cec_group(groups.get("by_line") or {}, limit=24)
    return {
        "overall": _finalize_cec_acc(acc.get("overall") or {}),
        "by_street": by_street,
        "by_action": by_action,
        "by_size": by_size,
        "by_line": by_line,
        "hotspots": sorted(
            [
                {**item, "source": source}
                for source, rows in (
                    ("street", by_street),
                    ("action", by_action),
                    ("size", by_size),
                    ("line", by_line),
                )
                for item in rows
            ],
            key=lambda item: (
                int(item.get("count") or 0) >= 30,
                abs(float(item.get("nll_gain") or 0.0)),
                abs(float(item.get("ece_gain") or 0.0)),
                int(item.get("count") or 0),
            ),
            reverse=True,
        )[:24],
        "examples": {
            "improved": sorted(
                acc.get("improved_examples") or [],
                key=lambda item: item["delta_prob"],
                reverse=True,
            )[:10],
            "worse": sorted(
                acc.get("worse_examples") or [],
                key=lambda item: item["delta_prob"],
            )[:10],
        },
    }


def _finalize_cec_group(groups: dict[str, dict[str, Any]], *, limit: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for key, raw in groups.items():
        item = _finalize_cec_acc(raw)
        if int(item.get("count") or 0) <= 0:
            continue
        item["key"] = str(key)
        rows.append(item)
    rows.sort(
        key=lambda item: (
            int(item.get("count") or 0),
            abs(float(item.get("nll_gain") or 0.0)),
            abs(float(item.get("ece_gain") or 0.0)),
        ),
        reverse=True,
    )
    return rows[:limit]


def _finalize_cec_acc(acc: dict[str, Any]) -> dict[str, Any]:
    count = int(acc.get("count", 0) or 0)
    if count <= 0:
        return {
            "count": 0,
            "improved": 0,
            "worse": 0,
            "tie": 0,
            "avg_raw_prob": None,
            "avg_cec_prob": None,
            "avg_prob_delta": None,
            "raw_nll": None,
            "cec_nll": None,
            "nll_gain": None,
            "raw_ece": None,
            "cec_ece": None,
            "ece_gain": None,
            "raw_top1": None,
            "cec_top1": None,
            "avg_reliability": None,
            "winner": "none",
        }
    raw_cal = _finalize_cal_acc(acc.get("raw_cal") or {})
    cec_cal = _finalize_cal_acc(acc.get("cec_cal") or {})
    raw_nll = float(acc["raw_nll_sum"]) / count
    cec_nll = float(acc["cec_nll_sum"]) / count
    nll_gain = raw_nll - cec_nll
    raw_ece = raw_cal.get("ece")
    cec_ece = cec_cal.get("ece")
    ece_gain = (
        float(raw_ece) - float(cec_ece)
        if raw_ece is not None and cec_ece is not None
        else None
    )
    if nll_gain > 0.005:
        winner = "cec"
    elif nll_gain < -0.005:
        winner = "raw"
    else:
        winner = "tie"
    return {
        "count": count,
        "improved": int(acc["improved"]),
        "worse": int(acc["worse"]),
        "tie": int(acc["tie"]),
        "avg_raw_prob": float(acc["raw_prob_sum"]) / count,
        "avg_cec_prob": float(acc["cec_prob_sum"]) / count,
        "avg_prob_delta": (float(acc["cec_prob_sum"]) - float(acc["raw_prob_sum"])) / count,
        "raw_nll": raw_nll,
        "cec_nll": cec_nll,
        "nll_gain": nll_gain,
        "raw_brier": float(acc["raw_brier_sum"]) / count,
        "cec_brier": float(acc["cec_brier_sum"]) / count,
        "raw_ece": raw_ece,
        "cec_ece": cec_ece,
        "ece_gain": ece_gain,
        "raw_top1": float(acc["raw_top_hits"]) / count,
        "cec_top1": float(acc["cec_top_hits"]) / count,
        "avg_reliability": float(acc["reliability_sum"]) / count,
        "positive_rate": float(acc["improved"]) / count,
        "winner": winner,
    }


def _push_cec_example(
    examples: list[dict[str, Any]],
    item: dict[str, Any],
    *,
    reverse: bool,
) -> None:
    examples.append(item)
    if len(examples) > 200:
        examples.sort(key=lambda x: x["delta_prob"], reverse=reverse)
        del examples[80:]


def _brier(probs: dict[str, float], actual: str) -> float:
    return sum(
        (float(probs.get(bucket, 0.0)) - (1.0 if bucket == actual else 0.0)) ** 2
        for bucket in BUCKET_ORDER
    )


def _normalize_dist(raw: Any) -> dict[str, float]:
    if not isinstance(raw, dict):
        return {}
    out = {bucket: max(0.0, _float(raw.get(bucket), 0.0)) for bucket in BUCKET_ORDER}
    total = sum(out.values())
    if total <= 1e-12:
        return {}
    return {bucket: value / total for bucket, value in out.items()}


def _conclusion(summary: dict[str, Any]) -> list[str]:
    count = int(summary.get("count") or 0)
    if count <= 0:
        lines = [
            "没有可用的 exact-combo NLL 行。需要用新代码实战到摊牌后，再点按钮分析。",
            "旧日志没有保存 1326 权重快照的真实 combo 概率，不能可靠回算 exact NLL。",
        ]
        ece = summary.get("bucket_ece")
        if ece is not None:
            lines.append(
                f"但当前已有 bucket ground truth，可用 CEC/ECE 分析；Bucket ECE {float(ece):.4f}。"
            )
        return lines
    delta = float(summary.get("avg_delta_nll") or 0.0)
    pos = summary.get("positive_rate")
    ece = summary.get("bucket_ece")
    lines = [
        f"ΔNLL = static - bayes；当前均值 {delta:.4f}，正数表示逐街贝叶斯让真实 combo 更可能。",
        f"改善率 {pos * 100:.1f}%；样本 {count} 个决策快照，覆盖 {int(summary.get('hands') or 0)} 手牌。",
    ]
    if ece is not None:
        lines.append(
            f"Bucket ECE {ece:.4f}，用于看桶分布是否系统性过度自信或过度保守。"
        )
    if summary.get("winner") == "static":
        lines.append("当前样本里静态范围更准，需要优先检查 Range V2 是否过度强收缩。")
    elif summary.get("winner") == "bayes":
        lines.append("当前样本里逐街更新有效，后续按街道/桶/玩家看哪里贡献最大。")
    else:
        lines.append("当前样本里两者接近，样本量或具体街道分布还不足以下结论。")
    return lines


def _float_or_none(value: Any) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(out):
        return None
    return out


def _float(value: Any, default: float) -> float:
    out = _float_or_none(value)
    return default if out is None else out
