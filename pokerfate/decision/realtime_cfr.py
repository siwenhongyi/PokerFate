"""Turn/river realtime CFR adapter for PokerFate decisions.

This module keeps the postflop solver boundary narrow: PokerFate supplies the
current heads-up turn/river public state plus Range V2 combo weights, and the
adapter returns one legal ``Action`` or a structured fallback reason.
"""

from __future__ import annotations

import importlib.util
import json
import math
import os
import re
import sys
import time
import traceback
from dataclasses import dataclass, field
from importlib.machinery import ExtensionFileLoader
from multiprocessing import get_context
from pathlib import Path
from typing import Any, Callable, Optional, Sequence

from pokerfate.core.game_state import Action, ActionType, GameState, Player
from pokerfate.core.hand_evaluator import HandEvaluator, HandRank
from pokerfate.decision.opponent_numeric_prior import (
    NumericOpponentPrior,
    build_numeric_prior,
)
from pokerfate.strategy.range_v2 import hand_combo_map as hcm


BASE_MENU = {
    "flop_bets": [33.0, 100.0],
    "turn_bets": [33.0, 75.0, 150.0],
    "river_bets": [33.0, 66.0, 100.0, 150.0],
    "future_river_bets": [66.0, 150.0],
    "raises": [2.2, 3.0],
    "rake_rate": 0.09,
    "rake_cap": 0.0,
    "add_allin_threshold": 1.5,
    "force_allin_threshold": 0.15,
    "merging_threshold": 0.0,
}
DEFAULT_ACCURACY = {"turn": 1.5, "river": 1.0}
DEFAULT_TIMEOUT_SEC = 10.0
DEFAULT_MAX_ITERATIONS = 1000
_ACTION_RE = re.compile(r"^(Check|Call|Fold|Bet|Raise|AllIn)(?:\((\d+)\))?$")


@dataclass
class RealtimeCFROptions:
    timeout_sec: float = DEFAULT_TIMEOUT_SEC
    max_iterations: int = DEFAULT_MAX_ITERATIONS
    turn_accuracy: float = DEFAULT_ACCURACY["turn"]
    river_accuracy: float = DEFAULT_ACCURACY["river"]
    threads: int = 0
    solver_lib_path: Optional[str] = None
    min_combo_weight: float = 1e-12
    exploit_enabled: bool = True
    max_exploit_confidence: float = 0.45


@dataclass
class RealtimeCFRState:
    board: str
    oop_range: str
    ip_range: str
    pot_bb: float
    effective_stack_bb: float
    prefix: list[tuple[str, float]] = field(default_factory=list)


@dataclass
class RealtimeCFRDecisionContext:
    gs: GameState
    hero_player_id: int
    street_start_pot: float
    range_provider: Callable[[int], Any]
    hero_range_provider: Optional[Callable[[int], Any]] = None
    villain_profile_provider: Optional[Callable[[int], Any]] = None
    exploit_adjustments_provider: Optional[Callable[[int], dict[str, Any]]] = None
    range_v2_prior_provider: Optional[Callable[[int], dict[str, Any]]] = None


class RealtimeCFRDecisionEngine:
    """Best-effort turn/river realtime CFR search with local fallback reasons."""

    def __init__(self, options: Optional[RealtimeCFROptions] = None):
        self.options = options or RealtimeCFROptions()
        self._last_result: dict[str, Any] = {}
        self._last_error = ""

    @property
    def last_result(self) -> dict[str, Any]:
        return dict(self._last_result)

    @property
    def last_error(self) -> str:
        return self._last_error

    def decide(self, ctx: RealtimeCFRDecisionContext) -> Optional[Action]:
        t0 = time.perf_counter()
        self._last_result = {}
        self._last_error = ""

        prepared = self._prepare(ctx)
        prepare_ms = (time.perf_counter() - t0) * 1000.0
        if prepared is None:
            return None
        state, meta = prepared

        solver_t0 = time.perf_counter()
        result = solve_realtime_cfr(
            state,
            accuracy=self._accuracy(meta["street"]),
            max_iterations=self.options.max_iterations,
            timeout_sec=self.options.timeout_sec,
            threads=self.options.threads,
            solver_lib_path=self.options.solver_lib_path,
        )
        solver_ms = (time.perf_counter() - solver_t0) * 1000.0
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        timing: dict[str, Any] = {
            "prepare_ms": round(prepare_ms, 1),
            "solver_call_ms": round(solver_ms, 1),
            "total_ms": round(elapsed_ms, 1),
        }
        if result is None:
            reason = str(getattr(solve_realtime_cfr, "last_error", "") or "solver_failed_or_timeout")
            detail = getattr(solve_realtime_cfr, "last_error_detail", {}) or {}
            self._last_error = reason
            self._last_result = {
                **meta,
                "status": "fallback",
                "reason": reason,
                "elapsed_ms": elapsed_ms,
                "timing": timing,
            }
            if isinstance(detail, dict) and detail:
                self._last_result["solver_error"] = detail
            return None

        if isinstance(result.get("timing"), dict):
            timing["solver"] = result.get("timing")
        strategy_t0 = time.perf_counter()
        strategy = hand_strategy(result, meta["hero_combo"])
        timing["strategy_lookup_ms"] = round((time.perf_counter() - strategy_t0) * 1000.0, 1)
        if not strategy:
            reason = "hero_combo_missing_from_solver_range"
            self._last_error = reason
            self._last_result = {
                **meta,
                "status": "fallback",
                "reason": reason,
                "elapsed_ms": elapsed_ms,
                "timing": timing,
                "node_actions": list((result.get("node") or {}).get("actions") or []),
            }
            return None

        exploit_t0 = time.perf_counter()
        exploit_detail: dict[str, float] = {}
        profile_t0 = time.perf_counter()
        exploit_profile = self._exploit_profile(ctx, meta["villain_player_id"])
        exploit_detail["profile_ms"] = round((time.perf_counter() - profile_t0) * 1000.0, 1)
        adjustments_t0 = time.perf_counter()
        exploit_adjustments = self._exploit_adjustments(ctx, meta["villain_player_id"])
        exploit_detail["adjustments_ms"] = round((time.perf_counter() - adjustments_t0) * 1000.0, 1)
        line_t0 = time.perf_counter()
        line_context = _build_line_context(
            ctx.gs,
            hero_player_id=ctx.hero_player_id,
            villain_player_id=meta["villain_player_id"],
        )
        exploit_detail["line_context_ms"] = round((time.perf_counter() - line_t0) * 1000.0, 1)
        prior_t0 = time.perf_counter()
        range_v2_prior = self._range_v2_prior(ctx, meta["villain_player_id"])
        prior_timing = {}
        if isinstance(range_v2_prior, dict):
            raw_prior_timing = range_v2_prior.pop("_timing", {})
            if isinstance(raw_prior_timing, dict):
                prior_timing = {
                    str(k): round(float(v), 1)
                    for k, v in raw_prior_timing.items()
                    if isinstance(v, (int, float))
                }
        exploit_detail["range_v2_prior_ms"] = round((time.perf_counter() - prior_t0) * 1000.0, 1)
        if prior_timing:
            for key, value in prior_timing.items():
                exploit_detail[f"range_v2_prior.{key}"] = value
        if range_v2_prior:
            line_context["range_v2"] = range_v2_prior
        bb = max(float(ctx.gs.big_blind or 0.0), 1e-9)
        hero_player = _player_by_id(ctx.gs.players, ctx.hero_player_id)
        defense_fold_cap = None
        if hero_player is not None:
            defense_fold_cap = _defense_fold_cap(
                pot_bb=float(ctx.gs.pot or 0.0) / bb,
                to_call_bb=float(ctx.gs.to_call(hero_player) or 0.0) / bb,
            )
        select_t0 = time.perf_counter()
        selection = _select_exploit_action(
            result,
            hero_combo=meta["hero_combo"],
            hero_side=meta["hero_side"],
            street=meta["street"],
            gto_strategy=strategy,
            profile=exploit_profile,
            adjustments=exploit_adjustments,
            max_confidence=self.options.max_exploit_confidence,
            enabled=self.options.exploit_enabled,
            defense_fold_cap=defense_fold_cap,
            big_blind=ctx.gs.big_blind,
            hero_made_rank=meta.get("hero_made_rank"),
            line_context=line_context,
        )
        exploit_detail["select_action_ms"] = round((time.perf_counter() - select_t0) * 1000.0, 1)
        timing["exploit_select_ms"] = round((time.perf_counter() - exploit_t0) * 1000.0, 1)
        timing["exploit_detail"] = exploit_detail
        selected_label = selection["selected_label"]
        selected_prob = float(selection.get("selected_prob", strategy.get(selected_label, 0.0)))
        action_t0 = time.perf_counter()
        action = self._action_from_solver_label(
            selected_label,
            gs=ctx.gs,
            hero_player_id=ctx.hero_player_id,
        )
        timing["action_convert_ms"] = round((time.perf_counter() - action_t0) * 1000.0, 1)
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        timing["total_ms"] = round(elapsed_ms, 1)
        if action is None:
            reason = f"unsupported_solver_action:{selected_label}"
            self._last_error = reason
            self._last_result = {
                **meta,
                "status": "fallback",
                "reason": reason,
                "elapsed_ms": elapsed_ms,
                "timing": timing,
            }
            return None

        self._last_result = {
            **meta,
            "status": "ok",
            "elapsed_ms": elapsed_ms,
            "timing": timing,
            "exploitability_pct": result.get("exploitability_pct"),
            "node_path": (result.get("node") or {}).get("path"),
            "node_player": (result.get("node") or {}).get("player"),
            "node_actions": list((result.get("node") or {}).get("actions") or []),
            "strategy": {k: round(float(v), 6) for k, v in strategy.items()},
            "action_evs_bb": {
                k: round(float(v), 4)
                for k, v in (selection.get("action_evs_bb") or {}).items()
            },
            "exploit": selection.get("exploit") or {},
            "selected_label": selected_label,
            "selected_prob": round(float(selected_prob), 6),
            "action": action.action_type.name.lower(),
            "amount": float(action.amount or 0.0),
        }
        if result.get("path_matches"):
            self._last_result["path_matches"] = result.get("path_matches")
        return action

    def _exploit_profile(self, ctx: RealtimeCFRDecisionContext, villain_id: int) -> Any:
        if ctx.villain_profile_provider is None:
            return None
        try:
            return ctx.villain_profile_provider(int(villain_id))
        except Exception:
            return None

    def _exploit_adjustments(
        self,
        ctx: RealtimeCFRDecisionContext,
        villain_id: int,
    ) -> dict[str, Any]:
        if ctx.exploit_adjustments_provider is None:
            return {}
        try:
            raw = ctx.exploit_adjustments_provider(int(villain_id))
        except Exception:
            return {}
        return raw if isinstance(raw, dict) else {}

    def _range_v2_prior(
        self,
        ctx: RealtimeCFRDecisionContext,
        villain_id: int,
    ) -> dict[str, Any]:
        if ctx.range_v2_prior_provider is None:
            return {}
        try:
            raw = ctx.range_v2_prior_provider(int(villain_id))
        except Exception:
            return {}
        return raw if isinstance(raw, dict) else {}

    def _accuracy(self, street: str) -> float:
        return self.options.turn_accuracy if street == "turn" else self.options.river_accuracy

    def _prepare(
        self,
        ctx: RealtimeCFRDecisionContext,
    ) -> Optional[tuple[RealtimeCFRState, dict[str, Any]]]:
        gs = ctx.gs
        street = str(gs.street).lower()
        if street not in {"turn", "river"}:
            self._fallback("street_not_supported", street=street)
            return None
        if len(gs.board) not in {4, 5}:
            self._fallback("board_length_not_supported", street=street, board_len=len(gs.board))
            return None
        if street == "turn" and len(gs.board) != 4:
            self._fallback("turn_requires_four_board_cards", board_len=len(gs.board))
            return None
        if street == "river" and len(gs.board) != 5:
            self._fallback("river_requires_five_board_cards", board_len=len(gs.board))
            return None

        hero = _player_by_id(gs.players, ctx.hero_player_id)
        if hero is None or hero.is_folded or len(hero.hole_cards) < 2:
            self._fallback("hero_missing_or_folded", street=street)
            return None

        active = [p for p in gs.active_players if not p.is_all_in]
        if len(active) != 2:
            self._fallback("requires_heads_up_active_players", street=street, active_count=len(active))
            return None
        villain = next((p for p in active if p.player_id != hero.player_id), None)
        if villain is None:
            self._fallback("villain_missing", street=street)
            return None

        hero_is_ip = gs.is_ip(hero)
        oop = villain if hero_is_ip else hero
        ip = hero if hero_is_ip else villain

        prefix = self._prefix_from_history(
            gs.action_history,
            street=street,
            oop_id=oop.player_id,
            ip_id=ip.player_id,
            big_blind=gs.big_blind,
        )
        if prefix is None:
            return None
        if prefix["next_actor_id"] != hero.player_id:
            self._fallback(
                "prefix_next_actor_is_not_hero",
                street=street,
                next_actor_id=prefix["next_actor_id"],
                hero_player_id=hero.player_id,
            )
            return None

        board = "".join(str(c) for c in gs.board)
        board_known_cards = {hcm.card_to_int(c) for c in list(gs.board)}
        villain_known_cards = {
            hcm.card_to_int(c) for c in list(gs.board) + list(hero.hole_cards)
        }
        hero_combo = f"{hero.hole_cards[0]}{hero.hole_cards[1]}"

        try:
            if oop.player_id == hero.player_id:
                oop_range = self._hero_range(
                    ctx,
                    hero=hero,
                    known_cards=board_known_cards,
                    side_player_id=oop.player_id,
                )
            else:
                oop_range = self._villain_range(
                    ctx.range_provider(oop.player_id),
                    villain_known_cards,
                )
            if ip.player_id == hero.player_id:
                ip_range = self._hero_range(
                    ctx,
                    hero=hero,
                    known_cards=board_known_cards,
                    side_player_id=ip.player_id,
                )
            else:
                ip_range = self._villain_range(
                    ctx.range_provider(ip.player_id),
                    villain_known_cards,
                )
        except Exception as exc:
            self._fallback("range_build_failed", street=street, reason=str(exc))
            return None

        if not oop_range or not ip_range:
            self._fallback("empty_solver_range", street=street)
            return None

        bb = max(float(gs.big_blind or 0.0), 1e-9)
        pot_bb = max(0.0, float(ctx.street_start_pot or 0.0)) / bb
        effective_stack = min(
            float(oop.stack or 0.0) + float(oop.current_bet or 0.0),
            float(ip.stack or 0.0) + float(ip.current_bet or 0.0),
        )
        effective_stack_bb = max(0.0, effective_stack / bb)
        if pot_bb <= 0.0 or effective_stack_bb <= 0.0:
            self._fallback(
                "invalid_pot_or_stack",
                street=street,
                pot_bb=pot_bb,
                effective_stack_bb=effective_stack_bb,
            )
            return None

        meta = {
            "engine": "realtime_cfr",
            "street": street,
            "board": board,
            "hero_player_id": int(hero.player_id),
            "villain_player_id": int(villain.player_id),
            "hero_side": "ip" if hero_is_ip else "oop",
            "hero_combo": hero_combo,
            "hero_made_rank": _hero_made_rank(hero.hole_cards, gs.board),
            "pot_bb": round(pot_bb, 4),
            "effective_stack_bb": round(effective_stack_bb, 4),
            "prefix": list(prefix["prefix"]),
            "range_counts": {
                "oop": _range_entry_count(oop_range),
                "ip": _range_entry_count(ip_range),
            },
            "timeout_sec": float(self.options.timeout_sec),
            "max_iterations": int(self.options.max_iterations),
        }
        state = RealtimeCFRState(
            board=board,
            oop_range=oop_range,
            ip_range=ip_range,
            pot_bb=pot_bb,
            effective_stack_bb=effective_stack_bb,
            prefix=list(prefix["prefix"]),
        )
        return state, meta

    def _hero_range(
        self,
        ctx: RealtimeCFRDecisionContext,
        *,
        hero: Player,
        known_cards: set[int],
        side_player_id: int,
    ) -> str:
        if ctx.hero_range_provider is not None:
            weights = ctx.hero_range_provider(side_player_id)
            if weights is not None:
                range_text = self._weights_to_range(weights, known_cards, hero=hero)
                if range_text:
                    return range_text
        return f"{hero.hole_cards[0]}{hero.hole_cards[1]}"

    def _villain_range(self, weights: Any, known_cards: set[int]) -> str:
        return self._weights_to_range(weights, known_cards, hero=None)

    def _weights_to_range(
        self,
        weights: Any,
        known_cards: set[int],
        *,
        hero: Optional[Player],
    ) -> str:
        blocked = hcm.blocked_by(known_cards)
        entries: list[str] = []
        total = 0.0
        values: list[tuple[str, float]] = []
        for idx, raw in enumerate(weights):
            if idx >= len(hcm.ALL_COMBOS):
                break
            try:
                weight = float(raw or 0.0)
            except (TypeError, ValueError):
                continue
            if weight <= self.options.min_combo_weight:
                continue
            if blocked[idx]:
                c1, c2 = hcm.cards_of(idx)
                if hero is None or {hcm.card_to_int(c1), hcm.card_to_int(c2)} != {
                    hcm.card_to_int(hero.hole_cards[0]),
                    hcm.card_to_int(hero.hole_cards[1]),
                }:
                    continue
            c1, c2 = hcm.cards_of(idx)
            combo = self._solver_combo_label(c1, c2)
            values.append((combo, weight))
            total += weight
        if total <= 1e-15:
            return ""
        for combo, weight in values:
            norm = weight / total
            if abs(norm - 1.0) <= 1e-12 and len(values) == 1:
                entries.append(combo)
            else:
                entries.append(f"{combo}:{_format_solver_weight(norm)}")
        return ",".join(entries)

    @staticmethod
    def _solver_combo_label(c1: Any, c2: Any) -> str:
        if int(getattr(c2, "rank", 0)) > int(getattr(c1, "rank", 0)):
            c1, c2 = c2, c1
        return f"{c1}{c2}"

    def _prefix_from_history(
        self,
        history: Sequence[Any],
        *,
        street: str,
        oop_id: int,
        ip_id: int,
        big_blind: float,
    ) -> Optional[dict[str, Any]]:
        actor = int(oop_id)
        other = int(ip_id)
        current_to = 0.0
        prefix: list[tuple[str, float]] = []
        bb = max(float(big_blind or 0.0), 1e-9)

        for item in history:
            if len(item) < 3 or str(item[2]).lower() != street:
                continue
            pid, action = int(item[0]), item[1]
            action_type = getattr(action, "action_type", None)
            if pid not in {int(oop_id), int(ip_id)}:
                if action_type == ActionType.FOLD:
                    continue
                self._fallback("prefix_unknown_player", street=street, player_id=pid)
                return None
            if pid != actor:
                self._fallback(
                    "prefix_actor_mismatch",
                    street=street,
                    expected_actor_id=actor,
                    actual_player_id=pid,
                )
                return None

            if action_type == ActionType.CHECK:
                prefix.append(("check", 0.0))
            elif action_type == ActionType.CALL:
                prefix.append(("call", current_to / bb))
            elif action_type == ActionType.FOLD:
                self._fallback("prefix_contains_fold", street=street)
                return None
            elif action_type == ActionType.RAISE:
                amount = max(0.0, float(getattr(action, "amount", 0.0) or 0.0))
                if amount <= current_to + 1e-9:
                    self._fallback("prefix_non_increasing_raise", street=street, amount=amount)
                    return None
                kind = "bet" if current_to <= 1e-9 else "raise"
                current_to = amount
                prefix.append((kind, amount / bb))
            else:
                self._fallback("prefix_unknown_action", street=street, action=str(action_type))
                return None

            actor, other = other, actor

        return {"prefix": prefix, "next_actor_id": actor}

    def _action_from_solver_label(
        self,
        label: str,
        *,
        gs: GameState,
        hero_player_id: int,
    ) -> Optional[Action]:
        hero = _player_by_id(gs.players, hero_player_id)
        if hero is None:
            return None
        to_call = gs.to_call(hero)
        match = _ACTION_RE.match(label)
        if match is None:
            return None
        kind, raw_amount = match.group(1), match.group(2)
        if kind == "Fold":
            return Action(ActionType.FOLD if to_call > 0 else ActionType.CHECK, 0.0)
        if kind == "Check":
            return Action(ActionType.CHECK if to_call <= 0 else ActionType.CALL, 0.0)
        if kind == "Call":
            return Action(ActionType.CALL if to_call > 0 else ActionType.CHECK, 0.0)
        if kind in {"Bet", "Raise", "AllIn"}:
            if raw_amount is None:
                return None
            amount_bb = int(raw_amount) / 10.0
            total_bet = amount_bb * float(gs.big_blind or 0.0)
            max_total = float(hero.current_bet or 0.0) + float(hero.stack or 0.0)
            total_bet = min(max_total, max(0.0, total_bet))
            if total_bet <= float(gs.current_bet or 0.0) + 1e-9:
                return Action(ActionType.CALL if to_call > 0 else ActionType.CHECK, 0.0)
            return Action(ActionType.RAISE, total_bet)
        return None

    def _fallback(self, reason: str, **extra: Any) -> None:
        self._last_error = reason
        self._last_result = {
            "engine": "realtime_cfr",
            "status": "fallback",
            "reason": reason,
            **extra,
        }


def _set_realtime_solver_error(
    reason: str = "",
    detail: Optional[dict[str, Any]] = None,
) -> None:
    solve_realtime_cfr.last_error = reason
    solve_realtime_cfr.last_error_detail = dict(detail or {})


def _short_text(value: Any, limit: int = 1200) -> str:
    text = str(value or "")
    if len(text) <= limit:
        return text
    return text[:limit] + "...<truncated>"


def _expected_path_debug(expect: Sequence[tuple[str, Optional[int]]]) -> list[str]:
    out: list[str] = []
    for kind, chips in expect:
        out.append(str(kind) if chips is None else f"{kind}({chips})")
    return out


def _format_solver_weight(value: float) -> str:
    text = f"{max(0.0, float(value)):.18f}".rstrip("0").rstrip(".")
    return text or "0"


def solve_realtime_cfr(
    state: RealtimeCFRState,
    *,
    accuracy: float,
    max_iterations: int,
    timeout_sec: float,
    threads: int = 0,
    solver_lib_path: Optional[str] = None,
) -> Optional[dict[str, Any]]:
    t0 = time.perf_counter()
    timing: dict[str, float] = {}
    _set_realtime_solver_error()
    resolve_t0 = time.perf_counter()
    solver_path = _resolve_solver_lib_path(solver_lib_path)
    timing["resolve_solver_ms"] = round((time.perf_counter() - resolve_t0) * 1000.0, 1)
    if solver_path is None:
        _set_realtime_solver_error(
            "solver_library_missing",
            {"configured_solver_lib": str(solver_lib_path or ""), "timing": dict(timing)},
        )
        return None

    args_t0 = time.perf_counter()
    try:
        args, expect = _build_solver_args(state, accuracy, max_iterations)
    except Exception as exc:
        _set_realtime_solver_error(
            "solver_args_build_failed",
            {"error": str(exc), "timing": dict(timing)},
        )
        return None
    timing["build_args_ms"] = round((time.perf_counter() - args_t0) * 1000.0, 1)

    ctx = get_context("spawn")
    q = ctx.Queue()
    proc = ctx.Process(
        target=_solver_worker,
        args=(json.dumps(args), int(threads or 0), solver_path, q),
        daemon=True,
    )
    start_t0 = time.perf_counter()
    try:
        proc.start()
    except Exception as exc:
        _set_realtime_solver_error(
            "solver_worker_start_failed",
            {"error": str(exc), "solver_lib": str(solver_path), "timing": dict(timing)},
        )
        return None
    timing["worker_start_ms"] = round((time.perf_counter() - start_t0) * 1000.0, 1)

    wait_t0 = time.perf_counter()
    try:
        msg = q.get(timeout=max(0.05, float(timeout_sec)))
    except Exception:
        timing["worker_wait_ms"] = round((time.perf_counter() - wait_t0) * 1000.0, 1)
        alive = proc.is_alive()
        if alive:
            proc.terminate()
        proc.join(1.0)
        _set_realtime_solver_error(
            "solver_timeout" if alive else "solver_worker_exited_no_message",
            {
                "timeout_sec": float(timeout_sec),
                "exitcode": proc.exitcode,
                "timing": dict(timing),
            },
        )
        return None
    finally:
        if proc.is_alive():
            proc.join(0.25)
    timing["worker_wait_ms"] = round((time.perf_counter() - wait_t0) * 1000.0, 1)

    if not isinstance(msg, dict):
        if proc.is_alive():
            proc.terminate()
            proc.join(1.0)
        _set_realtime_solver_error(
            "solver_worker_bad_message",
            {"message_type": type(msg).__name__, "exitcode": proc.exitcode, "timing": dict(timing)},
        )
        return None

    if not msg.get("ok"):
        if proc.is_alive():
            proc.terminate()
            proc.join(1.0)
        _set_realtime_solver_error(
            "solver_worker_error",
            {
                "error": _short_text(msg.get("error")),
                "traceback": _short_text(msg.get("traceback")),
                "exitcode": proc.exitcode,
                "timing": dict(timing),
            },
        )
        return None

    json_t0 = time.perf_counter()
    try:
        out = json.loads(str(msg.get("result") or "{}"))
    except Exception as exc:
        _set_realtime_solver_error(
            "solver_result_json_error",
            {
                "error": str(exc),
                "result_prefix": _short_text(msg.get("result"), 800),
                "exitcode": proc.exitcode,
                "timing": dict(timing),
            },
        )
        return None
    timing["json_decode_ms"] = round((time.perf_counter() - json_t0) * 1000.0, 1)

    parse_t0 = time.perf_counter()
    try:
        path_matches: list[dict[str, Any]] = []
        node = _locate_node(out.get("nodes") or [], expect, path_matches=path_matches)
        if node is None:
            root = next(
                (
                    n
                    for n in list(out.get("nodes") or [])
                    if isinstance(n, dict) and str(n.get("path")) == "r"
                ),
                {},
            )
            _set_realtime_solver_error(
                "solver_node_not_found",
                {
                    "expected_path": _expected_path_debug(expect),
                    "path_matches": path_matches,
                    "node_count": len(list(out.get("nodes") or [])),
                    "root_actions": list(root.get("actions") or [])[:20]
                    if isinstance(root, dict)
                    else [],
                    "timing": dict(timing),
                },
            )
            return None
        starting_pot = max(1, int(args["starting_pot"]))
        timing["result_parse_ms"] = round((time.perf_counter() - parse_t0) * 1000.0, 1)
        timing["total_ms"] = round((time.perf_counter() - t0) * 1000.0, 1)
        return {
            "node": node,
            "nodes": out.get("nodes") or [],
            "oop_hands": out.get("oop_hands") or [],
            "ip_hands": out.get("ip_hands") or [],
            "exploitability_pct": float(out.get("exploitability") or 0.0) / starting_pot * 100.0,
            "street": _street_of_state(state),
            "path_matches": path_matches,
            "timing": dict(timing),
        }
    except Exception as exc:
        timing["result_parse_ms"] = round((time.perf_counter() - parse_t0) * 1000.0, 1)
        _set_realtime_solver_error(
            "solver_result_parse_error",
            {
                "error": str(exc),
                "traceback": _short_text(traceback.format_exc()),
                "timing": dict(timing),
            },
        )
        return None


solve_realtime_cfr.last_error = ""
solve_realtime_cfr.last_error_detail = {}


def hand_strategy(result: dict[str, Any], hero_cards: str) -> Optional[dict[str, float]]:
    node = result.get("node") or {}
    hands = result.get("oop_hands") if node.get("player") == 0 else result.get("ip_hands")
    if not isinstance(hands, list):
        return None
    c1, c2 = hero_cards[:2], hero_cards[2:]
    idx = None
    for candidate in (c1 + c2, c2 + c1):
        try:
            idx = hands.index(candidate)
            break
        except ValueError:
            continue
    if idx is None:
        return None
    actions = list(node.get("actions") or [])
    strategy = list(node.get("strategy") or [])
    try:
        num_hands = int(node.get("num_hands") or len(hands))
    except (TypeError, ValueError):
        num_hands = len(hands)
    if not actions or num_hands <= 0:
        return None
    out: dict[str, float] = {}
    for action_idx, label in enumerate(actions):
        pos = action_idx * num_hands + idx
        if pos >= len(strategy):
            return None
        out[str(label)] = float(strategy[pos])
    total = sum(max(0.0, v) for v in out.values())
    if total <= 1e-12:
        return None
    return {label: max(0.0, prob) / total for label, prob in out.items()}


def _select_exploit_action(
    result: dict[str, Any],
    *,
    hero_combo: str,
    hero_side: str,
    street: str,
    gto_strategy: dict[str, float],
    profile: Any,
    adjustments: dict[str, Any],
    max_confidence: float,
    enabled: bool,
    defense_fold_cap: Optional[float] = None,
    big_blind: Any = None,
    hero_made_rank: Any = None,
    line_context: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    gto_label, gto_prob = _select_strategy_action(gto_strategy)
    out: dict[str, Any] = {
        "selected_label": gto_label,
        "selected_prob": gto_prob,
        "exploit": {"enabled": bool(enabled), "used": False},
    }
    if not enabled:
        return out

    node = result.get("node") or {}
    hero_idx = _hand_index(result, hero_side, hero_combo)
    if hero_idx is None:
        return out
    gto_evs = _node_hand_values(node, "evs", hero_idx)
    if not gto_evs:
        return out

    line_context = dict(line_context or {})
    numeric_prior = build_numeric_prior(profile, adjustments, street, big_blind)
    confidence = _exploit_confidence(
        profile,
        adjustments,
        street,
        max_confidence,
        line_context=line_context,
        numeric_prior=numeric_prior,
    )
    if confidence <= 1e-6:
        out["action_evs_bb"] = gto_evs
        return out
    signal = _exploit_signal_strength(
        profile,
        adjustments,
        street,
        line_context=line_context,
        numeric_prior=numeric_prior,
    )
    if signal <= 1e-9:
        out["action_evs_bb"] = gto_evs
        out["exploit"].update({
            "confidence": round(confidence, 4),
            "numeric_prior": numeric_prior.diagnostics,
            "reason": "no_profile_bias",
        })
        return out

    by_path = {
        str(n.get("path")): n
        for n in list(result.get("nodes") or [])
        if isinstance(n, dict)
    }
    current_path = str(node.get("path") or "r")
    final: dict[str, float] = {}
    adjusted_evs: dict[str, float] = {}
    response_summaries: dict[str, Any] = {}
    safety: dict[str, Any] = {}
    best_gto_ev = max(gto_evs.values())
    passive_gto_evs = {
        label: value
        for label, value in gto_evs.items()
        if _action_kind(label) in {"Fold", "Check", "Call"}
    }
    best_passive_gto_ev = max(passive_gto_evs.values(), default=best_gto_ev)

    for label, gto_ev in gto_evs.items():
        child = by_path.get(f"{current_path}:{label}")
        response_detail = _response_adjusted_ev_detail_from_result(
            result,
            child,
            hero_combo=hero_combo,
            hero_side=hero_side,
            profile=profile,
            adjustments=adjustments,
            street=street,
            hero_action_label=label,
            line_context=line_context,
            numeric_prior=numeric_prior,
        )
        if response_detail is None:
            adj_ev = gto_ev + _direct_exploit_delta(
                label,
                profile=profile,
                adjustments=adjustments,
                street=street,
                line_context=line_context,
                numeric_prior=numeric_prior,
                hero_made_rank=hero_made_rank,
            )
            response_detail = {}
        else:
            adj_ev = float(response_detail["ev"])
        adjusted_evs[label] = adj_ev
        final_ev = (1.0 - confidence) * gto_ev + confidence * adj_ev
        risk = _river_aggression_risk_discount(
            label,
            street=street,
            line_context=line_context,
            response_detail=response_detail,
            best_passive_gto_ev=best_passive_gto_ev,
            hero_combo=hero_combo,
            hero_made_rank=hero_made_rank,
            numeric_prior=numeric_prior,
        )
        if risk:
            discount = float(risk.get("discount_bb") or 0.0)
            if discount > 0.0:
                final_ev -= discount
                safety.setdefault("river_aggression_risk", []).append(risk)
        turn_risk = _turn_barrel_quality_discount(
            label,
            street=street,
            line_context=line_context,
            response_detail=response_detail,
            best_passive_gto_ev=best_passive_gto_ev,
            hero_combo=hero_combo,
            hero_made_rank=hero_made_rank,
            numeric_prior=numeric_prior,
        )
        if turn_risk:
            discount = float(turn_risk.get("discount_bb") or 0.0)
            if discount > 0.0:
                final_ev -= discount
                safety.setdefault("turn_barrel_quality", []).append(turn_risk)
        large_support = _large_size_support_check(
            label,
            street=street,
            line_context=line_context,
            response_detail=response_detail,
            best_passive_gto_ev=best_passive_gto_ev,
            gto_ev=gto_ev,
            hero_combo=hero_combo,
            hero_made_rank=hero_made_rank,
            numeric_prior=numeric_prior,
        )
        if large_support:
            discount = float(large_support.get("discount_bb") or 0.0)
            if discount > 0.0:
                final_ev -= discount
            safety.setdefault("large_size_support", []).append(large_support)
        raise_exposure = _raise_exposure_risk_discount(
            label,
            street=street,
            line_context=line_context,
            response_detail=response_detail,
            best_passive_gto_ev=best_passive_gto_ev,
            hero_combo=hero_combo,
            hero_made_rank=hero_made_rank,
            numeric_prior=numeric_prior,
        )
        if raise_exposure:
            discount = float(raise_exposure.get("discount_bb") or 0.0)
            if discount > 0.0:
                final_ev -= discount
            safety.setdefault("raise_exposure_risk", []).append(raise_exposure)
        calloff_risk = _calloff_risk_discount(
            label,
            street=street,
            line_context=line_context,
            gto_ev=gto_ev,
            best_passive_gto_ev=best_passive_gto_ev,
            hero_combo=hero_combo,
            hero_made_rank=hero_made_rank,
            numeric_prior=numeric_prior,
        )
        if calloff_risk:
            discount = float(calloff_risk.get("discount_bb") or 0.0)
            if discount > 0.0:
                final_ev -= discount
            safety.setdefault("calloff_risk", []).append(calloff_risk)
        strict_gate = _strict_bluff_aggression_gate(
            label,
            street=street,
            line_context=line_context,
            response_detail=response_detail,
            hero_combo=hero_combo,
            hero_made_rank=hero_made_rank,
            numeric_prior=numeric_prior,
        )
        if strict_gate:
            safety.setdefault("strict_bluff_gate", []).append(strict_gate)
        sticky_aggression = _sticky_aggression_discount(
            label,
            street=street,
            line_context=line_context,
            response_detail=response_detail,
            best_passive_gto_ev=best_passive_gto_ev,
            hero_combo=hero_combo,
            hero_made_rank=hero_made_rank,
            numeric_prior=numeric_prior,
        )
        if sticky_aggression:
            discount = float(sticky_aggression.get("discount_bb") or 0.0)
            if discount > 0.0:
                final_ev -= discount
            safety.setdefault("sticky_aggression", []).append(sticky_aggression)
        gto_gap = max(0.0, best_gto_ev - gto_ev)
        leash = 0.6 + 2.0 * confidence
        if gto_gap > leash and final_ev > best_gto_ev:
            final_ev = best_gto_ev - 1e-4
            safety.setdefault("gto_leash", []).append({
                "action": label,
                "gto_gap_bb": round(gto_gap, 4),
                "leash_bb": round(leash, 4),
            })
        final[label] = final_ev
        if child is not None:
            summary = _response_summary(
                child,
                profile,
                adjustments,
                street,
                hero_action_label=label,
                line_context=line_context,
                numeric_prior=numeric_prior,
            )
            if summary is not None:
                response_summaries[label] = summary

    _apply_hard_action_blocks(final, safety)
    selected_label = max(final.items(), key=lambda item: (item[1], gto_strategy.get(item[0], 0.0)))[0]
    selected_label = _apply_gto_ev_floor(
        selected_label,
        final,
        gto_evs,
        gto_strategy,
        confidence,
        safety,
    )
    selected_label = _apply_overvalue_cheap_call_guard(
        selected_label,
        final,
        gto_evs,
        prior=numeric_prior,
        street=street,
        line_context=line_context,
        hero_made_rank=hero_made_rank,
        confidence=confidence,
        safety=safety,
    )
    final_probs = _softmax_from_evs(final)
    selected_label, final_probs = _apply_defense_mdf_guard(
        selected_label,
        final,
        final_probs,
        defense_fold_cap=defense_fold_cap,
        confidence=confidence,
        safety=safety,
    )
    if not safety:
        safety = {"applied": False}
    out.update({
        "selected_label": selected_label,
        "selected_prob": final_probs.get(selected_label, gto_strategy.get(selected_label, 0.0)),
        "action_evs_bb": gto_evs,
        "exploit": {
            "enabled": True,
            "used": True,
            "confidence": round(confidence, 4),
            "numeric_prior": numeric_prior.diagnostics,
            "gto_action_evs_bb": {k: round(v, 4) for k, v in gto_evs.items()},
            "adjusted_action_evs_bb": {k: round(v, 4) for k, v in adjusted_evs.items()},
            "final_action_evs_bb": {k: round(v, 4) for k, v in final.items()},
            "final_strategy": {k: round(v, 6) for k, v in final_probs.items()},
            "response_summaries": response_summaries,
            "line_context": _public_line_context(line_context),
            "safety": safety,
        },
    })
    return out


def _exploit_signal_strength(
    profile: Any,
    adjustments: dict[str, Any],
    street: str,
    *,
    line_context: Optional[dict[str, Any]] = None,
    numeric_prior: Optional[NumericOpponentPrior] = None,
) -> float:
    prior = numeric_prior or build_numeric_prior(profile, adjustments, street)
    fold_bias, sticky_bias, raise_bias = _response_biases(
        profile,
        adjustments,
        street,
        numeric_prior=prior,
    )
    bluff_signal = abs(float(adjustments.get("bluff_ag_scale", 0.55) or 0.55) - 0.55)
    value_signal = abs(float(adjustments.get("value_ag_scale", 0.85) or 0.85) - 0.85)
    flag_signal = 0.0
    if adjustments.get("river_bluff_likely"):
        flag_signal = max(flag_signal, 0.35)
    if adjustments.get("river_bet_rare"):
        flag_signal = max(flag_signal, 0.20)
    line_signal = _line_signal_strength(str(street).lower(), line_context or {})
    range_v2_signal = _range_v2_signal_strength(line_context)
    return max(
        abs(fold_bias),
        abs(sticky_bias),
        abs(raise_bias),
        prior.underbluff_score,
        prior.fold_lean_score,
        prior.sticky_score,
        prior.pressure_score,
        bluff_signal,
        value_signal,
        flag_signal,
        line_signal,
        range_v2_signal,
    )


def _apply_gto_ev_floor(
    selected_label: str,
    final_evs: dict[str, float],
    gto_evs: dict[str, float],
    gto_strategy: dict[str, float],
    confidence: float,
    safety: dict[str, Any],
) -> str:
    if not selected_label or not final_evs or not gto_evs:
        return selected_label
    best_gto_ev = max(gto_evs.values())
    floor_bb = 0.5 + 2.0 * max(0.0, float(confidence or 0.0))
    selected_gto_ev = gto_evs.get(selected_label)
    if selected_gto_ev is None or selected_gto_ev >= best_gto_ev - floor_bb:
        return selected_label
    blocked = _safety_discounted_actions(safety)
    eligible = {
        label: value
        for label, value in final_evs.items()
        if gto_evs.get(label, -1e9) >= best_gto_ev - floor_bb
        and label not in blocked
    }
    if not eligible:
        return selected_label
    replacement = max(
        eligible.items(),
        key=lambda item: (item[1], gto_strategy.get(item[0], 0.0)),
    )[0]
    if replacement != selected_label:
        safety["gto_ev_floor"] = {
            "from": selected_label,
            "to": replacement,
            "selected_gto_gap_bb": round(best_gto_ev - selected_gto_ev, 4),
            "floor_bb": round(floor_bb, 4),
        }
    return replacement


def _apply_hard_action_blocks(final_evs: dict[str, float], safety: dict[str, Any]) -> None:
    if not final_evs or not safety:
        return
    blocked = _safety_hard_blocked_actions(safety)
    if not blocked:
        return
    eligible = {
        label: value
        for label, value in final_evs.items()
        if label not in blocked
    }
    if not eligible:
        return
    best_eligible = max(eligible.values())
    for label, penalty_bb in blocked.items():
        if label not in final_evs:
            continue
        final_evs[label] = min(final_evs[label], best_eligible - max(0.25, penalty_bb))


def _safety_hard_blocked_actions(safety: dict[str, Any]) -> dict[str, float]:
    blocked: dict[str, float] = {}
    for key in ("strict_bluff_gate", "large_size_support", "raise_exposure_risk", "sticky_aggression"):
        for item in list(safety.get(key) or []):
            if not isinstance(item, dict) or not item.get("blocked"):
                continue
            action = str(item.get("action") or "")
            if not action:
                continue
            penalty = max(0.0, float(item.get("penalty_bb") or 0.0))
            blocked[action] = max(blocked.get(action, 0.0), penalty)
    return blocked


def _safety_discounted_actions(safety: dict[str, Any]) -> set[str]:
    blocked: set[str] = set(_safety_hard_blocked_actions(safety))
    for key in (
        "river_aggression_risk",
        "turn_barrel_quality",
        "large_size_support",
        "raise_exposure_risk",
        "calloff_risk",
        "sticky_aggression",
    ):
        for item in list(safety.get(key) or []):
            if not isinstance(item, dict):
                continue
            if float(item.get("discount_bb") or 0.0) > 1e-9:
                action = str(item.get("action") or "")
                if action:
                    blocked.add(action)
    return blocked


def _apply_overvalue_cheap_call_guard(
    selected_label: str,
    final_evs: dict[str, float],
    gto_evs: dict[str, float],
    *,
    prior: NumericOpponentPrior,
    street: str,
    line_context: dict[str, Any],
    hero_made_rank: Any,
    confidence: float,
    safety: dict[str, Any],
) -> str:
    if str(street).lower() != "river" or selected_label != "Fold":
        return selected_label
    if "Call" not in final_evs or "Call" not in gto_evs or "Fold" not in gto_evs:
        return selected_label
    if "Call" in _safety_discounted_actions(safety):
        return selected_label

    made_strength = _made_hand_strength(hero_made_rank)
    if made_strength < 0.55:
        return selected_label

    price = _call_price_features(line_context)
    pot_odds = price["pot_odds"]
    cheapness = price["cheapness"]
    if pot_odds <= 0.0 or pot_odds > 0.25 or cheapness <= 0.0:
        return selected_label

    overvalue = float(prior.overvalue_score)
    nut_heavy = float(prior.nut_heavy_score)
    if overvalue <= max(0.35, nut_heavy + 0.08):
        return selected_label

    fold_gto = float(gto_evs["Fold"])
    call_gto = float(gto_evs["Call"])
    fold_final = float(final_evs.get("Fold", fold_gto))
    call_final = float(final_evs.get("Call", call_gto))

    gto_tolerance = (
        0.25
        + 1.10 * cheapness
        + 0.55 * made_strength
        + 0.65 * overvalue
        - 0.75 * nut_heavy
    )
    if call_gto < fold_gto - max(0.20, gto_tolerance):
        return selected_label

    final_tolerance = (
        0.12
        + 0.75 * cheapness
        + 0.50 * made_strength
        + 0.55 * overvalue
        + 0.25 * max(0.0, float(confidence or 0.0))
        - 0.70 * nut_heavy
    )
    ev_gap = fold_final - call_final
    if ev_gap > max(0.12, final_tolerance):
        return selected_label

    safety["overvalue_cheap_call_guard"] = {
        "from": "Fold",
        "to": "Call",
        "pot_odds": round(pot_odds, 4),
        "cheapness": round(cheapness, 4),
        "made_strength": round(made_strength, 4),
        "overvalue": round(overvalue, 4),
        "nut_heavy": round(nut_heavy, 4),
        "gto_gap_bb": round(fold_gto - call_gto, 4),
        "final_gap_bb": round(ev_gap, 4),
        "gto_tolerance_bb": round(max(0.20, gto_tolerance), 4),
        "final_tolerance_bb": round(max(0.12, final_tolerance), 4),
    }
    return "Call"


def _apply_defense_mdf_guard(
    selected_label: str,
    final_evs: dict[str, float],
    final_probs: dict[str, float],
    *,
    defense_fold_cap: Optional[float],
    confidence: float,
    safety: dict[str, Any],
) -> tuple[str, dict[str, float]]:
    if defense_fold_cap is None or "Fold" not in final_probs:
        return selected_label, final_probs
    cap = _clamp(float(defense_fold_cap), 0.0, 1.0)
    fold_prob = max(0.0, float(final_probs.get("Fold", 0.0)))
    if fold_prob <= cap + 1e-12:
        return selected_label, final_probs

    capped = dict(final_probs)
    excess = fold_prob - cap
    capped["Fold"] = cap
    continuations = {
        label: prob
        for label, prob in final_probs.items()
        if label != "Fold" and prob > 0.0
    }
    total_continue = sum(continuations.values())
    if total_continue > 1e-12:
        for label, prob in continuations.items():
            capped[label] = capped.get(label, 0.0) + excess * prob / total_continue
    norm = sum(max(0.0, v) for v in capped.values())
    if norm > 1e-12:
        capped = {label: max(0.0, value) / norm for label, value in capped.items()}

    mdf_info: dict[str, Any] = {
        "fold_prob_before": round(fold_prob, 6),
        "fold_cap": round(cap, 6),
        "fold_prob_after": round(capped.get("Fold", 0.0), 6),
        "applied": False,
    }
    if selected_label == "Fold":
        candidates = {
            label: value
            for label, value in final_evs.items()
            if label != "Fold"
            and label not in _safety_discounted_actions(safety)
        }
        if candidates:
            replacement = max(
                candidates.items(),
                key=lambda item: (item[1], capped.get(item[0], 0.0)),
            )[0]
            ev_gap = final_evs.get("Fold", 0.0) - final_evs.get(replacement, -1e9)
            tolerance = 0.25 + max(0.0, float(confidence or 0.0))
            if ev_gap <= tolerance and capped.get(replacement, 0.0) >= capped.get("Fold", 0.0):
                selected_label = replacement
                mdf_info.update({
                    "applied": True,
                    "to": replacement,
                    "ev_gap_bb": round(ev_gap, 4),
                    "tolerance_bb": round(tolerance, 4),
                })
    safety["defense_mdf"] = mdf_info
    return selected_label, capped


def _defense_fold_cap(*, pot_bb: float, to_call_bb: float) -> Optional[float]:
    if to_call_bb <= 1e-9:
        return None
    pot_before_call = max(float(pot_bb or 0.0) - float(to_call_bb or 0.0), 1e-9)
    bet_ratio = float(to_call_bb) / pot_before_call
    return min(1.0, 1.5 * bet_ratio / (1.0 + bet_ratio))


def _call_price_features(line_context: dict[str, Any]) -> dict[str, float]:
    to_call = max(0.0, float((line_context or {}).get("current_to_call_bb") or 0.0))
    pot = max(0.0, float((line_context or {}).get("current_pot_bb") or 0.0))
    if to_call <= 1e-9 or pot <= 1e-9:
        return {"pot_odds": 0.0, "cheapness": 0.0}
    pot_odds = to_call / max(pot + to_call, 1e-9)
    cheapness = _clamp((0.30 - pot_odds) / 0.18, 0.0, 1.0)
    return {"pot_odds": pot_odds, "cheapness": cheapness}


def _made_hand_strength(rank: Any) -> float:
    raw = str(rank or "").lower()
    if not raw:
        return 0.0
    if raw in {"royal_flush", "straight_flush", "four_of_a_kind", "full_house"}:
        return 1.0
    if raw in {"flush", "straight"}:
        return 0.90
    if raw == "three_of_a_kind":
        return 0.82
    if raw == "two_pair":
        return 0.74
    if raw == "one_pair":
        return 0.40
    return 0.0


def _build_line_context(
    gs: GameState,
    *,
    hero_player_id: int,
    villain_player_id: int,
) -> dict[str, Any]:
    bb = max(float(gs.big_blind or 0.0), 1e-9)
    hero = _player_by_id(gs.players, hero_player_id)
    villain = _player_by_id(gs.players, villain_player_id)
    current_street = str(gs.street).lower()
    streets = ("flop", "turn", "river")
    called_vs_hero: dict[str, bool] = {street: False for street in streets}
    hero_aggressed: dict[str, bool] = {street: False for street in streets}
    hero_max_to_bb: dict[str, float] = {street: 0.0 for street in streets}

    by_street: dict[str, list[tuple[int, Any]]] = {street: [] for street in streets}
    for item in list(gs.action_history or []):
        if len(item) < 3:
            continue
        street = str(item[2]).lower()
        if street not in by_street:
            continue
        try:
            pid = int(item[0])
        except (TypeError, ValueError):
            continue
        if pid not in {int(hero_player_id), int(villain_player_id)}:
            continue
        by_street[street].append((pid, item[1]))

    for street, actions in by_street.items():
        hero_is_current_aggressor = False
        for pid, action in actions:
            action_type = getattr(action, "action_type", None)
            if pid == int(hero_player_id) and action_type == ActionType.RAISE:
                hero_aggressed[street] = True
                hero_is_current_aggressor = True
                hero_max_to_bb[street] = max(
                    hero_max_to_bb[street],
                    max(0.0, float(getattr(action, "amount", 0.0) or 0.0)) / bb,
                )
            elif pid == int(villain_player_id) and action_type == ActionType.RAISE:
                hero_is_current_aggressor = False
            elif (
                pid == int(villain_player_id)
                and action_type == ActionType.CALL
                and hero_is_current_aggressor
            ):
                called_vs_hero[street] = True

    prior_streets = [s for s in ("flop", "turn") if streets.index(s) < streets.index(current_street)]
    call_chain = sum(1 for street in prior_streets if called_vs_hero.get(street))
    turn_to_bb = hero_max_to_bb.get("turn", 0.0)
    current_pot_bb = max(0.0, float(gs.pot or 0.0)) / bb
    estimated_turn_start_pot_bb = 0.0
    if called_vs_hero.get("turn") and turn_to_bb > 0.0:
        estimated_turn_start_pot_bb = max(0.0, current_pot_bb - 2.0 * turn_to_bb)
    turn_bet_pot_ratio = (
        turn_to_bb / max(estimated_turn_start_pot_bb, 1e-9)
        if estimated_turn_start_pot_bb > 1e-9
        else 0.0
    )
    line = {
        "street": current_street,
        "board": [str(card) for card in list(gs.board or [])],
        "hero_combo": (
            f"{hero.hole_cards[0]}{hero.hole_cards[1]}"
            if hero is not None and len(hero.hole_cards) >= 2
            else ""
        ),
        "villain_called_flop": bool(called_vs_hero.get("flop")),
        "villain_called_turn": bool(called_vs_hero.get("turn")),
        "villain_call_chain": int(call_chain),
        "hero_barrel_count": int(sum(1 for street in prior_streets if hero_aggressed.get(street))),
        "villain_called_large_turn": bool(
            called_vs_hero.get("turn")
            and (
                turn_to_bb >= max(8.0, current_pot_bb * 0.20)
                or turn_bet_pot_ratio >= 0.95
            )
        ),
        "hero_turn_bet_bb": float(turn_to_bb),
        "estimated_turn_start_pot_bb": float(estimated_turn_start_pot_bb),
        "turn_bet_pot_ratio": float(turn_bet_pot_ratio),
        "current_pot_bb": current_pot_bb,
        "current_to_call_bb": (
            max(0.0, float(gs.to_call(hero) or 0.0)) / bb if hero is not None else 0.0
        ),
        "hero_current_bet_bb": (
            max(0.0, float(hero.current_bet or 0.0)) / bb if hero is not None else 0.0
        ),
        "effective_stack_bb": (
            min(
                max(0.0, float(hero.stack or 0.0)) + max(0.0, float(hero.current_bet or 0.0)),
                max(0.0, float(villain.stack or 0.0)) + max(0.0, float(villain.current_bet or 0.0)),
            ) / bb
            if hero is not None and villain is not None
            else 0.0
        ),
    }
    return line


def _public_line_context(line_context: dict[str, Any]) -> dict[str, Any]:
    keys = {
        "street",
        "villain_called_flop",
        "villain_called_turn",
        "villain_call_chain",
        "hero_barrel_count",
        "villain_called_large_turn",
        "hero_turn_bet_bb",
        "estimated_turn_start_pot_bb",
        "turn_bet_pot_ratio",
        "current_pot_bb",
        "current_to_call_bb",
        "hero_current_bet_bb",
        "effective_stack_bb",
    }
    out: dict[str, Any] = {}
    for key in keys:
        if key in line_context:
            out[key] = line_context[key]
    rv2 = _public_range_v2_prior(line_context.get("range_v2"))
    if rv2:
        out["range_v2"] = rv2
    return out


def _public_range_v2_prior(raw: Any) -> dict[str, Any]:
    prior = raw if isinstance(raw, dict) else {}
    if not prior:
        return {}
    out: dict[str, Any] = {}
    bucket = _normalize_bucket_dist(prior.get("bucket_dist"))
    if bucket:
        out["bucket_dist"] = {k: round(v, 4) for k, v in bucket.items() if v > 1e-4}
    raw_bucket = _normalize_bucket_dist(prior.get("raw_bucket_dist"))
    if raw_bucket:
        out["raw_bucket_dist"] = {k: round(v, 4) for k, v in raw_bucket.items() if v > 1e-4}
    vs_hero = _float_map(prior.get("vs_hero"), keys=("win", "tie", "loss"))
    if vs_hero:
        out["vs_hero"] = {k: round(v, 4) for k, v in vs_hero.items()}
    raw_vs_hero = _float_map(prior.get("raw_vs_hero"), keys=("win", "tie", "loss"))
    if raw_vs_hero:
        out["raw_vs_hero"] = {k: round(v, 4) for k, v in raw_vs_hero.items()}
    cec = prior.get("cec_calibration")
    if isinstance(cec, dict):
        out["cec_calibration"] = {
            key: (
                round(float(value), 4)
                if isinstance(value, (int, float)) and not isinstance(value, bool)
                else value
            )
            for key, value in cec.items()
            if key in {
                "used",
                "source",
                "level",
                "key",
                "rows",
                "points",
                "ece",
                "raw_reliability",
                "sample_confidence",
                "bias_strength",
                "prior_strength",
                "runtime_rows",
                "files",
            }
        }
        shift = cec.get("shift")
        if isinstance(shift, dict):
            out["cec_calibration"]["shift"] = {
                str(k): round(_as_float(v, 0.0), 4)
                for k, v in shift.items()
                if abs(_as_float(v, 0.0)) > 1e-4
            }
    action_ctx = prior.get("action_context")
    if isinstance(action_ctx, dict):
        out["action_context"] = {
            key: (
                round(float(value), 4)
                if isinstance(value, (int, float)) and not isinstance(value, bool)
                else value
            )
            for key, value in action_ctx.items()
            if key in {"action", "street", "position", "is_ip", "is_raise_over", "bet_ratio", "facing_action"}
        }
    action_likelihood = prior.get("action_likelihood")
    if isinstance(action_likelihood, dict):
        compact = {
            "action": str(action_likelihood.get("action") or ""),
            "key": str(action_likelihood.get("key") or ""),
            "blend": round(_as_float(action_likelihood.get("blend"), 0.0), 4),
            "n": int(_as_float(action_likelihood.get("n"), 0.0)),
        }
        dist = action_likelihood.get("dist")
        if isinstance(dist, dict):
            compact["dist"] = {
                str(k): round(_clamp(_as_float(v, 0.0), 0.0, 1.0), 4)
                for k, v in dist.items()
            }
        out["action_likelihood"] = compact
    return out


def _range_v2_features(line_context: Optional[dict[str, Any]]) -> dict[str, float]:
    ctx = line_context if isinstance(line_context, dict) else {}
    prior = ctx.get("range_v2")
    if not isinstance(prior, dict):
        return {}
    bucket = _normalize_bucket_dist(prior.get("bucket_dist"))
    vs_hero = _float_map(prior.get("vs_hero"), keys=("win", "tie", "loss"))
    action_likelihood = prior.get("action_likelihood")
    action_ctx = prior.get("action_context")
    spot_blend = 0.0
    if isinstance(action_likelihood, dict):
        spot_blend = _clamp(_as_float(action_likelihood.get("blend"), 0.0), 0.0, 0.75)

    nuts = bucket.get("nuts", 0.0)
    strong = bucket.get("strong", 0.0)
    medium = bucket.get("medium", 0.0)
    draw = bucket.get("draw", 0.0)
    weak_draw = bucket.get("weak_draw", 0.0)
    air = bucket.get("air", 0.0)
    hero_win = vs_hero.get("win", 0.0)
    hero_tie = vs_hero.get("tie", 0.0)
    hero_loss = vs_hero.get("loss", 0.0)
    bet_ratio = 0.0
    is_raise_over = 0.0
    if isinstance(action_ctx, dict):
        bet_ratio = _as_float(action_ctx.get("bet_ratio"), 0.0)
        is_raise_over = 1.0 if bool(action_ctx.get("is_raise_over")) else 0.0

    return {
        "nuts": nuts,
        "strong": strong,
        "medium": medium,
        "draw": draw,
        "weak_draw": weak_draw,
        "air": air,
        "made_value": _clamp(nuts + strong + 0.45 * medium, 0.0, 1.0),
        "non_nut_value": _clamp(strong + 0.75 * medium, 0.0, 1.0),
        "bluff_mass": _clamp(air + draw + 0.65 * weak_draw, 0.0, 1.0),
        "hero_win": hero_win,
        "hero_tie": hero_tie,
        "hero_loss": hero_loss,
        "spot_blend": spot_blend,
        "bet_ratio": bet_ratio,
        "is_raise_over": is_raise_over,
    }


def _range_v2_signal_strength(line_context: Optional[dict[str, Any]]) -> float:
    f = _range_v2_features(line_context)
    if not f:
        return 0.0
    bucket_signal = max(
        f["made_value"],
        f["bluff_mass"],
        abs(f["nuts"] - 0.08) * 1.5,
        abs(f["air"] - 0.25),
    )
    relative_signal = abs(f["hero_win"] + 0.5 * f["hero_tie"] - f["hero_loss"])
    spot = f.get("spot_blend", 0.0) * 1.5
    raise_over = 0.10 if f.get("is_raise_over", 0.0) > 0.0 else 0.0
    size_signal = min(0.12, max(0.0, f.get("bet_ratio", 0.0) - 0.75) * 0.10)
    return _clamp(max(bucket_signal * 0.55, relative_signal * 0.70) + spot + raise_over + size_signal, 0.0, 1.0)


def _range_v2_direct_delta(
    label: str,
    *,
    street: str,
    line_context: Optional[dict[str, Any]],
    hero_made_rank: Any = None,
) -> float:
    f = _range_v2_features(line_context)
    if not f:
        return 0.0
    kind = _action_kind(label)
    price = _call_price_features(line_context or {})
    made = _made_hand_strength(hero_made_rank)
    street_l = str(street).lower()
    if kind == "Call":
        relative_edge = 0.0
        if street_l == "river" and (f["hero_win"] or f["hero_tie"] or f["hero_loss"]):
            relative_edge = f["hero_win"] + 0.45 * f["hero_tie"] - f["hero_loss"]
        bucket_edge = (
            0.55 * f["bluff_mass"]
            + 0.35 * f["non_nut_value"]
            - 0.95 * f["nuts"]
            - 0.20 * f["strong"]
        )
        edge = relative_edge if abs(relative_edge) > 1e-9 else bucket_edge
        delta = (0.16 + 0.46 * price["cheapness"]) * (0.35 + 0.65 * made) * edge
        return _clamp(delta, -0.55, 0.55)
    if kind == "Fold":
        call_delta = _range_v2_direct_delta(
            "Call",
            street=street,
            line_context=line_context,
            hero_made_rank=hero_made_rank,
        )
        return _clamp(-0.78 * call_delta, -0.45, 0.45)
    if kind in {"Bet", "Raise", "AllIn"}:
        pressure = _candidate_pressure_factor(label, line_context or {})
        foldable = f["bluff_mass"] + 0.20 * f["medium"]
        resistance = f["nuts"] + 0.62 * f["strong"] + 0.20 * f["medium"]
        delta = 0.26 * pressure * (foldable - resistance)
        return _clamp(delta, -0.40, 0.35)
    return 0.0


def _range_v2_response_multipliers(
    street: str,
    hero_action_label: str,
    line_context: dict[str, Any],
) -> dict[str, float]:
    f = _range_v2_features(line_context)
    if not f:
        return {}
    candidate = _candidate_action_context(hero_action_label, line_context)
    if candidate.get("kind") not in {"Bet", "Raise", "AllIn"}:
        return {}
    pressure = _candidate_pressure_factor(hero_action_label, line_context)
    if pressure <= 1e-9:
        return {}
    foldable = f["bluff_mass"] + 0.20 * f["medium"]
    call_region = f["strong"] + 0.80 * f["medium"] + 0.20 * f["draw"]
    raise_region = f["nuts"] + 0.18 * f["strong"]
    fold_mult = 1.0 + pressure * (0.58 * foldable - 0.52 * (f["nuts"] + f["strong"]))
    call_mult = 1.0 + pressure * (0.42 * call_region - 0.25 * f["air"])
    raise_mult = 1.0 + pressure * (0.55 * raise_region - 0.28 * f["medium"] - 0.25 * f["air"])
    return {
        "Fold": _clamp(fold_mult, 0.40, 1.75),
        "Call": _clamp(call_mult, 0.55, 1.85),
        "Check": _clamp(call_mult, 0.55, 1.85),
        "Bet": _clamp(raise_mult, 0.45, 1.90),
        "Raise": _clamp(raise_mult, 0.45, 1.90),
        "AllIn": _clamp(raise_mult, 0.45, 1.90),
    }


def _response_summary(
    child: dict[str, Any],
    profile: Any,
    adjustments: dict[str, Any],
    street: str,
    *,
    hero_action_label: Optional[str] = None,
    line_context: Optional[dict[str, Any]] = None,
    numeric_prior: Optional[NumericOpponentPrior] = None,
) -> Optional[dict[str, Any]]:
    eq_probs = _node_weighted_strategy(child)
    if not eq_probs:
        return None
    adj_probs = _adjust_response_probs(
        eq_probs,
        profile,
        adjustments,
        street,
        hero_action_label=hero_action_label,
        line_context=line_context,
        numeric_prior=numeric_prior,
    )
    candidate = _candidate_action_context(hero_action_label or "", line_context or {})
    return {
        "eq": {k: round(v, 6) for k, v in eq_probs.items()},
        "adj": {k: round(v, 6) for k, v in adj_probs.items()},
        "candidate": {
            k: round(v, 6) if isinstance(v, float) else v
            for k, v in candidate.items()
            if k in {"kind", "risk_bb", "pot_ratio", "all_in"}
        },
    }


def _response_adjusted_ev_detail_from_result(
    result: dict[str, Any],
    child: Optional[dict[str, Any]],
    *,
    hero_combo: str,
    hero_side: str,
    profile: Any,
    adjustments: dict[str, Any],
    street: str,
    hero_action_label: Optional[str] = None,
    line_context: Optional[dict[str, Any]] = None,
    numeric_prior: Optional[NumericOpponentPrior] = None,
) -> Optional[dict[str, Any]]:
    if not child:
        return None
    hero_player = 1 if hero_side == "ip" else 0
    if child.get("player") == hero_player:
        return None
    hero_idx = _hand_index(result, hero_side, hero_combo)
    if hero_idx is None:
        return None
    response_evs = _node_hand_values(
        child,
        "opponent_evs",
        hero_idx,
        num_hands_key="opponent_num_hands",
    )
    if not response_evs:
        return None
    eq_probs = _node_weighted_strategy(child)
    if not eq_probs:
        return None
    adj_probs = _adjust_response_probs(
        eq_probs,
        profile,
        adjustments,
        street,
        hero_action_label=hero_action_label,
        line_context=line_context,
        numeric_prior=numeric_prior,
    )
    total = 0.0
    weight_sum = 0.0
    for label, prob in adj_probs.items():
        if label not in response_evs:
            continue
        p = max(0.0, float(prob))
        total += p * response_evs[label]
        weight_sum += p
    if weight_sum <= 1e-12:
        return None
    return {
        "ev": total / weight_sum,
        "eq_probs": eq_probs,
        "adj_probs": adj_probs,
        "response_evs": response_evs,
    }


def _response_adjusted_ev_from_result(
    result: dict[str, Any],
    child: Optional[dict[str, Any]],
    *,
    hero_combo: str,
    hero_side: str,
    profile: Any,
    adjustments: dict[str, Any],
    street: str,
    hero_action_label: Optional[str] = None,
    line_context: Optional[dict[str, Any]] = None,
    numeric_prior: Optional[NumericOpponentPrior] = None,
) -> Optional[float]:
    detail = _response_adjusted_ev_detail_from_result(
        result,
        child,
        hero_combo=hero_combo,
        hero_side=hero_side,
        profile=profile,
        adjustments=adjustments,
        street=street,
        hero_action_label=hero_action_label,
        line_context=line_context,
        numeric_prior=numeric_prior,
    )
    if detail is None:
        return None
    return float(detail["ev"])


def _hand_index(result: dict[str, Any], side: str, combo: str) -> Optional[int]:
    hands = result.get("ip_hands") if side == "ip" else result.get("oop_hands")
    return _hand_index_for_hands(hands, combo)


def _hand_index_for_hands(hands: Any, combo: str) -> Optional[int]:
    if not isinstance(hands, list):
        return None
    c1, c2 = combo[:2], combo[2:]
    for candidate in (c1 + c2, c2 + c1):
        try:
            return hands.index(candidate)
        except ValueError:
            continue
    return None


def _node_hand_values(
    node: dict[str, Any],
    field: str,
    hand_idx: int,
    *,
    num_hands_key: str = "num_hands",
) -> dict[str, float]:
    actions = [str(a) for a in list(node.get("actions") or [])]
    values = list(node.get(field) or [])
    try:
        num_hands = int(node.get(num_hands_key) or node.get("num_hands") or 0)
    except (TypeError, ValueError):
        num_hands = 0
    if not actions or num_hands <= 0 or hand_idx < 0:
        return {}
    out: dict[str, float] = {}
    for action_idx, label in enumerate(actions):
        pos = action_idx * num_hands + hand_idx
        if pos >= len(values):
            continue
        try:
            out[label] = float(values[pos]) / 10.0
        except (TypeError, ValueError):
            continue
    return out


def _node_weighted_strategy(node: dict[str, Any]) -> dict[str, float]:
    actions = [str(a) for a in list(node.get("actions") or [])]
    strategy = list(node.get("strategy") or [])
    weights = list(node.get("weights") or [])
    try:
        num_hands = int(node.get("num_hands") or len(weights) or 0)
    except (TypeError, ValueError):
        num_hands = 0
    if not actions or num_hands <= 0 or not strategy:
        return {}
    if len(weights) < num_hands or sum(max(0.0, float(w or 0.0)) for w in weights[:num_hands]) <= 1e-12:
        weights = [1.0 / num_hands] * num_hands
    out = {label: 0.0 for label in actions}
    total_w = 0.0
    for hand_idx in range(num_hands):
        try:
            w = max(0.0, float(weights[hand_idx] or 0.0))
        except (TypeError, ValueError):
            continue
        if w <= 0.0:
            continue
        total_w += w
        for action_idx, label in enumerate(actions):
            pos = action_idx * num_hands + hand_idx
            if pos < len(strategy):
                out[label] += w * max(0.0, float(strategy[pos] or 0.0))
    if total_w <= 1e-12:
        return {}
    out = {label: value / total_w for label, value in out.items()}
    norm = sum(out.values())
    if norm <= 1e-12:
        return {}
    return {label: value / norm for label, value in out.items()}


def _adjust_response_probs(
    eq_probs: dict[str, float],
    profile: Any,
    adjustments: dict[str, Any],
    street: str,
    *,
    hero_action_label: Optional[str] = None,
    line_context: Optional[dict[str, Any]] = None,
    numeric_prior: Optional[NumericOpponentPrior] = None,
) -> dict[str, float]:
    if not eq_probs:
        return {}
    fold_bias, sticky_bias, raise_bias = _response_biases(
        profile,
        adjustments,
        street,
        numeric_prior=numeric_prior,
    )
    line_mults = _line_response_multipliers(
        street,
        hero_action_label or "",
        line_context or {},
    )
    range_v2_mults = _range_v2_response_multipliers(
        street,
        hero_action_label or "",
        line_context or {},
    )
    scaled: dict[str, float] = {}
    for label, prob in eq_probs.items():
        kind = _action_kind(label)
        mult = 1.0
        if kind == "Fold":
            mult += fold_bias
        elif kind in {"Call", "Check"}:
            mult += sticky_bias
        elif kind in {"Bet", "Raise", "AllIn"}:
            mult += raise_bias
        mult *= float(line_mults.get(kind, 1.0))
        mult *= float(range_v2_mults.get(kind, 1.0))
        scaled[label] = max(0.0, float(prob)) * _clamp(mult, 0.20, 2.50)
    total = sum(scaled.values())
    if total <= 1e-12:
        return dict(eq_probs)
    return {label: value / total for label, value in scaled.items()}


def _response_biases(
    profile: Any,
    adjustments: dict[str, Any],
    street: str,
    *,
    numeric_prior: Optional[NumericOpponentPrior] = None,
) -> tuple[float, float, float]:
    prior = numeric_prior or build_numeric_prior(profile, adjustments, street)
    return prior.fold_bias, prior.sticky_bias, prior.raise_bias


def _direct_exploit_delta(
    label: str,
    *,
    profile: Any,
    adjustments: dict[str, Any],
    street: str,
    line_context: Optional[dict[str, Any]] = None,
    numeric_prior: Optional[NumericOpponentPrior] = None,
    hero_made_rank: Any = None,
) -> float:
    prior = numeric_prior or build_numeric_prior(profile, adjustments, street)
    fold_bias, sticky_bias, raise_bias = _response_biases(
        profile,
        adjustments,
        street,
        numeric_prior=prior,
    )
    street_l = str(street).lower()
    line_context = line_context or {}
    line_signal = _line_signal_strength(street_l, line_context, hero_action_label=label)
    price = _call_price_features(line_context)
    cheap_made_overvalue = (
        price["cheapness"]
        * _made_hand_strength(hero_made_rank)
        * max(0.0, prior.overvalue_score - 0.35 * prior.nut_heavy_score)
    )
    nut_weighted_underbluff = prior.underbluff_score * (0.20 + 0.80 * prior.nut_heavy_score)
    kind = _action_kind(label)
    if kind in {"Bet", "Raise", "AllIn"}:
        return (
            0.45 * fold_bias
            - 0.25 * sticky_bias
            - 0.15 * max(0.0, raise_bias)
            - 0.35 * line_signal
            + _range_v2_direct_delta(
                label,
                street=street,
                line_context=line_context,
                hero_made_rank=hero_made_rank,
            )
        )
    if kind == "Call":
        bluff_signal = 0.35 if adjustments.get("river_bluff_likely") else 0.0
        value_signal = 0.35 if adjustments.get("river_bet_rare") else 0.0
        return (
            bluff_signal
            + 0.20 * max(0.0, raise_bias)
            + 0.28 * prior.pressure_score
            + 0.42 * cheap_made_overvalue
            - value_signal
            - 0.35 * nut_weighted_underbluff
            + _range_v2_direct_delta(
                label,
                street=street,
                line_context=line_context,
                hero_made_rank=hero_made_rank,
            )
        )
    if kind == "Fold":
        bluff_signal = 0.35 if adjustments.get("river_bluff_likely") else 0.0
        value_signal = 0.20 if adjustments.get("river_bet_rare") else 0.0
        return (
            value_signal
            - bluff_signal
            + 0.25 * nut_weighted_underbluff
            - 0.15 * prior.pressure_score
            - 0.30 * cheap_made_overvalue
            + _range_v2_direct_delta(
                label,
                street=street,
                line_context=line_context,
                hero_made_rank=hero_made_rank,
            )
        )
    return 0.0


def _exploit_confidence(
    profile: Any,
    adjustments: dict[str, Any],
    street: str,
    max_confidence: float,
    *,
    line_context: Optional[dict[str, Any]] = None,
    numeric_prior: Optional[NumericOpponentPrior] = None,
) -> float:
    line_signal = _line_signal_strength(str(street).lower(), line_context or {})
    range_v2_signal = _range_v2_signal_strength(line_context)
    if profile is None and not adjustments and line_signal <= 1e-9 and range_v2_signal <= 1e-9:
        return 0.0
    prior = numeric_prior or build_numeric_prior(profile, adjustments, street)
    hands = _profile_float(profile, "hands_seen", 0.0)
    street_samples = {
        "flop": _profile_float(profile, "flop_action_count", 0.0),
        "turn": _profile_float(profile, "turn_action_count", 0.0),
        "river": max(
            _profile_float(profile, "river_action_count", 0.0),
            _profile_float(profile, "river_facing_bet_opps", 0.0),
        ),
    }.get(str(street).lower(), 0.0)
    hand_conf = hands / (hands + 80.0) if hands > 0 else 0.0
    street_conf = street_samples / (street_samples + 30.0) if street_samples > 0 else 0.0
    conf = 0.04 + 0.18 * hand_conf + 0.14 * street_conf + 0.16 * prior.confidence
    server_prior = (
        _profile_float(profile, "server_af_prior", 0.0) > 0.0
        or _profile_float(profile, "server_wtsd_prior", 0.0) > 0.0
    )
    if hands < 10 and not server_prior:
        conf = min(conf, 0.10)
    elif hands < 40 and street_samples < 10 and not server_prior:
        conf = min(conf, 0.16)
    if adjustments.get("river_bluff_likely") or adjustments.get("river_bet_rare"):
        conf += 0.04
    if line_signal > 0.0:
        conf = max(conf, 0.12 + 0.18 * line_signal)
    if range_v2_signal > 0.0:
        features = _range_v2_features(line_context)
        conf = max(
            conf,
            0.10 + 0.16 * range_v2_signal + 0.10 * features.get("spot_blend", 0.0),
        )
    return _clamp(conf, 0.0, max(0.0, float(max_confidence)))


def _softmax_from_evs(evs: dict[str, float]) -> dict[str, float]:
    if not evs:
        return {}
    temp = 0.35
    m = max(evs.values())
    raw = {k: math.exp(_clamp((v - m) / temp, -40.0, 40.0)) for k, v in evs.items()}
    total = sum(raw.values())
    if total <= 1e-12:
        return {k: 1.0 / len(evs) for k in evs}
    return {k: v / total for k, v in raw.items()}


def _profile_float(profile: Any, name: str, default: float) -> float:
    if profile is None:
        return float(default)
    try:
        value = getattr(profile, name)
    except Exception:
        return float(default)
    try:
        return float(value() if callable(value) else value)
    except Exception:
        return float(default)


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _float_map(raw: Any, *, keys: Sequence[str]) -> dict[str, float]:
    if not isinstance(raw, dict):
        return {}
    out: dict[str, float] = {}
    for key in keys:
        if key in raw:
            out[key] = _clamp(_as_float(raw.get(key), 0.0), 0.0, 1.0)
    total = sum(out.values())
    if total > 1e-12 and total > 1.05:
        out = {key: value / total for key, value in out.items()}
    return out


def _normalize_bucket_dist(raw: Any) -> dict[str, float]:
    if not isinstance(raw, dict):
        return {}
    keys = ("nuts", "strong", "medium", "draw", "weak_draw", "air")
    out = {key: max(0.0, _as_float(raw.get(key), 0.0)) for key in keys}
    total = sum(out.values())
    if total <= 1e-12:
        return {}
    return {key: value / total for key, value in out.items()}


def _line_response_multipliers(
    street: str,
    hero_action_label: str,
    line_context: dict[str, Any],
) -> dict[str, float]:
    strength = _line_signal_strength(street, line_context, hero_action_label=hero_action_label)
    if strength <= 1e-9:
        return {}
    candidate = _candidate_action_context(hero_action_label, line_context)
    if candidate.get("kind") not in {"Bet", "Raise", "AllIn"}:
        return {}
    return {
        "Fold": _clamp(1.0 - 0.50 * strength, 0.25, 1.0),
        "Call": _clamp(1.0 + 0.72 * strength, 1.0, 2.10),
        "Check": _clamp(1.0 + 0.72 * strength, 1.0, 2.10),
        "Bet": _clamp(1.0 + 0.24 * strength, 1.0, 1.45),
        "Raise": _clamp(1.0 + 0.24 * strength, 1.0, 1.45),
        "AllIn": _clamp(1.0 + 0.24 * strength, 1.0, 1.45),
    }


def _line_signal_strength(
    street: str,
    line_context: dict[str, Any],
    *,
    hero_action_label: str = "",
) -> float:
    street = str(street).lower()
    if not line_context:
        return 0.0
    calls = int(line_context.get("villain_call_chain") or 0)
    strength = 0.0
    if street == "river":
        if calls >= 2:
            strength = 1.0
        elif calls == 1 or line_context.get("villain_called_turn"):
            strength = 0.62
        if line_context.get("villain_called_large_turn"):
            strength = min(1.0, strength + 0.18)
    elif street == "turn" and line_context.get("villain_called_flop"):
        strength = 0.35
    if strength <= 0.0:
        return 0.0
    pressure = _candidate_pressure_factor(hero_action_label, line_context)
    return _clamp(strength * pressure, 0.0, 1.0)


def _candidate_pressure_factor(hero_action_label: str, line_context: dict[str, Any]) -> float:
    candidate = _candidate_action_context(hero_action_label, line_context)
    kind = str(candidate.get("kind") or "")
    if kind not in {"Bet", "Raise", "AllIn"}:
        return 1.0 if not hero_action_label else 0.0
    if bool(candidate.get("all_in")):
        return 1.0
    pot_ratio = float(candidate.get("pot_ratio") or 0.0)
    if pot_ratio >= 1.25:
        return 0.95
    if pot_ratio >= 0.95:
        return 0.80
    if pot_ratio >= 0.66:
        return 0.60
    if pot_ratio >= 0.33:
        return 0.35
    return 0.15


def _candidate_action_context(label: str, line_context: dict[str, Any]) -> dict[str, Any]:
    match = _ACTION_RE.match(str(label or ""))
    if match is None:
        return {"kind": str(label or ""), "risk_bb": 0.0, "pot_ratio": 0.0, "all_in": False}
    kind, raw_amount = match.group(1), match.group(2)
    risk_bb = 0.0
    amount_bb = 0.0
    if raw_amount is not None:
        amount_bb = int(raw_amount) / 10.0
    if kind in {"Bet", "Raise", "AllIn"}:
        risk_bb = max(0.0, amount_bb - float(line_context.get("hero_current_bet_bb") or 0.0))
    elif kind == "Call":
        risk_bb = max(0.0, float(line_context.get("current_to_call_bb") or 0.0))
    pot_bb = max(1e-9, float(line_context.get("current_pot_bb") or 0.0))
    effective_stack_bb = max(0.0, float(line_context.get("effective_stack_bb") or 0.0))
    all_in = kind == "AllIn" or (
        kind in {"Bet", "Raise"}
        and effective_stack_bb > 0.0
        and amount_bb >= effective_stack_bb - 1e-6
    )
    return {
        "kind": kind,
        "amount_bb": amount_bb,
        "risk_bb": risk_bb,
        "pot_ratio": risk_bb / pot_bb,
        "all_in": bool(all_in),
    }


def _hero_aggression_quality(
    *,
    hero_combo: str,
    hero_made_rank: Any,
    line_context: dict[str, Any],
) -> dict[str, float]:
    f = _range_v2_features(line_context)
    made = _made_hand_strength(hero_made_rank)
    relative_total = f.get("hero_win", 0.0) + f.get("hero_tie", 0.0) + f.get("hero_loss", 0.0)
    if relative_total > 1e-9:
        showdown_value = _clamp(f.get("hero_win", 0.0) + 0.50 * f.get("hero_tie", 0.0), 0.0, 1.0)
        value_score = _clamp(0.25 * made + 0.75 * showdown_value, 0.0, 1.0)
    else:
        showdown_value = 0.0
        value_score = made

    combo = str(hero_combo or line_context.get("hero_combo") or "")
    board = [str(card) for card in list(line_context.get("board") or [])]
    blocker_score = _blocker_score(combo, board)
    draw_score = _turn_draw_score(combo, board)
    quality = _clamp(max(value_score, 0.82 * draw_score, 0.58 * blocker_score), 0.0, 1.0)
    return {
        "quality": quality,
        "value_score": value_score,
        "showdown_value": showdown_value,
        "made_strength": made,
        "draw_score": draw_score,
        "blocker_score": blocker_score,
    }


def _blocker_score(hero_combo: str, board: Sequence[Any]) -> float:
    hero_cards = _cards_from_combo(hero_combo)
    if len(hero_cards) < 2:
        return 0.0
    board_ranks = [_rank_char(card) for card in board]
    paired_board_ranks = {rank for rank in board_ranks if board_ranks.count(rank) >= 2}
    score = 0.0
    for card in hero_cards:
        rank = _rank_char(card)
        if rank in {"A", "K", "Q"}:
            score += 0.18
        elif rank in {"J", "T"}:
            score += 0.22
        if rank in paired_board_ranks:
            score += 0.24
        if rank in board_ranks and rank in {"A", "K", "Q", "J", "T", "9"}:
            score += 0.10
    return _clamp(score, 0.0, 1.0)


def _turn_draw_score(hero_combo: str, board: Sequence[Any]) -> float:
    hero_cards = _cards_from_combo(hero_combo)
    board_cards = [str(card) for card in board]
    if len(hero_cards) < 2 or len(board_cards) != 4:
        return 0.0
    all_cards = hero_cards + board_cards
    score = 0.0

    for suit in {card[1] for card in all_cards if len(card) >= 2}:
        total = sum(1 for card in all_cards if len(card) >= 2 and card[1] == suit)
        hero_total = sum(1 for card in hero_cards if len(card) >= 2 and card[1] == suit)
        if total >= 4 and hero_total > 0:
            score = max(score, 0.55)

    ranks = {_rank_value(_rank_char(card)) for card in all_cards}
    hero_ranks = {_rank_value(_rank_char(card)) for card in hero_cards}
    ranks.discard(0)
    hero_ranks.discard(0)
    if 14 in ranks:
        ranks.add(1)
    if 14 in hero_ranks:
        hero_ranks.add(1)
    for start in range(1, 11):
        window = set(range(start, start + 5))
        present = ranks & window
        if not present or not (hero_ranks & window):
            continue
        missing = 5 - len(present)
        if missing == 1:
            score = max(score, 0.58)
        elif missing == 2 and len(hero_ranks & window) >= 2:
            score = max(score, 0.16)
    return _clamp(score, 0.0, 1.0)


def _cards_from_combo(hero_combo: str) -> list[str]:
    text = str(hero_combo or "")
    cards: list[str] = []
    for pos in range(0, min(len(text), 4), 2):
        card = text[pos:pos + 2]
        if len(card) == 2:
            cards.append(card)
    return cards


def _rank_char(card: Any) -> str:
    text = str(card or "")
    return text[:1].upper()


def _rank_value(rank: str) -> int:
    return {
        "2": 2,
        "3": 3,
        "4": 4,
        "5": 5,
        "6": 6,
        "7": 7,
        "8": 8,
        "9": 9,
        "T": 10,
        "J": 11,
        "Q": 12,
        "K": 13,
        "A": 14,
    }.get(str(rank or "").upper(), 0)


def _response_fold_equity(
    response_detail: dict[str, Any],
    *,
    street: str,
    hero_action_label: str,
    line_context: dict[str, Any],
    numeric_prior: Optional[NumericOpponentPrior],
) -> tuple[float, str]:
    adj_probs = dict(response_detail.get("adj_probs") or {})
    if adj_probs:
        adjusted_fe = sum(
            max(0.0, float(prob or 0.0))
            for resp, prob in adj_probs.items()
            if _action_kind(resp) == "Fold"
        )
        return _clamp(adjusted_fe, 0.0, 1.0), "solver_child"
    return (
        _estimate_fold_equity_from_context(
            street=street,
            hero_action_label=hero_action_label,
            line_context=line_context,
            numeric_prior=numeric_prior,
        ),
        "range_line_estimate",
    )


def _estimate_fold_equity_from_context(
    *,
    street: str,
    hero_action_label: str,
    line_context: dict[str, Any],
    numeric_prior: Optional[NumericOpponentPrior],
) -> float:
    f = _range_v2_features(line_context)
    if f:
        foldable = f["air"] + 0.40 * f["weak_draw"] + 0.32 * f["draw"] + 0.12 * f["medium"]
        resistance = f["nuts"] + 0.72 * f["strong"] + 0.34 * f["medium"]
    else:
        foldable = 0.38
        resistance = 0.45

    fe = foldable / max(foldable + resistance, 1e-9)
    line_strength = _line_signal_strength(
        str(street).lower(),
        line_context,
        hero_action_label=hero_action_label,
    )
    fe *= 1.0 - 0.55 * line_strength

    if numeric_prior is not None:
        fe += 0.12 * numeric_prior.fold_lean_score
        fe += 0.08 * max(0.0, numeric_prior.fold_bias)
        fe -= 0.16 * numeric_prior.sticky_score
        fe -= 0.06 * numeric_prior.overvalue_score

    candidate = _candidate_action_context(hero_action_label, line_context)
    pot_ratio = float(candidate.get("pot_ratio") or 0.0)
    if pot_ratio >= 1.25 or bool(candidate.get("all_in")):
        fe -= 0.04 * line_strength
    elif pot_ratio <= 0.50:
        fe += 0.03
    return _clamp(fe, 0.02, 0.88)


def _response_value_supported(
    response_detail: dict[str, Any],
    *,
    best_passive_gto_ev: float,
) -> tuple[bool, Optional[float]]:
    response_evs = dict(response_detail.get("response_evs") or {})
    adj_probs = dict(response_detail.get("adj_probs") or {})
    continue_items = [
        (resp, max(0.0, float(adj_probs.get(resp, 0.0))), float(ev))
        for resp, ev in response_evs.items()
        if _action_kind(resp) != "Fold"
    ]
    continue_weight = sum(weight for _resp, weight, _ev in continue_items)
    if continue_weight <= 1e-12:
        return False, None
    continue_ev = sum(weight * ev for _resp, weight, ev in continue_items) / continue_weight
    return continue_ev >= float(best_passive_gto_ev) + 0.20, continue_ev


def _response_mass_ev(
    response_detail: dict[str, Any],
    kinds: set[str],
) -> tuple[float, Optional[float]]:
    response_evs = dict(response_detail.get("response_evs") or {})
    adj_probs = dict(response_detail.get("adj_probs") or {})
    total = 0.0
    weighted_ev = 0.0
    for label, prob in adj_probs.items():
        if _action_kind(label) not in kinds:
            continue
        if label not in response_evs:
            continue
        weight = max(0.0, float(prob or 0.0))
        if weight <= 0.0:
            continue
        total += weight
        weighted_ev += weight * float(response_evs[label])
    if total <= 1e-12:
        return 0.0, None
    return total, weighted_ev / total


def _raise_exposure_risk_discount(
    label: str,
    *,
    street: str,
    line_context: dict[str, Any],
    response_detail: dict[str, Any],
    best_passive_gto_ev: float,
    hero_combo: str,
    hero_made_rank: Any,
    numeric_prior: Optional[NumericOpponentPrior],
) -> Optional[dict[str, Any]]:
    street_l = str(street).lower()
    if street_l not in {"turn", "river"}:
        return None
    candidate = _candidate_action_context(label, line_context)
    if candidate.get("kind") not in {"Bet", "Raise"}:
        return None
    if bool(candidate.get("all_in")):
        return None
    if not response_detail:
        return None

    risk_bb = max(0.0, float(candidate.get("risk_bb") or 0.0))
    pot_ratio = max(0.0, float(candidate.get("pot_ratio") or 0.0))
    if risk_bb < 2.0 or pot_ratio < 0.18:
        return None

    raise_mass, raise_ev = _response_mass_ev(response_detail, {"Bet", "Raise", "AllIn"})
    if raise_ev is None or raise_mass <= 0.035:
        return None

    quality = _hero_aggression_quality(
        hero_combo=hero_combo,
        hero_made_rank=hero_made_rank,
        line_context=line_context,
    )
    features = _range_v2_features(line_context)
    adjusted_fe, fe_source = _response_fold_equity(
        response_detail,
        street=street_l,
        hero_action_label=label,
        line_context=line_context,
        numeric_prior=numeric_prior,
    )
    call_mass, call_ev = _response_mass_ev(response_detail, {"Call", "Check"})
    fold_mass, _fold_ev = _response_mass_ev(response_detail, {"Fold"})

    prior = numeric_prior
    pressure_score = float(prior.pressure_score) if prior is not None else 0.0
    nut_heavy = float(prior.nut_heavy_score) if prior is not None else 0.0
    overvalue = float(prior.overvalue_score) if prior is not None else 0.0
    line_strength = _line_signal_strength(street_l, line_context, hero_action_label=label)
    pressure = _candidate_pressure_factor(label, line_context)

    ev_gap = max(0.0, float(best_passive_gto_ev) - float(raise_ev))
    quality_buffer = (
        0.35 * quality["quality"]
        + 0.22 * quality["value_score"]
        + 0.16 * quality["draw_score"]
        + 0.10 * quality["blocker_score"]
    )
    if call_ev is not None and call_ev >= float(best_passive_gto_ev) - 0.35:
        quality_buffer += 0.16
    if adjusted_fe >= 0.58 + 0.04 * pressure:
        quality_buffer += 0.10
    if features:
        showdown = features.get("hero_win", 0.0) + 0.50 * features.get("hero_tie", 0.0)
        resistance = (
            features.get("nuts", 0.0)
            + 0.60 * features.get("strong", 0.0)
            + 0.20 * features.get("medium", 0.0)
        )
        quality_buffer += 0.18 * max(0.0, showdown - 0.50)
        quality_buffer -= 0.12 * max(0.0, resistance - 0.45)

    raise_need = (
        0.08
        + 0.06 * pressure
        + 0.04 * line_strength
        + 0.05 * max(0.0, pressure_score + nut_heavy - overvalue)
    )
    raise_need = _clamp(raise_need, 0.06, 0.24)
    exposure = raise_mass * (0.55 + pressure + 0.45 * line_strength)
    if exposure <= raise_need or ev_gap <= 0.25 or quality_buffer >= 0.64 + 0.10 * pressure:
        return None

    shortfall = max(0.0, exposure - raise_need)
    discount = (
        0.45
        + ev_gap * _clamp(raise_mass * 1.35, 0.0, 0.75)
        + 0.06 * min(risk_bb, 55.0)
        + 1.80 * shortfall
        + 1.25 * line_strength
        + 0.60 * max(0.0, 0.58 - quality_buffer)
    )
    discount = _clamp(discount, 0.0, 16.0)
    blocked = bool(
        exposure >= raise_need + 0.12
        and ev_gap >= max(2.0, 0.16 * min(risk_bb, 45.0))
        and quality_buffer < 0.50
        and adjusted_fe < 0.50
    )
    penalty = _clamp(discount + 0.06 * min(risk_bb, 60.0), 3.0, 20.0) if blocked else 0.0
    return {
        "action": label,
        "reason": "bet_raise_exposure_without_continue_support",
        "street": street_l,
        "blocked": blocked,
        "discount_bb": round(discount, 4),
        "penalty_bb": round(penalty, 4),
        "risk_bb": round(risk_bb, 4),
        "pot_ratio": round(pot_ratio, 4),
        "raise_mass": round(raise_mass, 4),
        "call_mass": round(call_mass, 4),
        "fold_mass": round(fold_mass, 4),
        "raise_ev_bb": round(raise_ev, 4),
        "call_ev_bb": round(call_ev, 4) if call_ev is not None else None,
        "best_passive_gto_ev_bb": round(float(best_passive_gto_ev), 4),
        "ev_gap_bb": round(ev_gap, 4),
        "adjusted_fe": round(adjusted_fe, 4),
        "fe_source": fe_source,
        "exposure": round(exposure, 4),
        "raise_need": round(raise_need, 4),
        "line_strength": round(line_strength, 4),
        "quality_buffer": round(quality_buffer, 4),
        "quality": {k: round(v, 4) for k, v in quality.items()},
    }


def _calloff_risk_discount(
    label: str,
    *,
    street: str,
    line_context: dict[str, Any],
    gto_ev: float,
    best_passive_gto_ev: float,
    hero_combo: str,
    hero_made_rank: Any,
    numeric_prior: Optional[NumericOpponentPrior],
) -> Optional[dict[str, Any]]:
    street_l = str(street).lower()
    if street_l not in {"turn", "river"}:
        return None
    candidate = _candidate_action_context(label, line_context)
    if candidate.get("kind") != "Call":
        return None

    price = _call_price_features(line_context)
    pot_odds = float(price.get("pot_odds") or 0.0)
    to_call_bb = max(0.0, float(candidate.get("risk_bb") or 0.0))
    if pot_odds <= 1e-9 or to_call_bb < 3.0:
        return None
    effective_stack_bb = max(0.0, float(line_context.get("effective_stack_bb") or 0.0))
    call_all_in = bool(effective_stack_bb > 0.0 and to_call_bb >= effective_stack_bb - 1e-6)

    features = _range_v2_features(line_context)
    relative_total = (
        features.get("hero_win", 0.0)
        + features.get("hero_tie", 0.0)
        + features.get("hero_loss", 0.0)
    )
    if relative_total <= 1e-9:
        return None

    range_v2 = line_context.get("range_v2") if isinstance(line_context, dict) else {}
    action_ctx = range_v2.get("action_context") if isinstance(range_v2, dict) else {}
    is_raise_over = bool(action_ctx.get("is_raise_over")) if isinstance(action_ctx, dict) else False
    is_raise_over = is_raise_over or (
        float(line_context.get("hero_current_bet_bb") or 0.0) > 0.0
        and to_call_bb > 0.0
    )
    bet_ratio = _as_float(action_ctx.get("bet_ratio"), 0.0) if isinstance(action_ctx, dict) else 0.0
    call_pressure = _clamp(max(float(candidate.get("pot_ratio") or 0.0), bet_ratio), 0.0, 1.8)

    showdown_equity = _clamp(
        features.get("hero_win", 0.0) + 0.50 * features.get("hero_tie", 0.0),
        0.0,
        1.0,
    )
    quality = _hero_aggression_quality(
        hero_combo=hero_combo,
        hero_made_rank=hero_made_rank,
        line_context=line_context,
    )
    prior = numeric_prior
    underbluff = float(prior.underbluff_score) if prior is not None else 0.0
    nut_heavy = float(prior.nut_heavy_score) if prior is not None else 0.0
    overvalue = float(prior.overvalue_score) if prior is not None else 0.0
    sticky = float(prior.sticky_score) if prior is not None else 0.0
    pressure_score = float(prior.pressure_score) if prior is not None else 0.0

    line_risk = 0.0
    if street_l == "river":
        line_risk += 0.025
    if is_raise_over:
        line_risk += 0.055
    if call_all_in or call_pressure >= 0.95:
        line_risk += 0.035
    if int(line_context.get("villain_call_chain") or 0) >= 1:
        line_risk += 0.018

    profile_risk = (
        0.050 * nut_heavy
        + 0.040 * underbluff
        - 0.055 * overvalue
        - 0.040 * sticky
        - 0.025 * pressure_score
    )
    hand_credit = (
        0.030 * max(0.0, quality["made_strength"] - 0.55) / 0.45
        + 0.030 * quality["draw_score"]
        + 0.018 * quality["blocker_score"]
    )
    required_margin = _clamp(
        0.012 + line_risk + profile_risk - hand_credit,
        -0.055,
        0.180,
    )
    required_equity = _clamp(pot_odds + required_margin, 0.02, 0.92)

    overvalue_continue_credit = (
        quality["made_strength"] >= 0.70
        and overvalue >= nut_heavy + 0.08
        and showdown_equity >= pot_odds - 0.035
    )
    draw_continue_credit = (
        street_l == "turn"
        and quality["draw_score"] >= 0.55
        and showdown_equity >= pot_odds - 0.060
    )
    gto_edge = float(gto_ev) - float(best_passive_gto_ev)
    gto_continue_credit = gto_edge >= max(1.0, 0.08 * min(to_call_bb, 60.0))
    if (
        showdown_equity >= required_equity
        or overvalue_continue_credit
        or draw_continue_credit
        or (gto_continue_credit and showdown_equity >= pot_odds + required_margin * 0.40)
    ):
        return None

    shortfall = max(0.0, required_equity - showdown_equity)
    multiplier = (
        0.34
        + 0.20 * (1.0 if is_raise_over else 0.0)
        + 0.10 * (1.0 if call_all_in else 0.0)
        + 0.14 * (1.0 if street_l == "river" else 0.0)
        + 0.12 * nut_heavy
        + 0.10 * underbluff
        - 0.12 * overvalue
        - 0.08 * sticky
    )
    multiplier = _clamp(multiplier, 0.16, 0.78)
    discount = shortfall * min(to_call_bb, 90.0) * multiplier
    if is_raise_over and to_call_bb >= 8.0 and showdown_equity < pot_odds + 0.015:
        discount += 0.55
    discount = _clamp(discount, 0.0, 18.0)
    return {
        "action": label,
        "reason": "calloff_without_price_or_profile_support",
        "street": street_l,
        "discount_bb": round(discount, 4),
        "to_call_bb": round(to_call_bb, 4),
        "pot_odds": round(pot_odds, 4),
        "showdown_equity": round(showdown_equity, 4),
        "required_equity": round(required_equity, 4),
        "required_margin": round(required_margin, 4),
        "shortfall": round(shortfall, 4),
        "is_raise_over": bool(is_raise_over),
        "all_in": bool(call_all_in),
        "call_pressure": round(call_pressure, 4),
        "gto_edge_bb": round(gto_edge, 4),
        "profile": {
            "underbluff": round(underbluff, 4),
            "nut_heavy": round(nut_heavy, 4),
            "overvalue": round(overvalue, 4),
            "sticky": round(sticky, 4),
            "pressure": round(pressure_score, 4),
        },
        "quality": {k: round(v, 4) for k, v in quality.items()},
    }


def _sticky_aggression_discount(
    label: str,
    *,
    street: str,
    line_context: dict[str, Any],
    response_detail: dict[str, Any],
    best_passive_gto_ev: float,
    hero_combo: str,
    hero_made_rank: Any,
    numeric_prior: Optional[NumericOpponentPrior],
) -> Optional[dict[str, Any]]:
    street_l = str(street).lower()
    if street_l not in {"turn", "river"}:
        return None
    candidate = _candidate_action_context(label, line_context)
    if candidate.get("kind") not in {"Bet", "Raise", "AllIn"}:
        return None

    prior = numeric_prior
    if prior is None:
        return None
    sticky_signal = max(
        float(prior.sticky_score),
        max(0.0, float(prior.sticky_bias)),
        0.55 * float(prior.overvalue_score),
    )
    if sticky_signal < 0.35:
        return None

    risk_bb = max(0.0, float(candidate.get("risk_bb") or 0.0))
    pot_ratio = max(0.0, float(candidate.get("pot_ratio") or 0.0))
    all_in = bool(candidate.get("all_in"))
    if risk_bb < 2.0 or (pot_ratio < 0.28 and not all_in):
        return None

    quality = _hero_aggression_quality(
        hero_combo=hero_combo,
        hero_made_rank=hero_made_rank,
        line_context=line_context,
    )
    features = _range_v2_features(line_context)
    relative_total = (
        features.get("hero_win", 0.0)
        + features.get("hero_tie", 0.0)
        + features.get("hero_loss", 0.0)
    )
    showdown_value = quality["showdown_value"] if relative_total > 1e-9 else 0.0
    villain_loss = features.get("hero_loss", 0.0)

    response_value_supported, continue_ev = _response_value_supported(
        response_detail,
        best_passive_gto_ev=best_passive_gto_ev,
    )
    value_supported = bool(
        response_value_supported
        or quality["value_score"] >= 0.76
        or (
            relative_total > 1e-9
            and showdown_value >= 0.66
            and villain_loss <= 0.30
            and quality["made_strength"] >= 0.70
        )
    )
    if value_supported:
        return None

    draw_supported = bool(
        street_l == "turn"
        and (
            quality["draw_score"] >= 0.58
            or (quality["draw_score"] >= 0.45 and quality["blocker_score"] >= 0.62)
        )
        and not all_in
        and pot_ratio <= 0.85
    )
    blocker_supported = bool(
        quality["blocker_score"] >= 0.74
        and features.get("bluff_mass", 0.0) >= 0.38
        and not all_in
        and pot_ratio <= 0.75
    )
    if draw_supported or blocker_supported:
        return None

    adjusted_fe, fe_source = _response_fold_equity(
        response_detail,
        street=street_l,
        hero_action_label=label,
        line_context=line_context,
        numeric_prior=numeric_prior,
    )
    pot_bb = max(1e-9, float(line_context.get("current_pot_bb") or 0.0))
    required_fe = risk_bb / max(pot_bb + risk_bb, 1e-9)
    line_strength = _line_signal_strength(street_l, line_context, hero_action_label=label)
    fe_margin = 0.06 + 0.06 * sticky_signal + 0.04 * line_strength
    fe_supported = adjusted_fe >= required_fe + fe_margin and sticky_signal < 0.55
    if fe_supported:
        return None

    shortfall = max(0.0, required_fe + fe_margin - adjusted_fe)
    low_quality = max(0.0, 0.58 - quality["quality"])
    discount = (
        0.65
        + 0.08 * min(risk_bb, 80.0)
        + 2.40 * sticky_signal
        + shortfall * min(risk_bb, 80.0) * 0.42
        + 1.20 * line_strength
        + 2.20 * low_quality
    )
    if all_in or pot_ratio >= 1.0:
        discount += 1.40
    discount = _clamp(discount, 0.50, 22.0)

    blocked = bool(
        quality["quality"] < 0.58
        and adjusted_fe < required_fe + max(0.04, fe_margin * 0.65)
        and (all_in or pot_ratio >= 0.45 or risk_bb >= 8.0)
    )
    penalty = _clamp(discount + 0.06 * min(risk_bb, 80.0), 3.0, 26.0) if blocked else 0.0
    return {
        "action": label,
        "reason": "sticky_pool_low_fe_unbacked_aggression",
        "street": street_l,
        "blocked": blocked,
        "discount_bb": round(discount, 4),
        "penalty_bb": round(penalty, 4),
        "risk_bb": round(risk_bb, 4),
        "pot_ratio": round(pot_ratio, 4),
        "all_in": all_in,
        "sticky_signal": round(sticky_signal, 4),
        "required_fe": round(required_fe, 4),
        "adjusted_fe": round(adjusted_fe, 4),
        "fe_margin": round(fe_margin, 4),
        "fe_source": fe_source,
        "line_strength": round(line_strength, 4),
        "showdown_value": round(showdown_value, 4),
        "continue_ev_bb": round(continue_ev, 4) if continue_ev is not None else None,
        "support": {
            "value": bool(value_supported),
            "draw": bool(draw_supported),
            "blocker": bool(blocker_supported),
            "fold_equity": bool(fe_supported),
        },
        "quality": {k: round(v, 4) for k, v in quality.items()},
    }


def _strict_bluff_aggression_gate(
    label: str,
    *,
    street: str,
    line_context: dict[str, Any],
    response_detail: dict[str, Any],
    hero_combo: str,
    hero_made_rank: Any,
    numeric_prior: Optional[NumericOpponentPrior],
) -> Optional[dict[str, Any]]:
    street_l = str(street).lower()
    if street_l not in {"turn", "river"}:
        return None
    candidate = _candidate_action_context(label, line_context)
    if candidate.get("kind") not in {"Bet", "Raise", "AllIn"}:
        return None

    features = _range_v2_features(line_context)
    relative_total = (
        features.get("hero_win", 0.0)
        + features.get("hero_tie", 0.0)
        + features.get("hero_loss", 0.0)
    )
    if relative_total <= 1e-9:
        return None
    showdown_equity = _clamp(
        features.get("hero_win", 0.0) + 0.50 * features.get("hero_tie", 0.0),
        0.0,
        1.0,
    )
    if showdown_equity > 0.35:
        return None

    risk_bb = max(0.0, float(candidate.get("risk_bb") or 0.0))
    pot_ratio = max(0.0, float(candidate.get("pot_ratio") or 0.0))
    all_in = bool(candidate.get("all_in"))
    if not all_in and risk_bb < 4.0 and pot_ratio < 0.33:
        return None

    quality = _hero_aggression_quality(
        hero_combo=hero_combo,
        hero_made_rank=hero_made_rank,
        line_context=line_context,
    )
    adjusted_fe, fe_source = _response_fold_equity(
        response_detail,
        street=street_l,
        hero_action_label=label,
        line_context=line_context,
        numeric_prior=numeric_prior,
    )
    range_line_fe = _estimate_fold_equity_from_context(
        street=street_l,
        hero_action_label=label,
        line_context=line_context,
        numeric_prior=numeric_prior,
    )
    # Solver child FE is equilibrium-facing; for strict low-equity bluffs cap it by
    # observed range/line evidence so one optimistic child node cannot justify a punt.
    effective_fe = adjusted_fe
    if fe_source == "solver_child":
        effective_fe = min(adjusted_fe, range_line_fe + 0.06)

    pot_bb = max(1e-9, float(line_context.get("current_pot_bb") or 0.0))
    required_fe = risk_bb / max(pot_bb + risk_bb, 1e-9)
    line_strength = _line_signal_strength(street_l, line_context, hero_action_label=label)
    margin = (
        0.04
        + 0.06 * line_strength
        + (0.04 if all_in else 0.0)
        + (0.03 if street_l == "river" else 0.0)
    )

    draw_supported = street_l == "turn" and quality["draw_score"] >= 0.55
    blocker_supported = (
        quality["blocker_score"] >= 0.68
        and (
            features.get("bluff_mass", 0.0) >= 0.38
            or effective_fe >= required_fe + max(0.05, margin * 0.70)
        )
    )
    fold_equity_supported = effective_fe >= required_fe + margin
    if draw_supported or blocker_supported or fold_equity_supported:
        return None

    shortfall = max(0.0, required_fe + margin - effective_fe)
    penalty = _clamp(4.0 + 0.14 * risk_bb + 8.0 * shortfall, 4.0, 22.0)
    return {
        "action": label,
        "blocked": True,
        "reason": "strict_low_equity_unbacked_aggression",
        "street": street_l,
        "showdown_equity": round(showdown_equity, 4),
        "required_fe": round(required_fe, 4),
        "adjusted_fe": round(adjusted_fe, 4),
        "range_line_fe": round(range_line_fe, 4),
        "effective_fe": round(effective_fe, 4),
        "fe_source": fe_source,
        "margin": round(margin, 4),
        "shortfall": round(shortfall, 4),
        "risk_bb": round(risk_bb, 4),
        "pot_ratio": round(pot_ratio, 4),
        "line_strength": round(line_strength, 4),
        "penalty_bb": round(penalty, 4),
        "quality": {k: round(v, 4) for k, v in quality.items()},
    }


def _turn_barrel_quality_discount(
    label: str,
    *,
    street: str,
    line_context: dict[str, Any],
    response_detail: dict[str, Any],
    best_passive_gto_ev: float,
    hero_combo: str,
    hero_made_rank: Any,
    numeric_prior: Optional[NumericOpponentPrior],
) -> Optional[dict[str, Any]]:
    if str(street).lower() != "turn":
        return None
    candidate = _candidate_action_context(label, line_context)
    if candidate.get("kind") not in {"Bet", "Raise", "AllIn"}:
        return None
    if not line_context.get("villain_called_flop"):
        return None
    pot_ratio = float(candidate.get("pot_ratio") or 0.0)
    if pot_ratio < 0.95 and not bool(candidate.get("all_in")):
        return None

    quality = _hero_aggression_quality(
        hero_combo=hero_combo,
        hero_made_rank=hero_made_rank,
        line_context=line_context,
    )
    response_value_supported, continue_ev = _response_value_supported(
        response_detail,
        best_passive_gto_ev=best_passive_gto_ev,
    )
    combo_supported = (
        quality["value_score"] >= 0.62
        or quality["draw_score"] >= 0.45
        or quality["blocker_score"] >= 0.62
    )
    if response_value_supported and combo_supported:
        return {
            "action": label,
            "discount_bb": 0.0,
            "value_supported": True,
            "combo_supported": True,
            "quality": {k: round(v, 4) for k, v in quality.items()},
            "pot_ratio": round(pot_ratio, 4),
            "continue_ev_bb": round(continue_ev, 4) if continue_ev is not None else None,
        }

    risk_bb = max(0.0, float(candidate.get("risk_bb") or 0.0))
    pot_bb = max(1e-9, float(line_context.get("current_pot_bb") or 0.0))
    required_fe = risk_bb / max(pot_bb + risk_bb, 1e-9)
    adjusted_fe, fe_source = _response_fold_equity(
        response_detail,
        street=street,
        hero_action_label=label,
        line_context=line_context,
        numeric_prior=numeric_prior,
    )
    line_strength = _line_signal_strength(street, line_context, hero_action_label=label)
    low_quality = 1.0 - quality["quality"]
    margin = 0.03 + 0.06 * line_strength + 0.12 * max(0.0, 0.50 - quality["quality"])
    if bool(candidate.get("all_in")):
        margin += 0.03
    shortfall = max(0.0, required_fe + margin - adjusted_fe)
    if shortfall <= 1e-9:
        return {
            "action": label,
            "required_fe": round(required_fe, 4),
            "adjusted_fe": round(adjusted_fe, 4),
            "fe_source": fe_source,
            "margin": round(margin, 4),
            "discount_bb": 0.0,
            "quality": {k: round(v, 4) for k, v in quality.items()},
            "value_supported": bool(response_value_supported),
            "combo_supported": bool(combo_supported),
        }

    multiplier = 0.14 if response_value_supported or combo_supported else 0.30 + 0.55 * low_quality
    discount = shortfall * min(risk_bb, 60.0) * multiplier
    if not response_value_supported and not combo_supported:
        discount += line_strength * max(0.0, pot_ratio - 0.75) * 1.25
    discount = _clamp(discount, 0.0, 5.0 if combo_supported else 16.0)
    return {
        "action": label,
        "required_fe": round(required_fe, 4),
        "adjusted_fe": round(adjusted_fe, 4),
        "fe_source": fe_source,
        "margin": round(margin, 4),
        "shortfall": round(shortfall, 4),
        "line_strength": round(line_strength, 4),
        "risk_bb": round(risk_bb, 4),
        "pot_ratio": round(pot_ratio, 4),
        "continue_ev_bb": round(continue_ev, 4) if continue_ev is not None else None,
        "value_supported": bool(response_value_supported),
        "combo_supported": bool(combo_supported),
        "quality": {k: round(v, 4) for k, v in quality.items()},
        "discount_bb": round(discount, 4),
    }


def _large_size_support_check(
    label: str,
    *,
    street: str,
    line_context: dict[str, Any],
    response_detail: dict[str, Any],
    best_passive_gto_ev: float,
    gto_ev: float,
    hero_combo: str,
    hero_made_rank: Any,
    numeric_prior: Optional[NumericOpponentPrior],
) -> Optional[dict[str, Any]]:
    street_l = str(street).lower()
    if street_l not in {"turn", "river"}:
        return None
    candidate = _candidate_action_context(label, line_context)
    if candidate.get("kind") not in {"Bet", "Raise", "AllIn"}:
        return None

    pot_bb = max(0.0, float(line_context.get("current_pot_bb") or 0.0))
    if pot_bb <= 1e-9:
        return None

    risk_bb = max(0.0, float(candidate.get("risk_bb") or 0.0))
    pot_ratio = max(0.0, float(candidate.get("pot_ratio") or 0.0))
    all_in = bool(candidate.get("all_in"))
    large = all_in or pot_ratio >= 0.72 or (risk_bb >= 20.0 and pot_ratio >= 0.45)
    if not large or risk_bb < 4.0:
        return None

    features = _range_v2_features(line_context)
    has_range_evidence = bool(features)
    has_response_evidence = bool(response_detail)
    if not has_range_evidence and not has_response_evidence:
        return None

    quality = _hero_aggression_quality(
        hero_combo=hero_combo,
        hero_made_rank=hero_made_rank,
        line_context=line_context,
    )
    response_value_supported, continue_ev = _response_value_supported(
        response_detail,
        best_passive_gto_ev=best_passive_gto_ev,
    )
    adjusted_fe, fe_source = _response_fold_equity(
        response_detail,
        street=street_l,
        hero_action_label=label,
        line_context=line_context,
        numeric_prior=numeric_prior,
    )
    required_fe = risk_bb / max(pot_bb + risk_bb, 1e-9)
    line_strength = _line_signal_strength(street_l, line_context, hero_action_label=label)
    pressure = _candidate_pressure_factor(label, line_context)

    prior = numeric_prior
    overvalue = float(prior.overvalue_score) if prior is not None else 0.0
    nut_heavy = float(prior.nut_heavy_score) if prior is not None else 0.0
    sticky = float(prior.sticky_score) if prior is not None else 0.0

    relative_total = (
        features.get("hero_win", 0.0)
        + features.get("hero_tie", 0.0)
        + features.get("hero_loss", 0.0)
    )
    showdown_value = quality["showdown_value"] if relative_total > 1e-9 else 0.0
    non_nut_value = features.get("non_nut_value", 0.0)
    resistance = _clamp(
        features.get("nuts", 0.0)
        + 0.62 * features.get("strong", 0.0)
        + 0.22 * features.get("medium", 0.0),
        0.0,
        1.0,
    )
    worse_call_proxy = _clamp(
        0.82 * features.get("medium", 0.0)
        + 0.30 * features.get("draw", 0.0)
        + 0.22 * features.get("weak_draw", 0.0)
        + 0.10 * features.get("air", 0.0)
        + 0.16 * overvalue * non_nut_value,
        0.0,
        1.0,
    )

    value_need = (
        0.55
        + 0.05 * pressure
        + 0.04 * max(0.0, nut_heavy - overvalue)
        + 0.03 * max(0.0, resistance - worse_call_proxy)
    )
    value_need = _clamp(value_need, 0.50, 0.68)
    value_supported_by_range = bool(
        relative_total > 1e-9
        and showdown_value >= value_need
        and worse_call_proxy + 0.05 >= 0.62 * resistance
    )
    strong_made_no_relative_alarm = bool(
        relative_total <= 1e-9
        and quality["made_strength"] >= 0.90
        and non_nut_value >= 0.35
        and features.get("nuts", 0.0) <= 0.22 + 0.10 * overvalue
    )
    value_supported = bool(
        response_value_supported
        or value_supported_by_range
        or strong_made_no_relative_alarm
    )

    fe_margin = 0.04 + 0.05 * pressure + 0.04 * line_strength + 0.03 * sticky
    fe_supported = adjusted_fe >= required_fe + fe_margin

    gto_edge = float(gto_ev) - float(best_passive_gto_ev)
    ev_need = (
        0.90
        + 0.055 * min(risk_bb, 70.0)
        + (0.75 if all_in else 0.0)
        + 0.55 * line_strength
    )
    ev_supported = bool(
        gto_edge >= ev_need
        and quality["quality"] >= 0.74
        and not (relative_total > 1e-9 and showdown_value < 0.44)
    )
    if value_supported or fe_supported or ev_supported:
        return None

    value_shortfall = max(0.0, value_need - showdown_value) if relative_total > 1e-9 else 0.0
    fe_shortfall = max(0.0, required_fe + fe_margin - adjusted_fe)
    resistance_gap = max(0.0, resistance - worse_call_proxy)
    low_quality = max(0.0, 0.78 - quality["quality"])
    discount = (
        1.00
        + 0.10 * min(risk_bb, 90.0)
        + 2.40 * fe_shortfall
        + 3.20 * value_shortfall
        + 2.20 * resistance_gap
        + 1.30 * line_strength
        + 1.60 * low_quality
    )
    if all_in or pot_ratio >= 1.25:
        discount += 1.50
    discount = _clamp(discount, 0.75, 24.0 if all_in or pot_ratio >= 1.25 else 16.0)

    blocked = bool(
        (all_in or pot_ratio >= 1.0)
        and quality["quality"] < 0.78
        and gto_edge < ev_need * 1.35
        and (relative_total <= 1e-9 or showdown_value < value_need - 0.04)
    )
    penalty = 0.0
    if blocked:
        penalty = _clamp(discount + 0.08 * min(risk_bb, 90.0), 4.0, 28.0)

    return {
        "action": label,
        "reason": "large_size_without_value_fe_or_ev_support",
        "street": street_l,
        "blocked": blocked,
        "discount_bb": round(discount, 4),
        "penalty_bb": round(penalty, 4),
        "risk_bb": round(risk_bb, 4),
        "pot_ratio": round(pot_ratio, 4),
        "all_in": all_in,
        "required_fe": round(required_fe, 4),
        "adjusted_fe": round(adjusted_fe, 4),
        "fe_margin": round(fe_margin, 4),
        "fe_source": fe_source,
        "showdown_value": round(showdown_value, 4),
        "value_need": round(value_need, 4),
        "worse_call_proxy": round(worse_call_proxy, 4),
        "resistance": round(resistance, 4),
        "gto_edge_bb": round(gto_edge, 4),
        "ev_need_bb": round(ev_need, 4),
        "line_strength": round(line_strength, 4),
        "continue_ev_bb": round(continue_ev, 4) if continue_ev is not None else None,
        "support": {
            "value": bool(value_supported),
            "fold_equity": bool(fe_supported),
            "ev": bool(ev_supported),
            "response_value": bool(response_value_supported),
            "range_value": bool(value_supported_by_range),
        },
        "quality": {k: round(v, 4) for k, v in quality.items()},
    }


def _river_aggression_risk_discount(
    label: str,
    *,
    street: str,
    line_context: dict[str, Any],
    response_detail: dict[str, Any],
    best_passive_gto_ev: float,
    hero_combo: str,
    hero_made_rank: Any,
    numeric_prior: Optional[NumericOpponentPrior],
) -> Optional[dict[str, Any]]:
    if str(street).lower() != "river":
        return None
    candidate = _candidate_action_context(label, line_context)
    if candidate.get("kind") not in {"Bet", "Raise", "AllIn"}:
        return None
    strength = _line_signal_strength(street, line_context, hero_action_label=label)
    if strength <= 1e-9:
        return None
    pot_ratio = float(candidate.get("pot_ratio") or 0.0)
    if pot_ratio < 0.66 and not bool(candidate.get("all_in")):
        return None
    risk_bb = max(0.0, float(candidate.get("risk_bb") or 0.0))
    pot_bb = max(1e-9, float(line_context.get("current_pot_bb") or 0.0))
    required_fe = risk_bb / max(pot_bb + risk_bb, 1e-9)
    adjusted_fe, fe_source = _response_fold_equity(
        response_detail,
        street=street,
        hero_action_label=label,
        line_context=line_context,
        numeric_prior=numeric_prior,
    )
    response_value_supported, continue_ev = _response_value_supported(
        response_detail,
        best_passive_gto_ev=best_passive_gto_ev,
    )
    quality = _hero_aggression_quality(
        hero_combo=hero_combo,
        hero_made_rank=hero_made_rank,
        line_context=line_context,
    )
    combo_supported = (
        quality["value_score"] >= 0.64
        or quality["blocker_score"] >= 0.68
    )
    value_supported = bool(
        response_value_supported
        or quality["value_score"] >= 0.72
    )
    margin = (
        0.04
        + 0.08 * strength
        + (0.03 if bool(candidate.get("all_in")) else 0.0)
        + 0.10 * max(0.0, 0.45 - quality["quality"])
        - 0.03 * min(1.0, quality["blocker_score"])
    )
    shortfall = max(0.0, required_fe + margin - adjusted_fe)
    if shortfall <= 1e-9:
        return {
            "action": label,
            "required_fe": round(required_fe, 4),
            "adjusted_fe": round(adjusted_fe, 4),
            "fe_source": fe_source,
            "margin": round(margin, 4),
            "line_strength": round(strength, 4),
            "discount_bb": 0.0,
            "value_supported": bool(value_supported),
            "combo_supported": bool(combo_supported),
            "quality": {k: round(v, 4) for k, v in quality.items()},
        }

    low_quality = 1.0 - quality["quality"]
    if value_supported:
        multiplier = 0.06
        cap = 6.0
    elif combo_supported:
        multiplier = 0.16
        cap = 10.0
    else:
        multiplier = 0.34 + 0.46 * low_quality
        cap = 28.0 if bool(candidate.get("all_in")) or pot_ratio >= 1.25 else 18.0
    discount = shortfall * min(risk_bb, 90.0) * multiplier
    if not value_supported and not combo_supported:
        discount += strength * max(0.0, pot_ratio - 0.75) * 2.0
        if line_context.get("villain_called_large_turn"):
            discount += 1.5 * low_quality
    discount = _clamp(discount, 0.0, cap)
    return {
        "action": label,
        "required_fe": round(required_fe, 4),
        "adjusted_fe": round(adjusted_fe, 4),
        "fe_source": fe_source,
        "margin": round(margin, 4),
        "shortfall": round(shortfall, 4),
        "line_strength": round(strength, 4),
        "risk_bb": round(risk_bb, 4),
        "pot_ratio": round(pot_ratio, 4),
        "continue_ev_bb": round(continue_ev, 4) if continue_ev is not None else None,
        "value_supported": bool(value_supported),
        "combo_supported": bool(combo_supported),
        "quality": {k: round(v, 4) for k, v in quality.items()},
        "discount_bb": round(discount, 4),
    }


def _action_kind(label: str) -> str:
    match = _ACTION_RE.match(str(label))
    return match.group(1) if match else str(label)


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, float(value)))


def _build_solver_args(
    state: RealtimeCFRState,
    accuracy: float,
    max_iterations: int,
    include_evs: bool = True,
) -> tuple[dict[str, Any], list[tuple[str, Optional[int]]]]:
    street = _street_of_state(state)
    menus = {0: list(BASE_MENU[f"{street}_bets"]), 1: list(BASE_MENU[f"{street}_bets"])}
    raises = {0: list(BASE_MENU["raises"]), 1: list(BASE_MENU["raises"])}
    contrib = [0.0, 0.0]
    prev_to = 0.0
    actor = 0
    expect: list[tuple[str, Optional[int]]] = []

    for action, to_amount in state.prefix:
        pot_now = float(state.pot_bb) + contrib[0] + contrib[1]
        if action == "check":
            expect.append(("Check", None))
        elif action == "call":
            contrib[actor] = prev_to
            expect.append(("Call", None))
        elif action in {"bet", "raise", "allin"}:
            to_amount = float(to_amount)
            if prev_to <= 0.0:
                pct = round(to_amount / max(pot_now, 1e-9) * 100.0, 2)
                menus[actor].append(pct)
                expect.append(("AllIn" if action == "allin" else "Bet", _chips(to_amount)))
            else:
                multiple = round(to_amount / max(prev_to, 1e-9), 3)
                raises[actor].append(multiple)
                expect.append(("AllIn" if action == "allin" else "Raise", _chips(to_amount)))
            prev_to = to_amount
            contrib[actor] = to_amount
        else:
            raise ValueError(f"unknown realtime CFR prefix action: {action}")
        actor ^= 1

    args = {
        "board": state.board,
        "oop_range": state.oop_range,
        "ip_range": state.ip_range,
        "starting_pot": _chips(state.pot_bb),
        "effective_stack": _chips(state.effective_stack_bb),
        "rake_rate": BASE_MENU["rake_rate"],
        "rake_cap": BASE_MENU["rake_cap"],
        "flop_bets": _fmt_bets(BASE_MENU["flop_bets"]),
        "turn_bets": (
            _fmt_bets(menus[0]) if street == "turn" else _fmt_bets(BASE_MENU["turn_bets"])
        ),
        "river_bets": (
            _fmt_bets(menus[0]) if street == "river" else _fmt_bets(BASE_MENU["future_river_bets"])
        ),
        f"{street}_bets_ip": _fmt_bets(menus[1]),
        "raises": _fmt_raises(raises[0]),
        "raises_ip": _fmt_raises(raises[1]),
        "add_allin_threshold": BASE_MENU["add_allin_threshold"],
        "force_allin_threshold": BASE_MENU["force_allin_threshold"],
        "merging_threshold": BASE_MENU["merging_threshold"],
        "target_exploitability_pct": float(accuracy),
        "max_iterations": int(max_iterations),
        "compression": False,
        "include_evs": bool(include_evs),
    }
    return args, expect


def _solver_worker(args_json: str, threads: int, solver_lib_path: Optional[str], q: Any) -> None:
    try:
        if threads > 0:
            os.environ["RAYON_NUM_THREADS"] = str(int(threads))
        pf_solver = _load_pf_solver(solver_lib_path)
        q.put({"ok": True, "result": pf_solver.solve_flop_json(args_json)})
    except Exception as exc:
        q.put({"ok": False, "error": str(exc), "traceback": traceback.format_exc()})


def _load_pf_solver(solver_lib_path: Optional[str]):
    path = _resolve_solver_lib_path(solver_lib_path)
    if not path:
        raise ImportError("local pf_solver extension is not built")
    existing = sys.modules.get("pf_solver")
    if existing is not None:
        existing_file = getattr(existing, "__file__", "")
        try:
            if Path(existing_file).resolve() == Path(path).resolve():
                return existing
        except Exception:
            pass
    loader = ExtensionFileLoader("pf_solver", path)
    spec = importlib.util.spec_from_loader("pf_solver", loader)
    if spec is None:
        raise ImportError(f"cannot load pf_solver from {path}")
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    sys.modules["pf_solver"] = module
    return module


def _resolve_solver_lib_path(configured: Optional[str]) -> Optional[str]:
    candidates: list[Path] = []
    for raw in (configured,):
        if raw:
            candidates.append(Path(raw).expanduser())

    repo_root = Path(__file__).resolve().parents[2]
    local_release = repo_root / "pokerfate" / "solver" / "pf_solver" / "target" / "release"
    candidates.extend([
        local_release / "libpf_solver.dylib",
        local_release / "libpf_solver.so",
        local_release / "pf_solver.pyd",
    ])
    candidates.extend(sorted(local_release.glob("pf_solver*.so")))

    for path in candidates:
        if path.is_file():
            return str(path)
    return None


def _locate_node(
    nodes: Sequence[dict[str, Any]],
    expect: Sequence[tuple[str, Optional[int]]],
    path_matches: Optional[list[dict[str, Any]]] = None,
) -> Optional[dict[str, Any]]:
    by_path = {str(node.get("path")): node for node in nodes if isinstance(node, dict)}
    path = "r"
    for kind, chips in expect:
        node = by_path.get(path)
        if node is None:
            return None
        chosen, match_info = _choose_matching_action(
            list(node.get("actions") or []),
            kind,
            chips,
        )
        if chosen is None:
            if path_matches is not None:
                path_matches.append({
                    "path": path,
                    "expected": str(kind) if chips is None else f"{kind}({chips})",
                    "available": list(node.get("actions") or []),
                    "match": "missing",
                })
            return None
        if path_matches is not None:
            path_matches.append({"path": path, **match_info})
        path = f"{path}:{chosen}"
    return by_path.get(path)


def _choose_matching_action(
    actions: Sequence[Any],
    kind: str,
    chips: Optional[int],
) -> tuple[Optional[str], dict[str, Any]]:
    expected = str(kind) if chips is None else f"{kind}({chips})"
    if chips is None:
        for label in actions:
            match = _ACTION_RE.match(str(label))
            if match is not None and match.group(1) == kind:
                selected = str(label)
                return selected, {
                    "expected": expected,
                    "selected": selected,
                    "match": "exact",
                }
        return None, {"expected": expected, "match": "missing"}

    exact_tolerance = max(2, int(chips * 0.05))
    candidates: list[dict[str, Any]] = []
    for label in actions:
        match = _ACTION_RE.match(str(label))
        if match is None:
            continue
        label_kind, raw_amount = match.group(1), match.group(2)
        if label_kind not in {kind, "AllIn"} or not raw_amount:
            continue
        amount = int(raw_amount)
        diff = abs(amount - chips)
        row = {
            "label": str(label),
            "kind": label_kind,
            "amount": amount,
            "diff": diff,
            "rel_diff": diff / max(float(chips), 1.0),
        }
        candidates.append(row)
        if diff <= exact_tolerance:
            return str(label), {
                "expected": expected,
                "selected": str(label),
                "match": "exact",
                "selected_amount": amount,
                "diff": diff,
            }

    fallback = _nearest_live_size_candidate(candidates, kind, chips)
    if fallback is None:
        return None, {
            "expected": expected,
            "match": "missing",
            "candidates": candidates[:8],
        }
    selected = str(fallback["label"])
    return selected, {
        "expected": expected,
        "selected": selected,
        "match": "nearest",
        "selected_amount": int(fallback["amount"]),
        "diff": int(fallback["diff"]),
        "rel_diff": round(float(fallback["rel_diff"]), 4),
    }


def _nearest_live_size_candidate(
    candidates: Sequence[dict[str, Any]],
    kind: str,
    chips: int,
) -> Optional[dict[str, Any]]:
    if not candidates:
        return None
    ranked = sorted(
        candidates,
        key=lambda row: (
            float(row.get("diff", 0.0)),
            0 if row.get("kind") == kind else 1,
        ),
    )
    best = ranked[0]
    rel_diff = float(best.get("rel_diff", 1.0))
    if rel_diff <= 0.25:
        return best
    if best.get("kind") == "AllIn":
        amount = max(float(best.get("amount") or 0.0), 1.0)
        if chips / amount >= 0.75 and rel_diff <= 0.35:
            return best
    return None


def _select_strategy_action(strategy: dict[str, float]) -> tuple[str, float]:
    order = {"Fold": 0, "Check": 1, "Call": 2, "Bet": 3, "Raise": 4, "AllIn": 5}

    def key(item: tuple[str, float]) -> tuple[float, int]:
        label, prob = item
        match = _ACTION_RE.match(label)
        kind = match.group(1) if match else label
        return (float(prob), order.get(kind, 0))

    return max(strategy.items(), key=key)


def _street_of_state(state: RealtimeCFRState) -> str:
    board_len = len(state.board)
    if board_len == 8:
        return "turn"
    if board_len == 10:
        return "river"
    raise ValueError(f"realtime CFR requires turn/river board, got {board_len} chars")


def _chips(bb: float) -> int:
    return int(round(float(bb) * 10.0))


def _fmt_bets(values: Sequence[float]) -> str:
    return ", ".join(f"{value:g}%" for value in sorted({float(v) for v in values}))


def _fmt_raises(values: Sequence[float]) -> str:
    return ", ".join(f"{value:g}x" for value in sorted({float(v) for v in values}))


def _player_by_id(players: Sequence[Player], player_id: int) -> Optional[Player]:
    for player in players:
        if int(player.player_id) == int(player_id):
            return player
    return None


def _hero_made_rank(hole_cards: Sequence[Any], board: Sequence[Any]) -> str:
    if len(hole_cards) + len(board) < 5:
        return ""
    try:
        score, _best = HandEvaluator.best_five(list(hole_cards) + list(board))
        return HandRank(score[0]).name.lower()
    except Exception:
        return ""


def _range_entry_count(range_text: str) -> int:
    return sum(1 for item in str(range_text or "").split(",") if item.strip())
