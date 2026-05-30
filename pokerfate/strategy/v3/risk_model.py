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


def _mass(ctx: DecisionCtx, bucket: str) -> float:
    dist = ctx.villain_bucket_dist or {}
    return max(0.0, float(dist.get(bucket, 0.0) or 0.0))


def _value_opportunity_cap(ctx: DecisionCtx, realization: float) -> float:
    bucket = str(ctx.hero_bucket or "")
    if bucket not in {"medium", "strong", "nuts"}:
        return realization

    spr = float(ctx.spr or 0.0)
    low_spr = 0.0 < spr <= 1.8
    pay_mass = (
        _mass(ctx, "medium")
        + 0.55 * _mass(ctx, "strong")
        + 0.35 * _mass(ctx, "draw")
        + 0.30 * _mass(ctx, "weak_draw")
    )
    deny_mass = _mass(ctx, "draw") + _mass(ctx, "weak_draw")
    value_pressure = (
        low_spr
        or pay_mass >= 0.35
        or deny_mass >= 0.18
        or int(ctx.prev_bet_called_count or 0) > 0
        or int(ctx.n_sticky or 0) > 0
    )
    if not value_pressure:
        return realization

    street = str(ctx.street or "")
    if street == "river":
        caps = (
            {"medium": 0.56, "strong": 0.56, "nuts": 0.76}
            if ctx.is_ip
            else {"medium": 0.48, "strong": 0.56, "nuts": 0.68}
        )
    elif street == "turn":
        caps = (
            {"medium": 0.68, "strong": 0.78, "nuts": 0.86}
            if ctx.is_ip
            else {"medium": 0.52, "strong": 0.62, "nuts": 0.74}
        )
    else:
        caps = (
            {"medium": 0.62, "strong": 0.72, "nuts": 0.82}
            if ctx.is_ip
            else {"medium": 0.45, "strong": 0.56, "nuts": 0.68}
        )
    return min(realization, caps.get(bucket, realization))


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
    pot = max(0.0, float(ctx.pot or 0.0))
    if pot <= 0:
        return 0.0

    street = str(ctx.street or "")
    if street == "river":
        realization = 1.00 if ctx.is_ip else 0.62
    elif street == "turn":
        realization = 0.78 if ctx.is_ip else 0.58
    else:
        realization = 0.70 if ctx.is_ip else 0.48

    bucket_adj = {
        "nuts": 0.10,
        "strong": 0.06,
        "medium": 0.00,
        "draw": -0.03,
        "weak_draw": -0.08,
        "weak": -0.16,
        "air": -0.22,
    }.get(ctx.hero_bucket or "", 0.0)
    realization += bucket_adj

    if ctx.num_opponents > 1:
        realization -= min(0.18, 0.06 * (ctx.num_opponents - 1))
    if ctx.board_sig.is_wet and ctx.hero_bucket in {"medium", "strong", "weak_draw", "draw"}:
        realization -= 0.05
    if 0 < float(ctx.spr or 0.0) <= 1.5 and ctx.hero_bucket in {"medium", "strong", "nuts"}:
        realization += 0.06

    realization = _value_opportunity_cap(ctx, realization)
    lo = 0.20 if ctx.hero_bucket in {"air", "weak", "weak_draw"} else 0.30
    realization = max(lo, min(1.0, realization))
    return eq * pot * realization
