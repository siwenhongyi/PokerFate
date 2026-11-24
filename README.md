# PokerFate

PokerFate 德州扑克游戏的自动打牌程序。

它有两种接入方式。纯 API 模式（headless）用保存的登录凭证直接连接游戏服务器。
代理模式作为 MITM 代理跟着游戏客户端运行。两种方式共用同一套对局逻辑、决策引擎、对手模型、选桌和大厅自动化。

## 功能

- **决策**：翻前用规则引擎；单挑翻牌查离线 CFR 翻牌书；单挑转牌、河牌用本地 solver 实时求解；其余情况回到规则引擎。
- **对手建模**：按 UID 累计对手统计，并参考服务器的历史数据。用服务器的人机计数识别平台机器人，人机的牌不参与学习。
- **牌桌与资金**：自动选桌，离开没有真人或人机多于真人的桌子；盈利锁仓、桌上补码、整轮净亏损上限。
- **大厅自动化**：领取基金、任务、签到、邮件和各类活动奖励，并完成任务需要的小游戏、竞猜和互动。
- **观看与通知**：本机 Web 显示实时牌桌和资金；可选的 VPS 只读观看页；Bark 手机通知。

## 运行环境

- macOS 或 Linux。进程锁和 DNS 提权用到 Unix 接口，Windows 上无法启动 bot。
- Python 3.12 及以上。
- mitmproxy：采集登录凭证和代理模式要用，不在 `requirements.txt` 里。
- Rust 工具链：编译实时求解用的 solver。可以不装，此时转牌、河牌改用规则引擎。
- 一部装有游戏的手机：首次使用和凭证过期时，用它登录一次。

## 安装

在项目根目录执行：

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m pip install mitmproxy
cargo build --release --manifest-path pokerfate/solver/pf_solver/Cargo.toml
```

solver 的构建和加载规则见[决策引擎](pokerfate/decision/README.md#构建本地-solver)。

## 快速开始

以下是纯 API 模式。代理模式见[下文](#代理模式)。

### 1. 采集登录凭证

游戏登录需要客户端里网易易盾 SDK 生成的风控 token，程序无法自己登录。
首次使用和凭证过期时，让手机经过临时代理登录一次：

```bash
source .venv/bin/activate
.venv/bin/python -m pf_intercept.headless.harvest_session
```

第一行让脚本能在 `PATH` 里找到 `mitmdump`。然后按终端提示操作：

1. 手机和电脑连同一个局域网，把手机 Wi-Fi 代理设为终端打印的 IP 和端口（默认 `8080`）。
2. 第一次使用时，在手机浏览器打开 `http://mitm.it`，安装并信任 mitmproxy 根证书。
3. 打开游戏，退出账号后重新登录。
4. 终端显示凭证已更新、脚本退出后，恢复手机原来的代理设置。

凭证保存在 `local/secrets/headless_session.json`，通常约 30 天有效。参数和排错见 [headless 运行说明](pf_intercept/headless/README.md#登录凭证)。

### 2. 启动

进大盲 10,000 的现金桌，每次买入 100BB：

```bash
.venv/bin/python -m pf_intercept.headless --bb 10000 --buyin-bb 100
```

浏览器打开 <http://127.0.0.1:9022> 查看实时牌桌和资金。不传 `--bb` 时只登录，保持连接 30 秒后退出。

```bash
nohup .venv/bin/python -m pf_intercept.headless --bb 10000 --buyin-bb 100 \
  > /dev/null 2>&1 & disown
```

程序自己写文件日志，丢掉控制台输出不影响日志。但参数错误和“已有实例在运行”只打印在控制台，
所以后台启动后要确认 `pf_intercept/logs/headless.pid` 已生成、`headless.log` 有新内容。

### 3. 停止

```bash
.venv/bin/python -m pf_intercept.headless --stop
```

bot 会打完当前手再离桌退出。命令返回时进程可能还没退出，重启前等 PID 文件消失。前台运行时也可以按 `Ctrl+C`。

## 代理模式

游戏客户端照常登录和显示，代理在中间解码消息，并替客户端行动。
需要先生成证书、设置手机代理和 DNS，步骤见[代理模式说明](pf_intercept/proxy/README.md)。准备好后：

```bash
source .venv/bin/activate
.venv/bin/python -m pf_intercept.launcher --bb 10000
```

## 命令行参数

两种入口使用同一套参数（[pf_intercept/options.py](pf_intercept/options.py)）。`--help` 列出全部参数：

```bash
.venv/bin/python -m pf_intercept.headless --help
```

| 参数类别 | 说明 |
|---|---|
| 选桌、买入、锁仓、补码、净亏损上限 | [对手信息与牌桌管理](pf_intercept/bot/README.md#控制参数) |
| 凭证文件、停止、通知、调试输出 | [headless 运行说明](pf_intercept/headless/README.md#进程参数) |
| 本机 Web、远程上传 | [Web 说明](pf_entertainment/README.md#监听与开关) |
| 大厅自动化总开关和各模块开关 | [大厅自动化](pf_intercept/headless/lobby/README.md#关闭功能) |

策略开关是环境变量，默认值就是实战配置，一般不用设置，见[决策引擎](pokerfate/decision/README.md#引擎与开关)。

## 文档

第一次使用：读完本页，再看对手信息与牌桌管理、大厅自动化和 Web。
改策略或接入其他牌桌：看决策引擎和 API 接入。游戏客户端更新后：看客户端协议与资源参考。

| 内容 | 文档 |
|---|---|
| 凭证采集、进程管理、断线重连与排错 | [headless 运行说明](pf_intercept/headless/README.md) |
| 证书、设备设置、组件与端口 | [代理模式](pf_intercept/proxy/README.md) |
| 对手信息、人机识别、选桌与资金限制 | [对手信息与牌桌管理](pf_intercept/bot/README.md) |
| 活动、任务、日常与奖励记账 | [大厅自动化](pf_intercept/headless/lobby/README.md) |
| 本机 Web、实时牌桌与资金展示 | [Web 说明](pf_entertainment/README.md) |
| VPS 观看服务的部署与维护 | [远程 Live](pf_entertainment/remote_live/README.md) |
| 决策链路、规则引擎、范围层、solver 与翻牌书 | [决策引擎](pokerfate/decision/README.md) |
| 把决策引擎接入其他牌桌系统 | [API 接入](pokerfate/INTEGRATION.md) |
| 回放、重新拟合模型 | [离线脚本](scripts/README.md) |
| 客户端协议、资源与版本维护 | [客户端协议与资源参考](pf_reverse/REVERSE_NOTES.md) |

## 目录结构

```text
headless（直接连接） ─┐
                    ├─ BotBridge ─ PokerFateAPI ─ 决策引擎
proxy（客户端代理） ─┘       │
                      对手模型、牌桌管理、大厅自动化
```

| 目录 | 职责 |
|---|---|
| `pokerfate/` | 可单独接入的决策引擎、对手模型、solver 和翻牌书；`pokerfate/data/` 是随仓库提供的模型和翻牌书 |
| `pf_intercept/` | 游戏连接、协议解码、对局桥接、选桌和大厅自动化 |
| `pf_entertainment/` | 本机 Web 和 VPS 观看服务 |
| `pf_notify/` | Bark 手机通知 |
| `pf_reverse/` | 客户端协议、安装包资源和热更新读取 |
| `scripts/` | 回放和重新拟合模型的脚本 |
| `analysis/` | 离线分析工具，读本机的实战日志；每个模块开头写了用途和用法 |
| `tests/` | 单元测试 |
| `local/` | 只在本机的凭证、状态、模型和样本，Git 忽略 |

## 本地数据

`local/` 不进 Git，新克隆的仓库里没有，程序运行时按需创建。

| 目录 | 内容 | 丢失后 |
|---|---|---|
| `local/secrets/` | 登录凭证 `headless_session.json`；原始登录抓包 `login_capture/`（含账号密码明文）；代理模式登录时写入的 `auth_token.txt`；Bark 设备 Key `bark_key.txt`；远程 Live 配置和证书 | 重新采集或重新配置 |
| `local/state/` | 线路缓存、服务器发现记录；离线工具用来认出自己账号的 `hero_names.json`；雷达忽略列表 `lobby_ignores.json` | 缓存会自动重建；后两个要重新填写 |
| `local/models/` | 运行中累计的对手统计 `opponents.json`（含 hero 胜率校准）、人机名单 `robots.json`、范围层经验模型 `range_v2_empirical_model.json` | 从零积累；人机名单可从网络日志重建，经验模型可用脚本重建 |
| `local/training/` | 训练样本、河牌价值尺度样本、摊牌样本队列 `live_spool/` | 只能靠实战重新积累 |
| `local/notes/` | 个人笔记 | — |

需要手机通知时，把 [Bark](https://bark.day.app) 的设备 Key 写进 `local/secrets/bark_key.txt` 第一行；
没有这个文件就不发通知。通知覆盖牌桌切换、资金限制、大额单手盈亏和运行异常。

实战日志同样只在本机，重新拟合模型要用它们，建议定期备份 `local/` 和各个 `logs/` 目录。

## 日志

| 文件 | 内容 |
|---|---|
| `pf_intercept/logs/headless.log` | headless 的登录、连接、收发消息、运行状态和大厅 `[REWARDS]` 记录 |
| `pf_intercept/logs/proxy.log`、`tcp.log`、`bot_worker.log` | 代理的连接、透传和 bot 工作进程；每次代理启动时覆盖 |
| `logs/mitmweb.log` | launcher 启动的 HTTP 抓包进程输出 |
| `pf_intercept/logs/table_select.jsonl` | 选桌依据、场次和进出桌记录 |
| `pf_intercept/logs/rewards.jsonl` | 大厅的领取、消耗和失败明细 |
| `pokerfate/logs/pokerfate.log` | 策略决策和逐手结算（JSONL）；每次启动时上一份内容并入 `pokerfate/logs/archive/` |
| `pf_entertainment/logs/web.log` | Web 启动、访问地址和请求处理异常 |

`headless.log` 记录了发出的登录消息，里面有登录 key，不要外传。

## 开发与测试

```bash
.venv/bin/python -m pytest -q
```

- 测试只允许连接本机：`tests/conftest.py` 拦截其他网络连接和域名解析，并清掉代理环境变量。
- 测试读仓库里的安装包配置表，不读本机同步的热更新。
- 测试中创建的 `PokerFateAPI` 默认不写对手模型和日志。
- 没有编译 solver 时，依赖它的测试会跳过。
- 改了协议定义后要重新生成 Python 绑定，见[客户端协议与资源参考](pf_reverse/REVERSE_NOTES.md#版本维护)。
