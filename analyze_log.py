#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
分析 pokerfate_console.bak.log 两段对局数据
Session 1: 第1手 ~ 第68手
Session 2: 第70手 ~ 第114手
"""

import re
from collections import defaultdict

LOG_FILE = "/Users/zhangmingli/dev-tool/PokerFate/pokerfate/logs/pokerfate_console.bak.log"
BOT = "HERO_NAME"
BB = 1000


def read_log():
    with open(LOG_FILE, encoding="utf-8") as f:
        return f.readlines()


def strip_time(line):
    """去掉行首时间戳"""
    return re.sub(r"^\[\d{2}:\d{2}:\d{2}\]\s*", "", line)


def parse_log(lines):
    """
    把日志按"手"拆分，每手记录原始行列表。
    返回: dict {hand_no: [lines...]}
    """
    hands = {}
    current_hand = None
    current_lines = []

    hand_header_re = re.compile(r"第\s*(\d+)\s*手\s+")

    for line in lines:
        s = strip_time(line)
        m = hand_header_re.search(s)
        if m and "━" in lines[lines.index(line) - 1] if lines.index(line) > 0 else False:
            # 检查上一行是否是分隔线
            pass
        # 更稳健：检查行本身包含 "第 N 手" 并且同行有玩家信息
        if m and ("bb" in s or "BB" in s):
            if current_hand is not None:
                hands[current_hand] = current_lines
            current_hand = int(m.group(1))
            current_lines = [line]
        elif current_hand is not None:
            current_lines.append(line)

    if current_hand is not None:
        hands[current_hand] = current_lines

    return hands


def get_players_in_hand(hand_lines):
    """从手的第一行提取本手玩家列表"""
    header = strip_time(hand_lines[0])
    # 格式: 第 N 手  玩家1(标签) Xbb []  玩家2...
    # 提取所有 "名字(xxx) Xbb" 或 "名字 Xbb"
    players = re.findall(r"(\S+?)(?:\([^)]*\))?\s+\d+bb", header)
    return players


def parse_hand(hand_no, hand_lines):
    """
    解析单手数据，返回 dict：
    - bot_participated: bool
    - hole_cards: str (如 AKo)
    - position: str
    - facing: str (none/open/3bet)
    - bot_preflop_action: str
    - greenline: str
    - pnl_chips: int (盈亏 chips，正数=赢，负数=输)
    - players: list[str]
    """
    result = {
        "hand_no": hand_no,
        "bot_participated": False,
        "hole_cards": "",
        "position": "",
        "facing": "none",
        "bot_preflop_action": "",
        "greenline": "",
        "pnl_chips": 0,
        "players": [],
    }

    result["players"] = get_players_in_hand(hand_lines)

    # 查找 bot 是否有底牌
    gto_preflop_lines = []  # 收集所有翻前GTO行（有些手有多个，如先开加后被3bet）
    greenline_line = None
    result_line = None

    i = 0
    while i < len(hand_lines):
        s = strip_time(hand_lines[i])

        # 底牌
        if s.startswith("底牌") and not result["bot_participated"]:
            result["bot_participated"] = True

        # GTO翻前行（收集所有）
        if "【GTOv2·翻前】" in s:
            gto_preflop_lines.append(s)
            greenline_line = None  # 每次新的GTOv2翻前行重置greenline

        # Greenline 行（跟随最近一个GTOv2翻前行，取第一个）
        if "📊 [Greenline]" in s and gto_preflop_lines and greenline_line is None:
            greenline_line = s

        # ✔ 结果行
        if s.startswith("✔"):
            result_line = s

        i += 1

    if not result["bot_participated"]:
        return result

    # 位置从第一个GTO翻前行提取，facing/action从最后一个提取
    gto_first = gto_preflop_lines[0] if gto_preflop_lines else None
    gto_last = gto_preflop_lines[-1] if gto_preflop_lines else None
    gto_preflop_line = gto_last  # 主要解析用最后一个

    # 解析 GTO翻前行
    if gto_preflop_line:
        # 格式: 【GTOv2·翻前】 AKo BTN 无开牌→开加 胜率X%
        # 或:   【GTOv2·翻前】 72o BB免费看牌（无人入局）过牌 胜率X%
        # 提取底牌
        m = re.search(r"【GTOv2·翻前】\s+(\S+?)\s+", gto_preflop_line)
        if m:
            result["hole_cards"] = m.group(1)

        # 提取位置：优先从第一个GTO翻前行（包含初始位置）
        pos_source = gto_first if gto_first else gto_preflop_line
        pos_m = re.search(
            r"【GTOv2·翻前】\s+\S+\s+(UTG\+?\d?|MP|CO|BTN|SB|BB|HJ|LJ|UTG)\s*",
            pos_source,
        )
        if pos_m:
            result["position"] = pos_m.group(1)
        else:
            pos_m2 = re.search(
                r"\s(UTG\+?\d?|MP|CO|BTN|SB|BB|HJ|LJ|UTG)\s+(?:无开牌|面对|免费|0人)",
                pos_source,
            )
            if pos_m2:
                result["position"] = pos_m2.group(1)

        # 提取 facing
        if "面对开加" in gto_preflop_line:
            result["facing"] = "open"
        elif "面对3bet" in gto_preflop_line or "面对re-raise" in gto_preflop_line:
            result["facing"] = "3bet"
        elif "无开牌" in gto_preflop_line or "免费看牌" in gto_preflop_line:
            result["facing"] = "none"
        elif "0人limp→iso" in gto_preflop_line or "limp" in gto_preflop_line.lower():
            result["facing"] = "none"

        # 从推理行提取 bot 翻前动作（最后决策词）
        action_m = re.search(
            r"(弃牌|跟注|加注|开加|过牌|3bet价值|3bet诈唬|3bet|all.in|iso)\s*胜率",
            gto_preflop_line,
        )
        if action_m:
            act = action_m.group(1)
            if act in ("开加", "iso"):
                act = "加注"
            elif "3bet" in act:
                act = "3bet"
            result["bot_preflop_action"] = act

    # Greenline 解析
    if greenline_line:
        m = re.search(r"📊 \[Greenline\]\s+(.+?)→\s*(\S+)", greenline_line)
        if m:
            situation = m.group(1).strip()
            advice = m.group(2).strip()
            result["greenline"] = f"{situation}→ {advice}"
        else:
            result["greenline"] = greenline_line.strip()

    # 从 ✔ 行读取 bot 盈亏
    if result_line:
        # 格式: 本手 +/-X
        pnl_m = re.search(r"本手\s+([+-]\d+)", result_line)
        if pnl_m:
            result["pnl_chips"] = int(pnl_m.group(1))

    return result


def determine_gto_mismatch(hand_data):
    """
    判断是否 GTO 不符：
    - Greenline 建议 raise 但 bot 弃牌/跟注 → 不符
    - Greenline 建议 fold 但 bot 跟注/加注 → 不符
    - Greenline 建议 call 但 bot 弃牌 → 不符（宽松判断）
    - Greenline 建议 — 时不判断
    """
    gl = hand_data["greenline"].lower()
    act = hand_data["bot_preflop_action"]

    if "→ —" in hand_data["greenline"] or "→—" in hand_data["greenline"]:
        return ""

    advice = ""
    if "→ raise" in gl or "→raise" in gl:
        advice = "raise"
    elif "→ fold" in gl or "→fold" in gl:
        advice = "fold"
    elif "→ call" in gl or "→call" in gl:
        advice = "call"

    if not advice:
        return ""

    if advice == "raise" and act in ("弃牌", "跟注"):
        return "⚠"
    if advice == "fold" and act in ("跟注", "加注"):
        return "⚠"
    if advice == "call" and act == "弃牌":
        return "⚠"

    return ""


def analyze_opponents(session_hands):
    """
    统计每个对手的对局次数和 bot 净盈亏
    """
    opponent_count = defaultdict(int)
    opponent_pnl = defaultdict(int)

    for h in session_hands:
        if not h["bot_participated"]:
            continue
        for p in h["players"]:
            if p != BOT:
                opponent_count[p] += 1
                opponent_pnl[p] += h["pnl_chips"]

    # 过滤出现次数 > 3 的对手
    result = {}
    for opp, cnt in opponent_count.items():
        if cnt > 3:
            result[opp] = {"count": cnt, "pnl_chips": opponent_pnl[opp]}
    return result


def print_preflop_table(session_hands, session_name):
    print(f"\n## {session_name} - A. 翻前决策表\n")
    print("| 手# | 底牌 | 位置 | Facing | Bot行动 | Greenline建议 | 盈亏(bb) | GTO不符? |")
    print("|-----|------|------|--------|---------|---------------|----------|----------|")

    for h in session_hands:
        if not h["bot_participated"]:
            continue
        hand_no = h["hand_no"]
        hole = h["hole_cards"] or "?"
        pos = h["position"] or "?"
        facing = h["facing"]
        act = h["bot_preflop_action"] or "?"
        gl = h["greenline"] or "—"
        # 只取 → 后面的建议部分
        if "→" in gl:
            gl_short = gl.split("→")[-1].strip()
        else:
            gl_short = gl

        pnl_bb = h["pnl_chips"] / BB
        pnl_str = f"{pnl_bb:+.1f}"
        mismatch = determine_gto_mismatch(h)

        print(f"| {hand_no} | {hole} | {pos} | {facing} | {act} | {gl_short} | {pnl_str} | {mismatch} |")


def print_opponent_table(session_hands, session_name):
    print(f"\n## {session_name} - B. 对手盈亏汇总\n")
    print("| 对手 | 对局次数 | bot净盈亏(bb) |")
    print("|------|----------|--------------|")

    opp_data = analyze_opponents(session_hands)
    # 按对局次数排序
    for opp, d in sorted(opp_data.items(), key=lambda x: -x[1]["count"]):
        pnl_bb = d["pnl_chips"] / BB
        print(f"| {opp} | {d['count']} | {pnl_bb:+.1f} |")


def print_session_stats(session_hands, session_name, start_chips, end_chips):
    total_hands = len(session_hands)
    bot_hands = sum(1 for h in session_hands if h["bot_participated"])
    net_chips = end_chips - start_chips
    net_bb = net_chips / BB

    print(f"\n## {session_name} - C. Session 统计\n")
    print(f"- 总手数：{total_hands}")
    print(f"- Bot 参与手数：{bot_hands}")
    print(f"- 起始筹码：{start_chips // BB}bb ({start_chips} chips)")
    print(f"- 结束筹码：{end_chips // BB}bb ({end_chips} chips)")
    print(f"- 净盈亏：{net_bb:+.1f}bb ({net_chips:+} chips)")


def main():
    lines = read_log()
    hands_raw = parse_log(lines)

    # Session 1: 手1~68
    session1_hand_nos = [n for n in sorted(hands_raw.keys()) if 1 <= n <= 68]
    # Session 2: 手70~114
    session2_hand_nos = [n for n in sorted(hands_raw.keys()) if 70 <= n <= 114]

    # 解析每手
    session1_hands = [parse_hand(n, hands_raw[n]) for n in session1_hand_nos]
    session2_hands = [parse_hand(n, hands_raw[n]) for n in session2_hand_nos]

    # --- Session 1 统计 ---
    print_preflop_table(session1_hands, "Session 1 (手1~68)")
    print_opponent_table(session1_hands, "Session 1 (手1~68)")
    # Session 1: 起始100bb，结束0（破产）
    print_session_stats(session1_hands, "Session 1 (手1~68)", 100 * BB, 0)

    # --- Session 2 统计 ---
    print_preflop_table(session2_hands, "Session 2 (手70~114)")
    print_opponent_table(session2_hands, "Session 2 (手70~114)")
    # Session 2: 起始100bb，结束从最后一行 ✔ 行的HERO_NAME筹码读取
    # 找最后一手的 ✔ 行
    last_hand_lines = hands_raw.get(114, [])
    end_chips_s2 = 100 * BB
    for line in last_hand_lines:
        s = strip_time(line)
        if s.startswith("✔") and BOT in s:
            m = re.search(rf"{BOT}\s+(\d+)", s)
            if m:
                end_chips_s2 = int(m.group(1))
    print_session_stats(session2_hands, "Session 2 (手70~114)", 100 * BB, end_chips_s2)

    # 额外：打印解析到的手数，便于 debug
    print(f"\n---\n> 日志共解析到手数：{len(hands_raw)}，Session1={len(session1_hand_nos)}手，Session2={len(session2_hand_nos)}手")
    print(f"> Session1 bot参与：{sum(1 for h in session1_hands if h['bot_participated'])}手")
    print(f"> Session2 bot参与：{sum(1 for h in session2_hands if h['bot_participated'])}手")


if __name__ == "__main__":
    main()
