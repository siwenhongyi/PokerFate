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


@pytest.fixture(autouse=True)
def _isolate_opponent_library(tmp_path_factory, monkeypatch):
    """The exploit layer's numeric prior takes its pool rates and neighbours from the opponent
    library, which the live bot rewrites all day: with it, a test's outcome moves with the day's
    play.  Tests see no library (the built-in pool rates) unless they bring one of their own."""
    import pokerfate.decision.opponent_numeric_prior as numeric_prior

    monkeypatch.setattr(numeric_prior, "MODEL_DIR", tmp_path_factory.mktemp("local_models"))
    numeric_prior._load_model.cache_clear()
    yield
    numeric_prior._load_model.cache_clear()


@pytest.fixture(autouse=True)
def _formula_layer_without_fitted_corrections(monkeypatch):
    """Tests run without the fitted postflop likelihood — it is data that changes with every
    refit — so postflop actions do not move ranges unless a test points PF_FORMULA_FIT_PATH at
    a model of its own (tests/test_fit_likelihood_model.py covers the fit and the deployed file)."""
    monkeypatch.setenv("PF_FORMULA_FIT_PATH", "off")


@pytest.fixture(autouse=True)
def _client_tables_are_the_installers(monkeypatch):
    """Tests read the client's tables as the repository has them (the installer's, output/), never
    the hot update this machine synced (remote_res/, git-ignored), so they pass alike everywhere."""
    from pf_reverse import tables

    monkeypatch.setattr(tables.TABLES, "roots", [tables.TPL])
    monkeypatch.setattr(tables.TABLES, "manifest", None)
