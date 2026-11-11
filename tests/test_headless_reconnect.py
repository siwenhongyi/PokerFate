"""Transport recovery with protocol snapshots; no real game/HTTP calls."""

import asyncio
import os
from types import SimpleNamespace

import pytest

from pf_intercept.bot import BotBridge
from pf_intercept.headless import reconnect as rc, session as hs
from pf_entertainment.live_table import LiveTableObserver
from tests.test_headless import _FakeWS, _login_result, _RecordingBridge
from tests.test_headless_rewards import eventually


@pytest.fixture(autouse=True)
def isolate(monkeypatch):
    monkeypatch.setattr(os, "environ", dict(os.environ))
    monkeypatch.setattr(hs, "HEARTBEAT_INTERVAL_SEC", .03)
    monkeypatch.setattr(hs, "STATE_TIMEOUT_SEC", .1)
    monkeypatch.setattr(hs, "ROOM_SYNC_TIMEOUT_SEC", .2)
    monkeypatch.setattr(rc, "RETRY_DELAYS", (.01, .02))


class GameWS(_FakeWS):
    def __init__(self, *, room=77, login_code=0, location=True):
        super().__init__()
        self.room = room
        self.login_code = login_code
        self.location = location

    async def send(self, data):
        await super().send(data)
        name, _, fields = self.sent[-1]
        if name == "pb.UserLoginREQ":
            self.push("pb.UserLoginRSP", {"code": self.login_code})
            if not self.login_code and self.location:
                self.push("pb.UserLocationRSP", {"roomid": self.room, "game_type": hs.LOBBY_HOLDEM_GAME_TYPE})
        elif name == "pb.SelfUserInfoREQ":
            self.push("pb.SelfUserInfoRSP", {"brief": {"uid": 42}})
        elif name == "pb.UserValueREQ":
            self.push("pb.UserValueRSP", {"type": 10100001, "value": 10000})
        elif name in {"pb.EnterRoomREQ", "pb.QuickStartREQ"}:
            self.room = fields.get("roomid", 88)
            self.push("pb.EnterRoomRSP", {
                "roomid": self.room, "game_type": hs.LOBBY_HOLDEM_GAME_TYPE,
                "room_info": {"bb": 10, "sb": 5},
                "table_status": {"seat": [{"seatid": 1, "player": {"uid": 42, "name": "Hero"},
                                               "hand_chips": 950}]},
            }, room_id=self.room)


def real_bridge(monkeypatch):
    bridge = BotBridge(max_auto_rebuy=5)
    bridge._auto_rebuy_done = 2
    bridge._my_uid = "42"
    bridge._my_seat = 1
    bridge._table_room_id = 77
    bridge._my_chips = 950
    bridge._seat_chips = {1: 950}
    bridge._bankroll_base_total_chips = 11000
    monkeypatch.setattr(bridge, "_trigger_gamedata_fetch", lambda *args: None)
    monkeypatch.setattr(bridge, "_ensure_api", lambda: False)
    monkeypatch.setattr(bridge, "_runtime_calibration_should_pause_play", lambda: None)
    monkeypatch.setattr(bridge, "_notify", lambda *args, **kw: None)
    return bridge


def socket_sequence(monkeypatch, outcomes):
    calls = []
    async def connect(uri, **kwargs):
        calls.append(uri)
        outcome = outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome
    monkeypatch.setattr(hs.websockets, "connect", connect)
    return calls


@pytest.mark.parametrize("cause", ["heartbeat", "eof", "send_error"])
def test_connection_loss_retries_and_restores_original_table_without_new_buyin(monkeypatch, cause):
    async def run():
        first, second = GameWS(), GameWS()
        calls = socket_sequence(monkeypatch, [first, OSError("network jitter"), second])
        login = _login_result()
        login.servers.append(hs.ServerEntry("wss://10.0.0.2:9013", ""))
        bridge = real_bridge(monkeypatch)
        observer = LiveTableObserver(my_uid=42)
        states = []
        original_status = observer.set_connection_status
        def status(value):
            states.append(value)
            original_status(value)
        monkeypatch.setattr(observer, "set_connection_status", status)
        sess = hs.HeadlessSession(login, bridge=bridge, auto_rewards=False, reconnect_enabled=True,
                                  on_frame=observer.observe)
        await sess.connect()
        sess._reward_chips = 123
        stop = asyncio.Event()
        runner = asyncio.create_task(rc.maintain_game(sess, stop, big_blind=10, buyin_bb=100, observer=observer))
        late = None
        try:
            await eventually(lambda: states.count("connected") == 1)
            late = asyncio.create_task(sess._inject(("pb.RebyREQ", {"is_reby": True, "chips": 1000}, .2), 77,
                                                    generation=sess._generation))
            if cause == "heartbeat":
                first.answer_heartbeats = False
            elif cause == "eof":
                first._incoming.put_nowait(None)
            else:
                async def fail_send(data):
                    raise OSError("socket reset")
                monkeypatch.setattr(first, "send", fail_send)
                await sess.send("pb.HeartBeatREQ", {}, room_id=0)
            await eventually(lambda: states.count("connected") == 2)
            await late
            assert "reconnecting" in states and "restoring" in states
            assert calls == ["wss://10.0.0.1:9013", "wss://10.0.0.1:9013", "wss://10.0.0.2:9013"]
            assert sess.bridge is bridge and not bridge._shutdown_requested
            assert (bridge._auto_rebuy_done, bridge._max_auto_rebuy) == (2, 5)
            assert bridge._bankroll_base_total_chips == 11000
            assert sess._reward_chips == 123
            assert observer.snapshot()["room_id"] == 77
            assert observer.snapshot()["my_seat"] == 1
            for ws in (first, second):
                entries = [x for x in ws.sent if x[0] == "pb.EnterRoomREQ"]
                assert len(entries) == 1 and entries[0][1] == 0 and entries[0][2] == {"roomid": 77}
                assert "pb.QuickStartREQ" not in ws.sent_types()
                assert "pb.RebyREQ" not in ws.sent_types()
            assert sess.stats.heartbeats_missed == (1 if cause == "heartbeat" else 0)
        finally:
            stop.set()
            await runner
            await sess.close("test end")
    asyncio.run(run())


def test_negative_login_rejection_is_also_terminal(monkeypatch):
    async def run():
        socket_sequence(monkeypatch, [GameWS(login_code=-2)])
        sess = hs.HeadlessSession(_login_result(), bridge=_RecordingBridge(), auto_rewards=False, reconnect_enabled=True)
        try:
            with pytest.raises(hs.LoginRejected):
                await sess.connect()
        finally:
            await sess.close()
    asyncio.run(run())


@pytest.mark.parametrize("busted", [False, True])
def test_authoritative_lobby_rematches_only_when_allowed(monkeypatch, busted):
    async def run():
        ws = GameWS(room=0)
        socket_sequence(monkeypatch, [ws])
        bridge = real_bridge(monkeypatch)
        if busted:
            bridge._my_chips = bridge._seat_chips[1] = 0
        bridge.prepare_transport_reconnect()
        # Repeated failed attempts must retain the same decision.
        bridge.prepare_transport_reconnect()
        sess = hs.HeadlessSession(_login_result(), bridge=bridge, auto_rewards=False, reconnect_enabled=True)
        try:
            await sess.connect()
            await sess.restore_or_start(big_blind=10, buyin_bb=80)
            matches = [x for x in ws.sent if x[0] == "pb.QuickStartREQ"]
            assert len(matches) == (0 if busted else 1)
            if matches:
                assert matches[0][1] == 0 and matches[0][2]["byin_chips"] == "800"
            assert (bridge._auto_rebuy_done, bridge._max_auto_rebuy) == (2, 5)
            assert bridge._bankroll_base_total_chips == 11000
        finally:
            await sess.close()
    asyncio.run(run())


def test_missing_location_never_guesses_a_new_buyin(monkeypatch):
    async def run():
        ws = GameWS(location=False)
        socket_sequence(monkeypatch, [ws])
        sess = hs.HeadlessSession(_login_result(), bridge=_RecordingBridge(), auto_rewards=False, reconnect_enabled=True)
        try:
            await sess.connect()
            with pytest.raises(hs.SessionClosed, match="UserLocationRSP"):
                await sess.restore_or_start(big_blind=10)
            assert "pb.QuickStartREQ" not in ws.sent_types()
            assert "pb.EnterRoomREQ" not in ws.sent_types()
        finally:
            await sess.close()
    asyncio.run(run())


@pytest.mark.parametrize("failure", ["logout", "login_rejected"])
def test_explicit_server_rejection_does_not_loop(monkeypatch, failure):
    async def run():
        ws = GameWS()
        outcomes = [ws] + ([GameWS(login_code=1001)] if failure == "login_rejected" else [])
        calls = socket_sequence(monkeypatch, outcomes)
        sess = hs.HeadlessSession(_login_result(), bridge=_RecordingBridge(), auto_rewards=False, reconnect_enabled=True)
        await sess.connect()
        stop = asyncio.Event()
        runner = asyncio.create_task(rc.maintain_game(sess, stop, big_blind=10, buyin_bb=100))
        try:
            await eventually(lambda: "pb.EnterRoomREQ" in ws.sent_types())
            if failure == "logout":
                ws.push("pb.UserLogoutRSP", {"code": 104})
            else:
                ws.answer_heartbeats = False
            assert await asyncio.wait_for(runner, 2) is False
            assert sess.fatal_error
            assert len(calls) == (1 if failure == "logout" else 2)
        finally:
            stop.set()
            await sess.close()
    asyncio.run(run())


@pytest.mark.parametrize("phase", ["backoff", "connect", "restore"])
def test_stop_interrupts_retry_work(monkeypatch, phase):
    async def run():
        stop, entered = asyncio.Event(), asyncio.Event()
        class FakeSession:
            connected = True
            fatal_error = None
            disconnect_reason = "jitter"
            login = _login_result()
            attempts = 0
            restores = 0
            async def restore_or_start(self, **kwargs):
                self.restores += 1
                if phase == "restore" and self.restores > 1:
                    entered.set()
                    await asyncio.Event().wait()
            async def wait_closed(self):
                self.connected = False
                if phase == "backoff":
                    entered.set()
            async def connect(self, **kwargs):
                self.attempts += 1
                if phase == "connect":
                    entered.set()
                    await asyncio.Event().wait()
                self.connected = True
        if phase == "backoff":
            monkeypatch.setattr(rc, "RETRY_DELAYS", (60,))
        sess = FakeSession()
        task = asyncio.create_task(rc.maintain_game(sess, stop, big_blind=10, buyin_bb=100))
        await asyncio.wait_for(entered.wait(), 1)
        stop.set()
        assert await asyncio.wait_for(task, .2) is True
        assert sess.attempts == (0 if phase == "backoff" else 1)
    asyncio.run(run())


def test_reward_service_survives_transport_and_final_close_drains_it(monkeypatch):
    async def run():
        first, second = GameWS(), GameWS()
        socket_sequence(monkeypatch, [first, second])
        sess = hs.HeadlessSession(_login_result(), bridge=_RecordingBridge(), auto_rewards=False, reconnect_enabled=True)
        await sess.connect()
        closes = []
        async def close_rewards():
            closes.append(True)
        rewards = SimpleNamespace(confirmed_chips=321, uncertain=True, claims=4,
                                  set_http_base=lambda value: None, start=lambda: None,
                                  observe_server_time=lambda value: None, close=close_rewards)
        sess._rewards = rewards
        await sess.disconnect("test jitter")
        assert closes == []
        await sess.connect()
        assert sess._rewards is rewards
        assert (rewards.confirmed_chips, rewards.uncertain, rewards.claims) == (321, True, 4)
        await sess.close()
        assert closes == [True]
    asyncio.run(run())
