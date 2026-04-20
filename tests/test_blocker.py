"""Tests for hero blocker weighting on opponent likelihood."""
from __future__ import annotations

import numpy as np

from pokerfate.core.card import Card
from pokerfate.strategy.range_v2.blocker import (
    SUIT_MASKS,
    _FLUSH_PENALTY_2,
    _FLUSH_PENALTY_3PLUS,
    blocker_weights,
)
from pokerfate.strategy.range_v2.hand_combo_map import COMBO_TO_IDX, card_to_int


def _c(s: str) -> Card:
    return Card.from_str(s)


def _idx(c1: str, c2: str) -> int:
    a, b = card_to_int(_c(c1)), card_to_int(_c(c2))
    return COMBO_TO_IDX[(min(a, b), max(a, b))]


def test_no_hero_cards_returns_ones():
    board = [_c('2s'), _c('7s'), _c('Jd')]
    w = blocker_weights([], board)
    assert np.all(w == 1.0)


def test_no_board_returns_ones():
    w = blocker_weights([_c('As'), _c('Ks')], [])
    assert np.all(w == 1.0)


def test_preflop_returns_ones():
    w = blocker_weights([_c('As'), _c('Ks')], [_c('2c'), _c('7d')])
    assert np.all(w == 1.0)


def test_no_flush_threat_returns_ones():
    # rainbow board — no two cards of same suit
    board = [_c('Ad'), _c('Kc'), _c('Qh')]
    w = blocker_weights([_c('As'), _c('Ks')], board)
    assert np.all(w == 1.0)


def test_two_tone_board_one_hero_blocker():
    # 2-flush board, hero holds one spade → backdoor penalty 0.10
    board = [_c('2s'), _c('7s'), _c('Jd')]
    hero = [_c('As'), _c('Kd')]
    w = blocker_weights(hero, board)

    # A spade-containing combo (e.g., Qs5h) should be reduced
    flush_combo = _idx('Qs', '5h')
    assert abs(w[flush_combo] - (1.0 - _FLUSH_PENALTY_2)) < 1e-9

    # A non-spade combo (e.g., Qd5h) should be unchanged
    non_flush_combo = _idx('Qd', '5h')
    assert w[non_flush_combo] == 1.0


def test_three_flush_board_two_hero_blockers():
    # 3-flush board, hero holds two spades → 2 * 0.20 = 0.40 penalty
    board = [_c('2s'), _c('7s'), _c('Js')]
    hero = [_c('As'), _c('Ks')]
    w = blocker_weights(hero, board)

    # Combo containing a spade (Qs5h) — fully penalised
    flush_combo = _idx('Qs', '5h')
    assert abs(w[flush_combo] - (1.0 - 2 * _FLUSH_PENALTY_3PLUS)) < 1e-9

    # Combo with two spades (Qs9s) — same penalty (we apply per-suit, not per-card)
    two_spade_combo = _idx('Qs', '9s')
    assert abs(w[two_spade_combo] - (1.0 - 2 * _FLUSH_PENALTY_3PLUS)) < 1e-9

    # Non-spade combo unchanged
    assert w[_idx('Qd', '9c')] == 1.0


def test_hero_no_overlap_with_flush_suit():
    # 3-flush board on spades, hero holds no spades → no blocker
    board = [_c('2s'), _c('7s'), _c('Js')]
    hero = [_c('Ad'), _c('Kc')]
    w = blocker_weights(hero, board)
    assert np.all(w == 1.0)


def test_max_penalty_clamp():
    # Pathological: 3-flush board + hero somehow holds 3 of suit
    # (impossible in real holdem but verify clamp)
    board = [_c('2s'), _c('7s'), _c('Js')]
    # Use 3 hero cards to force penalty > 0.50
    hero = [_c('As'), _c('Ks'), _c('Qs')]
    w = blocker_weights(hero, board)
    # 3 * 0.20 = 0.60 → clamped to 0.50
    flush_combo = _idx('5s', '4h')
    assert abs(w[flush_combo] - 0.50) < 1e-9


def test_suit_masks_consistency():
    # SUIT_MASKS[s] should mark exactly the combos that contain ≥1 card of suit s.
    # For spades (suit=3), every combo with >=1 spade should be True.
    spade_int = 3
    # Pick a known combo with 2 spades: AsKs
    assert SUIT_MASKS[spade_int][_idx('As', 'Ks')]
    # Pick a known combo with 1 spade: AsKd
    assert SUIT_MASKS[spade_int][_idx('As', 'Kd')]
    # Pick a known combo with 0 spades: AcKd
    assert not SUIT_MASKS[spade_int][_idx('Ac', 'Kd')]


def test_action_model_integration_attenuates_flush_combo():
    """End-to-end: a 'raise' likelihood for a flush-class combo should
    drop when hero blocks that flush.
    """
    from pokerfate.strategy.range_v2.action_model import (
        ActionContext, ActionModel, PlayerProfile,
    )

    am = ActionModel()
    board = [_c('2s'), _c('7s'), _c('Js')]
    ctx = ActionContext(
        position='BTN', board=board, street='flop',
        facing_action='bet', bet_ratio=0.75, is_raise_over=False,
    )
    prof = PlayerProfile(name='test', hands_seen=200)

    flush_combo = _idx('Qs', '5h')

    no_blocker = am.batch_likelihood('raise', 'flop', ctx, prof, board)
    with_blocker = am.batch_likelihood(
        'raise', 'flop', ctx, prof, board,
        hero_cards=[_c('As'), _c('Ks')],
    )

    # The flush-class combo's likelihood should drop with blocker active.
    assert with_blocker[flush_combo] < no_blocker[flush_combo]
    # Non-flush combo should be unchanged (within floating epsilon)
    non_flush = _idx('Qd', '5c')
    assert abs(with_blocker[non_flush] - no_blocker[non_flush]) < 1e-9
