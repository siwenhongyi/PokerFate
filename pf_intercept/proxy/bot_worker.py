from __future__ import annotations

import asyncio
import logging
import multiprocessing
import os
import queue
import sys
import time
import uuid
from pathlib import Path
from typing import Any

from pf_intercept.options import RunOptions
from dataclasses import asdict, replace
from pf_notify.config import load_bark_key_file, set_bark_key

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_LOGS_DIR = _PROJECT_ROOT / "pf_intercept" / "logs"
_DEFAULT_BARK_KEY_FILE = _PROJECT_ROOT / "local" / "secrets" / "bark_key.txt"

_BOT_IPC_MAX_QUEUE = int(os.environ.get("PF_BOT_IPC_MAX_QUEUE", "5000"))
_BOT_CALL_TIMEOUT_SEC = float(os.environ.get("PF_BOT_CALL_TIMEOUT_SEC", "3.0"))
_BOT_GUARD_CHECK_TIMEOUT_SEC = float(
    os.environ.get("PF_BOT_GUARD_CHECK_TIMEOUT_SEC", "0.75")
)
_BOT_WORKER_STOP_TIMEOUT_SEC = float(
    os.environ.get("PF_BOT_WORKER_STOP_TIMEOUT_SEC", "60.0")
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
    console_handler.setLevel(logging.INFO)
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


def _queue_put_best_effort(q, payload: dict[str, Any]) -> None:
    try:
        q.put_nowait(payload)
    except queue.Full:
        logging.getLogger("pf_bot_worker").warning(
            "[BOT_WORKER] outbound queue full, dropping %s",
            payload.get("kind"),
        )


def _handle_call(bridge, method: str, payload: dict[str, Any]) -> Any:
    if method == "runtime_settings":
        return bridge.runtime_settings()
    if method == "bankroll_dashboard":
        return bridge.bankroll_dashboard()
    if method == "guard_current":
        guard = payload.get("guard")
        if guard is None:
            return True
        if isinstance(guard, (list, tuple)) and len(guard) == 2:
            return bridge.injection_guard_is_current((str(guard[0]), int(guard[1])))
        return False
    raise ValueError(f"unknown bot worker method: {method}")


def _bot_worker_main(to_worker, from_worker, options: dict[str, Any]) -> None:
    logs_dir = Path(options.pop("logs_dir", _LOGS_DIR))
    _configure_worker_logging(logs_dir)
    opts = RunOptions(**options)
    if opts.no_notify:
        set_bark_key(None)
    else:
        _load_bark_key_for_worker(logging.getLogger("pf_bot_worker"))
    if opts.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
        for h in logging.getLogger().handlers:
            h.setLevel(logging.DEBUG)
    try:
        asyncio.run(_worker_loop(to_worker, from_worker, opts))
    except BaseException as exc:
        _queue_put_best_effort(from_worker, {"kind": "fatal", "error": f"{type(exc).__name__}: {exc}"})
        raise


async def _worker_loop(to_worker, from_worker, options):
    from pf_intercept.bot import BotBridge
    from pf_intercept.proxy.session import ProxySession
    bridge = BotBridge(options=options, auto_table_selection=not bool(options.bb))
    emit = lambda payload: _queue_put_best_effort(from_worker, payload)
    session = ProxySession(bridge, options, emit)
    last_payload = None
    def snapshot(kind="snapshot"):
        nonlocal last_payload
        payload = {"settings": bridge.runtime_settings(), "dashboard": session.bankroll_dashboard(),
                   "live": session.observer.snapshot()}
        if kind == "ready" or payload != last_payload:
            emit({"kind": kind, "pid": os.getpid(), **payload})
            last_payload = payload
    async def call(item):
        try:
            method, payload = item.get("method"), item.get("payload") or {}
            if method == "client_request":
                result = (await session.client_request(payload["type_name"], payload["msg"])
                          if payload.get("session_id") == session.session_id else False)
            elif method == "graceful_leave":
                await session.graceful_leave()
                result = True
            else:
                result = _handle_call(bridge, method, payload)
            emit({"kind": "response", "call_id": item["call_id"], "result": result})
        except Exception as exc:
            logging.getLogger("pf_bot_worker").exception("worker call failed")
            emit({"kind": "response", "call_id": item["call_id"], "error": str(exc)})
    snapshot("ready")
    logging.getLogger("pf_bot_worker").info("[RUN_OPTIONS] %s", asdict(options))
    last_snapshot = 0.0
    calls = set()
    try:
        while True:
            try:
                item = await asyncio.to_thread(to_worker.get, True, 0.2)
            except queue.Empty:
                item = {}
            kind = item.get("kind")
            if kind == "shutdown":
                break
            if kind == "session_open":
                await session.attach(int(item["session_id"]), item.get("upstream", ""))
            elif kind == "session_close":
                await session.detach(int(item["session_id"]))
            elif kind == "call":
                task = asyncio.create_task(call(item))
                calls.add(task)
                task.add_done_callback(calls.discard)
            elif item.get("session_id") == session.session_id:
                if kind == "s2c_msg":
                    await session.feed_message(item["type_name"], int(item.get("room_id") or 0), item["msg"])
                elif kind == "wire_sent":
                    session.sent(item["send_id"], item["ok"])
            if time.monotonic() - last_snapshot >= 0.3:
                snapshot()
                last_snapshot = time.monotonic()
    finally:
        for task in calls:
            task.cancel()
        await asyncio.gather(*calls, return_exceptions=True)
        await session.close("worker shutdown")
        snapshot()


class BotWorkerClient:
    def __init__(
        self,
        *,
        max_auto_rebuy: int | None = None,
        profit_lock_bb: int | None = None,
        options: RunOptions | None = None,
        logs_dir: Path | None = None,
    ) -> None:
        self.options = options or RunOptions()
        if max_auto_rebuy is not None:
            self.options = replace(self.options, max_auto_rebuy=int(max_auto_rebuy))
        if profit_lock_bb is not None:
            self.options = replace(self.options, profit_lock_bb=profit_lock_bb)
        self.logs_dir = logs_dir
        self.max_auto_rebuy = self.options.max_auto_rebuy
        self.profit_lock_bb = self.options.profit_lock_bb
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
        self._live_cache: dict[str, Any] = {}
        self._dropped_inbound = 0
        self._closed = False
        self._stopping = False
        self.failed = asyncio.Event()

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
        options = asdict(self.options)
        if self.logs_dir is not None:
            options["logs_dir"] = str(self.logs_dir)
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
        self._stopping = True
        if self._proc is None:
            self._closed = True
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

        self._closed = True
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

    def register_session(self, session_id: int, upstream: str = "") -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        self._session_queues[int(session_id)] = q
        self._submit_nowait({"kind": "session_open", "session_id": int(session_id), "upstream": upstream})
        return q

    def unregister_session(self, session_id: int) -> None:
        self._session_queues.pop(int(session_id), None)
        self._submit_nowait({"kind": "session_close", "session_id": int(session_id)})

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

    def runtime_settings(self) -> dict | None:
        return dict(self._settings_cache) if isinstance(self._settings_cache, dict) else None

    def bankroll_dashboard(self) -> dict | None:
        return dict(self._dashboard_cache) if isinstance(self._dashboard_cache, dict) else None

    def live_snapshot(self) -> dict:
        return dict(self._live_cache)

    def notify_wire_sent(self, session_id, send_id, ok):
        self._submit_nowait({"kind": "wire_sent", "session_id": session_id, "send_id": send_id, "ok": ok})

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
                        (self.log.info if self._stopping else self.log.warning)("[BOT_WORKER] exited exitcode=%s", self._proc.exitcode)
                        if not self._stopping:
                            self._mark_failed()
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
            self._mark_failed()
            self._fail_pending(exc)

    def _handle_worker_message(self, item: dict[str, Any]) -> None:
        kind = item.get("kind")
        if kind in {"snapshot", "ready"} and isinstance(item.get("live"), dict):
            self._live_cache = dict(item["live"])
        if kind == "close_transport":
            q = self._session_queues.get(int(item.get("session_id", 0)))
            if q is not None:
                q.put_nowait(item)
            return
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
            self._mark_failed()
            self._fail_pending(err)
            if self._ready is not None and not self._ready.done():
                self._ready.set_exception(err)
            return
        self.log.debug("[BOT_WORKER] ignored message kind=%s", kind)

    def _mark_failed(self):
        self._live_cache = {**self._live_cache, "connected": False, "connection_status": "disconnected"}
        self.failed.set()

    def _fail_pending(self, exc: BaseException) -> None:
        for fut in list(self._pending.values()):
            if not fut.done():
                fut.set_exception(exc)
        self._pending.clear()
