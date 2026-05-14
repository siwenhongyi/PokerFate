from pf_notify.templates import format_bark_message


def test_hand_swing_includes_start_chips_bb_note() -> None:
    title, body, _ = format_bark_message(
        "hand_swing",
        {
            "profit_delta": 2_000,
            "start_chips": 1_000,
            "big_blind": 50,
        },
    )

    assert title == "单手波动 · +40.0 BB"
    assert "本手盈亏: +2000（+40.0 BB）" in body
    assert "开局筹码: 1000（20.0 BB，占比 +200.0%）" in body
    assert "BB = 50" in body


def test_hand_swing_appends_hand_detail() -> None:
    _, body, _ = format_bark_message(
        "hand_swing",
        {
            "profit_delta": -1_000,
            "start_chips": 5_000,
            "big_blind": 50,
            "hand_detail": "手牌: A♠ K♠\n行动:\n翻前: 我加3bb; BB跟",
        },
    )

    assert "手牌: A♠ K♠" in body
    assert "翻前: 我加3bb; BB跟" in body


def test_hand_swing_detail_body_is_capped_for_push_payload() -> None:
    _, body, _ = format_bark_message(
        "hand_swing",
        {
            "profit_delta": 1_000,
            "start_chips": 5_000,
            "big_blind": 50,
            "hand_detail": "行动:" + ("玩家加注跟注亮牌" * 500),
        },
    )

    assert len(body.encode("utf-8")) <= 3000
    assert body.endswith("...")
