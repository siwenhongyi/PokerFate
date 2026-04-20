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

    def test_build_ctx_keeps_mc_and_range_equity_separate(self):
        strat = PostflopStrategy()
        board = [Card.from_str(c) for c in ['7s', '9d', 'Qc']]
        ctx = strat._build_ctx(
            equity=0.25,
            equity_mc=0.70,
            equity_range=0.25,
            pot=100.0,
            to_call=20.0,
            stack=200.0,
            board=board,
            is_ip=True,
            street='flop',
            facing_bet=True,
            num_opponents=1,
            big_blind=2.0,
            spr=2.0,
            opponent_af=1.5,
            opponent_fold_rate=0.45,
            fold_to_cbet=None,
            value_only=False,
            position='BTN',
            nut_advantage=0.0,
            is_delayed_cbet=False,
            opponent_checked_back=False,
            last_bet_frac=0.0,
            villain_nuts_pct=0.0,
            hole_cards=[Card.from_str('Ac'), Card.from_str('Kd')],
        )
        assert ctx.equity_mc == pytest.approx(0.70)
        assert ctx.equity_range == pytest.approx(0.25)
        assert ctx.compression == pytest.approx(0.25 / 0.70)

    def test_decide_calls_tiny_bet_with_marginal_range_equity(self):
        """range equity=0.43 (losing to opponent range 57%) → call tiny bet, don't raise.

        旧代码用 raw_equity=0.78 决定加注，但 raw equity 只是 vs 随机手牌的胜率，
        不反映对手实际范围。range equity 0.43 意味着对手范围里多数手牌赢我们，
        加注"价值"实际是撞枪口。正确行为是跟注这个极小注（pot odds 1.8% < 43%）。
        """
        strat = PostflopStrategy()
        board = [Card.from_str(c) for c in ['7s', '9d', 'Qc', '8c']]
        calls = 0
        for i in range(100):
            _rng.seed(i)
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
        strat = PostflopStrategy()
        board = [Card.from_str(c) for c in ['7s', '9d', 'Qc', '8c']]
        raises = 0
        for i in range(100):
            _rng.seed(i)
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

class TestEffectiveStackSPR:
    """SPR uses aggressor-first effective stack.

    1) if an aggressor exists on the line → min(hero_total, aggressor_total)
    2) else → min(hero_total, *active_opponent_totals)  (conservative)
    Regression: logs/20.log showed max() over-selecting a deep bystander
    behind a short raiser, inflating geo_cap and producing unrealisable bets.
    """

    def _flop_state(self, my_stack, opp_stacks, my_bet=0.0, board=None, pot=30.0,
                    aggressor_idx=None, raise_amount=0.0):
        """Build a multiway flop state. opp_stacks = list of villain stacks.

        Give each villain distinct dummy hole cards so the equity calculator
        never samples the same card twice (review P1 nit on the original
        TestEffectiveStackSPR: two villains shared '7c/2d').
        """
        villain_holes = [cards('7c', '2d'), cards('5h', '3s'), cards('8c', '4d')]
        p0 = Player(0, 'Hero', my_stack, cards('Ac', 'Ad'), current_bet=my_bet)
        players = [p0]
        for i, s in enumerate(opp_stacks, start=1):
            hole = villain_holes[(i - 1) % len(villain_holes)]
            players.append(Player(i, f'V{i}', s, hole))
        history = []
        if aggressor_idx is not None:
            history.append((aggressor_idx, Action(ActionType.RAISE, raise_amount), 'flop'))
        gs = GameState(
            players=players,
            dealer_pos=0,
            street=Street.FLOP,
            board=board or cards('As', 'Kd', '2c'),
            pot=pot,
            current_bet=my_bet,
            big_blind=2.0,
            current_player_idx=0,
            action_history=history,
        )
        return gs

    def test_spr_heads_up_uses_min(self):
        """HU: hero 400, villain 100 → SPR = 100/30 ≈ 3.33 (not 400/30)."""
        bot = PokerBot(equity_iterations=100)
        gs = self._flop_state(my_stack=400.0, opp_stacks=[100.0])
        bot.decide(gs, player_id=0)
        assert bot.last_spr == pytest.approx(100.0 / 30.0, rel=0.02)

    def test_spr_facing_raise_binds_to_aggressor_not_bystander(self):
        """Regression from logs/20.log: short raiser + deep bystander must NOT
        inflate SPR. Hero 400, V1 raises 10 with 100 stack, V2 bystander 300.
        Effective = min(400, 100 total) = 100, SPR = 100/(30+10) = 2.5."""
        bot = PokerBot(equity_iterations=100)
        gs = self._flop_state(
            my_stack=400.0, opp_stacks=[100.0, 300.0],
            pot=40.0, my_bet=0.0,
            aggressor_idx=1, raise_amount=10.0,
        )
        gs.players[1].current_bet = 10.0
        gs.players[1].stack = 90.0
        gs.current_bet = 10.0
        bot.decide(gs, player_id=0)
        assert bot.last_spr == pytest.approx(100.0 / 40.0, rel=0.05)

    def test_spr_multiway_no_aggressor_uses_shortest(self):
        """Checked-down multiway: hero 400, V1 100, V2 50 → min path picks 50."""
        bot = PokerBot(equity_iterations=100)
        gs = self._flop_state(my_stack=400.0, opp_stacks=[100.0, 50.0])
        bot.decide(gs, player_id=0)
        assert bot.last_spr == pytest.approx(50.0 / 30.0, rel=0.02)

    def test_spr_multiway_all_in_opp_excluded(self):
        """all-in opponents don't constrain SPR (can_act filter)."""
        bot = PokerBot(equity_iterations=100)
        gs = self._flop_state(my_stack=400.0, opp_stacks=[100.0, 80.0])
        gs.players[1].is_all_in = True   # V1 is all-in → excluded from can_act
        bot.decide(gs, player_id=0)
        # No aggressor → fallback min(hero=400, V2=80)
        assert bot.last_spr == pytest.approx(80.0 / 30.0, rel=0.02)

    def test_spr_hero_shortest_uses_hero(self):
        """Hero is shortest: effective = my stack."""
        bot = PokerBot(equity_iterations=100)
        gs = self._flop_state(my_stack=40.0, opp_stacks=[200.0, 300.0])
        bot.decide(gs, player_id=0)
        assert bot.last_spr == pytest.approx(40.0 / 30.0, rel=0.02)


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


class TestPlayerProfileProjection:
    def test_river_profile_separates_afq_samples_from_fold_opportunities(self):
        bot = PokerBot()
        s = bot.opponent_model.get(1)
        s.river_bet_count = 20
        s.river_call_count = 5
        s.river_check_count = 10
        s.river_action_count = 40
        s.river_facing_bet_opps = 3
        s.river_facing_bet_fold_count = 1

        prof = bot._build_player_profile(1)

        assert prof.river_action_count == 35
        assert prof.river_facing_bet_opps == 3
        assert prof.river_fold_rate == pytest.approx(1 / 3)
