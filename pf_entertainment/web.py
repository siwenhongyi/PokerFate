from __future__ import annotations

import asyncio
import json
import os
import sys
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

from pf_entertainment.color_strategy import ColorMartingaleConfig
from pf_entertainment.hand_preview import hand_detail_payload, hand_list_payload
from pf_entertainment.records import JsonRecordStore


ROOT = Path(__file__).resolve().parents[1]
RANGE_ANALYSIS_TIMEOUT_SEC = 180.0


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
        self._range_task: asyncio.Task | None = None
        self._range_job: dict[str, Any] | None = None

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
                        hand_no=self._str_query(request, "hand_no", ""),
                        board=self._str_query(request, "board", ""),
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
        if request.method == "POST" and request.path == "/api/range/compare":
            return self._start_range_analysis()
        if request.method == "GET" and request.path == "/api/range/compare/status":
            return self._json_response({"ok": True, "job": self._range_job_payload()})
        if request.method == "GET" and request.path == "/api/bot/settings":
            return self._json_response(
                {"ok": True, "settings": self.runtime.bot_settings_data()}
            )
        if request.method == "POST" and request.path == "/api/bot/settings":
            return await asyncio.to_thread(self._update_bot_settings, request)
        if request.method == "POST" and request.path == "/api/color/run":
            return await self._start_color_run(request)
        if request.method == "POST" and request.path == "/api/color/stop":
            return self._stop_color_run()
        return self._json_response({"ok": False, "error": "not found"}, status=404)

    def _update_bot_settings(
        self,
        request: _HttpRequest,
    ) -> tuple[int, dict[str, str], bytes]:
        try:
            payload = json.loads(request.body.decode("utf-8") or "{}")
            if not isinstance(payload, dict):
                raise ValueError("JSON body must be an object")
            settings = self.runtime.update_bot_settings(payload)
        except Exception as exc:
            return self._json_response({"ok": False, "error": str(exc)}, status=400)
        return self._json_response({"ok": True, "settings": settings})

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

    def _start_range_analysis(self) -> tuple[int, dict[str, str], bytes]:
        if self._range_task is not None and not self._range_task.done():
            return self._json_response({"ok": True, "job": self._range_job_payload()}, status=202)

        job_id = f"range-{int(time.time())}-{uuid.uuid4().hex[:8]}"
        self._range_job = {
            "id": job_id,
            "status": "running",
            "started_at": time.time(),
            "finished_at": None,
            "elapsed_ms": None,
            "result": None,
            "error": "",
        }
        self._range_task = asyncio.create_task(self._run_range_analysis_job(job_id))
        return self._json_response({"ok": True, "job": self._range_job_payload()}, status=202)

    async def _run_range_analysis_job(self, job_id: str) -> None:
        started = time.perf_counter()
        try:
            result = await self._run_range_analysis_subprocess()
            self._finish_range_job(
                job_id,
                status="done",
                elapsed_ms=(time.perf_counter() - started) * 1000.0,
                result=result,
            )
        except Exception as exc:
            self.log.exception("[娱乐游戏] 校准分析任务失败")
            self._finish_range_job(
                job_id,
                status="error",
                elapsed_ms=(time.perf_counter() - started) * 1000.0,
                error=str(exc),
            )

    async def _run_range_analysis_subprocess(self) -> dict[str, Any]:
        script = ROOT / "scripts" / "analyze_range_ece.py"
        env = dict(os.environ)
        env.setdefault("PYTHONUNBUFFERED", "1")
        proc = await asyncio.create_subprocess_exec(
            sys.executable,
            str(script),
            "--json",
            cwd=str(ROOT),
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=RANGE_ANALYSIS_TIMEOUT_SEC,
            )
        except asyncio.TimeoutError as exc:
            proc.kill()
            await proc.communicate()
            raise TimeoutError(
                f"range analysis timed out after {RANGE_ANALYSIS_TIMEOUT_SEC:.0f}s"
            ) from exc

        stderr_text = stderr.decode("utf-8", errors="replace").strip()
        if proc.returncode != 0:
            detail = stderr_text[-1200:] if stderr_text else "no stderr"
            raise RuntimeError(f"range analysis subprocess failed: {detail}")
        try:
            return json.loads(stdout.decode("utf-8"))
        except Exception as exc:
            detail = stderr_text[-1200:] if stderr_text else "no stderr"
            raise RuntimeError(f"range analysis returned invalid JSON: {detail}") from exc

    def _finish_range_job(
        self,
        job_id: str,
        *,
        status: str,
        elapsed_ms: float,
        result: dict[str, Any] | None = None,
        error: str = "",
    ) -> None:
        if not self._range_job or self._range_job.get("id") != job_id:
            return
        self._range_job.update(
            {
                "status": status,
                "finished_at": time.time(),
                "elapsed_ms": elapsed_ms,
                "result": result,
                "error": error,
            }
        )

    def _range_job_payload(self) -> dict[str, Any]:
        if not self._range_job:
            return {"running": False, "status": "idle"}
        running = self._range_task is not None and not self._range_task.done()
        out = dict(self._range_job)
        out["running"] = running
        if out.get("elapsed_ms") is not None:
            out["elapsed_ms"] = round(float(out["elapsed_ms"]), 1)
        return out

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
                "type": f"color_martingale_{config.selection_mode}",
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
    input[type="checkbox"] {
      width: 18px;
      height: 18px;
      padding: 0;
      align-self: start;
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
    .dashboard-grid {
      display: grid;
      grid-template-columns: minmax(0, 1fr) minmax(280px, .45fr);
      gap: 16px;
      align-items: start;
    }
    .chart-box {
      width: 100%;
      height: 260px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fbfcfe;
      overflow: hidden;
    }
    .chart-box svg { width: 100%; height: 100%; display: block; }
    .chart-toolbar {
      display: flex;
      align-items: center;
      justify-content: flex-end;
      gap: 10px;
      flex-wrap: wrap;
    }
    .range-layout { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; align-items: start; }
    .range-conclusion { display: grid; gap: 8px; }
    .range-conclusion div {
      padding: 9px 10px;
      border-left: 3px solid var(--brand);
      background: #f7fbff;
    }
    .range-table table { min-width: 720px; }
    .range-table h2 { font-size: 15px; margin: 0 0 10px; }
    .sample-list { display: grid; gap: 8px; }
    .sample-item {
      display: grid;
      grid-template-columns: 1fr auto;
      gap: 8px;
      padding: 8px 0;
      border-bottom: 1px solid var(--line);
    }
    .sample-item:last-child { border-bottom: 0; }
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
      grid-template-columns: repeat(7, minmax(120px, 1fr));
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
      .dashboard-grid { grid-template-columns: 1fr; }
      .range-layout { grid-template-columns: 1fr; }
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
      <button class="tab-btn" type="button" data-tab="dashboard">资金看板</button>
      <button class="tab-btn" type="button" data-tab="hands">对局列表</button>
      <button class="tab-btn" type="button" data-tab="range">校准评估</button>
      <button class="tab-btn" type="button" data-tab="bot">运行参数</button>
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
            <option value="cycle" selected>每个循环固定少见球</option>
            <option value="bet">每次重选少见球</option>
            <option value="random_each">每次随机选择</option>
            <option value="recent3_most">最近3次结果最多</option>
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

    <div id="tab-dashboard" class="tab-panel">
      <section>
        <div class="metrics">
          <div class="metric"><span>当前总筹码</span><b id="bank-total">-</b></div>
          <div class="metric"><span>钱包余额</span><b id="bank-wallet">-</b></div>
          <div class="metric"><span>桌上筹码</span><b id="bank-table">-</b></div>
          <div class="metric"><span>本次启动盈亏</span><b id="bank-delta">-</b></div>
          <div class="metric"><span>最近采样</span><b id="bank-last">-</b></div>
        </div>
      </section>
      <div class="dashboard-grid">
        <section>
          <div class="hand-detail-title">
            <h2>余额曲线</h2>
            <div class="chart-toolbar">
              <span id="bank-chart-meta" class="muted">等待余额采样</span>
            </div>
          </div>
          <div class="chart-box" id="bank-chart"></div>
        </section>
        <section>
          <div class="metrics" style="grid-template-columns: repeat(2, minmax(0, 1fr)); margin:0 0 12px;">
            <div class="metric"><span>盈利锁仓</span><b id="bank-locks">0</b></div>
            <div class="metric"><span>自动续入</span><b id="bank-rebuys">0</b></div>
            <div class="metric"><span>换桌</span><b id="bank-escapes">0</b></div>
            <div class="metric"><span>BB</span><b id="bank-bb">-</b></div>
          </div>
          <div id="bank-samples" class="sample-list muted">暂无采样</div>
        </section>
      </div>
    </div>

    <div id="tab-bot" class="tab-panel">
      <section>
        <form id="bot-settings-form">
          <label>盈利锁仓 BB
            <input id="bot-profit-lock-bb" name="profit_lock_bb" type="number" min="1" step="1" required>
          </label>
          <label>决策引擎
            <select id="bot-decision-engine" name="decision_engine">
              <option value="local">local</option>
              <option value="g5">g5</option>
              <option value="g5_all">g5_all</option>
              <option value="realtime_cfr">realtime_cfr</option>
              <option value="cfr">cfr</option>
            </select>
          </label>
          <label>粘池翻前调整
            <input id="bot-preflop-sticky-pool-adjust" name="preflop_sticky_pool_adjust" type="checkbox">
          </label>
          <button id="bot-save-btn" type="submit">保存运行参数</button>
          <button id="bot-refresh-btn" class="secondary" type="button">刷新参数</button>
        </form>
        <div id="bot-notice" class="notice"></div>
        <div class="metrics">
          <div class="metric"><span>锁仓阈值</span><b id="bot-lock-bb">-</b></div>
          <div class="metric"><span>锁仓筹码</span><b id="bot-lock-chips">-</b></div>
          <div class="metric"><span>锁仓状态</span><b id="bot-lock-state">-</b></div>
          <div class="metric"><span>决策引擎</span><b id="bot-engine-state">-</b></div>
          <div class="metric"><span>粘池翻前</span><b id="bot-preflop-sticky-state">-</b></div>
        </div>
      </section>
    </div>

    <div id="tab-range" class="tab-panel">
      <section>
        <div class="hand-detail-title">
          <h2>范围校准评估</h2>
          <button id="range-run-btn" type="button">计算校准</button>
        </div>
        <div id="range-notice" class="notice"></div>
        <div class="metrics">
          <div class="metric"><span>决策点</span><b id="range-count">0</b></div>
          <div class="metric"><span>手牌数</span><b id="range-hands">0</b></div>
          <div class="metric"><span>Bayes 改善</span><b id="range-pf-better">0</b></div>
          <div class="metric"><span>Bayes 变差</span><b id="range-g5-better">0</b></div>
          <div class="metric"><span>Bucket ECE</span><b id="range-ece">-</b></div>
          <div class="metric"><span>Top Bucket</span><b id="range-top-acc">-</b></div>
          <div class="metric"><span>CEC NLL Gain</span><b id="range-cec-nll-gain">-</b></div>
          <div class="metric"><span>CEC ECE Gain</span><b id="range-cec-ece-gain">-</b></div>
          <div class="metric"><span>结论</span><b id="range-winner">-</b></div>
        </div>
      </section>

      <section>
        <div class="hand-detail-title">
          <h2>结论</h2>
          <span id="range-meta" class="muted">点击重新分析读取最新采集</span>
        </div>
        <div id="range-conclusion" class="range-conclusion muted">暂无分析</div>
      </section>

      <div class="range-layout">
        <section class="range-table">
          <h2>ECE 可靠性曲线</h2>
          <div class="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>预测概率</th>
                  <th>点数</th>
                  <th>平均预测</th>
                  <th>真实频率</th>
                  <th>偏差</th>
                  <th>方向</th>
                </tr>
              </thead>
              <tbody id="range-ece-bin-body">
                <tr><td colspan="6" class="muted">暂无分析</td></tr>
              </tbody>
            </table>
          </div>
        </section>
        <section class="range-table">
          <h2>按 Bucket 校准</h2>
          <div class="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Bucket</th>
                  <th>点数</th>
                  <th>ECE</th>
                  <th>平均预测</th>
                  <th>真实频率</th>
                  <th>方向</th>
                </tr>
              </thead>
              <tbody id="range-ece-bucket-body">
                <tr><td colspan="6" class="muted">暂无分析</td></tr>
              </tbody>
            </table>
          </div>
        </section>
        <section class="range-table">
          <h2>校准热点</h2>
          <div class="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>场景</th>
                  <th>点数</th>
                  <th>ECE</th>
                  <th>平均预测</th>
                  <th>真实频率</th>
                  <th>方向</th>
                </tr>
              </thead>
              <tbody id="range-ece-hotspot-body">
                <tr><td colspan="6" class="muted">暂无分析</td></tr>
              </tbody>
            </table>
          </div>
        </section>
        <section class="range-table">
          <h2>CEC 接入效果</h2>
          <div class="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>维度</th>
                  <th>样本</th>
                  <th>真实 Bucket 概率</th>
                  <th>NLL</th>
                  <th>ECE</th>
                  <th>Top1</th>
                </tr>
              </thead>
              <tbody id="range-cec-overall-body">
                <tr><td colspan="6" class="muted">暂无分析</td></tr>
              </tbody>
            </table>
          </div>
        </section>
        <section class="range-table">
          <h2>CEC 接入热点</h2>
          <div class="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>场景</th>
                  <th>样本</th>
                  <th>真实 Bucket 概率</th>
                  <th>NLL Gain</th>
                  <th>ECE Gain</th>
                  <th>结论</th>
                </tr>
              </thead>
              <tbody id="range-cec-hotspot-body">
                <tr><td colspan="6" class="muted">暂无分析</td></tr>
              </tbody>
            </table>
          </div>
        </section>
        <section class="range-table">
          <h2>按街道</h2>
          <div class="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>维度</th>
                  <th>样本</th>
                  <th>改善/变差</th>
                  <th>Combo 概率</th>
                  <th>Logloss</th>
                  <th>ΔNLL</th>
                </tr>
              </thead>
              <tbody id="range-street-body">
                <tr><td colspan="6" class="muted">暂无分析</td></tr>
              </tbody>
            </table>
          </div>
        </section>
        <section class="range-table">
          <h2>按实际牌型</h2>
          <div class="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>维度</th>
                  <th>样本</th>
                  <th>改善/变差</th>
                  <th>Combo 概率</th>
                  <th>Logloss</th>
                  <th>ΔNLL</th>
                </tr>
              </thead>
              <tbody id="range-category-body">
                <tr><td colspan="6" class="muted">暂无分析</td></tr>
              </tbody>
            </table>
          </div>
        </section>
        <section class="range-table">
          <h2>按玩家</h2>
          <div class="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>维度</th>
                  <th>样本</th>
                  <th>改善/变差</th>
                  <th>Combo 概率</th>
                  <th>Logloss</th>
                  <th>ΔNLL</th>
                </tr>
              </thead>
              <tbody id="range-player-body">
                <tr><td colspan="6" class="muted">暂无分析</td></tr>
              </tbody>
            </table>
          </div>
        </section>
        <section class="range-table">
          <h2>明显样例</h2>
          <div class="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>方向</th>
                  <th>手牌</th>
                  <th>街道</th>
                  <th>玩家</th>
                  <th>实际</th>
                  <th>概率 / NLL</th>
                </tr>
              </thead>
              <tbody id="range-example-body">
                <tr><td colspan="6" class="muted">暂无分析</td></tr>
              </tbody>
            </table>
          </div>
        </section>
      </div>
    </div>

    <div id="tab-hands" class="tab-panel">
      <section>
        <div class="hand-filters">
          <label>手数
            <input id="hand-no" type="number" min="1" step="1" inputmode="numeric" placeholder="全部">
          </label>
          <label>公共牌前缀
            <input id="hand-board" type="text" inputmode="text" placeholder="A 2 5">
          </label>
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
    let activeTab = "color";
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
          ["local", "g5", "g5_all", "realtime_cfr", "cfr"].includes(engineValue)
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
