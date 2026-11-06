from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable

from pf_intercept.config import PREFERRED_WSS_HOSTS, SERVER_HOST
from pf_intercept.proxy.http_parse import (
    _extract_http_host,
    _extract_http_path,
    _extract_sni_hostname,
    _http_host_header,
    _rewrite_http_host_header,
)
from pf_intercept.proxy.routes import (
    RuntimeRoute,
    _connect_first_success,
    _get_host_lock,
    _host_ok_ip_cache,
    _persist_ip_cache,
    _resolve_host_candidates,
    _select_upstream_route,
)
from pf_intercept.proxy.tls import _make_client_ssl


def _peer_is_loopback(peer) -> bool:
    if not peer:
        return False
    host = peer[0] if isinstance(peer, tuple) and peer else str(peer)
    return host == "::1" or host.startswith("127.")


async def _pipe_raw(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    try:
        while True:
            data = await reader.read(65536)
            if not data:
                break
            writer.write(data)
            await writer.drain()
    except (ConnectionResetError, asyncio.IncompleteReadError):
        pass
    finally:
        writer.close()


async def _open_route_http_upstream(
    route: RuntimeRoute,
    *,
    timeout: float = 5.0,
) -> tuple[asyncio.StreamReader, asyncio.StreamWriter] | None:
    if not route.http_tcp_host or not route.http_port or not route.http_scheme:
        return None

    ssl_ctx = None
    server_hostname = None
    if route.http_scheme == "https":
        ssl_ctx = _make_client_ssl()
        server_hostname = route.http_upstream_host or route.visible_host

    conn = asyncio.open_connection(
        route.http_tcp_host,
        route.http_port,
        ssl=ssl_ctx,
        server_hostname=server_hostname,
    )
    return await asyncio.wait_for(conn, timeout=timeout)


async def handle_passthrough(
    client_reader: asyncio.StreamReader,
    client_writer: asyncio.StreamWriter,
    real_port: int,
    *,
    real_server_sni: Callable[[], str],
    log: logging.Logger,
    tcp_log: logging.Logger,
) -> None:
    peer = client_writer.get_extra_info("peername")
    if _peer_is_loopback(peer):
        tcp_log.info("[TCP] drop loopback passthrough from %s on port %d", peer, real_port)
        client_writer.close()
        try:
            await client_writer.wait_closed()
        except Exception:
            pass
        return

    initial = b""
    try:
        initial = await asyncio.wait_for(client_reader.read(4096), timeout=0.2)
    except TimeoutError:
        initial = b""
    except Exception:
        log.exception("[TCP] failed to read initial client bytes from %s", peer)
        initial = b""

    target_host = _extract_sni_hostname(initial) or _extract_http_host(initial) or real_server_sni() or SERVER_HOST
    if ":" in target_host:
        target_host = target_host.split(":", 1)[0]
    protocol = "TLS" if initial and initial[0:1] == b"\x16" else "HTTP"

    srv_reader: asyncio.StreamReader | None = None
    srv_writer: asyncio.StreamWriter | None = None
    chosen_ip: str | None = None
    route: RuntimeRoute | None = None

    # Plain HTTP can be paired with the same server entry selected for WSS:
    # - host mode: client still sees http://host, upstream may be HTTPS host.
    # - ip mode: client still sees http://host, upstream goes to server IP:8888.
    if protocol == "HTTP" and target_host in set(PREFERRED_WSS_HOSTS) | {SERVER_HOST}:
        try:
            route = await _select_upstream_route(target_host)
            opened = await _open_route_http_upstream(route)
            if opened is not None:
                srv_reader, srv_writer = opened
                chosen_ip = route.http_tcp_host
                if route.mode == "ip" and route.http_upstream_host:
                    initial = _rewrite_http_host_header(
                        initial,
                        _http_host_header(
                            route.http_upstream_host,
                            route.http_scheme,
                            route.http_port,
                        ),
                    )
        except (OSError, asyncio.TimeoutError) as exc:
            tcp_log.warning(
                "[TCP] route HTTP upstream %s://%s:%s (%s:%s) failed: %s",
                route.http_scheme if route else "-",
                route.http_upstream_host if route else "-",
                route.http_port if route else "-",
                route.http_tcp_host if route else "-",
                route.http_port if route else "-",
                exc,
            )
        except Exception:
            log.exception("[TCP] unexpected route HTTP upstream failure for %s", target_host)

    # Try cached-good IP first; this avoids DNS + candidate racing for stable hosts.
    cached = _host_ok_ip_cache.get(target_host)
    if srv_writer is None and cached:
        try:
            conn = asyncio.open_connection(cached, real_port)
            srv_reader, srv_writer = await asyncio.wait_for(conn, timeout=2.5)
            chosen_ip = cached
        except (OSError, asyncio.TimeoutError) as exc:
            tcp_log.warning("[TCP] cached upstream %s:%d failed: %s", cached, real_port, exc)
        except Exception:
            log.exception("[TCP] unexpected cached upstream failure %s:%d", cached, real_port)

    candidates: list[str] = []

    # Fallback: one coroutine per host computes candidates / selects reachable IP,
    # others wait and then consume the updated cache.
    if srv_writer is None:
        lock = _get_host_lock(target_host)
        async with lock:
            cached = _host_ok_ip_cache.get(target_host)
            if cached:
                try:
                    conn = asyncio.open_connection(cached, real_port)
                    srv_reader, srv_writer = await asyncio.wait_for(conn, timeout=2.5)
                    chosen_ip = cached
                except (OSError, asyncio.TimeoutError) as exc:
                    tcp_log.warning("[TCP] cached upstream %s:%d failed: %s", cached, real_port, exc)
                except Exception:
                    log.exception("[TCP] unexpected cached upstream failure %s:%d", cached, real_port)

            if srv_writer is None:
                if cached:
                    candidates.append(cached)
                for ip in _resolve_host_candidates(target_host, force_refresh=False):
                    if ip not in candidates:
                        candidates.append(ip)
                raced = await _connect_first_success(candidates, real_port, timeout=5.0)
                if raced is None:
                    # Only refresh DNS when current recorded candidates fail.
                    refreshed: list[str] = []
                    for ip in _resolve_host_candidates(target_host, force_refresh=True):
                        if ip not in refreshed:
                            refreshed.append(ip)
                    if refreshed:
                        candidates = refreshed
                        raced = await _connect_first_success(candidates, real_port, timeout=5.0)

                if raced is not None:
                    chosen_ip, srv_reader, srv_writer = raced
                    _host_ok_ip_cache[target_host] = chosen_ip
                    _persist_ip_cache()

    if srv_writer is None or srv_reader is None or chosen_ip is None:
        tcp_log.warning(
            "[TCP] no reachable upstream for %s:%d; host=%s; candidates=%s",
            peer, real_port, target_host, candidates,
        )
        client_writer.close()
        return

    path = _extract_http_path(initial) if protocol == "HTTP" else None
    if path:
        if route is not None and route.http_tcp_host == chosen_ip:
            tcp_log.info(
                "[TCP] %s -> %s:%d (%s://%s:%s via %s:%s route=%s)  %s %s",
                peer,
                target_host,
                real_port,
                route.http_scheme,
                route.http_upstream_host,
                route.http_port,
                route.http_tcp_host,
                route.http_port,
                route.mode,
                protocol,
                path,
            )
        else:
            tcp_log.info(
                "[TCP] %s -> %s:%d (%s)  %s %s",
                peer, target_host, real_port, chosen_ip, protocol, path,
            )
    else:
        tcp_log.info("[TCP] %s -> %s:%d (%s)  [%s]", peer, target_host, real_port, chosen_ip, protocol)
    if route is None or route.mode == "host":
        _host_ok_ip_cache[target_host] = chosen_ip
        _persist_ip_cache()

    t0 = asyncio.get_event_loop().time()
    try:
        if initial:
            srv_writer.write(initial)
            await srv_writer.drain()
        await asyncio.gather(
            _pipe_raw(client_reader, srv_writer),
            _pipe_raw(srv_reader, client_writer),
        )
    except Exception as exc:
        tcp_log.warning("[TCP] pass-through error: %s", exc)
    finally:
        elapsed = asyncio.get_event_loop().time() - t0
        tcp_log.info("[TCP] closed %s -> %s:%d  (%.1fs)", peer, target_host, real_port, elapsed)
        client_writer.close()
