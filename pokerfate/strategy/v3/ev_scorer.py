"""EV scoring for v3 action candidates."""

from __future__ import annotations

from pokerfate.core.config import RAKE_KEEP
from pokerfate.strategy.v3.candidates import ActionCandidate
from pokerfate.strategy.v3.context import DecisionCtx
from pokerfate.strategy.v3 import counterfactual, risk_model
from pokerfate.strategy.v3.decision_trace import ScoredCandidate


def _pot(ctx: DecisionCtx) -> float:
    return max(0.0, float(ctx.pot or 0.0))


def _call_cost(ctx: DecisionCtx) -> float:
    return max(0.0, min(float(ctx.to_call or 0.0), float(ctx.stack or ctx.to_call or 0.0)))


def score(
    ctx: DecisionCtx,
    cand: ActionCandidate,
    *,
    conservative: bool = True,
    range_only: bool = False,
) -> ScoredCandidate:
    """EV of one candidate. ``conservative`` prices calls on the pessimistic
    equity (min of range/MC minus uncertainty), which suits ranking many
    candidates; the EV veto/promotion pass ``range_only`` so calls are priced
    on the calibrated range equity alone."""
    pot = _pot(ctx)
    action = cand.action
    risk = risk_model.assess(ctx, action=action, frac=cand.frac, jammed=cand.jammed, purpose=cand.purpose)
    raw_ev = 0.0
    reason = ""
    components = {"risk": risk.as_dict(), "metadata": dict(cand.metadata or {})}
    confidence = 1.0
    if action == "fold":
        raw_ev = 0.0
        reason = "fold baseline"
    elif action == "check":
        raw_ev = risk_model.check_value(ctx)
        reason = "check baseline"
    elif action == "call":
        eq, mode, conf = counterfactual.effective_equity(ctx, conservative=conservative, range_only=range_only)
        # Low-SPR cheap calls are priced by the better of conservative range and raw MC,
        # with risk premium still applied below. This replaces the old fold_override path
        # without doing a post-hoc action rewrite.
        # River relative distributions are exact showdown relations; never
        # let the random-hand MC estimate override them.
        if (
            not range_only
            and mode != "rel_dist"
            and ctx.raw_pot_odds <= 0.30
            and ctx.hero_bucket not in {"air", "weak", "weak_draw"}
            and (ctx.spr <= 1.0 or abs(float(ctx.equity_mc or 0.0) - float(ctx.equity_range or 0.0)) >= 0.18)
            and max(float(ctx.equity_range or 0.0), float(ctx.equity_mc or 0.0) - 0.08) >= ctx.pot_odds + 0.08
        ):
            eq = max(eq, min(0.98, float(ctx.equity_mc or 0.0) - 0.08))
            mode = mode + "+cheap_low_spr"
        cost = _call_cost(ctx)
        io = 0.0
        if not cand.jammed and ctx.to_call < ctx.stack:
            if ctx.draw.flush_draw:
                io += min(ctx.stack, pot * 1.5) * (0.18 if ctx.blockers.nut_flush_blocker else 0.10)
            if ctx.draw.oesd:
                io += min(ctx.stack, pot * 1.2) * 0.10
            if ctx.draw.gutshot and ctx.draw.overcards:
                io += min(ctx.stack, pot) * 0.04
        # Win (pot + cost) × keep when ahead, lose cost otherwise.
        raw_ev = eq * (pot + cost) * RAKE_KEEP - cost + io
        confidence = conf
        components.update({"eq": round(eq, 4), "eq_mode": mode, "cost": cost, "pot_odds": ctx.pot_odds, "io": round(io, 4)})
        reason = f"call eq={eq:.2f}/{mode}"
    elif action in {"bet", "raise"}:
        bet = max(0.0, float(cand.amount or 0.0))
        if action == "raise" and ctx.facing_bet:
            extra = max(0.0, bet - float(ctx.to_call or 0.0))
            frac = extra / max(pot + extra, 1.0)
            invested = float(ctx.to_call or 0.0) + extra
            kind = "raise"
        else:
            extra = bet
            frac = cand.frac if cand.frac > 0 else bet / max(pot, 1.0)
            invested = bet
            kind = "bet"
        rx = counterfactual.reaction_estimate(ctx, frac, kind, purpose=cand.purpose)
        # Every branch that wins the pot is raked: fold wins pot × keep,
        # a called bet wins (pot + extra + invested) × keep − invested, etc.
        call_ev = rx.eq_call * (pot + extra + invested) * RAKE_KEEP - invested
        raise_ev = rx.eq_raise * (pot + 3.0 * invested) * RAKE_KEEP - invested
        if ctx.hero_bucket != "nuts":
            raise_ev = min(raise_ev, -invested)
        raw_ev = rx.p_fold * pot * RAKE_KEEP + rx.p_call * call_ev + rx.p_raise * raise_ev
        confidence = rx.confidence
        components.update({"reaction": rx.as_dict(), "call_ev": round(call_ev, 4), "raise_ev": round(raise_ev, 4), "invested": invested})
        reason = f"{kind} pf={rx.p_fold:.2f} pc={rx.p_call:.2f} pr={rx.p_raise:.2f}"
    else:
        raw_ev = -1e9
        reason = "unknown action"
    if range_only:
        # Range-only pricing already took the tracker uncertainty as an equity
        # haircut; the MC-divergence penalty and confidence discount would
        # charge the same doubt a second time (AK on JJ4 at 28% price with 42%
        # range equity priced negative, 2026-11-08).
        confidence = 1.0
        ev = raw_ev - risk.premium
    else:
        ev = raw_ev - risk.premium - risk.confidence_penalty - (1.0 - confidence) * risk.margin
    return ScoredCandidate(
        label=cand.label,
        action=action,
        amount=cand.amount,
        frac=cand.frac,
        purpose=cand.purpose,
        ev=ev,
        raw_ev=raw_ev,
        risk=risk.premium,
        margin=risk.margin,
        confidence=confidence,
        jammed=cand.jammed,
        reason=reason,
        components=components,
    )
