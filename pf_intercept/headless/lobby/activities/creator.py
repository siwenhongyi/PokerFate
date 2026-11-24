"""创作盛典 (creator activity: 50001, 12-01 → 12-31 UTC+8). CreatorModel.lua (client 1.7.7).

The token-shop template (``token_shop.py``): the server names the period (``creatorActivity``),
the client's tpl_creator_activity row gives its token (创作回响). Of its three task lists the
daily (category 12) and the activity tasks (13) are hands and side-game rounds anyone plays and
go on the needs board; the creator tasks (14: streams and videos) are for certified creators.

The shop (tpl_shop_creator_activity, shop 50001) sells 结缘晶片 ×2 (800 each), gift packs and
1000 chips for 10 tokens (limit 1000). The tasks pay a few thousand tokens in a month, not
enough for everything: the template's order (结缘晶片, chips, gift packs) decides what they buy.
"""
from __future__ import annotations

from pf_intercept.headless.lobby.activities.token_shop import TokenShop, ready
from pf_intercept.headless.lobby.core.base import rows_of

DATA, TASKS, CLAIM = "/activity/creatorActivity", "/task/creatorTaskList", "/task/recCreatorTaskRw"
LISTS = (("daily_list", 12), ("version_list", 13))      # the creator list (14) is for creators
CREATOR_SHOP = 50001


class Creator(TokenShop):
    name = "creator"
    title = "创作者活动"
    switch = ("creator", "不做创作者活动（创作盛典）的任务和兑换，其余奖励照常")
    tables = ("creator_activity",)
    leaves = ("创作任务（直播、投稿）只给认证创作者",)
    shop_table, shop_column, shop_type = "shop_creator_activity", "creator_activity_id", CREATOR_SHOP

    async def current(self):
        data = await self.ask("data", DATA, {})
        info = (data or {}).get("data")
        return info.get("id") if isinstance(info, dict) else 0

    async def task_rows(self, found):
        if self.blocked("tasks"):
            return None
        data = await self.ask("tasks", TASKS, {"task_cate": 0})
        if data is None:
            return None
        return [dict(r, _cate=cate) for key, cate in LISTS for r in rows_of(data.get(key)) if isinstance(r, dict)]

    async def claim(self, found, rows):
        asked = []
        for _, cate in LISTS:
            ids = ready([r for r in rows if r["_cate"] == cate])
            if ids and await self.ask("claim", CLAIM, {"task_cate": cate, "id_arr": ids}, claim=True) is not None:
                asked += ids
        return asked
