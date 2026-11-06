#!/usr/bin/env python3
"""Stream-count PokerFate strategy branches and candidates by stack depth and SPR."""

from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.hero_name import load_hero_names


TS_RE = re.compile(r"^\[\d{2}:\d{2}:\d{2}\]\s*")
HAND_RE = re.compile(r"第\s*(\d+)\s*手\s+(.*)$")
STREET_RE = re.compile(r"──\s*(翻牌前|翻牌|转牌|河牌)")
HERO_ACTION_RE = re.compile(r"►\s*(?P<name>.+?)\s+(?P<action>弃牌|过牌|跟注|加注|下注|全下)(?P<rest>.*)$")
SPR_RE = re.compile(r"SPR\s*[≈=]?\s*(\d+(?:\.\d+)?)")
ENGINE_RE = re.compile(r"\[([A-Za-z0-9_]+)\]")
BRANCH_RE = re.compile(r"分支=([^│]+)")
CAND_RE = re.compile(r"候选:\s*([^│]+)")
CAND_ITEM_RE = re.compile(r"([A-Za-z][A-Za-z0-9_]*)(?:\[\d+%\])?")

STREET_MAP = {
    "翻牌前": "preflop",
    "翻牌": "flop",
    "转牌": "turn",
    "河牌": "river",
}


@dataclass(frozen=True)
class PendingDecision:
    hand_no: int | None
    line_no: int
    stack_bb: float | None
    spr: float | None
    street: str
    engine: str


@dataclass
class BucketStat:
    hero_decisions: int = 0
    strategy_decisions: int = 0
    triggered: Counter[str] = field(default_factory=Counter)
    candidates: Counter[str] = field(default_factory=Counter)
    candidate_triggered: Counter[str] = field(default_factory=Counter)


@dataclass
class Summary:
    hands: int = 0
    hero_decisions: int = 0
    strategy_decisions: int = 0
    by_stack: dict[str, BucketStat] = field(default_factory=dict)
    by_spr: dict[str, BucketStat] = field(default_factory=dict)
    by_stack_spr: dict[str, BucketStat] = field(default_factory=dict)


def strip_ts(line: str) -> str:
    return TS_RE.sub("", line.rstrip("\n"))


def load_hero_aliases(hero: str | None) -> tuple[str, ...]:
    if hero:
        return (hero.strip(),)
    return load_hero_names().all_names


def parse_stack_bb(header_tail: str, hero_aliases: Iterable[str]) -> float | None:
    for hero in sorted((h for h in hero_aliases if h), key=len, reverse=True):
        m = re.search(rf"(?:^|\s){re.escape(hero)}(?:\([^)]*\))?\s+(\d+(?:\.\d+)?)bb\s+\[\]", header_tail)
        if m:
            return float(m.group(1))
    return None


def parse_hero_decision(text: str, hero_aliases: set[str]) -> tuple[float | None, str] | None:
    if "►" not in text:
        return None
    m = HERO_ACTION_RE.search(text)
    if not m or m.group("name").strip() not in hero_aliases:
        return None
    spr_m = SPR_RE.search(text)
    engine_m = ENGINE_RE.search(text)
    spr = float(spr_m.group(1)) if spr_m else None
    engine = engine_m.group(1) if engine_m else ""
    return spr, engine


def normalize_branch(raw: str) -> str:
    branch = raw.strip().split()[0]
    branch = branch.split("→", 1)[0]
    return branch.strip()


def parse_candidates(text: str) -> set[str]:
    m = CAND_RE.search(text)
    if not m:
        return set()
    return {item.group(1) for item in CAND_ITEM_RE.finditer(m.group(1))}


def stack_bucket(stack_bb: float | None, step: int) -> str:
    if stack_bb is None:
        return "unknown"
    lower = int(stack_bb // step) * step
    upper = lower + step
    return f"{lower}-{upper}bb"


def parse_spr_edges(raw: str) -> list[float]:
    edges: list[float] = []
    for part in raw.split(","):
        token = part.strip().lower()
        if not token:
            continue
        if token in {"inf", "+inf", "∞"}:
            edges.append(float("inf"))
        else:
            edges.append(float(token))
    if len(edges) < 2:
        raise ValueError("SPR buckets need at least two edges")
    if edges != sorted(edges):
        raise ValueError("SPR bucket edges must be ascending")
    return edges


def fmt_edge(value: float) -> str:
    if value == float("inf"):
        return "∞"
    if value.is_integer():
        return str(int(value))
    return str(value)


def spr_bucket(spr: float | None, edges: list[float]) -> str:
    if spr is None:
        return "unknown"
    for idx in range(len(edges) - 1):
        lo = edges[idx]
        hi = edges[idx + 1]
        if lo <= spr < hi:
            return f"SPR {fmt_edge(lo)}-{fmt_edge(hi)}"
    if spr >= edges[-1]:
        return f"SPR {fmt_edge(edges[-1])}+"
    return f"SPR <{fmt_edge(edges[0])}"


def bucket_sort_key(label: str) -> tuple[float, str]:
    if label == "unknown":
        return (float("inf"), label)
    m = re.search(r"(?:SPR\s*)?(\d+(?:\.\d+)?)", label)
    if m:
        return (float(m.group(1)), label)
    return (float("inf"), label)


def get_bucket(stats: dict[str, BucketStat], key: str) -> BucketStat:
    stat = stats.get(key)
    if stat is None:
        stat = BucketStat()
        stats[key] = stat
    return stat


def iter_bucket_stats(summary: Summary, decision: PendingDecision, stack_step: int, spr_edges: list[float]) -> Iterable[BucketStat]:
    stack_key = stack_bucket(decision.stack_bb, stack_step)
    spr_key = spr_bucket(decision.spr, spr_edges)
    yield get_bucket(summary.by_stack, stack_key)
    yield get_bucket(summary.by_spr, spr_key)
    yield get_bucket(summary.by_stack_spr, f"{stack_key} / {spr_key}")


def add_hero_decision(summary: Summary, decision: PendingDecision, stack_step: int, spr_edges: list[float]) -> None:
    summary.hero_decisions += 1
    for stat in iter_bucket_stats(summary, decision, stack_step, spr_edges):
        stat.hero_decisions += 1


def add_strategy_decision(
    summary: Summary,
    decision: PendingDecision,
    branch: str,
    candidates: set[str],
    stack_step: int,
    spr_edges: list[float],
) -> None:
    summary.strategy_decisions += 1
    for stat in iter_bucket_stats(summary, decision, stack_step, spr_edges):
        stat.strategy_decisions += 1
        if branch:
            stat.triggered[branch] += 1
        for candidate in candidates:
            stat.candidates[candidate] += 1
        if branch in candidates:
            stat.candidate_triggered[branch] += 1


def analyze_log(log_path: Path, hero_aliases: tuple[str, ...], stack_step: int, spr_edges: list[float]) -> Summary:
    summary = Summary()
    hero_set = set(hero_aliases)
    current_stack_bb: float | None = None
    current_hand_no: int | None = None
    current_street = ""
    pending: PendingDecision | None = None

    with log_path.open("r", encoding="utf-8", errors="replace") as fh:
        for line_no, raw in enumerate(fh, start=1):
            text = strip_ts(raw)

            hand_m = HAND_RE.search(text)
            if hand_m:
                summary.hands += 1
                current_hand_no = int(hand_m.group(1))
                current_stack_bb = parse_stack_bb(hand_m.group(2), hero_aliases)
                current_street = "preflop"
                pending = None
                continue

            street_m = STREET_RE.search(text)
            if street_m:
                current_street = STREET_MAP[street_m.group(1)]
                pending = None
                continue

            hero_decision = parse_hero_decision(text, hero_set)
            if hero_decision is not None:
                spr, engine = hero_decision
                pending = PendingDecision(
                    hand_no=current_hand_no,
                    line_no=line_no,
                    stack_bb=current_stack_bb,
                    spr=spr,
                    street=current_street or "unknown",
                    engine=engine,
                )
                add_hero_decision(summary, pending, stack_step, spr_edges)
                continue

            if pending is not None and "分支=" in text:
                branch_m = BRANCH_RE.search(text)
                branch = normalize_branch(branch_m.group(1)) if branch_m else ""
                candidates = parse_candidates(text)
                if branch or candidates:
                    add_strategy_decision(summary, pending, branch, candidates, stack_step, spr_edges)
                pending = None

    return summary


def rate(count: int, denom: int) -> str:
    if denom <= 0:
        return "0/0 0.0%"
    return f"{count}/{denom} {count / denom * 100:.1f}%"


def pick_rate(triggered: int, candidates: int) -> str:
    if candidates <= 0:
        return "-"
    return f"{triggered}/{candidates} {triggered / candidates * 100:.1f}%"


def print_group(title: str, stats: dict[str, BucketStat], strategy_filter: set[str], min_decisions: int, top: int) -> None:
    print(f"\n## {title}")
    print("桶\t策略决策数\t英雄决策数\t策略\t触发\t触发率\t候选\t候选率\t候选后触发")
    for bucket in sorted(stats, key=bucket_sort_key):
        stat = stats[bucket]
        if stat.strategy_decisions < min_decisions:
            continue
        strategies = set(stat.triggered) | set(stat.candidates)
        if strategy_filter:
            strategies &= strategy_filter
        ordered = sorted(
            strategies,
            key=lambda name: (-(stat.triggered[name] + stat.candidates[name]), name),
        )
        if top > 0:
            ordered = ordered[:top]
        for strategy in ordered:
            triggered = stat.triggered[strategy]
            candidates = stat.candidates[strategy]
            candidate_triggered = stat.candidate_triggered[strategy]
            print(
                "\t".join(
                    [
                        bucket,
                        str(stat.strategy_decisions),
                        str(stat.hero_decisions),
                        strategy,
                        str(triggered),
                        rate(triggered, stat.strategy_decisions),
                        str(candidates),
                        rate(candidates, stat.strategy_decisions),
                        pick_rate(candidate_triggered, candidates),
                    ]
                )
            )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--log", type=Path, default=ROOT / "pokerfate" / "logs" / "pokerfate_console.bak.log")
    parser.add_argument("--hero", help="默认读取 data/hero_names.json 的 current 和 aliases")
    parser.add_argument("--stack-step", type=int, default=10, help="筹码深度分桶宽度，默认 10bb")
    parser.add_argument("--spr-buckets", default="0,1,2,4,8,12,20,inf", help="SPR 分桶边界，逗号分隔")
    parser.add_argument("--group", choices=("stack", "spr", "both", "all"), default="all")
    parser.add_argument("--strategy", action="append", default=[], help="只输出指定策略，可重复传入")
    parser.add_argument("--min-decisions", type=int, default=1, help="过滤策略决策数少于该值的桶")
    parser.add_argument("--top", type=int, default=0, help="每个桶只输出前 N 个策略，0 表示不限")
    args = parser.parse_args()

    spr_edges = parse_spr_edges(args.spr_buckets)
    hero_aliases = load_hero_aliases(args.hero)
    summary = analyze_log(args.log, hero_aliases, args.stack_step, spr_edges)
    strategy_filter = set(args.strategy)

    print(f"source={args.log}")
    print(f"hero_aliases={', '.join(hero_aliases)}")
    print(f"hands={summary.hands} hero_decisions={summary.hero_decisions} strategy_decisions={summary.strategy_decisions}")
    print("频率分母=该桶内带 分支/候选 详情行的策略决策数；候选同一决策内去重；候选后触发=同一决策既是候选又被选中的比例。")

    if args.group in {"stack", "all"}:
        print_group("按筹码深度", summary.by_stack, strategy_filter, args.min_decisions, args.top)
    if args.group in {"spr", "all"}:
        print_group("按 SPR", summary.by_spr, strategy_filter, args.min_decisions, args.top)
    if args.group in {"both", "all"}:
        print_group("按筹码深度 + SPR", summary.by_stack_spr, strategy_filter, args.min_decisions, args.top)


if __name__ == "__main__":
    main()
