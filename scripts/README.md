# 离线脚本

这里的脚本把实战日志转成回放、重放历史牌局，并重新拟合 `pokerfate/data/runtime_calibration/` 和 `local/models/` 里的模型。
它们读本机的实战日志和训练样本，新克隆的仓库里没有这些数据，要先实战积累。
各模型的作用见[决策引擎的模型文件](../pokerfate/decision/README.md#模型文件)。

所有命令在项目根目录执行，完整参数用 `--help` 查看。

## 脚本一览

| 脚本 | 输入 → 输出 |
|---|---|
| `json_log_to_replay` | 策略日志 `pokerfate/logs/` → 回放文件（每行一手） |
| `replay_and_compare` | 回放 → 当前代码的决策与日志里原决策的差异 |
| `replay_parallel` | 同上，按 CPU 核数分片并行 |
| `extract_range_calibration_rows_parallel` | 回放 → 范围层样本行（`bucket` 只含牌力桶，`full` 另算 hero 胜率） |
| `fit_likelihood_model` | 样本行 → 动作似然 `formula_fit.json` |
| `fit_range_lgbm_calibration` | 样本行 → 桶校准模型 `runtime_lgbm_bucket_model.json` |
| `score_bucket_rows` | 两份样本行 → 按摊牌结果比较哪份更准 |
| `refill_hero_eq` | `full` 样本行 → 重填 `opponents.json` 里的 hero 胜率校准 |
| `fit_response_model` | 策略日志 → 对手回应模型 `response_model.json` |
| `fit_pre_action` | `headless.log` 网络日志 → 预选动作读数 `pre_action_fit.json` |
| `build_range_v2_empirical_model` | `opponents.json` 和样本行 → 人群先验 `range_v2_empirical_model.json` |
| `hero_name`、`range_calibration_meta` | 其他脚本共用的辅助模块 |

回放和提取样本时，API 不写 `opponents.json`，也不写策略日志。
会改动本机模型的只有带 `--apply` 的命令，以及没传 `--out` 时的 `build_range_v2_empirical_model`
（默认写到正在使用的 `local/models/range_v2_empirical_model.json`）。改动在用模型前先停 bot。

## 回放

```bash
.venv/bin/python -m scripts.json_log_to_replay \
  --json-log pokerfate/logs/pokerfate.log --out /tmp/replay.jsonl
.venv/bin/python -m scripts.replay_parallel --replay /tmp/replay.jsonl --max-hands 300
```

`--json-log` 可以重复传入，包括 `pokerfate/logs/archive/` 里的旧日志。日志和回放里的金额都是筹码数，不是 BB。

## 重新拟合范围层

范围层分三层，上层在下层的输出上拟合：动作似然 → 桶校准 → hero 胜率校准。
换了某一层，它上面的层都要按顺序重做。

1. **提取样本**，关掉桶校准，用规则引擎回放：

   ```bash
   DECISION_ENGINE=rule_engine PF_BUCKET_ML=off \
     .venv/bin/python -m scripts.extract_range_calibration_rows_parallel \
     --replay /tmp/replay.jsonl --mode bucket --out rows.jsonl --parts-dir parts
   ```

2. **拟合动作似然**，用较新的一段做留出检验：

   ```bash
   .venv/bin/python -m scripts.fit_likelihood_model \
     --rows older.jsonl --holdout-rows newest.jsonl --out fit.json
   ```

   转牌、河牌前的范围取决于前面几街用的似然，所以要用新文件重新提取（`PF_FORMULA_FIT_PATH=fit.json`）再拟合：
   翻牌一轮就定，转牌两轮，河牌三轮。翻前似然用 `--layer preflop` 单独拟合，换了它之后翻后要在新样本上重拟。

3. **重训桶校准**：在新似然下重新提取 `bucket` 样本（仍然 `PF_BUCKET_ML=off`），
   用 `fit_range_lgbm_calibration --train-rows ... --val-rows ... --bucket-model-out candidate.json` 训练。

4. **验收**：分别在 `PF_BUCKET_ML=off` 和 `PF_BUCKET_ML=lgbm PF_BUCKET_ML_MODEL_PATH=candidate.json` 下提取样本，再比较：

   ```bash
   .venv/bin/python -m scripts.score_bucket_rows rows_off.jsonl rows_on.jsonl
   ```

5. **重填 hero 胜率校准**：用新模型提取 `full` 样本（`--mode full --parts-dir parts_full`），按场次顺序传入。先不加 `--apply` 看报告，
   停 bot 后再加 `--apply` 写入，原文件会备份：

   ```bash
   .venv/bin/python -m scripts.refill_hero_eq --rows parts_full/task_*.jsonl --apply
   ```

把通过验收的文件放回 `pokerfate/data/runtime_calibration/` 后，重启 bot 才生效。

## 其他模型

- **对手回应模型**：先从策略日志解析一次样本行，再用较新的一段做留出检验，最后在全部样本上拟合并写回：

  ```bash
  .venv/bin/python -m scripts.fit_response_model --logs pokerfate/logs/pokerfate.log --rows-out rows.jsonl
  .venv/bin/python -m scripts.fit_response_model --rows rows.jsonl --holdout-from 2026-11-18T00:00 --out candidate.json
  .venv/bin/python -m scripts.fit_response_model --rows rows.jsonl --ridge 3 \
    --out pokerfate/data/runtime_calibration/response_model.json
  ```

- **预选动作读数**：不加 `--out` 只出报告，加 `--out pokerfate/data/runtime_calibration/pre_action_fit.json` 才写入。
  它读 `headless.log`，只解析需要的消息类型，不会打印原始行（日志里有登录 key）。

- **人群先验**：`build_range_v2_empirical_model`，建议先 `--out` 到别处检查，再替换正在使用的文件。

从回放提取的样本按实战的学习规则，排除平台机器人和 bot 会离开的牌桌上的牌局；回应模型和预选动作读数也只用真人的数据。
