"""V3 postflop EV decision engine."""

from __future__ import annotations

import os
import struct
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from pokerfate.strategy.v3 import active_value_sizing, calibrator, ev_scorer, hard_guards
from pokerfate.strategy.v3.candidates import ActionCandidate
from pokerfate.strategy.v3.context import DecisionCtx
from pokerfate.strategy.v3.purpose import Purpose
from pokerfate.strategy.v3.purposes_active import all_active
from pokerfate.strategy.v3.purposes_defensive import all_defensive


_ACTIVE_OPPORTUNITY_V1 = os.environ.get("PF_ACTIVE_OPPORTUNITY_V1", "0").lower() in {
    "1", "true", "yes", "on"
}
_AOC_BASE = 0.12
_AOC_MAX_POT = 0.12
_AOC_MIN_EQ = 0.34
_SMALL_PRESSURE_MED_FRAC = 0.33
_SMALL_PRESSURE_HIGH_FRAC = 0.50
_SMALL_PRESSURE_HIGH_EQ = 0.40


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
    """Candidate-generation + EV-scoring postflop decision engine."""

    def __init__(self) -> None:
        self.active_purposes = [p for p in all_active() if getattr(p, "default_action", "bet") != "check"]
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
        raw = self._defensive_candidates(ctx) if ctx.facing_bet else self._active_candidates(ctx)
        candidates, blocked = self._apply_guards(ctx, raw)
        scored = [ev_scorer.score(ctx, c) for c in candidates]
        if ctx.facing_bet:
            chosen, gap, mode = ev_scorer.robust_select(ctx, scored)
        else:
            chosen, gap, mode = self._select_active_purpose_first(ctx, scored)
        trace = {
            "candidates": [s.summary() for s in sorted(scored, key=lambda x: x.ev, reverse=True)],
            "blocked": blocked,
            "mode": mode,
        }
        probs = self._candidate_probs(scored)
        flags = self._leverage_flags(ctx)
        flags = list(dict.fromkeys(flags + list((chosen.components.get("risk") or {}).get("tags") or [])))
        return DecisionOutput(
            action=chosen.action,
            amount=chosen.amount,
            purpose=chosen.purpose,
            frac=chosen.frac,
            seed=seed,
            candidates=probs,
            exploit_deltas={},
            jammed=chosen.jammed,
            downgraded_to_check=chosen.action == "check" and any(s.action in {"bet", "raise"} for s in scored),
            arbitration_mode=mode,
            top_gap=gap,
            leverage_flags=flags,
            reason=self._reason(chosen, mode),
            decision_trace=trace,
        )

    def _select_active_purpose_first(self, ctx: DecisionCtx, scored):
        ordered = sorted(scored, key=lambda s: s.ev, reverse=True)
        if not ordered:
            return ev_scorer.robust_select(ctx, scored)
        passive = next((s for s in ordered if s.action == "check"), None)
        active = [s for s in ordered if s.action == "bet"]
        if not active:
            return ordered[0], 0.0, "purpose_first_no_bet"
        purpose = self._active_purpose_anchor(ctx, active)
        pool = [s for s in active if s.purpose == purpose] if purpose else active
        ev_best = max(pool, key=lambda s: s.ev)
        chosen = self._sample_scored_size(ctx, purpose, pool) or ev_best
        if passive is not None:
            required = max(ev_best.margin, passive.margin, 0.0)
            opportunity_credit = self._active_opportunity_credit(ctx, ev_best)
            if ev_best.ev + opportunity_credit < passive.ev + required:
                return passive, passive.ev - ev_best.ev, "purpose_mix_veto"
            if opportunity_credit > 0 and ev_best.ev < passive.ev + required:
                return ev_best, ev_best.ev + opportunity_credit - passive.ev, "purpose_mix_opportunity"
        gap = chosen.ev - (passive.ev if passive else 0.0)
        return chosen, gap, "purpose_mix"

    def _active_opportunity_credit(self, ctx: DecisionCtx, active) -> float:
        """Small counterweight for value/protection lost when passive check wins.

        This is intentionally only used in the active-vs-check arbitration step.
        Global check EV still represents equity realization; this credit targets
        the narrower failure mode where check is reasonable but too conservative.
        """
        if not _ACTIVE_OPPORTUNITY_V1 or active is None or active.action != "bet":
            return 0.0
        pot = max(1.0, float(ctx.pot or 0.0))
        eq = max(float(ctx.equity_range or 0.0), float(ctx.equity_mc or 0.0))
        if eq < _AOC_MIN_EQ:
            return 0.0

        purpose = str(active.purpose or "")
        value_purposes = {
            "value_jam", "overbet_value", "monster_value_plan",
            "thick_value_bet", "thin_value_bet", "profit_paid_value_continue",
            "protection_bet", "block_bet", "range_cbet",
            "delayed_cbet", "turn_donk", "probe_bet", "profit_flop_cbet",
        }
        semi_purposes = {"semi_bluff", "small_pressure_bet", "polarized_cbet", "pure_bluff_river"}

        draw_or_blocker = (
            bool(ctx.draw.flush_draw or ctx.draw.oesd or ctx.draw.gutshot or ctx.draw.overcards)
            or ctx.blockers.count() > 0
        )
        if purpose in semi_purposes and not draw_or_blocker:
            return 0.0
        if purpose not in value_purposes and purpose not in semi_purposes:
            return 0.0

        rel = ctx.villain_vs_hero_dist or {}
        if rel:
            win = float(rel.get("win", 0.0) or 0.0)
            tie = float(rel.get("tie", 0.0) or 0.0)
            loss = float(rel.get("loss", 0.0) or 0.0)
            edge_signal = max(0.0, win + 0.5 * tie - loss)
        else:
            dist = ctx.villain_bucket_dist or {}
            worse = (
                float(dist.get("air", 0.0) or 0.0)
                + float(dist.get("weak", 0.0) or 0.0)
                + 0.8 * float(dist.get("weak_draw", 0.0) or 0.0)
                + 0.7 * float(dist.get("draw", 0.0) or 0.0)
                + 0.35 * float(dist.get("medium", 0.0) or 0.0)
            )
            better = float(dist.get("strong", 0.0) or 0.0) + float(dist.get("nuts", 0.0) or 0.0)
            if better >= 0.45 and worse < 0.35:
                return 0.0
            edge_signal = max(0.0, worse - 0.45 * better)
            if better < 0.30:
                edge_signal = max(edge_signal, max(0.0, eq - 0.50) * 1.7)

        bucket_mult = {
            "nuts": 1.25,
            "strong": 1.05,
            "medium": 0.70,
            "draw": 0.62,
            "weak_draw": 0.50,
            "weak": 0.15,
            "air": 0.0,
        }.get(ctx.hero_bucket or "", 0.45)
        if purpose in semi_purposes:
            if ctx.hero_bucket in {"draw", "weak_draw"} and draw_or_blocker:
                bucket_mult = max(bucket_mult, 0.80)
            else:
                bucket_mult *= 0.75
        if bucket_mult <= 0:
            return 0.0

        street_mult = {"flop": 0.70, "turn": 1.00, "river": 1.15}.get(ctx.street or "", 0.8)
        spr_mult = 1.20 if 0 < float(ctx.spr or 0.0) <= 1.5 else 1.0
        pos_mult = 1.10 if ctx.is_ip else 0.90
        multi_mult = max(0.45, 1.0 - 0.20 * max(0, int(ctx.num_opponents or 1) - 1))
        resistance_mult = max(0.65, 1.0 - 0.15 * max(0, int(ctx.prev_bet_called_count or 0)))
        if ctx.prev_bet_raised:
            resistance_mult *= 0.60

        signal = min(1.0, edge_signal)
        credit = pot * _AOC_BASE * signal * bucket_mult * street_mult * spr_mult * pos_mult * multi_mult * resistance_mult
        return min(pot * _AOC_MAX_POT, max(0.0, credit))

    def _sample_scored_size(self, ctx: DecisionCtx, purpose_id: str, pool):
        purpose = next((p for p in self.active_purposes if p.id == purpose_id), None)
        if purpose is None:
            return None
        sizes = list(purpose.sizer(ctx) or [])
        if not sizes:
            return None
        total = sum(max(0.0, float(w or 0.0)) for _frac, w in sizes)
        if total <= 0:
            target = float(sizes[0][0] or 0.0)
        else:
            r = ctx.rng.random() * total
            acc = 0.0
            target = float(sizes[-1][0] or 0.0)
            for frac, weight in sizes:
                acc += max(0.0, float(weight or 0.0))
                if r <= acc:
                    target = float(frac or 0.0)
                    break
        return min(pool, key=lambda s: abs(float(s.frac or 0.0) - target))

    def _active_purpose_anchor(self, ctx: DecisionCtx, active) -> str:
        by_purpose = {p.id: p for p in self.active_purposes}
        hits: list[tuple[int, float, str]] = []
        for purpose_id in {s.purpose for s in active}:
            purpose = by_purpose.get(purpose_id)
            if purpose is None:
                continue
            tr = purpose.trigger(ctx)
            if not tr.hit or tr.weight <= 0:
                continue
            hits.append((self._purpose_priority(ctx, purpose_id), float(tr.weight), purpose_id))
        if not hits:
            return active[0].purpose
        hits.sort(key=lambda item: (item[0], item[1]), reverse=True)
        return hits[0][2]

    def _purpose_priority(self, ctx: DecisionCtx, purpose_id: str) -> int:
        if purpose_id == "small_pressure_bet":
            return 20 if ctx.hero_bucket in {"air", "weak", "weak_draw", "draw"} else 5
        if purpose_id in {"value_jam", "overbet_value", "monster_value_plan"}:
            return 90
        if purpose_id in {"thick_value_bet", "profit_paid_value_continue"}:
            return 80
        if purpose_id in {"protection_bet", "thin_value_bet", "range_cbet", "profit_flop_cbet"}:
            return 70
        if purpose_id == "block_bet":
            return 45
        return 50

    def _candidate_probs(self, scored) -> List[Tuple[str, float]]:
        positives = [(s.purpose or s.label, max(0.0, float(s.ev))) for s in scored]
        total = sum(v for _, v in positives)
        if total <= 0:
            n = max(1, len(positives))
            return [(k, 1.0 / n) for k, _ in positives]
        return [(k, v / total) for k, v in positives]

    def _reason(self, chosen, mode: str) -> str:
        parts = [f"{chosen.label}: {chosen.reason}", f"ev={chosen.ev:.1f}", f"raw={chosen.raw_ev:.1f}"]
        risk = chosen.components.get("risk") or {}
        if risk.get("tags"):
            parts.append("risk=" + ",".join(risk.get("tags") or []))
        if mode == "robust_margin":
            parts.append("robust_margin")
        reaction = (chosen.components.get("reaction") or {})
        if reaction:
            parts.append(
                f"pf={reaction.get('p_fold', 0):.2f} pc={reaction.get('p_call', 0):.2f} pr={reaction.get('p_raise', 0):.2f} src={reaction.get('source','')} n={reaction.get('sample_count',0)}"
            )
        return " | ".join(parts)

    def _active_candidates(self, ctx: DecisionCtx) -> list[ActionCandidate]:
        out: list[ActionCandidate] = [ActionCandidate("check", "check", 0.0, 0.0, "check", "baseline")]
        seen: set[tuple[str, int, str]] = set()
        for p in self.active_purposes:
            tr = p.trigger(ctx)
            if not tr.hit or tr.weight <= 0:
                continue
            for frac, _w in p.sizer(ctx) or []:
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
                    metadata={"trigger_weight": tr.weight},
                )
                if cand.key not in seen:
                    seen.add(cand.key)
                    out.append(cand)
        for frac in self._small_pressure_fracs(ctx):
            cal = calibrator.calibrate(frac, ctx, "small_pressure_bet")
            cand = ActionCandidate(
                label=f"small_pressure_{int(round(cal.frac * 100))}",
                action="bet",
                amount=cal.amount,
                frac=cal.frac,
                purpose="small_pressure_bet",
                source="pressure",
                jammed=cal.jammed,
            )
            if cal.amount > 0 and cand.key not in seen:
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
        if self._small_pressure_blocked_by_live_limits(ctx):
            return []
        if ctx.hero_bucket in {"air", "weak", "weak_draw"}:
            has_semibluff = ctx.draw.flush_draw or ctx.draw.oesd or ctx.draw.gutshot or ctx.draw.backdoor_flush or ctx.blockers.count() > 0
            range_spot = ctx.is_pfr and (ctx.is_ip or ctx.board_sig.is_dry) and max(ctx.equity_range, ctx.equity_mc) >= 0.20
            if not (has_semibluff or range_spot):
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
            tr = p.trigger(ctx)
            if not tr.hit or tr.weight <= 0:
                continue
            action = getattr(p, "default_action", "raise")
            if action == "call":
                cand = ActionCandidate(
                    label=p.id,
                    action="call",
                    amount=min(ctx.to_call, ctx.stack),
                    frac=0.0,
                    purpose=p.id,
                    source="purpose",
                    jammed=ctx.to_call >= ctx.stack,
                    metadata={"trigger_weight": tr.weight},
                )
            elif action == "fold":
                cand = ActionCandidate(
                    label="fold_purpose",
                    action="fold",
                    amount=0.0,
                    frac=0.0,
                    purpose=p.id,
                    source="purpose",
                    metadata={"trigger_weight": tr.weight},
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
                    metadata={"trigger_weight": tr.weight},
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

    def _apply_guards(self, ctx: DecisionCtx, candidates: list[ActionCandidate]) -> tuple[list[ActionCandidate], list[dict[str, Any]]]:
        kept: list[ActionCandidate] = []
        blocked: list[dict[str, Any]] = []
        for cand in candidates:
            ok, reasons = hard_guards.allowed(ctx, cand)
            if ok:
                kept.append(cand)
            else:
                blocked.append({"label": cand.label, "purpose": cand.purpose, "reasons": reasons})
        if not kept:
            kept.append(ActionCandidate("fold" if ctx.facing_bet else "check", "fold" if ctx.facing_bet else "check", 0.0, 0.0, "fallback", "fallback"))
        return kept, blocked
