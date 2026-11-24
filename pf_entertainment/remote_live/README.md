# 独立实时对局 Web

VPS 只部署实时牌桌页面；本机通过 SSH 上传当前快照。没有历史库、游戏登录、模型或 bot 操作接口。
运行服务只依赖 Python 3.10+ 标准库，上传使用系统 OpenSSH。牌桌渲染与本机控制台共用 `static/live-table.js`。

## 本机配置

配置位于项目 `local/secrets/remote_live.json`，已被 `.gitignore` 忽略，权限应为 `600`。路径根据代码位置计算，不依赖启动目录。
SSH 私钥仍由 `~/.ssh/config` / ssh-agent 管理，不复制到仓库或 VPS 部署包。

```json
{
  "ssh_host": "my-vps",
  "remote_dir": "/opt/pokerfate-live/current",
  "remote_socket": "/run/pokerfate-live/ingest.sock",
  "interval": 0.7,
  "timeout": 8,
  "public_ip": "你的 VPS IPv4 地址",
  "public_url": "https://你的 VPS IPv4 地址/",
  "tls_mode": "letsencrypt",
  "web_port": 443,
  "viewer_user": "viewer",
  "viewer_password": "至少20字符的随机观看口令"
}
```

`ssh_host` 是连接配置，不是 SSH 密码。先确保 `ssh my-vps` 可免密登录，并已人工确认过主机指纹。
上传强制 `BatchMode=yes`、只用公钥认证、严格检查已知主机；不会询问密码或自动接受陌生指纹。
观看口令只保护浏览器访问，与上传认证独立；上传始终仅使用 SSH。

## bot 启动行为

原启动命令保持不变，远程直播默认开启。认证验证与上传在后台任务执行，不等待 SSH 再进桌。
配置缺失、JSON 错误、SSH 认证失败、远端未部署等，会在控制台和 `headless.log` 输出具体错误与免密登录提示，然后跳过此功能。
已经启用后出现网络中断，会以 1、2、4、8、16、30 秒间隔恢复上传；只重新发送最新快照。

关闭时在原有启动命令后增加 `--no-remote-live`。
`--no-web` 只关闭本机 Web，不影响远程直播。`--no-remote-live` 只关闭远程直播。
正常退出会结束 SSH 子进程，上传失败不传播到游戏决策链路，也不影响买入次数或资金统计。

## 给已经运行的 bot 接入（无需重启）

```bash
nohup .venv/bin/python -u -m pf_entertainment.remote_live publish \
  --source-url http://127.0.0.1:9022/api/live \
  --owner-pid "$(cat pf_intercept/logs/headless.pid)" \
  >> pf_intercept/logs/remote_live.log 2>&1 &
```

此进程只读本机 Web，原 bot PID 退出后自动结束。下次正常启动 bot 时由内置上传接管。
每份配置都有排他文件锁，同一台机器不会重复上传。临时上传进程和 bot 都遵循此锁。
本机 Web 必须已开启；独立进程只允许回环 HTTP 数据源。

## 从本机部署或更新 VPS

```bash
.venv/bin/python -m pf_entertainment.remote_live deploy
```

该命令读取本机配置，经 SSH 标准输入传输白名单 tar.gz 包，不需要 push/pull 仓库。
只传输 `pf_entertainment/__init__.py`、`remote_live/*.py` 及直播和登录页资源。
当前自动部署面向 Ubuntu/Debian、root SSH 用户，使用固定服务目录；不重启本机 bot。

首次部署自动安装 nginx 和独立 Certbot 环境，创建低权限 `pf-live` 服务用户，签发 IP 地址 HTTPS 证书，配置观看口令与 systemd 开机启动。
公网只有只读 Web；上传 socket 在 `/run/pokerfate-live/ingest.sock`，不提供公网 HTTP 写入接口。
服务监听回环地址 `127.0.0.1:9023`，由 nginx 提供 HTTPS。
部署健康检查失败会恢复旧代码链接；保留当前版本与一个旧版本供回退。

IP 证书采用 Let's Encrypt `shortlived` 配置，证书有效期约 6 天，独立 timer 每天检查两次续期，续期后自动 reload nginx。
依据：[Let's Encrypt / Certbot 的 IP 证书说明](https://letsencrypt.org/2026/03/11/shorter-certs-certbot.html)。
HTTP 80 端口用于 ACME 验证，HTTPS 443 用于观看，两者需要 VPS 网络放行。

### 80/443 被上游限制时

本次 Lisa VPS 实测 80/443 不通，8443 可达，已按用户选择改为：

```json
{"tls_mode": "self-signed", "web_port": 8443, "public_url": "https://192.220.0.55:8443/"}
```

此模式用独立自签证书，浏览器首次访问需要用户确认信任，传输仍经 TLS 加密。
部署命令通过已验证的 SSH 通道取回公钥证书，保存在 `local/secrets/remote_live_server.crt`，不会自动导入系统信任库。
证书/私钥仅在 VPS 的 `/etc/pokerfate-live/tls/`；证书有效期一年，重复部署保留现有证书，剩余不足 30 天时生成新证书（浏览器需要再次确认）。
自签模式不依赖 ACME，不启用 Let's Encrypt 续期 timer。
打开直播地址后用 `viewer` 登录。账号已预填，密码在本机 `local/secrets/remote_live.json` 的 `viewer_password`。macOS 可以在项目目录运行以下命令复制观看密码：

```bash
.venv/bin/python -c 'import json,sys; sys.stdout.write(json.load(open("local/secrets/remote_live.json"))["viewer_password"])' | pbcopy
```

登录页默认勾选「在此设备上保持登录 90 天」。浏览器通过 HTTPS 保存登录 cookie，重新打开原地址即可观看。取消勾选时改用会话 cookie，最长 12 小时。点击「退出登录」会立即撤销本设备当前会话。重新部署沿用原密码时已登录设备继续有效，更换观看密码并重新部署后各设备需要重新登录。

VPS 在 `/etc/pokerfate-live/viewer.json` 保存带盐密码校验值，在 `/var/lib/pokerfate-live-sessions/` 保存会话摘要和有效期。直播进程通过 systemd 的 `StateDirectory` 获得该目录。`/api/live` 支持观看页的登录 cookie，也兼容脚本显式发送的 Basic 认证头。未认证时返回 401。

以下维护命令仍可从本机执行：

```bash
ssh my-vps 'systemctl status pokerfate-live --no-pager'
ssh my-vps 'journalctl -u pokerfate-live -n 50 --no-pager'
ssh my-vps 'systemctl restart pokerfate-live'
ssh my-vps 'systemctl list-timers pokerfate-live-cert-renew.timer --no-pager'
```

独立服务的实际入口：

```bash
python3 -m pf_entertainment.remote_live serve
```

## 数据保留与断线

- 每份上传是完整牌桌快照；不排队补发历史帧，不落盘保存牌局数据。
- VPS 只保留一个快照，15 秒未收到上传就清除。计时基于服务器单调时钟和接收时间，正常长考不会误过期。
- SSH 上传连接正常结束时立即清除该连接的数据；新连接取代旧连接后，旧连接不能覆盖新快照。
- 浏览器也独立计算剩余有效期，VPS 或网络不可用时不会永久显示旧牌桌；请求禁用缓存。
- 页面显示的“游戏连接中断/重连中”与“直播数据已中断”分别表示游戏连接状态和上传链路状态。
- 这是实时快照展示，不保证展示每个快速连续动作的动画；最新快照附带现有 observer 的短行动列表。

## 结算亮牌与最佳五张

本机控制台和 VPS 共用结算展示：收到结算后先展示所有公开亮牌玩家的底牌 2.5 秒，再展示赢家和自己的最佳五张及中文牌型。组成牌型的底牌用金色标出；平分底池或多个边池赢家分别列出。

结算保留到下一次结算，新一手的牌桌正常更新。每份结算带独立手号和本手公共牌，避免与新一手混淆。即使自己提前弃牌，也按这手最终实际发出的公共牌计算组合；未发到翻牌时提示不足五张，不补造公共牌。对手未公开或只公开一张底牌时，不推测其完整底牌或五张组合；若服务器提供牌型，则仅展示该牌型。

这些字段由 bot 的牌桌 observer 处理公开亮牌消息并计算，VPS 只负责显示。更新页面后需在下一次 bot 启动时加载新版 observer；给旧 bot 加上传进程不会自动补上旧进程尚未采集的亮牌数据。直播快照过期时，结算也一起清除。
