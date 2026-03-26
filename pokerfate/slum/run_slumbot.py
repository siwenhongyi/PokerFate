#!/usr/bin/env python3
"""CLI runner: PokerFate vs Slumbot (slumbot.com).

用法
----
# 使用 auth.json 账号（默认）：
python run_slumbot.py

# 指定手数：
python run_slumbot.py --hands 500

# 匿名模式（不登录）：
python run_slumbot.py --anonymous --hands 100

# 静默模式（只显示每手盈亏和最终汇总）：
python run_slumbot.py --hands 200 --quiet
"""

import argparse
import json
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from pokerfate.bot.poker_bot import PokerBot
from pokerfate.slum.slumbot_adapter import SlumbotAdapter

AUTH_PATH = os.path.join(os.path.dirname(__file__), 'auth.json')


def load_auth():
    if not os.path.exists(AUTH_PATH):
        return '', ''
    with open(AUTH_PATH) as f:
        data = json.load(f)
    return data.get('username', ''), data.get('password', '')


def main():
    parser = argparse.ArgumentParser(
        description='PokerFate vs Slumbot — CFR bot 对战测试',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument('--anonymous', action='store_true', help='匿名模式，不使用 auth.json 登录')
    parser.add_argument('--hands', type=int, default=100, help='对战手数（默认 100）')
    parser.add_argument('--iterations', type=int, default=1000, help='MC 胜率迭代次数（默认 1000）')
    parser.add_argument('--aggression', type=float, default=1.0, help='翻后激进度乘数（默认 1.0）')
    parser.add_argument('--quiet', action='store_true', help='静默模式：只显示每手结果')
    args = parser.parse_args()

    if args.anonymous:
        username, password = '', ''
    else:
        username, password = load_auth()
        if not username:
            print('未找到 auth.json 或账号为空，以匿名模式运行')

    print('=== PokerFate vs Slumbot ===')
    print(f'对战手数: {args.hands}  MC迭代: {args.iterations}  激进度: {args.aggression}')
    print(f'账号: {username if username else "匿名"}')
    print()

    bot = PokerBot(
        name='PokerFate',
        equity_iterations=args.iterations,
        aggression=args.aggression,
    )
    adapter = SlumbotAdapter(
        bot=bot,
        username=username,
        password=password,
        verbose=not args.quiet,
    )

    try:
        results = adapter.play_session(num_hands=args.hands)
    except KeyboardInterrupt:
        print('\n用户中断')
        return

    print(f'\n最终结果:')
    print(f'  总手数:  {results["hands"]}')
    print(f'  总盈亏:  {results["total_chips"] / 100:+.1f}BB  ({results["total_chips"]:+d} chips)')
    print(f'  BB/100:  {results["bb_per_100"]:+.1f}')


if __name__ == '__main__':
    main()
