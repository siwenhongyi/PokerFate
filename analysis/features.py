"""Derived per-hand / per-spot features on top of analysis.pflog hands.

Everything here is generic over "player X" so the same code produces hero stats
and pool stats. No strategy code is imported.
"""
from __future__ import annotations

import math
from collections import Counter, defaultdict
from typing import Callable, Iterable, Optional

PRE_ORDER = {"UTG": 0, "MP": 1, "CO": 2, "BTN": 3, "SB": 4, "BB": 5}
POST_ORDER = {"SB": 0, "BB": 1, "UTG": 2, "MP": 3, "CO": 4, "BTN": 5}


def usable(h) -> bool:
    return bool(h.get("result")) and h.get("dealt") and not h.get("street_mismatch")


def wilson(k: int, n: int, z: float = 1.96) -> tuple:
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    r = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return ((c - r) / d, (c + r) / d)


def fmt_rate(k: int, n: int) -> str:
    if n == 0:
        return "   –   (n=0)"
    lo, hi = wilson(k, n)
    flag = " 低置信" if n < 30 else ""
    return f"{100 * k / n:5.1f}% [{100 * lo:4.1f},{100 * hi:4.1f}] (n={n}){flag}"


def mean_se(xs: list) -> tuple:
    n = len(xs)
    if n == 0:
        return (float("nan"), float("nan"), 0)
    m = sum(xs) / n
    if n < 2:
        return (m, float("nan"), n)
    var = sum((x - m) ** 2 for x in xs) / (n - 1)
    return (m, math.sqrt(var / n), n)


# ---------------------------------------------------------------------------
# Preflop spot classification
# ---------------------------------------------------------------------------
def preflop_spots(h) -> list:
    """One record per preflop action with the situation the actor faced.

    situation ∈ unopened (folded to actor) | limped (≥1 limper, no raise) |
    vs_open (1 raise) | vs_3bet (2 raises) | vs_4bet+ (≥3 raises)
    """
    out = []
    limpers = 0
    raises = 0
    callers_since_raise = 0
    raiser = None
    opener = None
    open_to_bb = None
    acted = Counter()
    bb = h["bb"]
    for a in h["actions"]:
        if a["street"] != "preflop":
            break
        if raises == 0:
            sit = "limped" if limpers else "unopened"
        elif raises == 1:
            sit = "vs_open"
        elif raises == 2:
            sit = "vs_3bet"
        else:
            sit = "vs_4bet+"
        rec = dict(
            who=a["who"], pos=a["pos"], hero=a["hero"], act=a["act"], kind=a["kind"], sit=sit,
            limpers=limpers, raises=raises, callers=callers_since_raise, raiser=raiser, opener=opener,
            open_to_bb=open_to_bb, to_call_bb=a["to_call"] / bb, pot_bb=a["pot_before"] / bb,
            to_bb=(a.get("to") or 0) / bb, first_action=acted[a["who"]] == 0, n=h["n"],
            stack_bb=a["stack_before"] / bb, allin=bool(a.get("allin")), i=a["i"],
            was_raiser=(raiser == a["who"]), dec=a.get("dec"),
        )
        out.append(rec)
        acted[a["who"]] += 1
        if a["act"] == "raise":
            raises += 1
            callers_since_raise = 0
            raiser = a["who"]
            if raises == 1:
                opener = a["who"]
                open_to_bb = (a.get("to") or 0) / bb
        elif a["act"] == "call":
            if raises == 0:
                limpers += 1
            else:
                callers_since_raise += 1
    return out


def pot_type(h) -> str:
    r = h["pf_raises"]
    return "limped" if r == 0 else ("SRP" if r == 1 else ("3bet" if r == 2 else "4bet+"))


# ---------------------------------------------------------------------------
# Postflop spot classification
# ---------------------------------------------------------------------------
def postflop_order(h, names: Iterable) -> list:
    """Postflop action order approximated from position labels (SB first, BTN last)."""
    pos = {p["name"]: p["pos"] for p in h["players"]}
    return sorted(names, key=lambda n: POST_ORDER.get(pos.get(n), 2.5))


def postflop_spots(h) -> list:
    """One record per postflop action with the context the actor faced."""
    out = []
    bb = h["bb"]
    pos = {p["name"]: p["pos"] for p in h["players"]}
    pfr = h["pfr_last"]
    ptype = pot_type(h)
    street = None
    prev_street_aggr = pfr  # last aggressor of the previous street (preflop → flop)
    street_aggr = None
    bets = 0
    checked = set()
    acted_this_street = []
    n_flop = len(h["flop_players"])
    street_first_actions = {}
    for a in h["actions"]:
        if a["street"] == "preflop":
            continue
        if a["street"] != street:
            if street is not None:
                prev_street_aggr = street_aggr if street_aggr else None
            street = a["street"]
            street_aggr = None
            bets = 0
            checked = set()
            acted_this_street = []
        who = a["who"]
        active = a["n_active"]
        facing = a["to_call"] > 0
        # position: IP if actor is last in postflop order among active players at this point
        # (approximate: uses labels; exact seat order is not in the log)
        rec = dict(
            street=street, who=who, pos=pos.get(who), hero=a["hero"], act=a["act"], kind=a["kind"],
            facing=facing, to_call_bb=a["to_call"] / bb, pot_bb=a["pot_before"] / bb,
            bet_frac=(a["to_call"] / (a["pot_before"] - a["to_call"]) if facing and a["pot_before"] > a["to_call"] else None),
            size_pot=a.get("size_pot"), n_active=active, n_flop=n_flop, ptype=ptype,
            is_pfr=(who == pfr), prev_aggr=(who == prev_street_aggr), prev_aggr_name=prev_street_aggr,
            bets_before=bets, checked_before=(who in checked), n_acted=len(acted_this_street),
            stack_bb=a["stack_before"] / bb, allin=bool(a.get("allin")), i=a["i"], dec=a.get("dec"),
            spr=(a["stack_before"] / a["pot_before"] if a["pot_before"] > 0 else None),
            bucket_dist=a.get("bucket_dist"), vs_hero=a.get("vs_hero"),
            street_aggr=street_aggr,
        )
        out.append(rec)
        acted_this_street.append(who)
        if a["act"] == "check":
            checked.add(who)
        if a["act"] == "raise":
            bets += 1
            street_aggr = who
    return out


def hero_ip_flags(h) -> dict:
    """For each street, whether hero is last to act among players active at street start."""
    out = {}
    hero = h["hero_name"]
    folded = set()
    cur = "preflop"
    alive_at = {}
    for a in h["actions"]:
        if a["street"] != cur:
            cur = a["street"]
            alive_at[cur] = [p["name"] for p in h["players"] if p["name"] not in folded]
        if a["act"] == "fold":
            folded.add(a["who"])
    for st, alive in alive_at.items():
        if hero in alive and len(alive) >= 2:
            order = postflop_order(h, alive)
            out[st] = order[-1] == hero
    return out


def size_bucket(frac: Optional[float]) -> str:
    if frac is None:
        return "?"
    if frac <= 0.40:
        return "≤40%"
    if frac <= 0.70:
        return "40-70%"
    if frac <= 1.05:
        return "70-105%"
    return ">105%"
