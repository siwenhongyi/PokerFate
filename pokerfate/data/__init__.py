"""pokerfate.data — 静态数据加载器

启动时调用 init() 预加载所有数据到内存。
翻前 GTO 数据来自 AHTOOOXA/poker-charts（Greenline Poker + Pekarstas）。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Union

_DATA_DIR = Path(__file__).parent
_GTO_DIR = _DATA_DIR / "gto"

# 懒加载缓存
_greenline: dict | None = None
_pekarstas: dict | None = None


def _load_greenline() -> dict:
    global _greenline
    if _greenline is None:
        with open(_GTO_DIR / "greenline.json", encoding="utf-8") as f:
            _greenline = json.load(f)
    return _greenline


def _load_pekarstas() -> dict:
    global _pekarstas
    if _pekarstas is None:
        with open(_GTO_DIR / "pekarstas.json", encoding="utf-8") as f:
            _pekarstas = json.load(f)
    return _pekarstas


def init() -> None:
    """启动时预加载所有数据文件到内存。"""
    _load_greenline()
    _load_pekarstas()


# Action 类型：单一动作字符串，或混合策略数组，或 None（chart 中无记录）
Action = Union[str, list, None]


def lookup_gto(chart_key: str, hand: str) -> dict[str, Action]:
    """查询翻前 GTO 参考数据。

    Args:
        chart_key: 场景键，格式如 "UTG-RFI"、"BTN-vs-open-MP"、"SB-vs-3bet-BB"
        hand:      手牌标记，如 "JTs"、"AA"、"AKo"

    Returns:
        {"greenline": action, "pekarstas": action}
        action 为 "raise"/"call"/"allin"，或 ["raise","fold"] 等混合策略，
        或 "fold"（chart 存在但手牌不在其中，Greenline 隐式弃牌），
        或 None（该 chart key 不存在，即无此场景数据）。

    常用 chart_key 格式：
        {POSITION}-RFI                      主动开池
        {POSITION}-ISO                      隔离跛入者
        {POSITION}-vs-open-{VILLAIN}        面对开池
        {POSITION}-vs-3bet-{VILLAIN}        面对 3bet
        {POSITION}-vs-4bet-{VILLAIN}        面对 4bet

    Positions: UTG, MP, CO, BTN, SB, BB（均为 6-max）
    """
    gl = _load_greenline()
    pk = _load_pekarstas()

    gl_chart = gl.get(chart_key)
    if gl_chart is None:
        gl_action = None          # chart key 不存在 → 无数据
    else:
        gl_action = gl_chart.get(hand, "fold")   # 手牌不在表内 → 弃牌

    pk_chart = pk.get(chart_key)
    if pk_chart is None:
        pk_action = None
    else:
        pk_action = pk_chart.get(hand, "fold")

    return {"greenline": gl_action, "pekarstas": pk_action}


def format_action(action: Action) -> str:
    """将 action 格式化为可读字符串，用于日志输出。"""
    if action is None:
        return "—"          # 无数据（chart key 不存在）
    if action == "fold":
        return "弃牌"        # chart 存在但手牌不在其中
    if action == "allin":
        return "全押"
    if isinstance(action, list):
        return "/".join(action)
    return action
