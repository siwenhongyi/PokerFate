"""Fetch 30-day player stats from the game REST API.

Sign formula (from pf_reverse/output/lua/src/manager/Net.lua, addSaltArgs):
    MD5("random=" + random + "&ts=" + ts + "&salt=" + SALT)

Rate field scaling (all /10000 to a [0, 1] percentage):
    pool_entry_rate           — raw VPIP count (treated as raw integer count)
    add_before_flipping_rate  — raw PFR count  (treated as raw integer count)
    show_hand_rate  / 10000   → showdown fraction per VPIP    (4375 → 43.75%)
    active_rate     / 10000   → aggression frequency (AFq, pct; 1700 → 17%)

字段使用现状（2026-04-22 清理）：
    ✅ 使用：  play_times / pool_entry_rate / add_before_flipping_rate /
              show_hand_rate / active_rate

⚠️ active_rate note (updated 2026-05-03):
  active_rate is interpreted as AFq (aggressive-action frequency), but not in
  the classic tracker denominator. Empirical replay over all local logs shows
  this server AFq is closest to:
      AFq ≈ A / (A + C + K + F)
  where A=aggressive, C=call, K=check, F=fold.

  To map this AFq to an AF-like ratio A/C used by downstream decision rules:
      AF = AFq / ((1 - AFq) * R)
      R = C / (C + K + F) ≈ 0.3109

  The calibration constant R=0.3109 is inferred from aggregated local logs
  (all players excluding hero, plus robustness checks on hero-fold subsets).
  This keeps server prior magnitude aligned with in-session behavior.
"""

from __future__ import annotations

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

from pokerfate.bot.opponent_model import OpponentStats

log = logging.getLogger("pf_gamedata")

_SALT = "Z3r0w0nd3rd3!3z4jz89z9DLbg&8Gjt("
_TOKEN_FILE = Path(__file__).resolve().parent.parent / "data" / "auth_token.txt"
_AFQ_TO_AF_CALL_SHARE = 0.3109


# ── Signing ───────────────────────────────────────────────────────────────────

def _sign(rand: str, ts: str) -> str:
    raw = f"random={rand}&ts={ts}&salt={_SALT}"
    return hashlib.md5(raw.encode()).hexdigest()


def _load_token() -> Optional[str]:
    try:
        token = _TOKEN_FILE.read_text(encoding="utf-8").strip()
        return token or None
    except (OSError, UnicodeError) as exc:
        log.warning(
            "[gamedata] failed to read token file %s (%s: %s)",
            _TOKEN_FILE,
            type(exc).__name__,
            exc,
        )
        return None
    except Exception:
        log.exception("[gamedata] unexpected error reading token file %s", _TOKEN_FILE)
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

    存服务端先验比率（server_ 前缀；server > 0 时永久用服务端）：
      server_af_prior   ← AFq (active_rate / 10000) 再转 AF 比率
      server_wtsd_prior ← show_hand_rate / 10000

    不覆盖（服务端无此数据）：
      fold_to_cbet / fold_to_3bet / river_* / flop_* / turn_*
      showdown_count / flop_seen_count / showdown_win_count
      bet_win_count / bluff_win_count
    """
    play_times = int(data.get("play_times") or 0)
    if play_times <= 0:
        return False

    # ── 所有 rate 字段均 /10000（pool_entry_rate=9600 > play_times=25 实测证明）──
    vpip = max(0.0, min(1.0, (data.get("pool_entry_rate")           or 0) / 10000))
    pfr  = max(0.0, min(vpip, (data.get("add_before_flipping_rate") or 0) / 10000))
    wtsd = max(0.0, min(1.0, (data.get("show_hand_rate") or 0) / 10000))

    # active_rate 是百分比 AFq（见文件顶注释）。
    # 经验映射到 AF(A/C)：
    #   AF = AFq / ((1 - AFq) * R), R=C/(C+K+F)≈0.3109
    # 仍保留上限截断避免极端除零爆炸。
    afq = max(0.0, min(0.95, (data.get("active_rate") or 0) / 10000))
    af  = max(0.01, afq / max(1e-3, (1.0 - afq) * _AFQ_TO_AF_CALL_SHARE))

    # ── 直接替换：hands_seen 为原始次数，vpip/pfr 由 rate × play_times 精确还原 ─
    stats.hands_seen = play_times
    stats.vpip_count = round(vpip * play_times)
    stats.pfr_count  = round(pfr  * play_times)

    # ── 存服务端先验比率（server > 0 时永久覆盖本地）─────────────────────
    stats.server_af_prior   = af
    stats.server_wtsd_prior = wtsd

    return True
