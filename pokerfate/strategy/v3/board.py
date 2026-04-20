"""Board texture analysis for v3.

Combines pokerfate.strategy.range_v2.board_analyzer (rich signals) with a
few convenience fields the purpose triggers need. Used to populate
DecisionCtx.board_sig.
"""

from __future__ import annotations

from collections import Counter
from typing import List

from pokerfate.core.card import Card
from pokerfate.strategy.range_v2 import board_analyzer as _ba
from pokerfate.strategy.v3.context import BoardSignals


def analyze(board: List[Card]) -> BoardSignals:
    if not board:
        return BoardSignals()

    tex = _ba.analyze(board)

    # Re-compute wetness with postflop's old formula (preserves behavior tests
    # care about): FD +0.35, monotone +0.25, connected +0.25, unpaired +0.15.
    # range_v2.board_analyzer used a different weighting — we keep the new
    # "rich" tex fields but override wetness so downstream gates match
    # published GTO thresholds (is_dry <0.35, is_wet >=0.55).
    w = 0.0
    if tex.flush_draw:
        w += 0.35
    if tex.monotone:
        w += 0.25
    if tex.straight_draw_heavy:
        w += 0.25
    if not tex.paired:
        w += 0.15
    wetness = max(0.0, min(1.0, w))

    return BoardSignals(
        wetness=wetness,
        paired=tex.paired,
        monotone=tex.monotone,
        flush_possible=tex.flush_possible,
        flush_draw=tex.flush_draw,
        straight_draw_heavy=tex.straight_draw_heavy,
        straight_possible=tex.straight_possible,
        connectedness=tex.connectedness,
        high_card_rank=tex.high_card_rank,
        is_dry=wetness < 0.35,
        is_wet=wetness >= 0.55,
    )


def detect_blockers(hole: List[Card], board: List[Card]) -> dict:
    """Compute hero's blocker effects on villain's ranges.

    Returns a plain dict that DecisionCtx.blockers consumes.
    """
    effects = {
        'nut_flush_blocker': False,
        'set_blocker': False,
        'straight_blocker': False,
    }
    if not hole or not board:
        return effects

    # Nut flush blocker: hero holds Ace of the suit with 2+ on board
    suit_cnt = Counter(c.suit for c in board)
    for suit, cnt in suit_cnt.items():
        if cnt >= 2 and any(c.suit == suit and c.rank.value == 14 for c in hole):
            effects['nut_flush_blocker'] = True
            break

    # Set blocker: hero holds a card matching a board rank
    board_ranks = {c.rank.value for c in board}
    if any(c.rank.value in board_ranks for c in hole):
        effects['set_blocker'] = True

    # Straight blocker: hero holds a key card that blocks the top straight
    # Simple heuristic: hero holds a card in the top straight window.
    ranks = sorted({c.rank.value for c in board})
    if len(ranks) >= 2:
        top = max(ranks)
        window = set(range(max(2, top - 4), top + 1))
        if any(c.rank.value in window and c.rank.value not in board_ranks for c in hole):
            effects['straight_blocker'] = True

    return effects
