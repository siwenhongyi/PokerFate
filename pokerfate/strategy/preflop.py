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
# Sources: GTO Wizard 6-max BB-vs-RFI defend ranges. MDF vs 3× open = 0.7;
# IP advantage of opener means real defend is ~0.62-0.85 (tighter vs UTG,
# widest vs BTN).
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

_GREENLINE_VS_OPEN_MAX_OPEN_BB = 4.0
_GREENLINE_VS_OPEN_MIN_STACK_BB = 50.0
_GREENLINE_VS_OPEN_MAX_SQUEEZE_CALLERS = 1
_GREENLINE_VS_OPEN_SQUEEZE_STICKY_CAP = 0.75

# Amount-aware pressure layer.  Bet level is still named by raise count
# (open/3bet/4bet), but the continue range must flex with the actual price.
_TINY_PRESSURE_MAX_CALL_BB = 2.0
_TINY_PRESSURE_MAX_POT_ODDS = 0.12
_CHEAP_PRESSURE_MAX_POT_ODDS = 0.20
_CHEAP_PRESSURE_MAX_STACK_COMMIT = 0.15
_HEAVY_PRESSURE_MIN_POT_ODDS = 0.35
_HEAVY_PRESSURE_MIN_STACK_COMMIT = 0.35
_JAM_PRESSURE_MIN_STACK_COMMIT = 0.65
_OPEN_SIZE_AS_3BET_MIN_BB = 8.0
_OPEN_SIZE_AS_4BET_MIN_BB = 32.0
_PRICE_TINY_EQUITY_EDGE = -0.02
_PRICE_CHEAP_EQUITY_EDGE = 0.03
_PRICE_DEFEND_RANGE = _BTN_RANGE | _SB_STEAL_VS_BB | _3BET_RANGE | _expand_range(
    '22+, A2s+, K2s+, Q5s+, J7s+, T7s+, 97s+, 86s+, 75s+, 65s, 54s, '
    'A9o+, KTo+, QTo+, JTo'
)
_POOL_FOLD_TO_3BET = 0.55
_FOLD_TO_3BET_SHRINK_OPPS = 30.0
_BLUFF_3BET_MIN_EXEC_FREQ = 0.05
_BLUFF_3BET_PURE_CHART_MIN_EVIDENCE = 0.05

_RANK_VALUE = {
    '2': 2, '3': 3, '4': 4, '5': 5, '6': 6, '7': 7,
    '8': 8, '9': 9, 'T': 10, 'J': 11, 'Q': 12, 'K': 13, 'A': 14,
}
_PRESSURE_PREMIUM_CONTINUE = _expand_range('QQ+, AKs, AKo')
_PRESSURE_STRONG_CONTINUE = _expand_range('TT+, AQs, AQo, AJs, KQs')

# Opponent-aware range expansions.  These only add continues against opponents
# whose observed preflop aggression is materially wider than baseline.
_WIDE_OPEN_3BET_EXPAND = _expand_range('99, 88, ATs, KQo, KJs, QJs')
_VERY_WIDE_OPEN_3BET_EXPAND = _WIDE_OPEN_3BET_EXPAND | _expand_range(
    '77, A9s, KTs, QTs, JTs, T9s'
)
_WIDE_3BET_DEFEND_EXPAND = _expand_range(
    '99, 88, 77, AQo, AJo, ATs, A9s, KQo, KJs, KTs, QJs, QTs, JTs, T9s'
)
_VERY_WIDE_3BET_DEFEND_EXPAND = _WIDE_3BET_DEFEND_EXPAND | _expand_range(
    '66, A8s, K9s, Q9s, 98s, 87s'
)


# ---------------------------------------------------------------------------
# 3-bet call fallback by hero-open position (hero open -> vs any 3-bet).
#
# Exact hero-position + villain-position responses still come from Greenline.
# This fallback only runs when that exact chart is absent.  Keep it close to
# the standard 6-max 100bb high-rake "RFI vs 3bet" continue core instead of
# the older hand-written wide defend table.
#
# Source reference: RangeConverter "6 max 100bb 100z GTO Ranges" free PDF.
# The standard chart set has UTG/MP/CO/BTN/SB RFI vs 3bet pages; there is no
# standard BB RFI vs 3bet page, so BB intentionally falls back to default.
# ---------------------------------------------------------------------------
_3BET_CALL_BY_POS = {
    # UTG: narrow continue core; exact blind/late 3bet mixes are chart-backed.
    'UTG': _expand_range('JJ, TT, AKo, AQs, AJs, KQs'),

    # MP: high-rake 100bb core keeps suited broadways; drops old AQo/88 widen.
    'MP':  _expand_range('JJ, TT, 99, AKo, AQs, AJs, ATs, KQs, KJs, QJs'),

    # CO: keep core pair/broadway calls; avoid auto-calling low suited connectors.
    'CO':  _expand_range('JJ, TT, 99, 88, AKo, AQs, AJs, ATs, KQs, KJs, QJs, JTs'),

    # BTN: widest standard RFI-vs-blind-3bet fallback, but still not BB-wide.
    'BTN': _expand_range('JJ, TT, 99, 88, 77, AKo, AQs, AQo, AJs, ATs, A9s, '
                         'KQs, KQo, KJs, KTs, QJs, QTs, JTs, T9s, 98s'),

    # SB: only standard SB RFI vs BB 3bet fallback.
    'SB':  _expand_range('JJ, TT, 99, 88, 77, AKo, AQs, AQo, AJs, ATs, '
                         'A9s, KQs, KQo, KJs, KTs, QJs, QTs, JTs, T9s, 98s'),
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

# Sticky-pool preflop adjustment.  When disabled, RFI/ISO sizing and ISO
# chart handling fall back to the legacy behavior.
_PREFLOP_STICKY_POOL_ADJUST_DEFAULT = os.environ.get(
    'PREFLOP_STICKY_POOL_ADJUST', '1'
) != '0'
_RFI_STICKY_OPEN_BONUS_BB = 1.0

# Isolation raise sizing for the observed sticky pool. Logs show standard
# 3-3.5bb ISO keeps too many callers, so use a 4bb base plus 1bb per limper.
_ISO_BASE_BB = 4.0
_ISO_PER_LIMPER_BB = 1.0
_ISO_OOP_BONUS_BB = 1.0

# Low-cost limp-behind / blind-complete for speculative hands. This is NOT
# open-limp and never applies after a raise. It exists for loose multiway
# tables where paying ~1bb with deep stacks has set-mining / draw implied odds.
_LIMP_BEHIND_ENABLED = os.environ.get('PF_LIMP_BEHIND_ENABLED', '1') != '0'
_LIMP_BEHIND_MAX_CALL_BB = 1.25
_LIMP_BEHIND_MIN_STACK_BB = 0.0
_LIMP_BEHIND_MIN_IMPLIED = 25.0
_LIMP_BEHIND_MIN_LIMPERS = 1
_LIMP_BEHIND_STICKY_DENSITY = 0.35
_LIMP_BEHIND_LOOSE_LIMPERS = 3
_LIMP_BEHIND_SMALL_PAIRS = _expand_range('22, 33, 44, 55, 66')
_LIMP_BEHIND_SUITED_CONNECTORS = _expand_range('54s, 65s, 76s, 87s, 98s, T9s, JTs')
_LIMP_BEHIND_SUITED_ONE_GAPPERS = _expand_range('64s, 75s, 86s, 97s, T8s, J9s, QTs')
_LIMP_BEHIND_WHEEL_AXS = _expand_range('A2s, A3s, A4s, A5s')
_ISO_EDGE_LIMP_DOWNGRADE = _LIMP_BEHIND_SMALL_PAIRS | _expand_range(
    '54s, 65s, 76s, 87s, 98s'
)
_ISO_EDGE_FOLD_DOWNGRADE = _expand_range('KTo, QTo, QJo, JTo, K9s, Q9s, J9s, T8s')
_ISO_EDGE_STICKY_DENSITY = 0.45

# Bluff 3bet frequency by villain (opener) position — applied to _3BET_BLUFF.
# Tighter open (UTG) → fewer 3bet bluffs; wider open (SB/BTN) → more.
_BLUFF_3BET_FREQ_BY_VS_POS = {
    'UTG': 0.20,
    'MP':  0.35,
    'CO':  0.55,
    'BTN': 0.65,
    'SB':  0.70,
}

class PreflopStrategy:
    """Preflop decision engine."""

    def __init__(
        self,
        bluff_3bet_freq: float = 0.5,
        rng: Optional[random.Random] = None,
        sticky_pool_adjust: Optional[bool] = None,
    ):
        self.bluff_3bet_freq = bluff_3bet_freq  # how often to execute 3-bet bluffs
        # Use an instance RNG so preflop decisions are reproducible alongside
        # the v3 engine (doc 03 §10).
        self._rng: random.Random = rng or random.Random()
        self.sticky_pool_adjust = (
            _PREFLOP_STICKY_POOL_ADJUST_DEFAULT
            if sticky_pool_adjust is None
            else bool(sticky_pool_adjust)
        )
        self.last_expand_reason: str = ''

    def _sticky_pool_adjust_enabled(self, override: Optional[bool] = None) -> bool:
        if override is None:
            return bool(self.sticky_pool_adjust)
        return bool(override)

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
        villain_vpip: float = 0.0,
        villain_pfr: float = 0.0,
        villain_three_bet: float = 0.0,
        villain_af: float = 1.5,
        villain_hands_seen: int = 0,
        villain_fold_to_3bet: float = _POOL_FOLD_TO_3BET,
        villain_fold_to_3bet_opps: int = 0,
        open_raise: float = 0.0,
        big_blind: float = 0.0,
        stack: float = 0.0,
        pot: float = 0.0,
        to_call: float = 0.0,
        stack_bb: float = 100.0,
        is_ip: bool = True,
    ) -> bool:
        cat = _hand_category(hole_cards)
        attack_tier = self._opener_attack_tier(
            villain_vpip, villain_pfr, villain_three_bet, villain_af, villain_hands_seen,
        )
        if cat in _3BET_VALUE:
            if squeeze_callers > 0 and cat in _3BET_SQUEEZE_DOWNGRADE:
                return False
            return True
        if attack_tier >= 1 and squeeze_callers == 0 and sticky_density < 0.7:
            if cat in _WIDE_OPEN_3BET_EXPAND:
                self.last_expand_reason = f"villain_expand:wide_open_3bet {cat}"
                return True
            if attack_tier >= 2 and cat in _VERY_WIDE_OPEN_3BET_EXPAND:
                self.last_expand_reason = f"villain_expand:very_wide_open_3bet {cat}"
                return True
        if cat in _3BET_BLUFF:
            # Position-aware bluff freq: tighter opener → fewer bluff 3bets.
            vs_norm = _normalize_position(vs_position)
            freq = _BLUFF_3BET_FREQ_BY_VS_POS.get(vs_norm, self.bluff_3bet_freq)
            if squeeze_callers > 0:
                freq *= 0.35
            if sticky_density >= 0.7:
                return False
            candidate_raise = 0.0
            if open_raise > 0 and big_blind > 0:
                candidate_raise = self.three_bet_size(
                    open_raise, is_ip, big_blind,
                    open_pos=vs_position,
                    three_bet_pos=position,
                )
            freq = self._adjusted_bluff_3bet_freq(
                cat,
                freq,
                position=position,
                villain_position=vs_position,
                open_raise=open_raise,
                big_blind=big_blind,
                stack=stack,
                pot=pot,
                to_call=to_call,
                stack_bb=stack_bb,
                candidate_raise=candidate_raise,
                sticky_density=sticky_density,
                squeeze_callers=squeeze_callers,
                villain_vpip=villain_vpip,
                villain_pfr=villain_pfr,
                villain_three_bet=villain_three_bet,
                villain_af=villain_af,
                villain_hands_seen=villain_hands_seen,
                villain_fold_to_3bet=villain_fold_to_3bet,
                villain_fold_to_3bet_opps=villain_fold_to_3bet_opps,
            )
            if freq < _BLUFF_3BET_MIN_EXEC_FREQ:
                self.last_expand_reason = (
                    f"preflop_exploit:3bet_bluff_block {cat} adj={freq:.0%}"
                )
                return False
            if attack_tier >= 1:
                freq *= 1.0 + 0.35 * attack_tier
            freq = min(1.0, freq)
            fired = self._rng.random() < freq
            if not fired:
                self.last_expand_reason = (
                    f"preflop_exploit:3bet_bluff_freq {cat} adj={freq:.0%}"
                )
            return fired
        return False

    @staticmethod
    def _chart_has_action(action, wanted: str) -> bool:
        if isinstance(action, dict):
            return float(action.get(wanted, 0.0)) > 0.0001
        if isinstance(action, list):
            return wanted in action
        return action == wanted

    @staticmethod
    def _primary_chart_action(refs: dict) -> tuple[object, str]:
        primary = refs.get('primary')
        source = refs.get('primary_source') or ''
        if primary is not None:
            return primary, source
        return None, source

    def _greenline_action(self, chart_key: str, cat: str) -> tuple[str, str]:
        """Return the primary preflop chart action.

        Greenline is the only primary chart. PokerGTO is used only as a
        frequency reference when Greenline returns a mixed action.
        """
        refs = lookup_gto(chart_key, cat)
        action, source = self._primary_chart_action(refs)
        if action is None:
            return '', ''
        raw = action
        if isinstance(action, list):
            choices = [str(a) for a in action if a]
            if not choices:
                return '', ''
            weights = self._pokergto_mix_weights(refs.get('pokergto'), choices)
            weight_source = 'pokergto'
            if weights is None:
                uniform = 1.0 / len(choices)
                weights = {choice: uniform for choice in choices}
                weight_source = 'uniform'
            action = self._weighted_chart_choice(choices, weights)
            weight_text = '/'.join(
                f"{choice}:{weights.get(choice, 0.0):.0%}" for choice in choices
            )
            return str(action), (
                f"{source}_mix:{chart_key} {cat} {choices} "
                f"w={weight_source} {weight_text} -> {action}"
            )
        if isinstance(action, dict):
            choices = [
                str(name)
                for name in ('allin', 'raise', 'call', 'fold')
                if float(action.get(name, 0.0)) > 0.0001
            ]
            if not choices:
                return 'fold', f"{source}:{chart_key} {cat} -> fold"
            weights = {
                choice: max(0.0, float(action.get(choice, 0.0)))
                for choice in choices
            }
            selected = self._weighted_chart_choice(choices, weights)
            weight_text = '/'.join(
                f"{choice}:{weights.get(choice, 0.0):.0%}" for choice in choices
            )
            pg_key = refs.get('pokergto_chart_key') or chart_key
            return selected, (
                f"{source}:{pg_key} {cat} {weight_text} -> {selected}"
            )
        if self._chart_has_action(action, 'allin'):
            return 'allin', f"{source}:{chart_key} {cat} -> allin"
        if self._chart_has_action(action, 'raise'):
            return 'raise', f"{source}:{chart_key} {cat} -> raise"
        if self._chart_has_action(action, 'call'):
            return 'call', f"{source}:{chart_key} {cat} -> call"
        if self._chart_has_action(action, 'fold'):
            return 'fold', f"{source}:{chart_key} {cat} -> fold"
        return '', f"{source}:{chart_key} {cat} -> {raw}"

    def _greenline_vs_open_action(
        self,
        chart_key: str,
        cat: str,
        *,
        position: str,
        villain_position: str,
        open_raise: float,
        big_blind: float,
        stack: float,
        pot: float,
        to_call: float,
        stack_bb: float,
        is_ip: bool,
        sticky_density: float,
        squeeze_callers: int,
        villain_vpip: float,
        villain_pfr: float,
        villain_three_bet: float,
        villain_af: float,
        villain_hands_seen: int,
        villain_fold_to_3bet: float,
        villain_fold_to_3bet_opps: int,
    ) -> tuple[str, str]:
        refs = lookup_gto(chart_key, cat)
        action, source = self._primary_chart_action(refs)
        if action is None:
            return '', ''

        def _fallback_choice(choices: list[str]) -> str:
            if 'call' in choices:
                return 'call'
            return 'fold'

        def _candidate_raise() -> float:
            if open_raise <= 0 or big_blind <= 0:
                return 0.0
            return self.three_bet_size(
                open_raise, is_ip, big_blind,
                open_pos=villain_position,
                three_bet_pos=position,
            )

        def _adjust_raise_weight(base_raise: float) -> tuple[float, str]:
            adjusted = self._adjusted_bluff_3bet_freq(
                cat,
                base_raise,
                position=position,
                villain_position=villain_position,
                open_raise=open_raise,
                big_blind=big_blind,
                stack=stack,
                pot=pot,
                to_call=to_call,
                stack_bb=stack_bb,
                candidate_raise=_candidate_raise(),
                sticky_density=sticky_density,
                squeeze_callers=squeeze_callers,
                villain_vpip=villain_vpip,
                villain_pfr=villain_pfr,
                villain_three_bet=villain_three_bet,
                villain_af=villain_af,
                villain_hands_seen=villain_hands_seen,
                villain_fold_to_3bet=villain_fold_to_3bet,
                villain_fold_to_3bet_opps=villain_fold_to_3bet_opps,
            )
            return adjusted, f"exploit_raise={base_raise:.0%}->{adjusted:.0%}"

        if isinstance(action, list):
            choices = [str(a) for a in action if a]
            if not choices:
                return '', ''
            weights = self._pokergto_mix_weights(refs.get('pokergto'), choices)
            weight_source = 'pokergto'
            if weights is None:
                uniform = 1.0 / len(choices)
                weights = {choice: uniform for choice in choices}
                weight_source = 'uniform'
            exploit_text = ''
            if 'raise' in choices and cat not in _3BET_VALUE:
                base_raise = max(0.0, float(weights.get('raise', 0.0)))
                adjusted, exploit_text = _adjust_raise_weight(base_raise)
                weights = dict(weights)
                weights['raise'] = adjusted
                give_back = max(0.0, base_raise - adjusted)
                fallback = _fallback_choice(choices)
                weights[fallback] = max(0.0, float(weights.get(fallback, 0.0))) + give_back
            selected = self._weighted_chart_choice(choices, weights)
            weight_text = '/'.join(
                f"{choice}:{weights.get(choice, 0.0):.0%}" for choice in choices
            )
            extra = f" {exploit_text}" if exploit_text else ''
            return selected, (
                f"{source}_mix:{chart_key} {cat} {choices} "
                f"w={weight_source} {weight_text}{extra} -> {selected}"
            )

        if isinstance(action, dict):
            choices = [
                str(name)
                for name in ('allin', 'raise', 'call', 'fold')
                if float(action.get(name, 0.0)) > 0.0001
            ]
            if not choices:
                return 'fold', f"{source}:{chart_key} {cat} -> fold"
            weights = {
                choice: max(0.0, float(action.get(choice, 0.0)))
                for choice in choices
            }
            exploit_text = ''
            if 'raise' in choices and cat not in _3BET_VALUE:
                base_raise = max(0.0, float(weights.get('raise', 0.0)))
                adjusted, exploit_text = _adjust_raise_weight(base_raise)
                weights['raise'] = adjusted
                give_back = max(0.0, base_raise - adjusted)
                fallback = _fallback_choice(choices)
                weights[fallback] = max(0.0, float(weights.get(fallback, 0.0))) + give_back
            selected = self._weighted_chart_choice(choices, weights)
            weight_text = '/'.join(
                f"{choice}:{weights.get(choice, 0.0):.0%}" for choice in choices
            )
            extra = f" {exploit_text}" if exploit_text else ''
            pg_key = refs.get('pokergto_chart_key') or chart_key
            return selected, f"{source}:{pg_key} {cat} {weight_text}{extra} -> {selected}"

        if self._chart_has_action(action, 'allin'):
            return 'allin', f"{source}:{chart_key} {cat} -> allin"
        if self._chart_has_action(action, 'raise'):
            if cat in _3BET_VALUE:
                return 'raise', f"{source}:{chart_key} {cat} -> raise"
            size_mult = self._three_bet_size_multiplier(
                open_raise=open_raise,
                big_blind=big_blind,
                stack=stack,
                pot=pot,
                candidate_raise=_candidate_raise(),
            )
            has_exploit_evidence = (
                sticky_density >= _BLUFF_3BET_PURE_CHART_MIN_EVIDENCE
                or villain_fold_to_3bet_opps > 0
                or villain_hands_seen >= 10
                or squeeze_callers > 0
                or size_mult < 0.95
            )
            if has_exploit_evidence:
                adjusted, exploit_text = _adjust_raise_weight(1.0)
                if adjusted < _BLUFF_3BET_MIN_EXEC_FREQ:
                    return 'fold', (
                        f"{source}:{chart_key} {cat} -> fold "
                        f"{exploit_text}"
                    )
                selected = 'raise' if self._rng.random() < adjusted else 'fold'
                return selected, (
                    f"{source}:{chart_key} {cat} -> {selected} "
                    f"{exploit_text}"
                )
            return 'raise', f"{source}:{chart_key} {cat} -> raise"
        if self._chart_has_action(action, 'call'):
            return 'call', f"{source}:{chart_key} {cat} -> call"
        if self._chart_has_action(action, 'fold'):
            return 'fold', f"{source}:{chart_key} {cat} -> fold"
        return '', f"{source}:{chart_key} {cat} -> {action}"

    @staticmethod
    def _pokergto_mix_weights(
        pokergto_action: object,
        choices: list[str],
    ) -> dict[str, float] | None:
        if not isinstance(pokergto_action, dict):
            return None
        choice_set = set(choices)
        nonzero = {
            name
            for name, value in pokergto_action.items()
            if float(value) > 0.0001
        }
        if nonzero - choice_set:
            return None

        weights = {
            choice: max(0.0, float(pokergto_action.get(choice, 0.0)))
            for choice in choices
        }
        total = sum(weights.values())
        if total <= 0:
            return None

        return {choice: weight / total for choice, weight in weights.items()}

    def _weighted_chart_choice(self, choices: list[str], weights: dict[str, float]) -> str:
        weighted = [(choice, max(0.0, float(weights.get(choice, 0.0)))) for choice in choices]
        total = sum(weight for _, weight in weighted)
        if total <= 0:
            return self._rng.choice(choices)

        roll = self._rng.random() * total
        upto = 0.0
        for choice, weight in weighted:
            upto += weight
            if roll <= upto:
                return choice
        return weighted[-1][0]

    @staticmethod
    def _clamp(x: float, lo: float, hi: float) -> float:
        return max(lo, min(hi, x))

    @staticmethod
    def _cat_parts(cat: str) -> tuple[int, int, str]:
        if len(cat) < 2:
            return 0, 0, ''
        hi = _RANK_VALUE.get(cat[0], 0)
        lo = _RANK_VALUE.get(cat[1], 0)
        if hi < lo:
            hi, lo = lo, hi
        return hi, lo, cat[2] if len(cat) >= 3 else ''

    @classmethod
    def _bluff_3bet_hand_quality(cls, cat: str) -> float:
        """Relative realisation/blocker quality for non-value 3bet candidates."""
        if cat in _3BET_VALUE:
            return 1.0
        hi, lo, suited = cls._cat_parts(cat)
        if hi <= 0 or lo <= 0:
            return 0.50
        if suited == '':
            return 0.75 if hi >= 7 else 0.55
        if suited == 's':
            if hi == 14:
                return 1.10 if lo <= 5 else 0.95
            if hi >= 12 and lo >= 9:
                return 0.90
            if hi - lo <= 1 and hi >= 8:
                return 0.80
            if hi - lo <= 2 and hi >= 9:
                return 0.75
            return 0.60
        if hi >= 13 and lo >= 11:
            return 0.75
        if hi >= 12 and lo >= 10:
            return 0.65
        return 0.45

    @classmethod
    def _has_deep_implied_playability(cls, cat: str) -> bool:
        hi, lo, suited = cls._cat_parts(cat)
        if suited == '':
            return 22 <= hi * 10 + lo <= 99
        if suited == 's':
            return hi == 14 or hi - lo <= 2 or (hi >= 11 and lo >= 9)
        return False

    def _fold_to_3bet_prior(
        self,
        *,
        sticky_density: float,
        villain_vpip: float,
        villain_pfr: float,
        villain_hands_seen: int,
    ) -> float:
        prior = _POOL_FOLD_TO_3BET - 0.14 * self._clamp(sticky_density, 0.0, 1.0)
        if villain_hands_seen >= 10:
            gap = max(0.0, villain_vpip - villain_pfr)
            prior -= max(0.0, villain_vpip - 0.42) * 0.35
            prior -= max(0.0, gap - 0.18) * 0.50
            if villain_vpip >= 0.45 and villain_pfr < 0.18 and gap >= 0.22:
                prior -= 0.10
        return self._clamp(prior, 0.25, 0.70)

    def _effective_fold_to_3bet(
        self,
        *,
        sticky_density: float,
        villain_vpip: float,
        villain_pfr: float,
        villain_hands_seen: int,
        villain_fold_to_3bet: float,
        villain_fold_to_3bet_opps: int,
    ) -> float:
        prior = self._fold_to_3bet_prior(
            sticky_density=sticky_density,
            villain_vpip=villain_vpip,
            villain_pfr=villain_pfr,
            villain_hands_seen=villain_hands_seen,
        )
        opps = max(0.0, float(villain_fold_to_3bet_opps or 0))
        if opps <= 0:
            return prior
        rel = opps / (opps + _FOLD_TO_3BET_SHRINK_OPPS)
        observed = self._clamp(float(villain_fold_to_3bet or 0.0), 0.0, 1.0)
        return self._clamp(rel * observed + (1.0 - rel) * prior, 0.05, 0.85)

    def _opener_range_multiplier(
        self,
        *,
        villain_vpip: float,
        villain_pfr: float,
        villain_three_bet: float,
        villain_af: float,
        villain_hands_seen: int,
    ) -> float:
        if villain_hands_seen < 10:
            return 1.0
        gap = max(0.0, villain_vpip - villain_pfr)
        if villain_vpip >= 0.45 and villain_pfr < 0.18 and gap >= 0.22:
            return 0.55
        mult = 1.0
        if villain_pfr < 0.14:
            mult *= 0.65
        elif villain_pfr < 0.18:
            mult *= 0.80
        elif villain_pfr >= 0.30:
            mult *= 1.18
        elif villain_pfr >= 0.24:
            mult *= 1.08
        if villain_three_bet >= 0.12 and villain_af >= 1.5:
            mult *= 1.05
        return self._clamp(mult, 0.45, 1.25)

    def _three_bet_size_multiplier(
        self,
        *,
        open_raise: float,
        big_blind: float,
        stack: float,
        pot: float,
        candidate_raise: float,
    ) -> float:
        mult = 1.0
        if big_blind > 0 and open_raise > 0:
            open_bb = open_raise / big_blind
            if open_bb >= 4.5:
                mult *= 0.45
            elif open_bb >= 4.0:
                mult *= 0.65
            elif open_bb >= 3.5:
                mult *= 0.80
        if stack > 0 and candidate_raise > 0:
            raise_to = min(candidate_raise, stack)
            commit = raise_to / stack
            if commit >= 0.30:
                mult *= 0.35
            elif commit >= 0.22:
                mult *= 0.55
            elif commit >= 0.17:
                mult *= 0.75
            post_stack = max(0.0, stack - raise_to)
            post_pot = max(1.0, pot + raise_to)
            post_spr = post_stack / post_pot
            if post_spr < 2.0:
                mult *= 0.55
            elif post_spr < 3.0:
                mult *= 0.75
        return self._clamp(mult, 0.15, 1.0)

    def _adjusted_bluff_3bet_freq(
        self,
        cat: str,
        base_freq: float,
        *,
        position: str,
        villain_position: str,
        open_raise: float,
        big_blind: float,
        stack: float,
        pot: float,
        to_call: float,
        stack_bb: float,
        candidate_raise: float,
        sticky_density: float,
        squeeze_callers: int,
        villain_vpip: float,
        villain_pfr: float,
        villain_three_bet: float,
        villain_af: float,
        villain_hands_seen: int,
        villain_fold_to_3bet: float,
        villain_fold_to_3bet_opps: int,
    ) -> float:
        del position, villain_position, to_call, stack_bb
        if cat in _3BET_VALUE:
            return 1.0
        eff_fold = self._effective_fold_to_3bet(
            sticky_density=sticky_density,
            villain_vpip=villain_vpip,
            villain_pfr=villain_pfr,
            villain_hands_seen=villain_hands_seen,
            villain_fold_to_3bet=villain_fold_to_3bet,
            villain_fold_to_3bet_opps=villain_fold_to_3bet_opps,
        )
        fold_mult = self._clamp(1.0 + (eff_fold - _POOL_FOLD_TO_3BET) * 2.1, 0.35, 1.35)
        sticky_mult = self._clamp(1.0 - sticky_density * 0.80, 0.25, 1.0)
        range_mult = self._opener_range_multiplier(
            villain_vpip=villain_vpip,
            villain_pfr=villain_pfr,
            villain_three_bet=villain_three_bet,
            villain_af=villain_af,
            villain_hands_seen=villain_hands_seen,
        )
        size_mult = self._three_bet_size_multiplier(
            open_raise=open_raise,
            big_blind=big_blind,
            stack=stack,
            pot=pot,
            candidate_raise=candidate_raise,
        )
        squeeze_mult = 0.55 if squeeze_callers > 0 else 1.0
        quality = self._bluff_3bet_hand_quality(cat)
        return self._clamp(
            base_freq * fold_mult * sticky_mult * range_mult * size_mult * squeeze_mult * quality,
            0.0,
            1.0,
        )

    @staticmethod
    def _pressure_inputs(
        stack: float,
        pot: float,
        to_call: float,
        open_raise: float,
        big_blind: float,
    ) -> tuple[float, float, float, float]:
        raw_call = max(0.0, float(to_call or open_raise or 0.0))
        call_amt = min(raw_call, stack)
        contestable_pot = max(0.0, float(pot or 0.0) - max(0.0, raw_call - call_amt))
        pot_odds = call_amt / (contestable_pot + call_amt) if (contestable_pot + call_amt) > 0 else 1.0
        stack_commit = call_amt / stack if stack > 0 else 1.0
        call_bb = call_amt / big_blind if big_blind > 0 else 99.0
        return call_amt, pot_odds, stack_commit, call_bb

    def _pressure_kind(
        self,
        stack: float,
        pot: float,
        to_call: float,
        open_raise: float,
        big_blind: float,
    ) -> str:
        call_amt, pot_odds, stack_commit, call_bb = self._pressure_inputs(
            stack, pot, to_call, open_raise, big_blind,
        )
        if call_amt <= 0:
            return 'none'
        if stack_commit >= _JAM_PRESSURE_MIN_STACK_COMMIT:
            return 'jam'
        if call_bb <= _TINY_PRESSURE_MAX_CALL_BB or pot_odds <= _TINY_PRESSURE_MAX_POT_ODDS:
            return 'tiny'
        if pot_odds <= _CHEAP_PRESSURE_MAX_POT_ODDS and stack_commit <= _CHEAP_PRESSURE_MAX_STACK_COMMIT:
            return 'cheap'
        if pot_odds >= _HEAVY_PRESSURE_MIN_POT_ODDS or stack_commit >= _HEAVY_PRESSURE_MIN_STACK_COMMIT:
            return 'heavy'
        return 'normal'

    def _price_call_allowed(
        self,
        cat: str,
        stack: float,
        pot: float,
        to_call: float,
        open_raise: float,
        big_blind: float,
        equity: float,
        context: str,
    ) -> bool:
        kind = self._pressure_kind(stack, pot, to_call, open_raise, big_blind)
        if kind not in {'tiny', 'cheap'}:
            return False
        if cat not in _PRICE_DEFEND_RANGE:
            return False
        call_amt, pot_odds, _, call_bb = self._pressure_inputs(
            stack, pot, to_call, open_raise, big_blind,
        )
        edge = _PRICE_TINY_EQUITY_EDGE if kind == 'tiny' else _PRICE_CHEAP_EQUITY_EDGE
        if equity < pot_odds + edge:
            return False
        self.last_expand_reason = (
            f"price_call:{kind}_{context} {cat} "
            f"call={call_bb:.1f}bb po={pot_odds:.0%} eq={equity:.0%}"
        )
        return call_amt > 0

    @staticmethod
    def _opener_attack_tier(
        villain_vpip: float,
        villain_pfr: float,
        villain_three_bet: float,
        villain_af: float,
        villain_hands_seen: int,
    ) -> int:
        if villain_hands_seen < 10:
            return 0
        gap = villain_vpip - villain_pfr
        loose_passive_raise = villain_vpip >= 0.45 and villain_pfr < 0.17 and gap >= 0.20
        if loose_passive_raise:
            return 0
        if (
            villain_pfr >= 0.32
            or (villain_vpip >= 0.50 and villain_pfr >= 0.26)
            or (villain_three_bet >= 0.12 and villain_pfr >= 0.22 and villain_af >= 1.3)
        ):
            return 2
        if (
            villain_pfr >= 0.24
            or (villain_vpip >= 0.42 and villain_pfr >= 0.20)
            or (villain_three_bet >= 0.09 and villain_pfr >= 0.18)
        ):
            return 1
        return 0

    @staticmethod
    def _three_bettor_attack_tier(
        villain_vpip: float,
        villain_pfr: float,
        villain_three_bet: float,
        villain_af: float,
        villain_hands_seen: int,
    ) -> int:
        if villain_hands_seen < 10:
            return 0
        if villain_three_bet >= 0.14 or (
            villain_vpip >= 0.45 and villain_pfr >= 0.28 and villain_af >= 1.3
        ):
            return 2
        if villain_three_bet >= 0.09 or (
            villain_vpip >= 0.38 and villain_pfr >= 0.23 and villain_af >= 1.2
        ):
            return 1
        return 0

    def _dynamic_3bet_call_range(
        self,
        call_range: Set[str],
        villain_vpip: float,
        villain_pfr: float,
        villain_three_bet: float,
        villain_af: float,
        villain_hands_seen: int,
        pressure_kind: str,
    ) -> Set[str]:
        expanded = set(call_range)
        tier = self._three_bettor_attack_tier(
            villain_vpip, villain_pfr, villain_three_bet, villain_af, villain_hands_seen,
        )
        if tier >= 1:
            expanded |= _WIDE_3BET_DEFEND_EXPAND
        if tier >= 2:
            expanded |= _VERY_WIDE_3BET_DEFEND_EXPAND
        if pressure_kind in {'tiny', 'cheap'}:
            expanded |= _WIDE_3BET_DEFEND_EXPAND
        return expanded

    def _greenline_vs_open_expand_action(
        self,
        cat: str,
        position: str,
        villain_position: str,
        open_raise: float,
        big_blind: float,
        stack_bb: float,
        sticky_density: float,
        squeeze_callers: int,
        is_ip: bool,
        stack: float,
        pot: float,
        to_call: float,
        villain_vpip: float,
        villain_pfr: float,
        villain_three_bet: float,
        villain_af: float,
        villain_hands_seen: int,
        villain_fold_to_3bet: float,
        villain_fold_to_3bet_opps: int,
    ) -> str:
        hero_norm = _normalize_position(position)
        villain_norm = _normalize_position(villain_position)
        if not hero_norm or not villain_norm or big_blind <= 0:
            return ''
        if stack_bb < _GREENLINE_VS_OPEN_MIN_STACK_BB:
            return ''
        open_bb = open_raise / big_blind
        if open_bb <= 0 or open_bb > _GREENLINE_VS_OPEN_MAX_OPEN_BB:
            return ''
        if squeeze_callers > _GREENLINE_VS_OPEN_MAX_SQUEEZE_CALLERS:
            return ''
        if squeeze_callers > 0 and sticky_density >= _GREENLINE_VS_OPEN_SQUEEZE_STICKY_CAP:
            return ''

        chart_key = f"{hero_norm}-vs-open-{villain_norm}"
        chart_action, chart_reason = self._greenline_vs_open_action(
            chart_key,
            cat,
            position=position,
            villain_position=villain_position,
            open_raise=open_raise,
            big_blind=big_blind,
            stack=stack,
            pot=pot,
            to_call=to_call,
            stack_bb=stack_bb,
            is_ip=is_ip,
            sticky_density=sticky_density,
            squeeze_callers=squeeze_callers,
            villain_vpip=villain_vpip,
            villain_pfr=villain_pfr,
            villain_three_bet=villain_three_bet,
            villain_af=villain_af,
            villain_hands_seen=villain_hands_seen,
            villain_fold_to_3bet=villain_fold_to_3bet,
            villain_fold_to_3bet_opps=villain_fold_to_3bet_opps,
        )
        if chart_action != 'raise':
            return ''

        mode = 'squeeze' if squeeze_callers > 0 else '3bet'
        self.last_expand_reason = (
            f"chart_expand:{mode} {chart_reason}"
        )
        return 'raise'

    def _can_call_vs_3bet(
        self,
        cat: str,
        call_range: set,
        position: str,
        villain_position: str,
        open_raise: float,
        big_blind: float,
        stack: float,
        pot: float,
        to_call: float,
        stack_bb: float,
        equity: float = 0.5,
    ) -> bool:
        if self._price_call_allowed(
            cat, stack, pot, to_call, open_raise, big_blind, equity, '3bet',
        ):
            return True
        if cat in call_range:
            return True
        return False

    def _chart_call_pressure_allows(
        self,
        cat: str,
        *,
        context: str,
        stack: float,
        pot: float,
        to_call: float,
        open_raise: float,
        big_blind: float,
        stack_bb: float,
        equity: float,
        is_ip: bool,
    ) -> bool:
        call_amt, pot_odds, stack_commit, call_bb = self._pressure_inputs(
            stack, pot, to_call, open_raise, big_blind,
        )
        if call_amt <= 0:
            return True

        pressure = self._pressure_kind(stack, pot, to_call, open_raise, big_blind)
        premium = cat in _PRESSURE_PREMIUM_CONTINUE
        strong = cat in _PRESSURE_STRONG_CONTINUE
        playable = self._has_deep_implied_playability(cat)

        implied_credit = 0.0
        if context == '3bet' and playable and pressure not in {'jam'}:
            if stack_bb >= 90.0 and stack_commit <= 0.18:
                implied_credit = 0.10 if is_ip else 0.08
            elif stack_bb >= 60.0 and stack_commit <= 0.25:
                implied_credit = 0.05 if is_ip else 0.03

        margin = 0.00 if pressure in {'tiny', 'cheap'} else 0.02
        if not is_ip:
            margin += 0.02
        if context == '4bet':
            margin += 0.03
        if pressure == 'heavy':
            margin += 0.03
        elif pressure == 'jam':
            margin += 0.07
        if stack_commit >= 0.35:
            margin += 0.03

        hi, lo, suited = self._cat_parts(cat)
        dominated_broadway = suited == 'o' and hi >= 12 and lo >= 10
        dominated_suited_broadway = suited == 's' and hi <= 13 and lo >= 10
        if dominated_broadway:
            margin += 0.03
        if dominated_suited_broadway and stack_commit >= 0.30:
            margin += 0.03
        if premium:
            margin -= 0.04
        elif strong:
            margin -= 0.02

        realised = equity + implied_credit
        if pressure == 'jam' and not premium and realised < pot_odds + 0.10:
            self.last_expand_reason = (
                f"chart_block:{context}_jam_pressure {cat} "
                f"eq={equity:.0%}+imp={implied_credit:.0%} "
                f"po={pot_odds:.0%} commit={stack_commit:.0%}"
            )
            return False
        if stack_commit >= 0.45 and not (premium or strong) and realised < pot_odds + 0.08:
            self.last_expand_reason = (
                f"chart_block:{context}_commit_pressure {cat} "
                f"eq={equity:.0%}+imp={implied_credit:.0%} "
                f"po={pot_odds:.0%} commit={stack_commit:.0%}"
            )
            return False
        if context == '4bet' and stack_commit >= 0.30 and not premium and realised < pot_odds + 0.08:
            self.last_expand_reason = (
                f"chart_block:{context}_nonpremium_pressure {cat} "
                f"eq={equity:.0%}+imp={implied_credit:.0%} "
                f"po={pot_odds:.0%} commit={stack_commit:.0%}"
            )
            return False

        need = pot_odds + margin
        if realised < need:
            self.last_expand_reason = (
                f"chart_block:{context}_pressure {cat} "
                f"eq={equity:.0%}+imp={implied_credit:.0%} "
                f"need={need:.0%} po={pot_odds:.0%} commit={stack_commit:.0%}"
            )
            return False
        return True

    def _chart_4bet_defense_action(
        self,
        cat: str,
        position: str,
        villain_position: str,
    ) -> str:
        hero_norm = _normalize_position(position)
        villain_norm = _normalize_position(villain_position)
        chart_key = f"{hero_norm}-vs-4bet-{villain_norm}" if hero_norm and villain_norm else ''
        if not chart_key:
            return ''
        chart_action, chart_reason = self._greenline_action(chart_key, cat)
        if not chart_action:
            return ''
        if chart_action in {'allin', 'raise'}:
            self.last_expand_reason = chart_reason
            return 'raise'
        if chart_action == 'call':
            self.last_expand_reason = chart_reason
            return 'call'
        if chart_action == 'fold':
            self.last_expand_reason = chart_reason
            return 'fold'
        return 'fold'

    def _chart_vs_3bet_response_action(
        self,
        cat: str,
        position: str,
        villain_position: str,
    ) -> str:
        """Primary chart response after hero opened and faces a 3bet.

        This is intentionally narrower than `should_4bet`: it only lets a
        clear chart action take priority over the static range.  In particular,
        chart-pure calls must not be promoted to 4bets by `_4BET_VALUE`.
        """
        hero_norm = _normalize_position(position)
        villain_norm = _normalize_position(villain_position)
        chart_key = f"{hero_norm}-vs-3bet-{villain_norm}" if hero_norm and villain_norm else ''
        if not chart_key:
            return ''
        chart_action, chart_reason = self._greenline_action(chart_key, cat)
        if not chart_action:
            return ''
        if chart_action == 'allin':
            self.last_expand_reason = chart_reason
            return 'allin'
        if chart_action == 'raise':
            self.last_expand_reason = chart_reason
            return 'raise'
        if chart_action == 'call':
            self.last_expand_reason = chart_reason
            return 'call'
        if chart_action == 'fold':
            self.last_expand_reason = chart_reason
            return 'fold'
        return ''

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
        num_limpers: int = 0,
        stack_bb: float = 100.0,
        sticky_density: float = 0.0,
        sticky_pool_adjust: Optional[bool] = None,
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
        chart_action = refs.get('primary')
        sticky_adjust = self._sticky_pool_adjust_enabled(sticky_pool_adjust)
        if chart_action is not None:
            if self._chart_has_action(chart_action, 'raise'):
                if sticky_adjust and self._should_downgrade_iso_edge(
                    cat, chart_key, num_limpers, stack_bb, sticky_density,
                ):
                    return False
                self.last_expand_reason = f"chart_iso:{chart_key} {cat}"
                return True
            return False

        if (
            cat in _ISO_FALLBACK_RAISE
            and self.in_open_range(hole_cards, position, num_players)
        ):
            if sticky_adjust and self._should_downgrade_iso_edge(
                cat, chart_key, num_limpers, stack_bb, sticky_density,
            ):
                return False
            self.last_expand_reason = f"fallback_iso:{chart_key} {cat}"
            return True
        return False

    def _should_downgrade_iso_edge(
        self,
        cat: str,
        chart_key: str,
        num_limpers: int,
        stack_bb: float,
        sticky_density: float,
    ) -> bool:
        """Convert edge ISO raises into limp-behind/fold in sticky multiway pots."""
        if num_limpers <= 0:
            return False
        multi_limp = num_limpers >= 2
        sticky = sticky_density >= _ISO_EDGE_STICKY_DENSITY
        if not (multi_limp or sticky):
            return False

        if cat in _ISO_EDGE_LIMP_DOWNGRADE:
            self.last_expand_reason = (
                f"iso_downgrade:overlimp {chart_key} {cat} "
                f"nlimp={num_limpers} sticky={sticky_density:.0%} stack={stack_bb:.0f}bb"
            )
            return True

        if multi_limp and cat in _ISO_EDGE_FOLD_DOWNGRADE:
            self.last_expand_reason = (
                f"iso_downgrade:fold {chart_key} {cat} "
                f"nlimp={num_limpers} sticky={sticky_density:.0%}"
            )
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
          - small pairs: mainly set mining, but only when the hand would
            otherwise fold; do not convert chart/fallback ISO raises to limps.
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
        if _LIMP_BEHIND_MIN_STACK_BB > 0 and stack_bb < _LIMP_BEHIND_MIN_STACK_BB:
            return False
        if iso_available:
            return False

        pos = _normalize_position(position) or position
        sb_complete = pos == 'SB' and call_bb <= 0.75 and num_limpers >= 1
        if not (sb_complete or num_limpers >= _LIMP_BEHIND_MIN_LIMPERS):
            return False

        implied = stack_bb / max(call_bb, 0.01)
        if implied < _LIMP_BEHIND_MIN_IMPLIED:
            return False

        if cat in _LIMP_BEHIND_SMALL_PAIRS:
            self.last_expand_reason = (
                f"limp_behind:setmine {cat} nlimp={num_limpers} "
                f"call={call_bb:.1f}bb implied={implied:.0f}x"
            )
            return True

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

    def open_raise_size(
        self,
        position: str,
        big_blind: float,
        stack_bb: float = 100.0,
        sticky_pool_adjust: Optional[bool] = None,
    ) -> float:
        """Standard open raise sizing in chips. Open size is position-based."""
        if position in ('SB',):
            mul = 3.0
        elif position in ('BTN', 'CO'):
            mul = 2.5
        else:
            mul = 3.0
        if self._sticky_pool_adjust_enabled(sticky_pool_adjust):
            mul += _RFI_STICKY_OPEN_BONUS_BB
        return big_blind * mul

    def iso_raise_size(
        self,
        position: str,
        big_blind: float,
        num_limpers: int,
        stack_bb: float = 100.0,
        sticky_pool_adjust: Optional[bool] = None,
    ) -> float:
        """Isolation raise size after limpers.

        Sticky-pool adjustment: use 4bb plus 1bb per limper. When disabled,
        restore the legacy normal-open-plus-limper-premium formula.
        """
        limpers = max(0, num_limpers)
        sticky_adjust = self._sticky_pool_adjust_enabled(sticky_pool_adjust)
        if limpers <= 0:
            return self.open_raise_size(
                position,
                big_blind,
                stack_bb,
                sticky_pool_adjust=sticky_adjust,
            )
        if not sticky_adjust:
            base = self.open_raise_size(
                position,
                big_blind,
                stack_bb,
                sticky_pool_adjust=False,
            )
            pos = _normalize_position(position) or position
            oop_bonus = _ISO_OOP_BONUS_BB if pos in ('SB', 'BB') else 0.0
            return big_blind * (
                (base / big_blind)
                + limpers * _ISO_PER_LIMPER_BB
                + oop_bonus
            )
        return big_blind * (
            _ISO_BASE_BB
            + limpers * _ISO_PER_LIMPER_BB
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
        villain_vpip: float = 0.0,
        villain_pfr: float = 0.0,
        villain_three_bet: float = 0.0,
        villain_af: float = 1.5,
        villain_hands_seen: int = 0,
        villain_fold_to_3bet: float = _POOL_FOLD_TO_3BET,
        villain_fold_to_3bet_opps: int = 0,
        sticky_pool_adjust: Optional[bool] = None,
    ) -> Tuple[str, float]:
        """Return (action, amount). action in: fold, call, raise, check."""
        self.last_expand_reason = ''
        cat = _hand_category(hole_cards)
        stack_bb = max(stack_bb, 1.0)
        sticky_adjust = self._sticky_pool_adjust_enabled(sticky_pool_adjust)
        size_map_reason = ''
        if facing_action == 'open' and big_blind > 0 and open_raise > 0:
            open_bb = open_raise / big_blind
            if open_bb >= _OPEN_SIZE_AS_4BET_MIN_BB:
                facing_action = '4bet'
                size_map_reason = f"size_map:open_as_4bet open={open_bb:.1f}bb"
                self.last_expand_reason = size_map_reason
            elif open_bb >= _OPEN_SIZE_AS_3BET_MIN_BB:
                facing_action = '3bet'
                size_map_reason = f"size_map:open_as_3bet open={open_bb:.1f}bb"
                self.last_expand_reason = size_map_reason
        # Historical parameter name is is_big_blind, but callers use it as a
        # "free check available" signal.  It is only allowed to convert a
        # would-be fold into check after normal open/ISO logic has run.
        free_check_option = bool(is_big_blind and to_call == 0)

        def _fold_fallback() -> Tuple[str, float]:
            if free_check_option:
                self.last_expand_reason = 'free_check_option:fold_to_check'
                return ('check', 0.0)
            return ('fold', 0.0)

        def _preserve_size_map_reason() -> None:
            if (
                size_map_reason
                and self.last_expand_reason
                and not self.last_expand_reason.startswith(size_map_reason)
            ):
                self.last_expand_reason = (
                    f"{size_map_reason} | {self.last_expand_reason}"
                )

        if facing_action == 'none':
            pos = _normalize_position(position) or position
            if num_limpers == 0:
                chart_key = f"{pos}-RFI"
                chart_action, chart_reason = self._greenline_action(chart_key, cat)
                if chart_action in {'allin', 'raise'}:
                    self.last_expand_reason = chart_reason
                    size = self.open_raise_size(
                        position,
                        big_blind,
                        stack_bb,
                        sticky_pool_adjust=sticky_adjust,
                    )
                    return ('raise', min(size, stack))
                if chart_action == 'fold':
                    self.last_expand_reason = chart_reason
                    return _fold_fallback()

            # SB heads-up steal: only BB left, use wide steal range
            if position == 'SB' and num_limpers == 0 and num_active_opponents == 1:
                if cat in _SB_STEAL_VS_BB:
                    size = self.open_raise_size(
                        position,
                        big_blind,
                        stack_bb,
                        sticky_pool_adjust=sticky_adjust,
                    )
                    return ('raise', min(size, stack))
                return _fold_fallback()

            if num_limpers > 0:
                iso_available = self.should_iso_raise(
                    hole_cards,
                    position,
                    num_players,
                    num_limpers,
                    stack_bb,
                    sticky_density,
                    sticky_pool_adjust=sticky_adjust,
                )
                if self.should_limp_behind(
                    hole_cards, position, big_blind, stack, to_call,
                    num_limpers, stack_bb, sticky_density,
                    iso_available=iso_available,
                ):
                    return ('call', min(to_call if to_call > 0 else big_blind, stack))
                if iso_available:
                    size = self.iso_raise_size(
                        position,
                        big_blind,
                        num_limpers,
                        stack_bb,
                        sticky_pool_adjust=sticky_adjust,
                    )
                    return ('raise', min(size, stack))
                return _fold_fallback()

            # Normal positions: open or fold (range adjusted for player count)
            if self.in_open_range(hole_cards, position, num_players):
                size = self.open_raise_size(
                    position,
                    big_blind,
                    stack_bb,
                    sticky_pool_adjust=sticky_adjust,
                )
                return ('raise', min(size, stack))
            return _fold_fallback()

        elif facing_action == 'open':
            hero_norm = _normalize_position(position)
            villain_norm = _normalize_position(villain_position)
            chart_key = f"{hero_norm}-vs-open-{villain_norm}" if hero_norm and villain_norm else ''
            chart_action, chart_reason = (
                self._greenline_vs_open_action(
                    chart_key,
                    cat,
                    position=position,
                    villain_position=villain_position,
                    open_raise=open_raise,
                    big_blind=big_blind,
                    stack=stack,
                    pot=pot,
                    to_call=to_call,
                    stack_bb=stack_bb,
                    is_ip=is_ip,
                    sticky_density=sticky_density,
                    squeeze_callers=squeeze_callers,
                    villain_vpip=villain_vpip,
                    villain_pfr=villain_pfr,
                    villain_three_bet=villain_three_bet,
                    villain_af=villain_af,
                    villain_hands_seen=villain_hands_seen,
                    villain_fold_to_3bet=villain_fold_to_3bet,
                    villain_fold_to_3bet_opps=villain_fold_to_3bet_opps,
                ) if chart_key else ('', '')
            )
            call_amt, pot_odds, _, _ = self._pressure_inputs(
                stack, pot, to_call, open_raise, big_blind,
            )
            oop_penalty = 0.04 if (position == 'SB') else 0.0
            depth_margin = -0.02 if stack_bb >= 75.0 else 0.0
            if chart_action in {'allin', 'raise'}:
                self.last_expand_reason = chart_reason
                size = self.three_bet_size(
                    open_raise, is_ip, big_blind,
                    open_pos=villain_position,
                    three_bet_pos=position,
                )
                return ('raise', min(size, stack))
            if chart_action == 'call':
                self.last_expand_reason = chart_reason
                if self._price_call_allowed(
                    cat, stack, pot, to_call, open_raise, big_blind, equity, 'open',
                ):
                    return ('call', call_amt)
                if call_amt > 0 and equity >= pot_odds + oop_penalty + depth_margin:
                    return ('call', call_amt)
                return _fold_fallback()
            if chart_action == 'fold':
                self.last_expand_reason = chart_reason
                if self._price_call_allowed(
                    cat, stack, pot, to_call, open_raise, big_blind, equity, 'open',
                ):
                    return ('call', call_amt)
                return _fold_fallback()

            if squeeze_callers > 0:
                expand_action = self._greenline_vs_open_expand_action(
                    cat, position, villain_position, open_raise, big_blind,
                    stack_bb, sticky_density, squeeze_callers,
                    is_ip, stack, pot, to_call,
                    villain_vpip, villain_pfr, villain_three_bet, villain_af,
                    villain_hands_seen, villain_fold_to_3bet, villain_fold_to_3bet_opps,
                )
                if expand_action == 'raise':
                    size = self.three_bet_size(
                        open_raise, is_ip, big_blind,
                        open_pos=villain_position,
                        three_bet_pos=position,
                    )
                    return ('raise', min(size, stack))
            if self.should_3bet(
                hole_cards, position, villain_position,
                squeeze_callers=squeeze_callers,
                sticky_density=sticky_density,
                villain_vpip=villain_vpip,
                villain_pfr=villain_pfr,
                villain_three_bet=villain_three_bet,
                villain_af=villain_af,
                villain_hands_seen=villain_hands_seen,
                villain_fold_to_3bet=villain_fold_to_3bet,
                villain_fold_to_3bet_opps=villain_fold_to_3bet_opps,
                open_raise=open_raise,
                big_blind=big_blind,
                stack=stack,
                pot=pot,
                to_call=to_call,
                stack_bb=stack_bb,
                is_ip=is_ip,
            ):
                size = self.three_bet_size(
                    open_raise, is_ip, big_blind,
                    open_pos=villain_position,
                    three_bet_pos=position,
                )
                return ('raise', min(size, stack))
            if squeeze_callers <= 0:
                expand_action = self._greenline_vs_open_expand_action(
                    cat, position, villain_position, open_raise, big_blind,
                    stack_bb, sticky_density, squeeze_callers,
                    is_ip, stack, pot, to_call,
                    villain_vpip, villain_pfr, villain_three_bet, villain_af,
                    villain_hands_seen, villain_fold_to_3bet, villain_fold_to_3bet_opps,
                )
                if expand_action == 'raise':
                    size = self.three_bet_size(
                        open_raise, is_ip, big_blind,
                        open_pos=villain_position,
                        three_bet_pos=position,
                    )
                    return ('raise', min(size, stack))
            # Pot-odds gate: if calling costs more equity than we have, fold.
            # Catches large/all-in raises where range heuristics should not override math.
            # OOP penalty: SB calling OOP requires extra equity vs IP callers
            # Deep enough stacks get a small realization discount; short stacks
            # no longer pay an extra penalty here.
            if self._price_call_allowed(
                cat, stack, pot, to_call, open_raise, big_blind, equity, 'open',
            ):
                return ('call', call_amt)
            if equity < pot_odds + oop_penalty + depth_margin:
                return _fold_fallback()
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
            return _fold_fallback()

        elif facing_action == '3bet':
            hero_norm = _normalize_position(position)
            call_range = _3BET_CALL_BY_POS.get(hero_norm, _3BET_CALL_DEFAULT)
            pressure = self._pressure_kind(stack, pot, to_call, open_raise, big_blind)
            call_range = self._dynamic_3bet_call_range(
                call_range,
                villain_vpip,
                villain_pfr,
                villain_three_bet,
                villain_af,
                villain_hands_seen,
                pressure,
            )
            chart_action = self._chart_vs_3bet_response_action(
                cat, position, villain_position,
            )
            if chart_action in {'allin', 'raise'}:
                four_bet = self.four_bet_size(
                    open_raise, is_ip,
                    hero_open_pos=position,
                    villain_3bet_pos=villain_position,
                )
                if chart_action == 'allin':
                    _preserve_size_map_reason()
                    return ('raise', stack)
                _preserve_size_map_reason()
                return ('raise', min(four_bet, stack))

            if chart_action == 'call':
                self.last_expand_reason = (
                    f"chart_expand:3bet_call greenline "
                    f"{hero_norm}-vs-3bet-{_normalize_position(villain_position)} {cat}"
                )
                if not self._chart_call_pressure_allows(
                    cat,
                    context='3bet',
                    stack=stack,
                    pot=pot,
                    to_call=to_call,
                    open_raise=open_raise,
                    big_blind=big_blind,
                    stack_bb=stack_bb,
                    equity=equity,
                    is_ip=is_ip,
                ):
                    _preserve_size_map_reason()
                    return _fold_fallback()
                _preserve_size_map_reason()
                return ('call', min(to_call or open_raise, stack))

            if chart_action == 'fold':
                if self._price_call_allowed(
                    cat, stack, pot, to_call, open_raise, big_blind, equity, '3bet',
                ):
                    _preserve_size_map_reason()
                    return ('call', min(to_call or open_raise, stack))
                _preserve_size_map_reason()
                return _fold_fallback()

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
                _preserve_size_map_reason()
                return ('raise', min(four_bet, stack))

            # Position-aware call range (hero's open position determines defend range).
            # Falls back to _3BET_CALL_DEFAULT when hero position unrecognized.
            if self._can_call_vs_3bet(
                cat, call_range, position, villain_position,
                open_raise, big_blind, stack, pot, to_call, stack_bb,
                equity,
            ):
                _preserve_size_map_reason()
                return ('call', min(to_call or open_raise, stack))
            _preserve_size_map_reason()
            return _fold_fallback()

        elif facing_action == '4bet':
            chart_action = self._chart_4bet_defense_action(
                cat, position, villain_position,
            )
            if chart_action == 'raise':
                return ('raise', stack)
            if chart_action == 'call':
                if not self._chart_call_pressure_allows(
                    cat,
                    context='4bet',
                    stack=stack,
                    pot=pot,
                    to_call=to_call,
                    open_raise=open_raise,
                    big_blind=big_blind,
                    stack_bb=stack_bb,
                    equity=equity,
                    is_ip=is_ip,
                ):
                    return _fold_fallback()
                return ('call', min(to_call or open_raise, stack))
            if chart_action == 'fold':
                if self._price_call_allowed(
                    cat, stack, pot, to_call, open_raise, big_blind, equity, '4bet',
                ):
                    return ('call', min(to_call or open_raise, stack))
                return _fold_fallback()

            if self._price_call_allowed(
                cat, stack, pot, to_call, open_raise, big_blind, equity, '4bet',
            ):
                return ('call', min(to_call or open_raise, stack))
            if cat in _VS_4BET_FALLBACK_JAM:
                return ('raise', stack)  # 5-bet shove
            if cat in _VS_4BET_FALLBACK_CALL:
                return ('call', min(to_call or open_raise, stack))
            return _fold_fallback()

        return ('fold', 0.0)
