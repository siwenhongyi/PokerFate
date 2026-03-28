"""Slumbot API adapter — plays PokerFate bot against slumbot.com.

协议说明
--------
Slumbot 是 CMU 开源的基于 CFR 的德州 bot，提供公开 HTTP API 进行 HU 对战。
  https://slumbot.com/

API 端点：
  POST /slumbot/api/new_hand   → 开始新手牌
  POST /slumbot/api/act        → 提交行动

行动字符串格式（action string）：
  k = check（过牌）
  c = call（跟注）
  f = fold（弃牌）
  b{N} = bet/raise，N = 本街本方累计投入筹码数
  /    = 街道分隔符

示例：'b200c/kb400'
  翻牌前：我方下注 200，对方跟注
  翻牌：对方过牌，我方下注 400

参数：
  blinds 50/100，stack 20000（每手重置）
  client_pos=0 → 我方是 BB（OOP 翻后）
  client_pos=1 → 我方是 SB/BTN（IP 翻后）
"""

from __future__ import annotations

import requests
from typing import List, Optional, Tuple

from pokerfate.core.card import Card
from pokerfate.core.game_state import GameState, Player, Street, Action, ActionType
from pokerfate.bot.poker_bot import PokerBot

# ── 常量 ──────────────────────────────────────────────────────────────────────

HOST = 'slumbot.com'
BIG_BLIND = 100
SMALL_BLIND = 50
STACK_SIZE = 20_000
STREET_NAMES = ['preflop', 'flop', 'turn', 'river']
STREET_ENUMS = [Street.PREFLOP, Street.FLOP, Street.TURN, Street.RIVER]

OUR_ID = 0
SLUMBOT_ID = 1


# ── HTTP 封装 ─────────────────────────────────────────────────────────────────

def _post(endpoint: str, data: dict) -> dict:
    resp = requests.post(
        f'https://{HOST}/slumbot/api/{endpoint}',
        json=data,
        timeout=15,
    )
    if resp.status_code != 200:
        raise RuntimeError(f'HTTP {resp.status_code} /{endpoint}: {resp.text[:200]}')
    r = resp.json()
    if 'error_msg' in r:
        raise RuntimeError(f"Slumbot error: {r['error_msg']}")
    return r


def slumbot_login(username: str, password: str) -> str:
    r = _post('login', {'username': username, 'password': password})
    token = r.get('token')
    if not token:
        raise RuntimeError('Login failed: no token in response')
    return token


def slumbot_new_hand(token: Optional[str] = None) -> dict:
    return _post('new_hand', {'token': token} if token else {})


def slumbot_act(token: str, incr: str) -> dict:
    return _post('act', {'token': token, 'incr': incr})


# ── Action string 解析 ────────────────────────────────────────────────────────

def parse_hand_state(action_str: str, client_pos: int) -> dict:
    """重放完整 action string，推导当前游戏状态。

    Parameters
    ----------
    action_str : str
        Slumbot 返回的完整行动字符串，如 'b200c/kb400'。
    client_pos : int
        0 = 我方是 BB；1 = 我方是 SB（Slumbot 约定）。

    Returns
    -------
    dict
        street        : 'preflop' | 'flop' | 'turn' | 'river'
        pot           : 底池总筹码
        our_street_inv: 我方本街已投入筹码
        to_call       : 我方需补充跟注筹码（0 = 无需跟注）
        our_total_inv : 我方本手总投入
        is_over       : 手牌是否已结束（弃牌 / 摊牌）
    """
    # ParseAction 约定：pos=0 是 BB，pos=1 是 SB
    our_pos = client_pos

    # 两方累计投入（含各街）；从盲注开始
    total_inv = [BIG_BLIND, SMALL_BLIND]   # total_inv[ParseAction_pos]

    # 注意：不要 rstrip('/')，尾部的 '/' 表示已进入下一街但尚无行动
    # 'b200c/' → ['b200c', ''] → preflop 结束，flop 刚开始（无行动）
    streets = action_str.split('/') if action_str else ['']

    # 本街两方投入（每街重置，翻牌前从盲注开始）
    st_inv = [BIG_BLIND, SMALL_BLIND]
    current_st_idx = 0
    hand_over = False

    for st_idx, st_str in enumerate(streets):
        current_st_idx = st_idx
        if st_idx > 0:
            st_inv = [0, 0]

        # 首位行动者：翻牌前 SB（pos=1）先行；翻后 BB（pos=0）先行
        acting = 1 if st_idx == 0 else 0

        i = 0
        while i < len(st_str):
            c = st_str[i]; i += 1
            if c == 'f':
                hand_over = True
                break
            elif c == 'k':
                acting = 1 - acting
            elif c == 'c':
                matched = max(st_inv)
                delta = matched - st_inv[acting]
                total_inv[acting] += delta
                st_inv[acting] = matched
                acting = 1 - acting
            elif c == 'b':
                j = i
                while i < len(st_str) and st_str[i].isdigit():
                    i += 1
                new_st_total = int(st_str[j:i])
                delta = new_st_total - st_inv[acting]
                total_inv[acting] += delta
                st_inv[acting] = new_st_total
                acting = 1 - acting

        if hand_over:
            break

    our_street_inv = float(st_inv[our_pos])
    slumbot_street_inv = float(st_inv[1 - our_pos])
    to_call = max(0.0, slumbot_street_inv - our_street_inv)

    return {
        'street': STREET_NAMES[current_st_idx],
        'pot': float(sum(total_inv)),
        'our_street_inv': our_street_inv,
        'to_call': to_call,
        'our_total_inv': float(total_inv[our_pos]),
        'is_over': hand_over,
    }


def iter_actions(action_str: str, client_pos: int):
    """逐一产出 (actor_pos, action_type_str) 元组。

    用于区分哪些行动属于我方、哪些属于 Slumbot，
    以便仅将 Slumbot 的行动喂给 range estimator。
    """
    streets = action_str.split('/') if action_str else ['']
    for st_idx, st_str in enumerate(streets):
        acting = 1 if st_idx == 0 else 0
        i = 0
        while i < len(st_str):
            c = st_str[i]; i += 1
            if c == 'f':
                yield (acting, 'fold')
                return
            elif c == 'k':
                yield (acting, 'check')
                acting = 1 - acting
            elif c == 'c':
                yield (acting, 'call')
                acting = 1 - acting
            elif c == 'b':
                while i < len(st_str) and st_str[i].isdigit():
                    i += 1
                yield (acting, 'raise')
                acting = 1 - acting


def _build_preflop_history(
    action_str: str,
    client_pos: int,
) -> list:
    """从 action string 重建翻牌前行动历史（供 _classify_preflop_action 使用）。"""
    streets = action_str.split('/') if action_str else ['']
    if not streets:
        return []

    history = []
    st_str = streets[0]
    acting = 1   # SB 先行
    i = 0
    while i < len(st_str):
        c = st_str[i]; i += 1
        pid = OUR_ID if acting == client_pos else SLUMBOT_ID
        if c == 'b':
            j = i
            while i < len(st_str) and st_str[i].isdigit():
                i += 1
            amount = float(st_str[j:i])
            history.append((pid, Action(ActionType.RAISE, amount), "preflop"))
            acting = 1 - acting
        elif c == 'c':
            history.append((pid, Action(ActionType.CALL, 0.0), "preflop"))
            acting = 1 - acting
        elif c == 'k':
            history.append((pid, Action(ActionType.CHECK, 0.0), "preflop"))
            acting = 1 - acting
        elif c == 'f':
            history.append((pid, Action(ActionType.FOLD, 0.0), "preflop"))
            break
    return history


# ── 辅助函数 ──────────────────────────────────────────────────────────────────

def parse_cards(card_strs: List[str]) -> List[Card]:
    return [Card.from_str(s) for s in card_strs]


def action_to_incr(action: Action, our_street_inv: float) -> str:
    """将 PokerBot 的 Action 转换为 Slumbot incr 字符串。

    Slumbot b{N}：N = 行动后本方本街累计投入筹码。
    我方 action.amount = 本次行动新增筹码（包含跟注部分）。
    因此 N = our_street_inv（行动前）+ action.amount。
    """
    if action.action_type == ActionType.FOLD:
        return 'f'
    if action.action_type == ActionType.CHECK:
        return 'k'
    if action.action_type == ActionType.CALL:
        return 'c'
    if action.action_type == ActionType.RAISE:
        n = int(our_street_inv + action.amount)
        return f'b{n}'
    return 'k'


# ── 主适配器类 ─────────────────────────────────────────────────────────────────

class SlumbotAdapter:
    """在 Slumbot 公开 API 上运行 PokerFate bot。

    用法
    ----
    bot = PokerBot(name='PokerFate', equity_iterations=1000)
    adapter = SlumbotAdapter(bot)                          # 匿名对战
    # 或带账号登录（需在 slumbot.com 注册）：
    adapter = SlumbotAdapter(bot, username='u', password='p')

    results = adapter.play_session(num_hands=200)
    """

    def __init__(
        self,
        bot: PokerBot,
        username: str = '',
        password: str = '',
        verbose: bool = True,
    ):
        self.bot = bot
        self.verbose = verbose
        self.token: Optional[str] = None

        if username and password:
            self.token = slumbot_login(username, password)
            if verbose:
                print(f'已登录账户 {username}，token: {self.token}')

        # 每手牌已观察过的 Slumbot 行动数（用于去重）
        self._slumbot_observed: int = 0

    # ── 多手对战 ───────────────────────────────────────────────────────────────

    def play_session(self, num_hands: int = 100) -> dict:
        """运行 num_hands 手，打印逐手和汇总结果。"""
        total_chips = 0
        for h in range(num_hands):
            print(f'\n{"="*15} {h+1} {"="*15}')
            try:
                w = self.play_hand()
            except Exception as exc:
                print(f'手牌 {h + 1} 出错: {exc}')
                w = 0
            total_chips += w
            sign = '+' if w >= 0 else ''
            print(
                f'手牌 {h + 1:4d}  {sign}{w / BIG_BLIND:+.1f}BB  '
                f'累计 {total_chips / BIG_BLIND:+.1f}BB'
            )

        bb_per_100 = total_chips / BIG_BLIND / num_hands * 100
        print(
            f'\n=== 共 {num_hands} 手  总计 {total_chips / BIG_BLIND:+.1f}BB  '
            f'({bb_per_100:.1f} BB/100) ==='
        )
        return {
            'hands': num_hands,
            'total_chips': total_chips,
            'bb_per_100': bb_per_100,
        }

    # ── 单手牌 ─────────────────────────────────────────────────────────────────

    def play_hand(self) -> int:
        """运行一手牌，返回盈亏筹码数（正数=盈利）。"""
        r = slumbot_new_hand(self.token)
        self.token = r.get('token', self.token)

        client_pos: int = r.get('client_pos', 0)
        hole_cards: List[Card] = parse_cards(r.get('hole_cards', []))

        # dealer_pos 决定谁 IP：
        #   client_pos=1 (SB/BTN, 我方 IP) → dealer_pos=0（我方索引=BTN）
        #   client_pos=0 (BB, 我方 OOP)   → dealer_pos=1（Slumbot 索引=BTN）
        dealer_pos = 1 - client_pos

        # 重置 bot 手牌状态
        self.bot.new_hand([OUR_ID, SLUMBOT_ID])
        self._slumbot_observed = 0

        pos_str = 'SB/BTN(IP)' if client_pos == 1 else 'BB(OOP)'
        if self.verbose:
            print(f'\n── 新手牌 ─── 我方位置: {pos_str}  手牌: {hole_cards}')

        # 检查手牌是否直接结束（Slumbot 立刻弃牌，极罕见）
        if 'winnings' in r:
            if self.verbose:
                print(f'  手牌立刻结束，盈亏: {r["winnings"] / BIG_BLIND:+.1f}BB')
            return r['winnings']

        # 主循环
        while True:
            action_str: str = r.get('action', '')
            board: List[Card] = parse_cards(r.get('board', []))
            winnings = r.get('winnings')

            if winnings is not None:
                if self.verbose:
                    print(f'  → 手牌结束  盈亏: {winnings / BIG_BLIND:+.1f}BB')
                return winnings

            # 解析当前游戏状态
            state = parse_hand_state(action_str, client_pos)
            if state['is_over']:
                return r.get('winnings', 0)

            # 将新观察到的 Slumbot 行动喂给 range estimator
            self._observe_new_slumbot_actions(action_str, client_pos, state['street'])

            # 构建 GameState 并让 bot 决策
            gs = self._build_game_state(hole_cards, board, state, dealer_pos, action_str, client_pos)
            bot_action = self.bot.decide(gs, my_player_id=OUR_ID)

            if self.verbose:
                self._log_decision(state, board, hole_cards, bot_action)

            # 转换为 Slumbot incr 并发送
            incr = action_to_incr(bot_action, state['our_street_inv'])
            if self.verbose:
                print(f'  发送: {incr}')

            r = slumbot_act(self.token, incr)
            self.token = r.get('token', self.token)

    # ── 内部方法 ───────────────────────────────────────────────────────────────

    def _observe_new_slumbot_actions(
        self,
        action_str: str,
        client_pos: int,
        current_street: str,
    ) -> None:
        """仅观察本次响应中新增的 Slumbot 行动，避免重复喂入 range estimator。"""
        slumbot_pos = 1 - client_pos
        slumbot_seen = 0

        # 重新枚举全部行动，跳过已观察的
        street_idx_map = {n: i for i, n in enumerate(STREET_NAMES)}
        actions_with_street = self._iter_actions_with_street(action_str, client_pos)

        for (actor_pos, action_type_str, street_name) in actions_with_street:
            if actor_pos != slumbot_pos:
                continue
            slumbot_seen += 1
            if slumbot_seen <= self._slumbot_observed:
                continue  # 已处理过，跳过
            # 新行动：记录
            act = Action(ActionType[action_type_str.upper()])
            self.bot.observe_action(SLUMBOT_ID, act, street_name)
            self._slumbot_observed += 1

    def _iter_actions_with_street(self, action_str: str, client_pos: int):
        """产出 (actor_pos, action_type_str, street_name) 三元组。"""
        streets = action_str.split('/') if action_str else ['']
        for st_idx, st_str in enumerate(streets):
            street_name = STREET_NAMES[st_idx]
            acting = 1 if st_idx == 0 else 0
            i = 0
            while i < len(st_str):
                c = st_str[i]; i += 1
                if c == 'f':
                    yield (acting, 'fold', street_name)
                    return
                elif c == 'k':
                    yield (acting, 'check', street_name)
                    acting = 1 - acting
                elif c == 'c':
                    yield (acting, 'call', street_name)
                    acting = 1 - acting
                elif c == 'b':
                    while i < len(st_str) and st_str[i].isdigit():
                        i += 1
                    yield (acting, 'raise', street_name)
                    acting = 1 - acting

    def _build_game_state(
        self,
        hole_cards: List[Card],
        board: List[Card],
        state: dict,
        dealer_pos: int,
        action_str: str,
        client_pos: int,
    ) -> GameState:
        """构建供 PokerBot.decide() 使用的 GameState 对象。"""
        our_total_inv = state['our_total_inv']
        slumbot_total_inv = state['pot'] - our_total_inv
        our_stack = float(STACK_SIZE - our_total_inv)
        slumbot_stack = float(STACK_SIZE - slumbot_total_inv)

        our_street_inv = state['our_street_inv']
        slumbot_street_inv = our_street_inv + state['to_call']

        our_player = Player(
            player_id=OUR_ID,
            name='PokerFate',
            stack=our_stack,
            hole_cards=hole_cards,
            current_bet=our_street_inv,
        )
        slumbot_player = Player(
            player_id=SLUMBOT_ID,
            name='Slumbot',
            stack=slumbot_stack,
            hole_cards=[],
            current_bet=slumbot_street_inv,
        )

        st_enum = STREET_ENUMS[STREET_NAMES.index(state['street'])]
        street_max_bet = max(our_street_inv, slumbot_street_inv)

        # 翻牌前行动历史（用于 _classify_preflop_action）
        preflop_history = (
            _build_preflop_history(action_str, client_pos)
            if st_enum == Street.PREFLOP
            else []
        )

        return GameState(
            players=[our_player, slumbot_player],
            dealer_pos=dealer_pos,
            street=st_enum,
            board=board,
            pot=state['pot'],
            current_bet=street_max_bet,
            big_blind=float(BIG_BLIND),
            small_blind=float(SMALL_BLIND),
            current_player_idx=0,   # 永远是我方决策时才调用
            action_history=preflop_history,
        )

    def _log_decision(
        self,
        state: dict,
        board: List[Card],
        hole_cards: List[Card],
        bot_action: Action,
    ) -> None:
        street = state['street'].upper()
        board_str = str(board) if board else '---'
        print(
            f'  {street:<7} 底池:{state["pot"]:.0f}  '
            f'跟注:{state["to_call"]:.0f}  '
            f'胜率:{self.bot.last_equity:.0%}'
        )
        print(f'  手牌:{hole_cards}  牌面:{board_str}')
        print(f'  决策:{bot_action}  理由:{self.bot.last_reasoning}')
