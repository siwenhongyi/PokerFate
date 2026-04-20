"""Opponent hand-range estimation via Bayesian compression.

理论依据
--------
Libratus (Brown & Sandholm, CMU 2017)
  在每次实时子博弈求解前，维护对每位对手1326种起手牌组合的后验概率分布。
  每个行动（下注/加注/过牌/跟注）都以GTO行动频率作为先验，乘以似然更新分布。

Pluribus (Brown & Sandholm, 2019)
  蓝图策略通过MCCFR学习每个信息集的行动频率，实时搜索时以此作为范围先验，
  然后用深度受限的求解更新对手范围。

简化实现
--------
全量1326手组合追踪在实时决策中开销过大。
本模块用一个标量"范围分数(range_fraction)"代替完整分布：
  - range_fraction = 1.0 → 对手可能持有任意手牌（纯随机）
  - range_fraction = 0.10 → 对手范围已压缩至全部手牌的最强10%

每个行动对范围产生乘法压缩，系数来自GTO求解器研究中的典型下注频率（经宽池调优略放宽）：
  - 下注/加注 — 按街见下方 _ACTION_COMPRESSION_RAISE
  - 跟注     ~0.76 — 跟注范围更宽（包含跟注摸牌和中强度手牌）
  - 过牌     ~0.92 — 过牌范围信息量较少（含慢打和弱手）

胜率折扣
--------
若对手持有全部手牌中最强X%的组合，我们对随机手的MC胜率会系统性高估。
折扣曲线通过以下校准点进行分段线性插值（参考PioSolver研究数据；中段与低端略抬高以减少对宽池的过弃）：

  range_fraction | equity_discount
  1.00           | 1.00
  0.70           | 0.95
  0.50           | 0.89
  0.30           | 0.81
  0.15           | 0.71
  0.08           | 0.59
  0.04           | 0.51
  0.02           | 0.44

示例（与当前系数一致，自 1.0 起三街连续 raise）：
  range_fraction = 1.0 * 0.58 * 0.50 * 0.42 ≈ 0.122 → equity_discount ≈ 0.66（插值）
  raw_equity = 0.41 → effective_equity ≈ 0.27
  再经河牌加注：rf ≈ 0.122 * 0.42 ≈ 0.051 → discount 更低，更易低于底池赔率而弃牌
"""

from __future__ import annotations
import json
import os
from typing import Dict, List

from pokerfate.core.card import Card as _Card
from pokerfate.core.equity import EquityCalculator


# ---------------------------------------------------------------------------
# Showdown 手牌强度估算
# ---------------------------------------------------------------------------
# rank char → 0-based index (2=0 … A=12)
_RANK_TO_IDX: Dict[str, int] = {
    '2': 0, '3': 1, '4': 2, '5': 3, '6': 4, '7': 5, '8': 6,
    '9': 7, 'T': 8, 'J': 9, 'Q': 10, 'K': 11, 'A': 12,
}


def _hand_strength_pct(cards) -> float:
    """将两张底牌转换为 0-1 强度分位值（1.0=AA，~0.36=72o）。

    仅用于翻牌前（preflop）强度评估。翻牌后请用 _hand_equity_postflop。

    适用于 Card 对象或形如 "As"/"Td" 的字符串。
    数学推导：
      - 对子：score = 156 + rank*2（范围 156-180，高于所有非对子）
      - 非对子：score = hi*13 + lo + 3(如果同花)（最大 170=AKs）
      - 归一化至 [0, 1]，分母 180（AA 得分上限）
    """
    if not cards or len(cards) < 2:
        return 0.5
    c1, c2 = str(cards[0]), str(cards[1])
    r1 = _RANK_TO_IDX.get(c1[0].upper(), 6)
    r2 = _RANK_TO_IDX.get(c2[0].upper(), 6)
    suited = len(c1) > 1 and len(c2) > 1 and c1[1].lower() == c2[1].lower()
    is_pair = r1 == r2
    hi, lo = max(r1, r2), min(r1, r2)
    if is_pair:
        score = 156 + hi * 2
    else:
        score = hi * 13 + lo + (3 if suited else 0)
    return min(1.0, score / 180.0)


def _hand_equity_postflop(cards, board, n_iters: int = 300) -> float:
    """翻牌后实际手牌强度：底牌 + 公牌条件下，相对随机对手的 MC 胜率（0-1）。

    比翻牌前底牌排名更准确：
      - 37o 打出葫芦 → ~0.97（而非底牌排名的 0.24）
      - AK 翻牌未中高牌 → ~0.55（而非 0.93）
      - T9s 有开口顺子摸牌 → ~0.55（实际权益，含摸牌出路）
    """
    def _to_card(c):
        return _Card.from_str(str(c)) if not hasattr(c, 'rank') else c

    hole = [_to_card(c) for c in cards[:2]]
    board_cards = [_to_card(c) for c in board]
    return EquityCalculator().calculate(hole, board_cards, 1, iterations=n_iters)


# ---------------------------------------------------------------------------
# 行动压缩系数（按街道区分，基于GTO下注频率研究）
# ---------------------------------------------------------------------------
# raise 翻前压缩（更新 preflop_rf）：
#   preflop：GTO 开牌约 15-20%，3-bet 约 5-10%，系数 ~0.33
# raise 翻后压缩（更新 postflop_rf，在翻前范围内进一步裁切）：
#   flop：c-bet 代表约 50% 的翻前范围，系数 0.50
#   turn：第二街连续下注代表更强范围，系数 0.45
#   river：河牌高度极化（强价值 + 纯诈唬），系数 0.40
# 来源：Bayes' Bluff (Alberta 2005)；GTO Wizard Range Morphology；Upswing Poker
_ACTION_COMPRESSION_RAISE_PREFLOP: float = 0.33

_ACTION_COMPRESSION_RAISE_POSTFLOP: Dict[str, float] = {
    "flop":  0.50,
    "turn":  0.45,
    "river": 0.40,
}

_ACTION_COMPRESSION: Dict[str, float] = {
    "call":  0.76,   # 跟注：宽但封顶（call 范围不含顶端强手），业界参考值 45-76%
    "check": 1.0,    # 过牌：不压缩。强手可慢打、弱手可过牌、免费看牌更是全范围 check，
                     # 过牌几乎不携带范围信息，任何压缩均无 GTO 依据。
    "fold":  0.0,    # 弃牌：不再追踪（对手已出局）
}

# ---------------------------------------------------------------------------
# PFR/VPIP 加权 + 诈唬例外：根据玩家风格调整翻后 raise 的 postflop_rf 压缩系数
# ---------------------------------------------------------------------------
# 核心原则：加注是强信号，无论任何玩家类型，默认强力压缩。
#
#   - 被动玩家（whale/跟注站）极少加注，一旦加注几乎是顶端价值 → 压缩最强
#   - GTO 玩家 raise 含价值 + 诈唬，频率较高 → 标准压缩
#   - 唯一例外：已知高频诈唬玩家，raise 可信度低 → 放宽到 GTO 基准
#
# 公式：adjusted = gto_factor × (pfr_vpip / R_ref)
#   pfr_vpip_ratio 越低（跟注站），adjusted 越小（压缩更快，range 更窄）
#   pfr_vpip_ratio 越高（Nit/GTO），adjusted ≈ gto_factor（标准压缩）
#
# 效果示例（gto_factor=0.50）：
#   Whale  PFR/VPIP=0.13 → 0.50×(0.13/0.75)=0.087 → clip 到 0.20（极紧，强手信号）
#   GTO    PFR/VPIP=0.75 → 0.50×(0.75/0.75)=0.50（无调整）
#   Nit    PFR/VPIP=0.87 → 0.50×(0.87/0.75)=0.58 → clip 到 0.58
#   已知诈唬者（bluff_win_rate>40%）→ factor≥0.50（不额外压缩）
#
# 边界：
#   lo = gto_factor × 0.40（最多比 GTO 再压紧 60%，避免极端低估）
#   hi = gto_factor × 1.20（最多比 GTO 宽 20%，防止无效信号）
_PFR_VPIP_R_REF: float = 0.75


def _adjusted_postflop_raise_factor(gto_factor: float, pfr_vpip_ratio: float) -> float:
    """样本不足时，用 PFR/VPIP 比值调整 GTO 先验压缩系数（启发式路）。

    仅在 showdown 样本不足（< 5 次）时使用。
    有足够 showdown 数据时，调用方直接用 showdown_calibrator 的结果，不走此函数。

    核心：加注是强信号，被动玩家（低 PFR/VPIP）一旦加注 range 极窄，压缩更强。
    诈唬例外由调用方在拿到 factor 后统一处理（两条路共用同一逻辑）。
    """
    ratio = max(0.01, min(1.0, pfr_vpip_ratio))
    raw = gto_factor * (ratio / _PFR_VPIP_R_REF)
    lo = gto_factor * 0.40   # 最多比 GTO 再压紧 60%
    hi = gto_factor * 1.20   # 最多比 GTO 放宽 20%
    return max(lo, min(hi, raw))

# ---------------------------------------------------------------------------
# 胜率折扣校准表（分段线性插值）
# ---------------------------------------------------------------------------
# 每个元素：(range_fraction, equity_discount)
# 从宽到窄排列
_DISCOUNT_CALIBRATION = [
    (1.00, 1.00),
    (0.70, 0.95),
    (0.50, 0.89),
    (0.30, 0.81),
    (0.15, 0.71),
    (0.08, 0.59),
    (0.04, 0.51),
    (0.02, 0.44),
]


def _equity_discount(range_fraction: float) -> float:
    """将范围分数映射到胜率折扣因子（分段线性插值）。"""
    rf = max(0.02, min(1.00, range_fraction))
    for i in range(len(_DISCOUNT_CALIBRATION) - 1):
        r_hi, d_hi = _DISCOUNT_CALIBRATION[i]
        r_lo, d_lo = _DISCOUNT_CALIBRATION[i + 1]
        if rf >= r_lo:
            # 在 [r_lo, r_hi] 区间内线性插值
            t = (rf - r_lo) / (r_hi - r_lo)
            return d_lo + t * (d_hi - d_lo)
    return _DISCOUNT_CALIBRATION[-1][1]


# ---------------------------------------------------------------------------
# ShowdownCalibrator
# ---------------------------------------------------------------------------

class ShowdownCalibrator:
    """从 showdown 底牌数据中学习对手的实际 raise 范围压缩系数。

    核心思想
    --------
    如果一个人打 all-in 时 showdown 的平均手牌强度分位值为 P，
    则他的 raise range 约为全部手牌的 X = 2*(1-P) 比例：
      - maniac（永远 all-in）→ 平均 P≈0.50 → X≈1.0（全范围，不压缩）
      - nit（只有 AA/KK raise）→ 平均 P≈0.95 → X≈0.10（极紧范围）
      - GTO 玩家 preflop raise  → 平均 P≈0.835 → X≈0.33（与固定系数吻合）

    样本不足（< _MIN_SAMPLES）时退回 GTO 先验，与原行为完全一致。
    """

    _MIN_SAMPLES = 5

    def __init__(self) -> None:
        # 玩家名字 → {(street, action): [hand_strength_pct, ...]}
        # 用名字而非座位号，跨 session 座位换人时数据不会挂错人
        self._data: Dict[str, Dict[tuple, list]] = {}

    def record(self, name: str, action_sequence: list, strength_by_street: Dict[str, float]) -> None:
        """记录一次 showdown 观察。

        Parameters
        ----------
        name : str
            玩家名字（跨 session 稳定标识）。
        action_sequence : list of (street, action) tuples
        strength_by_street : dict
            {street: hand_strength} — 各街道下注时的实际手牌强度（0-1）。
            preflop 用底牌预选强度，翻牌后用 equity vs random。
        """
        player_data = self._data.setdefault(name, {})
        for street, action in action_sequence:
            pct = strength_by_street.get(street, 0.5)
            player_data.setdefault((street, action), []).append(pct)

    def calibrated_factor(
        self, name: str, action: str, street: str, gto_default: float
    ) -> float:
        """返回校准后的压缩系数；样本不足时返回 GTO 先验。"""
        samples = self._data.get(name, {}).get((street, action), [])
        if len(samples) < self._MIN_SAMPLES:
            return gto_default
        mean_strength = sum(samples) / len(samples)
        return max(0.05, min(1.0, 2.0 * (1.0 - mean_strength)))

    def sample_count(self, name: str, action: str, street: str) -> int:
        """返回已积累的样本数量。"""
        return len(self._data.get(name, {}).get((street, action), []))

    def to_dict(self) -> dict:
        """序列化为 JSON 兼容字典（key 为玩家名字）。"""
        return {
            name: {
                f"{s}:{a}": samples
                for (s, a), samples in pdata.items()
            }
            for name, pdata in self._data.items()
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ShowdownCalibrator":
        """从序列化字典恢复（key 为玩家名字）。"""
        cal = cls()
        for name, pdata in data.items():
            cal._data[name] = {
                tuple(key.split(":", 1)): samples
                for key, samples in pdata.items()
            }
        return cal


# ---------------------------------------------------------------------------
# HandRangeEstimator
# ---------------------------------------------------------------------------

class HandRangeEstimator:
    """逐手追踪对手范围，并提供胜率折扣因子。

    使用方法
    --------
    estimator = HandRangeEstimator()

    # 每手开始时重置（先验用对手历史VPIP或默认值）
    estimator.reset_hand(player_id=1, prior_range=0.35)

    # 观察到对手行动后更新
    estimator.observe_action(player_id=1, action='raise', street='flop')

    # 在决策点获取有效胜率
    raw_equity = 0.41   # MC胜率（对随机手）
    eff_equity = estimator.effective_equity(player_id=1, raw_equity=raw_equity)
    """

    def __init__(self) -> None:
        # 两阶段 range 追踪：
        #   _preflop_rf：翻前行动压缩（仅由 preflop raise/call/check 更新）
        #   _postflop_rf：翻后行动在翻前范围内的二次裁切（由 flop/turn/river 行动更新）
        # 组合 rf = preflop_rf * postflop_rf，用于胜率折扣计算
        self._preflop_rf: Dict[int, float] = {}
        self._postflop_rf: Dict[int, float] = {}
        # 向后兼容：get_range_fraction 返回组合 rf
        self._range: Dict[int, float] = {}
        # 每位对手的先验范围（VPIP），作为 call/check 压缩的下界
        self._prior: Dict[int, float] = {}
        # 本手中对手下注/加注的街数（用于决策原因说明）
        self._streets_bet: Dict[int, int] = {}
        # 追踪本手是否已在某街行动（避免同一街重复计数）
        self._street_acted: Dict[int, set] = {}
        # 本手行动序列记录（用于 showdown 校准）
        self._hand_actions: Dict[int, list] = {}
        # player_id → player name（每手 reset_hand 时填充，用于 showdown 校准器的 name key 查询）
        self._pid_to_name: Dict[int, str] = {}
        # player_id → PFR/VPIP 比值（用于调整翻后 raise 压缩系数）
        self._pfr_vpip: Dict[int, float] = {}
        # 诈唬指标（用于 raise 压缩的诈唬例外判断）
        self._bluff_wr: Dict[int, float] = {}       # bluff_win_rate
        self._bet_win_n: Dict[int, int] = {}         # bet_win_count（样本数）
        self._river_bf: Dict[int, float] = {}        # river_bet_frequency
        self._river_bf_n: Dict[int, int] = {}        # river_bf 样本数（bets+checks）
        # Showdown 联合建模校准器
        self.showdown_calibrator: ShowdownCalibrator = ShowdownCalibrator()

    def reset_hand(self, player_id: int, prior_range: float = 0.35, name: str = "",
                   pfr_vpip_ratio: float = _PFR_VPIP_R_REF,
                   bluff_win_rate: float = 0.0, bet_win_samples: int = 0,
                   river_bet_freq: float = 0.0, river_bf_samples: int = 0) -> None:
        """手牌开始时重置状态。

        Parameters
        ----------
        player_id : int
        prior_range : float
            先验范围分数，通常用对手历史VPIP。
            若未知，默认0.35（典型6人桌玩家）。
        name : str
            玩家名字，用于 showdown 校准器的跨 session 查询（name 为 key）。
        bluff_win_rate : float
            对手 bluff_win_rate（弱牌赢的比率）。> 0.40 时视为诈唬玩家。
        bet_win_samples : int
            bluff_win_rate 的样本数（bet_win_count）。< 5 时不使用。
        river_bet_freq : float
            对手河牌下注频率。> 0.55 时视为诈唬玩家。
        river_bf_samples : int
            river_bet_freq 的样本数。< 8 时不使用。
        """
        self._preflop_rf[player_id] = max(0.05, min(1.0, prior_range))
        self._postflop_rf[player_id] = 1.0   # 翻后尚无行动，postflop_rf 从 1.0 开始
        self._range[player_id] = self._preflop_rf[player_id]  # 组合 rf（初始等于翻前 rf）
        self._prior[player_id] = max(0.05, min(1.0, prior_range))
        self._pfr_vpip[player_id] = max(0.01, min(1.0, pfr_vpip_ratio))
        self._bluff_wr[player_id] = max(0.0, min(1.0, bluff_win_rate))
        self._bet_win_n[player_id] = bet_win_samples
        self._river_bf[player_id] = max(0.0, min(1.0, river_bet_freq))
        self._river_bf_n[player_id] = river_bf_samples
        self._streets_bet[player_id] = 0
        self._street_acted[player_id] = set()
        self._hand_actions[player_id] = []
        if name:
            self._pid_to_name[player_id] = name

    def observe_action(self, player_id: int, action: str, street: str) -> None:
        """观察到对手行动，更新范围估算。

        Parameters
        ----------
        player_id : int
        action : str
            'raise', 'call', 'check', 'fold'
        street : str
            'preflop', 'flop', 'turn', 'river'
        """
        if player_id not in self._preflop_rf:
            self.reset_hand(player_id)

        is_preflop = (street == "preflop")
        name = self._pid_to_name.get(player_id, str(player_id))

        if action == "raise":
            if is_preflop:
                # 翻前加注：更新 preflop_rf
                gto_factor = _ACTION_COMPRESSION_RAISE_PREFLOP
                factor = self.showdown_calibrator.calibrated_factor(
                    name, action, street, gto_factor
                )
                new_pf = max(0.02, self._preflop_rf[player_id] * factor)
                self._preflop_rf[player_id] = new_pf
            else:
                # 翻后加注：在翻前范围内二次裁切，更新 postflop_rf
                gto_factor = _ACTION_COMPRESSION_RAISE_POSTFLOP.get(street, 0.45)
                # Showdown 实测数据 vs PFR/VPIP 启发式：二选一，不叠加
                #   有足够 showdown 样本 → 直接用实测（更准，不再叠加 PFR/VPIP）
                #   样本不足            → 用 PFR/VPIP 调整 GTO 先验（启发式）
                # 两条路最后都叠加诈唬例外（已知诈唬者放宽压缩）
                sd_samples = self.showdown_calibrator.sample_count(name, action, street)
                if sd_samples >= ShowdownCalibrator._MIN_SAMPLES:
                    # 实测路：直接从 showdown 得到 factor，不再乘 PFR/VPIP
                    factor = self.showdown_calibrator.calibrated_factor(
                        name, action, street, gto_factor
                    )
                else:
                    # 启发式路：PFR/VPIP 调整 GTO 先验
                    pfr_vpip = self._pfr_vpip.get(player_id, _PFR_VPIP_R_REF)
                    factor = _adjusted_postflop_raise_factor(gto_factor, pfr_vpip)
                # 诈唬例外：两条路都适用（已知诈唬者放宽到 GTO 基准）
                is_bluffer = (
                    (self._bet_win_n.get(player_id, 0) >= 5
                     and self._bluff_wr.get(player_id, 0.0) > 0.40) or
                    (self._river_bf_n.get(player_id, 0) >= 8
                     and self._river_bf.get(player_id, 0.0) > 0.55)
                )
                if is_bluffer:
                    factor = max(factor, gto_factor)
                new_po = max(0.02, self._postflop_rf[player_id] * factor)
                self._postflop_rf[player_id] = new_po
        else:
            factor = _ACTION_COMPRESSION.get(action, 1.0)
            if factor == 0.0:
                # 弃牌：不更新（对手已出局，无需追踪）
                self._hand_actions.setdefault(player_id, []).append((street, action))
                return

            # 翻后 call：用 showdown 校准数据替换固定压缩系数。
            # 校准逻辑：calibrated_factor = 2*(1 - mean_call_strength)
            #   宽范围跟注站（call 均强度 ~0.35）→ factor ≈ 1.30 → 压缩更少，postflop_rf 保持更高
            #   紧手 call（call 均强度 ~0.65）    → factor ≈ 0.70 → 压缩更多，postflop_rf 更低
            # check 和 preflop call 继续使用固定值（check=1.0 无压缩，preflop call 由 VPIP floor 保护）
            if not is_preflop and action == 'call':
                gto_factor = _ACTION_COMPRESSION['call']   # 0.76（GTO 先验）
                factor = self.showdown_calibrator.calibrated_factor(
                    name, action, street, gto_factor
                )

            if is_preflop:
                new_pf = max(0.02, self._preflop_rf[player_id] * factor)
                # VPIP 下界：跟注站 call 不应被压缩到与 VPIP 严重脱节的程度
                if action != "raise":
                    vpip_floor = self._prior.get(player_id, 0.35) * 0.65
                    new_pf = max(new_pf, vpip_floor)
                self._preflop_rf[player_id] = new_pf
            else:
                new_po = max(0.05, self._postflop_rf[player_id] * factor)
                # 翻后 call/check：保留至少 40% 的翻后范围（防止跟注站被误判为紧手）
                new_po = max(new_po, 0.40)
                self._postflop_rf[player_id] = new_po

        # 同步组合 rf（用于胜率折扣计算）
        self._range[player_id] = self._preflop_rf[player_id] * self._postflop_rf[player_id]

        # 记录行动序列，供本手结束时的 showdown 校准使用
        self._hand_actions.setdefault(player_id, []).append((street, action))

        # 统计加注街数（同一街只计一次）
        if action == "raise":
            acted = self._street_acted.setdefault(player_id, set())
            if street not in acted:
                self._streets_bet[player_id] = self._streets_bet.get(player_id, 0) + 1
                acted.add(street)

    def get_range_fraction(self, player_id: int) -> float:
        """返回对手当前组合范围分数 preflop_rf * postflop_rf [0.02, 1.0]。

        若该对手在本手中从未被追踪（reset_hand 未调用），返回 1.0——
        即"无信息，使用原始MC胜率"，与 Libratus 均匀先验一致。
        """
        return self._range.get(player_id, 1.0)

    def get_discount(self, player_id: int) -> float:
        """返回胜率折扣因子 [0.44, 1.0]。

        数值越低 = 对手范围越强 = 我们的实际胜率越低于MC估算值。
        未追踪的对手返回 1.0（不施加折扣）。
        """
        return _equity_discount(self.get_range_fraction(player_id))

    def effective_equity(self, player_id: int, raw_equity: float) -> float:
        """返回对手范围压缩后的有效胜率。

        effective_equity = raw_equity * discount_factor

        这是Libratus实时子博弈求解中"条件于对手范围的胜率期望值"的近似。
        """
        return raw_equity * self.get_discount(player_id)

    def streets_bet(self, player_id: int) -> int:
        """本手中对手已在几条街上主动下注/加注。"""
        return self._streets_bet.get(player_id, 0)

    def worst_discount(self, player_ids) -> float:
        """返回多位对手中最保守的折扣因子（最小值 = 范围最强的对手）。

        在多路底池中，我们面对的是所有仍在局中对手中范围最强的一位。
        """
        if not player_ids:
            return 1.0
        return min(self.get_discount(pid) for pid in player_ids)

    def has_calibration(self, player_id: int) -> bool:
        """该对手是否已有足够样本（≥5）影响任意行动的压缩系数。"""
        name = self._pid_to_name.get(player_id, str(player_id))
        player_data = self.showdown_calibrator._data.get(name, {})
        return any(
            len(samples) >= ShowdownCalibrator._MIN_SAMPLES
            for samples in player_data.values()
        )

    def observe_showdown(self, player_id: int, cards, name: str = "", board=None) -> None:
        """在 showdown 时记录对手底牌，用于校准该对手的范围压缩系数。

        Parameters
        ----------
        player_id : int
        cards : list of Card or str
            对手亮出的底牌（至少两张）。
        name : str
            玩家名字；若为空则从 _pid_to_name 查找，再 fallback 到 str(player_id)。
        board : list of Card or str, optional
            本手最终公牌。用于计算翻牌后各街道的实际手牌强度（equity vs random），
            比单纯用底牌预选强度更准确（37o 打葫芦 raise 应记为强而非弱）。
        """
        action_sequence = self._hand_actions.get(player_id, [])
        if not action_sequence:
            return
        if len(cards) < 2:
            return
        resolved_name = name or self._pid_to_name.get(player_id, str(player_id))
        board = list(board) if board else []

        # 按街道划分公牌，计算各街道下注时的实际手牌强度
        board_by_street = {
            'preflop': [],
            'flop':    board[:3] if len(board) >= 3 else [],
            'turn':    board[:4] if len(board) >= 4 else [],
            'river':   board[:5] if len(board) >= 5 else [],
        }
        # 同时计算 raise 和 call 街道的手牌强度，两者都需要校准：
        #   raise：价值/诈唬的强度分布 → 压缩系数
        #   call：跟注范围宽窄 → 跟注压缩系数（宽手跟注站 factor>0.76，紧手 factor<0.76）
        # preflop call 不计算（由 VPIP floor 保护，无需额外校准）
        streets_with_action = {s for s, a in action_sequence
                                if a in ('raise', 'call') and (a != 'call' or s != 'preflop')}
        strength_by_street: Dict[str, float] = {}
        for street in streets_with_action:
            b = board_by_street.get(street, [])
            if not b:
                # preflop raise：用底牌预选强度（快速、确定性）
                strength_by_street[street] = _hand_strength_pct(cards)
            else:
                # 翻牌后：用实际 equity，反映成牌/摸牌/听牌的真实强度
                strength_by_street[street] = _hand_equity_postflop(cards, b)

        self.showdown_calibrator.record(resolved_name, action_sequence, strength_by_street)
        return strength_by_street

    def save_calibrator(self, filepath: str) -> None:
        """将 showdown 校准数据持久化到 JSON 文件。"""
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(self.showdown_calibrator.to_dict(), f, indent=2)

    def load_calibrator(self, filepath: str) -> None:
        """从 JSON 文件加载 showdown 校准数据（文件不存在时静默跳过）。"""
        if not os.path.exists(filepath):
            return
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read().strip()
        if not content:
            return
        try:
            self.showdown_calibrator = ShowdownCalibrator.from_dict(json.loads(content))
        except (json.JSONDecodeError, KeyError, ValueError):
            pass  # 损坏的文件，保持空校准器
