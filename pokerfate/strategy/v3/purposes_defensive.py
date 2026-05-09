"""Defensive (facing_bet=True) purposes. doc 03 §9."""

from __future__ import annotations

import os as _os
from typing import List, Tuple

from pokerfate.strategy.gto import GTOMath
from pokerfate.strategy.v3.context import DecisionCtx
from pokerfate.strategy.v3.exploit import AF_PASSIVE_BASELINE, no_fold_equity
from pokerfate.strategy.v3.purpose import Purpose, TriggerResult
from pokerfate.strategy.v3.stackoff_guard import stackoff_guard_reason

# 2026-04-25 参数扫描钩子：overbet fold 加权的 pot_odds 阈值（3 级累加）
# 默认保持 v2 配置 0.55 / 0.65 / 0.75。扫描后选中的最优值写到默认。
_BR_T1 = float(_os.environ.get('PF_BR_T1', '0.55'))
_BR_T2 = float(_os.environ.get('PF_BR_T2', '0.65'))
_BR_T3 = float(_os.environ.get('PF_BR_T3', '0.75'))
_PR_MIN_EQ = float(_os.environ.get('PF_PROTECTION_RAISE_MIN_EQ', '0.55'))
_PR_MEDIUM_ADD = float(_os.environ.get('PF_PROTECTION_RAISE_MEDIUM_ADD', '0.03'))
_PR_MULTIWAY_ADD = float(_os.environ.get('PF_PROTECTION_RAISE_MULTIWAY_ADD', '0.03'))
_PR_STICKY_ADD = float(_os.environ.get('PF_PROTECTION_RAISE_STICKY_ADD', '0.03'))
_PR_WETNESS_MIN = float(_os.environ.get('PF_PROTECTION_RAISE_WETNESS_MIN', '0.35'))
_PR_DRAW_MASS_MIN = float(_os.environ.get('PF_PROTECTION_RAISE_DRAW_MASS_MIN', '0.08'))
_PR_MAX_NUTS = float(_os.environ.get('PF_PROTECTION_RAISE_MAX_NUTS', '0.30'))
_PR_MAX_POT_ODDS = float(_os.environ.get('PF_PROTECTION_RAISE_MAX_POT_ODDS', '0.20'))
_PR_MIN_SPR = float(_os.environ.get('PF_PROTECTION_RAISE_MIN_SPR', '0.5'))
_PR_MAX_SPR = float(_os.environ.get('PF_PROTECTION_RAISE_MAX_SPR', '8.0'))
_PR_VALUE_DEFER_MARGIN = float(_os.environ.get('PF_PROTECTION_RAISE_VALUE_DEFER_MARGIN', '0.08'))
_PR_WEIGHT = float(_os.environ.get('PF_PROTECTION_RAISE_WEIGHT', '1.0'))
_PR_TINY_DONK_OVERPAIR_MAX_POT_ODDS = float(
    _os.environ.get('PF_PROTECTION_RAISE_TINY_DONK_OVERPAIR_MAX_POT_ODDS', '0.12')
)
_PR_TINY_DONK_OVERPAIR_MAX_SPR = float(
    _os.environ.get('PF_PROTECTION_RAISE_TINY_DONK_OVERPAIR_MAX_SPR', '2.5')
)
_PR_TINY_DONK_OVERPAIR_MIN_PRESSURE = float(
    _os.environ.get('PF_PROTECTION_RAISE_TINY_DONK_OVERPAIR_MIN_PRESSURE', '0.55')
)
_PR_TINY_DONK_OVERPAIR_MAX_NUTS = float(
    _os.environ.get('PF_PROTECTION_RAISE_TINY_DONK_OVERPAIR_MAX_NUTS', '0.20')
)
_PR_TINY_DONK_OVERPAIR_MIN_EQ = float(
    _os.environ.get('PF_PROTECTION_RAISE_TINY_DONK_OVERPAIR_MIN_EQ', '0.50')
)
_PR_TINY_DONK_OVERPAIR_WEIGHT = float(
    _os.environ.get('PF_PROTECTION_RAISE_TINY_DONK_OVERPAIR_WEIGHT', '2.5')
)
_ORJ_MIN_SPR = float(_os.environ.get('PF_OVERBET_RAISE_JAM_MIN_SPR', '2.0'))
_ORJ_MAX_SPR = float(_os.environ.get('PF_OVERBET_RAISE_JAM_MAX_SPR', '4.0'))
_ORJ_MIN_NUT_ADV = float(_os.environ.get('PF_OVERBET_RAISE_JAM_MIN_NUT_ADV', '0.30'))
_ORJ_MIN_EQ = float(_os.environ.get('PF_OVERBET_RAISE_JAM_MIN_EQ', '0.90'))
_ORJ_MAX_STRONG_VILLAIN_NUTS = float(
    _os.environ.get('PF_OVERBET_RAISE_JAM_MAX_STRONG_VILLAIN_NUTS', '0.55')
)
_ORJ_WEIGHT_BASE = float(_os.environ.get('PF_OVERBET_RAISE_JAM_WEIGHT_BASE', '7.0'))
_ORJ_WEIGHT_EQ_SCALE = float(_os.environ.get('PF_OVERBET_RAISE_JAM_WEIGHT_EQ_SCALE', '18.0'))
_ORJ_WEIGHT_NUTADV_SCALE = float(_os.environ.get('PF_OVERBET_RAISE_JAM_WEIGHT_NUTADV_SCALE', '4.0'))


def _villain_draw_mass(ctx: DecisionCtx) -> float:
    dist = ctx.villain_bucket_dist or {}
    return dist.get('draw', 0.0) + dist.get('weak_draw', 0.0)


def _draw_pressure(ctx: DecisionCtx) -> float:
    pressure = ctx.board_sig.wetness
    if ctx.board_sig.flush_draw or ctx.board_sig.flush_possible:
        pressure = max(pressure, 0.50)
    if ctx.board_sig.straight_draw_heavy:
        pressure = max(pressure, 0.50)
    pressure = max(pressure, _villain_draw_mass(ctx))
    return pressure


def _tiny_donk_overpair_protection(ctx: DecisionCtx, pressure: float, nuts: float) -> bool:
    """Low-SPR wet-board overpair should not let tiny donks realize equity."""
    return (
        ctx.street == 'flop'
        and ctx.hero_bucket == 'strong'
        and ctx.hero_made_subtype == 'clean_overpair'
        and ctx.spr <= _PR_TINY_DONK_OVERPAIR_MAX_SPR
        and ctx.pot_odds <= _PR_TINY_DONK_OVERPAIR_MAX_POT_ODDS
        and pressure >= _PR_TINY_DONK_OVERPAIR_MIN_PRESSURE
        and nuts <= _PR_TINY_DONK_OVERPAIR_MAX_NUTS
    )


def _protection_raise_need(ctx: DecisionCtx, pressure: float, nuts: float) -> float:
    need = _PR_MIN_EQ
    if ctx.hero_bucket == 'medium':
        need += _PR_MEDIUM_ADD
    if ctx.num_opponents >= 2:
        need += _PR_MULTIWAY_ADD
    if ctx.n_sticky >= 1:
        need += _PR_STICKY_ADD
    if _tiny_donk_overpair_protection(ctx, pressure, nuts):
        need = min(need, _PR_TINY_DONK_OVERPAIR_MIN_EQ)
    return need


def _opp_raise_premium(ctx: DecisionCtx) -> float:
    """villain 下注频率 → value_raise 门槛 premium（连续化）。

    原则：**bet 的强度与下注频率成反比**。对所有对手统一用 AF 连续映射。

      AF < 基线 → 下注更有选择 → bet range 紧 → +premium（尊重 passive bet）
      AF > 基线 → 下注频繁 → bet range 宽、不极化 → -premium
      AF = AF_PASSIVE_BASELINE → 无调整

    映射（线性）：
      premium = (AF_PASSIVE_BASELINE − AF) × 0.06，clamp 到 [-0.10, +0.15]
      乘以 pot_odds / 0.25 缩放（小注不值得尊重）

    数值示例（AF_PASSIVE_BASELINE = 1.5）：
      AF=0.3（很少下注） → +0.072 premium → value_raise need 0.79
      AF=1.5（基线）     → 0 premium     → need 0.72
      AF=3.0（频繁下注） → -0.090        → need 0.63

    对 whale 加 premium 是合理的——他下注时确实代表选择性判断。对
    whale 应该"多做 value"的 exploit 在 exploit.py 的 _value_lean
    驱动下独立生效，与 premium 不冲突。
    """
    vs = ctx.villain_stats
    premium = max(-0.10, min(0.15, (AF_PASSIVE_BASELINE - vs.af) * 0.06))
    scale = min(1.0, ctx.pot_odds / 0.25) if ctx.pot_odds > 0 else 0.0
    return premium * scale


# ---------------------------------------------------------------------------
# bluff_catch_call
# ---------------------------------------------------------------------------


class BluffCatchCall(Purpose):
    id = 'bluff_catch_call'
    facing_bet = True
    default_action = 'call'
    emits_bet = False

    def trigger(self, ctx: DecisionCtx) -> TriggerResult:
        if not ctx.facing_bet:
            return TriggerResult(False)
        # Accept any made-hand bucket. 'nuts' is critical — when hero holds a
        # nut hand but weighted-equity is compressed by a polarized villain
        # range (doc: H73 — 多人池 Jh 高顺面对 villain range 含 51% spade
        # flush combos → hero weighted eq 49%，够不到 value_raise 0.72 门槛
        # 但 pot odds 仍远低于 eq → call +EV)，BluffCatchCall 是唯一合法
        # call 路径；漏掉 nuts 会导致候选池只剩 fold，hero 弃掉赢定的牌。
        # draw / weak_draw 走 DrawCall（带 implied odds 奖励更合适）。
        # air 仍排除：eq 通常不够 pot_odds，真需要时走 fold baseline。
        if ctx.hero_bucket not in ('medium', 'strong', 'nuts'):
            return TriggerResult(False)
        adj = 0.0
        if ctx.villain_stats.bet_win_count >= 5:
            if ctx.villain_stats.bluff_win_rate < 0.12:
                adj += 0.04
            elif ctx.villain_stats.bluff_win_rate > 0.30:
                adj -= 0.04
        if ctx.board_sig.paired and not ctx.is_ip and ctx.pot_odds >= 0.30:
            adj += 0.06
        if ctx.villain_bucket_dist.get('nuts', 0.0) > 0.08:
            adj += 0.03

        need = ctx.pot_odds + adj
        if ctx.equity_range < need:
            return TriggerResult(False)
        # Vote weight — scales with equity margin over need. Ceiling kept at
        # 1.5 so that at strong equity (eq ≥ 0.75) value_raise still
        # dominates in the sampler (value_raise's weight grows past 2.1 in
        # that range; 67/33 split raise:call is closer to solver output
        # than a 50/50 mix).
        w = 0.5 + min(1.0, (ctx.equity_range - need) * 3.0)
        return TriggerResult(True, max(0.3, w))


# ---------------------------------------------------------------------------
# draw_call
# ---------------------------------------------------------------------------


class DrawCall(Purpose):
    id = 'draw_call'
    facing_bet = True
    default_action = 'call'
    emits_bet = False

    def trigger(self, ctx: DecisionCtx) -> TriggerResult:
        if not ctx.facing_bet:
            return TriggerResult(False)
        if ctx.hero_bucket not in ('draw', 'weak_draw'):
            return TriggerResult(False)
        if ctx.street == 'river':
            return TriggerResult(False)
        implied = GTOMath.implied_odds_bonus(ctx.spr, ctx.street)
        if ctx.num_opponents > 1:
            implied *= 0.7 ** (ctx.num_opponents - 1)
        if ctx.equity_range + implied < ctx.pot_odds:
            return TriggerResult(False)
        return TriggerResult(True, 0.6)


# ---------------------------------------------------------------------------
# value_raise (includes check-raise case)
# ---------------------------------------------------------------------------


class ValueRaise(Purpose):
    id = 'value_raise'
    facing_bet = True
    default_action = 'raise'
    emits_bet = True
    emits_raise = True

    def trigger(self, ctx: DecisionCtx) -> TriggerResult:
        if not ctx.facing_bet:
            return TriggerResult(False)
        need = 0.72 + _opp_raise_premium(ctx)
        if ctx.equity_range < need:
            return TriggerResult(False)
        if stackoff_guard_reason(ctx, self.id, will_jam=(ctx.spr <= 2.0)):
            return TriggerResult(False)
        # Vote weight grows monotonically past the trigger threshold and
        # sharply past 0.85 to dominate bluff_catch_call at near-nuts equity
        # (doc 03 §9.2 shape). Tuned so that:
        #   - eq 0.72 (边缘):  1.5 → ~50% raise vs typical bluff_catch 1.5
        #   - eq 0.80 (强档): 3.30 → ~69% raise (solver 65-85% range)
        #   - eq 0.90 (near-nuts): 6.0 → ~80% raise
        #   - eq 0.95 (nuts): 9.0 → ~86% raise
        # Piecewise-linear: 1.5 + 22×(eq-0.72) + extra 30×(eq-0.85) kicker.
        eq = ctx.equity_range
        w = 1.5 + 22.0 * max(0.0, eq - 0.72) + 30.0 * max(0.0, eq - 0.85)
        return TriggerResult(True, w)

    def sizer(self, ctx: DecisionCtx) -> List[Tuple[float, float]]:
        """Emits a 'to-amount' via special marker — engine resolves to raise amount.

        For uniformity we emit a nominal frac = 0 and signal jam via purpose
        interface in engine.
        """
        return []


# ---------------------------------------------------------------------------
# semi_bluff_raise
# ---------------------------------------------------------------------------


class SemiBluffRaise(Purpose):
    id = 'semi_bluff_raise'
    facing_bet = True
    default_action = 'raise'
    emits_bet = True
    emits_raise = True

    def trigger(self, ctx: DecisionCtx) -> TriggerResult:
        if not ctx.facing_bet:
            return TriggerResult(False)
        # 2026-04-25: 同 semi_bluff —— 实战 weak_draw 更常见，draw 桶几乎不
        # 触发。weak_draw + blocker 的 semi_bluff_raise 仍有 EV（blocker
        # 直接削弱对手 value 组合）。eq 门槛 0.22 防止 gutshot-only 硬 raise。
        if ctx.hero_bucket not in ('draw', 'weak_draw'):
            return TriggerResult(False)
        if ctx.hero_bucket == 'weak_draw' and ctx.equity_range < 0.22:
            return TriggerResult(False)
        if not (ctx.blockers.nut_flush_blocker or ctx.blockers.straight_blocker):
            return TriggerResult(False)
        if ctx.spr < 2.5:
            return TriggerResult(False)
        # Sticky villain 硬门：semi-bluff raise 的 EV 公式中 fold_equity 是
        # 主收入项；FE ≈ 0 时 raise 把 pot 放大只增加 reverse-implied 损失，
        # EV 结构性为负。用 exploit.no_fold_equity 公共判据（统一跨 purpose）。
        if no_fold_equity(ctx):
            return TriggerResult(False)
        return TriggerResult(True, 0.3 + 0.3 * ctx.equity_range)


# ---------------------------------------------------------------------------
# protection_raise
# ---------------------------------------------------------------------------


class ProtectionRaise(Purpose):
    id = 'protection_raise'
    facing_bet = True
    default_action = 'raise'
    emits_bet = True
    emits_raise = True

    def trigger(self, ctx: DecisionCtx) -> TriggerResult:
        if not ctx.facing_bet:
            return TriggerResult(False)
        if ctx.num_opponents > 3:
            return TriggerResult(False)
        if ctx.street not in ('flop', 'turn'):
            return TriggerResult(False)
        if ctx.spr < _PR_MIN_SPR or ctx.spr > _PR_MAX_SPR or ctx.pot <= 0:
            return TriggerResult(False)
        if ctx.to_call <= 0:
            return TriggerResult(False)
        if ctx.pot_odds > _PR_MAX_POT_ODDS:
            return TriggerResult(False)

        # Protection raise 的语义不是“近坚果价值加注”，而是“脆弱领先牌
        # 不想给多人/听牌便宜实现 equity”。因此必须有 draw pressure，且
        # 对手坚果密度不能过高；近坚果高 equity spot 让 value_raise 接管。
        if ctx.hero_bucket not in ('medium', 'strong'):
            return TriggerResult(False)
        pressure = _draw_pressure(ctx)
        if pressure < _PR_WETNESS_MIN and _villain_draw_mass(ctx) < _PR_DRAW_MASS_MIN:
            return TriggerResult(False)
        nuts = (ctx.villain_bucket_dist or {}).get('nuts', 0.0)
        if nuts > _PR_MAX_NUTS:
            return TriggerResult(False)

        tiny_donk_overpair = _tiny_donk_overpair_protection(ctx, pressure, nuts)
        need = _protection_raise_need(ctx, pressure, nuts)
        if ctx.equity_range < need:
            return TriggerResult(False)

        value_need = 0.72 + _opp_raise_premium(ctx)
        if ctx.hero_bucket == 'strong' and ctx.equity_range >= value_need + _PR_VALUE_DEFER_MARGIN:
            return TriggerResult(False)

        w = _PR_WEIGHT + max(0.0, ctx.equity_range - need) * 2.0 + pressure * 0.4
        if tiny_donk_overpair:
            w = max(w, _PR_TINY_DONK_OVERPAIR_WEIGHT)
        return TriggerResult(True, max(0.4, w))


# ---------------------------------------------------------------------------
# overbet_raise_jam
# ---------------------------------------------------------------------------


class OverbetRaiseJam(Purpose):
    id = 'overbet_raise_jam'
    facing_bet = True
    default_action = 'raise'
    emits_bet = True
    emits_raise = True

    def trigger(self, ctx: DecisionCtx) -> TriggerResult:
        if not ctx.facing_bet:
            return TriggerResult(False)
        if not (_ORJ_MIN_SPR < ctx.spr <= _ORJ_MAX_SPR):
            return TriggerResult(False)
        if ctx.hero_bucket not in ('strong', 'nuts'):
            return TriggerResult(False)
        if ctx.nut_advantage < _ORJ_MIN_NUT_ADV:
            return TriggerResult(False)
        if ctx.equity_range < _ORJ_MIN_EQ:
            return TriggerResult(False)
        if (ctx.hero_bucket == 'strong'
                and (ctx.villain_bucket_dist or {}).get('nuts', 0.0)
                > _ORJ_MAX_STRONG_VILLAIN_NUTS):
            return TriggerResult(False)
        if stackoff_guard_reason(ctx, self.id, will_jam=True):
            return TriggerResult(False)
        w = (
            _ORJ_WEIGHT_BASE
            + max(0.0, ctx.equity_range - _ORJ_MIN_EQ) * _ORJ_WEIGHT_EQ_SCALE
            + ctx.nut_advantage * _ORJ_WEIGHT_NUTADV_SCALE
        )
        return TriggerResult(True, max(1.5, w))


# ---------------------------------------------------------------------------
# fold (baseline)
# ---------------------------------------------------------------------------


class FoldPurpose(Purpose):
    """Fold 以独立 purpose 身份参与投票（2026-04-25 架构修正）。

    旧版：engine.py 用 baseline = 0.30 − 0.30×max_alt 的残量公式把 fold
    手动 append 到候选池，trigger 固定返回 0.3 但实际不被调用。后果：
      - max_alt ≥ 1.0 时 baseline=0 → fold 被完全挤出 → facing overbet
        场景灾难性 call-off（session 04-24 实测 5 次挤出累计 -909 BB）
      - max_alt 小时 fold 基线高 → marginal spot 随机抽到 fold → 弃掉
        价值牌（AA 超对等）

    新版：trigger 根据 (equity margin, equity_uncertainty, bet_ratio,
    villain bucket_dist.nuts) 返回动态 weight。engine.py 同步修改让 fold
    走 _collect_candidates 的标准投票流程。

    pessimistic_eq = equity_range - equity_uncertainty
    ↑ tracker 经实验证实在 single-action 下有 ±15-20% 结构性偏差；
      用悲观估计做决策让 fold 对 tracker 偏差鲁棒（见
      docs/策略修复/胜率模型校正.md）。
    """
    id = 'fold'
    facing_bet = True
    default_action = 'fold'
    emits_bet = False

    def trigger(self, ctx: DecisionCtx) -> TriggerResult:
        if not ctx.facing_bet:
            return TriggerResult(False)

        hero_is_top_tier = ctx.hero_bucket in ('nuts', 'strong')
        hero_is_draw = ctx.hero_bucket in ('draw', 'weak_draw')

        # Guard A：hero 有 NUTS / STRONG 档 + equity 显著超 pot_odds → 不弃
        # 保留旧"hero 有大牌绝不误弃"语义。
        if hero_is_top_tier and ctx.equity_range >= ctx.pot_odds + 0.15:
            return TriggerResult(False)

        # Guard B：hero 是 draw 听牌 → FoldPurpose 不参与，交给 DrawCall 基于
        # implied odds 判定。听牌的 EV 由 implied odds 补偿，直接算 eq vs
        # pot_odds 会漏算 +EV 跟注。
        if hero_is_draw:
            return TriggerResult(False)

        # 悲观 equity = point estimate 减 tracker 不确定度
        pessimistic_eq = ctx.equity_range - (ctx.equity_uncertainty or 0.0)

        # 硬门：悲观口径 equity 不足 → 强 fold
        if pessimistic_eq < ctx.pot_odds:
            return TriggerResult(True, 2.5)

        # Margin-based base weight（线性分段）：
        #   margin < 0.05  → w=1.5（勉强过门槛，fold 仍重）
        #   0.05-0.15      → w 1.0→0.3
        #   0.15-0.30      → w 0.3→0.05（margin 越大 fold 越轻）
        #   margin >= 0.30 → w=0.05（tiny bet + 大 eq 超额，几乎不 fold）
        margin = pessimistic_eq - ctx.pot_odds
        if margin < 0.05:
            w = 1.5
        elif margin < 0.15:
            w = 1.0 - (margin - 0.05) * 7.0
        elif margin < 0.30:
            w = 0.3 - (margin - 0.15) * (0.25 / 0.15)   # 0.15→0.3, 0.30→0.05
        else:
            w = 0.05

        # Villain bucket 坚果证据：极高 nut 比例下 fold 加权（hero 非 top 档时）
        nut_prob = (ctx.villain_bucket_dist or {}).get('nuts', 0.0)
        if nut_prob >= 0.50 and not hero_is_top_tier:
            w += 0.6
        if nut_prob >= 0.80 and not hero_is_top_tier:
            w += 0.6

        # Villain bet size 证据：pot_odds 高 = villain 下超额 pot 注
        # 数学关系：bet_ratio = pot_odds / (1 - pot_odds)
        #   pot_odds 0.55 ↔ bet_ratio 1.22（略超 pot）
        #   pot_odds 0.65 ↔ bet_ratio 1.86
        #   pot_odds 0.75 ↔ bet_ratio 3.00
        # 超额 pot bet 在 range 层强烈表达 polarization（nuts 或纯 bluff），
        # whale 桌上 "纯 bluff" 极少 → fold 加权 +EV。
        if not hero_is_top_tier:
            if ctx.pot_odds >= _BR_T1:
                w += 0.8
            if ctx.pot_odds >= _BR_T2:
                w += 0.6    # 累加
            if ctx.pot_odds >= _BR_T3:
                w += 0.4    # 再累加

        # Hero 自己是 air / weak → fold 至少保持 0.8 地板
        if ctx.hero_bucket in ('air', 'weak'):
            w = max(w, 0.8)

        return TriggerResult(True, max(0.0, w))


def all_defensive() -> list:
    return [BluffCatchCall(), DrawCall(), ValueRaise(), SemiBluffRaise(),
            ProtectionRaise(), OverbetRaiseJam(), FoldPurpose()]
