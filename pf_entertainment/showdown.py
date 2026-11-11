"""Presentation-only Hold'em best-five groups; reuse the existing evaluator."""
from __future__ import annotations

from collections import Counter

from pokerfate.core.card import Card
from pokerfate.core.hand_evaluator import HandEvaluator, HandRank


def hand_group(hole: list, board: list, *, server_type: int = 0) -> dict:
    result = {"label": "未知牌型", "cards": [], "hole_used": [], "note": "", "source": "unknown"}
    if 1 <= server_type <= 10:
        result.update(label=HandRank(server_type - 1).cn_name(), source="server")
    if len(hole) != 2 or not all(hole):
        result["note"] = "底牌未完整公开，无法确定最佳五张"
        return result
    if len(board) < 3:
        result["note"] = "公共牌不足，尚未组成五张牌"
        if not server_type:
            result["label"] = "未成五张牌"
        return result
    try:
        cards = [Card.from_str(card) for card in hole + board]
        if len(board) > 5 or len(set(cards)) != len(cards):
            raise ValueError("invalid card set")
        # Board first prefers playing the board when equivalent combinations tie.
        score, best = HandEvaluator.best_five(cards[2:] + cards[:2])
        counts = Counter(card.rank.value for card in best)
        if score[0] in (HandRank.STRAIGHT, HandRank.STRAIGHT_FLUSH, HandRank.ROYAL_FLUSH):
            best.sort(key=lambda c: (1 if score[1] == 5 and c.rank.value == 14 else c.rank.value), reverse=True)
        else:
            best.sort(key=lambda c: (counts[c.rank.value], c.rank.value), reverse=True)
        result.update(label=HandRank(score[0]).cn_name(), cards=[str(c) for c in best],
                      hole_used=[str(c) in hole for c in best], source="calculated")
        if not any(result["hole_used"]):
            result["note"] = "公共牌成牌，未使用底牌"
    except (ValueError, KeyError, IndexError, TypeError):
        result["note"] = "牌面数据不完整，无法计算最佳五张"
    return result
