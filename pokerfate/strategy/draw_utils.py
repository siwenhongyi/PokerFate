"""Detect flush / straight draws for implied-odds vs made-hand call tuning."""

from __future__ import annotations

from collections import Counter
from typing import List

from pokerfate.core.card import Card
from pokerfate.core.hand_evaluator import HandEvaluator, HandRank


def _straight_rank_windows() -> List[frozenset]:
    """All 5-card straight rank sets (Ace high and low)."""
    out: List[frozenset] = []
    # Wheel A-2-3-4-5
    out.append(frozenset([14, 2, 3, 4, 5]))
    # 2-6 through T-A
    for low in range(2, 11):
        out.append(frozenset(range(low, low + 5)))
    return out


_STRAIGHT_WINDOWS = _straight_rank_windows()


def is_drawing_heavy(hole_cards: List[Card], board: List[Card]) -> bool:
    """True if we have meaningful draw equity (flush draw or straight draw), not pure made-only.

    Used to keep implied-odds bonus for draws while tightening calls with one-pair type hands
    facing large bets.
    """
    if len(hole_cards) < 2 or len(board) < 3:
        return False
    cards = hole_cards + board
    if len(cards) < 5:
        return False

    score = HandEvaluator.evaluate(cards)
    hr = HandRank(score[0])

    if _has_flush_draw(cards, hr):
        return True
    if _has_straight_draw(cards, hr):
        return True
    return False


def _has_flush_draw(cards: List[Card], hr: HandRank) -> bool:
    if hr >= HandRank.FLUSH:
        return False
    suit_cnt = Counter(c.suit for c in cards)
    return any(v == 4 for v in suit_cnt.values())


def _has_straight_draw(cards: List[Card], hr: HandRank) -> bool:
    if hr >= HandRank.STRAIGHT:
        return False
    rs: set[int] = set()
    for c in cards:
        rs.add(c.rank.value)
    if 14 in rs:
        rs.add(1)
    for window in _STRAIGHT_WINDOWS:
        if len(rs & window) >= 4:
            return True
    return False
