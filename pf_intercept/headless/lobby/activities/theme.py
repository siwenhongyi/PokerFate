"""主题活动 (a period about every month: 即兴恶作剧 is 10010, 超天酱直播中 10011). ThemeModel.lua.

The token-shop template (``token_shop.py``): the server names the period (``themeActivity``),
the client's tpl_theme_activity row gives its token; the tasks (``task/activityTaskList`` with
the period's id, category 4, the task page's "claim all") are collected and go on the needs
board; the tokens buy everything of the period's shop (tpl_shop_activity rows of the period,
shop 20001: 结缘晶片, gifts, decorations, the chips last) — the client's 女巫集市 / 周边商城 page.
Tokens also come from every hand played (the table's ``mod_add``), so the shop is emptied over
the month and the rest buys chips.

Left alone: the draw pool and the story and points rewards (only some periods have them).
"""
from __future__ import annotations

from pf_intercept.headless.lobby.activities.token_shop import TokenShop, ready
from pf_intercept.headless.lobby.core.base import rows_of

DATA, TASKS, CLAIM = "/activity/themeActivity", "/task/activityTaskList", "/task/recReward"
ACTIVITY_TASKS = 4              # task_cate of an activity's tasks
THEME_SHOP = 20001              # SHOP_TYPE of the periods' shops since 10004


class Theme(TokenShop):
    name = "theme"
    title = "主题活动"
    switch = ("theme", "不做主题活动（即兴恶作剧等）的任务和兑换，其余奖励照常")
    tables = ("theme_activity",)
    does = {(313, THEME_SHOP): "在活动商店兑换"}
    leaves = ("抽卡池、剧情奖励、积分奖励不做（只有个别几期有）",)
    shop_table, shop_column, shop_type = "shop_activity", "activity", THEME_SHOP

    async def current(self):
        data = await self.ask("data", DATA, {"t": 1})
        info = (data or {}).get("data")
        return info.get("id") if isinstance(info, dict) else 0

    async def task_rows(self, found):
        if self.blocked("tasks"):
            return None
        data = await self.ask("tasks", TASKS, {"id": found.ident})
        return None if data is None else [r for r in rows_of(data.get("list")) if isinstance(r, dict)]

    async def claim(self, found, rows):
        ids = ready(rows)
        if not ids:
            return []
        # The task page's "claim all" button.
        answer = await self.ask("claim", CLAIM, {"id_arr": ids, "task_cate": ACTIVITY_TASKS,
                                                 "all": True, "mask": "reward"}, claim=True)
        return ids if answer is not None else []
