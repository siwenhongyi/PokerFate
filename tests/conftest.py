"""Shared test fixtures."""

from __future__ import annotations

import pytest

import pokerfate.calibration.runtime_recorder as runtime_recorder
import pokerfate.calibration.spool_showdown_calibration as spool_calibration


@pytest.fixture(autouse=True)
def _isolate_runtime_calibration_writes(tmp_path_factory, monkeypatch):
    """Keep test hands out of the real data/runtime_calibration training rows."""
    root = tmp_path_factory.mktemp("runtime_calibration")
    monkeypatch.setattr(runtime_recorder, "_default_root", lambda: root)
    monkeypatch.setattr(spool_calibration, "_default_runtime_root", lambda: root)


@pytest.fixture(autouse=True)
def _isolate_g5_shadow_worker(monkeypatch):
    """Ordinary tests must not launch the native G5 worker or read live model data."""
    from pf_intercept import config
    monkeypatch.setenv("PF_G5_SHADOW_ENABLED", "0")
    monkeypatch.setattr(config, "PF_G5_SHADOW_ENABLED", False)


@pytest.fixture(autouse=True)
def _isolate_robot_registry(tmp_path_factory, monkeypatch):
    """Tests must neither read nor grow the real robot registry / table-selection log."""
    import pokerfate.core.robots as robots
    import pf_intercept.bot as bridge_mod

    root = tmp_path_factory.mktemp("robots")
    monkeypatch.delenv("PF_ROBOT_REGISTRY", raising=False)
    monkeypatch.setattr(robots, "_default", robots.RobotRegistry(root / "robots.json", autosave=False))
    monkeypatch.setattr(bridge_mod, "_TABLE_LOG_PATH", root / "table_select.jsonl")
