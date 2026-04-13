"""Tests for draw_utils."""

from pokerfate.core.card import Card
from pokerfate.strategy.draw_utils import is_drawing_heavy


def _c(s: str) -> Card:
    return Card.from_str(s)


def test_flush_draw_four_to_flush():
    hole = [_c("Ah"), _c("Kh")]
    board = [_c("Qh"), _c("Jh"), _c("2d")]  # 四张红桃：同花听牌
    assert is_drawing_heavy(hole, board) is True


def test_made_flush_not_draw():
    hole = [_c("Ah"), _c("Kh")]
    board = [_c("Qh"), _c("Jh"), _c("9h")]
    assert is_drawing_heavy(hole, board) is False


def test_pair_no_draw_on_rainbow():
    hole = [_c("As"), _c("Kd")]
    board = [_c("Ac"), _c("7h"), _c("2d")]
    assert is_drawing_heavy(hole, board) is False


def test_open_ended_four_to_straight():
    hole = [_c("9h"), _c("8d")]
    board = [_c("7c"), _c("6s"), _c("2d")]
    assert is_drawing_heavy(hole, board) is True
