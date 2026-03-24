"""Card and Deck representations."""

from __future__ import annotations
import random
from enum import IntEnum
from typing import List


class Rank(IntEnum):
    TWO = 2
    THREE = 3
    FOUR = 4
    FIVE = 5
    SIX = 6
    SEVEN = 7
    EIGHT = 8
    NINE = 9
    TEN = 10
    JACK = 11
    QUEEN = 12
    KING = 13
    ACE = 14

    def __str__(self) -> str:
        names = {2: '2', 3: '3', 4: '4', 5: '5', 6: '6', 7: '7', 8: '8',
                 9: '9', 10: 'T', 11: 'J', 12: 'Q', 13: 'K', 14: 'A'}
        return names[self.value]


class Suit(IntEnum):
    CLUBS = 0
    DIAMONDS = 1
    HEARTS = 2
    SPADES = 3

    def __str__(self) -> str:
        return ['c', 'd', 'h', 's'][self.value]


class Card:
    __slots__ = ('rank', 'suit')

    def __init__(self, rank: int | Rank, suit: int | Suit):
        self.rank = Rank(rank)
        self.suit = Suit(suit)

    def __repr__(self) -> str:
        return f"{self.rank}{self.suit}"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Card):
            return NotImplemented
        return self.rank == other.rank and self.suit == other.suit

    def __hash__(self) -> int:
        return self.rank * 4 + self.suit

    def __lt__(self, other: Card) -> bool:
        return self.rank < other.rank

    @staticmethod
    def from_str(s: str) -> Card:
        """Parse card from string like 'As', 'Kh', 'Tc', '2d'."""
        rank_map = {'2': 2, '3': 3, '4': 4, '5': 5, '6': 6, '7': 7,
                    '8': 8, '9': 9, 'T': 10, 'J': 11, 'Q': 12, 'K': 13, 'A': 14}
        suit_map = {'c': 0, 'd': 1, 'h': 2, 's': 3}
        s = s.strip()
        return Card(rank_map[s[0].upper()], suit_map[s[1].lower()])


class Deck:
    def __init__(self):
        self.cards: List[Card] = [
            Card(rank, suit)
            for rank in Rank
            for suit in Suit
        ]
        self._dealt: set = set()

    def shuffle(self) -> None:
        random.shuffle(self.cards)
        self._dealt.clear()

    def deal(self, n: int = 1) -> List[Card]:
        result = []
        for card in self.cards:
            if card not in self._dealt:
                self._dealt.add(card)
                result.append(card)
                if len(result) == n:
                    break
        return result

    def deal_excluding(self, exclude: List[Card], n: int = 1) -> List[Card]:
        excluded_set = set(exclude) | self._dealt
        result = []
        for card in self.cards:
            if card not in excluded_set:
                self._dealt.add(card)
                result.append(card)
                if len(result) == n:
                    break
        return result

    def remaining(self, exclude: List[Card]) -> List[Card]:
        excluded_set = set(exclude)
        return [c for c in self.cards if c not in excluded_set]
