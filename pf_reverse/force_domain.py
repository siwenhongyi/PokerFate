"""
mitmproxy addon: 过滤登录响应中的 IP 直连服务器，保留所有域名服务器。
将第一个可用域名服务器写入 pf_intercept/discovered_server.json，
供 pf_intercept/proxy.py 启动时读取。

用法:
    mitmweb --ignore-hosts "aliyuncs.com|miui.com" -s pf_reverse/force_domain.py
"""

import json
import re
import socket
import sys
import time
from pathlib import Path
from urllib.parse import urlparse
from mitmproxy import http

# Allow importing config from the repo root regardless of cwd.
_REPO_ROOT = Path(__file__).parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
from pf_intercept.config import (  # single source of truth
    EXPERIMENT_ROUTE_HTTP_TO_IP_ENTRY,
    PREFERRED_WSS_HOSTS,
    SERVER_WSS_PORT,
)

_DISCOVERED_FILE = _REPO_ROOT / "pf_intercept" / "discovered_server.json"
_ORIGINAL_RESPONSE_FILE = _REPO_ROOT / "data" / "force_domain_original_response.json"
_TOKEN_FILE = _REPO_ROOT / "data" / "auth_token.txt"
_IP_PATTERN = re.compile(r"wss?://\d+\.\d+\.\d+\.\d+")
_IP_HOST_PATTERN = re.compile(r"^\d+\.\d+\.\d+\.\d+$")
_PREFERRED_HOSTS = set(PREFERRED_WSS_HOSTS)
_HTTP_ROUTE_CACHE_MTIME: float | None = None
_HTTP_ROUTE_CACHE_TARGET: tuple[str, str, int, float] | None = None
_HTTP_ROUTE_LOGGED_TARGET: tuple[str, str, int] | None = None


def _extract_ws_host(server_host: str) -> str:
    url = server_host.replace("wss://", "").replace("ws://", "")
    return url.split(":", 1)[0]


def _extract_port(server_host: str) -> int:
    url = server_host.replace("wss://", "").replace("ws://", "")
    parts = url.split(":", 1)
    try:
        return int(parts[1]) if len(parts) > 1 else 443
    except ValueError:
        return 443


def _default_port(scheme: str) -> int:
    return 443 if scheme == "https" else 80


def _host_header(host: str, port: int, scheme: str) -> str:
    return host if port == _default_port(scheme) else f"{host}:{port}"


def _probe_latency(host: str, port: int, timeout: float = 0.5) -> float:
    started_at = time.monotonic()
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return time.monotonic() - started_at
    except OSError:
        return float("inf")


def _ip_http_candidates() -> list[tuple[str, str, int]]:
    try:
        data = json.loads(_ORIGINAL_RESPONSE_FILE.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return []
    except Exception as exc:
        print(f"[force_domain] 读取原始服务器列表失败: {exc}")
        return []

    candidates: list[tuple[str, str, int]] = []
    for item in data.get("server", {}).get("server", []):
        if not isinstance(item, dict):
            continue
        server_host = item.get("server_host") or ""
        http_host = item.get("http_host") or ""
        ws_url = urlparse(server_host)
        http_url = urlparse(http_host)
        ws_host = ws_url.hostname or ""
        http_host_name = http_url.hostname or ""
        if not _IP_HOST_PATTERN.match(ws_host):
            continue
        if http_host_name != ws_host:
            continue
        scheme = http_url.scheme or "http"
        port = http_url.port or _default_port(scheme)
        target = (scheme, http_host_name, int(port))
        if target not in candidates:
            candidates.append(target)
    return candidates


def _select_ip_http_target() -> tuple[str, str, int, float] | None:
    global _HTTP_ROUTE_CACHE_MTIME, _HTTP_ROUTE_CACHE_TARGET

    if not EXPERIMENT_ROUTE_HTTP_TO_IP_ENTRY:
        return None

    try:
        mtime = _ORIGINAL_RESPONSE_FILE.stat().st_mtime
    except FileNotFoundError:
        return None

    if _HTTP_ROUTE_CACHE_MTIME == mtime:
        return _HTTP_ROUTE_CACHE_TARGET

    candidates = _ip_http_candidates()
    if not candidates:
        _HTTP_ROUTE_CACHE_MTIME = mtime
        _HTTP_ROUTE_CACHE_TARGET = None
        return None

    measured = [
        (scheme, host, port, _probe_latency(host, port))
        for scheme, host, port in candidates
    ]
    reachable = [item for item in measured if item[3] != float("inf")]
    target = min(reachable or measured, key=lambda item: item[3])
    _HTTP_ROUTE_CACHE_MTIME = mtime
    _HTTP_ROUTE_CACHE_TARGET = target
    return target


class ForceDomain:
    def request(self, flow: http.HTTPFlow) -> None:
        global _HTTP_ROUTE_LOGGED_TARGET

        original_host = flow.request.host
        if original_host not in _PREFERRED_HOSTS:
            return

        target = _select_ip_http_target()
        if target is None:
            return

        scheme, host, port, latency = target
        original_url = flow.request.pretty_url
        flow.request.scheme = scheme
        flow.request.host = host
        flow.request.port = port
        flow.request.headers["Host"] = _host_header(host, port, scheme)

        log_key = (scheme, host, port)
        if _HTTP_ROUTE_LOGGED_TARGET != log_key:
            _HTTP_ROUTE_LOGGED_TARGET = log_key
            latency_text = "n/a" if latency == float("inf") else f"{int(latency * 1000)}ms"
            print(
                "[force_domain] HTTP 转发实验启用: "
                f"{original_host} → {scheme}://{_host_header(host, port, scheme)} "
                f"(probe={latency_text})"
            )
        print(f"[force_domain] HTTP route {original_url[:120]} -> {flow.request.pretty_url[:120]}")

    def response(self, flow: http.HTTPFlow) -> None:
        # Log every response so we can see if this addon is running at all.
        print(f"[force_domain] {flow.response.status_code} {flow.request.url[:120]}")

        # Try JSON parsing regardless of content-type; some servers omit or
        # mislabel it (e.g. "text/plain" for a JSON body).
        try:
            data = json.loads(flow.response.content)
        except Exception:
            return

        # 拦截登录响应：data.authorization 就是 HTTP Authorization token
        if data.get("code") == 0:
            token = data.get("authorization")
            if token:
                try:
                    _TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
                    _TOKEN_FILE.write_text(token, encoding="utf-8")
                    print(f"[force_domain] Token 已写入 {_TOKEN_FILE.name}  ({token[:12]}…)")
                except Exception as e:
                    print(f"[force_domain] Token 写入失败: {e}")

        servers = data.get("server", {}).get("server", [])
        if not servers:
            return

        # 保留域名服务器，过滤掉 IP 直连
        domain_servers = [
            s for s in servers
            if not _IP_PATTERN.match(s.get("server_host", ""))
        ]

        if not domain_servers:
            print("[force_domain] 响应中无域名服务器，不修改")
            return

        # 只保留：域名在证书范围内 且 端口为 SERVER_WSS_PORT (9012)
        preferred_servers = [
            s for s in domain_servers
            if _extract_ws_host(s.get("server_host", "")) in _PREFERRED_HOSTS
            and _extract_port(s.get("server_host", "")) == SERVER_WSS_PORT
        ]

        if preferred_servers:
            domain_servers = preferred_servers
        else:
            print(f"[force_domain] 无满足条件的服务器（需在证书范围内且端口={SERVER_WSS_PORT}），不修改")
            return

        # Save the untouched response just before rewriting the server list.
        try:
            _ORIGINAL_RESPONSE_FILE.parent.mkdir(parents=True, exist_ok=True)
            _ORIGINAL_RESPONSE_FILE.write_text(
                json.dumps(data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            print(f"[force_domain] 原始响应已写入 {_ORIGINAL_RESPONSE_FILE.name}")
        except Exception as e:
            print(f"[force_domain] 原始响应写入失败: {e}")

        # Keep preferred domain servers in response (domain hijack mode).
        data["server"]["server"] = domain_servers
        flow.response.content = json.dumps(data).encode()

        print(f"[force_domain] 原始 {len(servers)} 个服务器，保留 {len(domain_servers)} 个优先域名服务器:")
        for s in domain_servers:
            print(f"  {s.get('server_host')}")

        # 取第一个写入 discovered_server.json，proxy.py 启动时读取
        chosen = domain_servers[0]["server_host"]
        try:
            _DISCOVERED_FILE.write_text(json.dumps({"server_host": chosen}))
            print(f"[force_domain] 首选服务器: {chosen}  → {_DISCOVERED_FILE.name}")
            print("[force_domain] 提示: 确保 hosts 文件包含对应域名的重定向")
        except Exception as e:
            print(f"[force_domain] 写入失败: {e}")


addons = [ForceDomain()]
