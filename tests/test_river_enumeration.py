"""Tests for river exact-enumeration path in RangeEquityCalculator."""
from __future__ import annotations

import numpy as np

from pokerfate.core.card import Card
from pokerfate.strategy.range_v2 import hand_combo_map as hcm
from pokerfate.strategy.range_v2.range_equity_calculator import RangeEquityCalculator


def _c(s: str) -> Card:
    return Card.from_str(s)


def _uniform_weights() -> np.ndarray:
    return np.ones(1326, dtype=np.float64)


def test_river_is_deterministic():
    """Same inputs must produce identical equity across repeated calls."""
    my = [_c('As'), _c('Kd')]
    board = [_c('Qh'), _c('Jc'), _c('7s'), _c('2d'), _c('5h')]
    w = _uniform_weights()

    e1 = RangeEquityCalculator.weighted_equity(my, board, w, n_samples=100)
    e2 = RangeEquityCalculator.weighted_equity(my, board, w, n_samples=100)
    e3 = RangeEquityCalculator.weighted_equity(my, board, w, n_samples=999)

    assert e1 == e2 == e3   # exact enumeration ignores n_samples


def test_river_nuts_returns_one():
    """Royal flush vs uniform range — must be (near) 1.0 (ties only with same hand)."""
    my = [_c('As'), _c('Ks')]
    board = [_c('Qs'), _c('Js'), _c('Ts'), _c('2d'), _c('5h')]   # we have royal
    w = _uniform_weights()

    eq = RangeEquityCalculator.weighted_equity(my, board, w)
    assert eq > 0.99   # at most a few combos can chop or beat (none can beat)


def test_river_dead_hand_returns_low():
    """High card on a board with possible flushes — equity should be low."""
    my = [_c('2c'), _c('3d')]
    board = [_c('As'), _c('Ks'), _c('Qs'), _c('Js'), _c('Ts')]   # board straight to A
    w = _uniform_weights()

    eq = RangeEquityCalculator.weighted_equity(my, board, w)
    # We tie with everyone who plays the board, lose to flush draws.
    assert eq < 0.6


def test_river_weighted_range_concentration():
    """When opponent range is concentrated on weak combos, equity should rise."""
    my = [_c('Ah'), _c('Kh')]   # top pair top kicker
    board = [_c('Ad'), _c('7c'), _c('2s'), _c('Jd'), _c('4h')]

    # uniform
    w_uni = _uniform_weights()
    eq_uni = RangeEquityCalculator.weighted_equity(my, board, w_uni)

    # heavy on a single weak combo: 32o (no pair, no draw)
    w_weak = np.zeros(1326, dtype=np.float64)
    weak_idx = hcm.COMBO_TO_IDX[
        tuple(sorted([hcm.card_to_int(_c('3c')), hcm.card_to_int(_c('2c'))]))
    ]
    w_weak[weak_idx] = 1.0

    eq_weak = RangeEquityCalculator.weighted_equity(my, board, w_weak)
    assert eq_weak > eq_uni   # against pure trash we should do better


def test_river_blocked_combos_not_counted():
    """Combos containing my hole cards or board cards must contribute zero."""
    my = [_c('As'), _c('Kd')]
    board = [_c('Qh'), _c('Jc'), _c('7s'), _c('2d'), _c('5h')]

    # Put weight on an impossible combo (As Kd is in my hand)
    w = np.zeros(1326, dtype=np.float64)
    impossible_idx = hcm.COMBO_TO_IDX[
        tuple(sorted([hcm.card_to_int(_c('As')), hcm.card_to_int(_c('Kd'))]))
    ]
    w[impossible_idx] = 1.0

    # All weight on impossible combo → returns the no-valid-combos default 0.5
    eq = RangeEquityCalculator.weighted_equity(my, board, w)
    assert eq == 0.5
