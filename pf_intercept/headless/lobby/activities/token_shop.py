"""代币兑换类活动: the template of the activities that pay a token for tasks and play, and sell
goods for it in their own shop. 主题活动 (a period a month: 即兴恶作剧, 超天酱直播中 ...) and
创作盛典 are this template; a new kind of it is a subclass that names its requests and tables.

A pass, for the period the server names (``period``):

1. the tasks: read them, collect the finished ones, read again, put the rows on the needs board
   (the side games, football, the hands and the reports are done for them by their doers);
2. the shop: with the tokens in the bag, buy every good of this period (the subclass's shop
   table, the rows naming the period) in the order of ``rank``, each up to its limit, as the
   purchase counts of ``shop/limit`` stand: 结缘晶片, then the chips, then gifts and gift packs,
   then the rest (decorations ...), the shop's own order within each. A good not affordable yet
   stops the buying: the tokens are saved for it, and what comes after it waits.

Tokens left at the end become chips at 1:1 by mail, while the shop's chips cost a tenth of that
or less, so nothing is kept back. Buys go through ShopModel:buyWithProp's request; the answer
carries no reward list (the client draws the rewards from its tables), so the chips are counted
from the table and a fresh ``shop/limit`` read has to show every purchase, or that good is left
alone for ``BLOCK_SEC``. Written from the client's code; the answers were never seen on the wire.
"""
from __future__ import annotations

from dataclasses import dataclass

from pf_intercept.headless.lobby.core.base import GOLD, Activity, RewardAPIError, _int, game_day, rows_of
from pf_reverse.tables import TABLES

BUY, LIMITS = "/shop/buyWithProp", "/shop/limit"
COMPLETED = 2                   # TaskStatus.Completed: finished, reward not collected
MAX_NUM = 100                   # units in one request, for goods the client sells in batches
MAX_BUYS = 30                   # requests in a pass; the rest follow on the next one
BOND_CRYSTAL = 10200002         # 结缘晶片
GIFTS = {106, 302, 303}         # GPropKind: a gift, a random gift pack, a chosen gift pack


@dataclass(frozen=True)
class Good:
    id: int
    item: int                   # what it gives
    count: int                  # how many of it per unit
    token: int                  # what it costs
    cost: int                   # how many tokens per unit
    limit: int | None           # units the account may buy (None: no limit)
    batch: bool                 # several units in one request
    index: int

    @property
    def chips(self) -> bool:
        return self.item == GOLD


def goods_of(rows):
    """Goods of shop rows ({props: [kind, item, count], exchange_cost: [token, cost], ...})."""
    out = []
    for r in rows:
        props, cost = r.get("props"), r.get("exchange_cost")
        if not (isinstance(props, list) and len(props) >= 3 and isinstance(cost, list) and len(cost) >= 2):
            continue
        limit = _int(r.get("limit_count")) or None
        out.append(Good(_int(r.get("id")), _int(props[1]), _int(props[2]), _int(cost[0]), _int(cost[1]),
                        limit, _int(r.get("batch")) == 1, _int(r.get("index"))))
    return out


def plan(goods, bought, tokens):
    """[(good, units)] to buy now with ``tokens``, in the order given: each good up to what its
    limit leaves; the first good still wanted but not affordable stops the list."""
    out = []
    for good in goods:
        left = good.limit - bought.get(good.id, 0) if good.limit else tokens // max(good.cost, 1)
        if left <= 0:
            continue
        units = min(left, tokens // max(good.cost, 1))
        if units <= 0:
            break
        out.append((good, units))
        tokens -= units * good.cost
    return out


def rank(good):
    """Where a good stands in the buying order: 结缘晶片 (scarce), the chips (the money), gifts and
    gift packs (the gift tasks use them), the rest; the shop's own order within each."""
    kind = _int((TABLES.row("props", good.item) or {}).get("type"))
    tier = 0 if good.item == BOND_CRYSTAL else 1 if good.chips else 2 if kind in GIFTS else 3
    return tier, good.index, good.id


def ready(rows):
    return sorted({_int(r.get("id")) for r in rows if isinstance(r, dict)
                   and _int(r.get("status")) == COMPLETED and _int(r.get("id")) > 0})


class TokenShop(Activity):
    """The template; a subclass sets the shop and writes ``current``, ``task_rows``, ``claim``."""

    shop_table = ""             # tpl table of the goods
    shop_column = ""            # its column naming the period
    shop_type = 0               # the shop_type sent with a purchase

    async def current(self):
        """The period the server names (an id, 0 for none)."""
        raise NotImplementedError

    async def task_rows(self, found):
        """The period's task rows as the server has them, or None when it would not say."""
        raise NotImplementedError

    async def claim(self, found, rows):
        """Collect the finished tasks of ``rows``; the ids asked for (empty when none)."""
        raise NotImplementedError

    def goods(self, found):
        """The period's goods sold for its token, in buying order."""
        rows = [r for r in TABLES.rows(self.shop_table) if _int(r.get(self.shop_column)) == found.ident]
        return sorted((g for g in goods_of(rows) if g.token == _int(found.row.get("activity_item"))), key=rank)

    async def check(self):
        self.load()
        if self.blocked("data"):
            return
        found = self.period(await self.current())
        if found is None:
            return
        rows = await self.task_rows(found)
        if rows is not None and not self.blocked("claim"):
            asked = await self.claim(found, rows)
            if asked:
                rows = await self.task_rows(found)
                still = set(asked) & set(ready(rows or []))
                if still:
                    # Answered as collected and still finished: this worker misreads the tasks.
                    self.block("claim", RewardAPIError("claim", "still due: " + ",".join(map(str, sorted(still)))))
        if rows is not None:
            self.tell(f"{self.name}_tasks", ident=found.ident, rows=sorted(
                [_int(r.get("task_id")), _int(r.get("status")), _int(r.get("current_value"))] for r in rows))
            self.service.needs.want(self.name, rows)
        await self.exchange(found)

    async def bought(self):
        """{good id: units bought} of this shop, from ``shop/limit``; None when it would not say."""
        data = await self.ask("limits", LIMITS, {"mask": "shopLimit"})
        if data is None:
            return None
        return {_int(r.get("id")): _int(r.get("count")) for r in rows_of(data.get("list"))
                if isinstance(r, dict) and _int(r.get("shop_type")) == self.shop_type}

    async def exchange(self, found):
        goods = [g for g in self.goods(found) if not self.blocked(f"buy:{g.id}")]
        if not goods or self.blocked("limits"):
            return
        token = goods[0].token
        tokens = await self.held(token)
        # Every hand earns tokens: the balance is journalled once a game day, not on every pass.
        today = (found.ident, game_day(self.service.now()))
        if self.told.get(f"{self.name}_tokens") != today:
            self.told[f"{self.name}_tokens"] = today
            self.service._record(f"{self.name}_tokens", ident=found.ident, token=token, held=tokens)
        if tokens < min(g.cost for g in goods):
            return
        before = await self.bought()
        if before is None:
            return
        # What is left to buy, good by good: all zero is "the shop is emptied".
        self.tell(f"{self.name}_shop", ident=found.ident,
                  left={str(g.id): (g.limit - before.get(g.id, 0)) if g.limit else None for g in goods})
        todo, done, requests = plan(goods, before, tokens), {}, 0
        for good, units in todo:
            while units > 0 and requests < MAX_BUYS:
                num = min(units, MAX_NUM) if good.batch else 1
                requests += 1
                if not await self.buy(found, good, num):
                    units = 0
                    break
                done[good.id] = done.get(good.id, 0) + num
                units -= num
        if not done:
            return
        after = await self.bought()
        if after is None:
            return
        for good_id, num in done.items():
            if after.get(good_id, 0) < before.get(good_id, 0) + num:
                # Answered as bought and not counted: this worker misreads the shop.
                self.block(f"buy:{good_id}", RewardAPIError(BUY, f"count {before.get(good_id, 0)} -> "
                                                                 f"{after.get(good_id, 0)}, bought {num}"))
        if requests >= MAX_BUYS:
            self.service.wake(self.name, 5)

    async def buy(self, found, good, num) -> bool:
        svc = self.service
        payload = {"shop_type": self.shop_type, "id": good.id, "num": num, "mask": "buyWithProp"}
        svc._record(f"{self.name}_buy", ident=found.ident, good=good.id, item=good.item, count=good.count * num,
                    num=num, cost=good.cost * num, token=good.token, required=True)
        try:
            answer = await self.ask(f"buy:{good.id}", BUY, payload)
        except RewardAPIError as exc:
            if exc.code is None and good.chips:
                await svc.activity_uncertain(f"{self.name}_exchange", good=good.id, num=num)
            raise
        if answer is None:
            return False
        await svc.activity_payout(f"{self.name}_exchange", good.count * num if good.chips else 0,
                                  good=good.id, item=good.item, count=good.count * num, cost=good.cost * num)
        return True
