"""Decision trace objects emitted by the EV decision layer."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ScoredCandidate:
    label: str
    action: str
    amount: float
    frac: float
    purpose: str
    ev: float
    raw_ev: float
    risk: float = 0.0
    margin: float = 0.0
    confidence: float = 1.0
    jammed: bool = False
    reason: str = ""
    components: dict[str, Any] = field(default_factory=dict)
    blocked_by: list[str] = field(default_factory=list)

    def summary(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "action": self.action,
            "amount": round(float(self.amount), 4),
            "frac": round(float(self.frac), 4),
            "purpose": self.purpose,
            "ev": round(float(self.ev), 4),
            "raw_ev": round(float(self.raw_ev), 4),
            "risk": round(float(self.risk), 4),
            "margin": round(float(self.margin), 4),
            "confidence": round(float(self.confidence), 4),
            "jammed": bool(self.jammed),
            "reason": self.reason,
            "components": self.components,
            "blocked_by": list(self.blocked_by),
        }
