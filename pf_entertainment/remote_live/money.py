"""The money view's figures on their way to the VPS: only what the page draws.

The console's dashboard (BotBridge.bankroll_dashboard) carries every sample and seventeen fields
per hand.  The viewer gets sixteen figures and three numbers per hand.  The hands only ever grow,
so they travel as a tail: ``from`` hands are already there, ``points`` are the next ones; a tail
that starts at 0 replaces what was there (a new connection, or the bot replaced its session).
"""
from __future__ import annotations

# The figures of the money view (static/live-money.js); nothing else is sent, stored or served.
FACTS = ("session_delta_chips", "session_delta_bb", "big_blind", "base_at",
         "current_total_chips", "wallet_chips", "table_chips",
         "reward_chips", "rewards_uncertain", "sidegame_net_chips",
         "profit_lock_count", "auto_rebuy_count", "topup_count", "topup_chips",
         "loss_cap_chips", "loss_stop")
# One hand: when it was settled, its result in big blinds, the session's chips after it.
POINT = ("ts", "hand_delta_bb", "delta_chips")
CHUNK = 2000          # hands in one frame: at most ~37 bytes each, well inside MAX_FRAME
MAX_POINTS = 20000    # hands kept for one session; later ones are not sent


def _number(value, digits=None):
    if type(value) is int:
        return value
    if type(value) is float and value == value and abs(value) != float("inf"):
        return value if digits is None else round(value, digits)
    return None


def facts(dashboard: dict) -> dict:
    return {key: dashboard.get(key) for key in FACTS}


def points(hands: list) -> list:
    """Dashboard hand points as [ts, hand_delta_bb, delta_chips].

    Six decimals keep a result exact at every 1-2-5 blind and bound its width at any other.
    """
    return [[int(hand.get("ts") or 0), _number(hand.get("hand_delta_bb"), 6), _number(hand.get("delta_chips")) or 0]
            for hand in hands]


def next_part(dashboard, sent: int, sent_facts: dict | None) -> dict | None:
    """The money part of the next frame, given what this connection has already delivered.

    ``sent`` hands and ``sent_facts`` are what the server acknowledged; None when nothing is new.
    """
    if not isinstance(dashboard, dict) or not dashboard:
        return None
    now = facts(dashboard)
    hands = dashboard.get("hand_points") or []
    total = min(len(hands), MAX_POINTS)
    start = sent
    # Fewer hands than delivered, or another start time: these are another session's hands.
    if total < sent or (sent_facts is not None and now["base_at"] != sent_facts.get("base_at")):
        start = 0
    tail = points(hands[start:min(total, start + CHUNK)])
    if not tail and start == sent and now == sent_facts:
        return None
    return {"facts": now, "from": start, "points": tail}


def checked(part) -> tuple[dict, int, list]:
    """(facts, from, points) of an uploaded money part; ValueError unless it is exactly that."""
    if not isinstance(part, dict) or set(part) != {"facts", "from", "points"}:
        raise ValueError("invalid money")
    now, start, tail = part["facts"], part["from"], part["points"]
    if not isinstance(now, dict) or not set(now) <= set(FACTS):
        raise ValueError("invalid money facts")
    if any(value is not None and type(value) not in (bool, int, float) for value in now.values()):
        raise ValueError("invalid money facts")
    if type(start) is not int or start < 0 or not isinstance(tail, list) or len(tail) > CHUNK:
        raise ValueError("invalid money points")
    for point in tail:
        if (not isinstance(point, list) or len(point) != len(POINT)
                or any(value is not None and type(value) not in (int, float) for value in point)):
            raise ValueError("invalid money points")
    return now, start, tail
