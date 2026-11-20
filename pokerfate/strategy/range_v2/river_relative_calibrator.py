"""Helpers for the river-only hero-relative strength signal.

The signal is ``villain_vs_hero_dist``:

    {'win': hero beats villain, 'tie': split, 'loss': villain beats hero}

The learned calibration layer that used to live here was removed on
2026-11-11; what remains are the relation helpers, exact win/tie/loss bounds
for locked hands, and the board-texture key used by the showdown recorder.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Tuple

from pokerfate.core.card import Card
from pokerfate.core.hand_evaluator import HandEvaluator
from pokerfate.strategy.range_v2 import hand_combo_map as hcm


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
