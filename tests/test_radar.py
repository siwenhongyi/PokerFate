"""活动雷达: the calendar, the findings, the ignore list and the phone, from scripted tables."""
import asyncio
import json
from unittest.mock import AsyncMock

import pytest

from pf_intercept.headless.lobby.core.base import Worker
from pf_intercept.headless.lobby.core.service import RewardService
from pf_intercept.headless.lobby.radar import calendar as cal
from pf_intercept.headless.lobby.radar import findings as fd
from pf_intercept.headless.lobby.core.ignore import Ignores
from pf_intercept.headless.lobby.radar.worker import Radar
from pf_reverse import tables as tb

DAY = 86400
TABLES = {
    "tpl_theme_activity.lua": "local keys = {'id','name','time_start','time_end','task','white_list_start',}\n"
                              "local bodys = {\n{1,\"LAB_T\",1000,865000,{7},500},\n{2,\"LAB_T\",100,200,{7},0}\n}",
    "tpl_theme_task.lua": "local keys = {'task_id','group','task_type','value','dec',}\n"
                          "local bodys = {\n{11,7,101,{30030101,10},\"LAB_D\"},\n{12,7,305,{1},\"LAB_R\"},\n"
                          "{13,7,305,{2},\"LAB_R\"},\n{14,7,101,{30030101,1500},\"LAB_D\"},\n{15,7,325,{5},\"LAB_L\"}\n}",
    "tpl_festival_activity.lua": "local keys = {'id','name','time_start','time_end','task',}\n"
                                 "local bodys = {\n{3,\"LAB_F\",1500,3000,{8}}\n}",
    "tpl_dailytasks.lua": "local keys = {'task_id','task_type','value','dec',}\n"
                          "local bodys = {\n{21,101,{30030101,150},\"LAB_D\"},\n{22,201,{3},\"LAB_G\"}\n}",
    "tpl_mult_language.lua": "local keys = {'id','zh',}\nlocal bodys = {\n{\"LAB_T\",\"主题\"},\n{\"LAB_F\",\"节日\"},\n"
                             "{\"LAB_D\",\"玩{p1}次{p2}\"},\n{\"LAB_R\",\"招募{p1}次\"},\n{\"LAB_G\",\"送礼{p1}次\"},\n"
                             "{\"LAB_L\",\"直播{p1}场\"}\n}",
    "tpl_task_type_info.lua": "local keys = {'id','name',}\nlocal bodys = {\n{30030101,\"LAB_C\"}\n}",
    "tpl_constdata.lua": "tpl_constdata = {\n\tDispatch_Start = 100,\n\tDispatch_End = 900\n}",
}


class Theme(Worker):
    name, title, tables, leaves = "theme", "主题活动", ("theme_activity",), ("抽卡池不做",)


class Games(Worker):
    name, title = "sidegames", "彩球机 / 弹球"
    does, limits = {(101, 30030101): "彩球"}, {(101, 30030101): 100}


@pytest.fixture
def t(tmp_path):
    for name, text in TABLES.items():
        (tmp_path / name).write_text(text, encoding="utf-8")
    return tb.Tables(tmp_path)


def by_key(found):
    return {f.key: f for f in found}


def test_the_calendar_and_a_periods_tasks(t):
    assert [(s.table, s.ident, s.title, s.start) for s in cal.calendar(t)] == [
        ("constdata:Dispatch", 0, "协会经营（派遣）", 100), ("theme_activity", 2, "主题", 100),
        ("theme_activity", 1, "主题", 1000), ("festival_activity", 3, "节日", 1500)]
    seen = next(s for s in cal.calendar(t) if s.ident == 1)
    assert [(task["task_id"], days) for task, days in cal.tasks_of(seen, t)] == [(i, 10.0) for i in (11, 12, 13, 14, 15)]
    assert cal.describe(t.row("theme_task", 11), t) == "玩10次LAB_C"


def test_findings(t):
    found = by_key(fd.findings(1200, [Theme, Games], tables=t, ignores=Ignores(internal={})))
    assert set(found) == {"gaps:theme_activity:1", "uncovered:festival_activity:3", "ended:theme_activity:2",
                          "gaps:routine"}
    theme = found["gaps:theme_activity:1"]
    assert "招募1次（类型 305，共 2 档）" in theme.body and "抽卡池不做" in theme.body
    # Somebody plays the colour game, 100 rounds a day: 1500 in 10 days is more than that.
    assert "玩1500次LAB_C（类型 101）：彩球机 / 弹球每天最多 100，10 天内只能做到 1000" in theme.body
    assert "玩150次LAB_C（类型 101）：彩球机 / 弹球每天最多 100，每日只能做到 100" in found["gaps:routine"].body
    assert "送礼3次" in found["gaps:routine"].body


def test_what_is_undone_repeats_and_what_happened_is_told_once(t):
    found = by_key(fd.findings(1200, [Theme, Games], tables=t))
    assert {k: f.repeat for k, f in found.items()} == {
        "gaps:theme_activity:1": True, "uncovered:festival_activity:3": True, "gaps:routine": True,
        "ended:theme_activity:2": False}
    early = by_key(fd.findings(1000 - 40 * DAY, [Theme, Games], tables=t))["gaps:theme_activity:1"]
    later = by_key(fd.findings(1000 - 39 * DAY, [Theme, Games], tables=t))["gaps:theme_activity:1"]
    assert early.body != later.body and early.digest == later.digest


def test_the_ignore_list_keeps_things_out_of_the_phone_and_in_the_report(t):
    none = Ignores(internal={})
    lines = by_key(fd.findings(1200, [Theme, Games], tables=t, ignores=none))["gaps:theme_activity:1"].body
    assert "直播5场" in lines and "1000" in lines
    ignores = Ignores(internal={"task:325": "直播做不了", "limit:101:30030101": "不追这么多局",
                                "table:festival_activity": "节日活动不做"})
    found = by_key(fd.findings(1200, [Theme, Games], tables=t, ignores=ignores))
    theme = found["gaps:theme_activity:1"]
    assert "直播" not in theme.body and "只能做到 1000" not in theme.body
    assert any("直播5场" in line and "直播做不了（内部）" in line for line in theme.ignored)
    assert any("1500" in line and "不追这么多局（内部）" in line for line in theme.ignored)
    assert found["uncovered:festival_activity:3"].muted == "节日活动不做（内部）"


def test_an_external_entry_wins_over_an_internal_one(tmp_path):
    external = tmp_path / "ignores.json"
    external.write_text(json.dumps({"task:325": {"ignore": False}, "task:201": {"ignore": True, "reason": "不送礼"}}))
    ignores = Ignores(internal={"task:325": "直播做不了", "task:305": "不招募"}, external_path=external)
    assert ignores.task(325) is None                        # the user took the project's decision back
    assert ignores.task(201) == ("不送礼", "外部") and ignores.task(305) == ("不招募", "内部")
    assert ignores.task(101, 30030101) is None and Ignores(internal={"task:101": "x"}).task(101, 5) == ("x", "内部")
    assert Ignores(internal={}, external_path=tmp_path / "missing.json").task(201) is None


def test_a_hot_update_is_told_with_its_new_tables_pages_and_protocol():
    f = fd.hot_update_finding({"res_from": "1.7.7", "res_to": "1.7.8", "removed": [], "differ": 160,
                               "changed": ["lua/src/tpl/tpl_new.lua", "lua/src/app/views/Dice/Main.lua",
                                           "proto/Proto/CSGame.proto"],
                               "added": ["lua/src/tpl/tpl_new.lua", "lua/src/app/views/Dice/Main.lua"]})
    assert f.title == "热更新 · 1.7.7 → 1.7.8" and "tpl_new" in f.body and "views/Dice" in f.body
    assert "160" in f.body and "gen_pb2.sh" in f.body and not f.repeat


def test_the_phone_hears_what_is_undone_on_every_run_and_what_happened_once(tmp_path):
    sent, clock = [], [1_000_000.0]

    def radar():
        svc = RewardService(uid=1, authorization="x", http_base="", chnl=1, version="1", on_credit=AsyncMock(),
                            ready=asyncio.Event(), journal_path=tmp_path / "rewards.jsonl",
                            alert=lambda title, body: sent.append(title))
        svc.now = lambda: clock[0]
        return Radar(svc, None)
    report = {"update": None, "error": None, "findings": [
        {"key": "gaps:x", "title": "缺口", "body": "1", "repeat": True},
        {"key": "ended:x", "title": "结束", "body": "2"},
        {"key": "uncovered:y", "title": "忽略的", "body": "", "muted": "不做（内部）", "repeat": True}]}
    radar().tell_findings(report)
    clock[0] += 3600                                   # a restart an hour later: nothing again
    radar().tell_findings(report)
    clock[0] += 6 * 3600                               # the next run: the gap again, the end not
    radar().tell_findings(report)
    assert sent == ["缺口", "结束", "缺口"]


def test_a_scan_is_told_as_soon_as_it_ends_and_the_next_starts_six_hours_after_it(tmp_path):
    async def run():
        sent, clock = [], [1_000_000.0]
        svc = RewardService(uid=1, authorization="x", http_base="", chnl=1, version="1", on_credit=AsyncMock(),
                            ready=asyncio.Event(), journal_path=tmp_path / "rewards.jsonl",
                            alert=lambda title, body: sent.append(title))
        svc.now = lambda: clock[0]
        radar = svc.attach(Radar(svc, None))
        done = asyncio.Event()

        async def scan():
            await done.wait()
            return {"findings": [{"key": "gaps:x", "title": "缺口", "body": "1", "repeat": True}]}
        radar.scan = scan
        svc.due["radar"] = clock[0] + radar.interval()      # as the service sets it before a check
        await radar.check()                                 # the scan starts
        clock[0] += 20
        done.set()
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        assert svc.due["radar"] <= clock[0]                 # its end woke the radar
        await radar.check()
        assert sent == ["缺口"] and svc.due["radar"] == 1_000_000.0 + 6 * 3600
    asyncio.run(run())
