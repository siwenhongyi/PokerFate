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

from typing import Any, Dict, List, Optional, Tuple



_MIN_SAMPLES = 10         # 低于此样本量直接返回 raw
# 每个 key 只保留最近 N 条 (pred, actual)。bias 估的是"当前 tracker 在当前牌池里"
# 的系统偏差，而样本会随代码版本和牌池漂移：2026-11-09 用持久化样本做前瞻
# (prequential) 检验，每个 key 最后 25% 样本上 raw+bias 的 MSE：全量均值
# -4.5%，窗口 100/200/300/500/1000 分别 -6.0/-6.1/-6.2/-6.2/-5.9%，且
# strong|river|1|passive、strong|river|2|bet、strong|turn|1|passive 等面对
# 下注的 key 上全量均值比不校准还差，窗口均值不差。300 处在平台区中段：
# 河牌 0/1 标签下窗口均值的标准误 ≈ 0.03，忙 key 几天内即可跟上漂移。
_MAX_SAMPLES_PER_KEY = 300
_MAX_SHIFT = 0.25         # bias 单次最多 ±25pp，防止 runaway
_BIAS_SHRINK_K = 50.0
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
        self.last_diagnostic: Dict[str, Any] = {}

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
        samples = self._samples.setdefault(key, [])
        samples.append((float(predicted), float(actual)))
        if len(samples) > _MAX_SAMPLES_PER_KEY:
            del samples[:-_MAX_SAMPLES_PER_KEY]

    def calibrate(self, raw_eq: float, bucket: str, street: str,
                  num_opp: int, action_ctx: str = 'passive') -> float:
        """Add the online historical bias for this (bucket, street, n_opp, ctx) key.

        Two layers that used to run first were removed on 2026-11-11 after
        row-level evaluation on the latest run: the runtime formula params
        (runtime_equity_params.json) moved hero equity by <= 0.3pp, and the
        LightGBM equity model by <= 0.1pp. Only the online bias is left.
        """
        self.last_diagnostic = {}
        if not bucket or not street:
            return raw_eq
        calibrated = raw_eq
        samples = self._samples.get(_make_key(bucket, street, num_opp, action_ctx), [])
        online_bias = 0.0
        if len(samples) >= _MIN_SAMPLES:
            online_bias = sum(a - p for p, a in samples) / len(samples)
            online_bias = max(-_MAX_SHIFT, min(_MAX_SHIFT, online_bias))
            if _BIAS_SHRINK_K > 0:
                online_bias *= len(samples) / (len(samples) + _BIAS_SHRINK_K)
            calibrated = max(0.0, min(1.0, calibrated + online_bias))
        self.last_diagnostic = {
            'raw': float(raw_eq),
            'online_bias': float(online_bias),
            'final': float(calibrated),
        }
        return calibrated

    def sample_count(self, bucket: str, street: str, num_opp: int,
                     action_ctx: str = 'passive') -> int:
        return len(self._samples.get(
            _make_key(bucket, street, num_opp, action_ctx), []))

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
                # Persisted lists are append-ordered, so the tail is the
                # most recent window.
                inst._samples[k] = cleaned[-_MAX_SAMPLES_PER_KEY:]
        return inst
