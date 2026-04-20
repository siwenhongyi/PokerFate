"""Showdown calibration: 记录每次 range 调整时 tracker 的预测，在手牌结束时
对比摊牌的实际结果，输出 calibration 数据供 offline 分析。

设计原则：
- 每次 range 调整（reset_hand / observe_action / reweight_for_board）都调
  `record_prediction`，捕捉当时的预测状态
- 手牌结束时对每个已知底牌的玩家（摊牌参与者）调 `record_actual`，对所有
  该玩家的历史预测进行对比
- 结果写入 structured log（pokerfate.log 的 JSON 流），offline 脚本聚合
  分析（如 hero_eq 预测区间 vs 实际胜率的校准曲线）

不做 runtime 动态调参——样本密度不够可靠。收集数据 → offline 人工复盘 →
手动调参（α, λ, damping 等）。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

import numpy as np
import random

from pokerfate.core.card import Card
from pokerfate.core.hand_evaluator import HandEvaluator
from pokerfate.strategy.range_v2 import hand_categorizer as hcat
from pokerfate.strategy.range_v2 import hand_combo_map as hcm


@dataclass
class PredictionRecord:
    """单次 range 调整之后，tracker 对该玩家的预测快照。"""
    hand_id: int
    street: str
    player_id: int
    player_name: str
    board: List[Card]
    trigger: str                          # 'reset' / 'action:call' / 'board:flop' / ...
    range_pct: float                      # 有效 range 大小（vs 1326 combos）
    bucket_dist: Dict[str, float]         # cat → weight share
    hero_cards: Optional[List[Card]]      # hero 底牌（若已知）
    predicted_hero_eq: Optional[float]    # hero vs 此玩家 narrow range 的胜率（单挑）
    # 多人池胜率：hero 赢过所有当时未弃牌对手的概率（每人自己的 range）。
    # 与决策层 `胜率 X%` 同口径。active_player_ids 记录当时的活跃集，便于
    # 手牌结束后用所有亮牌的 villain 真手牌复算"实际多人胜率"。
    predicted_hero_eq_multi: Optional[float] = None
    active_player_ids: List[int] = field(default_factory=list)
    # Hero 在预测时板面上的桶（air/weak_draw/draw/medium/strong/nuts）。
    # 缺陷 C meta-calibration：按 (hero_bucket, street, n_opp) 累积 (pred,
    # actual) 对，用历史 bias 校正 raw equity。preflop 时为 hero preflop 桶。
    hero_bucket: str = ''


@dataclass
class CalibrationResult:
    """把一个预测和实际摊牌结果对比得出的指标。"""
    record: PredictionRecord
    actual_cards: List[Card]              # 此玩家实际底牌
    actual_bucket: str                    # 实际底牌在预测时点板面下属于哪个桶
    predicted_bucket_prob: float          # 预测时该桶的权重占比
    actual_hero_eq_street: Optional[float]# 预测街道下 hero vs 实际手牌（按当街补牌模拟，单挑）
    eq_prediction_error_street: Optional[float]  # predicted_hero_eq - actual_hero_eq_street
    actual_hero_eq_final: Optional[float] # 最终板面下 hero 对此玩家真实手牌的确定胜率 (0/0.5/1)
    eq_prediction_error: Optional[float]  # predicted_hero_eq - actual_hero_eq_final
    # 多人池实际胜率（方案 5）：已亮 villain 用真手 + 未亮 villain 从剩余
    # 牌堆随机填——保证和 predicted_hero_eq_multi 同口径（都是 N 人池）。
    # 用于 hero_eq_calibrator 学 tracker 的系统性偏差。
    actual_hero_eq_street_multi: Optional[float] = None
    eq_prediction_error_street_multi: Optional[float] = None
    # 日志展示用：只用亮牌 villain 做模拟（旧行为），反映真实本手结果。
    # 不喂给 calibrator——它有口径偏差，只用于人看。
    actual_hero_eq_street_multi_shown: Optional[float] = None


class ShowdownCalibrator:
    """按手牌累积 prediction，手牌结束时对比摊牌实际并输出校准数据。"""

    def __init__(self, logger=None):
        """
        Parameters
        ----------
        logger : optional
            具有 calibration_result 方法的 logger
            实例。如 None，则只累积在内存中不写日志。
        """
        self._logger = logger
        self._hand_id: int = 0
        # player_id → 本手至今的所有 PredictionRecord 列表
        self._hand_predictions: Dict[int, List[PredictionRecord]] = {}
        # 本手累积的摊牌 villain 底牌（player_id → cards），用于计算多人
        # 池"实际胜率"。finalize_hand_calibration 读这里。
        self._shown_cards: Dict[int, List[Card]] = {}

    # ---------------- lifecycle ----------------

    def start_hand(self, hand_id: int) -> None:
        self._hand_id = hand_id
        self._hand_predictions = {}
        self._shown_cards = {}

    # ---------------- prediction 录入 ----------------

    def record_prediction(
        self,
        player_id: int,
        player_name: str,
        street: str,
        board: List[Card],
        weights: np.ndarray,
        hero_cards: Optional[List[Card]],
        trigger: str,
        active_weights: Optional[Dict[int, np.ndarray]] = None,
    ) -> None:
        """每次 tracker 的 _weights[player_id] 更新后调用。

        active_weights：tracker 当前所有未弃牌对手的权重 {pid: w}。若提供，
        计算 hero 赢过所有这些对手的多人池胜率（决策层同口径）。
        """
        total = float(weights.sum())
        if total < 1e-15:
            return
        w_norm = weights / total

        # range_pct：把"有效 combo"定义为权重 > uniform 的 10%
        # （meaningful in range）
        threshold = (1.0 / 1326) * 0.1
        range_pct = float((w_norm > threshold).sum()) / 1326

        # bucket dist
        bucket_dist = self._compute_bucket_dist(w_norm, board)

        # hero eq（如 hero 底牌已知）
        predicted_hero_eq: Optional[float] = None
        predicted_hero_eq_multi: Optional[float] = None
        active_player_ids: List[int] = []
        if hero_cards is not None and len(hero_cards) >= 2:
            predicted_hero_eq = self._compute_hero_eq(hero_cards, board, w_norm)
            if active_weights:
                opp_ranges: List[np.ndarray] = []
                ordered_ids: List[int] = []
                for pid, aw in active_weights.items():
                    s = float(aw.sum())
                    if s <= 1e-15:
                        continue
                    opp_ranges.append(aw / s)
                    ordered_ids.append(pid)
                if opp_ranges:
                    predicted_hero_eq_multi = self._compute_hero_eq_multi(
                        hero_cards, board, opp_ranges,
                    )
                    active_player_ids = ordered_ids

        # Hero 自己在这个板面的桶（meta-calibration 键的一部分）
        hero_bucket = ''
        if hero_cards is not None and len(hero_cards) >= 2:
            hero_bucket = hcat.categorize_cards(list(hero_cards), list(board))

        record = PredictionRecord(
            hand_id=self._hand_id,
            street=street,
            player_id=player_id,
            player_name=player_name,
            board=list(board),
            trigger=trigger,
            range_pct=range_pct,
            bucket_dist=bucket_dist,
            hero_cards=list(hero_cards) if hero_cards else None,
            predicted_hero_eq=predicted_hero_eq,
            predicted_hero_eq_multi=predicted_hero_eq_multi,
            active_player_ids=active_player_ids,
            hero_bucket=hero_bucket,
        )
        self._hand_predictions.setdefault(player_id, []).append(record)

    # ---------------- 手牌结束：摊牌对比 ----------------

    def record_actual(
        self,
        player_id: int,
        actual_cards: List[Card],
        final_board: List[Card],
        hero_cards: Optional[List[Card]],
    ) -> None:
        """在手牌结束且此玩家底牌已知时调用——只缓存底牌。逐手的
        CalibrationResult 在 `finalize_hand_calibration` 里统一计算和
        写日志，这样多人池"实际胜率"能在所有亮牌的 villain 都记入后
        再一并模拟。"""
        self._shown_cards[player_id] = list(actual_cards)

    def finalize_hand_calibration(
        self,
        hero_cards: Optional[List[Card]],
        final_board: List[Card],
    ) -> List[CalibrationResult]:
        """所有 villain 亮牌采集完后调一次，对每个 (villain, 预测快照)
        计算 CalibrationResult（单挑 + 多人池）并写日志。"""
        all_results: List[CalibrationResult] = []
        for player_id, actual_cards in self._shown_cards.items():
            records = self._hand_predictions.get(player_id, [])
            for rec in records:
                result = self._build_result(rec, actual_cards, hero_cards, final_board)
                all_results.append(result)
        if self._logger is not None:
            for r in all_results:
                self._logger.calibration_result(r)
        return all_results

    def emit_records_for(
        self,
        player_id: int,
        hero_cards: Optional[List[Card]],
        final_board: List[Card],
    ) -> List[CalibrationResult]:
        """只发这一个 villain 的校准记录。调用方要先把本手所有 villain 的
        亮牌都喂进 `_shown_cards`（通过 `record_actual`），这样多人池"实际
        胜率"能引用其他 villain 的真手牌。"""
        actual_cards = self._shown_cards.get(player_id)
        if actual_cards is None:
            return []
        records = self._hand_predictions.get(player_id, [])
        results: List[CalibrationResult] = []
        for rec in records:
            result = self._build_result(rec, actual_cards, hero_cards, final_board)
            results.append(result)
        if self._logger is not None:
            for r in results:
                self._logger.calibration_result(r)
        return results

    def _build_result(
        self,
        rec: PredictionRecord,
        actual_cards: List[Card],
        hero_cards: Optional[List[Card]],
        final_board: List[Card],
    ) -> CalibrationResult:
        # 预测时点的实际桶（把 actual_cards 放到 rec.board 上分类）
        if rec.board and len(rec.board) >= 3:
            actual_bucket = hcat.categorize_cards(actual_cards, rec.board)
        else:
            actual_bucket = hcat.categorize_cards(actual_cards, [])
        predicted_bucket_prob = rec.bucket_dist.get(actual_bucket, 0.0)

        # heads-up 实际胜率（单挑）
        actual_hero_eq_street = None
        eq_error_street = None
        if hero_cards is not None and len(hero_cards) >= 2:
            actual_hero_eq_street = self._actual_hero_eq_at_street(
                hero_cards, actual_cards, rec.board,
            )
            if (rec.predicted_hero_eq is not None
                    and actual_hero_eq_street is not None):
                eq_error_street = rec.predicted_hero_eq - actual_hero_eq_street

        # 最终板面下 hero vs 此 villain 的确定胜率（保留兼容字段）
        actual_hero_eq_final = None
        eq_error = None
        if (hero_cards is not None and len(hero_cards) >= 2
                and final_board and len(final_board) >= 5):
            actual_hero_eq_final = self._actual_hero_eq(
                hero_cards, actual_cards, final_board,
            )
            if rec.predicted_hero_eq is not None:
                eq_error = rec.predicted_hero_eq - actual_hero_eq_final

        # 多人池实际胜率：用 N-way 模拟——已亮牌 villain 用真手牌，未亮牌的
        # 用剩余牌堆随机 2 张填充。这样 actual 和 predicted 都是 N 人池口径，
        # 消除"predicted 用 N 人、actual 只用亮牌子集（M ≤ N）"的选择偏差——
        # 之前那个偏差让 hero_eq_calibrator 学到假的 +20~+40pp bias。
        #
        # 需要至少一个亮牌作为 ground-truth 锚定，否则等同 hero vs N 个随机
        # 对手，信息量太弱，直接跳过。
        actual_hero_eq_multi = None
        actual_hero_eq_multi_shown = None
        eq_error_multi = None
        if (hero_cards is not None and len(hero_cards) >= 2
                and rec.active_player_ids):
            shown_hands: List[List[Card]] = []
            n_unshown = 0
            for pid in rec.active_player_ids:
                if pid in self._shown_cards:
                    shown_hands.append(self._shown_cards[pid])
                else:
                    n_unshown += 1
            if shown_hands:
                # 只用亮牌 villain 的版本——日志展示用（反映本手真实摊牌结果）
                actual_hero_eq_multi_shown = self._actual_hero_eq_multi_at_street(
                    hero_cards, shown_hands, rec.board, n_unshown=0,
                )
                # N-way 版本——hero_eq_calibrator 用（和 predicted 同口径）
                if n_unshown > 0:
                    actual_hero_eq_multi = self._actual_hero_eq_multi_at_street(
                        hero_cards, shown_hands, rec.board, n_unshown=n_unshown,
                    )
                else:
                    # 全亮牌：shown 版就是 N-way 版
                    actual_hero_eq_multi = actual_hero_eq_multi_shown
                if (rec.predicted_hero_eq_multi is not None
                        and actual_hero_eq_multi is not None):
                    eq_error_multi = (
                        rec.predicted_hero_eq_multi - actual_hero_eq_multi
                    )

        return CalibrationResult(
            record=rec,
            actual_cards=list(actual_cards),
            actual_bucket=actual_bucket,
            predicted_bucket_prob=predicted_bucket_prob,
            actual_hero_eq_street=actual_hero_eq_street,
            eq_prediction_error_street=eq_error_street,
            actual_hero_eq_final=actual_hero_eq_final,
            eq_prediction_error=eq_error,
            actual_hero_eq_street_multi=actual_hero_eq_multi,
            eq_prediction_error_street_multi=eq_error_multi,
            actual_hero_eq_street_multi_shown=actual_hero_eq_multi_shown,
        )

    # ---------------- 辅助计算 ----------------

    @staticmethod
    def _compute_bucket_dist(w_norm: np.ndarray,
                             board: List[Card]) -> Dict[str, float]:
        """与 BayesianRangeTracker.get_bucket_distribution 同口径但不需要
        tracker 实例。"""
        buckets: Dict[str, float] = {}
        if board and len(board) >= 3:
            board_ints = {hcm.card_to_int(c) for c in board}
            for idx in range(1326):
                if w_norm[idx] < 1e-8:
                    continue
                c1, c2 = hcm.ALL_COMBOS[idx]
                if c1 in board_ints or c2 in board_ints:
                    continue
                cat = hcat.categorize(idx, board)
                buckets[cat] = buckets.get(cat, 0.0) + float(w_norm[idx])
        else:
            # preflop：用 preflop bucket
            for idx in range(1326):
                if w_norm[idx] < 1e-8:
                    continue
                cat = hcat.categorize(idx, [])
                buckets[cat] = buckets.get(cat, 0.0) + float(w_norm[idx])
        total = sum(buckets.values())
        if total > 0:
            buckets = {k: v / total for k, v in buckets.items()}
        return buckets

    @staticmethod
    def _compute_hero_eq(hero_cards: List[Card], board: List[Card],
                         w_norm: np.ndarray) -> float:
        """hero 对 villain 的 weighted range equity。river 精确枚举；前街 MC。
        复用 RangeEquityCalculator 接口。"""
        from pokerfate.strategy.range_v2.range_equity_calculator import (
            RangeEquityCalculator,
        )
        return float(RangeEquityCalculator.weighted_equity(
            hero_cards, board, w_norm, num_opponents=1, n_samples=500,
        ))

    @staticmethod
    def _compute_hero_eq_multi(hero_cards: List[Card], board: List[Card],
                               opp_ranges: List[np.ndarray]) -> float:
        """hero 赢过所有 opp_ranges 对手的多人池胜率。每个对手独立 range。
        与决策层 weighted_equity_multi 同口径。"""
        from pokerfate.strategy.range_v2.range_equity_calculator import (
            RangeEquityCalculator,
        )
        return float(RangeEquityCalculator.weighted_equity_multi(
            hero_cards, board, opp_ranges, n_samples=500,
        ))

    @staticmethod
    def _actual_hero_eq(hero_cards: List[Card], villain_cards: List[Card],
                        final_board: List[Card]) -> float:
        """最终板面下 hero vs villain 具体手牌的确定胜率（0.0/0.5/1.0）。"""
        hero_score = HandEvaluator.eval_int(list(hero_cards) + list(final_board))
        villain_score = HandEvaluator.eval_int(list(villain_cards) + list(final_board))
        if hero_score > villain_score:
            return 1.0
        if hero_score < villain_score:
            return 0.0
        return 0.5

    @staticmethod
    def _actual_hero_eq_at_street(
        hero_cards: List[Card],
        villain_cards: List[Card],
        board_at_street: List[Card],
    ) -> Optional[float]:
        """按预测街道计算 hero 对具体 villain 手牌的真实胜率。

        - preflop: 手牌 + 补发5张
        - flop:    手牌+3张板面 + 补发2张
        - turn:    手牌+4张板面 + 补发1张
        - river:   手牌+5张板面（确定性 0/0.5/1）
        """
        if hero_cards is None or villain_cards is None:
            return None
        if len(hero_cards) < 2 or len(villain_cards) < 2:
            return None

        board = list(board_at_street or [])
        if len(board) > 5:
            board = board[:5]

        # river 直接确定胜负
        if len(board) == 5:
            return ShowdownCalibrator._actual_hero_eq(hero_cards, villain_cards, board)

        need = 5 - len(board)
        if need < 0:
            return None

        # 构建剩余牌堆
        used = {hcm.card_to_int(c) for c in (list(hero_cards[:2]) + list(villain_cards[:2]) + board)}
        deck = [i for i in range(52) if i not in used]
        if len(deck) < need:
            return None

        # 为了日志稳定可复现，用固定 seed；不同牌局状态会得到不同抽样序列
        seed = 17
        for c in hero_cards[:2] + villain_cards[:2] + board:
            seed = seed * 131 + hcm.card_to_int(c)
        rng = random.Random(seed)

        # 按街道控制采样量：前街多一点，后街少一点
        if need == 5:
            n_samples = 3000
        elif need == 2:
            n_samples = 1800
        else:  # need == 1
            n_samples = 1200

        win = 0.0
        hero = list(hero_cards[:2])
        villain = list(villain_cards[:2])
        for _ in range(n_samples):
            runout_idx = rng.sample(deck, need)
            runout = [hcm.int_to_card(i) for i in runout_idx]
            full_board = board + runout
            hero_score = HandEvaluator.eval_int(hero + full_board)
            villain_score = HandEvaluator.eval_int(villain + full_board)
            if hero_score > villain_score:
                win += 1.0
            elif hero_score == villain_score:
                win += 0.5
        return win / float(n_samples)

    @staticmethod
    def _actual_hero_eq_multi_at_street(
        hero_cards: List[Card],
        villain_hands: List[List[Card]],
        board_at_street: List[Card],
        n_unshown: int = 0,
    ) -> Optional[float]:
        """多人池下 hero 赢过所有活跃对手的胜率，按预测街道补发剩余板牌。

        - villain_hands：已亮牌 villain 的真手牌
        - n_unshown：未亮牌但当时活跃的 villain 数量——每次抽样从剩余牌堆
          随机抽 2 张给他们做手牌。这样 hero 面对的永远是"N 人池"，和
          predicted_hero_eq_multi 的 N 同口径，避免选择偏差把假 bias 学进
          hero_eq_calibrator。
        - 平分按 1/(n_tied) 计入胜率
        - 需要至少 1 个亮牌做 ground-truth 锚定；全部随机等同 hero vs 随机，
          信息量太弱，调用方应过滤（返回 None 表示无法计算）
        """
        if hero_cards is None:
            return None
        if len(hero_cards) < 2:
            return None
        if not villain_hands:
            return None
        if any(len(v) < 2 for v in villain_hands):
            return None
        if n_unshown < 0:
            n_unshown = 0

        board = list(board_at_street or [])
        if len(board) > 5:
            board = board[:5]

        hero = list(hero_cards[:2])
        shown_villains = [list(v[:2]) for v in villain_hands]

        need_runout = 5 - len(board)
        if need_runout < 0:
            return None

        # river + 全亮牌：确定性计算（无须 MC）
        if need_runout == 0 and n_unshown == 0:
            hero_s = HandEvaluator.eval_int(hero + board)
            opp_s = [HandEvaluator.eval_int(v + board) for v in shown_villains]
            best_opp = max(opp_s)
            if hero_s > best_opp:
                return 1.0
            if hero_s < best_opp:
                return 0.0
            tied = 1 + sum(1 for s in opp_s if s == best_opp)
            return 1.0 / tied

        # 构造剩余牌堆（hero + shown villains + board 全部 used）
        used_ints = {hcm.card_to_int(c) for c in hero}
        for v in shown_villains:
            used_ints |= {hcm.card_to_int(c) for c in v}
        used_ints |= {hcm.card_to_int(c) for c in board}
        deck = [i for i in range(52) if i not in used_ints]

        total_draws_per_trial = 2 * n_unshown + need_runout
        if len(deck) < total_draws_per_trial:
            return None

        # 固定 seed 可复现
        seed = 29
        for c in hero + [cc for v in shown_villains for cc in v] + board:
            seed = seed * 131 + hcm.card_to_int(c)
        seed = seed * 131 + n_unshown
        rng = random.Random(seed)

        # 采样量：按 runout 长度 + n_unshown 增幅（填充引入额外方差）
        if need_runout == 5:
            base = 3000
        elif need_runout == 2:
            base = 1800
        elif need_runout == 1:
            base = 1200
        else:   # 0 runout but n_unshown > 0
            base = 2000
        n_samples = int(base * (1.0 + 0.25 * n_unshown))

        score = 0.0
        for _ in range(n_samples):
            drawn = rng.sample(deck, total_draws_per_trial)
            # 前 2*n_unshown 张分给未亮 villain（两两一组）
            filled: List[List[Card]] = []
            for i in range(n_unshown):
                filled.append([
                    hcm.int_to_card(drawn[2 * i]),
                    hcm.int_to_card(drawn[2 * i + 1]),
                ])
            runout = [
                hcm.int_to_card(drawn[2 * n_unshown + j])
                for j in range(need_runout)
            ]
            full_board = board + runout
            all_villains = shown_villains + filled

            hero_s = HandEvaluator.eval_int(hero + full_board)
            opp_s = [HandEvaluator.eval_int(v + full_board) for v in all_villains]
            best_opp = max(opp_s)
            if hero_s > best_opp:
                score += 1.0
            elif hero_s == best_opp:
                tied = 1 + sum(1 for s in opp_s if s == best_opp)
                score += 1.0 / tied
        return score / float(n_samples)
