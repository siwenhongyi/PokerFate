"""Purposes that exist only because an opponent pre-selected his action.

``ctx.opp_reads`` says, per opponent still in the hand, what his latest pre-selected action
is worth now (pokerfate/strategy/pre_action.py).  A pre-selected check is a hand that gave
up: it folds to a bet about four times in five, whatever the size, on that street and on
the next ones.  The other purposes do not know this; the one here acts on it.
"""

from __future__ import annotations

from typing import List, Optional, Tuple

from pokerfate.strategy.v3 import ev_scorer
from pokerfate.strategy.v3.candidates import ActionCandidate
from pokerfate.strategy.v3.context import DecisionCtx
from pokerfate.strategy.v3.purpose import Purpose, TriggerResult

# Sizes tried, smallest first: the players with the read fold the same to every size, so a
# bigger bet only pays when it moves the players without one.
_SIZES = (0.33, 0.5, 0.75)
# The bet must beat checking by this share of the pot before it is proposed at all, and the
# vote weight grows with the edge (0.65 at the minimum, 1.2 from a third of the pot up).
_MIN_EDGE = 0.05
_WEIGHT_BASE = 0.55
_WEIGHT_PER_EDGE = 2.0
_WEIGHT_MAX = 1.2
_NO_MADE_HAND = ('air', 'weak_draw', 'draw')
_CHECK = ActionCandidate("default_check", "check", 0.0, 0.0, "default_check", "fallback")


class ReadStab(Purpose):
    """Bet at a field in which somebody showed he gave up.

    Priced, not assumed: the bet is proposed when its expected value (``ev_scorer``, with the
    chance that everybody folds taken from the measured single fold rates of the players with
    and without a read) beats the value of checking.

    Only for hands without a made hand.  Fold equity is what turns a hand that loses at
    showdown into a winner; a made hand gains little from folding out a player who gave up,
    and whether to bet it is the business of the value and protection purposes, which see
    the same field through the range the read has already weakened.  On 10,886 replayed
    hands the bets of made hands this purpose would have added were worth between -0.7 and
    +1.9bb each depending on what one assumes happens after a call; the ones without a made
    hand +1.2 to +1.6bb.
    """
    id = 'read_stab'
    street_gate = ('flop', 'turn', 'river')

    def best_size(self, ctx: DecisionCtx) -> Optional[Tuple[float, float]]:
        """(pot fraction, edge over checking in pots) of the best size, or None."""
        if ctx.facing_bet or not ctx.weak_reads or ctx.pot <= 0 or ctx.stack <= 0:
            return None
        if ctx.hero_bucket not in _NO_MADE_HAND:
            return None
        check_ev = ev_scorer.score(ctx, _CHECK, conservative=False, range_only=True).ev
        best: Optional[Tuple[float, float]] = None
        for frac in _SIZES:
            amount = min(frac * ctx.pot, ctx.stack)
            cand = ActionCandidate(f"{self.id}_{int(frac * 100)}", "bet", amount, frac, self.id, "purpose")
            edge = (ev_scorer.score(ctx, cand, conservative=False, range_only=True).ev - check_ev) / ctx.pot
            if best is None or edge > best[1] + 1e-9:
                best = (frac, edge)
        return best

    def trigger(self, ctx: DecisionCtx) -> TriggerResult:
        best = self.best_size(ctx)
        if best is None or best[1] < _MIN_EDGE:
            return TriggerResult(False)
        return TriggerResult(True, min(_WEIGHT_MAX, _WEIGHT_BASE + _WEIGHT_PER_EDGE * best[1]))

    def sizer(self, ctx: DecisionCtx) -> List[Tuple[float, float]]:
        best = self.best_size(ctx)
        return [(best[0], 1.0)] if best is not None else []

    def active_value_sizing_allowed(self, ctx: DecisionCtx, frac: float) -> bool:
        return False


def all_reads() -> list:
    return [ReadStab()]
