"""Build opponent hole-card combos using two-stage pure subtraction.

两阶段纯减法（业界标准，参考 Upswing Poker / GTOWizard / SplitSuit）：

Stage 1 — 翻前过滤：
  按翻前起手牌强度（_hand_strength_pct）排序，取最强 preflop_rf 比例。
  preflop_rf 由翻前行动（VPIP/PFR + raise/call/fold）决定，
  代表"这名玩家用多紧的翻前范围入局"。

Stage 2 — 翻后裁切（减法，永不增加手牌）：
  在 Stage 1 子集内，按当前牌面成牌强度排序，取最强 postflop_rf 比例。
  postflop_rf 由翻后行动（flop/turn/river 的 raise/call/check）决定，
  代表"在进入范围的手牌中，有多少与当前牌面行动一致"。

为什么必须是减法：
  range_fraction 来自对手行动信息，信息只能增加（范围只能缩小），
  不能凭空给对手"加"进他翻前就不会玩的手牌。
  22 在 2-7-9 面加注 → Stage 1 保留 22（翻前 rf 够宽时），
  Stage 2 在牌面强度上 22 排名很高（三条），得以保留——这才是正确的建模。

湿润牌面诈唬 range 修正（polarized 模式）：
  GTO raise range = 强手价值 + 半诈唬（draw），不是纯空气。
  当前若不修正，极化的 bluff 槽取"最低权益手牌"（纯空气/高牌），
  但实际上对手在湿润面加注更多携带同花/顺子听牌。

  修正逻辑：
    - 在 Stage 1 子集中找到 flush draw / open-ended straight draw 组合
    - 在 bluff_n 名额内，用 draw 组合替换等量纯空气，替换比例由牌面湿度决定
    - 牌面越湿（flush draw 概率越高）替换比例越大，最多替换 60%
    - 只替换 Stage 1 已有组合，永不增加新手牌（保持减法原则）
    - 净效果：对手 range 含更多听牌 → 我方权益被适度下调 → 更保守
"""

from __future__ import annotations

from typing import List, Set, Tuple

from pokerfate.core.card import Card
from pokerfate.strategy.range_estimator import _hand_strength_pct


# ---------------------------------------------------------------------------
# 牌面湿度与 draw 检测（仅用于 polarized bluff 槽修正）
# ---------------------------------------------------------------------------

def _board_flush_suits(board: List[Card]) -> Set[int]:
    """返回在当前公牌中出现 ≥ 2 次的花色集合（flush draw 存在的花色）。"""
    from collections import Counter
    suit_counts = Counter(c.suit for c in board)
    return {s for s, cnt in suit_counts.items() if cnt >= 2}


def _board_wetness(board: List[Card]) -> float:
    """计算牌面湿度 [0, 1]，用于决定 draw 替换比例。

    组成：
      flush draw（2张同花）+0.45
      monotone（3张同花）   +0.25（额外加成）
      connected（最大间距≤3）+0.30
    上限 1.0，河牌返回 0（draw 已定，无半诈唬意义）。
    """
    if len(board) >= 5:
        return 0.0  # 公牌完整，河牌无 draw 半诈唬
    from collections import Counter
    suit_counts = Counter(c.suit for c in board)
    max_suit = max(suit_counts.values()) if suit_counts else 0
    ranks = sorted(c.rank for c in board)
    gap = (ranks[-1] - ranks[0]) if len(ranks) >= 2 else 99

    wetness = 0.0
    if max_suit >= 2:
        wetness += 0.45
    if max_suit >= 3:
        wetness += 0.25
    if gap <= 3 and len(ranks) >= 2:
        wetness += 0.30
    return min(1.0, wetness)


def _flush_draw_combos(
    candidates: List[List[Card]],
    flush_suits: Set[int],
    exclude_indices: Set[int],
) -> List[int]:
    """从 candidates 中找到含 flush draw 的组合索引。

    条件：组合的两张牌中至少一张花色在 flush_suits 中，
    且该张牌与公牌同花（即贡献凑成听牌）。
    仅返回不在 exclude_indices 中的索引。
    """
    result = []
    for i, combo in enumerate(candidates):
        if i in exclude_indices:
            continue
        if any(c.suit in flush_suits for c in combo):
            result.append(i)
    return result


def _straight_draw_combos(
    candidates: List[List[Card]],
    board: List[Card],
    exclude_indices: Set[int],
) -> List[int]:
    """从 candidates 中找到开口顺子听牌（OESD）或顺子 combo 索引。

    判断：底牌 + 公牌中有 4 张连续点数（间距 ≤ 1）则视为 OESD。
    仅返回不在 exclude_indices 中的索引。
    """
    result = []
    board_ranks = sorted(c.rank for c in board)
    for i, combo in enumerate(candidates):
        if i in exclude_indices:
            continue
        all_ranks = sorted(set(board_ranks + [c.rank for c in combo]))
        # 检查是否有 4 张连续（任意子集）
        for start in range(len(all_ranks) - 3):
            window = all_ranks[start: start + 4]
            if window[-1] - window[0] <= 3:  # 4 张点数跨度 ≤ 3 = OESD
                result.append(i)
                break
    return result


def all_hole_combos(exclude: Set[Card]) -> List[List[Card]]:
    """All unordered 2-card hands from the deck excluding `exclude`."""
    deck = [
        Card(r, s)
        for r in range(2, 15)
        for s in range(4)
        if Card(r, s) not in exclude
    ]
    out: List[List[Card]] = []
    for i in range(len(deck)):
        for j in range(i + 1, len(deck)):
            out.append([deck[i], deck[j]])
    return out


def top_fraction_hole_combos(
    range_fraction: float,
    exclude: Set[Card],
    board: List[Card],
) -> List[List[Card]]:
    """按翻前强度取前 range_fraction 比例（单阶段，向后兼容）。"""
    rf = max(0.02, min(1.0, range_fraction))
    combos = all_hole_combos(exclude)
    if not combos:
        return []
    combos.sort(key=_hand_strength_pct, reverse=True)
    n = max(1, int(len(combos) * rf))
    return combos[:n]


def two_stage_hole_combos(
    preflop_rf: float,
    postflop_rf: float,
    exclude: Set[Card],
    board: List[Card],
    polarized: bool = True,
    street: str = "river",
) -> List[List[Card]]:
    """两阶段纯减法：先按翻前强度取 preflop_rf，再在结果内按当前权益取 postflop_rf。

    Parameters
    ----------
    preflop_rf : float
        翻前范围分数（由翻前行动压缩得到）。
    postflop_rf : float
        翻后裁切比例（在翻前范围内，由翻后行动压缩得到）。
        无翻后行动时应为 1.0（不裁切）。
    exclude : set
        已知底牌 + 公牌，不计入候选组合。
    board : list
        当前公牌，用于 Stage 2 权益排序。
    polarized : bool
        True  = raise 范围，极化：取最强 (1-bluff_ratio) + 最弱 bluff_ratio。
                GTO raise 范围 = 强手价值 + 低权益诈唬，中间手牌不参与。
        False = call 范围，线性：取权益最高的前 postflop_rf 比例。
                call 范围主要是中强手 + 听牌，不含纯诈唬。
    street : str
        当前街道，用于确定极化时的诈唬比例（河牌诈唬比例最低）。

    Stage 2 排序改用 MC 权益（_hand_equity_postflop）而非成牌强度：
    - 听牌（同花 / 顺子听牌）在翻牌 / 转牌的权益 35-40%，排名正确
    - 已成强牌排名正确
    - 比 HandEvaluator 更能反映"对手为什么会用这手牌加注/跟注"
    """
    from pokerfate.strategy.range_estimator import _hand_equity_postflop

    # Stage 1: 按翻前起手牌强度排序，取顶部 preflop_rf
    pf_rf = max(0.02, min(1.0, preflop_rf))
    all_combos = all_hole_combos(exclude)
    if not all_combos:
        return []

    all_combos.sort(key=_hand_strength_pct, reverse=True)
    n1 = max(1, int(len(all_combos) * pf_rf))
    stage1 = all_combos[:n1]

    # Stage 2: 无公牌或 postflop_rf≈1.0 时跳过（只用翻前范围）
    if not board or postflop_rf >= 0.99:
        return stage1

    po_rf = max(0.05, min(1.0, postflop_rf))

    # 按 MC 权益排序（含听牌权益）而非成牌强度
    # n_iters=30 足以区分强手/听牌/空气牌的权益层级，耗时约 3ms/combo
    stage1.sort(key=lambda c: _hand_equity_postflop(c, board, n_iters=30), reverse=True)
    n2 = max(1, int(len(stage1) * po_rf))

    if polarized:
        # Raise 范围极化：最强手（价值）+ 半诈唬/诈唬
        # GTO 最优诈唬比例随街道递减（河牌接近 1/2pot 下注约 25% bluff）
        bluff_ratio = {"flop": 0.33, "turn": 0.27, "river": 0.22}.get(street, 0.25)
        value_n = max(1, int(n2 * (1.0 - bluff_ratio)))
        bluff_n = max(0, n2 - value_n)
        value_indices = set(range(value_n))
        result = stage1[:value_n]

        if bluff_n > 0 and board and street != "river":
            # 湿润面修正：用 draw 半诈唬替换部分纯空气诈唬
            # 替换上限 = bluff_n × min(wetness × 0.6, 0.6)，最多 60% 的诈唬名额给 draw
            wetness = _board_wetness(board)
            draw_slots = int(bluff_n * min(wetness * 0.6, 0.6))

            if draw_slots > 0:
                flush_suits = _board_flush_suits(board)
                draw_idxs: List[int] = []

                # 优先取 flush draw（更常见、权益更稳定）
                if flush_suits:
                    draw_idxs = _flush_draw_combos(stage1, flush_suits, value_indices)

                # 若 flush draw 不足，补充 OESD
                if len(draw_idxs) < draw_slots:
                    straight_idxs = _straight_draw_combos(
                        stage1, board,
                        value_indices | set(draw_idxs),
                    )
                    draw_idxs = draw_idxs + straight_idxs

                # 取前 draw_slots 个（已在 stage1 范围内，保持减法原则）
                draw_idxs = draw_idxs[:draw_slots]
                air_n = bluff_n - len(draw_idxs)

                draw_combos = [stage1[i] for i in draw_idxs]
                # 空气诈唬：从 stage1 尾部取（最低权益）
                air_combos = stage1[-air_n:] if air_n > 0 else []
                result = result + draw_combos + air_combos
            else:
                result = result + stage1[-bluff_n:]
        elif bluff_n > 0:
            result = result + stage1[-bluff_n:]  # 干燥面或河牌：纯空气诈唬

        return result
    else:
        # Call 范围线性：按权益取前 n2（中强手 + 听牌）
        return stage1[:n2]
