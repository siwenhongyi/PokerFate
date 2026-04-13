"""pf_intercept BotBridge: profit-lock leave / re-enter and auto-rebuy cap."""

from pf_intercept import config
from pf_intercept.bot import BotBridge


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
        b = BotBridge(max_auto_rebuy=3)
        b._my_uid = "99"
        self._bootstrap_table(b)
        b._uid_to_seat["99"] = 0
        bb = 2.0
        thr_chips = int(config.PROFIT_LOCK_BB_THRESHOLD * bb)
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
