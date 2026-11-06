from __future__ import annotations

import json

from pf_entertainment.range_nll import range_nll_payload


def test_range_nll_payload_analyzes_runtime_rows(tmp_path):
    root = tmp_path / "runtime_calibration"
    out = root / "bb_10k"
    out.mkdir(parents=True)
    rows = [
        {
            "schema": "runtime_range_calibration_v2",
            "hand": 77,
            "street": "flop",
            "player_uid": "2",
            "player_name": "villain-a",
            "trigger": "action:call",
            "actual_cards": ["Ac", "Kd"],
            "actual_combo": "AcKd",
            "actual_bucket": "strong",
            "bucket_dist": {"strong": 0.60, "medium": 0.30, "air": 0.10},
            "bet_size_bucket": "half",
            "action_bet_ratio": 0.50,
            "static_combo_prob": 0.001,
            "bayes_combo_prob": 0.004,
            "nll_static": 6.907755,
            "nll_bayes": 5.521461,
            "delta_nll": 1.386294,
            "nll_source": "exact_showdown",
        },
        {
            "schema": "runtime_range_calibration_v2",
            "hand": 88,
            "street": "turn",
            "player_uid": "3",
            "player_name": "villain-b",
            "trigger": "action:raise",
            "actual_cards": ["Qs", "Qh"],
            "actual_combo": "QhQs",
            "actual_bucket": "medium",
            "bucket_dist": {"strong": 0.70, "medium": 0.20, "air": 0.10},
            "bet_size_bucket": "pot",
            "action_bet_ratio": 1.00,
            "is_raise_over": True,
            "static_combo_prob": 0.006,
            "bayes_combo_prob": 0.002,
            "nll_static": 5.116996,
            "nll_bayes": 6.214608,
            "delta_nll": -1.097612,
            "nll_source": "exact_showdown",
        },
        {"schema": "runtime_range_calibration_v2", "hand": 99},
    ]
    (out / "train.rows.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )

    payload = range_nll_payload(root)

    summary = payload["summary"]
    assert summary["count"] == 2
    assert summary["rows"] == 3
    assert summary["skipped"] == 1
    assert summary["hands"] == 2
    assert summary["improved"] == 1
    assert summary["worse"] == 1
    assert summary["bucket_ece"] is not None
    assert summary["top_bucket_accuracy"] == 0.5
    calibration = payload["calibration"]
    assert calibration["overall"]["ece"] == summary["bucket_ece"]
    assert calibration["overall"]["bins"]
    assert {row["key"] for row in calibration["by_bucket"]} >= {"strong", "medium", "air"}
    assert {row["key"] for row in calibration["by_action"]} >= {"call", "raise"}
    assert {row["key"] for row in calibration["by_size"]} >= {"half", "pot"}
    assert calibration["hotspots"]
    cec = payload["cec_integration"]
    assert cec["overall"]["count"] == 2
    assert cec["overall"]["raw_nll"] is not None
    assert cec["overall"]["cec_nll"] is not None
    assert cec["overall"]["raw_ece"] is not None
    assert cec["overall"]["cec_ece"] is not None
    assert cec["hotspots"]
    assert payload["by_street"][0]["key"] in {"flop", "turn"}
    assert payload["examples"]["improved"][0]["actual_combo"] == "AcKd"
    assert payload["examples"]["worse"][0]["actual_combo"] == "QhQs"
