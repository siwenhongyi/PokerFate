"""Remote Ubuntu/Debian provisioner. Called by deploy over SSH, JSON on stdin."""
from __future__ import annotations

import ipaddress
import json
import os
import pwd
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import ProxyHandler, build_opener

from .viewer_auth import CREDENTIALS, credentials_for

BASE = Path("/opt/pokerfate-live")


def run(*args, **kwargs):
    subprocess.run(args, check=True, **kwargs)


def write(path, text, mode=0o644, gid=None):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, delete=False) as tmp:
        try:
            tmp.write(text)
            tmp.flush()
            if gid is not None:
                os.fchown(tmp.fileno(), 0, gid)
            os.fchmod(tmp.fileno(), mode)
            os.replace(tmp.name, path)
        finally:
            Path(tmp.name).unlink(missing_ok=True)


def nginx_config(ip: str, *, tls: bool, port: int = 443, mode: str = "letsencrypt"):
    suffix = "" if port == 443 else f":{port}"
    text = "# Managed by pf_entertainment.remote_live.deploy\n"
    if mode == "letsencrypt":
        text += f"""
server {{
    listen 80;
    server_name {ip};
    location /.well-known/acme-challenge/ {{ root /var/lib/pokerfate-live/acme; }}
    location / {{ return 301 https://{ip}{suffix}$request_uri; }}
}}
"""
    if tls:
        cert = ("/etc/pokerfate-live/tls/cert.pem" if mode == "self-signed"
                else "/etc/letsencrypt/live/pokerfate-live/fullchain.pem")
        key = ("/etc/pokerfate-live/tls/key.pem" if mode == "self-signed"
               else "/etc/letsencrypt/live/pokerfate-live/privkey.pem")
        text += f"""map $http_authorization $pf_viewer_basic_ip {{ "" ""; default $binary_remote_addr; }}
limit_req_zone $pf_viewer_basic_ip zone=pf_viewer_api:1m rate=2r/s;
limit_req_zone $binary_remote_addr zone=pf_viewer_login:1m rate=10r/m;
server {{
    listen {port} ssl;
    server_name {ip};
    ssl_certificate {cert};
    ssl_certificate_key {key};
    ssl_protocols TLSv1.2 TLSv1.3;
    server_tokens off;
    access_log off;
    client_max_body_size 4k;
    proxy_set_header Host $http_host;
    proxy_set_header Authorization "";
    proxy_connect_timeout 2s;
    proxy_read_timeout 5s;
    proxy_buffering off;
    location = /healthz {{ return 404; }}
    location = /api/live {{
        limit_except GET {{ deny all; }}
        limit_req zone=pf_viewer_api burst=5 nodelay;
        limit_req_status 429;
        proxy_set_header Host $http_host;
        proxy_set_header Authorization $http_authorization;
        proxy_pass http://127.0.0.1:9023;
    }}
    location = /login {{
        limit_except GET POST {{ deny all; }}
        limit_req zone=pf_viewer_login burst=10 nodelay;
        limit_req_status 429;
        proxy_pass http://127.0.0.1:9023;
    }}
    location = /logout {{
        limit_except POST {{ deny all; }}
        proxy_pass http://127.0.0.1:9023;
    }}
    location / {{
        limit_except GET {{ deny all; }}
        proxy_pass http://127.0.0.1:9023;
    }}
}}
"""
    return text


def install(data):
    if os.geteuid() != 0:
        raise RuntimeError("自动部署需要 SSH 用户具备 root 权限")
    ip = str(ipaddress.IPv4Address(data["public_ip"]))
    mode, port = data.get("tls_mode", "letsencrypt"), data.get("web_port", 443)
    if mode not in ("letsencrypt", "self-signed") or type(port) is not int or not 1 <= port <= 65535 or port in (22, 80, 9023, 57129):
        raise ValueError("invalid tls_mode / web_port")
    release = Path(data["release"])
    if release.parent != BASE / "releases" or not release.is_dir():
        raise ValueError("invalid release directory")
    env = {**os.environ, "DEBIAN_FRONTEND": "noninteractive", "NEEDRESTART_MODE": "l"}
    if not shutil.which("nginx") or not Path("/usr/share/python-wheels").exists():
        run("apt-get", "update", "-qq", env=env)
        run("apt-get", "install", "-y", "--no-install-recommends", "nginx", "python3-venv", env=env)
    try:
        pwd.getpwnam("pf-live")
    except KeyError:
        run("useradd", "--system", "--home-dir", "/var/lib/pokerfate-live", "--shell", "/usr/sbin/nologin", "pf-live")
    certbot = BASE / "certbot" / "bin" / "certbot"
    if mode == "letsencrypt" and not certbot.exists():
        run("python3", "-m", "venv", str(BASE / "certbot"))
        run(str(BASE / "certbot" / "bin" / "pip"), "install", "--disable-pip-version-check", "certbot>=5.4,<6")

    # Password travels only in SSH stdin, never argv/process listings or git.
    password = data["viewer_password"]
    if data["viewer_user"] != "viewer" or len(password) < 20 or "\n" in password:
        raise ValueError("invalid viewer credentials")
    write(CREDENTIALS, json.dumps(credentials_for(password, CREDENTIALS)), mode=0o640,
          gid=pwd.getpwnam("pf-live").pw_gid)
    Path("/var/lib/pokerfate-live/acme").mkdir(parents=True, exist_ok=True)

    current = BASE / "current"
    previous = current.resolve() if current.exists() else None
    link = BASE / "current.new"
    link.unlink(missing_ok=True)
    link.symlink_to(release)
    os.replace(link, current)
    write("/etc/systemd/system/pokerfate-live.service", """[Unit]
Description=PokerFate read-only live viewer
After=network.target
[Service]
Type=simple
User=pf-live
Group=pf-live
WorkingDirectory=/opt/pokerfate-live/current
ExecStart=/usr/bin/python3 -B -m pf_entertainment.remote_live serve
RuntimeDirectory=pokerfate-live
RuntimeDirectoryMode=0700
StateDirectory=pokerfate-live-sessions
StateDirectoryMode=0700
UMask=0077
Restart=on-failure
RestartSec=2
TimeoutStopSec=5
NoNewPrivileges=true
PrivateTmp=true
ProtectHome=true
ProtectSystem=strict
RestrictAddressFamilies=AF_UNIX AF_INET AF_INET6
[Install]
WantedBy=multi-user.target
""")
    run("systemctl", "daemon-reload")
    try:
        run("systemctl", "enable", "pokerfate-live.service")
        run("systemctl", "restart", "pokerfate-live.service")
        import time
        opener = build_opener(ProxyHandler({}))
        for attempt in range(20):
            try:
                with opener.open("http://127.0.0.1:9023/healthz", timeout=1) as response:
                    if json.load(response).get("ok"):
                        break
            except OSError:
                if attempt == 19:
                    raise
                time.sleep(0.25)
        # Check the actual access boundary before replacing the old nginx gate.
        for api in ("/api/live", "/api/money"):
            try:
                with opener.open("http://127.0.0.1:9023" + api, timeout=2):
                    raise RuntimeError("viewer API accepted an anonymous request")
            except HTTPError as exc:
                if exc.code != 401:
                    raise
    except Exception:
        if previous:
            link.symlink_to(previous)
            os.replace(link, current)
            run("systemctl", "restart", "pokerfate-live.service")
        raise

    nginx = "/etc/nginx/conf.d/pokerfate-live.conf"
    if mode == "self-signed":
        tls_dir = Path("/etc/pokerfate-live/tls")
        tls_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        cert, key = tls_dir / "cert.pem", tls_dir / "key.pem"
        reusable = cert.exists() and key.exists()
        for options in (("-checkend", "2592000"), ("-checkip", ip)):
            if reusable:
                reusable = subprocess.run(["openssl", "x509", "-noout", "-in", str(cert), *options],
                                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0
        if not reusable:
            run("openssl", "req", "-x509", "-newkey", "rsa:3072", "-nodes", "-days", "365",
                "-keyout", str(key), "-out", str(cert), "-subj", f"/CN={ip}",
                "-addext", f"subjectAltName=IP:{ip}", stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            key.chmod(0o600)
        write(nginx, nginx_config(ip, tls=True, port=port, mode=mode))
        run("nginx", "-t")
        run("systemctl", "enable", "--now", "nginx")
        run("systemctl", "reload", "nginx")
        timer = Path("/etc/systemd/system/pokerfate-live-cert-renew.timer")
        if timer.exists():
            run("systemctl", "disable", "--now", timer.name)
        _finish(release, previous, ip, port)
        print("使用自签 HTTPS，浏览器首次需确认信任；证书临近到期时再次 deploy 会更新。", flush=True)
        return
    cert_exists = Path("/etc/letsencrypt/live/pokerfate-live/fullchain.pem").exists()
    write(nginx, nginx_config(ip, tls=cert_exists, port=port))
    run("nginx", "-t")
    run("systemctl", "enable", "--now", "nginx")
    run("systemctl", "reload", "nginx")
    run(str(certbot), "certonly", "--non-interactive", "--agree-tos", "--register-unsafely-without-email",
        "--preferred-profile", "shortlived", "--webroot", "--webroot-path", "/var/lib/pokerfate-live/acme",
        "--ip-address", ip, "--cert-name", "pokerfate-live", "--keep-until-expiring",
        "--deploy-hook", "systemctl reload nginx")
    write(nginx, nginx_config(ip, tls=True, port=port))
    run("nginx", "-t")
    run("systemctl", "reload", "nginx")
    write("/etc/systemd/system/pokerfate-live-cert-renew.service", """[Unit]
Description=Renew PokerFate live IP HTTPS certificate
[Service]
Type=oneshot
ExecStart=/opt/pokerfate-live/certbot/bin/certbot renew --quiet --cert-name pokerfate-live
""")
    write("/etc/systemd/system/pokerfate-live-cert-renew.timer", """[Unit]
Description=Check PokerFate live IP certificate twice daily
[Timer]
OnCalendar=*-*-* 00,12:00:00
RandomizedDelaySec=900
Persistent=true
[Install]
WantedBy=timers.target
""")
    run("systemctl", "daemon-reload")
    run("systemctl", "enable", "--now", "pokerfate-live-cert-renew.timer")
    _finish(release, previous, ip, port)


def _finish(release, previous, ip, port):
    # Keep the active release and one rollback; no models, sessions or histories.
    for old in (BASE / "releases").iterdir():
        if old.is_dir() and old not in (release, previous):
            shutil.rmtree(old)
    suffix = "" if port == 443 else f":{port}"
    print(f"部署成功：https://{ip}{suffix}/（账号 viewer；口令在本机 local/secrets/remote_live.json）", flush=True)


if __name__ == "__main__":
    try:
        install(json.load(sys.stdin))
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        print(f"部署未完成：{type(exc).__name__}: {exc}", file=sys.stderr)
        raise SystemExit(1)
