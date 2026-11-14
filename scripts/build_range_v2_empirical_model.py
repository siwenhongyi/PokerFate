"""Build Range V2 empirical priors from local opponent stats and calibration rows.

The output is an optional runtime model consumed by
``pokerfate.strategy.range_v2.empirical_model``.  Missing output means callers
fall back to the old static logic.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pokerfate.strategy.range_v2.empirical_model import (
    CAT_ORDER,
    MODEL_DIR,
    build_numeric_profile_payload,
    empirical_model_path,
)

ACTION_LABELS = ("call", "check", "bet", "raise_over", "fold")
# A bucket needs this many showdown rows on a street before its action rate
# replaces the GTO row (per-bucket noise guard; 2026-11-09).
MIN_CAT_DENOM = 30
BUCKET_TRANSLATE = {
    "坚果": "nuts",
    "强": "strong",
    "中": "medium",
    "听牌": "draw",
    "弱听": "weak_draw",
    "空气": "air",
}
CONSOLE_CAL_RE = re.compile(
    r"⚖\s+(preflop|flop|turn|river)\s+.+?\s+"
    r"(reset|board:\w+|action:\w+)\s+实际桶=([^\(\s]+)"
)


def _iter_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except Exception:
                continue
            if isinstance(row, dict):
                yield row


def _load_rows(
    paths: Iterable[Path],
    *,
    since_ts: float = 0.0,
    until_ts: float = 0.0,
) -> list[dict[str, Any]]:
    """Load calibration rows, optionally restricted by ``recorded_at`` (epoch
    seconds). The bounds make temporal hold-out builds possible: fit on rows
    before a cut, score on hands after it."""
    rows: list[dict[str, Any]] = []
    for path in paths:
        if not path.exists():
            continue
        for row in _iter_jsonl(path):
            if since_ts or until_ts:
                try:
                    at = float(row.get("recorded_at") or 0.0)
                except (TypeError, ValueError):
                    at = 0.0
                if since_ts and at < since_ts:
                    continue
                if until_ts and at >= until_ts:
                    continue
            rows.append(row)
    return rows


def _rows_from_console(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        m = CONSOLE_CAL_RE.search(raw)
        if not m:
            continue
        bucket = BUCKET_TRANSLATE.get(m.group(3), m.group(3))
        if bucket not in CAT_ORDER:
            continue
        rows.append({
            "source": str(path),
            "street": m.group(1),
            "trigger": m.group(2),
            "actual_bucket": bucket,
            "position": "",
            "bet_size_bucket": "none",
            "is_raise_over": m.group(2) == "action:raise_over",
            "player_uid": "",
            "preflop_action_type": "",
            "_console": True,
        })
    return rows


def _load_opponent_stats(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    out: dict[str, dict[str, Any]] = {}
    for pid, entry in (data.get("players") or {}).items():
        stats = entry.get("stats") if isinstance(entry, dict) else None
        if isinstance(stats, dict):
            out[str(pid)] = stats
    return out


def _rate(stats: dict[str, Any], num: str, den: str) -> tuple[float, float]:
    n = float(stats.get(num, 0) or 0)
    d = float(stats.get(den, 0) or 0)
    return n, d


def _population_rates(opponents: dict[str, dict[str, Any]]) -> dict[str, dict[str, float]]:
    specs = {
        "vpip": ("vpip_count", "hands_seen"),
        "pfr": ("pfr_count", "hands_seen"),
        "three_bet": ("three_bet_count", "three_bet_opportunities"),
        "fold_to_3bet": ("fold_to_3bet_count", "fold_to_3bet_opps"),
        "fold_to_cbet": ("fold_to_cbet_count", "fold_to_cbet_opps"),
        "wtsd": ("showdown_count", "flop_seen_count"),
        "wmsd": ("showdown_win_count", "showdown_count"),
        "river_fold_rate": ("river_facing_bet_fold_count", "river_facing_bet_opps"),
        "bluff_win_rate": ("bluff_win_count", "bet_win_count"),
    }
    out: dict[str, dict[str, float]] = {}
    for name, (num, den) in specs.items():
        n = d = 0.0
        for stats in opponents.values():
            a, b = _rate(stats, num, den)
            n += a
            d += b
        if d > 0:
            out[name] = _rate_record(n, d)

    derived = {
        "flop_afq": ("flop_bet_count", ("flop_bet_count", "flop_passive_count")),
        "turn_afq": ("turn_bet_count", ("turn_bet_count", "turn_passive_count")),
        "river_afq": ("river_bet_count", ("river_bet_count", "river_call_count", "river_check_count")),
        "river_bet_frequency": ("river_bet_count", ("river_bet_count", "river_check_count")),
    }
    for name, (num_field, den_fields) in derived.items():
        n = d = 0.0
        for stats in opponents.values():
            n += float(stats.get(num_field, 0) or 0)
            d += sum(float(stats.get(field, 0) or 0) for field in den_fields)
        if d > 0:
            out[name] = _rate_record(n, d)
    return out


def _rate_record(success: float, trials: float) -> dict[str, float]:
    mean = success / trials if trials > 0 else 0.0
    return {
        "mean": round(mean, 6),
        "success": int(success),
        "trials": int(trials),
        "prior_strength": round(min(80.0, max(12.0, math.sqrt(trials))), 3),
    }


def _action_from_trigger(trigger: str) -> str:
    label = str(trigger or "")
    if not label.startswith("action:"):
        return ""
    label = label.split(":", 1)[1]
    if label == "fold_other":
        return ""
    return label if label in ACTION_LABELS else ""


def _context_keys(row: dict[str, Any]) -> list[str]:
    street = str(row.get("street") or "").lower()
    size = str(row.get("bet_size_bucket") or "none")
    rr = "1" if bool(row.get("is_raise_over")) else "0"
    out = []
    for size_key in (size, "*"):
        for rr_key in (rr, "*"):
            out.append(f"{street}|{size_key}|{rr_key}")
    return out


def _build_action_likelihoods(
    rows: list[dict[str, Any]],
    *,
    min_action_n: int,
    prior_weight: float,
    max_blend: float = 0.055,
) -> dict[str, dict[str, Any]]:
    counts: dict[str, dict[str, Counter[str]]] = defaultdict(lambda: defaultdict(Counter))
    for row in rows:
        cat = str(row.get("actual_bucket") or "")
        if cat not in CAT_ORDER:
            continue
        action = _action_from_trigger(str(row.get("trigger") or ""))
        if not action:
            continue
        for ctx_key in _context_keys(row):
            counts[ctx_key][cat][action] += 1

    table: dict[str, dict[str, Any]] = {}
    for ctx_key, cat_actions in counts.items():
        total_ctx = sum(sum(c.values()) for c in cat_actions.values())
        if total_ctx < min_action_n:
            continue
        street, size, rr = ctx_key.split("|")
        # P(action | cat) needs "all actions this bucket took on this street"
        # as the denominator. Bet size and raise-over are attributes of the
        # action itself, so a size- or rr-specific context only contains rows
        # of that action and the old per-context denominator gave
        # P(action | cat) ≈ 1 for every bucket (July model: river|bet|pot →
        # 0.98–1.0 for all cats). Always divide by the street-wide totals.
        # Size keys are then rescaled by N(action)/N(action, size) so they
        # keep the scale of P(action | cat) while carrying the size-specific
        # bucket composition — the tracker mixes them with the GTO row, which
        # is on the P(action | cat) scale.
        denom_actions = counts.get(f"{street}|*|*", cat_actions)
        base_actions = counts.get(f"{street}|*|{rr}", cat_actions) if size != "*" else cat_actions
        for action in ACTION_LABELS:
            n_action = sum(c.get(action, 0) for c in cat_actions.values())
            if n_action < min_action_n:
                continue
            scale = 1.0
            if size != "*":
                n_base = sum(c.get(action, 0) for c in base_actions.values())
                scale = (n_base / n_action) if n_action > 0 else 1.0
            cat_probs: dict[str, float] = {}
            for cat in CAT_ORDER:
                denom = sum(denom_actions.get(cat, {}).values())
                if denom < MIN_CAT_DENOM:
                    continue  # too few showdowns of this bucket: leave the GTO row in place
                cat_probs[cat] = round(min(0.99, cat_actions[cat].get(action, 0) / denom * scale), 6)
            if not cat_probs:
                continue
            # Shrinkage toward the GTO table: blend = min(cap, n / (n + prior_weight)).
            # Default cap keeps the historical 2.5–5.5% weight (the 2026-11-09
            # hold-out showed that lifting it to ~0.9 on top of the tracker
            # fixes over-corrects: river strength bias +0.016, Brier 0.1321 vs
            # 0.1304). --max-blend raises it for experiments.
            specificity = sum(1 for part in (size, rr) if part != "*")
            cap = min(max_blend, max_blend - 0.03 + specificity * 0.015) if max_blend <= 0.1 else max_blend
            blend = min(cap, n_action / (n_action + prior_weight))
            table[f"{street}|{action}|{size}|{rr}|*"] = {
                "cat_probs": cat_probs,
                "n": int(n_action),
                "ctx_n": int(total_ctx),
                "blend": round(blend, 4),
            }
    return table


def _build_preflop_priors(
    rows: list[dict[str, Any]],
    *,
    min_n: int,
) -> dict[str, dict[str, Any]]:
    counts: dict[str, Counter[str]] = defaultdict(Counter)
    for row in rows:
        if str(row.get("street") or "") != "preflop":
            continue
        if str(row.get("trigger") or "") != "reset":
            continue
        cat = str(row.get("actual_bucket") or "")
        if cat not in CAT_ORDER:
            continue
        pos = str(row.get("position") or "*")
        for key in (f"{pos}|*", "*|*"):
            counts[key][cat] += 1

    out: dict[str, dict[str, Any]] = {}
    for key, counter in counts.items():
        n = sum(counter.values())
        if n < min_n:
            continue
        dist = {cat: round(counter.get(cat, 0) / n, 6) for cat in CAT_ORDER}
        out[key] = {
            "dist": dist,
            "n": int(n),
            "blend": round(min(0.10, n / (n + 1000.0)), 4),
        }
    return out


def _build_player_action_counts(
    rows: list[dict[str, Any]],
    opponents: dict[str, dict[str, Any]],
) -> dict[str, dict[str, dict[str, Counter[str]]]]:
    counts: dict[str, dict[str, dict[str, Counter[str]]]] = defaultdict(
        lambda: defaultdict(lambda: defaultdict(Counter))
    )
    known = set(opponents)
    for row in rows:
        uid = str(row.get("player_uid") or "")
        if uid not in known:
            continue
        cat = str(row.get("actual_bucket") or "")
        if cat not in CAT_ORDER:
            continue
        action = _action_from_trigger(str(row.get("trigger") or ""))
        if not action:
            continue
        for ctx_key in _context_keys(row):
            counts[uid][ctx_key][cat][action] += 1
    return counts


def _build_player_preflop_counts(
    rows: list[dict[str, Any]],
    opponents: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Counter[str]]]:
    counts: dict[str, dict[str, Counter[str]]] = defaultdict(lambda: defaultdict(Counter))
    known = set(opponents)
    for row in rows:
        uid = str(row.get("player_uid") or "")
        if uid not in known:
            continue
        if str(row.get("street") or "") != "preflop":
            continue
        if str(row.get("trigger") or "") != "reset":
            continue
        cat = str(row.get("actual_bucket") or "")
        if cat not in CAT_ORDER:
            continue
        pos = str(row.get("position") or "*")
        counts[uid][pos][cat] += 1
        counts[uid]["*"][cat] += 1
    return counts


DEFAULT_TRAIN_ROWS = ROOT / "data" / "runtime_calibration" / "train.rows.jsonl"
DEFAULT_OPPONENTS = MODEL_DIR / "opponents.json"


def _build_model(
    *,
    row_paths: list[Path],
    console_logs: list[Path],
    opponents_path: Path,
    out_path: Path,
    min_action_n: int,
    min_prior_n: int,
    action_prior_weight: float,
    since_ts: float = 0.0,
    until_ts: float = 0.0,
    max_blend: float = 0.055,
    exclude_robots: bool = True,
    robot_registry_path: Path | None = None,
) -> dict[str, Any]:
    rows = _load_rows(row_paths, since_ts=since_ts, until_ts=until_ts)
    console_rows = []
    for path in console_logs:
        console_rows.extend(_rows_from_console(path))
    opponents = _load_opponent_stats(opponents_path)
    robots_dropped = {"excluded": bool(exclude_robots), "rows": 0, "opponents": 0}
    if exclude_robots:
        # House robots act without regard to their cards: a pool table or a neighbour prior
        # built from them describes nobody we want to model.
        from pokerfate.core.robots import RobotRegistry
        from scripts.range_calibration_meta import drop_robot_rows

        registry = RobotRegistry(robot_registry_path, autosave=False)
        rows, robots_dropped["rows"] = drop_robot_rows(rows, registry)
        human_opponents = {uid: st for uid, st in opponents.items() if not registry.is_robot(uid)}
        robots_dropped["opponents"] = len(opponents) - len(human_opponents)
        robots_dropped["registry"] = registry.counts()
        opponents = human_opponents
    all_rows = rows + console_rows
    player_action_counts = _build_player_action_counts(rows, opponents)
    player_preflop_counts = _build_player_preflop_counts(rows, opponents)
    numeric_profile_priors = build_numeric_profile_payload(
        opponents,
        player_action_counts,
        player_preflop_counts,
        action_prior_weight=action_prior_weight,
    )

    model = {
        "schema": "range_v2_empirical_model_v2",
        "generated_at": int(time.time()),
        "sources": {
            "rows": [str(p) for p in row_paths],
            "since_ts": since_ts or None,
            "until_ts": until_ts or None,
            "console_logs": [str(p) for p in console_logs],
            "opponents": str(opponents_path),
            "structured_rows": len(rows),
            "console_rows": len(console_rows),
            "opponents_players": len(opponents),
            "robots_dropped": robots_dropped,
            "numeric_action_players": len(player_action_counts),
            "numeric_preflop_players": len(player_preflop_counts),
        },
        "population_rates": _population_rates(opponents),
        "numeric_profile_priors": numeric_profile_priors,
        "preflop_bucket_priors": _build_preflop_priors(all_rows, min_n=min_prior_n),
        "action_likelihoods": _build_action_likelihoods(
            all_rows, min_action_n=min_action_n,
            prior_weight=action_prior_weight, max_blend=max_blend,
        ),
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = out_path.with_suffix(out_path.suffix + ".tmp")
    tmp.write_text(
        json.dumps(model, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    tmp.replace(out_path)
    return {
        "out": str(out_path),
        "rows": len(rows),
        "console_rows": len(console_rows),
        "opponents": len(opponents),
        "robots_dropped": robots_dropped,
        "population_rates": model["population_rates"],
        "numeric_profile_priors": numeric_profile_priors.get("counts", {}),
        "preflop_prior_keys": len(model["preflop_bucket_priors"]),
        "action_likelihood_keys": len(model["action_likelihoods"]),
    }


def _parse_ts(text: str) -> float:
    """ISO 8601 (assumed UTC when naive) or epoch seconds → epoch seconds; '' → 0."""
    raw = str(text or "").strip()
    if not raw:
        return 0.0
    try:
        return float(raw)
    except ValueError:
        pass
    from datetime import datetime, timezone
    dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.timestamp()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--row", type=Path, action="append", default=[],
                    help=f"structured calibration JSONL; default {DEFAULT_TRAIN_ROWS}")
    ap.add_argument("--console-log", type=Path, action="append", default=[],
                    help="optional console log; only global calibration lines are used")
    ap.add_argument("--opponents", type=Path, default=DEFAULT_OPPONENTS,
                    help=f"opponent model JSON (uid keyed); default {DEFAULT_OPPONENTS}")
    ap.add_argument("--out", type=Path, default=None,
                    help=f"output path; default {empirical_model_path()}")
    ap.add_argument("--min-action-n", type=int, default=12)
    ap.add_argument("--min-prior-n", type=int, default=20)
    ap.add_argument("--action-prior-weight", type=float, default=3000.0,
                    help="GTO-prior pseudo-count behind the pool action table: "
                         "blend = min(max_blend, n / (n + weight))")
    ap.add_argument("--max-blend", type=float, default=0.055,
                    help="cap on the pool table's blend weight (default keeps the "
                         "historical 2.5–5.5%%; 0.9 was tested 2026-11-09 and "
                         "over-corrected once the tracker's board floor and static "
                         "bucket calibration were removed)")
    ap.add_argument("--since", default="",
                    help="only rows recorded at/after this UTC time (ISO 8601 or epoch)")
    ap.add_argument("--until", default="",
                    help="only rows recorded before this UTC time (ISO 8601 or epoch); "
                         "use for temporal hold-out builds")
    ap.add_argument("--keep-robots", action="store_true",
                    help="do NOT drop house robots from rows / opponent stats (default: drop them)")
    ap.add_argument("--robot-registry", type=Path, default=None,
                    help="robot registry file (default pokerfate/data/local_models/robots.json)")
    args = ap.parse_args()

    summary = _build_model(
        row_paths=args.row or [DEFAULT_TRAIN_ROWS],
        console_logs=args.console_log,
        opponents_path=args.opponents,
        out_path=args.out or empirical_model_path(),
        min_action_n=args.min_action_n,
        min_prior_n=args.min_prior_n,
        action_prior_weight=args.action_prior_weight,
        since_ts=_parse_ts(args.since),
        until_ts=_parse_ts(args.until),
        max_blend=args.max_blend,
        exclude_robots=not args.keep_robots,
        robot_registry_path=args.robot_registry,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
