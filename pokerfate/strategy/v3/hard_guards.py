"""Hard action deletion rules for the EV decision layer."""

from __future__ import annotations

from pokerfate.strategy.v3.candidates import ActionCandidate
from pokerfate.strategy.v3.context import DecisionCtx
from pokerfate.strategy.v3.exploit import no_fold_equity

_NON_NUT_DANGER_SUBTYPES = {
    "board_pair_hero_pair", "board_pair_kicker", "board_two_pair",
    "trips_weak_kicker", "clean_two_pair", "two_pair", "overpair", "pair",
}


def reasons(ctx: DecisionCtx, cand: ActionCandidate) -> list[str]:
    out: list[str] = []
    action = cand.action
    if action in {"check", "fold"}:
        return out
    if action == "bet" and cand.amount <= 0:
        out.append("zero_bet")
    if action == "raise" and cand.amount <= max(ctx.to_call, 0.0):
        out.append("illegal_raise")
    if action in {"bet", "raise"}:
        if no_fold_equity(ctx) and ctx.hero_bucket in {"air", "weak", "weak_draw"} and not (ctx.draw.flush_draw or ctx.draw.oesd or ctx.blockers.count()):
            out.append("no_fe_air")
        if ctx.num_opponents >= 3 and ctx.hero_bucket in {"air", "weak", "weak_draw"} and ctx.board_sig.is_wet:
            out.append("multiway_wet_air")
        if ctx.street == "river" and ctx.hero_bucket in {"air", "weak", "weak_draw", "draw"} and cand.frac >= 0.75 and ctx.blockers.count() == 0:
            out.append("river_no_blocker_bluff")
        if action == "raise" and ctx.hero_bucket != "nuts" and (ctx.board_sig.flush_possible or ctx.board_sig.straight_possible) and not (ctx.blockers.nut_flush_blocker or ctx.blockers.straight_blocker) and ctx.hero_hand_rank not in {"flush", "full_house", "four_of_a_kind", "straight_flush"}:
            out.append("non_nut_completed_draw_raise")
        if (cand.jammed or (ctx.stack > 0 and cand.amount / ctx.stack >= 0.70)) and ctx.hero_bucket != "nuts":
            if ctx.spr <= 2.0 or ctx.board_sig.flush_possible or ctx.board_sig.straight_possible or ctx.board_sig.paired:
                if (ctx.hero_made_subtype or "") in _NON_NUT_DANGER_SUBTYPES or ctx.hero_bucket in {"medium", "strong", "draw", "weak_draw"}:
                    out.append("non_nut_stackoff")
        if ctx.prev_bet_raised and ctx.hero_bucket in {"air", "weak", "weak_draw"}:
            out.append("raised_line_no_air")
    if action == "call":
        if ctx.to_call >= ctx.stack and ctx.hero_bucket in {"air", "weak"}:
            out.append("allin_weak_call")
        if ctx.street == "river" and ctx.facing_large_bet and ctx.hero_bucket == "medium" and ctx.board_sig.is_wet:
            out.append("river_large_bet_medium_wet")
        if ctx.hero_bucket in {"medium", "strong"} and ctx.street == "river" and ctx.villain_vs_hero_dist:
            rel_eq = float(ctx.villain_vs_hero_dist.get("win", 0.0) or 0.0) + 0.5 * float(ctx.villain_vs_hero_dist.get("tie", 0.0) or 0.0)
            if ctx.pot_odds >= 0.35 and rel_eq < ctx.pot_odds + 0.08:
                out.append("fragile_rel_eq")
        if ctx.hero_bucket in {"medium", "strong"} and ctx.villain_bucket_dist:
            strong_mass = float(ctx.villain_bucket_dist.get("strong", 0.0) or 0.0) + float(ctx.villain_bucket_dist.get("nuts", 0.0) or 0.0)
            stack_commit = ctx.to_call / max(ctx.stack or 1.0, 1.0)
            if strong_mass >= 0.65 and (ctx.villain_stats.af < 1.0 or stack_commit >= 0.25):
                out.append("passive_value_bet_dominates")
            if ctx.hero_bucket == "medium" and ctx.pot_odds >= 0.22 and strong_mass >= 0.20 and ctx.villain_stats.af < 1.2:
                clear_edge = max(float(ctx.equity_range or 0.0), float(ctx.equity_mc or 0.0) - 0.08) >= ctx.pot_odds + 0.08
                if not (ctx.spr <= 1.0 and clear_edge):
                    out.append("fold_dominant_call")
    return out


def allowed(ctx: DecisionCtx, cand: ActionCandidate) -> tuple[bool, list[str]]:
    rs = reasons(ctx, cand)
    return not rs, rs
