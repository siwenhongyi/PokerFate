"""并行 replay：按 (cpu_count − 2) 自动分片，合并 summary。

为什么能并行：
  bot 决策的关键状态（Bayesian tracker、opponent_model）跨手累积，但 sweep
  /baseline 用例关心的是"同一份日志、不同代码版本下 hero 的决策差"，每个
  shard 内部都重新建立 opponent_model。各 shard 看到的对手都"似新"——这会让
  tracker 不能用历史 hands 的 vpip 推 prior，但：
    - 对 P0-on vs P0-off 这种"同一 shard 比较两个配置"的口径，shard 内的偏置
      被减掉，比较仍然有效
    - 对绝对 EV 数字，shard 越多偏置越大 —— 所以 shard 数控制在 cpu_count-2
      避免过度切碎；每 shard 至少 ~10 手让 tracker 有机会建模

合并语义：
  - 各 shard 各自跑出 summary，再把它们的"原始计数"合到一起
  - 不重新算平均（mean of means 错），而是 sum 后重算 avg

用法：
    .venv/bin/python -m scripts.replay_parallel \
        --replay data/calibration_replays/replay_2log.jsonl --max-hands 300

    # 控制 shard 数
    .venv/bin/python -m scripts.replay_parallel \
        --replay data/calibration_replays/replay_2log.jsonl \
        --shards 8 --max-hands 300
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
import traceback
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _default_shards() -> int:
    return max(1, (os.cpu_count() or 4) - 2)


def run_shard(task: tuple) -> dict:
    """跑一个 shard（subprocess），返回 summary dict + per-decision rows path。"""
    (shard_id, replay_path, start, end, env_overrides, seed) = task
    rows_path = Path(tempfile.gettempdir()) / f"rep_shard_{os.getpid()}_{shard_id}.jsonl"

    env = os.environ.copy()
    env.update(env_overrides)

    cmd = [
        sys.executable, '-m', 'scripts.replay_and_compare',
        '--replay', str(replay_path),
        '--start-hand', str(start),
        '--end-hand', str(end),
        '--out', str(rows_path),
        '--seed', str(seed),
    ]
    t0 = time.time()
    try:
        proc = subprocess.run(
            cmd, cwd=ROOT, env=env,
            capture_output=True, text=True,
            encoding='utf-8', errors='replace',
            timeout=3600,
        )
    except subprocess.TimeoutExpired:
        return {'shard_id': shard_id, 'error': 'timeout',
                'elapsed': time.time() - t0}
    elapsed = time.time() - t0
    if proc.returncode != 0:
        return {'shard_id': shard_id,
                'error': f'returncode={proc.returncode}: {proc.stderr[-500:]}',
                'elapsed': elapsed}
    try:
        summary = json.loads(proc.stdout)
    except Exception as e:
        return {'shard_id': shard_id, 'error': f'parse: {e}',
                'stdout_tail': proc.stdout[-300:], 'elapsed': elapsed}
    # Read per-decision rows
    rows = []
    if rows_path.exists():
        with rows_path.open('r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        rows.append(json.loads(line))
                    except json.JSONDecodeError as exc:
                        print(
                            f"[replay_parallel] shard={shard_id} bad row JSON: {exc}",
                            file=sys.stderr,
                        )
                    except Exception as exc:
                        print(
                            f"[replay_parallel] shard={shard_id} row parse failed: "
                            f"{type(exc).__name__}: {exc}",
                            file=sys.stderr,
                        )
                        traceback.print_exc(file=sys.stderr)
        try:
            rows_path.unlink()
        except OSError:
            pass
    return {'shard_id': shard_id, 'summary': summary, 'rows': rows,
            'elapsed': elapsed}


def merge_summaries(shard_results: list[dict]) -> dict:
    """把多个 shard 的 summary + rows 合成一个等价于"全跑"的 summary。"""
    all_rows: list[dict] = []
    for s in shard_results:
        if 'rows' in s:
            all_rows.extend(s['rows'])
    # 直接复用 replay_and_compare.summarize，因为它接受 rows 列表
    from scripts.replay_and_compare import summarize
    return summarize(all_rows)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--replay', type=Path, required=True)
    ap.add_argument('--max-hands', type=int, default=0)
    ap.add_argument('--shards', type=int, default=_default_shards(),
                    help=f'分片数（默认 cpu_count - 2 = {_default_shards()}）')
    ap.add_argument('--seed', type=int, default=42)
    ap.add_argument('--env', action='append', default=[],
                    help='ENV 覆盖（KEY=VAL），可多次。例：--env PF_BASELINE_THRESH=0.5')
    ap.add_argument('--out', type=Path,
                    help='将合并的 per-decision rows 写到此 jsonl')
    args = ap.parse_args()

    # 读 replay 数手数
    with args.replay.open('r', encoding='utf-8') as f:
        n_hands = sum(1 for line in f if line.strip())
    if args.max_hands > 0:
        n_hands = min(n_hands, args.max_hands)

    n_shards = max(1, min(args.shards, n_hands))
    if n_shards > 1 and n_hands < n_shards * 5:
        # 每 shard 太少手会拖累 tracker prior 建立，强制最少 5 手/shard
        n_shards = max(1, n_hands // 5)

    # 切分手范围
    chunk = n_hands // n_shards
    rem = n_hands % n_shards
    ranges: list[tuple[int, int]] = []
    pos = 0
    for i in range(n_shards):
        size = chunk + (1 if i < rem else 0)
        ranges.append((pos, pos + size))
        pos += size

    env_overrides: dict[str, str] = {}
    for kv in args.env:
        if '=' not in kv:
            print(f"bad --env spec (need KEY=VAL): {kv}", file=sys.stderr)
            sys.exit(2)
        k, v = kv.split('=', 1)
        env_overrides[k.strip()] = v.strip()

    print(f"shards={n_shards} hands={n_hands} ranges={ranges} "
          f"env={env_overrides}", file=sys.stderr)

    tasks = [(i, args.replay, s, e, env_overrides, args.seed + i)
             for i, (s, e) in enumerate(ranges)]

    t0 = time.time()
    results: list[dict] = []
    with ProcessPoolExecutor(max_workers=n_shards) as ex:
        futs = {ex.submit(run_shard, t): t for t in tasks}
        for fut in as_completed(futs):
            r = fut.result()
            results.append(r)
            sid = r.get('shard_id', '?')
            err = r.get('error')
            if err:
                print(f"shard {sid} ERROR: {err[:200]} ({r.get('elapsed', 0):.0f}s)",
                      file=sys.stderr)
            else:
                summary = r.get('summary', {})
                print(f"shard {sid}: {summary.get('total_decisions', 0)} decisions, "
                      f"{summary.get('total_changed', 0)} changed "
                      f"({r.get('elapsed', 0):.0f}s)", file=sys.stderr)

    elapsed = time.time() - t0

    # 合并
    valid = [r for r in results if 'rows' in r]
    if not valid:
        print("ERROR: no shards succeeded", file=sys.stderr)
        sys.exit(1)
    merged = merge_summaries(valid)
    merged['_meta'] = {
        'shards': n_shards, 'hands': n_hands, 'elapsed_s': elapsed,
        'env_overrides': env_overrides,
    }

    print(json.dumps(merged, indent=2, ensure_ascii=False))

    if args.out:
        all_rows = []
        for r in valid:
            all_rows.extend(r.get('rows', []))
        with args.out.open('w', encoding='utf-8') as f:
            for row in all_rows:
                f.write(json.dumps(row, ensure_ascii=False) + '\n')
        print(f"wrote {len(all_rows)} rows to {args.out}", file=sys.stderr)


if __name__ == '__main__':
    main()
