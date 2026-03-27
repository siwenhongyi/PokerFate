"""PokerFate main bot: integrates preflop, postflop, GTO, and opponent modeling."""

from __future__ import annotations
import random
from typing import List, Optional, Tuple

from pokerfate.core.card import Card
from pokerfate.core.game_state import GameState, Player, Street, Action, ActionType
from pokerfate.core.equity import EquityCalculator
from pokerfate.strategy.preflop import PreflopStrategy
from pokerfate.strategy.postflop import PostflopStrategy
from pokerfate.strategy.gto import GTOMath
from pokerfate.strategy.range_estimator import HandRangeEstimator
from pokerfate.bot.opponent_model import OpponentModel


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
        self.range_estimator = HandRangeEstimator()
        self.equity_iterations = equity_iterations
        self._last_equity: float = 0.5
        self._last_reasoning: str = ""
        # Per-hand dedup guards: prevent counting VPIP/PFR more than once per player per hand
        self._vpip_recorded: set = set()
        self._pfr_recorded: set = set()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def decide(self, game_state: GameState, my_player_id: int = 0, *, player_id: int = None, is_bb_option: bool = False) -> Action:
        if player_id is not None:
            my_player_id = player_id
        """Main entry point: return the chosen Action given the game state."""
        player = self._find_player(game_state, my_player_id)
        if player is None or player.is_folded:
            return Action(ActionType.FOLD)

        if game_state.street == Street.PREFLOP:
            return self._decide_preflop(game_state, player, is_bb_option=is_bb_option)
        else:
            return self._decide_postflop(game_state, player)

    # ------------------------------------------------------------------
    # Preflop logic
    # ------------------------------------------------------------------

    def _decide_preflop(self, gs: GameState, player: Player, is_bb_option: bool = False) -> Action:
        position = gs.position_of(player)
        is_ip = gs.is_ip(player)
        bb = gs.big_blind
        to_call = gs.to_call(player)
        stack = player.stack

        # Calculate equity so last_equity is always meaningful
        num_opponents = len(gs.active_players) - 1
        self._last_equity = self._get_equity(player.hole_cards, gs.board, max(num_opponents, 1))

        # Determine what action we're facing
        facing_action, open_raise = self._classify_preflop_action(gs, player)

        # is_bb_option: server signal (forced_post + call_need==0), covers both regular BB and forced blind
        is_big_blind = is_bb_option
        num_limpers = self._count_limpers(gs, player) if facing_action == 'none' else 0

        action_str, amount = self.preflop.decide(
            hole_cards=player.hole_cards,
            position=position,
            facing_action=facing_action,
            open_raise=open_raise if open_raise else to_call,
            is_ip=is_ip,
            big_blind=bb,
            stack=stack,
            pot=gs.pot,
            is_big_blind=is_big_blind,
            num_limpers=num_limpers,
            equity=self._last_equity,
            to_call=to_call,
            num_players=len(gs.players),
            num_active_opponents=num_opponents,
        )

        self._last_reasoning = self._preflop_reasoning(
            player.hole_cards, position, facing_action, action_str, num_limpers
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

    def _count_limpers(self, gs: GameState, player: Player) -> int:
        """Count opponents who called (limped) preflop without raising."""
        return sum(
            1 for pid, act in gs.action_history
            if act.action_type == ActionType.CALL and pid != player.player_id
        )

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

        # Calculate raw MC equity (vs random hands)
        raw_equity = self._get_equity(player.hole_cards, board, num_opponents)

        # ── Libratus-inspired range compression ─────────────────────────────
        # Apply equity discount based on how aggressively opponents have acted.
        # When opponent bets multiple streets, their range compresses to strong
        # hands, making our raw MC equity (vs random) an over-estimate.
        # discount = f(range_fraction), see range_estimator.py for calibration.
        discount = self.range_estimator.worst_discount(opp_ids)
        equity = raw_equity * discount
        self._last_equity = equity

        # Get exploit adjustments
        adj = self.opponent_model.exploit_adjustments(primary_opp_id) if primary_opp_id >= 0 else {}
        opp_fold_rate = self._adjusted_fold_rate(primary_opp_id, adj)

        # Apply exploitative adjustments to postflop sizing
        self.postflop.aggression = self._compute_aggression(adj)
        self.postflop.value_mult = self._compute_value_mult(adj)

        spr = self.gto.spr(stack, max(pot, 0.01))

        value_only = adj.get('cbet_freq') == 'value_only'

        action_str, amount = self.postflop.decide(
            equity=equity,
            raw_equity=raw_equity,
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
            value_only=value_only,
        )

        self._last_reasoning = self._postflop_reasoning(
            equity, is_ip, facing_bet, to_call, pot, opp_fold_rate,
            board, action_str,
            raw_equity=raw_equity, discount=discount,
            streets_bet=self.range_estimator.streets_bet(primary_opp_id) if primary_opp_id >= 0 else 0,
            street=street,
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

    def _preflop_reasoning(
        self,
        hole_cards: List[Card],
        position: str,
        facing_action: str,
        action_str: str,
        num_limpers: int = 0,
    ) -> str:
        from pokerfate.strategy.preflop import _hand_category, _3BET_VALUE, _3BET_BLUFF
        cat = _hand_category(hole_cards)
        eq = f"胜率{self._last_equity:.0%}"
        facing_cn = {"none": "无开牌", "open": "面对开加", "3bet": "面对3bet", "4bet": "面对4bet"}
        facing = facing_cn.get(facing_action, facing_action)

        if action_str == "check":
            # BB checking for free when no one raised
            limper_str = f"{num_limpers}人跟注" if num_limpers > 0 else "无人入局"
            return f"{cat}  BB大盲免费看牌（{limper_str}）  不在iso加注范围，过牌  {eq}"

        if action_str == "raise":
            if facing_action == "none":
                if position == "BB":
                    return f"{cat}  BB  {num_limpers}人跟注 → iso加注，缩减底池人数  {eq}"
                return f"{cat}  {position}  {facing} → 在范围内，标准开加  {eq}"
            elif facing_action == "open":
                kind = "3bet价值" if cat in _3BET_VALUE else "3bet诈唬（阻挡强牌）"
                return f"{cat}  {facing} → {kind}  {eq}"
            elif facing_action == "3bet":
                return f"{cat}  {facing} → 4bet价值  {eq}"
            else:
                return f"{cat}  {facing} → 5bet全押  {eq}"
        elif action_str == "call":
            return f"{cat}  {position}  {facing} → 跟注（范围内或防守）  {eq}"
        else:
            return f"{cat}  {position}  {facing} → 不在范围，弃牌  {eq}"

    def _postflop_reasoning(
        self,
        equity: float,
        is_ip: bool,
        facing_bet: bool,
        to_call: float,
        pot: float,
        opp_fold_rate: float,
        board: List[Card],
        action_str: str,
        raw_equity: float = None,
        discount: float = 1.0,
        streets_bet: int = 0,
        street: str = "",
    ) -> str:
        from ..strategy.postflop import BoardTexture
        texture = BoardTexture(board)
        tex = "干燥" if texture.is_dry else ("湿润" if texture.is_wet else "中性")
        pos = "有位置" if is_ip else "无位置"
        pot_odds = to_call / (pot + to_call) if to_call > 0 else 0.0

        # Show range compression context when significant
        if raw_equity is not None and discount < 0.92 and streets_bet > 0:
            eq = f"胜率{equity:.0%}(原{raw_equity:.0%}→{streets_bet}街压缩)"
        else:
            eq = f"胜率{equity:.0%}"

        if action_str == "raise":
            if facing_bet:
                role = "IP价值加注，建底池" if is_ip else "check-raise价值/诈唬"
                return f"{eq}  {tex}牌面  {pos}  面对下注 → {role}"
            else:
                if street == "river":
                    if equity >= 0.60:
                        return f"{eq}  {tex}牌面  {pos}  面对过牌 → 河牌价值下注"
                    elif equity >= 0.50:
                        return f"{eq}  {tex}牌面  {pos}  面对过牌 → 河牌薄价值/混合下注"
                    else:
                        return f"{eq}  折叠率{opp_fold_rate:.0%}  面对过牌 → 河牌纯诈唬"
                if equity >= 0.90:
                    return f"{eq}  {tex}牌面  {pos}  面对过牌 → 强牌价值下注"
                elif equity >= 0.60:
                    return f"{eq}  {tex}牌面  {pos}  面对过牌 → 价值持续下注"
                elif equity >= 0.30:
                    return f"{eq}  {tex}牌面  {pos}  面对过牌 → 半诈唬（有摸牌出路）"
                else:
                    return f"{eq}  折叠率{opp_fold_rate:.0%}  面对过牌 → 纯诈唬"
        elif action_str == "call":
            return f"{eq} > 底池赔率{pot_odds:.0%}  {pos} → 跟注（有利赔率）"
        elif action_str == "check":
            if equity >= 0.85:
                return f"{eq}  强牌  面对过牌 → 慢打，保护过牌范围"
            else:
                return f"{eq}  {tex}牌面  {pos}  面对过牌 → 无注理由，过牌"
        else:  # fold
            return f"{eq} < 底池赔率{pot_odds:.0%}  {pos}  面对下注 → 无足够赔率，弃牌"

    def _compute_value_mult(self, adj: dict) -> float:
        """Bet-size multiplier: larger vs calling stations, normal otherwise."""
        if adj.get('value_sizing') == 'large':
            return 1.30   # 30% larger value bets vs calling stations / fish
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
                if player_id not in self._vpip_recorded:
                    self.opponent_model.record_vpip(player_id)
                    self._vpip_recorded.add(player_id)
                if player_id not in self._pfr_recorded:
                    self.opponent_model.record_pfr(player_id)
                    self._pfr_recorded.add(player_id)
        elif action.action_type == ActionType.CALL:
            if street == 'preflop':
                if player_id not in self._vpip_recorded:
                    self.opponent_model.record_vpip(player_id)
                    self._vpip_recorded.add(player_id)

        if is_3bet_spot:
            did_3bet = action.action_type == ActionType.RAISE
            self.opponent_model.record_3bet_opportunity(player_id, did_3bet)

        if is_cbet_spot:
            folded = action.action_type == ActionType.FOLD
            self.opponent_model.record_fold_to_cbet(player_id, folded)

        # Update range estimator for every opponent action
        self.range_estimator.observe_action(player_id, act, street)

    def new_hand(self, player_ids: List[int]):
        """Call at the start of each new hand."""
        self._vpip_recorded.clear()
        self._pfr_recorded.clear()
        for pid in player_ids:
            self.opponent_model.record_hand_start(pid)
            # Reset range estimator: prior = historical VPIP (or 0.35 if unknown)
            stats = self.opponent_model.get(pid)
            prior = stats.vpip if stats.hands_seen >= 10 else 0.35
            self.range_estimator.reset_hand(pid, prior_range=prior)

    @property
    def last_equity(self) -> float:
        return self._last_equity

    @property
    def last_reasoning(self) -> str:
        return self._last_reasoning
