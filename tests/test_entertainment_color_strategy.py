from __future__ import annotations

import pytest

from pf_entertainment.color_game import ALL_COLOR_IDS
from pf_entertainment.color_strategy import (
    ColorMartingaleConfig,
    LeastSeenColorPicker,
    RandomColorPicker,
    RecentResultsMostSeenColorPicker,
    bet_sequence,
)


class _FirstChoice:
    def choice(self, seq: list[int]) -> int:
        return seq[0]


class _LastChoice:
    def choice(self, seq: list[int]) -> int:
        return seq[-1]


def test_least_seen_picker_starts_random_then_uses_min_count() -> None:
    picker = LeastSeenColorPicker(rng=_FirstChoice())

    first = picker.choose()
    assert first.reason == "random"
    assert first.candidates == ALL_COLOR_IDS

    picker.observe([101, 101, 103])
    second = picker.choose()
    assert second.reason == "least_seen"
    assert set(second.candidates) == {102, 104, 105, 106}
    assert second.color_id == 102


def test_least_seen_picker_counts_across_observations() -> None:
    picker = LeastSeenColorPicker(rng=_FirstChoice())
    picker.observe([101, 102, 103])
    picker.observe([101, 104, 105])

    pick = picker.choose()
    assert pick.reason == "least_seen"
    assert pick.candidates == (106,)


def test_random_picker_selects_from_all_colors_each_time() -> None:
    picker = RandomColorPicker(rng=_LastChoice())

    first = picker.choose()
    assert first.reason == "random_each"
    assert first.candidates == ALL_COLOR_IDS
    assert first.color_id == 106

    picker.observe([101, 101, 102])
    second = picker.choose()
    assert second.reason == "random_each"
    assert second.candidates == ALL_COLOR_IDS
    assert second.color_id == 106


def test_recent_results_picker_uses_latest_three_result_records() -> None:
    picker = RecentResultsMostSeenColorPicker(rng=_FirstChoice())

    first = picker.choose()
    assert first.reason == "random"
    assert first.candidates == ALL_COLOR_IDS

    picker.observe([101, 101, 101])
    picker.observe([102, 102, 102])
    picker.observe([103, 103, 103])
    tied = picker.choose()
    assert tied.reason == "recent3_most_seen"
    assert tied.candidates == (101, 102, 103)
    assert tied.color_id == 101

    picker.observe([104, 104, 104])
    rolling = picker.choose()
    assert rolling.reason == "recent3_most_seen"
    assert rolling.candidates == (102, 103, 104)
    assert rolling.color_id == 102
    assert rolling.counts_before[101] == 0
    assert rolling.counts_before[104] == 3


def test_bet_sequence_stops_at_max_bet() -> None:
    assert bet_sequence(1000, 10_000, 2) == [1000, 2000, 4000, 8000]


def test_bet_sequence_rejects_invalid_range() -> None:
    with pytest.raises(ValueError):
        bet_sequence(1000, 500, 2)


def test_color_martingale_config_accepts_cli_style_aliases() -> None:
    config = ColorMartingaleConfig.from_mapping(
        {
            "base": "1000",
            "max": "8000",
            "cycle_count": "3",
            "level": "2",
            "pick_mode": "bet",
        }
    )
    assert config.base_bet == 1000
    assert config.max_bet == 8000
    assert config.cycles == 3
    assert config.lvl == 2
    assert config.selection_mode == "bet"


@pytest.mark.parametrize("selection_mode", ["cycle", "bet", "random_each", "recent3_most"])
def test_color_martingale_config_accepts_selection_modes(selection_mode: str) -> None:
    config = ColorMartingaleConfig.from_mapping({"selection_mode": selection_mode})

    assert config.selection_mode == selection_mode


def test_color_martingale_config_rejects_unknown_selection_mode() -> None:
    with pytest.raises(ValueError):
        ColorMartingaleConfig.from_mapping({"selection_mode": "round"})
