"""Who acts when in one hand, and the position label that follows from it.

The server gives three facts that matter at the start of a hand: the seats
that are dealt in, the dealer seat and the big-blind seat. It then orders the
action by two rules. Both were checked against every hand in
``pf_intercept/logs/headless.log`` up to 2026-11-18, where the seat the server
asks to act next is in ``pb.ActionNotifyBRC``; neither has an exception:

  * before the flop the action goes clockwise (ascending seat number, wrapping)
    starting with the first dealt-in seat after the big blind, so the big
    blind acts last (20,680 of 20,680 hands);
  * after the flop it goes clockwise starting with the first seat after the
    dealer *seat*, whether or not anyone sits there (33,077 of 33,077
    streets).

Nothing else is assumed. In particular the dealer seat may be empty because
the player left (5.8% of hands), nobody may post the small blind (3.5%), a
new player who posted may be dealt in between the dealer and the small blind
(3.0%), and at a short table the dealer may post a blind himself.

A position label is a summary of those two orders, so it is derived from them
and not from where the dealer chip lies:

  * ``BB``  - the big-blind seat (last before the flop);
  * ``BTN`` - the seat that acts last after the flop (unless that is the BB);
  * ``SB``  - the seat that acts right before the big blind before the flop,
    unless it is the BTN (whenever someone posts the small blind it is this
    seat: 19,983 of 19,983 hands);
  * every other seat by how many seats still act behind it before the flop,
    counted back from those: ``CO``, ``MP``, then ``UTG``.

With two players this gives ``BTN``/``BB`` when the small blind acts last
after the flop (the usual case) and ``SB``/``BB`` when it acts first (dealer
seat empty or on the big blind). When the dealer posts the small blind at a
table of three or more he is the ``BTN`` and nobody is ``SB``. A seat dealt in
between the dealer and the small blind acts after the BTN before the flop and
first after it; no 6-max name describes that, so it takes the label of the
seat next to the button (``CO``), the tighter of its two neighbours.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, Optional, Tuple

# Seats that are neither blind nor BTN, counted back from the blinds.
_LABELS_BACK_FROM_BUTTON = ("CO", "MP")
_EARLY_LABEL = "UTG"


@dataclass(frozen=True)
class Seating:
    """Action order and position labels of one hand, keyed by seat number."""

    preflop_order: Tuple[int, ...]    # first to act ... big blind
    postflop_order: Tuple[int, ...]   # first to act ... last to act
    labels: Dict[int, str]

    @property
    def big_blind(self) -> Optional[int]:
        return self.preflop_order[-1] if len(self.preflop_order) >= 2 else None

    @property
    def button(self) -> Optional[int]:
        """Seat labelled BTN (last to act after the flop), if any."""
        for seat, label in self.labels.items():
            if label == "BTN":
                return seat
        return None


def clockwise_after(seats: Iterable[int], seat: int) -> Tuple[int, ...]:
    """Dealt-in seats in clockwise order, starting right after ``seat``.

    ``seat`` itself, when it is dealt in, comes last.
    """
    ordered = sorted({int(s) for s in seats})
    pivot = int(seat)
    return tuple(s for s in ordered if s > pivot) + tuple(s for s in ordered if s <= pivot)


def standard_blind_seats(seats: Iterable[int], dealer: int) -> Tuple[Optional[int], Optional[int]]:
    """Blind seats of an undisturbed table: the two seats after the dealer.

    Heads-up the dealer posts the small blind. Used when the server did not
    say who posts (a hand rebuilt from a table snapshot) and to tell whether
    the layout it did send is the ordinary one.
    """
    after = clockwise_after(seats, dealer)
    if len(after) < 2:
        return None, None
    if len(after) == 2 and int(dealer) in after:
        return int(dealer), after[0]
    return after[0], after[1]


def derive_seating(
    seats: Iterable[int],
    dealer: int,
    big_blind: Optional[int] = None,
) -> Seating:
    """Action order and labels for the dealt-in ``seats``.

    ``big_blind`` is the seat the server named; pass ``None`` when it named
    no blinds (a hand rebuilt from a table snapshot), and the undisturbed
    layout is assumed.
    """
    dealt = tuple(sorted({int(s) for s in seats}))
    if not dealt:
        return Seating((), (), {})
    if len(dealt) == 1:
        return Seating(dealt, dealt, {dealt[0]: "BTN"})

    if big_blind is not None and int(big_blind) in dealt:
        bb = int(big_blind)
    else:
        bb = standard_blind_seats(dealt, dealer)[1]

    preflop = clockwise_after(dealt, bb)
    postflop = clockwise_after(dealt, dealer)

    labels: Dict[int, str] = {bb: "BB"}
    if postflop[-1] != bb:
        labels[postflop[-1]] = "BTN"
    before_bb = preflop[-2]
    if before_bb not in labels:
        labels[before_bb] = "SB"
    rest = [seat for seat in preflop if seat not in labels]
    for back, seat in enumerate(reversed(rest)):
        labels[seat] = (
            _LABELS_BACK_FROM_BUTTON[back]
            if back < len(_LABELS_BACK_FROM_BUTTON)
            else _EARLY_LABEL
        )
    return Seating(preflop, postflop, labels)
