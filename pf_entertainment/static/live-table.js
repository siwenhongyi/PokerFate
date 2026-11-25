/* The live table: one renderer for the local console and the VPS viewer.
 *
 *   PFLiveTable.mount(element)   build the skeleton once
 *   PFLiveTable.render(snapshot) draw a snapshot of LiveTableObserver (live_table.py)
 *   PFLiveTable.parts(snapshot, {unit})  the same as plain HTML strings, one per part of the view
 *
 * Amounts arrive in chips and are shown in big blinds; the chip count stays in the tooltip,
 * and the BB / 筹码 switch in the strip shows everything in chips (a phone has no tooltip).
 */
(() => {
  const esc = (text) => String(text ?? "")
    .replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;").replaceAll("'", "&#039;");

  // ── cards: "Ah" from the wire, "A♥" from the hand log ─────────────────────
  const SUITS = { s: ["s", "♠"], h: ["h", "♥"], d: ["d", "♦"], c: ["c", "♣"],
                  "♠": ["s", "♠"], "♥": ["h", "♥"], "♦": ["d", "♦"], "♣": ["c", "♣"] };
  function card(text, size = "", extra = "") {
    const t = String(text || "").replace(/️/g, "").trim();
    const cls = ["card", size, extra].filter(Boolean).join(" ");
    if (!t) return `<span class="${cls} unknown">?</span>`;
    const suit = SUITS[t.slice(-1).toLowerCase()];
    if (!suit) return `<span class="${cls}">${esc(t)}</span>`;
    return `<span class="${cls} ${suit[0]}">${esc(t.slice(0, -1).toUpperCase())}<i>${suit[1]}</i></span>`;
  }
  const cards = (list, size = "") => (list || []).map((c) => card(c, size)).join("");
  const cardBack = (size = "") => `<span class="card ${size} back"></span>`;

  // ── numbers ───────────────────────────────────────────────────────────────
  const trim = (n, digits) => Number(Number(n).toFixed(digits)).toLocaleString("zh-CN", { maximumFractionDigits: digits });
  // 1,967,500 at a 20,000 blind → "98.4"; bets and pots keep two decimals (2.25, 0.5).
  function bbNumber(chips, bb, { signed = false, digits = 1 } = {}) {
    const n = Number((Number(chips || 0) / bb).toFixed(digits));
    return `${signed && n > 0 ? "+" : ""}${trim(n, digits)}`;
  }
  const bbText = (chips, bb, opts) => `${bbNumber(chips, bb, opts)}BB`;
  const bbHtml = (chips, bb, opts) => `${bbNumber(chips, bb, opts)}<small>BB</small>`;
  const chipsFull = (n) => Number(n || 0).toLocaleString("zh-CN");
  const chipsTitle = (n) => `${chipsFull(n)} 筹码`;
  // 114,450,944 → "114.45m", 420,000 → "420k"
  function chipsShort(n, signed = false) {
    const v = Number(n || 0), a = Math.abs(v);
    const body = a >= 1e6 ? `${trim(a / 1e6, 2)}m` : a >= 1e3 ? `${trim(a / 1e3, 1)}k` : trim(a, 0);
    return `${v < 0 ? "-" : signed && v > 0 ? "+" : ""}${body}`;
  }
  const moneyClass = (n) => (n > 0 ? "pos-money" : n < 0 ? "neg-money" : "");
  const pct = (x) => `${Math.round(Number(x) * 100)}%`;

  // The observer writes amounts into its texts as plain chip counts:
  //   an action on a seat   "跟注 70000"                        → the number at the end
  //   a result   "A 赢 27300  |  B 赢 100  本手 -10000"          → each win and our own result
  function actionInBb(text, bb) {
    const t = String(text || "");
    return t.replace(/ (\d+)$/, (_, n) => " " + (bb > 0 ? bbText(n, bb, { digits: 2 }) : chipsFull(n)));
  }
  function resultInBb(text, bb) {
    const t = String(text || "");
    const amount = (n, signed) => (bb > 0 ? bbText(n, bb, { signed, digits: 2 })
      : `${signed && Number(n) > 0 ? "+" : ""}${chipsFull(n)}`);
    return t.replace(/ 赢 (\d+)(?=  \|  |  本手 |$)/g, (_, n) => " 赢 " + amount(n, false))
      .replace(/(^|  )本手 ([+-]?\d+)$/, (_, lead, n) => `${lead}本手 ${amount(n, true)}`);
  }

  // The blind amounts are read at: none when the viewer asked for chips.
  const blindOf = (d) => (d.__chips ? 0 : Number(d.bb || 0));

  // ── the strip above the table ─────────────────────────────────────────────
  function connection(d) {
    if (d.__stale) return ["", "直播数据中断"];
    if (d.connection_status === "reconnecting") return ["wait", "连接中断，正在重连"];
    if (d.connection_status === "restoring") return ["wait", "已连接，正在回到牌桌"];
    if (d.connected) return ["on", d.room_id ? "在牌桌" : "在大厅"];
    return ["", d.__available ? "连接已断开" : "bot 没有在运行"];
  }
  function nowHtml(d) {
    const [cls, text] = connection(d);
    let html = `<span class="conn ${cls}">${text}</span>`;
    if (d.sb && d.bb) html += `<span class="lv-chip" title="小盲 / 大盲"><b>${chipsShort(d.sb)}/${chipsShort(d.bb)}</b></span>`;
    if (d.room_id) {
      const robots = Number(d.robots || 0);
      html += `<span class="lv-chip">真人 <b>${Number(d.humans || 0)}</b></span>` +
        `<span class="lv-chip${robots ? " has-robot" : ""}">人机 <b>${robots}</b></span>`;
    }
    return html;
  }
  function sessionHtml(d) {
    const chips = d.session_pnl_chips;
    if (!Number.isSafeInteger(chips)) return "";
    const bb = blindOf(d);
    // The observer adds up each hand at the blind it was played at; an older bot sends chips only.
    const body = d.__chips ? chipsShort(chips, true)
      : Number.isFinite(d.session_pnl_bb) ? bbHtml(d.session_pnl_bb, 1, { signed: true })
      : bb > 0 ? bbHtml(chips, bb, { signed: true }) : chipsShort(chips, true);
    return `<span class="lbl">本次</span><b class="num ${moneyClass(chips)}" title="${chipsTitle(chips)}">${body}</b>`;
  }
  function moreHtml(d) {
    const rows = [];
    const row = (label, value, title = "") => rows.push(`<div><dt${title ? ` title="${title}"` : ""}>${label}</dt><dd>${value}</dd></div>`);
    if (Number.isSafeInteger(d.total_chips)) row("筹码总量", chipsFull(d.total_chips), "钱包加桌上的筹码；钱包是服务器最近一次回报的余额");
    if (Number.isSafeInteger(d.session_pnl_chips)) {
      const n = d.session_pnl_chips;
      row("本次对局盈亏", `${n > 0 ? "+" : ""}${chipsFull(n)}`, "本次启动以来，按已结算牌局累计");
    }
    if (Number.isSafeInteger(d.session_reward_chips)) {
      row("本次活动奖励", chipsFull(d.session_reward_chips) + (d.session_rewards_uncertain ? "（另有待确认）" : ""),
        "任务、宝箱、漫游和发展基金已领到的筹码");
    }
    if (d.room_id) row("房间", esc(d.room_id));
    if (d.hand_no) row("本次第几手", Number(d.hand_no));
    return rows.join("");
  }

  // ── the table ─────────────────────────────────────────────────────────────
  const POS_TITLE = { "BTN": "庄位", "BTN/SB": "庄位（兼小盲）", "SB": "小盲", "BB": "大盲",
                      "CO": "关煞位（庄位前一位）", "MP": "中位", "UTG": "枪口位" };
  const POS_CLASS = { "BTN": "btn", "BTN/SB": "btn", "SB": "blind", "BB": "blind" };

  function seatHtml(s, index, count, mySeat, bb) {
    // Our own seat is at the bottom; the others follow round the table.
    const rel = ((index - mySeat) % count + count) % count;
    const angle = (90 + rel * (360 / count)) * Math.PI / 180;
    const cx = Math.cos(angle), sy = Math.sin(angle);
    const at = `style="--cx:${cx.toFixed(4)};--sy:${sy.toFixed(4)}"`;
    if (!s || s.empty) return `<div class="seat empty" ${at}>空位</div>`;
    const cls = ["seat"];
    // The bet chip sits on the side facing the middle of the table: under a seat in the upper
    // half, above one in the lower half; a short table puts side seats' chips beside them.
    if (sy > 0.05) cls.push("low");
    if (cx < -0.3) cls.push("left"); else if (cx > 0.3) cls.push("right");
    if (s.is_me) cls.push("me");
    if (s.acting) cls.push("acting");
    if (s.folded && !s.revealed) cls.push("folded");
    // A robot is an account the server's own count has proven, nothing else.
    const robot = s.kind === "robot";
    if (robot) cls.push("robot");
    const size = s.is_me ? "md" : "sm";
    const hole = s.cards && s.cards.length ? cards(s.cards, size) : (s.folded ? "" : cardBack(size) + cardBack(size));
    const tags = [];
    if (robot) tags.push('<span class="tag robot">人机</span>');
    if (s.allin) tags.push('<span class="tag allin">全下</span>');
    if (s.revealed && !s.is_me) tags.push('<span class="tag shown">亮牌</span>');
    const pos = s.pos ? `<span class="pos ${POS_CLASS[s.pos] || ""}" title="${POS_TITLE[s.pos] || ""}">${esc(s.pos)}</span>` : "";
    const stack = bb > 0
      ? `<div class="seat-stack" title="${chipsTitle(s.stack)}">${bbHtml(s.stack, bb)}</div>`
      : `<div class="seat-stack">${chipsFull(s.stack)}</div>`;
    const bet = s.bet > 0
      ? (bb > 0 ? `<div class="bet" title="${chipsTitle(s.bet)}">${bbText(s.bet, bb, { digits: 2 })}</div>`
                : `<div class="bet">${chipsFull(s.bet)}</div>`) : "";
    return `<div class="${cls.join(" ")}" ${at}>` +
      `<div class="seat-top">${pos}<span class="seat-name">${s.is_me ? "我" : esc(s.name || "玩家" + index)}</span></div>` +
      stack + `<div class="seat-cards">${hole}</div>` +
      `<div class="seat-act">${esc(actionInBb(s.last, bb))}</div>` +
      (tags.length ? `<div class="seat-tags">${tags.join("")}</div>` : "") + bet + `</div>`;
  }

  function feltHtml(d) {
    const seats = d.seats || [];
    const count = Math.max(d.seat_num || 6, seats.length || 0) || 6;
    const mySeat = d.my_seat == null ? 0 : d.my_seat;
    const bb = blindOf(d);
    if (!seats.some((s) => s && !s.empty)) {
      const text = d.__stale ? "等待直播数据恢复" : d.connected && !d.room_id ? "在大厅，等待进桌" : "等待对局";
      return `<div class="felt-empty">${text}</div>`;
    }
    const pot = bb > 0 ? bbText(d.pot, bb, { digits: 2 }) : chipsFull(d.pot);
    // The result text names seats by their game name; ours reads better as "我".
    const me = seats.find((s) => s && s.is_me && s.name);
    const result = me ? String(d.result || "").split(me.name).join("我") : d.result;
    const note = resultInBb(result, d.__chips ? 0 : Number(d.result_bb || 0) || bb);
    let html = `<div class="felt-mid"><div class="board">${cards(d.board, "lg")}</div>` +
      `<div class="pot"${bb > 0 ? ` title="${chipsTitle(d.pot)}"` : ""}>底池<b>${pot}</b></div>` +
      (note ? `<div class="felt-note">${esc(note)}</div>` : "") + `</div>`;
    for (let i = 0; i < count; i++) html += seatHtml(seats.find((s) => s && s.seatid === i), i, count, mySeat, bb);
    return html;
  }

  // ── what the bot decided, and on what ─────────────────────────────────────
  const STREET = { preflop: "翻前", flop: "翻牌", turn: "转牌", river: "河牌" };
  const ACTION = { fold: "弃牌", check: "过牌", call: "跟注", raise: "加注", bet: "下注", jam: "全下" };
  const ENGINE = { realtime_cfr: "实时求解", flop_book: "翻牌手册", rule_engine: "规则引擎" };

  // The solver's own line reads "Bet(153)@85% | expl=1.24% | t=0.1s | path=r | risk=large,turn".
  function solverText(text) {
    return text.split("|").map((part) => part.trim()).map((part) => {
      const pick = part.match(/^(\w+)(\([^)]*\))?@(\d+)%$/);
      if (pick) return `求解策略里这一步占 ${pick[3]}%（${pick[1]}${pick[2] || ""}）`;
      if (part.startsWith("expl=")) return `可剥削度 ${part.slice(5)}`;
      if (part.startsWith("path=")) return `行动线 ${part.slice(5)}`;
      if (part.startsWith("risk=")) return `风险标记 ${part.slice(5)}`;
      return part.startsWith("t=") ? "" : part;
    }).filter(Boolean).join("，");
  }

  // One decision, as a head line, an equity bar with the price to beat, and the figures.
  // `d`: {street, action, amount, to_call, pot, equity, equity_random, spr, engine, ms, why};
  // from the hand log also `need` (the price as the log named it) and `facing` (a bet to answer).
  // `who` replaces the street in the head line.
  function decisionHtml(d, bb, { full = true, who = null } = {}) {
    const postflopBet = d.action === "raise" && !(d.to_call > 0) && !d.facing && d.street !== "preflop";
    const label = postflopBet ? ACTION.bet : (ACTION[d.action] || d.action || "");
    const size = d.action === "raise" || d.action === "bet" || d.action === "jam" ? d.amount : d.action === "call" ? d.to_call : 0;
    const amount = size > 0 ? `<span class="num" title="${chipsTitle(size)}">${bb > 0 ? bbHtml(size, bb, { digits: 2 }) : chipsFull(size)}</span>` : "";
    const need = Number.isFinite(d.need) ? d.need : d.to_call > 0 ? d.to_call / (Number(d.pot || 0) + d.to_call) : null;
    const hasEquity = Number.isFinite(d.equity);
    let html = `<div class="why-head"><span class="why-street">${who ?? (STREET[d.street] || esc(d.street || ""))}</span>` +
      `<span class="why-act ${d.action === "fold" ? "fold" : ""}">${label}${amount}</span>` +
      (d.engine ? `<span class="why-engine">${ENGINE[d.engine] || esc(d.engine)}</span>` : "") + `</div>`;
    if (full && hasEquity) {
      html += `<div class="meter" role="img" aria-label="胜率 ${pct(d.equity)}${need == null ? "" : `，跟注需要 ${pct(need)}`}">` +
        `<i style="width:${(Math.min(1, Math.max(0, d.equity)) * 100).toFixed(1)}%"></i>` +
        (need == null ? "" : `<u style="left:${(need * 100).toFixed(1)}%"></u>`) + `</div>`;
    }
    const nums = [];
    if (hasEquity) nums.push(`<span title="${d.mode ? `算法 ${esc(d.mode)}` : ""}">胜率<b>${pct(d.equity)}</b></span>`);
    if (need != null) nums.push(`<span title="要跟的注 ÷（底池 + 要跟的注）">跟注需要<b>${pct(need)}</b></span>`);
    if (full && Number.isFinite(d.equity_random)) nums.push(`<span>对随机牌<b>${pct(d.equity_random)}</b></span>`);
    if (full && Number.isFinite(d.spr)) nums.push(`<span title="剩余筹码 ÷ 底池">SPR<b>${trim(d.spr, 1)}</b></span>`);
    if (full && Number.isFinite(d.ms)) nums.push(`<span>用时<b>${d.ms >= 1000 ? trim(d.ms / 1000, 1) + "s" : Math.round(d.ms) + "ms"}</b></span>`);
    if (nums.length) html += `<div class="why-nums">${nums.join("")}</div>`;
    const raw = String(d.why || "");
    const why = raw.startsWith("realtime_cfr decision |") ? solverText(raw.slice(raw.indexOf("|") + 1))
      : raw.replace(/^【[^】]*】\s*/, "");
    if (full && why) html += `<p class="why-text">${esc(why)}</p>`;
    return html;
  }
  function whyHtml(d) {
    const list = Array.isArray(d.decisions) ? d.decisions : null;
    let body;
    if (!d.room_id) body = '<p class="empty-line">进桌后，这里显示 bot 每一步的依据。</p>';
    else if (list === null) body = '<p class="empty-line">运行中的 bot 版本较旧，重启后显示决策依据。</p>';
    else if (!list.length) body = '<p class="empty-line">这手牌还没轮到我们。</p>';
    else {
      const bb = blindOf(d);
      body = `<ol>` + list.slice().reverse().map((item, i) =>
        `<li class="why-item${i ? "" : " now"}">${decisionHtml(item, bb, { full: i === 0 })}</li>`).join("") + `</ol>`;
    }
    return `<h2>决策依据</h2>${body}`;
  }

  // ── the last hand ─────────────────────────────────────────────────────────
  function bestFive(group) {
    const used = group.hole_used || [];
    return (group.cards || []).map((c, i) => card(c, "", used[i] ? "used" : "")).join("");
  }
  function lastHtml(d) {
    const s = d.settlement;
    if (!s) return "";
    const bb = d.__chips ? 0 : Number(s.bb || 0) || Number(d.bb || 0);
    const hero = s.hero || {};
    const delta = hero.delta;
    const head = Number.isFinite(delta)
      ? `<b class="num ${moneyClass(delta)}" title="${chipsTitle(delta)}">${bb > 0 ? bbHtml(delta, bb, { signed: true, digits: 2 }) : chipsShort(delta, true)}</b>` : "";
    let html = `<h2>上一手${head}</h2>` +
      `<div class="last-board cards">${cards(s.board) || '<span class="muted">没有发公共牌</span>'}</div>`;
    const row = (name, group, won, hole, note) => {
      const five = bestFive(group || {});
      return `<div class="last-row"><div class="last-who"><span class="name">${name}</span>` +
        `<span class="rank">${esc((group || {}).label || "")}</span>${won}</div>` +
        (five ? `<div class="cards">${five}</div>` : "") +
        `<div class="last-hole">底牌 <span class="cards">${hole && hole.some(Boolean) ? cards(hole, "sm") : card("", "sm") + card("", "sm")}</span>${note}</div></div>`;
    };
    let heroWon = false;
    for (const w of s.winners || []) {
      const mine = hero.seatid != null && w.seatid === hero.seatid;
      heroWon = heroWon || mine;
      const won = `<span class="won pos-money" title="${chipsTitle(w.chips)}">+${bb > 0 ? bbText(w.chips, bb, { digits: 2 }) : chipsFull(w.chips)}</span>`;
      html += row(mine ? "我" : esc(w.name || "赢家"), w.group, won, w.hole, "");
    }
    if (!heroWon && hero.hole && hero.hole.some(Boolean)) {
      html += row("我", hero.group, "", hero.hole, hero.folded ? "<span>已弃牌</span>" : "");
    }
    const winners = new Set((s.winners || []).map((w) => w.seatid));
    const shown = (s.revealed || []).filter((p) => !winners.has(p.seatid) && p.seatid !== hero.seatid && (p.hole || []).some(Boolean));
    if (shown.length) {
      html += `<div class="last-shown">` + shown.map((p) =>
        `<span class="shown">${esc(p.name)} <span class="cards">${cards(p.hole, "sm")}</span></span>`).join("") + `</div>`;
    }
    return html;
  }

  function parts(snapshot, { unit = "bb" } = {}) {
    const d = unit === "chips" ? { ...(snapshot || {}), __chips: true } : (snapshot || {});
    return { now: nowHtml(d), session: sessionHtml(d), more: moreHtml(d),
             felt: feltHtml(d), why: whyHtml(d), last: lastHtml(d) };
  }

  // ── DOM ───────────────────────────────────────────────────────────────────
  let nodes = null;
  let unit = "bb";
  let latest = null;
  const drawn = {};
  function mount(root) {
    try { unit = localStorage.getItem("pf-unit") === "chips" ? "chips" : "bb"; } catch (_) { /* private mode */ }
    root.innerHTML = '<div class="lv">' +
      '<div class="lv-bar"><div class="lv-now"></div><div class="lv-session"></div>' +
      '<button class="lv-toggle" type="button" aria-expanded="false" aria-label="筹码、奖励和房间" title="筹码、奖励和房间"></button>' +
      '<dl class="lv-more"></dl>' +
      '<div class="lv-unit" role="group" aria-label="金额单位">' +
      '<button type="button" data-unit="bb">BB</button><button type="button" data-unit="chips">筹码</button></div></div>' +
      '<div class="lv-stage"><div class="felt"></div><div class="lv-side">' +
      '<section class="panel why" aria-live="polite"></section><section class="panel last" hidden></section>' +
      '</div></div></div>';
    const lv = root.firstChild;
    const pick = (sel) => lv.querySelector(sel);
    nodes = { now: pick(".lv-now"), session: pick(".lv-session"), more: pick(".lv-more"),
              felt: pick(".felt"), why: pick(".why"), last: pick(".last") };
    const toggle = pick(".lv-toggle");
    toggle.addEventListener("click", () => {
      toggle.setAttribute("aria-expanded", String(lv.classList.toggle("open")));
    });
    const units = [...lv.querySelectorAll(".lv-unit button")];
    const markUnit = () => units.forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.unit === unit)));
    units.forEach((b) => b.addEventListener("click", () => {
      unit = b.dataset.unit;
      try { localStorage.setItem("pf-unit", unit); } catch (_) { /* private mode */ }
      markUnit();
      render(latest);
    }));
    markUnit();
    for (const key of Object.keys(drawn)) delete drawn[key];
  }
  function render(snapshot) {
    if (!nodes) return;
    latest = snapshot;
    const next = parts(snapshot, { unit });
    for (const key of Object.keys(next)) {
      if (drawn[key] === next[key]) continue;      // untouched parts keep their DOM (and animation)
      drawn[key] = next[key];
      nodes[key].innerHTML = next[key];
    }
    nodes.last.hidden = !next.last;
  }

  window.PFLiveTable = { mount, render, parts, card, cards, decisionHtml, esc,
                         fmt: { bbNumber, bbText, bbHtml, chipsFull, chipsShort, chipsTitle, moneyClass, pct, trim } };
})();
