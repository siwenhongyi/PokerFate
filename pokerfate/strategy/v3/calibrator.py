"""Size calibrator — doc 03 §8.

Apply physical / range constraints to a purpose-suggested `frac` and emit
the final bet amount.

Order (doc 03 §8):
  1. geometric cap (防透支后续街)
  2. multiway cap
  3. texture penalty
  4. street hard cap
  5. physical clamp (min_bet, stack)
  6. jam round-up (bet ≥ 60% stack → all-in)
"""

from __future__ import annotations

import os as _os
from dataclasses import dataclass

from pokerfate.strategy.v3.context import DecisionCtx


_STREET_HARD_CAP = {'flop': 0.80, 'turn': 1.30, 'river': 2.00}
_JAM_ROUNDUP_STACK_FRAC = float(_os.environ.get('PF_JAM_ROUNDUP_STACK_FRAC', '0.60'))
_JAM_ROUNDUP_DANGER_FRAC = float(_os.environ.get('PF_JAM_ROUNDUP_DANGER_FRAC', '0.80'))
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


def _geo_cap(spr: float, street: str) -> float:
    if street == 'river' or spr <= 0:
        return 99.0
    streets_left = {'flop': 3, 'turn': 2, 'river': 1}.get(street, 1)
    ratio = 1.0 + 2.0 * spr
    base = (ratio ** (1.0 / streets_left) - 1.0) / 2.0
    return base * 1.1   # 1.1 buffer


def _jam_roundup_threshold(ctx: DecisionCtx) -> float:
    if ctx.street == 'river' and (ctx.board_sig.paired or ctx.board_sig.flush_possible
                                  or ctx.board_sig.straight_possible):
        return _JAM_ROUNDUP_DANGER_FRAC
    return _JAM_ROUNDUP_STACK_FRAC


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


@dataclass
class CalibrateResult:
    frac: float        # final pot fraction after all caps (0 if invalid)
    amount: float      # concrete bet amount in chips
    jammed: bool       # True if jam round-up fired


def calibrate(frac: float, ctx: DecisionCtx, purpose_id: str = '') -> CalibrateResult:
    """Apply calibration to a pot-fraction proposal."""
    if frac <= 0 or ctx.pot <= 0:
        return CalibrateResult(0.0, 0.0, False)

    # 0. Pre-check jam round-up: if the *raw* sizer proposal would already
    # bet ≥ 60% of stack, commit directly. Running this BEFORE the geometric
    # cap matters at low SPR — otherwise the geo cap compresses the bet to
    # an awkward mid-bet below the jam threshold (and we lose commitment EV).
    raw_amount = frac * ctx.pot
    jam_threshold = _jam_roundup_threshold(ctx)
    bet_stack = _effective_bet_stack(ctx)
    if bet_stack > 0 and raw_amount >= bet_stack * jam_threshold:
        amount = min(bet_stack, max(0.0, float(ctx.stack or bet_stack)))
        eff = amount / ctx.pot if ctx.pot > 0 else 0.0
        return CalibrateResult(eff, amount, True)

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

    # 2. Multiway cap (overbet_value / value_jam exempt)
    # Sticky 多人池不再一律压小 value/protection。粘手对手会支付更差牌；
    # 只有危险非坚果 spot 或非 value/protection 下注继续收紧到 0.50。
    if ctx.num_opponents >= 2 and purpose_id not in ('overbet_value', 'value_jam'):
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

    # 4. Street hard cap
    frac = min(frac, _STREET_HARD_CAP.get(ctx.street, 2.00))

    # 5. Physical clamp
    amount = max(frac * ctx.pot, ctx.big_blind)
    amount = min(amount, ctx.stack)

    # 6. Jam round-up (doc 03 §8 step 6)
    jammed = False
    if bet_stack > 0 and amount >= bet_stack * jam_threshold:
        amount = min(bet_stack, max(0.0, float(ctx.stack or bet_stack)))
        jammed = True

    # Recover the effective frac actually in use (may differ from input)
    eff_frac = (amount / ctx.pot) if ctx.pot > 0 else 0.0
    return CalibrateResult(eff_frac, amount, jammed)
