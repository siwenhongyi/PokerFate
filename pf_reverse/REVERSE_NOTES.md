# 客户端协议与资源参考

`output/` 提供已提取的协议定义和客户端 Lua，供接口接入、活动开发及版本维护使用。
游戏业务主要在 Lua 中，原生部分为 Unity IL2CPP；查业务行为优先看 Lua 和配置表。

## 资料索引

| 要查什么 | 位置 |
|---|---|
| 德州发牌、行动和结算字段 | [CSHoldem.proto](output/proto/Proto/CSHoldem.proto) |
| 登录、房间及公共消息 | [CSGame.proto](output/proto/Proto/CSGame.proto)、[CSGameDef.proto](output/proto/Proto/CSGameDef.proto) |
| 道具、角色、小游戏等协议 | [proto/Proto/](output/proto/Proto/) |
| 收包后如何更新牌桌状态 | [net_pk.lua](output/lua/src/net/net_pk.lua)、[net_table.lua](output/lua/src/net/net_table.lua) |
| HTTP 接口、请求参数、领奖顺序 | [app/model/](output/lua/src/app/model/)；结合调用它的界面判断触发条件 |
| 牌桌按钮及行动条件 | [app/table/PK/](output/lua/src/app/table/PK/) |
| 行动枚举 | [EnumConfig.lua](output/lua/src/app/EnumConfig.lua) 的 `POKER_ACTION` |
| 网络封包、HTTP 签名和请求头 | [Net.lua](output/lua/src/manager/Net.lua) |
| 服务入口、渠道等客户端常量 | [Constants.lua](output/lua/src/app/Constants.lua) |
| 活动期、任务、奖励、商城和场次配置 | [tpl/](output/lua/src/tpl/)；运行时通过 [tables.py](tables.py) 读取 |
| 原生类型、字符串和资源解密线索 | [reference/](reference/) 中的 `dump.cs`、`stringliteral.json` |

以上链接指向安装包基线；分析当前活动或新版本行为时，还需检查 `remote_res/` 的同名覆盖文件和删除记录。

## 接口接入的关键约定

- **WSS 有独立帧头**：消息不是裸 protobuf。帧结构为
  `4B 长度 + 2B 类型名长度 + 类型名 + 4B 房间号 + protobuf 正文`；整数为大端，长度不含最前面的 4 字节。
  使用现有 [framing.py](../pf_intercept/wire/framing.py) 和 [codec.py](../pf_intercept/wire/codec.py)。
  连接地址以登录响应为准，不固定域名或端口。
- **协议为 proto2，包名为 `pb`**：解码后的字典可能省略未设置的字段。默认值、字段是否出现和业务成功条件
  要结合 proto 定义与 Lua 处理逻辑判断，不能仅凭字段缺失认定失败。
- **客户端行动枚举不等于引擎的四种动作**：盲注、前注、系统弃牌、下注和加注有不同编号。
  映射集中在 [action_types.py](../pf_intercept/wire/action_types.py)，更新时与 `POKER_ACTION` 对照。
- **HTTP 签名与鉴权分开处理**：签名使用 `random`、`ts` 和客户端 salt，鉴权使用当前会话凭证。
  复用 [game_api/http.py](../pf_intercept/game_api/http.py)，各接口的参数、状态码和领取副作用以对应 Model 为准。
- **登录依赖客户端风控 token**：由 [YiDunHelper.lua](output/lua/src/sdk/YiDunHelper.lua) 调用原生 SDK 获取。
  现有 headless 通过真实客户端采集登录会话，入口见[登录凭证](../pf_intercept/headless/README.md#登录凭证)。

## 资源分层

| 位置 | 用途 | Git |
|---|---|---|
| `output/` | 安装包解出的 Lua / proto 基线 | 跟踪 |
| `remote_res/` | CDN 热更新中与基线不同的文件；删除项在 `manifest.json.removed` | 忽略 |
| `reference/` | 原生类型和字符串参考，辅助维护提取器 | 跟踪 |

[tables.py](tables.py) 按“热更新覆盖基线、删除项不回退”的规则读表，文件变化后自动重读。
业务代码使用 `TABLES`，避免直接打开 `output/` 而漏掉热更新。测试固定使用安装包基线。

[hotupdate.py](hotupdate.py) 负责 CDN 同步；[活动雷达](../pf_intercept/headless/lobby/README.md#活动雷达)
在启动及之后每 6 小时调用它。APK 版本与热更新版本独立，热更新缓存不能代替完整安装包基线。

## 版本维护

日常热更新由雷达处理；需要手动同步时，在项目根目录运行：

```bash
.venv/bin/python -m pf_reverse.hotupdate
```

更换安装包基线时，提取新 APK，再重建它对应的热更新层：

```bash
.venv/bin/python pf_reverse/extract_resources.py /path/to/PokerFate.apk
.venv/bin/python -m pf_reverse.hotupdate --rebuild
```

`output/` 只接收 APK 基线，不把设备缓存合并进去。提取器按本次提供的顶层分组整组替换，更新后检查资源差异。

| 变化 | 需要核对的实现 |
|---|---|
| proto 字段或消息变化 | 对应消息处理器；更新协议基线后生成 Python 绑定 |
| `POKER_ACTION` 变化 | `pf_intercept/wire/action_types.py` |
| `Net.lua` 封包、签名或请求头变化 | `pf_intercept/wire/`、`pf_intercept/game_api/http.py` |
| 活动 Model、任务或奖励表变化 | 对应 `lobby/` 模块的参数、状态判断和到账核对 |

更新协议基线后生成绑定：

```bash
bash pf_intercept/tools/gen_pb2.sh
```

该脚本只读 `output/proto/Proto/`。热更新单独修改 proto 时，需要先核对差异及处理器兼容性，
不能假定同步资源就会自动更新 Python 绑定。更新后运行受影响模块的测试。

## 提取器维护要点

解密实现及常量集中在 [extract_resources.py](extract_resources.py)：

| 层次 | 已确认的格式 |
|---|---|
| bundle 外层 | `XENC`：4 字节标识 + 16 字节 nonce，正文按 64 字节分块异或；解密后为标准 `UnityFS`。客户端类虽叫 `AesCryptoUtil`，这里不是 AES |
| bundle 内部 | MonoBehaviour 的 `encode=1` 表示 `data` 需要 XXTEA 解密；proto 与 Lua 使用不同密钥 |
| XXTEA 长度 | includeLength 变体，解密后的最后一个 uint32 保存原文长度 |
| 路径映射 | `Assets/GameRes/Proto/` → `proto/Proto/`；`Assets/GameRes/src/` → `lua/src/` |

密钥与外层 secret 以脚本中的 `PROTO_KEY`、`LUA_KEY`、`XENC_SECRET` 为准。
旧版无外层加密的 `UnityFS` bundle 也可直接读取。

提取失败时，先判断故障在哪一层：bundle 头或解密后不是 `UnityFS`，检查 XENC；
bundle 可读但文本无效，检查 XXTEA、密钥和路径映射；仅个别资源缺失，检查 APK 内容与热更新覆盖／删除记录。
原生格式变化时，重点查 `AesCryptoUtil`、`EncryptedBundleProvider`、`Security.XXTEA` 和 `Utils.XxteaDecrypt`。
原生引用地址及 metadata 偏移随版本变化，不能复用旧版本的数值。
