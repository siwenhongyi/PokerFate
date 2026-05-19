"""PokerFate External Interface — Event-Driven API

外部接入说明
============

外部系统只需与本文件的 `PokerFateAPI` 类交互，无需了解内部实现。

接入流程（每手牌）：
  1. api.new_hand(...)              # 新一手牌开始（传入当前所有玩家信息）
  2. api.deal_hole_cards(...)       # 发底牌给 bot
  3. api.notify_action(...)         # 通知各玩家行动（可多次调用）
  4. api.deal_board(...)            # 发公共牌（翻牌/转牌/河牌）
  5. action = api.request_action()  # 需要 bot 行动时调用，获取决策
  6. api.hand_over(...)             # 手牌结束，传入 final_stacks 更新筹码

事件通知与决策请求可以穿插调用，与实际游戏节奏一致。

筹码追踪策略（两种情况均已处理）：
  - 每手牌结束时调用 hand_over(final_stacks={...}) ——
    API 会将本手结果持久化到会话注册表，下一手自动使用
  - PlayerInfo.stack 可以传 None ——
    API 自动从会话注册表查找，查不到则默认 100 BB
  - 对手替换/新玩家加入：调用 notify_player_joined() 或
    直接在 new_hand() 中传入新的 player_id 即可；
    新 player_id 自动获得干净的对手模型（历史数据不会污染）
"""

from __future__ import annotations
import hashlib
import os
import time
import traceback
from collections import Counter
from dataclasses import dataclass
from typing import List, Optional, Dict
from pathlib import Path

_UNSET = object()  # sentinel for log_file default

from pokerfate.core.card import Card
from pokerfate.core.config import MIN_HANDS_FOR_CLASSIFICATION
from pokerfate.core.game_state import GameState, Player, Street, Action, ActionType
from pokerfate.core.hand_evaluator import HandEvaluator, HandRank
from pokerfate.bot.poker_bot import PokerBot
from pokerfate.logger import PokerLogger
from pokerfate.strategy.range_estimator import (
    _ACTION_COMPRESSION_RAISE_PREFLOP,
    _ACTION_COMPRESSION_RAISE_POSTFLOP,
)
from pokerfate.strategy.range_v2.showdown_learner import ShowdownLearner, _board_at_street
from pokerfate.strategy.range_v2.hand_categorizer import categorize_cards
from pokerfate.strategy.range_estimator import ShowdownCalibrator
from pokerfate.data import init as _init_data

# 启动时预加载静态数据（GTO charts 等）
_init_data()

_DEFAULT_LOG_FILE    = str(Path(__file__).resolve().parent / "logs" / "pokerfate.log")
_DEFAULT_OPPONENTS   = str(Path(__file__).resolve().parent / "data" / "opponents.json")

_PUSH_STREET_LABELS = {
    "preflop": "翻前",
    "flop": "翻牌",
    "turn": "转牌",
    "river": "河牌",
}
_PUSH_ACTION_LABELS = {
    ActionType.FOLD: "弃",
    ActionType.CHECK: "过",
    ActionType.CALL: "跟",
    ActionType.RAISE: "加",
}
_PUSH_SUIT_SYMBOLS = {"s": "♠️", "h": "♥️", "d": "♦️", "c": "♣️"}
_AUTO_COLLECT_HAND_RANKS = {
    HandRank.FOUR_OF_A_KIND: "四条",
    HandRank.STRAIGHT_FLUSH: "同花顺",
    HandRank.ROYAL_FLUSH: "皇家同花顺",
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


def _push_card_text(card) -> str:
    s = str(card)
    if len(s) < 2:
        return s
    return s[:-1] + _PUSH_SUIT_SYMBOLS.get(s[-1].lower(), s[-1])


def _push_cards_text(cards) -> str:
    return " ".join(_push_card_text(c) for c in cards)


# ---------------------------------------------------------------------------
# Public data types for the external interface
# ---------------------------------------------------------------------------

@dataclass
class PlayerInfo:
    """Describes one player at the table.

    stack may be None when the opponent's exact chip count is unknown
    (e.g. a new player joining mid-session). The API will fall back to
    the last known stack from session history, or a default of 100 BB.
    """
    player_id: int
    name: str
    stack: Optional[float] = None   # None = unknown / use session default
    position: str = ""              # e.g. "BTN", "BB", "UTG"


@dataclass
class ActionEvent:
    """An action taken by any player (including opponents)."""
    player_id: int
    action: str           # "fold" | "check" | "call" | "raise"
    # raise/bet: total bet size this street. call: chips added by this call.
    # For backwards compatibility, call amount=0 means "infer call amount from
    # the current highest street bet".
    amount: float = 0.0
    street: str = ""


@dataclass
class BotDecision:
    """The bot's chosen action, returned to the external system."""
    action: str           # "fold" | "check" | "call" | "raise"
    amount: float = 0.0   # For raise: total bet size (chips to put in total this street)

    def __repr__(self) -> str:
        if self.action == "raise":
            return f"BotDecision(raise, amount={self.amount:.1f})"
        return f"BotDecision({self.action})"


# ---------------------------------------------------------------------------
# Main API class
# ---------------------------------------------------------------------------

class PokerFateAPI:
    """External interface for the PokerFate bot.

    Usage example:
    --------------
        api = PokerFateAPI(my_player_id=0, big_blind=2.0)

        # Start of hand
        api.new_hand(
            players=[
                PlayerInfo(0, "PokerFate", 200.0, "BTN"),
                PlayerInfo(1, "GPT-Bot",   200.0, "BB"),
            ],
            dealer_id=0,
        )

        # Bot receives hole cards
        api.deal_hole_cards(["Ac", "Kd"])

        # Opponent posts BB (optional to notify, but helps modeling)
        api.notify_action(ActionEvent(player_id=1, action="raise", amount=2.0, street="preflop"))

        # Bot must act
        decision = api.request_action(
            street="preflop",
            pot=3.0,
            current_bet=2.0,
            to_call=2.0,
            my_stack=200.0,
        )
        print(decision)  # BotDecision(raise, amount=6.0)

        # Flop is dealt
        api.deal_board(["As", "7d", "2c"], street="flop")

        # Opponent checks
        api.notify_action(ActionEvent(player_id=1, action="check", street="flop"))

        # Bot acts again
        decision = api.request_action(
            street="flop",
            pot=7.0,
            current_bet=0.0,
            to_call=0.0,
            my_stack=197.0,
        )
        print(decision)
    """

    def __init__(
        self,
        my_player_id: int = 0,
        big_blind: float = 2.0,
        small_blind: float = 1.0,
        equity_iterations: int = 800,
        autosave_path: Optional[str] = _UNSET,
        log_file: Optional[str] = _UNSET,
        verbose: bool = False,
        use_range_equity: bool = True,
        enable_showdown_calibration: bool = True,
        decision_seed: Optional[int] = None,
    ):
        """
        Parameters
        ----------
        my_player_id : int
            The player ID assigned to this bot.
        big_blind : float
            Table big blind size.
        small_blind : float
            Table small blind size.
        equity_iterations : int
            Monte Carlo iterations for equity (higher = more accurate but slower).
        autosave_path : str or None
            Path to JSON file for opponent model persistence.
            After every hand_over() call, the model is automatically saved here.
            On startup, existing data is automatically loaded from this file.
            Set to None to disable autosave.
        log_file : str or None
            Path to JSONL log file. None disables file logging.
        verbose : bool
            If True, also print debug-level internal details to console.
            Key events (decisions, results) are always printed regardless.
        """
        self.my_player_id = my_player_id
        self.big_blind = big_blind
        self.small_blind = small_blind
        self.verbose = verbose
        self._decision_seed_base = decision_seed
        self._decision_index = 0
        _in_test = bool(os.environ.get("PYTEST_CURRENT_TEST"))
        if autosave_path is _UNSET:
            autosave_path = None if _in_test else _DEFAULT_OPPONENTS
        self.autosave_path = autosave_path
        if log_file is _UNSET:
            log_file = None if _in_test else _DEFAULT_LOG_FILE
        self._log = PokerLogger(log_file=log_file, console=True)
        self._default_stack = 100.0 * big_blind  # fallback when stack is unknown

        self._bot = PokerBot(
            name="PokerFate",
            equity_iterations=equity_iterations,
            use_range_equity=use_range_equity,
        )

        # Auto-load opponent data (+ embedded showdown/learner data) from disk on startup
        if autosave_path:
            self._bot.opponent_model = self._bot.opponent_model.__class__.load(autosave_path)
            if self._bot.opponent_model._stats:
                self._log.raw({"event": "model_loaded", "path": autosave_path,
                               "known_opponents": len(self._bot.opponent_model._stats)})
            showdown_raw = self._bot.opponent_model._showdown_data
            if showdown_raw:
                if use_range_equity:
                    # Range V2: load ShowdownLearner data (key: "range_v2_learner")
                    v2_data = showdown_raw.get('range_v2_learner')
                    if v2_data:
                        self._bot._showdown_learner = ShowdownLearner.from_dict(v2_data)
                        self._bot._action_model.showdown_learner = self._bot._showdown_learner
                    # 缺陷 C: Hero equity meta-calibrator 持久化
                    heq_data = showdown_raw.get('hero_eq_calibrator')
                    if heq_data:
                        from pokerfate.strategy.range_v2.hero_eq_calibrator import (
                            HeroEquityCalibrator,
                        )
                        self._bot._hero_eq_calibrator = HeroEquityCalibrator.from_dict(heq_data)
                    river_rel_data = showdown_raw.get('river_relative_calibrator')
                    if river_rel_data:
                        from pokerfate.strategy.range_v2.river_relative_calibrator import (
                            RiverRelativeCalibrator,
                        )
                        self._bot._river_relative_calibrator = (
                            RiverRelativeCalibrator.from_dict(river_rel_data)
                        )
                else:
                    # EQR: load ShowdownCalibrator
                    self._bot.range_estimator.showdown_calibrator = ShowdownCalibrator.from_dict(showdown_raw)

        # Session-level state: persists across hands
        self._session_stacks: Dict[int, float] = {}   # player_id -> last known stack
        self._session_names: Dict[int, str] = {}      # player_id -> name
        self._session_delta: float = 0.0              # cumulative P&L this session

        # Hand state: rebuilt each hand
        self._players: List[Player] = []
        self._hole_cards: List[Card] = []
        self._board: List[Card] = []
        self._action_history: List[tuple] = []
        self._dealer_id: int = 0
        self._hand_number: int = 0
        self._street_base_pot: float = 0.0
        self._street_base_street: str = "preflop"
        self._street_contribs: Dict[int, float] = {}
        self._last_hand_push_detail: str = ""
        self._last_auto_collect_reasons: list[str] = []
        self._runtime_calibration_recorder = None

        # ── 2026-04-23: Showdown calibration ──
        # 每次 tracker range 调整时记录预测，手牌结束时对比摊牌实际，写入
        # pokerfate.log JSON 流供 offline 校准分析。仅 range_v2 路径启用。
        if self._bot.use_range_equity and enable_showdown_calibration:
            from pokerfate.calibration import ShowdownCalibrator
            self._calibrator = ShowdownCalibrator(logger=self._log)
            # 挂到 tracker：每次权重更新会回调 calibrator.record_prediction
            tracker = self._bot._range_tracker
            def _prediction_hook_filtered(**kwargs):
                # 不记录 hero 自己的 calibration 预测；只看对手
                pid = kwargs.get("player_id")
                if pid == self.my_player_id:
                    return
                # tracker._weights 里包括 hero 自己，active_weights 把 hero
                # 也塞进去会让"多人池 hero eq"错误地把 hero 当成对手，并且
                # 摊牌校准时 hero 不在 _shown_cards → 永远算不出"实全场"。
                aw = kwargs.get("active_weights")
                if aw:
                    kwargs["active_weights"] = {
                        p: w for p, w in aw.items() if p != self.my_player_id
                    }
                self._calibrator.record_prediction(**kwargs)
            tracker._prediction_hook = _prediction_hook_filtered
            tracker._name_resolver = lambda pid: self._session_names.get(pid, str(pid))
            from pokerfate.calibration import RuntimeCalibrationRecorder
            self._runtime_calibration_recorder = RuntimeCalibrationRecorder()
        else:
            self._calibrator = None

    def set_table_blinds(self, big_blind: float, small_blind: float) -> None:
        """Update blinds after EnterRoomRSP (new table); refreshes unknown-stack fallback."""
        self.big_blind = float(big_blind)
        self.small_blind = float(small_blind)
        self._default_stack = 100.0 * self.big_blind

    # ------------------------------------------------------------------
    # Hand lifecycle events
    # ------------------------------------------------------------------

    def new_hand(
        self,
        players: List[PlayerInfo],
        dealer_id: int,
    ) -> None:
        """Call at the start of each new hand.

        Parameters
        ----------
        players : list of PlayerInfo
            All players at the table (including this bot).
            A player's stack may be None if unknown — the API will use
            the last recorded stack from session history, or 100 BB as
            a conservative default for brand-new opponents.
        dealer_id : int
            player_id of the dealer/button.

        Notes
        -----
        - If a player_id appears that was not seen before, they are
          treated as a new opponent with a fresh opponent model.
        - If a previously busted player is replaced by a new player_id,
          the old model is automatically abandoned (keyed by player_id).
        """
        self._hand_number += 1
        self._dealer_id = dealer_id
        self._hole_cards = []
        self._board = []
        self._action_history = []
        self._last_hand_push_detail = ""
        self._last_auto_collect_reasons = []
        self._decision_index = 0
        self._my_stack_start: float = 0.0  # set after resolving stacks below

        # Start showdown calibration for this hand
        if self._calibrator is not None:
            self._calibrator.start_hand(self._hand_number)

        # Preflop 初始 pot ≈ SB + BB（盲注已投入）。以前设 0 会让 notify_action
        # 里 `bet_ratio = bet_amount / pot` 在第一次 preflop open 时恒为 0，
        # 吞掉 open 尺寸信号（问题 2 的 deep open-shove range 窄化依赖此信号）。
        self._last_known_pot: float = self.small_blind + self.big_blind
        self._street_base_pot = self._last_known_pot
        self._street_base_street = "preflop"
        self._street_contribs = {}
        # Per-hand position map: player_id → position string (UTG/MP/CO/...).
        # Populated from PlayerInfo.position at hand start; consumed by
        # Range V2 tracker.reset_hand and per-action observe_action as
        # `opp_position`. Fresh every hand (positions rotate).
        self._hand_positions: Dict[int, str] = {}
        self._players = []
        for p in players:
            # Resolve stack: explicit > session history > default
            stack = p.stack
            if stack is None:
                stack = self._session_stacks.get(p.player_id, self._default_stack)

            self._session_names[p.player_id] = p.name
            # None → '' so downstream treats as unknown; '' triggers the
            # CO-neutral fallback in tracker.reset_hand. (Never look this
            # value up with dict.get(k, default) — the entry exists as '',
            # so the default never fires. Use `value or 'CO'` instead.)
            self._hand_positions[p.player_id] = p.position or ''
            if p.stack is not None:
                self._session_stacks[p.player_id] = p.stack

            # Register name for cross-session opponent model lookup
            if p.player_id != self.my_player_id:
                self._bot.opponent_model.register_name(p.player_id, p.name)

            self._players.append(Player(
                player_id=p.player_id,
                name=p.name,
                stack=stack,
            ))

        # Record my stack at the start of this hand for delta calculation
        my_p = self._get_my_player()
        self._my_stack_start = my_p.stack if my_p else 0.0

        all_ids = [p.player_id for p in players if p.player_id != self.my_player_id]
        player_names = {p.player_id: p.name for p in players if p.player_id != self.my_player_id}
        player_positions = {
            p.player_id: (p.position or '')
            for p in players if p.player_id != self.my_player_id
        }
        self._bot.new_hand(
            all_ids,
            player_names=player_names,
            player_positions=player_positions,
        )

        _TYPE_CN = {
            "nit":             "紧手",
            "calling_station": "跟注站",
            "maniac":          "疯狂激进",
            "whale":           "超松被动",
            "reg":             "常规玩家",
            "fish":            "鱼",
            "unknown":         "未知",
        }

        # 与 OpponentStats.player_type() 共用 core.config.MIN_HANDS_FOR_CLASSIFICATION；
        # 样本不足时只标「数据不足N手」，不用已失真的 player_type。

        def _player_type_tag(player_id: int) -> str:
            if player_id == self.my_player_id:
                return ""
            s = self._bot.opponent_model.get(player_id)
            if s.hands_seen < MIN_HANDS_FOR_CLASSIFICATION:
                return f"数据不足{s.hands_seen}手"
            return _TYPE_CN.get(s.player_type(), s.player_type())

        self._log.hand_start(
            hand_number=self._hand_number,
            players=[
                {"id": p.player_id, "name": p.name,
                 "stack": p.stack, "pos": pi.position,
                 "player_type": _player_type_tag(p.player_id)}
                for p, pi in zip(self._players, players)
            ],
            dealer_id=dealer_id,
            big_blind=self.big_blind,
        )

    def deal_hole_cards(self, cards: List[str]) -> None:
        """Tell the bot its hole cards.

        Parameters
        ----------
        cards : list of str
            Two card strings, e.g. ["Ac", "Kd"]
        """
        self._hole_cards = [Card.from_str(c) for c in cards]
        my_player = self._get_my_player()
        if my_player:
            my_player.hole_cards = self._hole_cards

        # Range V2: card removal for bot's hole cards
        self._bot.set_hole_cards(self._hole_cards)

        self._log.hole_cards(cards)

    def restore_board(self, cards: List[str]) -> None:
        """重连时静默恢复公共牌，不触发日志/统计（仅还原 _board 状态）。"""
        self._board = [Card.from_str(c) for c in cards]

    def deal_board(self, cards: List[str], street: str, pot: Optional[float] = None) -> None:
        """Notify the bot of new community cards.

        Parameters
        ----------
        cards : list of str
            The newly dealt cards (3 for flop, 1 for turn/river).
            Pass only the NEW cards, not all board cards.
        street : str
            "flop" | "turn" | "river"
        pot : float, optional
            Actual pot size at the start of this street. Recommended for
            accurate display; falls back to last known pot if omitted.
        """
        new_cards = [Card.from_str(c) for c in cards]
        self._board.extend(new_cards)
        for p in self._players:
            p.current_bet = 0.0
        self._street_contribs = {}

        # Range V2: update board for observe_action
        self._bot.update_board(self._board)

        display_pot = pot if pot is not None else self._last_known_pot
        if pot is not None:
            self._last_known_pot = pot
        self._street_base_pot = display_pot
        self._street_base_street = street.lower()
        self._log.board(street, cards, pot=display_pot)

        # Track flop_seen for WTSD denominator: all non-hero, non-folded players
        if street.lower() == 'flop':
            for p in self._players:
                if p.player_id != self.my_player_id and not p.is_folded:
                    self._bot.opponent_model.record_flop_seen(p.player_id)

    # ------------------------------------------------------------------
    # Action notification
    # ------------------------------------------------------------------

    def notify_action(self, event: ActionEvent) -> None:
        """Notify the bot of any player's action (for opponent modeling).

        Parameters
        ----------
        event : ActionEvent
            The action taken.
        """
        if event.player_id == self.my_player_id:
            return  # Don't track our own actions for modeling

        action_name = event.action.lower()
        street_key = event.street.lower()
        player = self._get_player(event.player_id)
        street_max_before = self._current_street_max_bet()
        amount_added, total_bet_after = self._normalize_action_amounts(
            event, player, street_max_before,
        )

        # Compute spot types BEFORE appending current action to history
        is_3bet_spot = self._detect_3bet_spot(event)
        is_fold_to_3bet_spot = self._detect_fold_to_3bet_spot(event)
        is_cbet_spot = self._detect_cbet_spot(event)
        is_facing_bet_spot = self._detect_facing_bet_spot(event)

        # Determine if this raise is over someone else's bet (vs first-bet).
        # MUST be computed BEFORE appending the current event — if we count
        # AFTER the append, this event's own raise is always in the count,
        # so `count > 0` is trivially true and `is_raise_over` becomes
        # permanently True, silently disabling the `_ACT_BET` pattern branch
        # and breaking triple_barrel detection. (Original P0 bug from review.)
        is_raise_over = False
        if action_name == 'raise':
            prior_raises_this_street = sum(
                1 for pid, a, s in self._action_history
                if s == street_key and a.action_type == ActionType.RAISE
            )
            is_raise_over = prior_raises_this_street > 0

        normalized_action_amount = (
            total_bet_after if action_name == 'raise' else amount_added
        )
        action = self._parse_action(event, normalized_action_amount)
        # Include street so GameState can find last aggressor on this street (full-hand history).
        self._action_history.append((event.player_id, action, street_key))

        # Feed into opponent model with correct spot context.
        # bet_ratio for sizing_adj: 也给 raise_over 喂一个可用的 ratio。
        # 2026-04-25 修复：之前 raise_over 传 0 → SIZING_CATEGORY_ADJ 直接跳过 →
        # tracker 对 whale 4.2x pot check-raise 和 0.5x bet 的桶间 likelihood 比例
        # 完全一致。这导致 S2·20 / S3·57 等 hero 面对 whale 大 raise 仍认为
        # villain range 有大量 air 的灾难。
        #
        # 估算：pot_at_action = _last_known_pot + 本街已累积 current_bet。
        # 对首次下注这个就是 _last_known_pot。对 raise_over，我们加上桌上其他
        # 玩家本街已投入的 current_bet 估计当前池子。
        opp_pos = self._hand_positions.get(event.player_id) or ''
        base_pot = getattr(self, '_street_base_pot', self._last_known_pot)
        pot_at_action = base_pot + self._observed_street_contrib_total()
        pot_for_model = max(1.0, pot_at_action)
        bet_amount_for_model = (
            total_bet_after if action_name == 'raise' else amount_added
        )

        # Update player state after deriving all pre-action diagnostics.
        self._apply_player_action(
            player, action_name, amount_added, total_bet_after,
        )
        self._record_street_contribution(event.player_id, amount_added)

        self._bot.observe_action(
            player_id=event.player_id,
            action=action,
            street=event.street,
            is_cbet_spot=is_cbet_spot,
            is_3bet_spot=is_3bet_spot,
            is_fold_to_3bet_spot=is_fold_to_3bet_spot,
            is_facing_bet_spot=is_facing_bet_spot,
            bet_amount=bet_amount_for_model,
            pot=pot_for_model,
            opp_position=opp_pos,
            is_raise_over=is_raise_over,
        )

        pobj = self._get_player(event.player_id)
        name = pobj.name if pobj else str(event.player_id)

        # Gather extra context for enriched opponent action log
        opp_stats = self._bot.opponent_model.get(event.player_id)
        ptype = opp_stats.player_type() if opp_stats.hands_seen >= MIN_HANDS_FOR_CLASSIFICATION else ''
        pwi = opp_stats.pwi()

        range_pct = 0.0
        bucket_dist = None
        vs_hero = None
        if self._bot.use_range_equity:
            range_pct = self._bot._range_tracker.get_effective_range_pct(event.player_id)
            if self._board:
                bucket_dist = self._bot._range_tracker.get_bucket_distribution(
                    event.player_id, self._board,
                )
                # River HU: compute hero-relative distribution so log shows
                # "beats hero %" instead of only the overloaded NUTS bucket
                # (see get_vs_hero_dist docstring — fix for problem 8a).
                if self._hole_cards and len(self._board) >= 5:
                    vs_hero = self._bot._range_tracker.get_vs_hero_dist(
                        event.player_id, self._board, self._hole_cards,
                    )

        # to_call for the BOT (how much we'd need to call if it's our turn next)
        to_call = 0.0
        if action_name == 'raise':
            my_player = self._get_my_player()
            if my_player:
                my_current_bet = getattr(my_player, 'current_bet', 0.0) or 0.0
                to_call = max(0.0, total_bet_after - my_current_bet)

        self._log.opponent_action(
            name, event.action, normalized_action_amount, event.street,
            big_blind=self.big_blind,
            pot=self._last_known_pot,
            player_type=ptype,
            pwi=pwi,
            range_pct=range_pct,
            bucket_dist=bucket_dist,
            vs_hero=vs_hero,
            to_call=to_call,
            pot_before_action=pot_at_action,
        )

        # Check for newly significant opponent patterns and surface them
        self._maybe_log_opponent_pattern(event.player_id, name)

    def notify_stack_update(self, player_id: int, new_stack: float) -> None:
        """Update a player's stack at any point (e.g. after side-pot resolution).

        Also persists to the session registry for future hands.
        """
        player = self._get_player(player_id)
        if player:
            player.stack = new_stack
        self._session_stacks[player_id] = new_stack

    def notify_player_left(self, player_id: int) -> None:
        """Notify that a player has vacated their seat mid-session.

        Call this when a StandUpBRC / OtherLeaveRoomBRC arrives and
        a player is confirmed gone. This ensures the next player to
        occupy the same seat (player_id / seatid) does NOT inherit
        the departed player's opponent-model data.

        Parameters
        ----------
        player_id : int
            The departing player's ID (same value used in new_hand / notify_action).
        """
        self._session_stacks.pop(player_id, None)
        self._session_names.pop(player_id, None)
        self._bot.opponent_model.unregister_seat(player_id)
        # Remove from current hand's active player list if mid-hand
        self._players = [p for p in self._players if p.player_id != player_id]
        if self.verbose:
            self._log.raw({"event": "player_left", "player_id": player_id})

    def notify_player_joined(
        self,
        player_id: int,
        name: str,
        stack: Optional[float] = None,
    ) -> None:
        """Notify that a new player has joined (or replaced a busted one).

        Call this between hands when the seat composition changes.
        The new player gets a fresh opponent model automatically.
        Their stack defaults to 100 BB if not provided.

        Parameters
        ----------
        player_id : int
            The new player's ID (must be different from any current player).
        name : str
            Display name.
        stack : float, optional
            Starting stack. None = use 100 BB default.
        """
        resolved_stack = stack if stack is not None else self._default_stack
        self._session_stacks[player_id] = resolved_stack
        self._session_names[player_id] = name
        # Register name: if this name was seen before with a different ID,
        # historical stats are automatically migrated to the new ID.
        self._bot.opponent_model.register_name(player_id, name)
        if self.verbose:
            self._log.raw({"event": "player_joined", "player_id": player_id,
                           "name": name, "stack": resolved_stack})

    # ------------------------------------------------------------------
    # Decision request
    # ------------------------------------------------------------------

    def request_action(
        self,
        street: str,
        pot: float,
        current_bet: float,
        to_call: float,
        my_stack: float,
        num_active_opponents: int = 1,
        my_current_bet_this_street: float = 0.0,
        is_bb_option: bool = False,
    ) -> BotDecision:
        """Ask the bot for its action.

        Call this whenever the bot needs to act.

        Parameters
        ----------
        street : str
            Current street: "preflop" | "flop" | "turn" | "river"
        pot : float
            Current pot size (before any call/raise by the bot).
        current_bet : float
            The highest bet on the table this street (0 if no bet yet).
        to_call : float
            Amount the bot needs to add to call (0 if no bet to call).
        my_stack : float
            Bot's current stack.
        num_active_opponents : int
            Number of opponents still in the hand.
        my_current_bet_this_street : float
            Amount the bot has already put in this street (for raise calculations).

        Returns
        -------
        BotDecision
            The bot's chosen action and amount.
        """
        self._last_known_pot = pot
        street_key = street.lower()
        if getattr(self, '_street_base_street', street_key) != street_key:
            for p in self._players:
                p.current_bet = 0.0
            self._street_contribs = {}
            self._street_base_street = street_key
        my_live = self._get_my_player()
        if my_live:
            my_live.stack = float(my_stack)
            my_live.current_bet = float(my_current_bet_this_street)
        self._street_base_pot = max(
            0.0, float(pot) - self._observed_street_contrib_total(),
        )
        # Build a minimal GameState for the bot
        gs = self._build_game_state(
            street=street,
            pot=pot,
            current_bet=current_bet,
            my_stack=my_stack,
            my_current_bet_this_street=my_current_bet_this_street,
        )

        self._bot.set_next_decision_seed(
            self._next_decision_seed(
                street=street_key,
                pot=pot,
                current_bet=current_bet,
                to_call=to_call,
                my_stack=my_stack,
            )
        )
        t0 = time.perf_counter()
        action = self._bot.decide(gs, self.my_player_id, is_bb_option=is_bb_option)
        elapsed_ms = (time.perf_counter() - t0) * 1000
        decision = self._to_decision(action)

        # Record bot's own action into _action_history so that
        # _classify_preflop_action's total-raise counter sees a correct
        # bet level (e.g. "bot open + villain re-raise" → 2 raises → 3bet
        # facing bot, not mis-classified as 'open'). notify_action skips
        # my_player_id, so we must append manually here.
        self._action_history.append(
            (self.my_player_id, action, street.lower())
        )

        my_name = self._session_names.get(self.my_player_id, "PokerFate")
        # 用实际需补差额，避免 BB 已 post 时 to_call 被误传为盲注金额
        effective_to_call = max(0.0, current_bet - my_current_bet_this_street)
        # 短码时 hero 跟不到对手满注，日志显示应按实际能付金额封顶
        # （不影响决策，决策内部已根据短码 effective pot_odds 自行判断；
        # 仅修日志误导：原来显示 "跟注 825000" 但 hero 只有 100000，实际 all-in）
        effective_to_call = min(effective_to_call, float(my_stack))
        if my_live:
            if decision.action == 'raise':
                total_bet_after = max(
                    float(decision.amount or 0.0),
                    float(my_current_bet_this_street),
                )
                amount_added = max(
                    0.0, total_bet_after - float(my_current_bet_this_street),
                )
            elif decision.action == 'call':
                amount_added = effective_to_call
                total_bet_after = float(my_current_bet_this_street) + amount_added
            else:
                amount_added = 0.0
                total_bet_after = float(my_current_bet_this_street)
            self._apply_player_action(
                my_live, decision.action, amount_added, total_bet_after,
            )
            self._record_street_contribution(self.my_player_id, amount_added)
        self._log.decision(
            action=decision.action,
            amount=decision.amount,
            street=street,
            equity=self._bot.last_equity,
            pot=pot,
            to_call=effective_to_call,
            bot_name=my_name,
            reasoning=self._bot.last_reasoning,
            equity_random=getattr(self._bot, "last_equity_random", None),
            spr=getattr(self._bot, "last_spr", None),
            equity_mode=getattr(self._bot, "last_equity_mode", None),
            gto_refs=getattr(self._bot, "last_gto_refs", None),
            elapsed_ms=elapsed_ms,
            river_relative=(
                getattr(self._bot, "last_decision_diagnostics", {})
                .get("river_relative", {})
            ),
            street_relative=(
                getattr(self._bot, "last_decision_diagnostics", {})
                .get("street_relative", {})
            ),
        )

        return decision

    def _next_decision_seed(
        self,
        *,
        street: str,
        pot: float,
        current_bet: float,
        to_call: float,
        my_stack: float,
    ) -> Optional[int]:
        if self._decision_seed_base is None:
            return None
        self._decision_index += 1
        payload = "|".join([
            str(int(self._decision_seed_base)),
            str(self._hand_number),
            str(self._decision_index),
            street,
            ",".join(str(c) for c in self._hole_cards),
            ",".join(str(c) for c in self._board),
            f"{pot:.2f}",
            f"{current_bet:.2f}",
            f"{to_call:.2f}",
            f"{my_stack:.2f}",
            str(len(self._action_history)),
        ])
        digest = hashlib.blake2b(payload.encode("utf-8"), digest_size=4).digest()
        seed = int.from_bytes(digest, "big")
        return seed or 1

    # ------------------------------------------------------------------
    # Hand result (optional, for tracking)
    # ------------------------------------------------------------------

    @staticmethod
    def _fmt_best5(score: tuple, cards: list) -> str:
        """将 best5 按牌型排序并格式化为带花色符号的字符串。

        排序规则：按出现频率降序（多张在前），同频率内按点数降序。
        示例：葫芦 → 三张在前+两张在后；两对 → 大对+小对+踢脚；四条 → 四张+踢脚
        """
        is_straight = score[0] in (4, 8)  # STRAIGHT or STRAIGHT_FLUSH
        if is_straight:
            # Wheel (A-2-3-4-5): A acts as 1, sort as 5-4-3-2-A
            is_wheel = score[1] == 5 and any(c.rank.value == 14 for c in cards)
            if is_wheel:
                sorted_cards = sorted(cards, key=lambda c: c.rank.value if c.rank.value != 14 else 0, reverse=True)
            else:
                sorted_cards = sorted(cards, key=lambda c: c.rank.value, reverse=True)
        else:
            counts = Counter(c.rank.value for c in cards)
            sorted_cards = sorted(cards, key=lambda c: (counts[c.rank.value], c.rank.value), reverse=True)
        return ' '.join(_push_card_text(c) for c in sorted_cards)

    # Server hand type int → Chinese name (from PKHelper.lua)
    _SERVER_HAND_TYPE_CN = {
        1: '高牌',
        2: '一对', 3: '两对', 4: '三条', 5: '顺子',
        6: '同花', 7: '葫芦', 8: '四条', 9: '同花顺', 10: '皇家同花顺',
    }

    @staticmethod
    def _server_hand_type_rank(type_int: int | None) -> Optional[HandRank]:
        if type_int is None:
            return None
        try:
            value = int(type_int)
        except (TypeError, ValueError):
            return None
        if not 1 <= value <= 10:
            return None
        return HandRank(value - 1)

    def hand_over(
        self,
        winner_ids: List[int],
        pot: float,
        final_stacks: Optional[Dict[int, float]] = None,
        showdown_hands: Optional[Dict[int, List[str]]] = None,
        winner_hand_types: Optional[Dict[int, int]] = None,
        my_profit_delta: Optional[float] = None,
    ) -> None:
        """Notify the bot that the hand is over.

        Parameters
        ----------
        winner_ids : list of int
            The winning player IDs.
        pot : float
            Total pot awarded.
        final_stacks : dict, optional
            {player_id: stack} — each player's stack after this hand.
            Strongly recommended: pass this so the API tracks stacks
            accurately across hands, buy-ins, and rebuys.
            If omitted, stacks are estimated from observed actions.
        showdown_hands : dict, optional
            {player_id: ["Ac", "Kd"]} — revealed hands at showdown.
        winner_hand_types : dict, optional
            {player_id: server_type_int} — server-provided hand type for winners
            (from WinnerRSP.winner.type). Takes priority over local evaluation.
        my_profit_delta : float, optional
            Hero's net gain/loss this hand, as reported by the server
            (WinnerRSP.profit). Preferred over computing from stack diff,
            because stack diff is wrong on profit_lock leave-reenter
            cycles (stack drops to 100 BB re-buy while the hand itself
            may have been a normal win/loss/chop).
        """
        if final_stacks:
            for pid, stack in final_stacks.items():
                self._session_stacks[pid] = stack
                player = self._get_player(pid)
                if player:
                    player.stack = stack

        winner_names = list(dict.fromkeys(
            self._session_names.get(wid, str(wid)) for wid in winner_ids
        ))
        my_final = (final_stacks or {}).get(self.my_player_id)
        # Prefer server-reported per-hand profit delta (WinnerRSP.profit):
        # it is the authoritative hand outcome, already net of rake / uncalled
        # bets, and — critically — is correct even on profit_lock leave-reenter
        # cycles where my_final reflects the 100 BB rebuy rather than the hand.
        # Fall back to stack diff for callers that don't plumb it through (tests).
        if my_profit_delta is not None:
            my_delta = float(my_profit_delta)
        elif my_final is not None:
            my_delta = my_final - self._my_stack_start
        else:
            my_delta = 0.0
        self._session_delta += my_delta

        # showdown_hands: pid→cards 转成 name→cards（用于 JSON 日志）
        sd_by_name: dict = {}
        if showdown_hands:
            for pid, cards in showdown_hands.items():
                name = self._session_names.get(pid, str(pid))
                sd_by_name[name] = [str(c) for c in cards]

        def _fmt_hole(cards) -> str:
            """底牌格式化（带花色符号），用于 fallback 展示。"""
            return _push_cards_text(cards)

        # 构建每个 showdown 玩家的成品展示：
        #   - 牌型名：优先用服务端 winner_hand_types，否则本地评估
        #   - 最佳5张：只有总牌数足够时本地计算；异常短公牌 replay 直接降级展示
        wht = winner_hand_types or {}
        hand_combos: dict = {}
        if showdown_hands and self._board:
            for pid, cards in showdown_hands.items():
                name = self._session_names.get(pid, str(pid))
                hole = [Card.from_str(c) if isinstance(c, str) else c for c in cards]
                server_type = wht.get(pid)
                server_rank = self._server_hand_type_rank(server_type)
                rank_cn = server_rank.cn_name() if server_rank is not None else None
                if len(hole) + len(self._board) >= 5:
                    try:
                        score, best5 = HandEvaluator.best_five(hole + self._board)
                        local_rank = HandRank(score[0])
                        # 牌型名：服务端优先
                        if rank_cn is None:
                            rank_cn = local_rank.cn_name()
                        hand_combos[name] = f"{rank_cn} {self._fmt_best5(score, best5)}"
                    except Exception as e:
                        print(f"[hand_combos ERROR] pid={pid} cards={cards} board={[str(c) for c in self._board]}")
                        traceback.print_exc()
                elif rank_cn is not None:
                    hand_combos[name] = rank_cn
                else:
                    hand_combos[name] = _fmt_hole(hole)
        # 兜底：有 winner_hand_types 但没有底牌数据时，至少展示牌型名
        # （包括：preflop 结束 / 对手没有亮牌但服务端下发了牌型）
        if wht:
            for pid, type_int in wht.items():
                name = self._session_names.get(pid, str(pid))
                if name not in hand_combos:
                    server_rank = self._server_hand_type_rank(type_int)
                    rank_cn = server_rank.cn_name() if server_rank is not None else None
                    if rank_cn:
                        hand_combos[name] = rank_cn

        # 自己的成品：本地计算（服务端不单独下发我的牌型）
        my_combo: str | None = None
        my_server_rank = self._server_hand_type_rank(wht.get(self.my_player_id))
        if self._hole_cards and self._board and len(self._hole_cards) + len(self._board) >= 5:
            try:
                score, best5 = HandEvaluator.best_five(self._hole_cards + self._board)
                local_rank = HandRank(score[0])
                rank_cn = (my_server_rank or local_rank).cn_name()
                my_combo = f"{rank_cn} {self._fmt_best5(score, best5)}"
            except Exception as e:
                print(f"[best_five ERROR] hole={[str(c) for c in self._hole_cards]} board={[str(c) for c in self._board]}")
                traceback.print_exc()
                my_combo = _fmt_hole(self._hole_cards)
        elif self._hole_cards:
            # 翻前弃牌（无公牌）：显示底牌
            my_combo = _fmt_hole(self._hole_cards)

        self._last_hand_push_detail = self._build_hand_push_detail(
            winner_names=winner_names,
            pot=pot,
            my_delta=my_delta,
            final_stacks=final_stacks or {},
            showdown_hands=showdown_hands or {},
            hand_combos=hand_combos or {},
            my_combo=my_combo,
        )
        self._last_auto_collect_reasons = self._build_auto_collect_reasons(
            winner_ids=winner_ids,
        )

        self._log.hand_result(
            winner_names=winner_names,
            pot=pot,
            my_delta=my_delta,
            final_stacks={
                self._session_names.get(pid, str(pid)): s
                for pid, s in (final_stacks or {}).items()
            },
            showdown_hands=sd_by_name or None,
            hand_combos=hand_combos or None,
            my_combo=my_combo,
        )

        # Track showdown stats (WTSD / WMSD)
        winner_id_set = set(winner_ids) if winner_ids else set()
        if showdown_hands:
            for pid in showdown_hands:
                if pid != self.my_player_id:
                    self._bot.opponent_model.record_showdown(pid, won=(pid in winner_id_set))

        # bluff_win_rate：赢底池时记录牌型（含无底牌的上界估算）
        # 对每个赢家：有下注行为 + 知道牌型（服务端下发或摊牌得到）→ 记录
        if winner_ids and wht:
            for pid in winner_ids:
                if pid == self.my_player_id:
                    continue
                hand_type = wht.get(pid)
                if hand_type is None:
                    continue
                # 判断本手该玩家是否有过下注/加注行为
                if self._bot.use_range_equity:
                    action_seq = self._bot._v2_action_history.get(pid, [])
                else:
                    action_seq = self._bot.range_estimator._hand_actions.get(pid, [])
                had_aggression = any(a == 'raise' for _, a in action_seq)
                self._bot.opponent_model.record_win_with_hand_type(pid, hand_type, had_aggression)

        if self._bot.use_range_equity:
            # ── Range V2 showdown processing ──
            if showdown_hands:
                # 先把所有亮牌 villain 的底牌预先喂给 calibrator，这样每个
                # villain 的 ⚖ 输出里"多人池实际胜率"能引用其他 villain 的
                # 真手牌（多人池模拟需要所有活跃对手的牌）。
                if self._calibrator is not None:
                    for pid, cards in showdown_hands.items():
                        if pid == self.my_player_id:
                            continue
                        hole_pre = [Card.from_str(str(c)) if isinstance(c, str) else c
                                    for c in cards[:2]]
                        self._calibrator.record_actual(
                            player_id=pid,
                            actual_cards=hole_pre,
                            final_board=self._board,
                            hero_cards=self._hole_cards,
                        )

                for pid, cards in showdown_hands.items():
                    if pid == self.my_player_id:
                        continue
                    name = self._session_names.get(pid, str(pid))
                    hole = [Card.from_str(str(c)) if isinstance(c, str) else c for c in cards[:2]]
                    self._bot.observe_showdown(pid, cards, name=name, board=self._board)
                    # Log with Range V2 format
                    learner = self._bot._showdown_learner
                    card_strs = [str(c) for c in cards]
                    action_seq = self._bot._v2_action_history.get(pid, [])
                    street_entries = []
                    for street_key in ('preflop', 'flop', 'turn', 'river'):
                        n = learner.sample_count(name, street_key, 'raise')
                        if n == 0:
                            continue
                        learned = learner.get_learned_freq(name, street_key, 'raise')
                        # 本次摊牌在该街道的 category
                        street_board = _board_at_street(self._board, street_key)
                        cat = categorize_cards(hole, street_board) if street_board or street_key == 'preflop' else None
                        # 只有本手在该街道有 raise 行动才显示 category
                        had_action = any(s == street_key and a == 'raise' for s, a in action_seq)
                        street_entries.append({
                            "street": street_key,
                            "action": "raise",
                            "sample_count": n,
                            "category": cat if had_action else None,
                            "learned_freq": learned,
                        })
                    if street_entries:
                        self._log.showdown_learner(
                            player_name=name,
                            cards=card_strs,
                            streets=street_entries,
                        )
                    # 紧跟 ◈ 学习 之后输出该 villain 的所有 ⚖ 校准记录
                    if self._calibrator is not None:
                        results = self._calibrator.emit_records_for(
                            player_id=pid,
                            hero_cards=self._hole_cards,
                            final_board=self._board,
                        )
                        # 缺陷 C: 同时把 (hero_bucket, street, n_opp,
                        # action_ctx, predicted_multi, actual_multi) 喂给
                        # hero 自校准器。action_ctx 从 snapshot 的 trigger
                        # 推导——separating passive / bet / raise，避免不同
                        # 压缩档位的 bias 互相稀释。
                        from pokerfate.strategy.range_v2.hero_eq_calibrator import (
                            classify_action_ctx_from_trigger,
                        )
                        for r in results:
                            rec = r.record
                            action_ctx = classify_action_ctx_from_trigger(rec.trigger)
                            if (
                                rec.predicted_hero_eq_multi is not None
                                and r.actual_hero_eq_street_multi is not None
                                and rec.hero_bucket
                            ):
                                self._bot._hero_eq_calibrator.record(
                                    bucket=rec.hero_bucket,
                                    street=rec.street,
                                    num_opp=len(rec.active_player_ids),
                                    predicted=rec.predicted_hero_eq_multi,
                                    actual=r.actual_hero_eq_street_multi,
                                    action_ctx=action_ctx,
                                )
                            if (
                                rec.street == 'river'
                                and rec.villain_vs_hero_dist
                                and r.actual_relation
                                and rec.hero_bucket
                            ):
                                self._bot._river_relative_calibrator.record(
                                    hero_bucket=rec.hero_bucket,
                                    hero_made_subtype=rec.hero_made_subtype,
                                    board_texture=rec.board_texture,
                                    action_ctx=action_ctx,
                                    predicted_dist=rec.villain_vs_hero_dist,
                                    actual_relation=r.actual_relation,
                                )
                        if self._runtime_calibration_recorder is not None and results:
                            try:
                                self._runtime_calibration_recorder.write_results(
                                    results,
                                    big_blind=self.big_blind,
                                    final_board=self._board,
                                    source="runtime",
                                )
                            except Exception:
                                traceback.print_exc()
        else:
            # ── EQR showdown processing ──
            # Showdown calibration: update range estimator with revealed hands + log
            if showdown_hands:
                _ACTION_COMPRESSION_RAISE_ALL = {
                    "preflop": _ACTION_COMPRESSION_RAISE_PREFLOP,
                    **_ACTION_COMPRESSION_RAISE_POSTFLOP,
                }
                for pid, cards in showdown_hands.items():
                    if pid == self.my_player_id:
                        continue
                    name = self._session_names.get(pid, str(pid))
                    strength_by_street = self._bot.observe_showdown(pid, cards, name=name, board=self._board) or {}
                    cal = self._bot.range_estimator.showdown_calibrator
                    card_strs = [str(c) for c in cards]
                    street_entries = []
                    for street_key, gto_factor in _ACTION_COMPRESSION_RAISE_ALL.items():
                        n = cal.sample_count(name, "raise", street_key)
                        if n == 0:
                            continue
                        street_entries.append({
                            "street": street_key, "action": "raise",
                            "calibrated_factor": cal.calibrated_factor(name, "raise", street_key, gto_factor),
                            "gto_factor": gto_factor, "sample_count": n,
                            "hand_strength_pct": strength_by_street.get(street_key),
                        })
                    if street_entries:
                        self._log.showdown_calibration(
                            player_name=name, cards=card_strs, streets=street_entries,
                        )

        # Auto-save opponent model + showdown/learner data into one file
        if self.autosave_path:
            if self._bot.use_range_equity:
                sd_data = {
                    'range_v2_learner': self._bot._showdown_learner.to_dict(),
                    'hero_eq_calibrator': self._bot._hero_eq_calibrator.to_dict(),
                    'river_relative_calibrator': (
                        self._bot._river_relative_calibrator.to_dict()
                    ),
                }
            else:
                sd_data = self._bot.range_estimator.showdown_calibrator.to_dict()
            self._bot.opponent_model.save(
                self.autosave_path,
                showdown_data=sd_data,
            )

    def last_hand_push_detail(self, max_bytes: int = 2200) -> str:
        """Return the latest hand detail in a push-friendly compact form."""
        return _fit_utf8(self._last_hand_push_detail, max_bytes)

    def last_auto_collect_reasons(self) -> list[str]:
        """Reasons why the latest hand should be auto-collected."""
        return list(self._last_auto_collect_reasons)

    def _build_auto_collect_reasons(self, *, winner_ids: List[int]) -> list[str]:
        if self.my_player_id not in set(winner_ids):
            return []

        rank = self._my_best_hand_rank()
        if rank is None:
            return []

        if rank == HandRank.FULL_HOUSE:
            if not self._board_has_rank_trip():
                return ["葫芦"]
            return []

        label = _AUTO_COLLECT_HAND_RANKS.get(rank)
        return [label] if label else []

    def _my_best_hand_rank(self) -> Optional[HandRank]:
        if not self._hole_cards or len(self._hole_cards) + len(self._board) < 5:
            return None
        try:
            score = HandEvaluator.evaluate(self._hole_cards + self._board)
        except Exception:
            return None
        return score[0]

    def _board_has_rank_trip(self) -> bool:
        return any(count >= 3 for count in Counter(c.rank.value for c in self._board).values())

    def _build_hand_push_detail(
        self,
        *,
        winner_names: List[str],
        pot: float,
        my_delta: float,
        final_stacks: Dict[int, float],
        showdown_hands: Dict[int, List[str]],
        hand_combos: Dict[str, str],
        my_combo: Optional[str],
    ) -> str:
        lines: list[str] = []
        lines.append(f"手牌: {_push_cards_text(self._hole_cards) or '-'}")
        lines.append(f"牌面: {self._push_board_text()}")

        action_lines = self._push_action_lines()
        if action_lines:
            lines.append("行动:")
            lines.extend(action_lines)
        else:
            lines.append("行动: -")

        lines.extend(self._push_showdown_lines(showdown_hands, hand_combos, winner_names))

        winners = " & ".join(self._short_push_name(n) for n in winner_names) or "-"
        sign = "+" if my_delta >= 0 else ""
        lines.append(f"结果: {winners} 赢池 {pot:.0f}，我 {sign}{my_delta:.0f}")
        if my_combo:
            lines.append(f"我牌型: {my_combo}")

        my_final = final_stacks.get(self.my_player_id)
        if my_final is not None:
            lines.append(f"我结算筹码: {my_final:.0f}")
        return "\n".join(lines)

    def _push_board_text(self) -> str:
        board = list(self._board)
        if not board:
            return "-"
        parts: list[str] = []
        if len(board) >= 3:
            parts.append(_push_cards_text(board[:3]))
        if len(board) >= 4:
            parts.append(_push_cards_text(board[3:4]))
        if len(board) >= 5:
            parts.append(_push_cards_text(board[4:5]))
        if not parts:
            parts.append(_push_cards_text(board))
        return " | ".join(parts)

    def _push_action_lines(self) -> list[str]:
        grouped: dict[str, list[str]] = {
            "preflop": [],
            "flop": [],
            "turn": [],
            "river": [],
        }
        for item in self._action_history:
            if len(item) < 3:
                continue
            pid, action, street = item[0], item[1], str(item[2]).lower()
            if street not in grouped:
                continue
            grouped[street].append(self._push_action_text(pid, action))

        lines: list[str] = []
        for street in ("preflop", "flop", "turn", "river"):
            actions = grouped.get(street) or []
            if not actions:
                continue
            lines.append(f"{_PUSH_STREET_LABELS[street]}: " + "; ".join(actions))
        return lines

    def _push_action_text(self, player_id: int, action: Action) -> str:
        who = "我" if player_id == self.my_player_id else self._short_push_name(
            self._session_names.get(player_id, str(player_id))
        )
        label = _PUSH_ACTION_LABELS.get(action.action_type, str(action.action_type))
        amount = float(getattr(action, "amount", 0.0) or 0.0)
        if action.action_type in (ActionType.CALL, ActionType.RAISE) and amount > 0:
            return f"{who}{label}{self._push_amount(amount)}"
        return f"{who}{label}"

    def _push_amount(self, amount: float) -> str:
        bb = float(self.big_blind or 0.0)
        if bb <= 0:
            return f"{amount:.0f}"
        amount_bb = amount / bb
        if abs(amount_bb - round(amount_bb)) < 0.05:
            return f"{amount_bb:.0f}bb"
        return f"{amount_bb:.1f}bb"

    def _push_showdown_lines(
        self,
        showdown_hands: Dict[int, List[str]],
        hand_combos: Dict[str, str],
        winner_names: List[str],
    ) -> list[str]:
        lines: list[str] = []
        shown_names: set[str] = set()

        if showdown_hands:
            parts: list[str] = []
            for pid in sorted(showdown_hands):
                raw_name = self._session_names.get(pid, str(pid))
                shown_names.add(raw_name)
                who = "我" if pid == self.my_player_id else self._short_push_name(raw_name)
                cards = _push_cards_text(showdown_hands[pid])
                combo = hand_combos.get(raw_name, "")
                text = f"{who}:{cards}"
                if combo:
                    text += f" {combo}"
                parts.append(text)
            lines.append("亮牌: " + "; ".join(parts))

        type_parts: list[str] = []
        my_name = self._session_names.get(self.my_player_id, str(self.my_player_id))
        for raw_name in winner_names:
            if raw_name in shown_names:
                continue
            combo = hand_combos.get(raw_name)
            if not combo:
                continue
            who = "我" if raw_name == my_name else self._short_push_name(raw_name)
            type_parts.append(f"{who}:{combo}")
        if type_parts:
            lines.append("赢家牌型: " + "; ".join(type_parts))

        if not lines:
            lines.append("亮牌: 无")
        return lines

    @staticmethod
    def _short_push_name(name: str, max_chars: int = 10) -> str:
        text = str(name).strip() or "-"
        if len(text) <= max_chars:
            return text
        return text[:max_chars] + "~"

    # ------------------------------------------------------------------
    # Convenience: parse card strings
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save_opponent_data(self, filepath: str) -> None:
        """Persist opponent model to disk."""
        self._bot.opponent_model.save(filepath)
        self._log.raw({"event": "model_saved", "path": filepath})

    def load_opponent_data(self, filepath: str) -> None:
        """Load previously saved opponent data from disk (no-op if file missing)."""
        self._bot.opponent_model = self._bot.opponent_model.__class__.load(filepath)
        self._log.raw({"event": "model_loaded", "path": filepath,
                       "known_opponents": len(self._bot.opponent_model._stats)})

    def opponent_summary(self) -> str:
        """Return a readable summary of all known opponents."""
        return self._bot.opponent_model.summary()

    # ------------------------------------------------------------------
    # Convenience: parse card strings
    # ------------------------------------------------------------------

    @staticmethod
    def parse_cards(card_strings: List[str]) -> List[Card]:
        """Utility: convert card strings to Card objects."""
        return [Card.from_str(c) for c in card_strings]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    # threshold tracking: avoid logging the same pattern repeatedly
    _PATTERN_LOG_INTERVAL = 20   # log a pattern at most once per N hands

    def _maybe_log_opponent_pattern(self, player_id: int, name: str):
        """Surface significant opponent patterns to the log (throttled)."""
        s = self._bot.opponent_model.get(player_id)
        if s.hands_seen < MIN_HANDS_FOR_CLASSIFICATION:
            return
        adj = self._bot.opponent_model.exploit_adjustments(player_id)
        if not adj:
            return
        # Only log once per interval to avoid spam
        key = f"_pattern_logged_{player_id}"
        last = getattr(self, key, 0)
        if self._hand_number - last < self._PATTERN_LOG_INTERVAL:
            return
        setattr(self, key, self._hand_number)

        # adj 只含连续 scale（不再有 cbet_freq / bluff_freq 离散字段）。
        # 从 scale 反推展示标签：bluff_ag_scale 是决策层用的连续值，
        # 在这里派生成 log 的一行"模式摘要"。
        bluff_ag = adj.get("bluff_ag_scale", 0.55)
        value_ag = adj.get("value_ag_scale", 1.0)
        if s.fold_to_cbet_opps >= 5 and (bluff_ag >= 0.85 or bluff_ag <= 0.18):
            tag = "high_fold" if bluff_ag >= 0.85 else "value_only"
            self._log.opponent_pattern(name, "fold_to_cbet",
                                       s.fold_to_cbet, tag)
        elif bluff_ag <= 0.22:
            self._log.opponent_pattern(name, "player_type",
                                       s.vpip, f"bluff_ag×{bluff_ag:.2f}")
        elif bluff_ag >= 0.90:
            self._log.opponent_pattern(name, "player_type",
                                       s.vpip, f"bluff_ag×{bluff_ag:.2f}")

        # ── 新信号：面对对手下注时的读牌信号 ──
        river_bf_samples = s.river_bet_count + s.river_check_count
        if river_bf_samples >= 8:
            if adj.get("river_bluff_likely"):
                self._log.opponent_pattern(
                    name, "river_bluff_likely",
                    s.river_bet_frequency, "equity+7%")
            elif adj.get("river_bet_rare"):
                self._log.opponent_pattern(
                    name, "river_bet_rare",
                    s.river_bet_frequency, "equity-5%")

        if adj.get("flop_float_favorable"):
            self._log.opponent_pattern(
                name, "flop_afq_high",
                s.flop_afq, "float+5%")
        if adj.get("turn_bluff_then_fold"):
            self._log.opponent_pattern(
                name, "turn_barrel_give_up",
                s.turn_afq, "equity+5%@turn")

        # ── 新信号：我方主动决策时的手牌质量信号 ──
        # 原本用 bluff_freq=='none' 离散判断；改为 bluff_ag_scale 连续阈值。
        if s.showdown_count >= 8:
            if adj.get("value_sizing_scale", 1.0) >= 1.10 and adj.get("bluff_ag_scale", 0.55) <= 0.18:
                self._log.opponent_pattern(
                    name, "calling_station",
                    s.wmsd, f"wtsd={s.wtsd:.0%} thin_value+no_bluff")

    def session_summary(self):
        """Print and log a session-end summary."""
        self._log.session_summary(self._hand_number, self._session_delta, self.big_blind)

    @property
    def logger(self) -> PokerLogger:
        """Direct access to the underlying PokerLogger."""
        return self._log

    def _detect_3bet_spot(self, event: ActionEvent) -> bool:
        """True if this action is a response to exactly one preflop open raise.

        Uses action history BEFORE the current event is appended.
        """
        if event.street.lower() != "preflop":
            return False
        if event.action.lower() not in ("fold", "call", "raise"):
            return False
        player_already_raised = any(
            len(item) >= 3
            and item[2] == "preflop"
            and item[0] == event.player_id
            and item[1].action_type == ActionType.RAISE
            for item in self._action_history
        )
        if player_already_raised:
            return False
        raises_by_others = [
            item[0] for item in self._action_history
            if len(item) >= 3
            and item[2] == "preflop"
            and item[1].action_type == ActionType.RAISE
            and item[0] != event.player_id
        ]
        return len(raises_by_others) == 1

    def _detect_fold_to_3bet_spot(self, event: ActionEvent) -> bool:
        """True when the original opener is responding to a preflop 3bet."""
        if event.street.lower() != "preflop":
            return False
        if event.action.lower() not in ("fold", "call", "raise"):
            return False
        raises = [
            item for item in self._action_history
            if len(item) >= 3
            and item[2] == "preflop"
            and item[1].action_type == ActionType.RAISE
        ]
        if len(raises) != 2:
            return False
        last_raiser = raises[-1][0]
        if last_raiser == event.player_id:
            return False
        return any(pid == event.player_id for pid, _, _ in raises[:-1])

    def _detect_cbet_spot(self, event: ActionEvent) -> bool:
        """True if villain is responding to a real continuation bet.

        Requires hero to be the previous street's last aggressor and the
        current street's first and latest bettor. This prevents turn/river
        actions from inheriting an unrelated old raise.
        """
        street = event.street.lower()
        if street == "preflop":
            return False
        raises_this_street = [
            item for item in self._action_history
            if len(item) >= 3
            and item[2] == street
            and item[1].action_type == ActionType.RAISE
        ]
        if not raises_this_street:
            return False
        if raises_this_street[0][0] != self.my_player_id:
            return False
        if raises_this_street[-1][0] != self.my_player_id:
            return False
        prev_street = {
            "flop": "preflop",
            "turn": "flop",
            "river": "turn",
        }.get(street)
        if prev_street is None:
            return False
        return self._last_aggressor_on_street(prev_street) == self.my_player_id

    def _detect_facing_bet_spot(self, event: ActionEvent) -> bool:
        """True if this action responds to an existing bet on this street."""
        if event.action.lower() not in ("fold", "call", "raise"):
            return False
        street = event.street.lower()
        for item in reversed(self._action_history):
            if len(item) < 3 or item[2] != street:
                continue
            pid, act = item[0], item[1]
            if act.action_type == ActionType.RAISE:
                return pid != event.player_id
        return False

    def _last_aggressor_on_street(self, street: str) -> Optional[int]:
        sk = street.lower()
        for item in reversed(self._action_history):
            if len(item) < 3 or item[2] != sk:
                continue
            pid, act = item[0], item[1]
            if act.action_type == ActionType.RAISE:
                return pid
        return None

    def _build_game_state(
        self,
        street: str,
        pot: float,
        current_bet: float,
        my_stack: float,
        my_current_bet_this_street: float,
    ) -> GameState:
        street_map = {
            "preflop": Street.PREFLOP,
            "flop":    Street.FLOP,
            "turn":    Street.TURN,
            "river":   Street.RIVER,
        }
        street_enum = street_map.get(street.lower(), Street.PREFLOP)

        # Reconstruct players list with current info
        players = []
        my_idx = 0
        for i, p in enumerate(self._players):
            player = Player(
                player_id=p.player_id,
                name=p.name,
                stack=my_stack if p.player_id == self.my_player_id else p.stack,
                hole_cards=self._hole_cards if p.player_id == self.my_player_id else [],
                current_bet=(
                    my_current_bet_this_street
                    if p.player_id == self.my_player_id
                    else p.current_bet
                ),
                is_folded=p.is_folded,
            )
            players.append(player)
            if p.player_id == self.my_player_id:
                my_idx = i

        # Dealer position (index in players list)
        dealer_pos = 0
        for i, p in enumerate(players):
            if p.player_id == self._dealer_id:
                dealer_pos = i
                break

        gs = GameState(
            players=players,
            dealer_pos=dealer_pos,
            street=street_enum,
            board=list(self._board),
            pot=pot,
            current_bet=current_bet,
            big_blind=self.big_blind,
            small_blind=self.small_blind,
            current_player_idx=my_idx,
            action_history=list(self._action_history),
        )
        return gs

    def _parse_action(self, event: ActionEvent, amount: Optional[float] = None) -> Action:
        action_map = {
            "fold":  ActionType.FOLD,
            "check": ActionType.CHECK,
            "call":  ActionType.CALL,
            "raise": ActionType.RAISE,
        }
        atype = action_map.get(event.action.lower(), ActionType.FOLD)
        return Action(atype, event.amount if amount is None else amount)

    def _current_street_max_bet(self) -> float:
        return max(
            (getattr(p, 'current_bet', 0.0) or 0.0 for p in self._players),
            default=0.0,
        )

    def _observed_street_contrib_total(self) -> float:
        return sum(float(v or 0.0) for v in self._street_contribs.values())

    def _record_street_contribution(self, player_id: int, amount_added: float) -> None:
        if amount_added <= 0:
            return
        self._street_contribs[player_id] = (
            self._street_contribs.get(player_id, 0.0) + float(amount_added)
        )
        self._last_known_pot = (
            getattr(self, '_street_base_pot', self._last_known_pot)
            + self._observed_street_contrib_total()
        )

    def _normalize_action_amounts(
        self,
        event: ActionEvent,
        player: Optional[Player],
        street_max_before: float,
    ) -> tuple[float, float]:
        """Return (amount_added, total_bet_after) for a public action event."""
        action = event.action.lower()
        raw = max(0.0, float(event.amount or 0.0))
        prev_bet = getattr(player, 'current_bet', 0.0) if player else 0.0

        if action == "raise":
            total_bet_after = max(raw, prev_bet)
            amount_added = max(0.0, total_bet_after - prev_bet)
            return amount_added, total_bet_after

        if action == "call":
            amount_added = raw if raw > 0 else max(0.0, street_max_before - prev_bet)
            total_bet_after = prev_bet + amount_added
            if street_max_before > 0 and amount_added >= street_max_before - prev_bet:
                total_bet_after = max(total_bet_after, street_max_before)
            elif (
                street_max_before > 0
                and raw > 0
                and player is not None
                and float(player.stack) > raw
            ):
                # Live bridge sends call as added chips. Forced blinds are not
                # model actions, so a blind player's prev_bet can be unknown
                # here; if they are not all-in, a call closes to table max.
                total_bet_after = max(total_bet_after, street_max_before)
            return amount_added, total_bet_after

        return 0.0, prev_bet

    def _apply_player_action(
        self,
        player: Optional[Player],
        action: str,
        amount_added: float,
        total_bet_after: float,
    ) -> None:
        if player is None:
            return
        action = action.lower()
        if action == "fold":
            player.is_folded = True
            return
        if action in ("raise", "call"):
            player.current_bet = max(player.current_bet, total_bet_after)
        elif action == "check":
            return

        if amount_added > 0:
            pay = min(float(amount_added), float(player.stack))
            player.stack = max(0.0, float(player.stack) - pay)
            player.total_invested += pay
            if player.stack <= 0:
                player.is_all_in = True

    def _to_decision(self, action: Action) -> BotDecision:
        name = action.action_type.name.lower()
        return BotDecision(action=name, amount=action.amount)

    def _get_my_player(self) -> Optional[Player]:
        return self._get_player(self.my_player_id)

    def _get_player(self, player_id: int) -> Optional[Player]:
        for p in self._players:
            if p.player_id == player_id:
                return p
        return None
