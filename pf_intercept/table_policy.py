"""Table selection: never stay at a table that has no humans, or fewer humans than robots.

Pure decision logic (no I/O).  ``BotBridge`` feeds it the table composition and a clock tick and
turns the returned steps into wire requests.  Play itself is untouched: at an acceptable
table the existing strategy runs unchanged, at an unacceptable one the bot simply leaves.

Rules (H = human opponents, R = robots, both excluding us):

    H = 0, R = 0   empty table: wait ``empty_grace_sec`` for somebody to sit, then leave
    H = 0, R >= 1  leave at once
    H >= 1, H < R  leave: at once when we have not been dealt in yet, otherwise after it held
                   at ``mixed_confirm_hands`` consecutive hand ends (a human re-buying or a
                   seat changing hands must not throw us out)
    otherwise      stay

Stakes.  ``ladder`` is a preference order (home stake first), not a one-way staircase:

  * a search always asks for the most preferred stake that is not cooling down;
  * ``tries_per_stake`` rejected tables in a row are one failed round at that stake, which
    puts it on a cool-down of ``stake_retry[0]`` seconds, doubling with every further failed
    round up to ``stake_retry[1]``; finding an acceptable table there clears it;
  * while we play at a less preferred stake and the cool-down of a more preferred one runs
    out, we leave after the current hand and probe upwards — so a fallback stake is never
    permanent.  One trip probes every more preferred stake that is due (or due within
    ``probe_batch_sec``) with ``probe_tries`` tables each, then returns to the stake that
    worked;
  * when every usable stake has failed ``max_fail_rounds`` rounds in a row the search stops
    (the caller notifies the user).
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Optional

from pokerfate.core.robots import table_verdict

# Lobby cash levels the bot may use: official minimum up to the user's cap.  The practice room
# is a different game type and can never be reached with these blinds.
ALLOWED_STAKES = (1000, 2000, 5000, 10000, 20000)

SEATED = "seated"            # at an acceptable table
PROBING = "probing"          # empty table: waiting for an opponent until the deadline
LEAVING = "leaving"          # leave requested, waiting for the server
SCHEDULED = "scheduled"      # in the lobby, next match is timed
MATCHING = "matching"        # QuickStart sent, waiting for the room
STOPPED = "stopped"          # every usable stake failed max_fail_rounds rounds
IDLE = "idle"                # not managing anything (before the first table / foreign leave)


def default_ladder(home_bb: int, allowed=ALLOWED_STAKES) -> tuple:
    """Preference order: home stake, then the nearest stakes — the higher one before the
    lower one at each distance, so the fallback does not only ever walk downwards."""
    stakes = sorted(set(int(s) for s in allowed))
    home = int(home_bb)
    if home not in stakes:
        return (home,) if home > 0 else ()
    i = stakes.index(home)
    lower, higher = stakes[:i][::-1], stakes[i + 1:]
    out = [home]
    while lower or higher:
        if higher:
            out.append(higher.pop(0))
        if lower:
            out.append(lower.pop(0))
    return tuple(out)


def parse_ladder(text: str, home_bb: int, allowed=ALLOWED_STAKES) -> tuple:
    """``"10000,5000,20000"`` -> validated ladder; empty text -> default ladder."""
    if not str(text or "").strip():
        return default_ladder(home_bb, allowed)
    out = []
    for part in str(text).replace(" ", "").split(","):
        if not part:
            continue
        bb = int(part)
        if bb not in allowed:
            raise ValueError(f"盲注 {bb} 不在允许的场次 {list(allowed)} 内")
        if bb not in out:
            out.append(bb)
    if not out:
        return default_ladder(home_bb, allowed)
    return tuple(out)


@dataclass
class TablePolicyConfig:
    home_bb: int
    buyin_bb: int = 100
    ladder: tuple = ()
    tries_per_stake: int = 3
    hop_delay: tuple = (3.0, 5.0)
    stake_retry: tuple = (900.0, 3600.0)   # cool-down after a failed round: first, cap (doubling)
    max_fail_rounds: int = 3               # stop when every usable stake failed this many rounds
    probe_tries: int = 2                   # tables per stake on an upward trip from a good table
    probe_batch_sec: float = 600.0         # a trip also covers stakes due within this many seconds
    mixed_confirm_hands: int = 2
    empty_grace_sec: float = 10.0
    wait_blind: bool = True
    leave_retry_sec: float = 90.0
    match_timeout_sec: float = 60.0

    def __post_init__(self) -> None:
        if not self.ladder:
            self.ladder = default_ladder(self.home_bb)
        self.ladder = tuple(int(b) for b in self.ladder)


def configured_policy(home_bb: int, buyin_bb: int = 100, stakes: str = "") -> TablePolicyConfig:
    """Shared runtime settings for headless and proxy cash tables."""
    from pf_intercept import config

    ladder = parse_ladder(stakes, home_bb)
    if ladder[0] != home_bb:
        ladder = (home_bb,) + tuple(bb for bb in ladder if bb != home_bb)
    return TablePolicyConfig(
        home_bb=home_bb, buyin_bb=buyin_bb, ladder=ladder,
        tries_per_stake=int(config.TABLE_SELECT_TRIES_PER_STAKE),
        hop_delay=tuple(config.TABLE_SELECT_HOP_DELAY_SEC),
        stake_retry=tuple(config.TABLE_SELECT_STAKE_RETRY_SEC),
        max_fail_rounds=int(config.TABLE_SELECT_MAX_FAIL_ROUNDS),
        probe_tries=int(config.TABLE_SELECT_PROBE_TRIES),
        probe_batch_sec=float(config.TABLE_SELECT_PROBE_BATCH_SEC),
        mixed_confirm_hands=int(config.TABLE_SELECT_MIXED_CONFIRM_HANDS),
        empty_grace_sec=float(config.TABLE_SELECT_EMPTY_GRACE_SEC),
        wait_blind=bool(config.TABLE_SELECT_WAIT_BLIND),
    )


@dataclass
class Step:
    """What the bridge should do now.  ``kind``: none / leave / match / stop."""
    kind: str = "none"
    reason: str = ""
    delayed: bool = False          # leave: use "leave after this hand" instead of leaving now
    bb: int = 0                    # match: stake to ask for
    info: dict = field(default_factory=dict)

    def __bool__(self) -> bool:
        return self.kind != "none"


NONE = Step()


verdict = table_verdict


class TablePolicy:
    def __init__(self, cfg: TablePolicyConfig, rng: Optional[random.Random] = None) -> None:
        self.cfg = cfg
        self.rng = rng or random.Random()
        self.state = IDLE
        self.stake_idx = 0
        self.tries = 0               # rejected tables in a row at the current stake (this round)
        self.fail_rounds: dict = {}  # stake -> failed rounds in a row
        self.retry_at: dict = {}     # stake -> time its cool-down ends
        self.probe_floor: Optional[int] = None   # upward trip: index of the stake we came from
        self.bad_streak = 0          # consecutive hand ends with humans < robots
        self.dealt = False           # have we been dealt a hand at this table
        self.deadline = 0.0          # PROBING: empty-table grace; LEAVING: retry; MATCHING: timeout
        self.next_match_at = 0.0
        self.unavailable: set = set()   # stakes the server refused (level / bankroll)
        self.table_bb = 0
        self.history: list = []      # compact log of what happened, newest last

    # ── helpers ───────────────────────────────────────────────────────────
    @property
    def searching(self) -> bool:
        return self.state in (PROBING, LEAVING, SCHEDULED, MATCHING)

    @property
    def stopped(self) -> bool:
        return self.state == STOPPED

    def current_bb(self) -> int:
        ladder = self.cfg.ladder
        return int(ladder[min(self.stake_idx, len(ladder) - 1)]) if ladder else int(self.cfg.home_bb)

    def _note(self, event: str, **fields) -> dict:
        rec = {"event": event, "state": self.state, "bb": self.table_bb or self.current_bb(),
               "tries": self.tries, **fields}
        self.history.append(rec)
        self.history = self.history[-200:]
        return rec

    def _leave(self, reason: str, now: float, *, delayed: bool, humans: int, robots: int,
               rejected: bool) -> Step:
        if rejected:
            self.tries += 1
        else:
            # leaving a table we had accepted (it went bad, or a better stake is due):
            # a fresh search at the most preferred stake that is not cooling down
            self.tries = 0
            if reason != "better_stake":
                self.probe_floor = None
            idx = self._pick_stake(now)
            if idx is not None:
                self.stake_idx = idx
        self.state = LEAVING
        self.deadline = now + self.cfg.leave_retry_sec
        self.bad_streak = 0
        return Step("leave", reason, delayed=delayed,
                    info=self._note("leave", reason=reason, humans=humans, robots=robots,
                                    delayed=delayed, rejected=rejected))

    # ── stake preference ──────────────────────────────────────────────────
    def _usable(self) -> list:
        return [i for i, bb in enumerate(self.cfg.ladder) if bb not in self.unavailable]

    def _cooldown(self, rounds: int) -> float:
        first, cap = float(self.cfg.stake_retry[0]), float(self.cfg.stake_retry[1])
        return min(cap, first * (2 ** max(0, int(rounds) - 1)))

    def _fail_stake(self, idx: int, now: float) -> None:
        bb = self.cfg.ladder[idx]
        rounds = int(self.fail_rounds.get(bb, 0)) + 1
        self.fail_rounds[bb] = rounds
        self.retry_at[bb] = now + self._cooldown(rounds)
        self._note("stake_failed", stake=bb, rounds=rounds, cooldown=round(self._cooldown(rounds)))

    def _pick_stake(self, now: float) -> Optional[int]:
        """Most preferred usable stake whose cool-down is over."""
        for i in self._usable():
            if self.retry_at.get(self.cfg.ladder[i], 0.0) <= now:
                return i
        return None

    def _better_stake_due(self, now: float) -> Optional[int]:
        """A stake we prefer to the current one that may be probed again."""
        for i in self._usable():
            if i >= self.stake_idx:
                break
            if self.retry_at.get(self.cfg.ladder[i], 0.0) <= now:
                return i
        return None

    def _tries_limit(self) -> int:
        """Tables to try at the current stake: fewer on an upward trip from a good table."""
        if self.probe_floor is not None and self.stake_idx < self.probe_floor:
            return max(1, int(self.cfg.probe_tries))
        return max(1, int(self.cfg.tries_per_stake))

    def _start_upward_trip(self, now: float) -> None:
        """Leave a good fallback table once and probe everything better that is (nearly) due."""
        self.probe_floor = self.stake_idx
        horizon = now + float(self.cfg.probe_batch_sec)
        for i in self._usable():
            if i >= self.stake_idx:
                break
            bb = self.cfg.ladder[i]
            if self.retry_at.get(bb, 0.0) <= horizon:
                self.retry_at[bb] = min(self.retry_at.get(bb, 0.0), now)

    def _settle(self, humans: int, robots: int) -> Step:
        self.state = SEATED
        self.tries = 0
        self.bad_streak = 0
        self.probe_floor = None
        bb = self.current_bb()
        self.fail_rounds[bb] = 0
        self.retry_at[bb] = 0.0
        self._note("stay", humans=humans, robots=robots)
        return NONE

    # ── events ────────────────────────────────────────────────────────────
    def match_fields(self, fields: dict) -> dict:
        """Apply the policy to an outgoing QuickStart (stake, buy-in, wait for the big blind)."""
        out = dict(fields)
        if self.searching or self.state == IDLE:
            bb = self.current_bb()
            if bb > 0:
                out["boot"] = bb
                out["byin_chips"] = bb * int(self.cfg.buyin_bb)
        out["wait_blind"] = bool(self.cfg.wait_blind)
        return out

    def on_match_sent(self, now: float) -> None:
        if self.state in (IDLE, SCHEDULED, STOPPED):
            if self.state == STOPPED:
                return
            self.state = MATCHING
            self.deadline = now + self.cfg.match_timeout_sec

    def on_enter(self, bb: int, humans: int, robots: int, now: float, *, dealt: bool = False) -> Step:
        """A room snapshot arrived (new table, or the same table after a reconnect).

        ``dealt``: we already hold cards in the hand in progress (reconnect mid-hand); the
        table is then judged at the end of that hand like any table we are playing at.
        """
        self.table_bb = int(bb or 0)
        if self.table_bb in self.cfg.ladder:
            self.stake_idx = self.cfg.ladder.index(self.table_bb)
        self.dealt = bool(dealt)
        self.bad_streak = 0
        self.state = SEATED
        self._note("enter", humans=humans, robots=robots, dealt=bool(dealt))
        if dealt and humans + robots > 0:
            return NONE
        return self.on_seats_changed(humans, robots, now)

    def on_dealt(self) -> None:
        self.dealt = True

    def on_seats_changed(self, humans: int, robots: int, now: float) -> Step:
        if self.state not in (SEATED, PROBING):
            return NONE
        v = verdict(humans, robots)
        if v == "empty":
            if self.state != PROBING:
                self.state = PROBING
                self.deadline = now + self.cfg.empty_grace_sec
                self.bad_streak = 0
            return NONE
        self.state = SEATED
        if not self.dealt:
            if v == "stay":
                return self._settle(humans, robots)
            return self._leave(v, now, delayed=False, humans=humans, robots=robots, rejected=True)
        if v == "no_humans":
            return self._leave(v, now, delayed=True, humans=humans, robots=robots, rejected=False)
        return NONE

    def on_hand_end(self, humans: int, robots: int, now: float) -> Step:
        # Before our first hand the table is judged on seat events and the clock, not here.
        if self.state not in (SEATED, PROBING) or not self.dealt:
            return NONE
        step = self.on_seats_changed(humans, robots, now)
        if step or self.state == PROBING:
            return step
        if humans < robots:
            self.bad_streak += 1
            if self.bad_streak >= max(1, int(self.cfg.mixed_confirm_hands)):
                return self._leave("outnumbered", now, delayed=True, humans=humans, robots=robots, rejected=False)
            return NONE
        self.bad_streak = 0
        # A good table at a fallback stake: go back up as soon as a stake we prefer may be
        # probed again, so a fallback never becomes permanent.
        better = self._better_stake_due(now)
        if better is not None:
            self._start_upward_trip(now)
            return self._leave("better_stake", now, delayed=True, humans=humans, robots=robots,
                               rejected=False)
        return NONE

    def on_errand(self, now: float, humans: int, robots: int) -> Step:
        """Something has to be done away from the table: leave when this hand ends, as from a
        table that was accepted, and search again afterwards. Only from a table we are playing
        at; anywhere else a match is on its way already."""
        if self.state != SEATED or not self.dealt:
            return NONE
        return self._leave("errand", now, delayed=True, humans=humans, robots=robots, rejected=False)

    def on_left(self, now: float, *, ours: bool) -> Step:
        """We are back in the lobby.  ``ours``: the policy asked for this leave."""
        self.table_bb = 0
        self.dealt = False
        if not ours:
            if self.state != STOPPED:
                self.state = IDLE
            return NONE
        return self._schedule_next(now)

    def on_transport_reset(self) -> None:
        """The connection dropped: a pending leave or match request is void."""
        if self.state in (LEAVING, MATCHING, PROBING, SEATED):
            self.state = IDLE
        self.dealt = False

    def on_match_failed(self, code: int, now: float) -> Step:
        """The server refused the QuickStart (not enough chips, level limit, …)."""
        if self.state not in (MATCHING, SCHEDULED, IDLE):
            return NONE
        self.unavailable.add(self.current_bb())
        self._note("match_failed", code=int(code))
        return self._schedule_next(now)

    def _schedule_next(self, now: float) -> Step:
        ladder = self.cfg.ladder
        pause = self.rng.uniform(float(self.cfg.hop_delay[0]), float(self.cfg.hop_delay[1]))
        refused = self.current_bb() in self.unavailable
        if refused or self.tries >= self._tries_limit():
            if not refused:
                self._fail_stake(self.stake_idx, now)
            self.tries = 0
            idx = self._pick_stake(now)
            if idx is None:
                usable = self._usable()
                if not usable or all(int(self.fail_rounds.get(ladder[i], 0)) >= int(self.cfg.max_fail_rounds)
                                     for i in usable):
                    self.state = STOPPED
                    return Step("stop", "no_acceptable_table",
                                info=self._note("stop", unavailable=sorted(self.unavailable),
                                                fail_rounds=dict(self.fail_rounds)))
                # everything is cooling down: wait for the stake that comes back first
                idx = min(usable, key=lambda i: (self.retry_at.get(ladder[i], 0.0), i))
                pause += max(0.0, self.retry_at.get(ladder[idx], 0.0) - now)
            self.stake_idx = idx
        self.state = SCHEDULED
        self.next_match_at = now + pause
        self._note("schedule", delay=round(pause, 1), next_bb=self.current_bb())
        return NONE

    def on_tick(self, now: float, humans: int = 0, robots: int = 0) -> Step:
        if self.state == SCHEDULED and now >= self.next_match_at:
            self.state = MATCHING
            self.deadline = now + self.cfg.match_timeout_sec
            return Step("match", "search", bb=self.current_bb(), info=self._note("match", bb=self.current_bb()))
        if self.state == MATCHING and now >= self.deadline:
            # no room arrived: ask again after a normal pause, without counting a rejection
            delay = self.rng.uniform(float(self.cfg.hop_delay[0]), float(self.cfg.hop_delay[1]))
            self.state = SCHEDULED
            self.next_match_at = now + delay
            self._note("match_timeout", delay=round(delay, 1))
            return NONE
        if self.state == PROBING:
            if humans + robots > 0:
                return self.on_seats_changed(humans, robots, now)
            if now >= self.deadline:
                return self._leave("empty_timeout", now, delayed=False, humans=0, robots=0,
                                   rejected=not self.dealt)
        if self.state == LEAVING and now >= self.deadline:
            self.deadline = now + self.cfg.leave_retry_sec
            return Step("leave", "retry", delayed=True, info=self._note("leave_retry"))
        return NONE

    def snapshot(self) -> dict:
        return {"state": self.state, "stake_bb": self.current_bb(), "table_bb": self.table_bb,
                "tries": self.tries, "ladder": list(self.cfg.ladder),
                "fail_rounds": {bb: n for bb, n in self.fail_rounds.items() if n},
                "retry_at": {bb: t for bb, t in self.retry_at.items() if t},
                "unavailable": sorted(self.unavailable), "bad_streak": self.bad_streak}
