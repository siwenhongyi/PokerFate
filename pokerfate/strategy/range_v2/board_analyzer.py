"""Board texture analysis and blocker detection.

Reference: GTO Wizard Board Texture Classification.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import List

from pokerfate.core.card import Card


@dataclass(frozen=True)
class BoardTexture:
    wetness: float          # [0, 1]
    flush_possible: bool    # 3+ of a suit on board → made flush possible
    flush_draw: bool        # 2 of a suit → flush draw possible
    flush_draw_suits: frozenset  # suits with 2+ cards
    monotone: bool          # 3+ of same suit
    straight_possible: bool # 5 board cards with straight
    straight_draw_heavy: bool  # connected board (many OESD combos)
    paired: bool            # board has a pair
    high_card_rank: int     # highest board card rank
    connectedness: float    # [0, 1] how connected the board is


def analyze(board: List[Card]) -> BoardTexture:
    """Analyze board texture."""
    if not board:
        return BoardTexture(
            wetness=0.0, flush_possible=False, flush_draw=False,
            flush_draw_suits=frozenset(), monotone=False,
            straight_possible=False, straight_draw_heavy=False,
            paired=False, high_card_rank=0, connectedness=0.0,
        )

    suit_counts = Counter(c.suit for c in board)
    rank_counts = Counter(c.rank for c in board)
    max_suit_count = max(suit_counts.values())
    ranks = sorted(set(c.rank for c in board))

    flush_draw_suits = frozenset(s for s, cnt in suit_counts.items() if cnt >= 2)
    flush_possible = max_suit_count >= 3
    flush_draw = max_suit_count >= 2
    monotone = max_suit_count >= 3
    paired = any(cnt >= 2 for cnt in rank_counts.values())

    # Connectedness: measure how many straight draws exist
    gaps = []
    for i in range(len(ranks) - 1):
        gaps.append(ranks[i + 1] - ranks[i])
    avg_gap = sum(gaps) / len(gaps) if gaps else 10
    connectedness = max(0.0, min(1.0, 1.0 - (avg_gap - 1) / 5))

    straight_draw_heavy = len(ranks) >= 2 and avg_gap <= 2.5

    # Straight possible (only with 5 board cards)
    straight_possible = False
    if len(ranks) >= 5:
        for i in range(len(ranks) - 4):
            if ranks[i + 4] - ranks[i] == 4:
                straight_possible = True
                break

    # Wetness
    wetness = 0.0
    if flush_draw:
        wetness += 0.40
    if monotone:
        wetness += 0.20
    if straight_draw_heavy:
        wetness += 0.30
    if paired:
        wetness -= 0.10  # paired boards are drier
    wetness = max(0.0, min(1.0, wetness))
    # River: no more draws
    if len(board) >= 5:
        wetness *= 0.3

    return BoardTexture(
        wetness=wetness,
        flush_possible=flush_possible,
        flush_draw=flush_draw,
        flush_draw_suits=flush_draw_suits,
        monotone=monotone,
        straight_possible=straight_possible,
        straight_draw_heavy=straight_draw_heavy,
        paired=paired,
        high_card_rank=max(c.rank for c in board),
        connectedness=connectedness,
    )
