from __future__ import annotations

import socket
from datetime import datetime
from typing import Callable

from pf_entertainment.logger import LOG_FILE, get_logger
from pf_entertainment.web import EntertainmentWebServer


BotDashboardGetter = Callable[[], dict]


class EntertainmentRuntime:
    """Serve the proxy dashboard and track whether a client is connected."""

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
        self._connected_at: datetime | None = None
        self._bot_dashboard_getter: BotDashboardGetter | None = None

    def set_bot_dashboard_handler(self, getter: BotDashboardGetter) -> None:
        self._bot_dashboard_getter = getter

    async def start(self) -> None:
        if self.web_host is not None and self.web_port is not None and self._web is None:
            self._web = EntertainmentWebServer(
                runtime=self,
                host=self.web_host,
                port=self.web_port,
            )
            await self._web.start()
            self.web_port = self._web.port
            urls = ", ".join(self.web_access_urls())
            if urls:
                self.log.info("[牌局 Web] Web 可访问地址: %s", urls)

    def attach_session(self) -> datetime:
        self._connected_at = datetime.now()
        return self._connected_at

    def detach_session(self, token: datetime) -> None:
        if self._connected_at is token:
            self._connected_at = None

    def status_data(self) -> dict:
        web_urls = self.web_access_urls()
        return {
            "session_state": "connected" if self._connected_at else "disconnected",
            "connected_at": self._connected_at.isoformat(timespec="seconds") if self._connected_at else None,
            "web_host": self.web_host,
            "web_port": self.web_port,
            "web_url": web_urls[0] if web_urls else None,
            "web_urls": web_urls,
            "log_file": str(LOG_FILE),
            "bot_dashboard": self.bot_dashboard_data(),
        }

    def bot_dashboard_data(self) -> dict | None:
        if self._bot_dashboard_getter is None:
            return None
        return self._bot_dashboard_getter()

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
