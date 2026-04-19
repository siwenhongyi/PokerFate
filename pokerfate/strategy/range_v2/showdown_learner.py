"""Learn P(action | category) from showdown observations.

Records the hand category (nuts/strong/medium/draw/air) for each observed
(street, action) at showdown.  When enough samples accumulate, provides
empirical action→category distributions that override GTO baselines.

Reference: Bayes' Bluff (UAI 2005) — Dirichlet posterior on action profiles.
"""

from __future__ import annotations

import json
import os
from typing import Dict, List, Optional, Tuple

from pokerfate.core.card import Card
from pokerfate.strategy.range_v2 import hand_categorizer as hcat


class ShowdownLearner:
    """Learn empirical action→category distributions from showdown data.

    Completely independent from EQR's ShowdownCalibrator.
    """

    _MIN_SAMPLES = 8

    def __init__(self) -> None:
        # player_name → {(street, action): {category: count}}
        self._freq: Dict[str, Dict[Tuple[str, str], Dict[str, int]]] = {}

    def record(self, name: str, action_history: List[Tuple[str, str]],
               hand: List[Card], board: List[Card]) -> None:
        """Record one showdown observation.

        Parameters
        ----------
        name : str
            Player name (stable across sessions).
        action_history : list of (street, action)
            Actions taken by this player during the hand.
        hand : list of Card
            The revealed hole cards (2 cards).
        board : list of Card
            Final board (up to 5 cards).
        """
        if len(hand) < 2:
            return

        player_data = self._freq.setdefault(name, {})

        for street, action in action_history:
            if action == 'fold':
                continue

            street_board = _board_at_street(board, street)
            if street_board:
                cat = hcat.categorize_cards(hand, street_board)
            else:
                cat = hcat.categorize_cards(hand, [])  # preflop bucket

            key = (street, action)
            cat_counts = player_data.setdefault(key, {})
            cat_counts[cat] = cat_counts.get(cat, 0) + 1

    def get_learned_freq(self, name: str, street: str, action: str,
                         min_samples: int = _MIN_SAMPLES
                         ) -> Optional[Dict[str, float]]:
        """Return normalized category distribution for (street, action).

        Returns None if insufficient samples → caller falls back to GTO.
        """
        data = self._freq.get(name, {}).get((street, action))
        if data is None:
            return None
        total = sum(data.values())
        if total < min_samples:
            return None
        return {cat: cnt / total for cat, cnt in data.items()}

    def sample_count(self, name: str, street: str, action: str) -> int:
        """Return number of showdown samples for (name, street, action)."""
        data = self._freq.get(name, {}).get((street, action))
        if data is None:
            return 0
        return sum(data.values())

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_dict(self) -> dict:
        """Serialize to JSON-compatible dict."""
        result: dict = {}
        for name, pdata in self._freq.items():
            player_dict: dict = {}
            for (street, action), cats in pdata.items():
                key = f"{street}:{action}"
                player_dict[key] = dict(cats)
            result[name] = player_dict
        return result

    @classmethod
    def from_dict(cls, data: dict) -> 'ShowdownLearner':
        """Deserialize from dict."""
        learner = cls()
        for name, pdata in data.items():
            player_freq: Dict[Tuple[str, str], Dict[str, int]] = {}
            for key_str, cats in pdata.items():
                parts = key_str.split(':', 1)
                if len(parts) == 2:
                    player_freq[(parts[0], parts[1])] = dict(cats)
            learner._freq[name] = player_freq
        return learner

    def save(self, filepath: str) -> None:
        """Persist to JSON file."""
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)

    def load(self, filepath: str) -> None:
        """Load from JSON file (no-op if file missing)."""
        if not os.path.exists(filepath):
            return
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read().strip()
        if not content:
            return
        try:
            loaded = self.__class__.from_dict(json.loads(content))
            self._freq = loaded._freq
        except (json.JSONDecodeError, KeyError, ValueError):
            pass


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _board_at_street(board: List[Card], street: str) -> List[Card]:
    """Return the board cards visible at the given street."""
    if street == 'preflop':
        return []
    if street == 'flop':
        return board[:3] if len(board) >= 3 else []
    if street == 'turn':
        return board[:4] if len(board) >= 4 else []
    if street == 'river':
        return board[:5] if len(board) >= 5 else []
    return []
