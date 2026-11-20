from pf_notify.templates import format_bark_message, format_bark_options


def test_gamedata_messages_separate_auth_failure_from_empty_history():
    title, body, _ = format_bark_message("gamedata_auth_failed", {})
    assert "登录态失效" in title and "code=-2" in body
    title, body, _ = format_bark_message("gamedata_no_history", {"name": "Villain"})
    assert title == "玩家 · 暂无历史统计"
    assert "查询成功" in body and "Villain" in body
    assert "code=-2" not in body and "小号" not in body and "激进" not in body


def test_table_leave_names_the_cause_and_carries_only_the_running_result() -> None:
    title, body, icon = format_bark_message("table_leave", {"reason": "no_humans", "session_delta_chips": -235_066})
    assert title == "选桌离桌 · 桌上没有真人了"
    assert body == "本次启动盈亏: -235.07k（筹码）"
    assert icon and icon.endswith("robot_3d.png")
    assert format_bark_message("table_leave", {"reason": "outnumbered", "session_delta_chips": 164_376}) == (
        "选桌离桌 · 真人少于人机", "本次启动盈亏: +164.38k（筹码）", icon)
    assert format_bark_message("table_leave", {"reason": "retry"})[0] == "选桌离桌"
    assert format_bark_options("table_leave", {}) == {}


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


def test_bust_rebuy_and_loss_stop_name_the_net_loss_cap() -> None:
    title, body, _ = format_bark_message("auto_rebuy", {
        "nth": 2, "rebuy_chips": 2_000_000, "rebuy_window_sec": 60, "session_delta_chips": -2_536_220,
        "loss_cap_chips": 6_000_000})
    assert title == "筹码清零 · 自动买入"
    assert body == ("第 2 次自动续入\n续入筹码: 2000000\nrebuy 窗口: 60 秒\n"
                    "本次启动盈亏: -2.54m（筹码）\n净亏损上限: -6.00m")
    title, body, icon = format_bark_message("loss_stop", {
        "what": "破产买入", "session_delta_chips": -6_000_000, "loss_cap_chips": 6_000_000, "buyins": 3})
    assert title == "净亏损到上限 · 已停止"
    assert body == ("本次启动盈亏: -6.00m（筹码）\n净亏损上限: -6.00m（3 个 100BB 买入）\n"
                    "放不下破产买入，已停在大厅，不再买入。重启后恢复。")
    assert icon and format_bark_options("loss_stop", {}) == {}


def test_top_up_says_what_was_added_what_is_on_the_table_and_the_running_result() -> None:
    title, body, icon = format_bark_message("topup", {
        "added_chips": 300_000, "stack_chips": 953_000, "big_blind": 10_000, "nth": 2, "session_delta_chips": -47_000})
    assert title == "桌上补码"
    assert body == "补充筹码: 300000（30BB），本次启动第 2 次\n桌上筹码: 953000（95BB）\n本次启动盈亏: -47.00k（筹码）"
    assert icon and icon.endswith("coin_3d.png")
    assert format_bark_options("topup", {}) == {}
