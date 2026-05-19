"""Passive / check-side purposes. doc 03 §4.2."""

from __future__ import annotations

from typing import List, Tuple

from pokerfate.strategy.v3.context import DecisionCtx
from pokerfate.strategy.v3.purpose import Purpose, TriggerResult


class TrapSlowPlay(Purpose):
    id = 'trap_slow_play'
    default_action = 'check'
    emits_bet = False

    def trigger(self, ctx: DecisionCtx) -> TriggerResult:
        if ctx.facing_bet:
            return TriggerResult(False)
        if ctx.hero_bucket != 'nuts':
            return TriggerResult(False)
        if ctx.spr < 4:
            return TriggerResult(False)
        # Trap is allowed as a single-street mix only. If flop/turn already
        # checked through, keep building value instead of giving two free cards.
        if ctx.street == 'turn' and (ctx.flop_checked_through
                                     or ctx.my_prev_actions.get('flop') == 'check'):
            return TriggerResult(False)
        if ctx.street == 'river' and (ctx.turn_checked_through
                                      or ctx.my_prev_actions.get('turn') == 'check'):
            return TriggerResult(False)
        vs = ctx.villain_stats
        # 慢打的唯一前提：对手会替你下注。
        #   - bluff_win_rate > 0.25（≥5 手 bet 样本）直接实锤爱诈唬
        #   - af > 2.0（≥20 手）激进下注倾向
        # 被动 sticky 对手（低 af、高 wtsd、低 river_fold）不会帮你发牌，
        # 慢打只会让你少收一街价值——由 sticky 指标统一否决，取代原
        # "calling_station/whale/fish" 标签分支。sticky 定义与 exploit.py
        # 的 _value_lean 基础口径一致，但这里只要触达中等粘性即否决。
        bluffy = False
        if vs.bet_win_count >= 5 and vs.bluff_win_rate > 0.25:
            bluffy = True
        if vs.hands_seen >= 20 and vs.af > 2.0:
            bluffy = True
        if not bluffy:
            return TriggerResult(False)
        sticky_signal = 0
        if vs.fold_to_cbet_opps >= 5 and vs.fold_to_cbet < 0.30:
            sticky_signal += 1
        if vs.hands_seen >= 20 and vs.wtsd > 0.32:
            sticky_signal += 1
        if vs.river_action_count >= 5 and vs.river_fold_rate < 0.30:
            sticky_signal += 1
        # 两个以上粘性证据 → 慢打退化为少收价值，否决
        if sticky_signal >= 2:
            return TriggerResult(False)
        # 权重随 trap_lean 连续放大：AF=2.2/bwr=0.30 → 0.5，AF=3.0/bwr=0.45 → ~0.85
        trap_strength = 0.0
        if vs.hands_seen >= 20:
            trap_strength += max(0.0, (vs.af - 1.8) * 0.30)
        if vs.bet_win_count >= 5:
            trap_strength += max(0.0, (vs.bluff_win_rate - 0.20) * 1.5)
        weight = max(0.5, min(1.0, 0.5 + trap_strength))
        return TriggerResult(True, weight)

    def sizer(self, ctx: DecisionCtx) -> List[Tuple[float, float]]:
        return []


class PotControl(Purpose):
    id = 'pot_control'
    default_action = 'check'
    emits_bet = False
    street_gate = ('turn', 'river')

    def trigger(self, ctx: DecisionCtx) -> TriggerResult:
        # 2026-04-25 P1-2：去 is_ip 硬门。OOP medium 牌到 turn/river
        # 同样需要 pot control 决策（不要"免费 check + 对手薄 value 打"
        # 这个反向思维——OOP check 本身就是 pot control，没有 IP 专属语义）。
        # default_action='check' + emits_bet=False 在 OOP 也合法。
        if ctx.facing_bet:
            return TriggerResult(False)
        if ctx.hero_bucket != 'medium':
            return TriggerResult(False)
        if ctx.street == 'river' and ctx.villain_vs_hero_dist:
            rel = ctx.villain_vs_hero_dist or {}
            hero_wins = float(rel.get('win', 0.0) or 0.0)
            ties = float(rel.get('tie', 0.0) or 0.0)
            villain_wins = float(rel.get('loss', 0.0) or 0.0)
            rel_eq = hero_wins + 0.5 * ties
            nuts = (ctx.villain_bucket_dist or {}).get('nuts', 0.0)
            if hero_wins >= 0.58 and rel_eq >= 0.58 and villain_wins <= 0.28 and nuts <= 0.25:
                return TriggerResult(False)
        vs = ctx.villain_stats
        sticky_value_target = (
            ctx.n_sticky >= 1
            or vs.vpip >= 0.40
            or (vs.hands_seen >= 20 and vs.wtsd > 0.28)
            or (vs.fold_to_cbet_opps >= 5 and vs.fold_to_cbet < 0.35)
            or (vs.river_action_count >= 5 and vs.river_fold_rate < 0.45)
            or (vs.hands_seen >= 20 and vs.af < 1.3)
        )
        if sticky_value_target and ctx.equity_range >= 0.58 and ctx.board_sig.wetness < 0.70:
            return TriggerResult(False)
        if ctx.board_sig.wetness < 0.55 and ctx.spr < 6:
            return TriggerResult(False)
        return TriggerResult(True, 0.4)

    def sizer(self, ctx: DecisionCtx) -> List[Tuple[float, float]]:
        return []


class DefaultCheck(Purpose):
    """Baseline — always a valid option when not facing a bet."""
    id = 'default_check'
    default_action = 'check'
    emits_bet = False

    def trigger(self, ctx: DecisionCtx) -> TriggerResult:
        # Always triggers (weight assigned by selector).
        return TriggerResult(not ctx.facing_bet, 0.3)

    def sizer(self, ctx: DecisionCtx) -> List[Tuple[float, float]]:
        return []


def all_passive() -> list:
    return [TrapSlowPlay(), PotControl(), DefaultCheck()]
