# 用法：先启动 proxy 并让设备连上，再执行：
#   .venv/bin/python -m pf_entertainment.strategy_pinball_task 20
# 固定发送最低档弹珠请求：lvl=1, per_bet=1000, ball_num=1。
# 只保留“次数”参数；任意错误或超时都会立即停止。

from __future__ import annotations

import argparse
import asyncio

from pf_entertainment.client import send_json_command
from pf_entertainment.logger import get_logger


HOST = "127.0.0.1"
PORT = 9021
TIMEOUT = 20.0
DELAY = 1.5


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run minimum-stake Pinball task plays.",
    )
    parser.add_argument("count", type=int, help="执行次数")
    return parser.parse_args()


async def _run(args: argparse.Namespace) -> int:
    if args.count <= 0:
        raise SystemExit("次数必须大于 0")

    log = get_logger()
    total_bet = 0
    total_return = 0
    total_net = 0
    played = 0

    start = f"[弹珠任务] start count={args.count} per_bet=1000 ball_num=1 delay={DELAY}"
    print(start)
    log.info(start)

    for idx in range(1, args.count + 1):
        try:
            data = await send_json_command(
                f"pinball wait=1 json=1 timeout={TIMEOUT}",
                host=HOST,
                port=PORT,
                timeout=TIMEOUT + 5,
            )
        except Exception as exc:
            log.exception("[弹珠任务] round=%s command failed", idx)
            print(f"{idx:02d}/{args.count} ERR {exc}")
            return 1

        if not data.get("ok"):
            log.warning("[弹珠任务] round=%s failed response=%s", idx, data)
            print(f"{idx:02d}/{args.count} ERR {data}")
            return 1

        played += 1
        summary = data["summary"]
        bet = int(summary["total_bet"])
        reward = int(summary["total_return"])
        net = int(summary["net_profit"])
        total_bet += bet
        total_return += reward
        total_net += net

        balls = summary.get("balls", [])
        ball_text = ", ".join(
            f"出口:{item['export_id']} 奖励:{item['reward']} 盈利:{item['profit']:+d}"
            for item in balls
        ) or "-"
        line = (
            f"{idx:02d}/{args.count} 投入={bet} 奖励={reward} "
            f"盈利={net:+d} 累计={total_net:+d} {ball_text}"
        )
        print(line)
        log.info("[弹珠任务] %s", line)

        if idx < args.count:
            await asyncio.sleep(DELAY)

    final = (
        f"[弹珠任务] done played={played}/{args.count} "
        f"total_bet={total_bet} total_return={total_return} net={total_net:+d}"
    )
    print(final)
    log.info(final)
    return 0


def main() -> None:
    raise SystemExit(asyncio.run(_run(_parse_args())))


if __name__ == "__main__":
    main()
