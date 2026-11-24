"""任务上报: the tasks the client counts by telling the server itself (TaskModel:reportTask).

Opening a page ("查看 X 界面", task type 302, the page in the task's value), touching a player
in the lobby (303) and using the table's chat (304: 1 a quick-chat line, 2 an emoji, 3 a free
interactive emoji thrown at a player) are counted when the client reports them with
``task/report``. This does what the client does for the tasks some source on the needs board
lacks, whichever list they are in: the report for a page or the lobby; at the bot's table the
chat itself first (TableChatLayer: TextREQ with a quick-chat line of the player the account
uses, FaceREQ with one of its emoji; IngameEmojiTipView: SendEmoji, only while the account has
free emoji left) and the report after it.

Each kind is done at most ``MAX_PER_DAY`` times a game day, from the journal across restarts:
a report the server does not count is not repeated for ever.
"""
from __future__ import annotations

import json

from pf_intercept.headless.lobby.core.base import Activity, _int, game_day, rows_of
from pf_intercept.headless.lobby.core.needs import task_key
from pf_reverse.tables import TABLES

REPORT = "/task/report"
CHECK_VIEW, ROLE_INTERACTION, TABLE_CHAT = 302, 303, 304     # TaskType / TaskTargetId
TEXT, EMOJI, EMOJI_ANI = 1, 2, 3     # TaskTableChatType: quick chat, emoji, interactive emoji
CHAT_LINE = 4                   # CHAT_VOICE_TYPE.Chat: a quick-chat line of tpl_chat
GREETING = "4001"               # the quick-chat line said first: a greeting
MAX_PER_DAY = 3                 # of each key
COMEBACK_SEC = 3


def first_role():
    """CharacterModel:getUsingRoleId when the server names none: the first player of the tables."""
    rows = TABLES.rows("character")
    return _int(rows[0]["id"]) if rows else 0


def quick_chat(role):
    """A quick-chat line of ``role`` anyone may say (no bond level, every language): the greeting
    when it has one, else its first."""
    lines = [r for r in TABLES.rows("chat") if _int(r.get("role")) == role and _int(r.get("kind")) == CHAT_LINE
             and not _int(r.get("unlock")) and not r.get("language_type")]
    lines.sort(key=lambda r: (str(r.get("key")) != GREETING, _int(r.get("id"))))
    return _int(lines[0]["id"]) if lines else 0


def emoji_of(role):
    """The first emoji of ``role`` that needs no bond level."""
    faces = sorted(_int(r["id"]) for r in TABLES.rows("emoji") if _int(r.get("role")) == role and not _int(r.get("unlock")))
    return faces[0] if faces else 0


class Reports(Activity):
    name = "reports"
    title = "任务上报"
    switch = ("task-reports", "不替任务上报查看界面 / 大厅互动，也不在牌桌说快捷语、发表情")
    does = {(CHECK_VIEW, None): "上报打开了任务要的界面", (ROLE_INTERACTION, None): "上报大厅与牌手互动",
            (TABLE_CHAT, TEXT): "牌桌上说一句问候快捷语再上报", (TABLE_CHAT, EMOJI): "牌桌上发一个表情再上报",
            (TABLE_CHAT, EMOJI_ANI): "牌桌上扔一个免费互动表情再上报"}
    limits = {key: MAX_PER_DAY for key in does}

    def __init__(self, service, session):
        super().__init__(service, session)
        self.day = None
        self.sent = {}              # key -> reports made today
        self.emoji_sent = False     # today's emoji went out and its report has not
        self.said = set()           # chat keys said today whose report has not gone out

    def load_day(self):
        day = game_day(self.service.now())
        if self.day == day:
            return
        self.day, self.sent, self.emoji_sent, self.said = day, {}, False, set()
        path = self.service._journal_path
        if not path.exists():
            return
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if row.get("uid") != self.service.uid or row.get("day") != day:
                continue
            if row.get("event") in ("report_sent", "emoji_attempt", "chat_attempt"):
                key = row.get("key") or task_key(TABLE_CHAT, EMOJI_ANI)
                self.sent[key] = self.sent.get(key, 0) + 1
            if row.get("event") == "chat_sent":
                self.said.add(row.get("key"))
            elif row.get("event") == "chat_reported":
                self.said.discard(row.get("key"))
            if row.get("event") == "emoji_sent":
                self.emoji_sent = True
            elif row.get("event") == "emoji_reported":
                self.emoji_sent = False

    async def check(self):
        self.load()
        self.load_day()
        needs = self.service.needs
        for key in needs.keys():
            if not isinstance(key, str) or self.sent.get(key, 0) >= MAX_PER_DAY or self.blocked(key):
                continue
            parts = key.split(":")[1:]
            kind, thing = _int(parts[0]), (_int(parts[1]) if len(parts) > 1 else None)
            if kind == CHECK_VIEW and thing:
                done = await self.report(key, CHECK_VIEW, thing)
            elif kind == ROLE_INTERACTION:
                done = await self.report(key, ROLE_INTERACTION, 0)
            elif kind == TABLE_CHAT and thing == EMOJI_ANI:
                done = await self.emoji(key)
            elif kind == TABLE_CHAT and thing in (TEXT, EMOJI):
                done = await self.chat(key, thing)
            else:
                continue
            if done:
                needs.played(key, 1, COMEBACK_SEC)

    async def report(self, key, task_type, ident):
        self.sent[key] = self.sent.get(key, 0) + 1
        self.service._record("report_sent", day=self.day, key=key, task_type=task_type, id=ident)
        return await self.ask(key, REPORT, {"task_type": task_type, "id": ident}) is not None

    async def emoji(self, key):
        """SendEmoji to a player at the table, then the report EmojiAni sends after it."""
        svc, session = self.service, self.session
        if not self.emoji_sent:
            room, target = session.activity_table()
            if not room or not target:
                return False
            player = await session.activity_request("SelfUserInfo", {})
            if _int(player.get("emoji_free_times")) <= 0 or session.activity_table() != (room, target):
                return False
            self.sent[key] = self.sent.get(key, 0) + 1
            svc._record("emoji_attempt", day=self.day, key=key, required=True)
            await session.activity_request("SendEmoji", {"id": 1, "to_uid": target}, room)
            svc._record("emoji_sent", day=self.day, required=True)
            self.emoji_sent = True
        # The client reports after SendEmojiRSP; a report that failed is retried on its own.
        if await self.ask(key, REPORT, {"task_type": TABLE_CHAT, "id": EMOJI_ANI}) is None:
            return False
        self.emoji_sent = False
        svc._record("emoji_reported", day=self.day)
        return True

    async def chat(self, key, kind):
        """A quick-chat line (TextREQ) or an emoji (FaceREQ) of the player the account uses, at the
        bot's table; then the report the client sends. Both go out as TableChatLayer sends them,
        without waiting for an answer: the server sends no TextRSP."""
        svc, session = self.service, self.session
        if key not in self.said:
            room, _ = session.activity_table()
            if not room:
                return False
            role = _int((await session.activity_request("RoleList", {})).get("using_role_id")) or first_role()
            line = quick_chat(role) if kind == TEXT else emoji_of(role)
            if not line:
                self.tell("chat_none", kind=kind, role=role)
                return False
            self.sent[key] = self.sent.get(key, 0) + 1
            svc._record("chat_attempt", day=self.day, key=key, kind=kind, role=role, id=line, required=True)
            if not await session.send("pb.TextREQ" if kind == TEXT else "pb.FaceREQ", {"id": line}, room):
                return False
            svc._record("chat_sent", day=self.day, key=key)
            self.said.add(key)
        if await self.ask(key, REPORT, {"task_type": TABLE_CHAT, "id": kind}) is None:
            return False
        self.said.discard(key)
        svc._record("chat_reported", day=self.day, key=key)
        return True
