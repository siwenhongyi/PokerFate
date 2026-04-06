"""事件名 + 上下文字段 → Bark 标题、正文、图标 URL。"""

from __future__ import annotations

import json
from typing import Any

# Microsoft Fluent Emoji 3D（github.com/microsoft/fluentui-emoji，MIT），经 jsDelivr。
_FE = "https://cdn.jsdelivr.net/gh/microsoft/fluentui-emoji@main/assets"

BARK_EVENT_ICONS: dict[str, str] = {
    "wss_disconnected": f"{_FE}/Broken%20chain/3D/broken_chain_3d.png",
    "auto_rebuy": f"{_FE}/Money%20bag/3D/money_bag_3d.png",
    "profit_lock_trigger": f"{_FE}/Locked/3D/locked_3d.png",
    "profit_lock_reenter": f"{_FE}/Check%20mark%20button/3D/check_mark_button_3d.png",
}


def format_bark_message(event: str, fields: dict[str, Any]) -> tuple[str, str, str | None]:
    icon: str | None = BARK_EVENT_ICONS.get(event)
    if icon is None:
        ic = fields.get("icon")
        icon = ic if isinstance(ic, str) else None

    if event == "wss_disconnected":
        return "WSS 异常断开", "", icon

    if event == "auto_rebuy":
        title = "筹码清零 · 自动买入"
        body = (
            f"第 {fields.get('nth')}/{fields.get('max_n')} 次自动续入\n"
            f"续入筹码: {fields.get('rebuy_chips')}\n"
            f"触发时桌上余额: {fields.get('balance_chips')}（NoticeReby 时一般为 0）\n"
            f"rebuy 窗口: {fields.get('rebuy_window_sec')} 秒"
        )
        return title, body, icon

    if event == "profit_lock_trigger":
        title = "盈利锁仓 · 已触发"
        body = (
            f"本局第 {fields.get('nth')} 次锁仓\n"
            f"触发时筹码: {fields.get('stack_chips')}（阈值 {fields.get('threshold_chips')} = {fields.get('lock_bb')}BB×BB）\n"
            f"房间 room_id={fields.get('room_id')}  BB={fields.get('big_blind')}"
        )
        return title, body, icon

    if event == "profit_lock_reenter":
        title = "盈利锁仓 · 已回桌"
        body = (
            f"对应第 {fields.get('nth')} 次锁仓流程（EnterRoomRSP 成功，含 QuickStart 等任意回桌路径）\n"
            f"退出房间后筹码总量: {fields.get('exit_room_chips_total')}\n"
            f"进房后桌上筹码: {fields.get('table_chips')}\n"
            f"买入 byin_chips={fields.get('buyin_chips')}  room_id={fields.get('room_id')}"
        )
        return title, body, icon

    title = str(fields.get("title", event))
    body = fields.get("body") or json.dumps(fields, ensure_ascii=False, default=str)
    return title, str(body), icon
