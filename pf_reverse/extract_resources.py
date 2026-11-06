"""从 APK / 设备 remote_res 的 Unity Addressables bundle 中提取并解密 proto / lua 源码。

游戏资源是单向更新的：对本次实际提供的「顶层分组」做整组替换（先清空该组
再重建），未提供的分组保留不动。

  - proto：8 个文件，APK 和 remote_res 都有，整体替换。
  - lua：remote_res 只含 app/appload/net/sdk/tpl 等业务分组；
          engine/manager/ui/perf/main.lua/protoc.lua 是 APK 内置框架，
          remote_res 不下发，故只在传入 APK 时才会被替换。

解密分两层（见 REVERSE_NOTES.md）：
  1. bundle 整包加密（2026-11 版本起）：文件以 "XENC" 开头，
     头 20 字节 = magic(4) + nonce(16)，正文按 64 字节分块异或密钥流。
     种子 = splitmix64(nonce[0:8] ^ nonce[8:16]) ^ secret_seed；
     块密钥 = xorshift64(块号 * 0x9E3779B97F4A7C15 + 种子) 逐字节取低 8 位。
     对应客户端 C# 类 AesCryptoUtil / EncryptedBundleProvider。
     未加密的旧 bundle（直接以 "UnityFS" 开头）原样读取。
  2. bundle 内 MonoBehaviour：encode=1, data=密文 -> XXTEA 解密 -> 文本。
     XXTEA 为 Ma Bingyao 变体，最后一个 uint32 存原始长度（includeLength）。
     密钥分两套（17 字节，标准 XXTEA 只用前 16 字节）：
       proto -> bee#happy&pkproto
       lua   -> bee#happy&pkproject

用法：
  python pf_reverse/extract_resources.py <src1> [<src2> ...] [--out pf_reverse/output]

每个 src 可以是：
  - .apk 文件：直接从压缩包内读 assets/aa/Android/ 下的 bundle，无需解压
  - 目录：递归查找 *.bundle（例如设备 remote_res 拉取目录）

按顺序传入，靠后的覆盖靠前的（同一逻辑路径以最后出现为准）。
典型用法是先 APK（基线，含 app/scenes 等 remote_res 不下发的内容）
再 remote_res 拉取目录（热更，最新）：

  python pf_reverse/extract_resources.py ~/Downloads/PokerFate_Android.apk [<remote_res_dir>]
"""
import argparse
import glob
import os
import shutil
import struct
import sys
import zipfile

import numpy as np
import UnityPy

PROTO_KEY = b"bee#happy&pkproto"
LUA_KEY = b"bee#happy&pkproject"
DELTA = 0x9E3779B9

# AesCryptoUtil._secret：global-metadata.dat 中
# <PrivateImplementationDetails>.57551730F4ED...63A6 的 16 字节初始化数据
# （Il2CppDumper dump.cs 标注 Metadata offset 0x69AE20）。只用前 8 字节。
XENC_MAGIC = b"XENC"
XENC_HEADER_SIZE = 20
XENC_SECRET = bytes.fromhex("2e498d51247d0392f13e6928533a2b7c")

# APK 内需要的 bundle（proto + lua 源码），其余美术资源 bundle 不读
APK_BUNDLE_PREFIXES = (
    "assets/aa/Android/gameres_assets_proto",
    "assets/aa/Android/gameres_assets_src",
)

# Unity container 路径 -> (output 子目录, 解密密钥)
PATH_MAP = (
    ("Assets/GameRes/Proto/", "proto/Proto/", PROTO_KEY),
    ("Assets/GameRes/src/", "lua/src/", LUA_KEY),
)

_U64 = np.uint64


def _splitmix64(z):
    m = (1 << 64) - 1
    z ^= z >> 30
    z = (z * 0xBF58476D1CE4E5B9) & m
    z ^= z >> 27
    z = (z * 0x94D049BB133111EB) & m
    return z ^ (z >> 31)


def xenc_decrypt(data, secret=XENC_SECRET):
    """解 bundle 外层 XENC 加密；非 XENC 数据原样返回。"""
    if data[:4] != XENC_MAGIC:
        return data
    nonce = data[4:XENC_HEADER_SIZE]
    n = int.from_bytes(nonce[:8], "little") ^ int.from_bytes(nonce[8:16], "little")
    secret_seed = int.from_bytes(bytes(b ^ 0x3D for b in secret[:8]), "little")
    seed = _splitmix64(n) ^ secret_seed

    body = np.frombuffer(data, dtype=np.uint8, offset=XENC_HEADER_SIZE)
    n_blocks = (len(body) + 63) // 64
    with np.errstate(over="ignore"):
        x = np.arange(n_blocks, dtype=_U64) * _U64(0x9E3779B97F4A7C15) + _U64(seed)
        ks = np.empty((n_blocks, 64), dtype=np.uint8)
        for i in range(64):                       # 每块独立的 xorshift64 状态
            x ^= x << _U64(13)
            x ^= x >> _U64(7)
            ks[:, i] = (x & _U64(0xFF)).astype(np.uint8)
            x ^= x << _U64(17)
    return (body ^ ks.reshape(-1)[:len(body)]).tobytes()


def _mx(sum_, y, z, p, e, k):
    return (((z >> 5 ^ (y << 2)) + (y >> 3 ^ (z << 4)))
            ^ ((sum_ ^ y) + (k[(p & 3) ^ e] ^ z))) & 0xFFFFFFFF


def _btea_decrypt(v, k):
    n = len(v)
    if n < 2:
        return v
    q = 6 + 52 // n
    sum_ = (q * DELTA) & 0xFFFFFFFF
    while sum_ != 0:
        e = (sum_ >> 2) & 3
        for p in range(n - 1, 0, -1):
            z = v[p - 1]
            v[p] = (v[p] - _mx(sum_, v[(p + 1) % n], z, p, e, k)) & 0xFFFFFFFF
        z = v[n - 1]
        v[0] = (v[0] - _mx(sum_, v[1], z, 0, e, k)) & 0xFFFFFFFF
        sum_ = (sum_ - DELTA) & 0xFFFFFFFF
    return v


def xxtea_decrypt(data, key=PROTO_KEY):
    if len(data) < 8:
        return b""
    k = list(struct.unpack("<4I", key.ljust(16, b"\x00")[:16]))
    v = list(struct.unpack("<%dI" % (len(data) // 4), data))
    _btea_decrypt(v, k)
    out = struct.pack("<%dI" % len(v), *v)
    length = struct.unpack("<I", out[-4:])[0]          # includeLength: 末尾存原始长度
    if 0 < length <= len(out) - 4:
        return out[:length]
    return out.rstrip(b"\x00")                          # 兜底：去尾部填充


def map_out_path(container_path):
    for prefix, sub, key in PATH_MAP:
        if container_path.startswith(prefix):
            return sub + container_path[len(prefix):], key
    return None, None


def _group_of(sub):
    """取相对 output 的「顶层分组」，用于整组替换。

    proto/Proto/CSGame.proto -> proto/Proto
    lua/src/app/...          -> lua/src/app
    lua/src/main.lua         -> lua/src/main.lua（根文件自成一组）
    """
    parts = sub.split("/")
    if sub.startswith("proto/"):
        return "/".join(parts[:2])               # proto/Proto
    if sub.startswith("lua/src/"):
        if len(parts) <= 3:                      # lua/src/<file>
            return sub
        return "/".join(parts[:3])               # lua/src/<group>
    return os.path.dirname(sub)


def iter_bundles(src):
    """产出 (显示名, bundle 原始字节)。src 为 .apk 文件或 bundle 目录。"""
    if os.path.isfile(src) and zipfile.is_zipfile(src):
        with zipfile.ZipFile(src) as zf:
            names = sorted(n for n in zf.namelist()
                           if n.endswith(".bundle") and n.startswith(APK_BUNDLE_PREFIXES))
            if not names:
                sys.exit("APK 内未找到 proto/src bundle：%s" % src)
            for n in names:
                yield n, zf.read(n)
        return
    bundles = sorted(glob.glob(os.path.join(src, "**", "*.bundle"), recursive=True))
    if not bundles:
        sys.exit("未找到任何 .bundle：%s" % src)
    for b in bundles:
        with open(b, "rb") as f:
            yield b, f.read()


def extract(srcs, out_dir):
    contents = {}                                # sub -> plain（后传入的来源覆盖先前的）
    n_skip = n_xenc = 0
    for src in srcs:
        for name, raw in iter_bundles(src):
            if raw[:4] == XENC_MAGIC:
                n_xenc += 1
            try:
                env = UnityPy.load(xenc_decrypt(raw))
            except Exception as e:
                print("  跳过(加载失败) %s: %s" % (os.path.basename(name), e))
                continue
            for cpath, obj in env.container.items():
                try:
                    obj_type = obj.type.name
                except Exception as e:
                    print("  跳过(对象失效) %s %s: %s" % (os.path.basename(name), cpath, e))
                    n_skip += 1
                    continue
                if obj_type != "MonoBehaviour":
                    continue
                sub, key = map_out_path(cpath)
                if sub is None:
                    n_skip += 1
                    continue
                tree = obj.read_typetree()
                if "data" not in tree:
                    n_skip += 1
                    continue
                data = bytes(tree["data"])
                contents[sub] = xxtea_decrypt(data, key) if tree.get("encode") else data

    if not contents:
        sys.exit("没有解出任何 proto/lua，未改动输出目录（加密方式可能又变了）")

    # 单向更新：整组替换本次实际提供的顶层分组（组内消失的旧文件随之清除）
    groups = {_group_of(sub) for sub in contents}
    for g in sorted(groups):
        p = os.path.join(out_dir, g)
        if os.path.isdir(p):
            shutil.rmtree(p)
        elif os.path.isfile(p):
            os.remove(p)
    print("替换分组：" + ", ".join(sorted(groups)))

    n_proto = n_lua = 0
    for sub, plain in contents.items():
        dst = os.path.join(out_dir, sub)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        with open(dst, "wb") as f:
            f.write(plain)
        if sub.startswith("proto/"):
            n_proto += 1
        else:
            n_lua += 1
    print("proto: %d, lua: %d, XENC bundle: %d, 跳过非源码: %d" % (n_proto, n_lua, n_xenc, n_skip))
    return n_proto, n_lua


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("srcs", nargs="+", help=".apk 文件或 bundle 目录，靠后的覆盖靠前的")
    ap.add_argument("--out", default=os.path.join(os.path.dirname(__file__), "output"),
                    help="输出目录（默认 pf_reverse/output）")
    args = ap.parse_args()
    extract(args.srcs, args.out)


if __name__ == "__main__":
    main()
