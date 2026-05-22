"""pokerfate.data — 静态数据加载器

启动时调用 init() 预加载所有数据到内存。
翻前 GTO 主决策数据优先来自 AHTOOOXA/poker-charts（Greenline Poker）；
Greenline 缺少对应 chart 时，PokerGTO Solver Range Wizard 作为次级主表；
Greenline 混合策略存在时，PokerGTO 仍只作为频率参考。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Union

_DATA_DIR = Path(__file__).parent
_GTO_DIR = _DATA_DIR / "gto"

_greenline: dict | None = None
_pokergto: dict | None = None


def _load_greenline() -> dict:
    global _greenline
    if _greenline is None:
        with open(_GTO_DIR / "greenline.json", encoding="utf-8") as f:
            _greenline = json.load(f)
    return _greenline


def _load_pokergto() -> dict:
    global _pokergto
    if _pokergto is None:
        with open(_GTO_DIR / "pokergto.json", encoding="utf-8") as f:
            _pokergto = json.load(f)
    return _pokergto


def init() -> None:
    """启动时预加载所有数据文件到内存。"""
    _load_pokergto()
    _load_greenline()


# Action 类型：单一动作字符串，或混合策略数组，或 None（chart 中无记录）
Action = Union[str, list, dict[str, float], None]


def _pokergto_chart_id(chart_key: str) -> str | None:
    """Map local chart keys to PokerGTO Range Wizard ids.

    PokerGTO has RFI charts, BB defense charts, hero-position vs-3bet
    charts, and late-position 3bet-vs-open charts. Greenline remains primary
    when it has a chart; PokerGTO only replaces missing Greenline chart keys.
    """
    if not chart_key:
        return None
    if chart_key.endswith("-RFI"):
        pos = chart_key.split("-", 1)[0].lower()
        return f"{pos}_open_100bb"
    if chart_key.startswith("BB-vs-open-"):
        return "bb_defend_100bb"
    if chart_key.startswith("BTN-vs-open-"):
        return "btn_3bet_100bb"
    if chart_key.startswith("SB-vs-open-"):
        return "sb_3bet_100bb"
    if chart_key.startswith("CO-vs-open-"):
        return "co_vs_open_100bb"
    if "-vs-3bet-" in chart_key:
        pos = chart_key.split("-", 1)[0].lower()
        return f"{pos}_vs_3bet_100bb"
    return None


def _pokergto_action(chart_key: str, hand: str) -> tuple[dict[str, float] | None, str | None]:
    pg = _load_pokergto()
    pg_key = _pokergto_chart_id(chart_key)
    if not pg_key:
        return None, None
    chart = pg.get(pg_key)
    if not chart:
        return None, None
    freq = chart.get("matrix", {}).get(hand)
    if freq is None:
        return None, pg_key
    return {
        "raise": float(freq.get("raise", 0.0)),
        "call": float(freq.get("call", 0.0)),
        "fold": float(freq.get("fold", 0.0)),
    }, pg_key


def lookup_gto(chart_key: str, hand: str) -> dict[str, object]:
    """查询翻前 GTO 参考数据。

    Args:
        chart_key: 场景键，格式如 "UTG-RFI"、"BTN-vs-open-MP"、"SB-vs-3bet-BB"
        hand:      手牌标记，如 "JTs"、"AA"、"AKo"

    Returns:
        {
          "pokergto": {"raise": 0.75, "call": 0.0, "fold": 0.25} | None,
          "greenline": action,
          "primary": Greenline action, or PokerGTO action when Greenline has no chart,
          "primary_source": "greenline" | "pokergto" | "",
        }
        Greenline action 为 "raise"/"call"/"allin"，或 ["raise","fold"] 等
        混合策略，或 "fold"（chart 存在但手牌不在其中），或 None（chart
        key 不存在）。只有 chart key 不存在时，PokerGTO 才会成为 primary。

    常用 chart_key 格式：
        {POSITION}-RFI                      主动开池
        {POSITION}-ISO                      隔离跛入者
        {POSITION}-vs-open-{VILLAIN}        面对开池
        {POSITION}-vs-3bet-{VILLAIN}        面对 3bet
        {POSITION}-vs-4bet-{VILLAIN}        面对 4bet

    Positions: UTG, MP, CO, BTN, SB, BB（均为 6-max）
    """
    pg_action, pg_key = _pokergto_action(chart_key, hand)

    gl = _load_greenline()
    gl_chart = gl.get(chart_key)
    if gl_chart is None:
        gl_action = None          # chart key 不存在 → 无数据
    else:
        gl_action = gl_chart.get(hand, "fold")   # 手牌不在表内 → 弃牌

    if gl_action is not None:
        primary: Action = gl_action
        primary_source = "greenline"
    elif pg_action is not None:
        primary = pg_action
        primary_source = "pokergto"
    else:
        primary = None
        primary_source = ""

    return {
        "pokergto": pg_action,
        "pokergto_chart_key": pg_key,
        "greenline": gl_action,
        "primary": primary,
        "primary_source": primary_source,
    }


def format_action(action: Action) -> str:
    """将 action 格式化为可读字符串，用于日志输出。"""
    if action is None:
        return "—"          # 无数据（chart key 不存在）
    if isinstance(action, dict):
        labels = {"raise": "raise", "call": "call", "fold": "fold"}
        parts = [
            f"{labels[key]}{value:.0%}"
            for key, value in action.items()
            if value > 0.0001
        ]
        return "/".join(parts) if parts else "弃牌"
    if action == "fold":
        return "弃牌"        # chart 存在但手牌不在其中
    if action == "allin":
        return "全押"
    if isinstance(action, list):
        return "/".join(action)
    return action
