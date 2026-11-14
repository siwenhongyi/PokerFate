/* Shared by the local console and the standalone VPS viewer. */
(() => {
    const $ = (id) => document.getElementById(id);
    function escapeHtml(text) {
      return String(text ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
    }

    function cardHtml(card) {
      const text = String(card || "");
      if (!text) return "";
      const suit = text.slice(-1);
      const cls = (suit === "♥" || suit === "♦") ? "red" : "black";
      return `<span class="card ${cls}">${escapeHtml(text)}</span>`;
    }

    // ── live table ──────────────────────────────────────────────
    const SUIT_SYM = { s: "♠", h: "♥", d: "♦", c: "♣" };
    function suitify(card) {
      const t = String(card || "");
      if (!t) return "";
      const suit = t.slice(-1).toLowerCase();
      return SUIT_SYM[suit] ? t.slice(0, -1) + SUIT_SYM[suit] : t;
    }
    function liveCardHtml(card) { return card ? cardHtml(suitify(card)) : '<span class="card unknown">?</span>'; }
    const POS_TITLE = { "BTN": "庄位", "BTN/SB": "庄位（兼小盲）", "SB": "小盲", "BB": "大盲",
                        "CO": "关煞位（庄位前一位）", "MP": "中位", "UTG": "枪口位" };

    let settlement = null;
    let settlementId = null;
    let revealUntil = 0;
    let summaryMarkup = "";

    function holeCards(cards) {
      const hole = cards && cards.length ? cards : [null, null];
      return hole.map(liveCardHtml).join("");
    }

    function groupHtml(player, label) {
      const group = player.group || {};
      const cards = (group.cards || []).map((card, i) =>
        `<span class="showdown-card${(group.hole_used || [])[i] ? " from-hole" : ""}">${liveCardHtml(card)}</span>`).join("");
      return `<div class="showdown-player">` +
        `<div class="showdown-player-name">${escapeHtml(label)} <b>${escapeHtml(group.label || "未知牌型")}</b></div>` +
        `<div class="showdown-best">${cards || '<span class="muted">最佳五张暂不可用</span>'}</div>` +
        `<div class="showdown-hole">底牌 ${holeCards(player.hole)}${player.folded ? '<span class="showdown-folded">已弃牌</span>' : ""}</div>` +
        (group.note ? `<div class="showdown-note">${escapeHtml(group.note)}</div>` : "") + `</div>`;
    }

    function drawSettlement() {
      const node = $("live-settlement");
      if (!node) return;
      if (!settlement) { node.hidden = true; node.innerHTML = ""; summaryMarkup = ""; return; }
      node.hidden = false;
      const revealing = performance.now() < revealUntil;
      const shown = settlement.revealed || [];
      const revealHtml = shown.map((p) =>
        `<div class="showdown-reveal"><span>${escapeHtml(p.name)}</span><div>${holeCards(p.hole)}</div></div>`).join("");
      const winnerHtml = (settlement.winners || []).map((p) =>
        groupHtml(p, `${p.name || "赢家"} · 获得 ${Number(p.chips || 0).toLocaleString()}`)).join("");
      const board = (settlement.board || []).map(liveCardHtml).join("");
      const markup = `<div class="showdown-heading"><strong>第 ${Number(settlement.hand_no || 0)} 手结算</strong>` +
        `<span>${revealing ? "公开亮牌" : "最佳五张牌"}</span></div>` +
        `<div class="showdown-board">本手公共牌 ${board || '<span class="muted">未发公共牌</span>'}</div>` +
        (revealing ? `<div class="showdown-reveals">${revealHtml || '<span class="muted">本手没有玩家公开底牌</span>'}</div>` +
          '<div class="showdown-note">随后展示赢家和我的牌型，结果保留至下一次结算</div>' :
          `<div class="showdown-row winners"><span class="showdown-label">赢家</span><div>${winnerHtml || '<span class="muted">暂无赢家信息</span>'}</div></div>` +
          `<div class="showdown-row hero"><span class="showdown-label">我</span><div>${groupHtml(settlement.hero || {}, "我的牌型")}</div></div>` +
          (shown.length ? `<div class="showdown-reveals small">${revealHtml}</div>` : "") +
          '<div class="showdown-note">金色标记为使用的底牌；按本手实际发出的公共牌计算。新一手牌桌照常更新。</div>');
      if (markup !== summaryMarkup) { node.innerHTML = markup; summaryMarkup = markup; }
    }

    function renderSettlement(data) {
      const next = data.settlement;
      if (!next) { settlement = null; settlementId = null; revealUntil = 0; drawSettlement(); return; }
      if (next.id !== settlementId) {
        settlementId = next.id;
        revealUntil = performance.now() + Math.max(2.5, Math.min(4, Number(next.reveal_seconds) || 2.5)) * 1000;
      }
      settlement = next;
      drawSettlement();
    }

    setInterval(() => {
      if (settlement && revealUntil && performance.now() >= revealUntil) {
        revealUntil = 0;
        drawSettlement();
      }
    }, 100);

    function renderLive(payload) {
      const data = payload || {};
      const conn = $("live-conn");
      const available = payload && payload.__available;
      if (conn) {
        const on = !!data.connected;
        conn.className = "live-conn " + (on ? "on" : "off");
        conn.textContent = on ? (data.room_id ? "● 已连接 · 牌桌" : "● 已连接 · 大厅") : (available ? "● 连接已断开" : "● 无 headless 会话");
        if (data.connection_status === "reconnecting") conn.textContent = "● 连接中断 · 自动重连中";
        if (data.connection_status === "restoring") conn.textContent = "● 已连接 · 恢复牌桌中";
      }
      const pnl = $("live-pnl"), rewards = $("live-rewards");
      if (pnl) {
        const n = data.session_pnl_chips;
        pnl.textContent = Number.isSafeInteger(n) ? `${n > 0 ? "+" : ""}${n.toLocaleString("zh-CN")} 筹码` : "—";
        pnl.className = n > 0 ? "pos" : n < 0 ? "neg" : "";
      }
      if (rewards) {
        const n = data.session_reward_chips;
        rewards.textContent = Number.isSafeInteger(n)
          ? `${n.toLocaleString("zh-CN")} 筹码${data.session_rewards_uncertain ? "（另有待确认）" : ""}` : "—";
      }
      $("live-room").textContent = data.room_id || "-";
      $("live-blinds").textContent = (data.sb && data.bb) ? `${data.sb}/${data.bb}` : "-";
      $("live-street").textContent = ({preflop:"翻前",flop:"翻牌",turn:"转牌",river:"河牌"}[data.street]) || "-";
      $("live-pot").textContent = Number(data.pot || 0).toLocaleString();
      $("live-hand").textContent = data.hand_no || "-";
      const mix = $("live-mix");
      if (mix) mix.textContent = data.room_id ? `真人 ${Number(data.humans || 0)} · 人机 ${Number(data.robots || 0)}` : "-";
      $("live-board").innerHTML = (data.board || []).map(liveCardHtml).join("");
      $("live-potc").textContent = "底池 " + Number(data.pot || 0).toLocaleString();
      $("live-result").textContent = data.result || "";

      const seats = data.seats || [];
      const seatNum = Math.max(data.seat_num || 6, seats.length || 0) || 6;
      const mySeat = (data.my_seat == null) ? 0 : data.my_seat;
      const felt = $("live-felt");
      const anyPlayer = seats.some((s) => s && !s.empty);
      $("live-empty").style.display = anyPlayer ? "none" : "block";
      $("live-empty").textContent = data.connected && !data.room_id ? "当前在大厅，等待进桌…" : "等待对局…";

      // responsive geometry: keep every seat box fully inside the felt so
      // names never get clipped, even on a narrow phone.
      const fw = felt.clientWidth || 600, fh = felt.clientHeight || 440;
      const compact = fw < 540;
      felt.classList.toggle("compact", compact);
      const seatW = Math.max(92, Math.min(150, Math.round(fw * (compact ? 0.30 : 0.26))));
      const seatHalfH = compact ? 42 : 52;
      const rx = Math.max(20, 50 - ((seatW / 2 + 8) / fw) * 100);
      const ry = Math.max(26, 50 - ((seatHalfH + 6) / fh) * 100);
      // keep a stable set of seat nodes
      felt.querySelectorAll(".live-seat").forEach((n) => { n.dataset.keep = "0"; });
      for (let i = 0; i < seatNum; i++) {
        const rel = ((i - mySeat) % seatNum + seatNum) % seatNum;
        const ang = (90 + rel * (360 / seatNum)) * Math.PI / 180;
        const x = 50 + rx * Math.cos(ang);
        const y = 50 + ry * Math.sin(ang);
        let node = felt.querySelector(`.live-seat[data-seat="${i}"]`);
        if (!node) {
          node = document.createElement("div");
          node.className = "live-seat";
          node.dataset.seat = String(i);
          felt.appendChild(node);
        }
        node.dataset.keep = "1";
        node.style.left = x + "%";
        node.style.top = y + "%";
        node.style.width = seatW + "px";
        const s = seats.find((e) => e && e.seatid === i) || { empty: true, seatid: i };
        if (s.empty) {
          node.className = "live-seat empty";
          node.innerHTML = `<div class="s-name">空位</div>`;
          continue;
        }
        const cls = ["live-seat"];
        if (s.is_me) cls.push("me");
        if (s.acting) cls.push("acting");
        if (s.folded && !s.revealed) cls.push("folded");
        if (s.revealed) cls.push("revealed");
        // 人机：服务器计数证实的（人机）或 UID 落在人机号段内的（疑似人机）。
        const robot = s.kind === "robot" || s.kind === "suspect";
        if (robot) cls.push("robot");
        node.className = cls.join(" ");
        let cardsHtmlStr = "";
        if (s.cards && s.cards.length) {
          cardsHtmlStr = s.cards.map(liveCardHtml).join("");
        } else if (!s.folded) {
          cardsHtmlStr = '<div class="back"></div><div class="back"></div>';
        }
        const tags = [];
        if (s.kind === "robot") tags.push('<span class="pill robot">人机</span>');
        else if (s.kind === "suspect") tags.push('<span class="pill robot suspect">疑似人机</span>');
        if (s.allin) tags.push('<span class="pill allin">ALLIN</span>');
        if (s.revealed) tags.push('<span class="pill">亮牌</span>');
        const posCls = { "BTN": "btn", "BTN/SB": "btn", "SB": "sb", "BB": "bb" }[s.pos] || "";
        const posHtml = s.pos ? `<span class="s-pos ${posCls}" title="${POS_TITLE[s.pos] || ""}">${escapeHtml(s.pos)}</span>` : "";
        node.innerHTML =
          `<div class="s-head">${posHtml}<div class="s-name">${escapeHtml(s.name || ("玩家" + i))}${s.is_me ? " ·我" : ""}</div></div>` +
          `<div class="s-stack">${Number(s.stack || 0).toLocaleString()}</div>` +
          (tags.length ? `<div class="s-tags">${tags.join("")}</div>` : "") +
          `<div class="s-cards">${cardsHtmlStr}</div>` +
          `<div class="s-last">${escapeHtml(s.last || "")}</div>` +
          (s.bet > 0 ? `<div class="s-bet">${Number(s.bet).toLocaleString()}</div>` : "");
      }
      felt.querySelectorAll('.live-seat[data-keep="0"]').forEach((n) => n.remove());

      const feed = data.feed || [];
      $("live-feed").innerHTML = feed.length
        ? feed.slice().reverse().map((t) => `<li class="${t.startsWith("▸") ? "win" : ""}">${escapeHtml(t)}</li>`).join("")
        : '<li class="muted">暂无</li>';
      renderSettlement(data);
    }


    window.PFLiveTable = { render: renderLive };
})();
