"""Rake economics from the logs: what the house takes, from whom, and what hero's result
would be under other rake structures (same hands, same actions - pure arithmetic).

Exact rake per hand = -(sum of every player's stack change), taken from hand_start stacks and
hand_result.final_stacks, so it needs no assumption about the rake rule.

    .venv/bin/python -m analysis.rake pokerfate/logs/archive/*.pokerfate.bak.log pokerfate/logs/pokerfate.log [--since ISO]
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict

from analysis import pflog
from analysis.features import mean_se


def hand_money(h):
    """Per-player stack change (chips) and the exact rake of one hand, or None if the stack
    bookkeeping of that hand is unusable (player missing from final_stacks, mid-hand top-up)."""
    res = h.get("result")
    if not res:
        return None
    fs = res.get("final_stacks") or {}
    winners = set(res.get("winners") or [])
    deltas = {}
    for p in h["players"]:
        name = p["name"]
        if name in fs:
            deltas[name] = float(fs[name]) - float(p["stack"])
        elif name not in winners and name in (h.get("invested") or {}):
            # A player who busts and leaves is dropped from final_stacks; he lost exactly
            # what he put in. Dropping these hands would remove hero's biggest wins.
            deltas[name] = -float(h["invested"][name])
        else:
            return None
    rake = -sum(deltas.values())
    return deltas, rake


def collect(hands):
    rows = []
    bad = Counter()
    for h in hands:
        if not h.get("result") or h.get("street_mismatch"):
            continue
        hm = hand_money(h)
        if hm is None:
            bad["missing_final_stack"] += 1
            continue
        deltas, rake = hm
        bb = h["bb"]
        hero = h["hero_name"]
        pot = h.get("pot_contested_recon") or 0.0
        # sanity: the house never pays in, and never takes more than 9% of the whole pot
        moved = sum(-d for d in deltas.values() if d < 0)
        recon_total = float(h.get("pot_final_recon") or 0.0)
        if rake < -0.02 * bb or rake > 0.095 * max(recon_total, 2.0 * moved) + 0.02 * bb:
            bad["rake_out_of_range"] += 1
            continue
        if hero in deltas and h.get("dealt") and abs(deltas[hero] - res_delta(h)) > 2.0:
            bad["hero_delta_mismatch"] += 1
            continue
        winners = [n for n, d in deltas.items() if d > 0]
        gross_win = sum(d for d in deltas.values() if d > 0)
        hero_paid = 0.0
        if hero in winners and gross_win > 0:
            hero_paid = rake * deltas[hero] / gross_win  # winner(s) bear the rake pro rata
        rows.append(dict(key=h["key"], ts=h["ts"], n=h["n"], bb=bb, rake=rake / bb, moved=moved / bb,
                         saw_flop="flop" in h["board"], hero_dealt=bool(h.get("dealt")),
                         hero_delta=(deltas.get(hero, 0.0) / bb) if h.get("dealt") else 0.0,
                         hero_paid=hero_paid / bb, hero_won=hero in winners,
                         pot_pre_rake=(moved + 0.0) / bb,  # money lost by losers = winners' gross + rake
                         deltas={k: v / bb for k, v in deltas.items()}, hero=hero))
    return rows, bad


def res_delta(h):
    return float(h["result"]["my_delta"])


def alt_rake(row, rate, cap_bb, no_flop_no_drop):
    """Rake of this hand under another structure. The raked amount is the money the losers
    put in plus the winners' own matched share; we recover it from the actual rake when the
    actual rule (9% uncapped) applied, and fall back to 0 for unraked hands (chops)."""
    if row["rake"] <= 1e-9:
        return 0.0
    if no_flop_no_drop and not row["saw_flop"]:
        return 0.0
    base = row["rake"] / 0.09  # contested pot in bb
    r = rate * base
    if cap_bb is not None:
        r = min(r, cap_bb)
    return r


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("logs", nargs="+")
    ap.add_argument("--since", default="")
    args = ap.parse_args(argv)
    hands, _ = pflog.load(args.logs)
    pflog.validate(hands)
    hands = [h for h in hands if (h["ts"] or "") >= args.since]
    rows, bad = collect(hands)
    n = len(rows)
    print(f"可用手数 {n}（剔除 {dict(bad)}）  {rows[0]['ts'][:16]} → {rows[-1]['ts'][:16]}")
    total_rake = sum(r["rake"] for r in rows)
    seat_hands = sum(r["n"] for r in rows)
    raked = [r for r in rows if r["rake"] > 1e-6]
    ratio = sorted(r["rake"] / r["moved"] for r in raked if r["moved"] > 0)
    print(f"\n== 全桌 ==")
    print(f"  每 100 手全桌被抽走 {100 * total_rake / n:.1f}bb；平均每手 {seat_hands / n:.2f} 人 → 平均每个座位 {100 * total_rake / seat_hands:.1f} bb/100")
    print(f"  有抽水的手 {len(raked)}/{n}；抽水 / 输家损失 的中位数 {ratio[len(ratio) // 2]:.3f}")
    pre = [r for r in rows if not r["saw_flop"]]
    print(f"  翻前结束的手 {len(pre)} ({100 * len(pre) / n:.0f}%)，贡献抽水 {100 * sum(r['rake'] for r in pre) / total_rake:.1f}%")
    for lo, hi in ((0, 10), (10, 33.4), (33.4, 100), (100, 1e9)):
        rs = [r for r in raked if lo <= r["rake"] / 0.09 < hi]
        print(f"  底池 {lo:g}–{hi if hi < 1e8 else '∞'}bb: {len(rs):5d} 手，贡献抽水 {100 * sum(r['rake'] for r in rs) / total_rake:5.1f}%")

    hero_rows = [r for r in rows if r["hero_dealt"]]
    nh = len(hero_rows)
    hd = [r["hero_delta"] for r in hero_rows]
    m, se, _ = mean_se(hd)
    paid = sum(r["hero_paid"] for r in hero_rows)
    opp_delta = 0.0
    opp_seats = 0
    for r in hero_rows:
        for name, d in r["deltas"].items():
            if name != r["hero"]:
                opp_delta += d
                opp_seats += 1
    print(f"\n== hero vs 对手池（hero 有牌的 {nh} 手）==")
    print(f"  hero: {100 * m:+.1f} ± {196 * se:.1f} bb/100；hero 赢下的底池被抽 {100 * paid / nh:.1f} bb/100 → 抽水前 {100 * (sum(hd) + paid) / nh:+.1f} bb/100")
    print(f"  对手池平均每个座位: {100 * opp_delta / opp_seats:+.1f} bb/100（{opp_seats} 个座位·手）")
    print(f"  同桌全部座位平均: {100 * (opp_delta + sum(hd)) / (opp_seats + nh):+.1f} bb/100  ← 这就是抽水摊到每个人头上的成本")
    for size in (2, 3, 4, 5, 6):
        rs = [r for r in hero_rows if r["n"] == size]
        if len(rs) < 100:
            continue
        hm_, hse, _ = mean_se([r["hero_delta"] for r in rs])
        od = sum(d for r in rs for nme, d in r["deltas"].items() if nme != r["hero"])
        os_ = sum(len(r["deltas"]) - 1 for r in rs)
        tr = sum(r["rake"] for r in rs)
        print(f"    {size}人桌 n={len(rs):5d}: hero {100 * hm_:+6.1f} ± {196 * hse:5.1f} | 对手均值 {100 * od / os_:+6.1f} | 每座位抽水成本 {100 * tr / (len(rs) * size):5.1f} | hero 被抽 {100 * sum(r['hero_paid'] for r in rs) / len(rs):5.1f} bb/100")

    print(f"\n== 同样的牌、同样的打法，换一种抽水结构 hero 的结果（纯算术，不含策略变化）==")
    structures = [
        ("现状：9% 无上限，翻前也抽", 0.09, None, False),
        ("9% 无上限，翻前不抽", 0.09, None, True),
        ("9% 封顶 3bb，翻前也抽", 0.09, 3.0, False),
        ("9% 封顶 1bb，翻前也抽", 0.09, 1.0, False),
        ("5% 封顶 3bb，翻前不抽（常见线上结构）", 0.05, 3.0, True),
        ("无抽水", 0.0, None, False),
    ]
    for label, rate, cap, nfnd in structures:
        tot = 0.0
        paid_alt = 0.0
        for r in hero_rows:
            alt = alt_rake(r, rate, cap, nfnd)
            share = (r["hero_paid"] / r["rake"]) if r["rake"] > 1e-9 else 0.0
            tot += r["hero_delta"] + r["hero_paid"] - alt * share
            paid_alt += alt * share
        print(f"  {label:<34} hero 被抽 {100 * paid_alt / nh:5.1f} bb/100 → 结果 {100 * tot / nh:+6.1f} ± {196 * se:.1f} bb/100")


if __name__ == "__main__":
    main()
