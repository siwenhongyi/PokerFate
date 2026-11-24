from __future__ import annotations

import asyncio
import logging
import queue
from pf_intercept.options import RunOptions

from pf_intercept.proxy.bot_worker import (
    BotWorkerClient,
    _load_bark_key_for_worker,
)
from pf_notify.config import get_bark_key, set_bark_key


def test_worker_loads_bark_key_from_file(tmp_path) -> None:
    key_file = tmp_path / "bark_key.txt"
    key_file.write_text("abc123\n", encoding="utf-8")
    set_bark_key(None)
    try:
        assert _load_bark_key_for_worker(logging.getLogger("test"), key_file) is True
        assert get_bark_key() == "abc123"
    finally:
        set_bark_key(None)


def test_worker_clears_bark_key_when_file_missing(tmp_path) -> None:
    set_bark_key("old-key")
    try:
        assert _load_bark_key_for_worker(logging.getLogger("test"), tmp_path / "missing.txt") is False
        assert get_bark_key() is None
    finally:
        set_bark_key(None)


def test_client_routes_worker_messages_to_cache_pending_and_session_queue() -> None:
    async def run() -> None:
        client = BotWorkerClient(max_auto_rebuy=1, profit_lock_bb=None)
        client._loop = asyncio.get_running_loop()
        client._ready = client._loop.create_future()

        client._handle_worker_message(
            {
                "kind": "ready",
                "settings": {"decision_engine": "cfr"},
                "dashboard": {"current_total_chips": 123},
            }
        )
        assert client.runtime_settings() == {"decision_engine": "cfr"}
        assert client.bankroll_dashboard() == {"current_total_chips": 123}
        assert client._ready.done()

        fut = client._loop.create_future()
        client._pending["abc"] = fut
        client._handle_worker_message({"kind": "response", "call_id": "abc", "result": 42})
        assert await fut == 42

        q = client.register_session(9)
        client._handle_worker_message(
            {
                "kind": "inject",
                "session_id": 9,
                "type_name": "pb.ActionREQ",
                "fields": {},
            }
        )
        assert (await q.get())["type_name"] == "pb.ActionREQ"

    asyncio.run(run())


def test_bot_worker_process_start_stop(tmp_path) -> None:
    async def run() -> None:
        client = BotWorkerClient(options=RunOptions(no_notify=True, no_auto_rewards=True), logs_dir=tmp_path)
        await client.start()
        try:
            status = client.status()
            assert status["alive"] is True
            assert isinstance(status["pid"], int)
            settings = client.runtime_settings()
            # the bridge state the proxy reads arrives with the worker's "ready" message
            assert settings == {"tournament_passthrough": False}
        finally:
            await client.stop()
        assert client.status()["alive"] is False

    asyncio.run(run())



def test_client_sends_connection_lifecycle(monkeypatch):
    client = BotWorkerClient(max_auto_rebuy=5, profit_lock_bb=None)
    sent = []
    monkeypatch.setattr(client, "_submit_nowait", sent.append)
    client.register_session(7)
    client.unregister_session(7)
    assert [v["kind"] for v in sent] == ["session_open", "session_close"]
    assert all(v["session_id"] == 7 for v in sent)


def test_async_worker_ignores_stale_frames_and_keeps_current_connection(monkeypatch):
    from pf_intercept.proxy.bot_worker import _worker_loop
    async def run():
        inbound, outbound = queue.Queue(), queue.Queue()
        options = RunOptions(no_notify=True, no_auto_rewards=True, no_task_hands=True)
        task = asyncio.create_task(_worker_loop(inbound, outbound, options))
        messages = []
        async def drain_until(predicate):
            for _ in range(300):
                while not outbound.empty():
                    item = outbound.get_nowait()
                    messages.append(item)
                    if item.get('send_id'):
                        inbound.put({'kind':'wire_sent', 'session_id':item['session_id'],
                                     'send_id':item['send_id'], 'ok':True})
                if predicate():
                    return
                await asyncio.sleep(.01)
            assert predicate()
        try:
            await drain_until(lambda: any(m['kind'] == 'ready' for m in messages))
            inbound.put({'kind':'session_open', 'session_id':1})
            inbound.put({'kind':'session_open', 'session_id':2})
            inbound.put({'kind':'session_close', 'session_id':1})
            for ident, room in [(2,91), (1,999)]:
                inbound.put({'kind':'s2c_msg', 'session_id':ident, 'type_name':'pb.EnterRoomRSP',
                             'room_id':room, 'msg':{'roomid':room,'game_type':10010101,
                             'room_info':{'bb':'5000','sb':'2500'}, 'table_status':{'seat':[]}}})
            await drain_until(lambda: any(m.get('live',{}).get('room_id') == 91 for m in messages))
            assert not any(m.get('live',{}).get('room_id') == 999 for m in messages)
            assert all(m.get('session_id',2) == 2 for m in messages if m.get('kind') == 'inject')
        finally:
            inbound.put({'kind':'shutdown'})
            await asyncio.wait_for(task, 3)
    asyncio.run(run())


def test_dead_worker_invalidates_live_snapshot_and_signals_runtime():
    client = BotWorkerClient()
    client._live_cache = {'connected':True, 'room_id':90}
    client._handle_worker_message({'kind':'fatal', 'error':'worker failed'})
    assert client.failed.is_set()
    assert client.live_snapshot()['connected'] is False
    assert client.live_snapshot()['connection_status'] == 'disconnected'


def test_spawned_worker_publishes_live_and_wallet_through_ipc(tmp_path):
    import json
    async def run():
        capture = tmp_path / 'session.json'
        capture.write_text(json.dumps({'uid':10,'rdkey':'fake','authorization':'fake',
                           'servers':[{'server_host':'wss://127.0.0.1:9012','http_host':'http://127.0.0.1'}]}))
        client = BotWorkerClient(options=RunOptions(no_notify=True, no_auto_rewards=True,
                                 no_task_hands=True, session_file=capture), logs_dir=tmp_path)
        await client.start()
        q = client.register_session(1, 'wss://127.0.0.1:9012')
        async def server():
            while True:
                message = await q.get()
                if message.get('send_id'):
                    client.notify_wire_sent(1, message['send_id'], True)
                if message.get('type_name') == 'pb.UserValueREQ':
                    client.submit_s2c(session_id=1, type_name='pb.UserValueRSP', room_id=0,
                                      msg={'type':10100001,'value':'1234000'})
        server_task = asyncio.create_task(server())
        try:
            assert await client.call('client_request', {'session_id':1, 'type_name':'pb.UserLoginREQ',
                                     'msg':{'uid':10,'key':'fake'}}, timeout=15)
            client.submit_s2c(session_id=1,type_name='pb.UserLoginRSP',room_id=0,msg={'code':0})
            client.submit_s2c(session_id=1,type_name='pb.UserLocationRSP',room_id=0,msg={'roomid':0})
            client.submit_s2c(session_id=1,type_name='pb.EnterRoomRSP',room_id=90,
                             msg={'roomid':90,'game_type':10010101,'room_info':{'bb':'5000'},
                                  'table_status':{'seat':[]}})
            for _ in range(300):
                if (client.live_snapshot().get('room_id') == 90 and
                    (client.bankroll_dashboard() or {}).get('wallet_chips') == 1234000):
                    break
                await asyncio.sleep(.01)
            assert client.live_snapshot()['room_id'] == 90
            assert client.bankroll_dashboard()['wallet_chips'] == 1234000
            assert client.live_snapshot()['connected']
        finally:
            client.unregister_session(1)
            server_task.cancel()
            await asyncio.gather(server_task, return_exceptions=True)
            await client.stop()
        assert not client.is_alive()
    asyncio.run(run())
