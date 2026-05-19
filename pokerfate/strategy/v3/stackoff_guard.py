"""Shared reverse-implied-odds guard for non-nut stack-off spots."""

from __future__ import annotations

import os as _os
from typing import Optional

from pokerfate.strategy.v3.context import DecisionCtx

_MODE = _os.environ.get('PF_STACKOFF_GUARD_MODE', 'texture').strip().lower()
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
_NON_FLUSH_STACKOFF_MIN_EQ = float(
    _os.environ.get('PF_NON_FLUSH_STACKOFF_MIN_EQ', '0.92')
)
_NON_FLUSH_STACKOFF_MAX_NUTS = float(
    _os.environ.get('PF_NON_FLUSH_STACKOFF_MAX_NUTS', '0.16')
)
_NON_FLUSH_STACKOFF_MAX_REL_LOSS = float(
    _os.environ.get('PF_NON_FLUSH_STACKOFF_MAX_REL_LOSS', '0.12')
)
_NON_FLUSH_STACKOFF_MIN_REL_WIN = float(
    _os.environ.get('PF_NON_FLUSH_STACKOFF_MIN_REL_WIN', '0.85')
)
_FOUR_STRAIGHT_FRAGILE_MIN_EQ = float(
    _os.environ.get('PF_FOUR_STRAIGHT_FRAGILE_MIN_EQ', '0.82')
)
_FOUR_STRAIGHT_MAX_NUTS = float(
    _os.environ.get('PF_FOUR_STRAIGHT_MAX_NUTS', '0.18')
)
_FOUR_STRAIGHT_MAX_REL_LOSS = float(
    _os.environ.get('PF_FOUR_STRAIGHT_MAX_REL_LOSS', '0.12')
)
_REL_CLEAR_MIN_WIN = float(
    _os.environ.get('PF_STACKOFF_REL_CLEAR_MIN_WIN', '0.72')
)
_REL_CLEAR_MIN_EDGE = float(
    _os.environ.get('PF_STACKOFF_REL_CLEAR_MIN_EDGE', '0.30')
)
_REL_CLEAR_MAX_LOSS = float(
    _os.environ.get('PF_STACKOFF_REL_CLEAR_MAX_LOSS', '0.18')
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
_BOARD_PAIR_TWO_PAIR_SUBTYPES = {
    'board_pair_pocket_underpair',
    'board_pair_hero_pair',
}
_FOUR_STRAIGHT_FRAGILE_SUBTYPES = {
    'clean_two_pair',
    'board_pair_hero_pair',
    'board_pair_pocket_underpair',
    'board_two_pair',
    'top_pair_weak_kicker',
    'top_pair_good_kicker',
    'clean_overpair',
    'set',
    'trips',
    'trips_weak_kicker',
    'trips_top_kicker',
}
_STRAIGHT_SEQUENCES = tuple(
    frozenset(seq)
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


def stackoff_guard_enabled() -> bool:
    return _MODE not in {'0', 'off', 'none', 'false'}


def _texture_guards_enabled() -> bool:
    return _MODE in {'1', 'on', 'true', 'all', 'full', 'texture', 'river_only'}


def _villain_nuts(ctx: DecisionCtx) -> float:
    return float((ctx.villain_bucket_dist or {}).get('nuts', 0.0) or 0.0)


def _villain_rel_loss(ctx: DecisionCtx) -> float:
    return float((ctx.villain_vs_hero_dist or {}).get('loss', 0.0) or 0.0)


def _hero_rel_win(ctx: DecisionCtx) -> float:
    return float((ctx.villain_vs_hero_dist or {}).get('win', 0.0) or 0.0)


def _worse_call_mass(ctx: DecisionCtx) -> float:
    dist = ctx.villain_bucket_dist or {}
    return float(
        (dist.get('strong', 0.0) or 0.0)
        + (dist.get('medium', 0.0) or 0.0)
        + 0.5 * (dist.get('draw', 0.0) or 0.0)
    )


def _relative_clear_value(ctx: DecisionCtx) -> bool:
    """True when the hero-relative range says this is still clear value.

    Bucket labels can overstate danger on coordinated boards. At stack-off
    nodes we still guard non-nut hands, but do not block value when the
    relative distribution says villain holds worse hands overwhelmingly.
    """
    rel = ctx.villain_vs_hero_dist or {}
    if not rel:
        return False
    win = float(rel.get('win', 0.0) or 0.0)
    loss = float(rel.get('loss', 0.0) or 0.0)
    return (
        win >= _REL_CLEAR_MIN_WIN
        and win - loss >= _REL_CLEAR_MIN_EDGE
        and loss <= _REL_CLEAR_MAX_LOSS
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


def _hero_is_flush_or_better(ctx: DecisionCtx) -> bool:
    return ctx.hero_hand_rank in {
        'flush',
        'full_house',
        'four_of_a_kind',
        'straight_flush',
        'royal_flush',
    }


def _board_four_to_straight(ctx: DecisionCtx) -> bool:
    ranks = {int(c.rank) for c in (ctx.board or [])}
    if len(ranks) < 4:
        return False
    return any(len(seq & ranks) >= 4 for seq in _STRAIGHT_SEQUENCES)


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
    rel_loss = _villain_rel_loss(ctx)
    if _relative_clear_value(ctx):
        return None

    if (
        _texture_guards_enabled()
        and ctx.street == 'river'
        and ctx.board_sig.flush_possible
        and not _hero_is_flush_or_better(ctx)
    ):
        rel_win = _hero_rel_win(ctx)
        has_rel = bool(ctx.villain_vs_hero_dist)
        eq_not_lock = (
            ctx.equity_range < _NON_FLUSH_STACKOFF_MIN_EQ
            and (not has_rel or rel_win < _NON_FLUSH_STACKOFF_MIN_REL_WIN)
        )
        nuts_too_high = nuts > _NON_FLUSH_STACKOFF_MAX_NUTS
        rel_loss_too_high = rel_loss > _NON_FLUSH_STACKOFF_MAX_REL_LOSS
        if eq_not_lock or nuts_too_high or rel_loss_too_high:
            bits = ['non_flush']
            if eq_not_lock:
                bits.append(f"eq{ctx.equity_range:.2f}<{_NON_FLUSH_STACKOFF_MIN_EQ:.2f}")
                if has_rel:
                    bits.append(f"win{rel_win:.2f}<{_NON_FLUSH_STACKOFF_MIN_REL_WIN:.2f}")
            if nuts_too_high:
                bits.append(f"nuts{nuts:.2f}>{_NON_FLUSH_STACKOFF_MAX_NUTS:.2f}")
            if rel_loss_too_high:
                bits.append(f"loss{rel_loss:.2f}>{_NON_FLUSH_STACKOFF_MAX_REL_LOSS:.2f}")
            return 'completed_flush:' + ','.join(bits)

    if (
        _texture_guards_enabled()
        and _board_four_to_straight(ctx)
        and subtype in _FOUR_STRAIGHT_FRAGILE_SUBTYPES
    ):
        eq_not_enough = ctx.equity_range < _FOUR_STRAIGHT_FRAGILE_MIN_EQ
        nuts_too_high = nuts > _FOUR_STRAIGHT_MAX_NUTS
        rel_loss_too_high = rel_loss > _FOUR_STRAIGHT_MAX_REL_LOSS
        if eq_not_enough or nuts_too_high or rel_loss_too_high:
            bits = [subtype]
            if eq_not_enough:
                bits.append(f"eq{ctx.equity_range:.2f}<{_FOUR_STRAIGHT_FRAGILE_MIN_EQ:.2f}")
            if nuts_too_high:
                bits.append(f"nuts{nuts:.2f}>{_FOUR_STRAIGHT_MAX_NUTS:.2f}")
            if rel_loss_too_high:
                bits.append(f"loss{rel_loss:.2f}>{_FOUR_STRAIGHT_MAX_REL_LOSS:.2f}")
            return 'four_straight:' + ','.join(bits)

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
        f"spr={_PAIRED_BOARD_SPR_MAX:.1f} "
        f"flush_eq={_NON_FLUSH_STACKOFF_MIN_EQ:.2f} flush_nuts={_NON_FLUSH_STACKOFF_MAX_NUTS:.2f} "
        f"flush_loss={_NON_FLUSH_STACKOFF_MAX_REL_LOSS:.2f} "
        f"4str_eq={_FOUR_STRAIGHT_FRAGILE_MIN_EQ:.2f} 4str_nuts={_FOUR_STRAIGHT_MAX_NUTS:.2f}"
    )
