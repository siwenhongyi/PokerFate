"""Live check of the opponent-range model against the hands opponents showed.

After every showdown the bot writes what it believed about each opponent at each step
(``local/training/*.rows.jsonl``).  This module reads those rows and answers two
questions about the model the bot is running now:

  * bucket calibration   postflop, is the predicted share of each strength bucket what
                         opponents turn out to hold?  Decisions read the strong + nuts
                         share, so that share is also checked per (street, action) cell —
                         the acceptance test of docs/range_v2_bucket_ml.md, on live rows.
  * street updates       does updating the range on every action make the opponent's real
                         combo more likely than the range the hand started with?

Only rows written since the deployed bucket model, about human opponents, count.  Older rows
describe models that no longer exist; house robots see hole cards and bet without regard to
their own.  Hands at a table the bot would leave (no human, or fewer humans than robots) never
get this far: the strategy writes no rows for them (``PokerFateAPI._hand_skip_learning``), and
the rows written before that rule were removed with ``analysis.robot_relearn rows``.
"""
from __future__ import annotations

import json
import math
import time
from pathlib import Path
from statistics import median
from typing import Any, Callable, Optional

from pokerfate.core.robots import RobotRegistry

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RUNTIME_ROOT = ROOT / "local" / "training"
# The file bucket_ml_calibration loads.  Not imported from there: that pulls in LightGBM.
BUCKET_MODEL = ROOT / "pokerfate" / "data" / "runtime_calibration" / "runtime_lgbm_bucket_model.json"
BUCKETS = ("nuts", "strong", "medium", "draw", "weak_draw", "air")
STREETS = ("preflop", "flop", "turn", "river")
# docs/range_v2_bucket_ml.md accepts a model whose strong + nuts share is within 3 points of
# the truth in every cell with at least 100 rows.
MASS_TOLERANCE = 0.03
MIN_CELL_ROWS = 100
_TS_KEY = '"recorded_at": '


def model_written_at() -> float:
    """When the deployed bucket model was written (0 if there is none)."""
    try:
        return BUCKET_MODEL.stat().st_mtime
    except OSError:
        return 0.0


def range_nll_payload(
    runtime_root: Path | str = DEFAULT_RUNTIME_ROOT,
    *,
    since: Optional[float] = None,
    is_robot: Optional[Callable[[str], bool]] = None,
) -> dict[str, Any]:
    """Score the rows recorded at or after ``since`` (default: the deployed model's write time)."""
    root = Path(runtime_root)
    since_model = since is None
    since = model_written_at() if since_model else float(since)
    if is_robot is None:
        is_robot = RobotRegistry(autosave=False).is_robot
    files = sorted(root.glob("*.rows.jsonl"))
    robots: dict[str, bool] = {}

    def robot(uid: str) -> bool:
        if uid not in robots:
            robots[uid] = bool(uid) and bool(is_robot(uid))
        return robots[uid]

    rows = older = robot_rows = bad_lines = 0
    hands: set[tuple[str, str]] = set()
    updates = _new_acc()
    updates_by_street: dict[str, dict[str, Any]] = {}
    points = _new_points()
    by_bucket = {bucket: _new_points() for bucket in BUCKETS}
    cells: dict[tuple[str, str], list[float]] = {}
    bucket_rows = 0
    mass_sum = held_sum = 0.0

    for path in files:
        with path.open("r", encoding="utf-8") as fh:
            for line in fh:
                if not line.strip():
                    continue
                # Most of the file predates the model; skip those rows without parsing them.
                stamp = _peek_recorded_at(line)
                if stamp is not None and stamp < since:
                    older += 1
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    bad_lines += 1
                    continue
                if stamp is None and _float(row.get("recorded_at"), 0.0) < since:
                    older += 1
                    continue
                if robot(str(row.get("player_uid") or "")):
                    robot_rows += 1
                    continue
                rows += 1
                hands.add(_hand_key(row))
                street = str(row.get("street") or "")
                trigger = str(row.get("trigger") or "")

                delta = _update_gain(row)
                if delta is not None and trigger != "reset":
                    _add_acc(updates, row, delta)
                    _add_acc(updates_by_street.setdefault(street or "unknown", _new_acc()), row, delta)

                probs = _bucket_probs(row) if street in STREETS[1:] else None
                if probs is None:
                    continue
                actual = row["actual_bucket"]
                bucket_rows += 1
                for bucket, prob in zip(BUCKETS, probs):
                    if prob <= 0.0 and bucket != actual:
                        continue          # impossible on this board (no draws on the river)
                    held = 1.0 if bucket == actual else 0.0
                    _add_point(points, prob, held)
                    _add_point(by_bucket[bucket], prob, held)
                mass = probs[0] + probs[1]
                held = 1.0 if actual in BUCKETS[:2] else 0.0
                mass_sum += mass
                held_sum += held
                if trigger == "action:fold_other":
                    # Somebody else folded: this player's range is the one already scored,
                    # re-emitted for hands picked by what happened next.  Not a cell of its own.
                    continue
                cell = cells.setdefault((street, _action(trigger)), [0, 0.0, 0.0, 0.0, 0.0])
                cell[0] += 1
                cell[1] += mass
                cell[2] += held
                cell[3] += mass - held
                cell[4] += (mass - held) ** 2

    overall = _finalize_points(points)
    by_cell = _cell_rows(cells)
    summary = _finalize_acc(updates)
    summary.update({
        "files": len(files),
        "rows": rows,
        "hands": len(hands),
        "older_rows": older,
        "robot_rows": robot_rows,
        "bad_lines": bad_lines,
        "since": since,
        "since_model": since_model,
        "bucket_rows": bucket_rows,
        "bucket_ece": overall["ece"],
        "strong_mass_predicted": mass_sum / bucket_rows if bucket_rows else None,
        "strong_mass_actual": held_sum / bucket_rows if bucket_rows else None,
        "runtime_root": str(root),
        "generated_at": int(time.time()),
    })
    by_street = [
        {**_finalize_acc(updates_by_street[street]), "key": street}
        for street in sorted(updates_by_street, key=_street_rank)
    ]
    calibration = {
        "overall": overall,
        "by_bucket": [
            {**_finalize_points(by_bucket[bucket]), "key": bucket}
            for bucket in BUCKETS if by_bucket[bucket]["points"]
        ],
        "by_cell": by_cell,
    }
    return {
        "ok": True,
        "summary": summary,
        "conclusion": _conclusion(summary, calibration, by_street),
        "by_street": by_street,
        "calibration": calibration,
        "files": [str(path) for path in files],
    }


def _hand_key(row: dict[str, Any]) -> tuple[str, str]:
    """Hand numbers restart with every run of the bot, so the run is part of the key."""
    return str(row.get("session_id") or ""), str(row.get("hand") or "")


def _peek_recorded_at(line: str) -> Optional[int]:
    start = line.find(_TS_KEY)
    if start < 0:
        return None
    start += len(_TS_KEY)
    end = start
    while end < len(line) and line[end].isdigit():
        end += 1
    return int(line[start:end]) if end > start else None


def _street_rank(street: str) -> int:
    return STREETS.index(street) if street in STREETS else len(STREETS)


def _action(trigger: str) -> str:
    """What the range had just been updated on when the prediction was recorded."""
    if trigger in {"action:raise", "action:raise_over"}:
        return "raise"
    if trigger.startswith("action:"):
        return trigger.split(":", 1)[1]
    if trigger.startswith("board:"):
        return "board"
    return "other"


# ── street updates: static (start of hand) range against the updated one ──────────────────

def _update_gain(row: dict[str, Any]) -> Optional[float]:
    """NLL of the opponent's real combo under the starting range minus under the updated one."""
    static = _float_or_none(row.get("nll_static"))
    bayes = _float_or_none(row.get("nll_bayes"))
    if static is None or bayes is None:
        return None
    return static - bayes


def _new_acc() -> dict[str, Any]:
    return {"count": 0, "improved": 0, "worse": 0, "static_prob": 0.0, "bayes_prob": 0.0,
            "static_nll": 0.0, "bayes_nll": 0.0, "deltas": []}


def _add_acc(acc: dict[str, Any], row: dict[str, Any], delta: float) -> None:
    acc["count"] += 1
    acc["improved"] += delta > 1e-9
    acc["worse"] += delta < -1e-9
    acc["static_prob"] += _float(row.get("static_combo_prob"), 0.0)
    acc["bayes_prob"] += _float(row.get("bayes_combo_prob"), 0.0)
    acc["static_nll"] += float(row["nll_static"])
    acc["bayes_nll"] += float(row["nll_bayes"])
    acc["deltas"].append(delta)


def _finalize_acc(acc: dict[str, Any]) -> dict[str, Any]:
    count = int(acc["count"])
    if not count:
        return {"count": 0, "improved": 0, "worse": 0, "positive_rate": None,
                "avg_static_prob": None, "avg_bayes_prob": None, "avg_static_nll": None,
                "avg_bayes_nll": None, "avg_delta_nll": None, "median_delta_nll": None}
    return {
        "count": count,
        "improved": int(acc["improved"]),
        "worse": int(acc["worse"]),
        "positive_rate": acc["improved"] / count,
        "avg_static_prob": acc["static_prob"] / count,
        "avg_bayes_prob": acc["bayes_prob"] / count,
        "avg_static_nll": acc["static_nll"] / count,
        "avg_bayes_nll": acc["bayes_nll"] / count,
        "avg_delta_nll": sum(acc["deltas"]) / count,
        "median_delta_nll": float(median(acc["deltas"])),
    }


# ── bucket calibration ────────────────────────────────────────────────────────────────────

def _bucket_probs(row: dict[str, Any]) -> Optional[list[float]]:
    dist = row.get("bucket_dist")
    if not isinstance(dist, dict) or row.get("actual_bucket") not in BUCKETS:
        return None
    probs = [max(_float(dist.get(bucket), 0.0), 0.0) for bucket in BUCKETS]
    total = sum(probs)
    if total <= 0.0:
        return None
    return [p / total for p in probs]


def _new_points() -> dict[str, Any]:
    return {"points": 0, "prob": 0.0, "held": 0.0, "brier": 0.0,
            "bins": [[0, 0.0, 0.0] for _ in range(10)]}


def _add_point(acc: dict[str, Any], prob: float, held: float) -> None:
    slot = acc["bins"][min(9, int(prob * 10))]
    slot[0] += 1
    slot[1] += prob
    slot[2] += held
    acc["points"] += 1
    acc["prob"] += prob
    acc["held"] += held
    acc["brier"] += (prob - held) ** 2


def _finalize_points(acc: dict[str, Any]) -> dict[str, Any]:
    points = int(acc["points"])
    if not points:
        return {"points": 0, "ece": None, "brier": None, "avg_pred": None, "empirical": None,
                "bias": None, "bias_label": "none", "bins": []}
    bins = []
    ece = 0.0
    for index, (count, prob, held) in enumerate(acc["bins"]):
        if not count:
            continue
        gap = (prob - held) / count
        ece += abs(prob - held) / points
        bins.append({"bin": f"{index * 10}-{index * 10 + 10}%", "count": count,
                     "avg_pred": prob / count, "empirical": held / count, "gap": gap,
                     "bias_label": _bias_label(gap)})
    bias = (acc["prob"] - acc["held"]) / points
    return {"points": points, "ece": ece, "brier": acc["brier"] / points,
            "avg_pred": acc["prob"] / points, "empirical": acc["held"] / points,
            "bias": bias, "bias_label": _bias_label(bias), "bins": bins}


def _bias_label(value: float) -> str:
    if value > MASS_TOLERANCE:
        return "overconfident"
    if value < -MASS_TOLERANCE:
        return "underconfident"
    return "ok"


def _cell_rows(cells: dict[tuple[str, str], list[float]]) -> list[dict[str, Any]]:
    """Strong + nuts share per (street, action): predicted, held, and whether the gap is real."""
    out = []
    for (street, action), (count, mass, held, diff_sum, diff_sq) in cells.items():
        if count < MIN_CELL_ROWS:
            continue
        diff = diff_sum / count
        se = math.sqrt(max(diff_sq / count - diff * diff, 0.0) / count)
        if abs(diff) > MASS_TOLERANCE and abs(diff) > 2.0 * se:
            label = "overconfident" if diff > 0 else "underconfident"
        else:
            label = "ok"
        out.append({"street": street, "action": action, "rows": int(count),
                    "predicted": mass / count, "actual": held / count,
                    "diff": diff, "se": se, "label": label})
    out.sort(key=lambda r: (_street_rank(r["street"]), -r["rows"]))
    return out


# ── summary text ──────────────────────────────────────────────────────────────────────────

_STREET_CN = {"preflop": "翻前", "flop": "翻牌", "turn": "转牌", "river": "河牌"}
_ACTION_CN = {"bet": "下注", "raise": "加注", "call": "跟注", "check": "过牌",
              "board": "发牌后", "fold": "弃牌", "other": "其他"}
_BUCKET_CN = {"nuts": "坚果", "strong": "强牌", "medium": "中等牌", "draw": "听牌",
              "weak_draw": "弱听牌", "air": "空气"}


def _conclusion(
    summary: dict[str, Any],
    calibration: dict[str, Any],
    by_street: list[dict[str, Any]],
) -> list[str]:
    since = float(summary.get("since") or 0.0)
    stamp = time.strftime("%Y-%m-%d %H:%M", time.localtime(since))
    used = f"对手为真人的 {int(summary['rows']):,} 行（{int(summary['hands']):,} 手）"
    older, robots = int(summary["older_rows"]), int(summary["robot_rows"])
    if since <= 0:
        scope = f"口径：全部历史里{used}，旧版模型的行也在内；对手是人机的 {robots:,} 行不计入。"
    elif summary.get("since_model"):
        scope = (f"口径：当前桶模型写入（{stamp}）之后、{used}。"
                 f"更早的 {older:,} 行来自旧版模型、{robots:,} 行的对手是人机，不计入。")
    else:
        scope = f"口径：{stamp} 之后、{used}。更早的 {older:,} 行、对手是人机的 {robots:,} 行不计入。"
    lines = [scope + "需要离桌的牌局（没有真人，或真人少于人机）不产生行；只有打到摊牌并亮牌的对手才有真值。"]
    if not summary.get("bucket_rows"):
        lines.append("这个时间段还没有翻后亮牌样本，打到摊牌后再算。")
        return lines

    worst = max(calibration["by_bucket"], key=lambda r: abs(r["bias"]))
    lines.append(
        f"牌力档分布：翻后 {int(summary['bucket_rows']):,} 行，ECE {summary['bucket_ece']:.4f}；"
        f"偏差最大的一档是{_BUCKET_CN.get(worst['key'], worst['key'])}"
        f"（预测 {worst['avg_pred'] * 100:.1f}%，实际 {worst['empirical'] * 100:.1f}%）。"
    )
    cells = calibration["by_cell"]
    off = sorted((c for c in cells if c["label"] != "ok"), key=lambda c: -abs(c["diff"]))
    predicted, actual = summary["strong_mass_predicted"], summary["strong_mass_actual"]
    head = (
        f"强牌+坚果占比：整体预测 {predicted * 100:.1f}%，实际 {actual * 100:.1f}%；"
        f"{len(cells)} 个街道×动作格子里 {len(off)} 个超出 ±{MASS_TOLERANCE * 100:.0f} 个点"
    )
    if off:
        shown = "、".join(
            f"{_STREET_CN.get(c['street'], c['street'])}{_ACTION_CN.get(c['action'], c['action'])}"
            f"{'高估' if c['diff'] > 0 else '低估'} {abs(c['diff']) * 100:.1f}"
            for c in off[:4]
        )
        lines.append(f"{head}：{shown}。")
    else:
        lines.append(f"{head}。")
    if summary.get("count"):
        gains = "、".join(
            f"{_STREET_CN.get(r['key'], r['key'])} {r['avg_delta_nll']:+.3f}"
            for r in by_street
        )
        lines.append(
            f"逐街更新：ΔNLL 平均 {summary['avg_delta_nll']:+.3f}"
            "（正数表示更新后的范围比起手范围更接近对手真实手牌）"
            + (f"；{gains}。" if gains else "。")
        )
    return lines


def _float_or_none(value: Any) -> Optional[float]:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _float(value: Any, default: float) -> float:
    out = _float_or_none(value)
    return default if out is None else out
