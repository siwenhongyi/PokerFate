"""Run the shared renderer with a tiny DOM and controlled clock, no browser/network."""
import shutil
import subprocess
from pathlib import Path

import pytest


def test_reveal_timer_retained_result_and_live_table_do_not_cross_hands():
    if not shutil.which("node"):
        pytest.skip("node not installed")
    script = r'''
const fs = require("fs"), vm = require("vm"), assert = require("assert");
let now = 0;
const timers = [], ids = {};
function element() {
  return {style:{}, dataset:{}, innerHTML:"", textContent:"", hidden:false,
          clientWidth:390, clientHeight:500, children:[], classList:{toggle(){}},
          querySelectorAll(selector) { return selector.includes('data-keep="0"') ? this.children.filter(c=>c.dataset.keep==="0") : this.children; },
          querySelector(selector) { const m=selector.match(/data-seat="(\d+)"/);return this.children.find(c=>c.dataset.seat===m?.[1]) || null; },
          appendChild(child) { child.remove=()=>{this.children=this.children.filter(x=>x!==child)};this.children.push(child); }};
}
for (const id of ["live-conn","live-room","live-blinds","live-street","live-pot","live-hand","live-board","live-potc","live-result","live-felt","live-empty","live-feed","live-settlement"]) ids[id]=element();
const window = {};
vm.runInNewContext(fs.readFileSync("pf_entertainment/static/live-table.js","utf8"),
 {window,document:{getElementById:id=>ids[id],createElement:()=>element()},performance:{now:()=>now},setInterval:f=>timers.push(f)});
const render=window.PFLiveTable.render;
ids["live-pnl"]=element(); ids["live-rewards"]=element();
render({session_pnl_chips:-1250,session_reward_chips:2000,session_rewards_uncertain:true});
assert.strictEqual(ids["live-pnl"].textContent,"-1,250 筹码");
assert.strictEqual(ids["live-rewards"].textContent,"2,000 筹码（另有待确认）");
render({session_pnl_chips:100,session_reward_chips:0});
assert.strictEqual(ids["live-pnl"].textContent,"+100 筹码");
assert.strictEqual(ids["live-rewards"].textContent,"0 筹码");
render({});
assert.strictEqual(ids["live-pnl"].textContent,"—");
assert.strictEqual(ids["live-rewards"].textContent,"—");
const group={label:"葫芦",cards:["As","Ad","Ah","Ks","Kd"],hole_used:[true,true,false,false,false]};
const result={id:"one",hand_no:1,board:["Ah","Ks","Kd","2c","3c"],reveal_seconds:2.5,
 winners:[{name:"<script>bad</script>",chips:150,hole:["As","Ad"],group}],
 hero:{hole:["Qh","Qd"],folded:true,group:{label:"两对",cards:["Ks","Kd","Qh","Qd","Ah"]}},
 revealed:[{name:"<script>bad</script>",hole:["As","Ad"]}]};
let data={connected:true,__available:true,room_id:42,hand_no:1,seats:[{seatid:0,name:"hero",cards:["Qh","Qd"],folded:true}],board:result.board,feed:[],settlement:result};
render(data);
assert(ids["live-settlement"].innerHTML.includes("公开亮牌"));
assert(!ids["live-settlement"].innerHTML.includes("<script>bad</script>"));
now=2499;render(data);
assert(ids["live-settlement"].innerHTML.includes("公开亮牌"));
now=2501;timers.forEach(f=>f());
assert(ids["live-settlement"].innerHTML.includes("最佳五张牌"));
assert(ids["live-settlement"].innerHTML.includes("from-hole"));
assert(ids["live-settlement"].innerHTML.includes("已弃牌"));
// Same settlement arriving with the next hand must not reset its timer.
data={...data,hand_no:2,board:[],seats:[{seatid:0,name:"hero",cards:["7s","8d"],folded:false}]};
render(data);
assert(ids["live-hand"].textContent===2);
assert(ids["live-board"].innerHTML==="");
assert(ids["live-felt"].children[0].innerHTML.includes("7♠"));
assert(!ids["live-felt"].children[0].innerHTML.includes("Q♥"));
assert(ids["live-settlement"].innerHTML.includes("第 1 手结算"));
assert(!ids["live-settlement"].innerHTML.includes("公开亮牌"));
now=50000;render(data);
assert(!ids["live-settlement"].hidden);
// New settlement restarts the reveal, an expired remote feed clears everything.
render({...data,settlement:{...result,id:"two",hand_no:2}});
assert(ids["live-settlement"].innerHTML.includes("公开亮牌"));
render({__available:true,seats:[],board:[],feed:[]});
assert(ids["live-settlement"].hidden && ids["live-settlement"].innerHTML==="");
console.log("shared renderer reveal/retention/live/expiry checks passed");
'''
    result = subprocess.run(["node", "-e", script], cwd=Path(__file__).resolve().parents[1],
                            capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr


def test_seat_shows_position_and_marks_robots():
    if not shutil.which("node"):
        pytest.skip("node not installed")
    script = r'''
const fs = require("fs"), vm = require("vm"), assert = require("assert");
const ids = {};
function element() {
  return {style:{}, dataset:{}, innerHTML:"", textContent:"", hidden:false, className:"",
          clientWidth:700, clientHeight:500, children:[], classList:{toggle(){}},
          querySelectorAll(selector) { return selector.includes('data-keep="0"') ? this.children.filter(c=>c.dataset.keep==="0") : this.children; },
          querySelector(selector) { const m=selector.match(/data-seat="(\d+)"/);return this.children.find(c=>c.dataset.seat===m?.[1]) || null; },
          appendChild(child) { child.remove=()=>{this.children=this.children.filter(x=>x!==child)};this.children.push(child); }};
}
for (const id of ["live-conn","live-room","live-blinds","live-street","live-pot","live-hand","live-mix","live-board","live-potc","live-result","live-felt","live-empty","live-feed","live-settlement"]) ids[id]=element();
const window = {};
vm.runInNewContext(fs.readFileSync("pf_entertainment/static/live-table.js","utf8"),
 {window,document:{getElementById:id=>ids[id],createElement:()=>element()},performance:{now:()=>0},setInterval:()=>0});
const seat = (i, extra) => ({seatid:i, name:"p"+i, stack:1000, cards:[], ...extra});
window.PFLiveTable.render({connected:true,__available:true,room_id:7,hand_no:3,humans:2,robots:2,board:[],feed:[],seat_num:6,my_seat:0,
  seats:[seat(0,{is_me:true,pos:"BB"}), seat(1,{pos:"BTN",kind:"robot"}), seat(2,{pos:"SB",kind:"suspect"}),
         seat(3,{pos:"CO",kind:"human"}), seat(4,{pos:"",kind:""}), {seatid:5,empty:true}]});
const node = i => ids["live-felt"].children.find(c => c.dataset.seat === String(i));
assert.strictEqual(ids["live-mix"].textContent, "真人 2 · 人机 2");
assert(node(1).className.split(" ").includes("robot") && node(1).innerHTML.includes('pill robot">人机<'));
assert(node(1).innerHTML.includes('class="s-pos btn"') && node(1).innerHTML.includes(">BTN<"));
assert(node(2).className.split(" ").includes("robot") && node(2).innerHTML.includes("疑似人机"));
assert(node(2).innerHTML.includes('class="s-pos sb"'));
assert(!node(3).className.split(" ").includes("robot") && !node(3).innerHTML.includes("人机"));
assert(node(3).innerHTML.includes(">CO<"));
assert(!node(4).innerHTML.includes("s-pos") && !node(4).className.split(" ").includes("robot"));
assert(node(0).innerHTML.includes('class="s-pos bb"') && node(0).innerHTML.includes("·我"));
assert(node(5).className.includes("empty"));
// in the lobby there is no table to count
window.PFLiveTable.render({connected:true,__available:true,seats:[],board:[],feed:[]});
assert.strictEqual(ids["live-mix"].textContent, "-");
// a snapshot from an older publisher (no pos / kind) still renders
window.PFLiveTable.render({connected:true,__available:true,room_id:7,seats:[seat(1,{})],board:[],feed:[]});
assert(node(1).innerHTML.includes("p1") && !node(1).innerHTML.includes("s-pos"));
console.log("position / robot marks ok");
'''
    result = subprocess.run(["node", "-e", script], cwd=Path(__file__).resolve().parents[1],
                            capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
