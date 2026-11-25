"""pf_intercept BotBridge: profit-lock leave / re-enter, bust rebuys and the net-loss cap."""

import threading

import pytest

from pf_intercept import config
from pf_intercept.bot import BotBridge
from pokerfate.api import BotDecision
from pokerfate.bot.opponent_model import OpponentModel, OpponentStats


def _recoverable_bridge():
    b = BotBridge(max_auto_rebuy=5)
    b._auto_rebuy_done = 2
    b._table_room_id = 21205174
    b._current_gameid = "last-hand"
    b._my_seat = 3
    b._my_chips = 952600
    b._seat_chips = {3: 952600}
    b.configure_auto_rejoin({"boot": 10000, "game_type": 10010101,
                            "lobby_coin": 10100001, "byin_chips": 1000000,
                            "wait_blind": False, "ip": ""})
    return b


def test_server_kick_rejoins_without_changing_rebuy_budget(monkeypatch):
    b = _recoverable_bridge()
    monkeypatch.setattr(b, "_runtime_calibration_should_pause_play", lambda: None)
    guard = b.injection_guard_for(("pb.ActionREQ", {}))
    sample = b.handle("pb.LeaveRoomRSP", {"roomid": 21205174})
    assert sample[0] == "pb.UserValueREQ"
    assert b.room_id_for_c2s(0) == 0
    assert not b.injection_guard_is_current(guard)
    assert b._current_table_chips() == 0
    # A duplicate leave must not schedule a second entry.
    assert b.handle("pb.LeaveRoomRSP", {"roomid": 21205174}) is None
    rejoin = b.handle("pb.UserValueRSP", {"type": 10100001, "value": "105363439"})
    assert rejoin[0] == "pb.QuickStartREQ"
    assert rejoin[1]["boot"] == 10000 and rejoin[1]["byin_chips"] == 1000000
    assert (b._auto_rebuy_done, b._max_auto_rebuy) == (2, 5)
    assert b._bankroll_profit_lock_count == 0
    assert b.handle("pb.UserValueRSP", {"type": 10100001, "value": "105363439"}) is None


@pytest.mark.parametrize("reason", ["stop", "bust", "friend", "backpressure", "disabled", "failed"])
def test_leave_recovery_does_not_override_intent_or_budget(monkeypatch, reason):
    b = _recoverable_bridge()
    monkeypatch.setattr(b, "_runtime_calibration_should_pause_play", lambda: None)
    if reason == "stop":
        b.stop_auto_rejoin()
    elif reason == "bust":
        b._seat_chips[3] = b._my_chips = 0
    elif reason == "friend":
        b._is_friend_room = True
    elif reason == "backpressure":
        b._calibration_backpressure_leaving = True
    elif reason == "disabled":
        b._auto_rejoin_fields = None
    b.handle("pb.LeaveRoomRSP", {"code": 121} if reason == "failed" else {})
    result = b.handle("pb.UserValueRSP", {"type": 10100001, "value": "105363439"})
    assert result is None
    assert (b._auto_rebuy_done, b._max_auto_rebuy) == (2, 5)


def test_shutdown_after_leave_before_wallet_cancels_rejoin(monkeypatch):
    b = _recoverable_bridge()
    monkeypatch.setattr(b, "_runtime_calibration_should_pause_play", lambda: None)
    b.handle("pb.LeaveRoomRSP", {})
    b.stop_auto_rejoin()
    assert b.handle("pb.UserValueRSP", {"type": 10100001, "value": "105363439"}) is None


def test_seat_move_keeps_models_for_same_uid():
    from types import SimpleNamespace
    b = BotBridge()
    b._my_uid = "42"
    b._my_seat = 3
    api = SimpleNamespace(my_player_id=42)
    b._api = api
    b._set_my_seat(2, "rejoin")
    assert b._my_seat == 2
    assert b._api is api


@pytest.fixture(autouse=True)
def _isolate_pushes(monkeypatch):
    # Game HTTP is isolated for every test file in conftest.py.
    import pf_intercept.bot as bot_mod
    monkeypatch.setattr(bot_mod, "notify", lambda *args, **kwargs: None)


class TestBotBridgeActionAmounts:
    class _FakeAPI:
        def __init__(self):
            self.events = []

        def notify_action(self, event):
            self.events.append(event)

    def test_opponent_raise_amount_sent_to_api_as_street_total(self):
        b = BotBridge()
        b._api = self._FakeAPI()
        b._stage = 1
        b._my_seat = 0

        b._on_action_brc({"seatid": 1, "action_type": 4, "chips": 6, "hand_chips": 194})
        b._on_action_brc({"seatid": 1, "action_type": 4, "chips": 12, "hand_chips": 182})

        assert b._api.events[0].amount == 6
        assert b._api.events[1].amount == 18

    def test_opponent_call_amount_sent_to_api_as_added_chips(self):
        b = BotBridge()
        b._api = self._FakeAPI()
        b._stage = 1
        b._my_seat = 0

        b._on_action_brc({"seatid": 2, "action_type": 3, "chips": 6, "hand_chips": 194})

        assert b._api.events[0].action == "call"
        assert b._api.events[0].amount == 6

    def test_opponent_action_uses_uid_not_seat_id(self):
        b = BotBridge()
        b._api = self._FakeAPI()
        b._stage = 1
        b._my_seat = 0
        b._seat_uids = {2: "123456"}

        b._on_action_brc({"seatid": 2, "action_type": 3, "chips": 6, "hand_chips": 194})

        assert b._api.events[0].player_id == 123456

    def test_opponent_action_without_uid_uses_negative_runtime_id(self):
        b = BotBridge()
        b._api = self._FakeAPI()
        b._stage = 1
        b._my_seat = 0

        b._on_action_brc({"seatid": 2, "action_type": 3, "chips": 6, "hand_chips": 194})

        assert b._api.events[0].player_id == -3


def test_action_notify_duplicate_is_suppressed_until_table_advances() -> None:
    class FakeAPI:
        def __init__(self):
            self.request_count = 0
            self.events = []

        def request_action(self, **kwargs):
            self.request_count += 1
            return BotDecision("raise", 50000.0)

        def notify_action(self, event):
            self.events.append(event)

    b = BotBridge()
    b._api = FakeAPI()
    b._my_seat = 0
    b._stage = 3
    b._current_gameid = "g42"
    b._all_seats = [0, 1]
    b._hole_cards_count = 2
    b._bb = 10000
    b._pot = 100000
    b._my_chips = 800000

    notify = {
        "seatid": 0,
        "call_need_chips": 0,
        "min_chipin": 20000,
        "max_chipin": 800000,
    }

    first = b._on_action_notify(dict(notify))
    assert first is not None
    assert b._api.request_count == 1

    assert b._on_action_notify(dict(notify)) is None
    assert b._api.request_count == 1

    b._on_action_brc({
        "seatid": 0,
        "action_type": 4,
        "chips": 50000,
        "hand_chips": 750000,
    })

    assert b._on_action_notify(dict(notify)) is None
    assert b._api.request_count == 1

    b._on_action_brc({
        "seatid": 1,
        "action_type": 3,
        "chips": 50000,
        "hand_chips": 750000,
    })

    next_turn = b._on_action_notify(dict(notify))
    assert next_turn is not None
    assert b._api.request_count == 2


def test_dealer_info_passes_global_hand_seq_to_api(monkeypatch) -> None:
    calls = []

    class FakeAPI:
        def new_hand(self, **kwargs):
            calls.append(kwargs)

    b = BotBridge()
    b._api = FakeAPI()
    b._hand_seq = 41
    monkeypatch.setattr(b, "_ensure_api", lambda: True)

    b._on_dealer_info(
        {
            "dealer": 0,
            "start_info": [{"seatid": 0, "chips": 200}],
            "gameid": "t42",
        }
    )

    assert calls[0]["hand_number"] == 42


class TestBotBridgeReconnectRestore:
    class _FakeAPI:
        def __init__(self):
            self.hole_cards = []
            self.requests = []
            self.hands = []

        def new_hand(self, **kwargs):
            self.hands.append(kwargs)

        def deal_hole_cards(self, cards):
            self.hole_cards.append(cards)

        def request_action(self, **kwargs):
            self.requests.append(kwargs)
            return BotDecision(action="call", amount=0.0)

        def last_decision_diagnostics(self):
            return {}

        def set_runtime_collection_enabled(self, enabled, reason=""):
            pass

    def _bridge(self):
        fake = self._FakeAPI()
        b = BotBridge()
        b._api = fake
        b._my_uid = "99"
        b._my_seat = 0
        b._bb = 10.0
        b._sb = 5.0
        return b, fake

    def test_enter_room_rsp_replays_pending_hero_action_after_reconnect(self, caplog) -> None:
        b, fake = self._bridge()

        with caplog.at_level("WARNING"):
            out = b.handle(
                "pb.EnterRoomRSP",
                {
                    "code": 0,
                    "roomid": 123,
                    "game_type": 10010101,
                    "room_info": {"bb": "10", "sb": "5"},
                    "table_status": {
                        "is_playing": True,
                        "action_idx": 0,
                        "stage": 1,
                        "gameid": "game-1",
                        "seat": [
                            {
                                "seatid": 0,
                                "action_type": 5,
                                "player": {"uid": "99", "name": "Hero"},
                                "hand_chips": "990",
                                "destop_chips": "10",
                            },
                            {
                                "seatid": 1,
                                "action_type": 4,
                                "player": {"uid": "100", "name": "Villain"},
                                "hand_chips": "970",
                                "destop_chips": "30",
                            },
                        ],
                    },
                    "playing_status": {
                        "card1": 782,
                        "card2": 1037,
                        "action_seatid": 0,
                        "call_need_chips": "20",
                        "min_chipin": "40",
                        "max_chipin": "990",
                        "action_time": 3,
                    },
                },
            )

        assert out[0] == "pb.ActionREQ"
        assert out[1] == {"action_type": 3, "chips": 0}
        assert out[2] <= 2.0
        assert fake.hole_cards == [["Ah", "Ks"]]
        assert fake.requests[0]["to_call"] == 20
        assert fake.requests[0]["current_bet"] == 30
        assert not any("重连恢复" in r.message for r in caplog.records)

    def test_enter_room_rsp_does_not_replay_when_hero_already_all_in(self) -> None:
        b, fake = self._bridge()
        b._hole_cards_count = 2

        out = b.handle(
            "pb.EnterRoomRSP",
            {
                "code": 0,
                "roomid": 123,
                "game_type": 10010101,
                "room_info": {"bb": "10", "sb": "5"},
                "table_status": {
                    "is_playing": True,
                    "action_idx": 0,
                    "stage": 1,
                    "seat": [
                        {
                            "seatid": 0,
                            "action_type": 17,
                            "is_allin": True,
                            "player": {"uid": "99", "name": "Hero"},
                            "destop_chips": "1000",
                        }
                    ],
                },
                "playing_status": {
                    "action_seatid": 0,
                    "call_need_chips": "20",
                    "action_time": 3,
                },
            },
        )

        assert out is None
        assert fake.requests == []

    def test_enter_room_rsp_does_not_duplicate_recent_action_notify(self) -> None:
        b, fake = self._bridge()
        b._hole_cards_count = 2
        b._current_gameid = "game-dup"
        b._stage = 4
        b._pot = 150000
        b._my_chips = 627881
        b._all_seats = [0, 1]

        first = b.handle(
            "pb.ActionNotifyBRC",
            {
                "seatid": 0,
                "call_need_chips": "50000",
                "min_chipin": "100000",
                "max_chipin": "627881",
            },
        )
        second = b.handle(
            "pb.EnterRoomRSP",
            {
                "code": 0,
                "roomid": 123,
                "game_type": 10010101,
                "room_info": {"bb": "10", "sb": "5"},
                "table_status": {
                    "is_playing": True,
                    "action_idx": 0,
                    "stage": 4,
                    "gameid": "game-dup",
                    "pool": ["150000"],
                    "seat": [
                        {
                            "seatid": 0,
                            "action_type": 5,
                            "player": {"uid": "99", "name": "Hero"},
                            "hand_chips": "627881",
                        },
                        {
                            "seatid": 1,
                            "action_type": 5,
                            "player": {"uid": "100", "name": "Villain"},
                            "hand_chips": "1408650",
                        },
                    ],
                },
                "playing_status": {
                    "card1": 1028,
                    "card2": 781,
                    "action_seatid": 0,
                    "call_need_chips": "50000",
                    "min_chipin": "100000",
                    "max_chipin": "627881",
                    "action_time": 15,
                },
            },
        )

        assert first[0] == "pb.ActionREQ"
        assert second is None
        assert len(fake.requests) == 1

    def test_enter_room_rsp_ignores_stale_playing_status_after_hand_end(self) -> None:
        b, fake = self._bridge()
        b._current_gameid = "old-hand"

        out = b.handle(
            "pb.EnterRoomRSP",
            {
                "code": 0,
                "roomid": 123,
                "game_type": 10010101,
                "room_info": {"bb": "10", "sb": "5"},
                "table_status": {
                    "action_idx": -1,
                    "gameid": "old-hand",
                    "seat": [
                        {
                            "seatid": 0,
                            "action_type": 5,
                            "player": {"uid": "99", "name": "Hero"},
                            "hand_chips": "1747862",
                        }
                    ],
                },
                "playing_status": {
                    "card1": 1034,
                    "card2": 259,
                    "action_seatid": 0,
                    "call_need_chips": "41620",
                    "max_chipin": "1789482",
                },
            },
        )

        assert out is None
        assert fake.hole_cards == []
        assert fake.requests == []

    def test_enter_room_rsp_rebuilds_hand_when_gameid_changed_before_restore(self) -> None:
        b, fake = self._bridge()
        b._current_gameid = "old-hand"
        b._hole_cards_count = 2
        b._robots.confirm("100", "robot", "test")

        out = b.handle(
            "pb.EnterRoomRSP",
            {
                "code": 0,
                "roomid": 123,
                "game_type": 10010101,
                "room_info": {"bb": "10", "sb": "5"},
                "table_status": {
                    "is_playing": True,
                    "action_idx": 0,
                    "d_idx": 2,
                    "stage": 1,
                    "gameid": "new-hand",
                    "seat": [
                        {
                            "seatid": 0,
                            "action_type": 5,
                            "player": {"uid": "99", "name": "Hero"},
                            "hand_chips": "1000",
                        },
                        {
                            "seatid": 1,
                            "action_type": 0,
                            "player": {"uid": "-1"},
                            "hand_chips": "0",
                        },
                        {
                            "seatid": 2,
                            "action_type": 5,
                            "player": {"uid": "100", "name": "Villain"},
                            "hand_chips": "1000",
                        },
                    ],
                },
                "playing_status": {
                    "card1": 782,
                    "card2": 1037,
                    "action_seatid": 0,
                    "call_need_chips": "10",
                    "min_chipin": "20",
                    "max_chipin": "1000",
                    "action_time": 3,
                },
            },
        )

        assert out[0] == "pb.ActionREQ"
        assert fake.hands
        assert len(fake.hands[0]["players"]) == 2
        # a hand joined in the middle marks house robots like one seen from the deal
        assert [p.is_robot for p in fake.hands[0]["players"]] == [False, True]
        assert fake.hole_cards == [["Ah", "Ks"]]
        assert fake.requests[0]["to_call"] == 10

    def test_action_inject_guard_rejects_stale_hand(self) -> None:
        b, _fake = self._bridge()
        b._current_gameid = "game-1"
        b._hand_seq = 7

        guard = b.injection_guard_for(("pb.ActionREQ", {"action_type": 2}, 1.0))

        assert guard == ("game-1", 7)
        assert b.injection_guard_is_current(guard)
        b._current_gameid = "game-2"
        assert not b.injection_guard_is_current(guard)
        assert b.injection_guard_for(("pb.ShowMyCardREQ", {"pos": 1}, 0.0)) is None


def test_dealer_info_passes_positions_to_api(monkeypatch) -> None:
    calls = []

    class FakeAPI:
        def new_hand(self, **kwargs):
            calls.append(kwargs)

    b = BotBridge()
    b._api = FakeAPI()
    b._my_seat = 0
    b._seat_uids = {0: "100", 2: "200", 5: "500"}
    monkeypatch.setattr(b, "_ensure_api", lambda: True)

    b._on_dealer_info(
        {
            "dealer": 2,
            "start_info": [
                {"seatid": 5, "chips": 200},
                {"seatid": 0, "chips": 200},
                {"seatid": 2, "chips": 200},
            ],
            "gameid": "pos1",
        }
    )

    positions = {p.player_id: p.position for p in calls[0]["players"]}
    seat_indices = {p.player_id: p.seat_index for p in calls[0]["players"]}
    assert calls[0]["dealer_id"] == 200
    assert positions == {
        100: "BB",
        200: "BTN",
        500: "SB",
    }
    assert seat_indices == {100: 0, 200: 2, 500: 5}


def test_dealer_info_uses_server_blind_seats_for_positions(monkeypatch) -> None:
    calls = []

    class FakeAPI:
        def new_hand(self, **kwargs):
            calls.append(kwargs)

    b = BotBridge()
    b._api = FakeAPI()
    b._my_seat = 2
    b._seat_uids = {
        0: "10523070",
        1: "10671762",
        2: "10262053",
        3: "10754527",
        4: "10473646",
    }
    monkeypatch.setattr(b, "_ensure_api", lambda: True)

    b._on_dealer_info(
        {
            "dealer": 1,
            "small_blind": 3,
            "big_blind": 4,
            "start_info": [
                {"seatid": 3, "chips": 127194},
                {"seatid": 4, "chips": 24539},
                {"chips": 28647},
                {"seatid": 1, "chips": 83264},
                {"seatid": 2, "chips": 100000},
            ],
            "gameid": "force-bb-layout",
        }
    )

    positions = {p.player_id: p.position for p in calls[0]["players"]}
    seat_indices = {p.player_id: p.seat_index for p in calls[0]["players"]}
    assert positions[10671762] == "BTN"
    assert positions[10754527] == "SB"
    assert positions[10473646] == "BB"
    # seat 0 has four seats behind it before the flop; hero in seat 2 sits
    # between the dealer and the small blind (he posted to play at once)
    assert positions[10523070] == "MP"
    assert positions[10262053] == "CO"
    assert seat_indices[10523070] == 0
    assert seat_indices[10671762] == 1
    assert seat_indices[10262053] == 2
    assert seat_indices[10754527] == 3
    assert seat_indices[10473646] == 4
    assert not getattr(b._api, "disabled_reason", "")


def test_dealer_info_empty_dealer_seat_labels_by_action_order(monkeypatch) -> None:
    """2026-11-18 hand 343: the dealer chip was on empty seat 3 and hero, first to
    act in seat 0, was labelled BTN (lowest seat number) and opened A7o."""
    calls = []

    class FakeAPI:
        def new_hand(self, **kwargs):
            calls.append(kwargs)

    b = BotBridge()
    b._api = FakeAPI()
    b._my_seat = 0
    b._seat_uids = {0: "10262053", 1: "10201582", 2: "10637554", 3: "10999999", 4: "10547857", 5: "10583348"}
    monkeypatch.setattr(b, "_ensure_api", lambda: True)

    b._on_dealer_info(
        {
            "dealer": 3,
            "small_blind": 4,
            "big_blind": 5,
            "start_info": [
                {"seatid": 4, "chips": 7379096},
                {"seatid": 5, "chips": 4447200},
                {"chips": 1592723},
                {"seatid": 1, "chips": 797300},
                {"seatid": 2, "chips": 3149111},
            ],
            "gameid": "dead-button",
        }
    )

    positions = {p.player_id: p.position for p in calls[0]["players"]}
    assert positions == {
        10262053: "MP",
        10201582: "CO",
        10637554: "BTN",
        10547857: "SB",
        10583348: "BB",
    }
    assert calls[0]["dealer_id"] == -4          # the physical dealer seat still reaches the API


def test_dealer_info_heads_up_empty_dealer_seat_uses_the_named_blinds(monkeypatch) -> None:
    calls = []

    class FakeAPI:
        def new_hand(self, **kwargs):
            calls.append(kwargs)

    b = BotBridge()
    b._api = FakeAPI()
    b._my_seat = 1
    b._seat_uids = {1: "10262053", 4: "10332601"}
    monkeypatch.setattr(b, "_ensure_api", lambda: True)

    # dealer chip on empty seat 0 (dropped from the message as a zero field);
    # hero in seat 1 is the big blind, seat 4 posts the small blind and acts last after the flop
    b._on_dealer_info(
        {
            "small_blind": 4,
            "big_blind": 1,
            "start_info": [{"seatid": 4, "chips": 1000000}, {"seatid": 1, "chips": 1000000}],
            "gameid": "hu-dead-button",
        }
    )
    assert {p.player_id: p.position for p in calls[0]["players"]} == {10262053: "BB", 10332601: "BTN"}


def test_forced_big_blind_post_is_hero_bet() -> None:
    b = BotBridge()
    b._api = object()
    b._my_seat = 2

    b._on_action_brc(
        {"seatid": 2, "action_type": 11, "chips": 1000, "hand_chips": 99000}
    )

    assert b._my_forced_post_this_street is True
    assert b._my_bet == 1000


@pytest.mark.parametrize("action_type, chips, recorded", [
    (4, 3000, [("raise", 3000, 3000, "flop")]),      # raise
    (17, 99000, [("raise", 99000, 99000, "flop")]),  # all-in over the others
    (1, 0, [("fold", 0, 0, "flop")]),
    (11, 1000, []),                                  # forced big blind: not a decision
])
def test_hero_action_confirmed_by_the_server_is_recorded(action_type, chips, recorded) -> None:
    class FakeAPI:
        def __init__(self):
            self.executions = []

        def record_hero_execution(self, *, action, amount_added, total_bet_after, street):
            self.executions.append((action, amount_added, total_bet_after, street))

    b = BotBridge()
    b._api = FakeAPI()
    b._my_seat = 2
    b._stage = 2

    b._on_action_brc({"seatid": 2, "action_type": action_type, "chips": chips, "hand_chips": 100000 - chips})

    assert b._api.executions == recorded


def test_pending_gamedata_seed_migrates_legacy_archive_before_get() -> None:
    class FakeBot:
        def __init__(self):
            self.opponent_model = OpponentModel()

    class FakeAPI:
        def __init__(self):
            self._bot = FakeBot()
            self.hands = []

        def new_hand(self, **kwargs):
            self.hands.append(kwargs)

    b = BotBridge()
    b._api = FakeAPI()
    b._my_seat = 0
    b._seat_names = {0: "Hero", 2: "LegacyName"}
    b._seat_uids = {0: "999", 2: "1001"}
    b._api._bot.opponent_model._name_archive["LegacyName"] = OpponentStats(
        hands_seen=35,
        fold_count=9,
    )
    b._pending_seeds = {
        1001: {
            "play_times": 20,
            "pool_entry_rate": 5000,
            "add_before_flipping_rate": 2000,
            "show_hand_rate": 2500,
            "active_rate": 1000,
        }
    }

    b._on_dealer_info(
        {
            "dealer": 0,
            "start_info": [
                {"seatid": 0, "chips": 200},
                {"seatid": 2, "chips": 200},
            ],
            "gameid": "legacy-seed",
        }
    )

    om = b._api._bot.opponent_model
    stats = om.get(1001)
    assert "LegacyName" not in om._name_archive
    assert stats.hands_seen == 20
    assert stats.fold_count == 9
    assert om._id_to_name[1001] == "LegacyName"


def test_pending_gamedata_seed_uses_cached_name_when_player_not_in_hand() -> None:
    class FakeBot:
        def __init__(self):
            self.opponent_model = OpponentModel()

    class FakeAPI:
        def __init__(self):
            self._bot = FakeBot()

        def new_hand(self, **kwargs):
            pass

    b = BotBridge()
    b._api = FakeAPI()
    b._my_seat = 0
    b._seat_names = {0: "Hero"}
    b._seat_uids = {0: "999"}
    b._pending_seeds = {
        1001: {
            "name": "CachedName",
            "data": {
                "play_times": 20,
                "pool_entry_rate": 5000,
                "add_before_flipping_rate": 2000,
                "show_hand_rate": 2500,
                "active_rate": 1000,
            },
        }
    }

    b._on_dealer_info(
        {
            "dealer": 0,
            "start_info": [{"seatid": 0, "chips": 200}],
            "gameid": "cached-name-seed",
        }
    )

    om = b._api._bot.opponent_model
    assert om.get(1001).hands_seen == 20
    assert om._id_to_name[1001] == "CachedName"


def test_gamedata_fetch_without_event_loop_uses_thread_fallback(monkeypatch) -> None:
    class FakeBot:
        def __init__(self):
            self.opponent_model = OpponentModel()

    class FakeAPI:
        def __init__(self):
            self._bot = FakeBot()

    b = BotBridge()
    b._api = FakeAPI()
    calls = []

    def fake_start(uid: int, seat: int, name: str = "") -> None:
        calls.append((uid, seat, name))
        b._apply_gamedata_fetch_result(
            uid,
            seat,
            name,
            {
                "code": 0,
                "data": {
                    "play_times": 20,
                    "pool_entry_rate": 5000,
                    "add_before_flipping_rate": 2000,
                    "show_hand_rate": 2500,
                    "active_rate": 1000,
                },
            },
        )

    monkeypatch.setattr(b, "_start_gamedata_fetch_thread", fake_start)

    seat_status = {
        "seatid": 2,
        "player": {"uid": 1001, "name": "Villain"},
    }
    b._trigger_gamedata_fetch(seat_status)
    b._trigger_gamedata_fetch(seat_status)

    assert calls == [(1001, 2, "Villain")]
    om = b._api._bot.opponent_model
    assert om.get(1001).hands_seen == 20
    assert om._id_to_name[1001] == "Villain"


def test_gamedata_thread_fallback_cleans_up(monkeypatch) -> None:
    b = BotBridge()
    calls = []
    entered = threading.Event()
    release = threading.Event()

    def fake_fetch(uid: int, seat: int, name: str = "") -> None:
        entered.set()
        release.wait(timeout=1.0)
        calls.append((uid, seat, name))

    monkeypatch.setattr(b, "_do_gamedata_fetch_sync", fake_fetch)

    b._start_gamedata_fetch_thread(1001, 2, "Villain")
    assert entered.wait(timeout=1.0)
    threads = list(b._gamedata_threads)
    assert len(threads) == 1
    release.set()
    threads[0].join(timeout=1.0)

    assert calls == [(1001, 2, "Villain")]
    assert not b._gamedata_threads


def test_hand_card_rsp_does_not_auto_show_hero_cards() -> None:
    class FakeAPI:
        def __init__(self):
            self.cards = []

        def deal_hole_cards(self, cards):
            self.cards.append(cards)

    b = BotBridge()
    b._api = FakeAPI()
    b._current_gameid = "game-1"

    out = b.handle("pb.HandCardRSP", {"card1": 270, "card2": 1038})

    assert b._api.cards == [["Ad", "As"]]
    assert out is None


def test_show_my_card_brc_is_not_watched_but_showdown_messages_are() -> None:
    assert "pb.ShowMyCardBRC" not in config.WATCH_S2C
    assert "pb.ShowHandRSP" in config.WATCH_S2C
    assert "pb.WinnerRSP" in config.WATCH_S2C


class TestBotBridgeProfitLock:
    def _next_hand_dealer(self, bridge: BotBridge, gameid: str = "t_next"):
        """Start the next hand; profit-lock no longer emits LeaveRoomREQ here."""
        return bridge.handle(
            "pb.DealerInfoRSP",
            {
                "dealer": 0,
                "small_blind": 1,
                "big_blind": 0,
                "start_info": [
                    {"seatid": 0, "chips": 200},
                    {"seatid": 1, "chips": 200},
                ],
                "gameid": gameid,
            },
        )

    def _bootstrap_table(self, bridge: BotBridge, room_id: int = 20242379) -> None:
        bridge.handle(
            "pb.EnterRoomRSP",
            {
                "code": 0,
                "roomid": room_id,
                "game_type": 10010101,
                "room_info": {
                    "bb": 2.0,
                    "sb": 1.0,
                    "lobby_coin": 10100001,
                },
                "table_status": {"seat": []},
            },
        )
        bridge.handle("pb.SitDownRSP", {"seatid": 0})
        bridge.handle(
            "pb.DealerInfoRSP",
            {
                "dealer": 0,
                "small_blind": 1,
                "big_blind": 0,
                "start_info": [
                    {"seatid": 0, "chips": 200},
                    {"seatid": 1, "chips": 200},
                ],
                "gameid": "t1",
            },
        )

    def test_winner_below_threshold_no_leave(self) -> None:
        """Trigger condition: on-table chips my_final >= threshold.
        my_final < threshold → no trigger, regardless of PnL history."""
        b = BotBridge(max_auto_rebuy=3)
        b._my_uid = "99"
        self._bootstrap_table(b)
        b._uid_to_seat["99"] = 0
        bb = 2.0
        thr_chips = int(config.PROFIT_LOCK_BB_THRESHOLD * bb)
        # Hero starts 200 chips; profit X → my_final = 200 + X.
        # To stay below threshold, profit = thr - 200 - 1.
        start = 200
        profit = thr_chips - start - 1
        out = b.handle(
            "pb.WinnerRSP",
            {
                "winner": [],
                "profit": [{"uid": "99", "chips": profit}],
            },
        )
        assert out is None
        assert b._profit_lock_reenter is None
        assert not b._profit_lock_awaiting_enter

    def test_winner_triggers_leave_then_enter_and_the_loss_cap_stays(self) -> None:
        b = BotBridge(max_auto_rebuy=3)
        b._my_uid = "99"
        rid = 20242379
        self._bootstrap_table(b, room_id=rid)
        b._uid_to_seat["99"] = 0
        bb = 2.0
        thr_chips = int(config.PROFIT_LOCK_BB_THRESHOLD * bb)
        # Hero starts 200 chips; profit = thr - 200 → my_final = thr → trigger.
        start = 200
        profit = thr_chips - start
        out = b.handle(
            "pb.WinnerRSP",
            {
                "winner": [],
                "profit": [{"uid": "99", "chips": profit}],
            },
        )
        assert out == ("pb.DelayLeaveRoomREQ", {"flag": True}, 0.0)
        assert b._profit_lock_deferred is not None
        assert b._profit_lock_deferred["roomid"] == rid
        assert b._profit_lock_deferred["byin_chips"] == int(100 * bb)
        assert b._profit_lock_reenter is not None
        assert b._profit_lock_reenter["roomid"] == rid
        assert b._profit_lock_reenter["byin_chips"] == int(100 * bb)
        assert not b._profit_lock_awaiting_enter

        out_delay = b.handle("pb.DelayLeaveRoomRSP", {"code": 0, "flag": True})
        assert out_delay is None
        assert b._profit_lock_deferred is not None
        assert b._profit_lock_reenter is not None
        assert b._profit_lock_reenter["delay_leave_confirmed"] is True
        assert not b._profit_lock_awaiting_enter

        out2 = b.handle("pb.LeaveRoomRSP", {"code": 0})
        assert out2[0] == "pb.UserValueREQ"
        assert out2[1]["type"] == 10100001
        assert b._profit_lock_deferred is None
        assert b._bankroll_pending_action is not None
        assert b._bankroll_pending_action["kind"] == "profit_lock"
        out3 = b.handle("pb.UserValueRSP", {"type": 10100001, "value": 10_000})
        assert out3[0] == "pb.EnterRoomREQ"
        assert out3[1]["roomid"] == rid
        assert out3[1]["byin_chips"] == 200
        assert out3[1]["uid"] == 99
        exp_delay = max(0.0, min(60.0, float(getattr(config, "PROFIT_LOCK_REENTER_DELAY_SEC", 2.0))))
        assert out3[2] == exp_delay
        assert b._profit_lock_reenter is None
        assert b._profit_lock_awaiting_enter

        enter_out = b.handle(
            "pb.EnterRoomRSP",
            {
                "code": 0,
                "roomid": rid,
                "game_type": 10010101,
                "room_info": {"bb": 2.0, "sb": 1.0, "lobby_coin": 10100001},
                "table_status": {"seat": []},
            },
        )
        assert enter_out is None
        assert b._max_auto_rebuy == 3          # a lock no longer widens the loss cap
        assert not b._profit_lock_awaiting_enter

    def test_leave_room_rsp_omitted_code_means_success(self) -> None:
        """MessageToDict 常省略 code=0，须仍能重进房。"""
        b = BotBridge(max_auto_rebuy=3)
        b._my_uid = "99"
        rid = 111
        self._bootstrap_table(b, room_id=rid)
        b._uid_to_seat["99"] = 0
        thr = int(config.PROFIT_LOCK_BB_THRESHOLD * 2.0)
        b.handle(
            "pb.WinnerRSP",
            {"winner": [], "profit": [{"uid": "99", "chips": thr - 200}]},
        )
        b.handle("pb.DelayLeaveRoomRSP", {"code": 0, "flag": True})
        out = b.handle(
            "pb.LeaveRoomRSP",
            {"roomid": rid, "game_type": 1},
        )
        assert out is not None and out[0] == "pb.UserValueREQ"
        enter = b.handle("pb.UserValueRSP", {"type": 10100001, "value": 10_000})
        assert enter is not None and enter[0] == "pb.EnterRoomREQ"
        assert enter[1]["roomid"] == rid
        assert enter[1]["byin_chips"] == 200
        assert len(enter) == 3

    def test_leave_room_fail_cancels(self) -> None:
        b = BotBridge(max_auto_rebuy=3)
        b._my_uid = "99"
        self._bootstrap_table(b)
        b._uid_to_seat["99"] = 0
        bb = 2.0
        thr_chips = int(config.PROFIT_LOCK_BB_THRESHOLD * bb)
        b.handle(
            "pb.WinnerRSP",
            {"winner": [], "profit": [{"uid": "99", "chips": thr_chips - 200}]},
        )
        b.handle("pb.DelayLeaveRoomRSP", {"code": 0, "flag": True})
        out = b.handle("pb.LeaveRoomRSP", {"code": -1})
        assert out is None
        assert b._profit_lock_reenter is None
        assert not b._profit_lock_awaiting_enter
        assert b._max_auto_rebuy == 3
        assert b._bankroll_samples == []

    def test_enter_room_rsp_before_leave_success_does_not_award(self) -> None:
        b = BotBridge(max_auto_rebuy=3)
        b._my_uid = "99"
        self._bootstrap_table(b)
        b._uid_to_seat["99"] = 0
        thr_chips = int(config.PROFIT_LOCK_BB_THRESHOLD * 2.0)
        b.handle(
            "pb.WinnerRSP",
            {"winner": [], "profit": [{"uid": "99", "chips": thr_chips - 200}]},
        )

        out = b.handle(
            "pb.EnterRoomRSP",
            {
                "code": 0,
                "roomid": 20242379,
                "game_type": 10010101,
                "room_info": {"bb": 2.0, "sb": 1.0, "lobby_coin": 10100001},
                "table_status": {"seat": []},
            },
        )

        assert out is None
        assert b._max_auto_rebuy == 3
        assert b._bankroll_samples == []
        assert not b._profit_lock_awaiting_enter

    def test_enter_room_fail_no_award(self) -> None:
        b = BotBridge(max_auto_rebuy=3)
        b._my_uid = "99"
        self._bootstrap_table(b)
        b._uid_to_seat["99"] = 0
        thr_chips = int(config.PROFIT_LOCK_BB_THRESHOLD * 2.0)
        b.handle(
            "pb.WinnerRSP",
            {"winner": [], "profit": [{"uid": "99", "chips": thr_chips - 200}]},
        )
        b.handle("pb.DelayLeaveRoomRSP", {"code": 0, "flag": True})
        assert b.handle("pb.LeaveRoomRSP", {"code": 0})[0] == "pb.UserValueREQ"
        assert b.handle("pb.UserValueRSP", {"type": 10100001, "value": 10_000})[0] == "pb.EnterRoomREQ"
        qs = b.handle(
            "pb.EnterRoomRSP",
            {"code": -1, "roomid": 20242379, "room_info": {"bb": 2.0}, "table_status": {"seat": []}},
        )
        assert qs is not None
        assert qs[0] == "pb.QuickStartREQ"
        assert qs[1]["game_type"] == 10010101
        assert qs[1]["lobby_coin"] == 10100001
        assert qs[1]["byin_chips"] == 200
        assert b._max_auto_rebuy == 3
        assert not b._profit_lock_awaiting_enter

    def test_delay_leave_fail_cancels(self) -> None:
        b = BotBridge(max_auto_rebuy=3)
        b._my_uid = "99"
        self._bootstrap_table(b)
        b._uid_to_seat["99"] = 0
        thr_chips = int(config.PROFIT_LOCK_BB_THRESHOLD * 2.0)
        out = b.handle(
            "pb.WinnerRSP",
            {"winner": [], "profit": [{"uid": "99", "chips": thr_chips - 200}]},
        )
        assert out == ("pb.DelayLeaveRoomREQ", {"flag": True}, 0.0)
        assert b.handle("pb.DelayLeaveRoomRSP", {"code": 121, "flag": False}) is None
        assert b._profit_lock_deferred is None
        assert b._profit_lock_reenter is None

    def test_next_dealer_retries_unconfirmed_delay_leave(self) -> None:
        b = BotBridge(max_auto_rebuy=3)
        b._my_uid = "99"
        self._bootstrap_table(b)
        b._uid_to_seat["99"] = 0
        thr_chips = int(config.PROFIT_LOCK_BB_THRESHOLD * 2.0)
        b.handle(
            "pb.WinnerRSP",
            {"winner": [], "profit": [{"uid": "99", "chips": thr_chips - 200}]},
        )

        retry = self._next_hand_dealer(b)
        assert retry == ("pb.DelayLeaveRoomREQ", {"flag": True}, 0.0)
        assert b._profit_lock_reenter is not None
        assert b._profit_lock_reenter["delay_leave_retry_sent"] is True

        assert self._next_hand_dealer(b, gameid="t_next2") is None


class TestBankrollSampling:
    """Wallet samples show the balances; the session's poker PnL is the sum of
    settled hands. The profit-lock trigger condition is on-table chips
    (my_final), not that PnL.
    """

    def _setup(self, bb: float = 2.0, room_id: int = 20242379):
        helper = TestBotBridgeProfitLock()
        b = BotBridge(max_auto_rebuy=5)
        b._my_uid = "99"
        helper._bootstrap_table(b, room_id=room_id)
        b._uid_to_seat["99"] = 0
        return b

    def test_winning_a_hand_does_not_record_bankroll_sample(self):
        """Per-hand profit does not update the bankroll dashboard by itself."""
        b = self._setup()
        assert b.bankroll_dashboard()["base_total_chips"] is None
        b.handle(
            "pb.WinnerRSP",
            {"winner": [], "profit": [{"uid": "99", "chips": 150}]},
        )
        assert b.bankroll_dashboard()["base_total_chips"] is None

    def test_winning_a_hand_records_bankroll_chart_point_after_baseline(self):
        """After wallet baseline, every settled hand adds one bankroll chart point."""
        b = self._setup()
        b.handle("pb.UserValueRSP", {"type": 10100001, "value": 50_000})
        out = b.handle(
            "pb.WinnerRSP",
            {"winner": [], "profit": [{"uid": "99", "chips": 150}]},
        )
        assert out is None
        dash = b.bankroll_dashboard()
        assert len(dash["samples"]) == 1
        assert len(dash["hand_points"]) == 1
        point = dash["hand_points"][0]
        assert point["hand_no"] == b._hand_seq
        assert point["wallet_chips"] == 50_000
        assert point["table_chips"] == 350
        assert point["total_chips"] == 50_350
        assert point["delta_chips"] == 150
        assert point["hand_delta_chips"] == 150
        assert point["buyin_seq"] == 1

    def test_bankroll_chart_points_mark_buyin_segments(self):
        """Chart points carry buy-in sequence so the Web chart can segment sessions."""
        b = self._setup()
        b.handle("pb.UserValueRSP", {"type": 10100001, "value": 50_000})
        b.handle("pb.WinnerRSP", {"winner": [], "profit": [{"uid": "99", "chips": 10}]})
        b.handle("pb.RebyBRC", {"seatid": 0, "chips": 200})
        b._hand_start_chips[0] = b._my_chips
        b.handle("pb.WinnerRSP", {"winner": [], "profit": [{"uid": "99", "chips": 20}]})

        points = b.bankroll_dashboard()["hand_points"]
        assert [point["buyin_seq"] for point in points] == [1, 2]
        assert points[-1]["table_chips"] == 430
        assert points[-1]["hand_delta_chips"] == 20

    def test_auto_rebuy_samples_bankroll_before_rebuy(self):
        """Hero busts → NoticeReby → UserValueREQ → UserValueRSP → RebyREQ."""
        b = self._setup()
        bb = 2.0
        rebuy_chips = int(100 * bb)
        out = b.handle("pb.NoticeRebyRSP", {"seatid": 0, "reby_left_time": 30})
        assert out[0] == "pb.UserValueREQ"
        assert b._bankroll_pending_action["kind"] == "auto_rebuy"
        assert b._current_table_chips() == 0

        reby = b.handle("pb.UserValueRSP", {"type": 10100001, "value": 50_000})
        assert reby == ("pb.RebyREQ", {"is_reby": True, "chips": rebuy_chips}, 0.0)
        dash = b.bankroll_dashboard()
        assert dash["base_total_chips"] == 50_000
        assert dash["session_delta_chips"] == 0

    def test_manual_leave_clears_table_chips_and_refreshes_wallet(self):
        """普通离桌后 Web 资金看板不能继续显示旧桌上筹码。"""
        b = self._setup()
        b.handle("pb.UserValueRSP", {"type": 10100001, "value": 50_000})
        assert b.bankroll_dashboard()["table_chips"] == 200

        out = b.handle("pb.LeaveRoomRSP", {"code": 0})

        assert out == ("pb.UserValueREQ", {"type": 10100001}, 0.0)
        assert b.bankroll_dashboard()["table_chips"] == 0
        b.handle("pb.UserValueRSP", {"type": 10100001, "value": 50_200})
        dash = b.bankroll_dashboard()
        assert dash["wallet_chips"] == 50_200
        assert dash["current_total_chips"] == 50_200
        assert dash["session_delta_chips"] == 0

    def test_stand_up_brc_clears_hero_table_chips(self):
        b = self._setup()
        b.handle("pb.UserValueRSP", {"type": 10100001, "value": 50_000})

        out = b.handle("pb.StandUpBRC", {"seatid": 0})

        assert out == ("pb.UserValueREQ", {"type": 10100001}, 0.0)
        assert b.bankroll_dashboard()["table_chips"] == 0

    def test_stand_up_rsp_clears_hero_table_chips(self):
        b = self._setup()
        b.handle("pb.UserValueRSP", {"type": 10100001, "value": 50_000})

        out = b.handle("pb.StandUpRSP", {"code": 0})

        assert out == ("pb.UserValueREQ", {"type": 10100001}, 0.0)
        assert b.bankroll_dashboard()["table_chips"] == 0

    def test_other_leave_room_brc_clears_hero_table_chips(self):
        b = self._setup()
        b.handle("pb.UserValueRSP", {"type": 10100001, "value": 50_000})

        out = b.handle("pb.OtherLeaveRoomBRC", {"uid": 99, "roomid": 20242379})

        assert out == ("pb.UserValueREQ", {"type": 10100001}, 0.0)
        assert b.bankroll_dashboard()["table_chips"] == 0

    def test_empty_table_snapshot_clears_stale_hero_table_chips(self):
        b = self._setup()
        b.handle("pb.UserValueRSP", {"type": 10100001, "value": 50_000})
        assert b.bankroll_dashboard()["table_chips"] == 200

        b._sync_stacks_from_table_snapshot({"seat": []})

        assert b.bankroll_dashboard()["table_chips"] == 0

    def test_full_profit_lock_cycle_samples_after_leave_before_reenter(self):
        """Full cycle: trigger → leave → UserValueRSP sample → reenter."""
        b = self._setup()
        bb = 2.0
        thr_chips = int(config.PROFIT_LOCK_BB_THRESHOLD * bb)   # 400 for 200 BB at BB=2
        # Bring on-table chips to exactly threshold (hero started 200).
        out = b.handle(
            "pb.WinnerRSP",
            {"winner": [], "profit": [{"uid": "99", "chips": thr_chips - 200}]},
        )
        assert out == ("pb.DelayLeaveRoomREQ", {"flag": True}, 0.0)
        assert b._profit_lock_deferred is not None
        b.handle("pb.DelayLeaveRoomRSP", {"code": 0, "flag": True})
        out = b.handle("pb.LeaveRoomRSP", {"code": 0})
        assert out[0] == "pb.UserValueREQ"
        assert b._profit_lock_deferred is None
        assert b._bankroll_pending_action["kind"] == "profit_lock"
        enter = b.handle("pb.UserValueRSP", {"type": 10100001, "value": 60_000})
        assert enter[0] == "pb.EnterRoomREQ"
        assert b._bankroll_profit_lock_count == 1
        assert b.bankroll_dashboard()["current_total_chips"] == 60_000
        # A successful re-entry leaves the loss cap where it was: the winnings are in the net result.
        b.handle(
            "pb.EnterRoomRSP",
            {
                "code": 0, "roomid": 20242379, "game_type": 10010101,
                "room_info": {"bb": 2.0, "sb": 1.0, "lobby_coin": 10100001},
                "table_status": {"seat": []},
            },
        )
        assert b._max_auto_rebuy == 5

    def test_trigger_uses_on_table_not_bankroll_sample(self):
        """Regression: even if no bankroll baseline exists, on-table
        chips above threshold MUST fire. This is the dead-lock regression —
        earlier code gated on session PnL and the first trigger was unreachable."""
        b = self._setup()
        bb = 2.0
        thr_chips = int(config.PROFIT_LOCK_BB_THRESHOLD * bb)
        assert b.bankroll_dashboard()["base_total_chips"] is None
        out = b.handle(
            "pb.WinnerRSP",
            {"winner": [], "profit": [{"uid": "99", "chips": thr_chips - 200}]},
        )
        assert out == ("pb.DelayLeaveRoomREQ", {"flag": True}, 0.0)
        assert b._profit_lock_deferred is not None, (
            "first-ever trigger MUST fire from on-table chips alone "
            "(dead-lock regression: trigger that gated on PnL was unreachable)"
        )

    def test_trigger_ignores_negative_session_pnl(self):
        """Even if the session's poker PnL is negative, on-table threshold fires."""
        b = self._setup()
        bb = 2.0
        thr_chips = int(config.PROFIT_LOCK_BB_THRESHOLD * bb)
        b.handle("pb.UserValueRSP", {"type": 10100001, "value": 100_000})
        b._session_poker_pnl = -10_000          # earlier tables in this run
        assert b.bankroll_dashboard()["session_delta_chips"] < 0
        # But hero's on-table chips just crossed threshold.
        out = b.handle(
            "pb.WinnerRSP",
            {"winner": [], "profit": [{"uid": "99", "chips": thr_chips - 200}]},
        )
        assert out == ("pb.DelayLeaveRoomREQ", {"flag": True}, 0.0)
        assert b._profit_lock_deferred is not None, (
            "session PnL is separate — trigger must still fire on on-table chips"
        )


class TestTableTopup:
    """A short stack is topped up at the table (pb.SetRebyREQ) before the next deal.

    Table of the profit-lock tests: big blind 2, hero in seat 0 with 200 chips (100BB).
    The top-up starts below 70BB (140 chips) and aims at 100BB (200 chips); the amounts the
    client offers are 20–30BB in steps of 1BB, then 40, 50 … 200BB.
    """

    def _setup(self, max_auto_rebuy: int = 5):
        b = BotBridge(max_auto_rebuy=max_auto_rebuy)
        b._my_uid = "99"
        TestBotBridgeProfitLock()._bootstrap_table(b)
        b._uid_to_seat["99"] = 0
        return b

    @staticmethod
    def _lose(b, chips: int):
        return b.handle("pb.WinnerRSP", {"winner": [], "profit": [{"uid": "99", "chips": -chips}]})

    @staticmethod
    def _deal(b, hero_chips: int, gameid: str):
        return b.handle("pb.DealerInfoRSP", {
            "dealer": 0, "small_blind": 1, "big_blind": 0, "gameid": gameid,
            "start_info": [{"seatid": 0, "chips": hero_chips}, {"seatid": 1, "chips": 200}]})

    def test_short_stack_asks_for_chips_and_reports_when_they_arrive(self, monkeypatch):
        sent = []
        monkeypatch.setattr("pf_intercept.bot.notify", lambda event, **f: event == "topup" and sent.append((event, f)))
        b = self._setup()
        # 200 → 130 chips (65BB): 70 short of 100BB, the largest amount on offer below that is 30BB
        assert self._lose(b, 70) == ("pb.SetRebyREQ", {"reby_chips": 60}, 0.0)
        assert b.handle("pb.SetRebyRSP", {"reby_chips": 60}) is None
        assert sent == []                                   # nothing until the chips are on the table
        # the server credits the amount it was asked for, right before the next deal
        out = b.handle("pb.RebyBRC", {"chips": 60, "type": "topup"})
        assert out == [("pb.UserValueREQ", {"type": 10100001}, 0.0)]      # wallet figure refreshed
        assert b._my_chips == b._current_table_chips() == 190
        assert sent == [("topup", {"added_chips": 60, "stack_chips": 190, "big_blind": 2, "nth": 1,
                                   "session_delta_chips": -70})]
        dash = b.bankroll_dashboard()
        assert (dash["topup_count"], dash["topup_chips"], dash["session_delta_chips"]) == (1, 60, -70)
        # the top-up is a buy-in, not a result: the next hand starts a new segment and the PnL is untouched
        self._deal(b, 190, "t2")
        assert self._lose(b, 10) is None and b._session_poker_pnl == -80

    def test_no_top_up_at_70bb_or_when_broke(self):
        b = self._setup()
        assert self._lose(b, 60) is None                    # exactly 70BB left
        b = self._setup()
        assert self._lose(b, 200) is None                   # nothing left: the rebuy path handles it

    def test_deeper_holes_get_the_largest_amount_that_stays_within_100bb(self):
        b = self._setup()
        assert self._lose(b, 110) == ("pb.SetRebyREQ", {"reby_chips": 100}, 0.0)   # 45BB + 50BB
        b = self._setup()
        assert self._lose(b, 61) == ("pb.SetRebyREQ", {"reby_chips": 60}, 0.0)     # 69.5BB + 30BB

    def test_one_request_at_a_time_then_given_up_after_two_hands(self):
        b = self._setup()
        assert self._lose(b, 70) is not None
        self._deal(b, 130, "t2")                            # the chips did not come
        assert self._lose(b, 2) is None                     # still waiting: no second request
        self._deal(b, 128, "t3")
        assert self._lose(b, 2) is None and b._topup_pending is None      # given up
        for i in range(29):                                 # and left alone for 30 hands
            self._deal(b, 126, f"w{i}")
            assert self._lose(b, 0) is None
        self._deal(b, 126, "t34")
        assert self._lose(b, 0) == ("pb.SetRebyREQ", {"reby_chips": 60}, 0.0)

    def test_a_refusal_backs_off(self):
        b = self._setup()
        assert self._lose(b, 70) is not None
        b.handle("pb.SetRebyRSP", {"code": 7})
        assert b._topup_pending is None
        self._deal(b, 130, "t2")
        assert self._lose(b, 2) is None

    def test_top_ups_stop_at_the_loss_limit_of_the_start(self):
        # limit = (1 + 5 rebuys) × 100BB = 1200 chips for lost + on the table + added
        b = self._setup()
        b._session_poker_pnl = -900
        assert self._lose(b, 70) == ("pb.SetRebyREQ", {"reby_chips": 60}, 0.0)     # 970 + 130 + 60 fits
        b = self._setup()
        b._session_poker_pnl = -960
        assert self._lose(b, 70) == ("pb.SetRebyREQ", {"reby_chips": 40}, 0.0)     # only 40 left of it
        b = self._setup()
        b._session_poker_pnl = -1000
        assert self._lose(b, 70) is None
        assert self._lose(self._setup(max_auto_rebuy=0), 70) is None               # no rebuys, no top-ups

    def test_no_top_up_while_leaving_stopping_or_switched_off(self, monkeypatch):
        b = self._setup()
        b._table_switch = {"mode": "leave"}
        assert self._lose(b, 70) is None
        b = self._setup()
        b.stop_auto_rejoin()
        assert self._lose(b, 70) is None
        b = self._setup()
        monkeypatch.setattr(config, "TOPUP_BELOW_BB", 0)
        assert self._lose(b, 70) is None

    def test_another_players_top_up_only_moves_his_stack(self, monkeypatch):
        sent = []
        monkeypatch.setattr("pf_intercept.bot.notify", lambda event, **f: event == "topup" and sent.append((event, f)))
        b = self._setup()
        assert b.handle("pb.RebyBRC", {"seatid": 1, "chips": 100, "type": "topup"}) is None
        assert b._seat_chips[1] == 300 and b._my_chips == 200 and sent == [] and b._topup_count == 0


class TestNetLossCap:
    """One number ends a start: its net loss may not pass (1 + N) buy-ins of 100BB.

    Same table as the top-up tests: big blind 2, so a buy-in is 200 chips and N = 1 caps the
    start at 400.  Everything that brings chips to a table must fit: lost + on the table + brought.
    """

    @staticmethod
    def _setup(max_auto_rebuy: int = 1, monkeypatch=None):
        b = TestTableTopup()._setup(max_auto_rebuy)
        if monkeypatch is not None:
            sent = []
            monkeypatch.setattr("pf_intercept.bot.notify", lambda event, **f: sent.append((event, f)))
            return b, sent
        return b

    @staticmethod
    def _bust(b, net: int):
        """Hero has no chips left and the start stands at ``net``; returns the rebuy request, if any."""
        b._session_poker_pnl = net
        b._seat_chips[0] = b._my_chips = 0
        if b.handle("pb.NoticeRebyRSP", {"seatid": 0, "reby_left_time": 30}) is None:
            return None
        return b.handle("pb.UserValueRSP", {"type": 10100001, "value": 50_000})

    def test_a_bust_buys_100bb_while_that_fits_and_ends_the_start_when_nothing_does(self, monkeypatch):
        b, sent = self._setup(1, monkeypatch)
        assert self._bust(b, -200) == ("pb.RebyREQ", {"is_reby": True, "chips": 200}, 0.0)
        b.handle("pb.RebyBRC", {"chips": 200, "type": "reby"})
        assert self._bust(b, -400) is None                  # two buy-ins lost: the cap
        assert b._loss_stop and b._auto_rebuy_done == 1
        stops = [f for e, f in sent if e == "loss_stop"]
        assert stops == [{"what": "破产买入", "session_delta_chips": -400, "loss_cap_chips": 400, "buyins": 2}]
        assert self._bust(b, -400) is None and len([e for e, _ in sent if e == "loss_stop"]) == 1
        dash = b.bankroll_dashboard()
        assert (dash["loss_cap_chips"], dash["loss_stop"], dash["auto_rebuy_count"]) == (400, True, 1)

    def test_a_bust_with_less_room_than_100bb_buys_what_fits(self, monkeypatch):
        b, _ = self._setup(1, monkeypatch)
        assert self._bust(b, -300) == ("pb.RebyREQ", {"is_reby": True, "chips": 100}, 0.0)   # 50BB left of it
        b, _ = self._setup(1, monkeypatch)
        assert self._bust(b, -345) == ("pb.RebyREQ", {"is_reby": True, "chips": 54}, 0.0)    # 27.5BB → 27BB
        b, _ = self._setup(1, monkeypatch)
        assert self._bust(b, -370) is None and b._loss_stop                                  # 15BB: below the smallest buy-in

    def test_rebuys_are_not_counted_only_the_net_result_is(self, monkeypatch):
        b, _ = self._setup(0, monkeypatch)                  # cap: one buy-in
        for nth in (1, 2, 3):                               # busting while the start is still ahead
            assert self._bust(b, +50) == ("pb.RebyREQ", {"is_reby": True, "chips": 200}, 0.0)
            assert b._auto_rebuy_done == nth
        assert self._bust(b, -1) == ("pb.RebyREQ", {"is_reby": True, "chips": 180}, 0.0)     # 99.5BB of room → 90BB
        assert self._bust(b, -200) is None and b._loss_stop

    def test_no_top_up_once_the_start_is_over(self, monkeypatch):
        b, _ = self._setup(5, monkeypatch)
        b._loss_stop = True
        assert TestTableTopup._lose(b, 70) is None

    def test_rejoin_after_an_unexpected_leave_brings_no_more_than_the_cap_allows(self, monkeypatch):
        sent = []
        monkeypatch.setattr("pf_intercept.bot.notify", lambda event, **f: sent.append((event, f)))
        # 10000 blind, N = 5: the cap is 6,000,000
        b = _recoverable_bridge()
        monkeypatch.setattr(b, "_runtime_calibration_should_pause_play", lambda: None)
        b._session_poker_pnl = -5_500_000
        b.handle("pb.LeaveRoomRSP", {"roomid": 21205174})
        rejoin = b.handle("pb.UserValueRSP", {"type": 10100001, "value": "105363439"})
        assert rejoin[0] == "pb.QuickStartREQ" and rejoin[1]["byin_chips"] == 500_000        # 50BB of room
        assert b._auto_rejoin_fields["byin_chips"] == 1_000_000                               # the plan is unchanged

        b = _recoverable_bridge()
        monkeypatch.setattr(b, "_runtime_calibration_should_pause_play", lambda: None)
        b._session_poker_pnl = -5_950_000
        b.handle("pb.LeaveRoomRSP", {"roomid": 21205174})
        assert b.handle("pb.UserValueRSP", {"type": 10100001, "value": "105363439"}) is None
        assert b._loss_stop and [e for e, _ in sent] == ["loss_stop"]
        assert sent[0][1]["what"] == "重新买入"
        # nothing revives it: not a later leave, not a reconnect
        b.prepare_transport_reconnect()
        assert b.restore_lobby_after_disconnect() is False

    def test_back_in_the_lobby_after_a_disconnect_checks_the_cap_before_matching(self, monkeypatch):
        monkeypatch.setattr("pf_intercept.bot.notify", lambda event, **f: None)
        b = _recoverable_bridge()
        monkeypatch.setattr(b, "_runtime_calibration_should_pause_play", lambda: None)
        b._session_poker_pnl = -5_000_000
        b.prepare_transport_reconnect()
        assert b.restore_lobby_after_disconnect() is True
        assert b.cap_match_buyin(b._auto_rejoin_fields)["byin_chips"] == 1_000_000
        b = _recoverable_bridge()
        monkeypatch.setattr(b, "_runtime_calibration_should_pause_play", lambda: None)
        b._session_poker_pnl = -5_990_000
        b.prepare_transport_reconnect()
        assert b.restore_lobby_after_disconnect() is False and b._loss_stop


def test_enter_room_syncs_current_and_start_chips_from_table() -> None:
    """重进房后 hand_chips 是当前筹码，begin_chips 是 WinnerRSP.profit 结算基准。"""
    b = BotBridge(max_auto_rebuy=3)
    b._my_uid = "10086"
    b._table_room_id = 1
    b._bb = 1000.0
    b._sb = 500.0
    b.handle(
        "pb.EnterRoomRSP",
        {
            "code": 0,
            "roomid": 1,
            "game_type": 10010101,
            "room_info": {"bb": "1000", "sb": "500", "lobby_coin": 10100001},
            "table_status": {
                "seat": [
                    {
                        "seatid": 5,
                        "player": {"uid": "10086", "name": "me"},
                        "hand_chips": "100000",
                        "begin_chips": "120000",
                    },
                ],
            },
        },
    )
    assert b._my_seat == 5
    assert b._hand_start_chips[5] == 120000
    assert b._seat_chips[5] == 100000


_TOURNAMENT_ENTER_ROOMS = [
    {"game_type": 10050301, "sngroom_info": {"blind_level": 1, "sb": "25", "bb": "50"}},
    {"game_type": 10060301},
    {"game_type": 40050301},
    {"game_type": 10070401, "mttroom_info": {"blind_level": 3}},
    {"game_type": 20050302},
    {"game_type": 0, "sngroom_info": {"blind_level": 1}},
    {"mttroom_info": {"blind_level": 1}},
]


@pytest.mark.parametrize("room", _TOURNAMENT_ENTER_ROOMS)
def test_tournament_room_is_fully_passive(monkeypatch, room) -> None:
    import pf_intercept.bot as bot_mod

    notified = []
    fetched = []
    monkeypatch.setattr(bot_mod, "notify", lambda event, **fields: notified.append(event))
    monkeypatch.setattr(
        BotBridge,
        "_start_gamedata_fetch_thread",
        lambda self, uid, seat, name="": fetched.append(uid),
    )

    b = BotBridge(max_auto_rebuy=3)
    b._my_uid = "99"
    b._bb = 10000.0
    b._sb = 5000.0
    out = b.handle(
        "pb.EnterRoomRSP",
        {
            "code": 0,
            "roomid": 20399792,
            "room_info": {},
            "table_status": {
                "gameid": "t1",
                "seat": [
                    {"seatid": 0, "player": {"uid": "99", "name": "me"}, "hand_chips": "1500"},
                    {"seatid": 1, "player": {"uid": "77", "name": "villain"}, "hand_chips": "1500"},
                ],
            },
            **room,
        },
    )

    assert out is None
    assert b._tournament_passthrough is True
    assert b.runtime_settings()["tournament_passthrough"] is True
    # Identification only: no blinds, seats, names or opponent fetches.
    assert (b._bb, b._sb) == (10000.0, 5000.0)
    assert b._my_seat is None
    assert b._seat_names == {}

    frames = [
        ("pb.SitDownRSP", {"seatid": 0, "chips": "1500"}),
        ("pb.DealerInfoRSP", {
            "dealer": 0, "small_blind": 0, "big_blind": 1,
            "start_info": [{"chips": "1500"}, {"seatid": 1, "chips": "1500"}],
            "gameid": "t1",
        }),
        ("pb.HandCardRSP", {"cards": [270, 526]}),
        ("pb.ActionNotifyBRC", {"seatid": 0, "call_need_chips": "50", "action_time": 15}),
        ("pb.ActionBRC", {"seatid": 1, "action_type": 4, "action_chips": "100"}),
        ("pb.ShowHandRSP", {"infos": [{"seatid": 1, "hand_cards": [270, 526]}]}),
        ("pb.WinnerRSP", {"winner": [], "profit": [{"uid": "99", "chips": "30000"}]}),
        ("pb.NoticeRebyRSP", {"seatid": 0, "reby_left_time": 30}),
        ("pb.UserValueRSP", {"type": 10100001, "value": 50_000}),
        ("pb.UserLoginRSP", {"code": 0}),
        ("pb.LeaveRoomRSP", {"code": 0}),
    ]
    for type_name, msg in frames:
        assert b.handle(type_name, msg) is None, type_name

    assert b._api is None
    assert b._my_seat is None
    assert b._bankroll_samples == []
    assert notified == []
    assert fetched == []


def test_tournament_drops_pending_cash_actions() -> None:
    b = BotBridge(max_auto_rebuy=3)
    b._my_seat = 2
    b._my_chips = 4000
    b._seat_chips[2] = 4000
    b._profit_lock_reenter = {"quickstart": True}
    b._profit_lock_deferred = {"pending": True}
    b._profit_lock_awaiting_enter = True
    b._bankroll_pending_action = {"kind": "auto_rebuy"}
    b._bankroll_pending_reason = "auto_rebuy"
    b._pending_injects = [("pb.ActionREQ", {})]

    b.handle("pb.EnterRoomRSP", {"code": 0, "roomid": 1, "game_type": 10070401})

    assert b._profit_lock_reenter is None
    assert b._profit_lock_deferred is None
    assert b._profit_lock_awaiting_enter is False
    assert b._bankroll_pending_action is None
    assert b._bankroll_pending_reason == ""
    assert b._pending_injects == []
    assert b._current_table_chips() == 0


def test_cash_enter_room_after_tournament_resumes_bot() -> None:
    b = BotBridge(max_auto_rebuy=3)
    b._my_seat = 0
    b.handle("pb.EnterRoomRSP", {"code": 0, "roomid": 1, "game_type": 10050301})
    assert b._tournament_passthrough is True

    b.handle(
        "pb.EnterRoomRSP",
        {
            "code": 0,
            "roomid": 20242379,
            "game_type": 10010101,
            "room_info": {"bb": 2.0, "sb": 1.0},
            "table_status": {"seat": []},
        },
    )
    assert b._tournament_passthrough is False
    assert b.runtime_settings()["tournament_passthrough"] is False
    assert b._session_game_type == 10010101
    assert (b._bb, b._sb) == (2.0, 1.0)

    b.handle(
        "pb.DealerInfoRSP",
        {
            "dealer": 0,
            "small_blind": 1,
            "big_blind": 2,
            "start_info": [{"chips": "200"}, {"seatid": 1, "chips": "200"}],
            "gameid": "cash1",
        },
    )
    assert b._api is not None
    assert b._skip_runtime_collection is False
    assert b._api._runtime_calibration_recorder is not None


def test_tournament_game_type_does_not_overwrite_cash_session() -> None:
    """QuickStart fallback must never reuse a tournament game_type."""
    b = BotBridge(max_auto_rebuy=3)
    b.handle(
        "pb.EnterRoomRSP",
        {"code": 0, "roomid": 5, "game_type": 10010101, "room_info": {"bb": 2.0, "sb": 1.0}},
    )
    b.handle("pb.EnterRoomRSP", {"code": 0, "roomid": 6, "game_type": 10070401})
    assert b._session_game_type == 10010101


def test_friend_room_disables_runtime_collection() -> None:
    b = BotBridge(max_auto_rebuy=3)
    b._my_seat = 0
    cash_enter = {
        "code": 0,
        "roomid": 20242379,
        "game_type": 10010101,
        "room_info": {"bb": 2.0, "sb": 1.0},
        "table_status": {"seat": []},
    }
    b.handle("pb.EnterRoomRSP", cash_enter)
    b.handle(
        "pb.DealerInfoRSP",
        {
            "dealer": 0,
            "small_blind": 1,
            "big_blind": 2,
            "start_info": [{"chips": "200"}, {"seatid": 1, "chips": "200"}],
            "gameid": "cash1",
        },
    )
    assert b._api is not None
    assert b._api._runtime_calibration_recorder is not None

    b.handle(
        "pb.EnterRoomRSP",
        {
            "code": 0,
            "roomid": 200001,
            "game_type": 20010103,
            "room_info": {"bb": 2.0, "sb": 1.0},
            "table_status": {"seat": []},
        },
    )
    assert b._skip_runtime_collection is True
    assert b._skip_runtime_collection_reason == "friend_room"
    assert b._api._runtime_calibration_recorder is None

    b.handle("pb.EnterRoomRSP", cash_enter)
    assert b._skip_runtime_collection is False
    assert b._skip_runtime_collection_reason == ""
    assert b._api._runtime_calibration_recorder is not None


def test_friend_room_game_type_disables_profit_lock(monkeypatch) -> None:
    import pf_intercept.bot as bot_mod

    notified = []
    monkeypatch.setattr(bot_mod, "notify", lambda event, **fields: notified.append(event))

    b = BotBridge(max_auto_rebuy=3)
    b._my_uid = "99"
    b._my_seat = 0
    b._uid_to_seat["99"] = 0
    b.handle(
        "pb.EnterRoomRSP",
        {
            "code": 0,
            "roomid": 200001,
            "game_type": 20010103,
            "room_info": {"bb": 2.0, "sb": 1.0},
            "table_status": {"seat": []},
        },
    )

    out = b.handle(
        "pb.WinnerRSP",
        {
            "winner": [],
            "profit": [{"uid": "99", "chips": "30000"}],
        },
    )

    assert b._is_friend_room is True
    assert b._skip_profit_lock is True
    assert b._skip_profit_lock_reason == "friend_room"
    assert out is None
    assert b._profit_lock_deferred is None
    assert "profit_lock_trigger" not in notified


def test_friend_room_info_disables_profit_lock_without_game_type(monkeypatch) -> None:
    import pf_intercept.bot as bot_mod

    notified = []
    monkeypatch.setattr(bot_mod, "notify", lambda event, **fields: notified.append(event))

    b = BotBridge(max_auto_rebuy=3)
    b._my_uid = "99"
    b._my_seat = 0
    b._uid_to_seat["99"] = 0
    b.handle(
        "pb.EnterRoomRSP",
        {
            "code": 0,
            "roomid": 200002,
            "game_type": 10010101,
            "room_info": {"bb": 2.0, "sb": 1.0},
            "friend_room_info": {
                "is_private": True,
                "owner_uid": "99",
                "owner_name": "hero",
            },
            "table_status": {"seat": []},
        },
    )

    out = b.handle(
        "pb.WinnerRSP",
        {
            "winner": [],
            "profit": [{"uid": "99", "chips": "30000"}],
        },
    )

    assert b._is_friend_room is True
    assert b._skip_profit_lock is True
    assert b._skip_profit_lock_reason == "friend_room"
    assert out is None
    assert b._profit_lock_deferred is None
    assert "profit_lock_trigger" not in notified


def test_friend_room_suppresses_bot_notifications(monkeypatch) -> None:
    import pf_intercept.bot as bot_mod

    notified = []
    monkeypatch.setattr(bot_mod, "notify", lambda event, **fields: notified.append(event))

    b = BotBridge(max_auto_rebuy=3)
    b._is_friend_room = True
    b._my_seat = 0
    b._bb = 50.0
    b._hand_start_chips[0] = 1000

    b._check_hand_swing(2000)

    assert notified == []


def test_hand_swing_triggers_at_twenty_bb_without_percent_gate(monkeypatch) -> None:
    import pf_intercept.bot as bot_mod

    notified = []
    monkeypatch.setattr(
        bot_mod,
        "notify",
        lambda event, **fields: notified.append((event, fields)),
    )

    b = BotBridge(max_auto_rebuy=3)
    b._my_seat = 0
    b._bb = 50.0
    b._hand_start_chips[0] = 100_000

    b._check_hand_swing(999)
    assert notified == []

    b._check_hand_swing(1_000)
    assert notified == [
        (
            "hand_swing",
            {
                "profit_delta": 1_000,
                "start_chips": 100_000,
                "big_blind": 50,
                "hand_detail": "",
            },
        )
    ]


def test_hand_swing_includes_last_hand_detail(monkeypatch) -> None:
    import pf_intercept.bot as bot_mod

    notified = []
    monkeypatch.setattr(
        bot_mod,
        "notify",
        lambda event, **fields: notified.append((event, fields)),
    )

    class FakeAPI:
        def last_hand_push_detail(self):
            return "手牌: A♠ A♥\n行动:\n翻前: 我加10bb"

    b = BotBridge(max_auto_rebuy=3)
    b._my_seat = 0
    b._bb = 50.0
    b._hand_start_chips[0] = 100_000
    b._hand_seq = 12
    b._api = FakeAPI()

    b._check_hand_swing(1_000)

    assert notified[0][1]["hand_detail"] == "手牌: A♠ A♥\n行动:\n翻前: 我加10bb"
    assert notified[0][1]["hand_no"] == 12
    assert "game_id" not in notified[0][1]


def test_profit_lock_threshold_in_config() -> None:
    assert isinstance(config.PROFIT_LOCK_BB_THRESHOLD, int)
    assert config.PROFIT_LOCK_BB_THRESHOLD >= 1


class _BoardApi:
    def __init__(self):
        self.calls = []

    def sync_board(self, cards, street, pot=None):
        self.calls.append(("sync", list(cards), street))


def _wire(cards):
    rank = "23456789TJQKA"
    suit = {"d": 1, "c": 2, "h": 3, "s": 4}
    return [suit[c[1]] * 256 + rank.index(c[0]) + 2 for c in cards]


def test_round_start_syncs_the_full_board_when_all_board_is_present():
    b = BotBridge()
    b._api = _BoardApi()
    flop = ["As", "Kd", "2c"]
    b._on_round_start({"stage": 2, "board": _wire(flop), "all_board": _wire(flop)})
    b._on_round_start({"stage": 2, "board": _wire(flop), "all_board": _wire(flop)})  # repeat is harmless
    b._on_round_start({"stage": 4, "board": _wire(["3c"]), "all_board": _wire(flop + ["9h", "3c"])})
    assert [c[:3] for c in b._api.calls] == [
        ("sync", flop, "flop"), ("sync", flop, "flop"),
        ("sync", flop + ["9h", "3c"], "river"),
    ]


def test_round_start_without_all_board_does_not_guess_the_board(caplog):
    b = BotBridge()
    b._api = _BoardApi()
    with caplog.at_level("ERROR"):
        b._on_round_start({"stage": 2, "board": _wire(["As", "Kd", "2c"])})
        b._on_round_start({"stage": 3, "board": _wire(["9h"])})
    assert b._api.calls == []
    assert sum("没有 all_board" in r.getMessage() for r in caplog.records) == 1  # reported once


def test_live_decisions_keep_this_hands_decisions_in_the_shape_the_page_reads() -> None:
    b = BotBridge()
    b._current_gameid = "g1"
    b._note_live_decision({"street": "flop", "action": "RAISE", "amount": 242915.0, "to_call": 0, "pot": 440000,
                           "equity": 0.49, "equity_random": 0.6, "spr": 3.5, "decision_source": "realtime_cfr",
                           "equity_mode": "range_v2", "elapsed_ms": 49.0, "reasoning": "first line\n│ second"})
    b._note_live_decision({"street": "turn", "action": "check", "amount": 0, "equity": 0.36, "pot": 925828})
    assert [d["street"] for d in b.live_decisions] == ["flop", "turn"]
    assert b.live_decisions[0] == {
        "game_id": "g1", "street": "flop", "action": "raise", "amount": 242915.0, "to_call": 0.0, "pot": 440000.0,
        "equity": 0.49, "equity_random": 0.6, "spr": 3.5, "engine": "realtime_cfr", "mode": "range_v2", "ms": 49.0,
        "why": "first line"}
    assert (b.live_decisions[1]["engine"], b.live_decisions[1]["spr"], b.live_decisions[1]["why"]) == ("", None, "")
    b._current_gameid = "g2"
    b._note_live_decision({"street": "preflop", "action": "fold"})
    assert [(d["game_id"], d["street"]) for d in b.live_decisions] == [("g2", "preflop")]
