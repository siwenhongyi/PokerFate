"""Tests for preflop strategy."""

import random

import pytest
from pokerfate.core.card import Card
from pokerfate.strategy import preflop as preflop_module
from pokerfate.strategy.preflop import (
    PreflopStrategy,
    _3BET_CALL_BY_POS,
    _3BET_CALL_DEFAULT,
    _hand_category,
    _normalize_position,
)


def cards(*strs):
    return [Card.from_str(s) for s in strs]


@pytest.fixture
def chart_expand_enabled(monkeypatch):
    monkeypatch.setattr(preflop_module, '_CHART_EXPAND_ENABLED', True)


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

    def test_bb1000_cheap_entry_calls_junk(self):
        action, amount = self.strat.decide(
            hole_cards=cards('7c', '2d'),
            position='UTG',
            facing_action='none',
            open_raise=0,
            is_ip=False,
            big_blind=1000.0,
            stack=200000.0,
            pot=1500.0,
            to_call=1000.0,
        )
        assert action == 'call'
        assert amount == pytest.approx(1000.0)
        assert self.strat.last_expand_reason == 'achievement_entry:bb1000 call<=4bb'

    def test_bb1000_cheap_entry_overrides_premium_raise(self):
        action, amount = self.strat.decide(
            hole_cards=cards('Ac', 'Ad'),
            position='BTN',
            facing_action='open',
            open_raise=3000.0,
            is_ip=True,
            big_blind=1000.0,
            stack=200000.0,
            pot=4500.0,
            to_call=3000.0,
            equity=0.85,
        )
        assert action == 'call'
        assert amount == pytest.approx(3000.0)

    def test_bb1000_cheap_entry_does_not_call_above_four_bb(self):
        action, _ = self.strat.decide(
            hole_cards=cards('7c', '2d'),
            position='BB',
            facing_action='open',
            open_raise=5000.0,
            is_ip=False,
            big_blind=1000.0,
            stack=200000.0,
            pot=2000.0,
            to_call=5000.0,
            equity=0.0,
        )
        assert action == 'fold'

    def test_3bet_value_hands(self):
        # AA should always 3-bet
        for _ in range(10):
            assert self.strat.should_3bet(cards('Ac', 'Ad'), 'BB', 'BTN')

    def test_4bet_AA(self):
        for _ in range(10):
            assert self.strat.should_4bet(cards('Ac', 'Ad'))

    def test_4bet_ako_downgrades_with_cold_caller(self):
        assert self.strat.should_4bet(cards('Ac', 'Kd'))
        assert not self.strat.should_4bet(
            cards('Ac', 'Kd'),
            cold_callers=1,
        )

    def test_squeeze_downgrades_boundary_value_3bet(self):
        assert self.strat.should_3bet(cards('Ac', 'Qd'), 'BTN', 'CO')
        assert not self.strat.should_3bet(
            cards('Ac', 'Qd'),
            'BTN',
            'CO',
            squeeze_callers=1,
        )

    def test_open_raise_sizing(self):
        size = self.strat.open_raise_size('BTN', 2.0)
        assert size == 5.0  # 2.5 BB

        size = self.strat.open_raise_size('UTG', 2.0)
        assert size == 6.0  # 3 BB

    def test_iso_raise_sizing_adds_limper_premium(self):
        # CO normal open is 2.5bb; vs 1 limper iso becomes 3.5bb.
        size = self.strat.iso_raise_size('CO', 2.0, num_limpers=1)
        assert size == pytest.approx(7.0)

        # UTG normal open is 3bb; vs 2 limpers iso becomes 5bb.
        size = self.strat.iso_raise_size('UTG', 2.0, num_limpers=2)
        assert size == pytest.approx(10.0)

        # Blinds add one extra OOP blind on top of the limper premium.
        size = self.strat.iso_raise_size('SB', 2.0, num_limpers=1)
        assert size == pytest.approx(10.0)

    def test_non_bb_limper_spot_uses_iso_sizing(self):
        action, amount = self.strat.decide(
            hole_cards=cards('Ac', 'Ad'),
            position='CO',
            facing_action='none',
            open_raise=0,
            is_ip=True,
            big_blind=2.0,
            stack=200.0,
            pot=5.0,
            num_limpers=1,
        )
        assert action == 'raise'
        assert amount == pytest.approx(7.0)

    def test_sb_iso_respects_chart_fold_veto(self):
        action, amount = self.strat.decide(
            hole_cards=cards('7h', '8c'),  # 87o
            position='SB',
            facing_action='none',
            open_raise=0,
            is_ip=False,
            big_blind=2.0,
            stack=200.0,
            pot=9.0,
            num_limpers=3,
            num_active_opponents=4,
        )
        assert (action, amount) == ('fold', 0.0)

    def test_sb_iso_allows_chart_raise(self):
        action, amount = self.strat.decide(
            hole_cards=cards('7s', '6s'),
            position='SB',
            facing_action='none',
            open_raise=0,
            is_ip=False,
            big_blind=2.0,
            stack=200.0,
            pot=5.0,
            num_limpers=1,
            num_active_opponents=2,
        )
        assert action == 'raise'
        assert amount == pytest.approx(10.0)
        assert self.strat.last_expand_reason == 'chart_iso:SB-ISO 76s'

    def test_limp_behind_does_not_replace_small_pair_iso(self):
        action, amount = self.strat.decide(
            hole_cards=cards('4s', '4d'),
            position='BTN',
            facing_action='none',
            open_raise=0,
            is_ip=True,
            big_blind=10.0,
            stack=1400.0,
            pot=45.0,
            to_call=10.0,
            num_limpers=3,
            stack_bb=140.0,
            sticky_density=0.50,
        )
        assert action == 'raise'
        assert amount == pytest.approx(55.0)
        assert self.strat.last_expand_reason == 'chart_iso:BTN-ISO 44'

    def test_limp_behind_does_not_replace_suited_connector_iso(self):
        action, amount = self.strat.decide(
            hole_cards=cards('7s', '6s'),
            position='BTN',
            facing_action='none',
            open_raise=0,
            is_ip=True,
            big_blind=10.0,
            stack=1000.0,
            pot=45.0,
            to_call=10.0,
            num_limpers=3,
            stack_bb=100.0,
            sticky_density=0.50,
        )
        assert action == 'raise'
        assert amount == pytest.approx(55.0)
        assert self.strat.last_expand_reason == 'chart_iso:BTN-ISO 76s'

    def test_limp_behind_adds_folded_suited_connector_with_one_limper(self):
        action, amount = self.strat.decide(
            hole_cards=cards('5s', '4s'),
            position='MP',
            facing_action='none',
            open_raise=0,
            is_ip=True,
            big_blind=10.0,
            stack=1000.0,
            pot=45.0,
            to_call=10.0,
            num_limpers=1,
            stack_bb=100.0,
            sticky_density=0.0,
        )
        assert action == 'call'
        assert amount == pytest.approx(10.0)
        assert 'limp_behind:suited_connector 54s' in self.strat.last_expand_reason

    def test_limp_behind_allows_moderate_stack_speculative_call(self):
        action, amount = self.strat.decide(
            hole_cards=cards('5s', '4s'),
            position='MP',
            facing_action='none',
            open_raise=0,
            is_ip=True,
            big_blind=10.0,
            stack=350.0,
            pot=45.0,
            to_call=10.0,
            num_limpers=3,
            stack_bb=35.0,
            sticky_density=0.50,
        )
        assert action == 'call'
        assert amount == pytest.approx(10.0)

    def test_btn_iso_allows_chart_raise_for_qto(self):
        action, amount = self.strat.decide(
            hole_cards=cards('Qh', 'Td'),
            position='BTN',
            facing_action='none',
            open_raise=0,
            is_ip=True,
            big_blind=2.0,
            stack=200.0,
            pot=5.0,
            num_limpers=1,
        )
        assert action == 'raise'
        assert amount == pytest.approx(7.0)

    def test_missing_iso_chart_uses_conservative_fallback_only(self):
        action, amount = self.strat.decide(
            hole_cards=cards('Ac', 'Ad'),
            position='UTG',
            facing_action='none',
            open_raise=0,
            is_ip=False,
            big_blind=2.0,
            stack=200.0,
            pot=5.0,
            num_limpers=1,
        )
        assert action == 'raise'
        assert amount == pytest.approx(8.0)
        assert self.strat.last_expand_reason == 'fallback_iso:UTG-ISO AA'

        action, amount = self.strat.decide(
            hole_cards=cards('8h', '7d'),  # 87o
            position='UTG',
            facing_action='none',
            open_raise=0,
            is_ip=False,
            big_blind=2.0,
            stack=200.0,
            pot=5.0,
            num_limpers=1,
        )
        assert (action, amount) == ('fold', 0.0)


class TestBBBigBlindOption:
    """Free-check fallback and BB-specific no-raise behavior."""

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
        """BB iso-raise adds limper premium plus OOP premium."""
        # 1 limper → 5 BB
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
        assert size1 == pytest.approx(2.0 * 5)

        # 2 limpers → 6 BB
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
        assert size2 == pytest.approx(2.0 * 6)

    def test_bb_free_option_uses_iso_chart_before_check_fallback(self):
        """BB free check is only the fallback after normal BB-ISO logic."""
        action, amount = self.strat.decide(
            hole_cards=cards('Kh', 'Th'),
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
        assert action == 'raise'
        assert amount == pytest.approx(12.0)
        assert self.strat.last_expand_reason == 'chart_iso:BB-ISO KTs'

    def test_bb_free_option_checks_when_iso_chart_folds(self):
        """BB with a true fold hand takes the free check instead of folding."""
        action, _ = self.strat.decide(
            hole_cards=cards('7c', '2d'),
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

    def test_free_check_option_rescues_fold_but_not_open_outside_bb(self):
        """Forced-post free option must not turn normal RFI hands into checks."""
        action, amount = self.strat.decide(
            hole_cards=cards('Ac', 'Ad'),
            position='MP',
            facing_action='none',
            open_raise=0,
            is_ip=False,
            big_blind=2.0,
            stack=200.0,
            pot=3.0,
            is_big_blind=True,
            num_limpers=0,
        )
        assert action == 'raise'
        assert amount > 0

        action, amount = self.strat.decide(
            hole_cards=cards('7c', '2d'),
            position='MP',
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


class TestNormalizePosition:
    """Canonical 6-max mapping + alias coverage + warn-on-unknown."""

    def test_canonical_positions_pass_through(self):
        for pos in ('UTG', 'MP', 'CO', 'BTN', 'SB', 'BB'):
            assert _normalize_position(pos) == pos

    def test_aliases_map_to_6max(self):
        assert _normalize_position('UTG+1') == 'MP'
        assert _normalize_position('UTG1') == 'MP'
        assert _normalize_position('UTG+2') == 'CO'
        assert _normalize_position('HJ') == 'CO'
        assert _normalize_position('LJ') == 'MP'
        assert _normalize_position('BU') == 'BTN'

    def test_empty_returns_empty(self):
        assert _normalize_position('') == ''
        assert _normalize_position(None) == ''

    def test_unknown_warns_and_returns_empty(self, caplog):
        with caplog.at_level('WARNING'):
            result = _normalize_position('FOO')
        assert result == ''
        assert any('unknown position' in r.message for r in caplog.records)


class TestThreeBetSizeMatrix:
    strat = PreflopStrategy()

    def test_btn_vs_bb_uses_matrix(self):
        # (open=BTN, 3bet=BB) → 4.4×. open_raise=5.0 → 3bet=22.0, floor 9×BB=18.
        size = self.strat.three_bet_size(
            5.0, is_ip=False, big_blind=2.0,
            open_pos='BTN', three_bet_pos='BB',
        )
        assert size == pytest.approx(22.0)

    def test_co_vs_btn_ip_uses_matrix_but_floor_wins(self):
        # (open=CO, 3bet=BTN) IP → 3.2×. open=5.0 → 3bet=16.0, floor 18 wins.
        size = self.strat.three_bet_size(
            5.0, is_ip=True, big_blind=2.0,
            open_pos='CO', three_bet_pos='BTN',
        )
        assert size == pytest.approx(18.0)

    def test_hj_alias_normalizes_to_co(self):
        """HJ is a 9-max alias; matrix lives in 6-max keys so normalize to CO."""
        via_hj = self.strat.three_bet_size(
            6.0, is_ip=False, big_blind=2.0,
            open_pos='HJ', three_bet_pos='BB',
        )
        via_co = self.strat.three_bet_size(
            6.0, is_ip=False, big_blind=2.0,
            open_pos='CO', three_bet_pos='BB',
        )
        assert via_hj == via_co

    def test_missing_pair_falls_back_to_ip_oop(self):
        big_ip = self.strat.three_bet_size(
            6.0, is_ip=True, big_blind=2.0,
            open_pos='', three_bet_pos='',
        )
        assert big_ip == pytest.approx(max(6.0 * 3.0, 18.0))
        big_oop = self.strat.three_bet_size(
            6.0, is_ip=False, big_blind=2.0,
            open_pos='', three_bet_pos='',
        )
        assert big_oop == pytest.approx(max(6.0 * 4.0, 18.0))


class TestFourBetSizeMatrix:
    strat = PreflopStrategy()

    def test_btn_open_vs_sb_3bet_ip_small(self):
        # Hero opened BTN, villain 3bet SB → hero IP 4bet 2.15×.
        size = self.strat.four_bet_size(
            last_raise_to=20.0, is_ip=True,
            hero_open_pos='BTN', villain_3bet_pos='SB',
        )
        assert size == pytest.approx(20.0 * 2.15)

    def test_utg_open_vs_btn_3bet_oop_large(self):
        # Hero opened UTG, villain 3bet BTN → hero OOP 4bet 2.45×.
        size = self.strat.four_bet_size(
            last_raise_to=20.0, is_ip=False,
            hero_open_pos='UTG', villain_3bet_pos='BTN',
        )
        assert size == pytest.approx(20.0 * 2.45)

    def test_sb_open_vs_bb_3bet_oop(self):
        # Special OOP row: SB opened, BB 3bet → 2.45×.
        # Review called out this missing test.
        size = self.strat.four_bet_size(
            last_raise_to=18.0, is_ip=False,
            hero_open_pos='SB', villain_3bet_pos='BB',
        )
        assert size == pytest.approx(18.0 * 2.45)

    def test_unknown_position_falls_back(self):
        # Both positions unknown → OOP fallback 2.45.
        size = self.strat.four_bet_size(
            last_raise_to=12.0, is_ip=False,
            hero_open_pos='', villain_3bet_pos='',
        )
        assert size == pytest.approx(12.0 * 2.45)
        # IP fallback 2.15.
        size_ip = self.strat.four_bet_size(
            last_raise_to=12.0, is_ip=True,
            hero_open_pos='', villain_3bet_pos='',
        )
        assert size_ip == pytest.approx(12.0 * 2.15)


@pytest.mark.usefixtures('chart_expand_enabled')
class TestFacingFourBetDefense:
    strat = PreflopStrategy()

    def test_greenline_allin_overrides_old_aks_call_fallback(self):
        action, amount = self.strat.decide(
            hole_cards=cards('Ac', 'Kc'),
            position='BB',
            facing_action='4bet',
            open_raise=420.0,
            is_ip=True,
            big_blind=10.0,
            stack=1_000.0,
            pot=500.0,
            to_call=300.0,
            equity=0.58,
            stack_bb=100.0,
            villain_position='CO',
        )

        assert action == 'raise'
        assert amount == pytest.approx(1_000.0)
        assert 'greenline' in self.strat.last_expand_reason

    def test_tt_calls_4bet_when_chart_and_equity_edge_are_clear(self):
        action, amount = self.strat.decide(
            hole_cards=cards('Tc', 'Td'),
            position='SB',
            facing_action='4bet',
            open_raise=580_000.0,
            is_ip=False,
            big_blind=10_000.0,
            stack=1_311_846.0,
            pot=735_000.0,
            to_call=440_000.0,
            equity=0.61,
            stack_bb=131.0,
            villain_position='UTG',
        )

        assert action == 'call'
        assert amount == pytest.approx(440_000.0)
        assert '4bet_defend' in self.strat.last_expand_reason

    def test_tt_still_folds_4bet_without_clear_equity_edge(self):
        action, amount = self.strat.decide(
            hole_cards=cards('Tc', 'Td'),
            position='SB',
            facing_action='4bet',
            open_raise=580_000.0,
            is_ip=False,
            big_blind=10_000.0,
            stack=1_311_846.0,
            pot=735_000.0,
            to_call=440_000.0,
            equity=0.49,
            stack_bb=131.0,
            villain_position='UTG',
        )

        assert action == 'fold'
        assert amount == 0.0

    def test_jj_folds_4bet_when_price_is_too_expensive(self):
        action, amount = self.strat.decide(
            hole_cards=cards('Jc', 'Jd'),
            position='SB',
            facing_action='4bet',
            open_raise=800.0,
            is_ip=False,
            big_blind=10.0,
            stack=2_000.0,
            pot=1_000.0,
            to_call=800.0,
            equity=0.62,
            stack_bb=200.0,
            villain_position='UTG',
        )

        assert action == 'fold'
        assert amount == 0.0

    def test_missing_greenline_4bet_chart_uses_fallback_only(self):
        action, amount = self.strat.decide(
            hole_cards=cards('Ac', '5c'),
            position='SB',
            facing_action='4bet',
            open_raise=800.0,
            is_ip=False,
            big_blind=10.0,
            stack=2_000.0,
            pot=700.0,
            to_call=300.0,
            equity=0.47,
            stack_bb=200.0,
            villain_position='UTG',
        )

        assert action == 'fold'
        assert amount == 0.0

        action, amount = self.strat.decide(
            hole_cards=cards('Ac', '5c'),
            position='SB',
            facing_action='4bet',
            open_raise=800.0,
            is_ip=False,
            big_blind=10.0,
            stack=2_000.0,
            pot=700.0,
            to_call=300.0,
            equity=0.42,
            stack_bb=200.0,
            villain_position='UTG',
        )

        assert action == 'fold'
        assert amount == 0.0

        action, amount = self.strat.decide(
            hole_cards=cards('Ac', '5c'),
            position='SB',
            facing_action='4bet',
            open_raise=800.0,
            is_ip=False,
            big_blind=10.0,
            stack=2_000.0,
            pot=700.0,
            to_call=300.0,
            equity=0.42,
            stack_bb=200.0,
            villain_position='UTG',
            fourbet_call_edge_adjust=-0.02,
        )

        assert action == 'fold'
        assert amount == 0.0

    def test_edge_adjust_only_changes_call_gate_not_hand_pool(self):
        action, amount = self.strat.decide(
            hole_cards=cards('Ac', '5c'),
            position='BTN',
            facing_action='4bet',
            open_raise=800.0,
            is_ip=True,
            big_blind=10.0,
            stack=2_000.0,
            pot=700.0,
            to_call=300.0,
            equity=0.60,
            stack_bb=200.0,
            villain_position='UTG',
            fourbet_call_edge_adjust=-0.03,
        )

        assert action == 'fold'
        assert amount == 0.0

    def test_positive_edge_adjust_tightens_existing_chart_call_gate(self):
        action, amount = self.strat.decide(
            hole_cards=cards('Ac', '5c'),
            position='SB',
            facing_action='4bet',
            open_raise=800.0,
            is_ip=False,
            big_blind=10.0,
            stack=2_000.0,
            pot=700.0,
            to_call=300.0,
            equity=0.45,
            stack_bb=200.0,
            villain_position='UTG',
            fourbet_call_edge_adjust=0.03,
        )

        assert action == 'fold'
        assert amount == 0.0

    def test_sticky_table_tightens_mixed_4bet_defend(self):
        action, amount = self.strat.decide(
            hole_cards=cards('Ac', '5c'),
            position='SB',
            facing_action='4bet',
            open_raise=800.0,
            is_ip=False,
            big_blind=10.0,
            stack=2_000.0,
            pot=700.0,
            to_call=300.0,
            equity=0.445,
            stack_bb=200.0,
            villain_position='UTG',
            sticky_density=0.5,
        )

        assert action == 'fold'
        assert amount == 0.0

    def test_no_chart_4bet_defend_only_allows_strong_fallback_edge(self):
        action, amount = self.strat.decide(
            hole_cards=cards('Tc', 'Td'),
            position='BTN',
            facing_action='4bet',
            open_raise=800.0,
            is_ip=True,
            big_blind=10.0,
            stack=2_000.0,
            pot=700.0,
            to_call=300.0,
            equity=0.60,
            stack_bb=200.0,
            villain_position='UTG',
        )

        assert action == 'call'
        assert amount == pytest.approx(300.0)

        action, amount = self.strat.decide(
            hole_cards=cards('Ac', '5c'),
            position='BTN',
            facing_action='4bet',
            open_raise=800.0,
            is_ip=True,
            big_blind=10.0,
            stack=2_000.0,
            pot=700.0,
            to_call=300.0,
            equity=0.60,
            stack_bb=200.0,
            villain_position='UTG',
        )

        assert action == 'fold'
        assert amount == 0.0


class TestBluff3BetFrequency:
    """Bluff 3bet rate depends on opener (villain) position."""

    strat = PreflopStrategy()

    def _bluff_rate(self, vs_pos: str, seed: int = 1234, trials: int = 400) -> float:
        # Set the global random.seed since should_3bet uses the module-level
        # random (not a local Random instance). We also re-seed here so each
        # call is reproducible independently. Note: running these tests in
        # parallel within one process will share state; pytest xdist workers
        # run in separate processes so cross-test pollution is bounded.
        random.seed(seed)
        hits = 0
        for _ in range(trials):
            # A5s is in _3BET_BLUFF
            if self.strat.should_3bet(cards('As', '5s'), 'BTN', vs_pos):
                hits += 1
        return hits / trials

    def test_vs_utg_bluffs_rarely(self):
        rate = self._bluff_rate('UTG')
        # Target 0.20 ± wide margin (seeded empirical).
        assert 0.10 <= rate <= 0.30, f"vs UTG expected ~0.20, got {rate}"

    def test_vs_btn_bluffs_more_than_vs_utg(self):
        # Margin 0.15 is ~1/3 of the nominal gap (0.65 - 0.20 = 0.45),
        # enough slack for seeded samples but tight enough to catch a regression.
        rate_btn = self._bluff_rate('BTN')
        rate_utg = self._bluff_rate('UTG')
        assert rate_btn > rate_utg + 0.15, (
            f"vs BTN ({rate_btn}) should bluff more than vs UTG ({rate_utg})"
        )

    def test_value_hand_always_3bets_regardless_of_position(self):
        for pos in ('UTG', 'BTN', 'SB'):
            for _ in range(10):
                assert self.strat.should_3bet(cards('Ac', 'Ad'), 'BTN', pos)


class TestThreeBetCallRangeByPos:
    """Hero's 3bet-defend range depends on hero's open position.

    Review P1: BB entry was missing and fell through to _3BET_CALL_DEFAULT.
    """

    strat = PreflopStrategy()

    def test_bb_defend_is_wider_than_default(self):
        # T9s should be in BB defend (BB has closing action IP post-flop).
        assert 'T9s' in _3BET_CALL_BY_POS['BB']
        assert 'T9s' not in _3BET_CALL_DEFAULT

    def test_utg_defend_is_narrow(self):
        # UTG defend should not include T9s or 98s (position disadvantage).
        assert 'T9s' not in _3BET_CALL_BY_POS['UTG']
        assert '98s' not in _3BET_CALL_BY_POS['UTG']

    def test_btn_defend_is_widest(self):
        for hand in ('T9s', '98s', '87s', 'JTs', 'KQo'):
            assert hand in _3BET_CALL_BY_POS['BTN']


@pytest.mark.usefixtures('chart_expand_enabled')
class TestPreflopChartExpandOverlay:
    """Chart-backed overlays only widen baseline folds in guarded spots."""

    strat = PreflopStrategy()

    def test_btn_kqo_3bets_co_small_open_before_equity_gate(self):
        action, amount = self.strat.decide(
            hole_cards=cards('Kc', 'Qd'),
            position='BTN',
            facing_action='open',
            open_raise=20.0,  # 2bb
            is_ip=True,
            big_blind=10.0,
            stack=1310.0,
            pot=40.0,
            to_call=20.0,
            stack_bb=131.0,
            villain_position='CO',
            equity=0.25,
        )
        assert action == 'raise'
        assert amount == pytest.approx(90.0)
        assert 'chart_expand:ip_3bet_small_open' in self.strat.last_expand_reason

    def test_btn_kqo_still_folds_vs_utg_large_open_low_equity(self):
        action, amount = self.strat.decide(
            hole_cards=cards('Kc', 'Qd'),
            position='BTN',
            facing_action='open',
            open_raise=30.0,  # 3bb, no chart overlay spot
            is_ip=True,
            big_blind=10.0,
            stack=1000.0,
            pot=45.0,
            to_call=30.0,
            stack_bb=100.0,
            villain_position='UTG',
            equity=0.18,
        )
        assert (action, amount) == ('fold', 0.0)
        assert self.strat.last_expand_reason == ''

    def test_utg_jts_calls_btn_3bet_when_deep_and_chart_supports_call(self):
        action, amount = self.strat.decide(
            hole_cards=cards('Jd', 'Td'),
            position='UTG',
            facing_action='3bet',
            open_raise=180.0,  # villain 3bet to 18bb
            is_ip=False,
            big_blind=10.0,
            stack=1200.0,
            pot=260.0,
            to_call=160.0,
            stack_bb=120.0,
            villain_position='BTN',
            equity=0.34,
        )
        assert action == 'call'
        assert amount == pytest.approx(160.0)
        assert 'chart_expand:deep_3bet_defend' in self.strat.last_expand_reason

    def test_utg_jts_overlay_disabled_when_short(self):
        action, amount = self.strat.decide(
            hole_cards=cards('Jd', 'Td'),
            position='UTG',
            facing_action='3bet',
            open_raise=180.0,
            is_ip=False,
            big_blind=10.0,
            stack=450.0,
            pot=260.0,
            to_call=160.0,
            stack_bb=45.0,
            villain_position='BTN',
            equity=0.34,
        )
        assert (action, amount) == ('fold', 0.0)
        assert 'chart_block:low_spr_3bet_call JTs' in self.strat.last_expand_reason

    def test_mid_stack_low_spr_blocks_speculative_chart_3bet_call(self):
        action, amount = self.strat.decide(
            hole_cards=cards('Jd', 'Td'),
            position='UTG',
            facing_action='3bet',
            open_raise=180.0,
            is_ip=False,
            big_blind=10.0,
            stack=600.0,
            pot=260.0,
            to_call=160.0,
            stack_bb=60.0,
            villain_position='BTN',
            equity=0.34,
        )

        assert (action, amount) == ('fold', 0.0)
        assert 'chart_block:low_spr_3bet_call JTs' in self.strat.last_expand_reason

    def test_chart_call_vetoes_static_tt_4bet(self):
        action, amount = self.strat.decide(
            hole_cards=cards('Th', 'Tc'),
            position='UTG',
            facing_action='3bet',
            open_raise=120_000.0,
            is_ip=False,
            big_blind=10_000.0,
            stack=520_000.0,
            pot=220_000.0,
            to_call=90_000.0,
            stack_bb=52.0,
            villain_position='BB',
            equity=0.38,
        )

        assert action == 'call'
        assert amount == pytest.approx(90_000.0)
        assert 'chart_expand:3bet_call greenline UTG-vs-3bet-BB TT' in self.strat.last_expand_reason

    def test_high_cost_chart_4bet_raise_falls_back_to_call_when_hand_can_defend(self):
        action, amount = self.strat.decide(
            hole_cards=cards('As', 'Qh'),
            position='SB',
            facing_action='3bet',
            open_raise=750_000.0,
            is_ip=False,
            big_blind=50_000.0,
            stack=4_150_000.0,
            pot=1_400_000.0,
            to_call=625_000.0,
            stack_bb=83.0,
            villain_position='BB',
            equity=0.37,
        )

        assert action == 'call'
        assert amount == pytest.approx(625_000.0)
        assert 'chart_block:high_cost_4bet AQo' in self.strat.last_expand_reason

    def test_high_cost_chart_4bet_raise_folds_when_hand_cannot_defend(self):
        action, amount = self.strat.decide(
            hole_cards=cards('Ac', '4c'),
            position='MP',
            facing_action='3bet',
            open_raise=600_000.0,
            is_ip=False,
            big_blind=50_000.0,
            stack=5_100_000.0,
            pot=825_000.0,
            to_call=450_000.0,
            stack_bb=102.0,
            villain_position='BTN',
            equity=0.36,
        )

        assert (action, amount) == ('fold', 0.0)
        assert 'chart_block:high_cost_4bet A4s' in self.strat.last_expand_reason

    def test_chart_allin_short_ako_jams_vs_3bet(self):
        action, amount = self.strat.decide(
            hole_cards=cards('As', 'Kh'),
            position='CO',
            facing_action='3bet',
            open_raise=110_000.0,
            is_ip=False,
            big_blind=10_000.0,
            stack=120_000.0,
            pot=264_000.0,
            to_call=70_000.0,
            stack_bb=12.0,
            villain_position='BB',
            equity=0.42,
        )

        assert action == 'raise'
        assert amount == pytest.approx(120_000.0)
        assert 'chart_expand:3bet_allin greenline CO-vs-3bet-BB AKo' in self.strat.last_expand_reason

    def test_tiny_3bet_price_overrides_chart_fold(self):
        action, amount = self.strat.decide(
            hole_cards=cards('Kc', 'Jh'),
            position='UTG',
            facing_action='3bet',
            open_raise=90.0,   # hero opened 8bb, villain makes it 9bb
            is_ip=False,
            big_blind=10.0,
            stack=1000.0,
            pot=185.0,
            to_call=10.0,
            stack_bb=100.0,
            villain_position='BB',
            equity=0.24,
        )

        assert action == 'call'
        assert amount == pytest.approx(10.0)
        assert 'price_call:tiny_3bet KJo' in self.strat.last_expand_reason

    def test_normal_3bet_chart_fold_still_folds(self):
        action, amount = self.strat.decide(
            hole_cards=cards('Kc', 'Jh'),
            position='UTG',
            facing_action='3bet',
            open_raise=240.0,
            is_ip=False,
            big_blind=10.0,
            stack=1000.0,
            pot=345.0,
            to_call=160.0,
            stack_bb=100.0,
            villain_position='BB',
            equity=0.24,
        )

        assert (action, amount) == ('fold', 0.0)

    def test_wide_three_bettor_expands_defend_range(self):
        action, amount = self.strat.decide(
            hole_cards=cards('Ah', 'Jc'),
            position='UTG',
            facing_action='3bet',
            open_raise=120.0,
            is_ip=False,
            big_blind=10.0,
            stack=1000.0,
            pot=210.0,
            to_call=90.0,
            stack_bb=100.0,
            villain_position='BTN',
            equity=0.38,
            villain_vpip=0.48,
            villain_pfr=0.30,
            villain_three_bet=0.14,
            villain_af=1.8,
            villain_hands_seen=40,
        )

        assert action == 'call'
        assert amount == pytest.approx(90.0)

    def test_narrow_three_bettor_does_not_expand_defend_range(self):
        action, amount = self.strat.decide(
            hole_cards=cards('Ah', 'Jc'),
            position='UTG',
            facing_action='3bet',
            open_raise=120.0,
            is_ip=False,
            big_blind=10.0,
            stack=1000.0,
            pot=210.0,
            to_call=90.0,
            stack_bb=100.0,
            villain_position='BTN',
            equity=0.38,
            villain_vpip=0.22,
            villain_pfr=0.12,
            villain_three_bet=0.03,
            villain_af=1.1,
            villain_hands_seen=40,
        )

        assert (action, amount) == ('fold', 0.0)

    def test_loose_aggressive_opener_expands_3bet(self):
        action, amount = self.strat.decide(
            hole_cards=cards('Kh', 'Qc'),
            position='BTN',
            facing_action='open',
            open_raise=30.0,
            is_ip=True,
            big_blind=10.0,
            stack=1000.0,
            pot=45.0,
            to_call=30.0,
            stack_bb=100.0,
            villain_position='CO',
            equity=0.42,
            villain_vpip=0.55,
            villain_pfr=0.32,
            villain_three_bet=0.10,
            villain_af=1.7,
            villain_hands_seen=50,
        )

        assert action == 'raise'
        assert amount > 30.0
        assert 'villain_expand:wide_open_3bet KQo' in self.strat.last_expand_reason

    def test_greenline_vs_open_squeeze_expands_suited_playable(self):
        action, amount = self.strat.decide(
            hole_cards=cards('Jd', '9d'),
            position='SB',
            facing_action='open',
            open_raise=30.0,
            is_ip=False,
            big_blind=10.0,
            stack=1080.0,
            pot=75.0,
            to_call=30.0,
            stack_bb=108.0,
            villain_position='MP',
            equity=0.26,
            squeeze_callers=1,
            sticky_density=0.40,
        )

        assert action == 'raise'
        assert amount > 30.0
        assert (
            'chart_expand:greenline_vs_open_squeeze SB-vs-open-MP J9s'
            in self.strat.last_expand_reason
        )

    def test_greenline_vs_open_no_caller_expands_normal_open(self):
        action, amount = self.strat.decide(
            hole_cards=cards('Kh', '8h'),
            position='SB',
            facing_action='open',
            open_raise=30.0,
            is_ip=False,
            big_blind=10.0,
            stack=1000.0,
            pot=45.0,
            to_call=30.0,
            stack_bb=100.0,
            villain_position='MP',
            equity=0.28,
        )

        assert action == 'raise'
        assert amount > 30.0
        assert (
            'chart_expand:greenline_vs_open_3bet SB-vs-open-MP K8s'
            in self.strat.last_expand_reason
        )

    def test_greenline_vs_open_overlay_ignores_large_open(self):
        action, amount = self.strat.decide(
            hole_cards=cards('Kh', '8h'),
            position='SB',
            facing_action='open',
            open_raise=60.0,
            is_ip=False,
            big_blind=10.0,
            stack=1000.0,
            pot=75.0,
            to_call=60.0,
            stack_bb=100.0,
            villain_position='MP',
            equity=0.24,
        )

        assert (action, amount) == ('fold', 0.0)

    def test_thirty_two_bb_open_size_maps_to_4bet_not_normal_3bet_bluff(self):
        action, amount = self.strat.decide(
            hole_cards=cards('Ac', '5c'),
            position='BTN',
            facing_action='open',
            open_raise=320.0,
            is_ip=True,
            big_blind=10.0,
            stack=1000.0,
            pot=15.0,
            to_call=320.0,
            stack_bb=100.0,
            villain_position='CO',
            equity=0.33,
        )

        assert (action, amount) == ('fold', 0.0)
        assert 'size_map:open_as_4bet open=32.0bb' in self.strat.last_expand_reason

    def test_huge_open_raise_maps_to_4bet_when_hero_covers(self):
        action, amount = self.strat.decide(
            hole_cards=cards('Ac', '5c'),
            position='BTN',
            facing_action='open',
            open_raise=1500.0,  # 150bb first raise maps to existing 4bet response
            is_ip=True,
            big_blind=10.0,
            stack=3000.0,
            pot=15.0,
            to_call=1500.0,
            stack_bb=300.0,
            villain_position='CO',
            equity=0.33,
        )

        assert (action, amount) == ('fold', 0.0)
        assert 'size_map:open_as_4bet open=150.0bb' in self.strat.last_expand_reason

    def test_fifteen_bb_open_maps_to_3bet_logic(self):
        action, amount = self.strat.decide(
            hole_cards=cards('Ac', '5c'),
            position='BTN',
            facing_action='open',
            open_raise=150.0,
            is_ip=True,
            big_blind=10.0,
            stack=3000.0,
            pot=15.0,
            to_call=150.0,
            stack_bb=300.0,
            villain_position='CO',
            equity=0.33,
        )

        assert action == 'raise'
        assert amount == pytest.approx(322.5)
        assert 'size_map:open_as_3bet open=15.0bb' in self.strat.last_expand_reason


class TestBBDefenseVsOpen:
    """Issue I (gameplay analysis): BB defense range is keyed by OPENER
    position. Old code only defined _BB_VS_SB_DEFENSE and fell through
    to _BTN_RANGE (~48%) for non-SB opens, violating MDF (~70%).

    Academic basis: Minimum Defense Frequency against a 3× open is
      MDF = 1 − B / (B + P) = 1 − 3 / (3 + 3) = 0.5 (nominal);
    Adjusted for IP disadvantage of the opener's range, real defends
    sit at 62–87% per position (GTO Wizard tables).
    """

    strat = PreflopStrategy()

    def test_bb_has_separate_defend_tables_per_opener(self):
        from pokerfate.strategy.preflop import _BB_VS_OPEN_DEFENSE
        for pos in ('UTG', 'MP', 'CO', 'BTN', 'SB'):
            assert pos in _BB_VS_OPEN_DEFENSE

    def test_bb_defend_widens_with_opener_pos(self):
        """Widest defend vs BTN, tightest vs UTG."""
        from pokerfate.strategy.preflop import _BB_VS_OPEN_DEFENSE
        sizes = {
            pos: len(_BB_VS_OPEN_DEFENSE[pos])
            for pos in ('UTG', 'MP', 'CO', 'BTN')
        }
        assert sizes['BTN'] > sizes['CO']
        assert sizes['CO'] >= sizes['MP']
        assert sizes['MP'] > sizes['UTG']

    def test_bb_calls_speculative_hand_vs_btn_open(self):
        """76s is in BB-vs-BTN defend, should call (not fold)."""
        action, _ = self.strat.decide(
            hole_cards=cards('7s', '6s'),
            position='BB',
            facing_action='open',
            open_raise=6.0,
            is_ip=False,
            big_blind=2.0,
            stack=200.0,
            pot=9.0,
            to_call=4.0,
            villain_position='BTN',
            equity=0.42,  # 76s vs BTN open range
        )
        assert action in ('call', 'raise'), (
            f"BB should defend 76s vs BTN open, got {action}"
        )

    def test_bb_folds_junk_vs_utg_open(self):
        """74o should still fold vs UTG (narrow defend)."""
        action, _ = self.strat.decide(
            hole_cards=cards('7d', '4c'),
            position='BB',
            facing_action='open',
            open_raise=6.0,
            is_ip=False,
            big_blind=2.0,
            stack=200.0,
            pot=9.0,
            to_call=4.0,
            villain_position='UTG',
            equity=0.25,
        )
        assert action == 'fold'
