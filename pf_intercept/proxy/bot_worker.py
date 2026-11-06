from __future__ import annotations

import asyncio
import logging
import multiprocessing
import os
import queue
import sys
import time
import traceback
import uuid
from pathlib import Path
from typing import Any

from pf_intercept import config
from pf_notify.config import load_bark_key_file, set_bark_key

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_LOGS_DIR = _PROJECT_ROOT / "pf_intercept" / "logs"
_DEFAULT_BARK_KEY_FILE = _PROJECT_ROOT / "data" / "bark_key.txt"

_BOT_IPC_MAX_QUEUE = int(os.environ.get("PF_BOT_IPC_MAX_QUEUE", "5000"))
_BOT_CALL_TIMEOUT_SEC = float(os.environ.get("PF_BOT_CALL_TIMEOUT_SEC", "3.0"))
_BOT_GUARD_CHECK_TIMEOUT_SEC = float(
    os.environ.get("PF_BOT_GUARD_CHECK_TIMEOUT_SEC", "0.75")
)
_BOT_WORKER_STOP_TIMEOUT_SEC = float(
    os.environ.get("PF_BOT_WORKER_STOP_TIMEOUT_SEC", "5.0")
)


def _configure_worker_logging(logs_dir: Path) -> None:
    logs_dir.mkdir(exist_ok=True)
    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(logging.INFO)

    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    file_handler = logging.FileHandler(logs_dir / "bot_worker.log", mode="w", encoding="utf-8")
    file_handler.setFormatter(fmt)
    root.addHandler(file_handler)

    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setLevel(logging.WARNING)
    console_handler.setFormatter(fmt)
    root.addHandler(console_handler)


def _load_bark_key_for_worker(
    log: logging.Logger,
    key_file: Path = _DEFAULT_BARK_KEY_FILE,
) -> bool:
    """Spawned workers do not inherit the parent process' in-memory Bark key."""
    try:
        key = load_bark_key_file(key_file)
        set_bark_key(key)
    except Exception:
        log.exception("[BOT_WORKER] Bark key load failed path=%s", key_file)
        return False
    if key:
        log.info("[BOT_WORKER] Bark key loaded from %s; bot push enabled", key_file)
        return True
    log.info("[BOT_WORKER] no Bark key in %s; bot push disabled", key_file)
    return False


def _queue_put(q, payload: dict[str, Any]) -> None:
    q.put(payload)


def _queue_put_best_effort(q, payload: dict[str, Any]) -> None:
    try:
        q.put_nowait(payload)
    except queue.Full:
        logging.getLogger("pf_bot_worker").warning(
            "[BOT_WORKER] outbound queue full, dropping %s",
            payload.get("kind"),
        )


def _iter_injects(result: tuple | list | None) -> tuple[tuple, ...]:
    if result is None:
        return ()
    if isinstance(result, list):
        return tuple(item for item in result if item is not None)
    if isinstance(result, tuple) and result and isinstance(result[0], tuple):
        return tuple(item for item in result if item is not None)
    return (result,)


def _inject_payload(
    *,
    bridge,
    session_id: int,
    frame_room_id: int,
    inject: tuple,
) -> dict[str, Any] | None:
    if not inject:
        return None
    inject_type = str(inject[0])
    fields = dict(inject[1] or {}) if len(inject) >= 2 else {}
    delay_sec = float(inject[2] or 0.0) if len(inject) >= 3 else 0.0
    guard = bridge.injection_guard_for(inject)
    return {
        "kind": "inject",
        "session_id": int(session_id),
        "type_name": inject_type,
        "fields": fields,
        "delay_sec": max(0.0, delay_sec),
        "room_id": int(bridge.room_id_for_c2s(frame_room_id)),
        "guard": list(guard) if guard is not None else None,
        "created_at": time.monotonic(),
    }


def _snapshot_payload(bridge) -> dict[str, Any]:
    return {
        "kind": "snapshot",
        "settings": bridge.runtime_settings(),
        "dashboard": bridge.bankroll_dashboard(),
    }


def _handle_call(bridge, method: str, payload: dict[str, Any]) -> Any:
    if method == "runtime_settings":
        return bridge.runtime_settings()
    if method == "bankroll_dashboard":
        return bridge.bankroll_dashboard()
    if method == "update_runtime_settings":
        return bridge.update_runtime_settings(
            profit_lock_bb=payload.get("profit_lock_bb"),
            decision_engine=payload.get("decision_engine"),
            preflop_sticky_pool_adjust=payload.get("preflop_sticky_pool_adjust"),
        )
    if method == "guard_current":
        guard = payload.get("guard")
        if guard is None:
            return True
        if isinstance(guard, (list, tuple)) and len(guard) == 2:
            return bridge.injection_guard_is_current((str(guard[0]), int(guard[1])))
        return False
    raise ValueError(f"unknown bot worker method: {method}")


def _bot_worker_main(to_worker, from_worker, options: dict[str, Any]) -> None:
    _configure_worker_logging(_LOGS_DIR)
    log = logging.getLogger("pf_bot_worker")
    _load_bark_key_for_worker(log)
    try:
        from pf_intercept.bot import BotBridge

        profit_lock_bb = options.get("profit_lock_bb")
        if profit_lock_bb is not None:
            config.PROFIT_LOCK_BB_THRESHOLD = int(profit_lock_bb)

        bridge = BotBridge(
            max_auto_rebuy=int(options.get("max_auto_rebuy", 1)),
            use_range_equity=bool(options.get("use_range_equity", True)),
        )
        _queue_put(
            from_worker,
            {
                "kind": "ready",
                "pid": os.getpid(),
                "settings": bridge.runtime_settings(),
                "dashboard": bridge.bankroll_dashboard(),
            },
        )
        log.info("[BOT_WORKER] ready pid=%s options=%s", os.getpid(), options)

        while True:
            item = to_worker.get()
            if not isinstance(item, dict):
                continue
            kind = item.get("kind")
            if kind == "shutdown":
                log.info("[BOT_WORKER] shutdown requested")
                break

            if kind == "room_seen":
                bridge.note_seen_room_id(int(item.get("room_id") or 0))
                continue

            if kind == "notify_inject_failed":
                bridge.notify_inject_failed(str(item.get("type_name") or ""))
                continue

            if kind == "call":
                call_id = str(item.get("call_id") or "")
                try:
                    result = _handle_call(
                        bridge,
                        str(item.get("method") or ""),
                        dict(item.get("payload") or {}),
                    )
                    _queue_put(from_worker, {"kind": "response", "call_id": call_id, "result": result})
                    if item.get("method") in {"update_runtime_settings"}:
                        _queue_put_best_effort(from_worker, _snapshot_payload(bridge))
                except Exception as exc:
                    log.exception("[BOT_WORKER] call failed method=%s", item.get("method"))
                    _queue_put(
                        from_worker,
                        {
                            "kind": "response",
                            "call_id": call_id,
                            "error": f"{type(exc).__name__}: {exc}",
                        },
                    )
                continue

            if kind != "s2c_msg":
                continue

            session_id = int(item.get("session_id") or 0)
            frame_room_id = int(item.get("room_id") or 0)
            type_name = str(item.get("type_name") or "")
            msg = dict(item.get("msg") or {})

            bridge.note_seen_room_id(frame_room_id)
            started = time.monotonic()
            try:
                result = bridge.handle(type_name, msg)
            except Exception:
                log.exception("[BOT_WORKER] bridge.handle failed type=%s", type_name)
                result = None
            handle_ms = (time.monotonic() - started) * 1000.0
            injects = _iter_injects(result)
            log.info(
                "[BOT_HANDLE] session=%s type=%s handle_ms=%.1f injects=%d",
                session_id,
                type_name,
                handle_ms,
                len(injects),
            )
            if handle_ms >= 500:
                log.warning(
                    "[BOT_HANDLE_SLOW] session=%s type=%s handle_ms=%.1f",
                    session_id,
                    type_name,
                    handle_ms,
                )
            for inject in injects:
                payload = _inject_payload(
                    bridge=bridge,
                    session_id=session_id,
                    frame_room_id=frame_room_id,
                    inject=inject,
                )
                if payload is not None:
                    _queue_put_best_effort(from_worker, payload)
            if type_name in {
                "pb.DealerInfoRSP",
                "pb.EnterRoomRSP",
                "pb.SitDownRSP",
                "pb.UserValueRSP",
                "pb.WinnerRSP",
                "pb.LeaveRoomRSP",
                "pb.StandUpRSP",
                "pb.StandUpBRC",
                "pb.OtherLeaveRoomBRC",
                "pb.NoticeRebyRSP",
                "pb.RebyBRC",
            }:
                _queue_put_best_effort(from_worker, _snapshot_payload(bridge))
    except BaseException as exc:
        traceback.print_exc()
        try:
            _queue_put(
                from_worker,
                {
                    "kind": "fatal",
                    "error": f"{type(exc).__name__}: {exc}",
                    "traceback": traceback.format_exc(),
                },
            )
        except Exception:
            pass
        raise
    finally:
        logging.getLogger("pf_bot_worker").info("[BOT_WORKER] exited")


class BotWorkerClient:
    def __init__(
        self,
        *,
        max_auto_rebuy: int,
        profit_lock_bb: int | None,
        use_range_equity: bool,
    ) -> None:
        self.max_auto_rebuy = int(max_auto_rebuy)
        self.profit_lock_bb = profit_lock_bb
        self.use_range_equity = bool(use_range_equity)
        self.log = logging.getLogger("pf_proxy")

        self._ctx = multiprocessing.get_context("spawn")
        self._to_worker = self._ctx.Queue(maxsize=_BOT_IPC_MAX_QUEUE)
        self._from_worker = self._ctx.Queue(maxsize=_BOT_IPC_MAX_QUEUE)
        self._proc = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._reader_task: asyncio.Task | None = None
        self._ready: asyncio.Future | None = None
        self._pending: dict[str, asyncio.Future] = {}
        self._session_queues: dict[int, asyncio.Queue] = {}
        self._settings_cache: dict[str, Any] | None = None
        self._dashboard_cache: dict[str, Any] | None = None
        self._dropped_inbound = 0
        self._closed = False

    @property
    def pid(self) -> int | None:
        return getattr(self._proc, "pid", None)

    def is_alive(self) -> bool:
        return self._proc is not None and self._proc.is_alive()

    async def start(self) -> None:
        if self._proc is not None:
            return
        self._loop = asyncio.get_running_loop()
        self._ready = self._loop.create_future()
        options = {
            "max_auto_rebuy": self.max_auto_rebuy,
            "profit_lock_bb": self.profit_lock_bb,
            "use_range_equity": self.use_range_equity,
        }
        self._proc = self._ctx.Process(
            target=_bot_worker_main,
            args=(self._to_worker, self._from_worker, options),
            name="pf-bot-worker",
        )
        self._proc.start()
        self._reader_task = asyncio.create_task(self._drain_worker_output())
        await asyncio.wait_for(self._ready, timeout=15.0)
        self.log.info("[BOT_WORKER] started pid=%s", self.pid)

    async def stop(self) -> None:
        self._closed = True
        if self._proc is None:
            return
        if self._proc.is_alive():
            try:
                self._to_worker.put_nowait({"kind": "shutdown"})
            except Exception:
                pass
            await asyncio.to_thread(self._proc.join, _BOT_WORKER_STOP_TIMEOUT_SEC)
        if self._proc.is_alive():
            self.log.warning("[BOT_WORKER] terminate stuck worker pid=%s", self.pid)
            self._proc.terminate()
            await asyncio.to_thread(self._proc.join, 2.0)
        if self._proc.is_alive():
            self.log.warning("[BOT_WORKER] kill stuck worker pid=%s", self.pid)
            self._proc.kill()
            await asyncio.to_thread(self._proc.join, 1.0)

        if self._reader_task is not None:
            self._reader_task.cancel()
            await asyncio.gather(self._reader_task, return_exceptions=True)
            self._reader_task = None
        self._fail_pending(RuntimeError("bot worker stopped"))
        try:
            self._to_worker.close()
            self._from_worker.close()
        except Exception:
            pass
        self.log.info("[BOT_WORKER] stopped exitcode=%s", self._proc.exitcode)

    def register_session(self, session_id: int) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        self._session_queues[int(session_id)] = q
        return q

    def unregister_session(self, session_id: int) -> None:
        self._session_queues.pop(int(session_id), None)

    def submit_room_seen(self, *, session_id: int, room_id: int) -> None:
        if int(room_id or 0) == 0:
            return
        self._submit_nowait(
            {
                "kind": "room_seen",
                "session_id": int(session_id),
                "room_id": int(room_id),
            }
        )

    def submit_s2c(
        self,
        *,
        session_id: int,
        type_name: str,
        msg: dict,
        room_id: int,
    ) -> None:
        self._submit_nowait(
            {
                "kind": "s2c_msg",
                "session_id": int(session_id),
                "type_name": str(type_name),
                "msg": msg,
                "room_id": int(room_id or 0),
                "queued_at": time.monotonic(),
            }
        )

    def notify_inject_failed(self, type_name: str) -> None:
        self._submit_nowait(
            {
                "kind": "notify_inject_failed",
                "type_name": str(type_name or ""),
            }
        )

    def runtime_settings(self) -> dict | None:
        return dict(self._settings_cache) if isinstance(self._settings_cache, dict) else None

    def bankroll_dashboard(self) -> dict | None:
        return dict(self._dashboard_cache) if isinstance(self._dashboard_cache, dict) else None

    def update_runtime_settings(
        self,
        *,
        profit_lock_bb=None,
        decision_engine=None,
        preflop_sticky_pool_adjust=None,
    ) -> dict:
        result = self.call_sync(
            "update_runtime_settings",
            {
                "profit_lock_bb": profit_lock_bb,
                "decision_engine": decision_engine,
                "preflop_sticky_pool_adjust": preflop_sticky_pool_adjust,
            },
            timeout=_BOT_CALL_TIMEOUT_SEC,
        )
        if isinstance(result, dict):
            self._settings_cache = dict(result)
            return result
        raise RuntimeError("bot worker returned invalid settings")

    async def injection_guard_is_current(self, guard) -> bool:
        if guard is None:
            return True
        try:
            result = await self.call(
                "guard_current",
                {"guard": guard},
                timeout=_BOT_GUARD_CHECK_TIMEOUT_SEC,
            )
        except Exception as exc:
            self.log.warning("[BOT_WORKER] guard check failed: %s", exc)
            return False
        return bool(result)

    async def call(
        self,
        method: str,
        payload: dict[str, Any] | None = None,
        *,
        timeout: float = _BOT_CALL_TIMEOUT_SEC,
    ) -> Any:
        if self._loop is None:
            raise RuntimeError("bot worker is not started")
        if not self.is_alive():
            raise RuntimeError("bot worker is not alive")
        call_id = uuid.uuid4().hex
        fut = self._loop.create_future()
        self._pending[call_id] = fut
        try:
            self._to_worker.put_nowait(
                {
                    "kind": "call",
                    "call_id": call_id,
                    "method": method,
                    "payload": payload or {},
                }
            )
        except Exception:
            self._pending.pop(call_id, None)
            fut.cancel()
            raise
        try:
            return await asyncio.wait_for(fut, timeout=timeout)
        finally:
            self._pending.pop(call_id, None)

    def call_sync(
        self,
        method: str,
        payload: dict[str, Any] | None = None,
        *,
        timeout: float = _BOT_CALL_TIMEOUT_SEC,
    ) -> Any:
        if self._loop is None:
            raise RuntimeError("bot worker is not started")
        future = asyncio.run_coroutine_threadsafe(
            self.call(method, payload, timeout=timeout),
            self._loop,
        )
        return future.result(timeout=timeout + 0.5)

    def status(self) -> dict[str, Any]:
        exitcode = getattr(self._proc, "exitcode", None)
        return {
            "pid": self.pid,
            "alive": self.is_alive(),
            "exitcode": exitcode,
            "dropped_inbound": self._dropped_inbound,
        }

    def _submit_nowait(self, payload: dict[str, Any]) -> None:
        if self._closed or not self.is_alive():
            return
        try:
            self._to_worker.put_nowait(payload)
        except queue.Full:
            self._dropped_inbound += 1
            if self._dropped_inbound == 1 or self._dropped_inbound % 100 == 0:
                self.log.warning(
                    "[BOT_IPC_BACKPRESSURE] inbound queue full dropped=%d kind=%s",
                    self._dropped_inbound,
                    payload.get("kind"),
                )
        except Exception as exc:
            self.log.warning("[BOT_WORKER] submit failed kind=%s err=%s", payload.get("kind"), exc)

    async def _drain_worker_output(self) -> None:
        try:
            while not self._closed:
                try:
                    item = await asyncio.to_thread(self._from_worker.get, True, 0.2)
                except queue.Empty:
                    if self._proc is not None and not self._proc.is_alive():
                        err = RuntimeError(f"bot worker exited exitcode={self._proc.exitcode}")
                        self.log.warning("[BOT_WORKER] exited unexpectedly exitcode=%s", self._proc.exitcode)
                        self._fail_pending(err)
                        if self._ready is not None and not self._ready.done():
                            self._ready.set_exception(err)
                        break
                    continue
                if not isinstance(item, dict):
                    continue
                self._handle_worker_message(item)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            self.log.exception("[BOT_WORKER] output drain failed: %s", exc)
            self._fail_pending(exc)

    def _handle_worker_message(self, item: dict[str, Any]) -> None:
        kind = item.get("kind")
        if kind == "ready":
            self._settings_cache = dict(item.get("settings") or {})
            self._dashboard_cache = dict(item.get("dashboard") or {})
            if self._ready is not None and not self._ready.done():
                self._ready.set_result(item)
            return
        if kind == "snapshot":
            if isinstance(item.get("settings"), dict):
                self._settings_cache = dict(item["settings"])
            if isinstance(item.get("dashboard"), dict):
                self._dashboard_cache = dict(item["dashboard"])
            return
        if kind == "response":
            call_id = str(item.get("call_id") or "")
            fut = self._pending.get(call_id)
            if fut is None or fut.done():
                return
            if item.get("error"):
                fut.set_exception(RuntimeError(str(item["error"])))
            else:
                fut.set_result(item.get("result"))
            return
        if kind == "inject":
            session_id = int(item.get("session_id") or 0)
            q = self._session_queues.get(session_id)
            if q is None:
                self.log.info("[BOT_WORKER] drop inject for inactive session=%s", session_id)
                return
            q.put_nowait(item)
            return
        if kind == "fatal":
            err = RuntimeError(str(item.get("error") or "bot worker fatal error"))
            self.log.error("[BOT_WORKER] fatal: %s", err)
            self._fail_pending(err)
            if self._ready is not None and not self._ready.done():
                self._ready.set_exception(err)
            return
        self.log.debug("[BOT_WORKER] ignored message kind=%s", kind)

    def _fail_pending(self, exc: BaseException) -> None:
        for fut in list(self._pending.values()):
            if not fut.done():
                fut.set_exception(exc)
        self._pending.clear()
