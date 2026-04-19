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
from pokerfate.strategy.range_v2 import hand_combo_map as hcm
from pokerfate.strategy.range_v2 import hand_categorizer as hcat

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
    new_board_cards: List[int] = None  # card_ints of newly dealt board cards


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
    player_type: str = 'unknown'
    pwi: float = 0.0
    # Samples for street-level AFq reliability
    flop_action_count: int = 0  # flop_bet + flop_passive
    turn_action_count: int = 0
    river_action_count: int = 0
    # Server priors
    server_af_prior: float = 0.0
    server_cbet_prior: float = 0.0
    server_3bet_prior: float = 0.0
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

    def batch_likelihood(
        self,
        action: str,
        street: str,
        context: ActionContext,
        profile: PlayerProfile,
        board: List[Card],
    ) -> np.ndarray:
        """Return likelihood[1326] for every combo given the observed action.

        This is the hot path — vectorized where possible.
        """
        if street == 'preflop':
            return self._preflop_batch(action, context, profile)
        else:
            return self._postflop_batch(action, street, context, profile, board)

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
        if prof.hands_seen < 20 and prof.server_priors_available:
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
                        board: List[Card]) -> np.ndarray:
        """Postflop likelihood for all 1326 combos."""
        result = np.empty(1326, dtype=np.float64)

        # Pre-categorize all combos on this board
        # This is the expensive part — but HandCategorizer uses evaluation, not MC
        categories = self._categorize_all(board)

        # Get GTO frequencies for this street
        gto_street = GTO_POSTFLOP_FREQ.get(street, GTO_POSTFLOP_FREQ['flop'])

        # Compute per-category scaling factors based on opponent profile
        cat_scales = self._compute_category_scales(action, street, prof)

        # Compute per-category GTO baseline
        for idx in range(1326):
            cat = categories[idx]

            # River: draws become air
            if street == 'river' and cat in ('draw', 'weak_draw'):
                cat = 'air'

            gto_cat = gto_street.get(cat)
            if gto_cat is None:
                gto_cat = gto_street['air']

            gto_freq = gto_cat.get(action, 0.1)

            # Apply opponent-specific scaling
            scale = cat_scales.get(cat, 1.0)
            adjusted = _clip(gto_freq * scale, 0.01, 0.99)

            # Confidence interpolation
            conf = _confidence('af', prof.hands_seen)
            result[idx] = conf * adjusted + (1 - conf) * gto_freq

        # Showdown learner override (if enough data)
        if self.showdown_learner is not None and prof.name:
            learned = self.showdown_learner.get_learned_freq(
                prof.name, street, action
            )
            if learned is not None:
                for idx in range(1326):
                    cat = categories[idx]
                    if street == 'river' and cat in ('draw', 'weak_draw'):
                        cat = 'air'
                    learned_freq = learned.get(cat, 0.01)
                    # Mix 50/50 with current estimate to avoid overfitting
                    result[idx] = 0.5 * result[idx] + 0.5 * _clip(learned_freq, 0.01, 0.99)

        # Floor
        np.maximum(result, 0.01, out=result)

        return result

    def _categorize_all(self, board: List[Card]) -> List[str]:
        """Categorize all 1326 combos on the given board.

        Returns list of category strings indexed by combo_idx.
        """
        categories = ['air'] * 1326
        # Build known board card set for quick blocking check
        board_ints = {hcm.card_to_int(c) for c in board}

        for idx in range(1326):
            c1, c2 = hcm.ALL_COMBOS[idx]
            # Skip combos that conflict with board (will be zeroed by tracker anyway)
            if c1 in board_ints or c2 in board_ints:
                continue
            categories[idx] = hcat.categorize(idx, board)
        return categories

    def _compute_category_scales(self, action: str, street: str,
                                 prof: PlayerProfile) -> Dict[str, float]:
        """Compute per-category scaling factors from opponent stats."""
        scales: Dict[str, float] = {
            'nuts': 1.0, 'strong': 1.0, 'medium': 1.0,
            'draw': 1.0, 'weak_draw': 1.0, 'air': 1.0,
        }

        if prof.hands_seen < 20:
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

            # ── PWI 拉平：弱玩家 raise 的手牌构成更平坦 ──
            # GTO 玩家 raise range 极化（nuts 高频 + air 低频，比值 ~7:1）
            # 鲸鱼/鱼 raise range 平坦（什么牌都可能 raise，比值 ~2:1）
            # 用 PWI 控制拉平力度：PWI=0 不拉平，PWI=+100 接近均匀
            if prof.pwi > 10:
                # flatten_t ∈ [0, 1]：0=纯 GTO 形态，1=完全均匀
                flatten_t = _clip(prof.pwi / 120.0, 0.0, 0.75)
                # 对中等/弱 category 提升 raise 似然（拉向 nuts 水平）
                # nuts 保持不变；其余向 nuts 靠拢
                nuts_scale = scales['nuts']
                for cat in ('strong', 'medium', 'draw', 'weak_draw', 'air'):
                    # 插值：scale → scale + flatten_t * (nuts_scale - scale)
                    scales[cat] = scales[cat] + flatten_t * (nuts_scale - scales[cat])

            # Known bluffer → air/weak_draw raise frequency higher
            if prof.bluff_win_rate > 0.40 and prof.bet_win_count >= 5:
                scales['air'] *= 1.5
                scales['weak_draw'] *= 1.3

        elif action == 'call':
            # WTSD high → calls more with all categories
            wtsd_scale = _clip(prof.wtsd / 0.25, 0.5, 2.5)
            for cat in scales:
                scales[cat] = wtsd_scale

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
            elif street == 'river' and prof.river_action_count >= 30:
                river_fold = prof.river_fold_rate
                rf_scale = _clip(river_fold / 0.35, 0.5, 2.0)
                scales['nuts'] = 0.05
                scales['strong'] = 0.2
                for cat in ('medium', 'draw', 'weak_draw', 'air'):
                    scales[cat] = rf_scale

        # check: no scaling needed (residual)

        return scales
