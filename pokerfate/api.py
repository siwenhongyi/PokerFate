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
import shlex
import sys
import time
import traceback
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from pokerfate.bot.poker_bot import PokerBot
from pokerfate.calibration import (
    FileSpoolShowdownCalibrator,
    FileSpoolRangeCompareCollector,
    RuntimeCalibrationRecorder,
)
from pokerfate.core.card import Card
from pokerfate.core.config import MIN_HANDS_FOR_CLASSIFICATION
from pokerfate.core.game_state import Action, ActionType, GameState, Player, Street
from pokerfate.core.hand_evaluator import HandEvaluator, HandRank
from pokerfate.data import init as _init_data
from pokerfate.decision import (
    FlopBookDecisionContext,
    FlopBookDecisionEngine,
    FlopBookOptions,
    G5EngineOptions,
    G5JsonDecisionEngine,
    RealtimeCFRDecisionContext,
    RealtimeCFRDecisionEngine,
    RealtimeCFROptions,
)
from pokerfate.decision.g5_model import G5ActionModel, stable_player_name
from pokerfate.logger import PokerLogger
from pokerfate.strategy.range_estimator import (
    _ACTION_COMPRESSION_RAISE_PREFLOP,
    _ACTION_COMPRESSION_RAISE_POSTFLOP,
    HandRangeEstimator,
    ShowdownCalibrator as LegacyShowdownCalibrator,
)
from pokerfate.strategy.range_v2.action_model import ActionContext
from pokerfate.strategy.range_v2.empirical_model import (
    bb_key,
    empirical_action_likelihood,
    set_current_big_blind,
)
from pokerfate.strategy.range_v2 import hand_combo_map as hcm
from pokerfate.strategy.range_v2.cec_calibration import calibrate_range_v2_prior
from pokerfate.strategy.range_v2.hand_categorizer import categorize_cards
from pokerfate.strategy.range_v2.hero_eq_calibrator import (
    HeroEquityCalibrator,
    classify_action_ctx_from_trigger,
)
from pokerfate.strategy.range_v2.river_relative_calibrator import RiverRelativeCalibrator
from pokerfate.strategy.range_v2.showdown_learner import ShowdownLearner, _board_at_street
from pokerfate.strategy.v3 import hero_range as hero_reach_range

_UNSET = object()  # sentinel for log_file default

# 启动时预加载静态数据（GTO charts 等）
_init_data()

_DEFAULT_LOG_FILE    = str(Path(__file__).resolve().parent / "logs" / "pokerfate.log")
_DEFAULT_ROBOT_LOG_FILE = str(Path(__file__).resolve().parent / "logs" / "bot.log")
_DEFAULT_MODEL_DIR = Path(__file__).resolve().parent / "data" / "local_models"
_DEFAULT_G5_LOG_FILE = str(Path(__file__).resolve().parent / "logs" / "g5.log")
_POSTFLOP_STREET_RANK = {"flop": 1, "turn": 2, "river": 3}


def _default_opponents_path(big_blind: float | None = None) -> Path:
    return _DEFAULT_MODEL_DIR / "opponents_all_bb.json"


def _default_g5_model_path(big_blind: float) -> Path:
    return _DEFAULT_MODEL_DIR / f"g5_stats_{bb_key(big_blind)}.json"

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
_RIVER_VALUE_SIZING_PURPOSES = {
    "thin_value_bet",
    "thick_value_bet",
    "monster_value_plan",
    "overbet_value",
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
    seat_index: Optional[int] = None  # physical table seat, when known


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
        robot_log_file: Optional[str] = _UNSET,
        verbose: bool = False,
        use_range_equity: bool = True,
        enable_showdown_calibration: bool = True,
        decision_seed: Optional[int] = None,
        decision_engine: Optional[str] = None,
        g5_worker_cmd: Optional[str] = None,
        g5_timeout_sec: Optional[float] = None,
        g5_recent_hands_count: int = 100,
        g5_randomly_sample_actions: bool = False,
        g5_preflop_charts_level: int = 4,
        g5_shadow_decisions: Optional[bool] = None,
        g5_model_path: Optional[str] = _UNSET,
        realtime_cfr_timeout_sec: Optional[float] = None,
        realtime_cfr_solver_lib: Optional[str] = None,
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
        set_current_big_blind(big_blind)
        self.verbose = verbose
        self._decision_seed_base = decision_seed
        self._decision_index = 0
        _in_test = bool(os.environ.get("PYTEST_CURRENT_TEST"))
        self._autosave_uses_default = autosave_path is _UNSET and not _in_test
        if autosave_path is _UNSET:
            autosave_path = None if _in_test else str(_default_opponents_path(big_blind))
        self.autosave_path = autosave_path
        if log_file is _UNSET:
            log_file = None if _in_test else _DEFAULT_LOG_FILE
        if robot_log_file is _UNSET:
            robot_log_file = None if _in_test else _DEFAULT_ROBOT_LOG_FILE
        self._g5_log_file = None if _in_test else _DEFAULT_G5_LOG_FILE
        self._g5_model_path = (
            None if _in_test else str(_default_g5_model_path(big_blind))
        ) if g5_model_path is _UNSET else g5_model_path
        self._g5_action_model = (
            G5ActionModel.load(self._g5_model_path)
            if self._g5_model_path else None
        )
        self._log = PokerLogger(
            log_file=log_file,
            console=True,
            robot_log_file=robot_log_file,
        )
        self._default_stack = 100.0 * big_blind  # fallback when stack is unknown

        self._bot = PokerBot(
            name="PokerFate",
            equity_iterations=equity_iterations,
            use_range_equity=use_range_equity,
        )
        self._bot._range_tracker.set_big_blind(self.big_blind)
        self._external_decision_engine = None
        self._external_decision_engine_enabled = False
        self._external_decision_engine_active = False
        self._external_decision_engine_shadow = False
        self._external_decision_engine_mode = "local"
        self._external_decision_engine_name = "local"
        self._external_decision_engine_error = ""
        self._flop_book_engine: Optional[FlopBookDecisionEngine] = None
        self._flop_book_enabled = False
        self._flop_book_error = ""
        self._realtime_cfr_engine: Optional[RealtimeCFRDecisionEngine] = None
        self._realtime_cfr_enabled = False
        self._realtime_cfr_error = ""
        self._realtime_cfr_timeout_sec = (
            float(realtime_cfr_timeout_sec)
            if realtime_cfr_timeout_sec is not None
            else float(os.environ.get("REALTIME_CFR_TIMEOUT_SEC", "10.0"))
        )
        self._realtime_cfr_solver_lib = realtime_cfr_solver_lib
        self._external_decision_engine_requested = str(
            decision_engine if decision_engine is not None else os.environ.get("DECISION_ENGINE", "local")
        ).strip().lower()
        self._external_decision_hand_disabled_reason = ""
        self._external_decision_shadow_hero_folded = False
        self._external_decision_shadow_warning = ""
        self._g5_worker_cmd = g5_worker_cmd
        self._g5_timeout_sec = g5_timeout_sec
        self._g5_recent_hands_count = int(g5_recent_hands_count)
        self._g5_randomly_sample_actions = bool(g5_randomly_sample_actions)
        self._g5_preflop_charts_level = int(g5_preflop_charts_level)
        self._g5_shadow_decisions = (
            (not _in_test) if g5_shadow_decisions is None else bool(g5_shadow_decisions)
        )
        self._configure_decision_engine(
            decision_engine=decision_engine,
            g5_worker_cmd=self._g5_worker_cmd,
            g5_timeout_sec=self._g5_timeout_sec,
            g5_recent_hands_count=self._g5_recent_hands_count,
            g5_randomly_sample_actions=self._g5_randomly_sample_actions,
            g5_preflop_charts_level=self._g5_preflop_charts_level,
            g5_shadow_decisions=self._g5_shadow_decisions,
        )

        # Auto-load opponent data (+ embedded showdown/learner data) from disk on startup
        if autosave_path:
            self._load_persisted_model(str(autosave_path))
            self._bootstrap_g5_action_model_from_opponents()

        # Session-level state: persists across hands
        self._session_stacks: Dict[int, float] = {}   # player_id -> last known stack
        self._session_names: Dict[int, str] = {}      # player_id -> name
        self._session_delta: float = 0.0              # cumulative P&L this session

        # Hand state: rebuilt each hand
        self._players: List[Player] = []
        self._hand_seat_indices: Dict[int, int] = {}
        self._dealer_seat_index: Optional[int] = None
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
        self._pending_river_value_sizing_rows: list[dict[str, Any]] = []
        self._g5_hand_start_players: list[dict[str, Any]] = []
        self._runtime_calibration_recorder = None
        self._range_compare_collector = None
        self._runtime_collection_enabled = False
        self._runtime_collection_skip_reason = ""
        self._last_decision_diagnostics: dict[str, Any] = {}
        self._pattern_logged_hands: Dict[int, int] = {}

        # ── 2026-04-23: Showdown calibration ──
        # 每次 tracker range 调整时记录预测，手牌结束时对比摊牌实际，写入
        # pokerfate.log JSON 流供 offline 校准分析。仅 range_v2 路径启用。
        if self._bot.use_range_equity and enable_showdown_calibration:
            self._calibrator = FileSpoolShowdownCalibrator(
                logger=self._log,
                big_blind=self.big_blind,
            )
            self._log.raw({
                "event": "showdown_calibration_spool_enabled",
                "mode": "process_file_spool",
            })
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
            self._runtime_calibration_recorder = RuntimeCalibrationRecorder()
            self._range_compare_collector = FileSpoolRangeCompareCollector(
                logger=self._log,
                big_blind=self.big_blind,
            )
            self._runtime_collection_enabled = True
        else:
            self._calibrator = None

    def _apply_spooled_calibration_updates(self) -> None:
        """Consume worker-produced calibration updates without blocking WSS."""
        calibrator = self._calibrator
        apply_updates = getattr(calibrator, "apply_pending_updates", None)
        if not callable(apply_updates):
            return
        try:
            count = apply_updates(
                self._bot._hero_eq_calibrator,
                self._bot._river_relative_calibrator,
            )
            if count:
                self._log.raw({
                    "event": "showdown_calibration_spool_updates_applied",
                    "count": int(count),
                })
        except Exception:
            traceback.print_exc()

    def _showdown_persistence_data(self) -> dict:
        if self._bot.use_range_equity:
            return {
                'range_v2_learner': self._bot._showdown_learner.to_dict(),
                'hero_eq_calibrator': self._bot._hero_eq_calibrator.to_dict(),
                'river_relative_calibrator': (
                    self._bot._river_relative_calibrator.to_dict()
                ),
            }
        return self._bot.range_estimator.showdown_calibrator.to_dict()

    def _save_persisted_model(self) -> None:
        if not self.autosave_path:
            return
        self._bot.opponent_model.save(
            self.autosave_path,
            showdown_data=self._showdown_persistence_data(),
        )

    def _save_g5_action_model(self) -> None:
        if self._g5_action_model is None or not self._g5_model_path:
            return
        self._g5_action_model.save(self._g5_model_path)

    def _bootstrap_g5_action_model_from_opponents(self) -> None:
        if self._g5_action_model is None:
            return
        changed = self._g5_action_model.seed_from_opponent_model(self._bot.opponent_model)
        if changed:
            self._save_g5_action_model()
            self._log.raw({
                "event": "g5_model_bootstrap",
                "path": self._g5_model_path,
                "vpip_seeded": changed,
            })

    def _load_persisted_model(self, filepath: str) -> None:
        self._bot.opponent_model = self._bot.opponent_model.__class__.load(filepath)
        if self._bot.opponent_model._stats:
            self._log.raw({"event": "model_loaded", "path": filepath,
                           "known_opponents": len(self._bot.opponent_model._stats)})
        showdown_raw = self._bot.opponent_model._showdown_data
        if not showdown_raw:
            return
        if self._bot.use_range_equity:
            v2_data = showdown_raw.get('range_v2_learner')
            if v2_data:
                self._bot._showdown_learner = ShowdownLearner.from_dict(v2_data)
                self._bot._action_model.showdown_learner = self._bot._showdown_learner
            heq_data = showdown_raw.get('hero_eq_calibrator')
            if heq_data:
                self._bot._hero_eq_calibrator = HeroEquityCalibrator.from_dict(heq_data)
            river_rel_data = showdown_raw.get('river_relative_calibrator')
            if river_rel_data:
                self._bot._river_relative_calibrator = (
                    RiverRelativeCalibrator.from_dict(river_rel_data)
                )
        else:
            self._bot.range_estimator.showdown_calibrator = (
                LegacyShowdownCalibrator.from_dict(showdown_raw)
            )

    def set_table_blinds(self, big_blind: float, small_blind: float) -> None:
        """Update blinds after EnterRoomRSP (new table); refreshes unknown-stack fallback."""
        new_big_blind = float(big_blind)
        if (
            self._autosave_uses_default
            and self.autosave_path
            and bb_key(new_big_blind) != bb_key(self.big_blind)
        ):
            self._save_persisted_model()
            if self._g5_model_path:
                self._save_g5_action_model()
                self._g5_model_path = str(_default_g5_model_path(new_big_blind))
                self._g5_action_model = G5ActionModel.load(self._g5_model_path)
                if self._external_decision_engine is not None:
                    self._external_decision_engine.options.model_file = self._g5_model_path
                self._bootstrap_g5_action_model_from_opponents()
        self.big_blind = float(big_blind)
        self.small_blind = float(small_blind)
        set_current_big_blind(self.big_blind)
        self._default_stack = 100.0 * self.big_blind
        self._bot._range_tracker.set_big_blind(self.big_blind)
        if self._range_compare_collector is not None:
            self._range_compare_collector.set_big_blind(self.big_blind)

    def set_runtime_collection_enabled(self, enabled: bool, reason: str = "") -> None:
        """Enable/disable realtime training-row collection for this room.

        SNG/tournament/friend rooms are useful for live play but should not
        contaminate cash-game runtime calibration datasets.
        """
        self._runtime_collection_enabled = bool(enabled)
        self._runtime_collection_skip_reason = "" if enabled else str(reason or "disabled")
        if not enabled:
            self._runtime_calibration_recorder = None
            self._pending_river_value_sizing_rows = []
            if self._range_compare_collector is not None:
                self._range_compare_collector.discard_hand()
            return
        if (
            self._runtime_calibration_recorder is None
            and self._calibrator is not None
            and self._bot.use_range_equity
        ):
            self._runtime_calibration_recorder = RuntimeCalibrationRecorder()
        if (
            self._range_compare_collector is None
            and self._calibrator is not None
            and self._bot.use_range_equity
        ):
            self._range_compare_collector = FileSpoolRangeCompareCollector(
                logger=self._log,
                big_blind=self.big_blind,
            )

    def _configure_decision_engine(
        self,
        *,
        decision_engine: Optional[str],
        g5_worker_cmd: Optional[str],
        g5_timeout_sec: Optional[float],
        g5_recent_hands_count: int,
        g5_randomly_sample_actions: bool,
        g5_preflop_charts_level: int,
        g5_shadow_decisions: bool,
    ) -> None:
        requested_engine = (
            decision_engine
            if decision_engine is not None
            else os.environ.get("DECISION_ENGINE", "local")
        )
        engine_name = str(requested_engine or "local").strip().lower().replace("-", "_")
        self._flop_book_error = ""
        self._realtime_cfr_error = ""
        if engine_name in {"", "pokerfate"}:
            engine_name = "local"
        self._external_decision_engine_requested = engine_name or "local"
        valid_engines = {"local", "g5", "g5_all", "realtime_cfr", "cfr"}
        invalid_engine = engine_name not in valid_engines
        if invalid_engine:
            self._external_decision_engine_error = (
                f"unknown decision engine: {engine_name}; using local"
            )
            self._log.raw({
                "event": "decision_engine_disabled",
                "engine": str(requested_engine or ""),
                "reason": self._external_decision_engine_error,
            })
            return

        if engine_name == "local":
            return

        if engine_name in {"realtime_cfr", "cfr"}:
            try:
                realtime_engine = RealtimeCFRDecisionEngine(
                    RealtimeCFROptions(
                        timeout_sec=self._realtime_cfr_timeout_sec,
                        solver_lib_path=self._realtime_cfr_solver_lib,
                    )
                )
                flop_book_engine = (
                    FlopBookDecisionEngine(FlopBookOptions())
                    if engine_name == "cfr"
                    else None
                )
            except Exception as exc:
                self._flop_book_engine = None
                self._flop_book_enabled = False
                self._realtime_cfr_engine = None
                self._realtime_cfr_enabled = False
                self._external_decision_engine_name = "local"
                self._external_decision_engine_mode = "local"
                self._external_decision_engine_error = str(exc)
                self._log.raw({
                    "event": "decision_engine_disabled",
                    "engine": engine_name,
                    "reason": str(exc),
                })
                return

            self._realtime_cfr_engine = realtime_engine
            self._realtime_cfr_enabled = True
            if engine_name == "cfr":
                self._flop_book_engine = flop_book_engine
                self._flop_book_enabled = True
            self._external_decision_engine_enabled = False
            self._external_decision_engine_active = False
            self._external_decision_engine_shadow = False
            self._external_decision_engine_mode = (
                "flop_book_turn_river" if engine_name == "cfr" else "turn_river"
            )
            self._external_decision_engine_name = engine_name
            self._external_decision_engine_error = ""
            self._log.raw({
                "event": "decision_engine_enabled",
                "engine": engine_name,
                "mode": self._external_decision_engine_mode,
                "requested_engine": str(requested_engine or ""),
                "timeout_sec": self._realtime_cfr_timeout_sec,
                "solver_lib": self._realtime_cfr_solver_lib,
                "flop_book": bool(engine_name == "cfr"),
            })
            return

        active = engine_name in {"g5", "g5_all"}
        active_mode = "g5_all" if engine_name == "g5_all" else "postflop"
        shadow = bool(g5_shadow_decisions) and engine_name == "g5"

        cmd = str(g5_worker_cmd or "").strip() or self._default_g5_worker_cmd()

        timeout = float(g5_timeout_sec) if g5_timeout_sec is not None else 8.0
        recent_hands = int(g5_recent_hands_count)
        charts_level = int(g5_preflop_charts_level)
        sample_actions = bool(g5_randomly_sample_actions)
        try:
            engine = G5JsonDecisionEngine(
                G5EngineOptions(
                    worker_cmd=str(cmd),
                    timeout_sec=timeout,
                    recent_hands_count=recent_hands,
                    randomly_sample_actions=sample_actions,
                    preflop_charts_level=charts_level,
                    log_file=self._g5_log_file,
                    model_file=self._g5_model_path,
                )
            )
            preflight = engine.preflight()
            self._external_decision_engine = engine
            self._external_decision_engine_enabled = True
            self._external_decision_engine_active = active
            self._external_decision_engine_shadow = shadow
            self._external_decision_engine_mode = active_mode
            self._external_decision_engine_name = "g5"
            self._log.raw({
                "event": "decision_engine_enabled",
                "engine": "g5",
                "mode": active_mode if active else "shadow",
                "requested_engine": str(requested_engine or ""),
                "invalid_engine_fallback": invalid_engine,
                "worker_cmd": cmd,
                "timeout_sec": timeout,
                "recent_hands_count": recent_hands,
                "preflop_charts_level": charts_level,
                "log_file": self._g5_log_file,
                "model_file": self._g5_model_path,
                "preflight": preflight,
            })
        except Exception as exc:
            try:
                engine.close()  # type: ignore[name-defined]
            except Exception:
                pass
            self._external_decision_engine = None
            self._external_decision_engine_enabled = False
            self._external_decision_engine_active = False
            self._external_decision_engine_shadow = False
            self._external_decision_engine_mode = "local"
            self._external_decision_engine_error = str(exc)
            self._log.raw({
                "event": "decision_engine_disabled",
                "engine": "g5",
                "mode": "active" if active else "shadow",
                "reason": str(exc),
            })

    @staticmethod
    def _default_g5_worker_cmd() -> str:
        root = Path(__file__).resolve().parent.parent
        script = root / "scripts" / "g5_json_worker.py"
        return f"{shlex.quote(sys.executable)} {shlex.quote(str(script))}"

    def set_decision_engine(self, decision_engine: str) -> dict[str, Any]:
        """Reconfigure DECISION_ENGINE at runtime."""
        value = str(decision_engine or "local").strip().lower().replace("-", "_")
        if value in {"", "pokerfate"}:
            value = "local"
        if value not in {"local", "g5", "g5_all", "realtime_cfr", "cfr"}:
            raise ValueError("decision_engine must be local, g5, g5_all, realtime_cfr, or cfr")

        old = self._external_decision_engine
        if old is not None:
            try:
                old.close()
            except Exception:
                pass
        if self._flop_book_engine is not None:
            try:
                self._flop_book_engine.close()
            except Exception:
                pass
        self._external_decision_engine = None
        self._external_decision_engine_enabled = False
        self._external_decision_engine_active = False
        self._external_decision_engine_shadow = False
        self._external_decision_engine_mode = "local"
        self._external_decision_engine_name = "local"
        self._external_decision_engine_error = ""
        self._flop_book_engine = None
        self._flop_book_enabled = False
        self._flop_book_error = ""
        self._realtime_cfr_engine = None
        self._realtime_cfr_enabled = False
        self._realtime_cfr_error = ""
        self._external_decision_hand_disabled_reason = ""
        self._external_decision_shadow_hero_folded = False
        self._external_decision_shadow_warning = ""
        self._external_decision_engine_requested = value
        self._configure_decision_engine(
            decision_engine=value,
            g5_worker_cmd=self._g5_worker_cmd,
            g5_timeout_sec=self._g5_timeout_sec,
            g5_recent_hands_count=self._g5_recent_hands_count,
            g5_randomly_sample_actions=self._g5_randomly_sample_actions,
            g5_preflop_charts_level=self._g5_preflop_charts_level,
            g5_shadow_decisions=self._g5_shadow_decisions,
        )
        if self._players and value in {"g5", "g5_all"}:
            self._disable_external_engine_current_hand("decision_engine_changed_mid_hand")
        self._log.raw({
            "event": "decision_engine_runtime_set",
            "requested_engine": value,
            "status": self.decision_engine_status(),
        })
        return self.decision_engine_status()

    def decision_engine_status(self) -> dict[str, Any]:
        return {
            "requested": self._external_decision_engine_requested or "local",
            "engine": self._external_decision_engine_name,
            "mode": self._external_decision_engine_mode,
            "enabled": bool(
                self._external_decision_engine_enabled
                or self._realtime_cfr_enabled
                or self._flop_book_enabled
            ),
            "active": bool(
                self._external_decision_engine_active
                or self._realtime_cfr_enabled
                or self._flop_book_enabled
            ),
            "shadow": bool(self._external_decision_engine_shadow),
            "realtime_cfr": bool(self._realtime_cfr_enabled),
            "flop_book": bool(self._flop_book_enabled),
            "error": (
                self._flop_book_error
                if self._flop_book_enabled and self._flop_book_error
                else
                self._realtime_cfr_error
                if self._realtime_cfr_enabled
                else self._external_decision_engine_error
            ),
            "hand_disabled_reason": self._external_decision_hand_disabled_reason,
        }

    def _external_engine_ready(self) -> bool:
        return bool(
            self._external_decision_engine_enabled
            and self._external_decision_engine is not None
        )

    def _external_engine_active_for_street(self, street: str) -> bool:
        if (
            not self._external_engine_ready()
            or not self._external_decision_engine_active
            or self._external_decision_hand_disabled_reason
        ):
            return False
        mode = str(self._external_decision_engine_mode or "").lower()
        if mode in {"", "local", "g5_all"}:
            return True
        return mode == "postflop" and str(street or "").lower() != "preflop"

    def _record_external_engine_error(self, phase: str, exc: Exception) -> None:
        self._external_decision_engine_error = str(exc)
        self._log.raw({
            "event": "decision_engine_fallback",
            "engine": self._external_decision_engine_name,
            "phase": phase,
            "reason": str(exc),
        })

    def _disable_external_engine_current_hand(self, reason: str) -> None:
        self._external_decision_hand_disabled_reason = str(reason or "disabled")
        if self._external_decision_engine is None:
            return
        disable = getattr(
            self._external_decision_engine,
            "disable_current_hand",
            None,
        )
        if callable(disable):
            try:
                disable(reason)
            except Exception:
                pass

    def disable_external_decision_current_hand(self, reason: str) -> None:
        """Disable the external engine for this hand and keep local fallback active."""
        if not self._external_engine_ready():
            return
        reason_text = str(reason)
        if reason_text.startswith("unsupported forced post"):
            return
        if self._external_decision_hand_disabled_reason:
            return
        self._log.raw({
            "event": "decision_engine_hand_disabled",
            "engine": self._external_decision_engine_name,
            "reason": reason_text,
        })
        self._disable_external_engine_current_hand(reason_text)

    def _external_engine_start_hand(self) -> None:
        if not self._external_engine_ready():
            return
        try:
            self._external_decision_engine.start_hand(
                players=self._players,
                dealer_id=self._dealer_id,
                seat_indices=self._hand_seat_indices,
                dealer_seat_index=self._dealer_seat_index,
                hand_number=self._hand_number,
                hero_player_id=self.my_player_id,
                big_blind=self.big_blind,
                small_blind=self.small_blind,
            )
        except Exception as exc:
            self._record_external_engine_error("start_hand", exc)
            self._disable_external_engine_current_hand(str(exc))

    def _external_engine_deal_hole_cards(self) -> None:
        if (
            not self._external_engine_ready()
            or self._external_decision_hand_disabled_reason
        ):
            return
        try:
            self._external_decision_engine.deal_hole_cards(
                [str(c) for c in self._hole_cards],
            )
        except Exception as exc:
            self._record_external_engine_error("hole_cards", exc)
            self._disable_external_engine_current_hand(str(exc))

    def _external_engine_deal_board(self, cards: Sequence[str], street: str) -> None:
        if (
            not self._external_engine_ready()
            or self._external_decision_hand_disabled_reason
        ):
            return
        try:
            self._external_decision_engine.deal_board(cards, street)
        except Exception as exc:
            self._record_external_engine_error("board", exc)
            self._disable_external_engine_current_hand(str(exc))

    def _external_engine_notify_action(
        self,
        *,
        player_id: int,
        action: str,
        amount_added: float,
        total_bet_after: float,
        street: str,
    ) -> None:
        if (
            not self._external_engine_ready()
            or self._external_decision_hand_disabled_reason
        ):
            return
        try:
            self._external_decision_engine.notify_action(
                player_id=player_id,
                action=action,
                amount_added=amount_added,
                total_bet_after=total_bet_after,
                street=street,
            )
        except Exception as exc:
            self._record_external_engine_error("action", exc)
            self._disable_external_engine_current_hand(str(exc))

    def _external_engine_finish_hand(
        self,
        *,
        winner_ids: List[int],
        pot: float,
        winner_payouts: Optional[Dict[int, float]],
        final_stacks: Optional[Dict[int, float]],
    ) -> None:
        if (
            not self._external_engine_ready()
            or self._external_decision_hand_disabled_reason
        ):
            return
        try:
            self._external_decision_engine.finish_hand(
                winner_ids=winner_ids,
                pot=pot,
                winner_payouts=winner_payouts,
                final_stacks=final_stacks,
            )
        except Exception as exc:
            self._record_external_engine_error("finish_hand", exc)
            self._disable_external_engine_current_hand(str(exc))

    def _record_g5_action_model_hand(self) -> None:
        if self._g5_action_model is None or not self._g5_model_path:
            return
        try:
            changed = self._g5_action_model.record_hand(
                players=self._g5_hand_start_players,
                dealer_id=self._dealer_id,
                action_history=self._action_history,
                big_blind=self.big_blind,
                small_blind=self.small_blind,
            )
            if changed:
                self._save_g5_action_model()
                self._log.raw({
                    "event": "g5_model_saved",
                    "path": self._g5_model_path,
                    "players": len(self._g5_hand_start_players),
                })
        except Exception as exc:
            self._log.raw({
                "event": "g5_model_save_failed",
                "path": self._g5_model_path,
                "reason": str(exc),
            })

    def _decide_with_realtime_cfr(
        self,
        gs: GameState,
        *,
        street: str,
    ) -> Optional[Action]:
        if (
            not self._realtime_cfr_enabled
            or self._realtime_cfr_engine is None
            or str(street or "").lower() not in {"turn", "river"}
        ):
            return None
        if not self._bot.use_range_equity:
            self._realtime_cfr_error = "range_v2_disabled"
            self._log.raw({
                "event": "decision_engine_fallback",
                "engine": "realtime_cfr",
                "phase": "prepare",
                "reason": "range_v2_disabled",
            })
            return None
        try:
            action = self._realtime_cfr_engine.decide(
                RealtimeCFRDecisionContext(
                    gs=gs,
                    hero_player_id=self.my_player_id,
                    street_start_pot=self._street_base_pot,
                    range_provider=self._bot._range_tracker.get_distribution,
                    hero_range_provider=lambda _player_id: self._realtime_cfr_hero_range_weights(
                        gs,
                        street,
                    ),
                    villain_profile_provider=self._bot._build_player_profile,
                    exploit_adjustments_provider=self._bot.opponent_model.exploit_adjustments,
                    range_v2_prior_provider=lambda villain_id: self._realtime_cfr_range_v2_prior(
                        gs,
                        street,
                        villain_id,
                    ),
                )
            )
        except Exception as exc:
            self._realtime_cfr_error = str(exc)
            self._log.raw({
                "event": "decision_engine_fallback",
                "engine": "realtime_cfr",
                "phase": "decide",
                "reason": str(exc),
            })
            return None

        result = self._realtime_cfr_engine.last_result
        if action is None:
            reason = str(result.get("reason") or self._realtime_cfr_engine.last_error or "fallback")
            self._realtime_cfr_error = reason
            self._log.raw({
                "event": "decision_engine_fallback",
                "engine": "realtime_cfr",
                "phase": "decide",
                "reason": reason,
                "result": result,
            })
            return None
        self._realtime_cfr_error = ""
        return action

    def _realtime_cfr_range_v2_prior(
        self,
        gs: GameState,
        street: str,
        villain_id: int,
    ) -> dict[str, Any]:
        """Compact Range V2 posterior/context for realtime CFR exploit only."""
        if not self._bot.use_range_equity:
            return {}
        t0 = time.perf_counter()
        timing: dict[str, float] = {}
        out: dict[str, Any] = {}
        board = list(gs.board or [])
        try:
            bucket_t0 = time.perf_counter()
            if board:
                bucket_dist = self._bot._range_tracker.get_bucket_distribution(
                    int(villain_id),
                    board,
                )
                if bucket_dist:
                    out["bucket_dist"] = {
                        str(k): float(v)
                        for k, v in bucket_dist.items()
                        if float(v or 0.0) > 1e-9
                    }
                if len(board) >= 5 and self._hole_cards:
                    vs_t0 = time.perf_counter()
                    vs_hero = self._bot._range_tracker.get_vs_hero_dist(
                        int(villain_id),
                        board,
                        list(self._hole_cards),
                    )
                    if vs_hero:
                        out["vs_hero"] = {str(k): float(v) for k, v in vs_hero.items()}
                    timing["vs_hero_ms"] = (time.perf_counter() - vs_t0) * 1000.0
            timing["bucket_dist_ms"] = (time.perf_counter() - bucket_t0) * 1000.0
        except Exception:
            pass

        action_ctx_t0 = time.perf_counter()
        action_name, action_ctx, public_ctx = self._realtime_cfr_action_context(
            gs,
            street,
            int(villain_id),
        )
        timing["action_context_ms"] = (time.perf_counter() - action_ctx_t0) * 1000.0
        if public_ctx:
            out["action_context"] = public_ctx
        if action_name and action_ctx is not None:
            try:
                likelihood_t0 = time.perf_counter()
                profile = self._bot._build_player_profile(int(villain_id))
                likelihood = empirical_action_likelihood(
                    action_name,
                    str(street or "").lower(),
                    action_ctx,
                    profile,
                )
                if likelihood is not None:
                    dist, blend, key, n = likelihood
                    out["action_likelihood"] = {
                        "action": action_name,
                        "dist": {str(k): float(v) for k, v in dict(dist).items()},
                        "blend": float(blend),
                        "key": str(key),
                        "n": int(n),
                    }
                timing["action_likelihood_ms"] = (time.perf_counter() - likelihood_t0) * 1000.0
            except Exception:
                pass
        if out:
            try:
                cec_t0 = time.perf_counter()
                out = calibrate_range_v2_prior(out, big_blind=self.big_blind)
                timing["cec_calibration_ms"] = (time.perf_counter() - cec_t0) * 1000.0
            except Exception:
                pass
        if out:
            timing["total_ms"] = (time.perf_counter() - t0) * 1000.0
            out["_timing"] = {
                key: round(value, 1)
                for key, value in timing.items()
                if isinstance(value, (int, float))
            }
        return out

    def _realtime_cfr_action_context(
        self,
        gs: GameState,
        street: str,
        villain_id: int,
    ) -> tuple[str, Optional[ActionContext], dict[str, Any]]:
        street_key = str(street or "").lower()
        base_pot = max(0.0, float(self._street_base_pot or 0.0))
        contrib: dict[int, float] = {}
        prior_raises = 0
        last: Optional[tuple[str, float, bool, float]] = None
        for item in list(gs.action_history or []):
            if len(item) < 3 or str(item[2]).lower() != street_key:
                continue
            try:
                pid = int(item[0])
            except (TypeError, ValueError):
                continue
            action = item[1]
            action_type = getattr(action, "action_type", None)
            amount = max(0.0, float(getattr(action, "amount", 0.0) or 0.0))
            pot_before = max(1.0, base_pot + sum(contrib.values()))
            name = ""
            bet_ratio = 0.0
            is_raise_over = False
            if action_type == ActionType.RAISE:
                name = "raise"
                is_raise_over = prior_raises > 0
                bet_ratio = amount / pot_before
                contrib[pid] = max(contrib.get(pid, 0.0), amount)
                prior_raises += 1
            elif action_type == ActionType.CALL:
                name = "call"
                bet_ratio = amount / pot_before if amount > 0.0 else 0.0
                contrib[pid] = contrib.get(pid, 0.0) + amount
            elif action_type == ActionType.CHECK:
                name = "check"
            elif action_type == ActionType.FOLD:
                name = "fold"
            if pid == int(villain_id) and name:
                last = (name, bet_ratio, is_raise_over, pot_before)
        if last is None:
            return "", None, {}

        action_name, bet_ratio, is_raise_over, pot_before = last
        villain = next((p for p in gs.players if p.player_id == int(villain_id)), None)
        position = (
            gs.position_of(villain)
            if villain is not None
            else self._hand_positions.get(int(villain_id), "CO")
        )
        is_ip = bool(gs.is_ip(villain)) if villain is not None else self._is_player_ip(int(villain_id))
        facing_action = "none"
        if action_name == "raise":
            facing_action = "bet" if is_raise_over else "check"
        elif action_name == "call":
            facing_action = "bet"
        ctx = ActionContext(
            position=position or "CO",
            board=list(gs.board or []),
            street=street_key,
            facing_action=facing_action,
            bet_ratio=float(bet_ratio),
            is_raise_over=bool(is_raise_over),
            is_ip=is_ip,
            big_blind=float(self.big_blind or 0.0),
        )
        public = {
            "action": action_name,
            "street": street_key,
            "position": position or "CO",
            "is_ip": is_ip,
            "is_raise_over": bool(is_raise_over),
            "bet_ratio": float(bet_ratio),
            "pot_before": float(pot_before),
            "facing_action": facing_action,
        }
        return action_name, ctx, public

    def _decide_with_flop_book(
        self,
        gs: GameState,
        *,
        street: str,
    ) -> Optional[Action]:
        if (
            not self._flop_book_enabled
            or self._flop_book_engine is None
            or str(street or "").lower() != "flop"
        ):
            return None
        try:
            action = self._flop_book_engine.decide(
                FlopBookDecisionContext(
                    gs=gs,
                    hero_player_id=self.my_player_id,
                    street_start_pot=self._street_base_pot,
                    villain_profile_provider=self._bot._build_player_profile,
                    exploit_adjustments_provider=self._bot.opponent_model.exploit_adjustments,
                )
            )
        except Exception as exc:
            self._flop_book_error = str(exc)
            self._log.raw({
                "event": "decision_engine_fallback",
                "engine": "cfr",
                "component": "flop_book",
                "phase": "decide",
                "reason": str(exc),
            })
            return None

        result = self._flop_book_engine.last_result
        if action is None:
            reason = str(result.get("reason") or self._flop_book_engine.last_error or "fallback")
            self._flop_book_error = reason
            self._log.raw({
                "event": "decision_engine_fallback",
                "engine": "cfr",
                "component": "flop_book",
                "phase": "decide",
                "reason": reason,
                "result": result,
            })
            return None
        self._flop_book_error = ""
        return action

    def _realtime_cfr_hero_range_weights(
        self,
        gs: GameState,
        street: str,
    ) -> List[float]:
        hero = next((p for p in gs.players if p.player_id == self.my_player_id), None)
        if hero is None or len(hero.hole_cards) < 2:
            return []

        street_key = str(street or gs.street or "").lower()
        current_rank = _POSTFLOP_STREET_RANK.get(street_key, 99)
        my_prev_actions = {
            str(prev_street).lower(): str(action).lower()
            for prev_street, action in (self._bot._my_street_actions or {}).items()
            if _POSTFLOP_STREET_RANK.get(str(prev_street).lower(), 99) < current_rank
        }
        hero_is_pfr = self._bot._my_street_actions.get("preflop") == "raise"
        position = gs.position_of(hero)
        facing = "bb_defend" if str(position).upper() == "BB" and not hero_is_pfr else "none"
        return hero_reach_range.combo_weights(
            position=position,
            facing=facing,
            board=list(gs.board),
            my_prev_actions=my_prev_actions,
            is_pfr=hero_is_pfr,
            force_include_cards=list(hero.hole_cards),
        )

    def _decide_with_external_engine(
        self,
        gs: GameState,
        *,
        street: str,
        my_current_bet_this_street: float,
    ) -> Optional[Action]:
        if (
            not self._external_engine_active_for_street(street)
        ):
            return None
        try:
            return self._external_decision_engine.decide(
                gs,
                hero_player_id=self.my_player_id,
                my_current_bet_this_street=my_current_bet_this_street,
            )
        except Exception as exc:
            self._record_external_engine_error("decide", exc)
            self._disable_external_engine_current_hand(str(exc))
            return None

    def _shadow_decide_with_external_engine(
        self,
        gs: GameState,
        *,
        street: str,
        my_current_bet_this_street: float,
        force_shadow: bool = False,
    ) -> Optional[dict[str, Any]]:
        if self._external_decision_shadow_hero_folded:
            return {"status": "folded"}
        if self._external_decision_hand_disabled_reason == "g5_shadow_folded":
            self._external_decision_shadow_hero_folded = True
            return {"status": "folded"}
        if not force_shadow and self._external_engine_active_for_street(street):
            return None
        if not self._external_decision_engine_shadow:
            return None
        if not self._external_engine_ready():
            if self._external_decision_engine_error:
                return {
                    "status": "unavailable",
                    "reason": self._external_decision_engine_error,
                }
            return None
        if self._external_decision_hand_disabled_reason:
            return {
                "status": "disabled",
                "reason": self._external_decision_hand_disabled_reason,
            }

        t0 = time.perf_counter()
        try:
            action = self._external_decision_engine.decide(
                gs,
                hero_player_id=self.my_player_id,
                my_current_bet_this_street=my_current_bet_this_street,
            )
        except Exception as exc:
            self._record_external_engine_error("shadow_decide", exc)
            self._disable_external_engine_current_hand(str(exc))
            return {"status": "error", "reason": str(exc)}

        elapsed_ms = (time.perf_counter() - t0) * 1000
        decision = self._to_decision(action)
        result = (
            self._external_decision_engine.last_result
            if self._external_decision_engine is not None
            else {}
        )
        warning = self._external_decision_shadow_warning
        reasoning = self._g5_decision_reasoning(result)
        if warning:
            reasoning = f"{reasoning} | {self._g5_shadow_warning_text(warning)}"
        shadow = {
            "status": "ok",
            "decision": decision,
            "result": result,
            "elapsed_ms": elapsed_ms,
            "reasoning": reasoning,
            "warning": warning,
        }
        if decision.action == "fold":
            self._external_decision_shadow_hero_folded = True
            self._disable_external_engine_current_hand("g5_shadow_folded")
        return shadow

    def _g5_shadow_action_payload(
        self,
        shadow: Optional[dict[str, Any]],
        *,
        my_current_bet_this_street: float,
    ) -> Optional[tuple[str, float, float]]:
        if not shadow or str(shadow.get("status") or "") != "ok":
            return None
        result = shadow.get("result") if isinstance(shadow.get("result"), dict) else {}
        decision = shadow.get("decision")

        raw_action = str(result.get("action") or "").strip().lower()
        if raw_action in {"bet", "raise", "allin", "all-in"}:
            action = "raise"
        elif raw_action in {"check", "call", "fold"}:
            action = raw_action
        elif isinstance(decision, BotDecision):
            action = decision.action
        else:
            return None

        if action == "fold":
            return None

        try:
            amount_added = float(result.get("byAmount", result.get("by_amount", 0.0)) or 0.0)
        except (TypeError, ValueError):
            amount_added = 0.0
        if action == "check":
            amount_added = 0.0
        total_bet_after = float(my_current_bet_this_street or 0.0) + max(0.0, amount_added)
        return action, max(0.0, amount_added), total_bet_after

    def _notify_external_engine_shadow_action(
        self,
        shadow: Optional[dict[str, Any]],
        *,
        street: str,
        my_current_bet_this_street: float,
    ) -> None:
        if (
            not self._external_engine_ready()
            or self._external_engine_active_for_street(street)
            or not self._external_decision_engine_shadow
            or self._external_decision_hand_disabled_reason
        ):
            return
        payload = self._g5_shadow_action_payload(
            shadow,
            my_current_bet_this_street=my_current_bet_this_street,
        )
        if payload is None:
            return
        action, amount_added, total_bet_after = payload
        self._external_engine_notify_action(
            player_id=self.my_player_id,
            action=action,
            amount_added=amount_added,
            total_bet_after=total_bet_after,
            street=street,
        )

    def _log_g5_shadow_decision(
        self,
        shadow: dict[str, Any],
        *,
        street: str,
    ) -> None:
        shadow_decision = shadow.get("decision")
        shadow_action = ""
        shadow_amount = 0.0
        if isinstance(shadow_decision, BotDecision):
            shadow_action = shadow_decision.action
            shadow_amount = shadow_decision.amount
        self._log.g5_shadow_decision(
            status=str(shadow.get("status") or ""),
            street=street,
            action=shadow_action,
            amount=shadow_amount,
            reasoning=str(shadow.get("reasoning") or ""),
            elapsed_ms=shadow.get("elapsed_ms"),
            result=(
                shadow.get("result")
                if isinstance(shadow.get("result"), dict)
                else None
            ),
            reason=str(shadow.get("reason") or ""),
        )

    def _bot_decision_state_snapshot(self) -> dict[str, Any]:
        return {
            "decision_index": self._decision_index,
            "pending_decision_seed": self._bot._pending_decision_seed,
            "last_equity": self._bot._last_equity,
            "last_equity_random": self._bot._last_equity_random,
            "last_spr": self._bot._last_spr,
            "last_equity_mode": self._bot._last_equity_mode,
            "last_reasoning": self._bot._last_reasoning,
            "last_gto_refs": self._bot._last_gto_refs,
            "last_decision_diagnostics": dict(self._bot._last_decision_diagnostics or {}),
            "my_street_actions": dict(self._bot._my_street_actions or {}),
        }

    def _restore_bot_decision_state(self, snapshot: dict[str, Any]) -> None:
        self._decision_index = int(snapshot.get("decision_index", self._decision_index))
        self._bot._pending_decision_seed = snapshot.get("pending_decision_seed")
        self._bot._last_equity = snapshot.get("last_equity", self._bot._last_equity)
        self._bot._last_equity_random = snapshot.get(
            "last_equity_random",
            self._bot._last_equity_random,
        )
        self._bot._last_spr = snapshot.get("last_spr", self._bot._last_spr)
        self._bot._last_equity_mode = snapshot.get(
            "last_equity_mode",
            self._bot._last_equity_mode,
        )
        self._bot._last_reasoning = snapshot.get(
            "last_reasoning",
            self._bot._last_reasoning,
        )
        self._bot._last_gto_refs = snapshot.get("last_gto_refs")
        self._bot._last_decision_diagnostics = dict(
            snapshot.get("last_decision_diagnostics") or {}
        )
        self._bot._my_street_actions = dict(snapshot.get("my_street_actions") or {})

    def _local_shadow_decide(
        self,
        gs: GameState,
        *,
        street: str,
        pot: float,
        current_bet: float,
        to_call: float,
        my_stack: float,
        is_bb_option: bool,
    ) -> dict[str, Any]:
        snapshot = self._bot_decision_state_snapshot()
        t0 = time.perf_counter()
        try:
            self._bot.set_next_decision_seed(
                self._next_decision_seed(
                    street=street,
                    pot=pot,
                    current_bet=current_bet,
                    to_call=to_call,
                    my_stack=my_stack,
                )
            )
            action = self._bot.decide(
                gs,
                self.my_player_id,
                is_bb_option=is_bb_option,
            )
            elapsed_ms = (time.perf_counter() - t0) * 1000
            return {
                "status": "ok",
                "decision": self._to_decision(action),
                "elapsed_ms": elapsed_ms,
                "reasoning": self._bot.last_reasoning,
                "diagnostics": {
                    **dict(self._bot.last_decision_diagnostics or {}),
                    "equity": self._bot.last_equity,
                    "equity_random": self._bot.last_equity_random,
                    "equity_mode": self._bot.last_equity_mode,
                    "spr": self._bot.last_spr,
                },
            }
        except Exception as exc:
            return {"status": "error", "reason": str(exc)}
        finally:
            self._restore_bot_decision_state(snapshot)

    def _log_local_shadow_decision(
        self,
        shadow: dict[str, Any],
        *,
        street: str,
    ) -> None:
        shadow_decision = shadow.get("decision")
        shadow_action = ""
        shadow_amount = 0.0
        if isinstance(shadow_decision, BotDecision):
            shadow_action = shadow_decision.action
            shadow_amount = shadow_decision.amount
        self._log.local_shadow_decision(
            status=str(shadow.get("status") or ""),
            street=street,
            action=shadow_action,
            amount=shadow_amount,
            reasoning=str(shadow.get("reasoning") or ""),
            elapsed_ms=shadow.get("elapsed_ms"),
            diagnostics=(
                shadow.get("diagnostics")
                if isinstance(shadow.get("diagnostics"), dict)
                else None
            ),
            reason=str(shadow.get("reason") or ""),
        )

    @staticmethod
    def _local_shadow_diagnostics(shadow: dict[str, Any]) -> dict[str, Any]:
        out: dict[str, Any] = {"status": str(shadow.get("status") or "")}
        decision = shadow.get("decision")
        if isinstance(decision, BotDecision):
            out["action"] = decision.action
            out["amount"] = decision.amount
        if shadow.get("reason"):
            out["reason"] = str(shadow.get("reason") or "")
        if shadow.get("warning"):
            out["warning"] = str(shadow.get("warning") or "")
        if shadow.get("elapsed_ms") is not None:
            out["elapsed_ms"] = shadow.get("elapsed_ms")
        if isinstance(shadow.get("diagnostics"), dict):
            out["diagnostics"] = shadow["diagnostics"]
        return out

    @staticmethod
    def _log_metrics_from_local_shadow(
        shadow: Optional[dict[str, Any]],
        fallback_mode: str,
    ) -> tuple[float, Optional[float], Optional[float], str]:
        diagnostics = (
            shadow.get("diagnostics")
            if isinstance(shadow, dict) and isinstance(shadow.get("diagnostics"), dict)
            else {}
        )

        def _float_or_none(value: Any) -> Optional[float]:
            try:
                if value is None:
                    return None
                return float(value)
            except (TypeError, ValueError):
                return None

        equity = _float_or_none(diagnostics.get("equity"))
        equity_random = _float_or_none(diagnostics.get("equity_random"))
        spr = _float_or_none(diagnostics.get("spr"))
        mode = str(diagnostics.get("equity_mode") or fallback_mode)
        return (
            equity if equity is not None else 0.0,
            equity_random,
            spr,
            mode,
        )

    @staticmethod
    def _rounded_range_map(range_map: dict[str, Any]) -> dict[str, float]:
        out: dict[str, float] = {}
        for key, value in (range_map or {}).items():
            try:
                prob = float(value or 0.0)
            except (TypeError, ValueError):
                continue
            if prob <= 1e-10:
                continue
            out[str(key)] = round(prob, 8)
        total = sum(out.values())
        if total > 0.0:
            out = {key: round(value / total, 8) for key, value in out.items()}
        return dict(sorted(out.items()))

    def _pf_range_169_for_player(self, player_id: int) -> dict[str, float]:
        if not self._bot.use_range_equity:
            return {}
        try:
            weights = self._bot._range_tracker.get_distribution(player_id)
        except Exception:
            traceback.print_exc()
            return {}
        known = {hcm.card_to_int(c) for c in list(self._hole_cards) + list(self._board)}
        if known:
            weights[hcm.blocked_by(known)] = 0.0
        total = float(weights.sum())
        if total <= 1e-15:
            return {}
        weights = weights / total
        out: dict[str, float] = {}
        for category, indices in hcm.CATEGORY_TO_INDICES.items():
            prob = float(weights[indices].sum())
            if prob > 1e-10:
                out[category] = prob
        return self._rounded_range_map(out)

    @staticmethod
    def _g5_ranges_by_pid(result: Optional[dict[str, Any]]) -> dict[str, dict[str, float]]:
        if not isinstance(result, dict):
            return {}
        by_pid = result.get("ranges_by_player_id")
        if isinstance(by_pid, dict):
            return {
                str(pid): PokerFateAPI._rounded_range_map(dict(range_map or {}))
                for pid, range_map in by_pid.items()
                if isinstance(range_map, dict)
            }
        rows = result.get("ranges")
        if not isinstance(rows, list):
            return {}
        out: dict[str, dict[str, float]] = {}
        for row in rows:
            if not isinstance(row, dict):
                continue
            pid = row.get("player_id")
            range_map = row.get("range_169")
            if pid is None or not isinstance(range_map, dict):
                continue
            out[str(pid)] = PokerFateAPI._rounded_range_map(range_map)
        return out

    def _maybe_record_range_compare_snapshot(
        self,
        *,
        gs: GameState,
        street: str,
        decision: BotDecision,
        decision_source: str,
        g5_result: Optional[dict[str, Any]],
        pot: float,
        current_bet: float,
        to_call: float,
        my_stack: float,
    ) -> None:
        if not self._runtime_collection_enabled:
            return
        if self._range_compare_collector is None:
            return
        if not self._bot.use_range_equity:
            return
        g5_ranges = self._g5_ranges_by_pid(g5_result)
        if not g5_ranges:
            return
        opponents = []
        for player in gs.active_players:
            if player.player_id == self.my_player_id:
                continue
            pf_range = self._pf_range_169_for_player(player.player_id)
            g5_range = g5_ranges.get(str(player.player_id), {})
            if not pf_range or not g5_range:
                continue
            opponents.append({
                "player_id": int(player.player_id),
                "name": self._session_names.get(player.player_id, player.name),
                "position": self._hand_positions.get(player.player_id, ""),
                "stack": float(player.stack or 0.0),
                "current_bet": float(player.current_bet or 0.0),
                "pf_range_169": pf_range,
                "g5_range_169": g5_range,
            })
        if not opponents:
            return
        self._range_compare_collector.record_decision_snapshot({
            "decision_index": int(self._decision_index or 0),
            "street": str(street or "").lower(),
            "decision_source": str(decision_source or ""),
            "hero_action": decision.action,
            "hero_amount": float(decision.amount or 0.0),
            "hero_cards": [str(c) for c in self._hole_cards],
            "board": [str(c) for c in self._board],
            "pot": float(pot or 0.0),
            "current_bet": float(current_bet or 0.0),
            "to_call": float(to_call or 0.0),
            "my_stack": float(my_stack or 0.0),
            "opponents": opponents,
        })

    def _remember_adopted_hero_action_for_local_bot(
        self,
        street: str,
        decision: BotDecision,
    ) -> None:
        self._bot._my_street_actions[str(street or "").lower()] = str(decision.action or "")

    def _maybe_shadow_auto_decide_after_real_fold(self, street: str) -> None:
        if (
            not self._external_decision_engine_shadow
            or not self._external_engine_ready()
            or self._external_decision_hand_disabled_reason
        ):
            return
        my_player = self._get_my_player()
        if my_player is None or not my_player.is_folded:
            return
        player_to_act_id = getattr(self._external_decision_engine, "player_to_act_id", None)
        if player_to_act_id != self.my_player_id:
            return

        street_key = street.lower()
        current_bet = self._current_street_max_bet()
        my_current = float(my_player.current_bet or 0.0)
        gs = self._build_game_state(
            street=street_key,
            pot=self._last_known_pot,
            current_bet=current_bet,
            my_stack=float(my_player.stack or 0.0),
            my_current_bet_this_street=my_current,
        )
        shadow = self._shadow_decide_with_external_engine(
            gs,
            street=street_key,
            my_current_bet_this_street=my_current,
            force_shadow=True,
        )
        if shadow is None:
            return
        self._log_g5_shadow_decision(shadow, street=street_key)
        self._notify_external_engine_shadow_action(
            shadow,
            street=street_key,
            my_current_bet_this_street=my_current,
        )

    @staticmethod
    def _g5_decision_reasoning(result: dict[str, Any]) -> str:
        if not result:
            return "g5 decision"
        parts = ["g5 decision"]
        cc_ev = result.get("checkCallEV", result.get("check_call_ev"))
        br_ev = result.get("betRaiseEV", result.get("bet_raise_ev"))
        if cc_ev is not None or br_ev is not None:
            parts.append(f"ccEV={cc_ev} brEV={br_ev}")
        spent = result.get("timeSpentSeconds", result.get("time_spent_seconds"))
        if spent is not None:
            parts.append(f"t={spent}s")
        msg = str(result.get("message") or "").strip()
        if msg:
            parts.append(msg)
        return " | ".join(parts)

    @staticmethod
    def _realtime_cfr_decision_reasoning(result: dict[str, Any]) -> str:
        if not result:
            return "realtime_cfr decision"
        parts = ["realtime_cfr decision"]
        selected = str(result.get("selected_label") or "").strip()
        prob = result.get("selected_prob")
        if selected:
            if prob is not None:
                parts.append(f"{selected}@{float(prob):.0%}")
            else:
                parts.append(selected)
        exploitability = result.get("exploitability_pct")
        if exploitability is not None:
            parts.append(f"expl={float(exploitability):.2f}%")
        elapsed = result.get("elapsed_ms")
        if elapsed is not None:
            parts.append(f"t={float(elapsed) / 1000.0:.1f}s")
        node_path = str(result.get("node_path") or "").strip()
        if node_path:
            parts.append(f"path={node_path}")
        cec_summary = PokerFateAPI._realtime_cfr_cec_summary(result)
        if cec_summary:
            parts.append(cec_summary)
        safety_summary = PokerFateAPI._realtime_cfr_safety_summary(result)
        if safety_summary:
            parts.append(safety_summary)
        return " | ".join(parts)

    @staticmethod
    def _realtime_cfr_cec_summary(result: dict[str, Any]) -> str:
        exploit = result.get("exploit")
        if not isinstance(exploit, dict):
            return ""
        line_context = exploit.get("line_context")
        if not isinstance(line_context, dict):
            return ""
        range_v2 = line_context.get("range_v2")
        if not isinstance(range_v2, dict):
            return ""
        cec = range_v2.get("cec_calibration")
        if not isinstance(cec, dict) or not cec.get("used"):
            return ""
        raw_bucket = range_v2.get("raw_bucket_dist")
        bucket = range_v2.get("bucket_dist")
        if not isinstance(raw_bucket, dict) or not isinstance(bucket, dict):
            return ""

        order = ("nuts", "strong", "medium", "draw", "weak_draw", "air")
        labels = {
            "nuts": "N",
            "strong": "S",
            "medium": "M",
            "draw": "D",
            "weak_draw": "W",
            "air": "A",
        }

        def pct(dist: dict[str, Any], key: str) -> int:
            try:
                return int(round(float(dist.get(key, 0.0) or 0.0) * 100.0))
            except Exception:
                return 0

        raw_text = "/".join(f"{labels[k]}{pct(raw_bucket, k)}" for k in order)
        cal_text = "/".join(f"{labels[k]}{pct(bucket, k)}" for k in order)
        level = str(cec.get("level") or cec.get("source") or "cec").strip() or "cec"
        rows = cec.get("rows")
        rel = cec.get("raw_reliability")
        meta = [f"cec={level}"]
        if rows is not None:
            try:
                meta.append(f"n={int(float(rows))}")
            except Exception:
                pass
        if rel is not None:
            try:
                meta.append(f"rel={float(rel):.0%}")
            except Exception:
                pass
        return f"{' '.join(meta)} {raw_text}→{cal_text}"

    @staticmethod
    def _realtime_cfr_safety_summary(result: dict[str, Any]) -> str:
        exploit = result.get("exploit")
        if not isinstance(exploit, dict):
            return ""
        safety = exploit.get("safety")
        if not isinstance(safety, dict):
            return ""
        labels = {
            "strict_bluff_gate": "bluff",
            "large_size_support": "large",
            "river_aggression_risk": "river",
            "turn_barrel_quality": "turn",
            "raise_exposure_risk": "raise-exp",
            "calloff_risk": "calloff",
            "sticky_aggression": "sticky",
            "overvalue_cheap_call_guard": "overvalue-call",
            "gto_ev_floor": "gto-floor",
            "defense_mdf": "mdf",
        }
        active: list[str] = []
        for key, label in labels.items():
            raw = safety.get(key)
            items = raw if isinstance(raw, list) else [raw]
            for item in items:
                if not isinstance(item, dict):
                    continue
                applied = bool(item.get("applied"))
                blocked = bool(item.get("blocked"))
                discounted = float(item.get("discount_bb") or 0.0) > 1e-9
                if applied or blocked or discounted:
                    active.append(label)
                    break
        if not active:
            return ""
        return "risk=" + ",".join(active[:4])

    @staticmethod
    def _flop_book_decision_reasoning(result: dict[str, Any]) -> str:
        if not result:
            return "flop_book decision"
        parts = ["flop_book decision"]
        scenario = str(result.get("scenario") or "").strip()
        if scenario:
            parts.append(scenario)
        selected = str(result.get("selected_label") or "").strip()
        prob = result.get("selected_prob")
        if selected:
            if prob is not None:
                parts.append(f"{selected}@{float(prob):.0%}")
            else:
                parts.append(selected)
        node_path = str(result.get("node_path") or "").strip()
        if node_path:
            parts.append(f"path={node_path}")
        if result.get("exact") is False:
            rep = str(result.get("flop_representative") or "").strip()
            if rep:
                parts.append(f"rep={rep}")
        exploit = result.get("exploit")
        if isinstance(exploit, dict) and exploit.get("used"):
            confidence = exploit.get("confidence")
            if confidence is not None:
                parts.append(f"exploit={float(confidence):.0%}")
            mode = str(exploit.get("mode") or "").strip()
            if mode:
                parts.append(mode)
        elapsed = result.get("elapsed_ms")
        if elapsed is not None:
            parts.append(f"t={float(elapsed):.0f}ms")
        return " | ".join(parts)

    @staticmethod
    def _g5_shadow_warning_text(reason: str) -> str:
        text = str(reason or "").strip()
        if text.startswith("unsupported forced post:"):
            detail = text.split(":", 1)[1].strip()
            return f"已忽略强制补盲 {detail}".strip()
        return text

    @staticmethod
    def _g5_shadow_diagnostics(shadow: dict[str, Any]) -> dict[str, Any]:
        diag: dict[str, Any] = {"status": str(shadow.get("status") or "")}
        decision = shadow.get("decision")
        if isinstance(decision, BotDecision):
            diag["action"] = decision.action
            diag["amount"] = decision.amount
        reason = str(shadow.get("reason") or "").strip()
        if reason:
            diag["reason"] = reason
        elapsed_ms = shadow.get("elapsed_ms")
        if elapsed_ms is not None:
            diag["elapsed_ms"] = round(float(elapsed_ms), 1)
        reasoning = str(shadow.get("reasoning") or "").strip()
        if reasoning:
            diag["reasoning"] = reasoning
        warning = str(shadow.get("warning") or "").strip()
        if warning:
            diag["warning"] = warning
        result = shadow.get("result")
        if isinstance(result, dict):
            diag["result"] = result
        return diag

    # ------------------------------------------------------------------
    # Hand lifecycle events
    # ------------------------------------------------------------------

    def new_hand(
        self,
        players: List[PlayerInfo],
        dealer_id: int,
        hand_number: Optional[int] = None,
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
        hand_number : int, optional
            External monotonically increasing hand number. When omitted,
            the API keeps its existing local counter behavior.

        Notes
        -----
        - If a player_id appears that was not seen before, they are
          treated as a new opponent with a fresh opponent model.
        - If a previously busted player is replaced by a new player_id,
          the old model is automatically abandoned (keyed by player_id).
        """
        if hand_number is None:
            self._hand_number += 1
        else:
            self._hand_number = int(hand_number)
        self._dealer_id = dealer_id
        self._hole_cards = []
        self._board = []
        self._action_history = []
        self._last_hand_push_detail = ""
        self._last_auto_collect_reasons = []
        self._pending_river_value_sizing_rows = []
        self._decision_index = 0
        self._last_decision_diagnostics = {}
        self._external_decision_hand_disabled_reason = ""
        self._external_decision_shadow_hero_folded = False
        self._external_decision_shadow_warning = ""
        self._flop_book_error = ""
        if self._flop_book_engine is not None:
            self._flop_book_engine._last_result = {}
            self._flop_book_engine._last_error = ""
        self._realtime_cfr_error = ""
        if self._realtime_cfr_engine is not None:
            self._realtime_cfr_engine._last_result = {}
            self._realtime_cfr_engine._last_error = ""
        if self._external_engine_ready() or self._realtime_cfr_enabled or self._flop_book_enabled:
            self._external_decision_engine_error = ""
        self._my_stack_start: float = 0.0  # set after resolving stacks below

        # Start showdown calibration for this hand
        if self._calibrator is not None:
            self._apply_spooled_calibration_updates()
            self._calibrator.start_hand(self._hand_number)

        # Preflop 初始 pot ≈ SB + BB（盲注已投入）。以前设 0 会让 notify_action
        # 里 `bet_ratio = bet_amount / pot` 在第一次 preflop open 时恒为 0，
        # 吞掉 open 尺寸信号（问题 2 的 deep open-shove range 窄化依赖此信号）。
        self._last_known_pot: float = self.small_blind + self.big_blind
        self._street_base_pot = self._last_known_pot
        self._street_base_street = "preflop"
        self._street_contribs = {}
        # Per-hand position map: player_id -> position string (UTG/MP/CO/...).
        # Upstream may leave PlayerInfo.position empty; after building the
        # players list below we fill those gaps from dealer_id + seat order.
        self._hand_positions: Dict[int, str] = {}
        self._hand_seat_indices = {}
        self._dealer_seat_index = None
        self._players = []
        for p in players:
            # Resolve stack: explicit > session history > default
            stack = p.stack
            if stack is None:
                stack = self._session_stacks.get(p.player_id, self._default_stack)

            self._session_names[p.player_id] = p.name
            if p.seat_index is not None:
                seat_index = int(p.seat_index)
                self._hand_seat_indices[int(p.player_id)] = seat_index
                if int(p.player_id) == int(dealer_id):
                    self._dealer_seat_index = seat_index
            # None -> '' so downstream treats it as unknown; '' triggers the
            # position inference below. Never look this value up with
            # dict.get(k, default) because the entry exists as ''.
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

        if self._dealer_seat_index is None and int(dealer_id) < 0:
            self._dealer_seat_index = abs(int(dealer_id)) - 1

        dealer_pos = 0
        for idx, p in enumerate(self._players):
            if p.player_id == dealer_id:
                dealer_pos = idx
                break
        position_state = GameState(
            players=self._players,
            dealer_pos=dealer_pos,
            player_positions=dict(self._hand_positions),
        )
        for p in self._players:
            if not self._hand_positions.get(p.player_id):
                self._hand_positions[p.player_id] = position_state.position_of(p)
        self._g5_hand_start_players = [
            {
                "player_id": p.player_id,
                "name": p.name,
                "g5_name": stable_player_name(p.player_id),
                "stack": float(p.stack or 0.0),
                "position": self._hand_positions.get(p.player_id, ""),
                "seat_index": self._hand_seat_indices.get(p.player_id),
            }
            for p in self._players
        ]
        if self._range_compare_collector is not None:
            self._range_compare_collector.start_hand(
                self._hand_number,
                players=list(self._g5_hand_start_players),
                hero_id=self.my_player_id,
            )

        # Record my stack at the start of this hand for delta calculation
        my_p = self._get_my_player()
        self._my_stack_start = my_p.stack if my_p else 0.0

        all_ids = [p.player_id for p in players if p.player_id != self.my_player_id]
        player_names = {p.player_id: p.name for p in players if p.player_id != self.my_player_id}
        player_positions = {
            p.player_id: self._hand_positions.get(p.player_id, '')
            for p in players if p.player_id != self.my_player_id
        }
        self._bot.new_hand(
            all_ids,
            player_names=player_names,
            player_positions=player_positions,
        )
        self._external_engine_start_hand()

        self._log.hand_start(
            hand_number=self._hand_number,
            players=[
                {"id": p.player_id, "name": p.name,
                 "stack": p.stack, "pos": self._hand_positions.get(p.player_id, '')}
                for p in self._players
            ],
            dealer_id=dealer_id,
            big_blind=self.big_blind,
            hero_id=self.my_player_id,
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
        self._external_engine_deal_hole_cards()

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
        self._external_engine_deal_board([str(c) for c in new_cards], street)
        self._log.board(street, cards, pot=display_pot)
        self._maybe_shadow_auto_decide_after_real_fold(street)

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
        opp_pos = self._hand_positions.get(event.player_id) or 'CO'
        opp_is_ip = self._is_player_ip(event.player_id)
        base_pot = self._street_base_pot
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
        self._external_engine_notify_action(
            player_id=event.player_id,
            action=action_name,
            amount_added=amount_added,
            total_bet_after=total_bet_after,
            street=street_key,
        )
        self._maybe_shadow_auto_decide_after_real_fold(street_key)

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
            is_ip=opp_is_ip,
        )
        self._record_river_value_sizing_response(
            event=event,
            action_name=action_name,
            amount_added=amount_added,
            total_bet_after=total_bet_after,
        )

        pobj = self._get_player(event.player_id)
        name = pobj.name if pobj else str(event.player_id)

        # Gather extra context for enriched opponent action log

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
                my_current_bet = my_player.current_bet or 0.0
                to_call = max(0.0, total_bet_after - my_current_bet)

        self._log.opponent_action(
            name, event.action, normalized_action_amount, event.street,
            big_blind=self.big_blind,
            pot=self._last_known_pot,
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
        # Register name for the uid-keyed opponent model; display names are not identities.
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
        if self._calibrator is not None:
            self._apply_spooled_calibration_updates()
        self._last_known_pot = pot
        street_key = street.lower()
        if self._street_base_street != street_key:
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

        t0 = time.perf_counter()
        decision_source = "pokerfate"
        action = self._decide_with_flop_book(
            gs,
            street=street_key,
        )
        if action is not None:
            decision_source = "flop_book"
        else:
            action = self._decide_with_realtime_cfr(
                gs,
                street=street_key,
            )
            if action is not None:
                decision_source = "realtime_cfr"
            else:
                action = self._decide_with_external_engine(
                    gs,
                    street=street_key,
                    my_current_bet_this_street=my_current_bet_this_street,
                )
        if action is not None and decision_source not in {"realtime_cfr", "flop_book"}:
            decision_source = self._external_decision_engine_name
        elif action is None:
            self._bot.set_next_decision_seed(
                self._next_decision_seed(
                    street=street_key,
                    pot=pot,
                    current_bet=current_bet,
                    to_call=to_call,
                    my_stack=my_stack,
                )
            )
            action = self._bot.decide(gs, self.my_player_id, is_bb_option=is_bb_option)
        elapsed_ms = (time.perf_counter() - t0) * 1000
        decision_timing: dict[str, Any] = {
            "decision_select_ms": round(float(elapsed_ms), 1),
        }
        decision = self._to_decision(action)
        g5_shadow = None
        local_shadow = None
        external_cfr_sources = {"flop_book", "realtime_cfr"}
        if decision_source not in {"g5", *external_cfr_sources}:
            shadow_t0 = time.perf_counter()
            g5_shadow = self._shadow_decide_with_external_engine(
                gs,
                street=street_key,
                my_current_bet_this_street=my_current_bet_this_street,
            )
            decision_timing["g5_shadow_ms"] = round((time.perf_counter() - shadow_t0) * 1000.0, 1)
        elif decision_source in {"g5", *external_cfr_sources}:
            shadow_t0 = time.perf_counter()
            local_shadow = self._local_shadow_decide(
                gs,
                street=street_key,
                pot=pot,
                current_bet=current_bet,
                to_call=to_call,
                my_stack=my_stack,
                is_bb_option=is_bb_option,
            )
            decision_timing["local_shadow_ms"] = round((time.perf_counter() - shadow_t0) * 1000.0, 1)

        g5_result_for_range_compare = None
        if decision_source == "g5":
            g5_result_for_range_compare = (
                self._external_decision_engine.last_result
                if self._external_decision_engine is not None
                else {}
            )
        elif isinstance(g5_shadow, dict) and g5_shadow.get("status") == "ok":
            shadow_result = g5_shadow.get("result")
            if isinstance(shadow_result, dict):
                g5_result_for_range_compare = shadow_result
        range_compare_t0 = time.perf_counter()
        self._maybe_record_range_compare_snapshot(
            gs=gs,
            street=street_key,
            decision=decision,
            decision_source=decision_source,
            g5_result=g5_result_for_range_compare,
            pot=pot,
            current_bet=current_bet,
            to_call=to_call,
            my_stack=my_stack,
        )
        decision_timing["range_compare_snapshot_ms"] = round(
            (time.perf_counter() - range_compare_t0) * 1000.0,
            1,
        )

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
        amount_added = 0.0
        total_bet_after = float(my_current_bet_this_street)
        apply_action_t0 = time.perf_counter()
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
            if (
                self._external_engine_ready()
                and not self._external_decision_hand_disabled_reason
                and self._external_engine_active_for_street(street_key)
            ):
                self._external_engine_notify_action(
                    player_id=self.my_player_id,
                    action=decision.action,
                    amount_added=amount_added,
                    total_bet_after=total_bet_after,
                    street=street_key,
                )
            elif g5_shadow is not None:
                self._notify_external_engine_shadow_action(
                    g5_shadow,
                    street=street_key,
                    my_current_bet_this_street=my_current_bet_this_street,
                )
        decision_timing["apply_action_ms"] = round((time.perf_counter() - apply_action_t0) * 1000.0, 1)

        diagnostics_t0 = time.perf_counter()
        if decision_source == "g5":
            self._remember_adopted_hero_action_for_local_bot(street_key, decision)
            g5_result = (
                self._external_decision_engine.last_result
                if self._external_decision_engine is not None
                else {}
            )
            self._last_decision_diagnostics = {
                "decision_source": "g5",
                "final_purpose": "",
                "g5": g5_result,
            }
            if local_shadow is not None:
                self._last_decision_diagnostics["local_shadow"] = (
                    self._local_shadow_diagnostics(local_shadow)
                )
            log_equity, log_equity_random, log_spr, log_equity_mode = (
                self._log_metrics_from_local_shadow(local_shadow, "g5")
            )
            log_reasoning = self._g5_decision_reasoning(g5_result)
            log_gto_refs = None
        elif decision_source == "flop_book":
            self._remember_adopted_hero_action_for_local_bot(street_key, decision)
            flop_result = (
                self._flop_book_engine.last_result
                if self._flop_book_engine is not None
                else {}
            )
            self._last_decision_diagnostics = {
                "decision_source": "flop_book",
                "final_purpose": "flop_book",
                "flop_book": flop_result,
            }
            if local_shadow is not None:
                self._last_decision_diagnostics["local_shadow"] = (
                    self._local_shadow_diagnostics(local_shadow)
                )
            log_equity, log_equity_random, log_spr, log_equity_mode = (
                self._log_metrics_from_local_shadow(local_shadow, "flop_book")
            )
            log_reasoning = self._flop_book_decision_reasoning(flop_result)
            log_gto_refs = None
        elif decision_source == "realtime_cfr":
            self._remember_adopted_hero_action_for_local_bot(street_key, decision)
            cfr_result = (
                self._realtime_cfr_engine.last_result
                if self._realtime_cfr_engine is not None
                else {}
            )
            self._last_decision_diagnostics = {
                "decision_source": "realtime_cfr",
                "final_purpose": "realtime_cfr",
                "realtime_cfr": cfr_result,
            }
            if local_shadow is not None:
                self._last_decision_diagnostics["local_shadow"] = (
                    self._local_shadow_diagnostics(local_shadow)
                )
            log_equity, log_equity_random, log_spr, log_equity_mode = (
                self._log_metrics_from_local_shadow(local_shadow, "realtime_cfr")
            )
            log_reasoning = self._realtime_cfr_decision_reasoning(cfr_result)
            log_gto_refs = None
        else:
            self._last_decision_diagnostics = {
                **self._bot.last_decision_diagnostics,
                "decision_source": "pokerfate",
            }
            if g5_shadow is not None:
                self._last_decision_diagnostics["g5_shadow"] = (
                    self._g5_shadow_diagnostics(g5_shadow)
                )
            log_equity = self._bot.last_equity
            log_equity_random = self._bot.last_equity_random
            log_spr = self._bot.last_spr
            log_equity_mode = self._bot.last_equity_mode
            log_reasoning = self._bot.last_reasoning
            log_gto_refs = self._bot.last_gto_refs
        decision_timing["diagnostics_build_ms"] = round(
            (time.perf_counter() - diagnostics_t0) * 1000.0,
            1,
        )
        if decision_source == "realtime_cfr":
            cfr_timing = (
                self._last_decision_diagnostics
                .get("realtime_cfr", {})
                .get("timing")
            )
            if isinstance(cfr_timing, dict):
                decision_timing["realtime_cfr"] = cfr_timing

        self._log.decision(
            action=decision.action,
            amount=decision.amount,
            street=street,
            equity=log_equity,
            pot=pot,
            to_call=effective_to_call,
            bot_name=my_name,
            reasoning=log_reasoning,
            equity_random=log_equity_random,
            spr=log_spr,
            equity_mode=log_equity_mode,
            gto_refs=log_gto_refs,
            elapsed_ms=elapsed_ms,
            timing=decision_timing,
            river_relative=(
                self.last_decision_diagnostics()
                .get("river_relative", {})
            ),
        )
        if g5_shadow is not None:
            self._log_g5_shadow_decision(g5_shadow, street=street_key)
        if local_shadow is not None:
            self._log_local_shadow_decision(local_shadow, street=street_key)
        self._maybe_record_river_value_sizing_decision(
            street_key=street_key,
            decision=decision,
            pot=pot,
            current_bet=current_bet,
            effective_to_call=effective_to_call,
            my_stack=my_stack,
            my_current_bet_this_street=my_current_bet_this_street,
            amount_added=amount_added,
            total_bet_after=total_bet_after,
        )
        return decision

    def _maybe_record_river_value_sizing_decision(
        self,
        *,
        street_key: str,
        decision: BotDecision,
        pot: float,
        current_bet: float,
        effective_to_call: float,
        my_stack: float,
        my_current_bet_this_street: float,
        amount_added: float,
        total_bet_after: float,
    ) -> None:
        if self._runtime_calibration_recorder is None:
            return
        if "PYTEST_CURRENT_TEST" in os.environ:
            return
        if street_key != "river" or decision.action != "raise":
            return
        # This sizing dataset is for proactive river value bets. Facing-bet
        # raises answer a different question: raise/call/fold defense.
        if effective_to_call > 1e-9 or current_bet > my_current_bet_this_street + 1e-9:
            return
        diag = self.last_decision_diagnostics() or {}
        purpose_raw = str(diag.get("final_purpose") or "")
        purpose = purpose_raw.split("→", 1)[0].strip()
        if purpose not in _RIVER_VALUE_SIZING_PURPOSES:
            return

        primary_opp_id = int(diag.get("primary_opp_id") or -1)
        row = {
            "street": "river",
            "decision_index": int(self._decision_index or 0),
            "hero_action": decision.action,
            "purpose": purpose,
            "purpose_raw": purpose_raw,
            "is_value_purpose": True,
            "amount_added": float(amount_added or 0.0),
            "total_bet_after": float(total_bet_after or 0.0),
            "bet_frac_pot": (
                float(amount_added or 0.0) / float(pot)
                if float(pot or 0.0) > 0 else 0.0
            ),
            "engine_frac": float(diag.get("frac") or 0.0),
            "pot_before": float(pot or 0.0),
            "stack_before": float(my_stack or 0.0),
            "my_current_bet_before": float(my_current_bet_this_street or 0.0),
            "hole_cards": [str(c) for c in self._hole_cards],
            "board": [str(c) for c in self._board],
            "hero_bucket": str(diag.get("hero_bucket") or ""),
            "hero_made_subtype": str(diag.get("hero_made_subtype") or ""),
            "hero_hand_rank": str(diag.get("hero_hand_rank") or ""),
            "equity_range": float(diag.get("equity_range") or 0.0),
            "equity_mc": float(diag.get("equity_mc") or 0.0),
            "pot_odds": float(diag.get("pot_odds") or 0.0),
            "spr": float(diag.get("spr") or 0.0),
            "decision_reason": str(diag.get("decision_reason") or ""),
            "purpose_candidates": list(diag.get("purpose_candidates") or []),
            "villain_bucket_dist": dict(diag.get("villain_bucket_dist") or {}),
            "villain_vs_hero_dist": dict(diag.get("villain_vs_hero_dist") or {}),
            "river_relative": dict(diag.get("river_relative") or {}),
            "river_relative_calibration": dict(diag.get("river_relative_calibration") or {}),
            "primary_opp_id": primary_opp_id,
            "primary_opp_name": self._session_names.get(primary_opp_id, str(primary_opp_id))
                                if primary_opp_id >= 0 else "",
            "primary_opp_stats": self._opponent_stats_snapshot(primary_opp_id),
            "active_opponents": [
                {
                    "player_id": p.player_id,
                    "name": self._session_names.get(p.player_id, p.name),
                    "stack": float(p.stack or 0.0),
                }
                for p in self._players
                if p.player_id != self.my_player_id and not p.is_folded
            ],
            "responses": [],
        }
        self._pending_river_value_sizing_rows.append(row)

    def _record_river_value_sizing_response(
        self,
        *,
        event: ActionEvent,
        action_name: str,
        amount_added: float,
        total_bet_after: float,
    ) -> None:
        if not self._pending_river_value_sizing_rows:
            return
        if event.street.lower() != "river":
            return
        response = {
            "player_id": int(event.player_id),
            "name": self._session_names.get(event.player_id, str(event.player_id)),
            "action": action_name,
            "amount_added": float(amount_added or 0.0),
            "total_bet_after": float(total_bet_after or 0.0),
        }
        for row in self._pending_river_value_sizing_rows:
            if row.get("finalized"):
                continue
            row.setdefault("responses", []).append(dict(response))

    def _flush_river_value_sizing_rows(
        self,
        *,
        winner_ids: List[int],
        winner_names: List[str],
        pot: float,
        my_delta: float,
        final_stacks: Dict[int, float],
        showdown_hands: Dict[int, List[str]],
        hand_combos: Dict[str, str],
    ) -> None:
        if not self._pending_river_value_sizing_rows:
            return
        try:
            for row in self._pending_river_value_sizing_rows:
                if row.get("finalized"):
                    continue
                responses = list(row.get("responses") or [])
                actions = [str(r.get("action") or "") for r in responses]
                if "raise" in actions:
                    response_kind = "raised"
                elif "call" in actions:
                    response_kind = "called"
                elif responses:
                    response_kind = "fold_all"
                else:
                    response_kind = "no_response"
                paid_amount = sum(
                    float(r.get("amount_added") or 0.0)
                    for r in responses
                    if str(r.get("action") or "") in {"call", "raise"}
                )
                row.update({
                    "finalized": True,
                    "response_kind": response_kind,
                    "paid": response_kind in {"called", "raised"},
                    "paid_amount": paid_amount,
                    "folded_by": [
                        r.get("name", "")
                        for r in responses
                        if str(r.get("action") or "") == "fold"
                    ],
                    "called_by": [
                        r.get("name", "")
                        for r in responses
                        if str(r.get("action") or "") == "call"
                    ],
                    "raised_by": [
                        r.get("name", "")
                        for r in responses
                        if str(r.get("action") or "") == "raise"
                    ],
                    "winner_ids": [int(x) for x in winner_ids],
                    "winner_names": list(winner_names),
                    "hero_won": self.my_player_id in set(winner_ids),
                    "pot_final": float(pot or 0.0),
                    "my_delta": float(my_delta or 0.0),
                    "my_delta_bb": (
                        float(my_delta or 0.0) / float(self.big_blind)
                        if float(self.big_blind or 0.0) > 0 else 0.0
                    ),
                    "final_stack": float((final_stacks or {}).get(self.my_player_id, 0.0) or 0.0),
                    "showdown_hands": {
                        self._session_names.get(pid, str(pid)): [str(c) for c in cards]
                        for pid, cards in (showdown_hands or {}).items()
                    },
                    "hand_combos": dict(hand_combos or {}),
                    "actual_relation_by_player": self._actual_relations_vs_showdown(
                        showdown_hands or {}
                    ),
                })
                if self._runtime_calibration_recorder is not None:
                    self._runtime_calibration_recorder.write_river_value_sizing(
                        row,
                        big_blind=self.big_blind,
                        hand_id=self._hand_number,
                        source="runtime",
                    )
        except Exception:
            traceback.print_exc()
        finally:
            self._pending_river_value_sizing_rows = []

    def _actual_relations_vs_showdown(
        self,
        showdown_hands: Dict[int, List[str]],
    ) -> dict[str, str]:
        if not showdown_hands or len(self._board) < 5 or len(self._hole_cards) < 2:
            return {}
        try:
            hero_score = HandEvaluator.evaluate(list(self._hole_cards) + list(self._board))
        except Exception:
            return {}
        out: dict[str, str] = {}
        for pid, cards in showdown_hands.items():
            if pid == self.my_player_id:
                continue
            try:
                hole = [
                    c if isinstance(c, Card) else Card.from_str(str(c))
                    for c in list(cards)[:2]
                ]
                villain_score = HandEvaluator.evaluate(hole + list(self._board))
                cmp = HandEvaluator.compare(hero_score, villain_score)
                relation = "win" if cmp > 0 else "loss" if cmp < 0 else "tie"
            except Exception:
                relation = "unknown"
            out[self._session_names.get(pid, str(pid))] = relation
        return out

    def _opponent_stats_snapshot(self, player_id: int) -> dict[str, Any]:
        if player_id is None or player_id < 0:
            return {}
        try:
            stats = self._bot.opponent_model.get(player_id)
            return {
                "hands_seen": int(stats.hands_seen),
                "vpip": float(stats.vpip),
                "pfr": float(stats.pfr),
                "three_bet_pct": float(stats.three_bet_pct),
                "fold_to_3bet": float(stats.fold_to_3bet),
                "fold_to_cbet": float(stats.fold_to_cbet),
                "af": float(stats.aggression_factor),
                "wtsd": float(stats.wtsd),
                "wmsd": float(stats.wmsd),
                "bluff_win_rate": float(stats.bluff_win_rate),
                "river_fold_rate": float(stats.river_fold_rate),
                "river_bet_frequency": float(stats.river_bet_frequency),
                "river_action_count": int(stats.river_action_count),
                "pwi": float(stats.pwi()),
            }
        except Exception:
            traceback.print_exc()
            return {}

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

    @staticmethod
    def _board_hand_type_for_bluff_stats(board: List[Card]) -> Optional[int]:
        if len(board) < 3:
            return None
        if len(board) >= 5:
            return int(HandEvaluator.evaluate(list(board))[0]) + 1

        counts = Counter(c.rank.value for c in board)
        max_count = max(counts.values(), default=0)
        pair_count = sum(1 for count in counts.values() if count >= 2)
        if max_count >= 4:
            return 8
        if max_count >= 3:
            return 4
        if pair_count >= 2:
            return 3
        if max_count >= 2:
            return 2
        return 1

    def hand_over(
        self,
        winner_ids: List[int],
        pot: float,
        final_stacks: Optional[Dict[int, float]] = None,
        winner_payouts: Optional[Dict[int, float]] = None,
        showdown_hands: Optional[Dict[int, List[str]]] = None,
        winner_hand_types: Optional[Dict[int, int]] = None,
        my_profit_delta: Optional[float] = None,
        robot_player_ids: Optional[List[int] | set[int]] = None,
        robot_player_uids: Optional[Dict[int, str]] = None,
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
        winner_payouts : dict, optional
            {player_id: chips_awarded_from_pot}. This is the gross pot share,
            not stack delta. It is used by external engines such as g5 whose
            hand history stores Wins actions at showdown.
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
        robot_player_ids : list/set, optional
            Player IDs known to be robots in this hand. If any of them has
            revealed cards, the complete formatted hand log is copied to
            pokerfate/logs/bot.log after all end-of-hand logs are emitted.
        robot_player_uids : dict, optional
            Optional player_id → uid mapping for the bot.log header.
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
        robot_ids = {int(pid) for pid in (robot_player_ids or [])}
        robot_showdown_players = []
        if showdown_hands and robot_ids:
            robot_uids = robot_player_uids or {}
            for pid in sorted(set(showdown_hands) & robot_ids):
                robot_showdown_players.append({
                    "player_id": pid,
                    "seat": pid,
                    "uid": robot_uids.get(pid, ""),
                    "name": self._session_names.get(pid, str(pid)),
                    "cards": [str(c) for c in showdown_hands.get(pid, [])],
                })

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
        if self._range_compare_collector is not None and self._runtime_collection_enabled:
            try:
                self._range_compare_collector.record_showdown(
                    shown_cards=showdown_hands or {},
                    final_board=self._board,
                    hero_cards=self._hole_cards,
                )
                self._range_compare_collector.finalize_hand()
            except Exception:
                traceback.print_exc()
        self._record_g5_action_model_hand()
        self._external_engine_finish_hand(
            winner_ids=winner_ids,
            pot=pot,
            winner_payouts=winner_payouts,
            final_stacks=final_stacks,
        )
        self._log.mark_robot_showdown_hand(robot_showdown_players)
        self._flush_river_value_sizing_rows(
            winner_ids=winner_ids,
            winner_names=winner_names,
            pot=pot,
            my_delta=my_delta,
            final_stacks=final_stacks or {},
            showdown_hands=showdown_hands or {},
            hand_combos=hand_combos or {},
        )

        # Track showdown stats (WTSD / WMSD)
        winner_id_set = set(winner_ids) if winner_ids else set()
        if showdown_hands:
            for pid in showdown_hands:
                if pid != self.my_player_id:
                    self._bot.opponent_model.record_showdown(pid, won=(pid in winner_id_set))

        # bluff_win_rate：只在河牌结算时记录弱牌主动赢池。
        # 早街亮牌/未亮牌都可能包含听牌半诈唬，不混入 river bluff 倾向。
        # 对每个赢家：有下注行为 + 知道牌型（服务端下发或摊牌得到）→ 记录
        if winner_ids and wht:
            board_hand_type = self._board_hand_type_for_bluff_stats(list(self._board))
            for pid in winner_ids:
                if pid == self.my_player_id:
                    continue
                hand_type = wht.get(pid)
                if hand_type is None:
                    continue
                if len(self._board) < 5:
                    continue
                # 判断本手该玩家是否有过下注/加注行为
                if self._bot.use_range_equity:
                    action_seq = self._bot._v2_action_history.get(pid, [])
                else:
                    action_seq = self._bot.range_estimator._hand_actions.get(pid, [])
                had_aggression = any(a == 'raise' for _, a in action_seq)
                self._bot.opponent_model.record_win_with_hand_type(
                    pid,
                    hand_type,
                    had_aggression,
                    board_hand_type=board_hand_type,
                )

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
                        if (
                            self._runtime_calibration_recorder is not None
                            and results
                            and "PYTEST_CURRENT_TEST" not in os.environ
                        ):
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

        self._log.flush_robot_hand_if_needed()

        # Auto-save opponent model + showdown/learner data into one file
        self._save_persisted_model()

    def last_hand_push_detail(self, max_bytes: int = 2200) -> str:
        """Return the latest hand detail in a push-friendly compact form."""
        return _fit_utf8(self._last_hand_push_detail, max_bytes)

    def last_decision_diagnostics(self) -> dict:
        if self._last_decision_diagnostics:
            return dict(self._last_decision_diagnostics)
        return dict(self._bot.last_decision_diagnostics or {})

    def last_auto_collect_reasons(self) -> list[str]:
        """Reasons why the latest hand should be auto-collected."""
        return list(self._last_auto_collect_reasons)

    def _build_auto_collect_reasons(self, *, winner_ids: List[int]) -> list[str]:
        if self.my_player_id not in set(winner_ids):
            return []

        rank = self._my_best_hand_rank()
        if rank is None:
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
        amount = float(action.amount or 0.0)
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
        last = self._pattern_logged_hands.get(player_id, 0)
        if self._hand_number - last < self._PATTERN_LOG_INTERVAL:
            return
        self._pattern_logged_hands[player_id] = self._hand_number

        bluff_ag = adj.get("bluff_ag_scale", 0.55)
        if s.fold_to_cbet_opps >= 5 and (bluff_ag >= 0.85 or bluff_ag <= 0.18):
            pattern = "fold_to_cbet_high" if bluff_ag >= 0.85 else "fold_to_cbet_low"
            self._log.opponent_pattern(name, pattern, s.fold_to_cbet, f"bluff_ag×{bluff_ag:.2f}")

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
            player_positions=dict(self._hand_positions),
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
            (p.current_bet or 0.0 for p in self._players),
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
            self._street_base_pot
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
        prev_bet = player.current_bet if player else 0.0

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

    def _is_player_ip(self, player_id: int) -> bool:
        player = self._get_player(player_id)
        if player is None:
            return False
        dealer_pos = 0
        for idx, p in enumerate(self._players):
            if p.player_id == self._dealer_id:
                dealer_pos = idx
                break
        return GameState(
            players=self._players,
            dealer_pos=dealer_pos,
            player_positions=dict(self._hand_positions),
        ).is_ip(player)
