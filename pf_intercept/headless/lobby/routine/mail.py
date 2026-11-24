"""邮件 (the mailbox): collect every mail's attachments, as a player opening each mail would.

Requests from the client's EmailModel.lua and EmailMain.lua. The server pushes MAIL_REFRESH
(10040, seen in headless.log with the message "[0]": the mail types to read again) when mail
arrives; the push wakes this worker, and it also looks every ``RECHECK_SEC`` without one.

A pass reads the counts (``mail/num``). For a type with attachments not collected it reads the
list, and for each such mail does what the mail screen does: opens it (``mail/detail``, which
marks it read and shows the attachments) and presses its claim button (``mail/receive`` with
that one id). One mail at a time, so every answer is one mail's attachments, and the journal
says which mail paid what.

Football settlements (6001) and refunds of cancelled matches (6002) give football stakes back.
Stakes are in no ledger (football.py), so these are journalled as ``football_payout``, not as
rewards. Every other mail's chips are reward money.

A mail with attachments not collected does not expire (the screen shows it no deadline), so
nothing here is urgent: a mail whose claim the server refuses is left alone for
``rewards.BLOCK_SEC``, and so is one answered as collected that the next read still shows due.
Written from the client's code; the server's answers were never seen on the wire.
"""
from __future__ import annotations

from pf_intercept.headless.lobby.core.base import GOLD, Activity, RewardAPIError, _amount, _int, rows_of

MAIL_REFRESH = 10040           # pushed when mail arrives
NUM, LIST, DETAIL, RECEIVE = "/mail/num", "/mail/list", "/mail/detail", "/mail/receive"
TYPES = ((0, "normal"), (1, "special"))     # EmailModel.MAIL_TYPE, and mail/num's field for each
RECEIVED = 3                    # UserMailStatusReadReceived: attachments collected
PAGE = 20                       # EmailModel.PAGE_SIZE
MAX_PAGES = 10                  # of one type in a pass
MAX_CLAIMS = 20                 # mails in a pass; the rest on the next
LANG = "en"                     # what the client sends for English, as the HTTP Lang header says
RECHECK_SEC = 1800.0            # no push: look again this much later
# tpl_system_mail: mails that give a side activity's stakes back, and that activity's ledger.
STAKE_RETURNS = {6001: "football", 6002: "football"}


def items_of(rows):
    """[[item_id, num], ...] received, as BackpackClaimResult reads a claim's items: a plain item
    (``item_id`` or ``id``, ``num``) or a RewardItemInfo, whose piece is ``decompose_item`` when
    it was decomposed and ``org_item`` otherwise."""
    received = []
    for row in rows_of(rows):
        if not isinstance(row, dict):
            raise ValueError("invalid mail item")
        piece = row.get("org_item") or row
        broken = row.get("decompose_item")
        if row.get("is_decompose") and isinstance(broken, dict) and _int(broken.get("item_id")) > 0:
            piece = broken
        ident = _int(piece.get("item_id") or piece.get("id"))
        if ident <= 0:
            raise ValueError("mail item without an id")
        received.append([ident, _amount(piece["num"])])
    return received


def due(row):
    return isinstance(row, dict) and bool(row.get("has_item")) and _int(row.get("status"), -1) != RECEIVED


class Mail(Activity):
    name = "mail"
    title = "邮件"
    switch = ("mail", "不领邮件附件（足球结算、排行榜等都走邮件），其余奖励照常")
    pushes = (MAIL_REFRESH,)

    def __init__(self, service, session):
        super().__init__(service, session)
        self.next_read = 0.0        # server time before which, without a push, nothing is read

    def pushed(self, notice_type):
        """MAIL_REFRESH: mail arrived."""
        self.next_read = 0.0
        self.service.wake(self.name, 1)

    async def check(self):
        svc = self.service
        if svc.now() < self.next_read:
            return
        self.load()
        if self.blocked("num"):
            return
        counts = await self.ask("num", NUM, {})
        if counts is None:
            return
        waiting = {kind: _int((counts.get(name) if isinstance(counts.get(name), dict) else {}).get("item_total"))
                   for kind, name in TYPES}
        self.tell("mail_state", waiting={str(kind): count for kind, count in waiting.items()},
                  fields=sorted(map(str, counts)))
        claims = 0
        for kind, _ in TYPES:
            if waiting[kind] <= 0 or claims >= MAX_CLAIMS:
                continue
            mails = await self.claimable(kind, waiting[kind])
            if mails is None:
                continue
            collected = []
            for mail in mails[:MAX_CLAIMS - claims]:
                claims += 1
                if await self.collect(kind, mail):
                    collected.append(str(mail.get("id")))
            if not collected:
                continue
            again = await self.claimable(kind, waiting[kind])
            for mail in again or ():
                if str(mail.get("id")) in collected:
                    # Answered as collected and still due: this worker misreads the mailbox.
                    self.block(f"receive:{mail.get('id')}", RewardAPIError(RECEIVE, "still due"))
        # Mails left over by the cap are read on the next pass, the rest when mail arrives.
        self.next_read = svc.now() + (0.0 if claims >= MAX_CLAIMS else RECHECK_SEC)

    async def claimable(self, kind, waiting):
        """Mails of a type with attachments not collected and not left alone, from the first
        pages of the list until as many as the counts said were seen."""
        found, seen, offset = [], 0, 0
        for _ in range(MAX_PAGES):
            page = await self.ask("list", LIST, {"offset": offset, "size": PAGE, "mail_type": kind,
                                                 "lang": LANG, "immediately": True})
            if page is None:
                return None
            rows = [row for row in rows_of(page.get("list")) if isinstance(row, dict)]
            if offset == 0:
                self.tell(f"mail_list_{kind}", total=_int(page.get("total")), waiting=_int(page.get("item_total")),
                          fields=sorted(map(str, page)), row_fields=sorted(map(str, rows[0])) if rows else [])
            ready = [row for row in rows if due(row)]
            seen += len(ready)
            found += [row for row in ready if not self.blocked(f"receive:{row.get('id')}")]
            offset += len(rows)
            if len(rows) < PAGE or seen >= waiting or offset >= _int(page.get("total")):
                break               # a short page is the last
        return found

    async def collect(self, kind, mail):
        """Open one mail and collect its attachments; whether the server answered as collected."""
        svc = self.service
        ident = mail.get("id")      # the server's own id, passed back as it came
        if self.blocked(f"detail:{ident}"):
            return False
        opened = await self.ask(f"detail:{ident}", DETAIL, {"id": ident, "lang": LANG})
        if opened is None:
            return False
        body = opened.get("data") if isinstance(opened.get("data"), dict) else {}
        template = _int(body.get("system_mail_id") or mail.get("system_mail_id"))
        ledger = STAKE_RETURNS.get(template, "rewards")
        self.tell("mail_detail", fields=sorted(map(str, body)))
        if _int(body.get("status"), -1) == RECEIVED:
            return False            # collected meanwhile, by the client on another device
        try:
            attached = items_of(body.get("item_list"))
        except (ValueError, TypeError, KeyError, OverflowError):
            attached = None         # shown for the journal only; the claim's answer is what counts
        details = {"mail": ident, "mail_type": kind, "template": template, "attached": attached}
        try:
            answer = await self.ask(f"receive:{ident}", RECEIVE, {"id_arr": [ident], "mail_type": kind})
            if answer is None:
                return False        # refused: this mail is left alone for a while
            try:
                if "item_list" not in answer:
                    raise KeyError("item_list")
                items = items_of(answer["item_list"])
            except (ValueError, TypeError, KeyError, OverflowError):
                raise RewardAPIError(RECEIVE) from None      # collected, with what cannot be read
        except RewardAPIError as exc:
            if exc.code is None:    # it may have reached the server, and the mail may hold chips
                if ledger == "rewards":
                    await svc.activity_uncertain("mail", **details)
                else:
                    svc._record(f"{ledger}_payout_uncertain", **details)
            raise
        chips = sum(num for item, num in items if item == GOLD)
        if ledger == "rewards":
            await svc.activity_payout("mail", chips, items=items, **details)
        else:
            svc._record(f"{ledger}_payout", chips=chips, items=items, **details)
        return True
