# 本地改动说明

这是 b-inary/postflop-solver 提交 `9d1509fe5077d019825f833eed04b16d342dfda1` 的副本（AGPL-3.0-or-later，见 LICENSE），
只改了结果解释器，求解过程没有动。所有改动处都有 `[PokerFate patch]` 注释。

## 改了什么

上游的 `expected_values_detail` 把一手牌的反事实价值除以 `w_normalized / w_raw`。
`w_normalized = w_raw × 对手与该手牌不冲突的到达权重`，所以这个商在 `w_raw > 0` 时就是对手的权重；
`w_raw = 0`（这手牌按均衡策略走不到当前节点）时上游直接把所有动作的 EV 填成 0。

反事实价值本身不依赖自己的到达权重（`compute_cfvalue_recursive` 只用对手的 reach），所以改成直接除以对手的权重：

- `game/mod.rs`、`game/base.rs`：新增缓存 `opponent_weights`。
- `game/interpreter.rs`
  - `cache_normalized_weights` 同时写入 `opponent_weights`（舍入余量按 0 处理）。
  - 新增 `pub fn opponent_weights(player)`。
  - `expected_values_detail`：`v * normalizer / w_opponent`；只有 `w_opponent = 0`（对手没有手牌到达）时才填 0。
    `expected_values` 走同一段代码。`equity` 没有改。

- `lib.rs`：加了三行 `#![allow(...)]`。作为 git 依赖时 cargo 会放宽依赖的 lint；改成本地路径依赖后，
  rustc 1.96 会因为 `dangerous_implicit_autorefs` 拒绝 action_tree.rs 里三处上游原有的写法。上游代码没有改，只恢复原来的 lint 处理。

## 影响

- 走得到节点的手牌：数值不变（只差浮点舍入）。
- 走不到节点的手牌：原来是 0，现在是真实 EV。
- 起因：2026-11-17 实战，坚果同花在“自己下注后被全下”的节点上 EV 被报成 弃牌 0 / 跟注 0，被上层当成真实数值而弃牌。
  见 `docs/candidates/zero_ev_2026-11-17/README.md`。

## 升级上游时

重新取上游源码后，按 `[PokerFate patch]` 注释把这几处改回去（共 5 处），或对照 `docs/candidates/zero_ev_2026-11-17/upstream.patch`。
