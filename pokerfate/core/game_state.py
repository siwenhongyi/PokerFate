"""Game state representation for Texas Hold'em."""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import List, Optional


class Street(Enum):
    PREFLOP = auto()
    FLOP = auto()
    TURN = auto()
    RIVER = auto()

    def __str__(self) -> str:
        return self.name.lower()


class ActionType(Enum):
    FOLD = auto()
    CHECK = auto()
    CALL = auto()
    RAISE = auto()

    def __str__(self) -> str:
        return self.name.lower()


@dataclass
class Action:
    action_type: ActionType
    amount: float = 0.0  # total bet amount (for RAISE), ignored for fold/check/call

    def __repr__(self) -> str:
        if self.action_type in (ActionType.FOLD, ActionType.CHECK, ActionType.CALL):
            return str(self.action_type)
        return f"{self.action_type}({self.amount:.1f})"


@dataclass
class Player:
    player_id: int
    name: str
    stack: float
    hole_cards: list = field(default_factory=list)
    current_bet: float = 0.0  # amount bet this street
    total_invested: float = 0.0  # total chips in pot this hand
    is_folded: bool = False
    is_all_in: bool = False

    def can_act(self) -> bool:
        return not self.is_folded and not self.is_all_in

    def effective_stack(self) -> float:
        return self.stack


@dataclass
class GameState:
    players: List[Player]
    dealer_pos: int = 0
    street: Street = Street.PREFLOP
    board: list = field(default_factory=list)
    pot: float = 0.0
    current_bet: float = 0.0   # highest bet this street
    big_blind: float = 1.0
    small_blind: float = 0.5
    current_player_idx: int = 0
    # Uniform shape: (player_id, Action, street) with street in {"preflop","flop","turn","river"}.
    action_history: list = field(default_factory=list)
    street_action_count: int = 0  # actions taken this street

    def last_aggressor_id(self, my_player_id: int, street: Optional[str] = None) -> Optional[int]:
        """Last opponent to bet or raise (RAISE includes first bet), optionally on one street."""
        sk = street.lower() if street else None
        for item in reversed(self.action_history):
            if len(item) < 3:
                continue
            pid, act, st = item[0], item[1], item[2]
            if sk is not None and st != sk:
                continue
            if pid == my_player_id:
                continue
            if act.action_type == ActionType.RAISE:
                return pid
        return None

    def aggressor_opponent_id(self, my_player: Player) -> Optional[int]:
        """Last aggressor among active opponents, if any (limp / check-down → None).

        Callers should combine with :meth:`OpponentModel.preferred_exploit_target`
        when this returns ``None``.
        """
        opp_ids = [p.player_id for p in self.active_players if p.player_id != my_player.player_id]
        if not opp_ids:
            return None
        my_id = my_player.player_id
        street_s = str(self.street)
        tc = self.to_call(my_player)

        if tc > 0:
            pid = self.last_aggressor_id(my_id, street=street_s)
            if pid is not None and pid in opp_ids:
                return pid
            pid = self.last_aggressor_id(my_id, street=None)
            if pid is not None and pid in opp_ids:
                return pid
        else:
            pid = self.last_aggressor_id(my_id, street=None)
            if pid is not None and pid in opp_ids:
                return pid
        return None

    @property
    def active_players(self) -> List[Player]:
        return [p for p in self.players if not p.is_folded]

    def to_call(self, player: Player) -> float:
        """Amount the player needs to add to call."""
        return max(0.0, self.current_bet - player.current_bet)

    def position_of(self, player: Player) -> str:
        """Return position label for the player."""
        n = len(self.players)
        # Use list index, NOT player_id — player_id may be non-contiguous
        try:
            idx = next(i for i, p in enumerate(self.players)
                       if p.player_id == player.player_id)
        except StopIteration:
            return 'MP'

        btn_idx = self.dealer_pos % n
        sb_idx = (self.dealer_pos + 1) % n
        bb_idx = (self.dealer_pos + 2) % n

        if n == 2:
            if idx == btn_idx:
                return 'BTN'
            return 'BB'

        if idx == btn_idx:
            return 'BTN'
        if idx == sb_idx:
            return 'SB'
        if idx == bb_idx:
            return 'BB'

        dist = (idx - bb_idx - 1) % n
        labels = ['UTG', 'UTG+1', 'UTG+2', 'LJ', 'HJ', 'CO']
        if dist < len(labels):
            return labels[dist]
        return 'MP'

    def is_ip(self, player: Player) -> bool:
        """True if player acts last (in position) postflop.

        Iterates positions from SB → BTN without breaking early, so that
        latest_active ends up as the last active player in the order
        (i.e. BTN/dealer = IP).  The previous implementation broke on the
        first match which wrongly returned the first-to-act (SB) as IP.
        """
        active = [p for p in self.players if not p.is_folded]
        if len(active) < 2:
            return False
        btn = self.dealer_pos % len(self.players)
        latest_active = None
        for i in range(len(self.players) - 1, -1, -1):
            p = self.players[(btn - i) % len(self.players)]
            if not p.is_folded:
                latest_active = p   # keep overwriting; last non-folded = IP
        return latest_active is not None and latest_active.player_id == player.player_id
