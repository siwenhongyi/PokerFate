"""Robot (house bot) registry, grown from the server's own robot counter.

The game server broadcasts ``rb_num`` — the number of robots in the room — whenever somebody
leaves (``OtherLeaveRoomBRC``) and, when the server sends it, when somebody enters
(``OtherEnterRoomBRC``).  That counter is the ground truth.  ``RoomRobotTracker`` turns the
stream of counts into per-account labels:

  * count rule    after an event the room holds exactly ``rb_num`` robots; if that equals
                  the number of still-unlabelled accounts they are all robots, if it is 0
                  they are all humans;
  * change rule   between two consecutive counts the difference equals the robots that
                  joined minus the robot that left — "did rb_num change when this player
                  came or went".

Labels are written to ``RobotRegistry`` (a JSON file next to opponents.json) and are never
guessed: an account is ``robot`` or ``human`` only after a count proved it.  Accounts not yet
proven are ``suspect`` when their UID lies inside a dense run of proven robots (the robots'
UIDs were allocated in one block) and ``unknown`` otherwise.

Nothing here imports strategy code, so the wire client, the strategy API, the training
scripts and the analysis tools can all use it.
"""
from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional, Set, Tuple

ROBOT = "robot"
HUMAN = "human"
SUSPECT = "suspect"
UNKNOWN = "unknown"

DEFAULT_PATH = Path(__file__).resolve().parents[1] / "data" / "local_models" / "robots.json"

# A run of proven robots whose neighbouring UIDs are at most this far apart is treated as one
# allocation block; unproven UIDs inside a block are "suspect".
BLOCK_MAX_GAP = 400
BLOCK_MIN_ROBOTS = 5
# A block stops being trusted once this share of its proven accounts turned out human.
BLOCK_MAX_HUMAN_SHARE = 0.02
_SAVE_INTERVAL_SEC = 20.0


def _uid(value) -> str:
    return str(value).strip()


def table_verdict(humans: int, robots: int) -> str:
    """stay / empty / no_humans / outnumbered, counting everybody but us.

    One rule for two questions: the table policy leaves unless this says "stay", and a hand
    dealt at a table it would leave teaches the strategy nothing.
    """
    if humans <= 0:
        return "empty" if robots <= 0 else "no_humans"
    if humans < robots:
        return "outnumbered"
    return "stay"


class RobotRegistry:
    """Persistent uid -> proven label, plus the derived suspect blocks."""

    def __init__(self, path: Optional[os.PathLike] = None, *, autosave: bool = True) -> None:
        self.path = Path(path) if path is not None else DEFAULT_PATH
        self.autosave = autosave
        self._lock = threading.RLock()
        self._labels: Dict[str, dict] = {}
        self._conflicts: Dict[str, dict] = {}
        self._blocks: Optional[List[Tuple[int, int, int]]] = None
        self._dirty = False
        self._last_save = 0.0
        self.load()

    # ── persistence ───────────────────────────────────────────────────────
    def load(self) -> None:
        with self._lock:
            self._labels, self._conflicts = {}, {}
            try:
                data = json.loads(self.path.read_text(encoding="utf-8"))
            except (FileNotFoundError, json.JSONDecodeError, OSError):
                data = {}
            for uid, rec in (data.get("accounts") or {}).items():
                if isinstance(rec, dict) and rec.get("label") in (ROBOT, HUMAN):
                    self._labels[_uid(uid)] = dict(rec)
            for uid, rec in (data.get("conflicts") or {}).items():
                if isinstance(rec, dict):
                    self._conflicts[_uid(uid)] = dict(rec)
            self._blocks = None
            self._dirty = False

    def save(self, *, force: bool = False) -> None:
        with self._lock:
            if not self._dirty and not force:
                return
            payload = {
                "schema": "robot_registry_v1",
                "updated_at": int(time.time()),
                "counts": self.counts(),
                "blocks": [{"lo": lo, "hi": hi, "robots": n} for lo, hi, n in self.blocks()],
                "accounts": dict(sorted(self._labels.items(), key=lambda kv: int(kv[0]) if kv[0].isdigit() else 0)),
                "conflicts": self._conflicts,
            }
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(self.path.suffix + ".tmp")
            tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
            os.replace(tmp, self.path)
            self._dirty = False
            self._last_save = time.time()

    def _maybe_save(self) -> None:
        if self.autosave and self._dirty and time.time() - self._last_save >= _SAVE_INTERVAL_SEC:
            self.save()

    # ── queries ───────────────────────────────────────────────────────────
    def label(self, uid) -> Optional[str]:
        """Proven label ("robot" / "human") or None."""
        rec = self._labels.get(_uid(uid))
        return rec["label"] if rec else None

    def status(self, uid) -> str:
        """robot / human when proven, else suspect (inside a robot UID block) or unknown."""
        proven = self.label(uid)
        if proven:
            return proven
        return SUSPECT if self.in_block(uid) else UNKNOWN

    def is_robot(self, uid, *, include_suspect: bool = True) -> bool:
        status = self.status(uid)
        return status == ROBOT or (include_suspect and status == SUSPECT)

    def robots(self) -> Set[str]:
        return {u for u, r in self._labels.items() if r["label"] == ROBOT}

    def humans(self) -> Set[str]:
        return {u for u, r in self._labels.items() if r["label"] == HUMAN}

    def counts(self) -> dict:
        robots = sum(1 for r in self._labels.values() if r["label"] == ROBOT)
        return {"robot": robots, "human": len(self._labels) - robots, "conflict": len(self._conflicts)}

    def blocks(self) -> List[Tuple[int, int, int]]:
        """[(lo, hi, proven_robots)] for runs of proven robots with small UID gaps."""
        with self._lock:
            if self._blocks is not None:
                return self._blocks
            ids = sorted(int(u) for u, r in self._labels.items() if r["label"] == ROBOT and u.isdigit())
            humans = sorted(int(u) for u, r in self._labels.items() if r["label"] == HUMAN and u.isdigit())
            blocks: List[Tuple[int, int, int]] = []
            run: List[int] = []
            for value in ids + [None]:
                if value is not None and (not run or value - run[-1] <= BLOCK_MAX_GAP):
                    run.append(value)
                    continue
                if len(run) >= BLOCK_MIN_ROBOTS:
                    lo, hi = run[0], run[-1]
                    inside_humans = sum(1 for h in humans if lo <= h <= hi)
                    if inside_humans <= BLOCK_MAX_HUMAN_SHARE * (len(run) + inside_humans):
                        blocks.append((lo, hi, len(run)))
                run = [value] if value is not None else []
            self._blocks = blocks
            return blocks

    def in_block(self, uid) -> bool:
        text = _uid(uid)
        if not text.isdigit():
            return False
        value = int(text)
        return any(lo <= value <= hi for lo, hi, _ in self.blocks())

    # ── updates ───────────────────────────────────────────────────────────
    def confirm(self, uid, label: str, how: str = "", *, ts: Optional[float] = None) -> bool:
        """Record a proven label.  Returns True when it is new information."""
        if label not in (ROBOT, HUMAN):
            raise ValueError(label)
        key = _uid(uid)
        if not key:
            return False
        now = float(ts if ts is not None else time.time())
        with self._lock:
            rec = self._labels.get(key)
            if rec is None:
                if key in self._conflicts:
                    self._conflicts[key][label] = self._conflicts[key].get(label, 0) + 1
                    self._dirty = True
                    return False
                self._labels[key] = {"label": label, "n": 1, "first": int(now), "last": int(now), "how": how}
                self._blocks = None
                self._dirty = True
                self._maybe_save()
                return True
            if rec["label"] == label:
                rec["n"] = int(rec.get("n", 1)) + 1
                rec["last"] = int(now)
                self._dirty = True
                self._maybe_save()
                return False
            # The same account proven both ways: trust neither until looked at by a human.
            self._conflicts[key] = {rec["label"]: int(rec.get("n", 1)), label: 1, "how": [rec.get("how", ""), how]}
            del self._labels[key]
            self._blocks = None
            self._dirty = True
            self._maybe_save()
            return True


class RoomRobotTracker:
    """Per-room inference from the ``rb_num`` counter.  Feed it every seat event."""

    def __init__(self, registry: RobotRegistry, my_uid=None,
                 on_label: Optional[Callable[[str, str, str], None]] = None) -> None:
        self.registry = registry
        self.my_uid = _uid(my_uid) if my_uid is not None else ""
        self.on_label = on_label
        self.members: Set[str] = set()          # everybody else known to be in the room
        self.joined: Set[str] = set()           # joined since the last count
        self.prev_count: Optional[int] = None   # rb_num at the last count, None = no usable base
        self.last_rb_num: Optional[int] = None  # latest rb_num seen in this room (authoritative count)
        self.last_num: Optional[int] = None
        self.pending: List[Tuple[frozenset, int]] = []   # unresolved "c robots among this set"
        self.events = 0
        self.skipped = 0

    # ── room lifecycle ────────────────────────────────────────────────────
    def set_my_uid(self, uid) -> None:
        self.my_uid = _uid(uid)
        self.members.discard(self.my_uid)

    def reset(self, seated: Iterable = ()) -> None:
        """Entered a room (or lost track): start again from the seat snapshot."""
        self.members = {u for u in (_uid(s) for s in seated) if u and u != self.my_uid}
        self.joined = set()
        self.prev_count = None
        self.last_rb_num = None
        self.last_num = None
        self.pending = []

    def sat_down(self, uid) -> None:
        key = _uid(uid)
        if not key or key == self.my_uid or key in self.members:
            return
        self.members.add(key)
        self.joined.add(key)

    def entered(self, uid, num, rb_num, *, ts: Optional[float] = None) -> None:
        key = _uid(uid)
        if not key or key == self.my_uid:
            return
        if key not in self.members:
            self.members.add(key)
            self.joined.add(key)
        self._count(left=None, num=num, rb_num=rb_num, ts=ts)

    def left(self, uid, num, rb_num, *, ts: Optional[float] = None) -> None:
        key = _uid(uid)
        if not key or key == self.my_uid:
            return
        known_member = key in self.members
        self.members.discard(key)
        self._count(left=key if known_member else None, num=num, rb_num=rb_num, ts=ts,
                    unknown_leaver=not known_member)

    # ── inference ─────────────────────────────────────────────────────────
    def _confirm(self, uid: str, label: str, how: str, ts) -> None:
        if self.registry.confirm(uid, label, how, ts=ts) and self.on_label is not None:
            self.on_label(uid, label, how)

    def _count(self, *, left: Optional[str], num, rb_num, ts=None, unknown_leaver: bool = False) -> None:
        self.events += 1
        r = int(rb_num or 0)
        n = int(num or 0)
        self.last_rb_num, self.last_num = r, n
        joined, self.joined = set(self.joined), set()
        prev, self.prev_count = self.prev_count, None
        # ``num`` counts everybody in the room including us.  If it does not match the people
        # we know about, somebody is in the room unseen (or left unseen): no inference now.
        if n != len(self.members) + 1 or r < 0 or r > len(self.members):
            self.skipped += 1
            self.pending = []
            return
        self.prev_count = r
        label = self.registry.label

        # change rule
        if prev is not None and not unknown_leaver:
            if left is not None and left in joined:        # came and went between two counts
                joined.discard(left)
                left_x: Optional[int] = 0                   # contributes nothing to the difference
                left_known = True
            else:
                left_known = left is None or label(left) is not None
                left_x = 0 if left is None else (1 if label(left) == ROBOT else 0)
            known_robots = sum(1 for u in joined if label(u) == ROBOT)
            unknown = [u for u in joined if label(u) is None]
            d = r - prev - known_robots            # = robots among `unknown` − x_left
            if left_known:
                total = d + (left_x or 0)
                if total == 0:
                    for u in unknown:
                        self._confirm(u, HUMAN, "rb_num unchanged on join", ts)
                elif total == len(unknown) and unknown:
                    for u in unknown:
                        self._confirm(u, ROBOT, "rb_num rose on join", ts)
            elif d == -1:
                self._confirm(left, ROBOT, "rb_num fell on leave", ts)
                for u in unknown:
                    self._confirm(u, HUMAN, "rb_num unchanged on join", ts)
            elif d == len(unknown):
                self._confirm(left, HUMAN, "rb_num unchanged on leave", ts)
                for u in unknown:
                    self._confirm(u, ROBOT, "rb_num rose on join", ts)

        # count rule, on the people still in the room
        self.pending.append((frozenset(self.members), r))
        self.pending = self.pending[-40:]
        self._propagate(ts)

    def _propagate(self, ts) -> None:
        label = self.registry.label
        changed = True
        while changed:
            changed = False
            keep: List[Tuple[frozenset, int]] = []
            for members, r in self.pending:
                unknown = [u for u in members if label(u) is None]
                c = r - sum(1 for u in members if label(u) == ROBOT)
                if not unknown or c < 0 or c > len(unknown):
                    continue
                if c == 0:
                    for u in unknown:
                        self._confirm(u, HUMAN, "room robot count", ts)
                    changed = True
                elif c == len(unknown):
                    for u in unknown:
                        self._confirm(u, ROBOT, "room robot count", ts)
                    changed = True
                else:
                    keep.append((members, r))
            self.pending = keep

    # ── what the table policy needs ───────────────────────────────────────
    def composition(self, seated: Iterable) -> dict:
        """Humans / robots among the given seated opponents.

        The server's own count wins when it is current for exactly these people; otherwise
        proven labels are used and unproven accounts inside a robot UID block count as robots.
        """
        uids = [u for u in (_uid(s) for s in seated) if u and u != self.my_uid]
        robots = sum(1 for u in uids if self.registry.is_robot(u))
        source = "labels"
        if (self.last_rb_num is not None and not self.joined and self.prev_count is not None
                and set(uids) == self.members):
            robots, source = self.last_rb_num, "rb_num"
        return {"humans": len(uids) - robots, "robots": robots, "total": len(uids), "source": source,
                "unproven": sum(1 for u in uids if self.registry.label(u) is None)}


_default: Optional[RobotRegistry] = None
_default_lock = threading.Lock()


def default_registry() -> RobotRegistry:
    """Process-wide registry on the default path (env ``PF_ROBOT_REGISTRY`` overrides)."""
    global _default
    with _default_lock:
        if _default is None:
            _default = RobotRegistry(os.environ.get("PF_ROBOT_REGISTRY") or None)
        return _default
