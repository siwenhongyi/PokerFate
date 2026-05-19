"""Turn/flop relative-strength guardrails for high-leverage decisions.

This module is deliberately narrow and env-gated. It does not try to replace
equity/bucket modeling; it only raises the bar when a fragile made hand faces
or creates a commit-level decision on boards where relative strength dominates
linear equity.
"""

from __future__ import annotations

import os
from typing import List

from pokerfate.strategy.v3.context import DecisionCtx

ENABLED = os.environ.get("PF_TURN_FLOP_RELATIVE_GUARD", "0") == "1"

_MIN_RISK = float(os.environ.get("PF_TFR_MIN_RISK", "0.58"))
_CALL_MAX_ADD = float(os.environ.get("PF_TFR_CALL_MAX_ADD", "0.10"))
_CALL_BASE_ADD = float(os.environ.get("PF_TFR_CALL_BASE_ADD", "0.03"))
_VALUE_JAM_MAX_ADD = float(os.environ.get("PF_TFR_VALUE_JAM_MAX_ADD", "0.12"))
_VALUE_JAM_BASE_ADD = float(os.environ.get("PF_TFR_VALUE_JAM_BASE_ADD", "0.04"))
_FOLD_OVERRIDE_MIN_EDGE = float(os.environ.get("PF_TFR_FOLD_OVERRIDE_MIN_EDGE", "0.08"))

_FRAGILE_SUBTYPES = {
    "clean_overpair",
    "pocket_pair",
    "top_pair_weak_kicker",
    "board_pair_pocket_pair",
    "board_pair_pocket_underpair",
    "board_pair_hero_pair",
    "board_pair_kicker",
    "board_two_pair",
    "trips",
    "trips_top_kicker",
    "trips_weak_kicker",
    "board_trips_kicker",
}


def _rank_values(ctx: DecisionCtx) -> set[int]:
    ranks = {int(c.rank) for c in ctx.board}
    if 14 in ranks:
        ranks.add(1)
    return ranks


def _four_to_straight(ctx: DecisionCtx) -> bool:
    ranks = _rank_values(ctx)
    for start in range(1, 11):
        if len(set(range(start, start + 5)) & ranks) >= 4:
            return True
    return False


def _four_flush(ctx: DecisionCtx) -> bool:
    counts: dict[int, int] = {}
    for card in ctx.board:
        suit = int(card.suit)
        counts[suit] = counts.get(suit, 0) + 1
    return max(counts.values(), default=0) >= 4


def board_flags(ctx: DecisionCtx) -> List[str]:
    if ctx.street not in {"flop", "turn"} or len(ctx.board) < 3:
        return []
    flags: List[str] = []
    ranks = [int(c.rank) for c in ctx.board]
    flop = ctx.board[:3]
    flop_mono = len(flop) == 3 and len({int(c.suit) for c in flop}) == 1
    if ctx.board_sig.paired or len(set(ranks)) < len(ranks):
        flags.append("paired")
    if flop_mono:
        flags.append("mono")
    if _four_flush(ctx):
        flags.append("4flush")
    if _four_to_straight(ctx):
        flags.append("4straight")
    return flags


def fragile_made(ctx: DecisionCtx) -> bool:
    subtype = ctx.hero_made_subtype or ""
    if subtype in _FRAGILE_SUBTYPES:
        return True
    return subtype.startswith("board_pair_") and ctx.hero_bucket in {"medium", "strong"}


def _villain_strong_plus(ctx: DecisionCtx) -> float:
    dist = ctx.villain_bucket_dist or {}
    return float(dist.get("strong", 0.0) or 0.0) + float(dist.get("nuts", 0.0) or 0.0)


def _villain_nuts(ctx: DecisionCtx) -> float:
    return float((ctx.villain_bucket_dist or {}).get("nuts", 0.0) or 0.0)


def _bet_frac(ctx: DecisionCtx) -> float:
    if not ctx.facing_bet or ctx.to_call <= 0:
        return 0.0
    pot_before = max(1.0, float(ctx.pot) - float(ctx.to_call))
    return float(ctx.to_call) / pot_before


def _sticky_or_passive(ctx: DecisionCtx) -> bool:
    return ctx.n_sticky > 0 or ctx.villain_stats.af <= 1.0


def facing_guard_applies(ctx: DecisionCtx) -> bool:
    if not ENABLED or not ctx.facing_bet:
        return False
    if ctx.street not in {"flop", "turn"}:
        return False
    if not board_flags(ctx) or not fragile_made(ctx):
        return False
    bet_frac = _bet_frac(ctx)
    return bet_frac >= 0.65 or (_sticky_or_passive(ctx) and bet_frac >= 0.35)


def active_value_guard_applies(ctx: DecisionCtx) -> bool:
    if not ENABLED or ctx.facing_bet:
        return False
    if ctx.street not in {"flop", "turn"}:
        return False
    if not board_flags(ctx) or not fragile_made(ctx):
        return False
    if ctx.hero_bucket not in {"strong", "nuts"}:
        return False
    return (
        ctx.prev_bet_raised
        or ctx.prev_bet_called_count > 0
        or ctx.resistance_level >= 0.25
        or ctx.n_sticky > 0
    )


def risk_score(ctx: DecisionCtx, *, active_value: bool = False) -> float:
    if active_value:
        if not active_value_guard_applies(ctx):
            return 0.0
    elif not facing_guard_applies(ctx):
        return 0.0

    flags = board_flags(ctx)
    flag_pressure = min(1.0, len(flags) * 0.18)
    action_pressure = 0.0
    if ctx.facing_bet:
        bet_frac = _bet_frac(ctx)
        if bet_frac >= 0.65:
            action_pressure += 0.18
        if _sticky_or_passive(ctx):
            action_pressure += 0.12
    else:
        action_pressure += min(0.25, float(ctx.resistance_level or 0.0) * 0.30)
        if ctx.prev_bet_raised:
            action_pressure += 0.18
        if ctx.prev_bet_called_count > 0:
            action_pressure += min(0.12, 0.04 * ctx.prev_bet_called_count)
        if ctx.n_sticky > 0:
            action_pressure += 0.08

    risk = (
        0.45 * min(1.0, _villain_strong_plus(ctx))
        + 0.35 * min(1.0, _villain_nuts(ctx))
        + flag_pressure
        + action_pressure
    )
    return max(0.0, min(1.0, risk))


def call_margin_add(ctx: DecisionCtx) -> float:
    risk = risk_score(ctx)
    if risk < _MIN_RISK:
        return 0.0
    add = _CALL_BASE_ADD + max(0.0, risk - _MIN_RISK) * 0.22
    add += min(0.03, _villain_nuts(ctx) * 0.06)
    return min(_CALL_MAX_ADD, add)


def fold_override_need(ctx: DecisionCtx) -> float:
    add = call_margin_add(ctx)
    if add <= 0:
        return 0.0
    return ctx.pot_odds + max(add, _FOLD_OVERRIDE_MIN_EDGE)


def value_jam_eq_add(ctx: DecisionCtx) -> float:
    risk = risk_score(ctx, active_value=True)
    if risk < _MIN_RISK:
        return 0.0
    add = _VALUE_JAM_BASE_ADD + max(0.0, risk - _MIN_RISK) * 0.20
    add += min(0.03, _villain_nuts(ctx) * 0.06)
    return min(_VALUE_JAM_MAX_ADD, add)


def describe(ctx: DecisionCtx, *, active_value: bool = False) -> str:
    risk = risk_score(ctx, active_value=active_value)
    if risk <= 0:
        return ""
    flags = ",".join(board_flags(ctx))
    return (
        f"erel risk={risk:.2f} strong={_villain_strong_plus(ctx):.2f} "
        f"nuts={_villain_nuts(ctx):.2f} board={flags}"
    )
