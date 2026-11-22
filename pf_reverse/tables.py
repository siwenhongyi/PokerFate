"""The client's config tables (``tpl_*.lua``) as Python values, as the running client has them.

The client is two layers, as on the phone: the installer's files (``output/``, extracted from
the APK, in the repository) and the hot update over them (``remote_res/``, synced from the CDN
by ``pf_reverse.hotupdate``, git-ignored). A file of the hot update wins over the installer's;
a file the hot update removed is gone (``remote_res/manifest.json`` lists them). Whoever reads
through here sees a new period as soon as the hot update is synced, without a restart: a table
is read again when its file changes.

Two layouts, both written by the game's export_excel.py:

    rows       local keys = {'id', ...}  local bodys = { {...}, {...} }   -> rows(name)
    constants  tpl_constdata = { Name = value, ... }                     -> const(name)

Lua values map to Python as: number -> int / float, string -> str, nil -> None,
true / false -> bool, a table of values -> list, a table with keys -> dict.
"""
from __future__ import annotations

import json
import re
import threading
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE / "output"              # the installer's client (APK), in the repository
REMOTE = HERE / "remote_res"        # the hot update over it, git-ignored
TPL_DIR = Path("lua") / "src" / "tpl"
TPL = BASE / TPL_DIR
REMOTE_TPL = REMOTE / TPL_DIR
MANIFEST = "manifest.json"
TEXT_TABLE = "mult_language"
LANG = "zh"

_TOKEN = re.compile(r"""
    (?P<space>\s+) |
    (?P<comment>--\[(?P<ceq>=*)\[.*?\](?P=ceq)\]|--[^\n]*) |
    (?P<long>\[(?P<leq>=*)\[.*?\](?P=leq)\]) |
    (?P<str>"(?:\\.|[^"\\\n])*"|'(?:\\.|[^'\\\n])*') |
    (?P<num>-?(?:0[xX][0-9a-fA-F]+|\d+\.?\d*(?:[eE][-+]?\d+)?|\.\d+)) |
    (?P<name>[A-Za-z_]\w*) |
    (?P<sym>[{}\[\]=,;]) |
    (?P<other>.)
""", re.VERBOSE | re.DOTALL)
_KINDS = ("long", "str", "num", "name", "sym", "other")
_ESCAPES = {"n": "\n", "t": "\t", "r": "\r", "\\": "\\", '"': '"', "'": "'", "0": "\0"}


class LuaSyntaxError(ValueError):
    pass


class OtherLayout(LuaSyntaxError):
    """A tpl file in neither layout (tpl_chat_voice): it has no rows to give."""


def _tokens(text):
    """Every token of a Lua file. Code the tables do not use (calls, operators) comes out as
    ``other`` tokens, which only a value may not contain."""
    out = []
    for m in _TOKEN.finditer(text):
        for kind in _KINDS:
            raw = m.group(kind)
            if raw is not None:
                out.append((kind, raw))
                break
    return out


def _long(raw):
    """A [[...]] or [==[...]==] string; Lua drops a newline right after the opening bracket."""
    level = raw.index("[", 1) + 1
    body = raw[level:len(raw) - level]
    return body[1:] if body.startswith("\n") else body


def _string(raw):
    body, out, i = raw[1:-1], [], 0
    while i < len(body):
        ch = body[i]
        if ch == "\\" and i + 1 < len(body):
            out.append(_ESCAPES.get(body[i + 1], body[i + 1]))
            i += 2
        else:
            out.append(ch)
            i += 1
    return "".join(out)


def _number(raw):
    neg = raw.startswith("-")
    digits = raw[1:] if neg else raw
    if digits[:2] in ("0x", "0X"):
        value = int(digits, 16)
    elif any(c in digits for c in ".eE"):
        value = float(digits)
    else:
        value = int(digits)
    return -value if neg else value


class _Parser:
    def __init__(self, tokens):
        self.tokens, self.i = tokens, 0

    def peek(self, offset=0):
        j = self.i + offset
        return self.tokens[j] if j < len(self.tokens) else (None, None)

    def take(self, kind=None, value=None):
        token = self.peek()
        if token[0] is None or (kind and token[0] != kind) or (value is not None and token[1] != value):
            raise LuaSyntaxError(f"expected {value or kind}, got {token[1]!r}")
        self.i += 1
        return token

    def value(self):
        kind, raw = self.peek()
        if kind == "str":
            self.i += 1
            return _string(raw)
        if kind == "long":
            self.i += 1
            return _long(raw)
        if kind == "num":
            self.i += 1
            return _number(raw)
        if kind == "name":
            # A bare name other than these is a global the client reads; its name is kept.
            self.i += 1
            return {"nil": None, "true": True, "false": False}.get(raw, raw)
        if (kind, raw) == ("sym", "{"):
            return self.table()
        raise LuaSyntaxError(f"unexpected {raw!r}")

    def table(self):
        self.take("sym", "{")
        items, keyed = [], {}
        while self.peek() != ("sym", "}"):
            kind, raw = self.peek()
            if kind == "name" and self.peek(1) == ("sym", "="):
                self.i += 2
                keyed[raw] = self.value()
            elif (kind, raw) == ("sym", "["):
                self.i += 1
                key = self.value()
                self.take("sym", "]")
                self.take("sym", "=")
                keyed[key] = self.value()
            else:
                items.append(self.value())
            if self.peek() in (("sym", ","), ("sym", ";")):
                self.i += 1
            elif self.peek() != ("sym", "}"):
                raise LuaSyntaxError(f"expected , or }}, got {self.peek()[1]!r}")
        self.take("sym", "}")
        if not keyed:
            return items
        keyed.update((n, v) for n, v in enumerate(items, 1))
        return keyed


def parse_value(text):
    """One Lua value written as a literal."""
    parser = _Parser(_tokens(text))
    value = parser.value()
    if parser.peek()[0] is not None:
        raise LuaSyntaxError("text after the value")
    return value


def _value_after(tokens, *names):
    """The value assigned right after the names ``names`` (``local keys =`` ...)."""
    words = [("name", n) for n in names] + [("sym", "=")]
    for i in range(len(tokens) - len(words)):
        if tokens[i:i + len(words)] == words:
            parser = _Parser(tokens)
            parser.i = i + len(words)
            return parser.value()
    return None


def parse_rows(text):
    """Rows of a table file: one dict per row, keyed by the file's column names."""
    tokens = _tokens(text)
    keys, rows = _value_after(tokens, "local", "keys"), _value_after(tokens, "local", "bodys")
    if not isinstance(keys, list) or not isinstance(rows, list):
        raise OtherLayout("not a row table")
    return [dict(zip(keys, list(row) + [None] * (len(keys) - len(row)))) for row in rows]


def parse_constants(text, name):
    value = _value_after(_tokens(text), f"tpl_{name}")
    if not isinstance(value, dict):
        raise OtherLayout("not a constant table")
    return value


def removed_files(manifest: Path) -> set:
    """Output paths the hot update removed (``lua/src/tpl/tpl_x.lua`` ...)."""
    try:
        data = json.loads(Path(manifest).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return set()
    return set(data.get("removed") or []) if isinstance(data, dict) else set()


class Tables:
    """Reads the tables from ``roots`` (tpl directories, the first that has a file wins) and keeps
    each until its file changes. ``manifest``: the hot update's, whose removed files are gone."""

    def __init__(self, *roots, manifest=None):
        self.roots = [Path(root) for root in roots] or [TPL]
        self.manifest = Path(manifest) if manifest else None
        self._cache = {}        # (kind, name) -> ((path, mtime_ns, size), value)
        self._removed = (None, set())
        self._lock = threading.Lock()

    def removed(self) -> set:
        if self.manifest is None:
            return set()
        try:
            stamp = self.manifest.stat().st_mtime_ns
        except OSError:
            return set()
        if self._removed[0] != stamp:
            self._removed = (stamp, removed_files(self.manifest))
        return self._removed[1]

    def path(self, name):
        """The file of a table as the client has it, else None."""
        filename = f"tpl_{name}.lua"
        if (TPL_DIR / filename).as_posix() in self.removed():
            return None
        for root in self.roots:
            candidate = root / filename
            if candidate.is_file():
                return candidate
        return None

    def names(self):
        """Every table the client has, by name (``monopoly_activity`` for tpl_monopoly_activity.lua)."""
        found = {p.stem[4:] for root in self.roots if root.is_dir() for p in root.glob("tpl_*.lua")}
        return sorted(name for name in found if self.path(name) is not None)

    def _load(self, kind, name, parse):
        path = self.path(name)
        if path is None:
            return None
        try:
            stat = path.stat()
        except FileNotFoundError:
            return None
        stamp = (str(path), stat.st_mtime_ns, stat.st_size)
        with self._lock:
            cached = self._cache.get((kind, name))
            if cached and cached[0] == stamp:
                return cached[1]
        try:
            value = parse(path.read_text(encoding="utf-8"))
        except OtherLayout:
            value = None
        with self._lock:
            self._cache[(kind, name)] = (stamp, value)
        return value

    def rows(self, name):
        """The table's rows, [] when the client has no such table (or not as rows)."""
        return self._load("rows", name, parse_rows) or []

    def row(self, name, ident):
        """The row whose first column is ``ident``, else None."""
        for row in self.rows(name):
            if next(iter(row.values()), None) == ident:
                return row
        return None

    def constants(self):
        """tpl_constdata: the client's single values (Dispatch_Start, Theme_Lottery_Limit, ...)."""
        return dict(self._load("const", "constdata", lambda text: parse_constants(text, "constdata")) or {})

    def const(self, key, default=None):
        return self.constants().get(key, default)

    def text(self, key, lang=LANG):
        """The client's text for a language key in ``lang``; the key itself when it has none."""
        if not isinstance(key, str):
            return key
        texts = self._load("text", TEXT_TABLE, lambda raw: {
            row["id"]: row.get(lang) for row in parse_rows(raw) if isinstance(row.get("id"), str)})
        found = (texts or {}).get(key)
        return found if isinstance(found, str) and found else key


TABLES = Tables(REMOTE_TPL, TPL, manifest=REMOTE / MANIFEST)     # the client as it runs
