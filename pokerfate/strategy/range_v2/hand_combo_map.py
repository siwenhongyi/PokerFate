"""Pre-computed 1326 hole-card combo index.

All 1326 unordered 2-card combinations from a 52-card deck are indexed once
at module load time.  Runtime lookups are O(1) dict/array access.

Reference: treys / phevaluator combo encoding.
"""

from __future__ import annotations

from typing import Dict, List, Set, Tuple

import numpy as np

from pokerfate.core.card import Card
from pokerfate.strategy.range_v2.preflop_equity_table import PREFLOP_EQUITY


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

    Backed by ``PREFLOP_EQUITY`` (169-class MC table) converted to
    a tie-aware percentile rank over the full 1326-combo space.

    Replaces the old linear formula `score = hi*13 + lo + 3*suited`
    which had two bugs: AKs and AKo clipped to the same value at the
    top of the range, and `score / 180.0` was a fake "percentile"
    that had no relation to hand equity.

    Exact percentile values are cached in `STRENGTH_PCT` at module
    load time; this function exists for API compatibility — callers
    that already have a combo index should use STRENGTH_PCT directly.
    """
    cls = _hand_category(c1_int, c2_int)
    return _CLASS_PCT[cls]


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
# Class → percentile lookup (derived from PREFLOP_EQUITY table)
# ---------------------------------------------------------------------------

# Populated at init: {'AA': 0.998, 'KK': 0.993, ..., '42o': 0.004}.
# Used by `_preflop_strength` for API back-compat.
_CLASS_PCT: Dict[str, float] = {}


def _class_size(cls: str) -> int:
    """Number of distinct combos in a 169 hand class.

    Pockets: 6 (C(4,2) suit pairs).
    Suited:  4 (one combo per suit).
    Offsuit: 12 (4×3 suit pairs).
    """
    if len(cls) == 2:
        return 6
    return 4 if cls.endswith('s') else 12


def _build_class_percentiles(equity_table: Dict[str, float]) -> Dict[str, float]:
    """Convert a class→equity map to class→percentile (tie-aware).

    Tie handling: all combos within a class share one equity. We place
    the class's combos at consecutive ranks (sorted by equity) and
    assign every combo in that class the AVERAGE of those ranks — the
    standard statistical rank-with-ties convention. Result: within-class
    combos all get the same percentile, which is what `reset_hand`'s
    bucketing logic expects (all AA combos either in or out of PFR).
    """
    # Sort classes by equity ascending (worst first).
    ordered = sorted(equity_table.items(), key=lambda kv: kv[1])

    total = sum(_class_size(c) for c, _ in ordered)
    assert total == 1326, f"class sizes sum to {total}, expected 1326"

    cum_weaker = 0   # count of combos strictly weaker than current class
    pct: Dict[str, float] = {}
    for cls, _eq in ordered:
        n = _class_size(cls)
        # This class occupies ranks [cum_weaker, cum_weaker+n-1] (0-indexed);
        # average = cum_weaker + (n-1)/2. Divide by (total-1) so the top
        # class ends at 1.0 exactly (when it's a pair — needs the last
        # combo at rank 1325, which for AA = pos 1320..1325, avg 1322.5,
        # pct 1322.5/1325 = 0.9981).
        avg_rank = cum_weaker + (n - 1) / 2.0
        pct[cls] = avg_rank / (total - 1)
        cum_weaker += n
    return pct


# ---------------------------------------------------------------------------
# Module init: populate all tables once
# ---------------------------------------------------------------------------

def _init() -> None:
    global ALL_COMBOS, COMBO_TO_IDX, CARD_TO_COMBOS, STRENGTH_PCT
    global CATEGORY_TO_INDICES, _CLASS_PCT

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

    # Build the class→percentile map once from the static equity table.
    _CLASS_PCT = _build_class_percentiles(PREFLOP_EQUITY)

    strengths = np.empty(1326, dtype=np.float64)
    cat_map: Dict[str, List[int]] = {}
    for idx, (c1, c2) in enumerate(combos):
        cat = _hand_category(c1, c2)
        strengths[idx] = _CLASS_PCT[cat]
        cat_map.setdefault(cat, []).append(idx)
    STRENGTH_PCT = strengths
    CATEGORY_TO_INDICES = cat_map


_init()
