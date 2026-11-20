"""Purpose base class.

A Purpose encapsulates one betting-decision motive (see doc 02 §2, doc 03 §4).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple

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

    def active_value_sizing_allowed(self, ctx: DecisionCtx, frac: float) -> bool:
        """Whether the generic active value sizing optimizer may rewrite frac."""
        return True

    def exploit_weight(self, ctx: DecisionCtx) -> float:
        """Multiplier applied to vote_weight based on opponent exploit reads.

        Default is 1.0 (no adjustment). Subclasses / the exploit module may
        override by registering adjustments against purpose.id.
        """
        return 1.0
