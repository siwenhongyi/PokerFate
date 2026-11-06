# PokerFate 逆向工程总结

## 目标

从 PokerFate 游戏客户端提取协议定义（proto）和业务逻辑（Lua），
为后续编写接入脚本（自动操控游戏）提供基础。

---

## 游戏架构概览

| 项目 | 内容 |
|------|------|
| 客户端引擎 | Unity 2022.3.62f3，IL2CPP 编译（非 Mono），metadata v31 |
| 脚本框架 | XLua（游戏逻辑全部用 Lua 编写，C# 只是壳）|
| 网络通信 | WebSocket Secure（WSS），端口 9012 |
| 消息编码 | Protocol Buffers（protobuf2）|
| 资产加密 | 两层：bundle 整包 XENC 异或流（2026-11 起）+ 包内 MonoBehaviour XXTEA |
| 风控 | 网易易盾 `NTESRiskSecProtect` + `DeviceFingerprint`，登录参数带 `yidun_risk_check` |

当前产物对应的客户端：2026-11-05 下载的 `PokerFate_Android.apk`（66 个源码 bundle，
8 proto + 683 lua）。

---

## 逆向过程

### 第一步：抓包确认协议

- 工具：mitmproxy + Proxifier（强制 TCP 代理）
- 发现游戏走 WSS 连接到非标准端口 9012
- 消息体为二进制，确认是 protobuf 编码

### 第二步：获取 APK

从游戏安卓端拉取 APK，用 `unzip` 解包：

```bash
unzip pokerfate.apk -d pokerfate_extracted/
```

### 第三步：确认客户端类型

检查 `assets/bin/Data/Managed/` 目录：

- 无 `.dll` 文件 → **IL2CPP 模式**（非 Mono）
- 存在 `libil2cpp.so` → 确认
- 存在 `libxlua.so` → 游戏使用 XLua 框架

### 第四步：定位 proto 资产

检查 Unity Addressables 目录：

```
assets/aa/Android/gameres_assets_proto_xxx.bundle
```

发现游戏把 `.proto` 文件打包进了 Unity Asset Bundle。

用 UnityPy 读取 bundle：

```python
import UnityPy
env = UnityPy.load("gameres_assets_proto_xxx.bundle")
for path, obj in env.container.items():
    tree = obj.read().object_reader.read_typetree()
    # tree['encode'] = 1  → 加密
    # tree['data'] = [...]  → 密文字节
```

字段 `encode=1` 说明内容被加密，`data` 为密文字节数组。

### 第五步：确认加密算法（Il2CppDumper）

因为是 IL2CPP，无法直接反编译 C# 代码。使用 Il2CppDumper 提取类结构：

```bash
# Il2CppDumper 6.7.46 是 net6 构建，用 DOTNET_ROLL_FORWARD 跑在新版 .NET 上；
# 想要 stringliteral.json / script.json，config.json 里 GenerateStruct 需为 true
DOTNET_ROLL_FORWARD=Major dotnet Il2CppDumper.dll \
  lib/arm64-v8a/libil2cpp.so \
  assets/bin/Data/Managed/Metadata/global-metadata.dat \
  il2cpp_dump/
```

在生成的 `dump.cs` 中搜索加密相关类，发现：

```csharp
// Namespace: Security
public sealed class XXTEA  // XXTEA 加密类
{
    public static byte[] Decrypt(byte[] data, byte[] key) { }
    ...
}

// Namespace: (global)
public class Utils
{
    private static string _xxteaKey;  // 运行时密钥
    public static byte[] XxteaDecrypt(byte[] data) { }  // 使用 _xxteaKey 解密
}
```

**确认算法：XXTEA**

### 第六步：暴力匹配密钥

Il2CppDumper 同时生成了 `stringliteral.json`，包含程序中所有字符串常量（18638 条）。

枚举所有长度在 4~32 之间的字符串，用 XXTEA 解密 proto bundle 的第一个文件，
检查解密结果是否包含 `syntax`、`message`、`proto3` 等关键词：

```python
for item in string_literals:
    plain = xxtea_decrypt(cipher, item['value'].encode())
    if b'syntax' in plain[:80]:
        print("FOUND:", item['value'])
```

**结果：密钥为 `bee#happy&pkproto`**

解密验证：

```
syntax = "proto2";
package pb;
import "CSGameDef.proto";
message UserLoginREQ { ... }
```

### 第七步：批量解密所有资产

**proto 和 lua 用的是不同密钥**（都在 stringliteral.json 里）：

```python
PROTO_KEY = b'bee#happy&pkproto'    # Assets/GameRes/Proto/*.proto
LUA_KEY   = b'bee#happy&pkproject'  # Assets/GameRes/src/**/*.lua
```

XXTEA 为 Ma Bingyao 变体：解密后最后一个 uint32 存原始长度（includeLength），
按它截断去掉尾部填充。

### 第八步：bundle 整包加密 XENC（2026-11 版本起）

新版 APK 里所有 bundle 不再以 `UnityFS` 开头，而是 `XENC`，UnityPy 直接读出 0 个对象。
对比新旧 `dump.cs` 的类型列表，新增：

```csharp
public static class AesCryptoUtil {            // 名字叫 Aes，实际是自定义异或流
    public const string FILE_MAGIC = "XENC";
    public const int HEADER_SIZE = 20;
    private const int KEY_BLOCK = 64;
    private const ulong BLOCK_CONST = 11400714819323198485;   // 0x9E3779B97F4A7C15
    private static readonly byte[] _secret;
    public static AesCryptoUtil.XorStream CreateDecryptStream(Stream s) { }
}
public class EncryptedBundleProvider : ResourceProviderBase { }  // Addressables 自定义 provider
```

反汇编 `libil2cpp.so`（`objdump -d --start-address=<RVA>`）还原出的算法：

1. 头：`"XENC"(4) + nonce(16)`，正文从偏移 20 开始。
2. `secret_seed = u64le(_secret[0:8] 每字节 ^ 0x3D)`（只用前 8 字节）。
3. `seed = splitmix64(u64le(nonce[0:8]) ^ u64le(nonce[8:16])) ^ secret_seed`。
4. 正文第 p 字节：块号 `p >> 6`，块密钥由
   `x = 块号 * 0x9E3779B97F4A7C15 + seed`，循环 64 次
   `x ^= x<<13; x ^= x>>7; 取 x 低 8 位; x ^= x<<17` 生成，明文 = 密文 ^ 块密钥[p & 63]。

`_secret` 在 `.cctor` 里用 `RuntimeHelpers.InitializeArray` 初始化。定位方式：
`.cctor` 中 `adrp/ldr` 取的 GOT 槽 → `objdump -R` 查 `R_AARCH64_RELATIVE` 目标 →
`script.json` 的 `ScriptMetadata` 得到
`Field$<PrivateImplementationDetails>.57551730F4ED...63A6` → `dump.cs` 里该字段标注
`Metadata offset 0x69AE20` → 从 `global-metadata.dat` 该偏移读 16 字节：

```
XENC_SECRET = 2e498d51247d0392f13e6928533a2b7c
```

解出来是标准 `UnityFS`（Unity 2022.3.62f3），之后的流程与以前相同。
客户端升级后若提取脚本报「没有解出任何 proto/lua」，先看 bundle 头是否变了，
再按上面的路径重新定位 `_secret`（RVA 和 metadata offset 每个版本都会变）。

---

## 一键提取脚本

`pf_reverse/extract_resources.py`：读 bundle → 去 XENC 外层 → UnityPy 解析 →
按路径选密钥 XXTEA 解密 → 写 `output/{proto,lua}`。单向更新：对本次提供的顶层分组整组替换。

来源可以直接给 `.apk` 文件（脚本从压缩包里只读 proto/src bundle，不用解压 1.6GB），
也可以给 bundle 目录：

```bash
# 先 APK（基线），再 remote_res 拉取目录（热更，覆盖）
.venv/bin/python pf_reverse/extract_resources.py ~/Downloads/PokerFate_Android.apk [<remote_res_dir>]
```

### 两个来源（关键！）

游戏走 Unity Addressables，lua/proto 分散在两处，必须都覆盖才完整：

| 来源 | 内容 | 更新频率 |
|------|------|----------|
| **APK 内置** `assets/aa/Android/gameres_assets_src*` | 全量基线，**含 `app/scenes`**（remote_res 从不下发） | 随 APK 版本（少） |
| **设备 remote_res** `/sdcard/Android/data/com.pokerfate.play/files/remote_res/` | 热更内容，覆盖 APK 同名资源 | 频繁（每次开服可能变）|

remote_res 里 lua 又分两块，**别只拉文件夹漏了根 bundle**：
- `gameres_assets_src/` 文件夹 → `app/appload/net/sdk/tpl`
- `gameres_assets_src_<hash>.bundle` 根文件 → `engine/manager/ui/perf/main.lua/protoc.lua`

判断是否有更新：对比 `remote_res/catalog_1.0.0.hash` 与上次。

---

## 输出文件

```
pf_reverse/output/
  proto/           ← 8 个解密后的 protobuf 定义文件
    Proto/
      CSGame.proto       游戏主协议（登录、桌子、玩家）
      CSHoldem.proto     德州扑克协议（手牌、行动、结算）
      CSGameDef.proto    公共枚举定义
      CSRole.proto       角色信息
      CSProps.proto      道具协议
      CSValue.proto      数值定义
      CSSideGame.proto   副游戏协议
      CSLobJackpot.proto 大厅 Jackpot 协议
  lua/             ← 全部解密后的 Lua 源码
    src/
      net/
        net_pk.lua       德州扑克网络层（收发消息处理）
        net_table.lua    牌桌网络层
        net_game.lua     游戏通用网络层
        net_role.lua     角色网络层
        ...
      app/
        table/PK/        德州牌桌 UI 和逻辑
        server/          服务器通信封装
        model/           各模块数据模型
      protoc.lua         Protobuf 编解码器（Lua 实现）
      manager/Net.lua    网络管理器
      ...
```

---

## 关键信息汇总

| 项目 | 值 |
|------|----|
| bundle 外层 | XENC 异或流，secret `2e498d51247d0392f13e6928533a2b7c` |
| 包内加密 | XXTEA，proto 密钥 `bee#happy&pkproto`，lua 密钥 `bee#happy&pkproject` |
| 网络协议 | WSS，端口 9012 |
| 消息格式 | Protobuf2（package `pb`）|
| Lua 框架 | XLua，游戏逻辑全在 Lua |
| 关键 proto | `CSHoldem.proto`（德州主协议）|
| 关键 Lua | `net_pk.lua`、`protoc.lua` |

---

## 工具链

| 工具 | 用途 |
|------|------|
| `UnityPy` | 读取 Unity Asset Bundle |
| `Il2CppDumper` 6.7.46 | 提取 IL2CPP C# 类结构 + 字符串表（本地放在 `pf_reverse/poker_chase/tools/`，不入库）|
| `objdump`（Xcode 自带 llvm） | ARM64 反汇编、`-R` 查动态重定位 |
| `jadx` | 反编译 Java 层（classes.dex，目前没用上）|
| Python XENC / XXTEA | 自实现解密，见 `extract_resources.py` |

---

## 新版本更新流程

1. `extract_resources.py <新 apk> [<remote_res 目录>]` 重建 `output/`，`git diff` 看 proto/lua 变化。
2. `bash pf_intercept/tools/gen_pb2.sh` 重新生成 `pf_intercept/wire/pb/*_pb2.py`。
3. 用新 APK 的 `libil2cpp.so` + `global-metadata.dat` 跑 Il2CppDumper，
   把 `dump.cs`、`stringliteral.json` 覆盖到 `reference/`（只保留这两个，`il2cpp.h`/`script.json` 太大不入库）。
4. 重点检查 `app/EnumConfig.lua` 的 `POKER_ACTION`（`wire/action_types.py` 依赖）
   和 `manager/Net.lua` 的签名逻辑（`game_api/gamedata.py` 依赖）有没有变。
5. 解包、dump 都放临时目录，用完删掉，不要把 APK 或中间产物留在项目里。
