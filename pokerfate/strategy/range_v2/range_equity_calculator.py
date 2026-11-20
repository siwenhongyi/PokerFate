"""Weighted equity calculation against opponent's range distribution.

Instead of enumerating all combos, we sample from the 1326-dim weight
vector proportional to probability — fixed O(n_samples) cost.

Reference: Pluribus importance sampling for belief-weighted equity.
"""

from __future__ import annotations

from typing import List, Optional

import numpy as np

from pokerfate.core.card import Card
from pokerfate.core.hand_evaluator import HandEvaluator
from pokerfate.strategy.range_v2 import hand_combo_map as hcm


class RangeEquityCalculator:
    """Compute equity of my hand against opponent's weighted range."""

    @staticmethod
    def weighted_equity(
        my_hand: List[Card],
        board: List[Card],
        opp_weights: np.ndarray,
        num_opponents: int = 1,
        n_samples: int = 2000,
        seed: Optional[int] = None,
        rng: Optional[np.random.Generator] = None,
    ) -> float:
        """Compute E[equity | opponent_range].

        For each sample:
          1. Draw opponent combo from weight distribution
          2. Complete the board randomly (if not river)
          3. Compare hands

        Multi-opponent: each opponent sampled independently (non-overlapping).
        """
        # Card removal: zero out combos conflicting with known cards
        known_ints = {hcm.card_to_int(c) for c in my_hand + board}
        valid = opp_weights.copy()
        valid[hcm.blocked_by(known_ints)] = 0.0

        total = valid.sum()
        if total < 1e-15:
            return 0.5

        valid /= total

        board_needed = 5 - len(board)
        is_river = board_needed == 0
        np_rng = rng if rng is not None else np.random.default_rng(seed)

        # Full deck minus known cards
        deck = [i for i in range(52) if i not in known_ints]

        # River + heads-up: exact enumeration (deterministic, zero MC variance).
        # Iterate every non-zero combo once, weight win/tie by combo probability.
        if is_river and num_opponents <= 1:
            my_score = HandEvaluator.eval_int(list(my_hand) + list(board))
            win_w = 0.0
            tie_w = 0.0
            nz = np.flatnonzero(valid)
            board_l = list(board)
            for idx in nz:
                c1, c2 = hcm.ALL_COMBOS[idx]
                opp_cards = [hcm.int_to_card(c1), hcm.int_to_card(c2)]
                opp_score = HandEvaluator.eval_int(opp_cards + board_l)
                w = float(valid[idx])
                if my_score > opp_score:
                    win_w += w
                elif my_score == opp_score:
                    tie_w += w
            return win_w + tie_w * 0.5

        wins = 0
        ties = 0

        if num_opponents <= 1:
            # Single opponent — simple sampling
            sampled = np_rng.choice(1326, size=n_samples, replace=True, p=valid)

            for idx in sampled:
                c1, c2 = hcm.ALL_COMBOS[idx]
                opp_cards = [hcm.int_to_card(c1), hcm.int_to_card(c2)]

                if is_river:
                    my_score = HandEvaluator.eval_int(list(my_hand) + list(board))
                    opp_score = HandEvaluator.eval_int(opp_cards + list(board))
                else:
                    opp_ints = {c1, c2}
                    avail = [c for c in deck if c not in opp_ints]
                    if len(avail) < board_needed:
                        continue
                    runout = np_rng.choice(avail, size=board_needed, replace=False).tolist()
                    full_board = list(board) + [hcm.int_to_card(r) for r in runout]
                    my_score = HandEvaluator.eval_int(list(my_hand) + full_board)
                    opp_score = HandEvaluator.eval_int(opp_cards + full_board)

                if my_score > opp_score:
                    wins += 1
                elif my_score == opp_score:
                    ties += 1
        else:
            # Multi-opponent: sample each independently, skip overlaps
            valid_count = 0
            for _ in range(n_samples):
                used_ints = set(known_ints)
                opp_hands = []
                ok = True
                for _o in range(num_opponents):
                    # Mask out used cards
                    w_copy = valid.copy()
                    w_copy[hcm.blocked_by(used_ints - known_ints)] = 0.0
                    s = w_copy.sum()
                    if s < 1e-15:
                        ok = False
                        break
                    w_copy /= s
                    idx = int(np_rng.choice(1326, p=w_copy))
                    c1, c2 = hcm.ALL_COMBOS[idx]
                    opp_hands.append([hcm.int_to_card(c1), hcm.int_to_card(c2)])
                    used_ints.add(c1)
                    used_ints.add(c2)

                if not ok:
                    continue

                avail = [c for c in range(52) if c not in used_ints]
                if len(avail) < board_needed:
                    continue

                if is_river:
                    full_board = list(board)
                else:
                    runout = np_rng.choice(avail, size=board_needed, replace=False).tolist()
                    full_board = list(board) + [hcm.int_to_card(r) for r in runout]

                valid_count += 1
                my_score = HandEvaluator.eval_int(list(my_hand) + full_board)
                opp_scores = [HandEvaluator.eval_int(h + full_board) for h in opp_hands]
                best_opp = max(opp_scores)
                if my_score > best_opp:
                    wins += 1
                elif my_score == best_opp:
                    ties += 1

            if valid_count == 0:
                return 0.5
            return (wins + ties * 0.5) / valid_count

        return (wins + ties * 0.5) / n_samples

    @staticmethod
    def weighted_equity_multi(
        my_hand: List[Card],
        board: List[Card],
        opponent_weights_list: List[np.ndarray],
        n_samples: int = 2000,
        seed: Optional[int] = None,
        rng: Optional[np.random.Generator] = None,
    ) -> float:
        """Compute equity vs multiple opponents, each with their OWN range.

        Unlike weighted_equity with num_opponents>1 (which uses ONE range for
        all opponents), this uses a DIFFERENT 1326-dim distribution per
        opponent — correct when each opponent has a different action
        history and therefore a different estimated range.
        """
        if not opponent_weights_list:
            return 0.5

        if len(opponent_weights_list) == 1:
            return RangeEquityCalculator.weighted_equity(
                my_hand, board, opponent_weights_list[0], 1, n_samples,
                seed=seed, rng=rng,
            )

        known_ints = {hcm.card_to_int(c) for c in my_hand + board}
        board_needed = 5 - len(board)
        is_river = board_needed == 0
        np_rng = rng if rng is not None else np.random.default_rng(seed)

        # Pre-normalize each opponent's weights against the known cards.
        valid_list = []
        for opp_w in opponent_weights_list:
            v = opp_w.copy()
            v[hcm.blocked_by(known_ints)] = 0.0
            s = v.sum()
            if s > 1e-15:
                v /= s
            else:
                v = np.ones(1326, dtype=np.float64)
                v[hcm.blocked_by(known_ints)] = 0.0
                s = v.sum()
                if s > 0:
                    v /= s
            valid_list.append(v)

        wins = 0
        ties = 0
        valid_count = 0

        for _ in range(n_samples):
            used_ints = set(known_ints)
            opp_hands = []
            ok = True

            for opp_v in valid_list:
                w_copy = opp_v.copy()
                extra_blocked = used_ints - known_ints
                if extra_blocked:
                    w_copy[hcm.blocked_by(extra_blocked)] = 0.0
                s = w_copy.sum()
                if s < 1e-15:
                    ok = False
                    break
                w_copy /= s
                idx = int(np_rng.choice(1326, p=w_copy))
                c1, c2 = hcm.ALL_COMBOS[idx]
                opp_hands.append([hcm.int_to_card(c1), hcm.int_to_card(c2)])
                used_ints.add(c1)
                used_ints.add(c2)

            if not ok:
                continue

            avail = [c for c in range(52) if c not in used_ints]
            if len(avail) < board_needed:
                continue

            if is_river:
                full_board = list(board)
            else:
                runout = np_rng.choice(avail, size=board_needed, replace=False).tolist()
                full_board = list(board) + [hcm.int_to_card(r) for r in runout]

            valid_count += 1
            my_score = HandEvaluator.eval_int(list(my_hand) + full_board)
            opp_scores = [HandEvaluator.eval_int(h + full_board) for h in opp_hands]
            best_opp = max(opp_scores)
            if my_score > best_opp:
                wins += 1
            elif my_score == best_opp:
                ties += 1

        if valid_count == 0:
            return 0.5
        return (wins + ties * 0.5) / valid_count

    # Fewer behind-samples than this and the conditional equity is too noisy to use.
    _MIN_BEHIND_SAMPLES = 100

    @staticmethod
    def equity_when_behind(
        my_hand: List[Card],
        board: List[Card],
        opponent_weights_list: List[np.ndarray],
        n_samples: int = 2000,
        seed: Optional[int] = None,
        rng: Optional[np.random.Generator] = None,
    ) -> Optional[float]:
        """Hero's equity given that some opponent holds a hand that beats his right now.

        A range estimate can be wrong about how often the opponents are ahead,
        but not by more than "always". This is the equity in that worst case:
        the chance that the cards still to come turn the hand around, weighted
        over the hands in the opponents' ranges that are ahead on the present
        board. A bluff-catcher gets a low number here, a draw to the best hand
        nearly its whole equity.

        Returns ``None`` on the river (nothing to come), without ranges, or
        when the opponents are ahead too rarely to measure it.
        """
        board_needed = 5 - len(board)
        if board_needed <= 0 or len(board) < 3 or not opponent_weights_list:
            return None

        known_ints = {hcm.card_to_int(c) for c in my_hand + board}
        np_rng = rng if rng is not None else np.random.default_rng(seed)
        valid_list = []
        for opp_w in opponent_weights_list:
            v = opp_w.copy()
            v[hcm.blocked_by(known_ints)] = 0.0
            total = v.sum()
            if total < 1e-15:
                return None
            valid_list.append(v / total)

        my_hand_l = list(my_hand)
        board_l = list(board)
        my_now = HandEvaluator.eval_int(my_hand_l + board_l)
        single = valid_list[0] if len(valid_list) == 1 else None
        sampled = np_rng.choice(1326, size=n_samples, replace=True, p=single) if single is not None else None

        behind = 0
        wins = 0.0
        for i in range(n_samples):
            used_ints = set(known_ints)
            opp_hands = []
            if sampled is not None:
                c1, c2 = hcm.ALL_COMBOS[int(sampled[i])]
                opp_hands.append([hcm.int_to_card(c1), hcm.int_to_card(c2)])
                used_ints.update((c1, c2))
            else:
                ok = True
                for opp_v in valid_list:
                    extra_blocked = used_ints - known_ints
                    w_copy = opp_v
                    if extra_blocked:
                        w_copy = opp_v.copy()
                        w_copy[hcm.blocked_by(extra_blocked)] = 0.0
                        total = w_copy.sum()
                        if total < 1e-15:
                            ok = False
                            break
                        w_copy /= total
                    c1, c2 = hcm.ALL_COMBOS[int(np_rng.choice(1326, p=w_copy))]
                    opp_hands.append([hcm.int_to_card(c1), hcm.int_to_card(c2)])
                    used_ints.update((c1, c2))
                if not ok:
                    continue
            if max(HandEvaluator.eval_int(h + board_l) for h in opp_hands) <= my_now:
                continue
            avail = [c for c in range(52) if c not in used_ints]
            runout = np_rng.choice(avail, size=board_needed, replace=False).tolist()
            full_board = board_l + [hcm.int_to_card(r) for r in runout]
            behind += 1
            my_score = HandEvaluator.eval_int(my_hand_l + full_board)
            best_opp = max(HandEvaluator.eval_int(h + full_board) for h in opp_hands)
            if my_score > best_opp:
                wins += 1.0
            elif my_score == best_opp:
                wins += 0.5

        if behind < RangeEquityCalculator._MIN_BEHIND_SAMPLES:
            return None
        return wins / behind

