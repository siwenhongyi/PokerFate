# PokerFate 接入方案（hosts 劫持 + 本地 TLS 代理）

## 架构总览

```
[PokerFate.exe (Windows)]
        │
        │  DNS 解析 game-server:9012
        │  → hosts 文件强制返回 127.0.0.1
        │
[pf_intercept/proxy.py  127.0.0.1:9012]
        │  TLS 终止（用我们生成的证书）
        │  WSS MITM：解析/注入游戏消息
        │  TCP 透传：其他端口（443/80）原样转发
        │
[Real Server  wss://game-server:9012]
```

**优势**：不需要 Proxifier，只影响游戏服务器那一个域名，其他流量完全不受影响。

---

## 数据包格式（来自 Net.lua 逆向）

```
[4B total_len BE] [2B type_len BE] [N B type_name] [4B room_id BE] [M B pb_body]

total_len = 2 + len(type_name) + 4 + len(pb_body)
完整帧 = 4 + total_len 字节
```

- `type_name`：完整消息名，如 `pb.ActionREQ`、`pb.HandCardRSP`
- `room_id`：当前房间 ID
- `pb_body`：protobuf2 编码消息体

---

## 卡牌编码（来自 GFunctions.lua + config.lua）

```
code = num + suit * 256
num  : 2='2', 3='3', ..., 13='K', 14='A'
suit : 0='d'(方块)  1='c'(梅花)  2='h'(红桃)  3='s'(黑桃)
```

转换为 pokerfate 牌字符串：`_RANK_TO_STR[code % 256] + _SUIT_TO_STR[code // 256]`

---

## 自动检测（无需手动配置）

| 参数 | 来源消息 | 字段 |
|------|----------|------|
| 我的座位号 | `pb.SitDownRSP` | `seatid` |
| 大盲注额 | `pb.EnterRoomRSP` | `room_info.bb` |
| 小盲注额 | `pb.EnterRoomRSP` | `room_info.sb` |

`PokerFateAPI` 在首次收到 `DealerInfoRSP` 时懒初始化（确保 seat 和 blinds 已就绪）。

---

## 关键消息清单

### Server → Client（完整处理）

| 消息 | 触发动作 |
|------|----------|
| `pb.EnterRoomRSP` | 检测 BB/SB → 更新盲注 |
| `pb.SitDownRSP` | 检测我方座位号 |
| `pb.DealerInfoRSP` | 新手牌开始 → `api.new_hand()` |
| `pb.HandCardRSP` | `api.deal_hole_cards()` |
| `pb.RoundStartBRC` | `api.deal_board()`（仅翻牌/转牌/河牌）|
| `pb.ActionBRC` | 累加 pot，记录弃牌 → `api.notify_action()`（非我方）|
| `pb.RoundOverBRC` | 用 pool 修正 pot 总量 |
| `pb.ActionNotifyBRC` (我方座位) | `api.request_action()` → 注入 ActionREQ |
| `pb.WinnerRSP` | `api.hand_over()` |

### Server → Client（透传，不解析）

`HeartBeatRSP`、`HBPingRSP`，以及所有不在 WATCH_S2C 中的消息。

### Client → Server（透传，仅日志）

`pb.ActionREQ`（记录我方行动）

---

## action_type 取值

| 值 | 行动 | `BotDecision.action` |
|----|------|---------------------|
| 1 | Fold | `"fold"` |
| 2 | Check | `"check"` |
| 3 | Call | `"call"` |
| 4 | Raise / Bet | `"raise"` |
| 5 | All-in | `"raise"`（amount = max_chipin）|

---

## 证书方案

mitmproxy 的原理和我们完全一样：生成本地 CA → 签发服务器证书 → 安装 CA 到系统信任根。

```bash
python -m pf_intercept.gen_cert
# 输出:
#   pf_intercept/certs/ca.crt      ← 安装到 Windows 受信根
#   pf_intercept/certs/server.crt  ← 代理使用
#   pf_intercept/certs/server.key  ← 代理使用
```

Windows 安装 CA：双击 `ca.crt` → 安装证书 → 本地计算机 → 受信任的根证书颁发机构。

---

## 非 9012 端口透传

代理同时监听 `PASSTHROUGH_PORTS`（默认 443、80）。这些端口上的连接是纯 TCP 隧道，不做任何 TLS 拆包，直接转发到真实服务器。游戏使用同一域名的其他 HTTPS 请求（如登录 API）走这条路，不受影响。

---

## 模块结构

```
pf_intercept/
  config.py         服务器地址、证书路径、BB/SB 回退默认值
  framing.py        帧编解码 + FrameBuffer（粘包处理）
  codec.py          protobuf encode/decode（依赖编译后的 pb2）
  bot.py            BotBridge：事件处理 + PokerFateAPI 桥接
  proxy.py          asyncio WSS MITM 代理主程序
  gen_cert.py       生成本地 CA + 服务器证书
  gen_pb2.sh        编译 proto → pb2.py
  certs/            生成的证书（gitignore）
  pb/               编译后的 pb2 模块（gitignore）
  INTERCEPT_PLAN.md 本文档
```

---

## 启动顺序（全流程）

```bash
# 1. 编译 proto（一次性）
./pf_intercept/gen_pb2.sh

# 2. 生成证书（一次性）
python -m pf_intercept.gen_cert

# 3. Windows hosts 文件追加一行：
#    127.0.0.1  <game-server-hostname>

# 4. Windows 安装 ca.crt → 受信根证书

# 5. 填写 config.py 的 SERVER_HOST（游戏服务器域名）

# 6. 启动代理
python -m pf_intercept.proxy
```

启动后日志会依次出现：
```
[BOT] Waiting for SitDownRSP and EnterRoomRSP to detect seat / blinds
[BOT] Big blind detected: 2.0
[BOT] Small blind detected: 1.0
[BOT] My seat detected: 3
[BOT] PokerFateAPI ready — seat=3  BB=2.0  SB=1.0
[BOT] Decision: BotDecision(raise, amount=6.0)  (street=preflop ...)
[BOT→S] ActionREQ  action_type=4  chips=6
```

---

## 唯一需要手动填的配置

`config.py` 中的 `SERVER_HOST`：游戏服务器域名（从 mitmproxy 抓包里看到的 WSS 连接目标）。
