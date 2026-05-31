"""
mitmproxy addon: 过滤登录响应中的 IP 直连服务器，保留所有域名服务器。
将第一个可用域名服务器写入 pf_intercept/discovered_server.json，
供 pf_intercept/proxy.py 启动时读取。

用法:
    mitmweb --ignore-hosts "aliyuncs.com|miui.com" -s pf_reverse/force_domain.py
"""

import json
import re
import sys
from pathlib import Path
from mitmproxy import http

# Allow importing config from the repo root regardless of cwd.
_REPO_ROOT = Path(__file__).parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
from pf_intercept.config import PREFERRED_WSS_HOSTS, SERVER_WSS_PORT  # single source of truth

_DISCOVERED_FILE = _REPO_ROOT / "pf_intercept" / "discovered_server.json"
_ORIGINAL_RESPONSE_FILE = _REPO_ROOT / "data" / "force_domain_original_response.json"
_SELECTED_ROUTE_FILE = _REPO_ROOT / "data" / "selected_route.json"
_TOKEN_FILE = _REPO_ROOT / "data" / "auth_token.txt"
_IP_PATTERN = re.compile(r"wss?://\d+\.\d+\.\d+\.\d+")
_PREFERRED_HOSTS = set(PREFERRED_WSS_HOSTS)


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


class ForceDomain:
    def __init__(self) -> None:
        self._route_mtime: float | None = None
        self._route: dict | None = None

    def _load_selected_route(self) -> dict | None:
        try:
            mtime = _SELECTED_ROUTE_FILE.stat().st_mtime
        except FileNotFoundError:
            self._route_mtime = None
            self._route = None
            return None
        except Exception as e:
            print(f"[force_domain] 读取线路文件失败: {e}")
            return self._route

        if self._route is not None and self._route_mtime == mtime:
            return self._route

        try:
            route = json.loads(_SELECTED_ROUTE_FILE.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"[force_domain] 解析线路文件失败: {e}")
            return self._route

        self._route_mtime = mtime
        self._route = route if isinstance(route, dict) else None
        return self._route

    def request(self, flow: http.HTTPFlow) -> None:
        # The client keeps using the domain from the login response. When the
        # WSS proxy has selected a faster server entry, mirror that entry for
        # HTTP APIs while preserving the client-visible Host header.
        if flow.request.host not in _PREFERRED_HOSTS:
            return

        route = self._load_selected_route()
        if not route:
            return

        scheme = route.get("http_scheme")
        upstream_host = route.get("http_upstream_host")
        port = route.get("http_port")
        if scheme not in ("http", "https") or not upstream_host or not port:
            return

        original_host = flow.request.host
        try:
            flow.request.scheme = str(scheme)
            flow.request.host = str(upstream_host)
            flow.request.port = int(port)
            flow.request.headers["Host"] = original_host
            print(
                "[force_domain] HTTP route "
                f"{original_host} -> {scheme}://{upstream_host}:{port} "
                f"(mode={route.get('mode')})"
            )
        except Exception as e:
            print(f"[force_domain] HTTP route 改写失败: {e}")

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

        # Client-facing response stays domain based. Use plain HTTP here so the
        # addon / local passthrough can pair HTTP with the WSS route internally.
        client_server = dict(domain_servers[0])
        visible_host = _extract_ws_host(client_server.get("server_host", ""))
        client_server["server_host"] = f"wss://{visible_host}:{SERVER_WSS_PORT}"
        client_server["http_host"] = f"http://{visible_host}/"
        data["server"]["server"] = [client_server]
        flow.response.content = json.dumps(data, ensure_ascii=False).encode()

        print(f"[force_domain] 原始 {len(servers)} 个服务器，返回域名服务器:")
        print(f"  {client_server.get('server_host')}  http={client_server.get('http_host')}")

        # 取第一个写入 discovered_server.json，proxy.py 启动时读取
        chosen = client_server["server_host"]
        try:
            _DISCOVERED_FILE.write_text(json.dumps({"server_host": chosen}))
            print(f"[force_domain] 首选服务器: {chosen}  → {_DISCOVERED_FILE.name}")
            print("[force_domain] 提示: 确保 hosts 文件包含对应域名的重定向")
        except Exception as e:
            print(f"[force_domain] 写入失败: {e}")


addons = [ForceDomain()]
