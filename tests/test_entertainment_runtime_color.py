from __future__ import annotations

import asyncio

from pf_entertainment.color_strategy import ColorMartingaleConfig, LeastSeenColorPicker
from pf_entertainment.runtime import EntertainmentRuntime


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
