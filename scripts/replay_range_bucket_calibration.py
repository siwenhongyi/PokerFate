"""Replay hands and fit bucket-distribution calibration parameters.

This is the lightweight companion to ``replay_range_calibration``.  It keeps
the expensive hero-equity Monte Carlo out of the loop and records only:

    predicted bucket distribution, actual showdown bucket

The fitted model is intentionally simple and runtime-friendly:

    q_bucket = softmax(gamma * log(p_bucket) + theta_bucket)

At runtime this can be applied by multiplying every combo in a bucket by
``q_bucket / p_bucket``.  That preserves the intra-bucket combo ordering and
only calibrates the bucket compression/expansion step.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
from collections import defaultdict
from pathlib import Path
from typing import Iterable, Optional

import numpy as np

os.environ.setdefault("PYTEST_CURRENT_TEST", "scripts/replay_range_bucket_calibration.py")

from pokerfate.calibration.showdown_calibration import ShowdownCalibrator
from pokerfate.core.card import Card
from pokerfate.strategy.range_v2 import hand_categorizer as hcat
from scripts.hero_name import load_hero_name
from scripts.replay_and_compare import _hero_id, _replay_hand, load_replay


CAT_ORDER = ("nuts", "strong", "medium", "draw", "weak_draw", "air")
POSTFLOP_STREETS = frozenset(("flop", "turn", "river"))
EPS = 1e-6


class BucketCalibrationCollector:
    """ShowdownCalibrator-compatible collector that skips equity MC."""

    def __init__(self, source: str) -> None:
        self.source = source
        self._hand_id = 0
        self._hand_predictions: dict[int, list[dict]] = {}
        self._shown_cards: dict[int, list[Card]] = {}
        self.rows: list[dict] = []

    def start_hand(self, hand_id: int) -> None:
        self._hand_id = int(hand_id)
        self._hand_predictions = {}
        self._shown_cards = {}

    def record_prediction(
        self,
        player_id: int,
        player_name: str,
        street: str,
        board: list[Card],
        weights: np.ndarray,
        hero_cards=None,
        trigger: str = "",
        active_weights=None,
    ) -> None:
        total = float(weights.sum())
        if total <= 1e-15:
            return
        w_norm = weights / total
        bucket_dist = ShowdownCalibrator._compute_bucket_dist(w_norm, board)
        self._hand_predictions.setdefault(player_id, []).append({
            "source": self.source,
            "hand": self._hand_id,
            "street": street,
            "player_id": player_id,
            "player": player_name,
            "trigger": trigger,
            "board": [str(c) for c in board],
            "bucket_dist": bucket_dist,
        })

    def record_actual(
        self,
        player_id: int,
        actual_cards: list[Card],
        final_board: list[Card],
        hero_cards=None,
    ) -> None:
        self._shown_cards[player_id] = list(actual_cards[:2])

    def emit_records_for(
        self,
        player_id: int,
        hero_cards=None,
        final_board: Optional[list[Card]] = None,
    ) -> list:
        actual_cards = self._shown_cards.get(player_id)
        if not actual_cards:
            return []
        for rec in self._hand_predictions.get(player_id, []):
            board = [Card.from_str(s) for s in rec["board"]]
            actual_bucket = hcat.categorize_cards(actual_cards, board if board else [])
            bucket_dist = rec["bucket_dist"]
            row = {
                **rec,
                "actual_cards": [str(c) for c in actual_cards],
                "actual_bucket": actual_bucket,
                "predicted_bucket_prob": float(bucket_dist.get(actual_bucket, 0.0)),
            }
            self.rows.append(row)
        # API hand_over iterates return values for hero equity calibration.
        # Returning [] deliberately skips that expensive path in this script.
        return []

    def finalize_hand_calibration(
        self,
        hero_cards=None,
        final_board: Optional[list[Card]] = None,
    ) -> list:
        for pid in list(self._shown_cards):
            self.emit_records_for(pid, hero_cards=hero_cards, final_board=final_board)
        return []


def _write_rows(rows: Iterable[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def _load_rows(paths: Iterable[Path]) -> list[dict]:
    out: list[dict] = []
    for path in paths:
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    out.append(json.loads(line))
    return out


def _bucket_vec(row: dict) -> np.ndarray:
    dist = row.get("bucket_dist") or {}
    arr = np.array([float(dist.get(cat, 0.0)) for cat in CAT_ORDER], dtype=np.float64)
    total = float(arr.sum())
    if total > 0:
        arr /= total
    else:
        arr[:] = 1.0 / len(CAT_ORDER)
    return np.clip(arr, EPS, 1.0)


def _label_idx(row: dict) -> int:
    bucket = row.get("actual_bucket")
    if bucket not in CAT_ORDER:
        return CAT_ORDER.index("air")
    return CAT_ORDER.index(bucket)


def _softmax(logits: np.ndarray) -> np.ndarray:
    z = logits - logits.max(axis=1, keepdims=True)
    exp = np.exp(z)
    return exp / exp.sum(axis=1, keepdims=True)


def _metrics(rows: list[dict], gamma: float = 1.0,
             theta: Optional[np.ndarray] = None) -> dict:
    if not rows:
        return {
            "n": 0, "nll": 0.0, "actual_bucket_avg_pct": 0.0,
            "under_10_pct": 0.0, "top1_pct": 0.0,
        }
    theta = np.zeros(len(CAT_ORDER), dtype=np.float64) if theta is None else theta
    p = np.vstack([_bucket_vec(r) for r in rows])
    y = np.array([_label_idx(r) for r in rows], dtype=np.int64)
    q = _softmax(gamma * np.log(p) + theta[None, :])
    py = q[np.arange(len(rows)), y]
    return {
        "n": len(rows),
        "nll": round(float(-np.mean(np.log(np.clip(py, EPS, 1.0)))), 5),
        "actual_bucket_avg_pct": round(float(np.mean(py) * 100.0), 2),
        "under_10_pct": round(float(np.mean(py < 0.10) * 100.0), 2),
        "top1_pct": round(float(np.mean(np.argmax(q, axis=1) == y) * 100.0), 2),
    }


def _fit_context(rows: list[dict], *, steps: int, lr: float,
                 l2_theta: float, l2_gamma: float) -> tuple[float, np.ndarray]:
    p = np.vstack([_bucket_vec(r) for r in rows])
    logp = np.log(p)
    y = np.array([_label_idx(r) for r in rows], dtype=np.int64)
    onehot = np.zeros((len(rows), len(CAT_ORDER)), dtype=np.float64)
    onehot[np.arange(len(rows)), y] = 1.0

    gamma = 1.0
    theta = np.zeros(len(CAT_ORDER), dtype=np.float64)
    m_g = v_g = 0.0
    m_t = np.zeros_like(theta)
    v_t = np.zeros_like(theta)
    beta1 = 0.9
    beta2 = 0.999

    for step in range(1, steps + 1):
        q = _softmax(gamma * logp + theta[None, :])
        diff = q - onehot
        grad_theta = diff.mean(axis=0) + 2.0 * l2_theta * theta
        grad_gamma = float((diff * logp).sum(axis=1).mean()
                           + 2.0 * l2_gamma * (gamma - 1.0))

        m_t = beta1 * m_t + (1.0 - beta1) * grad_theta
        v_t = beta2 * v_t + (1.0 - beta2) * (grad_theta * grad_theta)
        mt_hat = m_t / (1.0 - beta1 ** step)
        vt_hat = v_t / (1.0 - beta2 ** step)
        theta -= lr * mt_hat / (np.sqrt(vt_hat) + 1e-8)

        m_g = beta1 * m_g + (1.0 - beta1) * grad_gamma
        v_g = beta2 * v_g + (1.0 - beta2) * (grad_gamma * grad_gamma)
        mg_hat = m_g / (1.0 - beta1 ** step)
        vg_hat = v_g / (1.0 - beta2 ** step)
        gamma -= lr * mg_hat / (math.sqrt(vg_hat) + 1e-8)

        gamma = float(np.clip(gamma, 0.65, 1.60))
        theta = np.clip(theta, -0.75, 0.75)
        # Remove the unidentifiable common offset.
        theta -= float(theta.mean())

    return gamma, theta


def _context_key(row: dict) -> str:
    return f"{row.get('street')} {row.get('trigger')}"


def search_params(train_rows: list[dict], val_rows: list[dict], *,
                  min_train: int, min_val: int, steps: int, lr: float,
                  l2_theta: float, l2_gamma: float,
                  min_val_nll_gain: float) -> dict:
    train_groups: dict[str, list[dict]] = defaultdict(list)
    val_groups: dict[str, list[dict]] = defaultdict(list)
    for row in train_rows:
        if row.get("street") in POSTFLOP_STREETS:
            train_groups[_context_key(row)].append(row)
    for row in val_rows:
        if row.get("street") in POSTFLOP_STREETS:
            val_groups[_context_key(row)].append(row)

    contexts = []
    accepted = {}
    for key, rows in sorted(train_groups.items()):
        val = val_groups.get(key, [])
        if len(rows) < min_train or len(val) < min_val:
            continue
        gamma, theta = _fit_context(
            rows, steps=steps, lr=lr,
            l2_theta=l2_theta, l2_gamma=l2_gamma,
        )
        base_train = _metrics(rows)
        fit_train = _metrics(rows, gamma, theta)
        base_val = _metrics(val)
        fit_val = _metrics(val, gamma, theta)
        val_gain = base_val["nll"] - fit_val["nll"]
        item = {
            "context": key,
            "gamma": round(float(gamma), 4),
            "theta": {
                cat: round(float(v), 4)
                for cat, v in zip(CAT_ORDER, theta)
                if abs(float(v)) >= 0.005
            },
            "train_base": base_train,
            "train_fit": fit_train,
            "val_base": base_val,
            "val_fit": fit_val,
            "val_nll_gain": round(float(val_gain), 5),
        }
        contexts.append(item)
        if val_gain >= min_val_nll_gain:
            accepted[key] = {
                "gamma": item["gamma"],
                "theta": item["theta"],
            }
    contexts.sort(key=lambda x: (x["val_nll_gain"], x["val_base"]["n"]), reverse=True)
    return {
        "accepted": accepted,
        "contexts": contexts,
        "settings": {
            "min_train": min_train,
            "min_val": min_val,
            "steps": steps,
            "lr": lr,
            "l2_theta": l2_theta,
            "l2_gamma": l2_gamma,
            "min_val_nll_gain": min_val_nll_gain,
        },
    }


def replay_rows(args: argparse.Namespace) -> list[dict]:
    try:
        hero_name = load_hero_name()
    except RuntimeError as exc:
        raise SystemExit(str(exc)) from exc

    from pokerfate.api import PokerFateAPI

    all_rows: list[dict] = []
    for replay_path in args.replay:
        hands = load_replay(replay_path)
        if args.max_hands > 0:
            hands = hands[:args.max_hands]

        last_session = None
        api: Optional[PokerFateAPI] = None
        played = 0
        skipped_no_hero = 0
        collector: Optional[BucketCalibrationCollector] = None

        for hand in hands:
            hero_id = _hero_id(hand.get("players", []), hero_name)
            if hero_id is None:
                skipped_no_hero += 1
                continue
            session = hand.get("session", 0)
            if session != last_session or api is None or hero_id != api.my_player_id:
                api = PokerFateAPI(
                    my_player_id=hero_id,
                    big_blind=2.0,
                    autosave_path=None,
                    log_file=None,
                    verbose=False,
                    equity_iterations=args.equity_iterations,
                    enable_showdown_calibration=True,
                    decision_seed=args.seed,
                )
                api._log._console = False
                collector = BucketCalibrationCollector(str(replay_path))
                api._calibrator = collector
                last_session = session

            _replay_hand(api, hand, hero_id)
            played += 1
            if collector is not None and collector.rows:
                all_rows.extend(collector.rows)
                collector.rows = []
            if args.progress_every > 0 and played % args.progress_every == 0:
                print(
                    f"replayed {played}/{len(hands)} hands from {replay_path}, "
                    f"rows={len(all_rows)} skipped_no_hero={skipped_no_hero}",
                    file=sys.stderr,
                    flush=True,
                )
    return all_rows


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--replay", type=Path, action="append", default=[])
    ap.add_argument("--rows-out", type=Path)
    ap.add_argument("--train-rows", type=Path, action="append", default=[])
    ap.add_argument("--val-rows", type=Path, action="append", default=[])
    ap.add_argument("--params-out", type=Path)
    ap.add_argument("--max-hands", type=int, default=0)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--equity-iterations", type=int, default=80)
    ap.add_argument("--progress-every", type=int, default=250)
    ap.add_argument("--min-train", type=int, default=80)
    ap.add_argument("--min-val", type=int, default=30)
    ap.add_argument("--steps", type=int, default=500)
    ap.add_argument("--lr", type=float, default=0.035)
    ap.add_argument("--l2-theta", type=float, default=0.03)
    ap.add_argument("--l2-gamma", type=float, default=0.20)
    ap.add_argument("--min-val-nll-gain", type=float, default=0.002)
    args = ap.parse_args()

    rows: list[dict] = []
    if args.replay:
        rows = replay_rows(args)
        if args.rows_out:
            _write_rows(rows, args.rows_out)

    result = {
        "replay_rows": len(rows),
        "rows_out": str(args.rows_out) if args.rows_out else None,
    }

    if args.train_rows and args.val_rows:
        train_rows = _load_rows(args.train_rows)
        val_rows = _load_rows(args.val_rows)
        search = search_params(
            train_rows, val_rows,
            min_train=args.min_train,
            min_val=args.min_val,
            steps=args.steps,
            lr=args.lr,
            l2_theta=args.l2_theta,
            l2_gamma=args.l2_gamma,
            min_val_nll_gain=args.min_val_nll_gain,
        )
        result["search"] = search
        if args.params_out:
            args.params_out.parent.mkdir(parents=True, exist_ok=True)
            args.params_out.write_text(
                json.dumps(search["accepted"], ensure_ascii=False, indent=2, sort_keys=True),
                encoding="utf-8",
            )

    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
