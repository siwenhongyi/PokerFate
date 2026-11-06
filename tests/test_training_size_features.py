from __future__ import annotations

import pytest
import numpy as np

from pokerfate.core.card import Card
from pokerfate.strategy.range_v2 import bucket_ml_calibration as bucket_ml
from pokerfate.strategy.range_v2 import hero_eq_calibrator as heq
from scripts import fit_range_calibration_v2 as formula


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

    base = lgbm._features(row, include_context=False)
    with_context = lgbm._features(row, include_context=True)

    assert "bet_size_bucket=overpot" not in base
    assert with_context["bet_size_bucket=overpot"] == 1
    assert with_context["action_bet_ratio"] == pytest.approx(0.3)
    assert with_context["is_raise_over"] == 1.0


def test_formula_size_context_keys() -> None:
    row = _row()

    assert formula._bucket_context(row, "size") == (
        "turn action:raise size=overpot rr=1"
    )
    assert formula._bucket_context(row, "rich_size") == (
        "turn action:raise nopp=2 tex=unpaired:rainbow size=overpot rr=1"
    )
    assert formula._eq_context(row, "action_size") == (
        "turn|medium|2|raise|size=overpot rr=1"
    )
    assert formula._eq_context(row, "rich_size") == (
        "turn|medium|2|raise|unpaired:rainbow|size=overpot rr=1"
    )


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


def test_runtime_equity_formula_prefers_size_context(monkeypatch) -> None:
    def fake_load_runtime_params(_big_blind):
        return {
            "flop|strong|2|bet": {"type": "bias", "bias": -0.20},
            "flop|strong|2|bet|size=pot rr=1": {"type": "bias", "bias": 0.20},
        }

    def fake_ml(raw_eq, **_kwargs):
        return raw_eq, {"mode": "off", "used": False}

    monkeypatch.setattr(heq, "_load_runtime_equity_params", fake_load_runtime_params)
    monkeypatch.setattr(heq, "calibrate_equity", fake_ml)

    cal = heq.HeroEquityCalibrator()
    out = cal.calibrate(
        0.50,
        "strong",
        "flop",
        2,
        action_ctx="bet",
        big_blind=10_000,
        action_bet_ratio=1.0,
        bet_size_bucket="pot",
        is_raise_over=True,
    )

    assert out == pytest.approx(0.70)
