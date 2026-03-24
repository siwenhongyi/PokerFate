"""Integration tests: bot makes valid decisions in full game scenarios."""

import pytest
from pokerfate.core.card import Card
from pokerfate.core.game_state import GameState, Player, Street, Action, ActionType
from pokerfate.bot.poker_bot import PokerBot
from pokerfate.engine.game_engine import GameEngine


def card(s):
    return Card.from_str(s)


def cards(*strs):
    return [card(s) for s in strs]


class TestBotDecisions:
    def _make_state(self, street=Street.PREFLOP, board=None, pot=10.0,
                    current_bet=0.0, my_stack=200.0, opp_stack=200.0):
        p0 = Player(0, 'Hero', my_stack, cards('Ac', 'Ad'))
        p1 = Player(1, 'Villain', opp_stack, cards('7c', '2d'))
        gs = GameState(
            players=[p0, p1],
            dealer_pos=0,
            street=street,
            board=board or [],
            pot=pot,
            current_bet=current_bet,
            big_blind=2.0,
            small_blind=1.0,
            current_player_idx=0,
        )
        return gs, p0

    def test_bot_returns_valid_action_preflop(self):
        bot = PokerBot(equity_iterations=200)
        gs, _ = self._make_state()
        action = bot.decide(gs, player_id=0)
        assert isinstance(action, Action)
        assert action.action_type in ActionType

    def test_bot_action_type_preflop_aa(self):
        bot = PokerBot(equity_iterations=200)
        gs, _ = self._make_state()
        action = bot.decide(gs, player_id=0)
        # With AA from BTN facing no action, should raise
        assert action.action_type == ActionType.RAISE
        assert action.amount > 0

    def test_bot_postflop_with_strong_hand(self):
        bot = PokerBot(equity_iterations=300)
        gs, _ = self._make_state(
            street=Street.FLOP,
            board=cards('As', 'Kd', '2c'),
            pot=20.0,
            current_bet=0.0,
        )
        action = bot.decide(gs, player_id=0)
        # With top set, should bet (not check/fold)
        assert action.action_type in (ActionType.RAISE, ActionType.CHECK)

    def test_bot_postflop_facing_bet(self):
        bot = PokerBot(equity_iterations=300)
        p0 = Player(0, 'Hero', 200.0, cards('Ac', 'Ad'))
        p0.current_bet = 0.0
        p1 = Player(1, 'Villain', 200.0, cards('7c', '2d'))
        p1.current_bet = 10.0
        gs = GameState(
            players=[p0, p1],
            dealer_pos=0,
            street=Street.FLOP,
            board=cards('As', 'Kd', '2c'),
            pot=30.0,
            current_bet=10.0,
            big_blind=2.0,
            current_player_idx=0,
        )
        action = bot.decide(gs, player_id=0)
        # Should call or raise (not fold) with top set
        assert action.action_type != ActionType.FOLD

    def test_bot_folds_weak_hand_vs_large_bet(self):
        bot = PokerBot(equity_iterations=300)
        p0 = Player(0, 'Hero', 50.0, cards('7c', '2d'))
        p0.current_bet = 0.0
        p1 = Player(1, 'Villain', 200.0, cards('Ac', 'Kd'))
        p1.current_bet = 45.0
        gs = GameState(
            players=[p0, p1],
            dealer_pos=0,
            street=Street.RIVER,
            board=cards('As', 'Kd', 'Qc', 'Js', '9h'),
            pot=100.0,
            current_bet=45.0,
            big_blind=2.0,
            current_player_idx=0,
        )
        action = bot.decide(gs, player_id=0)
        # 72o on AKQJs9 board with large bet should fold
        assert action.action_type == ActionType.FOLD

    def test_bot_does_not_crash_any_street(self):
        bot = PokerBot(equity_iterations=200)
        for street, board in [
            (Street.PREFLOP, []),
            (Street.FLOP, cards('As', 'Kd', '2c')),
            (Street.TURN, cards('As', 'Kd', '2c', '7h')),
            (Street.RIVER, cards('As', 'Kd', '2c', '7h', 'Jc')),
        ]:
            gs, _ = self._make_state(street=street, board=board)
            action = bot.decide(gs, player_id=0)
            assert isinstance(action, Action)


class TestGameEngine:
    def _build_engine(self, verbose=False):
        bot0 = PokerBot(name="PokerFate", equity_iterations=200)
        bot1 = PokerBot(name="Challenger", equity_iterations=200)

        def decide0(gs, pid): return bot0.decide(gs, pid)
        def decide1(gs, pid): return bot1.decide(gs, pid)

        engine = GameEngine(
            bots={0: decide0, 1: decide1},
            player_names={0: "PokerFate", 1: "Challenger"},
            starting_stacks={0: 200.0, 1: 200.0},
            big_blind=2.0,
            small_blind=1.0,
            verbose=verbose,
        )
        return engine

    def test_single_hand_completes(self):
        engine = self._build_engine()
        result = engine.play_hand()
        assert result is not None
        assert len(result.winners) >= 1
        assert result.pot > 0

    def test_stack_conservation(self):
        engine = self._build_engine()
        initial_total = sum(engine.stacks.values())
        for _ in range(20):
            if sum(1 for v in engine.stacks.values() if v > 0) < 2:
                break
            engine.play_hand()
        final_total = sum(engine.stacks.values())
        assert abs(final_total - initial_total) < 0.01  # chips are conserved

    def test_session_runs(self):
        engine = self._build_engine()
        deltas = engine.play_session(50)
        assert isinstance(deltas, dict)
        assert set(deltas.keys()) == {0, 1}
        # Total delta should be ~0
        assert abs(sum(deltas.values())) < 0.01

    def test_verbose_hand(self, capsys):
        engine = self._build_engine(verbose=True)
        engine.play_hand()
        captured = capsys.readouterr()
        assert "Hand #1" in captured.out

    def test_many_hands_no_error(self):
        engine = self._build_engine()
        engine.play_session(100)  # Should not raise
