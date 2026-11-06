//! postflop-solver 的薄 PyO3 绑定。
//!
//! 单入口 `solve_flop_json(args_json) -> result_json`：
//! 输入求解参数，跑 DCFR 到目标可剥削度，返回当前街全部决策节点的策略。
//! JSON 进出，绑定面最小化；格式转换/量化/入库全部留在 Python 侧。

use postflop_solver::*;
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use serde::{Deserialize, Serialize};

#[derive(Deserialize)]
struct SolveArgs {
    board: String,      // 6/8/10 字符：翻牌/转牌/河牌起始（如 "Td9d6h2c"）
    oop_range: String,  // postflop-solver Range 语法
    ip_range: String,
    starting_pot: i32,     // 筹码单位（建议 bb x10 取整），当前街开始时的底池
    effective_stack: i32,
    rake_rate: f64,
    rake_cap: f64,
    flop_bets: String,  // OOP 菜单，"33%, 66%, 100%, 200%"
    turn_bets: String,
    river_bets: String,
    raises: String,     // "2.7x"
    #[serde(default)]
    flop_bets_ip: Option<String>,  // IP 独立菜单（实时注入对手真实尺寸用），缺省同 OOP
    #[serde(default)]
    turn_bets_ip: Option<String>,
    #[serde(default)]
    river_bets_ip: Option<String>,
    #[serde(default)]
    raises_ip: Option<String>,
    add_allin_threshold: f64,
    force_allin_threshold: f64,
    merging_threshold: f64,
    target_exploitability_pct: f32, // 占 starting_pot 的百分比，如 0.5
    max_iterations: u32,
    compression: bool,
    #[serde(default)]
    include_evs: bool,
}

#[derive(Serialize)]
struct NodeOut {
    path: String,          // 动作 label 以 ":" 连接，根 = "r"
    player: usize,         // 0=OOP 1=IP
    actions: Vec<String>,  // 如 ["Check","Bet(21)"]，顺序即 strategy 列序
    num_hands: usize,
    strategy: Vec<f32>,    // 长度 = actions.len() * num_hands，action-major
    #[serde(skip_serializing_if = "Vec::is_empty")]
    evs: Vec<f32>,         // 当前玩家每个动作/手牌的 EV，shape 同 strategy
    #[serde(skip_serializing_if = "Vec::is_empty")]
    weights: Vec<f32>,     // 当前节点当前玩家归一化 reach weights
    #[serde(skip_serializing_if = "Vec::is_empty")]
    opponent_evs: Vec<f32>, // 当前玩家每个动作后，对手每手牌 EV；action-major
    #[serde(skip_serializing_if = "is_zero")]
    opponent_num_hands: usize,
}

fn is_zero(value: &usize) -> bool {
    *value == 0
}

#[derive(Serialize)]
struct SolveOut {
    exploitability: f32,
    target_exploitability: f32,
    oop_hands: Vec<String>, // 与 strategy 的 hand 维度对齐
    ip_hands: Vec<String>,
    nodes: Vec<NodeOut>,
}

fn err<E: std::fmt::Display>(e: E) -> PyErr {
    PyValueError::new_err(e.to_string())
}

fn action_label(a: &Action) -> String {
    match a {
        Action::Check => "Check".to_string(),
        Action::Call => "Call".to_string(),
        Action::Fold => "Fold".to_string(),
        Action::Bet(x) => format!("Bet({})", x),
        Action::Raise(x) => format!("Raise({})", x),
        Action::AllIn(x) => format!("AllIn({})", x),
        other => format!("{:?}", other),
    }
}

/// 深度优先收集决策节点；遇 chance（发下一张公共牌）或终端即停 => 只覆盖当前街。
fn walk(
    game: &mut PostFlopGame,
    history: &mut Vec<usize>,
    labels: &mut Vec<String>,
    out: &mut Vec<NodeOut>,
    include_evs: bool,
) {
    game.apply_history(history);
    if game.is_terminal_node() || game.is_chance_node() {
        return;
    }
    let player = game.current_player();
    let actions = game.available_actions();
    let strategy = game.strategy();
    let num_hands = strategy.len() / actions.len();
    let mut evs = Vec::new();
    let mut weights = Vec::new();
    let mut opponent_evs = Vec::new();
    let mut opponent_num_hands = 0;
    if include_evs {
        game.cache_normalized_weights();
        evs = game.expected_values_detail(player);
        weights = game.normalized_weights(player).to_vec();
        let opponent = player ^ 1;
        opponent_num_hands = game.private_cards(opponent).len();
        for action in 0..actions.len() {
            let mut child_history = history.clone();
            child_history.push(action);
            game.apply_history(&child_history);
            game.cache_normalized_weights();
            opponent_evs.extend(game.expected_values(opponent));
        }
        game.apply_history(history);
        game.cache_normalized_weights();
    }
    out.push(NodeOut {
        path: if labels.is_empty() { "r".to_string() } else { format!("r:{}", labels.join(":")) },
        player,
        actions: actions.iter().map(action_label).collect(),
        num_hands,
        strategy,
        evs,
        weights,
        opponent_evs,
        opponent_num_hands,
    });
    let n = actions.len();
    for i in 0..n {
        history.push(i);
        labels.push({
            game.apply_history(&history[..history.len() - 1]);
            action_label(&game.available_actions()[i])
        });
        walk(game, history, labels, out, include_evs);
        labels.pop();
        history.pop();
    }
}

fn parse_sizes(oop: &str, ip: Option<&str>, raises_oop: &str, raises_ip: Option<&str>,
               what: &str) -> Result<[BetSizeOptions; 2], String> {
    let o = BetSizeOptions::try_from((oop, raises_oop))
        .map_err(|e| format!("{}: {}", what, e))?;
    let i = BetSizeOptions::try_from((ip.unwrap_or(oop), raises_ip.unwrap_or(raises_oop)))
        .map_err(|e| format!("{}_ip: {}", what, e))?;
    Ok([o, i])
}

fn run_solve(args: &SolveArgs) -> Result<SolveOut, String> {
    let oop: Range = args.oop_range.parse().map_err(|e| format!("oop_range: {}", e))?;
    let ip: Range = args.ip_range.parse().map_err(|e| format!("ip_range: {}", e))?;

    let b = &args.board;
    if !matches!(b.len(), 6 | 8 | 10) {
        return Err(format!("board 长度非法: {}", b));
    }
    let flop = flop_from_str(&b[0..6]).map_err(|e| format!("board: {}", e))?;
    let turn = if b.len() >= 8 {
        card_from_str(&b[6..8]).map_err(|e| format!("turn: {}", e))?
    } else {
        NOT_DEALT
    };
    let river = if b.len() == 10 {
        card_from_str(&b[8..10]).map_err(|e| format!("river: {}", e))?
    } else {
        NOT_DEALT
    };
    let initial_state = match b.len() {
        6 => BoardState::Flop,
        8 => BoardState::Turn,
        _ => BoardState::River,
    };

    let card_config = CardConfig {
        range: [oop, ip],
        flop,
        turn,
        river,
    };

    let raises_ip = args.raises_ip.as_deref();
    let flop_sizes = parse_sizes(&args.flop_bets, args.flop_bets_ip.as_deref(),
                                 &args.raises, raises_ip, "flop_bets")?;
    let turn_sizes = parse_sizes(&args.turn_bets, args.turn_bets_ip.as_deref(),
                                 &args.raises, raises_ip, "turn_bets")?;
    let river_sizes = parse_sizes(&args.river_bets, args.river_bets_ip.as_deref(),
                                  &args.raises, raises_ip, "river_bets")?;

    let tree_config = TreeConfig {
        initial_state,
        starting_pot: args.starting_pot,
        effective_stack: args.effective_stack,
        rake_rate: args.rake_rate,
        rake_cap: args.rake_cap,
        flop_bet_sizes: flop_sizes,
        turn_bet_sizes: turn_sizes,
        river_bet_sizes: river_sizes,
        turn_donk_sizes: None,
        river_donk_sizes: None,
        add_allin_threshold: args.add_allin_threshold,
        force_allin_threshold: args.force_allin_threshold,
        merging_threshold: args.merging_threshold,
    };

    let action_tree = ActionTree::new(tree_config).map_err(|e| format!("tree: {}", e))?;
    let mut game =
        PostFlopGame::with_config(card_config, action_tree).map_err(|e| format!("game: {}", e))?;
    game.allocate_memory(args.compression);

    let target = args.starting_pot as f32 * args.target_exploitability_pct / 100.0;
    let exploitability = solve(&mut game, args.max_iterations, target, false);
    game.cache_normalized_weights();

    let oop_hands = holes_to_strings(game.private_cards(0)).map_err(|e| format!("{}", e))?;
    let ip_hands = holes_to_strings(game.private_cards(1)).map_err(|e| format!("{}", e))?;

    let mut nodes = Vec::new();
    walk(&mut game, &mut Vec::new(), &mut Vec::new(), &mut nodes, args.include_evs);

    Ok(SolveOut {
        exploitability,
        target_exploitability: target,
        oop_hands,
        ip_hands,
        nodes,
    })
}

#[pyfunction]
fn solve_flop_json(py: Python<'_>, args_json: &str) -> PyResult<String> {
    let args: SolveArgs = serde_json::from_str(args_json).map_err(err)?;
    let out = py
        .allow_threads(|| run_solve(&args))
        .map_err(err)?;
    serde_json::to_string(&out).map_err(err)
}

#[pymodule]
fn pf_solver(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(solve_flop_json, m)?)?;
    Ok(())
}
