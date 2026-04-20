"""通用 replay 参数 sweep。

基于 replay_parallel 对同一份 replay 跑多组 ENV 配置，按 HIGH/MED/LOW EV 汇总排序。

用法：
    .venv/bin/python -m scripts.sweep_replay \
        --replay data/calibration_replays/replay_1_2log.jsonl \
        --grid scripts/sweep_grids/p1_default.json \
        --max-hands 500 --seeds 1 --workers 1

Grid JSON 支持两种格式：

1) 参数网格（自动笛卡尔积）：
    {
      "PF_DEFAULT_STAB_HU": ["0.3", "0.5", "0.7"],
      "PF_DEFAULT_STAB_MULTI": ["0.3", "0.5", "0.7"]
    }

2) 显式配置列表：
    {
      "configs": [
        {"PF_DEFAULT_STAB_HU": "0.5"},
        {"PF_DEFAULT_STAB_HU": "0.7", "PF_DEFAULT_STAB_MULTI": "0.5"}
      ]
    }
"""
from __future__ import annotations

import argparse
import itertools
import json
import os
import subprocess
import sys
import time
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent


def _default_shards() -> int:
    return max(1, (os.cpu_count() or 4) - 2)


def _config_id(config: dict[str, str], idx: int | None = None) -> str:
    if not config:
        return 'default'
    body = '_'.join(f"{k.replace('PF_', '').lower()}={v}" for k, v in sorted(config.items()))
    if len(body) <= 180:
        return body
    prefix = f'cfg{idx}_' if idx is not None else ''
    return prefix + body[:180]


def load_configs(grid_path: Path) -> list[dict[str, str]]:
    raw = json.loads(grid_path.read_text(encoding='utf-8'))
    if isinstance(raw, list):
        return [{str(k): str(v) for k, v in cfg.items()} for cfg in raw]
    if not isinstance(raw, dict):
        raise ValueError('grid JSON must be an object or a list of config objects')

    if 'configs' in raw:
        configs = raw['configs']
        if not isinstance(configs, list):
            raise ValueError('grid.configs must be a list')
        return [{str(k): str(v) for k, v in cfg.items()} for cfg in configs]

    grid = raw.get('grid', raw)
    if not isinstance(grid, dict):
        raise ValueError('grid must be an object')
    keys = list(grid.keys())
    values: list[list[Any]] = []
    for key in keys:
        vals = grid[key]
        if not isinstance(vals, list) or not vals:
            raise ValueError(f'grid value for {key} must be a non-empty list')
        values.append(vals)

    configs: list[dict[str, str]] = []
    for combo in itertools.product(*values):
        configs.append({str(k): str(v) for k, v in zip(keys, combo)})
    return configs


def run_one(task: tuple) -> dict[str, Any]:
    config, config_idx, seed, replay_path, max_hands, out_dir, shards = task
    config_id = _config_id(config, config_idx)
    out_jsonl = out_dir / f"{config_id}_s{seed}.jsonl"
    json_summary = out_dir / f"{config_id}_s{seed}.json"

    cmd = [
        sys.executable, '-m', 'scripts.replay_parallel',
        '--replay', str(replay_path),
        '--out', str(out_jsonl),
        '--seed', str(seed),
        '--shards', str(shards),
    ]
    for key, value in sorted(config.items()):
        cmd.extend(['--env', f'{key}={value}'])
    if max_hands > 0:
        cmd.extend(['--max-hands', str(max_hands)])

    start = time.time()
    try:
        proc = subprocess.run(
            cmd,
            cwd=ROOT,
            env=os.environ.copy(),
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            timeout=1800,
        )
    except subprocess.TimeoutExpired:
        return {
            'config_id': config_id,
            'config': config,
            'seed': seed,
            'error': 'timeout',
            'elapsed': time.time() - start,
        }

    if proc.returncode != 0:
        return {
            'config_id': config_id,
            'config': config,
            'seed': seed,
            'error': proc.stderr[-500:],
            'elapsed': time.time() - start,
        }

    try:
        summary = json.loads(proc.stdout)
    except Exception:
        json_summary.write_text(proc.stdout, encoding='utf-8')
        return {
            'config_id': config_id,
            'config': config,
            'seed': seed,
            'error': 'summary_not_json',
            'elapsed': time.time() - start,
        }

    json_summary.write_text(proc.stdout, encoding='utf-8')
    ev = summary.get('ev_delta_chips', {})
    high = ev.get('HIGH', {})
    med = ev.get('MED', {})
    low = ev.get('LOW', {})
    return {
        'config_id': config_id,
        'config': config,
        'seed': seed,
        'total_decisions': summary.get('total_decisions', 0),
        'total_changed': summary.get('total_changed', 0),
        'change_pct': summary.get('change_pct', 0),
        'high_sum': high.get('sum', 0),
        'high_count': high.get('count', 0),
        'med_sum': med.get('sum', 0),
        'med_count': med.get('count', 0),
        'low_sum': low.get('sum', 0),
        'low_count': low.get('count', 0),
        'elapsed': time.time() - start,
    }


def aggregate(results: list[dict[str, Any]], objective: str) -> list[dict[str, Any]]:
    agg: dict[str, dict[str, Any]] = defaultdict(lambda: {
        'high_sums': [],
        'high_counts': [],
        'med_sums': [],
        'med_counts': [],
        'low_sums': [],
        'low_counts': [],
        'changed_pcts': [],
        'errors': 0,
        'config': {},
    })
    for result in results:
        row = agg[result['config_id']]
        row['config'] = result['config']
        if result.get('error'):
            row['errors'] += 1
            continue
        row['high_sums'].append(result.get('high_sum', 0))
        row['high_counts'].append(result.get('high_count', 0))
        row['med_sums'].append(result.get('med_sum', 0))
        row['med_counts'].append(result.get('med_count', 0))
        row['low_sums'].append(result.get('low_sum', 0))
        row['low_counts'].append(result.get('low_count', 0))
        row['changed_pcts'].append(result.get('change_pct', 0))

    rows: list[dict[str, Any]] = []
    for config_id, row in agg.items():
        high_sums = row['high_sums']
        if not high_sums:
            continue
        seeds_ok = len(high_sums)
        med_sums = row['med_sums']
        low_sums = row['low_sums']
        high_mean = sum(high_sums) / seeds_ok
        med_mean = sum(med_sums) / seeds_ok
        low_mean = sum(low_sums) / seeds_ok
        score = high_mean
        if objective == 'high_med_guard':
            score = high_mean + min(0.0, med_mean) * 0.25 + min(0.0, low_mean) * 0.10
        rows.append({
            'config_id': config_id,
            'config': row['config'],
            'seeds_ok': seeds_ok,
            'errors': row['errors'],
            'objective': objective,
            'score': score,
            'high_mean': high_mean,
            'high_min': min(high_sums),
            'high_max': max(high_sums),
            'high_count_mean': sum(row['high_counts']) / seeds_ok,
            'med_mean': med_mean,
            'med_count_mean': sum(row['med_counts']) / seeds_ok,
            'low_mean': low_mean,
            'low_count_mean': sum(row['low_counts']) / seeds_ok,
            'changed_pct_mean': sum(row['changed_pcts']) / seeds_ok,
        })

    rows.sort(key=lambda r: (-r['score'], -r['high_min'], -r['med_mean']))
    return rows


def build_parser(description: str | None = None) -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        description=description or __doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument('--replay', type=Path, required=True, help='replay jsonl path')
    ap.add_argument('--grid', type=Path, required=True, help='grid JSON path')
    ap.add_argument('--out', type=Path, default=Path('data/sweep_replay'), help='output dir')
    ap.add_argument('--max-hands', type=int, default=0, help='cap hands per replay (0 = all)')
    ap.add_argument('--seeds', type=int, default=3, help='seeds per config')
    ap.add_argument('--workers', type=int, default=1, help='parallel configs')
    ap.add_argument('--shards', type=int, default=_default_shards(), help='shards per config')
    ap.add_argument(
        '--objective',
        choices=('high', 'high_med_guard'),
        default='high_med_guard',
        help='ranking objective',
    )
    return ap


def main(argv: list[str] | None = None, *, description: str | None = None) -> None:
    args = build_parser(description).parse_args(argv)

    out_dir = args.out
    if not out_dir.is_absolute():
        out_dir = (ROOT / out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    configs = load_configs(args.grid)
    tasks = []
    for config_idx, config in enumerate(configs):
        for seed_idx in range(args.seeds):
            tasks.append((
                config,
                config_idx,
                42 + seed_idx * 13,
                args.replay,
                args.max_hands,
                out_dir,
                args.shards,
            ))

    print(
        f"configs: {len(configs)}, seeds: {args.seeds}, total runs: {len(tasks)}, "
        f"workers: {args.workers}, shards: {args.shards}, objective: {args.objective}",
        file=sys.stderr,
    )

    results: list[dict[str, Any]] = []
    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        futures = {ex.submit(run_one, task): task for task in tasks}
        for done, fut in enumerate(as_completed(futures), start=1):
            result = fut.result()
            results.append(result)
            err = result.get('error')
            mark = ' ERR' if err else ''
            high = result.get('high_sum', 0) or 0
            med = result.get('med_sum', 0) or 0
            print(
                f"[{done}/{len(tasks)}] {result['config_id'][:70]} seed={result['seed']} "
                f"HIGH={high:+.0f} MED={med:+.0f}{mark} ({result.get('elapsed', 0):.0f}s)",
                file=sys.stderr,
            )
            if err:
                print(f"  err: {str(err)[:250]}", file=sys.stderr)

    rows = aggregate(results, args.objective)
    summary_path = out_dir / 'sweep_summary.json'
    summary_path.write_text(
        json.dumps({
            'rows': rows,
            'tasks_total': len(tasks),
            'replay': str(args.replay),
            'grid': str(args.grid),
            'max_hands': args.max_hands,
            'objective': args.objective,
        }, indent=2, ensure_ascii=False),
        encoding='utf-8',
    )

    print()
    print('=== TOP 10 ===')
    print(f"{'config':<70} {'score':>10} {'HIGH':>10} {'Hmin':>9} {'MED':>10} {'LOW':>10} {'chg%':>6}")
    for row in rows[:10]:
        print(
            f"{row['config_id'][:70]:<70} "
            f"{row['score']:>+10.0f} {row['high_mean']:>+10.0f} "
            f"{row['high_min']:>+9.0f} {row['med_mean']:>+10.0f} "
            f"{row['low_mean']:>+10.0f} {row['changed_pct_mean']:>6.1f}"
        )
    print()
    print(f"Full summary: {summary_path}")


if __name__ == '__main__':
    main()
