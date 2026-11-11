"""Bucket-ML layer: read-only overlay (no compounding) and train/serve feature parity."""
import numpy as np
import pytest

from pokerfate.core.card import Card
from pokerfate.strategy.range_v2 import bayesian_range_tracker as brt
from pokerfate.strategy.range_v2 import bucket_ml_calibration as bml
from pokerfate.strategy.range_v2.action_model import ActionContext, ActionModel, PlayerProfile


def _cards(*s):
    return [Card.from_str(c) for c in s]


def _ctx(board, street, **kw):
    base = dict(position='BTN', board=list(board), street=street, facing_action='check',
                bet_ratio=0.66, is_ip=True, big_blind=10000.0)
    base.update(kw)
    return ActionContext(**base)


def _fake_ml(target):
    def _cal(bucket_probs, **kwargs):
        return dict(target), {"mode": "lgbm", "used": True, "alpha": 1.0}
    return _cal


def _run(monkeypatch, ml):
    tracker = brt.BayesianRangeTracker(ActionModel())
    tracker.set_known_cards(_cards('Ah', 'Kc'))
    prof = PlayerProfile(hands_seen=200, vpip=0.3, pfr=0.2)
    tracker.reset_hand(1, 'CO', prof)
    if ml is not None:
        monkeypatch.setattr(brt, 'calibrate_bucket_probs', ml)
    else:
        monkeypatch.setattr(brt, 'calibrate_bucket_probs', lambda *a, **k: ({}, {}))
    board = _cards('7h', '7d', '2c')
    tracker.reweight_for_board(board)
    tracker.observe_action(1, 'bet', 'flop', _ctx(board, 'flop'), prof, board)
    turn = board + _cards('Jd')
    tracker.observe_action(1, 'bet', 'turn', _ctx(turn, 'turn'), prof, turn)
    return tracker


def test_ml_overlay_is_visible_to_readers_but_does_not_compound(monkeypatch):
    target = {'nuts': 0.6, 'strong': 0.3, 'medium': 0.05, 'draw': 0.02, 'weak_draw': 0.02, 'air': 0.01}
    off = _run(monkeypatch, None)
    on = _run(monkeypatch, _fake_ml(target))
    board = _cards('7h', '7d', '2c', 'Jd')
    dist_off = on_dist = None
    dist_off = off.get_bucket_distribution(1, board)
    on_dist = on.get_bucket_distribution(1, board)
    # readers see the overlay ...
    assert on_dist['nuts'] + on_dist['strong'] > dist_off['nuts'] + dist_off['strong'] + 0.1
    # ... but the formula state carried into the next update is identical to ML-off
    np.testing.assert_allclose(on._formula_weights[1], off.get_distribution(1), atol=1e-12)


def test_next_update_starts_from_formula_state(monkeypatch):
    target = {'nuts': 0.6, 'strong': 0.3, 'medium': 0.05, 'draw': 0.02, 'weak_draw': 0.02, 'air': 0.01}
    on = _run(monkeypatch, _fake_ml(target))
    # observe once more: before the likelihood step the weights must be the saved formula state
    saved = on._formula_weights[1].copy()
    seen = {}
    orig = brt.BayesianRangeTracker._apply_bucket_calibration

    def spy(self, pid, street, board, trigger):
        seen['pre_ml_sum_nuts'] = float(self._weights[pid].sum())
        return orig(self, pid, street, board, trigger)
    monkeypatch.setattr(brt.BayesianRangeTracker, '_apply_bucket_calibration', spy)
    board = _cards('7h', '7d', '2c', 'Jd', '3s')
    prof = PlayerProfile(hands_seen=200, vpip=0.3, pfr=0.2)
    on.observe_action(1, 'check', 'river', _ctx(board, 'river', bet_ratio=0.0), prof, board)
    assert 1 in on._formula_weights          # overlay applied again on the river
    assert not np.allclose(on._formula_weights[1], saved)  # and the formula state moved with the new action
    assert seen  # calibration ran


def test_runtime_features_carry_profile_and_no_version_onehots():
    probs = np.array([0.1, 0.2, 0.3, 0.1, 0.1, 0.2])
    prof = PlayerProfile(hands_seen=500, vpip=0.4, pfr=0.1)
    feats = bml._feature_values(
        probs, street='turn', trigger='action:call', active_count=2, board=_cards('7h', '7d', '2c', 'Jd'),
        range_pct=0.5, hero_bucket='medium', player_profile=bml.profile_feature_dict(prof))
    assert feats['profile_vpip'] == pytest.approx(0.4)
    assert feats['profile_hands_seen'] == pytest.approx(0.1)
    assert not any(k.startswith('strategy_version=') or k.startswith('experiment_profile=') for k in feats)
    assert bml.profile_feature_dict(None) is None


def test_training_adapter_uses_runtime_feature_function():
    from scripts.fit_range_lgbm_calibration import _bucket_features_runtime
    row = {
        'bucket_dist': {'nuts': 0.1, 'strong': 0.2, 'medium': 0.3, 'draw': 0.1, 'weak_draw': 0.1, 'air': 0.2},
        'street': 'turn', 'trigger': 'action:call', 'active_player_count': 2, 'board': ['7h', '7d', '2c', 'Jd'],
        'range_pct': 0.5, 'hero_bucket': 'medium', 'position': 'BB', 'is_ip': False, 'facing_action': 'raise',
        'preflop_action_type': 'call_open', 'action_bet_ratio': 0.66, 'bet_size_bucket': 'two_third',
        'is_raise_over': False, 'action_sequence': 'flop:bet|flop:call|turn:bet|turn:call',
        'player_profile': {'hands_seen': 500, 'vpip': 0.4, 'pfr': 0.1},
    }
    a = _bucket_features_runtime(row)
    b = bml._feature_values(
        np.array([0.1, 0.2, 0.3, 0.1, 0.1, 0.2]), street='turn', trigger='action:call', active_count=2,
        board=_cards('7h', '7d', '2c', 'Jd'), range_pct=0.5, hero_bucket='medium', position='BB', is_ip=False,
        facing_action='raise', preflop_action_type='call_open', action_bet_ratio=0.66, bet_size_bucket='two_third',
        is_raise_over=False, action_sequence='flop:bet|flop:call|turn:bet|turn:call',
        player_profile={'hands_seen': 500, 'vpip': 0.4, 'pfr': 0.1})
    assert a == b
    assert 'profile_vpip' not in _bucket_features_runtime(row, profile_features=False)


def test_prediction_record_keeps_player_profile():
    from pokerfate.calibration.showdown_calibration import PredictionRecord
    rec = PredictionRecord(hand_id=1, street='flop', player_id=1, player_name='v', board=[], trigger='action:bet',
                           range_pct=0.5, bucket_dist={}, hero_cards=None, predicted_hero_eq=None,
                           player_profile={'vpip': 0.3})
    assert rec.player_profile == {'vpip': 0.3}
