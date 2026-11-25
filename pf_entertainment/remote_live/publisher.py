from __future__ import annotations

import asyncio
import fcntl
import inspect
import json
import logging
import os
import shlex
import time
from pathlib import Path
from urllib.request import ProxyHandler, Request, build_opener

from . import money as money_frame
from .config import DEFAULT_CONFIG, PublishConfig, SSH_HINT, ssh_args
from .server import MAX_FRAME, encode

log = logging.getLogger("pf_remote_live")
MONEY_EVERY = 2.0     # seconds between reads of the money figures: the console's own page polls at this rate


class RemotePublisher:
    """Latest snapshot only. Never awaits network operations on the game path.

    ``money_source`` returns the console's bankroll dashboard; its figures ride along with the
    table (money.py) and a failure to read them never holds the table back.
    """

    def __init__(self, source, *, money_source=None, config_path: Path = DEFAULT_CONFIG):
        self.source, self.money_source, self.config_path = source, money_source, Path(config_path)
        self.money_sent = 0          # hands the server acknowledged on this connection
        self.money_facts = None      # figures it acknowledged
        self.money_due = 0.0
        self.money_failed = False
        self.task = None
        self.process = None
        self.stderr_task = None
        self.stderr_tail = b""
        self.lock_file = None
        self.config = None
        self.sequence = 0

    def start(self):
        self.task = asyncio.create_task(self.run(), name="remote-live-upload")
        return self

    async def close(self):
        if self.task:
            self.task.cancel()
            await asyncio.gather(self.task, return_exceptions=True)

    async def _stderr(self, stream):
        while chunk := await stream.read(1024):
            self.stderr_tail = (self.stderr_tail + chunk)[-4096:]

    async def _ack(self):
        line = await asyncio.wait_for(self.process.stdout.readline(), self.config.timeout)
        if not line:
            await asyncio.sleep(0)
            reason = self.stderr_tail.decode(errors="replace").strip()
            raise ConnectionError(reason or "SSH 通道提前关闭，请检查远端服务及免密认证")
        ack = json.loads(line)
        if not ack.get("ok"):
            raise ConnectionError(str(ack.get("error", "远端拒绝接收快照")))
        return ack

    async def _connect(self):
        cfg = self.config
        command = (f"cd {shlex.quote(cfg.remote_dir)} && exec python3 -m pf_entertainment.remote_live "
                   f"ingest --socket {shlex.quote(cfg.remote_socket)}")
        self.stderr_tail = b""
        self.process = await asyncio.create_subprocess_exec(
            *ssh_args(cfg.ssh_host), command, stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, limit=MAX_FRAME)
        self.stderr_task = asyncio.create_task(self._stderr(self.process.stderr))
        ready = await self._ack()
        if not ready.get("ready") or ready.get("protocol") != 1:
            raise ConnectionError("远端直播服务协议不兼容")
        self.money_sent, self.money_facts, self.money_due = 0, None, 0.0     # a new connection starts empty

    async def _disconnect(self):
        process, self.process = self.process, None
        if process:
            if process.stdin:
                process.stdin.close()
            if process.returncode is None:
                try:
                    process.terminate()
                except ProcessLookupError:
                    pass
                try:
                    await asyncio.wait_for(process.wait(), 1)
                except asyncio.TimeoutError:
                    try:
                        process.kill()
                    except ProcessLookupError:
                        pass
                    await process.wait()
        if self.stderr_task:
            self.stderr_task.cancel()
            await asyncio.gather(self.stderr_task, return_exceptions=True)
            self.stderr_task = None

    async def _publish(self):
        live = self.source()
        if inspect.isawaitable(live):
            live = await live
        if not isinstance(live, dict):
            raise ValueError("本机实时对局快照不可用")
        money = await self._money()
        self.sequence += 1
        frame = encode({"sequence": self.sequence, "live": live, **({"money": money} if money else {})})
        if len(frame) > MAX_FRAME:
            raise ValueError("牌桌快照超过上传上限")
        self.process.stdin.write(frame)
        await asyncio.wait_for(self.process.stdin.drain(), self.config.timeout)
        ack = await self._ack()
        if ack.get("sequence") != self.sequence:
            raise ConnectionError("上传确认序号不匹配")
        if money:
            self.money_sent, self.money_facts = money["from"] + len(money["points"]), money["facts"]

    async def _money(self):
        """The money part of this frame: the figures when they changed, and the hands not yet sent."""
        if self.money_source is None or time.monotonic() < self.money_due:
            return None
        self.money_due = time.monotonic() + MONEY_EVERY
        try:
            dashboard = self.money_source()
            if inspect.isawaitable(dashboard):
                dashboard = await dashboard
            part = money_frame.next_part(dashboard, self.money_sent, self.money_facts)
            if part and len(part["points"]) == money_frame.CHUNK:
                self.money_due = 0.0          # a long session goes up in consecutive frames
            if self.money_failed:
                log.info("[REMOTE-LIVE] 资金数据已恢复上传")
            self.money_failed = False
            return part
        except Exception as exc:
            if not self.money_failed:
                log.warning("[REMOTE-LIVE] 读不到资金数据，牌桌照常上传：%s: %s", type(exc).__name__, exc)
            self.money_failed = True
            return None

    async def run(self):
        try:
            self.config = PublishConfig.load(self.config_path)
            self.lock_file = self.config_path.with_suffix(".publisher.lock").open("a+")
            fcntl.flock(self.lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.lock_file.seek(0)
            self.lock_file.truncate()
            self.lock_file.write(str(os.getpid()))
            self.lock_file.flush()
            try:
                await self._connect()
            except Exception as exc:
                log.warning("[REMOTE-LIVE] 启用失败：%s: %s。%s", type(exc).__name__, exc, SSH_HINT)
                return
            log.info("[REMOTE-LIVE] SSH 上传已启用：%s（仅最新快照）", self.config.ssh_host)
            failures = 0
            while True:
                try:
                    if self.process is None:
                        await self._connect()
                    await self._publish()
                    if failures:
                        log.info("[REMOTE-LIVE] 上传已恢复；已丢弃中断期间的旧数据")
                    failures = 0
                    await asyncio.sleep(self.config.interval)
                except Exception as exc:
                    failures += 1
                    delay = min(30, 2 ** min(failures - 1, 5))
                    log.warning("[REMOTE-LIVE] 上传中断：%s: %s；%ss 后重试", type(exc).__name__, exc, delay)
                    await self._disconnect()
                    await asyncio.sleep(delay)
        except asyncio.CancelledError:
            raise
        except BlockingIOError:
            log.warning("[REMOTE-LIVE] 已有本机上传进程，本实例跳过远程直播")
        except Exception as exc:
            log.warning("[REMOTE-LIVE] 启用失败（%s）：%s: %s。%s",
                        self.config_path, type(exc).__name__, exc, SSH_HINT)
        finally:
            await self._disconnect()
            if self.lock_file:
                self.lock_file.close()
                self.lock_file = None


def start_remote_live(source, *, money_source=None, enabled=True, config_path: Path = DEFAULT_CONFIG):
    if not enabled:
        return None
    return RemotePublisher(source, money_source=money_source, config_path=config_path).start()


def _loopback(url: str):
    # Standalone sidecar: read only the existing loopback Web API. Never proxy it.
    from urllib.parse import urlsplit
    parsed = urlsplit(url)
    if parsed.scheme != "http" or parsed.hostname not in ("127.0.0.1", "localhost", "::1"):
        raise ValueError("source-url 必须是本机回环 HTTP 地址")
    return parsed, build_opener(ProxyHandler({}))


def http_source(url: str):
    _, opener = _loopback(url)

    def read():
        with opener.open(Request(url, headers={"Cache-Control": "no-cache"}), timeout=2) as response:
            raw = response.read(MAX_FRAME + 1)
        if len(raw) > MAX_FRAME:
            raise ValueError("本机 Web 快照过大")
        data = json.loads(raw)
        if not data.get("ok") or not data.get("available") or not isinstance(data.get("live"), dict):
            raise ValueError("本机 Web 没有可用的实时对局数据")
        return data["live"]

    async def source():
        return await asyncio.to_thread(read)
    return source


def http_money_source(url: str):
    """The sidecar's money figures: the console's /api/status beside the given /api/live."""
    parsed, opener = _loopback(url)
    status = parsed._replace(path="/api/status", query="", fragment="").geturl()

    def read():
        with opener.open(Request(status, headers={"Cache-Control": "no-cache"}), timeout=2) as response:
            data = json.load(response)
        return (data.get("runtime") or {}).get("bot_dashboard")

    async def source():
        return await asyncio.to_thread(read)
    return source
