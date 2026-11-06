"""Empirical population priors for Range V2.

This module is deliberately data-driven and optional.  If the generated model
file is absent or incomplete, every lookup falls back to the old hard-coded
logic in the caller.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Optional, Tuple


CAT_ORDER = ("nuts", "strong", "medium", "draw", "weak_draw", "air")
SUPPORTED_BB_KEYS = ("bb_1k", "bb_10k", "bb_50k")
DEFAULT_BB_KEY = "bb_10k"
MODEL_KEY = "all_bb"
MODEL_DIR = Path(__file__).resolve().parents[2] / "data" / "local_models"
_CURRENT_BB_KEY = DEFAULT_BB_KEY
FEATURES = (
    "vpip",
    "pfr",
    "gap",
    "af",
    "wtsd",
    "wmsd",
    "flop_afq",
    "turn_afq",
    "river_afq",
    "river_bet_freq",
    "bluff_win_rate",
    "fold_to_cbet",
    "river_fold_rate",
    "three_bet",
    "fold_to_3bet",
)
FEATURE_WEIGHTS = {
    "vpip": 1.2,
    "pfr": 1.0,
    "gap": 1.4,
    "af": 1.3,
    "wtsd": 1.5,
    "wmsd": 0.7,
    "flop_afq": 1.0,
    "turn_afq": 1.0,
    "river_afq": 1.0,
    "river_bet_freq": 1.0,
    "bluff_win_rate": 1.4,
    "fold_to_cbet": 0.8,
    "river_fold_rate": 0.9,
    "three_bet": 0.6,
    "fold_to_3bet": 0.5,
}
FALLBACK_POOL = {
    "vpip": 0.55,
    "pfr": 0.14,
    "gap": 0.41,
    "af": 0.85,
    "wtsd": 0.37,
    "wmsd": 0.48,
    "flop_afq": 0.28,
    "turn_afq": 0.30,
    "river_afq": 0.33,
    "river_bet_freq": 0.38,
    "bluff_win_rate": 0.11,
    "fold_to_cbet": 0.42,
    "river_fold_rate": 0.53,
    "three_bet": 0.066,
    "fold_to_3bet": 0.19,
}
_KNN_MAX_NEIGHBORS = 50
_KNN_DISTANCE_SCALE = 0.75
_KNN_MIN_ACTION_N = 4.0
_KNN_MIN_ACTION_CTX_N = 8.0
_KNN_MIN_PREFLOP_N = 6.0


@dataclass
class _FeatureVector:
    uid: str
    values: Dict[str, float]
    reliability: Dict[str, float]
    z: Dict[str, float]
    hands: int


@dataclass
class _NumericIndex:
    pool: Dict[str, float]
    scales: Dict[str, float]
    rows: list[_FeatureVector]
    action_counts: Dict[str, Dict[str, Dict[str, Dict[str, float]]]]
    preflop_counts: Dict[str, Dict[str, Dict[str, float]]]
    action_prior_weight: float
    player_count: int


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
    return MODEL_DIR / f"range_v2_empirical_model_{MODEL_KEY}.json"


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
    return _load_empirical_model_for_key(MODEL_KEY)


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


def build_numeric_profile_payload(
    opponents: Dict[str, Dict[str, Any]],
    player_action_counts: Dict[str, Any],
    player_preflop_counts: Dict[str, Any],
    *,
    action_prior_weight: float,
) -> Dict[str, Any]:
    """Build the KNN payload persisted by the empirical-model training script."""
    stats_list = [stats for stats in opponents.values() if isinstance(stats, dict)]
    pool = _pool_from_stats(stats_list)
    raw_rows = [
        _stats_vector(str(uid), stats, pool)
        for uid, stats in opponents.items()
        if isinstance(stats, dict)
    ]
    rows = [row for row in raw_rows if row.hands > 0]
    scales = _feature_scales(rows, pool)
    players = {
        row.uid: {
            "hands": int(row.hands),
            "values": _round_feature_dict(row.values),
            "reliability": _round_feature_dict(row.reliability),
        }
        for row in rows
    }
    known_uids = set(players)
    action_counts = _json_counts_nested(
        {
            str(uid): counts
            for uid, counts in player_action_counts.items()
            if str(uid) in known_uids
        }
    )
    preflop_counts = _json_counts_nested(
        {
            str(uid): counts
            for uid, counts in player_preflop_counts.items()
            if str(uid) in known_uids
        }
    )
    return {
        "schema": "range_v2_numeric_profile_priors_v1",
        "features": list(FEATURES),
        "pool": _round_feature_dict(pool),
        "scales": _round_feature_dict(scales),
        "players": players,
        "player_action_counts": action_counts,
        "player_preflop_counts": preflop_counts,
        "action_prior_weight": float(action_prior_weight),
        "counts": {
            "players": len(players),
            "action_players": len(action_counts),
            "preflop_players": len(preflop_counts),
        },
    }


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


def _global_action_likelihood_from_table(
    table: Dict[str, Any],
    street_s: str,
    label: str,
    size: str,
    rr: str,
) -> Optional[Tuple[Dict[str, float], float, str, int]]:
    keys = (
        f"{street_s}|{label}|{size}|{rr}|*",
        f"{street_s}|{label}|*|{rr}|*",
        f"{street_s}|{label}|{size}|*|*",
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
            cat: _clamp(float(dist.get(cat, 0.0) or 0.0), 0.01, 0.99)
            for cat in CAT_ORDER
            if cat in dist
        }
        if clean:
            return clean, _clamp(blend, 0.0, 0.75), key, n
    return None


def _global_preflop_prior_from_table(
    table: Dict[str, Any],
    pos: str,
) -> Optional[Tuple[Dict[str, float], float, str, int]]:
    for key in (f"{pos}|*", "*|*"):
        rec = table.get(key)
        if not rec:
            continue
        dist = rec.get("dist") or {}
        n = int(rec.get("n", 0) or 0)
        blend = float(rec.get("blend", 0.0) or 0.0)
        if n <= 0 or blend <= 0.0:
            continue
        clean = {
            cat: _clamp(float(dist.get(cat, 0.0) or 0.0), 0.0, 1.0)
            for cat in CAT_ORDER
            if cat in dist
        }
        total = sum(clean.values())
        if total <= 1e-12:
            continue
        return {cat: value / total for cat, value in clean.items()}, _clamp(blend, 0.0, 0.35), key, n
    return None


def empirical_action_likelihood(
    action: str,
    street: str,
    ctx: Any,
    profile: Any,
) -> Optional[Tuple[Dict[str, float], float, str, int]]:
    """Return (cat -> P(action|cat), blend, key, n) for this context."""
    if profile is None or not str(getattr(profile, "name", "") or "").strip():
        return None
    numeric = _numeric_action_likelihood(action, street, ctx, profile)
    if numeric is not None:
        return numeric

    model = load_empirical_model(ctx.big_blind)
    table = model.get("action_likelihoods") or {}
    if not table:
        return None

    street_s = str(street or "").lower()
    is_rr = bool(ctx.is_raise_over)
    label = action_label(action, is_rr)
    size = _bet_size_bucket(float(ctx.bet_ratio or 0.0))
    rr = "1" if is_rr else "0"
    return _global_action_likelihood_from_table(table, street_s, label, size, rr)


def empirical_preflop_bucket_prior(
    position: str,
    profile: Any,
    big_blind: Any = None,
) -> Optional[Tuple[Dict[str, float], float, str, int]]:
    """Return a gentle bucket-level prior for cold/small-sample players."""
    if profile is None or not str(getattr(profile, "name", "") or "").strip():
        return None
    hands = int(getattr(profile, "hands_seen", 0) or 0)
    if hands >= 80:
        return None

    numeric = _numeric_preflop_prior(position, profile, big_blind, hands)
    if numeric is not None:
        return numeric

    model = load_empirical_model(big_blind)
    table = model.get("preflop_bucket_priors") or {}
    if not table:
        return None

    pos = str(position or "CO")
    global_prior = _global_preflop_prior_from_table(table, pos)
    if global_prior is None:
        return None
    clean, blend, key, n = global_prior
    sample_discount = max(0.15, 1.0 - min(hands, 80) / 80.0)
    return clean, _clamp(blend * sample_discount, 0.0, 0.35), key, n


def _numeric_action_likelihood(
    action: str,
    street: str,
    ctx: Any,
    profile: Any,
) -> Optional[Tuple[Dict[str, float], float, str, int]]:
    index = _numeric_index_for_key(MODEL_KEY)
    if not index.rows or not index.action_counts:
        return None
    scored, query_conf = _knn_scores(profile, index)
    if not scored:
        return None

    street_s = str(street or "").lower()
    is_rr = bool(getattr(ctx, "is_raise_over", False))
    label = action_label(action, is_rr)
    size = _bet_size_bucket(float(getattr(ctx, "bet_ratio", 0.0) or 0.0))
    rr = "1" if is_rr else "0"
    raw_model = load_empirical_model(getattr(ctx, "big_blind", None))
    global_rec = _global_action_likelihood_from_table(
        raw_model.get("action_likelihoods") or {},
        street_s,
        label,
        size,
        rr,
    )
    for ctx_key in _action_context_keys(street_s, size, rr):
        cat_action = {cat: 0.0 for cat in CAT_ORDER}
        cat_total = {cat: 0.0 for cat in CAT_ORDER}
        total_ctx = 0.0
        contributors = 0
        for dist, row in scored:
            counts = index.action_counts.get(row.uid, {}).get(ctx_key)
            if not counts:
                continue
            sim = math.exp(-dist / _KNN_DISTANCE_SCALE)
            contributors += 1
            for cat in CAT_ORDER:
                actions = counts.get(cat) or {}
                denom = sum(float(v or 0.0) for v in actions.values())
                if denom <= 0.0:
                    continue
                cat_total[cat] += sim * denom
                cat_action[cat] += sim * float(actions.get(label, 0.0) or 0.0)
                total_ctx += sim * denom
            if contributors >= _KNN_MAX_NEIGHBORS:
                break

        n_action = sum(cat_action.values())
        if n_action < _KNN_MIN_ACTION_N or total_ctx < _KNN_MIN_ACTION_CTX_N:
            continue
        clean = {
            cat: _clamp(cat_action[cat] / cat_total[cat], 0.01, 0.99)
            for cat in CAT_ORDER
            if cat_total[cat] > 1e-12
        }
        if not clean:
            continue
        size_key, rr_key = ctx_key.split("|")[1:]
        specificity = sum(1 for part in (size_key, rr_key) if part != "*")
        cap = min(0.07, 0.025 + specificity * 0.015)
        conf_scale = _clamp(0.25 + query_conf, 0.25, 1.0)
        blend = min(cap, n_action / (n_action + index.action_prior_weight)) * conf_scale
        base_key = ""
        if global_rec is not None:
            global_dist, global_blend, global_key, _global_n = global_rec
            neighbor_weight = _clamp(0.20 + 0.60 * query_conf, 0.20, 0.80)
            neighbor_weight *= _clamp(n_action / (n_action + 40.0), 0.15, 1.0)
            clean = {
                cat: (
                    neighbor_weight * clean.get(cat, global_dist.get(cat, 0.01))
                    + (1.0 - neighbor_weight) * global_dist.get(cat, clean.get(cat, 0.01))
                )
                for cat in CAT_ORDER
                if cat in clean or cat in global_dist
            }
            blend = max(blend, global_blend * 0.75)
            base_key = f":base={global_key}"
        if blend > 1e-4:
            return clean, blend, f"knn:{ctx_key}:{label}:contributors={contributors}{base_key}", int(round(n_action))
    return None


def _numeric_preflop_prior(
    position: str,
    profile: Any,
    big_blind: Any,
    hands: int,
) -> Optional[Tuple[Dict[str, float], float, str, int]]:
    index = _numeric_index_for_key(MODEL_KEY)
    if not index.rows or not index.preflop_counts:
        return None
    scored, query_conf = _knn_scores(profile, index)
    if not scored:
        return None

    pos = str(position or "CO")
    raw_model = load_empirical_model(big_blind)
    global_rec = _global_preflop_prior_from_table(
        raw_model.get("preflop_bucket_priors") or {},
        pos,
    )
    for pos_key in (pos, "*"):
        counts = {cat: 0.0 for cat in CAT_ORDER}
        contributors = 0
        for dist, row in scored:
            rec = index.preflop_counts.get(row.uid, {}).get(pos_key)
            if not rec:
                continue
            sim = math.exp(-dist / _KNN_DISTANCE_SCALE)
            contributors += 1
            for cat in CAT_ORDER:
                counts[cat] += sim * float(rec.get(cat, 0.0) or 0.0)
            if contributors >= _KNN_MAX_NEIGHBORS:
                break
        n = sum(counts.values())
        if n < _KNN_MIN_PREFLOP_N:
            continue
        dist = {cat: _clamp(counts[cat] / n, 0.0, 1.0) for cat in CAT_ORDER}
        total = sum(dist.values())
        if total <= 1e-12:
            continue
        dist = {cat: value / total for cat, value in dist.items()}
        sample_discount = max(0.15, 1.0 - min(hands, 80) / 80.0)
        conf_scale = _clamp(0.25 + query_conf, 0.25, 1.0)
        blend = min(0.12, n / (n + 600.0)) * conf_scale * sample_discount
        base_key = ""
        if global_rec is not None:
            global_dist, global_blend, global_key, _global_n = global_rec
            neighbor_weight = _clamp(0.20 + 0.60 * query_conf, 0.20, 0.80)
            neighbor_weight *= _clamp(n / (n + 30.0), 0.15, 1.0)
            dist = {
                cat: (
                    neighbor_weight * dist.get(cat, global_dist.get(cat, 0.0))
                    + (1.0 - neighbor_weight) * global_dist.get(cat, dist.get(cat, 0.0))
                )
                for cat in CAT_ORDER
                if cat in dist or cat in global_dist
            }
            total = sum(dist.values())
            if total > 1e-12:
                dist = {cat: value / total for cat, value in dist.items()}
            blend = max(blend, global_blend * sample_discount * 0.75)
            base_key = f":base={global_key}"
        if blend > 1e-4:
            return dist, blend, f"knn:{pos_key}:contributors={contributors}{base_key}", int(round(n))
    return None


def _action_context_keys(street: str, size: str, rr: str) -> tuple[str, ...]:
    return (
        f"{street}|{size}|{rr}",
        f"{street}|*|{rr}",
        f"{street}|{size}|*",
        f"{street}|*|*",
    )


@lru_cache(maxsize=8)
def _numeric_index_for_key(key: str) -> _NumericIndex:
    raw = _load_empirical_model_for_key(key)
    section = raw.get("numeric_profile_priors") or {}
    if not isinstance(section, dict):
        return _empty_numeric_index()
    pool = _feature_dict(section.get("pool"), FALLBACK_POOL)
    scales = _feature_dict(section.get("scales"), _default_scales())
    players = section.get("players") or {}
    rows: list[_FeatureVector] = []
    if isinstance(players, dict):
        for uid, rec in players.items():
            if not isinstance(rec, dict):
                continue
            values = _feature_dict(rec.get("values"), pool)
            reliability = _feature_dict(rec.get("reliability"), {name: 0.0 for name in FEATURES})
            hands = int(float(rec.get("hands", 0) or 0))
            rows.append(_FeatureVector(
                uid=str(uid),
                values=values,
                reliability=reliability,
                z=_z_values(values, pool, scales),
                hands=hands,
            ))
    try:
        action_prior_weight = float(section.get("action_prior_weight", 3000.0) or 3000.0)
    except Exception:
        action_prior_weight = 3000.0
    action_counts = section.get("player_action_counts") or {}
    preflop_counts = section.get("player_preflop_counts") or {}
    return _NumericIndex(
        pool=pool,
        scales=scales,
        rows=rows,
        action_counts=action_counts if isinstance(action_counts, dict) else {},
        preflop_counts=preflop_counts if isinstance(preflop_counts, dict) else {},
        action_prior_weight=max(1.0, action_prior_weight),
        player_count=len(rows),
    )


def _empty_numeric_index() -> _NumericIndex:
    return _NumericIndex(
        pool=dict(FALLBACK_POOL),
        scales=_default_scales(),
        rows=[],
        action_counts={},
        preflop_counts={},
        action_prior_weight=3000.0,
        player_count=0,
    )


def _knn_scores(profile: Any, index: _NumericIndex) -> tuple[list[tuple[float, _FeatureVector]], float]:
    current = _profile_vector(profile, index)
    query_conf = _query_confidence(current)
    if query_conf <= 0.03:
        return [], query_conf
    scored: list[tuple[float, _FeatureVector]] = []
    for row in index.rows:
        dist = 0.0
        weight_sum = 0.0
        for name in FEATURES:
            cur_rel = current.reliability.get(name, 0.0)
            row_rel = row.reliability.get(name, 0.0)
            if cur_rel <= 0.04 or row_rel <= 0.04:
                continue
            weight = FEATURE_WEIGHTS[name] * cur_rel * row_rel
            delta = current.z.get(name, 0.0) - row.z.get(name, 0.0)
            dist += weight * delta * delta
            weight_sum += weight
        if weight_sum <= 0.12:
            continue
        scored.append((dist / weight_sum, row))
    scored.sort(key=lambda item: item[0])
    return scored, query_conf


def _query_confidence(current: _FeatureVector) -> float:
    numerator = 0.0
    denominator = 0.0
    for name in FEATURES:
        weight = FEATURE_WEIGHTS[name]
        numerator += weight * current.reliability.get(name, 0.0)
        denominator += weight
    if denominator <= 1e-12:
        return 0.0
    return _clamp(numerator / denominator, 0.0, 1.0)


def _pool_from_stats(stats_list: list[Dict[str, Any]]) -> Dict[str, float]:
    def rate(num: str, den: str, fallback: float) -> float:
        success = sum(float(stats.get(num, 0) or 0) for stats in stats_list)
        trials = sum(float(stats.get(den, 0) or 0) for stats in stats_list)
        return success / trials if trials > 0 else fallback

    pool = dict(FALLBACK_POOL)
    pool["vpip"] = rate("vpip_count", "hands_seen", pool["vpip"])
    pool["pfr"] = rate("pfr_count", "hands_seen", pool["pfr"])
    pool["gap"] = _clamp(pool["vpip"] - pool["pfr"], 0.0, 1.0)
    pool["three_bet"] = rate("three_bet_count", "three_bet_opportunities", pool["three_bet"])
    pool["fold_to_3bet"] = rate("fold_to_3bet_count", "fold_to_3bet_opps", pool["fold_to_3bet"])
    pool["fold_to_cbet"] = rate("fold_to_cbet_count", "fold_to_cbet_opps", pool["fold_to_cbet"])
    pool["wtsd"] = rate("showdown_count", "flop_seen_count", pool["wtsd"])
    pool["wmsd"] = rate("showdown_win_count", "showdown_count", pool["wmsd"])
    pool["river_fold_rate"] = rate(
        "river_facing_bet_fold_count",
        "river_facing_bet_opps",
        pool["river_fold_rate"],
    )
    pool["bluff_win_rate"] = rate("bluff_win_count", "bet_win_count", pool["bluff_win_rate"])
    pool["flop_afq"] = _derived_rate(stats_list, "flop_bet_count", ("flop_bet_count", "flop_passive_count"), pool["flop_afq"])
    pool["turn_afq"] = _derived_rate(stats_list, "turn_bet_count", ("turn_bet_count", "turn_passive_count"), pool["turn_afq"])
    pool["river_afq"] = _derived_rate(
        stats_list,
        "river_bet_count",
        ("river_bet_count", "river_call_count", "river_check_count"),
        pool["river_afq"],
    )
    pool["river_bet_freq"] = _derived_rate(
        stats_list,
        "river_bet_count",
        ("river_bet_count", "river_check_count"),
        pool["river_bet_freq"],
    )
    passive = sum(
        float(stats.get("call_count", 0) or 0) + float(stats.get("check_count", 0) or 0)
        for stats in stats_list
    )
    aggressive = sum(
        float(stats.get("bet_count", 0) or 0) + float(stats.get("raise_count", 0) or 0)
        for stats in stats_list
    )
    if passive > 0:
        pool["af"] = aggressive / passive
    return pool


def _derived_rate(
    stats_list: list[Dict[str, Any]],
    num_field: str,
    den_fields: tuple[str, ...],
    fallback: float,
) -> float:
    success = sum(float(stats.get(num_field, 0) or 0) for stats in stats_list)
    trials = sum(
        sum(float(stats.get(field, 0) or 0) for field in den_fields)
        for stats in stats_list
    )
    return success / trials if trials > 0 else fallback


def _stats_vector(uid: str, stats: Dict[str, Any], pool: Dict[str, float]) -> _FeatureVector:
    hands = int(float(stats.get("hands_seen", 0) or 0))
    call_count = float(stats.get("call_count", 0) or 0)
    check_count = float(stats.get("check_count", 0) or 0)
    bet_count = float(stats.get("bet_count", 0) or 0)
    raise_count = float(stats.get("raise_count", 0) or 0)
    passive = call_count + check_count
    actions = passive + bet_count + raise_count
    flop_actions = float(stats.get("flop_bet_count", 0) or 0) + float(stats.get("flop_passive_count", 0) or 0)
    turn_actions = float(stats.get("turn_bet_count", 0) or 0) + float(stats.get("turn_passive_count", 0) or 0)
    river_actions = (
        float(stats.get("river_bet_count", 0) or 0)
        + float(stats.get("river_call_count", 0) or 0)
        + float(stats.get("river_check_count", 0) or 0)
    )
    river_bf = float(stats.get("river_bet_count", 0) or 0) + float(stats.get("river_check_count", 0) or 0)
    server_af = float(stats.get("server_af_prior", 0) or 0)
    server_wtsd = float(stats.get("server_wtsd_prior", 0) or 0)
    vpip = _safe_rate(stats.get("vpip_count", 0), hands, pool["vpip"])
    pfr = _safe_rate(stats.get("pfr_count", 0), hands, pool["pfr"])
    values = {
        "vpip": vpip,
        "pfr": pfr,
        "gap": _clamp(vpip - pfr, 0.0, 1.0),
        "af": server_af if server_af > 0 else _safe_rate(bet_count + raise_count, passive, pool["af"]),
        "wtsd": server_wtsd if server_wtsd > 0 else _safe_rate(stats.get("showdown_count", 0), stats.get("flop_seen_count", 0), pool["wtsd"]),
        "wmsd": _safe_rate(stats.get("showdown_win_count", 0), stats.get("showdown_count", 0), pool["wmsd"]),
        "flop_afq": _safe_rate(stats.get("flop_bet_count", 0), flop_actions, pool["flop_afq"]),
        "turn_afq": _safe_rate(stats.get("turn_bet_count", 0), turn_actions, pool["turn_afq"]),
        "river_afq": _safe_rate(stats.get("river_bet_count", 0), river_actions, pool["river_afq"]),
        "river_bet_freq": _safe_rate(stats.get("river_bet_count", 0), river_bf, pool["river_bet_freq"]),
        "bluff_win_rate": _safe_rate(stats.get("bluff_win_count", 0), stats.get("bet_win_count", 0), pool["bluff_win_rate"]),
        "fold_to_cbet": _safe_rate(stats.get("fold_to_cbet_count", 0), stats.get("fold_to_cbet_opps", 0), pool["fold_to_cbet"]),
        "river_fold_rate": _safe_rate(stats.get("river_facing_bet_fold_count", 0), stats.get("river_facing_bet_opps", 0), pool["river_fold_rate"]),
        "three_bet": _safe_rate(stats.get("three_bet_count", 0), stats.get("three_bet_opportunities", 0), pool["three_bet"]),
        "fold_to_3bet": _safe_rate(stats.get("fold_to_3bet_count", 0), stats.get("fold_to_3bet_opps", 0), pool["fold_to_3bet"]),
    }
    reliability = {
        "vpip": _rel(hands, 80.0),
        "pfr": _rel(hands, 80.0),
        "gap": _rel(hands, 80.0),
        "af": max(_rel(actions, 60.0), 0.75 if server_af > 0 else 0.0),
        "wtsd": max(_rel(float(stats.get("flop_seen_count", 0) or 0), 80.0), 0.75 if server_wtsd > 0 else 0.0),
        "wmsd": _rel(float(stats.get("showdown_count", 0) or 0), 80.0),
        "flop_afq": _rel(flop_actions, 40.0),
        "turn_afq": _rel(turn_actions, 40.0),
        "river_afq": _rel(river_actions, 40.0),
        "river_bet_freq": _rel(river_bf, 40.0),
        "bluff_win_rate": _rel(float(stats.get("bet_win_count", 0) or 0), 20.0),
        "fold_to_cbet": _rel(float(stats.get("fold_to_cbet_opps", 0) or 0), 20.0),
        "river_fold_rate": _rel(float(stats.get("river_facing_bet_opps", 0) or 0), 20.0),
        "three_bet": _rel(float(stats.get("three_bet_opportunities", 0) or 0), 100.0),
        "fold_to_3bet": _rel(float(stats.get("fold_to_3bet_opps", 0) or 0), 30.0),
    }
    return _FeatureVector(uid=uid, values=values, reliability=reliability, z={}, hands=hands)


def _profile_vector(profile: Any, index: _NumericIndex) -> _FeatureVector:
    hands = int(_profile_float(profile, "hands_seen", 0.0))
    vpip = _profile_float(profile, "vpip", index.pool["vpip"])
    pfr = _profile_float(profile, "pfr", index.pool["pfr"])
    flop_actions = _profile_float(profile, "flop_action_count", 0.0)
    turn_actions = _profile_float(profile, "turn_action_count", 0.0)
    river_actions = _profile_float(profile, "river_action_count", 0.0)
    river_bf = _profile_float(profile, "river_bet_count", 0.0) + _profile_float(profile, "river_check_count", 0.0)
    server_af = _profile_float(profile, "server_af_prior", 0.0)
    server_wtsd = _profile_float(profile, "server_wtsd_prior", 0.0)
    values = {
        "vpip": vpip,
        "pfr": pfr,
        "gap": _clamp(vpip - pfr, 0.0, 1.0),
        "af": _profile_float(profile, "af", index.pool["af"]),
        "wtsd": _profile_float(profile, "wtsd", index.pool["wtsd"]),
        "wmsd": _profile_float(profile, "wmsd", index.pool["wmsd"]),
        "flop_afq": _profile_float(profile, "flop_afq", index.pool["flop_afq"]),
        "turn_afq": _profile_float(profile, "turn_afq", index.pool["turn_afq"]),
        "river_afq": _profile_float(profile, "river_afq", index.pool["river_afq"]),
        "river_bet_freq": _profile_float(profile, "river_bet_freq", index.pool["river_bet_freq"]),
        "bluff_win_rate": _profile_float(profile, "bluff_win_rate", index.pool["bluff_win_rate"]),
        "fold_to_cbet": _profile_float(profile, "fold_to_cbet", index.pool["fold_to_cbet"]),
        "river_fold_rate": _profile_float(profile, "river_fold_rate", index.pool["river_fold_rate"]),
        "three_bet": _profile_float(profile, "three_bet_pct", index.pool["three_bet"]),
        "fold_to_3bet": _profile_float(profile, "fold_to_3bet", index.pool["fold_to_3bet"]),
    }
    reliability = {
        "vpip": _rel(hands, 80.0),
        "pfr": _rel(hands, 80.0),
        "gap": _rel(hands, 80.0),
        "af": max(_rel(max(flop_actions + turn_actions + river_actions, hands * 0.25), 80.0), 0.75 if server_af > 0 else 0.0),
        "wtsd": max(_rel(hands, 160.0), 0.75 if server_wtsd > 0 else 0.0),
        "wmsd": _rel(hands, 180.0),
        "flop_afq": _rel(flop_actions, 40.0),
        "turn_afq": _rel(turn_actions, 40.0),
        "river_afq": _rel(river_actions, 40.0),
        "river_bet_freq": _rel(river_bf, 40.0),
        "bluff_win_rate": _rel(_profile_float(profile, "bet_win_count", 0.0), 20.0),
        "fold_to_cbet": _rel(_profile_float(profile, "fold_to_cbet_opps", 0.0), 20.0),
        "river_fold_rate": _rel(_profile_float(profile, "river_facing_bet_opps", 0.0), 20.0),
        "three_bet": _rel(hands, 180.0),
        "fold_to_3bet": _rel(hands, 180.0),
    }
    return _FeatureVector(
        uid="",
        values=values,
        reliability=reliability,
        z=_z_values(values, index.pool, index.scales),
        hands=hands,
    )


def _feature_scales(rows: list[_FeatureVector], pool: Dict[str, float]) -> Dict[str, float]:
    scales: Dict[str, float] = {}
    for name in FEATURES:
        values = sorted(
            row.values.get(name, pool[name])
            for row in rows
            if row.reliability.get(name, 0.0) > 0.05
        )
        if len(values) < 4:
            scales[name] = 0.75 if name == "af" else 0.15
            continue
        q1 = values[int((len(values) - 1) * 0.25)]
        q3 = values[int((len(values) - 1) * 0.75)]
        minimum = 0.35 if name == "af" else 0.05
        scales[name] = max(minimum, q3 - q1)
    return scales


def _z_values(values: Dict[str, float], pool: Dict[str, float], scales: Dict[str, float]) -> Dict[str, float]:
    return {
        name: (values.get(name, pool[name]) - pool[name]) / max(scales.get(name, 0.1), 1e-6)
        for name in FEATURES
    }


def _feature_dict(raw: Any, fallback: Dict[str, float]) -> Dict[str, float]:
    raw = raw if isinstance(raw, dict) else {}
    out: Dict[str, float] = {}
    for name in FEATURES:
        try:
            value = float(raw.get(name, fallback.get(name, FALLBACK_POOL[name])) or 0.0)
        except Exception:
            value = float(fallback.get(name, FALLBACK_POOL[name]))
        out[name] = value
    return out


def _default_scales() -> Dict[str, float]:
    scales = {name: 0.15 for name in FEATURES}
    scales["af"] = 0.75
    return scales


def _round_feature_dict(values: Dict[str, float]) -> Dict[str, float]:
    return {name: round(float(values.get(name, 0.0) or 0.0), 6) for name in FEATURES}


def _json_counts_nested(value: Any) -> Any:
    if isinstance(value, dict):
        out = {}
        for key, child in value.items():
            converted = _json_counts_nested(child)
            if converted not in ({}, 0, 0.0):
                out[str(key)] = converted
        return out
    try:
        number = float(value or 0.0)
    except Exception:
        return 0
    if number <= 0.0:
        return 0
    return int(number) if number.is_integer() else round(number, 6)


def _profile_float(profile: Any, name: str, default: float) -> float:
    if profile is None:
        return float(default)
    try:
        value = getattr(profile, name)
    except Exception:
        return float(default)
    try:
        return float(value() if callable(value) else value)
    except Exception:
        return float(default)


def _safe_rate(success: Any, trials: Any, fallback: float) -> float:
    try:
        s = float(success or 0.0)
        t = float(trials or 0.0)
    except Exception:
        return fallback
    return s / t if t > 0 else fallback


def _rel(samples: float, k: float) -> float:
    samples = max(0.0, float(samples or 0.0))
    return samples / (samples + max(1.0, k))


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, float(x)))
