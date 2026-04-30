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
