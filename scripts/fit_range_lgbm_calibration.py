"""Fit the Range V2 bucket-ML calibration model (LightGBM) from showdown rows.

Rows come from `scripts/extract_range_calibration_rows_parallel.py --mode bucket`
(or the live recorder). Features are built by the RUNTIME feature function
(`bucket_ml_calibration._feature_values`) so train/serve skew is impossible;
acceptance is two-sided (strong+nuts mass must not be over- or under-stated)
and relative to the raw formula distribution. Workflow: scripts/README.md.

The hero-equity and river-relative LightGBM layers this script used to fit were
removed on 2026-11-11: retrained with feature parity they did not beat the raw
inputs on a time-ordered hold-out.
"""
from __future__ import annotations

import argparse
import json
import os
import warnings
from pathlib import Path
from typing import Any, Iterable

os.environ.setdefault("MPLCONFIGDIR", "/private/tmp/matplotlib")
os.environ.setdefault("LOKY_MAX_CPU_COUNT", str(os.cpu_count() or 1))
warnings.filterwarnings("ignore", category=UserWarning, module="joblib")
warnings.filterwarnings("ignore", message="X does not have valid feature names.*")

import numpy as np
from lightgbm import LGBMClassifier
from sklearn.feature_extraction import DictVectorizer

from scripts.range_calibration_meta import (
    drop_robot_rows,
    filter_rows_by_meta,
    limit_rows,
    meta_summary,
    parse_flag_filters,
)

CAT_ORDER = ("nuts", "strong", "medium", "draw", "weak_draw", "air")
CAT_IDX = {cat: i for i, cat in enumerate(CAT_ORDER)}
EPS = 1e-6


# --------------------------------------------------------------------------- rows

def _load_rows(paths: Iterable[Path], limit: int = 0) -> list[dict[str, Any]]:
    """Read JSONL rows; tolerates part files whose records were concatenated on one line."""
    dec = json.JSONDecoder()
    rows: list[dict[str, Any]] = []
    for path in paths:
        with Path(path).open("r", encoding="utf-8") as f:
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
                    rows.append(obj)
                    if limit > 0 and len(rows) >= limit:
                        return rows
    return rows


def _write_json(path: Path | None, obj: Any) -> None:
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def _bucket_vec(row: dict[str, Any]) -> np.ndarray:
    dist = row.get("bucket_dist") or {}
    arr = np.array([float(dist.get(cat, 0.0) or 0.0) for cat in CAT_ORDER], dtype=np.float64)
    total = float(arr.sum())
    if total > 0:
        arr /= total
    else:
        arr[:] = 1.0 / len(CAT_ORDER)
    return np.clip(arr, EPS, 1.0)


def _label_idx(row: dict[str, Any]) -> int:
    return CAT_IDX[str(row.get("actual_bucket"))]


def _bucket_rows(rows: list[dict[str, Any]], streets: set[str]) -> list[dict[str, Any]]:
    return [r for r in rows if r.get("actual_bucket") in CAT_IDX and str(r.get("street")) in streets]


def _bucket_features_runtime(row: dict[str, Any], *, profile_features: bool = True) -> dict[str, float]:
    """Bucket-model features built by the RUNTIME feature function.

    This is the only way the bucket model may be featurised: the same
    `bucket_ml_calibration._feature_values` that `BayesianRangeTracker` calls
    live, fed with the fields the extractor recorded at prediction time. Any
    feature the runtime cannot supply therefore cannot leak into training.
    """
    from pokerfate.core.card import Card
    from pokerfate.strategy.range_v2 import bucket_ml_calibration as bml

    dist = row.get("bucket_dist") or {}
    probs = np.array([float(dist.get(cat, 0.0) or 0.0) for cat in CAT_ORDER], dtype=np.float64)
    total = float(probs.sum())
    probs = probs / total if total > EPS else np.full(len(CAT_ORDER), 1.0 / len(CAT_ORDER))
    profile = row.get("player_profile") if profile_features else None
    return bml._feature_values(
        probs,
        street=str(row.get("street") or ""),
        trigger=str(row.get("trigger") or ""),
        active_count=int(row.get("active_player_count") or 0),
        board=[Card.from_str(c) for c in (row.get("board") or [])],
        range_pct=float(row.get("range_pct") or 0.0),
        hero_bucket=str(row.get("hero_bucket") or ""),
        position=str(row.get("position") or ""),
        is_ip=bool(row.get("is_ip") or False),
        facing_action=str(row.get("facing_action") or ""),
        preflop_action_type=str(row.get("preflop_action_type") or ""),
        action_bet_ratio=float(row.get("action_bet_ratio") or 0.0),
        bet_size_bucket=str(row.get("bet_size_bucket") or ""),
        is_raise_over=bool(row.get("is_raise_over") or False),
        action_sequence=str(row.get("action_sequence") or ""),
        player_profile=dict(profile) if isinstance(profile, dict) and profile else None,
    )


# ------------------------------------------------------------------------ metrics

def _mass_bias_cells(
    rows: list[dict[str, Any]],
    strong_nuts_combo: np.ndarray,
    strong_nuts_mask: np.ndarray,
    min_cell_rows: int = 100,
) -> dict[str, Any]:
    """Predicted vs actual strong+nuts mass, overall and per (street, trigger) cell."""
    actual = strong_nuts_mask.astype(np.float64)
    overall = float(np.mean(strong_nuts_combo) - np.mean(actual)) * 100.0 if len(rows) else 0.0
    cells: dict[str, dict[str, float]] = {}
    keys = [f"{r.get('street')} {r.get('trigger') or '?'}" for r in rows]
    for key in sorted(set(keys)):
        idx = np.array([k == key for k in keys], dtype=bool)
        n = int(idx.sum())
        if n < min_cell_rows:
            continue
        cells[key] = {
            "n": n,
            "pred_pct": round(float(np.mean(strong_nuts_combo[idx])) * 100.0, 2),
            "actual_pct": round(float(np.mean(actual[idx])) * 100.0, 2),
            "bias_pp": round(float(np.mean(strong_nuts_combo[idx]) - np.mean(actual[idx])) * 100.0, 2),
        }
    max_abs = max((abs(c["bias_pp"]) for c in cells.values()), default=0.0)
    return {"overall_pp": round(overall, 2), "max_abs_cell_pp": round(max_abs, 2), "cells": cells}


def _bucket_metrics(rows: list[dict[str, Any]], probs: np.ndarray) -> dict[str, Any]:
    if not rows:
        return {"n": 0}
    y = np.array([_label_idx(r) for r in rows], dtype=np.int64)
    py = probs[np.arange(len(rows)), y]
    strong_nuts_mask = np.array([r.get("actual_bucket") in ("strong", "nuts") for r in rows], dtype=bool)
    brier = float(np.mean(np.sum((probs - np.eye(len(CAT_ORDER))[y]) ** 2, axis=1)))
    strong_nuts_combo = probs[:, CAT_IDX["strong"]] + probs[:, CAT_IDX["nuts"]]
    mass_bias = _mass_bias_cells(rows, strong_nuts_combo, strong_nuts_mask)
    return {
        "n": len(rows),
        "nll": round(float(-np.mean(np.log(np.clip(py, EPS, 1.0)))), 5),
        "brier": round(brier, 5),
        "actual_bucket_avg_pct": round(float(np.mean(py) * 100.0), 2),
        "under_10_pct": round(float(np.mean(py < 0.10) * 100.0), 2),
        "top1_pct": round(float(np.mean(np.argmax(probs, axis=1) == y) * 100.0), 2),
        # Two-sided calibration of the aggregate strong+nuts mass (the quantity the
        # decision layer consumes). The pre-2026-11 gate only forbade under-stating
        # strong hands and produced a model that ran +6..+20pp hot live.
        "strong_nuts_mass_bias_pp": mass_bias["overall_pp"],
        "strong_nuts_mass_cell_max_abs_pp": mass_bias["max_abs_cell_pp"],
        "strong_nuts_mass_cells": mass_bias["cells"],
        "strong_nuts_under_20_pct": round(
            float(np.mean(py[strong_nuts_mask] < 0.20) * 100.0) if bool(strong_nuts_mask.any()) else 0.0, 2),
        "strong_nuts_combo_under_20_pct": round(
            float(np.mean(strong_nuts_combo[strong_nuts_mask] < 0.20) * 100.0) if bool(strong_nuts_mask.any()) else 0.0, 2),
        "strong_nuts_combo_avg_pct": round(
            float(np.mean(strong_nuts_combo[strong_nuts_mask]) * 100.0) if bool(strong_nuts_mask.any()) else 0.0, 2),
    }


def _bucket_risk_summary(raw: dict[str, Any], fit: dict[str, Any]) -> dict[str, Any]:
    raw_cells = raw.get("strong_nuts_mass_cells") or {}
    fit_cells = fit.get("strong_nuts_mass_cells") or {}
    return {
        "strong_nuts_under_20_delta_pp": round(
            float(fit.get("strong_nuts_under_20_pct", 0.0)) - float(raw.get("strong_nuts_under_20_pct", 0.0)), 2),
        "strong_nuts_combo_under_20_delta_pp": round(
            float(fit.get("strong_nuts_combo_under_20_pct", 0.0)) - float(raw.get("strong_nuts_combo_under_20_pct", 0.0)), 2),
        "strong_nuts_combo_avg_delta_pp": round(
            float(fit.get("strong_nuts_combo_avg_pct", 0.0)) - float(raw.get("strong_nuts_combo_avg_pct", 0.0)), 2),
        "strong_nuts_mass_bias_pp": float(fit.get("strong_nuts_mass_bias_pp", 0.0)),
        "strong_nuts_mass_cell_max_abs_pp": float(fit.get("strong_nuts_mass_cell_max_abs_pp", 0.0)),
        # worst per-cell change of |bias| relative to raw (positive = fit further from actual)
        "strong_nuts_mass_cell_worsen_pp": round(max(
            (abs(float(c["bias_pp"])) - abs(float(raw_cells.get(k, c)["bias_pp"])) for k, c in fit_cells.items()),
            default=0.0,
        ), 2),
    }


def _select_bucket_blend(
    rows: list[dict[str, Any]],
    raw_probs: np.ndarray,
    model_probs: np.ndarray,
    *,
    min_bucket_nll_gain: float,
    max_strong_nuts_under_worsen_pp: float,
    max_strong_nuts_combo_under_worsen_pp: float,
    max_mass_bias_pp: float,
    max_mass_cell_bias_pp: float,
    max_mass_cell_worsen_pp: float,
    pinned_alpha: float | None = None,
) -> dict[str, Any]:
    """Pick the blend weight alpha (runtime: (1-alpha)*raw + alpha*model).

    Among alphas that satisfy every gate, the one with the largest NLL gain wins.
    If none does, alpha=0 and the model is marked unusable.  ``pinned_alpha`` skips the
    search: the gates were passed on a real hold-out and this fit only adds its sessions.
    """
    raw_m = _bucket_metrics(rows, raw_probs)
    best: dict[str, Any] | None = None
    for alpha in (np.linspace(0.05, 1.0, 20) if pinned_alpha is None else (float(pinned_alpha),)):
        blended = (1.0 - float(alpha)) * raw_probs + float(alpha) * model_probs
        blended = np.clip(blended, EPS, 1.0)
        blended /= blended.sum(axis=1, keepdims=True)
        metrics = _bucket_metrics(rows, blended)
        risk = _bucket_risk_summary(raw_m, metrics)
        nll_gain = round(float(raw_m["nll"] - metrics["nll"]), 5)
        usable = (
            nll_gain >= min_bucket_nll_gain
            and risk["strong_nuts_under_20_delta_pp"] <= max_strong_nuts_under_worsen_pp
            and risk["strong_nuts_combo_under_20_delta_pp"] <= max_strong_nuts_combo_under_worsen_pp
            and abs(risk["strong_nuts_mass_bias_pp"]) <= max_mass_bias_pp
            and risk["strong_nuts_mass_cell_max_abs_pp"] <= max_mass_cell_bias_pp
            and risk["strong_nuts_mass_cell_worsen_pp"] <= max_mass_cell_worsen_pp
        )
        candidate = {"alpha": round(float(alpha), 2), "metrics": metrics, "risk": risk, "nll_gain": nll_gain, "usable": usable}
        if pinned_alpha is not None:
            return {**candidate, "usable": True, "pinned": True}
        if usable and (best is None or candidate["nll_gain"] > best["nll_gain"]
                       or (candidate["nll_gain"] == best["nll_gain"] and candidate["alpha"] > best["alpha"])):
            best = candidate
    if best is not None:
        return best
    return {"alpha": 0.0, "metrics": raw_m, "risk": _bucket_risk_summary(raw_m, raw_m), "nll_gain": 0.0, "usable": False}


def _full_class_proba(clf: LGBMClassifier, probs: np.ndarray) -> np.ndarray:
    out = np.full((probs.shape[0], len(CAT_ORDER)), EPS, dtype=np.float64)
    for col, cls in enumerate(clf.classes_):
        out[:, int(cls)] = probs[:, col]
    out /= out.sum(axis=1, keepdims=True)
    return out


# --------------------------------------------------------------------------- main

def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--train-rows", type=Path, action="append", required=True)
    ap.add_argument("--val-rows", type=Path, action="append", required=True,
                    help="hold-out rows; use the most recent session(s), never a random split")
    ap.add_argument("--report-out", type=Path)
    ap.add_argument("--bucket-model-out", type=Path)
    ap.add_argument("--bucket-streets", default="flop,turn,river")
    ap.add_argument("--bucket-profile-features", choices=("on", "off"), default="off",
                    help="feed the opponent profile recorded at prediction time to the model "
                         "(2026-11-11: hurt on hold-out, hence off by default)")
    ap.add_argument("--max-train-rows", type=int, default=0)
    ap.add_argument("--max-val-rows", type=int, default=0)
    ap.add_argument("--n-estimators", type=int, default=200)
    ap.add_argument("--learning-rate", type=float, default=0.03)
    ap.add_argument("--num-leaves", type=int, default=7)
    ap.add_argument("--min-child-samples", type=int, default=80)
    ap.add_argument("--reg-lambda", type=float, default=20.0)
    ap.add_argument("--n-jobs", type=int, default=1)
    ap.add_argument("--bucket-strong-nuts-weight", type=float, default=1.0,
                    help="sample weight for strong/nuts rows; >1 teaches the model to over-state "
                         "villain strength (the 2026-11-05 model used 2.0 and ran +6..+20pp hot live)")
    ap.add_argument("--min-bucket-nll-gain", type=float, default=0.001)
    ap.add_argument("--max-bucket-mass-bias-pp", type=float, default=3.0,
                    help="usable only if |mean predicted strong+nuts mass - actual share| <= this (pp)")
    ap.add_argument("--max-bucket-mass-cell-bias-pp", type=float, default=8.0,
                    help="usable only if every (street, trigger) cell with >=100 val rows is within this (pp)")
    ap.add_argument("--max-bucket-mass-cell-worsen-pp", type=float, default=2.0,
                    help="usable only if no such cell drifts further from actual than raw by more than this (pp)")
    ap.add_argument("--max-strong-nuts-under-worsen-pp", type=float, default=2.0)
    ap.add_argument("--max-strong-nuts-combo-under-worsen-pp", type=float, default=2.0)
    ap.add_argument("--train-strategy-version")
    ap.add_argument("--val-strategy-version")
    ap.add_argument("--train-experiment-flag", action="append", default=[])
    ap.add_argument("--val-experiment-flag", action="append", default=[])
    ap.add_argument("--blend-alpha", type=float, default=None,
                    help="use this blend instead of selecting it on --val-rows: for the final fit on "
                         "all sessions, after the gates were passed and alpha chosen on a real hold-out")
    ap.add_argument("--robot-registry", type=Path, default=None,
                    help="robot registry file (default local/models/robots.json)")
    args = ap.parse_args()

    raw_train_rows = _load_rows(args.train_rows)
    raw_val_rows = _load_rows(args.val_rows)
    # Rows about house robots never train a model.
    from pokerfate.core.robots import RobotRegistry
    registry = RobotRegistry(args.robot_registry, autosave=False)
    robot_rows = {"excluded": True, "registry": registry.counts()}
    raw_train_rows, robot_rows["train"] = drop_robot_rows(raw_train_rows, registry)
    raw_val_rows, robot_rows["val"] = drop_robot_rows(raw_val_rows, registry)
    # The runtime applies the model when a player acts and when a board card lands.  A
    # ``fold_other`` row is the unchanged range of a player who stayed in while somebody else
    # folded: the model is never applied there, and which of those players reach showdown
    # depends on what happened next.  Such rows neither train nor gate the model.
    raw_train_rows = [r for r in raw_train_rows if r.get("trigger") != "action:fold_other"]
    raw_val_rows = [r for r in raw_val_rows if r.get("trigger") != "action:fold_other"]
    train_flag_filter = parse_flag_filters(args.train_experiment_flag)
    val_flag_filter = parse_flag_filters(args.val_experiment_flag)
    train_rows = limit_rows(filter_rows_by_meta(raw_train_rows, strategy_version=args.train_strategy_version,
                                                experiment_flags=train_flag_filter), args.max_train_rows)
    val_rows = limit_rows(filter_rows_by_meta(raw_val_rows, strategy_version=args.val_strategy_version,
                                              experiment_flags=val_flag_filter), args.max_val_rows)
    # The model corrects one particular formula layer: remember which (rows carry its
    # fingerprint), so the runtime can refuse the model once the layer below has changed.
    formula_fits = {r.get("formula_fit") for r in train_rows} - {None}
    if len(formula_fits) > 1:
        raise SystemExit(f"training rows were extracted with different formula fits: {sorted(formula_fits)}")
    formula_fit = next(iter(formula_fits), None)
    streets = {s.strip() for s in args.bucket_streets.split(",") if s.strip()}
    tr = _bucket_rows(train_rows, streets)
    va = _bucket_rows(val_rows, streets)
    report: dict[str, Any] = {
        "meta": {
            "data_meta": {"train": meta_summary(train_rows), "val": meta_summary(val_rows)},
            "row_filters": {
                "train_strategy_version": args.train_strategy_version,
                "val_strategy_version": args.val_strategy_version,
                "train_experiment_flags": train_flag_filter,
                "val_experiment_flags": val_flag_filter,
            },
            "bucket_rows": {"train": len(tr), "val": len(va)},
            "robot_rows_dropped": robot_rows,
        }
    }
    if not tr or not va:
        report["bucket"] = {"error": "no bucket rows after filtering"}
        _write_json(args.report_out, report)
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
        return

    profile_features = args.bucket_profile_features == "on"
    vec = DictVectorizer(sparse=True)
    x_tr = vec.fit_transform([_bucket_features_runtime(r, profile_features=profile_features) for r in tr])
    x_va = vec.transform([_bucket_features_runtime(r, profile_features=profile_features) for r in va])
    y_tr = np.array([_label_idx(r) for r in tr], dtype=np.int64)
    clf = LGBMClassifier(
        objective="multiclass", num_class=len(CAT_ORDER), n_estimators=args.n_estimators,
        learning_rate=args.learning_rate, num_leaves=args.num_leaves, min_child_samples=args.min_child_samples,
        reg_lambda=args.reg_lambda, subsample=0.9, colsample_bytree=0.9, n_jobs=args.n_jobs,
        random_state=42, verbose=-1,
    )
    fit_kwargs: dict[str, Any] = {}
    if args.bucket_strong_nuts_weight > 1.0:
        weights = np.ones(len(y_tr), dtype=np.float64)
        weights[(y_tr == CAT_IDX["strong"]) | (y_tr == CAT_IDX["nuts"])] = float(args.bucket_strong_nuts_weight)
        fit_kwargs["sample_weight"] = weights
    clf.fit(x_tr, y_tr, **fit_kwargs)
    raw_tr = np.vstack([_bucket_vec(r) for r in tr])
    raw_va = np.vstack([_bucket_vec(r) for r in va])
    lgb_tr = _full_class_proba(clf, clf.predict_proba(x_tr))
    lgb_va = _full_class_proba(clf, clf.predict_proba(x_va))
    raw_val_m = _bucket_metrics(va, raw_va)
    lgb_val_m = _bucket_metrics(va, lgb_va)
    selected = _select_bucket_blend(
        va, raw_va, lgb_va,
        min_bucket_nll_gain=args.min_bucket_nll_gain,
        max_strong_nuts_under_worsen_pp=args.max_strong_nuts_under_worsen_pp,
        max_strong_nuts_combo_under_worsen_pp=args.max_strong_nuts_combo_under_worsen_pp,
        max_mass_bias_pp=args.max_bucket_mass_bias_pp,
        max_mass_cell_bias_pp=args.max_bucket_mass_cell_bias_pp,
        max_mass_cell_worsen_pp=args.max_bucket_mass_cell_worsen_pp,
        pinned_alpha=args.blend_alpha,
    )
    runtime_usable = bool(selected["usable"])
    train_args = {k: getattr(args, k) for k in (
        "bucket_profile_features", "n_estimators", "learning_rate", "num_leaves", "min_child_samples", "reg_lambda",
        "bucket_strong_nuts_weight", "min_bucket_nll_gain", "max_bucket_mass_bias_pp", "max_bucket_mass_cell_bias_pp",
        "max_bucket_mass_cell_worsen_pp", "max_strong_nuts_under_worsen_pp", "max_strong_nuts_combo_under_worsen_pp",
    )}
    train_args["row_filters"] = report["meta"]["row_filters"]
    if args.bucket_model_out is not None:
        _write_json(args.bucket_model_out, {
            "type": "bucket_lgbm_calibration",
            "cat_order": list(CAT_ORDER),
            "feature_names": list(vec.feature_names_),
            "classes": [int(c) for c in clf.classes_],
            "blend_alpha": selected["alpha"],
            "runtime_usable": runtime_usable,
            "formula_fit": formula_fit,
            "model_str": clf.booster_.model_to_string(),
            "selected_blend": selected,
            "feature_source": "pokerfate.strategy.range_v2.bucket_ml_calibration._feature_values",
            "profile_features": profile_features,
            "train_args": train_args,
        })
    report["bucket"] = {
        "features": len(vec.feature_names_),
        "train_raw": _bucket_metrics(tr, raw_tr),
        "train_lgbm": _bucket_metrics(tr, lgb_tr),
        "val_raw": raw_val_m,
        "val_lgbm": lgb_val_m,
        "val_nll_gain": round(raw_val_m["nll"] - lgb_val_m["nll"], 5),
        "val_brier_gain": round(raw_val_m["brier"] - lgb_val_m["brier"], 5),
        "val_risk": _bucket_risk_summary(raw_val_m, lgb_val_m),
        "selected_blend": selected,
        "runtime_usable": runtime_usable,
        "train_args": train_args,
    }
    _write_json(args.report_out, report)
    summary = {k: report["bucket"][k] for k in ("features", "val_nll_gain", "val_brier_gain", "runtime_usable")}
    summary["selected_alpha"] = selected["alpha"]
    summary["val_mass_bias_pp"] = selected["metrics"].get("strong_nuts_mass_bias_pp")
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
