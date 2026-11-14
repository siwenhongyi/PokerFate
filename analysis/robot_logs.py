"""Robots in the strategy logs (all sessions): replication of the hidden-card dependence on
accounts in the robot UID block, and what hero's lines actually earn against them.

    .venv/bin/python -m analysis.robot_logs pokerfate/logs/archive/2026-11-*.pokerfate.bak.log pokerfate/logs/pokerfate.log

Robots are identified with the registry built from the server's own ``rb_num`` counter
(pokerfate/core/robots.py; rebuild it from the wire log with ``python -m analysis.robot_wire
--write``): proven robots plus unproven accounts inside a robot UID block.

Sections
  1  hero's result by who sits at the table (robots only / mixed / none), before and after rake
  2  hidden-card test per UID block: opponents' first decision in an unopened pot, taken
     before hero has acted, against the strength of hero's hole cards
  3  hero at robot-only tables: result of voluntarily played hands by hole-card tier
  4  hero's open raises against robots: how they respond by tier
  5  heads-up vs one robot, nobody has bet: realised value of betting vs checking
"""
from __future__ import annotations

import math
import sys
from collections import Counter, defaultdict

from analysis.features import mean_se, wilson
from analysis.pflog import load
from analysis.rake import hand_money
from analysis.robot_report import fr, hand_percentile, tier
from analysis.robot_strength import hs_now

_REGISTRY = None


def is_robot(uid) -> bool:
    global _REGISTRY
    if _REGISTRY is None:
        from pokerfate.core.robots import RobotRegistry
        _REGISTRY = RobotRegistry(autosave=False)
    return _REGISTRY.is_robot(uid or 0)


def ms(xs, scale=1.0, unit=""):
    m, se, n = mean_se(xs)
    return f"{scale * m:+.2f} ± {scale * 1.96 * se:.2f}{unit} (n={n})" if n > 1 else f"n={n}"


def hero_rake_bb(h) -> float:
    hm = hand_money(h)
    if hm is None:
        return 0.0
    deltas, rake = hm
    win = sum(v for v in deltas.values() if v > 0)
    d = deltas.get(h["hero_name"], 0)
    return rake * d / win / h["bb"] if d > 0 and win > 0 and rake > 0 else 0.0


def opponents(h):
    return [p for p in h["players"] if p["name"] != h["hero_name"]]


def composition(hands):
    print("== 1 hero 的结果 × 同桌对手构成 ==")
    groups = defaultdict(list)
    for h in hands:
        opp = opponents(h)
        if not opp:
            continue
        nr = sum(is_robot(p["id"]) for p in opp)
        key = "全是机器人号段" if nr == len(opp) else "没有机器人号段" if nr == 0 else "混合"
        groups[key].append(h)
    for key in ("全是机器人号段", "混合", "没有机器人号段"):
        v = groups[key]
        if not v:
            continue
        paid = [hero_rake_bb(h) for h in v]
        post = [h["delta_bb"] for h in v]
        pre = [d + p for d, p in zip(post, paid)]
        print(f"  {key:8s} {len(v):5d} 手  抽水后 {ms(post, 100)} bb/100   抽水前 {ms(pre, 100)}   "
              f"被抽 {100 * sum(paid) / len(v):.1f}   桌型 {dict(Counter(h['n'] for h in v).most_common(3))}")
    return groups["全是机器人号段"]


def hidden_card_test(hands, P):
    print("\n== 2 对手在 hero 行动之前的首次入池决定 × hero 底牌强度（按 UID 号段）==")
    tab = defaultdict(lambda: defaultdict(Counter))
    for h in hands:
        idof = {p["name"]: p["id"] for p in h["players"]}
        t = tier(P(h["hole"]))
        for a in h["actions"]:
            if a["street"] != "preflop" or a["hero"]:
                break
            if a["act"] not in ("fold", "call", "raise"):
                continue
            if a.get("raises_before", 0) > 0:
                break
            if a["to_call"] > 0:
                tab["机器人号段" if is_robot(idof.get(a["who"])) else "其他账号"][t][a["act"]] += 1
            if a["act"] != "fold":
                break
    for grp in ("机器人号段", "其他账号"):
        print(f"  {grp}")
        for t in sorted(tab[grp]):
            c = tab[grp][t]
            n = sum(c.values())
            print(f"     hero 底牌 {t:8s} 弃 {fr(c['fold'], n):28s} 平跟 {100 * c['call'] / n:3.0f}%  加注 {100 * c['raise'] / n:3.0f}%")
        s, w = tab[grp]["1 前15%"], tab[grp]["4 后35%"]
        ns, nw = sum(s.values()), sum(w.values())
        if ns and nw:
            ps, pw = s["fold"] / ns, w["fold"] / nw
            se = math.sqrt(ps * (1 - ps) / ns + pw * (1 - pw) / nw)
            print(f"     前15% 与 后35% 的弃牌率之差 {100 * (ps - pw):+.0f} ± {196 * se:.0f} 个百分点  z={(ps - pw) / se:+.1f}")


def by_tier(robot_hands, P):
    print("\n== 3 全机器人桌：hero 自愿入池的牌 × 底牌档（相对直接弃牌，抽水后）==")
    posted = lambda h: 0.5 if h["hero_pos"] == "SB" else 1.0 if h["hero_pos"] == "BB" else 0.0
    total = 0.0
    for t in ("1 前15%", "2 15-35%", "3 35-65%", "4 后35%"):
        s = [h for h in robot_hands if tier(P(h["hole"])) == t]
        vp = [h for h in s if any(a["hero"] and a["street"] == "preflop" and a["act"] in ("call", "raise") for a in h["actions"])]
        gain = [h["delta_bb"] + posted(h) for h in vp]
        print(f"  {t:8s} 发到 {len(s):4d} 手，入池 {len(vp):3d} 手：每手 {ms(gain)} bb，合计 {sum(gain):+.0f}bb")
        if t != "1 前15%":
            total += sum(gain)
    print(f"  前15% 以外的入池牌合计 {total:+.0f}bb ≈ {-100 * total / len(robot_hands):+.1f} bb/100（全部不打时的理论改变量，未扣不确定性）")


def opens(robot_hands, P):
    print("\n== 4 全机器人桌：hero 无人入池时开池，机器人的反应 × hero 底牌档 ==")
    resp, gain = defaultdict(Counter), defaultdict(list)
    for h in robot_hands:
        pre = [a for a in h["actions"] if a["street"] == "preflop" and a["act"] in ("fold", "call", "raise", "check")]
        fh = next((a for a in pre if a["hero"]), None)
        if fh is None or fh["act"] != "raise" or not all(a["act"] == "fold" for a in pre if a["i"] < fh["i"]):
            continue
        seen, r = set(), []
        for a in pre:
            if a["i"] > fh["i"] and not a["hero"] and a["who"] not in seen:
                seen.add(a["who"])
                r.append(a["act"])
                if a["act"] == "raise":
                    break
        out = "全弃" if all(x == "fold" for x in r) else "被再加注" if "raise" in r else "被跟注"
        t = tier(P(h["hole"]))
        resp[t][out] += 1
        gain[t].append(h["delta_bb"] + (0.5 if h["hero_pos"] == "SB" else 1.0 if h["hero_pos"] == "BB" else 0.0))
    for t in sorted(resp):
        c = resp[t]
        n = sum(c.values())
        print(f"  {t:8s} n={n:3d}  全弃 {100 * c['全弃'] / n:3.0f}%  被跟 {100 * c['被跟注'] / n:3.0f}%  被再加注 {100 * c['被再加注'] / n:3.0f}%"
              f"   相对弃牌每次 {ms(gain[t])} bb")


def bet_vs_check(robot_hands):
    print("\n== 5 全机器人桌、单挑一个机器人、无人下注：下注 vs 过牌 从该决策往后的净得（单位：当时底池）==")
    rows = []
    for h in robot_hands:
        bb, hero = h["bb"], h["hero_name"]
        inv_total = h["invested"].get(hero, 0.0)
        full = h["board"].get("flop", []) + h["board"].get("turn", []) + h["board"].get("river", [])
        board = {"flop": full[:3], "turn": full[:4], "river": full[:5]}
        folded, street, acted, acts = set(), None, set(), h["actions"]
        for idx, a in enumerate(acts):
            if a["street"] != street:
                street, acted = a["street"], set()
            if a["hero"] and street != "preflop" and a["act"] in ("check", "raise") and a["to_call"] == 0 \
                    and len(board[street]) >= 3 and a["pot_before"] > 0:
                live = [p["name"] for p in h["players"] if p["name"] not in folded and p["name"] != hero]
                if len(live) == 1:
                    later = sum(x["add"] for x in acts[idx:] if x["hero"] and x["act"] in ("call", "raise"))
                    rows.append(dict(street=street, bet=a["act"] == "raise", ip=live[0] in acted,
                                     hs=hs_now(h["hole"], board[street]), pot=a["pot_before"] / bb,
                                     r=(h["delta_bb"] * bb + inv_total - later) / a["pot_before"]))
            acted.add(a["who"])
            if a["act"] == "fold":
                folded.add(a["who"])
    n_hands = len(robot_hands)

    def line(label, sel):
        s = [r for r in rows if sel(r)]
        bet = [r["r"] for r in s if r["bet"]]
        chk = [r["r"] for r in s if not r["bet"]]
        if len(bet) < 2 or len(chk) < 2:
            print(f"  {label:26s} 样本不足 (bet {len(bet)}, check {len(chk)})")
            return
        mb, sb, nb = mean_se(bet)
        mc, sc, nc = mean_se(chk)
        d, sd = mb - mc, math.sqrt(sb ** 2 + sc ** 2)
        pot = sum(r["pot"] for r in s if not r["bet"]) / nc
        k = pot * nc / n_hands * 100
        print(f"  {label:26s} 下注 {mb:+.2f} (n={nb:3d})  过牌 {mc:+.2f} (n={nc:3d})  差 {d:+.2f} ± {1.96 * sd:.2f}"
              f"  | 过牌时均池 {pot:4.1f}bb → 全改下注 ≈ {d * k:+.1f} bb/100 [{(d - 1.96 * sd) * k:+.1f}, {(d + 1.96 * sd) * k:+.1f}]")

    early = lambda r: r["street"] in ("flop", "turn")
    line("翻牌/转牌 弱牌 无位置", lambda r: early(r) and r["hs"] < .6 and not r["ip"])
    line("翻牌/转牌 弱牌 有位置", lambda r: early(r) and r["hs"] < .6 and r["ip"])
    line("  其中 翻牌 无位置 很弱(<.35)", lambda r: r["street"] == "flop" and r["hs"] < .35 and not r["ip"])
    line("河牌 弱牌", lambda r: r["street"] == "river" and r["hs"] < .6)
    line("各街 中等牌(.60-.80)", lambda r: .6 <= r["hs"] < .8)
    line("各街 强牌(>=.80)", lambda r: r["hs"] >= .8)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    hands, _ = load(argv)
    hands = [h for h in hands if h.get("hole") and len(h["hole"]) == 2 and h.get("delta_bb") is not None and h.get("actions")]
    print(f"{len(hands)} 手；对手账号中机器人号段 "
          f"{len({p['id'] for h in hands for p in opponents(h) if is_robot(p['id'])})} 个\n")
    P = hand_percentile()
    robot_hands = composition(hands)
    hidden_card_test(hands, P)
    by_tier(robot_hands, P)
    opens(robot_hands, P)
    bet_vs_check(robot_hands)


if __name__ == "__main__":
    main()
