"""HTTP 调用 Bark API 与对外 ``notify`` 入口。"""

from __future__ import annotations

import json
import logging
import ssl
import threading
import urllib.error
import urllib.request
from typing import Any

import certifi

from pf_notify.config import BARK_API_BASE, get_bark_key
from pf_notify.templates import format_bark_message, format_bark_options

log = logging.getLogger("pf_notify")

_BARK_SSL = ssl.create_default_context(cafile=certifi.where())


def _send_bark_http(
    device_key: str,
    title: str,
    body: str,
    icon: str | None = None,
    options: dict[str, Any] | None = None,
) -> None:
    url = f"{BARK_API_BASE}/push"
    data: dict[str, Any] = {"device_key": device_key, "title": title, "body": body}
    if icon:
        data["icon"] = icon
    if options:
        data.update(options)
    payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        method="POST",
        headers={"Content-Type": "application/json; charset=utf-8"},
    )
    with urllib.request.urlopen(req, timeout=10, context=_BARK_SSL) as resp:
        resp.read()


def notify(event: str, **fields: Any) -> None:
    key = get_bark_key()
    if not key:
        log.debug("pf_notify: skipped %s (no Bark key)", event)
        return

    fields_dict = dict(fields)
    title, body, icon = format_bark_message(event, fields_dict)
    options = format_bark_options(event, fields_dict)

    def _run() -> None:
        try:
            _send_bark_http(key, title, body, icon, options)
        except urllib.error.HTTPError as e:
            log.warning("pf_notify: Bark HTTP %s event=%s", e.code, event)
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            log.warning("pf_notify: Bark failed event=%s err=%s", event, e)
        except Exception as e:
            log.warning("pf_notify: Bark failed event=%s err=%s", event, e)

    threading.Thread(target=_run, daemon=True).start()
