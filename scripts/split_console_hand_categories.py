#!/usr/bin/env python3
"""Split PokerFate console logs into mutually exclusive hand categories.

The script intentionally works from the console log itself, not replay output,
so it can be used on live sessions even when strategy code is dirty.
"""

from __future__ import annotations

import argparse
import math
import re
import shutil
import sys
from dataclasses import dataclass, field
from itertools import combinations
from pathlib import Path
from statistics import median
from typing import Iterable, Optional

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pokerfate.core.card import Card
from pokerfate.core.hand_evaluator import HandEvaluator


TS_RE = re.compile(r"^\[\d{2}:\d{2}:\d{2}\]\s*")
HAND_HEADER_RE = re.compile(r"第\s*(\d+)\s*手\s+(.*)$")
PLAYER_RE = re.compile(r"(\S+?)(?:\(([^)]+)\))?\s+(\d+)bb\s+\[\]")
STREET_RE = re.compile(r"──\s*(翻牌前|翻牌|转牌|河牌)\s*(.*?)\s*(?:底池\s+(\d+))?\s*─")
RESULT_RE = re.compile(
    r"✔\s*(.*?)\s*赢得\s*(\d+)\s+本手\s*([+-]\d+).*?\[我:\s*([^\]]+)\]\s*│\s*(.*)$"
)
LEARN_RE = re.compile(
    r"◈\s*学习\s+(.+?)\s+([2-9TJQKA][♠♥♦♣]️?)\s+([2-9TJQKA][♠♥♦♣]️?)\s+"
)
CARD_RE = re.compile(r"([2-9TJQKA][♠♥♦♣]️?)")
EQUITY_RE = re.compile(r"胜率\s*(\d+)%")
SPR_RE = re.compile(r"SPR[≈=]?\s*([\d.]+)")
BRANCH_RE = re.compile(r"分支=([^│]+)")
CANDIDATE_RE = re.compile(r"候选:\s*([^│]+)")
GATE_RE = re.compile(r"门:\s*([^│]+)")

STREET_MAP = {
    "翻牌前": "preflop",
    "翻牌": "flop",
    "转牌": "turn",
    "河牌": "river",
}
CN_STREET = {
    "preflop": "翻前",
    "flop": "翻牌",
    "turn": "转牌",
    "river": "河牌",
}
RANK_ORDER = {
    "高牌": 0,
    "一对": 1,
    "两对": 2,
    "三条": 3,
    "顺子": 4,
    "同花": 5,
    "葫芦": 6,
    "四条": 7,
    "同花顺": 8,
    "皇家同花顺": 9,
}
SUIT_MAP = {"♣": "c", "♦": "d", "♥": "h", "♠": "s"}


@dataclass
class Decision:
    street: str
    action: str
    line_no: int
    line: str
    equity: Optional[float] = None
    spr: Optional[float] = None
    thought: str = ""
    branch: str = ""
    candidates: str = ""
    gate: str = ""


@dataclass
class Hand:
    seq: int
    hand_no: int
    source: str
    start_line: int
    lines: list[str]
    hero: str
    hero_stack_bb: Optional[int] = None
    hole_cards: list[str] = field(default_factory=list)
    board_by_street: dict[str, list[str]] = field(default_factory=dict)
    decisions: list[Decision] = field(default_factory=list)
    winner_part: str = ""
    winner_names: list[str] = field(default_factory=list)
    winner_detail: str = ""
    winner_hand_type: str = ""
    hero_final_text: str = ""
    hero_pnl_chips: int = 0
    result_line: str = ""
    learned_holes: dict[str, list[str]] = field(default_factory=dict)
    complete: bool = False

    @property
    def board(self) -> list[str]:
        cards: list[str] = []
        for street in ("flop", "turn", "river"):
            cards.extend(self.board_by_street.get(street, []))
        return cards

    @property
    def last_decision(self) -> Optional[Decision]:
        return self.decisions[-1] if self.decisions else None

    @property
    def final_action(self) -> str:
        return self.last_decision.action if self.last_decision else ""

    @property
    def final_street(self) -> str:
        return self.last_decision.street if self.last_decision else ""

    @property
    def hero_won(self) -> bool:
        return self.hero in self.winner_names

    @property
    def showdownish(self) -> bool:
        if self.final_action == "fold":
            return False
        return len(self.board) >= 5 or bool(self.learned_holes)


def strip_ts(line: str) -> str:
    return TS_RE.sub("", line.rstrip("\n"))


def normalize_card(card: str) -> str:
    card = card.replace("\ufe0f", "")
    return card[0] + SUIT_MAP[card[1]]


def card_obj(card: str) -> Card:
    return Card.from_str(normalize_card(card))


def extract_cards(text: str) -> list[str]:
    return [m.group(1).replace("\ufe0f", "") for m in CARD_RE.finditer(text)]


def hand_type(text: str) -> str:
    for name in ("皇家同花顺", "同花顺", "四条", "葫芦", "同花", "顺子", "三条", "两对", "一对", "高牌"):
        if name in text:
            return name
    return ""


def identify_hero_from_lines(lines: Iterable[str]) -> str:
    counts: dict[str, int] = {}
    header_candidates: list[str] = []
    for raw in lines:
        line = strip_ts(raw)
        if "►" in line:
            m = re.search(r"►\s*(\S+)", line)
            if m:
                counts[m.group(1)] = counts.get(m.group(1), 0) + 1
        mh = HAND_HEADER_RE.search(line)
        if mh:
            for name, typ, _bb in PLAYER_RE.findall(mh.group(2)):
                if not typ:
                    header_candidates.append(name)
    if counts:
        return max(counts.items(), key=lambda kv: kv[1])[0]
    if header_candidates:
        return header_candidates[0]
    return "斯文红衣"


def iter_hands(log_path: Path, hero: str) -> Iterable[Hand]:
    seq = 0
    cur_lines: list[str] = []
    cur_start = 0
    cur_no = 0
    with log_path.open("r", encoding="utf-8", errors="replace") as fh:
        for line_no, raw in enumerate(fh, 1):
            line = strip_ts(raw)
            mh = HAND_HEADER_RE.search(line)
            if mh:
                if cur_lines:
                    seq += 1
                    yield parse_hand(seq, cur_no, log_path.name, cur_start, cur_lines, hero)
                cur_lines = [raw.rstrip("\n")]
                cur_start = line_no
                cur_no = int(mh.group(1))
            elif cur_lines:
                cur_lines.append(raw.rstrip("\n"))
    if cur_lines:
        seq += 1
        yield parse_hand(seq, cur_no, log_path.name, cur_start, cur_lines, hero)


def _extract_decision_context(lines: list[str], idx: int) -> tuple[str, str, str, str]:
    thought = ""
    branch = ""
    candidates = ""
    gate = ""
    for nxt in lines[idx + 1: idx + 6]:
        s = strip_ts(nxt)
        if "💭" in s:
            thought = s.split("💭", 1)[-1].strip()
        if "分支=" in s:
            m = BRANCH_RE.search(s)
            if m:
                branch = m.group(1).strip()
        if "候选:" in s:
            m = CANDIDATE_RE.search(s)
            if m:
                candidates = m.group(1).strip()
        if "门:" in s:
            m = GATE_RE.search(s)
            if m:
                gate = m.group(1).strip()
    return thought, branch, candidates, gate


def parse_action(line: str) -> str:
    if "弃牌" in line:
        return "fold"
    if "跟注" in line:
        return "call"
    if "加注" in line:
        return "raise"
    if "过牌" in line:
        return "check"
    return "unknown"


def parse_hand(seq: int, hand_no: int, source: str, start_line: int, raw_lines: list[str], hero: str) -> Hand:
    h = Hand(seq=seq, hand_no=hand_no, source=source, start_line=start_line, lines=raw_lines, hero=hero)
    current_street = ""
    for idx, raw in enumerate(raw_lines):
        line = strip_ts(raw)
        mh = HAND_HEADER_RE.search(line)
        if mh:
            for name, _typ, bb in PLAYER_RE.findall(mh.group(2)):
                if name == hero:
                    h.hero_stack_bb = int(bb)
                    break
        if "底牌" in line:
            h.hole_cards = extract_cards(line)[:2]
        ms = STREET_RE.search(line)
        if ms:
            current_street = STREET_MAP[ms.group(1)]
            cards = extract_cards(ms.group(2) or "")
            h.board_by_street[current_street] = cards
        if f"► {hero}" in line:
            thought, branch, candidates, gate = _extract_decision_context(raw_lines, idx)
            eq_m = EQUITY_RE.search(line)
            spr_m = SPR_RE.search(line)
            h.decisions.append(Decision(
                street=current_street or "preflop",
                action=parse_action(line),
                line_no=start_line + idx,
                line=line.strip(),
                equity=(float(eq_m.group(1)) / 100.0 if eq_m else None),
                spr=(float(spr_m.group(1)) if spr_m else None),
                thought=thought,
                branch=branch,
                candidates=candidates,
                gate=gate,
            ))
        mr = RESULT_RE.search(line)
        if mr:
            h.complete = True
            h.result_line = line.strip()
            h.winner_part = mr.group(1).strip()
            h.hero_pnl_chips = int(mr.group(3))
            h.hero_final_text = mr.group(4).strip()
            winner_chunks = [x.strip() for x in h.winner_part.split("&")]
            for chunk in winner_chunks:
                name = chunk.split("[", 1)[0].strip()
                if name:
                    h.winner_names.append(name)
            first_detail = ""
            m_first = re.search(r"\[([^\]]+)\]", h.winner_part)
            if m_first:
                first_detail = m_first.group(1).strip()
            h.winner_detail = first_detail
            h.winner_hand_type = hand_type(first_detail)
        ml = LEARN_RE.search(line)
        if ml:
            h.learned_holes[ml.group(1).strip()] = [ml.group(2).replace("\ufe0f", ""), ml.group(3).replace("\ufe0f", "")]
    return h


def infer_big_blind(hands: list[Hand]) -> int:
    estimates: list[int] = []
    for h in hands:
        if not h.result_line:
            continue
        tail = h.result_line.split("│", 1)
        if len(tail) != 2:
            continue
        header_bbs: dict[str, int] = {}
        for raw in h.lines:
            line = strip_ts(raw)
            mh = HAND_HEADER_RE.search(line)
            if mh:
                header_bbs = {name: int(bb) for name, _typ, bb in PLAYER_RE.findall(mh.group(2))}
                break
        for m in re.finditer(r"(\S+?)\s+(\d{4,})", tail[1]):
            name, chips = m.group(1), int(m.group(2))
            if name in header_bbs and header_bbs[name] > 0:
                est = chips / header_bbs[name]
                if est > 0:
                    estimates.append(int(round(est / 1000.0)) * 1000)
    if not estimates:
        return 10000
    return int(median(estimates))


def preflop_faced_raise_before_final(h: Hand) -> bool:
    final = h.last_decision
    if not final or final.street != "preflop":
        return False
    for idx, raw in enumerate(h.lines):
        abs_line = h.start_line + idx
        if abs_line >= final.line_no:
            break
        line = strip_ts(raw)
        if "── 翻牌" in line and "翻牌前" not in line:
            return False
        if "加注" in line and f"► {h.hero}" not in line:
            return True
    return False


def outcome_category_1_6(h: Hand) -> str:
    if h.hero_stack_bb is None and not h.decisions:
        return "00_审计_未参与或未完成"
    final = h.last_decision
    if final and final.action == "fold":
        if final.street == "preflop":
            return "01_翻前面对开加弃牌" if preflop_faced_raise_before_final(h) else "01_翻前直接弃牌_无人首加"
        if final.street == "flop":
            return "02_翻牌弃牌"
        if final.street == "turn":
            return "03_转牌弃牌"
        if final.street == "river":
            return "04_河牌弃牌"
    if h.showdownish and h.hero_won:
        return "05_摊牌胜利"
    if h.showdownish and not h.hero_won:
        return "06_摊牌失败"
    return "00_审计_未参与或未完成"


def pnl_category_7_10(h: Hand, bb: int) -> str:
    if not h.complete:
        return "00_审计_未参与或未完成"
    pnl_bb = h.hero_pnl_chips / bb if bb else 0.0
    if pnl_bb <= -20.0:
        return "07_大亏_20bb以上"
    if pnl_bb < 0:
        final = h.last_decision
        blind_only = (
            abs(pnl_bb) <= 1.05
            and final is not None
            and final.street == "preflop"
            and final.action in {"fold", "check"}
        )
        return "08_小盲大盲损失_排除项" if blind_only else "08_小亏_20bb以内"
    if 0 < pnl_bb < 20.0:
        return "09_小赢_20bb以内"
    if pnl_bb >= 20.0:
        return "10_大赢_20bb以上"
    return "00_零盈亏"


def score_cards(cards: list[str]):
    return HandEvaluator.evaluate([card_obj(c) for c in cards])


def exact_compare_with_winner(h: Hand) -> tuple[Optional[int], str]:
    """Return compare(hero, winner): 1 hero wins, -1 hero loses, 0 tie."""
    board = h.board
    if len(board) == 5 and len(h.hole_cards) == 2:
        for winner in h.winner_names:
            if winner == h.hero:
                continue
            wh = h.learned_holes.get(winner)
            if wh and len(wh) == 2:
                hero_score = score_cards(h.hole_cards + board)
                villain_score = score_cards(wh + board)
                return HandEvaluator.compare(hero_score, villain_score), f"exact:{winner} {''.join(wh)}"
    hero_type = hand_type(h.hero_final_text)
    winner_type = h.winner_hand_type
    if hero_type and winner_type:
        hr = RANK_ORDER.get(hero_type, -1)
        wr = RANK_ORDER.get(winner_type, -1)
        if hr > wr:
            return 1, "type_only"
        if hr < wr:
            return -1, "type_only"
        hero_cards = extract_cards(h.hero_final_text)
        winner_cards = extract_cards(h.winner_detail)
        if len(hero_cards) >= 5 and len(winner_cards) >= 5:
            return HandEvaluator.compare(score_cards(hero_cards[:5]), score_cards(winner_cards[:5])), "best5_text"
    return None, "insufficient"


def win_bucket_for_fold(h: Hand) -> tuple[str, str]:
    cmp, evidence = exact_compare_with_winner(h)
    if cmp is not None:
        if cmp > 0:
            return "我们肯定大", evidence
        if cmp == 0:
            return "平局", evidence
        return "我们肯定小", evidence

    hero_type = hand_type(h.hero_final_text)
    winner_type = h.winner_hand_type
    if not hero_type or not winner_type:
        return "无法判断", evidence
    hr = RANK_ORDER.get(hero_type, -1)
    wr = RANK_ORDER.get(winner_type, -1)
    if hr > wr:
        return "我们肯定大", "type_only"
    if hr < wr:
        return "我们肯定小", "type_only"

    hero_cards = [normalize_card(c) for c in extract_cards(h.hero_final_text)]
    ranks = [c[0] for c in hero_cards]
    if hero_type in {"一对", "两对"} and ("A" in ranks or "K" in ranks):
        return "我们大概率大", "same_type_heuristic"
    if hero_type in {"顺子", "同花", "葫芦"}:
        return "我们小概率大", "same_type_no_kicker"
    return "我们小概率大", "same_type_heuristic"


def exact_suckout_info(h: Hand) -> Optional[dict]:
    if not h.complete or h.hero_won or len(h.hole_cards) != 2 or len(h.board) != 5:
        return None
    winner = next((w for w in h.winner_names if w != h.hero and w in h.learned_holes), "")
    if not winner:
        return None
    villain_hole = h.learned_holes[winner]
    if len(villain_hole) != 2:
        return None
    flop = h.board[:3]
    turn_board = h.board[:4]
    river_board = h.board[:5]
    hero_flop = score_cards(h.hole_cards + flop)
    villain_flop = score_cards(villain_hole + flop)
    hero_turn = score_cards(h.hole_cards + turn_board)
    villain_turn = score_cards(villain_hole + turn_board)
    hero_river = score_cards(h.hole_cards + river_board)
    villain_river = score_cards(villain_hole + river_board)
    if not (
        HandEvaluator.compare(hero_flop, villain_flop) > 0
        and HandEvaluator.compare(hero_turn, villain_turn) > 0
        and HandEvaluator.compare(hero_river, villain_river) < 0
    ):
        return None

    known_turn = {normalize_card(c) for c in (h.hole_cards + villain_hole + turn_board)}
    deck = [r + s for r in "23456789TJQKA" for s in "cdhs"]
    unseen_turn = [c for c in deck if c not in known_turn]
    river_win = 0
    river_tie = 0
    for c in unseen_turn:
        hero = HandEvaluator.evaluate([Card.from_str(x) for x in (map(normalize_card, h.hole_cards + turn_board))] + [Card.from_str(c)])
        vil = HandEvaluator.evaluate([Card.from_str(x) for x in (map(normalize_card, villain_hole + turn_board))] + [Card.from_str(c)])
        cmp = HandEvaluator.compare(vil, hero)
        river_win += int(cmp > 0)
        river_tie += int(cmp == 0)

    known_flop = {normalize_card(c) for c in (h.hole_cards + villain_hole + flop)}
    unseen_flop = [c for c in deck if c not in known_flop]
    two_card_win = 0
    two_card_total = 0
    for c1, c2 in combinations(unseen_flop, 2):
        board = flop + [c1[0] + { "c": "♣", "d": "♦", "h": "♥", "s": "♠" }[c1[1]], c2[0] + { "c": "♣", "d": "♦", "h": "♥", "s": "♠" }[c2[1]]]
        hero = score_cards(h.hole_cards + board)
        vil = score_cards(villain_hole + board)
        two_card_win += int(HandEvaluator.compare(vil, hero) > 0)
        two_card_total += 1

    return {
        "winner": winner,
        "winner_hole": "".join(villain_hole),
        "river_win": river_win,
        "river_total": len(unseen_turn),
        "river_tie": river_tie,
        "river_prob": river_win / len(unseen_turn) if unseen_turn else 0.0,
        "flop_to_river_prob": two_card_win / two_card_total if two_card_total else 0.0,
        "flop_to_river_total": two_card_total,
    }


def md_escape(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ").strip()


def hand_label(h: Hand, bb: int) -> str:
    pnl = h.hero_pnl_chips / bb if bb else 0.0
    return f"S{h.seq}/H{h.hand_no} {''.join(h.hole_cards)} {pnl:+.2f}bb"


def write_split_logs(out_dir: Path, categories: dict[str, list[Hand]]) -> None:
    split = out_dir / "拆分日志"
    split.mkdir(parents=True, exist_ok=True)
    for cat, hands in sorted(categories.items()):
        path = split / f"{cat}.log"
        with path.open("w", encoding="utf-8") as fh:
            for h in hands:
                fh.write(f"\n# ===== {h.source}:{h.start_line} S{h.seq}/H{h.hand_no} =====\n")
                fh.write("\n".join(h.lines))
                fh.write("\n")


def write_table_report(path: Path, title: str, rows: list[list[str]], headers: list[str], note: str = "") -> None:
    preserved_analysis = ""
    if path.exists():
        old = path.read_text(encoding="utf-8", errors="replace")
        marker = "\n## 我的判断\n"
        idx = old.find(marker)
        if idx >= 0:
            table_idx = old.find("\n| ", idx)
            if table_idx >= 0:
                preserved_analysis = old[idx:table_idx].strip() + "\n\n"
    with path.open("w", encoding="utf-8") as fh:
        fh.write(f"# {title}\n\n")
        if note:
            fh.write(note.rstrip() + "\n\n")
        fh.write(f"共 {len(rows)} 手。\n\n")
        if preserved_analysis:
            fh.write(preserved_analysis)
        if not rows:
            return
        fh.write("| " + " | ".join(headers) + " |\n")
        fh.write("|" + "|".join(["---"] * len(headers)) + "|\n")
        for row in rows:
            fh.write("| " + " | ".join(md_escape(x) for x in row) + " |\n")


def report_fold_category(out_dir: Path, cat: str, hands: list[Hand], bb: int) -> None:
    rows: list[list[str]] = []
    for h in hands:
        d = h.last_decision
        win_bucket, evidence = win_bucket_for_fold(h)
        rows.append([
            hand_label(h, bb),
            CN_STREET.get(d.street, d.street) if d else "",
            d.branch if d else "",
            d.gate if d else "",
            d.candidates if d else "",
            win_bucket,
            evidence,
            h.winner_part or "",
            h.hero_final_text or "",
        ])
    write_table_report(
        out_dir / f"{cat}.md",
        f"{cat} 分析",
        rows,
        ["手", "弃牌街", "分支", "门/拦截", "候选", "如果看到摊牌", "证据", "赢家", "我最终牌型"],
        "这里的“如果看到摊牌”只回答结果层面能不能赢，不等价于当时 call 一定正确。",
    )


def report_showdown_category(out_dir: Path, cat: str, hands: list[Hand], bb: int) -> None:
    rows: list[list[str]] = []
    for h in hands:
        d = h.last_decision
        rows.append([
            hand_label(h, bb),
            CN_STREET.get(d.street, d.street) if d else "",
            d.action if d else "",
            d.branch if d else "",
            d.candidates if d else "",
            h.winner_part,
            h.hero_final_text,
        ])
    write_table_report(
        out_dir / f"{cat}.md",
        f"{cat} 分析",
        rows,
        ["手", "最后决策街", "最后动作", "分支", "候选", "赢家", "我最终牌型"],
    )


def report_pnl_category(out_dir: Path, cat: str, hands: list[Hand], bb: int, outcome_map: dict[int, str]) -> None:
    rows: list[list[str]] = []
    for h in sorted(hands, key=lambda x: x.hero_pnl_chips):
        d = h.last_decision
        rows.append([
            hand_label(h, bb),
            outcome_map.get(h.seq, ""),
            CN_STREET.get(d.street, d.street) if d else "",
            d.action if d else "",
            d.branch if d else "",
            d.gate if d else "",
            h.winner_part,
            h.hero_final_text,
        ])
    write_table_report(
        out_dir / f"{cat}.md",
        f"{cat} 分析",
        rows,
        ["手", "结局类", "最后街", "动作", "分支", "门/拦截", "赢家", "我最终牌型"],
    )


def report_special(out_dir: Path, hands: list[tuple[Hand, dict]], bb: int) -> None:
    rows: list[list[str]] = []
    for h, info in hands:
        rows.append([
            hand_label(h, bb),
            info["winner"],
            info["winner_hole"],
            f"{info['river_win']}/{info['river_total']} = {info['river_prob']:.1%}",
            f"{info['flop_to_river_prob']:.1%}",
            h.winner_part,
            h.hero_final_text,
        ])
    write_table_report(
        out_dir / "11_特殊_转牌领先河牌被反杀.md",
        "11 特殊类：摊牌输了，hero 一直领先到转牌，河牌被反杀",
        rows,
        ["手", "反杀对手", "对手底牌", "河牌反杀概率", "翻牌到河牌反杀概率", "赢家", "我最终牌型"],
        "只统计有对手亮牌数据的摊牌手；河牌概率按转牌后已知 hero 手牌、对手手牌、4 张公共牌枚举 44 张未知河牌。",
    )


def write_summary(
    out_dir: Path,
    log_path: Path,
    hands: list[Hand],
    bb: int,
    outcome_categories: dict[str, list[Hand]],
    pnl_categories: dict[str, list[Hand]],
    special: list[tuple[Hand, dict]],
) -> None:
    with (out_dir / "汇总.md").open("w", encoding="utf-8") as fh:
        fh.write("# 日志拆分类汇总\n\n")
        fh.write(f"- 源日志：`{log_path}`\n")
        fh.write(f"- 推断 BB：{bb}\n")
        fh.write(f"- 完整手数：{sum(1 for h in hands if h.complete)} / 读取手数：{len(hands)}\n")
        fh.write(f"- 未完成/未覆盖审计：{len(outcome_categories.get('00_审计_未参与或未完成', []))} 手\n\n")

        fh.write("## 1-6 决策结局组\n\n")
        fh.write("| 类别 | 手数 | 净 BB |\n|---|---:|---:|\n")
        for cat in sorted(outcome_categories):
            hs = outcome_categories[cat]
            net = sum(h.hero_pnl_chips for h in hs) / bb if bb else 0.0
            fh.write(f"| {cat} | {len(hs)} | {net:+.2f} |\n")

        fh.write("\n## 7-10 盈亏组\n\n")
        fh.write("| 类别 | 手数 | 净 BB |\n|---|---:|---:|\n")
        for cat in sorted(pnl_categories):
            hs = pnl_categories[cat]
            net = sum(h.hero_pnl_chips for h in hs) / bb if bb else 0.0
            fh.write(f"| {cat} | {len(hs)} | {net:+.2f} |\n")

        fh.write("\n## 11 特殊反杀\n\n")
        fh.write(f"- 符合“摊牌输了且 hero 领先到转牌、河牌被反杀”的可验证样本：{len(special)} 手。\n")
        if special:
            avg = sum(info["river_prob"] for _, info in special) / len(special)
            fh.write(f"- 平均河牌反杀概率：{avg:.1%}\n")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("log", type=Path)
    ap.add_argument("--hero", default="")
    ap.add_argument("--out-dir", type=Path, default=Path("docs/log_hand_split_latest"))
    ap.add_argument("--bb", type=int, default=0)
    args = ap.parse_args()

    all_lines = args.log.read_text(encoding="utf-8", errors="replace").splitlines()
    hero = args.hero or identify_hero_from_lines(all_lines)
    hands = list(iter_hands(args.log, hero))
    bb = args.bb or infer_big_blind(hands)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    for legacy in (
        "summary.md",
        "03_turn_fold.md",
        "04_river_fold.md",
        "05_showdown_win.md",
        "06_showdown_loss.md",
        "07_big_loss_20bb_plus.md",
        "08_small_loss_under_20bb.md",
        "09_small_win_under_20bb.md",
        "10_big_win_20bb_plus.md",
        "11_suckout_after_turn_lead.md",
    ):
        old = args.out_dir / legacy
        if old.exists():
            old.unlink()
    for split_dir in (args.out_dir / "split_logs", args.out_dir / "拆分日志"):
        if split_dir.exists():
            shutil.rmtree(split_dir)

    outcome_categories: dict[str, list[Hand]] = {}
    outcome_map: dict[int, str] = {}
    for h in hands:
        oc = outcome_category_1_6(h)
        outcome_categories.setdefault(oc, []).append(h)
        outcome_map[h.seq] = oc

    special: list[tuple[Hand, dict]] = []
    for h in outcome_categories.get("06_摊牌失败", []):
        info = exact_suckout_info(h)
        if info and info["river_prob"] <= 0.15:
            special.append((h, info))
    special_seq = {h.seq for h, _ in special}

    pnl_categories: dict[str, list[Hand]] = {}
    pnl_categories["11_特殊_转牌领先河牌被反杀_不计入大小盈亏"] = [h for h, _ in special]
    for h in hands:
        if h.seq in special_seq:
            continue
        pc = pnl_category_7_10(h, bb)
        pnl_categories.setdefault(pc, []).append(h)

    write_split_logs(args.out_dir, {**outcome_categories, **{f"盈亏_{k}": v for k, v in pnl_categories.items()}, "11_特殊_转牌领先河牌被反杀": [h for h, _ in special]})
    write_summary(args.out_dir, args.log, hands, bb, outcome_categories, pnl_categories, special)

    for cat in ("03_转牌弃牌", "04_河牌弃牌"):
        report_fold_category(args.out_dir, cat, outcome_categories.get(cat, []), bb)
    for cat in ("05_摊牌胜利", "06_摊牌失败"):
        report_showdown_category(args.out_dir, cat, outcome_categories.get(cat, []), bb)
    for cat in ("07_大亏_20bb以上", "08_小亏_20bb以内", "09_小赢_20bb以内", "10_大赢_20bb以上"):
        report_pnl_category(args.out_dir, cat, pnl_categories.get(cat, []), bb, outcome_map)
    report_special(args.out_dir, special, bb)

    print(f"hero={hero}")
    print(f"bb={bb}")
    print(f"hands={len(hands)} complete={sum(1 for h in hands if h.complete)}")
    print(f"out={args.out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
