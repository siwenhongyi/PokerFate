"""V3 purpose-first postflop decision engine."""

from __future__ import annotations

import os
import struct
from dataclasses import dataclass, field, replace
from typing import Any, Dict, List, Optional, Tuple

from pokerfate.strategy.v3 import active_value_sizing, alpha_gate, calibrator, ev_scorer, exploit
from pokerfate.strategy.v3.candidates import ActionCandidate
from pokerfate.strategy.v3.context import DecisionCtx
from pokerfate.strategy.v3.purpose import Purpose
from pokerfate.strategy.v3.purposes_active import all_active, monster_value_plan_kind
from pokerfate.strategy.v3.purposes_defensive import all_defensive
from pokerfate.strategy.v3.purposes_passive import all_passive
from pokerfate.strategy.v3.stackoff_guard import stackoff_guard_reason


_VOTE_BASELINE_THRESH = 0.6
_VOTE_LEVERAGE_TOP_GAP = 0.18
_VOTE_LEVERAGE_MIN_TOP = 0.48
_VOTE_LEVERAGE_DETERMINISTIC = os.environ.get("PF_V3_VOTE_LEVERAGE_DETERMINISTIC", "1").lower() not in {
    "0", "false", "no", "off"
}
# EV veto: the purpose vote picks WHAT to do (and keeps the strategy mixed);
# the EV layer (ev_scorer / counterfactual / risk_model) then prices the
# chosen bet, raise or call against doing nothing. Rake, fold equity that
# must be collected from every live opponent, pot odds and the risk premiums
# only enter the decision here. The veto is one-directional: it can turn a
# bet into a check or a call into a fold, never the reverse, so it removes
# aggression that is paid for by fold equity the pool does not give (flop:
# 32% fold heads-up, ~23% for two opponents) without touching value bets with
# strong/nuts hands. PF_V3_EV_VETO=0 disables it for A/B replays.
#
# The opposite direction (fold -> call, "ev_promote") was deleted on
# 2026-11-18. It let this formula overrule a fold of the purpose vote, and
# over 15,187 human-table hands those 146 calls made -260bb against folding
# (-1.8 +/- 4.2 each) while the 231 calls the vote chose itself made +2,235bb
# (+9.7 +/- 4.8). The hands the vote rejects realised 18.5% of the pot share
# where the formula estimated 43.5% (flop); a bigger estimated edge did not
# earn more, and the "committed, low SPR" rescues it was written for were its
# worst cases (12 calls, 3 of 11 showdowns won, -267bb). The formula prices a
# call as if it bought a showdown and has none of what the triggers know
# (made-hand subtype, the opponent's line, texture), so an override that only
# acts where the two disagree collects the formula's own errors. Facing a
# bet the vote alone decides call or fold; all-in calls keep their price rule
# in ``_decide_all_in``. Evidence: the rule engine audit of 2026-11-17.
_EV_VETO_ENABLED = os.environ.get("PF_V3_EV_VETO", "1").lower() not in {
    "0", "false", "no", "off"
}
_EV_VETO_EXEMPT_BUCKETS = {"strong", "nuts"}
# A bet whose equity beats the average share 1/(n+1) by this edge is value /
# protection, not a bluff: it is not paid for by fold equity, so it is not
# priced by the veto (the one-caller EV model understates multiway value).
_EV_VETO_VALUE_EDGE = 0.08
_BET_FOLD_BUDGET_PURPOSES = {
    "default_stab",
    "thick_value_bet",
    "range_cbet",
    "profit_flop_cbet",
    "profit_delayed_probe",
}
_BET_FOLD_BUDGET_FRAGILE_SUBTYPES = {
    "pocket_pair",
    "top_pair_weak_kicker",
    "board_pair_kicker",
    "board_pair_hero_pair",
    "board_pair_pocket_underpair",
    "board_two_pair",
    "trips_weak_kicker",
    "board_trips_kicker",
}
_BET_FOLD_BUDGET_MAX_FRAC = 0.33
_BET_FOLD_BUDGET_SPR = 3.0
_STICKY_MULTIWAY_MEDIUM_MAX_FRAC = 0.60


@dataclass
class DecisionOutput:
    action: str = "check"
    amount: float = 0.0
    purpose: str = ""
    frac: float = 0.0
    seed: int = 0
    candidates: List[Tuple[str, float]] = field(default_factory=list)
    alpha: Optional[Any] = None
    exploit_deltas: Dict[str, float] = field(default_factory=dict)
    jammed: bool = False
    downgraded_to_check: bool = False
    reason: str = ""
    arbitration_mode: str = "argmax"
    top_gap: float = 0.0
    leverage_flags: List[str] = field(default_factory=list)
    decision_trace: Dict[str, Any] = field(default_factory=dict)


class V3Engine:
    """Purpose injection + weighted purpose-vote postflop decision engine."""

    def __init__(self) -> None:
        self.active_purposes = [
            p for p in all_active() + all_passive()
            if not p.facing_bet and p.default_action != "fold"
        ]
        self.defensive_purposes = [p for p in all_defensive()]

    def _fresh_seed(self, ctx: DecisionCtx) -> int:
        seed = int(ctx.seed or 0)
        if seed <= 0:
            seed = struct.unpack(">I", os.urandom(4))[0]
        ctx.rng.seed(seed)
        ctx.seed = seed
        return seed

    def _leverage_flags(self, ctx: DecisionCtx) -> List[str]:
        flags: list[str] = []
        if ctx.street == "river":
            flags.append("river")
        if ctx.spr > 0 and ctx.spr <= 1.5:
            flags.append("low_spr")
        bet_ratio = (ctx.to_call / max(ctx.pot, 1.0)) if ctx.facing_bet else 0.0
        if bet_ratio >= 0.75:
            flags.append("large_bet")
        if ctx.stack > 0 and ctx.to_call / ctx.stack >= 0.35:
            flags.append("stack_commit")
        if ctx.big_blind > 0 and ctx.pot / ctx.big_blind >= 40:
            flags.append("large_pot")
        if ctx.facing_large_bet:
            flags.append("facing_large_bet")
        return flags

    def decide(self, ctx: DecisionCtx) -> DecisionOutput:
        seed = self._fresh_seed(ctx)
        if ctx.facing_bet and ctx.to_call >= ctx.stack:
            return self._decide_all_in(ctx, seed)
        raw = self._defensive_candidates(ctx) if ctx.facing_bet else self._active_candidates(ctx)
        return self._decide_by_vote(ctx, seed, raw)

    def _decide_all_in(self, ctx: DecisionCtx, seed: int) -> DecisionOutput:
        blended_eq = self._legacy_blended_eq(ctx)
        flags = self._leverage_flags(ctx) or ["all_in"]
        behind_note = (
            f" behind_eq={ctx.equity_when_behind:.2f}"
            if ctx.equity_when_behind is not None else ""
        )
        if blended_eq >= ctx.pot_odds:
            return DecisionOutput(
                action="call",
                amount=min(ctx.to_call, ctx.stack),
                purpose="bluff_catch_call",
                seed=seed,
                arbitration_mode="deterministic",
                top_gap=1.0,
                leverage_flags=flags,
                reason=(
                    f"all-in robust call blended_eq={blended_eq:.2f} "
                    f">= pot_odds={ctx.pot_odds:.2f}{behind_note}"
                ),
            )
        return DecisionOutput(
            action="fold",
            amount=0.0,
            purpose="fold",
            seed=seed,
            arbitration_mode="deterministic",
            top_gap=1.0,
            leverage_flags=flags,
            reason=(
                f"all-in robust fold blended_eq={blended_eq:.2f} "
                f"< pot_odds={ctx.pot_odds:.2f}{behind_note}"
            ),
        )

    def _decide_by_vote(
        self,
        ctx: DecisionCtx,
        seed: int,
        candidates: list[ActionCandidate],
    ) -> DecisionOutput:
        chosen, probs, gap, mode = (
            self._vote_select_defensive(ctx, candidates)
            if ctx.facing_bet
            else self._vote_select_active(ctx, candidates)
        )
        blocked: list[dict[str, Any]] = []
        alpha_checks: list[dict[str, Any]] = []
        blocked_alpha = None
        stackoff_guard = self._selected_stackoff_guard(ctx, chosen)
        if stackoff_guard:
            blocked.append({
                "label": chosen.label,
                "purpose": chosen.purpose,
                "reasons": [f"stackoff_guard:{stackoff_guard}"],
            })
            if ctx.facing_bet and chosen.action == "raise":
                chosen = ActionCandidate(
                    chosen.label,
                    "call",
                    min(ctx.to_call, ctx.stack),
                    0.0,
                    chosen.purpose,
                    "fallback",
                    jammed=ctx.to_call >= ctx.stack,
                )
                mode = mode + "_stackoff_call"
            else:
                chosen = ActionCandidate(
                    chosen.label,
                    "check",
                    0.0,
                    0.0,
                    chosen.purpose,
                    "fallback",
                    metadata={"block_reason": f"stackoff_guard {stackoff_guard}"},
                )
                mode = mode + "_stackoff_check"
        chosen_alpha = self._alpha_for_candidate(ctx, chosen)
        if chosen_alpha is not None and not chosen_alpha.passed and chosen_alpha.direction == "over_bluff":
            smaller = self._alpha_downsize_candidate(ctx, candidates, chosen)
            if smaller is not None:
                chosen = smaller
                mode = mode + "_alpha_downsize"
                chosen_alpha = self._alpha_for_candidate(ctx, chosen)
        if chosen_alpha is not None:
            summary = self._alpha_summary(chosen_alpha)
            alpha_checks.append({"label": chosen.label, "purpose": chosen.purpose, **summary})
            if not chosen_alpha.passed and chosen_alpha.direction == "over_bluff":
                blocked_alpha = chosen_alpha
                blocked.append({
                    "label": chosen.label,
                    "purpose": chosen.purpose,
                    "reasons": ["alpha_over_bluff"],
                    "alpha": summary,
                })
                chosen = ActionCandidate(
                    chosen.label,
                    "check",
                    0.0,
                    0.0,
                    chosen.purpose,
                    "fallback",
                    metadata={"block_reason": "alpha_over_bluff"},
                )
                mode = mode + "_alpha"
                chosen_alpha = None
        if _EV_VETO_ENABLED:
            veto = self._ev_veto(ctx, chosen)
            if veto is not None:
                replacement, detail = veto
                blocked.append({
                    "label": chosen.label,
                    "purpose": chosen.purpose,
                    "reasons": ["ev_veto"],
                    "ev": detail,
                })
                chosen = replacement
                mode = mode + "_ev_veto"
                chosen_alpha = None
        alpha_out = chosen_alpha if chosen_alpha is not None and chosen_alpha.direction != "under_bluff" else blocked_alpha
        trace = {
            "candidates": [self._vote_summary(ctx, c) for c in candidates],
            "blocked": blocked,
            "alpha": alpha_checks,
            "mode": mode,
        }
        flags = self._leverage_flags(ctx)
        return DecisionOutput(
            action=chosen.action,
            amount=chosen.amount,
            purpose=chosen.purpose,
            frac=chosen.frac,
            seed=seed,
            candidates=probs,
            exploit_deltas=self._exploit_deltas(candidates),
            jammed=chosen.jammed,
            downgraded_to_check=(
                chosen.action in {"check", "fold"}
                and any(c.action in {"bet", "raise", "call"} and c.action != chosen.action for c in candidates)
            ),
            arbitration_mode=mode,
            top_gap=gap,
            leverage_flags=flags,
            reason=self._vote_reason(ctx, chosen, mode),
            alpha=alpha_out,
            decision_trace=trace,
        )

    def _ev_veto(
        self,
        ctx: DecisionCtx,
        chosen: ActionCandidate,
    ) -> tuple[ActionCandidate, dict[str, Any]] | None:
        """Price the vote's bet/raise/call against the passive alternatives.

        Returns ``(replacement, detail)`` when the EV layer prefers check /
        call / fold over ``chosen`` by its robust margin, else ``None``.
        Value bets with strong/nuts hands are exempt (they are not priced on
        fold equity) and all-in spots are decided elsewhere.
        """
        if chosen.action not in {"bet", "raise", "call"}:
            return None
        if chosen.action in {"bet", "raise"}:
            if ctx.hero_bucket in _EV_VETO_EXEMPT_BUCKETS:
                return None
            share = 1.0 / (max(1, int(ctx.num_opponents or 1)) + 1)
            if float(ctx.equity_range or 0.0) >= share + _EV_VETO_VALUE_EDGE:
                return None
        if ctx.facing_bet and ctx.to_call >= ctx.stack:
            return None
        if ctx.facing_bet:
            alternatives = [ActionCandidate("fold", "fold", 0.0, 0.0, "fold", "fallback")]
            if chosen.action == "raise":
                alternatives.insert(0, ActionCandidate(
                    "call", "call", min(ctx.to_call, ctx.stack), 0.0, "call", "fallback",
                    jammed=ctx.to_call >= ctx.stack,
                ))
        else:
            alternatives = [ActionCandidate("check", "check", 0.0, 0.0, "default_check", "fallback")]
        # Blended (not pessimistic) equity: the veto removes clear losers, it
        # does not re-rank close spots the vote already weighed. The risk
        # premium inside each score is the only margin.
        scored = [ev_scorer.score(ctx, c, conservative=False, range_only=True) for c in [chosen] + alternatives]
        top = max(scored, key=lambda sc: sc.ev)
        gap = scored[0].ev - top.ev
        how = "ev_loss"
        detail = {
            "selected": top.action,
            "mode": how,
            "gap": round(float(gap), 2),
            "candidates": [
                {
                    "action": sc.action,
                    "amount": round(float(sc.amount), 1),
                    "ev": round(float(sc.ev), 2),
                    "raw_ev": round(float(sc.raw_ev), 2),
                    "risk": round(float(sc.risk), 2),
                    "margin": round(float(sc.margin), 2),
                    "reason": sc.reason,
                }
                for sc in scored
            ],
        }
        if top.action == chosen.action:
            return None
        replacement = next(alt for alt in alternatives if alt.action == top.action)
        chosen_sc = scored[0]
        replacement = replace(replacement, metadata={
            "block_reason": (
                f"ev_veto {chosen.label} ev={chosen_sc.ev:.1f} "
                f"< {top.action} ev={top.ev:.1f} ({how})"
            ),
            "ev_veto": detail,
        })
        return replacement, detail

    @staticmethod
    def _selected_stackoff_guard(ctx: DecisionCtx, cand: ActionCandidate) -> str:
        if cand.action not in {"bet", "raise"}:
            return ""
        will_jam = cand.jammed
        if cand.action == "raise" and ctx.stack > 0:
            will_jam = will_jam or cand.amount >= ctx.stack * 0.85
        return stackoff_guard_reason(ctx, cand.purpose, will_jam=will_jam) or ""

    def _alpha_downsize_candidate(
        self,
        ctx: DecisionCtx,
        candidates: list[ActionCandidate],
        chosen: ActionCandidate,
    ) -> ActionCandidate | None:
        smaller = sorted(
            (
                c for c in candidates
                if c.action == "bet"
                and c.purpose == chosen.purpose
                and 0 < c.frac < chosen.frac
            ),
            key=lambda c: c.frac,
        )
        for cand in smaller[:2]:
            alpha = self._alpha_for_candidate(ctx, cand)
            if alpha is None or alpha.passed or alpha.direction != "over_bluff":
                return cand
        return None

    @staticmethod
    def _exploit_weight(ctx: DecisionCtx, purpose_id: str) -> float:
        if not purpose_id:
            return 1.0
        return max(0.0, float(exploit.weight_for(purpose_id, ctx)))

    @staticmethod
    def _effective_weight(trigger_weight: float, exploit_weight: float) -> float:
        return max(0.0, float(trigger_weight or 0.0) * float(exploit_weight or 0.0))

    @staticmethod
    def _exploit_deltas(candidates: list[ActionCandidate]) -> Dict[str, float]:
        out: Dict[str, float] = {}
        for cand in candidates:
            meta = cand.metadata or {}
            if "exploit_weight" not in meta or not cand.purpose:
                continue
            out[cand.purpose] = round(float(meta.get("exploit_weight") or 1.0), 4)
        return out

    @staticmethod
    def _alpha_summary(alpha) -> dict[str, Any]:
        return {
            "passed": bool(alpha.passed),
            "direction": str(alpha.direction or "ok"),
            "target": round(float(alpha.target or 0.0), 4),
            "hero_bluff_share": round(float(alpha.hero_bluff_share or 0.0), 4),
        }

    @staticmethod
    def _alpha_for_candidate(ctx: DecisionCtx, cand: ActionCandidate):
        if cand.action != "bet" or cand.frac <= 0:
            return None
        alpha = alpha_gate.check(ctx, cand.frac, cand.purpose)
        return alpha if float(alpha.target or 0.0) > 0 else None

    def _vote_select_active(self, ctx: DecisionCtx, candidates: list[ActionCandidate]):
        bet_groups: dict[str, list[ActionCandidate]] = {}
        check_by_purpose: dict[str, ActionCandidate] = {}
        purpose_weights: dict[str, float] = {}
        for cand in candidates:
            weight = self._vote_weight(cand)
            if weight <= 0:
                continue
            if cand.action == "bet":
                bet_groups.setdefault(cand.purpose, []).append(cand)
            elif cand.action == "check":
                check_by_purpose[cand.purpose] = cand
            else:
                continue
            purpose_weights[cand.purpose] = max(purpose_weights.get(cand.purpose, 0.0), weight)

        max_alt = max(purpose_weights.values(), default=0.0)
        if max_alt >= _VOTE_BASELINE_THRESH:
            check_weight = 0.0
        else:
            check_weight = 0.30 * (1.0 - max_alt / max(_VOTE_BASELINE_THRESH, 1e-9))

        groups = [
            (purpose, weight)
            for purpose, weight in purpose_weights.items()
            if weight > 0 and purpose != "default_check"
        ]
        if check_weight > 0:
            groups.append(("default_check", check_weight))
        chosen_purpose, probs, gap, mode = self._vote_choose_group(ctx, groups)
        if not chosen_purpose:
            return ActionCandidate("default_check", "check", 0.0, 0.0, "default_check", "fallback"), probs, gap, mode
        if chosen_purpose in check_by_purpose or chosen_purpose == "default_check":
            check = check_by_purpose.get(chosen_purpose) or ActionCandidate(
                "default_check", "check", 0.0, 0.0, "default_check", "baseline"
            )
            if chosen_purpose == "default_check":
                meta = dict(check.metadata or {})
                meta.update({
                    "trigger_weight": check_weight,
                    "exploit_weight": 1.0,
                    "effective_weight": check_weight,
                })
                check = replace(check, metadata=meta)
            return check, probs, gap, mode
        return self._vote_choose_size(ctx, bet_groups[chosen_purpose]), probs, gap, mode

    def _vote_select_defensive(self, ctx: DecisionCtx, candidates: list[ActionCandidate]):
        purpose_candidates = [
            c for c in candidates
            if c.source == "purpose" and self._vote_weight(c) > 0
        ]
        forced = self._force_river_monster_raise(ctx, purpose_candidates)
        if forced is not None:
            total = sum(max(0.0, self._vote_weight(c)) for c in purpose_candidates)
            probs = (
                [(c.purpose, self._vote_weight(c) / total) for c in purpose_candidates]
                if total > 0 else []
            )
            return forced, probs, 1.0, "deterministic"
        groups = [(c.purpose, self._vote_weight(c)) for c in purpose_candidates]
        chosen_purpose, probs, gap, mode = self._vote_choose_group(ctx, groups)
        if not chosen_purpose:
            fold = next((c for c in candidates if c.action == "fold"), None)
            return fold or ActionCandidate("fold", "fold", 0.0, 0.0, "fold", "fallback"), probs, gap, mode
        chosen = next(c for c in purpose_candidates if c.purpose == chosen_purpose)
        return chosen, probs, gap, mode

    def _force_river_monster_raise(
        self,
        ctx: DecisionCtx,
        candidates: list[ActionCandidate],
    ) -> ActionCandidate | None:
        if not (
            ctx.street == "river"
            and ctx.facing_bet
            and ctx.is_ip
            and monster_value_plan_kind(ctx, allow_facing_bet=True)
        ):
            return None
        for purpose_id in ("overbet_raise_jam", "value_raise"):
            match = next(
                (
                    c for c in candidates
                    if c.purpose == purpose_id and c.action == "raise" and self._vote_weight(c) > 0
                ),
                None,
            )
            if match is not None:
                return match
        return None

    @staticmethod
    def _legacy_blended_eq(ctx: DecisionCtx) -> float:
        """Pessimistic range equity used by the all-in check.

        2026-11-10: removed the former ``equity_mc - penalty`` floor.
        ``equity_mc`` is hero's equity against a *random* hand; letting it
        floor the estimate meant a villain all-in could be called because the
        hand beats random holdings while the range model said hero was behind
        (live 2026-11-09 hand 31:166: set of tens on a three-flush river,
        range equity 0.21 vs the bettor's range, floor gave 0.83). Equity vs
        a random hand is not an estimate of equity vs the actual betting
        range, so only the range estimate, widened by its uncertainty, counts.

        2026-11-18: the uncertainty is about *which* hands the opponents hold,
        so it cannot take away equity hero has against the hands that beat
        him. ``equity_when_behind`` is the estimate if they always hold one of
        those; the pessimistic value never goes below it (nor above the point
        estimate). Without it a nut flush draw on the turn (live 2026-11-18
        hand 374: real chance 26%, price 18%) was marked down from 0.25 to
        0.06 and folded. Bluff-catchers are unaffected: their equity when
        behind is small.
        """
        point = float(ctx.equity_range or 0.0)
        pessimistic = max(0.0, point - float(ctx.equity_uncertainty or 0.0))
        behind = ctx.equity_when_behind
        if behind is not None:
            pessimistic = max(pessimistic, min(point, float(behind)))
        return pessimistic

    def _vote_choose_group(self, ctx: DecisionCtx, groups: list[tuple[str, float]]):
        total = sum(max(0.0, float(weight or 0.0)) for _purpose, weight in groups)
        if total <= 0:
            return "", [], 0.0, "mixed"
        ordered = sorted(groups, key=lambda item: item[1], reverse=True)
        top_purpose, top_weight = ordered[0]
        second_weight = ordered[1][1] if len(ordered) > 1 else 0.0
        top_prob = top_weight / total
        second_prob = second_weight / total
        gap = top_prob - second_prob
        probs = [(purpose, max(0.0, weight) / total) for purpose, weight in groups]
        flags = self._leverage_flags(ctx)
        if (
            _VOTE_LEVERAGE_DETERMINISTIC
            and flags
            and top_prob >= _VOTE_LEVERAGE_MIN_TOP
            and gap >= _VOTE_LEVERAGE_TOP_GAP
        ):
            return top_purpose, probs, gap, "deterministic"
        r = ctx.rng.random() * total
        acc = 0.0
        for purpose, weight in groups:
            acc += max(0.0, float(weight or 0.0))
            if r <= acc:
                return purpose, probs, gap, "mixed"
        return groups[-1][0], probs, gap, "mixed"

    @staticmethod
    def _vote_weight(cand: ActionCandidate) -> float:
        meta = cand.metadata or {}
        if "effective_weight" in meta:
            return max(0.0, float(meta.get("effective_weight") or 0.0))
        if "trigger_weight" in meta:
            return max(0.0, float(meta.get("trigger_weight") or 0.0))
        return 0.0

    @staticmethod
    def _vote_choose_size(ctx: DecisionCtx, group: list[ActionCandidate]) -> ActionCandidate:
        if len(group) <= 1:
            return group[0]
        total = sum(max(0.0, float((c.metadata or {}).get("size_weight", 1.0) or 0.0)) for c in group)
        if total <= 0:
            return group[0]
        r = ctx.rng.random() * total
        acc = 0.0
        for cand in group:
            acc += max(0.0, float((cand.metadata or {}).get("size_weight", 1.0) or 0.0))
            if r <= acc:
                return cand
        return group[-1]

    def _vote_summary(self, ctx: DecisionCtx, cand: ActionCandidate) -> dict[str, Any]:
        weight = self._vote_weight(cand)
        return {
            "label": cand.label,
            "action": cand.action,
            "amount": round(float(cand.amount), 4),
            "frac": round(float(cand.frac), 4),
            "purpose": cand.purpose,
            "vote_weight": round(weight, 4),
            "reason": "purpose vote" if weight > 0 else "baseline/fallback",
            "components": {"metadata": dict(cand.metadata or {})},
            "blocked_by": [],
        }

    def _vote_reason(self, ctx: DecisionCtx, chosen: ActionCandidate, mode: str) -> str:
        weight = self._vote_weight(chosen)
        if chosen.source == "fallback" and (chosen.metadata or {}).get("block_reason"):
            return f"{chosen.label}: {(chosen.metadata or {}).get('block_reason')} | {mode}"
        if chosen.source == "baseline":
            return f"{chosen.label}: baseline selected | {mode}"
        return f"{chosen.label}: purpose vote weight={weight:.3f} | {mode}"

    def _active_candidates(self, ctx: DecisionCtx) -> list[ActionCandidate]:
        out: list[ActionCandidate] = []
        seen: set[tuple[str, int, str]] = set()
        for p in self.active_purposes:
            if ctx.street not in p.street_gate:
                continue
            tr = p.trigger(ctx)
            exploit_weight = self._exploit_weight(ctx, p.id)
            effective_weight = self._effective_weight(tr.weight, exploit_weight)
            if not tr.hit or effective_weight <= 0:
                continue
            metadata = {
                "trigger_weight": tr.weight,
                "exploit_weight": exploit_weight,
                "effective_weight": effective_weight,
            }
            if p.default_action == "check" or not p.emits_bet:
                cand = ActionCandidate(
                    label=p.id,
                    action="check",
                    amount=0.0,
                    frac=0.0,
                    purpose=p.id,
                    source="purpose",
                    metadata=metadata,
                )
                if cand.key not in seen:
                    seen.add(cand.key)
                    out.append(cand)
                continue
            for frac, size_weight in p.sizer(ctx) or []:
                frac = self._active_value_frac(ctx, p, float(frac or 0.0))
                cal = calibrator.calibrate(frac, ctx, p.id)
                if cal.amount <= 0:
                    continue
                if self._active_sticky_multiway_blocks(ctx, p.id, cal.frac):
                    continue
                if self._active_bet_fold_budget_blocks(ctx, p.id, cal.frac):
                    continue
                cand = ActionCandidate(
                    label=f"{p.id}_{int(round(cal.frac * 100))}",
                    action="bet",
                    amount=cal.amount,
                    frac=cal.frac,
                    purpose=p.id,
                    source="purpose",
                    jammed=cal.jammed,
                    metadata={
                        **metadata,
                        "size_weight": size_weight,
                    },
                )
                if cand.key not in seen:
                    seen.add(cand.key)
                    out.append(cand)
        return out

    def _active_value_frac(self, ctx: DecisionCtx, purpose: Purpose, frac: float) -> float:
        if not purpose.active_value_sizing_allowed(ctx, frac):
            return frac
        ev_size = active_value_sizing.choose(ctx, purpose.id, frac)
        return float(ev_size.frac if ev_size is not None else frac)

    @staticmethod
    def _active_sticky_multiway_blocks(ctx: DecisionCtx, purpose_id: str, frac: float) -> bool:
        sticky = (
            ctx.num_opponents >= 2
            and (
                ctx.n_sticky >= 1
                or ctx.max_value_lean >= 1.20
                or exploit.no_fold_equity(ctx)
                or exploit.sticky_passive(ctx)
            )
        )
        if not sticky:
            return False
        if ctx.hero_bucket in {"air", "weak_draw"}:
            return True
        if ctx.hero_bucket == "medium" and frac > _STICKY_MULTIWAY_MEDIUM_MAX_FRAC:
            return True
        return False

    @staticmethod
    def _active_bet_fold_budget_blocks(ctx: DecisionCtx, purpose_id: str, frac: float) -> bool:
        """Skip active bets that are too large for fragile hands to defend.

        This changes only the active side: if the bet is blocked, the engine can
        still check or use another value/protection purpose. It does not make a
        facing-bet fold decision.
        """
        if ctx.facing_bet or purpose_id not in _BET_FOLD_BUDGET_PURPOSES:
            return False
        if frac <= _BET_FOLD_BUDGET_MAX_FRAC:
            return False
        if ctx.hero_bucket not in {"medium", "strong"}:
            return False

        subtype = ctx.hero_made_subtype or ""
        stable_strong = (
            ctx.hero_bucket == "strong"
            and subtype in {"clean_overpair", "set", "clean_two_pair", "straight_or_flush"}
            and float(ctx.equity_range or 0.0) >= 0.62
        )
        if stable_strong:
            return False

        fragile = (
            subtype in _BET_FOLD_BUDGET_FRAGILE_SUBTYPES
            or ctx.hero_hand_rank == "one_pair"
        )
        if not fragile:
            return False

        pressured_pot = (
            (ctx.spr > 0 and ctx.spr <= _BET_FOLD_BUDGET_SPR)
            or ctx.prev_bet_called_count > 0
            or ctx.prev_bet_raised
            or ctx.resistance_level >= 0.20
        )
        if not pressured_pot:
            return False

        sig = ctx.board_sig
        dangerous_board = (
            bool(sig.flush_possible)
            or bool(sig.flush_draw)
            or bool(sig.straight_possible)
            or bool(sig.straight_draw_heavy)
            or bool(sig.paired)
            or sig.wetness >= 0.55
        )
        strong_mass = float((ctx.villain_bucket_dist or {}).get("strong", 0.0) or 0.0)
        nuts = float((ctx.villain_bucket_dist or {}).get("nuts", 0.0) or 0.0)
        pressure_range = strong_mass + nuts >= 0.45 or nuts >= 0.18
        poor_continue = (
            float(ctx.equity_range or 0.0) < 0.58
            or float(ctx.equity_mc or 0.0) - float(ctx.equity_range or 0.0) >= 0.18
        )
        return (dangerous_board or pressure_range) and poor_continue

    def _defensive_candidates(self, ctx: DecisionCtx) -> list[ActionCandidate]:
        out: list[ActionCandidate] = [
            ActionCandidate("fold", "fold", 0.0, 0.0, "fold", "baseline"),
            ActionCandidate("call", "call", min(ctx.to_call, ctx.stack), 0.0, "call", "baseline", jammed=ctx.to_call >= ctx.stack),
        ]
        seen = {c.key for c in out}

        def add_candidate(cand: ActionCandidate) -> None:
            if cand.source == "purpose" and cand.action in {"call", "fold"}:
                for idx, existing in enumerate(out):
                    if existing.action == cand.action and existing.source == "baseline":
                        seen.discard(existing.key)
                        out[idx] = cand
                        seen.add(cand.key)
                        return
            if cand.key in seen:
                return
            seen.add(cand.key)
            out.append(cand)

        for p in self.defensive_purposes:
            if ctx.street not in p.street_gate:
                continue
            tr = p.trigger(ctx)
            exploit_weight = self._exploit_weight(ctx, p.id)
            effective_weight = self._effective_weight(tr.weight, exploit_weight)
            if not tr.hit or effective_weight <= 0:
                continue
            action = p.default_action
            metadata = {
                "trigger_weight": tr.weight,
                "exploit_weight": exploit_weight,
                "effective_weight": effective_weight,
            }
            if action == "call":
                cand = ActionCandidate(
                    label=p.id,
                    action="call",
                    amount=min(ctx.to_call, ctx.stack),
                    frac=0.0,
                    purpose=p.id,
                    source="purpose",
                    jammed=ctx.to_call >= ctx.stack,
                    metadata=metadata,
                )
            elif action == "fold":
                cand = ActionCandidate(
                    label="fold_purpose",
                    action="fold",
                    amount=0.0,
                    frac=0.0,
                    purpose=p.id,
                    source="purpose",
                    metadata=metadata,
                )
            elif action == "raise":
                amount = self._raise_amount(ctx, p)
                if amount <= ctx.to_call:
                    continue
                frac = amount / max(ctx.pot, 1.0)
                cand = ActionCandidate(
                    label=p.id,
                    action="raise",
                    amount=amount,
                    frac=frac,
                    purpose=p.id,
                    source="purpose",
                    jammed=ctx.stack > 0 and amount >= ctx.stack,
                    metadata=metadata,
                )
            else:
                continue
            add_candidate(cand)
        return out

    def _raise_amount(self, ctx: DecisionCtx, purpose: Purpose) -> float:
        if purpose.id == "overbet_raise_jam":
            return ctx.stack
        if purpose.id == "value_raise" and ctx.spr <= 2.0:
            return ctx.stack
        size = max(ctx.to_call * 2.8, ctx.to_call + ctx.pot * 0.75)
        return min(size, ctx.stack)
