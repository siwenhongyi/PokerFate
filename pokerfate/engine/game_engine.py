"""Texas Hold'em game simulation engine.

Supports heads-up and multi-player No-Limit Hold'em.
"""

from __future__ import annotations
import random
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Callable

from pokerfate.core.card import Card, Deck
from pokerfate.core.game_state import GameState, Player, Street, Action, ActionType
from pokerfate.core.hand_evaluator import HandEvaluator


@dataclass
class GameResult:
    winners: List[int]          # player IDs
    pot: float
    board: List[Card]
    player_hands: Dict[int, List[Card]]
    player_stacks_delta: Dict[int, float]


BotDecideFn = Callable[[GameState, int], Action]


class GameEngine:
    """Simulate a No-Limit Texas Hold'em game.

    Parameters
    ----------
    bots : dict
        {player_id: decide_fn} where decide_fn(GameState, player_id) -> Action
    player_names : dict
        {player_id: name}
    starting_stacks : dict
        {player_id: chips}
    big_blind : float
    small_blind : float
    verbose : bool
        Print hand history if True.
    """

    def __init__(
        self,
        bots: Dict[int, BotDecideFn],
        player_names: Optional[Dict[int, str]] = None,
        starting_stacks: Optional[Dict[int, float]] = None,
        big_blind: float = 2.0,
        small_blind: float = 1.0,
        verbose: bool = False,
    ):
        self.bots = bots
        self.player_ids = sorted(bots.keys())
        n = len(self.player_ids)
        self.player_names = player_names or {pid: f"Bot{pid}" for pid in self.player_ids}
        self.big_blind = big_blind
        self.small_blind = small_blind
        self.verbose = verbose
        self.stacks = starting_stacks or {pid: 200.0 * big_blind for pid in self.player_ids}
        self.dealer_pos = 0  # index into player_ids
        self.hand_count = 0

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def play_hand(self) -> Optional[GameResult]:
        """Play one complete hand. Returns GameResult or None if only one player left."""
        active = [pid for pid in self.player_ids if self.stacks[pid] > 0]
        if len(active) < 2:
            return None

        self.hand_count += 1
        n = len(active)

        # Create players
        players = [
            Player(
                player_id=pid,
                name=self.player_names[pid],
                stack=self.stacks[pid],
            )
            for pid in active
        ]
        pid_to_idx = {p.player_id: i for i, p in enumerate(players)}

        # Set up game state
        gs = GameState(
            players=players,
            dealer_pos=self.dealer_pos % n,
            big_blind=self.big_blind,
            small_blind=self.small_blind,
        )

        # Deal hole cards
        deck = Deck()
        deck.shuffle()
        for p in players:
            p.hole_cards = deck.deal(2)

        if self.verbose:
            self._log(f"\n=== Hand #{self.hand_count} ===")
            for p in players:
                self._log(f"  {p.name}: {p.hole_cards} (stack={p.stack:.1f})")

        # Post blinds
        self._post_blinds(gs)

        # Betting streets
        for street in [Street.PREFLOP, Street.FLOP, Street.TURN, Street.RIVER]:
            gs.street = street

            # Deal community cards
            if street == Street.FLOP:
                gs.board = deck.deal(3)
                if self.verbose:
                    self._log(f"  Flop: {gs.board}")
            elif street == Street.TURN:
                gs.board += deck.deal(1)
                if self.verbose:
                    self._log(f"  Turn: {gs.board}")
            elif street == Street.RIVER:
                gs.board += deck.deal(1)
                if self.verbose:
                    self._log(f"  River: {gs.board}")

            # Reset street bets
            for p in players:
                p.current_bet = 0.0
            gs.current_bet = 0.0 if street != Street.PREFLOP else gs.current_bet
            gs.street_action_count = 0

            if street != Street.PREFLOP:
                gs.action_history = []

            # Run betting round
            folded_out = self._betting_round(gs, deck)
            if folded_out:
                break

            # Check if only 1 remains
            if len(gs.active_players) <= 1:
                break

        # Determine winner(s)
        result = self._showdown(gs)

        # Update stacks
        for pid, delta in result.player_stacks_delta.items():
            self.stacks[pid] = max(0.0, self.stacks[pid] + delta)

        # Advance dealer
        self.dealer_pos = (self.dealer_pos + 1) % n

        if self.verbose:
            for pid, delta in result.player_stacks_delta.items():
                name = self.player_names[pid]
                self._log(f"  {name}: {'+' if delta >= 0 else ''}{delta:.1f}")

        return result

    def play_session(self, num_hands: int) -> Dict[int, float]:
        """Play multiple hands and return total stack delta per player."""
        initial = dict(self.stacks)
        for _ in range(num_hands):
            active = [pid for pid in self.player_ids if self.stacks[pid] > 0]
            if len(active) < 2:
                break
            self.play_hand()
        return {pid: self.stacks[pid] - initial[pid] for pid in self.player_ids}

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _post_blinds(self, gs: GameState):
        n = len(gs.players)
        if n == 2:
            # HU: dealer = SB
            sb_idx = gs.dealer_pos
            bb_idx = (gs.dealer_pos + 1) % n
        else:
            sb_idx = (gs.dealer_pos + 1) % n
            bb_idx = (gs.dealer_pos + 2) % n

        sb_player = gs.players[sb_idx]
        bb_player = gs.players[bb_idx]

        sb_amt = min(gs.small_blind, sb_player.stack)
        bb_amt = min(gs.big_blind, bb_player.stack)

        sb_player.stack -= sb_amt
        sb_player.current_bet = sb_amt
        sb_player.total_invested += sb_amt

        bb_player.stack -= bb_amt
        bb_player.current_bet = bb_amt
        bb_player.total_invested += bb_amt

        gs.pot = sb_amt + bb_amt
        gs.current_bet = bb_amt

        # UTG acts first preflop
        if n == 2:
            gs.current_player_idx = sb_idx  # SB/dealer acts first preflop in HU
        else:
            gs.current_player_idx = (bb_idx + 1) % n

        if self.verbose:
            self._log(f"  SB: {sb_player.name} posts {sb_amt:.1f}")
            self._log(f"  BB: {bb_player.name} posts {bb_amt:.1f}")

    def _betting_round(self, gs: GameState, deck: Deck) -> bool:
        """Run one betting round. Returns True if all but one player folded."""
        players = gs.players
        n = len(players)
        num_active = sum(1 for p in players if p.can_act())

        if num_active <= 1:
            return False

        # Track who has acted since the last raise
        last_aggressor_idx = None
        actions_since_last_raise = 0
        max_actions = n * 4  # safety limit

        iterations = 0
        while iterations < max_actions:
            iterations += 1
            player = gs.players[gs.current_player_idx]

            if not player.can_act():
                gs.current_player_idx = (gs.current_player_idx + 1) % n
                continue

            # Check if betting is done
            if last_aggressor_idx is not None and gs.current_player_idx == last_aggressor_idx:
                break

            to_call = gs.to_call(player)

            # If only one player can act and it's a check situation
            acting_count = sum(1 for p in players if p.can_act())
            if acting_count == 1 and to_call == 0:
                break

            # Get bot decision
            bot_fn = self.bots.get(player.player_id)
            if bot_fn is None:
                action = Action(ActionType.FOLD)
            else:
                action = bot_fn(gs, player.player_id)

            # Validate and apply action
            action = self._validate_action(action, player, gs)
            self._apply_action(action, player, gs)

            gs.action_history.append((player.player_id, action))
            gs.street_action_count += 1

            if self.verbose:
                self._log(f"    {player.name} [{gs.street}]: {action} (eq~{self._fmt_eq(player)})")

            if action.action_type == ActionType.FOLD:
                if len(gs.active_players) == 1:
                    return True

            if action.action_type == ActionType.RAISE:
                last_aggressor_idx = gs.current_player_idx
                actions_since_last_raise = 0
            else:
                actions_since_last_raise += 1

            # Initialize last_aggressor on first action of preflop (BB is last to act)
            if last_aggressor_idx is None and gs.street == Street.PREFLOP:
                if gs.street_action_count == len(gs.active_players):
                    break

            gs.current_player_idx = (gs.current_player_idx + 1) % n

        return False

    def _validate_action(self, action: Action, player: Player, gs: GameState) -> Action:
        """Ensure action is valid, fix if necessary."""
        to_call = gs.to_call(player)

        if action.action_type == ActionType.CHECK and to_call > 0:
            # Can't check if there's a bet — convert to call or fold
            if player.stack > 0:
                return Action(ActionType.CALL, min(to_call, player.stack))
            return Action(ActionType.FOLD)

        if action.action_type == ActionType.CALL:
            if to_call <= 0:
                return Action(ActionType.CHECK)
            call_amt = min(to_call, player.stack)
            return Action(ActionType.CALL, call_amt)

        if action.action_type == ActionType.RAISE:
            min_raise = gs.current_bet + gs.big_blind
            if action.amount < min_raise and action.amount < player.stack:
                action = Action(ActionType.RAISE, min_raise)
            if action.amount > player.stack:
                action = Action(ActionType.RAISE, player.stack)  # All-in
            if action.amount <= gs.current_bet:
                # Not enough to raise, call instead
                return Action(ActionType.CALL, min(to_call, player.stack))

        return action

    def _apply_action(self, action: Action, player: Player, gs: GameState):
        to_call = gs.to_call(player)

        if action.action_type == ActionType.FOLD:
            player.is_folded = True

        elif action.action_type == ActionType.CHECK:
            pass

        elif action.action_type == ActionType.CALL:
            amount = min(to_call, player.stack)
            player.stack -= amount
            player.current_bet += amount
            player.total_invested += amount
            gs.pot += amount
            if player.stack == 0:
                player.is_all_in = True

        elif action.action_type == ActionType.RAISE:
            # Amount is total bet for this street
            total_bet = action.amount
            already_bet = player.current_bet
            add = total_bet - already_bet
            if add > player.stack:
                add = player.stack
                total_bet = already_bet + add
            player.stack -= add
            player.current_bet = total_bet
            player.total_invested += add
            gs.pot += add
            gs.current_bet = total_bet
            if player.stack == 0:
                player.is_all_in = True

    def _showdown(self, gs: GameState) -> GameResult:
        active = gs.active_players
        board = gs.board

        stacks_delta: Dict[int, float] = {p.player_id: -p.total_invested for p in gs.players}

        if len(active) == 1:
            winner = active[0]
            stacks_delta[winner.player_id] += gs.pot
            if self.verbose:
                self._log(f"  {winner.name} wins {gs.pot:.1f} (all others folded)")
            return GameResult(
                winners=[winner.player_id],
                pot=gs.pot,
                board=board,
                player_hands={p.player_id: p.hole_cards for p in gs.players},
                player_stacks_delta=stacks_delta,
            )

        # Evaluate hands
        scores = {}
        for p in active:
            if len(p.hole_cards) + len(board) >= 5:
                scores[p.player_id] = HandEvaluator.evaluate(p.hole_cards + board)
            else:
                scores[p.player_id] = (0,)

        best_score = max(scores.values())
        winners = [p for p in active if scores[p.player_id] == best_score]

        split = gs.pot / len(winners)
        for w in winners:
            stacks_delta[w.player_id] += split

        if self.verbose:
            for w in winners:
                hand_name = HandEvaluator.hand_rank_name(scores[w.player_id])
                self._log(f"  {w.name} wins {split:.1f} with {hand_name} — {w.hole_cards}")

        return GameResult(
            winners=[w.player_id for w in winners],
            pot=gs.pot,
            board=board,
            player_hands={p.player_id: p.hole_cards for p in gs.players},
            player_stacks_delta=stacks_delta,
        )

    def _fmt_eq(self, player: Player) -> str:
        return ""  # Placeholder — bots can expose last_equity if needed

    def _log(self, msg: str):
        print(msg)
