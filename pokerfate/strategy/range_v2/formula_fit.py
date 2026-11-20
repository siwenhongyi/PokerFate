"""The fitted formula layer of the range tracker: where its file is and which one is in force.

The file (JSON, next to the bucket model) holds ``likelihood_model``: the postflop action
likelihood fitted by ``scripts/fit_likelihood_model.py`` and read by ``fitted_likelihood.py``.
Everything above this layer (the bucket model, the online hero-equity calibrator) is fitted
on its output, so a new file means re-extracting rows and retraining those — see
docs/range_v2_bucket_ml.md.

``PF_FORMULA_FIT_PATH`` points the tracker at another file (a candidate under evaluation);
``off`` leaves the tracker without a postflop likelihood: actions then do not move ranges.
"""
from __future__ import annotations

import hashlib
import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Optional

CAT_ORDER = ("nuts", "strong", "medium", "draw", "weak_draw", "air")
DEFAULT_PATH = Path(__file__).resolve().parents[2] / "data" / "runtime_calibration" / "formula_fit.json"
_OFF = {"off", "0", "none", "false", "disabled"}


def formula_fit_path() -> Optional[Path]:
    override = os.environ.get("PF_FORMULA_FIT_PATH", "").strip()
    if override.lower() in _OFF:
        return None
    return Path(override) if override else DEFAULT_PATH


@lru_cache(maxsize=4)
def _load(path: str) -> Dict[str, Any]:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


@lru_cache(maxsize=4)
def _fingerprint(path: str) -> str:
    try:
        return hashlib.sha1(Path(path).read_bytes()).hexdigest()[:12]
    except OSError:
        return "none"


def fingerprint() -> str:
    """Identity of the corrections in force ("none" without any).

    Extracted rows carry it and the bucket model remembers the one it was trained on: a model
    fitted on another formula layer corrects errors that are no longer there.
    """
    path = formula_fit_path()
    return _fingerprint(str(path)) if path is not None else "none"


def load_formula_fit() -> Dict[str, Any]:
    path = formula_fit_path()
    return _load(str(path)) if path is not None else {}
