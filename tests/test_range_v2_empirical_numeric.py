from types import SimpleNamespace

from pokerfate.strategy.range_v2 import empirical_model as em


def _profile(**overrides):
    base = {
        "name": "hero_target",
        "hands_seen": 160,
        "vpip": 0.78,
        "pfr": 0.10,
        "af": 0.55,
        "wtsd": 0.48,
        "wmsd": 0.45,
        "flop_afq": 0.18,
        "turn_afq": 0.20,
        "river_afq": 0.20,
        "river_bet_freq": 0.22,
        "bluff_win_rate": 0.05,
        "fold_to_cbet": 0.20,
        "river_fold_rate": 0.25,
        "three_bet_pct": 0.01,
        "fold_to_3bet": 0.10,
        "flop_action_count": 80,
        "turn_action_count": 60,
        "river_action_count": 50,
        "river_bet_count": 8,
        "river_check_count": 28,
        "bet_win_count": 20,
        "fold_to_cbet_opps": 20,
        "river_facing_bet_opps": 20,
        "server_af_prior": 0.0,
        "server_wtsd_prior": 0.0,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def _numeric_model():
    opponents = {
        "loose": {
            "hands_seen": 400,
            "vpip_count": 320,
            "pfr_count": 40,
            "server_af_prior": 0.55,
            "server_wtsd_prior": 0.48,
            "showdown_win_count": 12,
            "showdown_count": 30,
            "flop_seen_count": 80,
            "flop_bet_count": 4,
            "flop_passive_count": 36,
            "turn_bet_count": 3,
            "turn_passive_count": 27,
            "river_bet_count": 2,
            "river_call_count": 8,
            "river_check_count": 20,
            "bluff_win_count": 0,
            "bet_win_count": 12,
            "fold_to_cbet_count": 2,
            "fold_to_cbet_opps": 12,
            "river_facing_bet_fold_count": 2,
            "river_facing_bet_opps": 12,
            "three_bet_count": 0,
            "three_bet_opportunities": 30,
            "fold_to_3bet_count": 1,
            "fold_to_3bet_opps": 10,
            "bet_count": 6,
            "raise_count": 0,
            "call_count": 48,
            "check_count": 42,
        },
        "tight": {
            "hands_seen": 400,
            "vpip_count": 80,
            "pfr_count": 72,
            "server_af_prior": 2.4,
            "server_wtsd_prior": 0.20,
            "showdown_win_count": 18,
            "showdown_count": 30,
            "flop_seen_count": 80,
            "flop_bet_count": 28,
            "flop_passive_count": 12,
            "turn_bet_count": 20,
            "turn_passive_count": 10,
            "river_bet_count": 18,
            "river_call_count": 4,
            "river_check_count": 8,
            "bluff_win_count": 8,
            "bet_win_count": 20,
            "fold_to_cbet_count": 10,
            "fold_to_cbet_opps": 12,
            "river_facing_bet_fold_count": 10,
            "river_facing_bet_opps": 12,
            "three_bet_count": 8,
            "three_bet_opportunities": 30,
            "fold_to_3bet_count": 6,
            "fold_to_3bet_opps": 10,
            "bet_count": 50,
            "raise_count": 10,
            "call_count": 15,
            "check_count": 10,
        },
    }
    action_counts = {
        "loose": {
            "flop|half|0": {
                "air": {"bet": 18, "check": 2},
                "strong": {"bet": 2, "check": 18},
            }
        },
        "tight": {
            "flop|half|0": {
                "air": {"bet": 2, "check": 18},
                "strong": {"bet": 18, "check": 2},
            }
        },
    }
    preflop_counts = {
        "loose": {"BTN": {"air": 18, "strong": 2}, "*": {"air": 18, "strong": 2}},
        "tight": {"BTN": {"air": 2, "strong": 18}, "*": {"air": 2, "strong": 18}},
    }
    return {
        "schema": "range_v2_empirical_model_v2",
        "numeric_profile_priors": em.build_numeric_profile_payload(
            opponents,
            action_counts,
            preflop_counts,
            action_prior_weight=20.0,
        ),
        "action_likelihoods": {},
        "preflop_bucket_priors": {},
    }


def _install_model(monkeypatch, model):
    em._numeric_index_for_key.cache_clear()
    monkeypatch.setattr(em, "_load_empirical_model_for_key", lambda _key: model)


def test_empirical_action_likelihood_uses_numeric_neighbors(monkeypatch):
    _install_model(monkeypatch, _numeric_model())
    ctx = SimpleNamespace(big_blind=10000, is_raise_over=False, bet_ratio=0.50)

    dist, blend, key, n = em.empirical_action_likelihood(
        "raise",
        "flop",
        ctx,
        _profile(),
    )

    assert key.startswith("knn:flop|half|0:bet")
    assert n > 0
    assert blend > 0
    assert dist["air"] > dist["strong"]


def test_empirical_preflop_prior_uses_numeric_neighbors(monkeypatch):
    _install_model(monkeypatch, _numeric_model())

    dist, blend, key, n = em.empirical_preflop_bucket_prior(
        "BTN",
        _profile(hands_seen=20),
        10000,
    )

    assert key.startswith("knn:BTN")
    assert n > 0
    assert blend > 0
    assert dist["air"] > dist["strong"]


def test_empirical_action_likelihood_falls_back_to_global_without_labels(monkeypatch):
    _install_model(monkeypatch, {
        "schema": "range_v2_empirical_model_v2",
        "action_likelihoods": {
            "flop|bet|half|0|*": {
                "cat_probs": {"air": 0.70, "strong": 0.20},
                "n": 30,
                "blend": 0.03,
            }
        },
        "preflop_bucket_priors": {},
    })
    ctx = SimpleNamespace(big_blind=10000, is_raise_over=False, bet_ratio=0.50)

    dist, blend, key, n = em.empirical_action_likelihood(
        "raise",
        "flop",
        ctx,
        _profile(),
    )

    assert key == "flop|bet|half|0|*"
    assert n == 30
    assert blend == 0.03
    assert dist == {"strong": 0.2, "air": 0.7}
