from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import Any
from urllib.parse import parse_qs, urlsplit

from pf_entertainment.color_strategy import ColorMartingaleConfig
from pf_entertainment.hand_preview import hand_detail_payload, hand_list_payload
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
        if request.method == "GET" and request.path == "/api/hands":
            return self._json_response(
                {
                    "ok": True,
                    **hand_list_payload(
                        position=self._str_query(request, "position", "all"),
                        vpip=self._str_query(request, "vpip", "all"),
                        result=self._str_query(request, "result", "all"),
                        bb_k=self._str_query(request, "bb_k", "all"),
                        page=self._int_query(request, "page", 1),
                        page_size=self._int_query(request, "page_size", 30),
                    ),
                }
            )
        if request.method == "GET" and request.path == "/api/hand":
            hand_id = self._int_query(request, "id", 0)
            try:
                return self._json_response({"ok": True, **hand_detail_payload(hand_id)})
            except KeyError as exc:
                return self._json_response({"ok": False, "error": str(exc)}, status=404)
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

    def _str_query(self, request: _HttpRequest, name: str, default: str = "") -> str:
        values = request.query.get(name)
        if not values:
            return default
        return str(values[0])

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
  <title>PokerFate 控制台</title>
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
    .tabs {
      display: flex;
      gap: 8px;
      margin-bottom: 16px;
      border-bottom: 1px solid var(--line);
    }
    .tab-btn {
      height: 38px;
      border: 1px solid transparent;
      border-bottom: 0;
      border-radius: 8px 8px 0 0;
      padding: 0 16px;
      color: var(--muted);
      background: transparent;
    }
    .tab-btn.active {
      color: var(--text);
      background: #fff;
      border-color: var(--line);
      transform: translateY(1px);
    }
    .tab-panel { display: none; }
    .tab-panel.active { display: block; }
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
    button.tab-btn {
      color: var(--muted);
      background: transparent;
      border: 1px solid transparent;
      border-bottom: 0;
    }
    button.tab-btn:hover { background: #eef4fb; }
    button.tab-btn.active {
      color: var(--text);
      background: #fff;
      border-color: var(--line);
    }
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
    .zero { color: var(--muted); }
    .table-wrap { overflow: auto; border: 1px solid var(--line); border-radius: 8px; }
    table { width: 100%; border-collapse: collapse; min-width: 1040px; background: #fff; }
    th, td { padding: 9px 10px; border-bottom: 1px solid var(--line); text-align: left; vertical-align: middle; }
    th { font-size: 12px; color: var(--muted); background: #f8fafc; position: sticky; top: 0; }
    tr:last-child td { border-bottom: 0; }
    .clickable { cursor: pointer; }
    .clickable:hover td { background: #f8fbff; }
    .clickable.active td { background: #eef6ff; }
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
    .hand-filters {
      display: grid;
      grid-template-columns: repeat(5, minmax(120px, 1fr));
      gap: 12px;
      align-items: end;
    }
    .hand-grid {
      display: grid;
      grid-template-columns: minmax(0, 1.15fr) minmax(360px, .85fr);
      gap: 16px;
      align-items: start;
    }
    .hand-grid > section { margin-bottom: 0; }
    .hand-detail-section { position: sticky; top: 88px; }
    .hand-pager {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      margin-top: 14px;
      flex-wrap: wrap;
    }
    .hand-pager-controls { display: flex; align-items: center; gap: 8px; }
    .hand-page-size { display: flex; align-items: center; gap: 8px; color: var(--muted); font-size: 12px; }
    .hand-page-size select { width: 82px; }
    .cards { display: inline-flex; gap: 5px; flex-wrap: wrap; align-items: center; }
    .card {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-width: 28px;
      height: 30px;
      padding: 0 6px;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: #fff;
      font-weight: 700;
      font-variant-numeric: tabular-nums;
    }
    .card.red { color: #d12929; border-color: #f0b4b4; background: #fff7f7; }
    .card.black { color: #1f2937; }
    .hand-detail-title {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      margin-bottom: 10px;
      flex-wrap: wrap;
    }
    .hand-detail-title h2 { font-size: 16px; margin: 0; }
    .log-detail {
      margin: 0;
      max-height: 620px;
      overflow: auto;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #0f1720;
      color: #e6edf3;
      padding: 14px;
      font: 12px/1.55 ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
      white-space: pre-wrap;
      overflow-wrap: anywhere;
    }
    .log-detail .card {
      height: 20px;
      min-width: 22px;
      padding: 0 4px;
      border-color: rgba(255,255,255,.18);
      background: rgba(255,255,255,.05);
      font-size: 12px;
    }
    .log-detail .card.red { color: #ff8b8b; background: rgba(255,80,80,.08); }
    .log-detail .card.black { color: #e6edf3; }
    @media (max-width: 860px) {
      header { align-items: flex-start; flex-direction: column; padding: 14px 16px; }
      main { padding: 14px 16px 28px; }
      form { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      .metrics { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      .history-item { grid-template-columns: 1fr 1fr; }
      .hand-filters { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      .hand-grid { grid-template-columns: 1fr; }
      .hand-detail-section { position: static; }
    }
  </style>
</head>
<body>
  <header>
    <h1>PokerFate 控制台</h1>
    <div class="status">
      <span id="session-dot" class="dot"></span><span id="session-text">WSS -</span>
      <span id="job-dot" class="dot"></span><span id="job-text">任务 -</span>
      <span id="web-url"></span>
    </div>
  </header>
  <main>
    <div class="tabs" role="tablist">
      <button class="tab-btn active" type="button" data-tab="color">彩球集</button>
      <button class="tab-btn" type="button" data-tab="hands">对局列表</button>
    </div>

    <div id="tab-color" class="tab-panel active">
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
    </div>

    <div id="tab-hands" class="tab-panel">
      <section>
        <div class="hand-filters">
          <label>位置
            <select id="hand-position">
              <option value="all">全部</option>
            </select>
          </label>
          <label>是否入池
            <select id="hand-vpip">
              <option value="all">全部</option>
              <option value="yes" selected>入池</option>
              <option value="no">未入池</option>
            </select>
          </label>
          <label>是否盈利
            <select id="hand-result">
              <option value="all">全部</option>
              <option value="profit">盈利</option>
              <option value="loss">亏损</option>
              <option value="zero">持平</option>
              <option value="incomplete">未结束</option>
            </select>
          </label>
          <label>BB(k)
            <select id="hand-bb">
              <option value="all">全部</option>
            </select>
          </label>
          <button id="hands-refresh-btn" class="secondary" type="button">刷新对局</button>
        </div>
        <div class="metrics">
          <div class="metric"><span>当前日志手数</span><b id="hands-total">0</b></div>
          <div class="metric"><span>筛选结果</span><b id="hands-count">0</b></div>
          <div class="metric"><span>当前日志</span><b id="hands-log">-</b></div>
          <div class="metric"><span>已选手牌</span><b id="hands-selected">-</b></div>
          <div class="metric"><span>详情行号</span><b id="hands-lines">-</b></div>
        </div>
        <div class="hand-pager">
          <div class="hand-pager-controls">
            <button id="hands-prev-btn" class="secondary" type="button">上一页</button>
            <span id="hands-page-info" class="muted">第 1 / 1 页</span>
            <button id="hands-next-btn" class="secondary" type="button">下一页</button>
          </div>
          <label class="hand-page-size">每页
            <select id="hands-page-size">
              <option value="20">20</option>
              <option value="30" selected>30</option>
              <option value="50">50</option>
              <option value="100">100</option>
            </select>
          </label>
        </div>
      </section>

      <div class="hand-grid">
        <section>
          <div class="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>手数</th>
                  <th>时间</th>
                  <th>位置</th>
                  <th>BB</th>
                  <th>底牌</th>
                  <th>排面</th>
                  <th>入池</th>
                  <th>结果</th>
                  <th>最后动作</th>
                  <th>赢家 / 我的牌型</th>
                </tr>
              </thead>
              <tbody id="hands-body">
                <tr><td colspan="10" class="muted">暂无对局</td></tr>
              </tbody>
            </table>
          </div>
        </section>

        <section class="hand-detail-section">
          <div class="hand-detail-title">
            <h2 id="hand-detail-title">对局详情</h2>
            <span id="hand-detail-meta" class="muted">选择一手查看完整日志</span>
          </div>
          <pre id="hand-detail" class="log-detail">暂无详情</pre>
        </section>
      </div>
    </div>
  </main>

  <script>
    const $ = (id) => document.getElementById(id);
    const colorName = (item) => item && item.name ? item.name : "-";
    const signed = (n) => {
      const v = Number(n || 0);
      return `${v > 0 ? "+" : ""}${v.toLocaleString()}`;
    };
    const moneyClass = (n) => Number(n || 0) >= 0 ? "pos" : "neg";
    const handMoneyClass = (n) => Number(n || 0) > 0 ? "pos" : (Number(n || 0) < 0 ? "neg" : "zero");
    const swatch = (item) => `<span class="swatch"><i class="ball c${item.id}"></i>${colorName(item)}</span>`;
    let activeTab = "color";
    let selectedHandId = null;
    let handFilterOptionsReady = false;
    let handPage = 1;
    let handPageSize = 30;

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
      const params = new URLSearchParams({
        position: $("hand-position").value || "all",
        vpip: $("hand-vpip").value || "all",
        result: $("hand-result").value || "all",
        bb_k: $("hand-bb").value || "all",
        page: String(handPage),
        page_size: String(handPageSize),
      });
      const data = await api(`/api/hands?${params.toString()}`);
      renderHands(data);
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
    $("hands-refresh-btn").addEventListener("click", () => {
      handFilterOptionsReady = false;
      refreshHands().catch((err) => setNotice(err.message));
    });
    $("hands-prev-btn").addEventListener("click", () => {
      if (handPage <= 1) return;
      handPage -= 1;
      selectedHandId = null;
      refreshHands().catch((err) => setNotice(err.message));
    });
    $("hands-next-btn").addEventListener("click", () => {
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
        }
      });
    });
    refresh();
    refreshHands().catch(() => {});
    setInterval(refresh, 1000);
    setInterval(() => {
      if (activeTab === "hands") {
        refreshHands().catch((err) => setNotice(err.message));
      }
    }, 4000);
  </script>
</body>
</html>
"""
