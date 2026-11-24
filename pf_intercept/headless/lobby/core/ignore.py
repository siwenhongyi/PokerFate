"""忽略列表: what the radar does not tell the phone, because it was decided to leave it.

Two sources:

    INTERNAL   the project's decisions, here in the repository with their reasons: what the bot
               cannot do at all, and what it leaves alone on purpose (its rules)
    external   the user's decisions: ``local/state/lobby_ignores.json`` (this machine's state, not in
               the repository), edited from the console's 雷达 tab:
                   {"<key>": {"ignore": true, "reason": "...", "at": "11-26 17:30"}, ...}   (at: UTC+8)
               An external entry wins over an internal one of the same key, so the user can also
               take back one of the project's decisions ("ignore": false).

Keys:

    task:<type>                 a task type, wherever it is
    task:<type>:<thing>         a task type about one thing (a game, a page, an item)
    limit:<type>:<thing>        a task somebody does, but asking more than the daily limit allows
    table:<name>                an activity table: its periods need no code
    period:<table>:<id>         one period of an activity

Whatever is ignored is still printed by ``python -m pf_intercept.headless.lobby``, with its
reason and whose decision it is, so nothing is forgotten.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

UTC8 = timezone(timedelta(hours=8))

OMAHA, AOF = 10020101, 10040101
GHOST_CASTLE = 30090101         # 幽灵古堡之谜: the side game of 即兴恶作剧 (主题活动 10010)

INTERNAL = {
    **{f"task:{kind}": "直播和投稿（创作者活动），bot 做不了" for kind in range(324, 334)},
    "task:1201": "邀请好友回归，要真人被邀请",
    "task:1202": "邀请好友回归，要真人被邀请",
    "table:invite_rules": "邀请好友回归，要真人被邀请",
    "task:103": "按下注额计的任务随同一批局数一起涨，不为它多玩（项目规则）",
    "task:105": "从来不打锦标赛（SNG）",
    "task:130": "从来不打锦标赛（MTT）",
    "task:126": "用指定牌手参与赛事：要打锦标赛，从来不打",
    "task:305": "牌手招募不做",
    f"task:101:{GHOST_CASTLE}": "主题活动自带的小游戏（幽灵古堡之谜），只奖励 100 个活动代币，不划算",
    f"limit:101:{OMAHA}": "每周后面几档要更多手数，多打是亏的，每天最多 15 手（任务手数的规则）",
    f"limit:101:{AOF}": "每周后面几档要更多手数，AOF 每手交前注，每天最多 15 手（任务手数的规则）",
}
EXTERNAL_PATH = Path(__file__).resolve().parents[4] / "local" / "state" / "lobby_ignores.json"
KEY = re.compile(r"(task|limit):\d+(:\d+)?|table:[A-Za-z0-9_:]+|period:[A-Za-z0-9_:]+:\d+")
REASON_MAX = 80


def valid_key(key) -> bool:
    return isinstance(key, str) and KEY.fullmatch(key) is not None


class Ignores:
    """The internal list with the external file over it. ``reason(key)`` -> (reason, whose) when
    ignored, None when not."""

    def __init__(self, internal=None, external_path=EXTERNAL_PATH):
        self.internal = dict(INTERNAL if internal is None else internal)
        self.external_path = Path(external_path) if external_path else None
        self._external = (None, {})

    def external(self) -> dict:
        """The external file's entries, read again when it changes; {} without one."""
        if self.external_path is None:
            return {}
        try:
            stamp = self.external_path.stat().st_mtime_ns
        except OSError:
            return {}
        if self._external[0] != stamp:
            try:
                data = json.loads(self.external_path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                data = {}
            self._external = (stamp, {str(k): v for k, v in data.items() if isinstance(v, dict)}
                              if isinstance(data, dict) else {})
        return self._external[1]

    def reason(self, key):
        entry = self.external().get(key)
        if entry is not None:
            return (str(entry.get("reason") or "你决定忽略"), "外部") if entry.get("ignore", True) else None
        if key in self.internal:
            return self.internal[key], "内部"
        return None

    def set(self, key, ignore=True, reason=""):
        """Write the user's decision on ``key`` into the external file."""
        if not valid_key(key):
            raise ValueError(f"not an ignore key: {key!r}")
        entries = dict(self.external())
        entries[key] = {"ignore": bool(ignore), "reason": str(reason or "").strip()[:REASON_MAX],
                        "at": datetime.now(UTC8).strftime("%m-%d %H:%M")}     # game time, as the radar shows it
        self._save(entries)

    def drop(self, key):
        """Forget the user's decision on ``key``: what the project decides holds again."""
        entries = dict(self.external())
        if entries.pop(key, None) is not None:
            self._save(entries)

    def _save(self, entries):
        if self.external_path is None:
            raise ValueError("no external ignore file")
        self.external_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.external_path.with_name(self.external_path.name + ".part")
        tmp.write_text(json.dumps(entries, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
        tmp.replace(self.external_path)
        self._external = (None, {})

    def entries(self):
        """Every decision, for the web: [{key, reason, by, ignore, at, overrides}] — internal ones
        with what the user said over them, then the user's own."""
        external = self.external()
        out = []
        for key, reason in self.internal.items():
            mine = external.get(key)
            out.append({"key": key, "reason": reason, "by": "内部", "ignore": mine is None or bool(mine.get("ignore", True)),
                        "overridden": mine is not None, "at": (mine or {}).get("at", "")})
        for key, entry in external.items():
            if key not in self.internal:
                out.append({"key": key, "reason": str(entry.get("reason") or "你决定忽略"), "by": "外部",
                            "ignore": bool(entry.get("ignore", True)), "overridden": False, "at": entry.get("at", "")})
        return out

    def first(self, *keys):
        for key in keys:
            found = self.reason(key)
            if found:
                return found
        return None

    def task(self, kind, thing=None):
        return self.first(*([f"task:{kind}:{thing}"] if thing is not None else []), f"task:{kind}")

    def limit(self, kind, thing=None):
        return self.first(*([f"limit:{kind}:{thing}"] if thing is not None else []), f"limit:{kind}")

    def period(self, table, ident):
        return self.first(f"period:{table}:{ident}", f"table:{table}")


IGNORES = Ignores()
