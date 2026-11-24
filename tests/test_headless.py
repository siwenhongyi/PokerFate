"""Headless client: resumed-session types + WSS session driver."""

from __future__ import annotations

import asyncio
import json
import os
import time

import pytest

from pf_intercept.headless import login as hl
from pf_intercept.headless import lobby
from pf_intercept.headless import session as hs
from pf_intercept.wire import codec
from pf_intercept.wire.framing import FrameBuffer, encode_frame


@pytest.fixture(autouse=True)
def _isolate_session_proxy_environment(monkeypatch):
    monkeypatch.setattr(os, "environ", dict(os.environ))


# ── WSS session ───────────────────────────────────────────────────────────

class _FakeWS:
    """Minimal async websocket double: records sends, replays scripted frames."""

    def __init__(self):
        self.sent: list[tuple[str, int, dict]] = []
        self._incoming: asyncio.Queue = asyncio.Queue()
        self.closed = False

    answer_heartbeats = True

    async def send(self, data: bytes):
        buf = FrameBuffer()
        for f in buf.feed(data):
            self.sent.append((f.type_name, f.room_id, codec.decode(f.type_name, f.pb_body) or {}))
            if f.type_name == "pb.HeartBeatREQ" and self.answer_heartbeats:
                self.push("pb.HeartBeatRSP", {"server_timestamp": 1})

    def push(self, type_name: str, fields: dict, room_id: int = 0):
        self._incoming.put_nowait(encode_frame(type_name, room_id, codec.encode(type_name, fields)))

    def __aiter__(self):
        return self

    async def __anext__(self):
        item = await self._incoming.get()
        if item is None:
            raise StopAsyncIteration
        return item

    async def close(self, code=1000, reason=""):
        self.closed = True
        self._incoming.put_nowait(None)

    def sent_types(self):
        return [t for t, _, _ in self.sent]


class _RecordingBridge:
    def __init__(self):
        self.handled: list[tuple[str, dict]] = []
        self.room_ids: list[int] = []
        self.injects: dict[str, list] = {}
        self.slow: dict[str, float] = {}   # seconds a handler blocks (runs in a worker thread)
        self.pre_action_notices: list[dict] = []

    def note_seen_room_id(self, rid):
        self.room_ids.append(rid)

    def note_pre_action(self, msg):
        self.pre_action_notices.append(msg)

    def room_id_for_c2s(self, frame_room_id):
        return frame_room_id or (self.room_ids[-1] if self.room_ids else 0)

    def handle(self, type_name, msg):
        time.sleep(self.slow.get(type_name, 0.0))
        self.handled.append((type_name, msg))
        return self.injects.get(type_name)

    def injection_guard_for(self, inject):
        return None

    def injection_guard_is_current(self, guard):
        return True

    def notify_inject_failed(self, type_name):
        pass

    def bankroll_dashboard(self):
        return {"frames_handled": len(self.handled)}


def _login_result():
    return hl.LoginResult(uid=42, rdkey="rk", authorization="a", login_ip="9.9.9.9",
                          servers=[hl.ServerEntry("wss://10.0.0.1:9013", "")])


def test_backlogged_action_is_discarded_after_server_system_fold(monkeypatch):
    async def run():
        bridge = _RecordingBridge()
        bridge.slow["pb.WinnerRSP"] = 0.15
        bridge.injects["pb.ActionNotifyBRC"] = ("pb.ActionREQ", {"action_type": 4, "chips": 60000}, 0.0)
        sess, ws = await _connect_with_fake(monkeypatch, bridge)
        try:
            ws.push("pb.WinnerRSP", {})
            ws.push("pb.DealerInfoRSP", {"gameid": "new"})
            ws.push("pb.ActionNotifyBRC", {"seatid": 3, "pre_action_result": 2})
            ws.push("pb.ActionBRC", {"seatid": 3, "action_type": 12})
            for _ in range(100):
                if any(t == "pb.ActionBRC" for t, _ in bridge.handled):
                    break
                await asyncio.sleep(0.01)
            assert not any(t == "pb.ActionNotifyBRC" for t, _ in bridge.handled)
            # the overtaken notice is not acted on, but its pre-action flag reaches the bridge
            assert bridge.pre_action_notices == [{"seatid": 3, "pre_action_result": 2}]
            assert "pb.ActionREQ" not in ws.sent_types()
            assert sess.stats.injects_dropped == 1
            assert sess.stats.heartbeats_sent > 0
        finally:
            await sess.close()
    asyncio.run(run())


def test_action_delay_cannot_outlive_server_turn(monkeypatch):
    async def run():
        bridge = _RecordingBridge()
        sess, ws = await _connect_with_fake(monkeypatch, bridge)
        try:
            task = asyncio.create_task(sess._inject(("pb.ActionREQ", {"action_type": 3}, 0.06), 777,
                                                   wire_turn=sess._wire_turn, received_at=time.monotonic()))
            ws.push("pb.ActionBRC", {"seatid": 0, "action_type": 12})
            await task
            assert "pb.ActionREQ" not in ws.sent_types()
            assert sess.stats.injects_dropped == 1
        finally:
            await sess.close()
    asyncio.run(run())


def test_graceful_stop_in_lobby_does_not_wait_or_rejoin(monkeypatch):
    from pf_intercept.headless.__main__ import _graceful_leave
    async def run():
        bridge = _RecordingBridge()
        bridge.room_ids = [777]  # old bridge snapshot can lag behind reception
        sess, ws = await _connect_with_fake(monkeypatch, bridge)
        try:
            sess._wire_room_id = 0
            await _graceful_leave(sess, asyncio.Event(), timeout=0.01)
            assert sess._stopping
            await sess._inject(("pb.QuickStartREQ", {"boot": 10000}, 0), 777)
            assert "pb.DelayLeaveRoomREQ" not in ws.sent_types()
            assert "pb.QuickStartREQ" not in ws.sent_types()
        finally:
            await sess.close()
    asyncio.run(run())


def test_quickstart_injection_always_uses_lobby_header(monkeypatch):
    async def run():
        sess, ws = await _connect_with_fake(monkeypatch, _RecordingBridge())
        try:
            await sess._inject(("pb.QuickStartREQ", {"boot": 10000}, 0), 777)
            assert ws.sent[-1][0:2] == ("pb.QuickStartREQ", 0)
        finally:
            await sess.close()
    asyncio.run(run())


async def _connect_with_fake(monkeypatch, bridge, login_code=0, *, auto_rewards=False):
    ws = _FakeWS()

    async def fake_connect(uri, **kwargs):
        assert uri == "wss://10.0.0.1:9013"
        return ws

    monkeypatch.setattr(hs.websockets, "connect", fake_connect)
    monkeypatch.setattr(hs, "HEARTBEAT_INTERVAL_SEC", 0.05)
    sess = hs.HeadlessSession(_login_result(), bridge=bridge, chnl=5, client_version="1.7.0", auto_rewards=auto_rewards,
                              off={flag for flag, _ in lobby.switches()})
    ws.push("pb.UserLoginRSP", {"code": login_code, "server_timestamp": 1})
    await sess.connect()
    return sess, ws


def test_session_login_handshake_and_bootstrap(monkeypatch):
    async def run():
        bridge = _RecordingBridge()
        sess, ws = await _connect_with_fake(monkeypatch, bridge)
        try:
            assert sess.logged_in
            login = ws.sent[0]
            assert login[0] == "pb.UserLoginREQ" and login[1] == 0
            assert login[2] == {"uid": "42", "key": "rk", "ver": "1.7.0", "chnl": 5}
            assert ws.sent_types()[1:3] == ["pb.SelfUserInfoREQ", "pb.UserValueREQ"]
            # UserLoginRSP is in WATCH_S2C, so the bridge saw it too.
            for _ in range(50):
                if bridge.handled:
                    break
                await asyncio.sleep(0.01)
            assert bridge.handled[0][0] == "pb.UserLoginRSP"
        finally:
            await sess.close()
    asyncio.run(run())


def test_session_rejects_bad_login_code(monkeypatch):
    async def run():
        with pytest.raises(hs.SessionClosed):
            await _connect_with_fake(monkeypatch, _RecordingBridge(), login_code=1001)
    asyncio.run(run())


def test_session_feeds_bridge_and_sends_injects_with_room_id(monkeypatch):
    async def run():
        bridge = _RecordingBridge()
        bridge.injects["pb.ActionNotifyBRC"] = ("pb.ActionREQ", {"action_type": 3, "chips": 50}, 0.0)
        sess, ws = await _connect_with_fake(monkeypatch, bridge)
        try:
            ws.push("pb.ActionNotifyBRC", {"seatid": 0, "call_need_chips": 50}, room_id=777)
            for _ in range(50):
                await asyncio.sleep(0.01)
                if any(t == "pb.ActionREQ" for t, _, _ in ws.sent):
                    break
            action = [s for s in ws.sent if s[0] == "pb.ActionREQ"]
            assert action and action[0][1] == 777
            assert action[0][2]["action_type"] == 3
            assert sess.stats.injects_sent == 1
            # non-watched frames (e.g. chat) never reach the bridge
            ws.push("pb.HeartBeatRSP", {"server_timestamp": 2})
            await asyncio.sleep(0.02)
            assert all(t != "pb.HeartBeatRSP" for t, _ in bridge.handled)
        finally:
            await sess.close()
    asyncio.run(run())


def test_session_heartbeat_and_quick_start(monkeypatch):
    async def run():
        bridge = _RecordingBridge()
        sess, ws = await _connect_with_fake(monkeypatch, bridge)
        try:
            await asyncio.sleep(0.2)
            assert ws.sent_types().count("pb.HeartBeatREQ") >= 2
            assert await sess.quick_start(big_blind=1000, buyin_bb=100)
            qs = [s for s in ws.sent if s[0] == "pb.QuickStartREQ"][0]
            assert qs[1] == 0
            assert qs[2]["boot"] == "1000" and qs[2]["byin_chips"] == "100000"
            assert qs[2]["game_type"] == hs.LOBBY_HOLDEM_GAME_TYPE and qs[2]["ip"] == "9.9.9.9"
        finally:
            await sess.close()
    asyncio.run(run())


def test_quick_start_sends_the_buy_in_the_loss_cap_allows_and_nothing_when_none_fits(monkeypatch):
    async def run():
        bridge = _RecordingBridge()
        sess, ws = await _connect_with_fake(monkeypatch, bridge)
        try:
            bridge.cap_match_buyin = lambda fields: {**fields, "byin_chips": 50000}
            assert await sess.quick_start(big_blind=1000, buyin_bb=100)
            assert [s[2]["byin_chips"] for s in ws.sent if s[0] == "pb.QuickStartREQ"] == ["50000"]
            bridge.cap_match_buyin = lambda fields: {**fields, "byin_chips": 0}
            assert not await sess.quick_start(big_blind=1000, buyin_bb=100)
            assert len([s for s in ws.sent if s[0] == "pb.QuickStartREQ"]) == 1
        finally:
            await sess.close()
    asyncio.run(run())


def test_session_closes_after_missed_heartbeats(monkeypatch):
    async def run():
        bridge = _RecordingBridge()
        sess, ws = await _connect_with_fake(monkeypatch, bridge)
        ws.answer_heartbeats = False
        await asyncio.wait_for(sess.wait_closed(), timeout=2.0)
        assert ws.closed
        assert sess.stats.heartbeats_missed == 1
    asyncio.run(run())


def test_slow_bridge_does_not_starve_heartbeat(monkeypatch):
    """A slow bridge handler (e.g. post-showdown learning after WinnerRSP, which
    took 10s+ live) must not block the receive loop — otherwise HeartBeatRSP sits
    unread and the session is wrongly closed as 'heartbeat lost'."""
    async def run():
        bridge = _RecordingBridge()
        bridge.slow["pb.WinnerRSP"] = 0.6          # ~12 beats @ 0.05s, far over the 2-miss limit
        sess, ws = await _connect_with_fake(monkeypatch, bridge)
        try:
            for _ in range(100):
                if sess.bankroll_dashboard()["frames_handled"] == 1:
                    break
                await asyncio.sleep(0.01)
            initial = sess.bankroll_dashboard()
            assert initial["frames_handled"] == 1
            ws.push("pb.WinnerRSP", {"winner": [{"seatid": 1, "chips": "10"}]})
            await asyncio.sleep(0.1)
            # Web reads the last complete snapshot while the handler is busy.
            assert sess._bridge_lock.locked()
            assert sess.bankroll_dashboard() == initial
            await asyncio.sleep(0.8)
            assert sess.connected, "session wrongly closed while the bridge was busy"
            assert sess.stats.heartbeats_missed == 0
            assert any(t == "pb.WinnerRSP" for t, _ in bridge.handled)   # still processed, in the end
            assert sess.bankroll_dashboard()["frames_handled"] == len(bridge.handled)
        finally:
            await sess.close()
    asyncio.run(run())


async def _web_get_json(port, path="/api/status"):
    reader, writer = await asyncio.open_connection("127.0.0.1", port)
    try:
        writer.write(f"GET {path} HTTP/1.1\r\nHost: localhost\r\n\r\n".encode())
        await writer.drain()
        response = await asyncio.wait_for(reader.read(), timeout=2)
        headers, body = response.split(b"\r\n\r\n", 1)
        assert headers.startswith(b"HTTP/1.1 200")
        return json.loads(body)
    finally:
        writer.close()
        await writer.wait_closed()


def test_headless_web_bankroll_tracks_wallet_hands_rebuy_and_leave(monkeypatch):
    """Actual Web route + WSS decoder + bridge accounting, with no game/network IO."""
    from unittest.mock import Mock

    from pf_entertainment.live_table import LiveTableObserver, start_live_web
    from pf_intercept.bot import BotBridge

    bridge = BotBridge(max_auto_rebuy=5)
    # Keep strategy/model work and player lookups out of this accounting test.
    monkeypatch.setattr(bridge, "_ensure_api", lambda: bridge._api is not None)
    monkeypatch.setattr(bridge, "_trigger_gamedata_fetch", lambda *_: None)
    monkeypatch.setattr(bridge, "_runtime_calibration_should_pause_play", lambda: None)

    async def run():
        sess, ws = await _connect_with_fake(monkeypatch, bridge)
        observer = LiveTableObserver(my_uid=42, chips_source=sess.live_total_chips)
        sess.on_frame = observer.observe
        server = await start_live_web(observer, port=0, bankroll_source=sess.bankroll_dashboard)

        async def dashboard(**expected):
            async def wait_for_values():
                while True:
                    status = await _web_get_json(server.port)
                    assert status["ok"]
                    data = status["runtime"]["bot_dashboard"]
                    if all(data[k] == v for k, v in expected.items()):
                        return data
                    await asyncio.sleep(0.01)
            return await asyncio.wait_for(wait_for_values(), timeout=2)

        def wallet(chips):
            ws.push("pb.UserValueRSP", {"type": 10100001, "value": chips})

        def deal(number, stack):
            ws.push("pb.DealerInfoRSP", {
                "dealer": 0, "small_blind": 0, "big_blind": 1,
                "gameid": f"bankroll-{number}",
                "start_info": [{"seatid": 0, "chips": stack}, {"seatid": 1, "chips": 200}],
            })

        def settle(profit):
            ws.push("pb.WinnerRSP", {"profit": [{"uid": "42", "chips": profit}]})

        try:
            empty = await dashboard(wallet_chips=None, current_total_chips=None)
            assert empty["max_auto_rebuy"] == 5
            assert empty["samples"] == empty["hand_points"] == []
            assert (await _web_get_json(server.port, "/api/live"))["live"]["total_chips"] is None
            wallet(50_000)
            await dashboard(base_total_chips=50_000, session_delta_chips=0)

            ws.push("pb.SelfUserInfoRSP", {"brief": {"uid": "42"}})
            ws.push("pb.EnterRoomRSP", {
                "code": 0, "roomid": 777, "game_type": 10010101,
                "room_info": {"bb": 2, "sb": 1, "lobby_coin": 10100001},
                "table_status": {"seat": [{
                    "seatid": 0, "player": {"uid": "42"},
                    "hand_chips": 200, "begin_chips": 200,
                }]},
            }, room_id=777)
            wallet(49_800)
            # Buying in transfers funds; it must not appear as a profit or loss.
            await dashboard(table_chips=200, wallet_chips=49_800, session_delta_chips=0)

            bridge._api = Mock()
            deal(1, 200)
            settle(30)
            won = await dashboard(table_chips=230, session_delta_chips=30)
            assert won["session_delta_bb"] == 15
            assert won["hand_points"][0]["hand_no"] == 1
            assert won["hand_points"][0]["hand_delta_chips"] == 30
            assert won["hand_points"][0]["total_chips"] == 50_030
            # The live view shows the same total: wallet plus the chips on the table.
            assert (await _web_get_json(server.port, "/api/live"))["live"]["total_chips"] == 50_030

            # Returned snapshots cannot mutate the cached accounting history.
            detached = sess.bankroll_dashboard()
            detached["hand_points"][0]["delta_chips"] = -999
            assert sess.bankroll_dashboard()["hand_points"][0]["delta_chips"] == 30

            deal(2, 230)
            settle(-230)
            await dashboard(table_chips=0, session_delta_chips=-200)
            ws.push("pb.NoticeRebyRSP", {"seatid": 0, "reby_left_time": 30})
            await dashboard(pending_reason="auto_rebuy")
            wallet(49_800)
            await dashboard(auto_rebuy_count=1)
            ws.push("pb.RebyBRC", {"seatid": 0, "chips": 200})
            wallet(49_600)
            await dashboard(table_chips=200, wallet_chips=49_600, session_delta_chips=-200)

            deal(3, 200)
            settle(10)
            final = await dashboard(table_chips=210, session_delta_chips=-190)
            assert [p["buyin_seq"] for p in final["hand_points"]] == [1, 1, 2]
            assert [p["hand_delta_chips"] for p in final["hand_points"]] == [30, -230, 10]
            assert final["profit_lock_count"] == 0

            ws.push("pb.LeaveRoomRSP", {"code": 0})
            wallet(49_810)
            left = await dashboard(table_chips=0, current_total_chips=49_810)
            assert left["session_delta_chips"] == -190
            assert left["base_total_chips"] == 50_000
            assert len(left["hand_points"]) == 3
            assert (await _web_get_json(server.port, "/api/live"))["available"] is True

            # A new session never inherits this run's baseline/hand history.
            fresh = hs.HeadlessSession(_login_result(), max_auto_rebuy=5)
            assert fresh.bankroll_dashboard()["base_total_chips"] is None
            assert fresh.bankroll_dashboard()["hand_points"] == []
        finally:
            server._server.close()
            await server._server.wait_closed()
            await sess.close()

    asyncio.run(run())


def test_bankroll_display_error_does_not_drop_bot_action(monkeypatch):
    async def run():
        bridge = _RecordingBridge()
        sess, ws = await _connect_with_fake(monkeypatch, bridge)
        previous = sess.bankroll_dashboard()

        def broken_dashboard():
            raise ValueError("display failure")

        monkeypatch.setattr(bridge, "bankroll_dashboard", broken_dashboard)
        bridge.injects["pb.ActionNotifyBRC"] = ("pb.ActionREQ", {"action_type": 3, "chips": 50}, 0.0)
        try:
            ws.push("pb.ActionNotifyBRC", {"seatid": 0, "call_need_chips": 50})
            for _ in range(100):
                if "pb.ActionREQ" in ws.sent_types():
                    break
                await asyncio.sleep(0.01)
            assert "pb.ActionREQ" in ws.sent_types()
            assert sess.bankroll_dashboard() == previous
            assert sess.connected
        finally:
            await sess.close()

    asyncio.run(run())


def test_headless_cli_web_follows_current_session_on_server_fallback(monkeypatch, caplog):
    from types import SimpleNamespace

    from pf_entertainment import live_table
    from pf_intercept.headless import __main__ as cli

    result = _login_result()
    result.servers.append(hl.ServerEntry("wss://10.0.0.2:9013", ""))
    monkeypatch.setattr(cli, "_resume_result", lambda _: (result, 5, "1.7.0"))
    captured = {}
    attempts = []

    async def keep_order(servers):
        return servers

    async def fake_web(observer, **kwargs):
        captured.update(kwargs)
        return SimpleNamespace(port=9022)

    class FailedSession:
        logged_in = False

        def __init__(self, *args, **kwargs):
            pass

        def bankroll_dashboard(self):
            return {"session_id": id(self)}

        async def connect(self, server_index):
            attempts.append(self)
            assert captured["bankroll_source"]() == {"session_id": id(self)}
            raise OSError("test server unavailable")

        async def close(self, reason):
            pass

    monkeypatch.setattr(cli, "_order_servers_by_latency", keep_order)
    monkeypatch.setattr(cli, "HeadlessSession", FailedSession)
    monkeypatch.setattr(live_table, "start_live_web", fake_web)
    args = SimpleNamespace(no_notify=True, session_file="unused", profit_lock_bb=None,
                           no_web=False, web_host="127.0.0.1", web_port=9022, max_auto_rebuy=5)
    assert asyncio.run(cli._run(args)) == 2
    assert "连接/登录失败" in caplog.text
    assert "所有服务器登录失败" in caplog.text
    assert len(attempts) == 2 and attempts[0] is not attempts[1]


def test_rewards_http_does_not_block_heartbeats_or_actions_and_notice_wakes_worker(monkeypatch, tmp_path):
    import threading
    from pf_intercept.headless.lobby.core.service import RewardService
    from tests.test_headless_rewards import eventually, task_list

    async def run():
        entered, release = threading.Event(), threading.Event()
        calls, credits = [], []
        bridge = _RecordingBridge()
        bridge.bankroll_dashboard = lambda: {"base_total_chips": 1000}
        bridge.record_reward_credit = lambda chips, uncertain: credits.append((chips, uncertain))
        bridge.injects["pb.ActionNotifyBRC"] = ("pb.ActionREQ", {"action_type": 3, "chips": 50}, 0.0)

        def post(url, payload, **kwargs):
            calls.append(url)
            assert kwargs['token'] == 'a'  # saved WSS session, never legacy auth_token.txt
            if url.endswith('/task/list'):
                entered.set()
                assert release.wait(2)
                return task_list()
            if url.endswith('/activity/rebate'):
                return {"code": 0, "status": 1, "reward": 20}
            # The fund is ready at its second status read, the one the notice below asks for;
            # every other read (other activities included) answers that nothing is there.
            ready = sum(u.endswith('/activity/rebateStatus') for u in calls) == 2
            return {"code": 0, "status": 1 if url.endswith('/activity/rebateStatus') and ready else 0}

        def create_service(**kwargs):
            return RewardService(**kwargs, post=post, journal_path=tmp_path / 'rewards.jsonl')

        monkeypatch.setattr(hs, 'RewardService', create_service)
        sess, ws = await _connect_with_fake(monkeypatch, bridge, auto_rewards=True)
        try:
            await eventually(entered.is_set)
            ws.push('pb.NoticeBRC', {'type': 10082, 'message': '{}'})
            ws.push('pb.ActionNotifyBRC', {'seatid': 0, 'call_need_chips': 50}, room_id=777)
            await eventually(lambda: any(t == 'pb.ActionREQ' for t, _, _ in ws.sent))
            await asyncio.sleep(.16)
            assert sess.connected
            assert sess.stats.heartbeats_sent >= 2
            assert sess.stats.heartbeats_missed == 0
            assert not any(t == 'pb.NoticeBRC' for t, _ in bridge.handled)
            release.set()
            await eventually(lambda: credits == [(20, False)])
            assert any(url.endswith('/activity/rebate') for url in calls)
        finally:
            release.set()
            await sess.close()

    asyncio.run(run())


def test_a_reward_or_an_unknown_side_game_result_never_touches_poker_pnl(monkeypatch):
    from pf_intercept.bot import BotBridge
    from tests.test_headless_rewards import eventually

    async def run():
        bridge = BotBridge()
        sess, ws = await _connect_with_fake(monkeypatch, bridge)
        try:
            ws.push('pb.UserValueRSP', {'type': 10100001, 'value': 1000})
            await eventually(lambda: sess.bankroll_dashboard()['base_total_chips'] == 1000)
            # The wallet can move before the claim's HTTP reply says by how much.
            ws.push('pb.UserValueRSP', {'type': 10100001, 'value': 1100})
            await eventually(lambda: sess.bankroll_dashboard()['wallet_chips'] == 1100)
            assert sess.bankroll_dashboard()['session_delta_chips'] == 0
            await sess._on_reward_credit(100, False)
            await sess.on_sidegame_result(-30)
            await sess._on_reward_credit(0, True)             # a round whose result never arrived
            d = sess.bankroll_dashboard()
            assert d['session_delta_chips'] == 0
            assert (d['reward_chips'], d['sidegame_net_chips'], d['rewards_uncertain']) == (100, -30, True)
        finally:
            await sess.close()

    asyncio.run(run())


def test_activity_request_reserves_a_timed_out_reply_type_for_a_bounded_time(monkeypatch):
    from pf_intercept.headless.lobby.core.base import RewardAPIError
    from tests.test_headless_rewards import eventually

    async def run():
        monkeypatch.setattr(hs, "_ACTIVITY_REPLY_TIMEOUT_SEC", 0.05)
        monkeypatch.setattr(hs, "_ACTIVITY_LATE_REPLY_SEC", 0.2)
        sess, ws = await _connect_with_fake(monkeypatch, _RecordingBridge())
        sess._bankroll_ready.set()
        sent = lambda name: ws.sent_types().count(f"pb.{name}REQ")
        try:
            # No reply: the outcome is unknown and the reply type stays reserved.
            with pytest.raises(RewardAPIError) as lost:
                await sess.activity_request("ThrowDice", {"multiple": 1})
            assert lost.value.code is None
            with pytest.raises(RewardAPIError) as busy:
                await sess.activity_request("ThrowDice", {"multiple": 1})
            assert busy.value.code == "waiting for late response"
            assert sent("ThrowDice") == 1
            # The late reply is dropped, never handed to the next request, and frees the type.
            ws.push("pb.ThrowDiceRSP", {"index": 3, "all_cost_num": 1})
            await eventually(lambda: "pb.ThrowDiceRSP" not in sess._activity_pending)
            task = asyncio.create_task(sess.activity_request("ThrowDice", {"multiple": 1}))
            await eventually(lambda: sent("ThrowDice") == 2)
            ws.push("pb.ThrowDiceRSP", {"index": 5, "all_cost_num": 2})
            assert (await task)["index"] == 5
            # A reply that never comes stops blocking once the window is over.
            with pytest.raises(RewardAPIError):
                await sess.activity_request("GetProgressReward", {})
            await asyncio.sleep(0.25)
            task = asyncio.create_task(sess.activity_request("GetProgressReward", {}))
            await eventually(lambda: sent("GetProgressReward") == 2)
            ws.push("pb.GetProgressRewardRSP", {"progress": 2})
            assert (await task)["progress"] == 2
            # A request that cannot be encoded was never sent: a definite failure, nothing reserved.
            with pytest.raises(RewardAPIError) as bad:
                await sess.activity_request("NoSuchMessage", {})
            assert bad.value.code == "encode failed"
            assert not sess._activity_pending and not sess._activity_late
        finally:
            await sess.close()

    asyncio.run(run())
