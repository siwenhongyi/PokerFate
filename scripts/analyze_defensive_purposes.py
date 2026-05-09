"""Stream-analyze defensive v3 purpose usage from PokerFate console logs.

The parser keeps only one hand in memory. It extracts postflop defensive
branches from human console logs, records triggered candidates, selected branch,
nearby responses, and a coarse purpose-achievement verdict.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

try:
    from scripts.hero_name import load_hero_name
except ModuleNotFoundError:
    from hero_name import load_hero_name


DEF_PURPOSES = {
    "bluff_catch_call",
    "draw_call",
    "value_raise",
    "semi_bluff_raise",
    "protection_raise",
    "overbet_raise_jam",
    "fold",
    "fold_override_call",
}

TS_RE = re.compile(r"^\[(\d{2}:\d{2}:\d{2})\]\s?(.*)$")
HAND_RE = re.compile(r"第\s*(\d+)\s*手")
HOLE_RE = re.compile(r"底牌\s+(\S+)\s+(\S+)")
STREET_RE = re.compile(r"──\s*(翻牌前|翻牌|转牌|河牌)")
HERO_RE = re.compile(
    r"►\s*(\S+)\s+(弃牌|过牌|跟注|加注|下注|全下)"
    r"(?:\s+(\d+))?"
    r".*?胜率\s*(\d+)%(?:\(vs随机(\d+)%\))?"
    r"\s+SPR\s*[≈=]?\s*([\d.]+)"
    r".*?底池\s+(\d+)"
)
BRANCH_RE = re.compile(r"分支=([^│]+)")
CAND_RE = re.compile(r"候选:\s*([^│]+)")
CAND_ITEM_RE = re.compile(r"([A-Za-z_]+)(?:\[(\d+)%\])?")
ODDS_RE = re.compile(r"(?:底池)?赔率\s*(\d+)%")
OPP_ACTION_RE = re.compile(
    r"^\s{2,}(\S+)\s+(弃牌|过牌|跟注|加注|下注|全下)"
    r"(?:\s+(\d+)bb(?:\s+\(\d+bb\s+([\d.]+)x\s+pot\))?)?"
    r".*?(?:range\s+(\d+)%(?:\s+\[([^\]]+)\])?)?"
)
RESULT_RE = re.compile(
    r"✔\s*(.+?)\s*\[([^\]]*)\]\s*赢得\s*(\d+)"
    r"\s+本手\s*([+-]?\d+)\s*(?:\[我:\s*([^\]]*)\])?"
)

STREET_MAP = {
    "翻牌前": "preflop",
    "翻牌": "flop",
    "转牌": "turn",
    "河牌": "river",
}


def _clean_text(raw: str) -> tuple[str, str | None]:
    m = TS_RE.match(raw)
    if m:
        return m.group(2), m.group(1)
    return raw, None


def _branch_id(raw: str) -> str:
    raw = raw.strip()
    raw = raw.split()[0]
    raw = raw.split("→", 1)[0]
    return raw


def _parse_candidates(text: str) -> list[dict[str, Any]]:
    m = CAND_RE.search(text)
    if not m:
        return []
    out = []
    for item in CAND_ITEM_RE.finditer(m.group(1)):
        purpose = item.group(1)
        if purpose not in DEF_PURPOSES:
            continue
        prob = int(item.group(2)) / 100.0 if item.group(2) else None
        out.append({"purpose": purpose, "prob": prob})
    return out


def _parse_bucket_text(text: str | None) -> dict[str, float]:
    if not text:
        return {}
    out: dict[str, float] = {}
    for part in text.split("/"):
        m = re.match(r"([一-龥]+)(\d+)%", part.strip())
        if m:
            out[m.group(1)] = int(m.group(2)) / 100.0
    return out


def _result_from_line(text: str, line_no: int) -> dict[str, Any] | None:
    m = RESULT_RE.search(text)
    if not m:
        return None
    return {
        "winner": m.group(1).strip(),
        "winner_hand_type": m.group(2).strip(),
        "pot": int(m.group(3)),
        "hero_pnl_chips": int(m.group(4)),
        "hero_final_hand": (m.group(5) or "").strip(),
        "line_no": line_no,
        "line": text,
    }


def _has_strong_response(responses: list[dict[str, Any]]) -> bool:
    for resp in responses:
        buckets = resp.get("bucket_dist") or {}
        if buckets.get("坚果", 0.0) >= 0.35:
            return True
        if buckets.get("坚果", 0.0) + buckets.get("强", 0.0) >= 0.60:
            return True
        if resp.get("action") in ("加注", "全下") and (
            buckets.get("坚果", 0.0) + buckets.get("强", 0.0) >= 0.45
        ):
            return True
    return False


def _all_folded(responses: list[dict[str, Any]]) -> bool:
    actionable = [r for r in responses if r.get("action") != "过牌"]
    return bool(actionable) and all(r.get("action") == "弃牌" for r in actionable)


def _pot_odds(event: dict[str, Any]) -> float | None:
    if event.get("pot_odds") is not None:
        return float(event["pot_odds"])
    return None


def _classify_event(event: dict[str, Any], result: dict[str, Any] | None, hero_name: str) -> tuple[str, str]:
    purpose = event["used_purpose"]
    eq = event.get("equity")
    eqf = (float(eq) / 100.0) if eq is not None else None
    odds = _pot_odds(event)
    hero_won = bool(result and hero_name in (result.get("winner") or ""))
    pnl = int(result.get("hero_pnl_chips") or 0) if result else 0
    responses = event.get("immediate_responses", []) + event.get("later_responses", [])
    strong_resp = _has_strong_response(responses)

    if purpose == "fold":
        if odds is not None and eqf is not None:
            if eqf + 0.02 < odds:
                return "good", "equity below pot odds; fold saved chips"
            if eqf >= odds + 0.15 and eqf >= 0.35:
                return "bad_or_tight", "equity was well above pot odds; possible overfold"
            return "ok", "marginal fold by equity/pot-odds"
        if eqf is not None and eqf <= 0.20:
            return "good", "very low equity fold"
        return "unclear", "no pot-odds evidence for fold"

    if purpose in ("bluff_catch_call", "fold_override_call"):
        if hero_won:
            return "good", "call reached showdown/won pot"
        if odds is not None and eqf is not None and eqf >= odds:
            if pnl < 0 and strong_resp:
                return "mixed_followup", "call was priced, but later strong range won"
            return "ok_variance", "call was priced but hand lost"
        if pnl < 0:
            return "bad", "call lost without enough pot-odds evidence"
        return "unclear", "insufficient showdown/odds evidence"

    if purpose == "draw_call":
        if hero_won:
            return "good", "draw/realization call won"
        implied = 0.02
        if event.get("street") == "flop":
            implied = 0.04
        if odds is not None and eqf is not None and eqf + implied >= odds:
            return "ok_variance", "draw call was priced with implied odds"
        if pnl < 0:
            return "bad", "draw call lost without enough price evidence"
        return "unclear", "insufficient evidence for draw-call price"

    if purpose in ("value_raise", "protection_raise", "overbet_raise_jam"):
        if _all_folded(responses) or hero_won:
            return "good", "raise took pot or won at showdown"
        if strong_resp and pnl < 0:
            return "bad", "raise ran into strong/nut response"
        if pnl < 0:
            return "mixed_followup", "raise did not realize by final result"
        return "ok", "raise did not show clear failure"

    if purpose == "semi_bluff_raise":
        if _all_folded(responses) or hero_won:
            return "good", "semi-bluff raise got folds or won"
        if strong_resp and pnl < 0:
            return "bad", "semi-bluff raise met strong response and lost"
        if odds is not None and eqf is not None and eqf >= 0.25:
            return "ok_variance", "semi-bluff had equity but missed"
        if pnl < 0:
            return "bad", "semi-bluff raise did not generate enough fold equity"
        return "unclear", "insufficient response evidence"

    return "unclear", "unknown defensive purpose"


def _finish_hand(hand: dict[str, Any] | None, hero_name: str, events_out: list[dict[str, Any]]) -> None:
    if not hand:
        return
    result = hand.get("result")
    for event in hand.get("events", []):
        verdict, reason = _classify_event(event, result, hero_name)
        event["result"] = result
        event["verdict"] = verdict
        event["verdict_reason"] = reason
        event["hand_start_line"] = hand.get("start_line")
        event["hand_end_line"] = hand.get("end_line")
        events_out.append(event)


def analyze_log(log_path: Path, hero_name: str) -> dict[str, Any]:
    events: list[dict[str, Any]] = []
    hand: dict[str, Any] | None = None
    current_street = "preflop"
    pending_decision: dict[str, Any] | None = None
    open_event: dict[str, Any] | None = None
    last_opp_odds: float | None = None
    hands_total = 0

    with log_path.open("r", encoding="utf-8", errors="replace") as f:
        for line_no, raw in enumerate(f, start=1):
            text, ts = _clean_text(raw.rstrip("\n"))

            m_hand = HAND_RE.search(text)
            if m_hand:
                _finish_hand(hand, hero_name, events)
                hands_total += 1
                hand = {
                    "hand_no": int(m_hand.group(1)),
                    "start_line": line_no,
                    "end_line": line_no,
                    "hole": "",
                    "events": [],
                    "result": None,
                }
                current_street = "preflop"
                pending_decision = None
                open_event = None
                last_opp_odds = None
                continue

            if hand is None:
                continue
            hand["end_line"] = line_no

            m_hole = HOLE_RE.search(text)
            if m_hole:
                hand["hole"] = f"{m_hole.group(1)} {m_hole.group(2)}"
                continue

            m_street = STREET_RE.search(text)
            if m_street:
                current_street = STREET_MAP[m_street.group(1)]
                if open_event is not None:
                    open_event = None
                pending_decision = None
                last_opp_odds = None
                continue

            m_hero = HERO_RE.search(text)
            if m_hero and m_hero.group(1) == hero_name:
                pending_decision = {
                    "line_no": line_no,
                    "timestamp": ts,
                    "hand_no": hand["hand_no"],
                    "hole": hand.get("hole", ""),
                    "street": current_street,
                    "action": m_hero.group(2),
                    "amount": float(m_hero.group(3) or 0),
                    "equity": int(m_hero.group(4)),
                    "equity_random": int(m_hero.group(5)) if m_hero.group(5) else None,
                    "spr": float(m_hero.group(6)),
                    "pot": int(m_hero.group(7)),
                    "pot_odds": last_opp_odds,
                    "line": text,
                    "reasoning": "",
                }
                open_event = None
                continue

            if "💭" in text and pending_decision is not None:
                pending_decision["reasoning"] = text.strip()
                m_odds = ODDS_RE.search(text)
                if m_odds:
                    pending_decision["pot_odds"] = int(m_odds.group(1)) / 100.0
                continue

            m_branch = BRANCH_RE.search(text)
            if m_branch and pending_decision is not None:
                used = _branch_id(m_branch.group(1))
                cands = _parse_candidates(text)
                cand_ids = {c["purpose"] for c in cands}
                if used in DEF_PURPOSES or cand_ids:
                    if used not in DEF_PURPOSES and cand_ids:
                        used = sorted(cand_ids)[0]
                    event = dict(pending_decision)
                    event.update({
                        "used_purpose": used,
                        "triggered_purposes": cands or [{"purpose": used, "prob": None}],
                        "detail_line_no": line_no,
                        "detail": text.strip(),
                        "immediate_responses": [],
                        "later_responses": [],
                    })
                    hand["events"].append(event)
                    open_event = event
                pending_decision = None
                continue

            m_opp = OPP_ACTION_RE.match(text)
            if m_opp:
                odds_m = ODDS_RE.search(text)
                if odds_m:
                    last_opp_odds = int(odds_m.group(1)) / 100.0
                if open_event is not None:
                    resp = {
                        "name": m_opp.group(1),
                        "action": m_opp.group(2),
                        "amount_bb": int(m_opp.group(3)) if m_opp.group(3) else 0,
                        "bet_pot_ratio": float(m_opp.group(4)) if m_opp.group(4) else None,
                        "range_pct": int(m_opp.group(5)) / 100.0 if m_opp.group(5) else None,
                        "bucket_text": m_opp.group(6) or "",
                        "bucket_dist": _parse_bucket_text(m_opp.group(6)),
                        "line_no": line_no,
                        "line": text,
                    }
                    open_event["immediate_responses"].append(resp)
                continue

            result = _result_from_line(text, line_no)
            if result is not None:
                hand["result"] = result
                open_event = None
                pending_decision = None
                continue

    _finish_hand(hand, hero_name, events)

    by_used: dict[str, Counter[str]] = defaultdict(Counter)
    by_triggered: Counter[str] = Counter()
    by_street: Counter[str] = Counter()
    verdict_counts: Counter[str] = Counter()
    for event in events:
        by_used[event["used_purpose"]][event["verdict"]] += 1
        verdict_counts[event["verdict"]] += 1
        by_street[event["street"]] += 1
        for cand in event.get("triggered_purposes", []):
            by_triggered[cand["purpose"]] += 1

    return {
        "source": str(log_path),
        "hands_total": hands_total,
        "hands_with_defense": len({(e["hand_no"], e.get("hand_start_line")) for e in events}),
        "defense_events": len(events),
        "verdict_counts": dict(verdict_counts.most_common()),
        "by_street": dict(by_street.most_common()),
        "by_used_purpose": {
            purpose: dict(counter.most_common())
            for purpose, counter in sorted(by_used.items())
        },
        "triggered_counts": dict(by_triggered.most_common()),
        "events": events,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--log", type=Path, required=True)
    ap.add_argument("--out", type=Path, default=Path("/tmp/pokerfate_defensive_purposes.json"))
    args = ap.parse_args()
    hero_name = load_hero_name()
    summary = analyze_log(args.log, hero_name)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    compact = {k: v for k, v in summary.items() if k != "events"}
    print(json.dumps(compact, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
