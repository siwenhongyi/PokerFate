from __future__ import annotations

import asyncio
import ipaddress
import json
import logging
import socket
import struct
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from pf_intercept.config import (
    EXTERNAL_DNS_SERVERS,
    PREFERRED_WSS_HOSTS,
    SERVER_WSS_PORT,
)

log = logging.getLogger("pf_proxy")

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_DATA_DIR = _PROJECT_ROOT / "data"
_DATA_DIR.mkdir(exist_ok=True)
_IP_CACHE_FILE = _DATA_DIR / "ip_cache.json"
_ORIGINAL_RESPONSE_FILE = _DATA_DIR / "force_domain_original_response.json"
_SELECTED_ROUTE_FILE = _DATA_DIR / "selected_route.json"
_ROUTE_HOST_FAST_MS = 100.0
_ROUTE_CACHE_TTL_SEC = 120.0


def _load_ip_cache() -> dict[str, str]:
    try:
        return json.loads(_IP_CACHE_FILE.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except Exception:
        logging.getLogger("pf_proxy").exception(
            "[IP cache] failed to load %s", _IP_CACHE_FILE
        )
        return {}


_host_ok_ip_cache: dict[str, str] = _load_ip_cache()
_host_dns_cache: dict[str, list[str]] = {}
_host_connect_locks: dict[str, asyncio.Lock] = {}
_route_cache: dict[str, tuple[float, float | None, "RuntimeRoute"]] = {}
_route_select_locks: dict[str, asyncio.Lock] = {}


def _persist_ip_cache() -> None:
    try:
        _IP_CACHE_FILE.write_text(
            json.dumps(_host_ok_ip_cache, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    except Exception as exc:
        log.warning("[IP cache] persist failed for %s: %s", _IP_CACHE_FILE, exc)


def _get_host_lock(hostname: str) -> asyncio.Lock:
    lock = _host_connect_locks.get(hostname)
    if lock is None:
        lock = asyncio.Lock()
        _host_connect_locks[hostname] = lock
    return lock


def _dns_query_a(hostname: str, nameserver: str) -> list[str]:
    """Direct UDP DNS A-record query bypassing OS resolver / hosts file."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    except OSError as exc:
        log.warning("[DNS] socket create failed for %s via %s: %s", hostname, nameserver, exc)
        return []
    sock.settimeout(3.0)
    ips: list[str] = []
    try:
        qname = b"".join(bytes([len(p)]) + p.encode() for p in hostname.split(".")) + b"\x00"
        query = b"\x12\x34\x01\x00\x00\x01\x00\x00\x00\x00\x00\x00" + qname + b"\x00\x01\x00\x01"
        sock.sendto(query, (nameserver, 53))
        data, _ = sock.recvfrom(512)
        pos = 12 + len(qname) + 4
        for _ in range(struct.unpack(">H", data[6:8])[0]):
            if data[pos] & 0xC0 == 0xC0:
                pos += 2
            else:
                while data[pos]:
                    pos += data[pos] + 1
                pos += 1
            rtype, _, _, rdlen = struct.unpack(">HHIH", data[pos:pos + 10])
            pos += 10
            if rtype == 1 and rdlen == 4:
                ip = socket.inet_ntoa(data[pos:pos + 4])
                if ip not in ips:
                    ips.append(ip)
            pos += rdlen
    except Exception as exc:
        log.debug("[DNS] query failed for %s: %s", hostname, exc)
    finally:
        sock.close()
    return ips


def _resolve_host_candidates(hostname: str, force_refresh: bool = False) -> list[str]:
    """Resolve host from external DNS servers + system resolver fallback."""
    cached = _host_dns_cache.get(hostname)
    if cached and not force_refresh:
        return list(cached)

    candidates: list[str] = []
    for dns in EXTERNAL_DNS_SERVERS:
        for ip in _dns_query_a(hostname, dns):
            if ip not in candidates:
                candidates.append(ip)

    try:
        infos = socket.getaddrinfo(hostname, None, socket.AF_INET, socket.SOCK_STREAM)
        for info in infos:
            ip = info[4][0]
            if ip not in candidates and not ip.startswith("127."):
                candidates.append(ip)
    except OSError as exc:
        log.warning("[DNS] system resolver failed for %s: %s", hostname, exc)
    except Exception:
        log.exception("[DNS] unexpected resolver failure for %s", hostname)

    _host_dns_cache[hostname] = list(candidates)
    return candidates


async def _connect_first_success(
    ips: list[str],
    port: int,
    timeout: float,
) -> tuple[str, asyncio.StreamReader, asyncio.StreamWriter] | None:
    """Attempt multiple upstream TCP connections concurrently and return first success."""
    if not ips:
        return None

    async def _one(ip: str):
        conn = asyncio.open_connection(ip, port)
        reader, writer = await asyncio.wait_for(conn, timeout=timeout)
        return ip, reader, writer

    tasks = [asyncio.create_task(_one(ip)) for ip in ips]
    try:
        pending = set(tasks)
        while pending:
            done, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
            for d in done:
                exc = d.exception()
                if exc is None:
                    ip, reader, writer = d.result()
                    for p in pending:
                        p.cancel()
                    if pending:
                        await asyncio.gather(*pending, return_exceptions=True)
                    return ip, reader, writer
        return None
    finally:
        for task in tasks:
            if not task.done():
                task.cancel()


@dataclass(frozen=True)
class ServerRouteCandidate:
    mode: str
    server_host: str
    wss_host: str
    wss_port: int
    http_scheme: str | None
    http_host: str | None
    http_port: int | None


@dataclass(frozen=True)
class ProbedRoute:
    candidate: ServerRouteCandidate
    wss_tcp_host: str
    latency_ms: float | None


@dataclass(frozen=True)
class RuntimeRoute:
    mode: str
    visible_host: str
    wss_upstream_host: str
    wss_tcp_host: str
    wss_tcp_port: int
    wss_latency_ms: float | None
    http_scheme: str | None
    http_upstream_host: str | None
    http_tcp_host: str | None
    http_port: int | None


def _get_route_lock(visible_host: str) -> asyncio.Lock:
    lock = _route_select_locks.get(visible_host)
    if lock is None:
        lock = asyncio.Lock()
        _route_select_locks[visible_host] = lock
    return lock


def _is_ip_literal(host: str | None) -> bool:
    if not host:
        return False
    try:
        ipaddress.ip_address(host)
        return True
    except ValueError:
        return False


def _parse_url_endpoint(url: str | None, default_scheme: str) -> tuple[str, str, int] | None:
    if not url:
        return None
    raw = str(url).strip()
    if not raw:
        return None
    if "://" not in raw:
        raw = f"{default_scheme}://{raw}"
    try:
        parsed = urlparse(raw)
    except Exception:
        return None
    host = parsed.hostname
    if not host:
        return None
    scheme = parsed.scheme or default_scheme
    default_port = 443 if scheme in ("wss", "https") else 80
    try:
        port = parsed.port or default_port
    except ValueError:
        port = default_port
    return scheme, host, port


def _load_original_server_response() -> dict | None:
    try:
        return json.loads(_ORIGINAL_RESPONSE_FILE.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except Exception as exc:
        log.warning("[ROUTE] failed to load %s: %s", _ORIGINAL_RESPONSE_FILE, exc)
        return None


def _original_response_mtime() -> float | None:
    try:
        return _ORIGINAL_RESPONSE_FILE.stat().st_mtime
    except FileNotFoundError:
        return None
    except Exception:
        return None


def _parse_server_route_candidates(data: dict | None, visible_host: str) -> list[ServerRouteCandidate]:
    servers = ((data or {}).get("server") or {}).get("server") or []
    candidates: list[ServerRouteCandidate] = []

    for entry in servers:
        if not isinstance(entry, dict):
            continue
        wss = _parse_url_endpoint(entry.get("server_host"), "wss")
        if wss is None:
            continue
        _, wss_host, wss_port = wss
        if wss_port == 443:
            # 443 is used by the local transparent HTTPS passthrough; using it
            # as a game WSS target conflicts with the current deployment.
            continue

        http = _parse_url_endpoint(entry.get("http_host"), "http")
        http_scheme: str | None = None
        http_host: str | None = None
        http_port: int | None = None
        if http is not None:
            http_scheme, http_host, http_port = http

        is_ip = _is_ip_literal(wss_host)
        if not is_ip and wss_host not in set(PREFERRED_WSS_HOSTS) | {visible_host}:
            continue

        candidates.append(
            ServerRouteCandidate(
                mode="ip" if is_ip else "host",
                server_host=str(entry.get("server_host") or ""),
                wss_host=wss_host,
                wss_port=wss_port,
                http_scheme=http_scheme,
                http_host=http_host,
                http_port=http_port,
            )
        )

    if candidates:
        return candidates

    return [
        ServerRouteCandidate(
            mode="host",
            server_host=f"wss://{visible_host}:{SERVER_WSS_PORT}",
            wss_host=visible_host,
            wss_port=SERVER_WSS_PORT,
            http_scheme=None,
            http_host=None,
            http_port=None,
        )
    ]


async def _tcp_connect_latency_ms(host: str, port: int, timeout: float = 2.0) -> float | None:
    loop = asyncio.get_event_loop()
    start = loop.time()
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port),
            timeout=timeout,
        )
        elapsed = (loop.time() - start) * 1000.0
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass
        _ = reader
        return elapsed
    except Exception:
        return None


async def _probe_route_candidate(candidate: ServerRouteCandidate) -> ProbedRoute:
    if _is_ip_literal(candidate.wss_host):
        hosts = [candidate.wss_host]
    else:
        hosts = _resolve_host_candidates(candidate.wss_host, force_refresh=False)
        if not hosts:
            hosts = [candidate.wss_host]

    async def _probe_one(host: str) -> tuple[str, float | None]:
        return host, await _tcp_connect_latency_ms(host, candidate.wss_port)

    results = await asyncio.gather(
        *(_probe_one(host) for host in hosts),
        return_exceptions=True,
    )
    best_host = hosts[0]
    best_latency: float | None = None
    for result in results:
        if isinstance(result, Exception):
            continue
        host, latency = result
        if latency is None:
            continue
        if best_latency is None or latency < best_latency:
            best_host = host
            best_latency = latency
    return ProbedRoute(candidate=candidate, wss_tcp_host=best_host, latency_ms=best_latency)


def _choose_probed_route(probed: list[ProbedRoute]) -> ProbedRoute | None:
    usable = [route for route in probed if route.latency_ms is not None]
    if not usable:
        return probed[0] if probed else None

    host_routes = [route for route in usable if route.candidate.mode == "host"]
    best_host = min(host_routes, key=lambda r: r.latency_ms) if host_routes else None
    if best_host is not None and best_host.latency_ms is not None and best_host.latency_ms <= _ROUTE_HOST_FAST_MS:
        return best_host

    return min(usable, key=lambda r: r.latency_ms)


def _first_resolved_host(host: str | None) -> str | None:
    if not host:
        return None
    if _is_ip_literal(host):
        return host
    candidates = _resolve_host_candidates(host, force_refresh=False)
    return candidates[0] if candidates else host


def _runtime_route_from_probe(visible_host: str, probed: ProbedRoute) -> RuntimeRoute:
    c = probed.candidate
    http_tcp_host = _first_resolved_host(c.http_host)
    return RuntimeRoute(
        mode=c.mode,
        visible_host=visible_host,
        wss_upstream_host=c.wss_host,
        wss_tcp_host=probed.wss_tcp_host,
        wss_tcp_port=c.wss_port,
        wss_latency_ms=probed.latency_ms,
        http_scheme=c.http_scheme,
        http_upstream_host=c.http_host,
        http_tcp_host=http_tcp_host,
        http_port=c.http_port,
    )


def _persist_selected_route(route: RuntimeRoute) -> None:
    try:
        _SELECTED_ROUTE_FILE.write_text(
            json.dumps(
                {
                    "visible_host": route.visible_host,
                    "mode": route.mode,
                    "wss_upstream_host": route.wss_upstream_host,
                    "wss_tcp_host": route.wss_tcp_host,
                    "wss_tcp_port": route.wss_tcp_port,
                    "wss_latency_ms": route.wss_latency_ms,
                    "http_scheme": route.http_scheme,
                    "http_upstream_host": route.http_upstream_host,
                    "http_tcp_host": route.http_tcp_host,
                    "http_port": route.http_port,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
    except Exception as exc:
        log.warning("[ROUTE] failed to persist selected route: %s", exc)


async def _select_upstream_route(
    visible_host: str,
    *,
    force_refresh: bool = False,
) -> RuntimeRoute:
    mtime = _original_response_mtime()
    now = asyncio.get_event_loop().time()
    cached = _route_cache.get(visible_host)
    if cached and not force_refresh:
        expires_at, cached_mtime, route = cached
        if now < expires_at and cached_mtime == mtime:
            return route

    lock = _get_route_lock(visible_host)
    async with lock:
        cached = _route_cache.get(visible_host)
        now = asyncio.get_event_loop().time()
        if cached and not force_refresh:
            expires_at, cached_mtime, route = cached
            if now < expires_at and cached_mtime == mtime:
                return route

        candidates = _parse_server_route_candidates(
            _load_original_server_response(),
            visible_host,
        )
        probed = await asyncio.gather(
            *(_probe_route_candidate(candidate) for candidate in candidates),
            return_exceptions=True,
        )
        routes = [route for route in probed if isinstance(route, ProbedRoute)]
        chosen = _choose_probed_route(routes)
        if chosen is None:
            chosen = ProbedRoute(
                candidate=ServerRouteCandidate(
                    mode="host",
                    server_host=f"wss://{visible_host}:{SERVER_WSS_PORT}",
                    wss_host=visible_host,
                    wss_port=SERVER_WSS_PORT,
                    http_scheme=None,
                    http_host=None,
                    http_port=None,
                ),
                wss_tcp_host=visible_host,
                latency_ms=None,
            )

        route = _runtime_route_from_probe(visible_host, chosen)
        latency_text = ", ".join(
            f"{r.candidate.mode}:{r.candidate.wss_host}:{r.candidate.wss_port}"
            f"={r.latency_ms:.0f}ms" if r.latency_ms is not None
            else f"{r.candidate.mode}:{r.candidate.wss_host}:{r.candidate.wss_port}=fail"
            for r in routes
        )
        log.info(
            "[ROUTE] selected %s route for %s: wss_tcp=%s:%d http=%s://%s:%s; probes=[%s]",
            route.mode,
            visible_host,
            route.wss_tcp_host,
            route.wss_tcp_port,
            route.http_scheme or "-",
            route.http_upstream_host or "-",
            route.http_port or "-",
            latency_text,
        )
        _persist_selected_route(route)
        _route_cache[visible_host] = (
            now + _ROUTE_CACHE_TTL_SEC,
            mtime,
            route,
        )
        return route
