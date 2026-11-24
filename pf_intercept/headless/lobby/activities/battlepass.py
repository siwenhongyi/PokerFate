"""通行证 (the battle pass, 灵猫风尚志 in season 1001). Requests from client 1.7.5, BattlePassModel.lua;
the season, its levels and its paid editions from the client's tables, so the next season needs
a table sync, not new code.

Collect the finished pass tasks, which pay inspiration (the pass's experience,
an item in the bag), then the rewards of the levels the inspiration has
reached and the repeating reward past the last level. Nothing is bought:
neither a paid edition nor levels. The paid rewards are collected only for an
account that already owns a paid edition.

Written from how the client reads the server's answers, which were never seen
on the wire. So an action the server refuses is not repeated for
``rewards.BLOCK_SEC``, a claim is followed by a fresh read that has to show it
as collected, and what each answer said is journalled when it changes.
"""
from __future__ import annotations

from pf_intercept.headless.lobby.core.base import Activity, RewardAPIError, _int, claimed_chips, rows_of
from pf_reverse.tables import TABLES

CLAIM = "/task/battlePassClaimReward"
EXP = 11000061                  # GPropId.BattlePassExp
COMPLETED = 2                   # TaskStatus.Completed: finished, reward not collected
UNLOCK_TTL_SEC = 3600.0         # how long "no paid edition" is believed

BATTLE_PASS_PUSHES = (10039, 10085)     # PASSCARD_TASK_REFRESH, BATTLE_PASS_START


def levels(pass_id):
    """tpl_battle_pass_level of a pass, in the client's order: (id, level, exp). The exp of a level
    is the total that reaches it. The last row, level -1, is the repeating reward, and its exp
    what each further one costs."""
    return tuple((_int(r["id"]), _int(r["level"]), _int(r["exp"]))
                 for r in TABLES.rows("battle_pass_level") if _int(r["battle_pass_id"]) == pass_id)


def editions(pass_id):
    """tpl_shop_battle_pass: (shop_type, the goods that are a paid edition: level_type 1, 2)."""
    rows = [r for r in TABLES.rows("shop_battle_pass")
            if _int(r["battle_pass_id"]) == pass_id and _int(r["level_type"]) in (1, 2)]
    return (_int(rows[0]["shop_type"]) if rows else 0), tuple(_int(r["id"]) for r in rows)


def ready_tasks(detail):
    """Ids, as text, of the weekly and season tasks that are finished and not collected."""
    return {str(row.get("id")) for name in ("weekly_list", "list") for row in rows_of(detail.get(name))
            if isinstance(row, dict) and _int(row.get("status")) == COMPLETED}


def levels_due(detail, exp):
    """Level ids to ask for with this much inspiration: those any account may ask for, those
    only the owner of a paid edition may, then the level reached and the repeats earned."""
    *steps, (loop, _, loop_cost) = levels(_int(detail.get("battle_pass_id")))
    free = {_int(ident, -1) for ident in rows_of(detail.get("level_free_reward_ids"))}
    paid = {_int(ident, -1) for ident in rows_of(detail.get("level_paid_reward_ids"))}
    reached = [ident for ident, _, need in steps if need <= exp]
    # A level is asked for once for both rewards. One whose free reward is taken is asked for
    # again only to collect the paid one.
    anyone = [ident for ident in reached if ident not in free]
    owner = [ident for ident in reached if ident in free and ident not in paid]
    # BattlePassModel:getPassCycleCount: repeats earned past the last level.
    cycles = max(0, exp - steps[-1][2]) // loop_cost
    if cycles > _int(detail.get("loop_times_free")):
        anyone.append(loop)
    elif cycles > _int(detail.get("loop_times_paid")):
        owner.append(loop)
    return anyone, owner, len(reached), cycles


class BattlePass(Activity):
    name = "battlepass"
    title = "通行证"
    switch = ("auto-battlepass", "只关闭通行证（灵猫风尚志等）的自动领奖，其余奖励照常")
    pushes = BATTLE_PASS_PUSHES
    tables = ("battle_pass_info",)
    leaves = ("付费版和购买等级不碰",)

    def __init__(self, service, session):
        super().__init__(service, session)
        self.edition = (0, False, 0.0)      # pass, whether a paid edition is owned, when read

    async def detail(self):
        """The pass as the server has it, or None when there is none this worker knows."""
        data = await self.ask("detail", "/task/battlePassDetail", {})
        if data is None:
            return None
        current = _int(data.get("battle_pass_id"))
        tasks = [row for name in ("weekly_list", "list") for row in rows_of(data.get(name)) if isinstance(row, dict)]
        seen = {}
        for row in tasks:
            seen[str(_int(row.get("status")))] = seen.get(str(_int(row.get("status"))), 0) + 1
        # Which task stands where. Progress moves with every hand, so this is journalled when a
        # status changes (and once per start), with the progress of that moment.
        marks = sorted((_int(row.get("task_id")), _int(row.get("status"))) for row in tasks)
        if self.told.get("battlepass_tasks") != marks:
            self.told["battlepass_tasks"] = marks
            self.service._record("battlepass_tasks", rows=sorted(
                ([_int(row.get("task_id")), _int(row.get("status")), _int(row.get("current_value")), row.get("value")]
                 for row in tasks), key=lambda entry: entry[:3]))
        self.tell("battlepass_state", pass_id=current, known=TABLES.row("battle_pass_info", current) is not None, tasks=seen,
                  free=len(rows_of(data.get("level_free_reward_ids"))),
                  paid=len(rows_of(data.get("level_paid_reward_ids"))),
                  loops=[_int(data.get("loop_times_free")), _int(data.get("loop_times_paid"))],
                  fields=sorted(map(str, data)), row_fields=sorted(map(str, tasks[0])) if tasks else [])
        # BattlePassModel ignores a pass its tables do not have, and one past its end.
        if self.period(current) is None or not levels(current):
            return None
        self.service.needs.want("battlepass", tasks)    # its tasks that count rounds or hands
        return data

    def still_due(self, action, ids):
        """Answered as collected and due again in the next read: this worker misreads the pass."""
        self.block(action, RewardAPIError(CLAIM, "still due: " + ",".join(sorted(map(str, ids)))))

    async def check(self):
        self.load()
        if self.blocked("detail"):
            return
        detail = await self.detail()
        if detail is None:
            return
        # Tasks first: they pay the inspiration the levels are reached with, and they do not
        # depend on the bag, which is read over the game socket.
        ready = ready_tasks(detail)
        if ready and not self.blocked("tasks"):
            # The task page's "claim all" button.
            answer = await self.ask("tasks", CLAIM, {"type": 0})
            if answer is not None:
                await self.service.activity_payout("battlepass_tasks", await self.chips(answer), tasks=len(ready))
                detail = await self.detail()
                if detail is None:
                    return
                if ready & ready_tasks(detail):
                    self.still_due("tasks", ready & ready_tasks(detail))
        await self.claim_levels(detail)

    async def chips(self, answer):
        """Chips in the answer to a task claim. The tasks of the client's tables pay inspiration
        only, so an answer without reward fields is no chips, not an unknown amount."""
        if not any(key in answer for key in ("reward_chips", "item_list")):
            return 0
        try:
            return claimed_chips(answer, "battlepass_tasks")
        except (ValueError, TypeError, KeyError, OverflowError):
            await self.service.activity_uncertain("battlepass_tasks")
            raise RewardAPIError(CLAIM) from None

    async def claim_levels(self, detail):
        current = _int(detail.get("battle_pass_id"))
        exp = await self.held(EXP)
        anyone, owner, level, cycles = levels_due(detail, exp)
        owned = bool(owner) and await self.owns_edition(current)
        if not owned:
            owner = []
        due = sorted(anyone + owner)
        self.tell("battlepass_levels", exp=exp, level=level, cycles=cycles, due=due, owned=owned)
        if not due or self.blocked("levels"):
            return
        # The reward page's "claim all" button.
        if await self.ask("levels", CLAIM, {"type": 3, "id_arr": due}, claim=True) is None:
            return
        after = await self.detail()
        if after is None:
            return
        again, later, _, _ = levels_due(after, exp)
        # Asked for both rewards and only the free one came: asked again on the next pass.
        if set(anyone) & set(again) or set(owner) & set(later):
            self.still_due("levels", set(anyone) & set(again) | set(owner) & set(later))

    async def owns_edition(self, current):
        """BattlePassModel:isUnlockPass: a paid edition shows in the shop's purchase counts."""
        known, owned, at = self.edition
        now = self.service.now()
        if known == current and (owned or now - at < UNLOCK_TTL_SEC):
            return owned
        if self.blocked("shop"):
            return False
        data = await self.ask("shop", "/shop/limit", {"mask": "shopLimit"})
        if data is None:
            return False
        shop, goods = editions(current)
        owned = any(_int(row.get("shop_type")) == shop and _int(row.get("id")) in goods
                    and _int(row.get("count")) >= 1
                    for row in rows_of(data.get("list")) if isinstance(row, dict))
        self.edition = (current, owned, now)
        return owned
