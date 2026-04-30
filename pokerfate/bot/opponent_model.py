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

player_type 标签（hands_seen >= MIN_HANDS_FOR_CLASSIFICATION；按下列顺序先匹配先胜出）
----------------------------------------------------------------
nit — VPIP < 18% 且 PFR < 14%。

reg — 22% ≤ VPIP ≤ 32%、16% ≤ PFR ≤ 26%、且 (VPIP−PFR) ≤ 12%。

maniac — VPIP > 33%，且 (AF > 2.5) 或（flop 下注+被动 ≥ 12 且 flop AFq ≥ 0.42 且 AF > 1.6）。

whale — (VPIP > 55% 且 AF < 1.2) 或（48% ≤ VPIP ≤ 55%、AF < 1.25、flop_seen ≥ 15、WTSD ≥ 31%）。

fish — VPIP > 30%、PFR < 17%、且 (VPIP−PFR) ≥ 6%。

calling_station — VPIP > 40% 且 AF < 1.5，且满足以下任一：flop_seen ≥ 15 且 WTSD ≥ 26%；或 PFR ≥ 17%；或 (VPIP−PFR) ≤ 14%。

unknown — 以上皆不满足。
"""

from __future__ import annotations
import json
import logging
import os
from dataclasses import dataclass, asdict, fields
from typing import Dict, List, Optional

from pokerfate.core.config import MIN_HANDS_FOR_CLASSIFICATION

log = logging.getLogger(__name__)


def _clip(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


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
    fold_to_cbet_count: int = 0
    fold_to_cbet_opps: int = 0

    # Aggression
    bet_count: int = 0
    raise_count: int = 0
    call_count: int = 0
    check_count: int = 0
    fold_count: int = 0

    # 服务端 30 天历史先验（play_times 级别样本，远大于本地 session）。
    # 对 AF / WTSD 两项：server 有值时**永久覆盖**本地（见 property）。
    # 3bet / cbet 服务端数据已作废：
    #   - three_bet_rate：per-hand 语义，与本地 per-opportunity 不同，不再接入
    #   - c_bete_rate：cbet_pct 字段在决策层没有读取路径，彻底删除
    server_af_prior: float = 0.0      # AF ratio (converted from active_rate/10000)
    server_wtsd_prior: float = 0.0    # show_hand_rate/10000（showdowns per VPIP hand）

    # River
    river_bet_count: int = 0
    river_fold_count: int = 0
    river_call_count: int = 0
    river_check_count: int = 0   # checks on river (not facing a bet)
    river_action_count: int = 0
    river_facing_bet_fold_count: int = 0
    river_facing_bet_opps: int = 0

    # Street-level aggression (flop / turn; river already above)
    flop_bet_count: int = 0
    flop_passive_count: int = 0  # call + check on flop
    turn_bet_count: int = 0
    turn_passive_count: int = 0  # call + check on turn

    # Showdown tracking (WTSD / WMSD)
    flop_seen_count: int = 0     # times they saw the flop (not folded preflop)
    showdown_count: int = 0      # times they went to showdown
    showdown_win_count: int = 0  # times they won at showdown

    # Bluff win tracking：赢底池时实际牌型（含无摊牌用牌型上界估算）
    # 用于 bluff_win_rate = 弱牌赢（高牌/一对）/ 有下注行为时的总赢次
    bet_win_count: int = 0       # 本手有过下注/加注行为且最终赢得底池的次数
    bluff_win_count: int = 0     # 其中牌型为高牌(1)或一对(2)的次数（弱牌赢）

    @property
    def vpip(self) -> float:
        return self.vpip_count / max(self.hands_seen, 1)

    @property
    def pfr(self) -> float:
        return self.pfr_count / max(self.hands_seen, 1)

    @property
    def three_bet_pct(self) -> float:
        """Per-opportunity 3bet frequency (本地实测 only).

        服务端 three_bet_rate 是 per-hand 语义（3bet 次数 / 总手数），
        与本地 per-opportunity 语义不兼容，直接作废。
        """
        return self.three_bet_count / max(self.three_bet_opportunities, 1)

    @property
    def fold_to_3bet(self) -> float:
        return self.fold_to_3bet_count / max(self.fold_to_3bet_opps, 1)

    @property
    def fold_to_cbet(self) -> float:
        return self.fold_to_cbet_count / max(self.fold_to_cbet_opps, 1)

    @property
    def aggression_factor(self) -> float:
        """AF = (bets+raises) / passive。服务端数据在就永久用服务端。

        30 天服务端样本 ≫ 本地 session 实测。以前用 "session_actions<20" 切换
        存在严重问题：对手坐 5-7 手就跨过阈值，1000 手服务端数据被丢弃。
        现在规则简化为：server_af_prior > 0 → 永久服务端；否则本地 fallback。
        """
        if self.server_af_prior > 0:
            return self.server_af_prior
        passive = max(self.call_count + self.check_count, 1)
        return (self.bet_count + self.raise_count) / passive

    @property
    def river_fold_rate(self) -> float:
        return self.river_facing_bet_fold_count / max(self.river_facing_bet_opps, 1)

    @property
    def river_bet_frequency(self) -> float:
        """Active river bet frequency: bets / (bets + checks).
        Excludes facing-a-bet actions (fold/call) to measure voluntary aggression."""
        return self.river_bet_count / max(self.river_bet_count + self.river_check_count, 1)

    @property
    def flop_afq(self) -> float:
        """Flop aggression frequency: bets / (bets + passive actions)."""
        return self.flop_bet_count / max(self.flop_bet_count + self.flop_passive_count, 1)

    @property
    def turn_afq(self) -> float:
        """Turn aggression frequency."""
        return self.turn_bet_count / max(self.turn_bet_count + self.turn_passive_count, 1)

    @property
    def river_afq(self) -> float:
        """River aggression frequency (bets / all river actions)."""
        total = self.river_bet_count + self.river_call_count + self.river_check_count
        return self.river_bet_count / max(total, 1)

    @property
    def wtsd(self) -> float:
        """Went to showdown: fraction of flop-seen hands that reached showdown.

        服务端数据在就永久用服务端（同 aggression_factor 的逻辑）。
        服务端分母是 VPIP hands，本地分母是 flop_seen_count，差距 5-10% 可忽略。
        """
        if self.server_wtsd_prior > 0:
            return self.server_wtsd_prior
        return self.showdown_count / max(self.flop_seen_count, 1)

    @property
    def wmsd(self) -> float:
        """Won money at showdown: win rate among showdown hands."""
        return self.showdown_win_count / max(self.showdown_count, 1)

    @property
    def bluff_win_rate(self) -> float:
        """有下注行为时以弱牌（高牌/一对）赢底池的比例。
        高值 = 经常诈唬得手；低值 = 下注时通常有货。
        仅在 bet_win_count >= 5 时有统计意义。
        """
        return self.bluff_win_count / max(self.bet_win_count, 1)

    def pwi(self) -> float:
        """Player Weakness Index：连续型可剥削分（参考业界 PWI 公式）。

        分值越高 = 越好打；负分 = reg/nit 对你不利。
        只有 hands_seen >= MIN_HANDS_FOR_CLASSIFICATION 时才有意义，样本不足返回 0。

        公式来源：行业标准指标加权组合
          (VPIP% - 26) × 1.0    — 超过正常水平的松牌程度
          (VPIP% - PFR% - 10) × 0.8  — 跛进/被动倾向（差值越大越被动）
          max(0, 2.5 - AF) × 5.0     — 被动程度（AF 低 = 爱跟注 = 易剥削）
          max(0, WTSD% - 24) × 0.5   — 过度摊牌倾向

        典型分值参考（20手以上）：
          super whale (VPIP85%, AF0.8):  ~110
          calling_station (VPIP50%, AF1.2): ~65
          fish (VPIP45%, AF1.8):         ~45
          unknown:                         ~0
          reg (VPIP25%, AF2.5):          ~-5
          nit (VPIP15%, AF2.0):         ~-15
        """
        if self.hands_seen < MIN_HANDS_FOR_CLASSIFICATION:
            return 0.0
        v = self.vpip * 100
        p = self.pfr * 100
        af = self.aggression_factor
        w = self.wtsd * 100
        score = (
            (v - 26) * 1.0
            + (v - p - 10) * 0.8
            + max(0.0, 2.5 - af) * 5.0
            + max(0.0, w - 24) * 0.5
        )
        return score

    def player_type(self) -> str:
        """Classify opponent into a rough player type. 命中条件见本文件模块 docstring。"""
        if self.hands_seen < MIN_HANDS_FOR_CLASSIFICATION:
            return 'unknown'
        vpip = self.vpip
        pfr = self.pfr
        af = self.aggression_factor
        gap = vpip - pfr
        wtsd = self.wtsd
        flop_seen = self.flop_seen_count
        flop_n = self.flop_bet_count + self.flop_passive_count
        flop_afq = self.flop_afq

        # 1) nit
        if vpip < 0.18 and pfr < 0.14:
            return 'nit'
        # 2) reg — TAG：常客 VPIP/PFR 带 + VPIP−PFR 不过大（减少跛进型误标）
        if 0.22 <= vpip <= 0.32 and 0.16 <= pfr <= 0.26 and gap <= 0.12:
            return 'reg'
        # 3) maniac — 凶：AF 高；flop 样本够时用 AFq 补（AF 在少量 postflop 动作时易失真）
        if vpip > 0.33 and (
            af > 2.5
            or (flop_n >= 12 and flop_afq >= 0.42 and af > 1.6)
        ):
            return 'maniac'
        # 4) whale — 极松被动；55%+ 经典 whale；48–55% 需 flop/摊牌样本 + 高 WTSD 支撑
        if vpip > 0.55 and af < 1.2:
            return 'whale'
        if (
            0.48 <= vpip <= 0.55
            and af < 1.25
            and flop_seen >= 15
            and wtsd >= 0.31
        ):
            return 'whale'
        # 5) fish — 松、主动加注少、VPIP−PFR 偏大（跛进/跟注型）
        if vpip > 0.30 and pfr < 0.17 and gap >= 0.06:
            return 'fish'
        # 6) calling_station — 松、被动；或 WTSD 偏高印证爱跟到摊牌
        if vpip > 0.40 and af < 1.5:
            if flop_seen >= 15 and wtsd >= 0.26:
                return 'calling_station'
            if pfr >= 0.17 or gap <= 0.14:
                return 'calling_station'
        return 'unknown'

    def __repr__(self) -> str:
        return (
            f"OpponentStats(type={self.player_type()}, "
            f"VPIP={self.vpip:.0%}, PFR={self.pfr:.0%}, "
            f"AF={self.aggression_factor:.1f}, "
            f"fold_cbet={self.fold_to_cbet:.0%}, "
            f"hands={self.hands_seen})"
        )

    def to_villain_stats(self):
        """Project this OpponentStats into a v3 VillainStats.

        所有字段原样传过去（含样本量字段 fold_to_cbet_opps /
        river_action_count / bet_win_count / hands_seen），让 exploit.py 的
        _value_lean / _bluff_lean / _trap_lean 能真正通过所有路驱动。
        """
        # Import lazily to avoid circular import at module load.
        from pokerfate.strategy.v3.context import VillainStats
        return VillainStats(
            vpip=self.vpip,
            pfr=self.pfr,
            af=self.aggression_factor,
            fold_to_cbet=self.fold_to_cbet,
            fold_to_cbet_opps=self.fold_to_cbet_opps,
            fold_to_3bet=self.fold_to_3bet,
            wtsd=self.wtsd,
            wmsd=self.wmsd,
            bluff_win_rate=self.bluff_win_rate,
            bet_win_count=self.bet_win_count,
            flop_afq=self.flop_afq,
            turn_afq=self.turn_afq,
            river_afq=self.river_afq,
            river_fold_rate=self.river_fold_rate,
            river_bet_frequency=self.river_bet_frequency,
            river_action_count=self.river_facing_bet_opps,
            hands_seen=self.hands_seen,
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

    def record_fold_to_cbet(self, player_id: int, folded: bool):
        s = self.get(player_id)
        s.fold_to_cbet_opps += 1
        if folded:
            s.fold_to_cbet_count += 1

    def record_river_facing_bet(self, player_id: int, folded: bool):
        s = self.get(player_id)
        s.river_facing_bet_opps += 1
        if folded:
            s.river_facing_bet_fold_count += 1

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

        street_l = street.lower() if street else ''
        if street_l == 'flop':
            if action_type == 'raise':
                s.flop_bet_count += 1
            elif action_type in ('call', 'check'):
                s.flop_passive_count += 1
        elif street_l == 'turn':
            if action_type == 'raise':
                s.turn_bet_count += 1
            elif action_type in ('call', 'check'):
                s.turn_passive_count += 1
        elif street_l == 'river':
            s.river_action_count += 1
            if action_type == 'fold':
                s.river_fold_count += 1
            elif action_type == 'call':
                s.river_call_count += 1
            elif action_type == 'raise':
                s.river_bet_count += 1
            elif action_type == 'check':
                s.river_check_count += 1

    def record_flop_seen(self, player_id: int) -> None:
        """Call when a player sees the flop (not folded preflop). Used for WTSD denominator."""
        self.get(player_id).flop_seen_count += 1

    def record_showdown(self, player_id: int, won: bool) -> None:
        """Call when a player reaches showdown. Used for WTSD and WMSD."""
        s = self.get(player_id)
        s.showdown_count += 1
        if won:
            s.showdown_win_count += 1

    def record_win_with_hand_type(self, player_id: int, hand_type: int, had_aggression: bool) -> None:
        """记录赢底池时的牌型，用于统计 bluff_win_rate。

        Parameters
        ----------
        hand_type : int
            服务端牌型整数（1=高牌, 2=一对, ...）。
        had_aggression : bool
            本手该玩家是否有过下注/加注行为（无攻击性行为的赢不计入）。
        """
        if not had_aggression:
            return
        s = self.get(player_id)
        s.bet_win_count += 1
        if hand_type in (1, 2):   # 高牌或一对 = 弱牌赢
            s.bluff_win_count += 1

    def fold_to_cbet_rate(self, player_id: int) -> float:
        s = self.get(player_id)
        if s.fold_to_cbet_opps < 5:
            return 0.45  # Default assumption
        return s.fold_to_cbet

    def river_fold_rate(self, player_id: int) -> float:
        s = self.get(player_id)
        if s.river_facing_bet_opps < 5:
            return 0.40
        return s.river_fold_rate

    def preferred_exploit_target(self, player_ids: List[int]) -> int:
        """Pick the most exploitable opponent (highest PWI) when no aggressor exists.

        排序逻辑：
          主键 — PWI 分（连续分，越高越好打）；样本不足（<20手）时 PWI=0 但仍参与排序
          次键 — hands_seen（样本越多读牌越准）
          末键 — -player_id（稳定 tie-break）
        """
        if not player_ids:
            return -1

        def score(pid: int) -> tuple:
            s = self.get(pid)
            return (s.pwi(), s.hands_seen, -pid)

        return max(player_ids, key=score)

    def exploit_adjustments(self, player_id: int) -> dict:
        """Return suggested exploitative adjustments vs this opponent.

        **完全指标驱动**：不再按 player_type 标签做决策分支（whale/fish/
        calling_station/maniac/nit 只做 log 展示用途）。

        输出字段全部是连续 scale 或由单一指标阈值派生的 boolean 信号，
        下游（poker_bot / api）消费时只读连续数值，不读字符串枚举。

        输出字段：
          value_ag_scale      ∈ [0.30, 1.00]  价值下注频率乘子
          bluff_ag_scale      ∈ [0.08, 1.15]  诈唬下注频率乘子
          value_sizing_scale  ∈ [1.00, 1.35]  价值注码放大倍率
          aggression_scale    ∈ [0.35, 1.30]  PWI 驱动整体攻击性
          river_bluff_likely  bool            对手河牌偏向诈唬（提升跟注意愿）
          river_bet_rare      bool            对手河牌下注罕见（下注=强手）
          flop_float_favorable bool           对手翻牌激进但可浮牌剥削
          turn_bluff_then_fold bool           对手常 turn 诈唬 river 放弃

        连续化要点：
          1. sticky 对手（whale/station/fish）原来由 ptype 枚举触发
             bluff_freq='none'。现在由 fold_to_cbet/wtsd/river_fold_rate
             三路指标共同下压 bluff_ag_scale 至 0.08-0.15；同时 sticky
             越深 value_sizing_scale 越大（连续插值而非 0/1.30 二档）。
          2. maniac 的慢打（原 value_ag_scale=0.45 硬值）现在由 AF + bwr
             驱动：AF 2.5→0.75, AF 3.0→0.60, AF 3.5+bwr 0.40→0.45。
          3. nit 的多诈唬（原 'high'）由 fold_to_cbet 本身驱动 bluff_ag
             上升：fold_to_cbet 0.55→0.85, 0.65→1.10。
        """
        s = self.get(player_id)
        adj = {}

        if s.hands_seen < MIN_HANDS_FOR_CLASSIFICATION:
            return adj

        pwi = s.pwi()
        af = s.aggression_factor

        # ──────────────────────────────────────────────────────────────
        # 连续指数：作为下游连续 scale 的共享输入
        # ──────────────────────────────────────────────────────────────
        # sticky_score ∈ [0, 1]：对手"不弃牌"强度。三路独立指标各贡献 1/3，
        # 缺样本的路贡献 0（不惩罚），最终归一化。
        sticky_parts = []
        if s.fold_to_cbet_opps >= 5:
            sticky_parts.append(_clip((0.50 - s.fold_to_cbet) / 0.35, 0.0, 1.0))
        if s.flop_seen_count >= 15 or s.server_wtsd_prior > 0:
            sticky_parts.append(_clip((s.wtsd - 0.22) / 0.22, 0.0, 1.0))
        if s.river_facing_bet_opps >= 5:
            sticky_parts.append(_clip((0.45 - s.river_fold_rate) / 0.30, 0.0, 1.0))
        sticky_score = sum(sticky_parts) / len(sticky_parts) if sticky_parts else 0.0

        # fold_lean_score ∈ [0, 1]：对手"易弃牌"强度（与 sticky 对称）。
        fold_lean_parts = []
        if s.fold_to_cbet_opps >= 5:
            fold_lean_parts.append(_clip((s.fold_to_cbet - 0.45) / 0.25, 0.0, 1.0))
        if s.river_facing_bet_opps >= 5:
            fold_lean_parts.append(_clip((s.river_fold_rate - 0.45) / 0.25, 0.0, 1.0))
        if s.flop_seen_count >= 15 or s.server_wtsd_prior > 0:
            fold_lean_parts.append(_clip((0.25 - s.wtsd) / 0.15, 0.0, 1.0))
        fold_lean_score = sum(fold_lean_parts) / len(fold_lean_parts) if fold_lean_parts else 0.0

        # ──────────────────────────────────────────────────────────────
        # value_ag_scale：价值下注频率乘子
        # ──────────────────────────────────────────────────────────────
        #   sticky 对手跟注多 → value_ag 高（1.00）
        #   fold-lean 对手常弃 → value_ag 低（0.50，薄价值风险高）
        #   maniac（AF 高 + bwr 高）→ value_ag 进一步下压（慢打让他诈唬）
        # action_samples：对手出过的**主动行为**样本量。
        # 稀疏样本时（如 15 手里只 fold 过 preflop 从未进入 postflop 动作），
        # AF 分母几乎是 1、分子是 0 → AF=0，原代码会当成"极度被动"给高 value_ag。
        # 必须要求足够主动行为样本才启用 AF 兜底。
        action_samples = (s.call_count + s.check_count
                          + s.bet_count + s.raise_count)
        if s.fold_to_cbet_opps >= 5:
            base_val = _clip(1.0 - s.fold_to_cbet * 0.6, 0.50, 1.00)
        elif action_samples >= 10:
            af_norm = _clip((af - 1.0) / 2.0, 0.0, 1.0)
            base_val = _clip(0.85 - af_norm * 0.30, 0.50, 1.00)
        else:
            base_val = 0.85  # baseline，样本不足不推断激进度
        # sticky 加成（最高 +0.08）—— 非常粘的对手即使 fold_to_cbet 未必极低，
        # wtsd/river_fold_rate 证据也能拉高 value_ag（摊牌怪要多收价值）。
        base_val = _clip(base_val + sticky_score * 0.08, 0.50, 1.00)
        # maniac 慢打覆盖：AF+bwr 驱动下压（替代旧 ptype=='maniac'→0.45 硬值）
        maniac_pressure = 0.0
        if s.hands_seen >= 20:
            maniac_pressure += max(0.0, (af - 2.0) * 0.25)       # AF 2.5→0.125, 3.0→0.25
        if s.bet_win_count >= 5:
            maniac_pressure += max(0.0, (s.bluff_win_rate - 0.20) * 1.5)  # bwr 0.40→0.30
        maniac_pressure = min(1.0, maniac_pressure)
        if maniac_pressure > 0:
            # 插值到最低 0.40 —— maniac_pressure=1 时 value_ag=0.40（比原 0.45 略激进）
            base_val = min(base_val, 1.0 - maniac_pressure * 0.60)
            base_val = max(base_val, 0.40)
        adj['value_ag_scale'] = base_val

        # ──────────────────────────────────────────────────────────────
        # bluff_ag_scale：诈唬下注频率乘子
        # ──────────────────────────────────────────────────────────────
        #   fold_to_cbet 实测样本 ≥ 5 时主驱；否则用 AF 兜底；sticky 进一步下压，
        #   fold-lean 进一步上提。最低 0.08（原 'bluff_freq=none' 等价效果），
        #   最高 1.15（原 'bluff_freq=high' + fold_to_cbet 高的等价效果）。
        if s.fold_to_cbet_opps >= 5:
            # fold_to_cbet 0.20→0.40, 0.40→0.80, 0.60→1.10, 0.75→1.15(cap)
            base_bluff = _clip(s.fold_to_cbet / 0.50, 0.25, 1.15)
        elif action_samples >= 10:
            # af 高 = 激进 = 我方诈唬易被反加 → 低；af 低 = 被动 = 但爱跟 → 也低
            base_bluff = _clip(0.55 - (af - 1.5) * 0.20, 0.15, 1.10)
        else:
            base_bluff = 0.55  # baseline
        # sticky 下压（可至 0.08）：sticky_score=1 时从 base 减 0.40，但不低于 0.08。
        # 替代原 ptype=='whale/fish/station' → bluff_freq='none' 的语义。
        base_bluff = max(0.08, base_bluff - sticky_score * 0.40)
        # wtsd 极端高（>0.38）额外压制，等价原"禁止诈唬"
        if (s.flop_seen_count >= 15 or s.server_wtsd_prior > 0) and s.wtsd > 0.38:
            base_bluff = min(base_bluff, 0.12)
        if s.showdown_count >= 8 and s.wmsd < 0.45 and s.wtsd > 0.35:
            # 频繁摊牌但常输 → 只用强手摊 → 对他诈唬无意义
            base_bluff = min(base_bluff, 0.10)
        if s.bet_win_count >= 5 and s.bluff_win_rate > 0.40:
            # 他诈唬多但能赢 → 经常跟 → 我方诈唬回应效率低
            base_bluff = min(base_bluff, 0.12)
        # fold-lean 上提（等价原 ptype=='nit' → bluff_freq='high'）
        base_bluff = _clip(base_bluff + fold_lean_score * 0.20, 0.08, 1.15)
        adj['bluff_ag_scale'] = base_bluff

        # ──────────────────────────────────────────────────────────────
        # value_sizing_scale：价值注码放大倍率
        # ──────────────────────────────────────────────────────────────
        #   驱动：sticky（不弃牌+爱摊牌）→ 加大价值注码。
        #   上限从旧 1.30 提到 1.35（sticky_score=1 + WMSD 证据可加满）。
        fold_w = _clip((0.45 - s.fold_to_cbet) / 0.30, 0.0, 1.0) \
                 if s.fold_to_cbet_opps >= 5 else 0.5
        wtsd_w = _clip((s.wtsd - 0.20) / 0.20, 0.0, 1.0) \
                 if (s.flop_seen_count >= 15 or s.server_wtsd_prior > 0) else 0.5
        sizing = 1.0 + 0.30 * fold_w * wtsd_w
        # WTSD 极端高加满（原代码 hardcoded 1.30，现在保留但在新上限范围内）
        if (s.flop_seen_count >= 15 or s.server_wtsd_prior > 0) and s.wtsd > 0.38:
            sizing = max(sizing, 1.30)
        if s.showdown_count >= 8 and s.wmsd < 0.45 and s.wtsd > 0.35:
            sizing = max(sizing, 1.32)
        adj['value_sizing_scale'] = min(1.35, sizing)

        # ──────────────────────────────────────────────────────────────
        # aggression_scale：PWI 连续映射（原分档保留，驱动指标本来就连续）
        # ──────────────────────────────────────────────────────────────
        if pwi >= 60:
            adj['aggression_scale'] = 0.35
        elif pwi >= 40:
            adj['aggression_scale'] = 0.55
        elif pwi >= 20:
            adj['aggression_scale'] = 0.75
        elif pwi >= 0:
            adj['aggression_scale'] = 0.90
        elif pwi >= -10:
            adj['aggression_scale'] = 1.10
        else:
            adj['aggression_scale'] = 1.30

        # ──────────────────────────────────────────────────────────────
        # Boolean 派生信号（单一指标阈值 → 语义 flag，用于 log 与特定策略钩子）
        # 这些不是"玩家类型标签"，而是从连续指标派生的具体行为模式 flag。
        # ──────────────────────────────────────────────────────────────
        # river_bluff_likely 闸门（2026-04-23 升级）：被动对手的"弱牌赢底"或
        # "河牌高频下注"往往是误判牌力 / 误下注，不是真诈唬。用街位级 AFq 证据
        # 把"真的会在晚街打出下注序列"过滤出来。turn_afq/river_afq 是局部频率，
        # 不依赖 af ratio 归一化，server 先验/本地计算两条路径都成立。
        # 样本门槛同时提高（5→10 / 8→12）降低小样本假阳性。
        turn_samples_for_gate = s.turn_bet_count + s.turn_passive_count
        bluff_capable = (
            turn_samples_for_gate >= 10
            and s.turn_afq >= 0.45
            and s.river_afq >= 0.30
        )

        if s.bet_win_count >= 10 and bluff_capable:
            if s.bluff_win_rate > 0.40:
                adj['river_bluff_likely'] = True
            elif s.bluff_win_rate < 0.15:
                adj['river_bet_rare'] = True
        elif s.bet_win_count >= 10 and s.bluff_win_rate < 0.15:
            # river_bet_rare 反向不要求 bluff_capable——低 bluff_win_rate 本身是
            # "下注就是真"的可信信号，被动对手更适合这个反向 flag。
            adj['river_bet_rare'] = True

        river_bf_samples = s.river_bet_count + s.river_check_count
        if river_bf_samples >= 12 and bluff_capable:
            if s.river_bet_frequency > 0.55:
                adj['river_bluff_likely'] = True
            elif s.river_bet_frequency < 0.20:
                adj['river_bet_rare'] = True
        elif river_bf_samples >= 12 and s.river_bet_frequency < 0.20:
            adj['river_bet_rare'] = True

        flop_samples = s.flop_bet_count + s.flop_passive_count
        turn_samples = s.turn_bet_count + s.turn_passive_count
        river_afq_samples = s.river_bet_count + s.river_call_count + s.river_check_count

        if flop_samples >= 10 and s.flop_afq > 0.60:
            adj['flop_float_favorable'] = True

        if turn_samples >= 8 and river_afq_samples >= 8:
            if s.turn_afq > 0.50 and s.river_afq < 0.25:
                adj['turn_bluff_then_fold'] = True

        # 第三处 river_bluff_likely：提高 river_afq_samples 门槛 + 要求
        # bluff_capable（flop-afq-持平-river 的 barrel-through 模式只有在
        # 晚街真的打出高 AFq 时才算诈唬证据）。
        if flop_samples >= 10 and turn_samples >= 12 and river_afq_samples >= 12:
            if s.river_afq >= s.flop_afq * 0.90 and bluff_capable:
                adj['river_bluff_likely'] = True

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
            datasets stay in one local JSON file.
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

        Unknown fields in persisted JSON are silently ignored — this allows
        reading files written by older code versions that contained fields
        we've since removed (e.g. cbet_count / server_cbet_prior /
        server_3bet_prior). Without this filter, `OpponentStats(**dict)`
        throws TypeError on stale files.
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
        except json.JSONDecodeError as exc:
            log.warning("OpponentModel.load: invalid JSON in %s: %s", filepath, exc)
            return model

        valid_keys = {f.name for f in fields(OpponentStats)}

        def _build(stats_dict: dict) -> OpponentStats:
            return OpponentStats(**{k: v for k, v in stats_dict.items()
                                     if k in valid_keys})

        for pid_str, stats_dict in data.get("stats", {}).items():
            model._stats[int(pid_str)] = _build(stats_dict)
        model._id_to_name = {int(k): v for k, v in data.get("id_to_name", {}).items()}
        model._name_to_id = data.get("name_to_id", {})
        for name, stats_dict in data.get("name_archive", {}).items():
            model._name_archive[name] = _build(stats_dict)
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
                s.river_check_count += o.river_check_count
                s.river_action_count += o.river_action_count
                s.river_facing_bet_fold_count += o.river_facing_bet_fold_count
                s.river_facing_bet_opps += o.river_facing_bet_opps
                s.flop_bet_count += o.flop_bet_count
                s.flop_passive_count += o.flop_passive_count
                s.turn_bet_count += o.turn_bet_count
                s.turn_passive_count += o.turn_passive_count
                s.flop_seen_count += o.flop_seen_count
                s.showdown_count += o.showdown_count
                s.showdown_win_count += o.showdown_win_count
                s.bet_win_count += o.bet_win_count
                s.bluff_win_count += o.bluff_win_count
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
