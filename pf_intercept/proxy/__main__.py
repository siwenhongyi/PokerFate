"""CLI entry for ``python -m pf_intercept.proxy``."""

from __future__ import annotations

import asyncio

from pf_intercept.proxy.app import _parse_proxy_args, main


def run() -> None:
    args = _parse_proxy_args()
    asyncio.run(
        main(
            max_auto_rebuy=args.max_auto_rebuy,
            profit_lock_bb=args.profit_lock_bb,
            use_range_equity=(args.equity_mode == "range"),
            entertainment_web_host=(
                None if args.no_entertainment_web else args.entertainment_web_host
            ),
            entertainment_web_port=(
                None if args.no_entertainment_web else args.entertainment_web_port
            ),
        )
    )


if __name__ == "__main__":
    run()
