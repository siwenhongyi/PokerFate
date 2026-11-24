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


def _format_optional_chips(value: Any) -> str:
    if isinstance(value, (int, float)):
        return format_chips_km_signed(float(value))
    if value is None:
        return "-"
    return str(value)

# Microsoft Fluent Emoji 3D（github.com/microsoft/fluentui-emoji，MIT），经 jsDelivr。
_FE = "https://cdn.jsdelivr.net/gh/microsoft/fluentui-emoji@main/assets"

BARK_EVENT_ICONS: dict[str, str] = {
    "wss_disconnected": f"{_FE}/Exploding%20Head/3D/exploding_head_3d.png",
    "wss_reconnected": f"{_FE}/Exploding%20Head/3D/exploding_head_3d.png",
    "auto_rebuy": f"{_FE}/Money%20with%20Wings/3D/money_with_wings_3d.png",
    "profit_lock_trigger": f"{_FE}/Gem%20Stone/3D/gem_stone_3d.png",
    "table_leave": f"{_FE}/Robot/3D/robot_3d.png",
    "topup": f"{_FE}/Coin/3D/coin_3d.png",
    "loss_stop": f"{_FE}/Face%20Screaming%20in%20Fear/3D/face_screaming_in_fear_3d.png",
    "hand_swing_up": f"{_FE}/Chart%20Increasing/3D/chart_increasing_3d.png",
    "hand_swing_down": f"{_FE}/Chart%20Decreasing/3D/chart_decreasing_3d.png",
    "gamedata_no_history": f"{_FE}/Ghost/3D/ghost_3d.png",
    "gamedata_auth_failed": f"{_FE}/Key/3D/key_3d.png",
    # 大厅事务：活动雷达的发现、服务器开了表里没有的一期等（标题和正文由调用方给出）。
    "lobby_alert": f"{_FE}/Satellite%20Antenna/3D/satellite_antenna_3d.png",
}

_WSS_NOTICE_ID = "pokerfate-wss-disconnected"

# 选桌让 bot 离开一张已经打过牌的桌子（table_policy 的离桌原因 → 标题）。
_TABLE_LEAVE_TITLES: dict[str, str] = {
    "no_humans": "选桌离桌 · 桌上没有真人了",
    "outnumbered": "选桌离桌 · 真人少于人机",
    "empty_timeout": "选桌离桌 · 桌上没人了",
    "better_stake": "选桌离桌 · 回优先场次",
    "errand": "离桌 · 去打任务手数（奥马哈 / AOF）",
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

    if event == "wss_reconnected":
        return "WSS 已恢复", "", icon

    if event == "auto_rebuy":
        delta_str = _format_optional_chips(fields.get("session_delta_chips"))
        title = "筹码清零 · 自动买入"
        cap = fields.get("loss_cap_chips")
        cap_line = f"\n净亏损上限: {format_chips_km_signed(-float(cap))}" if isinstance(cap, (int, float)) and cap > 0 else ""
        body = (
            f"第 {fields.get('nth')} 次自动续入\n"
            f"续入筹码: {fields.get('rebuy_chips')}\n"
            f"rebuy 窗口: {fields.get('rebuy_window_sec')} 秒\n"
            f"本次启动盈亏: {delta_str}（筹码）"
            f"{cap_line}"
        )
        return title, body, icon

    if event == "loss_stop":
        cap = fields.get("loss_cap_chips")
        cap_str = format_chips_km_signed(-float(cap)) if isinstance(cap, (int, float)) and cap > 0 else "-"
        title = "净亏损到上限 · 已停止"
        body = (
            f"本次启动盈亏: {_format_optional_chips(fields.get('session_delta_chips'))}（筹码）\n"
            f"净亏损上限: {cap_str}（{fields.get('buyins')} 个 100BB 买入）\n"
            f"放不下{fields.get('what') or '买入'}，已停在大厅，不再买入。重启后恢复。"
        )
        return title, body, icon

    if event == "profit_lock_trigger":
        delta_str = _format_optional_chips(fields.get("session_delta_chips"))
        title = "盈利锁仓 · 已触发"
        body = (
            f"触发时筹码: {fields.get('stack_chips')}（阈值 {fields.get('lock_bb')}BB）\n"
            f"房间 room_id={fields.get('room_id')}  BB={fields.get('big_blind')}\n"
            f"本次启动盈亏: {delta_str}（筹码）"
        )
        return title, body, icon

    if event == "topup":
        try:
            bb = float(fields.get("big_blind") or 0)
        except (TypeError, ValueError):
            bb = 0.0

        def in_bb(chips: Any) -> str:
            return f"（{float(chips) / bb:.0f}BB）" if bb > 0 and isinstance(chips, (int, float)) else ""

        added, stack = fields.get("added_chips"), fields.get("stack_chips")
        title = "桌上补码"
        body = (
            f"补充筹码: {added}{in_bb(added)}，本次启动第 {fields.get('nth')} 次\n"
            f"桌上筹码: {stack}{in_bb(stack)}\n"
            f"本次启动盈亏: {_format_optional_chips(fields.get('session_delta_chips'))}（筹码）"
        )
        return title, body, icon

    if event == "table_leave":
        title = _TABLE_LEAVE_TITLES.get(str(fields.get("reason") or ""), "选桌离桌")
        body = f"本次启动盈亏: {_format_optional_chips(fields.get('session_delta_chips'))}（筹码）"
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
        hand_no = fields.get("hand_no")
        hand_no_line = ""
        try:
            hand_no_i = int(hand_no)
            if hand_no_i > 0:
                hand_no_line = f"第几手: 第{hand_no_i}手\n"
        except (TypeError, ValueError):
            hand_no_line = ""
        title = f"单手波动 · {sign}{delta_bb:.1f} BB"
        body = (
            f"{hand_no_line}"
            f"本手盈亏: {sign}{int(delta_f)}（{sign}{delta_bb:.1f} BB）\n"
            f"开局筹码: {int(start_f)}（{start_bb:.1f} BB，占比 {sign}{pct:.1f}%）\n"
            f"BB = {int(bb_f)}"
        )
        return title, _append_hand_detail(body, fields), icon

    if event == "gamedata_no_history":
        title = "玩家 · 暂无历史统计"
        body = (f"玩家：{fields.get('name') or fields.get('uid') or '未知'}\n"
                "查询成功，近30天有效对局数为0。\n本次运行仅提醒一次。")
        return title, body, icon

    if event == "gamedata_auth_failed":
        title = "对手历史查询 · 登录态失效"
        body = "HTTP 鉴权失败（code=-2），暂停查询对手历史统计。\n更新有效凭证后重试；游戏对局继续。"
        return title, body, icon

    title = str(fields.get("title", event))
    body = fields.get("body") or json.dumps(fields, ensure_ascii=False, default=str)
    return title, str(body), icon


def format_bark_options(event: str, fields: dict[str, Any]) -> dict[str, Any]:
    """Bark non-content options used for notification updating."""
    if event == "wss_disconnected":
        return {"id": _WSS_NOTICE_ID}

    if event == "wss_reconnected":
        return {"id": _WSS_NOTICE_ID, "delete": 1}

    return {}
