"""
PokerFate action_type mapping used by interceptor bridge.

Source of truth:
  - Semantic enum source (authoritative for numeric meaning):
      pf_reverse/output/lua/src/app/EnumConfig.lua
      lines 183-203: POKER_ACTION = { ... }
  - Proto schema only declares field type, not enum semantics:
      pf_reverse/output/proto/Proto/CSHoldem.proto
      lines 197-202: ActionREQ.action_type (int32)
      lines 209-216: ActionBRC.action_type (int32)

Notes:
  - These numeric values are game wire semantics used in ActionBRC.action_type
    and ActionREQ.action_type.
  - We map them to PokerFateAPI ActionEvent.action domain:
      "fold" | "check" | "call" | "raise"
  - Non-decision events (e.g. blinds/antes/wait/sited) are mapped to None so
    they won't be fed into opponent-model action history.
"""

from __future__ import annotations

# Full action_type map (same numeric space as client POKER_ACTION constants).
ACTION_TYPE_TO_EVENT_ACTION: dict[int, str | None] = {
    0: None,      # NONE
    1: "fold",    # FOLD
    2: "check",   # CHECK
    3: "call",    # CALL
    4: "raise",   # RAISE
    5: None,      # WAIT
    6: None,      # SITED
    7: "raise",   # BET (first aggressive action this street)
    8: None,      # SB (forced blind post)
    9: None,      # BB (forced blind post)
    10: None,     # ANTE (forced post)
    11: None,     # FORCE_BB (forced post)
    12: "fold",   # SYS_FOLD
    13: "check",  # SYS_CHECK
    14: None,     # STRADDLE (forced post)
    15: None,     # reserved / POT (commented out in current client enum)
    16: "fold",   # LEAVE_FOLD
    17: "raise",  # ALLIN
}

# Action types that represent "seat is folded / out of hand" state.
FOLD_ACTION_TYPES: set[int] = {1, 12, 16}

