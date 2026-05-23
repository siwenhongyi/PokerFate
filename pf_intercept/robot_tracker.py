from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

log = logging.getLogger("pf_robot")


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _int(value: Any, default: int = 0) -> int:
    try:
        if value is None:
            return default
        return int(value)
    except (TypeError, ValueError, OverflowError):
        return default


def _uid(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return text


class RobotTracker:
    """Persist compact rb_num evidence across proxy.log rotations."""

    def __init__(self, data_dir: Path) -> None:
        self._data_dir = data_dir
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._events_file = self._data_dir / "robot_events.jsonl"
        self._summary_file = self._data_dir / "robot_players.json"

        self._self_uids: set[str] = set()
        self._current_room_id: int = 0
        self._last_rb_num_by_room: dict[int, int] = {}
        self._players_by_uid: dict[str, dict[str, Any]] = {}
        self._summary: dict[str, Any] = self._load_summary()

    def set_self_uid(self, uid: Any) -> None:
        uid_str = _uid(uid)
        if not uid_str:
            return
        self._self_uids.add(uid_str)
        robots = self._summary.get("robots")
        if isinstance(robots, dict) and uid_str in robots:
            robots.pop(uid_str, None)
            self._summary["updated_at"] = _now_iso()
            self._write_summary()

    def observe(
        self,
        type_name: str,
        msg: dict,
        *,
        room_id: int = 0,
        observed_at: str | None = None,
    ) -> None:
        try:
            self._observe(type_name, msg, room_id=_int(room_id, 0), observed_at=observed_at)
        except Exception:
            log.exception("[ROBOT] tracker failed for %s", type_name)

    def _observe(
        self,
        type_name: str,
        msg: dict,
        *,
        room_id: int,
        observed_at: str | None,
    ) -> None:
        if type_name == "pb.EnterRoomRSP":
            self._on_enter_room(msg, room_id=room_id)
        elif type_name == "pb.SitDownBRC":
            self._remember_seat(msg.get("status") or {}, room_id=room_id)
        elif type_name == "pb.OtherEnterRoomBRC":
            self._on_other_enter(msg, room_id=room_id, observed_at=observed_at)
        elif type_name == "pb.OtherLeaveRoomBRC":
            self._on_other_leave(msg, room_id=room_id, observed_at=observed_at)

    def _on_enter_room(self, msg: dict, *, room_id: int) -> None:
        room = self._resolve_room_id(msg, room_id)
        if room > 0:
            self._current_room_id = room
        table_status = msg.get("table_status") or {}
        for seat_status in table_status.get("seat", []) or []:
            self._remember_seat(seat_status, room_id=room)

    def _on_other_enter(self, msg: dict, *, room_id: int, observed_at: str | None) -> None:
        room = self._resolve_room_id(msg, room_id)
        user = self._remember_user(msg.get("user") or {}, room_id=room)
        new_rb = _int(msg.get("rb_num"), 0)
        old_rb = self._last_rb_num_by_room.get(room)
        inference = self._infer("enter", old_rb, new_rb)
        event = self._event(
            "enter",
            "pb.OtherEnterRoomBRC",
            room,
            user,
            msg,
            old_rb,
            new_rb,
            inference,
            observed_at=observed_at,
        )
        self._last_rb_num_by_room[room] = new_rb
        self._append_event(event)
        self._log_event(event)

    def _on_other_leave(self, msg: dict, *, room_id: int, observed_at: str | None) -> None:
        room = self._resolve_room_id(msg, room_id)
        uid = _uid(msg.get("uid"))
        user = dict(self._players_by_uid.get(uid) or {})
        if uid and not user:
            user = {"uid": uid}
        new_rb = _int(msg.get("rb_num"), 0)
        old_rb = self._last_rb_num_by_room.get(room)
        inference = self._infer("leave", old_rb, new_rb)
        event = self._event(
            "leave",
            "pb.OtherLeaveRoomBRC",
            room,
            user,
            msg,
            old_rb,
            new_rb,
            inference,
            observed_at=observed_at,
        )
        self._last_rb_num_by_room[room] = new_rb
        self._append_event(event)
        if inference == "robot_leave":
            self._mark_robot(user, event, reason="rb_num decreased on leave")
        if uid:
            self._players_by_uid.pop(uid, None)
        self._log_event(event)

    def _resolve_room_id(self, msg: dict, frame_room_id: int) -> int:
        room = _int(msg.get("roomid"), 0)
        if room <= 0:
            room = _int(frame_room_id, 0)
        if room <= 0:
            room = self._current_room_id
        return room

    def _remember_seat(self, seat_status: dict, *, room_id: int) -> None:
        player = seat_status.get("player") or {}
        seat_id = _int(seat_status.get("seatid"), 0)
        self._remember_user(player, room_id=room_id, seat_id=seat_id)

    def _remember_user(
        self,
        user: dict,
        *,
        room_id: int,
        seat_id: int | None = None,
    ) -> dict[str, Any]:
        uid = _uid(user.get("uid"))
        if not uid:
            return {}
        info = dict(self._players_by_uid.get(uid) or {})
        info["uid"] = uid
        name = str(user.get("name") or "").strip()
        if name:
            info["name"] = name
        avatar = user.get("avatar")
        if avatar is not None:
            info["avatar"] = avatar
        if seat_id is not None:
            info["seat_id"] = seat_id
        if room_id > 0:
            info["room_id"] = room_id
        self._players_by_uid[uid] = info
        return dict(info)

    def _infer(self, event: str, old_rb: int | None, new_rb: int) -> str:
        if old_rb is None:
            return "rb_count_seen"
        if event == "enter":
            if new_rb > old_rb:
                return "rb_count_increased_on_enter"
            if new_rb == old_rb:
                return "non_robot_enter"
            return "rb_count_decreased_on_enter"
        if new_rb < old_rb:
            return "robot_leave"
        if new_rb == old_rb:
            return "non_robot_leave"
        return "rb_count_increased_on_leave"

    def _event(
        self,
        event: str,
        type_name: str,
        room_id: int,
        user: dict[str, Any],
        msg: dict,
        old_rb: int | None,
        new_rb: int,
        inference: str,
        observed_at: str | None = None,
    ) -> dict[str, Any]:
        delta = None if old_rb is None else new_rb - old_rb
        return {
            "ts": observed_at or _now_iso(),
            "event": event,
            "type": type_name,
            "room_id": room_id,
            "uid": user.get("uid") or _uid(msg.get("uid")),
            "name": user.get("name") or "",
            "seat_id": user.get("seat_id"),
            "num": _int(msg.get("num"), 0),
            "player": _int(msg.get("player"), 0),
            "old_rb_num": old_rb,
            "new_rb_num": new_rb,
            "rb_delta": delta,
            "rb_num_present": "rb_num" in msg,
            "inference": inference,
        }

    def _append_event(self, event: dict[str, Any]) -> None:
        line = json.dumps(event, ensure_ascii=False, separators=(",", ":"))
        with self._events_file.open("a", encoding="utf-8") as fh:
            fh.write(line)
            fh.write("\n")

    def _load_summary(self) -> dict[str, Any]:
        try:
            data = json.loads(self._summary_file.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                data.setdefault("robots", {})
                return data
        except FileNotFoundError:
            pass
        except Exception:
            log.exception("[ROBOT] failed to load %s", self._summary_file)
        return {"robots": {}}

    def _mark_robot(self, user: dict[str, Any], event: dict[str, Any], *, reason: str) -> None:
        uid = _uid(event.get("uid") or user.get("uid"))
        if not uid:
            return
        if uid in self._self_uids:
            log.info("[ROBOT] skip self uid=%s for robot evidence", uid)
            return
        ts = str(event.get("ts") or _now_iso())
        robots = self._summary.setdefault("robots", {})
        item = robots.setdefault(
            uid,
            {
                "uid": uid,
                "first_seen_at": ts,
                "evidence_count": 0,
                "rooms": [],
                "evidence": [],
            },
        )
        name = str(event.get("name") or user.get("name") or "").strip()
        if name:
            item["name"] = name
        item["last_seen_at"] = ts
        item["evidence_count"] = int(item.get("evidence_count") or 0) + 1
        room_id = _int(event.get("room_id"), 0)
        rooms = list(item.get("rooms") or [])
        if room_id > 0 and room_id not in rooms:
            rooms.append(room_id)
        item["rooms"] = rooms[-20:]
        evidence = list(item.get("evidence") or [])
        evidence.append(
            {
                "ts": ts,
                "event": event.get("event"),
                "room_id": room_id,
                "old_rb_num": event.get("old_rb_num"),
                "new_rb_num": event.get("new_rb_num"),
                "reason": reason,
            }
        )
        item["evidence"] = evidence[-20:]
        self._summary["updated_at"] = ts
        self._write_summary()

    def _write_summary(self) -> None:
        self._summary_file.write_text(
            json.dumps(self._summary, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )

    def _log_event(self, event: dict[str, Any]) -> None:
        old_rb = event.get("old_rb_num")
        old_text = "?" if old_rb is None else str(old_rb)
        name = event.get("name") or ""
        uid = event.get("uid") or "?"
        log.info(
            "[ROBOT] %s uid=%s name=%s room=%s rb_num %s -> %s inference=%s",
            event.get("event"),
            uid,
            name,
            event.get("room_id"),
            old_text,
            event.get("new_rb_num"),
            event.get("inference"),
        )
