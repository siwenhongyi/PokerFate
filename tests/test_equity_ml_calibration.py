from __future__ import annotations

import json

import pytest

from pokerfate.strategy.range_v2 import equity_ml_calibration as eqml
from pokerfate.strategy.range_v2.hero_eq_calibrator import HeroEquityCalibrator


FEATURE_NAMES = [
    "raw_eq",
    "p_nuts",
    "p_strong",
    "p_medium",
    "p_draw",
    "p_weak_draw",
    "p_air",
    "range_pct",
    "board_len",
    "street=flop",
    "trigger=action:bet",
    "action=bet",
    "nopp=2",
    "texture=unpaired:rainbow",
    "hero_bucket=strong",
    "strategy_version=test-version",
    "experiment_profile=test-profile",
]


def test_mode_for_big_blind_uses_off_lgbm_fm_values(monkeypatch):
    monkeypatch.setenv("PF_EQUITY_ML_10K", "off")
    monkeypatch.setenv("PF_EQUITY_ML_50K", "fm")
    monkeypatch.setenv("PF_EQUITY_ML_DEFAULT", "lgbm")

    assert eqml.mode_for_big_blind(10_000) == "off"
    assert eqml.mode_for_big_blind(50_000) == "fm"
    assert eqml.mode_for_big_blind(2) == "lgbm"


def test_lgbm_missing_model_falls_back(monkeypatch, tmp_path):
    monkeypatch.setattr(eqml, "_ROOT", tmp_path)
    monkeypatch.setenv("PF_EQUITY_ML_10K", "lgbm")
    eqml.clear_caches()

    out, diag = eqml.calibrate_equity(
        0.42,
        big_blind=10_000,
        bucket_dist={"strong": 1.0},
        street="flop",
        action_ctx="bet",
        active_count=2,
        board_len=3,
        board_texture="unpaired:rainbow",
        range_pct=0.30,
        hero_bucket="strong",
    )

    assert out == 0.42
    assert diag == {"mode": "lgbm", "used": False, "reason": "model_missing"}


def test_runtime_usable_false_falls_back(monkeypatch, tmp_path):
    path = tmp_path / "bb_10k" / "runtime_lgbm_equity_model.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"runtime_usable": False}), encoding="utf-8")
    monkeypatch.setattr(eqml, "_ROOT", tmp_path)
    monkeypatch.setenv("PF_EQUITY_ML_10K", "lgbm")
    eqml.clear_caches()

    out, diag = eqml.calibrate_equity(
        0.42,
        big_blind=10_000,
        bucket_dist={"strong": 1.0},
        street="flop",
        action_ctx="bet",
        active_count=2,
        board_len=3,
        board_texture="unpaired:rainbow",
        range_pct=0.30,
        hero_bucket="strong",
    )

    assert out == 0.42
    assert diag["reason"] == "model_missing"


def test_lightgbm_missing_falls_back(monkeypatch, tmp_path):
    path = tmp_path / "bb_10k" / "runtime_lgbm_equity_model.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({
        "runtime_usable": True,
        "blend_alpha": 0.5,
        "feature_names": ["raw_eq"],
        "model_str": "fake",
    }), encoding="utf-8")
    monkeypatch.setattr(eqml, "_ROOT", tmp_path)
    monkeypatch.setattr(eqml, "Booster", None)
    monkeypatch.setenv("PF_EQUITY_ML_10K", "lgbm")
    eqml.clear_caches()

    out, diag = eqml.calibrate_equity(
        0.42,
        big_blind=10_000,
        bucket_dist={"strong": 1.0},
        street="flop",
        action_ctx="bet",
        active_count=2,
        board_len=3,
        board_texture="unpaired:rainbow",
        range_pct=0.30,
        hero_bucket="strong",
    )

    assert out == 0.42
    assert diag == {"mode": "lgbm", "used": False, "reason": "lightgbm_missing"}


def test_prediction_output_is_clamped_and_uses_bb_path(monkeypatch, tmp_path):
    path = tmp_path / "bb_50k" / "runtime_lgbm_equity_model.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({
        "runtime_usable": True,
        "blend_alpha": 1.0,
        "feature_names": ["raw_eq"],
        "model_str": "fake",
    }), encoding="utf-8")

    class FakeBooster:
        def __init__(self, model_str):
            assert model_str == "fake"

        def predict(self, x):
            assert x.shape == (1, 1)
            return [1.40]

    monkeypatch.setattr(eqml, "_ROOT", tmp_path)
    monkeypatch.setattr(eqml, "Booster", FakeBooster)
    monkeypatch.setenv("PF_EQUITY_ML_50K", "lgbm")
    eqml.clear_caches()

    out, diag = eqml.calibrate_equity(
        0.42,
        big_blind=50_000,
        bucket_dist={"strong": 1.0},
        street="flop",
        action_ctx="bet",
        active_count=2,
        board_len=3,
        board_texture="unpaired:rainbow",
        range_pct=0.30,
        hero_bucket="strong",
    )

    assert out == 1.0
    assert diag["used"] is True
    assert diag["prediction"] == 1.0


    features = eqml._feature_values(
        0.42,
        {"strong": 0.6, "medium": 0.4},
        street="flop",
        trigger="action:bet",
        action_ctx="bet",
        active_count=2,
        board_len=3,
        board_texture="unpaired:rainbow",
        range_pct=0.30,
        hero_bucket="strong",
        strategy_version="test-version",
        experiment_profile="test-profile",
    )
    vec = eqml._vector_from_feature_names(features, FEATURE_NAMES)

    assert vec.shape == (1, len(FEATURE_NAMES))
    assert vec[0, FEATURE_NAMES.index("raw_eq")] == pytest.approx(0.42)
    assert vec[0, FEATURE_NAMES.index("p_strong")] == pytest.approx(0.6, abs=1e-5)
    assert vec[0, FEATURE_NAMES.index("p_medium")] == pytest.approx(0.4, abs=1e-5)
    assert vec[0, FEATURE_NAMES.index("board_len")] == pytest.approx(0.6)
    assert vec[0, FEATURE_NAMES.index("trigger=action:bet")] == 1.0
    assert vec[0, FEATURE_NAMES.index("action=bet")] == 1.0
    assert vec[0, FEATURE_NAMES.index("strategy_version=test-version")] == 1.0
    assert vec[0, FEATURE_NAMES.index("experiment_profile=test-profile")] == 1.0


def test_by_street_model_selects_current_street(monkeypatch, tmp_path):
    path = tmp_path / "bb_10k" / "runtime_lgbm_equity_model.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({
        "type": "equity_lgbm_calibration_by_street",
        "runtime_usable": True,
        "models_by_street": {
            "flop": {
                "runtime_usable": True,
                "blend_alpha": 1.0,
                "feature_names": ["raw_eq"],
                "model_str": "flop-model",
            },
            "turn": {
                "runtime_usable": False,
                "blend_alpha": 0.0,
                "feature_names": ["raw_eq"],
                "model_str": "turn-model",
            },
        },
    }), encoding="utf-8")

    class FakeBooster:
        def __init__(self, model_str):
            assert model_str == "flop-model"

        def predict(self, x):
            return [0.73]

    monkeypatch.setattr(eqml, "_ROOT", tmp_path)
    monkeypatch.setattr(eqml, "Booster", FakeBooster)
    monkeypatch.setenv("PF_EQUITY_ML_10K", "lgbm")
    eqml.clear_caches()

    out, diag = eqml.calibrate_equity(
        0.42,
        big_blind=10_000,
        bucket_dist={"strong": 1.0},
        street="flop",
        trigger="action:bet",
        action_ctx="bet",
        active_count=2,
        board_len=3,
        board_texture="unpaired:rainbow",
        range_pct=0.30,
        hero_bucket="strong",
    )

    assert out == pytest.approx(0.73)
    assert diag["used"] is True

    out, diag = eqml.calibrate_equity(
        0.42,
        big_blind=10_000,
        bucket_dist={"strong": 1.0},
        street="turn",
        trigger="board:turn",
        action_ctx="board",
        active_count=2,
        board_len=4,
        board_texture="unpaired:rainbow",
        range_pct=0.30,
        hero_bucket="strong",
    )

    assert out == 0.42
    assert diag["reason"] == "street_model_unusable"


def test_residual_model_adds_prediction_to_raw(monkeypatch, tmp_path):
    path = tmp_path / "bb_10k" / "runtime_lgbm_equity_model.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({
        "runtime_usable": True,
        "blend_alpha": 1.0,
        "feature_names": ["raw_eq"],
        "model_str": "fake",
        "prediction_kind": "residual",
    }), encoding="utf-8")

    class FakeBooster:
        def __init__(self, model_str):
            assert model_str == "fake"

        def predict(self, x):
            return [0.11]

    monkeypatch.setattr(eqml, "_ROOT", tmp_path)
    monkeypatch.setattr(eqml, "Booster", FakeBooster)
    monkeypatch.setenv("PF_EQUITY_ML_10K", "lgbm")
    eqml.clear_caches()

    out, diag = eqml.calibrate_equity(
        0.42,
        big_blind=10_000,
        bucket_dist={"strong": 1.0},
        street="flop",
        trigger="action:bet",
        action_ctx="bet",
        active_count=2,
        board_len=3,
        board_texture="unpaired:rainbow",
        range_pct=0.30,
        hero_bucket="strong",
    )

    assert out == pytest.approx(0.53)
    assert diag["prediction"] == pytest.approx(0.53)


def test_hero_calibrator_applies_ml_before_online_bias(monkeypatch):
    captured = {}

    def fake_calibrate_equity(raw_eq, **kwargs):
        captured.update(kwargs)
        return 0.60, {"mode": "lgbm", "used": True, "alpha": 0.5, "input": raw_eq, "prediction": 0.70, "output": 0.60}

    monkeypatch.setattr(
        "pokerfate.strategy.range_v2.hero_eq_calibrator.calibrate_equity",
        fake_calibrate_equity,
    )
    cal = HeroEquityCalibrator()
    for _ in range(10):
        cal.record("strong", "flop", 2, predicted=0.50, actual=0.62, action_ctx="bet")

    out = cal.calibrate(
        0.50,
        "strong",
        "flop",
        2,
        action_ctx="bet",
        big_blind=10_000,
        bucket_dist={"strong": 1.0},
        range_pct=0.20,
        board_len=3,
        trigger="action:bet",
        strategy_version="test-version",
        experiment_profile="test-profile",
    )

    expected_bias = 0.12 * 10 / (10 + 50)
    assert out == pytest.approx(0.60 + expected_bias)
    assert cal.last_diagnostic["formula"] == 0.50
    assert cal.last_diagnostic["ml"]["used"] is True
    assert cal.last_diagnostic["final"] == pytest.approx(out)
    assert captured["trigger"] == "action:bet"
    assert captured["strategy_version"] == "test-version"
    assert captured["experiment_profile"] == "test-profile"
