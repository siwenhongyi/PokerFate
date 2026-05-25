"""Candidate actions for the v3 EV decision layer."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ActionCandidate:
    label: str
    action: str
    amount: float = 0.0
    frac: float = 0.0
    purpose: str = ""
    source: str = ""
    jammed: bool = False
    risk_tags: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def key(self) -> tuple[str, int, str]:
        return (self.action, int(round(self.amount)), self.purpose)
