"""Seat order and position labels derived from the server's hand-start facts.

Every layout here occurs in the live wire log; the expected orders are the
ones the server actually used (clockwise after the big blind before the flop,
clockwise after the dealer seat after it).
"""

import pytest

from pokerfate.core.position import relabel_positions_by_button
from pokerfate.core.seating import clockwise_after, derive_seating, standard_blind_seats


def test_clockwise_after_wraps_and_puts_the_seat_itself_last():
    assert clockwise_after([0, 1, 3, 5], 3) == (5, 0, 1, 3)
    assert clockwise_after([0, 1, 3, 5], 4) == (5, 0, 1, 3)
    assert clockwise_after([0, 1, 3, 5], 5) == (0, 1, 3, 5)


@pytest.mark.parametrize(
    "seats, dealer, big_blind, expected",
    [
        # full table
        ([0, 1, 2, 3, 4, 5], 2, 4, {2: "BTN", 3: "SB", 4: "BB", 5: "UTG", 0: "MP", 1: "CO"}),
        # five, four and three handed: the seats before the button keep their distance to it
        ([0, 1, 2, 3, 4], 0, 2, {0: "BTN", 1: "SB", 2: "BB", 3: "MP", 4: "CO"}),
        ([1, 2, 4, 5], 5, 2, {5: "BTN", 1: "SB", 2: "BB", 4: "CO"}),
        ([0, 2, 5], 2, 0, {2: "BTN", 5: "SB", 0: "BB"}),
        # more than six: everything earlier than MP is UTG
        ([0, 1, 2, 3, 4, 5, 6, 7], 7, 1, {7: "BTN", 0: "SB", 1: "BB", 2: "UTG", 3: "UTG", 4: "UTG", 5: "MP", 6: "CO"}),
    ],
)
def test_ordinary_tables(seats, dealer, big_blind, expected):
    assert derive_seating(seats, dealer, big_blind).labels == expected


def test_orders_follow_the_big_blind_and_the_dealer_seat():
    s = derive_seating([0, 1, 2, 3, 4, 5], dealer=2, big_blind=4)
    assert s.preflop_order == (5, 0, 1, 2, 3, 4)
    assert s.postflop_order == (3, 4, 5, 0, 1, 2)
    assert s.big_blind == 4 and s.button == 2


def test_empty_dealer_seat_makes_the_last_seat_before_the_blinds_the_button():
    """2026-11-18 hand 343: dealer chip on empty seat 3; hero in seat 0 acts first
    before the flop and was labelled BTN because he had the lowest seat number."""
    s = derive_seating([0, 1, 2, 4, 5], dealer=3, big_blind=5)
    assert s.preflop_order == (0, 1, 2, 4, 5)
    assert s.postflop_order == (4, 5, 0, 1, 2)
    assert s.labels == {0: "MP", 1: "CO", 2: "BTN", 4: "SB", 5: "BB"}


def test_empty_dealer_seat_does_not_depend_on_seat_numbers():
    # same table shape, the empty dealer seat sits at different places in the numbering
    assert derive_seating([1, 2, 3, 4], dealer=0, big_blind=2).labels == {1: "SB", 2: "BB", 3: "CO", 4: "BTN"}
    assert derive_seating([0, 1, 2, 4], dealer=3, big_blind=0).labels == {4: "SB", 0: "BB", 1: "CO", 2: "BTN"}
    assert derive_seating([0, 1, 2, 3], dealer=5, big_blind=1).labels == {0: "SB", 1: "BB", 2: "CO", 3: "BTN"}


def test_heads_up_small_blind_on_the_button():
    s = derive_seating([1, 4], dealer=4, big_blind=1)
    assert s.preflop_order == (4, 1)          # the button acts first before the flop
    assert s.postflop_order == (1, 4)         # and last after it
    assert s.labels == {4: "BTN", 1: "BB"}


def test_heads_up_empty_dealer_seat_small_blind_last_after_the_flop():
    # dealer chip on empty seat 0, big blind in seat 1: seat 4 posts the small blind and still acts last
    s = derive_seating([1, 4], dealer=0, big_blind=1)
    assert s.postflop_order == (1, 4)
    assert s.labels == {4: "BTN", 1: "BB"}


def test_heads_up_small_blind_out_of_position_is_a_blind_battle():
    # dealer chip on empty seat 0, big blind in seat 4: seat 1 acts first on every street
    s = derive_seating([1, 4], dealer=0, big_blind=4)
    assert s.preflop_order == (1, 4) and s.postflop_order == (1, 4)
    assert s.labels == {1: "SB", 4: "BB"}
    # dealer chip on the big blind: same thing
    assert derive_seating([1, 4], dealer=4, big_blind=4).labels == {1: "SB", 4: "BB"}


def test_nobody_posts_the_small_blind():
    # small-blind seat 3 is empty: the dealer acts right before the big blind and stays the button
    s = derive_seating([0, 1, 2, 4], dealer=2, big_blind=4)
    assert s.preflop_order == (0, 1, 2, 4)
    assert s.labels == {4: "BB", 2: "BTN", 1: "CO", 0: "MP"}


def test_dealer_posting_the_small_blind_at_three_or_more_is_the_button():
    # 2026-11-07 01:00:45: dealer 0 posts the small blind, big blind 2, seats 3 and 4 just sat down
    s = derive_seating([0, 2, 3, 4], dealer=0, big_blind=2)
    assert s.preflop_order == (3, 4, 0, 2)
    assert s.postflop_order == (2, 3, 4, 0)
    assert s.labels == {2: "BB", 0: "BTN", 4: "CO", 3: "MP"}


def test_new_player_between_dealer_and_small_blind():
    # 2026-11-06 20:52:25: dealer 3, small blind 0, big blind 1; seat 4 posted to play at once
    s = derive_seating([0, 1, 2, 3, 4], dealer=3, big_blind=1)
    assert s.preflop_order == (2, 3, 4, 0, 1)   # seat 4 acts after the dealer
    assert s.postflop_order == (4, 0, 1, 2, 3)  # and first after the flop
    assert s.labels == {1: "BB", 3: "BTN", 0: "SB", 4: "CO", 2: "MP"}


def test_blinds_not_named_assumes_the_undisturbed_layout():
    assert standard_blind_seats([0, 2, 5], 2) == (5, 0)
    assert standard_blind_seats([1, 4], 4) == (4, 1)
    assert standard_blind_seats([1, 4], 0) == (1, 4)
    assert derive_seating([0, 2, 5], dealer=2).labels == {2: "BTN", 5: "SB", 0: "BB"}
    assert derive_seating([1, 4], dealer=4).labels == {4: "BTN", 1: "BB"}
    # a named big blind that is not dealt in cannot be right; fall back the same way
    assert derive_seating([0, 2, 5], dealer=2, big_blind=3).labels == {2: "BTN", 5: "SB", 0: "BB"}


def test_degenerate_tables():
    assert derive_seating([], dealer=0).labels == {}
    assert derive_seating([3], dealer=0).labels == {3: "BTN"}


@pytest.mark.parametrize("n", [2, 3, 4, 5, 6, 7, 8, 9])
@pytest.mark.parametrize("dealer_offset", [0, 1])
def test_labels_are_stable_under_the_api_relabel(n, dealer_offset):
    """`PokerFateAPI.new_hand` relabels once more; it must leave these labels alone."""
    seats = list(range(n))
    dealer = (n - 1) + dealer_offset          # last seat, or an empty seat after it
    labels = derive_seating(seats, dealer, big_blind=1 if dealer_offset else None).labels
    assert relabel_positions_by_button(labels) == labels
    assert set(labels) == set(seats)
    assert list(labels.values()).count("BB") == 1
    assert list(labels.values()).count("BTN") <= 1
