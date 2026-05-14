from __future__ import annotations

import random
from collections import Counter
from dataclasses import dataclass
from typing import Iterable, Protocol

from pf_entertainment.color_game import (
    ALL_COLOR_IDS,
    DEFAULT_FROM_GAME_TYPE,
    DEFAULT_LEVEL,
    DEFAULT_ROOM_ID,
    DEFAULT_STAKE,
)


class _ChoiceRng(Protocol):
    def choice(self, seq: list[int]) -> int:
        ...


@dataclass(frozen=True)
class ColorPick:
    color_id: int
    reason: str
    candidates: tuple[int, ...]
    counts_before: dict[int, int]


class LeastSeenColorPicker:
    """Per-run in-memory color selector."""

    def __init__(
        self,
        *,
        color_ids: Iterable[int] = ALL_COLOR_IDS,
        rng: _ChoiceRng | None = None,
    ) -> None:
        self._color_ids = tuple(int(color_id) for color_id in color_ids)
        if not self._color_ids:
            raise ValueError("color_ids must not be empty")
        self._rng = rng or random.SystemRandom()
        self._counts: Counter[int] = Counter({color_id: 0 for color_id in self._color_ids})
        self._observed = False

    def choose(self) -> ColorPick:
        counts = self.snapshot()
        if not self._observed:
            candidates = self._color_ids
            reason = "random"
        else:
            min_count = min(counts[color_id] for color_id in self._color_ids)
            candidates = tuple(
                color_id
                for color_id in self._color_ids
                if counts[color_id] == min_count
            )
            reason = "least_seen"
        return ColorPick(
            color_id=self._rng.choice(list(candidates)),
            reason=reason,
            candidates=candidates,
            counts_before=counts,
        )

    def observe(self, ids: Iterable[int]) -> None:
        for raw_color_id in ids:
            color_id = int(raw_color_id)
            if color_id in self._counts:
                self._counts[color_id] += 1
                self._observed = True

    def snapshot(self) -> dict[int, int]:
        return {color_id: self._counts[color_id] for color_id in self._color_ids}


@dataclass(frozen=True)
class ColorMartingaleConfig:
    base_bet: int = DEFAULT_STAKE
    max_bet: int = 100_000
    multiplier: int = 2
    cycles: int = 1
    selection_mode: str = "cycle"
    lvl: int = DEFAULT_LEVEL
    from_game_type: int = DEFAULT_FROM_GAME_TYPE
    room_id: int = DEFAULT_ROOM_ID
    timeout: float = 20.0
    delay: float = 1.5

    def validate(self) -> None:
        if self.base_bet <= 0:
            raise ValueError("base_bet must be > 0")
        if self.max_bet < self.base_bet:
            raise ValueError("max_bet must be >= base_bet")
        if self.multiplier <= 1:
            raise ValueError("multiplier must be > 1")
        if self.cycles <= 0:
            raise ValueError("cycles must be > 0")
        if self.selection_mode not in ("cycle", "bet"):
            raise ValueError("selection_mode must be 'cycle' or 'bet'")
        if not 1 <= self.lvl <= 5:
            raise ValueError("lvl must be in 1..5")
        if self.room_id < 0:
            raise ValueError("room_id must be >= 0")
        if self.timeout <= 0:
            raise ValueError("timeout must be > 0")
        if self.delay < 0:
            raise ValueError("delay must be >= 0")

    @classmethod
    def from_mapping(cls, raw: dict) -> "ColorMartingaleConfig":
        def raw_value(names: tuple[str, ...], default):
            for name in names:
                if name in raw:
                    return raw[name]
            return default

        def read_int(names: tuple[str, ...], default: int) -> int:
            value = raw_value(names, default)
            if value is None or value == "":
                return default
            return int(value)

        def read_float(names: tuple[str, ...], default: float) -> float:
            value = raw_value(names, default)
            if value is None or value == "":
                return default
            return float(value)

        def read_str(names: tuple[str, ...], default: str) -> str:
            value = raw_value(names, default)
            if value is None or value == "":
                return default
            return str(value)

        config = cls(
            base_bet=read_int(("base_bet", "base"), DEFAULT_STAKE),
            max_bet=read_int(("max_bet", "max"), 100_000),
            multiplier=read_int(("multiplier",), 2),
            cycles=read_int(("cycles", "cycle_count"), 1),
            selection_mode=read_str(("selection_mode", "pick_mode"), "cycle"),
            lvl=read_int(("lvl", "level"), DEFAULT_LEVEL),
            from_game_type=read_int(("from_game_type", "from"), DEFAULT_FROM_GAME_TYPE),
            room_id=read_int(("room_id", "room"), DEFAULT_ROOM_ID),
            timeout=read_float(("timeout",), 20.0),
            delay=read_float(("delay",), 1.5),
        )
        config.validate()
        return config

    def to_dict(self) -> dict:
        return {
            "base_bet": self.base_bet,
            "max_bet": self.max_bet,
            "multiplier": self.multiplier,
            "cycles": self.cycles,
            "selection_mode": self.selection_mode,
            "lvl": self.lvl,
            "from_game_type": self.from_game_type,
            "room_id": self.room_id,
            "timeout": self.timeout,
            "delay": self.delay,
        }


def bet_sequence(base_bet: int, max_bet: int, multiplier: int) -> list[int]:
    config = ColorMartingaleConfig(
        base_bet=base_bet,
        max_bet=max_bet,
        multiplier=multiplier,
    )
    config.validate()

    bets: list[int] = []
    stake = base_bet
    while stake <= max_bet:
        bets.append(stake)
        stake *= multiplier
    return bets
