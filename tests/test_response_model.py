"""The fitted opponent response model and how the solver path reads the solver's answers.

The river tests run on a real solver output (tests/fixtures/river_solve_Kd5d4hJd2c.json:
pot 30bb, stacks 60bb, 9% rake), because two things here depend on how the solver reports
values and cannot be checked on hand-made numbers: the value after each answer still counts
the chips hero adds, and hero's share when called follows from the opponent's hands.
"""

import json
import math
import statistics
from pathlib import Path

import pytest

from pokerfate.decision import realtime_cfr as rc
from pokerfate.decision import response_model as rm
from pokerfate.strategy.range_v2.fitted_likelihood import likelihood_features

FIXTURE = Path(__file__).parent / "fixtures" / "river_solve_Kd5d4hJd2c.json"


def _model_file(tmp_path, monkeypatch, models):
    path = tmp_path / "response_model.json"
    path.write_text(json.dumps({"version": 1, "models": models}), encoding="utf-8")
    monkeypatch.setenv("PF_RESPONSE_MODEL_PATH", str(path))
    return path


def _answers(fold, call, raise_):
    return {"call": {"intercept": math.log(call / fold), "weights": {}},
            "raise": {"intercept": math.log(raise_ / fold), "weights": {}}}


# ── features ─────────────────────────────────────────────────────────────────────────────

def test_bet_size_is_the_bet_over_the_pot_it_was_made_into():
    assert rm.bet_size(to_call=5.0, pot_with_bet=15.0) == pytest.approx(0.5)        # 5 into 10
    # a raise from 5 to 20 into a pot of 10: 15 more on top of a call, pot after the call 20
    assert rm.bet_size(to_call=15.0, pot_with_bet=35.0) == pytest.approx(0.75)
    assert rm.bet_size(to_call=0.0, pot_with_bet=10.0) == 0.0


def _features(**over):
    args = dict(kind=rm.FACING_BET, street="river", size=0.6, facing_raise=False, in_position=False,
                own_actions=[], opponent_actions=[], bucket_dist={"medium": 0.5, "air": 0.5},
                hands_seen=200, vpip=0.55, aggression_factor=0.75)
    args.update(over)
    return rm.response_features(**args)


def test_features_describe_the_size_in_three_steps():
    assert [_features(size=0.3)[k] for k in ("size_lo", "size_mid", "size_hi")] == pytest.approx([0.3, 0.0, 0.0])
    assert [_features(size=0.8)[k] for k in ("size_lo", "size_mid", "size_hi")] == pytest.approx([0.5, 0.3, 0.0])
    assert [_features(size=1.6)[k] for k in ("size_lo", "size_mid", "size_hi")] == pytest.approx([0.5, 0.5, 0.6])
    assert _features(size=9.0)["size_hi"] == pytest.approx(2.0)                      # capped at three pots


def test_features_read_both_players_lines():
    f = _features(own_actions=[("flop", "call"), ("turn", "call"), ("river", "check")],
                  opponent_actions=[("flop", "bet"), ("turn", "bet")])
    assert (f["prev_call"], f["prev_bet"], f["called_twice"], f["checked_this_street"], f["opp_bet_prev"]) == (1, 0, 1, 1, 1)
    f = _features(street="turn", own_actions=[("flop", "bet")], opponent_actions=[("flop", "call"), ("turn", "check")])
    assert (f["prev_bet"], f["prev_call"], f["called_twice"], f["checked_this_street"], f["opp_bet_prev"]) == (1, 0, 0, 0, 0)
    # the flop does not count as "the street before" on the river
    f = _features(own_actions=[("flop", "bet"), ("turn", "check")], opponent_actions=[("flop", "call"), ("turn", "check")])
    assert (f["prev_bet"], f["prev_call"]) == (0, 0)


def test_player_features_are_the_range_trackers_own():
    tracker = likelihood_features(action="call", street="river", bet_ratio=0.4, players_in_pot=2, in_position=True,
                                  hands_seen=45, vpip=0.31, aggression_factor=2.2, history=[])
    f = _features(hands_seen=45, vpip=0.31, aggression_factor=2.2)
    assert {k: f[k] for k in ("known", "tight", "aggressive")} == {k: tracker[k] for k in ("known", "tight", "aggressive")}
    # recorded values (the fit) are taken as they are
    f = _features(player={"known": 0.9, "tight": -1.2, "aggressive": 0.4}, hands_seen=0)
    assert (f["known"], f["tight"], f["aggressive"]) == (0.9, -1.2, 0.4)


def test_range_features_are_shares_with_draws_pooled():
    f = _features(bucket_dist={"nuts": 1, "strong": 2, "medium": 3, "draw": 1, "weak_draw": 1, "air": 2})
    assert (f["nuts"], f["strong"], f["medium"], f["draw"]) == pytest.approx((0.1, 0.2, 0.3, 0.2))
    assert set(_features(kind=rm.CHECKED_TO)) == set(rm.FEATURES[rm.CHECKED_TO])


# ── prediction ───────────────────────────────────────────────────────────────────────────

def test_predict_is_a_softmax_over_the_answers(tmp_path, monkeypatch):
    spec = {"call": {"intercept": 0.2, "weights": {"size_lo": -2.0, "strong": 1.5}},
            "raise": {"intercept": -1.0, "weights": {"nuts": 3.0}}}
    _model_file(tmp_path, monkeypatch, {"facing_bet": {"river": spec}})
    f = _features(size=0.4, bucket_dist={"nuts": 0.1, "strong": 0.3, "medium": 0.3, "air": 0.3})
    scores = [0.0, 0.2 - 2.0 * 0.4 + 1.5 * 0.3, -1.0 + 3.0 * 0.1]
    total = sum(math.exp(s) for s in scores)
    assert rm.predict(rm.FACING_BET, "river", f) == pytest.approx(
        {"fold": 1 / total, "call": math.exp(scores[1]) / total, "raise": math.exp(scores[2]) / total})
    assert rm.predict(rm.FACING_BET, "turn", f) is None            # no model for the street
    assert rm.predict(rm.CHECKED_TO, "river", f) is None
    monkeypatch.setenv("PF_RESPONSE_MODEL_PATH", "off")
    assert rm.predict(rm.FACING_BET, "river", f) is None


def test_the_shipped_model_covers_what_the_solver_decides():
    for kind in (rm.FACING_BET, rm.CHECKED_TO):
        for street in rm.STREETS:
            assert rm.covers(kind, street)
            spec = rm.load_model()["models"][kind][street]
            assert set(spec) == set(rm.CLASSES[kind][1:])
            for part in spec.values():
                assert set(part["weights"]) == set(rm.FEATURES[kind])
    # a bigger bet is folded to more often, on both streets
    for street in rm.STREETS:
        folds = [rm.predict(rm.FACING_BET, street, _features(street=street, size=s))["fold"] for s in (0.3, 0.6, 1.0, 1.5)]
        assert folds == sorted(folds)


# ── who calls ────────────────────────────────────────────────────────────────────────────

def test_fewer_calls_take_the_weakest_callers_out():
    # (strength, reach, P(fold), P(call)); hero (strength 5) beats the two weak hands
    hands = [(1, 0.25, 0.0, 1.0), (3, 0.25, 0.0, 1.0), (7, 0.25, 0.0, 1.0), (9, 0.25, 0.0, 1.0)]
    assert rm.shifted_call_win_share(hands, 5, 0.0) == pytest.approx((0.5, 0.5))
    assert rm.shifted_call_win_share(hands, 5, -0.25) == pytest.approx((0.5, 1 / 3))      # the weakest goes
    assert rm.shifted_call_win_share(hands, 5, -0.375) == pytest.approx((0.5, 0.125 / 0.625))
    assert rm.shifted_call_win_share(hands, 5, -1.0) is None                              # nobody left


def test_more_calls_come_from_the_strongest_folders():
    hands = [(1, 0.25, 1.0, 0.0), (3, 0.25, 1.0, 0.0), (7, 0.25, 0.0, 1.0), (9, 0.25, 0.0, 1.0)]
    assert rm.shifted_call_win_share(hands, 5, 0.25) == pytest.approx((0.0, 1 / 3))       # the 3 calls now
    assert rm.shifted_call_win_share(hands, 3, 0.25) == pytest.approx((0.0, 0.5 / 3))     # a tie counts half
    assert rm.shifted_call_win_share([(1, 0.5, 1.0, 0.0), (9, 0.5, 1.0, 0.0)], 5, 0.1) is None   # nobody calls at equilibrium


# ── the solver's own numbers ─────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def river():
    fx = json.loads(FIXTURE.read_text(encoding="utf-8"))
    nodes = {n["path"]: n for n in fx["nodes"]}
    result = {"node": nodes["r"], "nodes": fx["nodes"], "oop_hands": fx["oop_hands"], "ip_hands": fx["ip_hands"]}
    board = [fx["board"][i:i + 2] for i in range(0, 10, 2)]
    context = {"street": "river", "board": board, "current_pot_bb": 30.0, "current_to_call_bb": 0.0,
               "hero_current_bet_bb": 0.0, "effective_stack_bb": 60.0, "hero_actions": [], "villain_actions": [],
               "range_v2": {"bucket_dist": {"medium": 0.5, "air": 0.5}}}
    return fx, nodes, result, context


def _details(river, label, min_freq=0.002):
    fx, nodes, result, context = river
    cache: dict = {}
    for idx, hand in enumerate(fx["oop_hands"]):
        if rc._node_hand_values(nodes["r"], "strategy", idx).get(label, 0.0) < min_freq:
            continue
        detail = rc._response_adjusted_ev_detail_from_result(
            result, nodes["r:" + label], hero_combo=hand, hero_side="oop", profile=None, street="river",
            hero_action_label=label, line_context=dict(context, hero_combo=hand), cache=cache)
        yield idx, hand, rc._node_hand_values(nodes["r"], "evs", idx)[label], detail


def test_the_solver_counts_the_bet_as_heros_in_the_values_after_an_answer(river, monkeypatch):
    fx, nodes, _result, _context = river
    monkeypatch.setenv("PF_RESPONSE_MODEL_PATH", "off")
    for label, bet in (("Bet(198)", 19.8), ("AllIn(600)", 60.0)):
        child = nodes["r:" + label]
        eq = rc._node_weighted_strategy(child)
        gaps = []
        for idx in range(0, len(fx["oop_hands"]), 7):
            if rc._node_hand_values(nodes["r"], "strategy", idx).get(label, 0.0) < 0.02:
                continue
            after = rc._node_hand_values(child, "opponent_evs", idx, num_hands_key="opponent_num_hands")
            own = rc._node_hand_values(nodes["r"], "evs", idx)[label]
            gaps.append(sum(eq[k] * after[k] for k in after) - own)
        # hero's own cards shift the opponent's answers a little; the range-wide frequencies used
        # here leave half a big blind of slack on this board
        assert statistics.median(gaps) == pytest.approx(bet, abs=0.8)
    # ... so with the bet taken off they reproduce the action's own value, and are used
    used = [(gto, detail) for _i, _h, gto, detail in _details(river, "Bet(198)")]
    assert len(used) > 600 and all(detail is not None for _gto, detail in used)
    assert all(detail["ev"] == pytest.approx(gto, abs=1e-6) for gto, detail in used)   # no model: the solver's value


def test_share_when_called_rebuilt_from_the_opponents_hands_matches_the_solver(river, tmp_path, monkeypatch):
    _model_file(tmp_path, monkeypatch, {"facing_bet": {"river": _answers(0.6, 0.3, 0.1)}})
    for label in ("Bet(198)", "AllIn(600)"):
        records = [detail["summary"]["call_range"] for _i, _h, _g, detail in _details(river, label) if detail is not None]
        assert len(records) > 400
        assert not any(r.get("skipped") for r in records)
        assert max(abs(r["solver_share"] - r["share_eq"]) for r in records) < 0.03
        assert statistics.median(abs(r["solver_share"] - r["share_eq"]) for r in records) < 0.002


def test_an_opponent_who_folds_more_pays_bluffs_and_shortchanges_thin_value(river, tmp_path, monkeypatch):
    fx, _nodes, _result, _context = river
    # equilibrium answers to the 66% pot bet: fold 42%, call 40%, raise 18%
    _model_file(tmp_path, monkeypatch, {"facing_bet": {"river": _answers(0.6, 0.3, 0.1)}})
    by_hand = {hand: (gto, detail) for _i, hand, gto, detail in _details(river, "Bet(198)")}

    gto, detail = by_hand["7c3c"]                                 # air
    assert gto < 0 and detail["ev"] > gto + 8.0
    assert detail["summary"]["response"]["fitted"]["fold"] == pytest.approx(0.6, abs=1e-3)

    gto, detail = by_hand["Kh2s"]                                 # top pair, no kicker
    shift = detail["summary"]["call_range"]
    assert 0.85 < shift["share_eq"] < 0.95 and shift["share_new"] < shift["share_eq"] - 0.02
    assert shift["delta_bb"] < -1.0
    # without resizing the calling range the same answers would be worth more
    assert detail["ev"] < gto + (0.6 - 0.42) * 30.0

    gto, detail = by_hand["QdTd"]                                 # the nuts: fewer calls, less value
    assert detail["summary"]["call_range"]["share_new"] == pytest.approx(1.0)
    assert detail["ev"] < gto - 3.0


def test_an_opponent_who_calls_more_pays_value_and_punishes_bluffs(river, tmp_path, monkeypatch):
    _model_file(tmp_path, monkeypatch, {"facing_bet": {"river": _answers(0.25, 0.6, 0.15)}})
    by_hand = {hand: (gto, detail) for _i, hand, gto, detail in _details(river, "Bet(198)")}
    gto, detail = by_hand["7c3c"]
    assert detail["ev"] < gto - 5.0
    gto, detail = by_hand["Kh2s"]
    shift = detail["summary"]["call_range"]
    assert shift["share_new"] > shift["share_eq"] + 0.02 and detail["ev"] > gto + 3.0


def test_answers_keep_the_solvers_split_inside_a_class(river, tmp_path, monkeypatch):
    _fx, nodes, _result, context = river
    _model_file(tmp_path, monkeypatch, {"facing_bet": {"river": _answers(0.5, 0.3, 0.2)}})
    eq = rc._node_weighted_strategy(nodes["r:Bet(198)"])
    adj, info = rc._expected_response_probs(eq, street="river", hero_side="oop", hero_action_label="Bet(198)",
                                            profile=None, line_context=context)
    assert info["model"] is True and info["size"] == pytest.approx(0.66)
    assert adj["Fold"] == pytest.approx(0.5) and adj["Call"] == pytest.approx(0.3)
    assert adj["Raise(396)"] + adj["AllIn(600)"] == pytest.approx(0.2)
    assert adj["Raise(396)"] / adj["AllIn(600)"] == pytest.approx(eq["Raise(396)"] / eq["AllIn(600)"])
    # behind an all-in there is no raise left: the hands that would have raised, call
    eq = rc._node_weighted_strategy(nodes["r:AllIn(600)"])
    adj, info = rc._expected_response_probs(eq, street="river", hero_side="oop", hero_action_label="AllIn(600)",
                                            profile=None, line_context=context)
    assert adj == pytest.approx({"Fold": 0.5, "Call": 0.5})
    assert info["fitted"] == {"fold": 0.5, "call": 0.5}


def test_a_check_is_answered_by_the_checked_to_model(river, tmp_path, monkeypatch):
    _fx, nodes, result, context = river
    _model_file(tmp_path, monkeypatch, {"checked_to": {"river": {"bet": {"intercept": math.log(0.2 / 0.8), "weights": {}}}}})
    eq = rc._node_weighted_strategy(nodes["r:Check"])
    adj, info = rc._expected_response_probs(eq, street="river", hero_side="oop", hero_action_label="Check",
                                            profile=None, line_context=context)
    assert info["kind"] == rm.CHECKED_TO and info["model"] is True and "size" not in info
    assert adj["Check"] == pytest.approx(0.8)
    assert adj["Bet(198)"] + adj["AllIn(600)"] == pytest.approx(0.2)
    # the value of checking moves with it, and nothing is taken off for a bet hero did not make
    detail = rc._response_adjusted_ev_detail_from_result(
        result, nodes["r:Check"], hero_combo="8h2s", hero_side="oop", profile=None, street="river",
        hero_action_label="Check", line_context=dict(context, hero_combo="8h2s"))
    after = detail["response_evs"]
    gto = rc._node_hand_values(nodes["r"], "evs", result["oop_hands"].index("8h2s"))["Check"]
    expected = gto + sum((adj[k] - eq[k]) * after[k] for k in after)
    assert detail["ev"] == pytest.approx(expected, abs=1e-6)
    assert "call_range" not in detail["summary"]


def test_line_context_carries_both_players_postflop_actions():
    from pokerfate.core.card import Card
    from pokerfate.core.game_state import Action, ActionType, GameState, Player, Street

    hero = Player(player_id=1, name="hero", stack=9000.0)
    villain = Player(player_id=2, name="villain", stack=9000.0)
    hero.hole_cards = [Card.from_str("As"), Card.from_str("Kd")]
    gs = GameState(players=[hero, villain], small_blind=50, big_blind=100)
    gs.street = Street.RIVER
    gs.board = [Card.from_str(c) for c in ("Kh", "7d", "2c", "9s", "3c")]
    gs.pot = 2000.0
    gs.action_history = [
        (2, Action(ActionType.CALL, 100.0), "preflop"),
        (1, Action(ActionType.RAISE, 300.0), "flop"),
        (2, Action(ActionType.CALL, 300.0), "flop"),
        (1, Action(ActionType.CHECK, 0.0), "turn"),
        (2, Action(ActionType.RAISE, 500.0), "turn"),
        (1, Action(ActionType.CALL, 500.0), "turn"),
        (2, Action(ActionType.CHECK, 0.0), "river"),
    ]
    line = rc._build_line_context(gs, hero_player_id=1, villain_player_id=2)
    assert line["hero_actions"] == [("flop", "bet"), ("turn", "check"), ("turn", "call")]
    assert line["villain_actions"] == [("flop", "call"), ("turn", "bet"), ("river", "check")]


def test_the_decision_log_gets_both_sets_of_answers(river, tmp_path, monkeypatch):
    from pokerfate.api import PokerFateAPI

    fx, nodes, result, context = river
    _model_file(tmp_path, monkeypatch, {"facing_bet": {"river": _answers(0.6, 0.3, 0.1)}})
    idx = fx["oop_hands"].index("Kh2s")
    strategy = {a: nodes["r"]["strategy"][i * nodes["r"]["num_hands"] + idx] for i, a in enumerate(nodes["r"]["actions"])}
    selection = rc._select_exploit_action(
        result, hero_combo="Kh2s", hero_side="oop", street="river", gto_strategy=strategy, profile=None,
        adjustments={}, max_confidence=0.45, enabled=True, line_context=dict(context, hero_combo="Kh2s"),
    )
    log = PokerFateAPI._compact_response_summaries(selection["exploit"]["response_summaries"])
    bet = log["Bet(198)"]
    assert bet["eq"] == {"fold": pytest.approx(0.42, abs=0.01), "call": pytest.approx(0.396, abs=0.01), "raise": pytest.approx(0.184, abs=0.01)}
    assert bet["fit"] == {"fold": pytest.approx(0.6, abs=1e-3), "call": pytest.approx(0.3, abs=1e-3), "raise": pytest.approx(0.1, abs=1e-3)}
    assert bet["size"] == pytest.approx(0.66)
    assert bet["call_range"]["share_new"] < bet["call_range"]["share_eq"]
    # no model for a check in this file: the equilibrium answers are still logged, with the reason
    assert log["Check"]["why"] == "no_model" and set(log["Check"]["eq"]) == {"check", "bet"}
    assert PokerFateAPI._compact_response_summaries(None) == {}
