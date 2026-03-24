"""Tests for preflop strategy."""

import pytest
from pokerfate.core.card import Card
from pokerfate.strategy.preflop import PreflopStrategy, _hand_category


def cards(*strs):
    return [Card.from_str(s) for s in strs]


class TestHandCategory:
    def test_pocket_pair(self):
        assert _hand_category(cards('Ac', 'Ad')) == 'AA'
        assert _hand_category(cards('2c', '2d')) == '22'

    def test_suited(self):
        assert _hand_category(cards('Ac', 'Kc')) == 'AKs'
        assert _hand_category(cards('Kh', 'Ah')) == 'AKs'  # order independent

    def test_offsuit(self):
        assert _hand_category(cards('Ac', 'Kd')) == 'AKo'
        assert _hand_category(cards('7d', '2c')) == '72o'


class TestOpenRange:
    strat = PreflopStrategy()

    def test_AA_in_all_positions(self):
        for pos in ['UTG', 'HJ', 'CO', 'BTN', 'SB', 'BB']:
            assert self.strat.in_open_range(cards('Ac', 'Ad'), pos)

    def test_72o_not_in_utg(self):
        assert not self.strat.in_open_range(cards('7c', '2d'), 'UTG')

    def test_72o_not_in_btn(self):
        # 72o should not be in BTN range either
        assert not self.strat.in_open_range(cards('7c', '2d'), 'BTN')

    def test_btn_wider_than_utg(self):
        # Some hands that are BTN open but not UTG
        t9s = cards('Tc', '9c')
        assert self.strat.in_open_range(t9s, 'BTN')
        # JTs should be in UTG
        jts = cards('Jc', 'Tc')
        assert self.strat.in_open_range(jts, 'UTG')

    def test_preflop_open_decision(self):
        # AA should raise from UTG
        action, amount = self.strat.decide(
            hole_cards=cards('Ac', 'Ad'),
            position='UTG',
            facing_action='none',
            open_raise=0,
            is_ip=False,
            big_blind=2.0,
            stack=200.0,
            pot=3.0,
        )
        assert action == 'raise'
        assert amount > 0

    def test_preflop_fold_junk(self):
        action, _ = self.strat.decide(
            hole_cards=cards('7c', '2d'),
            position='UTG',
            facing_action='none',
            open_raise=0,
            is_ip=False,
            big_blind=2.0,
            stack=200.0,
            pot=3.0,
        )
        assert action == 'fold'

    def test_3bet_value_hands(self):
        # AA should always 3-bet
        for _ in range(10):
            assert self.strat.should_3bet(cards('Ac', 'Ad'), 'BB', 'BTN')

    def test_4bet_AA(self):
        for _ in range(10):
            assert self.strat.should_4bet(cards('Ac', 'Ad'))

    def test_open_raise_sizing(self):
        size = self.strat.open_raise_size('BTN', 2.0)
        assert size == 5.0  # 2.5 BB

        size = self.strat.open_raise_size('UTG', 2.0)
        assert size == 6.0  # 3 BB
