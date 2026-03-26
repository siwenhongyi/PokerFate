"""PokerFate External Interface — Event-Driven API

外部接入说明
============

外部系统只需与本文件的 `PokerFateAPI` 类交互，无需了解内部实现。

接入流程（每手牌）：
  1. api.new_hand(...)              # 新一手牌开始（传入当前所有玩家信息）
  2. api.deal_hole_cards(...)       # 发底牌给 bot
  3. api.notify_action(...)         # 通知各玩家行动（可多次调用）
  4. api.deal_board(...)            # 发公共牌（翻牌/转牌/河牌）
  5. action = api.request_action()  # 需要 bot 行动时调用，获取决策
  6. api.hand_over(...)             # 手牌结束，传入 final_stacks 更新筹码

事件通知与决策请求可以穿插调用，与实际游戏节奏一致。

筹码追踪策略（两种情况均已处理）：
  - 每手牌结束时调用 hand_over(final_stacks={...}) ——
    API 会将本手结果持久化到会话注册表，下一手自动使用
  - PlayerInfo.stack 可以传 None ——
    API 自动从会话注册表查找，查不到则默认 100 BB
  - 对手替换/新玩家加入：调用 notify_player_joined() 或
    直接在 new_hand() 中传入新的 player_id 即可；
    新 player_id 自动获得干净的对手模型（历史数据不会污染）
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from enum import Enum
from pathlib import Path

from pokerfate.core.card import Card
from pokerfate.core.game_state import GameState, Player, Street, Action, ActionType
from pokerfate.bot.poker_bot import PokerBot
from pokerfate.logger import PokerLogger, get_logger

_DEFAULT_LOG_FILE = str(Path(__file__).resolve().parent / "logs" / "pokerfate.log")


# ---------------------------------------------------------------------------
# Public data types for the external interface
# ---------------------------------------------------------------------------

class StreetName(str, Enum):
    PREFLOP = "preflop"
    FLOP = "flop"
    TURN = "turn"
    RIVER = "river"


@dataclass
class PlayerInfo:
    """Describes one player at the table.

    stack may be None when the opponent's exact chip count is unknown
    (e.g. a new player joining mid-session). The API will fall back to
    the last known stack from session history, or a default of 100 BB.
    """
    player_id: int
    name: str
    stack: Optional[float] = None   # None = unknown / use session default
    position: str = ""              # e.g. "BTN", "BB", "UTG"


@dataclass
class ActionEvent:
    """An action taken by any player (including opponents)."""
    player_id: int
    action: str           # "fold" | "check" | "call" | "raise"
    amount: float = 0.0   # For raise: total bet size. 0 for others.
    street: str = ""


@dataclass
class BotDecision:
    """The bot's chosen action, returned to the external system."""
    action: str           # "fold" | "check" | "call" | "raise"
    amount: float = 0.0   # For raise: total bet size (chips to put in total this street)

    def __repr__(self) -> str:
        if self.action == "raise":
            return f"BotDecision(raise, amount={self.amount:.1f})"
        return f"BotDecision({self.action})"


# ---------------------------------------------------------------------------
# Main API class
# ---------------------------------------------------------------------------

class PokerFateAPI:
    """External interface for the PokerFate bot.

    Usage example:
    --------------
        api = PokerFateAPI(my_player_id=0, big_blind=2.0)

        # Start of hand
        api.new_hand(
            players=[
                PlayerInfo(0, "PokerFate", 200.0, "BTN"),
                PlayerInfo(1, "GPT-Bot",   200.0, "BB"),
            ],
            dealer_id=0,
        )

        # Bot receives hole cards
        api.deal_hole_cards(["Ac", "Kd"])

        # Opponent posts BB (optional to notify, but helps modeling)
        api.notify_action(ActionEvent(player_id=1, action="raise", amount=2.0, street="preflop"))

        # Bot must act
        decision = api.request_action(
            street="preflop",
            pot=3.0,
            current_bet=2.0,
            to_call=2.0,
            my_stack=200.0,
        )
        print(decision)  # BotDecision(raise, amount=6.0)

        # Flop is dealt
        api.deal_board(["As", "7d", "2c"], street="flop")

        # Opponent checks
        api.notify_action(ActionEvent(player_id=1, action="check", street="flop"))

        # Bot acts again
        decision = api.request_action(
            street="flop",
            pot=7.0,
            current_bet=0.0,
            to_call=0.0,
            my_stack=197.0,
        )
        print(decision)
    """

    def __init__(
        self,
        my_player_id: int = 0,
        big_blind: float = 2.0,
        small_blind: float = 1.0,
        equity_iterations: int = 800,
        aggression: float = 1.0,
        autosave_path: Optional[str] = "opponents.json",
        log_file: Optional[str] = _DEFAULT_LOG_FILE,
        verbose: bool = False,
    ):
        """
        Parameters
        ----------
        my_player_id : int
            The player ID assigned to this bot.
        big_blind : float
            Table big blind size.
        small_blind : float
            Table small blind size.
        equity_iterations : int
            Monte Carlo iterations for equity (higher = more accurate but slower).
        aggression : float
            Postflop aggression multiplier. 1.0 = GTO baseline.
        autosave_path : str or None
            Path to JSON file for opponent model persistence.
            After every hand_over() call, the model is automatically saved here.
            On startup, existing data is automatically loaded from this file.
            Set to None to disable autosave.
        log_file : str or None
            Path to JSONL log file. None disables file logging.
        verbose : bool
            If True, also print debug-level internal details to console.
            Key events (decisions, results) are always printed regardless.
        """
        self.my_player_id = my_player_id
        self.big_blind = big_blind
        self.small_blind = small_blind
        self.verbose = verbose
        self.autosave_path = autosave_path
        self._log = PokerLogger(log_file=log_file, console=True)
        self._default_stack = 100.0 * big_blind  # fallback when stack is unknown

        self._bot = PokerBot(
            name="PokerFate",
            equity_iterations=equity_iterations,
            aggression=aggression,
        )

        # Auto-load opponent data from disk on startup
        if autosave_path:
            self._bot.opponent_model = self._bot.opponent_model.__class__.load(autosave_path)
            if self._bot.opponent_model._stats:
                self._log.raw({"event": "model_loaded", "path": autosave_path,
                               "known_opponents": len(self._bot.opponent_model._stats)})

        # Session-level state: persists across hands
        self._session_stacks: Dict[int, float] = {}   # player_id -> last known stack
        self._session_names: Dict[int, str] = {}      # player_id -> name
        self._session_delta: float = 0.0              # cumulative P&L this session

        # Hand state: rebuilt each hand
        self._players: List[Player] = []
        self._hole_cards: List[Card] = []
        self._board: List[Card] = []
        self._action_history: List[tuple] = []
        self._dealer_id: int = 0
        self._hand_number: int = 0

    # ------------------------------------------------------------------
    # Hand lifecycle events
    # ------------------------------------------------------------------

    def new_hand(
        self,
        players: List[PlayerInfo],
        dealer_id: int,
    ) -> None:
        """Call at the start of each new hand.

        Parameters
        ----------
        players : list of PlayerInfo
            All players at the table (including this bot).
            A player's stack may be None if unknown — the API will use
            the last recorded stack from session history, or 100 BB as
            a conservative default for brand-new opponents.
        dealer_id : int
            player_id of the dealer/button.

        Notes
        -----
        - If a player_id appears that was not seen before, they are
          treated as a new opponent with a fresh opponent model.
        - If a previously busted player is replaced by a new player_id,
          the old model is automatically abandoned (keyed by player_id).
        """
        self._hand_number += 1
        self._dealer_id = dealer_id
        self._hole_cards = []
        self._board = []
        self._action_history = []
        self._my_stack_start: float = 0.0  # set after resolving stacks below

        self._last_known_pot: float = 0.0
        self._players = []
        for p in players:
            # Resolve stack: explicit > session history > default
            stack = p.stack
            if stack is None:
                stack = self._session_stacks.get(p.player_id, self._default_stack)

            self._session_names[p.player_id] = p.name
            if p.stack is not None:
                self._session_stacks[p.player_id] = p.stack

            # Register name for cross-session opponent model lookup
            if p.player_id != self.my_player_id:
                self._bot.opponent_model.register_name(p.player_id, p.name)

            self._players.append(Player(
                player_id=p.player_id,
                name=p.name,
                stack=stack,
            ))

        # Record my stack at the start of this hand for delta calculation
        my_p = self._get_my_player()
        self._my_stack_start = my_p.stack if my_p else 0.0

        all_ids = [p.player_id for p in players]
        self._bot.new_hand(all_ids)

        self._log.hand_start(
            hand_number=self._hand_number,
            players=[
                {"id": p.player_id, "name": p.name,
                 "stack": p.stack, "pos": pi.position}
                for p, pi in zip(self._players, players)
            ],
            dealer_id=dealer_id,
        )

    def deal_hole_cards(self, cards: List[str]) -> None:
        """Tell the bot its hole cards.

        Parameters
        ----------
        cards : list of str
            Two card strings, e.g. ["Ac", "Kd"]
        """
        self._hole_cards = [Card.from_str(c) for c in cards]
        my_player = self._get_my_player()
        if my_player:
            my_player.hole_cards = self._hole_cards

        self._log.hole_cards(cards)

    def deal_board(self, cards: List[str], street: str, pot: Optional[float] = None) -> None:
        """Notify the bot of new community cards.

        Parameters
        ----------
        cards : list of str
            The newly dealt cards (3 for flop, 1 for turn/river).
            Pass only the NEW cards, not all board cards.
        street : str
            "flop" | "turn" | "river"
        pot : float, optional
            Actual pot size at the start of this street. Recommended for
            accurate display; falls back to last known pot if omitted.
        """
        new_cards = [Card.from_str(c) for c in cards]
        self._board.extend(new_cards)

        display_pot = pot if pot is not None else self._last_known_pot
        if pot is not None:
            self._last_known_pot = pot
        self._log.board(street, cards, pot=display_pot)

    # ------------------------------------------------------------------
    # Action notification
    # ------------------------------------------------------------------

    def notify_action(self, event: ActionEvent) -> None:
        """Notify the bot of any player's action (for opponent modeling).

        Parameters
        ----------
        event : ActionEvent
            The action taken.
        """
        if event.player_id == self.my_player_id:
            return  # Don't track our own actions for modeling

        # Compute spot types BEFORE appending current action to history
        is_3bet_spot = self._detect_3bet_spot(event)
        is_cbet_spot = self._detect_cbet_spot(event)

        action = self._parse_action(event)
        self._action_history.append((event.player_id, action))

        # Update player state
        player = self._get_player(event.player_id)
        if player and event.action == "fold":
            player.is_folded = True
        if player and event.action in ("call", "raise"):
            cost = event.amount - (player.current_bet if event.action == "raise" else 0)
            player.stack = max(0, player.stack - max(cost, event.amount))

        # Feed into opponent model with correct spot context
        self._bot.observe_action(
            player_id=event.player_id,
            action=action,
            street=event.street,
            is_cbet_spot=is_cbet_spot,
            is_3bet_spot=is_3bet_spot,
        )

        pobj = self._get_player(event.player_id)
        name = pobj.name if pobj else str(event.player_id)
        self._log.opponent_action(name, event.action, event.amount, event.street)

        # Check for newly significant opponent patterns and surface them
        self._maybe_log_opponent_pattern(event.player_id, name)

    def notify_stack_update(self, player_id: int, new_stack: float) -> None:
        """Update a player's stack at any point (e.g. after side-pot resolution).

        Also persists to the session registry for future hands.
        """
        player = self._get_player(player_id)
        if player:
            player.stack = new_stack
        self._session_stacks[player_id] = new_stack

    def notify_player_joined(
        self,
        player_id: int,
        name: str,
        stack: Optional[float] = None,
    ) -> None:
        """Notify that a new player has joined (or replaced a busted one).

        Call this between hands when the seat composition changes.
        The new player gets a fresh opponent model automatically.
        Their stack defaults to 100 BB if not provided.

        Parameters
        ----------
        player_id : int
            The new player's ID (must be different from any current player).
        name : str
            Display name.
        stack : float, optional
            Starting stack. None = use 100 BB default.
        """
        resolved_stack = stack if stack is not None else self._default_stack
        self._session_stacks[player_id] = resolved_stack
        self._session_names[player_id] = name
        # Register name: if this name was seen before with a different ID,
        # historical stats are automatically migrated to the new ID.
        self._bot.opponent_model.register_name(player_id, name)
        if self.verbose:
            self._log.raw({"event": "player_joined", "player_id": player_id,
                           "name": name, "stack": resolved_stack})

    # ------------------------------------------------------------------
    # Decision request
    # ------------------------------------------------------------------

    def request_action(
        self,
        street: str,
        pot: float,
        current_bet: float,
        to_call: float,
        my_stack: float,
        num_active_opponents: int = 1,
        my_current_bet_this_street: float = 0.0,
    ) -> BotDecision:
        """Ask the bot for its action.

        Call this whenever the bot needs to act.

        Parameters
        ----------
        street : str
            Current street: "preflop" | "flop" | "turn" | "river"
        pot : float
            Current pot size (before any call/raise by the bot).
        current_bet : float
            The highest bet on the table this street (0 if no bet yet).
        to_call : float
            Amount the bot needs to add to call (0 if no bet to call).
        my_stack : float
            Bot's current stack.
        num_active_opponents : int
            Number of opponents still in the hand.
        my_current_bet_this_street : float
            Amount the bot has already put in this street (for raise calculations).

        Returns
        -------
        BotDecision
            The bot's chosen action and amount.
        """
        self._last_known_pot = pot
        # Build a minimal GameState for the bot
        gs = self._build_game_state(
            street=street,
            pot=pot,
            current_bet=current_bet,
            my_stack=my_stack,
            my_current_bet_this_street=my_current_bet_this_street,
        )

        action = self._bot.decide(gs, self.my_player_id)
        decision = self._to_decision(action)

        my_name = self._session_names.get(self.my_player_id, "PokerFate")
        self._log.decision(
            action=decision.action,
            amount=decision.amount,
            street=street,
            equity=self._bot.last_equity,
            pot=pot,
            to_call=to_call,
            bot_name=my_name,
            reasoning=self._bot.last_reasoning,
        )

        return decision

    # ------------------------------------------------------------------
    # Hand result (optional, for tracking)
    # ------------------------------------------------------------------

    def hand_over(
        self,
        winner_ids: List[int],
        pot: float,
        final_stacks: Optional[Dict[int, float]] = None,
        showdown_hands: Optional[Dict[int, List[str]]] = None,
    ) -> None:
        """Notify the bot that the hand is over.

        Parameters
        ----------
        winner_ids : list of int
            The winning player IDs.
        pot : float
            Total pot awarded.
        final_stacks : dict, optional
            {player_id: stack} — each player's stack after this hand.
            Strongly recommended: pass this so the API tracks stacks
            accurately across hands, buy-ins, and rebuys.
            If omitted, stacks are estimated from observed actions.
        showdown_hands : dict, optional
            {player_id: ["Ac", "Kd"]} — revealed hands at showdown.
        """
        if final_stacks:
            for pid, stack in final_stacks.items():
                self._session_stacks[pid] = stack
                player = self._get_player(pid)
                if player:
                    player.stack = stack

        winner_names = [self._session_names.get(wid, str(wid)) for wid in winner_ids]
        my_final = (final_stacks or {}).get(self.my_player_id)
        my_delta = (my_final - self._my_stack_start) if my_final is not None else 0.0
        self._session_delta += my_delta
        self._log.hand_result(
            winner_names=winner_names,
            pot=pot,
            my_delta=my_delta,
            final_stacks={
                self._session_names.get(pid, str(pid)): s
                for pid, s in (final_stacks or {}).items()
            },
        )

        # Auto-save opponent model after every hand — safe against any kind of crash/kill
        if self.autosave_path:
            self._bot.opponent_model.save(self.autosave_path)

    # ------------------------------------------------------------------
    # Convenience: parse card strings
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save_opponent_data(self, filepath: str) -> None:
        """Persist opponent model to disk."""
        self._bot.opponent_model.save(filepath)
        self._log.raw({"event": "model_saved", "path": filepath})

    def load_opponent_data(self, filepath: str) -> None:
        """Load previously saved opponent data from disk (no-op if file missing)."""
        self._bot.opponent_model = self._bot.opponent_model.__class__.load(filepath)
        self._log.raw({"event": "model_loaded", "path": filepath,
                       "known_opponents": len(self._bot.opponent_model._stats)})

    def opponent_summary(self) -> str:
        """Return a readable summary of all known opponents."""
        return self._bot.opponent_model.summary()

    # ------------------------------------------------------------------
    # Convenience: parse card strings
    # ------------------------------------------------------------------

    @staticmethod
    def parse_cards(card_strings: List[str]) -> List[Card]:
        """Utility: convert card strings to Card objects."""
        return [Card.from_str(c) for c in card_strings]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    # threshold tracking: avoid logging the same pattern repeatedly
    _PATTERN_LOG_INTERVAL = 20   # log a pattern at most once per N hands

    def _maybe_log_opponent_pattern(self, player_id: int, name: str):
        """Surface significant opponent patterns to the log (throttled)."""
        s = self._bot.opponent_model.get(player_id)
        if s.hands_seen < 15:
            return
        adj = self._bot.opponent_model.exploit_adjustments(player_id)
        if not adj:
            return
        # Only log once per interval to avoid spam
        key = f"_pattern_logged_{player_id}"
        last = getattr(self, key, 0)
        if self._hand_number - last < self._PATTERN_LOG_INTERVAL:
            return
        setattr(self, key, self._hand_number)

        if "cbet_freq" in adj and s.fold_to_cbet_opps >= 5:
            self._log.opponent_pattern(name, "fold_to_cbet",
                                       s.fold_to_cbet, adj["cbet_freq"])
        elif "bluff_freq" in adj:
            self._log.opponent_pattern(name, "player_type",
                                       s.vpip, adj.get("bluff_freq", ""))

    def session_summary(self):
        """Print and log a session-end summary."""
        self._log.session_summary(self._hand_number, self._session_delta, self.big_blind)

    @property
    def logger(self) -> PokerLogger:
        """Direct access to the underlying PokerLogger."""
        return self._log

    def _detect_3bet_spot(self, event: ActionEvent) -> bool:
        """True if this action is a response to exactly one preflop open raise.

        Uses action history BEFORE the current event is appended.
        """
        if event.street.lower() != "preflop":
            return False
        raises_by_others = [
            pid for pid, act in self._action_history
            if act.action_type == ActionType.RAISE and pid != event.player_id
        ]
        return len(raises_by_others) == 1

    def _detect_cbet_spot(self, event: ActionEvent) -> bool:
        """True if the bot made the last bet on this street and the opponent is responding.

        Uses action history BEFORE the current event is appended.
        """
        if event.street.lower() == "preflop":
            return False
        for pid, act in reversed(self._action_history):
            if act.action_type == ActionType.RAISE:
                return pid == self.my_player_id
        return False

    def _build_game_state(
        self,
        street: str,
        pot: float,
        current_bet: float,
        my_stack: float,
        my_current_bet_this_street: float,
    ) -> GameState:
        street_map = {
            "preflop": Street.PREFLOP,
            "flop":    Street.FLOP,
            "turn":    Street.TURN,
            "river":   Street.RIVER,
        }
        street_enum = street_map.get(street.lower(), Street.PREFLOP)

        # Reconstruct players list with current info
        players = []
        my_idx = 0
        for i, p in enumerate(self._players):
            player = Player(
                player_id=p.player_id,
                name=p.name,
                stack=my_stack if p.player_id == self.my_player_id else p.stack,
                hole_cards=self._hole_cards if p.player_id == self.my_player_id else [],
                current_bet=(
                    my_current_bet_this_street
                    if p.player_id == self.my_player_id
                    else p.current_bet
                ),
                is_folded=p.is_folded,
            )
            players.append(player)
            if p.player_id == self.my_player_id:
                my_idx = i

        # Dealer position (index in players list)
        dealer_pos = 0
        for i, p in enumerate(players):
            if p.player_id == self._dealer_id:
                dealer_pos = i
                break

        gs = GameState(
            players=players,
            dealer_pos=dealer_pos,
            street=street_enum,
            board=list(self._board),
            pot=pot,
            current_bet=current_bet,
            big_blind=self.big_blind,
            small_blind=self.small_blind,
            current_player_idx=my_idx,
            action_history=list(self._action_history),
        )
        return gs

    def _parse_action(self, event: ActionEvent) -> Action:
        action_map = {
            "fold":  ActionType.FOLD,
            "check": ActionType.CHECK,
            "call":  ActionType.CALL,
            "raise": ActionType.RAISE,
        }
        atype = action_map.get(event.action.lower(), ActionType.FOLD)
        return Action(atype, event.amount)

    def _to_decision(self, action: Action) -> BotDecision:
        name = action.action_type.name.lower()
        return BotDecision(action=name, amount=action.amount)

    def _get_my_player(self) -> Optional[Player]:
        return self._get_player(self.my_player_id)

    def _get_player(self, player_id: int) -> Optional[Player]:
        for p in self._players:
            if p.player_id == player_id:
                return p
        return None
