from __future__ import annotations

import asyncio
import socket
import uuid
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from typing import Awaitable, Callable

from pf_entertainment.color_game import (
    ColorGameCommand,
    color_name,
    format_bets,
    format_ids,
    format_response_summary,
    summarize_color_response,
)
from pf_entertainment.color_strategy import (
    ColorMartingaleConfig,
    LeastSeenColorPicker,
    bet_sequence,
)
from pf_entertainment.logger import LOG_FILE, get_logger


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


class EntertainmentRuntime:
    """Runtime for entertainment side-game packet injection used by the Web UI."""

    watched_s2c_types = frozenset({"pb.ColorGameActionRSP"})

    def __init__(
        self,
        *,
        web_host: str | None = "0.0.0.0",
        web_port: int | None = 9022,
    ) -> None:
        self.web_host = web_host
        self.web_port = web_port
        self.log = get_logger()
        self._web = None
        self._session: _Session | None = None
        self._send_lock = asyncio.Lock()
        self._pending_color: deque[_PendingColorAction] = deque()
        self._last_room_id = 0

    async def start(self) -> None:
        if self.web_host is not None and self.web_port is not None and self._web is None:
            from pf_entertainment.web import EntertainmentWebServer

            self._web = EntertainmentWebServer(
                runtime=self,
                host=self.web_host,
                port=self.web_port,
            )
            await self._web.start()
            self.web_port = self._web.port
            urls = ", ".join(self.web_access_urls())
            if urls:
                self.log.info("[娱乐游戏] Web 可访问地址: %s", urls)

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

    async def _dispatch_color(
        self,
        cmd: ColorGameCommand,
        *,
        wait: bool,
        timeout: float,
    ) -> dict:
        future = asyncio.get_running_loop().create_future() if wait else None
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

        request_line = self._format_color_request_line(cmd)
        self.log.info("[彩球REQ] %s", request_line)
        result = {
            "ok": True,
            "request": self._command_payload(cmd),
            "request_line": request_line,
        }
        if not wait:
            return result

        assert future is not None
        try:
            summary = await asyncio.wait_for(future, timeout=timeout)
        except asyncio.TimeoutError:
            try:
                self._pending_color.remove(pending)
            except ValueError:
                pass
            raise

        response_line = format_response_summary(summary)
        result.update(
            {
                "ok": summary["code"] == 0,
                "summary": summary,
                "line": response_line,
            }
        )
        return result

    async def play_color(
        self,
        cmd: ColorGameCommand,
        *,
        timeout: float = 15.0,
    ) -> dict:
        return await self._dispatch_color(cmd, wait=True, timeout=timeout)

    def _format_color_request_line(self, cmd: ColorGameCommand) -> str:
        return (
            f"彩球 投入 {format_bets(cmd.bets)} | "
            f"总投入:{cmd.total_bet} lvl:{cmd.lvl} "
            f"from_game_type:{cmd.from_game_type} room_id:{cmd.room_id} "
            f"策略:{cmd.strategy}"
        )

    async def run_color_martingale(
        self,
        config: ColorMartingaleConfig,
        *,
        progress: Callable[[dict], None] | None = None,
        stop_event: asyncio.Event | None = None,
    ) -> dict:
        config.validate()
        bets = bet_sequence(config.base_bet, config.max_bet, config.multiplier)
        picker = LeastSeenColorPicker()
        started_at = datetime.now()
        record = {
            "id": self._new_run_id(started_at),
            "type": "color_martingale_least_seen",
            "status": "running",
            "started_at": started_at.isoformat(timespec="seconds"),
            "finished_at": None,
            "params": config.to_dict(),
            "bet_sequence": bets,
            "rounds": [],
            "summary": {
                "played": 0,
                "profit_cycles": 0,
                "total_bet": 0,
                "total_return": 0,
                "net_profit": 0,
                "color_counts": self._color_counts_payload(picker.snapshot()),
            },
        }
        self._emit_progress(progress, record)

        status = "done"
        error: str | None = None
        stop_requested = False

        for cycle in range(1, config.cycles + 1):
            cycle_net = 0
            cycle_bet = 0
            cycle_return = 0
            cycle_played = 0
            cycle_pick = picker.choose() if config.selection_mode == "cycle" else None

            for attempt, stake in enumerate(bets, start=1):
                if stop_event is not None and stop_event.is_set():
                    stop_requested = True
                    status = "stopped"
                    break

                pick = cycle_pick if cycle_pick is not None else picker.choose()
                cmd = ColorGameCommand(
                    bets=((pick.color_id, stake),),
                    lvl=config.lvl,
                    from_game_type=config.from_game_type,
                    room_id=config.room_id,
                    strategy="least_seen",
                )
                try:
                    result = await self.play_color(cmd, timeout=config.timeout)
                except asyncio.TimeoutError:
                    status = "error"
                    error = f"等待彩球响应超时: {config.timeout:.1f}s"
                    break
                except RuntimeError as exc:
                    status = "error"
                    error = str(exc)
                    self.log.warning("[彩球自适应倍投] %s", error)
                    break
                except Exception as exc:
                    status = "error"
                    error = str(exc)
                    self.log.exception("[彩球自适应倍投] command failed")
                    break

                summary = result["summary"]
                ok = bool(result.get("ok"))
                picker.observe(summary.get("ids", []))
                counts_after = picker.snapshot()

                bet = int(summary["total_bet"])
                reward = int(summary["total_return"])
                net = int(summary["net_profit"])
                cycle_bet += bet
                cycle_return += reward
                cycle_net += net
                cycle_played += 1

                totals = record["summary"]
                totals["played"] = int(totals["played"]) + 1
                totals["total_bet"] = int(totals["total_bet"]) + bet
                totals["total_return"] = int(totals["total_return"]) + reward
                totals["net_profit"] = int(totals["net_profit"]) + net
                totals["color_counts"] = self._color_counts_payload(counts_after)

                round_record = {
                    "index": totals["played"],
                    "cycle": cycle,
                    "attempt": attempt,
                    "stake": stake,
                    "selected": {
                        "id": pick.color_id,
                        "name": color_name(pick.color_id),
                        "reason": pick.reason,
                        "candidates": [
                            {"id": color_id, "name": color_name(color_id)}
                            for color_id in pick.candidates
                        ],
                        "counts_before": self._color_counts_payload(pick.counts_before),
                        "scope": config.selection_mode,
                    },
                    "request": result["request"],
                    "ok": ok,
                    "code": int(summary.get("code", 0)),
                    "ids": [
                        {"id": color_id, "name": color_name(color_id)}
                        for color_id in summary.get("ids", [])
                    ],
                    "ids_text": format_ids(summary.get("ids", [])),
                    "total_bet": bet,
                    "total_return": reward,
                    "net_profit": net,
                    "cycle_bet": cycle_bet,
                    "cycle_return": cycle_return,
                    "cycle_net": cycle_net,
                    "total_net": totals["net_profit"],
                    "color_counts_after": self._color_counts_payload(counts_after),
                    "line": result["line"],
                }
                record["rounds"].append(round_record)
                self._emit_progress(progress, record)

                if not ok:
                    status = "error"
                    error = result["line"]
                    break
                if cycle_net > 0:
                    record["summary"]["profit_cycles"] = (
                        int(record["summary"]["profit_cycles"]) + 1
                    )
                    break
                if config.delay > 0 and attempt < len(bets):
                    await asyncio.sleep(config.delay)

            if status == "error" or stop_requested:
                break
            if cycle_played <= 0:
                break
            if cycle < config.cycles and config.delay > 0:
                await asyncio.sleep(config.delay)

        record["status"] = status
        if error:
            record["error"] = error
        record["finished_at"] = datetime.now().isoformat(timespec="seconds")
        self._emit_progress(progress, record)
        self.log.info(
            "[彩球自适应倍投] done status=%s played=%s profit_cycles=%s/%s total_bet=%s total_return=%s net=%+d",
            record["status"],
            record["summary"]["played"],
            record["summary"]["profit_cycles"],
            config.cycles,
            record["summary"]["total_bet"],
            record["summary"]["total_return"],
            record["summary"]["net_profit"],
        )
        return record

    def _emit_progress(
        self,
        progress: Callable[[dict], None] | None,
        record: dict,
    ) -> None:
        if progress is not None:
            progress(record)

    def _color_counts_payload(self, counts: dict[int, int]) -> list[dict]:
        return [
            {"id": color_id, "name": color_name(color_id), "count": int(count)}
            for color_id, count in counts.items()
        ]

    def _new_run_id(self, started_at: datetime) -> str:
        return f"{started_at.strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:8]}"

    def _command_payload(self, cmd: ColorGameCommand) -> dict:
        return {
            "bets": [{"id": color_id, "value": value} for color_id, value in cmd.bets],
            "total_bet": cmd.total_bet,
            "lvl": cmd.lvl,
            "from_game_type": cmd.from_game_type,
            "room_id": cmd.room_id,
            "strategy": cmd.strategy,
        }

    async def _send_packet(self, type_name: str, fields: dict, room_id: int) -> None:
        session = self._session
        if session is None:
            raise RuntimeError("当前没有 WSS 会话，先让设备连上 proxy")
        async with self._send_lock:
            await session.sender(type_name, fields, room_id)

    def status_data(self) -> dict:
        session = self._session
        web_urls = self.web_access_urls()
        return {
            "session_state": "connected" if session else "disconnected",
            "connected_at": (
                session.connected_at.isoformat(timespec="seconds")
                if session is not None
                else None
            ),
            "pending_color": len(self._pending_color),
            "last_room_id": self._last_room_id,
            "web_host": self.web_host,
            "web_port": self.web_port,
            "web_url": web_urls[0] if web_urls else None,
            "web_urls": web_urls,
            "log_file": str(LOG_FILE),
        }

    def web_access_urls(self) -> list[str]:
        if self.web_host is None or self.web_port is None:
            return []
        if self.web_host in ("0.0.0.0", "::", ""):
            hosts = [*self._local_lan_ipv4_addresses(), "127.0.0.1"]
        else:
            hosts = [self.web_host]

        urls: list[str] = []
        seen: set[str] = set()
        for host in hosts:
            if host in seen:
                continue
            seen.add(host)
            urls.append(f"http://{host}:{self.web_port}")
        return urls

    def _local_lan_ipv4_addresses(self) -> list[str]:
        ips: set[str] = set()
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                sock.connect(("223.5.5.5", 80))
                ips.add(sock.getsockname()[0])
        except OSError:
            pass
        try:
            for ip in socket.gethostbyname_ex(socket.gethostname())[2]:
                ips.add(ip)
        except OSError:
            pass
        return sorted(
            (ip for ip in ips if self._is_lan_ipv4(ip)),
            key=self._ipv4_display_sort_key,
        )

    def _ipv4_display_sort_key(self, ip: str) -> tuple[int, str]:
        if ip.startswith("192.168."):
            group = 0
        elif ip.startswith("10."):
            group = 1
        elif ip.startswith("172.") and 16 <= int(ip.split(".")[1]) <= 31:
            group = 2
        else:
            group = 3
        return (group, ip)

    def _is_lan_ipv4(self, ip: str) -> bool:
        try:
            parts = [int(part) for part in ip.split(".")]
        except ValueError:
            return False
        if len(parts) != 4 or any(part < 0 or part > 255 for part in parts):
            return False
        return (
            parts[0] == 10
            or (parts[0] == 192 and parts[1] == 168)
            or (parts[0] == 172 and 16 <= parts[1] <= 31)
        )
