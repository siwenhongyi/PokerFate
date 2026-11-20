"""Button-relative position relabelling for short-handed tables.

Upstream labels seats forwards from the BB ('UTG', 'UTG+1', ...). Charts and
range tables are keyed on 6-max positions counted backwards from the BTN, so
4-handed 'UTG' must be played as the CO, 5-handed 'UTG'/'UTG+1' as MP/CO.
"""

from pokerfate.api import PlayerInfo, PokerFateAPI
from pokerfate.core.card import Card
from pokerfate.core.position import relabel_positions_by_button
from pokerfate.data import lookup_gto
from pokerfate.strategy.preflop import _hand_category


def test_six_handed_matches_canonical_six_max():
    raw = {1: 'SB', 2: 'BB', 3: 'UTG', 4: 'UTG+1', 5: 'UTG+2', 6: 'BTN'}
    out = relabel_positions_by_button(raw)
    assert out == {1: 'SB', 2: 'BB', 3: 'UTG', 4: 'MP', 5: 'CO', 6: 'BTN'}


def test_five_handed_first_seat_is_mp_second_is_co():
    raw = {1: 'SB', 2: 'BB', 3: 'UTG', 4: 'UTG+1', 5: 'BTN'}
    assert relabel_positions_by_button(raw) == {1: 'SB', 2: 'BB', 3: 'MP', 4: 'CO', 5: 'BTN'}


def test_four_handed_only_seat_is_co():
    raw = {1: 'SB', 2: 'BB', 3: 'UTG', 4: 'BTN'}
    assert relabel_positions_by_button(raw) == {1: 'SB', 2: 'BB', 3: 'CO', 4: 'BTN'}


def test_dead_blind_three_handed_seat_is_co():
    raw = {2: 'BB', 3: 'UTG', 4: 'BTN'}
    assert relabel_positions_by_button(raw) == {2: 'BB', 3: 'CO', 4: 'BTN'}


def test_blinds_button_and_unknown_labels_untouched():
    raw = {1: 'SB', 2: 'BB', 3: '', 4: 'BTN', 5: 'XYZ'}
    assert relabel_positions_by_button(raw) == raw


def test_idempotent_on_canonical_labels():
    canonical = {1: 'SB', 2: 'BB', 3: 'MP', 4: 'CO', 5: 'BTN'}
    assert relabel_positions_by_button(canonical) == canonical
    canonical6 = {1: 'SB', 2: 'BB', 3: 'UTG', 4: 'MP', 5: 'CO', 6: 'BTN'}
    assert relabel_positions_by_button(canonical6) == canonical6


def test_nine_max_forward_labels_compress_to_six_max():
    raw = {1: 'SB', 2: 'BB', 3: 'UTG', 4: 'UTG+1', 5: 'UTG+2', 6: 'LJ', 7: 'HJ', 8: 'CO', 9: 'BTN'}
    out = relabel_positions_by_button(raw)
    assert out[8] == 'CO' and out[7] == 'MP'
    assert all(out[pid] == 'UTG' for pid in (3, 4, 5, 6))


def _api():
    return PokerFateAPI(
        my_player_id=0, big_blind=2.0, small_blind=1.0,
        equity_iterations=100, verbose=False, decision_seed=7,
    )


def test_four_handed_hero_utg_label_uses_co_chart(tmp_path):
    """Hero dealt 'UTG' at a 4-handed table must act from the CO chart."""
    api = _api()
    api.new_hand(
        players=[
            PlayerInfo(0, "Hero", 200.0, "UTG"),
            PlayerInfo(1, "Btn", 200.0, "BTN"),
            PlayerInfo(2, "Sb", 200.0, "SB"),
            PlayerInfo(3, "Bb", 200.0, "BB"),
        ],
        dealer_id=1,
    )
    assert api._hand_positions[0] == 'CO'
    assert api._hand_positions_raw[0] == 'UTG'
    # Pick a hand the CO-RFI chart opens but the UTG-RFI chart folds, so the
    # test asserts the chart actually consulted rather than a hard-coded hand.
    cards = ["Th", "8h"]
    cat = _hand_category([Card.from_str(c) for c in cards])
    co_primary = lookup_gto("CO-RFI", cat).get("primary")
    utg_primary = lookup_gto("UTG-RFI", cat).get("primary")
    assert co_primary is not None and utg_primary is not None
    assert str(co_primary) != str(utg_primary)
    api.deal_hole_cards(cards)
    decision = api.request_action(
        street="preflop", pot=3.0, current_bet=2.0, to_call=2.0,
        my_stack=200.0, num_active_opponents=3, my_current_bet_this_street=0.0,
    )
    assert decision.action == "raise"


def test_hand_start_log_records_raw_label(tmp_path):
    log_path = tmp_path / "pf.log"
    api = PokerFateAPI(
        my_player_id=0, big_blind=2.0, small_blind=1.0, equity_iterations=50,
        verbose=False, log_file=str(log_path),
    )
    api.new_hand(
        players=[
            PlayerInfo(0, "Hero", 200.0, "UTG"),
            PlayerInfo(1, "Btn", 200.0, "BTN"),
            PlayerInfo(2, "Sb", 200.0, "SB"),
            PlayerInfo(3, "Bb", 200.0, "BB"),
        ],
        dealer_id=1,
    )
    import json
    rows = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    start = next(r for r in rows if r.get("event") == "hand_start")
    hero = next(p for p in start["players"] if p["id"] == 0)
    assert hero["pos"] == "CO" and hero["pos_raw"] == "UTG"
    btn = next(p for p in start["players"] if p["id"] == 1)
    assert btn["pos"] == "BTN" and "pos_raw" not in btn


def test_inferred_positions_are_relabelled_too():
    """Empty PlayerInfo.position falls back to GameState.position_of, whose
    forward 'UTG' label at a 4-handed table must also become 'CO'."""
    api = _api()
    api.new_hand(
        players=[
            PlayerInfo(1, "Btn", 200.0, ""),
            PlayerInfo(2, "Sb", 200.0, ""),
            PlayerInfo(3, "Bb", 200.0, ""),
            PlayerInfo(0, "Hero", 200.0, ""),
        ],
        dealer_id=1,
    )
    assert api._hand_positions == {1: 'BTN', 2: 'SB', 3: 'BB', 0: 'CO'}
    assert api._hand_positions_raw[0] == 'UTG'
