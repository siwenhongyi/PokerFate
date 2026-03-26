# PokerFate Bot

德州扑克 AI Bot，通过 WSS 中间人代理拦截并注入游戏操作。

---

## 环境要求

- **代理运行机**：macOS，Python 3.12+
- **游戏客户端**：Windows PC 或 Android 手机
- Android 模式下，手机与 Mac 需在同一局域网

---

## 项目结构

```
pokerfate/       策略引擎（GTO + 可剥削决策）
pf_intercept/    WSS MITM 代理 — 拦截游戏流量，驱动 Bot
pf_reverse/      逆向工程产物（Lua 源码、proto 文件）
```

---

## 初始化（首次运行）

```bash
# 1. 创建虚拟环境并安装依赖
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 2. 编译 protobuf
bash pf_intercept/gen_pb2.sh

# 3. 生成 TLS 证书
python -m pf_intercept.gen_cert
```

---

## Windows 接入

**1. 安装 CA 证书**

双击 `pf_intercept/certs/ca.crt` → 安装证书 → 本地计算机 → 受信任的根证书颁发机构

**2. 修改 hosts 文件**

用管理员权限打开 `C:\Windows\System32\drivers\etc\hosts`，添加：

```
127.0.0.1  zga-entry.poker-fate.net
127.0.0.1  zga-entry.allinmoe.com
127.0.0.1  ga-foreign.poker-fate.com
```

**3. 启动代理，打开游戏**

```bash
python -m pf_intercept.proxy
```

Bot 自动接管，座位号和盲注从游戏消息中自动识别。

---

## Android 接入

用 DNS 劫持替代 hosts 文件，无需 root。

**1. 修改 APK（首次，电脑上操作）**

原始 APK 默认不信任用户级证书，需要用 `apk-mitm` 打包一个信任版本：

```bash
# 安装 apk-mitm（需要 Node.js）
npm install -g apk-mitm

# 修改 APK
apk-mitm 原始.apk
# 生成 原始-patched.apk，安装到手机
```

**2. 安装 CA 证书到手机**

将 `pf_intercept/certs/ca.crt` 传到手机：

> 设置 → 安全 → 加密与凭据 → 安装证书 → CA 证书 → 选择 `ca.crt`

（不同机型路径略有差异）

**3. 启动 DNS 劫持服务器**

```bash
sudo .venv/bin/python -m pf_intercept.dns_server
```

本机 IP 自动探测，启动后输出如下：

```
DNS server  0.0.0.0:53  proxy_ip=192.168.1.100
upstream DNS: 192.168.1.1 → 223.5.5.5 → ...
  hijack: zga-entry.poker-fate.net → 192.168.1.100
  hijack: zga-entry.allinmoe.com → 192.168.1.100
  hijack: ga-foreign.poker-fate.com → 192.168.1.100
```

**4. 手机 Wi-Fi 设置 DNS**

将手机当前 Wi-Fi 的 DNS 改为上面输出的 `proxy_ip`。

> Wi-Fi 长按 → 修改网络 → 高级选项 → DNS

**5. 启动代理，打开游戏**

另开一个终端：

```bash
.venv/bin/python -m pf_intercept.proxy
```

打开手机游戏，Bot 自动接管。

**常见问题**

| 问题 | 解决 |
|------|------|
| `:53 Address already in use` | `sudo lsof -i UDP:53` 查占用；mDNSResponder 可在系统设置 → 共享里临时关掉 |
| 手机改完 DNS 上不了网 | DNS 填的 IP 有误，重新运行 dns_server 确认 `proxy_ip` |
| TLS 握手失败 | 确认 `ca.crt` 装在用户证书区（非系统区），且使用的是逆向后的 APK |

---

## 架构

```
Windows:
  游戏 → hosts 重定向(127.0.0.1) → proxy:9012 → 真实服务器

Android:
  游戏 → DNS 劫持(本机 IP) → proxy:9012 → 真实服务器

proxy.py 处理流程：
  TLS SNI 提取域名 → 外部 DNS 解析真实 IP → 建立上行连接
  解码 protobuf 帧 → 驱动策略引擎 → 轮到自己时注入 ActionREQ
```

---

## 牌面编码

```
code = rank + suit × 256
rank : 2~14  对应  2~A
suit : 1=方块  2=梅花  3=红桃  4=黑桃
```
