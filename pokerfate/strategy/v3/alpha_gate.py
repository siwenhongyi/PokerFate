"""α-Balance Gate — doc 03 §7.

Runs AFTER the size calibrator on the final bet amount. Two-sided:
 - Chain A: bluff share over α×1.30 → downsize to next sizer tier, else check.
 - Chain B: bluff share under α×0.70 → resample once with bluff-emitters
   reweighted; if still nothing, accept the bet (trust range-level balance
   across hands).
"""

from __future__ import annotations

from dataclasses import dataclass

from pokerfate.strategy.v3 import exploit, hero_range
from pokerfate.strategy.v3.context import DecisionCtx


@dataclass
class AlphaCheckResult:
    passed: bool
    direction: str = 'ok'        # 'ok' | 'over_bluff' | 'under_bluff'
    target: float = 0.0
    hero_bluff_share: float = 0.0


def alpha_from_frac(frac: float) -> float:
    """α = bet / (bet + pot)."""
    if frac <= 0:
        return 0.0
    return frac / (1.0 + frac)


def _hero_facing_tag(ctx: DecisionCtx) -> str:
    """Pick a preflop-range scenario based on hero's story so far."""
    if ctx.is_pfr:
        return 'none'
    if ctx.position == 'BB':
        return 'bb_defend'
    return 'none'


def check(ctx: DecisionCtx, frac: float, purpose_id: str) -> AlphaCheckResult:
    """Evaluate α balance on (hero's range at this frac). Returns a result
    indicating pass / over-bluff / under-bluff.

    purpose_id is passed so merged purposes (block_bet, thin_value_bet) can
    skip α checking — they're not polarized.
    """
    # Purposes that skip α-gate:
    #  - merged purposes: not polarized by construction (range/block/thin/protection)
    #  - commitment purposes (value_jam): SPR-driven shove, not polarization
    #  - thick_value_bet: semantically "bet for value with strong hands";
    #    does not rely on bluff coverage to prevent exploitation. In practice
    #    the hero_range bucket estimator on wide defend/limped pools gives a
    #    bluff_share that far exceeds α for any polarized size — this killed
    #    legitimate 2-pair+ value bets in multi-way checked spots (see
    #    betting-redesign/gameplay-analysis).
    SKIP_ALPHA = {'range_cbet', 'block_bet', 'thin_value_bet',
                   'protection_bet', 'value_jam', 'thick_value_bet'}
    if purpose_id in SKIP_ALPHA or frac <= 0:
        return AlphaCheckResult(True, 'ok', 0.0, 0.0)

    # Bucket-level skip: α-gate 的作用是校准 range 层 bluff-to-value ratio。
    # 同一 polarized purpose（如 delayed_cbet、polarized_cbet、double_barrel）
    # 里 hero 持 value bucket 的采样，本身就是 value 贡献而非 bluff；用
    # range 层 bluff_share 去判定当前 value 采样是否过度 polar，分类粒度
    # 与约束粒度不匹配，会把合法 value line 误降级（实战手 17 / 手 30：
    # delayed_cbet with TPTK 或 pair+draw 被判 over_bluff 强制 check）。
    # 逻辑基础：Janda / Brokos — bluff-to-value ratio 约束作用在 hero
    # 手牌强度 bucket 上，不作用在下注动作类别上。
    if ctx.hero_bucket in ('medium', 'strong', 'nuts'):
        return AlphaCheckResult(True, 'ok', alpha_from_frac(frac), 0.0)

    target = alpha_from_frac(frac)
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

    if share > target * 1.30:
        if exploit.over_bluff_harmless(ctx):
            # vs whale/fish/calling_station → 对手不做 range 层 exploit；
            # 放弃平衡换 value 是 +EV。
            return AlphaCheckResult(True, 'ok', target, share)
        return AlphaCheckResult(False, 'over_bluff', target, share)
    if share < target * 0.70:
        if exploit.under_bluff_allowed(ctx):
            # vs whale/fish → under-bluff is correct exploit; pass.
            return AlphaCheckResult(True, 'ok', target, share)
        return AlphaCheckResult(False, 'under_bluff', target, share)
    return AlphaCheckResult(True, 'ok', target, share)
