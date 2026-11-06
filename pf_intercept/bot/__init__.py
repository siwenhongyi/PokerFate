"""Bot bridge package.

Expose ``bridge`` as ``pf_intercept.bot`` so existing tests and monkeypatches
continue to target the module that owns ``BotBridge`` globals.
"""

from __future__ import annotations

import sys

from pf_intercept.bot import bridge as _bridge

_parent = sys.modules.get(__name__.rsplit(".", 1)[0])
if _parent is not None:
    setattr(_parent, __name__.rsplit(".", 1)[1], _bridge)
sys.modules[__name__] = _bridge
