from pf_notify.templates import format_bark_message, format_bark_options


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


def test_hand_swing_body_includes_hand_number() -> None:
    title, body, _ = format_bark_message(
        "hand_swing",
        {
            "profit_delta": 2_000,
            "start_chips": 1_000,
            "big_blind": 50,
            "hand_no": 12,
        },
    )

    assert title == "单手波动 · +40.0 BB"
    assert body.startswith("第几手: 第12手\n")


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


def test_bark_options_do_not_group_regular_events() -> None:
    assert format_bark_options("hand_swing", {}) == {}
    assert format_bark_options("profit_lock_trigger", {}) == {}
    assert format_bark_options("auto_rebuy", {}) == {}
    assert format_bark_options("room_escape", {}) == {}


def test_room_escape_message_describes_quickstart_reentry() -> None:
    title, body, _ = format_bark_message(
        "room_escape",
        {
            "bust_count": 2,
            "bust_need": 2,
            "byin_chips": 1_000_000,
            "room_id": 20399138,
            "big_blind": 10_000,
            "rebuy_window_sec": 60,
        },
    )

    assert title == "筹码清零 · 换桌"
    assert "连续破产: 2/2 次" in body
    assert "离桌后 QuickStart 换桌" in body
    assert "预计买入: 1000000（100BB）" in body


def test_bark_options_wss_uses_single_updatable_notice() -> None:
    assert format_bark_options("wss_disconnected", {}) == {
        "id": "pokerfate-wss-disconnected",
    }
    assert format_bark_options("wss_reconnected", {}) == {
        "id": "pokerfate-wss-disconnected",
        "delete": 1,
    }
