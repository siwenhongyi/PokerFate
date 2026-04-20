from __future__ import annotations

import numpy as np

from pokerfate.core.card import Card
from pokerfate.core.equity import EquityCalculator
from pokerfate.strategy.range_v2.range_equity_calculator import RangeEquityCalculator
from pokerfate.strategy.v3 import DecisionCtx, V3Engine, VillainStats
from pokerfate.strategy.v3 import board as v3_board


def c(s: str) -> Card:
    return Card.from_str(s)


def cards(*items: str) -> list[Card]:
    return [c(x) for x in items]


def test_raw_mc_equity_repeats_with_same_seed() -> None:
    calc = EquityCalculator()
    hole = cards('As', 'Kd')
    board = cards('Qh', '7c', '2d')

    a = calc.calculate(hole, board, num_opponents=1, iterations=250, seed=123)
    b = calc.calculate(hole, board, num_opponents=1, iterations=250, seed=123)

    assert a == b


def test_weighted_equity_repeats_with_same_seed() -> None:
    hero = cards('As', 'Kd')
    board = cards('Qh', '7c', '2d')
    weights = np.ones(1326, dtype=np.float64)

    a = RangeEquityCalculator.weighted_equity(
        hero, board, weights, n_samples=250, seed=456,
    )
    b = RangeEquityCalculator.weighted_equity(
        hero, board, weights, n_samples=250, seed=456,
    )

    assert a == b


def test_weighted_equity_multi_repeats_with_same_seed() -> None:
    hero = cards('As', 'Kd')
    board = cards('Qh', '7c', '2d')
    weights = [
        np.ones(1326, dtype=np.float64),
        np.ones(1326, dtype=np.float64),
    ]

    a = RangeEquityCalculator.weighted_equity_multi(
        hero, board, weights, n_samples=250, seed=789,
    )
    b = RangeEquityCalculator.weighted_equity_multi(
        hero, board, weights, n_samples=250, seed=789,
    )

    assert a == b


def test_v3_uses_ctx_seed_for_replayable_sampling() -> None:
    board = cards('Jh', 'Th', '4c')
    base = dict(
        street='flop',
        hole_cards=cards('Qh', '9c'),
        board=board,
        position='CO',
        is_ip=True,
        num_opponents=2,
        pot=100.0,
        stack=800.0,
        big_blind=2.0,
        spr=8.0,
        facing_bet=False,
        hero_bucket='draw',
        equity_mc=0.35,
        equity_range=0.35,
        board_sig=v3_board.analyze(board),
        villain_stats=VillainStats(hands_seen=80, fold_to_cbet=0.50),
        seed=20260429,
    )

    a = V3Engine().decide(DecisionCtx(**base))
    b = V3Engine().decide(DecisionCtx(**base))

    assert a.seed == b.seed == 20260429
    assert a.action == b.action
    assert a.purpose == b.purpose
    assert a.candidates == b.candidates
