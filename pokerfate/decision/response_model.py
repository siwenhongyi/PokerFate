"""How an opponent answers hero's action: fitted to what opponents did, not written by hand.

The solver path needs, for every action hero can take, the probability of each answer:
fold / call / raise when hero bets or raises, check / bet when hero checks to a player who
acts after him.  The solver supplies the equilibrium answer; this model supplies what human
opponents actually did in the decision logs, given the size of the bet, the opponent's own
line in the hand, what kind of player he is and what the range tracker thought he held:

    P(answer) = softmax(intercept[answer] + sum over features of weight[answer][feature] * x)

with the first answer of each kind (fold, check) as the reference.  One model per kind and
street (turn, river); heads-up pots only, because that is all the solver decides.

``response_features`` is the only place the features are computed.  The fit script
(``scripts/fit_response_model.py``) builds them from the logs with this function and the
solver path builds them at decision time with this function, so the two cannot drift apart.
The player features (known / tight / aggressive) are the range tracker's own
(``fitted_likelihood.likelihood_features``).

House robots are not in the fit and get no prediction: against them, and wherever the file
has no model, the solver's own frequencies stand.

``PF_RESPONSE_MODEL_PATH`` points at another file (a candidate under evaluation); ``off``
switches the model off, which leaves the equilibrium frequencies unadjusted.
"""
from __future__ import annotations

import json
import math
import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Optional, Sequence, Tuple

from pokerfate.strategy import pre_action
from pokerfate.strategy.range_v2.fitted_likelihood import likelihood_features

DEFAULT_PATH = Path(__file__).resolve().parents[1] / "data" / "runtime_calibration" / "response_model.json"
_OFF = {"off", "0", "none", "false", "disabled"}

STREETS = ("turn", "river")
FACING_BET = "facing_bet"
CHECKED_TO = "checked_to"
CLASSES = {FACING_BET: ("fold", "call", "raise"), CHECKED_TO: ("check", "bet")}
AGGRESSIVE = ("bet", "raise")
_BUCKETS = ("nuts", "strong", "medium", "draw", "weak_draw", "air")
_ORDER = ("preflop", "flop", "turn", "river")

# Every feature is 0 for "nothing special": no bet to answer, out of position, a player we
# know nothing about who only checked on the street before, a range that is all air.
FEATURES = {
    FACING_BET: (
        "size_lo", "size_mid", "size_hi", "facing_raise",
        "in_position", "checked_this_street",
        "prev_bet", "prev_call", "called_twice", "opp_bet_prev",
        "known", "tight", "aggressive",
        "nuts", "strong", "medium", "draw",
    ),
    CHECKED_TO: (
        "prev_bet", "prev_call", "called_twice", "opp_bet_prev",
        "known", "tight", "aggressive",
        "nuts", "strong", "medium", "draw",
    ),
}


def bet_size(*, to_call: float, pot_with_bet: float) -> float:
    """The bet a player faces as a fraction of the pot it was made into.

    ``pot_with_bet`` is the pot as the answering player finds it (the bet included) and
    ``to_call`` what he must add.  For a first bet this is bet / pot; for a raise it is the
    raise on top of a call over the pot after that call.
    """
    before = float(pot_with_bet) - float(to_call)
    if to_call <= 0.0 or before <= 0.0:
        return 0.0
    return float(to_call) / before


def response_features(
    *,
    kind: str,
    street: str,
    size: float,
    facing_raise: bool,
    in_position: bool,
    own_actions: Sequence[Tuple[str, str]],
    opponent_actions: Sequence[Tuple[str, str]],
    bucket_dist: Optional[Dict[str, float]],
    hands_seen: float = 0.0,
    vpip: float = 0.0,
    aggression_factor: float = 0.0,
    player: Optional[Dict[str, float]] = None,
) -> Dict[str, float]:
    """What the answer may depend on, for one player about to answer.

    ``own_actions`` / ``opponent_actions`` are the answering player's and the other player's
    earlier actions in this hand as (street, action), action being check / call / bet /
    raise.  ``bucket_dist`` is the tracker's range for the answering player before he acts.
    ``player`` carries known / tight / aggressive when they were recorded at the time (the
    fit); otherwise they are computed from ``hands_seen`` / ``vpip`` / ``aggression_factor``.
    """
    names = FEATURES[kind]
    out: Dict[str, float] = {name: 0.0 for name in names}

    if kind == FACING_BET:
        s = min(max(float(size or 0.0), 0.0), 3.0)
        out["size_lo"] = min(s, 0.5)
        out["size_mid"] = min(max(s - 0.5, 0.0), 0.5)
        out["size_hi"] = max(s - 1.0, 0.0)
        out["facing_raise"] = 1.0 if facing_raise else 0.0
        out["in_position"] = 1.0 if in_position else 0.0
        out["checked_this_street"] = 1.0 if any(s_ == street and a == "check" for s_, a in own_actions) else 0.0

    index = _ORDER.index(street) if street in _ORDER else 0
    before = _ORDER[index - 1] if index >= 2 else ""
    own_before = [a for s_, a in own_actions if s_ == before]
    if any(a in AGGRESSIVE for a in own_before):
        out["prev_bet"] = 1.0
    elif "call" in own_before:
        out["prev_call"] = 1.0
    called_on = {s_ for s_, a in own_actions if a == "call" and s_ in ("flop", "turn") and _ORDER.index(s_) < index}
    if len(called_on) >= 2:
        out["called_twice"] = 1.0
    if any(s_ == before and a in AGGRESSIVE for s_, a in opponent_actions):
        out["opp_bet_prev"] = 1.0

    if player is None:
        player = likelihood_features(
            action="check", street=street, bet_ratio=0.0, players_in_pot=2, in_position=False,
            hands_seen=hands_seen, vpip=vpip, aggression_factor=aggression_factor, history=(),
        )
    for name in ("known", "tight", "aggressive"):
        out[name] = float(player.get(name, 0.0) or 0.0)

    dist = {b: max(0.0, float((bucket_dist or {}).get(b, 0.0) or 0.0)) for b in _BUCKETS}
    total = sum(dist.values())
    if total > 1e-9:
        out["nuts"] = dist["nuts"] / total
        out["strong"] = dist["strong"] / total
        out["medium"] = dist["medium"] / total
        out["draw"] = (dist["draw"] + dist["weak_draw"]) / total
    return out


def model_path() -> Optional[Path]:
    override = os.environ.get("PF_RESPONSE_MODEL_PATH", "").strip()
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


def load_model() -> Dict[str, Any]:
    path = model_path()
    return _load(str(path)) if path is not None else {}


def covers(kind: str, street: str) -> bool:
    return bool(((load_model().get("models") or {}).get(kind) or {}).get(street))


def predict(kind: str, street: str, features: Optional[Dict[str, float]],
            pre_action_key: Optional[str] = None) -> Optional[Dict[str, float]]:
    """Probability of each answer in ``CLASSES[kind]``; None without a model for this spot.

    ``pre_action_key`` is the read on the answering player from a pre-selected action
    (``pre_action.read_key``); its fitted offsets are added to the class scores.  The bucket
    shares in ``features`` must then be the ones without that evidence, or it counts twice.
    """
    if features is None or kind not in CLASSES:
        return None
    spec = ((load_model().get("models") or {}).get(kind) or {}).get(street)
    if not spec:
        return None
    classes = CLASSES[kind]
    offsets = pre_action.response_offsets(kind, street, pre_action_key) if pre_action_key else {}
    scores = [0.0]
    for answer in classes[1:]:
        part = spec.get(answer) or {}
        weights = part.get("weights") or {}
        score = float(part.get("intercept", 0.0))
        for name in FEATURES[kind]:
            score += float(weights.get(name, 0.0)) * float(features.get(name, 0.0))
        scores.append(score + float(offsets.get(answer, 0.0)))
    top = max(scores)
    exps = [math.exp(s - top) for s in scores]
    total = sum(exps)
    return {answer: e / total for answer, e in zip(classes, exps)}


def shifted_call_win_share(
    hands: Sequence[Tuple[Any, float, float, float]],
    hero_strength: Any,
    call_share_change: float,
) -> Optional[Tuple[float, float]]:
    """Hero's share of the pot when called, before and after the calling range is resized.

    On the river a call ends the hand, so what hero wins when called depends only on which
    hands call.  The solver's value for "called" belongs to the equilibrium calling range.
    When the opponent is expected to call less often than that, the calls that go missing
    are taken from his weakest calling hands first; when more often, the extra calls come
    from the strongest hands he folds at equilibrium.

    ``hands`` holds one (strength, reach weight, P(fold), P(call)) per opponent hand at
    equilibrium, strength comparable with ``hero_strength`` (higher wins);
    ``call_share_change`` is how much of his whole range moves into the calling range
    (negative: out of it).  Returns (share with the equilibrium callers, share with the
    resized callers), a tie counting half, or None when nobody calls on one side.
    """
    rows = [(s, float(w) * max(0.0, float(c)), float(w) * max(0.0, float(f)))
            for s, w, f, c in hands if float(w) > 0.0]
    reach = sum(float(w) for _s, w, _f, _c in hands if float(w) > 0.0)
    call_eq = sum(c for _s, c, _f in rows)
    if reach <= 1e-12 or call_eq <= 1e-12:
        return None

    def share(masses: Sequence[Tuple[Any, float]]) -> Optional[float]:
        total = sum(m for _s, m in masses)
        if total <= 1e-12:
            return None
        won = sum(m * (1.0 if hero_strength > s else 0.5 if hero_strength == s else 0.0) for s, m in masses)
        return won / total

    calls = [c for _s, c, _f in rows]
    change = float(call_share_change) * reach
    order = sorted(range(len(rows)), key=lambda k: rows[k][0])
    if change < 0.0:
        left = -change
        for i in order:                                   # weakest callers fold first
            take = min(calls[i], left)
            calls[i] -= take
            left -= take
            if left <= 1e-15:
                break
    elif change > 0.0:
        left = change
        for i in reversed(order):                         # strongest folders call first
            take = min(rows[i][2], left)
            calls[i] += take
            left -= take
            if left <= 1e-15:
                break
    before = share([(s, c) for s, c, _f in rows])
    after = share([(rows[i][0], m) for i, m in enumerate(calls)])
    if before is None or after is None:
        return None
    return before, after
