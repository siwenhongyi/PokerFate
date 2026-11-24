"""Task hands of 奥马哈 / 德扑-AOF before the real game: a scripted server, no real requests."""
from __future__ import annotations

import asyncio
import json
import os
import re

import pytest

from pf_intercept.headless.lobby.core import base as lb
from pf_intercept.headless.lobby.routine import fund as fd
from pf_intercept.headless.lobby.core import needs as nd
from pf_intercept.headless.lobby.core import service as sv
from pf_intercept.headless.lobby.routine import tasks as tk
from pf_intercept.headless import lobby
from pf_intercept.headless import session as hs
from pf_intercept.headless.lobby.doers import taskhands as th
from pf_intercept.headless.lobby.doers.taskhands import AOF, OMAHA
from tests.test_dispatch import TPL, journal, lua_table
from tests.test_headless import _FakeWS, _login_result, _RecordingBridge

HOLDEM = hs.LOBBY_HOLDEM_GAME_TYPE
ROOMS = {OMAHA: 501, AOF: 502, HOLDEM: 88}


@pytest.fixture(autouse=True)
def isolate(monkeypatch):
    monkeypatch.setattr(os, "environ", dict(os.environ))
    monkeypatch.setattr(hs, "HEARTBEAT_INTERVAL_SEC", .03)
    # Waits that only end when something goes wrong are generous: a loaded machine must not
    # look like a silent server.
    monkeypatch.setattr(hs, "STATE_TIMEOUT_SEC", 5.0)
    monkeypatch.setattr(hs, "ROOM_SYNC_TIMEOUT_SEC", 5.0)
    monkeypatch.setattr(th, "REPORT_TIMEOUT_SEC", 5.0)
    monkeypatch.setattr(th, "ENTER_TIMEOUT_SEC", 2.0)
    monkeypatch.setattr(th, "IDLE_TIMEOUT_SEC", 1.0)
    monkeypatch.setattr(th, "LEAVE_TIMEOUT_SEC", 2.0)
    monkeypatch.setattr(th, "COMEBACK_SEC", .01)       # the lists are read again right after a hand
    monkeypatch.setattr(th, "POLL_SEC", .01)
    monkeypatch.setattr(th, "BREAK_ASK_SEC", .05)


class TableWS(_FakeWS):
    """The game server as far as this needs it: a lobby, task tables that deal, a hold'em table."""

    # The base double answers every heartbeat with server time 1, which holds the reward
    # worker's clock still. Here the clock is set once, at login, and runs from there.
    answer_heartbeats = False

    def __init__(self, *, location=0, location_game=HOLDEM, refuse=(), silent=(), deaf_to_leave=False):
        super().__init__()
        self.location, self.location_game = location, location_game
        self.refuse, self.silent, self.deaf_to_leave = set(refuse), set(silent), deaf_to_leave
        self.game = 0           # the task table the bot sits at
        self.hand = 0
        self.tables = 0         # how many tables have been sat at
        self.leaving = False
        self.dealt = {OMAHA: 0, AOF: 0}     # hands the bot was dealt and that ended: what the tasks count

    def deal(self):
        """Hand 1 was under way when the bot sat down: no cards for it. From then on a hand
        each; every other one can be checked."""
        if not self.game or self.leaving:
            return
        self.hand += 1
        room = ROOMS[self.game]
        if self.hand > 1:
            self.push("pb.HandCardRSP", {}, room_id=room)       # four cards at Omaha; none of them matter
            self.push("pb.ActionNotifyBRC", {"seatid": 0, "call_need_chips": 0 if self.hand % 2 == 0 else 500},
                      room_id=room)
        else:
            self.finish()

    def finish(self):
        room = ROOMS[self.game]
        if self.hand > 1:
            self.dealt[self.game] += 1
        self.push("pb.WinnerRSP", {"profit": [{"uid": 42, "chips": -100}, {"uid": 7, "chips": 100}]}, room_id=room)
        table = self.tables
        # The next hand a while later, at this table only: long enough for the task lists to be
        # read again in between, as they are at a real table.
        asyncio.get_running_loop().call_later(.3, lambda: self.deal() if table == self.tables else None)

    async def send(self, data):
        await super().send(data)
        name, room, fields = self.sent[-1]
        if name == "pb.HeartBeatREQ":
            self.push("pb.HeartBeatRSP", {})
        elif name == "pb.UserLoginREQ":
            # A server clock outside every activity's dates: only the task lists are read.
            self.push("pb.UserLoginRSP", {"code": 0, "server_timestamp": 1})
            self.push("pb.UserLocationRSP", {"roomid": self.location})
        elif name == "pb.UserValueREQ":
            self.push("pb.UserValueRSP", {"type": 10100001, "value": 5000000})
        elif name == "pb.QuickStartREQ":
            game = int(fields["game_type"])
            if game in self.refuse:
                self.push("pb.QuickStartRSP", {"code": 5})
            elif game == HOLDEM:
                self.push("pb.EnterRoomRSP", {"roomid": 88, "game_type": HOLDEM}, room_id=88)
            else:
                self.game, self.hand, self.tables = game, 0, self.tables + 1
                self.push("pb.EnterRoomRSP", {"roomid": ROOMS[game], "game_type": game}, room_id=ROOMS[game])
                self.push("pb.SitDownRSP", {"chips": 20000}, room_id=ROOMS[game])     # seat 0: no seatid on the wire
                self.push("pb.UserValueRSP", {"type": 10100001, "value": 4980000})  # the wallet without the buy-in
                if game not in self.silent:
                    self.deal()
        elif name == "pb.EnterRoomREQ":
            self.game = self.location_game if self.location_game != HOLDEM else 0
            self.push("pb.EnterRoomRSP", {"roomid": self.location, "game_type": self.location_game},
                      room_id=self.location)
        elif name == "pb.ActionREQ" and self.game:
            self.finish()
        elif name == "pb.LeaveRoomREQ" and self.deaf_to_leave:
            self.leaving = True
        elif name == "pb.LeaveRoomREQ":
            self.game = 0
            self.push("pb.LeaveRoomRSP", {}, room_id=room)
            self.push("pb.UserValueRSP", {"type": 10100001, "value": 5000000})


class Bridge(_RecordingBridge):
    def __init__(self):
        super().__init__()
        self.ledger = []

    def bankroll_dashboard(self):
        return {"base_total_chips": 5000000, "wallet_chips": 5000000}

    def record_sidegame_result(self, net):
        self.ledger.append(net)


def goal(game, need, done):
    return {"id": need, "task_id": 1, "task_type": 101, "status": 1, "value": [game, need], "current_value": done}


def chain(ws, game, steps, done=0):
    """A task chain as a list shows it: the current step only, counting what the server dealt."""
    done += ws.dealt.get(game, 0)
    return [goal(game, step, done) for step in steps if step > done][:1]


async def start(monkeypatch, tmp_path, ws, *, daily=(), weekly=(), down=False, **flags):
    """``daily`` / ``weekly``: (game, steps, hands already counted) per chain."""
    seen = []

    def post(url, payload, **kwargs):
        endpoint = url.removeprefix("https://game.example")
        if endpoint == "/task/list":
            if down:
                return None
            return {"code": 0, "challenge_list": [],
                    "daily_list": [row for spec in daily for row in chain(ws, *spec)],
                    "weekly_list": [row for spec in weekly for row in chain(ws, *spec)]}
        return {"code": 0, "status": 0}

    def service(**kwargs):
        kwargs["http_base"] = "https://game.example"
        return sv.RewardService(**kwargs, post=post, journal_path=tmp_path / "rewards.jsonl")

    async def connect(uri, **kwargs):
        return ws

    monkeypatch.setattr(hs.websockets, "connect", connect)
    monkeypatch.setattr(hs, "RewardService", service)
    bridge = Bridge()
    flags.setdefault("off", {flag for flag, _ in lobby.switches()})     # the task lists, fund and sign-in only
    sess = hs.HeadlessSession(_login_result(), bridge=bridge, chnl=5, client_version="1.7.0",
                              reconnect_enabled=True, on_frame=lambda name, msg: seen.append(name), **flags)
    await sess.connect()
    return sess, bridge, seen


def sent(ws, name):
    return [(room, fields) for kind, room, fields in ws.sent if kind == name]


def test_the_tables_and_actions_are_the_clients():
    omaha = next(r for r in lua_table("table_omaha") if r["id"] == "1")
    assert (int(omaha["gameType"]), int(omaha["bb"]), int(omaha["min_byin"])) == (
        OMAHA, th.TABLES[OMAHA]["boot"], th.TABLES[OMAHA]["byin_chips"])
    allin = next(r for r in lua_table("table_poker_allin") if r["id"] == "1")
    assert (int(allin["gameType"]), int(allin["bb"]), int(allin["byin"])) == (
        AOF, th.TABLES[AOF]["boot"], th.TABLES[AOF]["byin_chips"])
    enum = (TPL.parent / "app" / "EnumConfig.lua").read_text(encoding="utf-8")
    assert re.search(rf"POKER_ACTION = \{{[^}}]*\bFOLD = {th.FOLD},\s*CHECK = {th.CHECK},", enum)
    assert f"LOBBY_OMAHA_GAME    = {OMAHA}," in enum and f"LOBBY_HOLDEM_ALLIN = {AOF}," in enum
    # Every frame the strategy engine is given about a table is kept from it at a task table.
    from pf_intercept import config
    assert th.FRAMES == set(config.WATCH_S2C) - {"pb.UserLoginRSP", "pb.SelfUserInfoRSP", "pb.UserValueRSP", "pb.UserLocationRSP"}


def test_the_task_hands_come_first_and_the_real_game_after(monkeypatch, tmp_path):
    async def run():
        ws = TableWS()
        sess, bridge, seen = await start(
            monkeypatch, tmp_path, ws,
            # Omaha: the daily chain is at "3 hands" with 1 counted, then "6"; the weekly one lacks 3.
            # Six hands in all finish both; the list never showed more than a gap of 3.
            daily=[(OMAHA, [1, 3, 6], 1), (AOF, [1, 3], 0)],
            weekly=[(OMAHA, [10], 7), (HOLDEM, [40], 12)])
        try:
            await sess.restore_or_start(big_blind=10, buyin_bb=100)
            matches = sent(ws, "pb.QuickStartREQ")
            # The client's requests, from the lobby, in this order: Omaha, all-in-or-fold, the real game.
            assert matches[0] == (0, {"game_type": OMAHA, "lobby_coin": 10100001, "ip": "9.9.9.9",
                                      "boot": "1000", "byin_chips": "20000", "wait_blind": True})
            assert matches[1] == (0, {"game_type": AOF, "lobby_coin": 10100001, "ip": "9.9.9.9",
                                      "boot": "2000", "byin_chips": "20000"})
            assert [fields["game_type"] for _, fields in matches] == [OMAHA, AOF, HOLDEM]
            # It did not stop at the step the list showed: it played on until the lists, read
            # again after each hand, lacked nothing. Five for Omaha (to 6), three for all-in-or-fold.
            omaha, allin = journal(tmp_path, "taskhands")
            assert (omaha["game"], omaha["hands"], omaha["net"]) == (OMAHA, 5, -500)
            assert (allin["game"], allin["hands"], allin["net"]) == (AOF, 3, -300)
            assert omaha["stopped"] == allin["stopped"] == "nothing more is lacking"
            assert journal(tmp_path, "taskhands_attempt")[0]["wanted"] == {"tasks": 3}
            # Never a chip beyond the blinds: check when it is free, fold otherwise; all-in-or-fold only folds.
            actions = sent(ws, "pb.ActionREQ")
            assert [(room, fields.get("action_type")) for room, fields in actions] == [
                (501, th.CHECK), (501, th.FOLD), (501, th.CHECK), (501, th.FOLD), (501, th.CHECK),
                (502, th.FOLD), (502, th.FOLD), (502, th.FOLD)]
            assert all(int(fields.get("chips") or 0) == 0 for _, fields in actions)
            assert sent(ws, "pb.LeaveRoomREQ") == [(501, {"seat_reserve": False}), (502, {"seat_reserve": False})]
            # The blinds are no poker result: the side-game ledger has them.
            assert bridge.ledger == [-500, -300]
            # Nothing of a task table reached the strategy engine or the live view.
            table_frames = {"pb.HandCardRSP", "pb.ActionNotifyBRC", "pb.WinnerRSP", "pb.SitDownRSP", "pb.LeaveRoomRSP"}
            assert not table_frames & {name for name, _ in bridge.handled} and not table_frames & set(seen)
            rooms = [msg.get("game_type") for name, msg in bridge.handled if name == "pb.EnterRoomRSP"]
            assert rooms == [HOLDEM] and sess._seat is None
            # Nor did the wallet as it stood while the buy-in sat at a task table.
            wallets = {str(msg.get("value")) for name, msg in bridge.handled if name == "pb.UserValueRSP"}
            assert wallets == {"5000000"}
            # Back in the lobby later with nothing lacking: straight to the real game.
            await sess.restore_or_start(big_blind=10, buyin_bb=100)
            assert [fields["game_type"] for _, fields in sent(ws, "pb.QuickStartREQ")] == [OMAHA, AOF, HOLDEM, HOLDEM]
        finally:
            await sess.close()
    asyncio.run(run())


def test_one_hand_counts_for_every_list(monkeypatch, tmp_path):
    """Two sources lack 2 and 3 hands of the same game: three hands, not five."""
    async def run():
        ws = TableWS()
        sess, bridge, _ = await start(monkeypatch, tmp_path, ws)
        try:
            await sess.lobby_baseline()
            await asyncio.wait_for(sess._rewards.first_pass.wait(), 3)
            needs = sess._rewards.needs

            async def two_sources():        # each reads its own list, which the server keeps
                while True:
                    needs.want("one_list", chain(ws, OMAHA, [3], 1))
                    needs.want("another_list", chain(ws, OMAHA, [20], 17))
                    await asyncio.sleep(.01)
            reading = asyncio.create_task(two_sources())
            await asyncio.sleep(.03)
            try:
                await sess._task_hands.run()
            finally:
                reading.cancel()
            done, = journal(tmp_path, "taskhands")
            assert (done["hands"], journal(tmp_path, "taskhands_attempt")[0]["wanted"]) == (
                3, {"one_list": 2, "another_list": 3})
        finally:
            await sess.close()
    asyncio.run(run())


def test_the_days_limit_counts_what_earlier_starts_played(monkeypatch, tmp_path):
    async def run():
        day = lb.game_day(1.0)
        (tmp_path / "rewards.jsonl").write_text(json.dumps(
            {"uid": 42, "event": "taskhands", "day": day, "game": OMAHA, "hands": 13}) + "\n" + json.dumps(
            {"uid": 42, "event": "taskhands", "day": day, "game": AOF, "hands": 15}) + "\n" + json.dumps(
            {"uid": 43, "event": "taskhands", "day": day, "game": OMAHA, "hands": 9}) + "\n")
        ws = TableWS()
        sess, _, _ = await start(monkeypatch, tmp_path, ws, weekly=[(OMAHA, [260], 150), (AOF, [260], 150)])
        try:
            await sess.restore_or_start(big_blind=10, buyin_bb=100)
            # Omaha: two more today, however much the weekly task lacks. All-in-or-fold: none.
            assert [fields["game_type"] for _, fields in sent(ws, "pb.QuickStartREQ")] == [OMAHA, HOLDEM]
            last = journal(tmp_path, "taskhands")[-1]
            assert (last["hands"], last["stopped"]) == (2, "done") and th.MAX_HANDS == 15
        finally:
            await sess.close()
    asyncio.run(run())


@pytest.mark.parametrize("flags, tasks", [
    ({}, []),                                               # nothing lacking
    ({}, [(HOLDEM, [15], 3), (30030101, [15], 3)]),          # other games are not this errand's
    ({"auto_taskhands": False}, [(OMAHA, [15], 3)]),         # switched off
    ({"auto_rewards": False}, [(OMAHA, [15], 3)]),           # nobody reads the task lists
])
def test_without_hands_to_play_the_real_game_starts_at_once(monkeypatch, tmp_path, flags, tasks):
    async def run():
        ws = TableWS()
        sess, bridge, _ = await start(monkeypatch, tmp_path, ws, daily=tasks, **flags)
        try:
            await sess.restore_or_start(big_blind=10, buyin_bb=100)
            assert [fields["game_type"] for _, fields in sent(ws, "pb.QuickStartREQ")] == [HOLDEM]
            assert not journal(tmp_path, "taskhands", "taskhands_attempt") and bridge.ledger == []
        finally:
            await sess.close()
    asyncio.run(run())


def test_a_refused_or_empty_table_ends_the_errand_not_the_start(monkeypatch, tmp_path):
    async def run():
        ws = TableWS(refuse={OMAHA}, silent={AOF})
        sess, bridge, _ = await start(monkeypatch, tmp_path, ws, daily=[(OMAHA, [3], 0), (AOF, [3], 0)])
        try:
            await sess.restore_or_start(big_blind=10, buyin_bb=100)
            omaha, allin = journal(tmp_path, "taskhands")
            assert (omaha["hands"], omaha["stopped"]) == (0, "refused code=5")
            assert (allin["hands"], allin["stopped"]) == (0, "no hands")
            # The empty table was left; the real game started all the same.
            assert sent(ws, "pb.LeaveRoomREQ") == [(502, {"seat_reserve": False})] and sess._seat is None
            assert [fields["game_type"] for _, fields in sent(ws, "pb.QuickStartREQ")] == [OMAHA, AOF, HOLDEM]
            assert bridge.ledger == []
            # A game is tried at a few tables a day at most, however they ended.
            for _ in range(5):
                await sess._task_hands.run()
            tried = [row["game"] for row in journal(tmp_path, "taskhands")]
            assert tried.count(OMAHA) == tried.count(AOF) == th.MAX_TRIES == 3
        finally:
            await sess.close()
    asyncio.run(run())


def test_task_lists_that_are_not_read_in_time_do_not_hold_the_start(monkeypatch, tmp_path):
    async def run():
        monkeypatch.setattr(th, "REPORT_TIMEOUT_SEC", .2)
        monkeypatch.setattr(sv, "RETRY_SEC", 30)
        ws = TableWS()
        sess, _, _ = await start(monkeypatch, tmp_path, ws, daily=[(OMAHA, [3], 0)], down=True)
        try:
            # The first pass does finish (the task check failed), with nothing on the board.
            await sess.restore_or_start(big_blind=10, buyin_bb=100)
            assert [fields["game_type"] for _, fields in sent(ws, "pb.QuickStartREQ")] == [HOLDEM]
            assert not journal(tmp_path, "taskhands")
        finally:
            await sess.close()
    asyncio.run(run())


def test_a_seat_left_at_a_task_table_is_given_up_before_anything_else(monkeypatch, tmp_path):
    async def run():
        ws = TableWS(location=501, location_game=OMAHA)
        sess, bridge, seen = await start(monkeypatch, tmp_path, ws)
        try:
            await sess.restore_or_start(big_blind=10, buyin_bb=100)
            order = [name for name in ws.sent_types() if name in ("pb.EnterRoomREQ", "pb.LeaveRoomREQ", "pb.QuickStartREQ")]
            assert order == ["pb.EnterRoomREQ", "pb.LeaveRoomREQ", "pb.QuickStartREQ"]
            assert sent(ws, "pb.LeaveRoomREQ") == [(501, {"seat_reserve": False})]
            assert [fields["game_type"] for _, fields in sent(ws, "pb.QuickStartREQ")] == [HOLDEM]
            # The strategy engine never saw the Omaha table.
            assert [msg.get("game_type") for name, msg in bridge.handled if name == "pb.EnterRoomRSP"] == [HOLDEM]
            assert sess._seat is None
        finally:
            await sess.close()
    asyncio.run(run())


def test_a_restored_holdem_seat_is_the_bridges_as_before(monkeypatch, tmp_path):
    async def run():
        ws = TableWS(location=77, location_game=HOLDEM)
        sess, bridge, _ = await start(monkeypatch, tmp_path, ws, daily=[(OMAHA, [3], 0)])
        try:
            await sess.restore_or_start(big_blind=10, buyin_bb=100)
            assert "pb.QuickStartREQ" not in ws.sent_types() and "pb.LeaveRoomREQ" not in ws.sent_types()
            assert [msg.get("roomid") for name, msg in bridge.handled if name == "pb.EnterRoomRSP"] == [77]
        finally:
            await sess.close()
    asyncio.run(run())


def test_a_leave_that_is_not_confirmed_is_left_to_a_new_connection(monkeypatch, tmp_path):
    async def run():
        monkeypatch.setattr(th, "LEAVE_TIMEOUT_SEC", .3)
        ws = TableWS(deaf_to_leave=True)
        sess, bridge, _ = await start(monkeypatch, tmp_path, ws, daily=[(OMAHA, [1], 0)])
        try:
            with pytest.raises(ConnectionError, match="not confirmed"):
                await sess.restore_or_start(big_blind=10, buyin_bb=100)
            # No real match was asked for, and the table's frames stay away from the strategy engine.
            assert [fields["game_type"] for _, fields in sent(ws, "pb.QuickStartREQ")] == [OMAHA]
            assert sess._seat is not None
            ws.push("pb.ActionNotifyBRC", {"call_need_chips": 500}, room_id=501)
            await asyncio.sleep(.1)
            assert not any(name == "pb.ActionNotifyBRC" for name, _ in bridge.handled)
            assert journal(tmp_path, "taskhands")[0]["hands"] == 1 and bridge.ledger == [-100]
        finally:
            await sess.close()
    asyncio.run(run())


def test_a_new_game_day_asks_the_real_table_to_be_left_and_the_next_match_plays_first(monkeypatch, tmp_path):
    async def run():
        ws = TableWS()
        sess, bridge, _ = await start(monkeypatch, tmp_path, ws, daily=[(OMAHA, [1], 0)])
        asked = lambda: sum(name == "pf.Errand" for name, _ in bridge.handled)
        try:
            await sess.restore_or_start(big_blind=10, buyin_bb=100)       # today's hand, then the real table
            assert [fields["game_type"] for _, fields in sent(ws, "pb.QuickStartREQ")] == [OMAHA, HOLDEM]
            # More turns up the same day: it waits for the next change of table, the table is not left for it.
            needs = sess._rewards.needs
            needs.want("tasks", [goal(OMAHA, 3, 1)])
            await asyncio.sleep(.2)
            assert asked() == 0
            # A new game day: the daily tasks start over, the task list is read again by itself,
            # and the table is asked to be left when the hand ends.
            bridge.injects["pf.Errand"] = ("pb.DelayLeaveRoomREQ", {"flag": True}, 0.0)
            ws.dealt[OMAHA] = 0
            sess._rewards.observe_server_time(1 + 2 * 86400)
            for _ in range(200):
                if asked():
                    break
                await asyncio.sleep(.01)
            assert asked() >= 1 and "pb.DelayLeaveRoomREQ" in ws.sent_types()
            # The bridge leaves and matches again. That match request goes through the errand:
            # the Omaha hand first, the real table after; a repeat of the request meanwhile is dropped.
            ws.push("pb.LeaveRoomRSP", {}, room_id=88)
            await asyncio.sleep(.05)
            before = sess.stats.injects_dropped
            match = ("pb.QuickStartREQ", {"boot": 10, "game_type": HOLDEM, "lobby_coin": 10100001,
                                          "byin_chips": 1000, "ip": "9.9.9.9"}, 0.0)
            first = asyncio.create_task(sess._inject(match, 0))
            await asyncio.sleep(.05)
            await sess._inject(match, 0)
            assert sess.stats.injects_dropped == before + 1
            await first
            assert [fields["game_type"] for _, fields in sent(ws, "pb.QuickStartREQ")] == [OMAHA, HOLDEM, OMAHA, HOLDEM]
            assert [row["hands"] for row in journal(tmp_path, "taskhands")] == [1, 1]
            # Looked at for today: the table is not asked to be left again.
            count = asked()
            needs.want("tasks", [goal(OMAHA, 3, 1)])
            await asyncio.sleep(.2)
            assert asked() == count
        finally:
            await sess.close()
    asyncio.run(run())
