"""Opponent modeling: track statistics and detect exploitable patterns.

Persistence
-----------
OpponentModel 支持将对手数据持久化到 JSON 文件。
遇到熟悉对手时（相同 player_id 或相同 name），可以直接加载历史数据，
继续利用已积累的统计信息进行可剥削调整。

用法：
    model = OpponentModel.load("opponents.json")  # 从文件加载
    ...（对战过程中 model 自动更新）
    model.save("opponents.json")                  # 保存到文件
"""

from __future__ import annotations
import json
import os
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional


@dataclass
class OpponentStats:
    # Preflop
    hands_seen: int = 0
    vpip_count: int = 0          # voluntarily put money in pot
    pfr_count: int = 0           # preflop raise
    three_bet_count: int = 0
    three_bet_opportunities: int = 0
    fold_to_3bet_count: int = 0
    fold_to_3bet_opps: int = 0

    # Postflop
    cbet_count: int = 0
    cbet_opportunities: int = 0
    fold_to_cbet_count: int = 0
    fold_to_cbet_opps: int = 0

    # Aggression
    bet_count: int = 0
    raise_count: int = 0
    call_count: int = 0
    check_count: int = 0
    fold_count: int = 0

    # River
    river_bet_count: int = 0
    river_fold_count: int = 0
    river_call_count: int = 0
    river_action_count: int = 0

    @property
    def vpip(self) -> float:
        return self.vpip_count / max(self.hands_seen, 1)

    @property
    def pfr(self) -> float:
        return self.pfr_count / max(self.hands_seen, 1)

    @property
    def three_bet_pct(self) -> float:
        return self.three_bet_count / max(self.three_bet_opportunities, 1)

    @property
    def fold_to_3bet(self) -> float:
        return self.fold_to_3bet_count / max(self.fold_to_3bet_opps, 1)

    @property
    def cbet_pct(self) -> float:
        return self.cbet_count / max(self.cbet_opportunities, 1)

    @property
    def fold_to_cbet(self) -> float:
        return self.fold_to_cbet_count / max(self.fold_to_cbet_opps, 1)

    @property
    def aggression_factor(self) -> float:
        passive = max(self.call_count + self.check_count, 1)
        return (self.bet_count + self.raise_count) / passive

    @property
    def river_fold_rate(self) -> float:
        return self.river_fold_count / max(self.river_action_count, 1)

    def player_type(self) -> str:
        """Classify opponent into a rough player type."""
        if self.hands_seen < 20:
            return 'unknown'
        if self.vpip < 0.18 and self.pfr < 0.14:
            return 'nit'
        if self.vpip > 0.40 and self.aggression_factor < 1.5:
            return 'calling_station'
        if self.vpip > 0.35 and self.aggression_factor > 2.5:
            return 'maniac'
        if 0.22 <= self.vpip <= 0.32 and 0.16 <= self.pfr <= 0.26:
            return 'reg'
        if self.vpip > 0.30 and self.pfr < 0.16:
            return 'fish'
        return 'unknown'

    def __repr__(self) -> str:
        return (
            f"OpponentStats(type={self.player_type()}, "
            f"VPIP={self.vpip:.0%}, PFR={self.pfr:.0%}, "
            f"AF={self.aggression_factor:.1f}, "
            f"fold_cbet={self.fold_to_cbet:.0%}, "
            f"hands={self.hands_seen})"
        )


class OpponentModel:
    """Track and model opponent behavior, with optional persistence.

    Keyed by player_id (int). Optionally also indexed by name for
    cross-session lookup when player_ids change.
    """

    def __init__(self):
        self._stats: Dict[int, OpponentStats] = {}
        self._id_to_name: Dict[int, str] = {}    # player_id -> name
        self._name_to_id: Dict[str, int] = {}    # name -> canonical player_id
        # Archive: stats keyed by name for players who vacated a seat.
        # Allows stats to survive seat changes without leaking to new occupants.
        self._name_archive: Dict[str, OpponentStats] = {}
        # Showdown calibrator data loaded from file (passed back to caller).
        self._showdown_data: dict = {}

    def register_name(self, player_id: int, name: str) -> None:
        """Associate a player_id with a display name.

        Handles three scenarios correctly:

        1. Same player, same ID (re-registration): no-op, stable.

        2. Same player, new ID (e.g. changed seat between sessions):
           stats are migrated from old active ID to new ID.
           Also restores from name_archive if they previously vacated a seat.

        3. Different player, same ID (seat reuse within a session):
           old player's stats are archived under their name and cleared
           from this ID so the new player starts with a clean slate.
           Old player's data is recoverable if they rejoin later.
        """
        existing_name = self._id_to_name.get(player_id)
        if existing_name is not None and existing_name != name:
            # Scenario 3: different player now at this seat/ID.
            # Archive old player's stats by name (not lost, just detached).
            if self._name_to_id.get(existing_name) == player_id:
                del self._name_to_id[existing_name]
            if player_id in self._stats:
                self._name_archive[existing_name] = self._stats.pop(player_id)

        # Restore from archive if this player was previously seen (unregistered).
        if name in self._name_archive and player_id not in self._stats:
            self._stats[player_id] = self._name_archive.pop(name)

        # Migrate from a different active ID (same player, seat change).
        self._id_to_name[player_id] = name
        if name in self._name_to_id:
            old_id = self._name_to_id[name]
            if old_id != player_id and old_id in self._stats:
                self._stats[player_id] = self._stats.pop(old_id)
        self._name_to_id[name] = player_id

    def unregister_seat(self, player_id: int) -> None:
        """Dissociate a player_id / seat from its current occupant.

        Call this when a player leaves their seat (StandUpBRC / LeaveRoom)
        so the next player to sit here does not inherit their stats.

        Stats are moved to the name_archive — if the player rejoins at any
        seat/ID later, register_name() will restore their history.
        """
        name = self._id_to_name.pop(player_id, None)
        if name is None:
            return
        if self._name_to_id.get(name) == player_id:
            del self._name_to_id[name]
        # Move stats to name-keyed archive so they survive ID recycling.
        if player_id in self._stats:
            self._name_archive[name] = self._stats.pop(player_id)

    def get(self, player_id: int) -> OpponentStats:
        if player_id not in self._stats:
            self._stats[player_id] = OpponentStats()
        return self._stats[player_id]

    def record_hand_start(self, player_id: int):
        self.get(player_id).hands_seen += 1

    def record_vpip(self, player_id: int):
        self.get(player_id).vpip_count += 1

    def record_pfr(self, player_id: int):
        self.get(player_id).pfr_count += 1

    def record_3bet_opportunity(self, player_id: int, did_3bet: bool):
        s = self.get(player_id)
        s.three_bet_opportunities += 1
        if did_3bet:
            s.three_bet_count += 1

    def record_fold_to_3bet(self, player_id: int, folded: bool):
        s = self.get(player_id)
        s.fold_to_3bet_opps += 1
        if folded:
            s.fold_to_3bet_count += 1

    def record_cbet_opportunity(self, player_id: int, did_cbet: bool):
        s = self.get(player_id)
        s.cbet_opportunities += 1
        if did_cbet:
            s.cbet_count += 1

    def record_fold_to_cbet(self, player_id: int, folded: bool):
        s = self.get(player_id)
        s.fold_to_cbet_opps += 1
        if folded:
            s.fold_to_cbet_count += 1

    def record_action(self, player_id: int, action_type: str, street: str = ''):
        s = self.get(player_id)
        if action_type == 'fold':
            s.fold_count += 1
        elif action_type == 'check':
            s.check_count += 1
        elif action_type == 'call':
            s.call_count += 1
        elif action_type == 'raise':
            s.bet_count += 1

        if street == 'river':
            s.river_action_count += 1
            if action_type == 'fold':
                s.river_fold_count += 1
            elif action_type == 'call':
                s.river_call_count += 1
            elif action_type == 'raise':
                s.river_bet_count += 1

    def fold_to_cbet_rate(self, player_id: int) -> float:
        s = self.get(player_id)
        if s.fold_to_cbet_opps < 5:
            return 0.45  # Default assumption
        return s.fold_to_cbet

    def river_fold_rate(self, player_id: int) -> float:
        s = self.get(player_id)
        if s.river_action_count < 5:
            return 0.40
        return s.river_fold_rate

    def preferred_exploit_target(self, player_ids: List[int]) -> int:
        """Pick one opponent when history has no RAISE (limp / check-down).

        Prefer player types we can exploit (calling stations, fish), then more
        hands on file (better reads), then stable tie-break by ``player_id``.
        """
        if not player_ids:
            return -1
        type_rank = {
            "calling_station": 40,
            "fish": 30,
            "maniac": 25,
            "unknown": 10,
            "reg": 8,
            "nit": 0,
        }

        def score(pid: int) -> tuple:
            s = self.get(pid)
            tr = type_rank.get(s.player_type(), 0)
            return (tr, s.hands_seen, -pid)

        return max(player_ids, key=score)

    def exploit_adjustments(self, player_id: int) -> dict:
        """Return suggested exploitative adjustments vs this opponent."""
        s = self.get(player_id)
        adj = {}

        if s.hands_seen < 20:
            return adj

        ptype = s.player_type()

        if ptype == 'nit':
            adj['cbet_freq'] = 'high'
            adj['bluff_freq'] = 'high'
            adj['value_sizing'] = 'normal'

        elif ptype == 'calling_station':
            adj['bluff_freq'] = 'none'
            adj['value_sizing'] = 'large'
            adj['cbet_freq'] = 'value_only'

        elif ptype == 'maniac':
            adj['bluff_freq'] = 'low'
            adj['check_raise_freq'] = 'high'
            adj['trap_freq'] = 'high'

        elif ptype == 'fish':
            adj['bluff_freq'] = 'low'
            adj['value_sizing'] = 'large'

        # Fine-grained adjustments
        if s.fold_to_cbet > 0.60 and s.fold_to_cbet_opps >= 5:
            adj['cbet_freq'] = 'high'

        if s.fold_to_3bet > 0.65 and s.fold_to_3bet_opps >= 5:
            adj['three_bet_freq'] = 'high'

        if s.river_fold_rate > 0.55 and s.river_action_count >= 5:
            adj['river_bluff_freq'] = 'high'

        return adj

    # ------------------------------------------------------------------
    # Persistence: save / load
    # ------------------------------------------------------------------

    def save(self, filepath: str, showdown_data: Optional[dict] = None) -> None:
        """Persist all opponent data to a JSON file.

        The file is human-readable and can be inspected/edited manually.
        Call this after each session (or periodically) to preserve data.

        Parameters
        ----------
        showdown_data : dict, optional
            Showdown calibrator data to embed in the same file under the
            ``"showdown"`` key. Pass ``calibrator.to_dict()`` here so both
            datasets stay in one file and share the same encryption path.
        """
        data = {
            "stats": {
                str(pid): asdict(stats)
                for pid, stats in self._stats.items()
            },
            "id_to_name": {str(k): v for k, v in self._id_to_name.items()},
            "name_to_id": self._name_to_id,
            "name_archive": {
                name: asdict(stats)
                for name, stats in self._name_archive.items()
            },
        }
        if showdown_data is not None:
            data["showdown"] = showdown_data
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    @classmethod
    def load(cls, filepath: str) -> "OpponentModel":
        """Load opponent data from a JSON file.

        If the file does not exist, returns a fresh empty model
        (safe to call unconditionally at startup).
        """
        model = cls()
        if not os.path.exists(filepath):
            return model
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read().strip()
        if not content:
            return model
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            return model
        for pid_str, stats_dict in data.get("stats", {}).items():
            model._stats[int(pid_str)] = OpponentStats(**stats_dict)
        model._id_to_name = {int(k): v for k, v in data.get("id_to_name", {}).items()}
        model._name_to_id = data.get("name_to_id", {})
        for name, stats_dict in data.get("name_archive", {}).items():
            model._name_archive[name] = OpponentStats(**stats_dict)
        model._showdown_data = data.get("showdown", {})
        return model

    def merge(self, other: "OpponentModel") -> None:
        """Merge another model's stats into this one (additive)."""
        for pid, stats in other._stats.items():
            if pid in self._stats:
                s = self._stats[pid]
                o = stats
                s.hands_seen += o.hands_seen
                s.vpip_count += o.vpip_count
                s.pfr_count += o.pfr_count
                s.three_bet_count += o.three_bet_count
                s.three_bet_opportunities += o.three_bet_opportunities
                s.fold_to_3bet_count += o.fold_to_3bet_count
                s.fold_to_3bet_opps += o.fold_to_3bet_opps
                s.cbet_count += o.cbet_count
                s.cbet_opportunities += o.cbet_opportunities
                s.fold_to_cbet_count += o.fold_to_cbet_count
                s.fold_to_cbet_opps += o.fold_to_cbet_opps
                s.bet_count += o.bet_count
                s.raise_count += o.raise_count
                s.call_count += o.call_count
                s.check_count += o.check_count
                s.fold_count += o.fold_count
                s.river_bet_count += o.river_bet_count
                s.river_fold_count += o.river_fold_count
                s.river_call_count += o.river_call_count
                s.river_action_count += o.river_action_count
            else:
                self._stats[pid] = stats
        self._id_to_name.update(other._id_to_name)
        self._name_to_id.update(other._name_to_id)

    def summary(self) -> str:
        """Return a human-readable summary of all known opponents."""
        if not self._stats:
            return "No opponent data recorded."
        lines = ["Opponent Database:"]
        for pid, stats in self._stats.items():
            name = self._id_to_name.get(pid, f"Player#{pid}")
            lines.append(f"  [{name}] {stats}")
        return "\n".join(lines)
