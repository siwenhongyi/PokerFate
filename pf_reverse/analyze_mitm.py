"""
分析 mitmproxy 抓包文件，解码 PokerFate WSS 消息。

用法:
    python pf_reverse/analyze_mitm.py <file.mitm>

获取抓包文件:
    1. 在 Windows 上运行 mitmweb
    2. 打开游戏，进入房间打几手牌
    3. mitmweb 界面 → File → Save → 保存为 .mitm 文件
    4. 把文件改名放到 pf_reverse/packets/ 目录下
    5. 运行本脚本

输出格式:
    [方向] 消息类型  字段内容
    C→S = 客户端发给服务器
    S→C = 服务器发给客户端
"""

import sys
import json
import importlib
from pathlib import Path

# 把项目根加入 path，确保能 import pf_intercept
_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_ROOT))

from pf_intercept.framing import FrameBuffer
from pf_intercept import codec

try:
    HTTPFlow = importlib.import_module("mitmproxy.http").HTTPFlow
    FlowReader = importlib.import_module("mitmproxy.io").FlowReader
except ImportError:
    HTTPFlow = None
    FlowReader = None


def _direction(from_client: bool) -> str:
    return "C→S" if from_client else "S→C"


def _print_decoded(obj: dict) -> None:
    """
    Print JSON safely on Windows terminals that may use non-UTF8 encoding.
    """
    try:
        print(f"         {json.dumps(obj, ensure_ascii=False, indent=2)}")
    except UnicodeEncodeError:
        # Fallback when console encoding cannot represent some characters.
        print(f"         {json.dumps(obj, ensure_ascii=True, indent=2)}")


def analyze(mitm_path: str) -> None:
    if FlowReader is None or HTTPFlow is None:
        print("ERROR: 需要安装 mitmproxy:  pip install mitmproxy")
        sys.exit(1)

    path = Path(mitm_path)
    if not path.exists():
        print(f"ERROR: 文件不存在: {path}")
        sys.exit(1)

    print(f"分析文件: {path}")
    print("=" * 70)

    wss_count = 0
    msg_count = 0

    with open(path, "rb") as f:
        reader = FlowReader(f)
        for flow in reader.stream():
            if not isinstance(flow, HTTPFlow):
                continue
            if not flow.websocket:
                continue

            host = flow.request.pretty_host
            wss_count += 1
            print(f"\n[WSS 连接] {host}")
            print("-" * 70)

            # 每个方向独立的 FrameBuffer（处理粘包）
            buf_c2s = FrameBuffer()
            buf_s2c = FrameBuffer()

            for ws_msg in flow.websocket.messages:
                raw = ws_msg.content
                if isinstance(raw, str):
                    raw = raw.encode()

                buf = buf_c2s if ws_msg.from_client else buf_s2c
                direction = _direction(ws_msg.from_client)

                for frame in buf.feed(raw):
                    msg_count += 1
                    decoded = codec.decode(frame.type_name, frame.pb_body)

                    if decoded is not None:
                        print(f"[{direction}] {frame.type_name}")
                        _print_decoded(decoded)
                    else:
                        print(f"[{direction}] {frame.type_name}  "
                              f"(raw {len(frame.pb_body)}B — pb2 未编译或未知消息)")
                    print()

    print("=" * 70)
    print(f"共 {wss_count} 个 WSS 连接，{msg_count} 条消息")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        # 默认路径，把 .mitm 文件放这里即可
        default = _ROOT / "pf_reverse" / "packets" / "capture.mitm"
        print(f"用法: python {__file__} <file.mitm>")
        print(f"默认路径: {default}")
        sys.exit(0)

    analyze(sys.argv[1])
