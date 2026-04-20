"""P0 参数 sweep 兼容入口。

新 sweep 逻辑在 scripts.sweep_replay；这个文件只保留 P0 默认 grid 和
--baseline-only 控制组，避免旧命令失效。
"""
from __future__ import annotations

import argparse
import json
import os
import tempfile
from pathlib import Path

from scripts import sweep_replay


DEFAULT_GRID: dict[str, list[str]] = {
    'PF_BASELINE_THRESH': ['0.4', '0.6', '0.8'],
    'PF_LP_SIGNAL_FACTOR': ['0.3', '0.5', '0.7'],
    'PF_DEFAULT_STAB_HU': ['0.5', '0.7', '0.9'],
    'PF_DEFAULT_STAB_MULTI': ['0.3', '0.5', '0.7'],
}

P0_BASELINE_CONFIGS = [
    {},
    {
        'PF_BASELINE_THRESH': '999',
        'PF_LP_SIGNAL_FACTOR': '1.0',
        'PF_NEW_SIGNAL_FACTOR': '1.0',
        'PF_RANGECBET_WET_PEN': '0.001',
        'PF_RANGECBET_LOWBROAD_PEN': '0.001',
        'PF_RANGECBET_FLUSH_PEN': '0.001',
        'PF_RANGECBET_PAIRED_PEN': '0.001',
        'PF_DEFAULT_STAB_HU': '0.45',
        'PF_DEFAULT_STAB_MULTI': '0.45',
        'PF_FOLD_OVERRIDE_MARGIN': '999',
    },
]


def _default_shards() -> int:
    return max(1, (os.cpu_count() or 4) - 2)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--replay', type=Path, required=True, help='replay jsonl path')
    ap.add_argument('--max-hands', type=int, default=0, help='cap hands per replay (0 = all)')
    ap.add_argument('--seeds', type=int, default=3, help='seeds per config')
    ap.add_argument('--workers', type=int, default=1, help='parallel configs')
    ap.add_argument('--shards', type=int, default=_default_shards(), help='shards per config')
    ap.add_argument('--out', type=Path, default=Path('data/sweep_p0'), help='output dir')
    ap.add_argument('--grid', type=Path, help='custom grid JSON file')
    ap.add_argument('--baseline-only', action='store_true', help='run P0-on and P0-off only')
    args = ap.parse_args()

    cleanup = None
    if args.grid:
        grid_path = args.grid
    else:
        grid_payload = {'configs': P0_BASELINE_CONFIGS} if args.baseline_only else DEFAULT_GRID
        cleanup = tempfile.NamedTemporaryFile('w', suffix='.json', delete=False, encoding='utf-8')
        with cleanup:
            json.dump(grid_payload, cleanup, ensure_ascii=False)
        grid_path = Path(cleanup.name)

    try:
        sweep_replay.main([
            '--replay', str(args.replay),
            '--grid', str(grid_path),
            '--out', str(args.out),
            '--max-hands', str(args.max_hands),
            '--seeds', str(args.seeds),
            '--workers', str(args.workers),
            '--shards', str(args.shards),
            '--objective', 'high',
        ], description=__doc__)
    finally:
        if cleanup is not None:
            Path(cleanup.name).unlink(missing_ok=True)


if __name__ == '__main__':
    main()
