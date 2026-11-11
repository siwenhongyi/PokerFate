"""Fast hand categorization into 6 buckets.

Uses HandEvaluator (combinatorial, no MC) so each call is < 0.1ms.
On the river, unfinished draws are demoted to 'air'.

Reference: PioSolver equity-bucket concept.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import List

from collections import OrderedDict

from pokerfate.core.card import Card
from pokerfate.core.hand_evaluator import HandEvaluator, HandRank, _EVAL7_CARDS, _HAS_EVAL7, _eval7
from pokerfate.strategy.range_v2.hand_combo_map import cards_of

# eval7 hand-type label -> HandRank. Used by the fast scorer below.
_EVAL7_TYPE_TO_RANK = {
    'High Card': HandRank.HIGH_CARD, 'Pair': HandRank.ONE_PAIR, 'Two Pair': HandRank.TWO_PAIR,
    'Trips': HandRank.THREE_OF_A_KIND, 'Straight': HandRank.STRAIGHT, 'Flush': HandRank.FLUSH,
    'Full House': HandRank.FULL_HOUSE, 'Quads': HandRank.FOUR_OF_A_KIND,
    'Straight Flush': HandRank.STRAIGHT_FLUSH,
}


def _score(cards):
    """(HandRank, r1, r2, strength) for 5-7 cards.

    ``r1``/``r2`` are the group ranks the categorizer reads from
    ``HandEvaluator.evaluate`` (pair rank, top two pair ranks, trips rank,
    full-house trips/pair ranks, quads rank). ``strength`` is a comparable
    value (eval7 int when available, else the evaluate() tuple) used only for
    "does hero improve the board" equality checks.

    With eval7 installed this is one C lookup plus a rank count instead of
    C(7,5)=21 pure-Python five-card evaluations; categorising the 1326 combos
    of one board drops from ~130 ms to ~15 ms, which was 60% of replay and
    live notify_action time (profiled 2026-11-09).
    """
    if not _HAS_EVAL7:
        sc = HandEvaluator.evaluate(cards)
        r1 = sc[1] if len(sc) > 1 else 0
        r2 = sc[2] if len(sc) > 2 else 0
        return HandRank(sc[0]), r1, r2, tuple(sc)
    value = _eval7.evaluate([_EVAL7_CARDS[(int(c.rank) - 2) * 4 + int(c.suit)] for c in cards])
    hand_rank = _EVAL7_TYPE_TO_RANK[_eval7.handtype(value)]
    r1 = r2 = 0
    if hand_rank in (HandRank.ONE_PAIR, HandRank.TWO_PAIR, HandRank.THREE_OF_A_KIND,
                     HandRank.FULL_HOUSE, HandRank.FOUR_OF_A_KIND):
        counts = Counter(int(c.rank) for c in cards)
        quads = sorted((r for r, n in counts.items() if n == 4), reverse=True)
        trips = sorted((r for r, n in counts.items() if n == 3), reverse=True)
        pairs = sorted((r for r, n in counts.items() if n == 2), reverse=True)
        if hand_rank == HandRank.FOUR_OF_A_KIND:
            r1 = quads[0]
        elif hand_rank == HandRank.FULL_HOUSE:
            r1 = trips[0]
            r2 = max([t for t in trips[1:]] + pairs)
        elif hand_rank == HandRank.THREE_OF_A_KIND:
            r1 = trips[0]
        elif hand_rank == HandRank.TWO_PAIR:
            r1, r2 = pairs[0], pairs[1]
        else:
            r1 = pairs[0]
    return hand_rank, r1, r2, value


_ALL_COMBOS_CACHE: "OrderedDict[tuple, List[str]]" = OrderedDict()
_ALL_COMBOS_CACHE_MAX = 32


def categorize_all(board: List[Card]) -> List[str]:
    """Categories of all 1326 combos on ``board`` (combos that share a card
    with the board are returned as 'air'; callers mask them anyway).

    Shared, board-keyed LRU so the range tracker and the action model do not
    each recompute the same 1326 evaluations for every opponent action.
    """
    key = tuple(sorted((int(c.rank), int(c.suit)) for c in board)) if board else ()
    hit = _ALL_COMBOS_CACHE.get(key)
    if hit is not None:
        _ALL_COMBOS_CACHE.move_to_end(key)
        return hit
    board_list = list(board) if key else []
    board_ints = {(int(c.rank), int(c.suit)) for c in board_list}
    out = []
    for idx in range(1326):
        c1, c2 = cards_of(idx)
        if board_list and ((int(c1.rank), int(c1.suit)) in board_ints or (int(c2.rank), int(c2.suit)) in board_ints):
            out.append(AIR)
        else:
            out.append(categorize_cards([c1, c2], board_list))
    _ALL_COMBOS_CACHE[key] = out
    if len(_ALL_COMBOS_CACHE) > _ALL_COMBOS_CACHE_MAX:
        _ALL_COMBOS_CACHE.popitem(last=False)
    return out

# Bucket names (ordered strong → weak)
NUTS = 'nuts'           # set+, two pair top, straights, flushes, full houses, quads
STRONG = 'strong'       # overpair, top pair good kicker
MEDIUM = 'medium'       # top pair weak kicker, second pair, pocket pair below top
DRAW = 'draw'           # flush draw, OESD (8+ outs)
WEAK_DRAW = 'weak_draw' # gutshot, backdoor + overcards
AIR = 'air'             # nothing
GOOD_KICKER_MIN_RANK = 10


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


def _board_made_bucket(hole, board, score, hand_rank, board_ranks_desc, strength=None):
    """Bucket for made hands that live entirely on the board, else ``None``.

    The evaluator scores hole+board together, so on 6♦J♣6♣6♥ a K♥T♦ holding
    is "three of a kind" and used to be bucketed NUTS although its equity was
    22% (2% on the river): every opponent shares the board trips and any pair
    beats the kicker. The same happened for board full houses / quads and for
    5-card board straights and flushes, and because villain ranges are
    bucketed with this function too, such boards turned *every* villain combo
    into "nuts", zeroing hero's fold priors and inflating nut mass.
    """
    if hand_rank < HandRank.THREE_OF_A_KIND:
        return None
    hole_ranks = {c.rank for c in hole}

    def kicker_bucket() -> str:
        # Hero only brings kickers: overcards to the board keep showdown value.
        return MEDIUM if all(c.rank > board_ranks_desc[0] for c in hole) else AIR

    if hand_rank == HandRank.THREE_OF_A_KIND:
        return None if score[1] in hole_ranks else kicker_bucket()
    if hand_rank == HandRank.FOUR_OF_A_KIND:
        return None if score[1] in hole_ranks else kicker_bucket()
    if hand_rank == HandRank.FULL_HOUSE:
        if score[1] in hole_ranks or score[2] in hole_ranks:
            return None
        return kicker_bucket()
    if len(board) < 5:
        return None
    board_rank, _b1, _b2, board_strength = _score(list(board))
    if board_rank < HandRank.STRAIGHT:
        return None
    if (strength if strength is not None else tuple(score)) == board_strength:
        return MEDIUM  # hero plays the board: a chop unless someone improves
    if hand_rank == HandRank.FLUSH and board_rank == HandRank.FLUSH:
        suit = Counter(c.suit for c in board).most_common(1)[0][0]
        if any(c.suit == suit and c.rank == 14 for c in hole):
            return NUTS
        return STRONG  # improves a board flush without the ace
    return None


def categorize_cards(hole: List[Card], board: List[Card]) -> str:
    """Categorize hole cards on the given board."""
    if not board or len(board) < 3:
        return _preflop_bucket(hole)

    all_cards = list(hole) + list(board)
    hand_rank, r1, r2, strength = _score(all_cards)
    score = (hand_rank, r1, r2)
    is_river = len(board) >= 5
    board_ranks = sorted([c.rank for c in board], reverse=True)

    # --- Hands the board makes by itself ---
    board_made = _board_made_bucket(hole, board, score, hand_rank, board_ranks, strength)
    if board_made is not None:
        return board_made

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
            if kicker >= GOOD_KICKER_MIN_RANK:
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
            subtype = 'trips_top_kicker' if kicker >= GOOD_KICKER_MIN_RANK else 'trips_weak_kicker'
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
                subtype = 'top_pair_good_kicker' if kicker >= GOOD_KICKER_MIN_RANK else 'top_pair_weak_kicker'
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
