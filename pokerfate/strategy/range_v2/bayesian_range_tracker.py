"""Bayesian 1326-dim range tracker.

# 2026-04-28 P0.3 env hooks:
#   PF_LP_SIGNAL_FACTOR  loose-passive (vpip>=0.45 & pfr/vpip<=0.30) signal ×=this
#   PF_NEW_SIGNAL_FACTOR new villain (hands_seen<30) signal ×=this

Maintains a probability vector w[1326] for each opponent.  Every observed
action multiplies by the action likelihood and re-normalizes.

References:
  - Bayes' Bluff (Southey et al., UAI 2005) — Bayesian opponent modeling
  - Libratus (Brown & Sandholm, 2017) — reach probability as range prior
  - Johanson et al. (AISTATS 2009) — GTO↔observed confidence interpolation
    (paper: "Data Biased Robust Counter Strategies")
  - Grünwald (2012, SafeBayes) — power likelihood tempering (α-Bayes).
    The specific α = max(0.3, 0.85 - 0.4·confidence) schedule is a heuristic;
    Grünwald's original work uses cross-validation to pick η.
"""

from __future__ import annotations

import logging
import os as _os
from typing import Dict, List, Optional, Set

import numpy as np

from pokerfate.core.card import Card
from pokerfate.core.config import MIN_HANDS_FOR_CLASSIFICATION
from pokerfate.strategy.range_v2 import hand_categorizer as hcat
from pokerfate.strategy.range_v2 import hand_combo_map as hcm
from pokerfate.strategy.range_v2.action_model import (
    ActionContext,
    ActionModel,
    GTO_PFR,
    GTO_VPIP,
    PlayerProfile,
)

log = logging.getLogger(__name__)

_LP_SIGNAL_FACTOR = float(_os.environ.get('PF_LP_SIGNAL_FACTOR', '0.5'))
_NEW_SIGNAL_FACTOR = float(_os.environ.get('PF_NEW_SIGNAL_FACTOR', '0.7'))


# ---------------------------------------------------------------------------
# Cross-street sequence pattern corrections
#
# Empirically calibrated factors applied AFTER the independent Bayesian
# update. Goal: capture sequential information that category-level likelihoods
# miss (e.g. a capped calling line sharply de-weights nuts).
#
# Calibration methodology:
#   1. Run independent Bayesian updates with GTO freq tables + α=0.7
#   2. Get target distributions from PioSolver / Upswing / Red Chip data
#   3. correction = target ÷ independent_result
#
# These numbers come from a private solver run; they are not citable from any
# public source. Treat as engineering heuristics, not GTO truth.
# ---------------------------------------------------------------------------

# Refined action types (produced from raw 'raise' by context.is_raise_over)
_ACT_BET = 'bet'                 # first aggressive action on this street
_ACT_RAISE_OVER = 'raise_over'   # raising over someone else's bet
_ACT_CALL = 'call'
_ACT_CHECK = 'check'
_ACT_FOLD = 'fold'

_SEQUENCE_CORRECTIONS: Dict[str, Dict[str, float]] = {
    # check-check-raise_over on 2+ streets → slow-play trap.
    #  - strong 1.1→1.3: overpair/two-pair share of xr range is higher than 1.1 implied
    #  - draw 0.2→0.4: semi-bluff CR with FD is a real GTO line
    'xr_trap': {
        'nuts': 2.0, 'strong': 1.3, 'medium': 0.3,
        'draw': 0.4, 'weak_draw': 0.1, 'air': 0.4,
    },
    # same-street check-then-raise-over (river CR)
    'check_raise': {
        'nuts': 1.5, 'strong': 1.0, 'medium': 0.3,
        'draw': 0.7, 'weak_draw': 0.3, 'air': 0.7,
    },
    # same-street re-raise (e.g. flop 3bet).
    #  - weak_draw 0.1→0.3: gutshot + overcard is a real 3bet bluff combo
    'reraise': {
        'nuts': 2.0, 'strong': 0.8, 'medium': 0.2,
        'draw': 0.5, 'weak_draw': 0.3, 'air': 0.6,
    },
    # bet-bet-bet through the river.
    #  - draw/weak_draw would be remapped to 'air' on the river anyway
    #    (HandCategorizer rule). Keys omitted.
    'triple_barrel': {
        'nuts': 1.2, 'strong': 1.0, 'medium': 0.7,
        'air': 0.65,
    },
    # call-call (2-street cap): PARTIAL cap — nuts still possible (0.3 not 0.1)
    # because 2 calls isn't enough evidence to rule out slow-play.
    'capped_range_partial': {
        'nuts': 0.30, 'strong': 0.50, 'medium': 1.50,
        'draw': 1.20, 'weak_draw': 1.10, 'air': 1.0,
    },
    # call-call-call (3-street cap): FULL cap — nuts effectively ruled out.
    'capped_range_full': {
        'nuts': 0.10, 'strong': 0.35, 'medium': 1.65,
        'draw': 1.30, 'weak_draw': 1.20, 'air': 1.0,
    },
    # bet-bet-check give-up
    'bet_bet_give_up': {
        'nuts': 0.12, 'strong': 0.25, 'medium': 5.0,
        'draw': 2.0, 'weak_draw': 1.5, 'air': 5.0,
    },
    # raise → check on next street: failed semi-bluff signature
    'aggression_drop': {
        'nuts': 0.19, 'strong': 0.42, 'medium': 1.8,
        'draw': 2.0, 'weak_draw': 1.8, 'air': 2.7,
    },
}


def _detect_sequence_pattern(history: List[tuple]) -> Optional[str]:
    """Detect if the (street, refined_action) history matches a known pattern.

    Returns the most-specific matching pattern name, or None.
    Only triggers on POSTFLOP streets — preflop sequences go through the
    preflop action model and should not be double-weighted here.
    """
    if not history:
        return None

    last_street, last_act = history[-1]
    if last_street == 'preflop':
        # Pattern corrections are calibrated on postflop category semantics.
        # Running them on preflop would apply postflop nuts/medium/air
        # labels to preflop hand buckets — incorrect by construction.
        return None

    street_actions: Dict[str, List[str]] = {}
    for street, act in history:
        street_actions.setdefault(street, []).append(act)

    streets_in_order = ['preflop', 'flop', 'turn', 'river']
    postflop_streets = [
        s for s in streets_in_order
        if s in street_actions and s != 'preflop'
    ]

    # ── Strong signals (triggered on raise/bet) ──

    if last_act == _ACT_RAISE_OVER:
        # x/x/xr: checked on 2+ prior postflop streets, then raise_over
        check_streets = sum(
            1 for s in postflop_streets[:-1]
            if _ACT_CHECK in street_actions.get(s, [])
        )
        if check_streets >= 2:
            return 'xr_trap'

        current_street_acts = street_actions.get(last_street, [])
        # check-raise: checked earlier this street, now raise_over
        if len(current_street_acts) >= 2 and current_street_acts[-2] == _ACT_CHECK:
            return 'check_raise'

        # re-raise: already bet/raised this street
        prior_raises = sum(
            1 for a in current_street_acts[:-1]
            if a in (_ACT_BET, _ACT_RAISE_OVER)
        )
        if prior_raises >= 1:
            return 'reraise'

    if last_act == _ACT_BET:
        # triple barrel: a bet/raise on flop + turn + river, ending with a
        # river bet (this action). '3 streets of aggression + river bet'.
        bet_streets = [
            s for s in postflop_streets
            if any(a in (_ACT_BET, _ACT_RAISE_OVER) for a in street_actions.get(s, []))
        ]
        if len(bet_streets) >= 3 and last_street == 'river':
            return 'triple_barrel'

    # ── Weak signals (triggered on check/call) ──

    if last_act == _ACT_CHECK:
        # bet-bet-give_up: bet on 2 prior streets, now check
        bet_streets = [
            s for s in postflop_streets
            if any(a in (_ACT_BET, _ACT_RAISE_OVER) for a in street_actions.get(s, []))
            and s != last_street
        ]
        if len(bet_streets) >= 2:
            return 'bet_bet_give_up'

        # aggression_drop: bet/raised on previous street, check on current
        prev_idx = streets_in_order.index(last_street) - 1 if last_street in streets_in_order else -1
        if prev_idx >= 0:
            prev_street = streets_in_order[prev_idx]
            prev_acts = street_actions.get(prev_street, [])
            if any(a in (_ACT_BET, _ACT_RAISE_OVER) for a in prev_acts):
                return 'aggression_drop'

    if last_act == _ACT_CALL:
        # Capped range: ONLY call, never bet/raise on any postflop street.
        # Triggered pre-emptively at 2 calls (partial) so the bot's NEXT
        # decision can exploit; tightens further at 3 calls (full).
        ever_raised = any(
            a in (_ACT_BET, _ACT_RAISE_OVER)
            for s in postflop_streets
            for a in street_actions.get(s, [])
        )
        if ever_raised:
            return None
        call_streets = [
            s for s in postflop_streets
            if _ACT_CALL in street_actions.get(s, [])
        ]
        if len(call_streets) >= 3:
            return 'capped_range_full'
        if len(call_streets) >= 2:
            return 'capped_range_partial'

    return None


class BayesianRangeTracker:
    """Per-opponent 1326-dim Bayesian range tracker."""

    def __init__(self, action_model: ActionModel):
        self.action_model = action_model
        self._weights: Dict[int, np.ndarray] = {}  # player_id → w[1326]
        self._known_cards: Set[int] = set()        # my hole cards (set once per hand)
        # Per-hand folded set. Used to exclude folded villains from the
        # multi-way active set passed to the calibration hook. Cleared in
        # start_new_hand.
        self._folded: Set[int] = set()
        # Per-player history of (street, refined_action) tuples for
        # sequence-pattern detection. Cleared in reset_hand so patterns
        # never bleed across hand boundaries.
        self._action_history: Dict[int, List[tuple]] = {}
        # 2026-04-23 showdown calibration hook。可选 callback，在每次
        # _weights[pid] 更新后被调，参数：
        #   (player_id, street, board, weights, trigger)
        # 实际使用见 pokerfate.calibration.ShowdownCalibrator。None 时
        # tracker 无 overhead。
        self._prediction_hook = None  # type: Optional[callable]
        # 提供给 hook 取 player_name 的回调（player_id -> name）
        self._name_resolver = None    # type: Optional[callable]
        # Category cache: hcat.categorize(idx, board) is a pure function of
        # (board, idx), so within a street all callers (observe_action's
        # correction loop, reweight_for_board, get_bucket_distribution) can
        # share one lookup table of length 1326. Invalidated on any board
        # change via the cache key (sorted tuple of board card ints).
        # Review 01_bayesian_tracker §2.3 + §4.8: 50%+ CPU saving expected.
        self._cat_cache_key: Optional[tuple] = None
        self._cat_cache: Optional[List[str]] = None

    def set_known_cards(self, cards: List[Card]) -> None:
        """Call once per hand with bot's hole cards."""
        self._known_cards = {hcm.card_to_int(c) for c in cards}

    def start_new_hand(self) -> None:
        """Per-hand reset of fold state. Call before per-player reset_hand."""
        self._folded.clear()

    def _get_categories(self, board: List[Card]) -> List[str]:
        """Return per-combo category list for this board (cached).

        Pure wrapper around hcat.categorize — caches the full 1326-length
        list keyed by board. Preflop calls (empty board) use the preflop
        bucket; any postflop call uses the on-board evaluator.
        """
        key: tuple
        if board and len(board) >= 3:
            key = tuple(sorted(hcm.card_to_int(c) for c in board))
        else:
            key = ()
        if self._cat_cache_key != key:
            board_arg = board if key else []
            # Build in one pass; hcat.categorize is ~0.1 ms so 1326 calls
            # cost ~130 ms worst case, but this happens at most once per
            # street change — amortised to effectively free.
            self._cat_cache = [hcat.categorize(i, board_arg) for i in range(1326)]
            self._cat_cache_key = key
        return self._cat_cache

    def reset_hand(self, player_id: int, position: str,
                   profile: PlayerProfile) -> None:
        """Initialize prior distribution for a new hand.

        Prior construction (Johanson 2009 Data-Biased method):
          - Hands in PFR range → weight 1.0
          - Hands in VPIP range but not PFR → weight 0.6
          - Hands outside VPIP → weight 0.03 (never zero — allows deviation)
          - Card removal: combos containing known cards → 0
        """
        # Guard against empty/falsy position upstream (None / '').
        # Empty string was missing from GTO_VPIP so it fell through to the
        # 0.27 default, which is MP/CO-shaped. Use CO as neutral default when
        # unknown so BB 0.40 never accidentally maps to 0.27.
        if not position:
            position = 'CO'

        w = np.ones(1326, dtype=np.float64)

        # Card removal: my hole cards
        block = hcm.blocked_by(self._known_cards)
        w[block] = 0.0

        # Position prior
        vpip = profile.vpip if profile.hands_seen >= MIN_HANDS_FOR_CLASSIFICATION else GTO_VPIP.get(position, 0.27)
        pfr = profile.pfr if profile.hands_seen >= MIN_HANDS_FOR_CLASSIFICATION else GTO_PFR.get(position, 0.20)

        raise_thresh = 1.0 - pfr
        call_floor = 1.0 - vpip

        strengths = hcm.STRENGTH_PCT
        for idx in range(1326):
            if w[idx] == 0.0:
                continue
            s = strengths[idx]
            if s >= raise_thresh:
                w[idx] = 1.0
            elif s >= call_floor:
                w[idx] = 0.6
            else:
                w[idx] = 0.03

        total = w.sum()
        if total > 0:
            w /= total

        self._weights[player_id] = w
        # Sequence-pattern history starts fresh for this hand. If this call
        # gets skipped, _detect_sequence_pattern would see stale entries from
        # the previous hand and fire spurious triple_barrel/capped patterns.
        self._action_history[player_id] = []

        self._emit_prediction(player_id, 'preflop', [], 'reset')

    def reweight_for_board(self, board: List[Card]) -> None:
        """Board-aware prior recalibration on new community cards.

        Problem: preflop priors score hands by preflop strength. 74o → 0.03
        weight. But on a 77x flop, 74o is TRIPS. The Bayesian call-likelihood
        for nuts ≈ that for medium (~0.30-0.35), so calling alone won't
        differentiate them. Without this reweight, trips combos on paired
        boards stay invisible.

        Fix: boost combos that make nuts / strong on the current board
        (regardless of preflop weight). Does NOT scale down other combos —
        that rebalancing is already handled by the renormalize step.

        Issue D/E (gameplay analysis): the boost floor must scale with the
        opponent's range WIDTH. Fish open VPIP ~60% and reach postflop
        with ~600 live combos; nuts combos are DILUTED across that wide
        reach. Tight players reach with ~150 live combos; nuts are
        CONCENTRATED. A fixed 3× avg floor over-inflates fish bucket[nuts]
        (observed: 369 decisions showed fish bucket[nuts] ≥ 0.40;
        4 catastrophic river cold-calls vs obvious nuts).

        Math: P(nuts | reach) ∝ n_nuts_combos / n_reach_combos.
        Linear interpolation by reach_pct so fish get a lower floor.
        """
        if not board or len(board) < 3:
            return

        board_ints = {hcm.card_to_int(c) for c in board}
        categories = self._get_categories(board)

        # Threshold for "meaningful weight" (same bar as
        # get_effective_range_pct): weight > 10% of uniform. Combos at
        # 0.03/total (outside VPIP tier) don't count as part of reach.
        _MEANINGFUL_W = 1.0 / 13260  # 10% of 1/1326
        for w in self._weights.values():
            # avg_w still uses full "alive" (w>1e-10) as the denominator to
            # keep the magnitude of boost comparable across opponents.
            live_mask = w > 1e-10
            n_active = int(live_mask.sum())
            if n_active == 0:
                continue
            avg_w = 1.0 / n_active

            # Range-width-aware floor multipliers.
            # meaningful_pct counts combos with 10%+ of uniform weight — a
            # proxy for "how wide is the believable part of villain's range".
            # Tight prior (UTG) meaningful_pct ≈ 0.14 → nuts_mul ≈ 2.8
            # Loose prior (BB vs limp) meaningful_pct ≈ 0.55 → nuts_mul ≈ 2.2
            # Very wide (whale after tempered update) meaningful_pct ≈ 0.80 → 1.8
            meaningful_pct = float((w > _MEANINGFUL_W).sum()) / 1326.0
            # Clamp to [0.1, 1.0] so edge cases (near-empty or near-uniform)
            # produce sane floors.
            meaningful_pct = max(0.1, min(1.0, meaningful_pct))
            nuts_floor_mul = 1.5 + 1.5 * (1.0 - meaningful_pct)      # 1.5 – 2.85
            strong_floor_mul = 0.75 + 0.75 * (1.0 - meaningful_pct)  # 0.75 – 1.425

            modified = False
            for idx in range(1326):
                if w[idx] < 1e-10:
                    continue
                c1, c2 = hcm.ALL_COMBOS[idx]
                if c1 in board_ints or c2 in board_ints:
                    continue
                cat = categories[idx]
                if cat == 'nuts':
                    floor = avg_w * nuts_floor_mul
                    if w[idx] < floor:
                        w[idx] = floor
                        modified = True
                elif cat == 'strong':
                    floor = avg_w * strong_floor_mul
                    if w[idx] < floor:
                        w[idx] = floor
                        modified = True

            if modified:
                s = w.sum()
                if s > 0:
                    w /= s

        # Calibration hook — board 变化也算 range 调整，记录预测
        # 推断 street（board 长度）
        if len(board) == 5:
            inferred_street = 'river'
        elif len(board) == 4:
            inferred_street = 'turn'
        elif len(board) == 3:
            inferred_street = 'flop'
        else:
            inferred_street = 'preflop'
        for pid in list(self._weights.keys()):
            if pid in self._folded:
                continue
            self._emit_prediction(pid, inferred_street, board,
                                  f'board:{inferred_street}')

    def observe_action(self, player_id: int, action: str, street: str,
                       context: ActionContext, profile: PlayerProfile,
                       board: List[Card],
                       *, high_signal: bool = False,
                       signal_strength: Optional[float] = None) -> None:
        """Tempered Bayesian update with entropy-adaptive damping.

        Standard Bayes: w *= likelihood
        Tempered:       w *= likelihood^α   (α < 1 slows convergence)

        α is adaptive — when the posterior is already concentrated (low
        entropy), α decreases to resist further collapse.  This prevents
        the distribution from collapsing to a handful of combos after
        3-4 sequential updates, which is the core over-convergence problem
        in sequential Bayesian range tracking.

        References:
          - Grünwald 2012, SafeBayes — power likelihood / likelihood tempering
          - Posterior regularization — floor mixing to prevent zero probabilities

        2026-04-24 (方案 B 升级)：`signal_strength ∈ [0, 1]` 替代原 `high_signal`
        离散门。强度含义：villain 本次动作对其 range 的窄化证据力度。
          - strength=0 → 原 tempered 路径（α 自适应 0.1–0.85, λ=0.08, floor 生效）
          - strength=1 → 标准 Bayes（α=1.0, λ=0, 无 floor）
          - 中间连续插值。
        原 `high_signal=True` 等价于 strength=1.0（保留作向后兼容）。
        """
        if signal_strength is None:
            signal_strength = 1.0 if high_signal else 0.0
        signal_strength = max(0.0, min(1.0, float(signal_strength)))

        # 2026-04-28 P0.3：loose-passive 对手 + 新对手信号降权（env 可调）。
        # 鲸鱼/超松被动对手的下注 range 极宽且不极化，下注信号噪声远大于 reg；
        # tracker 把他们的 0.3x pot bet 当强信号收紧，导致 hero "胜率 25%(vs随机
        # 35%)" 这类系统性压制。新对手 (hands_seen<30) vpip/pfr 都不稳定，同样降权。
        if profile.hands_seen >= MIN_HANDS_FOR_CLASSIFICATION:
            pfr_ratio = (profile.pfr / profile.vpip) if profile.vpip > 0 else 1.0
            if profile.vpip >= 0.45 and pfr_ratio <= 0.30:
                signal_strength *= _LP_SIGNAL_FACTOR
        if profile.hands_seen < 30:
            signal_strength *= _NEW_SIGNAL_FACTOR
        if player_id not in self._weights:
            self.reset_hand(player_id, context.position or 'CO', profile)

        w = self._weights[player_id]

        # Card removal: board cards
        if board:
            board_ints = {hcm.card_to_int(c) for c in board}
            all_known = self._known_cards | board_ints
            block = hcm.blocked_by(all_known)
            w[block] = 0.0

        # Compute likelihoods for all 1326 combos
        hero_cards = (
            [hcm.int_to_card(i) for i in self._known_cards]
            if self._known_cards else None
        )
        likelihoods = self.action_model.batch_likelihood(
            action, street, context, profile, board, hero_cards=hero_cards
        )

        # ── Adaptive likelihood tempering ──
        # Compute current entropy to gauge how concentrated the posterior is
        active = w > 1e-10
        n_active = int(active.sum())
        if n_active > 1:
            w_pos = w[active]
            entropy = float(-np.sum(w_pos * np.log2(w_pos)))
            max_entropy = np.log2(n_active)
            confidence = 1.0 - entropy / max_entropy if max_entropy > 0 else 0.0
        else:
            confidence = 1.0
        # α_adaptive ∈ [0.10, 0.85]: high confidence → very low α (强抗集中)。
        # 2026-04-23：按 Grünwald SafeBayes (2012) 的 adaptive tempering 思路。
        alpha_adaptive = max(0.1, 0.85 - 0.75 * confidence)
        # signal_strength 线性插值到 α=1.0：strength=0 用自适应，strength=1 纯 Bayes
        alpha = (1.0 - signal_strength) * alpha_adaptive + signal_strength * 1.0

        # Bayesian update (standard when high_signal, tempered otherwise)
        w *= likelihoods ** alpha

        # Normalize
        total = w.sum()
        if total > 1e-15:
            w /= total
        else:
            w = np.ones(1326, dtype=np.float64)
            all_known = set(self._known_cards)
            if board:
                all_known |= {hcm.card_to_int(c) for c in board}
            w[hcm.blocked_by(all_known)] = 0.0
            s = w.sum()
            if s > 0:
                w /= s
            else:
                w[:] = 1.0 / 1326

        # ── Posterior regularization (floor mixing) ──
        # 2026-04-23：Grünwald SafeBayes prior mixing，和 α-tempering 互补——
        # α 管"单次更新激进度"、floor mixing 管"累积集中度上限"。
        # 混入 λ 的"对 active combos 均匀分布"，阻止连续 pot-size barrels
        # 把 air 权重压到 ~0。
        # signal_strength 线性降 λ：强度=0 → λ=0.08，强度=1 → λ=0。
        lam = 0.08 * (1.0 - signal_strength)
        if lam > 1e-6:
            active_mask = w > 0
            n_active = int(active_mask.sum())
            if n_active > 0:
                uniform = np.zeros_like(w)
                uniform[active_mask] = 1.0 / n_active
                w = (1.0 - lam) * w + lam * uniform

        # ── Probability floor: no combo drops below floor ──
        # 强信号（signal_strength > 0.8）时跳过：让 "villain 绝不会这么下"
        # 的空气 combo 真正归零，不再贡献 hero eq。
        # 有了 floor mixing 这一层基本不做事（mixing 后每个 active combo 至少
        # λ/n_active ≈ 8e-5，超过 1e-4/n_active 的 floor 阈值），保留为兜底。
        if signal_strength <= 0.8:
            active = w > 0
            n_active = int(active.sum())
            if n_active > 0:
                floor = 1e-4 / n_active
                below = active & (w < floor)
                if below.any():
                    w[below] = floor
                    w /= w.sum()

        # ── Cross-street sequence pattern correction ──
        # Refine action: distinguish 'bet' (first) from 'raise_over' (re-raise/CR).
        if action == 'raise':
            refined = _ACT_RAISE_OVER if context.is_raise_over else _ACT_BET
        elif action in ('call', 'check', 'fold'):
            refined = action
        else:
            refined = action

        history = self._action_history.setdefault(player_id, [])
        history.append((street, refined))

        pattern_name = _detect_sequence_pattern(history)
        if pattern_name:
            correction = _SEQUENCE_CORRECTIONS.get(pattern_name)
            if correction:
                board_ints = {hcm.card_to_int(c) for c in board} if board else set()
                categories = self._get_categories(board)
                for idx in range(1326):
                    if w[idx] < 1e-10:
                        continue
                    c1, c2 = hcm.ALL_COMBOS[idx]
                    if c1 in board_ints or c2 in board_ints:
                        continue
                    cat = categories[idx]
                    # River: draws become air (HandCategorizer rule).
                    if street == 'river' and cat in ('draw', 'weak_draw'):
                        cat = 'air'
                    factor = correction.get(cat, 1.0)
                    w[idx] *= factor
                s = w.sum()
                if s > 1e-15:
                    w /= s
                # Re-apply floor AFTER correction: small multipliers
                # (capped nuts=0.10, bet_bet_give_up nuts=0.12) can push
                # nuts combos below the 1e-4/n floor, from which they can
                # never recover. This regularisation prevents permanent
                # collapse of rare-but-live combos.
                active = w > 0
                n_active = int(active.sum())
                if n_active > 0:
                    floor = 1e-4 / n_active
                    below = active & (w < floor)
                    if below.any():
                        w[below] = floor
                        w /= w.sum()

        self._weights[player_id] = w

        # Mark as folded BEFORE emitting so active_weights excludes them for
        # this emit and subsequent fold_other emits.
        is_fold = (refined == 'fold')
        if is_fold:
            self._folded.add(player_id)

        # Calibration hook — 每次 observe_action 结束都记录预测
        self._emit_prediction(
            player_id, street, board, f'action:{refined}',
        )

        # A fold changes the multi-way active set for every surviving villain.
        # Re-emit their current predictions so calibration records reflect the
        # new active count (their own range is unchanged; what changed is the
        # scene).
        if is_fold:
            for pid in list(self._weights.keys()):
                if pid != player_id and pid not in self._folded:
                    self._emit_prediction(
                        pid, street, board, 'action:fold_other',
                    )

    def _emit_prediction(self, player_id: int, street: str,
                         board: List[Card], trigger: str) -> None:
        """Push current posterior to calibration hook (if set)."""
        if self._prediction_hook is None:
            return
        w = self._weights.get(player_id)
        if w is None:
            return
        # 解析 player name（通过 resolver；resolver 可 None 时用 id 字符串）
        if self._name_resolver is not None:
            name = self._name_resolver(player_id)
        else:
            name = str(player_id)
        # hero_cards from known_cards
        hero_cards = [hcm.int_to_card(i) for i in sorted(self._known_cards)]
        if len(hero_cards) < 2:
            hero_cards = None
        # Active opponents at this moment = everyone tracked minus folded.
        # Passed to hook so calibration can compute multi-way hero eq (hero
        # vs all active opponents' current ranges).
        active_weights = {
            pid: self._weights[pid]
            for pid in self._weights
            if pid not in self._folded
        }
        try:
            self._prediction_hook(
                player_id=player_id, player_name=name,
                street=street, board=list(board),
                weights=w, hero_cards=hero_cards, trigger=trigger,
                active_weights=active_weights,
            )
        except Exception:
            # Calibration hook 失败不应影响正常决策，但必须暴露出来。
            log.exception(
                "prediction calibration hook failed player_id=%s street=%s trigger=%s",
                player_id,
                street,
                trigger,
            )

    def get_distribution(self, player_id: int) -> np.ndarray:
        """Return current 1326-dim probability distribution."""
        return self._weights.get(player_id, np.ones(1326) / 1326).copy()

    def get_effective_range_pct(self, player_id: int) -> float:
        """Fraction of combos with non-negligible probability."""
        w = self._weights.get(player_id)
        if w is None:
            return 1.0
        threshold = 1.0 / 1326 * 0.1
        return float((w > threshold).sum()) / 1326

    def get_entropy(self, player_id: int) -> float:
        """Shannon entropy of the distribution (lower = more certain)."""
        w = self._weights.get(player_id)
        if w is None:
            return np.log2(1326)
        w_pos = w[w > 0]
        return float(-np.sum(w_pos * np.log2(w_pos)))

    def get_vs_hero_dist(self, player_id: int, board: List[Card],
                         hero_cards: List[Card]) -> Dict[str, float]:
        """Hero 视角对 villain 窄化 range 的相对分布：{'win','tie','loss'}。

        问题 8(a) 修：HandCategorizer 的 NUTS 桶 = 顺子+，当 hero 自己持 NUTS
        档（如 nut-straight）时，"坚果 82%" 包含 set/trips/同阶顺等 hero 赢/平
        的 combo，日志显示给人"82% 赢 hero"的错误印象。这里返回的是基于
        per-combo 评估的实际对比分布——loss（villain 赢 hero）才是"真坚果"占比。

        仅在 river（5 张板）计算；前面街的 equity 依赖未知 runout，per-combo
        河前对比没有确定语义。非 river 返回空 dict。
        """
        if not board or len(board) < 5:
            return {}
        if not hero_cards or len(hero_cards) < 2:
            return {}
        w = self._weights.get(player_id)
        if w is None:
            return {}

        from pokerfate.core.hand_evaluator import HandEvaluator

        board_ints = {hcm.card_to_int(c) for c in board}
        hero_ints = {hcm.card_to_int(c) for c in hero_cards}
        all_known = self._known_cards | board_ints | hero_ints
        valid = w.copy()
        valid[hcm.blocked_by(all_known)] = 0.0
        total = valid.sum()
        if total < 1e-15:
            return {}
        valid /= total

        hero_score = HandEvaluator.eval_int(list(hero_cards) + list(board))
        win_w = tie_w = loss_w = 0.0
        nz = np.flatnonzero(valid)
        board_l = list(board)
        for idx in nz:
            c1, c2 = hcm.ALL_COMBOS[idx]
            opp_cards = [hcm.int_to_card(c1), hcm.int_to_card(c2)]
            opp_score = HandEvaluator.eval_int(opp_cards + board_l)
            p = float(valid[idx])
            if hero_score > opp_score:
                win_w += p
            elif hero_score == opp_score:
                tie_w += p
            else:
                loss_w += p
        return {'win': win_w, 'tie': tie_w, 'loss': loss_w}

    def get_bucket_distribution(self, player_id: int, board: List[Card]) -> Dict[str, float]:
        """Return weight-aggregated bucket distribution {category: pct}.

        Sums w[i] per HandCategorizer bucket, normalized to percentages.
        Only includes buckets > 0.
        """
        w = self._weights.get(player_id)
        if w is None:
            return {}

        board_ints = {hcm.card_to_int(c) for c in board} if board else set()
        categories = self._get_categories(board)
        buckets: Dict[str, float] = {}

        for idx in range(1326):
            if w[idx] < 1e-8:
                continue
            c1, c2 = hcm.ALL_COMBOS[idx]
            if c1 in board_ints or c2 in board_ints:
                continue
            cat = categories[idx]
            buckets[cat] = buckets.get(cat, 0.0) + w[idx]

        total = sum(buckets.values())
        if total > 0:
            buckets = {k: v / total for k, v in buckets.items()}
        return buckets

    def get_range_summary(self, player_id: int) -> dict:
        """Return summary dict for logging/debugging."""
        w = self._weights.get(player_id)
        if w is None:
            return {'effective_range_pct': 1.0, 'active_combos': 1326,
                    'entropy': np.log2(1326), 'max_weight': 1.0 / 1326}
        nonzero = int((w > 1e-6).sum())
        return {
            'effective_range_pct': nonzero / 1326,
            'active_combos': nonzero,
            'entropy': self.get_entropy(player_id),
            'max_weight': float(w.max()),
        }
