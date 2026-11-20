"""Tests for GTO math module."""

from pokerfate.strategy.gto import GTOMath


class TestGTOMath:
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
