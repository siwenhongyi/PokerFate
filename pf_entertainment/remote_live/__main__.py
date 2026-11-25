"""python -m pf_entertainment.remote_live {serve,ingest,publish,deploy}."""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import signal
import subprocess
import sys
from pathlib import Path

from .config import DEFAULT_CONFIG


async def _publish(args):
    from .publisher import RemotePublisher, http_money_source, http_source
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set)
    publisher = RemotePublisher(http_source(args.source_url), money_source=http_money_source(args.source_url),
                                config_path=args.config).start()
    try:
        while not stop.is_set() and not publisher.task.done():
            if args.owner_pid:
                try:
                    os.kill(args.owner_pid, 0)
                except ProcessLookupError:
                    break
            try:
                await asyncio.wait_for(stop.wait(), timeout=0.5)
            except asyncio.TimeoutError:
                pass
    finally:
        await publisher.close()


def main():
    parser = argparse.ArgumentParser(description="独立实时对局 Web / SSH 上传 / 部署")
    commands = parser.add_subparsers(dest="command", required=True)
    serve = commands.add_parser("serve", help="VPS 上运行，只读 HTTP + 本地 Unix 上传 socket")
    serve.add_argument("--socket", type=Path, default=Path("/run/pokerfate-live/ingest.sock"))
    serve.add_argument("--port", type=int, default=9023)
    serve.add_argument("--ttl", type=float, default=15)
    ingest = commands.add_parser("ingest", help="经 SSH stdin 传送快照，非公网接口")
    ingest.add_argument("--socket", type=Path, default=Path("/run/pokerfate-live/ingest.sock"))
    publish = commands.add_parser("publish", help="给正在运行的 bot 添加独立上传进程，无需重启 bot")
    publish.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    publish.add_argument("--source-url", default="http://127.0.0.1:9022/api/live")
    publish.add_argument("--owner-pid", type=int, help="此 bot 退出后上传进程也退出")
    deploy = commands.add_parser("deploy", help="通过 SSH 传输最小部署包并安装/更新 VPS 服务")
    deploy.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    try:
        if args.command == "serve":
            from .server import LiveServer
            from .viewer_auth import CREDENTIALS, SESSIONS, ViewerAuth
            if not 3 <= args.ttl <= 120:
                parser.error("ttl 必须在 3–120 秒")
            server = LiveServer(args.socket, auth=ViewerAuth(CREDENTIALS, SESSIONS), port=args.port, ttl=args.ttl)
            for sig in (signal.SIGINT, signal.SIGTERM):
                signal.signal(sig, lambda *_: server.stop.set())
            server.start()
            logging.info("live viewer listening on loopback:%s; ttl=%ss", server.http.server_port, args.ttl)
            try:
                server.stop.wait()
            finally:
                server.close()
        elif args.command == "ingest":
            from .server import relay_stdin
            relay_stdin(args.socket, sys.stdin.buffer, sys.stdout.buffer)
        elif args.command == "publish":
            asyncio.run(_publish(args))
        else:
            from .deploy import deploy
            deploy(args.config)
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        logging.error("%s: %s", type(exc).__name__, exc)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
