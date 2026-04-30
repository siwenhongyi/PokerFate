"""Tests for the equity calculator."""

from pokerfate.core.card import Card
from pokerfate.core.equity import EquityCalculator


def card(s):
    return Card.from_str(s)


def cards(*strs):
    return [card(s) for s in strs]


class TestEquityCalculator:
    calc = EquityCalculator()

    def test_AA_vs_random_preflop(self):
        # AA should win ~85% preflop heads up
        hole = cards('Ac', 'Ad')
        eq = self.calc.calculate(hole, [], num_opponents=1, iterations=3000)
        assert 0.75 <= eq <= 0.95, f"AA equity should be ~85%, got {eq:.2%}"

    def test_72o_vs_random_preflop(self):
        # 72o should be weak, around 35%
        hole = cards('7c', '2d')
        eq = self.calc.calculate(hole, [], num_opponents=1, iterations=3000)
        assert 0.25 <= eq <= 0.50, f"72o equity should be ~35%, got {eq:.2%}"

    def test_flush_draw_equity(self):
        # Flush draw on flop should be ~36%
        hole = cards('Ah', 'Kh')
        board = cards('Qh', '7h', '2c')  # 4-flush, need 1 more heart
        eq = self.calc.calculate(hole, board, num_opponents=1, iterations=3000)
        assert 0.55 <= eq <= 0.95  # AKh has top pair + nut flush draw = very strong

    def test_made_hand_vs_draw(self):
        # Top set vs flush draw: set should be heavy favorite
        hole_set = cards('Qc', 'Qd')  # top set on QJ9
        board = cards('Qh', 'Jh', '9h')  # monotone, flush draw possible
        eq = self.calc.calculate(hole_set, board, num_opponents=1, iterations=3000)
        # Set still strong despite wet board
        assert eq >= 0.50

    def test_equity_with_board(self):
        hole = cards('Ac', 'Kd')
        board = cards('Ah', '2c', '7d', '9s')  # turn card
        eq = self.calc.calculate(hole, board, num_opponents=1, iterations=2000)
        # TPTK should be decent favorite
        assert eq >= 0.55

    def test_equity_bounds(self):
        hole = cards('5c', '5d')
        eq = self.calc.calculate(hole, [], num_opponents=1, iterations=1000)
        assert 0.0 <= eq <= 1.0
