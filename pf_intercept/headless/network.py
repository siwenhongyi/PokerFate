"""Bypass proxies for the game endpoints returned with the saved login session."""

from __future__ import annotations

import logging
import os
import urllib.request
from collections.abc import Iterable
from typing import TYPE_CHECKING
from urllib.parse import urlsplit

if TYPE_CHECKING:
    from pf_intercept.headless.login import ServerEntry

log = logging.getLogger("pf_headless")


def _hosts(address: str) -> tuple[str, ...]:
    if not address:
        return ()
    try:
        parsed = urlsplit(address.strip() if "://" in address else f"//{address.strip()}")
        host = parsed.hostname
    except ValueError:
        return ()
    if not host or any(c.isspace() or c in ",*" for c in host):
        return ()
    # urllib sees bracketed IPv6 authorities; websockets passes an unbracketed
    # host to proxy_bypass. Cover both without adding a port-specific exception.
    return (host, f"[{host}]") if ":" in host else (host,)


def configure_server_proxy_bypass(
    servers: Iterable[ServerEntry], *, http_fallback: str = "",
) -> tuple[str, ...]:
    """Merge game hosts into this process's NO_PROXY / no_proxy before any I/O.

    No system settings or shell files are changed. Existing bypass entries and
    effective proxy addresses are preserved; game URLs themselves aren't logged
    because only their hostnames are relevant here.
    """
    hosts = sorted({
        host
        for server in servers
        for address in (server.server_host, server.http_host or http_fallback)
        for host in _hosts(address)
    })
    if not hosts:
        return ()

    entries = []
    seen = set()
    for entry in [*os.environ.get("no_proxy", "").split(","),
                  *os.environ.get("NO_PROXY", "").split(","), *hosts]:
        entry = entry.strip()
        if entry and entry.lower() not in seen:
            entries.append(entry)
            seen.add(entry.lower())
    value = ",".join(entries)

    # On macOS, merely setting no_proxy makes getproxies() stop reading system
    # proxy addresses. Retain those effective addresses for unrelated traffic.
    proxies = urllib.request.getproxies()
    env_proxies = urllib.request.getproxies_environment()
    for scheme, address in proxies.items():
        if scheme != "no" and scheme not in env_proxies:
            os.environ[f"{scheme}_proxy"] = address
    changed = any(os.environ.get(key) != value for key in ("NO_PROXY", "no_proxy"))
    os.environ["NO_PROXY"] = os.environ["no_proxy"] = value
    if changed:
        log.info("[NETWORK] 游戏服务自动绕过代理 hosts=%s", ",".join(hosts))
    return tuple(hosts)
