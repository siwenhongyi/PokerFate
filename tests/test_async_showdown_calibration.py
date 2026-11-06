import numpy as np

from pokerfate.calibration.async_showdown_calibration import AsyncShowdownCalibrator
from pokerfate.core.card import Card


def test_async_calibrator_drains_predictions_before_emit():
    cal = AsyncShowdownCalibrator(logger=None, warn_backlog=999)
    try:
        board = [
            Card.from_str("2c"),
            Card.from_str("7d"),
            Card.from_str("Jh"),
            Card.from_str("4s"),
            Card.from_str("9c"),
        ]
        cal.start_hand(12)
        cal.record_prediction(
            player_id=7,
            player_name="villain",
            street="preflop",
            board=[],
            weights=np.ones(1326, dtype=np.float64),
            hero_cards=None,
            trigger="reset",
        )
        cal.record_actual(
            player_id=7,
            actual_cards=[Card.from_str("As"), Card.from_str("Kd")],
            final_board=board,
            hero_cards=None,
        )

        results = cal.emit_records_for(
            player_id=7,
            hero_cards=None,
            final_board=board,
        )

        assert len(results) == 1
        assert results[0].record.hand_id == 12
        assert results[0].record.player_id == 7
    finally:
        cal.close()
