"""Hands of 奥马哈 and 德扑-AOF that tasks count, played before the real game.

The daily tasks, the weekly tasks and the battle pass count hands of these two
games. Nothing in here plays poker. The bot takes a seat at the cheapest table,
pays the blinds as they come round and puts in nothing else (check when it is
free, otherwise fold; at all-in-or-fold always fold), and stands up when the
lists lack nothing more or the day's limit is reached.

Whether anything is lacking comes from the board every source of tasks reports
to (``rewards.Needs``); one hand counts for every list. A task list shows only
the current step of a chain, so the bot does not leave when that step is
reached: it plays on until the lists, read again after its last hand, lack
nothing more, or until ``MAX_HANDS`` of the game for the game day.

When: whenever the bot is in the lobby about to match the real game (at the
start, and at every later change of table), and once per game day it asks the
real table to be left for it, so that a bot running for days does each day's.

A seat at one of these tables is never the strategy engine's. While the bot
sits there its frames go to ``Seat`` and not to the bridge, and a seat found
left over (a crash, a lost connection) is given up before anything else.

The requests are the client's (LobbyByinDialog and OmahaBlinds for the match,
PKActionLayer and PKActionAllinLayer for the turn); the tables are level 1 of
tpl_table_omaha and tpl_table_poker_allin. None of it was seen live when this
was written, so every step that does not go as expected ends the errand and the
real game goes on.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time

from pf_intercept import config
from pf_intercept.headless.lobby.core.base import _int, game_day

log = logging.getLogger("pf_rewards")

OMAHA, AOF = 10020101, 10040101
# What these hands do for the tasks: the radar's capabilities (lobby.base.Worker.does).
DOES = {(101, OMAHA): "开赛前去奥马哈最低场弃牌凑手数", (101, AOF): "开赛前去 AOF 最低场弃牌凑手数"}
FOLD, CHECK = 1, 2              # POKER_ACTION
MAX_HANDS = 15                  # of each game per game day: the last step of the daily tasks
LIMITS = {(101, OMAHA): MAX_HANDS, (101, AOF): MAX_HANDS}      # the radar's view of MAX_HANDS
MAX_TRIES = 3                   # tables sat at for a game per game day, however they ended
BREAK_ASK_SEC = 60.0            # between two requests to the real table to be left for this
# QuickStartREQ per game. Omaha waits for the big blind instead of posting one to get in.
TABLES = {
    OMAHA: {"boot": 1000, "byin_chips": 20000, "wait_blind": True},
    AOF: {"boot": 2000, "byin_chips": 20000},
}
# What the server sends about a table. At a task table none of it reaches the bridge.
FRAMES = frozenset({
    "pb.EnterRoomRSP", "pb.SitDownRSP", "pb.SitDownBRC", "pb.OtherLeaveRoomBRC", "pb.OtherEnterRoomBRC",
    "pb.QuickStartRSP", "pb.DealerInfoRSP", "pb.HandCardRSP", "pb.RoundStartBRC", "pb.ActionNotifyBRC",
    "pb.ActionBRC", "pb.RoundOverBRC", "pb.WinnerRSP", "pb.ShowHandRSP", "pb.NoticeRebyRSP", "pb.RebyBRC",
    "pb.SetRebyRSP", "pb.DelayLeaveRoomRSP", "pb.LeaveRoomRSP",
})
REPORT_TIMEOUT_SEC = 240.0      # for the task lists to be read once after the start
ENTER_TIMEOUT_SEC = 20.0        # for the table after the match request
IDLE_TIMEOUT_SEC = 180.0        # without any hand finishing at the table: nobody to play with
GAME_TIMEOUT_SEC = 1500.0       # at one table in all
LEAVE_TIMEOUT_SEC = 45.0        # a seat in a running hand is given up when the hand ends
COMEBACK_SEC = 3                # after a hand the lists are read again, before the next one is dealt if possible
POLL_SEC = 0.5                  # how often the seat looks whether the lists still lack anything


def is_task_table(msg) -> bool:
    """An EnterRoomRSP for a table of one of these games."""
    return _int(msg.get("game_type")) in TABLES


class Seat:
    """One seat at a task table: answers every turn without putting a chip in, counts the hands."""

    def __init__(self, session, game):
        self.session = session
        self.game = game
        self.frames = asyncio.Queue()
        self.room = 0
        self.seat = None
        self.dealt = False
        self.hands = 0
        self.net = 0
        self.gone = False       # the server confirmed the seat is given up

    def feed(self, type_name, msg):
        self.frames.put_nowait((type_name, msg))

    async def frame(self, deadline):
        """The next frame of the table, or None at ``deadline``. A lost connection is an error:
        only a new one can tell where the seat is."""
        while True:
            if not self.session.connected:
                raise ConnectionError("connection lost at a task table")
            left = deadline - time.monotonic()
            if left <= 0:
                return None
            try:
                return await asyncio.wait_for(self.frames.get(), timeout=min(left, 1.0))
            except asyncio.TimeoutError:
                continue

    async def react(self, type_name, msg):
        """What every frame means here, whatever the seat is waiting for."""
        if type_name == "pb.EnterRoomRSP" and _int(msg.get("code")) == 0:
            self.room = _int(msg.get("roomid"))
        elif type_name == "pb.SitDownRSP":
            if _int(msg.get("code")) == 0:
                self.seat = _int(msg.get("seatid"))     # the wire leaves zero out: no field is seat 0
        elif type_name == "pb.HandCardRSP":
            self.dealt = True
        elif type_name == "pb.ActionNotifyBRC":
            if self.seat is not None and _int(msg.get("seatid")) == self.seat:
                free = self.game != AOF and _int(msg.get("call_need_chips")) == 0
                await self.session.send("pb.ActionREQ", {"action_type": CHECK if free else FOLD, "chips": 0},
                                        room_id=self.room)
        elif type_name == "pb.WinnerRSP":
            if self.dealt:
                self.dealt = False
                self.hands += 1
                me = str(self.session.login.uid)
                self.net += sum(_int(row.get("chips")) for row in msg.get("profit") or []
                                if isinstance(row, dict) and str(row.get("uid", "")) == me)
        elif type_name == "pb.LeaveRoomRSP" and _int(msg.get("code")) in (0, 2, 3):
            self.gone = True

    async def play(self, hands, keep_on=lambda: True, on_hand=lambda: None):
        """Match, sit through at most ``hands`` hands while ``keep_on()``, stand up.
        ``on_hand`` is called after every hand the bot was dealt. Returns why it ended."""
        fields = {"game_type": self.game, "lobby_coin": int(config.PROFIT_LOCK_FALLBACK_LOBBY_COIN),
                  "ip": self.session.login.login_ip or "", **TABLES[self.game]}
        if not await self.session.send("pb.QuickStartREQ", fields, room_id=0):
            return "the match request was not sent"
        try:
            return await self.sit_through(hands, keep_on, on_hand)
        finally:
            if self.room and not self.gone and self.session.connected:
                await self.leave()

    async def sit_through(self, hands, keep_on, on_hand):
        started = time.monotonic()
        deadline = started + ENTER_TIMEOUT_SEC
        while not self.room:
            got = await self.frame(deadline)
            if got is None:
                return "no table"
            type_name, msg = got
            if type_name in ("pb.QuickStartRSP", "pb.EnterRoomRSP") and _int(msg.get("code")) != 0:
                return f"refused code={_int(msg.get('code'))}"
            await self.react(type_name, msg)
            if type_name == "pb.EnterRoomRSP" and _int(msg.get("game_type")) != self.game:
                return "the table is of another game"
        # The table is alive while hands finish at it, also those the bot is not in yet: at Omaha
        # it waits for the big blind to come round before it is dealt in.
        last_hand = time.monotonic()
        while self.hands < hands:
            if not keep_on():
                return "nothing more is lacking"
            now = time.monotonic()
            if now - last_hand >= IDLE_TIMEOUT_SEC:
                return "no hands"
            if now - started >= GAME_TIMEOUT_SEC:
                return "took too long"
            got = await self.frame(now + POLL_SEC)
            if got is None:
                continue
            before = self.hands
            await self.react(*got)
            if self.gone:
                return "the server gave up the seat"
            if got[0] == "pb.WinnerRSP":
                last_hand = time.monotonic()
            if self.hands > before:
                on_hand()
        return "done"

    async def leave(self):
        """Stand up and wait for the server to confirm it, still answering turns meanwhile."""
        if not await self.session.send("pb.LeaveRoomREQ", {"seat_reserve": False}, room_id=self.room):
            raise ConnectionError("leaving a task table: request not sent")
        deadline = time.monotonic() + LEAVE_TIMEOUT_SEC
        while not self.gone:
            got = await self.frame(deadline)
            if got is None:
                # Where the seat is cannot be told on this connection: a new one asks the server.
                raise ConnectionError("leaving a task table was not confirmed")
            await self.react(*got)


class TaskHands:
    """The errand: for each game, the hands the task lists lack, before the real game."""

    def __init__(self, session):
        self.session = session
        self.started = False        # the task lists have been waited for once after this start
        self.lock = asyncio.Lock()
        self.day = None             # game day of ``counts`` and ``ran``
        self.counts = {}            # game -> [hands dealt, tables sat at] this game day
        self.ran = False            # the errand was looked at this game day
        self.asked = 0.0            # when the real table was last asked to be left

    def today(self, svc):
        """This game day's counts, from the journal when the day is new."""
        day = game_day(svc.now())
        if self.day != day:
            self.day, self.ran = day, False
            self.counts = {game: [0, 0] for game in TABLES}
            path = svc._journal_path
            for line in path.read_text(encoding="utf-8").splitlines() if path.exists() else ():
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                if (row.get("uid") == svc.uid and row.get("event") == "taskhands"
                        and row.get("day") == day and row.get("game") in self.counts):
                    self.counts[row["game"]][0] += _int(row.get("hands"))
                    self.counts[row["game"]][1] += 1
        return day

    def due(self, svc):
        """[(game, hands that may still be played today, what each source lacks)]."""
        self.today(svc)
        out = []
        for game in TABLES:
            lacking = svc.needs.lacking(game)
            hands, tries = self.counts[game]
            if lacking and hands < MAX_HANDS and tries < MAX_TRIES:
                out.append((game, MAX_HANDS - hands, lacking))
        return out

    def wants_break(self):
        """Seated at the real game with a new day's hands lacking: time to ask for a leave.
        Once the errand has been looked at today, later needs wait for the next change of table."""
        session, svc = self.session, self.session._rewards
        now = time.monotonic()
        if (svc is None or session._stopping or not session.connected or session._seat is not None
                or not session.current_room_id() or now - self.asked < BREAK_ASK_SEC):
            return False
        self.asked = now
        return bool(self.due(svc)) and not self.ran

    async def run(self):
        """From the lobby, before the real game is matched."""
        session, svc = self.session, self.session._rewards
        if svc is None or session._stopping:
            return
        async with self.lock:
            if not self.started:
                self.started = True
                # The reward worker reads the task lists; it starts once the bankroll baseline is taken.
                await session.lobby_baseline()
                try:
                    await asyncio.wait_for(svc.first_pass.wait(), timeout=REPORT_TIMEOUT_SEC)
                except asyncio.TimeoutError:
                    svc._record("taskhands_skipped", reason="the task lists were not read in time")
                    return
            for game, hands, lacking in self.due(svc):
                if session._stopping or not session.connected:
                    return
                await self.play(svc, game, hands, lacking)
            self.today(svc)
            self.ran = True

    async def play(self, svc, game, hands, lacking):
        session = self.session
        day = self.today(svc)
        wallet = session.bankroll_dashboard().get("wallet_chips")
        if wallet is None or int(wallet) < TABLES[game]["byin_chips"]:
            svc._record("taskhands_skipped", day=day, game=game, reason="wallet below the buy-in")
            return
        seat = Seat(session, game)
        session._seat = seat
        svc._record("taskhands_attempt", day=day, game=game, hands=hands, wanted=lacking, required=True)
        last = [svc.needs.order]    # the board as it stood at the last hand dealt, or at sitting down

        def on_hand():
            # It counted for every list. They read again and say what is still lacking.
            last[0] = svc.needs.order
            svc.needs.played(game, 1, COMEBACK_SEC)

        def keep_on():
            # None: the lists have not been read since the last hand. {}: read, nothing lacking.
            return svc.needs.settled(game, last[0]) != {}

        reason = "interrupted"
        try:
            reason = await seat.play(hands, keep_on, on_hand)
        except ConnectionError as exc:
            reason = str(exc)
            raise
        except Exception:
            # Anything unexpected ends the errand, never the bot.
            log.exception("[TASKHANDS] game=%s failed", game)
            reason = "error"
            if seat.room and not seat.gone:
                # Where the seat is cannot be told here: a new connection asks the server.
                raise ConnectionError("a task table in an unknown state") from None
        finally:
            self.counts[game][0] += seat.hands
            self.counts[game][1] += 1
            svc._record("taskhands", day=day, game=game, hands=seat.hands, net=seat.net, stopped=reason)
            if seat.gone or not seat.room:
                session._seat = None        # only once the seat is known to be given up
            if seat.net:
                # Blinds paid for tasks are not poker results: the side-game ledger takes them.
                await session.on_sidegame_result(seat.net)
