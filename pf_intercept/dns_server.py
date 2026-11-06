"""Compatibility CLI entry for ``python -m pf_intercept.dns_server``."""

from __future__ import annotations

import runpy


if __name__ == "__main__":
    runpy.run_module("pf_intercept.dns.server", run_name="__main__")
