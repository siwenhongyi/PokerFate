import json

from pokerfate.calibration.runtime_recorder import RuntimeCalibrationRecorder
from pokerfate.calibration.showdown_calibration import (
    CalibrationResult,
    PredictionRecord,
)
from pokerfate.core.card import Card


def test_runtime_calibration_recorder_writes_bb_split_rows(tmp_path):
    board = [Card.from_str(c) for c in ["Ah", "Kd", "7c"]]
    rec = PredictionRecord(
        hand_id=7,
        street="flop",
        player_id=11,
        player_name="villain",
        board=board,
        trigger="action:call",
        range_pct=0.42,
        bucket_dist={"strong": 0.4, "medium": 0.4, "air": 0.2},
        hero_cards=[Card.from_str("As"), Card.from_str("Qs")],
        predicted_hero_eq=0.55,
        predicted_hero_eq_multi=0.48,
        active_player_ids=[11, 12],
        hero_bucket="medium",
    )
    result = CalibrationResult(
        record=rec,
        actual_cards=[Card.from_str("Ad"), Card.from_str("Qd")],
        actual_bucket="strong",
        predicted_bucket_prob=0.4,
        actual_hero_eq_street=0.5,
        eq_prediction_error_street=0.05,
        actual_hero_eq_final=1.0,
        eq_prediction_error=-0.45,
        actual_hero_eq_street_multi=0.44,
        eq_prediction_error_street_multi=0.04,
        actual_hero_eq_street_multi_shown=0.5,
    )
    recorder = RuntimeCalibrationRecorder(
        root=tmp_path,
        session_id="test-session",
        val_ratio=0.0,
    )

    written = recorder.write_results(
        [result],
        big_blind=50000,
        final_board=board + [Card.from_str("2d"), Card.from_str("3s")],
    )

    assert written == 1
    row_path = tmp_path / "bb_50k" / "train.rows.jsonl"
    rows = [json.loads(line) for line in row_path.read_text().splitlines()]
    assert len(rows) == 1
    row = rows[0]
    assert row["bb_bucket"] == "bb_50k"
    assert row["split"] == "train"
    assert row["actual_bucket"] == "strong"
    assert row["bucket_dist"]["strong"] == 0.4
    assert row["active_player_count"] == 2
