from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Iterable


COLOR_NAMES: dict[int, str] = {
    101: "黄",
    102: "灰",
    103: "紫",
    104: "蓝",
    105: "红",
    106: "绿",
}

ALL_COLOR_IDS = tuple(COLOR_NAMES)
PAYOUT_BY_HIT_COUNT = {0: 0, 1: 2, 2: 3, 3: 10}
DEFAULT_STAKE = 1000
DEFAULT_LEVEL = 1
DEFAULT_FROM_GAME_TYPE = 0
DEFAULT_ROOM_ID = 0


@dataclass(frozen=True)
class ColorGameCommand:
    bets: tuple[tuple[int, int], ...]
    lvl: int = DEFAULT_LEVEL
    from_game_type: int = DEFAULT_FROM_GAME_TYPE
    room_id: int = DEFAULT_ROOM_ID
    strategy: str = "manual"

    @property
    def total_bet(self) -> int:
        return sum(value for _, value in self.bets)

    def to_fields(self) -> dict:
        return {
            "from_game_type": self.from_game_type,
            "bets": [
                {"id": color_id, "value": value}
                for color_id, value in self.bets
            ],
            "lvl": self.lvl,
        }


def color_name(color_id: int) -> str:
    return COLOR_NAMES.get(color_id, str(color_id))


def format_bets(bets: Iterable[tuple[int, int]]) -> str:
    return " ".join(f"{color_name(color_id)}:{value}" for color_id, value in bets)


def format_ids(ids: Iterable[int]) -> str:
    return ",".join(color_name(int(color_id)) for color_id in ids)


def summarize_color_response(
    msg: dict,
    fallback_total_bet: int | None = None,
) -> dict:
    bets = [
        (int(item.get("id", 0)), int(item.get("value", 0)))
        for item in msg.get("bets", []) or []
    ]
    total_bet = sum(value for _, value in bets)
    if total_bet <= 0 and fallback_total_bet is not None:
        total_bet = fallback_total_bet

    profits = [
        (int(item.get("id", 0)), int(item.get("profit", 0)))
        for item in msg.get("profits", []) or []
    ]
    total_return = sum(value for _, value in profits)
    net_profit = total_return - total_bet

    ids = [int(x) for x in (msg.get("ids", []) or [])]
    counts = Counter(ids)
    result_rates = {
        color_id: PAYOUT_BY_HIT_COUNT.get(count, 0)
        for color_id, count in counts.items()
    }

    return {
        "code": int(msg.get("code", 0) or 0),
        "bets": bets,
        "total_bet": total_bet,
        "profits": profits,
        "total_return": total_return,
        "net_profit": net_profit,
        "ids": ids,
        "result_rates": result_rates,
    }


def format_response_summary(summary: dict) -> str:
    bet_text = format_bets(summary["bets"]) if summary["bets"] else "-"
    profit_text = format_bets(summary["profits"]) if summary["profits"] else "-"
    ids_text = format_ids(summary["ids"]) if summary["ids"] else "-"
    net = summary["net_profit"]
    sign = "+" if net > 0 else ""
    return (
        f"彩球 投入 {bet_text} | 开奖 {ids_text} | "
        f"派彩(含本金) {profit_text} | 总投入:{summary['total_bet']} "
        f"总派彩:{summary['total_return']} 盈利:{sign}{net}"
    )
