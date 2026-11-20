"""RangeEquityCalculator.equity_when_behind: hero's equity if an opponent always has him beat now."""

import numpy as np
import pytest

from pokerfate.core.card import Card
from pokerfate.strategy.postflop import PostflopStrategy
from pokerfate.strategy.range_v2 import hand_combo_map as hcm
from pokerfate.strategy.range_v2.range_equity_calculator import RangeEquityCalculator


def cards(*xs):
    return [Card.from_str(x) for x in xs]


def weights_for(*hands):
    w = np.zeros(1326)
    for a, b in hands:
        ia, ib = hcm.card_to_int(Card.from_str(a)), hcm.card_to_int(Card.from_str(b))
        w[hcm.COMBO_TO_IDX[(min(ia, ib), max(ia, ib))]] = 1.0
    return w


UNIFORM = np.ones(1326)


def test_nut_flush_draw_keeps_its_outs_against_hands_that_beat_it():
    # hand 374's turn: against a pair of fives the nine hearts and two tens win
    got = RangeEquityCalculator.equity_when_behind(
        cards('Ah', 'Tc'), cards('5h', 'Kh', '9h', '8c'), [weights_for(('As', '5s'))], 4000, seed=1,
    )
    assert got == pytest.approx(11 / 44, abs=0.03)


def test_bluff_catcher_is_worth_little_when_behind():
    turn = RangeEquityCalculator.equity_when_behind(
        cards('9s', '8s'), cards('Ad', '9c', '4h', '2d'), [UNIFORM], 4000, seed=1,
    )
    assert turn is not None and turn < 0.15


def test_ahead_samples_are_left_out():
    # against one hand that hero beats and one that beats him, only the second counts:
    # KK vs AA on a dry turn has two outs
    got = RangeEquityCalculator.equity_when_behind(
        cards('Ks', 'Kc'), cards('7d', '8c', '2h', '3s'),
        [weights_for(('As', 'Ac'), ('Qs', 'Qc'))], 4000, seed=1,
    )
    assert got == pytest.approx(2 / 44, abs=0.02)


def test_not_measurable_cases_return_none():
    calc = RangeEquityCalculator.equity_when_behind
    # river: nothing to come
    assert calc(cards('Ah', 'Tc'), cards('5h', 'Kh', '9h', '8c', '2d'), [UNIFORM], 500, seed=1) is None
    # preflop / no ranges
    assert calc(cards('Ah', 'Tc'), [], [UNIFORM], 500, seed=1) is None
    assert calc(cards('Ah', 'Tc'), cards('5h', 'Kh', '9h', '8c'), [], 500, seed=1) is None
    # hero is ahead of the whole range
    assert calc(cards('As', 'Ac'), cards('Ad', '9c', '4h', '2d'), [weights_for(('Ks', 'Kc'))], 500, seed=1) is None
    # the opponent's range is impossible given the known cards
    assert calc(cards('As', 'Ac'), cards('Ad', '9c', '4h', '2d'), [weights_for(('As', 'Kc'))], 500, seed=1) is None


def test_two_opponents_each_from_their_own_range():
    # one opponent already has hero beat, the other has a hand hero beats: still counted as behind,
    # and hero has to beat both at the end (a ten now gives QJ a straight, so only the nine hearts win)
    got = RangeEquityCalculator.equity_when_behind(
        cards('Ah', 'Tc'), cards('5h', 'Kh', '9h', '8c'),
        [weights_for(('As', '5s')), weights_for(('Jc', 'Qd'))], 4000, seed=1,
    )
    assert got == pytest.approx(9 / 42, abs=0.03)


def test_same_seed_same_answer():
    args = (cards('Ah', 'Tc'), cards('5h', 'Kh', '9h', '8c'), [UNIFORM, UNIFORM], 800)
    assert RangeEquityCalculator.equity_when_behind(*args, seed=5) == RangeEquityCalculator.equity_when_behind(*args, seed=5)


def test_postflop_decide_passes_the_floor_to_the_all_in_rule():
    """Hand 374 through the strategy wrapper: fold without the floor, call with it."""
    strat = PostflopStrategy()
    kwargs = dict(
        equity=0.25, pot=1_855_000.0, to_call=395_000.0, stack=395_000.0,
        board=cards('5h', 'Kh', '9h', '8c'), is_ip=True, street='turn', facing_bet=True,
        num_opponents=2, big_blind=20000.0, hole_cards=cards('Ah', 'Tc'), decision_seed=11,
    )
    action, _ = strat.decide(**kwargs)
    without = strat._last_cbet_detail.get('reason')
    assert action == 'fold' and 'all-in robust fold' in without
    action, amount = strat.decide(equity_when_behind=0.24, **kwargs)
    assert action == 'call' and amount == 395_000.0
    assert 'behind_eq=0.24' in strat._last_cbet_detail.get('reason')
