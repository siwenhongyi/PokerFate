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
  "public_url": "https://你的 VPS IPv4 地址:8443/",
  "tls_mode": "self-signed",
  "web_port": 8443,
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

首次部署自动安装 nginx，创建低权限 `pf-live` 服务用户，按 `tls_mode` 配置 HTTPS 证书、观看口令与 systemd 开机启动。选择 `letsencrypt` 时另行安装独立 Certbot 环境并签发 IP 地址证书；选择 `self-signed` 时使用自签证书。
公网只有只读 Web；上传 socket 在 `/run/pokerfate-live/ingest.sock`，不提供公网 HTTP 写入接口。
服务监听回环地址 `127.0.0.1:9023`，由 nginx 提供 HTTPS。
部署健康检查失败会恢复旧代码链接；保留当前版本与一个旧版本供回退。

选择 `tls_mode: "letsencrypt"` 时，IP 证书采用 Let's Encrypt `shortlived` 配置，证书有效期约 6 天，独立 timer 每天检查两次续期，续期后自动 reload nginx。
依据：[Let's Encrypt / Certbot 的 IP 证书说明](https://letsencrypt.org/2026/03/11/shorter-certs-certbot.html)。
HTTP 80 端口用于 ACME 验证，HTTPS 443 用于观看，两者需要 VPS 网络放行。

### 当前线上部署：8443 + 自签 HTTPS

当前 Lisa VPS 观看地址为 **https://192.220.0.55:8443/**。2026-11-23 恢复 8443 后，已绕过本机 Clash TUN，绑定 Wi-Fi 网卡直接验证登录、页面和实时数据接口。本机配置为：

```json
{"tls_mode": "self-signed", "web_port": 8443, "public_url": "https://192.220.0.55:8443/"}
```

同日曾尝试迁到 443，但手机直连超时，因此已恢复 8443 作为正式入口，并保留 443 监听供排查。**经代理访问 443 成功不能证明公网直连已放通**：本机启用了 Clash TUN，代理节点就是这台 VPS；经代理访问可获得 HTTPS 200，但绑定 Wi-Fi 网卡绕过本机 TUN 后，80/443 连接超时，同路径 SSH 57129 和 HTTPS 8443 正常。VPS 抓包显示代理访问 443 走本机回环接口，测试期间未收到对应直连 80/443 的握手包。

排查端口时必须区分代理和直连路径，同时检查 nginx 监听、服务器收到的握手包和完整 HTTPS 响应。同一台 VPS 作为代理出口时，“本机能打开”不能证明公网入站已放通；仅设置 `NO_PROXY` 也不会绕过系统 TUN 路由。

本次恢复沿用原证书、观看密码和登录会话，只热更新 nginx；本机 bot 的 SSH 上传不依赖 Web 端口，无需重启 bot。今后执行上面的 `deploy` 命令会读取本机配置并部署到 8443；当前额外的 443 诊断监听不会由常规部署保留。在独立直连路径验证通过前，不再关闭 8443 或将主入口切到 443。

#### 安全组验证（2026-11-23）

排查期间曾将 Lisa 控制台的 `pokerfate-live` 安全组（ID `23810`）应用到实例 `C20261102163560`；刷新页面后显示“已关联”、关联实例数 `1`。入方向同时保留 HTTPS 443 预设规则和显式 TCP 443 规则，授权地址均为 `0.0.0.0/0`。为保留现有服务，另补齐 TCP `8443 / 57129 / 64814 / 2086 / 46059 / 61672` 和 UDP `31569 / 52471 / 44626`。

用户随后要求撤销本次安全组变更。控制台对已关联组仅提供“查看”和“新增策略”，没有解绑或删除入口，因此通过客服工单请求恢复排查前未关联任何安全组的状态。**客服处理后已刷新控制台确认：安全组列表显示“暂无任何规则”，本次测试组已不再显示。**

2026-11-23 已成功提交 Lisa 客服工单 **#851243**，标题为“192.220.0.55：请求恢复安全组原状，并排查放行公网 TCP 443”。工单包含解除并删除测试安全组的请求、443 直连超时的对照测试和抓包证据，以及保持现有 8443、SSH 和其他服务正常运行的要求。可登录控制台的[我的工单](https://lisahost.com/supporttickets.php)查看处理进度。客服在工单显示时间 2026-11-23 23:06 回复已解除安全组、全部端口开放；该回复注明由 AI 客服自动生成。**安全组移除已验证，但客服回复后的直连复测仍未确认 443 放通。**

客服回复后，于 2026-11-23 15:44–15:46 UTC 绕过本机 Clash、绑定物理 Wi-Fi 网卡再次测试：

| 路径 | 结果 |
| --- | --- |
| 绕过本机 Clash，直连 HTTPS 8443 | 登录、页面和数据接口正常 |
| 同路径直连 SSH 57129 | 正常返回 SSH 握手 |
| 同路径直连 HTTPS 443 | 两轮 TCP 连接分别等待 8 秒、10 秒后超时 |
| 同路径直连 HTTP 80 | TCP 连接等待 8 秒后超时 |
| 经本机 Clash 代理访问 HTTPS 443（前次排查） | HTTP 200，但 VPS 抓包显示连接走本机回环接口 |

VPS 的 nginx 仍监听 `0.0.0.0:443` 和 `0.0.0.0:8443`，nginx 与直播服务均为 active，系统 INPUT 策略为 ACCEPT、无附加规则。安全组移除后的同步抓包仍能看到公网网卡 `ens17` 收到测试来源 `47.237.8.3` 到 8443、57129 的 SYN 并返回 SYN-ACK，但未收到对应直连 443 的 SYN。因此，安全组移除后本机直连 443 的问题仍然存在；还需要服务商从独立外部网络复测，并核查宿主机及上游端口限制，也不能排除访问网络路径上的拦截。现有证据不足以断言所有公网来源都无法访问 443。正式入口继续保留 8443。

2026-11-23 17:12–17:14 UTC 进一步完成独立外网对照：

| Check-Host 探测 | 连接成功 | 连接超时 | 探测节点离线 |
| --- | --- | --- | --- |
| [TCP 443 报告](https://check-host.net/check-report/5a1f4e3fkc82) | 0 | 58 | 2 |
| [TCP 8443 报告](https://check-host.net/check-report/5a1f510ckd5a) | 58 | 1 | 1 |

美国洛杉矶、纽约、达拉斯、东京、香港、新加坡、巴黎等节点均为 443 超时、8443 成功；洛杉矶节点连接 8443 仅约 2 毫秒。VPS 内部通过 `127.0.0.1:443` 和 `:8443` 访问 `/login`、按服务器 IP 校验证书，均返回 HTTPS 200。再次检查 nginx 配置、IPv4/IPv6 防火墙和同步抓包，结果与前次一致。这些证据指向 VPS 客户系统之外的网络过滤，排除了仅由本机 Clash 或单条访问线路造成的解释；具体拦截层仍需服务商核实。

已于北京时间 2026-11-24 01:14 在原工单 **#851243** 追加上述报告和证据，并确认回复已显示在工单中。要求转人工技术人员，检查宿主机/虚拟交换机 ACL、底层安全组残留及机房上游端口策略，提供外部实测结果；同时要求保留 8443、SSH 和其他现有服务，不重装或重启实例。443 尚未恢复，主入口继续使用 8443。

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
