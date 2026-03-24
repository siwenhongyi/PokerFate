"""
mitmproxy addon: 篡改登录响应，删除 IP 直连的服务器，强制游戏走域名连接。
同时将发现的 WSS 服务器写入 pf_intercept/discovered_server.json，
供 pf_intercept/proxy.py 启动时读取。

用法:
    mitmweb --ignore-hosts "aliyuncs.com|miui.com" -s pf_reverse/force_domain.py
"""

import json
from pathlib import Path
from mitmproxy import http

_DISCOVERED_FILE = Path(__file__).parent.parent / "pf_intercept" / "discovered_server.json"


class ForceDomain:
    def response(self, flow: http.HTTPFlow) -> None:
        # 只处理登录响应（包含 server 列表的那个）
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

        import re
        ip_pattern = re.compile(r"wss?://\d+\.\d+\.\d+\.\d+")

        # 只保留 zga-entry.poker-fate.net:9012，其余全部丢弃
        # 并把 wss:// 降级成 ws://（明文），绕过客户端证书验证
        TARGET = "zga-entry.poker-fate.net"
        result = []
        for s in servers:
            host = s.get("server_host", "")
            if TARGET in host:
                s = dict(s)
                s["server_host"] = host.replace("wss://", "ws://").replace(":9012", ":9013")
                result = [s]
                break

        if not result:
            print("[force_domain] 未找到目标服务器，保留原始列表")
            return

        data["server"]["server"] = result
        flow.response.content = json.dumps(data).encode()
        server_host = result[0]["server_host"]
        print(f"[force_domain] 强制使用: {server_host}")

        # 写入 discovered_server.json 供 pf_intercept/proxy.py 读取
        try:
            _DISCOVERED_FILE.write_text(json.dumps({"server_host": server_host}))
            print(f"[force_domain] 已写入 {_DISCOVERED_FILE}")
        except Exception as e:
            print(f"[force_domain] 写入失败: {e}")


addons = [ForceDomain()]
