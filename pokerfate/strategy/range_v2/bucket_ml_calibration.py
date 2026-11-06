"""Optional LightGBM bucket calibration on top of formula bucket calibration."""

from __future__ import annotations

import importlib
import json
import math
import os
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

import numpy as np

from pokerfate.core.card import Card
from pokerfate.strategy.range_v2 import hand_categorizer as hcat
from pokerfate.strategy.range_v2 import hand_combo_map as hcm
from pokerfate.strategy.range_v2 import board_analyzer as _board_analyzer

try:
    Booster = importlib.import_module("lightgbm").Booster
except Exception:
    Booster = None

CAT_ORDER = ("nuts", "strong", "medium", "draw", "weak_draw", "air")
EPS = 1e-6
_ROOT = Path(__file__).resolve().parents[2] / "data" / "runtime_calibration"
_MODEL_KEY = "all_bb"
_CACHE: Dict[tuple[str, str], Optional[dict[str, Any]]] = {}
_BOOSTER_CACHE: Dict[tuple[str, str], Any] = {}


def mode_for_big_blind(big_blind: Optional[float]) -> str:
    raw = os.environ.get("PF_BUCKET_ML", "off")
    mode = str(raw or "off").strip().lower()
    if mode in {"0", "false", "no", "none", "off", "disabled"}:
        return "off"
    if mode in {"lgbm", "lightgbm"}:
        return "lgbm"
    return "off"


def experiment_flags() -> dict[str, str]:
    return {
        "PF_BUCKET_ML": os.environ.get("PF_BUCKET_ML", "off"),
    }


def _model_path(big_blind: Optional[float], mode: str) -> Path:
    return _ROOT / _MODEL_KEY / "runtime_lgbm_bucket_model.json"


def _load_model(big_blind: Optional[float], mode: str) -> Optional[dict[str, Any]]:
    if mode != "lgbm":
        return None
    cache_key = (_MODEL_KEY, mode)
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


def _clip01(value: Any, scale: float = 1.0) -> float:
    try:
        x = float(value or 0.0)
    except Exception:
        x = 0.0
    if scale > 0:
        x /= scale
    return max(0.0, min(1.0, x))


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


def _board_features(board: Iterable[Card] | None) -> dict[str, Any]:
    cards = list(board or [])
    if not cards:
        return {
            "wetness": 0.0,
            "paired": False,
            "monotone": False,
            "flush_possible": False,
            "flush_draw": False,
            "straight_possible": False,
            "straight_draw_heavy": False,
            "high_card_rank": 0,
            "connectedness": 0.0,
        }
    sig = _board_analyzer.analyze(cards)
    return {
        "wetness": float(sig.wetness),
        "paired": bool(sig.paired),
        "monotone": bool(sig.monotone),
        "flush_possible": bool(sig.flush_possible),
        "flush_draw": bool(sig.flush_draw),
        "straight_possible": bool(sig.straight_possible),
        "straight_draw_heavy": bool(sig.straight_draw_heavy),
        "high_card_rank": int(sig.high_card_rank or 0),
        "connectedness": float(sig.connectedness),
    }


def _experiment_profile() -> str:
    keys = (
        "PF_TURN_FLOP_RELATIVE_GUARD",
        "PF_RUNTIME_RANGE_CALIBRATION",
        "PF_BUCKET_CALIBRATION",
        "PF_BUCKET_ML",
    )
    defaults = {
        "PF_TURN_FLOP_RELATIVE_GUARD": "1",
        "PF_RUNTIME_RANGE_CALIBRATION": "1",
        "PF_BUCKET_CALIBRATION": "1",
        "PF_BUCKET_ML": "off",
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
    position: str = "",
    is_ip: bool = False,
    facing_action: str = "",
    preflop_action_type: str = "",
    action_bet_ratio: float = 0.0,
    bet_size_bucket: str = "",
    is_raise_over: bool = False,
    action_sequence: str = "",
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
        f"position={position or '?'}": 1.0,
        f"is_ip={'ip' if is_ip else 'oop'}": 1.0,
        f"facing_action={facing_action or '?'}": 1.0,
        f"preflop_action_type={preflop_action_type or '?'}": 1.0,
        f"bet_size_bucket={bet_size_bucket or 'none'}": 1.0,
        f"action_sequence={action_sequence or '?'}": 1.0,
        "action_bet_ratio": _clip01(action_bet_ratio, 4.0),
        "is_raise_over": 1.0 if is_raise_over else 0.0,
    }
    board_raw = _board_features(board)
    for key in (
        "paired", "monotone", "flush_possible", "flush_draw",
        "straight_possible", "straight_draw_heavy",
    ):
        out[f"board_{key}"] = 1.0 if board_raw.get(key) else 0.0
    out["board_wetness"] = _clip01(board_raw.get("wetness"), 1.0)
    out["board_connectedness"] = _clip01(board_raw.get("connectedness"), 1.0)
    out["board_high_card_rank"] = _clip01(board_raw.get("high_card_rank"), 14.0)
    for cat, val in zip(CAT_ORDER, probs):
        v = float(val)
        out[f"p_{cat}"] = v
        out[f"logp_{cat}"] = float(np.log(max(v, EPS)) / 8.0)
    return out


def _vector_from_feature_names(features: dict[str, float], feature_names: list[str]) -> np.ndarray:
    return np.array([[float(features.get(name, 0.0)) for name in feature_names]], dtype=np.float64)


def _predict_lgbm(
    model: dict[str, Any],
    probs: np.ndarray,
    features: dict[str, float],
    *,
    big_blind: Optional[float],
    mode: str,
) -> np.ndarray:
    if Booster is None:
        return probs
    cache_key = (_MODEL_KEY, mode)
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
    position: str = "",
    is_ip: bool = False,
    facing_action: str = "",
    preflop_action_type: str = "",
    action_bet_ratio: float = 0.0,
    bet_size_bucket: str = "",
    is_raise_over: bool = False,
    action_sequence: str = "",
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
        position=position,
        is_ip=is_ip,
        facing_action=facing_action,
        preflop_action_type=preflop_action_type,
        action_bet_ratio=action_bet_ratio,
        bet_size_bucket=bet_size_bucket,
        is_raise_over=is_raise_over,
        action_sequence=action_sequence,
    )
    ml_probs = _predict_lgbm(model, probs, features, big_blind=big_blind, mode=mode)
    alpha = max(0.0, min(1.0, float(model.get("blend_alpha", 0.0) or 0.0)))
    blended = (1.0 - alpha) * probs + alpha * ml_probs
    blended = np.clip(blended, EPS, 1.0)
    blended /= float(blended.sum())
    return (
        {cat: float(val) for cat, val in zip(CAT_ORDER, blended)},
        {"mode": mode, "used": True, "alpha": alpha},
    )
