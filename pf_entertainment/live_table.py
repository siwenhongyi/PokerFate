"""Read-only live-table observer for headless (pure-API) play.

It consumes decoded S2C messages (the same frames the bot bridge sees) and
maintains a render-ready snapshot of the current table — seats, stacks, bets,
board, pot, whose turn it is, the hero's hole cards and a short feed of key
actions — so the web UI can draw a live poker table without the game client.

It never injects, never decides and never raises into the session: every
handler is defensive, because this must not be able to break play.  Wire it in
through ``HeadlessSession(on_frame=observer.observe)``.
"""

from __future__ import annotations

import threading
import time
import copy
import uuid
from collections import deque
from typing import Any, Callable

# ── game wire decoding (mirrors pf_intercept.bot.bridge, kept dependency-light) ──

_RANK_TO_STR = {
    2: "2", 3: "3", 4: "4", 5: "5", 6: "6", 7: "7", 8: "8", 9: "9",
    10: "T", 11: "J", 12: "Q", 13: "K", 14: "A",
}
_SUIT_TO_STR = {1: "d", 2: "c", 3: "h", 4: "s", 0: "d"}
_STAGE_TO_STREET = {1: "preflop", 2: "flop", 3: "turn", 4: "river"}

# action_type (EnumConfig.POKER_ACTION) → short Chinese label for the feed.
_ACTION_LABEL = {
    1: "弃牌", 2: "过牌", 3: "跟注", 4: "加注", 7: "下注",
    8: "小盲", 9: "大盲", 10: "前注", 11: "大盲", 12: "弃牌",
    13: "过牌", 14: "跨注", 16: "弃牌", 17: "全下",
}
_FOLD_ACTIONS = {1, 12, 16}
_BLIND_ACTIONS = {8, 9, 10, 11, 14}


def _card_str(code: Any) -> str | None:
    try:
        code = int(code)
    except (TypeError, ValueError):
        return None
    if code <= 0:
        return None
    rank = _RANK_TO_STR.get(code % 256)
    suit = _SUIT_TO_STR.get(code // 256)
    if rank is None or suit is None:
        return None
    return rank + suit


def _chip(v: Any, default: int = 0) -> int:
    try:
        return int(v)
    except (TypeError, ValueError):
        try:
            return int(float(v))
        except (TypeError, ValueError):
            return default


def seat_positions(seats, dealer: int, small_blind: int | None = None,
                   big_blind: int | None = None) -> dict[int, str]:
    """Seat -> position label for the players dealt into a hand.

    Same convention the strategy uses: BTN / SB / BB, then counting back from the button
    CO, MP and UTG for every earlier seat.  Heads-up the button also posts the small blind
    ("BTN/SB").  With a dead button (dealer seat not dealt in) nobody is labelled BTN.
    """
    ordered = sorted({int(x) for x in seats})
    n = len(ordered)
    if n == 0:
        return {}
    if n == 1:
        return {ordered[0]: "BTN"}
    d_idx = ordered.index(int(dealer)) if int(dealer) in ordered else None
    out: dict[int, str] = {}
    if n == 2:
        if d_idx is None:
            d_idx = ordered.index(int(small_blind)) if small_blind in ordered else 0
        out[ordered[d_idx]] = "BTN/SB"
        out[ordered[1 - d_idx]] = "BB"
        return out
    sb = int(small_blind) if small_blind is not None and int(small_blind) in ordered else (
        ordered[(d_idx + 1) % n] if d_idx is not None else None)
    bb = int(big_blind) if big_blind is not None and int(big_blind) in ordered else (
        ordered[(d_idx + 2) % n] if d_idx is not None else None)
    if d_idx is not None:
        out[ordered[d_idx]] = "BTN"
    if sb is not None:
        out[sb] = "BTN/SB" if out.get(sb) == "BTN" else "SB"
    if bb is not None and bb not in out:
        out[bb] = "BB"
    anchor = d_idx if d_idx is not None else (ordered.index(sb) if sb in ordered else 0)
    back = ["CO", "MP"]
    for step in range(1, n):
        seat = ordered[(anchor - step) % n]
        if seat in out:
            continue
        out[seat] = back.pop(0) if back else "UTG"
    return out


class LiveTableObserver:
    """Maintains a thread-safe render snapshot of the live table."""

    def __init__(self, *, my_uid: int | str | None = None, log_size: int = 14,
                 reward_source: Callable[[], tuple[int, bool]] | None = None,
                 chips_source: Callable[[], int | None] | None = None) -> None:
        self.my_uid = str(my_uid) if my_uid is not None else None
        self._reward_source = reward_source
        # The account's chips, wallet plus table; None until the server has told the wallet.
        self._chips_source = chips_source
        self._session_pnl_chips = 0
        # The same result in big blinds, each hand at the blind it was played at (table selection
        # can change stakes).  None once a hand settled with no blind known: the page then reads
        # the chip total at the current table's blind instead.
        self._session_pnl_bb: float | None = 0.0
        self._settled_games: set[str] = set()
        self._lock = threading.Lock()
        self._feed: deque[str] = deque(maxlen=log_size)
        # The blind each feed line was played at: the page shows its amounts in big blinds, and
        # table selection can change stakes between two lines.  Same for the last result.
        self._feed_bb: deque[int] = deque(maxlen=log_size)
        self._result_bb = 0
        self._seats: dict[int, dict] = {}
        # The last result is independent of the live table. A profit-lock
        # leave/re-entry must not erase it before the viewer can read it.
        self._settlement: dict | None = None
        self._reset_table()
        self._connected = False
        self._connection_status = "disconnected"
        self._room_id = 0
        self._sb = 0
        self._bb = 0
        self._seat_num = 6
        self._hand_no = 0
        self._result = ""
        self._updated = time.time()

    # ── lifecycle ────────────────────────────────────────────────────────────
    def set_connected(self, flag: bool) -> None:
        with self._lock:
            self._connected = bool(flag)
            self._connection_status = "connected" if flag else "disconnected"
            self._updated = time.time()

    def set_connection_status(self, status: str) -> None:
        with self._lock:
            self._connection_status = status
            self._connected = status == "connected"
            if not self._connected:
                self._action_seat = None
            self._updated = time.time()

    def set_my_uid(self, uid: int | str | None) -> None:
        with self._lock:
            self.my_uid = str(uid) if uid is not None else None

    def _reset_table(self) -> None:
        self._game_id = ""
        self._hand_token = uuid.uuid4().hex
        self._public_holes: dict[int, list] = {}
        self._board: list[str] = []
        self._pot = 0
        self._street = ""
        self._my_seat: int | None = None
        self._my_hole: list[str] = []
        self._action_seat: int | None = None
        # Key by player identity so a replacement in the same seat cannot
        # inherit the previous occupant's settlement baseline.
        self._hand_start_stacks: dict[str, int] = {}

    def _reset_hand(self) -> None:
        self._public_holes.clear()
        self._hand_token = uuid.uuid4().hex
        self._board = []
        self._pot = 0
        self._street = "preflop"
        self._my_hole = []
        self._action_seat = None
        self._hand_start_stacks.clear()
        for s in self._seats.values():
            s["bet"] = 0
            s["folded"] = False
            s["allin"] = False
            s["last"] = ""
            s["cards"] = []
            s["revealed"] = False
            s["pos"] = ""

    def _seat(self, seatid: int) -> dict:
        s = self._seats.get(seatid)
        if s is None:
            s = {
                "seatid": seatid, "name": "", "uid": "", "stack": 0, "bet": 0,
                "folded": False, "allin": False, "cards": [], "last": "", "empty": True, "pos": "",
            }
            self._seats[seatid] = s
        return s

    def _set_positions(self, seats, dealer, small_blind, big_blind) -> None:
        for s in self._seats.values():
            s["pos"] = ""
        for seatid, label in seat_positions(seats, dealer, small_blind, big_blind).items():
            self._seat(seatid)["pos"] = label

    def _player_kind(self, uid: str) -> str:
        """robot / human, each proven by the server's counter, or "" (nothing proven yet)."""
        if not uid or uid == self.my_uid:
            return ""
        try:
            from pokerfate.core.robots import UNKNOWN, default_registry
            status = default_registry().status(uid)
            return "" if status == UNKNOWN else status
        except Exception:
            return ""

    # ── message intake ───────────────────────────────────────────────────────
    def observe(self, type_name: str, msg: dict) -> None:
        if not isinstance(msg, dict):
            return
        try:
            with self._lock:
                handler = _HANDLERS.get(type_name)
                if handler is not None:
                    handler(self, msg)
                    self._updated = time.time()
        except Exception:
            # Observability must never break the session.
            pass

    # individual handlers (called under lock) ---------------------------------
    def _h_enter_room(self, msg: dict) -> None:
        if _chip(msg.get("code"), 0) != 0:
            return
        self._reset_table()
        self._seats.clear()
        self._result = ""
        self._room_id = _chip(msg.get("roomid"), self._room_id)
        room_info = msg.get("room_info") or {}
        self._sb = _chip(room_info.get("sb"), self._sb)
        self._bb = _chip(room_info.get("bb"), self._bb)
        self._seat_num = _chip(room_info.get("seat_num"), self._seat_num) or 6
        ts = msg.get("table_status") or {}
        self._game_id = str(ts.get("gameid") or "")
        self._hand_start_stacks.clear()
        for entry in ts.get("seat") or []:
            if not isinstance(entry, dict):
                continue
            seatid = _chip(entry.get("seatid"), 0)
            player = entry.get("player") or {}
            s = self._seat(seatid)
            uid = player.get("uid")
            if uid:
                s["uid"] = str(uid)
                s["name"] = player.get("name") or s["name"] or f"玩家{seatid}"
                s["empty"] = False
                if "begin_chips" in entry:
                    self._hand_start_stacks[str(uid)] = _chip(entry["begin_chips"])
                if self.my_uid and str(uid) == self.my_uid:
                    self._my_seat = seatid
            else:
                s["empty"] = not bool(entry.get("has_card"))
            s["stack"] = _chip(entry.get("hand_chips"), 0)
            at = _chip(entry.get("last_action_type"), 0)
            s["folded"] = at in _FOLD_ACTIONS
            s["allin"] = bool(entry.get("is_allin"))
            cards = [_card_str(entry.get(k)) for k in ("card1", "card2")]
            if any(cards):
                s["cards"] = cards
                s["revealed"] = True
                self._public_holes[seatid] = cards
        if ts.get("is_playing"):
            dealt = [_chip(e.get("seatid"), 0) for e in ts.get("seat") or []
                     if isinstance(e, dict) and e.get("has_card")]
            if len(dealt) >= 2:
                self._set_positions(dealt, _chip(ts.get("d_idx"), 0),
                                    _chip(ts.get("sb_idx"), 0), _chip(ts.get("bb_idx"), 0))
        board = [c for c in (_card_str(x) for x in ts.get("board") or []) if c]
        if board:
            self._board = board
        self._pot = sum(_chip(p, 0) for p in ts.get("pool") or []) or self._pot
        stage = _chip(ts.get("stage"), 0)
        if stage:
            self._street = _STAGE_TO_STREET.get(stage, self._street)
        playing = msg.get("playing_status") or {}
        hole = [_card_str(playing.get(k)) for k in ("card1", "card2")]
        if any(hole):
            self._my_hole = hole
            if self._my_seat is not None:
                self._seat(self._my_seat)["cards"] = list(hole)
        if "action_seatid" in playing:
            self._action_seat = _chip(playing.get("action_seatid"), 0)

    def _h_leave_room_rsp(self, msg: dict) -> None:
        if _chip(msg.get("code"), 0) not in (0, 2, 3):
            return
        rid = _chip(msg.get("roomid"), 0)
        if rid and self._room_id and rid != self._room_id:
            return
        self._reset_table()
        self._seats.clear()
        self._room_id = 0
        self._sb = self._bb = 0
        self._result = "已离桌，当前在大厅"
        self._say("已离桌，当前在大厅")

    def _h_location(self, msg: dict) -> None:
        if _chip(msg.get("roomid"), 0) == 0:
            self._h_leave_room_rsp({})

    def _h_sit_down_rsp(self, msg: dict) -> None:
        seatid = _chip(msg.get("seatid"), 0)
        if seatid < 0:
            return
        self._my_seat = seatid
        s = self._seat(seatid)
        s["stack"] = _chip(msg.get("chips"), s["stack"])
        s["empty"] = False
        if self.my_uid:
            s["uid"] = self.my_uid

    def _h_sit_down_brc(self, msg: dict) -> None:
        status = msg.get("status") or {}
        seatid = _chip(status.get("seatid"), 0)
        if seatid < 0:
            return
        player = status.get("player") or {}
        s = self._seat(seatid)
        if player.get("uid"):
            s["uid"] = str(player.get("uid"))
            s["name"] = player.get("name") or s["name"] or f"玩家{seatid}"
        s["stack"] = _chip(status.get("hand_chips"), s["stack"])
        s["empty"] = False

    def _h_other_leave(self, msg: dict) -> None:
        # OtherLeaveRoomBRC identifies the departing player by uid only;
        # unlike action broadcasts, it has no seatid field (not even seat 0).
        uid = msg.get("uid")
        if uid is None:
            return
        seatid = next((i for i, s in self._seats.items()
                       if s["uid"] and s["uid"] == str(uid)), -1)
        self._h_leave({"seatid": seatid})

    def _h_leave(self, msg: dict) -> None:
        seatid = _chip(msg.get("seatid"), -1)
        if seatid >= 0 and seatid in self._seats:
            self._seats[seatid] = {
                "seatid": seatid, "name": "", "uid": "", "stack": 0, "bet": 0,
                "folded": False, "allin": False, "cards": [], "last": "", "empty": True, "pos": "",
            }

    def _h_hand_card(self, msg: dict) -> None:
        cards = [c for c in (_card_str(msg.get(k)) for k in ("card1", "card2", "card3", "card4")) if c]
        seatid = _chip(msg.get("seatid"), 0)
        if cards:
            self._my_hole = cards[:4]
            self._my_seat = seatid
            if seatid >= 0:
                self._seat(seatid)["cards"] = cards[:4]

    def _h_dealer_info(self, msg: dict) -> None:
        self._reset_hand()
        self._game_id = str(msg.get("gameid") or "")
        self._hand_no += 1
        self._result = ""
        dealt: list[int] = []
        for entry in msg.get("start_info") or []:
            if not isinstance(entry, dict):
                continue
            seatid = _chip(entry.get("seatid"), 0)
            if seatid < 0:
                continue
            s = self._seat(seatid)
            s["stack"] = _chip(entry.get("chips"), 0)
            if s["uid"]:
                self._hand_start_stacks[s["uid"]] = s["stack"]
            dealt.append(seatid)
        # Protobuf drops zero-valued fields: a missing dealer / blind is seat 0, unless the
        # message names no blind at all (then they follow from the button).
        has_blinds = "small_blind" in msg or "big_blind" in msg
        self._set_positions(
            dealt, _chip(msg.get("dealer"), 0),
            _chip(msg.get("small_blind"), 0) if has_blinds else None,
            _chip(msg.get("big_blind"), 0) if has_blinds else None,
        )

    def _h_round_start(self, msg: dict) -> None:
        stage = _chip(msg.get("stage"), 0)
        if stage:
            self._street = _STAGE_TO_STREET.get(stage, self._street)
        # all_board is the full board so far - just take it.
        full = [c for c in (_card_str(x) for x in msg.get("all_board") or []) if c]
        if full:
            self._board = full
        # New street: street bets are swept into the pot, and nobody has acted on it yet.
        # A fold or an all-in still shows on the seat itself (dimmed / ALLIN tag).
        for s in self._seats.values():
            s["bet"] = 0
            s["last"] = ""

    def _h_action(self, msg: dict) -> None:
        # Protobuf omits default-valued fields, so seat 0's broadcasts arrive
        # with no ``seatid`` at all. Treating that as "unknown" froze the
        # hero's stack at the buy-in on the web whenever hero sat in seat 0
        # (2026-11-08). A missing seatid is seat 0.
        seatid = _chip(msg.get("seatid"), 0)
        at = _chip(msg.get("action_type"), 0)
        chips = _chip(msg.get("chips"), 0)
        s = self._seat(seatid) if seatid >= 0 else None
        label = _ACTION_LABEL.get(at, "")
        if s is not None:
            # This field is the remaining stack, including zero when an
            # all-in (or a call/blind exhausting the stack) omits the default.
            s["stack"] = _chip(msg.get("hand_chips"), 0)
            if chips > 0:
                s["bet"] += chips
            if at in _FOLD_ACTIONS:
                s["folded"] = True
            if at == 17:
                s["allin"] = True
            s["last"] = (f"{label} {chips}" if chips > 0 and at not in _FOLD_ACTIONS else label) or s["last"]
        if chips > 0:
            self._pot += chips
        who = (s["name"] if s and s["name"] else (f"座位{seatid}" if seatid >= 0 else "?"))
        if s and self._player_kind(s["uid"]) == "robot":
            who += "〔人机〕"
        if label and at not in _BLIND_ACTIONS:
            amt = f" {chips}" if chips > 0 and at not in _FOLD_ACTIONS else ""
            self._say(f"{who} {label}{amt}")

    def _say(self, line: str) -> None:
        self._feed.append(line)
        self._feed_bb.append(int(self._bb or 0))

    def _h_action_notify(self, msg: dict) -> None:
        self._action_seat = _chip(msg.get("seatid"), 0)

    def _h_round_over(self, msg: dict) -> None:
        # Server totals account for uncalled bet returns and side pots.
        # An empty notification without a pool is not a new total.
        if "pool" in msg:
            self._pot = sum(_chip(p) for p in msg.get("pool") or [])
        for s in self._seats.values():
            s["bet"] = 0

    def _h_show_hand(self, msg: dict) -> None:
        for entry in msg.get("info") or []:
            if isinstance(entry, dict):
                self._reveal(_chip(entry.get("seatid"), 0),
                             [_card_str(entry.get(k)) for k in ("card1", "card2")])

    def _h_show_my_card(self, msg: dict) -> None:
        game_id = str(msg.get("gameid") or "")
        old = bool(game_id and game_id != self._game_id)
        if old and (not self._settlement or game_id != self._settlement["game_id"]):
            return
        for entry in msg.get("info") or []:
            if not isinstance(entry, dict):
                continue
            cards = [_card_str(card) for card in (entry.get("hand_cards") or [])[:2]]
            cards += [None] * (2 - len(cards))
            self._reveal(_chip(entry.get("seatid"), 0), cards, old_hand=old)

    def _reveal(self, seatid: int, cards: list, *, old_hand: bool = False) -> None:
        if seatid < 0 or seatid >= 12 or not any(cards):
            return
        if not old_hand:
            previous = self._public_holes.get(seatid, [None, None])
            cards = [card or previous[i] for i, card in enumerate(cards)]
            self._public_holes[seatid] = list(cards)
            seat = self._seat(seatid)
            seat["cards"] = list(self._my_hole) if seatid == self._my_seat and self._my_hole else list(cards)
            seat["revealed"] = True
        settlement = self._settlement
        if not settlement or (not old_hand and settlement["id"] != self._hand_token):
            return
        # Some voluntary reveals arrive after WinnerRSP, even after the next
        # DealerInfoRSP. Update the saved result, never the new hand's seats.
        shown = next((p for p in settlement["revealed"] if p["seatid"] == seatid), None)
        if shown is None:
            player = next((p for p in settlement["players"] if p["seatid"] == seatid), None)
            if player is None:
                return
            shown = {"seatid": seatid, "name": player["name"], "hole": [None, None]}
            settlement["revealed"].append(shown)
        shown["hole"] = [card or shown["hole"][i] for i, card in enumerate(cards)]
        from pf_entertainment.showdown import hand_group
        for winner in settlement["winners"]:
            if winner["seatid"] == seatid:
                hero = settlement["hero"]
                winner["hole"] = list(hero["hole"] if hero["seatid"] == seatid and hero["hole"] else shown["hole"])
                winner["group"] = hand_group(winner["hole"], settlement["board"], server_type=winner["server_type"])

    def _result_seat(self, player: dict) -> int:
        uid = str(player.get("uid") or "")
        if uid:
            match = next((i for i, s in self._seats.items() if s["uid"] == uid), None)
            if match is not None:
                return match
            if "seatid" not in player:
                return -1
        return _chip(player.get("seatid"), 0)

    def _save_settlement(self, winners: list) -> None:
        from pf_entertainment.showdown import hand_group
        merged: dict[str, dict] = {}
        for item in winners:
            if not isinstance(item, dict):
                continue
            seatid = self._result_seat(item)
            seat = self._seats.get(seatid, {})
            key = str(item.get("uid") or f"seat:{seatid}")
            if key not in merged:
                hole = list(self._my_hole if seatid == self._my_seat else self._public_holes.get(seatid, []))
                server_type = _chip(item.get("type"), 0)
                merged[key] = {"seatid": seatid, "name": seat.get("name") or "未识别玩家",
                               "hole": hole, "chips": 0, "pools": [], "server_type": server_type,
                               "group": hand_group(hole, self._board, server_type=server_type)}
            winner = merged[key]
            winner["chips"] += _chip(item.get("chips"), 0)
            pool = _chip(item.get("poolid"), 0)
            if pool not in winner["pools"]:
                winner["pools"].append(pool)
        existing = self._settlement if self._settlement and self._settlement["id"] == self._hand_token else None
        self._settlement = {
            "id": self._hand_token, "game_id": self._game_id, "hand_no": self._hand_no,
            "ended_at": existing["ended_at"] if existing else time.time(),
            "reveal_seconds": 2.5, "board": list(self._board), "winners": list(merged.values()),
            "bb": int(self._bb or 0),
            "hero": {"seatid": self._my_seat, "hole": list(self._my_hole),
                     "folded": self._seats.get(self._my_seat, {}).get("folded", False),
                     "group": hand_group(self._my_hole, self._board)},
            "revealed": [{"seatid": i, "name": self._seats.get(i, {}).get("name") or f"座位{i}",
                          "hole": list(cards)} for i, cards in self._public_holes.items()],
            "players": [{"seatid": i, "name": s["name"]} for i, s in self._seats.items() if not s["empty"]],
        }

    def _h_winner(self, msg: dict) -> None:
        # Net profit already includes refunds and rake. Adding gross winnings
        # to the last action stack would miss refunds (or count money twice).
        # Keep the baseline unchanged so repeated results are idempotent.
        for p in msg.get("profit") or []:
            if not isinstance(p, dict):
                continue
            uid = p.get("uid")
            seatid = _chip(p.get("seatid"), 0)
            if uid is not None:
                seatid = next((i for i, s in self._seats.items()
                               if s["uid"] == str(uid)), -1)
            s = self._seats.get(seatid)
            if s is not None and s["uid"] in self._hand_start_stacks:
                s["stack"] = self._hand_start_stacks[s["uid"]] + _chip(p.get("chips"))
        winners = msg.get("winner") or []
        names = []
        for w in winners:
            if not isinstance(w, dict):
                continue
            seatid = self._result_seat(w)
            name = self._seats.get(seatid, {}).get("name") or (
                "我" if seatid == self._my_seat else f"座位{seatid}")
            names.append(f"{name} 赢 {_chip(w.get('chips'),0)}")
        mine = next((p for p in (msg.get("profit") or [])
                     if isinstance(p, dict) and self.my_uid and str(p.get("uid")) == self.my_uid), None)
        tail = ""
        if mine is not None:
            d = _chip(mine.get("chips"), 0)
            # Replayed settlements (including after a room snapshot) count once.
            # Neither leaving the room nor buying in starts a new bot session.
            game = self._game_id or self._hand_token
            if game not in self._settled_games:
                self._settled_games.add(game)
                self._session_pnl_chips += d
                if self._session_pnl_bb is not None:
                    self._session_pnl_bb = (self._session_pnl_bb + d / self._bb) if self._bb else None
            tail = f"  本手 {'+' if d >= 0 else ''}{d}"
        self._result = ("  |  ".join(names) + tail).strip()
        self._result_bb = int(self._bb or 0)
        if self._result:
            self._say("▸ " + self._result)
        self._action_seat = None
        self._save_settlement(winners)

    # ── snapshot for the web ─────────────────────────────────────────────────
    def snapshot(self) -> dict:
        rewards, uncertain = self._reward_source() if self._reward_source else (None, False)
        total_chips = self._chips_source() if self._chips_source else None
        with self._lock:
            seats = []
            for i in range(max(self._seat_num, (max(self._seats) + 1) if self._seats else 0)):
                s = self._seats.get(i)
                if s is None:
                    seats.append({"seatid": i, "empty": True})
                    continue
                seats.append({
                    "seatid": i,
                    "name": s["name"],
                    "uid": s["uid"],
                    "stack": s["stack"],
                    "bet": s["bet"],
                    "folded": s["folded"],
                    "allin": s["allin"],
                    "cards": list(s["cards"]),
                    "last": s["last"],
                    "empty": bool(s["empty"]),
                    "is_me": (i == self._my_seat),
                    "acting": (i == self._action_seat),
                    "revealed": bool(s.get("revealed")),
                    "pos": s.get("pos", ""),
                    "kind": "" if s["empty"] or i == self._my_seat else self._player_kind(s["uid"]),
                })
            others = [x for x in seats if not x.get("empty") and not x.get("is_me")]
            robots = sum(1 for x in others if x.get("kind") == "robot")
            return {
                "total_chips": total_chips,
                "session_pnl_chips": self._session_pnl_chips,
                "session_pnl_bb": None if self._session_pnl_bb is None else round(self._session_pnl_bb, 2),
                "session_reward_chips": rewards,
                "session_rewards_uncertain": uncertain,
                "humans": len(others) - robots,
                "robots": robots,
                "updated": self._updated,
                "connected": self._connected,
                "connection_status": self._connection_status,
                "room_id": self._room_id,
                "sb": self._sb,
                "bb": self._bb,
                "seat_num": self._seat_num,
                "hand_no": self._hand_no,
                "game_id": self._game_id,
                "street": self._street,
                "board": list(self._board),
                "pot": self._pot,
                "my_seat": self._my_seat,
                "my_hole": list(self._my_hole),
                "action_seat": self._action_seat,
                "seats": seats,
                "feed": list(self._feed),
                "feed_bb": list(self._feed_bb),
                "result": self._result,
                "result_bb": self._result_bb,
                "settlement": copy.deepcopy(self._settlement),
            }


class _HeadlessRuntime:
    """Expose headless bankroll data to the existing Web dashboard."""

    def __init__(self, bankroll_source: Callable[[], dict] | None = None) -> None:
        import logging
        self.log = logging.getLogger("pf_live_web")
        self._bankroll_source = bankroll_source

    def status_data(self) -> dict:
        return {
            "session_state": "headless",
            "mode": "headless",
            "bot_dashboard": self._bankroll_source() if self._bankroll_source else None,
        }


async def start_live_web(
    observer: "LiveTableObserver", *, host: str = "127.0.0.1", port: int = 9022,
    bankroll_source: Callable[[], dict] | None = None,
):
    """Start the entertainment web server with live-table and bankroll snapshots.

    Returns the running EntertainmentWebServer (call ``await server.start()``
    is already done).  The live tab polls /api/live → observer.snapshot().
    """
    from pf_entertainment.web import EntertainmentWebServer

    server = EntertainmentWebServer(
        runtime=_HeadlessRuntime(bankroll_source), host=host, port=port,
        live_source=observer.snapshot,
    )
    await server.start()
    return server


_HANDLERS = {
    "pb.UserLocationRSP": LiveTableObserver._h_location,
    "pb.LeaveRoomRSP": LiveTableObserver._h_leave_room_rsp,
    "pb.EnterRoomRSP": LiveTableObserver._h_enter_room,
    "pb.SitDownRSP": LiveTableObserver._h_sit_down_rsp,
    "pb.SitDownBRC": LiveTableObserver._h_sit_down_brc,
    "pb.OtherLeaveRoomBRC": LiveTableObserver._h_other_leave,
    "pb.LeaveRoomBRC": LiveTableObserver._h_leave,
    "pb.HandCardRSP": LiveTableObserver._h_hand_card,
    "pb.DealerInfoRSP": LiveTableObserver._h_dealer_info,
    "pb.RoundStartBRC": LiveTableObserver._h_round_start,
    "pb.ActionBRC": LiveTableObserver._h_action,
    "pb.ActionNotifyBRC": LiveTableObserver._h_action_notify,
    "pb.RoundOverBRC": LiveTableObserver._h_round_over,
    "pb.WinnerRSP": LiveTableObserver._h_winner,
    "pb.ShowHandRSP": LiveTableObserver._h_show_hand,
    "pb.ShowMyCardBRC": LiveTableObserver._h_show_my_card,
}
