import json
import shutil
import threading

import pytest

from pokerfate.api import ActionEvent, PlayerInfo, PokerFateAPI
from pokerfate.core.card import Card
from pokerfate.core.game_state import Action, ActionType
from pokerfate.decision.flop_book import (
    BOOK_SCHEMA_VERSION,
    DEFAULT_BOOK_DIR,
    BookMiss,
    FlopBook,
    FlopBookDecisionEngine,
    _select_strategy_action,
)
from pokerfate.strategy.range_v2 import hand_combo_map as hcm

SCENES = {f"{pos}vBB_srp{depth}" for pos in ("UTG", "MP", "CO", "BTN", "SB") for depth in (50, 100)}


def test_default_book_is_the_project_local_v3_book():
    assert DEFAULT_BOOK_DIR.name == "v3"
    assert DEFAULT_BOOK_DIR.parent.name == "flop_book"
    assert not DEFAULT_BOOK_DIR.is_symlink()
    book = FlopBook()
    try:
        meta = book.meta
        assert meta["book_version"] == "v3" and meta["schema_version"] == BOOK_SCHEMA_VERSION == 3
        assert meta["complete"] is True and not meta.get("allow_unconverged", False)
        assert meta["rake"] == {"rate": 0.09, "cap_bb": None}
        assert {s["id"] for s in meta["scenarios"]} == SCENES
        by_id = {s["id"]: s for s in meta["scenarios"]}
        # Flop-start pot and remaining stack after the 3.5bb / 4bb opens.
        assert (by_id["BTNvBB_srp50"]["pot"], by_id["BTNvBB_srp50"]["effective_stack"]) == (7.5, 46.5)
        assert (by_id["BTNvBB_srp100"]["pot"], by_id["BTNvBB_srp100"]["effective_stack"]) == (7.5, 96.5)
        assert (by_id["SBvBB_srp100"]["pot"], by_id["SBvBB_srp100"]["effective_stack"]) == (8, 96)
        assert (by_id["UTGvBB_srp50"]["pot"], by_id["UTGvBB_srp50"]["effective_stack"]) == (8.5, 46)
    finally:
        book.close()


def _book_dir_with_meta(root, name, mutate):
    """A book directory holding the real v3 index files and an edited meta.json."""
    target = root / name
    target.mkdir()
    for filename in ("meta.json", "flop_iso_map.json", "flop_clusters.json"):
        shutil.copy(DEFAULT_BOOK_DIR / filename, target / filename)
    meta = json.loads((target / "meta.json").read_text())
    mutate(meta)
    (target / "meta.json").write_text(json.dumps(meta))
    return target


def test_older_or_incomplete_books_are_rejected(tmp_path):
    # The archived v2 book has no schema_version at all.
    with pytest.raises(BookMiss, match="book_schema_unsupported:None"):
        FlopBook(_book_dir_with_meta(tmp_path, "no_schema", lambda m: m.pop("schema_version")))
    with pytest.raises(BookMiss, match="book_schema_unsupported:2"):
        FlopBook(_book_dir_with_meta(tmp_path, "schema2", lambda m: m.update(schema_version=2)))
    with pytest.raises(BookMiss, match="book_not_complete"):
        FlopBook(_book_dir_with_meta(tmp_path, "partial", lambda m: m.update(complete=False)))


def test_flop_book_reads_strategy_matrix_for_both_depths():
    book = FlopBook()
    try:
        deep = book.lookup("BTNvBB_srp100", "4c4d3c", "As2s", [])
        short = book.lookup("BTNvBB_srp50", "4c4d3c", "As2s", [])
    finally:
        book.close()

    assert deep["scenario"] == "BTNvBB_srp100"
    assert deep["node_path"] == "r"
    assert deep["actor"] == 0
    assert deep["flop_representative"] == "4c4d3c"
    assert deep["node_pot_bb"] == 7.5
    assert deep["actions"] == ["x", "b33", "b50", "b67", "b100"]
    assert deep["strategy"]["x"] == pytest.approx(0.9783169299)
    assert sum(deep["strategy"].values()) == pytest.approx(1.0)
    assert short["strategy"]["x"] == pytest.approx(0.9774776837)
    assert short["strategy"]["b33"] == pytest.approx(0.0221713588)


def test_flop_book_walks_checked_prefix_and_bet_response():
    book = FlopBook()
    try:
        ip = book.lookup("BTNvBB_srp100", "4c4d3c", "AsKd", [("check", 0.0)])
        # A real 2.5bb bet into 7.5bb maps to the book's b33 branch.
        facing = book.lookup("BTNvBB_srp100", "4c4d3c", "As2s", [("check", 0.0), ("bet", 2.5)])
    finally:
        book.close()

    assert ip["node_path"] == "r:x"
    assert ip["actor"] == 1
    assert set(ip["actions"]) == {"x", "b33", "b50", "b67", "b100"}
    assert ip["strategy"]["b33"] == pytest.approx(0.648203, abs=1e-5)
    assert ip["strategy"]["b50"] == pytest.approx(0.320363, abs=1e-5)
    assert facing["node_path"] == "r:x:b33"
    assert facing["actions"] == ["f", "c", "r2.0x", "r4.0x"]
    assert facing["strategy"]["c"] == pytest.approx(0.884092, abs=1e-5)


def test_selection_compares_passive_actions_with_total_aggression():
    # Hand 514 of the 2026-11-12 session (SB open, 100bb book): the book bets 60%
    # of the time but splits it over four sizes; the single largest label is x.
    split = {"x": 0.40, "b33": 0.28, "b50": 0.20, "b67": 0.06, "b100": 0.06}
    assert max(split, key=split.get) == "x"
    assert _select_strategy_action(split) == ("b33", 0.28)
    # Hand 1484: the preferred size is the largest one.
    assert _select_strategy_action({"x": 0.42, "b33": 0.04, "b67": 0.17, "b100": 0.37}) == ("b100", 0.37)
    # A real majority check stays a check.
    assert _select_strategy_action({"x": 0.51, "b33": 0.39, "b50": 0.08, "b67": 0.01, "b100": 0.01}) == ("x", 0.51)
    # Facing a bet: fold, call and "any raise" are three kinds.
    assert _select_strategy_action({"f": 0.30, "c": 0.32, "r2.0x": 0.20, "r4.0x": 0.18}) == ("r2.0x", 0.20)
    assert _select_strategy_action({"f": 0.45, "c": 0.25, "r2.0x": 0.20, "r4.0x": 0.10}) == ("f", 0.45)
    assert _select_strategy_action({"f": 0.0, "c": 0.884092, "r2.0x": 0.005524, "r4.0x": 0.110384}) == ("c", 0.884092)
    assert _select_strategy_action({"f": 0.2, "c": 0.3, "ai": 0.5}) == ("ai", 0.5)


def _btn_open_bb_call_api(monkeypatch, *, villain_start, hero_stack, open_to=35_000, third_player=False):
    api = PokerFateAPI(
        my_player_id=0,
        big_blind=10_000,
        small_blind=5_000,
        autosave_path=None,
        decision_engine="cfr",
        equity_iterations=5,
    )
    monkeypatch.setattr(api, "_rule_engine_shadow_decide", lambda *args, **kwargs: None)
    players = [PlayerInfo(1, "BTN", villain_start, "BTN")]
    if third_player:
        players.append(PlayerInfo(2, "SB", villain_start, "SB"))
    players.append(PlayerInfo(0, "Hero", hero_stack, "BB"))
    api.new_hand(players=players, dealer_id=1)
    api.deal_hole_cards(["As", "2s"])
    api.notify_action(ActionEvent(1, "raise", open_to, "preflop"))
    pot = 2 * open_to + 5_000
    if third_player:
        api.notify_action(ActionEvent(2, "call", open_to, "preflop"))
        pot = 3 * open_to
    api._action_history.append((0, Action(ActionType.CALL, 0.0), "preflop"))
    api.deal_board(["4c", "4d", "3c"], street="flop", pot=pot)
    decision = api.request_action(
        "flop",
        pot=pot,
        current_bet=0,
        to_call=0,
        my_stack=hero_stack,
        my_current_bet_this_street=0,
    )
    return api, decision


@pytest.mark.parametrize("start_stack,scenario,depth", [
    (1_000_000, "BTNvBB_srp100", 100),   # 96.5bb left on the flop
    (500_000, "BTNvBB_srp50", 50),       # 46.5bb left
    (635_000, "BTNvBB_srp50", 50),       # 60bb left: still closer to the 50bb book
    (665_000, "BTNvBB_srp100", 100),     # 63bb left: closer to the 100bb book
])
def test_cfr_decision_engine_uses_flop_book_and_picks_the_depth(monkeypatch, start_stack, scenario, depth):
    api, decision = _btn_open_bb_call_api(
        monkeypatch, villain_start=start_stack, hero_stack=start_stack - 35_000,
    )

    diagnostics = api.last_decision_diagnostics()
    status = api.decision_engine_status()
    assert decision.action == "check"
    assert diagnostics["decision_source"] == "flop_book"
    book = diagnostics["flop_book"]
    assert book["status"] == "ok"
    assert book["scenario"] == scenario
    assert book["book_version"] == "v3"
    assert book["book_depth_bb"] == depth
    assert book["expected_pot_bb"] == 7.5
    assert book["selected_label"] == "x"
    assert book["exploit"]["mode"] == "probability_bias_no_evs"
    assert status["requested"] == "cfr"
    assert status["engine"] == "cfr"
    assert status["mode"] == "flop_book_turn_river"
    assert status["flop_book"] is True
    assert status["realtime_cfr"] is True


@pytest.mark.parametrize("kwargs,reason", [
    # Min-raise pot (4.5bb) is 40% away from the book's 7.5bb.
    (dict(villain_start=1_000_000, hero_stack=980_000, open_to=20_000), "book_pot_mismatch"),
    # 140bb left: nearest book is 100bb (96.5 left), 45% away.
    (dict(villain_start=1_435_000, hero_stack=1_400_000), "book_stack_mismatch"),
    # 30bb left: below the supported window.
    (dict(villain_start=335_000, hero_stack=300_000), "book_stack_out_of_range"),
    # Three players see the flop.
    (dict(villain_start=1_000_000, hero_stack=965_000, third_player=True), "requires_heads_up_active_players"),
])
def test_cfr_flop_book_mismatch_falls_back_to_rule_engine(monkeypatch, kwargs, reason):
    monkeypatch.setattr(
        "pokerfate.bot.poker_bot.PokerBot.decide",
        lambda self, gs, player_id, is_bb_option=False: Action(ActionType.CHECK, 0.0),
    )
    api, decision = _btn_open_bb_call_api(monkeypatch, **kwargs)

    assert decision.action == "check"
    assert api.last_decision_diagnostics()["decision_source"] == "rule_engine"
    assert api._flop_book_error == reason


def test_engine_default_reads_every_scenario_of_the_project_book(monkeypatch):
    monkeypatch.delenv("PF_FLOP_BOOK_DIR", raising=False)
    engine = FlopBookDecisionEngine()
    try:
        assert engine.book.dir == DEFAULT_BOOK_DIR
        for scene in engine.book.meta["scenarios"]:
            conn = engine.book._conn(scene["id"])
            flops = conn.execute("SELECT count(*) FROM flops").fetchone()[0]
            roots = conn.execute("SELECT count(*) FROM nodes WHERE node_path='r'").fetchone()[0]
            assert flops == roots == scene["flop_count"] == 200, scene["id"]
    finally:
        engine.close()


def test_flop_book_lookup_is_usable_from_worker_threads():
    """Decisions run on executor threads; the cached sqlite connection must
    work from a thread other than the one that opened it."""
    book = FlopBook()
    errors: list[BaseException] = []
    try:
        book.lookup("BTNvBB_srp100", "4c4d3c", "As2s", [])

        def worker() -> None:
            try:
                book.lookup("BTNvBB_srp100", "4c4d3c", "As2s", [("check", 0.0)])
            except BaseException as exc:  # noqa: BLE001
                errors.append(exc)

        t = threading.Thread(target=worker)
        t.start()
        t.join()
    finally:
        book.close()
    assert errors == []


def test_flop_book_range_action_probs_cover_hero_range():
    book = FlopBook()
    try:
        lookup = book.lookup("BTNvBB_srp100", "4c4d3c", "As2s", [])
        probs = book.range_action_probs(lookup, "x")
    finally:
        book.close()
    # Board cards are dead: no combo containing them may appear.
    dead = {hcm.card_to_int(Card.from_str(c)) for c in ["4c", "4d", "3c"]}
    assert probs
    assert all(0.0 <= p <= 1.0 for p in probs.values())
    for idx in probs:
        c1, c2 = hcm.cards_of(idx)
        assert hcm.card_to_int(c1) not in dead and hcm.card_to_int(c2) not in dead
    # Hero's own combo probability matches the single-hand lookup.
    idx = hcm.COMBO_TO_IDX[tuple(sorted((hcm.card_to_int(Card.from_str("As")), hcm.card_to_int(Card.from_str("2s")))))]
    assert probs[idx] == pytest.approx(lookup["strategy"]["x"], abs=1e-6)


# The imports for the tests below stay here, not at the top: the v3-switch rollback patch
# (pf_offline_book/archive/flop-book-v2-zc6sb8ct) matches the first lines of this file.
from types import SimpleNamespace  # noqa: E402

from pokerfate.core.game_state import GameState, Player  # noqa: E402


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
