"""Optional ML calibration for hero range equity."""

from __future__ import annotations

import hashlib
import importlib
import json
import math
import os
import subprocess
from pathlib import Path
from typing import Any, Optional

import numpy as np

try:
    Booster = importlib.import_module("lightgbm").Booster
except Exception:
    Booster = None

from pokerfate.strategy.range_v2.bucket_ml_calibration import CAT_ORDER

EPS = 1e-6
_ROOT = Path(__file__).resolve().parents[2] / "data" / "runtime_calibration"
_MODEL_KEY = "all_bb"
_CACHE: dict[tuple[str, str], Optional[dict[str, Any]]] = {}
_BOOSTER_CACHE: dict[tuple[str, str, str], Any] = {}
_STRATEGY_VERSION_CACHE: Optional[str] = None
_PROFILE_DEFAULTS = {
    "PF_TURN_FLOP_RELATIVE_GUARD": "1",
    "PF_RUNTIME_RANGE_CALIBRATION": "1",
    "PF_BUCKET_CALIBRATION": "1",
    "PF_BUCKET_ML": "off",
    "PF_EQUITY_ML": "lgbm",
    "PF_POSTFLOP_PROFIT_EXPAND_V1": "0",
}


def mode_for_big_blind(big_blind: Optional[float]) -> str:
    raw = os.environ.get("PF_EQUITY_ML", "lgbm")
    mode = str(raw or "off").strip().lower()
    if mode in {"0", "false", "no", "none", "off", "disabled", "关"}:
        return "off"
    if mode in {"lgbm", "lightgbm"}:
        return "lgbm"
    return "off"


def experiment_flags() -> dict[str, str]:
    return {
        "PF_EQUITY_ML": os.environ.get("PF_EQUITY_ML", "lgbm"),
    }


def clear_caches() -> None:
    global _STRATEGY_VERSION_CACHE
    _CACHE.clear()
    _BOOSTER_CACHE.clear()
    _STRATEGY_VERSION_CACHE = None


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _git_output(args: list[str]) -> str:
    try:
        out = subprocess.check_output(
            ["git", "-C", str(_repo_root()), *args],
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=2.0,
        )
    except Exception:
        return ""
    return out.strip()


def _current_strategy_version() -> str:
    global _STRATEGY_VERSION_CACHE
    env_version = os.environ.get("PF_STRATEGY_VERSION")
    if env_version:
        return str(env_version)
    if _STRATEGY_VERSION_CACHE is not None:
        return _STRATEGY_VERSION_CACHE

    commit = _git_output(["rev-parse", "--short=12", "HEAD"]) or "unknown"
    if commit == "unknown":
        _STRATEGY_VERSION_CACHE = "__OTHER__"
        return _STRATEGY_VERSION_CACHE
    status = _git_output(["status", "--porcelain"])
    diff = _git_output(["diff", "--no-ext-diff", "--no-color"])
    if status:
        diff_hash = hashlib.sha1(diff.encode("utf-8")).hexdigest()[:10] if diff else "status"
        commit = f"{commit}+dirty.{diff_hash}"
    _STRATEGY_VERSION_CACHE = commit
    return _STRATEGY_VERSION_CACHE


def _current_experiment_profile() -> str:
    return "|".join(
        f"{key}={os.environ.get(key, default)}"
        for key, default in _PROFILE_DEFAULTS.items()
    )


def _model_path(big_blind: Optional[float], mode: str) -> Path:
    return _ROOT / _MODEL_KEY / "runtime_lgbm_equity_model.json"


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
    models_by_street = model.get("models_by_street")
    if isinstance(models_by_street, dict):
        usable = any(
            isinstance(sub, dict)
            and sub.get("runtime_usable", False)
            and float(sub.get("blend_alpha", 0.0) or 0.0) > 0
            and bool(sub.get("model_str"))
            for sub in models_by_street.values()
        )
        if not usable:
            _CACHE[cache_key] = None
            return None
    else:
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


def _clip01(value: Any, scale: float = 1.0) -> float:
    try:
        x = float(value or 0.0)
    except Exception:
        x = 0.0
    if scale > 0:
        x /= scale
    return max(0.0, min(1.0, x))


def _feature_values(
    raw_eq: float,
    bucket_dist: dict[str, float],
    *,
    street: str,
    trigger: str = "",
    action_ctx: str,
    active_count: int,
    board_len: int,
    board_texture: str,
    range_pct: float,
    hero_bucket: str,
    strategy_version: str | None = None,
    experiment_profile: str | None = None,
    position: str = "",
    is_ip: bool = False,
    facing_action: str = "",
    preflop_action_type: str = "",
    action_bet_ratio: float = 0.0,
    bet_size_bucket: str = "",
    is_raise_over: bool = False,
    action_sequence: str = "",
    board_features: dict[str, Any] | None = None,
    hero_made_subtype: str = "",
    hero_hand_rank: str = "",
    hero_draw: dict[str, Any] | None = None,
    hero_blockers: dict[str, Any] | None = None,
    relation_dist: dict[str, float] | None = None,
    player_profile: dict[str, Any] | None = None,
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
        f"trigger={trigger or '?'}": 1.0,
        f"action={_norm_action_ctx(action_ctx or '')}": 1.0,
        f"nopp={_nopp_bin(active_count)}": 1.0,
        f"texture={board_texture or 'pre'}": 1.0,
        f"hero_bucket={hero_bucket or '?'}": 1.0,
        f"top_bucket={top_bucket}": 1.0,
        f"strategy_version={strategy_version or _current_strategy_version()}": 1.0,
        f"experiment_profile={experiment_profile or _current_experiment_profile()}": 1.0,
        f"position={position or '?'}": 1.0,
        f"is_ip={'ip' if is_ip else 'oop'}": 1.0,
        f"facing_action={facing_action or '?'}": 1.0,
        f"preflop_action_type={preflop_action_type or '?'}": 1.0,
        f"bet_size_bucket={bet_size_bucket or 'none'}": 1.0,
        f"action_sequence={action_sequence or '?'}": 1.0,
        "action_bet_ratio": _clip01(action_bet_ratio, 4.0),
        "is_raise_over": 1.0 if is_raise_over else 0.0,
        f"hero_made_subtype={hero_made_subtype or '?'}": 1.0,
        f"hero_hand_rank={hero_hand_rank or '?'}": 1.0,
        f"board_texture={board_texture or 'pre'}": 1.0,
    }
    board_raw = dict(board_features or {})
    for key in (
        "paired", "monotone", "flush_possible", "flush_draw",
        "straight_possible", "straight_draw_heavy",
    ):
        out[f"board_{key}"] = 1.0 if board_raw.get(key) else 0.0
    out["board_wetness"] = _clip01(board_raw.get("wetness"), 1.0)
    out["board_connectedness"] = _clip01(board_raw.get("connectedness"), 1.0)
    out["board_high_card_rank"] = _clip01(board_raw.get("high_card_rank"), 14.0)

    draw_raw = dict(hero_draw or {})
    for key in ("flush_draw", "oesd", "gutshot", "backdoor_flush", "overcards"):
        out[f"hero_draw_{key}"] = 1.0 if draw_raw.get(key) else 0.0

    blocker_raw = dict(hero_blockers or {})
    for key in ("nut_flush_blocker", "set_blocker", "straight_blocker"):
        out[f"hero_blocker_{key}"] = 1.0 if blocker_raw.get(key) else 0.0

    profile_raw = dict(player_profile or {})
    profile_scales = {
        "hands_seen": 5000.0,
        "vpip": 1.0,
        "pfr": 1.0,
        "af": 5.0,
        "three_bet_pct": 1.0,
        "fold_to_3bet": 1.0,
        "fold_to_cbet": 1.0,
        "wtsd": 1.0,
        "wmsd": 1.0,
        "river_bet_freq": 1.0,
        "river_fold_rate": 1.0,
        "bluff_win_rate": 1.0,
        "pwi": 100.0,
    }
    for key, scale in profile_scales.items():
        out[f"profile_{key}"] = _clip01(profile_raw.get(key), scale)
    rel_raw = dict(relation_dist or {})
    try:
        rel_win = max(0.0, float(rel_raw.get("win", 0.0) or 0.0))
        rel_tie = max(0.0, float(rel_raw.get("tie", 0.0) or 0.0))
        rel_loss = max(0.0, float(rel_raw.get("loss", 0.0) or 0.0))
    except Exception:
        rel_win = rel_tie = rel_loss = 0.0
    rel_total = rel_win + rel_tie + rel_loss
    if rel_total > EPS:
        rel_win /= rel_total
        rel_tie /= rel_total
        rel_loss /= rel_total
    out["rel_win"] = rel_win
    out["rel_tie"] = rel_tie
    out["rel_loss"] = rel_loss
    out["rel_loss_minus_win"] = rel_loss - rel_win
    out["rel_non_tie"] = rel_win + rel_loss
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
    trigger: str = "",
    action_ctx: str,
    active_count: int,
    board_len: int,
    board_texture: str,
    range_pct: float,
    hero_bucket: str,
    strategy_version: str | None = None,
    experiment_profile: str | None = None,
    hero_made_subtype: str = "",
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
    relation_dist: dict[str, float] | None = None,
    player_profile: dict[str, Any] | None = None,
) -> tuple[float, dict[str, Any]]:
    base = max(0.0, min(1.0, float(raw_eq)))
    mode = mode_for_big_blind(big_blind)
    if mode == "off":
        return base, {"mode": mode, "used": False, "reason": "mode_off"}
    model = _load_model(big_blind, mode)
    if not model:
        return base, {"mode": mode, "used": False, "reason": "model_missing"}
    if Booster is None:
        return base, {"mode": mode, "used": False, "reason": "lightgbm_missing"}
    runtime_model = model
    models_by_street = model.get("models_by_street")
    if isinstance(models_by_street, dict):
        runtime_model = models_by_street.get(str(street or ""))
        if not isinstance(runtime_model, dict):
            return base, {"mode": mode, "used": False, "reason": "street_model_missing"}
        if (
            not runtime_model.get("runtime_usable", False)
            or float(runtime_model.get("blend_alpha", 0.0) or 0.0) <= 0
        ):
            return base, {"mode": mode, "used": False, "reason": "street_model_unusable"}

    feature_names = list(runtime_model.get("feature_names") or [])
    model_str = str(runtime_model.get("model_str") or "")
    if not feature_names or not model_str:
        return base, {"mode": mode, "used": False, "reason": "model_invalid"}
    try:
        cache_key = (_MODEL_KEY, mode, str(street or "global"))
        booster = _BOOSTER_CACHE.get(cache_key)
        if booster is None:
            booster = Booster(model_str=model_str)
            _BOOSTER_CACHE[cache_key] = booster
        features = _feature_values(
            base,
            dict(bucket_dist or {}),
            street=street,
            trigger=trigger,
            action_ctx=action_ctx,
            active_count=active_count,
            board_len=board_len,
            board_texture=board_texture,
            range_pct=range_pct,
            hero_bucket=hero_bucket,
            strategy_version=strategy_version,
            experiment_profile=experiment_profile,
            position=position,
            is_ip=is_ip,
            facing_action=facing_action,
            preflop_action_type=preflop_action_type,
            action_bet_ratio=action_bet_ratio,
            bet_size_bucket=bet_size_bucket,
            is_raise_over=is_raise_over,
            action_sequence=action_sequence,
            board_features=board_features,
            hero_made_subtype=hero_made_subtype,
            hero_hand_rank=hero_hand_rank,
            hero_draw=hero_draw,
            hero_blockers=hero_blockers,
            relation_dist=relation_dist,
            player_profile=player_profile,
        )
        pred = float(np.asarray(booster.predict(_vector_from_feature_names(features, feature_names))).reshape(-1)[0])
    except Exception:
        return base, {"mode": mode, "used": False, "reason": "predict_failed"}
    if str(runtime_model.get("prediction_kind") or "absolute") == "residual":
        pred = base + pred
    pred = max(0.0, min(1.0, pred))
    alpha = max(0.0, min(1.0, float(runtime_model.get("blend_alpha", 0.0) or 0.0)))
    out = max(0.0, min(1.0, (1.0 - alpha) * base + alpha * pred))
    return out, {
        "mode": mode,
        "used": True,
        "alpha": alpha,
        "input": base,
        "prediction": pred,
        "output": out,
    }
