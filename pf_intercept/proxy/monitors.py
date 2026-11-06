from __future__ import annotations

import logging
import os
import subprocess

from pokerfate.calibration.spool_showdown_calibration import ensure_spool_worker_process

log = logging.getLogger("pf_proxy")

_CAL_SPOOL_PROC: subprocess.Popen | None = None


def start_calibration_spool_worker() -> None:
    global _CAL_SPOOL_PROC
    if _CAL_SPOOL_PROC is not None and _CAL_SPOOL_PROC.poll() is None:
        return
    try:
        _CAL_SPOOL_PROC = ensure_spool_worker_process(parent_pid=os.getpid())
    except Exception as exc:
        log.warning("[cal spool] start failed: %s", exc)
        print(f"[proxy] 校准消费 worker 启动失败: {type(exc).__name__}: {exc}")
        _CAL_SPOOL_PROC = None
        return

    if _CAL_SPOOL_PROC is None:
        log.warning("[cal spool] start returned no process")
        print("[proxy] 校准消费 worker 未启动")
        return
    log.info(
        "[cal spool] worker supervisor started pid=%s",
        _CAL_SPOOL_PROC.pid,
    )
    print(f"[proxy] 校准消费 worker 已启动  pid={_CAL_SPOOL_PROC.pid}")


def stop_calibration_spool_worker() -> None:
    global _CAL_SPOOL_PROC
    proc = _CAL_SPOOL_PROC
    _CAL_SPOOL_PROC = None
    if proc is None:
        return
    if proc.poll() is not None:
        return
    if not hasattr(proc, "terminate") or not hasattr(proc, "wait"):
        log.info(
            "[cal spool] worker pid=%s is not a child process; leave lifecycle to owner",
            getattr(proc, "pid", "?"),
        )
        return
    print(f"[proxy] 停止 校准消费 worker (pid={proc.pid})")
    try:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=3)
    except Exception as exc:
        log.warning("[cal spool] stop failed pid=%s: %s", getattr(proc, "pid", "?"), exc)
