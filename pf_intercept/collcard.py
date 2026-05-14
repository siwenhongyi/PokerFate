"""Game replay collection API helper."""

from __future__ import annotations

import logging
from typing import Optional

from pf_intercept.http_api import signed_post_json

log = logging.getLogger("pf_collcard")


def _collect_payload(gameid: str, roomid: int = 0, tid: int = 1) -> dict:
    payload = {"add_id": gameid}
    if roomid > 0:
        payload["roomid"] = str(int(roomid))
    if tid > 0:
        payload["tid"] = str(int(tid))
    return payload


def _sync_collect_game(
    gameid: str,
    *,
    roomid: int = 0,
    tid: int = 1,
    reason: str = "",
) -> Optional[dict]:
    """POST /collCard/update to collect one game replay.

    Returns the decoded response when the server replied, otherwise None.
    """
    gid = str(gameid or "").strip()
    if not gid or gid == "0":
        log.warning("[collcard] skip collect: missing gameid")
        return None

    data = signed_post_json(
        "/collCard/update",
        _collect_payload(gid, roomid=roomid, tid=tid),
        timeout=8,
    )
    if data is None:
        log.warning("[collcard] collect failed gameid=%s reason=%s", gid, reason)
        return None
    if data.get("code") == 0:
        count = len(data.get("gameids") or [])
        log.warning("[collcard] collected gameid=%s reason=%s count=%s", gid, reason, count)
    else:
        log.warning("[collcard] collect rejected gameid=%s reason=%s resp=%s", gid, reason, data)
    return data


def _sync_recently_cards(*, skip: int = 0, lang: str = "en") -> Optional[dict]:
    """POST /collCard/recentlyCardList for manual smoke checks."""
    return signed_post_json(
        "/collCard/recentlyCardList",
        {"skip": int(skip), "lang": lang},
        timeout=8,
    )
