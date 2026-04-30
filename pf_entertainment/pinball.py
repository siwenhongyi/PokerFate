from __future__ import annotations

from dataclasses import dataclass


DEFAULT_PINBALL_LEVEL = 1
DEFAULT_PINBALL_PER_BET = 1000
DEFAULT_PINBALL_BALL_NUM = 1
DEFAULT_FROM_GAME_TYPE = 0
DEFAULT_ROOM_ID = 0


@dataclass(frozen=True)
class PinballCommand:
    lvl: int = DEFAULT_PINBALL_LEVEL
    per_bet: int = DEFAULT_PINBALL_PER_BET
    ball_num: int = DEFAULT_PINBALL_BALL_NUM
    from_game_type: int = DEFAULT_FROM_GAME_TYPE
    room_id: int = DEFAULT_ROOM_ID

    @property
    def total_bet(self) -> int:
        return self.per_bet * self.ball_num

    def to_fields(self) -> dict:
        return {
            "from_game_type": self.from_game_type,
            "lvl": self.lvl,
            "per_bet": self.per_bet,
            "ball_num": self.ball_num,
        }


class PinballParseError(ValueError):
    pass


def parse_pinball_command(args: list[str]) -> PinballCommand:
    if args:
        raise PinballParseError("弹珠任务固定使用最低下注，不支持额外参数")
    return PinballCommand()


def summarize_pinball_response(
    msg: dict,
    fallback_total_bet: int | None = None,
) -> dict:
    action_result = msg.get("action_result") or {}
    balls = [
        {
            "ball_id": int(item.get("ball_id", 0) or 0),
            "export_id": int(item.get("export_id", 0) or 0),
            "reward": int(item.get("reward", 0) or 0),
            "profit": int(item.get("profit", 0) or 0),
        }
        for item in (action_result.get("balls", []) or [])
    ]
    total_return = sum(item["reward"] for item in balls)
    total_profit = sum(item["profit"] for item in balls)
    if fallback_total_bet is not None:
        total_bet = fallback_total_bet
    elif balls:
        total_bet = max(0, total_return - total_profit)
    else:
        total_bet = 0
    net_profit = total_profit if balls else total_return - total_bet

    return {
        "code": int(msg.get("code", 0) or 0),
        "total_bet": total_bet,
        "total_return": total_return,
        "net_profit": net_profit,
        "balls": balls,
        "start_time": int(action_result.get("start_time", 0) or 0),
        "ball_fire_interval": int(action_result.get("ball_fire_interval", 0) or 0),
        "per_ball_move_time": int(action_result.get("per_ball_move_time", 0) or 0),
        "from_game_type": int(action_result.get("from_game_type", 0) or 0),
    }


def format_pinball_balls(balls: list[dict]) -> str:
    if not balls:
        return "-"
    return " ".join(
        (
            f"ball:{item['ball_id']}"
            f"/出口:{item['export_id']}"
            f"/奖励:{item['reward']}"
            f"/盈利:{item['profit']:+d}"
        )
        for item in balls
    )


def format_pinball_response_summary(summary: dict) -> str:
    net = int(summary["net_profit"])
    sign = "+" if net > 0 else ""
    return (
        f"弹珠 结果 {format_pinball_balls(summary['balls'])} | "
        f"总投入:{summary['total_bet']} 总奖励:{summary['total_return']} "
        f"盈利:{sign}{net}"
    )
