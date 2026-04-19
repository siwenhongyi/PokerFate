"""GTO mathematical principles: MDF, bluff frequencies, EV calculations."""

from __future__ import annotations
import random


class GTOMath:
    @staticmethod
    def minimum_defense_frequency(bet_size: float, pot_before_bet: float) -> float:
        """MDF: fraction of range we must defend to prevent profitable bluffing.

        MDF = pot / (pot + bet)
        """
        if bet_size <= 0:
            return 1.0
        return pot_before_bet / (pot_before_bet + bet_size)

    @staticmethod
    def required_equity_to_call(call_amount: float, pot_after_call: float) -> float:
        """Minimum equity required to profitably call.

        equity = call / pot_after_call
        """
        if pot_after_call <= 0:
            return 1.0
        return call_amount / pot_after_call

    @staticmethod
    def optimal_bluff_frequency(bet_size: float, pot_before_bet: float) -> float:
        """Optimal river bluff frequency to make opponent indifferent.

        bluff_freq = bet / (bet + pot)
        This equals (1 - MDF) from the bettor's perspective.
        """
        total = bet_size + pot_before_bet
        if total <= 0:
            return 0.0
        return bet_size / total

    @staticmethod
    def ev_call(equity: float, pot: float, call_amount: float) -> float:
        """EV of calling = equity * pot - (1-equity) * call_amount."""
        return equity * pot - (1.0 - equity) * call_amount

    @staticmethod
    def ev_bet(fold_equity: float, equity: float, pot: float, bet: float) -> float:
        """EV of betting = fold_equity * pot + (1-fold_equity) * equity * (pot+bet)
           - (1-fold_equity) * (1-equity) * bet
        """
        return (fold_equity * pot
                + (1 - fold_equity) * equity * (pot + bet)
                - (1 - fold_equity) * (1 - equity) * bet)

    @staticmethod
    def breakeven_fold_rate(bet: float, pot: float) -> float:
        """How often opponent must fold for a bluff to break even.

        fold_rate = bet / (pot + bet)
        """
        return bet / (pot + bet)

    @staticmethod
    def bet_size_for_equity(equity: float, pot: float) -> float:
        """Recommended bet size when you have a given equity advantage.

        Uses polarization principle: bet more when more polarized.
        Returns a fraction of pot (0.25 to 1.0).
        """
        if equity >= 0.85:
            return pot * 1.0    # pot-size or overbet
        if equity >= 0.75:
            return pot * 0.75
        if equity >= 0.65:
            return pot * 0.5
        if equity >= 0.55:
            return pot * 0.33
        return pot * 0.25

    @staticmethod
    def should_bluff(
        equity: float,
        pot: float,
        bet: float,
        opponent_fold_rate: float,
        bluff_frequency_cap: float = 0.4,
    ) -> bool:
        """Decide whether to bluff given opponent fold rate and GTO constraints."""
        optimal_freq = GTOMath.optimal_bluff_frequency(bet, pot)
        actual_freq = min(optimal_freq, bluff_frequency_cap)
        # Only bluff if equity is low (no showdown value) and bluff has +EV
        if equity > 0.35:
            return False  # Has showdown value, don't need to bluff
        ev = GTOMath.ev_bet(opponent_fold_rate, equity, pot, bet)
        return ev > 0 and random.random() < actual_freq

    @staticmethod
    def spr(stack: float, pot: float) -> float:
        """Stack-to-pot ratio."""
        return stack / max(pot, 0.01)

    @staticmethod
    def spr_category(spr: float) -> str:
        """Human-readable SPR bucket for logs and sizing."""
        if spr < 4.0:
            return "低SPR"
        if spr < 8.0:
            return "中SPR"
        if spr < 15.0:
            return "偏高SPR"
        return "深SPR"

    @staticmethod
    def stack_bb_category(stack: float, big_blind: float) -> str:
        """Effective depth in big blinds (preflop / general)."""
        bb = max(big_blind, 1e-9)
        s = stack / bb
        if s < 22.0:
            return "短码"
        if s < 45.0:
            return "标准"
        if s < 100.0:
            return "深码"
        return "超深"

    @staticmethod
    def implied_odds_bonus(spr: float, street: str) -> float:
        """Extra equity credit for drawing hands (not river). Deep stacks → more."""
        if street == "river":
            return 0.0
        if spr >= 15.0:
            return 0.08
        if spr >= 8.0:
            return 0.06
        if spr >= 4.0:
            return 0.04
        return 0.02

    @staticmethod
    def geometric_frac(spr: float, streets_left: int) -> float:
        """每街下多少 % pot，刚好在最后一街 all-in。

        数学: ((1+2*spr)^(1/n) - 1) / 2
        底池每街增长 (1+2b) 倍，n 街后 pot×(1+2b)^n = pot+2×stack。
        例: SPR=8, 3街 → ~0.79;  SPR=4, 3街 → ~0.54;  SPR=2, 3街 → ~0.36
        用作分街尺度上限的参考锚点，防止前面街透支后续价值空间。
        """
        if streets_left <= 0 or spr <= 0:
            return 0.5
        ratio = 1.0 + 2.0 * spr
        return (ratio ** (1.0 / streets_left) - 1.0) / 2.0

    @staticmethod
    def pot_fraction_bet(fraction: float, pot: float, min_bet: float, stack: float) -> float:
        """Calculate a bet of `fraction` of pot, clamped to stack."""
        return min(max(pot * fraction, min_bet), stack)
