from __future__ import annotations

import asyncio
import json
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from typing import Awaitable, Callable

from pf_entertainment.color_game import (
    ColorGameCommand,
    ColorGameParseError,
    format_bets,
    format_response_summary,
    parse_color_command,
    strategy_note,
    summarize_color_response,
)
from pf_entertainment.logger import LOG_FILE, get_logger
from pf_entertainment.pinball import (
    PinballCommand,
    PinballParseError,
    format_pinball_response_summary,
    parse_pinball_command,
    summarize_pinball_response,
)


PacketSender = Callable[[str, dict, int], Awaitable[None]]


@dataclass
class _Session:
    token: object
    sender: PacketSender
    connected_at: datetime


@dataclass
class _PendingColorAction:
    command: ColorGameCommand
    created_at: datetime
    future: asyncio.Future | None = None


@dataclass
class _PendingPinballAction:
    command: PinballCommand
    created_at: datetime
    future: asyncio.Future | None = None


@dataclass
class _CommandOptions:
    wait: bool = False
    timeout: float = 15.0
    as_json: bool = False


class EntertainmentRuntime:
    """Local command runtime for entertainment side-game packet injection."""

    watched_s2c_types = frozenset({"pb.ColorGameActionRSP", "pb.PinballActionRSP"})

    def __init__(self, host: str = "127.0.0.1", port: int = 9021) -> None:
        self.host = host
        self.port = port
        self.log = get_logger()
        self._server: asyncio.AbstractServer | None = None
        self._session: _Session | None = None
        self._send_lock = asyncio.Lock()
        self._pending_color: deque[_PendingColorAction] = deque()
        self._pending_pinball: deque[_PendingPinballAction] = deque()
        self._last_room_id = 0

    async def start(self) -> None:
        if self._server is not None:
            return
        self._server = await asyncio.start_server(
            self._handle_client,
            self.host,
            self.port,
        )
        self.log.info(
            "[娱乐游戏] 指令服务已启动 %s:%d，日志=%s",
            self.host,
            self.port,
            LOG_FILE,
        )

    def attach_session(self, sender: PacketSender) -> object:
        token = object()
        self._session = _Session(token=token, sender=sender, connected_at=datetime.now())
        self.log.info("[娱乐游戏] WSS 会话已接入，可以发送小游戏包")
        return token

    def detach_session(self, token: object) -> None:
        if self._session is not None and self._session.token is token:
            self._session = None
            self.log.info("[娱乐游戏] WSS 会话已断开，暂停发送小游戏包")

    def note_room_id(self, room_id: int) -> None:
        if room_id > 0:
            self._last_room_id = room_id

    def observe_s2c(self, type_name: str, msg: dict) -> None:
        if type_name == "pb.PinballActionRSP":
            self._observe_pinball_rsp(msg)
            return
        if type_name != "pb.ColorGameActionRSP":
            return
        pending = self._pending_color.popleft() if self._pending_color else None
        fallback_total = pending.command.total_bet if pending else None
        summary = summarize_color_response(msg, fallback_total_bet=fallback_total)
        line = format_response_summary(summary)
        if pending:
            line += f" | 策略:{pending.command.strategy}"
            if pending.future is not None and not pending.future.done():
                pending.future.set_result(summary)
        if summary["code"] != 0:
            self.log.warning("[彩球RSP] code=%s %s", summary["code"], line)
        else:
            self.log.info("[彩球RSP] %s", line)

    def _observe_pinball_rsp(self, msg: dict) -> None:
        pending = self._pending_pinball.popleft() if self._pending_pinball else None
        fallback_total = pending.command.total_bet if pending else None
        summary = summarize_pinball_response(msg, fallback_total_bet=fallback_total)
        line = format_pinball_response_summary(summary)
        if pending and pending.future is not None and not pending.future.done():
            pending.future.set_result(summary)
        if summary["code"] != 0:
            self.log.warning("[弹珠RSP] code=%s %s", summary["code"], line)
        else:
            self.log.info("[弹珠RSP] %s", line)

    async def handle_command(self, line: str) -> str:
        line = line.strip()
        if not line:
            return self.help_text()

        parts = line.split()
        command = parts[0].lower()
        args = parts[1:]
        if command in ("help", "h", "?"):
            return self.help_text()
        if command in ("status", "s"):
            return self.status_text()
        if command in ("note", "strategy", "规则", "策略"):
            return strategy_note()
        if command in ("color", "colorgame", "cg", "彩球"):
            return await self._send_color(args)
        if command in ("pinball", "pb", "弹珠", "弹球"):
            return await self._send_pinball(args)
        return f"未知指令: {parts[0]}\n\n{self.help_text()}"

    async def _send_color(self, args: list[str]) -> str:
        opts, color_args = self._extract_command_options(args)
        try:
            cmd = parse_color_command(color_args)
        except ColorGameParseError as exc:
            return f"彩球指令错误: {exc}"

        future = asyncio.get_running_loop().create_future() if opts.wait else None
        pending = _PendingColorAction(
            command=cmd,
            created_at=datetime.now(),
            future=future,
        )
        self._pending_color.append(pending)
        try:
            await self._send_packet("pb.ColorGameActionREQ", cmd.to_fields(), cmd.room_id)
        except Exception:
            try:
                self._pending_color.remove(pending)
            except ValueError:
                pass
            if future is not None and not future.done():
                future.cancel()
            raise
        line = (
            f"彩球 投入 {format_bets(cmd.bets)} | "
            f"总投入:{cmd.total_bet} lvl:{cmd.lvl} "
            f"from_game_type:{cmd.from_game_type} room_id:{cmd.room_id} "
            f"策略:{cmd.strategy}"
        )
        self.log.info("[彩球REQ] %s", line)
        if not opts.wait:
            return f"OK {line}"

        assert future is not None
        try:
            summary = await asyncio.wait_for(future, timeout=opts.timeout)
        except asyncio.TimeoutError:
            try:
                self._pending_color.remove(pending)
            except ValueError:
                pass
            if opts.as_json:
                return json.dumps(
                    {
                        "ok": False,
                        "error": "timeout",
                        "request": self._command_payload(cmd),
                    },
                    ensure_ascii=False,
                )
            return f"ERR 等待彩球响应超时: {opts.timeout:.1f}s"

        response_line = format_response_summary(summary)
        if opts.as_json:
            return json.dumps(
                {
                    "ok": summary["code"] == 0,
                    "request": self._command_payload(cmd),
                    "summary": summary,
                    "line": response_line,
                },
                ensure_ascii=False,
            )
        return f"OK {line}\n{response_line}"

    async def _send_pinball(self, args: list[str]) -> str:
        opts, pinball_args = self._extract_command_options(args)
        try:
            cmd = parse_pinball_command(pinball_args)
        except PinballParseError as exc:
            return f"弹珠指令错误: {exc}"

        future = asyncio.get_running_loop().create_future() if opts.wait else None
        pending = _PendingPinballAction(
            command=cmd,
            created_at=datetime.now(),
            future=future,
        )
        self._pending_pinball.append(pending)
        try:
            await self._send_packet("pb.PinballActionREQ", cmd.to_fields(), cmd.room_id)
        except Exception:
            try:
                self._pending_pinball.remove(pending)
            except ValueError:
                pass
            if future is not None and not future.done():
                future.cancel()
            raise

        line = (
            f"弹珠 投入 每球:{cmd.per_bet} 数量:{cmd.ball_num} "
            f"总投入:{cmd.total_bet} lvl:{cmd.lvl} "
            f"from_game_type:{cmd.from_game_type} room_id:{cmd.room_id}"
        )
        self.log.info("[弹珠REQ] %s", line)
        if not opts.wait:
            return f"OK {line}"

        assert future is not None
        try:
            summary = await asyncio.wait_for(future, timeout=opts.timeout)
        except asyncio.TimeoutError:
            try:
                self._pending_pinball.remove(pending)
            except ValueError:
                pass
            if opts.as_json:
                return json.dumps(
                    {
                        "ok": False,
                        "error": "timeout",
                        "request": self._pinball_payload(cmd),
                    },
                    ensure_ascii=False,
                )
            return f"ERR 等待弹珠响应超时: {opts.timeout:.1f}s"

        response_line = format_pinball_response_summary(summary)
        if opts.as_json:
            return json.dumps(
                {
                    "ok": summary["code"] == 0,
                    "request": self._pinball_payload(cmd),
                    "summary": summary,
                    "line": response_line,
                },
                ensure_ascii=False,
            )
        return f"OK {line}\n{response_line}"

    def _extract_command_options(self, args: list[str]) -> tuple[_CommandOptions, list[str]]:
        opts = _CommandOptions()
        color_args: list[str] = []
        for arg in args:
            low = arg.lower()
            if low in ("wait", "wait=1", "wait=true", "wait=yes"):
                opts.wait = True
                continue
            if low in ("json", "json=1", "json=true", "format=json"):
                opts.as_json = True
                continue
            if low in ("wait=0", "wait=false", "wait=no"):
                opts.wait = False
                continue
            if low.startswith("timeout="):
                raw = arg.split("=", 1)[1]
                try:
                    opts.timeout = max(1.0, float(raw))
                except ValueError:
                    raise ColorGameParseError(f"timeout 必须是数字: {raw!r}")
                continue
            color_args.append(arg)
        return opts, color_args

    def _command_payload(self, cmd: ColorGameCommand) -> dict:
        return {
            "bets": [{"id": color_id, "value": value} for color_id, value in cmd.bets],
            "total_bet": cmd.total_bet,
            "lvl": cmd.lvl,
            "from_game_type": cmd.from_game_type,
            "room_id": cmd.room_id,
            "strategy": cmd.strategy,
        }

    def _pinball_payload(self, cmd: PinballCommand) -> dict:
        return {
            "lvl": cmd.lvl,
            "per_bet": cmd.per_bet,
            "ball_num": cmd.ball_num,
            "total_bet": cmd.total_bet,
            "from_game_type": cmd.from_game_type,
            "room_id": cmd.room_id,
        }

    async def _send_packet(self, type_name: str, fields: dict, room_id: int) -> None:
        session = self._session
        if session is None:
            raise RuntimeError("当前没有 WSS 会话，先让设备连上 proxy")
        async with self._send_lock:
            await session.sender(type_name, fields, room_id)

    async def _handle_client(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        peer = writer.get_extra_info("peername")
        try:
            raw = await reader.readline()
            if raw:
                try:
                    response = await self.handle_command(raw.decode("utf-8"))
                except Exception as exc:
                    self.log.exception("[娱乐游戏] 指令执行失败 peer=%s", peer)
                    response = f"ERR {exc}"
                writer.write((response.rstrip() + "\n").encode("utf-8"))
                await writer.drain()
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass

    def status_text(self) -> str:
        session = self._session
        state = "connected" if session else "disconnected"
        pending = len(self._pending_color)
        pending_pinball = len(self._pending_pinball)
        return (
            f"娱乐游戏状态: {state}, pending_color={pending}, pending_pinball={pending_pinball}, "
            f"last_room_id={self._last_room_id}, command={self.host}:{self.port}, "
            f"log={LOG_FILE}"
        )

    def help_text(self) -> str:
        return "\n".join(
            [
                "娱乐游戏指令:",
                "  status",
                "  note",
                "  color red=1000 lvl=1",
                "  color 黄:1000 红:3000 lvl=1",
                "  color single red stake=1000 lvl=1",
                "  color cover stake=1000 lvl=1",
                "  pinball",
                "参数:",
                "  颜色: yellow/黄, gray/灰, purple/紫, blue/蓝, red/红, green/绿",
                "  弹珠固定最低下注: lvl=1 per_bet=1000 ball_num=1",
                "  lvl 默认 1；from_game_type 默认 0；room_id 默认 0",
            ]
        )
