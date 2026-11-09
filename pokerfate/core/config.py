"""Shared runtime configuration for bot + strategy layers.

Magic numbers that were previously duplicated across modules live here so a
single edit propagates everywhere. Keep this file free of imports from
higher-level packages (bot/, strategy/) to avoid circular imports.
"""


# ── Opponent-model sample thresholds ─────────────────────────────────────────
# Minimum hands before opponent statistics are trusted by exploit helpers:
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


# ── Table rake ───────────────────────────────────────────────────────────────
# Measured from live hand results (2026-11): the site takes 9% of the final
# pot, with no cap, on every pot including ones that end preflop. Uncalled
# bets are returned before rake is applied.
#
# Every EV / pot-odds formula in the strategy layer must use these helpers so
# "win the pot" is worth RAKE_KEEP × pot, never the full pot. Set RAKE_RATE
# to 0.0 for a rake-free game.
RAKE_RATE: float = 0.09
# Rake cap in big blinds. 0.0 means "no cap" (the live game is uncapped).
RAKE_CAP_BB: float = 0.0
RAKE_KEEP: float = 1.0 - RAKE_RATE


def rake_keep(pot_bb: float = 0.0) -> float:
    """Fraction of ``pot`` the winner keeps after rake.

    With a cap the effective rate falls for big pots; without a cap it is the
    flat ``RAKE_KEEP``.
    """
    if RAKE_RATE <= 0.0:
        return 1.0
    if RAKE_CAP_BB > 0.0 and pot_bb > 0.0:
        return 1.0 - min(RAKE_RATE, RAKE_CAP_BB / pot_bb)
    return RAKE_KEEP


def required_equity(call_amount: float, pot_before_call: float, pot_bb: float = 0.0) -> float:
    """Break-even showdown equity for a call once rake is taken from the pot.

    ``pot_before_call`` already contains the opponent's bet. The call wins
    ``(pot_before_call + call_amount) × keep`` and loses ``call_amount``::

        eq × (P + C) × keep − C = 0  →  eq = C / ((P + C) × keep)
    """
    if call_amount <= 0.0:
        return 0.0
    total = pot_before_call + call_amount
    if total <= 0.0:
        return 1.0
    return min(1.0, call_amount / (total * rake_keep(pot_bb)))
