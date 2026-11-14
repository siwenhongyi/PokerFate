"""Loader for the pure-robot hand export (docs/pure_robot_hands_*.jsonl).

Each hand becomes a dict with a per-action table that carries everything a decision rule
could depend on: street, who acts, price, pot, stacks, who bet last, how many players are
left, plus the actor's hole cards when the hand was shown down.

Amounts are converted to big blinds.  ``raise`` in the export covers both a first bet and a
raise; here ``kind`` is one of fold / check / call / bet / raise.
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

HERO = "10262053"
DEFAULT_PATH = Path(__file__).resolve().parents[1] / "docs" / "pure_robot_hands_2026-11-12.jsonl"
STREETS = {1: "preflop", 2: "flop", 3: "turn", 4: "river"}
BLIND_ACTS = {"sb", "bb", "force_bb"}


def load(path=DEFAULT_PATH) -> list:
    hands = []
    with open(path) as fh:
        for line in fh:
            line = line.strip()
            if line:
                hands.append(expand(json.loads(line)))
    return hands


def _position_labels(raw) -> dict:
    """seat -> position label, taken from who posted what and who acted first preflop.

    HU: the seat that acts first preflop is "SB" (button), the other "BB".
    3-way: BTN / SB / BB when the hand has a normal blind structure, else the export's label
    prefixed with "~" so that irregular hands can be left out of position tables.
    """
    seats = raw["seats"]
    labels = {}
    posts = {a[1]: a[2] for a in raw["actions"] if a[2] in BLIND_ACTS}
    regular = Counter(posts.values()) == Counter({"sb": 1, "bb": 1}) and "force_bb" not in posts.values()
    if len(seats) == 2:
        first = next((a[1] for a in raw["actions"] if a[2] not in BLIND_ACTS), None)
        for s in seats:
            if regular and first is not None:
                labels[s["seat"]] = "SB" if posts.get(s["seat"]) == "sb" else "BB"
            else:
                labels[s["seat"]] = "~" + s["pos"]
        return labels
    for s in seats:
        if regular:
            p = posts.get(s["seat"])
            labels[s["seat"]] = "SB" if p == "sb" else "BB" if p == "bb" else "BTN"
        else:
            labels[s["seat"]] = "~" + s["pos"]
    return labels


def expand(raw) -> dict:
    bb = 10000.0
    seats = {s["seat"]: s for s in raw["seats"]}
    labels = _position_labels(raw)
    stack = {k: s["stack"] / bb for k, s in seats.items()}
    start_stack = dict(stack)
    put_street = {k: 0.0 for k in seats}
    put_total = {k: 0.0 for k in seats}
    folded, allin = set(), set()
    acts = []
    street = 1
    last_aggr = None           # seat of the last bet / raise on this street
    last_aggr_any = None       # seat of the last bet / raise in the hand
    pre_aggr = None            # last preflop raiser
    n_raises_street = 0
    voluntary_pre = []         # seats that put money in voluntarily preflop, in order
    limpers = []
    first_in_done = False
    acted_street = set()
    for i, (st, seat, act, to_call, amt, pot) in enumerate(raw["actions"]):
        if st != street:
            street = st
            put_street = {k: 0.0 for k in seats}
            last_aggr = None
            n_raises_street = 0
            acted_street = set()
        amt_bb = (amt or 0) / bb
        pot_bb = (pot or 0) / bb
        call_bb = (to_call or 0) / bb
        if act in BLIND_ACTS:
            stack[seat] -= amt_bb
            put_street[seat] += amt_bb
            put_total[seat] += amt_bb
            if stack[seat] <= 1e-9:
                allin.add(seat)
            continue
        if act == "raise":
            kind = "bet" if call_bb <= 1e-9 and st > 1 else "raise"
        else:
            kind = act
        live = [k for k in seats if k not in folded]
        can_act = [k for k in live if k not in allin]
        max_put = max(put_street.values())
        row = {
            "i": i, "street": STREETS[st], "st": st, "seat": seat, "uid": seats[seat]["uid"],
            "hero": seats[seat]["uid"] == HERO, "pos": labels[seat], "kind": kind,
            "to_call": call_bb, "amt": amt_bb, "pot": pot_bb,
            "stack": stack[seat], "start_stack": start_stack[seat],
            "n_live": len(live), "n_can_act": len(can_act),
            "facing_seat": last_aggr, "facing_hero": (last_aggr is not None and seats[last_aggr]["uid"] == HERO),
            "last_aggr_any": last_aggr_any, "pre_aggr": pre_aggr,
            "n_raises_street": n_raises_street,
            "first_on_street": not acted_street,
            "acted_before": seat in acted_street,
            "limpers_before": list(limpers), "first_in": (st == 1 and not first_in_done),
            "put_street": put_street[seat], "max_put": max_put,
            "allin": amt_bb >= stack[seat] - 1e-6 and amt_bb > 0,
            "eff_stack": min(stack[seat], max((stack[k] + put_street[k] - put_street[seat])
                                              for k in live if k != seat)) if len(live) > 1 else stack[seat],
        }
        # size descriptors
        if kind == "bet":
            row["frac"] = amt_bb / pot_bb if pot_bb > 0 else None
        elif kind == "raise":
            raise_to = put_street[seat] + amt_bb
            row["raise_to"] = raise_to
            row["raise_x"] = raise_to / max_put if max_put > 0 else None
            pot_after_call = pot_bb + call_bb
            row["frac"] = (amt_bb - call_bb) / pot_after_call if pot_after_call > 0 else None
        if call_bb > 1e-9:
            row["price"] = call_bb / (pot_bb + call_bb)          # pot odds needed
            row["faced_frac"] = call_bb / (pot_bb - call_bb) if pot_bb - call_bb > 1e-9 else None
        acts.append(row)
        # state update
        acted_street.add(seat)
        if kind == "fold":
            folded.add(seat)
        else:
            stack[seat] -= amt_bb
            put_street[seat] += amt_bb
            put_total[seat] += amt_bb
            if stack[seat] <= 1e-6:
                allin.add(seat)
        if st == 1 and kind in ("call", "raise"):
            if not first_in_done and kind == "call":
                limpers.append(seat)
            elif kind == "call" and pre_aggr is None:
                limpers.append(seat)
            if seat not in voluntary_pre:
                voluntary_pre.append(seat)
            first_in_done = True
        if kind in ("bet", "raise"):
            last_aggr = seat
            last_aggr_any = seat
            n_raises_street += 1
            if st == 1:
                pre_aggr = seat
    board = raw["board"]
    hand = {
        "gameid": raw["gameid"], "hand": raw["hand"], "group": raw["group"], "room": raw["room"],
        "start": raw["start"], "known_at_start": raw["known_at_start"],
        "seats": seats, "labels": labels, "hero_seat": next(k for k, s in seats.items() if s["uid"] == HERO),
        "hero_net": raw["hero_net"] / bb, "table_rake": raw["table_rake"] / bb, "hero_rake": raw["hero_rake"] / bb,
        "hole": raw["hole"], "board": board, "show": raw["show"], "acts": acts,
        "net": {k: s["net"] / bb for k, s in seats.items()},
        "start_stack": start_stack, "put_total": put_total, "folded": folded,
        "regular": not any(v.startswith("~") for v in labels.values()),
        "pre_aggr": pre_aggr, "voluntary_pre": voluntary_pre,
    }
    for a in acts:
        a["hand"] = hand
        if a["hero"]:
            a["cards"] = raw["hole"]
        else:
            a["cards"] = raw["show"].get(a["uid"])
        a["board"] = board[: {1: 0, 2: 3, 3: 4, 4: 5}[a["st"]]]
    return hand


def robot_acts(hands):
    for h in hands:
        for a in h["acts"]:
            if not a["hero"]:
                yield a


def hero_acts(hands):
    for h in hands:
        for a in h["acts"]:
            if a["hero"]:
                yield a


def size_tier(frac) -> str:
    """Robot bets come in four pot fractions; anything else is reported as is."""
    if frac is None:
        return "?"
    for name, v in (("33%", 1 / 3), ("50%", 0.5), ("67%", 2 / 3), ("100%", 1.0)):
        if abs(frac - v) <= 0.03:
            return name
    return "other"


if __name__ == "__main__":
    hs = load()
    print(len(hs), "hands;", Counter(h["group"] for h in hs), "regular:", sum(h["regular"] for h in hs))
    print(Counter(a["kind"] for h in hs for a in h["acts"]))
