"""Tests for Range V2: priors, board handling, is_raise_over wiring, floor mixing, calibration hooks.

Target bug from the equity-branch review (see docs/reviews/2026-04-20-equity-branch/):
  P0 #1: is_raise_over judged True on first raise because count-of-raises
         was done AFTER appending current action (api.py ordering bug).
"""

import itertools
import math

import numpy as np
import pytest
from pokerfate.api import ActionEvent, PlayerInfo, PokerFateAPI
from pokerfate.core.card import Card
from pokerfate.strategy.range_v2 import hand_categorizer as hcat
from pokerfate.strategy.range_v2 import hand_combo_map as hcm
from pokerfate.strategy.range_v2.action_model import (
    ActionContext, ActionModel, PlayerProfile,
)
from pokerfate.strategy.range_v2.range_equity_calculator import RangeEquityCalculator
from pokerfate.strategy.range_v2.bayesian_range_tracker import (

    BayesianRangeTracker,
)
from pokerfate.strategy.range_v2.hand_combo_map import (
    CATEGORY_TO_INDICES,
    STRENGTH_PCT,
    _CLASS_PCT,
)


@pytest.fixture(autouse=True)
def _bucket_ml_off(monkeypatch):
    """These tests pin down the formula tracker layers (prior, likelihood,
    runtime bucket params). The LightGBM bucket layer is
    on by default since 2026-11-11 and has its own tests, so it is switched off
    here to keep the expected numbers independent of the model file."""
    from pokerfate.strategy.range_v2 import bucket_ml_calibration as bml
    monkeypatch.setenv('PF_BUCKET_ML', 'off')
    bml._CACHE.clear()


class TestResetHandPositionPrior:
    """`reset_hand` starts every hand uniform: what a player holds is told by what he then
    does (the fitted preflop likelihood), not assumed from his position or statistics."""

    def _make_tracker(self):
        return BayesianRangeTracker(ActionModel())

    def _profile(self, hands_seen, vpip, pfr):
        return PlayerProfile(hands_seen=hands_seen, vpip=vpip, pfr=pfr)

    def test_every_hand_starts_equally_likely_whoever_the_player_is(self):
        """A nit under the gun and a maniac in the big blind start from the same range."""
        nit, maniac = self._make_tracker(), self._make_tracker()
        nit.reset_hand(1, 'UTG', self._profile(hands_seen=100, vpip=0.08, pfr=0.07))
        maniac.reset_hand(1, 'BB', self._profile(hands_seen=100, vpip=0.55, pfr=0.45))
        w = nit.get_distribution(1)
        assert np.allclose(w, 1.0 / 1326) and np.allclose(w, maniac.get_distribution(1))

    def test_empty_position_falls_back_to_co(self):
        """Empty / None position → CO (neutral) instead of dict.get default.

        Regression for the position-chain fallback bug (see api._hand_positions
        comment): empty string used to leak through and hit the 0.27 default
        even for BB, which should use 0.40.
        """
        tracker_empty = self._make_tracker()
        tracker_co = self._make_tracker()
        prof = self._profile(hands_seen=5, vpip=0.0, pfr=0.0)
        tracker_empty.reset_hand(1, '', prof)   # passes through to CO
        tracker_co.reset_hand(1, 'CO', prof)
        assert np.allclose(
            tracker_empty.get_distribution(1),
            tracker_co.get_distribution(1),
        )

    def test_card_removal_excludes_known_cards(self):
        """Combos containing any of the bot's known hole cards → weight 0."""
        tracker = self._make_tracker()
        tracker.set_known_cards([Card.from_str('Ac'), Card.from_str('Kd')])
        tracker.reset_hand(1, 'BTN', self._profile(5, 0.0, 0.0))
        w = tracker.get_distribution(1)
        ac_int = hcm.card_to_int(Card.from_str('Ac'))
        kd_int = hcm.card_to_int(Card.from_str('Kd'))
        # Every combo that contains Ac or Kd must be exactly zero.
        for idx in range(1326):
            c1, c2 = hcm.ALL_COMBOS[idx]
            if c1 in (ac_int, kd_int) or c2 in (ac_int, kd_int):
                assert w[idx] == 0.0, (
                    f"combo {idx} containing known card has w={w[idx]}"
                )


class TestReweightForBoard:
    """reweight_for_board must boost trips / strong combos that the
    preflop prior left underweighted. Review 05_tests_infra §1.2 flagged
    the paired-board trips scenario specifically as untested.
    """

    def _cards(self, *s):
        return [Card.from_str(c) for c in s]

    def _make_tracker(self):
        tracker = BayesianRangeTracker(ActionModel())
        # Hero holds AK — doesn't block 7x for trips on 77x boards.
        tracker.set_known_cards(self._cards('Ah', 'Kc'))
        # Tight UTG prior: 74o is outside VPIP, gets 0.03 weight.
        prof = PlayerProfile(hands_seen=5, vpip=0.0, pfr=0.0)
        tracker.reset_hand(1, 'UTG', prof)
        return tracker

    def test_new_board_does_not_reweight_combos(self):
        """2026-11-09: the nuts/strong weight floor was removed (it inflated
        strong-hand mass on every street against revealed showdowns), so new
        community cards leave the weight vector untouched."""
        tracker = self._make_tracker()
        board = self._cards('7h', '7d', '2c')
        before = tracker.get_distribution(1).copy()
        tracker.reweight_for_board(board)
        np.testing.assert_allclose(tracker.get_distribution(1), before)

    def test_reweight_preserves_distribution_sum(self):
        """After reweight the distribution must still sum to 1.0 (renorm)."""
        tracker = self._make_tracker()
        board = self._cards('Ad', '7h', '2c')
        tracker.reweight_for_board(board)
        assert np.isclose(tracker.get_distribution(1).sum(), 1.0, atol=1e-9)

    def test_reweight_does_not_lift_air_combos(self):
        """reweight only touches 'nuts' and 'strong' categories. A combo
        that categorizes as 'air' / 'weak_draw' on the flop should not be
        boosted (its weight can only shrink as others grow)."""
        tracker = self._make_tracker()
        board = self._cards('7h', '7d', '2c')
        # Find an 'air' combo (no pair, no draw): e.g. 3s 5c on 7h7d2c.
        three_s = hcm.card_to_int(Card.from_str('3s'))
        five_c = hcm.card_to_int(Card.from_str('5c'))
        air_idx = next(
            i for i in range(1326)
            if {hcm.ALL_COMBOS[i][0], hcm.ALL_COMBOS[i][1]} == {three_s, five_c}
        )
        # Sanity: confirm it's classified as non-nuts/non-strong.
        cat = hcat.categorize(air_idx, board)
        assert cat not in ('nuts', 'strong'), f"test fixture changed: {cat}"
        before = tracker.get_distribution(1).copy()
        tracker.reweight_for_board(board)
        after = tracker.get_distribution(1)
        # Air/weak combos don't get explicit boosts; their absolute weight
        # can only decrease (because renormalisation divides by the new
        # larger total sum).
        assert after[air_idx] <= before[air_idx] + 1e-12, (
            f"air combo unexpectedly grew: {before[air_idx]} → {after[air_idx]}"
        )

    def test_empty_or_preflop_board_is_noop(self):
        """reweight_for_board pre-flop (empty / <3 cards) must not touch
        weights — categorize is preflop-only and would corrupt the prior."""
        tracker = self._make_tracker()
        before = tracker.get_distribution(1).copy()
        tracker.reweight_for_board([])
        assert np.array_equal(tracker.get_distribution(1), before)
        # 2-card (shouldn't happen in practice but guard anyway)
        tracker.reweight_for_board(self._cards('7h', '7d'))
        assert np.array_equal(tracker.get_distribution(1), before)


class TestCategorizeCache:
    """Tracker-level cache must be invalidated on board change, otherwise
    a turn call would use flop categories (wrong). Pure correctness test.
    """

    def _make_tracker(self):
        tracker = BayesianRangeTracker(ActionModel())
        tracker.set_known_cards([Card.from_str('Ac'), Card.from_str('Kd')])
        return tracker

    def _cards(self, *s):
        return [Card.from_str(c) for c in s]

    def test_cache_reuses_on_same_board(self):
        tracker = self._make_tracker()
        board = self._cards('7h', '7d', '2c')
        first = tracker._get_categories(board)
        second = tracker._get_categories(board)
        # Same object reference — no recompute.
        assert first is second

    def test_cache_invalidates_on_board_change(self):
        tracker = self._make_tracker()
        flop = self._cards('7h', '7d', '2c')
        turn = self._cards('7h', '7d', '2c', 'Qs')
        flop_cats = tracker._get_categories(flop)
        turn_cats = tracker._get_categories(turn)
        # Different board → cache must have been rebuilt.
        assert turn_cats is not flop_cats
        # Some combos change category when a fourth card is dealt — e.g.
        # a hand with a Q now makes top pair; verify at least some category
        # differences exist between flop and turn assignments.
        diffs = sum(1 for a, b in zip(flop_cats, turn_cats) if a != b)
        assert diffs > 0, "board change must shift at least one combo's category"

    def test_cache_ignores_board_order(self):
        tracker = self._make_tracker()
        b1 = self._cards('7h', '7d', '2c')
        b2 = self._cards('2c', '7d', '7h')  # same cards, different order
        cats1 = tracker._get_categories(b1)
        cats2 = tracker._get_categories(b2)
        # Sorted key → same cache entry.
        assert cats1 is cats2


class TestPreflopStrengthTable:
    """The class→percentile strength ranking (review §4.5 fix).

    Old formula `score = hi*13 + lo + 3*suited` / `min(1.0, score/180)`
    had two bugs:
      (a) AKs vs AKo clipped to the same value near the top
      (b) `score/180` was a fabricated "percentile" with no relation
          to real hand equity

    New: MC-sourced 169-class equity table → tie-aware percentile rank
    over 1326 combos.
    """

    def _strength(self, hand: str) -> float:
        """Get the percentile for a hand class via the module cache."""
        return _CLASS_PCT[hand]

    def test_all_169_classes_covered(self):
        assert len(_CLASS_PCT) == 169

    def test_pair_ordering(self):
        pairs = ['AA', 'KK', 'QQ', 'JJ', 'TT', '99', '88', '77',
                 '66', '55', '44', '33', '22']
        for a, b in zip(pairs, pairs[1:]):
            assert self._strength(a) > self._strength(b), (
                f"pair order broken: {a}={self._strength(a):.4f} vs "
                f"{b}={self._strength(b):.4f}"
            )

    def test_aks_distinct_from_ako(self):
        """Core bug fix: AKs and AKo must be distinguishable."""
        aks = self._strength('AKs')
        ako = self._strength('AKo')
        assert aks > ako, f"AKs ({aks}) should rank above AKo ({ako})"
        # And the gap should be meaningful (not 0.001 noise) — suited
        # vs offsuit is a ~1.5 percent equity swing.
        assert aks - ako > 0.005, (
            f"AKs - AKo gap too small: {aks - ako}"
        )

    def test_tt_beats_22_by_wide_margin(self):
        """TT equity vs random ≈ 0.75; 22 ≈ 0.50. Must be ordered."""
        tt = self._strength('TT')
        twos = self._strength('22')
        assert tt > twos + 0.30, (
            f"TT ({tt}) should beat 22 ({twos}) by wide percentile margin"
        )

    def test_aa_is_top(self):
        aa_pct = self._strength('AA')
        others = [p for k, p in self._iter_all() if k != 'AA']
        assert aa_pct > max(others)

    def test_worst_hand_is_at_bottom(self):
        """42o is historically the worst class in MC-vs-random tables."""
        worst = min(self._iter_all(), key=lambda kv: kv[1])
        assert worst[0] in ('42o', '32o', '72o'), (
            f"worst class should be a low offsuit, got {worst}"
        )

    def test_suited_beats_offsuit_of_same_ranks(self):
        """Every suited combination must rank >= the same-rank offsuit."""
        ranks = 'AKQJT98765432'
        violations = []
        for hi, lo in itertools.combinations(ranks, 2):
            s = self._strength(f"{hi}{lo}s")
            o = self._strength(f"{hi}{lo}o")
            if s <= o:
                violations.append(f"{hi}{lo}: s={s:.4f} vs o={o:.4f}")
        assert not violations, "suited<=offsuit violations: " + "; ".join(violations)

    def test_percentile_in_zero_one_range(self):
        for _, p in self._iter_all():
            assert 0.0 <= p <= 1.0

    def test_aa_combos_all_get_same_percentile(self):
        """All 6 AA combos must share one percentile — tie handling."""
        aa_indices = CATEGORY_TO_INDICES['AA']
        assert len(aa_indices) == 6
        pct_set = set(STRENGTH_PCT[i] for i in aa_indices)
        assert len(pct_set) == 1, f"AA combos got different percentiles: {pct_set}"

    def test_pfr_threshold_selects_roughly_pfr_fraction(self):
        """reset_hand uses `s >= 1 - pfr` to pick the raise-tier.

        Verify: for pfr=0.20, the set of combos above threshold is
        ≈ 20% of 1326 combos (≈ 265). Exact count varies with class
        boundaries since classes are 6/4/12 combos and we can't land
        on exactly 265 — tolerate ±10%.
        """
        pfr = 0.20
        threshold = 1.0 - pfr
        selected = int((STRENGTH_PCT >= threshold).sum())
        expected = 1326 * pfr
        assert expected * 0.85 < selected < expected * 1.15, (
            f"PFR=20% should select ~{expected:.0f} combos, got {selected}"
        )

    def _iter_all(self):
        return list(_CLASS_PCT.items())


class TestPositionEndToEnd:
    """Position propagates: PlayerInfo.position → _hand_positions →
    new_hand(player_positions=) → reset_hand(position=) → observe_action
    (opp_position via ActionContext).

    Review 04_bot_api_preflop §N5 called out the missing end-to-end test.
    """

    def _setup(self, villain_pos):
        api = PokerFateAPI(my_player_id=0, big_blind=2.0, equity_iterations=50)
        api.new_hand(
            players=[
                PlayerInfo(player_id=0, name='Hero', stack=200.0, position='BTN'),
                PlayerInfo(player_id=1, name='V1', stack=200.0, position=villain_pos),
            ],
            dealer_id=0,
        )
        api.deal_hole_cards(['As', 'Ad'])
        return api

    def test_a_new_hand_starts_uniform_for_every_seat(self):
        """Whatever seat the opponent is in, he starts with every hand he can still hold."""
        for seat in ('BB', 'CO'):
            w = self._setup(seat)._bot._range_tracker.get_distribution(1)
            live = w > 0
            assert np.allclose(w[live], 1.0 / int(live.sum())) and int(live.sum()) >= 1225

    def test_opp_position_feeds_action_context(self):
        api = self._setup('SB')
        assert api._hand_positions.get(1) == 'SB'
        assert api._hand_positions.get(0) == 'BTN'

        api.deal_board(['7h', '7d', '2c'], street='flop', pot=6.0)
        api.notify_action(ActionEvent(
            player_id=1, action='check', amount=0.0, street='flop',
        ))
        hist = api._bot._range_tracker._action_history.get(1, [])
        assert hist and hist[-1] == ('flop', 'check')
        assert api._bot._range_tracker._action_meta[1]['position'] == 'SB'

    def test_empty_action_context_preserves_reset_position(self):
        tracker = BayesianRangeTracker(ActionModel())
        profile = PlayerProfile()
        tracker.reset_hand(1, 'BB', profile)
        tracker.observe_action(
            1,
            'check',
            'flop',
            ActionContext(position='', board=[], street='flop', facing_action='check'),
            profile,
            board=[Card.from_str('7h'), Card.from_str('7d'), Card.from_str('2c')],
        )
        assert tracker._action_meta[1]['position'] == 'BB'


class TestProfitLockOnTableTrigger:
    """Profit-lock trigger uses on-table chips (my_final >= threshold).
    Bankroll display is sampled from UserValueRSP and does NOT gate the trigger."""

    def _bootstrap(self):
        from pf_intercept.bot import BotBridge
        from tests.test_bot_bridge import TestBotBridgeProfitLock
        helper = TestBotBridgeProfitLock()
        b = BotBridge(max_auto_rebuy=3)
        b._my_uid = "99"
        helper._bootstrap_table(b, room_id=20242379)
        b._uid_to_seat["99"] = 0
        return b

    def test_winning_a_hand_does_not_record_bankroll_sample(self):
        """Winning a hand does not create/update a bankroll sample."""
        b = self._bootstrap()
        assert b.bankroll_dashboard()["base_total_chips"] is None
        b.handle("pb.WinnerRSP", {
            "winner": [],
            "profit": [{"uid": "99", "chips": 150}],
        })
        assert b.bankroll_dashboard()["base_total_chips"] is None

    def test_first_trigger_works_without_any_prior_leave(self):
        """Regression for the dead-lock: an on-table crossing of threshold
        must fire profit_lock on the very first attempt."""
        from pf_intercept import config
        b = self._bootstrap()
        bb = 2.0
        thr = int(config.PROFIT_LOCK_BB_THRESHOLD * bb)
        # Bring on-table from 200 to thr in one big win.
        b.handle("pb.WinnerRSP", {
            "winner": [],
            "profit": [{"uid": "99", "chips": thr - 200}],
        })
        assert b._profit_lock_deferred is not None, (
            "first-ever trigger must fire (dead-lock regression)"
        )


class TestIsRaiseOverFirstBet:
    """Regression for P0 bug: is_raise_over must be FALSE on first raise.

    Bug: api.py appended the current event to _action_history BEFORE
    counting raises on the street. The counter then included the current
    event, so any raise saw count ≥ 1 and is_raise_over was always True.
    Consequence: _ACT_BET was never emitted, so triple_barrel never fired.
    """

    def _setup_api(self, extra_players=None):
        """Create a PokerFateAPI with a flop board ready for action."""
        api = PokerFateAPI(my_player_id=0, big_blind=2.0)
        players = [
            PlayerInfo(player_id=0, name='Hero', stack=200.0, position='BTN'),
            PlayerInfo(player_id=1, name='V1', stack=200.0, position='BB'),
        ]
        if extra_players:
            players.extend(extra_players)
        api.new_hand(players=players, dealer_id=0)
        api.deal_hole_cards(['As', 'Ad'])
        api.deal_board(['Ks', '7h', '2c'], street='flop', pot=6.0)
        return api, ActionEvent

    def test_first_raise_is_bet_not_raise_over(self):
        api, ActionEvent = self._setup_api()

        # Villain fires the FIRST bet on the flop. is_raise_over must be False.
        api.notify_action(ActionEvent(
            player_id=1, action='raise', amount=4.0, street='flop',
        ))

        # Verify via the tracker's action_history.
        tracker = api._bot._range_tracker
        hist = tracker._action_history.get(1, [])
        assert hist, "tracker should have recorded the action"
        last_street, last_act = hist[-1]
        assert last_act == 'bet', (
            f"P0 regression: first raise must refine to 'bet', got {last_act!r}"
        )

    def test_second_raise_is_raise_over(self):
        api, ActionEvent = self._setup_api(extra_players=[
            PlayerInfo(player_id=2, name='V2', stack=200.0, position='SB'),
        ])

        # V1 bets (first raise on flop — 'bet').
        api.notify_action(ActionEvent(
            player_id=1, action='raise', amount=4.0, street='flop',
        ))
        # V2 raises over (second raise on flop — 'raise_over').
        api.notify_action(ActionEvent(
            player_id=2, action='raise', amount=12.0, street='flop',
        ))

        tracker = api._bot._range_tracker
        v2_hist = tracker._action_history.get(2, [])
        assert v2_hist
        _, last_act = v2_hist[-1]
        assert last_act == 'raise_over', (
            f"second raise should refine to 'raise_over', got {last_act!r}"
        )


class TestMultiwayEquity:
    """方案 D: 多人底池用 weighted_equity_multi（每对手自己 range）。

    对照旧代码硬编码 num_opponents=1，在 5 人池里 K 高只算 1v1 eq ≈ 50%+；
    新代码每对手独立采样，5 人池 K 高在 A-7-5 eq 应下降到 16-25% 区间。
    """

    def _uniform_weights(self):
        return np.ones(1326, dtype=np.float64) / 1326

    def test_multiway_eq_lower_than_single(self):
        """同 range 下，5 人多人池 eq 应显著 < 单对手 1v1 eq。"""
        calc = RangeEquityCalculator()
        hero = [Card.from_str('Ks'), Card.from_str('Qs')]
        board = [Card.from_str(c) for c in ['Ac', '7d', '5h']]
        w = self._uniform_weights()

        eq_1v1 = calc.weighted_equity(hero, board, w, 1, n_samples=500)
        eq_5way = calc.weighted_equity_multi(
            hero, board, [w, w, w, w], n_samples=500,
        )
        # K-Q 高在 A-high 板子单挑 vs 随机手 ≈ 25-35%，5-way ≈ 10-18%。
        assert eq_5way < eq_1v1 - 0.05, (
            f"多人 eq 应显著低于 1v1: 5way={eq_5way:.3f} vs 1v1={eq_1v1:.3f}"
        )

    def test_multi_uses_different_ranges(self):
        """`weighted_equity_multi` 每对手用各自 range：放 "含 A combo" 加权的
        range 进去，hero K 高 vs 它的 eq 应下降。"""
        calc = RangeEquityCalculator()
        hero = [Card.from_str('Ks'), Card.from_str('Qs')]
        board = [Card.from_str(c) for c in ['Ac', '7d', '5h']]
        w_uniform = self._uniform_weights()
        # 构造一个只含 Ax combo 的 range（必中顶对 A）
        # ALL_COMBOS[i] = (c1, c2); A = ranks 12. 52 张牌 index: rank*4+suit.
        # Ace 的 int 表示：12*4+0 .. 12*4+3 = 48..51
        ace_ints = {48, 49, 50, 51}
        # board 用了 Ac = rank 12 suit clubs，假设 Ac = 50，排除之
        # 实际 int_to_card 映射不一定一致，直接让 ALL_COMBOS 自动 card-removal
        w_ax = np.zeros(1326, dtype=np.float64)
        for i in range(1326):
            c1, c2 = hcm.ALL_COMBOS[i]
            if c1 in ace_ints or c2 in ace_ints:
                w_ax[i] = 1.0
        s = w_ax.sum()
        if s > 0:
            w_ax /= s
        # 双 uniform vs uniform+Ax：Ax 明显对 hero 更凶
        eq_both_uni = calc.weighted_equity_multi(
            hero, board, [w_uniform, w_uniform], n_samples=500,
        )
        eq_with_ax = calc.weighted_equity_multi(
            hero, board, [w_uniform, w_ax], n_samples=500,
        )
        assert eq_with_ax < eq_both_uni - 0.05, (
            f"含 Ax 对手的多人 eq 应明显低于双 uniform: "
            f"with_ax={eq_with_ax:.3f} vs both_uni={eq_both_uni:.3f}"
        )

    def test_single_opponent_path_unchanged(self):
        """len(opp)==1 时 multi 退化成 weighted_equity。"""
        calc = RangeEquityCalculator()
        hero = [Card.from_str('Ks'), Card.from_str('Qs')]
        board = [Card.from_str(c) for c in ['Ac', '7d', '5h']]
        w = self._uniform_weights()
        seed = 20260608
        eq_single = calc.weighted_equity(hero, board, w, 1, n_samples=500, seed=seed)
        eq_multi = calc.weighted_equity_multi(hero, board, [w], n_samples=500, seed=seed)
        assert abs(eq_single - eq_multi) < 1e-12, (
            f"single/multi(n=1) 应一致: single={eq_single:.3f} multi={eq_multi:.3f}"
        )


class TestVsHeroDist:
    """问题 8(a)：tracker.get_vs_hero_dist 在 river 返回 hero 视角 win/tie/loss。"""

    def test_river_returns_valid_distribution(self):
        tracker = BayesianRangeTracker(action_model=ActionModel())
        player_id = 1
        tracker.reset_hand(
            player_id=player_id, position='CO',
            profile=PlayerProfile(name='x', hands_seen=30, vpip=0.3, pfr=0.2, af=2.0),
        )
        # River 板：hero 有顺子
        hero_cards = [Card.from_str('8c'), Card.from_str('7d')]
        board = [Card.from_str(c) for c in ['5s', '6h', '9c', 'Jd', '2s']]
        tracker.set_known_cards(hero_cards)
        d = tracker.get_vs_hero_dist(player_id, board, hero_cards)
        assert 'win' in d and 'tie' in d and 'loss' in d
        total = d['win'] + d['tie'] + d['loss']
        assert abs(total - 1.0) < 0.01, f"分布应归一化: {d}"

    def test_non_river_returns_empty(self):
        tracker = BayesianRangeTracker(action_model=ActionModel())
        player_id = 1
        tracker.reset_hand(
            player_id=player_id, position='CO',
            profile=PlayerProfile(name='x', hands_seen=30, vpip=0.3, pfr=0.2, af=2.0),
        )
        hero_cards = [Card.from_str('Ac'), Card.from_str('Kd')]
        flop = [Card.from_str(c) for c in ['5s', '6h', '9c']]
        tracker.set_known_cards(hero_cards)
        d = tracker.get_vs_hero_dist(player_id, flop, hero_cards)
        assert d == {}, f"非 river 应返回空 dict，实际 {d}"

    def test_hero_nut_hand_mostly_wins(self):
        """hero 的同花顺 vs villain uniform range：应几乎全赢。"""
        tracker = BayesianRangeTracker(action_model=ActionModel())
        player_id = 1
        tracker.reset_hand(
            player_id=player_id, position='CO',
            profile=PlayerProfile(name='x', hands_seen=30, vpip=0.3, pfr=0.2, af=2.0),
        )
        # 同花顺 hand：2s 3s on 4s 5s 6s board
        hero_cards = [Card.from_str('2s'), Card.from_str('3s')]
        board = [Card.from_str(c) for c in ['4s', '5s', '6s', '8h', 'Kd']]
        tracker.set_known_cards(hero_cards)
        d = tracker.get_vs_hero_dist(player_id, board, hero_cards)
        # straight flush 几乎只输给更高同花顺，win 率应 >= 95%
        assert d['win'] >= 0.95, f"straight flush win 率应 >= 95%，实际 {d}"


class TestFloorMixing:
    """However strongly the likelihood speaks against a bucket, floor mixing keeps it alive."""

    def test_three_bets_that_are_almost_never_air_still_leave_air_in_the_range(self, tmp_path, monkeypatch):
        import json
        fit = tmp_path / "fit.json"
        fit.write_text(json.dumps({"likelihood_model": {"features": [], "actions": {"bet": {
            "base": {"flop": {"nuts": 0.0, "strong": 0.0, "medium": 0.0, "draw": 0.0, "weak_draw": 0.0, "air": -5.0}},
            "weights": {}}}}}), encoding="utf-8")
        monkeypatch.setenv("PF_FORMULA_FIT_PATH", str(fit))
        prof = PlayerProfile(name='villain', hands_seen=50, vpip=0.40, pfr=0.15, af=1.2, wtsd=0.35)
        model = ActionModel()
        tracker = BayesianRangeTracker(action_model=model)
        tracker.reset_hand(player_id=1, position='CO', profile=prof)
        board = [Card.from_str(c) for c in ['5h', '8d', 'Kc']]
        cats = model._categorize_all(board)

        def air_share():
            w = tracker._weights[1]
            return sum(float(w[i]) for i in range(1326) if cats[i] == 'air') / float(w.sum())

        before = air_share()
        ctx = ActionContext(position='CO', board=board, street='flop', facing_action='bet', bet_ratio=1.0)
        for _ in range(3):
            tracker.observe_action(1, 'raise', 'flop', ctx, prof, board=board)
        # the likelihood did its work (air is 150 times less likely to bet) ...
        assert air_share() < 0.25 * before
        # ... and a share lam = 0.08 of a uniform range still came back in after every bet
        assert air_share() >= 0.01
        assert tracker.last_update_trace['lam'] == 0.08


class TestShowdownCalibration:
    """验证 ShowdownCalibrator 在 tracker 更新时记录预测、摊牌时对比实际。"""

    def test_start_new_hand_limits_active_weights_to_current_hand_players(self):
        tracker = BayesianRangeTracker(action_model=ActionModel())
        seen: list[tuple[int, int]] = []
        tracker._prediction_hook = lambda **kwargs: seen.append((
            int(kwargs["player_id"]),
            len(kwargs.get("active_weights") or {}),
        ))
        prof = PlayerProfile(name="villain", hands_seen=20, vpip=0.30, pfr=0.20)

        tracker.start_new_hand()
        for pid in range(100, 110):
            tracker.reset_hand(pid, "CO", prof)
        assert max(count for _, count in seen) == 10

        seen.clear()
        tracker.start_new_hand()
        for pid in (1, 2, 3):
            tracker.reset_hand(pid, "CO", prof)

        assert seen == [(1, 1), (2, 2), (3, 3)]
        assert set(tracker._weights) == {1, 2, 3}

    def test_records_predictions_on_reset_and_action(self):
        """reset_hand + observe_action 各触发一次 record_prediction。"""
        from pokerfate.calibration import ShowdownCalibrator
        from pokerfate.strategy.range_v2.action_model import ActionModel, ActionContext, PlayerProfile

        calibrator = ShowdownCalibrator(logger=None)
        model = ActionModel()
        tracker = BayesianRangeTracker(action_model=model)
        tracker._prediction_hook = calibrator.record_prediction
        tracker._name_resolver = lambda pid: f'P{pid}'

        hero = [Card.from_str('Ac'), Card.from_str('Kd')]
        tracker.set_known_cards(hero)

        calibrator.start_hand(1)

        prof = PlayerProfile(name='villain', hands_seen=20, vpip=0.30, pfr=0.20, af=2.0, wtsd=0.25)
        tracker.reset_hand(player_id=1, position='CO', profile=prof)

        # 验证 reset 产生一条记录
        assert 1 in calibrator._hand_predictions
        assert len(calibrator._hand_predictions[1]) == 1
        first = calibrator._hand_predictions[1][0]
        assert first.trigger == 'reset'
        assert first.street == 'preflop'

        # observe flop call
        board = [Card.from_str(c) for c in ['5h', '8d', 'Kc']]
        ctx = ActionContext(
            position='CO', board=board, street='flop', facing_action='bet',
        )
        tracker.observe_action(1, 'call', 'flop', ctx, prof, board=board)
        assert len(calibrator._hand_predictions[1]) == 2
        second = calibrator._hand_predictions[1][1]
        assert second.trigger.startswith('action:')
        assert second.street == 'flop'
        # bucket_dist 不为空
        assert len(second.bucket_dist) > 0
        # hero_eq 能算出来（hero 已知 + board 已设）
        assert second.predicted_hero_eq is not None
        assert 0.0 <= second.predicted_hero_eq <= 1.0
        assert second.position == 'CO'
        assert second.facing_action == 'bet'
        assert second.action_bet_ratio == 0.0
        assert second.bet_size_bucket == 'none'
        assert second.action_sequence == 'flop:call'
        assert second.board_features['high_card_rank'] == 13
        assert 'flush_draw' in second.hero_draw
        assert 'nut_flush_blocker' in second.hero_blockers

    def test_preflop_action_type_survives_postflop_predictions(self):
        from pokerfate.calibration import ShowdownCalibrator
        from pokerfate.strategy.range_v2.action_model import ActionModel, ActionContext, PlayerProfile

        calibrator = ShowdownCalibrator(logger=None)
        tracker = BayesianRangeTracker(action_model=ActionModel())
        tracker._prediction_hook = calibrator.record_prediction
        tracker._name_resolver = lambda pid: f'P{pid}'
        tracker.set_known_cards([Card.from_str('Ac'), Card.from_str('Kd')])
        calibrator.start_hand(2)

        prof = PlayerProfile(name='villain', hands_seen=20, vpip=0.30, pfr=0.20, af=2.0)
        tracker.reset_hand(player_id=1, position='BB', profile=prof)
        tracker.observe_action(
            1,
            'raise',
            'preflop',
            ActionContext(
                position='BB',
                board=[],
                street='preflop',
                facing_action='none',
                preflop_action_type='open',
            ),
            prof,
            board=[],
        )
        board = [Card.from_str(c) for c in ['5h', '8d', 'Kc']]
        tracker.observe_action(
            1,
            'call',
            'flop',
            ActionContext(position='BB', board=board, street='flop', facing_action='call'),
            prof,
            board=board,
        )

        last = calibrator._hand_predictions[1][-1]
        assert last.street == 'flop'
        assert last.preflop_action_type == 'open'

    def test_record_actual_computes_compare(self):
        """record_actual 对每条历史预测计算 CalibrationResult。"""
        from pokerfate.calibration import ShowdownCalibrator
        from pokerfate.strategy.range_v2.action_model import ActionModel, ActionContext, PlayerProfile

        calibrator = ShowdownCalibrator(logger=None)
        model = ActionModel()
        tracker = BayesianRangeTracker(action_model=model)
        tracker._prediction_hook = calibrator.record_prediction
        tracker._name_resolver = lambda pid: f'P{pid}'

        hero = [Card.from_str('Ac'), Card.from_str('Kd')]
        tracker.set_known_cards(hero)
        calibrator.start_hand(5)

        prof = PlayerProfile(name='villain', hands_seen=20, vpip=0.30, pfr=0.20, af=2.0)
        tracker.reset_hand(player_id=1, position='CO', profile=prof)

        board = [Card.from_str(c) for c in ['5h', '8d', 'Kc']]
        ctx = ActionContext(position='CO', board=board, street='flop', facing_action='bet')
        tracker.observe_action(1, 'call', 'flop', ctx, prof, board=board)

        # Villain 摊牌亮 5c5d（flop 上是 set = nuts）
        actual_cards = [Card.from_str('5c'), Card.from_str('5d')]
        final_board = board + [Card.from_str('2s'), Card.from_str('Jh')]
        calibrator.record_actual(
            player_id=1, actual_cards=actual_cards,
            final_board=final_board, hero_cards=hero,
        )
        results = calibrator.finalize_hand_calibration(
            hero_cards=hero, final_board=final_board,
        )

        # 两条预测 → 两条 CalibrationResult
        assert len(results) == 2
        for r in results:
            assert r.actual_cards == actual_cards
            # 在 flop 板面上 55 = set → 'nuts' 桶
            # 在 preflop 上 55 = 某 preflop bucket
            if r.record.street == 'flop':
                assert r.actual_bucket == 'nuts'
                assert r.predicted_bucket_prob >= 0  # 应有合理概率
            # hero eq 最终结果可以算
            assert r.actual_hero_eq_final is not None
            assert r.actual_hero_eq_final in (0.0, 0.5, 1.0)
            # eq_prediction_error 应有值
            assert r.eq_prediction_error is not None
            assert r.actual_combo
            assert r.actual_combo_index is not None
            assert r.static_combo_prob is not None
            assert r.bayes_combo_prob is not None
            assert r.nll_static is not None
            assert r.nll_bayes is not None
            assert r.delta_nll is not None
            assert r.nll_source == 'exact_showdown'

    def test_combo_nll_uses_exact_combo_probability(self):
        from pokerfate.calibration import ShowdownCalibrator
        from pokerfate.calibration.showdown_calibration import PredictionRecord

        cal = ShowdownCalibrator(logger=None)
        hero = [Card.from_str('Ac'), Card.from_str('Kd')]
        board = [Card.from_str(c) for c in ['2c', '7d', 'Jh']]
        actual = [Card.from_str('Qs'), Card.from_str('Qh')]
        actual_idx = hcm.COMBO_TO_IDX[tuple(sorted(hcm.card_to_int(c) for c in actual))]
        static = np.ones(1326, dtype=np.float64)
        posterior = np.ones(1326, dtype=np.float64)
        posterior[actual_idx] = 4.0
        rec = PredictionRecord(
            hand_id=9,
            street='flop',
            player_id=1,
            player_name='villain',
            board=board,
            trigger='action:call',
            range_pct=1.0,
            bucket_dist={},
            hero_cards=hero,
            predicted_hero_eq=None,
            static_weights=static,
            posterior_weights=posterior,
        )

        result = cal._build_result(
            rec,
            actual,
            hero,
            board + [Card.from_str('4s'), Card.from_str('9c')],
        )

        assert result.actual_combo_index == actual_idx
        assert result.bayes_combo_prob > result.static_combo_prob
        assert result.delta_nll > 0
        assert math.isclose(
            result.delta_nll,
            math.log(result.bayes_combo_prob / result.static_combo_prob),
            rel_tol=1e-12,
        )

    def test_no_hook_is_zero_overhead(self):
        """tracker._prediction_hook=None 时 observe_action 正常工作不崩。"""
        from pokerfate.strategy.range_v2.action_model import ActionModel, ActionContext, PlayerProfile

        model = ActionModel()
        tracker = BayesianRangeTracker(action_model=model)
        # 默认 _prediction_hook=None

        hero = [Card.from_str('Ac'), Card.from_str('Kd')]
        tracker.set_known_cards(hero)
        prof = PlayerProfile(name='villain', hands_seen=20, vpip=0.30, pfr=0.20, af=2.0)
        tracker.reset_hand(player_id=1, position='CO', profile=prof)

        board = [Card.from_str(c) for c in ['5h', '8d', 'Kc']]
        ctx = ActionContext(position='CO', board=board, street='flop', facing_action='bet')
        # 应不抛异常
        tracker.observe_action(1, 'call', 'flop', ctx, prof, board=board)


class TestBucketPosteriorCalibration:
    """Offline-fitted bucket calibration should shift bucket mass, not combos."""

    def _seed_bucket_weights(self, tracker, player_id, board, target):
        cats = tracker._get_categories(board)
        board_ints = {hcm.card_to_int(c) for c in board}
        w = np.zeros(1326, dtype=np.float64)
        for cat, mass in target.items():
            idxs = []
            for idx, c in enumerate(cats):
                if c != cat:
                    continue
                c1, c2 = hcm.ALL_COMBOS[idx]
                if c1 in board_ints or c2 in board_ints:
                    continue
                idxs.append(idx)
            assert idxs, f'no combos for {cat} on board {board}'
            for idx in idxs:
                w[idx] = mass / len(idxs)
        w /= w.sum()
        tracker._weights[player_id] = w

    def test_fold_other_has_no_bucket_side_effect(self):
        tracker = BayesianRangeTracker(ActionModel())
        board = [Card.from_str(c) for c in ['Qh', 'Jd', '7c']]
        self._seed_bucket_weights(
            tracker, 1, board,
            {
                'nuts': 0.08, 'strong': 0.12, 'medium': 0.25,
                'draw': 0.12, 'weak_draw': 0.08, 'air': 0.35,
            },
        )
        before = tracker.get_distribution(1)
        tracker._apply_bucket_calibration(1, 'flop', board, 'action:fold_other')
        np.testing.assert_allclose(tracker.get_distribution(1), before)


# ── Board-made hands are not the nuts ────────────────────────────────────────

def _cards(*s):
    from pokerfate.core.card import Card
    return [Card.from_str(x) for x in s]


def test_board_trips_with_kicker_is_not_nuts():
    from pokerfate.strategy.range_v2.hand_categorizer import categorize_cards
    # Live hand 2026-11-07 #34: K♥T♦ on 6♦J♣6♣6♥ had 22% equity but was 'nuts'.
    assert categorize_cards(_cards('Kh', 'Td'), _cards('6d', 'Jc', '6c', '6h')) == 'air'
    assert categorize_cards(_cards('Kh', 'Td'), _cards('6d', 'Jc', '6c', '6h', 'Qh')) == 'air'
    # Overcards to the board keep some showdown value.
    assert categorize_cards(_cards('Ah', 'Kd'), _cards('6d', 'Jc', '6c', '6h')) == 'medium'
    # A real set / trips with a hole card stay nuts.
    assert categorize_cards(_cards('6s', '2d'), _cards('6d', 'Jc', '6c')) == 'nuts'
    assert categorize_cards(_cards('Jh', 'Jd'), _cards('6d', 'Jc', '6c')) == 'nuts'


def test_board_full_house_quads_straight_flush_not_nuts():
    from pokerfate.strategy.range_v2.hand_categorizer import categorize_cards
    # Board full house: hero kickers only.
    assert categorize_cards(_cards('Kh', 'Td'), _cards('6d', '6c', '6h', 'Jc', 'Js')) == 'air'
    # Hero pair fills the house -> still nuts bucket.
    assert categorize_cards(_cards('Jh', 'Jd'), _cards('6d', '6c', '6h', '2c', '3s')) == 'nuts'
    # Board straight, hero plays the board -> medium (chop at best).
    assert categorize_cards(_cards('Kh', '2d'), _cards('5d', '6c', '7h', '8c', '9s')) == 'medium'
    # Hero makes a higher straight -> nuts.
    assert categorize_cards(_cards('Th', '2d'), _cards('5d', '6c', '7h', '8c', '9s')) == 'nuts'
    # Board flush: plays the board -> medium; improves without ace -> strong; with ace -> nuts.
    assert categorize_cards(_cards('Kh', '2d'), _cards('3s', '6s', '7s', 'Ts', 'Js')) == 'medium'
    assert categorize_cards(_cards('Qs', '2d'), _cards('3s', '6s', '7s', 'Ts', 'Js')) == 'strong'
    assert categorize_cards(_cards('As', '2d'), _cards('3s', '6s', '7s', 'Ts', 'Js')) == 'nuts'
    # Board quads: kicker only.
    assert categorize_cards(_cards('Kh', '2d'), _cards('6d', '6c', '6h', '6s', 'Jc')) == 'air'


def test_fast_categorizer_matches_reference_evaluator():
    """eval7-backed _score must reproduce the evaluate()-based categories."""
    import random
    from pokerfate.core.card import Card
    from pokerfate.core.hand_evaluator import HandEvaluator, HandRank
    from pokerfate.strategy.range_v2 import hand_categorizer as hc

    def reference(hole, board):
        # The pre-2026-11-09 scorer: full tuple from HandEvaluator.evaluate.
        sc = HandEvaluator.evaluate(list(hole) + list(board))
        hand_rank = HandRank(sc[0])
        r1 = sc[1] if len(sc) > 1 else 0
        r2 = sc[2] if len(sc) > 2 else 0
        return hand_rank, r1, r2

    rng = random.Random(7)
    deck = [Card.from_str(r + s) for r in '23456789TJQKA' for s in 'cdhs']
    mismatches = 0
    for _ in range(4000):
        rng.shuffle(deck)
        n = rng.choice([3, 4, 5])
        hole, board = deck[:2], deck[2:2 + n]
        fast = hc._score(hole + board)[:3]
        ref = reference(hole, board)
        if fast[0] != ref[0] or (fast[0] in (HandRank.ONE_PAIR, HandRank.TWO_PAIR, HandRank.THREE_OF_A_KIND, HandRank.FULL_HOUSE, HandRank.FOUR_OF_A_KIND) and (int(fast[1]) != int(ref[1]) or (fast[0] in (HandRank.TWO_PAIR, HandRank.FULL_HOUSE) and int(fast[2]) != int(ref[2])))):
            mismatches += 1
    assert mismatches == 0


def test_categorize_all_is_shared_and_marks_blocked_combos_air():
    from pokerfate.core.card import Card
    from pokerfate.strategy.range_v2 import hand_categorizer as hc
    from pokerfate.strategy.range_v2 import hand_combo_map as hcm
    board = [Card.from_str(c) for c in ('Ah', 'Kd', '7c')]
    cats = hc.categorize_all(board)
    assert len(cats) == 1326
    assert hc.categorize_all(list(reversed(board))) is cats  # same board, same object
    for idx in range(1326):
        c1, c2 = hcm.cards_of(idx)
        if c1 in board or c2 in board:
            assert cats[idx] == 'air'
        else:
            assert cats[idx] == hc.categorize_cards([c1, c2], board)


def _knn_scores_reference(em, profile, index):
    """Pre-vectorisation scalar implementation of ``em._knn_scores``.

    Moved here from empirical_model on 2026-11-14: it only serves as the
    reference for the equivalence test below.
    """
    current = em._profile_vector(profile, index)
    query_conf = em._query_confidence(current)
    if query_conf <= 0.03:
        return [], query_conf
    scored = []
    for row in index.rows:
        dist = 0.0
        weight_sum = 0.0
        for name in em.FEATURES:
            cur_rel = current.reliability.get(name, 0.0)
            row_rel = row.reliability.get(name, 0.0)
            if cur_rel <= 0.04 or row_rel <= 0.04:
                continue
            weight = em.FEATURE_WEIGHTS[name] * cur_rel * row_rel
            delta = current.z.get(name, 0.0) - row.z.get(name, 0.0)
            dist += weight * delta * delta
            weight_sum += weight
        if weight_sum <= 0.12:
            continue
        scored.append((dist / weight_sum, row))
    scored.sort(key=lambda item: item[0])
    return scored, query_conf


def test_vectorised_knn_matches_scalar_reference():
    import random
    from pokerfate.strategy.range_v2 import empirical_model as em

    index = em._numeric_index()
    if not index.rows:
        import pytest
        pytest.skip("no empirical numeric index available")
    rng = random.Random(3)

    class P:
        pass

    for trial in range(12):
        p = P()
        hands = rng.choice([0, 5, 30, 120, 400])
        p.hands_seen = hands
        p.vpip = rng.uniform(0.1, 0.7); p.pfr = rng.uniform(0.0, p.vpip)
        p.af = rng.uniform(0.3, 4.0); p.wtsd = rng.uniform(0.15, 0.5); p.wmsd = rng.uniform(0.3, 0.7)
        for k in ('flop_afq', 'turn_afq', 'river_afq', 'river_bet_freq', 'bluff_win_rate', 'fold_to_cbet', 'river_fold_rate', 'three_bet_pct', 'fold_to_3bet'):
            setattr(p, k, rng.uniform(0.0, 0.8))
        for k in ('flop_action_count', 'turn_action_count', 'river_action_count', 'river_bet_count', 'river_check_count', 'bet_win_count', 'fold_to_cbet_opps', 'river_facing_bet_opps'):
            setattr(p, k, rng.choice([0, 3, 15, 60]))
        p.server_af_prior = rng.choice([0.0, 2.0]); p.server_wtsd_prior = rng.choice([0.0, 0.3])
        em._KNN_CACHE.clear()
        fast, conf_fast = em._knn_scores(p, index)
        ref, conf_ref = _knn_scores_reference(em, p, index)
        assert conf_fast == conf_ref
        assert bool(fast) == bool(ref)
        assert len(fast) == len(ref)
        if ref:
            assert fast[0][0] == ref[0][0] and fast[:3] == ref[:3]
        fast = list(fast)
        assert [r.uid for _, r in fast] == [r.uid for _, r in ref]
        assert [sc for sc, _ in fast] == [sc for sc, _ in ref]
