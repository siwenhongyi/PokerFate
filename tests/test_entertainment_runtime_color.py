from __future__ import annotations

import asyncio
import json
import logging

from pf_entertainment.color_strategy import (
    ColorMartingaleConfig,
    LeastSeenColorPicker,
    RecentResultsMostSeenColorPicker,
)
from pf_entertainment.runtime import EntertainmentRuntime
from pf_entertainment.web import EntertainmentWebServer, _HttpRequest


class _FirstChoice:
    def choice(self, seq: list[int]) -> int:
        return seq[0]


class _FakeRuntime(EntertainmentRuntime):
    def __init__(self) -> None:
        super().__init__(web_host=None, web_port=None)
        self.selected_colors: list[int] = []

    async def play_color(self, cmd, *, timeout: float = 15.0) -> dict:
        color_id = int(cmd.bets[0][0])
        self.selected_colors.append(color_id)
        return {
            "ok": True,
            "request": self._command_payload(cmd),
            "summary": {
                "code": 0,
                "bets": cmd.bets,
                "total_bet": cmd.total_bet,
                "profits": [],
                "total_return": 0,
                "net_profit": -cmd.total_bet,
                "ids": [color_id, color_id, color_id],
                "result_rates": {},
            },
            "line": "fake",
        }


class _ScriptedResultRuntime(_FakeRuntime):
    def __init__(self, results: list[list[int]]) -> None:
        super().__init__()
        self._results = [list(result) for result in results]

    async def play_color(self, cmd, *, timeout: float = 15.0) -> dict:
        color_id = int(cmd.bets[0][0])
        self.selected_colors.append(color_id)
        ids = self._results.pop(0) if self._results else [color_id, color_id, color_id]
        return {
            "ok": True,
            "request": self._command_payload(cmd),
            "summary": {
                "code": 0,
                "bets": cmd.bets,
                "total_bet": cmd.total_bet,
                "profits": [],
                "total_return": 0,
                "net_profit": -cmd.total_bet,
                "ids": ids,
                "result_rates": {},
            },
            "line": "fake",
        }


def test_color_martingale_keeps_same_color_within_cycle(monkeypatch) -> None:
    monkeypatch.setattr(
        "pf_entertainment.runtime.LeastSeenColorPicker",
        lambda: LeastSeenColorPicker(rng=_FirstChoice()),
    )
    runtime = _FakeRuntime()
    config = ColorMartingaleConfig(
        base_bet=1,
        max_bet=4,
        multiplier=2,
        cycles=1,
        delay=0,
    )

    record = asyncio.run(runtime.run_color_martingale(config))

    assert runtime.selected_colors == [101, 101, 101]
    assert [round_["selected"]["scope"] for round_ in record["rounds"]] == [
        "cycle",
        "cycle",
        "cycle",
    ]


def test_color_martingale_can_reselect_color_each_bet(monkeypatch) -> None:
    monkeypatch.setattr(
        "pf_entertainment.runtime.LeastSeenColorPicker",
        lambda: LeastSeenColorPicker(rng=_FirstChoice()),
    )
    runtime = _FakeRuntime()
    config = ColorMartingaleConfig(
        base_bet=1,
        max_bet=4,
        multiplier=2,
        cycles=1,
        delay=0,
        selection_mode="bet",
    )

    record = asyncio.run(runtime.run_color_martingale(config))

    assert runtime.selected_colors == [101, 102, 103]
    assert [round_["selected"]["scope"] for round_ in record["rounds"]] == [
        "bet",
        "bet",
        "bet",
    ]


def test_color_martingale_recent3_uses_latest_three_results_each_play(monkeypatch) -> None:
    monkeypatch.setattr(
        "pf_entertainment.runtime.RecentResultsMostSeenColorPicker",
        lambda: RecentResultsMostSeenColorPicker(rng=_FirstChoice()),
    )
    runtime = _ScriptedResultRuntime(
        [
            [101, 101, 101],
            [102, 102, 102],
            [103, 103, 103],
            [104, 104, 104],
            [105, 105, 105],
        ]
    )
    config = ColorMartingaleConfig(
        base_bet=1,
        max_bet=16,
        multiplier=2,
        cycles=1,
        delay=0,
        selection_mode="recent3_most",
    )

    record = asyncio.run(runtime.run_color_martingale(config))

    assert runtime.selected_colors == [101, 101, 101, 101, 102]
    assert [round_["selected"]["scope"] for round_ in record["rounds"]] == [
        "recent3_most",
        "recent3_most",
        "recent3_most",
        "recent3_most",
        "recent3_most",
    ]
    assert record["rounds"][-1]["selected"]["reason"] == "recent3_most_seen"
    assert [item["id"] for item in record["rounds"][-1]["selected"]["candidates"]] == [
        102,
        103,
        104,
    ]


def test_runtime_bot_settings_handlers_round_trip() -> None:
    runtime = EntertainmentRuntime(web_host=None, web_port=None)
    state = {
        "profit_lock_bb": 400,
        "decision_engine": "local",
        "preflop_sticky_pool_adjust": True,
    }

    runtime.set_bot_settings_handlers(
        lambda: dict(state),
        lambda payload: state.update(payload) or dict(state),
    )

    assert runtime.status_data()["bot_settings"] == {
        "profit_lock_bb": 400,
        "decision_engine": "local",
        "preflop_sticky_pool_adjust": True,
    }
    assert runtime.update_bot_settings(
        {
            "profit_lock_bb": 250,
            "decision_engine": "g5",
            "preflop_sticky_pool_adjust": False,
        }
    ) == {
        "profit_lock_bb": 250,
        "decision_engine": "g5",
        "preflop_sticky_pool_adjust": False,
    }


def test_web_bot_settings_api_updates_runtime() -> None:
    class Runtime:
        def __init__(self) -> None:
            self.log = logging.getLogger("test-web-runtime")
            self.settings = {
                "profit_lock_bb": 400,
                "decision_engine": "local",
                "preflop_sticky_pool_adjust": True,
            }

        def bot_settings_data(self) -> dict:
            return dict(self.settings)

        def update_bot_settings(self, payload: dict) -> dict:
            self.settings.update(payload)
            return dict(self.settings)

    runtime = Runtime()
    server = EntertainmentWebServer(runtime=runtime)
    request = _HttpRequest(
        method="POST",
        target="/api/bot/settings",
        path="/api/bot/settings",
        query={},
        headers={},
        body=(
            b'{"profit_lock_bb": 300, "decision_engine": "g5_all", '
            b'"preflop_sticky_pool_adjust": false}'
        ),
    )

    status, _headers, body = asyncio.run(server._route(request))

    assert status == 200
    assert json.loads(body) == {
        "ok": True,
        "settings": {
            "profit_lock_bb": 300,
            "decision_engine": "g5_all",
            "preflop_sticky_pool_adjust": False,
        },
    }


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
