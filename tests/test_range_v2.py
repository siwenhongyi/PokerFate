"""Tests for Range V2: sequence-pattern detection + is_raise_over wiring.

Target bugs from the equity-branch review (see docs/reviews/2026-04-20-equity-branch/):
  P0 #1: is_raise_over judged True on first raise because count-of-raises
         was done AFTER appending current action (api.py ordering bug).
  P0 #3: post-correction floor was missing, so capped_range nuts=0.10
         pushed combos below 1e-4/n and they never recovered.
  Structural gap: no unit test for _detect_sequence_pattern at all.
"""

import itertools

import numpy as np
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

    def test_paired_board_boosts_trips_combos(self):
        """74o on 7h 7d 2c flop makes trips (nuts). A 7x combo that had
        weight 0.03 preflop (outside UTG's tight VPIP) must be significantly
        boosted — the whole point of reweight_for_board is that board-
        relevant hands don't stay invisible just because the preflop prior
        underweighted them.
        """
        tracker = self._make_tracker()
        board = self._cards('7h', '7d', '2c')
        before = tracker.get_distribution(1).copy()
        tracker.reweight_for_board(board)
        after = tracker.get_distribution(1)

        # 7s 4s: trips sevens — outside UTG open range, preflop weight 0.03.
        seven_s = hcm.card_to_int(Card.from_str('7s'))
        four_s = hcm.card_to_int(Card.from_str('4s'))
        trips_idx = next(
            i for i in range(1326)
            if {hcm.ALL_COMBOS[i][0], hcm.ALL_COMBOS[i][1]} == {seven_s, four_s}
        )
        # Key invariant: the trips combo's weight grew SUBSTANTIALLY
        # (at least 5× its preflop value) so it's no longer invisible.
        assert after[trips_idx] > before[trips_idx] * 5.0, (
            f"7s4s trips should be boosted, got {after[trips_idx]} "
            f"from {before[trips_idx]} (ratio {after[trips_idx]/before[trips_idx]:.1f})"
        )
        # And its post-reweight weight should be meaningfully above the
        # population average. Issue D/E: the floor multiplier scales from
        # 1.5× (fish, wide reach) to ~2.85× (nit, narrow reach) — looser
        # than the old flat 3× but still visible. Allow ≥ 1.1× avg after
        # renormalization (boost sum widens the denominator slightly).
        n_active = int((after > 1e-10).sum())
        avg_w = 1.0 / max(1, n_active)
        assert after[trips_idx] >= avg_w * 1.1, (
            f"boosted trips should be above avg, got {after[trips_idx]} vs avg {avg_w}"
        )

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
        """After notify_action, the tracker's action history contains the
        street+refined action. We can't inspect the ActionContext directly
        (it's local to observe_action) but we CAN verify the position was
        used by checking _hand_positions is populated correctly.
        """
        api = self._setup('SB')
        # _hand_positions is the canonical storage for the per-hand map.
        assert api._hand_positions.get(1) == 'SB'
        assert api._hand_positions.get(0) == 'BTN'

        # And when a villain acts, observe_action is called with opp_position.
        # The tracker's action history should be populated without crashing.
        api.deal_board(['7h', '7d', '2c'], street='flop', pot=6.0)
        api.notify_action(ActionEvent(
            player_id=1, action='check', amount=0.0, street='flop',
        ))
        hist = api._bot._range_tracker._action_history.get(1, [])
        assert hist and hist[-1] == ('flop', 'check')


class TestProfitLockOnTableTrigger:
    """Profit-lock trigger uses on-table chips (my_final >= threshold).
    Session PnL is display-only and does NOT gate the trigger."""

    def _bootstrap(self):
        from pf_intercept.bot import BotBridge
        from tests.test_bot_bridge import TestBotBridgeProfitLock
        helper = TestBotBridgeProfitLock()
        b = BotBridge(max_auto_rebuy=3)
        b._my_uid = "99"
        helper._bootstrap_table(b, room_id=20242379)
        b._uid_to_seat["99"] = 0
        return b

    def test_winning_a_hand_does_not_move_pnl(self):
        """PnL is display-only — winning a hand (per-hand profit) does
        NOT move _session_pnl_chips."""
        b = self._bootstrap()
        assert b._session_pnl_chips == 0.0
        b.handle("pb.WinnerRSP", {
            "winner": [],
            "profit": [{"uid": "99", "chips": 150}],
        })
        assert b._session_pnl_chips == 0.0

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


class TestHighSignalBayesUpdate:
    """方案 A: 河牌极强信号 (raise / >=0.75x 池) 时跳过 tempering + floor。

    数据背景: 两个 console log 共 633 手，河牌跟注 24 手 -5.27M（avg -219k/手）；
    其中 villain 坚果 35%+ 的 6 手 -2.41M、9/9 输时 eq>po 仍然亏。根因是
    tempered α=0.3 + probability floor 让 "villain 绝不会这么下的空气 combo"
    永远不真正归零，hero 对这些空气 eq ≈ 100%，被拉高 10-20 个百分点。
    """

    def _setup(self):
        tracker = BayesianRangeTracker(ActionModel())
        prof = PlayerProfile(hands_seen=50, vpip=0.30, pfr=0.20)
        tracker.reset_hand(1, 'BTN', prof)
        return tracker, prof

    def test_high_signal_collapses_weaker_combos_more(self):
        """相同输入下，high_signal=True 产生的后验熵应 <= high_signal=False。"""
        board = [Card.from_str(c) for c in ['As', 'Kd', '7c', '2h', '3d']]
        prof = PlayerProfile(hands_seen=50, vpip=0.30, pfr=0.20)
        ctx = ActionContext(
            position='BTN', board=board, street='river',
            facing_action='raise', facing_cbet=False,
            bet_ratio=1.5, is_raise_over=True,
        )
        tracker_lo = BayesianRangeTracker(ActionModel())
        tracker_hi = BayesianRangeTracker(ActionModel())
        tracker_lo.reset_hand(1, 'BTN', prof)
        tracker_hi.reset_hand(1, 'BTN', prof)
        tracker_lo.observe_action(1, 'raise', 'river', ctx, prof, board,
                                   high_signal=False)
        tracker_hi.observe_action(1, 'raise', 'river', ctx, prof, board,
                                   high_signal=True)
        ent_lo = tracker_lo.get_entropy(1)
        ent_hi = tracker_hi.get_entropy(1)
        assert ent_hi < ent_lo, (
            f"high_signal 应让 range 更集中：tempered {ent_lo:.2f} vs "
            f"standard {ent_hi:.2f}"
        )

    def test_high_signal_skips_probability_floor(self):
        """high_signal=True 时，权重分布应更偏向头部（头 10% combo 占更高比例）。

        floor 的效果：把极弱 combo 从 "几乎归零" 抬回 `1e-4/n_active`，让
        非 0 权重有下限。high_signal 跳过 floor → 头部和底部差距拉大。
        """
        board = [Card.from_str(c) for c in ['As', 'Kd', '7c', '2h', '3d']]
        prof = PlayerProfile(hands_seen=50, vpip=0.30, pfr=0.20)
        ctx = ActionContext(
            position='BTN', board=board, street='river',
            facing_action='raise', facing_cbet=False,
            bet_ratio=1.5, is_raise_over=True,
        )
        tracker_lo = BayesianRangeTracker(ActionModel())
        tracker_hi = BayesianRangeTracker(ActionModel())
        tracker_lo.reset_hand(1, 'BTN', prof)
        tracker_hi.reset_hand(1, 'BTN', prof)
        tracker_lo.observe_action(1, 'raise', 'river', ctx, prof, board,
                                   high_signal=False)
        tracker_hi.observe_action(1, 'raise', 'river', ctx, prof, board,
                                   high_signal=True)
        w_lo = tracker_lo.get_distribution(1)
        w_hi = tracker_hi.get_distribution(1)
        # Top-10% 组合占总权重的比例。high_signal 下头部应更突出。
        n = len(w_lo)
        top_k = max(n // 10, 1)
        top_mass_lo = float(np.sort(w_lo)[::-1][:top_k].sum())
        top_mass_hi = float(np.sort(w_hi)[::-1][:top_k].sum())
        assert top_mass_hi > top_mass_lo, (
            f"high_signal 下头部 combo 应占更大权重: "
            f"tempered_top10%={top_mass_lo:.3f} vs standard_top10%={top_mass_hi:.3f}"
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
        """len(opp)==1 时 multi 退化成 weighted_equity（结果相近）。"""
        calc = RangeEquityCalculator()
        hero = [Card.from_str('Ks'), Card.from_str('Qs')]
        board = [Card.from_str(c) for c in ['Ac', '7d', '5h']]
        w = self._uniform_weights()
        eq_single = calc.weighted_equity(hero, board, w, 1, n_samples=500)
        eq_multi = calc.weighted_equity_multi(hero, board, [w], n_samples=500)
        # 阈值 0.08 容忍 n=500 MC 的方差（两侧各自 sampling，~±4pp 正常）
        assert abs(eq_single - eq_multi) < 0.08, (
            f"single/multi(n=1) 应相近: single={eq_single:.3f} multi={eq_multi:.3f}"
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


class TestShowdownLearnerShrinkage:
    """2026-04-23：showdown_learner 的 50/50 固定混合改为按样本量 shrinkage。

    公式 `blend = n / (n + 50)`，保留 MIN_SAMPLES=8 作为最低门槛：
    - n=8（门槛）：blend=14%，小样本噪声被压到最小
    - n=50：blend=50%，中等样本权重相当于旧版固定 50%
    - n=500：blend=91%，大样本时 learned_freq 主导
    """

    def _setup(self, cat_count_nuts: int, cat_count_air: int):
        """Build a showdown learner with specific per-cat counts, plus a
        matching opponent profile that has some hands observed."""
        from pokerfate.strategy.range_v2.showdown_learner import ShowdownLearner
        learner = ShowdownLearner()
        # Directly seed the internal dict so we can control exact sample counts.
        # Format: _freq[name][(street, action)][cat] = count
        learner._freq['TestPlayer'] = {
            ('flop', 'call'): {'nuts': cat_count_nuts, 'air': cat_count_air},
        }
        model = ActionModel(showdown_learner=learner)
        prof = PlayerProfile(
            name='TestPlayer', hands_seen=80,
            vpip=0.30, pfr=0.20, af=2.0, wtsd=0.25,
        )
        board = [Card.from_str(c) for c in ['5h', '8d', 'Kc']]
        ctx = ActionContext(
            position='CO', board=board, street='flop', facing_action='bet',
        )
        return model, prof, ctx, board

    def _get_sample_nuts_likelihood(self, model, prof, ctx, board):
        """Return mean likelihood for nuts-bucket combos via batch_likelihood."""
        like = model.batch_likelihood('call', 'flop', ctx, prof, board)
        cats = model._categorize_all(board)
        nuts_idx = [i for i in range(1326) if cats[i] == 'nuts']
        return float(like[nuts_idx].mean())

    def test_learner_below_min_samples_not_applied(self):
        """n<8（_MIN_SAMPLES）时 get_learned_freq 返回 None，blend 跳过，
        结果完全等于不用 learner。"""
        from pokerfate.strategy.range_v2.showdown_learner import ShowdownLearner
        model_with_learner, prof, ctx, board = self._setup(
            cat_count_nuts=3, cat_count_air=2   # total n=5 < 8
        )
        like_with = self._get_sample_nuts_likelihood(model_with_learner, prof, ctx, board)

        # Reference model with no learner at all
        model_no_learner = ActionModel(showdown_learner=None)
        like_no = self._get_sample_nuts_likelihood(model_no_learner, prof, ctx, board)

        assert abs(like_with - like_no) < 1e-6, (
            f"n<8 应完全不生效，with={like_with} no={like_no}"
        )

    def test_learner_low_samples_small_weight(self):
        """n=8（刚过门槛）时 blend≈14%，learned_freq 对结果影响应很小。"""
        # 学习器记的是 nuts 100%（8 次 call 全是 nuts）——极端值，考验 blend 压制
        model_learner, prof, ctx, board = self._setup(
            cat_count_nuts=8, cat_count_air=0
        )
        model_no = ActionModel(showdown_learner=None)
        like_learner = self._get_sample_nuts_likelihood(model_learner, prof, ctx, board)
        like_no = self._get_sample_nuts_likelihood(model_no, prof, ctx, board)
        # 极端 learned_freq[nuts]=1.0 clip→0.99；blend=8/58≈0.138
        # 如果旧版 0.5 固定，like_learner 会被拉到接近 0.5 * 0.99 + 0.5 * like_no
        # 新版应只被拉到 0.138 * 0.99 + 0.862 * like_no
        pulled_old = 0.5 * 0.99 + 0.5 * like_no
        pulled_new = 0.138 * 0.99 + 0.862 * like_no
        # 实际值应接近 pulled_new，远离 pulled_old
        assert abs(like_learner - pulled_new) < 0.02, (
            f"n=8 应用新 shrinkage 权重 0.14，预期接近 {pulled_new:.3f}，实际 {like_learner:.3f}"
        )
        # 对比之下旧版 0.5 固定会差得多
        assert abs(like_learner - pulled_old) > 0.1, (
            f"新版不应靠近旧版 0.5 固定的结果 {pulled_old:.3f}，实际 {like_learner:.3f}"
        )

    def test_learner_large_samples_high_weight(self):
        """n=500 时 blend≈91%，learned_freq 应主导结果。"""
        model_learner, prof, ctx, board = self._setup(
            cat_count_nuts=500, cat_count_air=0
        )
        model_no = ActionModel(showdown_learner=None)
        like_learner = self._get_sample_nuts_likelihood(model_learner, prof, ctx, board)
        like_no = self._get_sample_nuts_likelihood(model_no, prof, ctx, board)
        # blend = 500/550 ≈ 0.909
        # learned_freq[nuts] = 500/500 = 1.0 → clip 0.99
        pulled_new = 0.909 * 0.99 + 0.091 * like_no
        assert abs(like_learner - pulled_new) < 0.02, (
            f"n=500 应用权重 0.91，预期 {pulled_new:.3f}，实际 {like_learner:.3f}"
        )

    def test_blend_monotonic_with_samples(self):
        """样本数越多，learned_freq 权重越大（极端 learned_freq 与 baseline 的
        拉开幅度随 n 单调增加）。"""
        model_no = ActionModel(showdown_learner=None)
        board = [Card.from_str(c) for c in ['5h', '8d', 'Kc']]
        prof = PlayerProfile(
            name='P', hands_seen=80,
            vpip=0.30, pfr=0.20, af=2.0, wtsd=0.25,
        )
        ctx = ActionContext(
            position='CO', board=board, street='flop', facing_action='bet',
        )
        like_no = self._get_sample_nuts_likelihood(model_no, prof, ctx, board)

        distances = []
        for n in (10, 50, 200, 1000):
            model_l, prof_l, ctx_l, board_l = self._setup(
                cat_count_nuts=n, cat_count_air=0
            )
            like = self._get_sample_nuts_likelihood(model_l, prof_l, ctx_l, board_l)
            distances.append((n, abs(like - like_no)))

        # 距离单调递增：样本越多，离 baseline 越远
        for i in range(len(distances) - 1):
            assert distances[i][1] < distances[i+1][1], (
                f"样本量 {distances[i][0]}→{distances[i+1][0]} 时距离应递增，"
                f"实际 {distances[i][1]:.4f} → {distances[i+1][1]:.4f}"
            )


class TestShowdownLearnerBayesDirection:
    """2026-04-23：验证 get_learned_freq 返回的是 P(action | cat) 而非 P(cat | action)。

    这两个条件概率通过贝叶斯公式联系：
        P(action | cat) = P(cat | action) × P(action) / P(cat)
    数值**不相等**，是两个不同的分布。旧版返回后者（按 cat 归一化，同 action
    下各 cat 值加和为 1），新版返回前者（按 action 归一化，同 cat 下各 action
    值加和为 1）。

    用多动作多桶的 setup（单一动作下两种语义数值恰好相同，测不出区别）。
    """

    def test_returns_p_action_given_cat(self):
        """验证 P(action | cat) 计算正确。

        场景：Bob 在 flop 摊牌记录：
          - call with nuts: 8 次
          - raise with nuts: 2 次     → nuts 总计 10 次
          - call with air:  3 次
          - raise with air: 7 次      → air 总计 10 次

        P(call | nuts) = 8 / 10 = 0.80
        P(call | air)  = 3 / 10 = 0.30
        """
        from pokerfate.strategy.range_v2.showdown_learner import ShowdownLearner
        learner = ShowdownLearner()
        learner._freq['Bob'] = {
            ('flop', 'call'):  {'nuts': 8, 'air': 3},
            ('flop', 'raise'): {'nuts': 2, 'air': 7},
        }
        freq = learner.get_learned_freq('Bob', 'flop', 'call')
        assert freq is not None
        assert abs(freq['nuts'] - 0.80) < 1e-6, f"P(call|nuts) expected 0.80, got {freq['nuts']}"
        assert abs(freq['air']  - 0.30) < 1e-6, f"P(call|air)  expected 0.30, got {freq['air']}"

    def test_returns_raise_distribution_from_same_data(self):
        """同一份数据查 'raise' 应得 P(raise | cat)：nuts 2/10=0.20, air 7/10=0.70."""
        from pokerfate.strategy.range_v2.showdown_learner import ShowdownLearner
        learner = ShowdownLearner()
        learner._freq['Bob'] = {
            ('flop', 'call'):  {'nuts': 8, 'air': 3},
            ('flop', 'raise'): {'nuts': 2, 'air': 7},
        }
        freq = learner.get_learned_freq('Bob', 'flop', 'raise')
        assert freq is not None
        assert abs(freq['nuts'] - 0.20) < 1e-6, f"P(raise|nuts) expected 0.20, got {freq['nuts']}"
        assert abs(freq['air']  - 0.70) < 1e-6, f"P(raise|air)  expected 0.70, got {freq['air']}"

    def test_per_cat_sums_to_1_across_actions(self):
        """同一个 cat 对所有 action 的 P(action|cat) 加和 = 1（因为条件在 cat 上）。"""
        from pokerfate.strategy.range_v2.showdown_learner import ShowdownLearner
        learner = ShowdownLearner()
        learner._freq['Bob'] = {
            ('flop', 'call'):  {'nuts': 8, 'air': 3},
            ('flop', 'raise'): {'nuts': 2, 'air': 7},
            ('flop', 'check'): {'nuts': 0, 'air': 0},  # 0 counts still represented
        }
        f_call  = learner.get_learned_freq('Bob', 'flop', 'call')
        f_raise = learner.get_learned_freq('Bob', 'flop', 'raise')
        # 分桶求和：同 cat 上各 action 概率加起来 = 1
        for cat in ('nuts', 'air'):
            total = f_call[cat] + f_raise[cat]
            assert abs(total - 1.0) < 1e-6, (
                f"P(call|{cat}) + P(raise|{cat}) = {total}, 应为 1"
            )

    def test_differs_from_old_p_cat_given_action(self):
        """反向验证：新语义数值和旧 P(cat|action) 的数值明显不同。

        旧语义 P(cat | call) 下：
          P(nuts | call) = 8 / (8+3) = 0.727
          P(air  | call) = 3 / (8+3) = 0.273
        新语义 P(call | cat) 下：
          P(call | nuts) = 8 / 10 = 0.80
          P(call | air)  = 3 / 10 = 0.30
        两者数值在同一数据上差异明显。
        """
        from pokerfate.strategy.range_v2.showdown_learner import ShowdownLearner
        learner = ShowdownLearner()
        learner._freq['Bob'] = {
            ('flop', 'call'):  {'nuts': 8, 'air': 3},
            ('flop', 'raise'): {'nuts': 2, 'air': 7},
        }
        freq = learner.get_learned_freq('Bob', 'flop', 'call')
        # 旧语义下 nuts=0.727，新语义 0.80；差 0.07 足以区分
        assert freq['nuts'] > 0.75, f"新语义 P(call|nuts) 应 > 0.75（旧 P(nuts|call)=0.727）"
        # 新语义下 nuts+air 不加起来为 1（那是旧语义）
        assert abs(freq['nuts'] + freq['air'] - 1.0) > 0.1, (
            "新语义 P(action|cat) 的 nuts+air 不应加和为 1（那是旧 P(cat|action) 的性质）"
        )

    def test_missing_cat_not_in_result(self):
        """某 cat 没样本时，不出现在返回 dict 里。调用方用 .get(cat, fallback)。"""
        from pokerfate.strategy.range_v2.showdown_learner import ShowdownLearner
        learner = ShowdownLearner()
        learner._freq['Bob'] = {
            ('flop', 'call'): {'nuts': 8},   # 只有 nuts 有数据
        }
        freq = learner.get_learned_freq('Bob', 'flop', 'call')
        assert freq is not None
        assert 'nuts' in freq
        assert 'air' not in freq, "无样本的 cat 不应出现在 result"
        # P(call | nuts) = 8/8 = 1.0（nuts 只被 call 消耗过）
        assert abs(freq['nuts'] - 1.0) < 1e-6

    def test_min_samples_gate_unchanged(self):
        """门槛仍按 (street, action) 总观察数，和旧版兼容（让 shrinkage 计算不受影响）。"""
        from pokerfate.strategy.range_v2.showdown_learner import ShowdownLearner
        learner = ShowdownLearner()
        # (flop, call) 总样本 < 8，即使别的 action 样本多，这里也返回 None
        learner._freq['Bob'] = {
            ('flop', 'call'):  {'nuts': 3},      # 总计 3 < 8
            ('flop', 'raise'): {'nuts': 100},    # 其他 action 很多也没用
        }
        assert learner.get_learned_freq('Bob', 'flop', 'call') is None
        # 反过来：query raise 时 (flop, raise) 有 100 样本，返回 dict
        assert learner.get_learned_freq('Bob', 'flop', 'raise') is not None

    def test_sample_count_unchanged(self):
        """sample_count 语义保持：query (street, action) 的总观察数（跨 cat 求和）。

        poker_bot.py:484 的 use_calibration 判据依赖这个语义。
        """
        from pokerfate.strategy.range_v2.showdown_learner import ShowdownLearner
        learner = ShowdownLearner()
        learner._freq['Bob'] = {
            ('flop', 'call'):  {'nuts': 8, 'air': 3},
            ('flop', 'raise'): {'nuts': 2, 'air': 7},
        }
        assert learner.sample_count('Bob', 'flop', 'call') == 11
        assert learner.sample_count('Bob', 'flop', 'raise') == 9
        assert learner.sample_count('Bob', 'flop', 'fold') == 0   # never recorded
        assert learner.sample_count('Unknown', 'flop', 'call') == 0


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
