"""Fast hand categorization into 6 buckets.

Uses HandEvaluator (combinatorial, no MC) so each call is < 0.1ms.
On the river, unfinished draws are demoted to 'air'.

Reference: PioSolver equity-bucket concept.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import List

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


@dataclass(frozen=True)
class MadeHandInfo:
    """Fine-grained made-hand shape for stack-off guards.

    `categorize_cards()` intentionally stays coarse because many strategy
    branches use six stable buckets. This structure adds the missing detail
    for reverse-implied-odds spots without changing those buckets.
    """

    subtype: str = 'none'
    hand_rank: str = 'none'
    made_rank: int = 0
    kicker_rank: int = 0
    board_pair_rank: int = 0
    pocket_pair_rank: int = 0


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


def made_hand_info(hole: List[Card], board: List[Card]) -> MadeHandInfo:
    """Return structural made-hand detail independent of equity estimates."""
    if not hole or not board or len(hole) < 2 or len(board) < 3:
        return MadeHandInfo(subtype=_preflop_bucket(hole) if len(hole) >= 2 else 'none')

    all_cards = list(hole) + list(board)
    score = HandEvaluator.evaluate(all_cards)
    hand_rank = HandRank(score[0])
    hand_rank_name = hand_rank.name.lower()
    hole_ranks = [c.rank for c in hole]
    board_ranks = [c.rank for c in board]
    board_counts = Counter(board_ranks)
    pocket_pair_rank = hole_ranks[0] if hole_ranks[0] == hole_ranks[1] else 0
    board_pair_ranks = [r for r, cnt in board_counts.items() if cnt >= 2]
    board_pair_rank = max(board_pair_ranks) if board_pair_ranks else 0

    if hand_rank >= HandRank.FULL_HOUSE:
        return MadeHandInfo(
            subtype='full_house_plus',
            hand_rank=hand_rank_name,
            made_rank=score[1] if len(score) > 1 else 0,
            board_pair_rank=board_pair_rank,
            pocket_pair_rank=pocket_pair_rank,
        )

    if hand_rank in (HandRank.STRAIGHT, HandRank.FLUSH):
        return MadeHandInfo(
            subtype='straight_or_flush',
            hand_rank=hand_rank_name,
            made_rank=score[1] if len(score) > 1 else 0,
            board_pair_rank=board_pair_rank,
            pocket_pair_rank=pocket_pair_rank,
        )

    if hand_rank == HandRank.THREE_OF_A_KIND:
        trip_rank = score[1]
        hole_trip_count = sum(1 for r in hole_ranks if r == trip_rank)
        board_trip_count = board_counts.get(trip_rank, 0)
        if hole_trip_count == 2:
            subtype = 'set'
            kicker = max((r for r in board_ranks if r != trip_rank), default=0)
        elif hole_trip_count == 1 and board_trip_count >= 2:
            side_kickers = [r for r in hole_ranks if r != trip_rank]
            kicker = max(side_kickers) if side_kickers else 0
            subtype = 'trips_top_kicker' if kicker >= 12 else 'trips_weak_kicker'
        elif board_trip_count >= 3:
            kicker = max(hole_ranks)
            subtype = 'board_trips_kicker'
        else:
            kicker = max((r for r in hole_ranks if r != trip_rank), default=0)
            subtype = 'trips'
        return MadeHandInfo(
            subtype=subtype,
            hand_rank=hand_rank_name,
            made_rank=trip_rank,
            kicker_rank=kicker,
            board_pair_rank=board_pair_rank,
            pocket_pair_rank=pocket_pair_rank,
        )

    if hand_rank == HandRank.TWO_PAIR:
        high_pair = score[1]
        low_pair = score[2]
        kicker = score[3] if len(score) > 3 else 0
        pair_ranks = {high_pair, low_pair}
        if board_pair_rank:
            if pocket_pair_rank and pocket_pair_rank in pair_ranks:
                board_side_high = max((r for r in board_ranks if r != board_pair_rank), default=0)
                if pocket_pair_rank < max(board_pair_rank, board_side_high):
                    subtype = 'board_pair_pocket_underpair'
                else:
                    subtype = 'board_pair_pocket_pair'
            elif set(hole_ranks) & pair_ranks:
                subtype = 'board_pair_hero_pair'
            else:
                subtype = 'board_two_pair'
        else:
            subtype = 'clean_two_pair' if (set(hole_ranks) & pair_ranks) else 'board_two_pair'
        return MadeHandInfo(
            subtype=subtype,
            hand_rank=hand_rank_name,
            made_rank=high_pair,
            kicker_rank=kicker,
            board_pair_rank=board_pair_rank,
            pocket_pair_rank=pocket_pair_rank,
        )

    if hand_rank == HandRank.ONE_PAIR:
        pair_rank = score[1]
        kicker = max((r for r in hole_ranks if r != pair_rank), default=0)
        if pocket_pair_rank:
            top_board = max(board_ranks)
            subtype = 'clean_overpair' if pocket_pair_rank > top_board else 'pocket_pair'
        elif pair_rank in hole_ranks:
            top_board = max(board_ranks)
            if pair_rank >= top_board:
                subtype = 'top_pair_good_kicker' if kicker >= 12 else 'top_pair_weak_kicker'
            else:
                subtype = 'pair'
        elif board_pair_rank:
            subtype = 'board_pair_kicker'
        else:
            subtype = 'pair'
        return MadeHandInfo(
            subtype=subtype,
            hand_rank=hand_rank_name,
            made_rank=pair_rank,
            kicker_rank=kicker,
            board_pair_rank=board_pair_rank,
            pocket_pair_rank=pocket_pair_rank,
        )

    return MadeHandInfo(
        subtype='high_card',
        hand_rank=hand_rank_name,
        kicker_rank=max(hole_ranks) if hole_ranks else 0,
        board_pair_rank=board_pair_rank,
        pocket_pair_rank=pocket_pair_rank,
    )


def made_hand_subtype(hole: List[Card], board: List[Card]) -> str:
    return made_hand_info(hole, board).subtype


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
