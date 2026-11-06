from pf_entertainment.hand_preview import hand_list_payload, read_hands


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
