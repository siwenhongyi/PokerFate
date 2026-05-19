from pokerfate.strategy.range_v2.river_relative_calibrator import (
    RiverRelativeCalibrator,
    action_ctx_from_decision,
    relation_eq,
)


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
