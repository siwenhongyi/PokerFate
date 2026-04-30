"""Purpose base class + registry.

A Purpose encapsulates one betting-decision motive (see doc 02 §2, doc 03 §4).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple

from pokerfate.strategy.v3.context import DecisionCtx


@dataclass
class TriggerResult:
    hit: bool
    weight: float = 0.0


class Purpose:
    """Base class for a single betting purpose.

    Subclasses override trigger/sizer/exploit_weight etc. Kept deliberately
    thin — no inheritance magic, each subclass is a small configuration +
    logic bundle.
    """

    id: str = ''
    street_gate: Tuple[str, ...] = ('flop', 'turn', 'river')
    facing_bet: bool = False
    emits_bet: bool = True              # does this purpose produce a bet/raise action?
    emits_raise: bool = False           # raise-over-villain-bet (defensive side)

    # Default action when selected (for non-bet purposes)
    default_action: str = 'bet'          # bet / check / call / fold / raise

    def trigger(self, ctx: DecisionCtx) -> TriggerResult:
        """Return (hit, vote_weight). Override in subclasses."""
        return TriggerResult(False, 0.0)

    def sizer(self, ctx: DecisionCtx) -> List[Tuple[float, float]]:
        """Return [(pot_fraction, weight)] candidate list. Override."""
        return []

    def alpha_target(self, ctx: DecisionCtx, frac: float) -> Optional[float]:
        """α target for this purpose at the given pot fraction.

        None means this purpose is merged (α check not applicable).
        """
        return frac / (1.0 + frac) if frac > 0 else None

    def exploit_weight(self, ctx: DecisionCtx) -> float:
        """Multiplier applied to vote_weight based on opponent exploit reads.

        Default is 1.0 (no adjustment). Subclasses / the exploit module may
        override by registering adjustments against purpose.id.
        """
        return 1.0


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


class PurposeRegistry:
    """Collects all purposes; splits into active/defensive/passive views."""

    def __init__(self) -> None:
        self._all: List[Purpose] = []

    def register(self, p: Purpose) -> None:
        if not p.id:
            raise ValueError("Purpose.id must be set")
        self._all.append(p)

    def active(self) -> List[Purpose]:
        return [p for p in self._all if not p.facing_bet and p.default_action in ('bet', 'check')]

    def defensive(self) -> List[Purpose]:
        return [p for p in self._all if p.facing_bet]

    def all(self) -> List[Purpose]:
        return list(self._all)

    def by_id(self, pid: str) -> Optional[Purpose]:
        for p in self._all:
            if p.id == pid:
                return p
        return None
