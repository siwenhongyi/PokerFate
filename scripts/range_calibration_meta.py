"""Helpers for runtime calibration row metadata.

Rows collected before 2026-05-21 do not contain strategy metadata.  Treat them
as ``legacy`` so historical data stays usable while current-policy validation
can be isolated.
"""

from __future__ import annotations

from collections import Counter
from typing import Any, Iterable

LEGACY_VERSION = "legacy"


def row_strategy_version(row: dict[str, Any]) -> str:
    return str(row.get("strategy_version") or LEGACY_VERSION)


def row_experiment_flags(row: dict[str, Any]) -> dict[str, str]:
    raw = row.get("experiment_flags") or {}
    if not isinstance(raw, dict):
        return {}
    return {str(k): str(v) for k, v in raw.items()}


def row_experiment_profile(row: dict[str, Any]) -> str:
    flags = row_experiment_flags(row)
    if not flags:
        return LEGACY_VERSION
    keys = (
        "PF_TURN_FLOP_RELATIVE_GUARD",
        "PF_RUNTIME_RANGE_CALIBRATION",
        "PF_BUCKET_CALIBRATION",
    )
    return "|".join(f"{key}={flags.get(key, '')}" for key in keys)


def parse_flag_filters(values: Iterable[str] | None) -> dict[str, str]:
    filters: dict[str, str] = {}
    for item in values or []:
        if "=" in item:
            key, value = item.split("=", 1)
        else:
            key, value = item, "1"
        key = key.strip()
        if key:
            filters[key] = value.strip()
    return filters


def filter_rows_by_meta(
    rows: list[dict[str, Any]],
    *,
    strategy_version: str | None = None,
    experiment_flags: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    flags = experiment_flags or {}
    if not strategy_version and not flags:
        return rows
    out: list[dict[str, Any]] = []
    for row in rows:
        if strategy_version and row_strategy_version(row) != strategy_version:
            continue
        row_flags = row_experiment_flags(row)
        if any(row_flags.get(key) != value for key, value in flags.items()):
            continue
        out.append(row)
    return out


def limit_rows(rows: list[dict[str, Any]], limit: int = 0) -> list[dict[str, Any]]:
    if limit and limit > 0:
        return rows[:limit]
    return rows


def meta_summary(rows: list[dict[str, Any]], *, max_flags: int = 12) -> dict[str, Any]:
    versions = Counter(row_strategy_version(row) for row in rows)
    flag_keys: Counter[str] = Counter()
    flag_values: dict[str, Counter[str]] = {}
    for row in rows:
        for key, value in row_experiment_flags(row).items():
            flag_keys[key] += 1
            flag_values.setdefault(key, Counter())[value] += 1
    selected = [key for key, _count in flag_keys.most_common(max_flags)]
    return {
        "rows": len(rows),
        "strategy_versions": dict(versions.most_common(12)),
        "experiment_flags": {
            key: dict(flag_values[key].most_common(8))
            for key in selected
        },
    }
