"""Integration tests: bot makes valid decisions in full game scenarios."""


import pytest
from pokerfate.core.card import Card
from pokerfate.core.config import RAKE_KEEP
from pokerfate.core.game_state import GameState, Player, Street, Action, ActionType
from pokerfate.bot.poker_bot import PokerBot
from pokerfate.bot.opponent_model import OpponentModel
from pokerfate.strategy.postflop import PostflopStrategy

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

    @pytest.mark.parametrize("villains, pot, contestable, pot_after_call", [
        # hero 50 behind facing 70: the call is capped at 50, the excess is not contestable
        (1, 100.0, 80.0, 130.0),     # 30 old pot + 70 bet
        (2, 170.0, 130.0, 180.0),    # 30 old pot + two 70 bets
    ])
    def test_effective_call_context_caps_what_hero_cannot_call(self, villains, pot, contestable, pot_after_call):
        hero = Player(0, 'Hero', 50.0, cards('Ac', 'Ad'))
        others = [Player(i, f'Villain{i}', 200.0, cards('7c', '2d') if i == 1 else cards('8c', '3d'))
                  for i in range(1, villains + 1)]
        for p in others:
            p.current_bet = 70.0
        gs = GameState(players=[hero, *others], street=Street.FLOP, board=cards('As', 'Kd', '2c'),
                       pot=pot, current_bet=70.0)

        raw_call, effective_call, contestable_pot, pot_odds = PokerBot._effective_call_context(gs, hero)

        assert (raw_call, effective_call, contestable_pot) == pytest.approx((70.0, 50.0, contestable))
        # break-even equity is rake-adjusted: C / ((P + C) × keep)
        assert pot_odds == pytest.approx(50.0 / pot_after_call / RAKE_KEEP)

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


class TestPreflopBetLevelClassification:
    def _preflop_state(self, action_history, short_current_bet: float = 0.0) -> GameState:
        hero = Player(0, 'Royal Police', 930_000.0, cards('Ts', 'Tc'), current_bet=60_000.0)
        three_bettor = Player(1, 'zhouking', 1_000_000.0, [], current_bet=200_000.0)
        short_stack = Player(2, 'kasyer', 0.0, [], current_bet=short_current_bet)
        button = Player(3, 'button', 1_000_000.0, [])
        return GameState(
            players=[hero, three_bettor, short_stack, button],
            dealer_pos=3,  # hero=SB, three_bettor=BB, short_stack=UTG
            street=Street.PREFLOP,
            pot=363_084.0,
            current_bet=max((act.amount for _pid, act, _st in action_history), default=0.0),
            big_blind=10_000.0,
            small_blind=5_000.0,
            current_player_idx=0,
            action_history=action_history,
        )

    @pytest.mark.parametrize("third_raise, raisers, level, primary_id, primary_pos", [
        # a short all-in below the current bet, or an all-in raise too small to reopen, is no new level
        (40_000.0, [0, 1], ('3bet', 200_000.0), 1, 'BB'),
        (250_000.0, [0, 1], ('3bet', 200_000.0), 1, 'BB'),
        # a full raise over the 3-bet is a 4-bet
        (360_000.0, [0, 1, 2], ('4bet', 360_000.0), 2, 'UTG'),
    ])
    def test_preflop_bet_level(self, third_raise, raisers, level, primary_id, primary_pos):
        bot = PokerBot(equity_iterations=10)
        gs = self._preflop_state(
            [
                (0, Action(ActionType.RAISE, 60_000.0), 'preflop'),
                (1, Action(ActionType.RAISE, 200_000.0), 'preflop'),
                (2, Action(ActionType.RAISE, third_raise), 'preflop'),
            ],
            short_current_bet=third_raise,
        )
        hero = gs.players[0]
        assert [pid for _idx, pid, _act in bot._effective_preflop_raises(gs)] == raisers
        assert bot._classify_preflop_action(gs, hero) == level
        assert (bot._primary_raiser_id(gs, hero), bot._primary_raiser_position(gs, hero)) == (primary_id, primary_pos)

# ---------------------------------------------------------------------------
# Range Estimator Tests (Libratus-inspired range compression)
# ---------------------------------------------------------------------------

class TestTinyBetValueRaise:
    """Facing tiny bets: raise when range equity is strong, call when marginal."""

    def test_build_ctx_caps_short_stack_overbet_pot_odds(self):
        strat = PostflopStrategy()
        board = [Card.from_str(c) for c in ['7s', '9d', 'Qc']]
        ctx = strat._build_ctx(
            equity=0.40,
            pot=100.0,          # 30 old pot + villain's 70
            to_call=70.0,
            stack=50.0,
            board=board,
            is_ip=True,
            street='flop',
            facing_bet=True,
            num_opponents=1,
            big_blind=2.0,
            spr=1.0,
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

        assert ctx.to_call == pytest.approx(50.0)
        assert ctx.pot == pytest.approx(80.0)
        assert ctx.pot_odds == pytest.approx(50.0 / 130.0 / RAKE_KEEP)

    def test_build_ctx_zero_stack_cannot_call(self):
        strat = PostflopStrategy()
        board = [Card.from_str(c) for c in ['7s', '9d', 'Qc']]
        ctx = strat._build_ctx(
            equity=0.40,
            pot=100.0,
            to_call=70.0,
            stack=0.0,
            board=board,
            is_ip=True,
            street='flop',
            facing_bet=True,
            num_opponents=1,
            big_blind=2.0,
            spr=0.0,
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

        assert ctx.to_call == pytest.approx(0.0)
        assert ctx.pot == pytest.approx(30.0)
        assert ctx.pot_odds == pytest.approx(0.0)

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

    @pytest.mark.parametrize("aggressor_idx", [None, 1])
    def test_spr_multiway_all_in_opp_excluded(self, aggressor_idx):
        """An opponent who is all-in from an earlier street does not constrain
        SPR, whether or not he was the last to raise."""
        bot = PokerBot(equity_iterations=100)
        gs = self._flop_state(
            my_stack=400.0, opp_stacks=[0.0, 80.0], aggressor_idx=aggressor_idx, raise_amount=10.0,
        )
        bot.decide(gs, player_id=0)
        # fallback min(hero=400, V2=80)
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


class TestPreflopShowdownPrice:
    """A call that leaves nothing to bet against the players in for the raise is priced
    (PokerBot._preflop_showdown_price); everything else is left to the charts."""

    BB = 10_000.0

    @staticmethod
    def _range(*classes):
        import numpy as np
        from pokerfate.strategy.range_v2 import hand_combo_map as hcm

        weights = np.zeros(len(hcm.ALL_COMBOS))
        for cls in classes:
            weights[hcm.CATEGORY_TO_INDICES[cls]] = 1.0
        return weights

    def _bot(self, ranges):
        import numpy as np
        from pokerfate.strategy.range_v2 import hand_combo_map as hcm

        bot = PokerBot(equity_iterations=200)
        uniform = np.ones(len(hcm.ALL_COMBOS))
        bot._range_tracker.get_distribution = lambda pid: ranges.get(pid, uniform)
        bot.set_next_decision_seed(7)
        return bot

    def _state(self, players, history, pot, level):
        return GameState(
            players=players, dealer_pos=len(players) - 1, street=Street.PREFLOP, pot=pot,
            current_bet=level, big_blind=self.BB, small_blind=self.BB / 2, current_player_idx=0,
            action_history=history,
        )

    def _five_bet_spot(self, earlier_raisers: bool):
        """Hand 216 of 2026-11-16: 66 in the BB with 24.6bb; open, 3-bet, 4-bet, then the SB makes
        it 120bb.  The call is all-in.  ``earlier_raisers``: the three players between them are the
        opener, 3-bettor and 4-bettor (as it happened), or have only limped in for the same chips."""
        hero = Player(0, 'Hero', 236_384.0, cards('6s', '6d'), current_bet=10_000.0)
        opener = Player(1, 'utg', 1_463_917.0, [], current_bet=30_000.0)
        three = Player(2, 'mp', 873_300.0, [], current_bet=155_000.0)
        four = Player(3, 'btn', 1_057_050.0, [], current_bet=300_000.0)
        five = Player(4, 'sb', 421_100.0, [], current_bet=1_200_000.0)
        kind = ActionType.RAISE if earlier_raisers else ActionType.CALL
        gs = self._state(
            [hero, opener, three, four, five],
            [
                (1, Action(kind, 30_000.0), 'preflop'),
                (2, Action(kind, 155_000.0), 'preflop'),
                (3, Action(kind, 300_000.0), 'preflop'),
                (4, Action(ActionType.RAISE, 1_200_000.0), 'preflop'),
            ],
            pot=1_695_000.0, level=1_200_000.0,
        )
        strong = self._range('AA', 'KK', 'QQ', 'JJ', 'TT', '99', 'AKs', 'AKo', 'AQs', 'AQo', 'AJs', 'KQs')
        loose = self._range('AKs', 'AKo', 'AQs', 'AQo', 'AJs', 'AJo', 'KQs', 'KQo', 'QQ', 'JJ', 'KK', 'AA')
        bot = self._bot({1: strong, 2: strong, 3: strong, 4: loose})
        _raw, to_call, pot, _odds = bot._effective_call_context(gs, hero)
        return bot, gs, hero, to_call, pot

    def test_raisers_still_to_act_mostly_come_along(self):
        bot, gs, hero, to_call, pot = self._five_bet_spot(earlier_raisers=True)

        price = bot._preflop_showdown_price(gs, hero, to_call, pot)

        assert (to_call, price.pending) == (236_384.0, 3)
        assert pot == pytest.approx(246_384.0 * 2 + 155_000.0 + 30_000.0 + 10_000.0)   # what 24.6bb can win
        # Against the 5-bettor alone the price is fine ...
        assert price.equity > price.need + 0.08
        # ... but each of the three raisers behind comes along 69% of the time, with a real hand.
        assert price.ev < 0
        assert bot.decide(gs, 0).action_type == ActionType.FOLD
        assert bot.preflop.last_expand_reason.startswith('showdown_price:fold call=23.6bb')

    def test_players_who_only_called_come_along_less_often(self):
        raisers, gs, hero, to_call, pot = self._five_bet_spot(earlier_raisers=True)
        callers, gs2, hero2, _, _ = self._five_bet_spot(earlier_raisers=False)

        behind_raisers = raisers._preflop_showdown_price(gs, hero, to_call, pot)
        behind_callers = callers._preflop_showdown_price(gs2, hero2, to_call, pot)

        assert [PokerBot._preflop_earlier_action(gs, pid) for pid in (1, 2, 3, 0)] == ['raised'] * 3 + ['none']
        assert [PokerBot._preflop_earlier_action(gs2, pid) for pid in (1, 2, 3)] == ['called'] * 3
        assert behind_callers.equity == behind_raisers.equity          # same players in for the raise
        assert behind_callers.ev > behind_raisers.ev + 1.0 * self.BB

    def test_a_player_who_comes_along_holds_the_top_of_his_range(self):
        import numpy as np
        from pokerfate.bot.poker_bot import _strongest_share
        from pokerfate.strategy.range_v2 import hand_combo_map as hcm

        kept = _strongest_share(np.ones(len(hcm.ALL_COMBOS)), 0.30)
        strength = np.asarray(hcm.STRENGTH_PCT)

        assert kept.sum() / len(hcm.ALL_COMBOS) == pytest.approx(0.30, abs=0.01)
        assert strength[kept > 0].min() >= strength[kept == 0].max()


class TestPreflopThreeBetRate:
    """How often an opponent re-raises an open, as the preflop rules read it."""

    def test_a_player_without_a_record_reads_as_the_pool(self):
        bot = PokerBot(equity_iterations=50)
        assert bot._preflop_three_bet_rate(7) == pytest.approx(0.062)
        assert bot._preflop_three_bet_rate(None) == pytest.approx(0.062)

    def test_his_own_count_is_pulled_towards_the_pool(self):
        bot = PokerBot(equity_iterations=50)
        stats = bot.opponent_model.get(7)
        stats.three_bet_opportunities, stats.three_bet_count = 40, 6
        # (6 + 0.062 * 35) / (40 + 35)
        assert bot._preflop_three_bet_rate(7) == pytest.approx(8.17 / 75)

    def test_the_re_raise_of_the_hand_being_played_is_left_out(self):
        bot = PokerBot(equity_iterations=50)
        bot.new_hand([0, 7])
        stats = bot.opponent_model.get(7)
        stats.three_bet_opportunities, stats.three_bet_count = 40, 6
        bot.observe_action(7, Action(ActionType.RAISE, 22.0), 'preflop', is_3bet_spot=True)
        assert (stats.three_bet_opportunities, stats.three_bet_count) == (41, 7)
        assert bot._preflop_three_bet_rate(7) == pytest.approx(8.17 / 75)
        bot.new_hand([0, 7])
        # (7 + 0.062 * 35) / (41 + 35)
        assert bot._preflop_three_bet_rate(7) == pytest.approx(9.17 / 76)
