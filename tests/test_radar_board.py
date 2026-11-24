"""The 雷达 tab: the ignore file the user edits, the board behind the tab, and its web route."""
import asyncio
import json

import pytest

from pf_entertainment.web import EntertainmentWebServer, _HttpRequest
from pf_intercept.headless.lobby.core.base import Worker
from pf_intercept.headless.lobby.core.ignore import Ignores, valid_key
from pf_intercept.headless.lobby.radar.board import Board, label


@pytest.mark.parametrize("key, ok", [("task:105", True), ("task:101:30030101", True), ("limit:101:10020101", True),
                                     ("table:invite_rules", True), ("period:creator_activity:50001", True),
                                     ("task:x", False), ("rm -rf /", False), (None, False)])
def test_valid_key(key, ok):
    assert valid_key(key) is ok


def test_the_users_decisions_are_written_listed_and_forgotten(tmp_path):
    path = tmp_path / "state" / "lobby_ignores.json"
    ignores = Ignores(internal={"task:325": "直播做不了"}, external_path=path)
    ignores.set("task:105", True, "不打锦标赛")
    ignores.set("task:325", False)
    assert set(json.loads(path.read_text())) == {"task:105", "task:325"}
    assert ignores.task(105) == ("不打锦标赛", "外部") and ignores.task(325) is None
    entries = {e["key"]: e for e in ignores.entries()}
    assert (entries["task:325"]["by"], entries["task:325"]["ignore"], entries["task:325"]["overridden"]) == ("内部", False, True)
    assert (entries["task:105"]["by"], entries["task:105"]["reason"]) == ("外部", "不打锦标赛")
    ignores.drop("task:325")
    assert ignores.task(325) == ("直播做不了", "内部")
    with pytest.raises(ValueError):
        ignores.set("not a key")


class Games(Worker):
    name, title, does, limits = "sidegames", "彩球机 / 弹球", {(101, 30030101): "彩球"}, {(101, 30030101): 100}


def test_the_board_shows_items_with_their_keys_and_takes_one_decision_at_a_time(tmp_path):
    board = Board(ignores=Ignores(internal={}, external_path=tmp_path / "ignores.json"), workers=([Games], ()))
    routine = next(f for f in board.state()["findings"] if f["key"] == "gaps:routine")
    keys = {item["key"] for item in routine["items"]}
    assert "task:105" in keys and all(valid_key(k) for k in keys)
    after = board.change({"action": "ignore", "key": "task:105", "reason": "不打锦标赛"})
    routine = next(f for f in after["findings"] if f["key"] == "gaps:routine")
    assert all(item["ignored"] == {"reason": "不打锦标赛", "by": "外部"} for item in routine["items"] if item["key"] == "task:105")
    assert [e["key"] for e in after["ignores"]] == ["task:105"] and after["ignores"][0]["label"].startswith("类型 105 的任务")
    assert board.change({"action": "reset", "key": "task:105"})["ignores"] == []
    with pytest.raises(ValueError):
        board.change({"action": "ignore", "key": "../etc"})


def test_label():
    assert label("task:105").startswith("类型 105 的任务，例：")
    assert label("table:invite_rules") == "邀请活动（整张表的每一期）"


class FakeBoard:
    def __init__(self):
        self.changes = []

    def state(self):
        return {"findings": [], "ignores": []}

    def change(self, body):
        if body.get("key") == "bad":
            raise ValueError("不认识的忽略键")
        self.changes.append(body)
        return self.state()


def request(method, body=b""):
    return _HttpRequest(method=method, target="/api/radar", path="/api/radar", query={}, headers={}, body=body)


def test_the_web_route_reads_and_changes_through_the_board():
    async def run():
        board = FakeBoard()
        web = EntertainmentWebServer(runtime=None, radar_board=board)
        status, _, body = await web._route(request("GET"))
        assert status == 200 and json.loads(body) == {"ok": True, "available": True, "findings": [], "ignores": []}
        status, _, _ = await web._route(request("POST", json.dumps({"action": "ignore", "key": "task:105"}).encode()))
        assert status == 200 and board.changes == [{"action": "ignore", "key": "task:105"}]
        status, _, body = await web._route(request("POST", b'{"key": "bad"}'))
        assert status == 400 and json.loads(body)["error"] == "不认识的忽略键"
        status, _, body = await web._route(request("POST", b"x" * 5000))
        assert status == 400
        status, _, body = await EntertainmentWebServer(runtime=None)._route(request("GET"))
        assert json.loads(body) == {"ok": True, "available": False}
    asyncio.run(run())
