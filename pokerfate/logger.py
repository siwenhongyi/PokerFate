"""PokerFate logging module.

控制台：结构化展示每手牌的完整行动序列，方便观测
文件：JSONL 格式，每行一个完整事件，供后续分析/迭代使用

用法：
    from pokerfate.logger import get_logger
    log = get_logger()          # 使用默认配置
    log.decision(...)           # 记录 bot 决策
    log.hand_result(...)        # 记录手牌结果
"""

from __future__ import annotations

import json
import os
import pathlib
import re
import sys
from datetime import datetime, timezone
from typing import Dict, List, Optional

_ANSI_RE = re.compile(r"\033\[[0-9;]*[A-Za-z]")


# ---------------------------------------------------------------------------
# ANSI colors
# ---------------------------------------------------------------------------
class _C:
    RESET  = "\033[0m"
    BOLD   = "\033[1m"
    DIM    = "\033[2m"
    RED    = "\033[91m"
    GREEN  = "\033[92m"
    YELLOW = "\033[93m"
    CYAN   = "\033[96m"
    WHITE  = "\033[97m"
    MAGENTA = "\033[95m"

def _no_color() -> bool:
    return not sys.stdout.isatty() or bool(os.environ.get("NO_COLOR"))


# ---------------------------------------------------------------------------
# Card pretty-printing
# ---------------------------------------------------------------------------
_SUIT_SYMBOL = {"s": "♠", "h": "♥", "d": "♦", "c": "♣"}
_SUIT_COLOR  = {"s": "", "h": _C.RED, "d": _C.RED, "c": ""}

def _fmt_card(card_str: str, use_color: bool) -> str:
    """'As' → 'A♠'  (red for hearts/diamonds when color enabled)"""
    if len(card_str) < 2:
        return card_str
    rank, suit = card_str[:-1], card_str[-1].lower()
    symbol = _SUIT_SYMBOL.get(suit, suit)
    text = rank + symbol
    if use_color:
        color = _SUIT_COLOR.get(suit, "")
        if color:
            return f"{color}{text}{_C.RESET}"
    return text

def _fmt_cards(cards: List[str], use_color: bool) -> str:
    return "  ".join(_fmt_card(c, use_color) for c in cards)


# ---------------------------------------------------------------------------
# Chinese labels
# ---------------------------------------------------------------------------
_STREET_CN = {
    "PREFLOP": "翻牌前",
    "FLOP":    "翻牌",
    "TURN":    "转牌",
    "RIVER":   "河牌",
}
_ACTION_CN = {
    "raise": "加注",
    "call":  "跟注",
    "check": "过牌",
    "fold":  "弃牌",
}
_POS_CN = {
    "BTN": "庄",
    "SB":  "小盲",
    "BB":  "大盲",
    "UTG": "枪口",
    "CO":  "切牌",
    "HJ":  "劫机",
    "MP":  "中位",
}

def _pos(p: str) -> str:
    return _POS_CN.get(p.upper(), p)


# ---------------------------------------------------------------------------
# JSONL file writer
# ---------------------------------------------------------------------------
class _JsonlWriter:
    def __init__(self, filepath: str):
        os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
        self._f = open(filepath, "a", encoding="utf-8", buffering=1)

    def write(self, event: dict):
        event.setdefault("ts", datetime.now(timezone.utc).isoformat())
        self._f.write(json.dumps(event, ensure_ascii=False) + "\n")

    def close(self):
        self._f.close()


# ---------------------------------------------------------------------------
# PokerLogger
# ---------------------------------------------------------------------------
_W = 62   # console width

class PokerLogger:
    """Central logger for PokerFate."""

    def __init__(
        self,
        log_file: Optional[str] = "pokerfate.log",
        console: bool = True,
        hand_number_ref: Optional[list] = None,
    ):
        self._console = console
        self._writer = _JsonlWriter(log_file) if log_file else None
        self._hand_num = hand_number_ref if hand_number_ref is not None else [0]
        self._color = not _no_color()
        self._bot_name = "PokerFate"

        # Plain-text mirror of console output (no ANSI codes)
        self._text_log = None
        if log_file:
            p = pathlib.Path(log_file)
            text_path = p.with_name(p.stem + "_console" + p.suffix)
            text_path.parent.mkdir(parents=True, exist_ok=True)
            self._text_log = open(text_path, "a", encoding="utf-8", buffering=1)

    # ------------------------------------------------------------------
    # Public event methods
    # ------------------------------------------------------------------

    def hand_start(
        self,
        hand_number: int,
        players: List[Dict],
        dealer_id: int,
    ):
        self._hand_num[0] = hand_number
        self._file({
            "event": "hand_start",
            "hand": hand_number,
            "dealer_id": dealer_id,
            "players": players,
        })
        if not self._console:
            return

        # Find bot name
        for p in players:
            if p.get("id") == dealer_id or True:  # always record first time
                pass
        self._bot_name = next(
            (p["name"] for p in players if p.get("pos") != "" and p.get("id") is not None),
            "PokerFate"
        )
        # Use the player with pos BTN or first player as bot (assume player_id tracking)
        # Just use the name of the first player for formatting; API sets this correctly

        # Header
        self._raw("")
        self._raw("━" * _W, bold=True)

        seats = "   ".join(
            f"{p['name']} {p['stack']:.0f}bb [{_pos(p.get('pos', ''))}]"
            for p in players
        )
        hand_tag = f"  第 {hand_number} 手"
        self._raw(f"{hand_tag:<12}{seats}", bold=True)
        self._raw("━" * _W, bold=True)

    def hole_cards(self, cards: List[str]):
        self._file({"event": "hole_cards", "hand": self._hand_num[0], "cards": cards})
        cards_str = _fmt_cards(cards, self._color)
        self._raw(f"  底牌  {cards_str}", color=_C.CYAN, bold=True)
        self._street_header("PREFLOP", [], None)

    def board(self, street: str, cards: List[str], pot: Optional[float] = None):
        self._file({"event": "board", "hand": self._hand_num[0],
                    "street": street, "cards": cards})
        self._street_header(street.upper(), cards, pot)

    def opponent_action(
        self,
        player_name: str,
        action: str,
        amount: float,
        street: str,
    ):
        self._file({
            "event": "opponent_action",
            "hand": self._hand_num[0],
            "player": player_name,
            "action": action,
            "amount": amount,
            "street": street,
        })
        if not self._console:
            return

        cn = _ACTION_CN.get(action, action)
        if action == "raise":
            amt_str = f"{amount:.0f}"
            self._raw(f"    {player_name:<12}  {cn}   {amt_str}", color=_C.YELLOW)
        elif action == "fold":
            self._raw(f"    {player_name:<12}  {cn}", color=_C.RED, dim=True)
        elif action == "call":
            self._raw(f"    {player_name:<12}  {cn}", dim=True)
        elif action == "check":
            self._raw(f"    {player_name:<12}  {cn}", dim=True)
        else:
            self._raw(f"    {player_name:<12}  {cn}", dim=True)

    def decision(
        self,
        action: str,
        amount: float,
        street: str,
        equity: float,
        pot: float,
        to_call: float,
        bot_name: str = "PokerFate",
        reasoning: str = "",
    ):
        """Log the bot's own decision."""
        self._file({
            "event": "decision",
            "hand": self._hand_num[0],
            "street": street,
            "action": action,
            "amount": amount,
            "equity": round(equity, 3),
            "pot": pot,
            "to_call": to_call,
        })
        if not self._console:
            return

        eq_str  = f"胜率 {equity:.0%}"
        pot_str = f"底池 {pot:.0f}"
        cn = _ACTION_CN.get(action, action)

        if action == "raise":
            action_col = f"{cn}  {amount:.0f}"
            color = _C.GREEN
        elif action == "fold":
            action_col = cn
            color = _C.RED
        elif action == "call":
            action_col = f"{cn}  {to_call:.0f}" if to_call > 0 else cn
            color = _C.YELLOW
        else:
            action_col = cn
            color = _C.YELLOW

        line = f"  ► {bot_name:<12}  {action_col:<14}  {eq_str}   {pot_str}"
        self._raw(line, color=color, bold=True)
        if reasoning:
            self._raw(f"      💭 {reasoning}", dim=True)

    def hand_result(
        self,
        winner_names: List[str],
        pot: float,
        my_delta: float,
        final_stacks: Optional[Dict[str, float]] = None,
    ):
        self._file({
            "event": "hand_result",
            "hand": self._hand_num[0],
            "winners": winner_names,
            "pot": pot,
            "my_delta": my_delta,
            "final_stacks": final_stacks or {},
        })
        if not self._console:
            return

        sign  = "+" if my_delta >= 0 else ""
        color = _C.GREEN if my_delta > 0 else (_C.RED if my_delta < 0 else _C.WHITE)
        winners_str = " & ".join(winner_names)
        delta_str   = f"本手 {sign}{my_delta:.0f}"

        stacks_str = ""
        if final_stacks:
            stacks_str = "  │  " + "  ".join(
                f"{name} {s:.0f}" for name, s in final_stacks.items()
            )

        self._raw("")
        self._raw(f"  ✔ {winners_str} 赢得 {pot:.0f}    {delta_str}{stacks_str}",
                  color=color, bold=True)

    def opponent_pattern(
        self,
        player_name: str,
        pattern: str,
        value: float,
        adjustment: str,
    ):
        self._file({
            "event": "opponent_pattern",
            "hand": self._hand_num[0],
            "player": player_name,
            "pattern": pattern,
            "value": round(value, 3),
            "adjustment": adjustment,
        })
        self._raw(
            f"  ⚑ 对手模型  {player_name}: {pattern}={value:.0%} → {adjustment}",
            color=_C.MAGENTA,
        )

    def session_summary(
        self,
        hands_played: int,
        my_delta: float,
        big_blind: float,
    ):
        bb100 = (my_delta / max(hands_played, 1)) / big_blind * 100
        self._file({
            "event": "session_summary",
            "hands": hands_played,
            "my_delta": my_delta,
            "bb_per_100": round(bb100, 2),
        })
        sign  = "+" if my_delta >= 0 else ""
        color = _C.GREEN if my_delta >= 0 else _C.RED
        self._raw("")
        self._raw("━" * _W, bold=True)
        self._raw(
            f"  本局结束  {hands_played} 手    "
            f"{sign}{my_delta:.0f} 筹码    {sign}{bb100:.1f} BB/100",
            bold=True, color=color,
        )
        self._raw("━" * _W, bold=True)

    def raw(self, event: dict):
        """Write an arbitrary event directly to the log file."""
        self._file(event)

    def close(self):
        if self._writer:
            self._writer.close()
        if self._text_log:
            self._text_log.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _street_header(self, street: str, cards: List[str], pot: Optional[float]):
        if not self._console:
            return
        cn        = _STREET_CN.get(street.upper(), street)
        cards_str = ("  " + _fmt_cards(cards, self._color)) if cards else ""
        pot_str   = f"  底池 {pot:.0f}" if pot is not None else ""
        label     = f"  ── {cn}{cards_str}{pot_str} "
        line      = label + "─" * max(0, _W - len(_strip_ansi(label)))
        self._raw("")
        self._raw(line, color=_C.WHITE)

    def _file(self, event: dict):
        if self._writer:
            self._writer.write(event)

    def _raw(
        self,
        msg: str = "",
        color: str = "",
        bold: bool = False,
        dim: bool = False,
    ):
        # Write plain text to file (always, regardless of console setting)
        if self._text_log:
            self._text_log.write(_strip_ansi(msg) + "\n")

        if not self._console:
            return
        if self._color and (bold or dim or color):
            prefix = ""
            if bold:
                prefix += _C.BOLD
            if dim:
                prefix += _C.DIM
            if color:
                prefix += color
            suffix = _C.RESET
            print(f"{prefix}{msg}{suffix}", flush=True)
        else:
            print(msg, flush=True)

    # back-compat alias
    def _con(self, msg: str, color: str = "", bold: bool = False, dim: bool = False):
        self._raw(msg, color=color, bold=bold, dim=dim)


def _strip_ansi(s: str) -> str:
    """Remove ANSI escape codes for length calculation and plain-text output."""
    return _ANSI_RE.sub("", s)


# ---------------------------------------------------------------------------
# Singleton / factory
# ---------------------------------------------------------------------------
_default_logger: Optional[PokerLogger] = None


def get_logger(
    log_file: Optional[str] = "pokerfate.log",
    console: bool = True,
) -> PokerLogger:
    global _default_logger
    if _default_logger is None:
        _default_logger = PokerLogger(log_file=log_file, console=console)
    return _default_logger


def set_logger(logger: Optional[PokerLogger]) -> None:
    global _default_logger
    _default_logger = logger
