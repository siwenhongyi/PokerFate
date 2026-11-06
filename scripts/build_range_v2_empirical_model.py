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
    SUPPORTED_BB_KEYS,
    bb_key,
    build_numeric_profile_payload,
    MODEL_KEY,
    empirical_model_path,
)

ACTION_LABELS = ("call", "check", "bet", "raise_over", "fold")
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
HAND_HEADER_RE = re.compile(r"第\s+\d+\s+手\s+(.*)")
PLAYER_BB_RE = re.compile(r"(.+?)\s+(-?\d+(?:\.\d+)?)bb(?:\s+\[[^\]]*\])?$")
FINAL_STACK_RE = re.compile(r"(.+?)\s+(-?\d+(?:\.\d+)?)$")


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


def _row_bb_key(row: dict[str, Any], path: Path | None = None) -> str:
    raw = str(row.get("bb_bucket") or "")
    if raw in SUPPORTED_BB_KEYS:
        return raw
    path = path or Path(str(row.get("source") or ""))
    for part in path.parts:
        if part in SUPPORTED_BB_KEYS:
            return part
    raw_bb = row.get("bb")
    if raw_bb is not None:
        return bb_key(raw_bb)
    return "bb_10k"


def _load_rows(paths: Iterable[Path], target_bb: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in paths:
        if path.exists():
            for row in _iter_jsonl(path):
                if _row_bb_key(row, path) == target_bb:
                    rows.append(row)
    return rows


def _split_console_players(text: str) -> list[str]:
    return [part.strip() for part in re.split(r"\s{2,}", text.strip()) if part.strip()]


def _parse_console_hand_stacks(line: str) -> dict[str, float]:
    m = HAND_HEADER_RE.search(line)
    if not m:
        return {}
    out: dict[str, float] = {}
    for part in _split_console_players(m.group(1)):
        mm = PLAYER_BB_RE.match(part)
        if not mm:
            continue
        try:
            out[mm.group(1).strip()] = float(mm.group(2))
        except Exception:
            continue
    return out


def _median(values: list[float]) -> float:
    values = sorted(values)
    n = len(values)
    if n == 0:
        return 0.0
    mid = n // 2
    if n % 2:
        return values[mid]
    return (values[mid - 1] + values[mid]) / 2.0


def _infer_console_bb_from_final(line: str, hand_stacks_bb: dict[str, float]) -> str:
    if "│" not in line or not hand_stacks_bb:
        return ""
    tail = line.split("│", 1)[1]
    ratios: list[float] = []
    for part in _split_console_players(tail):
        mm = FINAL_STACK_RE.match(part)
        if not mm:
            continue
        name = mm.group(1).strip()
        try:
            chips = float(mm.group(2))
            stack_bb = float(hand_stacks_bb.get(name, 0.0) or 0.0)
        except Exception:
            continue
        if chips <= 0 or stack_bb <= 0:
            continue
        ratios.append(chips / stack_bb)
    if not ratios:
        return ""
    candidates = {"bb_1k": 1000.0, "bb_10k": 10000.0, "bb_50k": 50000.0}

    def score(candidate: float) -> float:
        return _median([abs((ratio / candidate) - 1.0) for ratio in ratios])

    best_key, best_value = min(candidates.items(), key=lambda item: score(item[1]))
    return best_key if score(best_value) <= 0.60 else ""


def _rows_from_console(path: Path, target_bb: str, fallback_bb: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    hand_stacks_bb: dict[str, float] = {}
    current_bb = fallback_bb
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        hand_stacks = _parse_console_hand_stacks(raw)
        if hand_stacks:
            hand_stacks_bb = hand_stacks
            continue
        inferred = _infer_console_bb_from_final(raw, hand_stacks_bb)
        if inferred:
            current_bb = inferred
            continue
        m = CONSOLE_CAL_RE.search(raw)
        if not m:
            continue
        if current_bb != target_bb:
            continue
        bucket = BUCKET_TRANSLATE.get(m.group(3), m.group(3))
        if bucket not in CAT_ORDER:
            continue
        rows.append({
            "source": str(path),
            "bb_bucket": current_bb,
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
        specificity = sum(1 for part in (size, rr) if part != "*")
        cap = min(0.055, 0.025 + specificity * 0.015)
        for action in ACTION_LABELS:
            n_action = sum(c.get(action, 0) for c in cat_actions.values())
            if n_action < min_action_n:
                continue
            cat_probs: dict[str, float] = {}
            for cat in CAT_ORDER:
                denom = sum(cat_actions.get(cat, {}).values())
                if denom <= 0:
                    continue
                cat_probs[cat] = round(cat_actions[cat].get(action, 0) / denom, 6)
            if not cat_probs:
                continue
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


def _default_train_rows(target_bb: str) -> list[Path]:
    return [ROOT / "data" / "runtime_calibration" / target_bb / "train.rows.jsonl"]


def _opponents_path(target_bb: str, override: Path | None) -> Path:
    if override is not None:
        return override
    return MODEL_DIR / "opponents_all_bb.json"


def _build_model(
    *,
    target_bb: str,
    row_paths: list[Path],
    console_logs: list[Path],
    fallback_console_bb: str,
    opponents_path: Path,
    out_path: Path,
    min_action_n: int,
    min_prior_n: int,
    action_prior_weight: float,
) -> dict[str, Any]:
    rows = _load_rows(row_paths, target_bb)
    console_rows = []
    for path in console_logs:
        console_rows.extend(_rows_from_console(path, target_bb, fallback_console_bb))
    all_rows = rows + console_rows
    opponents = _load_opponent_stats(opponents_path)
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
        "bb_bucket": target_bb,
        "generated_at": int(time.time()),
        "sources": {
            "rows": [str(p) for p in row_paths],
            "console_logs": [str(p) for p in console_logs],
            "fallback_console_bb": fallback_console_bb,
            "opponents": str(opponents_path),
            "structured_rows": len(rows),
            "console_rows": len(console_rows),
            "opponents_players": len(opponents),
            "numeric_action_players": len(player_action_counts),
            "numeric_preflop_players": len(player_preflop_counts),
        },
        "population_rates": _population_rates(opponents),
        "numeric_profile_priors": numeric_profile_priors,
        "preflop_bucket_priors": _build_preflop_priors(all_rows, min_n=min_prior_n),
        "action_likelihoods": _build_action_likelihoods(
            all_rows, min_action_n=min_action_n,
            prior_weight=action_prior_weight,
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
        "bb_bucket": target_bb,
        "out": str(out_path),
        "rows": len(rows),
        "console_rows": len(console_rows),
        "opponents": len(opponents),
        "population_rates": model["population_rates"],
        "numeric_profile_priors": numeric_profile_priors.get("counts", {}),
        "preflop_prior_keys": len(model["preflop_bucket_priors"]),
        "action_likelihood_keys": len(model["action_likelihoods"]),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--bb", default="all",
                    help="bb_1k/bb_10k/bb_50k, or all (default)")
    ap.add_argument("--row", type=Path, action="append", default=[],
                    help="structured calibration JSONL; defaults to data/runtime_calibration/<bb>/train.rows.jsonl")
    ap.add_argument("--console-log", type=Path, action="append", default=[],
                    help="optional console log; only global calibration lines are used")
    ap.add_argument("--fallback-console-bb", default="bb_10k",
                    help="fallback bb bucket only if a legacy console log cannot be inferred")
    ap.add_argument("--opponents", type=Path, default=None,
                    help="override opponent model JSON; default is pokerfate/data/local_models/opponents_all_bb.json")
    ap.add_argument("--out", type=Path, default=None,
                    help="override output path; only valid when --bb is not all")
    ap.add_argument("--min-action-n", type=int, default=12)
    ap.add_argument("--min-prior-n", type=int, default=20)
    ap.add_argument("--action-prior-weight", type=float, default=3000.0)
    args = ap.parse_args()

    raw_bb = str(args.bb).strip()
    if raw_bb == "all":
        targets = list(SUPPORTED_BB_KEYS)
    else:
        target = bb_key(raw_bb)
        if target not in SUPPORTED_BB_KEYS:
            ap.error(f"unsupported --bb: {args.bb}")
        targets = [target]
    fallback_console_bb = bb_key(args.fallback_console_bb)
    if fallback_console_bb not in SUPPORTED_BB_KEYS:
        ap.error(f"unsupported --fallback-console-bb: {args.fallback_console_bb}")
    if args.out is not None and len(targets) != 1:
        ap.error("--out is only valid for one --bb target")

    summaries = []
    for target_bb in targets:
        row_paths = args.row or _default_train_rows(target_bb)
        default_out = (
            MODEL_DIR / f"range_v2_empirical_model_{target_bb}.json"
            if raw_bb == "all"
            else empirical_model_path(MODEL_KEY)
        )
        summaries.append(_build_model(
            target_bb=target_bb,
            row_paths=row_paths,
            console_logs=args.console_log,
            fallback_console_bb=fallback_console_bb,
            opponents_path=_opponents_path(target_bb, args.opponents),
            out_path=args.out or default_out,
            min_action_n=args.min_action_n,
            min_prior_n=args.min_prior_n,
            action_prior_weight=args.action_prior_weight,
        ))
    print(json.dumps(summaries if len(summaries) > 1 else summaries[0],
                     ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
