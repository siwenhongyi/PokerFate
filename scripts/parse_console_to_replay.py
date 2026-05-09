"""把 PokerFate 的 console 文本日志转成 replay JSONL。

console 日志格式（人类可读）：
    [HH:MM:SS]   第 N 手   <hero> <stack>bb [] ...
    [HH:MM:SS]   底牌  Qd Jd
    [HH:MM:SS]   ── 翻牌前 ─...
    [HH:MM:SS]     <opp> 跟注 [鲸鱼/PWI+...] range 67%
    [HH:MM:SS]   ► <hero> 加注 5     胜率 28%(vs随机36%) SPR≈12.4 [range_v2]   底池 8000
    [HH:MM:SS]   ── 翻牌  4♣ Q♦ K♦  底池 2500 ──
    [HH:MM:SS]   ✔ <name>[<hand_type>] 赢得 X    本手 ±Y  [我: ...] │ <name> stack ...

输出 JSONL 每行一手：
    {"hand": N, "players": [...], "hole_cards": [...], "events": [...], "result": {...}}

用法：
    python -m scripts.parse_console_to_replay \\
        --log pokerfate/logs/pokerfate_console.bak.log \\
        --log pokerfate/logs/pokerfate_console.log \\
        --out data/calibration_replays/replay_latest.jsonl \\
        --source-label latest_console

注意单位：日志里所有筹码数字都是 chips（不是 BB）。replay 也用 chips。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Optional
from scripts.hero_name import load_hero_name

# Windows 兜底：强制 stdout/stderr UTF-8
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except (AttributeError, OSError):
        pass

TS_RE = re.compile(r"^\[(\d{2}:\d{2}:\d{2})\]\s?(.*)$")
HAND_HEADER_RE = re.compile(r"第\s*(\d+)\s*手")
HOLE_RE = re.compile(r"底牌\s+(\S+)\s+(\S+)")
STREET_RE = re.compile(r"──\s*(翻牌前|翻牌|转牌|河牌)(?:\s+(.+?))?\s*(?:底池\s+(\d+))?\s*──")
BOARD_CARD_RE = re.compile(r"[2-9TJQKA][♠♥♦♣]")
PLAYER_TOKEN_RE = re.compile(r"(\S+?)(?:\(([^)]+)\))?\s+(\d+)bb\s+\[\]")
SUITS = {"♠": "s", "♥": "h", "♦": "d", "♣": "c"}

HERO_DECISION_RE = re.compile(
    r"►\s*(\S+)\s+(弃牌|过牌|跟注|加注|下注|全下)"
    r"(?:\s+(\d+))?"
    r".*?胜率\s*(\d+)%(?:\(vs随机(\d+)%\))?"
    r"\s+SPR\s*[≈=]?\s*([\d.]+)"
    r"\s+\[(\w+)\]"
    r"(?:\s+底池\s+(\d+))?"
)

OPP_ACTION_RE = re.compile(
    r"^\s{2,}(\S+)\s+(弃牌|过牌|跟注|加注|下注|全下)"
    r"(?:\s+(\d+)bb(?:\s+\(\d+bb\s+([\d.]+)x\s+pot\))?)?"
    r".*?(?:\[([^/\]]+)(?:/PWI[+-]?\d+)?\])?"
    r"(?:.*?range\s+(\d+)%(?:\s+\[([^\]]+)\])?)?"
)

# 结算行：✔ <name>[<hand_type>] 赢得 X 本手 ±Y [我: ...] │ <stacks>
HAND_RESULT_RE = re.compile(
    r"✔\s*(.+?)\s*\[([^\]]*)\]\s*赢得\s*(\d+)"
    r"\s+本手\s*([+-]?\d+)"
)
LEARNER_RE = re.compile(
    r"◈\s+学习\s+(.+?)\s+"
    r"([2-9TJQKA][♠♥♦♣])\s+([2-9TJQKA][♠♥♦♣])"
)
# 结算行末尾的最终筹码（│ name X  name Y ...）
FINAL_STACKS_RE = re.compile(r"│\s*(.+)$")
PLAYER_STACK_RE = re.compile(r"(\S+?)\s+(\d+)(?:\s|$)")

ACTION_MAP = {"弃牌": "fold", "过牌": "check", "跟注": "call",
              "加注": "raise", "下注": "bet", "全下": "jam"}

BUCKET_TRANSLATE = {
    "空气": "air", "弱听": "weak_draw", "弱": "weak", "中": "medium",
    "强": "strong", "听牌": "draw", "坚果": "nuts", "听": "draw"
}

PTYPE_TRANSLATE = {
    "鲸鱼": "whale", "鱼": "fish", "超松被动": "whale", "跟注站": "whale",
    "紧手": "nit", "激进": "lag", "疯狂": "maniac", "规则": "reg",
}


def parse_cards_str(s: str) -> list[str]:
    """'Q♦ J♦' / 'Qd Jd' / 'Qd,Jd' → ['Qd','Jd']."""
    out = []
    for tok in re.findall(r"([2-9TJQKA])([♠♥♦♣scdh])", s):
        rank, suit = tok
        out.append(rank + (SUITS.get(suit, suit)))
    return out


def parse_bucket_dist(s: str) -> dict[str, float]:
    out = {}
    for part in s.split("/"):
        m = re.match(r"([一-龥]+)(\d+)%", part.strip())
        if m:
            name = BUCKET_TRANSLATE.get(m.group(1), m.group(1))
            out[name] = int(m.group(2)) / 100.0
    return out


def translate_ptype(tag: str) -> str:
    if not tag:
        return ""
    for cn, en in PTYPE_TRANSLATE.items():
        if cn in tag:
            return en
    if "数据不足" in tag or "未知" in tag:
        return ""
    return tag


def parse_log(log_path: Path, hero_name: str, bb_value: int = 1000) -> list[dict]:
    """把 console log 切成手数列表，每手一个 dict。"""
    lines = log_path.read_text(encoding='utf-8', errors='replace').split("\n")
    hands: list[dict] = []

    cur: Optional[dict] = None
    cur_street = "preflop"
    name_to_id: dict[str, int] = {}
    next_pid = 0
    folded_in_hand: set[str] = set()
    last_hand_no = 0
    session_id = 0

    def assign_pid(name: str) -> int:
        nonlocal next_pid
        if name not in name_to_id:
            name_to_id[name] = next_pid
            next_pid += 1
        return name_to_id[name]

    def reset_session():
        """新 session 时重置 player_id 映射，避免跨 session 累积让 replay 引擎
        内部状态膨胀（bayesian_range_tracker / opponent stats 都按 pid 追踪）。"""
        nonlocal name_to_id, next_pid
        name_to_id = {}
        next_pid = 0

    def finish_hand():
        nonlocal cur
        if cur is not None and cur.get("events"):
            hands.append(cur)
        cur = None

    for raw in lines:
        m_ts = TS_RE.match(raw)
        text = m_ts.group(2) if m_ts else raw

        # 手开始
        m = HAND_HEADER_RE.search(text)
        if m:
            finish_hand()
            hand_no = int(m.group(1))
            # 检测 session 边界：hand_no 突然回到 1（或下降）→ 新 session
            if hand_no == 1 and last_hand_no > 1:
                session_id += 1
                reset_session()
            last_hand_no = hand_no
            cur_street = "preflop"
            folded_in_hand = set()

            # 解析玩家 + 起始筹码
            players = []
            tail = text[m.end():]
            for pm in PLAYER_TOKEN_RE.finditer(tail):
                pname, ptype_raw, stack_bb = pm.group(1), pm.group(2) or "", int(pm.group(3))
                pid = assign_pid(pname)
                players.append({
                    "id": pid,
                    "name": pname,
                    "stack": stack_bb * bb_value,
                    "pos": "",
                    "player_type": translate_ptype(ptype_raw) if pname != hero_name else "",
                })
            cur = {
                "hand": hand_no,
                "session": session_id,
                "dealer_id": 0,
                "players": players,
                "hole_cards": [],
                "events": [],
                "result": {},
            }
            continue

        if cur is None:
            continue

        # 底牌
        m = HOLE_RE.search(text)
        if m:
            cards = parse_cards_str(m.group(1) + " " + m.group(2))
            cur["hole_cards"] = cards
            continue

        # 街切换
        m = STREET_RE.search(text)
        if m:
            label = m.group(1)
            cur_street = {"翻牌前": "preflop", "翻牌": "flop",
                          "转牌": "turn", "河牌": "river"}[label]
            if cur_street in ("flop", "turn", "river"):
                # 板牌
                body = text[m.start():m.end()]
                board_now = parse_cards_str(body)
                if cur_street == "flop":
                    new_cards = board_now
                else:
                    # turn/river 的 board_now 包含全部出来的牌，找出新增那一张
                    seen = set()
                    for ev in cur["events"]:
                        if ev.get("type") == "board":
                            for c in ev.get("cards", []):
                                seen.add(c)
                    new_cards = [c for c in board_now if c not in seen]
                cur["events"].append({
                    "type": "board",
                    "street": cur_street,
                    "cards": new_cards,
                })
            continue

        # hero 决策
        stripped = text.lstrip()
        if stripped.startswith("►"):
            h = HERO_DECISION_RE.search(text)
            if h and h.group(1) == hero_name:
                action_cn = h.group(2)
                amount = int(h.group(3)) if h.group(3) else 0
                eq_pct = int(h.group(4))
                vs_random = int(h.group(5)) if h.group(5) else eq_pct
                spr = float(h.group(6))
                engine = h.group(7)
                pot = int(h.group(8)) if h.group(8) else 0
                # to_call 难以从 console 直接拿，用 hero 跟注 amount 作 fallback
                # （call 时 amount=to_call；其它情况用上一个 opp_action 的 amount）
                to_call = 0
                if action_cn == "跟注":
                    to_call = amount
                else:
                    # 找当前街最后一个 opp action 的 amount 作 to_call proxy
                    for ev in reversed(cur["events"]):
                        if ev.get("type") == "opp_action" and ev.get("street") == cur_street:
                            if ev.get("amount", 0) > 0:
                                to_call = ev["amount"]
                            break
                cur["events"].append({
                    "type": "decision",
                    "street": cur_street,
                    "action": ACTION_MAP.get(action_cn, action_cn),
                    "amount": float(amount),
                    "pot": pot,
                    "to_call": float(to_call),
                    "equity": eq_pct / 100.0,
                    "equity_random": vs_random / 100.0,
                    "equity_mode": engine,
                    "spr": spr,
                })
            continue

        # opponent action
        m = OPP_ACTION_RE.match(text)
        if m:
            opp_name = m.group(1)
            if opp_name == hero_name or opp_name in folded_in_hand:
                continue
            action_cn = m.group(2)
            amount_bb = int(m.group(3)) if m.group(3) else 0
            type_tag = m.group(5)
            range_pct_raw = m.group(6)
            bucket_raw = m.group(7)

            pid = assign_pid(opp_name)
            ev = {
                "type": "opp_action",
                "pid": pid,
                "name": opp_name,
                "action": ACTION_MAP.get(action_cn, action_cn),
                "amount": amount_bb * bb_value if amount_bb else 0,
                "street": cur_street,
                "bucket_dist": parse_bucket_dist(bucket_raw) if bucket_raw else None,
                "range_pct": int(range_pct_raw) / 100.0 if range_pct_raw else 1.0,
                "player_type": translate_ptype(type_tag),
            }
            cur["events"].append(ev)

            if action_cn == "弃牌":
                folded_in_hand.add(opp_name)
            continue

        # Range V2 showdown learner line after the result contains revealed
        # villain hole cards. Keep the hand open until the next header so
        # replay can feed showdown_hands back into calibration.
        m = LEARNER_RE.search(text)
        if m and cur.get("result"):
            pname = m.group(1).strip()
            cards = parse_cards_str(m.group(2) + " " + m.group(3))
            if len(cards) == 2:
                cur["result"].setdefault("showdown_hands", {})[pname] = cards
            continue

        # hand result
        m = HAND_RESULT_RE.search(text)
        if m:
            winner_str = m.group(1).strip()
            hand_type = m.group(2)
            pot_won = int(m.group(3))
            my_delta = int(m.group(4))
            cur["result"] = {
                "winners": [w.strip() for w in winner_str.split("&")],
                "winner_hand_type": hand_type,
                "pot": pot_won,
                "my_delta": my_delta,
                "final_stacks": {},
                "showdown_hands": {},
            }
            # 解析最终筹码
            tail_m = FINAL_STACKS_RE.search(text)
            if tail_m:
                for sm in PLAYER_STACK_RE.finditer(tail_m.group(1)):
                    pname, stack = sm.group(1), int(sm.group(2))
                    cur["result"]["final_stacks"][pname] = stack
            continue

    finish_hand()
    return hands


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--log", action="append", required=True,
                    help="console log file; can be passed multiple times")
    ap.add_argument("--out", required=True, help="replay JSONL output")
    ap.add_argument("--bb-value", type=int, default=1000,
                    help="chips per BB (default 1000)")
    ap.add_argument("--source-label", default="",
                    help="single source_log label written to every hand")
    args = ap.parse_args()
    try:
        hero_name = load_hero_name()
    except RuntimeError as exc:
        ap.error(str(exc))

    hands = []
    for log in args.log:
        parsed = parse_log(Path(log), hero_name, args.bb_value)
        source = args.source_label or str(log)
        for h in parsed:
            h["source_log"] = source
        hands.extend(parsed)

    with open(args.out, "w", encoding='utf-8') as f:
        for h in hands:
            f.write(json.dumps(h, ensure_ascii=False) + "\n")

    print(f"解析 {len(hands)} 手 → {args.out}")
    decisions = sum(1 for h in hands for ev in h.get("events", []) if ev.get("type") == "decision")
    print(f"  决策点：{decisions}")
    if hands:
        print(f"  hand_no 范围：{min(h['hand'] for h in hands)} - {max(h['hand'] for h in hands)}")
        sources = sorted({h.get('source_log', '') for h in hands})
        print(f"  source_log：{', '.join(sources)}")


if __name__ == "__main__":
    main()
