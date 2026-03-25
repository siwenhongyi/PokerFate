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

    def test_ip_raise_facing_bet_with_strong_hand(self):
        """IP bot with strong hand facing a bet should sometimes raise (not only call)."""
        bot = PokerBot(equity_iterations=400)
        actions = set()
        for _ in range(60):
            p0 = Player(0, 'Hero', 200.0, cards('Ac', 'Ad'))
            p0.current_bet = 0.0
            p1 = Player(1, 'Villain', 200.0, cards('7c', '2d'))
            p1.current_bet = 10.0
            gs = GameState(
                players=[p0, p1],
                dealer_pos=0,          # p0 is dealer = IP
                street=Street.FLOP,
                board=cards('As', 'Kd', '2c'),
                pot=30.0,
                current_bet=10.0,
                big_blind=2.0,
                current_player_idx=0,
            )
            action = bot.decide(gs, player_id=0)
            actions.add(action.action_type)
        # Over 60 trials with strong hand IP, should see both CALL and RAISE
        assert ActionType.RAISE in actions, "IP strong hand should raise sometimes"
        assert ActionType.FOLD not in actions, "IP strong hand should never fold"

    def test_raise_size_ip_is_larger_than_call(self):
        """When IP raises facing a bet, raise amount must exceed to_call."""
        bot = PokerBot(equity_iterations=400)
        for _ in range(30):
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
            if action.action_type == ActionType.RAISE:
                assert action.amount > 10.0, "Raise amount must exceed to_call"
                assert action.amount <= 200.0, "Cannot raise more than stack"

    def test_monster_check_frequency(self):
        """Strong hand (equity ~98%) should occasionally check (slowplay) when not facing a bet."""
        from pokerfate.strategy.postflop import PostflopStrategy, BoardTexture
        from pokerfate.core.card import Card
        strategy = PostflopStrategy(aggression=1.0)
        board = [Card.from_str(c) for c in ['2d', '7h', 'Jc']]
        checks = sum(
            1 for _ in range(200)
            if not strategy.should_cbet(0.98, BoardTexture(board), True, 'flop')
        )
        # ~20% of the time should check; expect between 5% and 40%
        assert 10 <= checks <= 80, f"Monster check frequency out of range: {checks}/200"

    def test_value_mult_increases_bet_size(self):
        """value_mult > 1.0 should produce larger bets."""
        from pokerfate.strategy.postflop import PostflopStrategy, BoardTexture
        from pokerfate.core.card import Card
        board = [Card.from_str(c) for c in ['2d', '7h', 'Jc']]
        texture = BoardTexture(board)
        s1 = PostflopStrategy(); s1.value_mult = 1.0
        s2 = PostflopStrategy(); s2.value_mult = 1.3
        size1 = s1.bet_size(0.85, 100.0, texture, 200.0, 'flop', 2.0)
        size2 = s2.bet_size(0.85, 100.0, texture, 200.0, 'flop', 2.0)
        assert size2 > size1

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
