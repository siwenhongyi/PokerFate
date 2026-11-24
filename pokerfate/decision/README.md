# 决策引擎与翻牌书

本文说明当前决策路径、运行配置和模型接入；外部调用契约见 [API 接入](../INTEGRATION.md)，
bot 启停与日志位置见[项目首页](../../README.md)。
对手历史、人机标记的来源及学习样本筛选见 [对手信息与牌桌管理](../../pf_intercept/bot/README.md)。

## 引擎与开关

| 设置 | 行为 |
|---|---|
| `DECISION_ENGINE=cfr`（默认） | 翻前规则引擎；翻牌查书；转牌、河牌单挑实时 CFR |
| `DECISION_ENGINE=rule_engine` | 所有街都使用规则引擎 |
| `PF_CFR_FLOP_BOOK_ENABLED=0` | CFR 模式下关闭翻牌书，翻牌用规则引擎；转河实时求解保持开启 |

顶层模式只有 `cfr` 和 `rule_engine`。启动时遇到未知名字会记 `decision_engine_unknown` 并使用 `cfr`；
运行时的 `set_decision_engine()` 对未知名字报错。翻牌书开关默认开启，支持 `0/false/no/off` 和 `1/true/yes/on`。
API 的 `decision_engine`、`cfr_flop_book_enabled` 参数可显式覆盖环境变量。

常用默认值：`PF_BUCKET_ML=lgbm`、`PF_POSTFLOP_PROFIT_EXPAND_V1=1`、`REALTIME_CFR_TIMEOUT_SEC=10`。
两种游戏接入模式共用这些策略环境变量。

启动日志 `session_config.env` 记录显式环境变量，`session_config.resolved` 记录实际生效值。
`decision_engine_enabled` 和 `decision_engine_status()` 的 `flop_book_requested` 是开关值，`flop_book` 是实际启用状态。

### 模型文件

随仓库提供的文件在 `pokerfate/data/`，运行中累计的在 `local/models/`（不进 Git）。
下面的环境变量都用于试验候选文件，默认不用设置。

| 文件 | 作用 | 换文件 / 关闭 |
|---|---|---|
| `pokerfate/data/runtime_calibration/formula_fit.json` | 范围层的动作似然（翻前和翻后） | `PF_FORMULA_FIT_PATH=<文件>`；`off` 时动作不再改变范围 |
| `pokerfate/data/runtime_calibration/runtime_lgbm_bucket_model.json` | 范围层的 LightGBM 桶校准 | `PF_BUCKET_ML_MODEL_PATH=<文件>`；`PF_BUCKET_ML=off` 关闭 |
| `pokerfate/data/runtime_calibration/response_model.json` | 实时 CFR 用的对手回应模型 | `PF_RESPONSE_MODEL_PATH=<文件>` 或 `off` |
| `pokerfate/data/runtime_calibration/pre_action_fit.json` | 预选动作的读数 | `PF_PRE_ACTION=<文件>` 或 `off` |
| `pokerfate/data/flop_book/v3/` | 翻牌书 | `PF_FLOP_BOOK_DIR=<目录>`；`PF_CFR_FLOP_BOOK_ENABLED=0` 关闭 |
| `pokerfate/data/gto/` | 翻前图表 `greenline.json`、`pokergto.json` | — |
| `local/models/opponents.json` | 对手统计和 hero 胜率校准，运行中累计 | API 的 `autosave_path` |
| `local/models/robots.json` | 人机名单，运行中累计 | `PF_ROBOT_REGISTRY=<文件>` |
| `local/models/range_v2_empirical_model.json` | 范围层的人群先验，由脚本生成；缺失时用代码里的固定默认值 | `PF_EMPIRICAL_MODEL_PATH=<文件>` |

这些文件怎么重新生成见[离线脚本](../../scripts/README.md)。

## 决策顺序与回退

`PokerFateAPI.request_action()` 按街道调度：

1. 翻前直接交给规则引擎。
2. 翻牌书开启时尝试 `FlopBookDecisionEngine`；未命中则用规则引擎。
3. 转牌、河牌尝试 `RealtimeCFRDecisionEngine`；失败则用规则引擎。
4. 采纳 CFR 动作后，同步规则引擎的行动记忆，供后续决策使用。

多人、范围不可用、节点无法定位、缺少 solver 或超时等，均会记录回退原因。
初始化引擎时如果书文件损坏或格式不符，当前实现会把整个 CFR 模式回退到 `rule_engine`；
普通对局中的书 miss 只回退该次决策。应检查实际状态，不能仅凭启动参数判断 CFR 已工作。

## 规则引擎

规则引擎是 [poker_bot.py](../bot/poker_bot.py) 的 `PokerBot`。它负责翻前、所有多人底池，
以及翻牌书和实时 CFR 没有接住的决策。

- **翻前**（[preflop.py](../strategy/preflop.py)）：以 Greenline 图表为主，遇到混合动作时参考 PokerGTO 图表的频率；
  在此基础上按位置、筹码深度、对手和桌面情况调整。部分会结束下注的跟注按实测的对手继续比例定价。
- **翻后**（[strategy/v3/](../strategy/v3/)）：按“目的”投票。没人下注时用主动方的目的（持续下注、价值下注、诈唬、过牌控池等），
  面对下注时用防守方的目的（抓诈跟注、听牌跟注、价值加注、弃牌等）。每个目的按牌力、牌面和范围胜率给出候选动作和权重，
  对手指标按连续的倾向指数调整权重（[exploit.py](../strategy/v3/exploit.py)），不按玩家类型标签查表。
  选中的动作还要经过 EV 检查和几道守卫（筹码投入、诈唬比例等），不通过就改成更保守的动作。
  面对全下时只比较胜率和赔率。
- **胜率**：对手范围来自下面的范围层，按范围加权抽样计算 hero 胜率，
  再用 hero 胜率校准修正：它按牌力桶、街、对手人数累计“预测胜率”和“摊牌实际胜率”的差，保存在 `opponents.json`。

## 范围层

范围层（[range_v2/](../strategy/range_v2/)）为每个对手维护 1326 个起手组合的概率，规则引擎和实时 CFR 共用。
每手从均匀分布开始；每看到一个动作，就乘上该动作的似然（翻前按起手强度分档，翻后按牌力桶），
再混入一小部分均匀分布，保证没有哪手牌被完全排除。

- **动作似然**：`formula_fit.json`，用摊牌亮出的牌和无人跟注时服务器给出的牌型拟合，不是手写的表。
- **桶校准**：LightGBM 模型在似然给出的牌力桶分布上再校准一次（`PF_BUCKET_ML=lgbm`，需要安装 `lightgbm`）。
- **预选动作**：服务器会告诉所有人某个座位是否预先点了动作。预先点“过牌”的玩家多半已经放弃，
  范围和弃牌概率会据此调整，并有专门的诈唬目的利用它（[pre_action.py](../strategy/pre_action.py)）。
- **人机**：已证实的人机照常对局，但不进入任何学习；按真人数据拟合的调整对它们不使用。

上层模型都在下层的输出上拟合：换了动作似然，就要重新提取样本、重训桶校准，再重填 hero 胜率校准，
顺序见[离线脚本](../../scripts/README.md#重新拟合范围层)。

## 构建本地 solver

项目使用 [本地 Rust 绑定](../solver/pf_solver/Cargo.toml)，依赖随仓库提供的 postflop-solver 副本。
该副本的来源与 EV 修复见 [本地补丁说明](../solver/pf_solver/postflop-solver/POKERFATE_PATCH.md)。
上游 README 中的 git 依赖示例不是本项目的构建方式，直接替换依赖会丢失本地修复。

在项目根目录运行：

```bash
cargo build --release --manifest-path pokerfate/solver/pf_solver/Cargo.toml
```

默认从 `pokerfate/solver/pf_solver/target/release/` 加载平台对应的扩展库，
不从其他工程或虚拟环境里隐式导入同名 solver。没有构建产物时，实时求解会回退规则引擎。
`build.rs` 处理 PyO3 在 macOS 上的链接参数；父目录 Cargo.toml 关闭上游 bincode，保留 rayon。

## 翻牌书的内容和匹配

默认书是本项目的 `pokerfate/data/flop_book/v3/`，包含三个索引文件
`meta.json`、`flop_iso_map.json`、`flop_clusters.json`，以及五个位置各两档深度的十个 `.db`。
格式要求 `schema_version=3`、`complete=true`；SQLite 只读，策略矩阵以 zlib + uint16 存储。

当前书的计算参数以 [meta.json](../data/flop_book/v3/meta.json) 为准：

- 单挑单次加注底池：UTG / MP / CO / BTN / SB 开池，对 BB 防守。
- 翻前有效深度 50BB、100BB；抽水 9%，不封顶。
- UTG / MP / SB 开池 4BB，CO / BTN 开池 3.5BB。
- 翻牌下注 33 / 50 / 67 / 100% 底池，加注 2x / 4x。
- 离线求解树的转河下注 75%，加注 2.7x；这不限制实战转河实时求解的菜单。
- 目标可剥削度不超过起始底池的 0.5%；生成时的范围和配置指纹保存在元数据中。

运行时按以下条件匹配，不按房间的大盲金额直接选择 50BB 或 100BB：

| 条件 | 处理 |
|---|---|
| 人数与翻前线路 | 当前单挑，翻前一次加注、BB 防守，位置组合存在 |
| 有效筹码 | 以翻牌起点的双方剩余筹码取较小值；当前剩余筹码加回本街投入后除以 BB |
| 选档 | 对两档书的翻牌后手计算相对误差，选择误差较小的一档 |
| 范围限制 | 有效后手须在 40–170BB，且与所选档偏差不超过 35% |
| 底池 | 与对应场景标准底池偏差不超过 35% |
| 行动路径 | 按 OOP/IP 还原真实行动，并把下注／加注映射到最近尺度 |

例如 BTN 场景，两档的翻牌后手是 46.5BB / 96.5BB；其他位置看元数据，
不是拿当前桌上筹码与 50 / 100 直接比较。多人、limp、3bet 底池和其他位置组合不在覆盖内。
下注映射允许绝对比例差不超过 50 个百分点、相对误差不超过 60%；加注按对数距离匹配，
相对误差不超过 50%。偏离过大直接 miss。

书只含策略概率，没有动作 EV。先比较弃牌、过牌、跟注与全部进攻动作的总概率，
进攻胜出后再选概率最高的尺度，避免四档下注把进攻频率分散后误选过牌。
画像调整只做有限的概率偏置，诊断为 `probability_bias_no_evs`。

## 替换书的流程

1. 在项目外的离线计算工程（不在本仓库）完成计算和完整性、收敛性验证；产物应包含全部场景数据库和上述索引文件。
2. 试验时可用 `PF_FLOP_BOOK_DIR=<候选书目录>` 指向同格式产物，检查命中、后手选档、动作路径和回退原因。
   该变量只选择目录，不会自动把外部材料安装到项目内。
3. 验证通过后停止使用旧书的 bot，把旧书移到项目外归档；将新书实体文件完整替换到
   `pokerfate/data/flop_book/v3/`。不要用指向外部工程的符号链接，也不要混放新旧分片。
4. 清除 shell、PyCharm 等启动配置中的 `PF_FLOP_BOOK_DIR`，确认默认目录能够独立读取。
5. 运行下面的检查，再按原运行参数启动。检查启动日志中的实际引擎状态和首批书命中记录。

```bash
.venv/bin/python -m pytest tests/test_flop_book.py tests/test_api.py -q
```

这些测试包含当前书的已知策略值。重新计算导致预期值变化时，应核实新产物后更新相应数据断言；
不能只删除失败断言。若书的格式、覆盖或参数变化，还需同步读取器契约、元数据及本说明。
本仓库不保留旧书兼容分支；运行不能依赖项目外的离线工程。

## 实时 CFR 输入

- 仅处理当前仍在手的两名玩家，转牌四张／河牌五张公共牌。
- 位置由 `GameState.is_ip()` 决定；底池使用本街起始底池，后手加回本街已投入。
- 对手范围取本街发牌时的 Range V2 快照；本街真实行动放在 solver 前缀中，避免重复使用同一证据。
- hero 范围取实际翻前线路，前街优先乘以书或 CFR 导出的所选动作概率；规则引擎决策才用桶频率表。
- 对手范围去除 hero 底牌和公共牌 blockers；hero 范围只用公共牌做 blocker，真实底牌用于读取当前组合。
- 默认转牌下注 33 / 75 / 150%，河牌 33 / 66 / 100 / 150%，转牌树内未来河牌粗化为 66 / 150%，加注 2.2x / 3x。
  已发生的真实尺度另行注入，供节点定位。抽水读取 `core.config`；不封顶通过足够大的 cap 表示，不能传 0。

solver 导出策略、动作 EV、节点 reach weights，以及动作后对手各组合的 EV。
这些字段供下一层回应重算使用，输出来源和本地修复见 solver 补丁说明。

## 回应模型和动作选择

实时求解以均衡 EV 为起点，回应模型估计真人在当前尺度、线路和范围下的弃／跟／加注或过牌／下注频率。
将动作后的值先换成与动作 EV 相同的净投入口径，再按频率差重算，并按置信度与均衡 EV 混合。
对手加注比均衡多出的部分按跟注估值：solver 给的加注后价值只对应它自己的加注范围，
多出来的加注来自均衡里本会跟注的较强牌，按加注后价值算会把 hero 的强牌下注低估。
河牌跟注范围变化时会重新计算摊牌份额；人机、无模型或无范围输入时沿用均衡回应。
预行动证据有单独输入，避免与已修正的牌力分布重复计入。

数值先验来自 `local/models/opponents.json` 的玩家统计、相似玩家和池子均值，按各项机会样本收缩；
不靠玩家类型标签直接替换 solver。`PF_RESPONSE_MODEL_PATH` 可指向候选回应模型，`off` 关闭它。

动作调整受 GTO EV 损失底线和风险折扣约束，限制低置信度画像引起的偏离。
进攻风险检查区分成牌价值下注与诈唬：成牌免除部分河牌进攻和大尺度折扣；
成牌且为 solver 首选时，还免除部分转牌持续下注及对黏性对手的折扣，避免重复压低已有价值依据的下注。

河牌面对便宜下注时，可依据对手过度价值下注的证据，或范围模型估计的摊牌价值，
将部分成牌的弃牌改为跟注。该规则要求跟注底池赔率不超过 25%，并同时限制均衡 EV 与最终 EV 的差距，
不是按一个牌力阈值无条件跟注。范围模型这一路的门槛为 `PF_CFR_CHEAP_CALL_MIN_SHOWDOWN=0.45`，
底池比例容差为 `PF_CFR_CHEAP_CALL_POT_TOLERANCE=0.06`，实际生效值记入会话配置。

近似等 EV 的动作可以按策略概率抽样，容差为 `max(0.15BB, 1% 底池)`，但需要 API 提供 `decision_seed`。
当前实战 bridge 不传种子，因此选择最终 EV 最高的动作；带种子的回放才执行混合抽样。

## 诊断

策略日志通过 `decision_source` 区分 `flop_book`、`realtime_cfr` 与规则引擎结果。
未命中看 `decision_engine_fallback` 和对应引擎的 `status` / reason。

| 来源 | 优先看哪些字段 |
|---|---|
| 翻牌书 | `scenario`、`strategy`、`selected_label`、`node_path`、`flop_canonical` / `flop_representative`、有效后手和底池偏差 |
| 实时 CFR | `action_evs_bb`、`exploit` 下的基线／调整／最终 EV、`responses`、`safety`、`node_path`、`range_counts`、`exploitability_pct`、`elapsed_ms` |

solver 缺失、超时、范围为空、非单挑、动作顺序不符、节点／组合缺失、有效后手不足 0.1BB 都会回退。
翻牌另有 `book_schema_unsupported`、`book_stack_out_of_range`、`book_stack_mismatch`、`book_pot_mismatch` 等原因。
