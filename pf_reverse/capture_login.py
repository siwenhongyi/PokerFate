"""mitmproxy addon: capture the game login and auto-refresh headless creds.

On every /login round-trip it:
  1. saves the raw request/response to local/secrets/login_capture/ (git-ignored), and
  2. on a SUCCESS (code 0/-6, with uid/rdkey/server), writes the harvested
     session straight into local/secrets/headless_session.json — the file the headless
     client reads — so there is no manual "copy the credentials over" step.

So the whole flow becomes: phone opens the game (logs in through this proxy) →
headless_session.json refreshes itself; the Mac bot just reads it on start.

The capture holds the account password and session token in clear text; keep it
local.

Usage: don't invoke mitmdump directly — run
    python -m pf_intercept.headless.harvest_session
which starts mitmdump with this addon, prints the phone-side setup steps, and
exits once a fresh session has been captured.

Do NOT filter by hostname (e.g. "only intercept hosts containing poker-fate"):
the real client's candidate login addresses (see Constants.lua G_HTTP_URL /
_2 / _3 / _4 in pf_reverse/output/lua/src/app/Constants.lua) include bare IPs
with no hostname at all, so a host allow-list can silently miss the real
traffic. --ignore-hosts should instead exclude known-irrelevant hosts and
intercept everything else — see pf_intercept.config.MITM_IGNORE_HOSTS, the
value harvest_session.py actually passes to mitmdump.
"""

from __future__ import annotations

import base64
import json
import os
import time
from pathlib import Path

from mitmproxy import http

_REPO_ROOT = Path(__file__).parent.parent
_OUT_DIR = _REPO_ROOT / "local" / "secrets" / "login_capture"
_SESSION_FILE = _REPO_ROOT / "local" / "secrets" / "headless_session.json"
_PATHS = ("/login", "/player/valid", "/captcha")
_OK_CODES = {0, -6}  # LoginModel treats -6 (risk warning) as success too.


def _json_or_text(raw: bytes | None):
    if not raw:
        return None
    try:
        return json.loads(raw)
    except Exception:
        return raw.decode("utf-8", "replace")[:4000]


def _jwt_exp(token: str) -> int | None:
    try:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        return json.loads(base64.urlsafe_b64decode(payload)).get("exp")
    except Exception:
        return None


def _write_session(request: dict, response: dict, version: str) -> str | None:
    """Write local/secrets/headless_session.json from a successful /login; returns path or None."""
    if not isinstance(response, dict) or int(response.get("code", 0) or 0) not in _OK_CODES:
        return None
    uid = response.get("uid")
    rdkey = response.get("rdkey")
    servers = (response.get("server") or {}).get("server") or []
    if uid is None or not rdkey or not servers:
        return None
    req = request if isinstance(request, dict) else {}
    auth = response.get("authorization", "")
    session = {
        "captured_at": time.time(),
        "captured_at_str": time.strftime("%Y-%m-%d %H:%M:%S"),
        "uid": int(uid),
        "rdkey": str(rdkey),
        "authorization": str(auth),
        "authorization_exp": _jwt_exp(str(auth)),
        "chnl": req.get("chnl"),
        "imei": req.get("imei"),
        "version": version,
        "servers": servers,
        "login_ip": response.get("login_ip", ""),
        "login_region": response.get("login_region", ""),
    }
    _SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = _SESSION_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(session, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, _SESSION_FILE)  # atomic: bot never reads a half-written file
    return str(_SESSION_FILE)


class CaptureLogin:
    def response(self, flow: http.HTTPFlow) -> None:
        path = flow.request.path.split("?", 1)[0]
        if not path.endswith(_PATHS):
            return
        _OUT_DIR.mkdir(parents=True, exist_ok=True)
        name = path.strip("/").replace("/", "_") or "root"
        request = _json_or_text(flow.request.content)
        response = _json_or_text(flow.response.content) if flow.response else None
        out = _OUT_DIR / f"{int(time.time())}_{name}.json"
        out.write_text(json.dumps({
            "ts": time.time(),
            "url": flow.request.pretty_url,
            "status": flow.response.status_code if flow.response else None,
            "request_headers": dict(flow.request.headers),
            "request": request,
            "response_headers": dict(flow.response.headers) if flow.response else {},
            "response": response,
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[capture_login] {flow.request.method} {path} -> {out}")

        if path.endswith("/login"):
            try:
                version = flow.request.headers.get("Version", "")
                saved = _write_session(request, response, version)
                if saved:
                    uid = (response or {}).get("uid")
                    print(f"[capture_login] ✅ 已自动更新凭证 uid={uid} -> {saved}")
                else:
                    code = (response or {}).get("code") if isinstance(response, dict) else "?"
                    print(f"[capture_login] 登录非成功(code={code})，未更新凭证")
            except Exception as exc:
                print(f"[capture_login] 写入 headless_session.json 失败: {exc}")


addons = [CaptureLogin()]
