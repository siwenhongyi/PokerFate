import time

import pytest

from pf_entertainment.live_table import LiveTableObserver
from pf_entertainment.showdown import hand_group


def codes(cards):
    rank = "23456789TJQKA"
    suit = {"d": 1, "c": 2, "h": 3, "s": 4}
    return [suit[c[1]] * 256 + rank.index(c[0]) + 2 for c in cards]


def reveal(seat, cards):
    return {"seatid": seat, **dict(zip(("card1", "card2"), codes(cards)))}


def observer():
    obs = LiveTableObserver(my_uid="hero")
    obs.observe("pb.EnterRoomRSP", {"roomid": 42, "table_status": {"seat": [
        {"player": {"uid": "villain", "name": "赢家"}},
        {"seatid": 1, "player": {"uid": "hero", "name": "我"}},
        {"seatid": 2, "player": {"uid": "other", "name": "另一玩家"}},
    ]}})
    obs.observe("pb.DealerInfoRSP", {"gameid": "hand-1"})
    obs.observe("pb.HandCardRSP", reveal(1, ["As", "Ad"]))
    obs.observe("pb.RoundStartBRC", {"stage": 4, "board": codes(["Ah", "Kd", "Ks", "2c", "3c"])})
    return obs


@pytest.mark.parametrize("hole,board,label,ordered", [
    (["As", "2d"], ["3c", "4h", "5s", "9d", "Tc"], "顺子", "5432A"),
    (["Ks", "Kd"], ["Kh", "2c", "2d", "Ac", "Qd"], "葫芦", "KKK22"),
    (["As", "Ad"], ["Kc", "Kd", "7s", "5c", "2d"], "两对", "AAKK7"),
    (["As", "Ad"], ["Ac", "Ah", "Kd", "7c", "2d"], "四条", "AAAAK"),
    (["2c", "3d"], ["Ts", "Js", "Qs", "Ks", "As"], "皇家同花顺", "AKQJT"),
    (["As", "2s"], ["Ks", "9s", "6s", "3s", "Ah"], "同花", "AK963"),
])
def test_best_five_uses_holdem_rules(hole, board, label, ordered):
    result = hand_group(hole, board)
    assert result["label"] == label
    assert "".join(c[0] for c in result["cards"]) == ordered
    assert len(result["hole_used"]) == 5
    if label == "皇家同花顺":
        assert result["hole_used"] == [False] * 5
        assert "公共牌成牌" in result["note"]


def test_unknown_cards_never_invent_best_five_even_if_board_plays():
    group = hand_group(["As", None], ["2d", "2c", "2h", "Ks", "7s"], server_type=7)
    assert group["label"] == "葫芦" and group["source"] == "server"
    assert not group["cards"] and "未完整公开" in group["note"]
    assert hand_group(["As", "Kd"], [])["label"] == "未成五张牌"
    assert not hand_group(["As", "As"], ["2d", "3c", "4h"])["cards"]


def test_showdown_folded_hero_and_multiple_winners_survive_next_hand():
    obs = observer()
    obs.observe("pb.ActionBRC", {"seatid": 1, "action_type": 1})
    obs.observe("pb.ShowHandRSP", {"info": [reveal(0, ["Kc", "Kh"]), reveal(2, ["Ac", "3d"])]})
    obs.observe("pb.WinnerRSP", {"winner": [
        {"uid": "villain", "chips": 100, "poolid": 0, "type": 8},
        {"uid": "villain", "chips": 50, "poolid": 1, "type": 8},
        {"uid": "other", "seatid": 2, "chips": 30, "poolid": 2, "type": 3},
    ]})
    snapshot = obs.snapshot()
    result = snapshot["settlement"]
    assert snapshot["seats"][0]["cards"] == ["Kc", "Kh"]
    assert snapshot["seats"][0]["revealed"]
    assert len(result["revealed"]) == 2
    assert len(result["winners"]) == 2
    assert result["winners"][0]["chips"] == 150
    assert result["winners"][0]["group"]["label"] == "四条"
    assert result["hero"]["folded"]
    assert result["hero"]["group"]["label"] == "葫芦"
    obs.observe("pb.DealerInfoRSP", {"gameid": "hand-2"})
    obs.observe("pb.HandCardRSP", reveal(1, ["7c", "8c"]))
    next_hand = obs.snapshot()
    assert next_hand["game_id"] == "hand-2" and next_hand["board"] == []
    assert next_hand["seats"][0]["cards"] == []
    assert next_hand["settlement"] == result
    # Snapshot consumers cannot mutate the retained result.
    next_hand["settlement"]["hero"]["hole"].clear()
    assert obs.snapshot()["settlement"]["hero"]["hole"] == ["As", "Ad"]


def test_partial_voluntary_reveal_after_next_hand_updates_old_result_only():
    obs = observer()
    obs.observe("pb.WinnerRSP", {"winner": [{"uid": "villain", "type": 8, "chips": 100}]})
    first = obs.snapshot()["settlement"]
    assert first["winners"][0]["group"]["label"] == "四条"
    assert not first["winners"][0]["group"]["cards"]
    obs.observe("pb.DealerInfoRSP", {"gameid": "hand-2"})
    obs.observe("pb.ShowMyCardBRC", {"gameid": "hand-1", "info": [{"hand_cards": [0, codes(["Kh"])[0]]}]})
    partial = obs.snapshot()
    assert partial["seats"][0]["cards"] == []
    assert partial["settlement"]["revealed"][0]["hole"] == [None, "Kh"]
    assert not partial["settlement"]["winners"][0]["group"]["cards"]
    obs.observe("pb.ShowMyCardBRC", {"gameid": "hand-1", "info": [{"hand_cards": [codes(["Kc"])[0], 0]}]})
    finished = obs.snapshot()["settlement"]
    assert finished["id"] == first["id"] and finished["ended_at"] == first["ended_at"]
    assert finished["winners"][0]["group"]["label"] == "四条"
    assert len(finished["winners"][0]["group"]["cards"]) == 5
    obs.observe("pb.ShowMyCardBRC", {"gameid": "unrelated", "info": [reveal(0, ["2d", "3d"])]})
    assert obs.snapshot()["settlement"] == finished


def test_repeated_result_does_not_restart_reveal_timer():
    obs = observer()
    winner = {"winner": [{"uid": "villain", "type": 2, "chips": 100}]}
    obs.observe("pb.WinnerRSP", winner)
    first = obs.snapshot()["settlement"]
    obs.observe("pb.WinnerRSP", winner)
    assert obs.snapshot()["settlement"] == first


def test_result_survives_leaving_and_reentering_table():
    obs = observer()
    obs.observe("pb.WinnerRSP", {"winner": [{"uid": "hero", "type": 7, "chips": 100}]})
    result = obs.snapshot()["settlement"]
    obs.observe("pb.LeaveRoomRSP", {"roomid": 42})
    assert obs.snapshot()["room_id"] == 0
    assert obs.snapshot()["settlement"] == result
    obs.observe("pb.EnterRoomRSP", {"roomid": 43})
    assert obs.snapshot()["settlement"] == result
    obs.observe("pb.DealerInfoRSP", {"gameid": "new-room-hand"})
    obs.observe("pb.HandCardRSP", reveal(0, ["3d", "4d"]))
    obs.observe("pb.WinnerRSP", {"winner": [{"seatid": 0, "chips": 50}]})
    assert obs.snapshot()["settlement"]["id"] != result["id"]
    assert obs.snapshot()["settlement"]["hero"]["hole"] == ["3d", "4d"]


def test_reconnect_recovers_known_hero_cards():
    obs = LiveTableObserver(my_uid="hero")
    obs.observe("pb.EnterRoomRSP", {"roomid": 42,
        "table_status": {"gameid": "reconnected", "board": codes(["2d", "3h", "4s"]),
                         "seat": [{"player": {"uid": "hero", "name": "我"}}]},
        "playing_status": reveal(0, ["As", "5d"])})
    obs.observe("pb.WinnerRSP", {"winner": [{"uid": "hero", "type": 5}]})
    assert obs.snapshot()["settlement"]["hero"]["group"]["label"] == "顺子"


def test_observer_settlement_is_fast_enough_for_frame_hook():
    obs = observer()
    obs.observe("pb.ShowHandRSP", {"info": [reveal(0, ["Kc", "Kh"]), reveal(2, ["Ac", "3d"])]})
    started = time.perf_counter()
    for _ in range(100):
        obs.observe("pb.WinnerRSP", {"winner": [{"uid": "villain", "type": 8, "chips": 100}]})
    assert (time.perf_counter() - started) / 100 < 0.02
