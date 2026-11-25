"""The shared money view as plain strings: no browser, no DOM, no network."""
import shutil
import subprocess
from pathlib import Path

import pytest

_PRELUDE = r'''
const fs = require("fs"), vm = require("vm"), assert = require("assert");
const window = {};
for (const file of ["live-table.js", "live-money.js"]) {
  vm.runInNewContext(fs.readFileSync("pf_entertainment/static/" + file, "utf8"), {window});
}
const {parts, chart, hold} = window.PFMoney;
const has = (html, ...needles) => needles.forEach((n) => assert(html.includes(n), `missing ${n}\n in ${html}`));
const same = (a, b) => assert.strictEqual(JSON.stringify(a), JSON.stringify(b));      // values come from another realm
'''


def _node(script: str) -> None:
    if not shutil.which("node"):
        pytest.skip("node not installed")
    result = subprocess.run(["node", "-e", _PRELUDE + script], cwd=Path(__file__).resolve().parents[1],
                            capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr


def test_figures_lead_with_the_session_result_and_list_the_account():
    _node(r'''
const board = {session_delta_chips: -118600, session_delta_bb: -5.93, big_blind: 20000, base_at: 1000,
  hand_points: [{}, {}, {}], current_total_chips: 126703654, wallet_chips: 124949654, table_chips: 1754000,
  reward_chips: 60000, rewards_uncertain: true, sidegame_net_chips: -78500,
  profit_lock_count: 1, auto_rebuy_count: 2, topup_count: 3, topup_chips: 420000, loss_cap_chips: 12000000, loss_stop: false};
let p = parts(board, {now: 1000 + 2 * 3600 + 60});
assert.strictEqual(p.leadClass, "neg-money");
has(p.lead, "-5.9<small>BB</small>");
has(p.sub, "<b>-118,600</b> 筹码", "已打 <b>3</b> 手", "运行了 2 小时 1 分", "盲注 <b>20k</b>");
has(p.facts, '当前总筹码</dt><dd class=""><span title="126,703,654 筹码">126.7m</span>', ">124.95m<", ">1.75m<",
    "活动奖励", ">60k</span><small>另有待确认</small>", '活动任务输赢</dt><dd class="neg-money">', ">-78.5k<",
    "盈利锁仓", "1<small>次</small>", "破产买入", "2<small>次</small>", "桌上补码", "3<small>次</small><small>共 420k</small>",
    "净亏损上限", "-12m<small>已用 1%</small>", 'style="width:1.0%"');
// ahead, at the cap, and before the bot knows the blind
p = parts({...board, session_delta_chips: 2346808, session_delta_bb: 117.34, loss_stop: true});
assert.strictEqual(p.leadClass, "pos-money");
has(p.lead, "+117.3<small>BB</small>"); has(p.sub, "<b>+2,346,808</b> 筹码"); has(p.facts, "已到上限，停止买入");
p = parts({session_delta_chips: -1250});
has(p.lead, "-1.3k"); has(p.sub, "已打 <b>0</b> 手"); has(p.facts, "净亏损上限</dt><dd class=\"\">-</dd>");
''')


def test_chart_draws_the_running_result_hand_by_hand():
    _node(r'''
const hands = [{ts: 1, hand_delta_bb: 2.5, delta_chips: 50000}, {ts: 2, hand_delta_bb: -7.5, delta_chips: -100000},
               {ts: 3, hand_delta_bb: 1, delta_chips: -80000}];
const svg = chart(hands, 430, 280, {narrow: true});
has(svg, 'viewBox="0 0 430 280"', "本次对局盈亏走势：3 手，现在 -4BB，最高 +2.5BB，最低 -5BB", '<text class="pnl-end"', ">-4BB</text>");
// the line starts on the zero line and passes through every hand's running total
const line = svg.match(/<path d="M([^"]+)" fill="none"/)[1].split(" L").map((xy) => xy.split(",").map(Number));
assert.strictEqual(line.length, 4);
const ys = line.map(([, y]) => y);
assert(ys[1] < ys[0] && ys[2] > ys[3] && ys[3] > ys[0], `running totals 0, 2.5, -5, -4 → ${ys}`);
// a long session is thinned to the pixels there are, and still ends on its last hand
const long = Array.from({length: 5000}, (_v, i) => ({ts: i, hand_delta_bb: i % 2 ? 1 : -1, delta_chips: 0}));
const thinned = chart(long, 430, 280).match(/<path d="M([^"]+)" fill="none"/)[1].split(" L");
assert(thinned.length < 700 && thinned[thinned.length - 1].startsWith("366.0,"));
assert.strictEqual(chart([], 430, 280), "");
''')


def test_viewer_joins_the_answered_tail_to_the_hands_it_holds():
    _node(r'''
const first = hold({epoch: "", points: []}, {epoch: "a", from: 0, points: [[1, 0.5, 10], [2, null, 5]]});
same(first, {epoch: "a", points: [{ts: 1, hand_delta_bb: 0.5, delta_chips: 10}, {ts: 2, hand_delta_bb: null, delta_chips: 5}]});
const more = hold(first, {epoch: "a", from: 2, points: [[3, -1, 0]]});
same(more.points.map((p) => p.ts), [1, 2, 3]);
same(hold(more, {epoch: "a", from: 3, points: []}).points.map((p) => p.ts), [1, 2, 3]);
// another list replaces what is held; a tail that does not join is refused
same(hold(more, {epoch: "b", from: 0, points: [[9, 1, 1]]}).points.map((p) => p.ts), [9]);
assert.strictEqual(hold(more, {epoch: "b", from: 3, points: []}), null);
assert.strictEqual(hold(more, {epoch: "a", from: 5, points: []}), null);
''')
