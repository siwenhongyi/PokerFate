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

        # 保留所有域名服务器，过滤掉 IP 直连
        domain_servers = [
            s for s in servers
            if not _IP_PATTERN.match(s.get("server_host", ""))
        ]

        if not domain_servers:
            print("[force_domain] 响应中无域名服务器，不修改")
            return

        if len(domain_servers) == len(servers):
            return  # 本来就没有 IP 服务器，无需修改

        data["server"]["server"] = domain_servers
        flow.response.content = json.dumps(data).encode()

        print(f"[force_domain] 过滤 {len(servers) - len(domain_servers)} 个 IP 服务器，"
              f"保留 {len(domain_servers)} 个域名服务器:")
        for s in domain_servers:
            print(f"  {s.get('server_host')}")

        # 取第一个写入 discovered_server.json，proxy.py 启动时读取
        chosen = domain_servers[0]["server_host"]
        try:
            _DISCOVERED_FILE.write_text(json.dumps({"server_host": chosen}))
            print(f"[force_domain] 首选服务器: {chosen}  → {_DISCOVERED_FILE.name}")
            print(f"[force_domain] 提示: 确保 hosts 文件包含对应域名的重定向")
        except Exception as e:
            print(f"[force_domain] 写入失败: {e}")


addons = [ForceDomain()]
