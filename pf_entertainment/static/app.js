/* Local console: three views behind one address, so the browser's back button works.
 *
 *   #table           the live table (live-table.js)
 *   #money           the session result and the account (live-money.js)
 *   #hands[/<id>]    the hands played, and one hand read street by street
 *
 * live-views.js switches between them.  The table and the money view are shared with the VPS
 * viewer; the hands exist only here.
 */
(() => {
  const $ = (id) => document.getElementById(id);
  const T = window.PFLiveTable;
  const { esc, card, cards } = T;
  const { bbNumber, bbText, chipsFull, chipsShort, chipsTitle, moneyClass, trim } = T.fmt;
  const phone = window.matchMedia("(max-width: 860px)");

  async function api(path) {
    const res = await fetch(path, { cache: "no-store" });
    const data = await res.json();
    if (!res.ok || data.ok === false) throw new Error(data.error || `HTTP ${res.status}`);
    return data;
  }

  // ── the table ───────────────────────────────────────────────────────────────
  T.mount($("live-root"));
  async function refreshLive() {
    try {
      const res = await api("/api/live");
      T.render({ ...(res.live || {}), __available: res.available });
    } catch (_) {
      T.render({ __available: false });     // the console is served by the bot: no answer, no bot
    }
  }

  // ── money ───────────────────────────────────────────────────────────────────
  window.PFMoney.mount($("money-root"));
  async function refreshMoney() {
    let status;
    try {
      status = await api("/api/status");
    } catch (err) {
      window.PFMoney.notice("读不到资金数据，几秒后自动重试", { keep: true });
      throw err;
    }
    const runtime = status.runtime || {};
    const urls = runtime.web_urls && runtime.web_urls.length ? runtime.web_urls.join("  ") : (runtime.web_url || "");
    $("app-status").textContent = urls;
    window.PFMoney.render(runtime.bot_dashboard || {});
  }

  // ── hands: the list ─────────────────────────────────────────────────────────
  const STREET = { preflop: "翻前", flop: "翻牌", turn: "转牌", river: "河牌" };
  const ACTION = { fold: "弃牌", check: "过牌", call: "跟注", raise: "加注", bet: "下注", jam: "全下" };
  const DEFAULTS = { vpip: "yes", result: "all", position: "all", bb_k: "all" };
  const filters = $("hand-filters");
  let page = 1;
  let selected = 0;          // the hand shown in the detail pane
  let optionsReady = false;
  let pushedHand = false;    // the open hand was opened from the list, so "back" returns to it

  // Text from the log with its card tokens drawn as cards.
  function withCards(text) {
    return String(text || "").replace(/️/g, "").split(/((?:10|[2-9TJQKA])[♠♥♦♣])/)
      .map((part, i) => (i % 2 ? card(part, "sm") : esc(part))).join("");
  }

  // In the log's texts our own account goes by its game name; on this page it is "我".
  const asUs = (text, hero) => (hero ? String(text || "").split(hero).join("我") : String(text || ""));

  function rowHtml(h) {
    const result = !h.complete ? '<span class="hr-res muted">没打完</span>'
      : `<span class="hr-res ${moneyClass(h.pnl)}" title="${chipsTitle(h.pnl)}">${bbNumber(h.pnl_bb, 1, { signed: true })}<small>BB</small></span>`;
    const end = [`${STREET[h.final_street] || ""}${ACTION[h.final_action] || ""}`,
                 h.winner_text ? `${asUs(h.winner_text, h.hero).replace(/️/g, "")} 赢` : ""].filter(Boolean).join("，");
    return `<button type="button" class="hand-row" data-id="${h.id}"${h.id === selected ? ' aria-current="true"' : ""}>` +
      `<span class="hr-time">${esc(String(h.time || "").slice(0, 5))}<small>${esc(h.position || "")}</small></span>` +
      `<span class="hr-cards"><span class="cards">${cards(h.hole_cards)}</span>` +
      (h.board && h.board.length ? `<span class="cards">${cards(h.board, "sm")}</span>` : "") + `</span>` +
      `<span class="hr-end">${esc(end)}</span>${result}</button>`;
  }

  function renderHands(data) {
    if (!optionsReady) {
      const fill = (name, label, values, text) => {
        const select = filters.elements[name], keep = select.value;
        select.innerHTML = `<option value="all">${label}</option>` +
          values.map((v) => `<option value="${esc(v)}">${esc(text(v))}</option>`).join("");
        select.value = keep;
      };
      fill("position", "位置不限", data.positions || [], (v) => v);
      fill("bb_k", "盲注不限", data.bb_k_values || [], (v) => `盲注 ${v}k`);
      optionsReady = true;
    }
    for (const [name, initial] of Object.entries(DEFAULTS)) {
      filters.elements[name].classList.toggle("set", filters.elements[name].value !== initial);
    }
    page = Number(data.page || 1);
    $("hands-count").textContent = `共 ${Number(data.count || 0).toLocaleString("zh-CN")} 手`;
    $("hands-page").textContent = `${page} / ${Number(data.page_count || 1)}`;
    $("hands-prev").disabled = !data.has_prev;
    $("hands-next").disabled = !data.has_next;
    const hands = data.hands || [];
    $("hand-list").innerHTML = hands.length ? hands.map(rowHtml).join("")
      : '<div class="hands-empty">没有符合条件的手牌。放宽上面的筛选再看。</div>';
    // On a wide screen the pane beside the list always shows a hand.
    if (!phone.matches && hands.length && !hands.some((h) => h.id === selected)) showHand(hands[0].id);
    if (!hands.length && !phone.matches) $("hand-sheet").innerHTML = '<div class="sheet-empty">选一手牌，在这里逐街回看。</div>';
  }

  async function loadHands() {
    const params = new URLSearchParams({ page: String(page), page_size: "30" });
    for (const name of [...Object.keys(DEFAULTS), "board"]) params.set(name, filters.elements[name].value.trim());
    try {
      renderHands(await api(`/api/hands?${params}`));
    } catch (err) {
      // Rows already on screen stay; with nothing to show, say why and that it is retried.
      $("hands-count").textContent = "读取失败，几秒后自动重试";
      if (!document.querySelector(".hand-row")) {
        $("hand-list").innerHTML = `<div class="hands-empty">读不到对局记录（${esc(err.message)}）。bot 在运行的话，几秒后会自动重试。</div>`;
      }
    }
  }
  const reloadFromFirstPage = () => { page = 1; loadHands(); };
  filters.addEventListener("change", reloadFromFirstPage);
  filters.addEventListener("input", (e) => { if (e.target.name === "board") reloadFromFirstPage(); });
  filters.addEventListener("submit", (e) => e.preventDefault());
  $("hands-prev").addEventListener("click", () => { page = Math.max(1, page - 1); loadHands(); });
  $("hands-next").addEventListener("click", () => { page += 1; loadHands(); });
  $("hand-list").addEventListener("click", (e) => {
    const row = e.target.closest(".hand-row");
    if (!row) return;
    pushedHand = true;
    location.hash = `hands/${row.dataset.id}`;
  });

  // ── hands: one hand ─────────────────────────────────────────────────────────
  // The price our next decision faces is the one named on the bet just before it.
  function eventHtml(e, street, bb, facing) {
    if (e.kind === "note") return `<li class="ev note">${esc(e.text)}</li>`;
    if (e.kind === "action") {
      if (e.odds_pct != null) facing.need = e.odds_pct / 100;
      else if (e.action !== "fold") facing.need = null;
      const amount = e.amount_bb != null ? `<b class="num">${e.amount_bb}<small>BB</small></b>` : "";
      const ratio = e.pot_ratio != null ? `<span class="ratio">${trim(e.pot_ratio, 1)} 倍底池</span>` : "";
      const read = [];
      if (e.range_pct != null) read.push(`范围 ${e.range_pct}%${e.range_mix ? `（${esc(e.range_mix.replaceAll("/", "、"))}）` : ""}`);
      if (e.versus) read.push(`${e.versus[0]}% 比我们强，${e.versus[2]}% 比我们弱`);
      if (e.to_call_bb != null) read.push(`我们要跟 ${e.to_call_bb}BB，需要胜率 ${e.odds_pct}%`);
      return `<li class="ev"><span class="ev-who">${esc(e.who)}<small>${esc(e.pos || "")}</small></span>` +
        `<span class="ev-act act-${e.action}">${e.action_cn}${amount}${ratio}</span>` +
        (read.length ? `<span class="ev-read">${read.join("；")}</span>` : "") + `</li>`;
    }
    const lines = e.why || [];
    const first = lines[0] || "";
    const engine = first.startsWith("realtime_cfr") ? "realtime_cfr" : /GTOv2/.test(first) ? "rule_engine" : "";
    const head = T.decisionHtml({
      street: street.key, action: e.action, amount: e.amount, to_call: e.action === "call" ? e.amount : 0,
      pot: e.pot, equity: e.equity / 100, equity_random: e.equity_random == null ? null : e.equity_random / 100,
      spr: e.spr, engine, mode: e.mode, ms: e.ms, why: first,
      need: e.action === "call" ? undefined : facing.need, facing: facing.need != null,
    }, bb, { who: "我" });
    facing.need = null;
    const split = (rows) => rows.flatMap((row) => String(row).split("│")).map((s) => s.trim()).filter(Boolean);
    const list = (rows) => `<ul>${rows.map((row) => `<li>${esc(row)}</li>`).join("")}</ul>`;
    let more = "";
    if (lines.length > 1) more += list(split(lines.slice(1)));
    if (e.refs && e.refs.length) more += `<h4>翻前表</h4>${list(e.refs)}`;
    if (e.shadow) more += `<h4>规则引擎会${e.shadow.action_cn ? `选「${esc(e.shadow.action_cn)}」` : "怎么打"}</h4>${list(split(e.shadow.text || []))}`;
    return `<li class="ev hero">${head}${more ? `<details class="more"><summary>完整推理</summary>${more}</details>` : ""}</li>`;
  }

  function handHtml(data) {
    const h = data.hand || {}, detail = data.detail;
    const bb = Number(h.bb_chips || 0);
    const result = !h.complete ? '<div class="rec-result muted">没打完</div>'
      : `<div class="rec-result ${moneyClass(h.pnl)}" title="${chipsTitle(h.pnl)}">${bbNumber(h.pnl_bb, 1, { signed: true, digits: 2 })}<small>BB</small></div>`;
    const where = [h.position ? `${esc(h.position)}位` : "", bb ? `盲注 ${chipsShort(bb)}` : "",
                   h.hero_stack_bb != null ? `起手 ${h.hero_stack_bb}BB` : ""].filter(Boolean).join("，");
    let html = `<header class="rec-head">` +
      `<button type="button" class="rec-back" aria-label="返回列表"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M15 5l-7 7 7 7"/></svg></button>` +
      `<div class="rec-title">${esc(h.time || "")}<small>${where}</small></div>${result}</header><div class="rec-body">`;
    html += `<div class="rec-deal"><div><span class="lbl">底牌</span><span class="cards">${cards(h.hole_cards, "md") || "-"}</span></div>` +
      `<div><span class="lbl">公共牌</span><span class="cards">${h.board && h.board.length ? cards(h.board, "md") : '<span class="muted">没有发</span>'}</span></div></div>`;
    if (detail) {
      html += `<div class="rec-players">` + detail.players.map((p) =>
        `<span class="rec-player${p.hero ? " me" : ""}"><b>${p.hero ? "我" : esc(p.name)}</b>${esc(p.pos)} ${p.stack_bb}BB</span>`).join("") + `</div>`;
      for (const street of detail.streets) {
        const facing = { need: null };
        html += `<section class="rec-street"><h3>${esc(street.name)}<span class="cards">${cards(street.cards)}</span>` +
          (street.pot > 0 ? `<span class="rec-pot" title="${chipsTitle(street.pot)}">底池<b>${trim(street.pot_bb, 1)}BB</b></span>` : "") + `</h3>` +
          (street.events.length ? `<ol>${street.events.map((e) => eventHtml(e, street, bb, facing)).join("")}</ol>`
            : '<p class="empty-line">这条街没有动作。</p>') + `</section>`;
      }
    }
    if (h.complete) {
      html += `<footer class="rec-end">${withCards(asUs(h.winner_text, h.hero))} 赢得 <b class="num" title="${chipsTitle(h.pot)}">${bb ? bbText(h.pot, bb) : chipsFull(h.pot)}</b>` +
        (h.hero_combo ? `<br>我的牌型：${withCards(h.hero_combo)}` : "") + `</footer>`;
    }
    html += `<details class="more rec-raw"${detail ? "" : " open"}><summary>原始日志</summary><pre>${esc(data.log_text || "")}</pre></details></div>`;
    return html;
  }

  async function showHand(id) {
    selected = id;
    document.querySelectorAll(".hand-row").forEach((row) => {
      if (Number(row.dataset.id) === id) row.setAttribute("aria-current", "true");
      else row.removeAttribute("aria-current");
    });
    const sheet = $("hand-sheet");
    if (sheet.dataset.hand !== String(id)) sheet.innerHTML = '<div class="sheet-empty" aria-busy="true">正在读取这手牌</div>';
    sheet.dataset.hand = String(id);
    try {
      sheet.innerHTML = handHtml(await api(`/api/hand?id=${encodeURIComponent(id)}`));
    } catch (err) {
      sheet.innerHTML = `<div class="sheet-empty">这手牌读不出来：${esc(err.message)}。日志可能已经轮换，回到列表刷新一下。</div>`;
    }
    sheet.scrollTop = 0;
  }
  function setSheet(open) {
    $("hand-sheet").classList.toggle("open", open);
    document.body.style.overflow = open && phone.matches ? "hidden" : "";
  }
  function closeHand() {
    if (pushedHand) history.back();
    else location.replace("#hands");
  }
  $("hand-sheet").addEventListener("click", (e) => { if (e.target.closest(".rec-back")) closeHand(); });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && $("hand-sheet").classList.contains("open") && phone.matches) closeHand();
  });

  // ── which view is shown, and what it polls ──────────────────────────────────
  window.PFViews.start(
    { table: [refreshLive, 700], money: [refreshMoney, 2000], hands: [() => (page === 1 ? loadHands() : null), 5000] },
    {
      // A hand open over the list on a phone: nothing behind it needs redrawing.
      covered: (view) => view === "hands" && phone.matches && $("hand-sheet").classList.contains("open"),
      onRoute(view, arg) {
        const hand = view === "hands" ? Number(arg) || 0 : 0;
        if (hand) showHand(hand);
        else pushedHand = false;
        setSheet(Boolean(hand));
      },
    });
})();
