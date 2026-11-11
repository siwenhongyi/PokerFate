from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = ROOT / "data" / "remote_live.json"
SSH_HINT = "请提前配置 SSH 免密登录，并手动确认主机指纹（例如 ssh my-vps）；本次跳过远程直播，不影响 bot。"


@dataclass(frozen=True)
class PublishConfig:
    ssh_host: str
    remote_dir: str = "/opt/pokerfate-live/current"
    remote_socket: str = "/run/pokerfate-live/ingest.sock"
    interval: float = 0.7
    timeout: float = 8.0

    @classmethod
    def load(cls, path: Path) -> "PublishConfig":
        data = json.loads(path.read_text(encoding="utf-8"))
        result = cls(**{key: data[key] for key in cls.__dataclass_fields__ if key in data})
        if not isinstance(result.ssh_host, str) or not re.fullmatch(r"[a-zA-Z0-9_][a-zA-Z0-9_.@-]*", result.ssh_host):
            raise ValueError("ssh_host 必须是 SSH 配置别名或 user@host")
        for field in (result.remote_dir, result.remote_socket):
            if not isinstance(field, str) or not field.startswith("/") or "\n" in field or "\x00" in field:
                raise ValueError("remote_dir / remote_socket 必须是绝对路径")
        if (type(result.interval) not in (int, float) or type(result.timeout) not in (int, float)
                or not 0.25 <= result.interval <= 5 or not 1 <= result.timeout <= 15):
            raise ValueError("interval 应在 0.25–5 秒，timeout 应在 1–15 秒")
        return result


def ssh_args(host: str) -> list[str]:
    return ["ssh", "-T", "-o", "BatchMode=yes", "-o", "PasswordAuthentication=no",
            "-o", "KbdInteractiveAuthentication=no", "-o", "PreferredAuthentications=publickey",
            "-o", "StrictHostKeyChecking=yes", "-o", "ConnectTimeout=5",
            "-o", "ConnectionAttempts=1", "-o", "ServerAliveInterval=5",
            "-o", "ServerAliveCountMax=2", "-o", "ClearAllForwardings=yes",
            "-o", "ControlPath=none", "-o", "LogLevel=ERROR", host]
