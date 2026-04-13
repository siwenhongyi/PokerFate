"""Postflop strategy: board texture analysis, c-bet, bet sizing decisions.

改动历史（vs 上一版本）
──────────────────────────────────────────────────────────────────────────
P1  nut_advantage 参数：传入 bet_size，允许 overbet 极化尺度
P2  OOP 怪手不再 +8pp 下注，而是 -12pp（保留 check-raise 空间）
P3  fold_to_cbet 进入半诈唬 EV 判断（而非固定频率）
P4  河牌 OOP 薄价值频率按对手类型区分（不再统一 92%）
P5  _last_bet_frac 追踪翻牌注码，转牌 bet_size 用于一致性约束
P6  is_delayed_cbet 标志：翻牌过牌后转牌下注，降低门槛 5pp
P7  should_donk_bet：OOP 转牌 donk（翻牌 IP check-back 后）
P8  opponent_af 参数：AF 高降频 cbet，AF 低升频
P9  opponent_checked_back 标志：IP check-back → 大幅提升探测下注频率
P10 湿润面弱半诈唬改为 [50%, 66%] 注码（而非 [33%, 50%]）
P11 多人底池强价值引入 equity_bonus 连续权重（而非 0.50 clamp）
P12 空气诈唬加入 equity_scale 连续衰减（equity 越低频率越低）
P13 位置粒度细化：BTN=+12%，CO=+5%，UTG=-12%，UTG+1=-10%，LJ=-7%
P14 RNG 隔离：所有 random 调用改为 self._rng，每次 decide() 生成可复现种子
P15 多人底池封顶：num_opponents>1 时 frac ≤ 0.80，不超池避免吓跑松散跟注者
──────────────────────────────────────────────────────────────────────────
"""

from __future__ import annotations
import os
import struct
import random as _random_module
from typing import List, Optional, Tuple
from pokerfate.core.card import Card
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
        self.max_suit_count = max(suit_cnt.values(), default=0)
        self.flush_draw = self.max_suit_count >= 2
        self.monotone = self.max_suit_count >= 3
        self.four_flush = len(self.board) >= 4 and self.max_suit_count >= 4

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

    @property
    def is_flush_heavy(self) -> bool:
        """Flop 单调面，或转/河出现 4 张同花公牌。"""
        return self.monotone or self.four_flush

    def recommended_cbet_size_fraction(self) -> float:
        """Fraction of pot recommended for c-bet based on board texture."""
        if self.is_dry:
            return 0.33
        if self.is_wet:
            return 0.66
        return 0.5

    def __repr__(self) -> str:
        return (f"BoardTexture(wetness={self.wetness:.2f}, paired={self.is_paired}, "
                f"flush_heavy={self.is_flush_heavy}, connected={self.connected})")


class PostflopStrategy:
    """Postflop decision engine."""

    def __init__(self, aggression: float = 1.0, rng: _random_module.Random = None):
        """
        aggression : multiplier on betting frequencies. 1.0 = balanced GTO.
        rng        : optional pre-seeded Random instance (useful for testing).
                     Pass None to get a fresh instance seeded from os.urandom.
        """
        self.aggression = aggression
        self.value_mult = 1.0
        self.gto = GTOMath()

        # P14 – per-instance RNG; never touches the global random state
        self._rng: _random_module.Random = rng if rng is not None else _random_module.Random()
        self._last_decision_seed: int = 0

        # Diagnostic dicts populated during should_cbet() / bet_size()
        self._last_cbet_detail: dict = {}
        self._last_bet_detail: dict = {}

        # P5 – track last flop bet fraction for multi-street sizing consistency
        self._last_bet_frac: float = 0.0
        self._last_bet_street: str = ""

    # ------------------------------------------------------------------
    # RNG helpers (P14)
    # ------------------------------------------------------------------

    def _new_decision_seed(self) -> int:
        """Generate a fresh seed from os.urandom, apply to _rng, and return it.

        Logging this seed allows exact replay of any decision sequence.
        """
        raw = os.urandom(4)
        seed = struct.unpack(">I", raw)[0]
        self._rng.seed(seed)
        self._last_decision_seed = seed
        return seed

    def seed_for_testing(self, seed: int) -> None:
        """Pin the RNG to a fixed seed (use in unit tests for determinism)."""
        self._rng.seed(seed)
        self._last_decision_seed = seed

    # ------------------------------------------------------------------
    # Primary decision
    # ------------------------------------------------------------------

    def should_cbet(
        self,
        equity: float,
        board: BoardTexture,
        is_ip: bool,
        street: str,
        num_opponents: int = 1,
        opponent_fold_rate: float = 0.45,
        fold_to_cbet: Optional[float] = None,   # P3 – measured fold-to-cbet
        value_only: bool = False,
        position: str = "MP",
        opponent_af: float = 1.5,               # P8 – opponent aggression factor
        nut_advantage: float = 0.0,             # P1 – 0=no advantage, 1=maximal
        is_delayed_cbet: bool = False,          # P6 – checked last street, now betting
        opponent_checked_back: bool = False,    # P9 – IP opponent checked back last street
    ) -> bool:
        """Decide whether to make the first open bet on this street.

        Returns True = bet, False = check.
        Sets self._last_cbet_detail with full diagnostics.
        """
        # P3 – prefer measured fold-to-cbet over the generic fold-rate
        effective_fold_rate = fold_to_cbet if fold_to_cbet is not None else opponent_fold_rate

        # ── Step 0: aggression multiplier ────────────────────────────────
        # P13 – finer position granularity (BTN vs CO, UTG vs LJ)
        ag = self.aggression
        if position == "BTN":
            ag *= 1.12
        elif position == "CO":
            ag *= 1.05
        elif position in ("UTG", "UTG+1"):
            ag *= 0.88
        elif position in ("UTG+2", "LJ"):
            ag *= 0.93
        # HJ/MP: no adjustment

        # P8 – opponent AF adjustment
        if opponent_af > 2.0:
            ag *= 0.88   # aggressive opp → let him bluff, I cbet less
        elif opponent_af < 1.0:
            ag *= 1.10   # passive opp → I need to generate action

        ag = min(ag, 1.55)
        ag_value = max(ag, 1.0)
        ag_value = min(ag_value, 1.55)

        # P6/P9 – equity threshold discount when we have soft-range information
        eq_discount = 0.0
        if is_delayed_cbet:
            eq_discount += 0.05   # checked flop → opponent's range softened on turn
        if opponent_checked_back:
            eq_discount += 0.05   # IP check-back = his range is weak

        def _rand_bet(threshold: float, label: str) -> bool:
            rv = self._rng.random()
            self._last_cbet_detail.update({
                'branch': label,
                'threshold': round(threshold, 4),
                'random_val': round(rv, 4),
                'decision': rv < threshold,
            })
            return rv < threshold

        # R5: always pre-populate 'branch' so callers never hit KeyError
        self._last_cbet_detail = {'ag': round(ag, 3), 'ag_value': round(ag_value, 3),
                                   'eq_discount': eq_discount, 'nut_advantage': nut_advantage,
                                   'branch': 'unknown', 'decision': False}

        # ── Step 1: pure value mode (vs calling stations) ────────────────
        if value_only:
            threshold = (
                0.60 if street == 'river'
                else (0.50 if num_opponents <= 1 and board.is_dry else 0.55)
            )
            result = equity >= (threshold - eq_discount)
            self._last_cbet_detail.update({'branch': 'value_only', 'threshold': threshold,
                                            'decision': result})
            return result

        # ── Step 2: river → separate logic ───────────────────────────────
        if street == 'river':
            return self._should_river_bet(equity, is_ip, num_opponents,
                                           effective_fold_rate, ag)

        # Effective equity after delayed/probe discount
        eff_eq = equity + eq_discount

        # ── Step 3: monster hand (flop/turn), equity >= 0.90 ─────────────
        if equity >= 0.90:
            if num_opponents >= 2:
                self._last_cbet_detail['branch'] = 'monster_multiway'
                self._last_cbet_detail['decision'] = True
                return True
            # P2 – OOP monsters should preserve check-raise space (reduced, not increased)
            p_bet = min(1.0, 0.80 * ag_value)
            if not board.is_dry:
                p_bet = min(1.0, p_bet + 0.10)
            if not is_ip:
                p_bet = max(0.50, p_bet - 0.12)   # P2: reduce instead of increase
            return _rand_bet(p_bet, 'monster_hu')

        # ── Step 4: strong value, equity >= 0.60 (adjusted) ─────────────
        if eff_eq >= 0.60:
            if num_opponents <= 1:
                self._last_cbet_detail.update({'branch': 'strong_value_hu', 'decision': True})
                return True
            # P11 – confirmed strong hands (equity >= 0.75) always bet in multiway:
            # randomising a made straight/flush/set gives up real value to preserve
            # range balance that barely matters when 3+ players saw your check.
            if equity >= 0.75:
                self._last_cbet_detail.update({'branch': 'strong_value_mw_nut', 'decision': True})
                return True
            # Medium-strong (0.60-0.75): continuous weight still applies
            base = 0.90 if board.is_dry else 0.80
            equity_bonus = (equity - 0.60) / 0.30  # 0→0 at eq=0.60, 1→1 at eq=0.90
            equity_bonus = max(0.0, min(1.0, equity_bonus))
            freq = base - 0.10 * (num_opponents - 1) + 0.10 * equity_bonus
            freq = max(0.40, min(0.95, freq))
            return _rand_bet(freq * ag_value, 'strong_value_mw')

        # ── Step 5: weak hand, give up ────────────────────────────────────
        if equity < 0.20 and effective_fold_rate < 0.40:
            self._last_cbet_detail.update({'branch': 'give_up', 'decision': False})
            return False

        # ── Step 6: multiway semi-bluff floor ────────────────────────────
        if num_opponents >= 2 and equity < 0.45:
            self._last_cbet_detail.update({'branch': 'mw_bluff_floor', 'decision': False})
            return False

        # ── Step 7: semi-bluff zone, 0.30 <= equity <= 0.60 ─────────────
        # P3 – EV-gated: only semi-bluff if fold EV > 0
        if 0.30 <= equity <= 0.60:
            bet_frac_approx = 0.50
            bluff_ev = (effective_fold_rate * 1.0
                        - (1.0 - effective_fold_rate) * bet_frac_approx * (1.0 - equity))
            if bluff_ev <= 0 and equity < 0.45:
                self._last_cbet_detail.update({'branch': 'semi_bluff_ev_neg', 'decision': False,
                                                'bluff_ev': round(bluff_ev, 4)})
                return False

            freq = 0.65 if board.is_dry else 0.45
            freq *= ag
            if not is_ip:
                freq *= 0.85
            if num_opponents > 1:
                freq *= (0.6 ** (num_opponents - 1))
            # P9 – probe/delayed cbet boost
            if opponent_checked_back or is_delayed_cbet:
                freq = min(freq * 1.20, 1.0)
            return _rand_bet(freq, 'semi_bluff')

        # ── Step 8: air / pure bluff, equity < 0.30 ──────────────────────
        # P12 – equity_scale: lower equity → lower bluff frequency
        equity_scale = max(0.0, equity / 0.30)
        freq_base = (0.55 if board.is_dry else 0.35) * equity_scale
        freq_base *= ag
        if not is_ip:
            freq_base *= 0.80
        if num_opponents > 1:
            freq_base *= (0.5 ** (num_opponents - 1))
        # P9 – probe boost for air too (opponent range is very soft)
        if opponent_checked_back or is_delayed_cbet:
            freq_base = min(freq_base * 1.15, 0.70)
        return _rand_bet(freq_base, 'air_bluff')

    def _should_river_bet(
        self,
        equity: float,
        is_ip: bool,
        num_opponents: int,
        opponent_fold_rate: float,
        ag: float,
    ) -> bool:
        """River betting: value or pure fold-equity bluff only (no semi-bluffs)."""
        # Strong value: always bet
        if equity >= 0.70:
            self._last_cbet_detail.update({'branch': 'river_strong_value', 'decision': True})
            return True

        # P4 – thin value (0.60-0.70): OOP frequency depends on opponent type
        if equity >= 0.60:
            if not is_ip:
                # Calling station (low fold_rate) → OOP can bet for value, they call with weaker
                # Balanced/tight → OOP bet-call structure is bad, reduce frequency
                bet_freq = 0.88 if opponent_fold_rate < 0.40 else 0.62
            else:
                bet_freq = 0.80
            # R2: thin value in multiway is risky (someone else may have us beat)
            if num_opponents > 1:
                bet_freq *= (0.75 ** (num_opponents - 1))
            rv = self._rng.random()
            result = rv < (bet_freq * ag)
            self._last_cbet_detail.update({
                'branch': 'river_thin_value',
                'bet_freq': round(bet_freq, 3),
                'random_val': round(rv, 4),
                'decision': result,
            })
            return result

        # Merge hand (0.50-0.60): HU only
        if equity >= 0.50:
            if num_opponents > 1:
                self._last_cbet_detail.update({'branch': 'river_merge_mw', 'decision': False})
                return False
            rv = self._rng.random()
            result = rv < (0.45 * ag)
            self._last_cbet_detail.update({'branch': 'river_merge', 'random_val': round(rv, 4),
                                            'decision': result})
            return result

        # Pure bluff: GTO break-even for 66% pot bluff ≈ 40% fold rate
        if equity < 0.35 and num_opponents == 1:
            if opponent_fold_rate > 0.40:
                bluff_freq = min(ag * 0.28, 0.35)
                rv = self._rng.random()
                result = rv < bluff_freq
                self._last_cbet_detail.update({'branch': 'river_bluff', 'bluff_freq': round(bluff_freq, 4),
                                                'random_val': round(rv, 4), 'decision': result})
                return result

        self._last_cbet_detail.update({'branch': 'river_check', 'decision': False})
        return False

    def should_donk_bet(
        self,
        equity: float,
        board: BoardTexture,
        street: str,
        is_ip: bool,
        opponent_cbet_freq: float = 0.55,
    ) -> bool:
        """P7 – OOP donk bet (IP checked back on previous street).

        GTO donk bets are rare on flop (~0%). On turn they apply when:
        - IP checked flop (range is weakened), AND
        - OOP has strong hands or nut advantage on the turn card.

        Returns True only when this function should override normal cbet logic.
        """
        if is_ip:
            return False   # donk is OOP by definition
        if street == 'flop':
            return False   # flop GTO donk ≈ 0%
        if street not in ('turn', 'river'):
            return False

        # Turn donk: OOP has strong hand after IP check-back.
        # R1: opponent_cbet_freq now adjusts the donk frequency.
        # High cbet_freq → opponent's range is wide/polarised → our donk is more effective
        # Low cbet_freq → opponent has stronger condensed range → donk less often
        cbet_scale = 0.7 + 0.6 * opponent_cbet_freq   # 0.3→0.88, 0.55→1.03, 0.80→1.18
        if street == 'turn':
            if equity >= 0.65:
                # Nut-type hand on turn after IP checked flop → donk for value
                rv = self._rng.random()
                return rv < min(0.45 * cbet_scale, 0.65)
            if 0.40 <= equity < 0.65:
                # Semi-bluff donk: less frequent
                rv = self._rng.random()
                return rv < min(0.18 * cbet_scale, 0.35)
        return False

    def bet_size(
        self,
        equity: float,
        pot: float,
        board: BoardTexture,
        stack: float,
        street: str,
        big_blind: float,
        spr: float = 8.0,
        nut_advantage: float = 0.0,     # P1 – scales up sizing toward overbet
        last_bet_frac: float = 0.0,     # P5 – previous-street bet fraction
        num_opponents: int = 1,         # P15 – multiway cap: no overbet vs 2+ opponents
    ) -> float:
        """Determine bet size using action abstraction (Libratus/Pluribus approach).

        Discrete menu of pot fractions per street, mixed within tiers to prevent
        opponents from reverse-engineering hand strength from bet size.

        New in this version:
        - nut_advantage: strong nut advantage allows larger/polarised sizing (P1)
        - last_bet_frac: constrains turn/river to avoid jarring size jumps (P5)
        """
        min_bet = big_blind
        self._last_bet_detail = {}
        _p10_wet_sizing = False   # P10: set True when weak-flop wet-board path taken

        if street == 'river':
            if equity >= 0.85:
                # P1 – nut advantage boosts toward overbet
                if nut_advantage >= 0.5:
                    frac = self._rng.choices([1.0, 1.25, 1.5], weights=[0.30, 0.45, 0.25])[0]
                else:
                    frac = self._rng.choices([0.75, 1.0, 1.25], weights=[0.35, 0.45, 0.20])[0]
            elif equity >= 0.65:
                frac = self._rng.choices([0.66, 0.75, 1.0], weights=[0.30, 0.45, 0.25])[0]
            elif equity >= 0.50:
                frac = 0.50
            else:
                frac = self._rng.choices([0.50, 0.66], weights=[0.60, 0.40])[0]
            reason = f"river eq={equity:.2f}"

        elif street == 'turn':
            if equity >= 0.75:
                frac = self._rng.choices([0.66, 0.75], weights=[0.45, 0.55])[0]
            elif equity >= 0.50:
                frac = self._rng.choices([0.50, 0.66], weights=[0.55, 0.45])[0]
            else:
                frac = 0.50
            reason = f"turn eq={equity:.2f}"

            # P5 – multi-street consistency: avoid jarring size jumps
            if last_bet_frac > 0:
                if last_bet_frac <= 0.35 and frac > 0.66:
                    frac = 0.66   # flop small → turn max 2/3
                    reason += " (capped:flop_small)"
                elif last_bet_frac >= 0.66 and frac < 0.50:
                    frac = 0.50   # flop big → turn min 1/2
                    reason += " (floored:flop_big)"

        else:
            # Flop
            if equity >= 0.80:
                frac = self._rng.choices([0.66, 0.75], weights=[0.50, 0.50])[0]
            elif equity >= 0.55:
                base = board.recommended_cbet_size_fraction()
                frac = self._rng.choices(
                    [max(0.25, base - 0.15), base, min(1.0, base + 0.20)],
                    weights=[0.25, 0.50, 0.25]
                )[0]
            else:
                # P10 – wet boards: weak semi-bluff uses larger sizes to deny equity
                if board.is_wet:
                    frac = self._rng.choices([0.50, 0.66], weights=[0.60, 0.40])[0]
                    _p10_wet_sizing = True   # board texture already factored in
                else:
                    frac = self._rng.choices([0.33, 0.50], weights=[0.55, 0.45])[0]
            reason = f"flop eq={equity:.2f} wet={board.is_wet}"
            # _last_bet_frac is stored AFTER all calibrations (see below) so that
            # the next street's P5 constraint sees the actual final frac, not the raw pick.

        base_frac = frac
        # P1 – nut advantage allows larger sizing on all streets.
        # R4: gate lowered to equity >= 0.60 with a linear ramp-in from 0.60→0.65
        # so there's no abrupt cliff at 0.64 vs 0.65.
        if nut_advantage >= 0.3 and equity >= 0.60:
            eq_scale = min(1.0, (equity - 0.60) / 0.05)   # 0.0 at eq=0.60, 1.0 at eq≥0.65
            boost = 0.3 * nut_advantage * eq_scale
            frac = min(frac * (1.0 + boost), 1.55)

        # Apply value sizing multiplier (exploit adjustment vs calling stations)
        frac = min(frac * self.value_mult, 1.5)

        # Texture calibration: flush-heavy boards with non-nut hands.
        # Skip wet-board penalties when P10 already chose a larger size for the wet board.
        if not _p10_wet_sizing:
            if board.is_flush_heavy and equity < 0.88:
                frac *= 0.70
            elif board.is_wet and equity < 0.82:
                frac *= 0.85
        if spr > 12.0 and board.is_wet and equity < 0.90:
            frac *= 0.88

        frac = min(frac, 1.55)

        # P5 – re-enforce multi-street floor after texture calibration
        if last_bet_frac >= 0.66 and frac < 0.50:
            frac = 0.50

        # P15 – multiway cap: never overbet when 2+ opponents are in the pot.
        # Overbet opens fold to marginal hands; keeping sizing ≤0.80 retains more callers.
        if num_opponents > 1:
            frac = min(frac, 0.80)

        # Shallow SPR: amplify sizing for strong hands
        if spr < 5.0 and equity >= 0.72:
            if not (board.is_flush_heavy and equity < 0.90):
                frac = min(frac * 1.22, 1.55)

        # R3: store the final calibrated frac so P5 constraint on the next street uses
        # the actual bet size the opponent saw (not the raw pre-calibration pick).
        if street == 'flop':
            self._last_bet_frac = frac
            self._last_bet_street = 'flop'

        self._last_bet_detail = {
            'street': street,
            'base_frac': round(base_frac, 3),
            'final_frac': round(frac, 3),
            'reason': reason,
            'spr': round(spr, 2),
            'nut_adv': round(nut_advantage, 3),
        }
        return GTOMath.pot_fraction_bet(frac, pot, min_bet, stack)

    def should_check_raise(
        self,
        equity: float,
        board: BoardTexture,
        is_ip: bool,
    ) -> bool:
        """Decide whether to check-raise when checked to and opponent bets."""
        if is_ip:
            return False
        agv = max(min(self.aggression, 1.55), 1.0)
        if equity >= 0.75:
            return self._rng.random() < min(0.5 * agv, 1.0)
        if equity >= 0.60 and board.is_wet:
            return self._rng.random() < min(0.40 * agv, 1.0)
        return False

    def should_call(
        self,
        equity: float,
        pot_odds: float,
        spr: float,
        street: str,
        *,
        is_drawing_heavy: bool = False,
        facing_large_bet: bool = False,
        exploit_tighten_call: bool = False,
    ) -> bool:
        """方案 A：大注+低 SPR 时对「成牌主导」削减隐含赔率加成；对跟注站突然极化加注收紧跟注。"""
        bonus = GTOMath.implied_odds_bonus(spr, street)
        if facing_large_bet and not is_drawing_heavy:
            bonus = min(bonus, 0.01)
        need = pot_odds
        if exploit_tighten_call:
            need = pot_odds + 0.04
        return equity + bonus >= need

    def _raise_size(self, to_call: float, pot: float, stack: float) -> float:
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
        fold_to_cbet: Optional[float] = None,        # P3
        spr: float = 5.0,
        value_only: bool = False,
        position: str = "MP",
        is_drawing_heavy: bool = False,
        facing_large_bet: bool = False,
        exploit_tighten_call: bool = False,
        opponent_af: float = 1.5,                   # P8
        nut_advantage: float = 0.0,                 # P1
        is_delayed_cbet: bool = False,              # P6
        opponent_checked_back: bool = False,        # P9
        last_bet_frac: float = 0.0,                 # P5
    ) -> Tuple[str, float]:
        """Main postflop decision function.

        Returns (action, amount): action in 'fold', 'check', 'call', 'raise'

        At the start, generates a fresh decision seed (stored in _last_decision_seed)
        so every random branch can be reproduced by re-seeding with that value.
        """
        # P14 – seed RNG at start of each decision for reproducibility
        self._new_decision_seed()

        texture = BoardTexture(board)
        pot_odds = to_call / (pot + to_call) if to_call > 0 else 0.0

        if facing_bet:
            raise_ag = max(min(self.aggression, 1.55), 1.0)

            # Passive opponent premium: AF < 1.0 means their bets/raises represent
            # a much stronger range than usual — raise our re-raise equity bar accordingly.
            # opp_raise_premium: 0 when AF >= 1.5, up to +0.15 when AF = 0.
            opp_raise_premium = max(0.0, (1.0 - opponent_af) / 1.0) * 0.15
            # value_only context (whale) betting into us is an even stronger signal
            if value_only:
                opp_raise_premium = min(opp_raise_premium + 0.05, 0.20)

            if to_call >= stack:
                need = pot_odds + (0.04 if exploit_tighten_call and not is_drawing_heavy else 0.0)
                if equity >= need:
                    return ('call', to_call)
                return ('fold', 0.0)

            # Nuts-level all-in raise: threshold lifted by opp_raise_premium
            if street in ('turn', 'river') and equity >= (0.90 + opp_raise_premium):
                raise_size = self._raise_size(to_call, pot, stack)
                return ('raise', raise_size)

            # Tiny bet raise: threshold lifted
            if pot_odds <= 0.08 and equity >= (0.68 + opp_raise_premium):
                freq = min(0.90, 0.82 * self.aggression)
                if self._rng.random() < freq:
                    raise_size = self._raise_size(to_call, pot, stack)
                    return ('raise', raise_size)

            # IP value raise: threshold lifted
            if is_ip and equity >= (0.75 + opp_raise_premium) and to_call < stack * 0.8:
                raise_prob = 0.40 if equity >= 0.85 else 0.22
                raise_prob *= raise_ag
                if self._rng.random() < raise_prob:
                    raise_size = self._raise_size(to_call, pot, stack)
                    return ('raise', raise_size)

            # OOP check-raise: threshold lifted — passive opponents almost never bluff,
            # so their bet is worth more respect; only check-raise with near-nuts.
            cr_equity_floor = 0.75 + opp_raise_premium
            if not is_ip and equity >= cr_equity_floor and self.should_check_raise(equity, texture, is_ip):
                raise_size = self._raise_size(to_call, pot, stack)
                return ('raise', raise_size)

            if self.should_call(
                equity, pot_odds, spr, street,
                is_drawing_heavy=is_drawing_heavy,
                facing_large_bet=facing_large_bet,
                exploit_tighten_call=exploit_tighten_call,
            ):
                return ('call', to_call)
            return ('fold', 0.0)

        else:
            # P7 – check for donk bet opportunity first (OOP only)
            if not is_ip and opponent_checked_back and street in ('turn',):
                if self.should_donk_bet(equity, texture, street, is_ip):
                    amount = self.bet_size(
                        equity, pot, texture, stack, street, big_blind, spr=spr,
                        nut_advantage=nut_advantage, last_bet_frac=last_bet_frac,
                        num_opponents=num_opponents,
                    )
                    return ('raise', amount)

            if self.should_cbet(
                equity, texture, is_ip, street, num_opponents,
                opponent_fold_rate,
                fold_to_cbet=fold_to_cbet,
                value_only=value_only,
                position=position,
                opponent_af=opponent_af,
                nut_advantage=nut_advantage,
                is_delayed_cbet=is_delayed_cbet,
                opponent_checked_back=opponent_checked_back,
            ):
                amount = self.bet_size(
                    equity, pot, texture, stack, street, big_blind, spr=spr,
                    nut_advantage=nut_advantage, last_bet_frac=last_bet_frac,
                    num_opponents=num_opponents,
                )
                return ('raise', amount)
            return ('check', 0.0)
