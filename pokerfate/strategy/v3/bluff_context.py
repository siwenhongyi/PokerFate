"""Shared bluff-context scoring for postflop purposes.

The score answers one narrow question: is this a good range spot to make
villain fold, given his current bucket distribution and observed fold habits?
It is not a replacement for equity gates; semi-bluffs still need live equity
and river bluffs still need blockers.
"""

from __future__ import annotations

from dataclasses import dataclass

from pokerfate.strategy.v3.context import DecisionCtx


@dataclass(frozen=True)
class BluffContext:
    score: float
    bucket_score: float
    fold_score: float
    blocker_score: float
    story_score: float
    showdown_penalty: float
    risk_penalty: float
    air_weak: float
    draw: float
    medium: float
    strong: float
    nuts: float
    strong_nuts: float
    rel_win: float
    rel_loss: float
    rel_eq: float
    fold_signal: float


def _clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def _bucket(ctx: DecisionCtx, name: str) -> float:
    return float((ctx.villain_bucket_dist or {}).get(name, 0.0) or 0.0)


def _relative(ctx: DecisionCtx) -> tuple[float, float, float]:
    rel = ctx.villain_vs_hero_dist or {}
    win = float(rel.get('win', 0.0) or 0.0)
    tie = float(rel.get('tie', 0.0) or 0.0)
    loss = float(rel.get('loss', 0.0) or 0.0)
    return win, loss, win + 0.5 * tie


def blocker_score(ctx: DecisionCtx) -> float:
    score = 0.0
    if ctx.blockers.nut_flush_blocker:
        score += 0.50
    if ctx.blockers.straight_blocker:
        score += 0.38
    if ctx.blockers.set_blocker:
        score += 0.18
    return _clamp(score)


def _fold_score(ctx: DecisionCtx) -> tuple[float, float]:
    vs = ctx.villain_stats
    signals: list[float] = []
    if vs.fold_to_cbet_opps >= 5:
        signals.append(_clamp((vs.fold_to_cbet - 0.25) / 0.45))
    if ctx.street == 'river' and (vs.river_action_count >= 5 or vs.river_fold_rate > 0.50):
        signals.append(_clamp((vs.river_fold_rate - 0.25) / 0.45))
    if not signals:
        return 0.35, 0.0
    signal = sum(signals) / len(signals)
    return signal, signal


def _story_score(ctx: DecisionCtx) -> float:
    score = 0.0
    if ctx.num_opponents == 1:
        score += 0.15
    if ctx.is_ip:
        score += 0.08
    if ctx.is_pfr:
        score += 0.12
    if ctx.flop_checked_through and ctx.street in ('turn', 'river'):
        score += 0.18
    prev = {'turn': 'flop', 'river': 'turn'}.get(ctx.street)
    if prev and ctx.opp_prev_actions.get(prev) == 'check':
        score += 0.14
    if ctx.street == 'turn' and ctx.board_sig.high_card_rank >= 12:
        score += 0.10
    if ctx.street == 'river' and ctx.my_prev_actions.get('turn') == 'bet':
        score += 0.08
    return _clamp(score)


def evaluate(ctx: DecisionCtx) -> BluffContext:
    air = _bucket(ctx, 'air')
    weak = _bucket(ctx, 'weak_draw')
    draw = _bucket(ctx, 'draw')
    medium = _bucket(ctx, 'medium')
    strong = _bucket(ctx, 'strong')
    nuts = _bucket(ctx, 'nuts')
    strong_nuts = strong + nuts
    air_weak = air + weak

    fold_score, fold_signal = _fold_score(ctx)
    rel_win, rel_loss, rel_eq = _relative(ctx)
    b_score = blocker_score(ctx)
    story = _story_score(ctx)

    medium_attack = medium * (0.65 if fold_score >= 0.55 else 0.20)
    bucket_score = _clamp(
        0.95 * air
        + 0.75 * weak
        + 0.55 * draw
        + medium_attack
        - 0.70 * strong
        - 1.15 * nuts
    )

    showdown_penalty = 0.0
    if ctx.villain_vs_hero_dist:
        showdown_penalty += 0.55 * rel_eq
        showdown_penalty -= 0.20 * rel_loss
    elif ctx.hero_bucket in ('medium', 'strong', 'nuts'):
        showdown_penalty += 0.45
    elif ctx.hero_bucket == 'draw':
        showdown_penalty += 0.10

    risk_penalty = 0.0
    if ctx.num_opponents >= 2:
        risk_penalty += 0.18 + 0.06 * min(2, ctx.num_opponents - 2)
    if strong_nuts >= 0.55:
        risk_penalty += 0.12
    if nuts >= 0.25:
        risk_penalty += 0.18
    if ctx.prev_bet_called_count > 0:
        risk_penalty += min(0.18, 0.06 * ctx.prev_bet_called_count)
    if ctx.prev_bet_raised:
        risk_penalty += 0.16
    if ctx.n_sticky >= 1:
        risk_penalty += min(0.18, 0.07 * ctx.n_sticky)

    score = _clamp(
        0.28 * fold_score
        + 0.30 * bucket_score
        + 0.18 * b_score
        + 0.18 * story
        - 0.22 * _clamp(showdown_penalty)
        - 0.24 * _clamp(risk_penalty)
    )

    return BluffContext(
        score=score,
        bucket_score=bucket_score,
        fold_score=fold_score,
        blocker_score=b_score,
        story_score=story,
        showdown_penalty=_clamp(showdown_penalty),
        risk_penalty=_clamp(risk_penalty),
        air_weak=air_weak,
        draw=draw,
        medium=medium,
        strong=strong,
        nuts=nuts,
        strong_nuts=strong_nuts,
        rel_win=rel_win,
        rel_loss=rel_loss,
        rel_eq=rel_eq,
        fold_signal=fold_signal,
    )


def describe(ctx: DecisionCtx) -> str:
    b = evaluate(ctx)
    return (
        f"BLF s={b.score:.2f} b=A{b.air_weak:.2f}/D{b.draw:.2f}/"
        f"M{b.medium:.2f}/S{b.strong:.2f}/N{b.nuts:.2f} "
        f"rel=W{b.rel_win:.2f}/L{b.rel_loss:.2f} "
        f"fe={b.fold_signal:.2f} blk={b.blocker_score:.2f}"
    )
