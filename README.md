# PokerFate

德州扑克 AI bot，通过 MITM 代理接入 PokerFate 游戏客户端，实时拦截协议并自动决策。

---

## 架构总览

```
游戏客户端
    │  WSS (TLS)
    ▼
pf_intercept/proxy.py        ← MITM WebSocket 代理，拦截并解码 Protobuf 帧
    │  S2C 事件流
    ▼
pf_intercept/bot.py          ← BotBridge：将游戏事件翻译为 API 调用，注入 C2S 行动
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
| `strategy/postflop.py` | 翻后策略：公牌纹理分析 + c-bet/bet sizing |
| `strategy/gto.py` | GTO 数学：pot odds、MDF、SPR、下注尺度 |
| `strategy/range_estimator.py` | 两阶段 range equity 估算 + 摊牌校准 |
| `strategy/range_hands.py` | Range 组合枚举 |
| `core/hand_evaluator.py` | 7张牌最优5张评估 |
| `core/equity.py` | 蒙特卡洛胜率计算 |
| `core/game_state.py` | 游戏状态数据结构 |

**决策流程**：

```
request_action()
    ├── preflop → 手牌强度百分位 × 位置系数 × 对手类型调整
    └── postflop → 两阶段 range equity
                    ├── Stage 1: 对手 range 估算（基于行动历史 + 摊牌校准）
                    └── Stage 2: 本手 vs range equity → GTO 下注/跟注决策
```

---

### `pf_intercept/` — MITM 代理层

拦截游戏客户端与服务器的 WebSocket 流量，解码 Protobuf，驱动 bot 决策并注入行动。

| 文件 | 职责 |
|------|------|
| `proxy.py` | 主代理：TLS 握手、帧解码、事件分发、C2S 注入 |
| `bot.py` | BotBridge：状态机管理（seat/blinds/筹码/锁仓），翻译游戏事件 |
| `config.py` | 所有可调参数（服务器地址、盈利锁仓阈值、delay 等） |
| `codec.py` | Protobuf 编解码（基于逆向得到的 pb 定义） |
| `framing.py` | 游戏私有帧格式解析 |
| `dns_server.py` | 伪 DNS 服务（Android 模式下将游戏域名解析到本机） |
| `gen_cert.py` | 生成本地 CA + 服务端证书（一次性操作） |
| `gamedata_fetcher.py` | 拉取游戏 REST API 的 30 天玩家统计数据，自动注入对手模型 |
| `pb/` | 逆向得到的 Protobuf 定义编译结果 |

**关键自动行为（BotBridge）**：

- **seat / blinds 自检测**：从 `SitDownRSP` / `EnterRoomRSP` 自动识别，无需手动配置
- **盈利锁仓**：筹码达到阈值（默认 400BB）后自动离桌，以 100BB 重进，避免亏还回去
- **自动续入**：筹码清零后自动 rebuy（次数上限可配置，锁仓成功回桌后上限 +1）
- **人类延迟模拟**：按 street/动作类型/底池大小随机注入思考延迟

---

### `pf_notify/` — 手机推送

通过 [Bark](https://bark.day.app) 向 iPhone 推送关键事件。

| 事件 | 触发时机 |
|------|---------|
| `auto_rebuy` | 筹码清零，自动续入时 |
| `profit_lock_trigger` | 盈利锁仓触发（离桌时） |
| `chips_below_50bb` | 本次进桌后首次跌破 50BB |
| `chips_milestone` | 首次突破 200/300/400…BB 整百里程碑 |
| `wss_disconnected` | WebSocket 异常断开 |
| `gamedata_no_history` | 本次进程首次遇到无历史数据玩家（code=-2），每次启动最多一次 |
| `token_captured` | （模板备用）mitmproxy 捕获到新 token |

设备 Key 存放在 `data/bark_key.txt`（第一行）。

---

### `pf_reverse/` — 逆向工程

协议逆向过程的产出与笔记，见 `pf_reverse/REVERSE_NOTES.md`。不参与运行时。

---

### `data/` — 运行时数据

| 文件 | 说明 |
|------|------|
| `bark_key.txt` | Bark 设备 Key（第一行） |
| `auth_token.txt` | 游戏 REST API 鉴权 token（由 `force_domain.py` 登录时自动写入，无需手动填写） |
| `ip_cache.json` | DNS 解析结果缓存（跨重启复用，加速连接） |
| `resources.md` | 游戏内角色/皮肤/道具 ID 速查表 |

---

## 快速启动（代理模式）

### 1. 生成证书（一次性）

```bash
python -m pf_intercept.gen_cert
```

输出到 `pf_intercept/certs/`，将 `ca.crt` 安装为系统受信任根 CA。

### 2. 配置流量劫持

**Windows**（hosts 文件重定向）：

在 `C:\Windows\System32\drivers\etc\hosts` 添加：

```
127.0.0.1  zga-entry.poker-fate.net
```

**Android**（DNS 模式）：

**方式一：DNS 劫持（首选）**

1. 手机和电脑连接同一局域网
2. 手机 Wi-Fi 设置 → 修改 DNS 为电脑的局域网 IP
3. 电脑启动伪 DNS 服务：
   ```bash
   sudo python -m pf_intercept.dns_server
   ```
   伪 DNS 会将游戏域名解析到本机，其余域名转发上游正常解析。

**方式二：HTTP 代理（DNS 无法生效时的备选）**

若手机仍无法连接到电脑（部分机型 DNS 不走 Wi-Fi 设置），改用 HTTP 代理模式：

1. 手机 Wi-Fi 设置 → 代理 → 手动，填入电脑局域网 IP 和端口 `8080`
2. 电脑安装 mitmproxy：
   ```bash
   pip install mitmproxy
   ```
3. 启动 mitmweb，挂载 `force_domain.py` 插件：
   ```bash
   mitmweb --listen-port 8080 -s pf_reverse/force_domain.py
   ```
   插件会：
   - 自动从登录响应中提取 `authorization` token，写入 `data/auth_token.txt`（无需手动填写）
   - 过滤服务器列表，只保留域名条目，将首选域名写入 `pf_intercept/discovered_server.json`
4. 手机首次使用需安装 mitmproxy 的 CA 证书（访问 `mitm.it` 下载后安装）。
5. 游戏登录完成后（`force_domain.py` 打印出保留的服务器），再按方式一启动
   `pf_intercept.dns_server`，让后续 WSS 连接走到本机代理。

### 3. 启动代理

```bash
python -m pf_intercept.proxy
```

常用参数：

```bash
python -m pf_intercept.proxy \
  --rebuy 3 \          # 最大自动续入次数（默认 1）
  --no-range-equity    # 禁用两阶段 range equity，使用纯蒙卡胜率
```

启动后打开游戏客户端正常进桌，proxy 自动检测 seat/blinds 并开始决策。

---

## 关键配置（`pf_intercept/config.py`）

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `PROFIT_LOCK_BB_THRESHOLD` | `400` | 触发盈利锁仓的筹码阈值（BB 倍数） |
| `PROFIT_LOCK_REENTER_DELAY_SEC` | `4.0` | 离桌后等待多久再重进（秒） |
| `PROFIT_LOCK_LEAVE_SEAT_RESERVE` | `True` | 离桌时是否留座 |
| `ACTION_INJECT_DELAY_MAX_SEC` | `3.0` | 模拟人类思考的最长延迟（秒） |
| `GAMEDATA_HTTP_HOST` | `awsb-entry.poker-fate.com` | 拉取玩家统计的 API 域名 |

---

## 依赖

```bash
pip install websockets protobuf certifi cryptography
```

Python 3.12+。
