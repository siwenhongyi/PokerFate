# PokerFate 逆向工程总结

## 目标

从 PokerFate 游戏客户端提取协议定义（proto）和业务逻辑（Lua），
为后续编写接入脚本（自动操控游戏）提供基础。

---

## 游戏架构概览

| 项目 | 内容 |
|------|------|
| 客户端引擎 | Unity，IL2CPP 编译（非 Mono）|
| 脚本框架 | XLua（游戏逻辑全部用 Lua 编写，C# 只是壳）|
| 网络通信 | WebSocket Secure（WSS），端口 9012 |
| 消息编码 | Protocol Buffers（protobuf2）|
| 资产加密 | XXTEA |

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
# 修改 runtimeconfig.json 兼容 .NET 10
dotnet Il2CppDumper.dll \
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

用同一密钥解密所有 proto 文件和 Lua 源码：

```python
KEY = b'bee#happy&pkproto'
plain = xxtea_decrypt(cipher, KEY)
```

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
| 加密算法 | XXTEA |
| 加密密钥 | `bee#happy&pkproto` |
| 网络协议 | WSS，端口 9012 |
| 消息格式 | Protobuf2（package `pb`）|
| Lua 框架 | XLua，游戏逻辑全在 Lua |
| 关键 proto | `CSHoldem.proto`（德州主协议）|
| 关键 Lua | `net_pk.lua`、`protoc.lua` |

---

## 工具链

| 工具 | 用途 |
|------|------|
| `unzip` | 解包 APK |
| `UnityPy` | 读取 Unity Asset Bundle |
| `jadx` | 反编译 Java 层（classes.dex）|
| `Il2CppDumper` | 提取 IL2CPP C# 类结构 + 字符串表 |
| `objdump` | ARM64 反汇编辅助分析 |
| Python XXTEA | 自实现解密 |

---

## 下一步

1. 用 `CSHoldem.proto` + `CSGame.proto` 编译出 Python protobuf 类
2. 分析 `net_pk.lua` 了解消息 ID 和收发逻辑
3. 分析 `manager/Net.lua` 了解 WebSocket 连接建立和鉴权流程
4. 编写 Python WSS 客户端，接入游戏服务器
