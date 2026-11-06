from scripts.fit_range_calibration_v2 import _eq_pairs, _eq_raw


def test_v2_relative_training_skips_old_rows_and_accepts_new_rows():
    old_row = {
        "street": "river",
        "predicted_hero_eq_multi": 0.6,
        "actual_hero_eq_street_multi": 1.0,
    }
    new_row = {
        "street": "river",
        "predicted_relation_eq": 0.25,
        "actual_relation": "loss",
        "villain_vs_hero_dist": {"win": 0.2, "tie": 0.1, "loss": 0.7},
    }

    rows = _eq_pairs([old_row, new_row], target="relative")

    assert rows == [new_row]
    assert _eq_raw(new_row, "relative") == (0.25, 0.0)
