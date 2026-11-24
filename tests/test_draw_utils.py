"""Tests for draw_utils."""

import pytest

from pokerfate.core.card import Card
from pokerfate.strategy.draw_utils import is_drawing_heavy


@pytest.mark.parametrize("hole, board, expected", [
    (["Ah", "Kh"], ["Qh", "Jh", "2d"], True),    # four to a flush
    (["9h", "8d"], ["7c", "6s", "2d"], True),    # open-ended straight draw
    (["Ah", "Kh"], ["Qh", "Jh", "9h"], False),   # made flush
    (["As", "Kd"], ["Ac", "7h", "2d"], False),   # top pair, rainbow board
])
def test_is_drawing_heavy(hole, board, expected):
    assert is_drawing_heavy([Card.from_str(c) for c in hole], [Card.from_str(c) for c in board]) is expected
