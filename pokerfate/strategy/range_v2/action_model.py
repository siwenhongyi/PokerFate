"""Action likelihood model: P(action | hand_i, context, player_profile).

The core of Range V2.  For each of 1326 combos, returns the probability
that the opponent would take the observed action holding that combo.

Three-layer architecture (reference: Johanson et al., AAMAS 2009):
  Layer 1 — GTO baseline frequencies
  Layer 2 — Opponent statistics scaling
  Layer 3 — Confidence interpolation (GTO ↔ observed)

GTO preflop ranges: GTO Wizard 6-max + Upswing Poker.
GTO postflop frequencies: GTO Wizard aggregated solutions + PioSolver buckets.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

import numpy as np

from pokerfate.core.card import Card
from pokerfate.core.config import MIN_HANDS_FOR_CLASSIFICATION
from pokerfate.strategy.range_v2 import hand_combo_map as hcm
from pokerfate.strategy.range_v2 import hand_categorizer as hcat
from pokerfate.strategy.range_v2.blocker import blocker_weights

# ---------------------------------------------------------------------------
# Context passed to the likelihood function
# ---------------------------------------------------------------------------

@dataclass
class ActionContext:
    position: str             # opponent's position: UTG/MP/CO/BTN/SB/BB
    board: List[Card]         # current community cards
    street: str               # preflop/flop/turn/river
    facing_action: str        # what they're responding to: 'open'/'3bet'/'4bet'/'none'/'bet'/'check'
    facing_cbet: bool = False # is this response to a c-bet?
    # bet size / pot ratio of this action (0 = unknown or not a bet).
    # API now supplies a pre-action pot snapshot for first bets and raise-over
    # spots; the latter is deliberately kept because large reraises carry
    # strong range information.
    bet_ratio: float = 0.0
    # True = this raise is over someone's bet (re-raise / CR); False = first bet
    is_raise_over: bool = False


# ---------------------------------------------------------------------------
# Player profile (read-only view of OpponentStats)
# ---------------------------------------------------------------------------

@dataclass
class PlayerProfile:
    """Read-only snapshot of opponent statistics for likelihood computation.

    All data comes from OpponentModel — this module never writes to it.
    """
    name: str = ""
    hands_seen: int = 0
    vpip: float = 0.35
    pfr: float = 0.20
    af: float = 2.0
    three_bet_pct: float = 0.06
    fold_to_3bet: float = 0.55
    fold_to_cbet: float = 0.45
    fold_to_cbet_opps: int = 0
    wtsd: float = 0.25
    wmsd: float = 0.50
    flop_afq: float = 0.45
    turn_afq: float = 0.40
    river_afq: float = 0.35
    river_fold_rate: float = 0.35
    river_bet_freq: float = 0.35
    bluff_win_rate: float = 0.0
    bet_win_count: int = 0
    river_bet_count: int = 0
    river_check_count: int = 0
    # (player_type removed — was never read by any action_model code path.
    #  Everything that needs a behavioural classifier derives it from raw
    #  stats: bluff_win_rate drives air_scale, vpip-pfr gap drives
    #  medium/strong, af drives global aggression scale. See review
    #  02_action_model §3.1.)
    pwi: float = 0.0
    # Samples for street-level AFq reliability
    flop_action_count: int = 0  # flop_bet + flop_passive
    turn_action_count: int = 0
    river_action_count: int = 0      # river bet/call/check samples for AFq reliability
    river_facing_bet_opps: int = 0   # facing-river-bet fold opportunities
    # Server priors (only AF and WTSD remain — 3bet/cbet server data are
    # parsed for forward-compat but not propagated here)
    server_af_prior: float = 0.0
    server_wtsd_prior: float = 0.0

    @property
    def server_priors_available(self) -> bool:
        return self.server_af_prior > 0 or self.server_wtsd_prior > 0

    def street_afq(self, street: str) -> Optional[float]:
        """Return street-level AFq if enough samples, else None."""
        if street == 'flop' and self.flop_action_count >= 30:
            return self.flop_afq
        if street == 'turn' and self.turn_action_count >= 30:
            return self.turn_afq
        if street == 'river' and self.river_action_count >= 30:
            return self.river_afq
        return None


# ---------------------------------------------------------------------------
# GTO baseline constants
# ---------------------------------------------------------------------------

# GTO preflop ranges by position (fraction of 1326 combos)
# Source: GTO Wizard 6-max Cash 100bb
GTO_VPIP: Dict[str, float] = {
    'UTG': 0.16, 'MP': 0.19, 'CO': 0.27, 'BTN': 0.43,
    'SB': 0.38, 'BB': 0.40,
}
GTO_PFR: Dict[str, float] = {
    'UTG': 0.14, 'MP': 0.17, 'CO': 0.25, 'BTN': 0.38,
    'SB': 0.30, 'BB': 0.12,
}
GTO_3BET: Dict[str, float] = {
    'UTG': 0.025, 'MP': 0.035, 'CO': 0.06, 'BTN': 0.09,
    'SB': 0.10, 'BB': 0.12,
}

# GTO postflop frequencies per bucket per street
# Source: GTO Wizard aggregated, PioSolver equity buckets
# freq[street][category][action] → probability
GTO_POSTFLOP_FREQ: Dict[str, Dict[str, Dict[str, float]]] = {
    'flop': {
        'nuts':      {'raise': 0.55, 'call': 0.35, 'check': 0.10, 'fold': 0.00},
        'strong':    {'raise': 0.15, 'call': 0.50, 'check': 0.35, 'fold': 0.00},
        'medium':    {'raise': 0.05, 'call': 0.35, 'check': 0.45, 'fold': 0.15},
        'draw':      {'raise': 0.20, 'call': 0.55, 'check': 0.20, 'fold': 0.05},
        'weak_draw': {'raise': 0.05, 'call': 0.25, 'check': 0.40, 'fold': 0.30},
        'air':       {'raise': 0.08, 'call': 0.02, 'check': 0.40, 'fold': 0.50},
    },
    'turn': {
        'nuts':      {'raise': 0.60, 'call': 0.30, 'check': 0.10, 'fold': 0.00},
        'strong':    {'raise': 0.20, 'call': 0.50, 'check': 0.25, 'fold': 0.05},
        'medium':    {'raise': 0.05, 'call': 0.30, 'check': 0.35, 'fold': 0.30},
        'draw':      {'raise': 0.18, 'call': 0.45, 'check': 0.15, 'fold': 0.22},
        'weak_draw': {'raise': 0.03, 'call': 0.15, 'check': 0.27, 'fold': 0.55},
        'air':       {'raise': 0.06, 'call': 0.02, 'check': 0.22, 'fold': 0.70},
    },
    'river': {
        'nuts':      {'raise': 0.65, 'call': 0.30, 'check': 0.05, 'fold': 0.00},
        'strong':    {'raise': 0.20, 'call': 0.55, 'check': 0.20, 'fold': 0.05},
        'medium':    {'raise': 0.03, 'call': 0.40, 'check': 0.22, 'fold': 0.35},
        'draw':      None,  # river: draws become air
        'weak_draw': None,
        'air':       {'raise': 0.10, 'call': 0.02, 'check': 0.18, 'fold': 0.70},
    },
}

# GTO baseline AFq per street (for scaling)
GTO_AFQ_BASELINE: Dict[str, float] = {'flop': 0.45, 'turn': 0.40, 'river': 0.35}

# Confidence thresholds — how many hands before a stat is trusted
# Reference: PokerTracker / Hold'em Manager guidelines
CONFIDENCE_THRESHOLDS: Dict[str, int] = {
    'vpip': 50, 'pfr': 50, 'af': 80, 'three_bet': 150,
    'fold_to_cbet': 60, 'wtsd': 200, 'street_afq': 30,
    'bluff_wr': 20, 'river_bf': 30,
}


# 向量化用的 category 顺序与索引映射。改这两行的顺序会破坏向量化代码 ——
# 后续任何 cat_per_idx[CAT_IDX[X]] 假定固定顺序。
_CAT_ORDER = ('nuts', 'strong', 'medium', 'draw', 'weak_draw', 'air')
_CAT_IDX = {c: i for i, c in enumerate(_CAT_ORDER)}
_CAT_IDX_DRAW = _CAT_IDX['draw']
_CAT_IDX_WEAK_DRAW = _CAT_IDX['weak_draw']
_CAT_IDX_AIR = _CAT_IDX['air']


# ---------------------------------------------------------------------------
# Bet sizing → category adjustment (postflop only)
# ---------------------------------------------------------------------------
# Issue K (2026-04-21 gameplay analysis hand 26 + hand 68): the original
# single SIZING_CATEGORY_ADJ table assumed villain range is ALWAYS polarized
# at large/overbet sizings (nuts + bluff, no medium). That's true for regs
# and solver-style players but WRONG for fish/whale/station — they use
# merged ranges (value + medium + some bluff) even at large sizes.
#
# Two base tables; real adjustment interpolates by a continuous
# `polarization_index ∈ [0,1]` derived from low-level stats (AF, WTSD, VPIP).
# We deliberately do NOT dispatch on `player_type` labels — labels are
# thresholded derivatives of these same metrics and introduce artificial
# jumps at boundaries (the "label异化特征" problem).

# Polarized table: derived from PioSolver / MDF. Accurate for regs.
# Large/overbet: villain nuts ↑, medium ↓ hard, air ↑.
SIZING_CATEGORY_ADJ_POLARIZED: Dict[str, Dict[str, float]] = {
    'tiny': {       # <40% pot: blocking bet / probe
        'nuts': 0.7, 'strong': 1.0, 'medium': 1.3,
        'draw': 1.2, 'weak_draw': 1.1, 'air': 1.0,
    },
    'small': {      # 40-60% pot: standard half-pot
        'nuts': 0.9, 'strong': 1.0, 'medium': 1.1,
        'draw': 1.0, 'weak_draw': 0.9, 'air': 0.9,
    },
    'medium': {     # 60-90% pot: GTO baseline, no adjustment
        'nuts': 1.0, 'strong': 1.0, 'medium': 1.0,
        'draw': 1.0, 'weak_draw': 1.0, 'air': 1.0,
    },
    'large': {      # 90-130% pot: pot-sized, high polarization
        'nuts': 1.3, 'strong': 0.9, 'medium': 0.5,
        'draw': 0.6, 'weak_draw': 0.4, 'air': 1.2,
    },
    'overbet': {    # >130% pot: extreme polarization (nuts + pure bluff)
        'nuts': 1.5, 'strong': 0.7, 'medium': 0.3,
        'draw': 0.4, 'weak_draw': 0.3, 'air': 1.6,
    },
}

# Merged table: for non-polarizing players (fish / whale / calling station).
# Large sizing from fish is "I think I have something" — range is
# value + medium, rarely pure bluff, rarely pure nuts.
# Sources:
#   - Upswing Lab "Exploitation Against Calling Stations": fish large bets
#     are 5-15% nuts, 30-40% strong, 40-50% medium, 5-10% bluff (~uniform).
#   - Janda 2015 ch.3-4: merged range = value + medium + occasional bluff.
#   - PokerTracker Analytics (public) on VPIP>40% large-bet composition.
# Multipliers: pulled toward 1.0 (neutral) vs polarized; nuts/air no longer
# spike, medium not crushed.
SIZING_CATEGORY_ADJ_MERGED: Dict[str, Dict[str, float]] = {
    'tiny': {       # fish tiny bet: similar to probe — slight medium lean
        'nuts': 0.8, 'strong': 1.0, 'medium': 1.2,
        'draw': 1.1, 'weak_draw': 1.0, 'air': 0.9,
    },
    'small': {      # fish half-pot: near-flat likelihood
        'nuts': 0.95, 'strong': 1.0, 'medium': 1.05,
        'draw': 1.0, 'weak_draw': 0.95, 'air': 0.95,
    },
    'medium': {     # neutral — same as polarized baseline
        'nuts': 1.0, 'strong': 1.0, 'medium': 1.0,
        'draw': 1.0, 'weak_draw': 1.0, 'air': 1.0,
    },
    'large': {      # fish large bet: merged — medium NOT crushed
        # 2026-04-23：air 从 0.85 压到 0.60。原 0.85 让 air 和 medium 系数
        # 几乎相同（0.85 vs 0.85），违背 "fish pot-size barrel 极少 bluff"
        # 的经验（Upswing 实证 fish large bet 5-10% bluff，40-50% medium）。
        # 实战 -10BB QQ 个案：fish pot-size 双街 barrel → tracker 窄化出
        # 坚果 58%，实际 villain 只拿一对，hero 错弃 QQ。0.60 介于 overbet
        # 的 0.50 和旧 0.85 之间，既压制 air 又承认 fish 在 large 比 overbet
        # 更可能（非最纯 polar）有诈唬成分。
        'nuts': 1.10, 'strong': 1.0, 'medium': 0.85,
        'draw': 0.85, 'weak_draw': 0.70, 'air': 0.60,
    },
    'overbet': {    # fish overbet: still merged, slight tilt toward value
        # 2026-04-23：air 从 1.10 改到 0.50。之前 1.10 和注释 "fish 5-10% bluff"
        # 矛盾（Upswing 实证极低 bluff，系数应压制 air 而不是略放大）。1.10 导致
        # 实战中 fish 4.6x pot donk 的窄化后 range 仍然 46% air，hero 用中等牌
        # 做 bluff-catch 按"air 高比例"算出的 equity 虚高（H33 -54BB 个案：
        # 88 vs fish 4.6x pot donk，equity 显示 49%，真实 ~30%，44% pot odds
        # 下应弃牌但 call 了）。0.5 把 air likelihood 压到约 baseline 的一半，
        # 符合 fish 极低诈唬频率。
        'nuts': 1.25, 'strong': 0.95, 'medium': 0.65,
        'draw': 0.70, 'weak_draw': 0.50, 'air': 0.50,
    },
}

# Kept as alias for any external reference to the old name.
SIZING_CATEGORY_ADJ = SIZING_CATEGORY_ADJ_POLARIZED


def _sizing_bucket(bet_ratio: float) -> str:
    """Classify bet/pot ratio into a sizing bucket."""
    if bet_ratio <= 0:
        return 'medium'  # unknown or not a first-bet — no adjustment
    if bet_ratio < 0.40:
        return 'tiny'
    if bet_ratio < 0.60:
        return 'small'
    if bet_ratio < 0.90:
        return 'medium'
    if bet_ratio < 1.30:
        return 'large'
    return 'overbet'


def _polarization_index(profile: 'PlayerProfile') -> float:
    """Continuous polarization index ∈ [0.0, 1.0].

    0.0 = fully merged (fish/whale behaviour — bet range is value+medium)
    1.0 = fully polarized (reg/solver — bet range is nuts+bluff, no medium)

    Built from LOW-LEVEL stats (AF, WTSD, VPIP) — NOT player_type labels.
    Labels are thresholded buckets of the same underlying metrics and
    create artificial jumps at boundaries (e.g. VPIP 55% is 'calling
    station' but 54.9% isn't). Continuous interpolation avoids this.

    Weights:
      AF     (50%): primary polarization signal. AF<1.5 → fish/whale
                    (merged); AF>2.5 → aggressive reg (polarized).
      WTSD   (30%): high WTSD → shows weak hands = merged; low = polarized.
      VPIP   (20%): tie-breaker. High VPIP → loose fish → merged.
    """
    # Cold start: no data → default to mid-polarization (conservative —
    # don't over-assume either direction when below MIN_HANDS_FOR_CLASSIFICATION).
    if profile.hands_seen < MIN_HANDS_FOR_CLASSIFICATION:
        return 0.5

    # AF: 1.0 → 0.0 (passive, merged), 3.0 → 1.0 (aggressive, polarized).
    af_score = _clip((profile.af - 1.0) / 2.0, 0.0, 1.0)

    # WTSD: 0.35 → 0.0 (loose showdown, merged),
    #       0.20 → 1.0 (tight showdown, polarized).
    # If sample is thin (< 15 flop_seen), use VPIP as proxy instead.
    if profile.flop_action_count >= 15:
        wtsd_score = _clip((0.35 - profile.wtsd) / 0.15, 0.0, 1.0)
    else:
        # Fallback — overweight VPIP when WTSD sample is thin.
        wtsd_score = _clip((0.50 - profile.vpip) / 0.25, 0.0, 1.0)

    # VPIP: tight range → polarized; loose range → merged.
    # 0.50 → 0.0, 0.25 → 1.0.
    vpip_score = _clip((0.50 - profile.vpip) / 0.25, 0.0, 1.0)

    return 0.5 * af_score + 0.3 * wtsd_score + 0.2 * vpip_score


def _sizing_adj_for(bucket: str, profile: 'PlayerProfile') -> Dict[str, float]:
    """Return the per-category sizing adjustment for this bucket/player.

    Linearly interpolates between MERGED and POLARIZED tables by the
    continuous `polarization_index`. A player halfway between fish and reg
    gets an adjustment halfway between the two tables, not a hard bucket
    change.

    2026-04-23：unknown 对手（hands_seen < MIN）把偏离 1.0 的幅度阻尼 50%。
    引用 BlackRain79：未知对手不应按激进先验处理（可能是 whale 也可能是
    reg），sizing 信号本身可靠，但从"什么类型玩家"这层 prior 太弱——把
    polar/merged 的任何调整向中性 1.0 拉回一半，避免冷启动 + 连续 barrel
    组合下的过度窄化。样本足够后自动恢复全强度。
    """
    p = _polarization_index(profile)
    polar = SIZING_CATEGORY_ADJ_POLARIZED.get(bucket, SIZING_CATEGORY_ADJ_POLARIZED['medium'])
    merged = SIZING_CATEGORY_ADJ_MERGED.get(bucket, SIZING_CATEGORY_ADJ_MERGED['medium'])
    raw = {cat: merged[cat] * (1.0 - p) + polar[cat] * p for cat in polar}

    # Unknown opponent damping (D)
    if profile.hands_seen < MIN_HANDS_FOR_CLASSIFICATION and not profile.server_priors_available:
        damping = 0.5   # 偏离 1.0 幅度保留 50%
        return {cat: 1.0 + damping * (raw[cat] - 1.0) for cat in raw}
    return raw


def _clip(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def _confidence(stat_name: str, sample_count: int) -> float:
    """[0, 1] confidence for GTO↔observed interpolation."""
    thr = CONFIDENCE_THRESHOLDS.get(stat_name, 80)
    return min(1.0, sample_count / thr)


# ---------------------------------------------------------------------------
# ActionModel
# ---------------------------------------------------------------------------

class ActionModel:
    """Compute P(action | combo, context, profile) for all 1326 combos.

    Used by BayesianRangeTracker to perform Bayesian updates.
    """

    def __init__(self, showdown_learner=None):
        self.showdown_learner = showdown_learner
        # Per-board categorization cache. Same board reused across all opp
        # actions on the same street → 1326 hcat.categorize() calls per
        # notify_action used to dominate hot path. Cache key = sorted tuple
        # of card ints (insensitive to card order).
        self._cat_cache_key: Optional[tuple] = None
        self._cat_cache: Optional[List[str]] = None
        # 向量化加速辅助：cat int 数组 + river merge 数组（draw/weak_draw → air）
        self._cat_idx_cache: Optional[np.ndarray] = None
        self._cat_idx_river_cache: Optional[np.ndarray] = None

    def batch_likelihood(
        self,
        action: str,
        street: str,
        context: ActionContext,
        profile: PlayerProfile,
        board: List[Card],
        hero_cards: Optional[List[Card]] = None,
    ) -> np.ndarray:
        """Return likelihood[1326] for every combo given the observed action.

        This is the hot path — vectorized where possible.
        """
        if street == 'preflop':
            return self._preflop_batch(action, context, profile)
        else:
            return self._postflop_batch(
                action, street, context, profile, board, hero_cards
            )

    # ------------------------------------------------------------------
    # Preflop
    # ------------------------------------------------------------------

    def _preflop_batch(self, action: str, ctx: ActionContext,
                       prof: PlayerProfile) -> np.ndarray:
        """Vectorized preflop likelihood for all 1326 combos."""
        strengths = hcm.STRENGTH_PCT  # (1326,)
        result = np.empty(1326, dtype=np.float64)

        pos = ctx.position if ctx.position else 'CO'
        gto_vpip = GTO_VPIP.get(pos, 0.27)
        gto_pfr = GTO_PFR.get(pos, 0.20)
        gto_3bet = GTO_3BET.get(pos, 0.06)

        # Effective ranges for this opponent
        conf = _confidence('vpip', prof.hands_seen)
        eff_vpip = conf * prof.vpip + (1 - conf) * gto_vpip
        eff_pfr = conf * prof.pfr + (1 - conf) * gto_pfr

        # Handle server priors for cold start
        if prof.hands_seen < MIN_HANDS_FOR_CLASSIFICATION and prof.server_priors_available:
            conf = 0.3
            eff_vpip = 0.3 * prof.vpip + 0.7 * gto_vpip if prof.hands_seen >= 5 else gto_vpip
            eff_pfr = 0.3 * prof.pfr + 0.7 * gto_pfr if prof.hands_seen >= 5 else gto_pfr

        # Thresholds on strength axis (1.0 = strongest)
        raise_thresh = 1.0 - eff_pfr
        call_floor = 1.0 - eff_vpip

        # Adjust for 3bet/4bet
        if ctx.facing_action in ('3bet', '4bet'):
            eff_3bet = _confidence('three_bet', prof.hands_seen) * prof.three_bet_pct + \
                       (1 - _confidence('three_bet', prof.hands_seen)) * gto_3bet
            raise_thresh = 1.0 - eff_3bet
            # Call range vs 3bet is narrower
            call_floor = raise_thresh - eff_vpip * 0.3

        if action == 'raise':
            # In raise range → high freq; outside → very low
            in_range = strengths >= raise_thresh
            result[in_range] = 0.92
            result[~in_range] = 0.02
            # Transition zone: just below threshold
            transition = (strengths >= raise_thresh - 0.05) & (~in_range)
            result[transition] = 0.15

            # Deep open-shove / overbet narrow (2026-04-23)：翻前首加大 ≥ 10× pot
            # （pot = 盲注 ≈ 1.5bb 时对应开 ≥ 15bb；蛰伏 all-in 更甚）。这种尺寸
            # 的 range 应快速坍缩到顶端 {99+, AK+} 级别，不再按 VPIP/PFR 宽度
            # 建模。策略：按 STRENGTH_PCT 分三档 likelihood 乘子。
            # 触发门槛 bet_ratio >= 10 刻意高：正常 open (2-3bb→bet_ratio 1.5-2)
            # 和常规 3bet/4bet 都低于 10，不会误触。
            if ctx and ctx.bet_ratio >= 10.0 and not ctx.is_raise_over:
                mult = np.where(
                    strengths >= 0.96, 1.0,
                    np.where(strengths >= 0.85, 0.30, 0.05),
                )
                result *= mult

        elif action == 'call':
            in_call = (strengths >= call_floor) & (strengths < raise_thresh)
            result[in_call] = 0.85
            # Some hands in raise range might flat
            in_raise = strengths >= raise_thresh
            result[in_raise] = 0.08
            # Below VPIP → very unlikely
            below = strengths < call_floor
            result[below] = 0.02
            # Transition zone
            transition = (strengths >= call_floor - 0.05) & below
            result[transition] = 0.10

        elif action == 'fold':
            below_vpip = strengths < call_floor
            result[below_vpip] = 0.93
            in_call = (strengths >= call_floor) & (strengths < raise_thresh)
            result[in_call] = 0.05
            in_raise = strengths >= raise_thresh
            result[in_raise] = 0.02

        else:  # check (BB option)
            result[:] = 0.5  # check is uninformative

        # Floor: never let likelihood drop to absolute zero (Bayes robustness)
        np.maximum(result, 0.01, out=result)

        return result

    # ------------------------------------------------------------------
    # Postflop
    # ------------------------------------------------------------------

    def _postflop_batch(self, action: str, street: str,
                        ctx: ActionContext, prof: PlayerProfile,
                        board: List[Card],
                        hero_cards: Optional[List[Card]] = None) -> np.ndarray:
        """Postflop likelihood for all 1326 combos. 向量化版本。"""
        # Pre-categorize all combos on this board (cached per-board).
        cat_idx = self._cat_indices(board, street)  # int8[1326], river-merged
        # cache 内的"未参与"格子 (board 冲突) 在 _categorize_all 里默认 'air'，
        # 与原循环的 `categories[idx]` 默认 'air' 行为一致。

        gto_street = GTO_POSTFLOP_FREQ.get(street, GTO_POSTFLOP_FREQ['flop'])
        bet_ratio = ctx.bet_ratio if ctx else 0.0
        cat_scales = self._compute_category_scales(action, street, prof, bet_ratio)

        # Per-category GTO freq (按 _CAT_ORDER 顺序拿 P(action|cat))
        # river 已经在 cat_idx 内 merge 过，这里直接按 6 桶取
        gto_per_cat = np.empty(6, dtype=np.float64)
        for i, c in enumerate(_CAT_ORDER):
            cat_dict = gto_street.get(c) or gto_street['air']
            gto_per_cat[i] = cat_dict.get(action, 0.1)
        # Per-category scale
        scale_per_cat = np.array(
            [cat_scales.get(c, 1.0) for c in _CAT_ORDER], dtype=np.float64
        )

        # Vectorized lookup
        gto_freqs = gto_per_cat[cat_idx]
        scales_arr = scale_per_cat[cat_idx]

        # adjusted = clip(gto_freq * scale, 0.01, 0.99)
        adjusted = np.clip(gto_freqs * scales_arr, 0.01, 0.99)

        # result = conf * adjusted + (1 - conf) * gto_freq
        conf = _confidence('af', prof.hands_seen)
        result = conf * adjusted + (1.0 - conf) * gto_freqs

        # Showdown learner override (vectorized blend)
        if self.showdown_learner is not None and prof.name:
            learned = self.showdown_learner.get_learned_freq(
                prof.name, street, action
            )
            if learned is not None:
                n = self.showdown_learner.sample_count(prof.name, street, action)
                blend = n / (n + 50.0)
                # 按 _CAT_ORDER 取 learned 频率，缺失桶回落 0.01
                learned_per_cat = np.array(
                    [_clip(float(learned.get(c, 0.01)), 0.01, 0.99)
                     for c in _CAT_ORDER],
                    dtype=np.float64,
                )
                learned_arr = learned_per_cat[cat_idx]
                result = (1.0 - blend) * result + blend * learned_arr

        # Polar reraise narrow (vectorized)
        if (action == 'raise'
                and ctx is not None
                and ctx.is_raise_over
                and street in ('turn', 'river')
                and prof.hands_seen >= MIN_HANDS_FOR_CLASSIFICATION
                and prof.af < 1.5):
            # _CAT_ORDER = ('nuts', 'strong', 'medium', 'draw', 'weak_draw', 'air')
            # 对应 multipliers (river-merge 后 draw/weak_draw 已变 air，但本数组
            # 仍按原 6 桶给值；river-merged cat_idx 里这两桶不会出现，所以无影响)
            polar_mul = np.array([1.8, 0.55, 0.20, 0.10, 0.10, 0.10], dtype=np.float64)
            result *= polar_mul[cat_idx]
            np.clip(result, 0.01, 0.99, out=result)

        # Hero blocker (already vectorized in blocker_weights)
        if hero_cards:
            result *= blocker_weights(hero_cards, board)

        # Floor
        np.maximum(result, 0.01, out=result)

        return result

    def _postflop_batch_legacy(self, action: str, street: str,
                                ctx: ActionContext, prof: PlayerProfile,
                                board: List[Card],
                                hero_cards: Optional[List[Card]] = None
                                ) -> np.ndarray:
        """旧版未向量化的 _postflop_batch，作为金标准只用于等价性测试。

        切勿在 hot path 调用 —— 性能为旧版水平。任何对 _postflop_batch 的
        优化必须保证 batch_likelihood 输出与本函数逐元素一致。
        """
        result = np.empty(1326, dtype=np.float64)
        categories = self._categorize_all(board)
        gto_street = GTO_POSTFLOP_FREQ.get(street, GTO_POSTFLOP_FREQ['flop'])
        bet_ratio = ctx.bet_ratio if ctx else 0.0
        cat_scales = self._compute_category_scales(action, street, prof, bet_ratio)

        for idx in range(1326):
            cat = categories[idx]
            if street == 'river' and cat in ('draw', 'weak_draw'):
                cat = 'air'
            gto_cat = gto_street.get(cat)
            if gto_cat is None:
                gto_cat = gto_street['air']
            gto_freq = gto_cat.get(action, 0.1)
            scale = cat_scales.get(cat, 1.0)
            adjusted = _clip(gto_freq * scale, 0.01, 0.99)
            conf = _confidence('af', prof.hands_seen)
            result[idx] = conf * adjusted + (1 - conf) * gto_freq

        if self.showdown_learner is not None and prof.name:
            learned = self.showdown_learner.get_learned_freq(
                prof.name, street, action
            )
            if learned is not None:
                n = self.showdown_learner.sample_count(prof.name, street, action)
                blend = n / (n + 50.0)
                for idx in range(1326):
                    cat = categories[idx]
                    if street == 'river' and cat in ('draw', 'weak_draw'):
                        cat = 'air'
                    learned_freq = learned.get(cat, 0.01)
                    result[idx] = ((1.0 - blend) * result[idx]
                                   + blend * _clip(learned_freq, 0.01, 0.99))

        if (action == 'raise' and ctx is not None and ctx.is_raise_over
                and street in ('turn', 'river')
                and prof.hands_seen >= MIN_HANDS_FOR_CLASSIFICATION
                and prof.af < 1.5):
            for idx in range(1326):
                cat = categories[idx]
                if street == 'river' and cat in ('draw', 'weak_draw'):
                    cat = 'air'
                if cat == 'nuts':
                    result[idx] *= 1.8
                elif cat == 'strong':
                    result[idx] *= 0.55
                elif cat == 'medium':
                    result[idx] *= 0.20
                else:
                    result[idx] *= 0.10
            np.clip(result, 0.01, 0.99, out=result)

        if hero_cards:
            result *= blocker_weights(hero_cards, board)

        np.maximum(result, 0.01, out=result)
        return result

    def _categorize_all(self, board: List[Card]) -> List[str]:
        """Categorize all 1326 combos on the given board.

        Per-board memoized: same street's many opp actions reuse the cache.
        """
        key = tuple(sorted(hcm.card_to_int(c) for c in board)) if board else ()
        if self._cat_cache_key == key and self._cat_cache is not None:
            return self._cat_cache

        categories = ['air'] * 1326
        # Build known board card set for quick blocking check
        board_ints = {hcm.card_to_int(c) for c in board}

        for idx in range(1326):
            c1, c2 = hcm.ALL_COMBOS[idx]
            # Skip combos that conflict with board (will be zeroed by tracker anyway)
            if c1 in board_ints or c2 in board_ints:
                continue
            categories[idx] = hcat.categorize(idx, board)
        self._cat_cache_key = key
        self._cat_cache = categories
        # Pre-build int-array forms for vectorization (str→int via _CAT_IDX)
        idx_arr = np.array([_CAT_IDX[c] for c in categories], dtype=np.int8)
        self._cat_idx_cache = idx_arr
        # River-merged form: draw/weak_draw → air
        merged = idx_arr.copy()
        mask = (merged == _CAT_IDX_DRAW) | (merged == _CAT_IDX_WEAK_DRAW)
        merged[mask] = _CAT_IDX_AIR
        self._cat_idx_river_cache = merged
        return categories

    def _cat_indices(self, board: List[Card], street: str) -> np.ndarray:
        """Return 1326-length int8 cat-id array (river merges draw→air)."""
        # Ensure cache is built
        self._categorize_all(board)
        if street == 'river':
            return self._cat_idx_river_cache
        return self._cat_idx_cache

    def _compute_category_scales(self, action: str, street: str,
                                 prof: PlayerProfile,
                                 bet_ratio: float = 0.0) -> Dict[str, float]:
        """Compute per-category scaling factors from opponent stats + bet sizing."""
        scales: Dict[str, float] = {
            'nuts': 1.0, 'strong': 1.0, 'medium': 1.0,
            'draw': 1.0, 'weak_draw': 1.0, 'air': 1.0,
        }

        if prof.hands_seen < MIN_HANDS_FOR_CLASSIFICATION:
            # Sizing is objective info — apply it even with few hands.
            # Cold-start defaults to mid-polarization (see
            # _polarization_index); interpolation returns a neutral
            # mid-way adjustment.
            if action == 'raise' and bet_ratio > 0 and street != 'preflop':
                bucket = _sizing_bucket(bet_ratio)
                adj = _sizing_adj_for(bucket, prof)
                for cat in scales:
                    scales[cat] *= adj.get(cat, 1.0)
            return scales

        if action == 'raise':
            # AF scaling: low AF → raise is very strong signal
            af_scale = _clip(prof.af / 2.0, 0.3, 3.0)

            # Street-level AFq (more precise)
            s_afq = prof.street_afq(street)
            gto_afq = GTO_AFQ_BASELINE.get(street, 0.40)
            if s_afq is not None:
                afq_scale = _clip(s_afq / gto_afq, 0.3, 3.0)
                af_scale = 0.3 * af_scale + 0.7 * afq_scale

            for cat in scales:
                scales[cat] = af_scale

            # ── 统计驱动的分类别调整（替代旧 PWI-flatten + bluffer heuristic）──
            # 每个 category 由直接相关的统计量独立驱动，不互相污染。
            #
            # air: 由 bluff_win_rate 驱动（诈唬倾向的直接度量）
            #   GTO 基线 bluff rate ≈ 25%；whale ≈ 5%、maniac ≈ 45%。
            #   样本不足 (<5) 时不调整，用 GTO 默认。
            if prof.bet_win_count >= 5:
                air_mult = _clip(prof.bluff_win_rate / 0.25, 0.2, 2.0)
                scales['air'] *= air_mult
                scales['weak_draw'] *= _clip(air_mult, 0.4, 1.5)

            # medium / strong: 由 VPIP-PFR gap 驱动（被动倾向的直接度量）
            #   gap 大 = 被动型：raise 只用"自认为好的牌"（含弱顶对），medium 偏高
            #   gap 小 = 主动型：接近 GTO，不调整
            gap = prof.vpip - prof.pfr
            if gap > 0.15:
                medium_mult = _clip(1.0 + gap * 2, 1.0, 2.5)
                strong_mult = _clip(1.0 + gap, 1.0, 1.5)
                scales['medium'] *= medium_mult
                scales['strong'] *= strong_mult
                scales['draw'] *= _clip(medium_mult * 0.8, 1.0, 2.0)
                scales['weak_draw'] *= _clip(medium_mult * 0.6, 1.0, 1.5)

            # Bet sizing adjustment (postflop only, first-bet only — see docstring).
            # Issue K: interpolate between MERGED (fish) and POLARIZED (reg)
            # tables by continuous polarization_index from AF/WTSD/VPIP.
            if bet_ratio > 0 and street != 'preflop':
                bucket = _sizing_bucket(bet_ratio)
                adj = _sizing_adj_for(bucket, prof)
                for cat in scales:
                    scales[cat] *= adj.get(cat, 1.0)

        elif action == 'call':
            # WTSD high → calls more with all categories
            wtsd_scale = _clip(prof.wtsd / 0.25, 0.5, 2.5)
            for cat in scales:
                scales[cat] = wtsd_scale

            # 2026-04-23 修复：GTO baseline `P(call|nuts)/P(call|air)` 约 17.5×
            # (0.35/0.02)，这个比值对 **高 wtsd + 高 (vpip-pfr) gap** 的指标
            # 组合严重偏离现实——这种指标画像的对手用 air 跟注 20-35%，真实
            # nuts:air 比约 2-3×（由 WTSD 和 fold_to_cbet 反推，与 GTO Wizard
            # 实证一致）。
            #
            # 原代码 wtsd_scale 是标量对所有桶同乘，永久保留 17.5×：每次 call
            # 更新把 air 权重近乎清零，3 街累积后 villain range 只剩 strong+，
            # hero 对此假极端 range 算 equity → 系统性低估 9-24pp → 过度 fold。
            # log 实证：94 个后街决策 avg equity_range 比 equity_mc 低 9pp（100%
            # 单向偏差），hero fold 率 87%、value bet 仅 6%。
            #
            # 判据用 (wtsd, gap) 两项指标直接驱动，不读 player_type 标签。
            # 双门槛：wtsd ≥ 0.30 **AND** gap > 0.20 才触发 flatten——要求经常
            # 摊牌弱牌（wtsd 高）**同时** 被动 flat 倾向（VPIP-PFR 差距大）。
            # 单项触发不够：高 wtsd 低 gap 的指标组合（打到 showdown 是因为
            # aggression，不是 air flat call）不走这条路。
            gap = prof.vpip - prof.pfr
            if prof.wtsd >= 0.30 and gap > 0.20:
                looseness = _clip(min(prof.wtsd / 0.25, gap / 0.20), 1.0, 2.0)
                scales['air'] *= looseness * 2.0
                scales['weak_draw'] *= looseness * 1.5
                scales['draw'] *= looseness * 1.2
                scales['medium'] *= _clip(1.0 + gap, 1.0, 1.8)
            # 2026-04-25 Fix 6.2: Trap-range protection for passive/sticky villain.
            # 指标判据（不依赖标签）：wtsd≥0.32 OR af≤1.0（≥20 手样本）OR
            # （未知对手的 vpip≥0.40 先验）。这类对手 call range 包含 trap-
            # monster（强牌不加注而 flat）；若只按 "call=weak signal" 降权，
            # 连续 call 会把强牌权重推到近 0（S3·手103 tracker 强桶 25%→1%）。
            # 修复：call 时给 nuts/strong 补一个 1.3-1.6× 乘子，维持 trap 概率。
            trap_prior = (
                (prof.wtsd >= 0.32)
                or (prof.hands_seen >= 20 and prof.af <= 1.0)
                or (prof.hands_seen < 20 and prof.vpip >= 0.40)
            )
            if trap_prior:
                # 插值：wtsd 越高（或 vpip 越高）trap 越可能，nuts 增幅越大
                trap_strength = _clip(
                    max(prof.wtsd / 0.40, prof.vpip / 0.60), 1.0, 1.8
                )
                scales['nuts'] *= trap_strength
                scales['strong'] *= (1.0 + (trap_strength - 1.0) * 0.7)

        elif action == 'fold':
            if street == 'flop' and prof.fold_to_cbet_opps >= 60:
                # Direct fold_to_cbet application
                ftc = prof.fold_to_cbet
                # Strong hands don't fold regardless; weak hands fold more
                scales['nuts'] = 0.05
                scales['strong'] = 0.1
                scales['medium'] = _clip(ftc / 0.45, 0.5, 2.0)
                scales['draw'] = _clip(ftc * 0.7 / 0.45, 0.3, 1.5)
                scales['weak_draw'] = _clip(ftc * 1.2 / 0.45, 0.5, 2.5)
                scales['air'] = _clip(ftc * 1.4 / 0.45, 0.7, 3.0)
            elif street == 'river' and prof.river_facing_bet_opps >= 30:
                river_fold = prof.river_fold_rate
                rf_scale = _clip(river_fold / 0.35, 0.5, 2.0)
                scales['nuts'] = 0.05
                scales['strong'] = 0.2
                for cat in ('medium', 'draw', 'weak_draw', 'air'):
                    scales[cat] = rf_scale

        # check: no scaling needed (residual)

        return scales
