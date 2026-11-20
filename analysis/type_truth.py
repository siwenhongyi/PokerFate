"""Truth about bets nobody called.

A showdown only shows the hands that got there.  A player who bets the flop with nothing and
gives up, or whose bet makes everybody fold, never shows — so ranges fitted to showdowns alone
learn that bets are stronger than they are.

When a pot is won without showdown the server still names the winner's hand type (高牌 / 一对 /
两对 / ...; ``hand_result.hand_combos``, carried into the replay by scripts/json_log_to_replay).
That winner is the last player who bet or raised, and whether the others fold does not depend
on his cards: these hands are an unbiased sample of what bets are made of.

The extractor (bucket mode) writes one ``uncontested_win`` row per such pot, for the winner's
last bet: what the tracker saw before it (bucket shares, and inside each bucket how much of it
is each hand type), the type shares of the range it ended with, and the type the server named.
``scripts/fit_likelihood_model.py`` fits on these rows together with the showdown rows.

    # how far is the formula's range from the types actually held, by street
    .venv/bin/python -m analysis.type_truth rows.jsonl [other_rows.jsonl ...]
"""
from __future__ import annotations

import argparse
import math
from collections import defaultdict
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

TYPES = ("高牌", "一对", "两对", "三条", "顺子", "同花", "葫芦", "四条", "同花顺")
GROUPS = (("高牌", (0,)), ("一对", (1,)), ("两对及以上", (2, 3, 4, 5, 6, 7, 8)))
TRIGGER = "uncontested_win"
_EVAL7 = {"High Card": 0, "Pair": 1, "Two Pair": 2, "Trips": 3, "Straight": 4, "Flush": 5,
          "Full House": 6, "Quads": 7, "Straight Flush": 8}
_STREET_OF = {3: "flop", 4: "turn", 5: "river"}


def label_type(label: Any) -> Optional[int]:
    """Index into TYPES of a server hand label such as '一对 A A K Q 7'."""
    head = str(label or "").split(" ")[0]
    return TYPES.index(head) if head in TYPES else None


@lru_cache(maxsize=512)
def combo_types(board: Tuple[str, ...]) -> np.ndarray:
    """Hand type (index into TYPES) of each of the 1326 combos on a 3-5 card board; -1 if blocked."""
    import eval7
    from pokerfate.strategy.range_v2 import hand_combo_map as hcm

    cards = [eval7.Card(str(hcm.int_to_card(i))) for i in range(52)]
    on_board = [eval7.Card(c) for c in board]
    blocked = {str(c) for c in on_board}
    out = np.full(len(hcm.ALL_COMBOS), -1, dtype=np.int8)
    for idx, (c1, c2) in enumerate(hcm.ALL_COMBOS):
        a, b = cards[c1], cards[c2]
        if str(a) in blocked or str(b) in blocked:
            continue
        out[idx] = _EVAL7[eval7.handtype(eval7.evaluate(on_board + [a, b]))]
    return out


def type_shares(weights: np.ndarray, types: np.ndarray) -> np.ndarray:
    """Share of each hand type in a range."""
    w = np.where(types >= 0, weights, 0.0)
    total = float(w.sum())
    out = np.bincount(types[types >= 0], weights=w[types >= 0], minlength=len(TYPES))
    return out / total if total > 0 else out


def type_given_bucket(weights: np.ndarray, cats: np.ndarray, types: np.ndarray) -> np.ndarray:
    """6 x 9: inside each strength bucket of a range, the share of each hand type."""
    out = np.zeros((6, len(TYPES)))
    ok = types >= 0
    for b in range(6):
        mask = ok & (cats == b)
        mass = float(weights[mask].sum())
        if mass > 0:
            out[b] = np.bincount(types[mask], weights=weights[mask], minlength=len(TYPES)) / mass
    return out


def winner_row(hand: Dict[str, Any], tracker: Any, last_actions: Dict[int, Dict[str, Any]],
               source: str = "") -> Optional[Dict[str, Any]]:
    """The ``uncontested_win`` row of a replayed hand, or None when the hand has none.

    ``last_actions``: per player, his last recorded postflop action in this hand as the
    extractor's hook saw it (street, label, features, floor weight, board, weights before it).
    """
    from pokerfate.core.card import Card
    from pokerfate.strategy.range_v2.formula_fit import CAT_ORDER

    result = hand.get("result") or {}
    if result.get("showdown_hands"):
        return None
    winners = [str(w).split("[", 1)[0].strip() for w in (result.get("winners") or [])]
    if len(winners) != 1:
        return None
    actual = label_type((result.get("hand_combos") or {}).get(winners[0]))
    pid = next((p["id"] for p in hand.get("players", []) if p.get("name") == winners[0]), None)
    last = last_actions.get(pid) if pid is not None else None
    if actual is None or not last or last.get("label") not in ("bet", "raise_over"):
        return None
    board = [c for e in hand.get("events", []) if e.get("type") == "board" for c in e.get("cards", [])]
    street = _STREET_OF.get(len(board))
    final = getattr(tracker, "_weights", {}).get(pid)
    if street is None or street != last.get("street") or list(last.get("board") or []) != board or final is None:
        return None

    types = combo_types(tuple(board))
    cats = np.asarray(tracker.action_model._cat_indices([Card.from_str(c) for c in board], street))
    pre = np.where(types >= 0, np.asarray(last["pre_weights"], dtype=np.float64), 0.0)
    live = pre > 0
    if not live.any():
        return None
    uniform = live / live.sum()
    shares = lambda w: {cat: round(float(w[cats == i].sum() / w.sum()), 6) for i, cat in enumerate(CAT_ORDER)}
    return {
        "trigger": TRIGGER, "street": street, "board": board, "hand": hand.get("hand"),
        "session": hand.get("session"), "player_uid": str(pid), "source": source,
        "last_action": last["label"], "features": dict(last.get("features") or {}),
        "floor_lambda": last.get("lam"), "action_bet_ratio": last.get("bet_ratio"),
        "actual_type": TYPES[actual],
        "type_dist": {t: round(float(v), 6) for t, v in zip(TYPES, type_shares(np.asarray(final), types))},
        "layers": {"pre": shares(pre), "uniform": shares(uniform)},
        "type_given_bucket": np.round(type_given_bucket(pre, cats, types), 6).tolist(),
        "uniform_type_given_bucket": np.round(type_given_bucket(uniform, cats, types), 6).tolist(),
    }


# ── report ──────────────────────────────────────────────────────────────────────────────

def _clustered(values: np.ndarray, clusters: np.ndarray) -> Tuple[float, float]:
    mean = float(values.mean())
    _, index = np.unique(clusters, return_inverse=True)
    sums = np.bincount(index, weights=values - mean)
    g = len(sums)
    return mean, (float(math.sqrt(g / (g - 1) * float((sums ** 2).sum())) / len(values)) if g > 1 else 0.0)


def collect(rows) -> Dict[Tuple[str, str], List[Tuple[np.ndarray, int, str]]]:
    """(street, last action) -> [(predicted type shares, type held, player)]."""
    out: Dict[Tuple[str, str], List[Tuple[np.ndarray, int, str]]] = defaultdict(list)
    for row in rows:
        if row.get("trigger") != TRIGGER or row.get("actual_type") not in TYPES:
            continue
        dist = row.get("type_dist") or {}
        out[(row["street"], row["last_action"])].append(
            (np.array([float(dist.get(t, 0.0)) for t in TYPES]), TYPES.index(row["actual_type"]), str(row.get("player_uid"))))
    return out


def report(name: str, cells, min_rows: int = 100) -> None:
    order = {"flop": 0, "turn": 1, "river": 2}
    print(f"\n{name}\n没人跟注的下注：赢家实际牌型 vs 范围给出的占比（预测减实际，百分点；括号内为按玩家聚类的标准误）")
    print(f"{'街道 动作':18s} {'局数':>5s} | " + " | ".join(f"{g:>6s} 实际  预测-实际" for g, _ in GROUPS) + " | 每局NLL")
    total_nll, total_n = 0.0, 0
    for key in sorted(cells, key=lambda k: (order[k[0]], k[1])):
        items = cells[key]
        pred = np.array([p for p, _, _ in items])
        held = np.array([t for _, t, _ in items])
        who = np.array([w for _, _, w in items])
        nll = -np.log(np.maximum(pred[np.arange(len(held)), held], 1e-6))
        total_nll += float(nll.sum())
        total_n += len(held)
        if len(items) < min_rows:
            continue
        cols = []
        for _, members in GROUPS:
            actual = np.isin(held, members).astype(float)
            diff, se = _clustered(pred[:, list(members)].sum(axis=1) - actual, who)
            flag = "<<" if abs(100 * diff) > 3 and abs(diff) > 2 * se else "  "
            cols.append(f"{100 * actual.mean():6.1f}  {100 * diff:+6.1f} ({100 * se:.1f}){flag}")
        print(f"{key[0] + ' ' + key[1]:20s} {len(items):5d} | " + " | ".join(cols) + f" | {nll.mean():.4f}")
    if total_n:
        print(f"全部 {total_n} 局：每局 NLL {total_nll / total_n:.4f}")


def main(argv: Optional[Sequence[str]] = None) -> None:
    from analysis.range_layers import iter_rows

    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("rows", nargs="+", type=Path, help="bucket-mode rows from a replay that carries hand_combos")
    ap.add_argument("--min-rows", type=int, default=100)
    args = ap.parse_args(argv)
    for path in args.rows:
        report(str(path), collect(iter_rows([path])), args.min_rows)


if __name__ == "__main__":
    main()
