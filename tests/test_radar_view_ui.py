"""The 雷达 view as plain strings: no browser, no DOM, no network."""
import shutil
import subprocess
from pathlib import Path

import pytest

_PRELUDE = r'''
const fs = require("fs"), vm = require("vm"), assert = require("assert");
const window = {};
vm.runInNewContext(fs.readFileSync("pf_entertainment/static/radar-view.js", "utf8"), {window, document: {}});
const {parts, sheetHtml} = window.PFRadar;
const has = (html, ...needles) => needles.forEach((n) => assert(html.includes(n), `missing ${n}\n in ${html}`));
const lacks = (html, ...needles) => needles.forEach((n) => assert(!html.includes(n), `unexpected ${n}`));
const item = (o) => ({kind_key: null, type: 105, thing: null, what: "gap", steps: 1, detail: "", ignored: null, ...o});
const state = {res: "1.7.7", file: "local/state/lobby_ignores.json",
  findings: [
    {key: "gaps:theme_activity:10010", title: "活动缺口 · 即兴恶作剧", when: "10-29 → 11-29，进行中", muted: "", items: [
      item({key: "task:105", text: "参与SNG赛事1次"}),
      item({key: "limit:101:10040101", kind_key: "limit:101", type: 101, thing: 10040101, what: "limit",
            text: "玩260手德扑-AOF", detail: "任务手数每天最多 15，每周只能做到 105"}),
      item({key: "task:130", text: "玩1场MTT", ignored: {reason: "不打 MTT", by: "外部"}})]},
    {key: "uncovered:invite_rules:6001", title: "新活动 · 邀请活动 6001（还没有代码）", when: "", muted: "邀请（内部）", items: []}],
  ignores: [
    {key: "task:324", reason: "直播做不了", by: "内部", ignore: true, overridden: false, at: "", label: "类型 324"},
    {key: "task:325", reason: "直播做不了", by: "内部", ignore: true, overridden: false, at: "", label: "类型 325"},
    {key: "task:130", reason: "不打 MTT", by: "外部", ignore: true, overridden: false, at: "11-26 10:20", label: "类型 130"},
    {key: "task:103", reason: "按下注额", by: "内部", ignore: false, overridden: true, at: "11-26 10:22", label: "类型 103"}]};
'''


def _node(script: str) -> None:
    if not shutil.which("node"):
        pytest.skip("node not installed")
    result = subprocess.run(["node", "-e", _PRELUDE + script], cwd=Path(__file__).resolve().parents[1],
                            capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr


def test_undone_items_are_listed_with_an_ignore_button_each_and_ignored_ones_folded():
    _node(r'''
const p = parts(state);
assert.strictEqual(p.openCount, 2); assert.strictEqual(p.quietCount, 3);
has(p.summary, '<span class="num">2</span><span>项没处理</span>', "（1.7.7）", 'aria-selected="true">没处理');
has(p.list, "即兴恶作剧", "参与SNG赛事1次", "类型 105", 'data-act="ask" data-ref="0:0"', 'data-ref="0:1"',
    '<b class="rd-flag">额度不够</b>任务手数每天最多 15', "已忽略 1 项", "不打 MTT");
lacks(p.list, "邀请活动");                      // a finding the ignore list covers whole is not listed
''')


def test_the_ignored_list_groups_the_projects_decisions_and_offers_the_way_back():
    _node(r'''
const p = parts(state, {show: "ignored"});
has(p.list, "你的决定", "项目的决定", "2 类任务", 'data-act="unignore" data-key="task:324 task:325"',
    'data-act="reset" data-key="task:130">恢复提醒', "你改为提醒", 'data-act="reset" data-key="task:103">按项目的来',
    "local/state/lobby_ignores.json");
''')


def test_the_sheet_offers_this_item_or_its_whole_kind():
    _node(r'''
has(sheetHtml(item({key: "task:126:1018", kind_key: "task:126", type: 126, thing: 1018, text: "使用天濑千寻参与2场赛事"})),
    'value="task:126:1018" checked', "只忽略这一种", 'value="task:126"', "类型 126 的任务都忽略", "对所有活动和日常任务生效");
const single = sheetHtml(item({key: "task:105", text: "玩1场SNG"}));
has(single, 'value="task:105" checked', "类型 105 的任务都忽略"); lacks(single, "只忽略这一种");
has(sheetHtml(item({key: "period:creator_activity:50001", kind_key: "table:creator_activity", what: "period", text: "整个活动"})),
    "只忽略这一期", "这类活动以后每一期都忽略");
''')
