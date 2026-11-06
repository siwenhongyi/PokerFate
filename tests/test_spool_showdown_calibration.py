import json

import numpy as np

from pokerfate.calibration.spool_showdown_calibration import (
    FileSpoolRangeCompareCollector,
    FileSpoolShowdownCalibrator,
    _GB,
    _ensure_dirs,
    _maybe_monitor_spool,
    _reclaim_worker_processing,
    _target_worker_count,
    run_spool_worker_once,
    spool_backpressure_status,
)
from pokerfate.core.card import Card
from pokerfate.strategy.range_v2.hero_eq_calibrator import HeroEquityCalibrator
from pokerfate.strategy.range_v2.river_relative_calibrator import (
    RiverRelativeCalibrator,
)


def test_file_spool_worker_consumes_job_and_applies_updates(tmp_path):
    runtime_root = tmp_path / "runtime_calibration"
    spool_dir = runtime_root / "live_spool"
    cal = FileSpoolShowdownCalibrator(
        logger=None,
        big_blind=10000,
        spool_dir=spool_dir,
        runtime_root=runtime_root,
        start_worker=False,
    )

    hero = [Card.from_str("Ac"), Card.from_str("Kd")]
    board = [Card.from_str(c) for c in ["2c", "7d", "Jh", "4s", "9c"]]
    weights = np.ones(1326, dtype=np.float64)

    cal.start_hand(12)
    cal.record_prediction(
        player_id=7,
        player_name="villain",
        street="river",
        board=board,
        weights=weights,
        hero_cards=hero,
        trigger="action:call",
        active_weights={7: weights},
    )
    cal.record_actual(
        player_id=7,
        actual_cards=[Card.from_str("Qs"), Card.from_str("Qh")],
        final_board=board,
        hero_cards=hero,
    )

    assert cal.emit_records_for(player_id=7, hero_cards=hero, final_board=board) == []
    assert len(list((spool_dir / "pending").glob("*.pkl"))) == 1

    assert run_spool_worker_once(
        spool_dir=spool_dir,
        runtime_root=runtime_root,
        max_jobs=1,
    ) == 1
    assert list((spool_dir / "pending").glob("*.pkl")) == []
    assert list((spool_dir / "processing").glob("*.pkl")) == []
    assert list((spool_dir / "failed").glob("*.pkl")) == []

    row_files = list((runtime_root / "bb_10k").glob("*.rows.jsonl"))
    assert row_files
    assert sum(1 for path in row_files for _ in path.open(encoding="utf-8")) >= 1
    row = json.loads(row_files[0].read_text(encoding="utf-8").splitlines()[0])
    assert row["actual_combo"]
    assert row["nll_source"] == "exact_showdown"
    assert row["delta_nll"] is not None

    result_files = list((spool_dir / "results").glob("*.pkl"))
    assert result_files
    applied = cal.apply_pending_updates(
        HeroEquityCalibrator(),
        RiverRelativeCalibrator(),
    )
    assert applied >= 1
    assert list((spool_dir / "results").glob("*.pkl")) == []


def test_range_compare_spool_worker_writes_hand_level_row(tmp_path):
    runtime_root = tmp_path / "runtime_calibration"
    spool_dir = runtime_root / "live_spool"
    collector = FileSpoolRangeCompareCollector(
        logger=None,
        big_blind=10000,
        spool_dir=spool_dir,
        runtime_root=runtime_root,
        start_worker=False,
    )

    collector.start_hand(
        33,
        players=[
            {"player_id": 1, "name": "hero"},
            {"player_id": 2, "name": "villain"},
        ],
        hero_id=1,
    )
    collector.record_decision_snapshot({
        "decision_index": 1,
        "street": "flop",
        "opponents": [
            {
                "player_id": 2,
                "name": "villain",
                "pf_range_169": {"AKo": 0.7, "QQ": 0.3},
                "g5_range_169": {"AKo": 0.2, "QQ": 0.8},
            }
        ],
    })
    collector.record_showdown(
        shown_cards={2: ["Ac", "Kd"]},
        final_board=["2c", "3d", "4h", "5s", "9c"],
        hero_cards=["Qs", "Qh"],
    )
    collector.finalize_hand()

    assert len(list((spool_dir / "pending").glob("*.pkl"))) == 1
    assert run_spool_worker_once(
        spool_dir=spool_dir,
        runtime_root=runtime_root,
        max_jobs=1,
    ) == 1

    row_files = list((runtime_root / "bb_10k").glob("range_compare.*.jsonl"))
    assert len(row_files) == 1
    row = json.loads(row_files[0].read_text(encoding="utf-8").strip())
    assert row["schema"] == "runtime_range_compare_169_v1"
    assert row["hand_id"] == 33
    assert len(row["snapshots"]) == 1
    comparison = row["comparisons"][0]
    assert comparison["actual_category"] == "AKo"
    assert comparison["pf_prob"] == 0.7
    assert comparison["g5_prob"] == 0.2
    assert comparison["pf_rank"] == 1
    assert comparison["g5_rank"] == 2


def test_target_worker_count_uses_backlog_to_drain():
    stats = {
        "pending_count": 48,
        "backlog_count": 49,
        "backlog_bytes": 22 * _GB,
    }

    target = _target_worker_count(
        stats=stats,
        production_bytes_per_sec=6 * 1024 * 1024,
        worker_bytes_per_sec=2 * 1024 * 1024,
        min_workers=1,
        max_workers=8,
        drain_sec=3600,
    )

    assert target >= 6
    assert target <= 8


def test_worker_processing_reclaim_restores_original_pending_name(tmp_path):
    dirs = _ensure_dirs(tmp_path / "spool")
    path = dirs["processing"] / "w3__hand_7_123_456.pkl"
    path.write_bytes(b"x")

    assert _reclaim_worker_processing(dirs, worker_id="w3") == 1
    assert not path.exists()
    assert (dirs["pending"] / "hand_7_123_456.pkl").read_bytes() == b"x"


def test_monitor_pause_threshold_writes_backpressure_without_killing(tmp_path, monkeypatch):
    dirs = _ensure_dirs(tmp_path / "spool")
    killed = []
    monkeypatch.setattr(
        "pokerfate.calibration.spool_showdown_calibration.os.kill",
        lambda pid, sig: killed.append((pid, sig)),
    )

    should_stop_parent = _maybe_monitor_spool(
        dirs=dirs,
        stats={
            "backlog_bytes": 51 * _GB,
            "pending_count": 3,
            "processing_count": 1,
            "oldest_pending_age_sec": 600,
            "disk_free_bytes": 200 * _GB,
        },
        active_workers=8,
        target_workers=8,
        warn_gb=20,
        stop_gb=50,
        parent_pid=12345,
        key_file=tmp_path / "missing_bark_key.txt",
        parent_stop_requested=False,
    )

    assert should_stop_parent is True
    assert killed == []
    status = spool_backpressure_status(tmp_path / "spool")
    assert status["active"] is True
    assert status["level"] == "pause"
    assert status["pending_count"] == 3


def test_monitor_clears_backpressure_below_warn_threshold(tmp_path):
    dirs = _ensure_dirs(tmp_path / "spool")
    (tmp_path / "spool" / "backpressure.json").write_text(
        '{"active": true, "level": "pause"}\n',
        encoding="utf-8",
    )

    active = _maybe_monitor_spool(
        dirs=dirs,
        stats={
            "backlog_bytes": 5 * _GB,
            "pending_count": 0,
            "processing_count": 0,
            "oldest_pending_age_sec": 0,
            "disk_free_bytes": 200 * _GB,
        },
        active_workers=1,
        target_workers=1,
        warn_gb=20,
        stop_gb=50,
        parent_pid=12345,
        key_file=tmp_path / "missing_bark_key.txt",
        parent_stop_requested=False,
    )

    assert active is False
    status = spool_backpressure_status(tmp_path / "spool")
    assert status["active"] is False
    assert status["level"] == "ok"
