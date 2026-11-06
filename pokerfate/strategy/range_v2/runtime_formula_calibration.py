"""Runtime equity calibration parameter loader."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional, Set

log = logging.getLogger(__name__)

RUNTIME_RANGE_CALIBRATION_ENABLED = (
    os.environ.get("PF_RUNTIME_RANGE_CALIBRATION", "1").lower()
    not in ("0", "false", "no", "")
)
RUNTIME_RANGE_CALIBRATION_ROOT = (
    Path(__file__).resolve().parents[2] / "data" / "runtime_calibration"
)
RUNTIME_MODEL_KEY = "all_bb"

_CACHE: Dict[tuple[str, str], Optional[Dict[str, Any]]] = {}
_WARNED: Set[tuple[str, str]] = set()


def bb_key(big_blind: Optional[float]) -> str:
    bb = float(big_blind or 0.0)
    rounded = round(bb)
    if abs(bb - rounded) < 1e-6:
        bb_int = int(rounded)
        if bb_int >= 1000 and bb_int % 1000 == 0:
            return f"bb_{bb_int // 1000}k"
        return f"bb_{bb_int}"
    return "bb_" + str(bb).replace(".", "_")


def load_params(kind: str, big_blind: Optional[float]) -> Optional[Dict[str, Any]]:
    if not RUNTIME_RANGE_CALIBRATION_ENABLED or kind not in {"bucket", "equity"}:
        return None
    key = RUNTIME_MODEL_KEY
    cache_key = (kind, key)
    if cache_key in _CACHE:
        return _CACHE[cache_key]

    path = RUNTIME_RANGE_CALIBRATION_ROOT / key / f"runtime_{kind}_params.json"
    if not path.exists():
        if cache_key not in _WARNED:
            log.warning("runtime %s calibration not found for %s: %s", kind, key, path)
            _WARNED.add(cache_key)
        _CACHE[cache_key] = None
        return None

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError(f"expected object, got {type(raw).__name__}")
        _CACHE[cache_key] = raw
        log.info(
            "runtime %s calibration loaded for %s: %s contexts from %s",
            kind,
            key,
            len(raw),
            path,
        )
        return raw
    except Exception:
        log.exception("runtime %s calibration load failed for %s: %s", kind, key, path)
        _CACHE[cache_key] = None
        return None
