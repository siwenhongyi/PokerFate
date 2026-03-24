"""PokerFate main bot: integrates preflop, postflop, GTO, and opponent modeling."""

from __future__ import annotations
import random
from typing import List, Optional, Tuple

from ..core.card import Card
from ..core.game_state import GameState, Player, Street, Action, ActionType
from ..core.equity import EquityCalculator
from ..strategy.preflop import PreflopStrategy
from ..strategy.postflop import PostflopStrategy
from ..strategy.gto import GTOMath
from .opponent_model import OpponentModel


class PokerBot:
    """GTO-based Texas Hold'em bot with exploitative adjustments.

    Parameters
    ----------
    name : str
        Bot display name.
    equity_iterations : int
        Monte Carlo iterations for equity calculation (speed/accuracy tradeoff).
    aggression : float
        Postflop aggression multiplier (1.0 = balanced).
    """

    def __init__(
        self,
        name: str = "PokerFate",
        equity_iterations: int = 1000,
        aggression: float = 1.0,
    ):
        self.name = name
        self.equity_calc = EquityCalculator()
        self.preflop = PreflopStrategy()
        self.postflop = PostflopStrategy(aggression=aggression)
        self.gto = GTOMath()
        self.opponent_model = OpponentModel()
        self.equity_iterations = equity_iterations
        self._last_equity: float = 0.5

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def decide(self, game_state: GameState, my_player_id: int = 0, *, player_id: int = None) -> Action:
        if player_id is not None:
            my_player_id = player_id
        """Main entry point: return the chosen Action given the game state."""
        player = self._find_player(game_state, my_player_id)
        if player is None or player.is_folded:
            return Action(ActionType.FOLD)

        if game_state.street == Street.PREFLOP:
            return self._decide_preflop(game_state, player)
        else:
            return self._decide_postflop(game_state, player)

    # ------------------------------------------------------------------
    # Preflop logic
    # ------------------------------------------------------------------

    def _decide_preflop(self, gs: GameState, player: Player) -> Action:
        position = gs.position_of(player)
        is_ip = gs.is_ip(player)
        bb = gs.big_blind
        to_call = gs.to_call(player)
        stack = player.stack

        # Determine what action we're facing
        facing_action, open_raise = self._classify_preflop_action(gs, player)

        action_str, amount = self.preflop.decide(
            hole_cards=player.hole_cards,
            position=position,
            facing_action=facing_action,
            open_raise=open_raise if open_raise else to_call,
            is_ip=is_ip,
            big_blind=bb,
            stack=stack,
            pot=gs.pot,
        )

        return self._to_action(action_str, amount, to_call, stack)

    def _classify_preflop_action(self, gs: GameState, player: Player):
        """Returns (facing_action_str, open_raise_amount)."""
        history = gs.action_history
        raises = [
            (pid, act) for pid, act in history
            if act.action_type == ActionType.RAISE
            and pid != player.player_id
        ]
        if not raises:
            return 'none', 0.0
        if len(raises) == 1:
            return 'open', raises[0][1].amount
        if len(raises) == 2:
            return '3bet', raises[-1][1].amount
        return '4bet', raises[-1][1].amount

    # ------------------------------------------------------------------
    # Postflop logic
    # ------------------------------------------------------------------

    def _decide_postflop(self, gs: GameState, player: Player) -> Action:
        board = gs.board
        to_call = gs.to_call(player)
        stack = player.stack
        pot = gs.pot
        is_ip = gs.is_ip(player)
        street = str(gs.street)
        bb = gs.big_blind
        num_opponents = len(gs.active_players) - 1
        facing_bet = to_call > 0

        # Get opponent IDs for modeling
        opp_ids = [p.player_id for p in gs.active_players if p.player_id != player.player_id]
        primary_opp_id = opp_ids[0] if opp_ids else -1

        # Calculate equity
        equity = self._get_equity(player.hole_cards, board, num_opponents)
        self._last_equity = equity

        # Get exploit adjustments
        adj = self.opponent_model.exploit_adjustments(primary_opp_id) if primary_opp_id >= 0 else {}
        opp_fold_rate = self._adjusted_fold_rate(primary_opp_id, adj)

        # Apply exploitative aggression adjustment
        aggression = self._compute_aggression(adj)
        self.postflop.aggression = aggression

        spr = self.gto.spr(stack, max(pot, 0.01))

        action_str, amount = self.postflop.decide(
            equity=equity,
            pot=pot,
            to_call=to_call,
            stack=stack,
            board=board,
            is_ip=is_ip,
            street=street,
            facing_bet=facing_bet,
            num_opponents=num_opponents,
            big_blind=bb,
            opponent_fold_rate=opp_fold_rate,
            spr=spr,
        )

        return self._to_action(action_str, amount, to_call, stack)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_equity(self, hole_cards: List[Card], board: List[Card], num_opponents: int) -> float:
        if not hole_cards:
            return 0.5
        return self.equity_calc.calculate(
            hole_cards, board, num_opponents,
            iterations=self.equity_iterations,
        )

    def _adjusted_fold_rate(self, opp_id: int, adj: dict) -> float:
        base = self.opponent_model.fold_to_cbet_rate(opp_id) if opp_id >= 0 else 0.45
        if adj.get('cbet_freq') == 'high':
            return max(base, 0.55)
        if adj.get('bluff_freq') == 'none':
            return min(base, 0.30)
        return base

    def _compute_aggression(self, adj: dict) -> float:
        if adj.get('bluff_freq') == 'none':
            return 0.5   # Value-only mode
        if adj.get('cbet_freq') == 'high' or adj.get('bluff_freq') == 'high':
            return 1.3
        if adj.get('bluff_freq') == 'low':
            return 0.7
        return 1.0

    def _to_action(self, action_str: str, amount: float, to_call: float, stack: float) -> Action:
        if action_str == 'fold':
            return Action(ActionType.FOLD)
        if action_str == 'check':
            return Action(ActionType.CHECK)
        if action_str == 'call':
            call_amt = min(to_call, stack)
            return Action(ActionType.CALL, call_amt)
        if action_str == 'raise':
            raise_amt = min(amount, stack)
            if raise_amt <= to_call:
                # Can't raise less than call; just call
                return Action(ActionType.CALL, min(to_call, stack))
            return Action(ActionType.RAISE, raise_amt)
        return Action(ActionType.FOLD)

    def _find_player(self, gs: GameState, player_id: int) -> Optional[Player]:
        for p in gs.players:
            if p.player_id == player_id:
                return p
        return None

    # ------------------------------------------------------------------
    # Opponent model update (called by game engine)
    # ------------------------------------------------------------------

    def observe_action(
        self,
        player_id: int,
        action: Action,
        street: str,
        is_cbet_spot: bool = False,
        is_3bet_spot: bool = False,
    ):
        """Record an observed opponent action for modeling."""
        act = str(action.action_type).lower()
        self.opponent_model.record_action(player_id, act, street)

        if action.action_type == ActionType.RAISE:
            if street == 'preflop':
                self.opponent_model.record_vpip(player_id)
                self.opponent_model.record_pfr(player_id)
        elif action.action_type == ActionType.CALL:
            if street == 'preflop':
                self.opponent_model.record_vpip(player_id)

        if is_3bet_spot:
            did_3bet = action.action_type == ActionType.RAISE
            self.opponent_model.record_3bet_opportunity(player_id, did_3bet)

        if is_cbet_spot:
            folded = action.action_type == ActionType.FOLD
            self.opponent_model.record_fold_to_cbet(player_id, folded)

    def new_hand(self, player_ids: List[int]):
        """Call at the start of each new hand."""
        for pid in player_ids:
            self.opponent_model.record_hand_start(pid)

    @property
    def last_equity(self) -> float:
        return self._last_equity
