"""Replay historical hands through the CURRENT strategy code and report
how the bot's decisions would differ from what was logged.

Guarantees:
 * autosave_path=None   → opponents.json is NOT touched
 * log_file=None        → no log files written
 * no sleep / injection delay (the API doesn't sleep; the delay lives in
                                pf_intercept which we bypass entirely)
 * read-only w.r.t. the repo: this script never edits anything under
                              pokerfate/ or pf_intercept/

Output:
 * stdout: high-level summary (decision drift counts, direction buckets,
           drift per issue A-I)
 * --out (optional): NDJSON of per-decision comparisons

Usage:
    # Current session (small)
    python -m scripts.replay_and_compare --replay /tmp/replay_current.jsonl

    # Everything
    python -m scripts.replay_and_compare --replay /tmp/replay_bak.jsonl \\
        --out /tmp/replay_diff.jsonl --max-hands 200
"""
from __future__ import annotations

import argparse
import json
import sys
import os
import traceback
from collections import Counter, defaultdict
from pathlib import Path
from typing import Optional

try:
    from scripts.hero_name import load_hero_name
except ModuleNotFoundError:  # Support `python scripts/replay_and_compare.py`.
    from hero_name import load_hero_name

# Windows 编码兜底：强制 stdout/stderr 用 UTF-8（避免 cmd cp936 print 中文/花色崩）
# Python 3.7+ 支持 reconfigure；旧环境失败时静默跳过。
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass

# Belt-and-braces: force test-mode env so the API defaults autosave/log to None
# even if future versions change the _UNSET sentinel.
os.environ.setdefault("PYTEST_CURRENT_TEST", "scripts/replay_and_compare.py")


def load_replay(path: Path) -> list[dict]:
    hands = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            hands.append(json.loads(line))
    return hands


def _hero_id(players: list[dict], hero_name: str) -> Optional[int]:
    for p in players:
        if p.get("name") == hero_name:
            return p["id"]
    return None


def _replay_hand(api, hand: dict, hero_id: int) -> list[dict]:
    """Walk one hand. At each `decision` event, ask the bot what it would do.
    Return list of decision comparisons, not applied back to subsequent state
    (we always follow the HISTORICAL action to keep downstream state identical
    to the log — otherwise tracker state diverges and comparisons are noisy).
    """
    from pokerfate.api import PlayerInfo, ActionEvent
    from pokerfate.core.game_state import Action, ActionType

    # Build PlayerInfo list (all players including hero)
    players = hand["players"]
    pinfos = [
        PlayerInfo(
            player_id=p["id"],
            name=p.get("name", str(p["id"])),
            stack=float(p.get("stack") or 0),
            position=p.get("pos") or "",
        )
        for p in players
    ]
    api.new_hand(players=pinfos, dealer_id=int(hand.get("dealer_id") or 0))

    if hand.get("hole_cards"):
        api.deal_hole_cards(hand["hole_cards"])

    # Track per-street state we need for request_action params
    current_street = "preflop"
    board_cards: list[str] = []
    street_max_bet = 0.0
    street_bets: dict[int, float] = {}
    my_current_bet_this_street = 0.0
    my_committed_total = 0.0   # sum of bot's call/raise amounts across streets

    # hero's running stack (we update from recorded my_delta at the end)
    hero_player = next((p for p in players if p["id"] == hero_id), None)
    if hero_player is None:
        return []
    hero_stack = float(hero_player.get("stack") or 0)

    active_opp_ids: set[int] = {p["id"] for p in players if p["id"] != hero_id}

    comparisons: list[dict] = []

    for ev in hand["events"]:
        etype = ev["type"]
        if etype == "board":
            new_street = ev["street"]
            board_cards = list(board_cards) + list(ev.get("cards", []))
            api.deal_board(list(ev.get("cards", [])), street=new_street)
            current_street = new_street
            street_max_bet = 0.0
            street_bets = {}
            my_current_bet_this_street = 0.0

        elif etype == "opp_action":
            pid = ev["pid"]
            action = ev["action"]
            amount = float(ev.get("amount") or 0)
            street = ev.get("street", current_street)
            prev_bet = street_bets.get(pid, 0.0)
            api_amount = amount
            if action == "raise":
                street_bets[pid] = amount
                api_amount = amount
            elif action == "call":
                target_bet = amount if amount > 0 else street_max_bet
                added = max(0.0, target_bet - prev_bet)
                street_bets[pid] = prev_bet + added
                api_amount = added
            try:
                api.notify_action(ActionEvent(
                    player_id=pid,
                    action=action,
                    amount=api_amount,
                    street=street,
                ))
            except Exception as exc:
                print(
                    f"[replay_and_compare] notify_action failed hand={hand.get('hand_id')} "
                    f"player_id={pid} action={action}: {type(exc).__name__}: {exc}",
                    file=sys.stderr,
                )
                traceback.print_exc(file=sys.stderr)
                return comparisons
            if action == "fold":
                active_opp_ids.discard(pid)
            elif action == "raise":
                street_max_bet = max(street_max_bet, amount)
            elif action == "call":
                # Amount is the bet that was called, i.e. becomes the table's
                # current_bet level.
                street_max_bet = max(street_max_bet, amount)

        elif etype == "decision":
            # Build request_action parameters
            pot = float(ev.get("pot") or 0)
            to_call = float(ev.get("to_call") or 0)
            num_active_opp = len(active_opp_ids)
            try:
                decision = api.request_action(
                    street=ev.get("street", current_street),
                    pot=pot,
                    current_bet=street_max_bet,
                    to_call=to_call,
                    my_stack=hero_stack,
                    num_active_opponents=max(1, num_active_opp),
                    my_current_bet_this_street=my_current_bet_this_street,
                )
            except Exception as exc:
                print(
                    f"[replay_and_compare] request_action failed hand={hand.get('hand_id')} "
                    f"street={ev.get('street', current_street)}: {type(exc).__name__}: {exc}",
                    file=sys.stderr,
                )
                traceback.print_exc(file=sys.stderr)
                return comparisons

            hist_action = ev.get("action")
            hist_amount = float(ev.get("amount") or 0)
            new_action = decision.action
            new_amount = float(decision.amount or 0)
            diag = getattr(api._bot, "last_decision_diagnostics", {}) or {}

            comparisons.append({
                "hand": hand["hand"],
                "session": hand.get("session", 0),
                "street": ev.get("street"),
                "pot": pot,
                "to_call": to_call,
                "equity_hist": ev.get("equity"),
                "equity_random_hist": ev.get("equity_random"),
                "hist": {"action": hist_action, "amount": hist_amount},
                "new": {"action": new_action, "amount": new_amount},
                "diagnostics": diag,
                "changed": (hist_action != new_action)
                           or abs(hist_amount - new_amount) > 1.0,
                # Realized hand PnL (for sanity-check: did hero actually win
                # or lose this hand? If hero lost, a new code fold is
                # ~guaranteed to save chips; if hero won, fold would cost.)
                "hist_hand_delta": (hand.get("result") or {}).get("my_delta", 0),
            })

            # IMPORTANT: always follow the historical action for downstream
            # state. This keeps the opponent model + tracker state identical
            # to what actually happened, so subsequent comparisons aren't
            # compounded by decision drift.
            if hist_action in ("call", "raise"):
                cost = max(0.0, hist_amount - my_current_bet_this_street)
                hero_stack = max(0.0, hero_stack - cost)
                my_committed_total += cost
                my_current_bet_this_street = hist_amount
                street_bets[hero_id] = my_current_bet_this_street
                if hist_action == "raise":
                    street_max_bet = max(street_max_bet, hist_amount)
            elif hist_action == "check":
                street_bets[hero_id] = my_current_bet_this_street
            elif hist_action == "fold":
                active_opp_ids.clear()

            # request_action applies the NEW decision to API/GameState. For
            # replay diff we must continue from the HISTORICAL branch so later
            # decisions are not polluted by a prior counterfactual fold/call.
            hist_type = {
                "fold": ActionType.FOLD,
                "check": ActionType.CHECK,
                "call": ActionType.CALL,
                "raise": ActionType.RAISE,
            }.get(hist_action, ActionType.CHECK)
            hist_action_obj = Action(
                hist_type,
                hist_amount if hist_type == ActionType.RAISE else 0.0,
            )
            hist_street = ev.get("street", current_street)
            if getattr(api, "_action_history", None):
                api._action_history[-1] = (hero_id, hist_action_obj, hist_street)
            my_p = api._get_player(hero_id)
            if my_p is not None:
                my_p.stack = hero_stack
                my_p.current_bet = my_current_bet_this_street
                my_p.is_folded = hist_action == "fold"
                my_p.is_all_in = hero_stack <= 0
            api._street_contribs[hero_id] = my_current_bet_this_street
            api._bot._my_street_actions[hist_street] = hist_action

    # hand_over call — pass parsed showdown data when available so Range V2
    # learner/calibration replay has the same ground truth as the console log.
    result = hand.get("result") or {}
    name_to_pid = {p.get("name"): p["id"] for p in players}
    final_stacks_by_pid = {
        name_to_pid[name]: int(stack)
        for name, stack in (result.get("final_stacks") or {}).items()
        if name in name_to_pid
    }
    if hero_id not in final_stacks_by_pid:
        final_stacks_by_pid[hero_id] = int(hero_stack)

    showdown_by_pid = {
        name_to_pid[name]: cards
        for name, cards in (result.get("showdown_hands") or {}).items()
        if name in name_to_pid
    }

    def _clean_winner_name(name: str) -> str:
        return name.split("[", 1)[0].strip()

    winner_ids = [
        name_to_pid[name]
        for raw in (result.get("winners") or [])
        for name in [_clean_winner_name(str(raw))]
        if name in name_to_pid
    ]
    try:
        api.hand_over(
            winner_ids=winner_ids,
            pot=int(result.get("pot", 0)),
            final_stacks=final_stacks_by_pid,
            showdown_hands=showdown_by_pid or None,
            my_profit_delta=result.get("my_delta"),
        )
    except Exception as exc:
        print(
            f"[replay_and_compare] hand_over failed hand={hand.get('hand_id')}: "
            f"{type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        traceback.print_exc(file=sys.stderr)
        pass

    return comparisons


def classify_change(c: dict) -> str:
    """Short human-readable tag describing how the decision moved."""
    h = c["hist"]["action"]
    n = c["new"]["action"]
    if h == n:
        ha = c["hist"]["amount"]
        na = c["new"]["amount"]
        if h == "raise" and abs(na - ha) > max(ha * 0.15, 5.0):
            direction = "bigger" if na > ha else "smaller"
            return f"raise→raise-{direction}"
        return "unchanged"
    return f"{h}→{n}"


# ---------------------------------------------------------------------------
# EV delta estimation (chips-level)
# ---------------------------------------------------------------------------
#
# Theory (standard poker EV, e.g. Janda "Applications of No-Limit Hold'em" ch.2):
#   EV(fold)  = 0   (sunk costs ignored — they're gone either way)
#   EV(check) = 0   (no chip movement)
#   EV(call)  = eq·pot − (1−eq)·to_call      # relative to folding
#   EV(bet)   = fr·pot + (1−fr)·[eq·(pot + amount) − (1−eq)·amount]
#     where fr = villain fold rate to our bet.
#
# We use the historical equity recorded at the decision point. "pot" is the
# pot BEFORE hero's action, which is exactly what's logged. For bets, fold
# rate is not logged so we use a conservative pool prior fold_rate_prior=0.30
# (matches PokerTracker low-stakes field avg). This injects some noise but
# scales symmetrically across historical and new code, so NET delta is still
# a meaningful signal.
#
# Confidence labels:
#   HIGH  — call↔fold (no fold-rate assumption)
#   MED   — raise size change, same class (villain response assumed sticky)
#   LOW   — action class change involving a bet (fold_rate guessed)


_FOLD_RATE_PRIOR = 0.30


def _ev_call(eq: float, pot: float, to_call: float) -> float:
    """EV(call) relative to EV(fold) = 0."""
    return eq * pot - (1.0 - eq) * to_call


def _ev_bet(eq: float, pot: float, amount: float,
            fold_rate: float = _FOLD_RATE_PRIOR) -> float:
    """EV(bet `amount` into `pot` with equity `eq`). amount = total new bet size."""
    # If villain folds: we take the pot as-is.
    # If villain calls: pot grows by `amount` on villain side; we win pot+amount or lose amount.
    called_ev = eq * (pot + amount) - (1.0 - eq) * amount
    return fold_rate * pot + (1.0 - fold_rate) * called_ev


def estimate_ev_delta(c: dict) -> tuple[float | None, str]:
    """Return (delta_chips, confidence_tag).

    delta_chips is `EV(new_action) − EV(hist_action)` in chips; positive means
    the new code's decision has higher expected value given the historical
    equity estimate. None means we didn't estimate (no reasonable heuristic).
    """
    h = c["hist"]["action"]
    n = c["new"]["action"]
    ha = float(c["hist"].get("amount") or 0)
    na = float(c["new"].get("amount") or 0)
    eq = float(c.get("equity_hist") or 0)
    pot = float(c.get("pot") or 0)
    to_call = float(c.get("to_call") or 0)

    if h == n and abs(ha - na) < max(ha * 0.01, 1.0):
        return 0.0, "unchanged"

    def ev_of(action: str, amount: float) -> float:
        if action in ("fold", "check"):
            return 0.0
        if action == "call":
            return _ev_call(eq, pot, to_call)
        if action == "raise":
            return _ev_bet(eq, pot, amount)
        return 0.0

    delta = ev_of(n, na) - ev_of(h, ha)

    # Confidence: no bet involved → HIGH, both bets → MED, mixed → LOW.
    hist_has_bet = h == "raise"
    new_has_bet = n == "raise"
    if not hist_has_bet and not new_has_bet:
        conf = "HIGH"   # call ↔ fold/check space
    elif hist_has_bet and new_has_bet:
        conf = "MED"    # same class, size differs
    else:
        conf = "LOW"    # class change involving a bet (fold_rate assumption)

    return delta, conf


def _tag_issue(c: dict, tag: str) -> list[str]:
    """Tag this decision against expected gameplay-analysis fix directions."""
    tags: list[str] = []
    street = c.get("street") or ""
    to_call = c.get("to_call") or 0
    pot = c.get("pot") or 0
    pot_odds = to_call / (pot + to_call) if (pot + to_call) > 0 else 0
    eq = c.get("equity_hist") or 0

    # Issue A: zero-bluff fold — should fold more where villain is a value-only bettor
    if tag == "call→fold" and to_call > 0 and pot_odds >= 0.25:
        tags.append("A-tighter-call")

    # Issue C: more c-bets after fold-to-cbet proxy. No direct proxy, but
    # "check→raise" at 0 to_call is cbet coming in.
    if tag in ("check→raise",) and to_call == 0:
        tags.append("C-more-cbets")

    # Issue G: more river value bets
    if street == "river" and tag in ("check→raise",) and to_call == 0 and eq >= 0.50:
        tags.append("G-river-value")

    # Issue H: bigger river value bets vs station. Look at raise→raise-bigger on river
    if street == "river" and tag == "raise→raise-bigger":
        tags.append("H-bigger-river")

    # Issue I: BB defends (call) vs an open where hist folded.
    if tag == "fold→call" and street == "preflop" and pot_odds < 0.35:
        tags.append("I-bb-defend?")

    # Defensive tightening: fold→call new is MORE loose not tighter; mark for inspection
    if tag == "fold→call":
        tags.append("looser")
    if tag == "call→fold":
        tags.append("tighter")

    return tags


def summarize(comparisons: list[dict]) -> dict:
    change_counts: Counter[str] = Counter()
    issue_counts: Counter[str] = Counter()
    per_street: defaultdict[str, Counter[str]] = defaultdict(Counter)

    # EV delta totals. Separate by confidence so the user sees what's solid.
    ev_sum_by_conf: dict[str, float] = {"HIGH": 0.0, "MED": 0.0, "LOW": 0.0}
    ev_count_by_conf: dict[str, int] = {"HIGH": 0, "MED": 0, "LOW": 0}
    # Per-issue EV delta (only issue-tagged changes contribute)
    ev_sum_by_issue: defaultdict[str, float] = defaultdict(float)
    ev_count_by_issue: defaultdict[str, int] = defaultdict(int)
    ev_sum_by_purpose: defaultdict[str, float] = defaultdict(float)
    ev_count_by_purpose: defaultdict[str, int] = defaultdict(int)
    changed_by_street_purpose: Counter[str] = Counter()

    total = len(comparisons)
    changed = 0

    for c in comparisons:
        tag = classify_change(c)
        change_counts[tag] += 1
        if tag != "unchanged":
            changed += 1
        per_street[c.get("street") or "?"][tag] += 1

        ev_delta, conf = estimate_ev_delta(c)
        if ev_delta is not None and conf != "unchanged":
            ev_sum_by_conf[conf] += ev_delta
            ev_count_by_conf[conf] += 1
            # Store on the record for per-row output
            c["ev_delta"] = round(ev_delta, 1)
            c["ev_conf"] = conf

            issue_tags = _tag_issue(c, tag)
            for itag in issue_tags:
                ev_sum_by_issue[itag] += ev_delta
                ev_count_by_issue[itag] += 1
                issue_counts[itag] += 1
            diag = c.get("diagnostics") or {}
            purpose = (
                diag.get("final_purpose")
                or diag.get("purpose")
                or diag.get("action")
                or (c.get("new") or {}).get("purpose")
                or "unknown"
            )
            ev_sum_by_purpose[purpose] += ev_delta
            ev_count_by_purpose[purpose] += 1
            if tag != "unchanged":
                changed_by_street_purpose[
                    f"{c.get('street') or '?'}|{purpose}"
                ] += 1
        else:
            if tag == "unchanged":
                c["ev_delta"] = 0.0
                c["ev_conf"] = "unchanged"

    # ------------------------------------------------------------------
    # Realized-PnL sanity cross-check.
    #
    # For each change, the HAND already resolved one way in the log. We can't
    # perfectly know what would have happened with the new decision, but we
    # CAN check: did hero actually win or lose this hand historically?
    #
    # If hero LOST the hand and the change is call→fold: new code's fold
    # "very likely saves chips" — fold is free, and hero was going to lose.
    # If hero WON and change is call→fold: new code's fold "very likely
    # loses chips" — hero gave up winnings.
    #
    # This isn't a perfect delta (the change might be mid-hand, other
    # decisions could flip the outcome), but it's a strong directional
    # sanity check for terminal-ish fold/call changes.
    # ------------------------------------------------------------------
    realized_stats: dict[str, dict[str, int]] = defaultdict(
        lambda: {"hist_won": 0, "hist_lost": 0, "hist_flat": 0,
                 "won_delta_sum": 0, "lost_delta_sum": 0}
    )
    for c in comparisons:
        tag = classify_change(c)
        if tag == "unchanged":
            continue
        d = int(c.get("hist_hand_delta") or 0)
        bucket = realized_stats[tag]
        if d > 0:
            bucket["hist_won"] += 1
            bucket["won_delta_sum"] += d
        elif d < 0:
            bucket["hist_lost"] += 1
            bucket["lost_delta_sum"] += d
        else:
            bucket["hist_flat"] += 1

    # For call→fold changes: sign of historical outcome = chip impact direction
    #   hero lost the hand → fold saves chips (positive)
    #   hero won the hand  → fold gives up chips (negative)
    # Since hero typically has MULTIPLE decisions per hand, attributing the
    # full hand delta to a single decision overstates impact. We report the
    # COUNT distribution as the honest signal.
    realized_summary = {}
    for tag, stats in sorted(realized_stats.items(), key=lambda kv: -sum(kv[1].values())):
        total_t = stats["hist_won"] + stats["hist_lost"] + stats["hist_flat"]
        if total_t == 0:
            continue
        realized_summary[tag] = {
            "total": total_t,
            "hist_won": stats["hist_won"],
            "hist_lost": stats["hist_lost"],
            "hist_flat": stats["hist_flat"],
            "hist_lost_pct": round(100.0 * stats["hist_lost"] / total_t, 0),
            "won_delta_sum": stats["won_delta_sum"],
            "lost_delta_sum": stats["lost_delta_sum"],
        }

    worst_changes = []
    changed_rows = [c for c in comparisons if classify_change(c) != "unchanged"]
    changed_rows.sort(key=lambda c: float(c.get("ev_delta") or 0.0))
    for c in changed_rows[:10]:
        diag = c.get("diagnostics") or {}
        worst_changes.append({
            "hand": c.get("hand"),
            "session": c.get("session"),
            "street": c.get("street"),
            "hist": c.get("hist"),
            "new": c.get("new"),
            "ev_delta": c.get("ev_delta"),
            "ev_conf": c.get("ev_conf"),
            "purpose": diag.get("final_purpose") or diag.get("purpose") or diag.get("action"),
            "arbitration_mode": diag.get("arbitration_mode"),
            "leverage_flags": diag.get("leverage_flags"),
        })

    return {
        "total_decisions": total,
        "total_changed": changed,
        "change_pct": round(100.0 * changed / max(total, 1), 1),
        "change_breakdown": dict(change_counts.most_common()),
        "issue_alignment": dict(issue_counts.most_common()),
        "per_street": {k: dict(v.most_common()) for k, v in per_street.items()},
        "realized_hand_outcome_by_change": realized_summary,
        # EV (chips-level). HIGH = call↔fold (no assumption), MED = same-class
        # raise size, LOW = class change involving a bet (fold_rate guessed).
        "ev_delta_chips": {
            conf: {
                "sum": round(ev_sum_by_conf[conf], 1),
                "count": ev_count_by_conf[conf],
                "avg_per_change": (round(ev_sum_by_conf[conf] / ev_count_by_conf[conf], 1)
                                   if ev_count_by_conf[conf] else 0.0),
            }
            for conf in ("HIGH", "MED", "LOW")
        },
        "ev_delta_by_issue": {
            issue: {
                "sum": round(ev_sum_by_issue[issue], 1),
                "count": ev_count_by_issue[issue],
            }
            for issue in sorted(ev_sum_by_issue.keys(),
                                key=lambda k: -abs(ev_sum_by_issue[k]))
        },
        "ev_delta_by_purpose": {
            purpose: {
                "sum": round(ev_sum_by_purpose[purpose], 1),
                "count": ev_count_by_purpose[purpose],
            }
            for purpose in sorted(ev_sum_by_purpose.keys(),
                                  key=lambda k: -abs(ev_sum_by_purpose[k]))
        },
        "changed_by_street_purpose": dict(changed_by_street_purpose.most_common()),
        "worst_changes": worst_changes,
        "ev_caveats": (
            "HIGH confidence: call↔fold changes, no fold-rate assumption. "
            "MED/LOW confidence: bet-size or class changes use a 0.30 villain "
            "fold-rate prior; the ABSOLUTE values are rough, but NET SIGN is "
            "meaningful. Opponent responses to changed bet sizes are assumed "
            "sticky (villain does what they did historically), which is the "
            "standard counterfactual simplification in poker EV analysis."
        ),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--replay", type=Path, required=True,
                    help="Replay NDJSON produced by parse_log_to_replay.py")
    ap.add_argument("--out", type=Path,
                    help="Optional: write per-decision NDJSON diff here")
    ap.add_argument("--max-hands", type=int, default=-1,
                    help="Cap number of hands to replay (default: all)")
    ap.add_argument("--start-hand", type=int, default=0,
                    help="Skip the first N hands (0 = no skip; for parallel sharding)")
    ap.add_argument("--end-hand", type=int, default=-1,
                    help="Stop at hand index (exclusive); -1 = no limit")
    ap.add_argument("--seed", type=int, default=42,
                    help="Seed used to pin RNG behavior for reproducibility")
    ap.add_argument("--progress", action="store_true",
                    help="Emit machine-readable progress lines to stderr")
    ap.add_argument("--progress-every", type=int, default=10,
                    help="Emit progress every N hands when --progress is set")
    ap.add_argument("--disable-showdown-calibration", action="store_true", default=True,
                    help="Disable per-tracker-update showdown calibration during replay (default)")
    ap.add_argument("--enable-showdown-calibration", dest="disable_showdown_calibration",
                    action="store_false",
                    help="Keep calibration hook enabled for diagnostic replay")
    args = ap.parse_args()
    try:
        hero_name = load_hero_name()
    except RuntimeError as exc:
        ap.error(str(exc))

    # Defer heavy import until here so `--help` stays fast
    from pokerfate.api import PokerFateAPI

    hands = load_replay(args.replay)
    # Sharding：start_hand / end_hand 切片，max_hands 仍兼容（在切片内再 cap）。
    start = max(0, args.start_hand)
    end = args.end_hand if args.end_hand > 0 else len(hands)
    hands = hands[start:end]
    if args.max_hands > 0:
        hands = hands[:args.max_hands]

    # One fresh API per session so tracker state is session-scoped (matches
    # how the live bot experiences session boundaries).
    comparisons: list[dict] = []
    last_session = None
    api: Optional[PokerFateAPI] = None
    hero_id_cache: dict[int, Optional[int]] = {}

    total_hands = len(hands)
    progress_every = max(1, int(args.progress_every))
    for idx, hand in enumerate(hands, 1):
        session = hand.get("session", 0)
        hero_id = _hero_id(hand["players"], hero_name)
        if hero_id is None:
            if args.progress and (idx == 1 or idx == total_hands or idx % progress_every == 0):
                print(f"__PF_PROGRESS__ {idx} {total_hands}", file=sys.stderr, flush=True)
            continue
        if session != last_session or api is None or hero_id != getattr(api, "my_player_id", None):
            # Fresh API for new session or changed hero id
            api = PokerFateAPI(
                my_player_id=hero_id,
                big_blind=2.0,   # replay doesn't depend on BB; API uses it
                autosave_path=None,
                log_file=None,
                verbose=False,
                equity_iterations=200,
                enable_showdown_calibration=not args.disable_showdown_calibration,
                decision_seed=args.seed,
            )
            # Silence per-hand pretty-print so summary 不被淹没。
            api._log._console = False
            last_session = session

        comparisons.extend(_replay_hand(api, hand, hero_id))
        if args.progress and (idx == 1 or idx == total_hands or idx % progress_every == 0):
            print(f"__PF_PROGRESS__ {idx} {total_hands}", file=sys.stderr, flush=True)

    summary = summarize(comparisons)
    print(json.dumps(summary, indent=2, ensure_ascii=False))

    if args.out:
        with args.out.open("w", encoding="utf-8") as f:
            for c in comparisons:
                f.write(json.dumps(c, ensure_ascii=False) + "\n")
        print(f"\nwrote {len(comparisons)} comparisons to {args.out}",
              file=sys.stderr)


if __name__ == "__main__":
    main()
