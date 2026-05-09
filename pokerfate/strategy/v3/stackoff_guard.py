"""Shared reverse-implied-odds guard for non-nut stack-off spots."""

from __future__ import annotations

import os as _os
from typing import Optional

from pokerfate.strategy.v3.context import DecisionCtx

_MODE = _os.environ.get('PF_STACKOFF_GUARD_MODE', 'paired_only').strip().lower()
_NON_NUT_TRIPS_RAISE_MAX_EQ = float(
    _os.environ.get('PF_NON_NUT_TRIPS_RAISE_MAX_EQ', '0.86')
)
_NON_NUT_TRIPS_MIN_KICKER = int(
    float(_os.environ.get('PF_NON_NUT_TRIPS_MIN_KICKER', '12'))
)
_PAIRED_UNDERPAIR_VALUE_JAM_MAX_EQ = float(
    _os.environ.get('PF_PAIRED_UNDERPAIR_VALUE_JAM_MAX_EQ', '0.85')
)
_PAIRED_UNDERPAIR_EARLY_VALUE_JAM_MAX_EQ = float(
    _os.environ.get('PF_PAIRED_UNDERPAIR_EARLY_VALUE_JAM_MAX_EQ', '0.75')
)
_RIVER_VALUE_JAM_MIN_WORSE_CALL = float(
    _os.environ.get('PF_RIVER_VALUE_JAM_MIN_WORSE_CALL', '0.20')
)
_RIVER_RAISE_MAX_VILLAIN_NUTS = float(
    _os.environ.get('PF_RIVER_RAISE_MAX_VILLAIN_NUTS', '0.35')
)
_PAIRED_BOARD_SPR_MAX = float(
    _os.environ.get('PF_STACKOFF_PAIRED_BOARD_SPR_MAX', '2.8')
)

_STACKOFF_PURPOSES = {
    'value_jam',
    'value_raise',
    'overbet_raise_jam',
    'thick_value_bet',
    'overbet_value',
}
_TRIPS_SUBTYPES = {
    'trips_weak_kicker',
    'trips_top_kicker',
    'board_trips_kicker',
    'trips',
}
_BOARD_PAIR_TWO_PAIR_SUBTYPES = {'board_pair_pocket_underpair'}


def stackoff_guard_enabled() -> bool:
    return _MODE not in {'0', 'off', 'none', 'false'}


def _villain_nuts(ctx: DecisionCtx) -> float:
    return float((ctx.villain_bucket_dist or {}).get('nuts', 0.0) or 0.0)


def _worse_call_mass(ctx: DecisionCtx) -> float:
    dist = ctx.villain_bucket_dist or {}
    return float(
        (dist.get('strong', 0.0) or 0.0)
        + (dist.get('medium', 0.0) or 0.0)
        + 0.5 * (dist.get('draw', 0.0) or 0.0)
    )


def _is_stackoff_node(ctx: DecisionCtx, purpose_id: str, will_jam: bool) -> bool:
    if purpose_id not in _STACKOFF_PURPOSES:
        return False
    if purpose_id in {'value_jam', 'overbet_raise_jam'}:
        return True
    if purpose_id == 'value_raise' and (will_jam or ctx.spr <= 2.0):
        return True
    if purpose_id in {'thick_value_bet', 'overbet_value'} and will_jam:
        return True
    return False


def stackoff_guard_reason(
    ctx: DecisionCtx,
    purpose_id: str,
    *,
    will_jam: bool = False,
) -> Optional[str]:
    """Return a compact block reason, or None if stack-off is allowed."""
    if not stackoff_guard_enabled():
        return None
    if not _is_stackoff_node(ctx, purpose_id, will_jam):
        return None
    if ctx.hero_made_subtype == 'full_house_plus':
        return None
    if _MODE == 'paired_only' and not ctx.board_sig.paired:
        return None
    if _MODE == 'river_only' and ctx.street != 'river':
        return None
    if ctx.board_sig.paired and 0 < ctx.spr > _PAIRED_BOARD_SPR_MAX:
        return None

    subtype = ctx.hero_made_subtype or 'unknown'
    nuts = _villain_nuts(ctx)

    if (
        ctx.street == 'river'
        and subtype in _TRIPS_SUBTYPES
        and purpose_id in {'value_raise', 'overbet_raise_jam'}
    ):
        kicker_too_low = ctx.hero_kicker_rank and ctx.hero_kicker_rank < _NON_NUT_TRIPS_MIN_KICKER
        eq_not_enough = ctx.equity_range < _NON_NUT_TRIPS_RAISE_MAX_EQ
        nuts_too_high = nuts > _RIVER_RAISE_MAX_VILLAIN_NUTS
        if kicker_too_low or eq_not_enough or nuts_too_high:
            bits = []
            if kicker_too_low:
                bits.append(f"k{ctx.hero_kicker_rank}<{_NON_NUT_TRIPS_MIN_KICKER}")
            if eq_not_enough:
                bits.append(f"eq{ctx.equity_range:.2f}<{_NON_NUT_TRIPS_RAISE_MAX_EQ:.2f}")
            if nuts_too_high:
                bits.append(f"nuts{nuts:.2f}>{_RIVER_RAISE_MAX_VILLAIN_NUTS:.2f}")
            return 'non_nut_trips:' + ','.join(bits)

    if ctx.board_sig.paired and subtype in _BOARD_PAIR_TWO_PAIR_SUBTYPES:
        worse_call = _worse_call_mass(ctx)
        low_worse_call = ctx.street == 'river' and worse_call < _RIVER_VALUE_JAM_MIN_WORSE_CALL
        eq_cap = (
            _PAIRED_UNDERPAIR_VALUE_JAM_MAX_EQ
            if ctx.street == 'river'
            else min(_PAIRED_UNDERPAIR_VALUE_JAM_MAX_EQ, _PAIRED_UNDERPAIR_EARLY_VALUE_JAM_MAX_EQ)
        )
        eq_not_enough = ctx.equity_range < eq_cap
        if low_worse_call or eq_not_enough:
            bits = [subtype]
            if eq_not_enough:
                bits.append(f"eq{ctx.equity_range:.2f}<{eq_cap:.2f}")
            if low_worse_call:
                bits.append(f"wcall{worse_call:.2f}<{_RIVER_VALUE_JAM_MIN_WORSE_CALL:.2f}")
            return 'paired_two_pair:' + ','.join(bits)

    return None


def stackoff_guard_params() -> str:
    return (
        f"mode={_MODE} trips_eq={_NON_NUT_TRIPS_RAISE_MAX_EQ:.2f} "
        f"trips_k={_NON_NUT_TRIPS_MIN_KICKER} pair_eq={_PAIRED_UNDERPAIR_VALUE_JAM_MAX_EQ:.2f} "
        f"pair_early={_PAIRED_UNDERPAIR_EARLY_VALUE_JAM_MAX_EQ:.2f} "
        f"wcall={_RIVER_VALUE_JAM_MIN_WORSE_CALL:.2f} nuts={_RIVER_RAISE_MAX_VILLAIN_NUTS:.2f} "
        f"spr={_PAIRED_BOARD_SPR_MAX:.1f}"
    )
