"""Regressions from the 2026-11-07 headless session."""

import pytest

from pf_intercept.bot import BotBridge
from pokerfate.api import PokerFateAPI, PlayerInfo, BotDecision
from pokerfate.bot.poker_bot import PokerBot
from pokerfate.core.card import Card
from pokerfate.core.game_state import Action, ActionType, GameState, Player, Street
from pokerfate.decision.realtime_cfr import (
    RealtimeCFRDecisionContext,
    RealtimeCFRDecisionEngine,
)
from pokerfate.strategy.range_v2 import hand_combo_map as hcm
from pokerfate.strategy.preflop import PreflopStrategy


@pytest.mark.parametrize(
    "posted,raise_to,stack,street",
    [
        (10000, 40000, 945000, 1),  # Hand 3: BB open must add only 3 BB.
        (10000, 35000, 990000, 1),  # Hand 2: BTN with a forced entry blind.
        (5000, 40000, 254950, 1),   # SB open.
        (30000, 120000, 300000, 2), # Postflop re-raise after already betting.
        (30000, 120000, 90000, 3),  # All-in total includes chips already bet.
        (0, 40000, 1000000, 1),    # Unopened street: amount stays unchanged.
    ],
)
def test_raise_to_becomes_added_chips_on_wire(posted, raise_to, stack, street):
    class FakeAPI:
        def request_action(self, **kwargs):
            assert kwargs["my_current_bet_this_street"] == posted
            return BotDecision("raise", raise_to)

    bridge = BotBridge()
    bridge._api = FakeAPI()
    bridge._my_seat = 1
    bridge._stage = street
    bridge._all_seats = [0, 1]
    bridge._hole_cards_count = 2
    bridge._bb = 10000
    bridge._pot = 100000
    bridge._my_chips = stack
    bridge._my_bet = posted
    bridge._street_bets = {1: posted}

    result = bridge._on_action_notify({"seatid": 1, "call_need_chips": 0})
    assert result[0] == "pb.ActionREQ"
    assert result[1] == {"action_type": 4, "chips": raise_to - posted}

    # The server applies chips as an increment, matching the API's raise-to.
    bridge._on_action_brc({
        "seatid": 1,
        "action_type": 4,
        "chips": result[1]["chips"],
        "hand_chips": stack - result[1]["chips"],
    })
    assert bridge._my_bet == raise_to
    assert bridge._my_chips == stack - (raise_to - posted)


@pytest.mark.parametrize("street", ["turn", "river"])
def test_nonstandard_blinds_preserve_physical_order_for_cfr(street):
    hero_id, villain_id, button_id = 10262053, 10482879, 10489861
    api = PokerFateAPI(
        my_player_id=hero_id, big_blind=10000, small_blind=5000,
        autosave_path=None, log_file=None, g5_model_path=None,
        enable_showdown_calibration=False, decision_engine="local",
    )
    # Hand 3: button=3, hero=seat 1/BB, villain=seat 4/UTG+1.
    # Deliberately shuffle players: physical seats, not list order or blind
    # labels, determine which player acts last after the flop.
    api.new_hand([
        PlayerInfo(villain_id, "Villain", 872500, "UTG+1", seat_index=4),
        PlayerInfo(hero_id, "Hero", 827500, "BB", seat_index=1),
        PlayerInfo(button_id, "Button", 2000000, "BTN", seat_index=3),
    ], dealer_id=button_id)
    api.deal_hole_cards(["Kc", "9d"])
    api._get_player(button_id).is_folded = True
    gs = api._build_game_state(
        street=street, pot=310000, current_bet=0,
        my_stack=827500, my_current_bet_this_street=0,
    )
    gs.board = [Card.from_str(c) for c in ["8s", "9h", "7s", "2c"]]
    if street == "river":
        gs.board.append(Card.from_str("8h"))
    gs.action_history = [(villain_id, Action(ActionType.CHECK), street)]
    hero = next(p for p in gs.players if p.player_id == hero_id)
    assert gs.position_of(hero) == "BB"
    assert gs.is_ip(hero)
    assert api._is_player_ip(hero_id)
    assert not api._is_player_ip(villain_id)

    weights = [0.0] * len(hcm.ALL_COMBOS)
    combo = tuple(sorted(hcm.card_to_int(Card.from_str(c)) for c in ("Qs", "Qd")))
    weights[hcm.COMBO_TO_IDX[combo]] = 1.0
    engine = RealtimeCFRDecisionEngine()
    prepared = engine._prepare(RealtimeCFRDecisionContext(
        gs=gs, hero_player_id=hero_id, street_start_pot=310000,
        range_provider=lambda _pid: weights,
    ))
    assert prepared is not None, engine.last_error
    state, meta = prepared
    assert meta["hero_side"] == "ip"
    assert state.prefix == [("check", 0.0)]


@pytest.mark.parametrize("dealer_seat", [3, 5])
def test_physical_order_wraps_at_empty_button(dealer_seat):
    hero, villain = Player(1, "Hero", 100), Player(2, "Villain", 100)
    gs = GameState(
        players=[villain, hero], street=Street.TURN,
        player_positions={1: "BB", 2: "UTG"},
        player_seats={1: 1, 2: 6}, dealer_seat=dealer_seat,
    )
    assert gs.is_ip(hero)
    assert not gs.is_ip(villain)


def test_missing_physical_seat_falls_back_to_explicit_positions():
    hero, villain = Player(1, "Hero", 100), Player(2, "Villain", 100)
    gs = GameState(
        players=[hero, villain], player_positions={1: "BTN", 2: "BB"},
        player_seats={1: 1}, dealer_seat=3,
    )
    assert gs.is_ip(hero)
    assert not gs.is_ip(villain)


@pytest.mark.parametrize("hero_action", [ActionType.RAISE, ActionType.CALL])
@pytest.mark.parametrize("extra", [1000, 2417])
def test_short_allin_only_completes_bet_already_accepted(monkeypatch, hero_action, extra):
    bot = PokerBot(equity_iterations=10)
    hero = Player(1, "Hero", 20879, [Card.from_str(c) for c in ("Th", "As")], current_bet=40000)
    villain = Player(2, "Villain", 0, current_bet=40000 + extra, is_all_in=True)
    players = [hero, villain]
    history = []
    if hero_action == ActionType.CALL:
        players.append(Player(3, "Opener", 960000, current_bet=40000))
        history.append((3, Action(ActionType.RAISE, 40000), "preflop"))
    history += [
        (1, Action(hero_action, 40000), "preflop"),
        (2, Action(ActionType.RAISE, 40000 + extra), "preflop"),
    ]
    gs = GameState(
        players=players, big_blind=10000, small_blind=5000,
        current_bet=40000 + extra, pot=95000 + extra,
        action_history=history, player_positions={1: "CO", 2: "BTN"},
    )

    def no_chart(*args, **kwargs):
        pytest.fail("A short all-in top-up must not enter an opening/raise chart")

    monkeypatch.setattr(bot.preflop, "_greenline_action", no_chart)
    assert bot._classify_preflop_action(gs, hero)[0] == "short_allin"
    action = bot.decide(gs, 1)
    assert action.action_type == ActionType.CALL
    assert action.amount == extra
    assert bot._last_gto_refs is None


def test_short_allin_does_not_skip_an_unanswered_full_raise():
    bot = PokerBot(equity_iterations=10)
    hero = Player(1, "Hero", 960000, current_bet=40000)
    gs = GameState(
        players=[hero, Player(2, "Raiser", 880000), Player(3, "Short", 0, is_all_in=True)],
        big_blind=10000, current_bet=121000,
        action_history=[
            (1, Action(ActionType.RAISE, 40000), "preflop"),
            (2, Action(ActionType.RAISE, 120000), "preflop"),
            (3, Action(ActionType.RAISE, 121000), "preflop"),
        ],
    )
    assert bot._classify_preflop_action(gs, hero) == ("3bet", 120000)


@pytest.mark.parametrize("facing,position,villain,posted,stack,open_raise", [
    ("4bet", "BB", "BTN", 176000, 520550, 512200),  # Hand 368.
    ("3bet", "CO", "BB", 40000, 60000, 90000),
    ("none", "BB", "", 10000, 15000, 0),
])
def test_preflop_allin_amount_includes_existing_bet(facing, position, villain, posted, stack, open_raise):
    strategy = PreflopStrategy()
    action, amount = strategy.decide(
        hole_cards=[Card.from_str(c) for c in ("Ac", "Ad")],
        position=position, villain_position=villain, facing_action=facing,
        open_raise=open_raise, is_ip=False, big_blind=10000,
        stack=stack, current_bet=posted, pot=693200,
        to_call=max(0, open_raise - posted), stack_bb=stack / 10000,
        num_limpers=1 if facing == "none" else 0,
    )
    assert action == "raise"
    assert amount == posted + stack


def test_raise_to_cap_and_call_comparison_use_same_total_units():
    bot = PokerBot(equity_iterations=10)
    action = bot._to_action("raise", 696550, 336200, 520550, current_bet=176000)
    assert action == Action(ActionType.RAISE, 696550)
    # Target 50k is below the 60k call-to, although above the 20k call increment.
    action = bot._to_action("raise", 50000, 20000, 100000, current_bet=40000)
    assert action == Action(ActionType.CALL, 20000)


def _live_api():
    api = PokerFateAPI(
        my_player_id=1, big_blind=10000, small_blind=5000, equity_iterations=10,
        autosave_path=None, log_file=None, g5_model_path=None,
        enable_showdown_calibration=False, decision_engine="local",
    )
    api.new_hand([PlayerInfo(1, "Hero", 1000000, "BB"), PlayerInfo(2, "Villain", 1000000, "BTN")], dealer_id=2)
    api.deal_hole_cards(["Ac", "Ad"])
    return api


def test_postflop_allin_increment_becomes_total_once(monkeypatch):
    api = _live_api()
    api.deal_board(["As", "Kd", "2c"], street="flop", pot=200000)
    monkeypatch.setattr(api._bot.postflop, "decide", lambda **kwargs: ("raise", kwargs["stack"]))
    decision = api.request_action(
        street="flop", pot=200000, current_bet=60000, to_call=30000,
        my_stack=90000, my_current_bet_this_street=30000,
    )
    assert decision.action == "raise"
    assert decision.amount == 120000
    assert api._get_my_player().stack == 0
    assert api._action_history[-1][1] == Action(ActionType.RAISE, 120000)


@pytest.mark.parametrize("source", ["local", "cfr", "book"])
@pytest.mark.parametrize("requested,stack,expected", [(8000, 99311, 10000), (8000, 6000, 6000), (15000, 99311, 15000)])
def test_bet_floor_is_applied_before_recording_and_sending(monkeypatch, source, requested, stack, expected):
    api = _live_api()
    recorded = []
    monkeypatch.setattr(api._log, "decision", lambda **kwargs: recorded.append(kwargs))
    chosen = Action(ActionType.RAISE, requested)
    if source == "local":
        monkeypatch.setattr(api._bot, "decide", lambda *args, **kwargs: chosen)
    else:
        entry = "_decide_with_realtime_cfr" if source == "cfr" else "_decide_with_flop_book"
        monkeypatch.setattr(api, entry, lambda *args, **kwargs: chosen)
        monkeypatch.setattr(api, "_local_shadow_decide", lambda *args, **kwargs: None)
    bridge = BotBridge()
    bridge._api = api
    bridge._my_seat = 1
    bridge._stage = 4
    bridge._all_seats = [0, 1]
    bridge._hole_cards_count = 2
    bridge._bb = 10000
    bridge._pot = 25000
    bridge._my_chips = stack
    result = bridge._on_action_notify({"seatid": 1, "min_chipin": 10000})
    assert result[1] == {"action_type": 4, "chips": expected}
    assert api._action_history[-1][1] == Action(ActionType.RAISE, expected)
    assert api._get_my_player().stack == stack - expected
    assert recorded[-1]["amount"] == expected


@pytest.mark.parametrize("scenario", ["short_topup", "allin"])
def test_live_preflop_request_history_stack_and_wire_agree(scenario):
    api = _live_api()
    if scenario == "short_topup":
        posted, stack, call_need = 40000, 20879, 1000
        api._action_history = [
            (1, Action(ActionType.RAISE, 40000), "preflop"),
            (2, Action(ActionType.RAISE, 41000), "preflop"),
        ]
        expected_action, expected_added, wire_type = ActionType.CALL, 1000, 3
    else:
        # Hand 368: the additional all-in must be all 520550 remaining chips.
        api.deal_hole_cards(["Ad", "Kc"])
        posted, stack, call_need = 176000, 520550, 336200
        api._action_history = [
            (2, Action(ActionType.RAISE, 40000), "preflop"),
            (1, Action(ActionType.RAISE, 176000), "preflop"),
            (2, Action(ActionType.RAISE, 512200), "preflop"),
        ]
        expected_action, expected_added, wire_type = ActionType.RAISE, stack, 4
    villain = api._get_player(2)
    villain.current_bet = posted + call_need
    villain.stack = 0
    villain.is_all_in = True
    bridge = BotBridge()
    bridge._api = api
    bridge._my_seat = 1
    bridge._stage = 1
    bridge._all_seats = [1, 2]
    bridge._hole_cards_count = 2
    bridge._bb = 10000
    bridge._pot = 693200 if scenario == "allin" else 96000
    bridge._my_chips = stack
    bridge._my_bet = posted
    bridge._street_bets = {1: posted, 2: posted + call_need}
    result = bridge._on_action_notify({"seatid": 1, "call_need_chips": call_need})
    assert result[1] == {"action_type": wire_type, "chips": expected_added if wire_type == 4 else 0}
    expected_amount = posted + expected_added if wire_type == 4 else expected_added
    assert api._action_history[-1][1] == Action(expected_action, expected_amount)
    assert api._get_my_player().current_bet == posted + expected_added
    assert api._get_my_player().stack == stack - expected_added


def test_unseated_button_keeps_physical_order():
    """Hand 448: button on empty seat 3, hero seat 1 posts SB and acts first postflop."""
    bridge = BotBridge()
    bridge._all_seats = [1, 2]
    bridge._seat_uids = {1: 10262053, 2: 10332601, 3: 10572508}  # stale uid on the dead button
    assert bridge._dealer_player_id(3) == -4
    assert bridge._dealer_player_id(1) == 10262053

    api = PokerFateAPI(
        my_player_id=10262053, big_blind=10000, small_blind=5000,
        autosave_path=None, log_file=None, g5_model_path=None,
        enable_showdown_calibration=False, decision_engine="local",
    )
    api.new_hand([
        PlayerInfo(10262053, "Hero", 805780, "BTN", seat_index=1),
        PlayerInfo(10332601, "Villain", 510235, "BB", seat_index=2),
    ], dealer_id=-4)
    assert api._dealer_seat_index == 3
    assert not api._is_player_ip(10262053)
    assert api._is_player_ip(10332601)


def test_bb_behind_limpers_checks_instead_of_recording_a_call():
    """Hands 36/149/698: to_call=0 behind limpers must be a check, not a call."""
    strategy = PreflopStrategy()
    action, amount = strategy.decide(
        hole_cards=[Card.from_str(c) for c in ("5h", "5c")],
        position="BB", facing_action="none", open_raise=0.0, is_ip=False,
        big_blind=10000, stack=1030000, pot=30000, is_big_blind=True,
        num_limpers=2, to_call=0.0, stack_bb=103.0,
    )
    assert action in ("check", "raise")
    if action == "check":
        assert amount == 0.0
        assert "free_check_option" in strategy.last_expand_reason
    # A genuine limp behind (to_call > 0) is still a call of exactly to_call.
    action, amount = strategy.decide(
        hole_cards=[Card.from_str(c) for c in ("5h", "5c")],
        position="CO", facing_action="none", open_raise=0.0, is_ip=True,
        big_blind=10000, stack=1030000, pot=25000,
        num_limpers=2, to_call=10000.0, stack_bb=103.0,
    )
    assert action in ("call", "raise")
    if action == "call":
        assert amount == 10000.0
