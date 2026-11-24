"""Shared test fixtures."""

from __future__ import annotations

import ipaddress
import os
import socket
import threading
import urllib.request

import pytest

import pokerfate.calibration.runtime_recorder as runtime_recorder
import pokerfate.calibration.spool_showdown_calibration as spool_calibration

_refused: list[str] = []  # every outside connection or lookup refused in this run, in order


def _this_machine(host) -> bool:
    if isinstance(host, bytes):
        host = host.decode("ascii", "replace")
    if not host or host == "localhost":
        return True
    try:
        address = ipaddress.ip_address(str(host).partition("%")[0])
    except ValueError:
        return False  # any other name would have to be looked up
    return address.is_loopback or address.is_unspecified


def pytest_configure(config):
    """For the whole run, TCP connections and name lookups reach this machine only.

    The live bot shares this checkout, its credential files and its servers' addresses, so code
    under test that is not isolated would talk to the real game.  The guard stays on until the
    process exits: a worker thread that outlives its test is refused as well."""
    connect, connect_ex, getaddrinfo = socket.socket.connect, socket.socket.connect_ex, socket.getaddrinfo

    def refuse(kind: str, host) -> str:
        _refused.append(f"{kind} {host}")
        return f"tests reach this machine only: {kind} {host} refused"

    def outside(sock, address) -> bool:
        return sock.family in (socket.AF_INET, socket.AF_INET6) and not _this_machine(address[0])

    def guarded_connect(sock, address):
        if outside(sock, address):
            raise OSError(refuse("connect", address[0]))
        return connect(sock, address)

    def guarded_connect_ex(sock, address):
        if outside(sock, address):
            raise OSError(refuse("connect", address[0]))
        return connect_ex(sock, address)

    def guarded_getaddrinfo(host, *args, **kwargs):
        if not _this_machine(host):
            raise socket.gaierror(refuse("resolve", host))
        return getaddrinfo(host, *args, **kwargs)

    socket.socket.connect = guarded_connect
    socket.socket.connect_ex = guarded_connect_ex
    socket.getaddrinfo = guarded_getaddrinfo

    # A proxy on this machine would carry a request outside through a local port, unseen by the
    # checks above.  For the run no proxy comes from the shell or the system settings, so every
    # request connects directly and is refused; a test that needs a proxy sets one itself.
    for name in list(os.environ):
        if name.lower().endswith("_proxy") and name.lower() != "no_proxy":
            del os.environ[name]
    for reader in ("getproxies_macosx_sysconf", "getproxies_registry"):
        if hasattr(urllib.request, reader):
            setattr(urllib.request, reader, lambda: {})


@pytest.fixture(autouse=True)
def _nothing_leaves_this_machine():
    """A test fails when something was refused while it ran, even if the code under test
    swallowed the error.  A worker thread left running by an earlier test is counted here too."""
    seen = len(_refused)
    yield
    if len(_refused) > seen:
        pytest.fail("tried to reach another machine: " + ", ".join(sorted(set(_refused[seen:]))))


@pytest.fixture(autouse=True)
def _isolate_runtime_calibration_writes(tmp_path_factory, monkeypatch):
    """Keep test hands out of the real local/training training rows."""
    root = tmp_path_factory.mktemp("runtime_calibration")
    monkeypatch.setattr(runtime_recorder, "_default_root", lambda: root)
    monkeypatch.setattr(spool_calibration, "_default_runtime_root", lambda: root)


@pytest.fixture(autouse=True)
def _isolate_game_http(monkeypatch, _nothing_leaves_this_machine):
    """No test reaches the game's HTTP API.  A bridge that sees a seat asks for that player's
    statistics on a worker thread, and without a session of its own it would send the real
    account's credential file to the real server."""
    import pf_intercept.bot as bridge_mod

    monkeypatch.setattr(bridge_mod, "load_auth_token", lambda: "test-token")
    monkeypatch.setattr(bridge_mod, "_sync_fetch", lambda *args, **kwargs: None)
    yield
    # Finish request workers before monkeypatch restores the real functions, and before the
    # check for refused connections.
    for thread in threading.enumerate():
        if thread.name.startswith("pf-gamedata-"):
            thread.join(timeout=2.0)


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


@pytest.fixture(autouse=True)
def _lobby_ignores_are_the_projects(monkeypatch):
    """Tests never read or write the user's own ignore list (local/state/lobby_ignores.json)."""
    from pf_intercept.headless.lobby.core import ignore

    monkeypatch.setattr(ignore.IGNORES, "external_path", None)
