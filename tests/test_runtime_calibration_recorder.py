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
        position="BTN",
        is_ip=True,
        facing_action="open",
        preflop_action_type="3bet",
        action_bet_ratio=2.5,
        bet_size_bucket="huge",
        is_raise_over=True,
        action_sequence="preflop:raise|flop:call",
        board_features={"paired": False, "flush_draw": True, "wetness": 0.4},
        hero_draw={"flush_draw": True, "oesd": False},
        hero_blockers={"nut_flush_blocker": True},
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
        actual_combo="AdQd",
        actual_combo_index=123,
        static_combo_prob=0.001,
        bayes_combo_prob=0.004,
        nll_static=6.907755,
        nll_bayes=5.521461,
        delta_nll=1.386294,
        nll_source="exact_showdown",
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
    assert row["schema"] == "runtime_range_calibration_v2"
    assert row["bb_bucket"] == "bb_50k"
    assert row["split"] == "train"
    assert row["actual_bucket"] == "strong"
    assert row["actual_combo"] == "AdQd"
    assert row["actual_combo_index"] == 123
    assert row["static_combo_prob"] == 0.001
    assert row["bayes_combo_prob"] == 0.004
    assert row["nll_static"] == 6.907755
    assert row["nll_bayes"] == 5.521461
    assert row["delta_nll"] == 1.386294
    assert row["nll_source"] == "exact_showdown"
    assert row["bucket_dist"]["strong"] == 0.4
    assert row["active_player_count"] == 2
    assert row["strategy_version"]
    assert row["experiment_flags"]["PF_TURN_FLOP_RELATIVE_GUARD"] == "1"
    assert row["experiment_flags"]["PF_BUCKET_CALIBRATION"] == "1"
    assert row["position"] == "BTN"
    assert row["is_ip"] is True
    assert row["facing_action"] == "open"
    assert row["preflop_action_type"] == "3bet"
    assert row["action_bet_ratio"] == 2.5
    assert row["bet_size_bucket"] == "huge"
    assert row["is_raise_over"] is True
    assert row["action_sequence"] == "preflop:raise|flop:call"
    assert row["player_uid"] == "11"
    assert row["player_name"] == "villain"
    assert "player" not in row
    assert "player_id" not in row
    assert "active_player_ids" not in row
    assert row["board_features"]["flush_draw"] is True
    assert row["hero_draw"]["flush_draw"] is True
    assert row["hero_blockers"]["nut_flush_blocker"] is True
    assert "player_profile" not in row
    assert "range_summary" not in row
    assert "action_diagnostics" not in row
    assert "range_snapshot" not in row
    assert "active_range_summaries" not in row


def test_runtime_calibration_recorder_writes_river_value_sizing_rows(tmp_path):
    recorder = RuntimeCalibrationRecorder(
        root=tmp_path,
        session_id="test-session",
        val_ratio=0.0,
    )

    written = recorder.write_river_value_sizing(
        {
            "street": "river",
            "purpose": "overbet_value",
            "amount_added": 62500,
            "bet_frac_pot": 1.25,
            "response_kind": "called",
            "paid": True,
            "my_delta_bb": 18.5,
            "villain_vs_hero_dist": {"win": 0.98, "tie": 0.0, "loss": 0.02},
        },
        big_blind=50000,
        hand_id=43,
    )

    assert written == 1
    row_path = tmp_path / "bb_50k" / "river_value_sizing.train.jsonl"
    rows = [json.loads(line) for line in row_path.read_text().splitlines()]
    assert len(rows) == 1
    row = rows[0]
    assert row["schema"] == "runtime_river_value_sizing_v1"
    assert row["bb_bucket"] == "bb_50k"
    assert row["split"] == "train"
    assert row["hand"] == 43
    assert row["purpose"] == "overbet_value"
    assert row["paid"] is True
    assert row["villain_vs_hero_dist"]["win"] == 0.98
