#!/usr/bin/env python3
"""Fit the opponent response model (pokerfate/decision/response_model.py) to the decision logs.

Rows: every decision of a human opponent on the turn or river of a heads-up pot that is
either an answer to a bet or raise (fold / call / raise) or follows a check by the other
player (check / bet).  The features come from ``response_model.response_features`` — the
same function the solver path calls — fed with what the log recorded at the time: the
range tracker's bucket shares before the action and its player features.  Those are only
in the logs written by the fitted range layers, so rows start at ``--since``.

Left out, by the same rule the rest of the learning follows: house robots, and every hand
dealt at a table the bot would leave (pokerfate.core.robots.table_verdict).

    .venv/bin/python -m scripts.fit_response_model \\
        --logs pokerfate/logs/archive/2026-11-1[5-8].pokerfate.bak.log pokerfate/logs/pokerfate.log \\
        --rows-out rows.jsonl                      # parse once, keep the rows
    .venv/bin/python -m scripts.fit_response_model --rows rows.jsonl --holdout-from 2026-11-18T00:00 \\
        --out candidate.json                       # fit the older part, report on the newer
    .venv/bin/python -m scripts.fit_response_model --rows rows.jsonl --ridge 3 \\
        --out pokerfate/data/runtime_calibration/response_model.json    # final fit on everything

The ridge penalty pulls the weights (not the intercepts) to 0; without ``--ridge`` it is
the one that predicts best out of fold, the folds being consecutive blocks of rows.
Error bars are clustered by player: one player's answers are not independent.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
from collections import Counter, defaultdict
from multiprocessing import Pool
from pathlib import Path
from typing import Any, Iterable, Optional

import numpy as np
from scipy.optimize import minimize

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pokerfate.decision.response_model import (  # noqa: E402
    CHECKED_TO, CLASSES, FACING_BET, FEATURES, STREETS, bet_size, response_features,
)

DEFAULT_SINCE = "2026-11-15T17:01"     # first session with both fitted range layers
RIDGES = (0.3, 1.0, 3.0, 10.0, 30.0)
FOLDS = 5
KEEP = 0.91


# ── rows ─────────────────────────────────────────────────────────────────────────────────

def _traces(path: Path) -> list:
    """Per hand, in file order, what the log recorded for each opponent action."""
    from analysis import pflog

    out: list = []
    cur = None
    for d in pflog.iter_events(path):
        e = d.get("event")
        if e == "decision_engine_enabled":
            cur = None
        elif e == "hand_start":
            cur = {"hand": d["hand"], "acts": []}
            out.append(cur)
        elif e == "opponent_action" and cur is not None and d.get("hand") == cur["hand"]:
            trace = d.get("layer_trace") or {}
            cur["acts"].append({
                "player": d.get("player"), "street": d.get("street"), "action": d.get("action"),
                "pre": (trace.get("layers") or {}).get("pre"), "features": trace.get("features"),
            })
    return out


def rows_of_log(path: str) -> tuple:
    os.environ.setdefault("PYTEST_CURRENT_TEST", "scripts/fit_response_model.py")   # no autosave, no log files
    from analysis import pflog
    from analysis.robot_logs import is_robot
    from pokerfate.core.robots import table_verdict

    p = Path(path)
    hands, _ = pflog.parse_file(p)
    traces = _traces(p)
    stats: Counter = Counter()
    rows: list = []
    if len(traces) != len(hands):
        stats["file_misaligned"] += 1
        return rows, dict(stats)
    for h, tr in zip(hands, traces):
        if tr["hand"] != h["hand"] or not h.get("result") or h.get("street_mismatch"):
            stats["hand_unusable"] += 1
            continue
        hero = h["hero_name"]
        ids = {q["name"]: q["id"] for q in h["players"]}
        robots = {n for n in ids if n != hero and is_robot(ids[n])}
        humans = len([n for n in ids if n != hero]) - len(robots)
        if robots and table_verdict(humans, len(robots)) != "stay":
            stats["hand_at_a_table_to_leave"] += 1
            continue
        opp_acts = [a for a in h["actions"] if not a["hero"]]
        raw = [t for t in tr["acts"] if t["player"] in ids]
        if len(raw) != len(opp_acts) or any(
                t["player"] != a["who"] or t["street"] != a["street"] or t["action"] != a["act"]
                for t, a in zip(raw, opp_acts)):
            stats["hand_trace_mismatch"] += 1
            continue
        raw_of = {a["i"]: t for t, a in zip(raw, opp_acts)}
        own: dict = defaultdict(list)
        player_feat: dict = {}
        first_actor: dict = {}
        folded: set = set()
        for a in h["actions"]:
            name, street = a["who"], a["street"]
            t = raw_of.get(a["i"])
            if t is not None and isinstance(t.get("features"), dict):
                player_feat[name] = {k: float(t["features"].get(k, 0.0) or 0.0) for k in ("known", "tight", "aggressive")}
            if street != "preflop":
                first_actor.setdefault(street, name)
            alive = [n for n in ids if n not in folded]
            if (not a["hero"] and street in STREETS and len(alive) == 2 and name not in robots and t is not None):
                other = next(n for n in alive if n != name)
                kind = y = None
                if a["to_call"] > 0 and a["act"] in ("fold", "call", "raise"):
                    kind, y = FACING_BET, a["act"]
                elif (a["to_call"] <= 0 and a["act"] in ("check", "raise")
                      and any(s == street and k == "check" for s, k in own[other])):
                    kind, y = CHECKED_TO, ("bet" if a["act"] == "raise" else "check")
                if kind is not None:
                    if not isinstance(t.get("pre"), dict) or name not in player_feat:
                        stats["row_without_recorded_features"] += 1
                    else:
                        size = bet_size(to_call=a["to_call"], pot_with_bet=a["pot_before"]) if kind == FACING_BET else 0.0
                        feats = response_features(
                            kind=kind, street=street, size=size, facing_raise=a["raises_before"] >= 2,
                            in_position=first_actor.get(street) != name,
                            own_actions=own[name], opponent_actions=own[other],
                            bucket_dist=t["pre"], player=player_feat[name],
                        )
                        rows.append({
                            "ts": a.get("ts") or h["ts"], "key": h["key"], "pid": ids[name], "kind": kind,
                            "street": street, "y": y, "size": round(size, 4), "vs_hero": other == hero,
                            "pot_bb": round(a["pot_before"] / (h["bb"] or 1.0), 2),
                            "x": {k: round(v, 5) for k, v in feats.items()},
                        })
            own[name].append((street, a["kind"]))
            if a["act"] == "fold":
                folded.add(name)
    stats["hands"] = len(hands)
    stats["rows"] = len(rows)
    return rows, dict(stats)


def build_rows(logs: Iterable[str], since: str, workers: int = 4) -> list:
    rows: list = []
    total: Counter = Counter()
    with Pool(max(1, min(workers, 4))) as pool:
        for part, stats in pool.imap(rows_of_log, list(logs)):
            rows.extend(part)
            total.update(stats)
    rows = [r for r in rows if (r["ts"] or "") >= since]
    rows.sort(key=lambda r: r["ts"])
    print("parse:", dict(total), "| rows since", since, ":", len(rows))
    return rows


# ── model ────────────────────────────────────────────────────────────────────────────────

def design(rows: list, kind: str) -> tuple:
    names = FEATURES[kind]
    x = np.array([[float(r["x"].get(n, 0.0)) for n in names] for r in rows], dtype=float).reshape(len(rows), len(names))
    y = np.array([CLASSES[kind].index(r["y"]) for r in rows], dtype=int)
    return x, y


def _probs(theta: np.ndarray, x: np.ndarray, k: int) -> np.ndarray:
    """theta: (k-1) x (1 + features), reference class first."""
    w = theta.reshape(k - 1, x.shape[1] + 1)
    scores = np.concatenate([np.zeros((len(x), 1)), w[:, :1].T + x @ w[:, 1:].T], axis=1)
    scores -= scores.max(axis=1, keepdims=True)
    e = np.exp(scores)
    return e / e.sum(axis=1, keepdims=True)


def fit(x: np.ndarray, y: np.ndarray, k: int, ridge: float) -> np.ndarray:
    n, f = x.shape
    onehot = np.eye(k)[y]

    def objective(theta: np.ndarray) -> tuple:
        p = _probs(theta, x, k)
        w = theta.reshape(k - 1, f + 1)
        nll = -np.log(np.clip(p[np.arange(n), y], 1e-12, 1.0)).sum() + 0.5 * ridge * (w[:, 1:] ** 2).sum()
        err = (p - onehot)[:, 1:]                                   # n x (k-1)
        grad = np.concatenate([err.sum(axis=0)[:, None], err.T @ x], axis=1)
        grad[:, 1:] += ridge * w[:, 1:]
        return nll, grad.ravel()

    res = minimize(objective, np.zeros((k - 1) * (f + 1)), jac=True, method="L-BFGS-B", options={"maxiter": 2000})
    return res.x


def row_nll(p: np.ndarray, y: np.ndarray) -> np.ndarray:
    return -np.log(np.clip(p[np.arange(len(y)), y], 1e-12, 1.0))


def clustered(values: np.ndarray, clusters: np.ndarray) -> tuple:
    """Mean and its standard error with rows of one player kept together."""
    sums: dict = defaultdict(float)
    for v, c in zip(values, clusters):
        sums[c] += float(v)
    n = len(values)
    mean = float(values.mean()) if n else float("nan")
    by: dict = defaultdict(list)
    for v, c in zip(values, clusters):
        by[c].append(float(v) - mean)
    se = math.sqrt(sum(sum(vs) ** 2 for vs in by.values())) / n if n else float("nan")
    return mean, se


def pick_ridge(x: np.ndarray, y: np.ndarray, k: int) -> tuple:
    n = len(y)
    edges = [int(round(i * n / FOLDS)) for i in range(FOLDS + 1)]
    scores = {}
    for ridge in RIDGES:
        total = 0.0
        for lo, hi in zip(edges, edges[1:]):
            mask = np.ones(n, dtype=bool)
            mask[lo:hi] = False
            theta = fit(x[mask], y[mask], k, ridge)
            total += row_nll(_probs(theta, x[~mask], k), y[~mask]).sum()
        scores[ridge] = total / n
    best = min(scores, key=scores.get)
    return best, scores


def baseline_probs(x_train_y: np.ndarray, n: int, k: int) -> np.ndarray:
    freq = np.bincount(x_train_y, minlength=k) / max(1, len(x_train_y))
    return np.tile(freq, (n, 1))


def to_spec(theta: np.ndarray, kind: str) -> dict:
    names = FEATURES[kind]
    k = len(CLASSES[kind])
    w = theta.reshape(k - 1, len(names) + 1)
    return {answer: {"intercept": round(float(w[i, 0]), 5),
                     "weights": {n: round(float(v), 5) for n, v in zip(names, w[i, 1:])}}
            for i, answer in enumerate(CLASSES[kind][1:])}


def _size_bucket(s: float) -> str:
    return "<=40%" if s <= 0.4 else "40-70%" if s <= 0.7 else "70-105%" if s <= 1.05 else ">105%"


def calibration(rows: list, p: np.ndarray, kind: str, title: str) -> list:
    """Predicted vs actual frequency of each answer in a few slices of the rows."""
    out = []
    first = CLASSES[kind][0]
    slices: list = [("all", lambda r: True)]
    if kind == FACING_BET:
        for b in ("<=40%", "40-70%", "70-105%", ">105%"):
            slices.append((f"size {b}", lambda r, b=b: _size_bucket(r["size"]) == b and not r["x"]["facing_raise"]))
        slices += [("facing a raise", lambda r: bool(r["x"]["facing_raise"])),
                   ("called twice before", lambda r: bool(r["x"]["called_twice"])),
                   ("called the street before", lambda r: bool(r["x"]["prev_call"])),
                   ("bettor is hero", lambda r: bool(r["vs_hero"]))]
    else:
        slices += [("checker bet the street before", lambda r: bool(r["x"]["opp_bet_prev"])),
                   ("after hero's check", lambda r: bool(r["vs_hero"]))]
    slices += [("known player", lambda r: r["x"]["known"] >= 0.7), ("new player", lambda r: r["x"]["known"] < 0.3),
               ("strong range (nuts+strong >= 35%)", lambda r: r["x"]["nuts"] + r["x"]["strong"] >= 0.35),
               ("weak range (nuts+strong < 15%)", lambda r: r["x"]["nuts"] + r["x"]["strong"] < 0.15)]
    print(f"   {title}: predicted vs actual")
    for name, f in slices:
        idx = [i for i, r in enumerate(rows) if f(r)]
        if len(idx) < 40:
            continue
        parts = []
        for j, answer in enumerate(CLASSES[kind]):
            pred = float(p[idx, j].mean())
            act = sum(1 for i in idx if rows[i]["y"] == answer) / len(idx)
            parts.append(f"{answer} {100 * pred:4.1f}% / {100 * act:4.1f}%")
        out.append({"slice": name, "n": len(idx), "pred_first": float(p[idx, 0].mean()),
                    "actual_first": sum(1 for i in idx if rows[i]["y"] == first) / len(idx)})
        print(f"      {name:<34} n={len(idx):5d}  " + " | ".join(parts))
    return out


def main(argv: Optional[list] = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--logs", nargs="*", default=[])
    ap.add_argument("--rows", default="", help="rows written earlier with --rows-out")
    ap.add_argument("--rows-out", default="")
    ap.add_argument("--since", default=DEFAULT_SINCE)
    ap.add_argument("--holdout-from", default="", help="rows from this timestamp on are only reported")
    ap.add_argument("--ridge", type=float, default=None)
    ap.add_argument("--min-rows", type=int, default=400, help="no model for a kind and street with fewer rows")
    ap.add_argument("--out", default="")
    args = ap.parse_args(argv)

    if args.rows:
        rows = [json.loads(line) for line in open(args.rows, encoding="utf-8") if line.strip()]
        rows = [r for r in rows if (r["ts"] or "") >= args.since]
    else:
        rows = build_rows(args.logs, args.since)
    if args.rows_out:
        with open(args.rows_out, "w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        print("wrote", len(rows), "rows ->", args.rows_out)
    if not rows:
        return
    print(f"rows {len(rows)}: {rows[0]['ts'][:16]} .. {rows[-1]['ts'][:16]}, players {len({r['pid'] for r in rows})}")

    models: dict = {}
    report: dict = {}
    for kind in (FACING_BET, CHECKED_TO):
        k = len(CLASSES[kind])
        for street in STREETS:
            part = [r for r in rows if r["kind"] == kind and r["street"] == street]
            train = [r for r in part if not args.holdout_from or r["ts"] < args.holdout_from]
            test = [r for r in part if args.holdout_from and r["ts"] >= args.holdout_from]
            tag = f"{kind}/{street}"
            print(f"\n== {tag}: {len(train)} rows to fit" + (f", {len(test)} held out" if args.holdout_from else ""))
            if len(train) < args.min_rows:
                print("   too few rows: no model")
                continue
            x, y = design(train, kind)
            freq = np.bincount(y, minlength=k) / len(y)
            print("   answers:", {a: f"{100 * f:.1f}%" for a, f in zip(CLASSES[kind], freq)})
            if args.ridge is None:
                ridge, scores = pick_ridge(x, y, k)
                print("   out-of-fold log-loss by ridge:", {r: round(s, 4) for r, s in scores.items()}, "->", ridge)
            else:
                ridge = float(args.ridge)
            theta = fit(x, y, k, ridge)
            entry: dict = {"rows": len(train), "ridge": ridge,
                           "answers": {a: round(float(f), 4) for a, f in zip(CLASSES[kind], freq)}}
            if test:
                xt, yt = design(test, kind)
                pt = _probs(theta, xt, k)
                base = baseline_probs(y, len(yt), k)
                pids = np.array([r["pid"] for r in test])
                gain, se = clustered(row_nll(base, yt) - row_nll(pt, yt), pids)
                print(f"   held out: log-loss {row_nll(pt, yt).mean():.4f} vs {row_nll(base, yt).mean():.4f} with the plain frequencies"
                      f" -> better by {gain:+.4f} +/- {1.96 * se:.4f} per answer ({len({r['pid'] for r in test})} players)")
                entry["holdout"] = {"rows": len(test), "logloss": round(float(row_nll(pt, yt).mean()), 4),
                                    "logloss_frequencies": round(float(row_nll(base, yt).mean()), 4),
                                    "gain": round(gain, 4), "gain_ci95": round(1.96 * se, 4)}
                if kind == FACING_BET:
                    # fold or not, against the fold rate that makes a pure bluff break even (what an
                    # equilibrium sits around): the yardstick the hand-written layer was compared with
                    size = np.array([r["size"] for r in test])
                    ref = np.clip(size / (KEEP + size), 0.02, 0.98)
                    folded = (yt == 0)
                    nll_ref = -np.where(folded, np.log(ref), np.log(1.0 - ref))
                    nll_fit = -np.where(folded, np.log(np.clip(pt[:, 0], 1e-12, 1.0)), np.log(np.clip(1.0 - pt[:, 0], 1e-12, 1.0)))
                    g2, se2 = clustered(nll_ref - nll_fit, pids)
                    print(f"   held out, fold or not: log-loss {nll_fit.mean():.4f} vs {nll_ref.mean():.4f} with the break-even fold rate"
                          f" -> better by {g2:+.4f} +/- {1.96 * se2:.4f}; break-even says fold {100 * ref.mean():.1f}%, fitted {100 * pt[:, 0].mean():.1f}%, actual {100 * folded.mean():.1f}%")
                    entry["holdout"].update({"fold_logloss": round(float(nll_fit.mean()), 4),
                                             "fold_logloss_break_even": round(float(nll_ref.mean()), 4),
                                             "fold_gain_vs_break_even": round(g2, 4), "fold_gain_ci95": round(1.96 * se2, 4)})
                entry["holdout"]["calibration"] = calibration(test, pt, kind, "held out")
            else:
                calibration(train, _probs(theta, x, k), kind, "in sample")
            models.setdefault(kind, {})[street] = to_spec(theta, kind)
            report[tag] = entry
            w = theta.reshape(k - 1, len(FEATURES[kind]) + 1)
            for i, answer in enumerate(CLASSES[kind][1:]):
                print(f"   {answer} vs {CLASSES[kind][0]}: intercept {w[i, 0]:+.2f} | "
                      + " ".join(f"{n} {v:+.2f}" for n, v in zip(FEATURES[kind], w[i, 1:])))

    if args.out:
        payload = {
            "version": 1,
            "fitted_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "rows_from": rows[0]["ts"], "rows_to": rows[-1]["ts"],
            "holdout_from": args.holdout_from or None,
            "features": {kind: list(FEATURES[kind]) for kind in FEATURES},
            "classes": {kind: list(CLASSES[kind]) for kind in CLASSES},
            "models": models,
            "report": report,
        }
        Path(args.out).write_text(json.dumps(payload, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print("\nwrote", args.out)


if __name__ == "__main__":
    main()
