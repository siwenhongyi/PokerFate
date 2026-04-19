"""Bayesian 1326-dim range tracker.

Maintains a probability vector w[1326] for each opponent.  Every observed
action multiplies by the action likelihood and re-normalizes.

References:
  - Bayes' Bluff (Southey et al., UAI 2005) — Bayesian opponent modeling
  - Libratus (Brown & Sandholm, 2017) — reach probability as range prior
  - Johanson et al. (AAMAS 2009) — GTO↔observed confidence interpolation
"""

from __future__ import annotations

from typing import Dict, List, Optional, Set

import numpy as np

from pokerfate.core.card import Card
from pokerfate.strategy.range_v2 import hand_combo_map as hcm
from pokerfate.strategy.range_v2.action_model import (
    ActionContext,
    ActionModel,
    GTO_PFR,
    GTO_VPIP,
    PlayerProfile,
)


class BayesianRangeTracker:
    """Per-opponent 1326-dim Bayesian range tracker."""

    def __init__(self, action_model: ActionModel):
        self.action_model = action_model
        self._weights: Dict[int, np.ndarray] = {}  # player_id → w[1326]
        self._known_cards: Set[int] = set()         # my hole cards (set once per hand)

    def set_known_cards(self, cards: List[Card]) -> None:
        """Call once per hand with bot's hole cards."""
        self._known_cards = {hcm.card_to_int(c) for c in cards}

    def reset_hand(self, player_id: int, position: str,
                   profile: PlayerProfile) -> None:
        """Initialize prior distribution for a new hand.

        Prior construction (Johanson 2009 Data-Biased method):
          - Hands in PFR range → weight 1.0
          - Hands in VPIP range but not PFR → weight 0.6
          - Hands outside VPIP → weight 0.03 (never zero — allows deviation)
          - Card removal: combos containing known cards → 0
        """
        w = np.ones(1326, dtype=np.float64)

        # Card removal: my hole cards
        block = hcm.blocked_by(self._known_cards)
        w[block] = 0.0

        # Position prior
        vpip = profile.vpip if profile.hands_seen >= 20 else GTO_VPIP.get(position, 0.27)
        pfr = profile.pfr if profile.hands_seen >= 20 else GTO_PFR.get(position, 0.20)

        raise_thresh = 1.0 - pfr
        call_floor = 1.0 - vpip

        strengths = hcm.STRENGTH_PCT
        for idx in range(1326):
            if w[idx] == 0.0:
                continue
            s = strengths[idx]
            if s >= raise_thresh:
                w[idx] = 1.0
            elif s >= call_floor:
                w[idx] = 0.6
            else:
                w[idx] = 0.03

        total = w.sum()
        if total > 0:
            w /= total

        self._weights[player_id] = w

    def observe_action(self, player_id: int, action: str, street: str,
                       context: ActionContext, profile: PlayerProfile,
                       board: List[Card]) -> None:
        """Tempered Bayesian update with entropy-adaptive damping.

        Standard Bayes: w *= likelihood
        Tempered:       w *= likelihood^α   (α < 1 slows convergence)

        α is adaptive — when the posterior is already concentrated (low
        entropy), α decreases to resist further collapse.  This prevents
        the distribution from collapsing to a handful of combos after
        3-4 sequential updates, which is the core over-convergence problem
        in sequential Bayesian range tracking.

        References:
          - Grünwald 2012, SafeBayes — power likelihood / likelihood tempering
          - Posterior regularization — floor mixing to prevent zero probabilities
        """
        if player_id not in self._weights:
            self.reset_hand(player_id, context.position or 'CO', profile)

        w = self._weights[player_id]

        # Card removal: board cards
        if board:
            board_ints = {hcm.card_to_int(c) for c in board}
            all_known = self._known_cards | board_ints
            block = hcm.blocked_by(all_known)
            w[block] = 0.0

        # Compute likelihoods for all 1326 combos
        likelihoods = self.action_model.batch_likelihood(
            action, street, context, profile, board
        )

        # ── Adaptive likelihood tempering ──
        # Compute current entropy to gauge how concentrated the posterior is
        active = w > 1e-10
        n_active = int(active.sum())
        if n_active > 1:
            w_pos = w[active]
            entropy = float(-np.sum(w_pos * np.log2(w_pos)))
            max_entropy = np.log2(n_active)
            # confidence ∈ [0, 1]: 0 = uniform (no info), 1 = fully concentrated
            confidence = 1.0 - entropy / max_entropy if max_entropy > 0 else 0.0
        else:
            confidence = 1.0

        # α ∈ [0.3, 0.85]: high confidence → low α (resist further collapse)
        alpha = max(0.3, 0.85 - 0.4 * confidence)

        # Tempered Bayesian update
        w *= likelihoods ** alpha

        # Normalize
        total = w.sum()
        if total > 1e-15:
            w /= total
        else:
            w = np.ones(1326, dtype=np.float64)
            all_known = set(self._known_cards)
            if board:
                all_known |= {hcm.card_to_int(c) for c in board}
            w[hcm.blocked_by(all_known)] = 0.0
            s = w.sum()
            if s > 0:
                w /= s
            else:
                w[:] = 1.0 / 1326

        # ── Probability floor: no combo drops below floor ──
        # Ensures every non-blocked combo retains a minimum probability,
        # so the range never fully excludes any feasible hand.
        active = w > 0
        n_active = int(active.sum())
        if n_active > 0:
            floor = 1e-4 / n_active
            below = active & (w < floor)
            if below.any():
                w[below] = floor
                w /= w.sum()

        self._weights[player_id] = w

    def get_distribution(self, player_id: int) -> np.ndarray:
        """Return current 1326-dim probability distribution."""
        return self._weights.get(player_id, np.ones(1326) / 1326).copy()

    def get_effective_range_pct(self, player_id: int) -> float:
        """Fraction of combos with non-negligible probability."""
        w = self._weights.get(player_id)
        if w is None:
            return 1.0
        threshold = 1.0 / 1326 * 0.1
        return float((w > threshold).sum()) / 1326

    def get_entropy(self, player_id: int) -> float:
        """Shannon entropy of the distribution (lower = more certain)."""
        w = self._weights.get(player_id)
        if w is None:
            return np.log2(1326)
        w_pos = w[w > 0]
        return float(-np.sum(w_pos * np.log2(w_pos)))

    def get_bucket_distribution(self, player_id: int, board: List[Card]) -> Dict[str, float]:
        """Return weight-aggregated bucket distribution {category: pct}.

        Sums w[i] per HandCategorizer bucket, normalized to percentages.
        Only includes buckets > 0.
        """
        from pokerfate.strategy.range_v2 import hand_categorizer as hcat

        w = self._weights.get(player_id)
        if w is None:
            return {}

        board_ints = {hcm.card_to_int(c) for c in board} if board else set()
        buckets: Dict[str, float] = {}

        for idx in range(1326):
            if w[idx] < 1e-8:
                continue
            c1, c2 = hcm.ALL_COMBOS[idx]
            if c1 in board_ints or c2 in board_ints:
                continue
            if board and len(board) >= 3:
                cat = hcat.categorize(idx, board)
            else:
                cat = hcat.categorize(idx, [])
            buckets[cat] = buckets.get(cat, 0.0) + w[idx]

        total = sum(buckets.values())
        if total > 0:
            buckets = {k: v / total for k, v in buckets.items()}
        return buckets

    def get_range_summary(self, player_id: int) -> dict:
        """Return summary dict for logging/debugging."""
        w = self._weights.get(player_id)
        if w is None:
            return {'effective_range_pct': 1.0, 'active_combos': 1326,
                    'entropy': np.log2(1326), 'max_weight': 1.0 / 1326}
        nonzero = int((w > 1e-6).sum())
        return {
            'effective_range_pct': nonzero / 1326,
            'active_combos': nonzero,
            'entropy': self.get_entropy(player_id),
            'max_weight': float(w.max()),
        }
