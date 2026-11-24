/* The console's 雷达 view: what the activity radar finds undone, and the ignore list.
 *
 *   PFRadar.mount(root, { post })     post(body) -> Promise<state>: one decision to the server
 *   PFRadar.render(state)             state from GET /api/radar
 *   PFRadar.parts(state, { show })    the HTML strings, without the DOM (tested in node)
 *
 * Every item carries the ignore key that would leave it alone.  "忽略" asks once, in a sheet:
 * this item only, or the whole kind it belongs to, and why.  The user's decisions go to the
 * external ignore file and win over the project's own (internal) ones, which can be taken back.
 */
(() => {
  const esc = (s) => String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const KIND = { "新活动": "要写代码", "活动缺口": "活动缺口", "日常任务缺口": "日常任务" };
  const kindOf = (title) => Object.keys(KIND).find((k) => title.startsWith(k)) || "";
  const nameOf = (title) => title.replace(/^(新活动|活动缺口) · /, "").replace(/（还没有代码）$/, "");

  function itemMeta(item) {
    if (item.what === "period") return "还没有处理它的代码，要做得新写一个模块";
    const bits = [`类型 ${item.type}`];
    if (item.steps > 1) bits.push(`共 ${item.steps} 档`);
    if (item.list) bits.push(item.list);
    return bits.join(" · ");
  }

  function openRow(item, ref) {
    const limit = item.what === "limit";
    return `<li class="rd-item">` +
      `<div class="rd-text"><span class="rd-name">${esc(item.text)}</span>` +
      `<span class="rd-meta">${limit ? '<b class="rd-flag">额度不够</b>' : ""}${esc(limit ? item.detail : itemMeta(item))}</span></div>` +
      `<button type="button" class="rd-btn" data-act="ask" data-ref="${ref}">忽略</button></li>`;
  }

  function ignoredRow(item) {
    const mine = item.ignored.by === "外部";
    return `<li class="rd-item quiet">` +
      `<div class="rd-text"><span class="rd-name">${esc(item.text)}</span>` +
      `<span class="rd-meta"><b class="rd-who ${mine ? "mine" : ""}">${mine ? "你" : "项目"}</b>${esc(item.ignored.reason)}</span></div></li>`;
  }

  function findingCard(f, at) {
    const kind = kindOf(f.title);
    const open = f.items.map((item, i) => [item, `${at}:${i}`]).filter(([item]) => !item.ignored);
    const quiet = f.items.filter((i) => i.ignored);
    return `<article class="panel rd-card${kind === "新活动" ? " rd-new" : ""}">` +
      `<header class="rd-head"><h3>${esc(nameOf(f.title))}</h3><span class="rd-kind">${esc(KIND[kind] || kind)}</span></header>` +
      `<p class="rd-when">${esc(f.when)}</p>` +
      (open.length ? `<ul class="rd-list">${open.map(([item, ref]) => openRow(item, ref)).join("")}</ul>` : "") +
      (quiet.length ? `<details class="rd-quiet"><summary>已忽略 ${quiet.length} 项</summary><ul class="rd-list">${quiet.map(ignoredRow).join("")}</ul></details>` : "") +
      `</article>`;
  }

  // The project's decisions that share a reason are one row ("直播和投稿 … 10 条").
  function grouped(entries) {
    const groups = new Map();
    for (const e of entries) {
      const id = `${e.by}|${e.reason}|${e.ignore}|${e.overridden}`;
      if (!groups.has(id)) groups.set(id, []);
      groups.get(id).push(e);
    }
    return [...groups.values()];
  }

  function decisionRow(group) {
    const e = group[0];
    const keys = group.map((x) => x.key).join(" ");
    let who, action;
    if (e.by === "外部") {
      who = '<b class="rd-who mine">你</b>';
      action = `<button type="button" class="rd-btn" data-act="reset" data-key="${esc(keys)}">恢复提醒</button>`;
    } else if (e.overridden && !e.ignore) {
      who = '<b class="rd-who mine">你改为提醒</b>';
      action = `<button type="button" class="rd-btn" data-act="reset" data-key="${esc(keys)}">按项目的来</button>`;
    } else {
      who = '<b class="rd-who">项目</b>';
      action = `<button type="button" class="rd-btn" data-act="unignore" data-key="${esc(keys)}">改为提醒</button>`;
    }
    const what = group.length > 1
      ? `<details class="rd-many"><summary>${group.length} 类任务</summary><ul>${group.map((x) => `<li>${esc(x.label)}</li>`).join("")}</ul></details>`
      : `<span class="rd-name">${esc(e.label)}</span>`;
    return `<li class="rd-item${!e.ignore ? " off" : ""}"><div class="rd-text">${what}` +
      `<span class="rd-meta">${who}${esc(e.reason)}${e.at ? `<small>${esc(e.at)}</small>` : ""}</span></div>${action}</li>`;
  }

  function parts(state, { show = "open" } = {}) {
    const findings = (state && state.findings) || [];
    const ignores = (state && state.ignores) || [];
    const undone = findings.map((f, at) => [f, at]).filter(([f]) => !f.muted);
    const openCount = undone.reduce((n, [f]) => n + f.items.filter((i) => !i.ignored).length, 0);
    const quietCount = ignores.filter((e) => e.ignore).length;
    const mineCount = ignores.filter((e) => e.by === "外部" || e.overridden).length;
    const summary =
      `<div class="rd-sum"><div class="rd-count"><span class="num">${openCount}</span><span>项没处理</span></div>` +
      `<p class="rd-note">雷达每 6 小时对照一次客户端的表${state && state.res ? `（${esc(state.res)}）` : ""}，` +
      `没处理的每次都推到手机。不想再收到的，点<span class="rd-keep">「忽略」</span>。</p></div>` +
      `<div class="rd-seg" role="tablist" aria-label="列表">` +
      `<button type="button" role="tab" data-show="open" aria-selected="${show === "open"}">没处理<span class="num">${openCount}</span></button>` +
      `<button type="button" role="tab" data-show="ignored" aria-selected="${show === "ignored"}">已忽略<span class="num">${quietCount}</span></button></div>`;
    const openHtml = undone.length
      ? undone.map(([f, at]) => findingCard(f, at)).join("")
      : '<div class="panel rd-empty">没有没处理的事。新活动进表后，雷达会在这里列出来。</div>';
    const mine = ignores.filter((e) => e.by === "外部" || e.overridden);
    const projects = ignores.filter((e) => e.by === "内部" && !e.overridden);
    const ignoredHtml =
      `<section class="panel rd-card"><header class="rd-head"><h3>你的决定</h3><span class="rd-kind">${mineCount} 条</span></header>` +
      (mine.length ? `<ul class="rd-list">${grouped(mine).map(decisionRow).join("")}</ul>`
        : '<p class="rd-when">还没有。在「没处理」里点「忽略」，就会记在这里。</p>') + `</section>` +
      `<section class="panel rd-card"><header class="rd-head"><h3>项目的决定</h3><span class="rd-kind">写在代码里</span></header>` +
      `<ul class="rd-list">${grouped(projects).map(decisionRow).join("")}</ul></section>` +
      `<p class="rd-file">你的决定保存在 <code>${esc(state && state.file || "local/state/lobby_ignores.json")}</code>，优先于项目的决定，下一次雷达运行起生效。</p>`;
    return { summary, list: show === "open" ? openHtml : ignoredHtml, openCount, quietCount };
  }

  // What each choice leaves alone, in words: an ignore key holds wherever the same task shows up.
  function scopesOf(item) {
    if (item.what === "period") return [[item.key, "只忽略这一期"], [item.kind_key, "这类活动以后每一期都忽略"]];
    if (item.what === "limit") return [[item.key, "不再提醒这个额度"]];
    const whole = [item.kind_key || item.key, `类型 ${item.type} 的任务都忽略`];
    return item.kind_key ? [[item.key, "只忽略这一种"], whole] : [whole];
  }

  function sheetHtml(item) {
    const scopes = scopesOf(item);
    return `<div class="rd-sheet" role="dialog" aria-modal="true" aria-labelledby="rd-sheet-title">` +
      `<form class="rd-sheet-card" id="rd-form"><h3 id="rd-sheet-title">忽略后不再推送</h3>` +
      `<p class="rd-sheet-item">${esc(item.text)}</p>` +
      `<fieldset class="rd-scope"><legend>范围</legend>${scopes.map(([key, text], i) =>
        `<label><input type="radio" name="key" value="${esc(key)}"${i === 0 ? " checked" : ""}><span>${esc(text)}</span></label>`).join("")}</fieldset>` +
      `<p class="rd-scope-note">对所有活动和日常任务生效：别处同样的任务也不再提醒。</p>` +
      `<label class="rd-reason"><span>原因（可不填）</span><input name="reason" id="rd-reason" maxlength="80" autocomplete="off" placeholder="比如：不打锦标赛"></label>` +
      `<div class="rd-sheet-btns"><button type="button" class="rd-btn ghost" data-act="close">取消</button>` +
      `<button type="submit" class="rd-btn solid">忽略</button></div></form></div>`;
  }

  let root = null, post = null, state = null, show = "open", busy = false, error = "";

  function draw() {
    if (!root || !state) return;
    if (state.available === false) {
      root.innerHTML = '<div class="panel rd-empty">这个入口没有接上雷达。</div>';
      return;
    }
    const p = parts(state, { show });
    const keep = root.querySelector(".rd-sheet") ? root.querySelector(".rd-sheet").outerHTML : "";
    const problem = error ? `<p class="rd-error" role="alert">${esc(error)}</p>` : "";
    root.innerHTML = `<div class="rd" aria-busy="${busy}">${problem}${p.summary}<div class="rd-cards">${p.list}</div></div>${keep}`;
  }

  function findItem(ref) {
    const [at, i] = String(ref).split(":").map(Number);
    const f = (state.findings || [])[at];
    return f ? f.items[i] || null : null;
  }

  async function send(bodies) {
    busy = true; error = ""; draw();
    try {
      for (const body of bodies) state = await post(body);
    } catch (err) {
      error = `没有保存：${err.message}。再点一次试试。`;
    } finally {
      busy = false; draw();
    }
  }

  function closeSheet() {
    const sheet = root.querySelector(".rd-sheet");
    if (sheet) sheet.remove();
  }

  function mount(el, options) {
    root = el; post = options.post;
    root.innerHTML = '<div class="panel rd-empty" aria-busy="true">正在读取雷达的结果</div>';
    root.addEventListener("click", (e) => {
      const seg = e.target.closest("[data-show]");
      if (seg) { show = seg.dataset.show; draw(); return; }
      const btn = e.target.closest("[data-act]");
      if (!btn || busy) return;
      const act = btn.dataset.act;
      if (act === "close" || e.target.classList.contains("rd-sheet")) { closeSheet(); return; }
      if (act === "ask") {
        const item = findItem(btn.dataset.ref);
        if (!item) return;
        closeSheet();
        root.insertAdjacentHTML("beforeend", sheetHtml(item));
        root.querySelector("#rd-reason").focus();
        return;
      }
      const keys = btn.dataset.key.split(" ");
      send(keys.map((key) => ({ action: act, key })));
    });
    root.addEventListener("submit", (e) => {
      if (e.target.id !== "rd-form") return;
      e.preventDefault();
      const form = new FormData(e.target);
      closeSheet();
      send([{ action: "ignore", key: form.get("key"), reason: form.get("reason") || "" }]);
    });
    document.addEventListener("keydown", (e) => { if (e.key === "Escape" && root.querySelector(".rd-sheet")) closeSheet(); });
  }

  function render(next) {
    state = next;
    if (!root.querySelector(".rd-sheet") && !busy) draw();     // a decision in progress keeps its sheet
  }

  window.PFRadar = { mount, render, parts, sheetHtml };
})();
