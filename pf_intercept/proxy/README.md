# 代理模式

代理模式下，游戏客户端照常登录和显示，代理站在客户端和服务器之间，解码双方的消息。
bot 用和 headless 相同的会话逻辑决策、选桌和执行大厅自动化，并把自己的请求注入同一条连接。
安装和公共参数见[项目首页](../../README.md)，牌桌规则见[对手信息与牌桌管理](../bot/README.md)。

## 工作方式

`pf_intercept.launcher` 一条命令启动三样东西：

| 组件 | 默认端口 | 作用 |
|---|---|---|
| mitmweb | `8080` | HTTP 代理。记录登录凭证，再把登录返回的服务器列表改成证书覆盖的游戏域名 |
| 伪 DNS | `53` | 把游戏域名解析到本机，其他域名照常转发 |
| proxy | `9012`、`443`、`80` | 游戏 WSS 的 MITM，另两个端口原样透传；同时提供本机 Web（`9022`） |

mitmweb 加载两个插件：先是 [capture_login.py](../../pf_reverse/capture_login.py)，
它把登录结果写进 `local/secrets/headless_session.json`；然后是 [force_domain.py](../../pf_reverse/force_domain.py)，
它去掉服务器列表里的 IP 直连地址。登录不经过 mitmweb 时，客户端可能直连服务器 IP，绕开代理。

客户端进入比赛房（SNG / MTT）后由玩家自己打，bot 不决策也不记录。好友房不自动锁仓、补码或选桌。

## 准备

### 证书

```bash
.venv/bin/python -m pf_intercept.gen_cert
```

生成的证书在 `pf_intercept/certs/`。客户端设备要信任两张根证书：

- `pf_intercept/certs/ca.crt`：游戏 WSS 连接用，装成受信任的根 CA。
- mitmproxy 根证书：HTTP 登录用。启动 launcher 后，在设备浏览器打开 `http://mitm.it` 安装并信任。

### 手机客户端

手机和电脑连同一个局域网，在手机的 Wi-Fi 设置里：

1. 代理设为手动，填电脑的局域网 IP 和端口 `8080`。
2. DNS 设为电脑的局域网 IP。

### 电脑上的客户端

可以不用伪 DNS：在客户端那台电脑的 hosts 文件里加一行，把游戏域名指向运行代理的电脑
（同一台电脑就写 `127.0.0.1`），然后用 `--no-dns` 启动 launcher：

```text
<运行代理的电脑 IP>  ga-foreign.poker-fate.com
```

客户端的 HTTP 请求同样要经过 mitmweb：把客户端所在系统的 HTTP 代理设为运行代理的电脑、端口 `8080`。

## 启动与停止

```bash
source .venv/bin/activate
.venv/bin/python -m pf_intercept.launcher --bb 10000
```

第一行让 launcher 能在 `PATH` 里找到 `mitmweb`，找不到时会提示并跳过它。
launcher 自己只认 `--no-mitmweb`（跳过 mitmweb）和 `--no-dns`（跳过伪 DNS），其余参数都交给 proxy，
与纯 API 模式的参数相同，见[命令行参数](../../README.md#命令行参数)。

启动后在客户端登录。传了 `--bb` 时 bot 自动进桌；没传时由你在客户端选第一张现金桌，它的盲注就是本轮的起始场次。
客户端里手动离桌或站起会暂停自动选桌，重新入座后恢复。

停止时按 `Ctrl+C`，或在另一个终端运行：

```bash
.venv/bin/python -m pf_intercept.proxy --stop
```

两种方式都会请求打完当前手再离桌，离桌确认最多等 45 秒，然后关闭连接，并停掉 launcher 启动的 mitmweb 和伪 DNS。
`launcher --stop` 与上面的命令等价，都通过 `pf_intercept/logs/proxy.pid` 找到运行中的实例，不会启动任何组件。
同一份仓库同时只能运行一个代理实例。

### 权限

- 伪 DNS 监听 53 端口，需要 root。launcher 以普通用户运行，只对它调用 `sudo`，会提示输入密码或 Touch ID。
  30 秒内没起来就跳过，这时要用 hosts 文件把游戏域名指向本机。
- Linux 默认只有 root 能监听 1024 以下的端口，而 proxy 要监听 443 和 80。需要先放开，
  例如 `sudo sysctl net.ipv4.ip_unprivileged_port_start=80`，或给 Python 授予 `CAP_NET_BIND_SERVICE`。macOS 不需要。

## 登录凭证

大厅自动化和对手历史查询要用 HTTP 凭证。客户端每次经 mitmweb 登录时，
capture_login 都会更新 `local/secrets/headless_session.json`。proxy 收到客户端的登录消息后，
核对文件里的 UID 和登录 key 与这次登录一致，才使用其中的凭证。

这个文件也是纯 API 模式的凭证文件，两边是同一个账号时可以互用。
对不上时 `bot_worker.log` 会记 `[LOBBY] 无法使用当前登录的 HTTP 凭证`，对局照常，但大厅自动化关闭。
这时让客户端退出账号，再经过 mitmweb 重新登录一次。

`local/secrets/login_capture/` 保存每次登录的原始请求和响应，里面有账号密码明文，只留在本机。

## 单独运行组件

排查问题时可以在不同终端分别启动：

```bash
.venv/bin/python -m pf_intercept.proxy --bb 10000
```

```bash
sudo .venv/bin/python -m pf_intercept.dns_server
```

```bash
mitmweb --listen-port 8080 \
  --ignore-hosts "xiaomi.com|xiaomi.net|miui.com|aliyuncs.com" \
  -s pf_reverse/capture_login.py -s pf_reverse/force_domain.py
```

`--ignore-hosts` 只排除已知无关的推送和云存储域名，其余全部拦截。客户端可能用裸 IP 登录，
所以不能反过来只放行游戏域名。这个值以 `pf_intercept.config.MITM_IGNORE_HOSTS` 为准，launcher 用的也是它。

## 进程结构

```text
launcher（proxy 主进程）：WSS 中转、443/80 透传、本机 Web、远程上传
  ├─ pf-bot-worker：BotBridge、会话逻辑、大厅自动化、决策
  ├─ 校准样本 worker：处理摊牌样本队列
  ├─ mitmweb
  └─ 伪 DNS（sudo）
```

主进程收到服务器消息后先转发给客户端，再交给 pf-bot-worker；worker 只返回要发给服务器的请求。
延迟发送的行动在发出前会再核对一次是否仍属于当前这手，过期的直接丢弃。

## 日志与排错

| 文件 | 内容 |
|---|---|
| `pf_intercept/logs/proxy.log` | 连接、WSS 收发、线路选择 |
| `pf_intercept/logs/tcp.log` | 443 / 80 透传 |
| `pf_intercept/logs/bot_worker.log` | 决策、选桌、大厅 `[REWARDS]` 记录 |
| `logs/mitmweb.log` | mitmweb 和两个插件的输出 |

前三个文件每次启动时覆盖。断线和卡顿先看 `proxy.log`，决策和活动问题看 `bot_worker.log`。

| 现象 | 处理 |
|---|---|
| `certs not found` | 先生成证书 |
| 客户端连不上或一直重连 | 检查设备是否信任 `ca.crt`，DNS 或 hosts 是否把游戏域名指到运行代理的电脑 |
| `[LOBBY] 无法使用当前登录的 HTTP 凭证` | 见上面的[登录凭证](#登录凭证) |
| `已有实例运行` | 已有代理实例在跑，先用 `--stop` 停掉 |
