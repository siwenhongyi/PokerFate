"""The report that says how far each step of a range update is from the hands shown."""
from unittest.mock import Mock

from analysis.range_layers import bias, collect


def _row(street, trigger, actual, pre, likelihood, floor, features=None):
    layer = lambda strong: {"nuts": 0.0, "strong": strong, "air": 1.0 - strong}
    return {"street": street, "trigger": trigger, "actual_bucket": actual, "features": features,
            "layers": {"pre": layer(pre), "likelihood": layer(likelihood), "floor": layer(floor),
                       "bucket_cal": layer(floor)}}


def test_bias_is_reported_per_step_and_per_cut():
    pot = {"size_pot": 1.0, "known": 0.9, "tight": 0.8}
    rows = [
        _row("river", "action:bet", "strong", 0.40, 0.55, 0.50, pot),
        _row("river", "action:bet", "air", 0.40, 0.55, 0.50, pot),
        _row("river", "action:bet", "strong", 0.40, 0.55, 0.50, {"size_small": 1.0}),
        _row("river", "board:river", "strong", 0.4, 0.4, 0.4),                   # no action: no cut
        {"street": "river", "trigger": "action:call", "actual_bucket": "nuts"},  # row without a trace
    ]
    cells, cuts = collect(rows)

    cell = cells[("river", "bet")]
    assert cell[0] == 3 and cell[1] == 2.0                                      # held strong 2 of 3
    assert [round(bias(cell, name)[0], 1) for name in ("pre", "likelihood", "floor")] == [-26.7, -11.7, -16.7]
    assert cuts["尺寸 满池及以上"][0] == 2 and round(bias(cuts["尺寸 满池及以上"], "floor")[0], 1) == 0.0
    assert round(bias(cuts["尺寸 小注"], "floor")[0], 1) == -50.0
    assert cuts["对手 bet 紧手"][0] == 2 and cuts["对手 bet 不认识(<30手)"][0] == 1
    assert ("river", "call") not in cells and ("river", "river") in cells      # board rows need a trace too


def test_extracted_action_rows_carry_the_layer_trace(tmp_path):
    from scripts.extract_range_calibration_rows_parallel import _attach_inline_calibrator

    stored = {7: []}
    calibrator = Mock(_hand_predictions=stored)
    calibrator.record_prediction = lambda **kw: stored[kw["player_id"]].append(
        {"trigger": kw["trigger"], "street": kw["street"]})
    features = {"size_pot": 1.0}
    tracker = Mock(last_update_trace={"layers": {"pre": {"nuts": 0.1, "strong": 0.2, "air": 0.3}},
                                      "lam": 0.08, "bet_ratio": 1.0, "features": features},
                   last_update_weights=[0.5, 0.5])
    api = Mock()
    api._bot._range_tracker = tracker
    api.learnable_prediction = lambda kwargs: kwargs
    _attach_inline_calibrator(api, calibrator)

    tracker._prediction_hook(player_id=7, trigger="action:raise_over", street="flop")
    tracker._prediction_hook(player_id=7, trigger="board:turn", street="turn")          # not an action
    tracker._prediction_hook(player_id=7, trigger="action:fold_other", street="turn")   # range unchanged
    assert stored[7][0]["layers"] == {"pre": {"nuts": 0.1, "strong": 0.2, "air": 0.3}}
    assert (stored[7][0]["floor_lambda"], stored[7][0]["features"]) == (0.08, features)
    assert all("layers" not in rec for rec in stored[7][1:])
    # the player's last action of the hand is kept for a pot won without showdown
    last = api._last_kept_actions[7]
    assert (last["street"], last["label"], last["features"], last["pre_weights"]) == ("flop", "raise_over", features, [0.5, 0.5])


def test_flop_entry_report_scores_the_range_against_the_cards_shown(capsys):
    from analysis import flop_entry

    def row(mass, actual, p_actual, line="limp"):
        return {"preflop_action_type": line, "position": "CO", "player_uid": "7", "player_profile": {"hands_seen": 5},
                "flop_entry": {"decile_mass": mass, "decile_live": [122] * 10, "actual_decile": actual,
                               "p_actual": p_actual, "live_combos": 1220}}
    narrow = [0.0] * 9 + [1.0]
    rows = [row(narrow, 9, 1 / 122)] * 60 + [row(narrow, 0, 1e-9)] * 40          # 40% of the shown hands "impossible"
    flop_entry.main.__globals__["iter_rows"] = lambda paths: iter(rows)
    try:
        flop_entry.main(["rows.jsonl"], min_rows=50)
    finally:
        flop_entry.main.__globals__["iter_rows"] = __import__("analysis.range_layers", fromlist=["iter_rows"]).iter_rows
    out = capsys.readouterr().out
    assert "翻前动作 limp" in out and "100 手" in out
    line = next(l for l in out.splitlines() if l.startswith("== 全部"))
    assert "-" in line.split("：")[-1]                                             # worse than knowing nothing
    held = next(l for l in out.splitlines() if "实际亮出" in l).split()
    assert float(held[1]) == 40.0 and float(held[10]) == 60.0
