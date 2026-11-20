"""Bayesian 1326-dim range tracker.

Maintains a probability vector w[1326] for each opponent.  Every hand starts with all combos
equally likely; every observed action multiplies by the fitted action likelihood
(``fitted_likelihood.py``: by preflop strength bin before the flop, by strength bucket after
it), re-normalizes, and mixes a small share of a uniform range back in so that no hand is
ever ruled out.

References:
  - Bayes' Bluff (Southey et al., UAI 2005) — Bayesian opponent modeling
  - Libratus (Brown & Sandholm, 2017) — reach probability as range prior
"""

from __future__ import annotations

import logging
import os as _os
from typing import Any, Dict, List, Optional, Set

from collections import OrderedDict

import numpy as np

from pokerfate.core.card import Card
from pokerfate.core.hand_evaluator import HandEvaluator
from pokerfate.strategy.range_v2 import hand_categorizer as hcat
from pokerfate.strategy.range_v2 import hand_combo_map as hcm
from pokerfate.strategy.range_v2.action_model import ActionContext, ActionModel, PlayerProfile
from pokerfate.strategy.range_v2.bucket_ml_calibration import (
    calibrate_bucket_probs,
    profile_feature_dict,
)
from pokerfate.strategy.range_v2.empirical_model import action_label
from pokerfate.strategy.range_v2.fitted_likelihood import (
    ACTIONS as LIKELIHOOD_ACTIONS, PREFLOP_BINS, likelihood_features, preflop_bin_index, preflop_features,
    preflop_label,
)

log = logging.getLogger(__name__)

_BUCKET_CAL_MIN_FACTOR = 0.25
_BUCKET_CAL_MAX_FACTOR = 8.0
_BUCKET_CAL_CATS = ('nuts', 'strong', 'medium', 'draw', 'weak_draw', 'air')
_BUCKET_CAL_IDX = {cat: i for i, cat in enumerate(_BUCKET_CAL_CATS)}




def _bet_size_bucket(ratio: float) -> str:
    try:
        x = float(ratio or 0.0)
    except Exception:
        x = 0.0
    if x <= 0.0:
        return 'none'
    if x <= 0.25:
        return 'small'
    if x <= 0.40:
        return 'third'
    if x <= 0.55:
        return 'half'
    if x <= 0.80:
        return 'two_third'
    if x <= 1.10:
        return 'pot'
    if x <= 1.75:
        return 'overpot'
    return 'huge'


def _action_sequence_key(history: List[tuple], limit: int = 6) -> str:
    recent = history[-limit:]
    return '|'.join(f'{street}:{action}' for street, action in recent)


def _preflop_action_type(action: str, context: ActionContext) -> str:
    if context.street != 'preflop':
        return ''
    if action == 'raise':
        if context.facing_action == 'none':
            return 'open'
        if context.facing_action == 'open':
            return '3bet'
        if context.facing_action == '3bet':
            return '4bet'
        if context.facing_action == '4bet':
            return '5bet'
        return 'raise'
    if action == 'call':
        if context.facing_action == 'none':
            return 'limp'
        if context.facing_action == 'open':
            return 'call_open'
        if context.facing_action == '3bet':
            return 'call_3bet'
        return 'call'
    if action == 'check':
        return 'check_option'
    if action == 'fold':
        return 'fold'
    return action or ''


# Refined action types (produced from raw 'raise' by context.is_raise_over)
_ACT_BET = 'bet'                 # first aggressive action on this street
_ACT_RAISE_OVER = 'raise_over'   # raising over someone else's bet

_RIVER_SCORE_CACHE: "OrderedDict[tuple, List[int]]" = OrderedDict()
_RIVER_SCORE_CACHE_MAX = 16


def _river_combo_scores(board: List[Card]) -> List[int]:
    """eval_int strength of each of the 1326 combos on a 5-card ``board``
    (combos sharing a card with the board get 0; callers mask them)."""
    key = tuple(sorted(hcm.card_to_int(c) for c in board))
    hit = _RIVER_SCORE_CACHE.get(key)
    if hit is not None:
        _RIVER_SCORE_CACHE.move_to_end(key)
        return hit
    board_l = list(board)
    board_ints = set(key)
    out: List[int] = []
    for c1, c2 in hcm.ALL_COMBOS:
        if c1 in board_ints or c2 in board_ints:
            out.append(0)
        else:
            out.append(HandEvaluator.eval_int([hcm.int_to_card(c1), hcm.int_to_card(c2)] + board_l))
    _RIVER_SCORE_CACHE[key] = out
    if len(_RIVER_SCORE_CACHE) > _RIVER_SCORE_CACHE_MAX:
        _RIVER_SCORE_CACHE.popitem(last=False)
    return out


class BayesianRangeTracker:
    """Per-opponent 1326-dim Bayesian range tracker."""

    def __init__(self, action_model: ActionModel):
        self.action_model = action_model
        self._weights: Dict[int, np.ndarray] = {}  # player_id → w[1326]
        self._big_blind: Optional[float] = None
        self._known_cards: Set[int] = set()        # my hole cards (set once per hand)
        # Per-hand folded set. Used to exclude folded villains from the
        # multi-way active set passed to the calibration hook. Cleared in
        # start_new_hand.
        self._folded: Set[int] = set()
        # Per-player history of (street, refined_action) tuples for
        # sequence-pattern detection. Cleared in reset_hand so patterns
        # never bleed across hand boundaries.
        self._action_history: Dict[int, List[tuple]] = {}
        self._action_meta: Dict[int, Dict[str, Any]] = {}
        # Last PlayerProfile seen per opponent this hand (bucket-ML profile features).
        self._player_profiles: Dict[int, PlayerProfile] = {}
        # Bucket-ML is a read-only overlay (2026-11-11). When it is applied the
        # formula-only weights are kept here and restored before the next
        # update, so ML corrections never compound across triggers. Compounding
        # was measured to roughly double the layer's strength over-statement
        # (turn check +0.10 vs +0.06 non-compounding) and to cost 0.01 Brier.
        self._formula_weights: Dict[int, np.ndarray] = {}
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
        self._board_int_cache_key: Optional[tuple] = None
        self._board_int_cache: Set[int] = set()
        self._blocked_mask_cache: Dict[tuple, np.ndarray] = {}
        # Per-layer trace of the most recent observe_action; consumed by the
        # API's opponent_action log.
        self.last_update_trace: Dict[str, Any] = {}
        # Off in play.  The training-row extractor turns it on to get, next to the trace, the
        # weights the last postflop update started from (analysis/type_truth.py).
        self.keep_update_weights: bool = False
        self.last_update_weights: Optional[np.ndarray] = None

    def set_big_blind(self, big_blind: float) -> None:
        self._big_blind = float(big_blind or 0.0)

    def set_known_cards(self, cards: List[Card]) -> None:
        """Call once per hand with bot's hole cards: nobody else can hold them.

        The ranges of the hand usually exist already (``reset_hand`` runs when the hand
        starts, the hole cards arrive after), so the removal is applied to them here.
        """
        self._known_cards = {hcm.card_to_int(c) for c in cards}
        if not self._known_cards:
            return
        blocked = hcm.blocked_by(self._known_cards)
        for store in (self._weights, self._formula_weights):
            for w in store.values():
                w[blocked] = 0.0
                total = w.sum()
                if total > 0:
                    w /= total

    def start_new_hand(self) -> None:
        """Reset per-hand range state before per-player reset_hand calls."""
        # The previous hand's hole cards say nothing about this one.  Until 2026-11-15 they
        # were still in force when the new ranges were built: every combo containing one of
        # them stayed impossible for the whole hand (7.6% of what opponents really held).
        self._known_cards = set()
        self._weights.clear()
        self._folded.clear()
        self._action_history.clear()
        self._action_meta.clear()
        self._player_profiles.clear()
        self._formula_weights.clear()

    def _board_key(self, board: List[Card]) -> tuple:
        if board and len(board) >= 3:
            return tuple(sorted(hcm.card_to_int(c) for c in board))
        return ()

    def _board_ints(self, board: List[Card]) -> Set[int]:
        key = self._board_key(board)
        if self._board_int_cache_key != key:
            self._board_int_cache = set(key)
            self._board_int_cache_key = key
        return self._board_int_cache

    def _blocked_mask(self, known_cards: Set[int]) -> np.ndarray:
        key = tuple(sorted(known_cards))
        mask = self._blocked_mask_cache.get(key)
        if mask is None:
            mask = hcm.blocked_by(set(key))
            self._blocked_mask_cache[key] = mask
        return mask

    def _get_categories(self, board: List[Card]) -> List[str]:
        """Return per-combo category list for this board (cached).

        Pure wrapper around hcat.categorize — caches the full 1326-length
        list keyed by board. Preflop calls (empty board) use the preflop
        bucket; any postflop call uses the on-board evaluator.
        """
        key = self._board_key(board)
        if self._cat_cache_key != key:
            # Shared module-level LRU (hcat.categorize_all): the action model
            # categorises the same board, so the work is done once per board
            # for the whole process, not once per consumer.
            self._cat_cache = hcat.categorize_all(board if key else [])
            self._cat_cache_key = key
        return self._cat_cache

    def _apply_bucket_calibration(self, player_id: int, street: str,
                                  board: List[Card], trigger: str) -> None:
        """Bucket-ML overlay: recalibrate bucket masses (read-only, see _formula_weights).

        The offline gamma/theta formula params that used to run before the ML
        step were removed 2026-11-11: with the ML on they changed nothing in
        closed-loop replay (ΔBrier −0.0014 ± 0.0015) and without it they hurt.
        """
        if not board or len(board) < 3:
            return
        active_count = sum(1 for pid in self._weights if pid not in self._folded)
        meta = self._action_meta.get(player_id, {})
        size_bucket = str(meta.get('bet_size_bucket') or 'none')
        is_raise_over = bool(meta.get('is_raise_over') or False)
        w = self._weights.get(player_id)
        if w is None:
            return

        board_ints = self._board_ints(board)
        categories = self._get_categories(board)
        cat_indices = np.array(
            [_BUCKET_CAL_IDX.get(cat, -1) for cat in categories],
            dtype=np.int8,
        )
        blocked = self._blocked_mask(board_ints)

        def _eligible_mask() -> np.ndarray:
            return (w > 1e-12) & (~blocked) & (cat_indices >= 0)

        def _bucket_mass_vec() -> np.ndarray:
            eligible = _eligible_mask()
            return np.bincount(
                cat_indices[eligible],
                weights=w[eligible],
                minlength=len(_BUCKET_CAL_CATS),
            ).astype(np.float64, copy=False)

        def _apply_target(target: np.ndarray, source: np.ndarray) -> bool:
            factors = np.ones(len(_BUCKET_CAL_CATS), dtype=np.float64)
            live = source > 1e-8
            factors[live] = target[live] / source[live]
            np.clip(factors, _BUCKET_CAL_MIN_FACTOR, _BUCKET_CAL_MAX_FACTOR,
                    out=factors)
            eligible = _eligible_mask()
            combo_factors = factors[cat_indices[eligible]]
            changed_local = bool(np.any(np.abs(combo_factors - 1.0) > 1e-9))
            if changed_local:
                w[eligible] *= combo_factors
                s_local = float(w.sum())
                if s_local > 1e-15:
                    w[:] = w / s_local
            return changed_local

        bucket_mass = _bucket_mass_vec()

        total = float(bucket_mass.sum())
        if total <= 1e-15:
            return
        p = bucket_mass / total
        range_threshold = (1.0 / 1326) * 0.1
        range_pct = float((w > range_threshold).sum()) / 1326
        ml_target, _diag = calibrate_bucket_probs(
            {cat: float(val) for cat, val in zip(_BUCKET_CAL_CATS, p)},
            street=street,
            trigger=trigger,
            active_count=active_count,
            board=list(board),
            range_pct=range_pct,
            known_cards=self._known_cards,
            position=str(meta.get('position') or ''),
            is_ip=bool(meta.get('is_ip') or False),
            facing_action=str(meta.get('facing_action') or ''),
            preflop_action_type=str(meta.get('preflop_action_type') or ''),
            action_bet_ratio=float(meta.get('action_bet_ratio') or 0.0),
            bet_size_bucket=size_bucket,
            is_raise_over=is_raise_over,
            action_sequence=str(meta.get('action_sequence') or ''),
            player_profile=profile_feature_dict(self._player_profiles.get(player_id)),
        )
        if ml_target:
            target = np.array(
                [float(ml_target.get(cat, 0.0) or 0.0) for cat in _BUCKET_CAL_CATS],
                dtype=np.float64,
            )
            target_sum = float(target.sum())
            if target_sum > 1e-15:
                # Read-only overlay: remember the formula state first so the
                # next observe_action / reweight_for_board starts from it.
                self._formula_weights[player_id] = w.copy()
                _apply_target(target / target_sum, p)

    def reset_hand(self, player_id: int, position: str,
                   profile: PlayerProfile) -> None:
        """Start a new hand for this player: every combo he can hold is equally likely.

        What he holds is told by what he then does (the fitted preflop likelihood), not
        assumed from his statistics before he has acted: a big blind who is checked to, or a
        player still to act, can have any two cards.
        """
        if not position:
            position = 'CO'
        self._player_profiles[player_id] = profile
        self._formula_weights.pop(player_id, None)

        w = np.ones(1326, dtype=np.float64)
        w[hcm.blocked_by(self._known_cards)] = 0.0       # card removal: my hole cards
        total = w.sum()
        if total > 0:
            w /= total

        self._weights[player_id] = w
        self._action_meta[player_id] = {
            'position': position,
            'is_ip': False,
            'facing_action': 'none',
            'preflop_action_type': 'reset',
            'action_bet_ratio': 0.0,
            'bet_size_bucket': 'none',
            'is_raise_over': False,
            'action_sequence': '',
        }
        # The player's own actions in this hand, read by the fitted likelihood ("bet the
        # street before", "checked earlier on this street").  Starts fresh every hand.
        self._action_history[player_id] = []

        self._emit_prediction(player_id, 'preflop', [], 'reset')

    def reweight_for_board(self, board: List[Card]) -> None:
        """New community cards: emit a ``board:<street>`` calibration
        prediction for every live opponent.

        The weight floor that used to live here (raising every nuts/strong
        combo to 1.5–2.85× the average weight) was removed on 2026-11-09:
        scored against revealed showdown hands it inflated the predicted
        nuts+strong mass on every street (flop 0.237 vs 0.213 actual, turn
        0.368 vs 0.311, river 0.520 vs 0.432) and over-stated P(villain beats
        hero) on the river by 0.06; without it the masses match (0.195 /
        0.306 / 0.446). The postflop likelihoods already keep low-prior
        board-made combos alive.
        """
        if not board or len(board) < 3:
            return
        for pid, formula_w in list(self._formula_weights.items()):
            if pid in self._weights:
                self._weights[pid] = formula_w
        self._formula_weights.clear()

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
            self._apply_bucket_calibration(
                pid, inferred_street, board, f'board:{inferred_street}'
            )
            self._emit_prediction(pid, inferred_street, board,
                                  f'board:{inferred_street}')

    def observe_action(self, player_id: int, action: str, street: str,
                       context: ActionContext, profile: PlayerProfile,
                       board: List[Card]) -> None:
        """Bayesian update of one player's range on one action, then floor mixing.

        w *= likelihood, the likelihood being the fitted model (fitted_likelihood.py) for the
        street: by preflop strength bin before the flop, by strength bucket after it.  It is
        fitted through this very update, so it is applied as it is.  Then a share λ of a
        uniform range is mixed in, so no hand is ever ruled out.
        """

        if player_id not in self._weights:
            self.reset_hand(player_id, context.position or 'CO', profile)
        if context.big_blind <= 0 and self._big_blind:
            context.big_blind = float(self._big_blind)

        self._player_profiles[player_id] = profile
        formula_w = self._formula_weights.pop(player_id, None)
        if formula_w is not None:
            self._weights[player_id] = formula_w
        w = self._weights[player_id]
        trace: Optional[Dict[str, Any]] = None
        self.last_update_trace = {}
        # Postflop every update is traced (bucket shares after each step).  Preflop only for
        # the training-row extractor (shares per preflop strength bin): in play it would add
        # a trace to every preflop action in the log.
        if (board and len(board) >= 3) or (street == 'preflop' and self.keep_update_weights):
            trace = {
                'street': street, 'action': action,
                'bet_ratio': round(float(context.bet_ratio or 0.0), 3),
                'layers': {},
            }
            self._trace_layer(trace, 'pre', w, board)

        # Card removal: board cards
        if board:
            board_ints = self._board_ints(board)
            all_known = self._known_cards | board_ints
            w[self._blocked_mask(all_known)] = 0.0

        if trace is not None and self.keep_update_weights:
            self.last_update_weights = w.copy()

        # What the fitted likelihood may depend on.  Computed here, once, and recorded in the
        # trace: the model is fitted on exactly these values.
        label = action_label(action, bool(context.is_raise_over))
        context.likelihood_features = None
        if street == 'preflop':
            pre_label = preflop_label(context.preflop_action_type, action)
            if pre_label is not None:
                context.likelihood_features = preflop_features(
                    label=pre_label, action_type=context.preflop_action_type,
                    position=context.position or '', bet_ratio=float(context.bet_ratio or 0.0),
                    is_raise_over=bool(context.is_raise_over), hands_seen=profile.hands_seen,
                    vpip=profile.vpip, pfr=profile.pfr, aggression_factor=profile.af,
                    history=self._action_history.get(player_id, []),
                )
            if trace is not None:
                trace['preflop_label'] = pre_label
        elif label in LIKELIHOOD_ACTIONS:
            context.likelihood_features = likelihood_features(
                action=label, street=street, bet_ratio=float(context.bet_ratio or 0.0),
                players_in_pot=sum(1 for pid in self._weights if pid not in self._folded),
                in_position=bool(context.is_ip), hands_seen=profile.hands_seen,
                vpip=profile.vpip, aggression_factor=profile.af,
                history=self._action_history.get(player_id, []),
            )
        if trace is not None:
            trace['features'] = context.likelihood_features

        # Compute likelihoods for all 1326 combos
        hero_cards = (
            [hcm.int_to_card(i) for i in self._known_cards]
            if self._known_cards else None
        )
        likelihoods = self.action_model.batch_likelihood(
            action, street, context, profile, board, hero_cards=hero_cards
        )

        # The likelihood is fitted through this very update, so it is applied as it is.
        w *= likelihoods

        # Normalize
        total = w.sum()
        if total > 1e-15:
            w /= total
        else:
            w = np.ones(1326, dtype=np.float64)
            all_known = set(self._known_cards)
            if board:
                all_known |= self._board_ints(board)
            w[self._blocked_mask(all_known)] = 0.0
            s = w.sum()
            if s > 0:
                w /= s
            else:
                w[:] = 1.0 / 1326

        # ── Posterior regularization (floor mixing) ──
        # 2026-04-23：Grünwald SafeBayes prior mixing——
        # α 管"单次更新激进度"、floor mixing 管"累积集中度上限"。
        # 混入 λ 的"对 active combos 均匀分布"，阻止连续 pot-size barrels
        # 把 air 权重压到 ~0。
        lam = 0.08
        self._trace_layer(trace, 'likelihood', w, board)
        if trace is not None:
            trace['lam'] = round(float(lam), 4)
        if lam > 1e-6:
            active_mask = w > 0
            n_active = int(active_mask.sum())
            if n_active > 0:
                uniform = np.zeros_like(w)
                uniform[active_mask] = 1.0 / n_active
                self._trace_layer(trace, 'uniform', uniform, board)
                w = (1.0 - lam) * w + lam * uniform

        # ── Probability floor: no combo drops below floor ──
        # 有了 floor mixing 这一层基本不做事（mixing 后每个 active combo 至少
        # λ/n_active ≈ 8e-5，超过 1e-4/n_active 的 floor 阈值），保留为兜底。
        active = w > 0
        n_active = int(active.sum())
        if n_active > 0:
            floor = 1e-4 / n_active
            below = active & (w < floor)
            if below.any():
                w[below] = floor
                w /= w.sum()

        self._trace_layer(trace, 'floor', w, board)

        # Refine action: distinguish 'bet' (first) from 'raise_over' (re-raise/CR).
        if action == 'raise':
            refined = _ACT_RAISE_OVER if context.is_raise_over else _ACT_BET
        elif action in ('call', 'check', 'fold'):
            refined = action
        else:
            refined = action

        history = self._action_history.setdefault(player_id, [])
        history.append((street, refined))
        action_sequence = _action_sequence_key(history)

        existing_meta = self._action_meta.get(player_id, {})
        position = context.position or str(existing_meta.get('position') or '') or 'CO'
        preflop_action_type = (
            context.preflop_action_type
            or _preflop_action_type(action, context)
            or str(existing_meta.get('preflop_action_type') or '')
        )
        self._action_meta[player_id] = {
            'position': position,
            'is_ip': bool(context.is_ip),
            'facing_action': context.facing_action or '',
            'preflop_action_type': preflop_action_type,
            'action_bet_ratio': float(context.bet_ratio or 0.0),
            'bet_size_bucket': _bet_size_bucket(context.bet_ratio),
            'is_raise_over': bool(context.is_raise_over),
            'action_sequence': action_sequence,
        }
        self._weights[player_id] = w
        self._apply_bucket_calibration(
            player_id, street, board, f'action:{refined}'
        )
        if trace is not None:
            self._trace_layer(trace, 'bucket_cal', self._weights[player_id], board)
            self.last_update_trace = trace

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
        meta = self._action_meta.get(player_id, {})
        try:
            self._prediction_hook(
                player_id=player_id, player_name=name,
                street=street, board=list(board),
                weights=w, hero_cards=hero_cards, trigger=trigger,
                active_weights=active_weights,
                position=str(meta.get('position') or ''),
                is_ip=bool(meta.get('is_ip') or False),
                facing_action=str(meta.get('facing_action') or ''),
                preflop_action_type=str(meta.get('preflop_action_type') or ''),
                action_bet_ratio=float(meta.get('action_bet_ratio') or 0.0),
                bet_size_bucket=str(meta.get('bet_size_bucket') or ''),
                is_raise_over=bool(meta.get('is_raise_over') or False),
                action_sequence=str(meta.get('action_sequence') or ''),
                player_profile=profile_feature_dict(self._player_profiles.get(player_id)),
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
        return self._vs_hero_from_weights(w, board, hero_cards)

    def _vs_hero_from_weights(self, w: np.ndarray, board: List[Card],
                              hero_cards: List[Card]) -> Dict[str, float]:
        """``get_vs_hero_dist`` for an explicit weight vector (layer trace)."""
        if not board or len(board) < 5 or not hero_cards or len(hero_cards) < 2:
            return {}
        board_ints = self._board_ints(board)
        hero_ints = {hcm.card_to_int(c) for c in hero_cards}
        all_known = self._known_cards | board_ints | hero_ints
        valid = w.copy()
        valid[self._blocked_mask(all_known)] = 0.0
        total = valid.sum()
        if total < 1e-15:
            return {}
        valid /= total

        hero_score = HandEvaluator.eval_int(list(hero_cards) + list(board))
        win_w = tie_w = loss_w = 0.0
        nz = np.flatnonzero(valid)
        # Every combo's river strength depends only on the board, so it is
        # scored once per board (shared by all players and trace layers)
        # instead of re-evaluated ~1000 times per call. The accumulation
        # order below is unchanged, so the sums are bit-identical.
        scores = _river_combo_scores(board)
        valid_l = valid.tolist()
        for idx in nz.tolist():
            opp_score = scores[idx]
            p = valid_l[idx]
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
        board_ints = self._board_ints(board) if board else set()
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

    def _bucket_mass_from_weights(self, w: np.ndarray, board: List[Card]) -> Dict[str, float]:
        """Mass of every strength bucket for a weight vector (layer trace)."""
        if not board or len(board) < 3:
            return {}
        cats = np.asarray(self._get_categories(board))
        board_ints = self._board_ints(board)
        valid = w.copy()
        valid[self._blocked_mask(self._known_cards | board_ints)] = 0.0
        total = float(valid.sum())
        if total <= 1e-15:
            return {}
        out: Dict[str, float] = {}
        for cat in ('nuts', 'strong', 'medium', 'draw', 'weak_draw', 'air'):
            out[cat] = round(float(valid[cats == cat].sum()) / total, 4)
        return out

    def _trace_layer(self, trace: Optional[Dict[str, Any]], name: str,
                     w: np.ndarray, board: List[Card]) -> None:
        if trace is None:
            return
        if not board:
            total = float(w.sum())
            mass = np.bincount(preflop_bin_index(), weights=w, minlength=len(PREFLOP_BINS)) / (total or 1.0)
            trace['layers'][name] = {b: round(float(v), 5) for b, v in zip(PREFLOP_BINS, mass)}
            return
        entry: Dict[str, Any] = dict(self._bucket_mass_from_weights(w, board))
        if len(board) >= 5 and len(self._known_cards) >= 2:
            hero_cards = [hcm.int_to_card(i) for i in sorted(self._known_cards)]
            rel = self._vs_hero_from_weights(w, board, hero_cards)
            if rel:
                entry['loss'] = round(float(rel.get('loss', 0.0)), 4)
        trace['layers'][name] = entry

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
