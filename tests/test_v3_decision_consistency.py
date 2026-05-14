"""Decision consistency regressions for v3 strategy tuning.

These tests lock behavior that P0 replay/sweep proved important, so later
parameter searches cannot silently reintroduce passive leaks.
"""

from __future__ import annotations

from pokerfate.core.card import Card
from pokerfate.strategy.v3 import BoardSignals, DecisionCtx, V3Engine, VillainStats
from pokerfate.strategy.v3 import board as v3_board


def card(s: str) -> Card:
    return Card.from_str(s)


def cards(*strs: str) -> list[Card]:
    return [card(s) for s in strs]


def candidate_prob(out, purpose_id: str) -> float:
    return dict(out.candidates).get(purpose_id, 0.0)


def top_candidate(out) -> tuple[str, float]:
    return max(out.candidates, key=lambda item: item[1])


def sticky_passive_stats(**over) -> VillainStats:
    base = dict(
        vpip=0.58,
        pfr=0.10,
        af=0.7,
        fold_to_cbet=0.18,
        fold_to_cbet_opps=12,
        wtsd=0.42,
        river_fold_rate=0.22,
        river_action_count=12,
        hands_seen=60,
    )
    base.update(over)
    return VillainStats(**base)


def reg_stats(**over) -> VillainStats:
    base = dict(
        vpip=0.26,
        pfr=0.18,
        af=1.8,
        fold_to_cbet=0.45,
        fold_to_cbet_opps=12,
        wtsd=0.25,
        river_fold_rate=0.42,
        river_action_count=12,
        hands_seen=80,
    )
    base.update(over)
    return VillainStats(**base)


def test_strong_commit_spot_keeps_value_jam_as_top_purpose() -> None:
    board = cards('Ac', '7d', '2s')
    ctx = DecisionCtx(
        street='flop',
        hole_cards=cards('Ah', 'Ad'),
        board=board,
        position='BTN',
        is_ip=True,
        num_opponents=1,
        pot=50.0,
        stack=50.0,
        big_blind=2.0,
        spr=1.0,
        facing_bet=False,
        hero_bucket='nuts',
        equity_mc=0.95,
        equity_range=0.95,
        is_pfr=True,
        board_sig=v3_board.analyze(board),
        villain_stats=reg_stats(),
    )

    out = V3Engine().decide(ctx)
    purpose, prob = top_candidate(out)

    assert purpose == 'value_jam'
    assert prob >= 0.60
    assert candidate_prob(out, 'default_check') == 0.0
    assert out.arbitration_mode == 'deterministic'
    assert 'low_spr' in out.leverage_flags


def test_semi_bluff_is_not_stolen_by_default_check() -> None:
    board = cards('Jh', 'Th', '4c')
    ctx = DecisionCtx(
        street='flop',
        hole_cards=cards('Qh', '9c'),
        board=board,
        position='CO',
        is_ip=True,
        num_opponents=4,
        pot=100.0,
        stack=800.0,
        big_blind=2.0,
        spr=8.0,
        facing_bet=False,
        hero_bucket='draw',
        equity_mc=0.35,
        equity_range=0.35,
        is_pfr=False,
        board_sig=v3_board.analyze(board),
        villain_stats=reg_stats(fold_to_cbet=0.50),
    )

    out = V3Engine().decide(ctx)

    assert candidate_prob(out, 'semi_bluff') >= 0.95
    assert candidate_prob(out, 'default_check') <= 0.05


def test_obvious_plus_ev_call_cannot_collapse_to_fold() -> None:
    board = cards('As', 'Kd', '2c')
    ctx = DecisionCtx(
        street='flop',
        hole_cards=cards('Ah', 'Qs'),
        board=board,
        position='BTN',
        is_ip=True,
        num_opponents=1,
        pot=100.0,
        to_call=35.0,
        stack=500.0,
        big_blind=2.0,
        spr=5.0,
        pot_odds=35.0 / 135.0,
        facing_bet=True,
        hero_bucket='medium',
        equity_mc=0.55,
        equity_range=0.42,
        equity_uncertainty=0.03,
        board_sig=v3_board.analyze(board),
        villain_stats=sticky_passive_stats(),
    )

    for _ in range(50):
        out = V3Engine().decide(ctx)
        assert out.action != 'fold', (
            f"+EV call regressed to fold; purpose={out.purpose} candidates={out.candidates}"
        )


def test_fold_override_does_not_rescue_obvious_fold_only_air() -> None:
    board = cards('7s', '5d', '2c')
    ctx = DecisionCtx(
        street='flop',
        hole_cards=cards('Ac', 'Qd'),
        board=board,
        position='SB',
        is_ip=False,
        num_opponents=1,
        pot=90.0,
        to_call=30.0,
        stack=500.0,
        big_blind=2.0,
        spr=5.5,
        pot_odds=30.0 / 120.0,
        facing_bet=True,
        hero_bucket='air',
        equity_mc=0.53,
        equity_range=0.09,
        equity_uncertainty=0.05,
        board_sig=v3_board.analyze(board),
        villain_stats=sticky_passive_stats(),
    )

    out = V3Engine().decide(ctx)

    assert out.action == 'fold'
    assert out.purpose == 'fold'


def test_fold_override_rescues_marginal_tracker_compressed_equity() -> None:
    board = cards('7s', '5d', '2c')
    ctx = DecisionCtx(
        street='flop',
        hole_cards=cards('Ac', 'Qd'),
        board=board,
        position='SB',
        is_ip=False,
        num_opponents=1,
        pot=90.0,
        to_call=30.0,
        stack=500.0,
        big_blind=2.0,
        spr=5.5,
        pot_odds=30.0 / 120.0,
        facing_bet=True,
        hero_bucket='medium',
        equity_mc=0.53,
        equity_range=0.23,
        equity_uncertainty=0.03,
        board_sig=v3_board.analyze(board),
        villain_stats=sticky_passive_stats(),
    )

    out = V3Engine().decide(ctx)

    assert out.action == 'call'
    assert out.purpose == 'fold_override_call'


def test_fold_override_rescues_low_spr_commit_spot_when_cheap_edge_is_clear() -> None:
    board = cards('6d', 'Ad', '8s')
    ctx = DecisionCtx(
        street='flop',
        hole_cards=cards('Qs', 'Qc'),
        board=board,
        position='BB',
        is_ip=False,
        num_opponents=2,
        pot=1052499.0,
        to_call=373499.0,
        stack=663525.0,
        big_blind=10000.0,
        spr=0.4,
        pot_odds=373499.0 / (1052499.0 + 373499.0),
        facing_bet=True,
        hero_bucket='medium',
        equity_mc=0.55,
        equity_range=0.38,
        equity_uncertainty=0.05,
        board_sig=v3_board.analyze(board),
        villain_bucket_dist={
            'medium': 0.37, 'air': 0.30, 'draw': 0.16,
            'strong': 0.12, 'nuts': 0.05,
        },
        villain_stats=sticky_passive_stats(),
        n_sticky=1,
    )

    out = V3Engine().decide(ctx)

    assert out.action == 'call'
    assert out.purpose == 'fold_override_call'
    assert 'cheap_commit_range_call' in out.reason


def test_fold_override_rescues_committed_low_spr_when_range_edge_is_clear() -> None:
    board = cards('Js', 'Jd', '4h')
    ctx = DecisionCtx(
        street='flop',
        hole_cards=cards('Ac', 'Kc'),
        board=board,
        position='CO',
        is_ip=True,
        num_opponents=1,
        pot=200.0,
        to_call=70.0,
        stack=180.0,
        big_blind=10.0,
        spr=0.4,
        pot_odds=70.0 / 270.0,
        facing_bet=True,
        hero_bucket='medium',
        equity_mc=0.63,
        equity_range=0.42,
        equity_uncertainty=0.20,
        board_sig=v3_board.analyze(board),
        villain_bucket_dist={
            'air': 0.46, 'nuts': 0.32, 'strong': 0.20, 'medium': 0.02,
        },
        villain_stats=sticky_passive_stats(af=0.3, fold_to_cbet=0.29, wtsd=0.35),
        n_sticky=1,
    )

    out = V3Engine().decide(ctx)

    assert out.action == 'call'
    assert out.purpose == 'fold_override_call'
    assert candidate_prob(out, 'fold') > candidate_prob(out, 'bluff_catch_call')
    assert 'commit_range_call' in out.reason


def test_fold_override_rescues_cheap_committed_low_spr_call() -> None:
    board = cards('Ad', 'Kh', '7s')
    ctx = DecisionCtx(
        street='flop',
        hole_cards=cards('Ac', 'Qs'),
        board=board,
        position='BTN',
        is_ip=True,
        num_opponents=1,
        pot=375_000.0,
        to_call=12_000.0,
        stack=30_000.0,
        big_blind=10_000.0,
        spr=0.08,
        pot_odds=12_000.0 / 387_000.0,
        facing_bet=True,
        hero_bucket='medium',
        equity_mc=0.315,
        equity_range=0.125,
        equity_uncertainty=0.0,
        board_sig=v3_board.analyze(board),
        villain_bucket_dist={
            'medium': 0.31, 'air': 0.27, 'draw': 0.20,
            'nuts': 0.09, 'strong': 0.11,
        },
        villain_stats=sticky_passive_stats(af=0.8),
        n_sticky=1,
    )

    out = V3Engine().decide(ctx)

    assert out.action == 'call'
    assert out.purpose == 'fold_override_call'
    assert 'cheap_commit_range_call' in out.reason


def test_fold_override_rescues_cheap_low_spr_river_call_with_range_edge() -> None:
    board = cards('2c', 'Qh', '9c', '5c', '4s')
    ctx = DecisionCtx(
        street='river',
        hole_cards=cards('Ah', 'Qs'),
        board=board,
        position='UTG+1',
        is_ip=True,
        num_opponents=1,
        pot=855_000.0,
        to_call=150_000.0,
        stack=1_237_342.0,
        big_blind=10_000.0,
        spr=0.2,
        pot_odds=150_000.0 / (855_000.0 + 150_000.0),
        facing_bet=True,
        hero_bucket='medium',
        equity_mc=0.83,
        equity_range=0.24,
        equity_uncertainty=0.08,
        board_sig=v3_board.analyze(board),
        villain_bucket_dist={
            'nuts': 0.79, 'strong': 0.10, 'medium': 0.11,
            'draw': 0.0, 'weak_draw': 0.0, 'air': 0.0,
        },
        villain_stats=sticky_passive_stats(af=1.0),
        n_sticky=1,
        seed=39,
    )

    out = V3Engine().decide(ctx)

    assert out.action == 'call'
    assert out.purpose == 'fold_override_call'
    assert 'cheap_range_call' in out.reason


def test_fold_override_does_not_rescue_fold_dominant_call_candidate() -> None:
    board = cards('Qh', '8s', '3d')
    ctx = DecisionCtx(
        street='flop',
        hole_cards=cards('Ks', '8c'),
        board=board,
        position='SB',
        is_ip=False,
        num_opponents=1,
        pot=100.0,
        to_call=33.0,
        stack=500.0,
        big_blind=2.0,
        spr=4.0,
        pot_odds=33.0 / 133.0,
        facing_bet=True,
        hero_bucket='medium',
        equity_mc=0.55,
        equity_range=0.30,
        equity_uncertainty=0.06,
        board_sig=v3_board.analyze(board),
        villain_bucket_dist={
            'medium': 0.34, 'air': 0.25, 'draw': 0.17,
            'strong': 0.18, 'nuts': 0.06,
        },
        villain_stats=sticky_passive_stats(),
        n_sticky=1,
    )

    out = V3Engine().decide(ctx)

    assert out.action == 'fold'
    assert out.purpose == 'fold'
    assert 'fold_prob' in out.reason


def test_hu_pfr_default_stab_survives_when_range_cbet_is_soft_penalized() -> None:
    sig = BoardSignals(
        wetness=0.50,
        high_card_rank=10,
        flush_possible=True,
        connectedness=0.70,
    )
    ctx = DecisionCtx(
        street='flop',
        hole_cards=cards('Kc', 'Qd'),
        board=cards('Ts', '8s', '4c'),
        position='BTN',
        is_ip=True,
        num_opponents=1,
        pot=100.0,
        stack=900.0,
        big_blind=2.0,
        spr=9.0,
        facing_bet=False,
        hero_bucket='weak_draw',
        equity_mc=0.32,
        equity_range=0.32,
        is_pfr=True,
        board_sig=sig,
        villain_stats=reg_stats(),
    )

    out = V3Engine().decide(ctx)

    assert candidate_prob(out, 'default_stab') >= 0.45
    assert candidate_prob(out, 'default_stab') >= candidate_prob(out, 'default_check') * 5
