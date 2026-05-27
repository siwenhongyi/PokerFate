"""Risk premiums for the v3 EV decision layer."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from pokerfate.strategy.v3.context import DecisionCtx
from pokerfate.strategy.v3.exploit import no_fold_equity, sticky_passive

_FRAGILE_SUBTYPES = {
    "pair", "top_pair_weak_kicker", "overpair", "board_pair_hero_pair",
    "board_pair_kicker", "board_two_pair", "trips_weak_kicker",
    "clean_two_pair", "two_pair",
}


@dataclass(frozen=True)
class RiskAssessment:
    premium: float
    margin: float
    confidence_penalty: float
    tags: tuple[str, ...] = ()
    details: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "premium": round(self.premium, 4),
            "margin": round(self.margin, 4),
            "confidence_penalty": round(self.confidence_penalty, 4),
            "tags": list(self.tags),
            "details": self.details,
        }


def _pot(ctx: DecisionCtx) -> float:
    return max(1.0, float(ctx.pot or 0.0))


def assess(ctx: DecisionCtx, *, action: str, frac: float = 0.0, jammed: bool = False, purpose: str = "") -> RiskAssessment:
    tags: list[str] = []
    pot = _pot(ctx)
    premium = 0.0
    margin = 0.02 * pot
    confidence_penalty = 0.0
    commit = (float(ctx.to_call or 0.0) / max(float(ctx.stack or 1.0), 1.0)) if ctx.facing_bet else 0.0
    if action in {"bet", "raise", "call"}:
        if ctx.street == "river":
            margin += 0.015 * pot
            tags.append("river")
        if ctx.num_opponents > 1:
            premium += 0.025 * pot * (ctx.num_opponents - 1)
            margin += 0.015 * pot
            tags.append("multiway")
        if ctx.board_sig.is_wet:
            premium += 0.025 * pot
            tags.append("wet_board")
        if ctx.spr > 0 and ctx.spr <= 1.5:
            premium += 0.04 * pot
            margin += 0.03 * pot
            tags.append("low_spr")
        if commit >= 0.35:
            premium += 0.05 * pot
            margin += 0.03 * pot
            tags.append("stack_commit")
        if jammed:
            nut_draw = ctx.draw.flush_draw and ctx.blockers.nut_flush_blocker
            premium += (0.015 if nut_draw else 0.06) * pot
            margin += (0.010 if nut_draw else 0.04) * pot
            tags.append("jam")
        if (ctx.hero_made_subtype or "") in _FRAGILE_SUBTYPES and ctx.hero_bucket in {"medium", "strong"}:
            premium += 0.03 * pot
            margin += 0.025 * pot
            tags.append("fragile_made")
        if sticky_passive(ctx) or no_fold_equity(ctx):
            if action in {"bet", "raise"} and ctx.hero_bucket in {"air", "weak", "weak_draw", "draw"}:
                premium += 0.08 * pot
                margin += 0.06 * pot
                tags.append("no_fe_bluff_risk")
            elif action in {"bet", "raise"} and ctx.hero_bucket in {"medium", "strong"}:
                premium += 0.015 * pot
                tags.append("sticky_value_risk")
        div = abs(float(ctx.equity_mc or 0.0) - float(ctx.equity_range or 0.0))
        if div >= 0.12:
            confidence_penalty += min(0.08 * pot, div * 0.20 * pot)
            tags.append("equity_divergence")
        if ctx.prev_bet_called_count > 0 and action in {"bet", "raise"} and ctx.hero_bucket in {"air", "weak", "weak_draw", "draw"}:
            premium += 0.03 * pot * ctx.prev_bet_called_count
            margin += 0.02 * pot
            tags.append("barrel_resistance")
    return RiskAssessment(
        premium=premium,
        margin=margin,
        confidence_penalty=confidence_penalty,
        tags=tuple(dict.fromkeys(tags)),
        details={"commit": round(commit, 4), "spr": round(float(ctx.spr or 0.0), 4)},
    )


def check_value(ctx: DecisionCtx) -> float:
    eq, _mode, _conf = __import__("pokerfate.strategy.v3.counterfactual", fromlist=["effective_equity"]).effective_equity(ctx)
    value = eq * max(0.0, float(ctx.pot or 0.0))
    if ctx.is_ip:
        value *= 0.22
    else:
        value *= 0.12
    if ctx.hero_bucket in {"strong", "nuts"}:
        value *= 1.25
    if ctx.hero_bucket in {"air", "weak"}:
        value *= 0.40
    return value
