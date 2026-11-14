"""Hand-strength descriptors used to reverse-engineer the robots' rules.

``describe(hole, board)`` returns what a simple rule engine could plausibly key on:
  cls      coarse made-hand class relative to the board (air / weak pair / mid pair / top pair /
           overpair / two pair+ ...), where pairs that are on the board do not count
  hs       share of the 1,081-or-fewer random opponent holdings currently beaten (ties half)
  draw     flush draw / open-ended / gutshot on flop and turn (hole cards must take part)
"""
from __future__ import annotations

from collections import Counter
from functools import lru_cache
from itertools import combinations

import eval7

RANKS = "23456789TJQKA"
RV = {r: i for i, r in enumerate(RANKS, start=2)}
DECK = [r + s for r in RANKS for s in "cdhs"]
_TYPES = {"High Card": 0, "Pair": 1, "Two Pair": 2, "Trips": 3, "Straight": 4, "Flush": 5,
          "Full House": 6, "Quads": 7, "Straight Flush": 8}
CLS_ORDER = ["空气", "A高", "底对/小口袋对", "中对", "顶对", "超对", "两对", "三条", "顺子+"]


@lru_cache(maxsize=None)
def _card(c):
    return eval7.Card(c)


def _score(cards):
    return eval7.evaluate([_card(c) for c in cards])


def _type(cards):
    if len(cards) >= 5:
        return _TYPES[eval7.handtype(_score(cards))]
    counts = sorted(Counter(c[0] for c in cards).values(), reverse=True)
    if not counts:
        return 0
    if counts[0] == 4:
        return 7
    if counts[0] == 3:
        return 3
    if counts[0] == 2:
        return 2 if len(counts) > 1 and counts[1] == 2 else 1
    return 0


def hs_now(hole, board) -> float:
    """Share of random opponent holdings beaten right now (ties count half)."""
    dead = set(hole) | set(board)
    rest = [c for c in DECK if c not in dead]
    mine = _score(list(hole) + list(board))
    b = [_card(c) for c in board]
    win = tie = n = 0
    for x, y in combinations(rest, 2):
        s = eval7.evaluate([_card(x), _card(y)] + b)
        n += 1
        if mine > s:
            win += 1
        elif mine == s:
            tie += 1
    return (win + 0.5 * tie) / n


def _straight_draw(ranks: set) -> str:
    vals = set(ranks)
    if 14 in vals:
        vals.add(1)
    outs = 0
    for add in range(2, 15):
        if add in vals:
            continue
        v = vals | {add} | ({1} if add == 14 else set())
        if any(all(x in v for x in range(lo, lo + 5)) for lo in range(1, 11)):
            outs += 1
    return "oesd" if outs >= 2 else "gutshot" if outs == 1 else ""


def describe(hole, board) -> dict:
    hole, board = list(hole), list(board)
    cards = hole + board
    tr, btr = _type(cards), _type(board)
    hr = sorted((RV[c[0]] for c in hole), reverse=True)
    br = sorted((RV[c[0]] for c in board), reverse=True)
    brs = sorted(set(br), reverse=True)
    pocket = hr[0] == hr[1]
    out = {"tr": tr, "btr": btr, "pocket": pocket}
    # made-hand class relative to the board
    if tr - btr <= 0:
        cls = "A高" if hr[0] == 14 and tr == btr else "空气"
    elif tr >= 4:
        cls = "顺子+"
    elif tr == 3:
        cls = "三条"
    elif tr == 2 and btr == 0:
        cls = "两对"
    else:
        # exactly one pair made with hole cards (possibly on a paired board -> "two pair" by type)
        if pocket:
            cls = "超对" if hr[0] > brs[0] else "中对" if len(brs) > 1 and hr[0] > brs[-1] else "底对/小口袋对"
        else:
            hit = max((r for r in hr if r in br), default=None)
            if hit is None:
                cls = "空气"
            elif hit == brs[0]:
                cls = "顶对"
            elif hit == brs[-1] and len(brs) > 1:
                cls = "底对/小口袋对"
            else:
                cls = "中对"
    out["cls"] = cls
    out["kicker"] = hr[0] if not pocket else hr[0]
    # draws (only before the river, and only if a hole card is part of it)
    draw = ""
    if len(board) in (3, 4):
        suits = Counter(c[1] for c in cards)
        s, n = suits.most_common(1)[0]
        if n == 4 and any(c[1] == s for c in hole):
            draw = "fd"
        if tr < 4:
            with_hole = _straight_draw({RV[c[0]] for c in cards})
            board_only = _straight_draw({RV[c[0]] for c in board})
            rank_order = {"": 0, "gutshot": 1, "oesd": 2}
            if rank_order[with_hole] > rank_order[board_only]:
                draw = (draw + "+" if draw else "") + with_hole
    out["draw"] = draw
    out["hs"] = hs_now(hole, board) if board else None
    return out


def coarse(cls: str) -> str:
    if cls in ("空气", "A高"):
        return "无对"
    if cls in ("底对/小口袋对", "中对"):
        return "弱对"
    if cls in ("顶对", "超对"):
        return "顶对/超对"
    return "两对+"
