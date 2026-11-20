from pokerfate.strategy.range_v2.river_relative_calibrator import (
    clamp_equity_to_bounds,
    clamp_relation_to_bounds,
    exact_relation_bounds,
    relation_eq,
)
from pokerfate.core.card import Card


def _cards(*names):
    return [Card.from_str(name) for name in names]


def test_exact_lock_hand_is_bounded():
    bounds = exact_relation_bounds(_cards("As", "Ad"), _cards("Ah", "Ac", "Kd", "7s", "2c"))
    raw = {"win": 0.40, "tie": 0.10, "loss": 0.50}
    out = clamp_relation_to_bounds(raw, bounds)
    assert out == {"win": 1.0, "tie": 0.0, "loss": 0.0}
    assert clamp_equity_to_bounds(0.95, bounds) == 1.0
