"""HTTP login, mirroring LoginModel.lua (emailLogin / guestLogin) + Net.lua.

Request body (Net:post adds random/ts/sign/chnl via addSaltArgs):

    type, token, os, imei, lang, verify,
    yidun_risk_check = {account, ip, os, sceneData{...}, token},
    adjust_id, push_token, random, ts, sign, chnl

`verify` is the password for EMAIL login and
md5(os .. imei .. CHECK_SALT) for GUEST login (LoginModel:getCheckMd5).

The YiDun device-fingerprint token is sent empty: the client itself falls
back to '' when its SDK version check fails, so the server accepts it.

Response (code == 0, or -6 "risk verify warning" which the client treats as
success): uid, rdkey, authorization, server.server[] {http_host, server_host}.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pf_intercept import config
from pf_intercept.game_api.http import (
    GAME_HTTP_SSL_CTX,
    _UNITY_USER_AGENT,
    add_signed_args,
)
from pf_intercept.headless.credentials import LOGIN_TYPE_EMAIL, Account

log = logging.getLogger("pf_headless")

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_TOKEN_FILE = _PROJECT_ROOT / "data" / "auth_token.txt"
# LoginModel:getCheckMd5 — appended to os..imei for guest `verify`.
_CHECK_SALT = "ba2798edafa12f3ae08822a3203158cb"
# Constants.lua G_HTTP_URL / _2 (release, non-cn channel); tried in order.
LOGIN_HOSTS = (
    "https://ga-foreign.poker-fate.com/",
    "https://awsb-entry.poker-fate.com/",
)
# Login codes the client treats as success (LoginModel:_onLoginSuccess).
_OK_CODES = {0, -6}


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


def guest_verify(os_name: str, device_id: str) -> str:
    return hashlib.md5(f"{os_name}{device_id}{_CHECK_SALT}".encode("utf-8")).hexdigest()


def build_login_payload(account: Account) -> dict[str, Any]:
    """Body exactly as LoginModel builds it, before addSaltArgs."""
    if account.login_type == LOGIN_TYPE_EMAIL:
        verify = account.secret
    else:
        verify = guest_verify(account.os, account.device_id)
    return {
        "type": int(account.login_type),
        "token": account.token,
        "os": account.os,
        "imei": account.device_id,
        "lang": account.lang,
        "verify": verify,
        "yidun_risk_check": {
            "account": "unknown",
            "ip": "unknown",
            "os": account.os,
            "sceneData": {
                "registerOrLogType": str(account.login_type),
                "operationType": "log",
                "appChannel": "1",
            },
            "token": "",
        },
        "adjust_id": "",
        "push_token": "",
        "mask": "LoginHttp",   # LoginModel:addLoginArgs — UI mask key, but it is in the body
    }


def _http_headers(lang: str, version: str | None = None) -> dict[str, str]:
    # Net:getHttpHeader(): Content-Type / Version / Authorization / Lang
    return {
        "Content-Type": "application/json; charset=utf-8",
        "Version": str(version or config.GAME_HTTP_VERSION),
        "Authorization": "",
        "Lang": lang,
        "User-Agent": _UNITY_USER_AGENT,
        "Accept": "*/*",
        "X-Unity-Version": "2022.3.62f3",
    }


def parse_login_response(data: dict[str, Any]) -> LoginResult:
    code = int(data.get("code", 0) or 0)
    if code not in _OK_CODES:
        raise LoginError(f"登录失败 code={code} reason={data.get('reason') or data.get('msg') or '-'}", code)
    uid = data.get("uid")
    rdkey = data.get("rdkey")
    auth = data.get("authorization")
    if uid is None or not rdkey or not auth:
        raise LoginError("登录响应缺少 uid/rdkey/authorization", code)
    servers: list[ServerEntry] = []
    for item in (data.get("server") or {}).get("server") or []:
        if not isinstance(item, dict):
            continue
        wss = str(item.get("server_host") or "").strip()
        if wss:
            servers.append(ServerEntry(wss, str(item.get("http_host") or "").strip()))
    if not servers:
        raise LoginError("登录响应没有可用的 server_host", code)
    return LoginResult(
        uid=int(uid),
        rdkey=str(rdkey),
        authorization=str(auth),
        servers=servers,
        code=code,
        login_ip=str(data.get("login_ip") or ""),
        raw=data,
    )


def _post_json(url: str, body: dict[str, Any], headers: dict[str, str], timeout: float) -> dict[str, Any]:
    raw = json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=raw, method="POST")
    for k, v in headers.items():
        req.add_header(k, v)
    with urllib.request.urlopen(req, timeout=timeout, context=GAME_HTTP_SSL_CTX) as resp:
        return json.loads(resp.read())


def http_login(
    account: Account,
    *,
    hosts: tuple[str, ...] = LOGIN_HOSTS,
    timeout: float = 10.0,
    save_token: bool = True,
    http_version: str | None = None,
) -> LoginResult:
    """POST /login; tries each host in turn like UrlManager:nextHttpUrl."""
    body = add_signed_args(build_login_payload(account), chnl=account.chnl)
    headers = _http_headers(account.lang, http_version)
    last_exc: Exception | None = None
    for host in hosts:
        url = host.rstrip("/") + "/login"
        log.info("[LOGIN] POST %s (%s)", url, account.redacted())
        try:
            data = _post_json(url, body, headers, timeout)
        except Exception as exc:
            log.warning("[LOGIN] %s 请求失败: %s: %s", url, type(exc).__name__, exc)
            last_exc = exc
            continue
        result = parse_login_response(data)   # raises LoginError on bad code
        if result.code == -6:
            log.warning("[LOGIN] 服务端返回 -6（风控验证警告），客户端视为登录成功，继续。")
        log.info("[LOGIN] ok %s", result.redacted())
        if save_token:
            try:
                _TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
                _TOKEN_FILE.write_text(result.authorization, encoding="utf-8")
            except OSError as exc:
                log.warning("[LOGIN] token 写入 %s 失败: %s", _TOKEN_FILE, exc)
        return result
    raise LoginError(f"所有登录地址均失败: {last_exc}")


def measure_ping(http_host: str, *, timeout: float = 4.0) -> float:
    """Latency (ms) to ``http_host + "ping"`` — mirrors Loginline.lua's probe.

    Returns +inf when unreachable (the client's 999 marker). Honors the
    http(s)_proxy env vars via urllib's default opener, so it measures the same
    network path the WSS session uses."""
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
