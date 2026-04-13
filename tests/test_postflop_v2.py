"""Unit tests for postflop strategy v2 — covering all 14 optimisation points.

Tests are grouped by problem number (P1–P14) so each fix has explicit coverage.
"""

import pytest
import random as _random
from pokerfate.core.card import Card
from pokerfate.strategy.postflop import BoardTexture, PostflopStrategy


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def card(s: str) -> Card:
    return Card.from_str(s)


def cards(*strs) -> list:
    return [Card.from_str(s) for s in strs]


def _strategy(aggression: float = 1.0, seed: int = 0) -> PostflopStrategy:
    """Return a PostflopStrategy pinned to a fixed RNG seed for determinism."""
    s = PostflopStrategy(aggression=aggression)
    s.seed_for_testing(seed)
    return s


def _dry_board() -> BoardTexture:
    return BoardTexture(cards("Kc", "7d", "2s"))


def _wet_board() -> BoardTexture:
    return BoardTexture(cards("Jh", "Th", "8h"))


def _mid_board() -> BoardTexture:
    return BoardTexture(cards("Qd", "9c", "3h"))


# ---------------------------------------------------------------------------
# P14 – RNG isolation & reproducibility
# ---------------------------------------------------------------------------

class TestRNGIsolation:
    """P14: every decision uses a per-instance RNG; fixed seed = exact replay."""

    def test_seed_for_testing_gives_same_result(self):
        s = PostflopStrategy()
        board = _dry_board()
        results = []
        for _ in range(2):
            s.seed_for_testing(42)
            outcomes = [
                s.should_cbet(0.40, board, True, 'flop')
                for _ in range(20)
            ]
            results.append(outcomes)
        assert results[0] == results[1], "Same seed must produce identical sequence"

    def test_different_seeds_may_differ(self):
        """Two different seeds should produce at least sometimes-different results."""
        board = _dry_board()
        s = PostflopStrategy()
        s.seed_for_testing(1)
        r1 = [s.should_cbet(0.40, board, True, 'flop') for _ in range(50)]
        s.seed_for_testing(999)
        r2 = [s.should_cbet(0.40, board, True, 'flop') for _ in range(50)]
        # Not guaranteed to differ on every element, but overwhelmingly should
        assert r1 != r2, "Different seeds should generally produce different sequences"

    def test_global_random_state_unaffected(self):
        """PostflopStrategy must not mutate the global random state."""
        _random.seed(777)
        before = _random.random()
        _random.seed(777)
        s = PostflopStrategy()
        s.seed_for_testing(42)
        for _ in range(100):
            s.should_cbet(0.50, _dry_board(), True, 'flop')
        after = _random.random()
        assert before == after, "Global random state must not change"

    def test_decision_seed_stored(self):
        """decide() must store _last_decision_seed after each call."""
        s = PostflopStrategy()
        board_cards = cards("As", "Kd", "2c")
        s.decide(
            equity=0.75, pot=100.0, to_call=0.0, stack=500.0,
            board=board_cards, is_ip=True, street='flop',
            facing_bet=False, num_opponents=1, big_blind=2.0,
        )
        assert s._last_decision_seed != 0, "_last_decision_seed must be set after decide()"

    def test_cbet_detail_populated(self):
        """After should_cbet(), _last_cbet_detail should contain branch and ag."""
        s = _strategy()
        s.should_cbet(0.70, _dry_board(), True, 'flop')
        assert 'branch' in s._last_cbet_detail
        assert 'ag' in s._last_cbet_detail

    def test_bet_detail_populated_on_bet(self):
        """bet_size() must populate _last_bet_detail."""
        s = _strategy()
        s.bet_size(0.70, 100.0, _dry_board(), 500.0, 'flop', 2.0)
        assert 'final_frac' in s._last_bet_detail
        assert 'reason' in s._last_bet_detail


# ---------------------------------------------------------------------------
# P2 – OOP monster: preserve check-raise space
# ---------------------------------------------------------------------------

class TestOOPMonsterCheckRaise:
    """P2: OOP equity >= 0.90 should be less likely to directly cbet (vs. old +8pp)."""

    def test_oop_monster_bet_prob_lower_than_ip(self):
        """OOP monster cbet freq must be lower than IP monster (check-raise space)."""
        board = _dry_board()
        n_trials = 500
        ip_bets = sum(
            1 for i in range(n_trials)
            if _strategy(seed=i).should_cbet(0.95, board, True, 'flop')
        )
        oop_bets = sum(
            1 for i in range(n_trials)
            if _strategy(seed=i).should_cbet(0.95, board, False, 'flop')
        )
        ip_rate = ip_bets / n_trials
        oop_rate = oop_bets / n_trials
        # OOP should bet less often than IP (not more, as old code did)
        assert oop_rate < ip_rate, (
            f"OOP ({oop_rate:.0%}) should bet less than IP ({ip_rate:.0%}) with monster"
        )

    def test_oop_monster_still_bets_most_of_time(self):
        """Even with reduced freq, OOP monster must still bet >40% of the time."""
        board = _dry_board()
        bets = sum(
            1 for i in range(500)
            if _strategy(seed=i).should_cbet(0.95, board, False, 'flop')
        )
        assert bets / 500 >= 0.40, "OOP monster cbet rate should be >= 40%"


# ---------------------------------------------------------------------------
# P3 – fold_to_cbet gates semi-bluff EV
# ---------------------------------------------------------------------------

class TestFoldToCbetEVGate:
    """P3: when fold_to_cbet is very low, semi-bluff EV is negative → check."""

    def test_low_fold_rate_suppresses_semi_bluff(self):
        """fold_to_cbet=0.15 → bluff_ev < 0 → should NOT bet with equity=0.40."""
        board = _dry_board()
        bets = sum(
            1 for i in range(500)
            if _strategy(seed=i).should_cbet(
                0.40, board, True, 'flop',
                opponent_fold_rate=0.15, fold_to_cbet=0.15,
            )
        )
        # Near-zero fold equity → semi-bluff should be heavily suppressed
        assert bets / 500 <= 0.20, (
            f"With fold_to_cbet=0.15 semi-bluff rate={bets/500:.0%} should be ≤20%"
        )

    def test_high_fold_rate_allows_semi_bluff(self):
        """fold_to_cbet=0.60 → bluff EV positive → semi-bluffs should fire normally."""
        board = _dry_board()
        bets = sum(
            1 for i in range(500)
            if _strategy(seed=i).should_cbet(
                0.40, board, True, 'flop',
                opponent_fold_rate=0.60, fold_to_cbet=0.60,
            )
        )
        assert bets / 500 >= 0.35, (
            f"With fold_to_cbet=0.60 semi-bluff rate={bets/500:.0%} should be ≥35%"
        )


# ---------------------------------------------------------------------------
# P4 – River OOP thin value frequency depends on opponent type
# ---------------------------------------------------------------------------

class TestRiverOOPThinValue:
    """P4: OOP river thin value (eq 0.60-0.70) should differ by opponent fold rate."""

    def test_oop_thin_value_vs_calling_station_high_freq(self):
        """vs calling station (low fold_rate) OOP river thin value is aggressive."""
        n = 500
        bets = sum(
            1 for i in range(n)
            if _strategy(seed=i).should_cbet(
                0.65, _dry_board(), False, 'river',
                opponent_fold_rate=0.25,   # calling station
            )
        )
        assert bets / n >= 0.70, f"vs calling station river OOP bet={bets/n:.0%} should be ≥70%"

    def test_oop_thin_value_vs_balanced_opp_lower_freq(self):
        """vs balanced opponent OOP river thin value is more cautious."""
        n = 500
        bets = sum(
            1 for i in range(n)
            if _strategy(seed=i).should_cbet(
                0.65, _dry_board(), False, 'river',
                opponent_fold_rate=0.55,   # balanced/tight
            )
        )
        assert bets / n <= 0.75, f"vs balanced opp river OOP bet={bets/n:.0%} should be ≤75%"

    def test_oop_lower_than_old_92_for_balanced(self):
        """New OOP thin value freq with balanced opp must be below old 92% cap."""
        n = 500
        bets = sum(
            1 for i in range(n)
            if _strategy(seed=i).should_cbet(
                0.63, _dry_board(), False, 'river',
                opponent_fold_rate=0.50,
            )
        )
        assert bets / n < 0.85, f"OOP river thin value {bets/n:.0%} should be <85% (old was 92%)"


# ---------------------------------------------------------------------------
# P5 – Multi-street sizing consistency
# ---------------------------------------------------------------------------

class TestMultiStreetConsistency:
    """P5: turn bet size should be constrained by flop bet size (no jarring jumps)."""

    def test_small_flop_limits_turn_max(self):
        """After a small flop bet (≤33%), turn bet fraction should not exceed 66%."""
        board_c = cards("Kc", "7d", "2s")
        s = _strategy(seed=100)
        # Store a small flop bet
        s._last_bet_frac = 0.33
        s._last_bet_street = 'flop'
        texture = BoardTexture(board_c)
        # Turn equity 0.80 would normally give 66-75% options
        turn_frac = s._last_bet_detail.get('final_frac', None)
        # Compute via bet_size directly
        turn_size = s.bet_size(0.80, 100.0, texture, 500.0, 'turn', 2.0, last_bet_frac=0.33)
        # 66% pot of 100 = 66
        assert turn_size <= 68.0, f"Turn size {turn_size} after small flop should be ≤68 (≤66% pot)"

    def test_large_flop_prevents_too_small_turn(self):
        """After a large flop bet (≥66%), turn bet should not drop below 50% pot."""
        board_c = cards("Jh", "Th", "8h")
        s = _strategy(seed=200)
        s._last_bet_frac = 0.75
        s._last_bet_street = 'flop'
        texture = BoardTexture(board_c)
        turn_size = s.bet_size(0.45, 100.0, texture, 500.0, 'turn', 2.0, last_bet_frac=0.75)
        # 50% pot of 100 = 50; give some slack for min_bet
        assert turn_size >= 48.0, f"Turn size {turn_size} after large flop should be ≥48 (≥50% pot)"


# ---------------------------------------------------------------------------
# P6 – Delayed c-bet threshold reduction
# ---------------------------------------------------------------------------

class TestDelayedCbet:
    """P6: is_delayed_cbet=True lowers equity threshold / raises frequency."""

    def test_delayed_cbet_higher_freq_than_normal(self):
        """Delayed cbet (checked flop) should fire more often than normal cbet at same equity."""
        board = _dry_board()
        equity = 0.48  # just below normal semi-bluff threshold

        normal_bets = sum(
            1 for i in range(500)
            if _strategy(seed=i).should_cbet(
                equity, board, True, 'turn', is_delayed_cbet=False
            )
        )
        delayed_bets = sum(
            1 for i in range(500)
            if _strategy(seed=i).should_cbet(
                equity, board, True, 'turn', is_delayed_cbet=True
            )
        )
        assert delayed_bets >= normal_bets, (
            f"Delayed cbet ({delayed_bets/500:.0%}) should fire >= normal ({normal_bets/500:.0%})"
        )

    def test_delayed_cbet_flag_in_detail(self):
        s = _strategy()
        s.should_cbet(0.48, _dry_board(), True, 'turn', is_delayed_cbet=True)
        assert s._last_cbet_detail.get('eq_discount', 0) >= 0.05


# ---------------------------------------------------------------------------
# P7 – Donk bet (OOP, IP checked back)
# ---------------------------------------------------------------------------

class TestDonkBet:
    """P7: OOP should occasionally donk-bet turn when IP checked flop."""

    def test_donk_bet_only_oop(self):
        """should_donk_bet must return False for IP players."""
        s = _strategy()
        assert not s.should_donk_bet(0.70, _dry_board(), 'turn', is_ip=True)

    def test_donk_bet_not_on_flop(self):
        """Flop donk bet should always be False (GTO flop donk ≈ 0)."""
        s = _strategy()
        for eq in [0.40, 0.60, 0.80]:
            assert not s.should_donk_bet(eq, _dry_board(), 'flop', is_ip=False)

    def test_donk_bet_fires_oop_turn_strong_hand(self):
        """OOP turn with equity >= 0.65 should donk sometimes."""
        n = 300
        fires = sum(
            1 for i in range(n)
            if _strategy(seed=i).should_donk_bet(0.72, _dry_board(), 'turn', is_ip=False)
        )
        assert fires / n >= 0.25, f"OOP turn donk with eq=0.72 should fire ≥25%, got {fires/n:.0%}"

    def test_donk_bet_rare_with_weak_hand(self):
        """OOP turn donk with equity < 0.40 should be rare."""
        n = 300
        fires = sum(
            1 for i in range(n)
            if _strategy(seed=i).should_donk_bet(0.35, _dry_board(), 'turn', is_ip=False)
        )
        assert fires / n <= 0.25, f"Weak hand donk should be rare, got {fires/n:.0%}"

    def test_donk_triggers_in_decide_when_opponent_checked_back(self):
        """decide() with opponent_checked_back=True and OOP should sometimes raise."""
        board_c = cards("Kc", "7d", "2s")
        raises = 0
        for i in range(100):
            s = _strategy(seed=i)
            action, _ = s.decide(
                equity=0.75, pot=100.0, to_call=0.0, stack=500.0,
                board=board_c, is_ip=False, street='turn',
                facing_bet=False, num_opponents=1, big_blind=2.0,
                opponent_checked_back=True,
            )
            if action == 'raise':
                raises += 1
        assert raises >= 30, f"OOP turn with opponent check-back and eq=0.75 should raise often"


# ---------------------------------------------------------------------------
# P8 – opponent_af affects cbet frequency
# ---------------------------------------------------------------------------

class TestOpponentAFEffect:
    """P8: high AF → reduce cbet freq; low AF → increase cbet freq."""

    def test_high_af_reduces_bluff_freq(self):
        """Against aggressive opponent (AF=3.0), semi-bluff frequency should be lower."""
        board = _dry_board()
        n = 500
        normal_bets = sum(
            1 for i in range(n)
            if _strategy(seed=i).should_cbet(0.40, board, True, 'flop', opponent_af=1.5)
        )
        high_af_bets = sum(
            1 for i in range(n)
            if _strategy(seed=i).should_cbet(0.40, board, True, 'flop', opponent_af=3.0)
        )
        assert high_af_bets <= normal_bets, (
            f"High AF ({high_af_bets/n:.0%}) should bet <= normal ({normal_bets/n:.0%})"
        )

    def test_low_af_increases_bluff_freq(self):
        """Against passive opponent (AF=0.7), semi-bluff frequency should be higher."""
        board = _dry_board()
        n = 500
        normal_bets = sum(
            1 for i in range(n)
            if _strategy(seed=i).should_cbet(0.40, board, True, 'flop', opponent_af=1.5)
        )
        low_af_bets = sum(
            1 for i in range(n)
            if _strategy(seed=i).should_cbet(0.40, board, True, 'flop', opponent_af=0.7)
        )
        assert low_af_bets >= normal_bets, (
            f"Low AF ({low_af_bets/n:.0%}) should bet >= normal ({normal_bets/n:.0%})"
        )


# ---------------------------------------------------------------------------
# P9 – Probe: opponent_checked_back boosts cbet frequency
# ---------------------------------------------------------------------------

class TestProbeDetection:
    """P9: opponent_checked_back=True should increase cbet frequency (probe scenario)."""

    def test_probe_increases_semi_bluff_freq(self):
        board = _dry_board()
        n = 500
        normal = sum(
            1 for i in range(n)
            if _strategy(seed=i).should_cbet(
                0.40, board, True, 'turn', opponent_checked_back=False
            )
        )
        probe = sum(
            1 for i in range(n)
            if _strategy(seed=i).should_cbet(
                0.40, board, True, 'turn', opponent_checked_back=True
            )
        )
        assert probe >= normal, (
            f"Probe ({probe/n:.0%}) should fire >= normal cbet ({normal/n:.0%})"
        )

    def test_probe_increases_air_freq(self):
        board = _dry_board()
        n = 500
        normal = sum(
            1 for i in range(n)
            if _strategy(seed=i).should_cbet(
                0.15, board, True, 'turn',
                opponent_fold_rate=0.60, opponent_checked_back=False
            )
        )
        probe = sum(
            1 for i in range(n)
            if _strategy(seed=i).should_cbet(
                0.15, board, True, 'turn',
                opponent_fold_rate=0.60, opponent_checked_back=True
            )
        )
        assert probe >= normal, "Probe should also boost air bluff frequency"


# ---------------------------------------------------------------------------
# P10 – Wet board weak semi-bluff uses larger sizing
# ---------------------------------------------------------------------------

class TestWetBoardSemiBluffSizing:
    """P10: weak semi-bluffs on wet boards should use larger sizes to deny equity."""

    def test_wet_weak_bluff_larger_than_dry(self):
        """On wet board, weak semi-bluff median size should be >= dry board."""
        dry = _dry_board()
        wet = _wet_board()

        dry_sizes = [
            _strategy(seed=i).bet_size(0.35, 100.0, dry, 500.0, 'flop', 2.0)
            for i in range(200)
        ]
        wet_sizes = [
            _strategy(seed=i).bet_size(0.35, 100.0, wet, 500.0, 'flop', 2.0)
            for i in range(200)
        ]
        dry_med = sorted(dry_sizes)[len(dry_sizes) // 2]
        wet_med = sorted(wet_sizes)[len(wet_sizes) // 2]
        assert wet_med >= dry_med, (
            f"Wet board weak bluff size {wet_med:.0f} should be >= dry {dry_med:.0f}"
        )

    def test_wet_weak_bluff_min_50pct(self):
        """Wet board weak semi-bluff should never use < 50% pot."""
        wet = _wet_board()
        sizes = [
            _strategy(seed=i).bet_size(0.35, 100.0, wet, 500.0, 'flop', 2.0)
            for i in range(200)
        ]
        # 50% pot = 50; account for min_bet effects
        assert min(sizes) >= 48.0, f"Wet weak bluff min size {min(sizes):.0f} should be >= 48"


# ---------------------------------------------------------------------------
# P11 – Multiway strong value: equity_bonus continuous weight
# ---------------------------------------------------------------------------

class TestMultiwayEquityBonus:
    """P11: in multiway pots, higher equity → higher cbet frequency (continuous)."""

    def test_higher_equity_higher_freq_multiway(self):
        """equity=0.85 should fire more often than equity=0.62 in multiway."""
        board = _dry_board()
        n = 500
        lo_bets = sum(
            1 for i in range(n)
            if _strategy(seed=i).should_cbet(0.62, board, True, 'flop', num_opponents=3)
        )
        hi_bets = sum(
            1 for i in range(n)
            if _strategy(seed=i).should_cbet(0.85, board, True, 'flop', num_opponents=3)
        )
        assert hi_bets > lo_bets, (
            f"eq=0.85 ({hi_bets/n:.0%}) should fire > eq=0.62 ({lo_bets/n:.0%}) in multiway"
        )

    def test_multiway_never_zero_with_strong_equity(self):
        """In 4-way, equity=0.85 should still fire often (>40%)."""
        board = _dry_board()
        n = 500
        bets = sum(
            1 for i in range(n)
            if _strategy(seed=i).should_cbet(0.85, board, True, 'flop', num_opponents=4)
        )
        assert bets / n >= 0.40, (
            f"4-way, eq=0.85: cbet rate {bets/n:.0%} should be ≥40% (old clamp was 50%)"
        )


# ---------------------------------------------------------------------------
# P12 – Air bluff equity decay
# ---------------------------------------------------------------------------

class TestAirBluffEquityDecay:
    """P12: equity=0.05 should bluff less than equity=0.25 (linear decay)."""

    def test_lower_equity_lower_bluff_freq(self):
        board = _dry_board()
        n = 500
        # equity=0.25 (near semi-bluff threshold)
        hi_eq_bets = sum(
            1 for i in range(n)
            if _strategy(seed=i).should_cbet(
                0.25, board, True, 'flop', opponent_fold_rate=0.70
            )
        )
        # equity=0.05 (pure air)
        lo_eq_bets = sum(
            1 for i in range(n)
            if _strategy(seed=i).should_cbet(
                0.05, board, True, 'flop', opponent_fold_rate=0.70
            )
        )
        assert lo_eq_bets < hi_eq_bets, (
            f"Air (eq=0.05, {lo_eq_bets/n:.0%}) should bluff less than eq=0.25 ({hi_eq_bets/n:.0%})"
        )

    def test_zero_equity_almost_never_bluffs(self):
        """equity≈0 should almost never bluff even with high fold rate."""
        board = _dry_board()
        n = 500
        bets = sum(
            1 for i in range(n)
            if _strategy(seed=i).should_cbet(
                0.01, board, True, 'flop', opponent_fold_rate=0.80
            )
        )
        assert bets / n <= 0.05, (
            f"equity≈0 bluff rate {bets/n:.0%} should be ≤5%"
        )


# ---------------------------------------------------------------------------
# P13 – Position granularity (BTN > CO > neutral > LJ > UTG)
# ---------------------------------------------------------------------------

class TestPositionGranularity:
    """P13: BTN cbet freq > CO > MP > LJ > UTG at same equity."""

    def _freq_at_pos(self, equity: float, position: str, n: int = 500) -> float:
        board = _dry_board()
        bets = sum(
            1 for i in range(n)
            if _strategy(seed=i).should_cbet(equity, board, True, 'flop', position=position)
        )
        return bets / n

    def test_btn_more_aggressive_than_utg(self):
        eq = 0.45
        btn = self._freq_at_pos(eq, "BTN")
        utg = self._freq_at_pos(eq, "UTG")
        assert btn > utg, f"BTN ({btn:.0%}) should cbet more than UTG ({utg:.0%})"

    def test_btn_more_than_co(self):
        eq = 0.45
        btn = self._freq_at_pos(eq, "BTN")
        co = self._freq_at_pos(eq, "CO")
        assert btn >= co, f"BTN ({btn:.0%}) should cbet >= CO ({co:.0%})"

    def test_utg_more_conservative_than_lj(self):
        eq = 0.45
        utg = self._freq_at_pos(eq, "UTG")
        lj = self._freq_at_pos(eq, "LJ")
        assert utg <= lj, f"UTG ({utg:.0%}) should be <= LJ ({lj:.0%})"


# ---------------------------------------------------------------------------
# P1 – Nut advantage increases bet size
# ---------------------------------------------------------------------------

class TestNutAdvantageSizing:
    """P1: higher nut_advantage should produce larger bet sizes."""

    def test_nut_advantage_increases_river_size(self):
        """River near-nut with nut_advantage=0.8 should produce larger bets than 0.0."""
        texture = _dry_board()
        n = 200
        no_adv = [
            _strategy(seed=i).bet_size(0.88, 100.0, texture, 500.0, 'river', 2.0, nut_advantage=0.0)
            for i in range(n)
        ]
        hi_adv = [
            _strategy(seed=i).bet_size(0.88, 100.0, texture, 500.0, 'river', 2.0, nut_advantage=0.8)
            for i in range(n)
        ]
        assert sum(hi_adv) / n >= sum(no_adv) / n, (
            "Higher nut_advantage should produce larger or equal average bet size"
        )

    def test_nut_advantage_no_effect_on_weak_hands(self):
        """For weak hands (equity=0.35), nut_advantage should not dramatically increase size."""
        texture = _dry_board()
        n = 200
        no_adv = [
            _strategy(seed=i).bet_size(0.35, 100.0, texture, 500.0, 'flop', 2.0, nut_advantage=0.0)
            for i in range(n)
        ]
        hi_adv = [
            _strategy(seed=i).bet_size(0.35, 100.0, texture, 500.0, 'flop', 2.0, nut_advantage=0.8)
            for i in range(n)
        ]
        # For weak hands, nut advantage bonus requires equity >= 0.65, so should be minimal
        avg_no = sum(no_adv) / n
        avg_hi = sum(hi_adv) / n
        # The difference should be small (texture-dominated)
        assert abs(avg_hi - avg_no) < avg_no * 0.30, (
            "Nut advantage on weak hands should not dramatically change size"
        )


# ---------------------------------------------------------------------------
# Integration: decide() respects all new params
# ---------------------------------------------------------------------------

class TestDecideIntegration:
    """Smoke tests that decide() correctly routes new parameters."""

    def _decide(self, equity, street='flop', is_ip=True, facing_bet=False, **kwargs):
        board_c = cards("Kc", "7d", "2s")
        s = PostflopStrategy()
        return s.decide(
            equity=equity, pot=100.0, to_call=0.0, stack=500.0,
            board=board_c, is_ip=is_ip, street=street,
            facing_bet=facing_bet, num_opponents=1, big_blind=2.0,
            **kwargs,
        )

    def test_value_only_never_bluffs(self):
        """value_only=True: equity < 0.50 must always check."""
        for _ in range(20):
            action, _ = self._decide(0.35, value_only=True)
            assert action == 'check', "value_only must not bluff"

    def test_strong_hand_always_bets_hu(self):
        """equity=0.75 HU should always bet (not check) on flop."""
        for seed in range(30):
            s = _strategy(seed=seed)
            board_c = cards("Kc", "7d", "2s")
            action, _ = s.decide(
                equity=0.75, pot=100.0, to_call=0.0, stack=500.0,
                board=board_c, is_ip=True, street='flop',
                facing_bet=False, num_opponents=1, big_blind=2.0,
            )
            assert action == 'raise', f"seed={seed}: equity=0.75 HU should always bet"

    def test_multiway_low_equity_checks(self):
        """equity=0.30, 3 opponents should almost always check (P6 multiway floor)."""
        board_c = cards("Kc", "7d", "2s")
        checks = 0
        for i in range(100):
            s = _strategy(seed=i)
            action, _ = s.decide(
                equity=0.30, pot=100.0, to_call=0.0, stack=500.0,
                board=board_c, is_ip=True, street='flop',
                facing_bet=False, num_opponents=3, big_blind=2.0,
            )
            if action == 'check':
                checks += 1
        assert checks >= 90, f"equity=0.30 with 3 opponents: {checks}/100 checks, expected >=90"

    def test_decide_seed_changes_each_call(self):
        """Two successive decide() calls should use different seeds."""
        board_c = cards("Kc", "7d", "2s")
        s = PostflopStrategy()
        s.decide(
            equity=0.60, pot=100.0, to_call=0.0, stack=500.0,
            board=board_c, is_ip=True, street='flop',
            facing_bet=False, num_opponents=1, big_blind=2.0,
        )
        seed1 = s._last_decision_seed
        s.decide(
            equity=0.60, pot=100.0, to_call=0.0, stack=500.0,
            board=board_c, is_ip=True, street='flop',
            facing_bet=False, num_opponents=1, big_blind=2.0,
        )
        seed2 = s._last_decision_seed
        # Two calls from os.urandom should essentially never collide
        assert seed1 != seed2, "Each decide() should use a fresh seed"
