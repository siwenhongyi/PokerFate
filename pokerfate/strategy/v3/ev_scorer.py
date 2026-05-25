"""EV scoring for v3 action candidates."""

from __future__ import annotations

from pokerfate.strategy.v3.candidates import ActionCandidate
from pokerfate.strategy.v3.context import DecisionCtx
from pokerfate.strategy.v3 import counterfactual, risk_model
from pokerfate.strategy.v3.decision_trace import ScoredCandidate


def _pot(ctx: DecisionCtx) -> float:
    return max(0.0, float(ctx.pot or 0.0))


def _call_cost(ctx: DecisionCtx) -> float:
    return max(0.0, min(float(ctx.to_call or 0.0), float(ctx.stack or ctx.to_call or 0.0)))


def score(ctx: DecisionCtx, cand: ActionCandidate) -> ScoredCandidate:
    pot = _pot(ctx)
    action = cand.action
    risk = risk_model.assess(ctx, action=action, frac=cand.frac, jammed=cand.jammed, purpose=cand.purpose)
    raw_ev = 0.0
    reason = ""
    components = {"risk": risk.as_dict()}
    confidence = 1.0
    if action == "fold":
        raw_ev = 0.0
        reason = "fold baseline"
    elif action == "check":
        raw_ev = risk_model.check_value(ctx)
        reason = "check baseline"
    elif action == "call":
        eq, mode, conf = counterfactual.effective_equity(ctx, conservative=True)
        # Low-SPR cheap calls are priced by the better of conservative range and raw MC,
        # with risk premium still applied below. This replaces the old fold_override path
        # without doing a post-hoc action rewrite.
        if (
            ctx.pot_odds <= 0.30
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
        raw_ev = eq * pot - (1.0 - eq) * cost + io
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
        rx = counterfactual.reaction_estimate(ctx, frac, kind)
        call_ev = rx.eq_call * (pot + extra) - (1.0 - rx.eq_call) * invested
        raise_ev = rx.eq_raise * (pot + 2.0 * invested) - (1.0 - rx.eq_raise) * invested
        if ctx.hero_bucket != "nuts":
            raise_ev = min(raise_ev, -invested)
        raw_ev = rx.p_fold * pot + rx.p_call * call_ev + rx.p_raise * raise_ev
        confidence = rx.confidence
        components.update({"reaction": rx.as_dict(), "call_ev": round(call_ev, 4), "raise_ev": round(raise_ev, 4), "invested": invested})
        reason = f"{kind} pf={rx.p_fold:.2f} pc={rx.p_call:.2f} pr={rx.p_raise:.2f}"
    else:
        raw_ev = -1e9
        reason = "unknown action"
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


def robust_select(ctx: DecisionCtx, scored: list[ScoredCandidate]) -> tuple[ScoredCandidate, float, str]:
    ordered = sorted(scored, key=lambda s: s.ev, reverse=True)
    value_jams = [s for s in ordered if s.purpose == "value_jam" and s.jammed]
    if value_jams and ordered and value_jams[0].ev >= ordered[0].ev - max(value_jams[0].margin, 0.04 * max(float(ctx.pot or 0.0), 1.0)):
        ordered = [value_jams[0]] + [s for s in ordered if s is not value_jams[0]]
    if not ordered:
        fallback = ScoredCandidate("fold" if ctx.facing_bet else "check", "fold" if ctx.facing_bet else "check", 0.0, 0.0, "fallback", 0.0, 0.0)
        return fallback, 0.0, "fallback"
    top = ordered[0]
    second = ordered[1] if len(ordered) > 1 else None
    gap = top.ev - (second.ev if second else 0.0)
    passive = next((s for s in ordered if s.action in {"check", "fold"}), None)
    if top.action in {"bet", "raise", "call"} and passive is not None:
        required = max(top.margin, passive.margin, 0.0)
        if top.action == "call" and ctx.pot_odds <= 0.30:
            required *= 0.35
        if top.ev < passive.ev + required:
            return passive, passive.ev - top.ev, "robust_margin"
    return top, gap, "deterministic"
