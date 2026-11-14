"""Where hero's money comes from and goes, before and after rake, by situation.

    .venv/bin/python -m analysis.breakdown pokerfate/logs/archive/*.pokerfate.bak.log pokerfate/logs/pokerfate.log [--since ISO]

"抽水前" = hero's result plus the rake taken out of the pots he won. A family that is positive
before rake and negative after it is one the rake structure makes unprofitable; a family that
is negative before rake is a playing leak.
"""
from __future__ import annotations

import argparse
from collections import defaultdict

from analysis import pflog
from analysis.features import mean_se, preflop_spots
from analysis.rake import collect


def hero_preflop_line(h) -> str:
    spots = [s for s in preflop_spots(h) if s["hero"]]
    if not spots:
        return "未行动(walk等)"
    first = spots[0]
    acts = [s["act"] for s in spots]
    saw_flop = h["hero_name"] in (h.get("flop_players") or [])
    if first["act"] == "fold":
        return {"unopened": "弃牌·无人入池", "limped": "弃牌·面对limp", "vs_open": "弃牌·面对open"}.get(first["sit"], "弃牌·面对3bet+")
    if first["act"] == "check":
        return "BB免费看牌(limp池)"
    if first["act"] == "raise":
        if first["sit"] == "unopened":
            if len(spots) > 1:
                return "open后遇3bet·" + ("弃" if spots[1]["act"] == "fold" else ("跟" if spots[1]["act"] == "call" else "4bet"))
            return "open·" + ("进翻牌" if saw_flop else "翻前拿下")
        if first["sit"] == "limped":
            return "隔离加注·" + ("进翻牌" if saw_flop else "翻前结束")
        if first["sit"] == "vs_open":
            return "3bet"
        return "4bet+"
    if first["act"] == "call":
        if first["sit"] == "limped":
            return "跟limp/补盲"
        if first["sit"] == "vs_open":
            return "跟注open" + ("(BB)" if first["pos"] == "BB" else "(非BB)")
        return "冷跟3bet+"
    return "其他"


def table(rows, key_fn, title, min_n=30):
    groups = defaultdict(list)
    for r in rows:
        groups[key_fn(r)].append(r)
    total_n = len(rows)
    print(f"\n== {title} ==")
    print(f"  {'场景':<26} {'手数':>6} {'占比':>5} {'净bb':>9} {'被抽bb':>8} {'抽水前bb':>9} {'每手(后)':>9} {'每手(前)':>9}  对总bb/100的贡献(后/前)")
    out = []
    for k, rs in groups.items():
        n = len(rs)
        net = sum(r["hero_delta"] for r in rs)
        paid = sum(r["hero_paid"] for r in rs)
        m, se, _ = mean_se([r["hero_delta"] for r in rs])
        mp, sep, _ = mean_se([r["hero_delta"] + r["hero_paid"] for r in rs])
        out.append((k, n, net, paid, m, se, mp, sep))
    for k, n, net, paid, m, se, mp, sep in sorted(out, key=lambda x: x[2]):
        flag = " 低置信" if n < min_n else ""
        print(f"  {str(k):<26} {n:6d} {100 * n / total_n:4.0f}% {net:9.1f} {paid:8.1f} {net + paid:9.1f} {m:+6.2f}±{1.96 * se if se == se else 0:4.2f} {mp:+6.2f}±{1.96 * sep if sep == sep else 0:4.2f}  {100 * net / total_n:+6.1f} / {100 * (net + paid) / total_n:+6.1f}{flag}")
    net = sum(r["hero_delta"] for r in rows)
    paid = sum(r["hero_paid"] for r in rows)
    print(f"  {'合计':<26} {total_n:6d} 100% {net:9.1f} {paid:8.1f} {net + paid:9.1f}  {'':>22}  {100 * net / total_n:+6.1f} / {100 * (net + paid) / total_n:+6.1f}")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("logs", nargs="+")
    ap.add_argument("--since", default="")
    ap.add_argument("--players", default="", help="comma list of table sizes to keep, e.g. 2,3")
    args = ap.parse_args(argv)
    hands, _ = pflog.load(args.logs)
    pflog.validate(hands)
    hands = [h for h in hands if (h["ts"] or "") >= args.since]
    by_key = {h["key"] + "|" + str(h["ts"]): h for h in hands}
    rake_rows, _bad = collect(hands)
    rows = []
    for r in rake_rows:
        if not r["hero_dealt"]:
            continue
        h = by_key.get(r["key"] + "|" + str(r["ts"]))
        if h is None:
            continue
        r = dict(r, pos=h["hero_pos"], line=hero_preflop_line(h), stack=h["hero_stack_bb"],
                 saw=h["hero_name"] in (h.get("flop_players") or []), n_flop=len(h.get("flop_players") or []))
        rows.append(r)
    if args.players:
        keep = {int(x) for x in args.players.split(",")}
        rows = [r for r in rows if r["n"] in keep]
    print(f"hero 有牌的手 {len(rows)}  {rows[0]['ts'][:16]} → {rows[-1]['ts'][:16]}")
    table(rows, lambda r: r["line"], "按 hero 翻前路线")
    table(rows, lambda r: f"{min(r['n'], 4) if r['n'] < 4 else ('4人' if r['n'] == 4 else '5-6人')}".replace("2", "2人").replace("3", "3人") if r["n"] < 4 else ("4人" if r["n"] == 4 else "5-6人"), "按桌人数")
    table(rows, lambda r: r["pos"], "按位置")
    table([r for r in rows if r["saw"]], lambda r: ("单挑" if r["n_flop"] == 2 else "多人") + "翻牌·" + ("limp池" if r["line"].startswith(("BB免费", "跟limp")) else ("hero进攻" if r["line"].startswith(("open", "隔离", "3bet", "4bet")) else "hero跟注")), "看到翻牌的手：按翻牌人数 × hero 翻前角色")


if __name__ == "__main__":
    main()
