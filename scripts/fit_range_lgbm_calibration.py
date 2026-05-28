"""Fit LightGBM calibration baselines for Range V2 rows.

This is a comparison model, not the default runtime implementation.  It uses
the current bucket/equity predictions as features and learns a supervised
calibration mapping from showdown rows.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import warnings
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

os.environ.setdefault("MPLCONFIGDIR", "/private/tmp/matplotlib")
os.environ.setdefault("LOKY_MAX_CPU_COUNT", str(os.cpu_count() or 1))
warnings.filterwarnings("ignore", category=UserWarning, module="joblib")
warnings.filterwarnings("ignore", message="X does not have valid feature names.*")

import numpy as np
from lightgbm import LGBMClassifier, LGBMRegressor
from sklearn.feature_extraction import DictVectorizer

from scripts.range_calibration_meta import (
    filter_rows_by_meta,
    limit_rows,
    meta_summary,
    parse_flag_filters,
    row_experiment_profile,
    row_strategy_version,
)


CAT_ORDER = ("nuts", "strong", "medium", "draw", "weak_draw", "air")
CAT_IDX = {cat: i for i, cat in enumerate(CAT_ORDER)}
EPS = 1e-6


def _load_rows(paths: Iterable[Path], limit: int = 0) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in paths:
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                rows.append(json.loads(line))
                if limit > 0 and len(rows) >= limit:
                    return rows
    return rows


def _write_json(path: Path | None, obj: Any) -> None:
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True),
                    encoding="utf-8")


def _bucket_vec(row: dict[str, Any]) -> np.ndarray:
    dist = row.get("bucket_dist") or {}
    arr = np.array([float(dist.get(cat, 0.0)) for cat in CAT_ORDER], dtype=np.float64)
    total = float(arr.sum())
    if total > 0:
        arr /= total
    else:
        arr[:] = 1.0 / len(CAT_ORDER)
    return np.clip(arr, EPS, 1.0)


def _label_idx(row: dict[str, Any]) -> int:
    return CAT_IDX.get(str(row.get("actual_bucket") or ""), CAT_IDX["air"])


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


def _nopp_bin(row: dict[str, Any]) -> str:
    n = int(row.get("active_player_count") or len(row.get("active_player_ids") or []) or 1)
    if n <= 1:
        return "1"
    if n == 2:
        return "2"
    return "3+"


def _board_texture(row: dict[str, Any]) -> str:
    board = row.get("board") or []
    if len(board) < 3:
        return "pre"
    ranks = [str(c)[0] for c in board if c]
    suits = [str(c)[1] for c in board if len(str(c)) >= 2]
    paired = len(set(ranks)) < len(ranks)
    if len(suits) >= 3 and len(set(suits[:3])) == 1:
        flush = "mono"
    elif len(suits) >= 3 and max(suits[:3].count(s) for s in set(suits[:3])) >= 2:
        flush = "fd"
    else:
        flush = "rainbow"
    return ("paired" if paired else "unpaired") + ":" + flush


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        x = float(value)
    except Exception:
        return default
    if not math.isfinite(x):
        return default
    return x


def _clip01(value: Any, scale: float = 1.0) -> float:
    x = _safe_float(value)
    if scale > 0:
        x /= scale
    return max(0.0, min(1.0, x))


def _bet_size_bucket(ratio: Any) -> str:
    x = _safe_float(ratio)
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


_RANK_VAL = {
    "2": 2, "3": 3, "4": 4, "5": 5, "6": 6, "7": 7, "8": 8,
    "9": 9, "T": 10, "J": 11, "Q": 12, "K": 13, "A": 14,
}
_STRAIGHT_SEQUENCES = tuple(
    set(seq)
    for seq in (
        (14, 13, 12, 11, 10),
        (13, 12, 11, 10, 9),
        (12, 11, 10, 9, 8),
        (11, 10, 9, 8, 7),
        (10, 9, 8, 7, 6),
        (9, 8, 7, 6, 5),
        (8, 7, 6, 5, 4),
        (7, 6, 5, 4, 3),
        (6, 5, 4, 3, 2),
        (14, 5, 4, 3, 2),
    )
)


def _card_parts(cards: Any) -> list[tuple[int, str]]:
    out: list[tuple[int, str]] = []
    for raw in cards or []:
        s = str(raw).strip()
        if len(s) < 2:
            continue
        rank = _RANK_VAL.get(s[0].upper())
        if rank is None:
            continue
        out.append((rank, s[1].lower()))
    return out


def _board_features(row: dict[str, Any]) -> dict[str, Any]:
    raw = row.get("board_features")
    if isinstance(raw, dict) and raw:
        return raw
    board = _card_parts(row.get("board") or [])
    if not board:
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
    ranks = sorted({r for r, _s in board})
    suits = [s for _r, s in board]
    rank_counts = Counter(r for r, _s in board)
    suit_counts = Counter(suits)
    max_suit_count = max(suit_counts.values()) if suit_counts else 0
    gaps = [ranks[i + 1] - ranks[i] for i in range(len(ranks) - 1)]
    avg_gap = sum(gaps) / len(gaps) if gaps else 10.0
    connectedness = max(0.0, min(1.0, 1.0 - (avg_gap - 1.0) / 5.0))
    flush_draw = max_suit_count >= 2
    monotone = max_suit_count >= 3
    straight_draw_heavy = len(ranks) >= 2 and avg_gap <= 2.5
    straight_possible = False
    if len(ranks) >= 5:
        for i in range(len(ranks) - 4):
            if ranks[i + 4] - ranks[i] == 4:
                straight_possible = True
                break
    paired = any(cnt >= 2 for cnt in rank_counts.values())
    wetness = 0.0
    if flush_draw:
        wetness += 0.40
    if monotone:
        wetness += 0.20
    if straight_draw_heavy:
        wetness += 0.30
    if paired:
        wetness -= 0.10
    wetness = max(0.0, min(1.0, wetness))
    if len(board) >= 5:
        wetness *= 0.3
    return {
        "wetness": wetness,
        "paired": paired,
        "monotone": monotone,
        "flush_possible": max_suit_count >= 3,
        "flush_draw": flush_draw,
        "straight_possible": straight_possible,
        "straight_draw_heavy": straight_draw_heavy,
        "high_card_rank": max(ranks) if ranks else 0,
        "connectedness": connectedness,
    }


def _hero_draw_features(row: dict[str, Any]) -> dict[str, bool]:
    raw = row.get("hero_draw")
    if isinstance(raw, dict) and raw:
        return {str(k): bool(v) for k, v in raw.items()}
    hole = _card_parts(row.get("hero_cards") or [])
    board = _card_parts(row.get("board") or [])
    out = {
        "flush_draw": False,
        "oesd": False,
        "gutshot": False,
        "backdoor_flush": False,
        "overcards": False,
    }
    if len(hole) < 2 or len(board) < 3 or len(board) >= 5:
        return out
    cards = hole + board
    suit_counts = Counter(s for _r, s in cards)
    out["flush_draw"] = any(
        cnt >= 4 and any(hs == suit for _hr, hs in hole)
        for suit, cnt in suit_counts.items()
    )
    out["backdoor_flush"] = (
        len(board) == 3
        and not out["flush_draw"]
        and any(
            cnt >= 3 and any(hs == suit for _hr, hs in hole)
            for suit, cnt in suit_counts.items()
        )
    )
    all_ranks = {r for r, _s in cards}
    hole_ranks = {r for r, _s in hole}
    straight_out_ranks: set[int] = set()
    for seq in _STRAIGHT_SEQUENCES:
        present = seq & all_ranks
        if len(present) != 4 or not (hole_ranks & present):
            continue
        missing = seq - present
        if len(missing) == 1:
            straight_out_ranks.update(missing)
    out["oesd"] = len(straight_out_ranks) >= 2
    out["gutshot"] = len(straight_out_ranks) == 1
    top_board = max(r for r, _s in board)
    out["overcards"] = all(r > top_board for r, _s in hole)
    return out


def _hero_blocker_features(row: dict[str, Any]) -> dict[str, bool]:
    raw = row.get("hero_blockers")
    if isinstance(raw, dict) and raw:
        return {str(k): bool(v) for k, v in raw.items()}
    hole = _card_parts(row.get("hero_cards") or [])
    board = _card_parts(row.get("board") or [])
    out = {
        "nut_flush_blocker": False,
        "set_blocker": False,
        "straight_blocker": False,
    }
    if len(hole) < 2 or len(board) < 3:
        return out
    suit_counts = Counter(s for _r, s in board)
    out["nut_flush_blocker"] = any(
        cnt >= 2 and any(hr == 14 and hs == suit for hr, hs in hole)
        for suit, cnt in suit_counts.items()
    )
    board_ranks = {r for r, _s in board}
    out["set_blocker"] = any(r in board_ranks for r, _s in hole)
    ranks = sorted(board_ranks)
    if len(ranks) >= 2:
        top = max(ranks)
        window = set(range(max(2, top - 4), top + 1))
        out["straight_blocker"] = any(
            r in window and r not in board_ranks for r, _s in hole
        )
    return out


def _profile_feature_dict(stats: dict[str, Any]) -> dict[str, float]:
    hands = _safe_float(stats.get("hands_seen"))
    showdown = _safe_float(stats.get("showdown_count"))
    flop_seen = _safe_float(stats.get("flop_seen_count"))
    bet_count = _safe_float(stats.get("bet_count"))
    raise_count = _safe_float(stats.get("raise_count"))
    call_count = _safe_float(stats.get("call_count"))
    river_bet = _safe_float(stats.get("river_bet_count"))
    river_check = _safe_float(stats.get("river_check_count"))
    river_fold = _safe_float(stats.get("river_facing_bet_fold_count", stats.get("river_fold_count")))
    river_facing = _safe_float(stats.get("river_facing_bet_opps"))
    bet_win = _safe_float(stats.get("bet_win_count"))
    bluff_win = _safe_float(stats.get("bluff_win_count"))
    return {
        "hands_seen": hands,
        "vpip": _safe_float(stats.get("vpip"), _safe_float(stats.get("vpip_count")) / hands if hands > 0 else 0.0),
        "pfr": _safe_float(stats.get("pfr"), _safe_float(stats.get("pfr_count")) / hands if hands > 0 else 0.0),
        "af": _safe_float(stats.get("af"), (bet_count + raise_count) / max(1.0, call_count)),
        "three_bet_pct": _safe_float(
            stats.get("three_bet_pct"),
            _safe_float(stats.get("three_bet_count")) / max(1.0, _safe_float(stats.get("three_bet_opportunities"))),
        ),
        "fold_to_3bet": _safe_float(
            stats.get("fold_to_3bet"),
            _safe_float(stats.get("fold_to_3bet_count")) / max(1.0, _safe_float(stats.get("fold_to_3bet_opps"))),
        ),
        "fold_to_cbet": _safe_float(
            stats.get("fold_to_cbet"),
            _safe_float(stats.get("fold_to_cbet_count")) / max(1.0, _safe_float(stats.get("fold_to_cbet_opps"))),
        ),
        "wtsd": _safe_float(stats.get("wtsd"), showdown / max(1.0, flop_seen)),
        "wmsd": _safe_float(stats.get("wmsd"), _safe_float(stats.get("showdown_win_count")) / max(1.0, showdown)),
        "river_bet_freq": _safe_float(stats.get("river_bet_freq"), river_bet / max(1.0, river_bet + river_check)),
        "river_fold_rate": _safe_float(stats.get("river_fold_rate"), river_fold / max(1.0, river_facing)),
        "bluff_win_rate": _safe_float(stats.get("bluff_win_rate"), bluff_win / max(1.0, bet_win)),
        "pwi": _safe_float(stats.get("pwi")),
    }


def _load_player_profiles(path: Path | None) -> dict[str, dict[str, float]]:
    if path is None:
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    profiles: dict[str, dict[str, float]] = {}
    players = raw.get("players") if isinstance(raw, dict) else {}
    if isinstance(players, dict):
        for uid, value in players.items():
            if not isinstance(value, dict):
                continue
            stats = value.get("stats") if isinstance(value.get("stats"), dict) else value
            profiles[f"id:{uid}"] = _profile_feature_dict(stats)
    names = raw.get("name_archive") if isinstance(raw, dict) else {}
    if isinstance(names, dict):
        for name, stats in names.items():
            if isinstance(stats, dict):
                profiles[f"name:{name}"] = _profile_feature_dict(stats)
    return profiles


def _row_profile(row: dict[str, Any], profiles: dict[str, dict[str, float]]) -> dict[str, float]:
    uid = str(row.get("player_uid") or "")
    if uid and f"id:{uid}" in profiles:
        return profiles[f"id:{uid}"]
    return {}


def _relation_dist(row: dict[str, Any]) -> dict[str, float]:
    rel = row.get("villain_vs_hero_dist") or {}
    try:
        win = max(0.0, float(rel.get("win", 0.0) or 0.0))
        tie = max(0.0, float(rel.get("tie", 0.0) or 0.0))
        loss = max(0.0, float(rel.get("loss", 0.0) or 0.0))
    except Exception:
        return {"win": 0.0, "tie": 0.0, "loss": 0.0}
    total = win + tie + loss
    if total <= 1e-12:
        return {"win": 0.0, "tie": 0.0, "loss": 0.0}
    return {"win": win / total, "tie": tie / total, "loss": loss / total}


def _relation_eq_from_dist(row: dict[str, Any]) -> float | None:
    rel = _relation_dist(row)
    if rel["win"] + rel["tie"] + rel["loss"] <= 1e-12:
        return None
    return rel["win"] + 0.5 * rel["tie"]


def _actual_relation_eq(row: dict[str, Any]) -> float | None:
    relation = str(row.get("actual_relation") or "")
    if relation == "win":
        return 1.0
    if relation == "tie":
        return 0.5
    if relation == "loss":
        return 0.0
    return None


def _features(
    row: dict[str, Any],
    raw_eq: float | None = None,
    include_player: bool = False,
    include_relative: bool = False,
    include_context: bool = False,
    player_profiles: dict[str, dict[str, float]] | None = None,
) -> dict[str, Any]:
    p = _bucket_vec(row)
    ordered = np.sort(p)[::-1]
    out: dict[str, Any] = {
        "street=" + str(row.get("street") or "?"): 1,
        "trigger=" + str(row.get("trigger") or "?"): 1,
        "action=" + _action_ctx(str(row.get("trigger") or "")): 1,
        "nopp=" + _nopp_bin(row): 1,
        "texture=" + _board_texture(row): 1,
        "hero_bucket=" + str(row.get("hero_bucket") or "?"): 1,
        "top_bucket=" + CAT_ORDER[int(np.argmax(p))]: 1,
        "strategy_version=" + row_strategy_version(row): 1,
        "experiment_profile=" + row_experiment_profile(row): 1,
        "range_pct": float(row.get("range_pct") or 0.0),
        "board_len": min(len(row.get("board") or []), 5) / 5.0,
        "top_prob": float(ordered[0]),
        "top_margin": float(ordered[0] - ordered[1]) if len(ordered) > 1 else 0.0,
        "entropy": float(-np.sum(p * np.log(np.clip(p, EPS, 1.0))) / math.log(len(CAT_ORDER))),
    }
    for cat, val in zip(CAT_ORDER, p):
        out[f"p_{cat}"] = float(val)
        out[f"logp_{cat}"] = float(np.log(max(float(val), EPS)) / 8.0)
    if raw_eq is not None:
        raw_eq = float(np.clip(raw_eq, EPS, 1.0 - EPS))
        out["raw_eq"] = raw_eq
        out["raw_eq_logit"] = float(np.log(raw_eq / (1.0 - raw_eq)) / 8.0)
    if include_relative:
        board_texture = str(row.get("board_texture") or "") or _board_texture(row)
        rel = _relation_dist(row)
        out["hero_made_subtype=" + str(row.get("hero_made_subtype") or "?")] = 1
        out["hero_hand_rank=" + str(row.get("hero_hand_rank") or "?")] = 1
        out["board_texture=" + board_texture] = 1
        out["rel_win"] = rel["win"]
        out["rel_tie"] = rel["tie"]
        out["rel_loss"] = rel["loss"]
        out["rel_loss_minus_win"] = rel["loss"] - rel["win"]
        out["rel_non_tie"] = rel["win"] + rel["loss"]
    if include_context:
        ratio = _safe_float(row.get("action_bet_ratio"))
        bet_bucket = str(row.get("bet_size_bucket") or "") or _bet_size_bucket(ratio)
        out["position=" + str(row.get("position") or "?")] = 1
        out["is_ip=" + ("ip" if bool(row.get("is_ip")) else "oop")] = 1
        out["facing_action=" + str(row.get("facing_action") or "?")] = 1
        out["preflop_action_type=" + str(row.get("preflop_action_type") or "?")] = 1
        out["bet_size_bucket=" + bet_bucket] = 1
        out["action_sequence=" + str(row.get("action_sequence") or "?")] = 1
        out["action_bet_ratio"] = _clip01(ratio, 4.0)
        out["is_raise_over"] = 1.0 if row.get("is_raise_over") else 0.0

        board_features = _board_features(row)
        for key in (
            "paired", "monotone", "flush_possible", "flush_draw",
            "straight_possible", "straight_draw_heavy",
        ):
            out[f"board_{key}"] = 1.0 if board_features.get(key) else 0.0
        out["board_wetness"] = _clip01(board_features.get("wetness"), 1.0)
        out["board_connectedness"] = _clip01(board_features.get("connectedness"), 1.0)
        out["board_high_card_rank"] = _clip01(board_features.get("high_card_rank"), 14.0)

        out["hero_made_subtype=" + str(row.get("hero_made_subtype") or "?")] = 1
        out["hero_hand_rank=" + str(row.get("hero_hand_rank") or "?")] = 1
        draw = _hero_draw_features(row)
        for key in ("flush_draw", "oesd", "gutshot", "backdoor_flush", "overcards"):
            out[f"hero_draw_{key}"] = 1.0 if draw.get(key) else 0.0
        blockers = _hero_blocker_features(row)
        for key in ("nut_flush_blocker", "set_blocker", "straight_blocker"):
            out[f"hero_blocker_{key}"] = 1.0 if blockers.get(key) else 0.0

    profiles = player_profiles or {}
    if profiles:
        profile = _row_profile(row, profiles)
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
            out[f"profile_{key}"] = _clip01(profile.get(key), scale)
    if include_player:
        out["player_uid=" + str(row.get("player_uid") or "?")] = 1
    return out


def _bucket_rows(rows: list[dict[str, Any]], streets: set[str]) -> list[dict[str, Any]]:
    return [
        r for r in rows
        if r.get("actual_bucket") in CAT_IDX and str(r.get("street")) in streets
    ]


def _equity_items(rows: list[dict[str, Any]], target: str) -> list[tuple[dict[str, Any], float, float]]:
    pred_key = "predicted_hero_eq_multi" if target == "multi" else "predicted_hero_eq"
    actual_key = "actual_hero_eq_street_multi" if target == "multi" else "actual_hero_eq_street"
    out = []
    for row in rows:
        pred = row.get(pred_key)
        actual = row.get(actual_key)
        if pred is None or actual is None:
            continue
        pred_f = float(pred)
        actual_f = float(actual)
        if 0.0 <= pred_f <= 1.0 and 0.0 <= actual_f <= 1.0:
            out.append((row, pred_f, actual_f))
    return out


def _relative_items(rows: list[dict[str, Any]]) -> list[tuple[dict[str, Any], float, float]]:
    out: list[tuple[dict[str, Any], float, float]] = []
    for row in rows:
        if row.get("street") != "river":
            continue
        pred = row.get("predicted_relation_eq")
        if pred is None:
            pred = _relation_eq_from_dist(row)
        actual = _actual_relation_eq(row)
        if pred is None or actual is None:
            continue
        pred_f = float(pred)
        actual_f = float(actual)
        if 0.0 <= pred_f <= 1.0 and 0.0 <= actual_f <= 1.0:
            out.append((row, pred_f, actual_f))
    return out


def _bucket_metrics(rows: list[dict[str, Any]], probs: np.ndarray) -> dict[str, Any]:
    if not rows:
        return {"n": 0}
    y = np.array([_label_idx(r) for r in rows], dtype=np.int64)
    py = probs[np.arange(len(rows)), y]
    strong_nuts_mask = np.array([
        r.get("actual_bucket") in ("strong", "nuts") for r in rows
    ], dtype=bool)
    brier = float(np.mean(np.sum((probs - np.eye(len(CAT_ORDER))[y]) ** 2, axis=1)))
    strong_nuts_combo = probs[:, CAT_IDX["strong"]] + probs[:, CAT_IDX["nuts"]]
    return {
        "n": len(rows),
        "nll": round(float(-np.mean(np.log(np.clip(py, EPS, 1.0)))), 5),
        "brier": round(brier, 5),
        "actual_bucket_avg_pct": round(float(np.mean(py) * 100.0), 2),
        "under_10_pct": round(float(np.mean(py < 0.10) * 100.0), 2),
        "top1_pct": round(float(np.mean(np.argmax(probs, axis=1) == y) * 100.0), 2),
        "strong_nuts_under_20_pct": round(
            float(np.mean(py[strong_nuts_mask] < 0.20) * 100.0)
            if bool(strong_nuts_mask.any()) else 0.0,
            2,
        ),
        "strong_nuts_combo_under_20_pct": round(
            float(np.mean(strong_nuts_combo[strong_nuts_mask] < 0.20) * 100.0)
            if bool(strong_nuts_mask.any()) else 0.0,
            2,
        ),
        "strong_nuts_combo_avg_pct": round(
            float(np.mean(strong_nuts_combo[strong_nuts_mask]) * 100.0)
            if bool(strong_nuts_mask.any()) else 0.0,
            2,
        ),
    }


def _bucket_risk_summary(raw: dict[str, Any], fit: dict[str, Any]) -> dict[str, Any]:
    return {
        "strong_nuts_under_20_delta_pp": round(
            float(fit.get("strong_nuts_under_20_pct", 0.0))
            - float(raw.get("strong_nuts_under_20_pct", 0.0)),
            2,
        ),
        "strong_nuts_combo_under_20_delta_pp": round(
            float(fit.get("strong_nuts_combo_under_20_pct", 0.0))
            - float(raw.get("strong_nuts_combo_under_20_pct", 0.0)),
            2,
        ),
        "strong_nuts_combo_avg_delta_pp": round(
            float(fit.get("strong_nuts_combo_avg_pct", 0.0))
            - float(raw.get("strong_nuts_combo_avg_pct", 0.0)),
            2,
        ),
    }


def _select_bucket_blend(
    rows: list[dict[str, Any]],
    raw_probs: np.ndarray,
    model_probs: np.ndarray,
    *,
    min_bucket_nll_gain: float,
    max_strong_nuts_under_worsen_pp: float,
    max_strong_nuts_combo_under_worsen_pp: float,
) -> dict[str, Any]:
    raw_m = _bucket_metrics(rows, raw_probs)
    best: dict[str, Any] | None = None
    for alpha in np.linspace(0.05, 1.0, 20):
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
        )
        candidate = {
            "alpha": round(float(alpha), 2),
            "metrics": metrics,
            "risk": risk,
            "nll_gain": nll_gain,
            "usable": usable,
        }
        if usable and (
            best is None
            or candidate["nll_gain"] > best["nll_gain"]
            or (
                candidate["nll_gain"] == best["nll_gain"]
                and candidate["alpha"] > best["alpha"]
            )
        ):
            best = candidate
    if best is not None:
        return best
    return {
        "alpha": 0.0,
        "metrics": raw_m,
        "risk": _bucket_risk_summary(raw_m, raw_m),
        "nll_gain": 0.0,
        "usable": False,
    }


def _equity_metrics(items: list[tuple[dict[str, Any], float, float]], pred: np.ndarray) -> dict[str, Any]:
    if not items:
        return {"n": 0}
    y = np.array([actual for _row, _pred, actual in items], dtype=np.float64)
    err = pred - y
    high_mask = y >= 0.75
    low_mask = y <= 0.25
    return {
        "n": len(items),
        "mae_pp": round(float(np.mean(np.abs(err)) * 100.0), 2),
        "rmse_pp": round(float(math.sqrt(np.mean(err * err))) * 100.0, 2),
        "bias_pp": round(float(np.mean(err) * 100.0), 2),
        "ece_pp": round(_ece(pred, y) * 100.0, 2),
        "high_actual_under_50_pct": round(
            float(np.mean(pred[high_mask] < 0.50) * 100.0)
            if bool(high_mask.any()) else 0.0,
            2,
        ),
        "high_actual_avg_pred_pct": round(
            float(np.mean(pred[high_mask]) * 100.0)
            if bool(high_mask.any()) else 0.0,
            2,
        ),
        "low_actual_over_50_pct": round(
            float(np.mean(pred[low_mask] > 0.50) * 100.0)
            if bool(low_mask.any()) else 0.0,
            2,
        ),
        "low_actual_avg_pred_pct": round(
            float(np.mean(pred[low_mask]) * 100.0)
            if bool(low_mask.any()) else 0.0,
            2,
        ),
    }


def _equity_risk_summary(raw: dict[str, Any], fit: dict[str, Any]) -> dict[str, Any]:
    return {
        "high_actual_under_50_delta_pp": round(
            float(fit.get("high_actual_under_50_pct", 0.0))
            - float(raw.get("high_actual_under_50_pct", 0.0)),
            2,
        ),
        "high_actual_avg_pred_delta_pp": round(
            float(fit.get("high_actual_avg_pred_pct", 0.0))
            - float(raw.get("high_actual_avg_pred_pct", 0.0)),
            2,
        ),
        "low_actual_over_50_delta_pp": round(
            float(fit.get("low_actual_over_50_pct", 0.0))
            - float(raw.get("low_actual_over_50_pct", 0.0)),
            2,
        ),
        "low_actual_avg_pred_delta_pp": round(
            float(fit.get("low_actual_avg_pred_pct", 0.0))
            - float(raw.get("low_actual_avg_pred_pct", 0.0)),
            2,
        ),
    }


def _select_equity_blend(
    items: list[tuple[dict[str, Any], float, float]],
    raw_pred: np.ndarray,
    model_pred: np.ndarray,
    *,
    min_mae_gain_pp: float,
    max_high_actual_under_worsen_pp: float,
    max_low_actual_over_worsen_pp: float,
) -> dict[str, Any]:
    raw_m = _equity_metrics(items, raw_pred)
    best: dict[str, Any] | None = None
    for alpha in np.linspace(0.05, 1.0, 20):
        blended = np.clip(
            (1.0 - float(alpha)) * raw_pred + float(alpha) * model_pred,
            0.0,
            1.0,
        )
        metrics = _equity_metrics(items, blended)
        risk = _equity_risk_summary(raw_m, metrics)
        gain = round(float(raw_m["mae_pp"] - metrics["mae_pp"]), 3)
        usable = (
            gain >= min_mae_gain_pp
            and risk["high_actual_under_50_delta_pp"] <= max_high_actual_under_worsen_pp
            and risk["low_actual_over_50_delta_pp"] <= max_low_actual_over_worsen_pp
        )
        candidate = {
            "alpha": round(float(alpha), 2),
            "metrics": metrics,
            "risk": risk,
            "mae_gain_pp": gain,
            "usable": usable,
        }
        if usable and (
            best is None
            or candidate["mae_gain_pp"] > best["mae_gain_pp"]
            or (
                candidate["mae_gain_pp"] == best["mae_gain_pp"]
                and candidate["alpha"] > best["alpha"]
            )
        ):
            best = candidate
    if best is not None:
        return best
    return {
        "alpha": 0.0,
        "metrics": raw_m,
        "risk": _equity_risk_summary(raw_m, raw_m),
        "mae_gain_pp": 0.0,
        "usable": False,
    }


def _hand_key(row: dict[str, Any]) -> str:
    return str(row.get("hand") or row.get("hand_id") or row.get("session_id") or id(row))


def _equity_sample_weights(
    items: list[tuple[dict[str, Any], float, float]],
    y: np.ndarray,
    *,
    args: Any,
) -> np.ndarray | None:
    weights = np.ones(len(items), dtype=np.float64)
    if args.equity_high_actual_weight > 1.0:
        weights[y >= 0.75] = float(args.equity_high_actual_weight)
    if args.equity_low_actual_weight > 1.0:
        weights[y <= 0.25] = np.maximum(
            weights[y <= 0.25],
            float(args.equity_low_actual_weight),
        )

    hand_mode = str(getattr(args, "equity_hand_weight", "none") or "none")
    if hand_mode != "none":
        counts: dict[str, int] = {}
        for row, _pred, _actual in items:
            key = _hand_key(row)
            counts[key] = counts.get(key, 0) + 1
        for idx, (row, _pred, _actual) in enumerate(items):
            n = max(1, counts.get(_hand_key(row), 1))
            if hand_mode == "inv":
                weights[idx] *= 1.0 / float(n)
            elif hand_mode == "inv_sqrt":
                weights[idx] *= 1.0 / math.sqrt(float(n))
            else:
                raise ValueError(f"unknown equity hand weight: {hand_mode}")

    if np.allclose(weights, 1.0):
        return None
    mean = float(np.mean(weights))
    if mean > 1e-12:
        weights /= mean
    return weights


def _ece(pred: np.ndarray, actual: np.ndarray, bins: int = 10) -> float:
    score = 0.0
    for i in range(bins):
        lo = i / bins
        hi = (i + 1) / bins
        mask = (pred >= lo) & ((pred <= hi) if i == bins - 1 else (pred < hi))
        if bool(mask.any()):
            score += float(mask.mean()) * abs(float(pred[mask].mean() - actual[mask].mean()))
    return score


def _full_class_proba(clf: LGBMClassifier, probs: np.ndarray) -> np.ndarray:
    out = np.full((probs.shape[0], len(CAT_ORDER)), EPS, dtype=np.float64)
    for col, cls in enumerate(clf.classes_):
        out[:, int(cls)] = probs[:, col]
    out /= out.sum(axis=1, keepdims=True)
    return out


def _fit_equity_lgbm_model(
    tr_items: list[tuple[dict[str, Any], float, float]],
    va_items: list[tuple[dict[str, Any], float, float]],
    *,
    args: Any,
    include_relative: bool = False,
    include_context: bool = False,
    player_profiles: dict[str, dict[str, float]] | None = None,
    random_state: int = 43,
) -> tuple[dict[str, Any], dict[str, Any], np.ndarray, np.ndarray, np.ndarray]:
    vec = DictVectorizer(sparse=True)
    x_tr = vec.fit_transform([
        _features(
            row,
            pred,
            include_player=args.include_player,
            include_relative=include_relative,
            include_context=include_context,
            player_profiles=player_profiles,
        )
        for row, pred, _actual in tr_items
    ])
    x_va = vec.transform([
        _features(
            row,
            pred,
            include_player=args.include_player,
            include_relative=include_relative,
            include_context=include_context,
            player_profiles=player_profiles,
        )
        for row, pred, _actual in va_items
    ])
    y_tr = np.array([actual for _row, _pred, actual in tr_items], dtype=np.float64)
    raw_tr = np.array([pred for _row, pred, _actual in tr_items], dtype=np.float64)
    raw_va = np.array([pred for _row, pred, _actual in va_items], dtype=np.float64)
    prediction_kind = "residual" if getattr(args, "equity_residual", False) else "absolute"
    y_fit = y_tr - raw_tr if prediction_kind == "residual" else y_tr
    reg = LGBMRegressor(
        objective="regression",
        n_estimators=args.n_estimators,
        learning_rate=args.learning_rate,
        num_leaves=args.num_leaves,
        min_child_samples=args.min_child_samples,
        reg_lambda=args.reg_lambda,
        subsample=0.9,
        colsample_bytree=0.9,
        n_jobs=1,
        random_state=random_state,
        verbose=-1,
    )
    fit_kwargs: dict[str, Any] = {}
    weights = _equity_sample_weights(tr_items, y_tr, args=args)
    if weights is not None:
        fit_kwargs["sample_weight"] = weights
    reg.fit(x_tr, y_fit, **fit_kwargs)
    raw_model_tr = np.asarray(reg.predict(x_tr), dtype=np.float64)
    raw_model_va = np.asarray(reg.predict(x_va), dtype=np.float64)
    if prediction_kind == "residual":
        pred_tr = np.clip(raw_tr + raw_model_tr, 0.0, 1.0)
        pred_va = np.clip(raw_va + raw_model_va, 0.0, 1.0)
    else:
        pred_tr = np.clip(raw_model_tr, 0.0, 1.0)
        pred_va = np.clip(raw_model_va, 0.0, 1.0)
    raw_val_m = _equity_metrics(va_items, raw_va)
    lgb_val_m = _equity_metrics(va_items, pred_va)
    val_risk = _equity_risk_summary(raw_val_m, lgb_val_m)
    val_mae_gain_pp = round(raw_val_m["mae_pp"] - lgb_val_m["mae_pp"], 3)
    selected = _select_equity_blend(
        va_items,
        raw_va,
        pred_va,
        min_mae_gain_pp=args.min_equity_mae_gain_pp,
        max_high_actual_under_worsen_pp=args.max_high_actual_under_worsen_pp,
        max_low_actual_over_worsen_pp=args.max_low_actual_over_worsen_pp,
    )
    runtime_usable = bool(selected["usable"])
    selected_pred_va = np.clip(
        (1.0 - float(selected["alpha"])) * raw_va
        + float(selected["alpha"]) * pred_va,
        0.0,
        1.0,
    )
    report = {
        "features": len(vec.feature_names_),
        "train_raw": _equity_metrics(tr_items, raw_tr),
        "train_lgbm": _equity_metrics(tr_items, pred_tr),
        "val_raw": raw_val_m,
        "val_lgbm": lgb_val_m,
        "val_mae_gain_pp": val_mae_gain_pp,
        "val_ece_gain_pp": round(raw_val_m["ece_pp"] - lgb_val_m["ece_pp"], 3),
        "val_risk": val_risk,
        "selected_blend": selected,
        "runtime_usable": runtime_usable,
        "usable_gate": {
            "min_mae_gain_pp": args.min_equity_mae_gain_pp,
            "max_high_actual_under_worsen_pp": args.max_high_actual_under_worsen_pp,
            "max_low_actual_over_worsen_pp": args.max_low_actual_over_worsen_pp,
        },
    }
    model = {
        "feature_names": list(vec.feature_names_),
        "blend_alpha": selected["alpha"],
        "runtime_usable": runtime_usable,
        "model_str": reg.booster_.model_to_string(),
        "prediction_kind": prediction_kind,
        "selected_blend": selected,
        "metrics": {
            "train_raw": report["train_raw"],
            "train_lgbm": report["train_lgbm"],
            "val_raw": raw_val_m,
            "val_lgbm": lgb_val_m,
            "val_mae_gain_pp": val_mae_gain_pp,
            "val_ece_gain_pp": report["val_ece_gain_pp"],
            "val_risk": val_risk,
        },
    }
    return report, model, raw_va, pred_va, selected_pred_va


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--train-rows", type=Path, action="append", required=True)
    ap.add_argument("--val-rows", type=Path, action="append", required=True)
    ap.add_argument("--report-out", type=Path)
    ap.add_argument("--bucket-model-out", type=Path)
    ap.add_argument("--equity-model-out", type=Path)
    ap.add_argument("--bucket-streets", default="flop,turn,river")
    ap.add_argument("--equity-target", choices=("multi", "hu"), default="multi")
    ap.add_argument("--equity-by-street", action="store_true")
    ap.add_argument("--equity-residual", action="store_true")
    ap.add_argument("--equity-hand-weight", choices=("none", "inv_sqrt", "inv"),
                    default="none")
    ap.add_argument("--equity-relative-features", action="store_true")
    ap.add_argument("--equity-context-features", action="store_true")
    ap.add_argument("--equity-player-profile-json", type=Path,
                    default=Path("pokerfate/data/opponents.json"))
    ap.add_argument("--include-player", action="store_true")
    ap.add_argument("--max-train-rows", type=int, default=0)
    ap.add_argument("--max-val-rows", type=int, default=0)
    ap.add_argument("--n-estimators", type=int, default=120)
    ap.add_argument("--learning-rate", type=float, default=0.04)
    ap.add_argument("--num-leaves", type=int, default=15)
    ap.add_argument("--min-child-samples", type=int, default=35)
    ap.add_argument("--reg-lambda", type=float, default=5.0)
    ap.add_argument("--bucket-strong-nuts-weight", type=float, default=2.0)
    ap.add_argument("--min-bucket-nll-gain", type=float, default=0.001)
    ap.add_argument("--max-strong-nuts-under-worsen-pp", type=float, default=0.0)
    ap.add_argument("--max-strong-nuts-combo-under-worsen-pp", type=float, default=0.0)
    ap.add_argument("--equity-high-actual-weight", type=float, default=1.5)
    ap.add_argument("--equity-low-actual-weight", type=float, default=1.25)
    ap.add_argument("--min-equity-mae-gain-pp", type=float, default=0.01)
    ap.add_argument("--max-high-actual-under-worsen-pp", type=float, default=0.0)
    ap.add_argument("--max-low-actual-over-worsen-pp", type=float, default=0.0)
    ap.add_argument("--skip-bucket", action="store_true")
    ap.add_argument("--skip-equity", action="store_true")
    ap.add_argument("--skip-river-relative", action="store_true")
    ap.add_argument("--train-strategy-version")
    ap.add_argument("--val-strategy-version")
    ap.add_argument("--train-experiment-flag", action="append", default=[])
    ap.add_argument("--val-experiment-flag", action="append", default=[])
    args = ap.parse_args()

    player_profiles: dict[str, dict[str, float]] = {}
    if args.equity_player_profile_json is not None:
        profile_path = args.equity_player_profile_json
        if profile_path.exists():
            player_profiles = _load_player_profiles(profile_path)

    raw_train_rows = _load_rows(args.train_rows)
    raw_val_rows = _load_rows(args.val_rows)
    train_flag_filter = parse_flag_filters(args.train_experiment_flag)
    val_flag_filter = parse_flag_filters(args.val_experiment_flag)
    train_rows = limit_rows(
        filter_rows_by_meta(
            raw_train_rows,
            strategy_version=args.train_strategy_version,
            experiment_flags=train_flag_filter,
        ),
        args.max_train_rows,
    )
    val_rows = limit_rows(
        filter_rows_by_meta(
            raw_val_rows,
            strategy_version=args.val_strategy_version,
            experiment_flags=val_flag_filter,
        ),
        args.max_val_rows,
    )
    report: dict[str, Any] = {
        "meta": {
            "train_rows": len(train_rows),
            "val_rows": len(val_rows),
            "row_filters": {
                "train_strategy_version": args.train_strategy_version,
                "val_strategy_version": args.val_strategy_version,
                "train_experiment_flags": train_flag_filter,
                "val_experiment_flags": val_flag_filter,
            },
            "data_meta_before_filter": {
                "train": meta_summary(raw_train_rows),
                "val": meta_summary(raw_val_rows),
            },
            "data_meta": {
                "train": meta_summary(train_rows),
                "val": meta_summary(val_rows),
            },
            "n_estimators": args.n_estimators,
            "learning_rate": args.learning_rate,
            "num_leaves": args.num_leaves,
            "min_child_samples": args.min_child_samples,
            "reg_lambda": args.reg_lambda,
            "bucket_strong_nuts_weight": args.bucket_strong_nuts_weight,
            "min_bucket_nll_gain": args.min_bucket_nll_gain,
            "max_strong_nuts_under_worsen_pp": args.max_strong_nuts_under_worsen_pp,
            "max_strong_nuts_combo_under_worsen_pp": args.max_strong_nuts_combo_under_worsen_pp,
            "equity_high_actual_weight": args.equity_high_actual_weight,
            "equity_low_actual_weight": args.equity_low_actual_weight,
            "equity_residual": args.equity_residual,
            "equity_hand_weight": args.equity_hand_weight,
            "equity_relative_features": args.equity_relative_features,
            "equity_context_features": args.equity_context_features,
            "equity_player_profile_json": (
                str(args.equity_player_profile_json)
                if args.equity_player_profile_json is not None else ""
            ),
            "equity_player_profile_count": len(player_profiles),
            "min_equity_mae_gain_pp": args.min_equity_mae_gain_pp,
            "max_high_actual_under_worsen_pp": args.max_high_actual_under_worsen_pp,
            "max_low_actual_over_worsen_pp": args.max_low_actual_over_worsen_pp,
            "include_player": args.include_player,
        }
    }

    if not args.skip_bucket:
        streets = {s.strip() for s in args.bucket_streets.split(",") if s.strip()}
        tr = _bucket_rows(train_rows, streets)
        va = _bucket_rows(val_rows, streets)
        if tr and va:
            vec = DictVectorizer(sparse=True)
            x_tr = vec.fit_transform([_features(r, include_player=args.include_player) for r in tr])
            x_va = vec.transform([_features(r, include_player=args.include_player) for r in va])
            y_tr = np.array([_label_idx(r) for r in tr], dtype=np.int64)
            clf = LGBMClassifier(
                objective="multiclass",
                num_class=len(CAT_ORDER),
                n_estimators=args.n_estimators,
                learning_rate=args.learning_rate,
                num_leaves=args.num_leaves,
                min_child_samples=args.min_child_samples,
                reg_lambda=args.reg_lambda,
                subsample=0.9,
                colsample_bytree=0.9,
                n_jobs=1,
                random_state=42,
                verbose=-1,
            )
            fit_kwargs: dict[str, Any] = {}
            if args.bucket_strong_nuts_weight > 1.0:
                weights = np.ones(len(y_tr), dtype=np.float64)
                sn_mask = (
                    (y_tr == CAT_IDX["strong"]) | (y_tr == CAT_IDX["nuts"])
                )
                weights[sn_mask] = float(args.bucket_strong_nuts_weight)
                fit_kwargs["sample_weight"] = weights
            clf.fit(x_tr, y_tr, **fit_kwargs)
            raw_tr = np.vstack([_bucket_vec(r) for r in tr])
            raw_va = np.vstack([_bucket_vec(r) for r in va])
            lgb_tr = _full_class_proba(clf, clf.predict_proba(x_tr))
            lgb_va = _full_class_proba(clf, clf.predict_proba(x_va))
            raw_val_m = _bucket_metrics(va, raw_va)
            lgb_val_m = _bucket_metrics(va, lgb_va)
            val_risk = _bucket_risk_summary(raw_val_m, lgb_val_m)
            val_nll_gain = round(raw_val_m["nll"] - lgb_val_m["nll"], 5)
            selected = _select_bucket_blend(
                va,
                raw_va,
                lgb_va,
                min_bucket_nll_gain=args.min_bucket_nll_gain,
                max_strong_nuts_under_worsen_pp=args.max_strong_nuts_under_worsen_pp,
                max_strong_nuts_combo_under_worsen_pp=args.max_strong_nuts_combo_under_worsen_pp,
            )
            runtime_usable = bool(selected["usable"])
            if args.bucket_model_out is not None:
                _write_json(args.bucket_model_out, {
                    "type": "bucket_lgbm_calibration",
                    "cat_order": list(CAT_ORDER),
                    "feature_names": list(vec.feature_names_),
                    "classes": [int(c) for c in clf.classes_],
                    "blend_alpha": selected["alpha"],
                    "runtime_usable": runtime_usable,
                    "model_str": clf.booster_.model_to_string(),
                    "selected_blend": selected,
                })
            report["bucket"] = {
                "features": len(vec.feature_names_),
                "train_raw": _bucket_metrics(tr, raw_tr),
                "train_lgbm": _bucket_metrics(tr, lgb_tr),
                "val_raw": raw_val_m,
                "val_lgbm": lgb_val_m,
                "val_nll_gain": val_nll_gain,
                "val_brier_gain": round(
                    raw_val_m["brier"] - lgb_val_m["brier"],
                    5,
                ),
                "val_risk": val_risk,
                "selected_blend": selected,
                "runtime_usable": runtime_usable,
                "usable_gate": {
                    "min_bucket_nll_gain": args.min_bucket_nll_gain,
                    "max_strong_nuts_under_worsen_pp": args.max_strong_nuts_under_worsen_pp,
                    "max_strong_nuts_combo_under_worsen_pp": args.max_strong_nuts_combo_under_worsen_pp,
                },
            }
        else:
            report["bucket"] = {"error": "no bucket rows after filtering"}

    if not args.skip_equity:
        tr_items = _equity_items(train_rows, args.equity_target)
        va_items = _equity_items(val_rows, args.equity_target)
        if tr_items and va_items:
            train_args = {
                "n_estimators": args.n_estimators,
                "learning_rate": args.learning_rate,
                "num_leaves": args.num_leaves,
                "min_child_samples": args.min_child_samples,
                "reg_lambda": args.reg_lambda,
                "equity_high_actual_weight": args.equity_high_actual_weight,
                "equity_low_actual_weight": args.equity_low_actual_weight,
                "min_equity_mae_gain_pp": args.min_equity_mae_gain_pp,
                "max_high_actual_under_worsen_pp": args.max_high_actual_under_worsen_pp,
                "max_low_actual_over_worsen_pp": args.max_low_actual_over_worsen_pp,
                "include_player": args.include_player,
                "row_filters": report["meta"]["row_filters"],
                "equity_by_street": args.equity_by_street,
                "equity_residual": args.equity_residual,
                "equity_hand_weight": args.equity_hand_weight,
                "equity_relative_features": args.equity_relative_features,
                "equity_context_features": args.equity_context_features,
                "equity_player_profile_json": (
                    str(args.equity_player_profile_json)
                    if args.equity_player_profile_json is not None else ""
                ),
                "equity_player_profile_count": len(player_profiles),
            }
            if args.equity_by_street:
                by_street: dict[str, Any] = {}
                models_by_street: dict[str, Any] = {}
                all_items: list[tuple[dict[str, Any], float, float]] = []
                all_raw: list[np.ndarray] = []
                all_lgbm: list[np.ndarray] = []
                all_selected: list[np.ndarray] = []
                for street in ("preflop", "flop", "turn", "river"):
                    tr_s = [
                        item for item in tr_items
                        if str(item[0].get("street") or "") == street
                    ]
                    va_s = [
                        item for item in va_items
                        if str(item[0].get("street") or "") == street
                    ]
                    if not tr_s or not va_s:
                        by_street[street] = {"error": "no equity rows after filtering"}
                        continue
                    rep_s, model_s, raw_s, pred_s, selected_s = _fit_equity_lgbm_model(
                        tr_s,
                        va_s,
                        args=args,
                        include_relative=args.equity_relative_features,
                        include_context=args.equity_context_features,
                        player_profiles=player_profiles,
                        random_state=43 + len(by_street),
                    )
                    by_street[street] = rep_s
                    models_by_street[street] = model_s
                    all_items.extend(va_s)
                    all_raw.append(raw_s)
                    all_lgbm.append(pred_s)
                    all_selected.append(selected_s)
                if all_items:
                    raw_all = np.concatenate(all_raw)
                    lgbm_all = np.concatenate(all_lgbm)
                    selected_all = np.concatenate(all_selected)
                    raw_m = _equity_metrics(all_items, raw_all)
                    lgbm_m = _equity_metrics(all_items, lgbm_all)
                    selected_m = _equity_metrics(all_items, selected_all)
                    selected = {
                        "alpha": "by_street",
                        "metrics": selected_m,
                        "risk": _equity_risk_summary(raw_m, selected_m),
                        "mae_gain_pp": round(raw_m["mae_pp"] - selected_m["mae_pp"], 3),
                        "usable": any(
                            bool(m.get("runtime_usable"))
                            for m in models_by_street.values()
                        ),
                    }
                    report["equity"] = {
                        "type": "equity_lgbm_calibration_by_street",
                        "by_street": by_street,
                        "val_raw": raw_m,
                        "val_lgbm": lgbm_m,
                        "val_mae_gain_pp": round(raw_m["mae_pp"] - lgbm_m["mae_pp"], 3),
                        "val_ece_gain_pp": round(raw_m["ece_pp"] - lgbm_m["ece_pp"], 3),
                        "val_risk": _equity_risk_summary(raw_m, lgbm_m),
                        "selected_blend": selected,
                        "runtime_usable": bool(selected["usable"]),
                        "usable_gate": {
                            "min_mae_gain_pp": args.min_equity_mae_gain_pp,
                            "max_high_actual_under_worsen_pp": args.max_high_actual_under_worsen_pp,
                            "max_low_actual_over_worsen_pp": args.max_low_actual_over_worsen_pp,
                        },
                    }
                    if args.equity_model_out is not None:
                        _write_json(args.equity_model_out, {
                            "type": "equity_lgbm_calibration_by_street",
                            "feature_version": "range_v2_equity_lgbm_by_street_v2",
                            "equity_target": args.equity_target,
                            "runtime_usable": bool(selected["usable"]),
                            "models_by_street": models_by_street,
                            "selected_blend": selected,
                            "metrics": {
                                "val_raw": raw_m,
                                "val_lgbm": lgbm_m,
                                "val_selected": selected_m,
                                "val_mae_gain_pp": report["equity"]["val_mae_gain_pp"],
                                "val_selected_mae_gain_pp": selected["mae_gain_pp"],
                                "val_ece_gain_pp": report["equity"]["val_ece_gain_pp"],
                                "val_risk": report["equity"]["val_risk"],
                                "by_street": by_street,
                            },
                            "train_args": train_args,
                        })
                else:
                    report["equity"] = {"error": "no equity rows after filtering"}
            else:
                eq_report, eq_model, _raw_va, _pred_va, _selected_va = _fit_equity_lgbm_model(
                    tr_items,
                    va_items,
                    args=args,
                    include_relative=args.equity_relative_features,
                    include_context=args.equity_context_features,
                    player_profiles=player_profiles,
                    random_state=43,
                )
                report["equity"] = eq_report
                if args.equity_model_out is not None:
                    _write_json(args.equity_model_out, {
                        "type": "equity_lgbm_calibration",
                        "feature_version": "range_v2_equity_lgbm_v2",
                        "equity_target": args.equity_target,
                        **eq_model,
                        "train_args": train_args,
                    })
        else:
            report["equity"] = {"error": "no equity rows after filtering"}

    if not args.skip_river_relative:
        tr_items = _relative_items(train_rows)
        va_items = _relative_items(val_rows)
        if tr_items and va_items:
            vec = DictVectorizer(sparse=True)
            x_tr = vec.fit_transform([
                _features(
                    row,
                    pred,
                    include_player=args.include_player,
                    include_relative=True,
                    include_context=args.equity_context_features,
                    player_profiles=player_profiles,
                )
                for row, pred, _actual in tr_items
            ])
            x_va = vec.transform([
                _features(
                    row,
                    pred,
                    include_player=args.include_player,
                    include_relative=True,
                    include_context=args.equity_context_features,
                    player_profiles=player_profiles,
                )
                for row, pred, _actual in va_items
            ])
            y_tr = np.array([actual for _row, _pred, actual in tr_items], dtype=np.float64)
            raw_tr = np.array([pred for _row, pred, _actual in tr_items], dtype=np.float64)
            raw_va = np.array([pred for _row, pred, _actual in va_items], dtype=np.float64)
            reg = LGBMRegressor(
                objective="regression",
                n_estimators=args.n_estimators,
                learning_rate=args.learning_rate,
                num_leaves=args.num_leaves,
                min_child_samples=args.min_child_samples,
                reg_lambda=args.reg_lambda,
                subsample=0.9,
                colsample_bytree=0.9,
                n_jobs=1,
                random_state=44,
                verbose=-1,
            )
            fit_kwargs = {}
            if args.equity_high_actual_weight > 1.0 or args.equity_low_actual_weight > 1.0:
                weights = np.ones(len(y_tr), dtype=np.float64)
                if args.equity_high_actual_weight > 1.0:
                    weights[y_tr >= 0.75] = float(args.equity_high_actual_weight)
                if args.equity_low_actual_weight > 1.0:
                    weights[y_tr <= 0.25] = np.maximum(
                        weights[y_tr <= 0.25],
                        float(args.equity_low_actual_weight),
                    )
                fit_kwargs["sample_weight"] = weights
            reg.fit(x_tr, y_tr, **fit_kwargs)
            pred_tr = np.clip(reg.predict(x_tr), 0.0, 1.0)
            pred_va = np.clip(reg.predict(x_va), 0.0, 1.0)
            raw_val_m = _equity_metrics(va_items, raw_va)
            lgb_val_m = _equity_metrics(va_items, pred_va)
            val_risk = _equity_risk_summary(raw_val_m, lgb_val_m)
            val_mae_gain_pp = round(raw_val_m["mae_pp"] - lgb_val_m["mae_pp"], 3)
            selected = _select_equity_blend(
                va_items,
                raw_va,
                pred_va,
                min_mae_gain_pp=args.min_equity_mae_gain_pp,
                max_high_actual_under_worsen_pp=args.max_high_actual_under_worsen_pp,
                max_low_actual_over_worsen_pp=args.max_low_actual_over_worsen_pp,
            )
            runtime_usable = bool(selected["usable"])
            report["river_relative"] = {
                "features": len(vec.feature_names_),
                "train_raw": _equity_metrics(tr_items, raw_tr),
                "train_lgbm": _equity_metrics(tr_items, pred_tr),
                "val_raw": raw_val_m,
                "val_lgbm": lgb_val_m,
                "val_mae_gain_pp": val_mae_gain_pp,
                "val_ece_gain_pp": round(raw_val_m["ece_pp"] - lgb_val_m["ece_pp"], 3),
                "val_risk": val_risk,
                "selected_blend": selected,
                "runtime_usable": runtime_usable,
                "usable_gate": {
                    "min_mae_gain_pp": args.min_equity_mae_gain_pp,
                    "max_high_actual_under_worsen_pp": args.max_high_actual_under_worsen_pp,
                    "max_low_actual_over_worsen_pp": args.max_low_actual_over_worsen_pp,
                },
            }
        else:
            report["river_relative"] = {"error": "no river relative rows after filtering"}

    _write_json(args.report_out, report)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
