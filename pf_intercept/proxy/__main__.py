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
        )
    )


if __name__ == "__main__":
    run()
