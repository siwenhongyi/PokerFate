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
    if ctx.stack > 0 and raw_amount >= ctx.stack * jam_threshold:
        amount = ctx.stack
        eff = amount / ctx.pot if ctx.pot > 0 else 0.0
        return CalibrateResult(eff, amount, True)

    # 1. Geometric cap (except river — river allows overbet freely)
    geo = _geo_cap(ctx.spr, ctx.street)
    if ctx.street != 'river':
        frac = min(frac, geo)

    # 2. Multiway cap (overbet_value / value_jam exempt)
    # 2026-04-24 缺陷 A 第 1 步：n_sticky ≥ 1 时（桌上至少一个粘手对手）
    # strong/medium 桶的 value bet 被反向剥削风险显著更高——cap 从 0.80/0.66
    # 都压到 0.50。nuts 不收紧（坚果不怕被 raise，反而欢迎）。
    if ctx.num_opponents >= 2 and purpose_id not in ('overbet_value', 'value_jam'):
        if ctx.hero_bucket == 'nuts':
            frac = min(frac, 1.00)
        elif ctx.hero_bucket == 'strong':
            frac = min(frac, 0.50 if ctx.n_sticky >= 1 else 0.80)
        else:
            frac = min(frac, 0.50 if ctx.n_sticky >= 1 else 0.66)

    # 3. Texture penalty (non-overbet purposes)
    if purpose_id != 'overbet_value':
        if ctx.board_sig.flush_possible and ctx.hero_bucket != 'nuts':
            frac = min(frac, 0.75)
        if ctx.board_sig.wetness > 0.8 and ctx.hero_bucket in ('medium', 'strong'):
            frac = min(frac, 0.66)

    # 4. Street hard cap
    frac = min(frac, _STREET_HARD_CAP.get(ctx.street, 2.00))

    # 5. Physical clamp
    amount = max(frac * ctx.pot, ctx.big_blind)
    amount = min(amount, ctx.stack)

    # 6. Jam round-up (doc 03 §8 step 6)
    jammed = False
    if ctx.stack > 0 and amount >= ctx.stack * jam_threshold:
        amount = ctx.stack
        jammed = True

    # Recover the effective frac actually in use (may differ from input)
    eff_frac = (amount / ctx.pot) if ctx.pot > 0 else 0.0
    return CalibrateResult(eff_frac, amount, jammed)
