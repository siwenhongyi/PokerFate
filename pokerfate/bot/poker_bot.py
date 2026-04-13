"""PokerFate main bot: integrates preflop, postflop, GTO, and opponent modeling."""

from __future__ import annotations
from typing import List, Optional, Dict

from pokerfate.core.card import Card
from pokerfate.core.game_state import GameState, Player, Street, Action, ActionType
from pokerfate.core.hand_evaluator import HandEvaluator, HandRank
from pokerfate.core.equity import EquityCalculator
from pokerfate.strategy.draw_utils import is_drawing_heavy
from pokerfate.strategy.preflop import PreflopStrategy
from pokerfate.strategy.postflop import PostflopStrategy
from pokerfate.strategy.gto import GTOMath
from pokerfate.strategy.range_estimator import HandRangeEstimator
from pokerfate.strategy.range_hands import two_stage_hole_combos
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
        use_range_equity: bool = True,
    ):
        self.name = name
        self.equity_calc = EquityCalculator()
        self.preflop = PreflopStrategy()
        self.postflop = PostflopStrategy(aggression=aggression)
        self.gto = GTOMath()
        self.opponent_model = OpponentModel()
        self.range_estimator = HandRangeEstimator()
        self.equity_iterations = equity_iterations
        self.use_range_equity = use_range_equity   # True=range模式, False=GTO+EQR模式(同mingli分支)
        self._last_equity: float = 0.5
        self._last_equity_random: float = 0.5
        self._last_spr: float = 0.0
        self._last_equity_mode: str = "mc_eqr"
        self._last_reasoning: str = ""
        self._last_gto_refs: dict | None = None
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
        raw_mc = self._get_equity(player.hole_cards, gs.board, max(num_opponents, 1))
        self._last_equity_random = raw_mc
        self._last_equity = raw_mc
        self._last_spr = self.gto.spr(stack, max(gs.pot, 0.01))
        self._last_equity_mode = "preflop_mc"

        # Determine what action we're facing
        facing_action, open_raise = self._classify_preflop_action(gs, player)

        # 翻前面对加注时使用 range equity 作为决策依据（random 仅供参考对比）
        opp_ids = [p.player_id for p in gs.active_players if p.player_id != player.player_id]
        if self.use_range_equity and opp_ids and facing_action in ('open', '3bet', '4bet'):
            two_stage_rfs = {pid: self.range_estimator.get_two_stage_rf(pid) for pid in opp_ids}
            primary_opp_id = gs.aggressor_opponent_id(player)
            if primary_opp_id is not None and primary_opp_id in two_stage_rfs:
                target_preflop_rf, _ = two_stage_rfs[primary_opp_id]
            else:
                target_preflop_rf = min(v[0] for v in two_stage_rfs.values())
            if target_preflop_rf < 0.99:
                exclude = set(player.hole_cards)
                # 4bet/3bet 范围极化（价值 + 诈唬），open 范围线性
                polarized_pf = facing_action in ('3bet', '4bet')
                pf_opp_hands = two_stage_hole_combos(
                    target_preflop_rf, 1.0, exclude, [],
                    polarized=polarized_pf,
                )
                if pf_opp_hands:
                    pf_range_eq = self.equity_calc.calculate_vs_top_range_multi(
                        player.hole_cards, [], max(num_opponents, 1),
                        pf_opp_hands, self.equity_iterations,
                    )
                    self._last_equity = pf_range_eq
                    self._last_equity_mode = "range_top"

        # is_bb_option: explicit server signal (forced_post + call_need==0)
        # Auto-detect fallback: BB position + no raises + nothing to call = free check option
        auto_detect_bb = (position == 'BB' and facing_action == 'none' and to_call == 0)
        is_big_blind = is_bb_option or auto_detect_bb
        num_limpers = self._count_limpers(gs, player) if facing_action == 'none' else 0

        stack_bb = stack / bb if bb > 0 else 100.0
        villain_pos = self._primary_raiser_position(gs, player) if facing_action in ('open', '3bet', '4bet') else ''
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
            stack_bb=stack_bb,
            villain_position=villain_pos,
        )

        self._last_reasoning = self._preflop_reasoning(
            player.hole_cards,
            position,
            facing_action,
            action_str,
            num_limpers,
            stack_bb=stack_bb,
            big_blind=bb,
        )
        self._last_gto_refs = self._lookup_preflop_gto(
            gs, player, position, facing_action, num_limpers,
        )
        return self._to_action(action_str, amount, to_call, stack)

    def _classify_preflop_action(self, gs: GameState, player: Player):
        """Returns (facing_action_str, open_raise_amount).

        Uses total raise count (including bot's own raises) to determine the
        true bet level, so that bot's 3bet + opponent's re-raise is correctly
        identified as a 4bet rather than a 3bet.
        """
        history = gs.action_history
        opp_raises = []
        total_raise_count = 0
        for item in history:
            pid, act = item[0], item[1]
            if act.action_type == ActionType.RAISE:
                total_raise_count += 1
                if pid != player.player_id:
                    opp_raises.append((pid, act))
        if not opp_raises:
            return 'none', 0.0
        # total_raise_count includes bot's raises, giving the true bet level:
        # 1 total raise  → open (bot hasn't acted yet)
        # 2 total raises → 3bet facing bot (open + bot's raise, or open + opponent 3bet)
        # 3 total raises → 4bet (open + 3bet + 4bet)
        if total_raise_count == 1:
            return 'open', opp_raises[-1][1].amount
        if total_raise_count == 2:
            return '3bet', opp_raises[-1][1].amount
        return '4bet', opp_raises[-1][1].amount

    def _count_limpers(self, gs: GameState, player: Player) -> int:
        """Count opponents who called (limped) preflop without raising."""
        n = 0
        for item in gs.action_history:
            pid, act = item[0], item[1]
            if act.action_type == ActionType.CALL and pid != player.player_id:
                n += 1
        return n

    # ------------------------------------------------------------------
    # Postflop logic
    # ------------------------------------------------------------------

    def _decide_postflop(self, gs: GameState, player: Player) -> Action:
        self._last_gto_refs = None  # 翻后不打印 GTO 翻前参考行
        board = gs.board
        to_call = gs.to_call(player)
        stack = player.stack
        pot = gs.pot
        is_ip = gs.is_ip(player)
        street = str(gs.street)
        bb = gs.big_blind
        # can_act 排除 all-in 玩家：all-in 对手无法弃牌/跟注，不影响下注的折叠价值计算
        num_opponents = sum(1 for p in gs.active_players
                           if p.player_id != player.player_id and p.can_act())
        facing_bet = to_call > 0

        # Opponents still in the hand + exploit target: last aggressor, else best profile among limpers
        opp_ids = [p.player_id for p in gs.active_players if p.player_id != player.player_id]
        primary_opp_id = gs.aggressor_opponent_id(player)
        if primary_opp_id is None:
            primary_opp_id = self.opponent_model.preferred_exploit_target(opp_ids)

        raw_mc = self._get_equity(player.hole_cards, board, max(num_opponents, 1))
        self._last_equity_random = raw_mc

        # 两阶段 rf：翻前行动压缩 + 翻后行动在翻前范围内的二次裁切
        # facing_bet=True：用主要对手（加注者）的 rf——该玩家决定了我们的决策上下文；
        # 取 min 会错误地把范围估得比实际更窄（当存在 limper 时尤其严重）。
        # facing_bet=False（主动下注）：用 min 保守估计，避免高估胜率冒进。
        if opp_ids:
            two_stage_rfs = {pid: self.range_estimator.get_two_stage_rf(pid) for pid in opp_ids}
            if facing_bet and primary_opp_id is not None and primary_opp_id >= 0 and primary_opp_id in two_stage_rfs:
                # 用加注者的 rf
                target_preflop_rf, target_postflop_rf = two_stage_rfs[primary_opp_id]
            else:
                # 保守：取所有对手的 min
                pf_rfs = [v[0] for v in two_stage_rfs.values()]
                po_rfs = [v[1] for v in two_stage_rfs.values()]
                target_preflop_rf = min(pf_rfs)
                target_postflop_rf = min(po_rfs)
        else:
            target_preflop_rf = 1.0
            target_postflop_rf = 1.0
        min_rf = target_preflop_rf * target_postflop_rf  # 组合 rf，用于 use_range 判断

        # polarized=True 对应 raise 范围（价值手 + 诈唬），False 对应 call 范围（线性）
        if primary_opp_id is not None and primary_opp_id >= 0:
            last_action = self.range_estimator.last_postflop_action(primary_opp_id)
            polarized = last_action == 'raise'
        else:
            polarized = facing_bet  # 面对下注时默认 polarized

        use_range = self.use_range_equity and bool(board) and min_rf < 0.99 and opp_ids
        range_eq: float | None = None
        if use_range:
            exclude = set(player.hole_cards) | set(board)
            opp_hands = two_stage_hole_combos(
                target_preflop_rf, target_postflop_rf, exclude, board,
                polarized=polarized, street=street,
            )
            # 只要候选手牌非空就使用 range equity：range 越紧（opp_hands 越少）
            # 反而说明对手范围越确定，信息量越高，不应该回退到 EQR。
            # MC 采样时会从候选列表随机选取，即使候选只有几个也是有效的。
            if opp_hands:
                range_eq = self.equity_calc.calculate_vs_top_range_multi(
                    player.hole_cards,
                    board,
                    num_opponents,
                    opp_hands,
                    self.equity_iterations,
                )

        if range_eq is not None:
            call_equity = range_eq
            discount = 1.0
            self._last_equity_mode = "range_top"
        else:
            discount = self.range_estimator.worst_discount(opp_ids)
            call_equity = max(
                0.0,
                raw_mc - (1.0 - discount) * (1.0 - raw_mc),
            )
            self._last_equity_mode = "mc_eqr"

        equity = call_equity
        self._last_equity = equity

        # Get exploit adjustments
        adj = self.opponent_model.exploit_adjustments(primary_opp_id) if primary_opp_id >= 0 else {}
        opp_fold_rate = self._adjusted_fold_rate(primary_opp_id, adj)

        # 当 range equity 被大幅压缩时，对手本手处于强手范围，实际弃牌率远低于历史统计。
        # compression = range_equity / raw_equity：越接近 0 说明对手越强、越不会弃牌。
        # 调整后的弃牌率用于诈唬判断，防止在对手持有强手范围时仍尝试诈唬。
        # 公式：adjusted = historical × min(1, compression + 0.20)
        #   compression=1.0（无压缩）→ adjusted = historical（不变）
        #   compression=0.25（严重压缩）→ adjusted ≈ historical × 0.45
        if raw_mc > 0:
            compression = equity / raw_mc
            opp_fold_rate = opp_fold_rate * min(1.0, compression + 0.20)

        # Apply exploitative adjustments to postflop sizing
        self.postflop.aggression = self._compute_aggression(adj)
        self.postflop.value_mult = self._compute_value_mult(adj)

        spr = self.gto.spr(stack, max(pot, 0.01))
        self._last_spr = spr

        value_only = adj.get('cbet_freq') == 'value_only'
        pos = gs.position_of(player)

        # 方案 A：大注+低 SPR 时收紧成牌跟注；听牌保留隐含赔率
        pot_odds_pre = to_call / (pot + to_call) if to_call > 0 else 0.0
        is_dh = (
            bool(board)
            and len(board) >= 3
            and facing_bet
            and is_drawing_heavy(player.hole_cards, board)
        )
        facing_large_bet = facing_bet and to_call > 0 and pot_odds_pre >= 0.30 and spr < 5.0
        exploit_tighten_call = bool(value_only and facing_large_bet)

        # Street-level AFq adjustments: widen call range when opponent's betting
        # range on that street is known to be wide (more bluffs included).
        effective_equity = equity
        if facing_bet:
            if street == 'flop' and adj.get('flop_float_favorable'):
                # Opponent bets flop widely → float more, plan to take pot on turn
                effective_equity = min(equity + 0.05, 1.0)
            elif street == 'turn' and adj.get('turn_bluff_then_fold'):
                # Opponent barrels turn then gives up river → call turn more liberally
                effective_equity = min(equity + 0.05, 1.0)
            elif street == 'river':
                if adj.get('river_bluff_likely'):
                    effective_equity = min(equity + 0.07, 1.0)
                elif adj.get('river_bet_rare'):
                    effective_equity = max(equity - 0.05, 0.0)

        action_str, amount = self.postflop.decide(
            equity=effective_equity,
            raw_equity=raw_mc,
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
            position=pos,
            is_drawing_heavy=is_dh,
            facing_large_bet=facing_large_bet,
            exploit_tighten_call=exploit_tighten_call,
        )

        # 下注金额不超过可以行动的对手中筹码最多的那个（超出无意义）
        if action_str == 'raise' and amount > 0:
            acting_opp_stacks = [p.stack for p in gs.active_players
                                 if p.player_id != player.player_id and p.can_act()]
            if acting_opp_stacks:
                max_opp_stack = max(acting_opp_stacks)
                amount = min(amount, max_opp_stack)

        use_calibration = (
            primary_opp_id >= 0
            and self.range_estimator.has_calibration(primary_opp_id)
        )

        # 对手标签日志：类型 + PWI + 关键 adj 信号摘要
        opp_label = ""
        adj_summary = ""
        if primary_opp_id >= 0:
            opp_stats = self.opponent_model.get(primary_opp_id)
            opp_name = self.opponent_model._id_to_name.get(primary_opp_id, f"P{primary_opp_id}")
            ptype = opp_stats.player_type()
            pwi = opp_stats.pwi()
            opp_label = f"{opp_name}/{ptype}/PWI{pwi:+.0f}"
            # 提炼最关键的 adj 信号，不是全部堆出来
            sig_parts = []
            if adj.get('bluff_freq') == 'none':
                sig_parts.append("禁诈唬")
            elif adj.get('bluff_freq') == 'high':
                sig_parts.append("多诈唬")
            elif adj.get('bluff_freq') == 'low':
                sig_parts.append("少诈唬")
            if adj.get('cbet_freq') == 'value_only':
                sig_parts.append("纯价值")
            elif adj.get('cbet_freq') == 'high':
                sig_parts.append("高频cbet")
            if adj.get('value_sizing') == 'large':
                sig_parts.append("加大注码")
            scale = adj.get('aggression_scale', 1.0)
            if scale != 1.0:
                sig_parts.append(f"ag×{scale:.2f}")
            if adj.get('river_bluff_likely'):
                sig_parts.append("河牌可能诈唬")
            if adj.get('river_bet_rare'):
                sig_parts.append("河牌下注=强")
            if adj.get('flop_float_favorable'):
                sig_parts.append("翻牌可浮牌")
            if adj.get('turn_bluff_then_fold'):
                sig_parts.append("转牌诈唬放弃")
            adj_summary = "/".join(sig_parts)

        self._last_reasoning = self._postflop_reasoning(
            player.hole_cards,
            equity,
            is_ip,
            facing_bet,
            to_call,
            pot,
            opp_fold_rate,
            board,
            action_str,
            raw_equity=raw_mc,
            discount=discount,
            streets_bet=self.range_estimator.streets_bet(primary_opp_id) if primary_opp_id >= 0 else 0,
            street=street,
            use_calibration=use_calibration,
            spr=spr,
            position=pos,
            equity_mode=self._last_equity_mode,
            min_rf=min_rf,
            num_opp=num_opponents,
            opp_label=opp_label,
            adj_summary=adj_summary,
        )
        return self._to_action(action_str, amount, to_call, stack)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _made_hand_label_cn(hole_cards: List[Card], board: List[Card]) -> str:
        """翻牌前：手牌范畴（如 AKs）；翻牌后：手牌+公牌组成的最优五张牌型中文（如 一对）。"""
        if len(hole_cards) < 2:
            return "未知"
        if not board:
            from pokerfate.strategy.preflop import _hand_category
            return _hand_category(hole_cards)
        combined = hole_cards + board
        if len(combined) < 5:
            return "未成牌"
        score = HandEvaluator.evaluate(combined)
        return HandRank(score[0]).cn_name()

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
        """将 exploit_adjustments 的方向 + 强度信号合并为 aggression 乘数。

        优先读取 aggression_scale（PWI 连续映射），再叠加方向信号微调：
          bluff_freq=none → 强制压低（纯价值）
          bluff_freq=high → 强制拉高（多诈唬）
          bluff_freq=low  → 小幅压低
        最终值 clamp 到 [0.3, 1.5]，与 postflop.should_cbet 的上限 1.55 衔接。
        """
        base = adj.get('aggression_scale', 1.0)
        bluff = adj.get('bluff_freq', '')
        if bluff == 'none':
            base = min(base, 0.5)   # 强制压低，不超过 0.5
        elif bluff == 'high':
            base = max(base, 1.2)   # 至少 1.2
        elif bluff == 'low':
            base = min(base, 0.8)
        return max(0.3, min(1.5, base))

    def _preflop_reasoning(
        self,
        hole_cards: List[Card],
        position: str,
        facing_action: str,
        action_str: str,
        num_limpers: int = 0,
        stack_bb: float = 100.0,
        big_blind: float = 2.0,
    ) -> str:
        from pokerfate.strategy.preflop import _hand_category, _3BET_VALUE
        cat = _hand_category(hole_cards)
        depth = GTOMath.stack_bb_category(stack_bb * big_blind, big_blind)
        if self._last_equity_mode == "range_top":
            rnd = f"vs随机{self._last_equity_random:.0%}"
            eq = f"胜率{self._last_equity:.0%}({rnd} range)"
        else:
            eq = f"胜率{self._last_equity:.0%}"
        facing_cn = {"none": "无开牌", "open": "面对开加", "3bet": "面对3bet", "4bet": "面对4bet"}
        facing = facing_cn.get(facing_action, facing_action)
        tag = "【GTOv2·翻前】"
        meta = f"深度{depth} {stack_bb:.0f}bb"

        if action_str == "check":
            limper_str = f"{num_limpers}人跟注" if num_limpers > 0 else "无人入局"
            return f"{tag} {cat} {position}免费看牌（{limper_str}）过牌 {eq} | {meta}"

        if action_str == "raise":
            if facing_action == "none":
                if position == "BB":
                    return f"{tag} {cat} BB {num_limpers}人limp→iso {eq} | {meta}"
                return f"{tag} {cat} {position} {facing}→开加 {eq} | {meta}"
            elif facing_action == "open":
                kind = "3bet价值" if cat in _3BET_VALUE else "3bet诈唬"
                return f"{tag} {cat} {facing}→{kind} {eq} | {meta}"
            elif facing_action == "3bet":
                return f"{tag} {cat} {facing}→4bet价值 {eq} | {meta}"
            else:
                return f"{tag} {cat} {facing}→5bet全押 {eq} | {meta}"
        elif action_str == "call":
            return f"{tag} {cat} {position} {facing}→跟注 {eq} | {meta}"
        else:
            return f"{tag} {cat} {position} {facing}→弃牌 {eq} | {meta}"

    def _postflop_reasoning(
        self,
        hole_cards: List[Card],
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
        use_calibration: bool = False,
        spr: float = 1.0,
        position: str = "MP",
        equity_mode: str = "mc_eqr",
        min_rf: float = 1.0,
        num_opp: int = 1,
        opp_label: str = "",
        adj_summary: str = "",
    ) -> str:
        from ..strategy.postflop import BoardTexture
        made = self._made_hand_label_cn(hole_cards, board)
        tag = "【GTOv2·翻后】"
        texture = BoardTexture(board)
        tex = "干燥" if texture.is_dry else ("湿润" if texture.is_wet else "中性")
        pos = "有位置" if is_ip else "无位置"
        pot_odds = to_call / (pot + to_call) if to_call > 0 else 0.0
        spr_lbl = GTOMath.spr_category(spr)
        mw = f"{num_opp}人底池" if num_opp > 1 else "单挑"

        if equity_mode == "range_top":
            rnd = f"{raw_equity:.0%}" if raw_equity is not None else "?"
            eq = f"决策胜率{equity:.0%}(vs随机{rnd} rf≤{min_rf:.0%}范围)"
        elif raw_equity is not None and discount < 0.92 and streets_bet > 0:
            cal_tag = "(校准)" if use_calibration else ""
            eq = f"决策胜率{equity:.0%}(EQR:原{raw_equity:.0%} {streets_bet}街{cal_tag})"
        else:
            eq = f"决策胜率{equity:.0%}"

        # 对手标签上下文：类型 + PWI + 关键 adj 信号
        opp_ctx = f" [{opp_label}]" if opp_label else ""
        adj_ctx = f" 调整:{adj_summary}" if adj_summary else ""

        head = f"{tag} {made} {position}/{mw} SPR≈{spr:.1f}({spr_lbl}) {tex}{opp_ctx}{adj_ctx}"

        if action_str == "raise":
            if facing_bet:
                role = "IP加注" if is_ip else "check-raise"
                return f"{head} {eq} {pos} 面对下注→{role}"
            else:
                if street == "river":
                    if equity >= 0.60:
                        return f"{head} {eq} 河牌价值下注"
                    elif equity >= 0.50:
                        return f"{head} {eq} 河牌薄价值"
                    else:
                        return f"{head} {eq} 诈唬(对手弃牌率{opp_fold_rate:.0%})"
                if equity >= 0.90:
                    return f"{head} {eq} 强牌下注"
                elif equity >= 0.60:
                    return f"{head} {eq} 价值持续下注"
                elif equity >= 0.30:
                    return f"{head} {eq} 半诈唬"
                else:
                    return f"{head} {eq} 纯诈唬(弃牌率{opp_fold_rate:.0%})"
        elif action_str == "call":
            return f"{head} {eq} 底池赔率{pot_odds:.0%}→跟注"
        elif action_str == "check":
            if equity >= 0.85:
                return f"{head} {eq} 强牌过牌控池"
            else:
                return f"{head} {eq} 过牌"
        else:  # fold
            return f"{head} {eq} 赔率{pot_odds:.0%}不足→弃牌"

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

    def observe_showdown(self, player_id: int, cards, name: str = "", board=None) -> None:
        """在 showdown 时记录对手底牌，校准其 raise 范围压缩系数。

        Parameters
        ----------
        player_id : int
        cards : list of Card or str
            对手亮出的底牌。
        name : str
            玩家名字，用于 showdown 校准器的 name key。
        board : list of Card or str, optional
            本手最终公牌，用于计算翻牌后实际手牌强度。
        """
        return self.range_estimator.observe_showdown(player_id, cards, name=name, board=board)

    def new_hand(self, player_ids: List[int], player_names: Optional[Dict[int, str]] = None):
        """Call at the start of each new hand.

        Parameters
        ----------
        player_ids : list of int
        player_names : dict, optional
            {player_id: name} — used to populate the range estimator's
            pid→name mapping so showdown calibration is keyed by name
            rather than seat ID (seats can be reused across sessions).
        """
        self._vpip_recorded.clear()
        self._pfr_recorded.clear()
        names = player_names or {}
        for pid in player_ids:
            self.opponent_model.record_hand_start(pid)
            # Reset range estimator: prior = historical VPIP (or 0.35 if unknown)
            stats = self.opponent_model.get(pid)
            prior = stats.vpip if stats.hands_seen >= 10 else 0.35
            # PFR/VPIP 比值：样本不足时用 GTO 参考值 0.75（不偏不倚）
            pfr_vpip = (stats.pfr / stats.vpip
                        if stats.hands_seen >= 10 and stats.vpip > 0
                        else 0.75)
            # 诈唬指标：用于 raise 压缩的诈唬例外判断
            bluff_wr = stats.bluff_win_rate
            bet_win_n = stats.bet_win_count
            river_bf_n = stats.river_bet_count + stats.river_check_count
            river_bf = stats.river_bet_frequency
            name = names.get(pid, self.opponent_model._id_to_name.get(pid, str(pid)))
            self.range_estimator.reset_hand(
                pid, prior_range=prior, name=name,
                pfr_vpip_ratio=pfr_vpip,
                bluff_win_rate=bluff_wr, bet_win_samples=bet_win_n,
                river_bet_freq=river_bf, river_bf_samples=river_bf_n,
            )

    @property
    def last_equity(self) -> float:
        return self._last_equity

    @property
    def last_equity_random(self) -> float:
        return self._last_equity_random

    @property
    def last_spr(self) -> float:
        return self._last_spr

    @property
    def last_equity_mode(self) -> str:
        return self._last_equity_mode

    @property
    def last_reasoning(self) -> str:
        return self._last_reasoning

    @property
    def last_gto_refs(self) -> dict | None:
        return self._last_gto_refs

    def _lookup_preflop_gto(
        self, gs: GameState, player: Player, position: str, facing_action: str,
        num_limpers: int = 0,
    ) -> dict | None:
        """查询翻前 GTO 参考数据，返回 {chart_key, hand, greenline, pekarstas}（展示用已格式化）。"""
        from pokerfate.strategy.preflop import _hand_category
        from pokerfate.data import lookup_gto, format_action
        try:
            hand = _hand_category(player.hole_cards)
            pos = self._normalize_pos(position)
            villain_pos = self._primary_raiser_position(gs, player)
            if facing_action == 'none':
                # 有人 limp 时用 ISO chart（隔离跛入者）；无人 limp 时用 RFI chart
                if num_limpers > 0:
                    chart_key = f"{pos}-ISO"
                else:
                    chart_key = f"{pos}-RFI"
            elif facing_action == 'open':
                chart_key = f"{pos}-vs-open-{villain_pos}" if villain_pos else ""
            elif facing_action == '3bet':
                chart_key = f"{pos}-vs-3bet-{villain_pos}" if villain_pos else ""
            elif facing_action == '4bet':
                chart_key = f"{pos}-vs-4bet-{villain_pos}" if villain_pos else ""
            else:
                chart_key = ""
            if not chart_key:
                return None
            refs = lookup_gto(chart_key, hand)
            return {
                "chart_key": chart_key,
                "hand": hand,
                "greenline": format_action(refs["greenline"]),
                "pekarstas": format_action(refs["pekarstas"]),
            }
        except Exception:
            return None

    # 将 position_of() 返回的原始位置名统一映射到 chart key 使用的 6-max 标准名
    _POS_NORMALIZE = {
        'UTG': 'UTG', 'UTG+1': 'MP', 'UTG+2': 'CO',
        'LJ': 'MP', 'HJ': 'CO', 'CO': 'CO',
        'BTN': 'BTN', 'SB': 'SB', 'BB': 'BB', 'MP': 'MP',
    }

    def _normalize_pos(self, raw: str) -> str:
        return self._POS_NORMALIZE.get(raw, raw)

    def _primary_raiser_position(self, gs: GameState, player: Player) -> str:
        """返回最后一个（相对于 hero）加注者的标准位置字符串，找不到时返回空字符串。"""
        raises = [
            item[0] for item in gs.action_history
            if len(item) >= 3
            and item[2] == 'preflop'
            and item[1].action_type == ActionType.RAISE
            and item[0] != player.player_id
        ]
        if not raises:
            return ""
        raiser = next((p for p in gs.players if p.player_id == raises[-1]), None)
        if raiser is None:
            return ""
        return self._normalize_pos(gs.position_of(raiser))
