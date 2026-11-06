"""Persistent opponent stats in g5's native PlayerStats shape.

This module intentionally mirrors ``G5.Logic.PlayerStats.increment`` instead
of reusing PokerFate's higher-level opponent model.  The exported arrays are
fed back to g5 as ``ActionStats[]`` for hot-starting its Bayesian model.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Sequence, TYPE_CHECKING

from pokerfate.core.game_state import Action, ActionType

if TYPE_CHECKING:
    from pokerfate.bot.opponent_model import OpponentModel


TABLE_SIX_MAX = "SixMax"
TABLE_HEADS_UP = "HeadsUp"

_POSITIONS = {
    "SmallBlind": 0,
    "BigBlind": 1,
    "UTG": 2,
    "HJ": 3,
    "CutOff": 4,
    "Button": 5,
}
_STREETS = {"flop": 0, "turn": 1, "river": 2}
_ACTION_FOLD = "Fold"
_ACTION_CHECK = "Check"
_ACTION_CALL = "Call"
_ACTION_BET = "Bet"
_ACTION_RAISE = "Raise"
_ACTION_ALL_IN = "AllIn"


@dataclass
class G5ActionStats:
    br: int = 0
    cc: int = 0
    fold: int = 0

    @classmethod
    def from_raw(cls, raw: Any) -> "G5ActionStats":
        if isinstance(raw, dict):
            return cls(
                br=int(raw.get("br", raw.get("bet_raise", 0)) or 0),
                cc=int(raw.get("cc", raw.get("check_call", 0)) or 0),
                fold=int(raw.get("fold", raw.get("fo", 0)) or 0),
            )
        if isinstance(raw, (list, tuple)) and len(raw) >= 3:
            return cls(br=int(raw[0] or 0), cc=int(raw[1] or 0), fold=int(raw[2] or 0))
        return cls()

    def add(self, action_type: str) -> None:
        if action_type == _ACTION_FOLD:
            self.fold += 1
        elif action_type in {_ACTION_CALL, _ACTION_CHECK}:
            self.cc += 1
        elif action_type in {_ACTION_ALL_IN, _ACTION_BET, _ACTION_RAISE}:
            self.br += 1

    def to_json(self) -> dict[str, int]:
        return {"br": int(self.br), "cc": int(self.cc), "fold": int(self.fold)}


@dataclass
class G5PlayerStats:
    name: str = ""
    display_name: str = ""
    vpip_positive: int = 0
    vpip_total: int = 0
    preflop: list[G5ActionStats] = field(default_factory=list)
    postflop: list[G5ActionStats] = field(default_factory=list)

    @classmethod
    def empty(cls, name: str, *, table_type: str, display_name: str = "") -> "G5PlayerStats":
        return cls(
            name=name,
            display_name=display_name,
            preflop=[G5ActionStats() for _ in range(preflop_count(table_type))],
            postflop=[G5ActionStats() for _ in range(postflop_count(table_type))],
        )

    @classmethod
    def from_raw(cls, name: str, raw: dict[str, Any], *, table_type: str) -> "G5PlayerStats":
        stats = cls.empty(name, table_type=table_type, display_name=str(raw.get("display_name") or ""))
        stats.vpip_positive = int(raw.get("vpip_positive", 0) or 0)
        stats.vpip_total = int(raw.get("vpip_total", 0) or 0)
        for idx, item in enumerate(raw.get("preflop") or []):
            if idx < len(stats.preflop):
                stats.preflop[idx] = G5ActionStats.from_raw(item)
        for idx, item in enumerate(raw.get("postflop") or []):
            if idx < len(stats.postflop):
                stats.postflop[idx] = G5ActionStats.from_raw(item)
        return stats

    def to_json(self) -> dict[str, Any]:
        return {
            "display_name": self.display_name,
            "vpip_positive": int(self.vpip_positive),
            "vpip_total": int(self.vpip_total),
            "preflop": [item.to_json() for item in self.preflop],
            "postflop": [item.to_json() for item in self.postflop],
        }

    def seed_vpip_if_stronger(self, positive: int, total: int) -> bool:
        if total <= self.vpip_total:
            return False
        self.vpip_positive = max(0, min(int(positive), int(total)))
        self.vpip_total = int(total)
        return True

    def to_seed_payload(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "display_name": self.display_name,
            "vpip_positive": int(self.vpip_positive),
            "vpip_total": int(self.vpip_total),
            "preflop": [item.to_json() for item in self.preflop],
            "postflop": [item.to_json() for item in self.postflop],
        }


class G5ActionModel:
    def __init__(self, *, table_type: str = TABLE_SIX_MAX, players: dict[str, G5PlayerStats] | None = None):
        self.table_type = table_type if table_type in {TABLE_SIX_MAX, TABLE_HEADS_UP} else TABLE_SIX_MAX
        self.players: dict[str, G5PlayerStats] = players or {}
        self.updated_at = 0.0

    @classmethod
    def load(cls, path: str | Path | None, *, table_type: str = TABLE_SIX_MAX) -> "G5ActionModel":
        if not path:
            return cls(table_type=table_type)
        file_path = Path(path)
        try:
            raw = json.loads(file_path.read_text(encoding="utf-8"))
        except (FileNotFoundError, OSError, json.JSONDecodeError):
            return cls(table_type=table_type)
        stored_table = str(raw.get("table_type") or table_type)
        model = cls(table_type=stored_table)
        players = raw.get("players") if isinstance(raw.get("players"), dict) else {}
        for name, item in players.items():
            if isinstance(item, dict):
                model.players[str(name)] = G5PlayerStats.from_raw(
                    str(name), item, table_type=model.table_type,
                )
        model.updated_at = float(raw.get("updated_at", 0.0) or 0.0)
        return model

    def save(self, path: str | Path | None) -> None:
        if not path:
            return
        self.updated_at = time.time()
        file_path = Path(path)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": 1,
            "table_type": self.table_type,
            "updated_at": self.updated_at,
            "players": {
                name: stats.to_json()
                for name, stats in sorted(self.players.items())
            },
        }
        tmp = file_path.with_suffix(file_path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        tmp.replace(file_path)

    def get_or_create(self, name: str, *, display_name: str = "") -> G5PlayerStats:
        stats = self.players.get(name)
        if stats is None:
            stats = G5PlayerStats.empty(name, table_type=self.table_type, display_name=display_name)
            self.players[name] = stats
        elif display_name and not stats.display_name:
            stats.display_name = display_name
        return stats

    def seed_from_opponent_model(self, opponent_model: "OpponentModel") -> int:
        """Import only fields whose semantics match g5 exactly.

        At the moment this is deliberately limited to VPIP:
        PokerFate's ``hands_seen/vpip_count`` and g5's VPIP are both
        "voluntarily put money in pot preflop" over hands.  PFR/AF/3bet/cbet
        are not injected because g5 derives them from context-specific
        ActionStats, and the aggregate server fields are not equivalent.
        """
        stats_map = opponent_model._stats
        name_map = opponent_model._id_to_name
        changed = 0
        for pid, stats in stats_map.items():
            total = int(stats.hands_seen or 0)
            positive = int(stats.vpip_count or 0)
            if total <= 0:
                continue
            name = stable_player_name(int(pid))
            display = str(name_map.get(int(pid), ""))
            if self.get_or_create(name, display_name=display).seed_vpip_if_stronger(positive, total):
                changed += 1
        return changed

    def seed_payload_for(self, player_names: Iterable[str], *, table_type: str) -> list[dict[str, Any]]:
        if table_type != self.table_type:
            return []
        payload: list[dict[str, Any]] = []
        for name in player_names:
            stats = self.players.get(str(name))
            if stats is not None:
                payload.append(stats.to_seed_payload())
        return payload

    def record_hand(
        self,
        *,
        players: Sequence[dict[str, Any]],
        dealer_id: int,
        action_history: Sequence[tuple[Any, Action, str]],
        big_blind: float,
        small_blind: float,
    ) -> bool:
        if not players or not action_history:
            return False
        hand_order = _g5_hand_order(players, dealer_id)
        if len(hand_order) < 2:
            return False
        actions = _normalize_actions_for_g5(
            action_history,
            hand_order=hand_order,
            big_blind=big_blind,
            small_blind=small_blind,
        )
        changed = False
        for player in hand_order:
            stats = self.get_or_create(player["name"], display_name=player.get("display_name", ""))
            _increment_player_stats(stats, hand_order, actions, table_type=self.table_type)
            changed = True
        return changed


def stable_player_name(player_id: int) -> str:
    pid = int(player_id)
    if pid >= 0:
        return f"uid:{pid}"
    return f"seat:{abs(pid) - 1}"


def table_type_for_player_count(num_players: int) -> str:
    return TABLE_HEADS_UP if int(num_players) == 2 else TABLE_SIX_MAX


def preflop_count(table_type: str) -> int:
    return 10 if table_type == TABLE_HEADS_UP else 54


def postflop_count(table_type: str) -> int:
    return 45 if table_type == TABLE_HEADS_UP else 216


def _g5_hand_order(players: Sequence[dict[str, Any]], dealer_id: int) -> list[dict[str, Any]]:
    by_index = list(players)
    if len(by_index) < 2:
        return []
    button_index = 0
    for idx, player in enumerate(by_index):
        if int(player.get("player_id", -1)) == int(dealer_id):
            button_index = idx
            break
    if len(by_index) == 2:
        indices = [button_index, (button_index + 1) % len(by_index)]
    else:
        indices = [(button_index + i) % len(by_index) for i in range(1, len(by_index) + 1)]
    return [
        {
            "player_id": int(by_index[idx].get("player_id", 0)),
            "name": stable_player_name(int(by_index[idx].get("player_id", 0))),
            "display_name": str(by_index[idx].get("name", "")),
            "stack": float(by_index[idx].get("stack", 0.0) or 0.0),
        }
        for idx in indices
    ]


def _normalize_actions_for_g5(
    action_history: Sequence[tuple[Any, Action, str]],
    *,
    hand_order: Sequence[dict[str, Any]],
    big_blind: float,
    small_blind: float,
) -> list[dict[str, Any]]:
    names_by_pid = {int(p["player_id"]): str(p["name"]) for p in hand_order}
    stacks = {str(p["name"]): float(p.get("stack", 0.0) or 0.0) for p in hand_order}
    street_contrib = {name: 0.0 for name in stacks}
    if len(hand_order) >= 2:
        sb = str(hand_order[0]["name"])
        bb = str(hand_order[1]["name"])
        street_contrib[sb] += float(small_blind or 0.0)
        street_contrib[bb] += float(big_blind or 0.0)
        stacks[sb] = max(0.0, stacks[sb] - float(small_blind or 0.0))
        stacks[bb] = max(0.0, stacks[bb] - float(big_blind or 0.0))

    current_street = "preflop"
    out: list[dict[str, Any]] = []
    for pid_raw, action, street_raw in action_history:
        pid = int(pid_raw)
        name = names_by_pid.get(pid)
        if name is None:
            continue
        street = str(street_raw or "preflop").lower()
        if street != current_street:
            current_street = street
            street_contrib = {player_name: 0.0 for player_name in stacks}

        action_type = _action_type_for_history(action)
        added = _chips_added(action, action_type=action_type, current_contrib=street_contrib.get(name, 0.0))
        is_all_in = added > 0 and added >= stacks.get(name, 0.0) - 1e-9
        if action_type in {_ACTION_CALL, _ACTION_RAISE, _ACTION_BET} and is_all_in:
            action_type = _ACTION_ALL_IN

        if added > 0:
            stacks[name] = max(0.0, stacks.get(name, 0.0) - added)
            street_contrib[name] = street_contrib.get(name, 0.0) + added

        out.append({"player_name": name, "street": street, "type": action_type})
    return out


def _action_type_for_history(action: Action) -> str:
    if action.action_type == ActionType.FOLD:
        return _ACTION_FOLD
    if action.action_type == ActionType.CHECK:
        return _ACTION_CHECK
    if action.action_type == ActionType.CALL:
        return _ACTION_CALL
    if action.action_type == ActionType.RAISE:
        return _ACTION_RAISE
    return _ACTION_FOLD


def _chips_added(action: Action, *, action_type: str, current_contrib: float) -> float:
    amount = float(action.amount or 0.0)
    if action_type in {_ACTION_FOLD, _ACTION_CHECK}:
        return 0.0
    if action_type == _ACTION_CALL:
        return max(0.0, amount)
    return max(0.0, amount - float(current_contrib or 0.0))


def _increment_player_stats(
    stats: G5PlayerStats,
    hand_order: Sequence[dict[str, Any]],
    actions: Sequence[dict[str, Any]],
    *,
    table_type: str,
) -> None:
    player_names = [str(p["name"]) for p in hand_order]
    player_name = stats.name
    if player_name not in player_names:
        return

    all_in_list: list[str] = []
    active_player_list = list(player_names)
    position = _player_position(active_player_list, player_name)
    last_player_action = _ACTION_FOLD
    player_put_money_in_pot = False
    player_folded_or_all_in = False

    num_raises = 0
    num_callers = 0
    for action in (a for a in actions if a.get("street") == "preflop" and _is_valid_action(str(a.get("type")))):
        if player_folded_or_all_in or len(active_player_list) <= 1:
            break
        action_type = str(action.get("type"))
        actor = str(action.get("player_name"))
        if actor == player_name:
            num_players = len(active_player_list) + len(all_in_list)
            idx = _preflop_index(
                table_type,
                position,
                num_callers,
                num_raises,
                num_players,
                last_player_action,
                _in_position(active_player_list, actor, num_players),
            )
            if 0 <= idx < len(stats.preflop):
                stats.preflop[idx].add(action_type)
            if action_type in {_ACTION_FOLD, _ACTION_ALL_IN}:
                player_folded_or_all_in = True
            if _is_raise_action(action_type) or action_type == _ACTION_CALL:
                player_put_money_in_pot = True
            last_player_action = action_type
        else:
            _remove_folded_or_all_in(actor, action_type, active_player_list, all_in_list)

        if _is_raise_action(action_type):
            num_raises += 1
            num_callers = 0
        elif action_type == _ACTION_CALL:
            num_callers += 1

    stats.vpip_total += 1
    if player_put_money_in_pot:
        stats.vpip_positive += 1

    for street in ("flop", "turn", "river"):
        if player_folded_or_all_in or len(active_player_list) <= 1:
            break
        round_num = 0
        num_bets = 0
        for action in (a for a in actions if a.get("street") == street and _is_valid_action(str(a.get("type")))):
            action_type = str(action.get("type"))
            actor = str(action.get("player_name"))
            if actor == player_name:
                num_players = len(active_player_list) + len(all_in_list)
                idx = _postflop_index(
                    table_type,
                    street,
                    round_num,
                    last_player_action,
                    num_bets,
                    _in_position(active_player_list, actor, num_players),
                    num_players,
                )
                if 0 <= idx < len(stats.postflop):
                    stats.postflop[idx].add(action_type)
                if action_type in {_ACTION_FOLD, _ACTION_ALL_IN}:
                    player_folded_or_all_in = True
                    break
                last_player_action = action_type
                round_num += 1
            else:
                _remove_folded_or_all_in(actor, action_type, active_player_list, all_in_list)

            if _is_raise_action(action_type):
                num_bets += 1


def _remove_folded_or_all_in(actor: str, action_type: str, active: list[str], all_in: list[str]) -> None:
    if action_type == _ACTION_FOLD:
        if actor in active:
            active.remove(actor)
    elif action_type == _ACTION_ALL_IN:
        if actor in active:
            active.remove(actor)
        if actor not in all_in:
            all_in.append(actor)


def _player_position(player_list: Sequence[str], player_name: str) -> str:
    idx = list(player_list).index(player_name)
    if idx == 0:
        return "SmallBlind"
    if idx == 1:
        return "BigBlind"
    if idx == len(player_list) - 1:
        return "Button"
    if idx == len(player_list) - 2:
        return "CutOff"
    if idx == len(player_list) - 3:
        return "HJ"
    if idx == len(player_list) - 4:
        return "UTG"
    return "Button"


def _in_position(player_list: Sequence[str], player_name: str, num_players: int) -> bool:
    if not player_list:
        return False
    if num_players == 2:
        return player_list[0] == player_name
    return player_list[-1] == player_name


def _is_raise_action(action_type: str) -> bool:
    return action_type in {_ACTION_RAISE, _ACTION_BET, _ACTION_ALL_IN}


def _is_valid_action(action_type: str) -> bool:
    return action_type in {_ACTION_RAISE, _ACTION_BET, _ACTION_ALL_IN, _ACTION_CALL, _ACTION_CHECK, _ACTION_FOLD}


def _preflop_index(
    table_type: str,
    position: str,
    num_callers: int,
    num_raises: int,
    num_active_players: int,
    previous_action: str,
    in_position_on_flop: bool,
) -> int:
    if table_type == TABLE_HEADS_UP:
        if position == "SmallBlind":
            return min(num_raises, 4)
        if position == "BigBlind":
            return 5 + min(num_raises, 4)
        raise ValueError(f"wrong HU position: {position}")

    if previous_action == _ACTION_FOLD:
        a0 = _POSITIONS[position]
        if num_raises == 0:
            a1 = 0 if num_callers == 0 else 1
        elif num_raises == 1:
            a1 = 2 if num_callers == 0 else 3
        else:
            a1 = 4
        return (5 * a0) + a1

    a0 = 0 if previous_action in {_ACTION_CHECK, _ACTION_CALL} else 1
    a1 = 0 if in_position_on_flop else 1
    a2 = 0 if num_active_players == 2 else 1
    if num_raises == 1:
        a3 = 0 if num_callers == 0 else 1
    else:
        a3 = 2
    return 30 + (12 * a0) + (6 * a1) + (3 * a2) + a3


def _postflop_index(
    table_type: str,
    street: str,
    round_num: int,
    previous_action: str,
    num_bets: int,
    in_position: bool,
    num_players: int,
) -> int:
    prev_mod = 0 if previous_action in {_ACTION_BET, _ACTION_RAISE, _ACTION_ALL_IN} else (
        1 if previous_action == _ACTION_CALL else 2
    )
    if table_type == TABLE_HEADS_UP:
        index = 15 if street == "turn" else 30 if street == "river" else 0
        if in_position:
            if num_bets < 2:
                index += prev_mod if num_bets == 0 else 3 + prev_mod
            else:
                index += 6 if num_bets == 2 else 7
        else:
            index += 8
            index += prev_mod if num_bets == 0 else min(num_bets, 4) + 2
        return index

    a0 = _STREETS.get(street, 0)
    a1 = 0 if round_num == 0 else 1
    a3 = 0 if num_bets <= 0 else 1 if num_bets == 1 else 2
    a4 = 1 if in_position else 0
    a5 = 0 if num_players <= 2 else 1
    return a5 + (2 * a4) + (4 * a3) + (12 * prev_mod) + (36 * a1) + (72 * a0)
