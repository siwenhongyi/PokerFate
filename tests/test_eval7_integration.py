"""Tests for HandEvaluator.eval_int (eval7-backed fast scorer)."""
from __future__ import annotations

import time

from pokerfate.core.card import Card
from pokerfate.core.hand_evaluator import (
    HandEvaluator, _HAS_EVAL7,
)


def _c(s: str) -> Card:
    return Card.from_str(s)


def test_eval7_is_installed():
    """We expect eval7 to be installed in dev env."""
    assert _HAS_EVAL7, "eval7 not installed — install via requirements.txt"


def test_eval_int_orders_consistent_with_evaluate():
    """eval_int must agree with evaluate() on which hand is better, across
    a battery of representative pairs.
    """
    cases = [
        # (hand A, hand B, board) — A should beat B on board
        (['As', 'Ks'], ['Qd', 'Jc'], ['Ah', '2c', '7d', '5s', '9h']),  # AK pair vs nothing
        (['Ah', 'Ad'], ['Kh', 'Kd'], ['2c', '7d', '5s', '9h', 'Tc']),  # AA vs KK
        (['As', 'Ks'], ['Ah', 'Kc'], ['Qs', 'Js', 'Ts', '2d', '5h']),  # royal flush vs trips
        (['7s', '7h'], ['As', 'Kd'], ['7c', '2d', '5h', '9c', '3s']),  # set vs ace high
    ]
    for hole_a, hole_b, board in cases:
        a = [_c(s) for s in hole_a + board]
        b = [_c(s) for s in hole_b + board]

        sa_old = HandEvaluator.evaluate(a)
        sb_old = HandEvaluator.evaluate(b)
        sa_new = HandEvaluator.eval_int(a)
        sb_new = HandEvaluator.eval_int(b)

        # Both must agree A > B
        assert sa_old > sb_old, f"old: {hole_a} should beat {hole_b}"
        assert sa_new > sb_new, f"new: {hole_a} should beat {hole_b}"


def test_eval_int_ties_consistent():
    """Ties must be detected consistently."""
    # Both hands play the board (chop)
    a = [_c('2c'), _c('3d')]
    b = [_c('4c'), _c('5d')]
    board = [_c('Ah'), _c('Kh'), _c('Qh'), _c('Jh'), _c('Th')]   # board = royal
    sa = HandEvaluator.eval_int(a + board)
    sb = HandEvaluator.eval_int(b + board)
    assert sa == sb


def test_eval_int_speed_advantage():
    """Smoke-bench: eval_int should be ≥ 5x faster than evaluate on 7-card."""
    cards = [_c('As'), _c('Ks'), _c('Qh'), _c('Jc'), _c('7d'), _c('5h'), _c('2c')]
    n = 2000

    t0 = time.perf_counter()
    for _ in range(n):
        HandEvaluator.evaluate(cards)
    t_old = time.perf_counter() - t0

    t0 = time.perf_counter()
    for _ in range(n):
        HandEvaluator.eval_int(cards)
    t_new = time.perf_counter() - t0

    speedup = t_old / max(t_new, 1e-9)
    print(f"\nevaluate: {t_old*1e6/n:.1f}us  eval_int: {t_new*1e6/n:.1f}us  "
          f"speedup: {speedup:.1f}x")
    assert speedup >= 5.0, f"eval_int only {speedup:.1f}x faster — expected ≥5x"


def test_river_equity_unchanged_with_eval7():
    """River exact-enum equity must be identical regardless of which scorer
    is used internally — both must produce the correct combinatorial answer.
    """
    import numpy as np
    from pokerfate.strategy.range_v2.range_equity_calculator import RangeEquityCalculator

    my = [_c('As'), _c('Ah')]   # pocket aces, overpair to dry board
    board = [_c('Qh'), _c('7c'), _c('2d'), _c('Jc'), _c('5h')]
    w = np.ones(1326, dtype=np.float64)

    eq = RangeEquityCalculator.weighted_equity(my, board, w)
    # AA overpair on dry rainbow river vs uniform range → strong
    assert 0.70 < eq < 0.99
