"""The postflop action likelihood, fitted to hands shown at showdown.

P(action | strength bucket) decides how an opponent's range moves when he bets, raises, calls
or checks.  It used to be a table written by hand, scaled by hand-written rules about the
player and the bet size.  Here it is one fitted model per action:

    score[bucket] = base[street][bucket] + sum over features of weight[feature][bucket] * x
    likelihood[bucket] = exp(score[bucket])            (scaled so the largest is 1)

``likelihood_features`` is the only place the features are computed: the tracker calls it for
every action and both uses the result and records it, and ``scripts/fit_likelihood_model.py``
fits on exactly those recorded values — there is no second implementation to drift apart.

The model lives in the formula-fit file (``formula_fit.py``) under ``likelihood_model``.

Preflop works the same way one level down (``preflop_model`` in the same file): every hand
starts as equally likely, and each preflop action — open, re-raise, limp, call, check — has a
fitted likelihood per step of preflop strength (``PREFLOP_BINS``: tenths of all hands,
weakest first, the top twentieth split by hand into three groups), with weights for the
position, the raise size,
what the player faced, what he did earlier in the hand and what kind of player he is.  There is no hand-written preflop range any more.
"""
from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

from pokerfate.strategy.range_v2.formula_fit import CAT_ORDER, _load, formula_fit_path

STREETS = ("preflop", "flop", "turn", "river")
ACTIONS = ("bet", "raise_over", "call", "check")
AGGRESSIVE = ("bet", "raise_over")
# Every feature is 0 for "nothing special": a medium-sized bet, three players in the pot, out
# of position, a player we know nothing about, no earlier action in the hand worth noting.
FEATURES = (
    "size_small", "size_two_third", "size_pot", "size_none",
    "pot_two", "pot_four_plus",
    "in_position",
    "known", "tight", "aggressive",
    "prev_bet", "prev_call", "prev_check", "checked_this_street", "bet_two_streets",
)
_KNOWN_HANDS = 30.0          # hands at which we trust half of what we saw of a player
_MIN_LIKELIHOOD = 0.003


def _size_features(bet_ratio: float) -> Dict[str, float]:
    x = float(bet_ratio or 0.0)
    if x <= 0.0:
        return {"size_none": 1.0}
    if x <= 0.40:
        return {"size_small": 1.0}
    if x <= 0.55:
        return {}
    if x <= 0.80:
        return {"size_two_third": 1.0}
    return {"size_pot": 1.0}


def likelihood_features(
    *,
    action: str,
    street: str,
    bet_ratio: float,
    players_in_pot: int,
    in_position: bool,
    hands_seen: float,
    vpip: float,
    aggression_factor: float,
    history: Sequence[Tuple[str, str]],
) -> Dict[str, float]:
    """What the likelihood may depend on, for one action about to be applied.

    ``history`` is the player's own earlier actions in this hand as (street, action), action
    being bet / raise_over / call / check; ``players_in_pot`` counts everybody still in.
    """
    out: Dict[str, float] = {name: 0.0 for name in FEATURES}
    if action != "check":
        out.update(_size_features(bet_ratio))
    if players_in_pot <= 2:
        out["pot_two"] = 1.0
    elif players_in_pot >= 4:
        out["pot_four_plus"] = 1.0
    out["in_position"] = 1.0 if in_position else 0.0

    hands = max(0.0, float(hands_seen or 0.0))
    known = hands / (hands + _KNOWN_HANDS)
    out["known"] = known
    out["tight"] = known * float(np.clip((0.45 - float(vpip or 0.0)) / 0.15, -1.5, 1.5))
    out["aggressive"] = known * float(np.clip(float(aggression_factor or 0.0) - 1.0, -1.0, 2.0))

    index = STREETS.index(street) if street in STREETS else 0
    before = [a for s, a in history if index > 0 and s == STREETS[index - 1]]
    now = [a for s, a in history if s == street]
    if any(a in AGGRESSIVE for a in before):
        out["prev_bet"] = 1.0
    elif "call" in before:
        out["prev_call"] = 1.0
    elif "check" in before:
        out["prev_check"] = 1.0
    if "check" in now:
        out["checked_this_street"] = 1.0
    earlier = {s for s, a in history if s in STREETS[1:index] and a in AGGRESSIVE}
    if len(earlier) >= 2:
        out["bet_two_streets"] = 1.0
    return out


@lru_cache(maxsize=4)
def _model(path: str) -> Dict[str, Any]:
    """action -> (base[street] as vectors, weight matrix feature x bucket)."""
    raw = _load(path).get("likelihood_model") or {}
    out: Dict[str, Any] = {}
    for action, spec in (raw.get("actions") or {}).items():
        base = {street: np.array([float(row.get(cat, 0.0)) for cat in CAT_ORDER])
                for street, row in (spec.get("base") or {}).items()}
        weights = np.array([[float(((spec.get("weights") or {}).get(name) or {}).get(cat, 0.0))
                             for cat in CAT_ORDER] for name in FEATURES])
        out[action] = (base, weights)
    return out


def has_model() -> bool:
    path = formula_fit_path()
    return path is not None and bool(_model(str(path)))


def covers(street: str, action: str) -> bool:
    """True when the fitted model gives the likelihood of ``action`` on ``street``."""
    path = formula_fit_path()
    if path is None:
        return False
    spec = _model(str(path)).get(action)
    return spec is not None and street in spec[0]


def bucket_likelihood(street: str, action: str, features: Optional[Dict[str, float]]) -> Optional[np.ndarray]:
    """Likelihood of ``action`` per strength bucket in ``CAT_ORDER``; None without a fitted model."""
    if features is None or not covers(street, action):
        return None
    base, weights = _model(str(formula_fit_path()))[action]
    x = np.array([float(features.get(name, 0.0)) for name in FEATURES])
    score = base[street] + x @ weights
    return np.maximum(np.exp(score - score.max()), _MIN_LIKELIHOOD)


def feature_vector(features: Dict[str, float]) -> List[float]:
    return [float(features.get(name, 0.0)) for name in FEATURES]


# ── preflop ──────────────────────────────────────────────────────────────────────────────

PREFLOP_EDGES = (0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 0.95)        # upper edges of the percentile bins
# The strongest twentieth (AA-77, AK, AQs, AJs: 72 combos) is three bins, split by hand and not
# by percentile.  As one bin it gave AA and 77 the same likelihood for every action, and they
# are not played alike: of the hands in it that were shown after a first re-raise (474 at
# human tables to 2026-11-24), QQ+ were 39%, JJ and AK 34%, the rest 26% - against 25%, 31%
# and 44% of the combos.  After a 4-bet the same (330: 40% / 34% / 26%).  With one weight per
# combo hero's equity against a re-raise was 6-9 points too high with JJ-99 and 3-4 with AQ.
PREFLOP_TOP_GROUPS = (
    ("TT-77,AQs,AJs", ("TT", "99", "88", "77", "AQs", "AJs")),
    ("JJ,AK", ("JJ", "AKs", "AKo")),
    ("QQ+", ("QQ", "KK", "AA")),
)
PREFLOP_BINS = ("00-10", "10-20", "20-30", "30-40", "40-50", "50-60", "60-70", "70-80", "80-90", "90-95") + tuple(
    name for name, _classes in PREFLOP_TOP_GROUPS)
PREFLOP_STRONG_FROM = "80-90"             # the strongest fifth of all hands starts here (calibration cuts)
PREFLOP_ACTIONS = ("open", "reraise", "limp", "call", "check")
PREFLOP_GROUPS = ("all",)
PREFLOP_FEATURES = (
    "pos_early", "pos_sb", "pos_bb",
    "size_small", "size_big", "size_shove",
    "over_limpers", "four_bet", "facing_reraise",
    "limped_before", "raised_before",
    "known", "tight", "raises_often", "aggressive",
)


_PREFLOP_LABELS = {
    "open": "open", "3bet": "reraise", "4bet": "reraise", "5bet": "reraise", "raise": "reraise",
    "limp": "limp", "call_open": "call", "call_3bet": "call", "call": "call",
    "check_option": "check",
}


def preflop_label(action_type: str, action: str = "") -> Optional[str]:
    """Which preflop model an action belongs to; None for a fold.

    ``action_type`` is the bot's name for the preflop line (open / 3bet / 4bet / limp /
    call_open / call_3bet / check_option); without one the bare action decides.
    """
    label = _PREFLOP_LABELS.get(str(action_type or "").lower())
    if label is not None or action_type:
        return label
    return {"raise": "open", "call": "limp", "check": "check"}.get(str(action or "").lower())


def position_group(position: str) -> str:
    pos = str(position or "").upper()
    if pos == "SB":
        return "sb"
    if pos == "BB":
        return "bb"
    return "late" if pos in ("CO", "BTN") else "early"


def preflop_features(
    *,
    label: str,
    action_type: str,
    position: str,
    bet_ratio: float,
    is_raise_over: bool,
    hands_seen: float,
    vpip: float,
    pfr: float,
    aggression_factor: float,
    history: Sequence[Tuple[str, str]],
) -> Dict[str, float]:
    """What a preflop likelihood may depend on, for one action about to be applied.

    ``bet_ratio`` is the raise as a share of the pot before it (a 2.5bb open into the blinds is
    about 1.7); ``history`` is the player's own earlier actions in this hand as (street, action).
    The cut-off and the button are the position everything else is measured against.

    Tried and left out (2026-11-25): a weight of its own for the button, and the size of a
    first raise as a scale (the three size steps were cut for re-raises: a first raise into the
    blinds never reaches ``size_small`` and passes ``size_big`` only above 3.6bb).  Raises
    nobody called do differ along both (pocket pairs: 16.8% on the button against 20.4% in the
    cut-off; 12% for raises to 2.5bb or less against 21% for 3.5-4bb), but on the 3,550 shown
    preflop actions held out from the fit neither feature moved the score (2.2740 with both,
    2.2738 with neither).
    """
    out: Dict[str, float] = {name: 0.0 for name in PREFLOP_FEATURES}
    group = position_group(position)
    if group != "late":
        out[f"pos_{group}"] = 1.0
    ratio = float(bet_ratio or 0.0)
    if label in ("open", "reraise") and ratio > 0.0:
        if ratio >= 6.0:
            out["size_shove"] = 1.0
        elif ratio > 2.4:
            out["size_big"] = 1.0
        elif ratio <= 1.2:
            out["size_small"] = 1.0
    kind = str(action_type or "").lower()
    if label == "open" and is_raise_over:
        out["over_limpers"] = 1.0
    if kind in ("4bet", "5bet"):
        out["four_bet"] = 1.0
    if kind == "call_3bet":
        out["facing_reraise"] = 1.0
    before = [a for s, a in history if s == "preflop"]
    if any(a in AGGRESSIVE for a in before):
        out["raised_before"] = 1.0
    elif "call" in before:
        out["limped_before"] = 1.0

    hands = max(0.0, float(hands_seen or 0.0))
    known = hands / (hands + _KNOWN_HANDS)
    out["known"] = known
    out["tight"] = known * float(np.clip((0.45 - float(vpip or 0.0)) / 0.15, -1.5, 1.5))
    out["raises_often"] = known * float(np.clip((float(pfr or 0.0) - 0.12) / 0.10, -1.5, 1.5))
    out["aggressive"] = known * float(np.clip(float(aggression_factor or 0.0) - 1.0, -1.0, 2.0))
    return out


@lru_cache(maxsize=1)
def preflop_bin_index() -> np.ndarray:
    """Preflop strength bin (index into PREFLOP_BINS) of each of the 1326 combos."""
    from pokerfate.strategy.range_v2 import hand_combo_map as hcm

    index = np.searchsorted(np.array(PREFLOP_EDGES), np.asarray(hcm.STRENGTH_PCT), side="right").astype(np.int8)
    top = len(PREFLOP_EDGES)                         # the percentile bin PREFLOP_TOP_GROUPS divides
    strongest = index == top
    placed = np.zeros(len(index), dtype=bool)
    for offset, (_name, classes) in enumerate(PREFLOP_TOP_GROUPS):
        for cls in classes:
            combos = hcm.CATEGORY_TO_INDICES[cls]
            index[combos] = top + offset
            placed[combos] = True
    if not np.array_equal(placed, strongest):
        raise RuntimeError("PREFLOP_TOP_GROUPS must hold exactly the hands above the last percentile edge")
    return index


@lru_cache(maxsize=4)
def _preflop_model(path: str) -> Dict[str, Any]:
    """action -> (base[group] as vectors, weight matrix feature x bin)."""
    raw = _load(path).get("preflop_model") or {}
    out: Dict[str, Any] = {}
    if raw and list(raw.get("bins") or []) != list(PREFLOP_BINS):
        # A file fitted on other bins would be read with its missing bins at zero.
        logging.getLogger(__name__).warning(
            "preflop likelihood in %s was fitted on other strength bins; preflop actions are read as uninformative",
            path)
        return out
    for action, spec in (raw.get("actions") or {}).items():
        base = {group: np.array([float(row.get(b, 0.0)) for b in PREFLOP_BINS])
                for group, row in (spec.get("base") or {}).items()}
        weights = np.array([[float(((spec.get("weights") or {}).get(name) or {}).get(b, 0.0))
                             for b in PREFLOP_BINS] for name in PREFLOP_FEATURES])
        out[action] = (base, weights)
    return out


def has_preflop_model() -> bool:
    path = formula_fit_path()
    return path is not None and bool(_preflop_model(str(path)))


def preflop_likelihood(label: Optional[str], features: Optional[Dict[str, float]]) -> Optional[np.ndarray]:
    """Likelihood of a preflop action per strength bin in ``PREFLOP_BINS``; None without a fitted model."""
    path = formula_fit_path()
    if path is None or features is None or label is None:
        return None
    spec = _preflop_model(str(path)).get(label)
    if spec is None or "all" not in spec[0]:
        return None
    base, weights = spec
    x = np.array([float(features.get(name, 0.0)) for name in PREFLOP_FEATURES])
    score = base["all"] + x @ weights
    return np.maximum(np.exp(score - score.max()), _MIN_LIKELIHOOD)
