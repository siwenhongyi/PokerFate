"""Hero range bucket distribution estimator for α-gate.

Given hero's position and facing_action, enumerate the preflop opening /
defending range and bucket each combo on the current board. Returns the
aggregated bucket distribution — doc 03 §7.2.

**2026-04-22 增强（方案 B）**：按 `my_prev_actions` 过滤 subrange。每个 combo
在返回前被一个 `reach_prob` 加权，用 GTO 基线频率表估算该 combo 经过 hero 前
街动作后仍留在当前 range 的概率。

为什么需要：原实现把所有 preflop open range 的 combo 一视同仁投到当前板上，
忽略了 "hero 翻牌 check 过，正在 turn 做 delayed c-bet" 这种节点的 subrange
实际比全 range 窄得多。solver 的 range 树天然做了这件事；这里做一个 bucket
频率表驱动的轻量近似。
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional

from pokerfate.core.card import Card, Suit
from pokerfate.core.position import normalize_position
from pokerfate.strategy import preflop as _pf
from pokerfate.strategy.range_v2.hand_categorizer import categorize_cards

log = logging.getLogger(__name__)


_BUCKETS = ('nuts', 'strong', 'medium', 'draw', 'weak_draw', 'air')


# ---------------------------------------------------------------------------
# GTO baseline action frequencies per bucket per street
# ---------------------------------------------------------------------------
#
# 语义：`P(bucket 在某街选某 action)`，用来做 reach-probability 过滤。
# 源：
#   - GTO Wizard "The Mechanics of C-Bet Sizing"
#   - GTO Wizard "Principles of Turn Strategy"
#   - Upswing Poker bet sizing 8 rules
#   - PioSolver aggregate tendencies
# 这些是 solver 对 "PFR 翻牌面对无动作" 和 "turn first-in" 场景的 ballpark
# 均值，按 6 档 bucket 汇总。
#
# 使用路径：reach_prob(combo, history) = Π_{street ∈ history} p(bucket_on_street,
#   action)。结果作为 combo 在 subrange 中的权重。
#

# PFR 翻牌 c-bet 频率（面对无前置动作的首位下注）
_FLOP_CBET_FREQ_PFR: Dict[str, float] = {
    'nuts':      0.85,  # 套子 / 强两对 — 强 value + 极化
    'strong':    0.75,  # 超对 / 顶对好 kicker — value + 保护
    'medium':    0.50,  # 弱顶对 / 次对 / 中小对 — 混频（pot control 50%）
    'draw':      0.70,  # FD / OESD — 半诈唬高频
    'weak_draw': 0.55,  # gutshot+overcard / BDFD+overcard — 中频
    'air':       0.60,  # 纯空气 — range cbet 覆盖（干板高，湿板低）
}

# 防守方（非 PFR）flop 主动下注频率（donk-bet 为主）— solver 里极低
_FLOP_CBET_FREQ_DEFENDER: Dict[str, float] = {
    'nuts':      0.30,
    'strong':    0.15,
    'medium':    0.05,
    'draw':      0.15,
    'weak_draw': 0.08,
    'air':       0.08,
}

# Turn first-in 下注频率（翻牌双方 check 后，谁先下）
# 适用 delayed_cbet / probe_bet / turn_donk 的 subrange 估算
_TURN_FIRST_IN_FREQ: Dict[str, float] = {
    'nuts':      0.80,
    'strong':    0.60,
    'medium':    0.35,
    'draw':      0.55,
    'weak_draw': 0.35,
    'air':       0.40,
}

# Turn continuation after flop bet（double barrel 频率估算）
_TURN_BARREL_FREQ: Dict[str, float] = {
    'nuts':      0.85,
    'strong':    0.70,
    'medium':    0.40,
    'draw':      0.60,
    'weak_draw': 0.35,
    'air':       0.45,
}


def _combos_for_category(cat: str) -> List[List[Card]]:
    """Enumerate all 2-card Card combos that belong to a canonical category
    like 'AA', 'AKs', 'AKo'."""
    rank_map = {'2': 2, '3': 3, '4': 4, '5': 5, '6': 6, '7': 7, '8': 8, '9': 9,
                'T': 10, 'J': 11, 'Q': 12, 'K': 13, 'A': 14}
    combos: List[List[Card]] = []
    if len(cat) == 2:  # pair, e.g. AA
        r = rank_map[cat[0]]
        suits = [Suit.CLUBS, Suit.DIAMONDS, Suit.HEARTS, Suit.SPADES]
        for i in range(len(suits)):
            for j in range(i + 1, len(suits)):
                combos.append([Card(r, suits[i]), Card(r, suits[j])])
    elif len(cat) == 3:
        r1, r2, s = cat[0], cat[1], cat[2]
        r1v, r2v = rank_map[r1], rank_map[r2]
        suits = [Suit.CLUBS, Suit.DIAMONDS, Suit.HEARTS, Suit.SPADES]
        if s == 's':
            for su in suits:
                combos.append([Card(r1v, su), Card(r2v, su)])
        else:  # off-suit
            for i in suits:
                for j in suits:
                    if i != j:
                        combos.append([Card(r1v, i), Card(r2v, j)])
    return combos


def _range_for(position: str, facing: str) -> set:
    """Return hero's category-level range set for given (position, facing)."""
    pos = normalize_position(position, default='MP', warn=False)
    if facing in ('', 'none'):
        return _pf._POSITION_RANGES.get(pos, _pf._UTG_RANGE)
    if facing == 'bb_defend':
        # Approximate: use BTN-wide defend as baseline.
        return _pf._BB_VS_BTN_DEFENSE
    # Default fallback: position's RFI range.
    return _pf._POSITION_RANGES.get(pos, _pf._UTG_RANGE)


def _action_prob(
    bucket: str,
    street: str,
    action: str,
    is_pfr: bool,
    had_flop_bet: bool = False,
) -> float:
    """P(选这个 action | bucket, street, PFR 身份, 是否已在翻牌下过注)。"""
    if street == 'flop':
        table = _FLOP_CBET_FREQ_PFR if is_pfr else _FLOP_CBET_FREQ_DEFENDER
    elif street == 'turn':
        # 如果翻牌下过注，是 barrel 续注场景；否则是 turn-first-in
        table = _TURN_BARREL_FREQ if had_flop_bet else _TURN_FIRST_IN_FREQ
    else:
        # River 或未知街：不过滤
        return 1.0

    bet_p = table.get(bucket, 0.5)
    if action in ('bet', 'raise'):
        return bet_p
    if action == 'check':
        return 1.0 - bet_p
    # call / fold 不改变 hero 后续 range 存活概率（hero 若弃，就不在这节点）
    return 1.0


def _reach_prob(
    combo: List[Card],
    board: List[Card],
    my_prev_actions: Dict[str, str],
    is_pfr: bool,
) -> float:
    """combo 在经历 my_prev_actions 后仍在 hero range 里的概率。

    按街链式乘积：P(reach) = Π P(action_on_street | bucket_at_that_street)。
    每个街的 bucket 按**当时能看到的 board 部分**重新分类（同一个 combo 在
    flop 可能是 medium，在 turn 改进后变 strong，两次用各自 bucket 算频率）。
    """
    if not my_prev_actions:
        return 1.0

    prob = 1.0
    had_flop_bet = False

    if 'flop' in my_prev_actions and len(board) >= 3:
        flop_board = board[:3]
        try:
            bucket = categorize_cards(list(combo), flop_board)
        except Exception:
            log.exception(
                "hero range reach bucket failed street=flop combo=%s board=%s",
                [str(c) for c in combo],
                [str(c) for c in flop_board],
            )
            return 1.0
        action = my_prev_actions['flop']
        prob *= _action_prob(bucket, 'flop', action, is_pfr)
        if action in ('bet', 'raise'):
            had_flop_bet = True

    if 'turn' in my_prev_actions and len(board) >= 4:
        turn_board = board[:4]
        try:
            bucket = categorize_cards(list(combo), turn_board)
        except Exception:
            log.exception(
                "hero range reach bucket failed street=turn combo=%s board=%s",
                [str(c) for c in combo],
                [str(c) for c in turn_board],
            )
            return prob
        action = my_prev_actions['turn']
        prob *= _action_prob(bucket, 'turn', action, is_pfr, had_flop_bet=had_flop_bet)

    return prob


def distribution(
    position: str,
    facing: str,
    board: List[Card],
    hero_known_cards: Optional[List[Card]] = None,
    my_prev_actions: Optional[Dict[str, str]] = None,
    is_pfr: bool = False,
) -> Dict[str, float]:
    """Return bucket → probability over hero's (action-filtered) range.

    参数：
      position / facing  — 选哪张翻前 range 表
      board              — 当前板（3/4/5 张）
      hero_known_cards   — hero 底牌（用于 card removal）
      my_prev_actions    — {'flop': 'check'/'bet', 'turn': ...} hero 前街动作
      is_pfr             — hero 是否翻前最后加注者

    当 my_prev_actions 为空时等价于旧版（无过滤）。给了动作历史就按 bucket ×
    street × action 的频率表对每个 combo 做贝叶斯加权，更贴近 solver 在当前
    节点的 subrange。
    """
    hero_range = _range_for(position, facing)

    # Cards already on the table (including hero's known holding, if any).
    blocked: set = set()
    if hero_known_cards:
        blocked.update(hero_known_cards)
    if board:
        blocked.update(board)

    totals = {b: 0.0 for b in _BUCKETS}
    total_w = 0.0

    for cat in hero_range:
        for combo in _combos_for_category(cat):
            if combo[0] in blocked or combo[1] in blocked:
                continue
            try:
                bucket = categorize_cards(combo, board)
            except Exception:
                log.exception(
                    "hero range distribution bucket failed combo=%s board=%s",
                    [str(c) for c in combo],
                    [str(c) for c in board],
                )
                continue
            weight = _reach_prob(combo, board, my_prev_actions or {}, is_pfr)
            if weight <= 1e-9:
                continue
            totals[bucket] += weight
            total_w += weight

    if total_w <= 1e-9:
        # Degenerate — return a uniform fallback so α-gate doesn't crash.
        return {b: 1.0 / len(_BUCKETS) for b in _BUCKETS}

    return {b: c / total_w for b, c in totals.items()}


def value_bluff_split(dist: Dict[str, float]) -> tuple[float, float]:
    """Split bucket distribution into value-mass and bluff-mass for α-gate.

    Value = {nuts, strong}; bluff = {draw, weak_draw, air}. Medium is
    excluded (it's check-call territory, not typically in a polarized bet
    range).
    """
    value = dist.get('nuts', 0.0) + dist.get('strong', 0.0)
    bluff = dist.get('draw', 0.0) + dist.get('weak_draw', 0.0) + dist.get('air', 0.0)
    return value, bluff
