"""Behaviour profile of the confirmed robots, from the pure-robot hand export.

    .venv/bin/python -m analysis.robot_report [docs/pure_robot_hands_YYYY-MM-DD.jsonl]

Sections
  1  sample check (must reproduce the numbers of the export's own report)
  2  preflop frequencies by spot
  3  postflop: bet frequency / sizes / response to bets, split by who the robot is playing
     against (another robot vs hero)
  4  how much the robot's own cards matter (hands shown at showdown)
  5  does the robot's action depend on hero's hidden cards?  (position-controlled: only robot
     decisions taken before hero has acted in the hand)
"""
from __future__ import annotations

import sys
from collections import Counter, defaultdict

import numpy as np

from analysis.features import wilson
from analysis.preflop_price import cls_of, combos_of, rank_classes
from analysis.robot_strength import CLS_ORDER, coarse, describe
from analysis.robots import DEFAULT_PATH, HERO, load, size_tier


def fr(k, n):
    if n == 0:
        return "n=0"
    lo, hi = wilson(k, n)
    return f"{k}/{n}={100 * k / n:.0f}% [{100 * lo:.0f},{100 * hi:.0f}]"


def hand_percentile():
    """Hole-card class -> share of all combos that are stronger (0 = best, 1 = worst)."""
    order = rank_classes(iters=1500)
    tot, pct = 0, {}
    for c in order:
        n = len(combos_of(c))
        pct[c] = (tot + n / 2) / 1326
        tot += n
    return lambda cards: pct[cls_of(cards[0], cards[1])]


def tier(p):
    return "1 前15%" if p < .15 else "2 15-35%" if p < .35 else "3 35-65%" if p < .65 else "4 后35%"


def logit_slope(xs, ys):
    X = np.column_stack([np.ones(len(xs)), xs])
    y = np.array(ys, float)
    b = np.zeros(2)
    for _ in range(50):
        p = 1 / (1 + np.exp(-X @ b))
        hm = (X * (p * (1 - p))[:, None]).T @ X + 1e-9 * np.eye(2)
        b += np.linalg.solve(hm, X.T @ (y - p))
    se = np.sqrt(np.diag(np.linalg.inv(hm)))
    return b[1], se[1]


def hero_live(h, a):
    return not any(b["hero"] and b["kind"] == "fold" and b["i"] < a["i"] for b in h["acts"])


# ---------------------------------------------------------------------------
def sample(hands):
    print("== 1 样本 ==")
    n_seat = sum(len(h["seats"]) - 1 for h in hands)
    print(f"手数 {len(hands)}  {dict(Counter(h['group'] for h in hands))}  机器人座位·手 {n_seat}")
    net = sum(h["hero_net"] for h in hands)
    rake = sum(h["table_rake"] for h in hands)
    paid = sum(h["hero_rake"] for h in hands)
    print(f"hero 净 {net:+.1f}bb ({100 * net / len(hands):+.1f} bb/100)，全桌抽水 {rake:.0f}bb"
          f"（每 100 手 {100 * rake / len(hands):.0f}bb），hero 被抽 {paid:.0f}bb；"
          f"机器人每座位 {100 * (-net - rake) / n_seat:+.1f} bb/100")
    sd = [h for h in hands if h["show"]]
    print(f"摊牌 {len(sd)} 手：机器人之间 {sum(1 for h in sd if HERO not in h['show'])}，含 hero "
          f"{sum(1 for h in sd if HERO in h['show'])}；亮出的机器人底牌 "
          f"{sum(len([u for u in h['show'] if u != HERO]) for h in sd)} 组")
    first, cnt = {}, Counter()
    for h in hands:
        for s in h["seats"].values():
            if s["uid"] != HERO:
                cnt[s["uid"]] += 1
                first.setdefault(s["uid"], s["stack"] / 1e4)
    c = Counter(cnt.values())
    print(f"账号 {len(cnt)} 个；同桌满 29-30 手后离开的 {c[29] + c[30]} 个；"
          f"首次出现时筹码中位数 {sorted(first.values())[len(first) // 2]:.0f}bb")


def preflop(hands):
    print("\n== 2 翻前（只算机器人的行动）==")
    rows = []
    for h in hands:
        n_raise, raiser, raise_to, limp, acted = 0, None, 1.0, 0, set()
        for a in h["acts"]:
            if a["st"] != 1:
                break
            if not a["hero"]:
                rows.append(dict(h=h, a=a, n_raise=n_raise, limp=limp, first=a["seat"] not in acted,
                                 by_hero=raiser is not None and h["seats"][raiser]["uid"] == HERO,
                                 raise_to=raise_to))
            acted.add(a["seat"])
            if a["kind"] == "raise":
                n_raise, raiser, raise_to = n_raise + 1, a["seat"], a["raise_to"]
            elif a["kind"] == "call" and n_raise == 0:
                limp += 1

    def line(label, sel):
        c, s = Counter(), Counter()
        for r in rows:
            if sel(r):
                c[r["a"]["kind"]] += 1
                if r["a"]["kind"] == "raise":
                    s[round(r["a"]["raise_to"], 1)] += 1
        n = sum(c.values())
        if n:
            parts = " ".join(f"{k} {100 * c[k] / n:.0f}%" for k in ("fold", "check", "call", "raise") if c[k])
            print(f"  {label:34s} n={n:4d}  {parts}   加注到(bb) {dict(s.most_common(4))}")

    reg = lambda r: r["h"]["regular"]
    line("单挑 SB 首先行动", lambda r: reg(r) and r["h"]["group"] == "HU" and r["a"]["pos"] == "SB" and r["a"]["first_in"] and r["first"])
    line("三人 BTN 首先行动", lambda r: reg(r) and r["h"]["group"] == "3way" and r["a"]["pos"] == "BTN" and r["a"]["first_in"] and r["first"])
    line("三人 SB，前面全弃", lambda r: reg(r) and r["h"]["group"] == "3way" and r["a"]["pos"] == "SB" and r["a"]["first_in"] and r["first"])
    line("三人 SB，面对一个平跟", lambda r: reg(r) and r["a"]["pos"] == "SB" and r["n_raise"] == 0 and r["limp"] == 1 and r["first"])
    line("BB 面对平跟（可免费看牌）", lambda r: reg(r) and r["a"]["pos"] == "BB" and r["n_raise"] == 0 and r["a"]["to_call"] == 0)
    line("首次行动，面对 hero 的加注", lambda r: r["n_raise"] == 1 and r["first"] and r["by_hero"])
    line("首次行动，面对机器人的加注", lambda r: r["n_raise"] == 1 and r["first"] and not r["by_hero"])
    line("平跟后被 hero 加注", lambda r: r["n_raise"] == 1 and not r["first"] and r["by_hero"])
    line("平跟后被机器人加注", lambda r: r["n_raise"] == 1 and not r["first"] and not r["by_hero"])
    line("面对再加注（3bet 以上）", lambda r: r["n_raise"] >= 2)


def postflop(hands):
    print("\n== 3 翻后：机器人之间 vs 对 hero ==")
    bet, size, face = defaultdict(Counter), defaultdict(Counter), defaultdict(Counter)
    for h in hands:
        for a in h["acts"]:
            if a["st"] == 1 or a["hero"]:
                continue
            if a["to_call"] == 0:
                mode = "hero 仍在池中" if hero_live(h, a) else "只剩机器人"
                bet[(mode, a["street"])]["bet" if a["kind"] == "bet" else "check"] += 1
                if a["kind"] == "bet":
                    size[mode][size_tier(a["frac"])] += 1
            else:
                who = "下注者是 hero" if a["facing_hero"] else "下注者是机器人"
                face[(who, "全部")][a["kind"]] += 1
                face[(who, a["street"])][a["kind"]] += 1
                if a["n_raises_street"] == 1:
                    ff = a.get("faced_frac") or 0
                    z = "≤40%池" if ff <= .4 else "40-58%" if ff <= .58 else "58-80%" if ff <= .8 else ">80%池"
                    face[(who, "尺度 " + z)][a["kind"]] += 1
    print(" 无人下注时的下注率")
    for k in sorted(bet):
        t = bet[k]
        print(f"   {k[0]:8s} {k[1]:5s} {fr(t['bet'], t['bet'] + t['check'])}")
    for mode, t in size.items():
        n = sum(t.values())
        print(f"   下注尺度（{mode}）: " + "  ".join(f"{s} {100 * t[s] / n:.0f}%" for s in ("33%", "50%", "67%", "100%", "other")))
    print(" 面对下注 / 加注")
    for k in sorted(face):
        t = face[k]
        n = sum(t.values())
        print(f"   {k[0]:8s} {k[1]:10s} 弃 {fr(t['fold'], n):26s} 跟 {100 * t['call'] / n:3.0f}%  加 {100 * t['raise'] / n:3.0f}%")


def own_cards(hands):
    print("\n== 4 机器人自己的牌有多大作用（摊牌亮出的底牌）==")
    cache = {}

    def d(a):
        key = (tuple(a["cards"]), tuple(a["board"]))
        if key not in cache:
            cache[key] = describe(a["cards"], a["board"])
        return cache[key]

    rob = [a for h in hands for a in h["acts"] if a["st"] > 1 and not a["hero"] and a["cards"]]
    print(f" 可见底牌的翻后决策 {len(rob)} 次")
    print(" 无人下注时的下注率 × 自己的成牌")
    tab = defaultdict(Counter)
    for a in rob:
        if a["to_call"] == 0:
            tab[coarse(d(a)["cls"])]["bet" if a["kind"] == "bet" else "check"] += 1
    for c in ("无对", "弱对", "顶对/超对", "两对+"):
        t = tab[c]
        print(f"   {c:8s} {fr(t['bet'], t['bet'] + t['check'])}")
    print(" 下注尺度 × 下注时的牌力百分位（对随机牌）")
    by = defaultdict(list)
    for a in rob:
        if a["kind"] == "bet":
            by[size_tier(a["frac"])].append(d(a)["hs"])
    for s in ("33%", "50%", "67%", "100%"):
        v = sorted(by[s])
        print(f"   {s:5s} n={len(v):3d} 中位 {v[len(v) // 2]:.2f} 均值 {sum(v) / len(v):.2f}")
    print(" 河牌跟注 / 加注的人拿着什么（河牌跟注必摊牌，样本无偏）")
    tab = defaultdict(Counter)
    for a in rob:
        if a["street"] == "river" and a["to_call"] > 0 and a["kind"] != "fold":
            tab[("对 hero" if a["facing_hero"] else "对机器人", a["kind"])][coarse(d(a)["cls"])] += 1
    for k in sorted(tab):
        t = tab[k]
        n = sum(t.values())
        print(f"   {k[0]:5s} {k[1]:5s} n={n:3d}  " + "  ".join(f"{c} {100 * t[c] / n:.0f}%" for c in ("无对", "弱对", "顶对/超对", "两对+")))
    P = hand_percentile()
    print(" 翻前动作 × 自己底牌的强度百分位（0 最强，随机发牌的中位数是 50）")
    by = defaultdict(list)
    for h in hands:
        n_raise = 0
        for a in h["acts"]:
            if a["st"] != 1:
                break
            if not a["hero"] and a["cards"] and a["kind"] in ("call", "raise", "check"):
                key = ("无人加注时" if n_raise == 0 else "面对加注时") + {"call": "跟/平跟", "raise": "加注", "check": "过牌"}[a["kind"]]
                by[key].append(P(a["cards"]))
            if a["kind"] == "raise":
                n_raise += 1
    for k in sorted(by):
        v = sorted(by[k])
        print(f"   {k:14s} n={len(v):3d} 中位 {100 * v[len(v) // 2]:.0f}  最弱的 10% 在 {100 * v[int(.9 * len(v))]:.0f} 之后")


def hidden_cards(hands):
    print("\n== 5 机器人的行动是否随 hero 的暗牌变化（只取 hero 本手尚未行动时）==")
    P = hand_percentile()

    def first_before_hero(h, pos, group):
        if h["group"] != group or not h["regular"]:
            return None
        for a in h["acts"]:
            if a["st"] != 1 or a["hero"]:
                return None
            if a["pos"] == pos:
                return a if a["first_in"] else None
            if a["kind"] != "fold":
                return None
        return None

    def control(h):
        if h["group"] != "3way" or not h["regular"]:
            return None
        pre = [a for a in h["acts"] if a["st"] == 1]
        if len(pre) < 2 or not pre[0]["hero"] or pre[0]["kind"] != "fold":
            return None
        return pre[1] if pre[1]["pos"] == "SB" else None

    zs = []
    for name, sel, is_test in (
            ("单挑：机器人 SB 先行动，hero 在 BB", lambda h: first_before_hero(h, "SB", "HU"), True),
            ("三人：机器人 BTN 先行动，hero 在盲注", lambda h: first_before_hero(h, "BTN", "3way"), True),
            ("三人：BTN 机器人弃牌后 SB 机器人行动，hero 在 BB", lambda h: first_before_hero(h, "SB", "3way"), True),
            ("对照：hero 在 BTN 已弃牌，SB 机器人行动", control, False)):
        tab, xs, ys = defaultdict(Counter), [], []
        for h in hands:
            a = sel(h)
            if a is None:
                continue
            p = P(h["hole"])
            tab[tier(p)][a["kind"]] += 1
            xs.append(p)
            ys.append(a["kind"] == "fold")
        print(f" {name}  n={len(xs)}")
        for k in sorted(tab):
            t = tab[k]
            n = sum(t.values())
            print(f"    hero 底牌 {k:8s} 弃 {fr(t['fold'], n):24s} 平跟 {100 * t['call'] / n:3.0f}%  加注 {100 * t['raise'] / n:3.0f}%")
        b, se = logit_slope(xs, ys)
        print(f"    弃牌率对 hero 牌力的斜率 z = {b / se:+.1f}")
        if is_test:
            zs.append(b / se)
    print(f" 三个独立位置合并 z = {sum(zs) / len(zs) ** .5:+.1f}（公平游戏应为 0 附近）")
    print(" 翻后：机器人面对 hero 下注的弃牌率 × hero 当时的真实牌力")
    tab = defaultdict(Counter)
    for h in hands:
        for a in h["acts"]:
            if a["st"] > 1 and not a["hero"] and a["to_call"] > 0 and a["facing_hero"]:
                hs = describe(h["hole"], a["board"])["hs"]
                tab["hero 强（胜过 ≥75% 随机牌）" if hs >= .75 else "hero 中弱"][a["kind"]] += 1
    for k in sorted(tab):
        t = tab[k]
        n = sum(t.values())
        print(f"    {k:22s} 弃 {fr(t['fold'], n)}  跟 {100 * t['call'] / n:.0f}%  加 {100 * t['raise'] / n:.0f}%")
    print(" 翻后：机器人先行动、hero 在后位时的下注率 × hero 牌力")
    tab = defaultdict(Counter)
    for h in hands:
        for a in h["acts"]:
            if a["st"] > 1 and not a["hero"] and a["to_call"] == 0 and hero_live(h, a) \
                    and not any(b["hero"] and b["st"] == a["st"] and b["i"] < a["i"] for b in h["acts"]):
                hs = describe(h["hole"], a["board"])["hs"]
                tab["hero 强（胜过 ≥75% 随机牌）" if hs >= .75 else "hero 中弱"]["bet" if a["kind"] == "bet" else "check"] += 1
    for k in sorted(tab):
        t = tab[k]
        print(f"    {k:22s} 下注 {fr(t['bet'], t['bet'] + t['check'])}")


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    hands = load(argv[0] if argv else DEFAULT_PATH)
    sample(hands)
    preflop(hands)
    postflop(hands)
    own_cards(hands)
    hidden_cards(hands)


if __name__ == "__main__":
    main()
