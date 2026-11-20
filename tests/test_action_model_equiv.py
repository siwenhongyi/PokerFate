"""ActionModel.batch_likelihood over a fixed batch of inputs.

Preflop / postflop, dry / wet / paired boards, every action, known and unknown opponents,
every bet size, with and without hero cards.  Postflop the likelihood is the fitted model
looked up by each combo's strength bucket; this pins that lookup down against a plain loop,
and that there is no update at all where the model has nothing to say.
"""
from __future__ import annotations

import numpy as np
import pytest

from pokerfate.core.card import Card
from pokerfate.strategy.range_v2.action_model import (
    ActionContext,
    ActionModel,
    PlayerProfile,
)


def _c(s: str) -> Card:
    return Card.from_str(s)


def _board(*ss: str):
    return [_c(s) for s in ss]


def _make_inputs():
    """返回 (label, action, street, ctx, prof, board, hero) 的列表。"""
    cases = []

    # 翻前 — 各 facing_action
    for fa in ('open', '3bet', '4bet'):
        for action in ('raise', 'call', 'fold'):
            ctx = ActionContext(position='CO', board=[], street='preflop',
                                facing_action=fa, bet_ratio=2.5)
            prof = PlayerProfile(name='reg', hands_seen=200,
                                 vpip=0.27, pfr=0.22, af=2.5,
                                 three_bet_pct=0.07)
            cases.append((f'pf-{fa}-{action}', action, 'preflop', ctx, prof, [], None))

    # 翻前 - 大注 narrow
    ctx = ActionContext(position='UTG', board=[], street='preflop',
                        facing_action='open', bet_ratio=15.0)
    prof = PlayerProfile(name='maniac', hands_seen=80, vpip=0.5, pfr=0.3, af=3.5)
    cases.append(('pf-deep-overshove', 'raise', 'preflop', ctx, prof, [], None))

    # 翻前 - cold start
    ctx_cs = ActionContext(position='BB', board=[], street='preflop',
                           facing_action='open', bet_ratio=2.5)
    prof_cs = PlayerProfile(name='new', hands_seen=3, vpip=0.30, pfr=0.20, af=2.0)
    cases.append(('pf-cold-call', 'call', 'preflop', ctx_cs, prof_cs, [], None))

    # 翻后 — 不同板面 / 不同 street / 不同 action / 不同 sizing
    boards = [
        ('dry-Ahi', _board('As', '7d', '2c')),
        ('wet-flush', _board('Jh', 'Th', '9h')),
        ('paired', _board('Kc', 'Kd', '7s')),
        ('mid-conn', _board('9s', '8d', '7c')),
    ]
    streets_with_4 = [('flop', _board('As', '7d', '2c')),
                      ('turn', _board('As', '7d', '2c', 'Th')),
                      ('river', _board('As', '7d', '2c', 'Th', '5c'))]
    actions_pf = ['raise', 'call', 'fold', 'check']

    profs = [
        ('reg', PlayerProfile(name='reg', hands_seen=300, vpip=0.25, pfr=0.20,
                              af=2.8, fold_to_cbet=0.55, fold_to_cbet_opps=80,
                              wtsd=0.24, flop_action_count=60, turn_action_count=40,
                              river_action_count=35, river_fold_rate=0.42,
                              flop_afq=0.50, turn_afq=0.40, river_afq=0.30)),
        ('whale', PlayerProfile(name='whale', hands_seen=120, vpip=0.55, pfr=0.10,
                                af=0.8, wtsd=0.40, fold_to_cbet=0.20, fold_to_cbet_opps=40,
                                flop_action_count=50, turn_action_count=30,
                                river_action_count=25)),
        ('cold', PlayerProfile(name='unknown', hands_seen=8)),
    ]

    for board_label, board in boards:
        street = 'flop'
        for action in actions_pf:
            for prof_label, prof in profs:
                ctx = ActionContext(position='BB', board=board, street=street,
                                    facing_action='open', bet_ratio=0.66 if action == 'raise' else 0.0)
                cases.append((f'{street}-{board_label}-{action}-{prof_label}',
                              action, street, ctx, prof, board, None))

    # turn/river 路径
    for street, board in streets_with_4[1:]:
        for action in ('raise', 'call', 'fold'):
            for prof_label, prof in profs:
                ctx = ActionContext(position='BTN', board=board, street=street,
                                    facing_action='bet',
                                    bet_ratio=1.2 if action == 'raise' else 0.0,
                                    is_raise_over=False)
                cases.append((f'{street}-dry-{action}-{prof_label}',
                              action, street, ctx, prof, board, None))

    # polar reraise narrow path: passive villain raise_over on turn/river
    for street, board in streets_with_4[1:]:
        passive = PlayerProfile(name='whale', hands_seen=80, vpip=0.50, pfr=0.10,
                                af=0.9, wtsd=0.35, fold_to_cbet_opps=20,
                                flop_action_count=30, turn_action_count=20)
        ctx = ActionContext(position='SB', board=board, street=street,
                            facing_action='bet', bet_ratio=2.0, is_raise_over=True)
        cases.append((f'{street}-polar-raise_over', 'raise', street, ctx, passive, board, None))

    # hero blocker path
    hero = [_c('Ah'), _c('Kh')]
    board = _board('2h', '5h', '9c')
    ctx = ActionContext(position='CO', board=board, street='flop',
                        facing_action='bet', bet_ratio=0.66)
    prof = PlayerProfile(name='reg', hands_seen=200, vpip=0.25, pfr=0.20, af=2.5)
    cases.append(('flop-hero-blocker', 'raise', 'flop', ctx, prof, board, hero))

    # sizing 各档位
    for ratio, label in [(0.30, 'tiny'), (0.50, 'small'), (0.75, 'medium'),
                         (1.10, 'large'), (1.80, 'overbet')]:
        ctx = ActionContext(position='UTG', board=_board('As', '7d', '2c'),
                            street='flop', facing_action='bet', bet_ratio=ratio)
        prof = PlayerProfile(name='reg', hands_seen=200, vpip=0.27, pfr=0.22,
                             af=2.5, wtsd=0.24, flop_action_count=50)
        cases.append((f'sizing-{label}', 'raise', 'flop', ctx, prof,
                      _board('As', '7d', '2c'), None))

    return cases


_MODEL = {"likelihood_model": {"features": ["size_pot"], "actions": {
    "bet": {"base": {st: {"nuts": 0.0, "strong": -0.3, "medium": -1.0, "draw": -0.5, "weak_draw": -1.5, "air": -2.0}
                     for st in ("flop", "turn", "river")},
            "weights": {"size_pot": {"nuts": 0.6, "air": 0.2}}},
    "call": {"base": {st: {"nuts": -0.2, "strong": 0.0, "medium": -0.4, "draw": -0.1, "weak_draw": -1.2, "air": -2.5}
                      for st in ("flop", "turn", "river")}, "weights": {}},
}}}


@pytest.fixture()
def fitted(tmp_path, monkeypatch):
    import json
    path = tmp_path / "fit.json"
    path.write_text(json.dumps(_MODEL), encoding="utf-8")
    monkeypatch.setenv("PF_FORMULA_FIT_PATH", str(path))


@pytest.fixture()
def outputs(fitted):
    am = ActionModel()
    out = {}
    for label, action, street, ctx, prof, board, hero in _make_inputs():
        if street != 'preflop':
            ctx.likelihood_features = {"size_pot": 1.0 if ctx.bet_ratio > 0.8 else 0.0}
        out[label] = np.array(am.batch_likelihood(action, street, ctx, prof, board, hero_cards=hero), copy=True)
    return out


def test_postflop_likelihood_is_the_model_of_each_combos_bucket(outputs):
    from pokerfate.strategy.range_v2 import hand_categorizer as hcat
    from pokerfate.strategy.range_v2 import hand_combo_map as hcm
    am = ActionModel()
    checked = 0
    for label, action, street, ctx, prof, board, hero in _make_inputs():
        if street == 'preflop':
            continue
        spec = _MODEL["likelihood_model"]["actions"].get(
            {'raise': 'raise_over' if ctx.is_raise_over else 'bet'}.get(action, action))
        if spec is None:                                   # check, fold, raise over a bet: no model
            assert np.all(outputs[label] == 1.0), label
            continue
        size_pot = 1.0 if ctx.bet_ratio > 0.8 else 0.0     # what the fixture put in the context
        score = {cat: base + spec["weights"].get("size_pot", {}).get(cat, 0.0) * size_pot
                 for cat, base in spec["base"][street].items()}
        top = max(score.values())
        board_ints = {hcm.card_to_int(c) for c in board}
        for idx in range(0, 1326, 7):
            c1, c2 = hcm.ALL_COMBOS[idx]
            if c1 in board_ints or c2 in board_ints:
                continue
            cat = hcat.categorize_cards([hcm.int_to_card(c1), hcm.int_to_card(c2)], board)
            if street == 'river' and cat in ('draw', 'weak_draw'):
                cat = 'air'
            assert outputs[label][idx] == pytest.approx(np.exp(score[cat] - top)), (label, idx, cat)
            checked += 1
    assert checked > 2000


def test_without_a_model_postflop_actions_say_nothing():
    am = ActionModel()                                     # conftest: PF_FORMULA_FIT_PATH=off
    for label, action, street, ctx, prof, board, hero in _make_inputs():
        if street != 'preflop':
            ctx.likelihood_features = {"size_pot": 1.0}
            assert np.all(am.batch_likelihood(action, street, ctx, prof, board, hero_cards=hero) == 1.0), label


def test_batch_likelihood_shape_and_finite(outputs):
    """所有输出必须是 (1326,) 有限正数。"""
    for label, arr in outputs.items():
        assert arr.shape == (1326,), f"{label}: shape {arr.shape}"
        assert np.all(np.isfinite(arr)), f"{label}: non-finite values"
        assert np.all(arr >= 0.0), f"{label}: negative values"


def test_categorize_all_cache_correctness():
    """缓存机制改动后,_categorize_all 必须给出和无缓存版本一样的结果。

    用两个不同板面交替调用,验证缓存不会"粘住"。
    """
    am = ActionModel()
    b1 = _board('As', '7d', '2c')
    b2 = _board('Jh', 'Th', '9h')
    cats_b1_v1 = am._categorize_all(b1)
    cats_b2 = am._categorize_all(b2)
    cats_b1_v2 = am._categorize_all(b1)  # 重新拿 b1 应该和首次一致
    assert cats_b1_v1 == cats_b1_v2, "categorize cache returned different results for same board"
    # 板面不同应该产生不同分类(至少有一些位置不一致)
    assert any(a != b for a, b in zip(cats_b1_v1, cats_b2)), \
        "different boards produced identical categorizations — suspicious"
