"""Postflop module — **thin compatibility layer** over v3 engine.

The legacy `PostflopStrategy` class (1000+ lines of hand-coded branches) has
been replaced by the purpose-first architecture in `pokerfate.strategy.v3`.
See docs/betting-redesign/03-new-betting-decision-design.md.

Why this file still exists:
 - `BoardTexture` is a small data class used by poker_bot's reasoning text.
 - `PostflopStrategy` is kept as a thin shim for existing imports. It builds
   a `DecisionCtx` from the legacy kwargs and delegates to `V3Engine`.
"""

from __future__ import annotations

import logging
import math
import os as _os
import random as _random_module
from collections import Counter
from typing import Dict, List, Optional, Tuple

# 2026-04-25 参数扫描（3-seed × 3 u_cap）：u_cap=0.20 合计 +652 BB，
# 显著优于 0.30（+529 BB）且方差小 15 倍。选 0.20 作默认。
_U_CAP = float(_os.environ.get('PF_U_CAP', '0.20'))

from pokerfate.core.card import Card
from pokerfate.strategy.v3 import (
    BlockerSet, DecisionCtx, DrawProfile, V3Engine, VillainStats,
)
from pokerfate.strategy.v3 import engine as _v3_engine
from pokerfate.strategy.v3 import early_relative as _v3_early_relative
from pokerfate.strategy.v3 import purposes_active as _v3_active
from pokerfate.strategy.v3 import purposes_defensive as _v3_defensive
from pokerfate.strategy.v3.stackoff_guard import stackoff_guard_reason


# ---------------------------------------------------------------------------
# equity_uncertainty 估计（见 docs/策略修复/胜率模型校正.md §路 A 诊断）
# ---------------------------------------------------------------------------

def _compute_equity_uncertainty(
    villain_bucket_dist: Dict[str, float],
    villain_stats: VillainStats,
    num_opponents: int,
    facing_bet: bool,
) -> float:
    """tracker 的 equity_range 点估计的悲观半宽 ∈ [0, 0.30]。

    只在 facing_bet 场景生效（不面对下注时 hero 可以用点估计做主动决策；
    真正灾难是 facing_bet 时点估计乐观导致的 call-off）。

    证据（见 docs/策略修复/胜率模型校正.md）：9174 条 ⚖ 校准记录按 villain
    真实 bucket 分组后 air -14.9% / nuts +23.5% 系统性偏差。四轮参数实验
    证实这是 GTO 表 + 6-bucket hand_categorizer 结构的数学天花板。

    估计用可量化信号加权：
      1. bucket_dist 熵：range 越分散 → 后验不稳 → uncertainty 升
      2. villain 被动特征（AF 低 / VPIP 高）：GTO 表对 whale 表达力差
      3. 多人池：range 独立假设不成立，uncertainty 随人数升
    """
    if not facing_bet:
        return 0.0

    u = 0.0

    # 信号 1: bucket_dist 分散度（熵归一化）
    if villain_bucket_dist:
        H = -sum(p * math.log(p + 1e-9) for p in villain_bucket_dist.values() if p > 0)
        # 6-bucket 均匀分布 H_max ≈ log(6) ≈ 1.79
        u += min(0.12, H / 14.9)  # H=1.79 → +0.12, H=0 → 0

    # 信号 2: villain 偏被动（polarization_index 低 → GTO 表适配性差）
    # 用 AF 和 VPIP 做 proxy（postflop 路径不一定能直接拿到 polarization_index）
    af = getattr(villain_stats, 'af', 1.5) or 1.5
    vpip = getattr(villain_stats, 'vpip', 0.25) or 0.25
    if af < 1.5 and vpip > 0.45:        # 典型 whale 画像
        u += 0.06
    elif af < 2.0 and vpip > 0.35:       # 偏 loose-passive
        u += 0.03

    # 信号 3: 多人池 range 不独立
    if num_opponents > 1:
        u += 0.03 * (num_opponents - 1)

    return min(_U_CAP, u)
from pokerfate.strategy.v3 import board as _v3_board
from pokerfate.strategy.range_v2.hand_categorizer import categorize_cards, made_hand_info

log = logging.getLogger(__name__)


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


def _hero_draw_profile(hole: List[Card], board: List[Card]) -> DrawProfile:
    """Classify hero's unfinished draw shape for DrawCall risk controls.

    This intentionally stays separate from the coarse hero_bucket classifier:
    older code may still call broadway four-liners "draw"; DrawCall needs the
    finer distinction between true 8-out draws, gutshots, backdoors, and
    overcards-only.
    """
    if len(hole) < 2 or len(board) < 3 or len(board) >= 5:
        return DrawProfile()

    cards = list(hole) + list(board)
    suit_counts = Counter(c.suit for c in cards)
    flush_draw = any(
        cnt >= 4 and any(h.suit == suit for h in hole)
        for suit, cnt in suit_counts.items()
    )
    backdoor_flush = (
        len(board) == 3
        and not flush_draw
        and any(
            cnt >= 3 and any(h.suit == suit for h in hole)
            for suit, cnt in suit_counts.items()
        )
    )

    all_ranks = {int(c.rank) for c in cards}
    hole_ranks = {int(c.rank) for c in hole}
    straight_out_ranks: set[int] = set()
    for seq in _STRAIGHT_SEQUENCES:
        present = seq & all_ranks
        if len(present) != 4:
            continue
        if not (hole_ranks & present):
            continue
        missing = seq - present
        if len(missing) == 1:
            straight_out_ranks.update(missing)

    oesd = len(straight_out_ranks) >= 2
    gutshot = len(straight_out_ranks) == 1

    top_board = max(int(c.rank) for c in board)
    overcards = all(int(c.rank) > top_board for c in hole)

    return DrawProfile(
        flush_draw=flush_draw,
        oesd=oesd,
        gutshot=gutshot,
        backdoor_flush=backdoor_flush,
        overcards=overcards,
    )


# ---------------------------------------------------------------------------
# BoardTexture — kept as a small public class used by reasoning text / tests
# ---------------------------------------------------------------------------


class BoardTexture:
    """Simple board texture wrapper (analytical fields used in log lines)."""

    def __init__(self, board: List[Card]):
        self.board = list(board)
        sig = _v3_board.analyze(list(board))
        self.wetness: float = sig.wetness
        self.is_paired: bool = sig.paired
        self.monotone: bool = sig.monotone
        self.flush_possible: bool = sig.flush_possible
        self.flush_draw: bool = sig.flush_draw
        self.straight_draw_heavy: bool = sig.straight_draw_heavy
        self.connectedness: float = sig.connectedness
        self.high_card_rank: int = sig.high_card_rank

    @property
    def is_dry(self) -> bool:
        return self.wetness < 0.35

    @property
    def is_wet(self) -> bool:
        return self.wetness >= 0.55

    @property
    def is_flush_heavy(self) -> bool:
        return self.monotone or (len(self.board) >= 4 and self._max_suit_count() >= 4)

    def _max_suit_count(self) -> int:
        if not self.board:
            return 0
        return max(Counter(c.suit for c in self.board).values())

    @property
    def connected(self) -> bool:
        return self.connectedness > 0.5

    def __repr__(self) -> str:
        return (f"BoardTexture(wetness={self.wetness:.2f}, paired={self.is_paired}, "
                f"flush_heavy={self.is_flush_heavy})")


def _pct(value: float) -> str:
    return f"{value * 100:.0f}%"


def _villain_draw_mass(ctx: DecisionCtx) -> float:
    dist = ctx.villain_bucket_dist or {}
    return float(dist.get('draw', 0.0) or 0.0) + float(dist.get('weak_draw', 0.0) or 0.0)


def _draw_pressure(ctx: DecisionCtx) -> float:
    pressure = float(ctx.board_sig.wetness or 0.0)
    if ctx.board_sig.flush_draw or ctx.board_sig.flush_possible:
        pressure = max(pressure, 0.50)
    if ctx.board_sig.straight_draw_heavy:
        pressure = max(pressure, 0.50)
    return max(pressure, _villain_draw_mass(ctx))


def _candidate_ids(out) -> set[str]:
    return {str(p) for p, _ in (getattr(out, 'candidates', None) or [])}


def _fold_override_note(ctx: DecisionCtx, out) -> str | None:
    if not ctx.facing_bet:
        return None
    reason = getattr(out, 'reason', '') or ''
    if out.purpose != 'fold_override_call' and 'fold-only guard' not in reason:
        return None
    gap = max(0.0, ctx.pot_odds - ctx.equity_range)
    nuts = float((ctx.villain_bucket_dist or {}).get('nuts', 0.0) or 0.0)
    tag = 'ok' if out.purpose == 'fold_override_call' else '-'
    if 'range_gap' in reason:
        tag = f"gap>{_pct(_v3_engine._FOLD_OVERRIDE_FOLD_ONLY_MAX_RANGE_GAP)}"
    elif 'bucket=' in reason:
        tag = 'bucket'
    elif 'low_spr' in reason:
        tag = f"spr<={_v3_engine._FOLD_OVERRIDE_LOW_SPR_DISABLE:.1f}"
    elif 'stack_commit' in reason:
        tag = f"commit>{_pct(_v3_engine._FOLD_OVERRIDE_STACK_COMMIT_DISABLE)}"
    elif 'fold_prob' in reason:
        tag = f"fold>{_pct(_v3_engine._FOLD_OVERRIDE_MAX_FOLD_PROB_WITH_CALL)}"
    elif 'river strong_mass' in reason:
        tag = f"strong>{_pct(_v3_engine._FOLD_OVERRIDE_RIVER_STRONG_MAX)}"
    elif 'rel_loss_dominant' in reason:
        tag = 'rel_loss'
    elif 'fragile_rel_eq' in reason:
        tag = 'rel_eq'
    elif 'fragile_rel_price' in reason:
        tag = 'rel_price'
    elif 'early_rel_risk' in reason:
        tag = 'early_rel'
    elif 'fragile ' in reason:
        tag = f"fragile>{_pct(_v3_engine._FOLD_OVERRIDE_FRAGILE_STRONG_MAX)}"
    elif 'blended_eq' in reason and out.purpose != 'fold_override_call':
        tag = 'blend<need'
    return (
        f"FO-{tag} eq={_pct(ctx.equity_range)} mc={_pct(ctx.equity_mc)} "
        f"po={_pct(ctx.pot_odds)} gap={_pct(gap)} nuts={_pct(nuts)}"
    )


def _protection_raise_note(ctx: DecisionCtx, out, ids: set[str]) -> str | None:
    active = out.purpose == 'protection_raise' or 'protection_raise' in ids
    pressure = _draw_pressure(ctx)
    near = (
        ctx.facing_bet
        and ctx.street in ('flop', 'turn')
        and ctx.hero_bucket in ('medium', 'strong')
        and ctx.to_call > 0
        and (active or pressure >= 0.25 or ctx.pot_odds <= _v3_defensive._PR_MAX_POT_ODDS + 0.05)
    )
    if not active and not near:
        return None

    nuts = float((ctx.villain_bucket_dist or {}).get('nuts', 0.0) or 0.0)
    need = _v3_defensive._protection_raise_need(ctx, pressure, nuts)
    tiny_donk_overpair = _v3_defensive._tiny_donk_overpair_protection(ctx, pressure, nuts)

    tag = 'ok'
    if ctx.num_opponents > 3:
        tag = f"opp>{3}"
    elif ctx.spr < _v3_defensive._PR_MIN_SPR or ctx.spr > _v3_defensive._PR_MAX_SPR:
        tag = 'spr'
    elif ctx.pot_odds > _v3_defensive._PR_MAX_POT_ODDS:
        tag = f"po>{_pct(_v3_defensive._PR_MAX_POT_ODDS)}"
    elif ctx.hero_bucket not in ('medium', 'strong'):
        tag = f"bucket={ctx.hero_bucket}"
    elif pressure < _v3_defensive._PR_WETNESS_MIN and _villain_draw_mass(ctx) < _v3_defensive._PR_DRAW_MASS_MIN:
        tag = f"pr<{_pct(_v3_defensive._PR_WETNESS_MIN)}"
    elif nuts > _v3_defensive._PR_MAX_NUTS:
        tag = f"nuts>{_pct(_v3_defensive._PR_MAX_NUTS)}"
    elif ctx.equity_range < need:
        tag = f"eq<{_pct(need)}"
    elif tiny_donk_overpair:
        tag = 'tiny'
    else:
        value_need = 0.72 + _v3_defensive._opp_raise_premium(ctx)
        if ctx.hero_bucket == 'strong' and ctx.equity_range >= value_need + _v3_defensive._PR_VALUE_DEFER_MARGIN:
            tag = 'value接管'

    return (
        f"PR-{tag} eq={_pct(ctx.equity_range)}/{_pct(need)} "
        f"spr={ctx.spr:.1f} po={_pct(ctx.pot_odds)} pr={_pct(pressure)} nuts={_pct(nuts)}"
    )


def _overbet_raise_jam_note(ctx: DecisionCtx, out, ids: set[str]) -> str | None:
    active = out.purpose == 'overbet_raise_jam' or 'overbet_raise_jam' in ids
    near = ctx.facing_bet and (
        active
        or ctx.hero_bucket in ('strong', 'nuts')
        or _v3_defensive._ORJ_MIN_SPR < ctx.spr <= _v3_defensive._ORJ_MAX_SPR
    )
    if not near:
        return None
    nuts = float((ctx.villain_bucket_dist or {}).get('nuts', 0.0) or 0.0)
    tag = 'ok'
    if not (_v3_defensive._ORJ_MIN_SPR < ctx.spr <= _v3_defensive._ORJ_MAX_SPR):
        tag = 'spr'
    elif ctx.hero_bucket not in ('strong', 'nuts'):
        tag = f"bucket={ctx.hero_bucket}"
    elif ctx.nut_advantage < _v3_defensive._ORJ_MIN_NUT_ADV:
        tag = f"na<{_pct(_v3_defensive._ORJ_MIN_NUT_ADV)}"
    elif ctx.equity_range < _v3_defensive._ORJ_MIN_EQ:
        tag = f"eq<{_pct(_v3_defensive._ORJ_MIN_EQ)}"
    elif ctx.hero_bucket == 'strong' and nuts > _v3_defensive._ORJ_MAX_STRONG_VILLAIN_NUTS:
        tag = f"nuts>{_pct(_v3_defensive._ORJ_MAX_STRONG_VILLAIN_NUTS)}"
    return (
        f"ORJ-{tag} eq={_pct(ctx.equity_range)}/{_pct(_v3_defensive._ORJ_MIN_EQ)} "
        f"na={_pct(ctx.nut_advantage)}/{_pct(_v3_defensive._ORJ_MIN_NUT_ADV)} spr={ctx.spr:.1f}"
    )


def _protection_bet_note(ctx: DecisionCtx, out, ids: set[str]) -> str | None:
    active = out.purpose == 'protection_bet' or 'protection_bet' in ids
    pressure = _draw_pressure(ctx)
    near = (
        not ctx.facing_bet
        and ctx.street in ('flop', 'turn')
        and ctx.hero_bucket in ('medium', 'strong')
        and (active or pressure >= 0.35)
    )
    if not near:
        return None
    nuts = float((ctx.villain_bucket_dist or {}).get('nuts', 0.0) or 0.0)
    need = _v3_active._PROTECTION_MIN_EQ
    medium_disabled = (
        ctx.hero_bucket == 'medium'
        and not _v3_active._ACTIVE_PROTECTION_MEDIUM_ENABLED
    )
    if ctx.hero_bucket == 'medium' and not medium_disabled:
        need = max(need, _v3_active._ACTIVE_PROTECTION_MEDIUM_MIN_EQ)
    if ctx.n_sticky >= 1:
        need += _v3_active._PROTECTION_STICKY_EQ_ADD
    if ctx.num_opponents >= 2:
        need += _v3_active._PROTECTION_MULTIWAY_EQ_ADD

    tag = 'ok'
    if ctx.hero_bucket not in ('medium', 'strong'):
        tag = f"bucket={ctx.hero_bucket}"
    elif medium_disabled:
        tag = 'medium-off'
    elif pressure < _v3_active._ACTIVE_PROTECTION_WETNESS_MIN:
        tag = f"pr<{_pct(_v3_active._ACTIVE_PROTECTION_WETNESS_MIN)}"
    elif nuts > _v3_active._ACTIVE_PROTECTION_MAX_NUTS:
        tag = f"nuts>{_pct(_v3_active._ACTIVE_PROTECTION_MAX_NUTS)}"
    elif ctx.spr < 3 or ctx.spr > 8:
        tag = 'spr'
    elif ctx.equity_range < need:
        tag = f"eq<{_pct(need)}"
    return (
        f"PB-{tag} eq={_pct(ctx.equity_range)}/{_pct(need)} "
        f"spr={ctx.spr:.1f} pr={_pct(pressure)} nuts={_pct(nuts)}"
    )


def _value_jam_note(ctx: DecisionCtx, out, ids: set[str]) -> str | None:
    active = out.purpose == 'value_jam' or 'value_jam' in ids
    near = (
        not ctx.facing_bet
        and ctx.hero_bucket in ('strong', 'nuts')
        and ctx.spr <= 4.0
        and ctx.equity_range >= 0.50
    )
    if not active and not near:
        return None
    rel_add = _v3_early_relative.value_jam_eq_add(ctx)
    need = _v3_active.commit_value_eq(ctx.spr) + _v3_active._river_danger_add(ctx) + rel_add
    tag = 'ok' if ctx.equity_range >= need else f"eq<{_pct(need)}"
    rel = f" erel+{_pct(rel_add)}" if rel_add > 0 else ""
    return f"VJ-{tag} eq={_pct(ctx.equity_range)}/{_pct(need)} spr={ctx.spr:.1f}{rel}"


def _early_relative_note(ctx: DecisionCtx, out, ids: set[str]) -> str | None:
    call_add = _v3_early_relative.call_margin_add(ctx)
    jam_add = _v3_early_relative.value_jam_eq_add(ctx)
    if call_add <= 0 and jam_add <= 0:
        return None
    if call_add > 0 and out.purpose not in {
        'bluff_catch_call', 'fold_override_call', 'fold',
    }:
        return None
    if jam_add > 0 and out.purpose != 'value_jam' and 'value_jam' not in ids:
        return None
    desc = _v3_early_relative.describe(ctx, active_value=jam_add > 0)
    add = call_add if call_add > 0 else jam_add
    return f"ER add={_pct(add)} {desc}"


def _stackoff_guard_note(ctx: DecisionCtx, out, ids: set[str]) -> str | None:
    watched = {'value_jam', 'value_raise', 'overbet_raise_jam', 'thick_value_bet', 'overbet_value'}
    selected = out.purpose.split("→", 1)[0] if out.purpose else ''
    if 'stackoff_guard' in (out.reason or ''):
        reason = (out.reason or '').replace('stackoff_guard ', '', 1)
        if reason.startswith('downsize '):
            return f"SG-down {selected} {reason[9:]} sub={ctx.hero_made_subtype or '-'}"
        return f"SG-block {selected} {reason} sub={ctx.hero_made_subtype or '-'}"
    if selected not in watched and not (ids & watched):
        return None
    if not ctx.board_sig.paired and ctx.hero_made_subtype not in {
        'trips_weak_kicker', 'trips_top_kicker', 'board_trips_kicker', 'trips',
    }:
        return None

    order = [selected] + [pid for pid in sorted(ids & watched) if pid != selected]
    for pid in order:
        will_jam = (
            pid in {'value_jam', 'overbet_raise_jam'}
            or (pid == 'value_raise' and ctx.spr <= 2.0)
            or (pid in {'thick_value_bet', 'overbet_value'} and getattr(out, 'jammed', False))
        )
        reason = stackoff_guard_reason(ctx, pid, will_jam=will_jam)
        if reason:
            return f"SG-block {pid} {reason} sub={ctx.hero_made_subtype or '-'}"
    return f"SG-ok sub={ctx.hero_made_subtype or '-'} spr={ctx.spr:.1f}"


def _resistance_note(ctx: DecisionCtx, out, ids: set[str]) -> str | None:
    if ctx.resistance_level <= 0:
        return None
    watched = {'default_stab', 'double_barrel', 'triple_barrel'}
    if out.purpose not in watched and not (ids & watched):
        return None
    raised = 'r' if ctx.prev_bet_raised else ''
    return f"R call={ctx.prev_bet_called_count}{raised} lvl={ctx.resistance_level:.2f}"


def _strategy_gate_notes(ctx: DecisionCtx, out) -> list[str]:
    ids = _candidate_ids(out)
    notes = [
        _fold_override_note(ctx, out),
        _protection_raise_note(ctx, out, ids),
        _overbet_raise_jam_note(ctx, out, ids),
        _protection_bet_note(ctx, out, ids),
        _stackoff_guard_note(ctx, out, ids),
        _value_jam_note(ctx, out, ids),
        _early_relative_note(ctx, out, ids),
        _resistance_note(ctx, out, ids),
    ]
    return [n for n in notes if n][:3]


# ---------------------------------------------------------------------------
# PostflopStrategy — compat shim over V3Engine
# ---------------------------------------------------------------------------


class PostflopStrategy:
    """Legacy API shim: `.decide(**kwargs)` → v3 engine under the hood.

    The old aggression/value_ag/bluff_ag/value_mult/is_station_sizing fields
    have been removed — v3 engine reads exploit signals directly from
    `ctx.villain_stats`. The only retained state is the cross-street memo
    and the diagnostic dicts read by poker_bot's log formatter.
    """

    def __init__(self, rng: Optional[_random_module.Random] = None) -> None:
        self._rng: _random_module.Random = rng or _random_module.Random()
        self._engine = V3Engine()

        # Cross-street memo (used by poker_bot's delayed-cbet detection).
        self._last_bet_frac: float = 0.0
        self._last_bet_street: str = ''
        self._last_decision_seed: int = 0
        self._last_cbet_detail: dict = {}
        self._last_bet_detail: dict = {}
        self._last_output = None  # type: Optional[object]

    # ------------------------------------------------------------------
    # Public API used by poker_bot / tests
    # ------------------------------------------------------------------

    def decide(
        self,
        equity: float,
        pot: float,
        to_call: float,
        stack: float,
        board: List[Card],
        is_ip: bool,
        street: str,
        facing_bet: bool,
        num_opponents: int,
        big_blind: float,
        effective_stack: Optional[float] = None,
        opponent_fold_rate: float = 0.45,
        fold_to_cbet: Optional[float] = None,
        spr: float = 5.0,
        value_only: bool = False,
        position: str = 'MP',
        is_drawing_heavy: bool = False,
        facing_large_bet: bool = False,
        exploit_tighten_call: bool = False,
        opponent_af: float = 1.5,
        nut_advantage: float = 0.0,
        is_delayed_cbet: bool = False,
        opponent_checked_back: bool = False,
        last_bet_frac: float = 0.0,
        villain_nuts_pct: float = 0.0,
        exploit_need_adjust: float = 0.0,
        hole_cards: Optional[List[Card]] = None,
        villain_stats: Optional[VillainStats] = None,
        is_pfr: Optional[bool] = None,
        worst_villain_stats: Optional[VillainStats] = None,
        max_value_lean: float = 0.0,
        max_trap_lean: float = 0.0,
        max_bluff_lean: float = 0.0,
        n_sticky: int = 0,
        villain_vs_hero_dist: Optional[Dict[str, float]] = None,
        my_prev_actions: Optional[dict] = None,
        opp_prev_actions: Optional[dict] = None,
        prev_bet_called_count: int = 0,
        prev_bet_raised: bool = False,
        prev_bet_was_multiway: bool = False,
        prev_bet_frac: float = 0.0,
        resistance_level: float = 0.0,
        equity_mc: Optional[float] = None,
        equity_range: Optional[float] = None,
        decision_seed: Optional[int] = None,
    ) -> Tuple[str, float]:
        """Wrap legacy kwargs → DecisionCtx → v3 engine.

        Returns (action, amount) with action in {'fold','check','call','raise'}.

        若 caller（poker_bot）能直接给出完整 VillainStats（通过
        OpponentStats.to_villain_stats() 构造），通过 ``villain_stats`` 参数
        传入，_build_ctx 会原样使用；否则回退到从 opponent_af /
        fold_to_cbet / value_only / opponent_fold_rate 拼装残缺版。
        """
        ctx = self._build_ctx(
            equity=equity, pot=pot, to_call=to_call, stack=stack,
            effective_stack=effective_stack, board=board,
            is_ip=is_ip, street=street, facing_bet=facing_bet,
            num_opponents=num_opponents, big_blind=big_blind, spr=spr,
            opponent_af=opponent_af, opponent_fold_rate=opponent_fold_rate,
            fold_to_cbet=fold_to_cbet, value_only=value_only, position=position,
            nut_advantage=nut_advantage, is_delayed_cbet=is_delayed_cbet,
            opponent_checked_back=opponent_checked_back,
            last_bet_frac=last_bet_frac, villain_nuts_pct=villain_nuts_pct,
            hole_cards=hole_cards,
            villain_stats=villain_stats,
            is_pfr=is_pfr,
            worst_villain_stats=worst_villain_stats,
            max_value_lean=max_value_lean,
            max_trap_lean=max_trap_lean,
            max_bluff_lean=max_bluff_lean,
            n_sticky=n_sticky,
            villain_vs_hero_dist=villain_vs_hero_dist,
            my_prev_actions=my_prev_actions,
            opp_prev_actions=opp_prev_actions,
            prev_bet_called_count=prev_bet_called_count,
            prev_bet_raised=prev_bet_raised,
            prev_bet_was_multiway=prev_bet_was_multiway,
            prev_bet_frac=prev_bet_frac,
            resistance_level=resistance_level,
            equity_mc=equity_mc,
            equity_range=equity_range,
            decision_seed=decision_seed,
        )

        out = self._engine.decide(ctx)
        self._last_output = out
        self._last_decision_seed = out.seed
        strategy_gates = _strategy_gate_notes(ctx, out)
        # Populate diagnostic dicts with v3-native fields. Keys are read by
        # poker_bot._postflop_reasoning for the per-decision log line.
        self._last_cbet_detail = {
            'purpose': out.purpose,
            'action': out.action,
            'frac': out.frac,
            'jammed': out.jammed,
            'downgraded_to_check': out.downgraded_to_check,
            'candidates': out.candidates,            # [(purpose_id, prob), ...]
            'alpha': out.alpha,                       # AlphaCheckResult | None
            'exploit_deltas': out.exploit_deltas,    # {purpose_id: multiplier}
            'reason': out.reason,
            'arbitration_mode': out.arbitration_mode,
            'top_gap': out.top_gap,
            'leverage_flags': out.leverage_flags,
            'strategy_gates': strategy_gates,
            'hero_made_subtype': ctx.hero_made_subtype,
            'hero_hand_rank': ctx.hero_hand_rank,
            'hero_kicker_rank': ctx.hero_kicker_rank,
            'board_pair_rank': ctx.board_pair_rank,
            'pocket_pair_rank': ctx.pocket_pair_rank,
            'villain_vs_hero_dist': dict(ctx.villain_vs_hero_dist or {}),
            'seed': out.seed,
        }
        self._last_bet_detail = {
            'street': street, 'frac': round(out.frac, 3),
            'reason': out.reason, 'spr': round(spr, 2),
            'nut_adv': round(nut_advantage, 3),
            'jammed': out.jammed,
            'arbitration_mode': out.arbitration_mode,
            'top_gap': round(out.top_gap, 3),
            'leverage_flags': out.leverage_flags,
            'strategy_gates': strategy_gates,
        }
        # Track last bet fraction so downstream callers (poker_bot) can feed
        # it back as multi-street consistency input.
        if street == 'flop' and out.action in ('bet', 'raise'):
            self._last_bet_frac = out.frac
            self._last_bet_street = 'flop'

        # Normalize action label: v3 emits 'bet' on open, legacy expected 'raise'.
        action_out = out.action
        if action_out == 'bet':
            action_out = 'raise'
        return action_out, out.amount

    # ------------------------------------------------------------------
    # ctx construction
    # ------------------------------------------------------------------

    def _build_ctx(
        self, *, equity: float, pot: float, to_call: float, stack: float,
        effective_stack: Optional[float] = None,
        board: List[Card], is_ip: bool, street: str, facing_bet: bool,
        num_opponents: int, big_blind: float, spr: float,
        opponent_af: float, opponent_fold_rate: float,
        fold_to_cbet: Optional[float], value_only: bool, position: str,
        nut_advantage: float, is_delayed_cbet: bool, opponent_checked_back: bool,
        last_bet_frac: float, villain_nuts_pct: float,
        hole_cards: Optional[List[Card]],
        villain_stats: Optional[VillainStats] = None,
        is_pfr: Optional[bool] = None,
        worst_villain_stats: Optional[VillainStats] = None,
        max_value_lean: float = 0.0,
        max_trap_lean: float = 0.0,
        max_bluff_lean: float = 0.0,
        n_sticky: int = 0,
        villain_vs_hero_dist: Optional[Dict[str, float]] = None,
        my_prev_actions: Optional[dict] = None,
        opp_prev_actions: Optional[dict] = None,
        prev_bet_called_count: int = 0,
        prev_bet_raised: bool = False,
        prev_bet_was_multiway: bool = False,
        prev_bet_frac: float = 0.0,
        resistance_level: float = 0.0,
        equity_mc: Optional[float] = None,
        equity_range: Optional[float] = None,
        decision_seed: Optional[int] = None,
    ) -> DecisionCtx:
        hole = list(hole_cards) if hole_cards else []
        board_list = list(board)

        # Board signals
        board_sig = _v3_board.analyze(board_list)

        # Hero bucket
        if hole and len(board_list) >= 3:
            try:
                hero_bucket = categorize_cards(hole, board_list)
                hmi = made_hand_info(hole, board_list)
            except Exception:
                log.exception(
                    "hero bucket categorization failed hole=%s board=%s",
                    [str(c) for c in hole],
                    [str(c) for c in board_list],
                )
                hero_bucket = 'medium'
                hmi = made_hand_info([], [])
        else:
            hero_bucket = 'medium'
            hmi = made_hand_info([], [])

        # Blockers
        bl = _v3_board.detect_blockers(hole, board_list) if hole else {
            'nut_flush_blocker': False, 'set_blocker': False, 'straight_blocker': False,
        }
        blockers = BlockerSet(**bl)
        draw_profile = _hero_draw_profile(hole, board_list) if hole else DrawProfile()

        # Villain stats — caller 可以直接传入完整 VillainStats（推荐路径），
        # 这样 hands_seen / wtsd / bluff_win_rate / bet_win_count / flop_afq /
        # turn_afq / river_afq / wmsd 等字段都能真实反映对手历史。
        # 若未传入则走 legacy fallback（从散标量拼装残缺版，_trap_lean 等
        # 需要 hands_seen/bet_win_count 的路径将不生效）。
        if villain_stats is not None:
            vs = villain_stats
        else:
            vs = VillainStats(
                af=opponent_af,
                fold_to_cbet=fold_to_cbet if fold_to_cbet is not None else opponent_fold_rate,
                fold_to_cbet_opps=5 if fold_to_cbet is not None else 0,
                hands_seen=30 if value_only else 0,
                wtsd=0.40 if value_only else 0.25,
                river_fold_rate=opponent_fold_rate,
                river_action_count=5 if value_only else 0,
            )

        # Villain bucket distribution: seed nuts% from caller; distribute
        # remaining among medium/weak_draw proportionally.
        nuts = max(0.0, min(1.0, villain_nuts_pct))
        remain = 1.0 - nuts
        vbd = {
            'nuts': nuts,
            'strong': remain * 0.25,
            'medium': remain * 0.30,
            'draw': remain * 0.10,
            'weak_draw': remain * 0.20,
            'air': remain * 0.15,
        }

        eq_range = equity if equity_range is None else equity_range
        eq_mc = eq_range if equity_mc is None else equity_mc
        effective_call = min(to_call, stack) if (to_call > 0 and stack > 0) else to_call
        pot_odds = (
            effective_call / (pot + effective_call)
            if effective_call > 0 and (pot + effective_call) > 0 else 0.0
        )
        compression = eq_range / max(1e-9, eq_mc)

        # is_pfr 必须由 preflop 真实动作决定（hero 是否为 last raiser），
        # 不能从 postflop 行为回推——limp pot 里 BB free check 后 flop
        # check-through 会让 is_delayed_cbet=True，但 hero 并不是 PFR。
        # 若 caller 传入 is_pfr（推荐路径，poker_bot 跟踪 preflop 动作）则
        # 直接使用；否则回退到旧的错误代理以保持兼容（会在 limp pot 误报）。
        if is_pfr is None:
            is_pfr = is_delayed_cbet  # legacy fallback — known to misfire in limp pots
        flop_checked_through = is_delayed_cbet or opponent_checked_back

        # 2026-04-25：equity_uncertainty — tracker 的 equity 估计经 A/B 实验证实
        # 在 single-action 场景下有 ±15-20% 结构性偏差（GTO 表 + 6-bucket 的数学
        # 上限；见 docs/策略修复/胜率模型校正.md）。在消费端加 robust margin：
        #   pessimistic_eq = equity_range - equity_uncertainty
        # 下面的 trigger 条件（FoldPurpose 等）用 pessimistic_eq 做判定，避免被
        # +20% 高估拖入灾难 call。
        equity_uncertainty = _compute_equity_uncertainty(
            vbd, vs, num_opponents, facing_bet,
        )

        ctx = DecisionCtx(
            street=street,
            hole_cards=hole,
            board=board_list,
            position=position,
            is_ip=is_ip,
            num_opponents=num_opponents,
            pot=pot,
            to_call=to_call,
            stack=stack,
            effective_stack=(
                float(effective_stack)
                if effective_stack is not None and effective_stack > 0
                else float(stack)
            ),
            big_blind=big_blind,
            spr=spr,
            pot_odds=pot_odds,
            facing_bet=facing_bet,
            facing_large_bet=(pot_odds >= 0.30 and spr < 5),
            hero_bucket=hero_bucket,
            hero_made_subtype=hmi.subtype,
            hero_hand_rank=hmi.hand_rank,
            hero_made_rank=hmi.made_rank,
            hero_kicker_rank=hmi.kicker_rank,
            board_pair_rank=hmi.board_pair_rank,
            pocket_pair_rank=hmi.pocket_pair_rank,
            equity_mc=eq_mc,
            equity_range=eq_range,
            equity_uncertainty=equity_uncertainty,
            compression=compression,
            nut_advantage=nut_advantage,
            draw=draw_profile,
            blockers=blockers,
            board_sig=board_sig,
            villain_bucket_dist=vbd,
            villain_vs_hero_dist=dict(villain_vs_hero_dist or {}),
            villain_stats=vs,
            exploit_adj={},
            worst_villain_stats=worst_villain_stats if worst_villain_stats is not None else vs,
            max_value_lean=max_value_lean,
            max_trap_lean=max_trap_lean,
            max_bluff_lean=max_bluff_lean,
            n_sticky=n_sticky,
            # 2026-04-25 修 P0 bug：my_prev_actions / opp_prev_actions 之前
            # 只在 is_delayed_cbet / opponent_checked_back 的 'check' 情况
            # 填充 → double_barrel / triple_barrel / stop_and_go / float_bet
            # 永远查不到 'bet' 或 'check' 历史，触发率 0%。
            # 现在优先用 caller 传入的完整 dict（poker_bot 跟踪的全部动作），
            # fallback 到旧行为以保持兼容。
            my_prev_actions=(my_prev_actions if my_prev_actions is not None
                             else ({'flop': 'check'} if is_delayed_cbet else {})),
            opp_prev_actions=(opp_prev_actions if opp_prev_actions is not None
                              else ({'flop': 'check'} if opponent_checked_back else {})),
            last_bet_frac=last_bet_frac,
            prev_bet_called_count=max(0, int(prev_bet_called_count)),
            prev_bet_raised=bool(prev_bet_raised),
            prev_bet_was_multiway=bool(prev_bet_was_multiway),
            prev_bet_frac=float(prev_bet_frac or 0.0),
            resistance_level=max(0.0, min(1.0, float(resistance_level or 0.0))),
            is_pfr=is_pfr,
            flop_checked_through=flop_checked_through,
            rng=self._rng,
            seed=int(decision_seed or 0),
        )
        return ctx
