"""Offline bucket calibration view for realtime CFR consumers.

This module does not change Range V2's stored posterior.  It builds a compact
calibration table from runtime rows and returns a calibrated view that CFR can
consume while logs keep both raw and effective values visible.
"""

from __future__ import annotations

import json
import math
import os
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional


CAT_ORDER = ("nuts", "strong", "medium", "draw", "weak_draw", "air")
DEFAULT_RUNTIME_ROOT = Path(__file__).resolve().parents[3] / "data" / "runtime_calibration"
MODEL_KEY = "all_bb"
FALLBACK_BUCKET_PRIOR = {
    "nuts": 0.06,
    "strong": 0.24,
    "medium": 0.34,
    "draw": 0.07,
    "weak_draw": 0.07,
    "air": 0.22,
}
MIN_ROWS_BY_LEVEL = {
    "line": 80,
    "size": 70,
    "action": 60,
    "street": 45,
    "overall": 1,
}
DEFAULT_RAW_RELIABILITY = 0.85
_CACHE_TTL_SEC = 30.0
_MODEL_CACHE: dict[tuple[str, str], "_CECCacheState"] = {}


@dataclass(frozen=True)
class CECGroup:
    key: str
    level: str
    rows: int
    points: int
    ece: float
    avg_pred: dict[str, float]
    empirical: dict[str, float]


@dataclass(frozen=True)
class CECModel:
    root: str
    bb_bucket: str
    files: int
    rows: int
    groups: dict[str, dict[str, CECGroup]]
    overall: Optional[CECGroup]


class _CECCacheState:
    def __init__(self, *, root: Path, key: str) -> None:
        self.root = root
        self.key = key
        self.lock = threading.Lock()
        self.refreshing = False
        self.last_check = 0.0
        self.model = _empty_model(root=root, bb_bucket=key)
        self.groups_acc = _new_groups_acc()
        self.offsets: dict[str, int] = {}
        self.rows = 0


def calibrate_range_v2_prior(
    prior: dict[str, Any],
    *,
    big_blind: Any = None,
    runtime_root: Path | str | None = None,
    blocking: bool = False,
) -> dict[str, Any]:
    """Return a CFR-facing calibrated prior while preserving raw values."""
    if not isinstance(prior, dict) or not prior:
        return prior if isinstance(prior, dict) else {}
    raw_bucket = _normalize_bucket_dist(prior.get("bucket_dist"))
    if not raw_bucket:
        return dict(prior)

    context = _context_from_prior(prior)
    calibrated, diag = calibrate_bucket_dist(
        raw_bucket,
        context=context,
        big_blind=big_blind,
        runtime_root=runtime_root,
        blocking=blocking,
    )
    out = dict(prior)
    out["raw_bucket_dist"] = raw_bucket
    out["bucket_dist"] = calibrated

    raw_vs_hero = _normalize_vs_hero(prior.get("vs_hero"))
    if raw_vs_hero:
        out["raw_vs_hero"] = raw_vs_hero
        out["vs_hero"] = _calibrate_vs_hero_from_bucket_shift(
            raw_vs_hero,
            raw_bucket=raw_bucket,
            calibrated_bucket=calibrated,
            reliability=float(diag.get("raw_reliability", DEFAULT_RAW_RELIABILITY)),
        )

    out["cec_calibration"] = diag
    return out


def calibrate_bucket_dist(
    bucket_dist: dict[str, Any],
    *,
    context: dict[str, Any] | None = None,
    big_blind: Any = None,
    runtime_root: Path | str | None = None,
    blocking: bool = False,
) -> tuple[dict[str, float], dict[str, Any]]:
    raw = _normalize_bucket_dist(bucket_dist)
    if not raw:
        return {}, {"used": False, "reason": "empty_bucket_dist"}

    model = load_cec_model(big_blind=big_blind, runtime_root=runtime_root, blocking=blocking)
    group = _select_group(model, context or {})
    if group is None:
        calibrated = _blend(raw, FALLBACK_BUCKET_PRIOR, 1.0 - DEFAULT_RAW_RELIABILITY)
        return calibrated, {
            "used": True,
            "source": "default_prior",
            "level": "default",
            "key": "fallback",
            "rows": 0,
            "points": 0,
            "ece": None,
            "raw_reliability": DEFAULT_RAW_RELIABILITY,
            "shift": _bucket_shift(raw, calibrated),
            "files": model.files,
            "runtime_rows": model.rows,
        }

    sample_conf = group.rows / (group.rows + 120.0)
    ece_reliability = _clamp(1.0 - group.ece / 0.24, 0.25, 0.95)
    raw_reliability = _clamp(0.68 * ece_reliability + 0.32 * sample_conf, 0.35, 0.93)
    bias_strength = _clamp((1.0 - raw_reliability) * 0.90, 0.04, 0.48)
    corrected = {}
    for bucket in CAT_ORDER:
        bias = group.avg_pred.get(bucket, 0.0) - group.empirical.get(bucket, 0.0)
        corrected[bucket] = max(0.0, raw.get(bucket, 0.0) - bias_strength * bias)
    corrected = _normalize_bucket_dist(corrected)
    prior_strength = _clamp((1.0 - raw_reliability) * sample_conf * 0.35, 0.0, 0.22)
    calibrated = _blend(corrected, group.empirical, prior_strength)
    return calibrated, {
        "used": True,
        "source": "runtime_cec",
        "level": group.level,
        "key": group.key,
        "rows": group.rows,
        "points": group.points,
        "ece": group.ece,
        "raw_reliability": raw_reliability,
        "sample_confidence": sample_conf,
        "bias_strength": bias_strength,
        "prior_strength": prior_strength,
        "shift": _bucket_shift(raw, calibrated),
        "files": model.files,
        "runtime_rows": model.rows,
    }


def load_cec_model(
    *,
    big_blind: Any = None,
    runtime_root: Path | str | None = None,
    blocking: bool = False,
) -> CECModel:
    root = Path(runtime_root) if runtime_root is not None else DEFAULT_RUNTIME_ROOT
    key = MODEL_KEY
    cache_key = (str(root), key)
    now = time.time()
    state = _MODEL_CACHE.get(cache_key)
    if state is None:
        state = _CECCacheState(root=root, key=key)
        _MODEL_CACHE[cache_key] = state

    with state.lock:
        model = state.model
        stale = now - state.last_check > _CACHE_TTL_SEC
    if not blocking and not stale:
        return model

    if blocking:
        _refresh_state(state)
        with state.lock:
            return state.model

    _schedule_refresh(state)
    return model


def context_keys(context: dict[str, Any]) -> dict[str, str]:
    street = str(context.get("street") or "unknown").lower()
    action = str(context.get("action") or "passive").lower()
    size = str(context.get("size") or "") or _size_bucket(context.get("bet_ratio"))
    if action in {"check", "call", "fold", "fold_other", "board", "passive"} and size == "none":
        size = action
    raise_flag = "raise_over" if bool(context.get("is_raise_over")) else "single"
    return {
        "line": f"{street}|{action}|{size}|{raise_flag}",
        "size": size,
        "action": action,
        "street": street,
        "overall": "overall",
    }


def row_context(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "street": str(row.get("street") or "unknown").lower(),
        "action": _action_ctx(str(row.get("trigger") or "")),
        "size": str(row.get("bet_size_bucket") or "") or _size_bucket(row.get("action_bet_ratio")),
        "bet_ratio": row.get("action_bet_ratio"),
        "is_raise_over": bool(row.get("is_raise_over")),
    }


def _new_groups_acc() -> dict[str, dict[str, dict[str, Any]]]:
    return {
        "line": {},
        "size": {},
        "action": {},
        "street": {},
        "overall": {},
    }


def _empty_model(*, root: Path, bb_bucket: str) -> CECModel:
    return CECModel(
        root=str(root),
        bb_bucket=bb_bucket,
        files=0,
        rows=0,
        groups={level: {} for level in ("line", "size", "action", "street", "overall")},
        overall=None,
    )


def _schedule_refresh(state: _CECCacheState) -> None:
    with state.lock:
        if state.refreshing:
            return
        state.refreshing = True
    thread = threading.Thread(target=_refresh_state, args=(state,), daemon=True)
    thread.start()


def _refresh_state(state: _CECCacheState) -> None:
    try:
        files = _row_files(state.root, state.key)
        with state.lock:
            state.last_check = time.time()
            tracked = {str(path) for path in files}
            reset = any(str(path) not in tracked for path in state.offsets)
            if not reset:
                for path in files:
                    try:
                        reset = path.stat().st_size < int(state.offsets.get(str(path), 0) or 0)
                    except OSError:
                        reset = True
                    if reset:
                        break
            if reset:
                state.groups_acc = _new_groups_acc()
                state.offsets = {}
                state.rows = 0

        for path in files:
            _consume_file_increment(state, path)

        with state.lock:
            state.model = _finalize_model(
                root=state.root,
                bb_bucket=state.key,
                files=len(files),
                rows=state.rows,
                groups_acc=state.groups_acc,
            )
    finally:
        with state.lock:
            state.refreshing = False


def _consume_file_increment(state: _CECCacheState, path: Path) -> None:
    path_key = str(path)
    with state.lock:
        offset = int(state.offsets.get(path_key, 0) or 0)
    local_groups = _new_groups_acc()
    local_rows = 0
    try:
        with path.open("r", encoding="utf-8") as fh:
            fh.seek(offset)
            while True:
                line = fh.readline()
                if not line:
                    break
                try:
                    row = json.loads(line)
                except Exception:
                    continue
                if _add_model_row(local_groups, row):
                    local_rows += 1
            end_pos = fh.tell()
    except OSError:
        return
    with state.lock:
        _merge_groups_acc(state.groups_acc, local_groups)
        state.rows += local_rows
        state.offsets[path_key] = int(end_pos)


def _add_model_row(groups: dict[str, dict[str, dict[str, Any]]], row: dict[str, Any]) -> bool:
    actual = str(row.get("actual_bucket") or "")
    raw = _normalize_bucket_dist(row.get("bucket_dist"))
    if actual not in CAT_ORDER or not raw:
        return False
    if str(row.get("trigger") or "") == "reset":
        return False
    keys = context_keys(row_context(row))
    for level, key in keys.items():
        _add_group_row(groups.setdefault(level, {}).setdefault(key, _new_group_acc()), raw, actual)
    return True


def _merge_groups_acc(
    target: dict[str, dict[str, dict[str, Any]]],
    source: dict[str, dict[str, dict[str, Any]]],
) -> None:
    for level, groups in source.items():
        target_level = target.setdefault(level, {})
        for key, acc in groups.items():
            target_acc = target_level.setdefault(key, _new_group_acc())
            target_acc["rows"] += int(acc.get("rows", 0) or 0)
            target_acc["points"] += int(acc.get("points", 0) or 0)
            for bucket in CAT_ORDER:
                target_acc["prob_sum"][bucket] += float(acc["prob_sum"].get(bucket, 0.0))
                target_acc["actual_sum"][bucket] += float(acc["actual_sum"].get(bucket, 0.0))
            for idx, bin_acc in enumerate(list(acc.get("bins") or [])):
                if idx >= len(target_acc["bins"]):
                    break
                target_bin = target_acc["bins"][idx]
                target_bin["count"] += int(bin_acc.get("count", 0) or 0)
                target_bin["prob_sum"] += float(bin_acc.get("prob_sum", 0.0))
                target_bin["actual_sum"] += float(bin_acc.get("actual_sum", 0.0))


def _build_model(*, root: Path, bb_bucket: str, files: list[Path]) -> CECModel:
    groups = _new_groups_acc()
    rows = 0
    for path in files:
        try:
            fh = path.open("r", encoding="utf-8")
        except OSError:
            continue
        with fh:
            for line in fh:
                try:
                    row = json.loads(line)
                except Exception:
                    continue
                if _add_model_row(groups, row):
                    rows += 1

    return _finalize_model(root=root, bb_bucket=bb_bucket, files=len(files), rows=rows, groups_acc=groups)


def _finalize_model(
    *,
    root: Path,
    bb_bucket: str,
    files: int,
    rows: int,
    groups_acc: dict[str, dict[str, dict[str, Any]]],
) -> CECModel:
    finalized: dict[str, dict[str, CECGroup]] = {}
    for level, level_groups in groups_acc.items():
        finalized[level] = {}
        for key, acc in level_groups.items():
            group = _finalize_group(key=key, level=level, acc=acc)
            if group is not None:
                finalized[level][key] = group
    return CECModel(
        root=str(root),
        bb_bucket=bb_bucket,
        files=files,
        rows=rows,
        groups=finalized,
        overall=finalized.get("overall", {}).get("overall"),
    )


def _new_group_acc() -> dict[str, Any]:
    return {
        "rows": 0,
        "points": 0,
        "prob_sum": {bucket: 0.0 for bucket in CAT_ORDER},
        "actual_sum": {bucket: 0.0 for bucket in CAT_ORDER},
        "bins": [
            {"count": 0, "prob_sum": 0.0, "actual_sum": 0.0}
            for _ in range(10)
        ],
    }


def _add_group_row(acc: dict[str, Any], probs: dict[str, float], actual_bucket: str) -> None:
    acc["rows"] += 1
    for bucket in CAT_ORDER:
        prob = float(probs.get(bucket, 0.0))
        actual = 1.0 if bucket == actual_bucket else 0.0
        acc["prob_sum"][bucket] += prob
        acc["actual_sum"][bucket] += actual
        acc["points"] += 1
        idx = min(9, max(0, int(prob * 10)))
        bin_acc = acc["bins"][idx]
        bin_acc["count"] += 1
        bin_acc["prob_sum"] += prob
        bin_acc["actual_sum"] += actual


def _finalize_group(*, key: str, level: str, acc: dict[str, Any]) -> Optional[CECGroup]:
    rows = int(acc.get("rows", 0) or 0)
    points = int(acc.get("points", 0) or 0)
    if rows <= 0 or points <= 0:
        return None
    ece = 0.0
    for bin_acc in list(acc.get("bins") or []):
        count = int(bin_acc.get("count", 0) or 0)
        if count <= 0:
            continue
        avg_pred = float(bin_acc.get("prob_sum", 0.0)) / count
        empirical = float(bin_acc.get("actual_sum", 0.0)) / count
        ece += (count / points) * abs(avg_pred - empirical)
    return CECGroup(
        key=key,
        level=level,
        rows=rows,
        points=points,
        ece=ece,
        avg_pred={
            bucket: float(acc["prob_sum"][bucket]) / rows for bucket in CAT_ORDER
        },
        empirical={
            bucket: float(acc["actual_sum"][bucket]) / rows for bucket in CAT_ORDER
        },
    )


def _select_group(model: CECModel, context: dict[str, Any]) -> Optional[CECGroup]:
    keys = context_keys(context)
    for level in ("line", "size", "action", "street", "overall"):
        group = model.groups.get(level, {}).get(keys[level])
        if group is not None and group.rows >= MIN_ROWS_BY_LEVEL[level]:
            return group
    return model.overall


def _context_from_prior(prior: dict[str, Any]) -> dict[str, Any]:
    ctx = prior.get("action_context") if isinstance(prior.get("action_context"), dict) else {}
    action = str(ctx.get("action") or "passive").lower()
    street = str(ctx.get("street") or "unknown").lower()
    bet_ratio = _as_float(ctx.get("bet_ratio"), 0.0)
    return {
        "street": street,
        "action": action,
        "bet_ratio": bet_ratio,
        "size": _size_bucket(bet_ratio) if bet_ratio > 0 else action,
        "is_raise_over": bool(ctx.get("is_raise_over")),
    }


def _row_files(root: Path, key: str) -> list[Path]:
    if key != MODEL_KEY:
        exact = sorted((root / key).glob("*.rows.jsonl"))
        if exact:
            return exact
    return sorted(root.glob("bb_*/*.rows.jsonl"))


def _newest_mtime(root: Path) -> float:
    newest = 0.0
    for path in root.glob("bb_*/*.rows.jsonl"):
        try:
            newest = max(newest, path.stat().st_mtime)
        except OSError:
            continue
    return newest


def _normalize_bucket_dist(raw: Any) -> dict[str, float]:
    if not isinstance(raw, dict):
        return {}
    out = {bucket: max(0.0, _as_float(raw.get(bucket), 0.0)) for bucket in CAT_ORDER}
    total = sum(out.values())
    if total <= 1e-12:
        return {}
    return {bucket: value / total for bucket, value in out.items()}


def _normalize_vs_hero(raw: Any) -> dict[str, float]:
    if not isinstance(raw, dict):
        return {}
    out = {key: max(0.0, _as_float(raw.get(key), 0.0)) for key in ("win", "tie", "loss")}
    total = sum(out.values())
    if total <= 1e-12:
        return {}
    return {key: value / total for key, value in out.items()}


def _blend(base: dict[str, float], prior: dict[str, float], amount: float) -> dict[str, float]:
    amount = _clamp(amount, 0.0, 1.0)
    raw = {
        bucket: (1.0 - amount) * float(base.get(bucket, 0.0)) + amount * float(prior.get(bucket, 0.0))
        for bucket in CAT_ORDER
    }
    return _normalize_bucket_dist(raw)


def _bucket_shift(raw: dict[str, float], calibrated: dict[str, float]) -> dict[str, float]:
    return {
        bucket: round(float(calibrated.get(bucket, 0.0)) - float(raw.get(bucket, 0.0)), 6)
        for bucket in CAT_ORDER
        if abs(float(calibrated.get(bucket, 0.0)) - float(raw.get(bucket, 0.0))) > 1e-6
    }


def _calibrate_vs_hero_from_bucket_shift(
    raw: dict[str, float],
    *,
    raw_bucket: dict[str, float],
    calibrated_bucket: dict[str, float],
    reliability: float,
) -> dict[str, float]:
    raw_strength = _villain_strength(raw_bucket)
    cal_strength = _villain_strength(calibrated_bucket)
    delta = _clamp((raw_strength - cal_strength) * (1.0 - _clamp(reliability, 0.0, 1.0)) * 0.55, -0.12, 0.12)
    out = {
        "win": max(0.0, float(raw.get("win", 0.0)) + delta),
        "tie": max(0.0, float(raw.get("tie", 0.0))),
        "loss": max(0.0, float(raw.get("loss", 0.0)) - delta),
    }
    total = sum(out.values())
    if total <= 1e-12:
        return raw
    return {key: value / total for key, value in out.items()}


def _villain_strength(bucket: dict[str, float]) -> float:
    return _clamp(
        1.0 * bucket.get("nuts", 0.0)
        + 0.72 * bucket.get("strong", 0.0)
        + 0.38 * bucket.get("medium", 0.0)
        + 0.18 * bucket.get("draw", 0.0)
        + 0.10 * bucket.get("weak_draw", 0.0)
        - 0.22 * bucket.get("air", 0.0),
        -1.0,
        1.0,
    )


def _action_ctx(trigger: str) -> str:
    if trigger in {"action:raise", "action:raise_over"}:
        return "raise"
    if trigger == "action:bet":
        return "bet"
    if trigger == "action:call":
        return "call"
    if trigger == "action:check":
        return "check"
    if trigger == "action:fold":
        return "fold"
    if trigger == "action:fold_other":
        return "fold_other"
    if trigger.startswith("board:"):
        return "board"
    return "passive"


def _size_bucket(value: Any) -> str:
    ratio = _as_float(value, 0.0)
    if ratio <= 0.0:
        return "none"
    if ratio <= 0.25:
        return "small"
    if ratio <= 0.40:
        return "third"
    if ratio <= 0.55:
        return "half"
    if ratio <= 0.80:
        return "two_third"
    if ratio <= 1.10:
        return "pot"
    if ratio <= 1.75:
        return "overpot"
    return "huge"


def _as_float(value: Any, default: float) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return default
    if not math.isfinite(out):
        return default
    return out


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, float(value)))


if os.environ.get("PF_CEC_CALIBRATION_PRELOAD", "").lower() in {"1", "true", "yes"}:
    load_cec_model(big_blind=None, blocking=True)
