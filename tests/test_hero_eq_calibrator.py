"""Tests for HeroEquityCalibrator (缺陷 C)."""

from pokerfate.strategy.range_v2.hero_eq_calibrator import (
    HeroEquityCalibrator,
    _BIAS_SHRINK_K,
    classify_action_ctx_from_trigger,
    classify_action_ctx_from_decision,
)


def _shrunk_shift(raw_bias: float, n: int) -> float:
    clamped = max(-0.25, min(0.25, raw_bias))
    return clamped * n / (n + _BIAS_SHRINK_K)


class TestHeroEquityCalibrator:
    def test_empty_returns_raw(self):
        cal = HeroEquityCalibrator()
        assert cal.calibrate(0.50, 'medium', 'flop', 2) == 0.50

    def test_below_min_samples_returns_raw(self):
        cal = HeroEquityCalibrator()
        # 9 samples < MIN=10, so no calibration yet
        for _ in range(9):
            cal.record('medium', 'flop', 2, predicted=0.40, actual=0.80)
        assert cal.calibrate(0.50, 'medium', 'flop', 2) == 0.50

    def test_positive_bias_shifts_up(self):
        cal = HeroEquityCalibrator()
        # Historical: pred=40%, actual=80% → bias=+40%
        # bias clamped to +25%, then shrunk by n/(n+K).
        for _ in range(10):
            cal.record('strong', 'flop', 2, predicted=0.40, actual=0.80)
        result = cal.calibrate(0.50, 'strong', 'flop', 2)
        expected = 0.50 + _shrunk_shift(0.40, 10)
        assert abs(result - expected) < 1e-9

    def test_negative_bias_shifts_down(self):
        cal = HeroEquityCalibrator()
        # Historical: pred=70%, actual=50% → bias=-20%
        for _ in range(10):
            cal.record('medium', 'turn', 1, predicted=0.70, actual=0.50)
        result = cal.calibrate(0.60, 'medium', 'turn', 1)
        expected = 0.60 + _shrunk_shift(-0.20, 10)
        assert abs(result - expected) < 1e-9

    def test_clamp_within_0_1(self):
        cal = HeroEquityCalibrator()
        # Extreme bias scenario
        for _ in range(1000):
            cal.record('nuts', 'river', 1, predicted=0.10, actual=0.95)
        # raw + 0.25 = 1.05 → clamp to 1.0
        result = cal.calibrate(0.95, 'nuts', 'river', 1)
        assert result == 1.0

    def test_num_opp_binning(self):
        cal = HeroEquityCalibrator()
        # n_opp = 5 should bin to '3+', same as n_opp=3 or 4
        for _ in range(10):
            cal.record('strong', 'flop', 3, predicted=0.50, actual=0.70)
        # query with n_opp=5 should find the same bucket
        r3 = cal.calibrate(0.50, 'strong', 'flop', 3)
        r5 = cal.calibrate(0.50, 'strong', 'flop', 5)
        r4 = cal.calibrate(0.50, 'strong', 'flop', 4)
        assert r3 == r5 == r4
        assert r3 > 0.50

    def test_different_keys_isolated(self):
        cal = HeroEquityCalibrator()
        # Heavy positive bias on medium/flop/2
        for _ in range(10):
            cal.record('medium', 'flop', 2, predicted=0.30, actual=0.80)
        # Different key (street=turn) — no data, should return raw
        assert cal.calibrate(0.50, 'medium', 'turn', 2) == 0.50
        # Different hero_bucket — no data, should return raw
        assert cal.calibrate(0.50, 'strong', 'flop', 2) == 0.50
        # Matching key — shifts up
        assert cal.calibrate(0.50, 'medium', 'flop', 2) > 0.50

    def test_invalid_input_ignored(self):
        cal = HeroEquityCalibrator()
        # Out-of-range values should be dropped on record
        cal.record('medium', 'flop', 2, predicted=-0.1, actual=0.5)
        cal.record('medium', 'flop', 2, predicted=1.5, actual=0.5)
        cal.record('', 'flop', 2, predicted=0.5, actual=0.5)
        assert cal.sample_count('medium', 'flop', 2) == 0

    def test_sample_count(self):
        cal = HeroEquityCalibrator()
        for _ in range(5):
            cal.record('draw', 'turn', 1, 0.3, 0.4)
        assert cal.sample_count('draw', 'turn', 1) == 5
        assert cal.sample_count('draw', 'turn', 2) == 0

    def test_persistence_roundtrip(self):
        cal = HeroEquityCalibrator()
        for _ in range(10):
            cal.record('strong', 'flop', 2, 0.40, 0.80)
        for _ in range(5):
            cal.record('air', 'river', 1, 0.20, 0.10)

        data = cal.to_dict()
        assert data  # non-empty

        restored = HeroEquityCalibrator.from_dict(data)
        assert restored.sample_count('strong', 'flop', 2) == 10
        assert restored.sample_count('air', 'river', 1) == 5
        # calibration should match the original
        orig = cal.calibrate(0.50, 'strong', 'flop', 2)
        new = restored.calibrate(0.50, 'strong', 'flop', 2)
        assert orig == new

    def test_from_dict_none(self):
        assert HeroEquityCalibrator.from_dict(None).sample_count('a', 'b', 1) == 0
        assert HeroEquityCalibrator.from_dict({}).sample_count('a', 'b', 1) == 0

    def test_bias_for_diagnostics(self):
        cal = HeroEquityCalibrator()
        # bias ≈ +15% raw
        for _ in range(10):
            cal.record('medium', 'flop', 2, 0.50, 0.65)
        assert abs(cal.bias_for('medium', 'flop', 2) - 0.15) < 0.01
        # bias_for returns 0 when below threshold
        assert cal.bias_for('nuts', 'flop', 2) == 0.0


class TestActionCtxSplit:
    """action_ctx 三档分桶：passive / bet / raise（避免 bet/raise 场景 bias
    被 passive 样本稀释）。"""

    def test_trigger_classifier(self):
        assert classify_action_ctx_from_trigger('action:raise_over') == 'raise'
        assert classify_action_ctx_from_trigger('action:raise') == 'raise'
        assert classify_action_ctx_from_trigger('action:bet') == 'bet'
        # passive 包括 check/call/fold_other/reset/board（和 B 不压缩场景一致）
        assert classify_action_ctx_from_trigger('action:check') == 'passive'
        assert classify_action_ctx_from_trigger('action:call') == 'passive'
        assert classify_action_ctx_from_trigger('action:fold_other') == 'passive'
        assert classify_action_ctx_from_trigger('reset') == 'passive'
        assert classify_action_ctx_from_trigger('board:flop') == 'passive'
        assert classify_action_ctx_from_trigger('') == 'passive'
        assert classify_action_ctx_from_trigger('unknown_trigger') == 'passive'

    def test_decision_classifier(self):
        # 不面对下注 → passive
        assert classify_action_ctx_from_decision(False, 0, 100) == 'passive'
        # 面对 0.5x pot 下注 → bet
        # pot_before = 50 - 25 = ? 等等，pot 这里是 current 含下注。
        # to_call=25, pot=75（含下注），pot_before=50，ratio=0.5
        assert classify_action_ctx_from_decision(True, 25, 75) == 'bet'
        # 面对 1x pot 下注（pot_before=50, to_call=50）→ raise
        assert classify_action_ctx_from_decision(True, 50, 100) == 'raise'
        # 面对 2x pot 下注 → raise
        assert classify_action_ctx_from_decision(True, 200, 300) == 'raise'

    def test_keys_are_isolated_by_ctx(self):
        """同桌 bucket/street/num_opp 下，不同 action_ctx 是独立桶。"""
        cal = HeroEquityCalibrator()
        # raise 场景：预测 20%, 实际 40%（大 bias）
        for _ in range(10):
            cal.record('medium', 'turn', 3, 0.20, 0.40, action_ctx='raise')
        # passive 场景：预测 50%, 实际 52%（小 bias）
        for _ in range(10):
            cal.record('medium', 'turn', 3, 0.50, 0.52, action_ctx='passive')

        # raise 桶 bias 大
        assert abs(cal.bias_for('medium', 'turn', 3, 'raise') - 0.20) < 0.01
        # passive 桶 bias 小
        assert abs(cal.bias_for('medium', 'turn', 3, 'passive') - 0.02) < 0.01
        # 两个桶独立，不会混
        raw = 0.30
        raise_expected = raw + _shrunk_shift(0.20, 10)
        passive_expected = raw + _shrunk_shift(0.02, 10)
        assert abs(cal.calibrate(raw, 'medium', 'turn', 3, 'raise') - raise_expected) < 1e-9
        assert abs(cal.calibrate(raw, 'medium', 'turn', 3, 'passive') - passive_expected) < 1e-9

    def test_default_ctx_passive_backwards_compat(self):
        """不传 action_ctx 时默认 passive，保证旧调用不崩。"""
        cal = HeroEquityCalibrator()
        for _ in range(10):
            cal.record('medium', 'flop', 2, 0.50, 0.60)
        # 不传 action_ctx 和传 'passive' 等价
        assert cal.calibrate(0.50, 'medium', 'flop', 2) == cal.calibrate(
            0.50, 'medium', 'flop', 2, action_ctx='passive'
        )
        # 不同 ctx 查询没数据 → raw
        assert cal.calibrate(0.50, 'medium', 'flop', 2, action_ctx='raise') == 0.50

    def test_persist_with_ctx(self):
        cal = HeroEquityCalibrator()
        for _ in range(10):
            cal.record('medium', 'turn', 3, 0.20, 0.40, action_ctx='raise')
        d = cal.to_dict()
        # key 格式应包含 action_ctx 段
        assert any('|raise' in k for k in d)
        restored = HeroEquityCalibrator.from_dict(d)
        assert restored.sample_count('medium', 'turn', 3, 'raise') == 10


class TestMultiwayActualRandomFill:
    """方案 5：_actual_hero_eq_multi_at_street 的 n_unshown 参数."""

    def test_no_unshown_matches_legacy(self):
        """n_unshown=0 等于原 1-way 模拟。"""
        from pokerfate.calibration.showdown_calibration import ShowdownCalibrator as SC
        from pokerfate.core.card import Card

        hero = [Card.from_str('As'), Card.from_str('Ks')]
        board = [Card.from_str(c) for c in ['Kh', '7h', '2d']]
        v = [Card.from_str('Qc'), Card.from_str('Jd')]
        eq = SC._actual_hero_eq_multi_at_street(hero, [v], board, n_unshown=0)
        assert eq is not None
        # hero 顶对 A 踢脚 vs villain 高牌 → 大幅领先
        assert eq > 0.80

    def test_unshown_lowers_eq(self):
        """加入未亮 villain 填随机牌后，eq 应下降（多一个对手变难赢）。"""
        from pokerfate.calibration.showdown_calibration import ShowdownCalibrator as SC
        from pokerfate.core.card import Card

        hero = [Card.from_str('9s'), Card.from_str('9h')]
        # river board 没给 9 任何帮助
        board = [Card.from_str(c) for c in ['5d', '8c', '2h', 'Kd', 'Jc']]
        v_weak = [Card.from_str('Qh'), Card.from_str('Th')]  # villain Q 高

        eq_hu = SC._actual_hero_eq_multi_at_street(hero, [v_weak], board, n_unshown=0)
        eq_2w = SC._actual_hero_eq_multi_at_street(hero, [v_weak], board, n_unshown=1)
        # 单挑 vs Q 高必胜；加一个随机对手后 eq 应明显下降
        assert eq_hu > 0.99
        assert eq_2w < eq_hu
        assert eq_2w < 0.85   # 现实的多人池 eq 应该显著低

    def test_river_deterministic_all_shown(self):
        """river 全亮牌：不走 MC，精确比较。"""
        from pokerfate.calibration.showdown_calibration import ShowdownCalibrator as SC
        from pokerfate.core.card import Card

        hero = [Card.from_str('As'), Card.from_str('Ad')]  # 一对 A
        board = [Card.from_str(c) for c in ['Ah', '7h', '2d', '5c', '9s']]
        v1 = [Card.from_str('Kc'), Card.from_str('Kd')]  # KK (输)
        v2 = [Card.from_str('Qc'), Card.from_str('Qd')]  # QQ (输)
        eq = SC._actual_hero_eq_multi_at_street(hero, [v1, v2], board, n_unshown=0)
        assert eq == 1.0   # hero 三条 A 精确赢两个对手

    def test_skip_without_shown_anchor(self):
        """没有任何亮牌 villain 时方案 5 语义上没意义——调用方应先过滤。"""
        from pokerfate.calibration.showdown_calibration import ShowdownCalibrator as SC
        from pokerfate.core.card import Card

        hero = [Card.from_str('As'), Card.from_str('Ks')]
        board = [Card.from_str(c) for c in ['Kh', '7h', '2d']]
        # villain_hands=[] → 返回 None
        assert SC._actual_hero_eq_multi_at_street(hero, [], board, n_unshown=2) is None

    def test_integration_selection_bias_shrunk(self):
        """集成测试：对比"只看亮牌子集" vs "N 人随机填"的 Δ 分布。
        方案 5 应该让两边口径一致，Δ 靠近 0。"""
        from pokerfate.calibration import ShowdownCalibrator
        from pokerfate.core.card import Card
        from pokerfate.strategy.range_v2.bayesian_range_tracker import BayesianRangeTracker
        from pokerfate.strategy.range_v2.action_model import ActionModel, ActionContext, PlayerProfile

        cal = ShowdownCalibrator(logger=None)
        tracker = BayesianRangeTracker(action_model=ActionModel())

        HERO_ID = 0
        def hook(**kw):
            if kw['player_id'] == HERO_ID:
                return
            aw = kw.get('active_weights')
            if aw:
                kw['active_weights'] = {p: w for p, w in aw.items() if p != HERO_ID}
            cal.record_prediction(**kw)

        tracker._prediction_hook = hook
        tracker._name_resolver = lambda pid: f'P{pid}'

        hero = [Card.from_str('9s'), Card.from_str('9h')]  # 一对 9
        tracker.set_known_cards(hero)
        tracker.start_new_hand()
        cal.start_hand(1)

        prof = PlayerProfile(name='v', hands_seen=20, vpip=0.30, pfr=0.20, af=2.0)
        for pid in range(3):
            tracker.reset_hand(player_id=pid, position=['SB', 'CO', 'BTN'][pid], profile=prof)

        board = [Card.from_str(c) for c in ['5h', '8d', 'Kc']]
        ctx = ActionContext(position='CO', board=board, street='flop', facing_action='bet')
        tracker.observe_action(1, 'call', 'flop', ctx, prof, board=board)
        tracker.observe_action(2, 'call', 'flop', ctx, prof, board=board)

        # 只有 P1 亮牌（P2 未亮）—— 方案 5 应该为 P2 随机填牌
        cal.record_actual(1, [Card.from_str('7c'), Card.from_str('2d')], [], hero)
        # P2 不 record_actual
        final = board + [Card.from_str('4s'), Card.from_str('Jh')]
        results = cal.finalize_hand_calibration(hero_cards=hero, final_board=final)

        for r in results:
            # actual_multi 非 None 说明方案 5 路径被触发
            if r.record.active_player_ids:
                assert r.actual_hero_eq_street_multi is not None, (
                    '方案 5 应在 active_player_ids 非空且至少一个亮牌时计算 actual_multi'
                )
                # 单挑 actual > 多人池 actual（多了一个随机对手）
                assert r.actual_hero_eq_street_multi <= r.actual_hero_eq_street + 0.05, (
                    f'多人池 actual 应 ≤ 单挑 actual，实际 HU={r.actual_hero_eq_street:.3f} '
                    f'Multi={r.actual_hero_eq_street_multi:.3f}'
                )
