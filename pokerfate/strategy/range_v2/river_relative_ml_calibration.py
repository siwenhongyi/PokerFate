"""Optional ML calibration for river hero-relative distribution."""

from __future__ import annotations

import importlib
import json
import os
from pathlib import Path
from typing import Any, Optional

import numpy as np

from pokerfate.strategy.range_v2.equity_ml_calibration import (
    _feature_values,
    _vector_from_feature_names,
)

try:
    Booster = importlib.import_module("lightgbm").Booster
except Exception:
    Booster = None

EPS = 1e-12
_ROOT = Path(__file__).resolve().parents[2] / "data" / "runtime_calibration"
_MODEL_KEY = "all_bb"
_CACHE: dict[tuple[str, str], Optional[dict[str, Any]]] = {}
_BOOSTER_CACHE: dict[tuple[str, str], Any] = {}


def mode_for_big_blind(big_blind: Optional[float]) -> str:
    raw = os.environ.get("PF_RIVER_RELATIVE_ML", "off")
    mode = str(raw or "off").strip().lower()
    if mode in {"0", "false", "no", "none", "off", "disabled", "关"}:
        return "off"
    if mode in {"lgbm", "lightgbm"}:
        return "lgbm"
    return "off"


def clear_caches() -> None:
    _CACHE.clear()
    _BOOSTER_CACHE.clear()


def _model_path(big_blind: Optional[float], mode: str) -> Path:
    return _ROOT / _MODEL_KEY / "runtime_lgbm_relative_model.json"


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


def _normalize_relation(dist: dict[str, float] | None) -> dict[str, float]:
    rel = {
        "win": max(0.0, float((dist or {}).get("win", 0.0) or 0.0)),
        "tie": max(0.0, float((dist or {}).get("tie", 0.0) or 0.0)),
        "loss": max(0.0, float((dist or {}).get("loss", 0.0) or 0.0)),
    }
    total = sum(rel.values())
    if total <= EPS:
        return {}
    return {k: v / total for k, v in rel.items()}


def _relation_eq(dist: dict[str, float] | None) -> float:
    rel = dist or {}
    return float(rel.get("win", 0.0) or 0.0) + 0.5 * float(rel.get("tie", 0.0) or 0.0)


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _clamp_relation_to_bounds(
    dist: dict[str, float] | None,
    bounds: dict[str, bool] | None,
) -> dict[str, float]:
    rel = _normalize_relation(dist)
    if not rel or not bounds:
        return rel
    for key in ("win", "tie", "loss"):
        if bounds.get(key) is False:
            rel[key] = 0.0
    total = sum(rel.values())
    if total > EPS:
        return {k: v / total for k, v in rel.items()}
    possible = [k for k in ("win", "tie", "loss") if bounds.get(k)]
    if len(possible) == 1:
        return {
            "win": 1.0 if possible[0] == "win" else 0.0,
            "tie": 1.0 if possible[0] == "tie" else 0.0,
            "loss": 1.0 if possible[0] == "loss" else 0.0,
        }
    return rel


def _clamp_equity_to_bounds(equity: float, bounds: dict[str, bool] | None) -> float:
    eq = _clamp01(equity)
    if not bounds:
        return eq
    win = bool(bounds.get("win"))
    tie = bool(bounds.get("tie"))
    loss = bool(bounds.get("loss"))
    if win and not tie and not loss:
        return 1.0
    if loss and not win and not tie:
        return 0.0
    if tie and not win and not loss:
        return 0.5
    if not loss:
        eq = max(eq, 0.5 if tie else 1.0)
    if not win:
        eq = min(eq, 0.5 if tie else 0.0)
    return _clamp01(eq)


def _shift_relation_eq(dist: dict[str, float], target_eq: float) -> dict[str, float]:
    rel = _normalize_relation(dist)
    if not rel:
        return {}
    tie = rel.get("tie", 0.0)
    non_tie = max(0.0, 1.0 - tie)
    target_win = _clamp01(target_eq - 0.5 * tie)
    target_win = min(non_tie, target_win)
    return {
        "win": target_win,
        "tie": tie,
        "loss": max(0.0, non_tie - target_win),
    }


def calibrate_dist(
    dist: dict[str, float] | None,
    *,
    big_blind: Optional[float],
    bucket_dist: dict[str, float] | None,
    hero_bucket: str,
    hero_made_subtype: str,
    board_texture: str,
    action_ctx: str,
    exact_bounds: dict[str, bool] | None = None,
    street: str = "river",
    trigger: str = "",
    active_count: int = 1,
    board_len: int = 5,
    range_pct: float = 0.0,
    hero_hand_rank: str = "",
    position: str = "",
    is_ip: bool = False,
    facing_action: str = "",
    preflop_action_type: str = "",
    action_bet_ratio: float = 0.0,
    bet_size_bucket: str = "",
    is_raise_over: bool = False,
    action_sequence: str = "",
    board_features: dict[str, Any] | None = None,
    hero_draw: dict[str, Any] | None = None,
    hero_blockers: dict[str, Any] | None = None,
    player_profile: dict[str, Any] | None = None,
) -> tuple[dict[str, float], dict[str, Any]]:
    base_rel = _clamp_relation_to_bounds(dist, exact_bounds)
    if not base_rel:
        return {}, {"mode": "off", "used": False, "reason": "empty_dist"}
    base_eq = _relation_eq(base_rel)
    mode = mode_for_big_blind(big_blind)
    if mode == "off":
        return base_rel, {"mode": mode, "used": False, "reason": "mode_off"}
    model = _load_model(big_blind, mode)
    if not model:
        return base_rel, {"mode": mode, "used": False, "reason": "model_missing"}
    if Booster is None:
        return base_rel, {"mode": mode, "used": False, "reason": "lightgbm_missing"}

    feature_names = list(model.get("feature_names") or [])
    model_str = str(model.get("model_str") or "")
    if not feature_names or not model_str:
        return base_rel, {"mode": mode, "used": False, "reason": "model_invalid"}
    try:
        cache_key = (_MODEL_KEY, mode)
        booster = _BOOSTER_CACHE.get(cache_key)
        if booster is None:
            booster = Booster(model_str=model_str)
            _BOOSTER_CACHE[cache_key] = booster
        features = _feature_values(
            base_eq,
            dict(bucket_dist or {}),
            street=street,
            trigger=trigger,
            action_ctx=action_ctx,
            active_count=active_count,
            board_len=board_len,
            board_texture=board_texture,
            range_pct=range_pct,
            hero_bucket=hero_bucket,
            hero_made_subtype=hero_made_subtype,
            hero_hand_rank=hero_hand_rank,
            position=position,
            is_ip=is_ip,
            facing_action=facing_action,
            preflop_action_type=preflop_action_type,
            action_bet_ratio=action_bet_ratio,
            bet_size_bucket=bet_size_bucket,
            is_raise_over=is_raise_over,
            action_sequence=action_sequence,
            board_features=board_features,
            hero_draw=hero_draw,
            hero_blockers=hero_blockers,
            relation_dist=base_rel,
            player_profile=player_profile,
        )
        pred = float(
            np.asarray(
                booster.predict(_vector_from_feature_names(features, feature_names))
            ).reshape(-1)[0]
        )
    except Exception:
        return base_rel, {"mode": mode, "used": False, "reason": "predict_failed"}

    if str(model.get("prediction_kind") or "absolute") == "residual":
        pred = base_eq + pred
    pred = _clamp_equity_to_bounds(_clamp01(pred), exact_bounds)
    alpha = _clamp01(float(model.get("blend_alpha", 0.0) or 0.0))
    out_eq = _clamp_equity_to_bounds((1.0 - alpha) * base_eq + alpha * pred, exact_bounds)
    out = _clamp_relation_to_bounds(_shift_relation_eq(base_rel, out_eq), exact_bounds)
    return out, {
        "mode": mode,
        "used": True,
        "alpha": alpha,
        "input_eq": round(base_eq, 4),
        "prediction_eq": round(pred, 4),
        "output_eq": round(_relation_eq(out), 4),
    }
