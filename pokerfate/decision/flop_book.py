"""Offline flop CFR book adapter for PokerFate decisions.

The book is copied into this repository under ``pokerfate/data/flop_book``.
Runtime lookup is deliberately narrow: only heads-up SRP spots covered by the
book are accepted. Everything else returns a structured fallback reason.
"""

from __future__ import annotations

import json
import math
import sqlite3
import time
import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional, Sequence

import numpy as np

from pokerfate.core.game_state import Action, ActionType, GameState, Player
from pokerfate.decision.opponent_numeric_prior import (
    NumericOpponentPrior,
    build_numeric_prior,
)


RANKS = "23456789TJQKA"
SUITS = "cdhs"
DEFAULT_BOOK_DIR = Path(__file__).resolve().parents[1] / "data" / "flop_book" / "v2"


class BookMiss(Exception):
    """The offline flop book cannot answer this spot; caller should fall back."""


@dataclass
class FlopBookOptions:
    book_dir: Optional[str] = None
    min_effective_stack_bb: float = 40.0
    max_effective_stack_bb: float = 170.0
    max_pot_ratio_delta: float = 0.35
    exploit_enabled: bool = True
    max_exploit_confidence: float = 0.25


@dataclass
class FlopBookDecisionContext:
    gs: GameState
    hero_player_id: int
    street_start_pot: float
    villain_profile_provider: Optional[Callable[[int], Any]] = None
    exploit_adjustments_provider: Optional[Callable[[int], dict[str, Any]]] = None


def _card_idx(cs: str) -> int:
    return RANKS.index(cs[0]) * 4 + SUITS.index(cs[1])


def _sort_key(card: str) -> tuple[int, int]:
    return (-RANKS.index(card[0]), SUITS.index(card[1]))


def _combo_rows(board: str) -> dict[frozenset[int], int]:
    dead = {_card_idx(board[i:i + 2]) for i in (0, 2, 4)}
    rows: dict[frozenset[int], int] = {}
    row = 0
    for i in range(52):
        for j in range(i + 1, 52):
            if i in dead or j in dead:
                continue
            rows[frozenset((i, j))] = row
            row += 1
    return rows


class FlopBook:
    """Reader for packed v2 flop book sqlite shards."""

    def __init__(self, book_dir: Path | str = DEFAULT_BOOK_DIR):
        self.dir = Path(book_dir)
        self.meta = json.loads((self.dir / "meta.json").read_text())
        self.iso = json.loads((self.dir / "flop_iso_map.json").read_text())
        self.clusters = json.loads((self.dir / "flop_clusters.json").read_text())["mapping"]
        self._db: dict[str, sqlite3.Connection] = {}
        self._row_cache: dict[str, dict[frozenset[int], int]] = {}

    def check_consistency(
        self,
        abstraction_hash: Optional[str] = None,
        range_hash: Optional[str] = None,
    ) -> bool:
        if abstraction_hash and self.meta.get("abstraction_hash") != abstraction_hash:
            return False
        if range_hash and self.meta.get("range_hash") != range_hash:
            return False
        return True

    def close(self) -> None:
        for conn in self._db.values():
            try:
                conn.close()
            except Exception:
                pass
        self._db = {}

    def _conn(self, scenario_id: str) -> sqlite3.Connection:
        if scenario_id not in self._db:
            path = self.dir / f"{scenario_id}.db"
            if not path.is_file():
                raise BookMiss(f"scenario_db_missing:{scenario_id}")
            self._db[scenario_id] = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        return self._db[scenario_id]

    def _rows(self, board: str) -> dict[frozenset[int], int]:
        if board not in self._row_cache:
            self._row_cache[board] = _combo_rows(board)
        return self._row_cache[board]

    def _canonicalize(self, flop: str) -> tuple[str, str]:
        key = self._normalize(flop)
        try:
            canon, perm = self.iso[key]
        except KeyError as exc:
            raise BookMiss(f"flop_iso_missing:{key}") from exc
        return canon, perm

    def _map_hand_exact(self, hero: str, perm: str) -> tuple[str, str]:
        smap = dict(zip(SUITS, perm))
        return hero[0] + smap[hero[1]], hero[2] + smap[hero[3]]

    def _map_hand_cross(
        self,
        hero_canon: tuple[str, str],
        canonical: str,
        representative: str,
        rows: dict[frozenset[int], int],
    ) -> Optional[int]:
        c_board = sorted([canonical[0:2], canonical[2:4], canonical[4:6]], key=_sort_key)
        r_board = sorted(
            [representative[0:2], representative[2:4], representative[4:6]],
            key=_sort_key,
        )
        rank_at = {c_board[i][0]: r_board[i][0] for i in range(3)}
        suit_at = {c_board[i][1]: r_board[i][1] for i in range(3)}
        r_board_ranks = {card[0] for card in r_board}
        r_dead = {_card_idx(card) for card in r_board}

        def map_card(card: str) -> Optional[str]:
            rank, suit = card[0], card[1]
            if rank in rank_at:
                new_rank = rank_at[rank]
            elif rank not in r_board_ranks:
                new_rank = rank
            else:
                candidates = sorted(
                    (r for r in RANKS if r not in r_board_ranks),
                    key=lambda r: abs(RANKS.index(r) - RANKS.index(rank)),
                )
                new_rank = candidates[0] if candidates else None
            if new_rank is None:
                return None
            return new_rank + suit_at.get(suit, suit)

        mapped_1 = map_card(hero_canon[0])
        mapped_2 = map_card(hero_canon[1])
        if mapped_1 is None or mapped_2 is None:
            return None
        idx_1 = _card_idx(mapped_1)
        idx_2 = _card_idx(mapped_2)
        if idx_1 == idx_2 or idx_1 in r_dead or idx_2 in r_dead:
            for alt_suit in SUITS:
                alt = mapped_2[0] + alt_suit
                alt_idx = _card_idx(alt)
                if alt_idx not in r_dead and alt != mapped_1:
                    idx_2 = alt_idx
                    break
            if idx_1 == idx_2 or idx_1 in r_dead or idx_2 in r_dead:
                return None
        return rows.get(frozenset((idx_1, idx_2)))

    def lookup(
        self,
        scenario_id: str,
        flop: str,
        hero_cards: str,
        action_line: Optional[list[tuple[str, float]]] = None,
    ) -> dict[str, Any]:
        action_line = action_line or []
        flop = self._normalize(flop)
        canonical, perm = self._canonicalize(flop)
        try:
            representative = self.clusters[canonical]
        except KeyError as exc:
            raise BookMiss(f"flop_cluster_missing:{canonical}") from exc
        exact = canonical == representative

        conn = self._conn(scenario_id)
        node_path, node = self._walk_path(conn, representative, action_line)
        matrix = self._decode(node)
        rows = self._rows(representative)

        hero_canon = self._map_hand_exact(hero_cards, perm)
        if exact:
            row_idx = rows.get(frozenset((_card_idx(hero_canon[0]), _card_idx(hero_canon[1]))))
        else:
            row_idx = self._map_hand_cross(hero_canon, canonical, representative, rows)
        if row_idx is None:
            raise BookMiss(f"hero_combo_unmapped:{hero_cards}:{representative}")

        raw = matrix[row_idx].astype(np.float64)
        total = float(raw.sum())
        if total <= 0.0:
            raise BookMiss(f"hero_combo_not_in_book_range:{hero_cards}:{scenario_id}")

        strategy = {action: float(prob / total) for action, prob in zip(node["actions"], raw)}
        return {
            "strategy": strategy,
            "actions": list(node["actions"]),
            "node_path": node_path,
            "actor": int(node["actor"]),
            "node_pot_bb": float(node["pot"]),
            "flop_canonical": canonical,
            "flop_representative": representative,
            "exact": bool(exact),
            "scenario": scenario_id,
        }

    def _walk_path(
        self,
        conn: sqlite3.Connection,
        flop_id: str,
        action_line: list[tuple[str, float]],
    ) -> tuple[str, dict[str, Any]]:
        path = "r"
        node = self._fetch(conn, flop_id, path)
        for kind, size in action_line:
            chosen = self._match_action(list(node["actions"]), kind, float(size), float(node["pot"]))
            if chosen is None:
                raise BookMiss(f"action_path_miss:{kind}:{size}:path={path}:actions={node['actions']}")
            path = f"{path}:{chosen}"
            node = self._fetch(conn, flop_id, path)
        return path, node

    @staticmethod
    def _match_action(
        actions: list[str],
        kind: str,
        size_bb: float,
        pot_bb: float,
    ) -> Optional[str]:
        simple = {"check": "x", "fold": "f", "call": "c"}
        if kind in simple:
            return simple[kind] if simple[kind] in actions else None

        if kind == "allin":
            if "ai" in actions:
                return "ai"
            candidates = [a for a in actions if a.startswith(("b", "r"))]
            return max(candidates, default=None, key=_book_action_size_key)

        if kind == "bet":
            candidates = [a for a in actions if a.startswith("b")]
            if not candidates:
                return None
            pct = size_bb / max(float(pot_bb), 1e-9) * 100.0
            best = min(candidates, key=lambda a: abs(float(a[1:]) - pct))
            diff = abs(float(best[1:]) - pct)
            rel = diff / max(abs(pct), 1.0)
            return best if diff <= 50.0 and rel <= 0.60 else None

        if kind == "raise":
            candidates = [a for a in actions if a.startswith("r")]
            if "ai" in actions:
                candidates.append("ai")
            if not candidates:
                return None
            if len(candidates) == 1:
                return candidates[0]
            return min(candidates, key=_book_action_size_key)

        return None

    def _fetch(self, conn: sqlite3.Connection, flop_id: str, node_path: str) -> dict[str, Any]:
        cur = conn.execute(
            "SELECT actor, pot, actions, strategy FROM nodes WHERE flop_id=? AND node_path=?",
            (flop_id, node_path),
        )
        row = cur.fetchone()
        if row is None:
            raise BookMiss(f"node_missing:{flop_id}:{node_path}")
        actor, pot, actions, blob = row
        return {
            "actor": actor,
            "pot": pot,
            "actions": json.loads(actions),
            "blob": blob,
            "node_path": node_path,
        }

    @staticmethod
    def _decode(node: dict[str, Any]) -> np.ndarray:
        action_count = len(node["actions"])
        return np.frombuffer(zlib.decompress(node["blob"]), dtype="<u2").reshape(1176, action_count)

    @staticmethod
    def _normalize(flop: str) -> str:
        if len(flop) != 6:
            raise BookMiss(f"invalid_flop:{flop}")
        cards = [flop[0:2], flop[2:4], flop[4:6]]
        return "".join(sorted(cards, key=_sort_key))


class FlopBookDecisionEngine:
    """Heads-up SRP flop book with local fallback reasons."""

    def __init__(self, options: Optional[FlopBookOptions] = None, book: Optional[FlopBook] = None):
        self.options = options or FlopBookOptions()
        self.book = book or FlopBook(self.options.book_dir or DEFAULT_BOOK_DIR)
        self._last_result: dict[str, Any] = {}
        self._last_error = ""

    @property
    def last_result(self) -> dict[str, Any]:
        return dict(self._last_result)

    @property
    def last_error(self) -> str:
        return self._last_error

    def close(self) -> None:
        self.book.close()

    def decide(self, ctx: FlopBookDecisionContext) -> Optional[Action]:
        t0 = time.perf_counter()
        self._last_result = {}
        self._last_error = ""

        prepared = self._prepare(ctx)
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        if prepared is None:
            if self._last_result:
                self._last_result["elapsed_ms"] = elapsed_ms
            return None
        lookup, meta, hero, facing_bet = prepared

        profile = self._profile(ctx, meta["villain_player_id"])
        adjustments = self._adjustments(ctx, meta["villain_player_id"])
        selection = _select_book_action(
            lookup["strategy"],
            profile=profile,
            adjustments=adjustments,
            street="flop",
            facing_bet=facing_bet,
            max_confidence=self.options.max_exploit_confidence,
            enabled=self.options.exploit_enabled,
            big_blind=ctx.gs.big_blind,
        )
        selected_label = str(selection["selected_label"])
        action = self._action_from_label(
            selected_label,
            ctx.gs,
            hero,
            node_pot_bb=float(lookup["node_pot_bb"]),
        )
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        if action is None:
            reason = f"unsupported_book_action:{selected_label}"
            self._fallback(reason, **meta, elapsed_ms=elapsed_ms)
            return None

        selected_prob = float(selection.get("selected_prob", lookup["strategy"].get(selected_label, 0.0)))
        self._last_result = {
            **meta,
            "status": "ok",
            "elapsed_ms": elapsed_ms,
            "node_path": lookup.get("node_path"),
            "node_actor": lookup.get("actor"),
            "node_actions": list(lookup.get("actions") or []),
            "node_pot_bb": round(float(lookup.get("node_pot_bb") or 0.0), 4),
            "strategy": {k: round(float(v), 6) for k, v in lookup["strategy"].items()},
            "selected_label": selected_label,
            "selected_prob": round(selected_prob, 6),
            "action": action.action_type.name.lower(),
            "amount": float(action.amount or 0.0),
            "flop_canonical": lookup.get("flop_canonical"),
            "flop_representative": lookup.get("flop_representative"),
            "exact": bool(lookup.get("exact")),
            "exploit": selection.get("exploit") or {},
        }
        return action

    def _prepare(
        self,
        ctx: FlopBookDecisionContext,
    ) -> Optional[tuple[dict[str, Any], dict[str, Any], Player, bool]]:
        gs = ctx.gs
        street = str(gs.street).lower()
        if street != "flop":
            self._fallback("street_not_supported", street=street)
            return None
        if len(gs.board) != 3:
            self._fallback("flop_requires_three_board_cards", board_len=len(gs.board))
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

        scenario = self._scenario_from_preflop(gs, oop, ip)
        if scenario is None:
            return None

        prefix = self._prefix_from_history(
            gs.action_history,
            street="flop",
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

        bb = max(float(gs.big_blind or 0.0), 1e-9)
        pot_bb = max(0.0, float(ctx.street_start_pot or gs.pot or 0.0)) / bb
        expected_pot = float(scenario["pot_bb"])
        pot_delta = abs(pot_bb - expected_pot) / max(expected_pot, 1e-9)
        if pot_delta > float(self.options.max_pot_ratio_delta):
            self._fallback(
                "book_pot_mismatch",
                street=street,
                pot_bb=round(pot_bb, 4),
                expected_pot_bb=round(expected_pot, 4),
                pot_ratio_delta=round(pot_delta, 4),
            )
            return None

        effective_stack_bb = min(
            float(oop.stack or 0.0) + float(oop.current_bet or 0.0),
            float(ip.stack or 0.0) + float(ip.current_bet or 0.0),
        ) / bb
        if (
            effective_stack_bb < float(self.options.min_effective_stack_bb)
            or effective_stack_bb > float(self.options.max_effective_stack_bb)
        ):
            self._fallback(
                "book_stack_out_of_range",
                street=street,
                effective_stack_bb=round(effective_stack_bb, 4),
                min_effective_stack_bb=float(self.options.min_effective_stack_bb),
                max_effective_stack_bb=float(self.options.max_effective_stack_bb),
            )
            return None

        board = "".join(str(card) for card in gs.board)
        hero_combo = f"{hero.hole_cards[0]}{hero.hole_cards[1]}"
        try:
            lookup = self.book.lookup(
                str(scenario["scenario_id"]),
                board,
                hero_combo,
                list(prefix["prefix"]),
            )
        except BookMiss as exc:
            self._fallback(
                "book_miss",
                street=street,
                scenario=scenario["scenario_id"],
                detail=str(exc),
            )
            return None
        except Exception as exc:
            self._fallback(
                "book_lookup_error",
                street=street,
                scenario=scenario["scenario_id"],
                detail=str(exc),
            )
            return None

        hero_actor = 1 if hero_is_ip else 0
        if int(lookup.get("actor", -1)) != hero_actor:
            self._fallback(
                "book_actor_not_hero",
                street=street,
                scenario=scenario["scenario_id"],
                node_actor=lookup.get("actor"),
                hero_actor=hero_actor,
                node_path=lookup.get("node_path"),
            )
            return None

        meta = {
            "engine": "cfr",
            "component": "flop_book",
            "street": "flop",
            "board": board,
            "hero_player_id": int(hero.player_id),
            "villain_player_id": int(villain.player_id),
            "hero_side": "ip" if hero_is_ip else "oop",
            "hero_combo": hero_combo,
            "scenario": scenario["scenario_id"],
            "positions": {
                "oop": scenario["oop_pos"],
                "ip": scenario["ip_pos"],
                "opener": scenario["opener_pos"],
                "defender": scenario["defender_pos"],
            },
            "pot_bb": round(pot_bb, 4),
            "expected_pot_bb": round(expected_pot, 4),
            "effective_stack_bb": round(effective_stack_bb, 4),
            "prefix": list(prefix["prefix"]),
            "book_version": self.book.meta.get("book_version"),
            "book_abstraction_hash": self.book.meta.get("abstraction_hash"),
            "book_range_hash": self.book.meta.get("range_hash"),
        }
        return lookup, meta, hero, bool(gs.to_call(hero) > 0.0)

    def _scenario_from_preflop(
        self,
        gs: GameState,
        oop: Player,
        ip: Player,
    ) -> Optional[dict[str, Any]]:
        active_ids = {int(oop.player_id), int(ip.player_id)}
        preflop = [
            item
            for item in gs.action_history
            if len(item) >= 3 and str(item[2]).lower() == "preflop"
        ]
        raises = [
            (int(pid), action)
            for pid, action, _street in preflop
            if getattr(action, "action_type", None) == ActionType.RAISE
        ]
        if len(raises) != 1:
            self._fallback("book_requires_single_raise_srp", raise_count=len(raises))
            return None

        opener_id = raises[0][0]
        if opener_id not in active_ids:
            self._fallback("book_opener_not_active", opener_id=opener_id)
            return None
        defender = ip if opener_id == oop.player_id else oop
        defender_id = int(defender.player_id)

        non_active_calls = [
            int(pid)
            for pid, action, _street in preflop
            if (
                int(pid) not in active_ids
                and getattr(action, "action_type", None) == ActionType.CALL
            )
        ]
        if non_active_calls:
            self._fallback("book_requires_hu_from_flop_start", callers=non_active_calls[:4])
            return None

        defender_called = any(
            int(pid) == defender_id and getattr(action, "action_type", None) == ActionType.CALL
            for pid, action, _street in preflop
        )
        if not defender_called:
            self._fallback("book_defender_call_missing", defender_id=defender_id)
            return None

        opener = _player_by_id(gs.players, opener_id)
        if opener is None:
            self._fallback("book_opener_missing", opener_id=opener_id)
            return None

        opener_pos = _book_position(gs.position_of(opener))
        defender_pos = _book_position(gs.position_of(defender))
        oop_pos = _book_position(gs.position_of(oop))
        ip_pos = _book_position(gs.position_of(ip))
        if opener_pos in {"UTG", "MP", "CO", "BTN"} and defender_pos == "BB":
            if oop.player_id != defender.player_id or ip.player_id != opener.player_id:
                self._fallback("book_position_order_mismatch", opener_pos=opener_pos, defender_pos=defender_pos)
                return None
            scenario_id = f"{opener_pos}vBB_srp100"
        elif opener_pos == "SB" and defender_pos == "BB":
            if oop_pos != "SB" or ip_pos != "BB":
                self._fallback("book_sb_vs_bb_position_mismatch", oop_pos=oop_pos, ip_pos=ip_pos)
                return None
            scenario_id = "SBvBB_srp100"
        else:
            self._fallback("book_scenario_not_covered", opener_pos=opener_pos, defender_pos=defender_pos)
            return None

        scenario_meta = next(
            (s for s in list(self.book.meta.get("scenarios") or []) if s.get("id") == scenario_id),
            {},
        )
        return {
            "scenario_id": scenario_id,
            "pot_bb": float(scenario_meta.get("pot") or 0.0),
            "opener_pos": opener_pos,
            "defender_pos": defender_pos,
            "oop_pos": oop_pos,
            "ip_pos": ip_pos,
        }

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
                self._fallback("book_requires_hu_from_flop_start", street=street, player_id=pid)
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

    def _action_from_label(
        self,
        label: str,
        gs: GameState,
        hero: Player,
        *,
        node_pot_bb: float,
    ) -> Optional[Action]:
        to_call = gs.to_call(hero)
        label = str(label)
        if label == "f":
            return Action(ActionType.FOLD if to_call > 0.0 else ActionType.CHECK, 0.0)
        if label == "x":
            return Action(ActionType.CHECK, 0.0) if to_call <= 0.0 else None
        if label == "c":
            return Action(ActionType.CALL if to_call > 0.0 else ActionType.CHECK, 0.0)

        max_total = float(hero.current_bet or 0.0) + float(hero.stack or 0.0)
        bb = max(float(gs.big_blind or 0.0), 1e-9)
        total_bet = 0.0
        if label == "ai":
            total_bet = max_total
        elif label.startswith("b"):
            if to_call > 0.0:
                return None
            pct = float(label[1:])
            total_bet = max(float(hero.current_bet or 0.0), node_pot_bb * pct / 100.0 * bb)
        elif label.startswith("r") and label.endswith("x"):
            if float(gs.current_bet or 0.0) <= 0.0:
                return None
            multiple = float(label[1:-1])
            total_bet = float(gs.current_bet or 0.0) * multiple
        else:
            return None

        total_bet = min(max_total, max(0.0, total_bet))
        if total_bet <= float(gs.current_bet or 0.0) + 1e-9:
            return Action(ActionType.CALL if to_call > 0.0 else ActionType.CHECK, 0.0)
        return Action(ActionType.RAISE, total_bet)

    def _profile(self, ctx: FlopBookDecisionContext, villain_id: int) -> Any:
        if ctx.villain_profile_provider is None:
            return None
        try:
            return ctx.villain_profile_provider(int(villain_id))
        except Exception:
            return None

    def _adjustments(self, ctx: FlopBookDecisionContext, villain_id: int) -> dict[str, Any]:
        if ctx.exploit_adjustments_provider is None:
            return {}
        try:
            raw = ctx.exploit_adjustments_provider(int(villain_id))
        except Exception:
            return {}
        return raw if isinstance(raw, dict) else {}

    def _fallback(self, reason: str, **extra: Any) -> None:
        self._last_error = reason
        self._last_result = {
            "engine": "cfr",
            "component": "flop_book",
            "status": "fallback",
            "reason": reason,
            **extra,
        }


def _select_book_action(
    strategy: dict[str, float],
    *,
    profile: Any,
    adjustments: dict[str, Any],
    street: str,
    facing_bet: bool,
    max_confidence: float,
    enabled: bool,
    big_blind: Any = None,
) -> dict[str, Any]:
    gto_label, gto_prob = _select_strategy_action(strategy)
    out: dict[str, Any] = {
        "selected_label": gto_label,
        "selected_prob": gto_prob,
        "exploit": {
            "enabled": bool(enabled),
            "used": False,
            "mode": "probability_bias_no_evs",
        },
    }
    if not enabled:
        return out

    numeric_prior = build_numeric_prior(profile, adjustments, street, big_blind)
    confidence = _exploit_confidence(
        profile,
        adjustments,
        street,
        max_confidence,
        numeric_prior=numeric_prior,
    )
    if confidence <= 1e-6:
        return out

    fold_bias, sticky_bias, raise_bias = _response_biases(
        profile,
        adjustments,
        street,
        numeric_prior=numeric_prior,
    )
    bluff_ag = float(adjustments.get("bluff_ag_scale", 0.55) or 0.55)
    value_ag = float(adjustments.get("value_ag_scale", 0.85) or 0.85)
    bluff_signal = bluff_ag - 0.55
    value_signal = value_ag - 0.85
    signal = max(
        abs(fold_bias),
        abs(sticky_bias),
        abs(raise_bias),
        abs(bluff_signal),
        abs(value_signal),
    )
    if signal <= 1e-9:
        out["exploit"].update({
            "confidence": round(confidence, 4),
            "numeric_prior": numeric_prior.diagnostics,
            "reason": "no_profile_bias",
        })
        return out

    adjusted: dict[str, float] = {}
    for label, prob in strategy.items():
        kind = _book_action_kind(label)
        mult = 1.0
        if kind in {"Bet", "Raise", "AllIn"}:
            if facing_bet:
                mult += confidence * (0.55 * fold_bias + 0.20 * bluff_signal - 0.25 * max(0.0, raise_bias))
            else:
                mult += confidence * (1.15 * fold_bias - 0.75 * sticky_bias - 0.35 * max(0.0, raise_bias))
        elif kind in {"Check", "Call"}:
            if facing_bet:
                mult += confidence * (0.65 * raise_bias + 0.45 * bluff_signal + 0.25 * sticky_bias - 0.35 * value_signal)
            else:
                mult += confidence * (-0.55 * fold_bias + 0.35 * sticky_bias + 0.20 * raise_bias)
        elif kind == "Fold":
            mult += confidence * (-0.70 * raise_bias - 0.50 * bluff_signal + 0.40 * value_signal)
        adjusted[label] = max(0.0, float(prob or 0.0)) * _clamp(mult, 0.35, 1.90)

    total = sum(adjusted.values())
    if total <= 1e-12:
        return out
    adjusted = {label: value / total for label, value in adjusted.items()}
    selected_label, selected_prob = _select_strategy_action(adjusted)
    out.update({
        "selected_label": selected_label,
        "selected_prob": selected_prob,
        "exploit": {
            "enabled": True,
            "used": True,
            "mode": "probability_bias_no_evs",
            "confidence": round(confidence, 4),
            "numeric_prior": numeric_prior.diagnostics,
            "gto_strategy": {k: round(float(v), 6) for k, v in strategy.items()},
            "adjusted_strategy": {k: round(float(v), 6) for k, v in adjusted.items()},
            "biases": {
                "fold": round(fold_bias, 4),
                "sticky": round(sticky_bias, 4),
                "raise": round(raise_bias, 4),
            },
        },
    })
    return out


def _select_strategy_action(strategy: dict[str, float]) -> tuple[str, float]:
    order = {"f": 0, "x": 1, "c": 2, "b": 3, "r": 4, "ai": 5}

    def key(item: tuple[str, float]) -> tuple[float, int]:
        label, prob = item
        prefix = "ai" if str(label) == "ai" else str(label)[:1]
        return float(prob), order.get(prefix, 0)

    return max(strategy.items(), key=key)


def _response_biases(
    profile: Any,
    adjustments: dict[str, Any],
    street: str,
    *,
    numeric_prior: Optional[NumericOpponentPrior] = None,
) -> tuple[float, float, float]:
    prior = numeric_prior or build_numeric_prior(profile, adjustments, street)
    return prior.fold_bias, prior.sticky_bias, prior.raise_bias


def _exploit_confidence(
    profile: Any,
    adjustments: dict[str, Any],
    street: str,
    max_confidence: float,
    *,
    numeric_prior: Optional[NumericOpponentPrior] = None,
) -> float:
    if profile is None and not adjustments:
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
    conf = 0.03 + 0.13 * hand_conf + 0.08 * street_conf + 0.10 * prior.confidence
    server_prior = (
        _profile_float(profile, "server_af_prior", 0.0) > 0.0
        or _profile_float(profile, "server_wtsd_prior", 0.0) > 0.0
    )
    if hands < 10 and not server_prior:
        conf = min(conf, 0.08)
    elif hands < 40 and street_samples < 10 and not server_prior:
        conf = min(conf, 0.12)
    return _clamp(conf, 0.0, max(0.0, float(max_confidence)))


def _book_action_kind(label: str) -> str:
    label = str(label)
    if label == "f":
        return "Fold"
    if label == "x":
        return "Check"
    if label == "c":
        return "Call"
    if label == "ai":
        return "AllIn"
    if label.startswith("b"):
        return "Bet"
    if label.startswith("r"):
        return "Raise"
    return label


def _book_position(position: str) -> str:
    pos = str(position or "").strip().upper().replace(" ", "")
    if pos in {"BB", "SB", "CO", "BTN", "BU"}:
        return "BTN" if pos == "BU" else pos
    if pos == "UTG":
        return "UTG"
    if pos in {"MP", "UTG+1", "UTG1", "UTG+2", "UTG2", "LJ", "HJ"}:
        return "MP"
    return pos


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


def _player_by_id(players: Sequence[Player], player_id: int) -> Optional[Player]:
    return next((p for p in players if p.player_id == player_id), None)


def _book_action_size_key(label: str) -> float:
    label = str(label)
    if label == "ai":
        return 999.0
    try:
        return float(label[1:-1] if label.endswith("x") else label[1:])
    except ValueError:
        return 0.0


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, float(value)))
