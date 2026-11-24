"""Tests for preflop strategy."""

import random

import pytest
from pokerfate.core.card import Card
from pokerfate.core.config import RAKE_KEEP
from pokerfate.strategy import preflop as preflop_module
from pokerfate.strategy.preflop import (
    SHOWDOWN_CONTINUE_RATE,
    SHOWDOWN_EQUITY_MARGIN,
    PreflopStrategy,
    continue_outcomes,
    may_flat_reraise,
    showdown_call_ev,
    showdown_continue_rate,
    _hand_category,
    _normalize_position,
)


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

    def test_pressure_inputs_cap_uncallable_overbet_odds(self):
        call_amt, pot_odds, stack_commit, call_bb = self.strat._pressure_inputs(
            stack=50.0,
            pot=100.0,          # 30 old pot + villain's 70
            to_call=70.0,
            open_raise=70.0,
            big_blind=10.0,
        )

        assert call_amt == pytest.approx(50.0)
        assert pot_odds == pytest.approx(50.0 / 130.0 / RAKE_KEEP)
        assert stack_commit == pytest.approx(1.0)
        assert call_bb == pytest.approx(5.0)

    @pytest.mark.parametrize("position, kwargs, expected", [
        ('BTN', {}, 7.0),                              # sticky pool: 2.5bb + 1bb
        ('BTN', {'stack_bb': 12.0}, 7.0),
        ('UTG', {}, 8.0),                              # sticky pool: 3bb + 1bb
        ('UTG', {'stack_bb': 12.0}, 8.0),
        ('BTN', {'sticky_pool_adjust': False}, 5.0),
        ('UTG', {'sticky_pool_adjust': False}, 6.0),
    ])
    def test_open_raise_size(self, position, kwargs, expected):
        assert self.strat.open_raise_size(position, 2.0, **kwargs) == pytest.approx(expected)

    @pytest.mark.parametrize("position, limpers, kwargs, expected", [
        # sticky pool: 4bb + 1bb per limper, blinds included
        ('CO', 1, {}, 10.0),
        ('UTG', 2, {}, 12.0),
        ('SB', 1, {}, 10.0),
        ('BB', 1, {}, 10.0),
        ('BB', 2, {}, 12.0),
        ('CO', 1, {'sticky_pool_adjust': False}, 7.0),
        ('UTG', 2, {'sticky_pool_adjust': False}, 10.0),
    ])
    def test_iso_raise_size(self, position, limpers, kwargs, expected):
        assert self.strat.iso_raise_size(position, 2.0, num_limpers=limpers, **kwargs) == pytest.approx(expected)


class TestBBBigBlindOption:
    strat = PreflopStrategy()

    @pytest.mark.parametrize("hand", [('7c', '2d'), ('8h', '3s'), ('6d', '4c'), ('5s', '2h')])
    def test_big_blind_with_nothing_to_call_checks_junk(self, hand):
        assert self.strat.decide(
            hole_cards=cards(*hand), position='BB', facing_action='none', open_raise=0,
            is_ip=False, big_blind=2.0, stack=200.0, pot=3.0, is_big_blind=True, num_limpers=1,
        ) == ('check', 0.0)


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


class TestRaiseSizeMatrix:
    strat = PreflopStrategy()

    @pytest.mark.parametrize("open_raise, is_ip, open_pos, three_bet_pos, expected", [
        (5.0, False, 'BTN', 'BB', 22.0),   # matrix 4.4x
        (5.0, True, 'CO', 'BTN', 18.0),    # matrix 3.2x = 16, the 9bb floor wins
        (6.0, False, 'CO', 'BB', 24.0),
        (6.0, False, 'HJ', 'BB', 24.0),    # 9-max alias of CO
        (6.0, True, '', '', 18.0),         # unknown pair: IP 3x, floor 18
        (6.0, False, '', '', 24.0),        # unknown pair: OOP 4x
    ])
    def test_three_bet_size(self, open_raise, is_ip, open_pos, three_bet_pos, expected):
        assert self.strat.three_bet_size(
            open_raise, is_ip=is_ip, big_blind=2.0, open_pos=open_pos, three_bet_pos=three_bet_pos,
        ) == pytest.approx(expected)

    @pytest.mark.parametrize("last_raise_to, is_ip, hero_open_pos, villain_3bet_pos, multiple", [
        (20.0, True, 'BTN', 'SB', 2.15),
        (20.0, False, 'UTG', 'BTN', 2.45),
        (18.0, False, 'SB', 'BB', 2.45),
        (12.0, False, '', '', 2.45),       # unknown positions: OOP fallback
        (12.0, True, '', '', 2.15),        # unknown positions: IP fallback
    ])
    def test_four_bet_size(self, last_raise_to, is_ip, hero_open_pos, villain_3bet_pos, multiple):
        assert self.strat.four_bet_size(
            last_raise_to=last_raise_to, is_ip=is_ip,
            hero_open_pos=hero_open_pos, villain_3bet_pos=villain_3bet_pos,
        ) == pytest.approx(last_raise_to * multiple)


class TestPreflopChartLookup:
    """greenline is the chart that acts; pokergto only supplies mixing weights."""

    @pytest.mark.parametrize("chart_key, cat, greenline, pokergto, primary_source", [
        ('UTG-RFI', 'ATo', ['raise', 'fold'], {'raise': 0.0, 'call': 0.0, 'fold': 1.0}, 'greenline'),
        ('BTN-vs-open-CO', '44', ['raise', 'fold'], {'raise': 0.0, 'call': 0.0, 'fold': 1.0}, 'greenline'),
        ('BB-vs-open-CO', 'A2o', 'fold', {'raise': 0.0, 'call': 0.02, 'fold': 0.98}, 'greenline'),
        ('SB-vs-3bet-UTG', 'ATo', None, {'raise': 0.75, 'call': 0.0, 'fold': 0.25}, ''),
    ])
    def test_lookup_gto(self, chart_key, cat, greenline, pokergto, primary_source):
        refs = preflop_module.lookup_gto(chart_key, cat)
        assert (refs['greenline'], refs['pokergto'], refs['primary_source'], refs['primary']) == (
            greenline, pokergto, primary_source, greenline)

    @pytest.mark.parametrize("chart_key, cat, seed, pokergto_missing, expected", [
        ('UTG-RFI', 'ATo', 0, False,
         ('fold', "greenline_mix:UTG-RFI ATo ['raise', 'fold'] w=pokergto raise:0%/fold:100% -> fold")),
        ('CO-RFI', 'A9o', 0, False,
         ('fold', "greenline_mix:CO-RFI A9o ['raise', 'fold'] w=pokergto raise:25%/fold:75% -> fold")),
        ('BTN-vs-open-CO', '44', 1, False,
         ('fold', "greenline_mix:BTN-vs-open-CO 44 ['raise', 'fold'] w=pokergto raise:0%/fold:100% -> fold")),
        # pokergto has no entry: uniform weights over the greenline actions
        ('X-RFI', 'AA', 1, True,
         ('raise', "greenline_mix:X-RFI AA ['raise', 'fold'] w=uniform raise:50%/fold:50% -> raise")),
        # no greenline chart: no action, pokergto is not used as a fallback
        ('SB-vs-3bet-UTG', 'ATo', 1, False, ('', '')),
    ])
    def test_greenline_action(self, monkeypatch, chart_key, cat, seed, pokergto_missing, expected):
        if pokergto_missing:
            monkeypatch.setattr(preflop_module, 'lookup_gto', lambda _key, _cat: {
                'greenline': ['raise', 'fold'], 'pokergto': None, 'pokergto_chart_key': None,
                'primary': ['raise', 'fold'], 'primary_source': 'greenline',
            })
        assert PreflopStrategy(rng=random.Random(seed))._greenline_action(chart_key, cat) == expected


def test_count_limpers_before_raise_excludes_those_who_acted():
    from pokerfate.bot.poker_bot import PokerBot
    from pokerfate.core.game_state import Action, ActionType, GameState, Player
    bot = PokerBot(equity_iterations=10)
    hero = Player(1, 'Hero', 100.0)
    gs = GameState(players=[hero, Player(2, 'L1', 100.0), Player(3, 'L2', 100.0), Player(4, 'R', 100.0)],
                   action_history=[(2, Action(ActionType.CALL, 1.0), 'preflop'), (3, Action(ActionType.CALL, 1.0), 'preflop'),
                                   (4, Action(ActionType.RAISE, 3.0), 'preflop')])
    assert bot._count_limpers_before_raise(gs, hero) == 2
    gs.action_history.append((2, Action(ActionType.CALL, 3.0), 'preflop'))   # L1 already called the raise
    assert bot._count_limpers_before_raise(gs, hero) == 1



# ---------------------------------------------------------------------------
# Calls that end the betting are decided by their price (2026-11-15).
# ---------------------------------------------------------------------------

def test_showdown_call_ev_is_the_raked_pot_share_minus_the_call():
    ev = showdown_call_ev(call=100.0, pot=300.0, equity=0.40)
    assert ev == pytest.approx((0.40 - SHOWDOWN_EQUITY_MARGIN) * RAKE_KEEP * 400.0 - 100.0)
    # Break-even sits at the raked price plus the margin.
    need = 100.0 / (RAKE_KEEP * 400.0) + SHOWDOWN_EQUITY_MARGIN
    assert showdown_call_ev(call=100.0, pot=300.0, equity=need + 0.01) > 0 > showdown_call_ev(call=100.0, pot=300.0, equity=need - 0.01)


def test_showdown_call_ev_weighs_every_way_the_players_behind_can_split():
    alone = showdown_call_ev(call=100.0, pot=300.0, equity=0.50)
    crowded = (0.30 - SHOWDOWN_EQUITY_MARGIN) * RAKE_KEEP * 500.0 - 100.0
    # One player behind who comes along 30% of the time, adding 100 and cutting hero to 30%.
    one = showdown_call_ev(call=100.0, pot=300.0, equity=0.50, outcomes=[(0.70, 0.50, 0.0), (0.30, 0.30, 100.0)])
    assert one == pytest.approx(0.70 * alone + 0.30 * crowded)
    assert one < alone
    # Rare splits that were left out make the weights fall short of 1: the rest is rescaled.
    short = showdown_call_ev(call=100.0, pot=300.0, equity=0.50, outcomes=[(0.35, 0.50, 0.0), (0.15, 0.30, 100.0)])
    assert short == pytest.approx(one)


def test_continue_outcomes_cover_every_split_of_the_players_behind():
    assert continue_outcomes([]) == [(1.0, ())]
    splits = {who: probability for probability, who in continue_outcomes([0.7, 0.7, 0.13])}
    assert len(splits) == 8 and sum(splits.values()) == pytest.approx(1.0)
    assert splits[()] == pytest.approx(0.3 * 0.3 * 0.87)
    assert splits[(0, 1)] == pytest.approx(0.7 * 0.7 * 0.87)          # both raisers, not the third player
    assert splits[(0, 1, 2)] == pytest.approx(0.7 * 0.7 * 0.13)
    # A split rarer than the cut-off is left out.
    assert [who for _, who in continue_outcomes([0.999])] == [(0,)]


def test_continue_rate_follows_the_raise_size_and_what_the_player_did_before():
    # Hand 216 of 2026-11-16: opener, 3-bettor and 4-bettor still to act behind a 5-bet to 120bb.
    assert showdown_continue_rate(120.0, 'raised') == 0.69
    assert showdown_continue_rate(120.0, 'called') == 0.35
    assert showdown_continue_rate(120.0, 'none') == 0.15
    assert showdown_continue_rate(20.0, 'none') == 0.15 and showdown_continue_rate(19.9, 'none') == 0.21
    assert showdown_continue_rate(8.0, 'called') == 0.51 and showdown_continue_rate(2.6, 'none') == 0.46
    assert showdown_continue_rate(50.0, 'anything else') == showdown_continue_rate(50.0, 'none')
    # Raisers come along most and untouched players least at every size; a bigger raise thins all of them out.
    for rates in SHOWDOWN_CONTINUE_RATE.values():
        assert rates['raised'] > rates['called'] > rates['none']
    for earlier in ('raised', 'called', 'none'):
        by_size = [SHOWDOWN_CONTINUE_RATE[size][earlier] for size in ('small', 'medium', 'big')]
        assert by_size == sorted(by_size, reverse=True)


class TestFlatAReRaise:
    """A call of a re-raise that leaves betting to come: QQ+ / AK and pocket pairs."""

    @pytest.mark.parametrize("cat, allowed", [
        ('AA', True), ('QQ', True), ('AKs', True), ('AKo', True),
        ('JJ', True), ('77', True), ('22', True),
        ('AQs', False), ('AQo', False), ('KQs', False), ('JTs', False),
    ])
    def test_may_flat_reraise(self, cat, allowed):
        assert may_flat_reraise(cat) is allowed

    @pytest.mark.parametrize("hole, action", [
        (('Th', 'Td'), 'call'),      # the chart flats, a pair may
        (('Ah', 'Qh'), 'fold'),      # the chart flats, an unpaired hand below AK may not
    ])
    def test_chart_flat_of_a_three_bet(self, hole, action):
        bb = 2.0
        got, _amount = PreflopStrategy(rng=random.Random(1)).chart_decision(
            hole_cards=cards(*hole), position='CO', facing_action='3bet',
            open_raise=11 * bb, is_ip=False, big_blind=bb, stack=96.5 * bb,
            pot=16 * bb, to_call=7.5 * bb, villain_position='BTN', equity=0.50,
            current_bet=3.5 * bb, stack_bb=96.5,
        )
        assert got == action

    @pytest.mark.parametrize("hole, action", [
        (('9h', '9d'), 'call'),
        (('Ah', 'Qh'), 'fold'),
    ])
    def test_static_range_flat_of_a_three_bet(self, hole, action):
        """No chart for a big blind that faces an open and a re-raise cold."""
        bb = 2.0
        got, _amount = PreflopStrategy(rng=random.Random(1)).chart_decision(
            hole_cards=cards(*hole), position='BB', facing_action='3bet',
            open_raise=11 * bb, is_ip=False, big_blind=bb, stack=99 * bb,
            pot=16 * bb, to_call=10 * bb, villain_position='BTN', equity=0.50,
            current_bet=1 * bb, stack_bb=99,
        )
        assert got == action

    @pytest.mark.parametrize("stack_bb, pot_bb, call_bb, equity, expected", [
        (96.5, 16.0, 7.5, 0.50, ('call', 7.5)),      # 89bb behind a 23.5bb pot: the flat stands
        (107.0, 49.0, 35.5, 0.60, ('raise', 110.5)), # 71.5bb behind an 84.5bb pot, worth a call for stacks
        (107.0, 49.0, 35.5, 0.45, ('fold', 0.0)),    # same spot, not worth it
    ])
    def test_flat_or_commit(self, stack_bb, pot_bb, call_bb, equity, expected):
        """A flat stands with a pot or more behind; below that it is all-in or a fold by the price."""
        bb = 2.0
        action, amount = PreflopStrategy(rng=random.Random(1))._flat_or_commit(
            'AKo', call_bb * bb, stack=stack_bb * bb, pot=pot_bb * bb, equity=equity,
            max_raise_to=(stack_bb + 3.5) * bb,
        )
        assert (action, amount / bb) == expected
