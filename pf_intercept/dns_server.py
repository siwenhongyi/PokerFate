"""
Fake DNS server for Android MITM mode.

PREFERRED_WSS_HOSTS → proxy_ip (本机 IP)
其他所有域名 → 转发给上游 DNS

Usage:
    sudo python -m pf_intercept.dns_server            # 自动探测本机 IP
    sudo python -m pf_intercept.dns_server 100.100.184.133
"""

from __future__ import annotations

import asyncio
import logging
import socket
import struct
import sys

from pf_intercept.config import EXTERNAL_DNS_SERVERS, PREFERRED_WSS_HOSTS

log = logging.getLogger(__name__)


# ── 系统 DNS 探测 ──────────────────────────────────────────────────────────────

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

def _local_ip() -> str:
    """探测本机对外 IP（不发包，仅用于获取路由出口地址）。"""
    # 用第一个外部 DNS 的 IP 做路由探测，避免依赖 8.8.8.8
    probe = _system_dns() or EXTERNAL_DNS_SERVERS[0]
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.connect((probe, 53))
        return s.getsockname()[0]


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


def _build_a_reply(request: bytes, ip: str) -> bytes:
    """构造只含一条 A 记录的 DNS 响应包。"""
    txid   = request[:2]
    flags  = b'\x81\x80'   # QR=1 AA=0 TC=0 RD=1 RA=1 RCODE=0
    counts = b'\x00\x01\x00\x01\x00\x00\x00\x00'  # QD=1 AN=1 NS=0 AR=0

    # 复制 question 段
    offset = 12
    while request[offset] != 0:
        if (request[offset] & 0xC0) == 0xC0:
            offset += 2
            break
        offset += 1 + request[offset]
    offset += 1 + 4   # null label + qtype + qclass
    question = request[12:offset]

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
        else:
            log.debug("DNS forward %s", name)
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
        await serve(ip_arg)
        await asyncio.Future()   # 永久保活

    asyncio.run(_run())
