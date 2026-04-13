"""Fetch 30-day player stats from the game REST API.

Sign formula (from pf_reverse/output/lua/src/manager/Net.lua, addSaltArgs):
    MD5("random=" + random + "&ts=" + ts + "&salt=" + SALT)

Rate field scaling (empirically verified against sample: play_times=777):
    pool_entry_rate           — raw VPIP count (treated as raw integer count)
    add_before_flipping_rate  — raw PFR count  (treated as raw integer count)
    three_bet_rate  / 10000   → 3bet fraction per hand   (476  → 4.76%)
    show_hand_rate  / 10000   → showdown fraction per VPIP hand  (4375 → 43.75%)
    active_rate     / 1000    → aggression factor ratio   (1700 → 1.7)
    c_bete_rate     / 10000   → cbet fraction per cbet opportunity (2727 → 27.27%)
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import random
import ssl
import string
import time
import urllib.request
from pathlib import Path
from typing import Optional

import certifi

_SSL_CTX = ssl.create_default_context(cafile=certifi.where())

from pokerfate.bot.opponent_model import OpponentModel, OpponentStats

log = logging.getLogger("pf_gamedata")

_SALT = "Z3r0w0nd3rd3!3z4jz89z9DLbg&8Gjt("
_TOKEN_FILE = Path(__file__).resolve().parent.parent / "data" / "auth_token.txt"


# ── Signing ───────────────────────────────────────────────────────────────────

def _sign(rand: str, ts: str) -> str:
    raw = f"random={rand}&ts={ts}&salt={_SALT}"
    return hashlib.md5(raw.encode()).hexdigest()


def _load_token() -> Optional[str]:
    try:
        token = _TOKEN_FILE.read_text(encoding="utf-8").strip()
        return token or None
    except Exception:
        return None


# ── HTTP fetch (sync, run in executor) ───────────────────────────────────────

def _sync_fetch(uid: int, http_host: str, chnl: int, game_type: int, token: str) -> Optional[dict]:
    rand = "".join(random.choices(string.ascii_letters + string.digits, k=6))
    ts   = str(int(time.time()))
    body = json.dumps({
        "game_type":  game_type,
        "chnl":       chnl,
        "random":     rand,
        "sign":       _sign(rand, ts),
        "player_uid": uid,
        "ts":         ts,
    }).encode("utf-8")

    url = f"https://{http_host}/player/gameData"
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", "application/json; charset=utf-8")
    req.add_header("Authorization", token)
    req.add_header("User-Agent", "UnityPlayer/2022.3.62f3 (UnityWebRequest/1.0, libcurl/8.10.1-DEV)")
    req.add_header("Accept", "*/*")
    req.add_header("X-Unity-Version", "2022.3.62f3")
    log.debug("[gamedata] POST %s uid=%d", url, uid)
    try:
        with urllib.request.urlopen(req, timeout=8, context=_SSL_CTX) as resp:
            raw = resp.read()
            log.debug("[gamedata] uid=%d response: %s", uid, raw[:500])
            return json.loads(raw)
    except Exception as exc:
        log.warning("[gamedata] uid=%d 请求失败 (%s: %s) url=%s",
                    uid, type(exc).__name__, exc, url)
        return None


# ── Merge server data into OpponentStats ─────────────────────────────────────

def seed_from_server(stats: OpponentStats, data: dict) -> bool:
    """Apply 30-day server stats into stats in-place. Always overwrites covered fields.

    Returns True if data was applied.

    Careful analysis of each field:

    直接替换（服务端给原始 count，与我们字段语义完全一致）：
      hands_seen  ← play_times
      vpip_count  ← pool_entry_rate
      pfr_count   ← add_before_flipping_rate

    存服务端先验比率（server_ 前缀；使用时优先服务端，样本充足后切换到实测）：
      server_af_prior   ← active_rate / 1000
      server_3bet_prior ← three_bet_rate / 10000
      server_cbet_prior ← c_bete_rate / 10000
      server_wtsd_prior ← show_hand_rate / 10000

    不覆盖（服务端无此数据）：
      fold_to_cbet / fold_to_3bet / river_* / flop_* / turn_*
      showdown_count / flop_seen_count / showdown_win_count
      bet_win_count / bluff_win_count
    """
    play_times = int(data.get("play_times") or 0)
    if play_times <= 0:
        return False

    # ── 所有 rate 字段均 ×10000（pool_entry_rate=9600 > play_times=25 实测证明）──
    vpip = max(0.0, min(1.0, (data.get("pool_entry_rate")           or 0) / 10000))
    pfr  = max(0.0, min(vpip, (data.get("add_before_flipping_rate") or 0) / 10000))
    af        = max(0.01, (data.get("active_rate")    or 0) / 1000)
    three_bet = max(0.0, min(1.0, (data.get("three_bet_rate") or 0) / 10000))
    cbet      = max(0.0, min(1.0, (data.get("c_bete_rate")    or 0) / 10000))
    wtsd      = max(0.0, min(1.0, (data.get("show_hand_rate") or 0) / 10000))

    # ── 直接替换：hands_seen 为原始次数，vpip/pfr 由 rate × play_times 精确还原 ─
    stats.hands_seen = play_times
    stats.vpip_count = round(vpip * play_times)
    stats.pfr_count  = round(pfr  * play_times)

    # ── 存服务端先验比率：使用时优先服务端，样本充足后切换到实测 ──────────
    stats.server_af_prior   = af
    stats.server_3bet_prior = three_bet
    stats.server_cbet_prior = cbet
    stats.server_wtsd_prior = wtsd

    return True


# ── Async entry point ─────────────────────────────────────────────────────────

async def fetch_and_seed(
    uid: int,
    player_id: int,
    opponent_model: OpponentModel,
    http_host: str,
    chnl: int,
    game_type: int,
) -> None:
    """Async: fetch server stats for uid and seed into opponent_model[player_id]."""
    token = _load_token()
    if not token:
        log.warning("[gamedata] auth_token.txt empty or missing — skipping uid=%d", uid)
        return

    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(
        None, _sync_fetch, uid, http_host, chnl, game_type, token
    )

    if not result:
        log.debug("[gamedata] uid=%d: no response", uid)
        return
    if result.get("code") != 0:
        log.debug("[gamedata] uid=%d: server code=%s", uid, result.get("code"))
        return

    data = result.get("data") or {}
    if not data or not data.get("play_times"):
        log.debug("[gamedata] uid=%d: no play_times in data — ignored", uid)
        return

    stats = opponent_model.get(player_id)
    applied = seed_from_server(stats, data)
    if applied:
        log.info(
            "[gamedata] uid=%d seat=%d seeded from server (%d hands): %s",
            uid, player_id, data.get("play_times", 0), stats,
        )
    else:
        log.debug(
            "[gamedata] uid=%d seat=%d already has %d session hands — skipped",
            uid, player_id, stats.hands_seen,
        )
