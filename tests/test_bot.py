"""Integration tests: bot makes valid decisions in full game scenarios."""

import random as _rng

import pytest
from pokerfate.core.card import Card
from pokerfate.core.game_state import GameState, Player, Street, Action, ActionType
from pokerfate.bot.poker_bot import PokerBot
from pokerfate.bot.opponent_model import OpponentModel
from pokerfate.strategy.postflop import PostflopStrategy, BoardTexture
from pokerfate.strategy.range_estimator import HandRangeEstimator

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
        """P22: equity >= 0.95 (nuts) always bets; equity 0.90-0.94 occasionally checks."""

        strategy = PostflopStrategy(aggression=1.0)
        board = [Card.from_str(c) for c in ['2d', '7h', 'Jc']]
        # P22: equity 0.98 = nuts → 强制下注，0 checks
        checks_nuts = sum(
            1 for _ in range(200)
            if not strategy.should_cbet(0.98, BoardTexture(board), True, 'flop')
        )
        assert checks_nuts == 0, f"P22: nuts (eq=0.98) should always bet, got {checks_nuts} checks"
        # equity 0.92 = strong but not nuts → still mixes checks
        checks_strong = sum(
            1 for _ in range(200)
            if not strategy.should_cbet(0.92, BoardTexture(board), True, 'flop')
        )
        assert 10 <= checks_strong <= 80, f"Strong (eq=0.92) check frequency out of range: {checks_strong}/200"

    def test_value_mult_per_street_sizing(self):
        """P19: value_mult != 1.0 → flop 缩小, river 放大（多街薄利提取）."""


        board = [Card.from_str(c) for c in ['2d', '7h', 'Jc']]
        texture = BoardTexture(board)
        # 使用相同种子确保 base_frac 一致
        s1 = PostflopStrategy(rng=_rng.Random(99)); s1.value_mult = 1.0
        s2 = PostflopStrategy(rng=_rng.Random(99)); s2.value_mult = 1.3
        # flop: 对跟注站缩小（×0.80）
        flop1 = s1.bet_size(0.85, 100.0, texture, 200.0, 'flop', 2.0)
        flop2 = s2.bet_size(0.85, 100.0, texture, 200.0, 'flop', 2.0)
        assert flop2 < flop1, "P19: flop should be smaller vs calling stations"
        # river: 对跟注站放大（×1.25）
        s1 = PostflopStrategy(rng=_rng.Random(99)); s1.value_mult = 1.0
        s2 = PostflopStrategy(rng=_rng.Random(99)); s2.value_mult = 1.3
        river1 = s1.bet_size(0.85, 100.0, texture, 200.0, 'river', 2.0)
        river2 = s2.bet_size(0.85, 100.0, texture, 200.0, 'river', 2.0)
        assert river2 > river1, "P19: river should be larger vs calling stations"

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

# ---------------------------------------------------------------------------
# Range Estimator Tests (Libratus-inspired range compression)
# ---------------------------------------------------------------------------

class TestRangeEstimator:
    """Unit tests for HandRangeEstimator — core innovation from Libratus."""

    def setup_method(self):

        self.est = HandRangeEstimator()

    def test_reset_sets_prior(self):
        self.est.reset_hand(1, prior_range=0.30)
        assert abs(self.est.get_range_fraction(1) - 0.30) < 0.01

    def test_bet_compresses_range(self):
        self.est.reset_hand(1, prior_range=0.40)
        self.est.observe_action(1, 'raise', 'flop')
        # After one bet, range should be meaningfully smaller
        assert self.est.get_range_fraction(1) < 0.30

    def test_three_streets_aggression_heavy_compression(self):
        """3 streets of betting: range drops well below 0.10."""
        self.est.reset_hand(1, prior_range=0.40)
        for street in ('flop', 'turn', 'river'):
            self.est.observe_action(1, 'raise', street)
        # 0.40 * flop * turn * river ≈ 0.40 * 0.58 * 0.50 * 0.42
        assert self.est.get_range_fraction(1) < 0.10

    def test_discount_decreases_with_compression(self):
        """More streets bet → smaller discount factor → lower effective equity."""
        self.est.reset_hand(1, prior_range=0.40)
        d0 = self.est.get_discount(1)
        self.est.observe_action(1, 'raise', 'flop')
        d1 = self.est.get_discount(1)
        self.est.observe_action(1, 'raise', 'turn')
        d2 = self.est.get_discount(1)
        assert d0 > d1 > d2

    def test_effective_equity_lower_after_pressure(self):
        """After 3 streets of pressure, effective equity < raw equity."""
        raw = 0.41
        self.est.reset_hand(1, prior_range=0.40)
        for s in ('flop', 'turn', 'river'):
            self.est.observe_action(1, 'raise', s)
        eff = self.est.effective_equity(1, raw)
        assert eff < raw
        # After 3 streets pressure, discount is significant (< 0.65)
        assert eff < raw * 0.70

    def test_streets_bet_counter(self):
        """streets_bet counts streets with aggression, not total actions."""
        self.est.reset_hand(1, prior_range=0.35)
        assert self.est.streets_bet(1) == 0
        self.est.observe_action(1, 'raise', 'flop')
        self.est.observe_action(1, 'raise', 'flop')  # same street, shouldn't double-count
        assert self.est.streets_bet(1) == 1
        self.est.observe_action(1, 'raise', 'turn')
        assert self.est.streets_bet(1) == 2

    def test_reset_clears_compression(self):
        """new_hand resets all state; discount returns to prior level."""
        self.est.reset_hand(1, prior_range=0.35)
        d_prior = self.est.get_discount(1)  # ~0.83 for prior=0.35
        for s in ('flop', 'turn', 'river'):
            self.est.observe_action(1, 'raise', s)
        # Should be significantly compressed
        assert self.est.get_discount(1) < 0.70
        # New hand: should return to prior level
        self.est.reset_hand(1, prior_range=0.35)
        assert self.est.get_discount(1) >= d_prior - 0.01

    def test_worst_discount_picks_most_aggressive_opponent(self):
        """worst_discount picks min discount (most compressed opponent)."""
        self.est.reset_hand(1, prior_range=0.35)
        self.est.reset_hand(2, prior_range=0.35)
        # Opponent 1 bets 2 streets, opponent 2 only checks
        self.est.observe_action(1, 'raise', 'flop')
        self.est.observe_action(1, 'raise', 'turn')
        self.est.observe_action(2, 'check', 'flop')
        d = self.est.worst_discount([1, 2])
        assert d == self.est.get_discount(1)  # should pick the more compressed one
        assert d < self.est.get_discount(2)


class TestTinyBetValueRaise:
    """Facing tiny bets: raise when range equity is strong, call when marginal."""

    def test_decide_calls_tiny_bet_with_marginal_range_equity(self):
        """range equity=0.43 (losing to opponent range 57%) → call tiny bet, don't raise.

        旧代码用 raw_equity=0.78 决定加注，但 raw equity 只是 vs 随机手牌的胜率，
        不反映对手实际范围。range equity 0.43 意味着对手范围里多数手牌赢我们，
        加注"价值"实际是撞枪口。正确行为是跟注这个极小注（pot odds 1.8% < 43%）。
        """
        import random


        strat = PostflopStrategy(aggression=1.0)
        board = [Card.from_str(c) for c in ['7s', '9d', 'Qc', '8c']]
        calls = 0
        for i in range(100):
            random.seed(i)
            action, amt = strat.decide(
                equity=0.43,
                pot=55000.0,
                to_call=1000.0,
                stack=127711.0,
                board=board,
                is_ip=False,
                street='turn',
                facing_bet=True,
                num_opponents=2,
                big_blind=3.0,
            )
            calls += (action == 'call')
        assert calls >= 90, f"expected mostly call vs tiny bet with marginal range equity, got {calls}/100"

    def test_decide_raises_tiny_bet_with_strong_range_equity(self):
        """range equity=0.80 (ahead of opponent range) → value raise against tiny bet."""
        import random


        strat = PostflopStrategy(aggression=1.0)
        board = [Card.from_str(c) for c in ['7s', '9d', 'Qc', '8c']]
        raises = 0
        for i in range(100):
            random.seed(i)
            action, amt = strat.decide(
                equity=0.80,
                pot=55000.0,
                to_call=1000.0,
                stack=127711.0,
                board=board,
                is_ip=True,
                street='turn',
                facing_bet=True,
                num_opponents=1,
                big_blind=3.0,
            )
            if action == 'raise':
                raises += 1
                assert amt > 1000.0
        assert raises >= 50, f"expected frequent value-raise with strong range equity, got {raises}/100"


class TestRiverBetLogic:
    """Verify river betting uses pure value/bluff logic, no semi-bluffs."""

    def test_turn_river_crushing_equity_facing_bet_always_raises(self):
        """转/河、面对下注、range equity≥90%：确定性价值加注（类：碾压范围，raise 不劣于 call）。"""
        import random


        strat = PostflopStrategy(aggression=0.55)
        river = [Card.from_str(c) for c in ['Ac', '4c', 'Ah', '7c', 'Qd']]
        turn_b = [Card.from_str(c) for c in ['Ac', '4c', 'Ah', '7c']]
        for equity in (0.90, 0.93, 1.0):
            for seed in range(15):
                random.seed(seed)
                action, amt = strat.decide(
                    equity=equity,
                    pot=160000.0,
                    to_call=80000.0,
                    stack=2_130_819.0,
                    board=river,
                    is_ip=True,
                    street='river',
                    facing_bet=True,
                    num_opponents=1,
                    big_blind=2.0,
                )
                assert action == 'raise', (equity, seed, action)
                assert amt > 80000.0
        for seed in range(15):
            random.seed(seed)
            action, amt = strat.decide(
                equity=0.91,
                pot=120000.0,
                to_call=40000.0,
                stack=500000.0,
                board=turn_b,
                is_ip=False,
                street='turn',
                facing_bet=True,
                num_opponents=1,
                big_blind=2.0,
            )
            assert action == 'raise', (seed, action)
            assert amt > 40000.0

    def test_river_strong_hand_bets(self):

        strategy = PostflopStrategy()
        board = [card(c) for c in ['As', 'Kd', '2c', '7h', 'Jc']]
        # Strong hand on river: should bet
        results = [strategy.should_cbet(0.80, BoardTexture(board), True, 'river')
                   for _ in range(50)]
        assert sum(results) >= 45  # almost always bet

    def test_river_medium_equity_semi_bluff_suppressed(self):
        """0.40 equity on river: should NOT bet frequently (no draws, just a bluff)."""

        strategy = PostflopStrategy()
        board = [card(c) for c in ['As', 'Kd', '2c', '7h', 'Jc']]
        # 40% equity on river = no draws, no semi-bluff justification
        results = [strategy.should_cbet(0.40, BoardTexture(board), True, 'river',
                                        opponent_fold_rate=0.35)
                   for _ in range(100)]
        # Should almost never bet (opponent fold rate too low for pure bluff)
        assert sum(results) <= 20

    def test_river_pure_bluff_with_fold_equity(self):
        """Low equity + high fold rate on river: allow some pure bluffs."""

        strategy = PostflopStrategy()
        board = [card(c) for c in ['As', 'Kd', '2c', '7h', 'Jc']]
        results = [strategy.should_cbet(0.15, BoardTexture(board), True, 'river',
                                        opponent_fold_rate=0.60)
                   for _ in range(200)]
        # Should bluff sometimes (fold equity is profitable), but not always
        assert 5 <= sum(results) <= 90


class TestBBDecisions:
    """BB-specific bot decisions: free check, iso-raise, never fold vs limpers."""

    def _make_bb_state(self, hole_cards_str, num_players=3, limper_count=1):
        """Create a state where the bot is in BB with limpers and no raise."""

        # Build players: p0 = BTN (dealer), p1 = SB, p2 = BB (bot)
        # For this test bot is player_id=2 in BB
        players = [
            Player(0, 'BTN', 200.0, []),
            Player(1, 'SB',  200.0, []),
            Player(2, 'BB',  200.0, cards(*hole_cards_str), current_bet=2.0),
        ]
        # Simulate limpers: each limper put in a CALL action in history
        history = []
        for i in range(limper_count):
            history.append((i, Action(ActionType.CALL, 2.0), "preflop"))  # limp
        gs = GameState(
            players=players,
            dealer_pos=0,       # index 0 = BTN, index 1 = SB, index 2 = BB
            street=Street.PREFLOP,
            board=[],
            pot=2.0 + 1.0 + 2.0 * limper_count,
            current_bet=2.0,
            big_blind=2.0,
            small_blind=1.0,
            current_player_idx=2,
            action_history=history,
        )
        return gs

    def test_bb_with_junk_checks_vs_limpers(self):
        """BB holding junk checks (does not fold) when facing only limpers."""
        bot = PokerBot(equity_iterations=100)
        gs = self._make_bb_state(['7c', '2d'], limper_count=1)
        action = bot.decide(gs, player_id=2)
        # Must check or raise — never fold with free check option
        assert action.action_type != ActionType.FOLD

    def test_bb_with_junk_never_folds_multiple_limpers(self):
        """BB holding junk never folds even with 2 limpers."""
        bot = PokerBot(equity_iterations=100)
        gs = self._make_bb_state(['8h', '3s'], limper_count=2)
        action = bot.decide(gs, player_id=2)
        assert action.action_type != ActionType.FOLD

    def test_bb_with_premium_iso_raises(self):
        """BB with a premium hand iso-raises vs limpers."""
        bot = PokerBot(equity_iterations=100)
        gs = self._make_bb_state(['Ac', 'Ad'], limper_count=1)
        action = bot.decide(gs, player_id=2)
        assert action.action_type == ActionType.RAISE

    def test_postflop_value_threshold_60pct(self):
        """60-65% equity hand should c-bet as value (not semi-bluff) on dry board."""

        strategy = PostflopStrategy(aggression=1.0)
        board = [Card.from_str(c) for c in ['2d', '7h', 'Jc']]  # dry board
        # Run many trials: at 62% equity on dry HU board, should almost always bet
        bets = sum(
            1 for _ in range(200)
            if strategy.should_cbet(0.62, BoardTexture(board), True, 'flop', num_opponents=1)
        )
        # With threshold lowered to 0.60, 62% equity → always bet HU
        assert bets == 200, f"Expected always bet at 62% equity HU dry board, got {bets}/200"

    def test_postflop_dry_board_multiway_60pct_bets_most(self):
        """60%+ equity on dry board even multiway should bet most of the time."""

        strategy = PostflopStrategy(aggression=1.0)
        board = [Card.from_str(c) for c in ['2d', '7h', 'Jc']]  # dry
        bets = sum(
            1 for _ in range(200)
            if strategy.should_cbet(0.65, BoardTexture(board), True, 'flop', num_opponents=2)
        )
        # dry board base=0.90, 2 opponents → freq = max(0.50, 0.90 - 0.10) = 0.80
        # Expect ~80% bet rate: roughly 140-170 out of 200
        assert bets >= 100, f"Expected frequent betting 3-way dry board at 65% equity, got {bets}/200"


class TestMultiwayBetting:
    """Verify multiway pot c-bet tightening (Pluribus: fold equity drops in multiway)."""

    def test_weak_hand_not_bet_3way(self):
        """35% equity hand: should never c-bet into 3 opponents."""

        strategy = PostflopStrategy()
        board = [card(c) for c in ['As', 'Kd', '2c']]
        results = [strategy.should_cbet(0.35, BoardTexture(board), True, 'flop',
                                        num_opponents=3)
                   for _ in range(100)]
        assert sum(results) == 0  # equity < 0.45 multiway floor → never bet

    def test_value_hand_still_bets_multiway(self):
        """70%+ equity: should still bet even multiway (just with lower frequency)."""

        strategy = PostflopStrategy()
        board = [card(c) for c in ['As', 'Kd', '2c']]
        results = [strategy.should_cbet(0.75, BoardTexture(board), True, 'flop',
                                        num_opponents=3)
                   for _ in range(100)]
        assert sum(results) >= 40  # still bets majority of time with strong hand

    def test_thin_value_bets_more_hu_than_multiway(self):
        """65% equity: bets more heads-up than 4-way."""

        strategy = PostflopStrategy()
        board = [card(c) for c in ['As', 'Kd', '2c']]
        hu = sum(strategy.should_cbet(0.65, BoardTexture(board), True, 'flop',
                                      num_opponents=1) for _ in range(200))
        mw = sum(strategy.should_cbet(0.65, BoardTexture(board), True, 'flop',
                                      num_opponents=3) for _ in range(200))
        assert hu > mw


class TestAggressorOpponent:
    """aggressor_opponent_id / preferred_exploit_target (exploit target selection)."""

    def test_facing_bet_last_aggressor_on_street(self):
        p0 = Player(0, "A", 100.0, [], current_bet=5.0)
        p1 = Player(1, "B", 100.0, [], current_bet=0.0)
        gs = GameState(
            players=[p0, p1],
            dealer_pos=0,
            street=Street.FLOP,
            pot=10.0,
            current_bet=5.0,
            action_history=[(0, Action(ActionType.RAISE, 5.0), "flop")],
        )
        assert gs.aggressor_opponent_id(p1) == 0

    def test_multiway_aggressor_not_first_seat(self):
        players = [
            Player(0, "b", 100.0, [], current_bet=0.0),
            Player(1, "x", 100.0, [], current_bet=0.0),
            Player(2, "y", 100.0, [], current_bet=10.0),
        ]
        gs = GameState(
            players=players,
            dealer_pos=0,
            street=Street.TURN,
            pot=30.0,
            current_bet=10.0,
            action_history=[
                (1, Action(ActionType.CALL, 0.0), "flop"),
                (2, Action(ActionType.RAISE, 10.0), "turn"),
            ],
        )
        assert gs.aggressor_opponent_id(players[0]) == 2

    def test_checked_to_uses_last_aggressor_in_hand(self):
        players = [
            Player(0, "b", 100.0, [], current_bet=0.0),
            Player(1, "raiser", 100.0, [], current_bet=0.0),
        ]
        gs = GameState(
            players=players,
            dealer_pos=0,
            street=Street.FLOP,
            pot=12.0,
            current_bet=0.0,
            action_history=[(1, Action(ActionType.RAISE, 6.0), "preflop")],
        )
        assert gs.aggressor_opponent_id(players[0]) == 1

    def test_no_raise_preferred_exploit_target_tiebreak(self):
        """Limp pot: no aggressor; preferred_exploit_target uses type + hands + stable id."""
        players = [
            Player(0, "hero", 100.0, [], current_bet=2.0),
            Player(1, "a", 100.0, [], current_bet=2.0),
            Player(2, "b", 100.0, [], current_bet=2.0),
        ]
        gs = GameState(
            players=players,
            dealer_pos=0,
            street=Street.PREFLOP,
            pot=6.0,
            current_bet=2.0,
            action_history=[
                (1, Action(ActionType.CALL, 2.0), "preflop"),
                (2, Action(ActionType.CALL, 2.0), "preflop"),
            ],
        )
        assert gs.aggressor_opponent_id(players[0]) is None
        m = OpponentModel()
        for pid in (1, 2):
            s = m.get(pid)
            s.hands_seen = 25
            s.vpip_count = 20
            s.pfr_count = 2
        assert m.preferred_exploit_target([1, 2]) == 1
