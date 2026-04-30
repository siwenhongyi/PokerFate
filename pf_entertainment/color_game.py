from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Iterable


COLOR_IDS: dict[str, int] = {
    "101": 101,
    "yellow": 101,
    "y": 101,
    "黄": 101,
    "黄色": 101,
    "102": 102,
    "gray": 102,
    "grey": 102,
    "g": 102,
    "灰": 102,
    "灰色": 102,
    "103": 103,
    "purple": 103,
    "p": 103,
    "紫": 103,
    "紫色": 103,
    "104": 104,
    "blue": 104,
    "b": 104,
    "蓝": 104,
    "蓝色": 104,
    "105": 105,
    "red": 105,
    "r": 105,
    "红": 105,
    "红色": 105,
    "106": 106,
    "green": 106,
    "gr": 106,
    "绿": 106,
    "绿色": 106,
}

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


class ColorGameParseError(ValueError):
    pass


def _split_key_value(token: str) -> tuple[str, str] | None:
    for sep in ("=", ":", "："):
        if sep in token:
            key, value = token.split(sep, 1)
            return key.strip().lower(), value.strip()
    return None


def _parse_int(name: str, raw: str) -> int:
    try:
        value = int(raw.replace("_", ""))
    except ValueError as exc:
        raise ColorGameParseError(f"{name} 必须是整数: {raw!r}") from exc
    return value


def _parse_color(raw: str) -> int:
    color_id = COLOR_IDS.get(raw.strip().lower())
    if color_id is None:
        raise ColorGameParseError(f"未知颜色: {raw!r}")
    return color_id


def _merge_bets(items: Iterable[tuple[int, int]]) -> tuple[tuple[int, int], ...]:
    merged: dict[int, int] = {}
    for color_id, value in items:
        if value <= 0:
            raise ColorGameParseError("投注数量必须大于 0")
        merged[color_id] = merged.get(color_id, 0) + value
    return tuple((color_id, merged[color_id]) for color_id in sorted(merged))


def parse_color_command(args: list[str]) -> ColorGameCommand:
    """Parse command args after the leading `color` / `彩球` token."""
    if not args:
        raise ColorGameParseError(
            "缺少投注参数，例如: color red=1000 lvl=1"
        )

    lvl = DEFAULT_LEVEL
    from_game_type = DEFAULT_FROM_GAME_TYPE
    room_id = DEFAULT_ROOM_ID
    stake = DEFAULT_STAKE
    strategy = "manual"
    strategy_color = 105
    explicit_bets: list[tuple[int, int]] = []

    for token in args:
        token = token.strip()
        if not token:
            continue
        low = token.lower()
        if low in ("auto", "single", "单押"):
            strategy = "single"
            continue
        if low in ("cover", "spread", "all", "全押", "铺满"):
            strategy = "cover"
            continue

        kv = _split_key_value(token)
        if kv is None:
            # In strategy mode, a bare color selects the strategy color.
            strategy_color = _parse_color(token)
            continue

        key, raw_value = kv
        if key in ("lvl", "level", "等级"):
            lvl = _parse_int(key, raw_value)
        elif key in ("from", "from_game_type", "game", "玩法"):
            from_game_type = _parse_int(key, raw_value)
        elif key in ("room", "room_id", "roomid"):
            room_id = _parse_int(key, raw_value)
        elif key in ("stake", "amount", "bet", "value", "数量", "金额"):
            stake = _parse_int(key, raw_value)
        elif key in ("color", "颜色"):
            strategy_color = _parse_color(raw_value)
        else:
            explicit_bets.append((_parse_color(key), _parse_int(key, raw_value)))

    if not 1 <= lvl <= 5:
        raise ColorGameParseError("lvl 需要在 1..5 之间")
    if room_id < 0:
        raise ColorGameParseError("room_id 不能小于 0")
    if stake <= 0:
        raise ColorGameParseError("stake 必须大于 0")

    if explicit_bets:
        bets = _merge_bets(explicit_bets)
    elif strategy == "cover":
        bets = tuple((color_id, stake) for color_id in ALL_COLOR_IDS)
    else:
        strategy = "single"
        bets = ((strategy_color, stake),)

    return ColorGameCommand(
        bets=bets,
        lvl=lvl,
        from_game_type=from_game_type,
        room_id=room_id,
        strategy=strategy,
    )


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


def strategy_note() -> str:
    return (
        "彩球客户端规则只显示 1/2/3 个命中分别按 2x/3x/10x 派彩，"
        "开奖结果由服务端返回，客户端没有预测入口。若按三球独立均匀估算，"
        "单押任意颜色净盈利概率约 42.13%，期望约 -5.09%；所有颜色期望相同。"
        "当前只保留单色有限倍投方向：命中后停止，达到下注上限仍未盈利则停止。"
    )
