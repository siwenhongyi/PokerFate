"""代币兑换类活动 (主题活动, 创作盛典): the shop plan, the exchange and the creator's task lists."""
import asyncio

import pytest

from pf_intercept.headless.lobby.activities import creator as cr
from pf_intercept.headless.lobby.activities import token_shop as ts
from pf_intercept.headless.lobby.activities.theme import Theme
from pf_intercept.headless.lobby.core.base import GOLD, Period
from tests.test_checkin_theme import Bag, setup
from tests.test_dispatch import journal

TOKEN, CRYSTAL = 10410010, 10200002


def good(ident, item, cost, limit, batch=False, count=1, index=0):
    return ts.Good(ident, item, count, TOKEN, cost, limit, batch, index)


CRYSTALS, GIFT, CHIPS = good(1, CRYSTAL, 1000, 2), good(2, 10601003, 250, 5, batch=True), good(3, GOLD, 100, 5000, True, 1000)


def test_goods_of_the_clients_rows():
    rows = [{"id": 1001016, "props": [1, GOLD, 1000], "exchange_cost": [TOKEN, 100], "limit_count": 5000, "batch": 1, "index": 3},
            {"id": 1001001, "props": [1, CRYSTAL, 1], "exchange_cost": [TOKEN, 1000], "limit_count": 2, "batch": None}]
    assert ts.goods_of(rows) == [ts.Good(1001016, GOLD, 1000, TOKEN, 100, 5000, True, 3),
                                 ts.Good(1001001, CRYSTAL, 1, TOKEN, 1000, 2, False, 0)]


@pytest.mark.parametrize("bought, tokens, expect", [
    ({}, 3000, [(CRYSTALS, 2), (CHIPS, 10)]),                  # the chips take the rest
    ({1: 2}, 3000, [(CHIPS, 30)]),
    ({}, 900, []),                                             # saving up for the crystals
    ({1: 2, 3: 4999}, 1000, [(CHIPS, 1), (GIFT, 3)]),          # the last chips the limit leaves, then gifts
    ({1: 2, 2: 5, 3: 5000}, 1000, []),                         # everything bought
])
def test_plan(bought, tokens, expect):
    assert ts.plan([CRYSTALS, CHIPS, GIFT], bought, tokens) == expect


def test_the_buying_order():
    pack, decoration = good(7, 30300002, 500, 2, index=2), good(4, 20402011, 900, 1, index=1)
    order = sorted([decoration, CHIPS, pack, GIFT, CRYSTALS], key=ts.rank)
    assert order == [CRYSTALS, CHIPS, GIFT, pack, decoration]


def test_the_tokens_buy_the_plan_and_the_chips_count_as_rewards(tmp_path, monkeypatch):
    async def run():
        limits = lambda counts: (ts.LIMITS, {"code": 0, "list": [{"shop_type": 20001, "id": i, "count": n}  # noqa: E731
                                                                for i, n in counts.items()]})
        replies = [limits({}),
                   (ts.BUY, {"code": 0}), (ts.BUY, {"code": 0}),        # the crystals, one at a time
                   (ts.BUY, {"code": 0}),                               # four gifts in one request
                   limits({1: 2, 2: 4})]
        worker, http, credits = setup(tmp_path, replies, Theme, 1_000_000, bag=Bag({TOKEN: 3000}))
        monkeypatch.setattr(worker, "goods", lambda found: [CRYSTALS, GIFT, CHIPS])
        found = Period("theme_activity", 10010, {"activity_item": TOKEN}, 0, 2_000_000)
        await worker.exchange(found)
        buys = [payload for endpoint, payload in http.calls if endpoint == ts.BUY]
        assert buys == [{"shop_type": 20001, "id": 1, "num": 1, "mask": "buyWithProp"}] * 2 + [
            {"shop_type": 20001, "id": 2, "num": 4, "mask": "buyWithProp"}]
        assert not http.replies and credits == [] and not journal(tmp_path, "theme_blocked")
        # the chips, once the rest is bought: 1000 for every 100 tokens, counted as a reward
        http.replies.extend([limits({1: 2, 2: 5}), (ts.BUY, {"code": 0}), limits({1: 2, 2: 5, 3: 3})])
        worker.session = Bag({TOKEN: 300})
        await worker.exchange(found)
        assert credits == [(3000, False)]
    asyncio.run(run())


def test_a_buy_the_shop_does_not_count_is_left_alone(tmp_path, monkeypatch):
    async def run():
        replies = [(ts.LIMITS, {"code": 0, "list": []}), (ts.BUY, {"code": 0}), (ts.LIMITS, {"code": 0, "list": []})]
        worker, http, _ = setup(tmp_path, replies, Theme, 1_000_000, bag=Bag({TOKEN: 100}))
        monkeypatch.setattr(worker, "goods", lambda found: [CHIPS])
        await worker.exchange(Period("theme_activity", 10010, {"activity_item": TOKEN}, 0, 2_000_000))
        assert journal(tmp_path, "theme_blocked")[0]["action"] == "buy:3"
    asyncio.run(run())


def test_the_creators_daily_and_activity_tasks_are_read_and_claimed_by_their_list(tmp_path):
    async def run():
        lists = {"code": 0, "daily_list": [{"id": 1, "status": 2}], "version_list": [{"id": 7, "status": 2}],
                 "creator_list": [{"id": 9, "status": 2}]}
        worker, http, _ = setup(tmp_path, [(cr.TASKS, lists), (cr.CLAIM, {"code": 0, "item_list": []}),
                                           (cr.CLAIM, {"code": 0, "item_list": []})], cr.Creator, 1_000_000)
        rows = await worker.task_rows(None)
        assert [(r["id"], r["_cate"]) for r in rows] == [(1, 12), (7, 13)]       # not the creators' own list
        assert await worker.claim(None, rows) == [1, 7]
        assert http.calls[1:] == [(cr.CLAIM, {"task_cate": 12, "id_arr": [1]}), (cr.CLAIM, {"task_cate": 13, "id_arr": [7]})]
    asyncio.run(run())
