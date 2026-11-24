"""Chip amounts on the wire, and seat order through the API."""

import pytest

from pf_intercept.bot import BotBridge
from pokerfate.api import PokerFateAPI, PlayerInfo, BotDecision
from pokerfate.bot.poker_bot import PokerBot
from pokerfate.core.card import Card
from pokerfate.core.game_state import Action, ActionType, GameState, Player, Street
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


@pytest.mark.parametrize("positions, seats, dealer_seat, ip_id, oop_id", [
    # physical seats decide who acts last, wrapping past an empty dealer seat
    ({1: "BB", 2: "UTG"}, {1: 1, 2: 6}, 3, 1, 2),
    ({1: "BB", 2: "UTG"}, {1: 1, 2: 6}, 5, 1, 2),
    # a player without a seat number: the labels decide
    ({1: "BTN", 2: "BB"}, {1: 1}, 3, 1, 2),
])
def test_game_state_ip_follows_physical_seats(positions, seats, dealer_seat, ip_id, oop_id):
    players = [Player(pid, f"P{pid}", 100) for pid in sorted(positions, reverse=True)]
    gs = GameState(players=players, street=Street.TURN, player_positions=positions,
                   player_seats=seats, dealer_seat=dealer_seat)
    by_id = {p.player_id: p for p in players}
    assert gs.is_ip(by_id[ip_id]) and not gs.is_ip(by_id[oop_id])


@pytest.mark.parametrize("seats, dealer_id, folded, positions, ip_id, oop_id", [
    # labels given, list order shuffled: the seats decide who is in position
    ([(3, "UTG+1", 4), (1, "BB", 1), (9, "BTN", 3)], 9, [9], None, 1, 3),
    # dealer chip on an empty seat (dealer_id -4 = seat 3), blind battle
    ([(1, "SB", 1), (2, "BB", 2)], -4, [], {1: "SB", 2: "BB"}, 2, 1),
    # no labels: derived from the seats and the empty dealer seat
    ([(1, "", 0), (2, "", 1), (3, "", 2), (4, "", 4), (5, "", 5)], -4, [],
     {1: "MP", 2: "CO", 3: "BTN", 4: "SB", 5: "BB"}, 3, 1),
])
def test_api_positions_and_ip_from_seats(seats, dealer_id, folded, positions, ip_id, oop_id):
    # hero is player 1 in every row
    api = PokerFateAPI(
        my_player_id=1, big_blind=10000, small_blind=5000,
        autosave_path=None, log_file=None,
        enable_showdown_calibration=False, decision_engine="rule_engine",
    )
    api.new_hand([PlayerInfo(pid, f"P{pid}", 1_000_000, label, seat_index=seat) for pid, label, seat in seats],
                 dealer_id=dealer_id)
    for pid in folded:
        api._get_player(pid).is_folded = True
    if positions is not None:
        assert api._hand_positions == positions
    assert api._is_player_ip(ip_id) and not api._is_player_ip(oop_id)


@pytest.mark.parametrize("seat, expected", [(1, 10262053), (3, -4)])
def test_dealer_player_id_is_the_seated_uid_or_minus_seat_plus_one(seat, expected):
    bridge = BotBridge()
    bridge._all_seats = [1, 2]
    bridge._seat_uids = {1: 10262053, 2: 10332601, 3: 10572508}  # stale uid on the empty dealer seat
    assert bridge._dealer_player_id(seat) == expected


@pytest.mark.parametrize("hero_action", [ActionType.RAISE, ActionType.CALL])
@pytest.mark.parametrize("extra", [1000, 2417])
def test_short_allin_only_completes_bet_already_accepted(monkeypatch, hero_action, extra):
    bot = PokerBot(equity_iterations=10)
    hero = Player(1, "Hero", 20879, [Card.from_str(c) for c in ("Th", "As")], current_bet=40000)
    villain = Player(2, "Villain", 0, current_bet=40000 + extra)
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
        players=[hero, Player(2, "Raiser", 880000), Player(3, "Short", 0)],
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
        autosave_path=None, log_file=None,
        enable_showdown_calibration=False, decision_engine="rule_engine",
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


@pytest.mark.parametrize("source", ["rule_engine", "cfr", "book"])
@pytest.mark.parametrize("requested,stack,notify,wire,recorded_action", [
    # a raise below the table's minimum becomes the minimum, or the all-in when the stack is shorter
    (8000, 99311, {"min_chipin": 10000}, {"action_type": 4, "chips": 10000}, Action(ActionType.RAISE, 10000)),
    (8000, 6000, {"min_chipin": 10000}, {"action_type": 4, "chips": 6000}, Action(ActionType.RAISE, 6000)),
    (40000, 99311, {"call_need_chips": 30000, "min_chipin": 60000}, {"action_type": 4, "chips": 60000}, Action(ActionType.RAISE, 60000)),
    # inside the range it goes out as asked
    (15000, 99311, {"min_chipin": 10000}, {"action_type": 4, "chips": 15000}, Action(ActionType.RAISE, 15000)),
    # the table accepts no raise: call
    (90000, 99311, {"call_need_chips": 30000}, {"action_type": 3, "chips": 0}, Action(ActionType.CALL, 30000)),
])
def test_raise_is_made_legal_before_recording_and_sending(monkeypatch, source, requested, stack, notify, wire, recorded_action):
    api = _live_api()
    recorded = []
    monkeypatch.setattr(api._log, "decision", lambda **kwargs: recorded.append(kwargs))
    chosen = Action(ActionType.RAISE, requested)
    if source == "rule_engine":
        monkeypatch.setattr(api._bot, "decide", lambda *args, **kwargs: chosen)
    else:
        entry = "_decide_with_realtime_cfr" if source == "cfr" else "_decide_with_flop_book"
        monkeypatch.setattr(api, entry, lambda *args, **kwargs: chosen)
        monkeypatch.setattr(api, "_rule_engine_shadow_decide", lambda *args, **kwargs: None)
    bridge = BotBridge()
    bridge._api = api
    bridge._my_seat = 1
    bridge._stage = 4
    bridge._all_seats = [0, 1]
    bridge._hole_cards_count = 2
    bridge._bb = 10000
    bridge._pot = 25000
    bridge._my_chips = stack
    result = bridge._on_action_notify({"seatid": 1, **notify})
    assert result[1] == wire
    assert api._action_history[-1][1] == recorded_action
    assert api._get_my_player().stack == stack - recorded_action.amount
    assert recorded[-1]["action"] == str(recorded_action.action_type)


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



@pytest.mark.parametrize("stack,folded,all_in,can_act", [
    (500, False, False, True),
    (0, False, True, False),
    (0, True, False, False),
    (500, True, False, False),
])
def test_player_is_all_in_when_in_the_hand_without_chips(stack, folded, all_in, can_act):
    player = Player(1, "P", stack, is_folded=folded)
    assert (player.is_all_in, player.can_act()) == (all_in, can_act)


@pytest.mark.parametrize("min_raise_to,stack,posted,current_bet,opponent_stack,amount,expected", [
    # the table states its minimum: below it → the minimum, inside → as asked, above the stack → all-in
    (625800, 1763757, 0, 312900, 20000, 332900, 625800),
    (625800, 1763757, 0, 312900, 20000, 900000, 900000),
    (625800, 1763757, 0, 312900, 20000, 5000000, 1763757),
    # a stack short of the minimum can still go all-in, with what is already in front counted in
    (848400, 520550, 176000, 512200, 900000, 520550, 696550),
    # the table accepts no raise
    (0, 1763757, 0, 312900, 900000, 900000, None),
    # the table did not say: one big blind at least, and somebody must be left who can call
    (None, 99311, 0, 0, 900000, 8000, 10000),
    (None, 99311, 0, 30000, 0, 90000, None),
    # all-in does not top the bet: no raise either way
    (None, 20000, 0, 30000, 900000, 90000, None),
    (60000, 20000, 0, 30000, 900000, 90000, None),
])
def test_legal_raise_to(min_raise_to, stack, posted, current_bet, opponent_stack, amount, expected):
    hero = Player(1, "Hero", stack, current_bet=posted)
    gs = GameState(
        players=[hero, Player(2, "Villain", opponent_stack, current_bet=current_bet)],
        big_blind=10000, current_bet=current_bet, min_raise_to=min_raise_to,
    )
    assert gs.legal_raise_to(hero, amount) == expected


class _RecordingAPI:
    def __init__(self):
        self.events = []
        self.requests = []

    def notify_action(self, event):
        self.events.append(event)

    def request_action(self, **kwargs):
        self.requests.append(kwargs)
        return BotDecision("fold", 0.0)


@pytest.mark.parametrize("chips,hand_chips,action,amount", [
    (50000, 0, "raise", 90000),       # tops the 60000 in front of the other seat
    (20000, 0, "call", 20000),        # stops at the 60000: a call for what it adds
    (10000, 0, "call", 10000),        # falls short of it: still a call
])
def test_all_in_reaches_the_api_as_raise_only_when_it_tops_the_bet(chips, hand_chips, action, amount):
    bridge = BotBridge()
    bridge._api = _RecordingAPI()
    bridge._my_seat = 1
    bridge._stage = 2
    bridge._street_bets = {1: 60000, 2: 40000}
    bridge._on_action_brc({"seatid": 2, "action_type": 17, "chips": chips, "hand_chips": hand_chips})
    event = bridge._api.events[-1]
    assert (event.action, event.amount, event.stack_after) == (action, amount, hand_chips)


@pytest.mark.parametrize("posted,notify,min_raise_to", [
    (10000, {"call_need_chips": 10000, "min_chipin": 30000}, 40000),
    (0, {"min_chipin": 20000}, 20000),
    (120000, {"call_need_chips": 30000}, 0),
])
def test_table_minimum_raise_reaches_the_api_as_a_raise_to_total(posted, notify, min_raise_to):
    bridge = BotBridge()
    bridge._api = _RecordingAPI()
    bridge._my_seat = 1
    bridge._stage = 1
    bridge._all_seats = [0, 1]
    bridge._hole_cards_count = 2
    bridge._bb = 10000
    bridge._my_chips = 500000
    bridge._my_bet = posted
    bridge._on_action_notify({"seatid": 1, **notify})
    assert bridge._api.requests[-1]["min_raise_to"] == min_raise_to


@pytest.mark.parametrize("event,stack,current_bet", [
    # the table's stack replaces the one worked out from the chips (the villain had posted a blind)
    (dict(action="call", amount=20000, stack_after=970000), 970000, 30000),
    (dict(action="check", stack_after=990000), 990000, 0),
    # an all-in call may fall short of the bet; a call that leaves chips behind matched it
    (dict(action="call", amount=20000, stack_after=0), 0, 20000),
    # no stack from the table: the previous one less the chips added
    (dict(action="call", amount=30000), 970000, 30000),
    (dict(action="raise", amount=90000), 910000, 90000),
])
def test_opponent_action_books_the_stack_the_table_reports(event, stack, current_bet):
    from pokerfate.api import ActionEvent
    api = _live_api()
    api._get_my_player().current_bet = 30000  # the bet on the table
    api.notify_action(ActionEvent(player_id=2, street="preflop", **event))
    villain = api._get_player(2)
    assert (villain.stack, villain.current_bet) == (stack, current_bet)
