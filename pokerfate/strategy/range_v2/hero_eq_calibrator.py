"""Hero equity meta-calibrator (缺陷 C).

背景：`range_equity_calculator.weighted_equity_multi` 吐出的 `equity_range`
是 raw MC 结果。决策层拿到后没有任何"事后校准"——即使某 (hero_bucket,
street, num_opponents) 组合在历史上系统性偏低 20pp，tracker 下次还是
照样偏低，没有学习闭环。

ShowdownLearner 学的是**对手**的"某类牌强度下会做什么动作"，是对手端闭环；
本类学的是**hero 自己**的"某状态下的 raw equity 估计 vs 实际摊牌胜率"，
是 hero 端的闭环——**mirror image** 设计。

用法：
1. 手牌结束后，对每条可校准记录调 `record(bucket, street, n_opp, pred, actual)`
2. 决策前调 `calibrate(raw_eq, bucket, street, n_opp)` 得到校准后的 eq
3. 样本不足时返回 raw（无副作用）

校准方式：按 (bucket, street, n_opp_bin) 聚合 (pred, actual) 对，
计算平均 bias = mean(actual - pred)，先 clamp 到 ±0.25，再按
`n/(n+50)` 收缩后加到 raw_eq。收缩常数来自 2-5.log 训练、6.log
交叉验证：multiway MAE 13.01pp → 12.92pp，river MAE 20.69pp → 20.40pp，
且 RMSE 基本不变。河牌 actual 是 0/100 的二元标签，小样本直接吃满 bias
会过拟合；收缩让样本越多越接近旧公式。

语义注意：调用方应传 `predicted_hero_eq_multi` / `actual_hero_eq_street_multi`
（多人池口径），和决策层 `ctx.equity_range` 同口径。单挑场景 n_opp=1 自成一桶。
"""

from __future__ import annotations

import os as _os
from typing import Dict, List, Tuple


_MIN_SAMPLES = 10         # 低于此样本量直接返回 raw
_MAX_SHIFT = 0.25         # bias 单次最多 ±25pp，防止 runaway
_BIAS_SHRINK_K = float(_os.environ.get('PF_HEQ_BIAS_SHRINK_K', '50'))
_VALID_CTX = frozenset(('passive', 'bet', 'raise'))


def _num_opp_bin(n: int) -> str:
    """1 / 2 / 3+ 三档分箱。超过 3 的多路池数据稀疏，合并避免过拟合。"""
    if n <= 1:
        return '1'
    if n == 2:
        return '2'
    return '3+'


def _norm_ctx(action_ctx: str) -> str:
    """Clamp action_ctx 到 {passive, bet, raise}；未知值兜底 passive。"""
    return action_ctx if action_ctx in _VALID_CTX else 'passive'


def _make_key(bucket: str, street: str, num_opp: int,
              action_ctx: str = 'passive') -> str:
    return f"{bucket}|{street}|{_num_opp_bin(num_opp)}|{_norm_ctx(action_ctx)}"


def classify_action_ctx_from_trigger(trigger: str) -> str:
    """Record 时从 PredictionRecord.trigger 推导 action_ctx。

    - action:raise / action:raise_over → 'raise'（B 强压缩源头）
    - action:bet                        → 'bet'（B 中等压缩）
    - action:check/call/fold_other, reset, board:*, 其他 → 'passive'
    """
    if not trigger:
        return 'passive'
    if trigger in ('action:raise', 'action:raise_over'):
        return 'raise'
    if trigger == 'action:bet':
        return 'bet'
    return 'passive'


def classify_action_ctx_from_decision(facing_bet: bool, to_call: float,
                                      pot: float) -> str:
    """Decision 时从 hero 当前局面推导 action_ctx。

    - 不面对下注 → passive
    - 面对下注，to_call / pot_before_bet ≥ 1.0（即 villain 下了 ≥ 1x pot）→ raise
    - 其他面对下注 → bet
    """
    if not facing_bet or to_call <= 0:
        return 'passive'
    pot_before = max(1e-9, pot - to_call)
    ratio = to_call / pot_before
    return 'raise' if ratio >= 1.0 else 'bet'


class HeroEquityCalibrator:
    """Meta-calibrator for hero's equity estimate."""

    def __init__(self) -> None:
        self._samples: Dict[str, List[Tuple[float, float]]] = {}

    # -------- record / query --------

    def record(self, bucket: str, street: str, num_opp: int,
               predicted: float, actual: float,
               action_ctx: str = 'passive') -> None:
        """Record one (predicted, actual) pair for given context key."""
        if not bucket or not street:
            return
        if not (0.0 <= predicted <= 1.0) or not (0.0 <= actual <= 1.0):
            return
        key = _make_key(bucket, street, num_opp, action_ctx)
        self._samples.setdefault(key, []).append((float(predicted), float(actual)))

    def calibrate(self, raw_eq: float, bucket: str, street: str,
                  num_opp: int, action_ctx: str = 'passive') -> float:
        """Apply historical bias correction. Falls back to raw if insufficient data."""
        if not bucket or not street:
            return raw_eq
        samples = self._samples.get(_make_key(bucket, street, num_opp, action_ctx), [])
        if len(samples) < _MIN_SAMPLES:
            return raw_eq
        bias = sum(a - p for p, a in samples) / len(samples)
        bias = max(-_MAX_SHIFT, min(_MAX_SHIFT, bias))
        if _BIAS_SHRINK_K > 0:
            bias *= len(samples) / (len(samples) + _BIAS_SHRINK_K)
        return max(0.0, min(1.0, raw_eq + bias))

    def sample_count(self, bucket: str, street: str, num_opp: int,
                     action_ctx: str = 'passive') -> int:
        return len(self._samples.get(
            _make_key(bucket, street, num_opp, action_ctx), []))

    def bias_for(self, bucket: str, street: str, num_opp: int,
                 action_ctx: str = 'passive') -> float:
        """Return raw bias (not clamped) for diagnostics. 0 if insufficient."""
        samples = self._samples.get(
            _make_key(bucket, street, num_opp, action_ctx), [])
        if len(samples) < _MIN_SAMPLES:
            return 0.0
        return sum(a - p for p, a in samples) / len(samples)

    # -------- persistence --------

    def to_dict(self) -> dict:
        return {k: list(v) for k, v in self._samples.items()}

    @classmethod
    def from_dict(cls, d: dict) -> 'HeroEquityCalibrator':
        inst = cls()
        if not d:
            return inst
        for k, pairs in d.items():
            cleaned: List[Tuple[float, float]] = []
            for item in pairs:
                if isinstance(item, (list, tuple)) and len(item) == 2:
                    p, a = item
                    if 0.0 <= float(p) <= 1.0 and 0.0 <= float(a) <= 1.0:
                        cleaned.append((float(p), float(a)))
            if cleaned:
                inst._samples[k] = cleaned
        return inst
