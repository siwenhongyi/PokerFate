"""River hero-relative strength calibration.

This calibrates the river-only ``villain_vs_hero_dist`` signal:

    {'win': hero beats villain, 'tie': split, 'loss': villain beats hero}

Unlike bucket/equity calibration, this layer does not try to learn "nuts" or
general equity.  It learns whether the current river relative showdown equity
is systematically high/low for a structural context, then shifts win/loss
mass while preserving the tie mass.
"""

from __future__ import annotations

import os as _os
from typing import Any, Dict, Iterable, List, Tuple

from pokerfate.core.card import Card


_MIN_SAMPLES_EXACT = int(_os.environ.get('PF_RIVER_REL_MIN_EXACT', '8'))
_MIN_SAMPLES_FALLBACK = int(_os.environ.get('PF_RIVER_REL_MIN_FALLBACK', '20'))
_MAX_SHIFT = float(_os.environ.get('PF_RIVER_REL_MAX_SHIFT', '0.25'))
_SHRINK_K = float(_os.environ.get('PF_RIVER_REL_SHRINK_K', '35'))


def relation_eq(dist: Dict[str, float] | None) -> float:
    """Hero showdown equity from a relative distribution."""
    rel = dist or {}
    return float(rel.get('win', 0.0) or 0.0) + 0.5 * float(rel.get('tie', 0.0) or 0.0)


def normalize_relation(dist: Dict[str, float] | None) -> Dict[str, float]:
    rel = {
        'win': max(0.0, float((dist or {}).get('win', 0.0) or 0.0)),
        'tie': max(0.0, float((dist or {}).get('tie', 0.0) or 0.0)),
        'loss': max(0.0, float((dist or {}).get('loss', 0.0) or 0.0)),
    }
    total = sum(rel.values())
    if total <= 1e-12:
        return {}
    return {k: v / total for k, v in rel.items()}


def relation_from_actual_eq(actual_eq: float | None) -> str:
    """Convert exact river hero-vs-villain result into win/tie/loss label."""
    if actual_eq is None:
        return ''
    actual = float(actual_eq)
    if actual >= 0.999:
        return 'win'
    if actual <= 0.001:
        return 'loss'
    return 'tie'


def action_ctx_from_trigger(trigger: str) -> str:
    if trigger in {'action:raise', 'action:raise_over'}:
        return 'raise'
    if trigger == 'action:bet':
        return 'bet'
    return 'passive'


def action_ctx_from_decision(
    *,
    facing_bet: bool,
    to_call: float,
    pot: float,
    observed_action: str = '',
) -> str:
    """Classify the villain pressure that produced the current decision.

    Prefer the tracked observed action.  Bet-size-only classification misses
    small raises over hero bets, which are still semantically raises.
    """
    if not facing_bet:
        return 'passive'
    if observed_action in {'raise', 'raise_over'}:
        return 'raise'
    if to_call <= 0:
        return 'passive'
    pot_before = max(1e-9, pot - to_call)
    return 'raise' if (to_call / pot_before) >= 1.0 else 'bet'


def board_texture_key(board: Iterable[Card] | None) -> str:
    cards = list(board or [])
    if len(cards) < 3:
        return 'pre'
    ranks = [c.rank for c in cards]
    suits = [c.suit for c in cards]
    paired = len(set(ranks)) < len(ranks)
    if len(suits) >= 3 and len(set(suits[:3])) == 1:
        flush = 'mono'
    elif len(suits) >= 3 and max(suits[:3].count(s) for s in set(suits[:3])) >= 2:
        flush = 'fd'
    else:
        flush = 'rainbow'
    return ('paired' if paired else 'unpaired') + ':' + flush


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, float(x)))


def _shift_relation_eq(dist: Dict[str, float], target_eq: float) -> Dict[str, float]:
    """Return a relation dist with requested hero equity, preserving tie mass."""
    rel = normalize_relation(dist)
    if not rel:
        return {}
    tie = rel.get('tie', 0.0)
    non_tie = max(0.0, 1.0 - tie)
    target_win = _clamp01(target_eq - 0.5 * tie)
    target_win = min(non_tie, target_win)
    return {
        'win': target_win,
        'tie': tie,
        'loss': max(0.0, non_tie - target_win),
    }


def exact_relation_bounds(
    hero_cards: Iterable[Card] | None,
    board: Iterable[Card] | None,
) -> Dict[str, bool]:
    """Return which river outcomes are mathematically possible vs any hand.

    This is independent of villain range weights.  A calibration layer may
    learn biases in estimated ranges, but it must not create impossible poker
    outcomes, e.g. lowering a royal flush or nut-lock hand below 100%.
    """
    hero = list(hero_cards or [])
    board_l = list(board or [])
    if len(hero) < 2 or len(board_l) < 5:
        return {}

    from pokerfate.core.hand_evaluator import HandEvaluator
    from pokerfate.strategy.range_v2 import hand_combo_map as hcm

    known = {hcm.card_to_int(c) for c in hero + board_l}
    hero_score = HandEvaluator.eval_int(hero + board_l)
    possible = {'win': False, 'tie': False, 'loss': False}
    for c1, c2 in hcm.ALL_COMBOS:
        if c1 in known or c2 in known:
            continue
        opp = [hcm.int_to_card(c1), hcm.int_to_card(c2)]
        opp_score = HandEvaluator.eval_int(opp + board_l)
        if hero_score > opp_score:
            possible['win'] = True
        elif hero_score == opp_score:
            possible['tie'] = True
        else:
            possible['loss'] = True
        if possible['win'] and possible['tie'] and possible['loss']:
            break
    return possible


def clamp_relation_to_bounds(
    dist: Dict[str, float] | None,
    bounds: Dict[str, bool] | None,
) -> Dict[str, float]:
    """Remove impossible win/tie/loss mass and renormalize."""
    rel = normalize_relation(dist)
    if not rel or not bounds:
        return rel
    for key in ('win', 'tie', 'loss'):
        if bounds.get(key) is False:
            rel[key] = 0.0
    total = sum(rel.values())
    if total > 1e-12:
        return {k: v / total for k, v in rel.items()}

    possible = [k for k in ('win', 'tie', 'loss') if bounds.get(k)]
    if len(possible) == 1:
        return {
            'win': 1.0 if possible[0] == 'win' else 0.0,
            'tie': 1.0 if possible[0] == 'tie' else 0.0,
            'loss': 1.0 if possible[0] == 'loss' else 0.0,
        }
    return rel


def clamp_equity_to_bounds(
    equity: float,
    bounds: Dict[str, bool] | None,
) -> float:
    """Clamp scalar river equity to mathematical outcome bounds."""
    eq = _clamp01(equity)
    if not bounds:
        return eq
    win = bool(bounds.get('win'))
    tie = bool(bounds.get('tie'))
    loss = bool(bounds.get('loss'))
    if win and not tie and not loss:
        return 1.0
    if loss and not win and not tie:
        return 0.0
    if tie and not win and not loss:
        return 0.5
    if not loss:
        eq = max(eq, 0.5 if tie else 1.0)
    if not win:
        eq = min(eq, 0.5 if tie else 0.0)
    return _clamp01(eq)


class RiverRelativeCalibrator:
    """Online bias calibrator for river relative showdown equity."""

    def __init__(self) -> None:
        self._samples: Dict[str, List[Tuple[float, float]]] = {}
        self.last_diagnostic: Dict[str, Any] = {}

    def record(
        self,
        *,
        hero_bucket: str,
        hero_made_subtype: str,
        board_texture: str,
        action_ctx: str,
        predicted_dist: Dict[str, float] | None,
        actual_relation: str,
    ) -> None:
        rel = normalize_relation(predicted_dist)
        if not rel or actual_relation not in {'win', 'tie', 'loss'}:
            return
        actual_eq = 1.0 if actual_relation == 'win' else (0.5 if actual_relation == 'tie' else 0.0)
        pred_eq = relation_eq(rel)
        for key in self._keys(
            hero_bucket=hero_bucket,
            hero_made_subtype=hero_made_subtype,
            board_texture=board_texture,
            action_ctx=action_ctx,
        )[:2]:
            self._samples.setdefault(key, []).append((pred_eq, actual_eq))

    def calibrate_dist(
        self,
        dist: Dict[str, float] | None,
        *,
        hero_bucket: str,
        hero_made_subtype: str,
        board_texture: str,
        action_ctx: str,
        exact_bounds: Dict[str, bool] | None = None,
    ) -> Dict[str, float]:
        rel = clamp_relation_to_bounds(dist, exact_bounds)
        if not rel:
            self.last_diagnostic = {}
            return {}

        raw_eq = relation_eq(rel)
        if exact_bounds:
            hard_eq = clamp_equity_to_bounds(raw_eq, exact_bounds)
            if abs(hard_eq - raw_eq) > 1e-9 or (
                sum(1 for k in ('win', 'tie', 'loss') if exact_bounds.get(k)) == 1
            ):
                rel = clamp_relation_to_bounds(rel, exact_bounds)
                self.last_diagnostic = {
                    'used': False,
                    'raw_eq': round(raw_eq, 4),
                    'cal_eq': round(relation_eq(rel), 4),
                    'action_ctx': action_ctx,
                    'hard_bound': True,
                }
                return rel

        key, n, bias = self._best_bias(
            hero_bucket=hero_bucket,
            hero_made_subtype=hero_made_subtype,
            board_texture=board_texture,
            action_ctx=action_ctx,
        )
        if not key:
            self.last_diagnostic = {
                'used': False,
                'raw_eq': round(raw_eq, 4),
                'action_ctx': action_ctx,
            }
            return rel

        shift = max(-_MAX_SHIFT, min(_MAX_SHIFT, bias))
        if _SHRINK_K > 0:
            shift *= n / (n + _SHRINK_K)
        target = clamp_equity_to_bounds(_clamp01(raw_eq + shift), exact_bounds)
        out = clamp_relation_to_bounds(_shift_relation_eq(rel, target), exact_bounds)
        self.last_diagnostic = {
            'used': True,
            'key': key,
            'n': n,
            'bias': round(bias, 4),
            'shift': round(shift, 4),
            'raw_eq': round(raw_eq, 4),
            'cal_eq': round(relation_eq(out), 4),
            'action_ctx': action_ctx,
        }
        return out

    def sample_count(
        self,
        *,
        hero_bucket: str,
        hero_made_subtype: str,
        board_texture: str,
        action_ctx: str,
    ) -> int:
        key = self._keys(
            hero_bucket=hero_bucket,
            hero_made_subtype=hero_made_subtype,
            board_texture=board_texture,
            action_ctx=action_ctx,
        )[0]
        return len(self._samples.get(key, []))

    def _best_bias(
        self,
        *,
        hero_bucket: str,
        hero_made_subtype: str,
        board_texture: str,
        action_ctx: str,
    ) -> Tuple[str, int, float]:
        keys = self._keys(
            hero_bucket=hero_bucket,
            hero_made_subtype=hero_made_subtype,
            board_texture=board_texture,
            action_ctx=action_ctx,
        )
        for idx, key in enumerate(keys):
            samples = self._samples.get(key, [])
            need = _MIN_SAMPLES_EXACT if idx == 0 else _MIN_SAMPLES_FALLBACK
            if len(samples) >= need:
                bias = sum(actual - pred for pred, actual in samples) / len(samples)
                return key, len(samples), bias
        return '', 0, 0.0

    @staticmethod
    def _keys(
        *,
        hero_bucket: str,
        hero_made_subtype: str,
        board_texture: str,
        action_ctx: str,
    ) -> List[str]:
        hb = hero_bucket or '?'
        subtype = hero_made_subtype or '?'
        tex = board_texture or '?'
        act = action_ctx or 'passive'
        return [
            f'{hb}|{subtype}|{act}|{tex}',
            f'{hb}|{act}|{tex}',
            f'{hb}|{act}',
            f'{act}|{tex}',
            act,
        ]

    def to_dict(self) -> dict:
        return {k: list(v) for k, v in self._samples.items()}

    @classmethod
    def from_dict(cls, d: dict) -> 'RiverRelativeCalibrator':
        inst = cls()
        if not d:
            return inst
        for key, pairs in d.items():
            cleaned: List[Tuple[float, float]] = []
            for item in pairs:
                if isinstance(item, (list, tuple)) and len(item) == 2:
                    pred, actual = item
                    pred_f = float(pred)
                    actual_f = float(actual)
                    if 0.0 <= pred_f <= 1.0 and 0.0 <= actual_f <= 1.0:
                        cleaned.append((pred_f, actual_f))
            if cleaned:
                inst._samples[str(key)] = cleaned
        return inst
