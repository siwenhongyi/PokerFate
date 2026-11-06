from __future__ import annotations

import logging
import sys
from pathlib import Path

import websockets.exceptions


class _ExpectedHandshakeNoiseFilter(logging.Filter):
    """Drop expected WebSocket handshake noise from half-open client retries."""

    def filter(self, record: logging.LogRecord) -> bool:
        if record.getMessage() != "opening handshake failed":
            return True
        exc_info = record.exc_info
        if not exc_info or len(exc_info) < 2:
            return True
        exc = exc_info[1]
        if not isinstance(exc, websockets.exceptions.InvalidMessage):
            return True
        cause = getattr(exc, "__cause__", None)
        return not isinstance(cause, EOFError)


_LOG_FMT = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")


def _fh(logs_dir: Path, filename: str) -> logging.Handler:
    # 每次启动覆盖，不追加。
    h = logging.FileHandler(logs_dir / filename, mode="w", encoding="utf-8")
    h.setFormatter(_LOG_FMT)
    return h


def _console_warnings_handler() -> logging.Handler:
    h = logging.StreamHandler(sys.stderr)
    h.setLevel(logging.WARNING)
    h.setFormatter(_LOG_FMT)
    return h


def configure_proxy_logging(logs_dir: Path) -> tuple[logging.Logger, logging.Logger]:
    logs_dir.mkdir(exist_ok=True)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(_fh(logs_dir, "proxy.log"))
    root_logger.addHandler(_console_warnings_handler())

    tcp_log = logging.getLogger("pf_tcp")
    tcp_log.setLevel(logging.INFO)
    tcp_log.propagate = False
    tcp_log.addHandler(_fh(logs_dir, "tcp.log"))
    tcp_log.addHandler(_console_warnings_handler())

    handshake_noise_filter = _ExpectedHandshakeNoiseFilter()
    logging.getLogger("websockets").addFilter(handshake_noise_filter)
    logging.getLogger("websockets.server").addFilter(handshake_noise_filter)

    return logging.getLogger("pf_proxy"), tcp_log
