"""Monte Carlo equity calculator."""

from __future__ import annotations
import random
from typing import List, Optional
from pokerfate.core.card import Card
from pokerfate.core.hand_evaluator import HandEvaluator


class EquityCalculator:
    @staticmethod
    def calculate(
        hole_cards: List[Card],
        board: List[Card],
        num_opponents: int = 1,
        iterations: int = 5000,
        seed: Optional[int] = None,
        rng: Optional[random.Random] = None,
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

        local_rng = rng if rng is not None else random.Random(seed)

        for _ in range(iterations):
            sample = local_rng.sample(remaining_deck, board_needed + num_opponents * 2)
            run_board = board + sample[:board_needed]
            opp_hands = [
                sample[board_needed + i * 2: board_needed + i * 2 + 2]
                for i in range(num_opponents)
            ]

            my_score = HandEvaluator.eval_int(hole_cards + run_board)
            opp_scores = [HandEvaluator.eval_int(h + run_board) for h in opp_hands]

            best_opp = max(opp_scores)
            if my_score > best_opp:
                wins += 1
            elif my_score == best_opp:
                ties += 1

        return (wins + ties * 0.5) / iterations
