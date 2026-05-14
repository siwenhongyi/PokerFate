from __future__ import annotations

import argparse
import asyncio

from pf_entertainment.client import send_json_command
from pf_entertainment.color_game import color_name
from pf_entertainment.color_strategy import LeastSeenColorPicker
from pf_entertainment.logger import get_logger


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the long-run finite Martingale ColorGame strategy.",
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=9021)
    parser.add_argument("--color", default="red")
    parser.add_argument(
        "--mode",
        choices=["adaptive", "fixed"],
        default="adaptive",
        help="adaptive=首局随机，之后按本次调用内最少出现颜色下注；fixed=使用 --color",
    )
    parser.add_argument("--base", type=int, default=1)
    parser.add_argument("--max-bet", type=int, default=100_000)
    parser.add_argument("--multiplier", type=int, default=2)
    parser.add_argument("--lvl", type=int, default=1)
    parser.add_argument("--timeout", type=float, default=20.0)
    parser.add_argument("--delay", type=float, default=1.5)
    parser.add_argument(
        "--cycles",
        type=int,
        default=1,
        help="Repeat independent Martingale cycles; each profitable cycle resets to base.",
    )
    return parser.parse_args()


def _bet_sequence(base: int, max_bet: int, multiplier: int) -> list[int]:
    if base <= 0:
        raise SystemExit("--base must be > 0")
    if max_bet < base:
        raise SystemExit("--max-bet must be >= --base")
    if multiplier <= 1:
        raise SystemExit("--multiplier must be > 1")

    bets: list[int] = []
    stake = base
    while stake <= max_bet:
        bets.append(stake)
        stake *= multiplier
    return bets


async def _run_one_cycle(
    args: argparse.Namespace,
    bets: list[int],
    cycle: int,
    picker: LeastSeenColorPicker,
) -> tuple[str, int, int, int, int]:
    log = get_logger()
    total_bet = 0
    total_return = 0
    total_net = 0
    played = 0
    if args.mode == "adaptive":
        pick = picker.choose()
        color_arg = str(pick.color_id)
        color_text = f"{color_name(pick.color_id)}({pick.reason},cycle)"
    else:
        color_arg = args.color
        color_text = str(args.color)

    for idx, stake in enumerate(bets, start=1):
        command = (
            f"color {color_arg}={stake} lvl={args.lvl} wait=1 json=1 "
            f"timeout={args.timeout}"
        )
        try:
            data = await send_json_command(
                command,
                host=args.host,
                port=args.port,
                timeout=args.timeout + 5,
            )
        except Exception as exc:
            log.exception("[长期最大-单色倍投] cycle=%s round=%s command failed", cycle, idx)
            print(f"C{cycle:02d} {idx:02d} ERR {exc}")
            return "error", played, total_bet, total_return, total_net
        if not data.get("ok"):
            log.warning(
                "[长期最大-单色倍投] cycle=%s round=%s failed response=%s",
                cycle,
                idx,
                data,
            )
            print(f"C{cycle:02d} {idx:02d} ERR {data}")
            return "error", played, total_bet, total_return, total_net

        played = idx
        summary = data["summary"]
        if args.mode == "adaptive":
            picker.observe(summary.get("ids", []))
        net = int(summary["net_profit"])
        total_bet += int(summary["total_bet"])
        total_return += int(summary["total_return"])
        total_net += net

        line = (
            f"C{cycle:02d} {idx:02d}/{len(bets)} color={color_text} stake={stake} "
            f"派彩={summary['total_return']} 本局={net:+d} "
            f"累计={total_net:+d} 开奖={summary['ids']}"
        )
        print(line)
        log.info("[长期最大-单色倍投] %s", line)

        if total_net > 0:
            final = (
                f"[长期最大-单色倍投] cycle={cycle} stop=profit attempts={played} "
                f"total_bet={total_bet} total_return={total_return} net={total_net:+d}"
            )
            print(final)
            log.info(final)
            return "profit", played, total_bet, total_return, total_net

        if args.delay > 0 and idx < len(bets):
            await asyncio.sleep(args.delay)

    final = (
        f"[长期最大-单色倍投] cycle={cycle} stop=max_bet attempts={played} "
        f"total_bet={total_bet} total_return={total_return} net={total_net:+d}"
    )
    print(final)
    log.info(final)
    return "max_bet", played, total_bet, total_return, total_net


async def _run(args: argparse.Namespace) -> int:
    log = get_logger()
    if args.cycles <= 0:
        raise SystemExit("--cycles must be > 0")

    bets = _bet_sequence(args.base, args.max_bet, args.multiplier)
    max_loss = sum(bets)

    log.info(
        "[长期最大-单色倍投] start mode=%s color=%s lvl=%s base=%s max_bet=%s levels=%s max_loss=%s cycles=%s delay=%s",
        args.mode,
        args.color,
        args.lvl,
        args.base,
        args.max_bet,
        len(bets),
        max_loss,
        args.cycles,
        args.delay,
    )
    print(
        f"[长期最大-单色倍投] mode={args.mode} color={args.color} base={args.base} max_bet={args.max_bet} "
        f"levels={len(bets)} max_loss={max_loss} cycles={args.cycles} delay={args.delay}"
    )

    picker = LeastSeenColorPicker()
    total_attempts = 0
    total_bet = 0
    total_return = 0
    total_net = 0
    profit_cycles = 0
    status = "done"

    for cycle in range(1, args.cycles + 1):
        status, played, cycle_bet, cycle_return, cycle_net = await _run_one_cycle(
            args,
            bets,
            cycle,
            picker,
        )
        total_attempts += played
        total_bet += cycle_bet
        total_return += cycle_return
        total_net += cycle_net
        if status == "profit":
            profit_cycles += 1
            continue
        break

    final = (
        f"[长期最大-单色倍投] repeat_done status={status} "
        f"profit_cycles={profit_cycles}/{args.cycles} attempts={total_attempts} "
        f"total_bet={total_bet} total_return={total_return} net={total_net:+d}"
    )
    print(final)
    log.info(final)
    if status == "error":
        return 1
    return 0


def main() -> None:
    raise SystemExit(asyncio.run(_run(_parse_args())))


if __name__ == "__main__":
    main()
