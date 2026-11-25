"""The shared live-table renderer as plain strings: no browser, no DOM, no network."""
import shutil
import subprocess
from pathlib import Path

import pytest

_PRELUDE = r'''
const fs = require("fs"), vm = require("vm"), assert = require("assert");
const window = {};
vm.runInNewContext(fs.readFileSync("pf_entertainment/static/live-table.js", "utf8"), {window});
const parts = window.PFLiveTable.parts;
const seat = (i, extra) => ({seatid: i, name: "p" + i, stack: 1000, cards: [], ...extra});
const has = (html, ...needles) => needles.forEach((n) => assert(html.includes(n), `missing ${n}\n in ${html}`));
const lacks = (html, ...needles) => needles.forEach((n) => assert(!html.includes(n), `unexpected ${n}`));
'''


def _node(script: str) -> None:
    if not shutil.which("node"):
        pytest.skip("node not installed")
    result = subprocess.run(["node", "-e", _PRELUDE + script], cwd=Path(__file__).resolve().parents[1],
                            capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr


def test_table_shows_seats_positions_robots_and_amounts_in_big_blinds():
    _node(r'''
const table = {connected: true, room_id: 7, sb: 10000, bb: 20000, pot: 187000, board: ["Ah", "Td"], seat_num: 6, my_seat: 0,
  result: "p1 赢 27000  |  hero 赢 400  本手 -10000",
  seats: [seat(0, {name: "hero", is_me: true, pos: "BB", stack: 1967500, bet: 45000, last: "加注 45000", cards: ["Qs", "Qc"]}),
          seat(1, {pos: "BTN", kind: "robot", stack: 2000000, bet: 10000, last: "小盲 10000", acting: true}),
          seat(2, {pos: "SB", kind: "", folded: true, last: "弃牌"}), seat(3, {pos: "CO", kind: "human", allin: true}),
          seat(4, {name: "<b>x</b>", revealed: true, cards: ["7s", "8d"]}), {seatid: 5, empty: true}]};
const felt = parts(table).felt;
const at = (i) => felt.split(/<div class="seat(?=[ "])/).slice(1).find((s) => s.includes(i === 0 ? ">我<" : ">p" + i + "<"));
// our own seat: called 我, stack and bet in big blinds with the chips in the tooltip, our cards face up
has(at(0), " low me", 'title="1,967,500 筹码">98.4<small>BB</small>', '<div class="bet" title="45,000 筹码">2.25BB</div>',
    "加注 2.25BB", 'class="card md s">Q<i>♠</i>', 'class="pos blind"');
// a proven robot is marked; the seat asked to act is marked; position tags
has(at(1), " acting", " robot", '<span class="tag robot">人机</span>', 'class="pos btn"', ">BTN<", "小盲 0.5BB", "100<small>BB</small>", "card sm back");
has(at(2), " folded", "弃牌"); lacks(at(2), "人机", "card sm back", 'class="bet"');
has(at(3), '<span class="tag allin">全下</span>'); lacks(at(3), "人机");
// a shown hand is face up; names are escaped; an empty seat says so
has(felt, 'class="card sm s">7<i>♠</i>', '<span class="tag shown">亮牌</span>', "&lt;b&gt;x&lt;/b&gt;", '<div class="seat empty"');
// the middle: board, pot and the result, all in big blinds, our own name read as 我
has(felt, 'class="card lg h">A<i>♥</i>', 'class="card lg d">T<i>♦</i>', '底池<b>9.35BB</b>', "p1 赢 1.35BB  |  我 赢 0.02BB  本手 -0.5BB");
// a result from a table at another stake is read at the blind it was played at
has(parts({...table, result_bb: 5000}).felt, "p1 赢 5.4BB  |  我 赢 0.08BB  本手 -2BB");
// no blind known, or the viewer asked for chips: everything in chips
for (const chips of [parts({...table, bb: 0}).felt, parts(table, {unit: "chips"}).felt]) {
  has(chips, '<div class="seat-stack">1,967,500</div>', '<div class="bet">45,000</div>', "加注 45,000", "底池<b>187,000</b>",
      "p1 赢 27,000  |  我 赢 400  本手 -10,000");
}
has(parts({...table, session_pnl_chips: -550000, session_pnl_bb: -27.5}, {unit: "chips"}).session, ">-550k<");
// nobody seated
has(parts({connected: true, seats: [], board: []}).felt, "在大厅，等待进桌");
has(parts({__stale: true, seats: [], board: []}).felt, "等待直播数据恢复");
''')


def test_strip_tells_connection_stake_company_and_the_session_result():
    _node(r'''
let p = parts({connected: true, __available: true, room_id: 7, sb: 10000, bb: 20000, humans: 3, robots: 1,
               total_chips: 113165900, session_pnl_chips: -550000, session_pnl_bb: -20, session_reward_chips: 2000,
               session_rewards_uncertain: true, hand_no: 12});
has(p.now, '<span class="conn on">在牌桌</span>', "<b>10k/20k</b>", "真人 <b>3</b>", 'has-robot">人机 <b>1</b>');
has(p.session, 'class="num neg-money" title="-550,000 筹码">-20<small>BB</small>');
has(p.more, "113,165,900", "-550,000", "2,000（另有待确认）", "<dd>7</dd>", "<dd>12</dd>");
// an older bot sends chips only: read at this table's blind; with no blind at all, chips
has(parts({bb: 20000, session_pnl_chips: 2346808}).session, "pos-money", "+117.3<small>BB</small>");
has(parts({session_pnl_chips: -1250}).session, ">-1.3k<");
assert.strictEqual(parts({}).session, "");
// where the bot is
has(parts({connected: true}).now, "在大厅");
has(parts({connection_status: "reconnecting"}).now, 'class="conn wait">连接中断，正在重连');
has(parts({__available: true}).now, "连接已断开");
has(parts({}).now, "bot 没有在运行");
has(parts({__stale: true}).now, "直播数据中断");
''')


def test_decisions_newest_first_with_equity_against_the_price():
    _node(r'''
const base = {connected: true, room_id: 7, bb: 20000};
const p = parts({...base, decisions: [
  {street: "preflop", action: "raise", amount: 180000, to_call: 20000, pot: 120000, equity: 0.26, engine: "rule_engine", ms: 20,
   why: "【GTOv2·翻前】 AQo BB 4人limp→iso"},
  {street: "flop", action: "raise", amount: 242915, to_call: 0, pot: 440000, equity: 0.49, equity_random: 0.6, spr: 3.5,
   engine: "realtime_cfr", ms: 1490, why: "realtime_cfr decision | Bet(153)@85% | expl=1.24% | t=0.1s | path=r | risk=large,turn"},
  {street: "river", action: "fold", amount: 0, to_call: 1380000, pot: 2909737, equity: 0.09, engine: "flop_book", ms: 55, why: "<i>x</i>"}]}).why;
const items = p.split('<li class="why-item').slice(1);
assert.strictEqual(items.length, 3);
// the latest decision leads, with the bar: equity filled, the price to beat marked
has(items[0], " now", "河牌", 'class="why-act fold">弃牌', "翻牌手册", 'style="width:9.0%"', '<u style="left:32.2%">', "胜率<b>9%</b>", "跟注需要<b>32%</b>", "&lt;i&gt;x&lt;/i&gt;");
// a bet into an unopened pot after the flop is a bet; the solver's line is put in words
has(items[1], "翻牌", ">下注<span", "12.15<small>BB</small>", "实时求解", "胜率<b>49%</b>"); lacks(items[1], "meter", "求解策略");
has(items[2], "翻前", ">加注<span", "9<small>BB</small>", "规则引擎", "跟注需要<b>14%</b>");
has(window.PFLiveTable.decisionHtml({street: "turn", action: "raise", amount: 306000, pot: 925828, equity: 0.36, ms: 1490,
  why: "realtime_cfr decision | Bet(153)@85% | expl=1.24% | t=0.1s | path=r | risk=large,turn"}, 20000),
  "求解策略里这一步占 85%（Bet(153)）", "可剥削度 1.24%", "行动线 r", "风险标记 large,turn", "用时<b>1.5s</b>");
// before there is anything to show
has(parts({...base, decisions: []}).why, "这手牌还没轮到我们");
has(parts(base).why, "重启后显示决策依据");
has(parts({connected: true}).why, "进桌后");
''')


def test_last_hand_names_winners_their_best_five_and_our_own_result():
    _node(r'''
const group = {label: "葫芦", cards: ["As", "Ad", "Ah", "Ks", "Kd"], hole_used: [true, true, false, false, false]};
const settlement = {id: "one", hand_no: 1, board: ["Ah", "Ks", "Kd", "2c", "3c"],
  winners: [{seatid: 2, name: "<script>bad</script>", chips: 150, hole: ["As", "Ad"], group}],
  hero: {seatid: 0, hole: ["Qh", "Qd"], folded: true, delta: -100, group: {label: "两对", cards: ["Ks", "Kd", "Qh", "Qd", "Ah"]}},
  revealed: [{seatid: 2, name: "<script>bad</script>", hole: ["As", "Ad"]}, {seatid: 4, name: "p4", hole: ["7s", "8d"]}]};
// chips while no blind is known, big blinds at the blind of that hand
let last = parts({settlement}).last;
has(last, "上一手", 'class="num neg-money" title="-100 筹码">-100</b>', "+150</span>", "葫芦", "两对", "已弃牌",
    'class="card used s">A<i>♠</i>', "&lt;script&gt;bad&lt;/script&gt;", 'class="shown">p4');
lacks(last, "<script>bad</script>");
last = parts({bb: 999, settlement: {...settlement, bb: 50}}).last;
has(last, "-2<small>BB</small>", "+3BB</span>");
// we won it: one row, named 我
last = parts({settlement: {...settlement, winners: [{...settlement.winners[0], seatid: 0}], hero: {...settlement.hero, delta: 150, folded: false}}}).last;
has(last, '<span class="name">我</span>', "pos-money"); lacks(last, "已弃牌");
assert.strictEqual(parts({}).last, "");
''')
