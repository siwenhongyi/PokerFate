# Realtime CFR 接入总结

## DECISION_ENGINE 模式

未设置时默认 `cfr`（实战默认；下列环境变量未设置时同样取实战值：`PF_BUCKET_ML=lgbm`（2026-11-11 重建的模型，见 docs/range_v2_bucket_ml.md）、
`PF_POSTFLOP_PROFIT_EXPAND_V1=1`、`REALTIME_CFR_TIMEOUT_SEC=10`，headless 入口还会自动等价设置
`PYTHONUNBUFFERED=1`。hero 胜率 ML、河牌相对 ML、运行时 gamma/theta 公式参数、CEC 校准、showdown 学习器等层已于 2026-11-11 删除，`PF_EQUITY_ML` / `PF_RIVER_RELATIVE_ML` / `PF_RUNTIME_RANGE_CALIBRATION` / `PF_BUCKET_CALIBRATION` 不再存在，见 docs/range_v2_bucket_ml.md）。

- `local` 或非法值：PokerFate 纯本地决策。
- `g5_all`：翻前、翻后都由 g5 接管，PokerFate 只做旁路对照。
- `g5`：翻前 PokerFate 查表/本地，翻后 g5 接管；翻前仍同步 g5 shadow，保证翻后状态连续。
- `cfr`：翻前 PokerFate 本地；翻牌由独立开关决定是否查离线 CFR 书；转牌、河牌实时求解；任意 miss/异常/超时都回退 PokerFate 本地。

`PF_CFR_FLOP_BOOK_ENABLED` 是启动时读取的独立开关，默认 `1`：

- `DECISION_ENGINE=cfr PF_CFR_FLOP_BOOK_ENABLED=1`：翻牌优先查书。
- `DECISION_ENGINE=cfr PF_CFR_FLOP_BOOK_ENABLED=0`：翻牌走本地，不加载翻牌书；转牌、河牌照常实时求解。

关闭值可用 `0/false/no/off`，开启值可用 `1/true/yes/on`。API 调用方可通过
`cfr_flop_book_enabled` 显式覆盖环境变量。启动日志 `session_config.env` 保留环境原值，
`session_config.resolved.PF_CFR_FLOP_BOOK_ENABLED` 记录实际解析后的布尔值（未设环境变量时也记录）。
`decision_engine_enabled.flop_book` 和状态接口的 `flop_book` 表示是否实际启用了书；
`flop_book_requested` 表示开关值。运行时切换决策引擎会再次记录 `session_config`。
顶层模式只支持 `local/g5/g5_all/cfr`，不提供旧模式的兼容别名。

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

翻牌书为 v3（2026-11-12 接入），由 `/Users/zhangmingli/dev-tool/pf_offline_book` 离线计算、严格校验（2000/2000 任务，可剥削度 ≤ 0.5% 起始底池）并打包，实体文件复制在本项目内：

```text
pokerfate/data/flop_book/v3/
  meta.json            # book_version=v3, schema_version=3, complete=true
  flop_iso_map.json
  flop_clusters.json
  {UTG,MP,CO,BTN,SB}vBB_srp50.db
  {UTG,MP,CO,BTN,SB}vBB_srp100.db
```

求解条件：9% 不封顶抽水；UTG/MP/SB 开池 4bb、CO/BTN 开池 3.5bb；翻牌起始底池 8.5 / 7.5 / 8bb；50bb 与 100bb 两档翻前有效筹码（翻牌剩余 46/46.5 与 96/96.5bb）；翻牌下注 33/50/67/100%，加注 2x/4x；范围取自当时的翻前策略（`runtime_preflop_v3`）。

运行时由 `pokerfate/decision/flop_book.py` 读取本项目内的数据，不引用外部目录；`PF_FLOP_BOOK_DIR` 只用于离线试验另一份同格式的书。读取器只接受 `schema_version == 3` 且 `complete` 的书，其他格式（包括已归档的 v2）直接报 `book_schema_unsupported`，初始化失败时整个 `cfr` 模式回落 `local`。读取路径保持简单：`sqlite3` 查节点、`zlib` 解压、`numpy.frombuffer(dtype="<u2")` 还原 `1176 x action_count` 策略矩阵。sqlite 连接以 `check_same_thread=False` 打开，因为决策跑在 asyncio 线程池里。

覆盖范围仍是 heads-up single-raised-pot：UTG/MP/CO/BTN/SB 开池对 BB 防守。多人、limp 底池、3-bet 底池和其他位置组合不查书。

选档：同一位置场景内按翻牌开始时的剩余有效筹码 `E = min(双方剩余筹码 + 本街已投入) / bb` 对两档书的相对误差取最小的一档；`E` 须在 `40bb..170bb` 内，且相对所选书的偏差 ≤ 35%，否则 `book_stack_out_of_range` / `book_stack_mismatch`。底池与书的标准底池偏差 > 35% 时 `book_pot_mismatch`（例如对手最小加注开池的 4.5bb 底池）。

选动作：书没有 EV，取最可能的动作，但先比动作类别再选尺度（`_select_strategy_action`）——弃牌、过牌、跟注各自与“下注+加注+全下”的合计频率比较，进攻类胜出后再取其中频率最高的尺度。v3 有四个下注尺度，若直接取单个最大标签，书下注 60% 但分散在四个尺度上的手牌会被打成过牌；2026-11-12 日志回放里 v3 命中的 64 个决策，书的平均进攻频率 0.44，单标签取最大只有 0.36。画像微调仍先作用在各标签概率上。

升级与回退流程见 [离线工程运行手册](/Users/zhangmingli/dev-tool/pf_offline_book/docs/RUN.md)：旧 v2 书归档在 `pf_offline_book/archive/`，本项目内不保留旧书或旧格式兼容分支。`analysis/flop_book_replay.py` 可把日志里的翻牌决策点按任意一份书重放（不跑求解器），用于比较命中率和回退原因。

查表前会校验本项目能还原的条件：flop、3 张公共牌、HU active、单次翻前 raise、defender call、位置组合匹配、底池接近书的标准底池、有效后手与所选档位匹配。动作前缀按 OOP/IP 还原：真实下注额除以书中对应节点底池后取最近的 `b33/b50/b67/b100`（差值 ≤ 50 个百分点且相对误差 ≤ 60%），真实加注倍数按对数距离取最近的 `r2.0x/r4.0x`（相对误差 ≤ 50%），全下映射到 `ai`；偏离过大直接 book miss 回退本地。

## 决策链路

`PokerFateAPI.request_action()` 的顺序：

1. `DECISION_ENGINE=cfr`、翻牌书开关开启且当前是 flop 时，先调用 `FlopBookDecisionEngine`；开关关闭则翻牌走本地。
2. `DECISION_ENGINE=cfr` 且当前是 turn/river 时，调用 `RealtimeCFRDecisionEngine`。
3. CFR 成功返回 `Action` 时，直接接入主决策结果，并把本地 bot 的已采纳动作记忆同步上。
4. CFR 失败、超时、solver 缺失、非 heads-up、range 不可用、节点无法定位、翻牌书 miss 时，记录 fallback 原因并继续走 PokerFate 本地。
5. g5 模式仍走原来的 g5 active/shadow 路径；`cfr` 不触发 g5 shadow。

## realtime CFR 输入

当前实现尽量喂项目内能拿到的最好信息：

- 公共牌：turn 4 张、river 5 张。
- 位置：用 `GameState.is_ip()` 划分 OOP/IP。
- 底池：使用当前街开始底池 `street_start_pot`，避免把本街下注重复计入 solver 起点。
- 有效后手：按 OOP/IP 当前剩余栈加本街已投入计算。
- 当前街真实动作前缀：从 `GameState.action_history` 提取 check/call/bet/raise，并把真实下注尺寸注入 solver menu。
- 对手范围：使用 Range V2 的 1326 combo 权重，但取的是**本街发牌时的快照**（`api.deal_board` 后保存），不是对手本街行动之后的后验。对手本街的 bet/raise/call 已经在 solver 树的动作前缀里，再喂后验等于把同一个动作算两遍（回放实测会把对手范围压得过紧、hero 多弃牌）。去除 hero 手牌和公共牌 blockers 后转成 `postflop-solver` range 字符串。
- Hero 范围：`v3/hero_range.combo_weights`。翻前基础范围按 hero 实际走过的线取（`describe_preflop_line`）：RFI/iso → 位置 RFI 表；3bet → 3bet 价值+诈唬池；4bet → 4bet 池；BB 跟开池 → 对应开池位置的 BB 防守表；非 BB 平跟 → 平跟防守表；跟 3bet → 位置 3bet-call 表；limp → limp-behind 池；BB 免费看牌 → 全范围。前街过滤优先用当时做决策的引擎输出：翻牌书 / realtime CFR 都会导出“当前节点所有 hero combo 选中所选动作的概率”（`last_hero_reach_update`），下一街直接乘上去；只有本地引擎做的决策才退回 bucket 频率表（含 call 的续牌频率）。hero 侧只用公共牌做 blocker，真实底牌只用于取当前 combo 的行动。
- 抽水：`core.config.RAKE_RATE=0.09`、不封顶，以 `rake_cap=10^9` 筹码传给 solver（postflop-solver 按 `min(rate×pot, cap)` 计费，cap=0 等于不抽水）。
- 默认菜单：flop `33/100`；turn `33/75/150`；river `33/66/100/150`；转牌求解树内未来 river 粗化为 `66/150`；raise `2.2x/3.0x`。真实已发生尺寸会额外注入，保证能定位到当前节点。

## solver 输出扩展

Rust 绑定现在支持 `include_evs=true`，默认开启。除当前节点策略外，每个决策节点还会导出：

- `evs`：当前行动方每个 action / combo 的动作 EV，shape 与 `strategy` 一致。
- `weights`：当前行动方在该节点的归一化 reach weights，用于把对手整段 range 的 response strategy 聚合成真实节点频率。
- `opponent_evs`：当前行动方选择每个 action 之后，对手每个 combo 的 EV。对 hero 下一层的 villain response 节点来说，这个字段就是 villain 每个 response 后 hero 当前 combo 的 EV。
- `opponent_num_hands`：`opponent_evs` 的手牌维度长度。

这些值是 solver 内部已经有的求解副产品；导出本身不新增求解迭代，只增加一次树遍历和 JSON 体积。

## 剥削层

动作选择：没有 EV 的翻牌书取当前 combo 最可能的动作（先比动作类别、再选尺度，见上文“离线翻牌书”）；有 EV 的 turn/river 先取当前 combo 的 action EV，经剥削层重算/约束后，在“最终 EV 与最优差距 ≤ max(0.15bb, 1% 底池)”的动作集合里按均衡频率抽样（`_sample_near_ev`，随机数来自 `api._next_decision_seed` 的可复现种子；无种子时取 EV 最高）。这样 EV 几乎相等的动作不会永远只出一个，诊断里的 `mixed_sample` 记录候选与概率。`selected_prob` 仍是该动作在基线策略里的频率。

实战注意：线上 bridge 创建 `PokerFateAPI` 时不传 `decision_seed`，`_next_decision_seed` 返回空，所以实战里 `_sample_near_ev` 恒取 EV 最高、不做混合（2026-11-09..18 日志里 2,889 个 solver 决策没有一条 `mixed_sample`）；只有传了种子的回放才会抽样。

realtime CFR 仍以均衡策略为锚点，不直接用画像替代 solver：

1. 先取当前节点 hero combo 的 GTO action EV。
2. 对 hero 每个 action，找到下一层 villain 节点，读取 villain `Fold/Call/Raise/...` 每个 response 后 hero combo 的值。solver 报的这个值仍把 hero 这次新投入的筹码算作他的（下注后对手弃牌 = 底池 + 这笔下注），而动作本身的 EV 是扣掉这笔投入的净值，所以要先减去新投入再用。2026-11-19 之前两者被直接相比，所有下注和加注都过不了一致性检查，实战里只有过牌的 response 被重算过，下注一直走的是第 7 步的手写修正。
3. 用 villain 节点的 `weights + strategy` 聚合出均衡 response 频率。
4. 对手实际会怎么回应，用拟合的回应模型（`pokerfate/decision/response_model.py`，2026-11-19）：按回应类别（面对下注：弃 / 跟 / 加注；hero 过牌后：过牌 / 下注）给出频率，特征是下注尺度、对手自己这手牌的线路、玩家特征（范围层的 known / tight / aggressive）和范围层给他的牌力分布；类别内部各尺度的比例沿用 solver。该动作的 exploit EV = GTO EV + Σ(拟合频率 − 均衡频率) × 该 response 后的值。河牌上“对手跟注”后的值还要按新的跟注范围重算：跟注变少时先去掉他最弱的跟注牌，变多时先加入他弃牌里最强的牌（`shifted_call_win_share`，用 solver 自己的逐手策略和权重精确算；重建的均衡胜率与 solver 的值相差超过 0.05 时不改）。人机、没有模型的街、范围层没给分布时不做调整，沿用均衡频率。模型由 `scripts/fit_response_model.py` 从决策日志拟合（单挑、转牌和河牌、真人），特征只在 `response_features` 一处计算，拟合和实战共用；`PF_RESPONSE_MODEL_PATH` 可指向候选文件，`off` 关闭。原来手写的回应系数（画像偏置、线路乘子、范围乘子）已删除。
5. 最终 action EV = `(1 - confidence) * GTO_EV + confidence * exploit_EV`。GTO leash：GTO EV 低于最优超过 `(0.6 + 2×confidence) × max(1, pot/20)` bb 的动作直接从候选集中剔除（旧版只是把它夹到“略低于最优”，后续 tie-break 仍可能选中它，回放里出现过 solver 100% 弃牌却选了 raise 的案例）。
6. 安全阀：没有真实偏置信号时不启用剥削；候选动作的 GTO EV 低于最优 GTO EV 太多时触发 `gto_ev_floor`；river 大注/all-in 会额外检查 adjusted fold equity 和 risk margin。旧的逐 combo `defense_mdf` 阀已删除：MDF 是范围层面的性质，solver 均衡本身已满足，按单个 combo 再套 MDF 概念上不成立。
7. 跟注和弃牌后面没有对手决策，走 `_direct_exploit_delta`（常数按 `pot/10`、限 0.5–4 缩放）。下注、加注、过牌如果没有可用的 response 值，保持 solver 的 EV，不做修正。风险守卫（第 6 步）目前不读对手的 response，和它们一直以来在实战里的状态一致，等单独评估后再定。
8. （2026-11-18 已删除）河牌价值下注下限 `value_bet_floor`。2026-11-12 上线，用来把“solver 多数下注、剥削层选了过牌”的河牌成手牌改回 solver 的下注（条件：河牌、选中 Check、solver 对这手牌下注 ≥ 0.50、tracker 摊牌价值 ≥ 0.66，尺度 ≤ 1 倍底池）。上线后 12,371 手里实际触发 77 次：改成的下注在河牌这条街比直接摊牌 −2.3 ± 4.4bb/次（68 次），同条件过牌 −0.8 ± 2.4bb/次（39 次），折合 −0.8 ± 2.7 bb/100（上线时的估计是 +1.9 ± 1.9），每次决定的标准差 18.4bb 对 7.6bb。按上线时定的停止规则（下注线不再胜过过牌线就关）删除，`PF_CFR_VALUE_BET_FLOOR*` 四个环境变量不再读取。评估脚本、说明和回滚补丁见 `docs/candidates/value_bet_floor_removal_2026-11-18/`。
9. 便宜跟注守卫的 tracker 证据路径（2026-11-12）。`overvalue_cheap_call_guard` 原本只在对手先验判定“高估牌力”且 solver 的 EV 差在约 2bb 内时把河牌弃牌改成跟注。现在当 tracker 摊牌价值 ≥ `PF_CFR_CHEAP_CALL_MIN_SHOWDOWN`（0.45）时也算证据，并把容差放宽到 `PF_CFR_CHEAP_CALL_POT_TOLERANCE`（0.06）× 底池；其余门槛不变（河牌、底池赔率 ≤ 25%、绝对牌型两对以上、Call 未被安全阀折扣）。任一参数设 0 即恢复旧行为。样本很小（9000 手里 2 次翻转），按日志继续观察。

上述两个值（`PF_CFR_CHEAP_CALL_*`）在 `RealtimeCFROptions` 构造时读取环境变量，生效值记录在 `session_config.resolved`。

画像来源是 `PokerBot._build_player_profile()`，也就是既有的 OpponentModel + Range V2 统计：VPIP/PFR/AF、fold to cbet、WTSD、street AFq、river fold/bet 等。连续剥削信号来自 `OpponentModel.exploit_adjustments()`：`value_ag_scale`、`bluff_ag_scale`、`river_bluff_likely`、`river_bet_rare` 等。

线路证据完全来自当前手 `GameState.action_history`，不依赖新增统计字段。realtime CFR 会统计 villain 是否在 flop/turn call 过 hero 下注、是否一路 call 到 river、当前候选下注的 pot ratio 和 risk bb。river 前对手已经连续 call 时，策略层会降低对手面对 hero 大注/all-in 的 fold response、提高 call response，并用修正后的 response EV 重新排序动作。这不是硬性收缩：如果 solver 的 response EV 显示对手 call 后 hero 仍明显赚钱，value 大注仍可被选中；被降权的是依赖虚高 fold equity 的大注 bluff。

数据不够时不再使用对手类型标签。CFR 决策层使用 `opponent_numeric_prior` 的数值先验：

- 从本项目 `pokerfate/data/local_models/opponents.json` 读取统一玩家库，离线构造 pool baseline 和软 KNN 先验。
- 特征是连续数值：VPIP/PFR/gap、AF、WTSD/WMSD、street AFq、river bet/fold、fold to cbet、bluff win rate、3bet/fold to 3bet 等。
- 每个特征按自己的机会样本做 shrink：`rate = player * reliability + (1 - reliability) * (KNN/pool)`；没有机会样本的字段不会被当成 0。
- 最终输出不是玩家类型，而是 `fold_bias/sticky_bias/raise_bias` 以及 `sticky/fold_lean/underbluff/pressure` 连续分。
- `_exploit_confidence()` 按手数、街位样本、数值特征可靠度限幅；小样本仍然只轻微影响 response 频率。
- 如果没有画像但有当前手强线路证据，例如 villain flop/turn 连续 call 后到 river，线路先验会立刻生效，不需要等新增样本收集。
- 因此小样本只会轻微影响 response 频率和最终 EV，不会把一个 solver 均衡高 EV 动作硬改成画像动作。

翻牌离线书的剥削层更保守：书只存当前 combo 的策略矩阵，不存 action EV 或下一层对手 response EV。因此 flop book 命中时不能像 turn/river 那样做 EV 重算，只能在 GTO 概率上做数值先验概率偏置，诊断字段为 `probability_bias_no_evs`。如果没有实际画像/群体先验信号，即使有默认置信度也不标记为已剥削。要让翻牌也走 EV 级剥削，需要未来离线书额外导出 action EV / response EV。

## fallback 条件

以下情况都会自动回退 PokerFate 本地：

- realtime CFR 当前不是 turn/river。
- `cfr` 的 flop spot 不在离线书覆盖范围：非 HU、非 SRP、位置组合缺失、底池/后手偏离过大、动作路径无法映射、hero combo 不在书范围。
- 非 heads-up active players。
- hero 手牌或公共牌不完整。
- Range V2 未启用或范围为空。
- 当前街动作历史无法按 OOP/IP 顺序还原。
- 有效后手不足 0.1bb（solver 筹码取整后为 0，本就只能 check/call）。
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
- `exploit.response_summaries`（每个动作：`eq` / `adj` 逐 response 频率，`response` 里是按类别的均衡频率、拟合频率或未用模型的原因，河牌下注另有 `call_range`）；决策日志里压缩为 `realtime_cfr.responses`：`eq` / `fit`（或 `why`）/ `size` / `call_range`，配合对手随后的实际动作用来校验回应模型
- `exploit.numeric_prior`
- `exploit.line_context`
- `exploit.safety.river_aggression_risk`
- `exploit.safety.overvalue_cheap_call_guard`（含 `evidence`：`overvalue` / `tracker` / `overvalue+tracker`）
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

## G5 真实历史旁路

`PF_G5_SHADOW_ENABLED=1` 默认开启，在 `DECISION_ENGINE=cfr` / `local` 下独立评估。
设为 `0` 可关闭；更改后下次启动生效。它不改变主决策路由。

每个真实决策点冻结手牌、牌面、此前的动作和本手开始时的 G5 对手模型，
后台 worker 在新建的游戏状态中重放到该节点。实战历史来自服务器 ActionBRC，
包括自己最终执行的动作；G5 建议不会被执行或写入下一节点的历史，建议弃牌后
仍继续评估后续真实节点。直接调用 PokerFateAPI 时默认使用 API 已应用的动作；
外部接入可设置 `g5_shadow_server_actions=True` 并调用 `record_g5_actual_action`。

`session_config.resolved` 记录开关、`G5_SHADOW_ACTIVE`、`G5_SHADOW_MODE=real_history_v1`
和历史来源。JSONL 日志中：

- `decision.decision_id`：主决策对应的唯一节点 ID。
- `g5_shadow_decision`：相同 ID 的主建议、local 对照（如果有）、G5 建议/EV、
  原始手号、牌面/筹码、历史长度/哈希、耗时和成功/失败/跳过状态。
- `g5_shadow_execution`：相同 ID 的服务器最终执行动作和实际金额。

旁路异步完成，按 `decision_id` 关联，不能按日志相邻位置关联。
队列满、缺少自己动作确认、重连丢失历史、非标准盲位/补盲或状态校验失败均显式记录；
这些节点不能算作有效建议样本。G5 RPC 超时/退出后会停止启动新的 worker，
后续节点保留错误记录，重启进程后恢复。旁路不接收本手最终输赢或未来牌面。

这能支持同点建议、覆盖率和故障率对照；没有执行过的 G5 建议仍没有真实收益，
不能把主引擎的实际输赢直接算作 G5 的反事实盈亏。原有 `g5` 主引擎模式的旧
`G5_SHADOW_DECISIONS` 属于另一条历史逻辑，评估时只取 `real_history_v1`。
