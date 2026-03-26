"""7-card poker hand evaluator.

Returns a comparable tuple: higher is better.
Format: (HandRank, *tiebreakers)
"""

from __future__ import annotations
from enum import IntEnum
from itertools import combinations
from typing import List, Tuple
from collections import Counter

from pokerfate.core.card import Card, Rank


class HandRank(IntEnum):
    HIGH_CARD = 0
    ONE_PAIR = 1
    TWO_PAIR = 2
    THREE_OF_A_KIND = 3
    STRAIGHT = 4
    FLUSH = 5
    FULL_HOUSE = 6
    FOUR_OF_A_KIND = 7
    STRAIGHT_FLUSH = 8
    ROYAL_FLUSH = 9

    def __str__(self) -> str:
        names = {
            0: 'High Card', 1: 'One Pair', 2: 'Two Pair',
            3: 'Three of a Kind', 4: 'Straight', 5: 'Flush',
            6: 'Full House', 7: 'Four of a Kind',
            8: 'Straight Flush', 9: 'Royal Flush',
        }
        return names[self.value]


HandScore = Tuple  # (HandRank, int, ...)


def _ranks_sorted(cards: List[Card]) -> List[int]:
    return sorted((c.rank.value for c in cards), reverse=True)


def _is_flush(cards: List[Card]) -> bool:
    return len({c.suit for c in cards}) == 1


def _straight_high(ranks: List[int]) -> int:
    """Return high card of straight, or 0 if not a straight. ranks must be sorted desc."""
    unique = sorted(set(ranks), reverse=True)
    # Normal straight
    for i in range(len(unique) - 4):
        window = unique[i:i + 5]
        if window[0] - window[4] == 4 and len(window) == 5:
            return window[0]
    # Wheel: A-2-3-4-5
    if set([14, 2, 3, 4, 5]).issubset(set(unique)):
        return 5
    return 0


def _evaluate_5(cards: List[Card]) -> HandScore:
    """Evaluate exactly 5 cards and return a comparable score tuple."""
    assert len(cards) == 5
    ranks = _ranks_sorted(cards)
    flush = _is_flush(cards)
    straight_high = _straight_high(ranks)

    if flush and straight_high:
        if straight_high == 14:
            return (HandRank.ROYAL_FLUSH, 14)
        return (HandRank.STRAIGHT_FLUSH, straight_high)

    cnt = Counter(ranks)
    freq = sorted(cnt.items(), key=lambda x: (x[1], x[0]), reverse=True)
    groups = [r for r, _ in freq]
    counts = [c for _, c in freq]

    if counts[0] == 4:
        return (HandRank.FOUR_OF_A_KIND, groups[0], groups[1])

    if counts[0] == 3 and counts[1] == 2:
        return (HandRank.FULL_HOUSE, groups[0], groups[1])

    if flush:
        return (HandRank.FLUSH, *ranks)

    if straight_high:
        return (HandRank.STRAIGHT, straight_high)

    if counts[0] == 3:
        kickers = [r for r, c in cnt.items() if c == 1]
        kickers.sort(reverse=True)
        return (HandRank.THREE_OF_A_KIND, groups[0], *kickers)

    if counts[0] == 2 and counts[1] == 2:
        pairs = sorted([groups[0], groups[1]], reverse=True)
        kicker = [r for r, c in cnt.items() if c == 1][0]
        return (HandRank.TWO_PAIR, pairs[0], pairs[1], kicker)

    if counts[0] == 2:
        kickers = [r for r, c in cnt.items() if c == 1]
        kickers.sort(reverse=True)
        return (HandRank.ONE_PAIR, groups[0], *kickers)

    return (HandRank.HIGH_CARD, *ranks)


class HandEvaluator:
    @staticmethod
    def evaluate(cards: List[Card]) -> HandScore:
        """Evaluate 5-7 cards and return best hand score (higher = better)."""
        n = len(cards)
        if n < 5:
            raise ValueError(f"Need at least 5 cards, got {n}")
        if n == 5:
            return _evaluate_5(cards)
        best = None
        for combo in combinations(cards, 5):
            score = _evaluate_5(list(combo))
            if best is None or score > best:
                best = score
        return best

    @staticmethod
    def hand_rank_name(score: HandScore) -> str:
        return str(HandRank(score[0]))

    @staticmethod
    def compare(score_a: HandScore, score_b: HandScore) -> int:
        """Return 1 if a wins, -1 if b wins, 0 if tie."""
        if score_a > score_b:
            return 1
        if score_a < score_b:
            return -1
        return 0
