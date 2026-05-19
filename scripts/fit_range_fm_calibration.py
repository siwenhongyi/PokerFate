"""Fit a small FM residual calibration model for Range V2 rows.

This is intentionally independent from fit_range_calibration_v2.py.  It uses
only numpy and treats the current range model as the base predictor:

* bucket: logits = log(bucket_dist) + FM(context/features)
* equity: logit(eq) = logit(raw_eq) + FM(context/features)

The goal is to learn systematic residual errors from showdown rows without
replacing the poker model from scratch.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any, Iterable

import numpy as np


CAT_ORDER = ("nuts", "strong", "medium", "draw", "weak_draw", "air")
CAT_IDX = {cat: i for i, cat in enumerate(CAT_ORDER)}
EPS = 1e-6
CAT_FIELDS = (
    "street",
    "trigger",
    "action",
    "nopp",
    "texture",
    "hero_bucket",
    "top_bucket",
)
RELATIVE_CAT_FIELDS = (
    "hero_made_subtype",
    "hero_hand_rank",
    "board_texture",
)


def _load_rows(paths: Iterable[Path], limit: int = 0) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in paths:
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                rows.append(json.loads(line))
                if limit > 0 and len(rows) >= limit:
                    return rows
    return rows


def _write_json(path: Path | None, obj: Any) -> None:
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def _bucket_vec(row: dict[str, Any]) -> np.ndarray:
    dist = row.get("bucket_dist") or {}
    arr = np.array([float(dist.get(cat, 0.0)) for cat in CAT_ORDER], dtype=np.float64)
    total = float(arr.sum())
    if total > 0:
        arr /= total
    else:
        arr[:] = 1.0 / len(CAT_ORDER)
    return np.clip(arr, EPS, 1.0)


def _label_idx(row: dict[str, Any]) -> int:
    return CAT_IDX.get(str(row.get("actual_bucket") or ""), CAT_IDX["air"])


def _softmax(z: np.ndarray) -> np.ndarray:
    z = z - z.max(axis=1, keepdims=True)
    e = np.exp(z)
    return e / e.sum(axis=1, keepdims=True)


def _sigmoid(z: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-np.clip(z, -40.0, 40.0)))


def _logit(x: np.ndarray) -> np.ndarray:
    x = np.clip(x, EPS, 1.0 - EPS)
    return np.log(x / (1.0 - x))


def _action_ctx(trigger: str) -> str:
    if trigger in {"action:raise", "action:raise_over"}:
        return "raise"
    if trigger == "action:bet":
        return "bet"
    if trigger == "action:call":
        return "call"
    if trigger == "action:check":
        return "check"
    if trigger == "action:fold_other":
        return "fold_other"
    if trigger.startswith("board:"):
        return "board"
    return "passive"


def _nopp_bin(row: dict[str, Any]) -> str:
    n = int(row.get("active_player_count") or len(row.get("active_player_ids") or []) or 1)
    if n <= 1:
        return "1"
    if n == 2:
        return "2"
    return "3+"


def _board_texture(row: dict[str, Any]) -> str:
    board = row.get("board") or []
    if len(board) < 3:
        return "pre"
    ranks = [str(c)[0] for c in board if c]
    suits = [str(c)[1] for c in board if len(str(c)) >= 2]
    paired = len(set(ranks)) < len(ranks)
    if len(suits) >= 3 and len(set(suits[:3])) == 1:
        flush = "mono"
    elif len(suits) >= 3 and max(suits[:3].count(s) for s in set(suits[:3])) >= 2:
        flush = "fd"
    else:
        flush = "rainbow"
    return ("paired" if paired else "unpaired") + ":" + flush


def _top_bucket(row: dict[str, Any]) -> str:
    p = _bucket_vec(row)
    return CAT_ORDER[int(np.argmax(p))]


def _categorical_values(
    row: dict[str, Any],
    *,
    include_player: bool = False,
    include_relative: bool = False,
) -> dict[str, str]:
    values = {
        "street": str(row.get("street") or "?"),
        "trigger": str(row.get("trigger") or "?"),
        "action": _action_ctx(str(row.get("trigger") or "")),
        "nopp": _nopp_bin(row),
        "texture": _board_texture(row),
        "hero_bucket": str(row.get("hero_bucket") or "?"),
        "top_bucket": _top_bucket(row),
    }
    if include_relative:
        board_texture = str(row.get("board_texture") or "") or _board_texture(row)
        values.update({
            "hero_made_subtype": str(row.get("hero_made_subtype") or "?"),
            "hero_hand_rank": str(row.get("hero_hand_rank") or "?"),
            "board_texture": board_texture,
        })
    if include_player:
        values["player"] = str(row.get("player") or "?")
    return values


def _dense_bucket_features(row: dict[str, Any]) -> dict[str, float]:
    p = _bucket_vec(row)
    ordered = np.sort(p)[::-1]
    board_len = min(len(row.get("board") or []), 5) / 5.0
    nopp = int(row.get("active_player_count") or len(row.get("active_player_ids") or []) or 1)
    entropy = float(-np.sum(p * np.log(np.clip(p, EPS, 1.0))) / math.log(len(CAT_ORDER)))
    out: dict[str, float] = {
        "range_pct": float(row.get("range_pct") or 0.0),
        "board_len": board_len,
        "nopp_scaled": min(max(nopp, 1), 6) / 6.0,
        "entropy": entropy,
        "top_prob": float(ordered[0]),
        "top_margin": float(ordered[0] - ordered[1]) if len(ordered) > 1 else 0.0,
    }
    for cat, val in zip(CAT_ORDER, p):
        out[f"p_{cat}"] = float(val)
        out[f"logp_{cat}"] = float(np.log(max(float(val), EPS)) / 8.0)
    return out


def _dense_equity_features(row: dict[str, Any], pred: float) -> dict[str, float]:
    out = _dense_bucket_features(row)
    out["raw_eq"] = float(pred)
    out["raw_eq_logit"] = float(_logit(np.array([pred]))[0] / 8.0)
    return out


def _relation_dist(row: dict[str, Any]) -> dict[str, float]:
    rel = row.get("villain_vs_hero_dist") or {}
    try:
        win = max(0.0, float(rel.get("win", 0.0) or 0.0))
        tie = max(0.0, float(rel.get("tie", 0.0) or 0.0))
        loss = max(0.0, float(rel.get("loss", 0.0) or 0.0))
    except Exception:
        return {"win": 0.0, "tie": 0.0, "loss": 0.0}
    total = win + tie + loss
    if total <= 1e-12:
        return {"win": 0.0, "tie": 0.0, "loss": 0.0}
    return {"win": win / total, "tie": tie / total, "loss": loss / total}


def _relation_eq_from_dist(row: dict[str, Any]) -> float | None:
    rel = _relation_dist(row)
    if rel["win"] + rel["tie"] + rel["loss"] <= 1e-12:
        return None
    return rel["win"] + 0.5 * rel["tie"]


def _actual_relation_eq(row: dict[str, Any]) -> float | None:
    relation = str(row.get("actual_relation") or "")
    if relation == "win":
        return 1.0
    if relation == "tie":
        return 0.5
    if relation == "loss":
        return 0.0
    return None


def _dense_relative_features(row: dict[str, Any], pred: float) -> dict[str, float]:
    out = _dense_equity_features(row, pred)
    rel = _relation_dist(row)
    out["rel_win"] = rel["win"]
    out["rel_tie"] = rel["tie"]
    out["rel_loss"] = rel["loss"]
    out["rel_loss_minus_win"] = rel["loss"] - rel["win"]
    out["rel_non_tie"] = rel["win"] + rel["loss"]
    return out


def _filter_bucket_rows(rows: list[dict[str, Any]], streets: set[str]) -> list[dict[str, Any]]:
    return [
        r for r in rows
        if r.get("actual_bucket") in CAT_IDX and str(r.get("street")) in streets
    ]


def _equity_pairs(rows: list[dict[str, Any]], target: str) -> list[tuple[dict[str, Any], float, float]]:
    pred_key = "predicted_hero_eq_multi" if target == "multi" else "predicted_hero_eq"
    actual_key = "actual_hero_eq_street_multi" if target == "multi" else "actual_hero_eq_street"
    out: list[tuple[dict[str, Any], float, float]] = []
    for row in rows:
        pred = row.get(pred_key)
        actual = row.get(actual_key)
        if pred is None or actual is None:
            continue
        pred_f = float(pred)
        actual_f = float(actual)
        if 0.0 <= pred_f <= 1.0 and 0.0 <= actual_f <= 1.0:
            out.append((row, pred_f, actual_f))
    return out


def _relative_pairs(rows: list[dict[str, Any]]) -> list[tuple[dict[str, Any], float, float]]:
    out: list[tuple[dict[str, Any], float, float]] = []
    for row in rows:
        if row.get("street") != "river":
            continue
        pred = row.get("predicted_relation_eq")
        if pred is None:
            pred = _relation_eq_from_dist(row)
        actual = _actual_relation_eq(row)
        if pred is None or actual is None:
            continue
        pred_f = float(pred)
        actual_f = float(actual)
        if 0.0 <= pred_f <= 1.0 and 0.0 <= actual_f <= 1.0:
            out.append((row, pred_f, actual_f))
    return out


def _build_feature_map(
    rows: list[dict[str, Any]],
    *,
    dense_names: list[str],
    include_player: bool,
    include_relative: bool = False,
) -> dict[str, int]:
    names: list[str] = list(dense_names)
    fields = list(CAT_FIELDS)
    if include_relative:
        fields += list(RELATIVE_CAT_FIELDS)
    if include_player:
        fields += ["player"]
    for field in fields:
        names.append(f"{field}=__OTHER__")
    seen: set[str] = set(names)
    for row in rows:
        for field, value in _categorical_values(
            row,
            include_player=include_player,
            include_relative=include_relative,
        ).items():
            name = f"{field}={value}"
            if name not in seen:
                seen.add(name)
                names.append(name)
    return {name: idx for idx, name in enumerate(names)}


def _matrix_from_rows(
    rows: list[dict[str, Any]],
    *,
    feature_map: dict[str, int],
    dense_getter,
    include_player: bool,
    include_relative: bool = False,
) -> np.ndarray:
    x = np.zeros((len(rows), len(feature_map)), dtype=np.float32)
    for i, row in enumerate(rows):
        for name, val in dense_getter(row).items():
            idx = feature_map.get(name)
            if idx is not None:
                x[i, idx] = float(val)
        for field, value in _categorical_values(
            row,
            include_player=include_player,
            include_relative=include_relative,
        ).items():
            name = f"{field}={value}"
            idx = feature_map.get(name, feature_map.get(f"{field}=__OTHER__"))
            if idx is not None:
                x[i, idx] = 1.0
    return x


def _bucket_base_logits(rows: list[dict[str, Any]]) -> np.ndarray:
    return np.log(np.vstack([_bucket_vec(r) for r in rows]))


def _bucket_metrics(rows: list[dict[str, Any]], probs: np.ndarray) -> dict[str, Any]:
    if not rows:
        return {"n": 0}
    y = np.array([_label_idx(r) for r in rows], dtype=np.int64)
    py = probs[np.arange(len(rows)), y]
    strong_nuts_mask = np.array([
        r.get("actual_bucket") in ("strong", "nuts") for r in rows
    ], dtype=bool)
    brier = float(np.mean(np.sum((probs - np.eye(len(CAT_ORDER))[y]) ** 2, axis=1)))
    strong_nuts_combo = probs[:, CAT_IDX["strong"]] + probs[:, CAT_IDX["nuts"]]
    return {
        "n": len(rows),
        "nll": round(float(-np.mean(np.log(np.clip(py, EPS, 1.0)))), 5),
        "brier": round(brier, 5),
        "actual_bucket_avg_pct": round(float(np.mean(py) * 100.0), 2),
        "under_10_pct": round(float(np.mean(py < 0.10) * 100.0), 2),
        "top1_pct": round(float(np.mean(np.argmax(probs, axis=1) == y) * 100.0), 2),
        "strong_nuts_under_20_pct": round(
            float(np.mean(py[strong_nuts_mask] < 0.20) * 100.0)
            if bool(strong_nuts_mask.any()) else 0.0,
            2,
        ),
        "strong_nuts_combo_under_20_pct": round(
            float(np.mean(strong_nuts_combo[strong_nuts_mask] < 0.20) * 100.0)
            if bool(strong_nuts_mask.any()) else 0.0,
            2,
        ),
        "strong_nuts_combo_avg_pct": round(
            float(np.mean(strong_nuts_combo[strong_nuts_mask]) * 100.0)
            if bool(strong_nuts_mask.any()) else 0.0,
            2,
        ),
    }


class Adam:
    def __init__(self, lr: float) -> None:
        self.lr = lr
        self.t = 0
        self.m: dict[str, np.ndarray] = {}
        self.v: dict[str, np.ndarray] = {}

    def step(self, params: dict[str, np.ndarray], grads: dict[str, np.ndarray]) -> None:
        self.t += 1
        b1 = 0.9
        b2 = 0.999
        for key, grad in grads.items():
            if key not in self.m:
                self.m[key] = np.zeros_like(grad)
                self.v[key] = np.zeros_like(grad)
            self.m[key] = b1 * self.m[key] + (1.0 - b1) * grad
            self.v[key] = b2 * self.v[key] + (1.0 - b2) * (grad * grad)
            mhat = self.m[key] / (1.0 - b1 ** self.t)
            vhat = self.v[key] / (1.0 - b2 ** self.t)
            params[key] -= self.lr * mhat / (np.sqrt(vhat) + 1e-8)


def _bucket_logits(
    x: np.ndarray,
    base_logits: np.ndarray,
    params: dict[str, np.ndarray],
) -> np.ndarray:
    w = params["w"]
    b = params["b"]
    v = params["v"]
    logits = base_logits + b[None, :] + x @ w
    x2 = x * x
    for c in range(len(CAT_ORDER)):
        vc = v[:, :, c]
        xv = x @ vc
        x2v2 = x2 @ (vc * vc)
        logits[:, c] += 0.5 * np.sum(xv * xv - x2v2, axis=1)
    return logits


def _train_bucket_fm(
    train_rows: list[dict[str, Any]],
    val_rows: list[dict[str, Any]],
    *,
    rank: int,
    epochs: int,
    batch_size: int,
    lr: float,
    l2: float,
    seed: int,
    include_player: bool,
    bucket_strong_nuts_weight: float,
    strong_nuts_lowprob_penalty: float,
    strong_nuts_lowprob_threshold: float,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    dense_names = list(_dense_bucket_features(train_rows[0]).keys())
    feature_map = _build_feature_map(
        train_rows,
        dense_names=dense_names,
        include_player=include_player,
    )
    x_train = _matrix_from_rows(
        train_rows,
        feature_map=feature_map,
        dense_getter=_dense_bucket_features,
        include_player=include_player,
    )
    x_val = _matrix_from_rows(
        val_rows,
        feature_map=feature_map,
        dense_getter=_dense_bucket_features,
        include_player=include_player,
    )
    y_train = np.array([_label_idx(r) for r in train_rows], dtype=np.int64)
    sample_weight = np.ones(len(y_train), dtype=np.float64)
    if bucket_strong_nuts_weight > 1.0:
        sn_train = (y_train == CAT_IDX["strong"]) | (y_train == CAT_IDX["nuts"])
        sample_weight[sn_train] = float(bucket_strong_nuts_weight)
    base_train = _bucket_base_logits(train_rows)
    base_val = _bucket_base_logits(val_rows)
    rng = np.random.default_rng(seed)
    d = x_train.shape[1]
    c = len(CAT_ORDER)
    params = {
        "w": np.zeros((d, c), dtype=np.float64),
        "b": np.zeros(c, dtype=np.float64),
        "v": rng.normal(0.0, 0.01, size=(d, rank, c)).astype(np.float64),
    }
    opt = Adam(lr)
    n = len(train_rows)
    eye = np.eye(c, dtype=np.float64)
    history = []
    for epoch in range(1, epochs + 1):
        order = rng.permutation(n)
        for start in range(0, n, batch_size):
            idx = order[start:start + batch_size]
            xb = x_train[idx].astype(np.float64, copy=False)
            base_b = base_train[idx]
            yb = y_train[idx]
            wb = sample_weight[idx]
            q = _softmax(_bucket_logits(xb, base_b, params))
            diff = (q - eye[yb]) * (wb[:, None] / max(float(wb.sum()), 1.0))
            if strong_nuts_lowprob_penalty > 0.0:
                py = q[np.arange(len(idx)), yb]
                sn_mask = (
                    (yb == CAT_IDX["strong"]) | (yb == CAT_IDX["nuts"])
                ) & (py < strong_nuts_lowprob_threshold)
                if bool(sn_mask.any()):
                    y_onehot = eye[yb[sn_mask]]
                    dldq = (
                        -2.0 * strong_nuts_lowprob_penalty
                        * (strong_nuts_lowprob_threshold - py[sn_mask])
                        / max(len(idx), 1)
                    )
                    diff[sn_mask] += (
                        dldq[:, None]
                        * py[sn_mask, None]
                        * (y_onehot - q[sn_mask])
                    )
            x2 = xb * xb
            grads = {
                "w": xb.T @ diff + l2 * params["w"],
                "b": diff.sum(axis=0) + l2 * params["b"],
                "v": np.zeros_like(params["v"]),
            }
            for cls in range(c):
                vc = params["v"][:, :, cls]
                xv = xb @ vc
                weighted = diff[:, cls][:, None] * xv
                g = xb.T @ weighted - vc * ((x2.T @ diff[:, cls])[:, None])
                grads["v"][:, :, cls] = g + l2 * vc
            opt.step(params, grads)
        if epoch == 1 or epoch == epochs or epoch % max(1, epochs // 5) == 0:
            train_probs = _softmax(_bucket_logits(x_train, base_train, params))
            val_probs = _softmax(_bucket_logits(x_val, base_val, params))
            history.append({
                "epoch": epoch,
                "train": _bucket_metrics(train_rows, train_probs),
                "val": _bucket_metrics(val_rows, val_probs),
            })
    raw_train = _bucket_metrics(train_rows, _softmax(base_train))
    raw_val = _bucket_metrics(val_rows, _softmax(base_val))
    fm_train = _bucket_metrics(train_rows, _softmax(_bucket_logits(x_train, base_train, params)))
    fm_val = _bucket_metrics(val_rows, _softmax(_bucket_logits(x_val, base_val, params)))
    model = {
        "type": "bucket_fm_residual",
        "cat_order": list(CAT_ORDER),
        "rank": rank,
        "include_player": include_player,
        "bucket_strong_nuts_weight": bucket_strong_nuts_weight,
        "strong_nuts_lowprob_penalty": strong_nuts_lowprob_penalty,
        "strong_nuts_lowprob_threshold": strong_nuts_lowprob_threshold,
        "feature_map": feature_map,
        "w": np.round(params["w"], 6).tolist(),
        "b": np.round(params["b"], 6).tolist(),
        "v": np.round(params["v"], 6).tolist(),
    }
    report = {
        "features": len(feature_map),
        "history": history,
        "train_raw": raw_train,
        "train_fm": fm_train,
        "val_raw": raw_val,
        "val_fm": fm_val,
        "val_nll_gain": round(float(raw_val["nll"] - fm_val["nll"]), 5),
        "val_brier_gain": round(float(raw_val["brier"] - fm_val["brier"]), 5),
    }
    return model, report, {"feature_map": feature_map}


def _equity_metrics(items: list[tuple[dict[str, Any], float, float]], pred: np.ndarray) -> dict[str, Any]:
    if not items:
        return {"n": 0}
    y = np.array([actual for _row, _raw, actual in items], dtype=np.float64)
    err = pred - y
    return {
        "n": len(items),
        "mae_pp": round(float(np.mean(np.abs(err)) * 100.0), 2),
        "rmse_pp": round(float(math.sqrt(np.mean(err * err))) * 100.0, 2),
        "bias_pp": round(float(np.mean(err) * 100.0), 2),
        "ece_pp": round(_ece(pred, y) * 100.0, 2),
    }


def _ece(pred: np.ndarray, actual: np.ndarray, bins: int = 10) -> float:
    score = 0.0
    for i in range(bins):
        lo = i / bins
        hi = (i + 1) / bins
        mask = (pred >= lo) & (pred <= hi if i == bins - 1 else pred < hi)
        if bool(mask.any()):
            score += float(mask.mean()) * abs(float(pred[mask].mean() - actual[mask].mean()))
    return score


def _equity_score(x: np.ndarray, base_logit: np.ndarray, params: dict[str, np.ndarray]) -> np.ndarray:
    w = params["w"]
    b = params["b"]
    v = params["v"]
    xv = x @ v
    x2v2 = (x * x) @ (v * v)
    inter = 0.5 * np.sum(xv * xv - x2v2, axis=1)
    return base_logit + b[0] + x @ w + inter


def _train_equity_fm(
    train_items: list[tuple[dict[str, Any], float, float]],
    val_items: list[tuple[dict[str, Any], float, float]],
    *,
    rank: int,
    epochs: int,
    batch_size: int,
    lr: float,
    l2: float,
    seed: int,
    include_player: bool,
    dense_feature_fn=_dense_equity_features,
    model_type: str = "equity_fm_residual",
    include_relative_context: bool = False,
) -> tuple[dict[str, Any], dict[str, Any]]:
    train_rows = [row for row, _pred, _actual in train_items]
    train_pred_by_id = {id(row): pred for row, pred, _actual in train_items}
    dense_names = list(dense_feature_fn(train_items[0][0], train_items[0][1]).keys())
    feature_map = _build_feature_map(
        train_rows,
        dense_names=dense_names,
        include_player=include_player,
        include_relative=include_relative_context,
    )
    x_train = _matrix_from_rows(
        train_rows,
        feature_map=feature_map,
        dense_getter=lambda row: dense_feature_fn(row, train_pred_by_id[id(row)]),
        include_player=include_player,
        include_relative=include_relative_context,
    )
    val_rows = [row for row, _pred, _actual in val_items]
    val_pred_by_id = {id(row): pred for row, pred, _actual in val_items}
    x_val = _matrix_from_rows(
        val_rows,
        feature_map=feature_map,
        dense_getter=lambda row: dense_feature_fn(row, val_pred_by_id[id(row)]),
        include_player=include_player,
        include_relative=include_relative_context,
    )
    raw_train = np.array([pred for _row, pred, _actual in train_items], dtype=np.float64)
    y_train = np.array([actual for _row, _pred, actual in train_items], dtype=np.float64)
    raw_val = np.array([pred for _row, pred, _actual in val_items], dtype=np.float64)
    base_train = _logit(raw_train)
    base_val = _logit(raw_val)
    rng = np.random.default_rng(seed + 17)
    d = x_train.shape[1]
    params = {
        "w": np.zeros(d, dtype=np.float64),
        "b": np.zeros(1, dtype=np.float64),
        "v": rng.normal(0.0, 0.01, size=(d, rank)).astype(np.float64),
    }
    opt = Adam(lr)
    n = len(train_items)
    history = []
    for epoch in range(1, epochs + 1):
        order = rng.permutation(n)
        for start in range(0, n, batch_size):
            idx = order[start:start + batch_size]
            xb = x_train[idx].astype(np.float64, copy=False)
            yb = y_train[idx]
            z = _equity_score(xb, base_train[idx], params)
            pred = _sigmoid(z)
            dz = (2.0 * (pred - yb) * pred * (1.0 - pred)) / max(len(idx), 1)
            xv = xb @ params["v"]
            x2 = xb * xb
            grads = {
                "w": xb.T @ dz + l2 * params["w"],
                "b": np.array([dz.sum() + l2 * params["b"][0]]),
                "v": xb.T @ (dz[:, None] * xv)
                     - params["v"] * ((x2.T @ dz)[:, None])
                     + l2 * params["v"],
            }
            opt.step(params, grads)
        if epoch == 1 or epoch == epochs or epoch % max(1, epochs // 5) == 0:
            train_pred = _sigmoid(_equity_score(x_train, base_train, params))
            val_pred = _sigmoid(_equity_score(x_val, base_val, params))
            history.append({
                "epoch": epoch,
                "train": _equity_metrics(train_items, train_pred),
                "val": _equity_metrics(val_items, val_pred),
            })
    fm_train = _equity_metrics(train_items, _sigmoid(_equity_score(x_train, base_train, params)))
    fm_val = _equity_metrics(val_items, _sigmoid(_equity_score(x_val, base_val, params)))
    raw_train_m = _equity_metrics(train_items, raw_train)
    raw_val_m = _equity_metrics(val_items, raw_val)
    model = {
        "type": model_type,
        "rank": rank,
        "include_player": include_player,
        "feature_map": feature_map,
        "w": np.round(params["w"], 6).tolist(),
        "b": np.round(params["b"], 6).tolist(),
        "v": np.round(params["v"], 6).tolist(),
    }
    report = {
        "features": len(feature_map),
        "history": history,
        "train_raw": raw_train_m,
        "train_fm": fm_train,
        "val_raw": raw_val_m,
        "val_fm": fm_val,
        "val_mae_gain_pp": round(float(raw_val_m["mae_pp"] - fm_val["mae_pp"]), 3),
        "val_ece_gain_pp": round(float(raw_val_m["ece_pp"] - fm_val["ece_pp"]), 3),
    }
    return model, report


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--train-rows", type=Path, action="append", required=True)
    ap.add_argument("--val-rows", type=Path, action="append", required=True)
    ap.add_argument("--report-out", type=Path)
    ap.add_argument("--bucket-model-out", type=Path)
    ap.add_argument("--equity-model-out", type=Path)
    ap.add_argument("--relative-model-out", type=Path)
    ap.add_argument("--bucket-streets", default="flop,turn,river")
    ap.add_argument("--equity-target", choices=("multi", "hu"), default="multi")
    ap.add_argument("--rank", type=int, default=4)
    ap.add_argument("--epochs", type=int, default=25)
    ap.add_argument("--batch-size", type=int, default=1024)
    ap.add_argument("--lr", type=float, default=0.01)
    ap.add_argument("--l2", type=float, default=0.0005)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--include-player", action="store_true")
    ap.add_argument("--bucket-strong-nuts-weight", type=float, default=1.0)
    ap.add_argument("--strong-nuts-lowprob-penalty", type=float, default=0.0)
    ap.add_argument("--strong-nuts-lowprob-threshold", type=float, default=0.20)
    ap.add_argument("--max-train-rows", type=int, default=0)
    ap.add_argument("--max-val-rows", type=int, default=0)
    ap.add_argument("--skip-bucket", action="store_true")
    ap.add_argument("--skip-equity", action="store_true")
    ap.add_argument("--skip-river-relative", action="store_true")
    args = ap.parse_args()

    train_rows = _load_rows(args.train_rows, args.max_train_rows)
    val_rows = _load_rows(args.val_rows, args.max_val_rows)
    report: dict[str, Any] = {
        "meta": {
            "train_rows": len(train_rows),
            "val_rows": len(val_rows),
            "rank": args.rank,
            "epochs": args.epochs,
            "batch_size": args.batch_size,
            "lr": args.lr,
            "l2": args.l2,
            "include_player": args.include_player,
            "bucket_strong_nuts_weight": args.bucket_strong_nuts_weight,
            "strong_nuts_lowprob_penalty": args.strong_nuts_lowprob_penalty,
            "strong_nuts_lowprob_threshold": args.strong_nuts_lowprob_threshold,
        }
    }

    if not args.skip_bucket:
        streets = {s.strip() for s in args.bucket_streets.split(",") if s.strip()}
        bucket_train = _filter_bucket_rows(train_rows, streets)
        bucket_val = _filter_bucket_rows(val_rows, streets)
        if not bucket_train or not bucket_val:
            report["bucket"] = {"error": "no bucket rows after filtering"}
        else:
            bucket_model, bucket_report, _extra = _train_bucket_fm(
                bucket_train,
                bucket_val,
                rank=args.rank,
                epochs=args.epochs,
                batch_size=args.batch_size,
                lr=args.lr,
                l2=args.l2,
                seed=args.seed,
                include_player=args.include_player,
                bucket_strong_nuts_weight=args.bucket_strong_nuts_weight,
                strong_nuts_lowprob_penalty=args.strong_nuts_lowprob_penalty,
                strong_nuts_lowprob_threshold=args.strong_nuts_lowprob_threshold,
            )
            report["bucket"] = bucket_report
            _write_json(args.bucket_model_out, bucket_model)

    if not args.skip_equity:
        eq_train = _equity_pairs(train_rows, args.equity_target)
        eq_val = _equity_pairs(val_rows, args.equity_target)
        if not eq_train or not eq_val:
            report["equity"] = {"error": "no equity rows after filtering"}
        else:
            eq_model, eq_report = _train_equity_fm(
                eq_train,
                eq_val,
                rank=args.rank,
                epochs=args.epochs,
                batch_size=args.batch_size,
                lr=args.lr,
                l2=args.l2,
                seed=args.seed,
                include_player=args.include_player,
            )
            report["equity"] = eq_report
            _write_json(args.equity_model_out, eq_model)

    if not args.skip_river_relative:
        rel_train = _relative_pairs(train_rows)
        rel_val = _relative_pairs(val_rows)
        if not rel_train or not rel_val:
            report["river_relative"] = {"error": "no river relative rows after filtering"}
        else:
            rel_model, rel_report = _train_equity_fm(
                rel_train,
                rel_val,
                rank=args.rank,
                epochs=args.epochs,
                batch_size=args.batch_size,
                lr=args.lr,
                l2=args.l2,
                seed=args.seed + 101,
                include_player=args.include_player,
                dense_feature_fn=_dense_relative_features,
                model_type="river_relative_fm_residual",
                include_relative_context=True,
            )
            report["river_relative"] = rel_report
            _write_json(args.relative_model_out, rel_model)

    _write_json(args.report_out, report)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
