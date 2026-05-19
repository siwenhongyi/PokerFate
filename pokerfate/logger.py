"""PokerFate logging module.

控制台：结构化展示每手牌的完整行动序列，方便观测
文件：JSONL 格式，每行一个完整事件，供后续分析/迭代使用

用法：
    from pokerfate.logger import PokerLogger
    log = PokerLogger()         # 使用默认配置
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
_DEFAULT_LOG_FILE = str(pathlib.Path(__file__).resolve().parent / "logs" / "pokerfate.log")


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


def _card_rank_value(card) -> int:
    try:
        return int(card.rank)
    except Exception:
        text = str(card)
        rank = text[:-1].upper() if len(text) > 1 else text.upper()
        return {
            "2": 2, "3": 3, "4": 4, "5": 5, "6": 6, "7": 7,
            "8": 8, "9": 9, "T": 10, "J": 11, "Q": 12, "K": 13, "A": 14,
        }.get(rank, 0)


def _card_suit_value(card) -> str:
    try:
        return str(card.suit)
    except Exception:
        text = str(card)
        return text[-1:].lower()


def _early_street_board_flags(board: List[object]) -> List[str]:
    if len(board) < 3:
        return []
    ranks = [_card_rank_value(c) for c in board]
    suits = [_card_suit_value(c) for c in board]
    flags: List[str] = []
    if len(set(ranks)) < len(ranks):
        flags.append("paired")
    flop = board[:3]
    if len(flop) == 3 and len({_card_suit_value(c) for c in flop}) == 1:
        flags.append("mono")
    suit_counts: Dict[str, int] = {}
    for suit in suits:
        suit_counts[suit] = suit_counts.get(suit, 0) + 1
    if max(suit_counts.values(), default=0) >= 4:
        flags.append("4flush")
    rank_set = set(ranks)
    if 14 in rank_set:
        rank_set.add(1)
    for start in range(1, 11):
        if len(set(range(start, start + 5)) & rank_set) >= 4:
            flags.append("4straight")
            break
    return flags


def _street_relative_calibration_watch(result) -> Optional[Dict]:
    rec = result.record
    if rec.street not in {"flop", "turn"}:
        return None
    if result.actual_bucket not in {"strong", "nuts"}:
        return None
    if not str(rec.trigger or "").startswith("action:"):
        return None
    subtype = getattr(rec, "hero_made_subtype", "") or ""
    fragile = {
        "clean_overpair",
        "board_pair_pocket_pair",
        "board_pair_pocket_underpair",
        "board_pair_hero_pair",
        "board_pair_kicker",
        "trips",
        "trips_top_kicker",
        "trips_weak_kicker",
        "board_trips_kicker",
        "top_pair_weak_kicker",
    }
    if subtype not in fragile and not subtype.startswith("board_pair_"):
        return None
    flags = _early_street_board_flags(rec.board)
    if not flags:
        return None
    return {
        "street": rec.street,
        "actual_bucket": result.actual_bucket,
        "predicted_bucket_prob": round(float(result.predicted_bucket_prob or 0.0), 4),
        "predicted_hero_eq": (
            round(float(rec.predicted_hero_eq), 4)
            if rec.predicted_hero_eq is not None else None
        ),
        "actual_hero_eq_street": (
            round(float(result.actual_hero_eq_street), 4)
            if result.actual_hero_eq_street is not None else None
        ),
        "hero_made_subtype": subtype,
        "board_flags": flags,
    }


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
        _rotate_log(filepath)
        self._f = open(filepath, "w", encoding="utf-8", buffering=1)

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
        log_file: Optional[str] = _DEFAULT_LOG_FILE,
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
            _rotate_log(str(text_path))
            self._text_log = open(text_path, "w", encoding="utf-8", buffering=1)

    # ------------------------------------------------------------------
    # Public event methods
    # ------------------------------------------------------------------

    def hand_start(
        self,
        hand_number: int,
        players: List[Dict],
        dealer_id: int,
        big_blind: float = 1.0,
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

        bb = max(big_blind, 1.0)
        def _seat_str(p: dict) -> str:
            ptype = p.get("player_type", "")
            tag = f"({ptype})" if ptype else ""
            return f"{p['name']}{tag} {p['stack'] / bb:.0f}bb [{_pos(p.get('pos', ''))}]"
        seats = "   ".join(_seat_str(p) for p in players)
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
        *,
        big_blind: float = 0.0,
        pot: float = 0.0,
        player_type: str = "",
        pwi: float = 0.0,
        range_pct: float = 0.0,
        bucket_dist: Optional[Dict[str, float]] = None,
        vs_hero: Optional[Dict[str, float]] = None,
        to_call: float = 0.0,
        pot_before_action: float = 0.0,
    ):
        self._file({
            "event": "opponent_action",
            "hand": self._hand_num[0],
            "player": player_name,
            "action": action,
            "amount": amount,
            "street": street,
            "player_type": player_type or None,
            "range_pct": round(range_pct, 3) if range_pct > 0 else None,
            "bucket_dist": {k: round(v, 3) for k, v in (bucket_dist or {}).items() if v > 0.01} or None,
            "vs_hero": {k: round(v, 3) for k, v in (vs_hero or {}).items()} or None,
            "pot_before_action": round(pot_before_action, 2) if pot_before_action > 0 else None,
        })
        if not self._console:
            return

        cn = _ACTION_CN.get(action, action)
        bb = big_blind if big_blind > 0 else 1.0

        # ── 标签：type/PWI ──
        tag = ""
        if player_type and player_type != 'unknown':
            _TYPE_SHORT = {
                'nit': '紧手', 'reg': 'reg', 'maniac': '疯狂',
                'whale': '鲸鱼', 'fish': '鱼', 'calling_station': '跟注站',
            }
            tag = f"[{_TYPE_SHORT.get(player_type, player_type)}/PWI{pwi:+.0f}]"

        # ── 范围信息 ──
        range_str = ""
        if range_pct > 0 and action != 'fold':
            _CAT_SHORT = {
                'nuts': '坚果', 'strong': '强', 'medium': '中',
                'draw': '听牌', 'weak_draw': '弱听', 'air': '空气',
            }
            if bucket_dist:
                # 只显示 > 10% 的 bucket，按占比降序
                parts = sorted(
                    ((cat, pct) for cat, pct in bucket_dist.items() if pct >= 0.10),
                    key=lambda x: x[1], reverse=True,
                )
                dist = "/".join(f"{_CAT_SHORT.get(c, c)}{p:.0%}" for c, p in parts)
                range_str = f"range {range_pct:.0%} [{dist}]"
            else:
                range_str = f"range {range_pct:.0%}"

            # 河牌单挑场景：额外显示 hero 视角真实对比（问题 8a）——"坚果"桶
            # 在 hero 自己持 NUTS 档时会过度解读，用 win/tie/loss 直观展示。
            if vs_hero:
                loss = vs_hero.get('loss', 0.0)
                tie = vs_hero.get('tie', 0.0)
                win = vs_hero.get('win', 0.0)
                range_str += f" [≥你{loss:.0%}/平{tie:.0%}/≤你{win:.0%}]"

        # ── 格式化输出 ──
        if action == "raise":
            amt_bb = amount / bb
            # pot 比率（翻后）或 bb 倍数（翻前）
            if street.lower() == "preflop":
                size_str = f"({amt_bb:.0f}bb)"
            elif pot_before_action > 0:
                ratio = amount / pot_before_action
                size_str = f"({amt_bb:.0f}bb {ratio:.1f}x pot)"
            elif pot > 0:
                ratio = amount / pot
                size_str = f"({amt_bb:.0f}bb {ratio:.1f}x pot)"
            else:
                size_str = f"({amt_bb:.0f}bb)"
            # 需跟金额（如果有）
            call_str = ""
            if to_call > 0:
                call_str = f"  需跟{to_call / bb:.0f}bb 赔率{to_call / (pot + to_call):.0%}"
            self._raw(
                f"    {player_name:<12}  {cn}  {amt_bb:.0f}bb  {size_str}  {tag}  {range_str}{call_str}",
                color=_C.YELLOW,
            )
        elif action == "fold":
            self._raw(f"    {player_name:<12}  {cn}", color=_C.RED, dim=True)
        elif action == "call":
            self._raw(
                f"    {player_name:<12}  {cn}  {tag}  {range_str}",
                dim=True,
            )
        elif action == "check":
            self._raw(
                f"    {player_name:<12}  {cn}  {tag}  {range_str}" if range_str else
                f"    {player_name:<12}  {cn}",
                dim=True,
            )
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
        equity_random: Optional[float] = None,
        spr: Optional[float] = None,
        equity_mode: Optional[str] = None,
        gto_refs: Optional[dict] = None,
        elapsed_ms: Optional[float] = None,
        river_relative: Optional[Dict] = None,
        street_relative: Optional[Dict] = None,
    ):
        """Log the bot's own decision."""
        rec: Dict = {
            "event": "decision",
            "hand": self._hand_num[0],
            "street": street,
            "action": action,
            "amount": amount,
            "equity": round(equity, 3),
            "pot": pot,
            "to_call": to_call,
        }
        if equity_random is not None:
            rec["equity_random"] = round(equity_random, 3)
        if spr is not None:
            rec["spr"] = round(spr, 2)
        if equity_mode:
            rec["equity_mode"] = equity_mode
        if elapsed_ms is not None:
            rec["elapsed_ms"] = round(elapsed_ms, 1)
        if river_relative:
            rec["river_relative"] = river_relative
        if street_relative:
            rec["street_relative"] = street_relative
        self._file(rec)
        if not self._console:
            return

        eq_str = f"胜率 {equity:.0%}"
        if equity_random is not None and abs(equity_random - equity) >= 0.01:
            eq_str += f"(vs随机{equity_random:.0%})"
        if spr is not None:
            eq_str += f"  SPR≈{spr:.1f}"
        if equity_mode:
            eq_str += f"  [{equity_mode}]"
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

        time_str = f"  {elapsed_ms:.0f}ms" if elapsed_ms is not None else ""
        line = f"  ► {bot_name:<12}  {action_col:<14}  {eq_str}   {pot_str}{time_str}"
        self._raw(line, color=color, bold=True)

        # reasoning 可能包含多行（\n 分隔），逐行输出
        if reasoning:
            lines = reasoning.split("\n")
            self._raw(f"      💭 {lines[0]}", dim=True)
            for extra in lines[1:]:
                self._raw(f"         {extra.strip()}", dim=True)

        if gto_refs:
            key = gto_refs.get("chart_key", "")
            hand = gto_refs.get("hand", "")
            gl = gto_refs.get("greenline", "—")
            self._raw(f"      📊 [Greenline]  {key} {hand} → {gl}", dim=True)

    def hand_result(
        self,
        winner_names: List[str],
        pot: float,
        my_delta: float,
        final_stacks: Optional[Dict[str, float]] = None,
        showdown_hands: Optional[Dict[str, List[str]]] = None,
        hand_combos: Optional[Dict[str, str]] = None,
        my_combo: Optional[str] = None,
        my_cards: Optional[List[str]] = None,
    ):
        self._file({
            "event": "hand_result",
            "hand": self._hand_num[0],
            "winners": winner_names,
            "pot": pot,
            "my_delta": my_delta,
            "final_stacks": final_stacks or {},
            "showdown_hands": showdown_hands or {},
            "hand_combos": hand_combos or {},
            "my_combo": my_combo or "",
        })
        if not self._console:
            return

        sign  = "+" if my_delta >= 0 else ""
        color = _C.GREEN if my_delta > 0 else (_C.RED if my_delta < 0 else _C.WHITE)

        # 赢家展示：优先用成品牌型，fallback 到原始底牌
        combos = hand_combos or {}
        sd = showdown_hands or {}
        def _fmt_winner(name: str) -> str:
            combo = combos.get(name)
            if combo:
                return f"{name}[{combo}]"
            raw = sd.get(name)
            return f"{name}[{' '.join(raw)}]" if raw else name

        winners_str = " & ".join(_fmt_winner(n) for n in winner_names)
        delta_str   = f"本手 {sign}{my_delta:.0f}"

        # 自己的成品牌型
        my_combo_str = f"  [我: {my_combo}]" if my_combo else ""

        stacks_str = ""
        if final_stacks:
            stacks_str = "  │  " + "  ".join(
                f"{name} {s:.0f}" for name, s in final_stacks.items()
            )

        self._raw("")
        self._raw(f"  ✔ {winners_str} 赢得 {pot:.0f}    {delta_str}{my_combo_str}{stacks_str}",
                  color=color, bold=True)

    def showdown_calibration(
        self,
        player_name: str,
        cards: List[str],
        streets: List[Dict],
    ):
        """Log a showdown calibration update (one line per player per hand).

        Parameters
        ----------
        streets : list of dict
            Each dict: {"street": str, "action": str, "calibrated_factor": float,
                        "gto_factor": float, "sample_count": int,
                        "hand_strength_pct": float or None}
            hand_strength_pct 是该街道下注时的实际手牌强度：
              preflop = 翻前起手牌排名，flop/turn/river = equity vs random
        """
        self._file({
            "event": "showdown_calibration",
            "hand": self._hand_num[0],
            "player": player_name,
            "cards": cards,
            "streets": streets,
        })
        if not self._console or not streets:
            return
        cards_str = _fmt_cards(cards, self._color)

        _CALIB_THRESHOLD = 5
        first_active = any(s["sample_count"] == _CALIB_THRESHOLD for s in streets)

        def _street_tag(s: Dict) -> str:
            n = s["sample_count"]
            pct = s.get("hand_strength_pct")
            pct_str = f"{pct:.0%}" if pct is not None else "?"
            if n >= _CALIB_THRESHOLD:
                direction = "↑宽" if s["calibrated_factor"] > s["gto_factor"] else "↓紧"
                suffix = "★首次生效" if n == _CALIB_THRESHOLD else ""
                return f"{s['street']}:{pct_str} {s['calibrated_factor']:.2f}{direction}({n}手){suffix}"
            return f"{s['street']}:{pct_str} 积累{n}/{_CALIB_THRESHOLD}"

        streets_str = "  ".join(_street_tag(s) for s in streets)
        self._raw(
            f"  ◈ 校准  {player_name}  {cards_str}  {streets_str}",
            color=_C.MAGENTA,
            dim=not first_active,
        )

    def showdown_learner(
        self,
        player_name: str,
        cards: List[str],
        streets: List[Dict],
    ):
        """Log a Range V2 ShowdownLearner update.

        Parameters
        ----------
        streets : list of dict
            Each dict: {"street": str, "action": str, "sample_count": int,
                        "category": str or None,
                        "learned_freq": dict or None}
            category: 本次摊牌该街道的手牌分类 (nuts/strong/medium/draw/air)
            learned_freq: 积累够样本后的分布 {category: pct}，不够时 None
        """
        self._file({
            "event": "showdown_learner",
            "hand": self._hand_num[0],
            "player": player_name,
            "cards": cards,
            "streets": streets,
        })
        if not self._console or not streets:
            return
        cards_str = _fmt_cards(cards, self._color)

        _LEARNER_THRESHOLD = 8

        # 分类缩写
        _CAT_SHORT = {
            'nuts': '坚果', 'strong': '强', 'medium': '中',
            'draw': '听牌', 'weak_draw': '弱听', 'air': '空气',
        }

        first_active = any(s["sample_count"] == _LEARNER_THRESHOLD for s in streets)

        def _street_tag(s: Dict) -> str:
            n = s["sample_count"]
            cat = s.get("category")
            cat_str = _CAT_SHORT.get(cat, cat) if cat else ""

            if n >= _LEARNER_THRESHOLD:
                learned = s.get("learned_freq")
                if learned:
                    # 显示 top 3 类别
                    sorted_cats = sorted(learned.items(), key=lambda x: x[1], reverse=True)[:3]
                    dist_str = "/".join(f"{_CAT_SHORT.get(c, c)}{p:.0%}" for c, p in sorted_cats)
                else:
                    dist_str = "?"
                suffix = " ★首次生效" if n == _LEARNER_THRESHOLD else ""
                return f"{s['street']}:[{cat_str}] {dist_str}({n}手){suffix}"
            return f"{s['street']}:[{cat_str}] 积累{n}/{_LEARNER_THRESHOLD}"

        streets_str = "  ".join(_street_tag(s) for s in streets)
        self._raw(
            f"  ◈ 学习  {player_name}  {cards_str}  {streets_str}",
            color=_C.MAGENTA,
            dim=not first_active,
        )

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

    def calibration_result(self, result) -> None:
        """result: CalibrationResult，hand 结束摊牌后的对比。"""
        rec = result.record
        # 无法形成有效对比（未亮牌/无 hero 卡/阶段实值缺失）时，不写日志
        if rec.predicted_hero_eq is None or result.actual_hero_eq_street is None:
            return
        street_rel_watch = _street_relative_calibration_watch(result)
        payload = {
            "event": "calibration_result",
            "hand": rec.hand_id,
            "street": rec.street,
            "player": rec.player_name,
            "player_id": rec.player_id,
            "trigger": rec.trigger,
            "board": [str(c) for c in rec.board],
            "actual_cards": [str(c) for c in result.actual_cards],
            "actual_bucket": result.actual_bucket,
            "predicted_bucket_prob": round(result.predicted_bucket_prob, 4),
            "hero_made_subtype": getattr(rec, "hero_made_subtype", ""),
            "hero_hand_rank": getattr(rec, "hero_hand_rank", ""),
            "board_texture": getattr(rec, "board_texture", ""),
            "villain_vs_hero_dist": {
                k: round(float(v), 4)
                for k, v in (getattr(rec, "villain_vs_hero_dist", {}) or {}).items()
            },
            "predicted_relation_eq": (
                round(result.predicted_relation_eq, 4)
                if result.predicted_relation_eq is not None else None
            ),
            "actual_relation": result.actual_relation or "",
            "predicted_hero_eq": (round(rec.predicted_hero_eq, 4)
                                  if rec.predicted_hero_eq is not None
                                  else None),
            "actual_hero_eq_street": (round(result.actual_hero_eq_street, 4)
                                      if result.actual_hero_eq_street is not None
                                      else None),
            "eq_prediction_error_street": (round(result.eq_prediction_error_street, 4)
                                           if result.eq_prediction_error_street is not None
                                           else None),
            "predicted_hero_eq_multi": (round(rec.predicted_hero_eq_multi, 4)
                                        if rec.predicted_hero_eq_multi is not None
                                        else None),
            "actual_hero_eq_street_multi": (round(result.actual_hero_eq_street_multi, 4)
                                            if result.actual_hero_eq_street_multi is not None
                                            else None),
            "eq_prediction_error_street_multi": (round(result.eq_prediction_error_street_multi, 4)
                                                 if result.eq_prediction_error_street_multi is not None
                                                 else None),
            "actual_hero_eq_street_multi_shown": (round(result.actual_hero_eq_street_multi_shown, 4)
                                                  if result.actual_hero_eq_street_multi_shown is not None
                                                  else None),
            "active_player_ids": list(rec.active_player_ids),
            "actual_hero_eq_final": (round(result.actual_hero_eq_final, 4)
                                     if result.actual_hero_eq_final is not None
                                     else None),
            "eq_prediction_error": (round(result.eq_prediction_error, 4)
                                    if result.eq_prediction_error is not None
                                    else None),
        }
        if street_rel_watch:
            payload["street_relative_watch"] = street_rel_watch
        self._file(payload)
        if not self._console:
            return

        _CAT_SHORT = {
            'nuts': '坚果', 'strong': '强', 'medium': '中',
            'draw': '听', 'weak_draw': '弱', 'air': '空气',
        }
        bucket_str = _CAT_SHORT.get(result.actual_bucket, result.actual_bucket)
        actual_cards_str = "".join(str(c) for c in result.actual_cards)

        def _tag(err: float) -> str:
            if abs(err) < 0.10:
                return "✓"
            return "↑" if err > 0 else "↓"

        # 单挑 eq 对比（颜色按单挑 Δ 着色——和主逻辑一致）
        err_hu = result.eq_prediction_error_street
        if abs(err_hu) < 0.10:
            color = _C.GREEN
        elif err_hu > 0:
            color = _C.YELLOW
        else:
            color = _C.RED
        hu_part = (f"eq预单挑={rec.predicted_hero_eq:.0%} "
                   f"实单挑={result.actual_hero_eq_street:.0%} "
                   f"Δ={err_hu:+.0%}{_tag(err_hu)}")

        # 多人池 eq 对比——日志只展示"只看亮牌 villain"的版本（人能看懂的真实
        # 摊牌结果）。喂给 calibrator 的是另一个 random-fill 版本（同口径），
        # 那个不打印。
        multi_part = ""
        if rec.predicted_hero_eq_multi is not None:
            shown_actual = result.actual_hero_eq_street_multi_shown
            if shown_actual is not None:
                err_m_shown = rec.predicted_hero_eq_multi - shown_actual
                multi_part = (f" 预全场={rec.predicted_hero_eq_multi:.0%} "
                              f"实全场={shown_actual:.0%} "
                              f"Δ={err_m_shown:+.0%}{_tag(err_m_shown)}")
            else:
                multi_part = f" 预全场={rec.predicted_hero_eq_multi:.0%} 实全场=—"

        bucket_part = (f"实际桶={bucket_str}({actual_cards_str},"
                       f"此桶={result.predicted_bucket_prob:.0%})")
        rel_part = ""
        if result.predicted_relation_eq is not None and result.actual_relation:
            rel_short = {'win': '胜', 'tie': '平', 'loss': '负'}.get(
                result.actual_relation, result.actual_relation,
            )
            rel_part = f" rel预={result.predicted_relation_eq:.0%}/实{rel_short}"

        street_rel_part = ""
        if street_rel_watch:
            flags = ",".join(street_rel_watch.get("board_flags", []) or [])
            actual = _CAT_SHORT.get(
                street_rel_watch.get("actual_bucket", ""),
                street_rel_watch.get("actual_bucket", ""),
            )
            pred_eq = street_rel_watch.get("predicted_hero_eq")
            actual_eq = street_rel_watch.get("actual_hero_eq_street")
            eq_part = ""
            if pred_eq is not None and actual_eq is not None:
                eq_part = f" eq{float(pred_eq):.0%}→{float(actual_eq):.0%}"
            street_rel_part = (
                f" street_rel校={actual} 桶"
                f"{float(street_rel_watch.get('predicted_bucket_prob', 0.0)):.0%}"
                f"{eq_part} board={flags}"
            )

        self._raw(
            f"      ⚖ {rec.street} {rec.player_name} {rec.trigger} "
            f"{bucket_part} {hu_part}{multi_part}{rel_part}{street_rel_part}",
            color=color,
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
            ts = datetime.now().strftime("%H:%M:%S")
            self._text_log.write(f"[{ts}] {_strip_ansi(msg)}\n")

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

    def note(self, msg: str) -> None:
        """写一行系统备注到控制台日志（pokerfate_console.log）。不触发 JSONL 记录。"""
        self._raw(msg)


def _strip_ansi(s: str) -> str:
    """Remove ANSI escape codes for length calculation and plain-text output."""
    return _ANSI_RE.sub("", s)


def _rotate_log(filepath: str) -> None:
    """如果文件已存在，将其内容追加到 *.bak.log，然后清空原文件。"""
    p = pathlib.Path(filepath)
    if not p.exists():
        return
    bak = p.with_name(p.stem + ".bak" + p.suffix)
    bak.parent.mkdir(parents=True, exist_ok=True)
    with open(bak, "a", encoding="utf-8") as dst, \
         open(p, "r", encoding="utf-8") as src:
        dst.write(src.read())
