"""事件名 + 上下文字段 → Bark 标题、正文、图标 URL。"""

from __future__ import annotations

import json
from typing import Any


def format_chips_km_signed(chips: float) -> str:
    """将筹码数量格式化为带符号的 k / m 缩写字符串，保留两位小数。"""
    c = float(chips)
    if c >= 0.0:
        sign = "+"
        v = c
    else:
        sign = "-"
        v = -c
    if v >= 1_000_000.0:
        return f"{sign}{v / 1_000_000.0:.2f}m"
    if v >= 1_000.0:
        return f"{sign}{v / 1_000.0:.2f}k"
    return f"{sign}{v:.2f}"

# Microsoft Fluent Emoji 3D（github.com/microsoft/fluentui-emoji，MIT），经 jsDelivr。
_FE = "https://cdn.jsdelivr.net/gh/microsoft/fluentui-emoji@main/assets"

BARK_EVENT_ICONS: dict[str, str] = {
    "wss_disconnected": f"{_FE}/Exploding%20Head/3D/exploding_head_3d.png",
    "auto_rebuy": f"{_FE}/Money%20with%20Wings/3D/money_with_wings_3d.png",
    "profit_lock_trigger": f"{_FE}/Gem%20Stone/3D/gem_stone_3d.png",
    "chips_below_50bb": f"{_FE}/Face%20Screaming%20in%20Fear/3D/face_screaming_in_fear_3d.png",
    "hand_swing_up": f"{_FE}/Chart%20Increasing/3D/chart_increasing_3d.png",
    "hand_swing_down": f"{_FE}/Chart%20Decreasing/3D/chart_decreasing_3d.png",
    "gamedata_no_history": f"{_FE}/Ghost/3D/ghost_3d.png",
    "token_captured": f"{_FE}/Key/3D/key_3d.png",
}


def _fit_utf8(text: str, max_bytes: int, suffix: str = "...") -> str:
    raw = text.encode("utf-8")
    if len(raw) <= max_bytes:
        return text
    suffix_raw = suffix.encode("utf-8")
    budget = max(0, max_bytes - len(suffix_raw))
    clipped = raw[:budget]
    while clipped:
        try:
            return clipped.decode("utf-8") + suffix
        except UnicodeDecodeError:
            clipped = clipped[:-1]
    return suffix if max_bytes >= len(suffix_raw) else ""


def _append_hand_detail(body: str, fields: dict[str, Any]) -> str:
    detail = fields.get("hand_detail")
    if not detail:
        return body
    detail_text = str(detail).strip()
    if not detail_text:
        return body

    # Bark ultimately uses APNs; regular APNs payloads are capped at 4096 bytes.
    # Keep the visible body comfortably below that to leave room for title/icon
    # and Bark's own JSON wrapper.
    max_body_bytes = 3000
    prefix = body + "\n\n"
    budget = max_body_bytes - len(prefix.encode("utf-8"))
    if budget <= 0:
        return _fit_utf8(body, max_body_bytes)
    return prefix + _fit_utf8(detail_text, budget)


def format_bark_message(event: str, fields: dict[str, Any]) -> tuple[str, str, str | None]:
    icon: str | None = BARK_EVENT_ICONS.get(event)
    if icon is None:
        ic = fields.get("icon")
        icon = ic if isinstance(ic, str) else None

    if event == "wss_disconnected":
        return "WSS 异常断开", "", icon

    if event == "auto_rebuy":
        pnl = fields.get("pnl_chips", fields.get("pnl_bb", 0))
        if isinstance(pnl, (int, float)):
            pnl_str = format_chips_km_signed(float(pnl))
        else:
            pnl_str = str(pnl)
        title = "筹码清零 · 自动买入"
        body = (
            f"第 {fields.get('nth')}/{fields.get('max_n')} 次自动续入\n"
            f"续入筹码: {fields.get('rebuy_chips')}\n"
            f"rebuy 窗口: {fields.get('rebuy_window_sec')} 秒\n"
            f"累计盈亏: {pnl_str}（筹码）"
        )
        return title, body, icon

    if event == "profit_lock_trigger":
        pnl = fields.get("pnl_chips", fields.get("pnl_bb", 0))
        if isinstance(pnl, (int, float)):
            pnl_str = format_chips_km_signed(float(pnl))
        else:
            pnl_str = str(pnl)
        title = "盈利锁仓 · 已触发"
        body = (
            f"触发时筹码: {fields.get('stack_chips')}（阈值 {fields.get('lock_bb')}BB）\n"
            f"房间 room_id={fields.get('room_id')}  BB={fields.get('big_blind')}\n"
            f"累计盈亏: {pnl_str}（筹码）"
        )
        return title, body, icon

    if event == "hand_swing":
        delta = fields.get("profit_delta", 0)
        start = fields.get("start_chips", 0)
        bb = fields.get("big_blind", 0)
        try:
            delta_f = float(delta)
            start_f = float(start) if float(start) > 0 else 1.0
            bb_f = float(bb) if float(bb) > 0 else 1.0
        except (TypeError, ValueError):
            delta_f, start_f, bb_f = 0.0, 1.0, 1.0
        is_up = delta_f >= 0
        pct = delta_f / start_f * 100.0
        delta_bb = delta_f / bb_f
        start_bb = start_f / bb_f
        sign = "+" if is_up else ""
        icon = BARK_EVENT_ICONS.get("hand_swing_up" if is_up else "hand_swing_down") or icon
        title = f"单手波动 · {sign}{delta_bb:.1f} BB"
        body = (
            f"本手盈亏: {sign}{int(delta_f)}（{sign}{delta_bb:.1f} BB）\n"
            f"开局筹码: {int(start_f)}（{start_bb:.1f} BB，占比 {sign}{pct:.1f}%）\n"
            f"BB = {int(bb_f)}"
        )
        return title, _append_hand_detail(body, fields), icon

    if event == "gamedata_no_history":
        title = "新玩家 · 无历史数据"
        body = f"本局首次出现无历史数据玩家（code=-2）\n可能是新号/小号，留意激进下注"
        return title, body, icon

    if event == "token_captured":
        title = "Token · 已自动捕获"
        body = f"mitmproxy 拦截到登录响应\nauth_token.txt 已更新"
        return title, body, icon

    title = str(fields.get("title", event))
    body = fields.get("body") or json.dumps(fields, ensure_ascii=False, default=str)
    return title, str(body), icon
