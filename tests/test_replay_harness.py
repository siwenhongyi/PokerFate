"""scripts.replay_and_compare must feed the bot the same table state the live
bridge does: hero's posted blind is part of my_current_bet_this_street, the
preflop table bet starts at bb, and logged call amounts are chips added."""

from __future__ import annotations

from scripts.replay_and_compare import _replay_hand


class _Decision:
    def __init__(self, action: str, amount: float = 0.0):
        self.action = action
        self.amount = amount


class _FakeBot:
    def __init__(self):
        self._my_street_actions = {}


class _FakeAPI:
    def __init__(self, decision=("check", 0.0)):
        self.calls = []
        self._action_history = []
        self._street_contribs = {}
        self._bot = _FakeBot()
        self._decision = decision

    def new_hand(self, players, dealer_id):
        pass

    def deal_hole_cards(self, cards):
        pass

    def deal_board(self, cards, street):
        pass

    def notify_action(self, event):
        pass

    def request_action(self, **kw):
        self.calls.append(kw)
        return _Decision(*self._decision)

    def last_decision_diagnostics(self):
        return {}

    def _get_player(self, pid):
        return None

    def hand_over(self, **kw):
        pass


def _hand(hero_pos: str, events: list, bb: float = 10.0):
    players = [
        {"id": 1, "name": "hero", "stack": 100 * bb, "pos": hero_pos},
        {"id": 2, "name": "v1", "stack": 100 * bb, "pos": "BTN" if hero_pos != "BTN" else "CO"},
        {"id": 3, "name": "v2", "stack": 100 * bb, "pos": "SB" if hero_pos != "SB" else "BB"},
    ]
    return {
        "hand": 1, "session": 1, "big_blind": bb, "dealer_id": 2, "players": players,
        "hole_cards": ["Ah", "Kh"], "events": events,
        "result": {"winners": [], "pot": 0, "my_delta": 0, "final_stacks": {}, "showdown_hands": {}},
    }


def test_bb_free_check_sees_posted_blind_and_zero_to_call():
    bb = 10.0
    api = _FakeAPI(decision=("check", 0.0))
    hand = _hand("BB", [
        {"type": "opp_action", "pid": 2, "action": "call", "amount": bb, "street": "preflop"},
        {"type": "opp_action", "pid": 3, "action": "call", "amount": bb, "street": "preflop"},
        {"type": "decision", "street": "preflop", "pot": 3 * bb, "to_call": 0.0, "action": "check", "amount": 0.0},
    ])
    _replay_hand(api, hand, hero_id=1)
    kw = api.calls[0]
    assert kw["my_current_bet_this_street"] == bb          # posted big blind
    assert kw["current_bet"] == bb
    assert kw["my_stack"] == 100 * bb - bb                 # hand_start stacks are pre-blind
    assert kw["is_bb_option"] is True


def test_first_to_act_faces_the_big_blind():
    bb = 10.0
    api = _FakeAPI(decision=("fold", 0.0))
    hand = _hand("UTG", [
        {"type": "decision", "street": "preflop", "pot": 1.5 * bb, "to_call": bb, "action": "fold", "amount": 0.0},
    ])
    _replay_hand(api, hand, hero_id=1)
    kw = api.calls[0]
    assert kw["my_current_bet_this_street"] == 0.0
    assert kw["current_bet"] == bb                          # not a phantom free check
    assert kw["my_stack"] == 100 * bb
    assert kw["is_bb_option"] is False


def test_bb_defend_call_amount_is_chips_added():
    bb = 10.0
    api = _FakeAPI(decision=("call", 0.0))
    hand = _hand("BB", [
        {"type": "opp_action", "pid": 2, "action": "raise", "amount": 2.5 * bb, "street": "preflop"},
        {"type": "opp_action", "pid": 3, "action": "fold", "amount": 0.0, "street": "preflop"},
        # logged call amount = chips added (1.5bb), hero already has 1bb posted
        {"type": "decision", "street": "preflop", "pot": 4 * bb, "to_call": 1.5 * bb, "action": "call", "amount": 1.5 * bb},
        {"type": "board", "street": "flop", "cards": ["2c", "7d", "Jh"]},
        {"type": "opp_action", "pid": 2, "action": "check", "amount": 0.0, "street": "flop"},
        {"type": "decision", "street": "flop", "pot": 5 * bb, "to_call": 0.0, "action": "check", "amount": 0.0},
    ])
    _replay_hand(api, hand, hero_id=1)
    pf, flop = api.calls
    assert pf["my_current_bet_this_street"] == bb
    assert pf["current_bet"] == 2.5 * bb
    assert pf["my_stack"] == 100 * bb - bb
    # After calling 1.5bb more, hero has 2.5bb in and a 97.5bb stack on the flop.
    assert flop["my_stack"] == 100 * bb - 2.5 * bb
    assert flop["my_current_bet_this_street"] == 0.0
