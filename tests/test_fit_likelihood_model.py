"""The fitted postflop likelihood: features, runtime lookup, and the fit recovering a known model."""
import json

import numpy as np
import pytest

from pokerfate.core.card import Card
from pokerfate.strategy.range_v2 import fitted_likelihood as fl
from pokerfate.strategy.range_v2.action_model import ActionContext, ActionModel, PlayerProfile
from scripts import fit_likelihood_model as flm

CATS = flm.CATS


def _features(**over):
    base = dict(action="bet", street="turn", bet_ratio=0.5, players_in_pot=3, in_position=False,
                hands_seen=0, vpip=0.35, aggression_factor=2.0, history=[])
    base.update(over)
    return fl.likelihood_features(**base)


def test_features_are_zero_for_the_unremarkable_spot_and_mark_what_differs():
    assert set(_features()) == set(fl.FEATURES)
    plain = _features(aggression_factor=1.0)
    assert not any(plain.values())                                  # half-pot bet, 3 players, unknown player
    assert _features(bet_ratio=1.2)["size_pot"] == 1.0 and _features(bet_ratio=0.3)["size_small"] == 1.0
    assert _features(action="check", bet_ratio=0.0)["size_none"] == 0.0      # a check has no size at all
    assert _features(action="call", bet_ratio=0.0)["size_none"] == 1.0
    assert _features(players_in_pot=2)["pot_two"] == 1.0 and _features(players_in_pot=5)["pot_four_plus"] == 1.0
    known = _features(hands_seen=90, vpip=0.30)
    assert known["known"] == pytest.approx(0.75) and known["tight"] == pytest.approx(0.75)
    assert _features(hands_seen=90, vpip=0.60)["tight"] == pytest.approx(-0.75)
    line = _features(street="river", history=[("flop", "bet"), ("turn", "bet")])
    assert line["prev_bet"] == 1.0 and line["bet_two_streets"] == 1.0 and line["prev_call"] == 0.0
    assert _features(street="turn", history=[("flop", "call")])["prev_call"] == 1.0
    assert _features(action="raise_over", history=[("turn", "check")])["checked_this_street"] == 1.0


def _rows(n, base, weights, *, action="bet", seed=0, lam=0.08):
    rng = np.random.default_rng(seed)
    rows = []
    for _ in range(n):
        street = ("flop", "turn", "river")[int(rng.integers(3))]
        q = rng.dirichlet(np.ones(6) * 2.0)
        u = rng.dirichlet(np.ones(6) * 4.0)
        if street == "river":
            for v in (q, u):
                v[5] += v[3] + v[4]
                v[3] = v[4] = 0.0
        feats = _features(action=action, street=street, bet_ratio=float(rng.choice([0.3, 0.5, 0.7, 1.2])),
                          players_in_pot=int(rng.integers(2, 6)), hands_seen=float(rng.choice([0, 20, 200])),
                          vpip=float(rng.uniform(0.2, 0.7)), aggression_factor=1.0)
        score = base[("flop", "turn", "river").index(street)] + np.array(fl.feature_vector(feats)) @ weights
        live = q > 0
        p = np.where(live, q * np.exp(score), 0.0)
        mixed = (1 - lam) * p / p.sum() + lam * u
        actual = CATS[int(rng.choice(6, p=mixed / mixed.sum()))]
        masses = lambda v: {cat: float(x) for cat, x in zip(CATS, v)}
        rows.append({"street": street, "trigger": f"action:{action}", "actual_bucket": actual,
                     "floor_lambda": lam, "features": feats, "player_uid": str(int(rng.integers(40))),
                     "layers": {"pre": masses(q), "uniform": masses(u), "floor": masses(q)}})
    return rows


def test_fit_recovers_the_model_behind_the_rows():
    base = np.zeros((3, 6))
    base[:, 0], base[:, 5] = 0.8, -0.8                                    # nuts bet more, air less
    weights = np.zeros((len(fl.FEATURES), 6))
    weights[fl.FEATURES.index("size_pot")] = [1.0, 0.5, -0.5, 0.0, 0.0, 0.0]   # big bets are stronger
    weights[fl.FEATURES.index("tight")] = [0.6, 0.6, 0.0, 0.0, 0.0, -0.8]      # so are tight players' bets
    train, val = flm.load(_rows(12000, base, weights)), flm.load(_rows(3000, base, weights, seed=1))
    got_base, got_w = flm.fit_action(train["bet"], kappa=1.0)

    centre = lambda v: v - v.mean()
    for name in ("size_pot", "tight"):
        f = fl.FEATURES.index(name)
        assert np.allclose(centre(got_w[f]), centre(weights[f]), atol=0.3), name
    assert np.abs(got_w[fl.FEATURES.index("in_position")]).max() < 0.25      # never mattered in the rows
    assert centre(got_base[1])[0] - centre(got_base[1])[5] == pytest.approx(1.6, abs=0.35)
    # the fitted model predicts held-out rows better than the shares it was given as "current"
    assert flm.nll(val["bet"], got_base, got_w) < flm.current_nll(val["bet"])
    # ... and so does every out-of-fold prediction: no row is scored by a model that saw it
    d = train["bet"]
    oof = flm.row_nll(d.prob(flm.out_of_fold(d, 1.0)))
    assert oof.mean() < flm.current_nll(d) / len(d)
    assert oof.sum() > flm.nll(d, got_base, got_w)                           # in-sample flatters


def test_error_bars_widen_when_a_few_players_make_all_the_rows():
    rng = np.random.default_rng(0)
    effect = rng.normal(0, 1, 10)                                   # each player is off in his own direction
    who = np.repeat(np.arange(10), 50)
    values = effect[who] + rng.normal(0, 0.2, 500)
    mean, se = flm.clustered(values, who)
    naive = values.std(ddof=1) / np.sqrt(len(values))
    assert mean == pytest.approx(values.mean()) and se > 4 * naive
    # every row its own player: the usual standard error
    assert flm.clustered(values, np.arange(500))[1] == pytest.approx(naive, rel=0.01)


def test_gradient_matches_finite_differences():
    data = flm.load(_rows(300, np.zeros((3, 6)), np.zeros((len(fl.FEATURES), 6)), seed=3))["bet"]
    rng = np.random.default_rng(0)
    theta = rng.normal(0, 0.3, 18 + len(fl.FEATURES) * 6)

    def loss(t):
        b, w = flm._unpack(t)
        return flm.nll(data, b, w) + 0.5 * 2.0 * float((w ** 2).sum()) + 0.5 * flm.BASE_RIDGE * float((b ** 2).sum())

    # reuse the optimiser's objective through one iteration at theta
    captured = {}
    orig = flm.minimize
    try:
        flm.minimize = lambda fun, x0, **kw: captured.setdefault("fun", fun) and type("R", (), {"x": x0})()
        flm.fit_action(data, 2.0)
    finally:
        flm.minimize = orig
    value, grad = captured["fun"](theta)
    assert value == pytest.approx(loss(theta), rel=1e-9)
    for k in rng.choice(len(theta), 12, replace=False):
        step = np.zeros_like(theta)
        step[k] = 1e-5
        numeric = (loss(theta + step) - loss(theta - step)) / 2e-5
        assert grad[k] == pytest.approx(numeric, rel=1e-3, abs=1e-4)


def test_the_file_drives_the_action_model(tmp_path, monkeypatch):
    rows = _rows(1500, np.zeros((3, 6)), np.zeros((len(fl.FEATURES), 6)))
    train, val, out = tmp_path / "train.jsonl", tmp_path / "val.jsonl", tmp_path / "fit.json"
    train.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    val.write_text("".join(json.dumps(r) + "\n" for r in rows[:400]), encoding="utf-8")
    flm.main(["--rows", str(train), "--holdout-rows", str(val), "--out", str(out)])
    fit = json.loads(out.read_text(encoding="utf-8"))
    assert set(fit) == {"type", "fitted_at", "likelihood_model", "report"}
    assert set(fit["likelihood_model"]["actions"]) == {"bet"}
    report = fit["report"]["likelihood_model"]
    assert report["ridge"] in flm.KAPPAS and report["truth"] == "both"
    assert report["out_of_fold"]["showdown"]["rows"] == 1500 and report["holdout"]["all"]["rows"] == 400

    # hand-write a model so the effect is unmistakable: pot-sized bets are never air
    fit["likelihood_model"]["actions"]["bet"]["weights"]["size_pot"] = {c: (-4.0 if c == "air" else 0.0) for c in CATS}
    out.write_text(json.dumps(fit), encoding="utf-8")
    monkeypatch.setenv("PF_FORMULA_FIT_PATH", str(out))
    board = [Card.from_str(c) for c in ("Ah", "7d", "2c", "Ks", "9h")]
    model, prof = ActionModel(), PlayerProfile()
    cats = model._cat_indices(board, "river")

    def air_over_strong(bet_ratio, action="raise"):
        ctx = ActionContext(position="BTN", board=board, street="river", facing_action="check", bet_ratio=bet_ratio)
        ctx.likelihood_features = fl.likelihood_features(
            action="bet", street="river", bet_ratio=bet_ratio, players_in_pot=3, in_position=False,
            hands_seen=0, vpip=0.35, aggression_factor=1.0, history=[])
        like = model.batch_likelihood(action, "river", ctx, prof, board)
        return like[cats == 5].mean() / like[cats == 1].mean()

    assert air_over_strong(1.2) < 0.05 * air_over_strong(0.5)
    assert fl.bucket_likelihood("river", "call", {}) is None                # no model for calls
    ctx = ActionContext(position="BTN", board=board, street="river", facing_action="bet")
    assert np.all(model.batch_likelihood("call", "river", ctx, prof, board) == 1.0)   # ... so a call says nothing
    monkeypatch.setenv("PF_FORMULA_FIT_PATH", "off")
    assert not fl.has_model() and fl.bucket_likelihood("river", "bet", {}) is None


def test_the_tracker_applies_a_fitted_likelihood_without_tempering(tmp_path, monkeypatch):
    from pokerfate.strategy.range_v2.bayesian_range_tracker import BayesianRangeTracker

    def trace_of(path):
        monkeypatch.setenv("PF_FORMULA_FIT_PATH", path)
        tracker = BayesianRangeTracker(ActionModel())
        board = [Card.from_str(c) for c in ("Ah", "7d", "2c")]
        prof = PlayerProfile()
        tracker.reset_hand(7, "BTN", prof)
        ctx = ActionContext(position="BTN", board=board, street="flop", facing_action="check", bet_ratio=0.5)
        tracker.observe_action(7, "raise", "flop", ctx, prof, board)
        return tracker.last_update_trace

    none = trace_of("off")                                                  # no model: the bet says nothing
    assert none["layers"]["likelihood"]["air"] == pytest.approx(none["layers"]["pre"]["air"], rel=1e-6)

    model = {cat: 0.0 for cat in CATS}
    fit = tmp_path / "fit.json"
    fit.write_text(json.dumps({"likelihood_model": {"features": list(fl.FEATURES), "actions": {"bet": {
        "base": {"flop": dict(model, air=-2.0)}, "weights": {}}}}}), encoding="utf-8")
    new = trace_of(str(fit))
    assert new["features"]["size_small"] == 0.0
    pre, after = new["layers"]["pre"], new["layers"]["likelihood"]
    # air is exp(-2) as likely to bet as anything else, applied in full
    expect = pre["air"] * np.exp(-2.0) / (pre["air"] * np.exp(-2.0) + 1.0 - pre["air"])
    assert after["air"] == pytest.approx(expect, rel=0.02)


# ── bets nobody called ───────────────────────────────────────────────────────────────────

def _bluffy_rows(n, seed=0):
    """River bets by a player who bets his air as often as his nuts.  A called bet is shown —
    and here the callers only pay off the strong hands, so a showdown never shows the air; a bet
    nobody calls only tells its hand type (air is 高牌, everything else 一对 or better)."""
    from analysis.type_truth import TYPES
    rng = np.random.default_rng(seed)
    given = np.zeros((6, len(TYPES)))
    given[0, 2] = given[1, 2] = 1.0          # nuts, strong: 两对
    given[2, 1] = 1.0                        # medium: 一对
    given[5, 0] = 1.0                        # air: 高牌
    rows = []
    for i in range(n):
        q = np.array([0.1, 0.2, 0.3, 0.0, 0.0, 0.4])
        like = np.array([1.0, 0.6, 0.2, 0.0, 0.0, 1.0])               # the truth: air bets like the nuts
        held = int(rng.choice(6, p=q * like / (q * like).sum()))
        masses = lambda v: {cat: float(x) for cat, x in zip(CATS, v)}
        common = {"street": "river", "floor_lambda": 0.0, "player_uid": str(i % 50),
                  "features": _features(street="river"), "layers": {"pre": masses(q), "uniform": masses(q), "floor": masses(q)}}
        if held <= 1 and rng.random() < 0.7:                           # called: only value gets shown
            rows.append(dict(common, trigger="action:bet", actual_bucket=CATS[held]))
        else:                                                          # everybody folded: type only
            actual = TYPES[int(np.argmax(given[held]))]
            rows.append(dict(common, trigger="uncontested_win", last_action="bet", actual_type=actual,
                             type_dist={t: 1.0 / len(TYPES) for t in TYPES},
                             type_given_bucket=given.tolist(), uniform_type_given_bucket=given.tolist()))
    return rows


def test_showdowns_alone_miss_the_bluffs_and_uncontested_wins_bring_them_back():
    data = flm.load(_bluffy_rows(6000))["bet"]
    assert set(np.unique(data.kind)) == {flm.SHOWDOWN, flm.WIN}

    def air_share(truth):
        post = data.posterior(*flm.fit_action(data, 1.0, flm.fit_weight(data, truth)))
        return float(post[:, 5].mean())

    true_share = 0.4 * 1.0 / (0.1 * 1.0 + 0.2 * 0.6 + 0.3 * 0.2 + 0.4 * 1.0)      # 0.59 of the bets are air
    assert air_share("showdown") < 0.05                                            # never shown, so "never bet"
    assert air_share("both") == pytest.approx(true_share, abs=0.04)


def test_uncontested_rows_report_type_groups_and_the_gradient_holds_for_them():
    data = flm.load(_bluffy_rows(400, seed=2))["bet"]
    rng = np.random.default_rng(1)
    theta = rng.normal(0, 0.3, 18 + len(fl.FEATURES) * 6)
    loss = lambda t: flm.nll(data, *flm._unpack(t)) + 0.5 * 2.0 * float((flm._unpack(t)[1] ** 2).sum()) \
        + 0.5 * flm.BASE_RIDGE * float((flm._unpack(t)[0] ** 2).sum())
    captured = {}
    orig = flm.minimize
    try:
        flm.minimize = lambda fun, x0, **kw: captured.setdefault("fun", fun) and type("R", (), {"x": x0})()
        flm.fit_action(data, 2.0)
    finally:
        flm.minimize = orig
    value, grad = captured["fun"](theta)
    assert value == pytest.approx(loss(theta), rel=1e-9)
    for k in (0, 5, 12, 17):                                              # river base: nuts, air ...
        step = np.zeros_like(theta)
        step[k] = 1e-5
        assert grad[k] == pytest.approx((loss(theta + step) - loss(theta - step)) / 2e-5, rel=1e-3, abs=1e-4)

    post = {"bet": data.posterior(*flm.fit_action(data, 1.0))}
    names = {item["slice"]: item for item in flm.slices({"bet": data}, post, min_rows=50)}
    high = names["没人跟注 river bet · 高牌"]
    # "current" was a flat guess over the nine types; the model is far closer.  (Not at 0: in
    # this made-up world a bet is called only when it is value, so uncalled bets are bluffier
    # than bets at large.)
    assert high["current"][0] < -50.0 and abs(high["model"][0]) < 25.0
    scores = flm.compare({"bet": data}, post)
    assert set(scores) == {"showdown", "uncontested", "all"}
    assert scores["all"]["rows"] == len(data) and scores["uncontested"]["model"] < scores["uncontested"]["current"]


def test_combo_types_agree_with_the_log_toolkit_and_block_board_cards():
    from analysis import truth, type_truth
    from pokerfate.strategy.range_v2 import hand_combo_map as hcm
    board = ("Ah", "7d", "2c", "Ks")
    types = type_truth.combo_types(board)
    assert types.shape == (1326,)
    rng = np.random.default_rng(0)
    for idx in rng.choice(1326, 60, replace=False):
        cards = [str(hcm.int_to_card(c)) for c in hcm.ALL_COMBOS[idx]]
        if set(cards) & set(board):
            assert types[idx] == -1
        else:
            assert types[idx] == truth.type_rank(cards + list(board))
    weights = np.where(types >= 0, 1.0, 0.0)
    shares = type_truth.type_shares(weights, types)
    assert shares.sum() == pytest.approx(1.0) and shares[0] > shares[1] > shares[2]   # mostly no pair
    assert type_truth.label_type("一对 A A K Q 7") == 1 and type_truth.label_type("") is None


def test_winner_row_needs_a_last_bet_on_the_final_board_and_no_showdown():
    from analysis import type_truth
    from pokerfate.strategy.range_v2.bayesian_range_tracker import BayesianRangeTracker
    tracker = BayesianRangeTracker(ActionModel())
    prof = PlayerProfile()
    tracker.reset_hand(7, "BTN", prof)
    board = ["Ah", "7d", "2c"]
    hand = {"hand": 3, "session": 1, "players": [{"id": 7, "name": "villain"}, {"id": 1, "name": "hero"}],
            "events": [{"type": "board", "street": "flop", "cards": board}],
            "result": {"winners": ["villain"], "showdown_hands": {}, "hand_combos": {"villain": "一对 A A K 7 2"}}}
    last = {7: {"street": "flop", "label": "bet", "features": _features(street="flop"), "lam": 0.08,
                "bet_ratio": 0.5, "board": board, "pre_weights": tracker._weights[7].copy()}}
    row = type_truth.winner_row(hand, tracker, last, "src")
    assert row["trigger"] == "uncontested_win" and row["actual_type"] == "一对" and row["last_action"] == "bet"
    assert sum(row["type_dist"].values()) == pytest.approx(1.0, abs=1e-4)
    assert sum(row["layers"]["pre"].values()) == pytest.approx(1.0, abs=1e-4)
    given = np.array(row["type_given_bucket"])
    assert given.shape == (6, 9) and set(np.round(given.sum(axis=1), 3)) <= {0.0, 1.0}
    assert flm.load([row])["bet"].kind[0] == flm.WIN                            # the fit takes it as it is

    shown = dict(hand, result=dict(hand["result"], showdown_hands={"villain": ["As", "Kd"]}))
    assert type_truth.winner_row(shown, tracker, last, "src") is None           # a showdown has its own rows
    assert type_truth.winner_row(hand, tracker, {7: dict(last[7], label="call")}, "src") is None
    assert type_truth.winner_row(hand, tracker, {7: dict(last[7], board=board + ["Ks"])}, "src") is None
    assert type_truth.winner_row(hand, tracker, {}, "src") is None              # nothing recorded about him


# ── the shipped files ────────────────────────────────────────────────────────────────────

def test_the_deployed_file_is_well_formed(monkeypatch):
    """Whatever was last fitted: every postflop action has a likelihood for every street and bucket."""
    from pokerfate.strategy.range_v2 import formula_fit
    monkeypatch.delenv("PF_FORMULA_FIT_PATH")
    path = formula_fit.formula_fit_path()
    if not path.exists():
        pytest.skip("no fitted formula file deployed")
    fit = json.loads(path.read_text(encoding="utf-8"))
    pre = fit["preflop_model"]
    assert pre["bins"] == list(fl.PREFLOP_BINS) and set(pre["actions"]) == set(fl.PREFLOP_ACTIONS)
    for label in fl.PREFLOP_ACTIONS:
        like = fl.preflop_likelihood(label, _pre_features(label=label, action_type=""))
        assert like.shape == (len(fl.PREFLOP_BINS),) and like.max() == pytest.approx(1.0) and like.min() > 0.0
    model = fit["likelihood_model"]
    assert set(model["features"]) == set(fl.FEATURES) and set(model["actions"]) == set(fl.ACTIONS)
    for action, spec in model["actions"].items():
        for street in ("flop", "turn", "river"):
            assert set(spec["base"][street]) == set(CATS), (action, street)
            assert fl.covers(street, action)
            like = fl.bucket_likelihood(street, action, _features(action=action, street=street))
            assert like.shape == (6,) and like.max() == pytest.approx(1.0) and like.min() > 0.0


def test_a_bucket_model_trained_on_another_formula_fit_is_ignored(tmp_path, monkeypatch):
    from pokerfate.strategy.range_v2 import bucket_ml_calibration as bml
    from pokerfate.strategy.range_v2 import formula_fit

    model = {"runtime_usable": True, "blend_alpha": 0.5, "formula_fit": "an-older-fit"}
    path = tmp_path / "model.json"
    path.write_text(json.dumps(model), encoding="utf-8")
    monkeypatch.setenv("PF_BUCKET_ML_MODEL_PATH", str(path))
    monkeypatch.setattr(bml, "_CACHE", {})
    assert bml._load_model("lgbm") is None                      # the formula layer below it has changed

    fit = tmp_path / "fit.json"
    fit.write_text("{}", encoding="utf-8")
    monkeypatch.setenv("PF_FORMULA_FIT_PATH", str(fit))
    model["formula_fit"] = formula_fit.fingerprint()
    path.write_text(json.dumps(model), encoding="utf-8")
    bml._CACHE.clear()
    assert bml._load_model("lgbm") is not None                  # trained on what is running

    del model["formula_fit"]                                    # a model from before fingerprints existed
    path.write_text(json.dumps(model), encoding="utf-8")
    bml._CACHE.clear()
    assert bml._load_model("lgbm") is not None


def test_the_deployed_bucket_model_matches_the_deployed_formula_fit(monkeypatch):
    from pokerfate.strategy.range_v2 import bucket_ml_calibration as bml
    from pokerfate.strategy.range_v2 import formula_fit

    monkeypatch.delenv("PF_FORMULA_FIT_PATH")
    monkeypatch.delenv("PF_BUCKET_ML_MODEL_PATH", raising=False)
    model = json.loads(bml._model_path().read_text(encoding="utf-8"))
    assert model.get("formula_fit") in (None, formula_fit.fingerprint())


# ── preflop ──────────────────────────────────────────────────────────────────────────────

def _pre_features(**over):
    base = dict(label="open", action_type="open", position="CO", bet_ratio=1.7, is_raise_over=False,
                hands_seen=0, vpip=0.35, pfr=0.12, aggression_factor=1.0, history=[])
    base.update(over)
    return fl.preflop_features(**base)


def test_preflop_lines_features_and_strength_bins():
    assert [fl.preflop_label(t) for t in ("open", "3bet", "4bet", "limp", "call_open", "call_3bet", "check_option")] == [
        "open", "reraise", "reraise", "limp", "call", "call", "check"]
    assert fl.preflop_label("fold") is None and fl.preflop_label("fold_to_open") is None
    assert fl.preflop_label("", "raise") == "open" and fl.preflop_label("", "call") == "limp"   # no line name given

    assert set(_pre_features()) == set(fl.PREFLOP_FEATURES) and not any(_pre_features().values())
    assert _pre_features(position="UTG")["pos_early"] == 1.0 and _pre_features(position="BB")["pos_bb"] == 1.0
    assert _pre_features(bet_ratio=1.0)["size_small"] == 1.0 and _pre_features(bet_ratio=3.0)["size_big"] == 1.0
    assert _pre_features(bet_ratio=40.0)["size_shove"] == 1.0
    assert _pre_features(is_raise_over=True)["over_limpers"] == 1.0
    assert _pre_features(label="reraise", action_type="4bet")["four_bet"] == 1.0
    assert _pre_features(label="call", action_type="call_3bet")["facing_reraise"] == 1.0
    assert _pre_features(label="call", action_type="call_open", history=[("preflop", "call")])["limped_before"] == 1.0
    assert _pre_features(label="call", action_type="call_3bet", history=[("preflop", "bet")])["raised_before"] == 1.0
    reg = _pre_features(hands_seen=90, vpip=0.30, pfr=0.22)
    assert reg["known"] == pytest.approx(0.75) and reg["tight"] == pytest.approx(0.75) and reg["raises_often"] == pytest.approx(0.75)

    from pokerfate.strategy.range_v2 import hand_combo_map as hcm
    bins = fl.preflop_bin_index()
    aces = hcm.COMBO_TO_IDX[tuple(sorted((hcm.card_to_int(Card.from_str("As")), hcm.card_to_int(Card.from_str("Ah")))))]
    trash = hcm.COMBO_TO_IDX[tuple(sorted((hcm.card_to_int(Card.from_str("7s")), hcm.card_to_int(Card.from_str("2h")))))]
    assert bins[aces] == len(fl.PREFLOP_BINS) - 1 and bins[trash] == 0
    share = np.bincount(bins, minlength=len(fl.PREFLOP_BINS)) / 1326
    assert np.all(share[:9] > 0.07) and np.all(share[:9] < 0.13) and share[9:].sum() == pytest.approx(0.1, abs=0.03)
    # the strongest twentieth is three bins, by hand: TT-77 / AQs / AJs, JJ / AK, QQ+
    combo = lambda a, b: hcm.COMBO_TO_IDX[tuple(sorted((hcm.card_to_int(Card.from_str(a)), hcm.card_to_int(Card.from_str(b)))))]
    names = [fl.PREFLOP_BINS[bins[combo(a, b)]] for a, b in (("7s", "7h"), ("As", "Qs"), ("Js", "Jh"), ("As", "Kh"), ("Qs", "Qh"))]
    assert names == ["TT-77,AQs,AJs", "TT-77,AQs,AJs", "JJ,AK", "JJ,AK", "QQ+"]
    assert [int(n) for n in np.bincount(bins)[-3:]] == [32, 22, 18]


def _pre_rows(n, true, seed=0, lam=0.08):
    """Players who limp and, a third of the time, then call a raise.  ``true``: label -> log-likelihood per bin."""
    rng = np.random.default_rng(seed)
    bins = fl.PREFLOP_BINS
    u = np.full(len(bins), 1.0 / len(bins))
    masses = lambda v: {b: float(x) for b, x in zip(bins, v)}
    rows = []
    for i in range(n):
        keep = np.exp(true["limp"])
        twice = rng.random() < 0.33
        chance = keep * (np.exp(true["call"]) if twice else 1.0)
        actual = bins[int(rng.choice(len(bins), p=u * chance / (u * chance).sum()))]
        common = {"street": "preflop", "position": "CO", "player_uid": str(i % 60), "hand": i, "source": "s",
                  "floor_lambda": lam, "actual_bin": actual}
        rows.append(dict(common, preflop_label="limp", features=_pre_features(label="limp", action_type="limp"),
                         layers={"pre": masses(u), "uniform": masses(u), "floor": masses(u)}))
        if twice:                                         # extracted without a model: still "uniform before"
            rows.append(dict(common, preflop_label="call",
                             features=_pre_features(label="call", action_type="call_open", history=[("preflop", "call")]),
                             layers={"pre": masses(u), "uniform": masses(u), "floor": masses(u)}))
    return rows


def test_preflop_fit_carries_a_players_range_from_his_first_action_to_his_second():
    k = len(fl.PREFLOP_BINS)
    true = {"limp": np.linspace(-1.5, 0.0, k), "call": np.linspace(-1.0, 1.0, k)}
    data = flm.load(_pre_rows(9000, true), flm.PREFLOP)
    assert set(data) == {"limp", "call"} and data["call"].chain[0][1] == 1          # second action of its hand
    models = {a: flm.fit_action(d, 1.0) for a, d in data.items()}
    naive_slope = models["call"][0][0][-1] - models["call"][0][0][0]
    for _ in range(4):                                    # what main() does
        if flm.carry_ranges(data, models) < 1e-4:
            break
        models = {a: flm.fit_action(d, 1.0) for a, d in data.items()}
    # before the call the range is no longer uniform: it is what the limp left
    call = data["call"]
    assert call.q[0, -1] > 1.5 * call.q[0, 0]
    slope = lambda a: models[a][0][0][-1] - models[a][0][0][0]
    assert naive_slope > slope("call") + 0.5              # without the carry-over the call takes credit for the limp
    # ... and the two steps together say what the callers turned out to hold
    after = call.mixed(call.posterior(*models["call"]))
    assert after[:, -3:].sum(axis=1).mean() == pytest.approx((call.y >= k - 3).mean(), abs=0.03)
    assert slope("limp") > 1.5                            # shown limpers include those who went on to call


def test_preflop_fit_writes_its_own_section_and_keeps_the_other(tmp_path):
    k = len(fl.PREFLOP_BINS)
    rows = _pre_rows(1500, {"limp": np.linspace(-1.5, 0.0, k), "call": np.zeros(k)})
    train, out, base = tmp_path / "rows.jsonl", tmp_path / "fit.json", tmp_path / "base.json"
    train.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    base.write_text(json.dumps({"likelihood_model": {"features": [], "actions": {}}}), encoding="utf-8")
    flm.main(["--layer", "preflop", "--rows", str(train), "--base", str(base), "--out", str(out)])
    fit = json.loads(out.read_text(encoding="utf-8"))
    assert fit["likelihood_model"] == {"features": [], "actions": {}}               # the other layer is kept
    model = fit["preflop_model"]
    assert model["bins"] == list(fl.PREFLOP_BINS) and set(model["actions"]) == {"limp", "call"}
    limp = model["actions"]["limp"]["base"]["all"]
    assert limp[fl.PREFLOP_BINS[-1]] > limp["00-10"] + 0.8
    assert fit["report"]["preflop_model"]["out_of_fold"]["showdown"]["rows"] == len(rows)


def _pre_model_file(tmp_path, monkeypatch):
    flat = {b: 0.0 for b in fl.PREFLOP_BINS}
    steep = {b: -4.0 + 4.0 * i / (len(fl.PREFLOP_BINS) - 1) for i, b in enumerate(fl.PREFLOP_BINS)}
    path = tmp_path / "fit.json"
    path.write_text(json.dumps({"preflop_model": {"bins": list(fl.PREFLOP_BINS), "actions": {
        "open": {"base": {"all": steep}, "weights": {"size_big": {fl.PREFLOP_BINS[-1]: 1.0}}},
        "check": {"base": {"all": flat}, "weights": {}}}}}), encoding="utf-8")
    monkeypatch.setenv("PF_FORMULA_FIT_PATH", str(path))


def test_tracker_starts_uniform_and_lets_the_preflop_model_speak(tmp_path, monkeypatch):
    from pokerfate.strategy.range_v2.bayesian_range_tracker import BayesianRangeTracker
    _pre_model_file(tmp_path, monkeypatch)
    bins = fl.preflop_bin_index()
    prof = PlayerProfile(hands_seen=200, vpip=0.10, pfr=0.08)                # a nit: it does not matter
    top = lambda tracker: float(tracker.get_distribution(7)[bins == len(fl.PREFLOP_BINS) - 1].sum())

    tracker = BayesianRangeTracker(ActionModel())
    tracker.reset_hand(7, "BB", prof)
    start = top(tracker)
    assert np.allclose(tracker.get_distribution(7), 1.0 / 1326)             # any two cards
    ctx = ActionContext(position="BB", board=[], street="preflop", facing_action="check", preflop_action_type="check_option")
    tracker.observe_action(7, "check", "preflop", ctx, prof, [])
    assert top(tracker) == pytest.approx(start)                             # a free check says nothing here
    assert tracker.last_update_trace == {}                                  # no preflop trace in play

    opener = BayesianRangeTracker(ActionModel())
    opener.keep_update_weights = True                                       # the extractor's switch
    opener.reset_hand(7, "CO", prof)
    ctx = ActionContext(position="CO", board=[], street="preflop", facing_action="raise", bet_ratio=1.7,
                        preflop_action_type="open")
    opener.observe_action(7, "raise", "preflop", ctx, prof, [])
    assert top(opener) > 4 * start
    trace = opener.last_update_trace
    assert trace["preflop_label"] == "open" and set(trace["layers"]["pre"]) == set(fl.PREFLOP_BINS)
    best = fl.PREFLOP_BINS[-1]
    assert trace["layers"]["floor"][best] > 4 * trace["layers"]["pre"][best]
    assert trace["features"]["known"] > 0.8 and trace["lam"] == 0.08

    big = BayesianRangeTracker(ActionModel())
    big.reset_hand(7, "CO", prof)
    big.observe_action(7, "raise", "preflop", ActionContext(position="CO", board=[], street="preflop", facing_action="raise",
                                                           bet_ratio=3.0, preflop_action_type="open"), prof, [])
    assert top(big) > 1.5 * top(opener)                                     # the size feature reaches the model


def test_hole_cards_of_the_last_hand_do_not_block_this_one():
    """Until 2026-11-15 the ranges of a new hand were built while the previous hand's hole cards
    were still 'known': every combo with one of them stayed impossible all hand."""
    from pokerfate.strategy.range_v2 import hand_combo_map as hcm
    from pokerfate.strategy.range_v2.bayesian_range_tracker import BayesianRangeTracker
    cards = lambda *names: [Card.from_str(n) for n in names]
    idx = lambda a, b: hcm.COMBO_TO_IDX[tuple(sorted((hcm.card_to_int(Card.from_str(a)), hcm.card_to_int(Card.from_str(b)))))]
    tracker, prof = BayesianRangeTracker(ActionModel()), PlayerProfile()

    tracker.start_new_hand()
    tracker.reset_hand(7, "CO", prof)
    tracker.set_known_cards(cards("As", "Kd"))                              # hand 1: hero holds As Kd
    assert tracker.get_distribution(7)[idx("As", "Qh")] == 0.0

    tracker.start_new_hand()                                                # hand 2, as the bot drives it:
    tracker.reset_hand(7, "CO", prof)                                       # ranges first,
    tracker.set_known_cards(cards("7c", "7d"))                              # hole cards after
    w = tracker.get_distribution(7)
    assert w[idx("As", "Qh")] > 0.0 and w[idx("Kd", "Ks")] > 0.0            # last hand's cards are free again
    assert w[idx("7c", "8c")] == 0.0 and w[idx("7d", "7h")] == 0.0          # this hand's are not, already preflop
    assert int((w > 0).sum()) == 1225 and w.sum() == pytest.approx(1.0)


def test_a_preflop_model_fitted_on_other_bins_is_not_read(tmp_path, monkeypatch):
    old_bins = list(fl.PREFLOP_BINS[:10]) + ["95-100"]
    path = tmp_path / "fit.json"
    path.write_text(json.dumps({"preflop_model": {"bins": old_bins, "actions": {
        "open": {"base": {"all": {b: 1.0 for b in old_bins}}, "weights": {}}}}}), encoding="utf-8")
    monkeypatch.setenv("PF_FORMULA_FIT_PATH", str(path))
    assert fl.preflop_likelihood("open", _pre_features()) is None
