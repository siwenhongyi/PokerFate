"""Counterfactual reaction and equity estimates for the EV decision layer."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pokerfate.strategy.v3 import bluff_context
from pokerfate.strategy.v3.context import DecisionCtx, VillainStats


_BUCKET_EQ_PRIOR = {
    "air": 0.86,
    "weak": 0.72,
    "weak_draw": 0.66,
    "draw": 0.58,
    "medium": 0.50,
    "strong": 0.30,
    "nuts": 0.08,
}
_HERO_MULT = {
    "air": 0.45,
    "weak": 0.70,
    "weak_draw": 0.78,
    "draw": 0.88,
    "medium": 1.00,
    "strong": 1.24,
    "nuts": 1.62,
}


@dataclass(frozen=True)
class ReactionEstimate:
    p_fold: float
    p_call_worse: float
    p_call_better: float
    p_raise: float
    eq_call: float
    eq_raise: float
    confidence: float
    source: str
    key: str
    sample_count: int = 0

    @property
    def p_call(self) -> float:
        return self.p_call_worse + self.p_call_better

    def as_dict(self) -> dict[str, Any]:
        return {
            "p_fold": round(self.p_fold, 4),
            "p_call_worse": round(self.p_call_worse, 4),
            "p_call_better": round(self.p_call_better, 4),
            "p_call": round(self.p_call, 4),
            "p_raise": round(self.p_raise, 4),
            "eq_call": round(self.eq_call, 4),
            "eq_raise": round(self.eq_raise, 4),
            "confidence": round(self.confidence, 4),
            "source": self.source,
            "key": self.key,
            "sample_count": self.sample_count,
        }


def clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, float(x)))


def size_bucket(frac: float) -> str:
    f = max(0.0, float(frac or 0.0))
    if f <= 0.30:
        return "small"
    if f <= 0.55:
        return "mid"
    if f <= 0.85:
        return "large"
    if f <= 1.20:
        return "pot"
    return "overbet"


def _wet_bucket(ctx: DecisionCtx) -> str:
    if ctx.board_sig.is_wet or ctx.board_sig.wetness >= 0.55:
        return "wet"
    if ctx.board_sig.is_dry or ctx.board_sig.wetness < 0.35:
        return "dry"
    return "neutral"


def _nopp_bucket(ctx: DecisionCtx) -> str:
    n = max(1, int(ctx.num_opponents or 1))
    if n <= 1:
        return "hu"
    if n == 2:
        return "2way"
    return "multi"


def _villain_bin(stats: VillainStats) -> str:
    if stats.hands_seen >= 5 and (stats.wtsd >= 0.34 or stats.fold_to_cbet <= 0.30 or stats.vpip >= 0.50):
        return "sticky"
    if stats.hands_seen >= 5 and (stats.fold_to_cbet >= 0.58 or stats.river_fold_rate >= 0.58):
        return "foldy"
    if stats.af < 1.2:
        return "passive"
    if stats.af >= 2.2:
        return "aggro"
    return "default"


def context_key(ctx: DecisionCtx, frac: float, action_kind: str) -> str:
    return "|".join([
        str(action_kind or "bet"),
        str(ctx.street or "flop"),
        size_bucket(frac),
        _nopp_bucket(ctx),
        "ip" if ctx.is_ip else "oop",
        "pfr" if ctx.is_pfr else "nopfr",
        _wet_bucket(ctx),
        _villain_bin(ctx.worst_villain_stats if ctx.num_opponents > 1 else ctx.villain_stats),
    ])


def _bayes(observed: float, n: int, prior: float, prior_weight: int = 12) -> float:
    n = max(0, int(n or 0))
    return (observed * n + prior * prior_weight) / max(1, n + prior_weight)


def _stat_fold_prior(ctx: DecisionCtx, action_kind: str) -> float:
    vs = ctx.worst_villain_stats if ctx.num_opponents > 1 and ctx.worst_villain_stats.hands_seen else ctx.villain_stats
    if ctx.street == "river" and (vs.river_action_count >= 5 or vs.river_fold_rate > 0):
        base = _bayes(vs.river_fold_rate, vs.river_action_count, 0.42, 8)
    elif vs.fold_to_cbet_opps >= 3 or vs.fold_to_cbet > 0:
        base = _bayes(vs.fold_to_cbet, vs.fold_to_cbet_opps, 0.42, 10)
    else:
        base = 0.42
    if action_kind == "raise":
        base *= 0.55
    if ctx.num_opponents > 1:
        base *= max(0.55, 1.0 - 0.15 * (ctx.num_opponents - 1))
    if ctx.prev_bet_called_count:
        base *= max(0.45, 1.0 - 0.18 * ctx.prev_bet_called_count)
    if ctx.prev_bet_raised:
        base *= 0.55
    if ctx.board_sig.is_dry:
        base *= 1.08
    if ctx.board_sig.is_wet:
        base *= 0.82
    return clamp(base, 0.03, 0.90)


def _raise_prior(ctx: DecisionCtx, frac: float) -> float:
    dist = ctx.villain_bucket_dist or {}
    strong = float(dist.get("strong", 0.0) or 0.0)
    nuts = float(dist.get("nuts", 0.0) or 0.0)
    base = nuts + 0.35 * strong
    vs = ctx.worst_villain_stats if ctx.num_opponents > 1 and ctx.worst_villain_stats.hands_seen else ctx.villain_stats
    if vs.af >= 2.0:
        base += 0.05
    if vs.af < 1.2:
        base -= 0.03
    if ctx.board_sig.is_wet:
        base += 0.03
    if frac >= 1.0:
        base *= 0.8
    if ctx.blockers.nut_flush_blocker or ctx.blockers.straight_blocker:
        base *= 0.82
    return clamp(base, 0.02, 0.55)


def _equity_vs_dist(ctx: DecisionCtx, filtered: dict[str, float]) -> float:
    total = sum(max(0.0, float(v or 0.0)) for v in filtered.values())
    if total <= 0:
        return float(ctx.equity_range or ctx.equity_mc or 0.0)
    eq = 0.0
    mult = _HERO_MULT.get(ctx.hero_bucket or "medium", 1.0)
    for bucket, weight in filtered.items():
        eq += (max(0.0, float(weight or 0.0)) / total) * _BUCKET_EQ_PRIOR.get(bucket, 0.50) * mult
    return clamp(eq, 0.02, 0.98)


def equity_vs_calling_range(ctx: DecisionCtx, frac: float) -> float:
    dist = ctx.villain_bucket_dist or {}
    if not dist:
        return clamp(ctx.equity_range or ctx.equity_mc or 0.0, 0.02, 0.98)
    rank = {"air": 0, "weak": 1, "weak_draw": 1, "draw": 2, "medium": 3, "strong": 4, "nuts": 5}
    cutoff = 1 if frac <= 0.35 else 2 if frac <= 0.75 else 3
    filtered = {k: v for k, v in dist.items() if rank.get(k, 3) >= cutoff}
    prior_full = _equity_vs_dist(ctx, dist)
    prior_filtered = _equity_vs_dist(ctx, filtered)
    shift = prior_filtered - prior_full
    return clamp(float(ctx.equity_range or 0.0) + shift, 0.02, 0.98)


def equity_vs_raising_range(ctx: DecisionCtx, frac: float) -> float:
    dist = ctx.villain_bucket_dist or {}
    if not dist:
        return clamp((ctx.equity_range or ctx.equity_mc or 0.0) * 0.55, 0.02, 0.98)
    filtered = {k: v for k, v in dist.items() if k in {"strong", "nuts"}}
    prior_full = _equity_vs_dist(ctx, dist)
    prior_filtered = _equity_vs_dist(ctx, filtered)
    blocker_lift = 0.04 * ctx.blockers.count()
    return clamp(float(ctx.equity_range or 0.0) + (prior_filtered - prior_full) + blocker_lift, 0.02, 0.98)


def effective_equity(ctx: DecisionCtx, *, conservative: bool = False) -> tuple[float, str, float]:
    rel = ctx.villain_vs_hero_dist or {}
    if ctx.street == "river" and rel:
        eq = float(rel.get("win", 0.0) or 0.0) + 0.5 * float(rel.get("tie", 0.0) or 0.0)
        return clamp(eq), "rel_dist", 1.0
    range_eq = float(ctx.equity_range or 0.0)
    mc_eq = float(ctx.equity_mc or range_eq)
    uncertainty = float(ctx.equity_uncertainty or 0.0)
    div = abs(mc_eq - range_eq)
    if conservative:
        return clamp(min(range_eq, mc_eq) - uncertainty), "conservative", max(0.2, 1.0 - div)
    if div <= 0.08:
        return clamp(range_eq), "range", 1.0 - div
    alpha = clamp(1.0 - (div - 0.08) / 0.25, 0.35, 1.0)
    eq = alpha * range_eq + (1.0 - alpha) * mc_eq
    return clamp(eq), f"blend:{alpha:.2f}", max(0.2, 1.0 - div)


def reaction_estimate(ctx: DecisionCtx, frac: float, action_kind: str = "bet") -> ReactionEstimate:
    source = "prior"
    sample_count = 0
    confidence = 0.35
    p_fold = _stat_fold_prior(ctx, action_kind)
    p_raise = _raise_prior(ctx, frac)
    p_fold = clamp(p_fold)
    p_raise = clamp(min(p_raise, 1.0 - p_fold))
    p_call = max(0.0, 1.0 - p_fold - p_raise)
    eq_call = equity_vs_calling_range(ctx, frac)
    eq_raise = equity_vs_raising_range(ctx, frac)
    better_share = clamp(1.0 - eq_call)
    if ctx.hero_bucket == "nuts":
        better_share *= 0.20
    elif ctx.hero_bucket == "strong":
        better_share *= 0.70
    elif ctx.hero_bucket in {"air", "weak", "weak_draw"}:
        better_share = max(better_share, 0.75)
    p_call_better = p_call * better_share
    p_call_worse = p_call - p_call_better
    return ReactionEstimate(
        p_fold=p_fold,
        p_call_worse=p_call_worse,
        p_call_better=p_call_better,
        p_raise=p_raise,
        eq_call=eq_call,
        eq_raise=eq_raise,
        confidence=confidence,
        source=source,
        key=context_key(ctx, frac, action_kind),
        sample_count=sample_count,
    )


def bluff_score(ctx: DecisionCtx) -> float:
    try:
        return float(bluff_context.evaluate(ctx).score)
    except Exception:
        return 0.35
