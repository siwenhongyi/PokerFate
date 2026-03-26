"""Postflop strategy: board texture analysis, c-bet, bet sizing decisions."""

from __future__ import annotations
import random
from typing import List, Tuple
from pokerfate.core.card import Card, Rank, Suit
from pokerfate.strategy.gto import GTOMath


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
        """Decide whether to make a continuation bet.

        Improvements based on Pluribus/Libratus research:
        - River: delegate to _should_river_bet (no semi-bluffs — no draws to realize)
        - Value threshold lowered 0.70 → 0.65 (capture thin value hands like AQ/top-pair)
        - Multiway (3+ opponents): semi-bluff requires equity >= 0.45 floor
          (Pluribus: fold equity drops sharply in multi-way pots)
        """
        # ── River: separate logic (no semi-bluffs, pure value or fold-equity bluff) ──
        if street == 'river':
            return self._should_river_bet(equity, is_ip, num_opponents, opponent_fold_rate)

        # Monster hand: mostly bet, but check 20% to protect checking range
        if equity >= 0.90:
            return random.random() < (0.80 * self.aggression)

        # Strong value hand: lowered threshold 0.65 → 0.60 to capture top-pair type hands.
        # At 60%+ equity we almost certainly have the best hand or a strong draw.
        if equity >= 0.60:
            if num_opponents <= 1:
                return True
            # Multiway: bet frequency scales with board texture.
            # Dry board → higher protection urgency (no draws to give free cards to).
            # Wet board → slightly lower but still aggressive.
            base = 0.90 if board.is_dry else 0.80
            freq = max(0.50, base - 0.10 * (num_opponents - 1))
            return random.random() < (freq * self.aggression)

        # Very weak hand (no equity, no fold equity): give up
        if equity < 0.20 and opponent_fold_rate < 0.40:
            return False

        # Multiway semi-bluff floor: need meaningful equity to barrel into multiple opponents
        # (Pluribus insight: EV of bluffing drops sharply as player count increases)
        if num_opponents >= 2 and equity < 0.45:
            return False

        # Semi-bluff zone: bet with fold equity
        if 0.30 <= equity <= 0.60:
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

    def _should_river_bet(
        self,
        equity: float,
        is_ip: bool,
        num_opponents: int,
        opponent_fold_rate: float,
    ) -> bool:
        """River betting: value or pure fold-equity bluff only.

        On the river there are no draws left to realize — 'semi-bluff' is
        a contradiction in terms. This mirrors the GTO river betting principle
        from The Mathematics of Poker (Chen & Ankenman): optimal river strategy
        is polarized (strong value hands + pure bluffs), not merged.

        Value threshold:
          equity >= 0.70 → always bet
          equity >= 0.60 → bet most of the time (thin value)
          equity >= 0.50 → occasional merge bet in HU, skip multiway

        Bluff threshold:
          Only when equity < 0.35 (no showdown value), HU, and fold equity
          exceeds the GTO break-even fold rate for a ~66% pot bluff (~40%).
        """
        # Strong value
        if equity >= 0.70:
            return True
        if equity >= 0.60:
            return random.random() < (0.80 * self.aggression)
        # Thin value / merge — only heads-up
        if equity >= 0.50:
            if num_opponents > 1:
                return False
            return random.random() < (0.45 * self.aggression)

        # Pure bluff: need genuine fold equity
        # GTO break-even for 66% pot bluff ≈ 0.40 fold rate
        if equity < 0.35 and num_opponents == 1:
            if opponent_fold_rate > 0.40:
                bluff_freq = min(self.aggression * 0.28, 0.35)
                return random.random() < bluff_freq

        return False

    def bet_size(
        self,
        equity: float,
        pot: float,
        board: BoardTexture,
        stack: float,
        street: str,
        big_blind: float,
    ) -> float:
        """Determine bet size using action abstraction.

        Inspired by OpenSpiel (DeepMind) and Libratus/Pluribus:
        - Use a discrete menu of pot fractions per street instead of a
          single deterministic size.
        - Mix between sizes within each hand-strength tier — this prevents
          opponents from reverse-engineering hand strength from bet size alone.
        - Bluffs use the same size distribution as thin value bets
          (size-based tells are a major exploitable leak in rule-based bots).
        - River adds a polarized overbet option for near-nut hands.

        Typical action abstractions used in academic poker AI:
          Flop:  [1/3, 1/2, 3/4] pot
          Turn:  [1/2, 2/3, 3/4] pot
          River: [1/2, 3/4, 1x, 5/4] pot (more polarized)
        """
        min_bet = big_blind

        if street == 'river':
            if equity >= 0.85:
                # Near-nut: polarized — mix pot-size and overbet
                frac = random.choices([0.75, 1.0, 1.25], weights=[0.35, 0.45, 0.20])[0]
            elif equity >= 0.65:
                # Strong value: 3/4 or full pot
                frac = random.choices([0.66, 0.75, 1.0], weights=[0.30, 0.45, 0.25])[0]
            elif equity >= 0.50:
                # Thin value: 1/2 pot (low commitment, still extracting)
                frac = 0.50
            else:
                # Bluff: same size distribution as thin value (no sizing tell)
                frac = random.choices([0.50, 0.66], weights=[0.60, 0.40])[0]

        elif street == 'turn':
            if equity >= 0.75:
                # Strong: mix 2/3 and 3/4 — build pot without committing all
                frac = random.choices([0.66, 0.75], weights=[0.45, 0.55])[0]
            elif equity >= 0.50:
                # Protection / semi-bluff: 1/2 to 2/3
                frac = random.choices([0.50, 0.66], weights=[0.55, 0.45])[0]
            else:
                # Thin semi-bluff: smaller to risk less
                frac = 0.50

        else:
            # Flop — board texture drives sizing more than equity
            if equity >= 0.80:
                # Strong flop hand: larger to build pot fast
                frac = random.choices([0.66, 0.75], weights=[0.50, 0.50])[0]
            elif equity >= 0.55:
                # Standard value / semi-bluff: board-texture driven
                base = board.recommended_cbet_size_fraction()
                # Mix a size above and below the recommended to obscure range
                frac = random.choices(
                    [max(0.25, base - 0.15), base, min(1.0, base + 0.20)],
                    weights=[0.25, 0.50, 0.25]
                )[0]
            else:
                # Weak semi-bluff: small size (cheap to barrel, low commitment)
                frac = random.choices([0.33, 0.50], weights=[0.55, 0.45])[0]

        # Apply value sizing multiplier (exploit adjustment vs calling stations)
        frac = min(frac * self.value_mult, 1.5)

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
