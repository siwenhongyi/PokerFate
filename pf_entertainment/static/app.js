    const $ = (id) => document.getElementById(id);
    const colorName = (item) => item && item.name ? item.name : "-";
    const signed = (n) => {
      const v = Number(n || 0);
      return `${v > 0 ? "+" : ""}${v.toLocaleString()}`;
    };
    const signedMaybe = (n) => {
      if (n === null || n === undefined || Number.isNaN(Number(n))) return "-";
      return signed(n);
    };
    const chipsMaybe = (n) => {
      if (n === null || n === undefined || Number.isNaN(Number(n))) return "-";
      return Number(n || 0).toLocaleString();
    };
    const bbMaybe = (n, digits = 1) => {
      if (n === null || n === undefined || Number.isNaN(Number(n))) return "-";
      return `${Number(n).toFixed(digits)}BB`;
    };
    const timeMaybe = (seconds) => {
      if (!seconds) return "-";
      return new Date(Number(seconds) * 1000).toLocaleTimeString();
    };
    const moneyClass = (n) => Number(n || 0) >= 0 ? "pos" : "neg";
    const handMoneyClass = (n) => Number(n || 0) > 0 ? "pos" : (Number(n || 0) < 0 ? "neg" : "zero");
    const swatch = (item) => `<span class="swatch"><i class="ball c${item.id}"></i>${colorName(item)}</span>`;
    let activeTab = "live";
    let selectedHandId = null;
    let handFilterOptionsReady = false;
    let handPage = 1;
    let handPageSize = 30;
    let handsLoading = false;

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

    function cardsHtml(cards) {
      const arr = Array.isArray(cards) ? cards : [];
      if (!arr.length) return '<span class="muted">-</span>';
      return `<span class="cards">${arr.map(cardHtml).join("")}</span>`;
    }

    // ── live table ──────────────────────────────────────────────
    const SUIT_SYM = { s: "♠", h: "♥", d: "♦", c: "♣" };
    function suitify(card) {
      const t = String(card || "");
      if (!t) return "";
      const suit = t.slice(-1).toLowerCase();
      return SUIT_SYM[suit] ? t.slice(0, -1) + SUIT_SYM[suit] : t;
    }
    function liveCardHtml(card) { return cardHtml(suitify(card)); }
    let liveSeenPlaying = false;

    function renderLive(payload) {
      const data = payload || {};
      const conn = $("live-conn");
      const available = payload && payload.__available;
      if (conn) {
        const on = !!data.connected;
        conn.className = "live-conn " + (on ? "on" : "off");
        conn.textContent = on ? "● 已连接" : (available ? "● 等待对局" : "● 无 headless 会话");
      }
      $("live-room").textContent = data.room_id || "-";
      $("live-blinds").textContent = (data.sb && data.bb) ? `${data.sb}/${data.bb}` : "-";
      $("live-street").textContent = ({preflop:"翻前",flop:"翻牌",turn:"转牌",river:"河牌"}[data.street]) || "-";
      $("live-pot").textContent = Number(data.pot || 0).toLocaleString();
      $("live-hand").textContent = data.hand_no || "-";
      $("live-board").innerHTML = (data.board || []).map(liveCardHtml).join("");
      $("live-potc").textContent = "底池 " + Number(data.pot || 0).toLocaleString();
      $("live-result").textContent = data.result || "";

      const seats = data.seats || [];
      const seatNum = Math.max(data.seat_num || 6, seats.length || 0) || 6;
      const mySeat = (data.my_seat == null) ? 0 : data.my_seat;
      const felt = $("live-felt");
      const anyPlayer = seats.some((s) => s && !s.empty);
      $("live-empty").style.display = anyPlayer ? "none" : "block";
      if (anyPlayer) liveSeenPlaying = true;

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
        if (s.folded) cls.push("folded");
        node.className = cls.join(" ");
        let cardsHtmlStr = "";
        if (s.cards && s.cards.length) {
          cardsHtmlStr = s.cards.map(liveCardHtml).join("");
        } else if (!s.folded) {
          cardsHtmlStr = '<div class="back"></div><div class="back"></div>';
        }
        const tags = [];
        if (s.allin) tags.push('<span class="pill allin">ALLIN</span>');
        node.innerHTML =
          `<div class="s-name">${escapeHtml(s.name || ("玩家" + i))}${s.is_me ? " ·我" : ""}</div>` +
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
    }

    async function refreshLive() {
      try {
        const res = await api("/api/live");
        const live = res.live || {};
        live.__available = res.available;
        renderLive(live);
      } catch (err) { /* keep last frame on transient errors */ }
    }

    function colorizeLog(text) {
      return escapeHtml(text).replace(/([2-9TJQKA])([♠♥♦♣])️?/g, (_m, rank, suit) => {
        return cardHtml(`${rank}${suit}`);
      });
    }

    function formPayload() {
      const payload = {};
      new FormData($("run-form")).forEach((value, key) => {
        payload[key] = value;
      });
      return payload;
    }

    function pickScopeText(scope) {
      return {
        cycle: "循环",
        bet: "每次",
        random_each: "每次",
        recent3_most: "每次",
      }[scope] || scope || "";
    }

    function pickReasonText(reason) {
      return {
        random: "随机",
        least_seen: "少见优先",
        random_each: "随机",
        recent3_most_seen: "近3次最多",
      }[reason] || reason || "";
    }

    async function api(path, options = {}) {
      const res = await fetch(path, options);
      const data = await res.json();
      if (!res.ok || data.ok === false) {
        throw new Error(data.error || `HTTP ${res.status}`);
      }
      return data;
    }

    function sleep(ms) {
      return new Promise((resolve) => setTimeout(resolve, ms));
    }

    function currentRecord(status) {
      return status.job.current || status.job.last || null;
    }

    function setNotice(message, tone = "error") {
      const el = $("notice");
      if (!message) {
        el.textContent = "";
        el.className = "notice";
        return;
      }
      el.textContent = message;
      el.className = `notice show ${tone}`;
    }

    function setBotNotice(message, tone = "error") {
      const el = $("bot-notice");
      if (!message) {
        el.textContent = "";
        el.className = "notice";
        return;
      }
      el.textContent = message;
      el.className = `notice show ${tone}`;
    }

    function setInputIfFree(id, value) {
      const el = $(id);
      if (document.activeElement !== el) {
        el.value = value ?? "";
      }
    }

    function renderBotSettings(settings) {
      const available = !!settings;
      $("bot-save-btn").disabled = !available;
      $("bot-refresh-btn").disabled = !available;
      if (!available) {
        setBotNotice("Bot 运行参数暂不可用。", "warn");
        return;
      }
      setBotNotice("");
      setInputIfFree("bot-profit-lock-bb", settings.profit_lock_bb);
      if (document.activeElement !== $("bot-decision-engine")) {
        const engineValue = String(settings.decision_engine || "local").replace(/-/g, "_");
        $("bot-decision-engine").value =
          ["local", "g5", "g5_all", "cfr"].includes(engineValue)
            ? engineValue
            : "local";
      }
      const stickyToggle = $("bot-preflop-sticky-pool-adjust");
      if (document.activeElement !== stickyToggle) {
        stickyToggle.checked = settings.preflop_sticky_pool_adjust !== false;
      }
      $("bot-lock-bb").textContent = `${Number(settings.profit_lock_bb || 0).toLocaleString()}BB`;
      $("bot-lock-chips").textContent = settings.profit_lock_chips == null
        ? "-"
        : Number(settings.profit_lock_chips || 0).toLocaleString();
      $("bot-lock-state").textContent = settings.profit_lock_enabled
        ? "启用"
        : `禁用 ${settings.profit_lock_skip_reason || ""}`.trim();
      const engineStatus = settings.decision_engine_status || {};
      const engineMode = engineStatus.enabled
        ? `${engineStatus.engine || "g5"}:${engineStatus.mode || "-"}`
        : "local";
      $("bot-engine-state").textContent = `${settings.decision_engine || "local"} / ${engineMode}`;
      $("bot-preflop-sticky-state").textContent =
        settings.preflop_sticky_pool_adjust !== false ? "启用" : "关闭";
    }

    function renderDashboard(data) {
      const d = data || {};
      $("bank-total").textContent = chipsMaybe(d.current_total_chips);
      $("bank-wallet").textContent = chipsMaybe(d.wallet_chips);
      $("bank-table").textContent = chipsMaybe(d.table_chips);
      $("bank-delta").textContent = signedMaybe(d.session_delta_chips);
      $("bank-delta").className = handMoneyClass(d.session_delta_chips);
      $("bank-last").textContent = timeMaybe(d.last_sample_at);
      $("bank-locks").textContent = Number(d.profit_lock_count || 0).toLocaleString();
      $("bank-rebuys").textContent = `${Number(d.auto_rebuy_count || 0).toLocaleString()} / ${Number(d.max_auto_rebuy || 0).toLocaleString()}`;
      $("bank-escapes").textContent = Number(d.room_escape_count || 0).toLocaleString();
      $("bank-bb").textContent = d.big_blind ? Number(d.big_blind).toLocaleString() : "-";
      const handPoints = Array.isArray(d.hand_points) ? d.hand_points : [];
      const samples = Array.isArray(d.samples) ? d.samples : [];
      renderBankChart(handPoints.length ? handPoints : samples, handPoints.length > 0);
      renderBankSamples(handPoints.length ? handPoints : samples, handPoints.length > 0);
    }

    function bankChartLayout(points, pad) {
      const w = 720;
      const xs = points.map((_s, idx) => (
        points.length <= 1 ? pad : pad + idx * ((w - pad * 2) / (points.length - 1))
      ));
      return {w, xs};
    }

    function renderBankChart(points, perHand = false) {
      const box = $("bank-chart");
      if (!points.length) {
        box.className = "chart-box";
        box.innerHTML = '<div class="muted" style="padding:14px;">暂无余额采样</div>';
        $("bank-chart-meta").textContent = "等待余额采样";
        return;
      }
      const values = points.map((s) => Number(s.delta_chips || 0));
      const min = Math.min(...values, 0);
      const max = Math.max(...values, 0);
      const span = Math.max(1, max - min);
      const h = 240;
      const pad = 28;
      const layout = bankChartLayout(points, pad);
      const w = layout.w;
      const x = (idx) => layout.xs[idx];
      const y = (v) => h - pad - ((v - min) / span) * (h - pad * 2);
      const polyPoints = values.map((v, idx) => `${x(idx)},${y(v)}`).join(" ");
      const zeroY = y(0);
      const dots = points.map((s, idx) => {
        const cls = Number(s.delta_chips || 0) >= 0 ? "#188052" : "#c24136";
        const radius = perHand ? 2.5 : 4;
        const label = s.hand_no ? `第 ${s.hand_no} 手` : (s.reason_text || s.reason || "");
        return `<circle cx="${x(idx)}" cy="${y(Number(s.delta_chips || 0))}" r="${radius}" fill="${cls}"><title>${escapeHtml(label)}: ${signedMaybe(s.delta_chips)} / 总筹码 ${chipsMaybe(s.total_chips)}</title></circle>`;
      }).join("");
      const segmentLines = perHand ? points.map((s, idx) => {
        if (idx <= 0) return "";
        const seq = Number(s.buyin_seq || 0);
        const prevSeq = Number(points[idx - 1].buyin_seq || 0);
        if (!seq || !prevSeq || seq === prevSeq) return "";
        const lx = x(idx);
        return `<g>
          <line x1="${lx}" y1="${pad}" x2="${lx}" y2="${h - pad}" stroke="#f59e0b" stroke-width="1.5" stroke-dasharray="5 4" />
          <text x="${lx + 4}" y="${pad + 12}" fill="#9a6200" font-size="11">买入 ${seq}</text>
        </g>`;
      }).join("") : "";
      box.className = "chart-box";
      box.innerHTML = `<svg viewBox="0 0 ${w} ${h}" role="img" aria-label="余额曲线">
        <line x1="${pad}" y1="${zeroY}" x2="${w - pad}" y2="${zeroY}" stroke="#d8dee8" stroke-width="1" />
        ${segmentLines}
        <polyline points="${polyPoints}" fill="none" stroke="#1677ff" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" />
        ${dots}
        <text x="${pad}" y="18" fill="#667085" font-size="12">${escapeHtml(signedMaybe(max))}</text>
        <text x="${pad}" y="${h - 8}" fill="#667085" font-size="12">${escapeHtml(signedMaybe(min))}</text>
      </svg>`;
      $("bank-chart-meta").textContent = perHand
        ? `${points.length} 手牌点 · 总览`
        : `${points.length} 个采样点`;
    }

    function renderBankSamples(points, perHand = false) {
      const latest = points.slice(-12).reverse();
      if (!latest.length) {
        $("bank-samples").className = "sample-list muted";
        $("bank-samples").textContent = "暂无采样";
        return;
      }
      $("bank-samples").className = "sample-list";
      $("bank-samples").innerHTML = latest.map((s) => {
        const deltaCls = handMoneyClass(s.delta_chips);
        const title = perHand && s.hand_no ? `第 ${s.hand_no} 手` : escapeHtml(s.reason_text || s.reason || "-");
        const sub = perHand
          ? `${timeMaybe(s.ts)} · 买入 ${Number(s.buyin_seq || 1)} · 总筹码 ${chipsMaybe(s.total_chips)} · 本手 ${signedMaybe(s.hand_delta_chips)}`
          : `${timeMaybe(s.ts)} · 钱包 ${chipsMaybe(s.wallet_chips)} · 桌上 ${chipsMaybe(s.table_chips)}`;
        return `<div class="sample-item">
          <div>
            ${title}<br>
            <span class="muted">${sub}</span>
          </div>
          <div class="${deltaCls}">${signedMaybe(s.delta_chips)}<br><span class="muted">${bbMaybe(s.delta_bb)}</span></div>
        </div>`;
      }).join("");
    }

    function setRangeNotice(message, tone = "error") {
      const el = $("range-notice");
      if (!message) {
        el.textContent = "";
        el.className = "notice";
        return;
      }
      el.textContent = message;
      el.className = `notice show ${tone}`;
    }

    function pctMaybe(n, digits = 1) {
      if (n === null || n === undefined || Number.isNaN(Number(n))) return "-";
      return `${(Number(n) * 100).toFixed(digits)}%`;
    }

    function probMaybe(n) {
      if (n === null || n === undefined || Number.isNaN(Number(n))) return "-";
      return Number(n).toFixed(4);
    }

    function rangeWinnerText(winner) {
      if (winner === "bayes") return "Bayes";
      if (winner === "static") return "静态";
      if (winner === "tie") return "接近";
      if (winner === "none") return "无样本";
      return "-";
    }

    function renderRangeTable(bodyId, rows) {
      const body = $(bodyId);
      if (!rows || !rows.length) {
        body.innerHTML = '<tr><td colspan="6" class="muted">暂无足够样本</td></tr>';
        return;
      }
      body.innerHTML = rows.map((row) => {
        const delta = Number(row.avg_delta_nll || 0);
        const deltaCls = delta > 0 ? "pos" : (delta < 0 ? "neg" : "zero");
        return `<tr>
          <td>${escapeHtml(row.key || "-")}<br><span class="muted">${rangeWinnerText(row.winner)} 更优</span></td>
          <td>${Number(row.count || 0).toLocaleString()}</td>
          <td>${Number(row.improved || 0).toLocaleString()} / ${Number(row.worse || 0).toLocaleString()}<br><span class="muted">${pctMaybe(row.positive_rate)} 改善</span></td>
          <td>Bayes ${probMaybe(row.avg_bayes_prob)}<br><span class="muted">静态 ${probMaybe(row.avg_static_prob)}</span></td>
          <td>Bayes ${probMaybe(row.avg_bayes_nll)}<br><span class="muted">静态 ${probMaybe(row.avg_static_nll)}</span></td>
          <td class="${deltaCls}">${delta > 0 ? "+" : ""}${delta.toFixed(4)}<br><span class="muted">中位 ${probMaybe(row.median_delta_nll)}</span></td>
        </tr>`;
      }).join("");
    }

    function eceBiasText(label) {
      if (label === "overconfident") return "预测过高";
      if (label === "underconfident") return "预测过低";
      if (label === "ok") return "接近";
      return "-";
    }

    function eceBiasClass(value) {
      const n = Number(value || 0);
      if (n > 0.03) return "neg";
      if (n < -0.03) return "warn";
      return "zero";
    }

    function renderEceBins(calibration) {
      const rows = (((calibration || {}).overall || {}).bins || []);
      const body = $("range-ece-bin-body");
      if (!rows.length) {
        body.innerHTML = '<tr><td colspan="6" class="muted">暂无 ECE 分桶</td></tr>';
        return;
      }
      body.innerHTML = rows.map((row) => {
        const gap = Number(row.gap || 0);
        return `<tr>
          <td>${escapeHtml(row.bin || "-")}</td>
          <td>${Number(row.count || 0).toLocaleString()}</td>
          <td>${pctMaybe(row.avg_pred, 1)}</td>
          <td>${pctMaybe(row.empirical, 1)}</td>
          <td class="${eceBiasClass(gap)}">${gap >= 0 ? "+" : ""}${pctMaybe(gap, 1)}</td>
          <td>${eceBiasText(row.bias_label)}</td>
        </tr>`;
      }).join("");
    }

    function renderEceRows(bodyId, rows, emptyText) {
      const body = $(bodyId);
      if (!rows || !rows.length) {
        body.innerHTML = `<tr><td colspan="6" class="muted">${escapeHtml(emptyText || "暂无 ECE 分析")}</td></tr>`;
        return;
      }
      body.innerHTML = rows.map((row) => {
        const bias = Number(row.bias || 0);
        const title = row.source ? `${row.source}: ${row.key || "-"}` : (row.key || "-");
        return `<tr>
          <td>${escapeHtml(title)}</td>
          <td>${Number(row.points || 0).toLocaleString()}<br><span class="muted">rows ${Number(row.rows || 0).toLocaleString()}</span></td>
          <td>${probMaybe(row.ece)}<br><span class="muted">Brier ${probMaybe(row.brier)}</span></td>
          <td>${pctMaybe(row.avg_pred, 1)}</td>
          <td>${pctMaybe(row.empirical, 1)}</td>
          <td class="${eceBiasClass(bias)}">${bias >= 0 ? "+" : ""}${pctMaybe(bias, 1)}<br><span class="muted">${eceBiasText(row.bias_label)}</span></td>
        </tr>`;
      }).join("");
    }

    function gainClass(value) {
      const n = Number(value || 0);
      if (n > 0.0001) return "pos";
      if (n < -0.0001) return "neg";
      return "zero";
    }

    function renderCecOverall(cec) {
      const row = ((cec || {}).overall || {});
      const body = $("range-cec-overall-body");
      if (!row.count) {
        body.innerHTML = '<tr><td colspan="6" class="muted">暂无 CEC 接入样本</td></tr>';
        return;
      }
      const nllGain = Number(row.nll_gain || 0);
      const eceGain = Number(row.ece_gain || 0);
      body.innerHTML = `<tr>
        <td>overall<br><span class="muted">${row.winner === "cec" ? "CEC 更优" : (row.winner === "raw" ? "Raw 更优" : "接近")}</span></td>
        <td>${Number(row.count || 0).toLocaleString()}<br><span class="muted">${pctMaybe(row.positive_rate)} 改善</span></td>
        <td>CEC ${probMaybe(row.avg_cec_prob)}<br><span class="muted">Raw ${probMaybe(row.avg_raw_prob)} Δ${probMaybe(row.avg_prob_delta)}</span></td>
        <td>CEC ${probMaybe(row.cec_nll)}<br><span class="${gainClass(nllGain)}">Gain ${nllGain >= 0 ? "+" : ""}${probMaybe(nllGain)}</span></td>
        <td>CEC ${probMaybe(row.cec_ece)}<br><span class="${gainClass(eceGain)}">Gain ${eceGain >= 0 ? "+" : ""}${probMaybe(eceGain)}</span></td>
        <td>CEC ${pctMaybe(row.cec_top1)}<br><span class="muted">Raw ${pctMaybe(row.raw_top1)}</span></td>
      </tr>`;
    }

    function renderCecRows(bodyId, rows, emptyText) {
      const body = $(bodyId);
      if (!rows || !rows.length) {
        body.innerHTML = `<tr><td colspan="6" class="muted">${escapeHtml(emptyText || "暂无 CEC 接入分析")}</td></tr>`;
        return;
      }
      body.innerHTML = rows.map((row) => {
        const nllGain = Number(row.nll_gain || 0);
        const eceGain = Number(row.ece_gain || 0);
        const title = row.source ? `${row.source}: ${row.key || "-"}` : (row.key || "-");
        return `<tr>
          <td>${escapeHtml(title)}</td>
          <td>${Number(row.count || 0).toLocaleString()}<br><span class="muted">${pctMaybe(row.positive_rate)} 改善</span></td>
          <td>CEC ${probMaybe(row.avg_cec_prob)}<br><span class="muted">Raw ${probMaybe(row.avg_raw_prob)}</span></td>
          <td class="${gainClass(nllGain)}">${nllGain >= 0 ? "+" : ""}${probMaybe(nllGain)}<br><span class="muted">Raw ${probMaybe(row.raw_nll)}</span></td>
          <td class="${gainClass(eceGain)}">${eceGain >= 0 ? "+" : ""}${probMaybe(eceGain)}<br><span class="muted">Raw ${probMaybe(row.raw_ece)}</span></td>
          <td>${row.winner === "cec" ? "CEC" : (row.winner === "raw" ? "Raw" : "接近")}<br><span class="muted">rel ${pctMaybe(row.avg_reliability)}</span></td>
        </tr>`;
      }).join("");
    }

    function renderRangeExamples(examples) {
      const rows = [
        ...((examples && examples.improved) || []).map((item) => ({...item, side: "改善"})),
        ...((examples && examples.worse) || []).map((item) => ({...item, side: "变差"})),
      ].slice(0, 20);
      if (!rows.length) {
        $("range-example-body").innerHTML = '<tr><td colspan="6" class="muted">暂无样例</td></tr>';
        return;
      }
      $("range-example-body").innerHTML = rows.map((item) => {
        const delta = Number(item.delta_nll || 0);
        const deltaText = `${delta > 0 ? "+" : ""}${delta.toFixed(4)}`;
        const deltaCls = delta > 0 ? "pos" : (delta < 0 ? "neg" : "zero");
        return `<tr>
          <td>${item.side}</td>
          <td>${item.hand_id ? `第 ${escapeHtml(item.hand_id)} 手` : "-"}<br><span class="muted">${escapeHtml(item.trigger || "-")}</span></td>
          <td>${streetText(item.street)}</td>
          <td>${escapeHtml(item.player || "-")}</td>
          <td>${cardsHtml(item.actual_cards)}<br><span class="muted">${escapeHtml(item.actual_combo || item.actual_bucket || "-")}</span></td>
          <td>Bayes ${probMaybe(item.bayes_combo_prob)} / ${probMaybe(item.nll_bayes)}<br><span class="${deltaCls}">静态 ${probMaybe(item.static_combo_prob)} / ${probMaybe(item.nll_static)} Δ${deltaText}</span></td>
        </tr>`;
      }).join("");
    }

    function renderRangeAnalysis(data) {
      const summary = data.summary || {};
      $("range-count").textContent = Number(summary.count || 0).toLocaleString();
      $("range-hands").textContent = Number(summary.hands || 0).toLocaleString();
      $("range-pf-better").textContent = Number(summary.improved || 0).toLocaleString();
      $("range-g5-better").textContent = Number(summary.worse || 0).toLocaleString();
      $("range-ece").textContent = summary.bucket_ece !== null && summary.bucket_ece !== undefined
        ? Number(summary.bucket_ece).toFixed(4)
        : "-";
      $("range-top-acc").textContent = pctMaybe(summary.top_bucket_accuracy, 1);
      const cecOverall = ((data.cec_integration || {}).overall || {});
      $("range-cec-nll-gain").textContent = cecOverall.nll_gain !== null && cecOverall.nll_gain !== undefined
        ? `${Number(cecOverall.nll_gain) >= 0 ? "+" : ""}${Number(cecOverall.nll_gain).toFixed(4)}`
        : "-";
      $("range-cec-nll-gain").className = gainClass(cecOverall.nll_gain);
      $("range-cec-ece-gain").textContent = cecOverall.ece_gain !== null && cecOverall.ece_gain !== undefined
        ? `${Number(cecOverall.ece_gain) >= 0 ? "+" : ""}${Number(cecOverall.ece_gain).toFixed(4)}`
        : "-";
      $("range-cec-ece-gain").className = gainClass(cecOverall.ece_gain);
      $("range-winner").textContent = rangeWinnerText(summary.winner);
      $("range-winner").className = summary.winner === "bayes" ? "pos" : (summary.winner === "static" ? "neg" : "zero");
      $("range-meta").textContent = [
        `文件 ${Number(summary.files || 0).toLocaleString()}`,
        `采集行 ${Number(summary.rows || 0).toLocaleString()}`,
        summary.skipped ? `跳过 ${Number(summary.skipped).toLocaleString()}` : "",
        summary.bucket_ece !== null && summary.bucket_ece !== undefined ? `Bucket ECE ${Number(summary.bucket_ece).toFixed(4)}` : "",
        summary.bad_lines ? `坏行 ${Number(summary.bad_lines).toLocaleString()}` : "",
      ].filter(Boolean).join("  ·  ");
      const conclusion = data.conclusion || [];
      $("range-conclusion").className = conclusion.length ? "range-conclusion" : "range-conclusion muted";
      $("range-conclusion").innerHTML = conclusion.length
        ? conclusion.map((line) => `<div>${escapeHtml(line)}</div>`).join("")
        : "暂无分析";
      renderRangeTable("range-street-body", data.by_street || []);
      renderRangeTable("range-category-body", data.by_category || []);
      renderRangeTable("range-player-body", data.by_player || []);
      renderEceBins(data.calibration || {});
      renderEceRows("range-ece-bucket-body", ((data.calibration || {}).by_bucket || []), "暂无 bucket 校准分析");
      renderEceRows("range-ece-hotspot-body", ((data.calibration || {}).hotspots || []), "暂无校准热点");
      renderCecOverall(data.cec_integration || {});
      renderCecRows("range-cec-hotspot-body", ((data.cec_integration || {}).hotspots || []), "暂无 CEC 接入热点");
      renderRangeExamples(data.examples || {});
    }

    async function waitRangeAnalysisJob(initialJob) {
      let job = initialJob || {};
      while (true) {
        if (job.status === "done" && job.result) {
          return job.result;
        }
        if (job.status === "error") {
          throw new Error(job.error || "校准分析任务失败");
        }
        const elapsed = job.started_at ? Math.max(0, (Date.now() / 1000) - Number(job.started_at)) : 0;
        setRangeNotice(`校准分析运行中... ${elapsed.toFixed(0)}s`, "warn");
        await sleep(1000);
        const status = await api("/api/range/compare/status");
        job = status.job || {};
        if (!job.running && job.status !== "done" && job.status !== "error") {
          throw new Error("校准分析任务没有运行");
        }
      }
    }

    async function runRangeAnalysis() {
      $("range-run-btn").disabled = true;
      setRangeNotice("正在启动独立进程分析 NLL / CEC / CEC 接入...", "warn");
      try {
        const started = await api("/api/range/compare", {method: "POST"});
        const data = started.summary ? started : await waitRangeAnalysisJob(started.job || {});
        renderRangeAnalysis(data);
        setRangeNotice("分析完成", "warn");
      } catch (err) {
        setRangeNotice(err.message);
      } finally {
        $("range-run-btn").disabled = false;
      }
    }

    function botSettingsPayload() {
      return {
        profit_lock_bb: Number($("bot-profit-lock-bb").value),
        decision_engine: $("bot-decision-engine").value || "local",
        preflop_sticky_pool_adjust: $("bot-preflop-sticky-pool-adjust").checked,
      };
    }

    function renderStatus(status) {
      const runtime = status.runtime;
      const running = status.job.running;
      const connected = runtime.session_state === "connected";
      $("session-dot").className = `dot ${runtime.session_state === "connected" ? "on" : ""}`;
      $("session-text").textContent = `WSS ${runtime.session_state}`;
      $("job-dot").className = `dot ${running ? "run" : ""}`;
      $("job-text").textContent = running ? "任务运行中" : "任务空闲";
      $("web-url").textContent = (runtime.web_urls && runtime.web_urls.length)
        ? runtime.web_urls.join("  ")
        : (runtime.web_url || "");
      $("start-btn").disabled = running || !connected;
      $("stop-btn").disabled = !running;
      if (!connected) {
        setNotice("WSS 未连接：先让设备连上 proxy，再启动彩球任务。", "warn");
      } else {
        setNotice("");
      }
      const record = currentRecord(status);
      renderRecord(record);
      renderBotSettings(runtime.bot_settings);
      renderDashboard(runtime.bot_dashboard);
    }

    function renderRecord(record) {
      const summary = record && record.summary ? record.summary : {};
      $("m-played").textContent = Number(summary.played || 0).toLocaleString();
      $("m-cycles").textContent = Number(summary.profit_cycles || 0).toLocaleString();
      $("m-bet").textContent = Number(summary.total_bet || 0).toLocaleString();
      $("m-return").textContent = Number(summary.total_return || 0).toLocaleString();
      $("m-net").textContent = signed(summary.net_profit);
      $("m-net").className = moneyClass(summary.net_profit);

      const rows = record && Array.isArray(record.rounds) ? record.rounds.slice().reverse() : [];
      if (rows.length === 0) {
        $("rounds-body").innerHTML = '<tr><td colspan="10" class="muted">暂无记录</td></tr>';
        return;
      }
      $("rounds-body").innerHTML = rows.map((round) => {
        const ids = (round.ids || []).map(swatch).join("");
        const counts = (round.color_counts_after || [])
          .map((item) => `${colorName(item)}:${item.count}`)
          .join(" ");
        const pick = round.selected || {};
        const scope = pickScopeText(pick.scope);
        const reason = pickReasonText(pick.reason);
        return `<tr>
          <td>${round.index}</td>
          <td>${round.cycle}</td>
          <td>${round.attempt}</td>
          <td>${swatch({id: pick.id, name: pick.name})}<span class="muted">${scope} ${reason}</span></td>
          <td>${Number(round.stake || 0).toLocaleString()}</td>
          <td>${ids || "-"}</td>
          <td class="${moneyClass(round.net_profit)}">${signed(round.net_profit)}</td>
          <td class="${moneyClass(round.cycle_net)}">${signed(round.cycle_net)}</td>
          <td class="${moneyClass(round.total_net)}">${signed(round.total_net)}</td>
          <td class="muted">${counts}</td>
        </tr>`;
      }).join("");
    }

    function renderHistory(records, summary = {}) {
      renderHistorySummary(summary);
      if (!records.length) {
        $("history").textContent = "暂无记录";
        return;
      }
      $("history").className = "history";
      $("history").innerHTML = records.map((record) => {
        const s = record.summary || {};
        return `<div class="history-item">
          <div>${record.started_at || "-"}<br><span class="muted">${record.status || "-"}</span></div>
          <div>局数 ${s.played || 0}</div>
          <div>投入 ${Number(s.total_bet || 0).toLocaleString()}</div>
          <div>派彩 ${Number(s.total_return || 0).toLocaleString()}</div>
          <div class="${moneyClass(s.net_profit)}">盈亏 ${signed(s.net_profit)}</div>
        </div>`;
      }).join("");
    }

    function renderHistorySummary(summary = {}) {
      $("h-records").textContent = Number(summary.records || 0).toLocaleString();
      $("h-played").textContent = Number(summary.played || 0).toLocaleString();
      $("h-bet").textContent = Number(summary.total_bet || 0).toLocaleString();
      $("h-return").textContent = Number(summary.total_return || 0).toLocaleString();
      $("h-net").textContent = signed(summary.net_profit);
      $("h-net").className = moneyClass(summary.net_profit);
    }

    function resultText(hand) {
      if (!hand.complete) return "未结束";
      if (hand.pnl > 0) return `盈利 ${signed(hand.pnl_bb)}bb`;
      if (hand.pnl < 0) return `亏损 ${signed(hand.pnl_bb)}bb`;
      return "持平";
    }

    function streetText(street) {
      return {
        preflop: "翻前",
        flop: "翻牌",
        turn: "转牌",
        river: "河牌",
      }[street] || street || "-";
    }

    function actionText(action) {
      return {
        fold: "弃牌",
        check: "过牌",
        call: "跟注",
        raise: "加注",
        bet: "下注",
        jam: "全下",
      }[action] || action || "-";
    }

    function syncHandFilterOptions(data) {
      if (!handFilterOptionsReady) {
        const posSelect = $("hand-position");
        const bbSelect = $("hand-bb");
        const selectedPos = posSelect.value;
        const selectedBb = bbSelect.value;
        posSelect.innerHTML = '<option value="all">全部</option>' +
          (data.positions || []).map((pos) => `<option value="${escapeHtml(pos)}">${escapeHtml(pos)}</option>`).join("");
        bbSelect.innerHTML = '<option value="all">全部</option>' +
          (data.bb_k_values || []).map((bb) => `<option value="${bb}">${bb}k</option>`).join("");
        posSelect.value = selectedPos || "all";
        bbSelect.value = selectedBb || "all";
        handFilterOptionsReady = true;
      }
    }

    function renderHands(data) {
      syncHandFilterOptions(data);
      $("hands-total").textContent = Number(data.total || 0).toLocaleString();
      $("hands-count").textContent = Number(data.count || 0).toLocaleString();
      $("hands-log").textContent = (data.log_path || "").split("/").slice(-1)[0] || "-";
      handPage = Number(data.page || 1);
      handPageSize = Number(data.page_size || handPageSize || 30);
      $("hands-page-size").value = String(handPageSize);
      $("hands-page-info").textContent = `${Number(data.page_start || 0).toLocaleString()}-${Number(data.page_end || 0).toLocaleString()} / ${Number(data.count || 0).toLocaleString()}，第 ${handPage} / ${Number(data.page_count || 1)} 页`;
      $("hands-prev-btn").disabled = !data.has_prev;
      $("hands-next-btn").disabled = !data.has_next;
      const hands = data.hands || [];
      if (!hands.length) {
        $("hands-body").innerHTML = '<tr><td colspan="10" class="muted">暂无对局</td></tr>';
        selectedHandId = null;
        $("hands-selected").textContent = "-";
        $("hands-lines").textContent = "-";
        $("hand-detail-title").textContent = "对局详情";
        $("hand-detail-meta").textContent = "选择一手查看完整日志";
        $("hand-detail").textContent = "暂无详情";
        return;
      }
      if (!selectedHandId || !hands.some((h) => h.id === selectedHandId)) {
        selectedHandId = hands[0].id;
      }
      $("hands-body").innerHTML = hands.map((hand) => {
        const rowClass = hand.id === selectedHandId ? "clickable active" : "clickable";
        const winner = hand.winner_text || "-";
        const combo = hand.hero_combo ? `<br><span class="muted">我: ${escapeHtml(hand.hero_combo)}</span>` : "";
        return `<tr class="${rowClass}" data-hand-id="${hand.id}">
          <td>第 ${hand.hand_no} 手<br><span class="muted">#${hand.seq}</span></td>
          <td>${escapeHtml(hand.time || "-")}</td>
          <td>${escapeHtml(hand.position || "-")}</td>
          <td>${hand.bb_k || "-"}k</td>
          <td>${cardsHtml(hand.hole_cards)}</td>
          <td>${cardsHtml(hand.board)}</td>
          <td>${hand.vpip ? "是" : "否"}</td>
          <td class="${handMoneyClass(hand.pnl)}">${resultText(hand)}</td>
          <td>${streetText(hand.final_street)} ${actionText(hand.final_action)}</td>
          <td>${escapeHtml(winner)}${combo}</td>
        </tr>`;
      }).join("");
      document.querySelectorAll("#hands-body tr[data-hand-id]").forEach((row) => {
        row.addEventListener("click", () => selectHand(Number(row.dataset.handId)));
      });
      if (selectedHandId) {
        selectHand(selectedHandId, false);
      }
    }

    async function refreshHands() {
      if (handsLoading) return;
      handsLoading = true;
      const prevDisabled = $("hands-prev-btn").disabled;
      const nextDisabled = $("hands-next-btn").disabled;
      let rendered = false;
      $("hands-prev-btn").disabled = true;
      $("hands-next-btn").disabled = true;
      const params = new URLSearchParams({
        hand_no: $("hand-no").value.trim(),
        board: $("hand-board").value.trim(),
        position: $("hand-position").value || "all",
        vpip: $("hand-vpip").value || "all",
        result: $("hand-result").value || "all",
        bb_k: $("hand-bb").value || "all",
        page: String(handPage),
        page_size: String(handPageSize),
      });
      try {
        const data = await api(`/api/hands?${params.toString()}`);
        renderHands(data);
        rendered = true;
      } finally {
        handsLoading = false;
        if (!rendered) {
          $("hands-prev-btn").disabled = prevDisabled;
          $("hands-next-btn").disabled = nextDisabled;
        }
      }
    }

    async function selectHand(id, refreshList = true) {
      selectedHandId = id;
      if (refreshList) {
        document.querySelectorAll("#hands-body tr[data-hand-id]").forEach((row) => {
          row.classList.toggle("active", Number(row.dataset.handId) === id);
        });
      }
      const data = await api(`/api/hand?id=${encodeURIComponent(id)}`);
      const hand = data.hand || {};
      $("hands-selected").textContent = hand.hand_no ? `第 ${hand.hand_no} 手` : "-";
      $("hands-lines").textContent = hand.start_line ? `${hand.start_line}-${hand.end_line}` : "-";
      $("hand-detail-title").textContent = hand.hand_no ? `第 ${hand.hand_no} 手` : "对局详情";
      $("hand-detail-meta").textContent = [
        hand.position || "-",
        hand.bb_k ? `${hand.bb_k}k` : "",
        resultText(hand),
      ].filter(Boolean).join("  ·  ");
      $("hand-detail").innerHTML = colorizeLog(data.log_text || "");
    }

    async function refresh() {
      try {
        const status = await api("/api/status");
        renderStatus(status);
        const history = await api("/api/records?limit=12");
        renderHistory(history.records || [], history.summary || {});
      } catch (err) {
        setNotice(err.message);
      }
    }

    async function refreshBotSettings() {
      const data = await api("/api/bot/settings");
      renderBotSettings(data.settings);
    }

    $("run-form").addEventListener("submit", async (event) => {
      event.preventDefault();
      try {
        await api("/api/color/run", {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify(formPayload()),
        });
        setNotice("彩球任务已启动", "warn");
        await refresh();
      } catch (err) {
        setNotice(err.message);
      }
    });
    $("stop-btn").addEventListener("click", async () => {
      try {
        await api("/api/color/stop", {method: "POST"});
        setNotice("已请求停止任务", "warn");
        await refresh();
      } catch (err) {
        setNotice(err.message);
      }
    });
    $("bot-settings-form").addEventListener("submit", async (event) => {
      event.preventDefault();
      try {
        const data = await api("/api/bot/settings", {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify(botSettingsPayload()),
        });
        renderBotSettings(data.settings);
        setBotNotice("运行参数已保存", "warn");
      } catch (err) {
        setBotNotice(err.message);
      }
    });
    $("bot-refresh-btn").addEventListener("click", () => {
      refreshBotSettings()
        .then(() => setBotNotice("运行参数已刷新", "warn"))
        .catch((err) => setBotNotice(err.message));
    });
    $("refresh-btn").addEventListener("click", refresh);
    $("range-run-btn").addEventListener("click", () => {
      runRangeAnalysis();
    });
    $("hands-refresh-btn").addEventListener("click", () => {
      handFilterOptionsReady = false;
      refreshHands().catch((err) => setNotice(err.message));
    });
    $("hands-prev-btn").addEventListener("click", () => {
      if (handsLoading) return;
      if (handPage <= 1) return;
      handPage -= 1;
      selectedHandId = null;
      refreshHands().catch((err) => setNotice(err.message));
    });
    $("hands-next-btn").addEventListener("click", () => {
      if (handsLoading) return;
      handPage += 1;
      selectedHandId = null;
      refreshHands().catch((err) => setNotice(err.message));
    });
    $("hands-page-size").addEventListener("change", () => {
      handPageSize = Number($("hands-page-size").value || 30);
      handPage = 1;
      selectedHandId = null;
      refreshHands().catch((err) => setNotice(err.message));
    });
    ["hand-position", "hand-vpip", "hand-result", "hand-bb"].forEach((id) => {
      $(id).addEventListener("change", () => {
        handPage = 1;
        selectedHandId = null;
        refreshHands().catch((err) => setNotice(err.message));
      });
    });
    ["hand-no", "hand-board"].forEach((id) => {
      $(id).addEventListener("input", () => {
        handPage = 1;
        selectedHandId = null;
        refreshHands().catch((err) => setNotice(err.message));
      });
    });
    document.querySelectorAll(".tab-btn").forEach((btn) => {
      btn.addEventListener("click", () => {
        activeTab = btn.dataset.tab;
        document.querySelectorAll(".tab-btn").forEach((item) => {
          item.classList.toggle("active", item === btn);
        });
        document.querySelectorAll(".tab-panel").forEach((panel) => {
          panel.classList.toggle("active", panel.id === `tab-${activeTab}`);
        });
        if (activeTab === "hands") {
          refreshHands().catch((err) => setNotice(err.message));
        } else if (activeTab === "bot") {
          refreshBotSettings().catch((err) => setBotNotice(err.message));
        } else if (activeTab === "live") {
          refreshLive();
        }
      });
    });
    refresh();
    refreshHands().catch(() => {});
    refreshLive();
    setInterval(refresh, 1000);
    setInterval(() => {
      if (activeTab === "live") refreshLive();
    }, 700);
    setInterval(() => {
      if (activeTab === "hands") {
        refreshHands().catch((err) => setNotice(err.message));
      }
    }, 4000);
  
