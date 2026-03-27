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

from pokerfate.api import PokerFateAPI, PlayerInfo, ActionEvent, BotDecision
from pf_intercept import config
from pf_intercept.action_types import ACTION_TYPE_TO_EVENT_ACTION, FOLD_ACTION_TYPES

log = logging.getLogger("pf_bot")

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


# ── BotBridge ─────────────────────────────────────────────────────────────────

class BotBridge:
    """
    Stateful bridge between the proxy event stream and PokerFateAPI.

    Seat ID and blind sizes are auto-detected from game messages.
    PokerFateAPI is created lazily once those values are known.

    Call handle(type_name, msg) for every decoded S2C frame.
    Returns (action_type: int, chips: int) when the bot should act, else None.
    """

    def __init__(self) -> None:
        # Detected from game messages (may be pre-seeded by config)
        self._my_seat: int | None  = None
        self._my_uid:  str | None  = None
        self._bb:      float | None = config.BIG_BLIND
        self._sb:      float | None = config.SMALL_BLIND

        self._api: PokerFateAPI | None = None   # created once blinds are known

        # Rebuy: allow at most one auto-rebuy per room entry
        self._reby_used: bool = False

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

    def handle(self, type_name: str, msg: dict) -> tuple[str, dict] | None:
        """
        Process one decoded S2C frame.
        Returns (proto_type_name, fields_dict) to inject a C2S message, else None.
        """
        try:
            return self._dispatch(type_name, msg)
        except Exception:
            log.exception("[BOT] Error handling %s", type_name)
            return None

    # ── Dispatch ──────────────────────────────────────────────────────────────

    def _dispatch(self, type_name: str, msg: dict) -> tuple[int, int] | None:
        if   type_name == "pb.SelfUserInfoRSP": self._on_self_user_info(msg)
        elif type_name == "pb.SitDownRSP":      self._on_sit_down(msg)
        elif type_name == "pb.SitDownBRC":       self._on_sit_down_brc(msg)
        elif type_name == "pb.EnterRoomRSP":     self._on_enter_room(msg)
        elif type_name == "pb.DealerInfoRSP":    self._on_dealer_info(msg)
        elif type_name == "pb.HandCardRSP":      self._on_hand_card(msg)
        elif type_name == "pb.RoundStartBRC":    self._on_round_start(msg)
        elif type_name == "pb.ActionBRC":        self._on_action_brc(msg)
        elif type_name == "pb.RoundOverBRC":     self._on_round_over(msg)
        elif type_name == "pb.ActionNotifyBRC":  return self._on_action_notify(msg)
        elif type_name == "pb.ShowHandRSP":      self._on_show_hand(msg)
        elif type_name == "pb.WinnerRSP":        self._on_winner(msg)
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

    def _on_enter_room(self, msg: dict) -> None:
        self._reby_used = False   # reset per room entry

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
            verbose=True,
        )
        log.info("[BOT] PokerFateAPI ready — seat=%d  BB=%.1f  SB=%.1f",
                 self._my_seat, bb, sb)
        return True

    # ── Hand lifecycle ────────────────────────────────────────────────────────

    def _on_dealer_info(self, msg: dict) -> None:
        if not self._ensure_api():
            return

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

    def _on_action_notify(self, msg: dict) -> tuple[int, int] | None:
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
            if call_need == 0:
                return 2, 0  # check
            return 1, 0      # fold

        street    = _STAGE_TO_STREET.get(self._stage, "preflop")

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
        return "pb.ActionREQ", {"action_type": action_type, "chips": chips}

    def _on_show_hand(self, msg: dict) -> None:
        """Capture ShowHandRSP — hole cards revealed at showdown."""
        for info in msg.get("info", []):
            seat = info.get("seatid")
            if seat is None:
                continue
            cards = []
            for key in ("card1", "card2", "card3", "card4"):
                code = info.get(key)
                if code:
                    s = _card_str(int(code))
                    if s:
                        cards.append(s)
            if cards:
                self._pending_showdown[int(seat)] = cards

    def _on_winner(self, msg: dict) -> None:
        if self._api is None:
            return

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

    def _on_notice_reby(self, msg: dict) -> tuple[str, dict] | None:
        """Server notifies us that our chips hit 0 — rebuy window opened."""
        seat = msg.get("seatid", 0)  # pb omits field when value is 0
        if seat != self._my_seat:
            log.debug("[BOT] NoticeRebyRSP for seat=%d (not us, my_seat=%s), ignored", seat, self._my_seat)
            return None

        reby_left_time = msg.get("reby_left_time", 0)
        rebuy_chips = int(100 * (self._bb or 1000))

        if self._reby_used:
            log.warning(
                "[BOT] ⚠️  筹码清零！（本局已自动续入过一次，不再续入）rebuy 窗口 %d 秒。",
                reby_left_time,
            )
            return None

        self._reby_used = True
        log.warning(
            "[BOT] ⚠️  筹码清零！自动续入 %d（100BB），rebuy 窗口 %d 秒。",
            rebuy_chips,
            reby_left_time,
        )
        return "pb.RebyREQ", {"is_reby": True, "chips": rebuy_chips}


# ── Wire action conversion ─────────────────────────────────────────────────────

def _decision_to_wire(decision: BotDecision) -> tuple[int, int]:
    action = decision.action.lower()
    if action == "fold":  return 1, 0
    if action == "check": return 2, 0
    if action == "call":  return 3, 0
    if action == "raise": return 4, int(decision.amount)
    return 2, 0   # safe default
