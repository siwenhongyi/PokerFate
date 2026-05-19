"""Extract Range V2 calibration rows from replay JSONL, in parallel.

This is the expensive stage of range calibration.  It replays historical hands
through the current bot, captures showdown calibration snapshots, and writes
one JSON row per (prediction snapshot, shown villain hand).

Two modes are supported:

* full   - bucket + hero-equity rows.  Uses ShowdownCalibrator, including MC
           actual-equity computation.  This is slower, but required for equity
           calibration.
* bucket - bucket-only rows.  Skips hero-equity MC and is much faster.  Use it
           when only fitting bucket distribution calibration.

By default runtime bucket calibration is disabled while extracting rows
(`PF_BUCKET_CALIBRATION=0`) so the rows represent the raw model.  That avoids
fitting a second calibration layer on top of already-calibrated output.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import traceback
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Iterable, TextIO

ROOT = Path(__file__).resolve().parent.parent


def _default_shards() -> int:
    return max(1, (os.cpu_count() or 4) - 2)


def _default_workers() -> int:
    # Full extraction is CPU-heavy because it runs Monte Carlo equity inside
    # each replay.  Keep one logical CPU for the OS / browser / poker client.
    return max(1, (os.cpu_count() or 4) - 1)


def _ts() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def _log(msg: str) -> None:
    print(f"[{_ts()}] {msg}", file=sys.stderr, flush=True)


def _sample_env(sample_scale: float) -> dict[str, str]:
    scale = max(0.02, float(sample_scale))
    defaults = {
        "PF_CAL_PRED_EQ_SAMPLES": 500,
        "PF_CAL_ACTUAL_EQ_PREFLOP_SAMPLES": 3000,
        "PF_CAL_ACTUAL_EQ_FLOP_SAMPLES": 1800,
        "PF_CAL_ACTUAL_EQ_TURN_SAMPLES": 1200,
        "PF_CAL_ACTUAL_EQ_RIVER_UNSHOWN_SAMPLES": 2000,
    }
    return {
        key: str(max(20, int(value * scale)))
        for key, value in defaults.items()
    }


def _load_replay_count(path: Path) -> int:
    with path.open("r", encoding="utf-8") as f:
        return sum(1 for line in f if line.strip())


def _ranges(n: int, shards: int) -> list[tuple[int, int]]:
    shards = max(1, min(shards, max(1, n)))
    chunk = n // shards
    rem = n % shards
    out: list[tuple[int, int]] = []
    pos = 0
    for i in range(shards):
        size = chunk + (1 if i < rem else 0)
        out.append((pos, pos + size))
        pos += size
    return out


def _session_ranges(path: Path, max_hands: int = 0) -> list[tuple[int, int, Any]]:
    """Return contiguous ranges that share the same replay session id."""
    ranges: list[tuple[int, int, Any]] = []
    start: int | None = None
    last_session: Any = None
    processed = 0
    last_line_idx = -1
    with path.open("r", encoding="utf-8") as f:
        for idx, line in enumerate(f):
            if max_hands > 0 and processed >= max_hands:
                break
            if not line.strip():
                continue
            try:
                session = json.loads(line).get("session", 0)
            except Exception:
                session = None
            if processed == 0:
                start = idx
                last_session = session
            elif session != last_session:
                assert start is not None
                ranges.append((start, idx, last_session))
                start = idx
                last_session = session
            processed += 1
            last_line_idx = idx
    if processed > 0:
        assert start is not None
        end = last_line_idx + 1
        ranges.append((start, end, last_session))
    return ranges


def _iter_replay_slice(path: Path, start: int, end: int) -> Iterable[tuple[int, dict[str, Any]]]:
    """Stream replay rows in [start, end) without loading the whole JSONL."""
    with path.open("r", encoding="utf-8") as f:
        for idx, line in enumerate(f):
            if idx < start:
                continue
            if idx >= end:
                break
            line = line.strip()
            if not line:
                continue
            yield idx, json.loads(line)


def _cards_str(cards: Iterable[Any] | None) -> list[str]:
    return [str(c) for c in (cards or [])]


def _malformed_board_reason(hand: dict[str, Any]) -> str:
    """Return why a replay hand has an impossible public-card sequence."""
    board: list[str] = []
    for event in hand.get("events", []) or []:
        if event.get("type") != "board":
            continue
        street = str(event.get("street") or "")
        cards = list(event.get("cards") or [])
        board.extend(str(c) for c in cards)
        if street == "flop" and len(cards) != 3:
            return f"flop_cards={len(cards)}"
        if street in {"turn", "river"} and len(cards) != 1:
            return f"{street}_cards={len(cards)}"
    if len(board) in {1, 2}:
        return f"partial_board={len(board)}"
    if len(board) > 5:
        return f"board_cards={len(board)}"
    return ""


def _row_from_result(result: Any, source: str) -> dict[str, Any]:
    rec = result.record
    return {
        "source": source,
        "hand": int(rec.hand_id),
        "street": rec.street,
        "player": rec.player_name,
        "player_id": rec.player_id,
        "trigger": rec.trigger,
        "board": _cards_str(rec.board),
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
            if getattr(result, "predicted_relation_eq", None) is not None else None
        ),
        "actual_relation": getattr(result, "actual_relation", "") or "",
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


def _task_signature(task: dict[str, Any]) -> dict[str, Any]:
    return {
        "replay": str(task["replay"]),
        "start": int(task["start"]),
        "end": int(task["end"]),
        "mode": task["mode"],
        "seed": int(task["seed"]),
        "equity_iterations": int(task["equity_iterations"]),
        "sample_scale": float(task["sample_scale"]),
        "bucket_calibration": str(task["bucket_calibration"]),
    }


def _meta_complete(task: dict[str, Any]) -> dict[str, Any] | None:
    part_path = Path(task["part_path"])
    meta_path = Path(task["meta_path"])
    if not part_path.exists() or not meta_path.exists():
        return None
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if meta.get("status") != "complete":
        return None
    if meta.get("signature") != _task_signature(task):
        return None
    return meta


def _write_meta(task: dict[str, Any], meta: dict[str, Any]) -> None:
    meta_path = Path(task["meta_path"])
    meta_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = meta_path.with_suffix(meta_path.suffix + ".tmp")
    tmp.write_text(json.dumps(meta, ensure_ascii=False, indent=2, sort_keys=True),
                   encoding="utf-8")
    os.replace(tmp, meta_path)


def _write_jsonl_rows(f: TextIO, rows: Iterable[dict[str, Any]]) -> int:
    count = 0
    for row in rows:
        f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
        count += 1
    return count


class FullRowsLogger:
    """ShowdownCalibrator logger that stores JSON-serializable rows."""

    def __init__(self, source: str) -> None:
        self.source = source
        self.rows: list[dict[str, Any]] = []

    def calibration_result(self, result: Any) -> None:
        self.rows.append(_row_from_result(result, self.source))


def _bucket_only_collector(source: str):
    """Build a lightweight ShowdownCalibrator-compatible collector.

    This intentionally avoids hero-equity MC.  It records predicted bucket
    distributions and actual showdown buckets only.
    """
    import numpy as np
    from pokerfate.calibration.showdown_calibration import ShowdownCalibrator
    from pokerfate.core.card import Card
    from pokerfate.strategy.range_v2 import hand_categorizer as hcat

    class BucketOnlyCollector:
        def __init__(self) -> None:
            self.source = source
            self._hand_id = 0
            self._hand_predictions: dict[int, list[dict[str, Any]]] = {}
            self._shown_cards: dict[int, list[Any]] = {}
            self.rows: list[dict[str, Any]] = []

        def start_hand(self, hand_id: int) -> None:
            self._hand_id = int(hand_id)
            self._hand_predictions = {}
            self._shown_cards = {}

        def record_prediction(
            self,
            player_id: int,
            player_name: str,
            street: str,
            board: list[Any],
            weights: np.ndarray,
            hero_cards=None,
            trigger: str = "",
            active_weights=None,
        ) -> None:
            total = float(weights.sum())
            if total <= 1e-15:
                return
            bucket_dist = ShowdownCalibrator._compute_bucket_dist(weights / total, board)
            threshold = (1.0 / 1326) * 0.1
            range_pct = float(((weights / total) > threshold).sum()) / 1326
            self._hand_predictions.setdefault(player_id, []).append({
                "source": self.source,
                "hand": self._hand_id,
                "street": street,
                "player_id": player_id,
                "player": player_name,
                "trigger": trigger,
                "board": [str(c) for c in board],
                "range_pct": range_pct,
                "bucket_dist": bucket_dist,
            })

        def record_actual(
            self,
            player_id: int,
            actual_cards: list[Any],
            final_board: list[Any],
            hero_cards=None,
        ) -> None:
            self._shown_cards[player_id] = list(actual_cards[:2])

        def emit_records_for(
            self,
            player_id: int,
            hero_cards=None,
            final_board=None,
        ) -> list[Any]:
            actual_cards = self._shown_cards.get(player_id)
            if not actual_cards:
                return []
            for rec in self._hand_predictions.get(player_id, []):
                board = [Card.from_str(s) for s in rec["board"]]
                actual_bucket = hcat.categorize_cards(actual_cards, board if board else [])
                bucket_dist = rec["bucket_dist"]
                self.rows.append({
                    **rec,
                    "actual_cards": [str(c) for c in actual_cards],
                    "actual_bucket": actual_bucket,
                    "range_pct": float(rec.get("range_pct", 0.0) or 0.0),
                    "predicted_bucket_prob": float(bucket_dist.get(actual_bucket, 0.0)),
                    "hero_cards": [],
                    "hero_bucket": "",
                    "hero_made_subtype": "",
                    "hero_hand_rank": "",
                    "board_texture": "",
                    "villain_vs_hero_dist": {},
                    "predicted_relation_eq": None,
                    "actual_relation": "",
                    "predicted_hero_eq": None,
                    "actual_hero_eq_street": None,
                    "predicted_hero_eq_multi": None,
                    "actual_hero_eq_street_multi": None,
                    "actual_hero_eq_street_multi_shown": None,
                    "active_player_ids": [],
                    "active_player_count": 0,
                })
            return []

        def finalize_hand_calibration(self, hero_cards=None, final_board=None) -> list[Any]:
            for pid in list(self._shown_cards):
                self.emit_records_for(pid, hero_cards=hero_cards, final_board=final_board)
            return []

    return BucketOnlyCollector()


def _run_task(task: dict[str, Any]) -> dict[str, Any]:
    """Worker entry point.  Imports PokerFate after env is set."""
    t0 = time.time()
    replay_path = Path(task["replay"])
    start = int(task["start"])
    end = int(task["end"])
    task_id = int(task["task_id"])
    mode = task["mode"]
    seed = int(task["seed"])
    equity_iterations = int(task["equity_iterations"])
    sample_scale = float(task["sample_scale"])
    bucket_calibration = str(task["bucket_calibration"])
    progress_every = int(task["progress_every"])
    resume = bool(task.get("resume", True))
    part_path = Path(task["part_path"])
    part_tmp_path = part_path.with_suffix(part_path.suffix + ".tmp")

    complete_meta = _meta_complete(task) if resume else None
    if complete_meta is not None:
        return {
            "task_id": task_id,
            "replay": str(replay_path),
            "start": start,
            "end": end,
            "played": int(complete_meta.get("played", 0)),
            "rows": int(complete_meta.get("rows", 0)),
            "skipped_no_hero": int(complete_meta.get("skipped_no_hero", 0)),
            "skipped_malformed_board": int(complete_meta.get("skipped_malformed_board", 0)),
            "malformed_examples": complete_meta.get("malformed_examples", []) or [],
            "elapsed_s": 0.0,
            "skipped_complete": True,
        }

    os.environ.setdefault("PYTEST_CURRENT_TEST", "scripts/extract_range_calibration_rows_parallel.py")
    os.environ.update(_sample_env(sample_scale))
    if bucket_calibration == "raw":
        os.environ["PF_BUCKET_CALIBRATION"] = "0"
    elif bucket_calibration == "current":
        os.environ["PF_BUCKET_CALIBRATION"] = "1"

    try:
        from pokerfate.api import PokerFateAPI
        from scripts.hero_name import load_hero_name
        from scripts.replay_and_compare import _hero_id, _replay_hand
    except Exception as exc:
        return {"error": f"import failed: {type(exc).__name__}: {exc}"}

    try:
        hero_name = load_hero_name()
    except Exception as exc:
        return {"error": f"hero name failed: {type(exc).__name__}: {exc}"}

    last_session = None
    last_big_blind = None
    api = None
    logger: FullRowsLogger | None = None
    bucket_collector = None
    played = 0
    skipped_no_hero = 0
    skipped_malformed_board = 0
    malformed_examples: list[dict[str, Any]] = []
    row_count = 0

    part_path.parent.mkdir(parents=True, exist_ok=True)
    _write_meta(task, {
        "status": "running",
        "signature": _task_signature(task),
        "started_at": _ts(),
        "part_path": str(part_path),
    })

    try:
        with part_tmp_path.open("w", encoding="utf-8") as part_file:
            for line_idx, hand in _iter_replay_slice(replay_path, start, end):
                malformed_reason = _malformed_board_reason(hand)
                if malformed_reason:
                    skipped_malformed_board += 1
                    if len(malformed_examples) < 5:
                        malformed_examples.append({
                            "hand": hand.get("hand"),
                            "session": hand.get("session"),
                            "line": line_idx + 1,
                            "reason": malformed_reason,
                        })
                    continue

                hero_id = _hero_id(hand.get("players", []), hero_name)
                if hero_id is None:
                    skipped_no_hero += 1
                    continue

                session = hand.get("session", 0)
                table_bb = float(hand.get("big_blind") or 2.0)
                needs_new_api = (
                    api is None
                    or session != last_session
                    or hero_id != getattr(api, "my_player_id", None)
                    or table_bb != last_big_blind
                )
                if needs_new_api:
                    api = PokerFateAPI(
                        my_player_id=hero_id,
                        big_blind=table_bb,
                        small_blind=table_bb / 2.0,
                        autosave_path=None,
                        log_file=None,
                        verbose=False,
                        equity_iterations=equity_iterations,
                        enable_showdown_calibration=True,
                        decision_seed=seed + line_idx + 1,
                    )
                    api._log._console = False
                    if mode == "full":
                        logger = FullRowsLogger(str(replay_path))
                        if api._calibrator is not None:
                            api._calibrator._logger = logger
                    else:
                        bucket_collector = _bucket_only_collector(str(replay_path))
                        api._calibrator = bucket_collector
                    last_session = session
                    last_big_blind = table_bb

                _replay_hand(api, hand, hero_id)
                played += 1
                if mode == "full" and logger is not None and logger.rows:
                    row_count += _write_jsonl_rows(part_file, logger.rows)
                    logger.rows = []
                elif mode == "bucket" and bucket_collector is not None and bucket_collector.rows:
                    row_count += _write_jsonl_rows(part_file, bucket_collector.rows)
                    bucket_collector.rows = []

                if progress_every > 0 and played % progress_every == 0:
                    _log(
                        f"[worker {task_id}] {replay_path.name} "
                        f"{line_idx + 1}/{end} rows={row_count} "
                        f"elapsed={time.time() - t0:.0f}s"
                    )
    except Exception as exc:
        return {
            "error": f"replay failed: {type(exc).__name__}: {exc}",
            "traceback": traceback.format_exc(),
            "played": played,
            "rows": row_count,
            "skipped_malformed_board": skipped_malformed_board,
            "malformed_examples": malformed_examples,
        }

    os.replace(part_tmp_path, part_path)
    _write_meta(task, {
        "status": "complete",
        "signature": _task_signature(task),
        "started_at": _ts(),
        "completed_at": _ts(),
        "part_path": str(part_path),
        "played": played,
        "rows": row_count,
        "skipped_no_hero": skipped_no_hero,
        "skipped_malformed_board": skipped_malformed_board,
        "malformed_examples": malformed_examples[:10],
        "elapsed_s": round(time.time() - t0, 2),
    })

    return {
        "task_id": task_id,
        "replay": str(replay_path),
        "start": start,
        "end": end,
        "played": played,
        "skipped_no_hero": skipped_no_hero,
        "skipped_malformed_board": skipped_malformed_board,
        "malformed_examples": malformed_examples,
        "rows": row_count,
        "elapsed_s": round(time.time() - t0, 2),
    }


def _parts_dir_for(out: Path, explicit: Path | None) -> Path:
    if explicit is not None:
        return explicit
    return out.with_name(out.name + ".parts")


def _part_paths(
    parts_dir: Path,
    task_id: int,
    replay_path: Path,
    start: int,
    end: int,
) -> tuple[Path, Path]:
    safe_stem = "".join(
        c if c.isalnum() or c in ("-", "_") else "_"
        for c in replay_path.stem
    )
    base = f"task_{task_id:04d}_{safe_stem}_{start}_{end}"
    return parts_dir / f"{base}.jsonl", parts_dir / f"{base}.meta.json"


def _combine_parts(tasks: list[dict[str, Any]], out: Path) -> int:
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(out.suffix + ".tmp")
    count = 0
    with tmp.open("w", encoding="utf-8") as dst:
        for task in sorted(tasks, key=lambda t: int(t["task_id"])):
            meta = _meta_complete(task)
            if meta is None:
                raise RuntimeError(f"part not complete: task={task['task_id']}")
            with Path(task["part_path"]).open("r", encoding="utf-8") as src:
                for line in src:
                    if line.strip():
                        dst.write(line)
                        count += 1
    os.replace(tmp, out)
    return count


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--replay", type=Path, action="append", required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--mode", choices=("full", "bucket"), default="full")
    ap.add_argument("--bucket-calibration", choices=("raw", "current"), default="raw")
    ap.add_argument("--max-hands", type=int, default=0, help="cap hands per replay, 0 = all")
    ap.add_argument("--task-split", choices=("session", "shard"), default="session",
                    help="session keeps opponent-model continuity and gives resumable parts")
    ap.add_argument("--parts-dir", type=Path,
                    help="directory for per-task JSONL/meta files; default = OUT.parts")
    ap.add_argument("--no-resume", action="store_true",
                    help="rerun tasks even if complete part files already exist")
    ap.add_argument("--combine-only", action="store_true",
                    help="only merge completed parts into --out")
    ap.add_argument("--shards", type=int, default=_default_shards())
    ap.add_argument("--workers", type=int, default=0, help="default = min(cpu-1, tasks)")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--equity-iterations", type=int, default=60)
    ap.add_argument("--sample-scale", type=float, default=0.20,
                    help="full mode MC scale; 0.20 is a good sweep speed default")
    ap.add_argument("--progress-every", type=int, default=0)
    args = ap.parse_args()

    tasks: list[dict[str, Any]] = []
    task_id = 0
    parts_dir = _parts_dir_for(args.out, args.parts_dir)
    for replay_path in args.replay:
        if args.task_split == "session":
            ranges = [(start, end) for start, end, _session in _session_ranges(
                replay_path, args.max_hands,
            )]
        else:
            n = _load_replay_count(replay_path)
            if args.max_hands > 0:
                n = min(n, args.max_hands)
            ranges = _ranges(n, args.shards)

        for start, end in ranges:
            part_path, meta_path = _part_paths(parts_dir, task_id, replay_path, start, end)
            tasks.append({
                "task_id": task_id,
                "replay": str(replay_path),
                "start": start,
                "end": end,
                "part_path": str(part_path),
                "meta_path": str(meta_path),
                "mode": args.mode,
                "seed": args.seed + task_id * 1009,
                "equity_iterations": args.equity_iterations,
                "sample_scale": args.sample_scale,
                "bucket_calibration": args.bucket_calibration,
                "progress_every": args.progress_every,
                "resume": not args.no_resume,
            })
            task_id += 1

    workers = args.workers if args.workers > 0 else max(1, min(_default_workers(), len(tasks)))
    _log(
        f"start tasks={len(tasks)} workers={workers} split={args.task_split} "
        f"mode={args.mode} bucket_calibration={args.bucket_calibration} "
        f"out={args.out} parts={parts_dir}"
    )
    if args.combine_only:
        count = _combine_parts(tasks, args.out)
        _log(f"combined rows={count} out={args.out}")
        print(json.dumps({
            "rows": count,
            "errors": 0,
            "elapsed_s": 0.0,
            "mode": args.mode,
            "bucket_calibration": args.bucket_calibration,
            "out": str(args.out),
            "parts_dir": str(parts_dir),
            "combined_only": True,
        }, ensure_ascii=False, indent=2))
        return

    t0 = time.time()
    errors: list[dict[str, Any]] = []
    completed = 0
    skipped_complete = 0
    total_rows = 0
    skipped_malformed_board = 0
    malformed_examples: list[dict[str, Any]] = []
    if workers == 1:
        iterator = ((idx, task, _run_task(task)) for idx, task in enumerate(tasks, 1))
        for done, task, result in iterator:
            if result.get("error"):
                errors.append(result)
                print(
                    f"[{_ts()}] [{done}/{len(tasks)}] task={task['task_id']} ERROR "
                    f"{result['error'][:250]}",
                    file=sys.stderr, flush=True,
                )
                continue
            skipped_malformed_board += int(result.get("skipped_malformed_board") or 0)
            malformed_examples.extend(result.get("malformed_examples", []) or [])
            rows_count = int(result.get("rows", 0) or 0)
            total_rows += rows_count
            completed += 1
            skipped_complete += 1 if result.get("skipped_complete") else 0
            _log(
                f"[{done}/{len(tasks)}] task={result['task_id']} "
                f"hands={result['played']} rows={rows_count} "
                f"elapsed={result['elapsed_s']}s"
            )
    else:
        with ProcessPoolExecutor(max_workers=workers) as ex:
            futures = {ex.submit(_run_task, task): task for task in tasks}
            for done, fut in enumerate(as_completed(futures), 1):
                task = futures[fut]
                result = fut.result()
                if result.get("error"):
                    errors.append(result)
                    print(
                        f"[{_ts()}] [{done}/{len(tasks)}] task={task['task_id']} ERROR "
                        f"{result['error'][:250]}",
                        file=sys.stderr, flush=True,
                    )
                    continue
                skipped_malformed_board += int(result.get("skipped_malformed_board") or 0)
                malformed_examples.extend(result.get("malformed_examples", []) or [])
                rows_count = int(result.get("rows", 0) or 0)
                total_rows += rows_count
                completed += 1
                skipped_complete += 1 if result.get("skipped_complete") else 0
                _log(
                    f"[{done}/{len(tasks)}] task={result['task_id']} "
                    f"hands={result['played']} rows={rows_count} "
                    f"elapsed={result['elapsed_s']}s"
                )

    count = _combine_parts(tasks, args.out) if not errors else 0

    summary = {
        "rows": count,
        "errors": len(errors),
        "tasks": len(tasks),
        "completed_tasks": completed,
        "skipped_complete_tasks": skipped_complete,
        "task_rows_seen": total_rows,
        "elapsed_s": round(time.time() - t0, 2),
        "mode": args.mode,
        "bucket_calibration": args.bucket_calibration,
        "out": str(args.out),
        "parts_dir": str(parts_dir),
        "skipped_malformed_board": skipped_malformed_board,
    }
    if malformed_examples:
        summary["malformed_examples"] = malformed_examples[:10]
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if errors:
        err_path = args.out.with_suffix(args.out.suffix + ".errors.json")
        err_path.write_text(json.dumps(errors, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"errors written to {err_path}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
