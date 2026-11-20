from __future__ import annotations

import asyncio
import json
import logging

from pf_entertainment.web import EntertainmentWebServer, _HttpRequest


def test_web_range_compare_api_runs_analysis(monkeypatch) -> None:
    class Runtime:
        def __init__(self) -> None:
            self.log = logging.getLogger("test-web-runtime")

    async def fake_runner(self):
        return {"ok": True, "summary": {"count": 1}, "conclusion": ["ok"]}

    monkeypatch.setattr(
        EntertainmentWebServer,
        "_run_range_analysis_subprocess",
        fake_runner,
    )

    async def run() -> tuple[int, dict, int, dict]:
        server = EntertainmentWebServer(runtime=Runtime())
        start_request = _HttpRequest(
            method="POST",
            target="/api/range/compare",
            path="/api/range/compare",
            query={},
            headers={},
            body=b"",
        )
        status, _headers, body = await server._route(start_request)
        start_data = json.loads(body)
        assert server._range_task is not None
        await server._range_task
        status2, _headers2, body2 = await server._route(
            _HttpRequest(
                method="GET",
                target="/api/range/compare/status",
                path="/api/range/compare/status",
                query={},
                headers={},
                body=b"",
            )
        )
        return status, start_data, status2, json.loads(body2)

    status, start_data, status2, final_data = asyncio.run(run())

    assert status == 202
    assert start_data["ok"] is True
    assert start_data["job"]["status"] == "running"
    assert status2 == 200
    assert final_data["job"]["status"] == "done"
    assert final_data["job"]["result"] == {
        "ok": True,
        "summary": {"count": 1},
        "conclusion": ["ok"],
    }


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
