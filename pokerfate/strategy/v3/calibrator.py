"""Size calibrator — doc 03 §8.

Apply physical / range constraints to a purpose-suggested `frac` and emit
the final bet amount.

Order (doc 03 §8):
  1. geometric cap (防透支后续街)
  2. multiway cap
  3. texture penalty
  4. street hard cap
  5. physical clamp (min_bet, stack)
"""

from __future__ import annotations

from dataclasses import dataclass

from pokerfate.strategy.v3.context import DecisionCtx


_STREET_HARD_CAP = {'flop': 0.80, 'turn': 1.30, 'river': 2.00}
_LOW_SPR_GEO_BYPASS_STACK_FRAC = 0.35
_VALUE_PROTECTION_PURPOSES = {
    'range_cbet',
    'protection_bet',
    'thin_value_bet',
    'thick_value_bet',
    'delayed_cbet',
    'probe_bet',
    'float_bet',
    'turn_donk',
    'double_barrel',
}
_SMART_VALUE_PURPOSES = {
    'thick_value_bet',
    'monster_value_plan',
    'overbet_value',
}


def _geo_cap(spr: float, street: str) -> float:
    if street == 'river' or spr <= 0:
        return 99.0
    streets_left = {'flop': 3, 'turn': 2, 'river': 1}.get(street, 1)
    ratio = 1.0 + 2.0 * spr
    base = (ratio ** (1.0 / streets_left) - 1.0) / 2.0
    return base * 1.1   # 1.1 buffer


def _effective_bet_stack(ctx: DecisionCtx) -> float:
    """Stack used for commitment sizing.

    ``ctx.stack`` is hero's own physical maximum. ``ctx.effective_stack`` is
    the stack that produced SPR and represents the current sizing target.  Use
    the smaller positive value for jam thresholds so a deep hero can still put
    a short target all-in instead of having the bet compressed by geo cap.
    """
    hero_stack = max(0.0, float(ctx.stack or 0.0))
    effective = max(0.0, float(getattr(ctx, 'effective_stack', 0.0) or 0.0))
    if hero_stack > 0 and effective > 0:
        return min(hero_stack, effective)
    return hero_stack or effective


def _dangerous_non_nut_value_spot(ctx: DecisionCtx) -> bool:
    if ctx.hero_bucket == 'nuts':
        return False
    if ctx.board_sig.flush_possible and not ctx.blockers.nut_flush_blocker:
        return True
    if ctx.board_sig.straight_possible and ctx.hero_hand_rank not in {'straight', 'flush', 'full_house'}:
        return True
    if ctx.board_sig.paired and ctx.hero_made_subtype in {
        'board_pair_hero_pair',
        'board_pair_kicker',
        'board_two_pair',
        'trips_weak_kicker',
        'board_trips_kicker',
        'board_pair_pocket_underpair',
    }:
        return True
    return False


def _payment_target(ctx: DecisionCtx) -> bool:
    vs = ctx.villain_stats
    if ctx.prev_bet_called_count > 0 or ctx.prev_bet_raised:
        return True
    if ctx.n_sticky >= 1:
        return True
    if vs.vpip >= 0.45:
        return True
    if vs.hands_seen >= 20 and (vs.wtsd >= 0.32 or vs.af <= 1.1):
        return True
    if vs.fold_to_cbet_opps >= 5 and vs.fold_to_cbet <= 0.35:
        return True
    if vs.river_action_count >= 5 and vs.river_fold_rate <= 0.35:
        return True
    return False


def _smart_value_min_frac(ctx: DecisionCtx, purpose_id: str, raw_frac: float) -> float:
    if purpose_id not in _SMART_VALUE_PURPOSES:
        return 0.0
    if raw_frac < 0.75:
        return 0.0
    if ctx.hero_bucket not in {'strong', 'nuts'}:
        return 0.0
    if _dangerous_non_nut_value_spot(ctx):
        return 0.0
    if not _payment_target(ctx):
        return 0.0
    return 0.75


@dataclass
class CalibrateResult:
    frac: float        # final pot fraction after all caps (0 if invalid)
    amount: float      # concrete bet amount in chips
    jammed: bool       # True if the final amount naturally consumes stack


def calibrate(
    frac: float,
    ctx: DecisionCtx,
    purpose_id: str = '',
) -> CalibrateResult:
    """Apply calibration to a pot-fraction proposal."""
    if frac <= 0 or ctx.pot <= 0:
        return CalibrateResult(0.0, 0.0, False)

    # 0. Raw amount is used only for geometric-cap bypass. There is no
    # automatic ">= X% stack => all-in" conversion; a bet becomes all-in only
    # when the requested amount physically exceeds hero's stack.
    raw_amount = frac * ctx.pot
    bet_stack = _effective_bet_stack(ctx)
    value_floor = _smart_value_min_frac(ctx, purpose_id, frac)

    # 1. Geometric cap (except river — river allows overbet freely)
    geo = _geo_cap(ctx.spr, ctx.street)
    # If the original strategy size already commits a meaningful part of the
    # effective stack, do not shrink it into a tiny low-SPR geometric size.
    # This is strategy-agnostic: the purpose's own sizer decides the intended
    # dose; geo cap should only preserve future-street geometry, not undo an
    # already committed sizing request.
    bypass_geo = (
        bet_stack > 0
        and raw_amount >= bet_stack * _LOW_SPR_GEO_BYPASS_STACK_FRAC
    )
    if ctx.street != 'river' and not bypass_geo:
        frac = min(frac, geo)

    if purpose_id == 'value_jam':
        amount = min(max(0.0, float(ctx.stack or 0.0)), frac * ctx.pot)
        amount = min(amount, ctx.stack)
        eff_frac = (amount / ctx.pot) if ctx.pot > 0 else 0.0
        return CalibrateResult(eff_frac, amount, bool(ctx.stack > 0 and amount >= ctx.stack))

    # 2. Multiway cap (overbet_value exempt)
    # Sticky 多人池不再一律压小 value/protection。粘手对手会支付更差牌；
    # 只有危险非坚果 spot 或非 value/protection 下注继续收紧到 0.50。
    if ctx.num_opponents >= 2 and purpose_id != 'overbet_value':
        value_protection = purpose_id in _VALUE_PROTECTION_PURPOSES
        dangerous = _dangerous_non_nut_value_spot(ctx)
        if ctx.hero_bucket == 'nuts':
            frac = min(frac, 1.00)
        elif ctx.hero_bucket == 'strong':
            if value_protection and not dangerous:
                frac = min(frac, 0.75 if ctx.n_sticky >= 1 else 0.80)
            else:
                frac = min(frac, 0.50 if ctx.n_sticky >= 1 else 0.80)
        else:
            if value_protection and not dangerous:
                frac = min(frac, 0.66)
            else:
                frac = min(frac, 0.50 if ctx.n_sticky >= 1 else 0.66)

    # 3. Texture penalty (non-overbet purposes)
    if purpose_id != 'overbet_value':
        if ctx.board_sig.flush_possible and ctx.hero_bucket != 'nuts':
            frac = min(frac, 0.75)
        if ctx.board_sig.wetness > 0.8 and ctx.hero_bucket in ('medium', 'strong'):
            value_protection = purpose_id in _VALUE_PROTECTION_PURPOSES
            safer_value = (
                value_protection
                and ctx.hero_bucket == 'strong'
                and ctx.equity_range >= 0.70
                and not _dangerous_non_nut_value_spot(ctx)
            )
            frac = min(frac, 0.75 if safer_value else 0.66)

    if value_floor > 0:
        frac = max(frac, value_floor)

    # 4. Street hard cap
    frac = min(frac, _STREET_HARD_CAP.get(ctx.street, 2.00))

    # 5. Physical clamp
    amount = max(frac * ctx.pot, ctx.big_blind)
    amount = min(amount, ctx.stack)

    # 6. Mark natural all-in after physical clamp. This is not a sizing
    # escalation; it only records that the chosen size consumed the stack.
    jammed = bool(ctx.stack > 0 and amount >= ctx.stack)

    # Recover the effective frac actually in use (may differ from input)
    eff_frac = (amount / ctx.pot) if ctx.pot > 0 else 0.0
    return CalibrateResult(eff_frac, amount, jammed)
