"""Postflop strategy: board texture analysis, c-bet, bet sizing decisions."""

from __future__ import annotations
import random
from typing import List, Tuple
from ..core.card import Card, Rank, Suit
from .gto import GTOMath


class BoardTexture:
    """Analyze the texture of the community cards."""

    def __init__(self, board: List[Card]):
        self.board = board
        self.ranks = [c.rank.value for c in board]
        self.suits = [c.suit.value for c in board]
        self._analyze()

    def _analyze(self):
        from collections import Counter
        rank_cnt = Counter(self.ranks)
        suit_cnt = Counter(self.suits)

        self.is_paired = max(rank_cnt.values(), default=0) >= 2
        self.is_tripled = max(rank_cnt.values(), default=0) >= 3
        self.flush_draw = max(suit_cnt.values(), default=0) >= 2
        self.monotone = max(suit_cnt.values(), default=0) >= 3

        sorted_ranks = sorted(set(self.ranks), reverse=True)
        gaps = []
        for i in range(len(sorted_ranks) - 1):
            gaps.append(sorted_ranks[i] - sorted_ranks[i + 1])
        self.connected = len(gaps) > 0 and min(gaps) <= 2
        self.max_gap = max(gaps) if gaps else 99

        # Wetness score [0, 1]: 0 = bone dry, 1 = very wet
        wetness = 0.0
        if self.flush_draw:
            wetness += 0.35
        if self.monotone:
            wetness += 0.25
        if self.connected:
            wetness += 0.25
        if not self.is_paired:
            wetness += 0.15
        self.wetness = min(wetness, 1.0)

    @property
    def is_dry(self) -> bool:
        return self.wetness < 0.35

    @property
    def is_wet(self) -> bool:
        return self.wetness >= 0.55

    def recommended_cbet_size_fraction(self) -> float:
        """Fraction of pot recommended for c-bet based on board texture."""
        if self.is_dry:
            return 0.33
        if self.is_wet:
            return 0.66
        return 0.5

    def __repr__(self) -> str:
        return (f"BoardTexture(wetness={self.wetness:.2f}, paired={self.is_paired}, "
                f"flush_draw={self.flush_draw}, connected={self.connected})")


class PostflopStrategy:
    """Postflop decision engine."""

    def __init__(self, aggression: float = 1.0):
        """aggression: multiplier on betting frequencies. 1.0 = balanced GTO."""
        self.aggression = aggression
        self.value_mult = 1.0   # bet-size multiplier for exploitative value sizing
        self.gto = GTOMath()

    def should_cbet(
        self,
        equity: float,
        board: BoardTexture,
        is_ip: bool,
        street: str,
        num_opponents: int = 1,
        opponent_fold_rate: float = 0.45,
    ) -> bool:
        """Decide whether to make a continuation bet."""
        # Monster hand: mostly bet, but check 20% to protect checking range
        # (prevents opponent from always knowing we're weak when we check)
        if equity >= 0.90:
            return random.random() < (0.80 * self.aggression)

        # Strong hand: almost always bet
        if equity >= 0.70:
            return True

        # Very weak hand (no equity, no fold equity): give up
        if equity < 0.20 and opponent_fold_rate < 0.40:
            return False

        # Semi-bluff zone: bet with fold equity
        if 0.30 <= equity <= 0.65:
            freq = 0.65 if board.is_dry else 0.45
            freq *= self.aggression
            if not is_ip:
                freq *= 0.85
            if num_opponents > 1:
                freq *= (0.6 ** (num_opponents - 1))
            return random.random() < freq

        # Thin value / air: bet based on fold equity only
        freq_base = 0.55 if board.is_dry else 0.35
        freq_base *= self.aggression
        if not is_ip:
            freq_base *= 0.80
        if num_opponents > 1:
            freq_base *= (0.5 ** (num_opponents - 1))
        return random.random() < freq_base

    def bet_size(
        self,
        equity: float,
        pot: float,
        board: BoardTexture,
        stack: float,
        street: str,
        big_blind: float,
    ) -> float:
        """Determine bet size given equity and board texture."""
        min_bet = big_blind

        if street == 'river':
            if equity >= 0.80:
                frac = 0.75
            elif equity >= 0.60:
                frac = 0.5
            else:
                frac = 0.66 if board.is_wet else 0.5
        elif street == 'turn':
            if equity >= 0.75:
                frac = 0.75
            else:
                frac = 0.6
        else:
            # Flop
            frac = board.recommended_cbet_size_fraction()
            if equity >= 0.85:
                frac = min(frac * 1.3, 1.0)

        # Apply value sizing multiplier (from exploit adjustments)
        frac = min(frac * self.value_mult, 1.5)  # cap at 150% pot (overbet territory)

        return GTOMath.pot_fraction_bet(frac, pot, min_bet, stack)

    def should_check_raise(
        self,
        equity: float,
        board: BoardTexture,
        is_ip: bool,
    ) -> bool:
        """Decide whether to check-raise when checked to and opponent bets."""
        if is_ip:
            return False  # Check-raise is an OOP move
        if equity >= 0.80:
            return random.random() < 0.5
        if equity >= 0.60 and board.is_wet:
            return random.random() < 0.35
        return False

    def should_call(
        self,
        equity: float,
        pot_odds: float,
        implied_odds_bonus: float = 0.05,
        spr: float = 5.0,
    ) -> bool:
        effective_equity = equity + (implied_odds_bonus if spr > 3 else 0)
        return effective_equity >= pot_odds

    def _raise_size(self, to_call: float, pot: float, stack: float) -> float:
        """Standard raise size when facing a bet: roughly 2.5-3x opponent's bet,
        but at least proportional to the pot."""
        # Raise to: call amount + ~75% of pot (total raise is well-sized vs pot)
        size = max(to_call * 2.5, to_call + pot * 0.75)
        return min(size, stack)

    def decide(
        self,
        equity: float,
        pot: float,
        to_call: float,
        stack: float,
        board: List[Card],
        is_ip: bool,
        street: str,
        facing_bet: bool,
        num_opponents: int,
        big_blind: float,
        opponent_fold_rate: float = 0.45,
        spr: float = 5.0,
    ) -> Tuple[str, float]:
        """Main postflop decision function.

        Returns (action, amount): action in 'fold', 'check', 'call', 'raise'
        amount is the total bet for raises (0 otherwise).
        """
        texture = BoardTexture(board)
        pot_odds = to_call / (pot + to_call) if to_call > 0 else 0.0

        if facing_bet:
            if to_call >= stack:
                # All-in situation
                if equity >= pot_odds or equity >= 0.35:
                    return ('call', to_call)
                return ('fold', 0.0)

            # IP value raise: strong hands raise for value instead of just calling
            # This was the key missing piece — IP had no raise option facing a bet
            if is_ip and equity >= 0.75 and to_call < stack * 0.8:
                raise_prob = 0.40 if equity >= 0.85 else 0.22
                raise_prob *= self.aggression
                if random.random() < raise_prob:
                    raise_size = self._raise_size(to_call, pot, stack)
                    return ('raise', raise_size)

            # OOP check-raise (pot-based sizing, not to_call*3)
            if not is_ip and self.should_check_raise(equity, texture, is_ip):
                raise_size = self._raise_size(to_call, pot, stack)
                return ('raise', raise_size)

            # Call or fold
            implied_bonus = 0.06 if (equity >= 0.25 and spr > 4) else 0.0
            if self.should_call(equity, pot_odds, implied_bonus, spr):
                return ('call', to_call)
            return ('fold', 0.0)

        else:
            # No bet facing: check or bet
            if self.should_cbet(equity, texture, is_ip, street, num_opponents, opponent_fold_rate):
                amount = self.bet_size(equity, pot, texture, stack, street, big_blind)
                return ('raise', amount)
            return ('check', 0.0)
