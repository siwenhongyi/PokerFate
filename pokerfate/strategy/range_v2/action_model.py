"""Action likelihood model: P(action | hand_i, context, player_profile).

The core of Range V2.  For each of 1326 combos, returns the probability that the opponent
would take the observed action holding that combo.  Both halves are models fitted to the hands
we get to know (``fitted_likelihood.py``, ``scripts/fit_likelihood_model.py``):

Preflop: per preflop strength bin, with position, raise size, what the player faced, what he
did earlier in the hand and what kind of player he is as inputs.

Postflop: per strength bucket on the board, with bet size, players in the pot, position,
player type and the player's earlier actions in the hand as inputs.

Nothing here is written by hand any more; without a model file actions do not move ranges.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

import numpy as np

from pokerfate.core.card import Card
from pokerfate.strategy.range_v2 import hand_combo_map as hcm
from pokerfate.strategy.range_v2 import hand_categorizer as hcat
from pokerfate.strategy.range_v2.empirical_model import action_label, population_rate
from pokerfate.strategy.range_v2.fitted_likelihood import (
    bucket_likelihood, preflop_bin_index, preflop_label, preflop_likelihood,
)

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
    # Whether the acting opponent is in position among currently active players.
    is_ip: bool = False
    # Normalized preflop action label for calibration features only.
    preflop_action_type: str = ""
    # Table big blind, used only for bb-specific empirical priors.
    big_blind: float = 0.0
    # Set by the range tracker for every postflop action: what the fitted likelihood may
    # depend on (fitted_likelihood.likelihood_features).
    likelihood_features: Optional[Dict[str, float]] = None
    # ActionNotifyBRC.pre_action_result of this action: 0 nothing selected, 1 reset, 2 the
    # action was pre-selected (pokerfate/strategy/pre_action.py).
    pre_action: int = 0


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
    flop_seen_count: int = 0
    showdown_count: int = 0
    showdown_win_count: int = 0
    vpip: float = population_rate('vpip', 0.35)
    pfr: float = population_rate('pfr', 0.20)
    af: float = 2.0
    three_bet_pct: float = population_rate('three_bet', 0.06)
    fold_to_3bet: float = population_rate('fold_to_3bet', 0.55)
    fold_to_cbet: float = population_rate('fold_to_cbet', 0.45)
    fold_to_cbet_opps: int = 0
    wtsd: float = population_rate('wtsd', 0.25)
    wmsd: float = population_rate('wmsd', 0.50)
    flop_afq: float = population_rate('flop_afq', 0.45)
    turn_afq: float = population_rate('turn_afq', 0.40)
    river_afq: float = population_rate('river_afq', 0.35)
    river_fold_rate: float = population_rate('river_fold_rate', 0.35)
    river_bet_freq: float = population_rate('river_bet_frequency', 0.35)
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


# 向量化用的 category 顺序与索引映射。改这两行的顺序会破坏向量化代码 ——
# 后续任何 cat_per_idx[CAT_IDX[X]] 假定固定顺序。
_CAT_ORDER = ('nuts', 'strong', 'medium', 'draw', 'weak_draw', 'air')
_CAT_IDX = {c: i for i, c in enumerate(_CAT_ORDER)}
_CAT_IDX_DRAW = _CAT_IDX['draw']
_CAT_IDX_WEAK_DRAW = _CAT_IDX['weak_draw']
_CAT_IDX_AIR = _CAT_IDX['air']


# ---------------------------------------------------------------------------
# ActionModel
# ---------------------------------------------------------------------------

class ActionModel:
    """Compute P(action | combo, context, profile) for all 1326 combos.

    Used by BayesianRangeTracker to perform Bayesian updates.
    """

    def __init__(self):
        pass
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
        """Preflop likelihood for all 1326 combos: the fitted model, by preflop strength bin.

        Uninformative (all ones) for a fold and when there is no model file.
        """
        model = preflop_likelihood(
            preflop_label(ctx.preflop_action_type if ctx is not None else '', action),
            getattr(ctx, 'likelihood_features', None))
        if model is None:
            return np.ones(1326, dtype=np.float64)
        return model[preflop_bin_index()]

    # ------------------------------------------------------------------
    # Postflop
    # ------------------------------------------------------------------

    def _postflop_batch(self, action: str, street: str,
                        ctx: ActionContext, prof: PlayerProfile,
                        board: List[Card],
                        hero_cards: Optional[List[Card]] = None) -> np.ndarray:
        """Postflop likelihood for all 1326 combos: the fitted model, by strength bucket.

        Uninformative (all ones) for an action the model does not cover — a fold, whose range
        nobody reads again — and when there is no model file.
        """
        cat_idx = self._cat_indices(board, street)  # int8[1326], river-merged
        model = bucket_likelihood(
            street, action_label(action, bool(ctx is not None and ctx.is_raise_over)),
            getattr(ctx, 'likelihood_features', None))
        if model is None:
            return np.ones(len(cat_idx), dtype=np.float64)
        return model[cat_idx]

    def _categorize_all(self, board: List[Card]) -> List[str]:
        """Categorize all 1326 combos on the given board.

        Per-board memoized: same street's many opp actions reuse the cache.
        """
        key = tuple(sorted(hcm.card_to_int(c) for c in board)) if board else ()
        if self._cat_cache_key == key and self._cat_cache is not None:
            return self._cat_cache

        # Shared with the range tracker through hcat.categorize_all (board-
        # blocked combos come back as 'air', exactly as the old loop left them).
        categories = hcat.categorize_all(list(board))
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
