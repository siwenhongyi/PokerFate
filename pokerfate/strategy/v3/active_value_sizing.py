"""Active value sizing optimizer.

Purpose triggers answer "should we value bet?".  This layer answers the next
question: "which price is most likely to get paid by worse?"
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

from pokerfate.strategy.v3.context import DecisionCtx


_ACTIVE_VALUE_PURPOSES = {
    'thick_value_bet',
    'monster_value_plan',
    'overbet_value',
}
_BASE_FRACS = (0.75, 1.00, 1.25, 1.50, 1.75, 2.00)


@dataclass
class ActiveValueSizeChoice:
    frac: float
    reason: str


def choose(
    ctx: DecisionCtx,
    purpose_id: str,
    base_frac: float,
) -> Optional[ActiveValueSizeChoice]:
    """Choose a value size by estimating incremental call EV.

    The EV score is intentionally simple and transparent:

        amount * (worse_call + 0.5 * tie_call - better_continue)

    The current pot is constant across bet sizes, so it is omitted from size
    comparison.  If no reliable strong-value context exists, return None and
    let the purpose's native sizer stand.
    """
    if (
        ctx.facing_bet
        or ctx.street not in {'flop', 'turn', 'river'}
        or purpose_id not in _ACTIVE_VALUE_PURPOSES
        or ctx.hero_bucket not in {'strong', 'nuts'}
        or ctx.pot <= 0
        or ctx.stack <= 0
    ):
        return None

    rel = _normalized_relation(ctx.villain_vs_hero_dist)
    rel_eq = rel.get('win', 0.0) + 0.5 * rel.get('tie', 0.0)
    if rel and rel_eq < 0.62:
        return None
    if not rel and ctx.equity_range < 0.68:
        return None

    fracs = _candidate_fracs(ctx, base_frac, purpose_id)
    if not fracs:
        return None

    scores = []
    for frac in fracs:
        score, meta = _score_frac(ctx, frac, rel)
        scores.append((frac, score, meta))
    if not scores:
        return None

    best_score = max(score for _frac, score, _meta in scores)
    mix_gap = max(ctx.big_blind, ctx.pot * 0.03)
    close = [
        (frac, score, meta)
        for frac, score, meta in scores
        if score >= best_score - mix_gap
    ]
    if not close:
        close = [max(scores, key=lambda item: item[1])]

    floor = min(score for _frac, score, _meta in close)
    weights = [max(1e-9, score - floor + ctx.big_blind) for _frac, score, _meta in close]
    total = sum(weights)
    r = ctx.rng.random() * total if total > 0 else 0.0
    acc = 0.0
    chosen = close[-1]
    for item, weight in zip(close, weights):
        acc += weight
        if r <= acc:
            chosen = item
            break

    frac, score, meta = chosen
    reason = (
        f"value_ev_size {base_frac:.2f}->{frac:.2f} "
        f"ev={score / max(ctx.big_blind, 1.0):.1f}bb "
        f"pay={meta['pay']:.0%} better={meta['better']:.0%} "
        f"decay={meta['decay']:.0%} r={meta['resistance']:.0%}"
    )
    return ActiveValueSizeChoice(frac=frac, reason=reason)


RiverValueSizeChoice = ActiveValueSizeChoice


def _candidate_fracs(
    ctx: DecisionCtx,
    base_frac: float,
    purpose_id: str,
) -> list[float]:
    values = set(_BASE_FRACS)
    if base_frac > 0:
        values.add(round(base_frac, 4))

    hi = 2.00
    out = []
    for frac in sorted(values):
        if frac < 0.75:
            continue
        if hi > 0 and frac > hi:
            continue
        amount = frac * ctx.pot
        if amount <= 0:
            continue
        if (
            purpose_id != 'overbet_value'
            and ctx.hero_bucket != 'nuts'
            and ctx.stack > 0
            and amount > ctx.stack * 0.60
        ):
            continue
        out.append(frac)
    return out


def _score_frac(
    ctx: DecisionCtx,
    frac: float,
    rel: Dict[str, float],
) -> tuple[float, Dict[str, float]]:
    amount = min(frac * ctx.pot, ctx.stack)
    dist = _normalized_bucket(ctx.villain_bucket_dist)
    pay_mass = _paying_mass(ctx, dist)
    sticky = _payment_scale(ctx)
    resistance = _resistance_scale(ctx)
    decay = _size_decay(frac, sticky, pay_mass, resistance)

    if rel:
        hero_win = rel.get('win', 0.0)
        tie = rel.get('tie', 0.0)
        hero_loss = rel.get('loss', 0.0)
    else:
        hero_win = max(0.0, min(1.0, ctx.equity_range))
        tie = 0.0
        hero_loss = max(0.0, 1.0 - hero_win)

    pay_cap = pay_mass * sticky * resistance
    worse_call = min(hero_win, pay_cap) * decay
    tie_call = min(tie, pay_cap * 0.75) * decay

    better_mass = dist.get('nuts', 0.0) + 0.65 * dist.get('strong', 0.0)
    if not dist:
        better_mass = hero_loss
    better_continue = min(hero_loss, better_mass)
    if frac >= 1.0:
        better_continue *= min(1.15, 1.0 + (frac - 1.0) * 0.20)
    else:
        better_continue *= 0.85
    if ctx.prev_bet_raised:
        better_continue *= 1.10
    elif ctx.prev_bet_called_count > 0:
        better_continue *= 1.04

    score = amount * (worse_call + 0.5 * tie_call - better_continue)
    return score, {
        'pay': min(1.0, pay_cap),
        'better': better_continue,
        'decay': decay,
        'resistance': resistance,
    }


def _normalized_relation(rel: Dict[str, float] | None) -> Dict[str, float]:
    raw = {
        'win': max(0.0, float((rel or {}).get('win', 0.0) or 0.0)),
        'tie': max(0.0, float((rel or {}).get('tie', 0.0) or 0.0)),
        'loss': max(0.0, float((rel or {}).get('loss', 0.0) or 0.0)),
    }
    total = sum(raw.values())
    if total <= 1e-12:
        return {}
    return {k: v / total for k, v in raw.items()}


def _normalized_bucket(dist: Dict[str, float] | None) -> Dict[str, float]:
    raw = {str(k): max(0.0, float(v or 0.0)) for k, v in (dist or {}).items()}
    total = sum(raw.values())
    if total <= 1e-12:
        return {}
    return {k: v / total for k, v in raw.items()}


def _paying_mass(ctx: DecisionCtx, dist: Dict[str, float]) -> float:
    if not dist:
        return 0.38 if ctx.hero_bucket == 'nuts' else 0.26
    pay = (
        0.95 * dist.get('nuts', 0.0)
        + 0.82 * dist.get('strong', 0.0)
        + 0.48 * dist.get('medium', 0.0)
        + 0.18 * dist.get('draw', 0.0)
        + 0.12 * dist.get('weak_draw', 0.0)
        + 0.04 * dist.get('air', 0.0)
    )
    if ctx.hero_bucket == 'nuts' and ctx.hero_hand_rank in {'flush', 'straight'}:
        pay += 0.10 * dist.get('strong', 0.0)
    return max(0.02, min(0.95, pay))


def _payment_scale(ctx: DecisionCtx) -> float:
    vs = ctx.villain_stats
    scale = 1.0
    scale += max(-0.10, min(0.35, (vs.vpip - 0.35) * 0.70))
    if vs.hands_seen >= 15:
        scale += max(-0.10, min(0.30, (vs.wtsd - 0.25) * 1.20))
        scale += max(-0.15, min(0.20, (1.4 - vs.af) * 0.12))
    if vs.fold_to_cbet_opps >= 5:
        scale += max(-0.20, min(0.25, (0.45 - vs.fold_to_cbet) * 0.55))
    if vs.river_action_count >= 5:
        scale += max(-0.25, min(0.30, (0.45 - vs.river_fold_rate) * 0.75))
    scale += min(0.25, ctx.n_sticky * 0.12)
    return max(0.55, min(1.75, scale))


def _resistance_scale(ctx: DecisionCtx) -> float:
    scale = 1.0
    if ctx.prev_bet_called_count > 0:
        scale += min(0.45, 0.16 * ctx.prev_bet_called_count)
    if ctx.prev_bet_raised:
        scale += 0.35
    if ctx.resistance_level > 0:
        scale += min(0.25, float(ctx.resistance_level) * 0.40)
    return max(0.85, min(1.90, scale))


def _size_decay(frac: float, sticky: float, pay_mass: float, resistance: float) -> float:
    points = (
        (0.75, 0.84),
        (1.00, 0.66),
        (1.25, 0.46),
        (1.50, 0.34),
        (1.75, 0.27),
        (2.00, 0.22),
    )
    base = points[-1][1]
    prev_f, prev_d = points[0]
    if frac <= prev_f:
        base = prev_d
    else:
        for f, d in points[1:]:
            if frac <= f:
                t = (frac - prev_f) / max(1e-9, f - prev_f)
                base = prev_d + (d - prev_d) * t
                break
            prev_f, prev_d = f, d

    if sticky > 1.0:
        base += (1.0 - base) * min(0.45, (sticky - 1.0) * 0.35)
    elif sticky < 1.0:
        base *= sticky
    if resistance > 1.0:
        base += (1.0 - base) * min(0.40, (resistance - 1.0) * 0.30)
    elif resistance < 1.0:
        base *= resistance

    if pay_mass < 0.35 and frac > 1.0:
        base *= 0.75
    if pay_mass < 0.22 and frac >= 1.25:
        base *= 0.80
    if resistance <= 1.0 and sticky < 1.0 and frac >= 1.50:
        base *= 0.70
    return max(0.05, min(1.0, base))
