from __future__ import annotations

import json
import os

import pytest

from pf_entertainment import range_nll
from pf_entertainment.range_nll import range_nll_payload

NOW = 2_000_000_000


def _row(**over):
    row = {
        "schema": "runtime_range_calibration_v2",
        "session_id": "s1",
        "hand": 1,
        "recorded_at": NOW,
        "street": "flop",
        "player_uid": "2",
        "trigger": "action:call",
        "actual_bucket": "strong",
        "bucket_dist": {"strong": 0.60, "medium": 0.30, "air": 0.10},
        "static_combo_prob": 0.001,
        "bayes_combo_prob": 0.004,
        "nll_static": 6.907755,
        "nll_bayes": 5.521461,
    }
    row.update(over)
    return row


def _write(root, rows, name="train.rows.jsonl"):
    root.mkdir(parents=True, exist_ok=True)
    (root / name).write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    return root


def _no_robots(uid):
    return False


def test_payload_scores_bucket_calibration_and_street_updates(tmp_path):
    root = _write(tmp_path / "rows", [
        _row(),
        _row(hand=2, street="turn", player_uid="3", trigger="action:raise_over", actual_bucket="medium",
             bucket_dist={"strong": 0.70, "medium": 0.20, "air": 0.10},
             static_combo_prob=0.006, bayes_combo_prob=0.002, nll_static=5.116996, nll_bayes=6.214608),
        # Preflop rows count for the update check only: the bucket model is postflop.
        _row(hand=3, street="preflop", trigger="action:call", actual_bucket="strong"),
        # The range at the start of a hand has not been updated on anything yet.
        _row(hand=3, street="preflop", trigger="reset"),
        {"schema": "runtime_range_calibration_v2", "session_id": "s1", "hand": 4, "recorded_at": NOW},
    ])

    payload = range_nll_payload(root, since=0, is_robot=_no_robots)

    summary = payload["summary"]
    assert summary["rows"] == 5
    assert summary["hands"] == 4
    assert (summary["count"], summary["improved"], summary["worse"]) == (3, 2, 1)
    assert summary["bucket_rows"] == 2
    assert summary["strong_mass_predicted"] == pytest.approx(0.65)
    assert summary["strong_mass_actual"] == pytest.approx(0.5)
    assert [row["key"] for row in payload["by_street"]] == ["preflop", "flop", "turn"]
    assert payload["by_street"][1]["avg_delta_nll"] == pytest.approx(1.386294)

    calibration = payload["calibration"]
    assert calibration["overall"]["points"] == 6          # three live buckets per row
    assert calibration["overall"]["ece"] == summary["bucket_ece"]
    assert calibration["overall"]["bins"]
    by_bucket = {row["key"]: row for row in calibration["by_bucket"]}
    assert set(by_bucket) == {"strong", "medium", "air"}
    assert by_bucket["strong"]["avg_pred"] == pytest.approx(0.65)
    assert by_bucket["strong"]["empirical"] == pytest.approx(0.5)
    assert calibration["by_cell"] == []                   # no cell has 100 rows
    assert len(payload["conclusion"]) == 4


def test_only_rows_since_the_deployed_model_about_humans_count(tmp_path, monkeypatch):
    model = tmp_path / "model.json"
    model.write_text("{}", encoding="utf-8")
    os.utime(model, (NOW, NOW))
    monkeypatch.setattr(range_nll, "BUCKET_MODEL", model)
    root = _write(tmp_path / "rows", [
        _row(recorded_at=NOW - 1),                        # an earlier model's belief
        _row(recorded_at=NOW, player_uid="900"),          # a house robot
        _row(recorded_at=NOW),
        _row(recorded_at=NOW + 5, session_id="s2"),       # same hand number, another run
    ])

    payload = range_nll_payload(root, is_robot=lambda uid: uid == "900")

    summary = payload["summary"]
    assert summary["since"] == NOW and summary["since_model"] is True
    assert (summary["older_rows"], summary["robot_rows"], summary["rows"]) == (1, 1, 2)
    assert summary["hands"] == 2
    assert "旧版模型" in payload["conclusion"][0] and "1 行的对手是人机" in payload["conclusion"][0]

    everything = range_nll_payload(root, since=0, is_robot=lambda uid: uid == "900")["summary"]
    assert (everything["older_rows"], everything["rows"]) == (0, 3)


def test_strong_mass_cell_is_flagged_beyond_tolerance_and_noise(tmp_path):
    dist = {"nuts": 0.10, "strong": 0.20, "medium": 0.40, "air": 0.30}

    def cell(street, trigger, strong_rows, total):
        return [
            _row(hand=i, street=street, trigger=trigger, bucket_dist=dist,
                 actual_bucket="strong" if i < strong_rows else "air")
            for i in range(total)
        ]

    root = _write(tmp_path / "rows", [
        *cell("river", "action:bet", 60, 120),            # predicted 30%, held 50%
        *cell("flop", "action:check", 33, 120),           # predicted 30%, held 27.5%
        *cell("turn", "action:raise", 40, 99),            # too few rows to judge
        *cell("river", "action:fold_other", 110, 120),    # a re-emitted prediction, not a cell
    ])

    payload = range_nll_payload(root, since=0, is_robot=_no_robots)

    cells = {(c["street"], c["action"]): c for c in payload["calibration"]["by_cell"]}
    assert list(cells) == [("flop", "check"), ("river", "bet")]
    assert cells[("river", "bet")]["label"] == "underconfident"
    assert cells[("river", "bet")]["diff"] == pytest.approx(-0.20)
    assert cells[("flop", "check")]["label"] == "ok"
    assert payload["summary"]["bucket_rows"] == 459      # every row still counts overall
    assert "河牌下注低估 20.0" in payload["conclusion"][2]


def test_empty_window_says_so(tmp_path):
    root = _write(tmp_path / "rows", [_row(recorded_at=NOW - 10)])

    payload = range_nll_payload(root, since=NOW, is_robot=_no_robots)

    assert payload["summary"]["rows"] == 0 and payload["summary"]["bucket_ece"] is None
    assert payload["calibration"]["by_bucket"] == [] and payload["by_street"] == []
    assert "还没有翻后亮牌样本" in payload["conclusion"][-1]


@pytest.mark.parametrize("flags", [["--json"], []])
def test_analysis_script_runs_the_way_the_web_console_calls_it(tmp_path, monkeypatch, capsys, flags):
    from scripts import analyze_range_ece

    class Registry:
        def __init__(self, *args, **kwargs):
            assert kwargs.get("autosave") is False       # read-only

        def is_robot(self, uid):
            return False

    monkeypatch.setattr(range_nll, "RobotRegistry", Registry)
    root = _write(tmp_path / "rows", [_row()])

    analyze_range_ece.main(["--runtime-root", str(root), "--since", "2020-01-01", *flags])

    out = capsys.readouterr().out
    if flags:
        assert json.loads(out)["summary"]["rows"] == 1
    else:
        assert out.startswith("口径：") and "strong" in out
