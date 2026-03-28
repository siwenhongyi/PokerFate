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
from typing import Dict


# ---------------------------------------------------------------------------
# 行动压缩系数（按街道区分，基于GTO下注频率研究）
# ---------------------------------------------------------------------------
# raise 系数按街道区分（宽池调优：略放宽 preflop / flop，减少 open+cbet 一步过紧）：
#   preflop：3-bet/4-bet代表极化强范围，压缩最猛（~0.33）
#   flop：c-bet 常见较宽（~0.58）
#   turn：第二街下注代表更强范围（~0.50）
#   river：河牌下注高度极化（~0.42）
_ACTION_COMPRESSION_RAISE: Dict[str, float] = {
    "preflop": 0.33,
    "flop":    0.58,
    "turn":    0.50,
    "river":   0.42,
}

_ACTION_COMPRESSION: Dict[str, float] = {
    "call":  0.76,   # 跟注：范围收缩（跟注更宽，含摸牌手）
    "check": 0.92,   # 过牌：范围几乎不变（含慢打和弱手混合）
    "fold":  0.0,    # 弃牌：不再追踪（对手已出局）
}

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
        # 当前手牌中每位对手的范围分数
        self._range: Dict[int, float] = {}
        # 本手中对手下注/加注的街数（用于决策原因说明）
        self._streets_bet: Dict[int, int] = {}
        # 追踪本手是否已在某街行动（避免同一街重复计数）
        self._street_acted: Dict[int, set] = {}

    def reset_hand(self, player_id: int, prior_range: float = 0.35) -> None:
        """手牌开始时重置状态。

        Parameters
        ----------
        player_id : int
        prior_range : float
            先验范围分数，通常用对手历史VPIP。
            若未知，默认0.35（典型6人桌玩家）。
        """
        self._range[player_id] = max(0.05, min(1.0, prior_range))
        self._streets_bet[player_id] = 0
        self._street_acted[player_id] = set()

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
        if player_id not in self._range:
            self.reset_hand(player_id)

        if action == "raise":
            factor = _ACTION_COMPRESSION_RAISE.get(street, 0.50)
        else:
            factor = _ACTION_COMPRESSION.get(action, 1.0)

        if factor == 0.0:
            return  # 弃牌，不更新（对手已出局，无需追踪）

        self._range[player_id] = max(0.02, self._range[player_id] * factor)

        # 统计加注街数（同一街只计一次）
        if action == "raise":
            street_key = (player_id, street)
            acted = self._street_acted.setdefault(player_id, set())
            if street not in acted:
                self._streets_bet[player_id] = self._streets_bet.get(player_id, 0) + 1
                acted.add(street)

    def get_range_fraction(self, player_id: int) -> float:
        """返回对手当前估算范围分数 [0.02, 1.0]。

        若该对手在本手中从未被追踪（new_hand 未调用），返回 1.0——
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
