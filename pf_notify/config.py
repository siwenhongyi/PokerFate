"""Bark 设备 Key 的内存状态与从文件加载。"""

from __future__ import annotations

import logging
import pathlib

BARK_API_BASE = "https://api.day.app"
log = logging.getLogger("pf_notify")

_bark_key: str | None = None


def set_bark_key(key: str | None) -> None:
    global _bark_key
    if key is None:
        _bark_key = None
        return
    k = str(key).strip()
    _bark_key = k or None


def get_bark_key() -> str | None:
    return _bark_key


def load_bark_key_file(path: str | pathlib.Path) -> str | None:
    p = pathlib.Path(path)
    try:
        text = p.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    except OSError as exc:
        log.warning("pf_notify: failed to read Bark key file %s: %s", p, exc)
        return None
    line = text.strip().splitlines()[0].strip() if text.strip() else ""
    return line or None
