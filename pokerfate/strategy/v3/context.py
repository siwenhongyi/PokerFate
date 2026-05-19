"""DecisionCtx — 单次决策的唯一数据入口（docs/betting-redesign/03 §3）。

所有 purpose 的 trigger 只读 ctx；新信号必须先落到这里。
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Dict, List

from pokerfate.core.card import Card


# ---------------------------------------------------------------------------
# Sub-structures
# ---------------------------------------------------------------------------


@dataclass
class BlockerSet:
    """Blocker effects hero's hand has on villain's range."""
    nut_flush_blocker: bool = False
    set_blocker: bool = False
    straight_blocker: bool = False

    def count(self) -> int:
        return int(self.nut_flush_blocker) + int(self.set_blocker) + int(self.straight_blocker)


@dataclass
class DrawProfile:
    """Hero's improvement potential on turn/flop."""
    flush_draw: bool = False
    oesd: bool = False
    gutshot: bool = False
    backdoor_flush: bool = False
    overcards: bool = False


@dataclass
class BoardSignals:
    """Texture of the community cards."""
    wetness: float = 0.0
    paired: bool = False
    monotone: bool = False
    flush_possible: bool = False
    flush_draw: bool = False
    straight_draw_heavy: bool = False
    straight_possible: bool = False
    connectedness: float = 0.0
    high_card_rank: int = 0
    # convenience flags — automatically derived from `wetness` after init
    # (can be overridden explicitly by callers if needed).
    is_dry: bool = False      # wetness < 0.35
    is_wet: bool = False      # wetness >= 0.55

    def __post_init__(self) -> None:
        # Only auto-derive when both are left at defaults.
        if not self.is_dry and not self.is_wet:
            self.is_dry = self.wetness < 0.35
            self.is_wet = self.wetness >= 0.55


@dataclass
class VillainStats:
    """Flattened opponent statistics needed by purpose triggers.

    不含 player_type / pwi 等聚合字段：决策层完全由原子连续指标驱动；
    玩家类型标签与 pwi 聚合分仅在 log 路径展示（分别由
    OpponentStats.player_type() 与 pwi() 方法直接提供）。
    """
    vpip: float = 0.0
    pfr: float = 0.0
    af: float = 1.5
    fold_to_cbet: float = 0.45
    fold_to_cbet_opps: int = 0
    fold_to_3bet: float = 0.50
    wtsd: float = 0.25
    wmsd: float = 0.50
    bluff_win_rate: float = 0.20
    bet_win_count: int = 0
    flop_afq: float = 0.45
    turn_afq: float = 0.40
    river_afq: float = 0.35
    river_fold_rate: float = 0.40
    river_bet_frequency: float = 0.35
    river_action_count: int = 0
    hands_seen: int = 0


# ---------------------------------------------------------------------------
# Main context
# ---------------------------------------------------------------------------


@dataclass
class DecisionCtx:
    """One decide() call's full input. Purposes are pure functions of this."""

    # === State ===
    street: str = 'flop'                        # 'preflop'|'flop'|'turn'|'river'
    hole_cards: List[Card] = field(default_factory=list)
    board: List[Card] = field(default_factory=list)
    position: str = 'MP'                        # canonical 10-value set
    is_ip: bool = False
    num_opponents: int = 1
    pot: float = 0.0
    to_call: float = 0.0
    # Hero's own remaining stack. Used as the absolute physical maximum.
    stack: float = 0.0
    # Effective stack against the current sizing target.  This can be much
    # smaller than hero's stack when the main opponent is short.  SPR already
    # uses this value upstream; calibrator uses it for stack-off sizing so
    # low-SPR value bets do not get compressed into tiny geometric bets.
    effective_stack: float = 0.0
    big_blind: float = 2.0
    spr: float = 8.0
    pot_odds: float = 0.0
    facing_bet: bool = False
    facing_large_bet: bool = False

    # === Hero strength ===
    hero_bucket: str = 'air'                    # nuts/strong/medium/draw/weak_draw/air
    hero_made_subtype: str = ''                 # fine-grained made-hand shape
    hero_hand_rank: str = ''                    # evaluator rank: full_house/quads/...
    hero_made_rank: int = 0
    hero_kicker_rank: int = 0
    board_pair_rank: int = 0
    pocket_pair_rank: int = 0
    equity_mc: float = 0.5                      # vs random hand
    equity_range: float = 0.5                   # vs villain bayesian range
    equity_uncertainty: float = 0.0             # equity_range 的悲观半宽 [0, 0.30]
    # ↑ 2026-04-25：tracker 经实验验证在 single-action 下有 ±15-20% 结构性偏差
    #   （见 docs/策略修复/胜率模型校正.md）。facing_bet 场景用
    #   pessimistic_eq = equity_range - equity_uncertainty 做决策，避免被
    #   偏差拖入灾难性 call。poker_bot 按 bucket_dist 熵 / vs_random 差 /
    #   polar_idx / 多人池 加权填充。
    compression: float = 1.0                    # equity_range / equity_mc
    nut_advantage: float = 0.0
    draw: DrawProfile = field(default_factory=DrawProfile)
    blockers: BlockerSet = field(default_factory=BlockerSet)

    # === Board ===
    board_sig: BoardSignals = field(default_factory=BoardSignals)

    # === Opponent / range ===
    primary_opp_id: int = -1
    villain_bucket_dist: Dict[str, float] = field(default_factory=dict)
    # River-only hero-relative showdown distribution from villain range:
    # {'win': hero beats villain, 'tie': split, 'loss': villain beats hero}.
    villain_vs_hero_dist: Dict[str, float] = field(default_factory=dict)
    villain_stats: VillainStats = field(default_factory=VillainStats)
    exploit_adj: Dict[str, object] = field(default_factory=dict)

    # === Multi-opponent summary (2026-04-24 缺陷 A 第 1 步) ===
    # 保留 villain_stats（primary opp）为 range/exploit 主路径；新增字段
    # 专门用于风险敏感决策——即使 primary 被识别为 LAG，只要桌上还坐着一个
    # 粘手被动的对手，bluff-catch / thin value 就要按后者定调。
    # 第 1 步：scalar 聚合；第 2 步才会引入 villains: List[VillainStats]。
    worst_villain_stats: VillainStats = field(default_factory=VillainStats)
    # ↑ 桌上 value_lean 最高的那个对手的完整 stats。
    #   语义："如果我 value bet 被加注，最可能是这个人加的"
    max_value_lean: float = 0.0
    # ↑ max(_value_lean(v)) over all active villains
    max_trap_lean: float = 0.0
    # ↑ max(_trap_lean(v))，用于 slow-play 风险识别
    max_bluff_lean: float = 0.0
    # ↑ max(_bluff_lean(v))
    n_sticky: int = 0
    # ↑ _value_lean ≥ 1.2 的对手数量（零/一/多三档足以）

    # === Cross-street memory ===
    my_prev_actions: Dict[str, str] = field(default_factory=dict)
    opp_prev_actions: Dict[str, str] = field(default_factory=dict)
    last_bet_frac: float = 0.0
    is_pfr: bool = False
    flop_checked_through: bool = False
    turn_checked_through: bool = False

    # === Cross-street resistance summary ===
    prev_bet_called_count: int = 0
    prev_bet_raised: bool = False
    prev_bet_was_multiway: bool = False
    prev_bet_frac: float = 0.0
    resistance_level: float = 0.0

    # === Derived convenience flags ===
    @property
    def is_delayed_cbet(self) -> bool:
        """hero PFR, 上一街 check 过，当前街尚未面对下注。"""
        if self.facing_bet or not self.is_pfr:
            return False
        prev = {'turn': 'flop', 'river': 'turn'}.get(self.street)
        if prev is None:
            return False
        return self.my_prev_actions.get(prev) == 'check'

    @property
    def opponent_checked_back(self) -> bool:
        """主 opp 在上一街（IP 身份）check 掉。"""
        prev = {'turn': 'flop', 'river': 'turn'}.get(self.street)
        if prev is None or self.facing_bet:
            return False
        return self.opp_prev_actions.get(prev) == 'check'

    # === RNG ===
    rng: random.Random = field(default_factory=random.Random)
    seed: int = 0
    decision_key: str = ''
