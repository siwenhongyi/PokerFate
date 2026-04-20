"""
PokerFate 一键启动器

整合三个服务到一个命令：
  1. mitmweb   — HTTP 代理，拦截登录响应并强制域名连接
  2. dns_server — 劫持游戏域名 DNS 到本机（需 root/管理员权限）
  3. proxy     — WSS MITM 代理 + Bot 决策引擎

用法:
    # macOS / Linux（DNS 部分自动请求 sudo）
    python -m pf_intercept.launcher

    # Windows（DNS 部分通过 UAC 弹窗提权）
    python -m pf_intercept.launcher

    # 透传 proxy 参数
    python -m pf_intercept.launcher --max-auto-rebuy 3 --profit-lock-bb 200

    # 跳过 mitmweb（已在别处运行、或不需要）
    python -m pf_intercept.launcher --no-mitmweb

    # 跳过 dns_server（用 hosts 文件代替）
    python -m pf_intercept.launcher --no-dns
"""

from __future__ import annotations

import asyncio
import ctypes  # used only on Windows; stdlib, harmless on other platforms
import logging
import os
import platform
import pty
import shlex
import shutil
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

from pf_intercept.proxy import _parse_proxy_args, main as proxy_main

log = logging.getLogger(__name__)

_IS_WIN = platform.system() == "Windows"
_IS_MAC = platform.system() == "Darwin"
_PROJECT_ROOT = Path(__file__).resolve().parent.parent

# mitmweb 默认参数
_MITMWEB_PORT = 8080
_MITMWEB_IGNORE = "xiaomi.com|xiaomi.net|miui.com|aliyuncs.com"
_FORCE_DOMAIN_SCRIPT = _PROJECT_ROOT / "pf_reverse" / "force_domain.py"

# 子进程引用（模块级，供 cleanup 访问）
_mitmweb_proc: subprocess.Popen | None = None
_dns_proc: subprocess.Popen | None = None


# ── 工具函数 ─────────────────────────────────────────────────────────────────


def _has_tty() -> bool:
    try:
        return os.isatty(sys.stdin.fileno())
    except Exception:
        return False


def _venv_path() -> str:
    """返回包含 venv bin 目录的 PATH。"""
    env_path = os.environ.get("PATH", "")
    venv_bin = str(Path(sys.executable).parent)
    if venv_bin not in env_path:
        env_path = f"{venv_bin}:{env_path}"
    return env_path


def _port_listening(port: int) -> bool:
    """检测本机某端口是否已有进程监听。"""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        try:
            s.bind(("0.0.0.0", port))
            return False  # 能 bind 说明没人占
        except OSError:
            return True   # bind 失败说明已被占用


def _stop_subprocess(proc: subprocess.Popen | None, name: str) -> None:
    if proc is None or proc.poll() is not None:
        return
    print(f"[launcher] 停止 {name} (pid={proc.pid})")
    try:
        if _IS_WIN:
            proc.terminate()
        else:
            os.kill(proc.pid, signal.SIGTERM)
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=3)
    except Exception:
        pass


# ── mitmweb 子进程 ───────────────────────────────────────────────────────────


def _start_mitmweb() -> subprocess.Popen | None:
    mitmweb = shutil.which("mitmweb")
    if not mitmweb:
        print("[launcher] mitmweb 未找到，跳过（pip install mitmproxy）")
        return None

    cmd = [
        mitmweb,
        "--listen-port", str(_MITMWEB_PORT),
        "--ignore-hosts", _MITMWEB_IGNORE,
        "-s", str(_FORCE_DOMAIN_SCRIPT),
        "--no-web-open-browser",
    ]
    print(f"[launcher] 启动 mitmweb  port={_MITMWEB_PORT}")
    # Redirect mitmweb output to a file under logs/. Review noted that the
    # original PIPE/STDOUT combo leaked nothing to the user; but DEVNULL
    # silenced it entirely, making force_domain.py exceptions invisible
    # and hurting debuggability. A log file preserves diagnostics without
    # cluttering the interactive launcher output.
    logs_dir = _PROJECT_ROOT / "logs"
    try:
        logs_dir.mkdir(exist_ok=True)
    except OSError:
        logs_dir = None
    if logs_dir is not None:
        log_path = logs_dir / "mitmweb.log"
        log_fh = open(log_path, "w", buffering=1)
        proc = subprocess.Popen(
            cmd,
            stdout=log_fh,
            stderr=subprocess.STDOUT,
        )
        print(f"[launcher] mitmweb 日志 → {log_path}")
    else:
        # Fallback when logs/ isn't writable (rare): keep output visible so
        # at least errors surface.
        proc = subprocess.Popen(cmd)
    print(f"[launcher] mitmweb 已启动  pid={proc.pid}")
    return proc


# ── DNS 子进程（以 root 启动） ───────────────────────────────────────────────


def _start_dns_elevated() -> subprocess.Popen | None:
    """以 root/管理员权限启动 dns_server 子进程。

    主进程保持普通用户运行，只有 DNS 需要 root（端口 53）。
    macOS/Linux 走 PTY + sudo 路径（触发 Touch ID / 密码提示）。
    Windows 走 UAC 提权，该分支**必须**在 sudo 路径之前检查 —
    否则 Windows 会掉到 `os.geteuid()`（Unix 专属）直接抛 AttributeError。

    已知局限：Windows UAC 路径 ShellExecuteW 启动的独立窗口进程不返回
    Popen 句柄（`return None`）。launcher `_cleanup` 因此不会 kill 它，
    Ctrl+C 退出后 DNS 服务窗口变成孤儿需要用户手动关闭。
    """
    python = sys.executable
    dns_cmd = [python, "-m", "pf_intercept.dns_server"]

    if _IS_WIN:
        print("[launcher] 启动 dns_server（UAC 提权）...")
        ctypes.windll.shell32.ShellExecuteW(
            None, "runas", python, "-m pf_intercept.dns_server", None, 1,
        )
        print("[launcher] dns_server UAC 已请求（独立窗口运行）")
        return None

    env_path = _venv_path()

    # sudo/root 下 cwd 与 PYTHONPATH 常与交互 shell 不一致，需显式带上项目根以便 -m 能解析包
    env = os.environ.copy()
    root = str(_PROJECT_ROOT)
    pp = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = root if not pp else f"{root}{os.pathsep}{pp}"

    if os.geteuid() == 0:
        print("[launcher] 启动 dns_server（当前已是 root）")
        return subprocess.Popen(dns_cmd, env=env)

    # 统一方案：PTY + sudo
    # PTY 让 sudo 看到终端 → PAM 触发 Touch ID（如果配了 pam_tid.so）
    # 终端和 IDE 都走这条路径
    print("[launcher] 启动 dns_server（sudo）...")
    master_fd, slave_fd = pty.openpty()
    proc = subprocess.Popen(
        ["sudo", "-E", "env", f"PATH={env_path}", f"PYTHONPATH={env['PYTHONPATH']}"] + dns_cmd,
        stdin=slave_fd,
        stdout=slave_fd,
        stderr=slave_fd,
        close_fds=True,
    )
    os.close(slave_fd)

    # 等待 port 53 就绪 或 进程退出（授权失败/取消）
    for i in range(30):
        time.sleep(1)
        if _port_listening(53):
            print(f"[launcher] dns_server 已启动  pid={proc.pid}")
            os.close(master_fd)
            return proc
        if proc.poll() is not None:
            # sudo 退出了，读取 PTY 输出看看什么原因
            try:
                output = os.read(master_fd, 4096).decode(errors="replace").strip()
            except OSError:
                output = ""
            os.close(master_fd)
            print(f"[launcher] dns_server 启动失败: {output or 'sudo 退出'}")
            return None

    os.close(master_fd)
    print("[launcher] dns_server 启动超时（30s）")
    proc.kill()
    return None


# ── 参数解析 ─────────────────────────────────────────────────────────────────


def _parse_launcher_args() -> tuple[bool, bool, list[str]]:
    """解析 launcher 自有参数，剩余的透传给 proxy。"""
    skip_mitmweb = False
    skip_dns = False
    proxy_argv: list[str] = []

    for arg in sys.argv[1:]:
        if arg == "--no-mitmweb":
            skip_mitmweb = True
        elif arg == "--no-dns":
            skip_dns = True
        else:
            proxy_argv.append(arg)

    return skip_mitmweb, skip_dns, proxy_argv


# ── 主流程 ───────────────────────────────────────────────────────────────────


async def _run(skip_mitmweb: bool, skip_dns: bool, proxy_argv: list[str]) -> None:
    global _mitmweb_proc, _dns_proc

    # ── 1. mitmweb（子进程，不需要 root） ──
    if not skip_mitmweb:
        _mitmweb_proc = _start_mitmweb()

    # ── 2. dns_server（子进程，需要 root，自动提权） ──
    if not skip_dns:
        _dns_proc = _start_dns_elevated()
        if _dns_proc is None:
            print("[launcher] DNS 服务未启动，proxy 仍将启动（需 hosts 文件生效）")

    # ── 3. Proxy（当前进程，不需要 root） ──
    saved_argv = sys.argv
    sys.argv = ["proxy"] + proxy_argv
    try:
        args = _parse_proxy_args()
    finally:
        sys.argv = saved_argv

    await proxy_main(
        max_auto_rebuy=args.max_auto_rebuy,
        profit_lock_bb=args.profit_lock_bb,
        spoof_role_id=args.role_id,
        spoof_skin_id=args.skin_id,
        use_range_equity=(args.equity_mode == "range"),
    )


def _cleanup() -> None:
    _stop_subprocess(_dns_proc, "dns_server")
    _stop_subprocess(_mitmweb_proc, "mitmweb")


def main() -> None:
    skip_mitmweb, skip_dns, proxy_argv = _parse_launcher_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-5s  %(message)s",
        datefmt="%H:%M:%S",
    )

    try:
        asyncio.run(_run(skip_mitmweb, skip_dns, proxy_argv))
    except KeyboardInterrupt:
        print("\n[launcher] Ctrl+C，正在停止所有服务...")
    finally:
        _cleanup()

    print("[launcher] 已退出")


if __name__ == "__main__":
    main()
