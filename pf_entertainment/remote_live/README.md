# 远程 Live 部署

本机通过 SSH 上传实时牌桌和资金数据，VPS 提供独立的只读观看页。
VPS 不运行 bot，不持有游戏登录凭证或模型，也不保存历史牌局库。
页面含义与结算展示见 [Web 说明](../README.md)。

## 准备与配置

当前自动部署支持 Ubuntu/Debian，需要可免密登录的 root SSH 账号；VPS 运行服务只依赖 Python 3.10+ 标准库。
本机使用系统 OpenSSH。先确认 `ssh my-vps` 可登录并已确认主机指纹，私钥由 SSH 配置或 ssh-agent 管理。

在项目 `local/secrets/remote_live.json` 中配置，文件权限设为 `600`：

```json
{
  "ssh_host": "my-vps",
  "remote_dir": "/opt/pokerfate-live/current",
  "remote_socket": "/run/pokerfate-live/ingest.sock",
  "interval": 0.7,
  "timeout": 8,
  "public_ip": "你的 VPS IPv4 地址",
  "public_url": "https://你的 VPS IPv4 地址:8443/",
  "tls_mode": "self-signed",
  "web_port": 8443,
  "viewer_user": "viewer",
  "viewer_password": "至少20字符的随机观看口令"
}
```

字段说明：

- `remote_dir`、`remote_socket` 必须是示例里的固定值，`viewer_user` 只能是 `viewer`，`viewer_password` 至少 20 个字符。
- `interval` 是上传间隔（0.25–5 秒），`timeout` 是单次 SSH 读写超时（1–15 秒）。
- 不写 `tls_mode`、`web_port` 时默认是 `letsencrypt` 和 `443`，与示例不同。
- `public_url` 只是给自己记的观看地址，程序不读。
观看账号保护浏览器访问，上传通过 SSH 公钥认证；上传不会提示输入密码，也不会自动接受未知主机指纹。

| HTTPS 模式 | 端口要求 | 浏览器访问 |
|---|---|---|
| `self-signed` | 放行配置的 `web_port`，示例为 8443 | 首次需确认信任自签证书 |
| `letsencrypt` | 放行 HTTP 80 和 HTTPS 443 | 自动签发 IP 证书；80 用于验证，443 用于观看 |

## 部署或更新

在本机项目根目录运行：

```bash
.venv/bin/python -m pf_entertainment.remote_live deploy
```

命令通过 SSH 传输最小服务包，无需 push/pull 仓库。首次部署会安装 nginx，创建 `pf-live` 服务用户，
配置 HTTPS、观看登录和 systemd 开机启动。服务在 `127.0.0.1:9023` 监听，由 nginx 提供公网 HTTPS；
上传使用本地 Unix socket，没有公网 HTTP 写入接口。

部署不会重启本机 bot。健康检查失败会恢复旧代码链接，服务器保留一个旧版本供回退。
配置文件不在默认位置时，`deploy` 和 `publish` 都可使用 `--config <文件路径>`。

自签模式将公钥证书取回 `local/secrets/remote_live_server.crt`，供客户端导入信任，私钥保留在 VPS。
重复部署保留有效证书，剩余不足 30 天时重新生成，届时客户端需要重新信任。
Let's Encrypt 模式安装续期 timer，每天检查两次，续期后重载 nginx。

## 上传数据

### 内置上传

headless 和代理模式都默认在后台读取配置并启动上传，无需修改原启动命令。
配置缺失、格式错误、SSH 认证或远端服务不可用时，控制台及对应入口的运行日志记录具体原因与免密登录提示，
跳过上传，不阻塞游戏启动。启用后断线按 1、2、4、8、16、30 秒间隔恢复，只发送最新状态。

`--no-remote-live` 关闭上传；`--no-web` 只关闭本机 Web。
正常退出时关闭 SSH 子进程。

### 给运行中的 bot 附加上传

bot 已提供本机实时 Web、但没有运行内置上传时，可在另一终端启动：

```bash
.venv/bin/python -m pf_entertainment.remote_live publish \
  --source-url http://127.0.0.1:9022/api/live \
  --owner-pid "$(cat pf_intercept/logs/headless.pid)"
```

该进程读取本机 Web 并上传，bot 无需重启。`--owner-pid` 使上传进程随 bot 退出，也可按 `Ctrl+C` 单独停止。
代理模式下把命令里的 `headless.pid` 换成 `proxy.pid`。
源地址必须为本机回环 HTTP，且 `/api/live` 返回 `available: true`。
同一配置只允许一个上传者，已运行的内置上传会占用同一个锁。
附加上传不会补上旧 bot 尚未采集的字段；修改采集代码后仍需重启 bot。

## 观看登录

打开配置的 `public_url`，使用 `viewer_user` 和 `viewer_password` 登录。
macOS 可在项目目录复制密码到剪贴板：

```bash
.venv/bin/python -c 'import json,sys; sys.stdout.write(json.load(open("local/secrets/remote_live.json"))["viewer_password"])' | pbcopy
```

默认保持登录 90 天；取消勾选时使用最长 12 小时的会话登录。退出登录会撤销当前会话。
沿用原密码重新部署不影响已登录设备，修改密码并重新部署后需重新登录。

## 维护与排错

```bash
ssh my-vps 'systemctl status pokerfate-live --no-pager'
ssh my-vps 'journalctl -u pokerfate-live -n 50 --no-pager'
ssh my-vps 'systemctl restart pokerfate-live'
```

Let's Encrypt 模式还可检查 `pokerfate-live-cert-renew.timer`；自签模式没有续期 timer。
systemd 运行入口是 `python3 -m pf_entertainment.remote_live serve`。

连接超时时分别检查服务监听、VPS 防火墙、服务商入站规则和外网直连结果。
若该 VPS 同时作为代理出口，经代理访问成功不能证明公网入站可达。
登录成功但没有牌桌时，先看本机 `/api/live` 和上传日志，再检查 VPS 服务日志。

## 数据有效期

服务器只保留最新牌桌快照和本轮资金数据。15 秒未收到上传或 SSH 连接结束时清除，
不会补播断线期间的旧动作。过期时间按服务器接收时间计算，正常长考不会触发过期。
已打开的资金页可保留最后收到的数字，但会标明更新时间与中断状态。

“游戏连接中断／重连中”表示 bot 与游戏服务器的连接状态；“直播数据已中断”表示上传链路失效。
本地和 VPS 共用页面组件，但 VPS 不提供本机历史对局列表、日志或活动雷达。
