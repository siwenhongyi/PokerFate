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
from collections import deque
from typing import Any

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


class LiveTableObserver:
    """Maintains a thread-safe render snapshot of the live table."""

    def __init__(self, *, my_uid: int | str | None = None, log_size: int = 14) -> None:
        self.my_uid = str(my_uid) if my_uid is not None else None
        self._lock = threading.Lock()
        self._feed: deque[str] = deque(maxlen=log_size)
        self._seats: dict[int, dict] = {}
        self._reset_table()
        self._connected = False
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
            self._updated = time.time()

    def set_my_uid(self, uid: int | str | None) -> None:
        with self._lock:
            self.my_uid = str(uid) if uid is not None else None

    def _reset_table(self) -> None:
        self._board: list[str] = []
        self._pot = 0
        self._street = ""
        self._my_seat: int | None = None
        self._my_hole: list[str] = []
        self._action_seat: int | None = None

    def _reset_hand(self) -> None:
        self._board = []
        self._pot = 0
        self._street = "preflop"
        self._my_hole = []
        self._action_seat = None
        for s in self._seats.values():
            s["bet"] = 0
            s["folded"] = False
            s["allin"] = False
            s["last"] = ""
            s["cards"] = []

    def _seat(self, seatid: int) -> dict:
        s = self._seats.get(seatid)
        if s is None:
            s = {
                "seatid": seatid, "name": "", "uid": "", "stack": 0, "bet": 0,
                "folded": False, "allin": False, "cards": [], "last": "", "empty": True,
            }
            self._seats[seatid] = s
        return s

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
        self._room_id = _chip(msg.get("roomid"), self._room_id)
        room_info = msg.get("room_info") or {}
        self._sb = _chip(room_info.get("sb"), self._sb)
        self._bb = _chip(room_info.get("bb"), self._bb)
        self._seat_num = _chip(room_info.get("seat_num"), self._seat_num) or 6
        ts = msg.get("table_status") or {}
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
                if self.my_uid and str(uid) == self.my_uid:
                    self._my_seat = seatid
            else:
                s["empty"] = not bool(entry.get("has_card"))
            s["stack"] = _chip(entry.get("hand_chips"), s["stack"])
            at = _chip(entry.get("last_action_type"), 0)
            s["folded"] = at in _FOLD_ACTIONS
            s["allin"] = bool(entry.get("is_allin"))
        board = [c for c in (_card_str(x) for x in ts.get("board") or []) if c]
        if board:
            self._board = board
        self._pot = sum(_chip(p, 0) for p in ts.get("pool") or []) or self._pot
        stage = _chip(ts.get("stage"), 0)
        if stage:
            self._street = _STAGE_TO_STREET.get(stage, self._street)
        playing = msg.get("playing_status") or {}
        if "action_seatid" in playing:
            self._action_seat = _chip(playing.get("action_seatid"), -1)

    def _h_sit_down_rsp(self, msg: dict) -> None:
        seatid = _chip(msg.get("seatid"), -1)
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
        seatid = _chip(status.get("seatid"), -1)
        if seatid < 0:
            return
        player = status.get("player") or {}
        s = self._seat(seatid)
        if player.get("uid"):
            s["uid"] = str(player.get("uid"))
            s["name"] = player.get("name") or s["name"] or f"玩家{seatid}"
        s["stack"] = _chip(status.get("hand_chips"), s["stack"])
        s["empty"] = False

    def _h_leave(self, msg: dict) -> None:
        seatid = _chip(msg.get("seatid"), -1)
        if seatid >= 0 and seatid in self._seats:
            self._seats[seatid] = {
                "seatid": seatid, "name": "", "uid": "", "stack": 0, "bet": 0,
                "folded": False, "allin": False, "cards": [], "last": "", "empty": True,
            }

    def _h_hand_card(self, msg: dict) -> None:
        cards = [c for c in (_card_str(msg.get(k)) for k in ("card1", "card2", "card3", "card4")) if c]
        seatid = msg.get("seatid")
        seatid = _chip(seatid, self._my_seat if self._my_seat is not None else -1)
        if cards:
            self._my_hole = cards[:4]
            if seatid >= 0:
                self._seat(seatid)["cards"] = cards[:4]

    def _h_dealer_info(self, msg: dict) -> None:
        self._reset_hand()
        self._hand_no += 1
        self._result = ""
        for entry in msg.get("start_info") or []:
            if not isinstance(entry, dict):
                continue
            seatid = _chip(entry.get("seatid"), -1)
            if seatid < 0:
                continue
            self._seat(seatid)["stack"] = _chip(entry.get("chips"), self._seat(seatid)["stack"])

    def _h_round_start(self, msg: dict) -> None:
        stage = _chip(msg.get("stage"), 0)
        if stage:
            self._street = _STAGE_TO_STREET.get(stage, self._street)
        # RoundStartBRC carries only the cards newly revealed this street
        # (flop=3, turn=1, river=1); accumulate so the whole board stays shown
        # (dedup also tolerates a message that repeats the full board).
        for c in (_card_str(x) for x in msg.get("board") or []):
            if c and c not in self._board:
                self._board.append(c)
        # New street: street bets are swept into the pot.
        for s in self._seats.values():
            s["bet"] = 0

    def _h_action(self, msg: dict) -> None:
        seatid = _chip(msg.get("seatid"), self._action_seat if self._action_seat is not None else -1)
        at = _chip(msg.get("action_type"), 0)
        chips = _chip(msg.get("chips"), 0)
        s = self._seat(seatid) if seatid >= 0 else None
        label = _ACTION_LABEL.get(at, "")
        if s is not None:
            if "hand_chips" in msg:
                s["stack"] = _chip(msg.get("hand_chips"), s["stack"])
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
        if label and at not in _BLIND_ACTIONS:
            amt = f" {chips}" if chips > 0 and at not in _FOLD_ACTIONS else ""
            self._feed.append(f"{who} {label}{amt}")

    def _h_action_notify(self, msg: dict) -> None:
        self._action_seat = _chip(msg.get("seatid"), self._action_seat if self._action_seat is not None else -1)

    def _h_round_over(self, msg: dict) -> None:
        for s in self._seats.values():
            s["bet"] = 0

    def _h_winner(self, msg: dict) -> None:
        winners = msg.get("winner") or []
        names = []
        for w in winners:
            if not isinstance(w, dict):
                continue
            seatid = _chip(w.get("seatid"), -1)
            name = self._seats.get(seatid, {}).get("name") or (
                "我" if seatid == self._my_seat else f"座位{seatid}")
            names.append(f"{name} 赢 {_chip(w.get('chips'),0)}")
        mine = next((p for p in (msg.get("profit") or [])
                     if isinstance(p, dict) and self.my_uid and str(p.get("uid")) == self.my_uid), None)
        tail = ""
        if mine is not None:
            d = _chip(mine.get("chips"), 0)
            tail = f"  本手 {'+' if d >= 0 else ''}{d}"
        self._result = ("  |  ".join(names) + tail).strip()
        if self._result:
            self._feed.append("▸ " + self._result)
        self._action_seat = None

    # ── snapshot for the web ─────────────────────────────────────────────────
    def snapshot(self) -> dict:
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
                })
            return {
                "updated": self._updated,
                "connected": self._connected,
                "room_id": self._room_id,
                "sb": self._sb,
                "bb": self._bb,
                "seat_num": self._seat_num,
                "hand_no": self._hand_no,
                "street": self._street,
                "board": list(self._board),
                "pot": self._pot,
                "my_seat": self._my_seat,
                "my_hole": list(self._my_hole),
                "action_seat": self._action_seat,
                "seats": seats,
                "feed": list(self._feed),
                "result": self._result,
            }


class _StubRuntime:
    """Minimal runtime so EntertainmentWebServer can serve the live tab in
    headless mode (other tabs degrade to empty — they need the proxy stack)."""

    def __init__(self) -> None:
        import logging
        self.log = logging.getLogger("pf_live_web")

    def status_data(self) -> dict:
        return {"session_state": "headless", "mode": "headless"}

    def bot_settings_data(self) -> dict:
        return {}

    def update_bot_settings(self, payload: dict) -> dict:
        return {}


async def start_live_web(observer: "LiveTableObserver", *, host: str = "127.0.0.1", port: int = 9022):
    """Start the entertainment web server bound to this observer's snapshot.

    Returns the running EntertainmentWebServer (call ``await server.start()``
    is already done).  The live tab polls /api/live → observer.snapshot().
    """
    from pf_entertainment.web import EntertainmentWebServer

    server = EntertainmentWebServer(
        runtime=_StubRuntime(), host=host, port=port, live_source=observer.snapshot
    )
    await server.start()
    return server


_HANDLERS = {
    "pb.EnterRoomRSP": LiveTableObserver._h_enter_room,
    "pb.SitDownRSP": LiveTableObserver._h_sit_down_rsp,
    "pb.SitDownBRC": LiveTableObserver._h_sit_down_brc,
    "pb.OtherLeaveRoomBRC": LiveTableObserver._h_leave,
    "pb.LeaveRoomBRC": LiveTableObserver._h_leave,
    "pb.HandCardRSP": LiveTableObserver._h_hand_card,
    "pb.DealerInfoRSP": LiveTableObserver._h_dealer_info,
    "pb.RoundStartBRC": LiveTableObserver._h_round_start,
    "pb.ActionBRC": LiveTableObserver._h_action,
    "pb.ActionNotifyBRC": LiveTableObserver._h_action_notify,
    "pb.RoundOverBRC": LiveTableObserver._h_round_over,
    "pb.WinnerRSP": LiveTableObserver._h_winner,
}
