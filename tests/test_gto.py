"""Tests for GTO math module."""

import pytest
from pokerfate.strategy.gto import GTOMath


class TestGTOMath:
    def test_mdf_half_pot(self):
        # Half-pot bet: MDF should be 2/3
        mdf = GTOMath.minimum_defense_frequency(50, 100)
        assert abs(mdf - 2/3) < 0.01

    def test_mdf_pot_size(self):
        # Pot-size bet: MDF should be 1/2
        mdf = GTOMath.minimum_defense_frequency(100, 100)
        assert abs(mdf - 0.5) < 0.01

    def test_required_equity_call(self):
        # Call 50 into pot of 150 total after call (was 100)
        eq = GTOMath.required_equity_to_call(50, 150)
        assert abs(eq - 1/3) < 0.01

    def test_optimal_bluff_frequency(self):
        # Bet 50 into 100: bluff freq = 50/150 ≈ 0.33
        freq = GTOMath.optimal_bluff_frequency(50, 100)
        assert abs(freq - 1/3) < 0.01

    def test_breakeven_fold_rate(self):
        # Bet 100 into 100 pot: need fold 50% of time
        fold_rate = GTOMath.breakeven_fold_rate(100, 100)
        assert abs(fold_rate - 0.5) < 0.01

    def test_ev_call_profitable(self):
        # 60% equity, pot=100, call=40
        ev = GTOMath.ev_call(0.60, 100, 40)
        assert ev > 0

    def test_ev_call_losing(self):
        # 20% equity, pot=100, call=40
        ev = GTOMath.ev_call(0.20, 100, 40)
        assert ev < 0

    def test_spr(self):
        spr = GTOMath.spr(200, 40)
        assert abs(spr - 5.0) < 0.01

    def test_pot_fraction_bet(self):
        bet = GTOMath.pot_fraction_bet(0.5, 100, 2, 200)
        assert abs(bet - 50.0) < 0.01

    def test_pot_fraction_bet_stack_cap(self):
        bet = GTOMath.pot_fraction_bet(0.75, 100, 2, 30)
        assert bet == 30.0  # capped by stack
