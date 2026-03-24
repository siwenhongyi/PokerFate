"""
mitmproxy addon: 过滤登录响应中的 IP 直连服务器，保留所有域名服务器。
将第一个可用域名服务器写入 pf_intercept/discovered_server.json，
供 pf_intercept/proxy.py 启动时读取。

用法:
    mitmweb --ignore-hosts "aliyuncs.com|miui.com" -s pf_reverse/force_domain.py
"""

import json
import re
from pathlib import Path
from mitmproxy import http

_DISCOVERED_FILE = Path(__file__).parent.parent / "pf_intercept" / "discovered_server.json"
_IP_PATTERN = re.compile(r"wss?://\d+\.\d+\.\d+\.\d+")
_PREFERRED_HOSTS = [
    "zga-entry.poker-fate.net",
    "zga-entry.allinmoe.com",
    "ga-foreign.poker-fate.com",
]


def _extract_ws_host(server_host: str) -> str:
    url = server_host.replace("wss://", "").replace("ws://", "")
    return url.split(":", 1)[0]


class ForceDomain:
    def response(self, flow: http.HTTPFlow) -> None:
        ct = flow.response.headers.get("content-type", "")
        if "json" not in ct:
            return

        try:
            data = json.loads(flow.response.content)
        except Exception:
            return

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

        # 只保留高优先级入口域名，避免客户端自动降级到低优先级池（ga/awss 等）
        preferred_servers = []
        for host in _PREFERRED_HOSTS:
            matched = [
                s for s in domain_servers
                if _extract_ws_host(s.get("server_host", "")) == host
            ]
            preferred_servers.extend(matched)

        if preferred_servers:
            domain_servers = preferred_servers

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
