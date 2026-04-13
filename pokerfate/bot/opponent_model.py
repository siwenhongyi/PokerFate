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

player_type 标签（hands_seen >= 20；按下列顺序先匹配先胜出）
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
    # 服务端 30 天历史先验值（直接存比率，不猜分母）
    # session 样本充足后切换到实测值（见对应 property）
    server_af_prior: float = 0.0      # active_rate/1000
    server_cbet_prior: float = 0.0    # c_bete_rate/10000
    server_3bet_prior: float = 0.0    # three_bet_rate/10000
    server_wtsd_prior: float = 0.0    # show_hand_rate/10000（showdowns per VPIP hand）

    # River
    river_bet_count: int = 0
    river_fold_count: int = 0
    river_call_count: int = 0
    river_check_count: int = 0   # checks on river (not facing a bet)
    river_action_count: int = 0

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
        if self.three_bet_opportunities < 15 and self.server_3bet_prior > 0:
            return self.server_3bet_prior
        return self.three_bet_count / max(self.three_bet_opportunities, 1)

    @property
    def fold_to_3bet(self) -> float:
        return self.fold_to_3bet_count / max(self.fold_to_3bet_opps, 1)

    @property
    def cbet_pct(self) -> float:
        if self.cbet_opportunities < 10 and self.server_cbet_prior > 0:
            return self.server_cbet_prior
        return self.cbet_count / max(self.cbet_opportunities, 1)

    @property
    def fold_to_cbet(self) -> float:
        return self.fold_to_cbet_count / max(self.fold_to_cbet_opps, 1)

    @property
    def aggression_factor(self) -> float:
        session_actions = self.call_count + self.check_count + self.bet_count + self.raise_count
        if session_actions < 20 and self.server_af_prior > 0:
            return self.server_af_prior
        passive = max(self.call_count + self.check_count, 1)
        return (self.bet_count + self.raise_count) / passive

    @property
    def river_fold_rate(self) -> float:
        return self.river_fold_count / max(self.river_action_count, 1)

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
        """Went to showdown: fraction of flop-seen hands that reached showdown."""
        if self.flop_seen_count < 15 and self.server_wtsd_prior > 0:
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
        只有 hands_seen >= 20 时才有意义，样本不足返回 0。

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
        if self.hands_seen < 20:
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
        if self.hands_seen < 20:
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
        if s.river_action_count < 5:
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

        两层结构：
          第一层 — 方向（bluff/value/trap）：由 player_type + AF + WTSD 决定
          第二层 — 强度（aggression_scale）：由 PWI 连续分决定，线性映射到 [0.3, 1.5]

        aggression_scale 含义：
          1.0 = GTO 基准（无调整）
          < 1.0 = 减少下注频率（对手不弃牌，只做价值）
          > 1.0 = 增加下注频率（对手容易弃牌，多诈唬）
        """
        s = self.get(player_id)
        adj = {}

        if s.hands_seen < 20:
            return adj

        ptype = s.player_type()
        pwi = s.pwi()

        # ── 第一层：方向信号（基于类型 + AF + WTSD）──────────────────────────

        if ptype == 'whale':
            # 极度被动：永不弃牌，永不加注 → 纯价值，不诈唬，加大注码
            adj['bluff_freq'] = 'none'
            adj['cbet_freq'] = 'value_only'
            adj['value_sizing'] = 'large'

        elif ptype == 'calling_station':
            # 跟注站：很少弃牌 → 禁止诈唬，价值下注
            adj['bluff_freq'] = 'none'
            adj['cbet_freq'] = 'value_only'
            adj['value_sizing'] = 'large'

        elif ptype == 'maniac':
            # 疯狂加注者：用强手慢打，让他们把钱送进来
            adj['bluff_freq'] = 'low'
            adj['check_raise_freq'] = 'high'
            adj['trap_freq'] = 'high'

        elif ptype == 'fish':
            # 普通鱼：入池太多但有时会弃牌，价值为主偶尔诈唬
            adj['bluff_freq'] = 'low'
            adj['value_sizing'] = 'large'

        elif ptype == 'nit':
            # 超紧：弃牌率高，诈唬有价值
            adj['cbet_freq'] = 'high'
            adj['bluff_freq'] = 'high'

        # ── 第二层：强度信号（PWI 连续映射）────────────────────────────────
        # PWI > 60: 极度可剥削 (whale/super fish) → aggression_scale 低至 0.3
        # PWI 30-60: 明显可剥削 (standard fish)  → aggression_scale 0.5-0.7
        # PWI 0-30: 轻微可剥削                   → aggression_scale 0.8-1.0
        # PWI < 0: reg/nit，可增加诈唬频率       → aggression_scale 1.0-1.4
        #
        # 对被动型（bluff_freq=none）：scale 控制价值下注频率（低 = 更纯价值）
        # 对激进型（bluff_freq=high）：scale 控制诈唬频率（高 = 更多诈唬）
        if pwi >= 60:
            adj['aggression_scale'] = 0.35   # whale: 极低，纯价值
        elif pwi >= 40:
            adj['aggression_scale'] = 0.55   # strong calling station
        elif pwi >= 20:
            adj['aggression_scale'] = 0.75   # fish
        elif pwi >= 0:
            adj['aggression_scale'] = 0.90   # 轻微可剥削
        elif pwi >= -10:
            adj['aggression_scale'] = 1.10   # reg 偏紧
        else:
            adj['aggression_scale'] = 1.30   # nit，增加诈唬

        # ── 细粒度指标覆盖（有足够样本时，实测数据优先于类型推断）──────────

        # fold_to_cbet 实测 > 60%：无论类型如何，c-bet 有利可图
        if s.fold_to_cbet > 0.60 and s.fold_to_cbet_opps >= 5:
            adj['cbet_freq'] = 'high'
            adj.pop('bluff_freq', None)   # 取消 none/low 限制

        # fold_to_3bet 实测 > 65%：3bet 挤压有价值
        if s.fold_to_3bet > 0.65 and s.fold_to_3bet_opps >= 5:
            adj['three_bet_freq'] = 'high'

        # 河牌弃牌率高：河牌诈唬有利可图
        if s.river_fold_rate > 0.55 and s.river_action_count >= 5:
            adj['river_bluff_freq'] = 'high'

        # WTSD：有服务端先验或本地 >= 15 手翻牌时使用
        if s.flop_seen_count >= 15 or s.server_wtsd_prior > 0:
            if s.wtsd > 0.38:
                # 频繁摊牌 = 不弃牌 → 强化禁止诈唬
                adj['bluff_freq'] = 'none'
                adj['value_sizing'] = 'large'
            elif s.wtsd < 0.20:
                # 极少摊牌 = 容易弃牌 → 可以诈唬
                adj.setdefault('bluff_freq', 'high')

        # WMSD + WTSD 联合信号（样本 >= 8 次摊牌）
        if s.showdown_count >= 8:
            if s.wmsd < 0.45 and s.wtsd > 0.35:
                # 频繁摊牌但经常输 → 只用强手来摊，加大价值注码
                adj['bluff_freq'] = 'none'
                adj['value_sizing'] = 'large'
            elif s.wmsd > 0.62 and s.wtsd < 0.25:
                # 只用强手摊牌 → 可以诈唬迫使弃牌
                adj.setdefault('bluff_freq', 'high')

        # bluff_win_rate：有下注行为时以弱牌赢的比例（>= 5手样本）
        if s.bet_win_count >= 5:
            if s.bluff_win_rate > 0.40:
                # 超过40%的赢都是高牌/一对 → 频繁诈唬得手，可以更多跟注
                adj['river_bluff_likely'] = True
                adj.setdefault('bluff_freq', 'none')   # 对他诈唬无意义，他会跟
            elif s.bluff_win_rate < 0.15:
                # 几乎从不用弱牌赢 → 下注时通常有货，收紧跟注
                adj['river_bet_rare'] = True

        # 河牌下注频率信号
        river_bf_samples = s.river_bet_count + s.river_check_count
        if river_bf_samples >= 8:
            if s.river_bet_frequency > 0.55:
                adj['river_bluff_likely'] = True
            elif s.river_bet_frequency < 0.20:
                adj['river_bet_rare'] = True

        # 各街 AFq 信号
        flop_samples = s.flop_bet_count + s.flop_passive_count
        turn_samples = s.turn_bet_count + s.turn_passive_count
        river_afq_samples = s.river_bet_count + s.river_call_count + s.river_check_count

        if flop_samples >= 10 and s.flop_afq > 0.60:
            adj['flop_float_favorable'] = True

        if turn_samples >= 8 and river_afq_samples >= 8:
            if s.turn_afq > 0.50 and s.river_afq < 0.25:
                adj['turn_bluff_then_fold'] = True

        if flop_samples >= 10 and turn_samples >= 8 and river_afq_samples >= 8:
            if s.river_afq >= s.flop_afq * 0.90:
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
                s.river_check_count += o.river_check_count
                s.river_action_count += o.river_action_count
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
