from __future__ import annotations

import asyncio
import logging

import pytest


@pytest.mark.parametrize("mode", ["proxy", "headless"])
def test_web_owns_its_log_in_both_modes(tmp_path, monkeypatch, caplog, mode):
    from pf_entertainment import logger as web_logging
    from pf_entertainment.live_table import LiveTableObserver, start_live_web
    from pf_entertainment.runtime import EntertainmentRuntime

    log_path = tmp_path / "web.log"
    monkeypatch.setattr(web_logging, "LOG_DIR", tmp_path)
    monkeypatch.setattr(web_logging, "LOG_FILE", log_path)
    logger = logging.getLogger("pf_web")
    monkeypatch.setattr(logger, "handlers", [])
    monkeypatch.setattr(logger, "level", logger.level)
    monkeypatch.setattr(logger, "propagate", logger.propagate)
    caplog.set_level(logging.INFO)

    async def request(server):
        reader, writer = await asyncio.open_connection("127.0.0.1", server.port)
        try:
            writer.write(b"GET /api/status HTTP/1.1\r\nHost: localhost\r\n\r\n")
            await writer.drain()
            return await asyncio.wait_for(reader.read(), timeout=3)
        finally:
            writer.close()
            await writer.wait_closed()

    async def run():
        if mode == "proxy":
            runtime = EntertainmentRuntime(web_host="127.0.0.1", web_port=0)
            assert not log_path.exists()  # the host runtime does not configure logging
            await runtime.start()
            server = runtime._web
        else:
            server = await start_live_web(LiveTableObserver(), host="127.0.0.1", port=0)
        try:
            assert not hasattr(server.runtime, "log")
            assert server.log is web_logging.get_logger()
            assert len(logger.handlers) == 2  # one file and one console handler
            await server.start()  # repeat startup adds neither handlers nor startup records
            assert b"200 OK" in await request(server)

            def broken_status():
                raise RuntimeError("test status failure")

            monkeypatch.setattr(server.runtime, "status_data", broken_status)
            assert b"500 Internal Server Error" in await request(server)
            text = log_path.read_text()
            assert text.count("Web 已启动") == 1
            assert text.count("Web 可访问地址") == 1
            assert f"http://127.0.0.1:{server.port}" in text
            assert text.count("Web 请求失败") == 1
            assert "RuntimeError: test status failure" in text
            assert not any(record.name == "pf_web" for record in caplog.records)
            assert not (tmp_path / "entertainment.log").exists()
        finally:
            server._server.close()
            await server._server.wait_closed()

    try:
        asyncio.run(run())
    finally:
        for handler in logger.handlers:
            handler.close()


def test_live_table_treats_missing_seatid_as_seat_zero():
    """Protobuf omits seatid=0; the hero in seat 0 must still get stack/action updates."""
    from pf_entertainment.live_table import LiveTableObserver
    obs = LiveTableObserver(my_uid=10262053)
    obs.observe("pb.EnterRoomRSP", {"roomid": 1, "room_info": {"sb": 5000, "bb": 10000, "seat_num": 6},
                                    "table_status": {"seat": [{"player": {"uid": 10262053, "name": "Hero"}, "hand_chips": "1000000"},
                                                              {"seatid": 1, "player": {"uid": 2, "name": "V"}, "hand_chips": "2000000"}]}})
    obs.observe("pb.DealerInfoRSP", {"dealer": 1, "start_info": [{"chips": "951450"}, {"seatid": 1, "chips": "1969667"}]})
    snap = obs.snapshot()
    assert snap["my_seat"] == 0
    assert snap["seats"][0]["stack"] == 951450
    obs.observe("pb.ActionNotifyBRC", {"call_need_chips": "40000"})
    assert obs.snapshot()["action_seat"] == 0
    obs.observe("pb.ActionBRC", {"action_type": 3, "chips": "40000", "hand_chips": "911450"})
    s0 = obs.snapshot()["seats"][0]
    assert s0["stack"] == 911450 and s0["bet"] == 40000
