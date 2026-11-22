"""pf_reverse.hotupdate: CDN -> remote_res/ over the installer's output/, with a scripted CDN."""
import json

import pytest

from pf_reverse import hotupdate as hu
from pf_reverse import tables as tb


class CDN:
    """Answers the version file, the file list and the bundles; a bundle's bytes are its file name."""

    def __init__(self, res, bundles):
        self.res, self.bundles, self.asked = res, bundles, []

    def __call__(self, url, timeout=60):
        self.asked.append(url.removeprefix(hu.BASE + "/"))
        if url.endswith(hu.VERSION_FILE):
            return json.dumps({hu.PLATFORM: {"url": "Android_official_v2", "res": self.res}}).encode()
        if url.endswith("0filelist.txt"):
            lines = [f"{path},{len(path.rsplit('/', 1)[-1])}" for path in self.bundles] + ["other_assets/x.bundle,9"]
            return "\n".join(lines).encode()
        return url.rsplit("/", 1)[-1].encode()


def decoder(contents):
    return lambda raw: contents[raw.decode()]


A = "gameres_assets_src/tpl_" + "a" * 32 + ".bundle"
B = "gameres_assets_src/tpl_" + "b" * 32 + ".bundle"
PROTO = "gameres_assets_proto_" + "c" * 32 + ".bundle"
TPL = "lua/src/tpl/"


def name(bundle):
    return bundle.rsplit("/", 1)[-1]


@pytest.fixture
def layers(tmp_path):
    installer, remote = tmp_path / "output", tmp_path / "remote_res"
    (installer / TPL).mkdir(parents=True)
    (installer / TPL / "tpl_same.lua").write_bytes(b"same")
    (installer / TPL / "tpl_old.lua").write_bytes(b"old")
    (installer / TPL / "tpl_gone.lua").write_bytes(b"gone")
    (installer / "lua/src/app").mkdir(parents=True)
    (installer / "lua/src/app/Main.lua").write_bytes(b"a group the catalogue does not bring")
    return installer, remote


def sync(layers, cdn, contents):
    installer, remote = layers
    return hu.sync(get=cdn, installer=installer, remote=remote, decoder=decoder(contents))


def test_source_bundles_keys_and_groups():
    assert hu.source_bundles(f"{A},10\n{PROTO},20\nsubpackage1_assets_x/y.bundle,30\nnot a line") == {A: 10, PROTO: 20}
    assert hu.bundle_key(A) == "gameres_assets_src/tpl"
    assert [hu.group_of(p) for p in ("proto/Proto/CSGame.proto", "lua/src/tpl/tpl_x.lua", "lua/src/main.lua")] == [
        "proto/Proto", "lua/src/tpl", "lua/src/main.lua"]


def test_only_what_differs_from_the_installer_lands_in_remote_res(layers):
    installer, remote = layers
    files = {name(A): {TPL + "tpl_same.lua": b"same", TPL + "tpl_old.lua": b"new", TPL + "tpl_x.lua": b"x"},
             name(PROTO): {"proto/Proto/CSGame.proto": b"msg"}}
    update = sync(layers, CDN("1.7.7", [A, PROTO]), files)
    assert (update.res_from, update.res_to, update.downloaded, update.differ) == ("", "1.7.7", 2, 3)
    assert update.changed == ["lua/src/tpl/tpl_old.lua", "lua/src/tpl/tpl_x.lua", "proto/Proto/CSGame.proto"]
    assert update.added == ["lua/src/tpl/tpl_x.lua", "proto/Proto/CSGame.proto"]
    assert update.removed == ["lua/src/tpl/tpl_gone.lua"] and update.proto_changed
    assert sorted(hu.files_under(remote)) == ["lua/src/tpl/tpl_old.lua", "lua/src/tpl/tpl_x.lua", "proto/Proto/CSGame.proto"]
    assert (installer / TPL / "tpl_old.lua").read_bytes() == b"old"          # the installer's files are never written
    manifest = json.loads((remote / hu.MANIFEST).read_text())
    assert manifest["res"] == "1.7.7" and manifest["removed"] == ["lua/src/tpl/tpl_gone.lua"]


def test_the_tables_read_the_hot_update_over_the_installer(layers):
    installer, remote = layers
    for path, rows in ((installer / TPL / "tpl_old.lua", "{1}"), (installer / TPL / "tpl_gone.lua", "{9}")):
        path.write_text(f"local keys = {{'id',}}\nlocal bodys = {{\n{rows}\n}}", encoding="utf-8")
    new = b"local keys = {'id',}\nlocal bodys = {\n{2}\n}"
    sync(layers, CDN("1.7.7", [A]), {name(A): {TPL + "tpl_old.lua": new, TPL + "tpl_same.lua": b"same"}})
    t = tb.Tables(remote / tb.TPL_DIR, installer / tb.TPL_DIR, manifest=remote / tb.MANIFEST)
    assert t.rows("old") == [{"id": 2}] and t.rows("gone") == [] and "gone" not in t.names()
    assert tb.Tables(installer / tb.TPL_DIR).rows("old") == [{"id": 1}]


def test_the_next_version_downloads_new_bundles_only(layers):
    sync(layers, CDN("1.7.7", [A]), {name(A): {TPL + "tpl_old.lua": b"1", TPL + "tpl_same.lua": b"same"}})
    cdn = CDN("1.7.8", [B])
    update = sync(layers, cdn, {name(B): {TPL + "tpl_old.lua": b"old", TPL + "tpl_same.lua": b"same",
                                          TPL + "tpl_gone.lua": b"back"}})
    assert (update.res_from, update.downloaded, update.differ) == ("1.7.7", 1, 1)
    assert update.changed == ["lua/src/tpl/tpl_gone.lua", "lua/src/tpl/tpl_old.lua"]
    assert update.added == ["lua/src/tpl/tpl_gone.lua"]
    assert [a for a in cdn.asked if a.endswith(".bundle")] == [f"Android_official_v2/1.7.8/{B}"]


def test_the_same_version_reads_the_version_file_only(layers):
    files = {name(A): {TPL + "tpl_old.lua": b"1"}}
    sync(layers, CDN("1.7.7", [A]), files)
    cdn = CDN("1.7.7", [A])
    assert sync(layers, cdn, files).changed == [] and cdn.asked == [hu.VERSION_FILE]


def test_a_bundle_of_the_wrong_size_stops_the_sync_before_the_manifest(layers):
    class Short(CDN):
        def __call__(self, url, timeout=60):
            data = super().__call__(url, timeout)
            return data[:-1] if url.endswith(".bundle") else data
    with pytest.raises(IOError):
        sync(layers, Short("1.7.7", [A]), {})
    assert not (layers[1] / hu.MANIFEST).exists()
