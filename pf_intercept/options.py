"""Run options shared by the direct client and the MITM transport."""
from __future__ import annotations

import argparse
from dataclasses import dataclass, fields
from pathlib import Path


@dataclass(frozen=True)
class RunOptions:
    bb: int = 0
    buyin_bb: int = 100
    max_auto_rebuy: int = 1
    profit_lock_bb: int = 200
    topup_below_bb: int = 70
    stakes: str = ""
    session_file: Path | None = None
    no_notify: bool = False
    no_auto_rewards: bool = False
    no_task_hands: bool = False
    no_web: bool = False
    no_remote_live: bool = False
    web_host: str = "0.0.0.0"
    web_port: int = 9022
    verbose: bool = False
    off: tuple[str, ...] = ()

    @classmethod
    def from_namespace(cls, args):
        from pf_intercept.headless.lobby import switches
        defaults = cls()
        values = {f.name: getattr(args, f.name, getattr(defaults, f.name)) for f in fields(cls)}
        # Older programmatic callers may pass None for a defaulted numeric option.
        for name in ("profit_lock_bb", "topup_below_bb"):
            if values[name] is None:
                values[name] = getattr(defaults, name)
        values["off"] = tuple(flag for flag, _ in switches()
                              if getattr(args, "no_" + flag.replace("-", "_"), False))
        return cls(**values)


def nonnegative(value):
    number = int(value)
    if number < 0:
        raise argparse.ArgumentTypeError("必须大于或等于 0")
    return number


def positive(value):
    number = nonnegative(value)
    if not number:
        raise argparse.ArgumentTypeError("必须大于 0")
    return number


def web_port(value):
    number = nonnegative(value)
    if number > 65535:
        raise argparse.ArgumentTypeError("端口必须在 0–65535")
    return number


def stake_order(value):
    from pf_intercept.table_policy import configured_policy
    try:
        configured_policy(10000, stakes=value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc
    return value


def add_run_arguments(parser):
    from pf_intercept.headless.lobby import switches
    d = RunOptions()
    parser.add_argument("--stop", action="store_true", help="通过本入口的 PID 锁请求优雅停止")
    parser.add_argument("--session-file", type=Path, default=d.session_file,
                        help="登录捕获文件，默认 local/secrets/headless_session.json")
    parser.add_argument("--bb", type=nonnegative, default=d.bb,
                        help="首选现金桌大盲；代理不传时使用客户端首次入座场次")
    parser.add_argument("--buyin-bb", type=positive, default=d.buyin_bb, help="自动匹配目标买入深度，默认 100BB")
    parser.add_argument("--max-auto-rebuy", type=int, choices=range(21), metavar="N", default=d.max_auto_rebuy,
                        help="净亏损上限 (1+N)×100BB，0–20，默认 1")
    parser.add_argument("--profit-lock-bb", type=positive, default=d.profit_lock_bb, help="锁仓阈值，默认 200BB")
    parser.add_argument("--topup-below-bb", type=nonnegative, default=d.topup_below_bb,
                        help="补码触发线，默认 70BB，0 关闭")
    parser.add_argument("--stakes", type=stake_order, default=d.stakes, help="场次偏好，如 10000,5000")
    parser.add_argument("--no-notify", action="store_true", help="关闭 Bark 通知")
    parser.add_argument("--no-auto-rewards", action="store_true", help="关闭大厅自动化")
    for flag, text in switches():
        parser.add_argument(f"--no-{flag}", action="store_true", help=text)
    parser.add_argument("--no-task-hands", action="store_true", help="关闭奥马哈 / AOF 任务手数")
    parser.add_argument("--no-web", action="store_true", help="关闭本机 Web")
    parser.add_argument("--no-remote-live", action="store_true", help="关闭远程 Live 上传")
    parser.add_argument("--web-host", default=d.web_host, help="Web 监听地址，默认 0.0.0.0")
    parser.add_argument("--web-port", type=web_port, metavar="PORT", default=d.web_port)
    parser.add_argument("-v", "--verbose", action="store_true", help="显示调试输出")
    return parser
