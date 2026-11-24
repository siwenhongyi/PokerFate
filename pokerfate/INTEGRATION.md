# PokerFate API 接入

通过 `pokerfate.api` 将决策引擎接入外部牌桌、模拟器或回放程序。
调用方提供牌局状态和行动历史，并负责执行返回的动作；API 负责维护决策状态和生成建议。
引擎配置、solver 构建和翻牌书见 [决策引擎说明](decision/README.md)。

## 安装与初始化

在项目根目录安装依赖：

```bash
.venv/bin/python -m pip install -r requirements.txt
```

Python 3.12+。`numpy` 是运行依赖；`eval7` 加速牌力评估，未安装时有纯 Python fallback；
`lightgbm` 用于范围层的桶校准，没有时范围只来自动作似然，决策会不同。
实时 CFR 另需按决策引擎文档构建本地 solver。

```python
from pokerfate.api import ActionEvent, PlayerInfo, PokerFateAPI

api = PokerFateAPI(
    my_player_id=101,
    big_blind=2.0,
    small_blind=1.0,
    equity_iterations=800,
    decision_engine="cfr",
    cfr_flop_book_enabled=True,
    realtime_cfr_timeout_sec=10,
    verbose=False,
)
```

- `small_blind` 默认是固定的 `1.0`，不会自动随 `big_blind` 除以二；应传牌桌实际值。
- `decision_engine`、`cfr_flop_book_enabled` 不传时读取环境变量及默认值；显式参数优先。
- `decision_seed` 默认 `None`；指定整数可复现决策随机数，主要供回放使用。
- `autosave_path` 默认是仓库里的 `local/models/opponents.json`：创建时读取，每手结束后写回；传 `None` 不读也不写。
- `log_file` 默认 `pokerfate/logs/pokerfate.log`；传 `None` 不写文件日志。每创建一个实例，已有的日志会先并入
  `pokerfate/logs/archive/` 再清空，所以同一份仓库里同时运行多个实例时，要给每个实例单独的路径。
- `enable_showdown_calibration` 默认开启：把摊牌样本写进 `local/training/`，由后台进程计算，用来校准 hero 胜率；
  离线示例和测试可以关闭。

## 身份、座位与筹码

`PlayerInfo` 描述这一手发到牌的玩家，包括 hero：

```python
PlayerInfo(
    player_id=102,       # 稳定 UID，不是座位号
    name="对手",        # 展示名称，不作为身份键
    stack=199.0,        # 当前剩余筹码；None 表示未知
    position="SB",      # 权威位置标签，优先使用
    seat_index=3,       # 可选：物理座位号
    is_robot=False,     # 可选：已证实的平台机器人
)
```

对手数据以 `player_id` 为主键：改名不丢历史，同名不同 UID 不合并。

`is_robot` 只对确认是平台机器人的玩家传 `True`。机器人照常对局，但不进入任何学习；
一手牌里没有真人、或真人少于机器人时，这一手谁的数据都不学。

位置按以下优先级处理：显式 `position`；缺失时用物理座位和按钮座位推导；再缺失时用
`players` 的座次顺序与 `dealer_id` 推导。显式位置会归一化为按钮相对的位置名供策略使用。
`dealer_id` 通常是按钮玩家的 UID，不是座位号；按钮为空位时，可传 `-(按钮座位号 + 1)`，
同时传入各玩家的 `seat_index` 和实际位置，避免把空按钮误放到列表第一人。

新一手筹码优先用显式 `stack`，其次是上一手的 `final_stacks`，未知新玩家才默认 100BB。
买入、补码和重进后应始终传服务器快照，不沿用旧手估算。

## 一手牌的生命周期

```text
new_hand → deal_hole_cards
  → 按顺序 notify_action / deal_board / request_action
  → hand_over
```

下面只演示发牌和一次决策，不假设策略一定返回某个动作：

```python
from pokerfate.api import PlayerInfo, PokerFateAPI

# 示例不保存到实战模型或日志，也不启动摊牌样本采集。
api = PokerFateAPI(
    my_player_id=101, big_blind=2.0, small_blind=1.0,
    autosave_path=None, log_file=None, enable_showdown_calibration=False,
    decision_engine="rule_engine",
)
# 三人桌，hero 在 BTN；对手已付小盲和大盲，尚无主动行动。
api.new_hand([
    PlayerInfo(101, "Hero", 200.0, "BTN", seat_index=0),
    PlayerInfo(102, "SB", 199.0, "SB", seat_index=1),
    PlayerInfo(103, "BB", 198.0, "BB", seat_index=2),
], dealer_id=101)
api.deal_hole_cards(["Ac", "Kd"])
decision = api.request_action(
    street="preflop", pot=3.0, current_bet=2.0, to_call=2.0,
    my_stack=200.0, my_current_bet_this_street=0.0,
    num_active_opponents=2, min_raise_to=4.0,
)
print(decision.action, decision.amount)
```

交盲注和前注不是主动加注，**不要用 `ActionEvent(..., action="raise")` 表示强制投入**。
牌桌适配器负责提供准确的底池、已投入金额、剩余筹码和合法加注下限。

API 在 `request_action` 中按返回的动作记账；不要把 hero 再通过 `notify_action` 上报一遍。
API 没有撤销或改正已记账动作的接口。服务器实际执行的金额不同（取整、全下、最小加注）时，
可以调用 `record_hero_execution` 把实际结果写进日志，它不改内部状态。
之后的 `deal_board(pot=...)`、`ActionEvent.stack_after` 和下一手 `new_hand` 的筹码都传服务器的真实值，后续计算以它们为准。

## 对手行动与金额

盲注、底池、筹码和行动金额统一使用调用方的筹码单位，不混用筹码数与 BB 倍数。

```python
ActionEvent(
    player_id=102,
    action="call",
    amount=4.0,           # 本次追加 4；例如已经投入 2，跟到 6
    street="preflop",
    stack_after=194.0,    # 服务器报告的行动后剩余筹码
)
```

| 动作 | `ActionEvent.amount` 的含义 |
|---|---|
| `raise`（含首次下注） | 本街总下注额，即 raise-to |
| `call` | 本次追加金额；0 是兼容用法，表示由当前最高下注推算 |
| `check` / `fold` | 0 |

`stack_after` 有值时优先采用，避免漏计盲注等强制投入。
短筹码全下未超过本街最高下注时按 `call` 上报，超过时才按 `raise` 上报。
按真实顺序提供完整对手行动：缺失或乱序会影响范围、3bet/cbet 统计以及 solver 节点定位。

如果数据源提供预选动作信息，可额外传入 `pre_action`：0 无标记，1 预选因下注变化被重置，2 本次执行了预选动作。
未提供时使用 0，不需要从行动速度推断。

## 方法参考

### `new_hand(players, dealer_id, hand_number=None)`

重置本手底牌、公共牌、行动历史和决策状态。`players` 应按实际座次组织，并尽量传权威位置和物理座位。
`hand_number` 可传外部递增手号，不传则内部累加。

### `deal_hole_cards(cards)`

传入两张底牌，如 `["Ac", "Kd"]`。牌面格式为 `2–9/T/J/Q/K/A` 加 `c/d/h/s`。

### `deal_board(cards, street, pot=None)`

只传新发的牌：翻牌 3 张，转牌、河牌各 1 张。`street` 为 `flop/turn/river`。
`pot` 是本街开始时的真实底池，建议总是提供，它也影响 solver 的起点。

### `sync_board(cards, street, pot=None)`

用于服务器提供完整公共牌快照的接入。重复快照不重复发牌；正常追加部分会经过 `deal_board`，
缺街或不一致的快照则静默恢复已知牌面。它不恢复缺失的行动历史，不能代替完整的断线恢复流程。

### `notify_action(event)`

上报对手的真实行动；hero 的事件会被忽略。身份、金额和行动顺序按上面的约定。

### `request_action(...) → BotDecision`

| 参数 | 含义 |
|---|---|
| `street` | `preflop/flop/turn/river` |
| `pot` | hero 行动前的底池，不含本次尚未发生的投入 |
| `current_bet` | 本街最高总下注额；无人下注为 0 |
| `to_call` | hero 需追加的跟注金额 |
| `my_stack` | hero 当前剩余筹码 |
| `num_active_opponents` | 仍在手的对手人数，默认 1；多人接入必须传实际值 |
| `my_current_bet_this_street` | hero 本街已投入金额，默认 0 |
| `is_bb_option` | BB 面对无人加注的免费看牌机会时为 True，默认 False |
| `min_raise_to` | 服务器接受的最小本街总加注额；0 表示不能加注，None 表示未知 |

返回 `action` 为 `fold/check/call/raise`；返回的 `amount` 只有 raise 时表示本街总下注额，其余为 0。
注意这是 **返回值** 的约定，与输入 `ActionEvent` 的 call 追加金额不同。
加注会按最小加注额、剩余筹码和对手是否还能跟注校正；未知最小加注额时至少保证 1BB。

### `hand_over(winner_ids, pot, ...)`

以牌桌实际结算为准，每手调用一次。可选数据使用关键字参数传入：

- `winner_ids`：赢家 UID 列表，平分或边池可有多人。
- `pot`：本手结算底池金额。
- `final_stacks`：各玩家结算后筹码，强烈建议提供。
- `showdown_hands`：实际公开的底牌，形如 `{102: ["Ah", "As"]}`；不要填猜测牌。
- `winner_hand_types`：服务器给出的赢家牌型编号，形如 `{102: 牌型编号}`。有它时结算显示用服务器牌型，
  对手河牌诈唬赢池的统计也只在有它时记录。
- `my_profit_delta`：服务端本手 hero 净盈亏，优先于筹码差，避免买入、补码和重进干扰。

此方法更新对手数据、处理摊牌校准并触发模型保存。结束会话前应完成最后一手的结算。

### `notify_player_joined(player_id, name, stack=None)`

用于两手之间的玩家变更，注册 UID 和展示名；未知筹码默认 100BB。
下一手仍需在 `new_hand` 传完整玩家名单。不同 UID 的历史不会因同名自动合并。

### `set_table_blinds(big_blind, small_blind)`

换桌时同步实际盲注，更新未知筹码的默认 100BB 基准。两种盲注都应传服务器值。

### `record_hero_execution(*, action, amount_added, total_bet_after, street)`

服务器确认 hero 的动作后调用，记录实际执行的动作、本次追加金额和本街总投入。只写日志，供离线分析比对。

### `last_decision_diagnostics() → dict`

最近一次决策的诊断信息：`decision_source` 和对应引擎的详情，字段见[决策引擎的诊断](decision/README.md#诊断)。

### 引擎状态与切换

`decision_engine_status()` 返回实际启用状态和错误原因。
`set_decision_engine("cfr" | "rule_engine")` 切换模式并记录会话配置；空闲时调用，不能与决策并发。

## 持久化

模型默认写在 `local/models/opponents.json`，按 UID 跨会话累计，名称仅作展示。
`autosave_path=None` 只关闭保存；同一 API 实例仍可在内存中学习。
