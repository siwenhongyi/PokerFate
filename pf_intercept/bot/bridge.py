"""
Bot bridge: translates proxy events → PokerFateAPI calls → wire actions.

Auto-detection:
  MY_SEAT_ID  ← pb.SitDownRSP.seatid
  BIG_BLIND   ← pb.EnterRoomRSP.room_info.bb
  SMALL_BLIND ← pb.EnterRoomRSP.room_info.sb
  (fallback to config values if messages aren't decoded yet)

Tournament rooms (SNG / MTT / friend SNG):
  Detected from pb.EnterRoomRSP only.  While seated in one the bridge is fully
  passive: no decisions, injects, data collection, bankroll tracking or
  notifications.  The player plays by hand; the next non-tournament
  EnterRoomRSP resumes normal operation.

Card encoding (GFunctions.lua / config.lua):
  code = num + suit * 256
  num  : 2='2' … 14='A'
  suit : 1='d'(方块)  2='c'(梅花)  3='h'(红桃)  4='s'(黑桃)

action_type (game wire; from client EnumConfig.POKER_ACTION):
  0=NONE  1=FOLD  2=CHECK  3=CALL  4=RAISE
  5=WAIT  6=SITED  7=BET  8=SB  9=BB  10=ANTE  11=FORCE_BB
  12=SYS_FOLD  13=SYS_CHECK  14=STRADDLE  15=(reserved)  16=LEAVE_FOLD  17=ALLIN

stage (RoundStartBRC):
  1=Preflop  2=Flop  3=Turn  4=River
"""

from __future__ import annotations
import asyncio
import json
import logging
import random
import threading
import time
from pathlib import Path
from typing import TypeAlias

from pokerfate.api import PokerFateAPI, PlayerInfo, ActionEvent, BotDecision
from pokerfate.calibration.spool_showdown_calibration import spool_backpressure_status
from pokerfate.core.robots import RoomRobotTracker, default_registry
from pokerfate.core.seating import derive_seating
from pf_intercept import config
from pf_intercept.table_policy import Step, TablePolicy, TablePolicyConfig
from pf_intercept.game_api.gamedata import GameDataHTTPContext, _sync_fetch, seed_from_server
from pf_intercept.game_api.http import load_auth_token
from pf_intercept.wire.action_types import ACTION_TYPE_TO_EVENT_ACTION, FOLD_ACTION_TYPES
from pf_notify.client import notify

log = logging.getLogger("pf_bot")

WireInject: TypeAlias = tuple[str, dict] | tuple[str, dict, float]
WireInjectResult: TypeAlias = WireInject | list[WireInject] | None
InjectGuard: TypeAlias = tuple[str, int]

_MAX_INJECT_DELAY = float(config.ACTION_INJECT_DELAY_MAX_SEC)
_BANKROLL_SAMPLE_LIMIT = 200
_HERO_ACTION_PENDING_SUPPRESS_SEC = 8.0
_GAMEDATA_RETRY_SEC = 30.0
_BANKROLL_REASONS: dict[str, str] = {
    "startup": "启动基线",
    "refresh": "余额刷新",
    "leave_room": "离桌后余额刷新",
    "unexpected_leave": "异常离桌重进前",
    "stand_up": "站起后余额刷新",
    "auto_rebuy": "破产买入前",
    "profit_lock": "盈利锁仓离桌",
    "table_switch": "选桌换桌",
    "topup": "桌上补码后余额刷新",
}
# The amounts the client's top-up slider offers, in big blinds (tpl_constdata.PokerBuyinStep).
_TOPUP_STEPS_BB = tuple(range(20, 31)) + tuple(range(40, 201, 10))
_TOPUP_PENDING_HANDS = 2    # a request not credited after this many hands is given up
_TOPUP_RETRY_HANDS = 30     # hands to wait after a refused or lost request
_BUYIN_BB = 100             # one buy-in in big blinds: a bust rebuy, and the unit of the loss cap
_TABLE_LOG_PATH = Path(__file__).resolve().parents[1] / "logs" / "table_select.jsonl"


def _inject_delay_before_action(
    street: str,
    decision: BotDecision,
    pot_chips: int,
    big_blind: float,
) -> float:
    """Seconds to wait after the client sees ActionNotify, before sending ActionREQ.

    Human-like spread: trivial decisions shorter, raises / big pots / later streets longer.
    Always capped at _MAX_INJECT_DELAY (default 3s).
    """
    action = (decision.action or "").lower()
    bb = float(big_blind) if big_blind and big_blind > 0 else 100.0
    pot_bb = pot_chips / bb

    if action == "fold":
        lo, hi = 0.35, 1.15
    elif action == "check":
        lo, hi = 0.5, 1.45
    elif action == "call":
        lo, hi = 0.7, 2.05
    elif action == "raise":
        lo, hi = 1.05, 2.75
    else:
        lo, hi = 0.5, 1.4

    if street != "preflop":
        lo += 0.08
        hi += 0.12
    if pot_bb >= 25:
        lo += 0.1
        hi += 0.18
    if pot_bb >= 60:
        lo += 0.08
        hi += 0.12

    hi = min(hi, _MAX_INJECT_DELAY)
    lo = min(lo, hi - 0.05)
    lo = max(0.0, lo)
    sec = random.uniform(lo, hi)
    return min(_MAX_INJECT_DELAY, max(0.0, sec))


def _clamp_inject_delay(result: WireInjectResult, max_delay: float) -> WireInjectResult:
    """Clamp delayed bot injections when reconnect leaves little action time."""
    max_delay = max(0.0, float(max_delay))
    if result is None:
        return None
    if isinstance(result, list):
        return [_clamp_inject_delay(item, max_delay) for item in result if item is not None]
    if isinstance(result, tuple) and len(result) == 3:
        inject_type, fields, delay_sec = result
        return inject_type, fields, min(float(delay_sec), max_delay)
    return result


def _seat_status_has_player(seat_status: dict) -> bool:
    player = seat_status.get("player") or {}
    uid = player.get("uid")
    if uid is not None:
        try:
            return int(uid) > 0
        except (TypeError, ValueError):
            return bool(str(uid).strip())
    if seat_status.get("has_card") is True:
        return True
    return _chip_int(seat_status.get("hand_chips", 0), 0) > 0

# ── Card conversion ────────────────────────────────────────────────────────────

_RANK_TO_STR = {
    2: '2', 3: '3', 4: '4', 5: '5', 6: '6',
    7: '7', 8: '8', 9: '9', 10: 'T',
    11: 'J', 12: 'Q', 13: 'K', 14: 'A',
}
_SUIT_TO_STR = {
    1: 'd', 2: 'c', 3: 'h', 4: 's',
    0: 'd',  # compatibility fallback for old captures
}


def _card_str(code: int) -> str | None:
    """Game card code → pokerfate card string (e.g. 'As', 'Td')."""
    rank = _RANK_TO_STR.get(code % 256)
    suit = _SUIT_TO_STR.get(code // 256)
    if rank is None or suit is None:
        return None
    return rank + suit


# ── Constants ──────────────────────────────────────────────────────────────────

_STAGE_TO_STREET = {1: "preflop", 2: "flop", 3: "turn", 4: "river"}
# Client GF.isTournament (SNG holdem/omaha/train + MTT) plus friend SNG.
_TOURNAMENT_GAME_TYPES = {10050301, 10060301, 40050301, 10070401, 20050302}
_FRIEND_GAME_TYPES = {20010103}
# Frames still handled while seated in a tournament room: identity + room
# detection only, so leaving the tournament can be noticed.
_TOURNAMENT_PASSTHROUGH_TYPES = frozenset({"pb.SelfUserInfoRSP", "pb.EnterRoomRSP"})


def _is_tournament_enter_room(msg: dict) -> bool:
    if _chip_int(msg.get("game_type"), 0) in _TOURNAMENT_GAME_TYPES:
        return True
    return bool(msg.get("sngroom_info") or msg.get("mttroom_info"))


def _is_friend_game_type(game_type) -> bool:
    return _chip_int(game_type, 0) in _FRIEND_GAME_TYPES


def _chip_int(value, default: int = 0) -> int:
    """
    Parse protobuf int64-like values that may arrive as int/str.
    """
    try:
        if value is None:
            return default
        return int(value)
    except (TypeError, ValueError, OverflowError) as exc:
        log.warning(
            "[BOT] bad chip int value=%r default=%r (%s: %s)",
            value, default, type(exc).__name__, exc,
        )
        return default


def _chip_float(value, default: float = 0.0) -> float:
    """Parse protobuf numeric values that may arrive as int/float/str."""
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        log.warning(
            "[BOT] bad chip float value=%r default=%r (%s: %s)",
            value, default, type(exc).__name__, exc,
        )
        return default


def _s2c_rsp_code(msg: dict, default_if_omitted: int = 0) -> int:
    """
    int32 `code` on *RSP messages: json_format often omits the field when it equals
    the proto default (0 = success). Treat missing key as default_if_omitted.
    """
    if "code" not in msg:
        return default_if_omitted
    return _chip_int(msg.get("code"), default_if_omitted)


# ── BotBridge ─────────────────────────────────────────────────────────────────

def _live_decision(rec: dict, game_id: str) -> dict:
    """The part of a strategy decision record the live page shows.

    engine: flop_book / realtime_cfr / rule_engine; mode: how the equity was
    computed; why: the first line of the engine's own reasoning.  Amounts stay in chips.
    """
    def num(key):
        value = rec.get(key)
        return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None

    return {
        "game_id": game_id,
        "street": str(rec.get("street") or ""),
        "action": str(rec.get("action") or "").lower(),
        "amount": num("amount") or 0.0,
        "to_call": num("to_call") or 0.0,
        "pot": num("pot") or 0.0,
        "equity": num("equity"),
        "equity_random": num("equity_random"),
        "spr": num("spr"),
        "engine": str(rec.get("decision_source") or ""),
        "mode": str(rec.get("equity_mode") or ""),
        "ms": num("elapsed_ms"),
        "why": str(rec.get("reasoning") or "").split("\n", 1)[0].strip()[:240],
    }


class BotBridge:
    """
    Stateful bridge between the proxy event stream and PokerFateAPI.

    Seat ID and blind sizes are auto-detected from game messages.
    PokerFateAPI is created lazily once those values are known.

    Call handle(type_name, msg) for every decoded S2C frame.
    Returns one or more C2S injections:
      (proto_name, fields), (proto_name, fields, delay_sec), a list of those,
      or None.
    """

    def __init__(self, max_auto_rebuy: int = 1) -> None:
        # Detected from game messages (may be pre-seeded by config)
        self._my_seat: int | None  = None
        self._my_uid:  str | None  = None
        self._bb:      float | None = config.BIG_BLIND
        self._sb:      float | None = config.SMALL_BLIND

        self._api: PokerFateAPI | None = None   # created once blinds are known

        # 净亏损上限：本次启动最多净亏 (1 + _max_auto_rebuy) 个 100BB 买入（_loss_cap_chips）。
        # 所有把筹码带上桌的动作（破产买入、桌上补码、换桌或异常离桌后的重新买入）都先过
        # _loss_room 这一条：已亏的 + 桌上的 + 要带的不超过上限。不再单独数破产买入的次数，
        # 盈利锁仓也不再把上限 +1：赢到的已经在净盈亏里。
        # _auto_rebuy_done：本次启动破产买入了几次，只用于展示。
        # _loss_stop：上限下连最小一档买入都放不下了，本次启动到此为止，停在大厅。
        self._max_auto_rebuy: int = max(0, min(20, int(max_auto_rebuy)))  # 0 = 净亏一个买入即停
        self._auto_rebuy_done: int = 0
        self._loss_stop: bool = False
        self._auto_rejoin_fields: dict | None = None
        self._shutdown_requested = False
        self._transport_can_match: bool | None = None

        # 盈利锁仓：WinnerRSP 达标后立刻设置服务端「下一手离桌」
        # DelayLeaveRoomREQ；真正 LeaveRoomRSP 成功后再采样余额并 EnterRoom（100BB）。
        self._profit_lock_deferred: dict[str, int | str | bool | None] | None = None
        self._profit_lock_reenter: dict[str, int | str | bool | None] | None = None
        self._profit_lock_awaiting_enter: bool = False
        # 最近一次注入的 EnterRoomREQ 字段（失败时打日志 / 人工对照）
        self._profit_lock_last_enter_fields: dict | None = None
        # 资金看板记三本互不相干的账：
        #   对局盈亏  服务端每手结算（WinnerRSP.profit）里自己那一项的累计，每手只记一次；
        #   活动奖励  领取成功的筹码；
        #   小游戏    每局的净输赢。
        # 钱包余额和桌上筹码只按原样展示，不用来倒推对局盈亏：倒推时任何一笔奖励或
        # 小游戏的金额不明，对局盈亏就跟着不明。
        self._bankroll_login_sample_requested: bool = False
        self._bankroll_base_total_chips: int | None = None
        self._bankroll_base_at: float | None = None
        self._session_poker_pnl = 0
        self._settled_hands: set[str] = set()
        self._sidegame_net = 0
        self._bankroll_reward_chips = 0
        self._bankroll_rewards_uncertain = False
        self._bankroll_wallet_chips: int | None = None
        self._bankroll_last_total_chips: int | None = None
        self._bankroll_last_sample_at: float | None = None
        self._bankroll_samples: list[dict] = []
        self._bankroll_hand_points: list[dict] = []
        self._bankroll_buyin_seq: int = 0
        self._bankroll_pending_buyin_reason: str = ""
        self._bankroll_pending_action: dict | None = None
        self._bankroll_pending_reason: str = ""
        self._bankroll_profit_lock_count: int = 0
        # 桌上补码（config.TOPUP_BELOW_BB）：已发出、还没到账的请求；被拒后到哪一手再试。
        self._topup_pending: dict | None = None
        self._topup_retry_hand: int = 0
        self._topup_budget_logged: bool = False
        self._topup_count: int = 0
        self._topup_chips_total: int = 0
        # 从最近一次成功进房 RSP 缓存，供 QuickStart 兜底（与客户端大厅一致）
        self._session_game_type: int = 0
        self._session_lobby_coin: int = 0
        # SNG/MTT: player takes over; bridge ignores everything except room detection.
        self._tournament_passthrough: bool = False
        self._is_friend_room: bool = False
        self._skip_profit_lock: bool = False
        self._skip_profit_lock_reason: str = ""
        self._skip_runtime_collection: bool = False
        self._skip_runtime_collection_reason: str = ""

        # C2S 帧里的 room_id 须与客户端 Net.packNetData 一致（GameModel:getRoomId）。
        # 部分 S2C（如 WinnerRSP）wire 上 room_id 可能为 0，要用进房时或任意非 0 帧补全。
        self._table_room_id: int = 0
        self._current_gameid: str = ""
        # This hand's decisions for the live page.  A tuple swapped whole, so the web can read
        # it without the bridge lock while a decision is being made.
        self.live_decisions: tuple[dict, ...] = ()
        self._hand_seq: int = 0
        self._pending_injects: list[WireInject] = []
        self._last_hero_action_notify_sig: tuple | None = None
        self._last_hero_action_notify_at: float = 0.0
        self._pending_hero_wire_action: dict | None = None
        self._last_hero_action_context: dict | None = None

        # Only successful, validated responses count as fetched.
        self._fetched_uids: set[str] = set()
        self._gamedata_inflight: set[str] = set()
        self._gamedata_retry_at: dict[str, float] = {}
        self._gamedata_lock = threading.RLock()
        self._gamedata_session: GameDataHTTPContext | None = None
        self._gamedata_failed_auth: GameDataHTTPContext | None = None
        self._gamedata_closed = False
        # 在 API 创建前到达的 server stats，缓存至 _ensure_api 创建后再注入
        self._pending_seeds: dict[int, dict] = {}   # uid -> {"data": raw stats, "name": display name}

        # GameData 无历史数据通知（每次 proxy 进程启动只发一次）
        self._gamedata_no_history_notified: bool = False
        self._gamedata_threads: set[threading.Thread] = set()

        # Session-level: real player names keyed by seat_id
        # Populated from EnterRoomRSP.table_status.seat[].player.name
        # and updated on SitDownBRC
        self._seat_names: dict[int, str] = {}
        # uid (str) → seat_id; built from EnterRoomRSP/SitDownBRC; used to
        # resolve WinnerRSP entries that carry uid but no seatid.
        self._uid_to_seat: dict[str, int] = {}
        self._seat_uids: dict[int, str] = {}

        # Per-hand state
        self._stage:    int       = 0
        self._pot:      int       = 0
        self._my_bet:   int       = 0   # my chips in this street
        self._max_bet:  int       = 0   # highest bet this street
        self._my_chips: int       = 0
        self._street_bets: dict[int, int] = {}
        # seat -> pre_action_result of its latest "your turn" notice, until its action arrives
        self._pre_action_flags: dict[int, int] = {}
        self._my_forced_post_this_street: bool = False
        self._folded:   set[int]  = set()
        self._all_seats: list[int] = []
        self._all_board_missing_logged: bool = False  # 缺 all_board 的错误每个 bridge 只报一次
        # Track each seat's remaining chips (for final_stacks on hand_over)
        # Initialised from DealerInfoRSP.start_info, updated on every ActionBRC
        self._seat_chips: dict[int, int] = {}
        # Snapshot of chips at hand start (from DealerInfoRSP.start_info)
        # Used with WinnerRSP.profit to compute authoritative final_stacks
        self._hand_start_chips: dict[int, int] = {}
        self._hole_cards_count: int = 0
        # Showdown data accumulated between ShowHandRSP and WinnerRSP
        self._pending_showdown: dict[int, list[str]] = {}   # seat → [card_str, ...]
        self._pending_winner_types: dict[int, int] = {}     # seat → server hand type int

        self._calibration_backpressure_leaving: bool = False

        # 人机识别：服务端 rb_num 计数 → 逐账号标签（pokerfate/core/robots.py）。
        # 选桌：桌上没有真人、或真人少于人机时离桌换桌 / 换场（table_policy.py）。
        # 策略只在 headless 显式 configure_table_policy 后生效；识别始终运行。
        self._robots = default_registry()
        self._room_tracker = RoomRobotTracker(
            self._robots, None, on_label=self._on_robot_label, on_mismatch=self._on_robot_count_mismatch,
        )
        self._table_policy: TablePolicy | None = None
        self._table_switch: dict | None = None      # 选桌发起的离桌，等待 LeaveRoomRSP
        self._table_log_path: Path | None = _TABLE_LOG_PATH

    # ── Public ────────────────────────────────────────────────────────────────

    def runtime_settings(self) -> dict:
        """Bridge state the proxy process reads (it runs the bot in a worker and gets this with
        every snapshot): whether an SNG/MTT table is being played by hand."""
        return {"tournament_passthrough": self._tournament_passthrough}

    def bankroll_dashboard(self) -> dict:
        """Current bankroll snapshot for the local Web UI."""
        wallet = self._bankroll_wallet_chips
        table_chips = self._current_table_chips()
        current_total = (int(wallet) + table_chips) if wallet is not None else None
        base_total = self._bankroll_base_total_chips
        delta = self._session_poker_pnl
        bb = float(self._bb or 0.0)
        return {
            "wallet_chips": wallet,
            "table_chips": table_chips,
            "current_total_chips": current_total,
            "base_total_chips": base_total,
            "session_delta_chips": delta,
            "session_delta_bb": (delta / bb) if bb > 0 else None,
            "reward_chips": self._bankroll_reward_chips,
            "rewards_uncertain": self._bankroll_rewards_uncertain,
            "sidegame_net_chips": self._sidegame_net,
            "big_blind": bb if bb > 0 else None,
            "auto_rebuy_count": self._auto_rebuy_done,
            "max_auto_rebuy": self._max_auto_rebuy,
            "loss_cap_chips": self._loss_cap_chips(),
            "loss_stop": self._loss_stop,
            "profit_lock_count": self._bankroll_profit_lock_count,
            "topup_count": self._topup_count,
            "topup_chips": self._topup_chips_total,
            "last_sample_at": self._bankroll_last_sample_at,
            "base_at": self._bankroll_base_at,
            "pending_reason": self._bankroll_pending_reason or None,
            "samples": list(self._bankroll_samples),
            "hand_points": list(self._bankroll_hand_points),
        }

    def record_reward_credit(self, chips: int, uncertain: bool = False) -> None:
        """Count a claimed reward. ``uncertain``: a claim or side-game round whose amount is unknown.

        Rewards and side games have their own totals; neither enters the poker PnL.
        """
        self._bankroll_reward_chips += max(0, int(chips))
        self._bankroll_rewards_uncertain |= uncertain

    def record_sidegame_result(self, net: int) -> None:
        self._sidegame_net += int(net)

    def _settle_my_hand(self, msg: dict) -> None:
        """Add our net result of this hand, as the server settled it, to the session's poker PnL."""
        if not self._my_uid:
            return
        mine = next((p for p in msg.get("profit") or []
                     if isinstance(p, dict) and str(p.get("uid", "")) == self._my_uid), None)
        if mine is None:
            return
        # A settlement replayed after a reconnect or a room snapshot counts once.
        hand = str(self._current_gameid or "") or f"hand#{self._hand_seq}"
        if hand in self._settled_hands:
            return
        self._settled_hands.add(hand)
        self._session_poker_pnl += _chip_int(mine.get("chips", 0), 0)

    def activity_emoji_target(self):
        for seat in self._all_seats:
            uid = self._seat_uids.get(seat)
            if seat != self._my_seat and uid and int(uid) > 0 and str(uid) != self._my_uid:
                return int(uid)
        return None

    def _apply_preflop_sticky_pool_adjust(self, enabled: bool) -> None:
        api_bot = getattr(self._api, "_bot", None) if self._api is not None else None
        preflop = getattr(api_bot, "preflop", None)
        if preflop is not None:
            preflop.sticky_pool_adjust = bool(enabled)

    def note_seen_room_id(self, room_id: int) -> None:
        """Update cached table room id from any S2C frame header (non-zero only)."""
        rid = _chip_int(room_id, 0)
        if rid != 0:
            self._table_room_id = rid

    def configure_auto_rejoin(self, fields: dict) -> None:
        """Only headless cash matchmaking opts into unexpected-leave recovery."""
        self._auto_rejoin_fields = dict(fields)

    def set_session_uid(self, uid: int) -> None:
        # Login supplies identity before a possibly delayed SelfUserInfoRSP;
        # an early room snapshot must still identify our seat correctly.
        self._my_uid = str(uid)
        self._room_tracker.set_my_uid(uid)

    def stop_auto_rejoin(self) -> None:
        self._shutdown_requested = True

    def prepare_transport_reconnect(self) -> None:
        """Forget ambiguous outbound work, retaining run counters and models."""
        pending_kind = (self._bankroll_pending_action or {}).get("kind")
        if self._transport_can_match is None:
            self._transport_can_match = (
                (self._my_seat is None or self._current_table_chips() > 0
                 or pending_kind in {"unexpected_leave", "profit_lock"}
                 or self._bankroll_pending_buyin_reason in {"unexpected_leave", "profit_lock", "table_switch"})
                and not self._shutdown_requested and not self._is_friend_room
                and not self._tournament_passthrough and not self._calibration_backpressure_leaving
                and not (self._table_policy is not None and self._table_policy.stopped)
            )
        self._table_switch = None
        if self._table_policy is not None:
            self._table_policy.on_transport_reset()
        self._pending_injects.clear()
        self._pending_hero_wire_action = None
        self._last_hero_action_notify_sig = None
        self._last_hero_action_notify_at = 0.0
        self._profit_lock_cancel_reenter()
        self._topup_pending = None
        self._bankroll_pending_action = None
        self._bankroll_pending_reason = ""
        self._bankroll_pending_buyin_reason = ""

    def restore_lobby_after_disconnect(self) -> bool:
        """Authoritative UserLocationRSP says lobby; don't revive busted seats."""
        allowed = self._transport_can_match
        self._transport_can_match = None
        if allowed is None:
            allowed = self._my_seat is None or self._current_table_chips() > 0
        self._mark_my_table_chips_zero()
        self._table_room_id = 0
        self._current_gameid = ""
        self._reset_hand_local_state(stage=0)
        if allowed and not self._loss_stop and self._auto_rejoin_fields:
            self.cap_match_buyin(self._auto_rejoin_fields)      # ends the start if nothing fits
        return bool(allowed and not self._shutdown_requested and not self._loss_stop
                    and not self._is_friend_room and not self._tournament_passthrough
                    and not (self._table_policy is not None and self._table_policy.stopped)
                    and self._runtime_calibration_should_pause_play() is None)

    def room_id_for_c2s(self, frame_room_id: int) -> int:
        """room_id to attach to injected C2S (match client Net.packNetData)."""
        fr = _chip_int(frame_room_id, 0)
        if fr != 0:
            return fr
        return _chip_int(self._table_room_id, 0)

    def notify_inject_failed(self, inject_type: str) -> None:
        """Proxy could not serialize/send a C2S frame — drop dependent bot state."""
        if inject_type in {"pb.LeaveRoomREQ", "pb.DelayLeaveRoomREQ"} and (
            self._profit_lock_reenter is not None
            or self._profit_lock_deferred is not None
        ):
            log.warning("[BOT] %s 未发出，已取消对应离桌后续。", inject_type)
            self._profit_lock_cancel_reenter()
        elif inject_type == "pb.EnterRoomREQ" and self._profit_lock_awaiting_enter:
            log.warning("[BOT] 盈利锁仓：EnterRoom 未发出。")
            self._profit_lock_awaiting_enter = False
            self._profit_lock_last_enter_fields = None
        elif inject_type == "pb.QuickStartREQ":
            log.warning("[BOT] 盈利锁仓：QuickStartREQ 编码/发送失败，请手动从大厅进桌。")
        elif inject_type == "pb.SetRebyREQ" and self._topup_pending is not None:
            log.warning("[BOT] 桌上补码：SetRebyREQ 未发出，%d 手后再试。", _TOPUP_RETRY_HANDS)
            self._topup_pending = None
            self._topup_retry_hand = self._hand_seq + _TOPUP_RETRY_HANDS
        elif inject_type == "pb.UserValueREQ" and self._bankroll_pending_action is not None:
            log.warning(
                "[BOT] 余额采样请求未发出，取消待完成动作：%s",
                self._bankroll_pending_action.get("kind"),
            )
            self._bankroll_pending_action = None
            self._bankroll_pending_reason = ""

    # ── 人机识别 / 选桌 ───────────────────────────────────────────────────────

    def configure_table_policy(self, cfg: TablePolicyConfig | None) -> None:
        """Enable table selection (headless cash play). ``None`` turns it off."""
        self._table_policy = TablePolicy(cfg) if cfg is not None else None
        self._table_switch = None
        if cfg is not None:
            log.warning(
                "[BOT] 选桌已启用：没有真人或真人少于人机即换桌；场次顺序 %s，每场最多 %d 次，"
                "等大盲入座=%s",
                list(cfg.ladder), cfg.tries_per_stake, cfg.wait_blind,
            )

    def wants_tick(self) -> bool:
        return self._table_policy is not None

    def adjust_match_fields(self, fields: dict) -> dict:
        """Let the table policy pick stake / buy-in / wait-for-blind of a QuickStart."""
        if self._table_policy is None:
            return dict(fields)
        return self._table_policy.match_fields(fields)

    def cap_match_buyin(self, fields: dict) -> dict:
        """Keep the buy-in of a QuickStart under the loss cap of this start.

        Returns a copy; ``byin_chips`` 0 means not even the smallest buy-in fits: the caller
        must not send the request, and the start has been stopped.
        """
        out = dict(fields)
        want = _chip_int(out.get("byin_chips", 0), 0)
        bb = float(_chip_int(out.get("boot", 0), 0) or self._bb or 0.0)
        got = self._capped_buyin(want, bb)
        if got == want:
            return out
        out["byin_chips"] = got
        if got <= 0:
            self._stop_for_loss_cap("重新买入")
        else:
            log.warning(
                "[BOT] 净亏损上限：本次启动已亏 %d，上限 %d，买入从 %d 减到 %d（%.0fBB）。",
                max(0, -int(self._session_poker_pnl)), self._loss_cap_chips(bb), want, got,
                got / bb if bb > 0 else 0.0,
            )
        return out

    def note_match_sent(self) -> None:
        if self._table_policy is not None:
            self._table_policy.on_match_sent(time.time())

    def _on_robot_label(self, uid: str, label: str, how: str) -> None:
        log.info("[BOT] 人机识别：uid=%s → %s（%s）名单 %s", uid, label, how, self._robots.counts())

    def _on_robot_count_mismatch(self, members: list, rb_num: int) -> None:
        """The server's robot count cannot be true of the labels held for the people in the
        room, so one of those labels is wrong: put it on record."""
        self._table_log("robot_count_mismatch", rb_num=int(rb_num), members=list(members))

    def _table_composition(self) -> dict:
        return self._room_tracker.composition(self._room_tracker.members)

    def _table_policy_blocked(self) -> bool:
        """Other leave / re-enter flows own the table right now, or we must not act."""
        return (
            self._table_policy is None
            or self._shutdown_requested
            or self._loss_stop
            or self._tournament_passthrough
            or self._is_friend_room
            or self._profit_lock_reenter is not None
            or self._profit_lock_deferred is not None
            or self._calibration_backpressure_leaving
        )

    def _table_log(self, event: str, **fields) -> None:
        comp = self._table_composition()
        rec = {
            "ts": round(time.time(), 3), "event": event,
            "room": _chip_int(self._table_room_id, 0), "bb": int(self._bb or 0),
            "humans": comp["humans"], "robots": comp["robots"], "source": comp["source"],
            "unproven": comp["unproven"],
            "seated": {u: self._robots.status(u) for u in sorted(self._room_tracker.members)},
            **fields,
        }
        log.warning("[BOT] 选桌 %s：room=%s bb=%s 真人=%d 人机=%d（%s）%s", event, rec["room"], rec["bb"],
                    rec["humans"], rec["robots"], rec["source"],
                    {k: v for k, v in fields.items() if k != "info"})
        if self._table_log_path is None:
            return
        try:
            self._table_log_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._table_log_path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
        except OSError:
            log.debug("[BOT] 选桌日志写入失败", exc_info=True)

    def _table_step(self, step: Step) -> WireInject | None:
        """Turn a policy step into the wire request that carries it out."""
        if not step:
            return None
        if step.kind == "leave":
            # ``played``: we were dealt in at this table, so leaving it ends a stretch of play
            # (a table rejected on arrival is not one).  A retry of an unanswered leave keeps
            # what the first request recorded.
            first = self._table_switch if step.reason == "retry" and self._table_switch else None
            self._table_switch = {
                "mode": "delay" if step.delayed else "leave", "reason": step.reason, "at": time.time(),
                "cause": first["cause"] if first else step.reason,
                "played": first["played"] if first else not step.info.get("rejected", True),
            }
            self._table_log("leave", reason=step.reason, delayed=bool(step.delayed))
            if self._api:
                self._api._log.note(f"[选桌] 离桌换桌：{step.reason}")
            if step.delayed:
                return "pb.DelayLeaveRoomREQ", {"flag": True}, 0.0
            return "pb.LeaveRoomREQ", {"seat_reserve": False, "is_switch_room": True}, 0.0
        if step.kind == "match":
            pause = self._runtime_calibration_should_pause_play()
            if pause is not None or self._shutdown_requested:
                log.warning("[BOT] 选桌：暂不匹配（%s）", "校准队列积压" if pause is not None else "正在停止")
                return None
            fields = self._table_match_fields(int(step.bb))
            if fields is None:
                return None
            self._auto_rejoin_fields = dict(fields)
            # 换桌带上桌的筹码也算在净亏损上限里：正在亏的时候最多带回离桌时的筹码量。
            fields = self.cap_match_buyin(fields)
            if _chip_int(fields.get("byin_chips", 0), 0) <= 0:
                return None
            self._bankroll_pending_buyin_reason = "table_switch"
            self._table_log("match", stake=int(step.bb), byin=int(fields.get("byin_chips", 0)))
            return "pb.QuickStartREQ", fields, 0.0
        if step.kind == "stop":
            self._table_log("stop", reason=step.reason)
            policy = self._table_policy
            self._notify(
                "codex_done",
                title="选桌 · 找不到有真人的牌桌，已停止",
                body=(f"场次 {list(policy.cfg.ladder) if policy else []} 每个都连续 "
                      f"{policy.cfg.max_fail_rounds if policy else 0} 轮没有合格的牌桌，"
                      "已停在大厅，不再匹配。重启后恢复。"),
            )
        return None

    def _table_match_fields(self, bb: int) -> dict | None:
        if bb <= 0 or self._table_policy is None:
            return None
        base = dict(self._auto_rejoin_fields or {})
        fields = {
            "boot": int(bb),
            "game_type": _chip_int(base.get("game_type"), 0) or self._session_game_type
            or int(config.PROFIT_LOCK_FALLBACK_GAME_TYPE),
            "lobby_coin": _chip_int(base.get("lobby_coin"), 0) or self._session_lobby_coin
            or int(config.PROFIT_LOCK_FALLBACK_LOBBY_COIN),
            "byin_chips": int(bb) * int(self._table_policy.cfg.buyin_bb),
            "wait_blind": bool(self._table_policy.cfg.wait_blind),
            "ip": str(base.get("ip", "") or ""),
        }
        return fields

    def _table_event(self, kind: str) -> WireInject | None:
        """Composition may have changed: ask the policy what to do."""
        if self._table_policy_blocked() or self._table_switch is not None:
            return None
        comp = self._table_composition()
        now = time.time()
        if kind == "hand_end":
            step = self._table_policy.on_hand_end(comp["humans"], comp["robots"], now)
        else:
            step = self._table_policy.on_seats_changed(comp["humans"], comp["robots"], now)
        return self._table_step(step)

    def _on_tick(self, msg: dict) -> WireInject | None:
        if self._table_policy is None or self._shutdown_requested:
            return None
        self._robots.save()
        if self._table_policy_blocked():
            return None
        now = float(msg.get("now") or time.time())
        comp = self._table_composition()
        return self._table_step(self._table_policy.on_tick(now, comp["humans"], comp["robots"]))

    def _on_quick_start_rsp(self, msg: dict) -> WireInject | None:
        code = _s2c_rsp_code(msg, 0)
        if code == 0 or self._table_policy is None:
            return None
        log.warning("[BOT] 选桌：QuickStartRSP code=%s，该场次本次运行不再尝试。", code)
        return self._table_step(self._table_policy.on_match_failed(code, time.time()))

    def _on_other_enter_room_brc(self, msg: dict) -> WireInject | None:
        """Somebody entered the room.  This broadcast carries no robot count; only the one
        for somebody leaving does."""
        user = msg.get("user") or {}
        uid = user.get("uid")
        if uid is None or (self._my_uid is not None and str(uid) == str(self._my_uid)):
            return None
        self._room_tracker.entered(uid)
        return self._table_event("seats")

    def _profit_lock_cancel_reenter(self) -> None:
        self._profit_lock_deferred = None
        self._profit_lock_reenter = None
        self._profit_lock_awaiting_enter = False
        self._profit_lock_last_enter_fields = None

    def _bankroll_prop_type(self) -> int:
        return int(config.PROFIT_LOCK_FALLBACK_LOBBY_COIN)

    def _current_table_chips(self) -> int:
        if self._my_seat is not None:
            return max(0, _chip_int(self._seat_chips.get(self._my_seat, self._my_chips), 0))
        return max(0, _chip_int(self._my_chips, 0))

    def _mark_my_table_chips_zero(self) -> None:
        self._my_chips = 0
        if self._my_seat is not None:
            self._seat_chips[self._my_seat] = 0

    def _mark_my_left_table(self, reason: str) -> WireInject | None:
        """Clear stale on-table chips after the server confirms hero left/stood up."""
        before = self._current_table_chips()
        self._mark_my_table_chips_zero()
        self._topup_pending = None
        if before > 0:
            log.info("[BOT] 资金看板：%s，桌上筹码 %d -> 0", reason, before)
        if self._bankroll_pending_action is not None or self._bankroll_pending_reason:
            log.debug(
                "[BOT] 余额采样：已有待处理请求 reason=%s action=%s，%s 不重复请求",
                self._bankroll_pending_reason or "-",
                (
                    self._bankroll_pending_action.get("kind")
                    if self._bankroll_pending_action else "-"
                ),
                reason,
            )
            return None
        return self._request_bankroll_sample(reason)

    def _request_bankroll_sample(
        self,
        reason: str,
        *,
        action: dict | None = None,
        delay_sec: float = 0.0,
    ) -> WireInject | None:
        if action is None and self._bankroll_pending_action is not None:
            log.debug(
                "[BOT] 余额采样：已有待完成动作 %s，跳过普通采样 reason=%s",
                self._bankroll_pending_action.get("kind"),
                reason,
            )
            return None
        if action is not None and self._bankroll_pending_action is not None:
            log.warning(
                "[BOT] 余额采样：覆盖未完成动作 %s → %s",
                self._bankroll_pending_action.get("kind"),
                action.get("kind"),
            )
        self._bankroll_pending_action = action
        self._bankroll_pending_reason = reason
        fields = {"type": self._bankroll_prop_type()}
        log.info("[BOT] 余额采样：请求 UserValueREQ reason=%s action=%s", reason, action.get("kind") if action else "-")
        return "pb.UserValueREQ", fields, max(0.0, float(delay_sec))

    def _record_bankroll_sample(self, reason: str, wallet_chips: int) -> dict:
        now = time.time()
        wallet = max(0, int(wallet_chips))
        table = self._current_table_chips()
        total = wallet + table
        if self._bankroll_base_total_chips is None:
            self._bankroll_base_total_chips = total
            self._bankroll_base_at = now
            reason = "startup" if reason == "refresh" else reason
        base = int(self._bankroll_base_total_chips)
        delta = self._session_poker_pnl
        bb = float(self._bb or 0.0)
        sample = {
            "ts": now,
            "reason": reason,
            "reason_text": _BANKROLL_REASONS.get(reason, reason),
            "wallet_chips": wallet,
            "table_chips": table,
            "total_chips": total,
            "base_total_chips": base,
            "reward_chips": self._bankroll_reward_chips,
            "delta_chips": delta,
            "delta_bb": (delta / bb) if bb > 0 else None,
            "big_blind": bb if bb > 0 else None,
        }
        self._bankroll_wallet_chips = wallet
        self._bankroll_last_total_chips = total
        self._bankroll_last_sample_at = now
        self._bankroll_samples.append(sample)
        if len(self._bankroll_samples) > _BANKROLL_SAMPLE_LIMIT:
            self._bankroll_samples = self._bankroll_samples[-_BANKROLL_SAMPLE_LIMIT:]
        log.info(
            "[BOT] 余额采样：%s wallet=%d table=%d total=%d 对局盈亏=%+d",
            sample["reason_text"],
            wallet,
            table,
            total,
            delta,
        )
        return sample

    def _note_bankroll_buyin(self, reason: str) -> None:
        reason = str(reason or "buyin")
        self._bankroll_buyin_seq += 1
        self._bankroll_pending_buyin_reason = ""
        log.info("[BOT] 资金看板：买入分段 #%d reason=%s", self._bankroll_buyin_seq, reason)

    def _record_bankroll_hand_point(self, final_stacks: dict[int, int], profit_delta: int) -> None:
        """Append one bankroll chart point at hand settlement.

        The wallet side only changes when UserValueRSP samples it. Between those
        samples, per-hand points use the latest wallet value plus authoritative
        WinnerRSP final table chips.
        """
        if self._my_seat is None or self._bankroll_wallet_chips is None:
            return
        if self._bankroll_base_total_chips is None:
            return
        if self._bankroll_buyin_seq <= 0:
            self._bankroll_buyin_seq = 1
        table = max(0, _chip_int(final_stacks.get(self._my_seat, self._my_chips), 0))
        wallet = max(0, int(self._bankroll_wallet_chips))
        total = wallet + table
        base = int(self._bankroll_base_total_chips)
        delta = self._session_poker_pnl
        bb = float(self._bb or 0.0)
        point = {
            "ts": time.time(),
            "kind": "hand",
            "reason": "hand",
            "reason_text": f"第 {self._hand_seq} 手",
            "hand_no": self._hand_seq,
            "gameid": str(self._current_gameid or ""),
            "wallet_chips": wallet,
            "table_chips": table,
            "total_chips": total,
            "base_total_chips": base,
            "reward_chips": self._bankroll_reward_chips,
            "delta_chips": delta,
            "delta_bb": (delta / bb) if bb > 0 else None,
            "hand_delta_chips": int(profit_delta),
            "hand_delta_bb": (int(profit_delta) / bb) if bb > 0 else None,
            "big_blind": bb if bb > 0 else None,
            "buyin_seq": self._bankroll_buyin_seq,
        }
        self._bankroll_hand_points.append(point)

    def _bankroll_notify_fields(self, sample: dict) -> dict:
        return {
            "current_total_chips": int(sample.get("total_chips", 0)),
            "wallet_chips": int(sample.get("wallet_chips", 0)),
            "table_chips": int(sample.get("table_chips", 0)),
            "session_delta_chips": int(sample.get("delta_chips", 0)),
            "session_delta_bb": sample.get("delta_bb"),
        }

    def _complete_bankroll_action(self, action: dict | None, sample: dict) -> WireInject | None:
        if action is None:
            return None
        kind = str(action.get("kind") or "")
        if self._shutdown_requested:
            return None
        if kind == "unexpected_leave":
            fields = self.cap_match_buyin(self.adjust_match_fields(dict(action["quickstart_fields"])))
            byin = _chip_int(fields.get("byin_chips", 0), 0)
            if byin <= 0:
                return None
            self._bankroll_pending_buyin_reason = "unexpected_leave"
            log.warning("[BOT] 异常离桌：余额已刷新，重新匹配，买入 %d。", byin)
            return "pb.QuickStartREQ", fields, 0.0
        if kind == "auto_rebuy":
            rebuy_chips = _chip_int(action.get("rebuy_chips", 0), 0)
            self._bankroll_pending_buyin_reason = "auto_rebuy"
            self._notify(
                "auto_rebuy",
                nth=_chip_int(action.get("nth", self._auto_rebuy_done), self._auto_rebuy_done),
                loss_cap_chips=self._loss_cap_chips(),
                rebuy_chips=rebuy_chips,
                balance_chips=0,
                rebuy_window_sec=_chip_int(action.get("rebuy_window_sec", 0), 0),
                **self._bankroll_notify_fields(sample),
            )
            log.warning(
                "[BOT] ⚠️  筹码清零！余额已采样，自动续入 %d 第 %d 次，rebuy 窗口 %d 秒。本次启动盈亏 %+d",
                rebuy_chips,
                _chip_int(action.get("nth", self._auto_rebuy_done), self._auto_rebuy_done),
                _chip_int(action.get("rebuy_window_sec", 0), 0),
                int(sample.get("delta_chips", 0)),
            )
            return "pb.RebyREQ", {"is_reby": True, "chips": rebuy_chips}, 0.0

        if kind == "profit_lock":
            self._bankroll_profit_lock_count += 1
            fields = dict(action.get("enter_fields") or {})
            delay = max(0.0, min(60.0, float(action.get("delay_sec", 0.0) or 0.0)))
            self._profit_lock_last_enter_fields = dict(fields)
            self._profit_lock_awaiting_enter = True
            self._bankroll_pending_buyin_reason = "profit_lock"
            self._notify(
                "profit_lock_trigger",
                stack_chips=_chip_int(action.get("table_chips", 0), 0),
                threshold_chips=_chip_int(action.get("threshold_chips", 0), 0),
                lock_bb=_chip_int(action.get("lock_bb", config.PROFIT_LOCK_BB_THRESHOLD), int(config.PROFIT_LOCK_BB_THRESHOLD)),
                room_id=_chip_int(action.get("room_id", 0), 0),
                big_blind=_chip_int(action.get("big_blind", 0), 0),
                **self._bankroll_notify_fields(sample),
            )
            log.info("[BOT] 盈利锁仓 [EnterRoomREQ 将发送] %s（%.1fs 后）", fields, delay)
            log.warning(
                "[BOT] 盈利锁仓：已离桌且余额已采样，%.1fs 后发 EnterRoomREQ roomid=%d byin_chips=%d。本次启动盈亏 %+d",
                delay,
                _chip_int(fields.get("roomid", 0), 0),
                _chip_int(fields.get("byin_chips", 0), 0),
                int(sample.get("delta_chips", 0)),
            )
            return "pb.EnterRoomREQ", fields, delay

        log.warning("[BOT] 余额采样：未知待完成动作 kind=%s action=%s", kind, action)
        return None

    def _drain_pending_injects(self, result: WireInjectResult) -> WireInjectResult:
        if not self._pending_injects:
            return result
        pending = self._pending_injects
        self._pending_injects = []
        if result is None:
            return pending
        if isinstance(result, list):
            return pending + result
        return pending + [result]

    def injection_guard_for(self, inject: WireInject) -> InjectGuard | None:
        inject_type = inject[0] if inject else ""
        if inject_type != "pb.ActionREQ":
            return None
        return (str(self._current_gameid or ""), int(self._hand_seq))

    def injection_guard_is_current(self, guard: InjectGuard | None) -> bool:
        if guard is None:
            return True
        gameid, hand_seq = guard
        if int(hand_seq) == int(self._hand_seq) and str(gameid) == str(self._current_gameid or ""):
            return True
        log.warning(
            "[BOT→S] skip stale ActionREQ guard_gameid=%s current_gameid=%s "
            "guard_hand=%s current_hand=%s",
            gameid or "<none>",
            self._current_gameid or "<none>",
            hand_seq,
            self._hand_seq,
        )
        return False

    def _notify(self, event: str, **fields) -> None:
        """Room-aware notification wrapper. Tournament/friend rooms stay quiet."""
        if self._tournament_passthrough:
            log.debug("[BOT] tournament room: skip notify event=%s", event)
            return
        if self._is_friend_room:
            log.debug("[BOT] friend room: skip notify event=%s", event)
            return
        notify(event, **fields)

    def _runtime_calibration_backpressure(self) -> dict:
        try:
            status = spool_backpressure_status()
        except Exception:
            log.exception("[BOT] 校准队列 backpressure 状态读取失败")
            return {"active": False}
        return status if isinstance(status, dict) else {"active": False}

    def _runtime_calibration_should_pause_play(self) -> dict | None:
        if self._skip_runtime_collection:
            return None
        status = self._runtime_calibration_backpressure()
        if not status.get("active"):
            return None
        return status

    def _leave_for_runtime_calibration_backpressure(self, status: dict) -> WireInject | None:
        if self._calibration_backpressure_leaving:
            log.info("[BOT] 校准队列积压：已在离桌流程中，跳过重复 LeaveRoomREQ。")
            return None
        self._calibration_backpressure_leaving = True
        self._profit_lock_cancel_reenter()
        self._profit_lock_deferred = None

        backlog_gb = float(status.get("backlog_gb", 0.0) or 0.0)
        pending = _chip_int(status.get("pending_count", 0), 0)
        processing = _chip_int(status.get("processing_count", 0), 0)
        pause_gb = float(status.get("pause_gb", 0.0) or 0.0)
        msg = (
            "[BOT] 校准队列积压：新一手开始时停止继续对局，"
            f"backlog={backlog_gb:.1f}GB pending={pending} processing={processing} "
            f"pause={pause_gb:.1f}GB；发送 LeaveRoomREQ，等待 worker 消费。"
        )
        log.warning(msg)
        if self._api:
            self._api._log.note(msg)
        self._notify(
            "codex_done",
            title="校准队列积压 · 停止新对局",
            body=(
                f"backlog={backlog_gb:.1f}GB\n"
                f"pending={pending} processing={processing}\n"
                "已在新一手开始时发 LeaveRoomREQ，不再 QuickStart/rebuy。"
            ),
        )
        return "pb.LeaveRoomREQ", {"seat_reserve": False}, 0.0

    def handle(self, type_name: str, msg: dict) -> WireInjectResult:
        """
        Process one decoded S2C frame.
        Returns one or more C2S injections after optional delay, else None.
        """
        try:
            return self._drain_pending_injects(self._dispatch(type_name, msg))
        except Exception:
            log.exception("[BOT] Error handling %s", type_name)
            return None

    # ── Dispatch ──────────────────────────────────────────────────────────────

    def _dispatch(self, type_name: str, msg: dict) -> WireInjectResult:
        if self._tournament_passthrough and type_name not in _TOURNAMENT_PASSTHROUGH_TYPES:
            return None
        if   type_name == "pb.UserLoginRSP":    return self._on_user_login_rsp(msg)
        elif type_name == "pb.SelfUserInfoRSP": self._on_self_user_info(msg)
        elif type_name == "pb.UserValueRSP":    return self._on_user_value_rsp(msg)
        elif type_name == "pb.SitDownRSP":      self._on_sit_down(msg)
        elif type_name == "pb.SitDownBRC":       return self._on_sit_down_brc(msg)
        elif type_name == "pb.OtherEnterRoomBRC": return self._on_other_enter_room_brc(msg)
        elif type_name == "pb.QuickStartRSP":    return self._on_quick_start_rsp(msg)
        elif type_name == "pf.Tick":             return self._on_tick(msg)
        elif type_name == "pb.StandUpRSP":      return self._on_stand_up_rsp(msg)
        elif type_name == "pb.StandUpBRC":      return self._on_stand_up_brc(msg)
        elif type_name == "pb.OtherLeaveRoomBRC":
            return self._on_other_leave_room_brc(msg)
        elif type_name == "pb.EnterRoomRSP":     return self._on_enter_room(msg)
        elif type_name == "pb.DealerInfoRSP":    return self._on_dealer_info(msg)
        elif type_name == "pb.HandCardRSP":      return self._on_hand_card(msg)
        elif type_name == "pb.RoundStartBRC":    self._on_round_start(msg)
        elif type_name == "pb.ActionBRC":        self._on_action_brc(msg)
        elif type_name == "pb.RoundOverBRC":     self._on_round_over(msg)
        elif type_name == "pb.ActionNotifyBRC":  return self._on_action_notify(msg)
        elif type_name == "pb.ShowHandRSP":      self._on_show_hand(msg)
        elif type_name == "pb.WinnerRSP":        return self._on_winner(msg)
        elif type_name == "pb.DelayLeaveRoomRSP": return self._on_delay_leave_room_rsp(msg)
        elif type_name == "pb.LeaveRoomRSP":     return self._on_leave_room_rsp(msg)
        elif type_name == "pb.NoticeRebyRSP":    return self._on_notice_reby(msg)
        elif type_name == "pb.RebyBRC":          self._on_reby_brc(msg)
        elif type_name == "pb.SetRebyRSP":       self._on_set_reby_rsp(msg)
        return None

    # ── Session setup ─────────────────────────────────────────────────────────

    def close(self) -> None:
        with self._gamedata_lock:
            self._gamedata_closed = True

    def _set_my_seat(self, seat: int, reason: str) -> None:
        if seat < 0:
            return
        if self._my_seat == seat:
            return
        old = self._my_seat
        self._my_seat = seat
        log.info("[BOT] My seat detected: %s -> %d (%s)", old, seat, reason)
        if (self._api is not None and self._my_uid
                and getattr(self._api, "my_player_id", None) == int(self._my_uid)):
            # Models are keyed by uid. Moving seats must not reload the entire
            # historical model while a new table is already dealing cards.
            return
        # Recreate API when seat changes (reconnect / table rejoin).
        self._api = None

    def _on_user_login_rsp(self, msg: dict) -> WireInject | None:
        code = _s2c_rsp_code(msg, 0)
        if code != 0:
            return None
        if self._bankroll_login_sample_requested:
            return None
        self._bankroll_login_sample_requested = True
        return self._request_bankroll_sample("startup")

    def _on_self_user_info(self, msg: dict) -> None:
        brief = msg.get("brief") or {}
        uid = brief.get("uid")
        if uid:
            self._my_uid = str(uid)
            self._room_tracker.set_my_uid(uid)
            log.info("[BOT] My uid detected: %s", self._my_uid)

    def _on_user_value_rsp(self, msg: dict) -> WireInject | None:
        prop_type = _chip_int(msg.get("type", self._bankroll_prop_type()), self._bankroll_prop_type())
        if prop_type != self._bankroll_prop_type():
            return None
        if "value" not in msg:
            log.debug("[BOT] UserValueRSP missing value: %s", msg)
            return None
        pending = self._bankroll_pending_action
        reason = self._bankroll_pending_reason
        self._bankroll_pending_action = None
        self._bankroll_pending_reason = ""
        if not reason:
            reason = "startup" if self._bankroll_base_total_chips is None else "refresh"
        sample = self._record_bankroll_sample(reason, _chip_int(msg.get("value", 0), 0))
        return self._complete_bankroll_action(pending, sample)

    def _on_sit_down(self, msg: dict) -> None:
        seat = _chip_int(msg.get("seatid", 0), 0)
        if "seatid" not in msg:
            log.debug("[BOT] SitDownRSP missing seatid; assume 0")
        self._set_my_seat(seat, "SitDownRSP")
        raw = msg.get("chips") or msg.get("hand_chips")
        if raw is not None:
            chips = _chip_int(raw, 0)
            self._seat_chips[seat] = chips
            self._hand_start_chips[seat] = chips
            if self._my_seat is not None and seat == self._my_seat:
                self._my_chips = chips
                if chips > 0 and self._bankroll_buyin_seq <= 0:
                    self._note_bankroll_buyin("sit_down")

    def _on_reby_brc(self, msg: dict) -> None:
        code = _s2c_rsp_code(msg, 0)
        if code != 0:
            return
        seat = _chip_int(msg.get("seatid", 0), 0)
        chips = _chip_int(msg.get("chips", 0), 0)
        current = _chip_int(self._seat_chips.get(seat, 0), 0)
        self._seat_chips[seat] = max(0, current + chips)
        if self._my_seat is not None and seat == self._my_seat:
            self._my_chips = self._seat_chips[seat]
            if chips > 0:
                kind = str(msg.get("type") or "")
                if kind == "topup" or (not kind and self._topup_pending is not None):
                    self._on_my_topup(chips)
                else:
                    self._note_bankroll_buyin(self._bankroll_pending_buyin_reason or "reby")

    # ── 桌上补码 ──────────────────────────────────────────────────────────────

    # ── 净亏损上限 ────────────────────────────────────────────────────────────
    #
    # One number ends a start: its net loss may not pass (1 + _max_auto_rebuy) buy-ins of 100BB.
    # Everything that brings chips to a table is checked against it — a top-up, a bust rebuy, the
    # buy-in after a table switch or an unexpected leave — so what is lost plus what is on the
    # table never exceeds the cap, whichever way the chips arrived.  Winnings need no rule of
    # their own: they are in the net result and make room by themselves.
    #
    # A profit-lock re-entry is not checked: it takes at least the threshold off the table and
    # brings 100BB back, so it can only lower what is at risk.

    def _loss_cap_bb(self, fallback: float = 0.0) -> float:
        """The blind the cap is counted in: the stake the start was launched for, else the table's."""
        cfg = getattr(self._table_policy, "cfg", None)
        home = float(getattr(cfg, "home_bb", 0) or 0.0)
        return home or float(self._bb or 0.0) or float(fallback or 0.0)

    def _loss_cap_chips(self, fallback_bb: float = 0.0) -> int:
        """The most this start may lose, in chips; 0 while no blind is known yet."""
        return (1 + self._max_auto_rebuy) * int(_BUYIN_BB * self._loss_cap_bb(fallback_bb))

    def _loss_room(self, table_chips: int = 0, fallback_bb: float = 0.0) -> int:
        """Chips that may still be brought to the table: the cap less what is lost and what sits there."""
        cap = self._loss_cap_chips(fallback_bb)
        return cap - max(0, -int(self._session_poker_pnl)) - max(0, int(table_chips))

    def _capped_buyin(self, want: int, bb: float) -> int:
        """What a buy-in of ``want`` chips at blind ``bb`` may bring after leaving a table or busting.

        ``want`` when the cap has room for it, else the largest amount the client's buy-in slider
        offers that fits (the same slider serves buy-in, rebuy and top-up); 0 when none does.
        """
        want = max(0, int(want))
        if bb <= 0 or self._loss_cap_chips(bb) <= 0:
            return want
        room = self._loss_room(0, bb)
        if want <= room:
            return want
        return max((int(s * bb) for s in _TOPUP_STEPS_BB if int(s * bb) <= room), default=0)

    def _stop_for_loss_cap(self, what: str) -> None:
        """The cap leaves no room for even the smallest buy-in: this start plays no more hands."""
        if self._loss_stop:
            return
        self._loss_stop = True
        self._topup_pending = None
        lost, cap = max(0, -int(self._session_poker_pnl)), self._loss_cap_chips()
        log.warning(
            "[BOT] 净亏损上限：本次启动已亏 %d，上限 %d（%d 个 100BB 买入），放不下%s，"
            "不再买入，停在大厅。重启后恢复。",
            lost, cap, 1 + self._max_auto_rebuy, what,
        )
        self._notify(
            "loss_stop",
            what=what,
            session_delta_chips=int(self._session_poker_pnl),
            loss_cap_chips=cap,
            buyins=1 + self._max_auto_rebuy,
        )

    def _maybe_topup(self, final_stacks: dict[int, int]) -> WireInject | None:
        """A short stack at the end of a hand asks the server to add chips before the next deal."""
        below_bb = float(getattr(config, "TOPUP_BELOW_BB", 0) or 0)
        if below_bb <= 0 or self._skip_profit_lock or self._shutdown_requested or self._loss_stop:
            return None
        if (
            self._my_seat is None
            or self._profit_lock_reenter is not None
            or self._profit_lock_deferred is not None
            or self._table_switch is not None
        ):
            return None
        bb = float(self._bb or 0.0)
        if bb <= 0:
            return None
        pending = self._topup_pending
        if pending is not None:
            if self._hand_seq - int(pending.get("hand_seq", 0)) < _TOPUP_PENDING_HANDS:
                return None
            log.warning(
                "[BOT] 桌上补码：请求的 %d 过了 %d 手仍未到账，%d 手后再试。",
                int(pending.get("chips", 0)), _TOPUP_PENDING_HANDS, _TOPUP_RETRY_HANDS,
            )
            self._topup_pending = None
            self._topup_retry_hand = self._hand_seq + _TOPUP_RETRY_HANDS
            return None
        if self._hand_seq < self._topup_retry_hand:
            return None
        stack = int(final_stacks.get(self._my_seat, 0))
        if stack <= 0 or stack >= int(below_bb * bb):
            return None
        short = int(float(getattr(config, "TOPUP_TARGET_BB", 100)) * bb) - stack
        budget = self._loss_room(stack)
        chips = max((int(s * bb) for s in _TOPUP_STEPS_BB if int(s * bb) <= min(short, budget)), default=0)
        if chips <= 0:
            if budget < short and not self._topup_budget_logged:
                self._topup_budget_logged = True
                log.warning(
                    "[BOT] 桌上补码：本次启动已亏 %d，再补就超过净亏损上限 %d（%d 个买入），不再补码。",
                    max(0, -int(self._session_poker_pnl)), self._loss_cap_chips(), 1 + self._max_auto_rebuy,
                )
            return None
        self._topup_budget_logged = False
        self._topup_pending = {"chips": chips, "hand_seq": self._hand_seq, "stack": stack}
        log.warning(
            "[BOT] 桌上补码：筹码 %d（%.1fBB）低于 %gBB，请求补 %d（%.0fBB），下一手发牌前到账。",
            stack, stack / bb, below_bb, chips, chips / bb,
        )
        return "pb.SetRebyREQ", {"reby_chips": chips}, 0.0

    def _on_set_reby_rsp(self, msg: dict) -> None:
        code = _s2c_rsp_code(msg, 0)
        if code == 0:
            log.info("[BOT] 桌上补码：服务端已受理 reby_chips=%s。", msg.get("reby_chips"))
            return
        log.warning(
            "[BOT] 桌上补码：服务端拒绝 code=%s（请求 %s），%d 手后再试。",
            code, (self._topup_pending or {}).get("chips"), _TOPUP_RETRY_HANDS,
        )
        self._topup_pending = None
        self._topup_retry_hand = self._hand_seq + _TOPUP_RETRY_HANDS

    def _on_my_topup(self, chips: int) -> None:
        """The server credited a top-up to our seat (pb.RebyBRC type=topup; chips = the amount added)."""
        pending = self._topup_pending
        self._topup_pending = None
        self._topup_count += 1
        self._topup_chips_total += chips
        self._note_bankroll_buyin("topup")
        bb = float(self._bb or 0.0)
        log.warning(
            "[BOT] 桌上补码到账 %d（请求 %s），桌上筹码 %d（%.1fBB）。本次启动第 %d 次，累计补 %d，对局盈亏 %+d",
            chips, pending.get("chips") if pending else "不是 bot 发的",
            self._my_chips, (self._my_chips / bb) if bb > 0 else 0.0,
            self._topup_count, self._topup_chips_total, int(self._session_poker_pnl),
        )
        self._notify(
            "topup",
            added_chips=chips,
            stack_chips=int(self._my_chips),
            big_blind=int(bb),
            nth=self._topup_count,
            session_delta_chips=int(self._session_poker_pnl),
        )
        # Refresh the wallet figure on the dashboard; skipped while another wallet action is waiting.
        if self._bankroll_pending_action is None and not self._bankroll_pending_reason:
            sample = self._request_bankroll_sample("topup")
            if sample is not None:
                self._pending_injects.append(sample)

    def _apply_table_blinds(
        self,
        *,
        big_blind,
        small_blind=None,
        source: str,
    ) -> bool:
        """Update cached/API blinds from room metadata; returns True if changed."""
        bb = _chip_float(big_blind, 0.0)
        if bb <= 0:
            return False

        sb = _chip_float(small_blind, 0.0)
        if sb <= 0:
            sb = bb / 2.0

        changed = False
        if self._bb is None or abs(float(self._bb) - bb) > 1e-9:
            self._bb = bb
            changed = True
            log.info("[BOT] Big blind detected (%s): %.1f", source, self._bb)
        if self._sb is None or abs(float(self._sb) - sb) > 1e-9:
            self._sb = sb
            changed = True
            log.info("[BOT] Small blind detected (%s): %.1f", source, self._sb)

        # 换桌 / 升盲后 PokerFateAPI 只创建一次，必须同步否则 stack→bb 日志仍用旧 BB。
        if changed and self._api is not None:
            self._api.set_table_blinds(float(self._bb), float(self._sb))
        return changed

    def _enter_tournament_passthrough(self, msg: dict) -> None:
        """Hand the tournament table to the player: drop every pending bot action."""
        if not self._tournament_passthrough:
            log.warning(
                "[BOT] 进入比赛房 game_type=%s roomid=%s：程序完全旁路，由玩家手动操作。",
                msg.get("game_type"),
                msg.get("roomid"),
            )
        self._tournament_passthrough = True
        self._profit_lock_cancel_reenter()
        self._bankroll_pending_action = None
        self._bankroll_pending_reason = ""
        self._bankroll_pending_buyin_reason = ""
        # Tournament chips are not bankroll; the cash seat (if any) is gone.
        self._mark_my_table_chips_zero()
        self._reset_hand_local_state()

    def _on_enter_room(self, msg: dict) -> WireInjectResult:
        if _is_tournament_enter_room(msg):
            self._enter_tournament_passthrough(msg)
            return None
        if self._tournament_passthrough:
            self._tournament_passthrough = False
            log.warning("[BOT] 离开比赛房，恢复托管 game_type=%s", msg.get("game_type"))

        self._profit_lock_reenter = None
        self._profit_lock_deferred = None

        if "game_type" in msg:
            self._session_game_type = _chip_int(msg.get("game_type"), 0)
        friend_info = msg.get("friend_room_info") or {}
        self._is_friend_room = (
            _is_friend_game_type(self._session_game_type)
            or bool(friend_info)
        )
        if self._is_friend_room:
            self._skip_profit_lock_reason = "friend_room"
        else:
            self._skip_profit_lock_reason = ""
        self._skip_profit_lock = bool(self._skip_profit_lock_reason)
        self._skip_runtime_collection = self._skip_profit_lock
        self._skip_runtime_collection_reason = self._skip_profit_lock_reason
        if self._api is not None:
            self._api.set_runtime_collection_enabled(
                not self._skip_runtime_collection,
                self._skip_runtime_collection_reason,
            )
        room_info_early = msg.get("room_info") or {}
        if "lobby_coin" in room_info_early:
            self._session_lobby_coin = _chip_int(room_info_early.get("lobby_coin"), 0)

        code = _s2c_rsp_code(msg, 0)
        if code == 0:
            self._transport_can_match = None
            if self._bankroll_pending_buyin_reason == "unexpected_leave":
                self._bankroll_pending_buyin_reason = ""
            if self._bankroll_pending_buyin_reason in {"profit_lock", "table_switch"}:
                self._note_bankroll_buyin(self._bankroll_pending_buyin_reason)
        fallback_inject: tuple[str, dict, float] | None = None
        if self._profit_lock_awaiting_enter:
            if self._profit_lock_last_enter_fields is None:
                log.warning("[BOT] 盈利锁仓：收到 EnterRoomRSP 但没有待确认的 EnterRoomREQ，忽略。")
                self._profit_lock_awaiting_enter = False
            elif code == 0:
                reenter_buyin = _chip_int(
                    (self._profit_lock_last_enter_fields or {}).get("byin_chips", 0),
                    0,
                )
                self._profit_lock_last_enter_fields = None
                log.warning("[BOT] 盈利锁仓：已重新进房，买入 %d。", reenter_buyin)
                self._profit_lock_awaiting_enter = False
            else:
                log.warning("[BOT] 盈利锁仓：重新进房失败 code=%s。", code)
                if self._profit_lock_last_enter_fields is not None:
                    log.warning(
                        "[BOT] 盈利锁仓 [EnterRoomREQ 备份，可对客户端抓包对照] %s",
                        self._profit_lock_last_enter_fields,
                    )
                self._profit_lock_awaiting_enter = False
                fallback_inject = self._profit_lock_quick_start_fallback()

        rid = msg.get("roomid")
        if rid is not None:
            self._table_room_id = _chip_int(rid, 0)
            if self._table_room_id:
                log.info("[BOT] Table room_id=%d (EnterRoomRSP)", self._table_room_id)

        # Blind detection (cash / friend rooms carry blinds in room_info).
        room_info = msg.get("room_info") or {}
        if room_info.get("bb"):
            self._apply_table_blinds(
                big_blind=room_info.get("bb"),
                small_blind=room_info.get("sb"),
                source="room_info",
            )

        # Seed player names from current table snapshot + trigger server stats fetch
        table_status = msg.get("table_status") or {}
        previous_gameid = self._current_gameid
        gameid = str(table_status.get("gameid") or "").strip()
        if gameid and gameid != "0":
            self._current_gameid = gameid
        for seat_status in table_status.get("seat", []):
            self._extract_seat_name(seat_status)
            self._trigger_gamedata_fetch(seat_status)

        # Re-detect my seat on reconnect by matching uid from SelfUserInfoRSP.
        if self._my_uid:
            for seat_status in table_status.get("seat", []):
                player = seat_status.get("player") or {}
                uid = player.get("uid")
                if uid is not None and str(uid) == self._my_uid:
                    seat = _chip_int(seat_status.get("seatid", 0), 0)
                    self._set_my_seat(seat, "EnterRoomRSP.uid")
                    break

        # If reconnect lands in a different hand, rebuild the API hand from
        # EnterRoomRSP before using playing_status. Otherwise old hole cards /
        # board/action history from the previous hand can leak into decisions.
        self._start_hand_from_enter_room_snapshot_if_needed(
            table_status,
            previous_gameid=previous_gameid,
        )

        # 重进 / 回桌后必须用服务端筹码覆盖快照（见 _sync_stacks_from_table_snapshot 注释）
        self._sync_stacks_from_table_snapshot(table_status)
        self._sync_hand_snapshot_from_enter_room(table_status)

        # 重连时恢复公共牌。若 table_status 携带了 board（说明局中重连），直接写入 api._board；
        # 之后的 RoundStartBRC.all_board 走 sync_board，与已恢复的牌一致时不会重复发牌。
        stage = table_status.get("stage", 1)
        board_ids = table_status.get("board", [])
        if board_ids and stage > 1 and self._api:
            cards = [_card_str(c) for c in board_ids if _card_str(c)]
            if cards:
                self._api.restore_board(cards)

        playing_status = msg.get("playing_status") or {}
        if self._enter_room_playing_status_is_current_hand(table_status, playing_status):
            self._restore_hole_cards_from_playing_status(playing_status)
            restored_action = self._action_from_enter_room_playing_status(
                table_status,
                playing_status,
                is_reconnect=bool(previous_gameid),
            )
        else:
            restored_action = None

        policy_inject = self._table_on_enter_room(table_status, code)
        injects: list = []
        for item in (fallback_inject, restored_action, policy_inject):
            if not item:
                continue
            if isinstance(item, list):
                injects.extend(item)
            else:
                injects.append(item)
        if not injects:
            return None
        return injects[0] if len(injects) == 1 else injects

    def _table_on_enter_room(self, table_status: dict, code: int) -> WireInject | None:
        """Room snapshot: restart the robot count for this room and judge the table."""
        if code != 0:
            return None
        seats = [(ss.get("player") or {}).get("uid") for ss in table_status.get("seat", [])]
        self._room_tracker.reset([u for u in seats if u is not None])
        self._table_switch = None
        if self._table_policy is None or self._is_friend_room or self._shutdown_requested:
            return None
        comp = self._table_composition()
        dealt = self._hole_cards_count >= 2
        step = self._table_policy.on_enter(int(self._bb or 0), comp["humans"], comp["robots"],
                                           time.time(), dealt=dealt)
        self._table_log("enter", decision=step.kind if step else self._table_policy.state, dealt=dealt)
        return self._table_step(step)

    def _profit_lock_quick_start_fallback(self) -> WireInject | None:
        """按大厅 QuickStart 随机配桌（LobbyByinDialog 同款字段）。"""
        pause_status = self._runtime_calibration_should_pause_play()
        if pause_status is not None:
            log.warning(
                "[BOT] 盈利锁仓：校准队列积压，取消 QuickStart。backlog=%.1fGB",
                float(pause_status.get("backlog_gb", 0.0) or 0.0),
            )
            return None
        bb = float(self._bb or 0.0)
        if bb <= 0:
            log.warning("[BOT] 盈利锁仓：无法 QuickStart（BB 未知）。")
            return None
        gt = self._session_game_type or int(config.PROFIT_LOCK_FALLBACK_GAME_TYPE)
        lc = self._session_lobby_coin or int(config.PROFIT_LOCK_FALLBACK_LOBBY_COIN)
        byin = int(100 * bb)
        delay = float(config.PROFIT_LOCK_QUICKSTART_DELAY_SEC)
        delay = max(0.0, min(30.0, delay))
        # wait_blind=False：与 LobbyByinDialog 勾选「支付大盲立刻加入」时一致（LocalStore poker_pay_bb_byin）
        fields = {
            "boot": int(bb),
            "game_type": gt,
            "lobby_coin": lc,
            "byin_chips": byin,
            "wait_blind": False,
            "ip": "",
        }
        fields = self.cap_match_buyin(self.adjust_match_fields(fields))
        if _chip_int(fields.get("byin_chips", 0), 0) <= 0:
            return None
        log.warning(
            "[BOT] 盈利锁仓：%.1fs 后发送 QuickStartREQ（随机桌，同盲注/100BB）: %s",
            delay,
            fields,
        )
        return "pb.QuickStartREQ", fields, delay

    def _on_sit_down_brc(self, msg: dict) -> WireInject | None:
        """A player sat down — update name map from SitDownBRC.status."""
        seat_status = msg.get("status") or {}
        self._extract_seat_name(seat_status)
        self._trigger_gamedata_fetch(seat_status)
        uid = (seat_status.get("player") or {}).get("uid")
        if uid is None or (self._my_uid is not None and str(uid) == str(self._my_uid)):
            return None
        self._room_tracker.sat_down(uid)
        return self._table_event("seats")

    def _on_stand_up_rsp(self, msg: dict) -> WireInject | None:
        code = _s2c_rsp_code(msg, 0)
        if code not in (0, 2, 3):
            return None
        return self._mark_my_left_table("stand_up")

    def _on_stand_up_brc(self, msg: dict) -> WireInject | None:
        """A player stood up; clear hero table chips immediately when it is us."""
        seat = _chip_int(msg.get("seatid", -1), -1)
        if self._my_seat is None or seat != self._my_seat:
            return None
        return self._mark_my_left_table("stand_up")

    def _on_other_leave_room_brc(self, msg: dict) -> WireInject | None:
        """A user left the room; clear stale table chips when the leaver is hero."""
        uid = msg.get("uid")
        if uid is None:
            return None
        if self._my_uid is None or str(uid) != str(self._my_uid):
            # rb_num 是服务端给出的房内机器人数：据此逐账号判定人机，并重新评估牌桌。
            self._room_tracker.left(uid, msg.get("num", 0), msg.get("rb_num", 0))
            return self._table_event("seats")
        return self._mark_my_left_table("leave_room")

    def _extract_seat_name(self, seat_status: dict) -> None:
        """Pull seat_id + player name/uid out of a SeatStatus dict."""
        seat = _chip_int(seat_status.get("seatid", 0), 0)
        player = seat_status.get("player") or {}
        name = player.get("name", "")
        uid  = player.get("uid")
        if seat >= 0 and name:
            self._seat_names[seat] = name
        if seat >= 0 and uid is not None:
            uid_str = str(uid)
            self._uid_to_seat[uid_str] = seat
            self._seat_uids[seat] = uid_str

    def _seat_to_player_id(self, seat: int) -> int:
        uid = self._seat_uids.get(seat)
        if uid is not None:
            return int(uid)
        return -(int(seat) + 1)

    def _dealer_player_id(self, dealer_seat: int) -> int:
        """Player id the API uses to locate the button.

        When the button sits on a seat that is not in this hand (a player who
        left or sits out keeps a stale uid in ``_seat_uids``), passing that uid
        makes ``PokerFateAPI`` lose the physical button seat and fall back to
        blind labels for postflop order; heads-up with a dead button that
        labels the first-to-act player "BTN" and the realtime CFR rejects the
        action prefix. Encode an unseated button as ``-(seat + 1)``, which
        ``new_hand`` decodes back to the seat index. 130 of 1798 logged hands
        (2026-11-07) had an unseated button.
        """
        if int(dealer_seat) not in self._all_seats:
            return -(int(dealer_seat) + 1)
        return self._seat_to_player_id(dealer_seat)

    def _seat_player_name(self, seat: int) -> str:
        return self._seat_names.get(seat) or f"Player_{seat}"

    def _seat_map_to_player_ids(self, values: dict[int, object]) -> dict[int, object]:
        return {self._seat_to_player_id(seat): value for seat, value in values.items()}

    def _seat_showdown_to_player_ids(self, hands: dict[int, list[str]]) -> dict[int, list[str]]:
        return {self._seat_to_player_id(seat): cards for seat, cards in hands.items()}

    def set_gamedata_session(self, *, authorization: str, http_base: str,
                             chnl: int, version: str) -> None:
        """Bind headless HTTP to its own login/line, never the legacy token file."""
        context = GameDataHTTPContext(authorization, http_base, int(chnl), str(version))
        with self._gamedata_lock:
            if context != self._gamedata_session:
                self._gamedata_session = context
                self._gamedata_failed_auth = None
                self._gamedata_retry_at = dict.fromkeys(self._gamedata_retry_at, 0.0)

    def _gamedata_context(self) -> GameDataHTTPContext:
        if self._gamedata_session is not None:
            return self._gamedata_session
        # MITM mode still gets its token from capture; headless always binds a
        # context, even when its authorization is missing (no stale fallback).
        return GameDataHTTPContext(load_auth_token() or "", config.GAMEDATA_HTTP_HOST,
                                   config.GAMEDATA_CHNL, config.GAME_HTTP_VERSION)

    def _retry_gamedata_for_seated_players(self) -> None:
        with self._gamedata_lock:
            pending = list(self._gamedata_retry_at)
        for uid in pending:
            seat = self._uid_to_seat.get(uid)
            if seat in self._all_seats and self._seat_uids.get(seat) == uid:
                self._trigger_gamedata_fetch({"seatid": seat, "player": {
                    "uid": uid, "name": self._seat_names.get(seat, ""),
                }})

    def _trigger_gamedata_fetch(self, seat_status: dict) -> None:
        """Fire-and-forget async fetch of 30-day server stats for one seat."""
        player = seat_status.get("player") or {}
        uid = player.get("uid")
        if not uid:
            return
        try:
            uid_int = int(uid)
        except (TypeError, ValueError):
            return
        if uid_int <= 0:
            return
        uid_str = str(uid_int)
        # Skip self
        if uid_str == self._my_uid:
            return
        with self._gamedata_lock:
            if (self._gamedata_closed or uid_str in self._fetched_uids
                    or uid_str in self._gamedata_inflight
                    or time.monotonic() < self._gamedata_retry_at.get(uid_str, 0.0)):
                return
            if self._gamedata_failed_auth is not None:
                if self._gamedata_context() == self._gamedata_failed_auth:
                    self._gamedata_retry_at.setdefault(uid_str, 0.0)
                    return
                self._gamedata_failed_auth = None
            self._gamedata_inflight.add(uid_str)
            self._gamedata_retry_at[uid_str] = time.monotonic() + _GAMEDATA_RETRY_SEC
        seat = _chip_int(seat_status.get("seatid", 0), 0)
        name = (seat_status.get("player") or {}).get("name", "")
        log.info("[gamedata] 触发拉取 %s", name or uid_str)
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self._do_gamedata_fetch(uid_int, seat, name))
        except RuntimeError:
            self._start_gamedata_fetch_thread(uid_int, seat, name)

    def _start_gamedata_fetch_thread(self, uid: int, seat: int, name: str = "") -> None:
        """Run GameData fetch from sync worker contexts without an asyncio loop."""
        thread: threading.Thread

        def _cleanup() -> None:
            try:
                self._do_gamedata_fetch_sync(int(uid), int(seat), str(name or ""))
            finally:
                self._gamedata_threads.discard(thread)

        thread = threading.Thread(
            target=_cleanup,
            name=f"pf-gamedata-{uid}",
            daemon=True,
        )
        self._gamedata_threads.add(thread)
        thread.start()

    async def _do_gamedata_fetch(self, uid: int, seat: int, name: str = "") -> None:
        """Async: fetch stats and write into opponent model (or buffer if API not ready)."""
        context = self._gamedata_context()
        try:
            if not context.authorization:
                log.warning("[gamedata] %s: HTTP 凭证缺失，跳过", name or uid)
                return
            result = await asyncio.to_thread(
                _sync_fetch, uid, context.http_base, context.chnl,
                config.GAMEDATA_GAME_TYPE, context.authorization, version=context.version,
            )
            self._apply_gamedata_fetch_result(uid, seat, name, result, context=context)
        except Exception:
            log.exception("[gamedata] %s: 请求或结果处理异常", name or uid)
        finally:
            self._finish_gamedata_fetch(uid)

    def _do_gamedata_fetch_sync(self, uid: int, seat: int, name: str = "") -> None:
        """Sync worker-thread equivalent of _do_gamedata_fetch."""
        context = self._gamedata_context()
        try:
            if not context.authorization:
                log.warning("[gamedata] %s: HTTP 凭证缺失，跳过", name or uid)
                return
            result = _sync_fetch(uid, context.http_base, context.chnl,
                                 config.GAMEDATA_GAME_TYPE, context.authorization,
                                 version=context.version)
            self._apply_gamedata_fetch_result(uid, seat, name, result, context=context)
        except Exception:
            log.exception("[gamedata] %s: 请求或结果处理异常", name or uid)
        finally:
            self._finish_gamedata_fetch(uid)

    def _finish_gamedata_fetch(self, uid: int) -> None:
        with self._gamedata_lock:
            self._gamedata_inflight.discard(str(uid))
            if str(uid) not in self._fetched_uids:
                self._gamedata_retry_at[str(uid)] = time.monotonic() + _GAMEDATA_RETRY_SEC

    def _apply_gamedata_fetch_result(
        self,
        uid: int,
        seat: int,
        name: str,
        result: dict | None,
        *, context: GameDataHTTPContext | None = None,
    ) -> None:
        with self._gamedata_lock:
            if self._gamedata_closed or (context is not None and context != self._gamedata_context()):
                return
            self._apply_gamedata_fetch_result_locked(uid, seat, name, result, context)

    def _apply_gamedata_fetch_result_locked(self, uid, seat, name, result, context) -> None:
        pname = name or self._seat_names.get(seat) or f"seat{seat}"

        if not isinstance(result, dict) or not result:
            log.warning("[gamedata] %s: 请求无响应", pname)
            return
        if result.get("code") != 0:
            code = result.get("code")
            if code == -2:
                failed_context = context or self._gamedata_context()
                if self._gamedata_failed_auth != failed_context:
                    self._gamedata_failed_auth = failed_context
                    log.warning("[gamedata] HTTP 鉴权失败 (code=-2)，暂停历史查询，等待有效凭证更新")
                    self._notify("gamedata_auth_failed")
            else:
                log.warning("[gamedata] %s: 服务端错误 code=%s", pname, code)
            return

        data = result.get("data")
        raw_hands = data.get("play_times") if isinstance(data, dict) else None
        try:
            if isinstance(raw_hands, bool) or not isinstance(raw_hands, (int, str)):
                raise ValueError("missing/invalid play_times")
            hands = int(raw_hands)
            if hands < 0:
                raise ValueError("negative play_times")
        except ValueError:
            log.warning("[gamedata] %s: 返回统计缺失或无效，稍后重试", pname)
            return
        data = {**data, "play_times": hands}
        if hands == 0:
            log.info("[gamedata] %s: 服务端无历史数据 (play_times=0)", pname)
            self._fetched_uids.add(str(uid))
            self._gamedata_retry_at.pop(str(uid), None)
            if not self._gamedata_no_history_notified:
                self._gamedata_no_history_notified = True
                self._notify("gamedata_no_history", name=pname, uid=uid)
            return

        api_bot = getattr(self._api, "_bot", None) if self._api is not None else None
        om = getattr(api_bot, "opponent_model", None)
        if om is not None:
            display_name = name or self._seat_names.get(seat) or f"uid{uid}"
            om.register_name(int(uid), display_name)
            stats = om.get(int(uid))
            applied = seed_from_server(stats, data)
            if applied:
                log.info(
                    "[gamedata] %s 写入成功 | hands=%d VPIP=%.0f%% PFR=%.0f%% "
                    "AF=%.2f wtsd=%.0f%%",
                    display_name,
                    data.get("play_times", 0),
                    stats.vpip * 100,
                    stats.pfr * 100,
                    stats.aggression_factor,
                    stats.wtsd * 100,
                )
        else:
            # API not ready yet (seat/blinds unknown); buffer until _ensure_api
            display_name = name or self._seat_names.get(seat) or f"uid{uid}"
            self._pending_seeds[int(uid)] = {"data": data, "name": display_name}
            log.info("[gamedata] %s: API 未就绪，数据已缓存 (hands=%d)",
                     display_name, data.get("play_times", 0))
        self._fetched_uids.add(str(uid))
        self._gamedata_retry_at.pop(str(uid), None)

    def _reset_hand_local_state(self, *, stage: int = 1) -> None:
        self._stage = stage
        self._pot = 0
        self._my_bet = 0
        self._max_bet = 0
        self._street_bets = {}
        self._pre_action_flags = {}
        self._my_forced_post_this_street = False
        self._folded = set()
        self._hole_cards_count = 0
        self._pending_showdown = {}
        self._pending_winner_types = {}
        self._pending_injects = []
        self._pending_hero_wire_action = None
        self._last_hero_action_context = None

    def _apply_pending_seeds_for_players(self, players: list[PlayerInfo]) -> None:
        if not self._pending_seeds or self._api is None:
            return
        om = self._api._bot.opponent_model
        player_names = {p.player_id: p.name for p in players}
        for uid, payload in self._pending_seeds.items():
            if isinstance(payload, dict) and "data" in payload:
                data = payload.get("data") or {}
                cached_name = str(payload.get("name") or "")
            else:
                data = payload
                cached_name = ""
            display_name = player_names.get(uid) or cached_name
            if display_name:
                om.register_name(uid, display_name)
            stats = om.get(uid)
            if seed_from_server(stats, data):
                pname = display_name or f"uid{uid}"
                log.info(
                    "[gamedata] %s 缓存数据写入 | hands=%d VPIP=%.0f%% PFR=%.0f%% "
                    "AF=%.2f wtsd=%.0f%%",
                    pname,
                    data.get("play_times", 0),
                    stats.vpip * 100,
                    stats.pfr * 100,
                    stats.aggression_factor,
                    stats.wtsd * 100,
                )
        self._pending_seeds.clear()

    def _is_robot_seat(self, seat: int, player_id: int) -> bool:
        """已被服务器计数证实的人机，不含自己。策略层据此让整手牌不参与采集 / 学习。"""
        return seat != self._my_seat and player_id > 0 and self._robots.is_robot(player_id)

    def _start_hand_from_enter_room_snapshot_if_needed(
        self,
        table_status: dict,
        *,
        previous_gameid: str,
    ) -> bool:
        gameid = str(table_status.get("gameid") or "").strip()
        if not gameid or gameid == "0" or gameid == previous_gameid:
            return False
        if table_status.get("is_playing") is not True:
            return False
        stage = _chip_int(table_status.get("stage"), 0)
        if stage not in (1, 2, 3, 4):
            return False
        if self._my_seat is None or not self._ensure_api():
            return False

        start_info: list[dict] = []
        for seat_status in table_status.get("seat", []) or []:
            if not _seat_status_has_player(seat_status):
                continue
            seat = _chip_int(seat_status.get("seatid", 0), 0)
            chips = seat_status.get("hand_chips")
            if chips is None:
                chips = seat_status.get("begin_chips", 0)
            start_info.append({"seatid": seat, "chips": chips})
        if not start_info:
            return False

        self._hand_seq += 1
        self._reset_hand_local_state(stage=stage)

        start_info.sort(key=lambda si: si["seatid"])
        self._all_seats = [si["seatid"] for si in start_info]
        dealer_seat = _chip_int(table_status.get("d_idx", 0), 0)
        # Zero-valued fields are dropped from the decoded message, so one blind
        # index being present means both were sent.
        blinds_named = "sb_idx" in table_status or "bb_idx" in table_status
        seat_positions = derive_seating(
            self._all_seats,
            dealer_seat,
            big_blind=_chip_int(table_status.get("bb_idx", 0), 0) if blinds_named else None,
        ).labels
        self._seat_chips = {}
        self._hand_start_chips = {}

        players = []
        for si in start_info:
            seat = si["seatid"]
            chips = _chip_int(si.get("chips", 0), 0)
            self._seat_chips[seat] = chips
            self._hand_start_chips[seat] = chips
            if seat == self._my_seat:
                self._my_chips = chips
            player_id = self._seat_to_player_id(seat)
            players.append(PlayerInfo(
                player_id=player_id,
                name=self._seat_player_name(seat),
                stack=chips,
                position=seat_positions.get(seat, ""),
                seat_index=seat,
                is_robot=self._is_robot_seat(seat, player_id),
            ))

        self._apply_pending_seeds_for_players(players)
        self._api.new_hand(
            players=players,
            dealer_id=self._dealer_player_id(dealer_seat),
            hand_number=self._hand_seq,
        )
        if previous_gameid:
            log.warning(
                "[BOT] 重连恢复：检测到 gameid 切换 %s -> %s，已从 EnterRoomRSP.table_status 重建当前手。",
                previous_gameid,
                gameid,
            )
        else:
            log.debug(
                "[BOT] 进桌初始化：已从 EnterRoomRSP.table_status 建立当前手 gameid=%s。",
                gameid,
            )
        return True

    def _sync_stacks_from_table_snapshot(self, table_status: dict) -> None:
        """用 EnterRoomRSP.table_status 对齐本地筹码快照。

        hand_chips 是当前剩余筹码；begin_chips 才是本手开局筹码。
        WinnerRSP.profit 需要加在 begin_chips 上，不能用局中剩余筹码当基准。
        """
        seen_my_seat = False
        seat_snapshot = table_status.get("seat")
        for seat_status in seat_snapshot or []:
            seat = _chip_int(seat_status.get("seatid", 0), 0)
            if "seatid" not in seat_status:
                log.debug(
                    "[BOT] table_status seat missing seatid; assume 0: %s",
                    seat_status,
                )
            has_player = _seat_status_has_player(seat_status)
            if self._my_seat is not None and seat == self._my_seat and not has_player:
                self._mark_my_table_chips_zero()
            if not has_player:
                continue
            if self._my_seat is not None and seat == self._my_seat:
                seen_my_seat = True
            current_raw = seat_status.get("hand_chips")
            if current_raw is None:
                current_raw = seat_status.get("begin_chips")
            if current_raw is None:
                continue
            start_raw = seat_status.get("begin_chips")
            if start_raw is None:
                start_raw = current_raw

            chips = _chip_int(current_raw, 0)
            start_chips = _chip_int(start_raw, chips)
            self._seat_chips[seat] = chips
            self._hand_start_chips[seat] = start_chips
            if self._my_seat is not None and seat == self._my_seat:
                self._my_chips = chips
        if (
            self._my_seat is not None
            and seat_snapshot is not None
            and not seen_my_seat
        ):
            self._mark_my_table_chips_zero()

    def _sync_hand_snapshot_from_enter_room(self, table_status: dict) -> None:
        """Best-effort restore of per-hand bridge state from EnterRoomRSP after reconnect."""
        if not table_status:
            return
        stage = _chip_int(table_status.get("stage", self._stage or 1), self._stage or 1)
        if stage > 0:
            self._stage = stage

        seats: list[int] = []
        folded: set[int] = set()
        street_bets: dict[int, int] = {}
        max_bet = 0
        my_bet = 0
        desktop_total = 0
        for seat_status in table_status.get("seat", []) or []:
            if not _seat_status_has_player(seat_status):
                continue
            seat = _chip_int(seat_status.get("seatid", 0), 0)
            seats.append(seat)
            action_type = _chip_int(seat_status.get("action_type", 0), 0)
            if action_type in FOLD_ACTION_TYPES:
                folded.add(seat)

            destop = _chip_int(seat_status.get("destop_chips", 0), 0)
            desktop_total += destop
            if stage == 1 and destop > 0:
                street_bets[seat] = destop
                max_bet = max(max_bet, destop)
                if self._my_seat is not None and seat == self._my_seat:
                    my_bet = destop

        if seats:
            self._all_seats = seats
        self._folded = folded
        if stage == 1:
            self._street_bets = street_bets
            self._max_bet = max_bet
            self._my_bet = my_bet

        pools = table_status.get("pool") or []
        if pools:
            self._pot = sum(_chip_int(p, 0) for p in pools)
        elif desktop_total and self._pot == 0:
            self._pot = desktop_total

    def _seat_status_from_table_snapshot(self, table_status: dict, seat: int) -> dict:
        for seat_status in table_status.get("seat", []) or []:
            if _chip_int(seat_status.get("seatid", 0), 0) == seat:
                return seat_status
        return {}

    def _restore_hole_cards_from_playing_status(self, playing_status: dict) -> None:
        if self._api is None or self._hole_cards_count >= 2:
            return
        cards = [
            _card_str(playing_status[k])
            for k in ("card1", "card2", "card3", "card4")
            if playing_status.get(k)
        ]
        cards = [c for c in cards if c is not None]
        if len(cards) < 2:
            return
        self._hole_cards_count = len(cards)
        self._api.deal_hole_cards(cards)
        log.info("[BOT] Reconnect restored %d hole card(s) from EnterRoomRSP.playing_status", len(cards))

    def _enter_room_playing_status_is_current_hand(
        self,
        table_status: dict,
        playing_status: dict,
    ) -> bool:
        """Guard against stale EnterRoomRSP.playing_status after reconnect churn."""
        if not table_status or not playing_status:
            return False
        if table_status.get("is_playing") is not True:
            if "action_seatid" in playing_status:
                log.warning(
                    "[BOT] EnterRoomRSP.playing_status ignored: table is not playing "
                    "(action_idx=%s gameid=%s)",
                    table_status.get("action_idx"),
                    table_status.get("gameid"),
                )
            return False
        action_idx = _chip_int(table_status.get("action_idx"), -1)
        if action_idx < 0:
            log.warning(
                "[BOT] EnterRoomRSP.playing_status ignored: invalid table action_idx=%s gameid=%s",
                table_status.get("action_idx"),
                table_status.get("gameid"),
            )
            return False
        stage = _chip_int(table_status.get("stage"), 0)
        if stage not in (1, 2, 3, 4):
            log.warning(
                "[BOT] EnterRoomRSP.playing_status ignored: invalid/missing stage=%s gameid=%s",
                table_status.get("stage"),
                table_status.get("gameid"),
            )
            return False
        return True

    def _action_from_enter_room_playing_status(
        self,
        table_status: dict,
        playing_status: dict,
        *,
        is_reconnect: bool = False,
    ) -> WireInjectResult:
        if not playing_status or self._my_seat is None:
            return None
        if not self._enter_room_playing_status_is_current_hand(table_status, playing_status):
            return None
        if "action_seatid" not in playing_status:
            return None
        table_action_seat = _chip_int(table_status.get("action_idx"), -1)
        if table_action_seat != self._my_seat:
            return None
        action_seat = _chip_int(playing_status.get("action_seatid"), -1)
        if action_seat != self._my_seat:
            return None

        my_status = self._seat_status_from_table_snapshot(table_status, self._my_seat)
        my_action = _chip_int(my_status.get("action_type", 0), 0)
        if my_status.get("is_allin") or my_action == 17 or my_action in FOLD_ACTION_TYPES:
            log.info(
                "[BOT] EnterRoomRSP.playing_status action is hero, but seat is already terminal/all-in; skip restore action"
            )
            return None
        if self._api is None or not self._all_seats:
            log.warning(
                "[BOT] EnterRoomRSP.playing_status action is hero, but API/hand snapshot is not ready; wait for ActionNotifyBRC"
            )
            return None

        notify_msg = dict(playing_status)
        notify_msg["seatid"] = self._my_seat
        sig = self._hero_action_notify_signature(notify_msg)
        if (
            sig == self._last_hero_action_notify_sig
            and time.monotonic() - self._last_hero_action_notify_at < 0.75
        ):
            log.info("[BOT] EnterRoomRSP.playing_status duplicates recent ActionNotifyBRC; skip restore action")
            return None
        if is_reconnect:
            log.warning("[BOT] 重连恢复：EnterRoomRSP.playing_status 仍轮到我行动，补一次决策。")
        else:
            log.debug("[BOT] 进桌初始化：EnterRoomRSP.playing_status 轮到我行动，补一次决策。")
        restored = self._on_action_notify(notify_msg)
        action_time = _chip_float(playing_status.get("action_time"), 0.0)
        if action_time > 0:
            restored = _clamp_inject_delay(restored, max(0.0, action_time - 1.0))
        return restored

    def _hero_action_notify_signature(self, msg: dict) -> tuple:
        return (
            self._current_gameid,
            self._stage,
            self._my_seat,
            _chip_int(msg.get("call_need_chips", 0)),
            _chip_int(msg.get("min_chipin", 0)),
            _chip_int(msg.get("max_chipin", 0)),
        )

    def _ensure_api(self) -> bool:
        """Create PokerFateAPI once seat and blind values are known. Returns True if ready."""
        if self._api is not None:
            return True
        if self._my_seat is None:
            log.warning("[BOT] Waiting for SitDownRSP to learn seat ID")
            return False
        bb = self._bb or 2.0
        sb = self._sb or 1.0
        self._api = PokerFateAPI(
            my_player_id=self._seat_to_player_id(self._my_seat),
            big_blind=bb,
            small_blind=sb,
            equity_iterations=3000,
            verbose=True,
            decision_engine=getattr(config, "DECISION_ENGINE", "cfr"),
            cfr_flop_book_enabled=getattr(config, "PF_CFR_FLOP_BOOK_ENABLED", True),
        )
        self._apply_preflop_sticky_pool_adjust(
            bool(getattr(config, "PREFLOP_STICKY_POOL_ADJUST", True))
        )
        if self._skip_runtime_collection:
            self._api.set_runtime_collection_enabled(
                False,
                self._skip_runtime_collection_reason,
            )
        self._api.logger.decision_listener = self._note_live_decision
        log.info("[BOT] PokerFateAPI ready — seat=%d  BB=%.1f  SB=%.1f",
                 self._my_seat, bb, sb)

        return True

    # ── Hand lifecycle ────────────────────────────────────────────────────────

    def _on_dealer_info(self, msg: dict) -> WireInject | None:
        if not self._ensure_api():
            return None

        gameid = str(msg.get("gameid") or "").strip()
        if gameid and gameid != "0":
            self._current_gameid = gameid

        pause_status = self._runtime_calibration_should_pause_play()
        if pause_status is not None:
            self._hand_seq += 1
            return self._leave_for_runtime_calibration_backpressure(pause_status)

        self._hand_seq += 1

        self._reset_hand_local_state(stage=1)

        raw_start_info = msg.get("start_info", [])
        start_info = []
        for si in raw_start_info:
            # In some decoded payloads, seatid=0 may be omitted from JSON output.
            # Treat missing seatid as 0 instead of dropping the player.
            seat = si.get("seatid", 0)
            normalized = dict(si)
            normalized["seatid"] = int(seat)
            if "seatid" not in si:
                log.debug("[BOT] DealerInfoRSP.start_info missing seatid; assume 0: %s", si)
            start_info.append(normalized)

        start_info.sort(key=lambda si: si["seatid"])
        self._all_seats = [si["seatid"] for si in start_info]
        dealer_seat = _chip_int(msg.get("dealer", 0), 0)
        blind_fields_present = "small_blind" in msg or "big_blind" in msg
        big_blind_seat = (
            _chip_int(msg.get("big_blind", 0), 0)
            if blind_fields_present
            else None
        )
        seat_positions = derive_seating(
            self._all_seats,
            dealer_seat,
            big_blind=big_blind_seat,
        ).labels
        self._seat_chips = {}
        self._hand_start_chips = {}

        players = []
        for si in start_info:
            seat  = si["seatid"]
            chips = _chip_int(si.get("chips", 0))
            self._seat_chips[seat] = chips
            self._hand_start_chips[seat] = chips
            if seat == self._my_seat:
                self._my_chips = chips
            name = self._seat_player_name(seat)
            player_id = self._seat_to_player_id(seat)
            position = seat_positions.get(seat, "")
            players.append(PlayerInfo(
                player_id=player_id,
                name=name,
                stack=chips,
                position=position,
                seat_index=seat,
                is_robot=self._is_robot_seat(seat, player_id),
            ))

        # 应用 API 创建前已缓冲的 server stats：
        # 必须在 new_hand（内部调用 register_name）之前 pre-register 玩家名，
        # 否则 opponent_model 里 seat 还映射着上一局的旧玩家，seed 会写错位置。
        self._apply_pending_seeds_for_players(players)

        self._api.new_hand(
            players=players,
            dealer_id=self._dealer_player_id(dealer_seat),
            hand_number=self._hand_seq,
        )
        # 盈利锁仓：若 WinnerRSP 后的 DelayLeaveRoomREQ 没有及时确认，新手牌开始时再补发一次。
        # 不再发 LeaveRoomREQ；实战证明新手牌开始后服务端会返回 121（playing cannot leave）。
        pending = self._profit_lock_reenter
        if pending is not None and pending.get("leave_mode") == "delay_leave":
            if (
                not bool(pending.get("delay_leave_confirmed", False))
                and not bool(pending.get("delay_leave_retry_sent", False))
            ):
                pending["delay_leave_retry_sent"] = True
                if self._profit_lock_deferred is not None:
                    self._profit_lock_deferred["delay_leave_retry_sent"] = True
                log.warning("[BOT] 盈利锁仓：下一手已开始但延迟离桌未确认，补发 DelayLeaveRoomREQ。")
                return "pb.DelayLeaveRoomREQ", {"flag": True}, 0.0

        return None

    def _on_hand_card(self, msg: dict) -> WireInjectResult:
        if self._api is None:
            return None
        cards = [
            _card_str(msg[k])
            for k in ("card1", "card2", "card3", "card4")
            if msg.get(k)
        ]
        cards = [c for c in cards if c is not None]
        self._hole_cards_count = len(cards)
        if len(cards) >= 2:
            if self._table_policy is not None:
                self._table_policy.on_dealt()
            self._api.deal_hole_cards(cards)
        elif cards:
            log.warning("[BOT] Incomplete hole cards (%d): %s", len(cards), cards)
        return None

    def _on_round_start(self, msg: dict) -> None:
        if _chip_int(msg.get("stage", 0)) == 1:
            self._retry_gamedata_for_seated_players()
        stage = msg.get("stage", 1)
        self._stage   = stage
        self._my_bet  = 0
        self._max_bet = 0
        self._street_bets = {}
        self._pre_action_flags = {}
        self._my_forced_post_this_street = False
        self._pending_hero_wire_action = None
        self._last_hero_action_context = None

        if not self._api:
            return
        # 1.7.5+：服务端直接给出到目前为止的全部公共牌，幂等同步，
        # 重复 / 迟到 / 漏掉的街都不会让牌面错位。
        cards = [c for c in (_card_str(x) for x in msg.get("all_board") or []) if c]
        if cards:
            self._api.sync_board(cards, street=_STAGE_TO_STREET.get(stage, "flop"), pot=self._pot)
        elif stage > 1 and not self._all_board_missing_logged:
            # 不再回退到按街累加：没有 all_board 就没有可信的公共牌，必须被看见。
            self._all_board_missing_logged = True
            log.error("[BOT] RoundStartBRC stage=%s 没有 all_board，公共牌未更新（服务端协议变了？）", stage)

    def _on_action_brc(self, msg: dict) -> None:
        seat        = _chip_int(msg.get("seatid", 0), 0)
        action_type = _chip_int(msg.get("action_type", 1), 1)
        chips       = _chip_int(msg.get("chips", 0))
        hand_chips  = msg.get("hand_chips")
        # The flag of the notice that asked for this action; a system fold / check (timeout,
        # leaving) was not chosen by the player.
        pre_action_flag = self._pre_action_flags.pop(seat, 0)
        if action_type in (12, 13, 16):
            pre_action_flag = 0

        # seatid=-1 is used by the game for system broadcasts (no specific player).
        if seat < 0:
            return

        if action_type in FOLD_ACTION_TYPES:
            self._folded.add(seat)

        self._pot += chips
        prev_street_bet = self._street_bets.get(seat, 0)
        total_street_bet = prev_street_bet
        if chips > 0:
            total_street_bet = prev_street_bet + chips
            self._street_bets[seat] = total_street_bet
            if total_street_bet > self._max_bet:
                self._max_bet = total_street_bet

        # Track remaining chips for every seat (used in final_stacks)
        if hand_chips is not None:
            self._seat_chips[seat] = _chip_int(hand_chips)

        action_str = ACTION_TYPE_TO_EVENT_ACTION.get(action_type)
        # The table reports every all-in as ALLIN, whatever it does to the
        # betting. One that does not top the highest bet of the others is a
        # call; only a higher one raises.
        other_max = max((v for s, v in self._street_bets.items() if s != seat), default=0)
        if action_str == "raise" and total_street_bet <= other_max:
            action_str = "call"

        if seat == self._my_seat:
            self._my_bet = total_street_bet
            if action_type in (8, 9, 10, 11, 14) and chips > 0:
                self._my_forced_post_this_street = True
            if hand_chips is not None:
                self._my_chips = _chip_int(hand_chips)
            if action_str is not None:
                self._pending_hero_wire_action = None
                record = getattr(self._api, "record_hero_execution", None)
                if callable(record):
                    record(
                        action=action_str, amount_added=chips, total_bet_after=total_street_bet,
                        street=_STAGE_TO_STREET.get(self._stage, "preflop"),
                    )
            return   # don't feed our own actions into the opponent model

        if self._pending_hero_wire_action:
            self._pending_hero_wire_action = None
        if self._last_hero_action_context:
            self._last_hero_action_context = None

        if self._api is None:
            return
        if action_str is None:
            if action_type not in ACTION_TYPE_TO_EVENT_ACTION:
                log.warning("[BOT] Unknown action_type=%s in ActionBRC; skipped", action_type)
            return
        street     = _STAGE_TO_STREET.get(self._stage, "preflop")
        if action_str == "raise":
            api_amount = total_street_bet
        elif action_str == "call":
            api_amount = chips
        else:
            api_amount = 0
        self._api.notify_action(ActionEvent(
            player_id=self._seat_to_player_id(seat),
            action=action_str,
            amount=api_amount,
            street=street,
            stack_after=None if hand_chips is None else _chip_int(hand_chips),
            pre_action=pre_action_flag,
        ))

    def _on_round_over(self, msg: dict) -> None:
        pool = msg.get("pool", [])
        if pool:
            self._pot = sum(_chip_int(p, 0) for p in pool)

    def note_pre_action(self, msg: dict) -> None:
        """Remember what a "your turn" notice says about another seat's pre-selected action.

        The notice says whether the seat had picked its action in advance; the action itself
        follows in ActionBRC and takes the flag along.  The headless session calls this also
        for the notices it does not hand over because the table has already moved on: a
        pre-selected action arrives together with its notice, so those are exactly the
        notices that carry the flag.
        """
        seat = _chip_int(msg.get("seatid", 0), 0)
        if self._my_seat is None or seat == self._my_seat or seat < 0:
            return
        self._pre_action_flags[seat] = _chip_int(msg.get("pre_action_result", 0), 0)

    def _on_action_notify(self, msg: dict) -> WireInject | None:
        if self._api is None or self._my_seat is None:
            return None
        seat = _chip_int(msg.get("seatid", 0), 0)
        if seat != self._my_seat:
            self.note_pre_action(msg)
            log.debug("[BOT] Ignore ActionNotify seat=%d my_seat=%d", seat, self._my_seat)
            return None

        notify_sig = self._hero_action_notify_signature(msg)
        if self._should_skip_duplicate_hero_action_notify(notify_sig):
            return None

        call_need = _chip_int(msg.get("call_need_chips", 0))
        # Chips a minimum raise takes on top of what is already in front of
        # us; the table sends 0 (decoded: no field) when it accepts no raise.
        min_chipin = _chip_int(msg.get("min_chipin", 0))
        self._last_hero_action_notify_sig = notify_sig
        self._last_hero_action_notify_at = time.monotonic()

        # Sometimes ActionNotify arrives before a full HandCardRSP payload.
        # Avoid crashing preflop strategy on incomplete hole cards.
        if self._hole_cards_count < 2:
            log.warning("[BOT] ActionNotify before full hole cards (%d); fallback action", self._hole_cards_count)
            street_fb = _STAGE_TO_STREET.get(self._stage, "preflop")
            if call_need == 0:
                fb = BotDecision(action="check", amount=0.0)
                self._remember_hero_wire_action(fb, notify_sig=notify_sig)
                delay_sec = _inject_delay_before_action(street_fb, fb, self._pot, self._bb or 0.0)
                return "pb.ActionREQ", {"action_type": 2, "chips": 0}, delay_sec
            fb = BotDecision(action="fold", amount=0.0)
            self._remember_hero_wire_action(fb, notify_sig=notify_sig)
            delay_sec = _inject_delay_before_action(street_fb, fb, self._pot, self._bb or 0.0)
            return "pb.ActionREQ", {"action_type": 1, "chips": 0}, delay_sec

        street = _STAGE_TO_STREET.get(self._stage, "preflop")

        # current_bet = highest total bet this street
        current_bet = self._my_bet + call_need

        num_active_opponents = sum(
            1 for s in self._all_seats
            if s != self._my_seat and s not in self._folded
        )

        is_bb_option = self._my_forced_post_this_street and call_need == 0

        decision: BotDecision = self._api.request_action(
            street=street,
            pot=self._pot,
            current_bet=current_bet,
            to_call=call_need,
            my_stack=self._my_chips,
            num_active_opponents=max(num_active_opponents, 1),
            my_current_bet_this_street=self._my_bet,
            is_bb_option=is_bb_option,
            min_raise_to=self._my_bet + min_chipin if min_chipin > 0 else 0,
        )

        log.info(
            "[BOT] Spot: street=%s pot=%d call_need=%d my_bet=%d current_bet=%d forced_post=%s",
            street,
            self._pot,
            call_need,
            self._my_bet,
            current_bet,
            self._my_forced_post_this_street,
        )
        log.info("[BOT] Decision: %s  (street=%s pot=%.0f to_call=%.0f stack=%.0f)",
                 decision, street, self._pot, call_need, self._my_chips)

        action_type, chips = _decision_to_wire(decision, current_bet=self._my_bet)
        self._remember_hero_wire_action(decision, notify_sig=notify_sig)
        delay_sec = _inject_delay_before_action(
            street, decision, self._pot, self._bb or 0.0,
        )
        log.debug("[BOT] ActionREQ inject delay: %.2fs", delay_sec)
        action_req = ("pb.ActionREQ", {"action_type": action_type, "chips": chips}, delay_sec)
        if self._pending_injects:
            pending = self._pending_injects
            self._pending_injects = []
            return pending + [action_req]
        return action_req

    def _note_live_decision(self, rec: dict) -> None:
        """One decision of ours, as the strategy logged it, kept until the next hand's first."""
        game = str(self._current_gameid or "")
        kept = tuple(d for d in self.live_decisions if d["game_id"] == game)
        self.live_decisions = kept + (_live_decision(rec, game),)

    def _should_skip_duplicate_hero_action_notify(self, notify_sig: tuple) -> bool:
        context = self._last_hero_action_context or self._pending_hero_wire_action
        if not context:
            return False
        if str(context.get("gameid") or "") != str(self._current_gameid or ""):
            self._pending_hero_wire_action = None
            self._last_hero_action_context = None
            return False
        if int(context.get("stage") or 0) != int(self._stage or 0):
            self._pending_hero_wire_action = None
            self._last_hero_action_context = None
            return False

        created_at = float(context.get("created_at") or 0.0)
        age = time.monotonic() - created_at if created_at > 0 else 0.0
        if age > _HERO_ACTION_PENDING_SUPPRESS_SEC:
            log.warning(
                "[BOT] last hero action context stale after %.1fs; allow ActionNotify retry",
                age,
            )
            self._pending_hero_wire_action = None
            self._last_hero_action_context = None
            return False

        log.info(
            "[BOT] Duplicate ActionNotify before table advances after hero action; skip. "
            "gameid=%s stage=%s action=%s age=%.1fs sig=%s",
            context.get("gameid"),
            context.get("stage"),
            context.get("action"),
            age,
            notify_sig,
        )
        self._last_hero_action_notify_sig = notify_sig
        self._last_hero_action_notify_at = time.monotonic()
        return True

    def _remember_hero_wire_action(
        self,
        decision: BotDecision,
        *,
        notify_sig: tuple | None = None,
    ) -> None:
        context = {
            "gameid": str(self._current_gameid or ""),
            "stage": int(self._stage),
            "action": str(decision.action or "").lower(),
            "created_at": time.monotonic(),
            "notify_sig": notify_sig,
        }
        self._pending_hero_wire_action = dict(context)
        self._last_hero_action_context = dict(context)

    def _on_show_hand(self, msg: dict) -> None:
        """Capture ShowHandRSP — hole cards revealed at showdown."""
        for info in msg.get("info", []):
            seat = info.get("seatid", 0)  # pb omits field when value is 0
            cards = []
            for key in ("card1", "card2", "card3", "card4"):
                code = info.get(key)
                if code:
                    s = _card_str(int(code))
                    if s:
                        cards.append(s)
            if cards:
                self._pending_showdown[int(seat)] = cards

    def _on_winner(self, msg: dict) -> tuple[str, dict, float] | None:
        self._settle_my_hand(msg)
        if self._api is None:
            return None

        winner_list = msg.get("winner", [])
        winner_ids: list[int] = []
        total_pot = 0

        # Build winner_ids and total_pot from winner list.
        for w in winner_list:
            chips = _chip_int(w.get("chips", 0), 0)
            total_pot += chips

            # Prefer explicit seatid; fall back to uid→seat lookup.
            if "seatid" in w:
                seat = int(w["seatid"])
            else:
                uid = str(w.get("uid", ""))
                seat = self._uid_to_seat.get(uid, -1)
                if seat < 0:
                    log.warning("[BOT] WinnerRSP: uid=%s has no seat mapping — skipping", uid)
                    continue

            player_id = self._seat_to_player_id(seat)
            winner_ids.append(player_id)

            # Capture server-provided hand type (authoritative)
            hand_type = w.get("type")
            if hand_type:
                self._pending_winner_types[player_id] = int(hand_type)

        # Build final_stacks from hand-start chips + server profit delta.
        # WinnerRSP.profit gives each player's net gain/loss for the hand,
        # already accounting for uncalled bet returns and rake.
        # This is more accurate than seat_chips + winner.chips.
        final_stacks: dict[int, int] = dict(self._hand_start_chips)
        my_profit_delta: int = 0
        for p in msg.get("profit", []):
            uid = str(p.get("uid", ""))
            seat = self._uid_to_seat.get(uid, -1)
            if seat < 0:
                continue
            profit_chips = _chip_int(p.get("chips", 0), 0)
            if seat in final_stacks:
                final_stacks[seat] = final_stacks[seat] + profit_chips
            if self._my_uid and uid == self._my_uid:
                my_profit_delta = profit_chips
        # Fall back to seat_chips for any seat missing from profit.
        for seat, chips in self._seat_chips.items():
            if seat not in final_stacks:
                final_stacks[seat] = chips

        # The session's poker PnL is the running sum of these server-settled
        # results (_settle_my_hand); wallet samples only show the balances.
        self._seat_chips = dict(final_stacks)
        if self._my_seat is not None:
            self._my_chips = max(0, _chip_int(final_stacks.get(self._my_seat, self._my_chips), 0))
        self._record_bankroll_hand_point(final_stacks, my_profit_delta)

        self._api.hand_over(
            winner_ids=winner_ids,
            pot=total_pot,
            final_stacks=self._seat_map_to_player_ids(final_stacks),
            showdown_hands=(
                self._seat_showdown_to_player_ids(self._pending_showdown)
                if self._pending_showdown else None
            ),
            winner_hand_types=self._pending_winner_types or None,
            my_profit_delta=my_profit_delta,
        )
        self._pending_showdown = {}
        self._pending_winner_types = {}

        if self._my_seat is not None:
            self._check_hand_swing(my_profit_delta)

        inject = self._maybe_profit_lock_leave_reenter(final_stacks)
        if inject is not None:
            return inject
        # 选桌：每手结束时按桌上真人 / 人机数决定去留（打法本身不变）。
        inject = self._table_event("hand_end")
        if inject is not None:
            return inject
        # 留在这张桌：筹码短了就在桌上补码。
        return self._maybe_topup(final_stacks)

    def _check_hand_swing(self, profit_delta: int) -> None:
        """单手盈亏波动：|delta| >= 20BB 时发通知。

        通知里仍展示相对本手开局筹码的百分比；百分比基准是本手
        DealerInfo 记录的开局筹码（_hand_start_chips），不是牌局进行中
        的瞬时筹码（我们会不断下注，基数会变）。
        """
        bb = float(self._bb or 0.0)
        if bb <= 0 or self._my_seat is None:
            return
        start_chips = int(self._hand_start_chips.get(self._my_seat, 0))
        if start_chips <= 0:
            return
        abs_delta = abs(int(profit_delta))
        if abs_delta < 20 * bb:
            return
        hand_detail = ""
        if self._api is not None:
            hand_detail = self._api.last_hand_push_detail()
        fields = dict(
            profit_delta=int(profit_delta),
            start_chips=start_chips,
            big_blind=int(bb),
            hand_detail=hand_detail,
        )
        if self._hand_seq > 0:
            fields["hand_no"] = self._hand_seq
        self._notify("hand_swing", **fields)

    def _maybe_profit_lock_leave_reenter(
        self, final_stacks: dict[int, int]
    ) -> WireInject | None:
        """桌上筹码 >= 阈值则设置下一手离桌，并在离桌成功后以 100BB 进同一房间。

        设计：
          触发条件 = 桌上筹码 my_final >= PROFIT_LOCK_BB_THRESHOLD × BB
            - 对游戏抽水不敏感（桌上多少就带走多少）
            - 一手一判，不需要累计
          本次启动盈亏：
            - 服务端每手结算 WinnerRSP.profit 里自己那一项的累计（_settle_my_hand）
            - 与钱包余额、活动奖励、小游戏输赢无关
        """
        if self._skip_profit_lock:
            return None
        if (
            self._my_seat is None
            or self._profit_lock_reenter is not None
            or self._profit_lock_deferred is not None
            or self._table_switch is not None
        ):
            return None
        bb = float(self._bb or 0.0)
        if bb <= 0:
            return None
        room_id = _chip_int(self._table_room_id, 0)
        if room_id <= 0:
            log.warning(
                "[BOT] 盈利锁仓：尚无 table room_id，跳过（需 EnterRoomRSP.roomid 或 S2C 帧头 room_id）。",
            )
            return None
        lock_bb = int(config.PROFIT_LOCK_BB_THRESHOLD)
        threshold = int(lock_bb * bb)
        my_final = int(final_stacks.get(self._my_seat, 0))
        if my_final < threshold:
            return None

        buyin = int(100 * bb)
        pending = {
            "roomid": room_id,
            "byin_chips": buyin,
            "uid": self._my_uid,
            "leave_mode": "delay_leave",
            "delay_leave_requested": True,
            "delay_leave_confirmed": False,
            "delay_leave_retry_sent": False,
            # Keep trigger-time table chips for LeaveRoom success logs.
            "table_chips": my_final,
            "threshold_chips": threshold,
            "lock_bb": lock_bb,
        }
        self._profit_lock_deferred = dict(pending)
        self._profit_lock_reenter = dict(pending)
        msg = (
            f"[BOT] 盈利锁仓：桌上筹码 {my_final} >= {threshold}（{lock_bb}BB），"
            "已设置服务端下一手离桌，"
            f"再以 {buyin}（100BB）重进房间 {room_id}。离桌成功后采样余额计算本次启动盈亏。"
        )
        log.warning(msg)
        if self._api:
            self._api._log.note(msg)
        return "pb.DelayLeaveRoomREQ", {"flag": True}, 0.0

    def _on_delay_leave_room_rsp(self, msg: dict) -> WireInject | None:
        pending = self._profit_lock_reenter
        if pending is None or pending.get("leave_mode") != "delay_leave":
            return None

        code = _s2c_rsp_code(msg, 0)
        flag = bool(msg.get("flag", False))
        if code != 0 or not flag:
            log.warning(
                "[BOT] 盈利锁仓：DelayLeaveRoomRSP code=%s flag=%s，取消锁仓重进。",
                code,
                flag,
            )
            self._profit_lock_cancel_reenter()
            return None

        pending["delay_leave_confirmed"] = True
        if self._profit_lock_deferred is not None:
            self._profit_lock_deferred["delay_leave_confirmed"] = True
        log.warning("[BOT] 盈利锁仓：服务端已确认下一手离桌，等待 LeaveRoomRSP。")
        return None

    def _on_leave_room_rsp(self, msg: dict) -> WireInject | None:
        """离桌确认：盈利锁仓带买入重新进房，选桌换桌重新匹配，其余有筹码的离桌按异常离桌重进。"""
        code = _s2c_rsp_code(msg, 0)
        was_seated = bool(self._table_room_id) and self._my_seat is not None
        chips_before_leave = self._current_table_chips()
        if code in (0, 2, 3):
            # Invalidate pending actions and avoid a 45s graceful-leave wait
            # when the server has already put us back in the lobby.
            self._table_room_id = 0
            self._current_gameid = ""
            self._hand_seq += 1
            if self._shutdown_requested:
                self._profit_lock_cancel_reenter()
                self._bankroll_pending_action = None
                return self._mark_my_left_table("leave_room")
        if self._calibration_backpressure_leaving:
            code = _s2c_rsp_code(msg, 0)
            self._calibration_backpressure_leaving = False
            if code in (0, 2, 3):
                log.warning("[BOT] 校准队列积压：离桌成功，暂停继续进桌，等待 worker 消费。")
                return self._mark_my_left_table("leave_room")
            else:
                log.warning("[BOT] 校准队列积压：LeaveRoomRSP code=%s，未确认离桌成功。", code)
            return None

        switch = self._table_switch
        if switch is not None:
            if code in (0, 2, 3):
                self._table_switch = None
                self._room_tracker.reset()
                step = (self._table_policy.on_left(time.time(), ours=True)
                        if self._table_policy is not None else None)
                self._bankroll_pending_buyin_reason = "table_switch"
                log.warning("[BOT] 选桌：已离桌（%s），%s", switch.get("reason"),
                            "停止匹配" if step else "稍后重新匹配")
                if switch.get("played"):
                    # 下一张桌会重新买入，桌上筹码不再连续：把累计的对局盈亏报出来。
                    self._notify("table_leave", reason=switch.get("cause"),
                                 session_delta_chips=int(self._session_poker_pnl))
                if step:
                    self._table_step(step)
                return self._mark_my_left_table("leave_room")
            if switch.get("mode") == "leave":
                # 牌局进行中不能直接离桌（121）：改为本手结束后离桌。
                switch["mode"] = "delay"
                log.warning("[BOT] 选桌：LeaveRoomRSP code=%s，改用本手结束后离桌。", code)
                return "pb.DelayLeaveRoomREQ", {"flag": True}, 0.0
            log.warning("[BOT] 选桌：LeaveRoomRSP code=%s，等待重试。", code)
            return None
        if code in (0, 2, 3):
            self._room_tracker.reset()
            if self._table_policy is not None:
                self._table_policy.on_left(time.time(), ours=False)

        pending = self._profit_lock_reenter
        if pending is None:
            if code in (0, 2, 3):
                if (was_seated and chips_before_leave > 0 and self._auto_rejoin_fields
                        and not self._loss_stop
                        and not self._is_friend_room and not self._tournament_passthrough
                        and self._runtime_calibration_should_pause_play() is None):
                    self._mark_my_table_chips_zero()
                    log.warning("[BOT] 非破产、非锁仓离桌：将重新匹配。")
                    return self._request_bankroll_sample("unexpected_leave", action={
                        "kind": "unexpected_leave", "quickstart_fields": dict(self._auto_rejoin_fields),
                    })
                return self._mark_my_left_table("leave_room")
            return None
        # 与客户端 net:LeaveRoomRSP 一致：0/2/3 视为离桌成功路径（code 常省略=成功）
        if code not in (0, 2, 3):
            log.warning("[BOT] 盈利锁仓：LeaveRoomRSP code=%s，取消重进。", code)
            self._profit_lock_cancel_reenter()
            return None

        room_id = _chip_int(pending.get("roomid", 0), 0)
        byin = _chip_int(pending.get("byin_chips", 0), 0)
        table_chips = _chip_int(pending.get("table_chips", 0), 0)
        uid = pending.get("uid")
        self._profit_lock_reenter = None
        self._profit_lock_deferred = None
        self._mark_my_table_chips_zero()

        fields: dict = {"roomid": room_id, "byin_chips": byin}
        if uid:
            fields["uid"] = int(uid)
        delay = float(config.PROFIT_LOCK_REENTER_DELAY_SEC)
        delay = max(0.0, min(60.0, delay))
        log.info("[BOT] 盈利锁仓：离桌已确认 mode=%s", pending.get("leave_mode") or "leave_room")
        action = {
            "kind": "profit_lock",
            "enter_fields": fields,
            "delay_sec": delay,
            "table_chips": table_chips,
            "threshold_chips": _chip_int(pending.get("threshold_chips", 0), 0),
            "lock_bb": _chip_int(pending.get("lock_bb", config.PROFIT_LOCK_BB_THRESHOLD), int(config.PROFIT_LOCK_BB_THRESHOLD)),
            "room_id": room_id,
            "big_blind": int(self._bb or 0),
        }
        log.warning("[BOT] 盈利锁仓：已离桌，先采样余额再重进房间。")
        return self._request_bankroll_sample("profit_lock", action=action)

    def _on_notice_reby(self, msg: dict) -> WireInject | None:
        """Server notifies us that our chips hit 0 — rebuy window opened."""
        seat = msg.get("seatid", 0)  # pb omits field when value is 0
        if seat != self._my_seat:
            log.debug("[BOT] NoticeRebyRSP for seat=%d (not us, my_seat=%s), ignored", seat, self._my_seat)
            return None

        reby_left_time = msg.get("reby_left_time", 0)
        bb = float(self._bb or 1000)
        pause_status = self._runtime_calibration_should_pause_play()
        if pause_status is not None:
            log.warning(
                "[BOT] 校准队列积压：跳过自动续入，backlog=%.1fGB，rebuy 窗口 %d 秒。",
                float(pause_status.get("backlog_gb", 0.0) or 0.0),
                reby_left_time,
            )
            return None

        # 破产买入也是把筹码带上桌：100BB 放得下就买 100BB，放不下就买上限还容得下的最大一档，
        # 连最小一档都放不下，本次启动到此为止。
        rebuy_chips = self._capped_buyin(int(_BUYIN_BB * bb), bb)
        if rebuy_chips <= 0:
            log.warning("[BOT] ⚠️  筹码清零！净亏损已到上限，不再续入。rebuy 窗口 %d 秒。", reby_left_time)
            self._stop_for_loss_cap("破产买入")
            return None

        self._auto_rebuy_done += 1
        rebuy_nth = self._auto_rebuy_done

        self._mark_my_table_chips_zero()
        action = {
            "kind": "auto_rebuy",
            "nth": rebuy_nth,
            "rebuy_chips": rebuy_chips,
            "rebuy_window_sec": reby_left_time,
        }
        log.warning(
            "[BOT] ⚠️  筹码清零！自动续入 %d（%.0fBB） 第 %d 次，先采样余额再买入。rebuy 窗口 %d 秒。",
            rebuy_chips,
            rebuy_chips / bb,
            rebuy_nth,
            reby_left_time,
        )
        return self._request_bankroll_sample("auto_rebuy", action=action)


# ── Wire action conversion ─────────────────────────────────────────────────────

def _decision_to_wire(decision: BotDecision, *, current_bet: float = 0.0) -> tuple[int, int]:
    """Convert API raise-to amounts to the protocol's additional chips."""
    action = decision.action.lower()
    if action == "fold":  return 1, 0
    if action == "check": return 2, 0
    if action == "call":  return 3, 0
    if action == "raise": return 4, max(0, int(decision.amount) - int(current_bet))
    return 2, 0   # safe default
