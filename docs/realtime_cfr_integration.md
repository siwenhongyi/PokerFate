# Realtime CFR 接入总结

## DECISION_ENGINE 模式

- `local` 或非法值：PokerFate 纯本地决策。
- `g5_all`：翻前、翻后都由 g5 接管，PokerFate 只做旁路对照。
- `g5`：翻前 PokerFate 查表/本地，翻后 g5 接管；翻前仍同步 g5 shadow，保证翻后状态连续。
- `realtime_cfr`：翻前、翻牌 PokerFate 本地；转牌、河牌走 realtime CFR 局部实时搜索，10 秒超时或准备失败时回退 PokerFate 本地。
- `cfr`：翻前 PokerFate 本地；翻牌查离线 CFR 书；转牌、河牌走 realtime CFR；任意 miss/异常/超时都回退 PokerFate 本地。

## 本次复制进项目的 solver

`pf_solver` 已复制到本项目内：

```text
pokerfate/solver/pf_solver/
  Cargo.toml
  Cargo.lock
  pyproject.toml
  build.rs
  src/lib.rs
```

运行时不依赖 `/Users/zhangmingli/dev-tool/pf_offline_book`，也不从 venv 里的同名包隐式 import。Python 侧默认只从本项目的 `pokerfate/solver/pf_solver/target/release/` 加载 `libpf_solver.dylib` / `libpf_solver.so` / `pf_solver.pyd`；没有本地产物就直接 fallback 到 PokerFate 本地决策。

本地构建：

```bash
cd pokerfate/solver/pf_solver
cargo build --release
```

`build.rs` 会为 PyO3 extension module 注入 macOS 所需链接参数。

## 离线翻牌书

`pf_offline_book` 的 v2 离线翻牌书已复制进本项目：

```text
pokerfate/data/flop_book/v2/
  meta.json
  flop_iso_map.json
  flop_clusters.json
  BTNvBB_srp100.db
  COvBB_srp100.db
  MPvBB_srp100.db
  SBvBB_srp100.db
  UTGvBB_srp100.db
```

运行时由 `pokerfate/decision/flop_book.py` 读取本项目内的数据，不引用外部目录。读取路径保持简单：`sqlite3` 查节点、`zlib` 解压、`numpy.frombuffer(dtype="<u2")` 还原 `1176 x action_count` 策略矩阵。

当前翻牌书覆盖 v2 的 heads-up single-raised-pot 100bb 场景：`UTGvBB_srp100`、`MPvBB_srp100`、`COvBB_srp100`、`BTNvBB_srp100`、`SBvBB_srp100`。

查表前会校验本项目能还原的条件：flop、3 张公共牌、HU active、单次翻前 raise、defender call、位置组合匹配、底池接近书的标准底池、有效后手在 `40bb..170bb`。动作前缀按 OOP/IP 还原，真实 flop 尺寸只在足够接近书菜单时映射到 `b33/b100/r2.7x/ai`；偏离过大直接 book miss 回退本地。

## 决策链路

`PokerFateAPI.request_action()` 的顺序：

1. `DECISION_ENGINE=cfr` 且当前是 flop 时，先调用 `FlopBookDecisionEngine`。
2. `DECISION_ENGINE=realtime_cfr/cfr` 且当前是 turn/river 时，调用 `RealtimeCFRDecisionEngine`。
3. CFR 成功返回 `Action` 时，直接接入主决策结果，并把本地 bot 的已采纳动作记忆同步上。
4. CFR 失败、超时、solver 缺失、非 heads-up、range 不可用、节点无法定位、翻牌书 miss 时，记录 fallback 原因并继续走 PokerFate 本地。
5. g5 模式仍走原来的 g5 active/shadow 路径；`realtime_cfr/cfr` 不触发 g5 shadow。

## realtime CFR 输入

当前实现尽量喂项目内能拿到的最好信息：

- 公共牌：turn 4 张、river 5 张。
- 位置：用 `GameState.is_ip()` 划分 OOP/IP。
- 底池：使用当前街开始底池 `street_start_pot`，避免把本街下注重复计入 solver 起点。
- 有效后手：按 OOP/IP 当前剩余栈加本街已投入计算。
- 当前街真实动作前缀：从 `GameState.action_history` 提取 check/call/bet/raise，并把真实下注尺寸注入 solver menu。
- 对手范围：使用 Range V2 的 1326 combo 权重，去除 hero 手牌和公共牌 blockers 后转成 `postflop-solver` range 字符串。
- Hero 范围：使用 v3 hero reach range，按翻前位置/防守场景 + hero 前街动作过滤生成 1326 combo 权重。hero 侧只用公共牌做 blocker，不用真实底牌删掉其它 hero combos；真实底牌只用于从 solver 输出策略表里取当前 combo 的行动。range 生成失败时才 fallback 到当前真实手牌精确 combo。
- 默认菜单：flop `33/100`；turn `33/75/150`；river `33/66/100/150`；转牌求解树内未来 river 粗化为 `66/150`；raise `2.2x/3.0x`。真实已发生尺寸会额外注入，保证能定位到当前节点。

## solver 输出扩展

Rust 绑定现在支持 `include_evs=true`，默认开启。除当前节点策略外，每个决策节点还会导出：

- `evs`：当前行动方每个 action / combo 的动作 EV，shape 与 `strategy` 一致。
- `weights`：当前行动方在该节点的归一化 reach weights，用于把对手整段 range 的 response strategy 聚合成真实节点频率。
- `opponent_evs`：当前行动方选择每个 action 之后，对手每个 combo 的 EV。对 hero 下一层的 villain response 节点来说，这个字段就是 villain 每个 response 后 hero 当前 combo 的 EV。
- `opponent_num_hands`：`opponent_evs` 的手牌维度长度。

这些值是 solver 内部已经有的求解副产品；导出本身不新增求解迭代，只增加一次树遍历和 JSON 体积。

## 剥削层

当前 CFR 接入不随机抽样混合策略。没有 EV 的翻牌书先取当前 combo 策略概率最高的动作；有 EV 的 turn/river 先取当前 combo 的 action EV，再经剥削层重算/约束后选最终 EV 最高的动作。`selected_prob` 只用于诊断“这个动作在基线/最终策略里有多高频”，不是随机采样结果。

realtime CFR 仍以均衡策略为锚点，不直接用画像替代 solver：

1. 先取当前节点 hero combo 的 GTO action EV。
2. 对 hero 每个 action，找到下一层 villain 节点，读取 villain `Fold/Call/Raise/...` 每个 response 后 hero combo 的 EV。
3. 用 villain 节点的 `weights + strategy` 聚合出均衡 response 频率。
4. 用项目内画像和当前手线路证据修正 response 频率，再重算该 hero action 的 exploit EV。
5. 最终 action EV = `(1 - confidence) * GTO_EV + confidence * exploit_EV`，并用 GTO leash 限制大幅偏离。
6. 安全阀：没有真实偏置信号时不启用剥削；候选动作的 GTO EV 低于最优 GTO EV 太多时触发 `gto_ev_floor`；防守端 fold 概率过高且非 fold EV 接近时触发 `defense_mdf` 软阀；river 大注/all-in 会额外检查 adjusted fold equity 和 risk margin。

画像来源是 `PokerBot._build_player_profile()`，也就是既有的 OpponentModel + Range V2 统计：VPIP/PFR/AF、fold to cbet、WTSD、street AFq、river fold/bet 等。连续剥削信号来自 `OpponentModel.exploit_adjustments()`：`value_ag_scale`、`bluff_ag_scale`、`river_bluff_likely`、`river_bet_rare` 等。

线路证据完全来自当前手 `GameState.action_history`，不依赖新增统计字段。realtime CFR 会统计 villain 是否在 flop/turn call 过 hero 下注、是否一路 call 到 river、当前候选下注的 pot ratio 和 risk bb。river 前对手已经连续 call 时，策略层会降低对手面对 hero 大注/all-in 的 fold response、提高 call response，并用修正后的 response EV 重新排序动作。这不是硬性收缩：如果 solver 的 response EV 显示对手 call 后 hero 仍明显赚钱，value 大注仍可被选中；被降权的是依赖虚高 fold equity 的大注 bluff。

数据不够时不再使用对手类型标签。CFR 决策层使用 `opponent_numeric_prior` 的数值先验：

- 从本项目 `pokerfate/data/local_models/opponents_all_bb.json` 读取统一玩家库，离线构造 pool baseline 和软 KNN 先验。
- 特征是连续数值：VPIP/PFR/gap、AF、WTSD/WMSD、street AFq、river bet/fold、fold to cbet、bluff win rate、3bet/fold to 3bet 等。
- 每个特征按自己的机会样本做 shrink：`rate = player * reliability + (1 - reliability) * (KNN/pool)`；没有机会样本的字段不会被当成 0。
- 最终输出不是玩家类型，而是 `fold_bias/sticky_bias/raise_bias` 以及 `sticky/fold_lean/underbluff/pressure` 连续分。
- `_exploit_confidence()` 按手数、街位样本、数值特征可靠度限幅；小样本仍然只轻微影响 response 频率。
- 如果没有画像但有当前手强线路证据，例如 villain flop/turn 连续 call 后到 river，线路先验会立刻生效，不需要等新增样本收集。
- 因此小样本只会轻微影响 response 频率和最终 EV，不会把一个 solver 均衡高 EV 动作硬改成画像动作。

翻牌离线书的剥削层更保守：v2 book 只存当前 combo 的策略矩阵，不存 action EV 或下一层对手 response EV。因此 flop book 命中时不能像 turn/river 那样做 EV 重算，只能在 GTO 概率上做数值先验概率偏置，诊断字段为 `probability_bias_no_evs`。如果没有实际画像/群体先验信号，即使有默认置信度也不标记为已剥削。要让翻牌也走 EV 级剥削，需要未来离线书额外导出 action EV / response EV。

## fallback 条件

以下情况都会自动回退 PokerFate 本地：

- realtime CFR 当前不是 turn/river。
- `cfr` 的 flop spot 不在离线书覆盖范围：非 HU、非 SRP、位置组合缺失、底池/后手偏离过大、动作路径无法映射、hero combo 不在书范围。
- 非 heads-up active players。
- hero 手牌或公共牌不完整。
- Range V2 未启用或范围为空。
- 当前街动作历史无法按 OOP/IP 顺序还原。
- solver 动态库不存在、加载失败、求解异常或 10 秒超时。
- solver 返回结果里找不到当前节点或 hero combo 策略。

## 运行诊断

`last_decision_diagnostics` 在 realtime CFR 命中时包含：

- `decision_source = "realtime_cfr"`
- `realtime_cfr.status`
- `selected_label` / `selected_prob`
- `action_evs_bb`
- `exploit.enabled` / `exploit.used` / `exploit.confidence`
- `exploit.gto_action_evs_bb`
- `exploit.adjusted_action_evs_bb`
- `exploit.final_action_evs_bb`
- `exploit.response_summaries`
- `exploit.numeric_prior`
- `exploit.line_context`
- `exploit.safety.river_aggression_risk`
- `exploitability_pct`
- `node_path`
- `range_counts`
- `elapsed_ms`

日志中的 reasoning 会显示类似：

```text
realtime_cfr decision | Raise(90)@80% | expl=0.42% | t=1.8s | path=r:Bet(60)
```

`last_decision_diagnostics` 在 flop book 命中时包含：

- `decision_source = "flop_book"`
- `flop_book.status`
- `scenario`
- `selected_label` / `selected_prob`
- `strategy`
- `node_path`
- `flop_canonical` / `flop_representative`
- `exploit.mode = "probability_bias_no_evs"`
- `elapsed_ms`

日志中的 reasoning 会显示类似：

```text
flop_book decision | BTNvBB_srp100 | x@100% | path=r | t=1ms
```
