    const $ = (id) => document.getElementById(id);
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

    const renderLive = window.PFLiveTable.render;

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

    function renderDashboard(data) {
      const d = data || {};
      $("bank-total").textContent = chipsMaybe(d.current_total_chips);
      $("bank-wallet").textContent = chipsMaybe(d.wallet_chips);
      $("bank-table").textContent = chipsMaybe(d.table_chips);
      // Three separate ledgers: settled hands, claimed rewards, side-game rounds.
      const unknown = d.rewards_uncertain ? "（另有待确认）" : "";
      $("bank-delta").textContent = signedMaybe(d.session_delta_chips);
      $("bank-delta").className = handMoneyClass(d.session_delta_chips);
      $("bank-rewards").textContent = chipsMaybe(d.reward_chips || 0) + unknown;
      $("bank-sidegame").textContent = signedMaybe(d.sidegame_net_chips || 0) + unknown;
      $("bank-sidegame").className = handMoneyClass(d.sidegame_net_chips || 0);
      $("bank-last").textContent = timeMaybe(d.last_sample_at);
      $("bank-locks").textContent = Number(d.profit_lock_count || 0).toLocaleString();
      $("bank-rebuys").textContent = `${Number(d.auto_rebuy_count || 0).toLocaleString()} 次`;
      // One number ends a start: its net loss may not pass this (bust rebuys, top-ups and
      // table-switch buy-ins are all checked against it).
      $("bank-losscap").textContent = d.loss_cap_chips
        ? `-${Number(d.loss_cap_chips).toLocaleString()}${d.loss_stop ? "（已停止）" : ""}` : "-";
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

    // Signed difference in percentage points.
    function pointsMaybe(n) {
      if (n === null || n === undefined || Number.isNaN(Number(n))) return "-";
      const value = Number(n) * 100;
      return `${value >= 0 ? "+" : ""}${value.toFixed(1)}`;
    }

    const RANGE_ACTION_TEXT = {
      bet: "下注", raise: "加注", call: "跟注", check: "过牌", board: "发牌后", fold: "弃牌", other: "其他",
    };
    const RANGE_BUCKET_TEXT = {
      nuts: "坚果", strong: "强牌", medium: "中等牌", draw: "听牌", weak_draw: "弱听牌", air: "空气",
    };

    function rangeBiasText(label) {
      if (label === "overconfident") return "预测过高";
      if (label === "underconfident") return "预测过低";
      if (label === "ok") return "接近";
      return "-";
    }

    function rangeBiasClass(label) {
      return label === "overconfident" || label === "underconfident" ? "neg" : "zero";
    }

    function renderRangeCells(rows) {
      const body = $("range-cell-body");
      if (!rows || !rows.length) {
        body.innerHTML = '<tr><td colspan="6" class="muted">暂无足够样本（每格至少 100 行）</td></tr>';
        return;
      }
      body.innerHTML = rows.map((row) => `<tr>
          <td>${streetText(row.street)} ${escapeHtml(RANGE_ACTION_TEXT[row.action] || row.action || "-")}</td>
          <td>${Number(row.rows || 0).toLocaleString()}</td>
          <td>${pctMaybe(row.predicted)}</td>
          <td>${pctMaybe(row.actual)}</td>
          <td class="${rangeBiasClass(row.label)}">${pointsMaybe(row.diff)}<br><span class="muted">± ${(Number(row.se || 0) * 100).toFixed(1)}</span></td>
          <td>${rangeBiasText(row.label)}</td>
        </tr>`).join("");
    }

    function renderRangeBuckets(rows) {
      const body = $("range-bucket-body");
      if (!rows || !rows.length) {
        body.innerHTML = '<tr><td colspan="6" class="muted">暂无样本</td></tr>';
        return;
      }
      body.innerHTML = rows.map((row) => `<tr>
          <td>${escapeHtml(RANGE_BUCKET_TEXT[row.key] || row.key || "-")}</td>
          <td>${Number(row.points || 0).toLocaleString()}</td>
          <td>${pctMaybe(row.avg_pred)}</td>
          <td>${pctMaybe(row.empirical)}</td>
          <td class="${rangeBiasClass(row.bias_label)}">${pointsMaybe(row.bias)}</td>
          <td>${probMaybe(row.ece)}</td>
        </tr>`).join("");
    }

    function renderRangeBins(rows) {
      const body = $("range-bin-body");
      if (!rows || !rows.length) {
        body.innerHTML = '<tr><td colspan="5" class="muted">暂无样本</td></tr>';
        return;
      }
      body.innerHTML = rows.map((row) => `<tr>
          <td>${escapeHtml(row.bin || "-")}</td>
          <td>${Number(row.count || 0).toLocaleString()}</td>
          <td>${pctMaybe(row.avg_pred)}</td>
          <td>${pctMaybe(row.empirical)}</td>
          <td class="${rangeBiasClass(row.bias_label)}">${pointsMaybe(row.gap)}</td>
        </tr>`).join("");
    }

    function renderRangeStreets(rows) {
      const body = $("range-street-body");
      if (!rows || !rows.length) {
        body.innerHTML = '<tr><td colspan="5" class="muted">暂无样本</td></tr>';
        return;
      }
      body.innerHTML = rows.map((row) => {
        const delta = Number(row.avg_delta_nll || 0);
        const deltaCls = delta > 0 ? "pos" : (delta < 0 ? "neg" : "zero");
        return `<tr>
          <td>${streetText(row.key)}</td>
          <td>${Number(row.count || 0).toLocaleString()}</td>
          <td>${pctMaybe(row.positive_rate)}<br><span class="muted">${Number(row.improved || 0).toLocaleString()} 改善 / ${Number(row.worse || 0).toLocaleString()} 变差</span></td>
          <td>${probMaybe(row.avg_bayes_prob)}<br><span class="muted">起手 ${probMaybe(row.avg_static_prob)}</span></td>
          <td class="${deltaCls}">${delta > 0 ? "+" : ""}${delta.toFixed(3)}<br><span class="muted">中位 ${Number(row.median_delta_nll || 0).toFixed(3)}</span></td>
        </tr>`;
      }).join("");
    }

    function renderRangeAnalysis(data) {
      const summary = data.summary || {};
      const calibration = data.calibration || {};
      const has = (value) => value !== null && value !== undefined;
      $("range-count").textContent = Number(summary.rows || 0).toLocaleString();
      $("range-hands").textContent = Number(summary.hands || 0).toLocaleString();
      $("range-ece").textContent = has(summary.bucket_ece) ? Number(summary.bucket_ece).toFixed(4) : "-";
      $("range-strong").textContent = has(summary.strong_mass_predicted)
        ? `${pctMaybe(summary.strong_mass_predicted)} / ${pctMaybe(summary.strong_mass_actual)}`
        : "-";
      const delta = has(summary.avg_delta_nll) ? Number(summary.avg_delta_nll) : null;
      $("range-delta").textContent = delta === null ? "-" : `${delta > 0 ? "+" : ""}${delta.toFixed(3)}`;
      $("range-delta").className = delta === null ? "" : (delta > 0 ? "pos" : (delta < 0 ? "neg" : "zero"));
      $("range-meta").textContent = [
        `文件 ${Number(summary.files || 0).toLocaleString()}`,
        `计入 ${Number(summary.rows || 0).toLocaleString()} 行`,
        `旧版模型 ${Number(summary.older_rows || 0).toLocaleString()} 行未计`,
        `人机 ${Number(summary.robot_rows || 0).toLocaleString()} 行未计`,
        summary.bad_lines ? `坏行 ${Number(summary.bad_lines).toLocaleString()}` : "",
      ].filter(Boolean).join("  ·  ");
      const conclusion = data.conclusion || [];
      $("range-conclusion").className = conclusion.length ? "range-conclusion" : "range-conclusion muted";
      $("range-conclusion").innerHTML = conclusion.length
        ? conclusion.map((line) => `<div>${escapeHtml(line)}</div>`).join("")
        : "暂无分析";
      renderRangeCells(calibration.by_cell || []);
      renderRangeBuckets(calibration.by_bucket || []);
      renderRangeBins((calibration.overall || {}).bins || []);
      renderRangeStreets(data.by_street || []);
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
      setRangeNotice("正在启动独立进程分析...", "warn");
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

    function renderStatus(status) {
      const runtime = status.runtime;
      $("session-dot").className = `dot ${["connected","headless"].includes(runtime.session_state) ? "on" : ""}`;
      $("session-text").textContent = `WSS ${runtime.session_state}`;
      $("web-url").textContent = (runtime.web_urls && runtime.web_urls.length)
        ? runtime.web_urls.join("  ")
        : (runtime.web_url || "");
      renderDashboard(runtime.bot_dashboard);
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
      } catch (err) {
        setNotice(err.message);
      }
    }

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
  
