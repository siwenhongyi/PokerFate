"""Game proxy bypass is derived from session endpoints; no live network calls."""

import asyncio
import logging
import os
import sys
import urllib.request
from types import SimpleNamespace

import pytest
from websockets.asyncio import client as ws_client
from websockets.uri import parse_uri

from pf_intercept.headless import __main__ as cli
from pf_intercept.headless import network
from pf_intercept.headless import session as hs
from pf_intercept.headless.login import LoginResult, ServerEntry


def get_proxy(uri):
    resolver = getattr(ws_client, "get_proxy", None)
    if resolver is None:
        pytest.skip("websockets < 15 has no automatic proxy selection")
    return resolver(uri)


@pytest.fixture(autouse=True)
def isolated_environment(monkeypatch):
    env = {k: v for k, v in os.environ.items() if not k.lower().endswith('_proxy')}
    monkeypatch.setattr(os, "environ", env)
    # Model macOS's fallback to system proxies, even on Linux test runners.
    monkeypatch.setattr(urllib.request, "getproxies", lambda:
                        urllib.request.getproxies_environment() or {
                            "https": "http://127.0.0.1:7897",
                            "socks": "http://127.0.0.1:7897",
                        })


def assert_http_direct(url):
    req = urllib.request.Request(url)
    original_host = req.host
    handler = urllib.request.ProxyHandler({"https": "http://127.0.0.1:7897"})
    handler.proxy_open(req, "http://127.0.0.1:7897", "https")
    assert req.host == original_host
    assert not req.has_proxy()


def test_dynamic_hosts_bypass_wss_and_http_preserving_other_proxy_routes(caplog):
    servers = [
        ServerEntry("wss://Game.Example:9012", "https://api.example/path/"),
        ServerEntry("wss://198.51.100.7:9013", "https://backup.example/"),
    ]
    with caplog.at_level(logging.INFO, logger="pf_headless"):
        hosts = network.configure_server_proxy_bypass(servers)
    assert set(hosts) == {"game.example", "api.example", "198.51.100.7", "backup.example"}
    assert os.environ["NO_PROXY"] == os.environ["no_proxy"]
    for s in servers:
        assert get_proxy(parse_uri(s.server_host)) is None
        assert_http_direct(s.http_host)
    assert get_proxy(parse_uri("wss://unrelated.example/")) == "socks5h://127.0.0.1:7897"
    assert "游戏服务自动绕过代理" in caplog.text
    assert "127.0.0.1:7897" not in caplog.text


def test_merge_both_cases_preserves_existing_entries_and_is_idempotent(monkeypatch):
    monkeypatch.setenv("NO_PROXY", "localhost,.internal,UPPER.example")
    monkeypatch.setenv("no_proxy", "127.0.0.1,lower.example,upper.example")
    monkeypatch.setenv("HTTPS_PROXY", "http://existing-proxy.example:8080")
    servers = [ServerEntry("wss://GAME.example:9012", "https://game.example/")]
    network.configure_server_proxy_bypass(servers)
    first = dict(os.environ)
    network.configure_server_proxy_bypass(servers)
    assert dict(os.environ) == first
    assert set(os.environ["no_proxy"].split(",")) == {
        "localhost", ".internal", "upper.example", "127.0.0.1", "lower.example", "game.example",
    }
    assert get_proxy(parse_uri("wss://unrelated.example/")) == "http://existing-proxy.example:8080"


def test_missing_http_endpoint_adds_actual_fallback_only():
    servers = [ServerEntry("wss://game.example:9012", "")]
    network.configure_server_proxy_bypass(servers, http_fallback="fallback.example")
    assert_http_direct("https://fallback.example/task/list")
    assert get_proxy(parse_uri(servers[0].server_host)) is None


@pytest.mark.parametrize("url", ["https://[2001:db8::1]:8443/", "https://198.51.100.3/"])
def test_ip_hosts_and_ports(url):
    network.configure_server_proxy_bypass([ServerEntry(url.replace("https:", "wss:"), url)])
    assert_http_direct(url)
    assert get_proxy(parse_uri(url.replace("https:", "wss:"))) is None


def test_hosts_never_include_url_secrets_or_global_wildcards(caplog):
    with caplog.at_level(logging.INFO, logger="pf_headless"):
        network.configure_server_proxy_bypass([
            ServerEntry("wss://user:secret@game.example:9012/path?token=private", ""),
            ServerEntry("wss://*/", ""),
            ServerEntry("wss://bad host/", ""),
        ])
    assert os.environ["no_proxy"] == "game.example"
    assert "secret" not in caplog.text and "private" not in caplog.text


def test_cli_applies_bypass_before_latency_probe(monkeypatch):
    async def run():
        stop = asyncio.Event()
        servers = [ServerEntry("wss://game.example:9012", "https://api.example/")]
        result = LoginResult(uid=42, rdkey="", authorization="", servers=servers)
        monkeypatch.setattr(cli, "_resume_result", lambda _: (result, 3, "test"))

        async def probe(items):
            assert get_proxy(parse_uri(items[0].server_host)) is None
            assert_http_direct(items[0].http_host)
            stop.set()
            return items

        monkeypatch.setattr(cli, "_order_servers_by_latency", probe)
        args = SimpleNamespace(no_notify=True, session_file=None)
        assert await cli._run(args, stop) == 0

    asyncio.run(run())


def test_session_applies_bypass_without_cli(monkeypatch):
    async def run():
        result = LoginResult(uid=42, rdkey="", authorization="", servers=[
            ServerEntry("wss://game.example:9012", "https://api.example/"),
        ])

        async def fake_connect(uri, **kwargs):
            assert get_proxy(parse_uri(uri)) is None
            assert_http_direct(result.servers[0].http_host)
            raise RuntimeError("fake handshake reached")

        monkeypatch.setattr(hs.websockets, "connect", fake_connect)
        session = hs.HeadlessSession(result, auto_rewards=False,
                                     bridge=SimpleNamespace(bankroll_dashboard=lambda: {}))
        with pytest.raises(RuntimeError, match="fake handshake reached"):
            await session.connect()

    asyncio.run(run())


@pytest.mark.parametrize("error", [cli.ResumeError("missing credentials"), RuntimeError("unexpected startup error")])
def test_main_startup_errors_are_logged(tmp_path, monkeypatch, caplog, error):
    monkeypatch.setattr(cli, "_PID_FILE", tmp_path / "headless.pid")
    monkeypatch.setattr(cli, "_setup_logging", lambda _: None)
    monkeypatch.setattr(sys, "argv", ["headless"])

    async def fail(*args):
        raise error

    monkeypatch.setattr(cli, "_run", fail)
    with caplog.at_level(logging.ERROR, logger="pf_headless"):
        assert cli.main() == 2
    assert str(error) in caplog.text
    assert not cli._PID_FILE.exists()
