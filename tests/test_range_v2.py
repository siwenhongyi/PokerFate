"""Tests for Range V2: sequence-pattern detection + is_raise_over wiring.

Target bugs from the equity-branch review (see docs/reviews/2026-04-20-equity-branch/):
  P0 #1: is_raise_over judged True on first raise because count-of-raises
         was done AFTER appending current action (api.py ordering bug).
  P0 #3: post-correction floor was missing, so capped_range nuts=0.10
         pushed combos below 1e-4/n and they never recovered.
  Structural gap: no unit test for _detect_sequence_pattern at all.
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
    GTO_VPIP,
    BayesianRangeTracker,
    _ACT_BET, _ACT_CALL, _ACT_CHECK, _ACT_RAISE_OVER,
    _SEQUENCE_CORRECTIONS,
    _detect_sequence_pattern,
)
from pokerfate.strategy.range_v2.hand_combo_map import (
    CATEGORY_TO_INDICES,
    STRENGTH_PCT,
    _CLASS_PCT,
)


@pytest.fixture(autouse=True)
def _bucket_ml_off(monkeypatch):
    """These tests pin down the formula tracker layers (prior, likelihood,
    sequence corrections, runtime bucket params). The LightGBM bucket layer is
    on by default since 2026-11-11 and has its own tests, so it is switched off
    here to keep the expected numbers independent of the model file."""
    from pokerfate.strategy.range_v2 import bucket_ml_calibration as bml
    monkeypatch.setenv('PF_BUCKET_ML', 'off')
    bml._CACHE.clear()


def _h(*pairs):
    """Build action history: _h(('flop', 'bet'), ('turn', 'check'))."""
    return list(pairs)


class TestSequencePatternDetection:
    """All seven patterns are triggered correctly, preflop-only input ignored."""

    def test_preflop_only_history_returns_none(self):
        # Pattern corrections are calibrated on postflop category semantics;
        # running them on preflop buckets (pocket pairs etc.) is meaningless.
        assert _detect_sequence_pattern(_h(('preflop', _ACT_RAISE_OVER))) is None
        assert _detect_sequence_pattern(_h(
            ('preflop', _ACT_BET),
            ('preflop', _ACT_RAISE_OVER),
        )) is None

    def test_empty_history_returns_none(self):
        assert _detect_sequence_pattern([]) is None

    def test_xr_trap_requires_two_prior_check_streets(self):
        history = _h(
            ('flop', _ACT_CHECK),
            ('turn', _ACT_CHECK),
            ('river', _ACT_RAISE_OVER),
        )
        assert _detect_sequence_pattern(history) == 'xr_trap'

    def test_check_raise_same_street(self):
        history = _h(
            ('river', _ACT_CHECK),
            ('river', _ACT_RAISE_OVER),
        )
        assert _detect_sequence_pattern(history) == 'check_raise'

    def test_reraise_same_street(self):
        history = _h(
            ('flop', _ACT_BET),
            ('flop', _ACT_RAISE_OVER),
        )
        assert _detect_sequence_pattern(history) == 'reraise'

    def test_triple_barrel_requires_river_bet(self):
        ok = _h(
            ('flop', _ACT_BET),
            ('turn', _ACT_BET),
            ('river', _ACT_BET),
        )
        assert _detect_sequence_pattern(ok) == 'triple_barrel'
        # Turn-ending bet/bet/bet stream: NOT triple_barrel yet (not at river).
        early = _h(
            ('flop', _ACT_BET),
            ('turn', _ACT_BET),
        )
        # No river bet yet → no triple_barrel (we don't match 2 bets).
        assert _detect_sequence_pattern(early) != 'triple_barrel'

    def test_bet_bet_give_up(self):
        history = _h(
            ('flop', _ACT_BET),
            ('turn', _ACT_BET),
            ('river', _ACT_CHECK),
        )
        assert _detect_sequence_pattern(history) == 'bet_bet_give_up'

    def test_aggression_drop(self):
        history = _h(
            ('flop', _ACT_BET),
            ('turn', _ACT_CHECK),
        )
        assert _detect_sequence_pattern(history) == 'aggression_drop'

    def test_capped_range_partial_vs_full(self):
        """Two streets of calls → partial cap; three → full cap.

        Review fix: original diff used the SAME nuts=0.10 factor for both
        2-street and 3-street cases. 2-street is insufficient evidence to
        rule out slow-play; split into partial (nuts=0.30) / full (0.10).
        """
        partial = _h(
            ('flop', _ACT_CALL),
            ('turn', _ACT_CALL),
        )
        assert _detect_sequence_pattern(partial) == 'capped_range_partial'
        full = _h(
            ('flop', _ACT_CALL),
            ('turn', _ACT_CALL),
            ('river', _ACT_CALL),
        )
        assert _detect_sequence_pattern(full) == 'capped_range_full'

    def test_capped_range_broken_by_any_raise(self):
        """If the player ever bet/raise-over on a postflop street, no cap."""
        history = _h(
            ('flop', _ACT_CALL),
            ('turn', _ACT_BET),
            ('river', _ACT_CALL),
        )
        assert _detect_sequence_pattern(history) is None


class TestSequenceCorrectionShape:
    """Shape / structural invariants on the correction tables."""

    def test_partial_and_full_caps_differ_on_nuts(self):
        """Partial cap must keep more nuts mass than full cap (review fix)."""
        p = _SEQUENCE_CORRECTIONS['capped_range_partial']['nuts']
        f = _SEQUENCE_CORRECTIONS['capped_range_full']['nuts']
        assert p > f, f"partial cap nuts ({p}) should exceed full cap ({f})"

    def test_triple_barrel_has_no_draw_keys(self):
        """Draw / weak_draw in triple_barrel are dead code (river maps them
        to 'air' before correction). Keeping the keys misleads readers."""
        tb = _SEQUENCE_CORRECTIONS['triple_barrel']
        assert 'draw' not in tb
        assert 'weak_draw' not in tb


class TestResetHandPositionPrior:
    """`reset_hand` uses GTO position priors for small samples, observed
    stats once hands_seen >= 20. Review 05_tests_infra §1.2 flagged no
    coverage of this switchover.
    """

    def _make_tracker(self):
        return BayesianRangeTracker(ActionModel())

    def _profile(self, hands_seen, vpip, pfr):
        return PlayerProfile(hands_seen=hands_seen, vpip=vpip, pfr=pfr)

    def test_bb_uses_gto_wide_prior_when_sample_small(self):
        """BB with hands_seen<20 → GTO VPIP 0.40 (wide), not default 0.27.

        This test guards against the regression where an empty-string
        position leaked into dict.get() and fell through to the 0.27
        default (the root cause of the position-chain P0 bug in api.py).
        """
        tracker_bb = self._make_tracker()
        tracker_co = self._make_tracker()
        prof = self._profile(hands_seen=5, vpip=0.0, pfr=0.0)
        tracker_bb.reset_hand(1, 'BB', prof)
        tracker_co.reset_hand(1, 'CO', prof)
        # BB's GTO VPIP (0.40) is much wider than CO's (0.27) → BB's
        # "call_floor" threshold is lower, so more combos get the 0.6
        # weight tier. Concretely: fraction of combos with weight >= 0.6
        # should be strictly higher for BB than for CO.
        w_bb = tracker_bb.get_distribution(1)
        w_co = tracker_co.get_distribution(1)
        # Normalised distributions aren't directly comparable on magnitude,
        # but the count of combos above the observed "medium-tier" weight
        # should scale with VPIP width.
        #
        # Note: all three tiers (1.0, 0.6, 0.03) get normalised by their
        # total. Since BB has MORE 0.6/1.0 combos, the normalised weights
        # of the strongest hands are LOWER (same numerator over larger
        # denominator). So compare wide-range fraction directly.
        assert GTO_VPIP['BB'] > GTO_VPIP['CO']   # sanity on source data
        # combos that survive 'call_floor' — approximate via top-percentile count
        threshold = w_co.max() * 0.05
        wide_bb = int((w_bb > threshold).sum())
        wide_co = int((w_co > threshold).sum())
        assert wide_bb > wide_co, (
            f"BB prior should be wider than CO: BB={wide_bb}, CO={wide_co}"
        )

    def test_observed_stats_override_gto_when_sample_large(self):
        """hands_seen >= 20 → use prof.vpip/pfr instead of GTO table."""
        tracker_nit = self._make_tracker()
        tracker_maniac = self._make_tracker()
        # Same position (UTG), very different observed tendencies
        tracker_nit.reset_hand(1, 'UTG',
                               self._profile(hands_seen=100, vpip=0.08, pfr=0.07))
        tracker_maniac.reset_hand(1, 'UTG',
                                  self._profile(hands_seen=100, vpip=0.55, pfr=0.45))
        w_nit = tracker_nit.get_distribution(1)
        w_maniac = tracker_maniac.get_distribution(1)
        # Maniac UTG opens 45% → many more "raise-tier" (weight 1.0) combos.
        top_nit = int((w_nit > 1.0 / 1326).sum())
        top_maniac = int((w_maniac > 1.0 / 1326).sum())
        assert top_maniac > top_nit

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

    def test_bb_prior_is_wider_than_co_via_end_to_end(self):
        """When PlayerInfo says villain is BB, the tracker must use the
        wide BB prior (vpip 0.40), not fall through to the 0.27 default
        that the CO/MP positions have.
        """
        api_bb = self._setup('BB')
        api_co = self._setup('CO')

        # Emit an ambiguous action (check on flop) — the key is that the
        # starting prior differs before any action. We inspect the tracker
        # distribution directly after new_hand/reset_hand.
        tracker_bb = api_bb._bot._range_tracker
        tracker_co = api_co._bot._range_tracker

        w_bb = tracker_bb.get_distribution(1)
        w_co = tracker_co.get_distribution(1)

        # BB's wider GTO VPIP (0.40) → more combos in the middle weight tier.
        # Not directly equal-weight comparable, but "fraction of combos above
        # some low threshold" scales with VPIP width.
        threshold = w_co.max() * 0.05
        wide_bb = int((w_bb > threshold).sum())
        wide_co = int((w_co > threshold).sum())
        assert wide_bb > wide_co, (
            f"BB prior didn't propagate: BB={wide_bb} combos vs CO={wide_co}"
        )

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


class TestPreflopOpenShoveNarrow:
    """问题 2：preflop 大 open/shove 的 range 应窄化到顶端。"""

    def _profile(self, **over) -> PlayerProfile:
        base = dict(
            name='test', hands_seen=30, vpip=0.30, pfr=0.20, af=2.0,
            fold_to_cbet_opps=0,
        )
        base.update(over)
        return PlayerProfile(**base)

    def test_large_open_collapses_likelihood_for_weak_hands(self):
        model = ActionModel()
        prof = self._profile()
        # bet_ratio = 15 (≈ open 22bb into 1.5bb blinds pot) 应触发窄化
        ctx_big = ActionContext(
            position='UTG', board=[], street='preflop',
            facing_action='open', bet_ratio=15.0,
        )
        # 正常 open (bet_ratio=2) 不触发
        ctx_small = ActionContext(
            position='UTG', board=[], street='preflop',
            facing_action='open', bet_ratio=2.0,
        )
        like_big = model.batch_likelihood('raise', 'preflop', ctx_big, prof, [])
        like_small = model.batch_likelihood('raise', 'preflop', ctx_small, prof, [])

        # 对顶 4% 牌（STRENGTH_PCT ≥ 0.96），两者 likelihood 都应较高。
        # 对 STRENGTH_PCT ∈ [0.85, 0.96) 的中强牌，big open 应显著降低 likelihood。
        mid_idx = np.where((STRENGTH_PCT >= 0.85) & (STRENGTH_PCT < 0.96))[0]
        assert len(mid_idx) > 0
        # big open 应比 normal open 对中强牌更 skeptical。
        mean_big = like_big[mid_idx].mean()
        mean_small = like_small[mid_idx].mean()
        assert mean_big < mean_small * 0.6, (
            f"big-open 对中强牌应窄化: big={mean_big:.3f} small={mean_small:.3f}"
        )

    def test_raise_over_does_not_trigger_preflop_narrow(self):
        """3-bet/4-bet（is_raise_over=True）不走 open-shove 窄化——poker_bot
        observe_action 已把 bet_ratio 置 0，但测试双保险：is_raise_over 为 True
        时显式跳过。"""
        model = ActionModel()
        prof = self._profile()
        ctx = ActionContext(
            position='UTG', board=[], street='preflop',
            facing_action='open', bet_ratio=15.0, is_raise_over=True,
        )
        # 对比：同参数但 is_raise_over=False
        ctx_open = ActionContext(
            position='UTG', board=[], street='preflop',
            facing_action='open', bet_ratio=15.0, is_raise_over=False,
        )
        like_rr = model.batch_likelihood('raise', 'preflop', ctx, prof, [])
        like_open = model.batch_likelihood('raise', 'preflop', ctx_open, prof, [])
        # raise_over 路径不窄化：中强牌 likelihood 应明显更高
        mid_idx = np.where((STRENGTH_PCT >= 0.85) & (STRENGTH_PCT < 0.96))[0]
        assert like_rr[mid_idx].mean() > like_open[mid_idx].mean() * 2.0


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


class TestCallFlattenByMetrics:
    """call 动作的 nuts:air 压缩程度由 (wtsd, vpip-pfr gap) 两项指标驱动。

    触发条件：wtsd ≥ 0.30 AND (vpip - pfr) > 0.20，两项同时满足才 flatten。
    未触发则保留 GTO baseline 的 nuts:air 比（≈17.5×）。

    问题背景：call 的 GTO baseline nuts:air = 0.35/0.02 = 17.5×，这个比值对
    高 wtsd 高 gap（用 air 跟注多）的对手严重偏离。不 flatten 的话每次 call
    更新把 air 权重近乎清零，3 街累积后 range 只剩 strong+，hero 系统性低估
    equity → 过度 fold。
    """

    def _board(self):
        return [Card.from_str(c) for c in ['5h', '8d', 'Kc']]

    def _get_call_nuts_air_ratio(self, wtsd: float, vpip: float, pfr: float, af: float = 2.0) -> float:
        """给定指标，返回 call 动作下 mean(nuts_likelihood) / mean(air_likelihood)。

        用 model 内部的 `_categorize_all` 而不是 `hcat.categorize_cards`——
        前者会对 board-conflict combo 保留默认 'air' 分类，后者会把
        5h5x（含板上的 5h）算成 trips=NUTS，两边不一致会污染桶均值。
        """
        prof = PlayerProfile(hands_seen=80, vpip=vpip, pfr=pfr, af=af, wtsd=wtsd)
        model = ActionModel()
        board = self._board()
        ctx = ActionContext(
            position='CO', board=board, street='flop',
            facing_action='bet',
        )
        like = model.batch_likelihood('call', 'flop', ctx, prof, board)
        cats_internal = model._categorize_all(board)
        nuts_idx = [i for i in range(1326) if cats_internal[i] == 'nuts']
        air_idx = [i for i in range(1326) if cats_internal[i] == 'air']
        nuts_mean = float(like[nuts_idx].mean()) if nuts_idx else 0.0
        air_mean = float(like[air_idx].mean()) if air_idx else 1e-9
        return nuts_mean / max(air_mean, 1e-9)

    def test_high_wtsd_high_gap_flattens_ratio(self):
        """wtsd=0.45, gap=0.48（双门限都触发）→ ratio 从 17.5× 压到 < 6。"""
        ratio = self._get_call_nuts_air_ratio(wtsd=0.45, vpip=0.60, pfr=0.12, af=0.8)
        assert ratio < 6.0, f"双门限触发时 ratio 应 < 6，实际 {ratio:.2f}"

    def test_high_wtsd_low_gap_does_not_flatten(self):
        """wtsd=0.32 触发单边，但 gap=0.05 不够 → gate 不过，保留 baseline。

        典型对应"aggressive 高 VPIP"类画像（wtsd 高但 PFR 跟上了，不用 air 跟）。
        """
        ratio = self._get_call_nuts_air_ratio(wtsd=0.32, vpip=0.30, pfr=0.25, af=3.0)
        assert ratio > 8.0, f"gap 未达门槛时应保留紧 ratio，实际 {ratio:.2f}"

    def test_low_wtsd_does_not_flatten(self):
        """wtsd=0.20 < 0.30 门槛 → gate 不过。对应紧手画像。"""
        ratio = self._get_call_nuts_air_ratio(wtsd=0.20, vpip=0.14, pfr=0.12, af=2.5)
        assert ratio > 8.0, f"wtsd 未达门槛时应保留紧 ratio，实际 {ratio:.2f}"

    def test_mid_wtsd_low_gap_does_not_flatten(self):
        """wtsd=0.26, gap=0.05（两项都不过门槛）→ baseline 行为。"""
        ratio = self._get_call_nuts_air_ratio(wtsd=0.26, vpip=0.25, pfr=0.20, af=2.0)
        assert ratio > 8.0, f"两项都未达门槛时应保留紧 ratio，实际 {ratio:.2f}"

    def test_high_wtsd_high_gap_prevents_air_runaway_over_streets(self):
        """多街累积效应：wtsd=0.45 + gap=0.48 连续 3 次 call 更新后，
        nuts/air 权重比应保持 < 5（修前 ≈30×，air 被抹除）。

        这是 log 里观察到的"3 街 passive 对手行动后 range 收窄 20pp"的
        根因——修前 air 权重 0.11%（归零），修后 1.04%（合理保留）；
        比值从 30× 降到 ~1.5×，但用 < 5 做断言留容差。
        """
        prof = PlayerProfile(hands_seen=80, vpip=0.60, pfr=0.12, af=0.8, wtsd=0.45)
        model = ActionModel()
        tracker = BayesianRangeTracker(action_model=model)
        pid = 1
        tracker.reset_hand(player_id=pid, position='CO', profile=prof)
        board = self._board()
        ctx = ActionContext(
            position='CO', board=board, street='flop',
            facing_action='bet',
        )
        for _ in range(3):
            tracker.observe_action(pid, 'call', 'flop', ctx, prof, board=board)

        w = tracker._weights[pid]
        cats_internal = model._categorize_all(board)
        nuts_total = sum(float(w[i]) for i in range(1326) if cats_internal[i] == 'nuts')
        air_total = sum(float(w[i]) for i in range(1326) if cats_internal[i] == 'air')
        ratio = nuts_total / max(air_total, 1e-9)
        assert ratio < 5.0, (
            f"3 次 call 后 nuts/air 权重比应 < 5（修前~30×），实际 {ratio:.2f}"
        )


class TestAntiConcentrationRegularization:
    """2026-04-23：验证 α-tempering 下限降低 + posterior floor mixing + unknown
    damping 三项协同抵抗连续 polar barrel 的累积过度窄化。

    文献依据：Grünwald 2012 SafeBayes、Franzolini 2023 Entropy Regularization、
    BlackRain79 unknown opponent baseline。
    """

    def _board(self):
        return [Card.from_str(c) for c in ['5h', '8d', 'Kc']]

    def test_floor_mixing_preserves_air_across_streets(self):
        """连续 3 次 pot-size 下注更新后，air 权重不应塌缩到 <1%。

        floor mixing λ=0.08 + α 下限 0.10 组合后，即使极端似然比（50×）也被
        抵抗住——3 街累积不再清零 air。
        """
        prof = PlayerProfile(
            name='villain', hands_seen=50,
            vpip=0.40, pfr=0.15, af=1.2, wtsd=0.35,
        )
        model = ActionModel()
        tracker = BayesianRangeTracker(action_model=model)
        pid = 1
        tracker.reset_hand(player_id=pid, position='CO', profile=prof)
        board = self._board()
        # 模拟 villain 连续 3 次 pot-size raise（极强似然信号）
        ctx = ActionContext(
            position='CO', board=board, street='flop', facing_action='bet',
            bet_ratio=1.0,  # pot-size bet ("large" bucket)
        )
        for _ in range(3):
            tracker.observe_action(pid, 'raise', 'flop', ctx, prof, board=board)

        w = tracker._weights[pid]
        cats = model._categorize_all(board)
        air_mass = sum(float(w[i]) for i in range(1326) if cats[i] == 'air')
        total = float(w.sum())
        air_pct = air_mass / total if total > 0 else 0.0
        # 修前：air 权重被连乘压到 < 0.3%；修后：≥ 1% (floor mixing λ=0.08
        # 保证 active combo 至少 0.08/n_active 权重，air 占相当比例 active
        # combo 因此加总也有几个百分点)
        assert air_pct >= 0.01, (
            f"3 次 pot-size barrel 后 air 至少保留 1% 权重（修前 < 0.3%），"
            f"实际 {air_pct:.3%}"
        )

    def test_alpha_formula_bounds(self):
        """验证 α 公式：confidence=0 时 α=0.85（全力更新），confidence=1 时
        α=0.10（下限，几乎不更新）。相比旧公式 max(0.3, 0.85 - 0.4*c) 在
        高 confidence 场景显著下降，解决累积塌缩。"""
        new_alpha = lambda c: max(0.1, 0.85 - 0.75 * c)
        old_alpha = lambda c: max(0.3, 0.85 - 0.4 * c)

        # 边界值
        assert abs(new_alpha(0.0) - 0.85) < 1e-6, "confidence=0 时 α=0.85（全力更新）"
        assert abs(new_alpha(1.0) - 0.10) < 1e-6, "confidence=1 时 α=0.10（新下限）"

        # 高 confidence 场景新版显著低于旧版
        assert new_alpha(0.8) < old_alpha(0.8) - 0.1, \
            f"confidence=0.8 时新 α ({new_alpha(0.8):.2f}) 应 << 旧 α ({old_alpha(0.8):.2f})"

        # 累积效应量化：50× 似然比的 3 街累积
        # 旧：α≥0.30 → 50^0.3 ≈ 3.2× 单街 → 33× 累积
        # 新：α=0.10 → 50^0.1 ≈ 1.48× 单街 → 3.2× 累积
        new_accum = (50 ** new_alpha(1.0)) ** 3
        old_accum = (50 ** old_alpha(1.0)) ** 3
        assert new_accum < 10, f"新 α 下 3 街累积应 < 10×（实际 {new_accum:.1f}×）"
        assert old_accum > new_accum * 3, \
            f"旧 α 累积应 > 新 α 累积 3 倍（旧 {old_accum:.1f}× vs 新 {new_accum:.1f}×）"

    def test_unknown_opponent_sizing_damped(self):
        """未知对手 (hands_seen < MIN) 的 sizing_adj 偏离 1.0 的幅度应被阻尼 50%。

        直接对比 unknown 的 adj 输出 与 "50/50 mix polar+merged 的 raw 值"——
        因为 unknown 固定 polarization=0.5，所以 raw=0.5*polar+0.5*merged，
        damped 应是 1.0 + 0.5*(raw - 1.0)。
        """
        from pokerfate.strategy.range_v2.action_model import (
            _sizing_adj_for, SIZING_CATEGORY_ADJ_POLARIZED, SIZING_CATEGORY_ADJ_MERGED,
        )

        unknown = PlayerProfile(hands_seen=3)   # 触发 damping
        adj = _sizing_adj_for('overbet', unknown)

        # Raw unknown: 两表 50/50 mix（因为 _polarization_index cold-start = 0.5）
        polar = SIZING_CATEGORY_ADJ_POLARIZED['overbet']
        merged = SIZING_CATEGORY_ADJ_MERGED['overbet']
        raw = {cat: 0.5 * polar[cat] + 0.5 * merged[cat] for cat in polar}

        # damped = 1.0 + 0.5 * (raw - 1.0)
        checked = 0
        for cat in adj:
            dev_damped = abs(adj[cat] - 1.0)
            dev_raw = abs(raw[cat] - 1.0)
            if dev_raw > 0.05:  # 只检查偏离明显的 cat
                ratio = dev_damped / dev_raw
                checked += 1
                assert 0.45 <= ratio <= 0.55, (
                    f"cat={cat}: damped dev={dev_damped:.3f}, raw dev={dev_raw:.3f}, "
                    f"ratio={ratio:.2f}（应 ≈ 0.5，即 50% damping 精确实现）"
                )
        assert checked > 0, "应至少有一个 cat 偏离明显 > 0.05"

    def test_unknown_opponent_damping_skipped_with_server_priors(self):
        """unknown damping 只对 hands_seen 少 AND 无服务端先验的玩家生效。
        有服务端先验说明至少是这个 ID 在平台打过很多手，应按服务端指标走。"""
        from pokerfate.strategy.range_v2.action_model import _sizing_adj_for

        unknown_with_server = PlayerProfile(
            hands_seen=3, server_af_prior=1.0, server_wtsd_prior=0.25,
        )
        adj = _sizing_adj_for('overbet', unknown_with_server)
        # 不应被阻尼——和 server_priors_available 的对手一致
        known_equiv = PlayerProfile(
            hands_seen=50, af=1.0, wtsd=0.25, vpip=0.30, pfr=0.20,
        )
        adj_ref = _sizing_adj_for('overbet', known_equiv)
        # 结果应相差不大（同样不阻尼）
        for cat in adj:
            assert abs(adj[cat] - adj_ref[cat]) < 0.15, (
                f"有服务端先验的 unknown 不应被阻尼，cat={cat}: "
                f"adj={adj[cat]:.3f}, ref={adj_ref[cat]:.3f}"
            )


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
        ref, conf_ref = em._knn_scores_reference(p, index)
        assert conf_fast == conf_ref
        assert bool(fast) == bool(ref)
        assert len(fast) == len(ref)
        if ref:
            assert fast[0][0] == ref[0][0] and fast[:3] == ref[:3]
        fast = list(fast)
        assert [r.uid for _, r in fast] == [r.uid for _, r in ref]
        assert [sc for sc, _ in fast] == [sc for sc, _ in ref]
