"""Shared runtime configuration for bot + strategy layers.

Magic numbers that were previously duplicated across modules live here so a
single edit propagates everywhere. Keep this file free of imports from
higher-level packages (bot/, strategy/) to avoid circular imports.
"""


# ── Opponent-model sample thresholds ─────────────────────────────────────────
# Minimum hands before we stop treating an opponent as "unknown":
#   - player_type() returns 'unknown' below this
#   - pwi() returns 0 below this
#   - exploit_adjustments() returns {} below this
#   - range_v2 prior blending uses GTO defaults below this
#   - range_v2 polarization_index returns mid (0.5) below this
#   - logger tag prints "数据不足N手" below this
#
# 2026-04-21: dropped from 20 → 10 so short-sample opponents get partial
# exploit coverage earlier. Below ~10 hands the stats are dominated by
# initial-position noise; above that they carry signal.
MIN_HANDS_FOR_CLASSIFICATION: int = 10
