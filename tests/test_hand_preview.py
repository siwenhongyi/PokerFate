from pf_entertainment.hand_preview import _snap_stake, hand_detail_payload, hand_list_payload, read_hands


def test_hand_preview_recognizes_multi_word_hero_vpip(tmp_path):
    log_path = tmp_path / "pokerfate_console.log"
    log_path.write_text(
        "\n".join(
            [
                "[00:00:01]   第 1 手   睡衣 100bb []   Villain 100bb []",
                "[00:00:02]   底牌  A♠  K♦",
                "[00:00:03]   ► 睡衣  弃牌              胜率 40%  SPR≈10.0  [preflop_mc]   底池 30000  10ms",
                "[00:00:04]   第 2 手   Villain 100bb []   Royal Police 75bb []",
                "[00:00:05]   底牌  A♥  T♣",
                "[00:00:06]   ► Royal Police  加注  150000      胜率 28%  SPR≈47.1  [preflop_mc]   底池 75000  16ms",
            ]
        ),
        encoding="utf-8",
    )

    hands = read_hands(log_path)

    assert hands[0].hero == "睡衣"
    assert hands[0].vpip is False
    assert hands[1].hero == "Royal Police"
    assert hands[1].hero_stack_bb == 75
    assert hands[1].vpip is True
    assert hands[1].hero_actions[0]["action"] == "raise"


def test_hand_list_vpip_filter_uses_per_hand_hero(tmp_path):
    log_path = tmp_path / "pokerfate_console.log"
    log_path.write_text(
        "\n".join(
            [
                "[00:00:01]   第 1 手   睡衣 100bb []   Villain 100bb []",
                "[00:00:02]   底牌  7♠  2♦",
                "[00:00:03]   ► 睡衣  弃牌              胜率 10%  SPR≈10.0  [preflop_mc]   底池 30000  10ms",
                "[00:00:04]   第 2 手   Villain 100bb []   Royal Police 75bb []",
                "[00:00:05]   底牌  A♥  T♣",
                "[00:00:06]   ► Royal Police  加注  150000      胜率 28%  SPR≈47.1  [preflop_mc]   底池 75000  16ms",
            ]
        ),
        encoding="utf-8",
    )

    assert hand_list_payload(vpip="yes", log_path=log_path)["count"] == 1
    assert hand_list_payload(vpip="no", log_path=log_path)["count"] == 1


def test_hand_preview_vpip_means_hero_voluntarily_puts_chips_in(tmp_path):
    log_path = tmp_path / "pokerfate_console.log"
    log_path.write_text(
        "\n".join(
            [
                "[00:00:01]   第 1 手   Villain 100bb [小盲]   Royal Police 100bb [大盲]",
                "[00:00:02]   底牌  7♠  2♦",
                "[00:00:03]   ► Royal Police  过牌              胜率 30%  SPR≈10.0  [preflop_mc]   底池 20000  10ms",
                "[00:00:04]   ── 翻牌  A♠  K♦  3♣  底池 20000 ────────────────────────────────",
                "[00:00:05]   ► Royal Police  弃牌              胜率 10%  SPR≈10.0  [range_v2]   底池 40000  10ms",
                "[00:00:06]   第 2 手   Villain 100bb [小盲]   Royal Police 100bb [大盲]",
                "[00:00:07]   底牌  A♥  T♣",
                "[00:00:08]   ► Royal Police  过牌              胜率 30%  SPR≈10.0  [preflop_mc]   底池 20000  10ms",
                "[00:00:09]   ── 翻牌  A♣  9♦  3♣  底池 20000 ────────────────────────────────",
                "[00:00:10]   ► Royal Police  加注  30000       胜率 70%  SPR≈10.0  [range_v2]   底池 20000  10ms",
                "[00:00:11]   第 3 手   Villain 100bb [庄]   Royal Police 100bb [大盲]",
                "[00:00:12]   底牌  K♥  Q♣",
                "[00:00:13]   ► Royal Police  跟注  20000       胜率 40%  SPR≈10.0  [preflop_mc]   底池 50000  10ms",
                "[00:00:14]   第 4 手   Villain 100bb [小盲]   Royal Police 100bb [大盲]",
                "[00:00:15]   底牌  9♥  8♣",
                "[00:00:16]   ► Royal Police  过牌              胜率 30%  SPR≈10.0  [preflop_mc]   底池 20000  10ms",
                "[00:00:17]   ── 翻牌  9♣  4♦  3♣  底池 20000 ────────────────────────────────",
                "[00:00:18]   ► Royal Police  跟注  30000       胜率 55%  SPR≈10.0  [range_v2]   底池 50000  10ms",
            ]
        ),
        encoding="utf-8",
    )

    hands = read_hands(log_path)

    assert hands[0].vpip is False
    assert hands[1].vpip is True
    assert hands[2].vpip is True
    assert hands[3].vpip is True


def test_hand_list_payload_paginates_filtered_hands(tmp_path):
    log_path = tmp_path / "pokerfate_console.log"
    lines = []
    for hand_no in range(1, 5):
        lines.extend(
            [
                f"[00:00:0{hand_no}]   第 {hand_no} 手   Hero 100bb []   Villain 100bb []",
                "[00:00:10]   底牌  A♠  K♦",
                "[00:00:11]   ► Hero  加注  30000      胜率 40%  SPR≈10.0  [preflop_mc]   底池 30000  10ms",
            ]
        )
    log_path.write_text("\n".join(lines), encoding="utf-8")

    page1 = hand_list_payload(vpip="yes", page=1, page_size=2, log_path=log_path)
    page2 = hand_list_payload(vpip="yes", page=2, page_size=2, log_path=log_path)

    assert page1["count"] == 4
    assert page1["page_count"] == 2
    assert page1["page_start"] == 1
    assert page1["page_end"] == 2
    assert page1["has_next"] is True
    assert [hand["hand_no"] for hand in page1["hands"]] == [4, 3]
    assert page2["has_prev"] is True
    assert [hand["hand_no"] for hand in page2["hands"]] == [2, 1]


def test_hand_list_payload_filters_exact_hand_no(tmp_path):
    log_path = tmp_path / "pokerfate_console.log"
    lines = []
    for hand_no in range(1, 5):
        lines.extend(
            [
                f"[00:00:0{hand_no}]   第 {hand_no} 手   Hero 100bb []   Villain 100bb []",
                "[00:00:10]   底牌  A♠  K♦",
                "[00:00:11]   ► Hero  加注  30000      胜率 40%  SPR≈10.0  [preflop_mc]   底池 30000  10ms",
            ]
        )
    log_path.write_text("\n".join(lines), encoding="utf-8")

    payload = hand_list_payload(hand_no="2", log_path=log_path)
    invalid = hand_list_payload(hand_no="not-a-number", log_path=log_path)

    assert payload["count"] == 1
    assert [hand["hand_no"] for hand in payload["hands"]] == [2]
    assert invalid["count"] == 0
    assert invalid["hands"] == []


def test_hand_list_board_prefix_search_uses_rank_prefix(tmp_path):
    log_path = tmp_path / "pokerfate_console.log"
    log_path.write_text(
        "\n".join(
            [
                "[12:00:00] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
                "[12:00:00]   第 1 手  Hero 100bb [BTN]   Villain 100bb [BB]",
                "[12:00:00] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
                "[12:00:01]   底牌  K♠  K♣",
                "[12:00:02] ── 翻牌 A♠  2♦  5♣ 底池 100 ─",
                "[12:00:03]   ► Hero          过牌            胜率 50%   底池 100  10ms",
                "[12:00:04] ✔ Hero 赢得 100 本手 +0",
                "[12:01:00] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
                "[12:01:00]   第 2 手  Hero 100bb [BTN]   Villain 100bb [BB]",
                "[12:01:00] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
                "[12:01:01]   底牌  Q♠  Q♣",
                "[12:01:02] ── 翻牌 A♥  2♣  5♦ 底池 100 ─",
                "[12:01:03] ── 转牌 7♠ 底池 100 ─",
                "[12:01:04] ── 河牌 9♣ 底池 100 ─",
                "[12:01:05]   ► Hero          过牌            胜率 50%   底池 100  10ms",
                "[12:01:06] ✔ Hero 赢得 100 本手 +0",
            ]
        ),
        encoding="utf-8",
    )

    three_card = hand_list_payload(board="a 2 5", vpip="all", log_path=log_path)
    assert three_card["count"] == 2

    suited_input = hand_list_payload(board="Ah 2d 5c", vpip="all", log_path=log_path)
    assert suited_input["count"] == 2

    middle_slice = hand_list_payload(board="2 5 7", vpip="all", log_path=log_path)
    assert middle_slice["count"] == 0

    four_card = hand_list_payload(board="A 2 5 7", vpip="all", log_path=log_path)
    assert four_card["count"] == 1
    assert four_card["hands"][0]["hand_no"] == 2


def test_hand_detail_reads_the_hand_street_by_street(tmp_path):
    log_path = tmp_path / "pokerfate_console.log"
    log_path.write_text("\n".join([
        "[05:03:00] ",
        "[05:03:00] ━━━━━━━━━━",
        "[05:03:00]   第 222 手   雷人 出世 105bb [庄]   Royal Police 86bb [大盲]",
        "[05:03:00]   底牌  A♦  Q♥",
        "[05:03:00]   ── 翻牌前 ─────────────",
        "[05:03:07]     雷人 出世          跟注  range 92%",
        "[05:03:07]   ⚑ 对手模型  雷人 出世: fold_to_cbet_low=50% → bluff_ag×0.14",
        "[05:03:20]   ► Royal Police  加注  180000      胜率 26%  SPR≈14.2  [preflop_mc]   底池 120000  20ms",
        "[05:03:20]       💭 【GTOv2·翻前】 AQo BB iso",
        "[05:03:20]       📊 [Greenline]  BB-ISO AQo → raise",
        "[05:03:38]   ── 河牌  T♥  T♠  9♦  底池 440000 ───────────────────────────────",
        "[05:04:08]   ► Royal Police  过牌              胜率 26%(vs随机48%)  SPR≈0.7  [range_v2]   底池 1537828  102ms",
        "[05:04:08]       💭 realtime_cfr decision | Check@100%",
        "[05:04:08]       ◇ 规则引擎旁路  过牌            【GTOv2·翻后】 控池",
        "        │  分支=pot_control  │  候选: pot_control[80%]",
        "[05:04:12]     雷人 出世          加注  69bb  (69bb 0.9x pot)  range 75% [坚果55%/强34%] [≥你89%/平0%/≤你10%]  需跟69bb 赔率32%",
        "[05:04:14]   ► Royal Police  弃牌              胜率 9%  SPR≈0.4  [range_v2]   底池 2909737  55ms",
        "[05:04:16]   ✔ 雷人 出世[一对] 赢得 1399424    本手 -728914  [我: 一对 T♥️ T♠️]  │  雷人 出世 2100000  Royal Police 1720000",
    ]), encoding="utf-8")

    payload = hand_detail_payload(1, log_path=log_path)
    assert payload["hand"]["bb_chips"] == 20000 and payload["log_text"].splitlines()[0].endswith("[大盲]")
    detail = payload["detail"]
    assert detail["players"] == [{"name": "雷人 出世", "stack_bb": 105, "pos": "庄", "hero": False},
                                 {"name": "Royal Police", "stack_bb": 86, "pos": "大盲", "hero": True}]
    preflop, river = detail["streets"]
    assert (preflop["key"], preflop["cards"], preflop["pot"]) == ("preflop", [], 0)
    assert (river["key"], river["name"], river["cards"], river["pot_bb"]) == ("river", "河牌", ["T♥", "T♠", "9♦"], 22.0)
    limp, note, open_raise = preflop["events"]
    assert (limp["kind"], limp["who"], limp["pos"], limp["action"], limp["range_pct"], limp["amount_bb"]) == (
        "action", "雷人 出世", "庄", "call", 92, None)
    assert note == {"kind": "note", "text": "对手模型  雷人 出世: fold_to_cbet_low=50% → bluff_ag×0.14"}
    assert {k: open_raise[k] for k in ("kind", "action", "amount", "amount_bb", "equity", "equity_random", "spr", "mode", "pot_bb", "ms")} == {
        "kind": "hero", "action": "raise", "amount": 180000, "amount_bb": 9.0, "equity": 26, "equity_random": None,
        "spr": 14.2, "mode": "preflop_mc", "pot_bb": 6.0, "ms": 20}
    assert open_raise["why"] == ["【GTOv2·翻前】 AQo BB iso"] and open_raise["refs"] == ["[Greenline]  BB-ISO AQo → raise"]
    check, bet, fold = river["events"]
    assert check["equity_random"] == 48 and check["why"] == ["realtime_cfr decision | Check@100%"]
    assert check["shadow"] == {"action_cn": "过牌", "text": ["【GTOv2·翻后】 控池", "│  分支=pot_control  │  候选: pot_control[80%]"]}
    assert {k: bet[k] for k in ("action", "amount_bb", "pot_ratio", "range_pct", "range_mix", "versus", "to_call_bb", "odds_pct")} == {
        "action": "raise", "amount_bb": 69, "pot_ratio": 0.9, "range_pct": 75, "range_mix": "坚果55%/强34%",
        "versus": [89, 0, 10], "to_call_bb": 69, "odds_pct": 32}
    assert (fold["kind"], fold["action"], fold["equity"], fold["shadow"]) == ("hero", "fold", 9, None)


def test_snap_stake_picks_the_blind_behind_a_rough_estimate():
    assert [_snap_stake(x) for x in (19500, 20400, 9800, 5100, 1042, 0)] == [20000, 20000, 10000, 5000, 1000, 0]
