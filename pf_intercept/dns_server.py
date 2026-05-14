"""
Fake DNS server for Android MITM mode.

PREFERRED_WSS_HOSTS:
  - A 记录 → proxy_ip（本机 IPv4）
  - AAAA 记录 → NODATA（避免客户端拿到真实 IPv6 后直连，绕过仅监听 IPv4 的代理）

其他域名 → 转发给上游 DNS。

Usage:
    sudo python -m pf_intercept.dns_server
    sudo python -m pf_intercept.dns_server 192.168.1.100
"""

from __future__ import annotations

import asyncio
import ipaddress
import logging
import os
import signal
import socket
import struct
import subprocess
import sys
import time

from pf_intercept.config import EXTERNAL_DNS_SERVERS, PREFERRED_WSS_HOSTS

log = logging.getLogger(__name__)


# ── 系统 DNS 探测 ──────────────────────────────────────────────────────────────

def _port53_occupied() -> bool:
    """Return True if UDP 53 is currently occupied."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.bind(("0.0.0.0", 53))
        return False
    except OSError:
        return True


def _port53_pids() -> list[int]:
    """Best-effort list of pids currently holding port 53."""
    try:
        out = subprocess.check_output(
            ["lsof", "-nP", "-t", "-i:53"],
            text=True,
            stderr=subprocess.DEVNULL,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return []
    pids: set[int] = set()
    for line in out.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            pids.add(int(line))
        except ValueError:
            continue
    return sorted(pids)


def _pid_command(pid: int) -> str:
    try:
        out = subprocess.check_output(
            ["ps", "-o", "command=", "-p", str(pid)],
            text=True,
            stderr=subprocess.DEVNULL,
        )
        return out.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return ""


def _is_stale_dns_server(cmd: str) -> bool:
    return "pf_intercept.dns_server" in cmd


def _kill_pids(pids: list[int]) -> None:
    if not pids:
        return

    def _alive(pid: int) -> bool:
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False

    alive = [pid for pid in pids if _alive(pid)]
    if not alive:
        return

    for pid in alive:
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError:
            pass

    deadline = time.time() + 1.5
    while time.time() < deadline:
        alive = [pid for pid in alive if _alive(pid)]
        if not alive:
            return
        time.sleep(0.1)

    for pid in alive:
        try:
            os.kill(pid, signal.SIGKILL)
        except OSError:
            pass


def _cleanup_stale_port53_owner() -> None:
    """Root preflight: kill stale pf_intercept.dns_server occupying port 53."""
    if not hasattr(os, "geteuid") or os.geteuid() != 0:
        return
    if not _port53_occupied():
        return

    me = os.getpid()
    stale: list[int] = []
    foreign: list[tuple[int, str]] = []
    for pid in _port53_pids():
        if pid == me:
            continue
        cmd = _pid_command(pid)
        if _is_stale_dns_server(cmd):
            stale.append(pid)
        else:
            foreign.append((pid, cmd))

    if stale:
        log.warning("port 53 occupied by stale dns_server pids=%s, killing", stale)
        _kill_pids(stale)

    if _port53_occupied():
        if foreign:
            desc = ", ".join(
                f"{pid}:{cmd or '<unknown>'}" for pid, cmd in foreign[:4]
            )
            log.warning("port 53 still occupied by non-dns_server process(es): %s", desc)
        else:
            log.warning("port 53 still occupied after stale cleanup")


def _system_dns() -> str | None:
    """从 /etc/resolv.conf 读取系统当前使用的 DNS 服务器。"""
    try:
        with open("/etc/resolv.conf") as f:
            for line in f:
                parts = line.strip().split()
                if len(parts) >= 2 and parts[0] == "nameserver":
                    ip = parts[1]
                    # 跳过本机回环（避免循环）
                    if not ip.startswith("127."):
                        return ip
    except Exception:
        pass
    return None


def _upstream_dns_list() -> list[str]:
    """返回上游 DNS 列表：系统 DNS 优先，然后是 EXTERNAL_DNS_SERVERS（去重）。"""
    result: list[str] = []
    sys_dns = _system_dns()
    if sys_dns:
        result.append(sys_dns)
    for s in EXTERNAL_DNS_SERVERS:
        if s not in result:
            result.append(s)
    return result


# ── 本机 IP 自动探测 ──────────────────────────────────────────────────────────

def _ipv4_probe_candidates() -> list[str]:
    """用于 UDP connect 探测的本机出口地址：仅 IPv4 字面量。

    /etc/resolv.conf 里的 nameserver 可能是主机名（未解析则 gaierror）、IPv6 等，
    不能交给 AF_INET 的 connect；依次尝试系统 IPv4 + 配置的公共 DNS。
    """
    out: list[str] = []
    sys_dns = _system_dns()
    if sys_dns:
        try:
            ipaddress.IPv4Address(sys_dns)
            out.append(sys_dns)
        except ValueError:
            pass
    for s in EXTERNAL_DNS_SERVERS:
        if s not in out:
            out.append(s)
    return out


def _local_ip() -> str:
    """探测本机对外 IP（不发包，仅用于获取路由出口地址）。"""
    for probe in _ipv4_probe_candidates():
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect((probe, 53))
                return s.getsockname()[0]
        except OSError:
            continue
    raise RuntimeError(
        "无法自动探测本机 IPv4，请显式传入局域网 IP："
        "sudo python -m pf_intercept.dns_server <你的本机IP>"
    )


# ── 最小化 DNS wire-format 解析 ───────────────────────────────────────────────

def _parse_name(data: bytes, offset: int) -> tuple[str, int]:
    labels: list[str] = []
    while True:
        length = data[offset]
        if length == 0:
            offset += 1
            break
        if (length & 0xC0) == 0xC0:          # 压缩指针
            ptr = ((length & 0x3F) << 8) | data[offset + 1]
            label, _ = _parse_name(data, ptr)
            labels.append(label)
            offset += 2
            break
        offset += 1
        labels.append(data[offset: offset + length].decode())
        offset += length
    return ".".join(labels), offset


def _query_name(data: bytes) -> str | None:
    try:
        name, _ = _parse_name(data, 12)
        return name.rstrip(".")
    except Exception:
        return None


def _is_a_query(data: bytes) -> bool:
    """判断是否为 A 记录查询（qtype=1）。"""
    try:
        offset = 12
        while data[offset] != 0:
            if (data[offset] & 0xC0) == 0xC0:
                offset += 2
                break
            offset += 1 + data[offset]
        offset += 1                          # null label
        qtype = struct.unpack_from(">H", data, offset)[0]
        return qtype == 1
    except Exception:
        return False


def _question_qtype(data: bytes) -> int | None:
    try:
        offset = 12
        while data[offset] != 0:
            if (data[offset] & 0xC0) == 0xC0:
                offset += 2
                break
            offset += 1 + data[offset]
        offset += 1
        return struct.unpack_from(">H", data, offset)[0]
    except Exception:
        return None


def _question_section(request: bytes) -> bytes:
    """Question 段（含 qtype/qclass）。"""
    offset = 12
    while request[offset] != 0:
        if (request[offset] & 0xC0) == 0xC0:
            offset += 2
            break
        offset += 1 + request[offset]
    offset += 1 + 4
    return request[12:offset]


def _build_nodata_reply(request: bytes) -> bytes:
    """NOERROR、Answer=0：用于 AAAA，避免客户端拿到真实 IPv6 绕过 IPv4 代理。"""
    txid = request[:2]
    flags = b"\x81\x80"
    counts = b"\x00\x01\x00\x00\x00\x00\x00\x00"
    return txid + flags + counts + _question_section(request)


def _build_a_reply(request: bytes, ip: str) -> bytes:
    """构造只含一条 A 记录的 DNS 响应包。"""
    txid   = request[:2]
    flags  = b'\x81\x80'   # QR=1 AA=0 TC=0 RD=1 RA=1 RCODE=0
    counts = b'\x00\x01\x00\x01\x00\x00\x00\x00'  # QD=1 AN=1 NS=0 AR=0

    question = _question_section(request)

    ip_bytes = bytes(int(x) for x in ip.split("."))
    answer = (
        b'\xc0\x0c'          # 名字指针 → question
        b'\x00\x01'          # TYPE A
        b'\x00\x01'          # CLASS IN
        b'\x00\x00\x00\x0a'  # TTL 10 s
        b'\x00\x04'          # RDLENGTH 4
        + ip_bytes
    )
    return txid + flags + counts + question + answer


# ── 上游转发 ──────────────────────────────────────────────────────────────────

async def _forward(data: bytes, addr: tuple, transport, upstreams: list[str]) -> None:
    """依次尝试每个上游 DNS，第一个成功就返回。"""
    loop = asyncio.get_running_loop()
    for upstream in upstreams:
        try:
            def _do(ns: str = upstream) -> bytes:
                with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                    s.settimeout(3)
                    s.sendto(data, (ns, 53))
                    resp, _ = s.recvfrom(4096)
                    return resp
            resp = await loop.run_in_executor(None, _do)
            transport.sendto(resp, addr)
            return
        except Exception as exc:
            log.debug("upstream %s failed: %s", upstream, exc)
    log.warning("DNS forward failed, all upstreams exhausted")


# ── 协议实现 ──────────────────────────────────────────────────────────────────

class _FakeDNS(asyncio.DatagramProtocol):
    def __init__(self, proxy_ip: str, upstreams: list[str]) -> None:
        self._proxy_ip = proxy_ip
        self._upstreams = upstreams
        self._transport: asyncio.DatagramTransport | None = None

    def connection_made(self, transport) -> None:
        self._transport = transport

    def datagram_received(self, data: bytes, addr: tuple) -> None:
        name = _query_name(data)
        if name and name in PREFERRED_WSS_HOSTS and _is_a_query(data):
            log.info("DNS hijack  %-40s → %s", name, self._proxy_ip)
            self._transport.sendto(_build_a_reply(data, self._proxy_ip), addr)
        elif name and name in PREFERRED_WSS_HOSTS:
            qt = _question_qtype(data)
            if qt == 28:  # AAAA — 若转发会得到真 v6，客户端常优先连 v6，绕过仅 IPv4 的 proxy
                log.info("DNS hijack  %-40s  AAAA → NODATA (force IPv4)", name)
                self._transport.sendto(_build_nodata_reply(data), addr)
            else:
                log.debug(
                    "DNS hijack skipped  %-40s  qtype=%s (forwarding)",
                    name, qt,
                )
                asyncio.create_task(_forward(data, addr, self._transport, self._upstreams))
        else:
            log.debug("DNS forward  %s", name)
            asyncio.create_task(_forward(data, addr, self._transport, self._upstreams))

    def error_received(self, exc: Exception) -> None:
        log.warning("DNS socket error: %s", exc)


# ── 公开入口 ──────────────────────────────────────────────────────────────────

async def serve(proxy_ip: str | None = None) -> None:
    """启动假 DNS 服务器，返回后持续运行（需 await asyncio.Future() 保活）。"""
    proxy_ip = proxy_ip or _local_ip()
    upstreams = _upstream_dns_list()

    log.info("DNS server  0.0.0.0:53  proxy_ip=%s", proxy_ip)
    log.info("upstream DNS: %s", " → ".join(upstreams))
    for h in PREFERRED_WSS_HOSTS:
        log.info("  hijack: %s → %s", h, proxy_ip)

    loop = asyncio.get_running_loop()
    await loop.create_datagram_endpoint(
        lambda: _FakeDNS(proxy_ip, upstreams),
        local_addr=("0.0.0.0", 53),
        family=socket.AF_INET,
    )


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-5s  %(message)s",
        datefmt="%H:%M:%S",
    )
    ip_arg = sys.argv[1] if len(sys.argv) > 1 else None

    async def _run() -> None:
        _cleanup_stale_port53_owner()
        await serve(ip_arg)
        await asyncio.Future()   # 永久保活

    asyncio.run(_run())
