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


class TestBBBigBlindOption:
    """BB-specific decision logic: free check or iso-raise when no one raised."""

    strat = PreflopStrategy()

    def test_bb_facing_no_raise_checks_junk(self):
        """BB with off-range junk checks (never folds) when no raise."""
        action, amount = self.strat.decide(
            hole_cards=cards('7c', '2d'),
            position='BB',
            facing_action='none',
            open_raise=0,
            is_ip=False,
            big_blind=2.0,
            stack=200.0,
            pot=3.0,
            is_big_blind=True,
            num_limpers=0,
        )
        assert action == 'check'
        assert amount == 0.0

    def test_bb_facing_no_raise_never_folds(self):
        """BB must never fold when facing_action='none' (no raise to face)."""
        junk_hands = [
            cards('7c', '2d'), cards('8h', '3s'), cards('6d', '4c'), cards('5s', '2h'),
        ]
        for hand in junk_hands:
            action, _ = self.strat.decide(
                hole_cards=hand,
                position='BB',
                facing_action='none',
                open_raise=0,
                is_ip=False,
                big_blind=2.0,
                stack=200.0,
                pot=3.0,
                is_big_blind=True,
                num_limpers=1,
            )
            assert action != 'fold', f"BB must not fold with {hand} vs limpers"

    def test_bb_iso_raises_premium_hand(self):
        """BB iso-raises a premium hand when facing limpers."""
        action, amount = self.strat.decide(
            hole_cards=cards('Ac', 'Ad'),
            position='BB',
            facing_action='none',
            open_raise=0,
            is_ip=False,
            big_blind=2.0,
            stack=200.0,
            pot=5.0,
            is_big_blind=True,
            num_limpers=1,
        )
        assert action == 'raise'
        assert amount > 0

    def test_bb_iso_sizing_scales_with_limpers(self):
        """Iso-raise size = (2 + limpers) * BB."""
        # 1 limper → 3 BB
        _, size1 = self.strat.decide(
            hole_cards=cards('Ac', 'Ad'),
            position='BB',
            facing_action='none',
            open_raise=0,
            is_ip=False,
            big_blind=2.0,
            stack=200.0,
            pot=5.0,
            is_big_blind=True,
            num_limpers=1,
        )
        assert size1 == 2.0 * 3  # (2+1)*2

        # 2 limpers → 4 BB
        _, size2 = self.strat.decide(
            hole_cards=cards('Kc', 'Kd'),
            position='BB',
            facing_action='none',
            open_raise=0,
            is_ip=False,
            big_blind=2.0,
            stack=200.0,
            pot=7.0,
            is_big_blind=True,
            num_limpers=2,
        )
        assert size2 == 2.0 * 4  # (2+2)*2

    def test_bb_iso_range_includes_pairs_and_broadway(self):
        """BB iso-raise range should include key pocket pairs and broadway hands."""
        from pokerfate.strategy.preflop import _BB_ISO_RAISE
        # Pocket pairs
        assert 'AA' in _BB_ISO_RAISE
        assert 'KK' in _BB_ISO_RAISE
        assert 'QQ' in _BB_ISO_RAISE
        # Suited broadway
        assert 'AKs' in _BB_ISO_RAISE
        assert 'AQs' in _BB_ISO_RAISE
        # Offsuit big hands
        assert 'AKo' in _BB_ISO_RAISE

    def test_bb_no_iso_with_speculative_hand(self):
        """BB with speculative hand (e.g. 54s) just checks — not in iso range."""
        action, _ = self.strat.decide(
            hole_cards=cards('5c', '4c'),
            position='BB',
            facing_action='none',
            open_raise=0,
            is_ip=False,
            big_blind=2.0,
            stack=200.0,
            pot=5.0,
            is_big_blind=True,
            num_limpers=1,
        )
        assert action == 'check'
