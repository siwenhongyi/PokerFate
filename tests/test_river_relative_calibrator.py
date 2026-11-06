from pokerfate.strategy.range_v2.river_relative_calibrator import (
    RiverRelativeCalibrator,
    action_ctx_from_decision,
    clamp_equity_to_bounds,
    exact_relation_bounds,
    relation_eq,
)
from pokerfate.strategy.range_v2 import river_relative_ml_calibration as relml
from pokerfate.core.card import Card


def _cards(*names):
    return [Card.from_str(name) for name in names]


def test_river_relative_calibrator_shifts_win_loss_mass_after_samples():
    cal = RiverRelativeCalibrator()
    raw = {"win": 0.60, "tie": 0.10, "loss": 0.30}
    for _ in range(12):
        cal.record(
            hero_bucket="strong",
            hero_made_subtype="board_pair_hero_pair",
            board_texture="paired:rainbow",
            action_ctx="raise",
            predicted_dist=raw,
            actual_relation="loss",
        )

    out = cal.calibrate_dist(
        raw,
        hero_bucket="strong",
        hero_made_subtype="board_pair_hero_pair",
        board_texture="paired:rainbow",
        action_ctx="raise",
    )

    assert out["tie"] == raw["tie"]
    assert relation_eq(out) < relation_eq(raw)
    assert out["loss"] > raw["loss"]
    assert cal.last_diagnostic["used"] is True


def test_river_relative_calibrator_no_samples_is_identity():
    cal = RiverRelativeCalibrator()
    raw = {"win": 0.38, "tie": 0.12, "loss": 0.50}

    out = cal.calibrate_dist(
        raw,
        hero_bucket="strong",
        hero_made_subtype="board_pair_hero_pair",
        board_texture="paired:rainbow",
        action_ctx="raise",
    )

    assert out == raw
    assert cal.last_diagnostic["used"] is False


def test_action_context_treats_raise_over_as_raise():
    assert action_ctx_from_decision(
        facing_bet=True,
        to_call=1,
        pot=100,
        observed_action="raise_over",
    ) == "raise"


def test_exact_lock_hand_is_not_calibrated_down():
    cal = RiverRelativeCalibrator()
    raw = {"win": 1.0, "tie": 0.0, "loss": 0.0}
    for _ in range(20):
        cal.record(
            hero_bucket="nuts",
            hero_made_subtype="flush",
            board_texture="unpaired:fd",
            action_ctx="passive",
            predicted_dist=raw,
            actual_relation="loss",
        )

    bounds = exact_relation_bounds(
        _cards("Kc", "4c"),
        _cards("6h", "Ac", "Qd", "9c", "2c"),
    )
    out = cal.calibrate_dist(
        raw,
        hero_bucket="nuts",
        hero_made_subtype="flush",
        board_texture="unpaired:fd",
        action_ctx="passive",
        exact_bounds=bounds,
    )

    assert out == {"win": 1.0, "tie": 0.0, "loss": 0.0}
    assert clamp_equity_to_bounds(0.95, bounds) == 1.0
    assert cal.last_diagnostic["hard_bound"] is True


def test_river_relative_ml_runs_before_online_bias(monkeypatch, tmp_path):
    path = tmp_path / "all_bb" / "runtime_lgbm_relative_model.json"
    path.parent.mkdir(parents=True)
    path.write_text(
        """
        {
          "runtime_usable": true,
          "blend_alpha": 1.0,
          "feature_names": ["raw_eq"],
          "model_str": "fake"
        }
        """,
        encoding="utf-8",
    )

    class FakeBooster:
        def __init__(self, model_str):
            assert model_str == "fake"

        def predict(self, x):
            assert x.shape == (1, 1)
            return [0.80]

    monkeypatch.setattr(relml, "_ROOT", tmp_path)
    monkeypatch.setattr(relml, "Booster", FakeBooster)
    monkeypatch.setenv("PF_RIVER_RELATIVE_ML", "lgbm")
    relml.clear_caches()

    cal = RiverRelativeCalibrator()
    raw = {"win": 0.40, "tie": 0.10, "loss": 0.50}
    for _ in range(12):
        cal.record(
            hero_bucket="strong",
            hero_made_subtype="pair",
            board_texture="unpaired:rainbow",
            action_ctx="passive",
            predicted_dist=raw,
            actual_relation="loss",
        )

    out = cal.calibrate_dist(
        raw,
        hero_bucket="strong",
        hero_made_subtype="pair",
        board_texture="unpaired:rainbow",
        action_ctx="passive",
        big_blind=10_000,
        bucket_dist={"strong": 0.7, "medium": 0.3},
        active_count=2,
        range_pct=0.25,
    )

    assert cal.last_diagnostic["ml"]["used"] is True
    assert cal.last_diagnostic["used"] is True
    assert relation_eq(out) > relation_eq(raw)
    assert relation_eq(out) < 0.80
