"""
Bot bridge: translates proxy events → PokerFateAPI calls → wire actions.

Auto-detection:
  MY_SEAT_ID  ← pb.SitDownRSP.seatid
  BIG_BLIND   ← pb.EnterRoomRSP.room_info.bb / sngroom_info.bb
  SMALL_BLIND ← pb.EnterRoomRSP.room_info.sb / sngroom_info.sb
  (fallback to config values if messages aren't decoded yet)

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
import functools
import json
import logging
import random
import time
from pathlib import Path
from typing import TypeAlias

from pokerfate.api import PokerFateAPI, PlayerInfo, ActionEvent, BotDecision
from pf_intercept import config
from pf_intercept.action_types import ACTION_TYPE_TO_EVENT_ACTION, FOLD_ACTION_TYPES
from pf_intercept.collcard import _sync_collect_game
from pf_intercept.gamedata_fetcher import _sync_fetch, seed_from_server
from pf_intercept.http_api import load_auth_token
from pf_notify import notify
from pf_notify.templates import format_chips_km_signed

log = logging.getLogger("pf_bot")

WireInject: TypeAlias = tuple[str, dict] | tuple[str, dict, float]
WireInjectResult: TypeAlias = WireInject | list[WireInject] | None
InjectGuard: TypeAlias = tuple[str, int]

_MAX_INJECT_DELAY = float(config.ACTION_INJECT_DELAY_MAX_SEC)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_ROBOT_PLAYERS_FILE = _PROJECT_ROOT / "data" / "robot_players.json"


def _load_known_robot_uids() -> set[str]:
    try:
        data = json.loads(_ROBOT_PLAYERS_FILE.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return set()
    except Exception:
        log.exception("[ROBOT] failed to load %s", _ROBOT_PLAYERS_FILE)
        return set()
    robots = data.get("robots") if isinstance(data, dict) else {}
    if not isinstance(robots, dict):
        return set()
    return {str(uid) for uid in robots if str(uid)}


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
_SNG_GAME_TYPES = {10050301, 10060301, 40050301}
_FRIEND_GAME_TYPES = {20010103}
_POSITION_LABELS_AFTER_BB = ["UTG", "UTG+1", "UTG+2", "LJ", "HJ", "CO"]


def _is_sng_game_type(game_type) -> bool:
    return _chip_int(game_type, 0) in _SNG_GAME_TYPES


def _is_friend_game_type(game_type) -> bool:
    return _chip_int(game_type, 0) in _FRIEND_GAME_TYPES


def _seat_positions(seats: list[int], dealer: int) -> dict[int, str]:
    ordered = sorted(int(s) for s in seats)
    if not ordered:
        return {}

    n = len(ordered)
    try:
        dealer_idx = ordered.index(int(dealer))
    except ValueError:
        dealer_idx = 0

    if n == 1:
        return {ordered[0]: "BTN"}
    if n == 2:
        return {
            ordered[dealer_idx]: "BTN",
            ordered[(dealer_idx + 1) % n]: "BB",
        }

    btn_idx = dealer_idx
    sb_idx = (dealer_idx + 1) % n
    bb_idx = (dealer_idx + 2) % n
    out: dict[int, str] = {}
    for idx, seat in enumerate(ordered):
        if idx == btn_idx:
            out[seat] = "BTN"
        elif idx == sb_idx:
            out[seat] = "SB"
        elif idx == bb_idx:
            out[seat] = "BB"
        else:
            dist = (idx - bb_idx - 1) % n
            out[seat] = (
                _POSITION_LABELS_AFTER_BB[dist]
                if dist < len(_POSITION_LABELS_AFTER_BB)
                else "MP"
            )
    return out


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

    def __init__(self, max_auto_rebuy: int = 1, use_range_equity: bool = True) -> None:
        # Detected from game messages (may be pre-seeded by config)
        self._my_seat: int | None  = None
        self._my_uid:  str | None  = None
        self._bb:      float | None = config.BIG_BLIND
        self._sb:      float | None = config.SMALL_BLIND

        self._api: PokerFateAPI | None = None   # created once blinds are known

        # Auto-rebuy when chips hit 0 (NoticeRebyRSP）。
        # _max_auto_rebuy：启动时 CLI 上限，仅盈利锁仓成功回桌时 +1。
        # _auto_rebuy_done：本代理进程内累计已自动续入次数，进/出房间不重置（避免反复进出刷爆亏损）。
        self._max_auto_rebuy: int = max(1, min(20, int(max_auto_rebuy)))
        self._use_range_equity: bool = use_range_equity
        self._auto_rebuy_done: int = 0

        # 盈利锁仓：WinnerRSP 达标后先记入 _profit_lock_deferred；下一手 DealerInfoRSP 再发
        # LeaveRoom（避免与结算界面并发）；LeaveRoomRSP 成功后发 EnterRoom（100BB）
        self._profit_lock_deferred: dict[str, int | str | bool | None] | None = None
        self._profit_lock_reenter: dict[str, int | str | None] | None = None
        self._profit_lock_award_rebuy_after_enter: bool = False
        # 最近一次注入的 EnterRoomREQ 字段（失败时打日志 / 人工对照）
        self._profit_lock_last_enter_fields: dict | None = None
        # 累计盈亏（本次 proxy 启动起，单位筹码）：
        #   1) 盈利锁仓离桌成功时：+离桌时桌上筹码
        #   2) 盈利锁仓重进（100BB）：-100BB
        #   3) 破产自动续入（100BB）：-100BB
        # 启动时从 0 开始，不按每手 WinnerRSP.profit 逐手累加。
        self._session_pnl_chips: float = 0.0
        # 从最近一次成功进房 RSP 缓存，供 QuickStart 兜底（与客户端大厅一致）
        self._session_game_type: int = 0
        self._session_lobby_coin: int = 0
        # SNG/tournament rooms carry blinds in sngroom_info instead of room_info.
        # Cache the schedule so pb.BlindStatusBRC can update table blinds on level-up.
        self._sng_blind_schedule: dict[int, tuple[float, float]] = {}
        self._sng_blind_level: int = 0
        self._is_sng_room: bool = False
        self._is_friend_room: bool = False
        self._skip_profit_lock: bool = False
        self._skip_profit_lock_reason: str = ""
        self._skip_runtime_collection: bool = False
        self._skip_runtime_collection_reason: str = ""

        # C2S 帧里的 room_id 须与客户端 Net.packNetData 一致（GameModel:getRoomId）。
        # 部分 S2C（如 WinnerRSP）wire 上 room_id 可能为 0，要用进房时或任意非 0 帧补全。
        self._table_room_id: int = 0
        self._table_tid: int = 1
        self._current_gameid: str = ""
        self._hand_seq: int = 0
        self._auto_collected_gameids: set[str] = set()
        self._pending_injects: list[WireInject] = []
        self._last_hero_action_notify_sig: tuple | None = None
        self._last_hero_action_notify_at: float = 0.0

        # GameData API: 已拉取过的 uid（本次 proxy 进程内不重复拉）
        self._fetched_uids: set[str] = set()
        # 在 API 创建前到达的 server stats，缓存至 _ensure_api 创建后再注入
        self._pending_seeds: dict[int, dict] = {}   # uid -> {"data": raw stats, "name": display name}

        # GameData 无历史数据通知（每次 proxy 进程启动只发一次）
        self._gamedata_no_history_notified: bool = False

        # Session-level: real player names keyed by seat_id
        # Populated from EnterRoomRSP.table_status.seat[].player.name
        # and updated on SitDownBRC
        self._seat_names: dict[int, str] = {}
        # uid (str) → seat_id; built from EnterRoomRSP/SitDownBRC; used to
        # resolve WinnerRSP entries that carry uid but no seatid.
        self._uid_to_seat: dict[str, int] = {}
        self._seat_uids: dict[int, str] = {}
        self._current_hand_robot_seats: set[int] = set()
        self._current_hand_robot_uids: dict[int, str] = {}

        # Per-hand state
        self._stage:    int       = 0
        self._pot:      int       = 0
        self._my_bet:   int       = 0   # my chips in this street
        self._max_bet:  int       = 0   # highest bet this street
        self._my_chips: int       = 0
        self._street_bets: dict[int, int] = {}
        self._my_forced_post_this_street: bool = False
        self._folded:   set[int]  = set()
        self._all_seats: list[int] = []
        self._announced_stages: set[int] = set()
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

        # 房间逃离：连续破产计数（盈利锁仓会清零）；Leave 后 QuickStart
        self._room_escape_bust_count: int = 0
        self._room_escape_reenter: dict[str, bool] | None = None  # {"quickstart": True}

    # ── Public ────────────────────────────────────────────────────────────────

    def note_seen_room_id(self, room_id: int) -> None:
        """Update cached table room id from any S2C frame header (non-zero only)."""
        rid = _chip_int(room_id, 0)
        if rid != 0:
            self._table_room_id = rid

    def room_id_for_c2s(self, frame_room_id: int) -> int:
        """room_id to attach to injected C2S (match client Net.packNetData)."""
        fr = _chip_int(frame_room_id, 0)
        if fr != 0:
            return fr
        return _chip_int(self._table_room_id, 0)

    def notify_inject_failed(self, inject_type: str) -> None:
        """Proxy could not serialize/send a C2S frame — drop dependent bot state."""
        if inject_type == "pb.LeaveRoomREQ" and (
            self._profit_lock_reenter is not None
            or self._profit_lock_deferred is not None
            or self._room_escape_reenter is not None
        ):
            log.warning("[BOT] LeaveRoom 未发出，已取消离桌后续（盈利锁仓 / 房间逃离）。")
            self._profit_lock_cancel_reenter()
            self._room_escape_reenter = None
        elif inject_type == "pb.EnterRoomREQ" and self._profit_lock_award_rebuy_after_enter:
            log.warning("[BOT] 盈利锁仓：EnterRoom 未发出，已取消续入次数奖励。")
            self._profit_lock_award_rebuy_after_enter = False
            self._profit_lock_last_enter_fields = None
        elif inject_type == "pb.QuickStartREQ":
            log.warning("[BOT] 盈利锁仓：QuickStartREQ 编码/发送失败，请手动从大厅进桌。")

    def _profit_lock_cancel_reenter(self) -> None:
        self._profit_lock_deferred = None
        self._profit_lock_reenter = None
        self._profit_lock_award_rebuy_after_enter = False
        self._profit_lock_last_enter_fields = None

    def _clear_room_escape_stats_for_rematch(self) -> None:
        """换桌匹配前清零统计，避免回到同房时立刻再次触发逃离。"""
        self._room_escape_bust_count = 0

    def _show_my_card_request(
        self,
        *,
        pos: int,
        flag: int = 1,
        delay_sec: float = 0.0,
    ) -> WireInject | None:
        """Build pb.ShowMyCardREQ for one of our hole-card positions."""
        gameid = str(self._current_gameid or "").strip()
        if not gameid or gameid == "0":
            log.warning("[BOT] 亮牌：缺少 gameid，跳过展示第 %s 张手牌。", pos)
            return None
        if pos <= 0:
            return None
        return (
            "pb.ShowMyCardREQ",
            {
                "gameid": gameid,
                "pos": int(pos),
                "flag": int(flag),
            },
            max(0.0, float(delay_sec)),
        )

    def show_my_card(self, pos: int, *, flag: int = 1, delay_sec: float = 0.0) -> bool:
        """Queue one ShowMyCardREQ. Decision logic calls this when it wants to reveal."""
        req = self._show_my_card_request(pos=pos, flag=flag, delay_sec=delay_sec)
        if req is None:
            return False
        self._pending_injects.append(req)
        return True

    def show_my_hole_cards(self, count: int = 2) -> int:
        """Queue ShowMyCardREQ for our first `count` hole cards."""
        requests: list[WireInject] = []
        for idx, pos in enumerate(range(1, min(2, int(count)) + 1)):
            req = self._show_my_card_request(pos=pos, flag=1, delay_sec=idx * 0.05)
            if req is not None:
                requests.append(req)
        self._pending_injects.extend(requests)
        if requests:
            log.info(
                "[BOT] 亮牌：已排队展示自己的 %d 张手牌 gameid=%s",
                len(requests),
                self._current_gameid,
            )
        return len(requests)

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
        """Room-aware notification wrapper. SNG/tournament/friend rooms stay quiet."""
        if self._is_sng_room:
            log.debug("[BOT] SNG room: skip notify event=%s", event)
            return
        if self._is_friend_room:
            log.debug("[BOT] friend room: skip notify event=%s", event)
            return
        notify(event, **fields)

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
        if   type_name == "pb.SelfUserInfoRSP": self._on_self_user_info(msg)
        elif type_name == "pb.SitDownRSP":      self._on_sit_down(msg)
        elif type_name == "pb.SitDownBRC":       self._on_sit_down_brc(msg)
        elif type_name == "pb.EnterRoomRSP":     return self._on_enter_room(msg)
        elif type_name == "pb.DealerInfoRSP":    return self._on_dealer_info(msg)
        elif type_name == "pb.HandCardRSP":      return self._on_hand_card(msg)
        elif type_name == "pb.RoundStartBRC":    self._on_round_start(msg)
        elif type_name == "pb.ActionBRC":        self._on_action_brc(msg)
        elif type_name == "pb.RoundOverBRC":     self._on_round_over(msg)
        elif type_name == "pb.ActionNotifyBRC":  return self._on_action_notify(msg)
        elif type_name == "pb.ShowHandRSP":      self._on_show_hand(msg)
        elif type_name == "pb.BlindStatusBRC":   self._on_blind_status(msg)
        elif type_name == "pb.WinnerRSP":        return self._on_winner(msg)
        elif type_name == "pb.LeaveRoomRSP":     return self._on_leave_room_rsp(msg)
        elif type_name == "pb.NoticeRebyRSP":    return self._on_notice_reby(msg)
        return None

    # ── Session setup ─────────────────────────────────────────────────────────

    def _set_my_seat(self, seat: int, reason: str) -> None:
        if seat < 0:
            return
        if self._my_seat == seat:
            return
        old = self._my_seat
        self._my_seat = seat
        log.info("[BOT] My seat detected: %s -> %d (%s)", old, seat, reason)
        # Recreate API when seat changes (reconnect / table rejoin).
        self._api = None

    def _on_self_user_info(self, msg: dict) -> None:
        brief = msg.get("brief") or {}
        uid = brief.get("uid")
        if uid:
            self._my_uid = str(uid)
            log.info("[BOT] My uid detected: %s", self._my_uid)

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

    def _remember_sng_blinds(self, sng_info: dict) -> tuple[float, float]:
        """Cache SNG blind schedule and return the current blind pair, if known."""
        if not sng_info:
            self._sng_blind_schedule = {}
            self._sng_blind_level = 0
            return 0.0, 0.0

        schedule: dict[int, tuple[float, float]] = {}
        for item in sng_info.get("blind_list", []) or []:
            level = _chip_int(item.get("blind_level"), 0)
            bb = _chip_float(item.get("big_blind"), 0.0)
            sb = _chip_float(item.get("small_blind"), 0.0)
            if level > 0 and bb > 0:
                schedule[level] = (bb, sb if sb > 0 else bb / 2.0)
        if schedule:
            self._sng_blind_schedule = schedule

        level = _chip_int(sng_info.get("blind_level"), 0)
        if level > 0:
            self._sng_blind_level = level
            if level in self._sng_blind_schedule:
                return self._sng_blind_schedule[level]

        bb = _chip_float(sng_info.get("bb"), 0.0)
        sb = _chip_float(sng_info.get("sb"), 0.0)
        if bb > 0:
            return bb, sb if sb > 0 else bb / 2.0
        return 0.0, 0.0

    def _on_enter_room(self, msg: dict) -> WireInjectResult:
        self._profit_lock_reenter = None
        self._profit_lock_deferred = None
        self._room_escape_reenter = None

        if "game_type" in msg:
            self._session_game_type = _chip_int(msg.get("game_type"), 0)
        sng_info = msg.get("sngroom_info") or {}
        friend_info = msg.get("friend_room_info") or {}
        self._is_sng_room = _is_sng_game_type(self._session_game_type)
        self._is_friend_room = (
            _is_friend_game_type(self._session_game_type)
            or bool(friend_info)
        )
        if self._is_sng_room:
            self._skip_profit_lock_reason = "sng"
        elif self._is_friend_room:
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
            self._clear_room_escape_stats_for_rematch()
        fallback_inject: tuple[str, dict, float] | None = None
        if self._is_sng_room and self._profit_lock_award_rebuy_after_enter:
            log.warning("[BOT] SNG 房间：取消盈利锁仓重进奖励/通知。")
            self._profit_lock_award_rebuy_after_enter = False
            self._profit_lock_last_enter_fields = None
        elif self._profit_lock_award_rebuy_after_enter:
            if self._profit_lock_last_enter_fields is None:
                log.warning("[BOT] 盈利锁仓：收到 EnterRoomRSP 但没有待确认的 EnterRoomREQ，忽略重进奖励。")
                self._profit_lock_award_rebuy_after_enter = False
            elif code == 0:
                reenter_buyin = _chip_int(
                    (self._profit_lock_last_enter_fields or {}).get("byin_chips", 0),
                    0,
                )
                if reenter_buyin > 0:
                    self._session_pnl_chips -= float(reenter_buyin)
                self._max_auto_rebuy += 1
                self._profit_lock_last_enter_fields = None
                pnl_str = format_chips_km_signed(self._session_pnl_chips)
                log.warning(
                    "[BOT] 盈利锁仓：已重新进房，扣除买入 %d，自动续入次数上限 +1 → %d。累计盈亏 %s（筹码）",
                    reenter_buyin,
                    self._max_auto_rebuy,
                    pnl_str,
                )
                self._profit_lock_award_rebuy_after_enter = False
            else:
                log.warning(
                    "[BOT] 盈利锁仓：重新进房失败 code=%s，未增加续入次数。",
                    code,
                )
                if self._profit_lock_last_enter_fields is not None:
                    log.warning(
                        "[BOT] 盈利锁仓 [EnterRoomREQ 备份，可对客户端抓包对照] %s",
                        self._profit_lock_last_enter_fields,
                    )
                self._profit_lock_award_rebuy_after_enter = False
                fallback_inject = self._profit_lock_quick_start_fallback()

        rid = msg.get("roomid")
        if rid is not None:
            self._table_room_id = _chip_int(rid, 0)
            if self._table_room_id:
                log.info("[BOT] Table room_id=%d (EnterRoomRSP)", self._table_room_id)

        # Blind detection. Cash/friend rooms use room_info; SNG rooms use
        # sngroom_info and BlindStatusBRC levels, matching the client GF.isSNG path.
        room_info = msg.get("room_info") or {}
        if self._is_sng_room:
            bb_sng, sb_sng = self._remember_sng_blinds(sng_info)
            if bb_sng > 0:
                source = "sngroom_info"
                if self._sng_blind_level > 0:
                    source = f"{source}.level{self._sng_blind_level}"
                self._apply_table_blinds(
                    big_blind=bb_sng,
                    small_blind=sb_sng,
                    source=source,
                )
        elif room_info.get("bb"):
            self._sng_blind_schedule = {}
            self._sng_blind_level = 0
            self._apply_table_blinds(
                big_blind=room_info.get("bb"),
                small_blind=room_info.get("sb"),
                source="room_info",
            )

        # Seed player names from current table snapshot + trigger server stats fetch
        table_status = msg.get("table_status") or {}
        tid = _chip_int(table_status.get("tid", 0), 0)
        if tid > 0:
            self._table_tid = tid
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

        # 重连时恢复公共牌。若 table_status 携带了 board（说明局中重连），直接写入 api._board，
        # 并标记已处理的街道，避免后续 RoundStartBRC 重复 deal_board 累加出重复牌。
        stage = table_status.get("stage", 1)
        board_ids = table_status.get("board", [])
        if board_ids and stage > 1 and self._api:
            cards = [_card_str(c) for c in board_ids if _card_str(c)]
            if cards:
                self._api.restore_board(cards)
                # 已处于哪一街就把该街及之前的 stage 全部标记，
                # 防止 _on_round_start 重复处理（turn/river 会作为新 stage 正常到来）
                for s in range(2, stage + 1):
                    self._announced_stages.add(s)

        playing_status = msg.get("playing_status") or {}
        if self._enter_room_playing_status_is_current_hand(table_status, playing_status):
            self._restore_hole_cards_from_playing_status(playing_status)
            restored_action = self._action_from_enter_room_playing_status(table_status, playing_status)
        else:
            restored_action = None

        if fallback_inject and restored_action:
            if isinstance(restored_action, list):
                return [fallback_inject, *restored_action]
            return [fallback_inject, restored_action]
        return restored_action or fallback_inject

    def _profit_lock_quick_start_fallback(
        self,
        context: str = "盈利锁仓",
    ) -> WireInject | None:
        """按大厅 QuickStart 随机配桌（LobbyByinDialog 同款字段）。"""
        bb = float(self._bb or 0.0)
        if bb <= 0:
            log.warning("[BOT] %s：无法 QuickStart（BB 未知）。", context)
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
        log.warning(
            "[BOT] %s：%.1fs 后发送 QuickStartREQ（随机桌，同盲注/100BB）: %s",
            context,
            delay,
            fields,
        )
        return "pb.QuickStartREQ", fields, delay

    def _on_sit_down_brc(self, msg: dict) -> None:
        """A player sat down — update name map from SitDownBRC.status."""
        seat_status = msg.get("status") or {}
        self._extract_seat_name(seat_status)
        self._trigger_gamedata_fetch(seat_status)

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

    def _seat_player_name(self, seat: int) -> str:
        return self._seat_names.get(seat) or f"Player_{seat}"

    def _seat_map_to_player_ids(self, values: dict[int, object]) -> dict[int, object]:
        return {self._seat_to_player_id(seat): value for seat, value in values.items()}

    def _seat_list_to_player_ids(self, seats: list[int]) -> list[int]:
        return [self._seat_to_player_id(seat) for seat in seats]

    def _seat_set_to_player_ids(self, seats: set[int]) -> set[int]:
        return {self._seat_to_player_id(seat) for seat in seats}

    def _seat_uid_map_to_player_ids(self, seat_uids: dict[int, str]) -> dict[int, str]:
        return {self._seat_to_player_id(seat): uid for seat, uid in seat_uids.items()}

    def _seat_showdown_to_player_ids(self, hands: dict[int, list[str]]) -> dict[int, list[str]]:
        return {self._seat_to_player_id(seat): cards for seat, cards in hands.items()}

    def _snapshot_current_hand_robots(self, seats: list[int]) -> None:
        """Freeze robot seats for this hand so later joins/leaves do not mutate it."""
        known_robot_uids = _load_known_robot_uids()
        self._current_hand_robot_seats = set()
        self._current_hand_robot_uids = {}
        if not known_robot_uids:
            return
        for seat in seats:
            uid = self._seat_uids.get(seat)
            if seat == self._my_seat or (self._my_uid and uid == self._my_uid):
                continue
            if uid and uid in known_robot_uids:
                self._current_hand_robot_seats.add(seat)
                self._current_hand_robot_uids[seat] = uid
        if self._current_hand_robot_seats:
            details = ", ".join(
                f"seat{seat}:{self._seat_names.get(seat, '')}({self._current_hand_robot_uids.get(seat, '')})"
                for seat in sorted(self._current_hand_robot_seats)
            )
            log.info("[ROBOT] current hand has known robot(s): %s", details)

    def _trigger_gamedata_fetch(self, seat_status: dict) -> None:
        """Fire-and-forget async fetch of 30-day server stats for one seat."""
        player = seat_status.get("player") or {}
        uid = player.get("uid")
        if not uid:
            return
        uid_str = str(uid)
        # Skip self
        if uid_str == self._my_uid:
            return
        # Only fetch once per uid per proxy session
        if uid_str in self._fetched_uids:
            return
        self._fetched_uids.add(uid_str)
        seat = _chip_int(seat_status.get("seatid", 0), 0)
        name = (seat_status.get("player") or {}).get("name", "")
        log.info("[gamedata] 触发拉取 %s", name or uid_str)
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self._do_gamedata_fetch(int(uid), seat, name))
        except RuntimeError:
            log.warning("[gamedata] uid=%s: 无事件循环，跳过", uid_str)

    async def _do_gamedata_fetch(self, uid: int, seat: int, name: str = "") -> None:
        """Async: fetch stats and write into opponent model (or buffer if API not ready)."""
        http_host  = config.GAMEDATA_HTTP_HOST
        chnl       = config.GAMEDATA_CHNL
        game_type  = config.GAMEDATA_GAME_TYPE

        pname = name or self._seat_names.get(seat) or f"seat{seat}"

        token = load_auth_token()
        if not token:
            log.warning("[gamedata] %s: auth_token.txt 缺失，跳过", pname)
            return

        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(
            None, _sync_fetch, uid, http_host, chnl, game_type, token
        )

        if not result:
            log.warning("[gamedata] %s: 请求无响应", pname)
            return
        if result.get("code") != 0:
            code = result.get("code")
            if code == -2:
                log.info("[gamedata] %s: 无历史数据 (code=-2)", pname)
                if not self._gamedata_no_history_notified:
                    self._gamedata_no_history_notified = True
                    self._notify("gamedata_no_history")
            else:
                log.warning("[gamedata] %s: 服务端错误 code=%s msg=%s",
                            pname, code, result.get("msg") or result)
            return

        data = result.get("data") or {}
        if not data or not data.get("play_times"):
            log.info("[gamedata] %s: 服务端无历史数据 (play_times=0)", pname)
            return

        if self._api is not None:
            om = self._api._bot.opponent_model
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

    def _reset_hand_local_state(self, *, stage: int = 1) -> None:
        self._stage = stage
        self._pot = 0
        self._my_bet = 0
        self._max_bet = 0
        self._street_bets = {}
        self._my_forced_post_this_street = False
        self._folded = set()
        self._announced_stages = set()
        self._hole_cards_count = 0
        self._pending_showdown = {}
        self._pending_winner_types = {}
        self._pending_injects = []

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
        seat_positions = _seat_positions(self._all_seats, dealer_seat)
        self._snapshot_current_hand_robots(self._all_seats)
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
            players.append(PlayerInfo(
                player_id=self._seat_to_player_id(seat),
                name=self._seat_player_name(seat),
                stack=chips,
                position=seat_positions.get(seat, ""),
            ))

        self._apply_pending_seeds_for_players(players)
        self._api.new_hand(
            players=players,
            dealer_id=self._seat_to_player_id(dealer_seat),
            hand_number=self._hand_seq,
        )
        log.warning(
            "[BOT] 重连恢复：检测到 gameid 切换 %s -> %s，已从 EnterRoomRSP.table_status 重建当前手。",
            previous_gameid or "<none>",
            gameid,
        )
        return True

    def _sync_stacks_from_table_snapshot(self, table_status: dict) -> None:
        """用 EnterRoomRSP.table_status 对齐本地筹码快照。

        hand_chips 是当前剩余筹码；begin_chips 才是本手开局筹码。
        WinnerRSP.profit 需要加在 begin_chips 上，不能用局中剩余筹码当基准。
        """
        for seat_status in table_status.get("seat", []) or []:
            if not _seat_status_has_player(seat_status):
                continue
            seat = _chip_int(seat_status.get("seatid", 0), 0)
            if "seatid" not in seat_status:
                log.debug(
                    "[BOT] table_status seat missing seatid; assume 0: %s",
                    seat_status,
                )
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
        log.warning("[BOT] 重连恢复：EnterRoomRSP.playing_status 仍轮到我行动，补一次决策。")
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
            use_range_equity=self._use_range_equity,
        )
        if self._skip_runtime_collection:
            self._api.set_runtime_collection_enabled(
                False,
                self._skip_runtime_collection_reason,
            )
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
        seat_positions = _seat_positions(self._all_seats, dealer_seat)
        self._snapshot_current_hand_robots(self._all_seats)
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
            ))

        # 应用 API 创建前已缓冲的 server stats：
        # 必须在 new_hand（内部调用 register_name）之前 pre-register 玩家名，
        # 否则 opponent_model 里 seat 还映射着上一局的旧玩家，seed 会写错位置。
        self._apply_pending_seeds_for_players(players)

        self._api.new_hand(
            players=players,
            dealer_id=self._seat_to_player_id(dealer_seat),
            hand_number=self._hand_seq,
        )

        # 盈利锁仓：上一手 Winner 已达标则等到本手 DealerInfo（下一手开始）再离桌
        deferred = self._profit_lock_deferred
        if deferred is not None:
            self._profit_lock_deferred = None
            room_id = _chip_int(deferred.get("roomid", 0), 0)
            byin = _chip_int(deferred.get("byin_chips", 0), 0)
            seat_reserve = bool(deferred.get("seat_reserve", True))
            self._profit_lock_reenter = {
                "roomid": room_id,
                "byin_chips": byin,
                "uid": deferred.get("uid"),
                "seat_reserve": seat_reserve,
                "table_chips": _chip_int(deferred.get("table_chips", 0), 0),
            }
            log.warning(
                "[BOT] 盈利锁仓：已收到下一手 DealerInfo，现离桌（留座=%s）再以 %d（100BB）重进房间 %d。",
                seat_reserve,
                byin,
                room_id,
            )
            return "pb.LeaveRoomREQ", {"seat_reserve": seat_reserve}, 0.0

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
            self._api.deal_hole_cards(cards)
        elif cards:
            log.warning("[BOT] Incomplete hole cards (%d): %s", len(cards), cards)
        return None

    def _on_round_start(self, msg: dict) -> None:
        stage = msg.get("stage", 1)
        self._stage   = stage
        self._my_bet  = 0
        self._max_bet = 0
        self._street_bets = {}
        self._my_forced_post_this_street = False

        board_ids = msg.get("board", [])
        if board_ids and stage not in self._announced_stages and self._api:
            self._announced_stages.add(stage)
            cards = [_card_str(c) for c in board_ids if _card_str(c)]
            if cards:
                # Keep display/log pot aligned with bridge-side real-time pot tracking.
                self._api.deal_board(
                    cards,
                    street=_STAGE_TO_STREET.get(stage, "flop"),
                    pot=self._pot,
                )

    def _on_blind_status(self, msg: dict) -> None:
        if not self._is_sng_room:
            return
        level = _chip_int(msg.get("blind_level"), 0)
        if level <= 0:
            return
        self._sng_blind_level = level
        pair = self._sng_blind_schedule.get(level)
        if pair is None:
            log.debug("[BOT] BlindStatusBRC level=%d but no SNG blind schedule cached", level)
            return
        bb, sb = pair
        self._apply_table_blinds(
            big_blind=bb,
            small_blind=sb,
            source=f"BlindStatusBRC.level{level}",
        )

    def _on_action_brc(self, msg: dict) -> None:
        seat        = _chip_int(msg.get("seatid", 0), 0)
        action_type = msg.get("action_type", 1)
        chips       = _chip_int(msg.get("chips", 0))
        hand_chips  = msg.get("hand_chips")

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

        if seat == self._my_seat:
            self._my_bet = total_street_bet
            if action_type in (8, 9, 10, 11, 14) and chips > 0:
                self._my_forced_post_this_street = True
            if hand_chips is not None:
                self._my_chips = _chip_int(hand_chips)
            return   # don't feed our own actions into the opponent model

        if self._api is None:
            return
        action_str = ACTION_TYPE_TO_EVENT_ACTION.get(action_type)
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
        ))

    def _on_round_over(self, msg: dict) -> None:
        pool = msg.get("pool", [])
        if pool:
            self._pot = sum(_chip_int(p, 0) for p in pool)

    def _decision_purpose(self) -> str:
        if self._api is None:
            return ""
        getter = getattr(self._api, "last_decision_diagnostics", None)
        if not callable(getter):
            return ""
        try:
            diag = getter() or {}
        except Exception:
            log.exception("[BOT] failed to read decision diagnostics")
            return ""
        return str(diag.get("final_purpose") or "").split("→", 1)[0].strip()

    def _maybe_show_pure_bluff_before_action(self, decision: BotDecision) -> None:
        if (decision.action or "").lower() != "raise":
            return
        if self._decision_purpose() != "pure_bluff_river":
            return
        # Auto reveal is disabled while pure-bluff show strategy is under review.
        # shown = self.show_my_hole_cards()
        # if shown:
        #     log.info("[BOT] 纯诈唬亮牌：ActionREQ 前展示 %d 张手牌。", shown)

    def _on_action_notify(self, msg: dict) -> WireInject | None:
        if self._api is None or self._my_seat is None:
            return None
        seat = _chip_int(msg.get("seatid", 0), 0)
        if seat != self._my_seat:
            log.debug("[BOT] Ignore ActionNotify seat=%d my_seat=%d", seat, self._my_seat)
            return None

        call_need = _chip_int(msg.get("call_need_chips", 0))
        self._last_hero_action_notify_sig = self._hero_action_notify_signature(msg)
        self._last_hero_action_notify_at = time.monotonic()

        # Sometimes ActionNotify arrives before a full HandCardRSP payload.
        # Avoid crashing preflop strategy on incomplete hole cards.
        if self._hole_cards_count < 2:
            log.warning("[BOT] ActionNotify before full hole cards (%d); fallback action", self._hole_cards_count)
            street_fb = _STAGE_TO_STREET.get(self._stage, "preflop")
            if call_need == 0:
                fb = BotDecision(action="check", amount=0.0)
                delay_sec = _inject_delay_before_action(street_fb, fb, self._pot, self._bb or 0.0)
                return "pb.ActionREQ", {"action_type": 2, "chips": 0}, delay_sec
            fb = BotDecision(action="fold", amount=0.0)
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

        action_type, chips = _decision_to_wire(decision)
        self._maybe_show_pure_bluff_before_action(decision)
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

            winner_ids.append(self._seat_to_player_id(seat))

            # Capture server-provided hand type (authoritative)
            hand_type = w.get("type")
            if hand_type:
                self._pending_winner_types[self._seat_to_player_id(seat)] = int(hand_type)

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

        # NOTE: per-hand profit_delta is NOT folded into _session_pnl_chips.
        # _session_pnl_chips is used for notification display only; it
        # accumulates "on-table chips brought away" at leave-success (see
        # _on_leave_room_rsp), minus rebuy / reenter buy-ins. The trigger
        # condition for profit_lock is the on-table stack (my_final),
        # NOT the session PnL — see _maybe_profit_lock_leave_reenter.
        # Earlier commits tried per-hand deltas from WinnerRSP.profit;
        # that conflated rake-sensitive bookkeeping with the trigger, and
        # broke the "simple" design. The on-table-trigger + table_chips
        # accumulate design is the intended one.

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
            robot_player_ids=self._seat_set_to_player_ids(self._current_hand_robot_seats),
            robot_player_uids=self._seat_uid_map_to_player_ids(self._current_hand_robot_uids),
        )
        self._pending_showdown = {}
        self._pending_winner_types = {}

        if self._my_seat is not None:
            self._check_hand_swing(my_profit_delta)

        reasons = self._api.last_auto_collect_reasons()
        self._maybe_auto_collect_current_hand(reasons)

        return self._maybe_profit_lock_leave_reenter(final_stacks)

    def _maybe_auto_collect_current_hand(self, reasons: list[str]) -> bool:
        if not getattr(config, "AUTO_COLLECT_SPECIAL_HANDS_ENABLED", True):
            return False
        if self._is_sng_room or self._is_friend_room:
            log.debug(
                "[BOT] 自动收藏：特殊房间跳过 gameid=%s sng=%s friend=%s",
                self._current_gameid,
                self._is_sng_room,
                self._is_friend_room,
            )
            return False
        reasons = [str(r) for r in reasons if str(r)]
        if not reasons:
            return False

        gameid = str(self._current_gameid or "").strip()
        if not gameid or gameid == "0":
            log.warning("[BOT] 自动收藏：命中 %s，但缺少 gameid，跳过。", "/".join(reasons))
            return False
        if gameid in self._auto_collected_gameids:
            return False
        self._auto_collected_gameids.add(gameid)

        room_id = _chip_int(self._table_room_id, 0)
        tid = _chip_int(self._table_tid, 1)
        reason = "/".join(reasons)
        log.warning(
            "[BOT] 自动收藏：gameid=%s roomid=%s tid=%s reason=%s",
            gameid,
            room_id,
            tid,
            reason,
        )

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            _sync_collect_game(gameid, roomid=room_id, tid=tid, reason=reason)
            return True

        loop.run_in_executor(
            None,
            functools.partial(
                _sync_collect_game,
                gameid,
                roomid=room_id,
                tid=tid,
                reason=reason,
            ),
        )
        return True

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
        """桌上筹码 >= 阈值则记在 deferred，下一手 DealerInfo 再离桌并以 100BB 进同一房间.

        设计：
          触发条件 = 桌上筹码 my_final >= PROFIT_LOCK_BB_THRESHOLD × BB
            - 对游戏抽水不敏感（桌上多少就带走多少）
            - 一手一判，不需要累计
          累计盈亏 _session_pnl_chips（仅用于通知显示）：
            - 启动时 0；首次进房买入不扣（~100 BB 偏差）
            - LeaveRoomRSP 成功时 += 当前桌上筹码
            - 自动续入 -= 100 BB（NoticeRebyRSP → RebyREQ）
            - 盈利锁仓重进 -= 100 BB
        """
        if self._skip_profit_lock:
            return None
        if (
            self._my_seat is None
            or self._profit_lock_reenter is not None
            or self._profit_lock_deferred is not None
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
        seat_reserve = bool(config.PROFIT_LOCK_LEAVE_SEAT_RESERVE)
        self._profit_lock_deferred = {
            "roomid": room_id,
            "byin_chips": buyin,
            "uid": self._my_uid,
            "seat_reserve": seat_reserve,
            # Keep trigger-time table chips for LeaveRoom success logs.
            "table_chips": my_final,
        }
        self._room_escape_bust_count = 0
        # 通知展示触发时的预估累计；真正入账等 LeaveRoomRSP 成功，避免离桌失败后重复触发重复累计。
        pnl_chips = self._session_pnl_chips + float(my_final)
        self._notify(
            "profit_lock_trigger",
            stack_chips=my_final,
            threshold_chips=threshold,
            lock_bb=lock_bb,
            room_id=room_id,
            big_blind=int(bb),
            pnl_chips=pnl_chips,
        )
        pnl_str = format_chips_km_signed(pnl_chips)
        msg = (
            f"[BOT] 盈利锁仓：桌上筹码 {my_final} >= {threshold}（{lock_bb}BB），"
            f"将在下一手 DealerInfo 开始后离桌（留座={seat_reserve}）"
            f"再以 {buyin}（100BB）重进房间 {room_id}。累计盈亏 {pnl_str}（筹码）"
        )
        log.warning(msg)
        if self._api:
            self._api._log.note(msg)
        return None

    def _on_leave_room_rsp(self, msg: dict) -> WireInject | None:
        """盈利锁仓：离桌成功后带买入重新进房；房间逃离：离桌后 QuickStart。"""
        esc = self._room_escape_reenter
        if esc is not None and esc.get("quickstart"):
            code = _s2c_rsp_code(msg, 0)
            if code not in (0, 2, 3):
                log.warning("[BOT] 房间逃离：LeaveRoomRSP code=%s，取消 QuickStart。", code)
                self._room_escape_reenter = None
                return None
            self._room_escape_reenter = None
            qs = self._profit_lock_quick_start_fallback("房间逃离")
            if qs is None:
                log.warning("[BOT] 房间逃离：无法 QuickStart（BB 未知）。")
            return qs

        pending = self._profit_lock_reenter
        if pending is None:
            return None
        code = _s2c_rsp_code(msg, 0)
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

        if table_chips > 0:
            self._session_pnl_chips += float(table_chips)
            log.warning(
                "[BOT] 盈利锁仓：离桌成功，累计盈亏 +%d（离桌桌上筹码），当前累计 %s（筹码）",
                table_chips,
                format_chips_km_signed(self._session_pnl_chips),
            )

        fields: dict = {"roomid": room_id, "byin_chips": byin}
        if uid:
            fields["uid"] = int(uid)
        self._profit_lock_last_enter_fields = dict(fields)
        self._profit_lock_award_rebuy_after_enter = True
        delay = float(config.PROFIT_LOCK_REENTER_DELAY_SEC)
        delay = max(0.0, min(60.0, delay))
        log.info(
            "[BOT] 盈利锁仓 [LeaveRoomREQ 已发] %s",
            {"seat_reserve": bool(pending.get("seat_reserve", False))},
        )
        log.info("[BOT] 盈利锁仓 [EnterRoomREQ 将发送] %s（%.1fs 后）", fields, delay)
        log.warning(
            "[BOT] 盈利锁仓：已离桌，%.1fs 后发 EnterRoomREQ roomid=%d byin_chips=%d",
            delay,
            room_id,
            byin,
        )
        return "pb.EnterRoomREQ", fields, delay

    def _on_notice_reby(self, msg: dict) -> WireInject | None:
        """Server notifies us that our chips hit 0 — rebuy window opened."""
        seat = msg.get("seatid", 0)  # pb omits field when value is 0
        if seat != self._my_seat:
            log.debug("[BOT] NoticeRebyRSP for seat=%d (not us, my_seat=%s), ignored", seat, self._my_seat)
            return None

        reby_left_time = msg.get("reby_left_time", 0)
        rebuy_chips = int(100 * (self._bb or 1000))

        if self._auto_rebuy_done >= self._max_auto_rebuy:
            log.warning(
                "[BOT] ⚠️  筹码清零！已达本房间最大自动续入次数 %d/%d，不再续入。rebuy 窗口 %d 秒。",
                self._auto_rebuy_done,
                self._max_auto_rebuy,
                reby_left_time,
            )
            return None

        esc_enabled = bool(config.ROOM_ESCAPE_ENABLED)
        bust_need = max(1, int(config.ROOM_ESCAPE_CONSECUTIVE_BUSTS))
        if esc_enabled:
            self._room_escape_bust_count += 1
            if self._room_escape_bust_count >= bust_need:
                bust_count = self._room_escape_bust_count
                self._clear_room_escape_stats_for_rematch()
                self._room_escape_reenter = {"quickstart": True}
                self._notify(
                    "room_escape",
                    bust_count=bust_count,
                    bust_need=bust_need,
                    byin_chips=rebuy_chips,
                    room_id=_chip_int(self._table_room_id, 0),
                    big_blind=int(self._bb or 0),
                    rebuy_window_sec=reby_left_time,
                )
                log.warning(
                    "[BOT] 房间逃离：连续破产 %d 次（中间无盈利锁仓），离桌后 QuickStart 换桌。",
                    bust_need,
                )
                return "pb.LeaveRoomREQ", {"seat_reserve": False}, 0.0

        self._auto_rebuy_done += 1
        self._session_pnl_chips -= float(rebuy_chips)
        pnl_chips = self._session_pnl_chips
        self._notify(
            "auto_rebuy",
            nth=self._auto_rebuy_done,
            max_n=self._max_auto_rebuy,
            rebuy_chips=rebuy_chips,
            balance_chips=0,
            rebuy_window_sec=reby_left_time,
            pnl_chips=pnl_chips,
        )
        pnl_str = format_chips_km_signed(pnl_chips)
        log.warning(
            "[BOT] ⚠️  筹码清零！自动续入 %d（100BB） 第 %d/%d 次，rebuy 窗口 %d 秒。累计盈亏 %s（筹码）",
            rebuy_chips,
            self._auto_rebuy_done,
            self._max_auto_rebuy,
            reby_left_time,
            pnl_str,
        )
        return "pb.RebyREQ", {"is_reby": True, "chips": rebuy_chips}, 0.0


# ── Wire action conversion ─────────────────────────────────────────────────────

def _decision_to_wire(decision: BotDecision) -> tuple[int, int]:
    action = decision.action.lower()
    if action == "fold":  return 1, 0
    if action == "check": return 2, 0
    if action == "call":  return 3, 0
    if action == "raise": return 4, int(decision.amount)
    return 2, 0   # safe default
