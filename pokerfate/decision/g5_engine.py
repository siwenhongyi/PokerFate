"""JSON-line adapter for running g5 as an external decision worker.

This module deliberately does not import or load the C# g5 assembly in-process.
The mitm/proxy process stays Python-only; g5 can run in a separate worker
process with its native C++/C# runtime and fail independently.
"""

from __future__ import annotations

import json
import queue
import shlex
import subprocess
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Optional, Sequence

from pokerfate.core.game_state import Action, ActionType, GameState
from pokerfate.decision.g5_model import G5ActionModel, table_type_for_player_count


class DecisionEngineError(RuntimeError):
    """Raised when an external decision engine is unavailable or out of sync."""


@dataclass
class G5EngineOptions:
    worker_cmd: str
    timeout_sec: float = 1.5
    game_name: str = "pokerfate"
    recent_hands_count: int = 100
    randomly_sample_actions: bool = False
    preflop_charts_level: int = 4
    log_file: Optional[str] = None
    model_file: Optional[str] = None
    max_worker_exits: int = 1


class G5JsonDecisionEngine:
    """Thin RPC client for a long-lived g5 worker.

    The worker protocol is newline-delimited JSON:

        {"id": 1, "method": "start_hand", "params": {...}}
        {"id": 1, "ok": true, "result": {...}}

    A response with ``ok=false`` or a missing response before timeout disables
    the current hand; callers should fall back to the local PokerFate engine.
    """

    def __init__(self, options: G5EngineOptions):
        if not options.worker_cmd.strip():
            raise DecisionEngineError("g5 worker command is empty")
        self.options = options
        self._proc: Optional[subprocess.Popen[str]] = None
        self._stdout_queue: "queue.Queue[dict[str, Any]]" = queue.Queue()
        self._stderr_queue: "queue.Queue[str]" = queue.Queue()
        self._next_id = 0
        self._created_signature: Optional[tuple[Any, ...]] = None
        self._player_ids: list[int] = []
        self._player_names: list[str] = []
        self._display_names: list[str] = []
        self._hand_failed = False
        self._last_error = ""
        self._last_result: dict[str, Any] = {}
        self._player_to_act_index: int | None = None
        self._worker_exit_count = 0
        self._worker_disabled_reason = ""
        self._log_file = Path(options.log_file).expanduser() if options.log_file else None
        if self._log_file is not None:
            self._log_file.parent.mkdir(parents=True, exist_ok=True)

    @property
    def last_error(self) -> str:
        return self._last_error

    @property
    def last_result(self) -> dict[str, Any]:
        return dict(self._last_result)

    @property
    def player_to_act_id(self) -> int | None:
        index = self._player_to_act_index
        if index is None or index < 0 or index >= len(self._player_ids):
            return None
        return self._player_ids[index]

    def disable_current_hand(self, reason: str) -> None:
        self._fail_hand(reason)

    def close(self) -> None:
        proc = self._proc
        self._proc = None
        self._created_signature = None
        if proc is None:
            return
        try:
            if proc.poll() is None:
                proc.terminate()
                proc.wait(timeout=1.0)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass

    def preflight(self) -> dict[str, Any]:
        result = self._rpc(
            "preflight",
            {
                "recent_hands_count": int(self.options.recent_hands_count),
                "randomly_sample_actions": bool(self.options.randomly_sample_actions),
                "preflop_charts_level": int(self.options.preflop_charts_level),
            },
            timeout_sec=max(20.0, float(self.options.timeout_sec)),
        )
        if not isinstance(result, dict):
            raise DecisionEngineError("g5 preflight returned a non-object result")
        return dict(result)

    def start_hand(
        self,
        *,
        players: Sequence[Any],
        dealer_id: int,
        seat_indices: Optional[dict[int, int]] = None,
        dealer_seat_index: Optional[int] = None,
        table_seat_count: int = 6,
        hand_number: int,
        hero_player_id: int,
        big_blind: float,
        small_blind: float,
    ) -> None:
        self._hand_failed = False
        if len(players) < 2:
            raise DecisionEngineError("g5 requires at least two players")
        if len(players) > 6:
            raise DecisionEngineError("g5 supports at most six players")

        ordered_players, sitting_out_indices = self._ordered_players_for_g5(
            players,
            seat_indices=seat_indices,
            dealer_seat_index=dealer_seat_index,
            table_seat_count=table_seat_count,
        )

        self._player_ids = [int(p["player_id"]) for p in ordered_players]
        self._player_names = [self._stable_player_name(pid) for pid in self._player_ids]
        self._display_names = [str(p["name"]) for p in ordered_players]
        stack_sizes = [self._int_chips(p["stack"]) for p in ordered_players]

        try:
            hero_index = self._player_ids.index(int(hero_player_id))
        except ValueError as exc:
            raise DecisionEngineError("hero is missing from g5 player list") from exc

        try:
            button_index = self._player_ids.index(int(dealer_id))
        except ValueError:
            button_index = int(dealer_seat_index) if dealer_seat_index is not None else 0
            if button_index < 0 or button_index >= len(self._player_ids):
                button_index = 0

        signature = (
            tuple(self._player_ids),
            hero_index,
            self._int_chips(big_blind),
            self._int_chips(small_blind),
        )
        if signature != self._created_signature:
            self._rpc(
                "create_game",
                {
                    "game_name": self.options.game_name,
                    "players": self._player_payload(stack_sizes),
                    "hero_index": hero_index,
                    "button_index": button_index,
                    "big_blind": self._int_chips(big_blind),
                    "small_blind": self._int_chips(small_blind),
                    "recent_hands_count": int(self.options.recent_hands_count),
                    "randomly_sample_actions": bool(self.options.randomly_sample_actions),
                    "preflop_charts_level": int(self.options.preflop_charts_level),
                },
            )
            self._created_signature = signature

        self._seed_current_players()

        result = self._rpc(
            "start_hand",
            {
                "game_name": self.options.game_name,
                "hand_number": int(hand_number),
                "button_index": button_index,
                "players": self._player_payload(stack_sizes),
                "sitting_out_indices": sitting_out_indices,
            },
        )
        self._update_player_to_act(result)

    def _ordered_players_for_g5(
        self,
        players: Sequence[Any],
        *,
        seat_indices: Optional[dict[int, int]],
        dealer_seat_index: Optional[int],
        table_seat_count: int,
    ) -> tuple[list[dict[str, Any]], list[int]]:
        if not seat_indices:
            return (
                [
                    {
                        "player_id": int(p.player_id),
                        "name": str(p.name),
                        "stack": p.stack,
                    }
                    for p in players
                ],
                [],
            )

        seat_by_pid = {int(pid): int(seat) for pid, seat in seat_indices.items()}
        if len(set(seat_by_pid.values())) != len(seat_by_pid):
            raise DecisionEngineError("duplicate physical seat index in g5 player list")

        max_seat = max(
            [int(table_seat_count) - 1, *seat_by_pid.values()]
            + ([int(dealer_seat_index)] if dealer_seat_index is not None else [])
        )
        seat_count = max_seat + 1
        if seat_count > 6:
            raise DecisionEngineError(f"g5 supports at most six physical seats, got {seat_count}")

        player_by_seat: dict[int, Any] = {}
        for p in players:
            pid = int(p.player_id)
            seat = seat_by_pid.get(pid)
            if seat is None:
                raise DecisionEngineError(f"missing physical seat for g5 player_id={pid}")
            player_by_seat[int(seat)] = p

        ordered: list[dict[str, Any]] = []
        sitting_out: list[int] = []
        for seat in range(seat_count):
            player = player_by_seat.get(seat)
            if player is None:
                ordered.append({
                    "player_id": -(seat + 1),
                    "name": f"seat:{seat}",
                    "stack": 0,
                })
                sitting_out.append(seat)
                continue
            ordered.append({
                "player_id": int(player.player_id),
                "name": str(player.name),
                "stack": player.stack,
            })
        return ordered, sitting_out

    def _seed_current_players(self) -> None:
        if not self.options.model_file:
            return
        try:
            table_type = table_type_for_player_count(len(self._player_ids))
            model = G5ActionModel.load(self.options.model_file, table_type=table_type)
            payload = model.seed_payload_for(self._player_names, table_type=table_type)
            if not payload:
                return
            self._rpc(
                "seed_player_stats",
                {
                    "game_name": self.options.game_name,
                    "players": payload,
                },
            )
        except Exception as exc:
            raise DecisionEngineError(f"failed to seed g5 player stats: {exc}") from exc

    def deal_hole_cards(self, cards: Sequence[str]) -> None:
        if self._hand_failed:
            return
        if len(cards) < 2:
            return
        self._safe_event(
            "hole_cards",
            {"game_name": self.options.game_name, "cards": [str(c) for c in cards[:2]]},
        )

    def deal_board(self, cards: Sequence[str], street: str) -> None:
        if self._hand_failed or not cards:
            return
        self._safe_event(
            "board",
            {
                "game_name": self.options.game_name,
                "street": str(street).lower(),
                "cards": [str(c) for c in cards],
            },
        )

    def notify_action(
        self,
        *,
        player_id: int,
        action: str,
        amount_added: float,
        total_bet_after: float,
        street: str,
    ) -> None:
        if self._hand_failed:
            return
        try:
            player_index = self._player_ids.index(int(player_id))
        except ValueError:
            self._fail_hand(f"unknown g5 player_id={player_id}")
            return

        self._safe_event(
            "action",
            {
                "game_name": self.options.game_name,
                "player_id": int(player_id),
                "player_index": player_index,
                "action": str(action).lower(),
                "amount_added": self._int_chips(amount_added),
                "total_bet_after": self._int_chips(total_bet_after),
                "street": str(street).lower(),
            },
        )

    def decide(
        self,
        gs: GameState,
        *,
        hero_player_id: int,
        my_current_bet_this_street: float,
    ) -> Action:
        if self._hand_failed:
            raise DecisionEngineError(self._last_error or "g5 hand is disabled")
        try:
            hero_index = self._player_ids.index(int(hero_player_id))
        except ValueError as exc:
            raise DecisionEngineError("hero is missing from g5 state") from exc

        result = self._rpc(
            "decide",
            {
                "game_name": self.options.game_name,
                "hero_player_id": int(hero_player_id),
                "hero_index": hero_index,
                "street": str(gs.street),
                "pot": self._int_chips(gs.pot),
                "current_bet": self._int_chips(gs.current_bet),
                "my_current_bet_this_street": self._int_chips(my_current_bet_this_street),
            },
        )
        if not isinstance(result, dict):
            raise DecisionEngineError("g5 decide returned a non-object result")
        self._last_result = self._with_player_id_ranges(dict(result))
        return self._action_from_result(
            self._last_result,
            gs=gs,
            hero_player_id=hero_player_id,
            my_current_bet_this_street=my_current_bet_this_street,
        )

    def finish_hand(
        self,
        *,
        winner_ids: Sequence[int],
        pot: float,
        winner_payouts: Optional[dict[int, float]],
        final_stacks: Optional[dict[int, float]],
    ) -> None:
        if self._hand_failed:
            return

        payouts_by_id: dict[int, float]
        if winner_payouts:
            payouts_by_id = {int(k): float(v) for k, v in winner_payouts.items()}
        else:
            winners = [int(pid) for pid in winner_ids]
            share = float(pot or 0.0) / len(winners) if winners else 0.0
            payouts_by_id = {pid: share for pid in winners}

        winnings = [
            self._int_chips(payouts_by_id.get(pid, 0.0))
            for pid in self._player_ids
        ]
        self._safe_event(
            "finish_hand",
            {
                "game_name": self.options.game_name,
                "winner_ids": [int(pid) for pid in winner_ids],
                "winnings": winnings,
                "final_stacks": {
                    str(int(pid)): self._int_chips(stack)
                    for pid, stack in (final_stacks or {}).items()
                },
            },
        )

    def _action_from_result(
        self,
        result: dict[str, Any],
        *,
        gs: GameState,
        hero_player_id: int,
        my_current_bet_this_street: float,
    ) -> Action:
        raw_action = (
            result.get("action")
            if "action" in result
            else result.get("actionType", result.get("action_type"))
        )
        action_name = self._normalize_g5_action(raw_action)
        if action_name == "noaction":
            raise DecisionEngineError("g5 returned NoAction")

        by_amount = self._float_value(
            result.get("by_amount", result.get("byAmount", 0.0))
        )
        hero = next((p for p in gs.players if p.player_id == hero_player_id), None)
        to_call = gs.to_call(hero) if hero is not None else 0.0

        if action_name == "fold":
            if to_call <= 0:
                return Action(ActionType.CHECK, 0.0)
            return Action(ActionType.FOLD, 0.0)
        if action_name in {"check"}:
            if to_call > 0:
                return Action(ActionType.CALL, 0.0)
            return Action(ActionType.CHECK, 0.0)
        if action_name == "call":
            if to_call <= 0:
                return Action(ActionType.CHECK, 0.0)
            return Action(ActionType.CALL, 0.0)
        if action_name in {"bet", "raise", "allin"}:
            total_bet_after = float(my_current_bet_this_street) + max(0.0, by_amount)
            if total_bet_after <= float(gs.current_bet) + 1e-9:
                return Action(ActionType.CALL if to_call > 0 else ActionType.CHECK, 0.0)
            return Action(ActionType.RAISE, total_bet_after)

        raise DecisionEngineError(f"unsupported g5 action: {raw_action!r}")

    def _player_payload(self, stack_sizes: Sequence[int]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for idx, pid in enumerate(self._player_ids):
            out.append(
                {
                    "player_id": pid,
                    "name": self._player_names[idx],
                    "display_name": self._display_names[idx],
                    "stack": int(stack_sizes[idx]),
                }
            )
        return out

    def _safe_event(self, method: str, params: dict[str, Any]) -> Any:
        try:
            result = self._rpc(method, params)
            self._update_player_to_act(result)
            return result
        except DecisionEngineError as exc:
            self._fail_hand(str(exc))
            return None

    def _fail_hand(self, reason: str) -> None:
        self._last_error = reason
        self._hand_failed = True
        self._player_to_act_index = None

    def _update_player_to_act(self, result: Any) -> None:
        if not isinstance(result, dict) or "player_to_act" not in result:
            return
        try:
            self._player_to_act_index = int(result.get("player_to_act"))
        except (TypeError, ValueError):
            self._player_to_act_index = None

    def _rpc(
        self,
        method: str,
        params: dict[str, Any],
        *,
        timeout_sec: Optional[float] = None,
    ) -> Any:
        self._log_rpc({"direction": "request", "method": method, "params": params})
        try:
            proc = self._ensure_process()
        except Exception as exc:
            self._log_rpc({
                "direction": "error",
                "method": method,
                "error": str(exc),
            })
            raise
        if proc.stdin is None:
            raise DecisionEngineError("g5 worker stdin is closed")

        self._next_id += 1
        request_id = self._next_id
        payload = {"id": request_id, "method": method, "params": params}
        try:
            proc.stdin.write(json.dumps(payload, separators=(",", ":")) + "\n")
            proc.stdin.flush()
        except Exception as exc:
            self.close()
            self._log_rpc({
                "direction": "error",
                "method": method,
                "error": str(exc),
            })
            raise DecisionEngineError(f"failed to write to g5 worker: {exc}") from exc

        timeout = self.options.timeout_sec if timeout_sec is None else timeout_sec
        deadline = time.monotonic() + max(0.05, float(timeout))
        while True:
            returncode = proc.poll()
            if returncode is not None:
                detail = self._drain_stderr()
                reason = self._record_worker_exit(returncode, method=method)
                self.close()
                if detail:
                    reason = f"{reason} ({detail})"
                self._log_rpc({
                    "direction": "error",
                    "method": method,
                    "error": reason,
                })
                raise DecisionEngineError(reason)
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                err = self._drain_stderr()
                detail = f" ({err})" if err else ""
                reason = self._disable_worker(
                    f"g5 worker timeout on {method}{detail}",
                    method=method,
                )
                self.close()
                self._log_rpc({
                    "direction": "error",
                    "method": method,
                    "error": reason,
                })
                raise DecisionEngineError(reason)
            try:
                response = self._stdout_queue.get(timeout=min(remaining, 0.05))
            except queue.Empty:
                continue
            if response.get("id") != request_id:
                continue
            if not response.get("ok", False):
                err = str(response.get("error") or f"g5 worker rejected {method}")
                self._log_rpc({
                    "direction": "response",
                    "method": method,
                    "ok": False,
                    "error": err,
                })
                raise DecisionEngineError(err)
            self._log_rpc({
                "direction": "response",
                "method": method,
                "ok": True,
                "result": response.get("result"),
            })
            return response.get("result")

    def _ensure_process(self) -> subprocess.Popen[str]:
        if self._worker_disabled_reason:
            raise DecisionEngineError(self._worker_disabled_reason)
        if self._proc is not None and self._proc.poll() is None:
            return self._proc
        if self._proc is not None:
            returncode = self._proc.poll()
            if returncode is not None:
                reason = self._record_worker_exit(returncode, method="ensure_process")
                self._proc = None
                if self._worker_disabled_reason:
                    raise DecisionEngineError(reason)

        argv = shlex.split(self.options.worker_cmd)
        if not argv:
            raise DecisionEngineError("g5 worker command is empty")
        try:
            self._proc = subprocess.Popen(
                argv,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                bufsize=1,
            )
        except Exception as exc:
            self._proc = None
            raise DecisionEngineError(f"failed to start g5 worker: {exc}") from exc

        assert self._proc.stdout is not None
        assert self._proc.stderr is not None
        threading.Thread(
            target=self._read_stdout,
            args=(self._proc.stdout,),
            daemon=True,
        ).start()
        threading.Thread(
            target=self._read_stderr,
            args=(self._proc.stderr,),
            daemon=True,
        ).start()
        return self._proc

    def _record_worker_exit(self, returncode: int, *, method: str) -> str:
        reason = f"g5 worker exited code={returncode} during {method}"
        self._worker_exit_count += 1
        max_exits = max(1, int(self.options.max_worker_exits or 1))
        if self._worker_exit_count >= max_exits:
            self._worker_disabled_reason = (
                f"{reason}; disabling g5 for this proxy process after "
                f"{self._worker_exit_count} unexpected worker exit(s)"
            )
        self._log_rpc({
            "direction": "worker_exit",
            "method": method,
            "returncode": returncode,
            "exit_count": self._worker_exit_count,
            "disabled": bool(self._worker_disabled_reason),
            "reason": self._worker_disabled_reason or reason,
        })
        return self._worker_disabled_reason or reason

    def _disable_worker(self, reason: str, *, method: str) -> str:
        self._worker_disabled_reason = (
            f"{reason}; disabling g5 for this proxy process"
        )
        self._log_rpc({
            "direction": "worker_disabled",
            "method": method,
            "reason": self._worker_disabled_reason,
        })
        return self._worker_disabled_reason

    def _read_stdout(self, pipe: Iterable[str]) -> None:
        for line in pipe:
            text = line.strip()
            if not text:
                continue
            try:
                item = json.loads(text)
            except json.JSONDecodeError:
                self._stderr_queue.put(f"non-json stdout: {text[:200]}")
                continue
            if isinstance(item, dict):
                self._stdout_queue.put(item)

    def _read_stderr(self, pipe: Iterable[str]) -> None:
        for line in pipe:
            text = line.strip()
            if text:
                self._stderr_queue.put(text)

    def _drain_stderr(self) -> str:
        lines: list[str] = []
        while True:
            try:
                lines.append(self._stderr_queue.get_nowait())
            except queue.Empty:
                break
        return " | ".join(lines[-3:])

    def _log_rpc(self, event: dict[str, Any]) -> None:
        if self._log_file is None:
            return
        payload = {
            "ts": datetime.now(timezone.utc).isoformat(),
            **self._compact_log_event(event),
        }
        try:
            with self._log_file.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(payload, ensure_ascii=False) + "\n")
        except OSError:
            pass

    def _with_player_id_ranges(self, result: dict[str, Any]) -> dict[str, Any]:
        ranges = result.get("ranges")
        if not isinstance(ranges, list):
            return result
        by_pid: dict[str, dict[str, float]] = {}
        for row in ranges:
            if not isinstance(row, dict):
                continue
            pid = row.get("player_id")
            if pid is None:
                idx = row.get("player_index")
                try:
                    pid = self._player_ids[int(idx)]
                except Exception:
                    continue
            range_map = row.get("range_169")
            if isinstance(range_map, dict):
                by_pid[str(int(pid))] = {
                    str(k): float(v or 0.0)
                    for k, v in range_map.items()
                }
        if by_pid:
            result["ranges_by_player_id"] = by_pid
        return result

    @staticmethod
    def _compact_log_event(event: dict[str, Any]) -> dict[str, Any]:
        def _compact(value: Any) -> Any:
            if not isinstance(value, dict):
                return value
            out = dict(value)
            ranges = out.pop("ranges", None)
            by_pid = out.pop("ranges_by_player_id", None)
            if isinstance(ranges, list):
                out["ranges_summary"] = {
                    "players": len(ranges),
                    "categories": sum(
                        len(row.get("range_169", {}))
                        for row in ranges
                        if isinstance(row, dict)
                    ),
                }
            if isinstance(by_pid, dict):
                out["ranges_by_player_id_summary"] = {
                    "players": len(by_pid),
                    "categories": sum(
                        len(rng)
                        for rng in by_pid.values()
                        if isinstance(rng, dict)
                    ),
                }
            return out

        compacted = dict(event)
        if "result" in compacted:
            compacted["result"] = _compact(compacted["result"])
        return compacted

    @staticmethod
    def _stable_player_name(player_id: int) -> str:
        pid = int(player_id)
        if pid >= 0:
            return f"uid:{pid}"
        return f"seat:{abs(pid) - 1}"

    @staticmethod
    def _int_chips(value: float) -> int:
        return int(round(float(value or 0.0)))

    @staticmethod
    def _float_value(value: Any) -> float:
        try:
            return float(value or 0.0)
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _normalize_g5_action(value: Any) -> str:
        if isinstance(value, str):
            text = value.strip().lower()
            return text.replace("_", "").replace("-", "")
        try:
            enum_value = int(value)
        except (TypeError, ValueError):
            return ""
        return {
            0: "fold",
            1: "check",
            2: "call",
            3: "bet",
            4: "raise",
            5: "allin",
            8: "noaction",
        }.get(enum_value, "")
