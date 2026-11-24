"""analysis.pflog rebuilds each hand's chips from the JSON log."""

import json

import pytest

from analysis import pflog


def _hand_log(tmp_path, *, executed):
    """Heads-up flop: hero bets first, the villain folds."""
    events = [
        {"event": "hand_start", "hand": 1, "dealer_id": 1, "players": [
            {"id": 1, "name": "Hero", "stack": 1000, "pos": "BTN"},
            {"id": 2, "name": "Villain", "stack": 1000, "pos": "BB"}]},
        {"event": "hole_cards", "hand": 1, "cards": ["As", "Kd"]},
        {"event": "board", "hand": 1, "street": "flop", "cards": ["Qh", "7c", "2d"]},
        {"event": "decision", "hand": 1, "street": "flop", "action": "raise", "amount": 50.0,
         "pot": 40.0, "to_call": 0.0, "current_bet": 0.0, "my_current_bet": 0.0},
        *([{"event": "hero_execution", "hand": 1, "street": "flop", "action": "raise",
            "amount_added": executed, "total_bet_after": executed}] if executed is not None else []),
        {"event": "opponent_action", "hand": 1, "street": "flop", "player": "Villain",
         "action": "fold", "amount": 0.0},
        {"event": "hand_result", "hand": 1, "winners": ["Hero"], "pot": 40.0, "my_delta": 20.0},
    ]
    path = tmp_path / "pokerfate.log"
    path.write_text("".join(json.dumps(e) + "\n" for e in events), encoding="utf-8")
    return path


@pytest.mark.parametrize("executed, hero_bet", [
    (80.0, 80.0),    # the server's confirmed amount wins over the engine's request
    (None, 50.0),    # no confirmation: the decision's amount
])
def test_hero_bet_follows_the_server_confirmation(tmp_path, executed, hero_bet):
    hands, _ = pflog.parse_file(_hand_log(tmp_path, executed=executed), hero_names={"Hero"})
    hero_actions = [a for a in hands[0]["actions"] if a["hero"]]
    assert [(a["street"], a["act"], a["add"]) for a in hero_actions] == [("flop", "raise", hero_bet)]
