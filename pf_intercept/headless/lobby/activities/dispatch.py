"""协会经营 (派遣 / afk). Requests from client 1.7.0, DispatchModel.lua. The season (Dispatch_Start /
Dispatch_End), the assignments, the players and their skins and the season pass are read from
the client's tables, so a new season or a new player needs a table sync, not new code.

Collect finished assignments, send idle players out again with the ordinary
ticket, and collect the season pass and goal rewards that this pays for.
Nothing is bought, sped up or upgraded, and no premium ticket is used.

Written from how the client reads the server's answers; of those only the
field names of the assignment list have been seen live (2026-11-21). So an
action the server refuses is not repeated for ``BLOCK_SEC``, an answer that
never arrived is followed by a fresh read of the list, and what each answer
said is journalled when it changes.
"""
from __future__ import annotations

import asyncio

from pf_intercept.headless.lobby.core.base import GOLD, Activity, RewardAPIError, _amount, _int, refused
from pf_reverse.tables import TABLES

ORDINARY = 10440001                     # the ticket of an ordinary dispatch
NOT_SENT, RUNNING, FINISHED = 0, 1, 2   # DispatchModel.EventStatus; 3 is collected
PAUSE_SEC = 1.0
ROSTER_TTL_SEC = 3600.0
MAX_SENDS = 18                          # per 24 h; the server allows 9 a day
MAX_REFRESHES = 3                       # per 24 h: Dispatch_Free_Refresh
EVENT_SLOTS = 5                         # Dispatch_Event_Num
ROLE_SENDS, SKIN_SENDS = 3, 2           # Dispatch_Ordinary_Character_Num / _Skin_Num

DISPATCH_TASK_REFRESH = 10037


def season():
    """tpl_constdata Dispatch_Start / Dispatch_End: the season's window, (0, 0) when the client has none."""
    return _int(TABLES.const("Dispatch_Start")), _int(TABLES.const("Dispatch_End"))


def events():
    """tpl_event_info: assignment -> (camp, level). The level is also the star a player needs;
    levels 4 and 5 can pay an egg reward, possibly chips, to a player of the camp."""
    return {_int(r["id"]): (_int(r["campInt"]), _int(r["event_level"])) for r in TABLES.rows("event_info")}


def role_camp():
    """tpl_character: role -> camp."""
    return {_int(r["id"]): _int(r["campInt"]) for r in TABLES.rows("character")}


def outfits():
    """tpl_character_skin: skin -> (role, avatar)."""
    return {_int(r["id"]): (_int(r["role"]), _int(r["avatar"])) for r in TABLES.rows("character_skin")}


def pass_costs():
    """tpl_passcard_info.level_up_cost: summaries earned in total to reach pass level 0, 1, 2 ..."""
    return tuple(_int(r["level_up_cost"]) for r in TABLES.rows("passcard_info"))


def event_rows(state):
    return [row for row in state.get("event_list") or [] if isinstance(row, dict)]


def usable(ident):
    """The id of an assignment row is the server's own and goes back to it as it came:
    the client never looks inside it, and it need not be a number."""
    if isinstance(ident, str):
        return bool(ident)
    return isinstance(ident, int) and not isinstance(ident, bool) and ident > 0


def goal_rows(data):
    rows = data.get("list") or []
    if isinstance(rows, dict):
        rows = rows.values()
    return [row for row in rows if isinstance(row, dict)]


def egg_chips(data):
    """Chips in the egg reward of a collected assignment: a flat id, count, id, count ... list."""
    egg = data.get("reward_bonus") or []
    try:
        if not isinstance(egg, list) or len(egg) % 2:
            raise ValueError("invalid egg reward")
        return sum(_amount(num) for item, num in zip(egg[::2], egg[1::2]) if _int(item) == GOLD)
    except (ValueError, TypeError, OverflowError):
        # A success code with an unreadable amount is not a zero award.
        raise RewardAPIError("/afk/recReward") from None


def may_pay_chips(row):
    camp, level = events().get(_int(row.get("event_id")), (None, 5))
    return level >= 4 and (camp is None or role_camp().get(_int(row.get("role_id")), camp) == camp)


def pass_level(summaries):
    return sum(cost <= summaries for cost in pass_costs()) - 1


class Dispatch(Activity):
    name = "dispatch"
    title = "协会经营（派遣）"
    switch = ("auto-dispatch", "只关闭协会经营（派遣）的自动派遣和领奖，其余奖励照常")
    pushes = (DISPATCH_TASK_REFRESH,)
    tables = ("constdata:Dispatch",)
    does = {(401, None): "派遣牌手"}
    leaves = ("加速、升级、高级派遣券不用",)

    def __init__(self, service, session):
        super().__init__(service, session)
        self.sends = []         # server times of the dispatch requests of the last 24 h
        self.refreshes = []     # the same for list refreshes
        self.pass_due = True
        self.tasks_due = True
        self.roster = None      # role -> (skin, avatar, number of owned skins)
        self.roster_at = 0.0

    def pushed(self, notice_type):
        """DISPATCH_TASK_REFRESH: the goals moved."""
        self.tasks_due = True
        self.service.wake(self.name, 1)

    def replay(self, row):
        """The 24 h counts survive a restart through the reward journal."""
        if row["event"] == "dispatch_attempt":
            self.sends.append(float(row["server_ts"]))
        elif row["event"] == "dispatch_refresh":
            self.refreshes.append(float(row["server_ts"]))

    def recent(self, stamps):
        floor = self.service.now() - 86400
        stamps[:] = [stamp for stamp in stamps if stamp > floor]
        return len(stamps)

    async def events(self, **extra):
        state = await self.ask("list", "/afk/eventList", {**extra, "immediately": True})
        if state is None:
            return None
        # The names of the fields are kept as well: they are what a first live run has to confirm.
        rows = event_rows(state)
        seen = {}
        for row in rows:
            seen[str(_int(row.get("status")))] = seen.get(str(_int(row.get("status"))), 0) + 1
        self.tell("dispatch_state", events=seen,
                  unknown=sum(_int(row.get("event_id")) not in events() for row in rows),
                  camps={str(_int(row.get("camp_id"))): _int(row.get("camp_level"))
                         for row in state.get("camp_list") or [] if isinstance(row, dict)},
                  sends_left=_int(state.get("remain_free_dispatch_times")),
                  refreshes_left=_int(state.get("remain_free_refresh_times")),
                  fields=sorted(map(str, state)), row_fields=sorted(map(str, rows[0])) if rows else [],
                  id_types=sorted({type(row.get("id")).__name__ for row in rows}))
        return state

    async def check(self):
        svc = self.service
        start, end = season()
        if not start <= svc.now() <= end:
            self.tell("dispatch_season", start=start, end=end, open=False)
            return
        self.tell("dispatch_season", start=start, end=end, open=True)
        self.load()
        if self.blocked("list"):
            return
        # What the client sends when the page is opened; rec_item also collects
        # the tickets given on the first visit.
        state = await self.events(rec_item=True)
        if state is not None:
            state = await self.collect(state)
        if state is None:
            return
        # The pass pays tickets, so it is collected before players are sent out.
        if self.pass_due:
            await self.claim_pass()
        if self.tasks_due:
            await self.claim_goals()
        state = await self.send_out(state)
        if state is None:
            return
        now = svc.now()
        ends = [_int(row.get("end_ts")) for row in event_rows(state) if _int(row.get("status")) == RUNNING]
        ends = [end for end in ends if end > now]
        if ends:
            svc.wake(self.name, min(ends) - now + 5)

    async def collect(self, state):
        svc = self.service
        collected = 0
        for row in event_rows(state):
            ident, status, end = row.get("id"), _int(row.get("status")), _int(row.get("end_ts"))
            if status not in (RUNNING, FINISHED) or status == RUNNING and not 0 < end <= svc.now():
                continue
            if not usable(ident):
                # Never silently: a reward that waits but cannot be asked for.
                self.tell("dispatch_unreadable", field="id", type=type(ident).__name__)
                continue
            if self.blocked(f"collect:{ident}"):
                continue
            if collected:
                await asyncio.sleep(PAUSE_SEC)
            try:
                data = await svc._request("/afk/recReward", {"id": ident})
                chips = egg_chips(data)
            except RewardAPIError as exc:
                if refused(exc):
                    self.block(f"collect:{ident}", exc)
                    continue
                if may_pay_chips(row):
                    await svc.activity_uncertain("dispatch", id=ident)
                raise
            collected += 1
            await svc.activity_payout(
                "dispatch", chips, id=ident, event_id=_int(row.get("event_id")),
                role_id=_int(row.get("role_id")),
                rewards={key: data[key] for key in ("exp", "bond", "star_exp", "camp_quality", "reward_bonus")
                         if data.get(key)})
        if not collected:
            return state
        # Summaries were earned: the pass level and the goals may have moved.
        self.pass_due = self.tasks_due = True
        return await self.events()

    async def send_out(self, state):
        svc = self.service
        left = min(_int(state.get("remain_free_dispatch_times")), MAX_SENDS - self.recent(self.sends))
        if left <= 0 or self.blocked("send"):
            return state
        # An assignment is one row per player sent, or a single unsent row.
        status = {}
        for row in event_rows(state):
            status.setdefault(_int(row.get("event_id")), set()).add(_int(row.get("status")))
        known, camps = events(), role_camp()
        waiting = sorted((event for event, seen in status.items() if seen == {NOT_SENT} and event in known),
                         key=lambda event: (-known[event][1], event))
        stale = None if waiting else self.stale_camp(state, status)
        if not waiting and stale is None:
            return state
        players = await self.players(state)
        tickets = await self.held(ORDINARY) if players else 0
        if not players or tickets <= 0:
            self.tell("dispatch_idle", waiting=len(waiting), players=len(players), tickets=tickets)
            return state
        self.told.pop("dispatch_idle", None)
        left = min(left, tickets)
        if not waiting:
            return await self.refresh(stale, state)
        sent = 0
        for event in waiting:
            if sent >= left:
                break
            camp, level = known[event]
            fit = [role for role, (star, _, _) in players.items() if star >= level]
            if not fit:
                continue
            # DispatchSelection's order: own camp, then stars, then the lower id.
            role = min(fit, key=lambda role: (camps.get(role) != camp, -players[role][0], role))
            _, skin, avatar = players.pop(role)
            if sent:
                await asyncio.sleep(PAUSE_SEC)
            svc._record("dispatch_attempt", event_id=event, role_id=role, required=True)
            self.sends.append(svc.now())
            if await self.ask("send", "/afk/dispatch", {
                    "event_id": event, "role_id_arr": [role], "item_id": ORDINARY,
                    "avatar_arr": [avatar], "skin_id_arr": [skin]}) is None:
                break
            sent += 1
            svc._record("dispatched", event_id=event, role_id=role, skin_id=skin)
        return await self.events() if sent else state

    def stale_camp(self, state, status):
        """An unlocked camp with nothing left to send, which may be drawn again for free."""
        known = events()
        if (self.blocked("refresh") or _int(state.get("remain_free_refresh_times")) <= 0
                or self.recent(self.refreshes) >= MAX_REFRESHES
                or any(event not in known for event in status)):   # a list this table cannot read
            return None
        camps = sorted((_int(row.get("camp_id")), _int(row.get("camp_level")))
                       for row in state.get("camp_list") or [] if isinstance(row, dict))
        for camp, level in camps:
            # DispatchModel:getCampIsCanRefresh: assignments under way keep their slot.
            kinds = sum(1 for where, grade in known.values() if where == camp and grade <= level)
            busy = sum(1 for event, seen in status.items()
                       if known.get(event, (None,))[0] == camp and seen & {RUNNING, FINISHED})
            if level > 0 and busy < min(EVENT_SLOTS, kinds):
                return camp
        return None

    async def refresh(self, camp, state):
        svc = self.service
        svc._record("dispatch_refresh", camp_id=camp, required=True)
        self.refreshes.append(svc.now())
        if await self.ask("refresh", "/afk/refresh", {"camp_id": camp, "item_id": 0}) is None:
            return state
        svc.wake(self.name, 5)    # the new list is sent out on the next pass
        return await self.events()

    async def players(self, state):
        """Idle players with ordinary sends left today: role -> (star, skin, avatar)."""
        svc = self.service
        if self.roster is None or svc.now() - self.roster_at > ROSTER_TTL_SEC:
            reply = await self.session.activity_request("RoleList", {})
            dressed, camps = outfits(), role_camp()
            roster = {}
            for row in reply.get("role_list") or []:
                role = _int(row.get("role_id"))
                skins = row.get("skin_info") or {}
                skin = _int(skins.get("skin_id"))
                if dressed.get(skin, (None,))[0] != role:
                    # CharacterData:getSkinData falls back to the player's first skin.
                    skin = min((known for known, (owner, _) in dressed.items() if owner == role), default=0)
                if role in camps and skin:
                    roster[role] = (skin, dressed[skin][1], max(1, len(skins.get("owned_skin_ids") or [])))
            self.roster, self.roster_at = roster, svc.now()
            # Which players the account has, as the server lists them (also those this table lacks).
            self.tell("dispatch_roster", roles=sorted(_int(row.get("role_id")) for row in reply.get("role_list") or []),
                      usable=sorted(roster))
        now = svc.now()
        known = {_int(row.get("role_id")): row for row in state.get("role_list") or [] if isinstance(row, dict)}
        away = {_int(row.get("role_id")) for row in event_rows(state)
                if _int(row.get("status")) == RUNNING or _int(row.get("end_ts")) > now}
        idle = {}
        for role, (skin, avatar, owned) in self.roster.items():
            if role in away:
                continue
            row = known.get(role)
            # A player the server has no dispatch record of starts with the full daily count.
            sends = ROLE_SENDS + (owned - 1) * SKIN_SENDS if row is None else _int(row.get("remain_dispatch_times"))
            if sends > 0:
                idle[role] = (max(1, _int((row or {}).get("role_star"))), skin, avatar)
        return idle

    async def claim_pass(self):
        if self.blocked("pass"):
            return
        data = await self.ask("pass", "/afk/passCardData", {"t": 1, "immediately": True})
        if data is None:
            return
        taken = data.get("data") or {}
        ordinary = {_int(level, -1) for level in taken.get("ordinary") or []}
        advanced = {_int(level, -1) for level in taken.get("advanced") or []}
        paid = bool(data.get("has_pass_card"))
        level = pass_level(_int(data.get("item_num")))
        self.tell("dispatch_pass", summaries=_int(data.get("item_num")), level=level, paid=paid,
                  ordinary=len(ordinary), advanced=len(advanced),
                  fields=sorted(map(str, data)), taken_fields=sorted(map(str, taken)))
        if any(step not in ordinary or paid and step not in advanced for step in range(level + 1)):
            # The page's "claim all" button.
            await self.ask("pass", "/afk/recPassCardReward", {"level": 1, "advanced": True, "all": True}, claim=True)
        self.pass_due = False

    async def claim_goals(self):
        if self.blocked("goals"):
            return
        data = await self.ask("goals", "/task/dispatchTaskList", {})
        if data is None:
            return
        self.tell_goals(data)
        ready = sorted({_int(row.get("id")) for row in goal_rows(data)
                        if _int(row.get("status")) == 2 and _int(row.get("id")) > 0})
        if ready:
            if await self.ask("goals", "/task/recDispatchTaskRw", {"id_arr": ready}, claim=True) is None:
                return
            data = await self.ask("goals", "/task/dispatchTaskList", {})
            if data is None:
                return
            self.tell_goals(data)
        rows = goal_rows(data)
        if (rows and all(_int(row.get("status")) == 3 for row in rows)
                and not data.get("season_reward") and not self.blocked("season")):
            # Every goal collected: the season title.
            await self.ask("season", "/afk/recSeasonReward", {}, claim=True)
        self.tasks_due = False

    def tell_goals(self, data):
        rows = goal_rows(data)
        seen = {}
        for row in rows:
            seen[str(_int(row.get("status")))] = seen.get(str(_int(row.get("status"))), 0) + 1
        self.tell("dispatch_goals", goals=seen, season=bool(data.get("season_reward")),
                  fields=sorted(map(str, data)), row_fields=sorted(map(str, rows[0])) if rows else [],
                  id_types=sorted({type(row.get("id")).__name__ for row in rows}),
                  # tpl_rewards_info id, status, progress: which goal stands where.
                  rows=sorted([_int(row.get("task_id")), _int(row.get("status")), _int(row.get("current_value"))]
                              for row in rows))
