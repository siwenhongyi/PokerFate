"""Fast hand categorization into 6 buckets.

Uses HandEvaluator (combinatorial, no MC) so each call is < 0.1ms.
On the river, unfinished draws are demoted to 'air'.

Reference: PioSolver equity-bucket concept.
"""

from __future__ import annotations

from collections import Counter
from typing import List, Tuple

from pokerfate.core.card import Card
from pokerfate.core.hand_evaluator import HandEvaluator, HandRank
from pokerfate.strategy.range_v2.hand_combo_map import cards_of

# Bucket names (ordered strong → weak)
NUTS = 'nuts'           # set+, two pair top, straights, flushes, full houses, quads
STRONG = 'strong'       # overpair, top pair good kicker
MEDIUM = 'medium'       # top pair weak kicker, second pair, pocket pair below top
DRAW = 'draw'           # flush draw, OESD (8+ outs)
WEAK_DRAW = 'weak_draw' # gutshot, backdoor + overcards
AIR = 'air'             # nothing


def categorize(combo_idx: int, board: List[Card]) -> str:
    """Categorize a combo on the given board.  No MC — pure evaluation."""
    c1, c2 = cards_of(combo_idx)
    return categorize_cards([c1, c2], board)


def categorize_cards(hole: List[Card], board: List[Card]) -> str:
    """Categorize hole cards on the given board."""
    if not board or len(board) < 3:
        return _preflop_bucket(hole)

    all_cards = list(hole) + list(board)
    score = HandEvaluator.evaluate(all_cards)
    hand_rank = HandRank(score[0])
    is_river = len(board) >= 5
    board_ranks = sorted([c.rank for c in board], reverse=True)

    # --- Strong made hands ---
    if hand_rank >= HandRank.STRAIGHT:
        return NUTS
    if hand_rank == HandRank.THREE_OF_A_KIND:
        return NUTS
    if hand_rank == HandRank.TWO_PAIR:
        # Two pair using at least one hole card is strong
        hole_ranks = {c.rank for c in hole}
        pair_ranks_in_score = [score[1], score[2]]  # the two pair ranks
        if hole_ranks & set(pair_ranks_in_score):
            return STRONG
        return MEDIUM  # board two pair
    if hand_rank == HandRank.ONE_PAIR:
        pair_rank = score[1]
        hole_ranks = {c.rank for c in hole}
        if pair_rank not in hole_ranks and pair_rank not in {c.rank for c in board}:
            # Pair from board + kicker
            pass
        # Check if pair uses a hole card
        board_rank_counts = Counter(c.rank for c in board)
        if board_rank_counts.get(pair_rank, 0) >= 2:
            # Board pair — we just have kickers
            if all(c.rank > board_ranks[0] for c in hole):
                return MEDIUM  # overcards to board pair
            return AIR
        # Pair involves a hole card
        if pair_rank >= board_ranks[0]:
            # Top pair or overpair
            non_pair = [c.rank for c in hole if c.rank != pair_rank]
            kicker = max(non_pair) if non_pair else pair_rank
            if pair_rank > board_ranks[0]:
                return STRONG  # overpair
            # Top pair: kicker quality matters
            if kicker >= 12:  # Q+
                return STRONG
            return MEDIUM
        if len(board_ranks) > 1 and pair_rank >= board_ranks[1]:
            return MEDIUM  # second pair
        return MEDIUM  # bottom pair / low pocket pair

    # --- No made hand: check draws ---
    if not is_river:
        if _has_flush_draw(hole, board):
            return DRAW
        if _has_oesd(hole, board):
            return DRAW
        if _has_gutshot(hole, board):
            return WEAK_DRAW
        # Backdoor flush + overcards (flop only)
        if len(board) == 3:
            if _has_backdoor_flush(hole, board) and _has_overcards(hole, board):
                return WEAK_DRAW

    # Overcards on non-river
    if not is_river and _has_overcards(hole, board):
        return WEAK_DRAW

    return AIR


def _preflop_bucket(hole: List[Card]) -> str:
    """Rough preflop bucket (used when no board available)."""
    r1, r2 = hole[0].rank, hole[1].rank
    hi, lo = max(r1, r2), min(r1, r2)
    suited = hole[0].suit == hole[1].suit
    if hi == lo:
        if hi >= 10:
            return NUTS  # TT+
        if hi >= 7:
            return STRONG  # 77-99
        return MEDIUM  # 22-66
    if hi == 14:  # Ace
        if lo >= 10:
            return STRONG  # AT+
        if suited and lo >= 6:
            return MEDIUM  # A6s+
        if lo >= 10:
            return MEDIUM
        return WEAK_DRAW if suited else AIR
    if hi >= 12 and lo >= 10:
        return STRONG if suited else MEDIUM  # KQ, KJ, QJ, KTs+
    if suited and hi - lo <= 3 and lo >= 5:
        return MEDIUM  # suited connectors / 1-gappers
    return AIR


# -----------------------------------------------------------------------
# Draw detection helpers
# -----------------------------------------------------------------------

def _has_flush_draw(hole: List[Card], board: List[Card]) -> bool:
    """4 cards of same suit between hole + board."""
    suits = Counter(c.suit for c in list(hole) + list(board))
    for suit, cnt in suits.items():
        if cnt >= 4:
            # At least one hole card contributes
            if any(c.suit == suit for c in hole):
                return True
    return False


def _has_oesd(hole: List[Card], board: List[Card]) -> bool:
    """Open-ended straight draw: 4 consecutive ranks (8 outs)."""
    all_ranks = sorted(set(c.rank for c in list(hole) + list(board)))
    hole_ranks = {c.rank for c in hole}
    for i in range(len(all_ranks) - 3):
        window = all_ranks[i:i + 4]
        if window[-1] - window[0] == 3:
            # Check we don't already have a straight (5 consecutive)
            if i + 4 < len(all_ranks) and all_ranks[i + 4] - window[0] == 4:
                continue  # already a straight
            # At least one hole card contributes
            if hole_ranks & set(window):
                return True
    # Wheel draw: A-2-3-4
    wheel = {14, 2, 3, 4}
    if len(wheel & set(all_ranks)) >= 4 and (hole_ranks & wheel):
        return True
    return False


def _has_gutshot(hole: List[Card], board: List[Card]) -> bool:
    """Gutshot straight draw: 4 ranks within span of 4 (one gap, 4 outs)."""
    all_ranks = sorted(set(c.rank for c in list(hole) + list(board)))
    hole_ranks = {c.rank for c in hole}
    for i in range(len(all_ranks) - 3):
        window = all_ranks[i:i + 4]
        if window[-1] - window[0] == 4 and len(window) == 4:
            if hole_ranks & set(window):
                return True
    # Wheel gutshot
    wheel = {14, 2, 3, 4, 5}
    present = wheel & set(all_ranks)
    if len(present) >= 4 and (hole_ranks & present):
        return True
    return False


def _has_backdoor_flush(hole: List[Card], board: List[Card]) -> bool:
    """3 cards of same suit (only meaningful on flop)."""
    suits = Counter(c.suit for c in list(hole) + list(board))
    for suit, cnt in suits.items():
        if cnt >= 3 and any(c.suit == suit for c in hole):
            return True
    return False


def _has_overcards(hole: List[Card], board: List[Card]) -> bool:
    """Both hole cards above highest board card."""
    if not board:
        return False
    top_board = max(c.rank for c in board)
    return all(c.rank > top_board for c in hole)
