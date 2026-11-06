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

_CACHE: Dict[str, Optional[Dict[str, Any]]] = {}
_WARNED: Set[str] = set()


def load_params(kind: str) -> Optional[Dict[str, Any]]:
    if not RUNTIME_RANGE_CALIBRATION_ENABLED or kind not in {"bucket", "equity"}:
        return None
    if kind in _CACHE:
        return _CACHE[kind]

    path = RUNTIME_RANGE_CALIBRATION_ROOT / f"runtime_{kind}_params.json"
    if not path.exists():
        if kind not in _WARNED:
            log.warning("runtime %s calibration not found: %s", kind, path)
            _WARNED.add(kind)
        _CACHE[kind] = None
        return None

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError(f"expected object, got {type(raw).__name__}")
        _CACHE[kind] = raw
        log.info("runtime %s calibration loaded: %s contexts from %s", kind, len(raw), path)
        return raw
    except Exception:
        log.exception("runtime %s calibration load failed: %s", kind, path)
        _CACHE[kind] = None
        return None
