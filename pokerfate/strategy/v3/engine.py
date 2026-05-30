"""V3 purpose-first postflop decision engine."""

from __future__ import annotations

import os
import struct
from dataclasses import dataclass, field, replace
from typing import Any, Dict, List, Optional, Tuple

from pokerfate.strategy.v3 import active_value_sizing, alpha_gate, calibrator, exploit, hard_guards
from pokerfate.strategy.v3.candidates import ActionCandidate
from pokerfate.strategy.v3.context import DecisionCtx
from pokerfate.strategy.v3.purpose import Purpose
from pokerfate.strategy.v3.purposes_active import all_active, monster_value_plan_kind
from pokerfate.strategy.v3.purposes_defensive import all_defensive
from pokerfate.strategy.v3.purposes_passive import all_passive
from pokerfate.strategy.v3.stackoff_guard import stackoff_guard_reason


_VOTE_BASELINE_THRESH = float(os.environ.get("PF_V3_VOTE_BASELINE_THRESH", "0.6"))
_VOTE_LEVERAGE_TOP_GAP = float(os.environ.get("PF_V3_VOTE_LEVERAGE_TOP_GAP", "0.18"))
_VOTE_LEVERAGE_MIN_TOP = float(os.environ.get("PF_V3_VOTE_LEVERAGE_MIN_TOP", "0.48"))
_VOTE_LEVERAGE_DETERMINISTIC = os.environ.get("PF_V3_VOTE_LEVERAGE_DETERMINISTIC", "1").lower() not in {
    "0", "false", "no", "off"
}
_SMALL_PRESSURE_MED_FRAC = 0.33
_SMALL_PRESSURE_HIGH_FRAC = 0.50
_SMALL_PRESSURE_HIGH_EQ = 0.40
_FRAGILE_FOLD_OVERRIDE_SUBTYPES = {
    "top_pair_weak_kicker",
    "board_pair_kicker",
    "board_pair_hero_pair",
    "board_pair_pocket_underpair",
    "board_two_pair",
    "trips_weak_kicker",
    "board_trips_kicker",
}


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
            if not p.facing_bet and getattr(p, "default_action", "bet") != "fold"
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
                    f">= pot_odds={ctx.pot_odds:.2f}"
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
                f"< pot_odds={ctx.pot_odds:.2f}"
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
        if ctx.facing_bet and chosen.action == "fold":
            override, _override_reason = self._legacy_fold_override(ctx, candidates)
            if override is not None:
                chosen = override
                mode = mode + "_override"
                gap = max(gap, 0.0)
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
        overbet_jam = next(
            (
                c for c in purpose_candidates
                if c.purpose == "overbet_raise_jam"
                and c.action == "raise"
                and self._vote_weight(c) >= 0.0
            ),
            None,
        )
        if overbet_jam is not None:
            total = sum(max(0.0, self._vote_weight(c)) for c in purpose_candidates)
            probs = (
                [(c.purpose, self._vote_weight(c) / total) for c in purpose_candidates]
                if total > 0 else []
            )
            return overbet_jam, probs, 1.0, "deterministic"
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

    def _legacy_fold_override(self, ctx: DecisionCtx, candidates: list[ActionCandidate]) -> tuple[ActionCandidate | None, str]:
        if ctx.hero_bucket not in {"medium", "strong", "nuts"}:
            return None, "bucket"
        blended_eq = self._legacy_blended_eq(ctx)
        allowed, reason = self._legacy_fold_override_allowed(ctx, candidates, blended_eq)
        if not allowed or blended_eq < ctx.pot_odds:
            return None, reason
        return ActionCandidate(
            "fold_override_call",
            "call",
            min(ctx.to_call, ctx.stack),
            0.0,
            "fold_override_call",
            "override",
            jammed=ctx.to_call >= ctx.stack,
            metadata={"override_reason": reason, "blended_eq": blended_eq},
        ), reason

    @staticmethod
    def _legacy_blended_eq(ctx: DecisionCtx) -> float:
        penalty = 0.10
        vs = ctx.worst_villain_stats if ctx.worst_villain_stats.hands_seen else ctx.villain_stats
        stickyish = (
            ctx.n_sticky >= 1
            or ctx.max_value_lean >= 1.2
            or (
                vs.hands_seen >= 20
                and vs.af <= 1.0
                and (vs.wtsd >= 0.32 or vs.fold_to_cbet <= 0.30)
            )
        )
        if stickyish:
            penalty += 0.10
        street_order = {"flop": 1, "turn": 2, "river": 3}
        if (
            street_order.get(ctx.street, 0) >= 2
            and ctx.pot > 0
            and ctx.to_call / max(ctx.pot, 1.0) >= 0.20
            and ctx.equity_mc - ctx.equity_range >= 0.18
        ):
            penalty += 0.15
        return max(
            float(ctx.equity_range or 0.0) - float(ctx.equity_uncertainty or 0.0),
            float(ctx.equity_mc or 0.0) - penalty,
        )

    def _legacy_fold_override_allowed(
        self,
        ctx: DecisionCtx,
        candidates: list[ActionCandidate],
        blended_eq: float,
    ) -> tuple[bool, str]:
        dist = ctx.villain_bucket_dist or {}
        nut_prob = float(dist.get("nuts", 0.0) or 0.0)
        strong_mass = nut_prob + float(dist.get("strong", 0.0) or 0.0)
        range_edge = float(ctx.equity_range or 0.0) - float(ctx.pot_odds or 0.0)
        stack_commit = ctx.to_call / ctx.stack if ctx.stack > 0 else 0.0
        fragile = (ctx.hero_made_subtype or "") in _FRAGILE_FOLD_OVERRIDE_SUBTYPES
        if fragile and ctx.hero_made_subtype in {"board_pair_kicker", "board_two_pair"} and ctx.street != "river":
            fragile = False
        if fragile:
            fragile_high_leverage = (
                stack_commit >= 0.25
                or ctx.pot_odds >= 0.25
                or ctx.spr <= 1.5
            )
            if (
                fragile_high_leverage
                and (
                    strong_mass >= 0.55
                    or range_edge < 0.08
                    or blended_eq < ctx.pot_odds + 0.08
                )
            ):
                return False, (
                    f"fragile {ctx.hero_made_subtype} "
                    f"edge {range_edge:.2f} strong {strong_mass:.2f}"
                )
        cheap_range_call = (
            ctx.pot_odds <= 0.30
            and ctx.equity_range >= ctx.pot_odds
            and range_edge >= 0.08
        )
        commit_base = (
            stack_commit >= 0.35
            and ctx.street != "river"
            and 0 < ctx.spr <= 1.00
            and nut_prob < 0.40
            and strong_mass < 0.60
        )
        standard_commit_call = (
            commit_base
            and range_edge >= 0.12
            and blended_eq >= ctx.pot_odds + 0.12
        )
        cheap_commit_call = (
            commit_base
            and cheap_range_call
            and blended_eq >= ctx.pot_odds + 0.08
        )
        commit_range_call = standard_commit_call or cheap_commit_call

        if stack_commit >= 0.35 and not commit_range_call:
            return False, "stack_commit"
        if 0 < ctx.spr <= 1.00 and not (cheap_range_call or commit_range_call):
            return False, "low_spr"

        total = sum(max(0.0, self._vote_weight(c)) for c in candidates if c.source == "purpose")
        if total > 0:
            fold_prob = sum(
                max(0.0, self._vote_weight(c))
                for c in candidates
                if c.source == "purpose" and c.purpose == "fold"
            ) / total
            has_call = any(
                c.source == "purpose" and c.action == "call" and self._vote_weight(c) > 0
                for c in candidates
            )
            if has_call and fold_prob > 0.80 and range_edge <= 0.15 and not cheap_range_call:
                return False, "fold_prob"

        if max(0.0, ctx.pot_odds - ctx.equity_range) > 0.03:
            return False, "range_gap"
        if ctx.street == "river" and strong_mass >= 0.55 and not cheap_range_call:
            return False, "river_strong_mass"
        if blended_eq < ctx.pot_odds:
            return False, "blended_eq"
        if cheap_range_call:
            return True, "cheap_range_call"
        if commit_range_call:
            return True, "commit_range_call"
        return True, "fold_only_extra_margin"

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
        if chosen.source == "override":
            meta = chosen.metadata or {}
            return (
                f"{chosen.label}: legacy fold→call override "
                f"blended_eq={float(meta.get('blended_eq') or 0.0):.2f} "
                f"reason={meta.get('override_reason', '')} | {mode}"
            )
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
            if getattr(p, "default_action", "bet") == "check" or not getattr(p, "emits_bet", True):
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

    def _small_pressure_fracs(self, ctx: DecisionCtx) -> list[float]:
        if ctx.facing_bet:
            return []
        if ctx.num_opponents > 3:
            return []
        exploit_weight = self._exploit_weight(ctx, "small_pressure_bet")
        if exploit_weight <= 0.35:
            return []
        if exploit.no_fold_equity(ctx) and ctx.hero_bucket in {"air", "weak", "weak_draw"}:
            return []
        if self._small_pressure_blocked_by_live_limits(ctx):
            return []
        if ctx.hero_bucket in {"air", "weak", "weak_draw"}:
            if exploit_weight < 0.85:
                return []
            has_semibluff = ctx.draw.flush_draw or ctx.draw.oesd or ctx.draw.gutshot or ctx.draw.backdoor_flush or ctx.blockers.count() > 0
            range_spot = ctx.is_pfr and (ctx.is_ip or ctx.board_sig.is_dry) and max(ctx.equity_range, ctx.equity_mc) >= 0.20
            if not (has_semibluff or range_spot):
                return []
            eq_need = 0.24 if ctx.num_opponents <= 1 else 0.32
            if max(ctx.equity_range, ctx.equity_mc) < eq_need and ctx.blockers.count() <= 0:
                return []
        if ctx.num_opponents > 1 and ctx.board_sig.is_wet and ctx.hero_bucket in {"air", "weak", "weak_draw"}:
            return []
        return [self._small_pressure_frac(ctx)]

    @staticmethod
    def _small_pressure_frac(ctx: DecisionCtx) -> float:
        equity = max(0.0, min(1.0, float(ctx.equity_range or 0.0)))
        if equity >= _SMALL_PRESSURE_HIGH_EQ:
            return _SMALL_PRESSURE_HIGH_FRAC
        return _SMALL_PRESSURE_MED_FRAC

    def _small_pressure_blocked_by_live_limits(self, ctx: DecisionCtx) -> bool:
        equity = max(0.0, min(1.0, float(ctx.equity_range or 0.0)))
        if self._is_big_blind_level(ctx, 10_000) and equity < 0.20:
            return True
        if not self._is_big_blind_level(ctx, 50_000):
            return False
        if equity < 0.30:
            return True
        if 0.30 <= equity < 0.40 and ctx.street in {"turn", "river"}:
            return self._had_called_flop_bet(ctx) or ctx.prev_bet_called_count > 0
        return False

    @staticmethod
    def _is_big_blind_level(ctx: DecisionCtx, target: float) -> bool:
        bb = float(ctx.big_blind or 0.0)
        return target * 0.90 <= bb <= target * 1.10

    @staticmethod
    def _had_called_flop_bet(ctx: DecisionCtx) -> bool:
        return (
            ctx.my_prev_actions.get("flop") in {"bet", "raise"}
            and ctx.opp_prev_actions.get("flop") == "call"
        )

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
            action = getattr(p, "default_action", "raise")
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

    def _apply_guards(
        self,
        ctx: DecisionCtx,
        candidates: list[ActionCandidate],
    ) -> tuple[list[ActionCandidate], list[dict[str, Any]], list[dict[str, Any]], Any]:
        kept: list[ActionCandidate] = []
        blocked: list[dict[str, Any]] = []
        alpha_checks: list[dict[str, Any]] = []
        blocked_alpha = None
        for cand in candidates:
            ok, reasons = hard_guards.allowed(ctx, cand)
            if not ok:
                blocked.append({"label": cand.label, "purpose": cand.purpose, "reasons": reasons})
                continue
            alpha = self._alpha_for_candidate(ctx, cand)
            if alpha is not None:
                summary = self._alpha_summary(alpha)
                alpha_checks.append({"label": cand.label, "purpose": cand.purpose, **summary})
                meta = dict(cand.metadata or {})
                meta["alpha"] = summary
                cand = replace(cand, metadata=meta)
                if not alpha.passed and alpha.direction == "over_bluff":
                    blocked.append({
                        "label": cand.label,
                        "purpose": cand.purpose,
                        "reasons": ["alpha_over_bluff"],
                        "alpha": summary,
                    })
                    if blocked_alpha is None:
                        blocked_alpha = alpha
                    continue
            kept.append(cand)
        if not kept:
            kept.append(ActionCandidate("fold" if ctx.facing_bet else "check", "fold" if ctx.facing_bet else "check", 0.0, 0.0, "fallback", "fallback"))
        return kept, blocked, alpha_checks, blocked_alpha
