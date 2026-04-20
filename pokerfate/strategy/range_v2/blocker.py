"""Hero blocker weighting for opponent likelihood.

Card removal (hero's cards can't be in opponent's combo) is already
handled by hand_combo_map.blocked_by. This module adds the *strategic*
blocker layer: when hero holds suits/ranks that block a relevant subset
of opponent combos, the action likelihood for those combos is attenuated.

Currently only flush blockers are modelled. Straight blockers are
deferred (lower frequency, higher implementation complexity).

Reference: GTO Wizard "Understanding Blockers" — flush blocker reduction
on a 3+ flush board is empirically 15-25% per hero card; halved on a
2-flush (backdoor) board.
"""
from __future__ import annotations

from collections import Counter
from typing import List

import numpy as np

from pokerfate.core.card import Card
from pokerfate.strategy.range_v2.hand_combo_map import CARD_TO_COMBOS


_FLUSH_PENALTY_3PLUS = 0.20
_FLUSH_PENALTY_2 = 0.10
_MAX_PENALTY = 0.50


def _build_suit_masks() -> List[np.ndarray]:
    masks = [np.zeros(1326, dtype=bool) for _ in range(4)]
    for card_int, combo_indices in CARD_TO_COMBOS.items():
        suit = card_int % 4
        for idx in combo_indices:
            masks[suit][idx] = True
    return masks


SUIT_MASKS: List[np.ndarray] = _build_suit_masks()


def blocker_weights(
    hero_cards: List[Card],
    board: List[Card],
) -> np.ndarray:
    """Return [1326] multiplicative weights in [1 - _MAX_PENALTY, 1.0].

    weight[i] < 1.0 means combo i's action likelihood should be
    attenuated because hero blocks a relevant portion of the class
    that combo belongs to.
    """
    weights = np.ones(1326, dtype=np.float64)

    if not board or len(board) < 3 or not hero_cards:
        return weights

    board_suits = Counter(int(c.suit) for c in board)
    hero_suits = Counter(int(c.suit) for c in hero_cards)

    for suit, board_count in board_suits.items():
        if board_count < 2:
            continue
        hero_count = hero_suits.get(suit, 0)
        if hero_count == 0:
            continue
        per_card = _FLUSH_PENALTY_3PLUS if board_count >= 3 else _FLUSH_PENALTY_2
        penalty = min(_MAX_PENALTY, per_card * hero_count)
        weights *= np.where(SUIT_MASKS[suit], 1.0 - penalty, 1.0)

    return weights
