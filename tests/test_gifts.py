"""礼物 and the table chat: scripted replies, no real game requests."""
import asyncio
from unittest.mock import AsyncMock

from pf_intercept.headless.lobby.core.needs import shop_key, task_key
from pf_intercept.headless.lobby.core.service import RewardService
from pf_intercept.headless.lobby.doers import gifts as gf
from pf_intercept.headless.lobby.doers import reports as rp

NOW = 1_795_500_000
CHEAP, DEAR = 10601003, 10602003            # 新月酿 (1 fragment), 天狗精酿 (4)


class Game:
    def __init__(self, gifts, fragments=0, sent=0):
        self.gifts, self.fragments, self.asked, self.sent = dict(gifts), fragments, [], sent

    async def activity_request(self, name, fields, room=None):
        self.asked.append((name, fields))
        if name == "ItemList":
            rows = [{"item_id": item, "item_uniq_id": f"u{item}", "num": n} for item, n in self.gifts.items() if n]
            return {"item_list": rows + [{"item_id": gf.FRAGMENT, "num": self.fragments}]}
        if name == "RoleList":
            return {"using_role_id": 1008, "role_list": [{"role_id": 1001}, {"role_id": 1008}], "send_gift_cnt": self.sent}
        if name == "RecycleItem":
            unit = fields["req_item_list"][0]
            item = int(unit["item_uniq_id"][1:])
            self.gifts[item] -= unit["item_num"]
            self.fragments += unit["item_num"] * gf.fragments_of(item)
            return {"reward_list": [{"decompose_item": {"item_id": gf.FRAGMENT, "num": unit["item_num"]}}]}
        return {"send_gift_cnt": 1}


def service(tmp_path, rows):
    svc = RewardService(uid=5, authorization="x", http_base="", chnl=1, version="1", on_credit=AsyncMock(),
                        ready=asyncio.Event(), journal_path=tmp_path / "rewards.jsonl")
    svc.now = lambda: NOW
    svc._request = AsyncMock(return_value={"code": 0})
    svc.needs.want("tasks", rows)
    return svc


def row(kind, value):
    return {"task_type": kind, "status": 1, "value": value, "current_value": 0}


def test_spare_gifts():
    assert gf.spare_gifts([(1, CHEAP, "a", 5), (2, DEAR, "b", 4)], reserve=7) == [(2, DEAR, "b", 2)]
    assert gf.spare_gifts([(1, CHEAP, "a", 5)], reserve=7) == []


def test_the_fragment_shop_and_the_gifts_from_the_tables():
    assert gf.fragment_good(16001) == (70, 1)                   # 结缘晶片: 70 fragments, one a week
    assert gf.fragments_of(CHEAP) == 1 and gf.fragments_of(DEAR) == 4
    bag = {"item_list": [{"item_id": DEAR, "item_uniq_id": "a", "num": 2}, {"item_id": CHEAP, "item_uniq_id": "b", "num": 1},
                         {"item_id": 10100001, "item_uniq_id": "c", "num": 9}]}
    assert gf.gifts_in(bag, NOW) == [(1, CHEAP, "b", 1), (2, DEAR, "a", 2)]


def test_the_cheapest_gift_is_given_to_the_player_in_use_and_another_recycled(tmp_path):
    async def run():
        svc = service(tmp_path, [row(201, [1]), row(310, [1])])
        game = Game({CHEAP: 2, DEAR: 1})
        await gf.Gifts(svc, game).check()
        assert ("RoleGift", {"role_id": 1008, "item_uniq_id": f"u{CHEAP}"}) in game.asked
        assert ("RecycleItem", {"req_item_list": [{"item_uniq_id": f"u{CHEAP}", "item_num": 1}]}) in game.asked
        assert svc.needs.lacking(task_key(201)) == {} and svc.needs.lacking(task_key(310)) == {}
    asyncio.run(run())


def test_the_receiver_is_a_player_whose_affection_is_not_full():
    full = {"level": gf.AWAKEN_LEVEL}
    players = [{"role_id": 1008, "level_info": full}, {"role_id": 1001, "level_info": {"level": 2}},
               {"role_id": 1006, "level_info": {"level": 1}, "is_star": True},
               {"role_id": 1007, "level_info": {"level": 4}, "expire_time": NOW - 1}]       # a trial that ended
    assert gf.receiver({"using_role_id": 1008, "role_list": players}, NOW) == 1006          # starred
    players[2]["is_star"] = False
    assert gf.receiver({"using_role_id": 1008, "role_list": players}, NOW) == 1001          # the higher bond level
    assert gf.receiver({"using_role_id": 1006, "role_list": players}, NOW) == 1006          # the one in use
    everyone_full = [{"role_id": 1008, "level_info": full}, {"role_id": 1001, "level_info": full}]
    assert gf.receiver({"using_role_id": 1008, "role_list": everyone_full}, NOW) == 1008


def test_no_gift_once_the_days_gifts_are_given(tmp_path):
    async def run():
        svc = service(tmp_path, [row(201, [1])])
        game = Game({CHEAP: 2}, sent=gf.daily_gifts())
        await gf.Gifts(svc, game).check()
        assert not [name for name, _ in game.asked if name == "RoleGift"]
    asyncio.run(run())


def test_the_fragments_short_come_from_the_gifts_beyond_the_reserve(tmp_path):
    async def run():
        svc = service(tmp_path, [row(313, [16, 16001, 1])])
        game = Game({CHEAP: 10, DEAR: 30}, fragments=10)
        svc.workers = {}
        worker = gf.Gifts(svc, game)
        worker.held = AsyncMock(return_value=10)
        await worker.check()
        recycled = [f["req_item_list"][0] for name, f in game.asked if name == "RecycleItem"]
        # 60 fragments short: the 3 cheap gifts beyond the 7 kept, then 15 dear ones
        assert recycled == [{"item_uniq_id": f"u{CHEAP}", "item_num": 3}, {"item_uniq_id": f"u{DEAR}", "item_num": 15}]
        assert svc._request.await_args.args == (gf.BUY, {"shop_type": 16, "id": 16001, "num": 1, "mask": "buyWithProp"})
        assert svc.needs.lacking(shop_key(16, 16001)) == {}
    asyncio.run(run())


def test_quick_chat_and_emoji_are_said_at_the_table_before_their_reports(tmp_path):
    async def run():
        svc = service(tmp_path, [row(304, [1, 1]), row(304, [2, 1])])
        game = Game({})
        game.activity_table = lambda: (77, 4242)
        game.send = AsyncMock(return_value=True)
        await rp.Reports(svc, game).check()
        game.send.assert_any_await("pb.TextREQ", {"id": rp.quick_chat(1008)}, 77)
        game.send.assert_any_await("pb.FaceREQ", {"id": rp.emoji_of(1008)}, 77)
        reports = [c.args for c in svc._request.await_args_list]
        assert ("/task/report", {"task_type": 304, "id": 1}) in reports and ("/task/report", {"task_type": 304, "id": 2}) in reports
    asyncio.run(run())


def test_quick_chat_line_and_emoji_of_a_player():
    assert rp.quick_chat(1001) and rp.emoji_of(1001)
    assert rp.first_role() == 1001
