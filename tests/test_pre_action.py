"""Reads from pre-selected actions (pokerfate/strategy/pre_action.py) and where they enter."""
import json
import math

import pytest

from pf_intercept.bot.bridge import BotBridge
from pokerfate.core.card import Card
from pokerfate.decision import response_model as rm
from pokerfate.strategy import pre_action as pa
from pokerfate.strategy.range_v2.action_model import ActionContext, ActionModel, PlayerProfile
from pokerfate.strategy.range_v2.bayesian_range_tracker import BayesianRangeTracker
from pokerfate.strategy.v3 import counterfactual
from pokerfate.strategy.v3.context import BoardSignals, DecisionCtx
from pokerfate.strategy.v3.purposes_reads import ReadStab

FIT = {
    "range": {"check": {"flop": {"nuts": 0.5, "strong": 0.5, "medium": 0.5, "draw": 1.0, "weak_draw": 1.0, "air": 2.0}}},
    "fold_shift": {"check_now": 1.0, "check_prev": 0.8},
    "raise_factor": {"check_now": 0.5},
    "fold_rate": {"flop": {"1": {"small": 0.3, "mid": 0.4, "big": 0.5},
                           "2": {"small": 0.4, "mid": 0.5, "big": 0.6}}},
    "response": {"facing_bet": {"river": {"check_prev": {"call": -1.0, "raise": -2.0}}}},
}


@pytest.fixture
def fit(tmp_path, monkeypatch):
    path = tmp_path / "pre_action_fit.json"
    path.write_text(json.dumps(FIT), encoding="utf-8")
    monkeypatch.setenv("PF_PRE_ACTION", str(path))
    return path


# ── the read ─────────────────────────────────────────────────────────────────────────────

CHECK_FLOP = pa.Read("check", "flop")
CALL_FLOP = pa.Read("call", "flop")
OPTION = pa.Read("option", "preflop")


@pytest.mark.parametrize("before, street, action, flag, after", [
    (None, "flop", "check", pa.EXECUTED, CHECK_FLOP),          # a pre-selected check starts a read
    (None, "flop", "call", pa.EXECUTED, CALL_FLOP),
    (None, "preflop", "check", pa.EXECUTED, OPTION),           # the big blind's option
    (None, "preflop", "call", pa.EXECUTED, None),              # a pre-selected limp says nothing
    (None, "flop", "check", pa.NONE, None),
    (None, "flop", "call", pa.RESET, None),
    (CHECK_FLOP, "turn", "check", pa.NONE, CHECK_FLOP),        # it lasts while he stays passive for free
    (CHECK_FLOP, "turn", "check", pa.EXECUTED, pa.Read("check", "turn")),
    (CHECK_FLOP, "flop", "call", pa.NONE, None),               # chips by choice end it
    (CHECK_FLOP, "turn", "bet", pa.NONE, None),
    (CHECK_FLOP, "turn", "raise_over", pa.NONE, None),
    (CHECK_FLOP, "turn", "fold", pa.NONE, None),
    (CALL_FLOP, "turn", "call", pa.NONE, CALL_FLOP),           # a capped caller who calls again is still capped
    (CALL_FLOP, "turn", "raise", pa.NONE, None),
    (OPTION, "flop", "call", pa.NONE, None),
])
def test_update_read(before, street, action, flag, after):
    assert pa.update_read(before, street=street, action=action, pre_action=flag) == after


@pytest.mark.parametrize("read, street, key", [
    (CHECK_FLOP, "flop", pa.CHECK_NOW),
    (CHECK_FLOP, "turn", pa.CHECK_PREV),
    (CHECK_FLOP, "river", pa.CHECK_PREV),
    (CALL_FLOP, "flop", pa.CALL_NOW),
    (CALL_FLOP, "river", pa.CALL_PREV),
    (OPTION, "flop", pa.OPTION_PREV),
    (OPTION, "turn", None),                                    # the option read is for the flop only
    (pa.Read("check", "turn"), "flop", None),
    (None, "flop", None),
])
def test_read_key(read, street, key):
    assert pa.read_key(read, street) == key


def test_shifted_moves_a_probability_in_log_odds():
    assert pa.shifted(0.5, 0.0) == pytest.approx(0.5)
    assert pa.shifted(0.5, math.log(3.0)) == pytest.approx(0.75)
    assert pa.shifted(0.25, -math.log(3.0)) == pytest.approx(0.1)


def test_field_fold_prob_is_the_product_of_single_rates(fit, monkeypatch):
    assert pa.field_fold_prob("flop", [None], 0.3) == pytest.approx(0.3)
    assert pa.field_fold_prob("flop", [None, None], 0.9) == pytest.approx(0.6 * 0.6)
    # the player with the read folds at the mid-size rate moved by his shift, whatever the size
    with_read = pa.shifted(0.5, 1.0)
    assert pa.field_fold_prob("flop", [pa.CHECK_NOW, None], 0.3) == pytest.approx(with_read * 0.4)
    assert pa.field_fold_prob("flop", [pa.CHECK_NOW, None], 0.9) == pytest.approx(with_read * 0.6)
    assert pa.field_fold_prob("turn", [None], 0.5) is None      # nothing measured for the street
    monkeypatch.setenv("PF_PRE_ACTION", "off")
    assert pa.field_fold_prob("flop", [None], 0.3) is None
    assert not pa.enabled()


# ── the wire ─────────────────────────────────────────────────────────────────────────────

class _FakeAPI:
    def __init__(self):
        self.events = []

    def notify_action(self, event):
        self.events.append(event)


def test_bridge_gives_each_action_the_flag_of_its_notice():
    b = BotBridge()
    b._api = _FakeAPI()
    b._stage = 2
    b._my_seat = 0
    b._on_action_notify({"seatid": 1, "pre_action_result": 2})
    b._on_action_brc({"seatid": 1, "action_type": 2, "hand_chips": 100})
    b._on_action_notify({"seatid": 2})
    b._on_action_brc({"seatid": 2, "action_type": 2, "hand_chips": 100})
    b._on_action_notify({"seatid": 3, "pre_action_result": 2})
    b._on_action_brc({"seatid": 3, "action_type": 13, "hand_chips": 100})     # the system checked for him
    b.note_pre_action({"seatid": 4, "pre_action_result": 2})                  # a notice the session did not hand over
    b._on_action_brc({"seatid": 4, "action_type": 1, "hand_chips": 100})
    b.note_pre_action({"seatid": 0, "pre_action_result": 2})                  # hero's own seat is not read
    assert [e.pre_action for e in b._api.events] == [2, 0, 0, 2]
    assert b._pre_action_flags == {}


# ── the range ────────────────────────────────────────────────────────────────────────────

def _cards(*names):
    return [Card.from_str(c) for c in names]


def _tracker_after_check(flag):
    tracker = BayesianRangeTracker(ActionModel())
    tracker.set_known_cards(_cards("Ah", "Kc"))
    profile = PlayerProfile(hands_seen=5, vpip=0.4, pfr=0.1)
    tracker.reset_hand(1, "BB", profile)
    board = _cards("Qd", "7h", "2c")
    tracker.reweight_for_board(board)
    ctx = ActionContext(position="BB", board=[], street="flop", facing_action="check", pre_action=flag)
    tracker.observe_action(1, "check", "flop", ctx, profile, board)
    return tracker, board


def test_a_pre_selected_check_moves_the_range_and_leaves_the_fitted_state_alone(fit):
    plain, board = _tracker_after_check(pa.NONE)
    read, _ = _tracker_after_check(pa.EXECUTED)
    before = plain.get_bucket_distribution(1, board)
    after = read.get_bucket_distribution(1, board)
    assert read.pre_action_read(1) == CHECK_FLOP and plain.pre_action_read(1) is None
    assert read.get_bucket_distribution(1, board, with_pre_action=False) == pytest.approx(before)
    # air doubled against the made hands (ratio 2.0 vs 0.5)
    assert after["air"] / after["medium"] == pytest.approx(4.0 * before["air"] / before["medium"], rel=1e-6)
    # a bet afterwards ends the read and with it the evidence
    profile = PlayerProfile(hands_seen=5, vpip=0.4, pfr=0.1)
    for tracker in (plain, read):
        tracker.observe_action(1, "raise", "turn", ActionContext(position="BB", board=[], street="turn",
                               facing_action="check", bet_ratio=0.5), profile, board + _cards("3s"))
    assert read.pre_action_read(1) is None
    assert read.get_bucket_distribution(1, board + _cards("3s")) == pytest.approx(
        plain.get_bucket_distribution(1, board + _cards("3s")))


# ── the solver path's response model ─────────────────────────────────────────────────────

def test_predict_adds_the_offsets_of_a_read(fit, tmp_path, monkeypatch):
    spec = {"call": {"intercept": 0.2, "weights": {}}, "raise": {"intercept": -1.0, "weights": {}}}
    path = tmp_path / "response_model.json"
    path.write_text(json.dumps({"version": 1, "models": {"facing_bet": {"river": spec}}}), encoding="utf-8")
    monkeypatch.setenv("PF_RESPONSE_MODEL_PATH", str(path))
    features = rm.response_features(kind=rm.FACING_BET, street="river", size=0.5, facing_raise=False,
                                    in_position=False, own_actions=[], opponent_actions=[], bucket_dist={"air": 1.0})
    scores = [0.0, 0.2 - 1.0, -1.0 - 2.0]
    total = sum(math.exp(s) for s in scores)
    assert rm.predict(rm.FACING_BET, "river", features, pre_action_key=pa.CHECK_PREV) == pytest.approx(
        {"fold": 1 / total, "call": math.exp(scores[1]) / total, "raise": math.exp(scores[2]) / total})
    assert rm.predict(rm.FACING_BET, "river", features, pre_action_key=pa.CALL_PREV) == pytest.approx(
        rm.predict(rm.FACING_BET, "river", features))


# ── the rule engine ──────────────────────────────────────────────────────────────────────

def _ctx(**over) -> DecisionCtx:
    defaults = dict(street="flop", pot=100.0, stack=1000.0, big_blind=2.0, spr=10.0, num_opponents=2,
                    hero_bucket="air", is_ip=True, equity_range=0.2, equity_mc=0.2,
                    board_sig=BoardSignals(wetness=0.4))
    defaults.update(over)
    return DecisionCtx(**defaults)


def test_fold_estimate_uses_the_field_product_when_somebody_has_a_read(fit):
    ctx = _ctx(opp_reads=(pa.CHECK_NOW, None))
    assert ctx.weak_reads == 1
    rx = counterfactual.reaction_estimate(ctx, 0.5, "bet")
    assert rx.source == "pre_action"
    assert rx.p_fold == pytest.approx(pa.field_fold_prob("flop", [pa.CHECK_NOW, None], 0.5))
    assert counterfactual.reaction_estimate(_ctx(), 0.5, "bet").source != "pre_action"


def test_read_stab_proposes_a_bet_exactly_when_it_is_priced_above_checking(fit):
    purpose = ReadStab()
    for ctx in (_ctx(opp_reads=(pa.CHECK_NOW, pa.CHECK_NOW)), _ctx(opp_reads=(pa.CHECK_NOW, None)),
                _ctx(opp_reads=(pa.CHECK_NOW, None), hero_bucket="draw", equity_range=0.35, equity_mc=0.35)):
        best = purpose.best_size(ctx)
        trigger = purpose.trigger(ctx)
        assert trigger.hit == (best[1] >= 0.05)
        assert purpose.sizer(ctx) == [(best[0], 1.0)]
    assert purpose.trigger(_ctx(opp_reads=(pa.CHECK_NOW, pa.CHECK_NOW))).hit
    assert not purpose.trigger(_ctx()).hit                                           # no read, no purpose
    assert not purpose.trigger(_ctx(opp_reads=(pa.CHECK_NOW, None), facing_bet=True, to_call=30.0)).hit
    # a made hand is the business of the value and protection purposes
    assert not purpose.trigger(_ctx(opp_reads=(pa.CHECK_NOW, pa.CHECK_NOW), hero_bucket="medium")).hit


# ── the live monitor ─────────────────────────────────────────────────────────────────────

def test_live_monitor_counts_answers_to_heros_bets(fit, tmp_path, monkeypatch):
    from analysis import pre_action_live

    monkeypatch.setattr(pre_action_live, "_load_hero_names", lambda: {"hero"})
    players = [{"name": n} for n in ("hero", "a", "b")]
    events = [
        {"event": "hand_start", "hand": 1, "players": players},
        {"event": "board", "hand": 1, "street": "flop", "cards": ["Qd", "7h", "2c"]},
        {"event": "opponent_action", "hand": 1, "player": "a", "action": "check", "street": "flop"},
        {"event": "opponent_action", "hand": 1, "player": "b", "action": "check", "street": "flop", "pre_action": 2},
        {"event": "decision", "hand": 1, "street": "flop", "action": "raise", "amount": 50, "pot": 100,
         "to_call": 0, "final_purpose": "read_stab"},
        {"event": "opponent_action", "hand": 1, "player": "a", "action": "fold", "street": "flop"},
        {"event": "opponent_action", "hand": 1, "player": "b", "action": "fold", "street": "flop"},
        {"event": "hand_result", "hand": 1},
        {"event": "hand_start", "hand": 2, "players": players},
        {"event": "board", "hand": 2, "street": "flop", "cards": ["Qd", "7h", "2c"]},
        {"event": "opponent_action", "hand": 2, "player": "a", "action": "check", "street": "flop", "pre_action": 2},
        {"event": "opponent_action", "hand": 2, "player": "b", "action": "check", "street": "flop"},
        {"event": "decision", "hand": 2, "street": "flop", "action": "raise", "amount": 50, "pot": 100, "to_call": 0},
        {"event": "opponent_action", "hand": 2, "player": "a", "action": "call", "street": "flop"},
        {"event": "opponent_action", "hand": 2, "player": "b", "action": "fold", "street": "flop"},
        {"event": "hand_result", "hand": 2},
    ]
    log = tmp_path / "pokerfate.log"
    log.write_text("\n".join(json.dumps(e) for e in events) + "\n", encoding="utf-8")
    c = pre_action_live.collect([log])
    assert (c["hands"], c["read_spots"], c["read_spots_open"]) == (2, 2, 2)
    assert (c["answers"], c["answers_fold"]) == (2, 1)                 # the players with the read: one folded
    assert (c["read_bets"], c["read_all_fold"]) == (2, 1)
    assert (c["stab_bets"], c["stab_all_fold"]) == (1, 1)
    assert c["read_fitted"] == pytest.approx(2 * pa.field_fold_prob("flop", [pa.CHECK_NOW, None], 0.5))
