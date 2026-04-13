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
        self.max_suit_count = max(suit_cnt.values(), default=0)
        self.flush_draw = self.max_suit_count >= 2
        self.monotone = self.max_suit_count >= 3
        # 转牌起可能出现 4 张同花公牌，坚果常为同花
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
        value_only: bool = False,
        position: str = "MP",
    ) -> bool:
        """Decide whether to make a continuation bet.

        Improvements based on Pluribus/Libratus research:
        - River: delegate to _should_river_bet (no semi-bluffs — no draws to realize)
        - Value threshold lowered 0.70 → 0.65 (capture thin value hands like AQ/top-pair)
        - Multiway (3+ opponents): semi-bluff requires equity >= 0.45 floor
          (Pluribus: fold equity drops sharply in multi-way pots)
        - Late position (BTN/CO): slightly higher bluff/value frequency; early
          position slightly tighter.
        - Flop/turn monster (equity >= 0.90): multiway always bet; HU ~80%×ag, wet +10pp,
          OOP +8pp vs IP.
        """
        ag = self.aggression
        if position in ("BTN", "CO"):
            ag *= 1.07
        elif position in ("UTG", "UTG+1", "UTG+2", "LJ"):
            ag *= 0.93
        ag = min(ag, 1.55)
        # 低 exploit aggression 主要压半诈唬/边缘；价值线不低于 1.0（方案 C）
        ag_value = max(ag, 1.0)
        ag_value = min(ag_value, 1.55)

        # ── 纯价值模式（对跟注站）：禁止诈唬，但「薄价值/保护」与「空气」分开（方案 B）──
        if value_only:
            if street == 'river':
                return equity >= 0.60
            # 单挑干燥面：允许略薄的保护与价值（仍无半诈唬分支）
            if num_opponents <= 1 and board.is_dry:
                return equity >= 0.50
            return equity >= 0.55

        # ── River: separate logic (no semi-bluffs, pure value or fold-equity bluff) ──
        if street == 'river':
            return self._should_river_bet(equity, is_ip, num_opponents, opponent_fold_rate, ag)

        # Monster hand (flop/turn): 胜率已极高；多人底池不再慢打（免费牌代价大）。
        if equity >= 0.90:
            if num_opponents >= 2:
                return True
            # 单挑：~80%×ag_value；湿润面 +10%；无位置(OOP)再 +8%（少先 check 送免费牌）。
            p_bet = min(1.0, 0.80 * ag_value)
            if not board.is_dry:
                p_bet = min(1.0, p_bet + 0.10)
            if not is_ip:
                p_bet = min(1.0, p_bet + 0.08)
            return random.random() < p_bet

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
            return random.random() < (freq * ag_value)

        # Very weak hand (no equity, no fold equity): give up
        if equity < 0.20 and opponent_fold_rate < 0.40:
            return False

        # Multiway semi-bluff floor: need meaningful equity to barrel into multiple opponents
        # (Pluribus insight: EV of bluffing drops sharply as player count increases)
        if num_opponents >= 2 and equity < 0.45:
            return False

        # Semi-bluff zone: bet with fold equity（仍用 ag，压制诈唬频率）
        if 0.30 <= equity <= 0.60:
            freq = 0.65 if board.is_dry else 0.45
            freq *= ag
            if not is_ip:
                freq *= 0.85
            if num_opponents > 1:
                freq *= (0.6 ** (num_opponents - 1))
            return random.random() < freq

        # Thin value / air: bet based on fold equity only
        freq_base = 0.55 if board.is_dry else 0.35
        freq_base *= ag
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
        ag: float,
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
            # OOP river: no second chance after check — bet more aggressively for thin value
            bet_freq = 0.92 if not is_ip else 0.80
            return random.random() < (bet_freq * ag)
        # Thin value / merge — only heads-up
        if equity >= 0.50:
            if num_opponents > 1:
                return False
            return random.random() < (0.45 * ag)

        # Pure bluff: need genuine fold equity
        # GTO break-even for 66% pot bluff ≈ 0.40 fold rate
        if equity < 0.35 and num_opponents == 1:
            if opponent_fold_rate > 0.40:
                bluff_freq = min(ag * 0.28, 0.35)
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
        spr: float = 8.0,
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

        # 协调面控池：单调/四张花上「强但非坚果」缩小下注比例，减少第二大强牌打光。
        if board.is_flush_heavy and equity < 0.88:
            frac *= 0.70
        elif board.is_wet and equity < 0.82:
            frac *= 0.85
        # 深码 + 湿面再收一档（仍非近坚果时）
        if spr > 12.0 and board.is_wet and equity < 0.90:
            frac *= 0.88

        frac = min(frac, 1.55)

        # 浅 SPR 加注码：易打光；在单调/四张花且胜率未近坚果时不放大，避免推叠撞同花。
        if spr < 5.0 and equity >= 0.72:
            if not (board.is_flush_heavy and equity < 0.90):
                frac = min(frac * 1.22, 1.55)

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
        agv = max(min(self.aggression, 1.55), 1.0)
        if equity >= 0.75:
            return random.random() < min(0.5 * agv, 1.0)
        if equity >= 0.60 and board.is_wet:
            return random.random() < min(0.40 * agv, 1.0)
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
        raw_equity: float = None,
        value_only: bool = False,
        position: str = "MP",
        is_drawing_heavy: bool = False,
        facing_large_bet: bool = False,
        exploit_tighten_call: bool = False,
    ) -> Tuple[str, float]:
        """Main postflop decision function.

        Returns (action, amount): action in 'fold', 'check', 'call', 'raise'

        equity:     range equity（对手估算范围下的胜率），全程统一使用。
                    当 range 信息不足时由调用方 fallback 到 EQR，此时 equity
                    仍是当前最佳估计值，决策逻辑无需区分来源。
        raw_equity: 仅用于日志/推理说明，不参与任何决策。
        """
        texture = BoardTexture(board)
        pot_odds = to_call / (pot + to_call) if to_call > 0 else 0.0

        if facing_bet:
            raise_ag = max(min(self.aggression, 1.55), 1.0)
            if to_call >= stack:
                # All-in：对「纯价值剥削 + 大注极化」收紧（方案 A）
                need = pot_odds + (0.04 if exploit_tighten_call and not is_drawing_heavy else 0.0)
                if equity >= need:
                    return ('call', to_call)
                return ('fold', 0.0)

            # 转/河面对下注、且相对对手范围胜率极高：价值加注弱优于跟注（可再榨一层），
            # 不走后面的随机「IP 价值加注 / call」。阈值 90%：碾压型成牌类局面，不单为某一手牌。
            # 仅当仍可合法加注时进入（对手未把我们套入全下 — 全下仅 call 见上分支）。
            if street in ('turn', 'river') and equity >= 0.90:
                raise_size = self._raise_size(to_call, pot, stack)
                return ('raise', raise_size)

            # 极小注（如 1k 进 5w 池）：range equity 仍强时造池拿价值
            if pot_odds <= 0.08 and equity >= 0.68:
                freq = min(0.90, 0.82 * self.aggression)
                if random.random() < freq:
                    raise_size = self._raise_size(to_call, pot, stack)
                    return ('raise', raise_size)

            # IP value raise：价值线用 raise_ag，避免低 exploit aggression 压扁加注频率（方案 C）
            if is_ip and equity >= 0.75 and to_call < stack * 0.8:
                raise_prob = 0.40 if equity >= 0.85 else 0.22
                raise_prob *= raise_ag
                if random.random() < raise_prob:
                    raise_size = self._raise_size(to_call, pot, stack)
                    return ('raise', raise_size)

            # OOP check-raise
            if not is_ip and self.should_check_raise(equity, texture, is_ip):
                raise_size = self._raise_size(to_call, pot, stack)
                return ('raise', raise_size)

            if self.should_call(
                equity,
                pot_odds,
                spr,
                street,
                is_drawing_heavy=is_drawing_heavy,
                facing_large_bet=facing_large_bet,
                exploit_tighten_call=exploit_tighten_call,
            ):
                return ('call', to_call)
            return ('fold', 0.0)

        else:
            # 主动下注：全程用 range equity。
            # range equity 已正确捕捉半诈唬价值（摸牌胜率与对手持牌无关），
            # 同时避免"vs随机强但vs对手弱"时误判为价值下注。

            if self.should_cbet(
                equity, texture, is_ip, street, num_opponents,
                opponent_fold_rate, value_only=value_only, position=position,
            ):
                amount = self.bet_size(
                    equity, pot, texture, stack, street, big_blind, spr=spr,
                )
                return ('raise', amount)
            return ('check', 0.0)
