"""礼物: the tasks about gifts, done for whichever source on the needs board lacks them.

    201  给牌手送礼        a gift to a player whose affection is not full (RoleGiftREQ,
                           CharacterMainBonds): the one in use, else the first such one
    310  回收礼物          one gift recycled in the bag (RecycleItemREQ, BackpackRecycle): it gives
                           礼物碎片, 1 for a one-star gift, 4 for a two-star one ...
    313  礼物碎片商城兑换  the good the task names in shop 16 (结缘晶片 for 70 fragments, one a
                           week), bought with ``shop/buyWithProp`` like every shop of items

Gifts come from the activity shops (theme, creator) and gift packs. The cheapest gift goes
first. To buy in the fragment shop, gifts beyond the ``RESERVE`` kept for giving are recycled for
the fragments that are short; with too few gifts nothing is bought, and the journal says so.
Each kind is done at most ``MAX_PER_DAY`` times a game day (the journal counts across restarts).
Written from the client's code; the answers were never seen on the wire.
"""
from __future__ import annotations

import json

from pf_intercept.headless.lobby.core.base import Activity, RewardAPIError, _int, game_day, refused, rows_of
from pf_intercept.headless.lobby.core.needs import task_key
from pf_reverse.tables import TABLES

GIVE, RECYCLE, EXCHANGE = 201, 310, 313
GIFT_KIND = 106                 # GPropKind.Gift
FRAGMENT = 10500001             # 礼物碎片
FRAGMENT_SHOP = 16
BUY = "/shop/buyWithProp"
RESERVE = 7                     # gifts kept for a week of giving
AWAKEN_LEVEL = 5                # Config.AWAKEN_LEVEL: from this bond level on a player is 已满级
MAX_PER_DAY = 3                 # of each kind
COMEBACK_SEC = 3


def gift_quality():
    """{gift item: quality} from tpl_props, without the bound ones (the client does not recycle those)."""
    return {_int(r["id"]): _int(r.get("quality")) for r in TABLES.rows("props")
            if _int(r.get("type")) == GIFT_KIND and _int(r.get("isBinding")) != 1}


def fragments_of(item):
    """礼物碎片 one gift recycles into (its decProps)."""
    row = TABLES.row("props", item) or {}
    dec = row.get("decProps") if isinstance(row.get("decProps"), list) else []
    return _int(dec[1]) if len(dec) >= 2 and _int(dec[0]) == FRAGMENT else 0


def gifts_in(bag, now):
    """[(quality, item, uniq id, count)] of the gifts in the bag, cheapest first."""
    quality = gift_quality()
    out = []
    for row in rows_of(bag.get("item_list")):
        item, num = _int(row.get("item_id")), _int(row.get("num"))
        live = _int(row.get("deadline")) == 0 or _int(row.get("deadline")) > now
        if item in quality and num > 0 and live and row.get("item_uniq_id"):
            out.append((quality[item], item, str(row["item_uniq_id"]), num))
    return sorted(out)


def daily_gifts():
    """Gifts a day at the lowest VIP level (VipModel:getDailyGiftCounts): the account's level is
    not read, so this is the limit it surely has."""
    return min((_int(r.get("daily_gift_counts")) for r in TABLES.rows("vip_level")), default=0)


def receiver(roles, now):
    """The player a gift goes to, from RoleListRSP. CharacterMainBonds, when the player in use is
    已满级 (bond level ``AWAKEN_LEVEL``), picks the first owned player who is not, in its order:
    starred first, a higher bond level, then the table's. When every one is full: the one in use
    (the client lets a gift go to a full player, its affection is kept as over-bond). 0: none."""
    sort = {_int(r["id"]): _int(r.get("sort")) for r in TABLES.rows("character")}
    using = _int(roles.get("using_role_id"))
    owned = [r for r in rows_of(roles.get("role_list")) if isinstance(r, dict) and _int(r.get("role_id"))
             and (_int(r.get("expire_time")) == 0 or _int(r.get("expire_time")) > now)]
    level = lambda r: _int((r.get("level_info") or {}).get("level"))     # noqa: E731
    open_ = sorted((r for r in owned if level(r) < AWAKEN_LEVEL),
                   key=lambda r: (_int(r["role_id"]) != using, not r.get("is_star"), -level(r),
                                  sort.get(_int(r["role_id"]), 0)))
    if open_:
        return _int(open_[0]["role_id"])
    ids = [_int(r["role_id"]) for r in owned]
    return using if using in ids else (ids[0] if ids else 0)


def spare_gifts(gifts, reserve=RESERVE):
    """The gifts beyond the ``reserve`` cheapest ones kept for giving, cheapest first."""
    out, keep = [], reserve
    for quality, item, uniq, num in gifts:
        kept = min(num, keep)
        keep -= kept
        if num > kept:
            out.append((quality, item, uniq, num - kept))
    return out


def fragment_good(good):
    """(cost in fragments, limit) of a good of the fragment shop, else None."""
    row = TABLES.row("shop_exchange", good)
    cost = (row or {}).get("exchange_cost")
    if not row or _int(row.get("shop_type")) != FRAGMENT_SHOP or not isinstance(cost, list) or _int(cost[0]) != FRAGMENT:
        return None
    return _int(cost[1]), _int(row.get("limit_count"))


class Gifts(Activity):
    name = "gifts"
    title = "礼物"
    switch = ("gifts", "不替任务送礼、回收礼物、在礼物碎片商城兑换")
    does = {(GIVE, None): "给好感没满的牌手送一件最便宜的礼物", (RECYCLE, None): "回收一件最便宜的礼物",
            (EXCHANGE, FRAGMENT_SHOP): "回收礼物攒碎片，在礼物碎片商城兑换"}

    def __init__(self, service, session):
        super().__init__(service, session)
        self.day = None
        self.done = {}              # kind -> attempts today

    def count_today(self):
        day = game_day(self.service.now())
        if self.day == day:
            return
        self.day, self.done = day, {}
        path = self.service._journal_path
        if not path.exists():
            return
        for line in path.read_text(encoding="utf-8").splitlines():
            if '"gifts_attempt"' not in line:
                continue
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if row.get("uid") == self.service.uid and row.get("day") == day:
                self.done[row.get("kind")] = self.done.get(row.get("kind"), 0) + 1

    def wanted(self):
        """[(board key, kind, good)] some source lacks, that are left for today."""
        needs, out = self.service.needs, []
        for key, kind in ((task_key(GIVE), GIVE), (task_key(RECYCLE), RECYCLE)):
            if needs.lacking(key) and self.done.get(kind, 0) < MAX_PER_DAY and not self.blocked(str(kind)):
                out.append((key, kind, 0))
        prefix = f"task_type:{EXCHANGE}:{FRAGMENT_SHOP}:"
        for key in needs.keys():
            if isinstance(key, str) and key.startswith(prefix) and self.done.get(EXCHANGE, 0) < MAX_PER_DAY:
                good = _int(key[len(prefix):])
                if good and not self.blocked(f"buy:{good}"):
                    out.append((key, EXCHANGE, good))
        return out

    def attempt(self, kind, **fields):
        self.done[kind] = self.done.get(kind, 0) + 1
        self.service._record("gifts_attempt", day=self.day, kind=kind, required=True, **fields)

    async def check(self):
        self.load()
        self.count_today()
        todo = self.wanted()
        if not todo:
            return
        session, svc = self.session, self.service
        for key, kind, good in todo:
            gifts = gifts_in(await session.activity_request("ItemList", {}), svc.now())
            if kind == GIVE and gifts:
                done = await self.give(gifts[0])
            elif kind == RECYCLE and gifts:
                done = await self.recycle(gifts[0], 1)
            elif kind == EXCHANGE:
                done = await self.exchange(good, gifts)
            else:
                self.tell("gifts_none", kind=kind)
                continue
            if done:
                svc.needs.played(key, 1, COMEBACK_SEC)

    async def give(self, gift):
        roles = await self.session.activity_request("RoleList", {})
        if _int(roles.get("send_gift_cnt")) >= daily_gifts():
            self.tell("gifts_none", kind=GIVE, reason="no gifts left today", sent=_int(roles.get("send_gift_cnt")))
            return False
        role = receiver(roles, self.service.now())
        if not role:
            self.tell("gifts_none", kind=GIVE, reason="no player owned")
            return False
        _, item, uniq, _ = gift
        self.attempt(GIVE, role=role, item=item)
        answer = await self.socket(str(GIVE), "RoleGift", {"role_id": role, "item_uniq_id": uniq})
        if answer is None:
            return False
        bond = answer.get("bond_change_rsp") or {}
        self.service._record("gifts_given", role=role, item=item, sent_today=_int(answer.get("send_gift_cnt")),
                             level=_int(bond.get("level")), bond_exp=_int(bond.get("bond_exp")),
                             bond_inc=_int(bond.get("bond_inc")))
        return True

    async def recycle(self, gift, num):
        _, item, uniq, _ = gift
        self.attempt(RECYCLE, item=item, num=num)
        answer = await self.socket(str(RECYCLE), "RecycleItem", {"req_item_list": [{"item_uniq_id": uniq, "item_num": num}]})
        if answer is None:
            return False
        got = [[_int((r.get("decompose_item") or r.get("org_item") or {}).get("item_id")),
                _int((r.get("decompose_item") or r.get("org_item") or {}).get("num"))]
               for r in rows_of(answer.get("reward_list")) if isinstance(r, dict)]
        self.service._record("gifts_recycled", item=item, num=num, got=got)
        return True

    async def exchange(self, good, gifts):
        """Buy one ``good`` of the fragment shop, recycling the gifts beyond the reserve that the
        fragments short take."""
        price = fragment_good(good)
        if price is None:
            self.tell("gifts_none", kind=EXCHANGE, good=good, reason="not a good of the fragment shop")
            return False
        cost, _ = price
        have = await self.held(FRAGMENT)
        spare = spare_gifts(gifts)
        while have < cost and spare:
            quality, item, uniq, num = spare.pop(0)
            each = fragments_of(item)
            if each <= 0:
                continue
            take = min(num, -(-(cost - have) // each))
            if not await self.recycle((quality, item, uniq, num), take):
                return False
            have += take * each
        if have < cost:
            self.tell("gifts_short", good=good, fragments=have, cost=cost, gifts=sum(g[3] for g in gifts))
            return False
        self.attempt(EXCHANGE, good=good, cost=cost)
        payload = {"shop_type": FRAGMENT_SHOP, "id": good, "num": 1, "mask": "buyWithProp"}
        if await self.ask(f"buy:{good}", BUY, payload) is None:
            return False
        self.service._record("gifts_exchanged", good=good, cost=cost)
        return True

    async def socket(self, action, name, fields):
        """One request on the game socket; a refusal blocks ``action``."""
        try:
            return await self.session.activity_request(name, fields)
        except RewardAPIError as exc:
            if not refused(exc):
                raise
            self.block(action, exc)
            return None
