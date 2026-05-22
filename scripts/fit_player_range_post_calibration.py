"""Fit per-player post calibration on top of baseline range calibration.

This script does not train player-type or scenario buckets.  It trains one
small residual model per individual player:

* bucket: q = softmax(gamma * log(base_probs) + theta)
* equity/relative equity: calibrated = bias/linear(base_calibrated)

The baseline model should come from fit_range_calibration_v2.py.  If a player
does not pass validation gates, runtime should keep using baseline.
"""

from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable, Optional

import numpy as np

from scripts.fit_range_calibration_v2 import (
    CAT_IDX,
    CAT_ORDER,
    EPS,
    _actual_relation_eq,
    _apply_eq_model,
    _bucket_context,
    _bucket_probs,
    _ece,
    _eq_context,
    _eq_pairs,
    _eq_raw,
    _label_idx,
    _load_rows,
    _softmax,
    _write_json,
)


def _load_json(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {}
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _player_key(row: dict[str, Any], *, include_unknown: bool) -> str | None:
    name = str(row.get("player") or "").strip()
    if name and name != "?":
        return name
    if include_unknown and row.get("player_id") is not None:
        return f"id:{row.get('player_id')}"
    return None


def _baseline_bucket_probs(
    row: dict[str, Any],
    baseline_params: dict[str, Any],
    *,
    context_level: str,
) -> np.ndarray:
    params = baseline_params.get(_bucket_context(row, context_level))
    return _bucket_probs(row, params)


def _apply_bucket_player_model(base_probs: np.ndarray, model: Optional[dict[str, Any]]) -> np.ndarray:
    if not model:
        return np.clip(base_probs, EPS, 1.0)
    gamma = float(model.get("gamma", 1.0))
    theta_dict = model.get("theta", {}) or {}
    theta = np.array([float(theta_dict.get(cat, 0.0)) for cat in CAT_ORDER], dtype=np.float64)
    return _softmax(gamma * np.log(np.clip(base_probs[None, :], EPS, 1.0)) + theta[None, :])[0]


def _bucket_metrics(
    rows: list[dict[str, Any]],
    *,
    baseline_params: dict[str, Any],
    baseline_context: str,
    player_models: Optional[dict[str, Any]] = None,
    include_unknown: bool = False,
) -> dict[str, Any]:
    usable = [
        r for r in rows
        if r.get("street") in ("flop", "turn", "river")
        and r.get("actual_bucket") in CAT_IDX
    ]
    if not usable:
        return {
            "n": 0,
            "nll": 0.0,
            "actual_bucket_avg_pct": 0.0,
            "under_10_pct": 0.0,
            "top1_pct": 0.0,
            "strong_nuts_under_20_pct": 0.0,
            "strong_nuts_combo_under_20_pct": 0.0,
            "strong_nuts_combo_avg_pct": 0.0,
        }

    labels = np.array([_label_idx(r) for r in usable], dtype=np.int64)
    probs = []
    for row in usable:
        base = _baseline_bucket_probs(row, baseline_params, context_level=baseline_context)
        model = None
        if player_models:
            key = _player_key(row, include_unknown=include_unknown)
            model = player_models.get(key) if key else None
        probs.append(_apply_bucket_player_model(base, model))
    q = np.vstack(probs)
    py = q[np.arange(len(usable)), labels]
    strong_nuts_mask = np.array([
        row.get("actual_bucket") in ("strong", "nuts") for row in usable
    ], dtype=bool)
    if bool(strong_nuts_mask.any()):
        strong_nuts_under = float(np.mean(py[strong_nuts_mask] < 0.20) * 100.0)
        strong_nuts_combo = q[:, CAT_IDX["strong"]] + q[:, CAT_IDX["nuts"]]
        strong_nuts_combo_under = float(
            np.mean(strong_nuts_combo[strong_nuts_mask] < 0.20) * 100.0
        )
        strong_nuts_combo_avg = float(np.mean(strong_nuts_combo[strong_nuts_mask]) * 100.0)
    else:
        strong_nuts_under = 0.0
        strong_nuts_combo_under = 0.0
        strong_nuts_combo_avg = 0.0
    return {
        "n": len(usable),
        "nll": round(float(-np.mean(np.log(np.clip(py, EPS, 1.0)))), 5),
        "actual_bucket_avg_pct": round(float(np.mean(py) * 100.0), 2),
        "under_10_pct": round(float(np.mean(py < 0.10) * 100.0), 2),
        "top1_pct": round(float(np.mean(np.argmax(q, axis=1) == labels) * 100.0), 2),
        "strong_nuts_under_20_pct": round(strong_nuts_under, 2),
        "strong_nuts_combo_under_20_pct": round(strong_nuts_combo_under, 2),
        "strong_nuts_combo_avg_pct": round(strong_nuts_combo_avg, 2),
    }


def _fit_bucket_player(
    rows: list[dict[str, Any]],
    *,
    baseline_params: dict[str, Any],
    baseline_context: str,
    steps: int,
    lr: float,
    l2_theta: float,
    l2_gamma: float,
) -> dict[str, Any]:
    base = np.vstack([
        _baseline_bucket_probs(row, baseline_params, context_level=baseline_context)
        for row in rows
    ])
    logp = np.log(np.clip(base, EPS, 1.0))
    labels = np.array([_label_idx(row) for row in rows], dtype=np.int64)
    onehot = np.zeros((len(rows), len(CAT_ORDER)), dtype=np.float64)
    onehot[np.arange(len(rows)), labels] = 1.0

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
        grad_gamma = float((diff * logp).sum(axis=1).mean() + 2.0 * l2_gamma * (gamma - 1.0))

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

        gamma = float(np.clip(gamma, 0.65, 1.50))
        theta = np.clip(theta, -0.75, 0.75)
        theta -= float(theta.mean())

    return {
        "gamma": round(float(gamma), 4),
        "theta": {
            cat: round(float(v), 4)
            for cat, v in zip(CAT_ORDER, theta)
            if abs(float(v)) >= 0.005
        },
    }


def fit_player_bucket(
    train_rows: list[dict[str, Any]],
    val_rows: list[dict[str, Any]],
    *,
    baseline_params: dict[str, Any],
    baseline_context: str,
    include_unknown: bool,
    min_train: int,
    min_val: int,
    steps: int,
    lr: float,
    l2_theta: float,
    l2_gamma: float,
    min_nll_gain: float,
    max_strong_nuts_under_worsen_pp: float,
    max_strong_nuts_combo_under_worsen_pp: float,
) -> dict[str, Any]:
    train_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    val_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in train_rows:
        if row.get("street") not in ("flop", "turn", "river"):
            continue
        if row.get("actual_bucket") not in CAT_IDX:
            continue
        key = _player_key(row, include_unknown=include_unknown)
        if key:
            train_groups[key].append(row)
    for row in val_rows:
        if row.get("street") not in ("flop", "turn", "river"):
            continue
        if row.get("actual_bucket") not in CAT_IDX:
            continue
        key = _player_key(row, include_unknown=include_unknown)
        if key:
            val_groups[key].append(row)

    accepted: dict[str, Any] = {}
    players: list[dict[str, Any]] = []
    for key, rows in sorted(train_groups.items()):
        val = val_groups.get(key, [])
        if len(rows) < min_train or len(val) < min_val:
            continue
        model = _fit_bucket_player(
            rows,
            baseline_params=baseline_params,
            baseline_context=baseline_context,
            steps=steps,
            lr=lr,
            l2_theta=l2_theta,
            l2_gamma=l2_gamma,
        )
        base_val = _bucket_metrics(
            val,
            baseline_params=baseline_params,
            baseline_context=baseline_context,
            include_unknown=include_unknown,
        )
        fit_val = _bucket_metrics(
            val,
            baseline_params=baseline_params,
            baseline_context=baseline_context,
            player_models={key: model},
            include_unknown=include_unknown,
        )
        val_gain = float(base_val["nll"] - fit_val["nll"])
        strong_delta = (
            float(fit_val["strong_nuts_under_20_pct"])
            - float(base_val["strong_nuts_under_20_pct"])
        )
        combo_delta = (
            float(fit_val["strong_nuts_combo_under_20_pct"])
            - float(base_val["strong_nuts_combo_under_20_pct"])
        )
        accepted_ok = (
            val_gain >= min_nll_gain
            and strong_delta <= max_strong_nuts_under_worsen_pp
            and combo_delta <= max_strong_nuts_combo_under_worsen_pp
        )
        item = {
            "player": key,
            "model": model,
            "train_base": _bucket_metrics(
                rows,
                baseline_params=baseline_params,
                baseline_context=baseline_context,
                include_unknown=include_unknown,
            ),
            "train_fit": _bucket_metrics(
                rows,
                baseline_params=baseline_params,
                baseline_context=baseline_context,
                player_models={key: model},
                include_unknown=include_unknown,
            ),
            "val_base": base_val,
            "val_fit": fit_val,
            "val_nll_gain": round(val_gain, 5),
            "val_strong_nuts_under_20_delta_pp": round(strong_delta, 2),
            "val_strong_nuts_combo_under_20_delta_pp": round(combo_delta, 2),
            "accepted": accepted_ok,
            "reject_reasons": [
                reason
                for reason, failed in (
                    ("nll_gain", val_gain < min_nll_gain),
                    (
                        "strong_nuts_under_20",
                        strong_delta > max_strong_nuts_under_worsen_pp,
                    ),
                    (
                        "strong_nuts_combo_under_20",
                        combo_delta > max_strong_nuts_combo_under_worsen_pp,
                    ),
                )
                if failed
            ],
        }
        players.append(item)
        if accepted_ok:
            accepted[key] = model

    players.sort(key=lambda x: (x["val_nll_gain"], x["val_base"]["n"]), reverse=True)
    return {
        "accepted": accepted,
        "players": players,
        "overall_val_base": _bucket_metrics(
            val_rows,
            baseline_params=baseline_params,
            baseline_context=baseline_context,
            include_unknown=include_unknown,
        ),
        "overall_val_post": _bucket_metrics(
            val_rows,
            baseline_params=baseline_params,
            baseline_context=baseline_context,
            player_models=accepted,
            include_unknown=include_unknown,
        ),
    }


def _baseline_eq_pred(
    row: dict[str, Any],
    *,
    target: str,
    baseline_models: dict[str, Any],
    context_level: str,
) -> tuple[float, float]:
    pred, actual = _eq_raw(row, target)
    model = baseline_models.get(_eq_context(row, context_level))
    return float(_apply_eq_model(np.array([pred], dtype=np.float64), model)[0]), float(actual)


def _eq_metrics_player(
    rows: list[dict[str, Any]],
    *,
    target: str,
    baseline_models: dict[str, Any],
    context_level: str,
    player_models: Optional[dict[str, Any]] = None,
    include_unknown: bool = False,
) -> dict[str, Any]:
    pairs = _eq_pairs(rows, target=target)
    if not pairs:
        return {"n": 0, "mae_pp": 0.0, "rmse_pp": 0.0, "bias_pp": 0.0, "ece_pp": 0.0}
    preds = []
    actuals = []
    for row in pairs:
        pred, actual = _baseline_eq_pred(
            row,
            target=target,
            baseline_models=baseline_models,
            context_level=context_level,
        )
        if player_models:
            key = _player_key(row, include_unknown=include_unknown)
            model = player_models.get(key) if key else None
            pred = float(_apply_eq_model(np.array([pred], dtype=np.float64), model)[0])
        preds.append(pred)
        actuals.append(actual)
    pred_arr = np.array(preds, dtype=np.float64)
    actual_arr = np.array(actuals, dtype=np.float64)
    err = pred_arr - actual_arr
    return {
        "n": len(pairs),
        "mae_pp": round(float(np.mean(np.abs(err)) * 100.0), 2),
        "rmse_pp": round(float(math.sqrt(np.mean(err * err))) * 100.0, 2),
        "bias_pp": round(float(np.mean(err) * 100.0), 2),
        "ece_pp": round(_ece(pred_arr, actual_arr) * 100.0, 2),
    }


def _fit_eq_player_group(
    rows: list[dict[str, Any]],
    *,
    target: str,
    baseline_models: dict[str, Any],
    context_level: str,
    shrink_k: float,
    linear_min_train: int,
) -> list[dict[str, Any]]:
    x_vals = []
    y_vals = []
    for row in rows:
        x, y = _baseline_eq_pred(
            row,
            target=target,
            baseline_models=baseline_models,
            context_level=context_level,
        )
        x_vals.append(x)
        y_vals.append(y)
    x = np.array(x_vals, dtype=np.float64)
    y = np.array(y_vals, dtype=np.float64)
    n = len(rows)
    shrink = n / (n + shrink_k) if shrink_k > 0 else 1.0

    raw_bias = float(np.mean(y - x))
    bias = float(np.clip(raw_bias, -0.30, 0.30) * shrink)
    models = [{"type": "bias", "bias": round(bias, 5), "raw_bias": round(raw_bias, 5)}]

    if n >= linear_min_train and float(np.var(x)) > 1e-6:
        a, b = np.polyfit(x, y, deg=1)
        a = float(np.clip(a, 0.35, 1.80))
        b = float(np.clip(b, -0.45, 0.45))
        a = 1.0 + shrink * (a - 1.0)
        b = shrink * b
        models.append({"type": "linear", "a": round(a, 5), "b": round(b, 5)})
    return models


def fit_player_equity(
    train_rows: list[dict[str, Any]],
    val_rows: list[dict[str, Any]],
    *,
    target: str,
    baseline_models: dict[str, Any],
    context_level: str,
    include_unknown: bool,
    min_train: int,
    min_val: int,
    min_mae_gain_pp: float,
    shrink_k: float,
    linear_min_train: int,
) -> dict[str, Any]:
    train_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    val_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in _eq_pairs(train_rows, target=target):
        key = _player_key(row, include_unknown=include_unknown)
        if key:
            train_groups[key].append(row)
    for row in _eq_pairs(val_rows, target=target):
        key = _player_key(row, include_unknown=include_unknown)
        if key:
            val_groups[key].append(row)

    accepted: dict[str, Any] = {}
    players: list[dict[str, Any]] = []
    for key, rows in sorted(train_groups.items()):
        val = val_groups.get(key, [])
        if len(rows) < min_train or len(val) < min_val:
            continue
        base_val = _eq_metrics_player(
            val,
            target=target,
            baseline_models=baseline_models,
            context_level=context_level,
            include_unknown=include_unknown,
        )
        candidates = []
        for model in _fit_eq_player_group(
            rows,
            target=target,
            baseline_models=baseline_models,
            context_level=context_level,
            shrink_k=shrink_k,
            linear_min_train=linear_min_train,
        ):
            fit_val = _eq_metrics_player(
                val,
                target=target,
                baseline_models=baseline_models,
                context_level=context_level,
                player_models={key: model},
                include_unknown=include_unknown,
            )
            gain = float(base_val["mae_pp"] - fit_val["mae_pp"])
            candidates.append((gain, model, fit_val))
        candidates.sort(key=lambda x: x[0], reverse=True)
        best_gain, best_model, best_fit_val = candidates[0]
        accepted_ok = best_gain >= min_mae_gain_pp
        item = {
            "player": key,
            "model": best_model,
            "train_base": _eq_metrics_player(
                rows,
                target=target,
                baseline_models=baseline_models,
                context_level=context_level,
                include_unknown=include_unknown,
            ),
            "train_fit": _eq_metrics_player(
                rows,
                target=target,
                baseline_models=baseline_models,
                context_level=context_level,
                player_models={key: best_model},
                include_unknown=include_unknown,
            ),
            "val_base": base_val,
            "val_fit": best_fit_val,
            "val_mae_gain_pp": round(best_gain, 3),
            "accepted": accepted_ok,
            "reject_reasons": [] if accepted_ok else ["mae_gain"],
        }
        players.append(item)
        if accepted_ok:
            accepted[key] = best_model

    players.sort(key=lambda x: (x["val_mae_gain_pp"], x["val_base"]["n"]), reverse=True)
    return {
        "accepted": accepted,
        "players": players,
        "overall_val_base": _eq_metrics_player(
            val_rows,
            target=target,
            baseline_models=baseline_models,
            context_level=context_level,
            include_unknown=include_unknown,
        ),
        "overall_val_post": _eq_metrics_player(
            val_rows,
            target=target,
            baseline_models=baseline_models,
            context_level=context_level,
            player_models=accepted,
            include_unknown=include_unknown,
        ),
    }


def _inspect_rows(
    rows: Iterable[dict[str, Any]],
    *,
    hand_filter: set[int],
    player_filter: set[str],
    bucket_params: dict[str, Any],
    bucket_context: str,
    bucket_models: dict[str, Any],
    equity_models: dict[str, Any],
    equity_context: str,
    equity_player_models: dict[str, Any],
    relative_models: dict[str, Any],
    relative_context: str,
    relative_player_models: dict[str, Any],
    include_unknown: bool,
    limit: int,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in rows:
        hand = row.get("hand")
        if hand_filter and hand not in hand_filter:
            continue
        key = _player_key(row, include_unknown=include_unknown)
        if player_filter and (key not in player_filter):
            continue
        item: dict[str, Any] = {
            "hand": hand,
            "player": key,
            "street": row.get("street"),
            "trigger": row.get("trigger"),
            "actual_bucket": row.get("actual_bucket"),
        }
        if row.get("street") in ("flop", "turn", "river") and row.get("actual_bucket") in CAT_IDX:
            base = _baseline_bucket_probs(row, bucket_params, context_level=bucket_context)
            post = _apply_bucket_player_model(base, bucket_models.get(key) if key else None)
            label = _label_idx(row)
            item["bucket"] = {
                "base_actual_pct": round(float(base[label]) * 100.0, 2),
                "post_actual_pct": round(float(post[label]) * 100.0, 2),
                "base_strong_nuts_pct": round(
                    float(base[CAT_IDX["strong"]] + base[CAT_IDX["nuts"]]) * 100.0, 2
                ),
                "post_strong_nuts_pct": round(
                    float(post[CAT_IDX["strong"]] + post[CAT_IDX["nuts"]]) * 100.0, 2
                ),
            }
        for target, base_models, ctx, player_models in (
            ("multi", equity_models, equity_context, equity_player_models),
            ("relative", relative_models, "relative:" + relative_context, relative_player_models),
        ):
            try:
                base_pred, actual = _baseline_eq_pred(
                    row,
                    target=target,
                    baseline_models=base_models,
                    context_level=ctx,
                )
            except Exception:
                continue
            post_pred = float(_apply_eq_model(
                np.array([base_pred], dtype=np.float64),
                player_models.get(key) if key else None,
            )[0])
            item[target] = {
                "base_pct": round(base_pred * 100.0, 2),
                "post_pct": round(post_pred * 100.0, 2),
                "actual_pct": round(float(actual) * 100.0, 2),
            }
        out.append(item)
        if len(out) >= limit:
            break
    return out


def _print_summary(report: dict[str, Any]) -> None:
    print("=== Player post calibration ===")
    print("train rows", report["meta"]["train_rows"], "val rows", report["meta"]["val_rows"])
    bucket = report["bucket"]
    print()
    print("Bucket base", bucket["overall_val_base"])
    print("Bucket post", bucket["overall_val_post"])
    print("accepted bucket players", len(bucket["accepted"]))
    for item in bucket["players"][:8]:
        print(
            f"  {item['player']:<16} n={item['val_base']['n']:>4} "
            f"nll_gain={item['val_nll_gain']:+.4f} "
            f"top1 {item['val_base']['top1_pct']:.1f}->{item['val_fit']['top1_pct']:.1f} "
            f"SNcombo<20 {item['val_strong_nuts_combo_under_20_delta_pp']:+.1f}pp "
            f"{'ok' if item['accepted'] else 'reject:' + ','.join(item['reject_reasons'])}"
        )
    print()
    equity = report["equity"]
    print("Equity base", equity["overall_val_base"])
    print("Equity post", equity["overall_val_post"])
    print("accepted equity players", len(equity["accepted"]))
    for item in equity["players"][:8]:
        print(
            f"  {item['player']:<16} n={item['val_base']['n']:>4} "
            f"mae_gain={item['val_mae_gain_pp']:+.2f}pp "
            f"mae {item['val_base']['mae_pp']:.2f}->{item['val_fit']['mae_pp']:.2f} "
            f"{'ok' if item['accepted'] else 'reject'}"
        )
    relative = report["river_relative"]
    print()
    print("Relative base", relative["overall_val_base"])
    print("Relative post", relative["overall_val_post"])
    print("accepted relative players", len(relative["accepted"]))
    for item in relative["players"][:8]:
        print(
            f"  {item['player']:<16} n={item['val_base']['n']:>4} "
            f"mae_gain={item['val_mae_gain_pp']:+.2f}pp "
            f"mae {item['val_base']['mae_pp']:.2f}->{item['val_fit']['mae_pp']:.2f} "
            f"{'ok' if item['accepted'] else 'reject'}"
        )
    if report.get("inspect"):
        print()
        print("Inspect examples")
        for item in report["inspect"][:20]:
            print(item)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--train-rows", type=Path, action="append", required=True)
    ap.add_argument("--val-rows", type=Path, action="append", required=True)
    ap.add_argument("--inspect-rows", type=Path, action="append", default=[])
    ap.add_argument("--baseline-bucket-params", type=Path)
    ap.add_argument("--baseline-equity-params", type=Path)
    ap.add_argument("--baseline-relative-params", type=Path)
    ap.add_argument("--model-out", type=Path)
    ap.add_argument("--report-out", type=Path)
    ap.add_argument("--bucket-context", choices=("simple", "street_trigger_nopp", "rich"), default="simple")
    ap.add_argument("--equity-context", choices=("simple", "action", "rich"), default="action")
    ap.add_argument("--relative-context", choices=("simple", "action", "rich"), default="rich")
    ap.add_argument("--include-unknown", action="store_true")
    ap.add_argument("--min-bucket-train", type=int, default=40)
    ap.add_argument("--min-bucket-val", type=int, default=12)
    ap.add_argument("--min-equity-train", type=int, default=35)
    ap.add_argument("--min-equity-val", type=int, default=12)
    ap.add_argument("--min-relative-train", type=int, default=15)
    ap.add_argument("--min-relative-val", type=int, default=6)
    ap.add_argument("--bucket-steps", type=int, default=500)
    ap.add_argument("--bucket-lr", type=float, default=0.025)
    ap.add_argument("--bucket-l2-theta", type=float, default=0.08)
    ap.add_argument("--bucket-l2-gamma", type=float, default=0.30)
    ap.add_argument("--min-bucket-nll-gain", type=float, default=0.005)
    ap.add_argument("--max-bucket-strong-nuts-under-worsen-pp", type=float, default=0.0)
    ap.add_argument("--max-bucket-strong-nuts-combo-under-worsen-pp", type=float, default=0.0)
    ap.add_argument("--min-equity-mae-gain-pp", type=float, default=0.8)
    ap.add_argument("--min-relative-mae-gain-pp", type=float, default=0.8)
    ap.add_argument("--equity-shrink-k", type=float, default=120.0)
    ap.add_argument("--relative-shrink-k", type=float, default=60.0)
    ap.add_argument("--linear-min-train", type=int, default=60)
    ap.add_argument("--focus-hand", type=int, action="append", default=[])
    ap.add_argument("--focus-player", action="append", default=[])
    ap.add_argument("--inspect-limit", type=int, default=80)
    args = ap.parse_args()

    train_rows = _load_rows(args.train_rows)
    val_rows = _load_rows(args.val_rows)
    inspect_rows = _load_rows(args.inspect_rows) if args.inspect_rows else train_rows + val_rows
    bucket_params = _load_json(args.baseline_bucket_params)
    equity_params = _load_json(args.baseline_equity_params)
    relative_params = _load_json(args.baseline_relative_params)

    bucket = fit_player_bucket(
        train_rows,
        val_rows,
        baseline_params=bucket_params,
        baseline_context=args.bucket_context,
        include_unknown=args.include_unknown,
        min_train=args.min_bucket_train,
        min_val=args.min_bucket_val,
        steps=args.bucket_steps,
        lr=args.bucket_lr,
        l2_theta=args.bucket_l2_theta,
        l2_gamma=args.bucket_l2_gamma,
        min_nll_gain=args.min_bucket_nll_gain,
        max_strong_nuts_under_worsen_pp=args.max_bucket_strong_nuts_under_worsen_pp,
        max_strong_nuts_combo_under_worsen_pp=args.max_bucket_strong_nuts_combo_under_worsen_pp,
    )
    equity = fit_player_equity(
        train_rows,
        val_rows,
        target="multi",
        baseline_models=equity_params,
        context_level=args.equity_context,
        include_unknown=args.include_unknown,
        min_train=args.min_equity_train,
        min_val=args.min_equity_val,
        min_mae_gain_pp=args.min_equity_mae_gain_pp,
        shrink_k=args.equity_shrink_k,
        linear_min_train=args.linear_min_train,
    )
    river_relative = fit_player_equity(
        train_rows,
        val_rows,
        target="relative",
        baseline_models=relative_params,
        context_level="relative:" + args.relative_context,
        include_unknown=args.include_unknown,
        min_train=args.min_relative_train,
        min_val=args.min_relative_val,
        min_mae_gain_pp=args.min_relative_mae_gain_pp,
        shrink_k=args.relative_shrink_k,
        linear_min_train=args.linear_min_train,
    )

    focus_hands = set(args.focus_hand)
    focus_players = set(args.focus_player)
    inspect = _inspect_rows(
        inspect_rows,
        hand_filter=focus_hands,
        player_filter=focus_players,
        bucket_params=bucket_params,
        bucket_context=args.bucket_context,
        bucket_models=bucket["accepted"],
        equity_models=equity_params,
        equity_context=args.equity_context,
        equity_player_models=equity["accepted"],
        relative_models=relative_params,
        relative_context=args.relative_context,
        relative_player_models=river_relative["accepted"],
        include_unknown=args.include_unknown,
        limit=args.inspect_limit,
    )

    report = {
        "meta": {
            "schema": "player_range_post_calibration_v1",
            "train_rows": len(train_rows),
            "val_rows": len(val_rows),
            "baseline_bucket_params": str(args.baseline_bucket_params) if args.baseline_bucket_params else "",
            "baseline_equity_params": str(args.baseline_equity_params) if args.baseline_equity_params else "",
            "baseline_relative_params": str(args.baseline_relative_params) if args.baseline_relative_params else "",
            "bucket_context": args.bucket_context,
            "equity_context": args.equity_context,
            "relative_context": args.relative_context,
            "min_bucket_train": args.min_bucket_train,
            "min_bucket_val": args.min_bucket_val,
            "min_equity_train": args.min_equity_train,
            "min_equity_val": args.min_equity_val,
            "min_relative_train": args.min_relative_train,
            "min_relative_val": args.min_relative_val,
            "note": "Per-player residual only; no player-type or scenario calibration.",
        },
        "bucket": bucket,
        "equity": equity,
        "river_relative": river_relative,
        "inspect": inspect,
    }
    model = {
        "schema": "player_range_post_calibration_v1",
        "bucket": bucket["accepted"],
        "equity": equity["accepted"],
        "river_relative": river_relative["accepted"],
        "meta": report["meta"],
    }
    _write_json(args.report_out, report)
    _write_json(args.model_out, model)
    _print_summary(report)


if __name__ == "__main__":
    main()
