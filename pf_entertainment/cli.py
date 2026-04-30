from __future__ import annotations

import argparse
import asyncio
import sys

from pf_entertainment.client import send_command


async def _send(host: str, port: int, command: str) -> int:
    try:
        response = await send_command(command, host=host, port=port)
    except OSError as exc:
        print(f"连接娱乐游戏指令端口失败 {host}:{port}: {exc}", file=sys.stderr)
        return 2
    print(response)
    return 0


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Send a local entertainment-game command to the running proxy.",
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=9021)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    command = " ".join(args.command).strip() or "help"
    raise SystemExit(asyncio.run(_send(args.host, args.port, command)))


if __name__ == "__main__":
    main()
