"""Optional ML bucket calibration on top of formula bucket calibration."""

from __future__ import annotations

import json
import math
import os
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

import numpy as np

from pokerfate.core.card import Card
from pokerfate.strategy.range_v2 import hand_categorizer as hcat
from pokerfate.strategy.range_v2 import hand_combo_map as hcm
from pokerfate.strategy.range_v2.runtime_formula_calibration import bb_key

CAT_ORDER = ("nuts", "strong", "medium", "draw", "weak_draw", "air")
EPS = 1e-6
_ROOT = Path(__file__).resolve().parents[2] / "data" / "runtime_calibration"
_CACHE: Dict[tuple[str, str], Optional[dict[str, Any]]] = {}
_BOOSTER_CACHE: Dict[tuple[str, str], Any] = {}


def mode_for_big_blind(big_blind: Optional[float]) -> str:
    key = bb_key(big_blind)
    if key == "bb_10k":
        raw = os.environ.get("PF_BUCKET_ML_10K", "off")
    elif key == "bb_50k":
        raw = os.environ.get("PF_BUCKET_ML_50K", "off")
    else:
        raw = os.environ.get("PF_BUCKET_ML_DEFAULT", "off")
    mode = str(raw or "off").strip().lower()
    if mode in {"0", "false", "no", "none", "off", "disabled"}:
        return "off"
    if mode in {"lgbm", "lightgbm"}:
        return "lgbm"
    return "off"


def experiment_flags() -> dict[str, str]:
    return {
        "PF_BUCKET_ML_10K": os.environ.get("PF_BUCKET_ML_10K", "off"),
        "PF_BUCKET_ML_50K": os.environ.get("PF_BUCKET_ML_50K", "off"),
        "PF_BUCKET_ML_DEFAULT": os.environ.get("PF_BUCKET_ML_DEFAULT", "off"),
    }


def _model_path(big_blind: Optional[float], mode: str) -> Path:
    return _ROOT / bb_key(big_blind) / "runtime_lgbm_bucket_model.json"


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


def _softmax(z: np.ndarray) -> np.ndarray:
    z = z - float(np.max(z))
    e = np.exp(z)
    return e / max(float(e.sum()), EPS)


def _nopp_bin(n: int) -> str:
    if n <= 1:
        return "1"
    if n == 2:
        return "2"
    return "3+"


def _action_ctx(trigger: str) -> str:
    if trigger in {"action:raise", "action:raise_over"}:
        return "raise"
    if trigger == "action:bet":
        return "bet"
    if trigger == "action:call":
        return "call"
    if trigger == "action:check":
        return "check"
    if trigger == "action:fold_other":
        return "fold_other"
    if trigger.startswith("board:"):
        return "board"
    return "passive"


def _board_texture(board: Iterable[Card] | None) -> str:
    cards = list(board or [])
    if len(cards) < 3:
        return "pre"
    ranks = [c.rank for c in cards]
    suits = [c.suit for c in cards]
    paired = len(set(ranks)) < len(ranks)
    if len(suits) >= 3 and len(set(suits[:3])) == 1:
        flush = "mono"
    elif len(suits) >= 3 and max(suits[:3].count(s) for s in set(suits[:3])) >= 2:
        flush = "fd"
    else:
        flush = "rainbow"
    return ("paired" if paired else "unpaired") + ":" + flush


def _experiment_profile() -> str:
    keys = (
        "PF_TURN_FLOP_RELATIVE_GUARD",
        "PF_RUNTIME_RANGE_CALIBRATION",
        "PF_BUCKET_CALIBRATION",
        "PF_BUCKET_ML_10K",
        "PF_BUCKET_ML_50K",
        "PF_BUCKET_ML_DEFAULT",
    )
    defaults = {
        "PF_TURN_FLOP_RELATIVE_GUARD": "1",
        "PF_RUNTIME_RANGE_CALIBRATION": "1",
        "PF_BUCKET_CALIBRATION": "1",
        "PF_BUCKET_ML_10K": "off",
        "PF_BUCKET_ML_50K": "off",
        "PF_BUCKET_ML_DEFAULT": "off",
    }
    return "|".join(f"{key}={os.environ.get(key, defaults[key])}" for key in keys)


def _hero_bucket(known_cards: Iterable[int], board: list[Card]) -> str:
    ints = list(known_cards or [])
    if len(ints) < 2:
        return "?"
    try:
        cards = [hcm.int_to_card(i) for i in sorted(ints)[:2]]
        return hcat.categorize_cards(cards, board)
    except Exception:
        return "?"


def _feature_values(
    probs: np.ndarray,
    *,
    street: str,
    trigger: str,
    active_count: int,
    board: list[Card],
    range_pct: float,
    hero_bucket: str,
) -> dict[str, float]:
    ordered = np.sort(probs)[::-1]
    entropy = float(-np.sum(probs * np.log(np.clip(probs, EPS, 1.0))) / math.log(len(CAT_ORDER)))
    top_bucket = CAT_ORDER[int(np.argmax(probs))]
    out: dict[str, float] = {
        "range_pct": float(range_pct),
        "board_len": min(len(board), 5) / 5.0,
        "nopp_scaled": min(max(active_count, 1), 6) / 6.0,
        "entropy": entropy,
        "top_prob": float(ordered[0]),
        "top_margin": float(ordered[0] - ordered[1]) if len(ordered) > 1 else 0.0,
        f"street={street or '?'}": 1.0,
        f"trigger={trigger or '?'}": 1.0,
        f"action={_action_ctx(trigger or '')}": 1.0,
        f"nopp={_nopp_bin(active_count)}": 1.0,
        f"texture={_board_texture(board)}": 1.0,
        f"hero_bucket={hero_bucket or '?'}": 1.0,
        f"top_bucket={top_bucket}": 1.0,
        "strategy_version=__OTHER__": 1.0,
        f"experiment_profile={_experiment_profile()}": 1.0,
    }
    for cat, val in zip(CAT_ORDER, probs):
        v = float(val)
        out[f"p_{cat}"] = v
        out[f"logp_{cat}"] = float(np.log(max(v, EPS)) / 8.0)
    return out


def _vector_from_feature_map(features: dict[str, float], feature_map: dict[str, int]) -> np.ndarray:
    x = np.zeros(len(feature_map), dtype=np.float64)
    for name, val in features.items():
        idx = feature_map.get(name)
        if idx is not None:
            x[idx] = float(val)
            continue
        if "=" in name:
            field = name.split("=", 1)[0]
            other = feature_map.get(f"{field}=__OTHER__")
            if other is not None:
                x[other] = 1.0
    return x


def _vector_from_feature_names(features: dict[str, float], feature_names: list[str]) -> np.ndarray:
    return np.array([[float(features.get(name, 0.0)) for name in feature_names]], dtype=np.float64)


def _predict_fm(model: dict[str, Any], probs: np.ndarray, features: dict[str, float]) -> np.ndarray:
    feature_map = model.get("feature_map") or {}
    x = _vector_from_feature_map(features, feature_map)
    w = np.array(model.get("w") or [], dtype=np.float64)
    b = np.array(model.get("b") or [], dtype=np.float64)
    v = np.array(model.get("v") or [], dtype=np.float64)
    if w.ndim != 2 or b.shape[0] != len(CAT_ORDER) or v.ndim != 3:
        return probs
    logits = np.log(np.clip(probs, EPS, 1.0)) + b + x @ w
    x2 = x * x
    for c in range(len(CAT_ORDER)):
        vc = v[:, :, c]
        xv = x @ vc
        x2v2 = x2 @ (vc * vc)
        logits[c] += 0.5 * float(np.sum(xv * xv - x2v2))
    return _softmax(logits)


def _predict_lgbm(
    model: dict[str, Any],
    probs: np.ndarray,
    features: dict[str, float],
    *,
    big_blind: Optional[float],
    mode: str,
) -> np.ndarray:
    try:
        from lightgbm import Booster
    except Exception:
        return probs
    cache_key = (bb_key(big_blind), mode)
    booster = _BOOSTER_CACHE.get(cache_key)
    if booster is None:
        model_str = str(model.get("model_str") or "")
        if not model_str:
            return probs
        booster = Booster(model_str=model_str)
        _BOOSTER_CACHE[cache_key] = booster
    feature_names = list(model.get("feature_names") or [])
    if not feature_names:
        return probs
    pred = np.asarray(booster.predict(_vector_from_feature_names(features, feature_names)))
    classes = [int(c) for c in (model.get("classes") or [])]
    out = np.full(len(CAT_ORDER), EPS, dtype=np.float64)
    if pred.ndim == 2:
        row = pred[0]
        for col, cls in enumerate(classes):
            if 0 <= cls < len(CAT_ORDER) and col < len(row):
                out[cls] = float(row[col])
    elif len(classes) == 2:
        p1 = float(pred[0])
        out[classes[1]] = p1
        out[classes[0]] = 1.0 - p1
    else:
        return probs
    out = np.clip(out, EPS, 1.0)
    return out / float(out.sum())


def calibrate_bucket_probs(
    bucket_probs: dict[str, float],
    *,
    big_blind: Optional[float],
    street: str,
    trigger: str,
    active_count: int,
    board: list[Card],
    range_pct: float,
    known_cards: Iterable[int],
) -> tuple[dict[str, float], dict[str, Any]]:
    mode = mode_for_big_blind(big_blind)
    if mode == "off":
        return {}, {}
    model = _load_model(big_blind, mode)
    if not model:
        return {}, {"mode": mode, "used": False, "reason": "model_missing"}
    probs = np.array([float(bucket_probs.get(cat, 0.0) or 0.0) for cat in CAT_ORDER], dtype=np.float64)
    total = float(probs.sum())
    if total <= EPS:
        return {}, {}
    probs /= total
    features = _feature_values(
        probs,
        street=street,
        trigger=trigger,
        active_count=active_count,
        board=board,
        range_pct=range_pct,
        hero_bucket=_hero_bucket(known_cards, board),
    )
    if mode == "fm":
        ml_probs = _predict_fm(model, probs, features)
    else:
        ml_probs = _predict_lgbm(model, probs, features, big_blind=big_blind, mode=mode)
    alpha = max(0.0, min(1.0, float(model.get("blend_alpha", 0.0) or 0.0)))
    blended = (1.0 - alpha) * probs + alpha * ml_probs
    blended = np.clip(blended, EPS, 1.0)
    blended /= float(blended.sum())
    return (
        {cat: float(val) for cat, val in zip(CAT_ORDER, blended)},
        {"mode": mode, "used": True, "alpha": alpha},
    )
