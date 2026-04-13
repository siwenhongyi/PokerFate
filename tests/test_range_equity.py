"""Range-based equity helpers (GTOv2)."""

from pokerfate.core.card import Card
from pokerfate.core.equity import EquityCalculator
from pokerfate.strategy.range_hands import top_fraction_hole_combos


def test_top_fraction_preflop_nonempty():
    hole = [Card.from_str("As"), Card.from_str("Kd")]
    ex = set(hole)
    r = top_fraction_hole_combos(0.15, ex, [])
    assert 50 < len(r) < 2000


def test_calculate_vs_top_range_multi_matches_hu_range():
    hole = [Card.from_str("Ah"), Card.from_str("Kh")]
    board = [Card.from_str("2c"), Card.from_str("7d"), Card.from_str("Jh")]
    ex = set(hole) | set(board)
    hands = top_fraction_hole_combos(0.25, ex, board)
    e1 = EquityCalculator.calculate_vs_range(hole, board, hands, iterations=400)
    e2 = EquityCalculator.calculate_vs_top_range_multi(hole, board, 1, hands, iterations=400)
    assert 0.0 <= e1 <= 1.0 and 0.0 <= e2 <= 1.0
    assert abs(e1 - e2) < 0.12
