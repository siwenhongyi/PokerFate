"""Position normalization to 6-max canonical set.

Shared single source of truth for mapping raw position strings
(from `game_state.position_of()`, upstream proto `PlayerInfo.position`,
9-max aliases like `UTG+1`, `LJ`, `HJ`, `BU`, etc.) to the 6-max
canonical set used by:
  - preflop 3bet/4bet sizing matrices
  - preflop bluff-3bet frequency tables
  - preflop 3bet-defend call ranges
  - GTO chart lookup keys

Canonical set: {UTG, MP, CO, BTN, SB, BB}.

Previously the mapping lived in two places with subtly different keys:
`poker_bot._POS_NORMALIZE` (no BU, `.get(raw, raw)` passthrough) and
`core.position.POS_CANONICAL_6MAX` (BU + more aliases, warn-on-unknown).
Review 04_bot_api_preflop §S2 flagged the duplication — this module
is the fix.
"""

from __future__ import annotations

import logging
from typing import Dict

_log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Canonical map
#
# Covers the 10 values emitted by `GameState.position_of()`
# ({UTG, UTG+1, UTG+2, LJ, HJ, CO, BTN, SB, BB, MP}) plus common aliases
# from upstream protocols (`UTG1`, `UTG-1`, `UTG-2`, `UTG2`, `BU`).
# ---------------------------------------------------------------------------
POS_CANONICAL_6MAX: Dict[str, str] = {
    'UTG': 'UTG',
    'UTG+1': 'MP', 'UTG1': 'MP', 'UTG-1': 'MP',
    'UTG+2': 'CO', 'UTG2': 'CO', 'UTG-2': 'CO',
    'LJ': 'MP',
    'HJ': 'CO',
    'MP': 'MP',
    'CO': 'CO',
    'BTN': 'BTN', 'BU': 'BTN',
    'SB': 'SB',
    'BB': 'BB',
}


def normalize_position(raw: str, default: str = '', *, warn: bool = True) -> str:
    """Map `raw` to 6-max canonical.

    Returns `default` for empty / unmapped input. When `warn=True`, also
    logs a WARN on an unmapped non-empty input — that signals an upstream
    regression (new alias, typo, stale proto field) we want to catch.

    Callers:
      - preflop: `normalize_position(raw, default='')` — strict; '' triggers
        IP/OOP sizing fallback and skips position-specific tables.
      - poker_bot chart lookup: `normalize_position(raw, default=raw, warn=False)`
        — passthrough on miss so we don't silently rewrite the chart key
        (the chart will just return no match, which the caller already
        handles gracefully).
    """
    if not raw:
        return default
    key = raw.strip()
    norm = POS_CANONICAL_6MAX.get(key)
    if norm is None:
        if warn:
            _log.warning("core.position.normalize_position: unknown position %r", raw)
        return default
    return norm


# ---------------------------------------------------------------------------
# Button-relative relabelling for short-handed tables
#
# Upstream labels (pf_intercept bridge `_seat_positions`, `GameState.
# position_of`) count the seats after the BB *forwards*: 'UTG', 'UTG+1',
# 'UTG+2', 'LJ', 'HJ', 'CO'. Every consumer of a position — the greenline /
# PokerGTO chart keys, `_POSITION_RANGES`, 3bet/4bet matrices, the Range V2
# preflop priors (GTO_VPIP/GTO_PFR), the flop-book scenario and the hero reach
# range — is keyed on 6-max positions counted *backwards* from the button
# (UTG, MP, CO, BTN). The two agree only at a full 6-handed table. 4-handed
# the single seat between BB and BTN is labelled 'UTG' although it is the CO;
# 5-handed 'UTG'/'UTG+1' are really MP/CO. `preflop._SHORT_HAND_POSITION`
# patched this for `in_open_range` only, so the chart lookups that run first
# still used the forward label (2026-11-07..09 logs: 863 preflop chart
# lookups keyed on the wrong seat, 76 with a different primary action).
#
# `relabel_positions_by_button` is applied once per hand in
# `PokerFateAPI.new_hand`, so every downstream consumer sees the same
# button-relative label. Blinds and BTN are untouched; the mapping is
# idempotent on canonical labels.
# ---------------------------------------------------------------------------
_FORWARD_LABEL_ORDER: Dict[str, int] = {
    'UTG': 0,
    'UTG+1': 1, 'UTG1': 1, 'UTG-1': 1,
    'UTG+2': 2, 'UTG2': 2, 'UTG-2': 2, 'MP': 2,
    'LJ': 3,
    'HJ': 4,
    'CO': 5,
}


def relabel_positions_by_button(positions: Dict[int, str]) -> Dict[int, str]:
    """Map forward-counted seat labels to button-relative 6-max labels.

    The seat right before the BTN becomes 'CO', the one before that 'MP', and
    every earlier seat 'UTG'. Labels that are not forward seat labels (BTN,
    SB, BB, '' or unknown strings) are returned unchanged.
    """
    forward = [
        (pid, str(label or '').strip())
        for pid, label in positions.items()
        if str(label or '').strip() in _FORWARD_LABEL_ORDER
    ]
    out = dict(positions)
    if not forward:
        return out
    forward.sort(key=lambda item: _FORWARD_LABEL_ORDER[item[1]])
    seats = len(forward)
    for idx, (pid, _label) in enumerate(forward):
        dist_to_btn = seats - idx
        if dist_to_btn == 1:
            out[pid] = 'CO'
        elif dist_to_btn == 2:
            out[pid] = 'MP'
        else:
            out[pid] = 'UTG'
    return out
