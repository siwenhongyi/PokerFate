"""Core frequency / result statistics for hero and for the opponent pool.

    .venv/bin/python -m analysis.overview pokerfate/logs/pokerfate.log
    .venv/bin/python -m analysis.overview <log> [<log> ...] --section preflop

Every rate is printed with its opportunity count n and a Wilson 95% interval;
n < 30 is tagged 低置信.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict

from analysis import pflog
from analysis.features import (fmt_rate, mean_se, pot_type, preflop_spots, postflop_spots, usable,
                               hero_ip_flags, size_bucket)


def table_group(n: int) -> str:
    return {2: "2人", 3: "3人"}.get(n, "4人" if n == 4 else "5-6人")


def results(hands):
    print("\n== 整体结果（bb；95% 区间按每手标准差估）==")

    def line(label, hs):
        xs = [h["delta_bb"] for h in hs]
        m, se, n = mean_se(xs)
        if n < 2:
            print(f"  {label:<22} n={n}")
            return
        sd = se * (n ** 0.5)
        print(f"  {label:<22} n={n:5d}  净 {sum(xs):9.1f}bb  {100 * m:7.1f} ± {196 * se:5.1f} bb/100  (每手σ={sd:5.1f}bb)")

    line("全部", hands)
    for g in ("2人", "3人", "4人", "5-6人"):
        line(f"桌人数 {g}", [h for h in hands if table_group(h["n"]) == g])
    for pos in ("UTG", "MP", "CO", "BTN", "SB", "BB"):
        line(f"位置 {pos}", [h for h in hands if h["hero_pos"] == pos])
    sd = [h for h in hands if h["hero_at_showdown"]]
    nsd = [h for h in hands if not h["hero_at_showdown"]]
    line("摊牌（蓝线）", sd)
    line("非摊牌（红线）", nsd)
    hero_vpip = []
    for h in hands:
        hero = h["hero_name"]
        v = any(a["hero"] and a["street"] == "preflop" and a["act"] in ("call", "raise") for a in h["actions"])
        hero_vpip.append(v)
    line("hero 入池的手", [h for h, v in zip(hands, hero_vpip) if v])
    line("hero 未入池的手", [h for h, v in zip(hands, hero_vpip) if not v])
    for pt in ("limped", "SRP", "3bet", "4bet+"):
        line(f"入池·{pt}", [h for h, v in zip(hands, hero_vpip) if v and pot_type(h) == pt])
    saw = [h for h in hands if h["hero_name"] in h["flop_players"]]
    line("hero 看到翻牌", saw)
    line("  其中翻牌单挑", [h for h in saw if len(h["flop_players"]) == 2])
    line("  其中翻牌多人", [h for h in saw if len(h["flop_players"]) > 2])
    stacks = sorted(h["hero_stack_bb"] for h in hands)
    q = lambda p: stacks[int(p * (len(stacks) - 1))]
    print(f"  hero 起手筹码(bb) 分位: 10%={q(.1):.0f} 25%={q(.25):.0f} 50%={q(.5):.0f} 75%={q(.75):.0f} 90%={q(.9):.0f}")


def preflop(hands):
    """VPIP/PFR/RFI/3bet/... for hero and for the pool, split by table size."""
    acc = defaultdict(lambda: [0, 0])  # (who, group, metric, pos) -> [k, n]

    def add(who, grp, metric, pos, hit):
        for g in (grp, "全部"):
            for p in (pos, "ALL"):
                c = acc[(who, g, metric, p)]
                c[1] += 1
                c[0] += 1 if hit else 0

    for h in hands:
        grp = table_group(h["n"])
        spots = preflop_spots(h)
        by_player = defaultdict(list)
        for s in spots:
            by_player[s["who"]].append(s)
        raises_total = h["pf_raises"]
        for p in h["players"]:
            nm = p["name"]
            who = "hero" if nm == h["hero_name"] else "pool"
            ss = by_player.get(nm, [])
            pos = p["pos"]
            if not ss:
                continue  # never had to act (walk for BB, or hand ended before)
            vpip = any(s["act"] in ("call", "raise") for s in ss)
            pfr = any(s["act"] == "raise" for s in ss)
            add(who, grp, "VPIP", pos, vpip)
            add(who, grp, "PFR", pos, pfr)
            first = ss[0]
            if first["sit"] == "unopened" and pos != "BB":
                add(who, grp, "RFI(无人入池时加注)", pos, first["act"] == "raise")
                add(who, grp, "open-limp(无人入池时平跟)", pos, first["act"] == "call")
            if first["sit"] == "limped":
                add(who, grp, "面对limp:加注(iso)", pos, first["act"] == "raise")
                if pos != "BB":
                    add(who, grp, "面对limp:跟(limp-behind/补盲)", pos, first["act"] == "call")
            if first["sit"] == "vs_open":
                add(who, grp, "面对open:3bet", pos, first["act"] == "raise")
                add(who, grp, "面对open:跟注", pos, first["act"] == "call")
                add(who, grp, "面对open:弃牌", pos, first["act"] == "fold")
            for s in ss:
                if s["sit"] == "vs_3bet" and s["opener"] == nm and not s["first_action"]:
                    add(who, grp, "open后面对3bet:弃牌", pos, s["act"] == "fold")
                    add(who, grp, "open后面对3bet:4bet", pos, s["act"] == "raise")
                    add(who, grp, "open后面对3bet:跟注", pos, s["act"] == "call")
                if s["sit"] == "vs_3bet" and s["first_action"]:
                    add(who, grp, "冷面对3bet:继续", pos, s["act"] != "fold")
    order = ["VPIP", "PFR", "RFI(无人入池时加注)", "open-limp(无人入池时平跟)", "面对limp:加注(iso)",
             "面对limp:跟(limp-behind/补盲)", "面对open:3bet", "面对open:跟注", "面对open:弃牌",
             "open后面对3bet:弃牌", "open后面对3bet:4bet", "open后面对3bet:跟注", "冷面对3bet:继续"]
    for grp in ("全部", "2人", "3人", "4人", "5-6人"):
        print(f"\n== 翻前 · 桌人数 {grp} ==")
        for metric in order:
            print(f"  -- {metric}")
            for pos in ("ALL", "UTG", "MP", "CO", "BTN", "SB", "BB"):
                hk = acc.get(("hero", grp, metric, pos))
                pk = acc.get(("pool", grp, metric, pos))
                if not hk and not pk:
                    continue
                hs = fmt_rate(*hk) if hk else "–"
                ps = fmt_rate(*pk) if pk else "–"
                print(f"     {pos:<4} hero {hs:<38} pool {ps}")


def postflop(hands):
    acc = defaultdict(lambda: [0, 0])

    def add(who, key, hit):
        c = acc[(who, key)]
        c[1] += 1
        c[0] += 1 if hit else 0

    agg = defaultdict(Counter)  # (who, street) -> Counter of bet/raise/call/fold/check
    wtsd = defaultdict(lambda: [0, 0])
    wsd = defaultdict(lambda: [0, 0])
    for h in hands:
        hero = h["hero_name"]
        spots = postflop_spots(h)
        mw = len(h["flop_players"]) > 2
        tag_mw = "多人" if mw else "单挑"
        # WTSD / W$SD
        for nm in h["flop_players"]:
            who = "hero" if nm == hero else "pool"
            at_sd = h["showdown"] and nm in h["remaining"]
            wtsd[who][1] += 1
            wtsd[who][0] += 1 if at_sd else 0
            if at_sd:
                wsd[who][1] += 1
                wsd[who][0] += 1 if nm in h["result"]["winners"] else 0
        seen_first_bet_opp = set()
        for s in spots:
            who = "hero" if s["hero"] else "pool"
            st = s["street"]
            agg[(who, st)][s["kind"]] += 1
            agg[(who, "all")][s["kind"]] += 1
            hu_now = s["n_active"] == 2
            now = "单挑" if hu_now else "多人"
            if not s["facing"]:
                # first-in opportunity (nobody has bet this street)
                if s["bets_before"] == 0:
                    if st == "flop" and s["is_pfr"] and s["ptype"] in ("SRP", "3bet", "4bet+"):
                        add(who, f"flop c-bet（翻前进攻者，{now}）", s["kind"] == "bet")
                    elif st == "flop" and s["ptype"] == "limped":
                        add(who, f"flop 首次下注（limp池，{now}）", s["kind"] == "bet")
                    elif st == "flop":
                        add(who, f"flop 非进攻者领打/过牌后下注（{now}）", s["kind"] == "bet")
                    if st in ("turn", "river"):
                        if s["prev_aggr"]:
                            add(who, f"{st} 持续开火（上街进攻者，{now}）", s["kind"] == "bet")
                        else:
                            add(who, f"{st} 首次下注（非上街进攻者，{now}）", s["kind"] == "bet")
            else:
                first_bet = s["bets_before"] == 1
                szb = size_bucket(s["bet_frac"])
                if first_bet:
                    add(who, f"{st} 面对下注:弃牌（{now}）", s["act"] == "fold")
                    add(who, f"{st} 面对下注:加注（{now}）", s["act"] == "raise")
                    add(who, f"{st} 面对下注[{szb}]:弃牌（{now}）", s["act"] == "fold")
                    if s["checked_before"]:
                        add(who, f"{st} check后面对下注:加注(check-raise)", s["act"] == "raise")
                else:
                    add(who, f"{st} 面对加注:弃牌", s["act"] == "fold")
    print("\n== 翻后 · 频率（hero vs pool）==")
    keys = sorted({k for (_w, k) in acc})
    for k in keys:
        hk = acc.get(("hero", k))
        pk = acc.get(("pool", k))
        print(f"  {k}")
        print(f"       hero {fmt_rate(*hk) if hk else '–':<40} pool {fmt_rate(*pk) if pk else '–'}")
    print("\n== 进攻性 ==")
    for who in ("hero", "pool"):
        for st in ("flop", "turn", "river", "all"):
            c = agg[(who, st)]
            br = c["bet"] + c["raise"]
            af = br / c["call"] if c["call"] else float("nan")
            tot = br + c["call"] + c["fold"]
            afq = br / tot if tot else float("nan")
            print(f"  {who:<4} {st:<5} bet={c['bet']:4d} raise={c['raise']:4d} call={c['call']:4d} fold={c['fold']:4d} check={c['check']:4d}  AF={af:4.2f}  AFq={100 * afq:4.1f}%")
    print("\n== 摊牌 ==")
    for who in ("hero", "pool"):
        print(f"  {who:<4} WTSD {fmt_rate(*wtsd[who])}   W$SD {fmt_rate(*wsd[who])}")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("logs", nargs="+")
    ap.add_argument("--section", default="all", choices=["all", "results", "preflop", "postflop"])
    args = ap.parse_args(argv)
    hands, _ = pflog.load(args.logs)
    pflog.validate(hands)
    hands = [h for h in hands if usable(h)]
    print(f"可用手数 {len(hands)}  时间 {hands[0]['ts'][:19]} → {hands[-1]['ts'][:19]}")
    print("桌人数分布:", dict(sorted(Counter(h["n"] for h in hands).items())))
    if args.section in ("all", "results"):
        results(hands)
    if args.section in ("all", "preflop"):
        preflop(hands)
    if args.section in ("all", "postflop"):
        postflop(hands)


if __name__ == "__main__":
    main()
