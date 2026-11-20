#!/usr/bin/env python3
"""Fit the postflop action likelihood (fitted_likelihood.py) to the hands we get to know.

Rows: extractor in bucket mode with the bucket model off (command in analysis/range_layers.py).
Every action row carries what the tracker saw and did for that update: the bucket shares before
the action, the floor-mixing weight and the uniform shares it mixes in, and the features it
computed.  The fit puts a likelihood through exactly that update,

    share_after[b] = (1 - lam) * q[b] * L[b] / Z  +  lam * uniform[b]
    L[b] = exp(base[street][b] + sum_f weight[f][b] * x[f])

and maximises the probability of what was then observed.  Two kinds of observation:

  showdown        the player's cards were shown: the bucket he held when he acted.
  uncontested win everybody folded to the player's bet, and the server named his hand type
                  (analysis/type_truth.py).  Observed is the type; inside a bucket the mix of
                  types is the one the range had before the bet.  These are the bets a showdown
                  never shows; without them the fit only sees bettors who got to showdown.

One model per action (bet / raise_over / call / check): a base per street, feature weights
shared by the streets.  A ridge penalty pulls the weights to 0; its strength is the one that
predicts best out of fold, the folds being consecutive blocks of the rows (rows arrive in
playing order, so a fold is a stretch of sessions).  ``--holdout-rows`` are only reported.

    .venv/bin/python -m scripts.fit_likelihood_model --rows older.jsonl --holdout-rows newest.jsonl \\
        --out fit.json

The range before a turn or river action depends on the likelihood used on earlier streets, so
fit, re-extract with the new file (PF_FORMULA_FIT_PATH=fit.json), and fit again: the flop is
final after one pass, the turn after two, the river after three.  The first pass starts from
rows extracted with PF_FORMULA_FIT_PATH=off or with the file in force.  ``--ridge`` pins the
penalty for the final fit on all sessions, after it was chosen with a hold-out.

``--layer preflop`` fits the preflop likelihood the same way one level down
(``preflop_model``): the truth is the preflop strength bin of the cards shown, the base is per
position group, and every hand starts uniform, so nothing has to be re-extracted — where a
player acts twice before the flop (limps, then calls a raise) the fit carries his range from
the first action to the second itself.  After a new preflop model the postflop one is refitted
on rows extracted with it: every layer is fitted on the output of the one below.

``--base`` is the file whose other layer is kept.

Error bars are clustered by player: one player's rows are not independent.
"""
from __future__ import annotations

import argparse
import copy
import json
import math
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

import numpy as np
from scipy.optimize import minimize

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from analysis.range_layers import iter_rows, slice_names  # noqa: E402
from analysis.type_truth import GROUPS, TRIGGER as UNCONTESTED, TYPES  # noqa: E402
from pokerfate.strategy.range_v2.fitted_likelihood import (  # noqa: E402
    ACTIONS, FEATURES, PREFLOP_ACTIONS, PREFLOP_BINS, PREFLOP_FEATURES, PREFLOP_GROUPS, position_group,
)

CATS = ("nuts", "strong", "medium", "draw", "weak_draw", "air")
STREETS = ("flop", "turn", "river")
KAPPAS = (1.0, 2.0, 4.0, 8.0, 16.0, 32.0)
BASE_RIDGE = 0.5
FOLDS = 6
EPS = 1e-4
SHOWDOWN, WIN = 0, 1
KIND_NAMES = {SHOWDOWN: "showdown", WIN: "uncontested"}
_ARRAYS = ("q", "u", "lam", "street", "x", "live", "seq", "player", "kind", "e", "cu", "cur",
           "after", "y", "gm", "gu", "gcur", "gact")


class Layout:
    """What differs between the two layers: the categories a range is split into, the groups
    that get a base of their own, the features, and how a row is read."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.preflop = name == "preflop"
        self.cats = PREFLOP_BINS if self.preflop else CATS
        self.groups = PREFLOP_GROUPS if self.preflop else STREETS
        self.features = PREFLOP_FEATURES if self.preflop else FEATURES
        self.actions = PREFLOP_ACTIONS if self.preflop else ACTIONS
        self.section = "preflop_model" if self.preflop else "likelihood_model"

    def action(self, row: dict[str, Any]) -> str:
        if self.preflop:
            return str(row.get("preflop_label") or "")
        return row_action(row)

    def group(self, row: dict[str, Any]) -> int:
        return 0 if self.preflop else self.groups.index(row["street"])

    def feature_values(self, row: dict[str, Any]) -> list[float]:
        f = row["features"]
        if self.preflop and "pos_early" not in f:        # rows from before the position features
            f = dict(f, **{f"pos_{g}": 1.0 for g in [position_group(row.get("position") or "")] if g != "late"})
        return [float(f.get(name, 0.0)) for name in self.features]

    def usable(self, row: dict[str, Any]) -> bool:
        layers = row.get("layers") or {}
        if not row.get("features"):
            return False
        if self.preflop:
            return (row.get("street") == "preflop" and row.get("actual_bin") in self.cats
                    and all(c in (layers.get(n) or {}) for n in ("pre", "uniform", "floor") for c in self.cats))
        if row.get("street") not in STREETS:
            return False
        if any(cat not in (layers.get(name) or {}) for name in ("pre", "uniform") for cat in CATS):
            return False
        if row.get("trigger") == UNCONTESTED:
            return (row.get("actual_type") in TYPES and bool(row.get("type_given_bucket"))
                    and bool(row.get("uniform_type_given_bucket")))
        return row.get("actual_bucket") in CATS and all(cat in (layers.get("floor") or {}) for cat in CATS)

    def names(self, row: dict[str, Any], action: str) -> list[str]:
        """What a showdown row is reported under."""
        if not self.preflop:
            return [f"{row['street']} {action}"] + slice_names(action, row["features"])
        f = row["features"]
        who = ("不认识(<30手)" if float(f.get("known") or 0.0) < 0.5
               else "紧手" if float(f.get("tight") or 0.0) > 0 else "松手")
        return [f"翻前 {action}", f"翻前 {action} · {position_group(row.get('position') or '')}", f"翻前 {action} · {who}"]


POSTFLOP, PREFLOP = Layout("postflop"), Layout("preflop")


def row_action(row: dict[str, Any]) -> str:
    if row.get("trigger") == UNCONTESTED:
        return str(row.get("last_action") or "")
    return str(row.get("trigger") or "").split(":", 1)[-1]


class Data:
    """The rows of one action label, as arrays."""

    def __init__(self, action: str, rows: list[dict[str, Any]], layout: Layout = POSTFLOP) -> None:
        n = len(rows)
        k = len(layout.cats)
        cats = layout.cats
        self.action = action
        self.layout = layout
        self.chain = [row.get("_chain") for row in rows]  # preflop: (sequence id, position in it)
        self.q = np.zeros((n, k))                        # bucket shares before the action
        self.u = np.zeros((n, k))                        # ... of the uniform range mixed in afterwards
        self.lam = np.zeros(n)
        self.street = np.zeros(n, dtype=np.int64)
        self.x = np.zeros((n, len(layout.features)))
        self.seq = np.array([int(row.get("_seq", i)) for i, row in enumerate(rows)], dtype=np.int64)
        self.player = np.array([str(row.get("player_uid") or f"row{i}") for i, row in enumerate(rows)])
        self.kind = np.zeros(n, dtype=np.int64)
        self.e = np.zeros((n, k))                        # P(what was observed | bucket)
        self.cu = np.zeros(n)                            # P(what was observed) under the uniform range
        self.cur = np.zeros(n)                           # ... under the formula that produced the rows
        self.after = np.zeros((n, k))                    # showdown rows: that formula's bucket shares,
        self.y = np.full(n, -1, dtype=np.int64)          # and the bucket held
        self.gm = np.zeros((n, k, len(GROUPS)))          # uncontested wins: P(type group | bucket),
        self.gu = np.zeros((n, len(GROUPS)))             # the uniform range's group shares,
        self.gcur = np.zeros((n, len(GROUPS)))           # that formula's group shares,
        self.gact = np.full(n, -1, dtype=np.int64)       # and the group held
        self.names: list[list[str]] = []                 # showdown rows: (street, action) and the cuts
        for i, row in enumerate(rows):
            layers = row["layers"]
            self.q[i] = [float(layers["pre"][cat]) for cat in cats]
            self.u[i] = [float(layers["uniform"][cat]) for cat in cats]
            self.lam[i] = float(row.get("floor_lambda") or 0.0)
            self.street[i] = layout.group(row)           # the group whose base the row uses
            self.x[i] = layout.feature_values(row)
            if layout.preflop:
                y = cats.index(row["actual_bin"])
                self.after[i] = [float(layers["floor"][cat]) for cat in cats]
                self.after[i] /= self.after[i].sum()
                self.y[i] = y
                self.e[i, y] = 1.0
                self.cu[i] = self.u[i, y]
                self.cur[i] = self.after[i, y]
                self.names.append(layout.names(row, action))
                continue
            river = row["street"] == "river"             # the tracker treats river draws as air
            if river:
                for target in (self.q, self.u):
                    target[i, 5] += target[i, 3] + target[i, 4]
                    target[i, 3] = target[i, 4] = 0.0
            if row.get("trigger") == UNCONTESTED:
                self.kind[i] = WIN
                given, given_u = np.array(row["type_given_bucket"]), np.array(row["uniform_type_given_bucket"])
                t = TYPES.index(row["actual_type"])
                dist = row.get("type_dist") or {}
                self.e[i] = given[:, t]
                self.cu[i] = float(self.u[i] @ given_u[:, t])
                self.cur[i] = float(dist.get(row["actual_type"], 0.0))
                for g, (_, members) in enumerate(GROUPS):
                    self.gm[i, :, g] = given[:, list(members)].sum(axis=1)
                    self.gu[i, g] = float(self.u[i] @ given_u[:, list(members)].sum(axis=1))
                    self.gcur[i, g] = sum(float(dist.get(TYPES[m], 0.0)) for m in members)
                    if t in members:
                        self.gact[i] = g
                self.names.append([])
                continue
            self.after[i] = [float(layers["floor"][cat]) for cat in CATS]
            y = CATS.index(row["actual_bucket"])
            if river:
                self.after[i, 5] += self.after[i, 3] + self.after[i, 4]
                self.after[i, 3] = self.after[i, 4] = 0.0
                y = 5 if y in (3, 4) else y
            self.after[i] /= self.after[i].sum()
            self.y[i] = y
            self.e[i, y] = 1.0
            self.cu[i] = self.u[i, y]
            self.cur[i] = self.after[i, y]
            self.names.append(layout.names(row, action))
        self.live = self.q > 0
        self.q = np.where(self.live, np.maximum(self.q, EPS), 0.0)
        self.q /= self.q.sum(axis=1, keepdims=True)

    def __len__(self) -> int:
        return len(self.lam)

    def take(self, mask: np.ndarray) -> "Data":
        out = copy.copy(self)
        for name in _ARRAYS:
            setattr(out, name, getattr(self, name)[mask])
        out.names = [names for names, keep in zip(self.names, mask) if keep]
        return out

    def posterior(self, base: np.ndarray, weights: np.ndarray) -> np.ndarray:
        """Bucket shares after the likelihood, before floor mixing."""
        score = base[self.street] + self.x @ weights
        logits = np.where(self.live, np.log(np.where(self.live, self.q, 1.0)) + score, -np.inf)
        logits -= logits.max(axis=1, keepdims=True)
        p = np.exp(logits)
        return p / p.sum(axis=1, keepdims=True)

    def mixed(self, p: np.ndarray) -> np.ndarray:
        """Bucket shares after floor mixing: what the tracker carries on."""
        return (1.0 - self.lam[:, None]) * p + self.lam[:, None] * self.u

    def prob(self, p: np.ndarray) -> np.ndarray:
        """Probability of what was observed."""
        return (1.0 - self.lam) * (p * self.e).sum(axis=1) + self.lam * self.cu

    def groups(self, p: np.ndarray) -> np.ndarray:
        """Hand-type group shares after floor mixing (uncontested wins)."""
        return (1.0 - self.lam[:, None]) * np.einsum("nb,nbg->ng", p, self.gm) + self.lam[:, None] * self.gu


def _unpack(theta: np.ndarray, layout: Layout = POSTFLOP) -> tuple[np.ndarray, np.ndarray]:
    g, k = len(layout.groups), len(layout.cats)
    return theta[:g * k].reshape(g, k), theta[g * k:].reshape(-1, k)


def fit_action(data: Data, kappa: float, weight: np.ndarray | None = None) -> tuple[np.ndarray, np.ndarray]:
    """``weight``: per row, how much it counts (default: every row once)."""
    w = np.ones(len(data)) if weight is None else np.asarray(weight, dtype=np.float64)

    layout = data.layout
    g, k = len(layout.groups), len(layout.cats)

    def objective(theta):
        base, weights = _unpack(theta, layout)
        p = data.posterior(base, weights)
        seen = (p * data.e).sum(axis=1)
        m = np.maximum((1.0 - data.lam) * seen + data.lam * data.cu, 1e-9)
        loss = -(w * np.log(m)).sum() + 0.5 * kappa * float((weights ** 2).sum()) + 0.5 * BASE_RIDGE * float((base ** 2).sum())
        # d(-log m)/d score[b] = -(1 - lam) * p[b] * (e[b] - sum_b' p[b'] e[b']) / m
        grad_score = -((w * (1.0 - data.lam) / m)[:, None]) * p * (data.e - seen[:, None])
        grad_base = np.zeros((g, k))
        np.add.at(grad_base, data.street, grad_score)
        grad = np.concatenate([(grad_base + BASE_RIDGE * base).ravel(),
                               (data.x.T @ grad_score + kappa * weights).ravel()])
        return loss, grad

    size = (g + data.x.shape[1]) * k
    best = minimize(objective, np.zeros(size), jac=True, method="L-BFGS-B",
                    bounds=[(-5.0, 5.0)] * size, options={"maxiter": 500})
    return _unpack(best.x, layout)


def row_nll(prob: np.ndarray) -> np.ndarray:
    return -np.log(np.maximum(prob, 1e-9))


def nll(data: Data, base: np.ndarray, weights: np.ndarray) -> float:
    return float(row_nll(data.prob(data.posterior(base, weights))).sum())


def current_nll(data: Data) -> float:
    return float(row_nll(data.cur).sum())


def fit_weight(data: Data, truth: str) -> np.ndarray:
    return np.ones(len(data)) if truth == "both" else (data.kind == SHOWDOWN).astype(np.float64)


def out_of_fold(data: Data, kappa: float, folds: int = FOLDS, total: int | None = None,
                truth: str = "both") -> np.ndarray:
    """Bucket shares after the likelihood, each row from a model that never saw its stretch of the rows."""
    total = int(total or (data.seq.max() + 1 if len(data) else 1))
    fold = np.minimum(data.seq * folds // max(1, total), folds - 1)
    out = np.zeros((len(data), len(data.layout.cats)))
    for k in range(folds):
        mask = fold == k
        if mask.any():
            rest = data.take(~mask)
            out[mask] = data.take(mask).posterior(*fit_action(rest, kappa, fit_weight(rest, truth)))
    return out


def clustered(values: np.ndarray, clusters: np.ndarray) -> tuple[float, float]:
    """(mean, standard error of the mean with the rows of one cluster allowed to move together)."""
    n = len(values)
    mean = float(values.mean())
    _, index = np.unique(clusters, return_inverse=True)
    sums = np.bincount(index, weights=values - mean)
    g = len(sums)
    if g < 2:
        return mean, 0.0
    return mean, float(math.sqrt(g / (g - 1) * float((sums ** 2).sum())) / n)


def load(rows: Iterable[dict[str, Any]], layout: Layout = POSTFLOP) -> dict[str, Data]:
    grouped: dict[str, list] = defaultdict(list)
    seq = chain = 0
    last = None
    for row in rows:
        action = layout.action(row)
        if action not in layout.actions or not layout.usable(row):
            continue
        row["_seq"] = seq
        seq += 1
        if layout.preflop:
            # A player's preflop actions of one hand arrive one after the other.
            key = (row.get("player_uid"), row.get("hand"), row.get("source"))
            if key != last:
                chain, position, last = chain + 1, 0, key
            row["_chain"] = (chain, position)
            position += 1
        grouped[action].append(row)
    return {action: Data(action, rows, layout) for action, rows in grouped.items()}


def carry_ranges(data: dict[str, Data], models: dict[str, tuple[np.ndarray, np.ndarray]]) -> float:
    """Preflop: put, before each later action of a player in a hand, the range the models leave
    after his earlier ones (the rows were extracted with whatever model was in force then).
    Returns the largest change made to a share."""
    order = sorted((d.chain[i], action, i) for action, d in data.items() for i in range(len(d)))
    moved, carried, current = 0.0, None, None
    for (chain, position), action, i in order:
        d = data[action]
        if position == 0 or chain != current:
            carried = None
        current = chain
        if carried is not None:
            moved = max(moved, float(np.abs(d.q[i] - carried).max()))
            d.q[i] = carried
            d.live[i] = carried > 0
        if action in models:
            base, weights = models[action]
            p = d.q[i] * np.exp(base[d.street[i]] + d.x[i] @ weights)
            carried = (1.0 - d.lam[i]) * p / p.sum() + d.lam[i] * d.u[i]
        else:
            carried = d.q[i].copy()
    return moved


def slices(data: dict[str, Data], post: dict[str, np.ndarray], min_rows: int = 100) -> list[dict[str, Any]]:
    """Predicted minus held, the formula that produced the rows against the model.

    Showdown rows: the strong + nuts share, per (street, action) and per acceptance cut.
    Uncontested wins: the share of each hand-type group, per (street, action).
    """
    groups: dict[str, list[tuple[float, float, str]]] = defaultdict(list)
    for action, d in data.items():
        mixed, typed = d.mixed(post[action]), d.groups(post[action])
        top = slice(0, 2) if not d.layout.preflop else slice(len(d.layout.cats) - 3, None)   # strong hands
        for i in range(len(d)):
            if d.kind[i] == SHOWDOWN:
                held = 1.0 if (d.y[i] <= 1 if not d.layout.preflop else d.y[i] >= len(d.layout.cats) - 3) else 0.0
                item = (d.after[i, top].sum() - held, mixed[i, top].sum() - held, d.player[i])
                for name in d.names[i]:
                    groups[name].append(item)
            else:
                for g, (label, _) in enumerate(GROUPS):
                    held = 1.0 if d.gact[i] == g else 0.0
                    groups[f"没人跟注 {d.layout.groups[d.street[i]]} {action} · {label}"].append(
                        (d.gcur[i, g] - held, typed[i, g] - held, d.player[i]))
    out = []
    for name in sorted(groups):
        if len(groups[name]) < min_rows:
            continue
        cur = np.array([g[0] for g in groups[name]])
        new = np.array([g[1] for g in groups[name]])
        who = np.array([g[2] for g in groups[name]])
        out.append({"slice": name, "rows": len(cur), "players": len(set(who)),
                    "current": [round(100 * v, 2) for v in clustered(cur, who)],
                    "model": [round(100 * v, 2) for v in clustered(new, who)]})
    return out


def compare(data: dict[str, Data], post: dict[str, np.ndarray]) -> dict[str, Any]:
    """NLL per row by kind of truth: the formula that produced the rows, the model, the paired difference."""
    actions = sorted(data)
    cur = np.concatenate([row_nll(data[a].cur) for a in actions])
    new = np.concatenate([row_nll(data[a].prob(post[a])) for a in actions])
    who = np.concatenate([data[a].player for a in actions])
    kind = np.concatenate([data[a].kind for a in actions])
    out = {}
    for name, mask in [(KIND_NAMES[k], kind == k) for k in (SHOWDOWN, WIN)] + [("all", np.ones(len(kind), dtype=bool))]:
        if mask.any():
            diff, se = clustered(new[mask] - cur[mask], who[mask])
            out[name] = {"rows": int(mask.sum()), "current": round(float(cur[mask].mean()), 5),
                         "model": round(float(new[mask].mean()), 5),
                         "difference": round(diff, 5), "difference_se": round(se, 5)}
    return out


def _print(title: str, scores: dict[str, Any], items: list[dict[str, Any]]) -> None:
    print(f"\n== {title} ==")
    for name, c in scores.items():
        print(f"NLL per row, {name:11s}: formula of the rows {c['current']:.5f} -> model {c['model']:.5f}  "
              f"(difference {c['difference']:+.5f} ± {c['difference_se']:.5f}, {c['rows']} rows)")
    flag = lambda v: " <<" if abs(v[0]) > 3 and abs(v[0]) > 2 * v[1] else "   "
    print(f"{'predicted - held, points':38s} {'rows':>6s} {'players':>7s}  {'current':>14s}  {'model':>14s}")
    for item in items:
        print(f"{item['slice']:38s} {item['rows']:6d} {item['players']:7d}  "
              f"{item['current'][0]:+6.1f} ({item['current'][1]:.1f}){flag(item['current'])}"
              f"  {item['model'][0]:+6.1f} ({item['model'][1]:.1f}){flag(item['model'])}")


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--layer", choices=("postflop", "preflop"), default="postflop")
    ap.add_argument("--rows", type=Path, action="append", required=True, help="rows to fit on, in playing order")
    ap.add_argument("--holdout-rows", type=Path, action="append", help="rows that are only reported")
    ap.add_argument("--truth", choices=("both", "showdown"), default="both",
                    help="postflop: fit on showdowns and uncontested wins (default), or on showdowns "
                         "alone; both kinds are reported either way")
    ap.add_argument("--base", type=Path, help="formula-fit file whose other layer is kept")
    ap.add_argument("--ridge", type=float, help="penalty to use instead of choosing it out of fold")
    ap.add_argument("--folds", type=int, default=FOLDS)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args(argv)
    layout = PREFLOP if args.layer == "preflop" else POSTFLOP

    train = load(iter_rows(args.rows), layout)
    hold = load(iter_rows(args.holdout_rows), layout) if args.holdout_rows else {}
    actions = [a for a in layout.actions if a in train]
    hold = {a: hold[a] for a in actions if a in hold}
    total = sum(len(train[a]) for a in actions)
    weights = {a: fit_weight(train[a], args.truth) for a in actions}

    def fit_all(kappa: float) -> dict[str, tuple[np.ndarray, np.ndarray]]:
        models = {a: fit_action(train[a], kappa, weights[a]) for a in actions}
        if layout.preflop:                               # a player's later preflop actions start
            for _ in range(4):                           # from what the models leave after his earlier ones
                if carry_ranges(train, models) < 1e-4:
                    break
                models = {a: fit_action(train[a], kappa, weights[a]) for a in actions}
        return models

    if layout.preflop:
        fit_all(KAPPAS[len(KAPPAS) // 2])                # ranges before later actions, for the folds below
    scores: dict[float, tuple[float, dict[str, np.ndarray]]] = {}
    for kappa in (KAPPAS if args.ridge is None else (float(args.ridge),)):
        oof = {a: out_of_fold(train[a], kappa, args.folds, total, args.truth) for a in actions}
        loss = sum(float((weights[a] * row_nll(train[a].prob(oof[a]))).sum()) for a in actions)
        scores[kappa] = (loss / max(1.0, sum(float(weights[a].sum()) for a in actions)), oof)
    kappa = min(scores, key=lambda k: scores[k][0])
    models = fit_all(kappa)
    oof = {a: out_of_fold(train[a], kappa, args.folds, total, args.truth) for a in actions}
    if layout.preflop and hold:
        carry_ranges(hold, models)

    out: dict[str, Any] = json.loads(args.base.read_text(encoding="utf-8")) if args.base else {}
    out["type"] = "range_formula_fit"
    out["fitted_at"] = time.strftime("%Y-%m-%d %H:%M")
    section: dict[str, Any] = {
        "features": list(layout.features),
        "actions": {
            a: {"base": {group: {cat: round(float(v), 4) for cat, v in zip(layout.cats, models[a][0][g])}
                         for g, group in enumerate(layout.groups)},
                "weights": {name: {cat: round(float(v), 4) for cat, v in zip(layout.cats, models[a][1][f])}
                            for f, name in enumerate(layout.features)}}
            for a in actions},
    }
    if layout.preflop:
        section["bins"] = list(layout.cats)
        section["groups"] = list(layout.groups)
    out[layout.section] = section
    report: dict[str, Any] = {
        "truth": args.truth if not layout.preflop else "showdown",
        "ridge": kappa,
        "ridge_scores": {str(k): round(v[0], 5) for k, v in scores.items()},
        "rows": {a: {KIND_NAMES[k]: int((train[a].kind == k).sum()) for k in (SHOWDOWN, WIN)} for a in actions},
        "out_of_fold": compare(train, oof),
        "out_of_fold_slices": slices(train, oof),
    }
    if hold:
        hold_post = {a: hold[a].posterior(*models[a]) for a in hold}
        report["holdout"] = compare(hold, hold_post)
        report["holdout_slices"] = slices(hold, hold_post)
    out["report"] = {**(out.get("report") or {}), layout.section: report}
    args.out.write_text(json.dumps(out, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")

    print(f"layer: {layout.name}; truth: {report['truth']}; ridge {kappa} "
          f"(out-of-fold NLL per fitted row by ridge: {report['ridge_scores']})")
    _print("fitted rows, out of fold", report["out_of_fold"], report["out_of_fold_slices"])
    if hold:
        _print("hold-out rows", report["holdout"], report["holdout_slices"])


if __name__ == "__main__":
    main()
