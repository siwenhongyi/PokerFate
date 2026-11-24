# PokerFate

德州扑克 AI bot，通过 MITM 代理接入 PokerFate 游戏客户端，实时拦截协议并自动决策。

---

## 架构总览

```
游戏客户端
    │  WSS (TLS)
    ▼
pf_intercept/proxy/         ← MITM 代理包，拦截并解码 Protobuf 帧
    │  S2C 事件流
    ▼
pf_intercept/bot/bridge.py  ← BotBridge：将游戏事件翻译为 API 调用，注入 C2S 行动
    │
    ▼
pokerfate/api.py             ← 对外接口：手牌管理、决策请求、对手建模
    │
    ├── bot/poker_bot.py     ← 核心决策引擎（preflop + postflop + GTO）
    ├── bot/opponent_model.py← 对手统计建模（VPIP/PFR/AF/3bet/cbet/WTSD）
    └── strategy/            ← 翻前策略、翻后策略、GTO 数学、range 估算
```

---

## 模块说明

### `pokerfate/` — AI 引擎

核心决策层，不依赖游戏客户端，可独立使用。

| 文件 | 职责 |
|------|------|
| `api.py` | 外部接入接口，详见 `pokerfate/INTEGRATION.md` |
| `bot/poker_bot.py` | 主决策逻辑，整合 preflop/postflop/GTO/range |
| `bot/opponent_model.py` | 对手建模：统计 VPIP/PFR/AF 等，输出可剥削调整 |
| `strategy/preflop.py` | 翻前策略：基于手牌强度百分位 + 位置 |
| `strategy/postflop.py` | 翻后策略兼容层，封装 `strategy/v3/` 决策引擎 |
| `strategy/v3/` | 翻后目的选择、下注尺度、攻防决策 |
| `strategy/gto.py` | GTO 数学：pot odds、MDF、SPR、下注尺度 |
| `strategy/range_v2/` | range equity：1326 组合建模、Bayesian range tracker、range equity |
| `core/hand_evaluator.py` | 7张牌最优5张评估 |
| `core/equity.py` | 蒙特卡洛胜率计算 |
| `core/game_state.py` | 游戏状态数据结构 |

**决策流程**：

```
request_action()
    ├── preflop → 手牌强度百分位 × 位置系数 × 对手类型调整
    └── postflop → Bayesian range tracker → range equity → v3 engine
```

---

### `pf_intercept/` — MITM 代理层

拦截游戏客户端与服务器的 WebSocket 流量，解码 Protobuf，驱动 bot 决策并注入行动。

| 文件 | 职责 |
|------|------|
| `launcher.py` | 代理模式一键启动器：mitmweb + 伪 DNS + proxy，见下文「快速启动（代理模式）」 |
| `proxy/` | 主代理包：WSS runtime、TCP 透传、路由选择、TLS、日志和监控 |
| `bot/bridge.py` | BotBridge：状态机管理（seat/blinds/筹码/锁仓），翻译游戏事件 |
| `config/` | 所有可调参数（服务器地址、盈利锁仓阈值、delay 等） |
| `wire/codec.py` | Protobuf 编解码（基于逆向得到的 pb 定义） |
| `wire/framing.py` | 游戏私有帧格式解析 |
| `wire/pb/` | 逆向得到的 Protobuf 定义编译结果 |
| `dns/server.py` | 伪 DNS 服务（Android 模式下将游戏域名解析到本机） |
| `certificates/generator.py` | 生成本地 CA + 服务端证书（一次性操作） |
| `game_api/` | 游戏 REST API helper，包括玩家统计和收藏牌局接口 |
| `tools/gen_pb2.sh` | 根据 `pf_reverse/output/proto/Proto` 重新生成 `wire/pb` |

**关键自动行为（BotBridge）**：

- **比赛房完全旁路**：进入 SNG / MTT / 好友 SNG（`EnterRoomRSP` 的 game_type 或 `sngroom_info` / `mttroom_info`）后，程序只做识别，不决策、不注入、不采集、不记资金、不推送，由玩家手动打；进入下一个非比赛房自动恢复托管
- **seat / blinds 自检测**：从 `SitDownRSP` / `EnterRoomRSP` 自动识别
- **盈利锁仓**：现金桌筹码达到阈值（默认 200BB）后自动离桌，以 100BB 重进，避免亏还回去；好友房不触发
- **净亏损上限**：本次启动最多净亏 (1 + `--max-auto-rebuy`) 个 100BB 买入（按启动场次的大盲算）。
  破产买入、桌上补码、换桌或异常离桌后的重新买入都先过这一条：已亏的 + 桌上的 + 要带的不超过上限。
  放不下 100BB 就带上限还容得下的最大一档，连最小一档（20BB）都放不下就停在大厅并推送 `loss_stop`。
  赢到的已经在净盈亏里，所以盈利锁仓不再增加次数，也不再单独数破产买入的次数
- **自动续入**：筹码清零后自动 rebuy，买多少、买不买由净亏损上限决定
- **桌上补码**：一手结束时桌上筹码低于 70BB（没输光），用客户端「补充筹码」同款的 `pb.SetRebyREQ`
  在桌上补到不超过 100BB 的最大一档，下一手发牌前到账，不用离桌；好友房不触发。
  补多少受净亏损上限约束
- **人类延迟模拟**：按 street/动作类型/底池大小随机注入思考延迟

---

### `pf_notify/` — 手机推送

通过 [Bark](https://bark.day.app) 向 iPhone 推送。Bark App 里的设备 Key 写在 `local/secrets/bark_key.txt` 的第一行；没有这个文件就不推送。

会推送的场景：

- 筹码清零，自动续入
- 桌上补码到账
- 盈利锁仓触发，准备离桌
- 净亏损到上限，停在大厅
- 选桌让 bot 离开一张打过牌的桌子（没有真人、真人少于人机等）
- 选桌在所有场次都找不到合格的牌桌，停在大厅
- 单手盈亏达到 20BB
- 第一次遇到没有历史数据的对手（每次启动最多一次）；对手历史数据接口鉴权失败
- 校准队列积压：积压到提醒线、积压到暂停线（停止新对局）、恢复
- 仅 proxy 模式：WebSocket 异常断开、恢复

比赛房（SNG/MTT）和好友房里不发牌桌相关的提醒，比赛房连断线提醒也不发；校准队列提醒由独立的 worker 发，不看房间。

---

### `pf_reverse/` — 逆向工程

协议逆向过程的产出与笔记，见 `pf_reverse/REVERSE_NOTES.md`。不参与运行时。

客户端更新后，直接用新 APK 重建 proto/lua，再重新生成 pb：

```bash
.venv/bin/python pf_reverse/extract_resources.py ~/Downloads/PokerFate_Android.apk
bash pf_intercept/tools/gen_pb2.sh
```

---

### `local/` — 本机数据（不入库）

目录名叫 `data` 的都入库（如 `pokerfate/data/`：翻牌书、GTO 表、拟合出的模型）；只在本机才有的东西全部放在顶层 `local/`，由 `.gitignore` 的一条规则忽略。

| 子目录 | 内容 |
|------|------|
| `local/secrets/` | 凭证和密钥：`bark_key.txt`（Bark 设备 Key，第一行）、`auth_token.txt`（游戏 REST API 鉴权 token，由 `force_domain.py` 登录时自动写入）、`headless_session.json`、`login_capture/`、`remote_live.json`（及它旁边的服务器证书和上传锁） |
| `local/state/` | 不含凭证的小文件：`ip_cache.json`（DNS 解析结果缓存）、`discovered_server.json`、`selected_route.json`、`force_domain_original_response.json`、`hero_names.json` |
| `local/models/` | bot 运行中学出来并不断改写的模型：`opponents.json`、`robots.json`、`range_v2_empirical_model.json` |
| `local/training/` | 从对局里抽出的训练样本（`*.rows.jsonl`、`river_value_sizing.*.jsonl`）和它的工作队列 `live_spool/` |

---

纯 API 模式的基金、每日／每周任务自动领取默认开启，配置、日志与异常处理见
[自动领取说明](pf_intercept/headless/README.md)。

## 快速启动（代理模式）

日常只用一条命令。`pf_intercept/launcher.py` 会把代理模式需要的三样东西一次拉起来：

```bash
.venv/bin/python -m pf_intercept.launcher
```

| 顺序 | 启动的东西 | 作用 |
|------|-----------|------|
| 1 | `mitmweb`（子进程，端口 `8080`） | HTTP 代理，挂载 `pf_reverse/force_domain.py`：从登录响应提取 `authorization` token 写入 `local/secrets/auth_token.txt`；过滤服务器列表，只保留证书覆盖范围内的域名服务器，首选域名记到 `local/state/discovered_server.json` |
| 2 | 伪 DNS `pf_intercept.dns_server`（子进程，端口 `53`） | 把游戏域名解析到本机，其余域名转发上游正常解析 |
| 3 | proxy（launcher 进程本身） | WSS MITM（`9012`）、`443` / `80` 透传、bot 决策、牌局 Web（`9022`） |

launcher 的行为：

- **权限**：只有伪 DNS 需要 root（53 端口）。macOS / Linux 下 launcher 自己调 `sudo`，会要密码或 Touch ID；
  Windows 下弹 UAC。launcher 本身用普通用户运行即可，不需要给整条命令加 `sudo`。
- **mitmweb**：在 `PATH` 里找 `mitmweb` 命令，找不到就打印提示并跳过。只装在 `.venv` 里时先
  `source .venv/bin/activate` 再启动。输出写到项目根目录的 `logs/mitmweb.log`，不自动打开浏览器。
- **伪 DNS 起不来**（取消授权、53 端口被占、30 秒内没就绪）：只跳过这一项，proxy 照常启动，
  这时要靠 hosts 文件把游戏域名指到本机。
- **停止**：Ctrl+C，mitmweb 和伪 DNS 跟着一起停。例外是 Windows：伪 DNS 跑在 UAC 拉起的独立窗口里，要手动关。

### 1. 一次性准备

**证书**

```bash
.venv/bin/python -m pf_intercept.gen_cert
```

输出到 `pf_intercept/certs/`，将 `ca.crt` 安装为受信任根 CA。没有证书时 proxy 报 `certs not found` 后直接退出。

**mitmproxy**（不在 `requirements.txt` 里）

```bash
.venv/bin/python -m pip install mitmproxy
```

**Android 手机**（和电脑在同一局域网）

1. Wi-Fi 设置 → 代理 → 手动，填电脑的局域网 IP 和端口 `8080`。登录请求经过 mitmweb。
2. Wi-Fi 设置 → 修改 DNS 为电脑的局域网 IP。游戏的 WSS 连接由伪 DNS 引到本机 proxy。
3. 首次使用安装 mitmproxy 的 CA 证书（手机浏览器访问 `mitm.it` 下载后安装）。

**Windows 客户端**（和 proxy 在同一台机器，用 hosts 文件代替伪 DNS）

在 `C:\Windows\System32\drivers\etc\hosts` 添加：

```
127.0.0.1  ga-foreign.poker-fate.com
```

启动时加 `--no-dns`。proxy 启动时也会打印需要的 hosts 条目。

### 2. 启动

```bash
.venv/bin/python -m pf_intercept.launcher --max-auto-rebuy 3 --profit-lock-bb 200
```

launcher 自己的参数：

- `--no-mitmweb`：不拉起 mitmweb（已在别处运行，或不需要）。
- `--no-dns`：不拉起伪 DNS（用 hosts 文件代替）。

其余参数原样交给 proxy：

- `--max-auto-rebuy N`：净亏损上限，本次启动最多净亏 (1+N) 个 100BB 买入。代理模式只接受 1–20，默认 1（即 200BB）。
- `--profit-lock-bb BB`：盈利锁仓阈值；不传则使用 `pf_intercept.config` 的 `PROFIT_LOCK_BB_THRESHOLD`。

启动后打开游戏客户端正常登录、进桌，proxy 自动检测 seat/blinds 并开始决策。

### 3. 牌局 Web

默认监听 `0.0.0.0:9022`：本机打开 `http://127.0.0.1:9022`，局域网内用电脑 IP 访问牌局与资金看板。
启动时会打印实际地址（`[proxy] 牌局 Web ...`）。

牌局 Web 随 proxy 一起启动，没有命令行开关；地址和端口在 `pf_intercept/config/` 的
`ENTERTAINMENT_WEB_HOST` / `ENTERTAINMENT_WEB_PORT`。

### 4. 单独启动各部分

排查问题、或者只需要其中一部分时用。launcher 做的就是下面三条：

```bash
# proxy（参数同上：--max-auto-rebuy、--profit-lock-bb）
.venv/bin/python -m pf_intercept.proxy

# 伪 DNS
sudo .venv/bin/python -m pf_intercept.dns_server

# mitmweb
mitmweb --listen-port 8080 --ignore-hosts "xiaomi.com|xiaomi.net|miui.com|aliyuncs.com" -s pf_reverse/force_domain.py
```

`--ignore-hosts` 用的是排除法：只排除已知与游戏无关的推送 / 云存储域名，其余全部拦截；不要反过来只放行游戏域名。
真机登录可能走裸 IP（见 `pf_reverse/output/lua/src/app/Constants.lua` 的 `G_HTTP_URL_2/_3/_4`），
域名白名单会直接漏掉这些连接。这串值的唯一来源是 `pf_intercept.config.MITM_IGNORE_HOSTS`，launcher 用的也是它。

---

## 快速启动（纯 API / headless 模式）

跟上面的代理模式是两条独立的路：headless 不需要设备常驻连代理、不需要 DNS 劫持，直接用 WSS 连游戏服务器。
代价是拿凭证本身仍然离不开一台真机——登录接口需要游戏客户端自带的网易易盾风控 SDK 在运行时生成的动态 token，
这段 SDK 没法在纯 Python 里复现，所以不存在"完全不用设备就能登录"的办法；
但只需要**登录这一步**在真机上做一次，拿到凭证之后的日常对局就不再需要设备或代理了。

### 1. 首次获取凭证（新用户，或凭证过期后重做一次）

凭证存在 `local/secrets/headless_session.json`，约 30 天过期；过期后 `pf_intercept.headless` 会报
`ResumeError`（提示"请重新薅凭证"），重复这一步即可。

```bash
.venv/bin/python -m pf_intercept.headless.harvest_session
```

这个脚本会自己拉起 `mitmdump` 挂载 `pf_reverse/capture_login.py`：

- 默认不加 `--mode upstream`；只有当脚本探测到本机直连不了游戏服务器时，才会去读
  `https_proxy`/`HTTPS_PROXY`/`all_proxy` 等环境变量，复用你已经配置好的本地代理/VPN——
  不会凭空假设一个代理端口。
- `--ignore-hosts` 用的是排除法（见 `pf_intercept.config.MITM_IGNORE_HOSTS`），不是只放行游戏域名；
  真机登录可能走裸 IP（`Constants.lua` 的 `G_HTTP_URL_2/_3/_4`），域名白名单会漏掉这些连接。

脚本启动后按提示操作：

1. 手机 Wi-Fi 设置 → 代理 → 手动，填脚本打印出来的局域网 IP 和端口（默认 `8080`）
2. 首次使用本机 mitmproxy 需要装根证书（手机浏览器访问 `mitm.it`）
3. 手机上正常打开 PokerFate app，用真实账号登录一次

脚本看到 `capture_login.py` 写出新的 `local/secrets/headless_session.json` 后会自动停掉 mitmdump 并退出；
之后不再需要这台手机。

### 2. 启动 headless

```bash
.venv/bin/python -m pf_intercept.headless --bb 10000 --buyin-bb 50
```

常用参数：

- `--bb`：进桌的大盲（不传则只登录+心跳，不进桌）。
- `--buyin-bb`：买入多少个大盲，默认 100。
- `--max-auto-rebuy` / `--profit-lock-bb`：含义同代理模式；headless 下 `--max-auto-rebuy` 还可以传 `0`（净亏一个买入即停）。
- `--topup-below-bb`：桌上筹码低于多少个大盲就在桌上补码（默认 70，`0` 关闭）。
- `--no-web`：不启动实时对局 Web（默认启动，监听 `0.0.0.0:9022`，手机同 WiFi 可看）。
- `--stop`：校验 `pf_intercept/logs/headless.pid` 对应实例后发送优雅停止请求，不登录游戏。

优雅停止（终端或 PyCharm 启动均适用）：

```bash
.venv/bin/python -m pf_intercept.headless --stop
```

PID 由 bot 自动维护，退出后删除；同一项目通过文件锁防止重复启动。
停止请求发送后仍需等待离桌及收尾，详见 [运行说明](pf_intercept/headless/README.md)。

日志见 `pf_intercept/logs/headless.log`；基金/任务自动领取见
[自动领取说明](pf_intercept/headless/README.md)。

---

## 关键配置（`pf_intercept/config/`）

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `PROFIT_LOCK_BB_THRESHOLD` | `200` | 触发盈利锁仓的筹码阈值（BB 倍数） |
| `PROFIT_LOCK_REENTER_DELAY_SEC` | `4.0` | 离桌后等待多久再重进（秒） |
| `TOPUP_BELOW_BB` | `70` | 一手结束时桌上筹码低于这个数（BB 倍数）就在桌上补码；`0` 关闭 |
| `TOPUP_TARGET_BB` | `100` | 补码补到不超过这个数的最大一档（20–30BB 每 1BB 一档，40BB 起每 10BB 一档） |
| `ACTION_INJECT_DELAY_MAX_SEC` | `3.0` | 模拟人类思考的最长延迟（秒） |
| `GAMEDATA_HTTP_HOST` | `ga-foreign.poker-fate.com` | 拉取玩家统计的 API 域名 |

---

## 依赖

```bash
.venv/bin/python -m pip install -r requirements.txt
```

Python 3.12+。完整依赖以 `requirements.txt` 为准；其中包含 AI 决策运行依赖、WSS 代理依赖和测试工具。代理模式的 launcher 和 headless 取凭证脚本用到的 `mitmproxy` 不在其中，按上面的步骤单独安装。
