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
