from __future__ import annotations

import asyncio
import logging

from pf_intercept.proxy.bot_worker import (
    BotWorkerClient,
    _inject_payload,
    _load_bark_key_for_worker,
)
from pf_notify.config import get_bark_key, set_bark_key


class _FakeBridge:
    def room_id_for_c2s(self, frame_room_id: int) -> int:
        return frame_room_id or 99

    def injection_guard_for(self, inject):
        if inject and inject[0] == "pb.ActionREQ":
            return ("g123", 7)
        return None


def test_inject_payload_preserves_room_delay_and_guard() -> None:
    payload = _inject_payload(
        bridge=_FakeBridge(),
        session_id=4,
        frame_room_id=0,
        inject=("pb.ActionREQ", {"action_type": 7, "chips": 135}, 1.25),
    )

    assert payload is not None
    assert payload["kind"] == "inject"
    assert payload["session_id"] == 4
    assert payload["type_name"] == "pb.ActionREQ"
    assert payload["fields"] == {"action_type": 7, "chips": 135}
    assert payload["delay_sec"] == 1.25
    assert payload["room_id"] == 99
    assert payload["guard"] == ["g123", 7]


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
        client = BotWorkerClient(max_auto_rebuy=1, profit_lock_bb=None, use_range_equity=True)
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


def test_bot_worker_process_start_stop() -> None:
    async def run() -> None:
        client = BotWorkerClient(max_auto_rebuy=1, profit_lock_bb=None, use_range_equity=True)
        await client.start()
        try:
            status = client.status()
            assert status["alive"] is True
            assert isinstance(status["pid"], int)
            settings = client.runtime_settings()
            assert isinstance(settings, dict)
            assert settings["decision_engine"]
        finally:
            await client.stop()
        assert client.status()["alive"] is False

    asyncio.run(run())
