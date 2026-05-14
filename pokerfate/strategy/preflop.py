"""Preflop range definitions and decision logic.

Ranges are defined as sets of hand categories (strings):
  - "AA", "KK" ... pocket pairs
  - "AKs" ... suited
  - "AKo" ... offsuit
"""

from __future__ import annotations
import os
import random
from typing import List, Optional, Set, Tuple
from pokerfate.core.card import Card
from pokerfate.core.position import (
    normalize_position as _normalize_position,
)
from pokerfate.data import lookup_gto

# _normalize_position is re-exported for backward-compat with tests and
# external imports that existed before the core.position module was introduced.


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
                top_idx = rank_idx[r1]
                for i in range(start_idx, top_idx):
                    r = ranks_order[i]
                    result.add(f"{r1}{r}{suf}")
            else:
                result.add(base)
        else:
            result.add(s)

    return result


# ---------------------------------------------------------------------------
# Position-based opening ranges (6-max cash, 100BB)  — V2
# GTO solver 共识对齐：UTG ~15–18%，HJ ~20–23%，CO ~25–30%，BTN ~40–48%。
# 详见 docs/PREFLOP_OPEN_RANGE_V2.md
# ---------------------------------------------------------------------------

_UTG_RANGE = _expand_range(
    '55+, '
    'AKs, AQs, AJs, ATs, A9s, A8s, A7s, A6s, A5s, A4s, A3s, A2s, '
    'KQs, KJs, KTs, K9s, '
    'QJs, QTs, Q9s, '
    'JTs, J9s, '
    'T9s, T8s, 98s, 87s, '
    'AKo, AQo, AJo, ATo, KQo, KJo'
)

_UTG1_RANGE = _UTG_RANGE | _expand_range(
    'K8s, 76s'
)

_UTG2_RANGE = _UTG1_RANGE

_HJ_RANGE = _UTG2_RANGE | _expand_range(
    '44, 33, 22, '
    'K7s, K6s, Q8s, 97s, 86s, 75s, 65s, 54s, '
    'QJo'
)

_CO_RANGE = _HJ_RANGE | _expand_range(
    'K5s, K4s, K3s, K2s, Q7s, Q6s, Q5s, J8s, J7s, T7s, 96s, 85s, 74s, 64s, 53s, 43s, '
    'KTo, QTo, JTo'
)

_BTN_RANGE = _CO_RANGE | _expand_range(
    'K8o, K9o, Q8o, Q9o, J8o, J9o, T8o, T9o, '
    'A5o, A6o, A7o, A8o, A9o, '
    'J6s, J5s, T6s'
)

_SB_RANGE = _CO_RANGE | _expand_range(
    'K9o, Q9o, J9o, T9o, T8o, 98o, 87o, 76o, 65o, '
    'A2o, A3o, A4o, A5o, A6o, A7o, A8o, A9o'
)

# SB heads-up steal vs BB only: ~63% of hands
_SB_STEAL_VS_BB = _BTN_RANGE | _expand_range(
    'K2o, K3o, K4o, K5o, K6o, K7o, '
    'Q5o, Q6o, Q7o, '
    'J6o, J7o, '
    'T6o, T7o, '
    '96o, 97o, 98o, 87o, 86o, 76o, '
    'Q2s, Q3s, Q4s, J2s, J3s, J4s, T2s, T3s, T4s, T5s, 95s'
)

# 短手位置映射：n人桌时，早位按等效位置放宽范围
# 5人桌 UTG ≈ 6人桌 HJ；5人桌 UTG+1 ≈ 6人桌 CO
# 4人桌 UTG ≈ 6人桌 CO
_SHORT_HAND_POSITION: dict = {
    5: {'UTG': 'HJ',  'UTG+1': 'CO'},
    4: {'UTG': 'CO',  'UTG+1': 'BTN'},
    3: {'UTG': 'BTN', 'UTG+1': 'BTN'},
}

# BB defends vs SB open — widest (BB closes IP, can realise very wide)
_BB_VS_SB_DEFENSE = _BTN_RANGE | _expand_range(
    'K4o, K3o, K2o, K7o, Q7o, Q6o, Q5o, J7o, T7o, '
    '96o, 97o, 98o, 87o, 86o, 76o, 85o, 74o, 63o, 52o, 42o, 32o, '
    'Q2s, Q3s, Q4s, J3s, J4s, T5s, 95s'
)


# ---------------------------------------------------------------------------
# BB defense vs non-SB open, keyed by opener position.
# Issue I (gameplay analysis): old code only had _BB_VS_SB_DEFENSE and
# fell through to _BTN_RANGE (~48%) for UTG/MP/CO/BTN opens, causing BB
# to over-fold by 6+ hands where equity ≥ pot-odds.
#
# Sources: GTO Wizard 6-max BB-vs-RFI defend ranges; Pekarstas "Modern
# Poker Theory" ch.8 table 8.4. MDF vs 3× open = 0.7; IP advantage of
# opener means real defend is ~0.62-0.85 (tighter vs UTG, widest vs BTN).
# ---------------------------------------------------------------------------

_BB_VS_UTG_DEFENSE = _expand_range(
    # ~62% range. UTG opens tight (~16%), BB defends the hands that play
    # well vs premiums: pairs (for set-mining implied odds), big suited
    # (for top pair/flushes), suited connectors, broadway off-suit.
    '22+, '
    'A2s+, '
    'K9s+, K7s, '
    'Q9s+, Q7s, '
    'J9s+, J8s, '
    'T9s, T8s, '
    '98s, 97s, 87s, 76s, 65s, 54s, '
    'ATo+, KJo+, QJo'
)

_BB_VS_MP_DEFENSE = _BB_VS_UTG_DEFENSE | _expand_range(
    # ~72% range. Add more suited broadway + KTo.
    'K6s, K5s, '
    'Q6s, Q5s, '
    'J7s, '
    'T7s, '
    '86s, 75s, 64s, 53s, '
    'A9o, KTo, QTo, JTo'
)

_BB_VS_CO_DEFENSE = _BB_VS_MP_DEFENSE | _expand_range(
    # ~78% range. Most suited + broad offsuit.
    'K4s, K3s, K2s, '
    'Q4s, Q3s, Q2s, '
    'J6s, J5s, '
    'T6s, T5s, '
    '96s, 85s, 74s, 63s, 43s, '
    'A8o, A7o, A6o, A5o, A4o, A3o, A2o, K9o, Q9o, J9o, T9o, 98o'
)

_BB_VS_BTN_DEFENSE = _BB_VS_CO_DEFENSE | _expand_range(
    # ~87% range (near-MDF). BTN opens widest → BB defends widest.
    'J4s, J3s, J2s, '
    'T4s, T3s, T2s, '
    '95s, 84s, 73s, 52s, 42s, 32s, '
    'K8o, K7o, K6o, K5o, K4o, K3o, K2o, '
    'Q8o, Q7o, Q6o, Q5o, '
    'J8o, J7o, J6o, '
    'T8o, T7o, T6o, '
    '97o, 96o, 87o, 86o, 76o, 75o, 65o, 54o'
)

# Lookup: opener position (6-max canonical) → BB defend range.
_BB_VS_OPEN_DEFENSE = {
    'UTG': _BB_VS_UTG_DEFENSE,
    'MP':  _BB_VS_MP_DEFENSE,
    'CO':  _BB_VS_CO_DEFENSE,
    'BTN': _BB_VS_BTN_DEFENSE,
    'SB':  _BB_VS_SB_DEFENSE,
}

# BB iso-raise range when facing limpers (no one raised, BB has option to raise).
# Strong enough to thin the field and play for value OOP.
# With more limpers, only tighten slightly — pot odds improve for everyone.
_BB_ISO_RAISE = _expand_range(
    'AA, KK, QQ, JJ, TT, 99, 88, '
    'AKs, AQs, AJs, ATs, '
    'AKo, AQo, AJo, '
    'KQs, KJs'
)

# Conservative fallback for ISO spots when no chart exists for the position.
# Chart data is authoritative when present; this fallback only covers missing
# ISO charts and avoids weak offsuit connectors / weak offsuit Ax.
_ISO_FALLBACK_RAISE = _expand_range(
    '66+, '
    'AKs, AQs, AJs, ATs, A9s, A8s, A7s, A6s, A5s, A4s, A3s, A2s, '
    'AKo, AQo, AJo, '
    'KQs, KJs, KTs, KQo, '
    'QJs, QTs, '
    'JTs, T9s, 98s, 87s, 76s'
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

# Value 3-bet (always 3-bet for value).
# 6max 100bb solver baseline: TT+, AKs/o, AQs/o, AJs, KQs are value or
# value-mix across ≥3 opener positions. Static table over-3bets TT/AJs/AQo
# slightly vs UTG opens — acceptable trade for covering wide-opener spots.
_3BET_VALUE = _expand_range('TT+, AKs, AKo, AQs, AQo, AJs, KQs')

# 3-Bet semi-bluff pool (blockers + suited playability). Actual fire rate
# is pool × _BLUFF_3BET_FREQ_BY_VS_POS[opener] — wider pool here lets the
# per-opener freq scale match solver totals (vs UTG ~6%, vs BTN ~9%).
_3BET_BLUFF = _expand_range(
    'A5s, A4s, A3s, A2s, A9s, A8s, '
    'KJs, KTs, K9s, '
    'QJs, QTs, Q9s, '
    'JTs, J9s, '
    'T9s, 98s, 87s, 76s, 65s'
)

_3BET_RANGE = _3BET_VALUE | _3BET_BLUFF

# 4-Bet range
# Value:Bluff 目标 ≈ 3:1（主流 GTO 6max 100bb）。
# 价值 46 combos (AA=6,KK=6,QQ=6,JJ=6,TT=6,AKs=4,AKo=12) → 诈唬目标 ~14-16 combos。
# 诈唬按 A-blocker/K-blocker 优先级分频：
#   A5s/A4s 100%  (wheel + nut-flush + A-blocker)
#   A3s/A2s 50%   (同理但频率减半)
#   KTs     50%   (K-blocker, 防 KK)
_4BET_VALUE = _expand_range('AA, KK, QQ, JJ, TT, AKs, AKo')
_4BET_BLUFF_FREQ = {
    'A5s': 1.00,
    'A4s': 1.00,
    'A3s': 0.50,
    'A2s': 0.50,
    'KTs': 0.50,
}
_4BET_BLUFF = set(_4BET_BLUFF_FREQ.keys())
_4BET_RANGE = _4BET_VALUE | _4BET_BLUFF
_3BET_SQUEEZE_DOWNGRADE = _expand_range('TT, AJs, AQo, KQs')
_4BET_MULTIWAY_DOWNGRADE = _expand_range('JJ, TT, AKo')
_VS_4BET_FALLBACK_JAM = _expand_range('AA, KK')
_VS_4BET_FALLBACK_CALL = _expand_range('QQ, AKs, AKo')
_VS_4BET_RANGE_EDGE_FALLBACK = _expand_range('JJ, TT, AQs')
_VS_4BET_CALL_EQUITY_MIN = {
    '99': 0.50,
    'JJ': 0.55,
    'TT': 0.55,
    'AQs': 0.52,
}
_VS_4BET_CHART_CALL_MIN_EDGE = 0.08
_VS_4BET_CHART_MIX_MIN_EDGE = 0.13
_VS_4BET_RANGE_EDGE_MIN = 0.18
_VS_4BET_STICKY_EDGE_PENALTY = 0.03
_VS_4BET_CALL_MAX_POT_ODDS = 0.40
_VS_4BET_CALL_MAX_STACK_COMMIT = 0.45
_VS_4BET_CALL_MIN_STACK_BB = 70.0
_VS_4BET_CHART_ALLIN_MAX_STACK_BB = 150.0
_VS_4BET_EDGE_ADJUST_MIN = -0.03
_VS_4BET_EDGE_ADJUST_MAX = 0.04

# Chart-backed overlays. These do not remove any baseline action; they only
# rescue good chart spots that the static baseline would otherwise fold.
_IP_SMALL_OPEN_3BET_EXPAND = _expand_range('KQo, AJo, KJs, QJs')
_IP_SMALL_OPEN_CALL_EXPAND = _expand_range('KTs, QTs, JTs')
_IP_SMALL_OPEN_SPOTS = {
    ('BTN', 'CO'),
    ('BTN', 'MP'),
    ('CO', 'MP'),
}
_IP_SMALL_OPEN_MAX_BB = 2.5
_IP_SMALL_OPEN_MIN_STACK_BB = 50.0
_IP_SMALL_OPEN_CALL_MIN_STACK_BB = 70.0
_IP_SMALL_OPEN_STICKY_DENSITY = 0.45

_CHART_3BET_CALL_DEEP_EXPAND = _expand_range(
    '99, 88, 77, ATs, KJs, KTs, QJs, QTs, JTs, T9s'
)
_CHART_3BET_CALL_MID_EXPAND = _expand_range(
    '99, 88, ATs, KJs, QJs, JTs'
)
_CHART_3BET_CALL_DEEP_STACK_BB = 70.0
_CHART_3BET_CALL_MID_STACK_BB = 50.0
_CHART_3BET_CALL_MAX_STACK_COMMIT = 0.25
_CHART_3BET_CALL_MAX_POT_ODDS = 0.42


# ---------------------------------------------------------------------------
# 3-bet call range by hero-open position (hero open → vs any 3-bet).
# Sources: GTO Wizard, PioSolver, Acevedo "Modern Poker Theory" (2019),
# Upswing Poker, cross-validated against Greenline data.
# ---------------------------------------------------------------------------
_3BET_CALL_BY_POS = {
    # UTG opens wide-premium; faces 3bet mostly from late positions
    'UTG': _expand_range('JJ, TT, AKo, AQs, AJs, KQs'),

    # MP opens slightly wider; includes suited broadway + ATs/88/QJs for MDF
    'MP':  _expand_range('JJ, TT, 99, 88, AKo, AQs, AQo, AJs, ATs, KQs, KJs, QJs'),

    # CO: removed 66 (OOP 3bet pot implied odds insufficient), kept 77
    'CO':  _expand_range('JJ, TT, 99, 88, 77, AKo, AQs, AQo, AJs, ATs, KQs'),

    # BTN: widest defend (IP vs blinds, most common 3bet scenario)
    'BTN': _expand_range('JJ, TT, 99, 88, 77, AKo, AQs, AQo, AJs, ATs, A9s, '
                         'KQs, KQo, KJs, KTs, QJs, JTs, T9s, 98s, 87s'),

    # SB vs BB 3bet: drop low SC, keep broadway SC (OOP flush/straight potential)
    'SB':  _expand_range('JJ, TT, 99, 88, 77, AKo, AQs, AQo, AJs, ATs, '
                         'KQs, KQo, KJs, KTs, QJs, QTs, JTs, T9s'),

    # BB iso-raise then gets 3bet (review P1 fix — previously missing).
    # BB defend range vs 3bet is noticeably wider than other positions
    # because BB already invested 1 bb and gets closing action IP post-flop.
    'BB':  _expand_range('JJ, TT, 99, 88, 77, AKo, AQs, AQo, AJs, ATs, A9s, '
                         'KQs, KQo, KJs, KTs, QJs, QTs, JTs, T9s, 98s, 87s'),
}
# Fallback for unknown / unmatched hero position
_3BET_CALL_DEFAULT = _expand_range('JJ, TT, 99, AKo, AQs, AQo, AJs, KQs')


# ---------------------------------------------------------------------------
# 3bet / 4bet sizing matrices (6-max NL 100bb, solver-calibrated).
# Keys: (open_pos, three_bet_pos) — both normalized to 6-max canonical.
# Positions not listed fall back to IP/OOP defaults.
# ---------------------------------------------------------------------------
_3BET_SIZE_MULT = {
    # OOP 3bet (3bettor in SB/BB): larger to offset position disadvantage
    ('UTG', 'SB'): 3.5, ('UTG', 'BB'): 3.6,
    ('MP',  'SB'): 3.6, ('MP',  'BB'): 3.8,
    ('CO',  'SB'): 4.0, ('CO',  'BB'): 4.0,
    ('BTN', 'SB'): 4.4, ('BTN', 'BB'): 4.4,
    ('SB',  'BB'): 4.0,
    # IP 3bet: smaller, opener range narrower anyway
    ('UTG', 'MP'):  3.2, ('UTG', 'CO'):  3.0, ('UTG', 'BTN'): 3.0,
    ('MP',  'CO'):  3.0, ('MP',  'BTN'): 3.0,
    ('CO',  'BTN'): 3.2,
}
_3BET_SIZE_FALLBACK_IP = 3.0
_3BET_SIZE_FALLBACK_OOP = 4.0

# 4bet sizing (multiplier × 3bet_size). Key = (hero_open_pos, villain_3bet_pos).
# Hero IP 4bet: smaller "click" — invite villain flat or 5bet bluff.
# Hero OOP 4bet: larger — need fold equity given OOP disadvantage.
_4BET_SIZE_MULT = {
    # Hero opened late, villain 3bet blinds → hero IP 4bet
    ('BTN', 'SB'): 2.15, ('BTN', 'BB'): 2.15,
    ('CO',  'SB'): 2.15, ('CO',  'BB'): 2.15,
    ('MP',  'SB'): 2.15, ('MP',  'BB'): 2.15,
    ('UTG', 'SB'): 2.15, ('UTG', 'BB'): 2.15,
    # Hero opened early/mid, villain 3bet late → hero OOP 4bet
    ('UTG', 'MP'): 2.45, ('UTG', 'CO'): 2.45, ('UTG', 'BTN'): 2.45,
    ('MP',  'CO'): 2.45, ('MP',  'BTN'): 2.45,
    ('CO',  'BTN'): 2.45,
    # SB-opens vs BB 3bet (rare OOP 4bet)
    ('SB',  'BB'):  2.45,
}
_4BET_SIZE_FALLBACK_IP = 2.15
_4BET_SIZE_FALLBACK_OOP = 2.45

# Isolation raise sizing: standard RFI plus 1bb per limper; blinds add an
# OOP premium because limpers realise equity too cheaply when we go small.
_ISO_PER_LIMPER_BB = 1.0
_ISO_OOP_BONUS_BB = 1.0

# Low-cost limp-behind / blind-complete for speculative hands. This is NOT
# open-limp and never applies after a raise. It exists for loose multiway
# tables where paying ~1bb with deep stacks has set-mining / draw implied odds.
_LIMP_BEHIND_ENABLED = os.environ.get('PF_LIMP_BEHIND_ENABLED', '1') != '0'
_LIMP_BEHIND_MAX_CALL_BB = float(os.environ.get('PF_LIMP_BEHIND_MAX_CALL_BB', '1.25'))
_LIMP_BEHIND_MIN_STACK_BB = float(os.environ.get('PF_LIMP_BEHIND_MIN_STACK_BB', '60.0'))
_LIMP_BEHIND_MIN_IMPLIED = float(os.environ.get('PF_LIMP_BEHIND_MIN_IMPLIED', '25.0'))
_LIMP_BEHIND_MIN_LIMPERS = int(os.environ.get('PF_LIMP_BEHIND_MIN_LIMPERS', '2'))
_LIMP_BEHIND_STICKY_DENSITY = float(os.environ.get('PF_LIMP_BEHIND_STICKY_DENSITY', '0.35'))
_LIMP_BEHIND_LOOSE_LIMPERS = int(os.environ.get('PF_LIMP_BEHIND_LOOSE_LIMPERS', '3'))
_LIMP_BEHIND_REPLACE_ISO = os.environ.get('PF_LIMP_BEHIND_REPLACE_ISO', '1') != '0'
_LIMP_BEHIND_SMALL_PAIRS = _expand_range('22, 33, 44, 55, 66')
_LIMP_BEHIND_SUITED_CONNECTORS = _expand_range('54s, 65s, 76s, 87s, 98s, T9s, JTs')
_LIMP_BEHIND_SUITED_ONE_GAPPERS = _expand_range('64s, 75s, 86s, 97s, T8s, J9s, QTs')
_LIMP_BEHIND_WHEEL_AXS = _expand_range('A2s, A3s, A4s, A5s')

# Bluff 3bet frequency by villain (opener) position — applied to _3BET_BLUFF.
# Tighter open (UTG) → fewer 3bet bluffs; wider open (SB/BTN) → more.
_BLUFF_3BET_FREQ_BY_VS_POS = {
    'UTG': 0.20,
    'MP':  0.35,
    'CO':  0.55,
    'BTN': 0.65,
    'SB':  0.70,
}

_ACHIEVEMENT_ENTRY_BB = 1000.0
_ACHIEVEMENT_ENTRY_MAX_CALL_BB = 4.0


class PreflopStrategy:
    """Preflop decision engine."""

    def __init__(self, bluff_3bet_freq: float = 0.5,
                 rng: Optional[random.Random] = None):
        self.bluff_3bet_freq = bluff_3bet_freq  # how often to execute 3-bet bluffs
        # Use an instance RNG so preflop decisions are reproducible alongside
        # the v3 engine (doc 03 §10).
        self._rng: random.Random = rng or random.Random()
        self.last_expand_reason: str = ''

    def in_open_range(self, hole_cards: List[Card], position: str,
                      num_players: int = 6) -> bool:
        cat = _hand_category(hole_cards)
        eff_pos = _SHORT_HAND_POSITION.get(num_players, {}).get(position, position)
        rng = _POSITION_RANGES.get(eff_pos, _UTG_RANGE)
        return cat in rng

    def should_3bet(
        self,
        hole_cards: List[Card],
        position: str,
        vs_position: str,
        squeeze_callers: int = 0,
        sticky_density: float = 0.0,
    ) -> bool:
        cat = _hand_category(hole_cards)
        if cat in _3BET_VALUE:
            if squeeze_callers > 0 and cat in _3BET_SQUEEZE_DOWNGRADE:
                return False
            return True
        if cat in _3BET_BLUFF:
            # Position-aware bluff freq: tighter opener → fewer bluff 3bets.
            vs_norm = _normalize_position(vs_position)
            freq = _BLUFF_3BET_FREQ_BY_VS_POS.get(vs_norm, self.bluff_3bet_freq)
            if squeeze_callers > 0:
                freq *= 0.35
            if sticky_density >= 0.7:
                return False
            freq *= max(0.0, 1.0 - sticky_density * 1.5)
            return self._rng.random() < freq
        return False

    @staticmethod
    def _chart_has_action(action, wanted: str) -> bool:
        if isinstance(action, list):
            return wanted in action
        return action == wanted

    @staticmethod
    def _chart_action_is_mixed(action) -> bool:
        return isinstance(action, list) and 'fold' in action

    @staticmethod
    def _primary_chart_action(refs: dict) -> tuple[object, str]:
        greenline = refs.get('greenline')
        if greenline is not None:
            return greenline, 'greenline'
        pekarstas = refs.get('pekarstas')
        if pekarstas is not None:
            return pekarstas, 'pekarstas'
        return None, ''

    def _ip_small_open_expand_action(
        self,
        cat: str,
        position: str,
        villain_position: str,
        is_ip: bool,
        open_raise: float,
        big_blind: float,
        stack_bb: float,
        sticky_density: float,
        squeeze_callers: int,
    ) -> str:
        hero_norm = _normalize_position(position)
        villain_norm = _normalize_position(villain_position)
        if not is_ip or (hero_norm, villain_norm) not in _IP_SMALL_OPEN_SPOTS:
            return ''
        if squeeze_callers > 0 or stack_bb < _IP_SMALL_OPEN_MIN_STACK_BB:
            return ''
        open_bb = open_raise / big_blind if big_blind > 0 else 99.0
        good_price_or_table = (
            open_bb <= _IP_SMALL_OPEN_MAX_BB
            or sticky_density >= _IP_SMALL_OPEN_STICKY_DENSITY
        )
        if not good_price_or_table:
            return ''

        chart_key = f"{hero_norm}-vs-open-{villain_norm}"
        refs = lookup_gto(chart_key, cat)
        chart_raises = any(
            self._chart_has_action(action, 'raise')
            for action in refs.values()
        )
        chart_plays = chart_raises or any(
            self._chart_has_action(action, 'call')
            for action in refs.values()
        )
        if chart_raises and cat in _IP_SMALL_OPEN_3BET_EXPAND:
            self.last_expand_reason = (
                f"chart_expand:ip_3bet_small_open {chart_key} {cat}"
            )
            return 'raise'
        if (
            chart_plays
            and stack_bb >= _IP_SMALL_OPEN_CALL_MIN_STACK_BB
            and cat in _IP_SMALL_OPEN_CALL_EXPAND
        ):
            self.last_expand_reason = (
                f"chart_expand:ip_call_small_open {chart_key} {cat}"
            )
            return 'call'
        return ''

    def _chart_expand_3bet_call_allowed(
        self,
        cat: str,
        position: str,
        villain_position: str,
        open_raise: float,
        big_blind: float,
        stack: float,
        pot: float,
        to_call: float,
        stack_bb: float,
    ) -> bool:
        hero_norm = _normalize_position(position)
        villain_norm = _normalize_position(villain_position)
        if not hero_norm or not villain_norm:
            return False
        if hero_norm not in {'UTG', 'MP', 'CO'}:
            return False
        if stack_bb >= _CHART_3BET_CALL_DEEP_STACK_BB:
            expand = _CHART_3BET_CALL_DEEP_EXPAND
        elif stack_bb >= _CHART_3BET_CALL_MID_STACK_BB:
            expand = _CHART_3BET_CALL_MID_EXPAND
        else:
            return False
        if cat not in expand:
            return False

        call_amt = min(to_call or open_raise, stack)
        if call_amt <= 0 or call_amt >= stack:
            return False
        if stack > 0 and call_amt / stack > _CHART_3BET_CALL_MAX_STACK_COMMIT:
            return False
        pot_odds = call_amt / (pot + call_amt) if (pot + call_amt) > 0 else 1.0
        if pot_odds > _CHART_3BET_CALL_MAX_POT_ODDS:
            return False

        chart_key = f"{hero_norm}-vs-3bet-{villain_norm}"
        refs = lookup_gto(chart_key, cat)
        if not any(self._chart_has_action(action, 'call') for action in refs.values()):
            return False
        self.last_expand_reason = f"chart_expand:deep_3bet_defend {chart_key} {cat}"
        return True

    def _conditional_4bet_call_allowed(
        self,
        cat: str,
        stack: float,
        pot: float,
        to_call: float,
        open_raise: float,
        equity: float,
        stack_bb: float,
        cold_callers: int,
        sticky_density: float,
        edge_adjust: float = 0.0,
        chart_defends: bool = False,
        chart_mixed: bool = False,
        chart_source: str = 'range_edge',
    ) -> bool:
        if cold_callers > 0 or stack_bb < _VS_4BET_CALL_MIN_STACK_BB:
            return False

        call_amt = min(to_call or open_raise, stack)
        if call_amt <= 0 or call_amt >= stack:
            return False
        if stack > 0 and call_amt / stack > _VS_4BET_CALL_MAX_STACK_COMMIT:
            return False

        pot_odds = call_amt / (pot + call_amt) if (pot + call_amt) > 0 else 1.0
        if pot_odds > _VS_4BET_CALL_MAX_POT_ODDS:
            return False

        edge = equity - pot_odds
        edge_penalty = (
            _VS_4BET_STICKY_EDGE_PENALTY if sticky_density >= 0.45 else 0.0
        )
        if chart_defends:
            min_edge = (
                _VS_4BET_CHART_MIX_MIN_EDGE
                if chart_mixed else _VS_4BET_CHART_CALL_MIN_EDGE
            ) + edge_penalty
        elif cat in _VS_4BET_RANGE_EDGE_FALLBACK:
            min_edge = _VS_4BET_RANGE_EDGE_MIN + edge_penalty
        else:
            return False
        edge_adjust = max(
            _VS_4BET_EDGE_ADJUST_MIN,
            min(_VS_4BET_EDGE_ADJUST_MAX, edge_adjust),
        )
        min_edge = max(0.0, min_edge + edge_adjust)

        equity_min = _VS_4BET_CALL_EQUITY_MIN.get(cat, pot_odds + min_edge)
        if equity < equity_min or edge < min_edge:
            return False

        mode = 'mix' if chart_mixed else ('chart' if chart_defends else 'edge')
        self.last_expand_reason = (
            f"chart_expand:4bet_defend {mode} {chart_source} {cat} "
            f"eq={equity:.0%} po={pot_odds:.0%} edge={edge:.0%}/{min_edge:.0%}"
            f" adj={edge_adjust:+.0%}"
        )
        return True

    def _chart_4bet_defense_action(
        self,
        cat: str,
        position: str,
        villain_position: str,
        stack: float,
        pot: float,
        to_call: float,
        open_raise: float,
        equity: float,
        stack_bb: float,
        cold_callers: int,
        sticky_density: float,
        edge_adjust: float,
    ) -> str:
        hero_norm = _normalize_position(position)
        villain_norm = _normalize_position(villain_position)
        chart_key = f"{hero_norm}-vs-4bet-{villain_norm}" if hero_norm and villain_norm else ''
        if not chart_key:
            return ''
        refs = lookup_gto(chart_key, cat)
        primary, source = self._primary_chart_action(refs)
        if primary is None:
            return ''
        if self._chart_has_action(primary, 'allin'):
            if stack_bb > _VS_4BET_CHART_ALLIN_MAX_STACK_BB and cat not in _VS_4BET_FALLBACK_JAM:
                return ''
            self.last_expand_reason = (
                f"chart_expand:4bet_allin {source} {chart_key} {cat}"
            )
            return 'raise'
        if self._chart_has_action(primary, 'call'):
            allowed = self._conditional_4bet_call_allowed(
                cat, stack, pot, to_call, open_raise, equity, stack_bb,
                cold_callers, sticky_density, edge_adjust,
                chart_defends=True,
                chart_mixed=self._chart_action_is_mixed(primary),
                chart_source=f"{source} {chart_key}",
            )
            return 'call' if allowed else 'fold'
        return 'fold'

    def should_4bet(self, hole_cards: List[Card],
                    sticky_density: float = 0.0,
                    cold_callers: int = 0) -> bool:
        """4-bet 决策。

        2026-04-25 Fix 6.3: sticky_density ∈ [0, 1] 是桌上 `_value_lean >= 1.2`
        对手占比（连续指标，不依赖标签）。density 越高 → 4bet pot 多路调用
        可能性越大 → SPR 将崩溃，hero 应收紧 4bet 范围：
          - density = 0.0 (桌上没有粘性对手)：全范围 4bet
          - density = 0.5 (一半对手粘性)：4bet bluff 频率砍半
          - density ≥ 0.7 (大多数对手粘性)：只用 value 4bet，完全关掉 bluff
        这避免 hand 103 那种 "hero 4bet AKs 60BB 多人池 → 被 2 whale call →
        SPR 0.3 → A-high 无对被迫 jam" 的 -52 BB 结构。
        """
        cat = _hand_category(hole_cards)
        if cat in _4BET_VALUE:
            if cold_callers > 0 and cat in _4BET_MULTIWAY_DOWNGRADE:
                return False
            if sticky_density >= 0.45 and cat in _4BET_MULTIWAY_DOWNGRADE:
                return False
            return True
        freq = _4BET_BLUFF_FREQ.get(cat)
        if freq is None:
            return False
        if cold_callers > 0:
            return False
        # Sticky density 连续下调 bluff 频率
        if sticky_density >= 0.7:
            return False       # 几乎全桌粘性 → 完全关掉 4bet bluff
        adjusted_freq = freq * max(0.0, 1.0 - sticky_density * 2.0)  # density=0.5 → 0
        return self._rng.random() < adjusted_freq

    def should_iso_raise(
        self,
        hole_cards: List[Card],
        position: str,
        num_players: int = 6,
    ) -> bool:
        """Whether to isolate limpers from a non-free-check position.

        RFI ranges are not ISO ranges. If a chart exists for `{pos}-ISO`, it
        gets veto power: chart-fold hands must not be promoted to iso raises
        just because they are in the normal open range.
        """
        cat = _hand_category(hole_cards)
        pos = _normalize_position(position) or position
        chart_key = f"{pos}-ISO"
        refs = lookup_gto(chart_key, cat)
        chart_actions = [action for action in refs.values() if action is not None]
        if chart_actions:
            if any(self._chart_has_action(action, 'raise') for action in chart_actions):
                self.last_expand_reason = f"chart_iso:{chart_key} {cat}"
                return True
            return False

        if (
            cat in _ISO_FALLBACK_RAISE
            and self.in_open_range(hole_cards, position, num_players)
        ):
            self.last_expand_reason = f"fallback_iso:{chart_key} {cat}"
            return True
        return False

    def should_limp_behind(
        self,
        hole_cards: List[Card],
        position: str,
        big_blind: float,
        stack: float,
        to_call: float,
        num_limpers: int,
        stack_bb: float,
        sticky_density: float,
        iso_available: bool = False,
    ) -> bool:
        """Cheap speculative limp-behind / SB complete after existing limpers.

        The range is deliberately narrow and implied-odds driven:
          - small pairs: mainly set mining; can replace ISO only in multiway
            sticky/deep spots where isolation is less valuable.
          - suited connectors: only when the hand would otherwise fold.
          - A2s-A5s / one-gappers: stricter, for very multiway cheap spots.
        """
        if not _LIMP_BEHIND_ENABLED or big_blind <= 0 or stack <= 0:
            return False
        if num_limpers <= 0:
            return False

        cat = _hand_category(hole_cards)
        call_amt = min(to_call if to_call > 0 else big_blind, stack)
        call_bb = call_amt / big_blind
        if call_bb <= 0 or call_bb > _LIMP_BEHIND_MAX_CALL_BB:
            return False
        if stack_bb < _LIMP_BEHIND_MIN_STACK_BB:
            return False

        pos = _normalize_position(position) or position
        sb_complete = pos == 'SB' and call_bb <= 0.75 and num_limpers >= 1
        multi_limp = num_limpers >= _LIMP_BEHIND_MIN_LIMPERS
        loose_payment = (
            sticky_density >= _LIMP_BEHIND_STICKY_DENSITY
            or num_limpers >= _LIMP_BEHIND_LOOSE_LIMPERS
        )
        if not (sb_complete or (multi_limp and loose_payment)):
            return False

        implied = stack_bb / max(call_bb, 0.01)
        if implied < _LIMP_BEHIND_MIN_IMPLIED:
            return False

        if cat in _LIMP_BEHIND_SMALL_PAIRS:
            if iso_available and not (
                _LIMP_BEHIND_REPLACE_ISO
                and multi_limp
                and loose_payment
                and num_limpers >= 3
                and sticky_density >= 0.50
                and stack_bb >= 120.0
                and call_bb <= 1.0
                and cat != '66'
            ):
                return False
            self.last_expand_reason = (
                f"limp_behind:setmine {cat} nlimp={num_limpers} "
                f"call={call_bb:.1f}bb implied={implied:.0f}x"
            )
            return True

        # If chart/fallback already wants to isolate, keep that fold-equity
        # line for non-pair speculative hands.
        if iso_available:
            return False

        if cat in _LIMP_BEHIND_SUITED_CONNECTORS:
            self.last_expand_reason = (
                f"limp_behind:suited_connector {cat} nlimp={num_limpers} "
                f"call={call_bb:.1f}bb implied={implied:.0f}x"
            )
            return True

        strict_multiway = (
            num_limpers >= 3
            and sticky_density >= 0.45
            and stack_bb >= 80.0
            and call_bb <= 1.0
        )
        if strict_multiway and cat in (_LIMP_BEHIND_SUITED_ONE_GAPPERS | _LIMP_BEHIND_WHEEL_AXS):
            kind = 'wheel_axs' if cat in _LIMP_BEHIND_WHEEL_AXS else 'suited_1gap'
            self.last_expand_reason = (
                f"limp_behind:{kind} {cat} nlimp={num_limpers} "
                f"call={call_bb:.1f}bb implied={implied:.0f}x"
            )
            return True
        return False

    def open_raise_size(self, position: str, big_blind: float, stack_bb: float = 100.0) -> float:
        """Standard open raise sizing in chips. Shorter stacks use slightly smaller opens."""
        if position in ('SB',):
            mul = 3.0
        elif position in ('BTN', 'CO'):
            mul = 2.5 if stack_bb >= 20.0 else 2.2
        else:
            mul = 3.0 if stack_bb >= 22.0 else 2.7
        return big_blind * mul

    def iso_raise_size(
        self,
        position: str,
        big_blind: float,
        num_limpers: int,
        stack_bb: float = 100.0,
    ) -> float:
        """Isolation raise size after limpers.

        Common live/solver practice is normal open size plus 1bb per limper.
        SB/BB add one more blind because we are out of position and must charge
        limp-call ranges more for equity realisation.
        """
        base = self.open_raise_size(position, big_blind, stack_bb)
        limpers = max(0, num_limpers)
        if limpers <= 0:
            return base
        pos = _normalize_position(position) or position
        oop_bonus = _ISO_OOP_BONUS_BB if pos in ('SB', 'BB') else 0.0
        return big_blind * (
            (base / big_blind)
            + limpers * _ISO_PER_LIMPER_BB
            + oop_bonus
        )

    def three_bet_size(
        self,
        open_raise: float,
        is_ip: bool,
        big_blind: float,
        open_pos: str = '',
        three_bet_pos: str = '',
    ) -> float:
        """3-bet sizing with position matrix.

        Falls back to IP/OOP default multipliers when either position is
        unknown or missing from the matrix. Floor at 9 × big_blind so we
        never give opener trivial pot odds on a calling response.
        """
        op = _normalize_position(open_pos)
        tp = _normalize_position(three_bet_pos)
        mul = _3BET_SIZE_MULT.get((op, tp))
        if mul is None:
            mul = _3BET_SIZE_FALLBACK_IP if is_ip else _3BET_SIZE_FALLBACK_OOP
        return max(open_raise * mul, big_blind * 9)

    def four_bet_size(
        self,
        last_raise_to: float,
        is_ip: bool,
        hero_open_pos: str = '',
        villain_3bet_pos: str = '',
    ) -> float:
        """4-bet sizing with position matrix.

        `last_raise_to` is the size of the most recent raise we're
        responding to (villain's 3bet amount). `is_ip` is only used as the
        fallback when (hero_open_pos, villain_3bet_pos) isn't mapped.
        """
        hp = _normalize_position(hero_open_pos)
        vp = _normalize_position(villain_3bet_pos)
        mul = _4BET_SIZE_MULT.get((hp, vp))
        if mul is None:
            mul = _4BET_SIZE_FALLBACK_IP if is_ip else _4BET_SIZE_FALLBACK_OOP
        return last_raise_to * mul

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
        is_big_blind: bool = False,
        num_limpers: int = 0,
        equity: float = 0.5,
        to_call: float = 0.0,
        num_players: int = 6,
        num_active_opponents: int = 5,
        stack_bb: float = 100.0,
        villain_position: str = '',
        sticky_density: float = 0.0,
        cold_callers: int = 0,
        squeeze_callers: int = 0,
        fourbet_call_edge_adjust: float = 0.0,
    ) -> Tuple[str, float]:
        """Return (action, amount). action in: fold, call, raise, check."""
        self.last_expand_reason = ''
        cat = _hand_category(hole_cards)
        stack_bb = max(stack_bb, 1.0)
        if (
            abs(big_blind - _ACHIEVEMENT_ENTRY_BB) < 1e-6
            and 0 < to_call <= _ACHIEVEMENT_ENTRY_MAX_CALL_BB * big_blind
        ):
            self.last_expand_reason = (
                f"achievement_entry:bb1000 call<={_ACHIEVEMENT_ENTRY_MAX_CALL_BB:.0f}bb"
            )
            return ('call', min(to_call, stack))

        if facing_action == 'none':
            if is_big_blind and to_call == 0:
                # BB with free option: iso-raise premiums against limpers, otherwise check.
                if num_limpers > 0 and _hand_category(hole_cards) in _BB_ISO_RAISE:
                    size = self.iso_raise_size(position, big_blind, num_limpers, stack_bb)
                    return ('raise', min(size, stack))
                return ('check', 0.0)

            # SB heads-up steal: only BB left, use wide steal range
            if position == 'SB' and num_limpers == 0 and num_active_opponents == 1:
                if cat in _SB_STEAL_VS_BB:
                    size = self.open_raise_size(position, big_blind, stack_bb)
                    return ('raise', min(size, stack))
                return ('fold', 0.0)

            if num_limpers > 0:
                iso_available = self.should_iso_raise(hole_cards, position, num_players)
                if self.should_limp_behind(
                    hole_cards, position, big_blind, stack, to_call,
                    num_limpers, stack_bb, sticky_density,
                    iso_available=iso_available,
                ):
                    return ('call', min(to_call if to_call > 0 else big_blind, stack))
                if iso_available:
                    size = self.iso_raise_size(position, big_blind, num_limpers, stack_bb)
                    return ('raise', min(size, stack))
                return ('fold', 0.0)

            # Normal positions: open or fold (range adjusted for player count)
            if self.in_open_range(hole_cards, position, num_players):
                size = self.open_raise_size(position, big_blind, stack_bb)
                return ('raise', min(size, stack))
            return ('fold', 0.0)

        elif facing_action == 'open':
            if self.should_3bet(
                hole_cards, position, villain_position,
                squeeze_callers=squeeze_callers,
                sticky_density=sticky_density,
            ):
                size = self.three_bet_size(
                    open_raise, is_ip, big_blind,
                    open_pos=villain_position,
                    three_bet_pos=position,
                )
                return ('raise', min(size, stack))
            expand_action = self._ip_small_open_expand_action(
                cat, position, villain_position, is_ip, open_raise,
                big_blind, stack_bb, sticky_density, squeeze_callers,
            )
            if expand_action == 'raise':
                size = self.three_bet_size(
                    open_raise, is_ip, big_blind,
                    open_pos=villain_position,
                    three_bet_pos=position,
                )
                return ('raise', min(size, stack))
            if expand_action == 'call':
                return ('call', min(to_call or open_raise, stack))
            # Pot-odds gate: if calling costs more equity than we have, fold.
            # Catches large/all-in raises where range heuristics should not override math.
            call_amt = min(to_call or open_raise, stack)
            pot_odds = call_amt / (pot + call_amt) if (pot + call_amt) > 0 else 0.0
            # OOP penalty: SB calling OOP requires extra equity vs IP callers
            oop_penalty = 0.04 if (position == 'SB') else 0.0
            # Stack depth: short stacks need stronger hands to commit good chips
            depth_margin = 0.025 if stack_bb < 22.0 else (0.0 if stack_bb < 75.0 else -0.02)
            if equity < pot_odds + oop_penalty + depth_margin:
                return ('fold', 0.0)
            # BB defense range only applies when we are actually in the big blind.
            # Issue I: select BB defend table by opener position (not just SB).
            # Previously only _BB_VS_SB_DEFENSE existed → BB over-folded
            # vs UTG/MP/CO/BTN opens where MDF expects 62-87% defend.
            bb_defend_range = None
            if position == 'BB':
                villain_norm = _normalize_position(villain_position)
                bb_defend_range = _BB_VS_OPEN_DEFENSE.get(
                    villain_norm, _BB_VS_SB_DEFENSE,
                )
            in_range = self.in_open_range(hole_cards, position, num_players) or (
                bb_defend_range is not None and cat in bb_defend_range
            )
            if in_range:
                return ('call', min(to_call or open_raise, stack))
            return ('fold', 0.0)

        elif facing_action == '3bet':
            if self.should_4bet(
                hole_cards,
                sticky_density=sticky_density,
                cold_callers=cold_callers,
            ):
                # In this branch `open_raise` parameter holds villain's
                # 3bet amount (hero opened, villain 3bet, hero now 4bets).
                # hero_open_pos = our `position`; villain_3bet_pos = `villain_position`.
                four_bet = self.four_bet_size(
                    open_raise, is_ip,
                    hero_open_pos=position,
                    villain_3bet_pos=villain_position,
                )
                if stack_bb <= 40 or four_bet >= stack * 0.65:
                    return ('raise', stack)   # 短码或 4bet 已超过 65% 筹码 → jam
                return ('raise', min(four_bet, stack))

            # Position-aware call range (hero's open position determines defend range).
            # Falls back to _3BET_CALL_DEFAULT when hero position unrecognized.
            hero_norm = _normalize_position(position)
            call_range = _3BET_CALL_BY_POS.get(hero_norm, _3BET_CALL_DEFAULT)
            if cat in call_range:
                return ('call', min(to_call or open_raise, stack))
            if self._chart_expand_3bet_call_allowed(
                cat, position, villain_position, open_raise, big_blind,
                stack, pot, to_call, stack_bb,
            ):
                return ('call', min(to_call or open_raise, stack))
            return ('fold', 0.0)

        elif facing_action == '4bet':
            chart_action = self._chart_4bet_defense_action(
                cat, position, villain_position, stack, pot, to_call,
                open_raise, equity, stack_bb, cold_callers, sticky_density,
                fourbet_call_edge_adjust,
            )
            if chart_action == 'raise':
                return ('raise', stack)
            if chart_action == 'call':
                return ('call', min(to_call or open_raise, stack))
            if chart_action == 'fold':
                return ('fold', 0.0)

            if cat in _VS_4BET_FALLBACK_JAM:
                return ('raise', stack)  # 5-bet shove
            if cat in _VS_4BET_FALLBACK_CALL:
                return ('call', min(to_call or open_raise, stack))
            if self._conditional_4bet_call_allowed(
                cat, stack, pot, to_call, open_raise, equity, stack_bb,
                cold_callers, sticky_density, fourbet_call_edge_adjust,
            ):
                return ('call', min(to_call or open_raise, stack))
            return ('fold', 0.0)

        return ('fold', 0.0)
