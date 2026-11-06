"""Active-side (no facing bet) purposes. doc 03 §4.2 / §4.3.

# Selected active-purpose parameters are kept as code constants so the current
# strategy version is explicit. Coarse feature switches below remain env-gated.
"""

from __future__ import annotations

import os as _os
from typing import List, Optional, Tuple

from pokerfate.strategy.v3 import bluff_context, draw_quality, early_relative
from pokerfate.strategy.v3.context import DecisionCtx
from pokerfate.strategy.v3.exploit import no_fold_equity, sticky_passive
from pokerfate.strategy.v3.purpose import Purpose, TriggerResult
from pokerfate.strategy.v3.stackoff_guard import stackoff_guard_reason

_RC_WET_PEN = 0.5
_RC_LOWBROAD_PEN = 0.7
_RC_FLUSH_PEN = 0.5
_RC_PAIRED_PEN = 0.6
_DS_HU_W = 0.65
_DS_MULTI_W = 0.55
_DS_AIR_MIN_EQ = 0.25
_DS_LOWFE_MULT = 0.0
_DS_LOWFE_MIN_EQ = 0.35
_COMMIT_VALUE_EQ_FLOOR = 0.55
_VALUE_JAM_RIVER_DANGER_ADD = 0.04
_VALUE_JAM_PAIRED_ADD = 0.05
_VALUE_JAM_COMPLETING_ADD = 0.04
_PROTECTION_MIN_EQ = 0.40
_PROTECTION_STICKY_EQ_ADD = 0.03
_PROTECTION_MULTIWAY_EQ_ADD = 0.04
_ACTIVE_PROTECTION_MEDIUM_ENABLED = True
# Medium protection is default-on, but only for stable made hands on draw-heavy
# boards. The old default-off state made top pair / clean overpair give too many
# free cards in loose games.
_ACTIVE_PROTECTION_MEDIUM_MIN_EQ = 0.55
_ACTIVE_PROTECTION_MEDIUM_MIN_MC = 0.50
_ACTIVE_PROTECTION_MEDIUM_MAX_NUTS = 0.22
_ACTIVE_PROTECTION_MEDIUM_DRAW_MASS_MIN = 0.15
_ACTIVE_PROTECTION_WETNESS_MIN = 0.45
_ACTIVE_PROTECTION_MAX_NUTS = 0.35
_RIVER_THIN_VALUE_MIN_EQ = 0.58
_RIVER_THIN_VALUE_MIN_WORSE = 0.58
_RIVER_THIN_VALUE_MAX_LOSS = 0.28
_RIVER_THIN_VALUE_MAX_NUTS = 0.25
_RIVER_CHECKED_THIN_MIN_REL_EQ = 0.60
_RIVER_CHECKED_THIN_MAX_LOSS = 0.32
_RIVER_CHECKED_THIN_MIN_WIN_GAP = 0.15
_RIVER_CHECKED_THIN_MIN_PAYING = 0.34
_RIVER_CHECKED_THIN_MAX_NUTS = 0.20
_PURE_BLUFF_ENABLED = _os.environ.get('PF_PURE_BLUFF_ENABLED', '1').lower() not in {'0', 'false', 'off', 'no'}
_PURE_BLUFF_CATCHER_MIN = 0.42
_PURE_BLUFF_FE_MARGIN = 0.02
_PURE_BLUFF_UNBLOCKER_PENALTY = 0.24
_BARREL_RESIST_CALL_EQ_ADD = 0.04
_BARREL_RESIST_RAISE_EQ_ADD = 0.10
_BARREL_RESIST_WEIGHT_MULT = 0.70
_SUPER_MONSTER_EQ = 0.985
_SUPER_MONSTER_MC = 0.95
_SUPER_MONSTER_MAX_VILLAIN_NUTS = 0.02
_MONSTER_EQ = 0.92
_MONSTER_MC = 0.85
_MONSTER_MAX_VILLAIN_NUTS = 0.10
_MONSTER_AIR_WEAK_MIN = 0.50
_MONSTER_PAYING_MIN = 0.35
_MONSTER_DRAW_PRESSURE_MIN = 0.15
_RIVER_FRAGILE_VALUE_MAX_LOSS = 0.18
_RIVER_FRAGILE_VALUE_MIN_REL_EQ = 0.72
_RIVER_MEDIUM_JAM_MIN_WIN = 0.75
_RIVER_MEDIUM_JAM_MAX_LOSS = 0.20
_RIVER_MEDIUM_DANGER_JAM_MIN_WIN = 0.82
_RIVER_MEDIUM_DANGER_JAM_MAX_LOSS = 0.15
_RIVER_MEDIUM_PROBE_MIN_REL_EQ = 0.55
_RIVER_MEDIUM_PROBE_MIN_WIN_GAP = 0.10
_BLUFF_CONTEXT_DELAYED_MIN = 0.55
_BLUFF_CONTEXT_PROBE_FLOAT_MIN = 0.50
_BLUFF_CONTEXT_BARREL_MIN = 0.58
_BLUFF_CONTEXT_RIVER_MIN = 0.48
_PROFIT_EXPAND_V1 = _os.environ.get('PF_POSTFLOP_PROFIT_EXPAND_V1', '0') == '1'
_PROFIT_PAID_VALUE_ENABLED = _os.environ.get(
    'PF_PROFIT_PAID_VALUE_ENABLED', '1'
).lower() not in {'0', 'false', 'off', 'no'}
_CAPPED_BLUFF_EXPAND_ENABLED = _os.environ.get(
    'PF_CAPPED_BLUFF_EXPAND_ENABLED', '1'
).lower() not in {'0', 'false', 'off', 'no'}
_PE_FLOP_MAX_NUTS = 0.22
_PE_FLOP_MAX_STRONG_NUTS = 0.55
_PE_TURN_MAX_NUTS = 0.18
_PE_TURN_MAX_STRONG_NUTS = 0.52
_PE_PAID_VALUE_MAX_NUTS = 0.26
_PE_PAID_VALUE_MIN_PAYING = 0.34
_PE_PAID_VALUE_MIN_DRAW_PRESSURE = 0.12
_CAPPED_BLUFF_MIN_FOLD = 0.55
_CAPPED_BLUFF_MIN_SCORE = 0.50
_CAPPED_BLUFF_MAX_NUTS = 0.12
_CAPPED_BLUFF_MAX_STRONG_NUTS = 0.45
_SAFE_VALUE_EXPAND_MIN_EQ = 0.54
_SAFE_VALUE_EXPAND_MIN_MC = 0.56
_SAFE_VALUE_EXPAND_MIN_PAYING = 0.42
_SAFE_VALUE_EXPAND_MAX_NUTS = 0.14
_SAFE_VALUE_EXPAND_MAX_LOSS = 0.35
_SAFE_VALUE_EXPAND_MIN_REL_EQ = 0.55


# ---------------------------------------------------------------------------
# Small shared helpers
# ---------------------------------------------------------------------------

def _villain_caps(ctx: DecisionCtx) -> bool:
    return ctx.villain_bucket_dist.get('nuts', 0.0) <= 0.08


def _bluff_catcher_density(ctx: DecisionCtx) -> float:
    return (ctx.villain_bucket_dist.get('medium', 0.0)
            + ctx.villain_bucket_dist.get('weak_draw', 0.0))


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def _pure_bluff_required_fe(frac: float) -> float:
    if frac <= 0:
        return 0.0
    return frac / (1.0 + frac)


def _river_fold_estimate(ctx: DecisionCtx) -> float:
    vs = ctx.villain_stats
    if vs.river_action_count >= 5 or vs.river_fold_rate > 0.50:
        return _clamp01(vs.river_fold_rate)
    if vs.fold_to_cbet_opps >= 5:
        return _clamp01(vs.fold_to_cbet - 0.05)
    return 0.38


def _worst_river_fold_estimate(ctx: DecisionCtx, primary: float) -> float:
    vs = ctx.worst_villain_stats
    if vs.river_action_count >= 5 or vs.river_fold_rate > 0.50:
        return _clamp01(vs.river_fold_rate)
    if vs.fold_to_cbet_opps >= 5:
        return _clamp01(vs.fold_to_cbet - 0.05)
    return _clamp01(primary - 0.08)


def _pure_bluff_field_fe(ctx: DecisionCtx) -> float:
    primary = _river_fold_estimate(ctx)
    if ctx.num_opponents <= 1:
        return primary
    if ctx.num_opponents == 2:
        return primary * _worst_river_fold_estimate(ctx, primary)
    return 0.0


def _pure_bluff_fe_ok(ctx: DecisionCtx, blf, frac: float) -> bool:
    context_bonus = min(0.06, 0.04 * blf.blocker_score + 0.03 * blf.story_score)
    return _pure_bluff_field_fe(ctx) + context_bonus >= _pure_bluff_required_fe(frac) + _PURE_BLUFF_FE_MARGIN


def _missed_flush_unblocker_penalty(ctx: DecisionCtx) -> float:
    if ctx.board_sig.flush_possible or not ctx.board_sig.flush_draw:
        return 0.0
    suits: dict[object, int] = {}
    for c in ctx.board:
        suits[c.suit] = suits.get(c.suit, 0) + 1
    draw_suits = {suit for suit, count in suits.items() if count == 2}
    if not draw_suits:
        return 0.0
    held_draw_suit = sum(1 for c in ctx.hole_cards if c.suit in draw_suits)
    return min(_PURE_BLUFF_UNBLOCKER_PENALTY, 0.12 * held_draw_suit)


def _missed_straight_unblocker_penalty(ctx: DecisionCtx) -> float:
    if ctx.board_sig.straight_possible or not ctx.board_sig.straight_draw_heavy:
        return 0.0
    ranks = {int(c.rank) for c in ctx.board}
    if not ranks:
        return 0.0
    top = max(ranks)
    windows = [set(range(lo, lo + 5)) for lo in range(2, 11)]
    live_windows = [w for w in windows if len(w & ranks) >= 3 and top in w]
    if not live_windows:
        return 0.0
    held = {int(c.rank) for c in ctx.hole_cards}
    if not any(held & (w - ranks) for w in live_windows):
        return 0.0
    return 0.08


def _pure_bluff_blocker_quality(ctx: DecisionCtx, blf) -> float:
    penalty = _missed_flush_unblocker_penalty(ctx) + _missed_straight_unblocker_penalty(ctx)
    quality = blf.blocker_score - min(_PURE_BLUFF_UNBLOCKER_PENALTY, penalty)
    if ctx.blockers.set_blocker and not (ctx.blockers.nut_flush_blocker or ctx.blockers.straight_blocker):
        quality -= 0.08
    return _clamp01(quality)


def _pure_bluff_blocker_need(ctx: DecisionCtx, blf) -> float:
    if blf.air_weak >= 0.45 and _pure_bluff_field_fe(ctx) >= 0.62 and blf.nuts <= 0.08:
        return 0.0
    need = 0.30 if (blf.air_weak >= 0.35 or _pure_bluff_field_fe(ctx) >= 0.55) else 0.40
    if _pure_bluff_field_fe(ctx) < 0.45:
        need = max(need, 0.45)
    if ctx.num_opponents == 2:
        need = max(need, 0.55)
    return need


def _pure_bluff_blocker_ok(ctx: DecisionCtx, blf, quality: float) -> bool:
    need = _pure_bluff_blocker_need(ctx, blf)
    if need <= 0.0:
        return True
    return quality >= need


def _pure_bluff_player_count_ok(ctx: DecisionCtx, blf, quality: float) -> bool:
    if ctx.num_opponents <= 1:
        return True
    if ctx.num_opponents >= 3:
        return False
    worst = ctx.worst_villain_stats
    worst_no_fe = worst.fold_to_cbet_opps >= 5 and worst.fold_to_cbet <= 0.30
    worst_sticky = (
        ctx.n_sticky > 0
        or ctx.max_value_lean >= 1.20
        or worst.wtsd >= 0.32
        or (worst.river_action_count >= 5 and worst.river_fold_rate < 0.45)
    )
    return (
        not worst_no_fe
        and not worst_sticky
        and blf.nuts <= 0.12
        and blf.strong_nuts <= 0.40
        and blf.air_weak + blf.medium >= 0.60
        and quality >= 0.55
    )


def _pure_bluff_river_fracs(ctx: DecisionCtx, blf=None) -> List[Tuple[float, float]]:
    blf = blf or bluff_context.evaluate(ctx)
    quality = _pure_bluff_blocker_quality(ctx, blf)
    if quality <= 0.0:
        if (
            ctx.num_opponents == 1
            and _river_fold_estimate(ctx) >= 0.65
            and blf.air_weak >= 0.45
            and blf.nuts <= 0.08
            and _pure_bluff_fe_ok(ctx, blf, 0.66)
        ):
            return [(0.66, 1.0)]
        return []
    base = [(0.50, 0.55), (0.66, 0.45)] if ctx.num_opponents == 2 else [(0.66, 0.4), (0.75, 0.3), (1.00, 0.3)]
    return [(frac, weight) for frac, weight in base if _pure_bluff_fe_ok(ctx, blf, frac)]


def _bucket_mass(ctx: DecisionCtx, *names: str) -> float:
    dist = ctx.villain_bucket_dist or {}
    return sum(dist.get(name, 0.0) for name in names)


def _villain_nuts(ctx: DecisionCtx) -> float:
    return (ctx.villain_bucket_dist or {}).get('nuts', 0.0)


def _draw_pressure_mass(ctx: DecisionCtx) -> float:
    dist = ctx.villain_bucket_dist or {}
    return dist.get('draw', 0.0) + 0.5 * dist.get('weak_draw', 0.0)


def _relative_hero_wins(ctx: DecisionCtx) -> Tuple[float, float, float, float]:
    rel = ctx.villain_vs_hero_dist or {}
    hero_wins = float(rel.get('win', 0.0) or 0.0)
    ties = float(rel.get('tie', 0.0) or 0.0)
    villain_wins = float(rel.get('loss', 0.0) or 0.0)
    rel_eq = hero_wins + 0.5 * ties
    return hero_wins, ties, villain_wins, rel_eq


def _paying_bucket_mass(ctx: DecisionCtx) -> float:
    """Approximate worse-hand call mass for value bets."""
    return (
        _bucket_mass(ctx, 'medium')
        + 0.5 * _bucket_mass(ctx, 'strong')
        + 0.4 * _bucket_mass(ctx, 'weak_draw')
    )


def _safe_medium_protection_hand(ctx: DecisionCtx) -> bool:
    return ctx.hero_made_subtype in {
        'top_pair_good_kicker',
        'clean_overpair',
        'board_pair_pocket_pair',
        'clean_two_pair',
    }


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


def _sticky_value_target(ctx: DecisionCtx) -> bool:
    vs = ctx.villain_stats
    return (
        ctx.n_sticky >= 1
        or vs.vpip >= 0.40
        or (vs.hands_seen >= 20 and vs.wtsd > 0.28)
        or (vs.fold_to_cbet_opps >= 5 and vs.fold_to_cbet < 0.35)
        or (vs.river_action_count >= 5 and vs.river_fold_rate < 0.45)
        or (vs.hands_seen >= 20 and vs.af < 1.3)
    )


def _sticky_pressure_target(ctx: DecisionCtx) -> bool:
    """Opponent/pool is call-heavy enough that fold equity should be discounted."""
    return (
        no_fold_equity(ctx)
        or sticky_passive(ctx)
        or ctx.n_sticky >= 1
        or ctx.max_value_lean >= 1.20
    )


def _sticky_multiway(ctx: DecisionCtx) -> bool:
    return ctx.num_opponents >= 2 and _sticky_pressure_target(ctx)


def _sticky_semibluff_allowed(ctx: DecisionCtx, *, multiway: bool = False) -> bool:
    """Keep only draws that can earn when called by sticky opponents."""
    if ctx.hero_bucket not in ('draw', 'weak_draw'):
        return False
    premium = draw_quality.premium_draw(ctx)
    strong = draw_quality.strong_draw(ctx)
    blocker = ctx.blockers.nut_flush_blocker or ctx.blockers.straight_blocker
    combo_draw = (
        ctx.draw.flush_draw
        and (ctx.draw.oesd or ctx.draw.gutshot or ctx.draw.overcards)
    )
    if premium and ctx.equity_range >= (0.38 if multiway else 0.34):
        return True
    if strong and blocker and ctx.equity_range >= (0.40 if multiway else 0.36):
        return True
    if combo_draw and blocker and ctx.equity_range >= (0.42 if multiway else 0.38):
        return True
    if multiway:
        return False
    return blocker and ctx.equity_range >= 0.40 and ctx.spr >= 3.0


def _sticky_multiway_value_ok(ctx: DecisionCtx) -> bool:
    """Higher value threshold for sticky multiway pots."""
    if not _sticky_multiway(ctx):
        return True
    if ctx.hero_bucket == 'nuts':
        return True
    if ctx.hero_bucket not in ('medium', 'strong'):
        return False
    if _fragile_underpair_after_resistance(ctx):
        return False
    nuts = _villain_nuts(ctx)
    hero_wins, _ties, villain_wins, rel_eq = _relative_hero_wins(ctx)
    has_rel = bool(ctx.villain_vs_hero_dist)
    if ctx.hero_bucket == 'strong':
        if _dangerous_non_nut_value_spot(ctx):
            if has_rel:
                return hero_wins >= 0.64 and rel_eq >= 0.68 and villain_wins <= 0.26
            return ctx.equity_range >= 0.72 and nuts <= 0.18
        if has_rel:
            return rel_eq >= 0.62 and hero_wins >= villain_wins + 0.08 and villain_wins <= 0.34
        return ctx.equity_range >= 0.62 and nuts <= 0.24

    if not _safe_medium_protection_hand(ctx):
        return False
    if _dangerous_non_nut_value_spot(ctx):
        return False
    if has_rel:
        return rel_eq >= 0.64 and hero_wins >= villain_wins + 0.12 and villain_wins <= 0.30
    return ctx.equity_range >= 0.64 and ctx.equity_mc >= 0.58 and nuts <= 0.14


def _sticky_value_size_up(ctx: DecisionCtx) -> bool:
    """Value sizing can grow against sticky opponents only with robust value."""
    if _no_fe_value_pressure(ctx):
        return True
    if not (_sticky_value_target(ctx) or _sticky_pressure_target(ctx)):
        return False
    if ctx.hero_bucket == 'nuts':
        return True
    if ctx.hero_bucket != 'strong':
        return False
    if _sticky_multiway(ctx):
        return _sticky_multiway_value_ok(ctx)
    if _dangerous_non_nut_value_spot(ctx):
        hero_wins, _ties, villain_wins, rel_eq = _relative_hero_wins(ctx)
        if ctx.villain_vs_hero_dist:
            return rel_eq >= 0.70 and hero_wins >= 0.64 and villain_wins <= 0.26
        return ctx.equity_range >= 0.78 and _villain_nuts(ctx) <= 0.18
    return (
        ctx.equity_range >= 0.66
        or _paying_bucket_mass(ctx) + _draw_pressure_mass(ctx) >= 0.48
    )


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


def _fragile_underpair_after_resistance(ctx: DecisionCtx) -> bool:
    """Pocket pair under an overcard should not keep value-betting after calls."""
    if ctx.facing_bet or ctx.street not in ('turn', 'river'):
        return False
    if not (ctx.prev_bet_called_count > 0 or ctx.prev_bet_raised):
        return False
    if ctx.pocket_pair_rank <= 0 or ctx.board_sig.high_card_rank <= ctx.pocket_pair_rank:
        return False
    if ctx.hero_hand_rank not in {'one_pair', 'two_pair'}:
        return False
    return ctx.hero_made_subtype in {'pocket_pair', 'board_pair_pocket_underpair'}


def _high_card_underpair(ctx: DecisionCtx) -> bool:
    if ctx.pocket_pair_rank <= 0 or ctx.board_sig.high_card_rank <= ctx.pocket_pair_rank:
        return False
    if ctx.hero_hand_rank not in {'one_pair', 'two_pair'}:
        return False
    return ctx.hero_made_subtype in {'pocket_pair', 'board_pair_pocket_underpair'}


def _river_fragile_relative_value_block(ctx: DecisionCtx, eq_need: float) -> bool:
    """River board-pair value needs enough worse-hand mass, not just raw equity."""
    if ctx.street != 'river' or not ctx.villain_vs_hero_dist:
        return False
    if not ctx.board_sig.paired:
        return False
    if ctx.hero_made_subtype not in {
        'board_pair_hero_pair',
        'board_pair_kicker',
        'board_two_pair',
        'trips_weak_kicker',
        'board_trips_kicker',
    }:
        return False
    rel = ctx.villain_vs_hero_dist or {}
    hero_wins = float(rel.get('win', 0.0) or 0.0)
    ties = float(rel.get('tie', 0.0) or 0.0)
    villain_wins = float(rel.get('loss', 0.0) or 0.0)
    rel_eq = hero_wins + 0.5 * ties
    need = max(_RIVER_FRAGILE_VALUE_MIN_REL_EQ, eq_need + 0.06)
    return (
        villain_wins >= _RIVER_FRAGILE_VALUE_MAX_LOSS
        and rel_eq < need
        and hero_wins < 0.70
    )


def _can_overbet_value(ctx: DecisionCtx) -> bool:
    """Return True iff OverbetValue would be a legal candidate in this spot.

    Keep this helper aligned with OverbetValue.trigger() so any "defer to
    overbet" logic never drops ThickValueBet when overbet itself cannot fire.
    """
    if ctx.facing_bet:
        return False
    if _fragile_underpair_after_resistance(ctx):
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
    if ctx.prev_bet_called_count > 0:
        add += _BARREL_RESIST_CALL_EQ_ADD * min(3, ctx.prev_bet_called_count)
    if ctx.prev_bet_raised:
        add += _BARREL_RESIST_RAISE_EQ_ADD
    return add


def _strong_draw_profile(ctx: DecisionCtx) -> bool:
    return draw_quality.strong_draw(ctx)


def _realizable_no_fe_draw(ctx: DecisionCtx) -> bool:
    """Draws worth betting when villain is unlikely to fold.

    Against calling stations, fold equity is not the income source. Keep firing
    only with draws that can improve cleanly enough when called; gutter/overcard
    hands are allowed only as a flop one-street pressure spot with enough equity.
    """
    d = ctx.draw
    if d.flush_draw or d.oesd:
        return ctx.equity_range >= 0.35
    return (
        ctx.street == 'flop'
        and d.gutshot
        and d.overcards
        and ctx.num_opponents == 1
        and ctx.equity_range >= 0.38
    )


def _profit_expand_board_ok(ctx: DecisionCtx) -> bool:
    if not _PROFIT_EXPAND_V1:
        return False
    if ctx.board_sig.monotone:
        return False
    if ctx.board_sig.wetness >= 0.65:
        return False
    if _villain_nuts(ctx) > _PE_FLOP_MAX_NUTS:
        return False
    if _bucket_mass(ctx, 'strong', 'nuts') > _PE_FLOP_MAX_STRONG_NUTS:
        return False
    return (
        ctx.board_sig.is_dry
        or ctx.board_sig.high_card_rank >= 11
        or ctx.is_ip
        or _bucket_mass(ctx, 'air', 'weak_draw') >= 0.35
    )


def _profit_expand_capped_turn(ctx: DecisionCtx) -> bool:
    if not _PROFIT_EXPAND_V1:
        return False
    if _villain_nuts(ctx) > _PE_TURN_MAX_NUTS:
        return False
    if _bucket_mass(ctx, 'strong', 'nuts') > _PE_TURN_MAX_STRONG_NUTS:
        return False
    if ctx.board_sig.monotone and ctx.hero_bucket in ('air', 'weak_draw'):
        return False
    return True


def _capped_high_fe_bluff_ok(ctx: DecisionCtx, blf, *, turn: bool = False) -> bool:
    if not _CAPPED_BLUFF_EXPAND_ENABLED:
        return False
    if no_fold_equity(ctx):
        return False
    if ctx.num_opponents > 2:
        return False
    if ctx.spr < (2.5 if turn else 3.0):
        return False
    if ctx.board_sig.monotone:
        return False
    if ctx.board_sig.wetness >= 0.70 and not ctx.draw.flush_draw:
        return False
    if _villain_nuts(ctx) > _CAPPED_BLUFF_MAX_NUTS:
        return False
    if _bucket_mass(ctx, 'strong', 'nuts') > _CAPPED_BLUFF_MAX_STRONG_NUTS:
        return False

    fold_est = ctx.villain_stats.fold_to_cbet
    sampled_fe = ctx.villain_stats.fold_to_cbet_opps >= 5 and fold_est >= _CAPPED_BLUFF_MIN_FOLD
    range_fe = blf.score >= _CAPPED_BLUFF_MIN_SCORE and blf.air_weak >= 0.35
    if not (sampled_fe or range_fe):
        return False

    if ctx.hero_bucket == 'air':
        return (
            ctx.equity_range >= 0.14
            and (
                sampled_fe
                or blf.blocker_score >= 0.25
                or ctx.board_sig.is_dry
                or ctx.board_sig.high_card_rank >= 12
            )
        )
    if ctx.hero_bucket == 'weak_draw':
        return (
            ctx.equity_range >= 0.18
            and (
                ctx.blockers.count() > 0
                or ctx.draw.overcards
                or ctx.draw.gutshot
                or ctx.draw.backdoor_flush
            )
        )
    if ctx.hero_bucket == 'draw':
        return ctx.equity_range >= 0.24
    return False


def _profit_expand_paid_value_ok(ctx: DecisionCtx) -> bool:
    if not (_PROFIT_EXPAND_V1 or _PROFIT_PAID_VALUE_ENABLED):
        return False
    if ctx.facing_bet or ctx.street not in ('turn', 'river'):
        return False
    if ctx.prev_bet_called_count <= 0 or ctx.prev_bet_raised:
        return False
    if ctx.hero_bucket not in ('medium', 'strong', 'nuts'):
        return False
    if _sticky_multiway(ctx) and not _sticky_multiway_value_ok(ctx):
        return False
    if _fragile_underpair_after_resistance(ctx):
        return False
    if ctx.hero_bucket == 'medium' and not _safe_medium_protection_hand(ctx):
        return False
    nuts = _villain_nuts(ctx)
    if ctx.hero_bucket != 'nuts' and nuts > _PE_PAID_VALUE_MAX_NUTS:
        return False

    if (
        ctx.hero_bucket != 'nuts'
        and not _sticky_value_target(ctx)
        and _paying_bucket_mass(ctx) < _PE_PAID_VALUE_MIN_PAYING
        and _draw_pressure_mass(ctx) < _PE_PAID_VALUE_MIN_DRAW_PRESSURE
    ):
        return False

    hero_wins, _ties, villain_wins, rel_eq = _relative_hero_wins(ctx)
    if ctx.villain_vs_hero_dist:
        if _dangerous_non_nut_value_spot(ctx):
            return (
                hero_wins >= 0.62
                and rel_eq >= 0.66
                and villain_wins <= 0.28
            )
        return (
            hero_wins >= 0.52
            and rel_eq >= 0.56
            and villain_wins <= 0.40
        )

    if _dangerous_non_nut_value_spot(ctx):
        return (
            ctx.hero_bucket in ('strong', 'nuts')
            and ctx.equity_range >= 0.68
            and nuts <= 0.18
        )
    if ctx.hero_bucket == 'medium':
        return (
            ctx.equity_range >= 0.52
            and (_paying_bucket_mass(ctx) >= 0.30 or _draw_pressure_mass(ctx) >= 0.12)
        )
    return ctx.equity_range >= 0.55


def _safe_thin_value_expand_ok(ctx: DecisionCtx) -> bool:
    """Extra value only when worse hands can pay and danger is contained."""
    if ctx.facing_bet or ctx.street not in ('turn', 'river'):
        return False
    if _sticky_multiway(ctx):
        return False
    if ctx.hero_bucket not in ('medium', 'strong'):
        return False
    if ctx.prev_bet_raised:
        return False
    if _fragile_underpair_after_resistance(ctx):
        return False
    if _dangerous_non_nut_value_spot(ctx):
        return False
    nuts = _villain_nuts(ctx)
    if nuts > _SAFE_VALUE_EXPAND_MAX_NUTS:
        return False
    if _paying_bucket_mass(ctx) < _SAFE_VALUE_EXPAND_MIN_PAYING:
        return False

    hero_wins, _ties, villain_wins, rel_eq = _relative_hero_wins(ctx)
    if ctx.villain_vs_hero_dist:
        return (
            rel_eq >= _SAFE_VALUE_EXPAND_MIN_REL_EQ
            and hero_wins >= villain_wins + 0.05
            and villain_wins <= _SAFE_VALUE_EXPAND_MAX_LOSS
        )

    return (
        ctx.equity_range >= _SAFE_VALUE_EXPAND_MIN_EQ
        and ctx.equity_mc >= _SAFE_VALUE_EXPAND_MIN_MC
    )


def _no_fe_value_pressure(ctx: DecisionCtx) -> bool:
    """Sticky/no-fold opponent: shift chips from bluffs into value/protection."""
    if not no_fold_equity(ctx):
        return False
    if ctx.hero_bucket not in ('medium', 'strong', 'nuts'):
        return False
    if _sticky_multiway(ctx) and not _sticky_multiway_value_ok(ctx):
        return False
    if ctx.hero_bucket == 'nuts':
        return True
    if _fragile_underpair_after_resistance(ctx):
        return False

    hero_wins, _ties, villain_wins, rel_eq = _relative_hero_wins(ctx)
    if ctx.villain_vs_hero_dist:
        if _dangerous_non_nut_value_spot(ctx):
            return rel_eq >= 0.62 and hero_wins >= 0.55 and villain_wins <= 0.35
        return rel_eq >= 0.58 and hero_wins >= 0.50 and villain_wins <= 0.42

    if _dangerous_non_nut_value_spot(ctx):
        return ctx.equity_range >= 0.70 and _villain_nuts(ctx) <= 0.18
    if ctx.hero_bucket == 'medium':
        return (
            ctx.equity_range >= 0.55
            and (
                _paying_bucket_mass(ctx) >= 0.30
                or _draw_pressure_mass(ctx) >= 0.12
                or ctx.street in ('flop', 'turn')
            )
        )
    return ctx.equity_range >= 0.58


def _no_fe_value_weight_add(ctx: DecisionCtx) -> float:
    if not _no_fe_value_pressure(ctx):
        return 0.0
    if ctx.hero_bucket == 'medium':
        return 0.20
    return 0.30


def _river_relative_value_ok(ctx: DecisionCtx) -> bool:
    if ctx.street != 'river' or not ctx.villain_vs_hero_dist:
        return False
    if ctx.hero_bucket not in ('medium', 'strong', 'nuts'):
        return False
    hero_wins, _ties, villain_wins, rel_eq = _relative_hero_wins(ctx)
    nuts = _villain_nuts(ctx)
    if ctx.hero_bucket == 'nuts':
        return rel_eq >= 0.55
    if _dangerous_non_nut_value_spot(ctx):
        return (
            hero_wins >= 0.65
            and rel_eq >= 0.65
            and villain_wins <= 0.30
            and nuts <= _RIVER_THIN_VALUE_MAX_NUTS
        )
    return (
        hero_wins >= _RIVER_THIN_VALUE_MIN_WORSE
        and rel_eq >= 0.58
        and villain_wins <= _RIVER_THIN_VALUE_MAX_LOSS
        and nuts <= _RIVER_THIN_VALUE_MAX_NUTS
    )


def _river_checked_thin_value_probe(ctx: DecisionCtx) -> bool:
    if ctx.street != 'river' or ctx.facing_bet or not ctx.villain_vs_hero_dist:
        return False
    if _sticky_multiway(ctx):
        return False
    if ctx.hero_bucket not in ('medium', 'strong'):
        return False
    if ctx.hero_bucket == 'medium' and not _safe_medium_protection_hand(ctx):
        return False
    if _villain_nuts(ctx) > _RIVER_CHECKED_THIN_MAX_NUTS:
        return False

    hero_wins, _ties, villain_wins, rel_eq = _relative_hero_wins(ctx)
    min_rel = _RIVER_CHECKED_THIN_MIN_REL_EQ
    max_loss = _RIVER_CHECKED_THIN_MAX_LOSS
    min_gap = _RIVER_CHECKED_THIN_MIN_WIN_GAP
    if _dangerous_non_nut_value_spot(ctx):
        min_rel += 0.06
        max_loss = min(max_loss, 0.25)
        min_gap += 0.05
    if rel_eq < min_rel or villain_wins > max_loss:
        return False
    if hero_wins < villain_wins + min_gap:
        return False

    return (
        _sticky_value_target(ctx)
        or _paying_bucket_mass(ctx) >= _RIVER_CHECKED_THIN_MIN_PAYING
        or ctx.villain_stats.vpip >= 0.40
    )


def _river_medium_probe_ok(ctx: DecisionCtx) -> bool:
    if ctx.street != 'river' or ctx.hero_bucket != 'medium':
        return True
    if not ctx.villain_vs_hero_dist:
        return True
    hero_wins, _ties, villain_wins, rel_eq = _relative_hero_wins(ctx)
    return (
        rel_eq >= _RIVER_MEDIUM_PROBE_MIN_REL_EQ
        and hero_wins >= villain_wins + _RIVER_MEDIUM_PROBE_MIN_WIN_GAP
    )


def _river_medium_value_jam_ok(ctx: DecisionCtx) -> bool:
    if ctx.street != 'river' or ctx.hero_bucket != 'medium':
        return True

    if ctx.hero_hand_rank in {'high_card', 'one_pair'}:
        return False

    hero_wins, _ties, villain_wins, rel_eq = _relative_hero_wins(ctx)
    if ctx.villain_vs_hero_dist:
        min_win = _RIVER_MEDIUM_JAM_MIN_WIN
        max_loss = _RIVER_MEDIUM_JAM_MAX_LOSS
        if _dangerous_non_nut_value_spot(ctx):
            min_win = _RIVER_MEDIUM_DANGER_JAM_MIN_WIN
            max_loss = _RIVER_MEDIUM_DANGER_JAM_MAX_LOSS
        return (
            hero_wins >= min_win
            and rel_eq >= min_win
            and villain_wins <= max_loss
            and _villain_nuts(ctx) <= _RIVER_THIN_VALUE_MAX_NUTS
        )

    if _dangerous_non_nut_value_spot(ctx):
        return False
    return ctx.equity_range >= 0.80 and _villain_nuts(ctx) <= 0.15


def _low_spr_made_hand_value_pressure(ctx: DecisionCtx) -> bool:
    if ctx.facing_bet or ctx.street not in ('flop', 'turn'):
        return False
    if ctx.spr <= 0 or ctx.spr > 1.8:
        return False
    if ctx.hero_bucket not in ('medium', 'strong'):
        return False
    if _sticky_multiway(ctx) and not _sticky_multiway_value_ok(ctx):
        return False
    if _fragile_underpair_after_resistance(ctx):
        return False
    if ctx.hero_bucket == 'medium' and _high_card_underpair(ctx):
        return False
    nuts = _villain_nuts(ctx)
    if ctx.hero_bucket == 'strong':
        return (
            nuts <= 0.22
            and (
                ctx.equity_range >= _commit_value_eq_need(ctx) - 0.015
                or ctx.equity_mc >= 0.62
                or _paying_bucket_mass(ctx) + _draw_pressure_mass(ctx) >= 0.45
            )
        )
    if _dangerous_non_nut_value_spot(ctx):
        return False
    return (
        nuts <= 0.15
        and (
            ctx.equity_mc >= 0.58
            or _paying_bucket_mass(ctx) + _draw_pressure_mass(ctx) >= 0.55
        )
    )


def _resisted_barrel_spot(ctx: DecisionCtx) -> bool:
    return (
        ctx.street == 'turn'
        and (
            ctx.prev_bet_called_count > 0
            or ctx.prev_bet_raised
            or ctx.resistance_level >= 0.20
        )
    )


def _commit_value_eq_need(ctx: DecisionCtx) -> float:
    return (
        commit_value_eq(ctx.spr)
        + _river_danger_add(ctx)
        + early_relative.active_value_eq_add(ctx)
    )


def _value_jam_frac(ctx: DecisionCtx) -> float:
    if ctx.pot <= 0 or ctx.stack <= 0:
        return 0.0
    return float(ctx.stack) / float(ctx.pot)


def _value_jam_payment_ok(ctx: DecisionCtx) -> bool:
    vs = ctx.villain_stats
    if ctx.prev_bet_called_count > 0 or ctx.prev_bet_raised:
        return True
    if ctx.n_sticky >= 1:
        return True
    if vs.vpip >= 0.45:
        return True
    if vs.hands_seen >= 20 and (vs.wtsd >= 0.32 or vs.af <= 1.1):
        return True
    if vs.fold_to_cbet_opps >= 5 and vs.fold_to_cbet <= 0.30:
        return True
    if vs.river_action_count >= 5 and vs.river_fold_rate <= 0.30:
        return True
    if _paying_bucket_mass(ctx) >= 0.42:
        return True
    if ctx.hero_bucket == 'nuts' and _bucket_mass(ctx, 'strong', 'medium') >= 0.35:
        return True
    return False


def _value_jam_relative_ok(ctx: DecisionCtx) -> bool:
    hero_wins, _ties, villain_wins, rel_eq = _relative_hero_wins(ctx)
    if not ctx.villain_vs_hero_dist:
        if _dangerous_non_nut_value_spot(ctx):
            return ctx.equity_range >= 0.82 and _villain_nuts(ctx) <= 0.14
        return ctx.equity_range >= 0.74 and _villain_nuts(ctx) <= 0.20
    if _dangerous_non_nut_value_spot(ctx):
        return hero_wins >= 0.80 and rel_eq >= 0.80 and villain_wins <= 0.15
    if ctx.hero_bucket == 'nuts':
        return rel_eq >= 0.72 and villain_wins <= 0.24
    return hero_wins >= 0.72 and rel_eq >= 0.72 and villain_wins <= 0.22


def _value_jam_legal(ctx: DecisionCtx) -> bool:
    if ctx.facing_bet:
        return False
    if _fragile_underpair_after_resistance(ctx):
        return False
    if not _river_medium_value_jam_ok(ctx):
        return False
    if ctx.hero_bucket not in ('strong', 'nuts'):
        return False
    if ctx.spr <= 0 or ctx.spr > 2.4:
        return False
    # Jam is a candidate only when the actual all-in size is not an oversized
    # overbet. A 2.78-pot side-pot shove like H69 should stay in normal value
    # sizing, not become value_jam.
    jam_frac = _value_jam_frac(ctx)
    if jam_frac <= 0 or jam_frac > 2.00:
        return False
    if not _value_jam_payment_ok(ctx):
        return False
    if (
        ctx.equity_range < _commit_value_eq_need(ctx)
        and not _low_spr_made_hand_value_pressure(ctx)
    ):
        return False
    if not _value_jam_relative_ok(ctx):
        return False
    return not stackoff_guard_reason(ctx, 'value_jam', will_jam=True)


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
        if _sticky_multiway(ctx):
            if ctx.hero_bucket in ('air', 'weak_draw'):
                return TriggerResult(False)
            if ctx.hero_bucket == 'draw' and not _sticky_semibluff_allowed(ctx, multiway=True):
                return TriggerResult(False)
            if ctx.hero_bucket in ('medium', 'strong') and not _sticky_multiway_value_ok(ctx):
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
        w += _no_fe_value_weight_add(ctx)
        return TriggerResult(True, w)

    def sizer(self, ctx: DecisionCtx) -> List[Tuple[float, float]]:
        if ctx.hero_bucket in ('medium', 'strong', 'nuts'):
            if _sticky_multiway(ctx) and ctx.hero_bucket == 'medium':
                return [(0.33, 0.45), (0.45, 0.55)]
            if _sticky_value_size_up(ctx):
                return [(0.50, 0.45), (0.60, 0.55)]
            return [(0.40, 0.45), (0.50, 0.55)]
        if ctx.board_sig.is_wet and ctx.hero_bucket in ('air', 'weak_draw'):
            return [(0.25, 0.55), (0.33, 0.45)]
        return [(0.33, 0.45), (0.40, 0.55)]

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
        if _sticky_pressure_target(ctx) and ctx.hero_bucket == 'draw' and not _sticky_semibluff_allowed(
            ctx,
            multiway=ctx.num_opponents > 1,
        ):
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
        if _fragile_underpair_after_resistance(ctx):
            return TriggerResult(False)
        if ctx.hero_bucket not in ('medium', 'strong'):
            return TriggerResult(False)
        if _sticky_multiway(ctx) and not _sticky_multiway_value_ok(ctx):
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
        protection_need = _PROTECTION_MIN_EQ
        if ctx.hero_bucket == 'medium':
            if not _ACTIVE_PROTECTION_MEDIUM_ENABLED:
                return TriggerResult(False)
            if not _safe_medium_protection_hand(ctx):
                return TriggerResult(False)
            if ctx.equity_mc < _ACTIVE_PROTECTION_MEDIUM_MIN_MC:
                return TriggerResult(False)
            if _villain_nuts(ctx) > _ACTIVE_PROTECTION_MEDIUM_MAX_NUTS:
                return TriggerResult(False)
            if _draw_pressure_mass(ctx) < _ACTIVE_PROTECTION_MEDIUM_DRAW_MASS_MIN and pressure < 0.50:
                return TriggerResult(False)
            protection_need = max(protection_need, _ACTIVE_PROTECTION_MEDIUM_MIN_EQ)
        if ctx.n_sticky >= 1:
            protection_need += _PROTECTION_STICKY_EQ_ADD
        if ctx.num_opponents >= 2:
            protection_need += _PROTECTION_MULTIWAY_EQ_ADD
        if ctx.equity_range < protection_need:
            return TriggerResult(False)
        return TriggerResult(True, 0.9 + _no_fe_value_weight_add(ctx))

    def sizer(self, ctx: DecisionCtx) -> List[Tuple[float, float]]:
        if _sticky_multiway(ctx) and ctx.hero_bucket == 'medium':
            return [(0.40, 0.50), (0.50, 0.50)]
        if _sticky_value_size_up(ctx):
            if ctx.board_sig.wetness >= 0.55:
                if ctx.hero_bucket == 'medium':
                    return [(0.60, 0.40), (0.75, 0.60)]
                return [(0.66, 0.35), (0.85, 0.65)]
            return [(0.60, 0.45), (0.75, 0.55)]
        if ctx.board_sig.wetness >= 0.55:
            if ctx.hero_bucket == 'medium':
                return [(0.50, 0.45), (0.60, 0.55)]
            return [(0.60, 0.45), (0.75, 0.55)]
        return [(0.50, 0.45), (0.66, 0.55)]

    def alpha_target(self, ctx: DecisionCtx, frac: float) -> Optional[float]:
        # Merged — small configured bluff share (~20-25%).
        return None


# ---------------------------------------------------------------------------
# 4. thin_value_bet
# ---------------------------------------------------------------------------


class ThinValueBet(Purpose):
    id = 'thin_value_bet'
    street_gate = ('turn', 'river')

    @staticmethod
    def _river_relative_value(ctx: DecisionCtx) -> bool:
        return _river_relative_value_ok(ctx)

    @staticmethod
    def _river_checked_thin_value(ctx: DecisionCtx) -> bool:
        return _river_checked_thin_value_probe(ctx)

    def trigger(self, ctx: DecisionCtx) -> TriggerResult:
        if ctx.facing_bet:
            return TriggerResult(False)
        if _fragile_underpair_after_resistance(ctx):
            return TriggerResult(False)
        # 2026-04-25 P1-1：窗口下限 0.52→0.48。实战多人池的 medium 桶 eq
        # 常在 0.45-0.55 区间，0.52 下限把几乎所有多人池 thin value 机会
        # 挡掉。0.48 对应 "赢得 call 后仍微领先" 的 Janda 薄 value 阈值。
        river_relative_value = self._river_relative_value(ctx)
        river_checked_value = self._river_checked_thin_value(ctx)
        safe_value_expand = _safe_thin_value_expand_ok(ctx)
        if not (
            (0.48 <= ctx.equity_range <= 0.65)
            or river_relative_value
            or river_checked_value
            or safe_value_expand
        ):
            return TriggerResult(False)
        if ctx.hero_bucket not in ('strong', 'medium'):
            return TriggerResult(False)
        sticky_line = _sticky_value_target(ctx) or _sticky_pressure_target(ctx)
        if sticky_line:
            if ctx.num_opponents != 1:
                return TriggerResult(False)
            if ctx.prev_bet_raised or ctx.resistance_level >= 0.25:
                return TriggerResult(False)
            if ctx.prev_bet_called_count > 0 and _dangerous_non_nut_value_spot(ctx):
                return TriggerResult(False)
        if ctx.board_sig.wetness >= 0.70 and not (
            river_relative_value or river_checked_value or safe_value_expand
        ):
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
        sticky_any = _sticky_value_target(ctx)
        if not sticky_any and not river_checked_value and not safe_value_expand:
            return TriggerResult(False)
        # weight 由 river_fold_rate 基底 + sticky 证据累加，最多 0.9（原上限 ~0.8）
        base = (1.0 - vs.river_fold_rate) * 0.8 if vs.river_action_count >= 5 else 0.4
        bonus = 0.0
        if vs.hands_seen >= 20:
            bonus += max(0.0, (vs.wtsd - 0.28) * 1.5)
        if vs.fold_to_cbet_opps >= 5:
            bonus += max(0.0, (0.35 - vs.fold_to_cbet) * 1.2)
        if river_relative_value:
            bonus += min(0.25, (ctx.equity_range - _RIVER_THIN_VALUE_MIN_EQ) * 1.5)
            if _paying_bucket_mass(ctx) < 0.30 and ctx.equity_range < 0.65:
                return TriggerResult(False)
        if river_checked_value:
            bonus += 0.20
            if _paying_bucket_mass(ctx) < 0.25 and not sticky_any and ctx.equity_range < 0.62:
                return TriggerResult(False)
        if safe_value_expand:
            bonus += 0.18
        bonus += _no_fe_value_weight_add(ctx)
        cap = 1.10 if (_no_fe_value_pressure(ctx) or safe_value_expand) else 0.9
        return TriggerResult(True, max(0.3, min(cap, base + bonus)))

    def sizer(self, ctx: DecisionCtx) -> List[Tuple[float, float]]:
        if _safe_thin_value_expand_ok(ctx) and not (
            self._river_relative_value(ctx) or self._river_checked_thin_value(ctx)
        ):
            if ctx.street == 'turn':
                return [(0.45, 0.45), (0.55, 0.45), (0.66, 0.10)]
            return [(0.40, 0.45), (0.55, 0.45), (0.66, 0.10)]
        if self._river_checked_thin_value(ctx):
            if _no_fe_value_pressure(ctx):
                return [(0.45, 0.45), (0.55, 0.55)]
            return [(0.33, 0.45), (0.45, 0.40), (0.55, 0.15)]
        if _no_fe_value_pressure(ctx):
            if self._river_relative_value(ctx):
                return [(0.55, 0.45), (0.66, 0.55)]
            if ctx.street == 'turn':
                return [(0.60, 0.40), (0.75, 0.60)]
            return [(0.55, 0.35), (0.66, 0.45), (0.75, 0.20)]
        if self._river_relative_value(ctx):
            return [(0.45, 0.55), (0.55, 0.45)]
        if ctx.street == 'turn':
            return [(0.50, 0.45), (0.66, 0.55)]
        return [(0.45, 0.40), (0.55, 0.40), (0.66, 0.20)]

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

    def active_value_sizing_allowed(self, ctx: DecisionCtx, frac: float) -> bool:
        return ctx.street not in {'flop', 'turn'}


# ---------------------------------------------------------------------------
# 6. thick_value_bet
# ---------------------------------------------------------------------------


class ThickValueBet(Purpose):
    id = 'thick_value_bet'

    def trigger(self, ctx: DecisionCtx) -> TriggerResult:
        if ctx.facing_bet:
            return TriggerResult(False)
        if _fragile_underpair_after_resistance(ctx):
            return TriggerResult(False)
        if _monster_value_kind(ctx):
            return TriggerResult(False)
        if _sticky_multiway(ctx) and not _sticky_multiway_value_ok(ctx):
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
        low_spr_pressure = _low_spr_made_hand_value_pressure(ctx)
        if ctx.equity_range < eq_need and not low_spr_pressure:
            return TriggerResult(False)
        if _river_fragile_relative_value_block(ctx, eq_need):
            return TriggerResult(False)
        # Don't compete with overbet_value only when overbet is truly legal.
        # This keeps ThickValueBet alive in boundary spots (e.g. 2.0 < SPR < 2.4)
        # where overbet cannot trigger yet.
        if _can_overbet_value(ctx):
            return TriggerResult(False)
        # Don't compete with range_cbet on flop dry boards for ordinary
        # top-pair/medium value. Near-lock nuts such as a flopped set should
        # still build value instead of being forced into 25-33% range bets.
        if ctx.street == 'flop' and ctx.board_sig.is_dry \
                and ctx.board_sig.high_card_rank >= 11 and ctx.is_pfr \
                and not (ctx.hero_bucket in ('strong', 'nuts') or ctx.equity_range >= 0.60):
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
            hero_wins, _ties, villain_wins, _rel_eq = _relative_hero_wins(ctx)
            if (
                ctx.prev_bet_raised
                or _villain_nuts(ctx) >= 0.25
                or villain_wins >= 0.30
                or _dangerous_non_nut_value_spot(ctx)
            ):
                return TriggerResult(False)
        # 权重基准从 eq_need 起算而非固定 0.70，确保 low SPR 下早触发的
        # hand 权重不会因为 (eq - 0.70) 为负而崩塌。低 SPR 成牌压力由 MC/
        # 支付桶补充 raw range equity，避免接近 commit 时只剩 check。
        if low_spr_pressure:
            w = 1.0
        else:
            w = 0.8 + (ctx.equity_range - eq_need) * 3.0
        w += _no_fe_value_weight_add(ctx)
        return TriggerResult(True, min(2.2, max(0.4, w)))

    def sizer(self, ctx: DecisionCtx) -> List[Tuple[float, float]]:
        resisted = ctx.prev_bet_called_count > 0 or ctx.prev_bet_raised
        if _sticky_multiway(ctx):
            if ctx.hero_bucket == 'medium':
                return [(0.40, 0.45), (0.50, 0.45), (0.60, 0.10)]
            return [(0.66, 0.35), (0.80, 0.45), (1.00, 0.20)]
        if _sticky_value_size_up(ctx):
            if ctx.street == 'river':
                if resisted:
                    return [(0.85, 0.40), (1.00, 0.60)]
                return [(0.75, 0.40), (0.90, 0.40), (1.00, 0.20)]
            if ctx.street == 'turn':
                if resisted:
                    return [(0.80, 0.40), (1.00, 0.60)]
                return [(0.75, 0.45), (0.90, 0.55)]
            return [(0.66, 0.35), (0.80, 0.65)]
        if ctx.street == 'river':
            if resisted:
                return [(0.75, 0.45), (1.00, 0.55)]
            return [(0.66, 0.30), (0.75, 0.45), (1.00, 0.25)]
        if ctx.street == 'turn':
            if resisted:
                return [(0.75, 0.45), (1.00, 0.55)]
            return [(0.66, 0.45), (0.80, 0.55)]
        return [(0.60, 0.35), (0.75, 0.65)]


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
        w = 1.2 * (0.5 + ctx.nut_advantage) + _no_fe_value_weight_add(ctx)
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
        if ctx.facing_bet or ctx.hero_bucket not in ('draw', 'weak_draw'):
            return TriggerResult(False)
        blf = bluff_context.evaluate(ctx)
        premium = draw_quality.premium_draw(ctx)
        strong = draw_quality.strong_draw(ctx)
        weak = ctx.hero_bucket == 'weak_draw'

        if weak:
            if not draw_quality.weak_draw_semibluff_quality_ok(ctx):
                return TriggerResult(False)
            if ctx.spr <= 2.0:
                return TriggerResult(False)
            if ctx.num_opponents > 1 and ctx.board_sig.is_wet:
                return TriggerResult(False)
            if sticky_passive(ctx) or ctx.n_sticky >= 1:
                return TriggerResult(False)
            weak_min = 0.26
            if ctx.is_pfr and (ctx.is_ip or ctx.num_opponents == 1):
                weak_min = 0.24
            if blf.air_weak >= 0.35 and blf.score >= 0.55 and ctx.is_ip:
                weak_min = max(0.22, weak_min - 0.02)
            if ctx.spr < 4.0:
                weak_min += 0.03
            if ctx.equity_range < weak_min:
                return TriggerResult(False)
            if blf.nuts >= 0.25 or blf.strong_nuts >= 0.55:
                return TriggerResult(False)
        else:
            min_eq = 0.32 if premium else 0.36
            if ctx.spr <= 2.0 and not premium:
                min_eq += 0.06
            elif ctx.spr < 4.0 and not premium:
                min_eq += 0.03
            if ctx.equity_range < min_eq:
                return TriggerResult(False)
            if ctx.num_opponents > 1 and ctx.board_sig.is_wet and not premium:
                return TriggerResult(False)

        if _sticky_pressure_target(ctx) and not _sticky_semibluff_allowed(
            ctx,
            multiway=ctx.num_opponents > 1,
        ):
            return TriggerResult(False)

        low_fe = no_fold_equity(ctx)
        if low_fe:
            if not premium and not _realizable_no_fe_draw(ctx):
                return TriggerResult(False)
            if premium and ctx.equity_range < 0.42:
                return TriggerResult(False)

        bet = 0.66
        fe = bet / (1.0 + bet)
        opp_fold_est = ctx.villain_stats.fold_to_cbet
        ev = (opp_fold_est * 1.0
              + (1 - opp_fold_est) * (ctx.equity_range * (1 + bet)
                                       - (1 - ctx.equity_range) * bet))
        if ev <= 0 and ctx.equity_range < (0.38 if premium else 0.40):
            return TriggerResult(False)
        _ = fe
        bucket_delta = 0.0
        if ctx.villain_bucket_dist:
            bucket_delta = max(-0.10, min(0.18, (blf.score - 0.45) * 0.35))
        w = 0.4 + 0.5 * ctx.equity_range + bucket_delta
        if premium:
            w += 0.10
            if not low_fe and (blf.score >= 0.50 or ctx.villain_stats.fold_to_cbet >= 0.45):
                w += 0.15
        if weak:
            w *= 0.70
        if ctx.spr < 3.0:
            w *= 0.85
        return TriggerResult(True, w)

    def sizer(self, ctx: DecisionCtx) -> List[Tuple[float, float]]:
        if ctx.hero_bucket == 'weak_draw':
            return [(0.45, 0.55), (0.55, 0.45)]
        if ctx.spr < 3.0 and not draw_quality.premium_draw(ctx):
            return [(0.45, 0.55), (0.55, 0.45)]
        if no_fold_equity(ctx):
            return [(0.40, 0.45), (0.55, 0.55)]
        if draw_quality.premium_draw(ctx):
            return [(0.55, 0.35), (0.66, 0.45), (0.75, 0.20)]
        return [(0.50, 0.45), (0.66, 0.40), (0.75, 0.15)]


# ---------------------------------------------------------------------------
# 10. pure_bluff_river
# ---------------------------------------------------------------------------


class PureBluffRiver(Purpose):
    id = 'pure_bluff_river'
    street_gate = ('river',)

    def trigger(self, ctx: DecisionCtx) -> TriggerResult:
        if not _PURE_BLUFF_ENABLED:
            return TriggerResult(False)
        if ctx.facing_bet or ctx.hero_bucket != 'air':
            return TriggerResult(False)
        if _sticky_pressure_target(ctx):
            return TriggerResult(False)
        if no_fold_equity(ctx):
            return TriggerResult(False)
        blf = bluff_context.evaluate(ctx)
        quality = _pure_bluff_blocker_quality(ctx, blf)
        if not _pure_bluff_blocker_ok(ctx, blf, quality):
            return TriggerResult(False)
        if blf.nuts > 0.18 or blf.strong_nuts > 0.55:
            return TriggerResult(False)
        if (
            _bluff_catcher_density(ctx) < _PURE_BLUFF_CATCHER_MIN
            and blf.air_weak < 0.35
            and blf.medium < 0.35
        ):
            return TriggerResult(False)
        if not _pure_bluff_player_count_ok(ctx, blf, quality):
            return TriggerResult(False)
        if blf.score < _BLUFF_CONTEXT_RIVER_MIN:
            return TriggerResult(False)
        if not _pure_bluff_river_fracs(ctx, blf):
            return TriggerResult(False)
        w = 0.25 + 0.75 * blf.score + 0.20 * quality
        if ctx.num_opponents == 2:
            w *= 0.65
        return TriggerResult(True, max(0.2, w))

    def sizer(self, ctx: DecisionCtx) -> List[Tuple[float, float]]:
        if not _PURE_BLUFF_ENABLED:
            return []
        return _pure_bluff_river_fracs(ctx)


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
        blf = bluff_context.evaluate(ctx)
        delayed_bluff = (
            ctx.hero_bucket in ('air', 'weak_draw')
            and ctx.equity_range >= 0.18
            and ctx.num_opponents <= 2
            and (ctx.is_ip or ctx.num_opponents == 1)
            and blf.score >= _BLUFF_CONTEXT_DELAYED_MIN
            and blf.nuts <= 0.20
            and blf.strong_nuts <= 0.55
        )
        if ctx.equity_range < 0.45 and not delayed_bluff:
            return TriggerResult(False)
        if (
            no_fold_equity(ctx)
            and ctx.hero_bucket in ('air', 'weak_draw', 'draw')
            and not _realizable_no_fe_draw(ctx)
        ):
            return TriggerResult(False)
        if delayed_bluff and _sticky_pressure_target(ctx):
            return TriggerResult(False)
        if delayed_bluff:
            return TriggerResult(True, 0.45 + 0.45 * blf.score)
        return TriggerResult(True, 0.6 + 0.4 * ctx.equity_range + _no_fe_value_weight_add(ctx))

    def sizer(self, ctx: DecisionCtx) -> List[Tuple[float, float]]:
        if _sticky_value_size_up(ctx):
            return [(0.60, 0.35), (0.75, 0.45), (0.85, 0.20)]
        if ctx.hero_bucket in ('medium', 'strong', 'nuts') or ctx.equity_range >= 0.60:
            return [(0.50, 0.30), (0.66, 0.45), (0.75, 0.25)]
        return [(0.50, 0.45), (0.66, 0.55)]


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
        blf = bluff_context.evaluate(ctx)
        probe_bluff = (
            ctx.hero_bucket in ('air', 'weak_draw')
            and ctx.equity_range >= 0.18
            and ctx.num_opponents <= 2
            and blf.score >= _BLUFF_CONTEXT_PROBE_FLOAT_MIN
            and blf.nuts <= 0.20
            and blf.strong_nuts <= 0.55
        )
        if ctx.equity_range < 0.40 and not probe_bluff:
            return TriggerResult(False)
        # Sticky 对手 + 无 showdown value（air/weak_draw）时 probe 是
        # 结构性 -EV：FE ≈ 0 无法靠下注赢 pot，hero 又没有叫到摊牌的 eq。
        # 持 value bucket（medium+）时保留 probe —— 对 station 薄 value
        # 是 +EV 的（他会 call 更弱）。
        if no_fold_equity(ctx) and ctx.hero_bucket in ('air', 'weak_draw'):
            return TriggerResult(False)
        if probe_bluff and _sticky_pressure_target(ctx):
            return TriggerResult(False)
        if not _river_medium_probe_ok(ctx):
            return TriggerResult(False)
        if ctx.street == 'river':
            w = 0.5 + 0.3 * (1 - ctx.villain_stats.river_fold_rate)
        else:
            w = 0.5 + 0.15
        if probe_bluff:
            w += 0.25 * blf.score
        return TriggerResult(True, w + _no_fe_value_weight_add(ctx))

    def sizer(self, ctx: DecisionCtx) -> List[Tuple[float, float]]:
        if _sticky_value_size_up(ctx):
            return [(0.60, 0.40), (0.75, 0.60)]
        if ctx.hero_bucket in ('medium', 'strong', 'nuts'):
            return [(0.50, 0.45), (0.66, 0.55)]
        return [(0.40, 0.35), (0.50, 0.45), (0.66, 0.20)]


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
        blf = bluff_context.evaluate(ctx)
        float_bluff = (
            ctx.hero_bucket in ('air', 'weak_draw')
            and ctx.equity_range >= 0.16
            and ctx.num_opponents <= 2
            and blf.score >= _BLUFF_CONTEXT_PROBE_FLOAT_MIN
            and blf.nuts <= 0.20
            and blf.strong_nuts <= 0.55
        )
        if ctx.equity_range < 0.30 and not float_bluff:
            return TriggerResult(False)
        # Sticky 对手 + bluff bucket 时 float 结构性 -EV（同 ProbeBet 逻辑）。
        # value bucket 保留 —— IP 对 station 的薄价值 stab 仍 +EV。
        if no_fold_equity(ctx) and ctx.hero_bucket in ('air', 'weak_draw'):
            return TriggerResult(False)
        if float_bluff and _sticky_pressure_target(ctx):
            return TriggerResult(False)
        return TriggerResult(True, 0.5 + 0.3 * ctx.villain_stats.bluff_win_rate
                             + 0.25 * blf.score + _no_fe_value_weight_add(ctx))

    def sizer(self, ctx: DecisionCtx) -> List[Tuple[float, float]]:
        if _sticky_value_size_up(ctx):
            return [(0.60, 0.40), (0.75, 0.60)]
        if ctx.hero_bucket in ('medium', 'strong', 'nuts', 'draw'):
            return [(0.50, 0.40), (0.66, 0.60)]
        return [(0.40, 0.45), (0.50, 0.55)]


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
        if _sticky_pressure_target(ctx) and ctx.hero_bucket == 'draw' and not _sticky_semibluff_allowed(
            ctx,
            multiway=ctx.num_opponents > 1,
        ):
            return TriggerResult(False)
        return TriggerResult(True, 0.6 + _no_fe_value_weight_add(ctx))

    def sizer(self, ctx: DecisionCtx) -> List[Tuple[float, float]]:
        if _sticky_value_size_up(ctx) and ctx.hero_bucket in ('strong', 'nuts'):
            return [(0.75, 0.45), (0.90, 0.55)]
        if ctx.hero_bucket in ('strong', 'nuts'):
            return [(0.60, 0.45), (0.75, 0.55)]
        return [(0.40, 0.35), (0.60, 0.50), (0.75, 0.15)]


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
        if _fragile_underpair_after_resistance(ctx):
            return TriggerResult(False)
        need = 0.45 + _barrel_resistance_eq_add(ctx)
        blf = bluff_context.evaluate(ctx)
        if (
            no_fold_equity(ctx)
            and ctx.hero_bucket in ('air', 'weak_draw', 'draw')
            and not _realizable_no_fe_draw(ctx)
        ):
            return TriggerResult(False)
        if (
            _sticky_pressure_target(ctx)
            and ctx.hero_bucket in ('air', 'weak_draw', 'draw')
            and not _sticky_semibluff_allowed(ctx, multiway=ctx.num_opponents > 1)
        ):
            return TriggerResult(False)
        barrel_context_ok = (
            blf.score >= _BLUFF_CONTEXT_BARREL_MIN
            and blf.nuts <= 0.25
            and blf.strong_nuts <= 0.60
        )
        if ctx.hero_bucket in ('air', 'weak_draw', 'draw') and ctx.equity_range < need and not barrel_context_ok:
            return TriggerResult(False)
        # good barrel card = high (A/K/Q) turn or equity >= need
        if ctx.equity_range < need and ctx.board_sig.high_card_rank < 12 and not barrel_context_ok:
            return TriggerResult(False)
        weight = 0.7 + 0.5 * ctx.equity_range + 0.25 * blf.score + _no_fe_value_weight_add(ctx)
        if ctx.hero_bucket in ('air', 'weak_draw', 'draw') and ctx.resistance_level > 0:
            weight *= _BARREL_RESIST_WEIGHT_MULT
        return TriggerResult(True, weight)

    def sizer(self, ctx: DecisionCtx) -> List[Tuple[float, float]]:
        if _sticky_value_size_up(ctx):
            return [(0.66, 0.35), (0.80, 0.45), (0.90, 0.20)]
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
        if _fragile_underpair_after_resistance(ctx):
            return TriggerResult(False)
        if ctx.hero_bucket not in ('nuts', 'strong', 'air'):
            return TriggerResult(False)
        blf = bluff_context.evaluate(ctx)
        if ctx.hero_bucket == 'air' and blf.blocker_score < 0.35:
            return TriggerResult(False)
        if ctx.hero_bucket == 'air' and _sticky_pressure_target(ctx):
            return TriggerResult(False)
        if ctx.hero_bucket in ('air', 'weak_draw', 'draw'):
            need = _barrel_resistance_eq_add(ctx)
            if need > 0 and ctx.equity_range < need:
                return TriggerResult(False)
            if blf.score < 0.60 or blf.nuts > 0.25 or blf.strong_nuts > 0.60:
                return TriggerResult(False)
        if ctx.villain_stats.river_fold_rate < 0.35:
            return TriggerResult(False)
        weight = 0.7 + (0.25 * blf.score if ctx.hero_bucket == 'air' else 0.0)
        if ctx.hero_bucket in ('air', 'weak_draw', 'draw') and ctx.resistance_level > 0:
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
# 18. value_jam
# ---------------------------------------------------------------------------


class ValueJam(Purpose):
    """Explicit value all-in candidate.

    This is not a sizing round-up. It only emits an all-in when the all-in
    amount itself is a reasonable value size (<= 2pot) and the opponent has
    shown payment evidence.
    """

    id = 'value_jam'

    def trigger(self, ctx: DecisionCtx) -> TriggerResult:
        if not _value_jam_legal(ctx):
            return TriggerResult(False)
        eq_need = _commit_value_eq_need(ctx)
        jam_frac = _value_jam_frac(ctx)
        payment_bonus = 0.25 if (ctx.prev_bet_called_count > 0 or ctx.prev_bet_raised) else 0.0
        payment_bonus += min(0.30, ctx.n_sticky * 0.10)
        w = 0.9 + 2.6 * (ctx.equity_range - eq_need) + payment_bonus
        if jam_frac <= 1.0:
            w += 0.25
        return TriggerResult(True, max(0.45, min(2.2, w)))

    def sizer(self, ctx: DecisionCtx) -> List[Tuple[float, float]]:
        jam_frac = _value_jam_frac(ctx)
        if jam_frac <= 0:
            return []
        return [(min(2.0, jam_frac), 1.0)]


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

    权重按 HU/多人分开配置，略高于 default_check。sizer 默认 33%-40%；
    medium+ 或 turn 提到 40%-55%，湿板 air/weak 仍保持 25%-33%。
    """
    id = 'default_stab'
    street_gate = ('flop', 'turn')

    def trigger(self, ctx: DecisionCtx) -> TriggerResult:
        if ctx.facing_bet or not ctx.is_pfr:
            return TriggerResult(False)
        if ctx.num_opponents > 3:
            return TriggerResult(False)
        # 湿板 + air 桶：最危险组合（对手听牌可能性高，stab 失败率高）
        if ctx.board_sig.is_wet and ctx.hero_bucket == 'air':
            return TriggerResult(False)
        if ctx.equity_range < _DS_AIR_MIN_EQ:
            return TriggerResult(False)
        if _sticky_multiway(ctx):
            if ctx.hero_bucket in ('air', 'weak_draw'):
                return TriggerResult(False)
            if ctx.hero_bucket == 'draw' and not _sticky_semibluff_allowed(ctx, multiway=True):
                return TriggerResult(False)
            if ctx.hero_bucket in ('medium', 'strong') and not _sticky_multiway_value_ok(ctx):
                return TriggerResult(False)
        if ctx.num_opponents >= 2 and ctx.equity_range < max(0.40, _DS_AIR_MIN_EQ):
            return TriggerResult(False)
        low_fe = no_fold_equity(ctx)
        if ctx.hero_bucket in ('air', 'weak_draw', 'draw'):
            if _sticky_pressure_target(ctx) and not _sticky_semibluff_allowed(
                ctx,
                multiway=ctx.num_opponents > 1,
            ):
                return TriggerResult(False)
            if _resisted_barrel_spot(ctx):
                if low_fe and not _realizable_no_fe_draw(ctx):
                    return TriggerResult(False)
                resisted_need = 0.45 if ctx.hero_bucket in ('air', 'weak_draw') else 0.40
                if ctx.equity_range < resisted_need + _barrel_resistance_eq_add(ctx):
                    return TriggerResult(False)
            if low_fe:
                if not _realizable_no_fe_draw(ctx):
                    return TriggerResult(False)
                if ctx.equity_range < _DS_LOWFE_MIN_EQ:
                    return TriggerResult(False)
        if ctx.hero_bucket in ('air', 'weak_draw') and low_fe and _DS_LOWFE_MULT <= 0:
            return TriggerResult(False)
        # 2026-04-28 P0.5：HU/多人 权重 env 可调。原 0.45 永远输给 thick_value(0.8+)
        # 和 range_cbet(0.8)，PFR check-frequency 实战 > 60%，远偏离业界 cbet ~55%。
        w = _DS_HU_W if ctx.num_opponents == 1 else _DS_MULTI_W
        if ctx.hero_bucket in ('air', 'weak_draw') and no_fold_equity(ctx):
            w *= _DS_LOWFE_MULT
        if ctx.hero_bucket in ('air', 'weak_draw', 'draw') and ctx.resistance_level > 0:
            w *= _BARREL_RESIST_WEIGHT_MULT
        w += _no_fe_value_weight_add(ctx)
        return TriggerResult(True, w)

    def sizer(self, ctx: DecisionCtx) -> List[Tuple[float, float]]:
        if ctx.hero_bucket in ('medium', 'strong', 'nuts'):
            if _sticky_multiway(ctx) and ctx.hero_bucket == 'medium':
                return [(0.33, 0.45), (0.45, 0.55)]
            if _sticky_value_size_up(ctx):
                return [(0.55, 0.40), (0.66, 0.45), (0.75, 0.15)]
            return [(0.40, 0.45), (0.55, 0.55)]
        if ctx.street == 'turn':
            return [(0.40, 0.45), (0.55, 0.55)]
        if ctx.board_sig.is_wet and ctx.hero_bucket in ('air', 'weak_draw'):
            return [(0.25, 0.55), (0.33, 0.45)]
        return [(0.33, 0.45), (0.40, 0.55)]


# ---------------------------------------------------------------------------
# 20. profit expansion v1 + targeted default-on profit branches
# ---------------------------------------------------------------------------


class ProfitFlopCbet(Purpose):
    """PFR small c-bet expansion.

    Broad expansion remains behind PF_POSTFLOP_PROFIT_EXPAND_V1.  Capped,
    high-fold-equity bluff nodes are default-on because they are the narrow
    profit branch we want, not a blanket c-bet frequency increase.
    """

    id = 'profit_flop_cbet'
    street_gate = ('flop',)

    def trigger(self, ctx: DecisionCtx) -> TriggerResult:
        if ctx.facing_bet or not ctx.is_pfr:
            return TriggerResult(False)
        if ctx.num_opponents > 2 or ctx.spr < 3.0:
            return TriggerResult(False)
        blf = bluff_context.evaluate(ctx)
        capped_high_fe = _capped_high_fe_bluff_ok(ctx, blf, turn=False)
        if not _PROFIT_EXPAND_V1 and not capped_high_fe:
            return TriggerResult(False)
        if _PROFIT_EXPAND_V1:
            if not _profit_expand_board_ok(ctx):
                return TriggerResult(False)
        elif ctx.hero_bucket not in ('air', 'weak_draw', 'draw'):
            return TriggerResult(False)

        if ctx.hero_bucket in ('air', 'weak_draw'):
            if no_fold_equity(ctx) or _sticky_pressure_target(ctx):
                return TriggerResult(False)
            if ctx.equity_range < 0.16:
                return TriggerResult(False)
            if not (
                blf.score >= 0.42
                or ctx.board_sig.is_dry
                or ctx.board_sig.high_card_rank >= 12
            ):
                return TriggerResult(False)
            weight = 0.55 + 0.25 * blf.score
            if capped_high_fe:
                weight += 0.20
            return TriggerResult(True, weight)

        if ctx.hero_bucket == 'draw':
            if _sticky_pressure_target(ctx) and not _sticky_semibluff_allowed(
                ctx,
                multiway=ctx.num_opponents > 1,
            ):
                return TriggerResult(False)
            if no_fold_equity(ctx) and not _realizable_no_fe_draw(ctx):
                return TriggerResult(False)
            if ctx.equity_range < 0.22:
                return TriggerResult(False)
            weight = 0.70 + 0.20 * blf.score
            if capped_high_fe:
                weight += 0.15
            return TriggerResult(True, weight)

        if ctx.hero_bucket == 'medium':
            if _sticky_multiway(ctx) and not _sticky_multiway_value_ok(ctx):
                return TriggerResult(False)
            if ctx.equity_range < 0.35 and not _safe_medium_protection_hand(ctx):
                return TriggerResult(False)
            return TriggerResult(True, 0.75 + _no_fe_value_weight_add(ctx))

        return TriggerResult(False)

    def sizer(self, ctx: DecisionCtx) -> List[Tuple[float, float]]:
        if ctx.hero_bucket in ('air', 'weak_draw'):
            if ctx.board_sig.is_dry:
                return [(0.25, 0.35), (0.33, 0.50), (0.40, 0.15)]
            return [(0.33, 0.55), (0.40, 0.45)]
        if ctx.hero_bucket == 'draw':
            return [(0.40, 0.45), (0.50, 0.55)]
        return [(0.40, 0.35), (0.50, 0.45), (0.60, 0.20)]

    def alpha_target(self, ctx: DecisionCtx, frac: float) -> Optional[float]:
        return None


class ProfitDelayedProbe(Purpose):
    """Turn stab after flop checks through.

    Broad delayed/probe expansion remains opt-in.  Capped high-FE bluff stabs
    are default-on and still require fold equity plus blockers/draw support.
    """

    id = 'profit_delayed_probe'
    street_gate = ('turn',)

    def trigger(self, ctx: DecisionCtx) -> TriggerResult:
        if ctx.facing_bet or not ctx.flop_checked_through:
            return TriggerResult(False)
        delayed_path = ctx.is_pfr
        probe_path = (not ctx.is_pfr and not ctx.is_ip)
        if not (delayed_path or probe_path):
            return TriggerResult(False)
        if ctx.num_opponents > 2 or ctx.spr < 2.5:
            return TriggerResult(False)
        blf = bluff_context.evaluate(ctx)
        capped_high_fe = _capped_high_fe_bluff_ok(ctx, blf, turn=True)
        if not _PROFIT_EXPAND_V1 and not capped_high_fe:
            return TriggerResult(False)
        if _PROFIT_EXPAND_V1:
            if not _profit_expand_capped_turn(ctx):
                return TriggerResult(False)
        elif ctx.hero_bucket not in ('air', 'weak_draw', 'draw'):
            return TriggerResult(False)

        if ctx.hero_bucket in ('air', 'weak_draw'):
            if no_fold_equity(ctx) or _sticky_pressure_target(ctx):
                return TriggerResult(False)
            if ctx.equity_range < 0.16 or blf.score < 0.55:
                return TriggerResult(False)
            if not (ctx.blockers.count() > 0 or ctx.draw.overcards or ctx.draw.gutshot):
                return TriggerResult(False)
            weight = 0.52 + 0.38 * blf.score
            if capped_high_fe:
                weight += 0.18
            return TriggerResult(True, weight)

        if ctx.hero_bucket == 'draw':
            if _sticky_pressure_target(ctx) and not _sticky_semibluff_allowed(
                ctx,
                multiway=ctx.num_opponents > 1,
            ):
                return TriggerResult(False)
            if no_fold_equity(ctx) and not _realizable_no_fe_draw(ctx):
                return TriggerResult(False)
            if ctx.equity_range < 0.28:
                return TriggerResult(False)
            weight = 0.62 + 0.25 * blf.score
            if capped_high_fe:
                weight += 0.12
            return TriggerResult(True, weight)

        if ctx.hero_bucket == 'medium':
            if _sticky_multiway(ctx) and not _sticky_multiway_value_ok(ctx):
                return TriggerResult(False)
            if ctx.equity_range < 0.38 and not _safe_medium_protection_hand(ctx):
                return TriggerResult(False)
            return TriggerResult(True, 0.68 + _no_fe_value_weight_add(ctx))

        if ctx.hero_bucket in ('strong', 'nuts'):
            if _sticky_multiway(ctx) and not _sticky_multiway_value_ok(ctx):
                return TriggerResult(False)
            return TriggerResult(True, 0.78 + _no_fe_value_weight_add(ctx))

        return TriggerResult(False)

    def sizer(self, ctx: DecisionCtx) -> List[Tuple[float, float]]:
        if ctx.hero_bucket in ('air', 'weak_draw'):
            return [(0.33, 0.45), (0.45, 0.40), (0.55, 0.15)]
        if ctx.hero_bucket == 'draw':
            return [(0.45, 0.40), (0.55, 0.45), (0.66, 0.15)]
        if ctx.hero_bucket in ('strong', 'nuts'):
            if _sticky_value_size_up(ctx) or _sticky_value_target(ctx):
                return [(0.66, 0.45), (0.80, 0.55)]
            return [(0.55, 0.45), (0.66, 0.55)]
        return [(0.45, 0.45), (0.55, 0.40), (0.66, 0.15)]

    def alpha_target(self, ctx: DecisionCtx, frac: float) -> Optional[float]:
        return None


class ProfitPaidValueContinue(Purpose):
    """Multi-street value continuation after a prior call.

    This purpose does not reduce losing hands.  It only adds a high-priority
    value candidate when villain has already paid a bet and hero still has a
    value edge under bucket/relative-strength checks.
    """

    id = 'profit_paid_value_continue'
    street_gate = ('turn', 'river')

    def trigger(self, ctx: DecisionCtx) -> TriggerResult:
        if not _profit_expand_paid_value_ok(ctx):
            return TriggerResult(False)
        base = 1.10
        if ctx.hero_bucket == 'nuts':
            base += 0.35
        elif ctx.hero_bucket == 'strong':
            base += 0.20
        if _sticky_value_target(ctx):
            base += 0.20
        if ctx.prev_bet_called_count >= 2:
            base += 0.15
        return TriggerResult(True, min(1.80, base))

    def sizer(self, ctx: DecisionCtx) -> List[Tuple[float, float]]:
        sticky = _sticky_value_target(ctx) or ctx.n_sticky >= 1
        if ctx.street == 'river':
            if ctx.hero_bucket == 'nuts' and sticky:
                return [(0.75, 0.35), (0.90, 0.45), (1.00, 0.20)]
            if ctx.hero_bucket == 'medium':
                if sticky:
                    return [(0.55, 0.45), (0.66, 0.45), (0.75, 0.10)]
                return [(0.40, 0.40), (0.55, 0.45), (0.66, 0.15)]
            if sticky:
                return [(0.66, 0.35), (0.75, 0.45), (0.90, 0.20)]
            return [(0.55, 0.35), (0.66, 0.45), (0.75, 0.20)]
        if sticky:
            return [(0.66, 0.35), (0.75, 0.45), (0.85, 0.20)]
        return [(0.55, 0.35), (0.66, 0.45), (0.75, 0.20)]

    def alpha_target(self, ctx: DecisionCtx, frac: float) -> Optional[float]:
        return None


# ---------------------------------------------------------------------------
# All active purposes
# ---------------------------------------------------------------------------


def all_active() -> list:
    return [
        ProfitFlopCbet(), ProfitDelayedProbe(), ProfitPaidValueContinue(),
        RangeCbet(), PolarizedCbet(), ProtectionBet(),
        ThinValueBet(),
        MonsterValuePlan(), ThickValueBet(), BlockBet(),
        OverbetValue(), SemiBluff(), PureBluffRiver(),
        DelayedCbet(), ProbeBet(), FloatBet(),
        TurnDonk(), DoubleBarrel(), TripleBarrel(),
        StopAndGo(), ValueJam(), DefaultStab(),
    ]
