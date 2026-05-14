"""PokerFate main bot: integrates preflop, postflop, GTO, and opponent modeling."""

from __future__ import annotations
import hashlib
import logging
from typing import List, Optional, Dict

from pokerfate.core.card import Card
from pokerfate.core.config import MIN_HANDS_FOR_CLASSIFICATION
from pokerfate.core.game_state import GameState, Player, Street, Action, ActionType
from pokerfate.core.hand_evaluator import HandEvaluator, HandRank
from pokerfate.core.equity import EquityCalculator
from pokerfate.core.position import normalize_position
from pokerfate.data import format_action, lookup_gto
from pokerfate.strategy.draw_utils import is_drawing_heavy
from pokerfate.strategy.preflop import PreflopStrategy, _3BET_VALUE, _hand_category
from pokerfate.strategy.postflop import BoardTexture, PostflopStrategy
from pokerfate.strategy.gto import GTOMath
from pokerfate.strategy.range_estimator import HandRangeEstimator
from pokerfate.bot.opponent_model import OpponentModel
from pokerfate.strategy.range_v2.action_model import ActionContext, ActionModel, PlayerProfile
from pokerfate.strategy.range_v2.bayesian_range_tracker import BayesianRangeTracker
from pokerfate.strategy.range_v2.range_equity_calculator import RangeEquityCalculator
from pokerfate.strategy.range_v2.showdown_learner import ShowdownLearner
from pokerfate.strategy.range_v2.hero_eq_calibrator import (
    HeroEquityCalibrator,
    classify_action_ctx_from_decision,
)
from pokerfate.strategy.range_v2.hand_categorizer import categorize_cards as _hero_categorize

log = logging.getLogger(__name__)


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
        use_range_equity: bool = True,
    ):
        self.name = name
        self.equity_calc = EquityCalculator()
        self.preflop = PreflopStrategy()
        self.postflop = PostflopStrategy()
        self.gto = GTOMath()
        self.opponent_model = OpponentModel()
        self.range_estimator = HandRangeEstimator()  # EQR mode only
        self.equity_iterations = equity_iterations
        self.use_range_equity = use_range_equity   # True=range_v2模式, False=EQR模式

        # Range V2 (completely independent from EQR)
        self._showdown_learner = ShowdownLearner()
        self._action_model = ActionModel(showdown_learner=self._showdown_learner)
        self._range_tracker = BayesianRangeTracker(self._action_model)
        self._range_equity_calc = RangeEquityCalculator()
        # Hero equity meta-calibrator (缺陷 C): tracks predicted-vs-actual
        # bias per (hero_bucket, street, n_opp) and shifts future raw eq by
        # historical mean bias. Mirrors ShowdownLearner but on the hero side.
        self._hero_eq_calibrator = HeroEquityCalibrator()
        self._current_board: List[Card] = []
        self._v2_action_history: Dict[int, list] = {}
        self._last_equity: float = 0.5
        self._last_equity_random: float = 0.5
        self._last_spr: float = 0.0
        self._last_equity_mode: str = "mc_eqr"
        self._last_reasoning: str = ""
        self._last_gto_refs: dict | None = None
        self._pending_decision_seed: Optional[int] = None
        self._last_decision_diagnostics: dict = {}
        # Per-hand dedup guards: prevent counting VPIP/PFR more than once per player per hand
        self._vpip_recorded: set = set()
        self._pfr_recorded: set = set()
        # P6/P9 – cross-street action tracking for delayed cbet / probe detection
        # {street: action_str} e.g. {'flop': 'check', 'turn': 'raise'}
        self._my_street_actions: dict = {}
        # {player_id: {street: action_str}} for primary opponent
        self._opp_street_actions: dict = {}

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
            action = self._decide_preflop(game_state, player, is_bb_option=is_bb_option)
        else:
            action = self._decide_postflop(game_state, player)
        self._pending_decision_seed = None
        return action

    def set_next_decision_seed(self, seed: Optional[int]) -> None:
        """Pin RNG/equity sampling for the next decision only."""
        self._pending_decision_seed = int(seed) if seed is not None else None
        pf_seed = self._seed_for('preflop_strategy')
        if pf_seed is not None:
            self.preflop._rng.seed(pf_seed)

    def _seed_for(self, label: str) -> Optional[int]:
        base = self._pending_decision_seed
        if base is None:
            return None
        digest = hashlib.blake2b(f"{base}:{label}".encode("utf-8"), digest_size=4).digest()
        seed = int.from_bytes(digest, "big")
        return seed or 1

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
        raw_seed = self._seed_for('preflop_raw')
        range_seed = self._seed_for('preflop_range')
        raw_mc = self._get_equity(
            player.hole_cards, gs.board, max(num_opponents, 1), seed=raw_seed,
        )
        self._last_equity_random = raw_mc
        self._last_equity = raw_mc
        self._last_spr = self.gto.spr(stack, max(gs.pot, 0.01))
        self._last_equity_mode = "preflop_mc"

        # Determine what action we're facing
        facing_action, open_raise = self._classify_preflop_action(gs, player)

        # 翻前面对加注时使用 range equity 作为决策依据（random 仅供参考对比）
        opp_ids = [p.player_id for p in gs.active_players if p.player_id != player.player_id]
        if self.use_range_equity and opp_ids and facing_action in ('open', '3bet', '4bet'):
            # Multi-range equity: each opponent uses their own Bayesian
            # distribution. The prior single-range weighted_equity call used
            # the primary raiser's range for ALL opponents — wrong in
            # multiway pots where callers / limpers have much wider ranges
            # than the raiser.
            opp_weights_list = [
                self._range_tracker.get_distribution(pid) for pid in opp_ids
            ]
            pf_range_eq = self._range_equity_calc.weighted_equity_multi(
                player.hole_cards, [], opp_weights_list,
                self.equity_iterations,
                seed=range_seed,
            )
            self._last_equity = pf_range_eq
            self._last_equity_mode = "range_v2"

        # is_bb_option: explicit server signal (forced_post + call_need==0)
        # Auto-detect fallback: BB position + no raises + nothing to call = free check option
        auto_detect_bb = (position == 'BB' and facing_action == 'none' and to_call == 0)
        is_big_blind = is_bb_option or auto_detect_bb
        num_limpers = self._count_limpers(gs, player) if facing_action == 'none' else 0

        stack_bb = stack / bb if bb > 0 else 100.0
        villain_pos = self._primary_raiser_position(gs, player) if facing_action in ('open', '3bet', '4bet') else ''
        callers_after_last_raise = self._count_callers_after_last_preflop_raise(gs, player)
        squeeze_callers = callers_after_last_raise if facing_action == 'open' else 0
        cold_callers = callers_after_last_raise if facing_action in ('3bet', '4bet') else 0
        sticky_density = self._preflop_sticky_density(gs, player)
        fourbet_call_edge_adjust = self._preflop_4bet_call_edge_adjust(
            gs, player, facing_action,
        )
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
            sticky_density=sticky_density,
            cold_callers=cold_callers,
            squeeze_callers=squeeze_callers,
            fourbet_call_edge_adjust=fourbet_call_edge_adjust,
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
        preflop_expand_reason = getattr(self.preflop, 'last_expand_reason', '')
        if preflop_expand_reason:
            self._last_reasoning += f" | {preflop_expand_reason}"
        self._last_gto_refs = self._lookup_preflop_gto(
            gs, player, position, facing_action, num_limpers,
        )
        self._my_street_actions['preflop'] = action_str
        self._last_decision_diagnostics = {
            'street': 'preflop',
            'decision_seed': self._pending_decision_seed,
            'equity_seed': raw_seed,
            'range_equity_seed': range_seed,
            'equity_mc': raw_mc,
            'equity_range': self._last_equity,
            'equity_mode': self._last_equity_mode,
            'facing_action': facing_action,
            'action': action_str,
            'amount': amount,
            'fourbet_call_edge_adjust': fourbet_call_edge_adjust,
            'position': position,
            'num_active_opponents': num_opponents,
            'sticky_density': sticky_density,
            'cold_callers': cold_callers,
            'squeeze_callers': squeeze_callers,
            'preflop_expand_reason': preflop_expand_reason,
        }
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

    def _count_callers_after_last_preflop_raise(self, gs: GameState, player: Player) -> int:
        """Count non-hero callers after the latest preflop raise."""
        last_raise_idx = -1
        for idx, item in enumerate(gs.action_history):
            if len(item) < 3 or item[2] != 'preflop':
                continue
            if item[1].action_type == ActionType.RAISE:
                last_raise_idx = idx
        if last_raise_idx < 0:
            return 0
        n = 0
        for item in gs.action_history[last_raise_idx + 1:]:
            if len(item) < 3 or item[2] != 'preflop':
                continue
            pid, act = item[0], item[1]
            if pid != player.player_id and act.action_type == ActionType.CALL:
                n += 1
        return n

    def _preflop_sticky_density(self, gs: GameState, player: Player) -> float:
        """Share of active opponents with sticky/value-lean profile."""
        opp_ids = [
            p.player_id for p in gs.active_players
            if p.player_id != player.player_id
        ]
        if not opp_ids:
            return 0.0
        from pokerfate.strategy.v3.exploit import aggregate_villain_stats
        stats = [self.opponent_model.get(pid).to_villain_stats() for pid in opp_ids]
        _, _, _, _, n_sticky = aggregate_villain_stats(stats)
        return max(0.0, min(1.0, n_sticky / max(1, len(stats))))

    def _preflop_4bet_call_edge_adjust(
        self, gs: GameState, player: Player, facing_action: str,
    ) -> float:
        """Adjustment to 4bet-call edge gates; negative loosens, positive tightens."""
        if facing_action != '4bet':
            return 0.0
        opp_id = gs.last_aggressor_id(player.player_id, street='preflop')
        if opp_id is None:
            return 0.0
        stats = self.opponent_model.get(opp_id)
        if stats.hands_seen < MIN_HANDS_FOR_CLASSIFICATION:
            return 0.0

        vpip = stats.vpip
        pfr = stats.pfr
        af = stats.aggression_factor
        three_bet = stats.three_bet_pct
        gap = vpip - pfr
        ptype = stats.player_type()

        if ptype == 'maniac' or three_bet >= 0.14 or (pfr >= 0.28 and af >= 1.6):
            return -0.03
        if three_bet >= 0.10 or (vpip >= 0.34 and pfr >= 0.22 and af >= 1.3):
            return -0.02
        if pfr <= 0.12 and af < 1.3:
            return 0.03
        if pfr <= 0.16 and gap >= 0.18:
            return 0.02
        return 0.0

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

        raw_seed = self._seed_for('postflop_raw')
        range_seed = self._seed_for('postflop_range')
        engine_seed = self._seed_for('postflop_engine')
        raw_mc = self._get_equity(
            player.hole_cards, board, max(num_opponents, 1), seed=raw_seed,
        )
        self._last_equity_random = raw_mc

        if self.use_range_equity and bool(board) and opp_ids:
            # ── Range V2 path ──
            # 方案 D (2026-04-21): 多人底池用 weighted_equity_multi，每个对手采自己的
            # range。这**不是**之前被回滚的"weighted_equity(num_opponents>N)"bug
            # ——那个是"所有对手共用 primary_opp 一个 range"，会过度计算去除效应。
            # weighted_equity_multi 的签名是 List[np.ndarray]，每个对手独立 range。
            #
            # 修的问题: 5 人池 K-Q 高在 A-7-5 日志显示 "胜率 56%(vs随机 16%)"——
            # 老 1v1 代码只对 primary_opp 的 post-check 软化 range 算胜率，忽略
            # 其它 3-4 个对手任一人中 A 即 hero 败。新代码每人自己的 range 独立采。
            target_opp = primary_opp_id if (primary_opp_id is not None and primary_opp_id >= 0) else opp_ids[0]
            if len(opp_ids) == 1:
                opp_weights = self._range_tracker.get_distribution(target_opp)
                range_eq = self._range_equity_calc.weighted_equity(
                    player.hole_cards, board, opp_weights,
                    1, self.equity_iterations,
                    seed=range_seed,
                )
            else:
                # 每个活跃对手（含 all-in，因 all-in 对手仍参与摊牌）各自的 range。
                multi_weights = [
                    self._range_tracker.get_distribution(pid) for pid in opp_ids
                ]
                range_eq = self._range_equity_calc.weighted_equity_multi(
                    player.hole_cards, board, multi_weights,
                    self.equity_iterations,
                    seed=range_seed,
                )
            # Meta-calibration (缺陷 C): 拿 range_eq 之前补一层事后校准——
            # 历史 (hero_bucket, street, n_opp, action_ctx) 下 raw_eq vs 摊牌
            # 实际胜率的平均 bias 加回。action_ctx 区分"passive / bet / raise"
            # 三种 tracker 压缩强度档位，防止 bet/raise 场景下的大 bias 被
            # passive 样本稀释（参见 docs/多对手重构/plan.md）。
            hero_bucket = _hero_categorize(list(player.hole_cards), list(board))
            action_ctx = classify_action_ctx_from_decision(
                facing_bet=facing_bet, to_call=to_call, pot=pot,
            )
            range_eq = self._hero_eq_calibrator.calibrate(
                range_eq, hero_bucket, street, len(opp_ids),
                action_ctx=action_ctx,
            )
            call_equity = range_eq
            discount = 1.0
            min_rf = self._range_tracker.get_effective_range_pct(target_opp)
            self._last_equity_mode = "range_v2"
        else:
            # ── EQR path (completely independent) ──
            discount = self.range_estimator.worst_discount(opp_ids)
            min_rf = self.range_estimator.get_range_fraction(
                primary_opp_id if (primary_opp_id is not None and primary_opp_id >= 0) else -1
            )
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
        if raw_mc > 0:
            compression = equity / raw_mc
            opp_fold_rate = opp_fold_rate * min(1.0, compression + 0.20)

        # Exploit signals (aggression_scale / value_ag / bluff_ag / value_mult /
        # is_station_sizing) no longer flow through PostflopStrategy — v3 engine
        # reads villain signals directly from ctx.villain_stats. The `adj` dict
        # is still consumed for opp_fold_rate adjustment (below, via
        # `_adjusted_fold_rate`) and for log summary only.

        # Effective stack for SPR (aggressor-first).
        #
        # SPR drives geometric bet-size cap in postflop.bet_size plus the
        # facing_large_bet / implied_odds / shallow-SPR gates. An
        # over-estimated SPR inflates all of them in lockstep.
        #
        # Rule:
        #   1. If an aggressor exists on this hand, bind SPR to that
        #      opponent — they're the player we're actually contesting.
        #   2. Otherwise fall back to the shortest live (can_act) opponent.
        #      All-in opponents are excluded because they can't fold/call,
        #      so they don't constrain our remaining chips-in-play.
        #   3. If hero is the shortest, hero's own committed amount wins.
        #
        # Motivation (from logs/20.log regression): max(opponent_totals)
        # inflated SPR 2-3x when a deep bystander sat behind a short raiser;
        # geo_cap then picked bet sizes that couldn't be realised against
        # the real opponent.
        my_committed = stack + getattr(player, 'current_bet', 0.0)
        spr_aggressor_id = gs.aggressor_opponent_id(player)
        aggressor_total: Optional[float] = None
        if spr_aggressor_id is not None:
            agg = self._find_player(gs, spr_aggressor_id)
            if agg is not None and agg.can_act():
                aggressor_total = agg.stack + getattr(agg, 'current_bet', 0.0)

        if aggressor_total is not None:
            effective_stack = min(my_committed, aggressor_total)
        else:
            opponent_totals = [
                p.stack + getattr(p, 'current_bet', 0.0)
                for p in gs.active_players
                if p.player_id != player.player_id and p.can_act()
            ]
            effective_stack = (
                min([my_committed] + opponent_totals)
                if opponent_totals else my_committed
            )

        spr = self.gto.spr(effective_stack, max(pot, 0.01))
        self._last_spr = spr

        # value_only 语义 = "对手不会弃牌，我们该走纯价值"。原先由 adj
        # 的离散字段 cbet_freq=='value_only' 触发（来自 ptype=='whale/fish/
        # station'）。现在用连续指标：bluff_ag_scale 很低（诈唬 EV 差）
        # 或 sticky 证据充分。与 _adjusted_fold_rate 保持判据一致。
        value_only = adj.get('bluff_ag_scale', 0.55) < 0.18
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

        # ── P3: measured fold-to-cbet (more specific than generic fold_rate) ──
        fold_to_cbet_val: float | None = None
        if primary_opp_id >= 0:
            opp_stats = self.opponent_model.get(primary_opp_id)
            if opp_stats.fold_to_cbet_opps >= 5:
                fold_to_cbet_val = opp_stats.fold_to_cbet

        # ── P8: opponent AF ──────────────────────────────────────────────
        opp_af = 1.5
        if primary_opp_id >= 0:
            opp_af = self.opponent_model.get(primary_opp_id).aggression_factor

        # ── P1: nut advantage heuristic ──────────────────────────────────
        # 2026-04-25 修 P0 bug：原公式 (equity - raw_mc) / 0.25 在多人池恒负
        # → clamp 到 0 → overbet_value / overbet_raise_jam 永远死代码。
        #
        # 原定义问题：range_eq 是多人池 weighted eq（恒低于 raw_mc），两者
        # 不同尺度不能相减。
        #
        # 新定义：hero 当前手牌 bucket 强度 - villain range 的加权平均强度。
        # 这是 range-vs-range 的"hero 占据 range 高端"连续指标。
        # Bucket 强度 mapping（离散 → [0,1]）：
        #   air=0.0 / weak_draw=0.2 / draw=0.3 / medium=0.5 / strong=0.7 / nuts=1.0
        _BUCKET_RANK = {'air': 0.0, 'weak_draw': 0.2, 'draw': 0.3,
                        'medium': 0.5, 'strong': 0.7, 'nuts': 1.0}
        hero_bucket = _hero_categorize(
            list(player.hole_cards), list(board)
        ) if (self.use_range_equity and bool(board)) else 'medium'
        hero_strength = _BUCKET_RANK.get(hero_bucket, 0.5)
        # Villain range 平均强度：优先 primary_opp 的 bucket_dist（已在 P26
        # 之前计算）；cold start 时默认 0.4（略低于均值，匹配未知对手偏弱）
        v_bucket_dist: Dict[str, float] = {}
        if (self.use_range_equity and bool(board)
                and primary_opp_id is not None and primary_opp_id >= 0):
            try:
                v_bucket_dist = self._range_tracker.get_bucket_distribution(
                    primary_opp_id, board,
                )
            except Exception:
                log.exception(
                    "range bucket distribution failed for opponent=%s board=%s",
                    primary_opp_id,
                    [str(c) for c in board],
                )
                v_bucket_dist = {}
        if v_bucket_dist:
            villain_strength = sum(
                _BUCKET_RANK.get(b, 0.5) * float(p)
                for b, p in v_bucket_dist.items()
            )
        else:
            villain_strength = 0.4
        nut_adv = max(0.0, min(1.0, hero_strength - villain_strength))

        # ── P6: delayed c-bet detection ─────────────────────────────────
        # True when: I was the preflop aggressor, checked flop, now it's turn (no bet)
        prev_street = {'turn': 'flop', 'river': 'turn'}.get(street, '')
        is_delayed_cbet = (
            not facing_bet
            and prev_street != ''
            and self._my_street_actions.get(prev_street) == 'check'
        )

        # ── P9: opponent IP check-back detection ────────────────────────
        # True when primary opponent (who was IP) checked back last street
        opponent_checked_back = False
        if primary_opp_id is not None and primary_opp_id >= 0 and prev_street:
            opp_prev = self._opp_street_actions.get(primary_opp_id, {}).get(prev_street)
            if opp_prev == 'check' and not facing_bet:
                opponent_checked_back = True

        # ── P5: pass last flop bet fraction for multi-street consistency ─
        last_bet_frac_val = self.postflop._last_bet_frac if self.postflop._last_bet_street == 'flop' else 0.0
        prev_resistance = self._prev_bet_resistance(
            prev_street, num_opponents, last_bet_frac_val,
        )

        # ── P26: villain bucket_dist['nuts'] for call tightening.
        # Only nuts% is used now — strong% was for the removed zero_bluff gate.
        villain_nuts_pct = 0.0
        if (self.use_range_equity
                and bool(board)
                and primary_opp_id is not None
                and primary_opp_id >= 0):
            try:
                bucket_dist = self._range_tracker.get_bucket_distribution(
                    primary_opp_id, board,
                )
                villain_nuts_pct = float(bucket_dist.get('nuts', 0.0) or 0.0)
            except Exception:
                log.exception(
                    "villain nuts bucket lookup failed for opponent=%s board=%s",
                    primary_opp_id,
                    [str(c) for c in board],
                )
                villain_nuts_pct = 0.0

        villain_vs_hero_dist: Dict[str, float] = {}
        if (self.use_range_equity
                and len(board) >= 5
                and primary_opp_id is not None
                and primary_opp_id >= 0):
            try:
                villain_vs_hero_dist = self._range_tracker.get_vs_hero_dist(
                    primary_opp_id, board, list(player.hole_cards),
                )
            except Exception:
                log.exception(
                    "villain vs hero distribution failed for opponent=%s board=%s",
                    primary_opp_id,
                    [str(c) for c in board],
                )
                villain_vs_hero_dist = {}

        # Replace fixed equity bumps with dynamic pot-odds threshold adjustment.
        # This keeps "equity" as a model estimate while exploit reads move "need".
        exploit_need_adjust = 0.0
        if facing_bet and primary_opp_id >= 0:
            opp_stats = self.opponent_model.get(primary_opp_id)
            exploit_need_adjust = self._compute_call_need_adjust(
                street=street,
                opp_stats=opp_stats,
                is_drawing_heavy=is_dh,
                pot_odds=pot_odds_pre,
                num_opponents=num_opponents,
            )

        # 构造完整 VillainStats 直传给 v3 engine。
        # 以前 postflop.decide 只从 opp_af / fold_to_cbet / value_only 几个
        # 散标量拼残缺版，导致 exploit.py 的 _trap_lean（需要 hands_seen +
        # bet_win_count）、_value_lean 的 wtsd 路、_bluff_lean 的 wtsd 路
        # 在生产 hot path 全部无法触发。改为直接把 OpponentStats 的完整
        # 字段传下去，让连续指标驱动真正在线上生效。
        villain_stats_full = None
        if primary_opp_id >= 0:
            villain_stats_full = self.opponent_model.get(primary_opp_id).to_villain_stats()

        # 缺陷 A 第 1 步：聚合桌上所有活跃对手的 stats，喂给 ctx 的
        # multi-opponent summary 字段。RISK_PURPOSES（bluff_catch_call /
        # thin_value_bet / thick_value_bet / value_raise）会读 worst 而非
        # primary，防止 primary 被识别为 LAG 时错误地对粘手对手 bluff-catch。
        from pokerfate.strategy.v3.exploit import aggregate_villain_stats
        all_villain_stats = [
            self.opponent_model.get(pid).to_villain_stats() for pid in opp_ids
        ]
        worst_vs, max_vl, max_tl, max_bl, n_sticky = aggregate_villain_stats(
            all_villain_stats
        )

        # is_pfr: hero 是否为 preflop 最后加注者。
        # _my_street_actions['preflop'] 在 poker_bot 每次 hero 决策后被覆写；
        # preflop 最后一次动作如果是 raise 则 hero 是 PFR，否则不是（call/check/fold 均非）。
        hero_is_pfr = self._my_street_actions.get('preflop') == 'raise'

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
            fold_to_cbet=fold_to_cbet_val,
            spr=spr,
            value_only=value_only,
            position=pos,
            is_drawing_heavy=is_dh,
            facing_large_bet=facing_large_bet,
            exploit_tighten_call=exploit_tighten_call,
            opponent_af=opp_af,
            nut_advantage=nut_adv,
            is_delayed_cbet=is_delayed_cbet,
            opponent_checked_back=opponent_checked_back,
            last_bet_frac=last_bet_frac_val,
            villain_nuts_pct=villain_nuts_pct,
            exploit_need_adjust=exploit_need_adjust,
            hole_cards=player.hole_cards,
            villain_stats=villain_stats_full,
            is_pfr=hero_is_pfr,
            worst_villain_stats=worst_vs,
            max_value_lean=max_vl,
            max_trap_lean=max_tl,
            max_bluff_lean=max_bl,
            n_sticky=n_sticky,
            villain_vs_hero_dist=villain_vs_hero_dist,
            # 2026-04-25 修 P0 bug：把完整跟踪的 hero / 主要 villain 街道动作
            # 传给 engine，修 double_barrel / triple_barrel / stop_and_go /
            # float_bet 永远拿不到历史动作的 bug。
            my_prev_actions=dict(self._my_street_actions),
            opp_prev_actions=dict(
                self._opp_street_actions.get(primary_opp_id, {})
                if primary_opp_id >= 0 else {}
            ),
            prev_bet_called_count=prev_resistance['called_count'],
            prev_bet_raised=prev_resistance['raised'],
            prev_bet_was_multiway=prev_resistance['was_multiway'],
            prev_bet_frac=prev_resistance['frac'],
            resistance_level=prev_resistance['level'],
            equity_mc=raw_mc,
            equity_range=equity,
            decision_seed=engine_seed,
        )

        # ── Track my own action for next-street cross-street logic ───────
        self._my_street_actions[street] = action_str

        # 加注金额不超过对手有效可投入的上限（超出无意义）。
        # 有效上限 = 对手剩余筹码 + 对手本街已投入（因为 amount 是 bot 的总额语义）。
        if action_str == 'raise' and amount > 0:
            acting_effective = [
                p.stack + getattr(p, 'current_bet', 0)
                for p in gs.active_players
                if p.player_id != player.player_id and p.can_act()
            ]
            if acting_effective:
                max_effective = max(acting_effective)
                amount = min(amount, max_effective)

        if self.use_range_equity:
            use_calibration = (
                primary_opp_id >= 0
                and self._showdown_learner.sample_count(
                    self.opponent_model._id_to_name.get(primary_opp_id, ''), street, 'raise') >= 8
            )
        else:
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
            # 提炼最关键的 adj 信号，不是全部堆出来。
            # 标签文字从连续 scale 派生（展示用途，不做决策）。
            sig_parts = []
            bluff_ag = adj.get('bluff_ag_scale', 0.55)
            if bluff_ag <= 0.18:
                sig_parts.append(f"禁诈唬(bluff_ag×{bluff_ag:.2f})")
            elif bluff_ag >= 0.85:
                sig_parts.append(f"多诈唬(bluff_ag×{bluff_ag:.2f})")
            elif bluff_ag <= 0.35:
                sig_parts.append(f"少诈唬(bluff_ag×{bluff_ag:.2f})")
            value_ag = adj.get('value_ag_scale', 1.0)
            if value_ag <= 0.55 and bluff_ag <= 0.25:
                sig_parts.append(f"纯价值(value_ag×{value_ag:.2f})")
            elif bluff_ag >= 0.90:
                sig_parts.append(f"高频cbet(bluff_ag×{bluff_ag:.2f})")
            if adj.get('value_sizing_scale', 1.0) >= 1.10:
                sig_parts.append(f"加大注码×{adj['value_sizing_scale']:.2f}")
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
            streets_bet=(len(set(s for s, a in self._v2_action_history.get(primary_opp_id, []) if a == 'raise'))
                         if self.use_range_equity and primary_opp_id >= 0
                         else self.range_estimator.streets_bet(primary_opp_id) if primary_opp_id >= 0 else 0),
            street=street,
            use_calibration=use_calibration,
            spr=spr,
            position=pos,
            equity_mode=self._last_equity_mode,
            min_rf=min_rf,
            num_opp=num_opponents,
            opp_label=opp_label,
            adj_summary=adj_summary,
            is_delayed_cbet=is_delayed_cbet,
            opponent_checked_back=opponent_checked_back,
            nut_advantage=nut_adv,
            opp_af=opp_af,
            fold_to_cbet_val=fold_to_cbet_val,
            exploit_need_adjust=exploit_need_adjust,
            stack=stack,
        )
        self._last_decision_diagnostics = self._build_postflop_diagnostics(
            street=street,
            action=action_str,
            amount=amount,
            pot=pot,
            to_call=to_call,
            effective_call=min(to_call, stack) if to_call > 0 else 0.0,
            stack=stack,
            spr=spr,
            raw_mc=raw_mc,
            equity=equity,
            equity_mode=self._last_equity_mode,
            compression=(equity / raw_mc if raw_mc > 0 else 1.0),
            primary_opp_id=primary_opp_id if primary_opp_id is not None else -1,
            board=board,
            hole_cards=player.hole_cards,
            hero_bucket=hero_bucket,
            nut_advantage=nut_adv,
            raw_seed=raw_seed,
            range_seed=range_seed,
            engine_seed=engine_seed,
            villain_bucket_dist=v_bucket_dist,
            prev_bet_called_count=prev_resistance['called_count'],
            prev_bet_raised=prev_resistance['raised'],
            prev_bet_was_multiway=prev_resistance['was_multiway'],
            resistance_level=prev_resistance['level'],
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
            return _hand_category(hole_cards)
        combined = hole_cards + board
        if len(combined) < 5:
            return "未成牌"
        score = HandEvaluator.evaluate(combined)
        return HandRank(score[0]).cn_name()

    def _get_equity(
        self,
        hole_cards: List[Card],
        board: List[Card],
        num_opponents: int,
        seed: Optional[int] = None,
    ) -> float:
        if not hole_cards:
            return 0.5
        return self.equity_calc.calculate(
            hole_cards, board, num_opponents,
            iterations=self.equity_iterations,
            seed=seed,
        )

    def _top_villain_combos(
        self,
        player_id: int,
        board: List[Card],
        hole_cards: List[Card],
        limit: int = 5,
    ) -> list[dict]:
        if player_id is None or player_id < 0:
            return []
        try:
            import numpy as np
            from pokerfate.strategy.range_v2 import hand_combo_map as hcm
            w = self._range_tracker.get_distribution(player_id)
            known = {hcm.card_to_int(c) for c in list(board) + list(hole_cards)}
            valid = w.copy()
            valid[hcm.blocked_by(known)] = 0.0
            total = float(valid.sum())
            if total <= 1e-15:
                return []
            valid /= total
            idxs = np.argsort(valid)[::-1][:limit]
            out = []
            for idx in idxs:
                if valid[idx] <= 0:
                    continue
                c1, c2 = hcm.cards_of(int(idx))
                combo = f"{c1}{c2}"
                row = {'combo': combo, 'weight': round(float(valid[idx]), 4)}
                if board:
                    try:
                        row['bucket'] = _hero_categorize([c1, c2], list(board))
                    except Exception:
                        log.exception(
                            "top villain combo bucket failed opponent=%s combo=%s board=%s",
                            player_id,
                            combo,
                            [str(c) for c in board],
                        )
                out.append(row)
            return out
        except Exception:
            log.exception(
                "top villain combo extraction failed opponent=%s board=%s",
                player_id,
                [str(c) for c in board],
            )
            return []

    def _build_postflop_diagnostics(
        self,
        *,
        street: str,
        action: str,
        amount: float,
        pot: float,
        to_call: float,
        effective_call: float,
        stack: float,
        spr: float,
        raw_mc: float,
        equity: float,
        equity_mode: str,
        compression: float,
        primary_opp_id: int,
        board: List[Card],
        hole_cards: List[Card],
        hero_bucket: str,
        nut_advantage: float,
        raw_seed: Optional[int],
        range_seed: Optional[int],
        engine_seed: Optional[int],
        villain_bucket_dist: Dict[str, float],
        prev_bet_called_count: int = 0,
        prev_bet_raised: bool = False,
        prev_bet_was_multiway: bool = False,
        resistance_level: float = 0.0,
    ) -> dict:
        out = self.postflop._last_output
        candidates = list(getattr(out, 'candidates', []) or [])
        detail = self.postflop._last_cbet_detail or {}
        entropy = None
        range_summary = {}
        if primary_opp_id >= 0:
            try:
                entropy = round(float(self._range_tracker.get_entropy(primary_opp_id)), 4)
                range_summary = self._range_tracker.get_range_summary(primary_opp_id)
            except Exception:
                log.exception("postflop diagnostics range summary failed opponent=%s", primary_opp_id)
                entropy = None
                range_summary = {}
        return {
            'street': street,
            'decision_seed': self._pending_decision_seed,
            'equity_seed': raw_seed,
            'range_equity_seed': range_seed,
            'engine_seed': engine_seed,
            'n_samples': self.equity_iterations,
            'equity_mc': round(raw_mc, 4),
            'equity_range': round(equity, 4),
            'equity_mode': equity_mode,
            'compression': round(compression, 4),
            'pot': pot,
            'to_call': to_call,
            'effective_call': effective_call,
            'pot_odds': round(effective_call / (pot + effective_call), 4)
                        if effective_call > 0 and (pot + effective_call) > 0 else 0.0,
            'stack': stack,
            'spr': round(spr, 4),
            'hero_bucket': hero_bucket,
            'hero_made_subtype': detail.get('hero_made_subtype', ''),
            'hero_hand_rank': detail.get('hero_hand_rank', ''),
            'hero_kicker_rank': int(detail.get('hero_kicker_rank') or 0),
            'board_pair_rank': int(detail.get('board_pair_rank') or 0),
            'pocket_pair_rank': int(detail.get('pocket_pair_rank') or 0),
            'nut_advantage': round(nut_advantage, 4),
            'primary_opp_id': primary_opp_id,
            'villain_bucket_dist': {
                k: round(float(v), 4) for k, v in (villain_bucket_dist or {}).items()
            },
            'villain_vs_hero_dist': {
                k: round(float(v), 4)
                for k, v in (detail.get('villain_vs_hero_dist') or {}).items()
            },
            'prev_bet_called_count': int(prev_bet_called_count),
            'prev_bet_raised': bool(prev_bet_raised),
            'prev_bet_was_multiway': bool(prev_bet_was_multiway),
            'resistance_level': round(float(resistance_level), 4),
            'range_entropy': entropy,
            'range_summary': range_summary,
            'top_villain_combos': self._top_villain_combos(
                primary_opp_id, board, hole_cards,
            ),
            'purpose_candidates': [
                {'purpose': p, 'prob': round(float(prob), 4)}
                for p, prob in candidates
            ],
            'final_purpose': getattr(out, 'purpose', ''),
            'final_action': action,
            'final_amount': amount,
            'decision_reason': getattr(out, 'reason', ''),
            'strategy_gates': list(detail.get('strategy_gates') or []),
            'arbitration_mode': getattr(out, 'arbitration_mode', 'mixed'),
            'top_gap': round(float(getattr(out, 'top_gap', 0.0) or 0.0), 4),
            'leverage_flags': list(getattr(out, 'leverage_flags', []) or []),
        }

    def _prev_bet_resistance(
        self,
        prev_street: str,
        num_opponents: int,
        last_bet_frac: float,
    ) -> dict:
        """Summarize how much resistance hero's previous-street bet met."""
        if not prev_street or self._my_street_actions.get(prev_street) != 'raise':
            return {
                'called_count': 0,
                'raised': False,
                'was_multiway': False,
                'frac': 0.0,
                'level': 0.0,
            }

        prev_actions = [
            streets.get(prev_street)
            for streets in self._opp_street_actions.values()
            if streets.get(prev_street)
        ]
        called_count = sum(1 for action in prev_actions if action == 'call')
        raised = any(action == 'raise' for action in prev_actions)
        was_multiway = num_opponents >= 2 or called_count >= 2
        level = min(
            1.0,
            called_count * 0.25
            + (0.55 if raised else 0.0)
            + (0.20 if was_multiway else 0.0),
        )
        return {
            'called_count': called_count,
            'raised': raised,
            'was_multiway': was_multiway,
            'frac': float(last_bet_frac or 0.0),
            'level': level,
        }

    @staticmethod
    def _signal_strength(action: str, bet_ratio: float,
                         is_raise_over: bool, street: str) -> float:
        """Villain 本次动作对其 range 窄化证据强度 ∈ [0, 1]。

        用于 BayesianRangeTracker 的 α / λ 连续插值：
          - strength = 0 → 完整 tempering + floor mixing（弱信号）
          - strength = 1 → 标准 Bayes + 无 mixing + 无 floor（强信号）

        合成两维独立因子后组合：
          1. size_factor ∈ [0,1]：bet_ratio 0.25→0, 0.75→0.4, 1.5+→1.0
          2. act_base：check/call→0, bet→0, raise→0.35, raise_over→0.55
          s = act_base + (1-act_base) · size_factor · 0.85
          river +30%  →  s' = s + (1-s)·0.30 (关街锁定 polarization)

        设计目标：
          - hand 249 翻牌 13.8x pot jam → 强信号（原 bool 门只在 river 触发，
            非 river 13.8x 完全漏掉；新公式 ≈ 0.85）
          - 原 2026-04-21 river bet ≥ 0.75 的高信号近似保留（≈ 0.74）
          - 翻牌 pot-size cbet 不会误触（≈ 0.44，部分坍缩）
          - 小注 (< 0.25x pot) 完全不触发
        """
        if action not in ('bet', 'raise') or bet_ratio <= 0:
            return 0.0

        # size factor
        if bet_ratio < 0.25:
            size_f = 0.0
        elif bet_ratio >= 1.5:
            size_f = 1.0
        else:
            size_f = (bet_ratio - 0.25) / 1.25

        # action baseline
        if is_raise_over:
            act_base = 0.55
        elif action == 'raise':
            act_base = 0.35
        else:  # bet
            act_base = 0.0

        s = act_base + (1.0 - act_base) * size_f * 0.85
        if street == 'river':
            s = s + (1.0 - s) * 0.30
        return max(0.0, min(1.0, s))

    def _adjusted_fold_rate(self, opp_id: int, adj: dict) -> float:
        """估算对手面对 cbet 的弃牌率。

        原先用 adj 的离散标签字段（cbet_freq=='high' / bluff_freq=='none'）
        来 clip 到 {0.55, 0.30}。现在完全由连续 scale 驱动：
          - bluff_ag_scale 高（≥0.85）→ 对手确实常弃 → 抬高
          - bluff_ag_scale 低（≤0.18）→ 对手极少弃 → 压低
        """
        if opp_id < 0:
            return 0.45
        base = self.opponent_model.fold_to_cbet_rate(opp_id)
        bluff_ag = adj.get('bluff_ag_scale', 0.55)
        if bluff_ag >= 0.85:
            return max(base, 0.55)
        if bluff_ag <= 0.18:
            return min(base, 0.30)
        return base

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
                if num_limpers > 0:
                    return f"{tag} {cat} {position} {num_limpers}人limp→iso {eq} | {meta}"
                return f"{tag} {cat} {position} {facing}→开加 {eq} | {meta}"
            elif facing_action == "open":
                kind = "3bet价值" if cat in _3BET_VALUE else "3bet诈唬"
                return f"{tag} {cat} {facing}→{kind} {eq} | {meta}"
            elif facing_action == "3bet":
                return f"{tag} {cat} {facing}→4bet价值 {eq} | {meta}"
            else:
                return f"{tag} {cat} {facing}→5bet全押 {eq} | {meta}"
        elif action_str == "call":
            if facing_action == "none" and num_limpers > 0:
                return f"{tag} {cat} {position} {num_limpers}人limp→平call {eq} | {meta}"
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
        is_delayed_cbet: bool = False,
        opponent_checked_back: bool = False,
        nut_advantage: float = 0.0,
        opp_af: float = 1.5,
        fold_to_cbet_val: float = None,
        exploit_need_adjust: float = 0.0,
        stack: float = 0.0,
    ) -> str:
        made = self._made_hand_label_cn(hole_cards, board)
        tag = "【GTOv2·翻后】"
        texture = BoardTexture(board)
        tex = "干燥" if texture.is_dry else ("湿润" if texture.is_wet else "中性")
        pos = "有位置" if is_ip else "无位置"
        # 短码时 hero 跟不满 villain 的注，uncalled 部分 villain 拿回。
        # 展示的赔率 / 所需胜率要按 effective (能付金额) 算，否则会像 H40 那样
        # 显示 "底池赔率33%" 但实际 effective 赔率只有 5-10%。
        effective_call = min(to_call, stack) if (stack > 0 and to_call > 0) else to_call
        pot_odds = effective_call / (pot + effective_call) if effective_call > 0 else 0.0
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

        opp_ctx = f" [{opp_label}]" if opp_label else ""
        adj_ctx = f" 调整:{adj_summary}" if adj_summary else ""
        head = f"{tag} {made} {position}/{mw} SPR≈{spr:.1f}({spr_lbl}) {tex}{opp_ctx}{adj_ctx}"

        # ── action label ──────────────────────────────────────────────────
        if action_str == "raise":
            if facing_bet:
                role = "IP加注" if is_ip else "check-raise"
                action_label = f"{pos} 面对下注→{role}"
            else:
                if street == "river":
                    if equity >= 0.60:
                        action_label = "河牌价值下注"
                    elif equity >= 0.50:
                        action_label = "河牌薄价值"
                    else:
                        action_label = f"诈唬(弃牌率{opp_fold_rate:.0%})"
                elif is_delayed_cbet:
                    action_label = "延迟续注(delayed-cbet)"
                elif opponent_checked_back and not is_ip:
                    action_label = "探测下注(probe)"
                elif equity >= 0.90:
                    action_label = "强牌下注"
                elif equity >= 0.60:
                    action_label = "价值持续下注"
                elif equity >= 0.30:
                    action_label = "半诈唬"
                else:
                    action_label = f"纯诈唬(弃牌率{opp_fold_rate:.0%})"
        elif action_str == "call":
            action_label = f"底池赔率{pot_odds:.0%}→跟注"
        elif action_str == "check":
            action_label = "强牌过牌控池" if equity >= 0.85 else "过牌"
        else:
            if facing_bet and equity >= pot_odds:
                action_label = f"范围压力→弃牌(赔率{pot_odds:.0%})"
            else:
                action_label = f"赔率{pot_odds:.0%}不足→弃牌"

        main_line = f"{head} {eq} {action_label}"

        # ── detail lines ──────────────────────────────────────────────────
        details = []

        # v3 decision fields: purpose, frac, candidates, α-gate, exploit
        cd = self.postflop._last_cbet_detail or {}
        purpose = cd.get('purpose', '?')
        frac = cd.get('frac', 0.0)
        jammed = cd.get('jammed', False)
        downgraded = cd.get('downgraded_to_check', False)

        # Main purpose line — show frac when we bet, "→check" when α-gate downgraded.
        if action_str == 'raise' and frac > 0:
            frac_tag = f"frac={frac:.2f}"
            if jammed:
                frac_tag += "·jam"
            details.append(f"分支={purpose} {frac_tag}")
        elif downgraded:
            details.append(f"分支={purpose}→check(α降级)")
        else:
            details.append(f"分支={purpose}")

        # Candidate distribution — top 3 by probability, skip trivial (<5%).
        candidates = cd.get('candidates') or []
        if candidates:
            ranked = [(p, prob) for p, prob in sorted(candidates, key=lambda x: -x[1]) if prob >= 0.05]
            top = ranked[:3]
            shown = {p for p, _ in top}
            selected = purpose.split("→", 1)[0]
            if selected not in shown:
                selected_row = next(((p, prob) for p, prob in ranked if p == selected), None)
                if selected_row is not None:
                    top = (top[:2] + [selected_row]) if len(top) >= 3 else (top + [selected_row])
            if top:
                cand_str = " ".join(f"{p}[{prob * 100:.0f}%]" for p, prob in top)
                details.append(f"候选: {cand_str}")

        gates = cd.get('strategy_gates') or []
        if gates:
            details.append("门: " + " | ".join(str(g) for g in gates[:3]))

        # α-gate result — only show when gate was actually evaluated.
        alpha = cd.get('alpha')
        if alpha is not None and getattr(alpha, 'target', 0) > 0:
            if alpha.passed:
                alpha_tag = f"α=ok t={alpha.target * 100:.0f}% s={alpha.hero_bluff_share * 100:.0f}%"
            else:
                alpha_tag = (f"α=FAIL({alpha.direction}) t={alpha.target * 100:.0f}% "
                             f"s={alpha.hero_bluff_share * 100:.0f}%")
            details.append(alpha_tag)

        # Exploit highlights — purposes whose weight shifted meaningfully (>15%).
        exploits = cd.get('exploit_deltas') or {}
        notable = [(k, v) for k, v in exploits.items() if abs(v - 1.0) > 0.15]
        if notable:
            notable.sort(key=lambda x: -abs(x[1] - 1.0))
            ex_str = " ".join(f"{k}×{v:.1f}" for k, v in notable[:3])
            details.append(f"剥削: {ex_str}")

        # Context flags (kept — these come from poker_bot, not v3 engine).
        ctx_flags = []
        if is_delayed_cbet:
            ctx_flags.append("delayed-cbet")
        if opponent_checked_back:
            ctx_flags.append("opp-checked-back")
        if fold_to_cbet_val is not None:
            ctx_flags.append(f"fold_to_cbet={fold_to_cbet_val:.0%}")
        if abs(opp_af - 1.5) >= 0.3:
            ctx_flags.append(f"AF={opp_af:.1f}")
        if ctx_flags:
            details.append(" ".join(ctx_flags))

        if facing_bet and abs(exploit_need_adjust) > 1e-6:
            details.append(f"need_adj={exploit_need_adjust:+.3f}")

        detail_line = "  │  " + "  │  ".join(details) if details else ""
        return main_line + ("\n      " + detail_line if detail_line else "")

    @staticmethod
    def _bayes_shrunk_rate(
        success: float,
        trials: float,
        prior_mean: float,
        prior_strength: float,
    ) -> float:
        """Beta-Binomial posterior mean for robust small-sample rate estimates."""
        if trials <= 0:
            return prior_mean
        alpha = max(prior_mean * prior_strength, 1e-9)
        beta = max((1.0 - prior_mean) * prior_strength, 1e-9)
        return (success + alpha) / (trials + alpha + beta)

    @staticmethod
    def _confidence_weight(trials: float, k: float) -> float:
        """Monotonic confidence in [0,1], approaching 1 with larger samples."""
        if trials <= 0:
            return 0.0
        return trials / (trials + max(k, 1e-9))

    def _compute_call_need_adjust(
        self,
        *,
        street: str,
        opp_stats,
        is_drawing_heavy: bool,
        pot_odds: float,
        num_opponents: int,
    ) -> float:
        """Dynamic exploit adjustment for call threshold (need).

        Positive = tighten calls (need more equity), negative = loosen calls.
        """
        # Street cap: fixed guardrail for dynamic values (not fixed strategy).
        cap = {'flop': 0.02, 'turn': 0.03, 'river': 0.04}.get(street, 0.02)
        if num_opponents >= 3:
            cap *= 0.30
        elif num_opponents == 2:
            cap *= 0.50

        read = 0.0
        conf = 0.0
        if street == 'flop':
            n = float(opp_stats.flop_bet_count + opp_stats.flop_passive_count)
            # TODO(empirical-bayes): replace fixed priors (mean/strength) with
            # pool priors estimated from persisted opponent history
            # (opponents.json), segmented by game format and stake.
            p = self._bayes_shrunk_rate(opp_stats.flop_bet_count, n, prior_mean=0.45, prior_strength=24.0)
            read = p - 0.45
            conf = self._confidence_weight(n, k=24.0)
            lam = 0.10
        elif street == 'turn':
            n_t = float(opp_stats.turn_bet_count + opp_stats.turn_passive_count)
            # TODO(empirical-bayes): same as flop, move to dynamic pool priors.
            p_t = self._bayes_shrunk_rate(opp_stats.turn_bet_count, n_t, prior_mean=0.40, prior_strength=24.0)
            # If turn aggression is high but river AFq is low, treat as turn over-bluff tendency.
            n_r = float(opp_stats.river_bet_count + opp_stats.river_call_count + opp_stats.river_check_count)
            p_r = self._bayes_shrunk_rate(opp_stats.river_bet_count, n_r, prior_mean=0.35, prior_strength=24.0)
            river_falloff = max(0.0, p_t - p_r)
            read = (p_t - 0.40) + 0.50 * river_falloff
            conf = min(self._confidence_weight(n_t, 24.0), self._confidence_weight(n_r, 24.0))
            lam = 0.10
        elif street == 'river':
            n_bf = float(opp_stats.river_bet_count + opp_stats.river_check_count)
            n_bw = float(opp_stats.bet_win_count)
            # TODO(empirical-bayes): calibrate river priors from historical pool
            # to avoid static assumptions across different player pools.
            p_bf = self._bayes_shrunk_rate(opp_stats.river_bet_count, n_bf, prior_mean=0.35, prior_strength=30.0)
            p_bw = self._bayes_shrunk_rate(opp_stats.bluff_win_count, n_bw, prior_mean=0.25, prior_strength=30.0)
            # Blend volume (bet freq) + quality (weak-hand win rate as bluff proxy).
            read = 0.50 * (p_bf - 0.35) + 0.50 * (p_bw - 0.25)
            conf = min(self._confidence_weight(n_bf, 30.0), self._confidence_weight(n_bw, 30.0))
            lam = 0.14
        else:
            return 0.0

        # read > 0 => likely wider/bluffier betting => loosen calls (negative need adjust)
        need_adj = -read * conf * lam

        # Non-draw bluff-catchers should not get the same looseness as draws.
        if not is_drawing_heavy and need_adj < 0:
            need_adj *= 0.40

        # Large bet safety rails.
        if pot_odds >= 0.40 and need_adj < 0:
            need_adj = 0.0
        elif pot_odds >= 0.30 and not is_drawing_heavy and need_adj < -0.01:
            need_adj = -0.01

        return max(-cap, min(cap, need_adj))

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
        is_fold_to_3bet_spot: bool = False,
        is_facing_bet_spot: bool = False,
        bet_amount: float = 0.0,
        pot: float = 0.0,
        opp_position: str = '',
        is_raise_over: bool = False,
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

        if is_fold_to_3bet_spot:
            folded = action.action_type == ActionType.FOLD
            self.opponent_model.record_fold_to_3bet(player_id, folded)

        if is_cbet_spot:
            folded = action.action_type == ActionType.FOLD
            self.opponent_model.record_fold_to_cbet(player_id, folded)

        if street.lower() == 'river' and is_facing_bet_spot:
            folded = action.action_type == ActionType.FOLD
            self.opponent_model.record_river_facing_bet(player_id, folded)

        # Update range estimator for every opponent action
        if self.use_range_equity:
            # Range V2: Bayesian update
            profile = self._build_player_profile(player_id)
            # bet_ratio is only meaningful for first-bets with a clean pot
            # snapshot (see api.py docstring). Otherwise caller passes 0 and
            # SIZING_CATEGORY_ADJ becomes a no-op.
            bet_ratio = bet_amount / pot if (pot > 0 and bet_amount > 0) else 0.0
            ctx = ActionContext(
                position=opp_position, board=[], street=street,
                facing_action=act, facing_cbet=False,
                bet_ratio=bet_ratio,
                is_raise_over=is_raise_over,
            )
            # 方案 B (2026-04-24)：信号强度连续化。
            #
            # 旧 bool `high_signal` 只在 river 且 (is_raise_over or bet_ratio≥0.75)
            # 时触发——遗漏了翻牌/转牌的 overbet/jam（hand 249 的 13.8x pot flop
            # all-in 就走了 tempered 路径，坚果桶只给 25%，hero 爆仓 -104BB）。
            #
            # 新 signal_strength ∈ [0,1]：bet_ratio / is_raise_over / street 合成，
            # tracker 按强度线性插值 α 和 λ——弱信号仍 tempered，强信号走纯 Bayes。
            strength = self._signal_strength(
                action=act, bet_ratio=bet_ratio,
                is_raise_over=is_raise_over, street=street,
            )
            self._range_tracker.observe_action(
                player_id, act, street, ctx, profile,
                board=getattr(self, '_current_board', []),
                signal_strength=strength,
            )
            # Track action history for ShowdownLearner
            self._v2_action_history.setdefault(player_id, []).append((street, act))
        else:
            # EQR mode
            self.range_estimator.observe_action(player_id, act, street)

        # P9 – track opponent street actions for check-back detection
        if player_id not in self._opp_street_actions:
            self._opp_street_actions[player_id] = {}
        self._opp_street_actions[player_id][street] = act

    def observe_showdown(self, player_id: int, cards, name: str = "", board=None) -> None:
        """在 showdown 时记录对手底牌，校准范围估算。

        Range V2: feeds ShowdownLearner (category×action frequency).
        EQR: feeds ShowdownCalibrator (average hand strength).
        """
        if self.use_range_equity:
            # Range V2: record to ShowdownLearner
            resolved_name = name or self.opponent_model._id_to_name.get(player_id, str(player_id))
            hole = [Card.from_str(str(c)) if not hasattr(c, 'rank') else c for c in cards[:2]]
            board_cards = [Card.from_str(str(c)) if not hasattr(c, 'rank') else c for c in (board or [])]
            action_seq = self._v2_action_history.get(player_id, [])
            self._showdown_learner.record(resolved_name, action_seq, hole, board_cards)
            return None
        else:
            return self.range_estimator.observe_showdown(player_id, cards, name=name, board=board)

    def new_hand(self, player_ids: List[int], player_names: Optional[Dict[int, str]] = None,
                 player_positions: Optional[Dict[int, str]] = None):
        """Call at the start of each new hand.

        Parameters
        ----------
        player_ids : list of int
        player_names : dict, optional
            {player_id: name} — used to populate the range estimator's
            pid→name mapping so showdown calibration is keyed by name
            rather than seat ID (seats can be reused across sessions).
        player_positions : dict, optional
            {player_id: position_str}. Feeds Range V2 reset_hand so the
            Bayesian prior uses the real position (BB 0.40 VPIP vs
            fallback CO 0.27). Empty / missing values fall back to CO.
        """
        self._vpip_recorded.clear()
        self._pfr_recorded.clear()
        # Reset cross-street action trackers for each new hand
        self._my_street_actions.clear()
        self._opp_street_actions.clear()
        self.postflop._last_bet_frac = 0.0
        self.postflop._last_bet_street = ""
        self._current_board = []  # track board for Range V2 observe_action
        self._v2_action_history: Dict[int, list] = {}  # player_id → [(street, action)]
        if self.use_range_equity:
            self._range_tracker.start_new_hand()
        names = player_names or {}
        positions = player_positions or {}
        for pid in player_ids:
            self.opponent_model.record_hand_start(pid)
            name = names.get(pid, self.opponent_model._id_to_name.get(pid, str(pid)))

            if self.use_range_equity:
                # Range V2: reset Bayesian tracker with the player's actual
                # position when known. Use `or 'CO'` (not dict.get(..., 'CO'))
                # because upstream stores empty strings for unknown positions —
                # an empty-string entry still exists in the dict, so get()
                # would never fall back.
                profile = self._build_player_profile(pid)
                pos = positions.get(pid) or 'CO'
                self._range_tracker.reset_hand(pid, pos, profile)
            else:
                # EQR mode: reset scalar range estimator
                stats = self.opponent_model.get(pid)
                prior = stats.vpip if stats.hands_seen >= MIN_HANDS_FOR_CLASSIFICATION else 0.35
                pfr_vpip = (stats.pfr / stats.vpip
                            if stats.hands_seen >= MIN_HANDS_FOR_CLASSIFICATION and stats.vpip > 0
                            else 0.75)
                bluff_wr = stats.bluff_win_rate
                bet_win_n = stats.bet_win_count
                river_bf_n = stats.river_bet_count + stats.river_check_count
                river_bf = stats.river_bet_frequency
                self.range_estimator.reset_hand(
                    pid, prior_range=prior, name=name,
                    pfr_vpip_ratio=pfr_vpip,
                    bluff_win_rate=bluff_wr, bet_win_samples=bet_win_n,
                    river_bet_freq=river_bf, river_bf_samples=river_bf_n,
                )

    def update_board(self, board: List[Card]) -> None:
        """Update tracked board for Range V2 observe_action."""
        self._current_board = list(board)
        # Board-aware prior recalibration: when a new street is dealt,
        # boost combos that make nuts / strong on the current board but
        # whose preflop prior weight was low (e.g. 74o on a 77x flop).
        if self.use_range_equity:
            self._range_tracker.reweight_for_board(board)

    def set_hole_cards(self, cards: List[Card]) -> None:
        """Tell Range V2 tracker about bot's hole cards (card removal)."""
        if self.use_range_equity:
            self._range_tracker.set_known_cards(cards)

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

    @property
    def last_decision_diagnostics(self) -> dict:
        return dict(self._last_decision_diagnostics)

    def _lookup_preflop_gto(
        self, gs: GameState, player: Player, position: str, facing_action: str,
        num_limpers: int = 0,
    ) -> dict | None:
        """查询翻前 GTO 参考数据，返回 {chart_key, hand, greenline, pekarstas}（展示用已格式化）。"""
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
            log.exception(
                "preflop GTO refs lookup failed position=%s facing_action=%s",
                position,
                facing_action,
            )
            return None

    def _normalize_pos(self, raw: str) -> str:
        """Map raw position to 6-max canonical for GTO chart lookup.

        Passthrough on miss (default=raw, warn=False): the chart lookup
        downstream will simply return no match for unrecognised keys,
        which is handled gracefully. We deliberately do NOT warn here —
        `_primary_raiser_position` can legitimately return '' for limped
        pots, and we don't want to spam the log on every hand.
        """
        return normalize_position(raw, default=raw, warn=False)

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

    def _build_player_profile(self, player_id: int) -> PlayerProfile:
        """Build a PlayerProfile from OpponentModel data (read-only)."""
        s = self.opponent_model.get(player_id)
        name = self.opponent_model._id_to_name.get(player_id, str(player_id))
        return PlayerProfile(
            name=name,
            hands_seen=s.hands_seen,
            vpip=s.vpip,
            pfr=s.pfr,
            af=s.aggression_factor,
            three_bet_pct=s.three_bet_pct,
            fold_to_3bet=s.fold_to_3bet,
            fold_to_cbet=s.fold_to_cbet,
            fold_to_cbet_opps=s.fold_to_cbet_opps,
            wtsd=s.wtsd,
            wmsd=s.wmsd,
            flop_afq=s.flop_afq,
            turn_afq=s.turn_afq,
            river_afq=s.river_afq,
            river_fold_rate=s.river_fold_rate,
            river_bet_freq=s.river_bet_frequency,
            bluff_win_rate=s.bluff_win_rate,
            bet_win_count=s.bet_win_count,
            river_bet_count=s.river_bet_count,
            river_check_count=s.river_check_count,
            pwi=s.pwi(),
            flop_action_count=s.flop_bet_count + s.flop_passive_count,
            turn_action_count=s.turn_bet_count + s.turn_passive_count,
            river_action_count=s.river_bet_count + s.river_call_count + s.river_check_count,
            river_facing_bet_opps=s.river_facing_bet_opps,
            server_af_prior=s.server_af_prior,
            server_wtsd_prior=s.server_wtsd_prior,
        )
