"""Compatibility CLI entry for ``python -m pf_intercept.gen_cert``."""

from __future__ import annotations

import runpy


if __name__ == "__main__":
    runpy.run_module("pf_intercept.certificates.generator", run_name="__main__")
