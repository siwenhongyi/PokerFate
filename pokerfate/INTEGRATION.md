# PokerFate 外部接入文档

本文档面向**外部调用方**，说明如何将 PokerFate AI 接入你的德州扑克系统。

外部系统只需与 `pokerfate.api` 模块交互，无需了解任何内部实现细节。

---

## 快速开始

```python
from pokerfate.api import PokerFateAPI, PlayerInfo, ActionEvent

# 创建 bot 实例（程序启动时创建一次）
api = PokerFateAPI(my_player_id=0, big_blind=2.0)

# 每手牌开始
api.new_hand(
    players=[
        PlayerInfo(player_id=0, name="PokerFate", stack=200.0),
        PlayerInfo(player_id=1, name="GPT-4o",    stack=200.0),
    ],
    dealer_id=0,
)

# 发底牌
api.deal_hole_cards(["Ac", "Kd"])

# 需要 bot 决策时
decision = api.request_action(
    street="preflop",
    pot=3.0,
    current_bet=2.0,
    to_call=2.0,
    my_stack=200.0,
)
print(decision.action, decision.amount)  # raise  6.0

# 每手结束
api.hand_over(winner_ids=[0], pot=9.0, final_stacks={0: 207.0, 1: 193.0})
```

---

## 安装与初始化

### 依赖

无第三方依赖，仅需 Python 3.10+。

### 创建实例

```python
api = PokerFateAPI(
    my_player_id=0,          # bot 在本局中的 player_id（整数）
    big_blind=2.0,           # 大盲注金额
    small_blind=1.0,         # 小盲注金额（默认 big_blind / 2）
    equity_iterations=800,   # 胜率计算精度（越高越准但越慢，建议 500-1500）
    aggression=1.0,          # 翻牌后激进系数（1.0 = GTO 基准）
    autosave_path="opponents.json",  # 对手数据持久化文件（None = 禁用）
    verbose=False,           # True 时打印调试日志
)
```

`PokerFateAPI` 在初始化时会**自动从 `autosave_path` 加载历史对手数据**（文件不存在时安全忽略）。

---

## 数据类型

### `PlayerInfo`

描述一名玩家：

```python
from pokerfate.api import PlayerInfo

PlayerInfo(
    player_id=1,        # 唯一整数 ID
    name="GPT-4o",      # 显示名称（用于跨会话对手识别）
    stack=200.0,        # 筹码数量；传 None 表示未知（见筹码追踪章节）
    position="BTN",     # 位置标识（可选，仅供参考）
)
```

### `ActionEvent`

描述一名玩家的行动：

```python
from pokerfate.api import ActionEvent

ActionEvent(
    player_id=1,         # 行动的玩家 ID
    action="raise",      # "fold" | "check" | "call" | "raise"
    amount=6.0,          # raise 时为本街总下注额；其他行动填 0
    street="preflop",    # 当前街道（用于对手建模统计）
)
```

### `BotDecision`（返回值）

```python
decision = api.request_action(...)

decision.action   # str: "fold" | "check" | "call" | "raise"
decision.amount   # float: raise 时为本街总下注额，其他为 0
```

---

## 完整接入流程

### 每手牌标准流程

```
new_hand()
    ↓
deal_hole_cards()
    ↓
┌─────────────────────────────────────────────┐
│  循环：直到手牌结束                           │
│                                             │
│  notify_action()   ← 每个对手行动后调用      │
│  deal_board()      ← 每次发公共牌后调用      │
│  request_action()  ← 轮到 bot 行动时调用    │
└─────────────────────────────────────────────┘
    ↓
hand_over()
```

### 详细示例（一手完整牌局）

```python
# ── 手牌开始 ──────────────────────────────────
api.new_hand(
    players=[
        PlayerInfo(0, "PokerFate", 200.0, "BTN"),
        PlayerInfo(1, "GPT-4o",   200.0, "BB"),
    ],
    dealer_id=0,
)

# ── 翻牌前 ────────────────────────────────────
api.deal_hole_cards(["Qh", "Qs"])

# 对手 BB 已经 post（可通知，也可跳过）
api.notify_action(ActionEvent(1, "raise", 2.0, "preflop"))

# 轮到 bot 行动
decision = api.request_action(
    street="preflop",
    pot=3.0,
    current_bet=2.0,
    to_call=2.0,
    my_stack=200.0,
)
# → decision.action == "raise", decision.amount == 6.0
# 你的系统按此执行行动

# 对手跟注
api.notify_action(ActionEvent(1, "call", 6.0, "preflop"))

# ── 翻牌 ──────────────────────────────────────
api.deal_board(["Qd", "7h", "2c"], street="flop")   # 只传新增的牌

# 对手 check
api.notify_action(ActionEvent(1, "check", 0.0, "flop"))

# bot 行动
decision = api.request_action(
    street="flop",
    pot=12.0,
    current_bet=0.0,
    to_call=0.0,
    my_stack=197.0,
)
# → decision.action == "raise", decision.amount == 6.0

# 对手 fold
api.notify_action(ActionEvent(1, "fold", 0.0, "flop"))

# ── 手牌结束 ──────────────────────────────────
api.hand_over(
    winner_ids=[0],
    pot=24.0,
    final_stacks={0: 212.0, 1: 188.0},  # 强烈建议传入，用于筹码追踪
)
```

---

## API 方法参考

### `new_hand(players, dealer_id)`

每手牌开始时调用。

| 参数 | 类型 | 说明 |
|------|------|------|
| `players` | `List[PlayerInfo]` | 本手所有玩家（含 bot 自身） |
| `dealer_id` | `int` | 庄家/按钮位的 player_id |

---

### `deal_hole_cards(cards)`

告知 bot 自己的底牌。

| 参数 | 类型 | 示例 |
|------|------|------|
| `cards` | `List[str]` | `["Ac", "Kd"]` |

牌面格式：`[rank][suit]`，rank 为 `2-9 T J Q K A`，suit 为 `c d h s`。

---

### `deal_board(cards, street)`

发公共牌。每次只传**新发的牌**，不要传已有的牌。

| 参数 | 类型 | 说明 |
|------|------|------|
| `cards` | `List[str]` | 新发的牌，翻牌传 3 张，转牌/河牌传 1 张 |
| `street` | `str` | `"flop"` / `"turn"` / `"river"` |

---

### `notify_action(event)`

通知 bot 某位对手的行动，用于对手建模。

- 传入的是**对手的行动**，不需要传 bot 自身的行动。
- 不强制要求每个行动都通知，但越完整，对手建模越准确。
- **对手行动的顺序很重要**：API 内部根据已有行动历史自动判断当前是否为 3-bet 机会或面对 bot c-bet 的场景。因此请按实际行动顺序依次调用 `notify_action()`。

---

### `request_action(...) → BotDecision`

**请求 bot 决策**。轮到 bot 行动时调用。

| 参数 | 类型 | 说明 |
|------|------|------|
| `street` | `str` | `"preflop"` / `"flop"` / `"turn"` / `"river"` |
| `pot` | `float` | 当前底池大小（bot 行动前） |
| `current_bet` | `float` | 本街最高下注额（无人下注时为 0） |
| `to_call` | `float` | bot 需要追加的跟注金额（无需跟注时为 0） |
| `my_stack` | `float` | bot 当前筹码 |
| `num_active_opponents` | `int` | 仍在手的对手人数（默认 1） |
| `my_current_bet_this_street` | `float` | bot 本街已投入金额（默认 0） |

返回 `BotDecision(action, amount)`：

- `action` = `"fold"` / `"check"` / `"call"` / `"raise"`
- `amount` = raise 时的本街总下注额（call/check/fold 时为 0）

---

### `hand_over(winner_ids, pot, final_stacks, showdown_hands)`

每手结束时调用。调用后**自动保存对手数据**到磁盘。

| 参数 | 类型 | 说明 |
|------|------|------|
| `winner_ids` | `List[int]` | 赢家的 player_id 列表（平局时多个） |
| `pot` | `float` | 本手总底池 |
| `final_stacks` | `Dict[int, float]` | **强烈建议传入**：手牌结束后各玩家筹码 |
| `showdown_hands` | `Dict[int, List[str]]` | 可选：摊牌时的手牌，用于未来扩展 |

---

### `notify_player_joined(player_id, name, stack)`

对手中途替换时调用（不在手牌进行中）。

```python
# GPT-4 断线，GPT-4o 加入
api.notify_player_joined(player_id=2, name="GPT-4o", stack=300.0)
```

- 若该 `name` 曾在历史数据中出现（即使 `player_id` 不同），其历史统计自动迁移到新 ID。
- `stack=None` 时使用 100 BB 作为默认值。

---

### `notify_stack_update(player_id, new_stack)`

在手牌进行中同步某玩家的筹码（如旁池结算后）。

```python
api.notify_stack_update(player_id=1, new_stack=150.0)
```

---

### `opponent_summary() → str`

返回所有已知对手的统计摘要（可打印调试）。

```python
print(api.opponent_summary())
# Opponent Database:
#   [GPT-4o] OpponentStats(type=fish, VPIP=45%, PFR=12%, AF=0.8, fold_cbet=62%, hands=87)
```

---

## 筹码追踪

### 推荐方式：`hand_over` + `final_stacks`

```python
api.hand_over(winner_ids=[1], pot=20.0, final_stacks={0: 190.0, 1: 210.0})

# 下一手传 stack=None，API 自动使用上一手的结果
api.new_hand(
    players=[
        PlayerInfo(0, "PokerFate", None),   # 自动取 190.0
        PlayerInfo(1, "GPT-4o",   None),    # 自动取 210.0
    ],
    dealer_id=1,
)
```

### 未知筹码

新对手加入但筹码未知时：

```python
api.notify_player_joined(player_id=3, name="NewBot")  # 默认 100 BB
# 或
PlayerInfo(player_id=3, name="NewBot", stack=None)    # 同样默认 100 BB
```

---

## 对手模型持久化

对手模型**每局结束后自动保存**，程序被强制结束（Ctrl+C / IDE Stop）最多损失当局数据。

```python
# 默认保存到 opponents.json（当前目录）
api = PokerFateAPI(autosave_path="opponents.json")

# 自定义路径
api = PokerFateAPI(autosave_path="/data/pokerfate/gpt_opponents.json")

# 禁用自动保存
api = PokerFateAPI(autosave_path=None)
```

对手识别方式：**优先以 `name` 为准，其次以 `player_id`**。
这意味着即使对手重连后 `player_id` 改变，只要 `name` 相同，历史统计数据照常可用。

---

## 多人桌

`PokerFateAPI` 支持多人桌，无需额外配置。

```python
api.new_hand(
    players=[
        PlayerInfo(0, "PokerFate", 200.0, "BTN"),
        PlayerInfo(1, "GPT-4o",   200.0, "SB"),
        PlayerInfo(2, "Claude",   200.0, "BB"),
        PlayerInfo(3, "Gemini",   200.0, "UTG"),
    ],
    dealer_id=0,
)
```

`request_action` 时传入 `num_active_opponents` 告知当前仍在手的对手数：

```python
decision = api.request_action(
    street="flop",
    pot=20.0,
    current_bet=0.0,
    to_call=0.0,
    my_stack=194.0,
    num_active_opponents=2,   # 3 人手牌，1 人已 fold
)
```

---

## 注意事项

1. **`new_hand()` 必须在每手开始前调用**，它会重置本手状态（底牌、公共牌、行动历史）。
2. **`deal_board()` 只传新增的牌**，不要每次都传全部公共牌。
3. **`request_action()` 中的 `pot` 是 bot 行动前的底池**，不含 bot 本次可能的下注。
4. **`notify_action()` 不需要传 bot 自身的行动**，只传对手行动即可。
5. **`hand_over()` 是触发自动保存的唯一时机**，请确保每手结束后都调用它。
6. **`notify_action()` 需要按实际行动顺序依次调用**，API 内部根据行动历史自动推断 3-bet 机会和 c-bet 场景，乱序调用会导致对手统计不准确。
7. **`dealer_id` 是 `player_id`，不是座位编号**。位置（BTN/SB/BB 等）由 bot 根据 `players` 列表顺序和 `dealer_id` 自动推算，与 `player_id` 的数值大小无关。
