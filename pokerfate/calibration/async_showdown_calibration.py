"""Background wrapper for live showdown calibration prediction capture.

The proxy's WSS relay runs on a single asyncio event loop.  Range prediction
capture can be CPU-heavy, so live play should enqueue immutable snapshots and
let a background worker build ``PredictionRecord`` objects.
"""

from __future__ import annotations

import logging
import queue
import threading
import time
from typing import Any, Optional

import numpy as np

from pokerfate.calibration.showdown_calibration import ShowdownCalibrator

log = logging.getLogger(__name__)


class AsyncShowdownCalibrator:
    """Serialize ShowdownCalibrator prediction work through one worker thread.

    ``record_prediction`` and ``start_hand`` are ordered exactly as submitted.
    Calls that need a complete current-hand view, such as ``record_actual`` and
    ``emit_records_for``, first drain the queue.  This keeps per-hand collection
    semantics identical to the synchronous calibrator while moving the frequent
    prediction computations off the WSS event-loop thread.
    """

    def __init__(
        self,
        logger=None,
        *,
        name: str = "showdown-calibration",
        warn_backlog: int = 50,
    ) -> None:
        self._inner = ShowdownCalibrator(logger=logger)
        self._queue: queue.Queue[tuple[str, Any]] = queue.Queue()
        self._closed = False
        self._warn_backlog = max(1, int(warn_backlog))
        self._worker = threading.Thread(
            target=self._run,
            name=name,
            daemon=True,
        )
        self._worker.start()

    def start_hand(self, hand_id: int) -> None:
        self._enqueue(("start_hand", int(hand_id)))

    def record_prediction(self, **kwargs) -> None:
        self._enqueue(("record_prediction", self._snapshot_prediction(kwargs)))

    def record_actual(self, *args, **kwargs) -> None:
        self.flush()
        self._inner.record_actual(*args, **kwargs)

    def emit_records_for(self, *args, **kwargs):
        self.flush()
        return self._inner.emit_records_for(*args, **kwargs)

    def finalize_hand_calibration(self, *args, **kwargs):
        self.flush()
        return self._inner.finalize_hand_calibration(*args, **kwargs)

    def flush(self, timeout: Optional[float] = None) -> bool:
        """Wait until all queued prediction work is done.

        ``queue.Queue`` has no timeout-aware join, so this method uses the
        queue's condition directly when a timeout is supplied.
        """
        pending_before = self._queue.qsize()
        started = time.monotonic()
        if timeout is None:
            self._queue.join()
            self._log_slow_flush(started, pending_before, completed=True)
            return True

        end_at = time.monotonic() + max(0.0, float(timeout))
        with self._queue.all_tasks_done:
            while self._queue.unfinished_tasks:
                remaining = end_at - time.monotonic()
                if remaining <= 0:
                    self._log_slow_flush(started, pending_before, completed=False)
                    return False
                self._queue.all_tasks_done.wait(remaining)
        self._log_slow_flush(started, pending_before, completed=True)
        return True

    def pending_count(self) -> int:
        return int(self._queue.qsize())

    def close(self, *, wait: bool = True, timeout: Optional[float] = 2.0) -> None:
        if self._closed:
            return
        if wait:
            self.flush(timeout=timeout)
        self._closed = True
        self._queue.put(("stop", None))
        if wait:
            self._worker.join(timeout=timeout)

    def __getattr__(self, name: str):
        return getattr(self._inner, name)

    def _enqueue(self, item: tuple[str, Any]) -> None:
        if self._closed:
            return
        self._queue.put(item)
        backlog = self._queue.qsize()
        if backlog >= self._warn_backlog and backlog % self._warn_backlog == 0:
            log.warning("[CAL_ASYNC] prediction backlog=%d", backlog)

    @staticmethod
    def _log_slow_flush(
        started: float,
        pending_before: int,
        *,
        completed: bool,
    ) -> None:
        wait_ms = (time.monotonic() - started) * 1000.0
        if wait_ms >= 500:
            log.warning(
                "[CAL_ASYNC] flush_wait_ms=%.1f pending_before=%d completed=%s",
                wait_ms,
                pending_before,
                completed,
            )

    def _run(self) -> None:
        while True:
            op, payload = self._queue.get()
            try:
                if op == "stop":
                    return
                if op == "start_hand":
                    self._inner.start_hand(payload)
                elif op == "record_prediction":
                    self._inner.record_prediction(**payload)
                else:
                    log.warning("[CAL_ASYNC] unknown op=%s", op)
            except Exception:
                log.exception("[CAL_ASYNC] worker op failed: %s", op)
            finally:
                self._queue.task_done()

    @staticmethod
    def _snapshot_prediction(kwargs: dict[str, Any]) -> dict[str, Any]:
        snap = dict(kwargs)
        weights = snap.get("weights")
        if weights is not None:
            snap["weights"] = np.array(weights, dtype=np.float64, copy=True)

        active_weights = snap.get("active_weights")
        if active_weights:
            snap["active_weights"] = {
                int(pid): np.array(w, dtype=np.float64, copy=True)
                for pid, w in active_weights.items()
                if w is not None
            }

        if snap.get("board") is not None:
            snap["board"] = list(snap["board"])
        if snap.get("hero_cards") is not None:
            snap["hero_cards"] = list(snap["hero_cards"])
        return snap
