"""Persistent realtime-CFR solver worker: reuse across solves and recovery after a timeout."""

import json
import os

import pytest

from pokerfate.decision import realtime_cfr as rc


pytestmark = pytest.mark.skipif(
    rc._resolve_solver_lib_path(None) is None, reason="pf_solver extension not built"
)


def _tiny_args():
    state = rc.RealtimeCFRState(
        board="AsKd2c7h9s", oop_range="QQ,JJ,TT", ip_range="AA,KK,88",
        pot_bb=10.0, effective_stack_bb=10.0, prefix=[],
    )
    args, _expect = rc._build_solver_args(state, 5.0, 20)
    return json.dumps(args)


def test_worker_is_reused_between_solves():
    client = rc._SolverClient()
    try:
        lib = rc._resolve_solver_lib_path(None)
        status, msg, meta = client.solve(_tiny_args(), 0, lib, 30.0)
        assert status == "ok" and msg.get("ok"), msg
        assert meta["reused"] is False
        status2, msg2, meta2 = client.solve(_tiny_args(), 0, lib, 30.0)
        assert status2 == "ok" and msg2.get("ok"), msg2
        assert meta2["reused"] is True
        assert meta2["start_ms"] < 50.0
        assert json.loads(msg["result"]).get("nodes") is not None
    finally:
        client.shutdown()


def _heavy_args():
    wide = "22+,A2s+,A2o+,K2s+,K2o+,Q2s+,Q2o+,J2s+,J2o+,T2s+,T2o+,92s+,92o+,82s+,82o+"
    state = rc.RealtimeCFRState(
        board="AsKd2c7h", oop_range=wide, ip_range=wide,
        pot_bb=10.0, effective_stack_bb=100.0, prefix=[],
    )
    args, _expect = rc._build_solver_args(state, 0.05, 2000)
    return json.dumps(args)


def test_timeout_terminates_worker_and_next_solve_recovers():
    client = rc._SolverClient()
    try:
        lib = rc._resolve_solver_lib_path(None)
        status, _msg, meta = client.solve(_heavy_args(), 0, lib, 0.01)
        assert status in {"timeout", "exited"}
        assert client._proc is None
        status2, msg2, meta2 = client.solve(_tiny_args(), 0, lib, 30.0)
        assert status2 == "ok" and msg2.get("ok"), msg2
        assert meta2["reused"] is False
    finally:
        client.shutdown()


def test_solve_realtime_cfr_reports_worker_reuse():
    state = rc.RealtimeCFRState(
        board="AsKd2c7h9s", oop_range="QQ,JJ,TT", ip_range="AA,KK,88",
        pot_bb=10.0, effective_stack_bb=10.0, prefix=[],
    )
    first = rc.solve_realtime_cfr(state, accuracy=5.0, max_iterations=20, timeout_sec=30.0)
    second = rc.solve_realtime_cfr(state, accuracy=5.0, max_iterations=20, timeout_sec=30.0)
    assert first is not None and second is not None, rc.solve_realtime_cfr.last_error
    assert second["timing"]["worker_reused"] is True
    assert second["timing"]["worker_start_ms"] < 50.0
