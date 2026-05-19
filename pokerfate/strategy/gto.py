"""GTO mathematical principles: MDF, bluff frequencies, EV calculations."""

from __future__ import annotations


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
    def breakeven_fold_rate(bet: float, pot: float) -> float:
        """How often opponent must fold for a bluff to break even.

        fold_rate = bet / (pot + bet)
        """
        return bet / (pot + bet)

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
        if s < 20.0:
            return "短码"
        if s < 40.0:
            return "浅码"
        if s < 70.0:
            return "中浅码"
        if s < 100.0:
            return "标准码"
        if s < 150.0:
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
    def pot_fraction_bet(fraction: float, pot: float, min_bet: float, stack: float) -> float:
        """Calculate a bet of `fraction` of pot, clamped to stack."""
        return min(max(pot * fraction, min_bet), stack)
