"""
Bot bridge: translates proxy events → PokerFateAPI calls → wire actions.

Auto-detection:
  MY_SEAT_ID  ← pb.SitDownRSP.seatid
  BIG_BLIND   ← pb.EnterRoomRSP.room_info.bb
  SMALL_BLIND ← pb.EnterRoomRSP.room_info.sb
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
import logging
import random

from pokerfate.api import PokerFateAPI, PlayerInfo, ActionEvent, BotDecision
from pf_intercept import config
from pf_intercept.action_types import ACTION_TYPE_TO_EVENT_ACTION, FOLD_ACTION_TYPES

log = logging.getLogger("pf_bot")

_MAX_INJECT_DELAY = getattr(config, "ACTION_INJECT_DELAY_MAX_SEC", 3.0)


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


def _chip_int(value, default: int = 0) -> int:
    """
    Parse protobuf int64-like values that may arrive as int/str.
    """
    try:
        if value is None:
            return default
        return int(value)
    except Exception:
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
    Returns (proto_name, fields) or (proto_name, fields, delay_sec) to inject C2S, else None.
    """

    def __init__(self, max_auto_rebuy: int = 1) -> None:
        # Detected from game messages (may be pre-seeded by config)
        self._my_seat: int | None  = None
        self._my_uid:  str | None  = None
        self._bb:      float | None = config.BIG_BLIND
        self._sb:      float | None = config.SMALL_BLIND

        self._api: PokerFateAPI | None = None   # created once blinds are known

        # Auto-rebuy when chips hit 0 (NoticeRebyRSP); capped per room entry
        self._max_auto_rebuy: int = max(1, min(20, int(max_auto_rebuy)))
        self._auto_rebuy_done: int = 0

        # 盈利锁仓：WinnerRSP 达标后先记入 _profit_lock_deferred；下一手 DealerInfoRSP 再发
        # LeaveRoom（避免与结算界面并发）；LeaveRoomRSP 成功后发 EnterRoom（100BB）
        self._profit_lock_deferred: dict[str, int | str | bool | None] | None = None
        self._profit_lock_reenter: dict[str, int | str | None] | None = None
        self._profit_lock_award_rebuy_after_enter: bool = False
        # 最近一次注入的 EnterRoomREQ 字段（失败时打日志 / 人工对照）
        self._profit_lock_last_enter_fields: dict | None = None
        # 从最近一次成功进房 RSP 缓存，供 QuickStart 兜底（与客户端大厅一致）
        self._session_game_type: int = 0
        self._session_lobby_coin: int = 0

        # C2S 帧里的 room_id 须与客户端 Net.packNetData 一致（GameModel:getRoomId）。
        # 部分 S2C（如 WinnerRSP）wire 上 room_id 可能为 0，要用进房时或任意非 0 帧补全。
        self._table_room_id: int = 0

        # Session-level: real player names keyed by seat_id
        # Populated from EnterRoomRSP.table_status.seat[].player.name
        # and updated on SitDownBRC
        self._seat_names: dict[int, str] = {}
        # uid (str) → seat_id; built from EnterRoomRSP/SitDownBRC; used to
        # resolve WinnerRSP entries that carry uid but no seatid.
        self._uid_to_seat: dict[str, int] = {}

        # Per-hand state
        self._stage:    int       = 0
        self._pot:      int       = 0
        self._my_bet:   int       = 0   # my chips in this street
        self._max_bet:  int       = 0   # highest bet this street
        self._my_chips: int       = 0
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
            self._profit_lock_reenter is not None or self._profit_lock_deferred is not None
        ):
            log.warning("[BOT] 盈利锁仓：LeaveRoom 未发出，已取消离桌重进。")
            self._profit_lock_cancel_reenter()
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

    def handle(self, type_name: str, msg: dict) -> tuple[str, dict] | tuple[str, dict, float] | None:
        """
        Process one decoded S2C frame.
        Returns (proto_type_name, fields_dict) or (proto_type_name, fields_dict, delay_sec)
        to inject a C2S message after optional delay (seconds), else None.
        """
        try:
            return self._dispatch(type_name, msg)
        except Exception:
            log.exception("[BOT] Error handling %s", type_name)
            return None

    # ── Dispatch ──────────────────────────────────────────────────────────────

    def _dispatch(self, type_name: str, msg: dict) -> tuple[str, dict] | tuple[str, dict, float] | None:
        if   type_name == "pb.SelfUserInfoRSP": self._on_self_user_info(msg)
        elif type_name == "pb.SitDownRSP":      self._on_sit_down(msg)
        elif type_name == "pb.SitDownBRC":       self._on_sit_down_brc(msg)
        elif type_name == "pb.EnterRoomRSP":     return self._on_enter_room(msg)
        elif type_name == "pb.DealerInfoRSP":    return self._on_dealer_info(msg)
        elif type_name == "pb.HandCardRSP":      self._on_hand_card(msg)
        elif type_name == "pb.RoundStartBRC":    self._on_round_start(msg)
        elif type_name == "pb.ActionBRC":        self._on_action_brc(msg)
        elif type_name == "pb.RoundOverBRC":     self._on_round_over(msg)
        elif type_name == "pb.ActionNotifyBRC":  return self._on_action_notify(msg)
        elif type_name == "pb.ShowHandRSP":      self._on_show_hand(msg)
        elif type_name == "pb.ShowMyCardBRC":    self._on_show_my_card_brc(msg)
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

    def _on_enter_room(self, msg: dict) -> tuple[str, dict, float] | None:
        self._auto_rebuy_done = 0   # reset per room entry
        self._profit_lock_reenter = None
        self._profit_lock_deferred = None

        if "game_type" in msg:
            self._session_game_type = _chip_int(msg.get("game_type"), 0)
        room_info_early = msg.get("room_info") or {}
        if "lobby_coin" in room_info_early:
            self._session_lobby_coin = _chip_int(room_info_early.get("lobby_coin"), 0)

        code = _s2c_rsp_code(msg, 0)
        fallback_inject: tuple[str, dict, float] | None = None
        if self._profit_lock_award_rebuy_after_enter:
            if code == 0:
                self._max_auto_rebuy += 1
                self._profit_lock_last_enter_fields = None
                log.warning(
                    "[BOT] 盈利锁仓：已重新进房，自动续入次数上限 +1 → %d",
                    self._max_auto_rebuy,
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

        # Blind detection
        room_info = msg.get("room_info") or {}
        bb = room_info.get("bb")
        sb = room_info.get("sb")
        if bb:
            self._bb = float(bb)
            log.info("[BOT] Big blind detected: %.1f", self._bb)
        if sb:
            self._sb = float(sb)
            log.info("[BOT] Small blind detected: %.1f", self._sb)

        # Seed player names from current table snapshot
        table_status = msg.get("table_status") or {}
        for seat_status in table_status.get("seat", []):
            self._extract_seat_name(seat_status)

        # Re-detect my seat on reconnect by matching uid from SelfUserInfoRSP.
        if self._my_uid:
            for seat_status in table_status.get("seat", []):
                player = seat_status.get("player") or {}
                uid = player.get("uid")
                if uid is not None and str(uid) == self._my_uid:
                    seat = _chip_int(seat_status.get("seatid", 0), 0)
                    self._set_my_seat(seat, "EnterRoomRSP.uid")
                    break

        # 重进 / 回桌后必须用服务端筹码覆盖快照（见 _sync_stacks_from_table_snapshot 注释）
        self._sync_stacks_from_table_snapshot(table_status)

        return fallback_inject

    def _profit_lock_quick_start_fallback(self) -> tuple[str, dict, float] | None:
        """EnterRoom 失败时按大厅 QuickStart 随机配桌（LobbyByinDialog 同款字段）。"""
        bb = float(self._bb or 0.0)
        if bb <= 0:
            log.warning("[BOT] 盈利锁仓：无法 QuickStart 兜底（BB 未知）。")
            return None
        gt = self._session_game_type or int(getattr(config, "PROFIT_LOCK_FALLBACK_GAME_TYPE", 10010101))
        lc = self._session_lobby_coin or int(getattr(config, "PROFIT_LOCK_FALLBACK_LOBBY_COIN", 10100001))
        byin = int(100 * bb)
        delay = float(getattr(config, "PROFIT_LOCK_QUICKSTART_DELAY_SEC", 0.5))
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
            "[BOT] 盈利锁仓：%.1fs 后发送 QuickStartREQ 兜底（随机桌，同盲注/100BB）: %s",
            delay,
            fields,
        )
        return "pb.QuickStartREQ", fields, delay

    def _on_sit_down_brc(self, msg: dict) -> None:
        """A player sat down — update name map from SitDownBRC.status."""
        seat_status = msg.get("status") or {}
        self._extract_seat_name(seat_status)

    def _extract_seat_name(self, seat_status: dict) -> None:
        """Pull seat_id + player name/uid out of a SeatStatus dict."""
        seat = _chip_int(seat_status.get("seatid", 0), 0)
        player = seat_status.get("player") or {}
        name = player.get("name", "")
        uid  = player.get("uid")
        if seat >= 0 and name:
            self._seat_names[seat] = name
        if seat >= 0 and uid is not None:
            self._uid_to_seat[str(uid)] = seat

    def _sync_stacks_from_table_snapshot(self, table_status: dict) -> None:
        """用 EnterRoomRSP.table_status 里的 hand_chips 对齐本地快照。

        盈利锁仓在 DealerInfo 里会写入 _hand_start_chips 后发 LeaveRoom；若重进后不刷新，
        WinnerRSP 仍用离桌前的大筹码作基准 + profit，会误再次触发锁仓。
        """
        for seat_status in table_status.get("seat", []) or []:
            seat = _chip_int(seat_status.get("seatid", 0), 0)
            if "seatid" not in seat_status:
                log.debug(
                    "[BOT] table_status seat missing seatid; assume 0: %s",
                    seat_status,
                )
            raw = seat_status.get("hand_chips")
            if raw is None:
                raw = seat_status.get("begin_chips")
            if raw is None:
                continue
            chips = _chip_int(raw, 0)
            self._seat_chips[seat] = chips
            self._hand_start_chips[seat] = chips
            if self._my_seat is not None and seat == self._my_seat:
                self._my_chips = chips

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
            my_player_id=self._my_seat,
            big_blind=bb,
            small_blind=sb,
            equity_iterations=3000,
            verbose=True,
        )
        log.info("[BOT] PokerFateAPI ready — seat=%d  BB=%.1f  SB=%.1f",
                 self._my_seat, bb, sb)
        return True

    # ── Hand lifecycle ────────────────────────────────────────────────────────

    def _on_dealer_info(self, msg: dict) -> tuple[str, dict, float] | None:
        if not self._ensure_api():
            return None

        self._stage   = 1
        self._pot     = 0
        self._my_bet  = 0
        self._max_bet = 0
        self._my_forced_post_this_street = False
        self._folded  = set()
        self._announced_stages = set()
        self._hole_cards_count = 0

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
            name = self._seat_names.get(seat) or f"Player_{seat}"
            players.append(PlayerInfo(
                player_id=seat,
                name=name,
                stack=chips,
            ))

        self._api.new_hand(players=players, dealer_id=msg.get("dealer", 0))

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
            }
            self._profit_lock_award_rebuy_after_enter = True
            log.warning(
                "[BOT] 盈利锁仓：已收到下一手 DealerInfo，现离桌（留座=%s）再以 %d（100BB）重进房间 %d。",
                seat_reserve,
                byin,
                room_id,
            )
            return "pb.LeaveRoomREQ", {"seat_reserve": seat_reserve}, 0.0

        return None

    def _on_hand_card(self, msg: dict) -> None:
        if self._api is None:
            return
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

    def _on_round_start(self, msg: dict) -> None:
        stage = msg.get("stage", 1)
        self._stage   = stage
        self._my_bet  = 0
        self._max_bet = 0
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

        self._pot     += chips
        if chips > self._max_bet:
            self._max_bet = chips

        # Track remaining chips for every seat (used in final_stacks)
        if hand_chips is not None:
            self._seat_chips[seat] = _chip_int(hand_chips)

        if seat == self._my_seat:
            self._my_bet += chips
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
        self._api.notify_action(ActionEvent(
            player_id=seat,
            action=action_str,
            amount=chips,
            street=street,
        ))

    def _on_round_over(self, msg: dict) -> None:
        pool = msg.get("pool", [])
        if pool:
            self._pot = sum(_chip_int(p, 0) for p in pool)

    def _on_action_notify(self, msg: dict) -> tuple[str, dict, float] | None:
        if self._api is None or self._my_seat is None:
            return None
        seat = _chip_int(msg.get("seatid", 0), 0)
        if seat != self._my_seat:
            log.debug("[BOT] Ignore ActionNotify seat=%d my_seat=%d", seat, self._my_seat)
            return None

        call_need = _chip_int(msg.get("call_need_chips", 0))

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
        delay_sec = _inject_delay_before_action(
            street, decision, self._pot, self._bb or 0.0,
        )
        log.debug("[BOT] ActionREQ inject delay: %.2fs", delay_sec)
        return "pb.ActionREQ", {"action_type": action_type, "chips": chips}, delay_sec

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

    def _on_show_my_card_brc(self, msg: dict) -> None:
        """Capture ShowMyCardBRC — cards revealed by players (active or folded showing voluntarily).

        hand_cards is a repeated int32 list; 0 means that card slot is not shown.
        Card encoding is identical to other messages: code = suit * 256 + rank_num.
        """
        for info in msg.get("info", []):
            seat = info.get("seatid", 0)  # pb omits field when value is 0
            cards = []
            for code in info.get("hand_cards", []):
                if code:
                    s = _card_str(int(code))
                    if s:
                        cards.append(s)
            if len(cards) >= 2:
                seat_int = int(seat)
                existing = self._pending_showdown.get(seat_int, [])
                if len(cards) > len(existing):
                    self._pending_showdown[seat_int] = cards

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

            winner_ids.append(seat)

            # Capture server-provided hand type (authoritative)
            hand_type = w.get("type")
            if hand_type:
                self._pending_winner_types[seat] = int(hand_type)

        # Build final_stacks from hand-start chips + server profit delta.
        # WinnerRSP.profit gives each player's net gain/loss for the hand,
        # already accounting for uncalled bet returns and rake.
        # This is more accurate than seat_chips + winner.chips.
        final_stacks: dict[int, int] = dict(self._hand_start_chips)
        for p in msg.get("profit", []):
            uid = str(p.get("uid", ""))
            seat = self._uid_to_seat.get(uid, -1)
            if seat < 0:
                continue
            profit_chips = _chip_int(p.get("chips", 0), 0)
            if seat in final_stacks:
                final_stacks[seat] = final_stacks[seat] + profit_chips
        # Fall back to seat_chips for any seat missing from profit.
        for seat, chips in self._seat_chips.items():
            if seat not in final_stacks:
                final_stacks[seat] = chips

        self._api.hand_over(
            winner_ids=winner_ids,
            pot=total_pot,
            final_stacks=final_stacks,
            showdown_hands=self._pending_showdown or None,
            winner_hand_types=self._pending_winner_types or None,
        )
        self._pending_showdown = {}
        self._pending_winner_types = {}

        return self._maybe_profit_lock_leave_reenter(final_stacks)

    def _maybe_profit_lock_leave_reenter(
        self, final_stacks: dict[int, int]
    ) -> tuple[str, dict, float] | None:
        """筹码 >= 阈值则记在 deferred，下一手 DealerInfo 再离桌并以 100BB 进同一房间。"""
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
        seat_reserve = bool(getattr(config, "PROFIT_LOCK_LEAVE_SEAT_RESERVE", True))
        self._profit_lock_deferred = {
            "roomid": room_id,
            "byin_chips": buyin,
            "uid": self._my_uid,
            "seat_reserve": seat_reserve,
        }
        log.warning(
            "[BOT] 盈利锁仓：本手结束后筹码 %d >= %d（%dBB），将在下一手 DealerInfo 开始后离桌（留座=%s）再以 %d（100BB）重进房间 %d。",
            my_final,
            threshold,
            lock_bb,
            seat_reserve,
            buyin,
            room_id,
        )
        return None

    def _on_leave_room_rsp(self, msg: dict) -> tuple[str, dict, float] | None:
        """盈利锁仓：离桌成功后带买入重新进房。"""
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
        uid = pending.get("uid")
        self._profit_lock_reenter = None

        fields: dict = {"roomid": room_id, "byin_chips": byin}
        if uid:
            fields["uid"] = int(uid)
        self._profit_lock_last_enter_fields = dict(fields)
        delay = float(getattr(config, "PROFIT_LOCK_REENTER_DELAY_SEC", 2.0))
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

    def _on_notice_reby(self, msg: dict) -> tuple[str, dict, float] | None:
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

        self._auto_rebuy_done += 1
        log.warning(
            "[BOT] ⚠️  筹码清零！自动续入 %d（100BB） 第 %d/%d 次，rebuy 窗口 %d 秒。",
            rebuy_chips,
            self._auto_rebuy_done,
            self._max_auto_rebuy,
            reby_left_time,
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
