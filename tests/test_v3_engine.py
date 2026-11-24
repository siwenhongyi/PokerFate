"""Direct unit tests for the v3 purpose-first engine.

Covers: DecisionCtx wiring, purpose triggers, α-gate, calibrator, engine
selection, defense branch. For integration tests see test_bot.py.
"""

from __future__ import annotations


import pytest

from pokerfate.core.card import Card
from pokerfate.strategy.v3 import (
    BoardSignals, DecisionCtx, DecisionOutput, V3Engine,
    VillainStats,
)
from pokerfate.strategy.v3 import alpha_gate, calibrator
from pokerfate.strategy.v3 import board as v3_board
from pokerfate.strategy.v3 import exploit as v3_exploit
from pokerfate.strategy.postflop import _compute_equity_uncertainty, _hero_draw_profile
from pokerfate.strategy.range_v2.hand_categorizer import categorize_cards, made_hand_info


def card(s: str) -> Card:
    return Card.from_str(s)


def cards(*strs) -> list:
    return [card(s) for s in strs]


class TestEquityUncertainty:
    def test_passive_villain_term_is_continuous(self):
        dist = {'strong': 0.25, 'medium': 0.30, 'draw': 0.10, 'weak_draw': 0.20, 'air': 0.15}
        below = _compute_equity_uncertainty(
            dist,
            VillainStats(af=0.8, vpip=0.349, hands_seen=30),
            num_opponents=3,
            facing_bet=True,
        )
        just_above = _compute_equity_uncertainty(
            dist,
            VillainStats(af=0.8, vpip=0.351, hands_seen=30),
            num_opponents=3,
            facing_bet=True,
        )
        loose_passive = _compute_equity_uncertainty(
            dist,
            VillainStats(af=0.8, vpip=0.55, hands_seen=30),
            num_opponents=3,
            facing_bet=True,
        )

        assert just_above - below < 0.001
        assert 0.163 <= below <= 0.164
        assert loose_passive == pytest.approx(0.20)


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

    def test_draw_profile_broadway_is_gutshot_not_oesd(self):
        draw = _hero_draw_profile(cards('As', 'Ks'), cards('Qc', 'Jd', '4h'))
        assert draw.gutshot is True
        assert draw.oesd is False
        assert draw.overcards is True

    def test_draw_profile_real_oesd(self):
        draw = _hero_draw_profile(cards('9s', '8s'), cards('7d', '6c', '2h'))
        assert draw.oesd is True


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

    _DEEP_SHORT_EFFECTIVE = dict(pot=180_000.0, stack=1_780_000.0, effective_stack=170_000.0,
                                 spr=170_000.0 / 180_000.0)

    @pytest.mark.parametrize("frac, purpose, over, expected", [
        # (frac, amount, jammed)
        (0.66, 'polarized_cbet', {}, (0.66, 66.0, False)),
        (1.50, 'polarized_cbet', dict(num_opponents=3, hero_bucket='nuts'), (0.80, 80.0, False)),   # flop cap
        (1.50, 'overbet_value', dict(num_opponents=3, hero_bucket='nuts'), (0.80, 80.0, False)),
        (0.66, 'polarized_cbet', dict(stack=50.0, spr=0.5), (0.50, 50.0, True)),                    # clamped to the stack
        (0.75, 'polarized_cbet', dict(spr=1.0), (0.2432, 24.32, False)),                            # geometric cap
        (1.50, 'polarized_cbet', dict(street='river', spr=1.0), (1.50, 150.0, False)),              # no geometric cap on the river
        (2.00, 'thick_value_bet', dict(_DEEP_SHORT_EFFECTIVE, hero_bucket='nuts'), (0.80, 144_000.0, False)),
        (0.50, 'range_cbet', dict(_DEEP_SHORT_EFFECTIVE), (0.50, 90_000.0, False)),
    ])
    def test_calibrate(self, frac, purpose, over, expected):
        out = calibrator.calibrate(frac, self._ctx(**over), purpose)
        assert (out.frac, out.amount, out.jammed) == pytest.approx(expected, rel=1e-3)


# ---------------------------------------------------------------------------
# Alpha gate
# ---------------------------------------------------------------------------


class TestAlphaGate:
    def test_balanced_bluff_share_from_frac(self):
        assert alpha_gate.balanced_bluff_share_from_frac(1.0) == pytest.approx(1 / 3)
        assert alpha_gate.balanced_bluff_share_from_frac(0.5) == pytest.approx(0.25)

    def test_river_pure_bluff_uses_balanced_bluff_share(self):
        ctx = DecisionCtx(
            street='river', position='BTN', is_pfr=True,
            hero_bucket='air',
            hole_cards=cards('Ac', '2d'),
            board=cards('Kh', 'Qh', 'Jc', '8s', '3d'),
        )
        r = alpha_gate.check(ctx, 1.0, 'pure_bluff_river')
        assert r.target == pytest.approx(1 / 3)
        assert 0 <= r.hero_bluff_share <= 1


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

    # 新增：证明边缘指标不再跳档（以前 VPIP 54.9%/55% 是 fish/whale 断层）
    def test_continuous_interpolation_no_jump(self):
        shallow = self._whale_stats(fold_to_cbet=0.30, wtsd=0.30, river_fold_rate=0.35)
        deep = self._whale_stats(fold_to_cbet=0.15, wtsd=0.42, river_fold_rate=0.20)
        w_shallow = v3_exploit.weight_for('thick_value_bet', self._ctx(**shallow))
        w_deep = v3_exploit.weight_for('thick_value_bet', self._ctx(**deep))
        # 更粘的对手拿到更高 delta（连续性：不是平台跳变）
        assert w_deep > w_shallow > 1.0

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
        assert out.candidates
        assert sum(prob for _, prob in out.candidates) == pytest.approx(1.0)

    def test_fresh_seed_is_reproducible(self):
        engine = V3Engine()
        ctx1 = self._setup_flop_ctx(seed=123456)
        ctx2 = self._setup_flop_ctx(seed=123456)
        out1 = engine.decide(ctx1)
        out2 = engine.decide(ctx2)

        assert out1.seed == out2.seed == 123456
        assert out1.action == out2.action
        assert out1.purpose == out2.purpose
        assert out1.amount == pytest.approx(out2.amount)
        assert out1.frac == pytest.approx(out2.frac)
        assert [purpose for purpose, _ in out1.candidates] == [
            purpose for purpose, _ in out2.candidates
        ]
        assert [prob for _, prob in out1.candidates] == pytest.approx([
            prob for _, prob in out2.candidates
        ])

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

    def test_raise_size_exceeds_to_call(self):
        engine = V3Engine()
        for _ in range(30):
            ctx = self._setup_facing_bet()
            out = engine.decide(ctx)
            if out.action == 'raise':
                assert out.amount > ctx.to_call

    @pytest.mark.parametrize("can_raise, raises", [(True, True), (False, False)])
    def test_raise_is_a_candidate_only_when_hero_may_raise(self, can_raise, raises):
        candidates = V3Engine()._defensive_candidates(self._setup_facing_bet(can_raise=can_raise))
        assert any(c.action == 'raise' for c in candidates) == raises

    @pytest.mark.parametrize("price, range_eq, uncertainty, behind_eq, expected", [
        # call iff max(range - uncertainty, min(equity when behind, range)) >= price
        (0.80, 0.90, 0.0, None, 'call'),
        (0.80, 0.40, 0.0, None, 'fold'),
        (0.50, 0.60, 0.20, None, 'fold'),
        (0.19, 0.25, 0.19, None, 'fold'),
        (0.19, 0.25, 0.19, 0.24, 'call'),
        (0.50, 0.45, 0.0, 0.55, 'fold'),   # the floor never exceeds the range estimate
    ])
    def test_all_in_call_rule(self, price, range_eq, uncertainty, behind_eq, expected):
        ctx = self._setup_facing_bet(to_call=200.0, pot=50.0, stack=200.0, pot_odds=price,
                                     equity_range=range_eq, equity_mc=range_eq)
        ctx.equity_uncertainty = uncertainty
        if behind_eq is not None:
            ctx.equity_when_behind = behind_eq
        assert V3Engine().decide(ctx).action == expected

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


# ---------------------------------------------------------------------------
# Purpose triggers (selective)
# ---------------------------------------------------------------------------


class TestNonNutStackoffGuard:
    def test_made_hand_info_marks_non_nut_trips_and_board_pair_two_pair(self):
        info = made_hand_info(cards('Qc', 'Ts'), cards('Ah', '8s', '2h', 'Qd', 'Qs'))
        assert info.subtype == 'trips_top_kicker'
        assert info.kicker_rank == 10

        info = made_hand_info(cards('Qc', '9s'), cards('Ah', '8s', '2h', 'Qd', 'Qs'))
        assert info.subtype == 'trips_weak_kicker'
        assert info.kicker_rank == 9

        top_pair = made_hand_info(cards('Ac', 'Ts'), cards('Ah', '8s', '2h'))
        assert top_pair.subtype == 'top_pair_good_kicker'
        assert top_pair.kicker_rank == 10
        assert categorize_cards(cards('Ac', 'Ts'), cards('Ah', '8s', '2h')) == 'strong'

        under = made_hand_info(cards('Tc', 'Ts'), cards('Qh', 'Qd', '6s'))
        assert under.subtype == 'board_pair_pocket_underpair'
        assert under.pocket_pair_rank == 10
        assert under.board_pair_rank == 12


class TestEvVeto:
    """The EV layer prices the vote's aggressive / calling choice."""

    def _ctx(self, **over):
        defaults = dict(street='flop', pot=100.0, stack=1000.0, big_blind=2.0, spr=10.0,
                        num_opponents=2, hero_bucket='air', is_pfr=True,
                        equity_range=0.17, equity_mc=0.20,
                        board_sig=BoardSignals(wetness=0.3, high_card_rank=11, is_dry=True),
                        villain_bucket_dist={'nuts': 0.05, 'strong': 0.15, 'medium': 0.3,
                                             'draw': 0.1, 'weak_draw': 0.2, 'air': 0.2})
        defaults.update(over)
        return DecisionCtx(**defaults)

    def test_multiway_fold_prob_compounds(self):
        from pokerfate.strategy.v3 import counterfactual as cf
        p1 = cf.reaction_estimate(self._ctx(num_opponents=1), 0.4, 'bet', 'range_cbet').p_fold
        p2 = cf.reaction_estimate(self._ctx(num_opponents=2), 0.4, 'bet', 'range_cbet').p_fold
        p3 = cf.reaction_estimate(self._ctx(num_opponents=3), 0.4, 'bet', 'range_cbet').p_fold
        assert p1 ** 2 * 0.85 <= p2 <= p1 ** 2 * 1.05
        assert p1 ** 3 * 0.80 <= p3 <= p1 ** 3 * 1.05


# ---------------------------------------------------------------------------
# Facing a bet: who may call, who votes to fold
# ---------------------------------------------------------------------------


def _facing_ctx(bucket, equity, to_call, pot, **kw):
    """Hero faces ``to_call`` into ``pot`` (the pot already holds the bet)."""
    from pokerfate.core.config import required_equity
    kw.setdefault('stack', 10 * pot)
    kw.setdefault('spr', 10.0)
    return DecisionCtx(
        facing_bet=True, hero_bucket=bucket, equity_range=equity, equity_mc=equity,
        to_call=to_call, pot=pot, pot_odds=required_equity(to_call, pot), **kw,
    )


class TestDefensiveCallAndFold:
    @pytest.mark.parametrize("bucket, equity, hit, weight", [
        ('medium', 0.45, True, 0.5 + 3.0 * (0.45 - 0.25 / 0.91)),
        ('air', 0.50, True, 0.5 + 3.0 * (0.50 - 0.25 / 0.91 - 0.15)),   # no pair: fifteen points more
        ('weak_draw', 0.50, True, 0.5 + 3.0 * (0.50 - 0.25 / 0.91 - 0.15)),
        ('air', 0.40, False, 0.0),
        ('draw', 0.60, False, 0.0),                                    # drawing hands belong to DrawCall
    ])
    def test_bluff_catch_call_judges_any_hand_on_equity_against_price(self, bucket, equity, hit, weight):
        from pokerfate.strategy.v3.purposes_defensive import BluffCatchCall
        tr = BluffCatchCall().trigger(_facing_ctx(bucket, equity, to_call=10.0, pot=30.0))
        assert tr.hit is hit
        if hit:
            assert tr.weight == pytest.approx(weight)

    @pytest.mark.parametrize("subtype, call", [
        ('board_pair_pocket_pair', True),          # aces over a paired board: the call is kept
        ('board_pair_hero_pair', False),           # a pair that shares the paired board: the refusal stands
    ])
    def test_a_guarded_hand_keeps_its_call_when_the_call_is_refused(self, subtype, call):
        from pokerfate.strategy.v3.purposes_defensive import BluffCatchCall, FoldPurpose
        ctx = _facing_ctx(
            'strong', 0.50, to_call=20.0, pot=60.0, street='turn', spr=0.8, stack=48.0,
            hero_made_subtype=subtype, board_sig=BoardSignals(paired=True),
            villain_bucket_dist={'nuts': 0.48},
        )
        tr = BluffCatchCall().trigger(ctx)
        assert tr.hit is call
        if call:
            assert tr.weight == 0.3
        assert FoldPurpose().trigger(ctx).hit is False

    @pytest.mark.parametrize("price, equity, weight", [
        (0.27, 0.41, 1.5),                                   # four points over a 27% price are thin
        (0.06, 0.20, 1.0 - (0.04 * 0.15 / 0.06 - 0.05) * 7.0),  # over a 6% price they count 2.5 times
        (0.06, 0.24, 0.3 - 0.05 * 0.25 / 0.15),              # eight points: 0.20 in units of the price
    ])
    def test_fold_weight_measures_the_margin_against_a_small_price(self, price, equity, weight):
        from pokerfate.strategy.v3.purposes_defensive import FoldPurpose
        ctx = DecisionCtx(
            facing_bet=True, hero_bucket='medium', equity_range=equity, equity_mc=equity,
            equity_uncertainty=0.10, pot_odds=price, to_call=5.0, pot=40.0, stack=400.0,
        )
        assert FoldPurpose().trigger(ctx).weight == pytest.approx(weight)

    @pytest.mark.parametrize("street, weight", [
        ('flop', 1.5),                                   # pessimistic margin 0.04
        ('turn', 1.0 - (0.09 - 0.05) * 7.0),             # half the uncertainty: margin 0.09
        ('river', 1.5),
    ])
    def test_fold_vote_takes_half_of_the_uncertainty_on_the_turn(self, street, weight):
        from pokerfate.strategy.v3.purposes_defensive import FoldPurpose
        ctx = DecisionCtx(
            facing_bet=True, street=street, hero_bucket='medium', equity_range=0.41, equity_mc=0.41,
            equity_uncertainty=0.10, pot_odds=0.27, to_call=10.0, pot=40.0, stack=400.0,
        )
        assert FoldPurpose().trigger(ctx).weight == pytest.approx(weight)

    @pytest.mark.parametrize("equity, to_call, pot, folds", [
        (0.10, 10.0, 26.0, True),      # overcards the draw call refuses: an ordinary fold vote
        (0.45, 10.0, 60.0, False),     # the draw call takes it
    ])
    def test_fold_votes_on_a_weak_draw_the_draw_call_refuses(self, equity, to_call, pot, folds):
        from pokerfate.strategy.v3.purposes_defensive import DrawCall, FoldPurpose
        ctx = _facing_ctx('weak_draw', equity, to_call=to_call, pot=pot)
        assert DrawCall().trigger(ctx).hit is (not folds)
        assert FoldPurpose().trigger(ctx).hit is folds


class TestMultiwayValueEdge:
    @pytest.mark.parametrize("opponents, bucket, equity, edge", [
        (1, 'nuts', 0.90, False),          # heads-up: the absolute thresholds apply
        (2, 'strong', 0.60, True),         # share 1/3 + 0.26
        (2, 'strong', 0.58, False),
        (3, 'nuts', 0.52, True),           # share 1/4 + 0.26
        (3, 'medium', 0.70, False),
    ])
    def test_top_tier_hand_far_above_its_share(self, opponents, bucket, equity, edge):
        from pokerfate.strategy.v3.purposes_active import _multiway_value_edge
        ctx = DecisionCtx(num_opponents=opponents, hero_bucket=bucket, equity_range=equity)
        assert _multiway_value_edge(ctx) is edge

