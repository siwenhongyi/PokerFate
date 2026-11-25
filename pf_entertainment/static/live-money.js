/* The money view: one renderer for the local console and the VPS viewer.
 *
 *   PFMoney.mount(element)           build the skeleton once
 *   PFMoney.render(dashboard)        draw BotBridge.bankroll_dashboard(): the result, its chart, the account
 *   PFMoney.notice(text, {keep})     say why nothing new is shown; `keep` leaves the last figures in place
 *   PFMoney.parts(dashboard, {now})  the figures as plain HTML strings
 *   PFMoney.chart(points, width, height, {narrow})   the chart as an SVG string
 *   PFMoney.hold(held, part)         the viewer's hands so far joined with the tail the VPS answered
 *
 * Needs live-table.js for the number formats.
 */
(() => {
  const { esc } = window.PFLiveTable;
  const { bbText, bbHtml, chipsFull, chipsShort, chipsTitle, moneyClass } = window.PFLiveTable.fmt;
  const clock = (seconds) => seconds
    ? new Date(Number(seconds) * 1000).toLocaleTimeString("zh-CN", { hour12: false }) : "-";
  const bbSigned = (v, digits = 1) => bbText(v, 1, { signed: true, digits });

  // ── the session result as one line ──────────────────────────────────────────
  // The running poker result in big blinds, hand by hand, starting on the zero line.  Green
  // above zero, red below, a light wash to zero.  No dot per hand and no buy-in markers:
  // top-ups, profit locks and table changes do not move this line, it is the sum of settled
  // hands.  Hovering (or the arrow keys) reads one hand.
  const COLOR = { up: "#74dfa3", down: "#ff8d7a", grid: "rgba(243,236,217,.08)", zero: "rgba(243,236,217,.32)" };
  const PAD = { top: 22, right: 64, bottom: 30, left: 44 };

  function niceStep(span, target, units) {
    const raw = Math.max(span, 1e-9) / target;
    const pow = Math.pow(10, Math.floor(Math.log10(raw)));
    return (units.find((m) => m * pow >= raw) || 10) * pow;
  }
  // Every hand at the blind it was played at (table selection can change stakes mid-session).
  function series(points) {
    let sum = 0;
    return points.map((p) => {
      if (Number.isFinite(p.hand_delta_bb)) sum += p.hand_delta_bb;
      else if (Number.isFinite(p.delta_bb)) sum = p.delta_bb;
      return { bb: sum, chips: Number(p.delta_chips || 0), handBb: p.hand_delta_bb, ts: p.ts };
    });
  }
  // A long session has more hands than pixels: keep each pixel column's low and high, in order.
  function thin(values, columns) {
    if (values.length <= columns * 2) return values.map((_v, i) => i);
    const keep = [0];
    const per = values.length / columns;
    for (let c = 0; c < columns; c++) {
      const from = Math.floor(c * per), to = Math.min(values.length, Math.floor((c + 1) * per));
      let lo = from, hi = from;
      for (let i = from; i < to; i++) {
        if (values[i] < values[lo]) lo = i;
        if (values[i] > values[hi]) hi = i;
      }
      for (const i of lo < hi ? [lo, hi] : lo > hi ? [hi, lo] : [lo]) if (i > keep[keep.length - 1]) keep.push(i);
    }
    if (keep[keep.length - 1] !== values.length - 1) keep.push(values.length - 1);
    return keep;
  }

  // `data` is series(points) with at least one hand.
  function plot(data, width, height, narrow) {
    const n = data.length;
    const values = [0, ...data.map((d) => d.bb)];       // position 0 is the start of the session
    const low = Math.min(...values), high = Math.max(...values);
    const step = niceStep(high - low || 1, 4, [1, 2, 2.5, 5, 10]);
    const y0 = Math.floor(low / step) * step, y1 = Math.max(Math.ceil(high / step) * step, y0 + step);
    const left = PAD.left, right = width - PAD.right, top = PAD.top, bottom = height - PAD.bottom;
    const x = (i) => left + (i / n) * (right - left);
    const y = (v) => bottom - ((v - y0) / (y1 - y0)) * (bottom - top);
    const zeroY = y(0);
    const f = (v) => v.toFixed(1);

    let grid = "";
    for (let k = 0; y0 + k * step <= y1 + step / 1000; k++) {
      const v = Number((y0 + k * step).toFixed(6)), gy = f(y(v));
      grid += `<line x1="${left}" x2="${right}" y1="${gy}" y2="${gy}" stroke="${v === 0 ? COLOR.zero : COLOR.grid}"/>` +
        `<text x="${left - 8}" y="${gy}" dy="0.35em" text-anchor="end">${v > 0 ? "+" : ""}${v.toLocaleString("zh-CN")}</text>`;
    }
    const handStep = Math.max(1, niceStep(n, narrow ? 4 : 7, [1, 2, 5, 10]));
    let ticks = "";
    for (let t = handStep; t <= n; t += handStep) {
      ticks += `<text x="${f(x(t))}" y="${bottom + 19}" text-anchor="middle">${t.toLocaleString("zh-CN")}</text>`;
    }
    const path = thin(values, Math.max(1, Math.floor(right - left))).map((i) => `${f(x(i))},${f(y(values[i]))}`).join(" L");
    const split = ((zeroY - top) / (bottom - top)).toFixed(4);
    const last = values[n];
    const endY = y(last);
    const svg = `<svg viewBox="0 0 ${width} ${height}" role="img" tabindex="0"
        aria-label="本次对局盈亏走势：${n} 手，现在 ${bbSigned(last)}，最高 ${bbSigned(high)}，最低 ${bbSigned(low)}">
      <defs><linearGradient id="pnl-sign" gradientUnits="userSpaceOnUse" x1="0" y1="${top}" x2="0" y2="${bottom}">
        <stop offset="0" stop-color="${COLOR.up}"/><stop offset="${split}" stop-color="${COLOR.up}"/>
        <stop offset="${split}" stop-color="${COLOR.down}"/><stop offset="1" stop-color="${COLOR.down}"/>
      </linearGradient></defs>
      <g class="pnl-axis">${grid}${ticks}
        <text x="${left - 8}" y="${top - 10}" text-anchor="end">BB</text>
        <text x="${right}" y="${bottom + 19}" text-anchor="start" dx="10">手</text></g>
      <path d="M${f(x(0))},${f(zeroY)} L${path} L${f(x(n))},${f(zeroY)} Z" fill="url(#pnl-sign)" opacity="0.14"/>
      <path d="M${path}" fill="none" stroke="url(#pnl-sign)" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>
      <circle cx="${f(x(n))}" cy="${f(endY)}" r="4" fill="${last < 0 ? COLOR.down : COLOR.up}" stroke="#0f211b" stroke-width="2"/>
      <text class="pnl-end" x="${f(x(n) + 9)}" y="${f(Math.min(bottom, Math.max(top + 4, endY)))}" dy="0.35em">${bbSigned(last)}</text>
      <g id="pnl-cursor" visibility="hidden">
        <line y1="${top}" y2="${bottom}" stroke="rgba(243,236,217,.45)"/>
        <circle r="4.5" stroke="#0f211b" stroke-width="2"/></g>
    </svg>`;
    return { svg, x, y, left, right };
  }
  function chart(points, width, height, { narrow = false } = {}) {
    const data = series(points || []);
    return data.length ? plot(data, width, height, narrow).svg : "";
  }

  // ── the figures ─────────────────────────────────────────────────────────────
  function duration(seconds) {
    const m = Math.max(0, Math.round(seconds / 60));
    return m >= 60 ? `${Math.floor(m / 60)} 小时 ${m % 60} 分` : `${m} 分钟`;
  }
  function parts(dashboard, { now = Date.now() / 1000 } = {}) {
    const d = dashboard || {};
    const chips = Number(d.session_delta_chips || 0);
    const hands = Array.isArray(d.hand_points) ? d.hand_points : [];
    const lead = Number.isFinite(d.session_delta_bb) ? bbHtml(d.session_delta_bb, 1, { signed: true }) : chipsShort(chips, true);
    const sub = `<b>${chips > 0 ? "+" : ""}${chipsFull(chips)}</b> 筹码<br>` +
      `已打 <b>${hands.length}</b> 手` + (d.base_at ? `，运行了 ${duration(now - d.base_at)}` : "") +
      (d.big_blind ? `，盲注 <b>${chipsShort(d.big_blind)}</b>` : "");

    const fact = (label, value, { title = "", cls = "", wide = false } = {}) =>
      `<div${wide ? ' class="wide"' : ""}><dt${title ? ` title="${title}"` : ""}>${label}</dt><dd class="${cls}">${value}</dd></div>`;
    const amount = (n, signed = false) => `<span title="${chipsTitle(n)}">${chipsShort(n, signed)}</span>`;
    const times = (n) => `${Number(n || 0)}<small>次</small>`;
    const cap = Number(d.loss_cap_chips || 0);
    const used = cap > 0 ? Math.min(1, Math.max(0, -chips / cap)) : 0;
    const side = Number(d.sidegame_net_chips || 0);
    const facts = [
      fact("当前总筹码", amount(d.current_total_chips), { title: "钱包加桌上的筹码" }),
      fact("钱包", amount(d.wallet_chips)),
      fact("桌上", amount(d.table_chips)),
      fact("活动奖励", amount(d.reward_chips || 0) + (d.rewards_uncertain ? "<small>另有待确认</small>" : ""),
        { title: "任务、宝箱、漫游和发展基金领到的筹码" }),
      fact("活动任务输赢", amount(side, true),
        { title: "为做活动任务打的彩球机、弹球，以及奥马哈和 AOF 的任务手数，本次启动的净输赢", cls: moneyClass(side) }),
      fact("盈利锁仓", times(d.profit_lock_count)),
      fact("破产买入", times(d.auto_rebuy_count)),
      fact("桌上补码", times(d.topup_count) + (d.topup_chips ? `<small>共 ${chipsShort(d.topup_chips)}</small>` : "")),
      fact("净亏损上限", cap > 0
        ? `-${chipsShort(cap)}<small>${d.loss_stop ? "已到上限，停止买入" : `已用 ${Math.round(used * 100)}%`}</small>` +
          `<div class="cap-bar"><i style="width:${(used * 100).toFixed(1)}%"></i></div>` : "-",
        { title: "本次启动的净亏损不会超过这个数：补码、破产买入和换桌买入都受它限制", wide: true }),
    ].join("");
    return { leadClass: moneyClass(chips), lead, sub, facts };
  }

  // ── the VPS's hands ─────────────────────────────────────────────────────────
  // The VPS answers the figures and the hands after position `from` of list `epoch`, each hand
  // as [ts, hand_delta_bb, delta_chips] (remote_live/money.py).  `held` is {epoch, points} from
  // the answers so far; null when the answer does not continue it (the caller asks from 0).
  function hold(held, part) {
    const have = held && held.epoch === part.epoch ? held.points : [];
    if (part.from > have.length) return null;
    const tail = part.points.map(([ts, hand_delta_bb, delta_chips]) => ({ ts, hand_delta_bb, delta_chips }));
    return { epoch: part.epoch, points: have.slice(0, part.from).concat(tail) };
  }

  // ── DOM ─────────────────────────────────────────────────────────────────────
  let nodes = null;
  let points = [];
  let layout = null;     // what is drawn now: { key, data, x(i), y(v) }
  let hover = 0;         // 1-based hand in the chart under the pointer, 0 = none
  let note = "";         // shown instead of the figures

  function draw() {
    if (!nodes || note) return;
    const box = nodes.chart;
    const width = Math.floor(box.clientWidth), height = Math.floor(box.clientHeight);
    if (!width || !height) return;            // view not shown: the resize observer draws it when it is
    const data = series(points);
    const n = data.length;
    const key = `${width}x${height}|${n}|${n ? data[n - 1].bb : ""}`;
    if (layout && layout.key === key) return;
    if (!n) {
      layout = { key, data };
      hover = 0;
      box.innerHTML = '<div class="pnl-empty">打完第一手后，这里画出本次的输赢走势。</div>';
      return;
    }
    const drawn = plot(data, width, height, window.matchMedia("(max-width: 860px)").matches);
    box.innerHTML = drawn.svg + '<div class="pnl-tip" hidden><div class="pnl-tip-when"></div>' +
      '<div class="pnl-tip-total"><b></b><span></span></div><div class="pnl-tip-hand"></div></div>';
    layout = { key, data, x: drawn.x, y: drawn.y, left: drawn.left, right: drawn.right, width };
    showHover(Math.min(hover, n));
  }

  function showHover(hand) {
    const box = nodes.chart;
    const cursor = box.querySelector("#pnl-cursor"), tip = box.querySelector(".pnl-tip");
    hover = hand;
    if (!cursor || !tip || !layout) return;
    if (!hand) { cursor.setAttribute("visibility", "hidden"); tip.hidden = true; return; }
    const d = layout.data[hand - 1];
    const px = layout.x(hand), py = layout.y(d.bb);
    cursor.setAttribute("visibility", "visible");
    const line = cursor.querySelector("line"), dot = cursor.querySelector("circle");
    line.setAttribute("x1", px); line.setAttribute("x2", px);
    dot.setAttribute("cx", px); dot.setAttribute("cy", py);
    dot.setAttribute("fill", d.bb < 0 ? COLOR.down : COLOR.up);
    tip.querySelector(".pnl-tip-when").textContent = `本次第 ${hand} 手，${clock(d.ts)}`;
    tip.querySelector(".pnl-tip-total b").textContent = bbSigned(d.bb);
    tip.querySelector(".pnl-tip-total span").textContent = `累计 ${chipsShort(d.chips, true)} 筹码`;
    tip.querySelector(".pnl-tip-hand").textContent = Number.isFinite(d.handBb) ? `这一手 ${bbSigned(d.handBb, 2)}` : "";
    tip.hidden = false;
    const tw = tip.offsetWidth, th = tip.offsetHeight;
    tip.style.left = `${Math.max(0, px + 14 + tw > layout.width ? px - 14 - tw : px + 14)}px`;
    tip.style.top = `${Math.max(4, py - th - 10)}px`;
  }
  function handAt(clientX) {
    if (!layout || !layout.data.length) return 0;
    const n = layout.data.length;
    const px = clientX - nodes.chart.getBoundingClientRect().left;
    return Math.min(n, Math.max(1, Math.round(((px - layout.left) / (layout.right - layout.left)) * n)));
  }

  function mount(root) {
    root.innerHTML = '<div class="money-lead"><div>' +
      '<h2 title="本次启动以来服务器每手结算的累计；活动奖励，以及为做活动任务打的小游戏和任务手数不算在内">本次对局盈亏</h2>' +
      '<div class="lead-num num">—</div></div>' +
      '<div class="lead-sub" aria-busy="true">正在读取</div></div>' +
      '<div class="pnl-chart"></div><dl class="facts"></dl>';
    const pick = (sel) => root.querySelector(sel);
    nodes = { lead: pick(".lead-num"), sub: pick(".lead-sub"), chart: pick(".pnl-chart"), facts: pick(".facts") };
    points = []; layout = null; hover = 0; note = "";
    const box = nodes.chart;
    box.addEventListener("pointermove", (e) => showHover(handAt(e.clientX)));
    box.addEventListener("pointerdown", (e) => showHover(handAt(e.clientX)));
    box.addEventListener("pointerleave", () => showHover(0));
    box.addEventListener("focusout", () => showHover(0));
    box.addEventListener("keydown", (e) => {
      const n = layout && layout.data ? layout.data.length : 0;
      if (!n || !["ArrowLeft", "ArrowRight", "Escape"].includes(e.key)) return;
      e.preventDefault();
      if (e.key === "Escape") return showHover(0);
      showHover(Math.min(n, Math.max(1, (hover || n) + (e.key === "ArrowRight" ? 1 : -1))));
    });
    new ResizeObserver(draw).observe(box);
  }

  function render(dashboard) {
    if (!nodes) return;
    const d = dashboard || {};
    const next = parts(d);
    nodes.lead.className = `lead-num num ${next.leadClass}`;
    nodes.lead.innerHTML = next.lead;
    nodes.sub.removeAttribute("aria-busy");
    nodes.sub.innerHTML = next.sub;
    nodes.facts.hidden = false;
    nodes.facts.innerHTML = next.facts;
    points = Array.isArray(d.hand_points) ? d.hand_points : [];
    if (note) { note = ""; layout = null; }
    draw();
  }

  function notice(text, { keep = false } = {}) {
    if (!nodes) return;
    nodes.sub.removeAttribute("aria-busy");
    if (keep) { nodes.sub.textContent = text; return; }
    note = text;
    points = []; layout = null; hover = 0;
    nodes.lead.className = "lead-num num muted";
    nodes.lead.textContent = "—";
    nodes.sub.textContent = "";
    nodes.facts.hidden = true;
    nodes.facts.innerHTML = "";
    nodes.chart.innerHTML = `<div class="pnl-empty">${esc(text)}</div>`;
  }

  window.PFMoney = { mount, render, notice, parts, chart, hold };
})();
