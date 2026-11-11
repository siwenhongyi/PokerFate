from types import SimpleNamespace

import pytest

from pokerfate.core.game_state import Action, ActionType, GameState, Player
from pokerfate.decision.flop_book import BookMiss, FlopBook, FlopBookDecisionEngine


def test_book_directory_can_be_selected_without_changing_default(monkeypatch, tmp_path):
    import pokerfate.decision.flop_book as module
    from pokerfate.decision.flop_book import FlopBookOptions

    selected = []
    monkeypatch.setattr(module, 'FlopBook', lambda path: selected.append(path) or object())
    monkeypatch.setenv('PF_FLOP_BOOK_DIR', str(tmp_path / 'v3'))
    FlopBookDecisionEngine()
    FlopBookDecisionEngine(options=FlopBookOptions(book_dir='explicit'))
    monkeypatch.delenv('PF_FLOP_BOOK_DIR')
    FlopBookDecisionEngine()
    assert selected == [str(tmp_path / 'v3'), 'explicit', module.DEFAULT_BOOK_DIR]


@pytest.mark.parametrize("amount,expected", [(10, "r2x"), (12.5, "r2x"), (20, "r4x"), (60, None)])
def test_raise_sizes_match_actual_previous_bet(amount, expected):
    assert FlopBook._match_action(["f", "c", "r2x", "r4x", "ai"], "raise", amount, 15, 5) == expected


def test_walk_uses_real_bet_not_rounded_book_size(monkeypatch):
    book = object.__new__(FlopBook)
    nodes = {
        "r": {"actions": ["b50"], "pot": 10},
        "r:b50": {"actions": ["r2x", "r4x"], "pot": 15},
        "r:b50:r4x": {"actions": ["f", "c"], "pot": 35},
    }
    monkeypatch.setattr(book, "_fetch", lambda conn, flop, path: nodes[path])
    # Actual first bet 6 maps to book bet 5; a real raise-to 24 is still 4x.
    path, _ = book._walk_path(None, "unused", [("bet", 6), ("raise", 24)])
    assert path == "r:b50:r4x"
    with pytest.raises(BookMiss, match="action_path_miss"):
        book._walk_path(None, "unused", [("bet", 6), ("raise", 100)])


@pytest.mark.parametrize("remaining,depth", [(46.5, 50), (60, 50), (63, 100), (96.5, 100)])
def test_selects_depth_from_flop_start_effective_stack(remaining, depth):
    bb, btn = Player(1, "BB", remaining - 5, current_bet=5), Player(2, "BTN", remaining)
    gs = GameState([bb, btn], big_blind=1, player_positions={1: "BB", 2: "BTN"},
                   action_history=[(2, Action(ActionType.RAISE, 3.5), "preflop"),
                                   (1, Action(ActionType.CALL), "preflop")])
    book = SimpleNamespace(meta={"schema_version": 3, "scenarios": [
        {"id": f"BTNvBB_srp{d}", "depth_bb": d, "pot": 7.5, "effective_stack": d - 3.5}
        for d in (50, 100)
    ]})
    engine = FlopBookDecisionEngine(book=book)
    result = engine._scenario_from_preflop(gs, bb, btn)
    assert result["scenario_id"] == f"BTNvBB_srp{depth}"
    assert result["depth_bb"] == depth
