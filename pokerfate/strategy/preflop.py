"""Preflop range definitions and decision logic.

Ranges are defined as sets of hand categories (strings):
  - "AA", "KK" ... pocket pairs
  - "AKs" ... suited
  - "AKo" ... offsuit
"""

from __future__ import annotations
import random
from typing import List, Optional, Set, Tuple
from pokerfate.core.card import Card, Rank
from pokerfate.core.position import (
    POS_CANONICAL_6MAX as _POS_CANONICAL_6MAX,
    normalize_position as _normalize_position,
)

# _POS_CANONICAL_6MAX and _normalize_position are re-exported for
# backward-compat with tests and any external imports that existed
# before the core.position module was introduced.


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

    def __init__(self, bluff_3bet_freq: float = 0.5,
                 rng: Optional[random.Random] = None):
        self.bluff_3bet_freq = bluff_3bet_freq  # how often to execute 3-bet bluffs
        # Use an instance RNG so preflop decisions are reproducible alongside
        # the v3 engine (doc 03 §10).
        self._rng: random.Random = rng or random.Random()

    def hand_category(self, hole_cards: List[Card]) -> str:
        return _hand_category(hole_cards)

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

    def open_raise_size(self, position: str, big_blind: float, stack_bb: float = 100.0) -> float:
        """Standard open raise sizing in chips. Shorter stacks use slightly smaller opens."""
        if position in ('SB',):
            mul = 3.0
        elif position in ('BTN', 'CO'):
            mul = 2.5 if stack_bb >= 20.0 else 2.2
        else:
            mul = 3.0 if stack_bb >= 22.0 else 2.7
        return big_blind * mul

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
    ) -> Tuple[str, float]:
        """Return (action, amount). action in: fold, call, raise, check."""
        cat = _hand_category(hole_cards)
        stack_bb = max(stack_bb, 1.0)

        if facing_action == 'none':
            if is_big_blind and to_call == 0:
                # BB with free option: iso-raise premiums against limpers, otherwise check.
                if num_limpers > 0 and _hand_category(hole_cards) in _BB_ISO_RAISE:
                    # Standard BB iso formula: (num_limpers + 2) × BB
                    size = (num_limpers + 2) * big_blind
                    return ('raise', min(size, stack))
                return ('check', 0.0)

            # SB heads-up steal: only BB left, use wide steal range
            if position == 'SB' and num_active_opponents == 1:
                if cat in _SB_STEAL_VS_BB:
                    size = self.open_raise_size(position, big_blind, stack_bb)
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
            return ('fold', 0.0)

        elif facing_action == '4bet':
            if cat in _expand_range('AA, KK'):
                return ('raise', stack)  # 5-bet shove
            if cat in _expand_range('QQ, AKs, AKo'):
                return ('call', min(to_call or open_raise, stack))
            return ('fold', 0.0)

        return ('fold', 0.0)
