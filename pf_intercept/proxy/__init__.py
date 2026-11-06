"""Proxy package.

The public imports historically came from ``pf_intercept.proxy``.  Re-export all
application symbols while the implementation lives in smaller modules.
"""

from __future__ import annotations

from pf_intercept.proxy import app as _app

for _name in dir(_app):
    if not (_name.startswith("__") and _name.endswith("__")):
        globals()[_name] = getattr(_app, _name)

__all__ = [name for name in globals() if not (name.startswith("__") and name.endswith("__"))]
