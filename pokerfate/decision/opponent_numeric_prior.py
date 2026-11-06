"""Numeric opponent priors for CFR exploit decisions.

This module is intentionally independent of Range V2's label buckets.  It uses
the local opponent database as a soft numeric prior, then shrinks current
player stats toward KNN / pool rates according to sample reliability.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any


MODEL_DIR = Path(__file__).resolve().parents[1] / "data" / "local_models"
OPPONENT_MODEL_FILE = "opponents_all_bb.json"

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

GENERIC_BASE = {
    "fold_to_cbet": 0.45,
    "river_fold_rate": 0.45,
    "wtsd": 0.25,
    "af": 1.5,
    "flop_afq": 0.45,
    "turn_afq": 0.40,
    "river_afq": 0.35,
    "river_bet_freq": 0.35,
    "bluff_win_rate": 0.20,
}


@dataclass
class _FeatureVector:
    values: dict[str, float]
    reliability: dict[str, float]
    z: dict[str, float]
    hands: int


@dataclass
class _NumericModel:
    pool: dict[str, float]
    scales: dict[str, float]
    rows: list[_FeatureVector]
    player_count: int


@dataclass
class NumericOpponentPrior:
    fold_bias: float
    sticky_bias: float
    raise_bias: float
    underbluff_score: float
    nut_heavy_score: float
    overvalue_score: float
    fold_lean_score: float
    sticky_score: float
    pressure_score: float
    confidence: float
    source: str
    diagnostics: dict[str, Any]


def build_numeric_prior(
    profile: Any,
    adjustments: dict[str, Any] | None,
    street: str,
    big_blind: Any = None,
) -> NumericOpponentPrior:
    """Return continuous response biases from numeric player similarity."""
    adjustments = adjustments or {}
    street_l = str(street or "").lower()
    model = _load_model("all_bb")
    current = _profile_vector(profile, model)
    final_values, source, knn_conf = _combine_features(current, model)

    sticky = _sticky_score(final_values)
    fold_lean = _fold_lean_score(final_values)
    underbluff = _underbluff_score(final_values)
    overvalue = _overvalue_score(final_values, sticky=sticky, fold_lean=fold_lean)
    nut_heavy = _nut_heavy_score(
        final_values,
        underbluff=underbluff,
        overvalue=overvalue,
        fold_lean=fold_lean,
    )
    pressure = _pressure_score(final_values)

    if adjustments.get("river_bet_rare"):
        underbluff = max(underbluff, 0.65)
        nut_heavy = max(nut_heavy, 0.55 + 0.25 * (1.0 - overvalue))
        pressure = min(pressure, 0.35)
    if adjustments.get("river_bluff_likely"):
        pressure = max(pressure, 0.55)
        underbluff = min(underbluff, 0.35)
        nut_heavy = min(nut_heavy, 0.35)

    ftc = final_values["fold_to_cbet"]
    rfr = final_values["river_fold_rate"]
    wtsd = final_values["wtsd"]
    af = final_values["af"]
    street_afq = final_values.get(f"{street_l}_afq", final_values["turn_afq"])

    fold_bias = (
        (ftc - GENERIC_BASE["fold_to_cbet"]) * 0.90
        - (wtsd - GENERIC_BASE["wtsd"]) * 0.55
        + fold_lean * 0.25
        - sticky * 0.20
    )
    sticky_bias = (
        (GENERIC_BASE["fold_to_cbet"] - ftc) * 0.55
        + (wtsd - GENERIC_BASE["wtsd"]) * 0.75
        + sticky * 0.30
        - fold_lean * 0.18
    )
    if street_l == "river":
        fold_bias += (rfr - GENERIC_BASE["river_fold_rate"]) * 0.80
        sticky_bias += (GENERIC_BASE["river_fold_rate"] - rfr) * 0.45

    base_afq = GENERIC_BASE.get(f"{street_l}_afq", 0.40)
    raise_bias = (
        (street_afq - base_afq) * 0.90
        + ((af - GENERIC_BASE["af"]) / 3.0) * 0.35
        + pressure * 0.25
        - underbluff * 0.20
    )

    bluff_ag = _dict_float(adjustments, "bluff_ag_scale", 0.55)
    value_ag = _dict_float(adjustments, "value_ag_scale", 0.85)
    fold_bias += (bluff_ag - 0.55) * 0.45
    sticky_bias += (value_ag - 0.85) * 0.45
    if adjustments.get("river_bluff_likely"):
        raise_bias += 0.15
    if adjustments.get("river_bet_rare"):
        raise_bias -= 0.18

    query_conf = _query_confidence(current)
    confidence = _clamp(0.08 + 0.42 * query_conf + 0.22 * knn_conf, 0.0, 1.0)
    if profile is None:
        confidence = min(confidence, 0.08)

    return NumericOpponentPrior(
        fold_bias=_clamp(fold_bias, -0.65, 0.85),
        sticky_bias=_clamp(sticky_bias, -0.65, 0.85),
        raise_bias=_clamp(raise_bias, -0.55, 0.75),
        underbluff_score=_clamp(underbluff, 0.0, 1.0),
        nut_heavy_score=_clamp(nut_heavy, 0.0, 1.0),
        overvalue_score=_clamp(overvalue, 0.0, 1.0),
        fold_lean_score=_clamp(fold_lean, 0.0, 1.0),
        sticky_score=_clamp(sticky, 0.0, 1.0),
        pressure_score=_clamp(pressure, 0.0, 1.0),
        confidence=confidence,
        source=source,
        diagnostics={
            "source": source,
            "confidence": round(confidence, 4),
            "knn_confidence": round(knn_conf, 4),
            "query_confidence": round(query_conf, 4),
            "scores": {
                "sticky": round(sticky, 4),
                "fold_lean": round(fold_lean, 4),
                "underbluff": round(underbluff, 4),
                "nut_heavy": round(nut_heavy, 4),
                "overvalue": round(overvalue, 4),
                "pressure": round(pressure, 4),
            },
            "rates": {
                "fold_to_cbet": round(ftc, 4),
                "river_fold_rate": round(rfr, 4),
                "wtsd": round(wtsd, 4),
                "wmsd": round(final_values["wmsd"], 4),
                "vpip": round(final_values["vpip"], 4),
                "pfr": round(final_values["pfr"], 4),
                "af": round(af, 4),
                "street_afq": round(street_afq, 4),
                "bluff_win_rate": round(final_values["bluff_win_rate"], 4),
            },
            "players": model.player_count,
        },
    )


def numeric_feature_confidence(
    profile: Any,
    street: str,
    big_blind: Any = None,
) -> float:
    model = _load_model("all_bb")
    current = _profile_vector(profile, model)
    _final_values, _source, knn_conf = _combine_features(current, model)
    return _clamp(0.60 * _query_confidence(current) + 0.40 * knn_conf, 0.0, 1.0)


def _combine_features(
    current: _FeatureVector,
    model: _NumericModel,
) -> tuple[dict[str, float], str, float]:
    knn_values, knn_reliability, knn_conf = _knn_features(current, model)
    out: dict[str, float] = {}
    for name in FEATURES:
        pool_value = model.pool.get(name, FALLBACK_POOL[name])
        knn_value = knn_values.get(name, pool_value)
        backoff = (1.0 - knn_conf) * pool_value + knn_conf * knn_value
        player_rel = current.reliability.get(name, 0.0)
        if knn_reliability.get(name, 0.0) <= 1e-9:
            backoff = pool_value
        out[name] = _clamp(
            player_rel * current.values.get(name, pool_value)
            + (1.0 - player_rel) * backoff,
            0.0,
            5.0 if name == "af" else 1.0,
        )
    source = "pool"
    if knn_conf > 0.05:
        source = "knn"
    if max(current.reliability.values(), default=0.0) > 0.35:
        source = "player_knn"
    return out, source, knn_conf


def _knn_features(
    current: _FeatureVector,
    model: _NumericModel,
) -> tuple[dict[str, float], dict[str, float], float]:
    query_conf = _query_confidence(current)
    if query_conf <= 0.03 or not model.rows:
        return {}, {}, 0.0

    scored: list[tuple[float, _FeatureVector]] = []
    for row in model.rows:
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

    if not scored:
        return {}, {}, 0.0
    scored.sort(key=lambda item: item[0])
    neighbors = scored[:50]

    sums = {name: 0.0 for name in FEATURES}
    weights = {name: 0.0 for name in FEATURES}
    sim_total = 0.0
    for dist, row in neighbors:
        sim = math.exp(-dist / 0.75)
        sim_total += sim
        for name in FEATURES:
            rel = row.reliability.get(name, 0.0)
            if rel <= 0.0:
                continue
            w = sim * rel
            sums[name] += w * row.values.get(name, model.pool.get(name, FALLBACK_POOL[name]))
            weights[name] += w

    values: dict[str, float] = {}
    reliability: dict[str, float] = {}
    for name in FEATURES:
        if weights[name] <= 1e-12:
            continue
        values[name] = sums[name] / weights[name]
        reliability[name] = weights[name] / (weights[name] + 6.0)

    knn_conf = _clamp((sim_total / (sim_total + 12.0)) * query_conf, 0.0, 0.70)
    return values, reliability, knn_conf


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


@lru_cache(maxsize=4)
def _load_model(key: str) -> _NumericModel:
    path = MODEL_DIR / OPPONENT_MODEL_FILE
    if not path.exists():
        return _empty_model()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return _empty_model()
    players = raw.get("players") if isinstance(raw, dict) else {}
    if not isinstance(players, dict):
        return _empty_model()

    stats_list = [
        entry.get("stats", {})
        for entry in players.values()
        if isinstance(entry, dict) and isinstance(entry.get("stats"), dict)
    ]
    if not stats_list:
        return _empty_model()
    pool = _pool_from_stats(stats_list)
    raw_rows = [_stats_vector(stats, pool) for stats in stats_list]
    rows = [row for row in raw_rows if row.hands > 0]
    scales = _feature_scales(rows, pool)
    rows = [
        _FeatureVector(
            values=row.values,
            reliability=row.reliability,
            z=_z_values(row.values, pool, scales),
            hands=row.hands,
        )
        for row in rows
    ]
    return _NumericModel(pool=pool, scales=scales, rows=rows, player_count=len(rows))


def _empty_model() -> _NumericModel:
    scales = {name: 0.15 for name in FEATURES}
    scales["af"] = 0.75
    return _NumericModel(pool=dict(FALLBACK_POOL), scales=scales, rows=[], player_count=0)


def _pool_from_stats(stats_list: list[dict[str, Any]]) -> dict[str, float]:
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
    stats_list: list[dict[str, Any]],
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


def _stats_vector(stats: dict[str, Any], pool: dict[str, float]) -> _FeatureVector:
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
    return _FeatureVector(values=values, reliability=reliability, z={}, hands=hands)


def _profile_vector(profile: Any, model: _NumericModel) -> _FeatureVector:
    if profile is None:
        return _FeatureVector(values=dict(model.pool), reliability={name: 0.0 for name in FEATURES}, z={}, hands=0)

    hands = int(_profile_float(profile, "hands_seen", 0.0))
    vpip = _profile_float(profile, "vpip", model.pool["vpip"])
    pfr = _profile_float(profile, "pfr", model.pool["pfr"])
    flop_seen = _profile_float(profile, "flop_seen_count", 0.0)
    showdown_count = _profile_float(profile, "showdown_count", 0.0)
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
        "af": _profile_float(profile, "af", model.pool["af"]),
        "wtsd": _profile_float(profile, "wtsd", model.pool["wtsd"]),
        "wmsd": _profile_float(profile, "wmsd", model.pool["wmsd"]),
        "flop_afq": _profile_float(profile, "flop_afq", model.pool["flop_afq"]),
        "turn_afq": _profile_float(profile, "turn_afq", model.pool["turn_afq"]),
        "river_afq": _profile_float(profile, "river_afq", model.pool["river_afq"]),
        "river_bet_freq": _profile_float(profile, "river_bet_freq", model.pool["river_bet_freq"]),
        "bluff_win_rate": _profile_float(profile, "bluff_win_rate", model.pool["bluff_win_rate"]),
        "fold_to_cbet": _profile_float(profile, "fold_to_cbet", model.pool["fold_to_cbet"]),
        "river_fold_rate": _profile_float(profile, "river_fold_rate", model.pool["river_fold_rate"]),
        "three_bet": _profile_float(profile, "three_bet_pct", model.pool["three_bet"]),
        "fold_to_3bet": _profile_float(profile, "fold_to_3bet", model.pool["fold_to_3bet"]),
    }
    reliability = {
        "vpip": _rel(hands, 80.0),
        "pfr": _rel(hands, 80.0),
        "gap": _rel(hands, 80.0),
        "af": max(_rel(max(flop_actions + turn_actions + river_actions, hands * 0.25), 80.0), 0.75 if server_af > 0 else 0.0),
        "wtsd": max(_rel(flop_seen, 80.0), 0.75 if server_wtsd > 0 else 0.0),
        "wmsd": _rel(showdown_count, 80.0),
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
        values=values,
        reliability=reliability,
        z=_z_values(values, model.pool, model.scales),
        hands=hands,
    )


def _feature_scales(rows: list[_FeatureVector], pool: dict[str, float]) -> dict[str, float]:
    scales: dict[str, float] = {}
    for name in FEATURES:
        values = sorted(row.values.get(name, pool[name]) for row in rows if row.reliability.get(name, 0.0) > 0.05)
        if len(values) < 4:
            scales[name] = 0.75 if name == "af" else 0.15
            continue
        q1 = values[int((len(values) - 1) * 0.25)]
        q3 = values[int((len(values) - 1) * 0.75)]
        minimum = 0.35 if name == "af" else 0.05
        scales[name] = max(minimum, q3 - q1)
    return scales


def _z_values(values: dict[str, float], pool: dict[str, float], scales: dict[str, float]) -> dict[str, float]:
    return {
        name: (values.get(name, pool[name]) - pool[name]) / max(scales.get(name, 0.1), 1e-6)
        for name in FEATURES
    }


def _sticky_score(values: dict[str, float]) -> float:
    return _clamp(
        max(0.0, (0.55 - values["fold_to_cbet"]) / 0.40) * 0.30
        + max(0.0, (values["wtsd"] - 0.25) / 0.25) * 0.30
        + max(0.0, (0.50 - values["river_fold_rate"]) / 0.35) * 0.20
        + max(0.0, (1.5 - values["af"]) / 1.5) * 0.20,
        0.0,
        1.0,
    )


def _fold_lean_score(values: dict[str, float]) -> float:
    return _clamp(
        max(0.0, (values["fold_to_cbet"] - 0.45) / 0.35) * 0.40
        + max(0.0, (values["river_fold_rate"] - 0.45) / 0.35) * 0.35
        + max(0.0, (0.25 - values["wtsd"]) / 0.18) * 0.25,
        0.0,
        1.0,
    )


def _underbluff_score(values: dict[str, float]) -> float:
    return _clamp(
        max(0.0, (0.20 - values["bluff_win_rate"]) / 0.20) * 0.35
        + max(0.0, (0.35 - values["river_afq"]) / 0.35) * 0.25
        + max(0.0, (0.35 - values["river_bet_freq"]) / 0.35) * 0.20
        + max(0.0, (1.5 - values["af"]) / 1.5) * 0.20,
        0.0,
        1.0,
    )


def _overvalue_score(
    values: dict[str, float],
    *,
    sticky: float,
    fold_lean: float,
) -> float:
    loose_entry = (
        max(0.0, (values["vpip"] - 0.40) / 0.25) * 0.22
        + max(0.0, (values["gap"] - 0.25) / 0.25) * 0.18
    )
    showdown_leak = (
        max(0.0, (values["wtsd"] - 0.32) / 0.24) * 0.24
        + max(0.0, (0.52 - values["wmsd"]) / 0.28) * 0.20
    )
    passive_confidence = max(0.0, (1.40 - values["af"]) / 1.40) * 0.16
    sticky_part = sticky * 0.18
    score = loose_entry + showdown_leak + passive_confidence + sticky_part - fold_lean * 0.20
    return _clamp(score, 0.0, 1.0)


def _nut_heavy_score(
    values: dict[str, float],
    *,
    underbluff: float,
    overvalue: float,
    fold_lean: float,
) -> float:
    tight_entry = (
        max(0.0, (0.38 - values["vpip"]) / 0.25) * 0.22
        + max(0.0, (0.18 - values["gap"]) / 0.18) * 0.15
    )
    showdown_quality = (
        max(0.0, (values["wmsd"] - 0.52) / 0.25) * 0.30
        + max(0.0, (0.30 - values["wtsd"]) / 0.20) * 0.13
    )
    selective = fold_lean * 0.13 + underbluff * 0.12
    score = tight_entry + showdown_quality + selective - overvalue * 0.35
    return _clamp(score, 0.0, 1.0)


def _pressure_score(values: dict[str, float]) -> float:
    return _clamp(
        max(0.0, (values["af"] - 1.8) / 1.8) * 0.35
        + max(0.0, (values["river_afq"] - 0.35) / 0.35) * 0.25
        + max(0.0, (values["turn_afq"] - 0.40) / 0.35) * 0.15
        + max(0.0, (values["bluff_win_rate"] - 0.20) / 0.30) * 0.25,
        0.0,
        1.0,
    )


def _bb_key(big_blind: Any = None) -> str:
    if isinstance(big_blind, str):
        raw = big_blind.strip()
        if raw in {"bb_1k", "bb_10k", "bb_50k"}:
            return raw
        if raw in {"1k", "10k", "50k"}:
            return f"bb_{raw}"
    try:
        bb = float(big_blind or 0.0)
    except Exception:
        return "bb_10k"
    if bb <= 0:
        return "bb_10k"
    candidates = {1000.0: "bb_1k", 10000.0: "bb_10k", 50000.0: "bb_50k"}
    return candidates[min(candidates, key=lambda value: abs(value - bb))]


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


def _dict_float(values: dict[str, Any], name: str, default: float) -> float:
    try:
        return float(values.get(name, default) or default)
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
