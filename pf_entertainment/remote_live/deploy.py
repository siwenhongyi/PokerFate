"""Upload a small allowlisted tarball through SSH; no git or game assets on VPS."""
from __future__ import annotations

import io
import ipaddress
import json
import shlex
import subprocess
import tarfile
import time
import uuid
from pathlib import Path

from .config import ROOT, PublishConfig, ssh_args


def bundle() -> bytes:
    paths = [ROOT / "pf_entertainment" / "__init__.py"]
    paths += sorted((ROOT / "pf_entertainment" / "remote_live").glob("*.py"))
    paths += [ROOT / "pf_entertainment" / "static" / name for name in
              ("live.html", "live-login.html", "live-table.js", "live-money.js", "live-views.js",
               "live-remote.js", "styles.css")]
    result = io.BytesIO()
    with tarfile.open(fileobj=result, mode="w:gz") as archive:
        for path in paths:
            archive.add(path, arcname=str(path.relative_to(ROOT)), recursive=False)
    return result.getvalue()


def deploy(config_path: Path):
    cfg = PublishConfig.load(config_path)
    data = json.loads(config_path.read_text())
    ipaddress.ip_address(data["public_ip"])
    if cfg.remote_dir != "/opt/pokerfate-live/current" or cfg.remote_socket != "/run/pokerfate-live/ingest.sock":
        raise ValueError("自动部署使用 /opt/pokerfate-live/current 与 /run/pokerfate-live/ingest.sock")
    if data.get("viewer_user") != "viewer" or not isinstance(data.get("viewer_password"), str) or len(data["viewer_password"]) < 20:
        raise ValueError("需要 viewer_user=viewer 与至少 20 字符的 viewer_password")
    release = f"/opt/pokerfate-live/releases/{time.strftime('%Y%m%d-%H%M%S', time.gmtime())}-{uuid.uuid4().hex[:8]}"
    archive = bundle()
    subprocess.run([*ssh_args(cfg.ssh_host), f"mkdir -p {shlex.quote(release)} && tar -xzf - -C {shlex.quote(release)}"],
                   input=archive, check=True, timeout=60)
    print(f"已通过 SSH 上传 {len(archive):,} 字节部署包；安装/更新服务…", flush=True)
    install = f"cd {shlex.quote(release)} && python3 -B -m pf_entertainment.remote_live.install"
    payload = {key: data[key] for key in ("public_ip", "viewer_user", "viewer_password")}
    payload["tls_mode"] = data.get("tls_mode", "letsencrypt")
    payload["web_port"] = data.get("web_port", 443)
    payload["release"] = release
    subprocess.run([*ssh_args(cfg.ssh_host), install], input=json.dumps(payload).encode(), check=True, timeout=900)
    if payload["tls_mode"] == "self-signed":
        cert = subprocess.check_output([*ssh_args(cfg.ssh_host), "cat /etc/pokerfate-live/tls/cert.pem"], timeout=20)
        config_path.with_name("remote_live_server.crt").write_bytes(cert)
        print("已通过 SSH 保存服务器公钥证书到 local/secrets/remote_live_server.crt（未导入系统信任库）")


if __name__ == "__main__":
    from .config import DEFAULT_CONFIG
    deploy(DEFAULT_CONFIG)
