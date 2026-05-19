"""River polarized bluff-share gate.

This gate is intentionally narrow.  It should protect only true polarized
river bluffing lines, where "how many bluff combos can this sizing support?"
is the right question.  Flop/turn semi-bluffs and default stabs have live
equity, fold-equity, position, and texture considerations; those belong in the
purpose EV gates, not in a river bluff-to-value formula.
"""

from __future__ import annotations

from dataclasses import dataclass
import os as _os

from pokerfate.strategy.v3 import exploit, hero_range
from pokerfate.strategy.v3.context import DecisionCtx

_OVER_MULT = float(_os.environ.get('PF_ALPHA_OVER_MULT', '1.30'))
_UNDER_MULT = float(_os.environ.get('PF_ALPHA_UNDER_MULT', '0.70'))
_LOOSE_VPIP_MIN = float(_os.environ.get('PF_ALPHA_LOOSE_VPIP_MIN', '0.40'))
_POLAR_RIVER_PURPOSES = {
    'pure_bluff_river',
    'triple_barrel',
    'stop_and_go',
}


@dataclass
class AlphaCheckResult:
    passed: bool
    direction: str = 'ok'        # 'ok' | 'over_bluff' | 'under_bluff'
    target: float = 0.0
    hero_bluff_share: float = 0.0


def alpha_from_frac(frac: float) -> float:
    """Break-even fold frequency for a pure bluff: bet / (pot + bet)."""
    if frac <= 0:
        return 0.0
    return frac / (1.0 + frac)


def balanced_bluff_share_from_frac(frac: float) -> float:
    """Balanced bluff share inside a polarized betting range.

    If hero bets B into pot P, villain calls B to win P + 2B, so the indifference
    point for villain is bluff_share = B / (P + 2B).  `frac` is B / P.
    """
    if frac <= 0:
        return 0.0
    return frac / (1.0 + 2.0 * frac)


def _hero_facing_tag(ctx: DecisionCtx) -> str:
    """Pick a preflop-range scenario based on hero's story so far."""
    if ctx.is_pfr:
        return 'none'
    if ctx.position == 'BB':
        return 'bb_defend'
    return 'none'


def _purpose_env_suffix(purpose_id: str) -> str:
    return purpose_id.upper().replace('-', '_')


def _env_float(name: str, default: float | None = None) -> float | None:
    raw = _os.environ.get(name)
    if raw is None or raw == '':
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _over_mult(ctx: DecisionCtx, purpose_id: str) -> float:
    """Return the over-bluff tolerance multiplier for this node.

    Defaults preserve the historical 1.30 gate.  Sweep-only overrides can relax
    specific purposes or contexts without globally disabling alpha balance.
    """
    mult = _env_float(f'PF_ALPHA_OVER_MULT_{_purpose_env_suffix(purpose_id)}', _OVER_MULT)

    if ctx.num_opponents == 1:
        mult = max(mult, _env_float('PF_ALPHA_OVER_MULT_HU', mult) or mult)
    if ctx.is_pfr:
        mult = max(mult, _env_float('PF_ALPHA_OVER_MULT_PFR', mult) or mult)

    vs = ctx.villain_stats
    if vs.vpip >= _LOOSE_VPIP_MIN:
        mult = max(mult, _env_float('PF_ALPHA_OVER_MULT_LOOSE', mult) or mult)

    # No-fold-equity opponents should not get a free alpha relaxation unless
    # explicitly requested in a sweep.
    nofe = _env_float('PF_ALPHA_OVER_MULT_NOFE', None)
    if nofe is not None and exploit.no_fold_equity(ctx):
        mult = nofe

    return mult


def _applies(ctx: DecisionCtx, purpose_id: str) -> bool:
    if ctx.street != 'river':
        return False
    if purpose_id not in _POLAR_RIVER_PURPOSES:
        return False
    # Made value hands do not need bluff-share policing.  They are value combos
    # in the polar range, not excess bluffs.
    return ctx.hero_bucket in ('air', 'draw', 'weak_draw')


def check(ctx: DecisionCtx, frac: float, purpose_id: str) -> AlphaCheckResult:
    """Evaluate river polar bluff-share balance.

    Non-river or non-polar purposes return a no-op pass with target 0 so they
    also stay quiet in logs.  This avoids using a river range-balance formula
    to suppress flop/turn equity-realizing bets.
    """
    if frac <= 0 or not _applies(ctx, purpose_id):
        return AlphaCheckResult(True, 'ok', 0.0, 0.0)

    target = balanced_bluff_share_from_frac(frac)
    if target <= 0:
        return AlphaCheckResult(True, 'ok', target, 0.0)

    facing = _hero_facing_tag(ctx)
    # Subrange filter by hero's prior-street actions so the computed
    # bluff_share matches the actual node (e.g. "UTG open, flop checked"
    # subrange, not the full UTG open range on board).
    dist = hero_range.distribution(
        ctx.position, facing, ctx.board, ctx.hole_cards,
        my_prev_actions=ctx.my_prev_actions or None,
        is_pfr=ctx.is_pfr,
    )
    value_mass, bluff_mass = hero_range.value_bluff_split(dist)
    total = value_mass + bluff_mass
    if total < 1e-9:
        return AlphaCheckResult(True, 'ok', target, 0.0)
    share = bluff_mass / total

    if share > target * _over_mult(ctx, purpose_id):
        if exploit.over_bluff_harmless(ctx):
            # vs whale/fish/calling_station → 对手不做 range 层 exploit；
            # 放弃平衡换 value 是 +EV。
            return AlphaCheckResult(True, 'ok', target, share)
        return AlphaCheckResult(False, 'over_bluff', target, share)
    if share < target * _UNDER_MULT:
        if exploit.under_bluff_allowed(ctx):
            # vs whale/fish → under-bluff is correct exploit; pass.
            return AlphaCheckResult(True, 'ok', target, share)
        return AlphaCheckResult(False, 'under_bluff', target, share)
    return AlphaCheckResult(True, 'ok', target, share)
