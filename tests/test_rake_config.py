"""Rake-aware EV helpers and their use in the strategy layer."""

import pytest

from pokerfate.core import config
from pokerfate.core.config import RAKE_KEEP, RAKE_RATE, rake_keep, required_equity


def test_required_equity_includes_rake():
    # Call 50 into 150 (pot already contains villain bet): raw 25%, raked higher.
    raw = 50.0 / 200.0
    assert required_equity(50.0, 150.0) == pytest.approx(raw / RAKE_KEEP)
    assert required_equity(0.0, 150.0) == 0.0
    assert required_equity(50.0, 0.0) == pytest.approx(min(1.0, 1.0 / RAKE_KEEP))


def test_rake_keep_matches_measured_table_rake():
    assert RAKE_RATE == pytest.approx(0.09)
    assert rake_keep() == pytest.approx(0.91)
    assert rake_keep(500.0) == pytest.approx(0.91)  # uncapped


def test_rake_cap_lowers_effective_rate_when_configured(monkeypatch):
    monkeypatch.setattr(config, "RAKE_CAP_BB", 3.0)
    assert config.rake_keep(100.0) == pytest.approx(0.97)
    assert config.rake_keep(10.0) == pytest.approx(0.91)


def test_realtime_cfr_solver_args_charge_rake():
    from pokerfate.decision import realtime_cfr as rc

    state = rc.RealtimeCFRState(board="KhTd7c4s2h", oop_range="AA,KK", ip_range="QQ,JJ",
                                pot_bb=20.0, effective_stack_bb=80.0, prefix=[])
    args, _expect = rc._build_solver_args(state, 1.0, 100)
    assert args["rake_rate"] == pytest.approx(RAKE_RATE)
    # postflop-solver charges min(rate*pot, cap); cap must not be 0.
    assert args["rake_cap"] >= args["starting_pot"] * RAKE_RATE


# ── Bet-size thresholds must not inherit the rake ───────────────────────────

def test_raw_pot_odds_is_rake_free_size_measure():
    from pokerfate.strategy.v3.context import DecisionCtx

    # Villain bets 60 into 100 → pot 160 contains the bet, hero calls 60.
    ctx = DecisionCtx(pot=160.0, to_call=60.0, pot_odds=required_equity(60.0, 160.0))
    assert ctx.raw_pot_odds == pytest.approx(60.0 / 220.0)
    assert ctx.pot_odds == pytest.approx(ctx.raw_pot_odds / RAKE_KEEP)
    assert DecisionCtx(pot=100.0, to_call=0.0).raw_pot_odds == 0.0


def test_facing_large_bet_uses_bet_size_not_raked_price():
    """A 0.6-pot bet is below the 0.75-pot 'large bet' line; with the raked
    pot_odds (0.273/0.91 = 0.30) it used to be flagged as large."""
    from pokerfate.strategy.postflop import PostflopStrategy

    strat = PostflopStrategy()
    # pot before bet 100, villain bets 60 → pot 160, to_call 60, spr low.
    ctx = strat._build_ctx(
        street='turn', board=[], position='BB', is_ip=False, equity=0.5,
        pot=160.0, to_call=60.0, stack=200.0, effective_stack=200.0,
        facing_bet=True, num_opponents=1, big_blind=2.0, spr=1.25,
        opponent_af=1.5, opponent_fold_rate=0.4, fold_to_cbet=None,
        value_only=False, nut_advantage=0.0, is_delayed_cbet=False,
        opponent_checked_back=False, last_bet_frac=0.0, villain_nuts_pct=0.0,
        hole_cards=None,
    )
    assert ctx.raw_pot_odds == pytest.approx(60.0 / 220.0)
    assert ctx.pot_odds == pytest.approx(60.0 / 220.0 / RAKE_KEEP)
    assert ctx.facing_large_bet is False
    # A genuine 0.75-pot bet still counts as large.
    ctx2 = strat._build_ctx(
        street='turn', board=[], position='BB', is_ip=False, equity=0.5,
        pot=175.0, to_call=75.0, stack=200.0, effective_stack=200.0,
        facing_bet=True, num_opponents=1, big_blind=2.0, spr=1.1,
        opponent_af=1.5, opponent_fold_rate=0.4, fold_to_cbet=None,
        value_only=False, nut_advantage=0.0, is_delayed_cbet=False,
        opponent_checked_back=False, last_bet_frac=0.0, villain_nuts_pct=0.0,
        hole_cards=None,
    )
    assert ctx2.facing_large_bet is True


def test_preflop_pressure_tier_uses_rake_free_price():
    from pokerfate.strategy.preflop import PreflopStrategy

    strat = PreflopStrategy()
    bb = 10.0
    # Hero BB, villain opens 3bb, two callers: pot 1.5 + 3 + 3 + 3 = 10.5bb,
    # hero calls 2bb → raw price 2/12.5 = 0.16 → 'cheap' tier (<= 0.20).
    # (Rake-adjusted price is 0.176, still cheap; make the case tight: 2.3bb
    # call into 9.3bb → raw 0.198 cheap, raked 0.218 would wrongly be 'normal'.)
    kind = strat._pressure_kind(stack=100 * bb, pot=9.3 * bb, to_call=2.3 * bb, open_raise=3.3 * bb, big_blind=bb)
    assert strat._raw_call_price(100 * bb, 9.3 * bb, 2.3 * bb, 3.3 * bb) == pytest.approx(2.3 / 11.6)
    assert kind == 'cheap'
    # The price check itself stays rake-adjusted.
    _call, pot_odds, _commit, _bb = strat._pressure_inputs(100 * bb, 9.3 * bb, 2.3 * bb, 3.3 * bb, bb)
    assert pot_odds == pytest.approx(2.3 / 11.6 / RAKE_KEEP)
