from __future__ import annotations

from datetime import datetime
from typing import Callable

from pf_entertainment.logger import LOG_FILE
from pf_entertainment.web import EntertainmentWebServer, web_access_urls


BotDashboardGetter = Callable[[], dict]


class EntertainmentRuntime:
    """Serve the proxy dashboard and track whether a client is connected."""

    def __init__(
        self,
        *,
        web_host: str | None = "0.0.0.0",
        web_port: int | None = 9022,
        live_source=None, radar_board=None,
    ) -> None:
        self.live_source, self.radar_board = live_source, radar_board
        self.web_host = web_host
        self.web_port = web_port
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
                live_source=self.live_source, radar_board=self.radar_board,
            )
            await self._web.start()
            self.web_port = self._web.port

    async def close(self):
        if self._web is not None:
            await self._web.close()
            self._web = None

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
        return web_access_urls(self.web_host, self.web_port)
