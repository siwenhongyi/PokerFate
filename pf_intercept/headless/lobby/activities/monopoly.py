"""大富翁 (monopoly: 蓝湾漫游 was period 30001). Requests from client 1.7.5, MonopolyModel.lua.

Every period of this kind of activity, not one: like MonopolyModel, the period that runs is
the one the server names (``GetMonopolyActData.act_id``, 0 for none), and its window, its dice
item, its board and its milestones come from the client's tables for that id
(tpl_monopoly_activity, tpl_monopoly_chessboard / _grid, tpl_dice_consumption_rewards). A new
period needs a table sync, not new code; outside a period nothing is sent but the one read
the client also makes at login.

A pass collects the finished tasks (they pay dice), rolls the dice in the bag, takes the
milestones the rolls reached and collects again. Its task rows go on the needs board: the side
games, football and the reports are done for it by those who do them for everyone.

A roll or a milestone pays what the table says for the square or the step, and is journalled
as an intent before it is sent; an answer that never arrived is resolved from the server's
state on a later pass, after a restart too.
"""
from __future__ import annotations

import asyncio
import uuid

from pf_intercept.headless.lobby.core.base import GOLD, Activity, RewardAPIError, _int, game_day
from pf_reverse.tables import TABLES

DICE_PER_PASS = 16      # rolls in a pass; the rest follow, so the other checks still get their turn
MONOPOLY_PUSHES = (10038, 10084)


def reward_chips(reward):
    """Chips in a table reward {item, num, item, num ...}."""
    reward = reward if isinstance(reward, list) else []
    return sum(_int(num) for item, num in zip(reward[::2], reward[1::2]) if _int(item) == GOLD)


def board(act_id):
    """(squares, {square: chips}) of the period's board: the 1-based squares of tpl_monopoly_grid
    for its tpl_monopoly_chessboard row."""
    chessboard = next((r for r in TABLES.rows("monopoly_chessboard") if _int(r["activity_id"]) == act_id), None)
    if chessboard is None:
        return 0, {}
    squares = {_int(r["index"]): reward_chips(r["rewards"]) for r in TABLES.rows("monopoly_grid")
               if _int(r["chessboard_id"]) == _int(chessboard["chessboard_id"])}
    return _int(chessboard["gird_quantity"]), {index: chips for index, chips in squares.items() if chips}


def milestones(act_id):
    """(dice used to reach each step, {step: chips}) from tpl_dice_consumption_rewards, steps from 1."""
    steps = sorted((r for r in TABLES.rows("dice_consumption_rewards") if _int(r["activity"]) == act_id),
                   key=lambda r: _int(r["id"]))
    return (tuple(_int(r["quantity"]) for r in steps),
            {n: reward_chips(r["rewards"]) for n, r in enumerate(steps, 1) if reward_chips(r["rewards"])})


class Monopoly(Activity):
    name = "monopoly"
    title = "大富翁"
    switch = ("monopoly", "不玩大富翁类活动（蓝湾漫游等）的骰子和任务，其余奖励照常")
    pushes = MONOPOLY_PUSHES
    tables = ("monopoly_activity",)
    does = {(312, None): "掷完背包里的骰子"}

    def __init__(self, service, session):
        super().__init__(service, session)
        self.pending_award = None

    def replay(self, row):
        """An intent without an outcome is resolved on the next pass."""
        if row.get("event") == "monopoly_intent":
            self.pending_award = row
        elif self.pending_award and row.get("intent") == self.pending_award.get("intent"):
            self.pending_award = None

    async def tasks(self):
        return (await self.service._request("/task/monopolyTaskList", {})).get("list") or []

    async def collect(self, rows, dice):
        attempted = set()
        while rows:
            ids = {_int(r.get("id")) for r in rows if _int(r.get("status")) == 2} - attempted
            if not ids:
                break
            attempted.update(ids)
            result = await self.service._request("/task/recMonopolyTaskRw", {"id_arr": sorted(ids)})
            items = result.get("item_list") or []
            count = sum(_int(i.get("num")) for i in items if _int(i.get("item_id")) == dice)
            self.service._record("monopoly_task_claim", ids=sorted(ids), dice=count)
            # These tasks pay dice. Should one ever pay chips, they count as a reward.
            chips = _int(result.get("reward_chips")) + sum(
                _int(i.get("num")) for i in items if _int(i.get("item_id")) == GOLD)
            if chips > 0:
                await self.service.activity_payout("monopoly_task", chips, ids=sorted(ids))
            rows = await self.tasks()
        return rows

    async def check(self):
        svc, session = self.service, self.session
        self.load()
        state = await session.activity_request("GetMonopolyActData", {})
        found = self.period(state.get("act_id"))
        if self.pending_award:
            await self.resolve_award(state)
        if found is None:
            return
        dice = _int(found.row.get("activity_item"))
        rows = await self.collect(await self.tasks(), dice)
        held = await self.held(dice)
        for _ in range(min(held, DICE_PER_PASS)):
            state = await self.roll(state)
            await asyncio.sleep(1)
        await self.take_milestones(state)
        if held:
            rows = await self.collect(await self.tasks(), dice)
            if held > DICE_PER_PASS or any(_int(r.get("task_type")) == 312 and _int(r.get("status")) == 3 for r in rows):
                svc.wake(self.name, 5)
        svc.needs.want(self.name, rows)

    def start_award(self, action, state):
        intent = dict(intent=uuid.uuid4().hex, activity=_int(state.get("act_id")), action=action,
                      used=_int(state.get("all_cost_num")), progress=_int(state.get("progress")),
                      day=game_day(self.service.now()))
        self.service._record("monopoly_intent", **intent, required=True)
        self.pending_award = intent

    async def resolve_award(self, state):
        intent = self.pending_award
        act_id = _int(intent.get("activity"))
        if _int(state.get("act_id")) != act_id:
            raise RewardAPIError("GetMonopolyActData", "activity changed")
        consumed, progress = _int(state.get("all_cost_num")), _int(state.get("progress"))
        squares, chips_at = board(act_id)
        needs, step_chips = milestones(act_id)
        if intent["action"] == "roll":
            pos = _int(state.get("index"))
            if consumed == intent["used"]:
                self.service._record("monopoly_not_applied", intent=intent["intent"])
            elif consumed == intent["used"] + 1 and 1 <= pos <= squares:
                await self.service.activity_payout("monopoly_roll", chips_at.get(pos, 0),
                                                   position=pos, used=consumed, intent=intent["intent"])
            else:
                await self.service.activity_uncertain("monopoly_roll", intent=intent["intent"])
        elif progress == intent["progress"]:
            self.service._record("monopoly_not_applied", intent=intent["intent"])
        elif intent["progress"] < progress <= sum(consumed >= n for n in needs):
            chips = sum(step_chips.get(i, 0) for i in range(intent["progress"] + 1, progress + 1))
            await self.service.activity_payout("monopoly_milestone", chips, progress=progress,
                                               used=consumed, intent=intent["intent"])
        else:
            await self.service.activity_uncertain("monopoly_milestone", intent=intent["intent"])
        self.pending_award = None

    async def award_request(self, action, state, name, fields):
        self.start_award(action, state)
        try:
            after = await self.session.activity_request(name, fields)
        except RewardAPIError as exc:
            if exc.code is not None:
                self.service._record("monopoly_rejected", intent=self.pending_award["intent"], code=exc.code)
                self.pending_award = None
            # If delivery is ambiguous, resolve from authoritative state on
            # a later pass, including after reconnecting or restarting.
            raise
        merged = {**state, **after}
        if (action == "roll" and ("all_cost_num" not in after or "index" not in after)
                or action == "milestone" and "progress" not in after):
            raise RewardAPIError(name, "incomplete response")
        await self.resolve_award(merged)
        return merged

    async def roll(self, state):
        return await self.award_request("roll", state, "ThrowDice", {"multiple": 1})

    async def take_milestones(self, state):
        needs, _ = milestones(_int(state.get("act_id")))
        ready = sum(_int(state.get("all_cost_num")) >= n for n in needs)
        while _int(state.get("progress")) < ready:
            old = _int(state.get("progress"))
            state = await self.award_request("milestone", state, "GetProgressReward", {})
            if _int(state.get("progress")) <= old:
                raise RewardAPIError("GetProgressReward", "progress not advanced")
