"""V3 decision engine — the purpose-first postflop brain.

Call pattern:
    engine = V3Engine()
    out = engine.decide(ctx)
    # out.action in {'fold','check','call','bet','raise'}; out.amount in chips

doc 03 §2 / §6 / §9.
"""

from __future__ import annotations

import os
import struct
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from pokerfate.strategy.v3 import alpha_gate, calibrator, exploit
from pokerfate.strategy.v3.context import DecisionCtx
from pokerfate.strategy.v3.purpose import Purpose, PurposeRegistry, TriggerResult
from pokerfate.strategy.v3.purposes_active import all_active
from pokerfate.strategy.v3.purposes_defensive import all_defensive
from pokerfate.strategy.v3.purposes_passive import all_passive

# 2026-04-28 P0.1：max_alt 阈值（≥此值时 baseline 归零）。env 可覆盖供 sweep。
_BASELINE_THRESH = float(os.environ.get('PF_BASELINE_THRESH', '0.6'))
# P1 sweep 2026-04-29: full replay × 3 seeds selected margin=0.00 +
# mc_penalty=0.10 over previous 0.02/0.15. This keeps the range-uncertainty
# guard but stops over-penalizing raw MC in profitable call/fold nodes.
_FOLD_OVERRIDE_MARGIN = float(os.environ.get('PF_FOLD_OVERRIDE_MARGIN', '0.00'))
_FOLD_OVERRIDE_MC_PENALTY = float(os.environ.get('PF_FOLD_OVERRIDE_MC_PENALTY', '0.10'))
_MC_RANGE_DIVERGENCE_GUARD = os.environ.get('PF_MC_RANGE_DIVERGENCE_GUARD', '1') == '1'
_MC_RANGE_DIVERGENCE_MIN = float(os.environ.get('PF_MC_RANGE_DIVERGENCE_MIN', '0.18'))
_MC_RANGE_DIVERGENCE_EXTRA_PENALTY = float(os.environ.get('PF_MC_RANGE_DIVERGENCE_EXTRA_PENALTY', '0.15'))
_MC_RANGE_DIVERGENCE_MIN_STREET = os.environ.get('PF_MC_RANGE_DIVERGENCE_MIN_STREET', 'turn')
_MC_RANGE_DIVERGENCE_MIN_CALL_POT = float(os.environ.get('PF_MC_RANGE_DIVERGENCE_MIN_CALL_POT', '0.20'))
_LEVERAGE_TOP_GAP = float(os.environ.get('PF_LEVERAGE_TOP_GAP', '0.18'))
_LEVERAGE_MIN_TOP = float(os.environ.get('PF_LEVERAGE_MIN_TOP', '0.48'))
_LEVERAGE_DETERMINISTIC = os.environ.get('PF_LEVERAGE_DETERMINISTIC', '1') != '0'


@dataclass
class DecisionOutput:
    action: str = 'check'
    amount: float = 0.0
    purpose: str = ''
    frac: float = 0.0
    seed: int = 0
    candidates: List[Tuple[str, float]] = field(default_factory=list)  # (id, prob)
    alpha: Optional[alpha_gate.AlphaCheckResult] = None
    exploit_deltas: Dict[str, float] = field(default_factory=dict)
    jammed: bool = False                       # jam round-up fired in calibrator
    downgraded_to_check: bool = False          # bet purpose selected but α-gate → check
    reason: str = ''
    arbitration_mode: str = 'mixed'
    top_gap: float = 0.0
    leverage_flags: List[str] = field(default_factory=list)


class V3Engine:
    """Purpose-first postflop decision engine."""

    def __init__(self) -> None:
        self.registry = PurposeRegistry()
        for p in all_active():
            self.registry.register(p)
        for p in all_passive():
            self.registry.register(p)
        for p in all_defensive():
            self.registry.register(p)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _fresh_seed(self, ctx: DecisionCtx) -> int:
        seed = int(ctx.seed or 0)
        if seed <= 0:
            seed = struct.unpack(">I", os.urandom(4))[0]
        ctx.rng.seed(seed)
        ctx.seed = seed
        return seed

    def _sample_purpose(
        self,
        candidates: List[Tuple[Purpose, float]],
        ctx: DecisionCtx,
    ) -> Optional[Purpose]:
        if not candidates:
            return None
        total = sum(w for _, w in candidates)
        if total <= 0:
            return None
        r = ctx.rng.random() * total
        acc = 0.0
        for p, w in candidates:
            acc += w
            if r <= acc:
                return p
        return candidates[-1][0]

    def _sample_size(
        self,
        purpose: Purpose,
        ctx: DecisionCtx,
    ) -> float:
        sizes = purpose.sizer(ctx)
        if not sizes:
            return 0.0
        total = sum(w for _, w in sizes)
        if total <= 0:
            return sizes[0][0]
        r = ctx.rng.random() * total
        acc = 0.0
        for frac, w in sizes:
            acc += w
            if r <= acc:
                return frac
        return sizes[-1][0]

    def _collect_candidates(
        self,
        pool: List[Purpose],
        ctx: DecisionCtx,
    ) -> Tuple[List[Tuple[Purpose, float]], Dict[str, float]]:
        """Run triggers. Returns (candidates, exploit_deltas_by_id)."""
        out: List[Tuple[Purpose, float]] = []
        deltas: Dict[str, float] = {}
        for p in pool:
            if ctx.street not in p.street_gate:
                continue
            tr: TriggerResult = p.trigger(ctx)
            if not tr.hit:
                continue
            ex = exploit.weight_for(p.id, ctx)
            deltas[p.id] = ex
            out.append((p, tr.weight * ex))
        return out, deltas

    def _mc_range_divergence_penalty(self, ctx: DecisionCtx) -> float:
        if not _MC_RANGE_DIVERGENCE_GUARD:
            return _FOLD_OVERRIDE_MC_PENALTY
        street_order = {'flop': 1, 'turn': 2, 'river': 3}
        min_order = street_order.get(_MC_RANGE_DIVERGENCE_MIN_STREET, 2)
        if street_order.get(ctx.street, 0) < min_order:
            return _FOLD_OVERRIDE_MC_PENALTY
        if ctx.pot <= 0 or ctx.to_call / ctx.pot < _MC_RANGE_DIVERGENCE_MIN_CALL_POT:
            return _FOLD_OVERRIDE_MC_PENALTY
        if ctx.equity_mc - ctx.equity_range < _MC_RANGE_DIVERGENCE_MIN:
            return _FOLD_OVERRIDE_MC_PENALTY
        return _FOLD_OVERRIDE_MC_PENALTY + _MC_RANGE_DIVERGENCE_EXTRA_PENALTY

    def _leverage_flags(self, ctx: DecisionCtx) -> List[str]:
        flags: List[str] = []
        if ctx.street == 'river':
            flags.append('river')
        if ctx.spr > 0 and ctx.spr <= 1.5:
            flags.append('low_spr')
        bet_ratio = (ctx.to_call / max(ctx.pot, 1.0)) if ctx.facing_bet else 0.0
        if bet_ratio >= 0.75:
            flags.append('large_bet')
        if ctx.stack > 0 and ctx.to_call / ctx.stack >= 0.35:
            flags.append('stack_commit')
        if ctx.big_blind > 0 and ctx.pot / ctx.big_blind >= 40:
            flags.append('large_pot')
        if ctx.facing_large_bet:
            flags.append('facing_large_bet')
        return flags

    def _choose_purpose(
        self,
        candidates: List[Tuple[Purpose, float]],
        ctx: DecisionCtx,
    ) -> Tuple[Optional[Purpose], List[Tuple[str, float]], str, float, List[str]]:
        cand_probs = self._candidate_probs(candidates)
        flags = self._leverage_flags(ctx)
        if not candidates:
            return None, cand_probs, 'mixed', 0.0, flags

        ordered = sorted(candidates, key=lambda item: item[1], reverse=True)
        total = sum(max(0.0, w) for _, w in candidates)
        if total <= 0:
            return None, cand_probs, 'mixed', 0.0, flags
        top_p, top_w = ordered[0]
        second_w = ordered[1][1] if len(ordered) > 1 else 0.0
        top_prob = top_w / total
        second_prob = second_w / total
        top_gap = top_prob - second_prob
        if (_LEVERAGE_DETERMINISTIC and flags
                and top_prob >= _LEVERAGE_MIN_TOP
                and top_gap >= _LEVERAGE_TOP_GAP):
            return top_p, cand_probs, 'deterministic', top_gap, flags
        return self._sample_purpose(candidates, ctx), cand_probs, 'mixed', top_gap, flags

    # ------------------------------------------------------------------
    # Main entry
    # ------------------------------------------------------------------

    def decide(self, ctx: DecisionCtx) -> DecisionOutput:
        seed = self._fresh_seed(ctx)

        if ctx.facing_bet:
            return self._decide_defense(ctx, seed)
        return self._decide_active(ctx, seed)

    # ------------------------------------------------------------------
    # Active branch (no facing bet)
    # ------------------------------------------------------------------

    def _decide_active(self, ctx: DecisionCtx, seed: int) -> DecisionOutput:
        active_pool = [p for p in self.registry.all()
                       if not p.facing_bet and p.default_action != 'fold']
        candidates, deltas = self._collect_candidates(active_pool, ctx)

        # Adaptive baseline weight: strong purpose present → suppress check baseline.
        max_alt = max((w for _, w in candidates), default=0.0)
        # 2026-04-28 P0.1：max_alt ≥ _BASELINE_THRESH 时 baseline 直接归零。
        # 旧公式 0.30 - 0.30·min(1, max_alt) 在 max_alt=0.79 仍给 6%，叠加 α-gate
        # 降级实测出现 21% baseline，把"semi_bluff[79%] default_check[21%]"这类
        # 强 purpose 摇成 check。env 可调供 sweep。
        if max_alt >= _BASELINE_THRESH:
            baseline = 0.0
        else:
            baseline = 0.30 * (1.0 - max_alt / _BASELINE_THRESH)
        # Replace default_check entry from candidates (if present) with adaptive weight.
        candidates = [(p, w) for p, w in candidates if p.id != 'default_check']
        default_check = self.registry.by_id('default_check')
        candidates.append((default_check, baseline))

        chosen, cand_probs, arb_mode, top_gap, flags = self._choose_purpose(candidates, ctx)

        if chosen is None or not chosen.emits_bet:
            return DecisionOutput(
                action='check', amount=0.0,
                purpose=chosen.id if chosen else 'default_check',
                frac=0.0, seed=seed,
                candidates=cand_probs, exploit_deltas=deltas,
                arbitration_mode=arb_mode, top_gap=top_gap,
                leverage_flags=flags,
                reason='no bet purpose selected',
            )

        # Sample size → calibrate → α gate (chain A only; chain B is implicit
        # trust-long-run per doc 03 §7.3 revision)
        frac = self._sample_size(chosen, ctx)
        return self._finalize_bet(
            ctx, chosen, frac, seed, cand_probs, deltas,
            arbitration_mode=arb_mode, top_gap=top_gap, leverage_flags=flags,
        )

    def _finalize_bet(
        self,
        ctx: DecisionCtx,
        purpose: Purpose,
        frac: float,
        seed: int,
        cand_probs: List[Tuple[str, float]],
        deltas: Dict[str, float],
        fallback_depth: int = 0,
        arbitration_mode: str = 'mixed',
        top_gap: float = 0.0,
        leverage_flags: Optional[List[str]] = None,
    ) -> DecisionOutput:
        leverage_flags = leverage_flags or []
        cal = calibrator.calibrate(frac, ctx, purpose.id)
        if cal.amount <= 0:
            return DecisionOutput(action='check', amount=0.0,
                                   purpose=purpose.id, frac=0.0, seed=seed,
                                   candidates=cand_probs,
                                   exploit_deltas=deltas,
                                   arbitration_mode=arbitration_mode,
                                   top_gap=top_gap,
                                   leverage_flags=leverage_flags,
                                   reason='calibrator produced 0')
        # α gate on the calibrated frac
        check = alpha_gate.check(ctx, cal.frac, purpose.id)

        if not check.passed and check.direction == 'over_bluff' and fallback_depth < 2:
            # Chain A: pick next smaller sizer tier, re-run calibrator+gate.
            sizes = purpose.sizer(ctx)
            smaller = [f for f, _ in sizes if f < frac]
            if smaller:
                smaller.sort()
                return self._finalize_bet(
                    ctx, purpose, smaller[0], seed, cand_probs, deltas,
                    fallback_depth + 1,
                    arbitration_mode=arbitration_mode,
                    top_gap=top_gap,
                    leverage_flags=leverage_flags,
                )
            # No smaller tier available → check.
            return DecisionOutput(
                action='check', amount=0.0, purpose=purpose.id, frac=0.0,
                seed=seed, candidates=cand_probs, exploit_deltas=deltas,
                alpha=check, downgraded_to_check=True,
                arbitration_mode=arbitration_mode, top_gap=top_gap,
                leverage_flags=leverage_flags,
                reason='α-gate chain A downsize exhausted → check',
            )
        # Chain B (under_bluff) already handled inside alpha_gate.check via
        # exploit.under_bluff_allowed. If it still failed here, doc 03 §7.3
        # says "accept current bet; trust long-run balance". Proceed.

        action = 'raise' if ctx.facing_bet else 'bet'
        return DecisionOutput(
            action=action,
            amount=cal.amount,
            purpose=purpose.id,
            frac=cal.frac,
            seed=seed,
            candidates=cand_probs,
            alpha=check,
            exploit_deltas=deltas,
            jammed=cal.jammed,
            arbitration_mode=arbitration_mode,
            top_gap=top_gap,
            leverage_flags=leverage_flags,
            reason=f"{purpose.id} frac={cal.frac:.2f}"
                   + (" (jammed)" if cal.jammed else ""),
        )

    # ------------------------------------------------------------------
    # Defense branch (facing a bet)
    # ------------------------------------------------------------------

    def _decide_defense(self, ctx: DecisionCtx, seed: int) -> DecisionOutput:
        # All-in first
        if ctx.to_call >= ctx.stack:
            mc_penalty = self._mc_range_divergence_penalty(ctx)
            blended_eq = max(
                ctx.equity_range - (ctx.equity_uncertainty or 0.0),
                ctx.equity_mc - mc_penalty,
            )
            if blended_eq >= ctx.pot_odds + _FOLD_OVERRIDE_MARGIN:
                return DecisionOutput(
                    action='call', amount=min(ctx.to_call, ctx.stack),
                    purpose='bluff_catch_call', seed=seed,
                    arbitration_mode='deterministic',
                    top_gap=1.0,
                    leverage_flags=self._leverage_flags(ctx) or ['all_in'],
                    reason=f'all-in robust call (blended_eq {blended_eq:.2f} '
                           f'≥ pot_odds {ctx.pot_odds:.2f})',
                )
            return DecisionOutput(
                action='fold', amount=0.0, purpose='fold', seed=seed,
                arbitration_mode='deterministic',
                top_gap=1.0,
                leverage_flags=self._leverage_flags(ctx) or ['all_in'],
                reason=f'all-in robust fold (blended_eq {blended_eq:.2f} '
                       f'< pot_odds {ctx.pot_odds:.2f})',
            )

        # 2026-04-25：fold 作为独立 purpose 参与投票（见 FoldPurpose.trigger）。
        # 旧架构的 baseline = 0.30 − 0.30×max_alt 残量公式在 max_alt≥1.0 时把
        # fold 完全挤出候选池（session 04-24 实测 5/67 决策挤出累计 -909 BB）；
        # 在 max_alt 小时又让 sampler 随机弃掉价值牌。两端病理都是因为 fold 的
        # weight 和"该不该弃"的实际证据无关，只跟"其它 purpose 有多强"挂钩。
        # 现在 fold 走 _collect_candidates 标准流程，按 equity margin、bet_ratio、
        # villain bucket_dist.nuts 等证据返回动态 weight。
        pool = [p for p in self.registry.all() if p.facing_bet]
        candidates, deltas = self._collect_candidates(pool, ctx)

        chosen, cand_probs, arb_mode, top_gap, flags = self._choose_purpose(candidates, ctx)

        if chosen is None or chosen.id == 'fold':
            # 2026-04-28 P0.2：tracker 对 loose-passive 对手会把 equity_range
            # 系统性压低（log 反复出现 "胜率 27%(vs随机 53%)"），fold-only 候选
            # 实际上是 tracker 偏置而非真正弱牌。用 mc-blend 做兜底：若 raw mc
            # 减去保守余量后仍超 pot_odds，强制 call。env 可调。
            mc_penalty = self._mc_range_divergence_penalty(ctx)
            blended_eq = max(
                ctx.equity_range - (ctx.equity_uncertainty or 0.0),
                ctx.equity_mc - mc_penalty,
            )
            if blended_eq >= ctx.pot_odds + _FOLD_OVERRIDE_MARGIN:
                return DecisionOutput(
                    action='call', amount=min(ctx.to_call, ctx.stack),
                    purpose='fold_override_call', seed=seed,
                    candidates=cand_probs, exploit_deltas=deltas,
                    arbitration_mode=arb_mode, top_gap=top_gap,
                    leverage_flags=flags,
                    reason=f'fold→call override (blended_eq {blended_eq:.2f} '
                           f'≥ pot_odds {ctx.pot_odds:.2f})',
                )
            return DecisionOutput(action='fold', amount=0.0, purpose='fold',
                                   seed=seed, candidates=cand_probs,
                                   exploit_deltas=deltas,
                                   arbitration_mode=arb_mode,
                                   top_gap=top_gap,
                                   leverage_flags=flags,
                                   reason='fold baseline sampled')

        if chosen.default_action == 'call':
            return DecisionOutput(
                action='call', amount=min(ctx.to_call, ctx.stack),
                purpose=chosen.id, seed=seed,
                candidates=cand_probs, exploit_deltas=deltas,
                arbitration_mode=arb_mode, top_gap=top_gap,
                leverage_flags=flags,
                reason=f"{chosen.id} accept",
            )

        # Raise path
        amount = self._raise_amount(ctx, chosen)
        if amount <= ctx.to_call:
            # Can't legally raise → fall back to call.
            return DecisionOutput(
                action='call', amount=min(ctx.to_call, ctx.stack),
                purpose=chosen.id, seed=seed,
                candidates=cand_probs, exploit_deltas=deltas,
                arbitration_mode=arb_mode, top_gap=top_gap,
                leverage_flags=flags,
                reason=f"{chosen.id} raise→call (amount too small)",
            )
        return DecisionOutput(
            action='raise', amount=amount, purpose=chosen.id, seed=seed,
            candidates=cand_probs, exploit_deltas=deltas,
            arbitration_mode=arb_mode, top_gap=top_gap,
            leverage_flags=flags,
            reason=f"{chosen.id} raise to {amount:.0f}",
        )

    def _raise_amount(self, ctx: DecisionCtx, purpose: Purpose) -> float:
        """Compute total raise amount (to-size) for a raise purpose."""
        # SPR <= 2 + strong: jam. Also overbet_raise_jam always jams.
        if purpose.id == 'overbet_raise_jam':
            return ctx.stack
        if purpose.id == 'value_raise' and ctx.spr <= 2.0:
            return ctx.stack
        # Standard raise: max(to_call * 2.8, to_call + 0.75 pot) clamped to stack.
        size = max(ctx.to_call * 2.8, ctx.to_call + ctx.pot * 0.75)
        return min(size, ctx.stack)

    # ------------------------------------------------------------------
    # Shared utilities
    # ------------------------------------------------------------------

    @staticmethod
    def _candidate_probs(cands: List[Tuple[Purpose, float]]) -> List[Tuple[str, float]]:
        total = sum(w for _, w in cands)
        if total <= 0:
            return [(p.id, 0.0) for p, _ in cands]
        return [(p.id, w / total) for p, w in cands]
