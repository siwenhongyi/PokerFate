from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import Any
from urllib.parse import parse_qs, urlsplit

from pf_entertainment.color_strategy import ColorMartingaleConfig
from pf_entertainment.records import JsonRecordStore


@dataclass
class _HttpRequest:
    method: str
    target: str
    path: str
    query: dict[str, list[str]]
    headers: dict[str, str]
    body: bytes


class EntertainmentWebServer:
    def __init__(
        self,
        *,
        runtime: Any,
        host: str = "127.0.0.1",
        port: int = 9022,
        store: JsonRecordStore | None = None,
    ) -> None:
        self.runtime = runtime
        self.host = host
        self.port = port
        self.store = store or JsonRecordStore()
        self.log = runtime.log
        self._server: asyncio.AbstractServer | None = None
        self._task: asyncio.Task | None = None
        self._stop_event: asyncio.Event | None = None
        self._current_record: dict | None = None
        self._last_record: dict | None = None

    async def start(self) -> None:
        if self._server is not None:
            return
        self._server = await asyncio.start_server(
            self._handle_client,
            self.host,
            self.port,
        )
        if self.port == 0 and self._server.sockets:
            self.port = int(self._server.sockets[0].getsockname()[1])
        self.log.info("[娱乐游戏] Web 已启动 http://%s:%d", self.host, self.port)

    async def _handle_client(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        try:
            request = await self._read_request(reader)
            status, headers, body = await self._route(request)
        except Exception as exc:
            self.log.exception("[娱乐游戏] Web 请求失败")
            status, headers, body = self._json_response(
                {"ok": False, "error": str(exc)},
                status=500,
            )
        try:
            writer.write(self._build_response(status, headers, body))
            await writer.drain()
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass

    async def _read_request(self, reader: asyncio.StreamReader) -> _HttpRequest:
        header_bytes = await reader.readuntil(b"\r\n\r\n")
        header_text = header_bytes.decode("iso-8859-1")
        lines = header_text.split("\r\n")
        request_line = lines[0].split()
        if len(request_line) < 2:
            raise ValueError("bad request line")
        method = request_line[0].upper()
        target = request_line[1]
        headers: dict[str, str] = {}
        for line in lines[1:]:
            if not line or ":" not in line:
                continue
            key, value = line.split(":", 1)
            headers[key.strip().lower()] = value.strip()

        content_length = int(headers.get("content-length") or 0)
        body = await reader.readexactly(content_length) if content_length > 0 else b""
        parsed = urlsplit(target)
        return _HttpRequest(
            method=method,
            target=target,
            path=parsed.path or "/",
            query=parse_qs(parsed.query),
            headers=headers,
            body=body,
        )

    async def _route(self, request: _HttpRequest) -> tuple[int, dict[str, str], bytes]:
        if request.method == "GET" and request.path == "/":
            return self._html_response(INDEX_HTML)
        if request.method == "GET" and request.path == "/api/status":
            return self._json_response(
                {
                    "ok": True,
                    "runtime": self.runtime.status_data(),
                    "job": self._job_payload(),
                }
            )
        if request.method == "GET" and request.path == "/api/records":
            limit = self._int_query(request, "limit", 20)
            return self._json_response(
                {
                    "ok": True,
                    "records": self.store.recent(limit),
                    "summary": self.store.summary(),
                }
            )
        if request.method == "POST" and request.path == "/api/color/run":
            return await self._start_color_run(request)
        if request.method == "POST" and request.path == "/api/color/stop":
            return self._stop_color_run()
        return self._json_response({"ok": False, "error": "not found"}, status=404)

    async def _start_color_run(
        self,
        request: _HttpRequest,
    ) -> tuple[int, dict[str, str], bytes]:
        if self._task is not None and not self._task.done():
            return self._json_response(
                {"ok": False, "error": "color job already running", "job": self._job_payload()},
                status=409,
            )
        runtime_status = self.runtime.status_data()
        if runtime_status.get("session_state") != "connected":
            return self._json_response(
                {
                    "ok": False,
                    "error": "当前没有 WSS 会话，先让设备连上 proxy 后再启动彩球任务",
                    "runtime": runtime_status,
                    "job": self._job_payload(),
                },
                status=409,
            )
        try:
            payload = json.loads(request.body.decode("utf-8") or "{}")
            if not isinstance(payload, dict):
                raise ValueError("JSON body must be an object")
            config = ColorMartingaleConfig.from_mapping(payload)
        except Exception as exc:
            return self._json_response({"ok": False, "error": str(exc)}, status=400)

        self._current_record = {
            "status": "starting",
            "params": config.to_dict(),
            "rounds": [],
            "summary": {
                "played": 0,
                "profit_cycles": 0,
                "total_bet": 0,
                "total_return": 0,
                "net_profit": 0,
                "color_counts": [],
            },
        }
        self._stop_event = asyncio.Event()
        self._task = asyncio.create_task(self._run_color_job(config, self._stop_event))
        return self._json_response({"ok": True, "job": self._job_payload()}, status=202)

    def _stop_color_run(self) -> tuple[int, dict[str, str], bytes]:
        if self._task is None or self._task.done() or self._stop_event is None:
            return self._json_response({"ok": False, "error": "no running job"}, status=409)
        self._stop_event.set()
        return self._json_response({"ok": True, "job": self._job_payload()})

    async def _run_color_job(
        self,
        config: ColorMartingaleConfig,
        stop_event: asyncio.Event,
    ) -> None:
        record: dict | None = None
        try:
            record = await self.runtime.run_color_martingale(
                config,
                progress=self._set_current_record,
                stop_event=stop_event,
            )
        except Exception as exc:
            self.log.exception("[娱乐游戏] 彩球 Web 任务失败")
            record = self._current_record or {
                "type": "color_martingale_least_seen",
                "params": config.to_dict(),
                "rounds": [],
                "summary": {},
            }
            record["status"] = "error"
            record["error"] = str(exc)
        finally:
            self._current_record = record
            self._last_record = record
            if record is not None:
                try:
                    self.store.append(record)
                except Exception:
                    self.log.exception("[娱乐游戏] 彩球记录写入失败")
            self._stop_event = None

    def _set_current_record(self, record: dict) -> None:
        self._current_record = record

    def _job_payload(self) -> dict:
        running = self._task is not None and not self._task.done()
        return {
            "running": running,
            "current": self._current_record,
            "last": self._last_record,
        }

    def _int_query(self, request: _HttpRequest, name: str, default: int) -> int:
        values = request.query.get(name)
        if not values:
            return default
        try:
            return int(values[0])
        except ValueError:
            return default

    def _html_response(self, html: str) -> tuple[int, dict[str, str], bytes]:
        return (
            200,
            {
                "Content-Type": "text/html; charset=utf-8",
                "Cache-Control": "no-store",
            },
            html.encode("utf-8"),
        )

    def _json_response(
        self,
        payload: dict,
        *,
        status: int = 200,
    ) -> tuple[int, dict[str, str], bytes]:
        return (
            status,
            {
                "Content-Type": "application/json; charset=utf-8",
                "Cache-Control": "no-store",
            },
            json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        )

    def _build_response(
        self,
        status: int,
        headers: dict[str, str],
        body: bytes,
    ) -> bytes:
        reason = {
            200: "OK",
            202: "Accepted",
            400: "Bad Request",
            404: "Not Found",
            409: "Conflict",
            500: "Internal Server Error",
        }.get(status, "OK")
        base_headers = {
            "Content-Length": str(len(body)),
            "Connection": "close",
        }
        base_headers.update(headers)
        header_lines = [f"HTTP/1.1 {status} {reason}"]
        header_lines.extend(f"{key}: {value}" for key, value in base_headers.items())
        return ("\r\n".join(header_lines) + "\r\n\r\n").encode("utf-8") + body


INDEX_HTML = r"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>PokerFate 小游戏</title>
  <style>
    :root {
      color-scheme: light;
      --bg: #f5f7fa;
      --panel: #ffffff;
      --text: #1d2430;
      --muted: #667085;
      --line: #d8dee8;
      --brand: #1677ff;
      --brand-dark: #0f5ec7;
      --danger: #c24136;
      --ok: #188052;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font: 14px/1.45 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }
    header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      padding: 18px 24px;
      border-bottom: 1px solid var(--line);
      background: #ffffff;
      position: sticky;
      top: 0;
      z-index: 2;
    }
    h1 { font-size: 20px; margin: 0; letter-spacing: 0; }
    main { max-width: 1280px; margin: 0 auto; padding: 20px 24px 40px; }
    section {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 16px;
      margin-bottom: 16px;
    }
    .status { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; color: var(--muted); }
    .dot { width: 9px; height: 9px; border-radius: 50%; background: #a0a7b4; display: inline-block; }
    .dot.on { background: var(--ok); }
    .dot.run { background: var(--brand); }
    form {
      display: grid;
      grid-template-columns: repeat(6, minmax(120px, 1fr));
      gap: 12px;
      align-items: end;
    }
    label { color: var(--muted); font-size: 12px; display: grid; gap: 6px; }
    input, select {
      height: 36px;
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 0 10px;
      color: var(--text);
      background: #fff;
      font: inherit;
    }
    button {
      height: 36px;
      border: 0;
      border-radius: 6px;
      padding: 0 14px;
      color: #fff;
      background: var(--brand);
      font: inherit;
      cursor: pointer;
      white-space: nowrap;
    }
    button:hover { background: var(--brand-dark); }
    button.secondary { background: #3f4756; }
    button.danger { background: var(--danger); }
    button:disabled { opacity: .5; cursor: not-allowed; }
    .metrics {
      display: grid;
      grid-template-columns: repeat(5, minmax(120px, 1fr));
      gap: 10px;
      margin-top: 14px;
    }
    .metric { border-left: 3px solid var(--line); padding-left: 10px; min-width: 0; }
    .metric b { display: block; font-size: 18px; overflow-wrap: anywhere; }
    .metric span { color: var(--muted); font-size: 12px; }
    .notice {
      display: none;
      margin-top: 12px;
      padding: 10px 12px;
      border-radius: 6px;
      border: 1px solid #f2c6c1;
      background: #fff4f2;
      color: var(--danger);
    }
    .notice.show { display: block; }
    .notice.warn {
      border-color: #f0d28a;
      background: #fff8e6;
      color: #835c0b;
    }
    .pos { color: var(--ok); }
    .neg { color: var(--danger); }
    .table-wrap { overflow: auto; border: 1px solid var(--line); border-radius: 8px; }
    table { width: 100%; border-collapse: collapse; min-width: 1040px; background: #fff; }
    th, td { padding: 9px 10px; border-bottom: 1px solid var(--line); text-align: left; vertical-align: middle; }
    th { font-size: 12px; color: var(--muted); background: #f8fafc; position: sticky; top: 0; }
    tr:last-child td { border-bottom: 0; }
    .swatch { display: inline-flex; align-items: center; gap: 6px; margin-right: 5px; }
    .ball { width: 12px; height: 12px; border-radius: 50%; display: inline-block; border: 1px solid rgba(0,0,0,.12); }
    .c101 { background: #f4c542; }
    .c102 { background: #98a2b3; }
    .c103 { background: #9b5de5; }
    .c104 { background: #3b82f6; }
    .c105 { background: #ef4444; }
    .c106 { background: #22c55e; }
    .muted { color: var(--muted); }
    .history { display: grid; gap: 8px; }
    .history-item {
      display: grid;
      grid-template-columns: 1.3fr .8fr .8fr .8fr .8fr;
      gap: 10px;
      padding: 10px 0;
      border-bottom: 1px solid var(--line);
    }
    .history-item:last-child { border-bottom: 0; }
    @media (max-width: 860px) {
      header { align-items: flex-start; flex-direction: column; padding: 14px 16px; }
      main { padding: 14px 16px 28px; }
      form { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      .metrics { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      .history-item { grid-template-columns: 1fr 1fr; }
    }
  </style>
</head>
<body>
  <header>
    <h1>小游戏控制台</h1>
    <div class="status">
      <span id="session-dot" class="dot"></span><span id="session-text">WSS -</span>
      <span id="job-dot" class="dot"></span><span id="job-text">任务 -</span>
      <span id="web-url"></span>
    </div>
  </header>
  <main>
    <section>
      <form id="run-form">
        <label>起始筹码
          <input name="base_bet" type="number" min="1" step="1" value="1000">
        </label>
        <label>最大筹码
          <input name="max_bet" type="number" min="1" step="1" value="100000">
        </label>
        <label>倍投倍率
          <input name="multiplier" type="number" min="2" step="1" value="2">
        </label>
        <label>循环次数
          <input name="cycles" type="number" min="1" step="1" value="1">
        </label>
        <label>选球模式
          <select name="selection_mode">
            <option value="cycle" selected>每个循环固定</option>
            <option value="bet">每次下注重选</option>
          </select>
        </label>
        <label>等级
          <input name="lvl" type="number" min="1" max="5" step="1" value="1">
        </label>
        <label>间隔秒
          <input name="delay" type="number" min="0" step="0.1" value="1.5">
        </label>
        <label>超时秒
          <input name="timeout" type="number" min="1" step="0.5" value="20">
        </label>
        <label>from_game_type
          <input name="from_game_type" type="number" step="1" value="0">
        </label>
        <label>room_id
          <input name="room_id" type="number" min="0" step="1" value="0">
        </label>
        <button id="start-btn" type="submit">开始彩球</button>
        <button id="stop-btn" class="danger" type="button">停止</button>
        <button id="refresh-btn" class="secondary" type="button">刷新</button>
      </form>
      <div id="notice" class="notice"></div>
      <div class="metrics">
        <div class="metric"><span>局数</span><b id="m-played">0</b></div>
        <div class="metric"><span>盈利循环</span><b id="m-cycles">0</b></div>
        <div class="metric"><span>总投入</span><b id="m-bet">0</b></div>
        <div class="metric"><span>总派彩</span><b id="m-return">0</b></div>
        <div class="metric"><span>总盈亏</span><b id="m-net">0</b></div>
      </div>
    </section>

    <section>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>#</th>
              <th>循环</th>
              <th>轮次</th>
              <th>选择</th>
              <th>筹码</th>
              <th>开奖结果</th>
              <th>本局盈亏</th>
              <th>循环盈亏</th>
              <th>累计盈亏</th>
              <th>计数</th>
            </tr>
          </thead>
          <tbody id="rounds-body">
            <tr><td colspan="10" class="muted">暂无记录</td></tr>
          </tbody>
        </table>
      </div>
    </section>

    <section>
      <h2 style="font-size:16px;margin:0 0 10px;">历史记录</h2>
      <div class="metrics" style="margin:0 0 12px;">
        <div class="metric"><span>历史次数</span><b id="h-records">0</b></div>
        <div class="metric"><span>历史局数</span><b id="h-played">0</b></div>
        <div class="metric"><span>历史总投入</span><b id="h-bet">0</b></div>
        <div class="metric"><span>历史总派彩</span><b id="h-return">0</b></div>
        <div class="metric"><span>历史总盈亏</span><b id="h-net">0</b></div>
      </div>
      <div id="history" class="history muted">暂无记录</div>
    </section>
  </main>

  <script>
    const $ = (id) => document.getElementById(id);
    const colorName = (item) => item && item.name ? item.name : "-";
    const signed = (n) => {
      const v = Number(n || 0);
      return `${v > 0 ? "+" : ""}${v.toLocaleString()}`;
    };
    const moneyClass = (n) => Number(n || 0) >= 0 ? "pos" : "neg";
    const swatch = (item) => `<span class="swatch"><i class="ball c${item.id}"></i>${colorName(item)}</span>`;

    function formPayload() {
      const payload = {};
      new FormData($("run-form")).forEach((value, key) => {
        payload[key] = value;
      });
      return payload;
    }

    async function api(path, options = {}) {
      const res = await fetch(path, options);
      const data = await res.json();
      if (!res.ok || data.ok === false) {
        throw new Error(data.error || `HTTP ${res.status}`);
      }
      return data;
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
        const scope = pick.scope === "bet" ? "每注" : "循环";
        return `<tr>
          <td>${round.index}</td>
          <td>${round.cycle}</td>
          <td>${round.attempt}</td>
          <td>${swatch({id: pick.id, name: pick.name})}<span class="muted">${scope} ${pick.reason || ""}</span></td>
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
    $("refresh-btn").addEventListener("click", refresh);
    refresh();
    setInterval(refresh, 1000);
  </script>
</body>
</html>
"""
