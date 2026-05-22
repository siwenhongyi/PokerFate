"""Runtime collection of Range V2 calibration rows.

The expensive replay extractor exists because historical console logs do not
already contain training rows. In live play the ShowdownCalibrator already has
the prediction snapshots and showdown truth, so this module only serializes
those CalibrationResult objects into append-only JSONL files.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any, Iterable, Optional

from pokerfate.calibration.showdown_calibration import CalibrationResult

_SCHEMA = "runtime_range_calibration_v2"
_RIVER_VALUE_SIZING_SCHEMA = "runtime_river_value_sizing_v1"
_EXPERIMENT_FLAG_DEFAULTS = {
    "PF_TURN_FLOP_RELATIVE_GUARD": "1",
    "PF_RUNTIME_RANGE_CALIBRATION": "1",
    "PF_BUCKET_CALIBRATION": "1",
    "PF_BUCKET_ML_10K": "off",
    "PF_BUCKET_ML_50K": "off",
    "PF_BUCKET_ML_DEFAULT": "off",
    "PF_BUCKET_ML_TAG": "20260522_riskblend",
    "PF_POSTFLOP_PROFIT_EXPAND_V1": "0",
}


def _cards_str(cards: Iterable[Any] | None) -> list[str]:
    return [str(c) for c in (cards or [])]


def _json_safe(value: Any) -> Any:
    """Return a value that can be safely appended to JSONL."""
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(v) for v in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _bb_key(big_blind: float) -> str:
    bb = float(big_blind or 0.0)
    rounded = round(bb)
    if abs(bb - rounded) < 1e-6:
        bb_int = int(rounded)
        if bb_int >= 1000 and bb_int % 1000 == 0:
            return f"bb_{bb_int // 1000}k"
        return f"bb_{bb_int}"
    return "bb_" + str(bb).replace(".", "_")


def _default_root() -> Path:
    return Path(__file__).resolve().parents[2] / "data" / "runtime_calibration"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _git_output(args: list[str]) -> str:
    try:
        out = subprocess.check_output(
            ["git", "-C", str(_repo_root()), *args],
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=2.0,
        )
    except Exception:
        return ""
    return out.strip()


def _git_meta() -> dict[str, Any]:
    commit = _git_output(["rev-parse", "--short=12", "HEAD"]) or "unknown"
    status = _git_output(["status", "--porcelain"])
    diff = _git_output(["diff", "--no-ext-diff", "--no-color"])
    dirty = bool(status)
    diff_hash = hashlib.sha1(diff.encode("utf-8")).hexdigest()[:10] if diff else ""
    strategy_version = commit
    if dirty:
        strategy_version += f"+dirty.{diff_hash or 'status'}"
    return {
        "git_commit": commit,
        "git_dirty": dirty,
        "git_diff_hash": diff_hash,
        "strategy_version": os.environ.get("PF_STRATEGY_VERSION", strategy_version),
    }


def _experiment_flags() -> dict[str, str]:
    flags = {
        key: str(os.environ.get(key, default))
        for key, default in _EXPERIMENT_FLAG_DEFAULTS.items()
    }
    # Keep explicitly supplied PF_* overrides visible without turning the row
    # into a dump of unrelated process environment.
    for key, value in os.environ.items():
        if key.startswith("PF_") and key not in flags:
            flags[key] = str(value)
    return dict(sorted(flags.items()))


class RuntimeCalibrationRecorder:
    """Append showdown calibration rows split by big blind and train/val.

    Split is deterministic per hand, so all rows from the same hand go to the
    same file. The recorder does no poker computation; it only writes rows.
    """

    def __init__(
        self,
        root: Optional[Path | str] = None,
        *,
        session_id: Optional[str] = None,
        val_ratio: float = 0.20,
    ) -> None:
        self.root = Path(root) if root is not None else _default_root()
        self.session_id = session_id or f"{int(time.time())}-{os.getpid()}"
        self.val_ratio = min(max(float(val_ratio), 0.0), 0.9)
        git_meta = _git_meta()
        self.strategy_version = str(git_meta["strategy_version"])
        self.experiment_flags = _experiment_flags()
        self.git_meta = git_meta

    def write_results(
        self,
        results: Iterable[CalibrationResult],
        *,
        big_blind: float,
        final_board: Iterable[Any] | None = None,
        source: str = "runtime",
    ) -> int:
        rows_by_path: dict[Path, list[dict[str, Any]]] = {}
        count = 0
        for result in results:
            row = self._row_from_result(
                result,
                big_blind=big_blind,
                final_board=final_board,
                source=source,
            )
            split = row["split"]
            path = self.root / row["bb_bucket"] / f"{split}.rows.jsonl"
            rows_by_path.setdefault(path, []).append(row)
            count += 1

        for path, rows in rows_by_path.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as f:
                for row in rows:
                    f.write(json.dumps(row, ensure_ascii=False, sort_keys=True))
                    f.write("\n")
        return count

    def write_river_value_sizing(
        self,
        row: dict[str, Any],
        *,
        big_blind: float,
        hand_id: int,
        source: str = "runtime",
    ) -> int:
        """Append one river value sizing training row.

        This is intentionally separate from range/bucket calibration rows:
        those rows learn "what did villain have", while this row learns
        "when hero used this value size, did worse hands pay or did the bet
        only fold out worse / get raised by better".
        """
        split = self._split_for_hand(hand_id, big_blind)
        bb_bucket = _bb_key(big_blind)
        out = {
            "schema": _RIVER_VALUE_SIZING_SCHEMA,
            "source": source,
            "session_id": self.session_id,
            "recorded_at": int(time.time()),
            "strategy_version": self.strategy_version,
            "experiment_flags": dict(self.experiment_flags),
            "git_commit": self.git_meta.get("git_commit", "unknown"),
            "git_dirty": bool(self.git_meta.get("git_dirty", False)),
            "git_diff_hash": self.git_meta.get("git_diff_hash", ""),
            "split": split,
            "bb": float(big_blind or 0.0),
            "bb_bucket": bb_bucket,
            "hand": int(hand_id),
        }
        out.update(_json_safe(row))
        path = self.root / bb_bucket / f"river_value_sizing.{split}.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(out, ensure_ascii=False, sort_keys=True))
            f.write("\n")
        return 1

    def _split_for_hand(self, hand_id: int, big_blind: float) -> str:
        key = f"{self.session_id}|{_bb_key(big_blind)}|{int(hand_id)}"
        digest = hashlib.sha1(key.encode("utf-8")).hexdigest()
        bucket = int(digest[:8], 16) % 10000
        return "val" if bucket < int(self.val_ratio * 10000) else "train"

    def _row_from_result(
        self,
        result: CalibrationResult,
        *,
        big_blind: float,
        final_board: Iterable[Any] | None,
        source: str,
    ) -> dict[str, Any]:
        rec = result.record
        split = self._split_for_hand(rec.hand_id, big_blind)
        return {
            "schema": _SCHEMA,
            "source": source,
            "session_id": self.session_id,
            "recorded_at": int(time.time()),
            "strategy_version": self.strategy_version,
            "experiment_flags": dict(self.experiment_flags),
            "calibration_enabled": True,
            "git_commit": self.git_meta.get("git_commit", "unknown"),
            "git_dirty": bool(self.git_meta.get("git_dirty", False)),
            "git_diff_hash": self.git_meta.get("git_diff_hash", ""),
            "split": split,
            "bb": float(big_blind or 0.0),
            "bb_bucket": _bb_key(big_blind),
            "hand": int(rec.hand_id),
            "street": rec.street,
            "player": rec.player_name,
            "player_id": rec.player_id,
            "trigger": rec.trigger,
            "board": _cards_str(rec.board),
            "final_board": _cards_str(final_board),
            "actual_cards": _cards_str(result.actual_cards),
            "actual_bucket": result.actual_bucket,
            "range_pct": float(getattr(rec, "range_pct", 0.0) or 0.0),
            "bucket_dist": dict(rec.bucket_dist or {}),
            "predicted_bucket_prob": float(result.predicted_bucket_prob or 0.0),
            "hero_cards": _cards_str(getattr(rec, "hero_cards", None)),
            "hero_bucket": getattr(rec, "hero_bucket", "") or "",
            "hero_made_subtype": getattr(rec, "hero_made_subtype", "") or "",
            "hero_hand_rank": getattr(rec, "hero_hand_rank", "") or "",
            "board_texture": getattr(rec, "board_texture", "") or "",
            "villain_vs_hero_dist": dict(getattr(rec, "villain_vs_hero_dist", {}) or {}),
            "predicted_relation_eq": (
                float(result.predicted_relation_eq)
                if result.predicted_relation_eq is not None else None
            ),
            "actual_relation": result.actual_relation or "",
            "predicted_hero_eq": (
                float(rec.predicted_hero_eq)
                if rec.predicted_hero_eq is not None else None
            ),
            "actual_hero_eq_street": (
                float(result.actual_hero_eq_street)
                if result.actual_hero_eq_street is not None else None
            ),
            "predicted_hero_eq_multi": (
                float(rec.predicted_hero_eq_multi)
                if rec.predicted_hero_eq_multi is not None else None
            ),
            "actual_hero_eq_street_multi": (
                float(result.actual_hero_eq_street_multi)
                if result.actual_hero_eq_street_multi is not None else None
            ),
            "actual_hero_eq_street_multi_shown": (
                float(result.actual_hero_eq_street_multi_shown)
                if result.actual_hero_eq_street_multi_shown is not None else None
            ),
            "active_player_ids": list(getattr(rec, "active_player_ids", []) or []),
            "active_player_count": len(getattr(rec, "active_player_ids", []) or []),
        }
