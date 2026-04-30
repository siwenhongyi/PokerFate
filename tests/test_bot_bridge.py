"""pf_intercept BotBridge: profit-lock leave / re-enter and auto-rebuy cap."""

from pf_intercept import config
from pf_intercept.bot import BotBridge


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


class TestBotBridgeProfitLock:
    def _next_hand_dealer(self, bridge: BotBridge, gameid: str = "t_next"):
        """盈利锁仓达标后需再收到一手 DealerInfo 才会注入 LeaveRoomREQ。"""
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
        assert not b._profit_lock_award_rebuy_after_enter

    def test_winner_triggers_leave_then_enter_then_award(self) -> None:
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
        assert out is None
        assert b._profit_lock_deferred is not None
        assert b._profit_lock_deferred["roomid"] == rid
        assert b._profit_lock_deferred["byin_chips"] == int(100 * bb)
        assert not b._profit_lock_award_rebuy_after_enter

        out_leave = self._next_hand_dealer(b)
        assert out_leave[0] == "pb.LeaveRoomREQ"
        assert out_leave[1] == {"seat_reserve": bool(getattr(config, "PROFIT_LOCK_LEAVE_SEAT_RESERVE", True))}
        assert out_leave[2] == 0.0
        assert b._profit_lock_deferred is None
        assert b._profit_lock_reenter is not None
        assert b._profit_lock_reenter["roomid"] == rid
        assert b._profit_lock_reenter["byin_chips"] == int(100 * bb)
        assert b._profit_lock_award_rebuy_after_enter

        out2 = b.handle("pb.LeaveRoomRSP", {"code": 0})
        assert out2[0] == "pb.EnterRoomREQ"
        assert out2[1]["roomid"] == rid
        assert out2[1]["byin_chips"] == 200
        assert out2[1]["uid"] == 99
        exp_delay = max(0.0, min(60.0, float(getattr(config, "PROFIT_LOCK_REENTER_DELAY_SEC", 2.0))))
        assert out2[2] == exp_delay
        assert b._profit_lock_reenter is None
        assert b._profit_lock_award_rebuy_after_enter

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
        assert b._max_auto_rebuy == 4
        assert not b._profit_lock_award_rebuy_after_enter

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
        self._next_hand_dealer(b)
        out = b.handle(
            "pb.LeaveRoomRSP",
            {"roomid": rid, "game_type": 1},
        )
        assert out is not None and out[0] == "pb.EnterRoomREQ"
        assert out[1]["roomid"] == rid
        assert out[1]["byin_chips"] == 200
        assert len(out) == 3

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
        self._next_hand_dealer(b)
        out = b.handle("pb.LeaveRoomRSP", {"code": -1})
        assert out is None
        assert b._profit_lock_reenter is None
        assert not b._profit_lock_award_rebuy_after_enter
        assert b._max_auto_rebuy == 3

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
        self._next_hand_dealer(b)
        b.handle("pb.LeaveRoomRSP", {"code": 0})
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
        assert not b._profit_lock_award_rebuy_after_enter


class TestProfitLockDisplayPnL:
    """Session PnL is display-only. It accumulates at leave-success
    (+= table_chips) and gets debited on rebuy/reenter (-= 100 BB).
    The trigger condition is on-table chips (my_final), NOT PnL.
    """

    def _setup(self, bb: float = 2.0, room_id: int = 20242379):
        helper = TestBotBridgeProfitLock()
        b = BotBridge(max_auto_rebuy=5)
        b._my_uid = "99"
        helper._bootstrap_table(b, room_id=room_id)
        b._uid_to_seat["99"] = 0
        return b

    def test_winning_a_hand_does_not_change_pnl(self):
        """Per-hand profit does NOT accumulate into _session_pnl_chips.
        PnL is booked only at leave-success + rebuy/reenter.
        (Earlier versions tried per-hand delta; rake made it noisy.)"""
        b = self._setup()
        assert b._session_pnl_chips == 0.0
        b.handle(
            "pb.WinnerRSP",
            {"winner": [], "profit": [{"uid": "99", "chips": 150}]},
        )
        assert b._session_pnl_chips == 0.0

    def test_auto_rebuy_debits_pnl(self):
        """Hero busts → NoticeReby → auto rebuy path debits 100 BB."""
        b = self._setup()
        bb = 2.0
        rebuy_chips = int(100 * bb)
        b.handle("pb.NoticeRebyRSP", {"seatid": 0, "reby_left_time": 30})
        assert b._session_pnl_chips == -rebuy_chips

    def test_full_profit_lock_cycle_books_table_chips_minus_buyin(self):
        """Full cycle: trigger → leave → reenter.
        PnL gain = table_chips brought away − 100 BB reenter buyin."""
        b = self._setup()
        bb = 2.0
        thr_chips = int(config.PROFIT_LOCK_BB_THRESHOLD * bb)   # 800 for 400 BB at BB=2
        # Bring on-table chips to exactly threshold (hero started 200).
        b.handle(
            "pb.WinnerRSP",
            {"winner": [], "profit": [{"uid": "99", "chips": thr_chips - 200}]},
        )
        assert b._profit_lock_deferred is not None
        # Next hand DealerInfo → LeaveRoomREQ
        TestBotBridgeProfitLock()._next_hand_dealer(b)
        # LeaveRoomRSP success → PnL += table_chips (= thr_chips)
        b.handle("pb.LeaveRoomRSP", {"code": 0})
        assert b._session_pnl_chips == thr_chips
        # EnterRoomRSP success → buyin deducted on award path (-100 BB)
        b.handle(
            "pb.EnterRoomRSP",
            {
                "code": 0, "roomid": 20242379, "game_type": 10010101,
                "room_info": {"bb": 2.0, "sb": 1.0, "lobby_coin": 10100001},
                "table_status": {"seat": []},
            },
        )
        assert b._session_pnl_chips == thr_chips - int(100 * bb)

    def test_trigger_uses_on_table_not_pnl(self):
        """Regression: even if PnL is 0 (first-ever trigger), on-table
        chips above threshold MUST fire. This is the dead-lock regression —
        earlier code gated on PnL and the first trigger was unreachable."""
        b = self._setup()
        bb = 2.0
        thr_chips = int(config.PROFIT_LOCK_BB_THRESHOLD * bb)
        assert b._session_pnl_chips == 0.0     # starting state
        out = b.handle(
            "pb.WinnerRSP",
            {"winner": [], "profit": [{"uid": "99", "chips": thr_chips - 200}]},
        )
        assert out is None
        assert b._profit_lock_deferred is not None, (
            "first-ever trigger MUST fire from on-table chips alone "
            "(dead-lock regression: trigger that gated on PnL was unreachable)"
        )

    def test_trigger_ignores_negative_pnl_history(self):
        """Even after many rebuys (PnL deep negative), if hero's on-table
        stack crosses threshold in one lucky hand, profit_lock fires."""
        b = self._setup()
        bb = 2.0
        thr_chips = int(config.PROFIT_LOCK_BB_THRESHOLD * bb)
        # Simulate heavy prior losses (display-only)
        b._session_pnl_chips = -5 * int(100 * bb)    # -500 BB
        # But hero's on-table chips just crossed threshold.
        out = b.handle(
            "pb.WinnerRSP",
            {"winner": [], "profit": [{"uid": "99", "chips": thr_chips - 200}]},
        )
        assert out is None
        assert b._profit_lock_deferred is not None, (
            "PnL is display-only — trigger must still fire on on-table chips"
        )


def test_enter_room_syncs_hand_start_chips_from_table() -> None:
    """重进房后必须用 table_status.hand_chips 覆盖 DealerInfo 留下的 _hand_start_chips。"""
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
                    },
                ],
            },
        },
    )
    assert b._my_seat == 5
    assert b._hand_start_chips[5] == 100000
    assert b._seat_chips[5] == 100000


def test_enter_room_uses_sngroom_info_blinds_when_room_info_empty() -> None:
    """SNG EnterRoomRSP has room_info={}, so blinds must come from sngroom_info."""
    b = BotBridge(max_auto_rebuy=3)
    b._my_seat = 0
    b._bb = 10000.0
    b._sb = 5000.0

    b.handle(
        "pb.EnterRoomRSP",
        {
            "code": 0,
            "roomid": 20399792,
            "game_type": 10050301,
            "room_info": {},
            "sngroom_info": {
                "blind_level": 1,
                "sb": "25",
                "bb": "50",
                "blind_list": [
                    {"blind_level": 1, "small_blind": "25", "big_blind": "50"},
                    {"blind_level": 2, "small_blind": "50", "big_blind": "100"},
                ],
            },
            "table_status": {"seat": []},
        },
    )

    assert b._bb == 50.0
    assert b._sb == 25.0

    b.handle(
        "pb.DealerInfoRSP",
        {
            "dealer": 0,
            "small_blind": 1,
            "big_blind": 2,
            "start_info": [{"chips": "1000"}, {"seatid": 1, "chips": "1000"}],
            "gameid": "sng1",
        },
    )
    assert b._api is not None
    assert b._api.big_blind == 50.0
    assert b._api.small_blind == 25.0


def test_blind_status_updates_sng_blinds_from_cached_schedule() -> None:
    b = BotBridge(max_auto_rebuy=3)
    b._my_seat = 0
    b.handle(
        "pb.EnterRoomRSP",
        {
            "code": 0,
            "roomid": 20399792,
            "game_type": 10050301,
            "room_info": {},
            "sngroom_info": {
                "blind_level": 1,
                "blind_list": [
                    {"blind_level": 1, "small_blind": "25", "big_blind": "50"},
                    {"blind_level": 2, "small_blind": "50", "big_blind": "100"},
                ],
            },
            "table_status": {"seat": []},
        },
    )
    b.handle(
        "pb.DealerInfoRSP",
        {
            "dealer": 0,
            "small_blind": 1,
            "big_blind": 2,
            "start_info": [{"chips": "1000"}, {"seatid": 1, "chips": "1000"}],
            "gameid": "sng1",
        },
    )

    b.handle("pb.BlindStatusBRC", {"blind_level": 2, "upblind_time": 60})

    assert b._bb == 100.0
    assert b._sb == 50.0
    assert b._api is not None
    assert b._api.big_blind == 100.0
    assert b._api.small_blind == 50.0


def test_sng_disables_profit_lock_even_above_threshold(monkeypatch) -> None:
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
            "roomid": 20399792,
            "game_type": 10050301,
            "room_info": {},
            "sngroom_info": {
                "blind_level": 1,
                "sb": "25",
                "bb": "50",
            },
            "table_status": {"seat": []},
        },
    )
    b.handle(
        "pb.DealerInfoRSP",
        {
            "dealer": 0,
            "small_blind": 1,
            "big_blind": 2,
            "start_info": [{"chips": "1000"}, {"seatid": 1, "chips": "1000"}],
            "gameid": "sng1",
        },
    )

    out = b.handle(
        "pb.WinnerRSP",
        {
            "winner": [],
            "profit": [{"uid": "99", "chips": "30000"}],
        },
    )

    assert out is None
    assert b._profit_lock_deferred is None
    assert b._profit_lock_reenter is None
    assert "profit_lock_trigger" not in notified


def test_sng_suppresses_bot_notifications(monkeypatch) -> None:
    import pf_intercept.bot as bot_mod

    notified = []
    monkeypatch.setattr(bot_mod, "notify", lambda event, **fields: notified.append(event))

    b = BotBridge(max_auto_rebuy=3)
    b._is_sng_room = True
    b._my_seat = 0
    b._bb = 50.0
    b._hand_start_chips[0] = 1000

    b._check_hand_swing(2000)
    out = b.handle("pb.NoticeRebyRSP", {"seatid": 0, "reby_left_time": 30})

    assert out is not None and out[0] == "pb.RebyREQ"
    assert notified == []


def test_profit_lock_threshold_in_config() -> None:
    assert isinstance(config.PROFIT_LOCK_BB_THRESHOLD, int)
    assert config.PROFIT_LOCK_BB_THRESHOLD >= 1


def test_room_escape_two_busts_then_quickstart() -> None:
    """连续破产 2 次（仍可自动续入）：第二弹离桌并以 QuickStart 换桌。"""
    b = BotBridge(max_auto_rebuy=5)
    b._my_seat = 0
    b._bb = 1000.0
    b._table_room_id = 42
    b._session_game_type = 10010101
    b._session_lobby_coin = 10100001
    r1 = b.handle("pb.NoticeRebyRSP", {"seatid": 0, "reby_left_time": 30})
    assert r1 is not None
    assert r1[0] == "pb.RebyREQ"
    assert b._room_escape_bust_count == 1
    assert b._auto_rebuy_done == 1
    r2 = b.handle("pb.NoticeRebyRSP", {"seatid": 0, "reby_left_time": 30})
    assert r2 is not None
    assert r2[0] == "pb.LeaveRoomREQ"
    assert r2[1]["seat_reserve"] is False
    assert b._room_escape_reenter == {"quickstart": True}
    r3 = b.handle("pb.LeaveRoomRSP", {"code": 0})
    assert r3 is not None
    assert r3[0] == "pb.QuickStartREQ"
    assert r3[1]["byin_chips"] == 100_000
    assert b._room_escape_reenter is None
