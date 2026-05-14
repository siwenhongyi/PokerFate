"""Active-side (no facing bet) purposes. doc 03 §4.2 / §4.3.

# 2026-04-28 P0.5 env hooks:
#   PF_RANGECBET_WET_PEN     RangeCbet wetness>=0.45 penalty (default 0.5)
#   PF_RANGECBET_LOWBROAD_PEN  high_card<11 penalty (default 0.7)
#   PF_RANGECBET_FLUSH_PEN   flush_possible penalty (default 0.5)
#   PF_RANGECBET_PAIRED_PEN  paired non-K-high penalty (default 0.6)
#   PF_DEFAULT_STAB_HU       DefaultStab HU weight (default 0.5)
#   PF_DEFAULT_STAB_MULTI    DefaultStab multi-way weight (default 0.5)
"""

from __future__ import annotations

import os as _os
from typing import List, Optional, Tuple

from pokerfate.strategy.v3.context import DecisionCtx
from pokerfate.strategy.v3.exploit import no_fold_equity, sticky_passive
from pokerfate.strategy.v3.purpose import Purpose, TriggerResult
from pokerfate.strategy.v3.stackoff_guard import stackoff_guard_reason

_RC_WET_PEN = float(_os.environ.get('PF_RANGECBET_WET_PEN', '0.5'))
_RC_LOWBROAD_PEN = float(_os.environ.get('PF_RANGECBET_LOWBROAD_PEN', '0.7'))
_RC_FLUSH_PEN = float(_os.environ.get('PF_RANGECBET_FLUSH_PEN', '0.5'))
_RC_PAIRED_PEN = float(_os.environ.get('PF_RANGECBET_PAIRED_PEN', '0.6'))
_DS_HU_W = float(_os.environ.get('PF_DEFAULT_STAB_HU', '0.5'))
_DS_MULTI_W = float(_os.environ.get('PF_DEFAULT_STAB_MULTI', '0.5'))
_DS_AIR_MIN_EQ = float(_os.environ.get('PF_DEFAULT_STAB_AIR_MIN_EQ', '0.25'))
_DS_LOWFE_MULT = float(_os.environ.get('PF_DEFAULT_STAB_LOWFE_WEIGHT_MULT', '0.0'))
_DS_LOWFE_MIN_EQ = float(_os.environ.get('PF_DEFAULT_STAB_LOWFE_MIN_EQ', '0.35'))
_COMMIT_VALUE_EQ_FLOOR = float(_os.environ.get('PF_COMMIT_VALUE_EQ_FLOOR', '0.55'))
_VALUE_JAM_RIVER_DANGER_ADD = float(_os.environ.get('PF_VALUE_JAM_RIVER_DANGER_ADD', '0.04'))
_VALUE_JAM_PAIRED_ADD = float(_os.environ.get('PF_VALUE_JAM_PAIRED_ADD', '0.05'))
_VALUE_JAM_COMPLETING_ADD = float(_os.environ.get('PF_VALUE_JAM_COMPLETING_ADD', '0.04'))
_PROTECTION_MIN_EQ = float(_os.environ.get('PF_PROTECTION_MIN_EQ', '0.40'))
_PROTECTION_STICKY_EQ_ADD = float(_os.environ.get('PF_PROTECTION_STICKY_EQ_ADD', '0.03'))
_PROTECTION_MULTIWAY_EQ_ADD = float(_os.environ.get('PF_PROTECTION_MULTIWAY_EQ_ADD', '0.04'))
_ACTIVE_PROTECTION_MEDIUM_MIN_EQ = float(
    _os.environ.get('PF_ACTIVE_PROTECTION_MEDIUM_MIN_EQ', '1.10')
)
_ACTIVE_PROTECTION_WETNESS_MIN = float(
    _os.environ.get('PF_ACTIVE_PROTECTION_WETNESS_MIN', '0.45')
)
_ACTIVE_PROTECTION_MAX_NUTS = float(
    _os.environ.get('PF_ACTIVE_PROTECTION_MAX_NUTS', '0.35')
)
_PURE_BLUFF_RIVER_FOLD_MIN = float(_os.environ.get('PF_PURE_BLUFF_RIVER_FOLD_MIN', '0.52'))
_PURE_BLUFF_CATCHER_MIN = float(_os.environ.get('PF_PURE_BLUFF_CATCHER_MIN', '0.42'))
_BARREL_RESIST_CALL_EQ_ADD = float(_os.environ.get('PF_BARREL_RESIST_CALL_EQ_ADD', '0.04'))
_BARREL_RESIST_RAISE_EQ_ADD = float(_os.environ.get('PF_BARREL_RESIST_RAISE_EQ_ADD', '0.10'))
_BARREL_RESIST_WEIGHT_MULT = float(_os.environ.get('PF_BARREL_RESIST_WEIGHT_MULT', '0.70'))
_SUPER_MONSTER_EQ = float(_os.environ.get('PF_SUPER_MONSTER_EQ', '0.985'))
_SUPER_MONSTER_MC = float(_os.environ.get('PF_SUPER_MONSTER_MC', '0.95'))
_SUPER_MONSTER_MAX_VILLAIN_NUTS = float(
    _os.environ.get('PF_SUPER_MONSTER_MAX_VILLAIN_NUTS', '0.02')
)
_MONSTER_EQ = float(_os.environ.get('PF_MONSTER_VALUE_EQ', '0.92'))
_MONSTER_MC = float(_os.environ.get('PF_MONSTER_VALUE_MC', '0.85'))
_MONSTER_MAX_VILLAIN_NUTS = float(
    _os.environ.get('PF_MONSTER_VALUE_MAX_VILLAIN_NUTS', '0.10')
)
_MONSTER_AIR_WEAK_MIN = float(_os.environ.get('PF_MONSTER_AIR_WEAK_MIN', '0.50'))
_MONSTER_PAYING_MIN = float(_os.environ.get('PF_MONSTER_PAYING_MIN', '0.35'))
_MONSTER_DRAW_PRESSURE_MIN = float(
    _os.environ.get('PF_MONSTER_DRAW_PRESSURE_MIN', '0.15')
)


# ---------------------------------------------------------------------------
# Small shared helpers
# ---------------------------------------------------------------------------

def _villain_caps(ctx: DecisionCtx) -> bool:
    return ctx.villain_bucket_dist.get('nuts', 0.0) <= 0.08


def _bluff_catcher_density(ctx: DecisionCtx) -> float:
    return (ctx.villain_bucket_dist.get('medium', 0.0)
            + ctx.villain_bucket_dist.get('weak_draw', 0.0))


def _bucket_mass(ctx: DecisionCtx, *names: str) -> float:
    dist = ctx.villain_bucket_dist or {}
    return sum(dist.get(name, 0.0) for name in names)


def _villain_nuts(ctx: DecisionCtx) -> float:
    return (ctx.villain_bucket_dist or {}).get('nuts', 0.0)


def _draw_pressure_mass(ctx: DecisionCtx) -> float:
    dist = ctx.villain_bucket_dist or {}
    return dist.get('draw', 0.0) + 0.5 * dist.get('weak_draw', 0.0)


def _super_monster(ctx: DecisionCtx) -> bool:
    rank = ctx.hero_hand_rank
    if rank in {'four_of_a_kind', 'straight_flush', 'royal_flush'}:
        return True
    # A nut full house can be practically locked, but only when both equity
    # estimators and villain range agree that almost no better combo exists.
    return (
        rank == 'full_house'
        and ctx.equity_range >= _SUPER_MONSTER_EQ
        and ctx.equity_mc >= _SUPER_MONSTER_MC
        and _villain_nuts(ctx) <= _SUPER_MONSTER_MAX_VILLAIN_NUTS
    )


def _monster_value_kind(ctx: DecisionCtx, *, allow_facing_bet: bool = False) -> str:
    """Return 'super' / 'monster' for the special nut-value plan.

    This is intentionally narrower than "hero has nuts": the plan is for
    hands that should avoid blasting air off the pot, not for ordinary strong
    value or fragile straight/flush spots.
    """
    if (ctx.facing_bet and not allow_facing_bet) or ctx.hero_bucket != 'nuts':
        return ''
    if ctx.street not in ('flop', 'turn', 'river'):
        return ''
    if ctx.spr <= 1.5 and ctx.street != 'river':
        return ''
    if _super_monster(ctx):
        return 'super'

    rank = ctx.hero_hand_rank
    if ctx.equity_range < _MONSTER_EQ or ctx.equity_mc < _MONSTER_MC:
        return ''
    if _villain_nuts(ctx) > _MONSTER_MAX_VILLAIN_NUTS:
        return ''
    if rank == 'full_house':
        return 'monster'
    if rank in {'straight', 'flush'}:
        safer_shape = (
            ctx.equity_range >= 0.96
            and _villain_nuts(ctx) <= 0.06
            and not ctx.board_sig.paired
            and ctx.board_sig.wetness < 0.45
            and _draw_pressure_mass(ctx) < _MONSTER_DRAW_PRESSURE_MIN
        )
        return 'monster' if safer_shape else ''
    return ''


def monster_value_plan_kind(ctx: DecisionCtx, *, allow_facing_bet: bool = False) -> str:
    """Public helper for tests and for other value purposes to defer."""
    return _monster_value_kind(ctx, allow_facing_bet=allow_facing_bet)


def _can_overbet_value(ctx: DecisionCtx) -> bool:
    """Return True iff OverbetValue would be a legal candidate in this spot.

    Keep this helper aligned with OverbetValue.trigger() so any "defer to
    overbet" logic never drops ThickValueBet when overbet itself cannot fire.
    """
    if ctx.facing_bet:
        return False
    if ctx.street not in ('turn', 'river'):
        return False
    if ctx.nut_advantage < 0.25:
        return False
    if ctx.equity_range < 0.75:
        return False
    if ctx.num_opponents != 1 or ctx.spr < 2.4:
        return False
    if not _villain_caps(ctx):
        return False
    if _bluff_catcher_density(ctx) < 0.40:
        return False
    return True


def commit_value_eq(spr: float) -> float:
    """Commitment-aware value bet equity threshold.

    理论依据：Acevedo / Tipton commitment threshold——SPR 越低越早 commit，
    因为剩余 stack 不够 recover，当前街的 value 窗口比深筹小很多。

        breakeven_all_in_eq = spr / (2*spr + 1)

    加安全边际（对手 call range 比全 range 强）后，工程化为 spr/(spr+2)：
        SPR 1 → 0.33 | SPR 2 → 0.50 | SPR 3 → 0.60 | SPR 4 → 0.67 | SPR ∞ → 1.0

    再 floor 在 0.55（Janda 标准："被 call 后赢 > 50%" 为合法 value），
    cap 在 0.72（deep-SPR 下保留原 thick_value 校准）。
    最终曲线：
        SPR ≤ 2 → 0.55 | SPR 3 → 0.60 | SPR 4 → 0.67 | SPR ≥ 6 → 0.72
    """
    if spr <= 0:
        return _COMMIT_VALUE_EQ_FLOOR
    raw = spr / (spr + 2.0)
    return max(_COMMIT_VALUE_EQ_FLOOR, min(0.72, raw))


def _river_danger_add(ctx: DecisionCtx) -> float:
    if ctx.street != 'river':
        return 0.0
    add = _VALUE_JAM_RIVER_DANGER_ADD
    if ctx.board_sig.paired:
        add += _VALUE_JAM_PAIRED_ADD
    if ctx.board_sig.flush_possible or ctx.board_sig.straight_possible:
        add += _VALUE_JAM_COMPLETING_ADD
    return add


def _barrel_resistance_eq_add(ctx: DecisionCtx) -> float:
    add = 0.0
    if getattr(ctx, 'prev_bet_called_count', 0) > 0:
        add += _BARREL_RESIST_CALL_EQ_ADD * min(3, ctx.prev_bet_called_count)
    if getattr(ctx, 'prev_bet_raised', False):
        add += _BARREL_RESIST_RAISE_EQ_ADD
    return add


# ---------------------------------------------------------------------------
# 1. range_cbet
# ---------------------------------------------------------------------------


class RangeCbet(Purpose):
    id = 'range_cbet'
    street_gate = ('flop',)

    def trigger(self, ctx: DecisionCtx) -> TriggerResult:
        if ctx.facing_bet:
            return TriggerResult(False)
        # 2026-04-25 Fix 3: 允许非 PFR 但无人下注时的 donk 进攻。
        # 原 `not is_pfr` 硬门让 33% 到 flop 作为 caller 的场景完全无进攻——
        # limp-pot / multi-way check-to-hero 都没有攻击入口。
        # 放宽条件：非 PFR 必须有 showdown value 才触发（air/weak_draw 不 stab
        # 进 PFR 未知的 cbet 范围，风险过高）。PFR 身份仍自动通过。
        if not ctx.is_pfr and ctx.hero_bucket in ('air', 'weak_draw'):
            return TriggerResult(False)
        # opp_count 与 SPR 的耦合：两条合法路径
        #   (1) standard range-bet: HU/3-way 深筹，覆盖范围卖（air 也打）
        #   (2) multiway commit value: 3-4 way 低 SPR，hero 有 made hand 时
        #       按 commit value 打。Janda 多人底池明确：SPR ≤ 4 且有 value
        #       范围时 PFR 小 size cbet 频率仍高，被原 opp_count ≤ 2 硬门
        #       系统性挡掉。
        # multi_commit 的 eq 门按 opp_count 连续化：对手越多，range 越紧，
        # hero 顶对/两对的 vs-range equity 天然更低，门应同步下降。
        #   2-way: 0.45 | 3-way: 0.40 | 4-way: 0.35
        # SPR 上限用软过渡 5.0 而非硬 4.0，避免单挑 PFR 在 SPR 4-5 的缝隙
        # 里 standard (SPR≥5) 和 multi_commit (SPR≤4) 都不触发。
        multi_eq_need = max(0.30, 0.45 - 0.05 * max(0, ctx.num_opponents - 2))
        standard = (ctx.num_opponents <= 2 and ctx.spr >= 5.0)
        multi_commit = (
            ctx.num_opponents <= 4
            and ctx.spr <= 5.0
            and ctx.hero_bucket in ('medium', 'strong', 'nuts')
            and ctx.equity_range >= multi_eq_need
        )
        if not (standard or multi_commit):
            return TriggerResult(False)
        # 板面条件只适用于 standard range-bet（覆盖范围卖要求牌面对 PFR
        # 范围友好）。multi_commit 打的是 value，板面纹理由 hero_bucket/
        # equity 约束，不需要额外 board gate。
        if standard:
            # 2026-04-28 P0.5：硬门改连续惩罚因子。
            # 旧版四个硬门让 PFR cbet 实战触发率 < 10%（业界基准 50-60%），
            # 直接造成 default_check 占比 37%。改为按板面"对 PFR 范围不友好"
            # 程度乘惩罚因子，差板面权重低但仍可能触发，差到一定程度才放弃。
            penalty = 1.0
            if ctx.board_sig.wetness >= 0.45:
                penalty *= _RC_WET_PEN
            if ctx.board_sig.high_card_rank < 11:
                penalty *= _RC_LOWBROAD_PEN
            if ctx.board_sig.flush_possible:
                penalty *= _RC_FLUSH_PEN
            if ctx.board_sig.paired and ctx.board_sig.high_card_rank < 13:
                penalty *= _RC_PAIRED_PEN
            base = 0.4 if ctx.hero_bucket == 'air' else 0.8
            w = base * penalty
            if w < 0.15:
                return TriggerResult(False)
        else:
            # multi_commit: 权重由 equity 相对 multi_eq_need 的 margin 驱动
            w = min(1.0, 0.4 + (ctx.equity_range - multi_eq_need) * 1.5)
        return TriggerResult(True, w)

    def sizer(self, ctx: DecisionCtx) -> List[Tuple[float, float]]:
        return [(0.25, 0.4), (0.33, 0.6)]

    def alpha_target(self, ctx: DecisionCtx, frac: float) -> Optional[float]:
        return None  # merged


# ---------------------------------------------------------------------------
# 2. polarized_cbet
# ---------------------------------------------------------------------------


class PolarizedCbet(Purpose):
    id = 'polarized_cbet'
    street_gate = ('flop', 'turn')

    def trigger(self, ctx: DecisionCtx) -> TriggerResult:
        if ctx.facing_bet or not ctx.is_pfr:
            return TriggerResult(False)
        wet = ctx.board_sig.wetness >= 0.45 or ctx.board_sig.high_card_rank < 11
        if not wet:
            return TriggerResult(False)
        if ctx.hero_bucket not in ('nuts', 'strong', 'draw'):
            return TriggerResult(False)
        if ctx.spr < 3:
            return TriggerResult(False)
        weight = min(2.0, ctx.equity_range + 0.5 * ctx.nut_advantage)
        return TriggerResult(True, max(0.4, weight))

    def sizer(self, ctx: DecisionCtx) -> List[Tuple[float, float]]:
        return [(0.55, 0.3), (0.66, 0.5), (0.75, 0.2)]


# ---------------------------------------------------------------------------
# 3. protection_bet
# ---------------------------------------------------------------------------


class ProtectionBet(Purpose):
    id = 'protection_bet'
    street_gate = ('flop', 'turn')

    def trigger(self, ctx: DecisionCtx) -> TriggerResult:
        if ctx.facing_bet:
            return TriggerResult(False)
        if ctx.hero_bucket not in ('medium', 'strong'):
            return TriggerResult(False)
        pressure = ctx.board_sig.wetness
        if ctx.board_sig.flush_draw or ctx.board_sig.flush_possible:
            pressure = max(pressure, 0.50)
        if ctx.board_sig.straight_draw_heavy:
            pressure = max(pressure, 0.50)
        if pressure < _ACTIVE_PROTECTION_WETNESS_MIN:
            return TriggerResult(False)
        if (ctx.villain_bucket_dist or {}).get('nuts', 0.0) > _ACTIVE_PROTECTION_MAX_NUTS:
            return TriggerResult(False)
        if ctx.spr < 3 or ctx.spr > 8:
            return TriggerResult(False)
        protection_need = _PROTECTION_MIN_EQ
        if ctx.hero_bucket == 'medium':
            protection_need = max(protection_need, _ACTIVE_PROTECTION_MEDIUM_MIN_EQ)
        if ctx.n_sticky >= 1:
            protection_need += _PROTECTION_STICKY_EQ_ADD
        if ctx.num_opponents >= 2:
            protection_need += _PROTECTION_MULTIWAY_EQ_ADD
        if ctx.equity_range < protection_need:
            return TriggerResult(False)
        return TriggerResult(True, 0.9)

    def sizer(self, ctx: DecisionCtx) -> List[Tuple[float, float]]:
        if ctx.board_sig.wetness >= 0.55:
            return [(0.55, 0.5), (0.66, 0.5)]
        return [(0.40, 0.4), (0.50, 0.4), (0.66, 0.2)]

    def alpha_target(self, ctx: DecisionCtx, frac: float) -> Optional[float]:
        # Merged — small configured bluff share (~20-25%).
        return None


# ---------------------------------------------------------------------------
# 4. thin_value_bet
# ---------------------------------------------------------------------------


class ThinValueBet(Purpose):
    id = 'thin_value_bet'
    street_gate = ('turn', 'river')

    def trigger(self, ctx: DecisionCtx) -> TriggerResult:
        if ctx.facing_bet:
            return TriggerResult(False)
        # 2026-04-25 P1-1：窗口下限 0.52→0.48。实战多人池的 medium 桶 eq
        # 常在 0.45-0.55 区间，0.52 下限把几乎所有多人池 thin value 机会
        # 挡掉。0.48 对应 "赢得 call 后仍微领先" 的 Janda 薄 value 阈值。
        if not (0.48 <= ctx.equity_range <= 0.65):
            return TriggerResult(False)
        if ctx.hero_bucket not in ('strong', 'medium'):
            return TriggerResult(False)
        if ctx.board_sig.wetness >= 0.70:
            return TriggerResult(False)
        vs = ctx.villain_stats
        # sticky = 对手会用更弱的牌 call 到摊牌。三条连续指标独立证据：
        #   river_fold_rate 低 / wtsd 高 / fold_to_cbet 低 / af 低（被动）。
        # 任一满足即触发（降低了原 player_type 标签三选一的冗余项）。
        # 2026-04-25 Fix 2: 新对手（样本不足）时加一条 vpip≥0.40 的先验代理。
        # 原因：本 session 实战 153 手里 thin_value_bet 触发次数 = 0，
        # 因为所有 sticky 证据指标都需要 hands_seen≥20 / opps≥5，新对手全挂。
        # 加 vpip prior：vpip≥0.40 说明玩家宽 VPIP（loose-passive 特征的连续
        # 指标），作为"可能 sticky"的先验触发。vpip 是低样本就可得到的指标
        # （server_priors 或 preflop 3-5 手即稳定）。
        sticky_any = False
        if vs.river_action_count >= 5 and vs.river_fold_rate < 0.45:
            sticky_any = True
        if vs.hands_seen >= 20 and vs.wtsd > 0.28:
            sticky_any = True
        if vs.fold_to_cbet_opps >= 5 and vs.fold_to_cbet < 0.35:
            sticky_any = True
        if vs.hands_seen >= 20 and vs.af < 1.3:
            sticky_any = True
        # Prior: 新对手 vpip ≥ 0.40 作为 sticky 代理（vpip 是高频早稳定指标）
        if not sticky_any and vs.vpip >= 0.40:
            sticky_any = True
        if not sticky_any:
            return TriggerResult(False)
        # weight 由 river_fold_rate 基底 + sticky 证据累加，最多 0.9（原上限 ~0.8）
        base = (1.0 - vs.river_fold_rate) * 0.8 if vs.river_action_count >= 5 else 0.4
        bonus = 0.0
        if vs.hands_seen >= 20:
            bonus += max(0.0, (vs.wtsd - 0.28) * 1.5)
        if vs.fold_to_cbet_opps >= 5:
            bonus += max(0.0, (0.35 - vs.fold_to_cbet) * 1.2)
        return TriggerResult(True, max(0.3, min(0.9, base + bonus)))

    def sizer(self, ctx: DecisionCtx) -> List[Tuple[float, float]]:
        return [(0.40, 0.4), (0.50, 0.4), (0.66, 0.2)]

    def alpha_target(self, ctx: DecisionCtx, frac: float) -> Optional[float]:
        return None  # merged


# ---------------------------------------------------------------------------
# 5. monster_value_plan
# ---------------------------------------------------------------------------


class MonsterValuePlan(Purpose):
    """Special plan for lock/near-lock nut hands.

    It is not the old "villain will bluff, so check" slow-play. This plan is
    hand-strength driven:
      - super monster: check/small bet on flop, then escalate after resistance
      - monster: small/medium value, less pure check because redraws exist
    """

    id = 'monster_value_plan'

    def trigger(self, ctx: DecisionCtx) -> TriggerResult:
        kind = _monster_value_kind(ctx)
        if not kind:
            return TriggerResult(False)
        if ctx.street == 'river' and ctx.spr <= 1.5:
            return TriggerResult(True, 5.5)
        base = 5.0 if kind == 'super' else 3.6
        if ctx.prev_bet_called_count > 0:
            base += 0.8
        if ctx.prev_bet_raised:
            base += 1.2
        if _bucket_mass(ctx, 'medium', 'strong') >= _MONSTER_PAYING_MIN:
            base += 0.5
        return TriggerResult(True, base)

    def sizer(self, ctx: DecisionCtx) -> List[Tuple[float, float]]:
        kind = _monster_value_kind(ctx)
        resisted = ctx.prev_bet_called_count > 0 or ctx.prev_bet_raised
        paying = _bucket_mass(ctx, 'medium', 'strong')
        air_weak = _bucket_mass(ctx, 'air', 'weak_draw')
        draw_pressure = _draw_pressure_mass(ctx)

        if kind == 'super':
            if ctx.street == 'flop' and not resisted:
                return [(0.00, 0.50), (0.33, 0.25), (0.50, 0.25)]
            if ctx.street == 'turn':
                if resisted:
                    if ctx.prev_bet_raised:
                        return [(0.75, 0.45), (1.00, 0.55)]
                    return [(0.55, 0.40), (0.75, 0.60)]
                if ctx.flop_checked_through or ctx.my_prev_actions.get('flop') == 'check':
                    return [(0.33, 0.45), (0.55, 0.55)]
                return [(0.50, 0.40), (0.66, 0.60)]
            if ctx.street == 'river':
                if resisted:
                    return [(0.75, 0.35), (1.00, 0.35), (2.00, 0.30)]
                return [(0.55, 0.45), (0.75, 0.40), (1.00, 0.15)]

        # Monster, not lock: no pure check unless air is abundant and redraw
        # pressure is low. Once anyone calls/raises, shift to harvest mode.
        if resisted:
            if ctx.prev_bet_raised:
                return [(0.75, 0.45), (1.00, 0.55)]
            return [(0.55, 0.40), (0.75, 0.60)]
        if ctx.street == 'river':
            return [(0.66, 0.40), (0.85, 0.40), (1.00, 0.20)]
        if paying >= _MONSTER_PAYING_MIN:
            return [(0.55, 0.45), (0.75, 0.55)]
        if draw_pressure >= _MONSTER_DRAW_PRESSURE_MIN or ctx.board_sig.wetness >= 0.55:
            return [(0.50, 0.45), (0.66, 0.40), (0.75, 0.15)]
        if air_weak >= _MONSTER_AIR_WEAK_MIN:
            return [(0.00, 0.10), (0.33, 0.50), (0.50, 0.40)]
        return [(0.40, 0.45), (0.55, 0.55)]

    def alpha_target(self, ctx: DecisionCtx, frac: float) -> Optional[float]:
        return None


# ---------------------------------------------------------------------------
# 6. thick_value_bet
# ---------------------------------------------------------------------------


class ThickValueBet(Purpose):
    id = 'thick_value_bet'

    def trigger(self, ctx: DecisionCtx) -> TriggerResult:
        if ctx.facing_bet:
            return TriggerResult(False)
        if _monster_value_kind(ctx):
            return TriggerResult(False)
        # Equity 门槛按 SPR commitment 动态化（不再固定 0.70）：低 SPR
        # 下门槛降到 0.55 以让"两对/顶对顶踢 + 低 SPR"这个常见 value
        # 场景能正常触发；deep SPR 保留 0.72 的 thick value 校准。
        #
        # 2026-04-25 Fix 1: medium 桶 + 非湿板按 SPR 分档放宽门槛。
        # 原因：medium bucket（一对好踢 / 两对下端）eq 50-60% 是最常见的
        # showdown-value 区间，但原 commit_value_eq 在 SPR 3-5 要求 0.60-0.67、
        # SPR > 6 要求 0.72 → 这段完全落空 → hero 对 medium 永远不 value bet →
        # 对手免费 showdown。
        # 门槛按 SPR 分档：
        #   SPR ≤ 5：eq ≥ 0.48（低 SPR 已近 commit，小注薄 value）
        #   SPR 5-10：eq ≥ 0.55（中深 SPR，仍允许 thin-ish value）
        #   SPR > 10：保留 commit_value_eq 0.72（deep 下避开 reverse IO）
        # 只对 medium + wetness < 0.55 生效。
        eq_need = commit_value_eq(ctx.spr)
        if (ctx.hero_bucket == 'medium'
                and ctx.board_sig.wetness < 0.55):
            if ctx.spr <= 5.0:
                eq_need = min(eq_need, 0.48)
            elif ctx.spr <= 10.0:
                eq_need = min(eq_need, 0.55)
        if ctx.equity_range < eq_need:
            return TriggerResult(False)
        # Don't compete with overbet_value only when overbet is truly legal.
        # This keeps ThickValueBet alive in boundary spots (e.g. 2.0 < SPR < 2.4)
        # where overbet cannot trigger yet.
        if _can_overbet_value(ctx):
            return TriggerResult(False)
        # Don't compete with range_cbet on flop dry boards.
        if ctx.street == 'flop' and ctx.board_sig.is_dry \
                and ctx.board_sig.high_card_rank >= 11 and ctx.is_pfr:
            return TriggerResult(False)
        # 湿板 + SPR ≥ 2 + 粘性被动：thick value 反向 -EV。被动对手的 raising
        # range 是 polar 朝坚果，多 street 有 polar 加注空间时 hero 的 value
        # 加码只会被 call-弱 / raise-强榨干。让位给 block_bet / pot_control。
        # equity_range < 0.85 门是关键：hero 近坚果（≥ 0.85）时，即便被 polar
        # 加注 hero 仍赢多数情况，thick value 依旧 +EV；只有"中等偏强"区间
        # （0.70-0.85）是 reverse implied odds 真正起效的地带。
        if (ctx.board_sig.is_wet
                and ctx.spr >= 2.0
                and ctx.num_opponents == 1
                and ctx.equity_range < 0.85
                and sticky_passive(ctx)):
            return TriggerResult(False)
        # 权重基准从 eq_need 起算而非固定 0.70，确保 low SPR 下早触发的
        # hand 权重不会因为 (eq - 0.70) 为负而崩塌。
        w = 0.8 + (ctx.equity_range - eq_need) * 3.0
        return TriggerResult(True, min(2.0, max(0.4, w)))

    def sizer(self, ctx: DecisionCtx) -> List[Tuple[float, float]]:
        return [(0.55, 0.2), (0.66, 0.4), (0.75, 0.4)]


# ---------------------------------------------------------------------------
# 7. block_bet
# ---------------------------------------------------------------------------


class BlockBet(Purpose):
    id = 'block_bet'
    street_gate = ('river',)

    def trigger(self, ctx: DecisionCtx) -> TriggerResult:
        if ctx.facing_bet or ctx.is_ip:
            return TriggerResult(False)
        if ctx.hero_bucket != 'medium':
            return TriggerResult(False)
        if not (0.40 <= ctx.equity_range <= 0.65):
            return TriggerResult(False)
        if ctx.spr < 1.5:
            return TriggerResult(False)
        # 2026-04-25 P2-1：polarized 判据加新对手 vpip 先验。原两个指标
        # river_bet_frequency / bluff_win_rate 都需要 sample，新对手永远
        # 不达标 → block_bet 对新对手 0 触发。
        # vpip ≥ 0.40 代理 "loose bettor" 倾向，是低样本就稳定的指标。
        vs = ctx.villain_stats
        polarized = (vs.river_bet_frequency > 0.35
                     or vs.bluff_win_rate > 0.25
                     or (vs.river_action_count < 5 and vs.bet_win_count < 5
                         and vs.vpip >= 0.40))
        if not polarized:
            return TriggerResult(False)
        # weight 基数用 vpip 代替（新对手场景）
        base = max(vs.river_bet_frequency, vs.vpip * 0.7)
        w = 0.6 * (1 + base)
        return TriggerResult(True, w)

    def sizer(self, ctx: DecisionCtx) -> List[Tuple[float, float]]:
        return [(0.20, 0.3), (0.25, 0.4), (0.33, 0.3)]

    def alpha_target(self, ctx: DecisionCtx, frac: float) -> Optional[float]:
        return None  # merged


# ---------------------------------------------------------------------------
# 8. overbet_value
# ---------------------------------------------------------------------------


class OverbetValue(Purpose):
    id = 'overbet_value'
    street_gate = ('turn', 'river')

    def trigger(self, ctx: DecisionCtx) -> TriggerResult:
        if not _can_overbet_value(ctx):
            return TriggerResult(False)
        w = 1.2 * (0.5 + ctx.nut_advantage)
        return TriggerResult(True, w)

    def sizer(self, ctx: DecisionCtx) -> List[Tuple[float, float]]:
        return [(1.25, 0.4), (1.50, 0.4), (1.75, 0.2)]


# ---------------------------------------------------------------------------
# 9. semi_bluff
# ---------------------------------------------------------------------------


class SemiBluff(Purpose):
    id = 'semi_bluff'
    street_gate = ('flop', 'turn')

    def trigger(self, ctx: DecisionCtx) -> TriggerResult:
        # 2026-04-25 放宽：draw 桶太严格（明确 OESD/flush draw），实战里 hero
        # 更常落到 weak_draw（gutshot / overcards + backdoor）。两者都是 "未
        # 成牌但有听牌潜力" —— semi_bluff 本来的语义就涵盖。
        # weak_draw 时用 eq 而非 draw 的确定性补偿听牌质量。
        if ctx.facing_bet or ctx.hero_bucket not in ('draw', 'weak_draw'):
            return TriggerResult(False)
        if ctx.spr < 3:
            return TriggerResult(False)
        # weak_draw 需要更低 EV 风险容忍：要求 eq ≥ 0.22（gutshot+overcards
        # 组合的典型下界）。draw 无此门（本身 eq 足）。
        if ctx.hero_bucket == 'weak_draw' and ctx.equity_range < 0.22:
            return TriggerResult(False)
        # Sticky 对手硬门：semi-bluff 是 draw-only bucket 的纯 bluff 线，
        # EV 公式以 fold_equity 为主项，FE≈0 时结构性负。原 EV gate 用
        # `opp_fold_est = max(0.35, ftc)` 的 floor 反而把 station 对手的
        # FE 人为抬到 35%，误判 +EV（实战手 204：hero JT gutshot eq 19%
        # vs ftc=0% station 连打两街 -287680）。
        if no_fold_equity(ctx):
            return TriggerResult(False)
        # EV gate: FE + (1-FE)*(eq*(1+bet) - (1-eq)*bet) >= 0 at 0.66 bet.
        bet = 0.66
        fe = bet / (1.0 + bet)  # required FE for pure bluff
        # Approximation of opp MDF-aligned fold:
        opp_fold_est = max(0.35, ctx.villain_stats.fold_to_cbet)
        ev = (opp_fold_est * 1.0
              + (1 - opp_fold_est) * (ctx.equity_range * (1 + bet)
                                       - (1 - ctx.equity_range) * bet))
        if ev <= 0 and ctx.equity_range < 0.40:
            return TriggerResult(False)
        _ = fe  # retained for doc clarity
        w = 0.4 + 0.5 * ctx.equity_range
        return TriggerResult(True, w)

    def sizer(self, ctx: DecisionCtx) -> List[Tuple[float, float]]:
        return [(0.55, 0.4), (0.66, 0.4), (0.75, 0.2)]


# ---------------------------------------------------------------------------
# 10. pure_bluff_river
# ---------------------------------------------------------------------------


class PureBluffRiver(Purpose):
    id = 'pure_bluff_river'
    street_gate = ('river',)

    def trigger(self, ctx: DecisionCtx) -> TriggerResult:
        if ctx.facing_bet or ctx.hero_bucket != 'air':
            return TriggerResult(False)
        if not (ctx.blockers.nut_flush_blocker or ctx.blockers.straight_blocker):
            return TriggerResult(False)
        if _bluff_catcher_density(ctx) < _PURE_BLUFF_CATCHER_MIN:
            return TriggerResult(False)
        if ctx.villain_stats.river_fold_rate <= _PURE_BLUFF_RIVER_FOLD_MIN:
            return TriggerResult(False)
        # Sticky 对手硬门：pure bluff 的 EV 主项完全依赖 FE；river_fold_rate
        # 已有 > 0.40 门，但 river_fold 与 fold_to_cbet 不同 street——对
        # fold_to_cbet ≤ 0.20 的 station 对手（flop-call station），river
        # fold 率偶尔过 0.40 门也仍是结构性 -EV。双门更稳健。
        if no_fold_equity(ctx):
            return TriggerResult(False)
        if ctx.num_opponents != 1:
            return TriggerResult(False)
        w = ctx.villain_stats.river_fold_rate * ctx.blockers.count() * 0.5
        return TriggerResult(True, max(0.2, w))

    def sizer(self, ctx: DecisionCtx) -> List[Tuple[float, float]]:
        return [(0.66, 0.4), (0.75, 0.3), (1.00, 0.3)]


# ---------------------------------------------------------------------------
# 11. delayed_cbet
# ---------------------------------------------------------------------------


class DelayedCbet(Purpose):
    id = 'delayed_cbet'
    street_gate = ('turn',)

    def trigger(self, ctx: DecisionCtx) -> TriggerResult:
        if ctx.facing_bet or not ctx.is_pfr:
            return TriggerResult(False)
        if not ctx.flop_checked_through:
            return TriggerResult(False)
        if ctx.equity_range < 0.45:
            return TriggerResult(False)
        return TriggerResult(True, 0.6 + 0.4 * ctx.equity_range)

    def sizer(self, ctx: DecisionCtx) -> List[Tuple[float, float]]:
        return [(0.50, 0.5), (0.66, 0.5)]


# ---------------------------------------------------------------------------
# 12. probe_bet
# ---------------------------------------------------------------------------


class ProbeBet(Purpose):
    id = 'probe_bet'
    street_gate = ('turn', 'river')

    def trigger(self, ctx: DecisionCtx) -> TriggerResult:
        if ctx.facing_bet or ctx.is_ip or ctx.is_pfr:
            return TriggerResult(False)
        if not ctx.flop_checked_through:
            return TriggerResult(False)
        if ctx.equity_range < 0.40:
            return TriggerResult(False)
        # Sticky 对手 + 无 showdown value（air/weak_draw）时 probe 是
        # 结构性 -EV：FE ≈ 0 无法靠下注赢 pot，hero 又没有叫到摊牌的 eq。
        # 持 value bucket（medium+）时保留 probe —— 对 station 薄 value
        # 是 +EV 的（他会 call 更弱）。
        if no_fold_equity(ctx) and ctx.hero_bucket in ('air', 'weak_draw'):
            return TriggerResult(False)
        if ctx.street == 'river':
            w = 0.5 + 0.3 * (1 - ctx.villain_stats.river_fold_rate)
        else:
            w = 0.5 + 0.15
        return TriggerResult(True, w)

    def sizer(self, ctx: DecisionCtx) -> List[Tuple[float, float]]:
        return [(0.40, 0.4), (0.50, 0.4), (0.66, 0.2)]


# ---------------------------------------------------------------------------
# 13. float_bet
# ---------------------------------------------------------------------------


class FloatBet(Purpose):
    id = 'float_bet'
    street_gate = ('turn', 'river')

    def trigger(self, ctx: DecisionCtx) -> TriggerResult:
        if ctx.facing_bet or not ctx.is_ip or ctx.is_pfr:
            return TriggerResult(False)
        prev_street = {'turn': 'flop', 'river': 'turn'}.get(ctx.street)
        if prev_street is None:
            return TriggerResult(False)
        if ctx.opp_prev_actions.get(prev_street) != 'check':
            return TriggerResult(False)
        if ctx.equity_range < 0.30:
            return TriggerResult(False)
        # Sticky 对手 + bluff bucket 时 float 结构性 -EV（同 ProbeBet 逻辑）。
        # value bucket 保留 —— IP 对 station 的薄价值 stab 仍 +EV。
        if no_fold_equity(ctx) and ctx.hero_bucket in ('air', 'weak_draw'):
            return TriggerResult(False)
        return TriggerResult(True, 0.5 + 0.3 * ctx.villain_stats.bluff_win_rate)

    def sizer(self, ctx: DecisionCtx) -> List[Tuple[float, float]]:
        return [(0.50, 0.5), (0.66, 0.5)]


# ---------------------------------------------------------------------------
# 14. turn_donk
# ---------------------------------------------------------------------------


class TurnDonk(Purpose):
    id = 'turn_donk'
    street_gate = ('turn',)

    def trigger(self, ctx: DecisionCtx) -> TriggerResult:
        if ctx.facing_bet or ctx.is_ip:
            return TriggerResult(False)
        if not ctx.flop_checked_through:
            return TriggerResult(False)
        if not (ctx.board_sig.straight_draw_heavy
                or ctx.board_sig.high_card_rank <= 10):
            return TriggerResult(False)
        if ctx.hero_bucket not in ('strong', 'nuts', 'draw'):
            return TriggerResult(False)
        return TriggerResult(True, 0.6)

    def sizer(self, ctx: DecisionCtx) -> List[Tuple[float, float]]:
        return [(0.20, 0.3), (0.60, 0.5), (1.10, 0.2)]


# ---------------------------------------------------------------------------
# 15. double_barrel
# ---------------------------------------------------------------------------


class DoubleBarrel(Purpose):
    id = 'double_barrel'
    street_gate = ('turn',)

    def trigger(self, ctx: DecisionCtx) -> TriggerResult:
        if ctx.facing_bet or not ctx.is_pfr:
            return TriggerResult(False)
        if ctx.my_prev_actions.get('flop') != 'bet':
            return TriggerResult(False)
        need = 0.45 + _barrel_resistance_eq_add(ctx)
        if ctx.hero_bucket in ('air', 'weak_draw', 'draw') and ctx.equity_range < need:
            return TriggerResult(False)
        # good barrel card = high (A/K/Q) turn or equity >= need
        if ctx.equity_range < need and ctx.board_sig.high_card_rank < 12:
            return TriggerResult(False)
        weight = 0.7 + 0.5 * ctx.equity_range
        if ctx.hero_bucket in ('air', 'weak_draw', 'draw') and getattr(ctx, 'resistance_level', 0.0) > 0:
            weight *= _BARREL_RESIST_WEIGHT_MULT
        return TriggerResult(True, weight)

    def sizer(self, ctx: DecisionCtx) -> List[Tuple[float, float]]:
        return [(0.55, 0.3), (0.66, 0.5), (0.75, 0.2)]


# ---------------------------------------------------------------------------
# 16. triple_barrel
# ---------------------------------------------------------------------------


class TripleBarrel(Purpose):
    id = 'triple_barrel'
    street_gate = ('river',)

    def trigger(self, ctx: DecisionCtx) -> TriggerResult:
        if ctx.facing_bet or not ctx.is_pfr:
            return TriggerResult(False)
        if ctx.my_prev_actions.get('flop') != 'bet':
            return TriggerResult(False)
        if ctx.my_prev_actions.get('turn') != 'bet':
            return TriggerResult(False)
        if ctx.hero_bucket not in ('nuts', 'strong', 'air'):
            return TriggerResult(False)
        if ctx.hero_bucket == 'air' and not ctx.blockers.count():
            return TriggerResult(False)
        if ctx.hero_bucket in ('air', 'weak_draw', 'draw'):
            need = _barrel_resistance_eq_add(ctx)
            if need > 0 and ctx.equity_range < need:
                return TriggerResult(False)
        if ctx.villain_stats.river_fold_rate < 0.35:
            return TriggerResult(False)
        weight = 0.7
        if ctx.hero_bucket in ('air', 'weak_draw', 'draw') and getattr(ctx, 'resistance_level', 0.0) > 0:
            weight *= _BARREL_RESIST_WEIGHT_MULT
        return TriggerResult(True, weight)

    def sizer(self, ctx: DecisionCtx) -> List[Tuple[float, float]]:
        return [(0.75, 0.3), (1.00, 0.4), (1.50, 0.3)]


# ---------------------------------------------------------------------------
# 17. stop_and_go
# ---------------------------------------------------------------------------


class StopAndGo(Purpose):
    id = 'stop_and_go'
    street_gate = ('river',)

    def trigger(self, ctx: DecisionCtx) -> TriggerResult:
        if ctx.facing_bet:
            return TriggerResult(False)
        if ctx.my_prev_actions.get('flop') != 'bet':
            return TriggerResult(False)
        if ctx.my_prev_actions.get('turn') != 'check':
            return TriggerResult(False)
        vs = ctx.villain_stats
        # stop-and-go EV 条件：对手会弃、但不过度弃（否则 flop-bet 就直接成功）、
        # 且河牌面前会弃。用连续加权替代原 reg/nit/station 白名单（也替代了
        # 原 [0.35, 0.68] 硬窗口）——避免任何 ftc/river_fold 边缘的硬跳变。
        #   ftc_score：在 fold_to_cbet=0.52 时峰值 1.0，向两端线性衰减
        #              （ftc<0.22 或 >0.82 衰减到 0）。
        #   rfr_score：river_fold_rate 从 0.30 线性升至 0.60 饱和。
        # composite = ftc_score × rfr_score；≥ 0.10 才触发（避免噪声）。
        # 激进爱 float 的对手（af > 2.6 + turn_afq > 0.55）单独走一条 path，
        # 因为他 turn 见 check 会打 stab，river 面对 shove 又弃。
        ftc_ok = vs.fold_to_cbet_opps >= 5
        rfr_ok = vs.river_action_count >= 5
        if ftc_ok and rfr_ok:
            ftc_score = max(0.0, 1.0 - abs(vs.fold_to_cbet - 0.52) / 0.30)
            rfr_score = max(0.0, min(1.0, (vs.river_fold_rate - 0.30) / 0.30))
            composite = ftc_score * rfr_score
        else:
            composite = 0.0
        aggressive_floater = (vs.hands_seen >= 20
                              and vs.af > 2.6
                              and vs.turn_afq > 0.55)
        if composite < 0.10 and not aggressive_floater:
            return TriggerResult(False)
        # weight：composite 强度驱动 0.35→0.75；aggressive_floater 独走给 0.45
        if composite >= 0.10:
            weight = 0.35 + composite * 0.40
        else:
            weight = 0.45
        return TriggerResult(True, max(0.35, min(0.75, weight)))

    def sizer(self, ctx: DecisionCtx) -> List[Tuple[float, float]]:
        return [(0.75, 0.5), (1.00, 0.5)]


# ---------------------------------------------------------------------------
# 18. value_jam (SPR <= 2.4 with strong hand — bypass normal sizing)
# ---------------------------------------------------------------------------


class ValueJam(Purpose):
    id = 'value_jam'

    def trigger(self, ctx: DecisionCtx) -> TriggerResult:
        if ctx.facing_bet:
            return TriggerResult(False)
        if ctx.spr > 2.4:
            return TriggerResult(False)
        # Equity 门按 SPR commitment threshold：SPR ≤ 2.4 时 commit_value_eq
        # 返回 0.55，即"被 call 赢 > 50%" Janda 最小 value 标准。原 0.70
        # 硬门在 SPR 1-2.4 的 commit 区把大量合法 value_jam（两对/顶对顶踢）
        # 挡在门外。
        eq_need = commit_value_eq(ctx.spr) + _river_danger_add(ctx)
        if ctx.equity_range < eq_need:
            return TriggerResult(False)
        if stackoff_guard_reason(ctx, self.id, will_jam=True):
            return TriggerResult(False)
        # 权重按 eq margin over commit 动态增长，保证在 SPR ≤ 2 与
        # ThickValueBet（cap 2.0）的 overlap 区 ValueJam 主导：jam 是
        # commit 节点 value 最大化的正确决策（fold equity + 避免被 villain
        # 后续控 pot）。eq=0.55 边界时 w=1.5；eq=0.95（nuts）w=3.1。
        w = 1.5 + 4.0 * (ctx.equity_range - eq_need)
        return TriggerResult(True, max(1.5, w))

    def sizer(self, ctx: DecisionCtx) -> List[Tuple[float, float]]:
        # Special: all-in → sizer returns a frac large enough to trigger
        # jam round-up in calibrator.
        return [(2.00, 1.0)]


# ---------------------------------------------------------------------------
# 19. default_stab (2026-04-25 Fix 4)
# ---------------------------------------------------------------------------


class DefaultStab(Purpose):
    """PFR 默认小注 stab —— 补足 range_cbet 严苛门槛拒掉后 PFR 仍应出手的场景。

    背景：RangeCbet.standard 要求 dry J+ 板且 num_opp ≤ 2，multi_commit 要求
    SPR ≤ 5；实战 PFR 到 flop 的 56 次里这两个都满足的不到 10%。剩下的
    场景 hero 作为 PFR 却默默 check，对手免费看牌 —— 这是 bot 被动化的
    核心漏洞。

    触发判据（全部连续指标，不依赖标签）：
      - is_pfr（hero 是 preflop 最后加注者）
      - not facing_bet（没人下注到 hero，hero 可主动）
      - spr ≥ 3（有 leverage 能做后街施压）
      - num_opponents ≤ 3（多人池 stab 过度危险，留给 range_cbet 处理）
      - 排除 air + 湿板组合（对手命中率高的场景不 stab）

    权重 0.45 比 default_check (0.3) 稍高，不和 thick_value/range_cbet
    直接竞争（他们权重 0.6-1.5）。sizer 25% pot—低风险小注探测对手。
    """
    id = 'default_stab'
    street_gate = ('flop', 'turn')

    def trigger(self, ctx: DecisionCtx) -> TriggerResult:
        if ctx.facing_bet or not ctx.is_pfr:
            return TriggerResult(False)
        if ctx.spr < 3.0:
            return TriggerResult(False)
        if ctx.num_opponents > 3:
            return TriggerResult(False)
        # 湿板 + air 桶：最危险组合（对手听牌可能性高，stab 失败率高）
        if ctx.board_sig.is_wet and ctx.hero_bucket == 'air':
            return TriggerResult(False)
        if ctx.equity_range < _DS_AIR_MIN_EQ:
            return TriggerResult(False)
        if ctx.num_opponents >= 2 and ctx.equity_range < max(0.40, _DS_AIR_MIN_EQ):
            return TriggerResult(False)
        if no_fold_equity(ctx) and ctx.equity_range < _DS_LOWFE_MIN_EQ:
            return TriggerResult(False)
        if ctx.hero_bucket in ('air', 'weak_draw') and no_fold_equity(ctx) and _DS_LOWFE_MULT <= 0:
            return TriggerResult(False)
        # 2026-04-28 P0.5：HU/多人 权重 env 可调。原 0.45 永远输给 thick_value(0.8+)
        # 和 range_cbet(0.8)，PFR check-frequency 实战 > 60%，远偏离业界 cbet ~55%。
        w = _DS_HU_W if ctx.num_opponents == 1 else _DS_MULTI_W
        if ctx.hero_bucket in ('air', 'weak_draw') and no_fold_equity(ctx):
            w *= _DS_LOWFE_MULT
        if ctx.hero_bucket in ('air', 'weak_draw', 'draw') and getattr(ctx, 'resistance_level', 0.0) > 0:
            w *= _BARREL_RESIST_WEIGHT_MULT
        return TriggerResult(True, w)

    def sizer(self, ctx: DecisionCtx) -> List[Tuple[float, float]]:
        # 25-33% pot —— 小注 stab，失败成本低
        return [(0.25, 0.6), (0.33, 0.4)]


# ---------------------------------------------------------------------------
# All active purposes
# ---------------------------------------------------------------------------


def all_active() -> list:
    return [
        RangeCbet(), PolarizedCbet(), ProtectionBet(),
        ThinValueBet(),
        MonsterValuePlan(), ThickValueBet(), BlockBet(),
        OverbetValue(), SemiBluff(), PureBluffRiver(),
        DelayedCbet(), ProbeBet(), FloatBet(),
        TurnDonk(), DoubleBarrel(), TripleBarrel(),
        StopAndGo(), ValueJam(),
        DefaultStab(),
    ]
