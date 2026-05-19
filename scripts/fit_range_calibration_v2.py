"""Fit and evaluate Range V2 bucket/equity calibration from extracted rows.

This is the fast stage.  It does not replay poker hands.  It only reads JSONL
rows produced by ``extract_range_calibration_rows_parallel.py`` and searches
small calibration formulas:

Bucket model:
    q = softmax(gamma * log(p) + theta_bucket)

Hero equity model:
    raw equity -> calibrated equity via either a context bias or linear map.

The script reports raw/current/fitted metrics separately.  "current" for bucket
means the runtime _BUCKET_CALIBRATION table already present in
bayesian_range_tracker.py, applied offline to raw rows.
"""

from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable, Optional

import numpy as np


CAT_ORDER = ("nuts", "strong", "medium", "draw", "weak_draw", "air")
CAT_IDX = {cat: idx for idx, cat in enumerate(CAT_ORDER)}
EPS = 1e-6


def _load_rows(paths: Iterable[Path]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in paths:
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    rows.append(json.loads(line))
    return rows


def _write_json(path: Path | None, obj: Any) -> None:
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True),
                    encoding="utf-8")


def _bucket_vec(row: dict[str, Any]) -> np.ndarray:
    dist = row.get("bucket_dist") or {}
    arr = np.array([float(dist.get(cat, 0.0)) for cat in CAT_ORDER], dtype=np.float64)
    total = float(arr.sum())
    if total > 0:
        arr /= total
    else:
        arr[:] = 1.0 / len(CAT_ORDER)
    return np.clip(arr, EPS, 1.0)


def _label_idx(row: dict[str, Any]) -> int:
    return CAT_IDX.get(row.get("actual_bucket"), CAT_IDX["air"])


def _softmax(logits: np.ndarray) -> np.ndarray:
    z = logits - logits.max(axis=1, keepdims=True)
    exp = np.exp(z)
    return exp / exp.sum(axis=1, keepdims=True)


def _action_ctx(trigger: str) -> str:
    if trigger in ("action:raise", "action:raise_over"):
        return "raise"
    if trigger == "action:bet":
        return "bet"
    return "passive"


def _nopp_bin(row: dict[str, Any]) -> str:
    n = int(row.get("active_player_count") or len(row.get("active_player_ids") or []) or 1)
    if n <= 1:
        return "1"
    if n == 2:
        return "2"
    return "3+"


def _board_texture(row: dict[str, Any]) -> str:
    board = row.get("board") or []
    if len(board) < 3:
        return "pre"
    ranks = [c[0] for c in board if c]
    suits = [c[1] for c in board if len(c) >= 2]
    paired = len(set(ranks)) < len(ranks)
    monotone = len(suits) >= 3 and len(set(suits[:3])) == 1
    two_flush = len(suits) >= 3 and max(suits[:3].count(s) for s in set(suits[:3])) >= 2
    if monotone:
        flush = "mono"
    elif two_flush:
        flush = "fd"
    else:
        flush = "rainbow"
    return ("paired" if paired else "unpaired") + ":" + flush


def _bucket_context(row: dict[str, Any], level: str) -> str:
    base = f"{row.get('street')} {row.get('trigger')}"
    if level == "simple":
        return base
    if level == "street_trigger_nopp":
        return f"{base} nopp={_nopp_bin(row)}"
    if level == "rich":
        return f"{base} nopp={_nopp_bin(row)} tex={_board_texture(row)}"
    raise ValueError(f"unknown bucket context level: {level}")


def _eq_context(row: dict[str, Any], level: str) -> str:
    if level.startswith("relative:"):
        rel_level = level.split(":", 1)[1]
        subtype = str(row.get("hero_made_subtype") or "?")
        rank = str(row.get("hero_hand_rank") or "?")
        texture = str(row.get("board_texture") or "") or _board_texture(row)
        base = f"river_rel|{row.get('hero_bucket') or '?'}|{subtype}"
        if rel_level == "simple":
            return base
        if rel_level == "action":
            return f"{base}|{_action_ctx(str(row.get('trigger') or ''))}"
        if rel_level == "rich":
            return (
                f"{base}|{_action_ctx(str(row.get('trigger') or ''))}"
                f"|{texture}|rank={rank}|nopp={_nopp_bin(row)}"
            )
        raise ValueError(f"unknown relative context level: {level}")

    base = f"{row.get('street')}|{row.get('hero_bucket') or '?'}"
    if level == "simple":
        return base
    if level == "action":
        return f"{base}|{_nopp_bin(row)}|{_action_ctx(str(row.get('trigger') or ''))}"
    if level == "rich":
        return (
            f"{base}|{_nopp_bin(row)}|{_action_ctx(str(row.get('trigger') or ''))}"
            f"|{_board_texture(row)}"
        )
    raise ValueError(f"unknown equity context level: {level}")


def _relation_eq_from_dist(dist: dict[str, Any] | None) -> float | None:
    rel = dist or {}
    try:
        win = max(0.0, float(rel.get("win", 0.0) or 0.0))
        tie = max(0.0, float(rel.get("tie", 0.0) or 0.0))
        loss = max(0.0, float(rel.get("loss", 0.0) or 0.0))
    except Exception:
        return None
    total = win + tie + loss
    if total <= 1e-12:
        return None
    return (win + 0.5 * tie) / total


def _actual_relation_eq(row: dict[str, Any]) -> float | None:
    relation = str(row.get("actual_relation") or "")
    if relation == "win":
        return 1.0
    if relation == "tie":
        return 0.5
    if relation == "loss":
        return 0.0
    return None


def _bucket_probs(row: dict[str, Any], params: Optional[dict[str, Any]]) -> np.ndarray:
    p = _bucket_vec(row)
    if not params:
        return p / float(p.sum())
    gamma = float(params.get("gamma", 1.0))
    theta_dict = params.get("theta", {}) or {}
    theta = np.array([float(theta_dict.get(cat, 0.0)) for cat in CAT_ORDER],
                     dtype=np.float64)
    q = _softmax(gamma * np.log(p[None, :]) + theta[None, :])[0]
    return q


def _bucket_metrics(
    rows: list[dict[str, Any]],
    params_by_context: Optional[dict[str, Any]] = None,
    *,
    context_level: str = "simple",
) -> dict[str, Any]:
    rows = [r for r in rows if r.get("street") in ("flop", "turn", "river")]
    if not rows:
        return {
            "n": 0, "nll": 0.0, "actual_bucket_avg_pct": 0.0,
            "under_10_pct": 0.0, "top1_pct": 0.0,
            "strong_nuts_under_20_pct": 0.0,
        }
    y = np.array([_label_idx(r) for r in rows], dtype=np.int64)
    probs = []
    for row in rows:
        params = None
        if params_by_context is not None:
            params = params_by_context.get(_bucket_context(row, context_level))
        probs.append(_bucket_probs(row, params))
    q = np.vstack(probs)
    py = q[np.arange(len(rows)), y]
    strong_nuts_mask = np.array([
        row.get("actual_bucket") in ("strong", "nuts") for row in rows
    ], dtype=bool)
    if bool(strong_nuts_mask.any()):
        strong_nuts_under = float(np.mean(py[strong_nuts_mask] < 0.20) * 100.0)
    else:
        strong_nuts_under = 0.0
    return {
        "n": len(rows),
        "nll": round(float(-np.mean(np.log(np.clip(py, EPS, 1.0)))), 5),
        "actual_bucket_avg_pct": round(float(np.mean(py) * 100.0), 2),
        "under_10_pct": round(float(np.mean(py < 0.10) * 100.0), 2),
        "top1_pct": round(float(np.mean(np.argmax(q, axis=1) == y) * 100.0), 2),
        "strong_nuts_under_20_pct": round(strong_nuts_under, 2),
    }


def _fit_bucket_context(
    rows: list[dict[str, Any]],
    *,
    steps: int,
    lr: float,
    l2_theta: float,
    l2_gamma: float,
    gamma_min: float,
    gamma_max: float,
    theta_clip: float,
) -> tuple[float, np.ndarray]:
    p = np.vstack([_bucket_vec(r) for r in rows])
    logp = np.log(p)
    y = np.array([_label_idx(r) for r in rows], dtype=np.int64)
    onehot = np.zeros((len(rows), len(CAT_ORDER)), dtype=np.float64)
    onehot[np.arange(len(rows)), y] = 1.0

    gamma = 1.0
    theta = np.zeros(len(CAT_ORDER), dtype=np.float64)
    m_g = v_g = 0.0
    m_t = np.zeros_like(theta)
    v_t = np.zeros_like(theta)
    beta1 = 0.9
    beta2 = 0.999

    for step in range(1, steps + 1):
        q = _softmax(gamma * logp + theta[None, :])
        diff = q - onehot
        grad_theta = diff.mean(axis=0) + 2.0 * l2_theta * theta
        grad_gamma = float((diff * logp).sum(axis=1).mean()
                           + 2.0 * l2_gamma * (gamma - 1.0))

        m_t = beta1 * m_t + (1.0 - beta1) * grad_theta
        v_t = beta2 * v_t + (1.0 - beta2) * (grad_theta * grad_theta)
        theta -= lr * (m_t / (1.0 - beta1 ** step)) / (
            np.sqrt(v_t / (1.0 - beta2 ** step)) + 1e-8
        )

        m_g = beta1 * m_g + (1.0 - beta1) * grad_gamma
        v_g = beta2 * v_g + (1.0 - beta2) * (grad_gamma * grad_gamma)
        gamma -= lr * (m_g / (1.0 - beta1 ** step)) / (
            math.sqrt(v_g / (1.0 - beta2 ** step)) + 1e-8
        )

        gamma = float(np.clip(gamma, gamma_min, gamma_max))
        theta = np.clip(theta, -theta_clip, theta_clip)
        theta -= float(theta.mean())

    return gamma, theta


def fit_bucket(
    train_rows: list[dict[str, Any]],
    val_rows: list[dict[str, Any]],
    *,
    context_level: str,
    min_train: int,
    min_val: int,
    steps: int,
    lr: float,
    l2_theta: float,
    l2_gamma: float,
    min_nll_gain: float,
) -> dict[str, Any]:
    train_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    val_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in train_rows:
        if row.get("street") in ("flop", "turn", "river"):
            train_groups[_bucket_context(row, context_level)].append(row)
    for row in val_rows:
        if row.get("street") in ("flop", "turn", "river"):
            val_groups[_bucket_context(row, context_level)].append(row)

    accepted: dict[str, Any] = {}
    contexts: list[dict[str, Any]] = []
    for key, rows in sorted(train_groups.items()):
        val = val_groups.get(key, [])
        if len(rows) < min_train or len(val) < min_val:
            continue
        gamma, theta = _fit_bucket_context(
            rows,
            steps=steps,
            lr=lr,
            l2_theta=l2_theta,
            l2_gamma=l2_gamma,
            gamma_min=0.55,
            gamma_max=1.80,
            theta_clip=0.95,
        )
        params = {
            "gamma": round(float(gamma), 4),
            "theta": {
                cat: round(float(v), 4)
                for cat, v in zip(CAT_ORDER, theta)
                if abs(float(v)) >= 0.005
            },
        }
        base_val = _bucket_metrics(val, None, context_level=context_level)
        fit_val = _bucket_metrics(val, {key: params}, context_level=context_level)
        val_gain = float(base_val["nll"] - fit_val["nll"])
        item = {
            "context": key,
            **params,
            "train_base": _bucket_metrics(rows, None, context_level=context_level),
            "train_fit": _bucket_metrics(rows, {key: params}, context_level=context_level),
            "val_base": base_val,
            "val_fit": fit_val,
            "val_nll_gain": round(val_gain, 5),
        }
        contexts.append(item)
        if val_gain >= min_nll_gain:
            accepted[key] = params

    contexts.sort(key=lambda x: (x["val_nll_gain"], x["val_base"]["n"]), reverse=True)
    return {
        "accepted": accepted,
        "contexts": contexts,
        "overall_val_raw": _bucket_metrics(val_rows, None, context_level=context_level),
        "overall_val_fit": _bucket_metrics(val_rows, accepted, context_level=context_level),
    }


def _current_bucket_params() -> dict[str, Any]:
    try:
        from pokerfate.strategy.range_v2.bayesian_range_tracker import _BUCKET_CALIBRATION
    except Exception:
        return {}
    return {
        key: {"gamma": gamma, "theta": dict(theta)}
        for key, (gamma, theta) in _BUCKET_CALIBRATION.items()
    }


def _eq_pairs(
    rows: list[dict[str, Any]],
    *,
    target: str,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if target == "relative":
        for row in rows:
            if row.get("street") != "river":
                continue
            pred = row.get("predicted_relation_eq")
            if pred is None:
                pred = _relation_eq_from_dist(row.get("villain_vs_hero_dist") or {})
            actual = _actual_relation_eq(row)
            if pred is None or actual is None:
                continue
            pred = float(pred)
            actual = float(actual)
            if 0.0 <= pred <= 1.0 and 0.0 <= actual <= 1.0:
                out.append(row)
        return out

    pred_key = "predicted_hero_eq_multi" if target == "multi" else "predicted_hero_eq"
    actual_key = (
        "actual_hero_eq_street_multi" if target == "multi"
        else "actual_hero_eq_street"
    )
    for row in rows:
        pred = row.get(pred_key)
        actual = row.get(actual_key)
        if pred is None or actual is None:
            continue
        pred = float(pred)
        actual = float(actual)
        if 0.0 <= pred <= 1.0 and 0.0 <= actual <= 1.0:
            out.append(row)
    return out


def _eq_raw(row: dict[str, Any], target: str) -> tuple[float, float]:
    if target == "relative":
        pred = row.get("predicted_relation_eq")
        if pred is None:
            pred = _relation_eq_from_dist(row.get("villain_vs_hero_dist") or {})
        actual = _actual_relation_eq(row)
        if pred is None or actual is None:
            raise ValueError("row does not contain river relative target")
        return float(pred), float(actual)
    if target == "multi":
        return float(row["predicted_hero_eq_multi"]), float(row["actual_hero_eq_street_multi"])
    return float(row["predicted_hero_eq"]), float(row["actual_hero_eq_street"])


def _apply_eq_model(x: np.ndarray, model: Optional[dict[str, Any]]) -> np.ndarray:
    if not model:
        return np.clip(x, 0.0, 1.0)
    kind = model.get("type")
    if kind == "bias":
        y = x + float(model.get("bias", 0.0))
    elif kind == "linear":
        y = float(model.get("a", 1.0)) * x + float(model.get("b", 0.0))
    else:
        y = x
    return np.clip(y, 0.0, 1.0)


def _eq_metrics(
    rows: list[dict[str, Any]],
    models: Optional[dict[str, Any]] = None,
    *,
    target: str,
    context_level: str,
) -> dict[str, Any]:
    rows = _eq_pairs(rows, target=target)
    if not rows:
        return {"n": 0, "mae_pp": 0.0, "rmse_pp": 0.0, "bias_pp": 0.0, "ece_pp": 0.0}
    x = []
    y = []
    for row in rows:
        pred, actual = _eq_raw(row, target)
        model = models.get(_eq_context(row, context_level)) if models else None
        x.append(float(_apply_eq_model(np.array([pred]), model)[0]))
        y.append(actual)
    pred_arr = np.array(x, dtype=np.float64)
    actual_arr = np.array(y, dtype=np.float64)
    err = pred_arr - actual_arr
    return {
        "n": len(rows),
        "mae_pp": round(float(np.mean(np.abs(err)) * 100.0), 2),
        "rmse_pp": round(float(math.sqrt(np.mean(err * err)) * 100.0), 2),
        "bias_pp": round(float(np.mean(err) * 100.0), 2),
        "ece_pp": round(_ece(pred_arr, actual_arr) * 100.0, 2),
    }


def _ece(pred: np.ndarray, actual: np.ndarray, bins: int = 10) -> float:
    total = len(pred)
    if total == 0:
        return 0.0
    score = 0.0
    for i in range(bins):
        lo = i / bins
        hi = (i + 1) / bins
        if i == bins - 1:
            mask = (pred >= lo) & (pred <= hi)
        else:
            mask = (pred >= lo) & (pred < hi)
        if not bool(mask.any()):
            continue
        score += float(mask.mean()) * abs(float(pred[mask].mean() - actual[mask].mean()))
    return score


def _fit_eq_group(rows: list[dict[str, Any]], *, target: str, shrink_k: float) -> list[dict[str, Any]]:
    x_vals = []
    y_vals = []
    for row in rows:
        x, y = _eq_raw(row, target)
        x_vals.append(x)
        y_vals.append(y)
    x = np.array(x_vals, dtype=np.float64)
    y = np.array(y_vals, dtype=np.float64)
    n = len(rows)
    shrink = n / (n + shrink_k) if shrink_k > 0 else 1.0

    raw_bias = float(np.mean(y - x))
    bias = float(np.clip(raw_bias, -0.30, 0.30) * shrink)
    models = [{"type": "bias", "bias": round(bias, 5), "raw_bias": round(raw_bias, 5)}]

    if n >= 3 and float(np.var(x)) > 1e-6:
        a, b = np.polyfit(x, y, deg=1)
        a = float(np.clip(a, 0.35, 1.80))
        b = float(np.clip(b, -0.45, 0.45))
        a = 1.0 + shrink * (a - 1.0)
        b = shrink * b
        models.append({
            "type": "linear",
            "a": round(a, 5),
            "b": round(b, 5),
        })
    return models


def fit_equity(
    train_rows: list[dict[str, Any]],
    val_rows: list[dict[str, Any]],
    *,
    target: str,
    context_level: str,
    min_train: int,
    min_val: int,
    min_mae_gain_pp: float,
    shrink_k: float,
) -> dict[str, Any]:
    train_pairs = _eq_pairs(train_rows, target=target)
    val_pairs = _eq_pairs(val_rows, target=target)
    train_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    val_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in train_pairs:
        train_groups[_eq_context(row, context_level)].append(row)
    for row in val_pairs:
        val_groups[_eq_context(row, context_level)].append(row)

    accepted: dict[str, Any] = {}
    contexts: list[dict[str, Any]] = []
    for key, rows in sorted(train_groups.items()):
        val = val_groups.get(key, [])
        if len(rows) < min_train or len(val) < min_val:
            continue
        base_val = _eq_metrics(val, None, target=target, context_level=context_level)
        candidates = []
        for model in _fit_eq_group(rows, target=target, shrink_k=shrink_k):
            fit_val = _eq_metrics(val, {key: model}, target=target,
                                  context_level=context_level)
            gain = float(base_val["mae_pp"] - fit_val["mae_pp"])
            candidates.append((gain, model, fit_val))
        candidates.sort(key=lambda x: x[0], reverse=True)
        best_gain, best_model, best_fit_val = candidates[0]
        item = {
            "context": key,
            "model": best_model,
            "train_raw": _eq_metrics(rows, None, target=target,
                                     context_level=context_level),
            "val_raw": base_val,
            "val_fit": best_fit_val,
            "val_mae_gain_pp": round(best_gain, 3),
        }
        contexts.append(item)
        if best_gain >= min_mae_gain_pp:
            accepted[key] = best_model

    contexts.sort(key=lambda x: (x["val_mae_gain_pp"], x["val_raw"]["n"]), reverse=True)
    return {
        "accepted": accepted,
        "contexts": contexts,
        "overall_val_raw": _eq_metrics(val_rows, None, target=target,
                                       context_level=context_level),
        "overall_val_fit": _eq_metrics(val_rows, accepted, target=target,
                                       context_level=context_level),
    }


def _print_summary(report: dict[str, Any]) -> None:
    bucket = report["bucket"]
    eq = report["equity"]
    print("=== Bucket ===")
    print("raw    ", bucket["overall_val_raw"])
    print("current", bucket.get("overall_val_current", {}))
    print("fit    ", bucket["overall_val_fit"])
    print(f"accepted contexts: {len(bucket['accepted'])}")
    print()
    print("Top bucket contexts:")
    for item in bucket["contexts"][:8]:
        print(
            f"  {item['context']:<45} "
            f"nll_gain={item['val_nll_gain']:+.4f} "
            f"top1 {item['val_base']['top1_pct']:.1f}->{item['val_fit']['top1_pct']:.1f} "
            f"under10 {item['val_base']['under_10_pct']:.1f}->{item['val_fit']['under_10_pct']:.1f}"
        )
    print()
    print("=== Equity ===")
    print("raw", eq["overall_val_raw"])
    print("fit", eq["overall_val_fit"])
    print(f"accepted contexts: {len(eq['accepted'])}")
    print()
    print("Top equity contexts:")
    for item in eq["contexts"][:8]:
        print(
            f"  {item['context']:<45} "
            f"mae_gain={item['val_mae_gain_pp']:+.2f}pp "
            f"mae {item['val_raw']['mae_pp']:.2f}->{item['val_fit']['mae_pp']:.2f} "
            f"bias {item['val_raw']['bias_pp']:+.2f}->{item['val_fit']['bias_pp']:+.2f}"
        )
    rel = report.get("river_relative")
    if rel and rel.get("skipped"):
        print()
        print("=== River Relative ===")
        print("skipped")
    elif rel:
        print()
        print("=== River Relative ===")
        print("raw", rel["overall_val_raw"])
        print("fit", rel["overall_val_fit"])
        print(f"accepted contexts: {len(rel['accepted'])}")
        print()
        print("Top river-relative contexts:")
        for item in rel["contexts"][:8]:
            print(
                f"  {item['context']:<65} "
                f"mae_gain={item['val_mae_gain_pp']:+.2f}pp "
                f"mae {item['val_raw']['mae_pp']:.2f}->{item['val_fit']['mae_pp']:.2f} "
                f"bias {item['val_raw']['bias_pp']:+.2f}->{item['val_fit']['bias_pp']:+.2f}"
            )


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--train-rows", type=Path, action="append", required=True)
    ap.add_argument("--val-rows", type=Path, action="append", required=True)
    ap.add_argument("--test-rows", type=Path, action="append", default=[])
    ap.add_argument("--report-out", type=Path)
    ap.add_argument("--bucket-params-out", type=Path)
    ap.add_argument("--equity-params-out", type=Path)
    ap.add_argument("--river-relative-params-out", type=Path)
    ap.add_argument("--bucket-context", choices=("simple", "street_trigger_nopp", "rich"),
                    default="simple")
    ap.add_argument("--equity-context", choices=("simple", "action", "rich"),
                    default="action")
    ap.add_argument("--equity-target", choices=("multi", "hu"), default="multi")
    ap.add_argument("--relative-context", choices=("simple", "action", "rich"),
                    default="rich")
    ap.add_argument("--min-bucket-train", type=int, default=120)
    ap.add_argument("--min-bucket-val", type=int, default=50)
    ap.add_argument("--min-equity-train", type=int, default=80)
    ap.add_argument("--min-equity-val", type=int, default=35)
    ap.add_argument("--min-relative-train", type=int, default=30)
    ap.add_argument("--min-relative-val", type=int, default=12)
    ap.add_argument("--bucket-steps", type=int, default=800)
    ap.add_argument("--bucket-lr", type=float, default=0.035)
    ap.add_argument("--bucket-l2-theta", type=float, default=0.02)
    ap.add_argument("--bucket-l2-gamma", type=float, default=0.12)
    ap.add_argument("--min-bucket-nll-gain", type=float, default=0.015)
    ap.add_argument("--min-equity-mae-gain-pp", type=float, default=1.0)
    ap.add_argument("--min-relative-mae-gain-pp", type=float, default=1.0)
    ap.add_argument("--equity-shrink-k", type=float, default=80.0)
    ap.add_argument("--relative-shrink-k", type=float, default=35.0)
    ap.add_argument("--skip-river-relative", action="store_true")
    args = ap.parse_args()

    train_rows = _load_rows(args.train_rows)
    val_rows = _load_rows(args.val_rows)
    test_rows = _load_rows(args.test_rows) if args.test_rows else []

    bucket = fit_bucket(
        train_rows,
        val_rows,
        context_level=args.bucket_context,
        min_train=args.min_bucket_train,
        min_val=args.min_bucket_val,
        steps=args.bucket_steps,
        lr=args.bucket_lr,
        l2_theta=args.bucket_l2_theta,
        l2_gamma=args.bucket_l2_gamma,
        min_nll_gain=args.min_bucket_nll_gain,
    )
    current = _current_bucket_params()
    if args.bucket_context == "simple" and current:
        bucket["overall_val_current"] = _bucket_metrics(
            val_rows, current, context_level="simple"
        )

    equity = fit_equity(
        train_rows,
        val_rows,
        target=args.equity_target,
        context_level=args.equity_context,
        min_train=args.min_equity_train,
        min_val=args.min_equity_val,
        min_mae_gain_pp=args.min_equity_mae_gain_pp,
        shrink_k=args.equity_shrink_k,
    )
    if args.skip_river_relative:
        river_relative = {"skipped": True}
    else:
        river_relative = fit_equity(
            train_rows,
            val_rows,
            target="relative",
            context_level="relative:" + args.relative_context,
            min_train=args.min_relative_train,
            min_val=args.min_relative_val,
            min_mae_gain_pp=args.min_relative_mae_gain_pp,
            shrink_k=args.relative_shrink_k,
        )

    report: dict[str, Any] = {
        "meta": {
            "train_rows": len(train_rows),
            "val_rows": len(val_rows),
            "test_rows": len(test_rows),
            "bucket_context": args.bucket_context,
            "equity_context": args.equity_context,
            "equity_target": args.equity_target,
            "relative_context": args.relative_context,
        },
        "bucket": bucket,
        "equity": equity,
        "river_relative": river_relative,
    }

    if test_rows:
        report["bucket"]["overall_test_raw"] = _bucket_metrics(
            test_rows, None, context_level=args.bucket_context
        )
        report["bucket"]["overall_test_fit"] = _bucket_metrics(
            test_rows, bucket["accepted"], context_level=args.bucket_context
        )
        if args.bucket_context == "simple" and current:
            report["bucket"]["overall_test_current"] = _bucket_metrics(
                test_rows, current, context_level="simple"
            )
        report["equity"]["overall_test_raw"] = _eq_metrics(
            test_rows, None, target=args.equity_target,
            context_level=args.equity_context,
        )
        report["equity"]["overall_test_fit"] = _eq_metrics(
            test_rows, equity["accepted"], target=args.equity_target,
            context_level=args.equity_context,
        )
        if not args.skip_river_relative:
            report["river_relative"]["overall_test_raw"] = _eq_metrics(
                test_rows, None, target="relative",
                context_level="relative:" + args.relative_context,
            )
            report["river_relative"]["overall_test_fit"] = _eq_metrics(
                test_rows, river_relative["accepted"], target="relative",
                context_level="relative:" + args.relative_context,
            )

    _write_json(args.report_out, report)
    _write_json(args.bucket_params_out, bucket["accepted"])
    _write_json(args.equity_params_out, equity["accepted"])
    if not args.skip_river_relative:
        _write_json(args.river_relative_params_out, river_relative["accepted"])
    _print_summary(report)


if __name__ == "__main__":
    main()
