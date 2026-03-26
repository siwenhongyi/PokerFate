"""Monte Carlo equity calculator."""

from __future__ import annotations
import random
from typing import List, Optional
from pokerfate.core.card import Card, Deck
from pokerfate.core.hand_evaluator import HandEvaluator


class EquityCalculator:
    @staticmethod
    def calculate(
        hole_cards: List[Card],
        board: List[Card],
        num_opponents: int = 1,
        iterations: int = 5000,
    ) -> float:
        """Estimate win equity via Monte Carlo simulation.

        Returns win probability [0.0, 1.0] for hole_cards vs num_opponents
        random opponents given the current board.
        """
        wins = 0
        ties = 0
        known = set(hole_cards) | set(board)
        remaining_deck = [
            Card(r, s)
            for r in range(2, 15)
            for s in range(4)
            if Card(r, s) not in known
        ]

        board_needed = 5 - len(board)

        for _ in range(iterations):
            sample = random.sample(remaining_deck, board_needed + num_opponents * 2)
            run_board = board + sample[:board_needed]
            opp_hands = [
                sample[board_needed + i * 2: board_needed + i * 2 + 2]
                for i in range(num_opponents)
            ]

            my_score = HandEvaluator.evaluate(hole_cards + run_board)
            opp_scores = [HandEvaluator.evaluate(h + run_board) for h in opp_hands]

            best_opp = max(opp_scores)
            if my_score > best_opp:
                wins += 1
            elif my_score == best_opp:
                ties += 1

        return (wins + ties * 0.5) / iterations

    @staticmethod
    def calculate_vs_range(
        hole_cards: List[Card],
        board: List[Card],
        opponent_range: List[List[Card]],
        iterations: int = 2000,
    ) -> float:
        """Estimate equity vs a specific hand range (list of 2-card hands)."""
        if not opponent_range:
            return 0.5

        wins = 0
        ties = 0
        known_base = set(hole_cards) | set(board)
        board_needed = 5 - len(board)

        for _ in range(iterations):
            opp_hand = random.choice(opponent_range)
            if set(opp_hand) & known_base:
                continue

            known = known_base | set(opp_hand)
            remaining = [
                Card(r, s)
                for r in range(2, 15)
                for s in range(4)
                if Card(r, s) not in known
            ]

            if len(remaining) < board_needed:
                continue

            run_board = board + random.sample(remaining, board_needed)
            my_score = HandEvaluator.evaluate(hole_cards + run_board)
            opp_score = HandEvaluator.evaluate(opp_hand + run_board)

            if my_score > opp_score:
                wins += 1
            elif my_score == opp_score:
                ties += 1

        total = wins + ties
        if total == 0:
            return 0.5
        return (wins + ties * 0.5) / iterations

    @staticmethod
    def outs_to_equity(outs: int, cards_to_come: int) -> float:
        """Rule of 2 and 4 approximation."""
        multiplier = 4 if cards_to_come == 2 else 2
        return min(outs * multiplier / 100.0, 0.99)
