"""Empirical population priors for Range V2.

This module is deliberately data-driven and optional.  If the generated model
file is absent or incomplete, every lookup falls back to the old hard-coded
logic in the caller.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Optional, Tuple


CAT_ORDER = ("nuts", "strong", "medium", "draw", "weak_draw", "air")
SUPPORTED_BB_KEYS = ("bb_1k", "bb_10k", "bb_50k")
DEFAULT_BB_KEY = "bb_10k"
MODEL_DIR = Path(__file__).resolve().parents[2] / "data" / "local_models"
_CURRENT_BB_KEY = DEFAULT_BB_KEY


def bb_key(big_blind: Any = None) -> str:
    """Map table blind to the three supported local model buckets."""
    if isinstance(big_blind, str):
        raw = big_blind.strip()
        if raw in SUPPORTED_BB_KEYS:
            return raw
        if raw in {"1k", "10k", "50k"}:
            return f"bb_{raw}"
    try:
        bb = float(big_blind or 0.0)
    except Exception:
        return _CURRENT_BB_KEY
    if bb <= 0:
        return _CURRENT_BB_KEY
    candidates = {1000.0: "bb_1k", 10000.0: "bb_10k", 50000.0: "bb_50k"}
    return candidates[min(candidates, key=lambda value: abs(value - bb))]


def set_current_big_blind(big_blind: Any) -> None:
    """Set process-wide default used by call sites that do not carry bb."""
    global _CURRENT_BB_KEY
    _CURRENT_BB_KEY = bb_key(big_blind)


def empirical_model_path(big_blind: Any = None) -> Path:
    key = bb_key(big_blind)
    return MODEL_DIR / f"range_v2_empirical_model_{key}.json"


@lru_cache(maxsize=8)
def _load_empirical_model_for_key(key: str) -> Dict[str, Any]:
    path = empirical_model_path(key)
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if isinstance(data, dict):
        return data
    return {}


def load_empirical_model(big_blind: Any = None) -> Dict[str, Any]:
    return _load_empirical_model_for_key(bb_key(big_blind))


def population_rate(name: str, fallback: float, big_blind: Any = None) -> float:
    """Return a generated population mean for a named rate."""
    try:
        rec = load_empirical_model(big_blind).get("population_rates", {}).get(name, {})
        value = float(rec.get("mean", fallback))
    except Exception:
        return float(fallback)
    if not 0.0 <= value <= 1.0:
        return float(fallback)
    return value


def population_strength(name: str, fallback: float, big_blind: Any = None) -> float:
    try:
        rec = load_empirical_model(big_blind).get("population_rates", {}).get(name, {})
        value = float(rec.get("prior_strength", fallback))
    except Exception:
        return float(fallback)
    return max(1.0, value)


def profile_cluster(profile: Any) -> str:
    """Small, stable behavioural buckets for empirical backoff."""
    hands = int(getattr(profile, "hands_seen", 0) or 0)
    vpip = float(getattr(profile, "vpip", 0.0) or 0.0)
    pfr = float(getattr(profile, "pfr", 0.0) or 0.0)
    af = float(getattr(profile, "af", 0.0) or 0.0)
    wtsd = float(getattr(profile, "wtsd", 0.0) or 0.0)
    gap = max(0.0, vpip - pfr)

    if hands < 20:
        return "unknown"
    if vpip < 0.18 and pfr < 0.14:
        return "nit"
    if vpip >= 0.50 and (af < 1.35 or wtsd >= 0.32):
        return "whale"
    if vpip > 0.35 and pfr < 0.17 and gap >= 0.10:
        return "fish"
    if vpip > 0.33 and (af > 2.5 or pfr >= 0.25):
        return "lag"
    if 0.22 <= vpip <= 0.32 and 0.16 <= pfr <= 0.26 and gap <= 0.12:
        return "reg"
    return "unknown"


def _bet_size_bucket(ratio: float) -> str:
    try:
        x = float(ratio or 0.0)
    except Exception:
        x = 0.0
    if x <= 0.0:
        return "none"
    if x <= 0.25:
        return "small"
    if x <= 0.40:
        return "third"
    if x <= 0.55:
        return "half"
    if x <= 0.80:
        return "two_third"
    if x <= 1.10:
        return "pot"
    if x <= 1.75:
        return "overpot"
    return "huge"


def action_label(action: str, is_raise_over: bool = False) -> str:
    act = str(action or "").lower()
    if act == "raise":
        return "raise_over" if is_raise_over else "bet"
    return act


def empirical_action_likelihood(
    action: str,
    street: str,
    ctx: Any,
    profile: Any,
) -> Optional[Tuple[Dict[str, float], float, str, int]]:
    """Return (cat -> P(action|cat), blend, key, n) for this context."""
    if not str(getattr(profile, "name", "") or "").strip():
        return None
    model = load_empirical_model(getattr(ctx, "big_blind", None))
    table = model.get("action_likelihoods") or {}
    if not table:
        return None

    street_s = str(street or "").lower()
    is_rr = bool(getattr(ctx, "is_raise_over", False))
    label = action_label(action, is_rr)
    size = _bet_size_bucket(float(getattr(ctx, "bet_ratio", 0.0) or 0.0))
    cluster = profile_cluster(profile)
    rr = "1" if is_rr else "0"

    keys = (
        f"{street_s}|{label}|{size}|{rr}|{cluster}",
        f"{street_s}|{label}|{size}|{rr}|*",
        f"{street_s}|{label}|*|{rr}|{cluster}",
        f"{street_s}|{label}|*|{rr}|*",
        f"{street_s}|{label}|{size}|*|{cluster}",
        f"{street_s}|{label}|{size}|*|*",
        f"{street_s}|{label}|*|*|{cluster}",
        f"{street_s}|{label}|*|*|*",
    )
    for key in keys:
        rec = table.get(key)
        if not rec:
            continue
        dist = rec.get("cat_probs") or {}
        if not dist:
            continue
        n = int(rec.get("n", 0) or 0)
        blend = float(rec.get("blend", 0.0) or 0.0)
        if n <= 0 or blend <= 0.0:
            continue
        clean = {
            cat: max(0.01, min(0.99, float(dist.get(cat, 0.0) or 0.0)))
            for cat in CAT_ORDER
            if cat in dist
        }
        if clean:
            return clean, max(0.0, min(0.75, blend)), key, n
    return None


def empirical_preflop_bucket_prior(
    position: str,
    profile: Any,
    big_blind: Any = None,
) -> Optional[Tuple[Dict[str, float], float, str, int]]:
    """Return a gentle bucket-level prior for cold/small-sample players."""
    if not str(getattr(profile, "name", "") or "").strip():
        return None
    hands = int(getattr(profile, "hands_seen", 0) or 0)
    if hands >= 80:
        return None

    model = load_empirical_model(big_blind)
    table = model.get("preflop_bucket_priors") or {}
    if not table:
        return None

    pos = str(position or "CO")
    cluster = profile_cluster(profile)
    keys = (
        f"{pos}|{cluster}",
        f"{pos}|*",
        f"*|{cluster}",
        "*|*",
    )
    for key in keys:
        rec = table.get(key)
        if not rec:
            continue
        dist = rec.get("dist") or {}
        n = int(rec.get("n", 0) or 0)
        blend = float(rec.get("blend", 0.0) or 0.0)
        if n <= 0 or blend <= 0.0:
            continue
        # Existing player samples should dominate the empirical pool quickly.
        sample_discount = max(0.15, 1.0 - min(hands, 80) / 80.0)
        clean = {
            cat: max(0.0, min(1.0, float(dist.get(cat, 0.0) or 0.0)))
            for cat in CAT_ORDER
            if cat in dist
        }
        total = sum(clean.values())
        if total <= 1e-12:
            continue
        clean = {cat: value / total for cat, value in clean.items()}
        return clean, max(0.0, min(0.35, blend * sample_discount)), key, n
    return None
