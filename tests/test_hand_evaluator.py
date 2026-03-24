"""Tests for the hand evaluator."""

import pytest
from pokerfate.core.card import Card
from pokerfate.core.hand_evaluator import HandEvaluator, HandRank


def cards(*strs):
    return [Card.from_str(s) for s in strs]


class TestHandRanking:
    def test_royal_flush(self):
        hand = cards('As', 'Ks', 'Qs', 'Js', 'Ts')
        score = HandEvaluator.evaluate(hand)
        assert score[0] == HandRank.ROYAL_FLUSH

    def test_straight_flush(self):
        hand = cards('9h', '8h', '7h', '6h', '5h')
        score = HandEvaluator.evaluate(hand)
        assert score[0] == HandRank.STRAIGHT_FLUSH
        assert score[1] == 9

    def test_four_of_a_kind(self):
        hand = cards('Ac', 'Ad', 'Ah', 'As', '2c')
        score = HandEvaluator.evaluate(hand)
        assert score[0] == HandRank.FOUR_OF_A_KIND
        assert score[1] == 14  # Aces

    def test_full_house(self):
        hand = cards('Kc', 'Kd', 'Kh', '7s', '7c')
        score = HandEvaluator.evaluate(hand)
        assert score[0] == HandRank.FULL_HOUSE
        assert score[1] == 13  # Kings full

    def test_flush(self):
        hand = cards('Ac', 'Jc', '9c', '5c', '2c')
        score = HandEvaluator.evaluate(hand)
        assert score[0] == HandRank.FLUSH

    def test_straight(self):
        hand = cards('8c', '7d', '6h', '5s', '4c')
        score = HandEvaluator.evaluate(hand)
        assert score[0] == HandRank.STRAIGHT
        assert score[1] == 8

    def test_wheel_straight(self):
        hand = cards('Ac', '2d', '3h', '4s', '5c')
        score = HandEvaluator.evaluate(hand)
        assert score[0] == HandRank.STRAIGHT
        assert score[1] == 5  # Five-high straight

    def test_three_of_a_kind(self):
        hand = cards('Qc', 'Qd', 'Qh', '8s', '3c')
        score = HandEvaluator.evaluate(hand)
        assert score[0] == HandRank.THREE_OF_A_KIND
        assert score[1] == 12

    def test_two_pair(self):
        hand = cards('Jc', 'Jd', '9h', '9s', 'Ac')
        score = HandEvaluator.evaluate(hand)
        assert score[0] == HandRank.TWO_PAIR

    def test_one_pair(self):
        hand = cards('8c', '8d', 'Ah', 'Ks', '2c')
        score = HandEvaluator.evaluate(hand)
        assert score[0] == HandRank.ONE_PAIR
        assert score[1] == 8

    def test_high_card(self):
        hand = cards('Ac', 'Kd', 'Qh', 'Js', '9c')
        score = HandEvaluator.evaluate(hand)
        assert score[0] == HandRank.HIGH_CARD

    def test_7_card_best_hand(self):
        # 7 cards with a flush hiding inside
        hand = cards('Ac', 'Kc', 'Qc', 'Jc', 'Tc', '2d', '7h')
        score = HandEvaluator.evaluate(hand)
        assert score[0] == HandRank.ROYAL_FLUSH

    def test_ranking_order(self):
        rf = HandEvaluator.evaluate(cards('As', 'Ks', 'Qs', 'Js', 'Ts'))
        sf = HandEvaluator.evaluate(cards('9h', '8h', '7h', '6h', '5h'))
        foak = HandEvaluator.evaluate(cards('Ac', 'Ad', 'Ah', 'As', '2c'))
        fh = HandEvaluator.evaluate(cards('Kc', 'Kd', 'Kh', '7s', '7c'))
        flush = HandEvaluator.evaluate(cards('Ac', 'Jc', '9c', '5c', '2c'))
        straight = HandEvaluator.evaluate(cards('8c', '7d', '6h', '5s', '4c'))
        toak = HandEvaluator.evaluate(cards('Qc', 'Qd', 'Qh', '8s', '3c'))
        two_pair = HandEvaluator.evaluate(cards('Jc', 'Jd', '9h', '9s', 'Ac'))
        one_pair = HandEvaluator.evaluate(cards('8c', '8d', 'Ah', 'Ks', '2c'))
        high = HandEvaluator.evaluate(cards('Ac', 'Kd', 'Qh', 'Js', '9c'))

        assert rf > sf > foak > fh > flush > straight > toak > two_pair > one_pair > high

    def test_compare(self):
        a = HandEvaluator.evaluate(cards('As', 'Ks', 'Qs', 'Js', 'Ts'))
        b = HandEvaluator.evaluate(cards('9h', '8h', '7h', '6h', '5h'))
        assert HandEvaluator.compare(a, b) == 1
        assert HandEvaluator.compare(b, a) == -1
        assert HandEvaluator.compare(a, a) == 0

    def test_kicker_breaks_tie(self):
        # Same pair, different kickers
        hand_a = HandEvaluator.evaluate(cards('Ac', 'Ad', 'Kh', 'Qs', 'Jc'))
        hand_b = HandEvaluator.evaluate(cards('Ac', 'Ad', 'Kh', 'Qs', '9c'))
        assert hand_a > hand_b
