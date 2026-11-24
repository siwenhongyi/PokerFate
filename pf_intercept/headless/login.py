"""Session result types + line latency probe for the headless client.

This module used to also POST /login itself (mirroring LoginModel.lua), but
that path is dead: the login request requires a risk-control token minted by
the game client's own YiDun SDK at runtime (see "风控" in
pf_reverse/REVERSE_NOTES.md and pf_reverse/output/lua/src/sdk/YiDunHelper.lua),
which has no pure-Python equivalent — sending it empty gets rejected in
practice. The only working way to get a session is to let a real device log
in once and capture the result; see pf_intercept.headless.harvest_session.

What's left here:
    LoginResult / ServerEntry / LoginError   — resuming a harvested session
                                                (pf_intercept.headless.__main__
                                                reads local/secrets/headless_session.json
                                                straight into a LoginResult)
    measure_ping                             — /ping latency, used to order
                                                the saved server list the same
                                                way the client's Loginline does
"""

from __future__ import annotations

import json
import logging
from pf_intercept import config
import time
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pf_intercept.game_api.http import GAME_HTTP_SSL_CTX, _UNITY_USER_AGENT

log = logging.getLogger("pf_headless")

_PROJECT_ROOT = Path(__file__).resolve().parents[2]


class LoginError(RuntimeError):
    def __init__(self, message: str, code: int | None = None) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class ServerEntry:
    server_host: str   # wss://ip:port
    http_host: str     # http://ip:port/  (may be empty)


@dataclass
class LoginResult:
    uid: int
    rdkey: str
    authorization: str
    servers: list[ServerEntry] = field(default_factory=list)
    code: int = 0
    login_ip: str = ""
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    def redacted(self) -> str:
        return (
            f"uid={self.uid} code={self.code} servers={len(self.servers)} "
            f"login_ip={self.login_ip or '-'}"
        )


def measure_ping(http_host: str, *, timeout: float = 4.0) -> float:
    """Latency (ms) to ``http_host + "ping"`` — mirrors Loginline.lua's probe.

    Returns +inf when unreachable (the client's 999 marker). Startup adds the
    saved game hosts to no_proxy before probing, so this uses the same direct
    network path as the WSS session and game HTTP requests."""
    if not http_host:
        return float("inf")
    url = http_host.rstrip("/") + "/ping"
    t0 = time.monotonic()
    try:
        req = urllib.request.Request(url, method="GET", headers={"User-Agent": _UNITY_USER_AGENT})
        with urllib.request.urlopen(req, timeout=timeout, context=GAME_HTTP_SSL_CTX) as resp:
            resp.read(32)
        return (time.monotonic() - t0) * 1000.0
    except Exception as exc:
        log.debug("[PING] %s 不可达: %s", url, exc)
        return float("inf")


def load_session(path: Path):
    """Load saved credentials and routes → (LoginResult, chnl, client_version)."""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        entries = [ServerEntry(s["server_host"], s.get("http_host", "")) for s in data.get("servers", [])]
        uid = int(data["uid"])
        rdkey = str(data["rdkey"])
    except FileNotFoundError:
        raise LoginError(f"会话凭证不存在: {path}（请在设备上登录一次薅凭证）")
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        raise LoginError(f"会话凭证无效 {path}: {exc}（请重新薅凭证）")
    if not entries:
        raise LoginError(f"会话凭证里没有服务器列表: {path}")
    result = LoginResult(uid=uid, rdkey=rdkey, authorization=str(data.get("authorization", "")),
                         servers=entries, code=0, login_ip=str(data.get("login_ip", "")))
    return result, int(data.get("chnl", config.GAMEDATA_CHNL)), str(data.get("version", config.GAME_HTTP_VERSION))
