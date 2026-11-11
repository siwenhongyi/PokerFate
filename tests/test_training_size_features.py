from __future__ import annotations

import pytest
import numpy as np

from pokerfate.core.card import Card
from pokerfate.strategy.range_v2 import bucket_ml_calibration as bucket_ml
from pokerfate.strategy.range_v2 import hero_eq_calibrator as heq


def _row() -> dict:
    return {
        "street": "turn",
        "trigger": "action:raise",
        "active_player_count": 2,
        "board": ["As", "Td", "4c", "2h"],
        "bucket_dist": {
            "nuts": 0.05,
            "strong": 0.20,
            "medium": 0.35,
            "draw": 0.10,
            "weak_draw": 0.05,
            "air": 0.25,
        },
        "actual_bucket": "strong",
        "hero_bucket": "medium",
        "position": "BTN",
        "is_ip": True,
        "facing_action": "bet",
        "preflop_action_type": "call_open",
        "action_bet_ratio": 1.2,
        "bet_size_bucket": "overpot",
        "is_raise_over": True,
        "action_sequence": "flop:call|turn:raise",
    }


def test_lgbm_context_features_include_bet_size() -> None:
    pytest.importorskip("lightgbm")
    from scripts import fit_range_lgbm_calibration as lgbm

    row = _row()

    feats = lgbm._bucket_features_runtime(row)

    assert feats["bet_size_bucket=overpot"] == 1.0
    assert feats["action_bet_ratio"] == pytest.approx(bucket_ml._clip01(row["action_bet_ratio"], 4.0))
    assert feats["is_raise_over"] == 1.0


def test_bucket_ml_runtime_features_include_bet_size() -> None:
    features = bucket_ml._feature_values(
        np.array([0.05, 0.20, 0.35, 0.10, 0.05, 0.25]),
        street="turn",
        trigger="action:raise",
        active_count=2,
        board=[
            Card.from_str("As"),
            Card.from_str("Td"),
            Card.from_str("4c"),
            Card.from_str("2h"),
        ],
        range_pct=0.32,
        hero_bucket="medium",
        position="BTN",
        is_ip=True,
        facing_action="bet",
        preflop_action_type="call_open",
        action_bet_ratio=1.2,
        bet_size_bucket="overpot",
        is_raise_over=True,
        action_sequence="flop:call|turn:raise",
    )

    assert features["bet_size_bucket=overpot"] == 1.0
    assert features["action_bet_ratio"] == pytest.approx(0.3)
    assert features["is_raise_over"] == 1.0
    assert features["position=BTN"] == 1.0


