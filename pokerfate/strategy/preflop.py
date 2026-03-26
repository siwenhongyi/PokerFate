"""Preflop range definitions and decision logic.

Ranges are defined as sets of hand categories (strings):
  - "AA", "KK" ... pocket pairs
  - "AKs" ... suited
  - "AKo" ... offsuit
"""

from __future__ import annotations
import random
from typing import List, Set, Tuple
from pokerfate.core.card import Card, Rank


def _hand_category(hole_cards: List[Card]) -> str:
    """Convert 2 hole cards to a canonical category string like 'AKs', 'AKo', 'AA'."""
    c1, c2 = hole_cards
    r1, r2 = c1.rank.value, c2.rank.value
    if r1 < r2:
        r1, r2 = r2, r1
    rank_names = {14: 'A', 13: 'K', 12: 'Q', 11: 'J', 10: 'T',
                  9: '9', 8: '8', 7: '7', 6: '6', 5: '5',
                  4: '4', 3: '3', 2: '2'}
    if r1 == r2:
        return f"{rank_names[r1]}{rank_names[r2]}"
    suited = 's' if c1.suit == c2.suit else 'o'
    return f"{rank_names[r1]}{rank_names[r2]}{suited}"


def _expand_range(spec: str) -> Set[str]:
    """Expand range specs like 'AA', 'AKs', 'AKo', '77+', 'A5s-A2s'.

    Supported notations:
      'AA', 'AKs', 'AKo'  — exact
      '77+'               — pair 77 and above
      'ATs+'              — suited Ax from AT to AK
      'ATo+'              — offsuit Ax from ATo to AKo
    """
    ranks_order = ['2', '3', '4', '5', '6', '7', '8', '9', 'T', 'J', 'Q', 'K', 'A']
    rank_idx = {r: i for i, r in enumerate(ranks_order)}

    result: Set[str] = set()

    specs = [s.strip() for s in spec.split(',')]
    for s in specs:
        s = s.strip()
        if not s:
            continue

        if s.endswith('+'):
            base = s[:-1]
            if len(base) == 2 and base[0] == base[1]:
                # Pair+ e.g. 77+
                start_idx = rank_idx[base[0]]
                for i in range(start_idx, len(ranks_order)):
                    r = ranks_order[i]
                    result.add(f"{r}{r}")
            elif len(base) == 3:
                # e.g. ATs+ or ATo+
                r1, r2, suf = base[0], base[1], base[2]
                start_idx = rank_idx[r2]
                top_idx = rank_idx[r1] - 1
                for i in range(start_idx, top_idx):
                    r = ranks_order[i]
                    result.add(f"{r1}{r}{suf}")
            else:
                result.add(base)
        else:
            result.add(s)

    return result


# ---------------------------------------------------------------------------
# Position-based opening ranges (9-max, 100BB)
# ---------------------------------------------------------------------------

_UTG_RANGE = _expand_range(
    'AA, KK, QQ, JJ, TT, 99, 88, 77, '
    'AKs, AQs, AJs, ATs, A9s, '
    'KQs, KJs, KTs, '
    'QJs, QTs, JTs, '
    'AKo, AQo, AJo, KQo'
)

_UTG1_RANGE = _UTG_RANGE | _expand_range(
    '66, A8s, A7s, K9s, T9s, 98s'
)

_UTG2_RANGE = _UTG1_RANGE | _expand_range(
    '55, A6s, A5s, K8s, Q9s, J9s, T8s, 87s, 76s'
)

_HJ_RANGE = _UTG2_RANGE | _expand_range(
    '44, A4s, A3s, A2s, K7s, K6s, Q8s, 97s, 86s, 75s, 65s, 54s'
)

_CO_RANGE = _HJ_RANGE | _expand_range(
    '33, 22, K5s, K4s, K3s, K2s, Q7s, Q6s, Q5s, J8s, J7s, T7s, 96s, 85s, 74s, 64s, 53s, 43s, '
    'ATo, KJo, QJo, KTo, QTo, JTo'
)

_BTN_RANGE = _CO_RANGE | _expand_range(
    'K5o, K6o, K7o, K8o, Q8o, Q9o, J8o, J9o, T8o, T9o, 97o, 98o, 87o, 86o, 76o, 75o, 65o, '
    'A2o, A3o, A4o, A5o, A6o, A7o, A8o, A9o, '
    'Q4s, Q3s, Q2s, J6s, J5s, J4s, J3s, T6s, T5s, 95s'
)

_SB_RANGE = _CO_RANGE | _expand_range(
    'K9o, Q9o, J9o, T8o, 98o, 87o, 76o, 65o, '
    'A2o, A3o, A4o, A5o, A6o, A7o, A8o'
)

# BB defends vs SB open — wide defense range
_BB_VS_SB_DEFENSE = _BTN_RANGE | _expand_range(
    'K4o, K3o, K2o, Q7o, Q6o, Q5o, J7o, T7o, 96o, 85o, 74o, 63o, 52o, 42o, 32o'
)

_POSITION_RANGES = {
    'UTG':  _UTG_RANGE,
    'UTG+1': _UTG1_RANGE,
    'UTG+2': _UTG2_RANGE,
    'LJ':   _UTG2_RANGE,
    'HJ':   _HJ_RANGE,
    'CO':   _CO_RANGE,
    'BTN':  _BTN_RANGE,
    'SB':   _SB_RANGE,
    'BB':   _BTN_RANGE,   # BB uses wide defense
    'MP':   _HJ_RANGE,
}

# ---------------------------------------------------------------------------
# 3-Bet ranges
# ---------------------------------------------------------------------------

# Value 3-bet (always 3-bet for value)
_3BET_VALUE = _expand_range('AA, KK, QQ, JJ, AKs, AKo')

# 3-Bet semi-bluff (blockers + equity): A5s-A2s + some suited connectors
_3BET_BLUFF = _expand_range('A5s, A4s, A3s, A2s, KQs, T9s, 98s')

_3BET_RANGE = _3BET_VALUE | _3BET_BLUFF

# 4-Bet range
_4BET_VALUE = _expand_range('AA, KK, QQ, AKs, AKo')
_4BET_BLUFF = _expand_range('A5s, A4s')
_4BET_RANGE = _4BET_VALUE | _4BET_BLUFF


class PreflopStrategy:
    """Preflop decision engine."""

    def __init__(self, bluff_3bet_freq: float = 0.5):
        self.bluff_3bet_freq = bluff_3bet_freq  # how often to execute 3-bet bluffs

    def hand_category(self, hole_cards: List[Card]) -> str:
        return _hand_category(hole_cards)

    def in_open_range(self, hole_cards: List[Card], position: str) -> bool:
        cat = _hand_category(hole_cards)
        rng = _POSITION_RANGES.get(position, _UTG_RANGE)
        return cat in rng

    def should_3bet(self, hole_cards: List[Card], position: str, vs_position: str) -> bool:
        cat = _hand_category(hole_cards)
        if cat in _3BET_VALUE:
            return True
        if cat in _3BET_BLUFF:
            # Bluff 3-bet with some frequency
            return random.random() < self.bluff_3bet_freq
        return False

    def should_4bet(self, hole_cards: List[Card]) -> bool:
        cat = _hand_category(hole_cards)
        if cat in _4BET_VALUE:
            return True
        if cat in _4BET_BLUFF:
            return random.random() < 0.5
        return False

    def open_raise_size(self, position: str, big_blind: float) -> float:
        """Standard open raise sizing in BB."""
        if position in ('SB',):
            return big_blind * 3.0
        if position in ('BTN', 'CO'):
            return big_blind * 2.5
        return big_blind * 3.0

    def three_bet_size(self, open_raise: float, is_ip: bool, big_blind: float) -> float:
        """3-bet sizing."""
        multiplier = 3.0 if is_ip else 4.0
        return max(open_raise * multiplier, big_blind * 9)

    def decide(
        self,
        hole_cards: List[Card],
        position: str,
        facing_action: str,  # 'none', 'open', '3bet', '4bet'
        open_raise: float,
        is_ip: bool,
        big_blind: float,
        stack: float,
        pot: float,
    ) -> Tuple[str, float]:
        """Return (action, amount). action in: fold, call, raise."""
        cat = _hand_category(hole_cards)

        if facing_action == 'none':
            # We are first to act (or limped to us)
            if self.in_open_range(hole_cards, position):
                size = self.open_raise_size(position, big_blind)
                return ('raise', min(size, stack))
            return ('fold', 0.0)

        elif facing_action == 'open':
            if self.should_3bet(hole_cards, position, 'any'):
                size = self.three_bet_size(open_raise, is_ip, big_blind)
                return ('raise', min(size, stack))
            if self.in_open_range(hole_cards, position) or cat in _BB_VS_SB_DEFENSE:
                return ('call', min(open_raise, stack))
            return ('fold', 0.0)

        elif facing_action == '3bet':
            if self.should_4bet(hole_cards):
                # 4-bet to ~2.5x the 3-bet
                size = min(open_raise * 2.5, stack)
                return ('raise', size)
            # Call with premium hands
            if cat in _expand_range('QQ, JJ, TT, AKs, AKo, AQs, KQs'):
                return ('call', min(open_raise, stack))
            return ('fold', 0.0)

        elif facing_action == '4bet':
            if cat in _expand_range('AA, KK'):
                return ('raise', stack)  # 5-bet shove
            if cat in _expand_range('QQ, AKs, AKo'):
                return ('call', min(open_raise, stack))
            return ('fold', 0.0)

        return ('fold', 0.0)
