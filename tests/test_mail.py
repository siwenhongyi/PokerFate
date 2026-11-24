"""邮件: scripted server replies, no real game requests."""
from __future__ import annotations

import asyncio
import re

import pytest

from pf_intercept.headless.lobby.routine import mail as ml
from pf_intercept.headless.lobby.core import base as lb
from pf_intercept.headless.lobby.routine import fund as fd
from pf_intercept.headless.lobby.core import needs as nd
from pf_intercept.headless.lobby.core import service as sv
from pf_intercept.headless.lobby.routine import tasks as tk
from tests.test_dispatch import TPL, ScriptedHTTP, journal

NOW = 1795400000
GOLD = 10100001
NUM, LIST, DETAIL, RECEIVE = "/mail/num", "/mail/list", "/mail/detail", "/mail/receive"


def setup(tmp_path, replies):
    http = ScriptedHTTP(replies)
    credits = []

    async def credit(chips, uncertain):
        credits.append((chips, uncertain))

    ready = asyncio.Event()
    ready.set()
    svc = sv.RewardService(uid=42, authorization="session-secret", http_base="https://game.example",
                           chnl=3, version="1.7.5", on_credit=credit, ready=ready, post=http,
                           journal_path=tmp_path / "rewards.jsonl")
    clock = [NOW]
    svc.now = lambda: clock[0]
    worker = ml.Mail(svc, None)
    svc.attach(worker)
    return worker, http, credits, clock


def counts(normal=0, special=0):
    return (NUM, {"code": 0, "normal": {"total": 9, "unread_total": 1, "del_total": 0, "item_total": normal},
                  "special": {"total": 0, "unread_total": 0, "del_total": 0, "item_total": special}})


def mail(ident, *, item=True, status=0, template=0):
    return {"id": ident, "has_item": item, "status": status, "system_mail_id": template, "title": ""}


def page(*rows, total=None, waiting=None):
    return (LIST, {"code": 0, "total": len(rows) if total is None else total,
                   "item_total": sum(ml.due(row) for row in rows) if waiting is None else waiting,
                   "list": list(rows)})


def opened(ident, items, *, template=0, status=0):
    return (DETAIL, {"code": 0, "data": {"id": ident, "status": status, "system_mail_id": template,
                                         "item_list": items}})


def received(items):
    return (RECEIVE, {"code": 0, "item_list": items})


def listing(kind=0, offset=0):
    return {"offset": offset, "size": 20, "mail_type": kind, "lang": "en", "immediately": True}


def test_the_requests_are_the_clients():
    model = TPL.parent / "app" / "model" / "EmailModel.lua"
    if not model.exists():
        pytest.skip("client code not checked out")
    source = model.read_text(encoding="utf-8")
    assert 'Net:post("mail/num", nil,' in source
    assert 'Net:post("mail/list", {\n        offset = offset,\n        size = size or self.PAGE_SIZE,' in source
    assert "mail_type = mail_type,\n        lang = LanguageManager:getLanguage(),\n        immediately = true," in source
    assert 'Net:post("mail/detail", {\n        id = id,\n        lang = LanguageManager:getLanguage(),' in source
    assert 'Net:post("mail/receive", {\n        id_arr = id_arr,\n        mail_type = mail_type,\n        all = all,' in source
    assert re.search(r"UserMailStatusReadReceived\s+= 3,", source) and "self.PAGE_SIZE = 20" in source
    screen = (TPL.parent / "app" / "views" / "Email" / "EmailMain.lua").read_text(encoding="utf-8")
    assert "EmailModel:reqEamilAttach({self._select_id}, self._mail_type, nil, function(data)" in screen
    pushes = (TPL / "tpl_PushConsts.lua").read_text(encoding="utf-8")
    assert '{"MAIL_REFRESH",10040,nil}' in pushes and ml.MAIL_REFRESH == 10040
    mails = (TPL / "tpl_system_mail.lua").read_text(encoding="utf-8")
    words = (TPL / "tpl_mult_language.lua").read_text(encoding="utf-8")
    assert '{6001,"LAB_MAIL_TITLE_5",' in mails and '{"LAB_MAIL_TITLE_5","足球竞猜比赛结算通知",' in words
    assert '{6002,"LAB_MAIL_TITLE_6",' in mails and '{"LAB_MAIL_TITLE_6","足球竞猜比赛下架通知",' in words


@pytest.mark.parametrize("rows, items", [
    ([{"item_id": GOLD, "num": 2000}, {"id": 11400001, "num": "1"}], [[GOLD, 2000], [11400001, 1]]),
    ({"a": {"item_id": GOLD, "num": 5}}, [[GOLD, 5]]),
    ([{"org_item": {"item_id": 20200014, "num": 1}, "is_decompose": False}], [[20200014, 1]]),
    ([{"org_item": {"item_id": 20200014, "num": 1}, "is_decompose": True,
       "decompose_item": {"item_id": GOLD, "num": 3000}}], [[GOLD, 3000]]),
    (None, []),
])
def test_items_of(rows, items):
    assert ml.items_of(rows) == items


@pytest.mark.parametrize("rows", [["x"], [{"num": 1}], [{"item_id": GOLD}], [{"item_id": GOLD, "num": -1}]])
def test_items_of_unreadable(rows):
    with pytest.raises((ValueError, KeyError)):
        ml.items_of(rows)


def test_each_mail_is_opened_and_collected_and_football_money_is_no_reward(tmp_path):
    async def run():
        rows = [mail("a", template=1003), mail("b", item=False), mail("c", status=3), mail("d", status=2, template=6001)]
        worker, http, credits, clock = setup(tmp_path, [
            counts(normal=2),
            page(*rows),
            opened("a", [{"item_id": GOLD, "num": 2000}, {"item_id": 20400009, "num": 1}], template=1003),
            received([{"item_id": GOLD, "num": 2000}, {"item_id": 20400009, "num": 1}]),
            opened("d", [{"item_id": GOLD, "num": 1800}], template=6001, status=2),
            received([{"item_id": GOLD, "num": 1800}]),
            page(mail("a", status=3, template=1003), *rows[1:3], mail("d", status=3, template=6001)),
        ])
        await worker.check()
        assert not http.replies
        assert http.calls == [
            (NUM, {}), (LIST, listing()),
            (DETAIL, {"id": "a", "lang": "en"}), (RECEIVE, {"id_arr": ["a"], "mail_type": 0}),
            (DETAIL, {"id": "d", "lang": "en"}), (RECEIVE, {"id_arr": ["d"], "mail_type": 0}),
            (LIST, listing()),
        ]
        # The 2k of the first mail are reward money; the football settlement's 1.8k are not.
        assert credits == [(2000, False)] and worker.service.confirmed_chips == 2000
        claimed, = journal(tmp_path, "claimed")
        assert (claimed["kind"], claimed["chips"], claimed["mail"], claimed["template"]) == ("mail", 2000, "a", 1003)
        assert claimed["items"] == [[GOLD, 2000], [20400009, 1]]
        payout, = journal(tmp_path, "football_payout")
        assert (payout["chips"], payout["mail"], payout["template"]) == (1800, "d", 6001)
        # Nothing more until mail arrives or the recheck is due.
        assert worker.next_read == NOW + ml.RECHECK_SEC
        await worker.check()
        assert len(http.calls) == 7
    asyncio.run(run())


def test_nothing_waiting_reads_the_counts_only_and_a_push_reads_again(tmp_path):
    async def run():
        worker, http, credits, clock = setup(tmp_path, [counts()])
        await worker.check()
        assert http.calls == [(NUM, {})]
        clock[0] += 60
        await worker.check()
        assert len(http.calls) == 1
        worker.service.notify(ml.MAIL_REFRESH)
        assert worker.service.due["mail"] <= clock[0] + 1
        http.replies.extend([counts(special=1), page(mail("s", template=6002)),
                             opened("s", [{"item_id": GOLD, "num": 1000}], template=6002),
                             received([{"item_id": GOLD, "num": 1000}]), page(mail("s", status=3, template=6002))])
        await worker.check()
        assert not http.replies
        assert http.calls[2] == (LIST, listing(kind=1))
        assert http.calls[4] == (RECEIVE, {"id_arr": ["s"], "mail_type": 1})
        assert journal(tmp_path, "football_payout")[0]["chips"] == 1000 and credits == []
    asyncio.run(run())


def test_the_list_is_read_page_by_page_until_the_waiting_mails_are_seen(tmp_path):
    async def run():
        first = [mail(f"m{n}", item=False) for n in range(19)] + [mail("x")]
        worker, http, credits, clock = setup(tmp_path, [
            counts(normal=2),
            page(*first, total=45, waiting=2),
            page(mail("y"), mail("z", item=False), total=45, waiting=2),
            opened("x", []), received([]),
            opened("y", []), received([]),
            page(*first[:19], mail("x", status=3), total=45, waiting=0),
            page(mail("y", status=3), total=45, waiting=0),
        ])
        await worker.check()
        assert not http.replies
        assert [payload["offset"] for endpoint, payload in http.calls if endpoint == LIST] == [0, 20, 0, 20]
    asyncio.run(run())


def test_a_refused_claim_leaves_that_mail_alone(tmp_path):
    async def run():
        worker, http, credits, clock = setup(tmp_path, [
            counts(normal=2), page(mail("a"), mail("b")),
            opened("a", [{"item_id": GOLD, "num": 10}]), (RECEIVE, {"code": 7}),
            opened("b", [{"item_id": GOLD, "num": 20}]), received([{"item_id": GOLD, "num": 20}]),
            page(mail("a"), mail("b", status=3)),
        ])
        await worker.check()
        assert not http.replies and credits == [(20, False)]
        blocked, = journal(tmp_path, "mail_blocked")
        assert (blocked["action"], blocked["code"]) == ("receive:a", 7)
        # The next pass reads the mailbox and leaves the refused mail alone.
        worker.next_read = 0
        http.replies.extend([counts(normal=1), page(mail("a"), mail("b", status=3))])
        await worker.check()
        assert not http.replies
    asyncio.run(run())


def test_a_mail_answered_as_collected_and_still_due_is_left_alone(tmp_path):
    async def run():
        worker, http, credits, clock = setup(tmp_path, [
            counts(normal=1), page(mail("a")),
            opened("a", [{"item_id": GOLD, "num": 10}]), received([{"item_id": GOLD, "num": 10}]),
            page(mail("a")),
        ])
        await worker.check()
        assert not http.replies
        blocked, = journal(tmp_path, "mail_blocked")
        assert blocked["action"] == "receive:a" and blocked["code"] == "still due"
    asyncio.run(run())


@pytest.mark.parametrize("template, event", [(1003, "claim_uncertain"), (6001, "football_payout_uncertain")])
def test_a_claim_without_a_readable_answer_is_uncertain(tmp_path, template, event):
    async def run():
        worker, http, credits, clock = setup(tmp_path, [
            counts(normal=1), page(mail("a", template=template)),
            opened("a", [{"item_id": GOLD, "num": 10}], template=template), (RECEIVE, {"code": 0}),
        ])
        with pytest.raises(lb.RewardAPIError):
            await worker.check()
        row, = journal(tmp_path, event)
        assert row["mail"] == "a" and row["template"] == template
        assert credits == ([(0, True)] if template == 1003 else [])
    asyncio.run(run())
