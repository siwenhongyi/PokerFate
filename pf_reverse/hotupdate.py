"""热更新: the client's lua and proto from the game's CDN, kept apart from the installer's.

    version  GET <BASE>/1.0.1_version.json         -> android_official: url, res (e.g. 1.7.7)
    list     GET <BASE>/<url>/<res>/0filelist.txt  -> "<bundle path>,<size>" per line
    bundle   GET <BASE>/<url>/<res>/<bundle path>  -> the bundle, XENC-encrypted

Two layers, as on the phone:

    output/       the installer's files (extract_resources.py <apk>), in the repository;
                  changed only by hand, when a new APK comes
    remote_res/   the hot update over them, git-ignored: exactly the files whose text differs
                  from the installer's, and in ``manifest.json`` the files the hot update removed

So running the bot never changes the repository, and ``remote_res/`` itself is the list of
what the hot update changed. ``pf_reverse.tables`` reads the two as the client does.

Only the source bundles are read: ``gameres_assets_src*`` (lua) and ``gameres_assets_proto*``
(proto), about 11 MB in 76 bundles at 1.7.7. The list is the whole remote catalogue; a bundle's
path ends in its content hash, so a path the manifest does not have is new content and only
those are downloaded. A file is gone when its top-level group (lua/src/app, proto/Proto ...)
is in the catalogue and no bundle brings it, the rule extract_resources.py replaces groups by.

Network: the CDN only, read-only, the same files every client downloads at start. Nothing of
the account goes out. Downloads stay in memory; only the extracted text is kept.

    python -m pf_reverse.hotupdate             # sync, print what changed as JSON
    python -m pf_reverse.hotupdate --rebuild   # after a new APK in output/: start remote_res afresh
"""
from __future__ import annotations

import argparse
import contextlib
import json
import shutil
import re
import ssl
import sys
import urllib.request
from dataclasses import asdict, dataclass, field
from pathlib import Path

import certifi

BASE = "https://aws.poker-fate.com/res"
VERSION_FILE = "1.0.1_version.json"     # the client path since APK 1.7.0 (sub-packages)
PLATFORM = "android_official"
SOURCES = ("gameres_assets_src", "gameres_assets_proto")
HERE = Path(__file__).resolve().parent
INSTALLER = HERE / "output"
REMOTE = HERE / "remote_res"
MANIFEST = "manifest.json"
LAYERS = ("lua", "proto")               # the output directories that hold client files
XENC_HEADER = 20                        # a downloaded bundle is the listed size, or 20 bytes more
_SSL = ssl.create_default_context(cafile=certifi.where())
_HEADERS = {"User-Agent": "Mozilla/5.0"}
_HASHED = re.compile(r"_[0-9a-f]{32}\.bundle$")


def fetch(url: str, timeout: float = 60) -> bytes:
    with urllib.request.urlopen(urllib.request.Request(url, headers=_HEADERS), timeout=timeout, context=_SSL) as resp:
        return resp.read()


def bundle_key(path: str) -> str:
    """A bundle path without its content hash: the same key across versions."""
    return _HASHED.sub("", path)


def source_bundles(text: str) -> dict:
    """{bundle path: listed size} of the lua / proto bundles in a 0filelist.txt."""
    found = {}
    for line in text.splitlines():
        if "," not in line:
            continue
        path, size = line.strip().rsplit(",", 1)
        if path.endswith(".bundle") and path.startswith(SOURCES):
            found[path] = int(size)
    return found


def group_of(sub: str) -> str:
    """The top-level group of an output path (extract_resources._group_of): proto/Proto,
    lua/src/<dir>, or a file directly under lua/src."""
    parts = sub.split("/")
    if sub.startswith("proto/"):
        return "/".join(parts[:2])
    if sub.startswith("lua/src/"):
        return sub if len(parts) <= 3 else "/".join(parts[:3])
    return "/".join(parts[:-1])


def decode(raw: bytes) -> dict:
    """{output path: bytes} of one bundle (extract_resources does the decryption)."""
    from pf_reverse.extract_resources import bundle_contents
    with contextlib.redirect_stdout(sys.stderr):
        contents, _ = bundle_contents(raw)
    return contents


def files_under(root: Path) -> set:
    """Output paths of the client files under ``root``."""
    return {p.relative_to(root).as_posix() for layer in LAYERS if (root / layer).is_dir()
            for p in (root / layer).rglob("*") if p.is_file() and not p.name.endswith(".part")}


@dataclass
class Update:
    res_from: str
    res_to: str
    changed: list = field(default_factory=list)     # files whose text, as the client runs, changed
    added: list = field(default_factory=list)       # of those, files the client did not have
    removed: list = field(default_factory=list)     # files the client no longer has
    downloaded: int = 0
    differ: int = 0                                 # files of remote_res: where the hot update differs

    @property
    def proto_changed(self) -> bool:
        return any(path.startswith("proto/") for path in self.changed + self.removed)

    def summary(self) -> dict:
        return {**asdict(self), "proto_changed": self.proto_changed}


def load_manifest(root: Path) -> dict:
    try:
        data = json.loads((root / MANIFEST).read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".part")
    tmp.write_bytes(data)
    tmp.replace(path)


class Client:
    """The installer's files and the hot update over them, as one client."""

    def __init__(self, installer: Path, remote: Path, removed=()):
        self.installer, self.remote, self.removed = installer, remote, set(removed)

    def read(self, sub):
        for root in (self.remote, self.installer):
            path = root / sub
            if path.is_file():
                return None if root == self.installer and sub in self.removed else path.read_bytes()
        return None

    def put(self, sub, data):
        """The client's file ``sub`` is now ``data`` (None: gone)."""
        own = self.installer / sub
        mine = self.remote / sub
        base = own.read_bytes() if own.is_file() else None
        if data is not None and data == base:
            if mine.is_file():
                mine.unlink()
            self.removed.discard(sub)
        elif data is not None:
            if not mine.is_file() or mine.read_bytes() != data:
                _write(mine, data)
            self.removed.discard(sub)
        else:
            if mine.is_file():
                mine.unlink()
            if base is not None:
                self.removed.add(sub)


def sync(*, get=fetch, installer: Path = INSTALLER, remote: Path = REMOTE, decoder=decode) -> Update:
    """Bring ``remote`` to the CDN's current resource version over ``installer``; what changed."""
    installer, remote = Path(installer), Path(remote)
    version = json.loads(get(f"{BASE}/{VERSION_FILE}", 20))[PLATFORM]
    url, res = str(version["url"]), str(version["res"])
    manifest = load_manifest(remote)
    old = manifest.get("bundles") if isinstance(manifest.get("bundles"), dict) else {}
    client = Client(installer, remote, manifest.get("removed") or ())
    update = Update(res_from=str(manifest.get("res", "")), res_to=res)
    if manifest.get("res") == res and manifest.get("url") == url and old:
        update.differ = len(files_under(remote))
        return update
    listed = source_bundles(get(f"{BASE}/{url}/{res}/0filelist.txt", 60).decode("utf-8"))
    if not listed:
        raise IOError("the file list has no lua / proto bundles")
    bundles = {path: list(old[path]) for path in listed if path in old}
    fresh = {}
    for path, size in sorted(listed.items()):
        if path in bundles:
            continue
        raw = get(f"{BASE}/{url}/{res}/{path}", 300)
        if len(raw) not in (size, size + XENC_HEADER):
            raise IOError(f"{path}: got {len(raw)} bytes, the list says {size}")
        update.downloaded += 1
        contents = decoder(raw)
        if not contents:
            raise IOError(f"{path}: no lua / proto in it (the encryption may have changed)")
        fresh.update(contents)
        bundles[path] = sorted(contents)
    catalogue = {sub for files in bundles.values() for sub in files}
    groups = {group_of(sub) for sub in catalogue}
    gone = {sub for sub in files_under(installer) | files_under(remote) | client.removed
            if group_of(sub) in groups and sub not in catalogue}
    for sub in sorted(set(fresh) | gone):
        before = client.read(sub)
        client.put(sub, fresh.get(sub))
        after = client.read(sub)
        if before == after:
            continue
        if after is None:
            update.removed.append(sub)
        else:
            update.changed.append(sub)
            if before is None:
                update.added.append(sub)
    update.differ = len(files_under(remote))
    _write(remote / MANIFEST, json.dumps({"res": res, "url": url, "bundles": bundles,
                                          "removed": sorted(client.removed)},
                                         ensure_ascii=False, indent=1, sort_keys=True).encode("utf-8"))
    return update


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="热更新：CDN 上的 lua / proto 同步到 pf_reverse/remote_res")
    ap.add_argument("--rebuild", action="store_true", help="清空 remote_res 后全量同步（换了新安装包之后用）")
    args = ap.parse_args(argv)
    if args.rebuild and REMOTE.exists():
        shutil.rmtree(REMOTE)
    update = sync()
    print(json.dumps(update.summary(), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
