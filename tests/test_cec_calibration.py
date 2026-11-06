import json

from pokerfate.strategy.range_v2.cec_calibration import (
    _MODEL_CACHE,
    calibrate_range_v2_prior,
    load_cec_model,
)


def test_cec_calibration_builds_runtime_view(tmp_path):
    root = tmp_path / "runtime_calibration"
    out = root / "bb_10k"
    out.mkdir(parents=True)
    rows = []
    for idx in range(90):
        rows.append({
            "street": "river",
            "trigger": "action:check",
            "actual_bucket": "air" if idx < 45 else "medium",
            "bucket_dist": {
                "nuts": 0.05,
                "strong": 0.60,
                "medium": 0.20,
                "draw": 0.0,
                "weak_draw": 0.0,
                "air": 0.15,
            },
            "bet_size_bucket": "check",
            "action_bet_ratio": 0.0,
            "bb": 10000,
        })
    (out / "train.rows.jsonl").write_text(
        "".join(json.dumps(row) + "\n" for row in rows),
        encoding="utf-8",
    )

    _MODEL_CACHE.clear()
    model = load_cec_model(big_blind=10000, runtime_root=root, blocking=True)
    assert model.bb_bucket == "all_bb"
    assert model.rows == 90
    assert model.groups["line"]["river|check|check|single"].rows == 90

    prior = {
        "bucket_dist": {
            "nuts": 0.05,
            "strong": 0.60,
            "medium": 0.20,
            "draw": 0.0,
            "weak_draw": 0.0,
            "air": 0.15,
        },
        "action_context": {
            "street": "river",
            "action": "check",
            "bet_ratio": 0.0,
            "is_raise_over": False,
        },
    }
    calibrated = calibrate_range_v2_prior(
        prior,
        big_blind=10000,
        runtime_root=root,
        blocking=True,
    )

    assert calibrated["cec_calibration"]["source"] == "runtime_cec"
    assert calibrated["cec_calibration"]["level"] == "line"
    assert calibrated["raw_bucket_dist"]["strong"] == 0.60
    assert calibrated["bucket_dist"]["strong"] < calibrated["raw_bucket_dist"]["strong"]
    assert calibrated["bucket_dist"]["air"] > calibrated["raw_bucket_dist"]["air"]


def test_cec_calibration_default_load_is_nonblocking(tmp_path):
    _MODEL_CACHE.clear()
    root = tmp_path / "runtime_calibration"
    (root / "bb_10k").mkdir(parents=True)
    model = load_cec_model(big_blind=10000, runtime_root=root)
    assert model.bb_bucket == "all_bb"
    assert model.rows == 0


def test_cec_calibration_incremental_refresh_reads_appended_rows(tmp_path):
    _MODEL_CACHE.clear()
    root = tmp_path / "runtime_calibration"
    out = root / "bb_10k"
    out.mkdir(parents=True)
    path = out / "train.rows.jsonl"
    row = {
        "street": "turn",
        "trigger": "action:bet",
        "actual_bucket": "nuts",
        "bucket_dist": {
            "nuts": 0.10,
            "strong": 0.30,
            "medium": 0.30,
            "draw": 0.10,
            "weak_draw": 0.10,
            "air": 0.10,
        },
        "bet_size_bucket": "half",
        "action_bet_ratio": 0.5,
    }
    path.write_text(json.dumps(row) + "\n", encoding="utf-8")
    model = load_cec_model(big_blind=50000, runtime_root=root, blocking=True)
    assert model.rows == 1

    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({**row, "actual_bucket": "air"}) + "\n")
    model = load_cec_model(big_blind=1000, runtime_root=root, blocking=True)
    assert model.bb_bucket == "all_bb"
    assert model.rows == 2
    assert model.groups["line"]["turn|bet|half|single"].rows == 2
