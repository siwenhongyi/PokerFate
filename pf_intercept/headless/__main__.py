"""CLI: ``python -m pf_intercept.headless``.

Headless (pure-API) play: connect to the game WSS with saved session
credentials (``data/headless_session.json``: uid / rdkey / authorization,
harvested from one real device login), skipping /login and YiDun risk control
entirely.  The live-table web is started by default so the game can be watched
in a browser (bind 0.0.0.0 → reachable from a phone on the same Wi-Fi).

  python -m pf_intercept.headless --bb 10000 --buyin-bb 50 --profit-lock-bb 140 --max-auto-rebuy 0

Credentials expire with the saved rdkey/JWT (~30 days); when invalid, log in
once on a device and re-harvest the session file.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import signal
import sys
from pathlib import Path

from pf_intercept import config
from pf_intercept.headless.session import HeadlessSession, SessionClosed
from pf_notify.config import load_bark_key_file, set_bark_key

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_LOGS_DIR = _PROJECT_ROOT / "pf_intercept" / "logs"
_DEFAULT_SESSION_FILE = _PROJECT_ROOT / "data" / "headless_session.json"


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
    root.setLevel(logging.INFO)
    root.handlers[:] = [fh, sh]
    logging.getLogger("websockets").setLevel(logging.WARNING)


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="PokerFate headless client (pure API, no game client, no device)")
    p.add_argument("--session-file", type=Path, default=None,
                   help="会话凭证文件（默认 data/headless_session.json）")
    p.add_argument("--bb", type=int, default=0, help="进桌：大厅现金桌大盲（如 10000）。不传则只登录+心跳")
    p.add_argument("--buyin-bb", type=int, default=100, help="买入多少个大盲，默认 100")
    p.add_argument("--max-auto-rebuy", type=int, default=1, help="破产自动续入上限，0=破产即停")
    p.add_argument("--profit-lock-bb", type=int, default=None, metavar="BB", help="盈利锁仓阈值（大盲数）")
    p.add_argument("--hold", type=float, default=30.0, help="不进桌时登录后保持连接的秒数，默认 30")
    p.add_argument("--no-notify", action="store_true", help="不发 Bark 通知（默认启用，读 data/bark_key.txt）")
    p.add_argument("--no-web", action="store_true", help="不启动实时对局 Web（默认启动）")
    p.add_argument("--web-host", default="0.0.0.0", help="Web 绑定地址，默认 0.0.0.0（允许局域网/手机访问）")
    p.add_argument("--web-port", type=int, default=9022, help="Web 端口，默认 9022")
    p.add_argument("-v", "--verbose", action="store_true")
    return p.parse_args()


def _resume_result(path: Path):
    """Load saved uid/rdkey/servers → (LoginResult, chnl, client_version).

    Servers are reordered so the real game port is tried before the WAF'd
    :443 entry (which rejects non-browser WSS with HTTP 403)."""
    from pf_intercept.headless.login import LoginResult, ServerEntry

    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        entries = [ServerEntry(s["server_host"], s.get("http_host", "")) for s in data.get("servers", [])]
        uid = int(data["uid"])
        rdkey = str(data["rdkey"])
    except FileNotFoundError:
        raise ResumeError(f"会话凭证不存在: {path}（请在设备上登录一次薅凭证）")
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        raise ResumeError(f"会话凭证无效 {path}: {exc}（请重新薅凭证）")
    if not entries:
        raise ResumeError(f"会话凭证里没有服务器列表: {path}")
    result = LoginResult(uid=uid, rdkey=rdkey, authorization=str(data.get("authorization", "")),
                         servers=entries, code=0, login_ip=str(data.get("login_ip", "")))
    return result, int(data.get("chnl", config.GAMEDATA_CHNL)), str(data.get("version", config.GAME_HTTP_VERSION))


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


async def _graceful_leave(session, leave_done: asyncio.Event, *, timeout: float = 45.0) -> None:
    """Leave the table cleanly before shutting down.

    Sends DelayLeaveRoomREQ (the client's "leave after this hand" request —
    a plain LeaveRoomREQ while a hand is in progress is rejected with 121) and
    waits for LeaveRoomRSP, so we don't abandon the seat for the server to time
    out."""
    try:
        rid = session.bridge.room_id_for_c2s(0)
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


async def _run(args: argparse.Namespace) -> int:
    # Bark 通知：headless 进程不经过 proxy 的 bot_worker，必须自己加载 key。
    if not args.no_notify:
        try:
            key = load_bark_key_file(_PROJECT_ROOT / "data" / "bark_key.txt")
            set_bark_key(key)
            print("[headless] Bark 通知已启用" if key else
                  "[headless] 未找到 data/bark_key.txt，通知关闭", file=sys.stderr)
        except Exception as exc:
            print(f"[headless] Bark key 加载失败: {exc}", file=sys.stderr)

    session_file = args.session_file or _DEFAULT_SESSION_FILE
    result, chnl, client_version = _resume_result(session_file)
    print(f"[headless] 恢复会话 {result.redacted()} chnl={chnl} ver={client_version}")
    # 按延迟选线（与客户端 Loginline 的 /ping 探测一致），低延迟优先连。
    result.servers = await _order_servers_by_latency(result.servers)

    if args.profit_lock_bb is not None:
        config.PROFIT_LOCK_BB_THRESHOLD = int(args.profit_lock_bb)

    observer = None
    if not args.no_web:
        from pf_entertainment.live_table import LiveTableObserver, start_live_web
        observer = LiveTableObserver(my_uid=result.uid)

    # Frame hook: feed the live observer and notice LeaveRoomRSP for graceful exit.
    leave_done = asyncio.Event()

    def on_frame(type_name, msg):
        if observer is not None:
            observer.observe(type_name, msg)
        if type_name == "pb.LeaveRoomRSP":
            leave_done.set()

    def _mk_session():
        return HeadlessSession(result, chnl=chnl, client_version=client_version,
                               max_auto_rebuy=args.max_auto_rebuy, on_frame=on_frame)

    # Connect, trying each server in turn (the :443 entry is WAF-blocked).
    session = _mk_session()
    if observer is not None:
        web_server = await start_live_web(
            observer, host=args.web_host, port=args.web_port,
            # Resolve the current session on every read: server fallback below
            # replaces it (and its bankroll baseline), so don't bind its method.
            bankroll_source=lambda: session.bankroll_dashboard(),
        )
        shown = args.web_host if args.web_host not in ("0.0.0.0", "") else "<本机IP>"
        print(f"[headless] 实时对局 Web: http://{shown}:{web_server.port}（手机同 WiFi 用本机局域网 IP 访问）")
    last_exc = None
    for idx in range(len(result.servers)):
        try:
            await session.connect(server_index=idx)
            break
        except Exception as exc:
            last_exc = exc
            print(f"[headless] server_index={idx} 失败: {exc}", file=sys.stderr)
            await session.close("retry next server")
            session = _mk_session()
    if not session.logged_in:
        print(f"[headless] 所有服务器登录失败: {last_exc}", file=sys.stderr)
        return 2
    if observer is not None:
        observer.set_connected(True)
    print(f"[headless] WSS 登录成功，心跳每 5s；日志 {_LOGS_DIR / 'headless.log'}")

    # Ctrl-C / SIGTERM → set stop, so we can leave the table before closing.
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop.set)
        except (NotImplementedError, RuntimeError):
            pass

    if args.bb > 0:
        await asyncio.sleep(1.0)
        await session.quick_start(big_blind=args.bb, buyin_bb=args.buyin_bb)
        print(f"[headless] 已请求进桌 bb={args.bb} buyin={args.bb * args.buyin_bb}；Ctrl-C 优雅退出（先离桌再关闭）")
        waiter = asyncio.create_task(session.wait_closed())
        stopper = asyncio.create_task(stop.wait())
        try:
            await asyncio.wait({waiter, stopper}, return_when=asyncio.FIRST_COMPLETED)
        except asyncio.CancelledError:
            stop.set()
        for t in (waiter, stopper):
            t.cancel()
        if stop.is_set() and session.connected:
            await _graceful_leave(session, leave_done)
    else:
        print(f"[headless] 只登录不进桌，保持 {args.hold:.0f}s 后断开")
        try:
            await asyncio.wait_for(stop.wait(), timeout=args.hold)
        except (asyncio.TimeoutError, asyncio.CancelledError):
            pass
    if observer is not None:
        observer.set_connected(False)
    await session.close("cli exit")
    print(f"[headless] 结束 {session.stats}")
    return 0


def main() -> int:
    args = _parse_args()
    _setup_logging(args.verbose)
    try:
        return asyncio.run(_run(args))
    except (ResumeError, SessionClosed) as exc:
        print(f"[headless] 失败: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
