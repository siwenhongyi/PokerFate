"""Pre-computed 1326 hole-card combo index.

All 1326 unordered 2-card combinations from a 52-card deck are indexed once
at module load time.  Runtime lookups are O(1) dict/array access.

Reference: treys / phevaluator combo encoding.
"""

from __future__ import annotations

from typing import Dict, List, Set, Tuple

import numpy as np

from pokerfate.core.card import Card


# ---------------------------------------------------------------------------
# Card integer encoding: (rank - 2) * 4 + suit = 0..51
# rank 2→0, 3→4, ..., A(14)→48;  suit 0-3
# ---------------------------------------------------------------------------

def card_to_int(c: Card) -> int:
    return (int(c.rank) - 2) * 4 + int(c.suit)


def int_to_card(i: int) -> Card:
    return Card(i // 4 + 2, i % 4)


# ---------------------------------------------------------------------------
# Pre-computed tables (populated at module load)
# ---------------------------------------------------------------------------

# Ordered list of all 1326 combos as (int, int) with c1 < c2
ALL_COMBOS: List[Tuple[int, int]] = []

# (c1, c2) → combo index  (canonical: min first)
COMBO_TO_IDX: Dict[Tuple[int, int], int] = {}

# card_int → list of combo indices containing that card
CARD_TO_COMBOS: Dict[int, List[int]] = {}

# Pre-computed preflop hand-strength percentile for each combo (0-1, 1=AA)
STRENGTH_PCT: np.ndarray  # shape (1326,)

# Category string ("AKs", "72o", "TT") → list of combo indices
CATEGORY_TO_INDICES: Dict[str, List[int]] = {}

# Rank chars for display
_RANK_CHARS = {2: '2', 3: '3', 4: '4', 5: '5', 6: '6', 7: '7', 8: '8',
               9: '9', 10: 'T', 11: 'J', 12: 'Q', 13: 'K', 14: 'A'}


def _hand_category(c1_int: int, c2_int: int) -> str:
    """Return category string like 'AKs', 'AKo', 'AA'."""
    r1, s1 = c1_int // 4 + 2, c1_int % 4
    r2, s2 = c2_int // 4 + 2, c2_int % 4
    hi, lo = max(r1, r2), min(r1, r2)
    hi_c = _RANK_CHARS[hi]
    lo_c = _RANK_CHARS[lo]
    if hi == lo:
        return f"{hi_c}{lo_c}"
    suffix = 's' if s1 == s2 else 'o'
    return f"{hi_c}{lo_c}{suffix}"


def _preflop_strength(c1_int: int, c2_int: int) -> float:
    """Preflop hand strength percentile (0-1).  1.0 ≈ AA.

    Same formula as the original ``_hand_strength_pct`` so that strength
    ordering is consistent across the codebase.
    """
    r1, s1 = c1_int // 4 + 2, c1_int % 4
    r2, s2 = c2_int // 4 + 2, c2_int % 4
    suited = s1 == s2
    hi, lo = max(r1, r2), min(r1, r2)
    if hi == lo:
        score = 156 + hi * 2
    else:
        score = hi * 13 + lo + (3 if suited else 0)
    return min(1.0, score / 180.0)


def cards_of(combo_idx: int) -> Tuple[Card, Card]:
    """Return the two Card objects for a given combo index."""
    c1, c2 = ALL_COMBOS[combo_idx]
    return int_to_card(c1), int_to_card(c2)


def cards_of_int(combo_idx: int) -> Tuple[int, int]:
    """Return the two card ints for a given combo index."""
    return ALL_COMBOS[combo_idx]


def blocked_by(known_cards: Set[int]) -> np.ndarray:
    """Return bool mask (1326,): True where combo conflicts with known cards."""
    mask = np.zeros(1326, dtype=bool)
    for card_int in known_cards:
        for idx in CARD_TO_COMBOS.get(card_int, []):
            mask[idx] = True
    return mask


# ---------------------------------------------------------------------------
# Module init: populate all tables once
# ---------------------------------------------------------------------------

def _init() -> None:
    global ALL_COMBOS, COMBO_TO_IDX, CARD_TO_COMBOS, STRENGTH_PCT, CATEGORY_TO_INDICES

    combos: List[Tuple[int, int]] = []
    for i in range(52):
        for j in range(i + 1, 52):
            combos.append((i, j))
    ALL_COMBOS = combos

    COMBO_TO_IDX = {c: idx for idx, c in enumerate(combos)}

    card_map: Dict[int, List[int]] = {i: [] for i in range(52)}
    for idx, (c1, c2) in enumerate(combos):
        card_map[c1].append(idx)
        card_map[c2].append(idx)
    CARD_TO_COMBOS = card_map

    strengths = np.empty(1326, dtype=np.float64)
    cat_map: Dict[str, List[int]] = {}
    for idx, (c1, c2) in enumerate(combos):
        strengths[idx] = _preflop_strength(c1, c2)
        cat = _hand_category(c1, c2)
        cat_map.setdefault(cat, []).append(idx)
    STRENGTH_PCT = strengths
    CATEGORY_TO_INDICES = cat_map


_init()
