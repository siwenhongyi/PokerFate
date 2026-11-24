"""CLI: ``python -m pf_intercept.headless``.

Headless (pure-API) play: connect to the game WSS with saved session
credentials (``local/secrets/headless_session.json``: uid / rdkey / authorization,
harvested from one real device login), skipping /login and YiDun risk control
entirely.  The live-table web is started by default so the game can be watched
in a browser (bind 0.0.0.0 → reachable from a phone on the same Wi-Fi).

  python -m pf_intercept.headless --bb 10000 --buyin-bb 50 --profit-lock-bb 140 --max-auto-rebuy 0

Credentials expire with the saved rdkey/JWT (~30 days); when invalid, run
``python -m pf_intercept.headless.harvest_session`` to re-harvest the session
file (requires logging in once on a real device through that script's proxy).
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import signal
import sys
from pathlib import Path

from pf_intercept.options import RunOptions
from pf_intercept import config
from pf_intercept.headless import lobby
from pf_intercept.headless.lobby.radar.board import Board as RadarBoard
from pf_intercept.headless.network import configure_server_proxy_bypass
from pf_intercept.headless.process import ProcessControlError, RunningProcess, request_stop
from pf_intercept.headless.session import HeadlessSession, LoginRejected, SessionClosed
from pf_intercept.headless.reconnect import maintain_game, until_stopped
from pf_notify.config import load_bark_key_file, set_bark_key

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_LOGS_DIR = _PROJECT_ROOT / "pf_intercept" / "logs"
_PID_FILE = _LOGS_DIR / "headless.pid"
_DEFAULT_SESSION_FILE = _PROJECT_ROOT / "local" / "secrets" / "headless_session.json"
log = logging.getLogger("pf_headless")

# 等价于启动命令里的 PYTHONUNBUFFERED=1：stdout/stderr 被 nohup 重定向到文件时仍即时落盘，
# 子进程（solver worker 等）也继承该设置。
os.environ.setdefault("PYTHONUNBUFFERED", "1")
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(write_through=True)


class ResumeError(RuntimeError):
    """Saved session credentials are missing or invalid."""


def _setup_logging(verbose: bool) -> None:
    _LOGS_DIR.mkdir(parents=True, exist_ok=True)
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s %(message)s")
    fh = logging.FileHandler(_LOGS_DIR / "headless.log", mode="a", encoding="utf-8")
    fh.setFormatter(fmt)
    sh = logging.StreamHandler(sys.stderr)
    sh.setFormatter(fmt)
    sh.setLevel(logging.DEBUG if verbose else logging.INFO)
    root = logging.getLogger()
    root.setLevel(logging.DEBUG if verbose else logging.INFO)
    root.handlers[:] = [fh, sh]
    logging.getLogger("websockets").setLevel(logging.WARNING)


def _parse_args() -> argparse.Namespace:
    from pf_intercept.options import add_run_arguments
    p = add_run_arguments(argparse.ArgumentParser(description="PokerFate 纯 API 客户端"))
    p.add_argument("--hold", type=float, default=30.0, help="不进桌时保持连接的秒数")
    return p.parse_args()


def switched_off(args: argparse.Namespace) -> set[str]:
    """The lobby workers' switches turned off on the command line."""
    return {flag for flag, _ in lobby.switches() if getattr(args, "no_" + flag.replace("-", "_"), False)}


def _resume_result(path: Path):
    from pf_intercept.headless.login import load_session, LoginError
    try:
        return load_session(path)
    except LoginError as exc:
        raise ResumeError(str(exc)) from exc


async def _order_servers_by_latency(servers):
    """Probe each line's http_host /ping and order by latency, like the client's
    Loginline line picker. Ties / unreachable lines keep the WAF'd :443 entry
    last (its WSS rejects headless with 403, so it is only a fallback)."""
    from pf_intercept.headless.login import measure_ping

    if len(servers) <= 1:
        return list(servers)
    delays = await asyncio.gather(*[asyncio.to_thread(measure_ping, s.http_host) for s in servers])
    # :443 入口网关对 headless WSS 恒 403，放到最后兜底；其余可用线路按延迟升序。
    order = sorted(range(len(servers)),
                   key=lambda i: (1 if ":443" in servers[i].server_host else 0, delays[i], i))
    for i in order:
        tag = f"{delays[i]:.0f}ms" if delays[i] != float("inf") else "超时/不可达"
        note = "（入口网关·兜底）" if ":443" in servers[i].server_host else ""
        print(f"[headless]   线路 {servers[i].server_host}  延迟={tag}{note}")
    return [servers[i] for i in order]


def _table_policy_config(args: argparse.Namespace):
    """Table selection settings from the CLI; None only when we are not joining a table.

    There is deliberately no off switch: the bot never stays at a table without humans.  A
    home stake outside the allowed fallback stakes still gets table selection, with a
    one-stake ladder unless ``--stakes`` names fallbacks.
    """
    from pf_intercept.table_policy import configured_policy

    bb = int(getattr(args, "bb", 0) or 0)
    if bb <= 0:
        return None
    try:
        return configured_policy(bb, int(args.buyin_bb), getattr(args, "stakes", ""))
    except ValueError as exc:
        raise ResumeError(f"--stakes 无效: {exc}")


async def _graceful_leave(session, leave_done: asyncio.Event, *, timeout: float = 45.0) -> None:
    """Leave the table cleanly before shutting down.

    Sends DelayLeaveRoomREQ (the client's "leave after this hand" request —
    a plain LeaveRoomREQ while a hand is in progress is rejected with 121) and
    waits for LeaveRoomRSP, so we don't abandon the seat for the server to time
    out."""
    begin_shutdown = getattr(session, "begin_shutdown", None)
    if callable(begin_shutdown):
        begin_shutdown()
    try:
        room = getattr(session, "current_room_id", None)
        rid = room() if callable(room) else session.bridge.room_id_for_c2s(0)
    except Exception:
        rid = 0
    if not rid:
        return
    print(f"[headless] 优雅退出：打完当前手后离桌 room={rid} …")
    leave_done.clear()
    if not await session.send("pb.DelayLeaveRoomREQ", {"flag": True}, room_id=rid):
        return
    try:
        await asyncio.wait_for(leave_done.wait(), timeout=timeout)
        print("[headless] 已确认离桌，关闭连接。")
    except asyncio.TimeoutError:
        print("[headless] 等待离桌确认超时，直接关闭。", file=sys.stderr)


async def _run(args: argparse.Namespace, stop: asyncio.Event | None = None) -> int:
    if stop is None:
        stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop.set)
        except (NotImplementedError, RuntimeError):
            pass
    if stop.is_set():
        return 0
    options = RunOptions.from_namespace(args)
    log.info("[RUN_OPTIONS] %s", options)
    # Bark 通知：headless 进程不经过 proxy 的 bot_worker，必须自己加载 key。
    if options.no_notify:
        set_bark_key(None)
    else:
        try:
            key = load_bark_key_file(_PROJECT_ROOT / "local" / "secrets" / "bark_key.txt")
            set_bark_key(key)
            print("[headless] Bark 通知已启用" if key else
                  "[headless] 未找到 local/secrets/bark_key.txt，通知关闭", file=sys.stderr)
        except Exception as exc:
            print(f"[headless] Bark key 加载失败: {exc}", file=sys.stderr)

    session_file = args.session_file or _DEFAULT_SESSION_FILE
    result, chnl, client_version = _resume_result(session_file)
    configure_server_proxy_bypass(result.servers, http_fallback=config.GAMEDATA_HTTP_HOST)
    print(f"[headless] 恢复会话 {result.redacted()} chnl={chnl} ver={client_version}")
    # 按延迟选线（与客户端 Loginline 的 /ping 探测一致），低延迟优先连。
    result.servers = await _order_servers_by_latency(result.servers)
    if stop.is_set():
        return 0


    observer = None
    remote_live_enabled = not getattr(args, "no_remote_live", False)
    if not args.no_web or remote_live_enabled:
        from pf_entertainment.live_table import LiveTableObserver, start_live_web
        # Initial login may switch lines and replace session before the first hand.
        observer = LiveTableObserver(my_uid=result.uid, reward_source=lambda: session.live_reward_totals(),
                                     chips_source=lambda: session.live_total_chips(),
                                     decision_source=lambda: session.live_decisions())

    # Frame hook: feed the live observer and notice LeaveRoomRSP for graceful exit.
    leave_done = asyncio.Event()

    def on_frame(type_name, msg):
        if observer is not None:
            observer.observe(type_name, msg)
        if type_name == "pb.LeaveRoomRSP" and int(msg.get("code", 0) or 0) in (0, 2, 3):
            leave_done.set()

    table_policy = _table_policy_config(args)

    def _mk_session():
        return HeadlessSession(result, chnl=chnl, client_version=client_version,
                               max_auto_rebuy=args.max_auto_rebuy, on_frame=on_frame,
                               options=options,
                               auto_rewards=not getattr(args, "no_auto_rewards", False),
                               off=switched_off(args),
                               auto_taskhands=not getattr(args, "no_task_hands", False),
                               reconnect_enabled=getattr(args, "bb", 0) > 0,
                               table_policy=table_policy)

    # Connect, trying each server in turn (the :443 entry is WAF-blocked).
    session = _mk_session()
    if observer is not None and not args.no_web:
        web_server = await start_live_web(
            observer, host=args.web_host, port=args.web_port,
            # Resolve the current session on every read: server fallback below
            # replaces it (and its bankroll baseline), so don't bind its method.
            bankroll_source=lambda: session.bankroll_dashboard(),
            # The 雷达 tab: the radar's findings and the user's ignore list (local/state/lobby_ignores.json).
            radar_board=RadarBoard(),
        )
    last_exc = None
    for idx in range(len(result.servers)):
        try:
            if not await until_stopped(session.connect(server_index=idx), stop):
                await session.close("cli exit")
                return 0
            break
        except LoginRejected as exc:
            log.error("[WSS] 登录被拒绝，不再切线重试: %s", exc)
            await session.close("login rejected")
            return 2
        except Exception as exc:
            last_exc = exc
            log.warning("[WSS] server_index=%d 连接/登录失败: %s: %s", idx, type(exc).__name__, exc)
            if getattr(session, "fatal_error", None):
                log.error("[WSS] %s", session.fatal_error)
                await session.close("server rejected session")
                return 2
            await session.close("retry next server")
            if stop.is_set():
                return 0
            session = _mk_session()
    if not session.logged_in:
        log.error("[WSS] 所有服务器登录失败: %s", last_exc)
        return 2
    if observer is not None:
        observer.set_connected(True)
    print(f"[headless] WSS 登录成功，心跳每 5s；日志 {_LOGS_DIR / 'headless.log'}")

    # SSH validation and all uploads happen in a background task. A missing or
    # unusable config must never delay joining a table or stop the bot.
    from pf_entertainment.remote_live.publisher import start_remote_live
    remote_publisher = start_remote_live(observer.snapshot if observer else None,
                                         # like the local Web: the session can be replaced, read the current one
                                         money_source=lambda: session.bankroll_dashboard(),
                                         enabled=remote_live_enabled and not stop.is_set())
    ok = True
    try:
        if args.bb > 0:
            if not stop.is_set():
                ok = await maintain_game(session, stop, big_blind=args.bb, buyin_bb=args.buyin_bb,
                                         server_index=idx, observer=observer)
            if stop.is_set() and session.connected:
                await _graceful_leave(session, leave_done)
        else:
            print(f"[headless] 只登录不进桌，保持 {args.hold:.0f}s 后断开")
            try:
                await asyncio.wait_for(stop.wait(), timeout=args.hold)
            except asyncio.TimeoutError:
                pass
    finally:
        if observer is not None:
            observer.set_connected(False)
        if remote_publisher is not None:
            await remote_publisher.close()
        await session.close("cli exit")
    print(f"[headless] 结束 {session.stats}")
    return 0 if ok else 2


def main() -> int:
    args = _parse_args()
    if args.stop:
        try:
            pid = request_stop(_PID_FILE)
        except (ProcessControlError, OSError) as exc:
            print(f"[headless] 停止失败: {exc}", file=sys.stderr)
            return 2
        print(f"[headless] 已向 PID {pid} 发送优雅停止请求；进程退出后 PID 文件自动删除" if pid
              else "[headless] 没有通过 PID 文件管理的运行实例（旧版进程需使用原停止命令）")
        return 0

    # Install before publishing the PID, including when nohup inherits ignored
    # SIGINT. Python signal callbacks run on the main thread, as does this loop.
    stop = asyncio.Event()
    previous = {sig: signal.signal(sig, lambda *_: stop.set())
                for sig in (signal.SIGINT, signal.SIGTERM)}
    logging_ready = False
    try:
        with RunningProcess(_PID_FILE):
            _setup_logging(args.verbose)
            logging_ready = True
            return asyncio.run(_run(args, stop))
    except (ResumeError, SessionClosed, ProcessControlError, OSError) as exc:
        if logging_ready:
            log.error("[headless] 失败: %s: %s", type(exc).__name__, exc)
        else:
            print(f"[headless] 失败: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        return 130
    except Exception:
        log.exception("[headless] 未处理异常，退出")
        return 2
    finally:
        for sig, handler in previous.items():
            signal.signal(sig, handler)


if __name__ == "__main__":
    raise SystemExit(main())
