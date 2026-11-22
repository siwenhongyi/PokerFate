"""协会经营 (派遣 / afk). Requests and tables from client 1.7.0, DispatchModel.lua.

Collect finished assignments, send idle players out again with the ordinary
ticket, and collect the season pass and goal rewards that this pays for.
Nothing is bought, sped up or upgraded, and no premium ticket is used.

The server's answers were never seen on the wire, only how the client reads
them. So an action the server refuses is not repeated for ``BLOCK_SEC``, and an
answer that never arrived is followed by a fresh read of the list.
"""
from __future__ import annotations

import asyncio
import json
from itertools import accumulate

from pf_intercept.headless.rewards import GOLD, RewardAPIError, _amount, _int

START, END = 1787796000, 1795618800     # Dispatch_Start / Dispatch_End
ORDINARY = 10440001                     # the ticket of an ordinary dispatch
NOT_SENT, RUNNING, FINISHED = 0, 1, 2   # DispatchModel.EventStatus; 3 is collected
BLOCK_SEC = 6 * 3600.0
PAUSE_SEC = 1.0
ROSTER_TTL_SEC = 3600.0
MAX_SENDS = 18                          # per 24 h; the server allows 9 a day
MAX_REFRESHES = 3                       # per 24 h: Dispatch_Free_Refresh
EVENT_SLOTS = 5                         # Dispatch_Event_Num
ROLE_SENDS, SKIN_SENDS = 3, 2           # Dispatch_Ordinary_Character_Num / _Skin_Num

# tpl_event_info: id -> (camp, level). The level is also the star a player
# needs; levels 4 and 5 can pay an egg reward, possibly chips, to a player of the camp.
EVENTS = {100000 + camp * 1000 + n: (camp, level)
          for camp in range(7) for n, level in enumerate((1, 1, 2, 3, 4, 5) * 2, 1)}
# tpl_character: role -> camp.
ROLE_CAMP = {1001: 0, 1002: 0, 1003: 1, 1004: 0, 1005: 5, 1006: 3, 1007: 0, 1008: 5, 1009: 2,
             1010: 3, 1012: 5, 1013: 5, 1014: 5, 1015: 0, 1016: 3, 1018: 5, 1019: 5, 1020: 2,
             1021: 0, 1022: 0, 1023: 4, 3001: 6}
# tpl_character_skin: skin -> (role, avatar).
SKINS = {
    100101: (1001, 20110101), 100104: (1001, 20110102), 100105: (1001, 20110103), 100106: (1001, 20110104),
    100201: (1002, 20110201), 100204: (1002, 20110202), 100205: (1002, 20110203),
    100301: (1003, 20110301), 100304: (1003, 20110302), 100305: (1003, 20110303), 100306: (1003, 20110306),
    100401: (1004, 20110401), 100404: (1004, 20110402), 100405: (1004, 20110403), 100406: (1004, 20110404),
    100501: (1005, 20110501), 100504: (1005, 20110502), 100505: (1005, 20110503), 100506: (1005, 20110506), 100507: (1005, 20110507),
    100601: (1006, 20110601), 100604: (1006, 20110602), 100605: (1006, 20110605), 100606: (1006, 20110606),
    100701: (1007, 20110701), 100704: (1007, 20110702), 100705: (1007, 20110705), 100706: (1007, 20110706),
    100801: (1008, 20110801), 100804: (1008, 20110802), 100805: (1008, 20110803), 100806: (1008, 20110806),
    100901: (1009, 20110901), 100904: (1009, 20110904), 100905: (1009, 20110905), 100906: (1009, 20110906),
    101001: (1010, 20111001), 101004: (1010, 20111004), 101005: (1010, 20111005), 101006: (1010, 20111006),
    101201: (1012, 20111201), 101204: (1012, 20111204), 101205: (1012, 20111205),
    101301: (1013, 20111301), 101304: (1013, 20111304), 101305: (1013, 20111305), 101306: (1013, 20111306),
    101401: (1014, 20111401), 101404: (1014, 20111404), 101405: (1014, 20111405), 101406: (1014, 20111406),
    101501: (1015, 20111501), 101504: (1015, 20111504), 101505: (1015, 20111505),
    101601: (1016, 20111601), 101604: (1016, 20111604), 101605: (1016, 20111605),
    101801: (1018, 20111801), 101804: (1018, 20111804), 101805: (1018, 20111805),
    101901: (1019, 20111901), 101904: (1019, 20111904), 101905: (1019, 20111905),
    102001: (1020, 20112001), 102004: (1020, 20112004), 102005: (1020, 20112005),
    102101: (1021, 20112101), 102104: (1021, 20112104), 102105: (1021, 20112105),
    102201: (1022, 20112201), 102204: (1022, 20112204), 102205: (1022, 20112205),
    102301: (1023, 20112301), 102304: (1023, 20112304), 102305: (1023, 20112305),
    300101: (3001, 20113001), 300104: (3001, 20113004), 300105: (3001, 20113005), 300106: (3001, 20113006),
}
# tpl_passcard_info.level_up_cost: summaries earned in total to reach pass level 0, 1, 2 ...
PASS_COSTS = tuple(accumulate(
    [0] + [15000] * 5 + [20000] * 5 + [25000] * 5 + [30000] * 5 + [40000] * 5 + [50000] * 5
    + [60000] * 5 + [80000] * 5 + [100000] * 10 + [120000] * 10))


def refused(exc):
    """The server answered with an error code; -2 (login expired) is the service's to handle."""
    return isinstance(exc.code, int) and not isinstance(exc.code, bool) and exc.code != -2


def event_rows(state):
    return [row for row in state.get("event_list") or [] if isinstance(row, dict)]


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
    camp, level = EVENTS.get(_int(row.get("event_id")), (None, 5))
    return level >= 4 and (camp is None or ROLE_CAMP.get(_int(row.get("role_id")), camp) == camp)


def pass_level(summaries):
    return sum(cost <= summaries for cost in PASS_COSTS) - 1


class Dispatch:
    def __init__(self, service, session):
        self.service = service
        self.session = session
        self.blocks = {}        # action -> server time until which it is not tried again
        self.sends = []         # server times of the dispatch requests of the last 24 h
        self.refreshes = []     # the same for list refreshes
        self.pass_due = True
        self.tasks_due = True
        self.roster = None      # role -> (skin, avatar, number of owned skins)
        self.roster_at = 0.0
        self.loaded = False
        self.told = {}          # journal event -> what it last said

    def load(self):
        """Refusals and the 24 h counts survive a restart through the reward journal."""
        if self.loaded:
            return
        self.loaded = True
        path = self.service._journal_path
        if not path.exists():
            return
        floor = self.service.now() - 86400
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                row = json.loads(line)
                if row.get("uid") != self.service.uid or float(row["server_ts"]) < floor:
                    continue
                if row["event"] == "dispatch_blocked":
                    self.blocks[str(row["action"])] = float(row["until"])
                elif row["event"] == "dispatch_attempt":
                    self.sends.append(float(row["server_ts"]))
                elif row["event"] == "dispatch_refresh":
                    self.refreshes.append(float(row["server_ts"]))
            except (ValueError, TypeError, KeyError, AttributeError):
                continue

    def blocked(self, action):
        return self.service.now() < self.blocks.get(action, 0)

    def block(self, action, exc):
        until = self.service.now() + BLOCK_SEC
        self.blocks[action] = until
        self.service._record("dispatch_blocked", action=action, endpoint=exc.endpoint,
                             code=exc.code, until=until)

    def recent(self, stamps):
        floor = self.service.now() - 86400
        stamps[:] = [stamp for stamp in stamps if stamp > floor]
        return len(stamps)

    async def ask(self, action, endpoint, payload, claim=False):
        """One request. A refusal blocks the action and returns None; no answer raises."""
        try:
            if claim:
                # Answered with reward_chips / item_list, like the task rewards.
                return await self.service._claim(endpoint, payload, "dispatch_" + action)
            return await self.service._request(endpoint, payload)
        except RewardAPIError as exc:
            if not refused(exc):
                raise
            self.block(action, exc)
            return None

    def tell(self, event, **fields):
        """Journal a condition when it changes, not on every pass."""
        if self.told.get(event) != fields:
            self.told[event] = fields
            self.service._record(event, **fields)

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
                  unknown=sum(_int(row.get("event_id")) not in EVENTS for row in rows),
                  camps={str(_int(row.get("camp_id"))): _int(row.get("camp_level"))
                         for row in state.get("camp_list") or [] if isinstance(row, dict)},
                  sends_left=_int(state.get("remain_free_dispatch_times")),
                  refreshes_left=_int(state.get("remain_free_refresh_times")),
                  fields=sorted(map(str, state)), row_fields=sorted(map(str, rows[0])) if rows else [])
        return state

    async def check(self):
        svc = self.service
        if not START <= svc.now() <= END:
            return
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
            svc.wake_dispatch(min(ends) - now + 5)

    async def collect(self, state):
        svc = self.service
        collected = 0
        for row in event_rows(state):
            ident, status, end = _int(row.get("id")), _int(row.get("status")), _int(row.get("end_ts"))
            if ident <= 0 or status not in (RUNNING, FINISHED) or self.blocked(f"collect:{ident}"):
                continue
            if status == RUNNING and not 0 < end <= svc.now():
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
        waiting = sorted((event for event, seen in status.items() if seen == {NOT_SENT} and event in EVENTS),
                         key=lambda event: (-EVENTS[event][1], event))
        stale = None if waiting else self.stale_camp(state, status)
        if not waiting and stale is None:
            return state
        players = await self.players(state)
        tickets = await self.tickets() if players else 0
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
            camp, level = EVENTS[event]
            fit = [role for role, (star, _, _) in players.items() if star >= level]
            if not fit:
                continue
            # DispatchSelection's order: own camp, then stars, then the lower id.
            role = min(fit, key=lambda role: (ROLE_CAMP[role] != camp, -players[role][0], role))
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
        if (self.blocked("refresh") or _int(state.get("remain_free_refresh_times")) <= 0
                or self.recent(self.refreshes) >= MAX_REFRESHES
                or any(event not in EVENTS for event in status)):   # a list this table cannot read
            return None
        camps = sorted((_int(row.get("camp_id")), _int(row.get("camp_level")))
                       for row in state.get("camp_list") or [] if isinstance(row, dict))
        for camp, level in camps:
            # DispatchModel:getCampIsCanRefresh: assignments under way keep their slot.
            kinds = sum(1 for where, grade in EVENTS.values() if where == camp and grade <= level)
            busy = sum(1 for event, seen in status.items()
                       if EVENTS.get(event, (None,))[0] == camp and seen & {RUNNING, FINISHED})
            if level > 0 and busy < min(EVENT_SLOTS, kinds):
                return camp
        return None

    async def refresh(self, camp, state):
        svc = self.service
        svc._record("dispatch_refresh", camp_id=camp, required=True)
        self.refreshes.append(svc.now())
        if await self.ask("refresh", "/afk/refresh", {"camp_id": camp, "item_id": 0}) is None:
            return state
        svc.wake_dispatch(5)    # the new list is sent out on the next pass
        return await self.events()

    async def players(self, state):
        """Idle players with ordinary sends left today: role -> (star, skin, avatar)."""
        svc = self.service
        if self.roster is None or svc.now() - self.roster_at > ROSTER_TTL_SEC:
            reply = await self.session.activity_request("RoleList", {})
            roster = {}
            for row in reply.get("role_list") or []:
                role = _int(row.get("role_id"))
                skins = row.get("skin_info") or {}
                skin = _int(skins.get("skin_id"))
                if SKINS.get(skin, (None,))[0] != role:
                    # CharacterData:getSkinData falls back to the player's first skin.
                    skin = min((known for known, (owner, _) in SKINS.items() if owner == role), default=0)
                if role in ROLE_CAMP and skin:
                    roster[role] = (skin, SKINS[skin][1], max(1, len(skins.get("owned_skin_ids") or [])))
            self.roster, self.roster_at = roster, svc.now()
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

    async def tickets(self):
        bag = await self.session.activity_request("ItemList", {})
        now = self.service.now()
        return sum(_int(item.get("num")) for item in bag.get("item_list") or []
                   if _int(item.get("item_id")) == ORDINARY
                   and (_int(item.get("deadline")) == 0 or _int(item.get("deadline")) > now))

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
        if any(level not in ordinary or paid and level not in advanced
               for level in range(pass_level(_int(data.get("item_num"))) + 1)):
            # The page's "claim all" button.
            await self.ask("pass", "/afk/recPassCardReward", {"level": 1, "advanced": True, "all": True}, claim=True)
        self.pass_due = False

    async def claim_goals(self):
        if self.blocked("goals"):
            return
        data = await self.ask("goals", "/task/dispatchTaskList", {})
        if data is None:
            return
        ready = sorted({_int(row.get("id")) for row in goal_rows(data)
                        if _int(row.get("status")) == 2 and _int(row.get("id")) > 0})
        if ready:
            if await self.ask("goals", "/task/recDispatchTaskRw", {"id_arr": ready}, claim=True) is None:
                return
            data = await self.ask("goals", "/task/dispatchTaskList", {})
            if data is None:
                return
        rows = goal_rows(data)
        if (rows and all(_int(row.get("status")) == 3 for row in rows)
                and not data.get("season_reward") and not self.blocked("season")):
            # Every goal collected: the season title.
            await self.ask("season", "/afk/recSeasonReward", {}, claim=True)
        self.tasks_due = False
