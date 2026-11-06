"""File-spooled showdown calibration for live play.

The WSS relay must not wait for showdown calibration math.  This wrapper keeps
the public ``ShowdownCalibrator`` call shape, but live code only records cheap
snapshots and writes one completed-hand job to disk.  A separate worker process
replays the job with the normal synchronous calibrator, writes runtime rows,
then leaves a small update file for the bot process to consume.
"""

from __future__ import annotations

import argparse
import json
import math
import multiprocessing
import os
import pickle
import signal
import shutil
import subprocess
import sys
import time
import traceback
from collections import deque
from pathlib import Path
from queue import Empty
from typing import Any, Deque, Optional

import numpy as np

from pf_notify.client import notify
from pf_notify.config import load_bark_key_file, set_bark_key
from pokerfate.calibration.runtime_recorder import RuntimeCalibrationRecorder
from pokerfate.calibration.showdown_calibration import (
    CalibrationResult,
    ShowdownCalibrator,
)
from pokerfate.strategy.range_v2.hero_eq_calibrator import (
    classify_action_ctx_from_trigger,
)


_SPOOL_SCHEMA = "showdown_calibration_spool_v1"
_RANGE_COMPARE_SPOOL_SCHEMA = "range_compare_169_spool_v1"
_UPDATE_SCHEMA = "showdown_calibration_updates_v1"
_GB = 1024 ** 3
_DEFAULT_MIN_WORKERS = 1
_DEFAULT_DRAIN_SEC = 3600.0
_DEFAULT_WARN_GB = 20.0
_DEFAULT_STOP_GB = 50.0
_BACKPRESSURE_FILE = "backpressure.json"
_SUPERVISOR_PID_FILE = "supervisor.pid"
_SUPERVISOR_STATUS_FILE = "supervisor_status.json"
_SHARED_WORKERS: dict[tuple[str, str], dict[str, Any]] = {}


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _default_runtime_root() -> Path:
    return _repo_root() / "data" / "runtime_calibration"


def _default_spool_dir() -> Path:
    return _default_runtime_root() / "live_spool"


def _spool_dirs(spool_dir: Path | str) -> dict[str, Path]:
    root = Path(spool_dir)
    return {
        "root": root,
        "pending": root / "pending",
        "processing": root / "processing",
        "results": root / "results",
        "failed": root / "failed",
    }


def _ensure_dirs(spool_dir: Path | str) -> dict[str, Path]:
    dirs = _spool_dirs(spool_dir)
    for path in dirs.values():
        path.mkdir(parents=True, exist_ok=True)
    return dirs


def _atomic_pickle(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.{time.time_ns()}.tmp")
    with tmp.open("wb") as f:
        pickle.dump(payload, f, protocol=pickle.HIGHEST_PROTOCOL)
    os.replace(tmp, path)


def _read_pickle(path: Path) -> Any:
    with path.open("rb") as f:
        return pickle.load(f)


def _move_to_failed(path: Path, failed_dir: Path, *, prefix: str) -> Path:
    failed_dir.mkdir(parents=True, exist_ok=True)
    dest = failed_dir / f"{prefix}_{int(time.time())}_{path.name}"
    os.replace(path, dest)
    return dest


def _cards_list(cards: Any) -> list[Any]:
    return list(cards or [])


def _default_max_workers() -> int:
    cpu_count = os.cpu_count() or 2
    return max(1, min(8, cpu_count - 2 if cpu_count > 3 else 1))


def _original_job_name(path: Path) -> str:
    name = path.name
    if "__" in name:
        return name.split("__", 1)[1]
    return name


def _job_identity(path: Path) -> str:
    return _original_job_name(path)


def _format_bytes(size: float) -> str:
    value = float(size)
    if value >= _GB:
        return f"{value / _GB:.1f}GB"
    if value >= 1024 ** 2:
        return f"{value / 1024 ** 2:.1f}MB"
    if value >= 1024:
        return f"{value / 1024:.1f}KB"
    return f"{value:.0f}B"


def _safe_stat(path: Path):
    try:
        return path.stat()
    except FileNotFoundError:
        return None


def _spool_stats(dirs: dict[str, Path]) -> dict[str, Any]:
    stats: dict[str, Any] = {
        "pending_count": 0,
        "processing_count": 0,
        "results_count": 0,
        "failed_count": 0,
        "pending_bytes": 0,
        "processing_bytes": 0,
        "results_bytes": 0,
        "failed_bytes": 0,
        "oldest_pending_age_sec": 0.0,
    }
    now = time.time()
    oldest_pending = None
    for key in ("pending", "processing", "results", "failed"):
        count = 0
        total = 0
        for path in dirs[key].glob("*.pkl"):
            st = _safe_stat(path)
            if st is None:
                continue
            count += 1
            total += int(st.st_size)
            if key == "pending":
                oldest_pending = (
                    st.st_mtime
                    if oldest_pending is None
                    else min(oldest_pending, st.st_mtime)
                )
        stats[f"{key}_count"] = count
        stats[f"{key}_bytes"] = total
    stats["backlog_count"] = int(stats["pending_count"]) + int(stats["processing_count"])
    stats["backlog_bytes"] = int(stats["pending_bytes"]) + int(stats["processing_bytes"])
    if oldest_pending is not None:
        stats["oldest_pending_age_sec"] = max(0.0, now - oldest_pending)
    try:
        usage = shutil.disk_usage(dirs["root"])
        stats["disk_free_bytes"] = int(usage.free)
        stats["disk_total_bytes"] = int(usage.total)
    except Exception:
        stats["disk_free_bytes"] = 0
        stats["disk_total_bytes"] = 0
    return stats


def _prune_rate_window(window: Deque[tuple], *, now: float, horizon_sec: float) -> None:
    while window and now - float(window[0][0]) > horizon_sec:
        window.popleft()


def _bytes_rate(window: Deque[tuple], *, now: float, horizon_sec: float) -> float:
    _prune_rate_window(window, now=now, horizon_sec=horizon_sec)
    if not window:
        return 0.0
    oldest = float(window[0][0])
    span = max(1.0, now - oldest)
    return sum(float(item[1]) for item in window) / span


def _worker_bytes_per_sec(window: Deque[tuple], *, now: float, horizon_sec: float) -> float:
    _prune_rate_window(window, now=now, horizon_sec=horizon_sec)
    total_bytes = sum(float(item[1]) for item in window)
    total_sec = sum(max(0.001, float(item[2])) for item in window)
    if total_bytes <= 0.0 or total_sec <= 0.0:
        return 0.0
    return total_bytes / total_sec


def _target_worker_count(
    *,
    stats: dict[str, Any],
    production_bytes_per_sec: float,
    worker_bytes_per_sec: float,
    min_workers: int,
    max_workers: int,
    drain_sec: float,
) -> int:
    min_workers = max(0, int(min_workers))
    max_workers = max(1, int(max_workers))
    min_workers = min(min_workers, max_workers)
    backlog_bytes = float(stats.get("backlog_bytes", 0) or 0)
    pending_count = int(stats.get("pending_count", 0) or 0)
    backlog_count = int(stats.get("backlog_count", 0) or 0)

    if backlog_count <= 0 and production_bytes_per_sec <= 0.0:
        return min_workers

    if worker_bytes_per_sec <= 0.0:
        if backlog_bytes >= 20 * _GB or pending_count >= 20:
            return max_workers
        if backlog_count > 0:
            return min(max_workers, max(min_workers, 4))
        return max(min_workers, 1)

    drain_rate = backlog_bytes / max(60.0, float(drain_sec or 3600.0))
    desired_rate = production_bytes_per_sec * 1.20 + drain_rate
    target = int(math.ceil(desired_rate / worker_bytes_per_sec))

    # Small jobs can make byte rate underestimate queue pressure.  Keep enough
    # workers active to reduce job count backlog, not just byte backlog.
    if pending_count > 0:
        target = max(target, int(math.ceil(pending_count / 8.0)))

    return max(min_workers, min(max_workers, target))


def _log_raw(logger, event: dict[str, Any]) -> None:
    if logger is None:
        return
    raw = getattr(logger, "raw", None)
    if not callable(raw):
        return
    try:
        raw(event)
    except Exception:
        pass


def ensure_spool_worker_process(
    *,
    spool_dir: Optional[Path | str] = None,
    runtime_root: Optional[Path | str] = None,
    poll_sec: float = 0.20,
    parent_pid: Optional[int] = None,
    logger=None,
) -> Optional[subprocess.Popen]:
    """Start or reuse the process-level live calibration spool supervisor.

    The producer lives in BotAPI, but the consumer is an infrastructure worker.
    Keeping one shared supervisor per process lets proxy startup drain old jobs
    before any WSS/BotAPI session is created, and prevents BotAPI instances from
    owning or killing the consumer lifecycle.
    """
    runtime = Path(runtime_root) if runtime_root is not None else _default_runtime_root()
    spool = Path(spool_dir) if spool_dir is not None else _default_spool_dir()
    runtime = runtime.resolve()
    spool = spool.resolve()
    _ensure_dirs(spool)
    key = (str(spool), str(runtime))

    existing = _SHARED_WORKERS.get(key)
    if existing is not None:
        proc = existing.get("proc")
        if proc is not None and proc.poll() is None:
            return proc
        log_fh = existing.get("log")
        if log_fh is not None:
            try:
                log_fh.close()
            except Exception:
                pass
        _SHARED_WORKERS.pop(key, None)

    existing_pid = _find_existing_worker_pid(spool)
    if existing_pid > 0 and existing_pid != os.getpid():
        ref = _ExistingWorkerRef(existing_pid)
        _SHARED_WORKERS[key] = {"proc": ref, "log": None}
        _log_raw(logger, {
            "event": "showdown_calibration_spool_worker_reused",
            "pid": existing_pid,
            "spool_dir": str(spool),
        })
        return ref  # type: ignore[return-value]

    cmd = [
        sys.executable,
        "-m",
        "pokerfate.calibration.spool_showdown_calibration",
        "worker",
        "--spool-dir",
        str(spool),
        "--runtime-root",
        str(runtime),
        "--poll-sec",
        str(max(0.05, float(poll_sec or 0.20))),
        "--parent-pid",
        str(os.getpid() if parent_pid is None else int(parent_pid)),
        "--max-workers",
        str(_default_max_workers()),
        "--min-workers",
        str(_DEFAULT_MIN_WORKERS),
        "--drain-sec",
        str(_DEFAULT_DRAIN_SEC),
        "--warn-gb",
        str(_DEFAULT_WARN_GB),
        "--stop-gb",
        str(_DEFAULT_STOP_GB),
    ]
    env = os.environ.copy()
    env.setdefault("PYTHONUNBUFFERED", "1")
    log_fh = None
    try:
        log_fh = (spool / "worker.stderr.log").open("w", encoding="utf-8")
        proc = subprocess.Popen(
            cmd,
            cwd=str(_repo_root()),
            stdin=subprocess.DEVNULL,
            stdout=log_fh,
            stderr=log_fh,
            env=env,
            start_new_session=True,
        )
        _SHARED_WORKERS[key] = {"proc": proc, "log": log_fh}
        _log_raw(logger, {
            "event": "showdown_calibration_spool_worker_started",
            "pid": proc.pid,
            "spool_dir": str(spool),
        })
        return proc
    except Exception:
        traceback.print_exc()
        if log_fh is not None:
            try:
                log_fh.close()
            except Exception:
                pass
        return None


class FileSpoolShowdownCalibrator:
    """Live-safe calibrator wrapper backed by a file spool and worker process."""

    def __init__(
        self,
        logger=None,
        *,
        big_blind: float = 0.0,
        spool_dir: Optional[Path | str] = None,
        runtime_root: Optional[Path | str] = None,
        start_worker: bool = True,
        poll_sec: float = 0.20,
    ) -> None:
        self._logger = logger
        self._big_blind = float(big_blind or 0.0)
        self._runtime_root = (
            Path(runtime_root) if runtime_root is not None else _default_runtime_root()
        )
        self._spool_dir = Path(spool_dir) if spool_dir is not None else _default_spool_dir()
        self._dirs = _ensure_dirs(self._spool_dir)
        self._start_worker = bool(start_worker)
        self._poll_sec = max(0.05, float(poll_sec or 0.20))
        self._worker: Optional[subprocess.Popen] = None
        self._session_id = f"{int(time.time())}-{os.getpid()}"

        self._hand_id = 0
        self._predictions: list[dict[str, Any]] = []
        self._shown_cards: dict[int, list[Any]] = {}
        self._hero_cards: Optional[list[Any]] = None
        self._final_board: list[Any] = []
        self._submitted_hand = False

        if self._start_worker:
            self._ensure_worker()

    def start_hand(self, hand_id: int) -> None:
        self._hand_id = int(hand_id)
        self._predictions = []
        self._shown_cards = {}
        self._hero_cards = None
        self._final_board = []
        self._submitted_hand = False

    def record_prediction(self, **kwargs) -> None:
        self._predictions.append(self._snapshot_prediction(kwargs))

    def record_actual(
        self,
        player_id: int,
        actual_cards: list[Any],
        final_board: list[Any],
        hero_cards: Optional[list[Any]],
    ) -> None:
        self._shown_cards[int(player_id)] = _cards_list(actual_cards)
        self._final_board = _cards_list(final_board)
        self._hero_cards = _cards_list(hero_cards) if hero_cards else None

    def emit_records_for(
        self,
        player_id: int,
        hero_cards: Optional[list[Any]],
        final_board: list[Any],
    ) -> list[CalibrationResult]:
        self._submit_hand_once(hero_cards=hero_cards, final_board=final_board)
        return []

    def finalize_hand_calibration(
        self,
        hero_cards: Optional[list[Any]],
        final_board: list[Any],
    ) -> list[CalibrationResult]:
        self._submit_hand_once(hero_cards=hero_cards, final_board=final_board)
        return []

    def apply_pending_updates(
        self,
        hero_eq_calibrator,
        river_relative_calibrator,
        *,
        max_files: int = 200,
    ) -> int:
        """Apply worker-produced online updates and delete consumed files."""
        self._ensure_worker()
        applied = 0
        result_files = sorted(self._dirs["results"].glob("*.pkl"))[:max_files]
        for path in result_files:
            try:
                payload = _read_pickle(path)
                for update in payload.get("updates", []):
                    kind = update.get("kind")
                    if kind == "hero_eq":
                        hero_eq_calibrator.record(
                            bucket=update.get("bucket", ""),
                            street=update.get("street", ""),
                            num_opp=int(update.get("num_opp", 0) or 0),
                            predicted=float(update.get("predicted", 0.0) or 0.0),
                            actual=float(update.get("actual", 0.0) or 0.0),
                            action_ctx=update.get("action_ctx", "passive"),
                        )
                        applied += 1
                    elif kind == "river_relative":
                        river_relative_calibrator.record(
                            hero_bucket=update.get("hero_bucket", ""),
                            hero_made_subtype=update.get("hero_made_subtype", ""),
                            board_texture=update.get("board_texture", ""),
                            action_ctx=update.get("action_ctx", "passive"),
                            predicted_dist=dict(update.get("predicted_dist", {}) or {}),
                            actual_relation=update.get("actual_relation", ""),
                        )
                        applied += 1
                path.unlink()
            except Exception:
                traceback.print_exc()
                try:
                    _move_to_failed(path, self._dirs["failed"], prefix="apply")
                except Exception:
                    traceback.print_exc()
        return applied

    def close(self, *, terminate_worker: bool = True, timeout: float = 1.0) -> None:
        # The live worker is a shared proxy-level consumer.  BotAPI/calibrator
        # instances should not own or kill it when a session object is cleaned up.
        self._worker = None

    def __del__(self) -> None:
        try:
            self.close(terminate_worker=False, timeout=0.2)
        except Exception:
            pass

    def _submit_hand_once(
        self,
        *,
        hero_cards: Optional[list[Any]],
        final_board: list[Any],
    ) -> None:
        if self._submitted_hand:
            return
        if not self._shown_cards or not self._predictions:
            return

        job = {
            "schema": _SPOOL_SCHEMA,
            "created_at": time.time(),
            "producer_pid": os.getpid(),
            "session_id": self._session_id,
            "hand_id": int(self._hand_id),
            "big_blind": float(self._big_blind or 0.0),
            "hero_cards": _cards_list(hero_cards) if hero_cards else self._hero_cards,
            "final_board": _cards_list(final_board) or self._final_board,
            "shown_cards": dict(self._shown_cards),
            "predictions": list(self._predictions),
        }
        name = f"hand_{self._hand_id}_{os.getpid()}_{time.time_ns()}.pkl"
        try:
            _atomic_pickle(self._dirs["pending"] / name, job)
            self._submitted_hand = True
            self._ensure_worker()
            self._log_raw({
                "event": "showdown_calibration_spool_submitted",
                "hand": int(self._hand_id),
                "predictions": len(self._predictions),
                "shown_players": len(self._shown_cards),
            })
        except Exception:
            traceback.print_exc()

    def _ensure_worker(self) -> None:
        if not self._start_worker:
            return
        if self._worker is not None and self._worker.poll() is None:
            return
        self._worker = ensure_spool_worker_process(
            spool_dir=self._spool_dir,
            runtime_root=self._runtime_root,
            poll_sec=self._poll_sec,
            parent_pid=os.getpid(),
            logger=self._logger,
        )

    def _log_raw(self, event: dict[str, Any]) -> None:
        _log_raw(self._logger, event)

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


class FileSpoolRangeCompareCollector:
    """Hand-level PokerFate-vs-g5 range comparison collector.

    The live path only appends small decision snapshots and writes a single
    completed-hand job.  The shared spool worker computes comparison metrics
    and appends JSONL rows off the WSS/BotAPI process.
    """

    def __init__(
        self,
        logger=None,
        *,
        big_blind: float = 0.0,
        spool_dir: Optional[Path | str] = None,
        runtime_root: Optional[Path | str] = None,
        start_worker: bool = True,
        poll_sec: float = 0.20,
    ) -> None:
        self._logger = logger
        self._big_blind = float(big_blind or 0.0)
        self._runtime_root = (
            Path(runtime_root) if runtime_root is not None else _default_runtime_root()
        )
        self._spool_dir = Path(spool_dir) if spool_dir is not None else _default_spool_dir()
        self._dirs = _ensure_dirs(self._spool_dir)
        self._start_worker = bool(start_worker)
        self._poll_sec = max(0.05, float(poll_sec or 0.20))
        self._worker: Optional[subprocess.Popen] = None
        self._session_id = f"{int(time.time())}-{os.getpid()}"

        self._hand_id = 0
        self._hero_id: Optional[int] = None
        self._players: list[dict[str, Any]] = []
        self._snapshots: list[dict[str, Any]] = []
        self._shown_cards: dict[int, list[str]] = {}
        self._hero_cards: list[str] = []
        self._final_board: list[str] = []
        self._submitted_hand = False

        if self._start_worker:
            self._ensure_worker()

    def set_big_blind(self, big_blind: float) -> None:
        self._big_blind = float(big_blind or 0.0)

    def start_hand(
        self,
        hand_id: int,
        *,
        players: Optional[list[dict[str, Any]]] = None,
        hero_id: Optional[int] = None,
    ) -> None:
        self._hand_id = int(hand_id)
        self._hero_id = int(hero_id) if hero_id is not None else None
        self._players = [dict(p) for p in (players or [])]
        self._snapshots = []
        self._shown_cards = {}
        self._hero_cards = []
        self._final_board = []
        self._submitted_hand = False

    def discard_hand(self) -> None:
        self._snapshots = []
        self._shown_cards = {}
        self._hero_cards = []
        self._final_board = []
        self._submitted_hand = False

    def record_decision_snapshot(self, snapshot: dict[str, Any]) -> None:
        if self._submitted_hand:
            return
        opponents = snapshot.get("opponents") if isinstance(snapshot, dict) else None
        if not opponents:
            return
        self._snapshots.append(_json_clone(snapshot))

    def record_showdown(
        self,
        *,
        shown_cards: dict[int, list[Any]],
        final_board: list[Any],
        hero_cards: Optional[list[Any]] = None,
    ) -> None:
        self._shown_cards = {
            int(pid): [str(c) for c in list(cards or [])[:2]]
            for pid, cards in (shown_cards or {}).items()
            if cards
        }
        self._final_board = [str(c) for c in (final_board or [])]
        self._hero_cards = [str(c) for c in (hero_cards or [])]

    def finalize_hand(self) -> None:
        if self._submitted_hand:
            return
        if not self._snapshots or not self._shown_cards:
            return
        shown_without_hero = {
            pid: cards
            for pid, cards in self._shown_cards.items()
            if self._hero_id is None or int(pid) != int(self._hero_id)
        }
        if not shown_without_hero:
            return
        job = {
            "schema": _RANGE_COMPARE_SPOOL_SCHEMA,
            "created_at": time.time(),
            "producer_pid": os.getpid(),
            "session_id": self._session_id,
            "hand_id": int(self._hand_id),
            "big_blind": float(self._big_blind or 0.0),
            "hero_id": self._hero_id,
            "hero_cards": list(self._hero_cards),
            "final_board": list(self._final_board),
            "players": list(self._players),
            "shown_cards": shown_without_hero,
            "snapshots": list(self._snapshots),
        }
        name = f"range_compare_hand_{self._hand_id}_{os.getpid()}_{time.time_ns()}.pkl"
        try:
            _atomic_pickle(self._dirs["pending"] / name, job)
            self._submitted_hand = True
            self._ensure_worker()
            _log_raw(self._logger, {
                "event": "range_compare_spool_submitted",
                "hand": int(self._hand_id),
                "snapshots": len(self._snapshots),
                "shown_players": len(shown_without_hero),
            })
        except Exception:
            traceback.print_exc()

    def close(self) -> None:
        self._worker = None

    def _ensure_worker(self) -> None:
        if not self._start_worker:
            return
        if self._worker is not None and self._worker.poll() is None:
            return
        self._worker = ensure_spool_worker_process(
            spool_dir=self._spool_dir,
            runtime_root=self._runtime_root,
            poll_sec=self._poll_sec,
            parent_pid=os.getpid(),
            logger=self._logger,
        )


def _json_clone(value: Any) -> Any:
    return json.loads(json.dumps(value, ensure_ascii=False, default=str))


def _updates_from_results(results: list[CalibrationResult]) -> list[dict[str, Any]]:
    updates: list[dict[str, Any]] = []
    for result in results:
        rec = result.record
        action_ctx = classify_action_ctx_from_trigger(rec.trigger)
        if (
            rec.predicted_hero_eq_multi is not None
            and result.actual_hero_eq_street_multi is not None
            and rec.hero_bucket
        ):
            updates.append({
                "kind": "hero_eq",
                "bucket": rec.hero_bucket,
                "street": rec.street,
                "num_opp": len(rec.active_player_ids),
                "predicted": float(rec.predicted_hero_eq_multi),
                "actual": float(result.actual_hero_eq_street_multi),
                "action_ctx": action_ctx,
            })
        if (
            rec.street == "river"
            and rec.villain_vs_hero_dist
            and result.actual_relation
            and rec.hero_bucket
        ):
            updates.append({
                "kind": "river_relative",
                "hero_bucket": rec.hero_bucket,
                "hero_made_subtype": rec.hero_made_subtype,
                "board_texture": rec.board_texture,
                "action_ctx": action_ctx,
                "predicted_dist": dict(rec.villain_vs_hero_dist),
                "actual_relation": result.actual_relation,
            })
    return updates


_RANK_TO_VALUE = {
    "2": 2, "3": 3, "4": 4, "5": 5, "6": 6, "7": 7,
    "8": 8, "9": 9, "T": 10, "J": 11, "Q": 12, "K": 13, "A": 14,
}
_VALUE_TO_RANK = {v: k for k, v in _RANK_TO_VALUE.items()}


def _category_from_cards(cards: list[Any]) -> str:
    if not cards or len(cards) < 2:
        return ""
    c1 = str(cards[0]).strip()
    c2 = str(cards[1]).strip()
    if len(c1) < 2 or len(c2) < 2:
        return ""
    r1 = _RANK_TO_VALUE.get(c1[0].upper())
    r2 = _RANK_TO_VALUE.get(c2[0].upper())
    if r1 is None or r2 is None:
        return ""
    hi, lo = max(r1, r2), min(r1, r2)
    if hi == lo:
        return f"{_VALUE_TO_RANK[hi]}{_VALUE_TO_RANK[lo]}"
    suited = "s" if c1[1].lower() == c2[1].lower() else "o"
    return f"{_VALUE_TO_RANK[hi]}{_VALUE_TO_RANK[lo]}{suited}"


def _range_prob(range_map: Any, category: str) -> float:
    if not isinstance(range_map, dict) or not category:
        return 0.0
    try:
        return max(0.0, float(range_map.get(category, 0.0) or 0.0))
    except (TypeError, ValueError):
        return 0.0


def _range_rank(range_map: Any, category: str) -> Optional[int]:
    if not isinstance(range_map, dict) or not category:
        return None
    prob = _range_prob(range_map, category)
    if prob <= 0.0:
        return None
    values = []
    for value in range_map.values():
        try:
            values.append(float(value or 0.0))
        except (TypeError, ValueError):
            continue
    return 1 + sum(1 for value in values if value > prob)


def _top_categories(range_map: Any, limit: int) -> list[str]:
    if not isinstance(range_map, dict):
        return []
    pairs = []
    for key, value in range_map.items():
        try:
            pairs.append((str(key), float(value or 0.0)))
        except (TypeError, ValueError):
            continue
    pairs.sort(key=lambda item: item[1], reverse=True)
    return [key for key, value in pairs[:limit] if value > 0.0]


def _range_compare_row_from_job(job: dict[str, Any]) -> dict[str, Any]:
    hand_id = int(job.get("hand_id", 0) or 0)
    hero_id = job.get("hero_id")
    shown_players: dict[str, dict[str, Any]] = {}
    for pid, cards in (job.get("shown_cards") or {}).items():
        pid_s = str(pid)
        cards_l = [str(c) for c in list(cards or [])[:2]]
        shown_players[pid_s] = {
            "player_id": pid_s,
            "cards": cards_l,
            "category": _category_from_cards(cards_l),
        }

    comparisons: list[dict[str, Any]] = []
    for snapshot in list(job.get("snapshots") or []):
        if not isinstance(snapshot, dict):
            continue
        decision_index = int(snapshot.get("decision_index", 0) or 0)
        street = str(snapshot.get("street") or "")
        for opponent in list(snapshot.get("opponents") or []):
            if not isinstance(opponent, dict):
                continue
            pid_s = str(opponent.get("player_id"))
            actual = shown_players.get(pid_s)
            if not actual:
                continue
            category = str(actual.get("category") or "")
            pf_range = opponent.get("pf_range_169") or {}
            g5_range = opponent.get("g5_range_169") or {}
            pf_prob = _range_prob(pf_range, category)
            g5_prob = _range_prob(g5_range, category)
            comparisons.append({
                "decision_index": decision_index,
                "street": street,
                "player_id": pid_s,
                "player_name": str(opponent.get("name") or ""),
                "actual_cards": list(actual.get("cards") or []),
                "actual_category": category,
                "pf_prob": pf_prob,
                "g5_prob": g5_prob,
                "pf_logloss": -math.log(max(pf_prob, 1e-12)),
                "g5_logloss": -math.log(max(g5_prob, 1e-12)),
                "pf_rank": _range_rank(pf_range, category),
                "g5_rank": _range_rank(g5_range, category),
                "pf_top5_hit": category in set(_top_categories(pf_range, 5)),
                "g5_top5_hit": category in set(_top_categories(g5_range, 5)),
                "pf_top20_hit": category in set(_top_categories(pf_range, 20)),
                "g5_top20_hit": category in set(_top_categories(g5_range, 20)),
            })

    return {
        "hand_id": hand_id,
        "created_at": float(job.get("created_at", 0.0) or 0.0),
        "hero_id": str(hero_id) if hero_id is not None else "",
        "hero_cards": [str(c) for c in (job.get("hero_cards") or [])],
        "final_board": [str(c) for c in (job.get("final_board") or [])],
        "players": list(job.get("players") or []),
        "shown_players": list(shown_players.values()),
        "snapshots": list(job.get("snapshots") or []),
        "comparisons": comparisons,
    }


def _process_range_compare_job(
    path: Path,
    *,
    runtime_root: Path,
    job: dict[str, Any],
    job_size: int,
) -> dict[str, Any]:
    hand_id = int(job.get("hand_id", 0) or 0)
    row = _range_compare_row_from_job(job)
    recorder = RuntimeCalibrationRecorder(
        root=runtime_root,
        session_id=str(job.get("session_id") or ""),
    )
    row_count = recorder.write_range_compare(
        row,
        big_blind=float(job.get("big_blind", 0.0) or 0.0),
        hand_id=hand_id,
        source="runtime",
    )
    path.unlink()
    return {
        "hand_id": hand_id,
        "row_count": row_count,
        "update_count": 0,
        "prediction_count": len(job.get("snapshots") or []),
        "shown_count": len(job.get("shown_cards") or {}),
        "work_units": len(row.get("comparisons") or []),
        "bytes": job_size,
    }


def _claim_next_job(dirs: dict[str, Path], *, worker_id: str = "") -> Optional[Path]:
    for path in sorted(dirs["pending"].glob("*.pkl")):
        dest_name = f"{worker_id}__{path.name}" if worker_id else path.name
        dest = dirs["processing"] / dest_name
        try:
            os.replace(path, dest)
            return dest
        except FileNotFoundError:
            continue
        except OSError:
            continue
    return None


def _reclaim_stale_processing(dirs: dict[str, Path], *, stale_sec: float = 300.0) -> None:
    now = time.time()
    for path in dirs["processing"].glob("*.pkl"):
        try:
            if now - path.stat().st_mtime < stale_sec:
                continue
            os.replace(path, dirs["pending"] / _original_job_name(path))
        except FileNotFoundError:
            continue
        except Exception:
            traceback.print_exc()


def _reclaim_worker_processing(dirs: dict[str, Path], *, worker_id: str) -> int:
    reclaimed = 0
    for path in dirs["processing"].glob(f"{worker_id}__*.pkl"):
        try:
            os.replace(path, dirs["pending"] / _original_job_name(path))
            reclaimed += 1
        except FileNotFoundError:
            continue
        except Exception:
            traceback.print_exc()
    return reclaimed


def _process_job(path: Path, *, runtime_root: Path, dirs: dict[str, Path]) -> dict[str, Any]:
    job_size = int(path.stat().st_size)
    job = _read_pickle(path)
    schema = job.get("schema")
    if schema == _RANGE_COMPARE_SPOOL_SCHEMA:
        return _process_range_compare_job(
            path,
            runtime_root=runtime_root,
            job=job,
            job_size=job_size,
        )
    if schema != _SPOOL_SCHEMA:
        raise ValueError(f"unsupported spool schema: {job.get('schema')!r}")

    hand_id = int(job.get("hand_id", 0) or 0)
    hero_cards = _cards_list(job.get("hero_cards"))
    final_board = _cards_list(job.get("final_board"))

    calibrator = ShowdownCalibrator(logger=None)
    calibrator.start_hand(hand_id)
    for pred in job.get("predictions", []):
        calibrator.record_prediction(**pred)
    for player_id, cards in (job.get("shown_cards") or {}).items():
        calibrator.record_actual(
            player_id=int(player_id),
            actual_cards=_cards_list(cards),
            final_board=final_board,
            hero_cards=hero_cards,
        )
    results = calibrator.finalize_hand_calibration(
        hero_cards=hero_cards,
        final_board=final_board,
    )

    row_count = 0
    if results:
        recorder = RuntimeCalibrationRecorder(
            root=runtime_root,
            session_id=str(job.get("session_id") or ""),
        )
        row_count = recorder.write_results(
            results,
            big_blind=float(job.get("big_blind", 0.0) or 0.0),
            final_board=final_board,
            source="runtime",
        )

    updates = _updates_from_results(results)
    if updates:
        out = {
            "schema": _UPDATE_SCHEMA,
            "created_at": time.time(),
            "hand_id": hand_id,
            "row_count": row_count,
            "updates": updates,
        }
        _atomic_pickle(dirs["results"] / f"{path.stem}.updates.pkl", out)
    path.unlink()
    predictions = job.get("predictions") or []
    shown_cards = job.get("shown_cards") or {}
    return {
        "hand_id": hand_id,
        "row_count": row_count,
        "update_count": len(updates),
        "prediction_count": len(predictions),
        "shown_count": len(shown_cards),
        "work_units": len(predictions) * max(1, len(shown_cards)),
        "bytes": job_size,
    }


def run_spool_worker_once(
    *,
    spool_dir: Optional[Path | str] = None,
    runtime_root: Optional[Path | str] = None,
    max_jobs: Optional[int] = None,
) -> int:
    """Process pending jobs once.  Tests use this without launching a process."""
    dirs = _ensure_dirs(spool_dir or _default_spool_dir())
    root = Path(runtime_root) if runtime_root is not None else _default_runtime_root()
    _reclaim_stale_processing(dirs)
    processed = 0
    while max_jobs is None or processed < max_jobs:
        path = _claim_next_job(dirs)
        if path is None:
            break
        try:
            _process_job(path, runtime_root=root, dirs=dirs)
            processed += 1
        except Exception:
            traceback.print_exc()
            try:
                _move_to_failed(path, dirs["failed"], prefix="job")
            except Exception:
                traceback.print_exc()
    return processed


def _notify_spool_alert(*, title: str, body: str, key_file: Path) -> None:
    try:
        key = load_bark_key_file(key_file)
    except Exception:
        traceback.print_exc()
        return
    if not key:
        return
    set_bark_key(key)
    notify("codex_done", title=title, body=body)


def _load_monitor_state(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _save_monitor_state(path: Path, state: dict[str, Any]) -> None:
    try:
        path.write_text(
            json.dumps(state, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    except Exception:
        traceback.print_exc()


def spool_backpressure_status(
    spool_dir: Optional[Path | str] = None,
) -> dict[str, Any]:
    root = Path(spool_dir) if spool_dir is not None else _default_spool_dir()
    path = root / _BACKPRESSURE_FILE
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {"active": False}
    except Exception:
        traceback.print_exc()
        return {"active": False}
    if not isinstance(data, dict):
        return {"active": False}
    data["active"] = bool(data.get("active"))
    return data


def spool_backpressure_active(
    spool_dir: Optional[Path | str] = None,
) -> bool:
    return bool(spool_backpressure_status(spool_dir).get("active"))


def _write_backpressure_status(
    *,
    dirs: dict[str, Path],
    active: bool,
    level: str,
    stats: dict[str, Any],
    warn_gb: float,
    pause_gb: float,
    reason: str,
) -> None:
    path = dirs["root"] / _BACKPRESSURE_FILE
    payload = {
        "active": bool(active),
        "level": level,
        "reason": reason,
        "updated_at": time.time(),
        "warn_gb": float(warn_gb),
        "pause_gb": float(pause_gb),
        "backlog_bytes": int(stats.get("backlog_bytes", 0) or 0),
        "backlog_gb": float(stats.get("backlog_bytes", 0) or 0) / _GB,
        "pending_count": int(stats.get("pending_count", 0) or 0),
        "processing_count": int(stats.get("processing_count", 0) or 0),
        "oldest_pending_age_sec": float(stats.get("oldest_pending_age_sec", 0.0) or 0.0),
        "disk_free_bytes": int(stats.get("disk_free_bytes", 0) or 0),
    }
    try:
        path.write_text(
            json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    except Exception:
        traceback.print_exc()


def _write_supervisor_status(
    *,
    dirs: dict[str, Path],
    stats: dict[str, Any] | None,
    workers: int,
    target_workers: int,
    max_workers: int,
    parent_pid: int,
) -> None:
    payload = {
        "pid": os.getpid(),
        "parent_pid": int(parent_pid),
        "updated_at": time.time(),
        "workers": int(workers),
        "target_workers": int(target_workers),
        "max_workers": int(max_workers),
    }
    if stats:
        payload.update({
            "pending_count": int(stats.get("pending_count", 0) or 0),
            "processing_count": int(stats.get("processing_count", 0) or 0),
            "results_count": int(stats.get("results_count", 0) or 0),
            "backlog_bytes": int(stats.get("backlog_bytes", 0) or 0),
            "backlog_gb": float(stats.get("backlog_bytes", 0) or 0) / _GB,
            "disk_free_bytes": int(stats.get("disk_free_bytes", 0) or 0),
        })
    try:
        (dirs["root"] / _SUPERVISOR_STATUS_FILE).write_text(
            json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    except Exception:
        traceback.print_exc()


def _maybe_monitor_spool(
    *,
    dirs: dict[str, Path],
    stats: dict[str, Any],
    active_workers: int,
    target_workers: int,
    warn_gb: float,
    stop_gb: float,
    parent_pid: int,
    key_file: Path,
    parent_stop_requested: bool,
) -> bool:
    now = time.time()
    state_path = dirs["root"] / "monitor_state.json"
    state = _load_monitor_state(state_path)
    backlog_bytes = float(stats.get("backlog_bytes", 0) or 0)
    backlog_gb = backlog_bytes / _GB
    free_gb = float(stats.get("disk_free_bytes", 0) or 0) / _GB
    pending_count = int(stats.get("pending_count", 0) or 0)
    processing_count = int(stats.get("processing_count", 0) or 0)
    oldest_min = float(stats.get("oldest_pending_age_sec", 0.0) or 0.0) / 60.0

    def _body(level: str) -> str:
        return (
            f"level={level}\n"
            f"backlog={_format_bytes(backlog_bytes)} "
            f"pending={pending_count} processing={processing_count}\n"
            f"workers={active_workers}/{target_workers}\n"
            f"oldest_pending={oldest_min:.0f}min\n"
            f"disk_free={free_gb:.1f}GB\n"
            f"spool={dirs['root']}"
        )

    pause_threshold = max(1.0, float(stop_gb or 50.0))
    warn_threshold = max(1.0, float(warn_gb or 20.0))
    cooldown_sec = 1800.0
    current_bp = spool_backpressure_status(dirs["root"])
    was_active = bool(current_bp.get("active"))

    if backlog_gb >= pause_threshold:
        last = float(state.get("last_stop_at", 0.0) or 0.0)
        if now - last >= cooldown_sec:
            _notify_spool_alert(
                title="校准队列严重积压",
                body=_body("pause"),
                key_file=key_file,
            )
            state["last_stop_at"] = now
            _save_monitor_state(state_path, state)
        _write_backpressure_status(
            dirs=dirs,
            active=True,
            level="pause",
            stats=stats,
            warn_gb=warn_threshold,
            pause_gb=pause_threshold,
            reason="backlog_over_pause_threshold",
        )
        if not was_active:
            print(
                "[CAL_SPOOL] backpressure active: "
                f"{backlog_gb:.1f}GB >= {pause_threshold:.1f}GB; "
                "bot should stop entering new hands",
                flush=True,
            )
        return True

    if was_active and backlog_gb < warn_threshold:
        _write_backpressure_status(
            dirs=dirs,
            active=False,
            level="ok",
            stats=stats,
            warn_gb=warn_threshold,
            pause_gb=pause_threshold,
            reason="backlog_below_warn_threshold",
        )
        last = float(state.get("last_resume_at", 0.0) or 0.0)
        if now - last >= cooldown_sec:
            _notify_spool_alert(
                title="校准队列已恢复",
                body=_body("resume"),
                key_file=key_file,
            )
            state["last_resume_at"] = now
            _save_monitor_state(state_path, state)
        print(
            "[CAL_SPOOL] backpressure cleared: "
            f"{backlog_gb:.1f}GB < {warn_threshold:.1f}GB",
            flush=True,
        )
        return False

    if backlog_gb >= warn_threshold:
        last = float(state.get("last_warn_at", 0.0) or 0.0)
        if now - last >= cooldown_sec:
            _notify_spool_alert(
                title="校准队列积压",
                body=_body("warn"),
                key_file=key_file,
            )
            state["last_warn_at"] = now
            _save_monitor_state(state_path, state)

    return was_active


def _worker_child_loop(
    *,
    worker_id: str,
    spool_dir: str,
    runtime_root: str,
    poll_sec: float,
    stop_event,
    result_queue,
) -> None:
    dirs = _ensure_dirs(spool_dir)
    root = Path(runtime_root)
    idle_sleep = max(0.05, float(poll_sec or 0.20))
    while not stop_event.is_set():
        path = _claim_next_job(dirs, worker_id=worker_id)
        if path is None:
            time.sleep(idle_sleep)
            continue
        started = time.monotonic()
        try:
            stats = _process_job(path, runtime_root=root, dirs=dirs)
            elapsed = max(0.001, time.monotonic() - started)
            result_queue.put({
                "event": "done",
                "worker_id": worker_id,
                "elapsed_sec": elapsed,
                **stats,
            })
        except Exception as exc:
            traceback.print_exc()
            try:
                failed = _move_to_failed(path, dirs["failed"], prefix=f"job_{worker_id}")
            except Exception:
                traceback.print_exc()
                failed = path
            result_queue.put({
                "event": "failed",
                "worker_id": worker_id,
                "elapsed_sec": max(0.001, time.monotonic() - started),
                "path": str(failed),
                "error": str(exc),
            })


def _start_child_worker(
    *,
    ctx,
    worker_id: str,
    spool_dir: Path,
    runtime_root: Path,
    poll_sec: float,
    result_queue,
) -> dict[str, Any]:
    stop_event = ctx.Event()
    proc = ctx.Process(
        target=_worker_child_loop,
        kwargs={
            "worker_id": worker_id,
            "spool_dir": str(spool_dir),
            "runtime_root": str(runtime_root),
            "poll_sec": poll_sec,
            "stop_event": stop_event,
            "result_queue": result_queue,
        },
        name=f"cal-spool-{worker_id}",
        daemon=False,
    )
    proc.start()
    return {"id": worker_id, "proc": proc, "stop": stop_event, "started_at": time.time()}


def _parent_alive(parent_pid: int) -> bool:
    if parent_pid <= 0:
        return True
    if os.getppid() == 1:
        return False
    try:
        os.kill(parent_pid, 0)
    except OSError:
        return False
    return True


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _read_pid_file(path: Path) -> int:
    try:
        return int(path.read_text(encoding="utf-8").strip() or "0")
    except Exception:
        return 0


class _ExistingWorkerRef:
    """Minimal Popen-like reference for a supervisor started by another process."""

    def __init__(self, pid: int) -> None:
        self.pid = int(pid)

    def poll(self) -> int | None:
        return None if _pid_alive(self.pid) else 1


def _find_existing_worker_pid(spool: Path) -> int:
    pid = _read_pid_file(spool / _SUPERVISOR_PID_FILE)
    if _pid_alive(pid):
        return pid
    # Compatibility for workers started before supervisor.pid existed.
    # Avoid starting a second supervisor that could reclaim active processing
    # files from the first one.
    try:
        out = subprocess.check_output(
            ["ps", "-axo", "pid=,command="],
            text=True,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        return 0
    spool_text = str(spool)
    self_pid = os.getpid()
    for line in out.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        try:
            pid_text, command = stripped.split(None, 1)
            candidate_pid = int(pid_text)
        except ValueError:
            continue
        if candidate_pid == self_pid:
            continue
        if "pokerfate.calibration.spool_showdown_calibration" not in command:
            continue
        if " worker " not in f" {command} ":
            continue
        if spool_text not in command:
            continue
        if _pid_alive(candidate_pid):
            return candidate_pid
    return 0


def worker_loop(
    *,
    spool_dir: Path | str,
    runtime_root: Path | str,
    poll_sec: float,
    parent_pid: int,
    min_workers: int = 1,
    max_workers: int = 0,
    drain_sec: float = 3600.0,
    warn_gb: float = 20.0,
    stop_gb: float = 50.0,
    key_file: Optional[Path | str] = None,
) -> None:
    dirs = _ensure_dirs(spool_dir)
    spool_root = Path(spool_dir)
    runtime = Path(runtime_root)
    max_workers = int(max_workers or _default_max_workers())
    max_workers = max(1, min(8, max_workers))
    min_workers = max(0, min(int(min_workers), max_workers))
    key_path = Path(key_file) if key_file is not None else (_repo_root() / "data" / "bark_key.txt")

    _reclaim_stale_processing(dirs, stale_sec=0.0)
    pid_path = dirs["root"] / _SUPERVISOR_PID_FILE
    try:
        pid_path.write_text(f"{os.getpid()}\n", encoding="utf-8")
    except Exception:
        traceback.print_exc()
    ctx = multiprocessing.get_context("spawn")
    result_queue = ctx.Queue()
    workers: dict[str, dict[str, Any]] = {}
    next_worker_id = 1
    production_window: Deque[tuple] = deque()
    consume_window: Deque[tuple] = deque()
    seen_jobs = {
        _job_identity(path)
        for key in ("pending", "processing")
        for path in dirs[key].glob("*.pkl")
    }
    last_status_at = 0.0
    parent_stop_requested = False
    shutting_down = False

    def _start_one() -> None:
        nonlocal next_worker_id
        worker_id = f"w{next_worker_id}"
        next_worker_id += 1
        workers[worker_id] = _start_child_worker(
            ctx=ctx,
            worker_id=worker_id,
            spool_dir=spool_root,
            runtime_root=runtime,
            poll_sec=poll_sec,
            result_queue=result_queue,
        )
        print(f"[CAL_SPOOL] worker started id={worker_id} pid={workers[worker_id]['proc'].pid}", flush=True)

    def _request_stop(worker_id: str) -> None:
        worker = workers.get(worker_id)
        if not worker:
            return
        worker["stop"].set()

    def _stop_all() -> None:
        for worker_id in list(workers):
            _request_stop(worker_id)
        deadline = time.time() + 5.0
        for worker_id, worker in list(workers.items()):
            proc = worker["proc"]
            remaining = max(0.0, deadline - time.time())
            proc.join(timeout=remaining)
            if proc.is_alive():
                proc.terminate()
                proc.join(timeout=2.0)
            if proc.is_alive():
                proc.kill()
                proc.join(timeout=1.0)
            _reclaim_worker_processing(dirs, worker_id=worker_id)
            workers.pop(worker_id, None)

    def _handle_signal(_signum, _frame) -> None:
        nonlocal shutting_down
        if parent_stop_requested:
            print("[CAL_SPOOL] ignore shutdown signal while draining backlog", flush=True)
            return
        shutting_down = True

    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    try:
        while True:
            now = time.time()
            if shutting_down:
                break
            if (
                not parent_stop_requested
                and parent_pid > 0
                and not _parent_alive(parent_pid)
            ):
                break

            for worker_id, worker in list(workers.items()):
                proc = worker["proc"]
                if proc.is_alive():
                    continue
                proc.join(timeout=0)
                reclaimed = _reclaim_worker_processing(dirs, worker_id=worker_id)
                print(
                    f"[CAL_SPOOL] worker exited id={worker_id} "
                    f"exitcode={proc.exitcode} reclaimed={reclaimed}",
                    flush=True,
                )
                workers.pop(worker_id, None)

            while True:
                try:
                    msg = result_queue.get_nowait()
                except Empty:
                    break
                if msg.get("event") == "done":
                    consume_window.append((
                        now,
                        int(msg.get("bytes", 0) or 0),
                        float(msg.get("elapsed_sec", 0.0) or 0.0),
                    ))
                    print(
                        "[CAL_SPOOL] job done "
                        f"worker={msg.get('worker_id')} hand={msg.get('hand_id')} "
                        f"bytes={_format_bytes(msg.get('bytes', 0))} "
                        f"elapsed={float(msg.get('elapsed_sec', 0.0)):.1f}s "
                        f"rows={msg.get('row_count')} updates={msg.get('update_count')}",
                        flush=True,
                    )
                elif msg.get("event") == "failed":
                    print(
                        "[CAL_SPOOL] job failed "
                        f"worker={msg.get('worker_id')} path={msg.get('path')} "
                        f"error={msg.get('error')}",
                        flush=True,
                    )

            for key in ("pending", "processing"):
                for path in dirs[key].glob("*.pkl"):
                    ident = _job_identity(path)
                    if ident in seen_jobs:
                        continue
                    seen_jobs.add(ident)
                    st = _safe_stat(path)
                    if st is not None:
                        production_window.append((now, int(st.st_size)))
            if len(seen_jobs) > 10000:
                seen_jobs = set(list(seen_jobs)[-5000:])

            stats = _spool_stats(dirs)
            production_rate = _bytes_rate(
                production_window,
                now=now,
                horizon_sec=1800.0,
            )
            worker_rate = _worker_bytes_per_sec(
                consume_window,
                now=now,
                horizon_sec=1800.0,
            )
            target = _target_worker_count(
                stats=stats,
                production_bytes_per_sec=production_rate,
                worker_bytes_per_sec=worker_rate,
                min_workers=min_workers,
                max_workers=max_workers,
                drain_sec=drain_sec,
            )
            if int(stats.get("backlog_count", 0) or 0) <= 0:
                target = min(target, min_workers)

            while len(workers) < target:
                _start_one()
            if len(workers) > target:
                idle_to_stop = len(workers) - target
                for worker_id in list(workers)[:idle_to_stop]:
                    _request_stop(worker_id)

            _maybe_monitor_spool(
                dirs=dirs,
                stats=stats,
                active_workers=len(workers),
                target_workers=target,
                warn_gb=warn_gb,
                stop_gb=stop_gb,
                parent_pid=parent_pid,
                key_file=key_path,
                parent_stop_requested=parent_stop_requested,
            )

            if now - last_status_at >= 30.0:
                last_status_at = now
                _write_supervisor_status(
                    dirs=dirs,
                    stats=stats,
                    workers=len(workers),
                    target_workers=target,
                    max_workers=max_workers,
                    parent_pid=parent_pid,
                )
                print(
                    "[CAL_SPOOL] status "
                    f"workers={len(workers)}/{target}/{max_workers} "
                    f"pending={stats['pending_count']} "
                    f"processing={stats['processing_count']} "
                    f"backlog={_format_bytes(stats['backlog_bytes'])} "
                    f"prod={_format_bytes(production_rate)}/s "
                    f"worker={_format_bytes(worker_rate)}/s "
                    f"free={_format_bytes(stats.get('disk_free_bytes', 0))}",
                    flush=True,
                )

            if (
                parent_stop_requested
                and int(stats.get("backlog_count", 0) or 0) <= 0
            ):
                break
            time.sleep(max(0.05, float(poll_sec or 0.20)))
    finally:
        _stop_all()
        if _read_pid_file(pid_path) == os.getpid():
            try:
                pid_path.unlink()
            except FileNotFoundError:
                pass
            except Exception:
                traceback.print_exc()


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    worker = sub.add_parser("worker")
    worker.add_argument("--spool-dir", required=True)
    worker.add_argument("--runtime-root", required=True)
    worker.add_argument("--poll-sec", type=float, default=0.20)
    worker.add_argument("--parent-pid", type=int, default=0)
    worker.add_argument("--min-workers", type=int, default=1)
    worker.add_argument("--max-workers", type=int, default=0)
    worker.add_argument("--drain-sec", type=float, default=3600.0)
    worker.add_argument("--warn-gb", type=float, default=20.0)
    worker.add_argument("--stop-gb", type=float, default=50.0)
    worker.add_argument(
        "--key-file",
        default=str(_repo_root() / "data" / "bark_key.txt"),
    )
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    args = _build_arg_parser().parse_args(argv)
    if args.cmd == "worker":
        worker_loop(
            spool_dir=args.spool_dir,
            runtime_root=args.runtime_root,
            poll_sec=args.poll_sec,
            parent_pid=args.parent_pid,
            min_workers=args.min_workers,
            max_workers=args.max_workers,
            drain_sec=args.drain_sec,
            warn_gb=args.warn_gb,
            stop_gb=args.stop_gb,
            key_file=args.key_file,
        )
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
