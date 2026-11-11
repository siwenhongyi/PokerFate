"""Standalone entry point: harvest/refresh ``data/headless_session.json``.

Run this once to get the headless (pure-API) client working for the first
time, and again whenever it reports a stale/expired session (``ResumeError``
in ``pf_intercept.headless.__main__``, or ``auth_failed`` in the reward log —
the saved rdkey/JWT is good for roughly 30 days).

There is no pure-API way to log in ourselves: /login requires a risk-control
token minted by the game client's own YiDun SDK (see
pf_reverse/output/lua/src/sdk/YiDunHelper.lua and the "风控" row in
pf_reverse/REVERSE_NOTES.md), which this project does not and cannot
reimplement. So the only way to obtain a valid session is to let a *real*
device log in once through a MITM proxy and capture the result — that's all
this script automates:

    1. start mitmdump with pf_reverse/capture_login.py mounted
    2. print the phone-side setup steps (proxy host:port, CA install)
    3. wait for data/headless_session.json to be (re)written
    4. stop mitmdump and exit — from here on, headless play needs no device

Usage (also runnable as-is from PyCharm, no package context needed):

    python -m pf_intercept.headless.harvest_session
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_SESSION_FILE = _PROJECT_ROOT / "data" / "headless_session.json"
_CAPTURE_ADDON = _PROJECT_ROOT / "pf_reverse" / "capture_login.py"

# Real candidate login addresses, straight from the reversed client config —
# used only to probe whether this Mac can reach the game directly. NOT used
# to filter what mitmdump intercepts (see capture_login.py for why a host
# allow-list is the wrong tool for that): some of these are bare IPs with no
# hostname, pf_reverse/output/lua/src/app/Constants.lua, G_HTTP_URL / _2/_3/_4.
_PROBE_HOSTS = [
    ("ga-foreign.poker-fate.com", 443),
    ("awsb-entry.poker-fate.com", 443),
    ("8.163.49.33", 8888),
    ("121.196.174.32", 8888),
]

_PROXY_ENV_VARS = ("https_proxy", "HTTPS_PROXY", "all_proxy", "ALL_PROXY", "http_proxy", "HTTP_PROXY")


def _is_lan_ipv4(ip: str) -> bool:
    """True RFC1918 only — rejects VPN/TUN virtual adapters (e.g. Clash/Tailscale
    style 198.18.0.0/15) that a UDP-connect probe can pick up instead of the
    real Wi-Fi interface when one of those is active."""
    try:
        parts = [int(p) for p in ip.split(".")]
    except ValueError:
        return False
    if len(parts) != 4 or any(p < 0 or p > 255 for p in parts):
        return False
    return parts[0] == 10 or (parts[0] == 192 and parts[1] == 168) or (parts[0] == 172 and 16 <= parts[1] <= 31)


def _lan_ip_sort_key(ip: str) -> tuple[int, str]:
    if ip.startswith("192.168."):
        return 0, ip
    if ip.startswith("10."):
        return 1, ip
    return 2, ip  # 172.16-31.x


def _local_lan_ips() -> list[str]:
    """Best-effort LAN IPv4 candidates for the phone-side setup instructions,
    best guess first.

    Same approach as pf_entertainment.runtime._local_lan_ipv4_addresses:
    the "UDP-connect and read getsockname" trick picks the OS's chosen route,
    which can be a VPN/TUN virtual adapter rather than the Wi-Fi NIC the phone
    needs — so results are filtered down to real RFC1918 ranges before use.

    This can still guess wrong (multiple real interfaces up at once, or a VPN
    that happens to tunnel through a RFC1918 range too) — there is no fully
    reliable cross-platform way to ask "which address is my Wi-Fi" without
    shelling out to OS-specific tools (macOS ifconfig/networksetup, Linux
    iproute2, Windows ipconfig all report differently, and none of them labels
    an interface as "the one your phone can reach" either). When this guesses
    wrong, pass --lan-ip explicitly."""
    candidates: set[str] = set()
    for probe in (("223.5.5.5", 80), ("8.8.8.8", 80)):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(probe)
                candidates.add(s.getsockname()[0])
        except OSError:
            pass
    try:
        candidates.update(socket.gethostbyname_ex(socket.gethostname())[2])
    except OSError:
        pass
    return sorted((ip for ip in candidates if _is_lan_ipv4(ip)), key=_lan_ip_sort_key)


def _direct_reachable(timeout: float = 3.0) -> bool:
    for host, port in _PROBE_HOSTS:
        try:
            with socket.create_connection((host, port), timeout=timeout):
                return True
        except OSError:
            continue
    return False


def _detect_upstream(explicit: str | None) -> str | None:
    """Decide whether mitmdump needs --mode upstream:<url> to reach the game.

    Only adds one when a direct connection demonstrably doesn't work, and
    then only by reusing a proxy already configured in this shell — never a
    guessed port."""
    if explicit:
        return explicit
    if _direct_reachable():
        print("[harvest] 本机可直连游戏服务器，不使用 upstream 代理")
        return None
    for var in _PROXY_ENV_VARS:
        val = os.environ.get(var)
        if val:
            print(f"[harvest] 本机直连游戏服务器失败，复用环境变量 {var}={val} 作为 upstream")
            return val
    print(
        "[harvest] 本机直连游戏服务器失败，且没有在环境变量里找到代理"
        f"（{'/'.join(_PROXY_ENV_VARS)}）。\n"
        "          如果你平时要走代理/VPN 才能连游戏，先在当前终端 export 一个，"
        "再重跑本脚本；否则抓包大概率会卡住。",
        file=sys.stderr,
    )
    return None


def _build_cmd(mitmdump: str, port: int, upstream: str | None) -> list[str]:
    from pf_intercept.config import MITM_IGNORE_HOSTS

    cmd = [
        mitmdump,
        "--listen-host", "0.0.0.0",
        "--listen-port", str(port),
        "--ignore-hosts", MITM_IGNORE_HOSTS,
        "-s", str(_CAPTURE_ADDON),
    ]
    if upstream:
        cmd += ["--mode", f"upstream:{upstream}", "--ssl-insecure"]
    return cmd


def _session_fingerprint(path: Path) -> tuple[float, int | None]:
    """(mtime, uid) so we notice a *new* capture even if mtime granularity ties."""
    try:
        st = path.stat()
    except FileNotFoundError:
        return 0.0, None
    try:
        uid = json.loads(path.read_text(encoding="utf-8")).get("uid")
    except Exception:
        uid = None
    return st.st_mtime, uid


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="薅一次 headless_session.json（首次使用或凭证过期时跑一次）")
    p.add_argument("--port", type=int, default=8080, help="mitmdump 监听端口，默认 8080")
    p.add_argument("--timeout-min", type=float, default=10.0, help="等待抓到登录的超时分钟数，默认 10")
    p.add_argument("--upstream", default=None, metavar="URL",
                   help="强制指定 upstream 代理（跳过自动探测），例如 http://127.0.0.1:7890")
    p.add_argument("--mitmdump", default=None, help="mitmdump 可执行文件路径（默认用 PATH 里找到的）")
    p.add_argument("--lan-ip", default=None, metavar="IP",
                   help="手动指定给手机填的局域网 IP（自动探测猜错/有多个网卡时用）")
    return p.parse_args()


def main() -> int:
    args = _parse_args()

    mitmdump = args.mitmdump or shutil.which("mitmdump")
    if not mitmdump:
        print("[harvest] 没找到 mitmdump，先安装: .venv/bin/python -m pip install mitmproxy", file=sys.stderr)
        return 1

    upstream = _detect_upstream(args.upstream)
    cmd = _build_cmd(mitmdump, args.port, upstream)
    before = _session_fingerprint(_SESSION_FILE)

    lan_ips = _local_lan_ips()
    if args.lan_ip:
        lan_ip = args.lan_ip
    elif lan_ips:
        lan_ip = lan_ips[0]
        if len(lan_ips) > 1:
            print(f"[harvest] 探测到多个局域网地址 {lan_ips}，默认用第一个；不对的话用 --lan-ip 手动指定")
    else:
        lan_ip = "<本机局域网IP，自动探测失败，用 ifconfig/ipconfig 查到后加 --lan-ip 重跑>"
    print(f"""
[harvest] 启动抓包代理: {' '.join(cmd)}

手机操作:
  1. 手机 Wi-Fi 设置 -> 代理 -> 手动，填 {lan_ip} : {args.port}
  2. 首次使用本机 mitmproxy 时，手机浏览器访问 http://mitm.it 装根证书
  3. 正常打开 PokerFate app，用真实账号登录一次
     （看到下面打印 "已自动更新凭证" 就说明成功了，这个脚本会自动退出）
""")

    proc = subprocess.Popen(cmd)
    deadline = time.monotonic() + args.timeout_min * 60
    try:
        while time.monotonic() < deadline:
            if proc.poll() is not None:
                print(f"[harvest] mitmdump 提前退出 (code={proc.returncode})，检查上面的输出", file=sys.stderr)
                return 1
            now = _session_fingerprint(_SESSION_FILE)
            if now != before and now[1] is not None:
                print(f"[harvest] ✅ 凭证已更新 uid={now[1]} -> {_SESSION_FILE}")
                print("[harvest] 接下来可以: python -m pf_intercept.headless --bb 10000 --buyin-bb 50")
                return 0
            time.sleep(1.0)
        print(f"[harvest] 等待超时（{args.timeout_min:.0f} 分钟），没有抓到新的登录", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\n[harvest] 用户中断")
        return 130
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()


if __name__ == "__main__":
    sys.exit(main())
