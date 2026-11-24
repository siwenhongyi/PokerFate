#!/usr/bin/env python3
"""Fit what a pre-selected action says about a player (pokerfate/strategy/pre_action.py).

Source: the headless wire log, which has ``ActionNotifyBRC.pre_action_result`` for every seat
of every hand since the first day.  Humans only (``RobotRegistry.is_robot``), the bot's own
seat left out.  Reads follow ``pre_action.update_read`` — the same function the bot uses.

Fitted, each with a hold-out report (first 70% of hands by time fit, last 30% score):

* ``range``        P(pre-selected | bucket) / P(pre-selected) for checks and calls per street,
                   from hands shown at showdown, shrunk towards 1;
* ``fold_shift``   log-odds of folding to a bet added by each read (logistic regression with
                   the bet size, the street, the number of players, the player's own earlier
                   actions and his past fold rate as covariates);
* ``raise_factor`` share of the normal raise frequency left under each read;
* ``bet_shift``    log-odds of betting when nothing is owed, same way;
* ``response``     offsets per answer class for the solver path's response model.

    .venv/bin/python -m scripts.fit_pre_action                      # report only
    .venv/bin/python -m scripts.fit_pre_action --out pokerfate/data/runtime_calibration/pre_action_fit.json

The log holds the account's login key: only the message types named in ``_TYPES`` are parsed
and no raw line is ever printed.
"""
from __future__ import annotations

import argparse
import ast
import json
import math
import re
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
from scipy.optimize import minimize

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pokerfate.core.card import Card  # noqa: E402
from pokerfate.core.robots import DEFAULT_PATH as ROBOTS_PATH, RobotRegistry  # noqa: E402
from pokerfate.strategy import pre_action  # noqa: E402
from pokerfate.strategy.range_v2 import hand_categorizer as hcat  # noqa: E402
from pokerfate.strategy.range_v2.formula_fit import CAT_ORDER  # noqa: E402

DEFAULT_LOG = ROOT / "pf_intercept" / "logs" / "headless.log"
_TYPES = ("pb.DealerInfoRSP", "pb.ActionBRC", "pb.ActionNotifyBRC", "pb.RoundStartBRC",
          "pb.HandCardRSP", "pb.WinnerRSP", "pb.ShowHandRSP", "pb.EnterRoomRSP", "pb.LeaveRoomRSP")
_LINE = re.compile(r"^(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d),(\d+) \[\w+\] \S+ \[S→C\] (pb\.\w+) (\{.*\})\s*$")
_HOLDEM = 10010101
_FOLDS, _CHECKS, _POSTS = (1, 12, 16), (2, 13), (8, 9, 10, 11, 14)
_SYSTEM = (12, 13, 16)
_RANK = {2: "2", 3: "3", 4: "4", 5: "5", 6: "6", 7: "7", 8: "8", 9: "9", 10: "T", 11: "J", 12: "Q", 13: "K", 14: "A"}
_SUIT = {1: "d", 2: "c", 3: "h", 4: "s", 0: "d"}
STREET = {1: "preflop", 2: "flop", 3: "turn", 4: "river"}
READ_KEYS = (pre_action.CHECK_NOW, pre_action.CHECK_PREV, pre_action.OPTION_PREV,
             pre_action.CALL_NOW, pre_action.CALL_PREV)
RANGE_PRIOR = 40.0          # shown hands at the pooled rate mixed into every bucket's rate
RANGE_CLIP = (0.2, 2.5)
RIDGE = 1.0


# ── the wire log ─────────────────────────────────────────────────────────────────────────

def _int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _card(code: Any) -> Optional[Card]:
    code = _int(code)
    rank, suit = _RANK.get(code % 256), _SUIT.get(code // 256)
    return Card.from_str(rank + suit) if rank and suit else None


def parse_hands(path: Path) -> List[dict]:
    """Complete hold'em hands in file order: blinds, every action with the flag of the
    notice that asked for it, board, shown cards, seat -> uid."""
    hands: List[dict] = []
    cur: Optional[dict] = None
    pending: Optional[tuple] = None
    game_type = None
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            i = line.find("[S→C] pb.")
            if i < 0:
                continue
            kind = line[i + 6:line.find(" ", i + 6)]
            if kind not in _TYPES:
                continue
            m = _LINE.match(line)
            if not m:
                continue
            try:
                msg = ast.literal_eval(m.group(4))
            except (ValueError, SyntaxError):
                continue
            if kind in ("pb.EnterRoomRSP", "pb.LeaveRoomRSP"):
                if kind == "pb.EnterRoomRSP" and _int(msg.get("code")) == 0:
                    game_type = msg.get("game_type")
                cur, pending = None, None
            elif kind == "pb.DealerInfoRSP":
                ts = time.mktime(time.strptime(m.group(1), "%Y-%m-%d %H:%M:%S"))
                cur = {"ts": ts, "game_type": game_type, "street": 1, "board": [], "posts": [], "acts": [],
                       "hero": None, "omaha": False, "show": {}, "uid": {},
                       "seats": {_int(s.get("seatid")) for s in msg.get("start_info", [])}}
                pending = None
            elif cur is None:
                continue
            elif kind == "pb.RoundStartBRC":
                cur["street"] = _int(msg.get("stage")) or cur["street"]
                if msg.get("all_board"):
                    cur["board"] = list(msg["all_board"])
                elif msg.get("board"):
                    cur["board"] = cur["board"] + list(msg["board"])
                pending = None
            elif kind == "pb.HandCardRSP":
                cur["hero"] = _int(msg.get("seatid"))
                cur["omaha"] = bool(msg.get("card3"))
            elif kind == "pb.ActionNotifyBRC":
                pending = (_int(msg.get("seatid")), pre_action.normalize(msg.get("pre_action_result")))
            elif kind == "pb.ActionBRC":
                seat, at, chips = _int(msg.get("seatid")), _int(msg.get("action_type")), _int(msg.get("chips"))
                if at in _POSTS:
                    cur["posts"].append((seat, at, chips))
                elif at in _FOLDS or at in _CHECKS or at in (3, 4, 7, 17):
                    flag = pending[1] if pending is not None and pending[0] == seat else None
                    cur["acts"].append((cur["street"], seat, at, chips, flag, _int(msg.get("hand_chips"))))
                    pending = None
            elif kind == "pb.ShowHandRSP":
                for it in msg.get("info", []):
                    if it.get("card1") and it.get("card2") and not it.get("card3"):
                        cur["show"][_int(it.get("seatid"))] = (it["card1"], it["card2"])
            elif kind == "pb.WinnerRSP":
                for p in msg.get("profit", []):
                    if p.get("uid") is not None:
                        cur["uid"][_int(p.get("seatid"))] = str(p["uid"])
                if cur["game_type"] == _HOLDEM and not cur["omaha"] and cur["acts"]:
                    hands.append(cur)
                cur, pending = None, None
    return hands


# ── rows ─────────────────────────────────────────────────────────────────────────────────

def _size(to_call: float, pot_with_bet: float) -> float:
    before = pot_with_bet - to_call
    return to_call / before if to_call > 0 and before > 0 else 0.0


def build_rows(hands: List[dict], registry: RobotRegistry) -> Dict[str, List[dict]]:
    """Three row sets, humans only: ``range`` (shown checks and calls where a pre-selection was
    possible), ``answer`` (facing a bet) and ``lead`` (nothing owed, first action of the street)."""
    out: Dict[str, List[dict]] = {"range": [], "answer": [], "lead": []}
    stat: Dict[str, Counter] = defaultdict(Counter)       # per player, earlier hands only
    for hi, h in enumerate(hands):
        seats = set(h["seats"]) | {s for s, _, _ in h["posts"]}
        bet: Counter = Counter()
        pot = 0
        for seat, _at, chips in h["posts"]:
            bet[seat] += chips
            pot += chips
        board = [_card(c) for c in h["board"]]
        folded: set = set()
        allin: set = set()
        reads: Dict[int, Optional[pre_action.Read]] = {}
        own: Dict[int, List[tuple]] = defaultdict(list)       # seat -> (street, kind)
        street_no, log = 1, []                                # log: (seat, kind) on this street
        aggressor_prev: set = set()
        aggressor_now: set = set()
        hand_stats: Dict[str, Counter] = defaultdict(Counter)
        for street, seat, at, chips, flag, hand_chips in h["acts"]:
            if street != street_no:
                street_no, bet, log = street, Counter(), []
                aggressor_prev, aggressor_now = aggressor_now, set()
            to_call = max(bet.values(), default=0) - bet[seat]
            if at in _FOLDS:
                kind = "fold"
            elif at in _CHECKS:
                kind = "check"
            elif at == 3:
                kind = "call"
            elif at == 7:
                kind = "bet"
            elif at == 4:
                kind = "raise"
            else:                                             # all-in: a call unless it tops the bet
                kind = "call" if (to_call > 0 and chips <= to_call) else ("raise" if to_call > 0 else "bet")
            uid = h["uid"].get(seat)
            human = bool(uid) and seat != h["hero"] and not registry.is_robot(uid) and at not in _SYSTEM
            name = STREET.get(street, "")
            n_active = len(seats - folded)
            key = pre_action.read_key(reads.get(seat), name)
            if human and flag is not None and street >= 2:
                st = stat[uid]
                known = min(1.0, st["hands"] / 30.0)
                mine_prev = [k for s, k in own[seat] if s == street - 1]
                mine_now = [k for s, k in own[seat] if s == street]
                aggs = [i for i, (_s, k) in enumerate(log) if k in ("bet", "raise")]
                x = {
                    "turn": float(street == 3), "river": float(street == 4),
                    "three": float(n_active == 3), "four_plus": float(n_active >= 4),
                    "prev_bet": float(any(k in ("bet", "raise") for k in mine_prev)),
                    "prev_call": float("call" in mine_prev and not any(k in ("bet", "raise") for k in mine_prev)),
                    "fold_rate": (st["folds"] + 4.0) / (st["faced"] + 8.0) - 0.5,
                    "loose": known * ((st["vpip"] / st["hands"] if st["hands"] else 0.5) - 0.5),
                    "aggression": (st["agg"] + 1.75) / (st["agg"] + st["call"] + 5.0) - 0.35,
                }
                base = {"hand": hi, "ts": h["ts"], "uid": uid, "street": name, "key": key, "x": x,
                        "nobody_allin": not (allin - folded)}
                if to_call > 0 and aggs and kind in ("fold", "call", "raise"):
                    size = min(_size(to_call, pot), 3.0)
                    x.update({
                        "size_lo": min(size, 0.5), "size_mid": min(max(size - 0.5, 0.0), 0.5),
                        "size_hi": max(size - 1.0, 0.0), "facing_raise": float(len(aggs) >= 2),
                        "checked": float("check" in mine_now),
                        "caller_before": float(any(k == "call" for _s, k in log[aggs[-1] + 1:])),
                        "bettor_bet_prev": float(log[aggs[-1]][0] in aggressor_prev),
                    })
                    out["answer"].append(dict(base, y=kind, size=size))
                elif to_call == 0 and not mine_now and kind in ("check", "bet"):
                    x.update({"first": float(not log), "checks_before": min(len(log), 3) / 3.0,
                              "other_bet_prev": float(bool(aggressor_prev - {seat}))})
                    out["lead"].append(dict(base, y=kind))
                cards = h["show"].get(seat)
                nb = {2: 3, 3: 4, 4: 5}[street]
                if (cards and kind in ("check", "call") and log and flag in (pre_action.NONE, pre_action.EXECUTED)
                        and len(board) >= nb and all(board[:nb])):
                    hole = [_card(cards[0]), _card(cards[1])]
                    if all(hole):
                        out["range"].append({
                            "hand": hi, "ts": h["ts"], "uid": uid, "street": name, "kind": kind,
                            "pre": flag == pre_action.EXECUTED, "bucket": hcat.categorize_cards(hole, board[:nb]),
                        })
            # state
            reads[seat] = pre_action.update_read(reads.get(seat), street=name, action=kind, pre_action=flag or 0)
            own[seat].append((street, kind))
            log.append((seat, kind))
            if kind in ("bet", "raise"):
                aggressor_now.add(seat)
            if kind == "fold":
                folded.add(seat)
            else:
                bet[seat] += chips
                pot += chips
                if hand_chips == 0 and chips > 0:
                    allin.add(seat)
            if uid and at not in _SYSTEM:
                hs = hand_stats[uid]
                if street == 1 and kind in ("call", "bet", "raise"):
                    hs["vpip"] = 1
                if street >= 2:
                    hs["agg"] += kind in ("bet", "raise")
                    hs["call"] += kind == "call"
                    if to_call > 0:
                        hs["faced"] += 1
                        hs["folds"] += kind == "fold"
        for uid in h["uid"].values():
            stat[uid]["hands"] += 1
        for uid, hs in hand_stats.items():
            stat[uid].update(hs)
    return out


# ── fitting ──────────────────────────────────────────────────────────────────────────────

def _probs(theta: np.ndarray, x: np.ndarray, k: int) -> np.ndarray:
    w = theta.reshape(k - 1, x.shape[1] + 1)
    z = np.concatenate([np.zeros((x.shape[0], 1)), x @ w[:, 1:].T + w[:, 0]], axis=1)
    z -= z.max(axis=1, keepdims=True)
    e = np.exp(z)
    return e / e.sum(axis=1, keepdims=True)


def softmax_fit(x: np.ndarray, y: np.ndarray, k: int, ridge: float = RIDGE) -> np.ndarray:
    """Weights (k-1 rows: intercept, then one per column) of a softmax with class 0 as reference."""
    n, f = x.shape
    onehot = np.eye(k)[y]

    def objective(theta: np.ndarray) -> tuple:
        w = theta.reshape(k - 1, f + 1)
        p = _probs(theta, x, k)
        nll = -np.log(np.clip(p[np.arange(n), y], 1e-12, 1.0)).sum() + 0.5 * ridge * (w[:, 1:] ** 2).sum()
        d = (p - onehot)[:, 1:]
        grad = np.zeros_like(w)
        grad[:, 0] = d.sum(axis=0)
        grad[:, 1:] = d.T @ x + ridge * w[:, 1:]
        return nll, grad.ravel()

    res = minimize(objective, np.zeros((k - 1) * (f + 1)), jac=True, method="L-BFGS-B", options={"maxiter": 3000})
    return res.x.reshape(k - 1, f + 1)


def clustered(values: np.ndarray, clusters: List[str]) -> tuple:
    """Mean and its standard error with one player's rows counted as one cluster."""
    n = len(values)
    if n == 0:
        return float("nan"), float("nan")
    mean = float(values.mean())
    sums: Dict[str, float] = defaultdict(float)
    count: Counter = Counter()
    for v, c in zip(values, clusters):
        sums[c] += float(v)
        count[c] += 1
    g = len(sums)
    var = sum((sums[c] - count[c] * mean) ** 2 for c in sums)
    return mean, math.sqrt(var) / n * math.sqrt(g / max(1, g - 1))


def _design(rows: List[dict], names: List[str], keys: tuple) -> np.ndarray:
    return np.array([[r["x"].get(n, 0.0) for n in names] + [float(r["key"] == k) for k in keys]
                     for r in rows], dtype=float)


def fit_reads(rows: List[dict], classes: tuple, names: List[str], keys: tuple, cut: float) -> dict:
    """Softmax of the answer on the covariates plus one indicator per read; the indicator
    weights are the result.  Also scores the read indicators on the hands after ``cut``."""
    k = len(classes)
    y = np.array([classes.index(r["y"]) for r in rows])
    full = softmax_fit(_design(rows, names, keys), y, k)
    out = {"rows": len(rows), "weights": {}, "holdout": {}}
    for j, key in enumerate(keys):
        n_key = sum(r["key"] == key for r in rows)
        out["weights"][key] = {"rows": n_key,
                               **{classes[c + 1]: round(float(full[c, 1 + len(names) + j]), 4) for c in range(k - 1)}}
    train = [r for r in rows if r["ts"] < cut]
    test = [r for r in rows if r["ts"] >= cut]
    if train and test:
        yt = np.array([classes.index(r["y"]) for r in train])
        ye = np.array([classes.index(r["y"]) for r in test])
        with_reads = softmax_fit(_design(train, names, keys), yt, k)
        without = softmax_fit(_design(train, names, ()), yt, k)
        p1 = _probs(with_reads.ravel(), _design(test, names, keys), k)
        p0 = _probs(without.ravel(), _design(test, names, ()), k)
        gain = np.log(np.clip(p1[np.arange(len(ye)), ye], 1e-12, 1)) - np.log(np.clip(p0[np.arange(len(ye)), ye], 1e-12, 1))
        for key in keys:
            mask = np.array([r["key"] == key for r in test])
            if mask.sum() < 10:
                continue
            mean, se = clustered(gain[mask], [r["uid"] for r, m in zip(test, mask) if m])
            out["holdout"][key] = {
                "rows": int(mask.sum()), "gain": round(mean, 4), "ci95": round(1.96 * se, 4),
                "actual": {c: round(float((ye[mask] == i).mean()), 3) for i, c in enumerate(classes)},
                "without": {c: round(float(p0[mask, i].mean()), 3) for i, c in enumerate(classes)},
                "with": {c: round(float(p1[mask, i].mean()), 3) for i, c in enumerate(classes)},
            }
    return out


def fit_range(rows: List[dict], cut: float) -> dict:
    out: dict = {"ratio": {}, "counts": {}, "holdout": {}}
    gains: List[float] = []
    who: List[str] = []
    for kind in ("check", "call"):
        for street in ("flop", "turn", "river"):
            part = [r for r in rows if r["kind"] == kind and r["street"] == street]

            def ratios(sel: List[dict]) -> Optional[Dict[str, float]]:
                n = Counter(r["bucket"] for r in sel)
                k = Counter(r["bucket"] for r in sel if r["pre"])
                total, pre = sum(n.values()), sum(k.values())
                if pre < 30:
                    return None
                rate = pre / total
                lo, hi = RANGE_CLIP
                return {b: float(min(hi, max(lo, ((k[b] + RANGE_PRIOR * rate) / (n[b] + RANGE_PRIOR)) / rate)))
                        for b in CAT_ORDER}

            fitted = ratios(part)
            if fitted is None:
                continue
            out["ratio"].setdefault(kind, {})[street] = {b: round(v, 3) for b, v in fitted.items()}
            out["counts"].setdefault(kind, {})[street] = {
                "shown": len(part), "pre_selected": sum(r["pre"] for r in part),
                "pre_by_bucket": dict(Counter(r["bucket"] for r in part if r["pre"])),
            }
            train = [r for r in part if r["ts"] < cut]
            test = [r for r in part if r["ts"] >= cut and r["pre"]]
            held = ratios(train)
            if held is None or not test:
                continue
            base = Counter(r["bucket"] for r in train)
            total = sum(base.values())
            q0 = {b: (base[b] + 1.0) / (total + len(CAT_ORDER)) for b in CAT_ORDER}
            norm = sum(q0[b] * held[b] for b in CAT_ORDER)
            for r in test:
                gains.append(math.log(q0[r["bucket"]] * held[r["bucket"]] / norm) - math.log(q0[r["bucket"]]))
                who.append(r["uid"])
    if gains:
        mean, se = clustered(np.array(gains), who)
        out["holdout"] = {"rows": len(gains), "gain": round(mean, 4), "ci95": round(1.96 * se, 4)}
    return out


def raise_factors(rows: List[dict]) -> Dict[str, float]:
    """Raise frequency under each read over the normal one, among players who do not fold."""
    stay = [r for r in rows if r["y"] != "fold"]
    normal = [r for r in stay if r["key"] is None]
    base = sum(r["y"] == "raise" for r in normal) / max(1, len(normal))
    out: Dict[str, float] = {}
    for key in READ_KEYS:
        part = [r for r in stay if r["key"] == key]
        if len(part) < 20 or base <= 0:
            continue
        rate = (sum(r["y"] == "raise" for r in part) + 10.0 * base) / (len(part) + 10.0)
        out[key] = round(min(1.0, rate / base), 3)
    return out


def fold_rates(rows: List[dict]) -> dict:
    """How often one player without a read folds to a bet (not a raise): street x number of
    opponents the bettor has (1, 2, 3+) x bet size (small < 0.35 pot <= mid < 0.8 <= big).
    Cells are shrunk towards the street's rate for that number of opponents."""
    out: dict = {}
    plain = [r for r in rows if r["key"] is None and not r["x"]["facing_raise"]]
    for street in ("flop", "turn", "river"):
        for n, pick in (("1", lambda x: not x["three"] and not x["four_plus"]),
                        ("2", lambda x: bool(x["three"])), ("3", lambda x: bool(x["four_plus"]))):
            cell = [r for r in plain if r["street"] == street and pick(r["x"])]
            if len(cell) < 50:
                continue
            rate = sum(r["y"] == "fold" for r in cell) / len(cell)
            sizes = {}
            for name, lo, hi in (("small", 0.0, 0.35), ("mid", 0.35, 0.8), ("big", 0.8, 99.0)):
                part = [r for r in cell if lo <= r["size"] < hi]
                sizes[name] = round((sum(r["y"] == "fold" for r in part) + 20.0 * rate) / (len(part) + 20.0), 4)
            out.setdefault(street, {})[n] = dict(sizes, rows=len(cell))
    return out


ANSWER_X = ["turn", "river", "three", "four_plus", "size_lo", "size_mid", "size_hi", "facing_raise", "checked",
            "caller_before", "bettor_bet_prev", "prev_bet", "prev_call", "fold_rate", "loose", "aggression"]
LEAD_X = ["turn", "river", "three", "four_plus", "first", "checks_before", "other_bet_prev", "prev_bet",
          "prev_call", "fold_rate", "loose", "aggression"]


def fit_all(rows: Dict[str, List[dict]], cut: float) -> dict:
    answers = rows["answer"]
    for r in answers:
        r["fold"] = "fold" if r["y"] == "fold" else "stay"
    fold = fit_reads([dict(r, y=r["fold"]) for r in answers], ("stay", "fold"), ANSWER_X, READ_KEYS, cut)
    lead_keys = (pre_action.CHECK_PREV, pre_action.OPTION_PREV, pre_action.CALL_PREV)
    lead = fit_reads(rows["lead"], ("check", "bet"), LEAD_X, lead_keys, cut)
    late = ("turn", "river")
    resp_answer = fit_reads([r for r in answers if r["street"] in late], ("fold", "call", "raise"),
                            ANSWER_X, (pre_action.CHECK_PREV,), cut)
    resp_lead = fit_reads([r for r in rows["lead"] if r["street"] in late and not r["x"]["first"]],
                          ("check", "bet"), LEAD_X, (pre_action.CHECK_PREV,), cut)
    rng = fit_range(rows["range"], cut)
    a = resp_answer["weights"][pre_action.CHECK_PREV]
    b = resp_lead["weights"][pre_action.CHECK_PREV]
    response = {
        "facing_bet": {s: {pre_action.CHECK_PREV: {"call": a["call"], "raise": a["raise"]}} for s in late},
        "checked_to": {s: {pre_action.CHECK_PREV: {"bet": b["bet"]}} for s in late},
    }
    return {
        "range": rng["ratio"],
        "fold_shift": {k: v["fold"] for k, v in fold["weights"].items() if v["rows"] >= 100},
        "fold_rate": fold_rates(answers),
        "raise_factor": raise_factors(answers),
        "bet_shift": {k: v["bet"] for k, v in lead["weights"].items() if v["rows"] >= 100},
        "response": response,
        "evidence": {
            "range": {"counts": rng["counts"], "holdout": rng["holdout"]},
            "fold": fold, "bet": lead, "response_answer": resp_answer, "response_lead": resp_lead,
        },
    }


def main(argv: Optional[list] = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--log", default=str(DEFAULT_LOG))
    ap.add_argument("--registry", default=str(ROBOTS_PATH))
    ap.add_argument("--out", default="", help="write the fit file here (omit to only report)")
    args = ap.parse_args(argv)

    hands = parse_hands(Path(args.log))
    registry = RobotRegistry(args.registry, autosave=False)
    rows = build_rows(hands, registry)
    cut = float(np.quantile([h["ts"] for h in hands], 0.70))
    result = fit_all(rows, cut)
    stamp = lambda ts: time.strftime("%Y-%m-%dT%H:%M", time.localtime(ts))
    result = {
        "version": 1,
        "fitted": {"hands": len(hands), "from": stamp(hands[0]["ts"]), "to": stamp(hands[-1]["ts"]),
                   "holdout_from": stamp(cut),
                   "rows": {k: len(v) for k, v in rows.items()}},
        **result,
    }
    print("hands", len(hands), "| rows", result["fitted"]["rows"], "| hold-out from", result["fitted"]["holdout_from"])
    print("range ratios (nuts, strong, medium, draw, weak_draw, air):")
    for kind, per in result["range"].items():
        for street, row in per.items():
            c = result["evidence"]["range"]["counts"][kind][street]
            print(f"  {kind:5s} {street:5s} " + " ".join(f"{row[b]:5.2f}" for b in CAT_ORDER)
                  + f"   shown {c['shown']} pre-selected {c['pre_selected']}")
    print("  hold-out, pre-selected rows:", result["evidence"]["range"]["holdout"])
    for title, block, cls in (("fold to a bet", "fold", "fold"), ("bet when nothing is owed", "bet", "bet")):
        print(title + ": log-odds per read | hold-out")
        ev = result["evidence"][block]
        for key, w in ev["weights"].items():
            print(f"  {key:12s} rows {w['rows']:5d} shift {w[cls]:+.3f} | {ev['holdout'].get(key, '-')}")
    print("fold rate of one player without a read (small / mid / big bet):")
    for street, per in result["fold_rate"].items():
        print("  " + street + "  " + "  ".join(
            f"{n} opp {c['small']:.2f}/{c['mid']:.2f}/{c['big']:.2f} (n={c['rows']})" for n, c in per.items()))
    print("raise factor:", result["raise_factor"])
    print("response offsets:", json.dumps(result["response"]))
    if args.out:
        Path(args.out).write_text(json.dumps(result, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print("written", args.out)


if __name__ == "__main__":
    main()
