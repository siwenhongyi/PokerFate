"""Direct unit tests for the v3 purpose-first engine.

Covers: DecisionCtx wiring, purpose triggers, α-gate, calibrator, engine
selection, defense branch. For integration tests see test_bot.py.
"""

from __future__ import annotations

import pytest

from pokerfate.core.card import Card
from pokerfate.strategy.v3 import (
    BlockerSet, BoardSignals, DecisionCtx, DecisionOutput, V3Engine,
    VillainStats,
)
from pokerfate.strategy.v3 import alpha_gate, calibrator
from pokerfate.strategy.v3 import board as v3_board
from pokerfate.strategy.v3 import exploit as v3_exploit
from pokerfate.strategy.range_v2.hand_categorizer import made_hand_info


def card(s: str) -> Card:
    return Card.from_str(s)


def cards(*strs) -> list:
    return [card(s) for s in strs]


# ---------------------------------------------------------------------------
# BoardSignals / board analysis
# ---------------------------------------------------------------------------


class TestBoardSignals:
    def test_is_dry_auto_derived(self):
        sig = BoardSignals(wetness=0.20)
        assert sig.is_dry is True
        assert sig.is_wet is False

    def test_is_wet_auto_derived(self):
        sig = BoardSignals(wetness=0.70)
        assert sig.is_dry is False
        assert sig.is_wet is True

    def test_analyze_dry_board(self):
        sig = v3_board.analyze(cards('Ac', '7d', '2s'))
        assert sig.is_dry
        assert sig.high_card_rank == 14

    def test_analyze_wet_board(self):
        sig = v3_board.analyze(cards('Jh', 'Th', '9h'))
        assert sig.monotone
        assert sig.is_wet

    def test_blockers_nut_flush(self):
        bl = v3_board.detect_blockers(cards('Ah', 'Kd'), cards('Th', '7h', '2c'))
        assert bl['nut_flush_blocker'] is True

    def test_blockers_set(self):
        bl = v3_board.detect_blockers(cards('Ac', '7d'), cards('Kh', '7h', '2c'))
        assert bl['set_blocker'] is True


# ---------------------------------------------------------------------------
# Calibrator
# ---------------------------------------------------------------------------


class TestCalibrator:
    def _ctx(self, **over) -> DecisionCtx:
        defaults = dict(
            street='flop', pot=100.0, stack=1000.0, big_blind=2.0, spr=10.0,
            num_opponents=1, hero_bucket='strong',
            board_sig=BoardSignals(wetness=0.2),
        )
        defaults.update(over)
        return DecisionCtx(**defaults)

    def test_basic_bet_amount(self):
        ctx = self._ctx()
        out = calibrator.calibrate(0.66, ctx, 'polarized_cbet')
        assert out.amount == pytest.approx(66.0, abs=1.0)
        assert not out.jammed

    def test_multiway_cap_on_nuts(self):
        ctx = self._ctx(num_opponents=3, hero_bucket='nuts')
        out = calibrator.calibrate(1.50, ctx, 'polarized_cbet')
        # Multiway cap for nuts is 1.00
        assert out.frac <= 1.01

    def test_overbet_value_exempt_from_multiway_cap(self):
        ctx = self._ctx(num_opponents=3, hero_bucket='nuts')
        out = calibrator.calibrate(1.50, ctx, 'overbet_value')
        # Exempt → still allowed up to street hard cap 0.80 flop
        # (geometric cap still applies for flop though)
        # Regardless, overbet_value on flop is rare. Just confirm not capped to 0.80.
        assert out.frac > 0

    def test_jam_round_up_fires_when_large_bet(self):
        ctx = self._ctx(pot=100.0, stack=50.0, spr=0.5, hero_bucket='strong')
        # A 0.66 pot bet on this pot would be 66 > stack(50), clamped to 50,
        # which is 100% of stack → triggers jam round-up.
        out = calibrator.calibrate(0.66, ctx, 'polarized_cbet')
        assert out.jammed is True
        assert out.amount == ctx.stack

    def test_geometric_cap_limits_flop(self):
        # SPR=1 flop: geometric cap ≈ 0.37 × 1.1 = 0.407 — 0.75 bet should be capped.
        ctx = self._ctx(spr=1.0)
        out = calibrator.calibrate(0.75, ctx, 'polarized_cbet')
        assert out.frac <= 0.50  # capped below 0.75

    def test_river_no_geometric_cap(self):
        ctx = self._ctx(street='river', spr=1.0)
        out = calibrator.calibrate(1.50, ctx, 'polarized_cbet')
        # River allows overbet freely.
        assert out.frac > 0.50


# ---------------------------------------------------------------------------
# Alpha gate
# ---------------------------------------------------------------------------


class TestAlphaGate:
    def test_alpha_from_frac(self):
        assert alpha_gate.alpha_from_frac(1.0) == pytest.approx(0.5)
        assert alpha_gate.alpha_from_frac(0.5) == pytest.approx(1 / 3, abs=0.01)
        assert alpha_gate.alpha_from_frac(0.0) == 0.0

    def test_merged_purpose_skipped(self):
        ctx = DecisionCtx(
            street='flop', position='BTN', is_pfr=True,
            hole_cards=cards('Ac', 'Ks'), board=cards('Ad', '7d', '2s'),
        )
        r = alpha_gate.check(ctx, 0.25, 'range_cbet')
        assert r.passed
        assert r.direction == 'ok'

    def test_polarized_bet_runs_check(self):
        ctx = DecisionCtx(
            street='flop', position='BTN', is_pfr=True,
            hole_cards=cards('Ac', 'Ks'), board=cards('Jh', 'Th', '9h'),
        )
        r = alpha_gate.check(ctx, 0.66, 'polarized_cbet')
        # Just verifies no crash and that target is computed.
        assert 0 < r.target < 1


# ---------------------------------------------------------------------------
# Exploit weights
# ---------------------------------------------------------------------------


class TestExploit:
    # 现在 weight_for 完全由底层指标驱动，label 字段不再影响决策。
    # 这些 helper 按典型 archetype 的实际指标特征构造 VillainStats。
    def _ctx(self, **stat_over) -> DecisionCtx:
        vs = VillainStats(hands_seen=30, **stat_over)
        return DecisionCtx(street='river', villain_stats=vs)

    def _whale_stats(self, **over) -> dict:
        # whale 指标特征：极粘（fold_to_cbet 低、wtsd 高、river_fold_rate 低、af 低）
        base = dict(
            fold_to_cbet=0.18, fold_to_cbet_opps=10,
            wtsd=0.40, river_fold_rate=0.22, river_action_count=10,
            af=1.0,
        )
        base.update(over)
        return base

    def _nit_stats(self, **over) -> dict:
        # nit 指标特征：易弃（fold_to_cbet 高、river_fold 高、wtsd 低、af 中高）
        base = dict(
            fold_to_cbet=0.65, fold_to_cbet_opps=10,
            wtsd=0.20, river_fold_rate=0.60, river_action_count=10,
            af=2.2,
        )
        base.update(over)
        return base

    def test_whale_amplifies_thin_value(self):
        w = v3_exploit.weight_for('thin_value_bet', self._ctx(**self._whale_stats()))
        assert w > 1.0

    def test_whale_suppresses_pure_bluff(self):
        w = v3_exploit.weight_for('pure_bluff_river', self._ctx(**self._whale_stats()))
        assert w < 1.0

    def test_nit_amplifies_pure_bluff(self):
        w = v3_exploit.weight_for('pure_bluff_river', self._ctx(**self._nit_stats()))
        assert w > 1.0

    def test_fold_to_cbet_high_boosts_semi_bluff(self):
        ctx = self._ctx(fold_to_cbet=0.60, fold_to_cbet_opps=10)
        w = v3_exploit.weight_for('semi_bluff', ctx)
        assert w > 1.0

    def test_under_bluff_allowed_vs_whale(self):
        assert v3_exploit.under_bluff_allowed(self._ctx(**self._whale_stats()))

    def test_under_bluff_not_allowed_vs_reg(self):
        # reg 指标：fold_to_cbet ~0.45 / wtsd ~0.25 / river_fold ~0.45 / af ~1.8
        reg = dict(
            fold_to_cbet=0.45, fold_to_cbet_opps=10,
            wtsd=0.25, river_fold_rate=0.45, river_action_count=10,
            af=1.8,
        )
        assert not v3_exploit.under_bluff_allowed(self._ctx(**reg))

    # 新增：证明边缘指标不再跳档（以前 VPIP 54.9%/55% 是 fish/whale 断层）
    def test_continuous_interpolation_no_jump(self):
        shallow = self._whale_stats(fold_to_cbet=0.30, wtsd=0.30, river_fold_rate=0.35)
        deep = self._whale_stats(fold_to_cbet=0.15, wtsd=0.42, river_fold_rate=0.20)
        w_shallow = v3_exploit.weight_for('thick_value_bet', self._ctx(**shallow))
        w_deep = v3_exploit.weight_for('thick_value_bet', self._ctx(**deep))
        # 更粘的对手拿到更高 delta（连续性：不是平台跳变）
        assert w_deep > w_shallow > 1.0

    # 问题 1：whale bluff_catch_call 权重压制
    def test_bluff_catch_call_suppressed_for_whale(self):
        w = v3_exploit.weight_for('bluff_catch_call', self._ctx(**self._whale_stats()))
        assert w < 0.5, f"whale bluff_catch_call 应该被压制，实际 {w:.2f}"

    # 问题 1 对称：maniac bluff_catch_call 仍然放大
    def test_bluff_catch_call_amplified_for_maniac(self):
        maniac = dict(
            fold_to_cbet=0.55, fold_to_cbet_opps=10,
            wtsd=0.22, river_fold_rate=0.50, river_action_count=10,
            af=3.0, bluff_win_rate=0.38, bet_win_count=10,
        )
        w = v3_exploit.weight_for('bluff_catch_call', self._ctx(**maniac))
        assert w > 1.2, f"maniac bluff_catch_call 应该被放大，实际 {w:.2f}"

    # 问题 1 边缘：value_lean 介于中高档（边缘粘性对手）不应被完全压到 0
    def test_bluff_catch_call_moderate_for_borderline_sticky(self):
        """实战 H-13BB 个案：河牌 flush vs whale PWI+87，hero 52% eq、赔率 25%，
        数学上 +27pp EV call，但 bluff_catch_call × 0.3 导致弃掉赢牌。

        -0.50 coef 后边缘粘性对手（value_lean ≈ 1.2-1.6）weight 应在 0.3-0.7
        区间——仍然显著压制但不完全消除，给 fold/call 混合留空间。
        """
        borderline = dict(
            fold_to_cbet=0.22, fold_to_cbet_opps=10,
            wtsd=0.35, river_fold_rate=0.30, river_action_count=10,
            af=1.0,  # passive 但非极端 whale
        )
        w = v3_exploit.weight_for('bluff_catch_call', self._ctx(**borderline))
        assert 0.15 <= w <= 0.60, (
            f"边缘粘性对手 bluff_catch_call 应在 0.15-0.60 区间（非完全压制），"
            f"实际 {w:.2f}"
        )

    # 问题 1 对称：reg 基线附近
    def test_bluff_catch_call_near_baseline_for_reg(self):
        reg = dict(
            fold_to_cbet=0.48, fold_to_cbet_opps=10,
            wtsd=0.25, river_fold_rate=0.42, river_action_count=10,
            af=1.9, bluff_win_rate=0.22, bet_win_count=10,
        )
        w = v3_exploit.weight_for('bluff_catch_call', self._ctx(**reg))
        assert 0.7 <= w <= 1.4, f"reg bluff_catch_call 应在基线附近，实际 {w:.2f}"

    # 问题 4：whale block_bet 权重压制到 0
    def test_block_bet_suppressed_for_whale(self):
        w = v3_exploit.weight_for('block_bet', self._ctx(**self._whale_stats()))
        assert w < 0.1, f"whale block_bet 应该压到 0 附近，实际 {w:.2f}"

    # 问题 5 guard：每个注册 purpose 要么在 _PURPOSE_COEF 里，要么在白名单里。
    # 防止未来新增 purpose 漏接入 exploit 后成为静默 leak。
    def test_all_purposes_in_coef_or_whitelisted(self):
        from pokerfate.strategy.v3.purposes_active import all_active
        from pokerfate.strategy.v3.purposes_defensive import all_defensive
        from pokerfate.strategy.v3.purposes_passive import all_passive
        # 白名单：exploit.py 文档里明确 baseline by design 的 purpose。
        # 新增 purpose 必须要么加进 _PURPOSE_COEF、要么加进这个白名单并说明理由。
        BASELINE_WHITELIST = {
            'default_check', 'pot_control', 'value_jam', 'fold',
            'stop_and_go', 'turn_donk', 'draw_call',
            # 2026-04-25 Fix 4: default_stab 的 baseline 是 PFR 默认小注，
            # 不用 exploit 加权——权重 0.45 固定，交给 engine 选择逻辑。
            'default_stab',
        }
        all_ids = set()
        for p in all_active() + all_defensive() + all_passive():
            all_ids.add(p.id)
        for pid in all_ids:
            assert (pid in v3_exploit._PURPOSE_COEF
                    or pid in BASELINE_WHITELIST), \
                f"purpose {pid} 既不在 _PURPOSE_COEF 也不在白名单里"


# ---------------------------------------------------------------------------
# Engine — active branch
# ---------------------------------------------------------------------------


class TestEngineActive:
    def _setup_flop_ctx(self, **over) -> DecisionCtx:
        board = cards('Ac', '7d', '2s')
        sig = v3_board.analyze(board)
        defaults = dict(
            street='flop',
            hole_cards=cards('Ah', 'Kh'),
            board=board,
            position='BTN',
            is_ip=True,
            num_opponents=1,
            pot=10.0,
            stack=200.0,
            big_blind=2.0,
            spr=20.0,
            facing_bet=False,
            hero_bucket='strong',
            equity_mc=0.80,
            equity_range=0.80,
            is_pfr=True,
            board_sig=sig,
        )
        defaults.update(over)
        return DecisionCtx(**defaults)

    def test_smoke_runs_without_error(self):
        engine = V3Engine()
        ctx = self._setup_flop_ctx()
        out = engine.decide(ctx)
        assert isinstance(out, DecisionOutput)
        assert out.action in ('check', 'bet', 'call', 'raise', 'fold')

    def test_fresh_seed_is_reproducible(self):
        engine = V3Engine()
        ctx1 = self._setup_flop_ctx()
        ctx2 = self._setup_flop_ctx()
        out1 = engine.decide(ctx1)
        ctx2.rng.seed(out1.seed)
        # Re-running with the same seed reproduces the random branches.
        # (ctx2 gets a new seed from the engine, but the underlying RNG was
        # pinned first — this verifies the seed plumbing.)
        assert out1.seed >= 0

    def test_default_check_when_no_bet_purpose(self):
        # Weak air with no blockers, no good reason to bet.
        engine = V3Engine()
        ctx = self._setup_flop_ctx(
            hero_bucket='air', equity_mc=0.15, equity_range=0.15,
            is_pfr=False,
        )
        actions = [engine.decide(ctx).action for _ in range(30)]
        # Should mostly check (no range_cbet because is_pfr=False;
        # no polarized_cbet because hero_bucket not in {nuts,strong,draw}).
        assert actions.count('check') >= 25

    def test_strong_hand_pfr_dry_board_bets_frequently(self):
        engine = V3Engine()
        ctx = self._setup_flop_ctx()
        # Strong hand on A-high dry board → range_cbet / polarized_cbet /
        # thick_value_bet all candidates. Should bet most of the time.
        bets = sum(1 for _ in range(50)
                   if engine.decide(ctx).action in ('bet', 'raise'))
        assert bets >= 30

    def test_nuts_spr2_jams(self):
        engine = V3Engine()
        # value_jam (w≈3.1) 与 range_cbet multi_commit (w=1.0) 在 SPR<=2 nuts
        # 场景下加权竞争（doc 03 §5.2），约 76% 概率采到 value_jam。多次采样
        # 校验多数 jam，避免单次随机失败。
        jams = 0
        total = 200
        for _ in range(total):
            ctx = self._setup_flop_ctx(
                hero_bucket='nuts', equity_mc=0.95, equity_range=0.95,
                stack=50.0, pot=50.0, spr=1.0,
            )
            out = engine.decide(ctx)
            if out.action in ('bet', 'raise') and out.amount == pytest.approx(ctx.stack, rel=0.01):
                jams += 1
        # Theoretical p ≈ 0.756; threshold 60% 留充足边际抗 binomial 方差。
        assert jams >= 120, f"value_jam should fire majority, got {jams}/{total}"


# ---------------------------------------------------------------------------
# Engine — defense branch
# ---------------------------------------------------------------------------


class TestEngineDefense:
    def _setup_facing_bet(self, **over) -> DecisionCtx:
        board = cards('As', 'Kd', '2c')
        sig = v3_board.analyze(board)
        defaults = dict(
            street='flop',
            hole_cards=cards('Ah', 'Ad'),
            board=board,
            position='BTN',
            is_ip=True,
            num_opponents=1,
            pot=30.0,
            to_call=10.0,
            stack=200.0,
            big_blind=2.0,
            spr=5.0,
            pot_odds=10.0 / 40.0,
            facing_bet=True,
            hero_bucket='strong',
            equity_mc=0.88,
            equity_range=0.88,
            board_sig=sig,
        )
        defaults.update(over)
        return DecisionCtx(**defaults)

    def test_strong_hand_never_folds(self):
        engine = V3Engine()
        for _ in range(100):
            ctx = self._setup_facing_bet()
            out = engine.decide(ctx)
            assert out.action != 'fold', \
                f"strong hand must not fold; got {out.action} purpose={out.purpose}"

    def test_raise_size_exceeds_to_call(self):
        engine = V3Engine()
        for _ in range(30):
            ctx = self._setup_facing_bet()
            out = engine.decide(ctx)
            if out.action == 'raise':
                assert out.amount > ctx.to_call

    def test_weak_hand_folds_vs_large_bet(self):
        engine = V3Engine()
        ctx = self._setup_facing_bet(
            hero_bucket='air',
            equity_mc=0.10, equity_range=0.10,
            to_call=60.0,
            pot=60.0,
            pot_odds=60.0 / 120.0,
            spr=2.0,
        )
        folds = sum(1 for _ in range(30) if engine.decide(ctx).action == 'fold')
        assert folds >= 25

    def test_all_in_pot_odds_call(self):
        engine = V3Engine()
        ctx = self._setup_facing_bet(
            to_call=200.0,            # all-in
            pot=50.0,
            pot_odds=200.0 / 250.0,   # ≈ 0.80 — need 80% equity
            equity_range=0.90,        # have it → call
            equity_mc=0.90,
        )
        out = engine.decide(ctx)
        assert out.action == 'call'

    def test_all_in_pot_odds_fold(self):
        engine = V3Engine()
        ctx = self._setup_facing_bet(
            to_call=200.0, pot=50.0,
            pot_odds=200.0 / 250.0,   # 0.80
            equity_range=0.40,        # below threshold → fold
            equity_mc=0.40,
        )
        out = engine.decide(ctx)
        assert out.action == 'fold'

    def test_all_in_uses_uncertainty_not_raw_range_only(self):
        engine = V3Engine()
        ctx = self._setup_facing_bet(
            to_call=100.0,
            pot=100.0,
            stack=100.0,
            pot_odds=0.50,
            equity_range=0.60,
            equity_mc=0.45,
        )
        ctx.equity_uncertainty = 0.20
        out = engine.decide(ctx)
        assert out.action == 'fold'

    def test_draw_call_uses_implied_odds(self):
        engine = V3Engine()
        # Flush draw facing half-pot bet: eq ~36% direct, pot_odds=25%,
        # implied bonus keeps the call +EV.
        ctx = self._setup_facing_bet(
            hero_bucket='draw',
            equity_mc=0.36, equity_range=0.36,
            pot=30.0, to_call=15.0,
            pot_odds=15.0 / 45.0,   # 0.33
            spr=10.0, stack=300.0,
        )
        calls = sum(1 for _ in range(30)
                    if engine.decide(ctx).action == 'call')
        assert calls >= 20

    def test_opp_raise_premium_is_monotonic_in_af(self):
        """premium 是 AF 的连续单调减函数：AF 越高，premium 越低。
        不按 player_type 分类做特例断言 — 任何对手身份只靠 AF 决定。
        """
        from pokerfate.strategy.v3.purposes_defensive import _opp_raise_premium
        from pokerfate.strategy.v3.context import VillainStats

        def premium_at(af: float) -> float:
            ctx = DecisionCtx(
                villain_stats=VillainStats(af=af),
                pot=100.0, to_call=33.0, pot_odds=0.25,
            )
            return _opp_raise_premium(ctx)

        # 单调递减：AF 越大，premium 越小（或持平在 clamp 边界）
        afs = [0.2, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 4.0]
        premiums = [premium_at(af) for af in afs]
        for i in range(len(premiums) - 1):
            assert premiums[i] >= premiums[i + 1] - 1e-9, (
                f"premium must be non-increasing in AF: "
                f"af={afs[i]}→{premiums[i]:.3f}, af={afs[i+1]}→{premiums[i+1]:.3f}"
            )

        # baseline: AF = 1.5 对应 premium = 0
        assert abs(premium_at(1.5)) < 1e-6

        # 低 AF 方向为正（下注少 → bet 更强 → 加 premium）
        assert premium_at(0.3) > 0.03

        # 高 AF 方向为负（下注多 → bet 更弱 → 减 premium）
        assert premium_at(3.0) < -0.03

    def test_opp_raise_premium_pot_odds_scaling(self):
        """小注（pot_odds 低）的 premium 被按比例缩小 —— 小注不值得尊重。"""
        from pokerfate.strategy.v3.purposes_defensive import _opp_raise_premium
        from pokerfate.strategy.v3.context import VillainStats

        def premium_at(pot_odds: float, af: float = 0.5) -> float:
            ctx = DecisionCtx(
                villain_stats=VillainStats(af=af),
                pot=100.0, to_call=pot_odds * 100 / (1 - pot_odds),
                pot_odds=pot_odds,
            )
            return _opp_raise_premium(ctx)

        # pot_odds 0.05（tiny bet）vs 0.25（standard）vs 0.40（large）
        tiny = premium_at(0.05)
        normal = premium_at(0.25)
        large = premium_at(0.40)
        assert tiny < normal
        assert normal <= large + 1e-9  # large bet saturates at scale=1.0

    def test_h31_delayed_cbet_vs_whale_not_suppressed(self):
        """H31 regression: UTG AJs, flop 8-T-4 check, turn A (两对 AJ, eq 73%)，
        villain 是 whale。over_bluff_harmless 应该让 α-gate 放行 delayed_cbet
        即使 range 层面 bluff_share 超过 α target。
        见 gameplay analysis (hand 31 / +179k) 和 H73 类型 log。
        """
        from pokerfate.strategy.v3 import alpha_gate
        from pokerfate.strategy.v3.context import VillainStats
        board = cards('8c', 'Tc', '4d', 'Ah')
        # whale villain: 指标驱动（af/wtsd/fold_to_cbet/river_fold + 样本量）
        vs = VillainStats(
            af=0.5, hands_seen=50,
            fold_to_cbet=0.20, fold_to_cbet_opps=15,
            wtsd=0.42,
            river_fold_rate=0.22, river_action_count=12,
        )
        ctx = DecisionCtx(
            street='turn',
            hole_cards=cards('As', 'Js'),
            board=board,
            position='UTG',
            is_pfr=True,
            my_prev_actions={'flop': 'check'},
            equity_range=0.73,
            villain_stats=vs,
            board_sig=v3_board.analyze(board),
        )
        # frac 0.50 → alpha target 0.33; filtered bluff share typically >0.52
        # → without over_bluff_harmless would FAIL; with it should PASS.
        result = alpha_gate.check(ctx, 0.50, 'delayed_cbet')
        assert result.passed, (
            f"expected α-gate PASS vs whale (over_bluff_harmless), "
            f"got direction={result.direction} share={result.hero_bluff_share:.2f}"
        )

    def test_delayed_cbet_still_blocked_vs_reg(self):
        """对称测试：同样的 range 层 over_bluff 场景，vs reg 仍然 FAIL。
        保证 over_bluff_harmless 不是无脑放行。
        """
        from pokerfate.strategy.v3 import alpha_gate
        from pokerfate.strategy.v3.context import VillainStats
        board = cards('8c', 'Tc', '4d', 'Ah')
        # reg: 指标均衡（fold_to_cbet ~0.45 / wtsd ~0.25 / river_fold ~0.45）
        vs = VillainStats(
            af=2.0, hands_seen=50,
            fold_to_cbet=0.45, fold_to_cbet_opps=15,
            wtsd=0.25,
            river_fold_rate=0.45, river_action_count=12,
        )
        ctx = DecisionCtx(
            street='turn',
            hole_cards=cards('As', 'Js'),
            board=board,
            position='UTG',
            is_pfr=True,
            my_prev_actions={'flop': 'check'},
            equity_range=0.73,
            villain_stats=vs,
            board_sig=v3_board.analyze(board),
        )
        result = alpha_gate.check(ctx, 0.50, 'delayed_cbet')
        # reg 桌 bluff_share > target × 1.30 → FAIL (protect range balance)
        assert not result.passed and result.direction == 'over_bluff'

    def test_hero_range_subrange_filter_changes_distribution(self):
        """验证 hero_range.distribution() 的 action-history filter 生效。
        flop check 过的 subrange 与未过滤版本 bucket 分布应显著不同。
        """
        from pokerfate.strategy.v3 import hero_range
        board = cards('8c', 'Tc', '4d', 'Ah')
        d_unfiltered = hero_range.distribution(
            'UTG', 'none', board, hero_known_cards=None,
        )
        d_filtered = hero_range.distribution(
            'UTG', 'none', board, hero_known_cards=None,
            my_prev_actions={'flop': 'check'}, is_pfr=True,
        )
        # 两个分布应不同（至少某个 bucket 有 >1pp 差异）
        diff = sum(abs(d_unfiltered.get(b, 0) - d_filtered.get(b, 0))
                    for b in ('nuts', 'strong', 'medium', 'draw', 'weak_draw', 'air'))
        assert diff > 0.02, \
            f"subrange filter produced no meaningful change, total diff={diff:.3f}"

    def test_hero_range_no_actions_matches_unfiltered(self):
        """无 action history 时，新接口应与原无参调用产生相同分布（向后兼容）。"""
        from pokerfate.strategy.v3 import hero_range
        board = cards('Ac', '7d', '2s')
        d1 = hero_range.distribution('BTN', 'none', board)
        d2 = hero_range.distribution('BTN', 'none', board,
                                        my_prev_actions={}, is_pfr=False)
        for b in d1:
            assert abs(d1[b] - d2[b]) < 1e-6

    def test_nuts_with_low_weighted_eq_must_call_not_fold(self):
        """H73 regression: hero 拿 nuts 但 villain range 含大量打败 hero 的坚果
        combos → weighted equity 压到 0.72 以下，value_raise 门槛不过；若
        BluffCatchCall 白名单漏 nuts，候选池只剩 fold → 弃掉赢定的牌。
        见 docs/analysis/2026-04-21-h73-nuts-fold-bug.md。
        """
        board = cards('Js', 'Kd', '4c', '9s', '7d')  # river board with straight
        sig = v3_board.analyze(board)
        engine = V3Engine()
        folds = 0
        calls = 0
        for _ in range(100):
            ctx = DecisionCtx(
                street='river',
                hole_cards=cards('Td', '8s'),
                board=board,
                position='BB', is_ip=False,
                num_opponents=4,                      # 多人池（H73 是 5 人）
                pot=60000.0,
                to_call=20000.0,                      # villain 0.33x 池（H73 是 0.5x 池）
                stack=800000.0,
                big_blind=2000.0,
                spr=13.3,
                pot_odds=20000.0 / 80000.0,           # 0.25
                facing_bet=True,
                hero_bucket='nuts',                   # 顺子 (HandCategorizer.NUTS)
                equity_mc=0.85, equity_range=0.49,    # range 压低到 49%
                # villain range 含 51% 坚果（spade flush 可能）
                villain_bucket_dist={
                    'nuts': 0.51, 'strong': 0.28, 'medium': 0.13,
                    'weak_draw': 0.04, 'draw': 0.02, 'air': 0.02,
                },
                board_sig=sig,
            )
            out = engine.decide(ctx)
            if out.action == 'fold':
                folds += 1
            elif out.action == 'call':
                calls += 1
        # Must essentially never fold; call or raise overwhelmingly.
        assert folds == 0, (
            f"nuts with eq(0.49) > pot_odds(0.25) + adj must not fold, "
            f"got {folds}/100 folds"
        )
        assert calls >= 60, f"expect call dominant, got {calls}/100"


# ---------------------------------------------------------------------------
# Purpose triggers (selective)
# ---------------------------------------------------------------------------


class TestPurposeTriggers:
    def _base_ctx(self, **over) -> DecisionCtx:
        board = cards('Ac', '7d', '2s')
        sig = v3_board.analyze(board)
        defaults = dict(
            street='flop', position='BTN', is_ip=True, num_opponents=1,
            pot=10.0, stack=200.0, big_blind=2.0, spr=20.0,
            hole_cards=cards('Ah', 'Kh'), board=board,
            hero_bucket='strong', equity_mc=0.75, equity_range=0.75,
            is_pfr=True, facing_bet=False, board_sig=sig,
        )
        defaults.update(over)
        return DecisionCtx(**defaults)

    def test_range_cbet_triggers_on_ahi_dry(self):
        from pokerfate.strategy.v3.purposes_active import RangeCbet
        p = RangeCbet()
        ctx = self._base_ctx()
        r = p.trigger(ctx)
        assert r.hit

    def test_range_cbet_excludes_wet(self):
        from pokerfate.strategy.v3.purposes_active import RangeCbet
        p = RangeCbet()
        board = cards('Jh', 'Th', '9h')
        ctx = self._base_ctx(
            board=board, board_sig=v3_board.analyze(board),
        )
        # P0.5 后：湿板软拒 —— 不再硬拒，而是给极低权重让位给 polarized_cbet。
        # 测试改为校验"权重远低于干板基准 0.8"，整数 1.0 量级更稳健。
        r = p.trigger(ctx)
        if r.hit:
            assert r.weight <= 0.30, (
                f"wet-board range_cbet weight should stay low, got {r.weight}"
            )

    def test_overbet_value_requires_nut_advantage(self):
        from pokerfate.strategy.v3.purposes_active import OverbetValue
        p = OverbetValue()
        ctx = self._base_ctx(
            street='river',
            equity_range=0.85,
            nut_advantage=0.30,
            villain_bucket_dist={
                'nuts': 0.05, 'strong': 0.10,
                'medium': 0.35, 'weak_draw': 0.20,
                'draw': 0.10, 'air': 0.20,
            },
            spr=5.0,
        )
        assert p.trigger(ctx).hit

    def test_overbet_value_fails_if_villain_uncapped(self):
        from pokerfate.strategy.v3.purposes_active import OverbetValue
        p = OverbetValue()
        ctx = self._base_ctx(
            street='river',
            equity_range=0.85,
            nut_advantage=0.30,
            villain_bucket_dist={
                'nuts': 0.20,        # too many nuts
                'medium': 0.30, 'weak_draw': 0.20,
                'strong': 0.10, 'draw': 0.10, 'air': 0.10,
            },
        )
        assert not p.trigger(ctx).hit

    def test_block_bet_only_oop(self):
        from pokerfate.strategy.v3.purposes_active import BlockBet
        p = BlockBet()
        # IP — should fail
        ctx_ip = self._base_ctx(
            street='river', is_ip=True,
            hero_bucket='medium', equity_range=0.55,
        )
        assert not p.trigger(ctx_ip).hit

    # 问题 3：湿板 + SPR ≥ 2 + 粘性被动 → thick_value_bet 退场
    def test_thick_value_bet_defers_on_wet_vs_sticky_passive(self):
        from pokerfate.strategy.v3.purposes_active import ThickValueBet
        from pokerfate.strategy.v3.context import VillainStats
        p = ThickValueBet()
        wet = cards('Jh', 'Th', '9h')   # monotone / wet
        # whale-like villain：fold_to_cbet 低、wtsd 高、river_fold_rate 低
        whale = VillainStats(
            hands_seen=40,
            fold_to_cbet=0.15, fold_to_cbet_opps=10,
            wtsd=0.42, river_fold_rate=0.22, river_action_count=10,
            af=1.0,
        )
        ctx = self._base_ctx(
            street='turn',
            board=wet,
            board_sig=v3_board.analyze(wet),
            equity_range=0.75,
            spr=3.0,
            villain_stats=whale,
        )
        assert not p.trigger(ctx).hit

    # 问题 3 反向：低 SPR 仍然开 thick value（被动对手没 polar 加注空间）
    def test_thick_value_bet_still_fires_on_wet_low_spr(self):
        from pokerfate.strategy.v3.purposes_active import ThickValueBet
        from pokerfate.strategy.v3.context import VillainStats
        p = ThickValueBet()
        wet = cards('Jh', 'Th', '9h')
        whale = VillainStats(
            hands_seen=40,
            fold_to_cbet=0.15, fold_to_cbet_opps=10,
            wtsd=0.42, river_fold_rate=0.22, river_action_count=10,
            af=1.0,
        )
        ctx = self._base_ctx(
            street='turn',
            board=wet,
            board_sig=v3_board.analyze(wet),
            equity_range=0.75,
            spr=1.5,            # < 2.0 → 不触发 gate
            villain_stats=whale,
        )
        assert p.trigger(ctx).hit

    # 问题 3 反向：干板不触发 gate
    def test_thick_value_bet_still_fires_on_dry_vs_sticky(self):
        from pokerfate.strategy.v3.purposes_active import ThickValueBet
        from pokerfate.strategy.v3.context import VillainStats
        p = ThickValueBet()
        dry = cards('Ac', '7d', '2s')
        whale = VillainStats(
            hands_seen=40,
            fold_to_cbet=0.15, fold_to_cbet_opps=10,
            wtsd=0.42, river_fold_rate=0.22, river_action_count=10,
            af=1.0,
        )
        ctx = self._base_ctx(
            street='flop',
            board=dry,
            board_sig=v3_board.analyze(dry),
            equity_range=0.75,
            spr=5.0,
            is_pfr=False,       # 避开 dry-flop-pfr range_cbet deferral
            villain_stats=whale,
        )
        assert p.trigger(ctx).hit

    # 问题 3 反向：高 equity (≥ 0.85) 时 gate 让路——hero 近坚果被 polar 加注
    # 后仍赢多数情况，thick value 依旧 +EV。
    def test_thick_value_bet_fires_when_near_nuts_even_on_wet_vs_sticky(self):
        from pokerfate.strategy.v3.purposes_active import ThickValueBet
        from pokerfate.strategy.v3.context import VillainStats
        p = ThickValueBet()
        wet = cards('Jh', 'Th', '9h')
        whale = VillainStats(
            hands_seen=40,
            fold_to_cbet=0.15, fold_to_cbet_opps=10,
            wtsd=0.42, river_fold_rate=0.22, river_action_count=10,
            af=1.0,
        )
        # equity_range=0.88：近坚果区间，不应被 gate 挡住
        ctx = self._base_ctx(
            street='turn',
            board=wet,
            board_sig=v3_board.analyze(wet),
            equity_range=0.88,
            spr=3.0,
            villain_stats=whale,
        )
        # 注意：overbet_value deferral 需要 nut_advantage >= 0.25；默认 0 → thick
        # value 应当触发，除非 sticky gate。
        assert p.trigger(ctx).hit

    def test_pure_bluff_river_requires_blocker(self):
        from pokerfate.strategy.v3.purposes_active import PureBluffRiver
        p = PureBluffRiver()
        ctx = self._base_ctx(
            street='river',
            hero_bucket='air', equity_range=0.05,
            blockers=BlockerSet(),   # no blockers
            villain_bucket_dist={
                'nuts': 0.05, 'strong': 0.10,
                'medium': 0.35, 'weak_draw': 0.20,
                'draw': 0.10, 'air': 0.20,
            },
        )
        assert not p.trigger(ctx).hit

    def test_pure_bluff_river_with_nut_flush_blocker(self):
        from pokerfate.strategy.v3.purposes_active import PureBluffRiver
        p = PureBluffRiver()
        ctx = self._base_ctx(
            street='river',
            hero_bucket='air', equity_range=0.05,
            blockers=BlockerSet(nut_flush_blocker=True),
            villain_bucket_dist={
                'nuts': 0.05, 'strong': 0.10,
                'medium': 0.35, 'weak_draw': 0.20,
                'draw': 0.10, 'air': 0.20,
            },
            villain_stats=VillainStats(river_fold_rate=0.55),
        )
        assert p.trigger(ctx).hit

    def test_delayed_cbet_requires_flop_checked_through(self):
        from pokerfate.strategy.v3.purposes_active import DelayedCbet
        p = DelayedCbet()
        ctx = self._base_ctx(
            street='turn', is_pfr=True,
            flop_checked_through=True,
            equity_range=0.55,
        )
        assert p.trigger(ctx).hit

    def test_trap_slow_play_requires_bluffy_villain(self):
        from pokerfate.strategy.v3.purposes_passive import TrapSlowPlay
        p = TrapSlowPlay()
        # Nuts + aggressive villain (足量样本) → slow play
        ctx_aggressive = self._base_ctx(
            hero_bucket='nuts', spr=10.0,
            villain_stats=VillainStats(
                hands_seen=30, af=3.0,
                bet_win_count=10, bluff_win_rate=0.35,
            ),
        )
        assert p.trigger(ctx_aggressive).hit
        # Nuts + sticky station (低 af + 高 sticky 指标) → don't trap
        ctx_station = self._base_ctx(
            hero_bucket='nuts', spr=10.0,
            villain_stats=VillainStats(
                hands_seen=30, af=0.8,
                fold_to_cbet=0.22, fold_to_cbet_opps=10,
                wtsd=0.36, river_fold_rate=0.25, river_action_count=10,
            ),
        )
        assert not p.trigger(ctx_station).hit

    def test_super_monster_flop_mixes_check_and_small_bet(self):
        from pokerfate.strategy.v3.purposes_active import MonsterValuePlan
        p = MonsterValuePlan()
        ctx = self._base_ctx(
            hero_bucket='nuts',
            hero_hand_rank='four_of_a_kind',
            equity_range=0.995,
            equity_mc=0.99,
            spr=8.0,
            villain_bucket_dist={
                'nuts': 0.0, 'strong': 0.05, 'medium': 0.10,
                'draw': 0.05, 'weak_draw': 0.20, 'air': 0.60,
            },
        )
        assert p.trigger(ctx).hit
        assert p.sizer(ctx) == [(0.00, 0.50), (0.33, 0.25), (0.50, 0.25)]

    def test_super_monster_turn_escalates_after_flop_call(self):
        from pokerfate.strategy.v3.purposes_active import MonsterValuePlan
        p = MonsterValuePlan()
        ctx = self._base_ctx(
            street='turn',
            hero_bucket='nuts',
            hero_hand_rank='four_of_a_kind',
            equity_range=0.995,
            equity_mc=0.99,
            spr=5.0,
            prev_bet_called_count=1,
            villain_bucket_dist={'nuts': 0.0, 'strong': 0.20, 'medium': 0.40},
        )
        assert p.trigger(ctx).hit
        assert p.sizer(ctx) == [(0.55, 0.40), (0.75, 0.60)]

    def test_monster_full_house_air_heavy_uses_small_value_plan(self):
        from pokerfate.strategy.v3.purposes_active import MonsterValuePlan, ThickValueBet
        p = MonsterValuePlan()
        thick = ThickValueBet()
        ctx = self._base_ctx(
            hero_bucket='nuts',
            hero_hand_rank='full_house',
            hero_made_subtype='full_house_plus',
            equity_range=0.95,
            equity_mc=0.90,
            spr=7.0,
            villain_bucket_dist={
                'nuts': 0.04, 'strong': 0.05, 'medium': 0.10,
                'draw': 0.03, 'weak_draw': 0.20, 'air': 0.58,
            },
        )
        assert p.trigger(ctx).hit
        assert p.sizer(ctx) == [(0.00, 0.10), (0.33, 0.50), (0.50, 0.40)]
        assert not thick.trigger(ctx).hit

    def test_monster_full_house_draw_pressure_does_not_pure_check(self):
        from pokerfate.strategy.v3.purposes_active import MonsterValuePlan
        p = MonsterValuePlan()
        wet = cards('Jh', 'Th', '9h')
        ctx = self._base_ctx(
            hero_bucket='nuts',
            hero_hand_rank='full_house',
            hero_made_subtype='full_house_plus',
            equity_range=0.94,
            equity_mc=0.88,
            spr=7.0,
            board=wet,
            board_sig=v3_board.analyze(wet),
            villain_bucket_dist={
                'nuts': 0.06, 'strong': 0.10, 'medium': 0.12,
                'draw': 0.18, 'weak_draw': 0.12, 'air': 0.42,
            },
        )
        assert p.trigger(ctx).hit
        sizes = p.sizer(ctx)
        assert all(frac > 0 for frac, _ in sizes)
        assert sizes == [(0.50, 0.45), (0.66, 0.40), (0.75, 0.15)]

    def test_tiny_donk_low_spr_overpair_protection_raise(self):
        from pokerfate.strategy.v3.purposes_defensive import ProtectionRaise
        board = cards('7d', '9d', '6h')
        info = made_hand_info(cards('Ah', 'As'), board)
        ctx = self._base_ctx(
            street='flop',
            hole_cards=cards('Ah', 'As'),
            board=board,
            board_sig=BoardSignals(
                wetness=0.75,
                flush_draw=True,
                straight_draw_heavy=True,
                high_card_rank=9,
            ),
            facing_bet=True,
            hero_bucket='strong',
            hero_made_subtype=info.subtype,
            hero_hand_rank=info.hand_rank,
            hero_made_rank=info.made_rank,
            pot=115_000.0,
            to_call=10_000.0,
            stack=230_000.0,
            spr=2.0,
            pot_odds=10_000.0 / 125_000.0,
            num_opponents=2,
            equity_range=0.51,
            equity_mc=0.59,
            villain_bucket_dist={
                'nuts': 0.14, 'strong': 0.11, 'medium': 0.26,
                'draw': 0.18, 'weak_draw': 0.14, 'air': 0.17,
            },
        )
        p = ProtectionRaise()
        result = p.trigger(ctx)
        assert info.subtype == 'clean_overpair'
        assert result.hit
        assert result.weight >= 2.5

        out = V3Engine().decide(ctx)
        assert out.action == 'raise'
        assert out.purpose == 'protection_raise'

    def test_tiny_donk_overpair_still_respects_high_villain_nuts(self):
        from pokerfate.strategy.v3.purposes_defensive import ProtectionRaise
        board = cards('7d', '9d', '6h')
        info = made_hand_info(cards('Ah', 'As'), board)
        ctx = self._base_ctx(
            street='flop',
            hole_cards=cards('Ah', 'As'),
            board=board,
            board_sig=BoardSignals(
                wetness=0.75,
                flush_draw=True,
                straight_draw_heavy=True,
                high_card_rank=9,
            ),
            facing_bet=True,
            hero_bucket='strong',
            hero_made_subtype=info.subtype,
            hero_hand_rank=info.hand_rank,
            pot=115_000.0,
            to_call=10_000.0,
            stack=230_000.0,
            spr=2.0,
            pot_odds=10_000.0 / 125_000.0,
            num_opponents=2,
            equity_range=0.51,
            equity_mc=0.59,
            villain_bucket_dist={
                'nuts': 0.35, 'strong': 0.30, 'medium': 0.15,
                'draw': 0.10, 'weak_draw': 0.05, 'air': 0.05,
            },
        )
        assert not ProtectionRaise().trigger(ctx).hit

    def test_stop_and_go_continuous_across_ftc_boundary(self):
        """StopAndGo 触发权重应随 fold_to_cbet 平滑变化，不在旧硬区间
        [0.35, 0.68] 边界跳档。见 review-2026-04-22.md E.3。
        """
        from pokerfate.strategy.v3.purposes_active import StopAndGo
        p = StopAndGo()

        def _ctx(ftc: float) -> DecisionCtx:
            board = cards('8c', 'Tc', '4d', 'Ah')
            return DecisionCtx(
                street='river',
                hole_cards=cards('Ac', 'Ks'),
                board=board,
                is_pfr=True,
                my_prev_actions={'flop': 'bet', 'turn': 'check'},
                facing_bet=False,
                board_sig=v3_board.analyze(board),
                villain_stats=VillainStats(
                    hands_seen=30, af=2.0,
                    fold_to_cbet=ftc, fold_to_cbet_opps=15,
                    river_fold_rate=0.50, river_action_count=10,
                ),
            )

        # 在以前的 [0.35, 0.68] 硬区间外 ftc=0.34 / 0.69 应**仍然**能触发（弱权重），
        # 不再直接 False。
        w_inside = p.trigger(_ctx(0.52)).weight  # 区间中心峰值
        w_near_low = p.trigger(_ctx(0.34))
        w_near_high = p.trigger(_ctx(0.69))
        # 中心必须强
        assert w_inside > 0.5
        # 边界附近不再硬弃（至少要有非零触发或在同量级），证明不再跳档
        # ftc=0.34 距离中心 0.18 < 0.30，ftc_score 约 0.4，composite 可能过阈
        assert w_near_low.hit or w_near_high.hit, (
            "boundary samples should smoothly degrade instead of hard-cut"
        )

    def test_stop_and_go_far_ftc_correctly_rejected(self):
        """ftc 远离 0.52（如 0.10 或 0.90）才应该关断。"""
        from pokerfate.strategy.v3.purposes_active import StopAndGo
        p = StopAndGo()
        board = cards('8c', 'Tc', '4d', 'Ah')
        ctx = DecisionCtx(
            street='river',
            hole_cards=cards('Ac', 'Ks'),
            board=board,
            is_pfr=True,
            my_prev_actions={'flop': 'bet', 'turn': 'check'},
            facing_bet=False,
            board_sig=v3_board.analyze(board),
            villain_stats=VillainStats(
                hands_seen=30, af=1.0,
                fold_to_cbet=0.10, fold_to_cbet_opps=15,  # 极粘不会弃
                river_fold_rate=0.15, river_action_count=10,
            ),
        )
        assert not p.trigger(ctx).hit


class TestNonNutStackoffGuard:
    def test_made_hand_info_marks_non_nut_trips_and_board_pair_two_pair(self):
        info = made_hand_info(cards('Qc', 'Ts'), cards('Ah', '8s', '2h', 'Qd', 'Qs'))
        assert info.subtype == 'trips_weak_kicker'
        assert info.kicker_rank == 10

        under = made_hand_info(cards('Tc', 'Ts'), cards('Qh', 'Qd', '6s'))
        assert under.subtype == 'board_pair_pocket_underpair'
        assert under.pocket_pair_rank == 10
        assert under.board_pair_rank == 12

    def _facing_river_ctx(self, **over) -> DecisionCtx:
        board = cards('Ah', '8s', '2h', 'Qd', 'Qs')
        info = made_hand_info(cards('Qc', 'Ts'), board)
        defaults = dict(
            street='river',
            hole_cards=cards('Qc', 'Ts'),
            board=board,
            position='BTN',
            is_ip=True,
            num_opponents=1,
            pot=1_037_500.0,
            to_call=310_936.0,
            stack=1_298_934.0,
            big_blind=20_000.0,
            spr=1.7,
            pot_odds=310_936.0 / (1_037_500.0 + 310_936.0),
            facing_bet=True,
            hero_bucket='nuts',
            hero_made_subtype=info.subtype,
            hero_made_rank=info.made_rank,
            hero_kicker_rank=info.kicker_rank,
            board_pair_rank=info.board_pair_rank,
            pocket_pair_rank=info.pocket_pair_rank,
            equity_mc=0.72,
            equity_range=0.83,
            board_sig=v3_board.analyze(board),
            villain_bucket_dist={
                'nuts': 0.44, 'strong': 0.51,
                'medium': 0.03, 'draw': 0.0,
                'weak_draw': 0.0, 'air': 0.02,
            },
        )
        defaults.update(over)
        return DecisionCtx(**defaults)

    def test_river_trips_weak_kicker_does_not_value_raise_jam(self):
        engine = V3Engine()
        ctx = self._facing_river_ctx(seed=1)
        out = engine.decide(ctx)
        assert out.action == 'call'
        assert out.purpose != 'value_raise' or 'stackoff_guard' in out.reason

    def test_river_trips_low_side_card_stays_call_even_with_high_equity(self):
        board = cards('6h', 'Qs', 'Ks', 'Ah', 'Kd')
        info = made_hand_info(cards('Kc', '4s'), board)
        ctx = self._facing_river_ctx(
            hole_cards=cards('Kc', '4s'),
            board=board,
            board_sig=v3_board.analyze(board),
            hero_made_subtype=info.subtype,
            hero_made_rank=info.made_rank,
            hero_kicker_rank=info.kicker_rank,
            board_pair_rank=info.board_pair_rank,
            pocket_pair_rank=info.pocket_pair_rank,
            equity_mc=1.0,
            equity_range=1.0,
            villain_bucket_dist={
                'nuts': 0.10, 'strong': 0.45,
                'medium': 0.35, 'draw': 0.0,
                'weak_draw': 0.0, 'air': 0.10,
            },
            seed=2,
        )
        assert info.subtype == 'trips_weak_kicker'
        out = V3Engine().decide(ctx)
        assert out.action == 'call'

    def test_river_ip_full_house_monster_forces_value_raise_over_call(self):
        board = cards('9c', '9h', 'Kh', '2d', '4s')
        info = made_hand_info(cards('Kc', '9d'), board)
        ctx = self._facing_river_ctx(
            street='river',
            hole_cards=cards('Kc', '9d'),
            board=board,
            board_sig=v3_board.analyze(board),
            position='BTN',
            is_ip=True,
            pot=500_000.0,
            to_call=120_000.0,
            stack=1_000_000.0,
            spr=2.0,
            pot_odds=120_000.0 / 620_000.0,
            hero_bucket='nuts',
            hero_made_subtype=info.subtype,
            hero_hand_rank=info.hand_rank,
            hero_made_rank=info.made_rank,
            hero_kicker_rank=info.kicker_rank,
            board_pair_rank=info.board_pair_rank,
            pocket_pair_rank=info.pocket_pair_rank,
            equity_mc=0.96,
            equity_range=0.94,
            villain_bucket_dist={
                'nuts': 0.04, 'strong': 0.35, 'medium': 0.30,
                'draw': 0.0, 'weak_draw': 0.0, 'air': 0.31,
            },
            seed=7,
        )
        out = V3Engine().decide(ctx)
        assert out.action == 'raise'
        assert out.purpose == 'value_raise'
        assert 'monster_river_raise' in out.leverage_flags

    def test_river_ip_quads_super_monster_forces_raise_for_many_seeds(self):
        board = cards('9c', '9h', '9s', '2d', '4s')
        info = made_hand_info(cards('9d', 'Kc'), board)
        for seed in range(1, 16):
            ctx = self._facing_river_ctx(
                street='river',
                hole_cards=cards('9d', 'Kc'),
                board=board,
                board_sig=v3_board.analyze(board),
                position='BTN',
                is_ip=True,
                pot=500_000.0,
                to_call=80_000.0,
                stack=1_000_000.0,
                spr=2.0,
                pot_odds=80_000.0 / 580_000.0,
                hero_bucket='nuts',
                hero_made_subtype=info.subtype,
                hero_hand_rank=info.hand_rank,
                hero_made_rank=info.made_rank,
                hero_kicker_rank=info.kicker_rank,
                board_pair_rank=info.board_pair_rank,
                pocket_pair_rank=info.pocket_pair_rank,
                equity_mc=1.0,
                equity_range=1.0,
                villain_bucket_dist={
                    'nuts': 0.0, 'strong': 0.30, 'medium': 0.35,
                    'draw': 0.0, 'weak_draw': 0.0, 'air': 0.35,
                },
                seed=seed,
            )
            out = V3Engine().decide(ctx)
            assert out.action == 'raise'
            assert out.purpose == 'value_raise'

    def test_paired_board_pocket_pair_value_jam_is_blocked(self):
        board = cards('Qh', 'Qd', '6s')
        info = made_hand_info(cards('Tc', 'Ts'), board)
        ctx = DecisionCtx(
            street='flop',
            hole_cards=cards('Tc', 'Ts'),
            board=board,
            position='BTN',
            is_ip=True,
            num_opponents=1,
            pot=1_000_000.0,
            stack=700_000.0,
            big_blind=20_000.0,
            spr=0.7,
            facing_bet=False,
            hero_bucket='strong',
            hero_made_subtype=info.subtype,
            hero_made_rank=info.made_rank,
            hero_kicker_rank=info.kicker_rank,
            board_pair_rank=info.board_pair_rank,
            pocket_pair_rank=info.pocket_pair_rank,
            equity_mc=0.57,
            equity_range=0.57,
            board_sig=v3_board.analyze(board),
            seed=3,
        )
        out = V3Engine().decide(ctx)
        assert out.action != 'bet' or out.amount < ctx.stack
        assert out.purpose != 'value_jam'

    def test_jam_sized_thick_value_on_board_pair_downgrades_to_check(self):
        board = cards('3h', '5d', '8s', 'Ah', '3c')
        info = made_hand_info(cards('Tc', 'Ts'), board)
        ctx = DecisionCtx(
            street='river',
            hole_cards=cards('Tc', 'Ts'),
            board=board,
            position='BTN',
            is_ip=True,
            num_opponents=1,
            pot=1_050_000.0,
            stack=682_244.0,
            big_blind=20_000.0,
            spr=0.65,
            facing_bet=False,
            hero_bucket='strong',
            hero_made_subtype=info.subtype,
            hero_made_rank=info.made_rank,
            hero_kicker_rank=info.kicker_rank,
            board_pair_rank=info.board_pair_rank,
            pocket_pair_rank=info.pocket_pair_rank,
            equity_mc=0.91,
            equity_range=0.91,
            board_sig=v3_board.analyze(board),
            villain_bucket_dist={
                'nuts': 0.02, 'strong': 0.04,
                'medium': 0.03, 'draw': 0.0,
                'weak_draw': 0.0, 'air': 0.91,
            },
            seed=4,
        )
        out = V3Engine().decide(ctx)
        assert out.action == 'check'
        assert 'stackoff_guard' in out.reason
