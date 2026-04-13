"""Monte Carlo equity calculator."""

from __future__ import annotations
import random
from typing import List
from pokerfate.core.card import Card
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

        base_remaining = [
            Card(r, s)
            for r in range(2, 15)
            for s in range(4)
            if Card(r, s) not in known_base
        ]

        valid = 0
        for _ in range(iterations):
            opp_hand = random.choice(opponent_range)
            if set(opp_hand) & known_base:
                continue

            opp_set = set(opp_hand)
            remaining = [c for c in base_remaining if c not in opp_set]

            if len(remaining) < board_needed:
                continue

            valid += 1
            run_board = board + random.sample(remaining, board_needed)
            my_score = HandEvaluator.evaluate(hole_cards + run_board)
            opp_score = HandEvaluator.evaluate(opp_hand + run_board)

            if my_score > opp_score:
                wins += 1
            elif my_score == opp_score:
                ties += 1

        if valid == 0:
            return 0.5
        return (wins + ties * 0.5) / valid

    @staticmethod
    def calculate_vs_top_range_multi(
        hole_cards: List[Card],
        board: List[Card],
        num_opponents: int,
        opponent_range_hands: List[List[Card]],
        iterations: int,
    ) -> float:
        """Monte Carlo equity vs `num_opponents`, each holding a hand from the same
        restricted range list (non-overlapping). Opponent hands are sampled first,
        then the board is completed from the remaining deck.

        Single-opponent delegates to :meth:`calculate_vs_range`.
        """
        if not opponent_range_hands or num_opponents < 1:
            return 0.5
        if num_opponents == 1:
            return EquityCalculator.calculate_vs_range(
                hole_cards, board, opponent_range_hands, iterations
            )

        wins = 0
        ties = 0
        valid = 0
        known_base = set(hole_cards) | set(board)
        board_needed = 5 - len(board)
        all_cards = [
            Card(r, s)
            for r in range(2, 15)
            for s in range(4)
        ]

        for _ in range(iterations):
            used = set(known_base)
            opp_hands: List[List[Card]] = []
            ok = True
            for _o in range(num_opponents):
                candidates = [h for h in opponent_range_hands if not (set(h) & used)]
                if not candidates:
                    ok = False
                    break
                h = random.choice(candidates)
                opp_hands.append(h)
                used |= set(h)
            if not ok:
                continue
            pool = [c for c in all_cards if c not in used]
            if len(pool) < board_needed:
                continue
            run_board = board + random.sample(pool, board_needed)
            valid += 1

            my_score = HandEvaluator.evaluate(hole_cards + run_board)
            opp_scores = [HandEvaluator.evaluate(h + run_board) for h in opp_hands]
            best_opp = max(opp_scores)
            if my_score > best_opp:
                wins += 1
            elif my_score == best_opp:
                ties += 1

        if valid == 0:
            return 0.5
        return (wins + ties * 0.5) / valid
