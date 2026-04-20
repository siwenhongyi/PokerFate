"""Learn P(action | category) from showdown observations.

记录每一次摊牌里对手每街动作所持桶的次数，累积后按贝叶斯 likelihood 语义
返回 `{cat: P(action | cat)}`，用来覆盖 action_model 的 GTO 默认 likelihood。

**存储格式**：`_freq[name][(street, action)][cat] = count`
表示玩家 `name` 在 `street` 做 `action` 时持桶 `cat` 的观察次数。

**查询语义**：`get_learned_freq(name, street, action)` 返回
`{cat: P(action | cat, street, player)}`，计算方式：
    P(action | cat) = count(action, cat) / Σ_{a} count(a, cat)
其中 a 遍历该玩家该街的所有已记录（非 fold）动作。

注意 record() 跳过 fold 动作，所以分母实际是 "非 fold 动作总数"——这是
showdown 数据的本质局限（fold 后不会亮牌），在极端情况下（某桶几乎全
fold）会让该桶的分母小到估计不稳。上层通过 min_samples 过滤缓解。

Reference: Bayes' Bluff (UAI 2005) — Dirichlet posterior on action profiles.
"""

from __future__ import annotations

import json
import os
from typing import Dict, List, Optional, Tuple

from pokerfate.core.card import Card
from pokerfate.strategy.range_v2 import hand_categorizer as hcat


class ShowdownLearner:
    """按摊牌数据学每个玩家的 P(action | category) 经验分布。

    **存储格式不变**（向后兼容，opponents.json 的 2193 玩家数据零迁移）：
        `_freq[name][(street, action)][cat] = count`

    **但查询语义已修正**（2026-04-23）：get_learned_freq 从返回 P(cat|action)
    改为真·按贝叶斯 likelihood 返回 P(action|cat)，详见该方法 docstring。

    存储格式"按 (street, action) 分组计 cat 次数"的原因：record() 的写入路径
    最自然的 key（每个事件天然携带 action），且保留这种索引让 sample_count
    (name, street, action) 能直接 O(1) 返回该 (street, action) 的观察总数，
    不影响 poker_bot 的 use_calibration 判据。

    Completely independent from EQR's ShowdownCalibrator.
    """

    _MIN_SAMPLES = 8

    def __init__(self) -> None:
        # 存储：`name → (street, action) → cat → count`
        # 每条记录 = 一次摊牌里观察到 "player 在 street 做 action 时持 cat" 的次数
        self._freq: Dict[str, Dict[Tuple[str, str], Dict[str, int]]] = {}

    def record(self, name: str, action_history: List[Tuple[str, str]],
               hand: List[Card], board: List[Card]) -> None:
        """Record one showdown observation.

        Parameters
        ----------
        name : str
            Player name (stable across sessions).
        action_history : list of (street, action)
            Actions taken by this player during the hand.
        hand : list of Card
            The revealed hole cards (2 cards).
        board : list of Card
            Final board (up to 5 cards).
        """
        if len(hand) < 2:
            return

        player_data = self._freq.setdefault(name, {})

        for street, action in action_history:
            if action == 'fold':
                continue

            street_board = _board_at_street(board, street)
            if street_board:
                cat = hcat.categorize_cards(hand, street_board)
            else:
                cat = hcat.categorize_cards(hand, [])  # preflop bucket

            key = (street, action)
            cat_counts = player_data.setdefault(key, {})
            cat_counts[cat] = cat_counts.get(cat, 0) + 1

    def get_learned_freq(self, name: str, street: str, action: str,
                         min_samples: int = _MIN_SAMPLES
                         ) -> Optional[Dict[str, float]]:
        """Return `{cat: P(action | cat, street, player)}` for this player。

        2026-04-23 修 Bayes 方向 bug：旧版错误地返回 P(cat | action) 并被
        action_model 当 likelihood 使用，等于在贝叶斯更新里双重施加 prior。
        新版真·按贝叶斯 likelihood 语义返回 P(action | cat)。

        计算：
            P(action | cat) = count(action, cat) /
                              Σ_{a ∈ player's recorded actions at street} count(a, cat)

        门槛（向后兼容）：仍按 (street, action) 的总观察数判断，总数 <
        `min_samples` 时返回 None，调用方回落 GTO baseline。门槛语义和旧版
        一致，这样 `sample_count` 和 blend shrinkage 公式都不受影响。

        数据不足的 cat 不进返回字典（那个桶没样本或 count 为 0），调用方
        需对缺失 cat 做 fallback（action_model 用 `learned.get(cat, 0.01)`
        + _clip 做兜底）。

        返回 None 当：(street, action) 的 combined count 未达 min_samples。
        """
        player_data = self._freq.get(name, {})

        # 门槛判定：保留旧版"该 (street, action) 总样本数"作为开关
        target_data = player_data.get((street, action))
        if target_data is None:
            return None
        if sum(target_data.values()) < min_samples:
            return None

        # 聚合该玩家该街所有已记录动作下的 per-cat 计数
        cat_action_totals: Dict[str, Dict[str, int]] = {}
        for (s, a), cat_counts in player_data.items():
            if s != street:
                continue
            for cat, cnt in cat_counts.items():
                cat_action_totals.setdefault(cat, {})
                cat_action_totals[cat][a] = cat_action_totals[cat].get(a, 0) + cnt

        result: Dict[str, float] = {}
        for cat, action_counts in cat_action_totals.items():
            cat_total = sum(action_counts.values())
            if cat_total <= 0:
                continue
            result[cat] = action_counts.get(action, 0) / cat_total
        return result

    def sample_count(self, name: str, street: str, action: str) -> int:
        """Return number of showdown samples for (name, street, action)."""
        data = self._freq.get(name, {}).get((street, action))
        if data is None:
            return 0
        return sum(data.values())

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_dict(self) -> dict:
        """Serialize to JSON-compatible dict."""
        result: dict = {}
        for name, pdata in self._freq.items():
            player_dict: dict = {}
            for (street, action), cats in pdata.items():
                key = f"{street}:{action}"
                player_dict[key] = dict(cats)
            result[name] = player_dict
        return result

    @classmethod
    def from_dict(cls, data: dict) -> 'ShowdownLearner':
        """Deserialize from dict."""
        learner = cls()
        for name, pdata in data.items():
            player_freq: Dict[Tuple[str, str], Dict[str, int]] = {}
            for key_str, cats in pdata.items():
                parts = key_str.split(':', 1)
                if len(parts) == 2:
                    player_freq[(parts[0], parts[1])] = dict(cats)
            learner._freq[name] = player_freq
        return learner

    def save(self, filepath: str) -> None:
        """Persist to JSON file."""
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)

    def load(self, filepath: str) -> None:
        """Load from JSON file (no-op if file missing)."""
        if not os.path.exists(filepath):
            return
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read().strip()
        if not content:
            return
        try:
            loaded = self.__class__.from_dict(json.loads(content))
            self._freq = loaded._freq
        except (json.JSONDecodeError, KeyError, ValueError):
            pass


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _board_at_street(board: List[Card], street: str) -> List[Card]:
    """Return the board cards visible at the given street."""
    if street == 'preflop':
        return []
    if street == 'flop':
        return board[:3] if len(board) >= 3 else []
    if street == 'turn':
        return board[:4] if len(board) >= 4 else []
    if street == 'river':
        return board[:5] if len(board) >= 5 else []
    return []
