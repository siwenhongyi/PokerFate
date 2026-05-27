"""Draw quality helpers shared by v3 purpose gates."""

from __future__ import annotations

from pokerfate.strategy.v3.context import DecisionCtx


def strong_draw(ctx: DecisionCtx) -> bool:
    d = ctx.draw
    return bool(
        d.flush_draw
        or d.oesd
        or (d.gutshot and d.overcards and ctx.equity_range >= 0.28)
    )


def premium_draw(ctx: DecisionCtx) -> bool:
    d = ctx.draw
    return bool(
        (d.flush_draw and d.oesd)
        or (d.flush_draw and d.overcards)
        or (d.oesd and d.overcards)
        or (d.flush_draw and ctx.blockers.nut_flush_blocker)
        or (
            d.gutshot
            and d.overcards
            and ctx.blockers.straight_blocker
            and ctx.equity_range >= 0.32
        )
    )


def weak_draw_semibluff_quality_ok(ctx: DecisionCtx) -> bool:
    d = ctx.draw
    if d.gutshot and d.overcards:
        return True
    if d.backdoor_flush and d.overcards:
        return ctx.is_ip and ctx.num_opponents == 1 and ctx.is_pfr
    return False


def premium_draw_stackoff_ok(ctx: DecisionCtx) -> bool:
    if not premium_draw(ctx):
        return False
    if ctx.street not in {'flop', 'turn'}:
        return False
    equity = max(float(ctx.equity_range or 0.0), float(ctx.equity_mc or 0.0) - 0.03)
    if equity < 0.40:
        return False
    d = ctx.draw
    if ctx.board_sig.paired and not (d.flush_draw and d.oesd):
        return False
    if (
        (ctx.board_sig.flush_possible or ctx.board_sig.straight_possible)
        and not (
            ctx.blockers.nut_flush_blocker
            or ctx.blockers.straight_blocker
            or (d.flush_draw and d.oesd)
        )
    ):
        return False
    return True
