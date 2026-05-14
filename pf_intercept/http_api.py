"""Shared signed HTTP helper for PokerFate game REST APIs."""

from __future__ import annotations

import hashlib
import json
import logging
import random
import ssl
import string
import time
import urllib.request
from pathlib import Path
from typing import Optional

import certifi

from pf_intercept import config

log = logging.getLogger("pf_http")

GAME_HTTP_SSL_CTX = ssl.create_default_context(cafile=certifi.where())
_SALT = "Z3r0w0nd3rd3!3z4jz89z9DLbg&8Gjt("
_TOKEN_FILE = Path(__file__).resolve().parent.parent / "data" / "auth_token.txt"
_UNITY_USER_AGENT = "UnityPlayer/2022.3.62f3 (UnityWebRequest/1.0, libcurl/8.10.1-DEV)"


def sign_request(rand: str, ts: str) -> str:
    raw = f"random={rand}&ts={ts}&salt={_SALT}"
    return hashlib.md5(raw.encode()).hexdigest()


def load_auth_token() -> Optional[str]:
    try:
        token = _TOKEN_FILE.read_text(encoding="utf-8").strip()
        return token or None
    except (OSError, UnicodeError) as exc:
        log.warning(
            "[http] failed to read token file %s (%s: %s)",
            _TOKEN_FILE,
            type(exc).__name__,
            exc,
        )
        return None
    except Exception:
        log.exception("[http] unexpected error reading token file %s", _TOKEN_FILE)
        return None


def add_signed_args(payload: Optional[dict], *, chnl: Optional[int] = None) -> dict:
    out = dict(payload or {})
    rand = "".join(random.choices(string.ascii_letters + string.digits, k=6))
    ts = str(out.get("ts") or int(time.time()))
    out["random"] = rand
    out["ts"] = ts
    out["sign"] = sign_request(rand, ts)
    out.setdefault("chnl", int(chnl if chnl is not None else config.GAMEDATA_CHNL))
    return out


def signed_post_json(
    path: str,
    payload: Optional[dict] = None,
    *,
    host: Optional[str] = None,
    chnl: Optional[int] = None,
    token: Optional[str] = None,
    timeout: float = 8.0,
    auth_required: bool = True,
    extra_headers: Optional[dict[str, str]] = None,
) -> Optional[dict]:
    """POST JSON with the same salt/sign/header pattern as the Unity client."""
    auth = token if token is not None else load_auth_token()
    if auth_required and not auth:
        log.warning("[http] skip POST %s: auth_token.txt missing", path)
        return None

    if path.startswith("http://") or path.startswith("https://"):
        url = path
    else:
        base_host = host or config.GAMEDATA_HTTP_HOST
        normalized = path if path.startswith("/") else "/" + path
        url = f"https://{base_host}{normalized}"

    body = json.dumps(
        add_signed_args(payload, chnl=chnl),
        ensure_ascii=False,
    ).encode("utf-8")
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", "application/json; charset=utf-8")
    req.add_header("Version", str(getattr(config, "GAME_HTTP_VERSION", "1.5.1")))
    req.add_header("User-Agent", _UNITY_USER_AGENT)
    req.add_header("Accept", "*/*")
    req.add_header("X-Unity-Version", "2022.3.62f3")
    if auth:
        req.add_header("Authorization", auth)
    for key, value in (extra_headers or {}).items():
        req.add_header(key, value)

    log.debug("[http] POST %s", url)
    try:
        with urllib.request.urlopen(
            req,
            timeout=timeout,
            context=GAME_HTTP_SSL_CTX,
        ) as resp:
            raw = resp.read()
    except Exception as exc:
        log.warning("[http] POST failed %s (%s: %s)", url, type(exc).__name__, exc)
        return None

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        log.warning("[http] bad JSON from %s raw=%r", url, raw[:300])
        return None
