"""Optional ML calibration for hero range equity."""

from __future__ import annotations

import json
import math
import os
from pathlib import Path
from typing import Any, Optional

import numpy as np

try:
    from lightgbm import Booster
except Exception:
    Booster = None

from pokerfate.strategy.range_v2.bucket_ml_calibration import CAT_ORDER
from pokerfate.strategy.range_v2.runtime_formula_calibration import bb_key

EPS = 1e-6
_ROOT = Path(__file__).resolve().parents[2] / "data" / "runtime_calibration"
_CACHE: dict[tuple[str, str], Optional[dict[str, Any]]] = {}
_BOOSTER_CACHE: dict[tuple[str, str], Any] = {}


def mode_for_big_blind(big_blind: Optional[float]) -> str:
    key = bb_key(big_blind)
    if key == "bb_10k":
        raw = os.environ.get("PF_EQUITY_ML_10K", "lgbm")
    elif key == "bb_50k":
        raw = os.environ.get("PF_EQUITY_ML_50K", "lgbm")
    else:
        raw = os.environ.get("PF_EQUITY_ML_DEFAULT", "off")
    mode = str(raw or "off").strip().lower()
    if mode in {"0", "false", "no", "none", "off", "disabled", "关"}:
        return "off"
    if mode in {"lgbm", "lightgbm"}:
        return "lgbm"
    if mode in {"fm", "factorization_machine", "factorization-machine"}:
        return "fm"
    return "off"


def experiment_flags() -> dict[str, str]:
    return {
        "PF_EQUITY_ML_10K": os.environ.get("PF_EQUITY_ML_10K", "lgbm"),
        "PF_EQUITY_ML_50K": os.environ.get("PF_EQUITY_ML_50K", "lgbm"),
        "PF_EQUITY_ML_DEFAULT": os.environ.get("PF_EQUITY_ML_DEFAULT", "off"),
    }


def clear_caches() -> None:
    _CACHE.clear()
    _BOOSTER_CACHE.clear()


def _model_path(big_blind: Optional[float], mode: str) -> Path:
    suffix = "fm" if mode == "fm" else "lgbm"
    return _ROOT / bb_key(big_blind) / f"runtime_{suffix}_equity_model.json"


def _load_model(big_blind: Optional[float], mode: str) -> Optional[dict[str, Any]]:
    if mode not in {"fm", "lgbm"}:
        return None
    cache_key = (bb_key(big_blind), mode)
    if cache_key in _CACHE:
        return _CACHE[cache_key]
    path = _model_path(big_blind, mode)
    if not path.exists():
        _CACHE[cache_key] = None
        return None
    try:
        model = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        _CACHE[cache_key] = None
        return None
    if not model.get("runtime_usable", False):
        _CACHE[cache_key] = None
        return None
    if float(model.get("blend_alpha", 0.0) or 0.0) <= 0:
        _CACHE[cache_key] = None
        return None
    _CACHE[cache_key] = model
    return model


def _nopp_bin(n: int) -> str:
    if n <= 1:
        return "1"
    if n == 2:
        return "2"
    return "3+"


def _norm_action_ctx(action_ctx: str) -> str:
    if action_ctx in {"bet", "raise", "call", "check", "fold_other", "board", "passive"}:
        return action_ctx
    return "passive"


def _feature_values(
    raw_eq: float,
    bucket_dist: dict[str, float],
    *,
    street: str,
    action_ctx: str,
    active_count: int,
    board_len: int,
    board_texture: str,
    range_pct: float,
    hero_bucket: str,
) -> dict[str, float]:
    probs = np.array([float(bucket_dist.get(cat, 0.0) or 0.0) for cat in CAT_ORDER], dtype=np.float64)
    total = float(probs.sum())
    if total > EPS:
        probs /= total
    else:
        probs[:] = 1.0 / len(CAT_ORDER)
    probs = np.clip(probs, EPS, 1.0)
    probs /= float(probs.sum())
    ordered = np.sort(probs)[::-1]
    top_bucket = CAT_ORDER[int(np.argmax(probs))]
    eq = float(np.clip(raw_eq, EPS, 1.0 - EPS))
    out: dict[str, float] = {
        "range_pct": float(range_pct),
        "board_len": min(max(int(board_len or 0), 0), 5) / 5.0,
        "top_prob": float(ordered[0]),
        "top_margin": float(ordered[0] - ordered[1]) if len(ordered) > 1 else 0.0,
        "entropy": float(-np.sum(probs * np.log(np.clip(probs, EPS, 1.0))) / math.log(len(CAT_ORDER))),
        "raw_eq": eq,
        "raw_eq_logit": float(np.log(eq / (1.0 - eq)) / 8.0),
        f"street={street or '?'}": 1.0,
        f"trigger=?": 1.0,
        f"action={_norm_action_ctx(action_ctx or '')}": 1.0,
        f"nopp={_nopp_bin(active_count)}": 1.0,
        f"texture={board_texture or 'pre'}": 1.0,
        f"hero_bucket={hero_bucket or '?'}": 1.0,
        f"top_bucket={top_bucket}": 1.0,
        "strategy_version=__OTHER__": 1.0,
        "experiment_profile=__OTHER__": 1.0,
    }
    for cat, val in zip(CAT_ORDER, probs):
        v = float(val)
        out[f"p_{cat}"] = v
        out[f"logp_{cat}"] = float(np.log(max(v, EPS)) / 8.0)
    return out


def _vector_from_feature_names(features: dict[str, float], feature_names: list[str]) -> np.ndarray:
    return np.array([[float(features.get(name, 0.0)) for name in feature_names]], dtype=np.float64)


def calibrate_equity(
    raw_eq: float,
    *,
    big_blind: Optional[float],
    bucket_dist: dict[str, float] | None,
    street: str,
    action_ctx: str,
    active_count: int,
    board_len: int,
    board_texture: str,
    range_pct: float,
    hero_bucket: str,
) -> tuple[float, dict[str, Any]]:
    base = max(0.0, min(1.0, float(raw_eq)))
    mode = mode_for_big_blind(big_blind)
    if mode == "off":
        return base, {"mode": mode, "used": False, "reason": "mode_off"}
    model = _load_model(big_blind, mode)
    if not model:
        return base, {"mode": mode, "used": False, "reason": "model_missing"}
    if mode != "lgbm":
        return base, {"mode": mode, "used": False, "reason": "mode_unsupported"}
    if Booster is None:
        return base, {"mode": mode, "used": False, "reason": "lightgbm_missing"}
    feature_names = list(model.get("feature_names") or [])
    model_str = str(model.get("model_str") or "")
    if not feature_names or not model_str:
        return base, {"mode": mode, "used": False, "reason": "model_invalid"}
    try:
        cache_key = (bb_key(big_blind), mode)
        booster = _BOOSTER_CACHE.get(cache_key)
        if booster is None:
            booster = Booster(model_str=model_str)
            _BOOSTER_CACHE[cache_key] = booster
        features = _feature_values(
            base,
            dict(bucket_dist or {}),
            street=street,
            action_ctx=action_ctx,
            active_count=active_count,
            board_len=board_len,
            board_texture=board_texture,
            range_pct=range_pct,
            hero_bucket=hero_bucket,
        )
        pred = float(np.asarray(booster.predict(_vector_from_feature_names(features, feature_names))).reshape(-1)[0])
    except Exception:
        return base, {"mode": mode, "used": False, "reason": "predict_failed"}
    pred = max(0.0, min(1.0, pred))
    alpha = max(0.0, min(1.0, float(model.get("blend_alpha", 0.0) or 0.0)))
    out = max(0.0, min(1.0, (1.0 - alpha) * base + alpha * pred))
    return out, {
        "mode": mode,
        "used": True,
        "alpha": alpha,
        "input": base,
        "prediction": pred,
        "output": out,
    }
