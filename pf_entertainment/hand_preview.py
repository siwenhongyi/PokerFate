from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from statistics import median
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CONSOLE_LOG = ROOT / "pokerfate" / "logs" / "pokerfate_console.log"

TS_RE = re.compile(r"^\[(\d{2}:\d{2}:\d{2})\]\s*(.*)$")
HAND_HEADER_RE = re.compile(r"第\s*(\d+)\s*手\s*(.*)$")
PLAYER_RE = re.compile(r"(?:^|\s{2,})(.+?)(?:\(([^)]*)\))?\s+(\d+)bb\s+\[([^\]]*)\]")
CARD_RE = re.compile(r"([2-9TJQKA])([♠♥♦♣]️?|[cdhs])", re.IGNORECASE)
RANK_TOKEN_RE = re.compile(r"(10|[2-9TJQKA])(?:[♠♥♦♣]️?|[cdhs])?", re.IGNORECASE)
HOLE_RE = re.compile(r"底牌\s+(.+)$")
STREET_RE = re.compile(r"──\s*(翻牌前|翻牌|转牌|河牌)\s*(.*?)\s*(?:底池\s+([\d,]+))?\s*─")
HERO_DECISION_RE = re.compile(r"►\s*(.+?)\s+(弃牌|过牌|跟注|加注|下注|全下)(?:\s+([+-]?\d+))?")
RESULT_RE = re.compile(
    r"✔\s*(.*?)\s+赢得\s+([\d,]+)\s+本手\s+([+-]?\d+)"
    r"(?:\s+\[我:\s*([^\]]+)\])?(?:\s*│\s*(.*))?"
)
FINAL_STACK_RE = re.compile(r"(?:^|\s{2,})(.+?)\s+(\d{4,})(?=\s{2,}|$)")
THOUGHT_PREFLOP_POS_RE = re.compile(
    r"【GTOv2·翻前】\s+\S+\s+([A-Z]{1,3}(?:\+\d+)?)\s"
)
GREENLINE_POS_RE = re.compile(r"\b(BTN|SB|BB|UTG(?:\+\d+)?|CO|HJ|MP)(?:-| )")

STREET_MAP = {
    "翻牌前": "preflop",
    "翻牌": "flop",
    "转牌": "turn",
    "河牌": "river",
}
SUIT_TO_SYMBOL = {"s": "♠", "h": "♥", "d": "♦", "c": "♣"}


@dataclass
class _HandCacheEntry:
    mtime_ns: int
    size: int
    hands: list["PreviewHand"]
    board_prefix_index: dict[tuple[str, ...], list["PreviewHand"]]


_HAND_CACHE: dict[Path, _HandCacheEntry] = {}


@dataclass
class PreviewHand:
    seq: int
    hand_no: int
    start_line: int
    end_line: int
    raw_lines: list[str]
    time: str = ""
    hero: str = ""
    hero_stack_bb: int | None = None
    header_positions: dict[str, str] = field(default_factory=dict)
    header_stacks_bb: dict[str, int] = field(default_factory=dict)
    hole_cards: list[str] = field(default_factory=list)
    board: list[str] = field(default_factory=list)
    board_by_street: dict[str, list[str]] = field(default_factory=dict)
    position: str = ""
    hero_actions: list[dict[str, Any]] = field(default_factory=list)
    vpip: bool = False
    complete: bool = False
    pot: int = 0
    pnl: int = 0
    winner_text: str = ""
    hero_combo: str = ""
    final_stacks: dict[str, int] = field(default_factory=dict)
    bb_chips: int | None = None

    @property
    def final_action(self) -> str:
        return self.hero_actions[-1]["action"] if self.hero_actions else ""

    @property
    def final_street(self) -> str:
        return self.hero_actions[-1]["street"] if self.hero_actions else ""

    @property
    def result_kind(self) -> str:
        if not self.complete:
            return "incomplete"
        if self.pnl > 0:
            return "profit"
        if self.pnl < 0:
            return "loss"
        return "zero"


def _strip_ts(line: str) -> tuple[str, str]:
    m = TS_RE.match(line.rstrip("\n"))
    if not m:
        return "", line.rstrip("\n")
    return m.group(1), m.group(2)


def _normalize_card(rank: str, suit: str) -> str:
    suit = suit.replace("\ufe0f", "").lower()
    return rank.upper() + SUIT_TO_SYMBOL.get(suit, suit)


def _extract_cards(text: str) -> list[str]:
    return [_normalize_card(rank, suit) for rank, suit in CARD_RE.findall(text)]


def _card_rank(card: str) -> str:
    text = str(card or "").strip().upper()
    if not text:
        return ""
    rank = text[:-1] if len(text) > 1 else text
    if rank == "10":
        rank = "T"
    return rank[:1]


def _normalize_board_query(text: str) -> tuple[str, ...]:
    ranks: list[str] = []
    for raw in RANK_TOKEN_RE.findall(str(text or "")):
        rank = str(raw or "").upper()
        ranks.append("T" if rank == "10" else rank)
        if len(ranks) >= 5:
            break
    return tuple(ranks)


def _num(text: str) -> int:
    try:
        return int(str(text).replace(",", ""))
    except Exception:
        return 0


def _action_hero(lines: list[str]) -> str:
    counts: dict[str, int] = {}
    for raw in lines:
        _ts, text = _strip_ts(raw)
        m = HERO_DECISION_RE.search(text)
        if m:
            name = m.group(1).strip()
            counts[name] = counts.get(name, 0) + 1
    if counts:
        return max(counts.items(), key=lambda item: item[1])[0]
    return ""


def _identify_hero(lines: list[str]) -> str:
    action_hero = _action_hero(lines)
    if action_hero:
        return action_hero
    fallback = ""
    for raw in lines:
        _ts, text = _strip_ts(raw)
        mh = HAND_HEADER_RE.search(text)
        if mh:
            for name, tag, _bb, pos in PLAYER_RE.findall(mh.group(2)):
                name = name.strip()
                if not tag and not fallback:
                    fallback = name
                if pos and not fallback:
                    fallback = name
    return fallback or "斯文红衣"


def _parse_position_from_text(text: str) -> str:
    m = THOUGHT_PREFLOP_POS_RE.search(text)
    if m:
        return m.group(1)
    m = GREENLINE_POS_RE.search(text)
    if m:
        return m.group(1)
    return ""


def _parse_hand(seq: int, start_line: int, raw_lines: list[str], hero: str) -> PreviewHand:
    first_ts, first_text = _strip_ts(raw_lines[0])
    mh = HAND_HEADER_RE.search(first_text)
    hand_no = int(mh.group(1)) if mh else seq
    h = PreviewHand(
        seq=seq,
        hand_no=hand_no,
        start_line=start_line,
        end_line=start_line + len(raw_lines) - 1,
        raw_lines=raw_lines,
        time=first_ts,
        hero=hero,
    )

    current_street = "preflop"
    for idx, raw in enumerate(raw_lines):
        _ts, text = _strip_ts(raw)
        mh = HAND_HEADER_RE.search(text)
        if mh:
            for name, _tag, stack_bb, pos in PLAYER_RE.findall(mh.group(2)):
                name = name.strip()
                h.header_stacks_bb[name] = int(stack_bb)
                h.header_positions[name] = pos
                if name == hero:
                    h.hero_stack_bb = int(stack_bb)
                    if pos:
                        h.position = pos
            continue

        if "底牌" in text:
            m = HOLE_RE.search(text)
            if m:
                h.hole_cards = _extract_cards(m.group(1))[:2]
            continue

        ms = STREET_RE.search(text)
        if ms:
            current_street = STREET_MAP.get(ms.group(1), current_street)
            cards = _extract_cards(ms.group(2) or "")
            h.board_by_street[current_street] = cards
            h.board = []
            for street in ("flop", "turn", "river"):
                h.board.extend(h.board_by_street.get(street, []))
            continue

        md = HERO_DECISION_RE.search(text)
        if md and md.group(1).strip() == hero:
            action_cn = md.group(2)
            amount = _num(md.group(3) or "0")
            action = {
                "弃牌": "fold",
                "过牌": "check",
                "跟注": "call",
                "加注": "raise",
                "下注": "bet",
                "全下": "jam",
            }.get(action_cn, action_cn)
            h.hero_actions.append({
                "street": current_street,
                "action": action,
                "action_cn": action_cn,
                "amount": amount,
                "line": text.strip(),
            })
            if action in {"call", "raise", "bet", "jam"} and amount > 0:
                h.vpip = True
            if not h.position:
                for nxt in raw_lines[idx:idx + 5]:
                    _nts, ntext = _strip_ts(nxt)
                    h.position = _parse_position_from_text(ntext)
                    if h.position:
                        break
            continue

        if not h.position:
            h.position = _parse_position_from_text(text)

        mr = RESULT_RE.search(text)
        if mr:
            h.complete = True
            h.winner_text = mr.group(1).strip()
            h.pot = _num(mr.group(2))
            h.pnl = _num(mr.group(3))
            h.hero_combo = (mr.group(4) or "").strip()
            h.final_stacks = {
                name.strip(): int(chips)
                for name, chips in FINAL_STACK_RE.findall(mr.group(5) or "")
            }
            estimates: list[int] = []
            for name, stack in h.final_stacks.items():
                bb = h.header_stacks_bb.get(name)
                if bb and bb > 0:
                    est = stack / bb
                    if est > 0:
                        estimates.append(max(1, int(round(est / 1000.0)) * 1000))
            if estimates:
                h.bb_chips = int(median(estimates))
    return h


def _is_header_prefix_line(raw: str) -> bool:
    _ts, text = _strip_ts(raw)
    stripped = text.strip()
    return not stripped or set(stripped) == {"━"}


def read_hands(log_path: Path = CONSOLE_LOG) -> list[PreviewHand]:
    return list(_read_hands_cached(log_path).hands)


def _parse_hands(log_path: Path) -> list[PreviewHand]:
    if not log_path.exists():
        return []
    lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
    hero = _identify_hero(lines)
    hands: list[PreviewHand] = []
    cur: list[str] = []
    cur_start = 0

    for line_no, raw in enumerate(lines, 1):
        _ts, text = _strip_ts(raw)
        if HAND_HEADER_RE.search(text):
            if cur:
                prefix: list[str] = []
                while cur and _is_header_prefix_line(cur[-1]):
                    prefix.insert(0, cur.pop())
                if cur:
                    hand_hero = _action_hero(cur) or hero
                    hands.append(_parse_hand(len(hands) + 1, cur_start, cur, hand_hero))
                cur = prefix + [raw]
                cur_start = line_no - len(prefix)
            else:
                cur = [raw]
                cur_start = line_no
        elif cur:
            cur.append(raw)
    if cur:
        hand_hero = _action_hero(cur) or hero
        hands.append(_parse_hand(len(hands) + 1, cur_start, cur, hand_hero))

    estimates = [h.bb_chips for h in hands if h.bb_chips]
    default_bb = int(median(estimates)) if estimates else 10000
    for h in hands:
        if not h.bb_chips:
            h.bb_chips = default_bb
    return hands


def _build_board_prefix_index(
    hands: list[PreviewHand],
) -> dict[tuple[str, ...], list[PreviewHand]]:
    index: dict[tuple[str, ...], list[PreviewHand]] = {}
    for hand in hands:
        ranks = tuple(rank for rank in (_card_rank(card) for card in hand.board) if rank)
        for prefix_len in range(1, min(5, len(ranks)) + 1):
            index.setdefault(ranks[:prefix_len], []).append(hand)
    return index


def _read_hands_cached(log_path: Path = CONSOLE_LOG) -> _HandCacheEntry:
    path = Path(log_path)
    try:
        stat = path.stat()
    except FileNotFoundError:
        entry = _HandCacheEntry(0, 0, [], {})
        _HAND_CACHE[path] = entry
        return entry
    cached = _HAND_CACHE.get(path)
    if (
        cached is not None
        and cached.mtime_ns == stat.st_mtime_ns
        and cached.size == stat.st_size
    ):
        return cached
    hands = _parse_hands(path)
    entry = _HandCacheEntry(
        mtime_ns=stat.st_mtime_ns,
        size=stat.st_size,
        hands=hands,
        board_prefix_index=_build_board_prefix_index(hands),
    )
    _HAND_CACHE[path] = entry
    return entry


def _summary(h: PreviewHand) -> dict[str, Any]:
    bb = h.bb_chips or 10000
    return {
        "id": h.seq,
        "hand_no": h.hand_no,
        "seq": h.seq,
        "time": h.time,
        "start_line": h.start_line,
        "end_line": h.end_line,
        "hero": h.hero,
        "position": h.position or "",
        "hero_stack_bb": h.hero_stack_bb,
        "vpip": h.vpip,
        "complete": h.complete,
        "result": h.result_kind,
        "pnl": h.pnl,
        "pnl_bb": round(h.pnl / bb, 2) if bb else 0.0,
        "bb_chips": bb,
        "bb_k": int(round(bb / 1000.0)),
        "hole_cards": h.hole_cards,
        "board": h.board,
        "final_action": h.final_action,
        "final_street": h.final_street,
        "winner_text": h.winner_text,
        "hero_combo": h.hero_combo,
        "pot": h.pot,
    }


def hand_list_payload(
    *,
    hand_no: str = "",
    board: str = "",
    position: str = "",
    vpip: str = "",
    result: str = "",
    bb_k: str = "",
    page: int = 1,
    page_size: int = 30,
    log_path: Path = CONSOLE_LOG,
) -> dict[str, Any]:
    cache = _read_hands_cached(log_path)
    hands = cache.hands
    positions = sorted({h.position for h in hands if h.position})
    bb_values = sorted({int(round((h.bb_chips or 0) / 1000.0)) for h in hands if h.bb_chips})
    board_prefix = _normalize_board_query(board)
    exact_hand_no: int | None = None
    hand_no = str(hand_no or "").strip()
    if hand_no and hand_no != "all":
        try:
            exact_hand_no = int(hand_no)
        except ValueError:
            exact_hand_no = -1

    def include(h: PreviewHand) -> bool:
        if exact_hand_no is not None and h.hand_no != exact_hand_no:
            return False
        if position and position != "all" and h.position != position:
            return False
        if vpip == "yes" and not h.vpip:
            return False
        if vpip == "no" and h.vpip:
            return False
        if result and result != "all" and h.result_kind != result:
            return False
        if bb_k and bb_k != "all":
            try:
                if int(bb_k) != int(round((h.bb_chips or 0) / 1000.0)):
                    return False
            except ValueError:
                pass
        return True

    candidates = (
        cache.board_prefix_index.get(board_prefix, [])
        if board_prefix
        else hands
    )
    filtered = [h for h in candidates if include(h)]
    filtered.sort(key=lambda item: item.seq, reverse=True)
    try:
        page = int(page)
    except (TypeError, ValueError):
        page = 1
    try:
        page_size = int(page_size)
    except (TypeError, ValueError):
        page_size = 30
    page = max(1, page)
    page_size = min(200, max(1, page_size))
    page_count = max(1, (len(filtered) + page_size - 1) // page_size)
    page = min(page, page_count)
    start = (page - 1) * page_size
    end = min(start + page_size, len(filtered))
    page_items = filtered[start:end]
    return {
        "log_path": str(log_path),
        "total": len(hands),
        "count": len(filtered),
        "board_query": board,
        "board_prefix": list(board_prefix),
        "positions": positions,
        "bb_k_values": bb_values,
        "page": page,
        "page_size": page_size,
        "page_count": page_count,
        "page_start": start + 1 if filtered else 0,
        "page_end": end,
        "has_prev": page > 1,
        "has_next": page < page_count,
        "hands": [_summary(h) for h in page_items],
    }


def hand_detail_payload(hand_id: int, log_path: Path = CONSOLE_LOG) -> dict[str, Any]:
    for hand in read_hands(log_path):
        if hand.seq == hand_id:
            return {
                "hand": _summary(hand),
                "log_text": "\n".join(hand.raw_lines),
            }
    raise KeyError(f"hand not found: {hand_id}")
