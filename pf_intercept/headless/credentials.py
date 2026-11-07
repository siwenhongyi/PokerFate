"""Account credentials for the headless client.

Stored in ``data/headless_account.json`` (the whole ``data/`` dir is
git-ignored).  Two login types are supported, matching LOGIN_TYPE in
EnumConfig.lua:

    {"type": "email", "email": "...", "password": "..."}
    {"type": "guest", "device_id": "..."}

Optional keys (defaults shown):

    "device_id": "<random uuid, persisted on first run>"
    "os":        "android"
    "lang":      "en"
    "chnl":      <config.GAMEDATA_CHNL>

Values are never logged.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from pathlib import Path

from pf_intercept import config

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ACCOUNT_FILE = _PROJECT_ROOT / "data" / "headless_account.json"

LOGIN_TYPE_GUEST = 1
LOGIN_TYPE_EMAIL = 2


@dataclass(frozen=True)
class Account:
    login_type: int
    token: str          # email for EMAIL login, device id for GUEST login
    secret: str         # password for EMAIL login; derived for GUEST login
    device_id: str
    os: str = "android"
    lang: str = "en"
    chnl: int = int(config.GAMEDATA_CHNL)

    def redacted(self) -> str:
        kind = "email" if self.login_type == LOGIN_TYPE_EMAIL else "guest"
        return f"{kind} token={self.token[:3]}… device={self.device_id[:8]}… chnl={self.chnl}"


class AccountError(ValueError):
    pass


def load_account(path: Path | str = DEFAULT_ACCOUNT_FILE) -> Account:
    path = Path(path)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise AccountError(
            f"账号文件不存在: {path}\n"
            '请创建，内容例如 {"type": "email", "email": "you@x.com", "password": "..."}'
        ) from None
    except json.JSONDecodeError as exc:
        raise AccountError(f"账号文件不是合法 JSON: {path} ({exc})") from None
    if not isinstance(raw, dict):
        raise AccountError(f"账号文件应为 JSON 对象: {path}")

    kind = str(raw.get("type") or "").strip().lower()
    device_id = str(raw.get("device_id") or "").strip()
    if not device_id:
        # Mirror SdkHelper:getDeviceID(): generate once, then persist so the
        # server sees a stable "imei" across runs.
        device_id = uuid.uuid4().hex
        raw["device_id"] = device_id
        path.write_text(json.dumps(raw, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    common = dict(
        device_id=device_id,
        os=str(raw.get("os") or "android"),
        lang=str(raw.get("lang") or "en"),
        chnl=int(raw.get("chnl") or config.GAMEDATA_CHNL),
    )
    if kind == "email":
        email = str(raw.get("email") or "").strip()
        password = str(raw.get("password") or "")
        if not email or not password:
            raise AccountError("email 登录需要 email 和 password 两个字段")
        return Account(LOGIN_TYPE_EMAIL, email, password, **common)
    if kind == "guest":
        return Account(LOGIN_TYPE_GUEST, device_id, "", **common)
    raise AccountError(f'type 必须是 "email" 或 "guest"，当前: {kind!r}')
