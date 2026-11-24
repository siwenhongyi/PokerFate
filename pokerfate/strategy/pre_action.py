"""What a pre-selected action says about a player.

With every "your turn" notice the table tells everybody whether the seat had picked its action
in advance (``ActionNotifyBRC.pre_action_result``): 2 = the pre-selected action is being
executed, 1 = it was reset by the bet or raise just before, 0 = nothing was selected.  The
client has three buttons — check-or-fold, call the current amount (a check when nothing is
owed), call any amount — and a seat that is first to act on a street cannot use them.

Measured on the wire log (``scripts/fit_pre_action.py``; the numbers live in
``pre_action_fit.json`` next to the other fitted files):

* a pre-selected **check** is a hand that gave up: against a bet it folds about three times as
  often (in odds) as a player who checked normally, whatever the size of the bet, on the same
  street and on the following ones, and it rarely bets when checked to;
* a pre-selected **call** is capped: two pair or better is a third to a half as likely as
  after a normal call; it does not fold more later, it raises less;
* a pre-selected check of the big blind's **option** before the flop says nothing about the
  cards but the player folds more and raises less on the flop;
* a pre-selected call before the flop, a reset, and the absence of a pre-selection say nothing
  worth using.

The read ends when the player puts chips in by his own choice afterwards: a pre-selected
checker who then calls a bet is harder to move than a normal caller, and one who bets is not
weak.  ``update_read`` is the one place that rule lives; the range tracker, the response model
and the rule engine all take their reads from it.

``PF_PRE_ACTION=off`` switches every use off (the flag is still carried and logged);
any other value is the path of another fit file.
"""
from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Optional, Sequence

import numpy as np

from pokerfate.strategy.range_v2.formula_fit import CAT_ORDER

NONE, RESET, EXECUTED = 0, 1, 2
STREETS = ("preflop", "flop", "turn", "river")
# What a read is worth right now (``Read.key``).
CHECK_NOW, CHECK_PREV, OPTION_PREV, CALL_NOW, CALL_PREV = (
    "check_now", "check_prev", "option_prev", "call_now", "call_prev")
WEAK_KEYS = (CHECK_NOW, CHECK_PREV, OPTION_PREV)
DEFAULT_PATH = Path(__file__).resolve().parents[1] / "data" / "runtime_calibration" / "pre_action_fit.json"
_OFF = {"off", "0", "none", "false", "disabled"}
_AGGRESSIVE = {"bet", "raise", "raise_over"}


def fit_path() -> Optional[Path]:
    override = os.environ.get("PF_PRE_ACTION", "").strip()
    if override.lower() in _OFF:
        return None
    if override and override.lower() not in {"on", "1", "true"}:
        return Path(override)
    return DEFAULT_PATH


@lru_cache(maxsize=4)
def _load(path: str) -> Dict[str, Any]:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def fit() -> Dict[str, Any]:
    path = fit_path()
    return _load(str(path)) if path is not None else {}


def enabled() -> bool:
    return bool(fit())


def normalize(flag: Any) -> int:
    """The wire value as NONE / RESET / EXECUTED (anything unknown is NONE)."""
    try:
        value = int(flag or 0)
    except (TypeError, ValueError):
        return NONE
    return value if value in (RESET, EXECUTED) else NONE


@dataclass(frozen=True)
class Read:
    """The latest pre-selected action of a player that is still in force.

    ``kind``: 'check' (postflop), 'call' (postflop) or 'option' (the big blind's free check
    before the flop); ``street``: where it happened.
    """
    kind: str
    street: str

    def key(self, street: str) -> Optional[str]:
        """What the read is worth on ``street``, or None when it no longer applies."""
        try:
            gap = STREETS.index(str(street).lower()) - STREETS.index(self.street)
        except ValueError:
            return None
        if gap < 0:
            return None
        if self.kind == "option":
            return OPTION_PREV if gap == 1 else None
        if self.kind == "check":
            return CHECK_NOW if gap == 0 else CHECK_PREV
        if self.kind == "call":
            return CALL_NOW if gap == 0 else CALL_PREV
        return None


def update_read(read: Optional[Read], *, street: str, action: str, pre_action: int) -> Optional[Read]:
    """The read on a player after one more of his actions.

    A pre-selected check or call replaces what was there; a bet or raise, a fold, and a call
    after a pre-selected check end it; anything else leaves it as it was.
    """
    act = str(action or "").lower()
    st = str(street or "").lower()
    if act in _AGGRESSIVE or act == "fold":
        return None
    if normalize(pre_action) == EXECUTED and act in ("check", "call"):
        if st == "preflop":
            return Read("option", st) if act == "check" else None
        if st in STREETS:
            return Read(act, st)
    if act == "call" and read is not None and read.kind in ("check", "option"):
        return None
    return read


def read_key(read: Optional[Read], street: str) -> Optional[str]:
    return read.key(street) if read is not None else None


# ── numbers ──────────────────────────────────────────────────────────────────────────────

def range_ratio(kind: str, street: str) -> Optional[np.ndarray]:
    """Likelihood of "it was pre-selected" per strength bucket (``CAT_ORDER``), relative to
    all hands that took the same action; None when nothing is fitted for it."""
    row = ((fit().get("range") or {}).get(str(kind)) or {}).get(str(street).lower())
    if not isinstance(row, dict):
        return None
    out = np.array([float(row.get(cat, 1.0) or 1.0) for cat in CAT_ORDER], dtype=np.float64)
    return out if np.all(out > 0.0) and not np.allclose(out, 1.0) else None


def fold_shift(key: Optional[str]) -> float:
    """Log-odds added to "folds to a bet" for a player with this read (0 without one)."""
    return float((fit().get("fold_shift") or {}).get(str(key), 0.0) or 0.0) if key else 0.0


def raise_factor(key: Optional[str]) -> float:
    """What is left of the chance that he raises a bet (1 without a read)."""
    return float((fit().get("raise_factor") or {}).get(str(key), 1.0) or 1.0) if key else 1.0


def bet_shift(key: Optional[str]) -> float:
    """Log-odds added to "bets when checked to" for a player with this read."""
    return float((fit().get("bet_shift") or {}).get(str(key), 0.0) or 0.0) if key else 0.0


def shifted(prob: float, delta: float) -> float:
    """``prob`` moved by ``delta`` in log-odds."""
    p = min(max(float(prob), 1e-6), 1.0 - 1e-6)
    if not delta:
        return p
    z = math.log(p / (1.0 - p)) + float(delta)
    return 1.0 / (1.0 + math.exp(-z))


def base_fold_rate(street: str, opponents: int, frac: float) -> Optional[float]:
    """Measured chance that one player without a read folds to a bet of ``frac`` pot when the
    bettor has ``opponents`` players to get through; None when it is not in the fit."""
    row = ((fit().get("fold_rate") or {}).get(str(street).lower()) or {}).get(str(min(max(int(opponents), 1), 3)))
    if not isinstance(row, dict):
        return None
    size = "small" if frac < 0.35 else ("mid" if frac < 0.8 else "big")
    value = row.get(size)
    return float(value) if value else None


def field_fold_prob(street: str, reads: Sequence[Optional[str]], frac: float) -> Optional[float]:
    """Chance that every opponent folds to a bet of ``frac`` pot, ``reads`` holding one entry
    per opponent (his read key or None).

    The single chances multiply (measured: 46% for two opponents one of whom pre-selected a
    check, 45% by the product).  A player without a read folds at the measured rate for the
    street, the size and the number of opponents; a player with a read at the mid-size rate
    moved by the read's log-odds, because his answer does not depend on the size.
    """
    n = len(reads)
    if n == 0:
        return None
    plain = base_fold_rate(street, n, frac)
    anchor = base_fold_rate(street, n, 0.5)
    if plain is None or anchor is None:
        return None
    out = 1.0
    for key in reads:
        shift = fold_shift(key)
        out *= shifted(anchor, shift) if shift else plain
    return out


def response_offsets(kind: str, street: str, key: Optional[str]) -> Dict[str, float]:
    """Logit offsets per answer class for the solver path's response model
    (``decision/response_model.py``): {class: offset against the reference class}."""
    if not key:
        return {}
    row = (((fit().get("response") or {}).get(str(kind)) or {}).get(str(street).lower()) or {}).get(str(key))
    return {str(k): float(v) for k, v in row.items()} if isinstance(row, dict) else {}
