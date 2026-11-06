"""Tests for the external API interface (PokerFateAPI)."""

import json
import os
import tempfile
import pytest
from pokerfate.api import PokerFateAPI, PlayerInfo, ActionEvent, BotDecision
from pokerfate.core.card import Card
from pokerfate.core.game_state import Action, ActionType, GameState, Player
from pokerfate.decision.g5_model import G5ActionModel


def make_api(verbose=False) -> PokerFateAPI:
    return PokerFateAPI(
        my_player_id=0,
        big_blind=2.0,
        small_blind=1.0,
        equity_iterations=300,
        verbose=verbose,
    )


def start_hand(api: PokerFateAPI):
    api.new_hand(
        players=[
            PlayerInfo(0, "PokerFate", 200.0, "BTN"),
            PlayerInfo(1, "Opponent",  200.0, "BB"),
        ],
        dealer_id=0,
    )


class TestAPILifecycle:
    def test_board_hand_type_for_bluff_stats_handles_partial_boards(self):
        def cards(*values):
            return [Card.from_str(v) for v in values]

        assert PokerFateAPI._board_hand_type_for_bluff_stats(cards("Ks", "Kh", "Ad")) == 2
        assert PokerFateAPI._board_hand_type_for_bluff_stats(cards("Ks", "Kh", "7d", "7c")) == 3
        assert PokerFateAPI._board_hand_type_for_bluff_stats(cards("Ks", "Kh", "Kd")) == 4
        assert PokerFateAPI._board_hand_type_for_bluff_stats(cards("2s", "3h", "4d", "5c", "6s")) == 5

    def test_new_hand_and_hole_cards(self):
        api = make_api()
        start_hand(api)
        api.deal_hole_cards(["Ac", "Ad"])
        assert len(api._hole_cards) == 2

    def test_new_hand_accepts_external_hand_number(self):
        api = make_api()
        api.new_hand(
            players=[
                PlayerInfo(0, "PokerFate", 200.0, "BTN"),
                PlayerInfo(1, "Opponent", 200.0, "BB"),
            ],
            dealer_id=0,
            hand_number=42,
        )
        assert api._hand_number == 42

        start_hand(api)
        assert api._hand_number == 43

    def test_hand_over_persists_g5_native_action_model(self, tmp_path):
        g5_path = tmp_path / "g5_stats.json"
        api = PokerFateAPI(
            my_player_id=0,
            big_blind=10,
            small_blind=5,
            equity_iterations=50,
            g5_model_path=str(g5_path),
        )
        api.new_hand(
            players=[
                PlayerInfo(0, "Hero", 1000, "BTN"),
                PlayerInfo(1, "Villain", 1000, "SB"),
                PlayerInfo(2, "Other", 1000, "BB"),
            ],
            dealer_id=0,
        )
        api.deal_hole_cards(["As", "Ah"])
        api.notify_action(ActionEvent(1, "call", 5, "preflop"))
        api.notify_action(ActionEvent(2, "check", 0, "preflop"))
        api.hand_over(
            winner_ids=[0],
            pot=30,
            final_stacks={0: 1020, 1: 990, 2: 990},
            my_profit_delta=20,
        )

        model = G5ActionModel.load(g5_path)
        villain = model.players["uid:1"]
        other = model.players["uid:2"]
        assert villain.vpip_positive == 1
        assert villain.vpip_total == 1
        assert other.vpip_positive == 0
        assert other.vpip_total == 1

    def test_hand_over_builds_push_detail(self):
        api = make_api()
        start_hand(api)
        api.deal_hole_cards(["As", "Ah"])
        api.deal_board(["Ks", "7d", "2c"], street="flop", pot=20)
        api.deal_board(["9h"], street="turn", pot=60)
        api.deal_board(["3c"], street="river", pot=120)
        api._action_history = [
            (1, Action(ActionType.RAISE, 6), "preflop"),
            (0, Action(ActionType.RAISE, 20), "preflop"),
            (1, Action(ActionType.CALL, 20), "preflop"),
            (1, Action(ActionType.CHECK), "flop"),
            (0, Action(ActionType.RAISE, 24), "flop"),
        ]

        api.hand_over(
            winner_ids=[0],
            pot=118,
            final_stacks={0: 240, 1: 160},
            showdown_hands={1: ["Kd", "Qd"]},
            my_profit_delta=40,
        )

        detail = api.last_hand_push_detail()
        assert "手牌: A♠️ A♥️" in detail
        assert "牌面: K♠️ 7♦️ 2♣️ | 9♥️ | 3♣️" in detail
        assert "翻前: Opponent加3bb; 我加10bb; Opponent跟10bb" in detail
        assert "亮牌: Opponent:K♦️ Q♦️" in detail
        assert "一对 K♦️ K♠️" in detail
        assert "结果: PokerFate 赢池 118，我 +40" in detail
        assert "我牌型: 一对 A♠️ A♥️" in detail

    def test_hand_over_push_detail_uses_server_winner_type_without_showdown(self):
        api = make_api()
        start_hand(api)
        api.deal_hole_cards(["As", "Qh"])
        api.deal_board(["Kd", "7d", "2d"], street="flop", pot=20)
        api.deal_board(["9d"], street="turn", pot=60)
        api.deal_board(["3c"], street="river", pot=120)

        api.hand_over(
            winner_ids=[1],
            pot=118,
            final_stacks={0: 160, 1: 240},
            winner_hand_types={1: 6},
            my_profit_delta=-40,
        )

        detail = api.last_hand_push_detail()
        assert "亮牌: 无" not in detail
        assert "赢家牌型: Opponent:同花" in detail
        assert "结果: Opponent 赢池 118，我 -40" in detail

    def test_weak_winner_before_river_does_not_count_as_bluff_win_without_showdown(self):
        api = make_api()
        start_hand(api)
        api.deal_hole_cards(["As", "Qh"])
        api.deal_board(["Kd", "7d", "2c"], street="flop", pot=20)
        api.deal_board(["9h"], street="turn", pot=60)
        api.notify_action(ActionEvent(1, "raise", 30.0, "turn"))

        api.hand_over(
            winner_ids=[1],
            pot=90,
            final_stacks={0: 170, 1: 230},
            winner_hand_types={1: 1},
            my_profit_delta=-30,
        )

        stats = api._bot.opponent_model.get(1)
        assert stats.bet_win_count == 0
        assert stats.bluff_win_count == 0

    def test_weak_winner_before_river_does_not_count_as_bluff_win_with_showdown(self):
        api = make_api()
        start_hand(api)
        api.deal_hole_cards(["As", "Qh"])
        api.deal_board(["Kd", "7d", "2c"], street="flop", pot=20)
        api.deal_board(["9h"], street="turn", pot=60)
        api.notify_action(ActionEvent(1, "raise", 30.0, "turn"))

        api.hand_over(
            winner_ids=[1],
            pot=90,
            final_stacks={0: 170, 1: 230},
            showdown_hands={1: ["Jh", "Th"]},
            winner_hand_types={1: 1},
            my_profit_delta=-30,
        )

        stats = api._bot.opponent_model.get(1)
        assert stats.showdown_count == 1
        assert stats.showdown_win_count == 1
        assert stats.bet_win_count == 0
        assert stats.bluff_win_count == 0

    def test_non_showdown_weak_winner_on_river_counts_as_bluff_win(self):
        api = make_api()
        start_hand(api)
        api.deal_hole_cards(["As", "Qh"])
        api.deal_board(["Kd", "7d", "2c"], street="flop", pot=20)
        api.deal_board(["9h"], street="turn", pot=60)
        api.deal_board(["3s"], street="river", pot=90)
        api.notify_action(ActionEvent(1, "raise", 30.0, "river"))

        api.hand_over(
            winner_ids=[1],
            pot=120,
            final_stacks={0: 170, 1: 230},
            winner_hand_types={1: 1},
            my_profit_delta=-30,
        )

        stats = api._bot.opponent_model.get(1)
        assert stats.bet_win_count == 1
        assert stats.bluff_win_count == 1

    def test_auto_collect_reasons_ignore_profit_only_hands(self):
        api = make_api()
        start_hand(api)
        api.deal_hole_cards(["As", "Ah"])
        api.deal_board(["Ks", "7d", "2c"], street="flop", pot=20)
        api.deal_board(["9h"], street="turn", pot=60)
        api.deal_board(["3c"], street="river", pot=120)

        api.hand_over(
            winner_ids=[0],
            pot=400,
            final_stacks={0: 500, 1: 0},
            my_profit_delta=300,
        )

        assert api.last_auto_collect_reasons() == []

    def test_auto_collect_reasons_skip_full_house(self):
        api = make_api()
        start_hand(api)
        api.deal_hole_cards(["Ac", "Ks"])
        api.deal_board(["Ah", "Ad", "7s"], street="flop", pot=20)
        api.deal_board(["7c"], street="turn", pot=60)
        api.deal_board(["2d"], street="river", pot=120)

        api.hand_over(
            winner_ids=[0],
            pot=120,
            final_stacks={0: 260, 1: 140},
            my_profit_delta=60,
        )

        assert api.last_auto_collect_reasons() == []

    def test_auto_collect_reasons_skip_board_trips_full_house(self):
        api = make_api()
        start_hand(api)
        api.deal_hole_cards(["Kd", "Qs"])
        api.deal_board(["Ah", "Ad", "As"], street="flop", pot=20)
        api.deal_board(["Kc"], street="turn", pot=60)
        api.deal_board(["2d"], street="river", pot=120)

        api.hand_over(
            winner_ids=[0],
            pot=120,
            final_stacks={0: 260, 1: 140},
            my_profit_delta=60,
        )

        assert api.last_auto_collect_reasons() == []

    def test_hand_over_partial_board_does_not_print_best_five_traceback(self, capsys):
        api = make_api()
        start_hand(api)
        api.deal_hole_cards(["Jd", "7s"])
        api.deal_board(["Js"], street="flop", pot=20)

        api.hand_over(
            winner_ids=[1],
            pot=20,
            final_stacks={0: 190, 1: 210},
            showdown_hands={1: ["Qd", "3s"]},
            my_profit_delta=-10,
        )

        captured = capsys.readouterr()
        assert "best_five ERROR" not in captured.out
        assert "hand_combos ERROR" not in captured.out
        assert "Traceback" not in captured.out

    def test_range_calibration_extractor_skips_partial_board_replays(self):
        from scripts.extract_range_calibration_rows_parallel import _malformed_board_reason

        assert _malformed_board_reason({
            "events": [{"type": "board", "street": "flop", "cards": ["Js"]}],
        }) == "flop_cards=1"
        assert _malformed_board_reason({
            "events": [{"type": "board", "street": "river", "cards": ["Qs", "5h"]}],
        }) == "river_cards=2"
        assert _malformed_board_reason({
            "events": [
                {"type": "board", "street": "turn", "cards": ["Qs"]},
                {"type": "board", "street": "river", "cards": ["5h"]},
            ],
        }) == "partial_board=2"

    def test_request_action_returns_decision(self):
        api = make_api()
        start_hand(api)
        api.deal_hole_cards(["Ac", "Ad"])
        decision = api.request_action(
            street="preflop",
            pot=3.0,
            current_bet=2.0,
            to_call=2.0,
            my_stack=200.0,
        )
        assert isinstance(decision, BotDecision)
        assert decision.action in ("fold", "check", "call", "raise")

    def test_aa_preflop_raises(self):
        api = make_api()
        start_hand(api)
        api.deal_hole_cards(["Ac", "Ad"])
        decision = api.request_action(
            street="preflop",
            pot=3.0,
            current_bet=2.0,
            to_call=2.0,
            my_stack=200.0,
        )
        assert decision.action == "raise"
        assert decision.amount > 2.0

    def test_free_check_signal_does_not_override_open_outside_bb(self):
        api = make_api()
        start_hand(api)  # Hero is BTN, not BB
        api.deal_hole_cards(["Ac", "Ad"])

        decision = api.request_action(
            street="preflop",
            pot=3.0,
            current_bet=0.0,
            to_call=0.0,
            my_stack=200.0,
            is_bb_option=True,
        )

        assert decision.action == "raise"

    def test_notify_action_updates_state(self):
        api = make_api()
        start_hand(api)
        api.deal_hole_cards(["Ac", "Kd"])
        api.notify_action(ActionEvent(
            player_id=1, action="raise", amount=6.0, street="preflop"
        ))
        assert len(api._action_history) == 1
        opp = api._get_player(1)
        assert opp.current_bet == pytest.approx(6.0)
        assert opp.stack == pytest.approx(194.0)

    def test_deal_board_resets_current_bet_but_keeps_pot_base(self):
        api = make_api()
        start_hand(api)
        api.deal_hole_cards(["Ac", "Kd"])
        api.notify_action(ActionEvent(
            player_id=1, action="raise", amount=6.0, street="preflop"
        ))
        assert api._last_known_pot == pytest.approx(9.0)

        api.deal_board(["As", "7d", "2c"], street="flop")

        assert api._get_player(1).current_bet == pytest.approx(0.0)
        assert api._street_base_pot == pytest.approx(9.0)
        assert api._street_contribs == {}

    def test_call_zero_amount_infers_call_from_current_bet(self):
        api = make_api()
        start_hand(api)
        api.deal_hole_cards(["Ac", "Kd"])
        hero = api._get_my_player()
        hero.current_bet = 6.0
        api.notify_action(ActionEvent(
            player_id=1, action="call", amount=0.0, street="preflop"
        ))
        opp = api._get_player(1)
        assert opp.current_bet == pytest.approx(6.0)
        assert opp.stack == pytest.approx(194.0)

    def test_call_added_chips_closes_to_current_bet_when_blind_untracked(self):
        api = make_api()
        start_hand(api)
        api.deal_hole_cards(["Ac", "Kd"])
        hero = api._get_my_player()
        hero.current_bet = 5.0
        api.notify_action(ActionEvent(
            player_id=1, action="call", amount=3.0, street="preflop"
        ))
        opp = api._get_player(1)
        assert opp.current_bet == pytest.approx(5.0)
        assert opp.stack == pytest.approx(197.0)

    def test_deal_board_flop(self):
        api = make_api()
        start_hand(api)
        api.deal_hole_cards(["Ac", "Kd"])
        api.deal_board(["As", "7d", "2c"], street="flop")
        assert len(api._board) == 3

    def test_deal_board_incremental(self):
        api = make_api()
        start_hand(api)
        api.deal_hole_cards(["Ac", "Kd"])
        api.deal_board(["As", "7d", "2c"], street="flop")
        api.deal_board(["Th"], street="turn")
        api.deal_board(["4s"], street="river")
        assert len(api._board) == 5

    def test_postflop_action(self):
        api = make_api()
        start_hand(api)
        api.deal_hole_cards(["Ac", "Kd"])
        api.deal_board(["As", "7d", "2c"], street="flop")
        decision = api.request_action(
            street="flop",
            pot=10.0,
            current_bet=0.0,
            to_call=0.0,
            my_stack=196.0,
        )
        assert isinstance(decision, BotDecision)
        assert decision.action in ("check", "raise")

    def test_full_hand_workflow(self):
        api = make_api()

        # Preflop
        api.new_hand(
            players=[
                PlayerInfo(0, "PokerFate", 200.0, "BTN"),
                PlayerInfo(1, "GPT-Bot",   200.0, "BB"),
            ],
            dealer_id=0,
        )
        api.deal_hole_cards(["Qh", "Qs"])
        api.notify_action(ActionEvent(1, "raise", 2.0, "preflop"))
        d1 = api.request_action("preflop", pot=3.0, current_bet=2.0, to_call=2.0, my_stack=200.0)
        assert d1.action in ("fold", "call", "raise")

        # Flop
        api.deal_board(["Qd", "7h", "2c"], street="flop")
        api.notify_action(ActionEvent(1, "check", 0.0, "flop"))
        d2 = api.request_action("flop", pot=7.0, current_bet=0.0, to_call=0.0, my_stack=197.0)
        assert d2.action in ("check", "raise")

        # Turn
        api.deal_board(["Ac"], street="turn")
        d3 = api.request_action("turn", pot=7.0, current_bet=0.0, to_call=0.0, my_stack=197.0)
        assert d3.action in ("check", "raise")

        # River
        api.deal_board(["5s"], street="river")
        d4 = api.request_action("river", pot=7.0, current_bet=0.0, to_call=0.0, my_stack=197.0)
        assert d4.action in ("check", "raise")

        # End hand
        api.hand_over(winner_ids=[0], pot=7.0)

    def test_fold_opponent_removes_from_active(self):
        api = make_api()
        start_hand(api)
        api.deal_hole_cards(["7c", "2d"])
        api.notify_action(ActionEvent(1, "fold", 0.0, "preflop"))
        folded = api._get_player(1)
        assert folded.is_folded

    def test_decision_repr(self):
        d_raise = BotDecision("raise", 10.0)
        assert "raise" in repr(d_raise)
        assert "10" in repr(d_raise)
        d_fold = BotDecision("fold")
        assert "fold" in repr(d_fold)

    def test_verbose_mode(self, capsys):
        api = make_api(verbose=True)
        start_hand(api)
        api.deal_hole_cards(["Ac", "Ad"])
        api.request_action("preflop", pot=3.0, current_bet=2.0, to_call=2.0, my_stack=200.0)
        captured = capsys.readouterr()
        assert "PokerFate" in captured.out

    def test_parse_cards_utility(self):
        cards = PokerFateAPI.parse_cards(["Ac", "Kd", "Qh"])
        assert len(cards) == 3

    def test_multiple_hands(self):
        api = make_api()
        for _ in range(10):
            start_hand(api)
            api.deal_hole_cards(["Ac", "Kd"])
            d = api.request_action("preflop", pot=3.0, current_bet=2.0, to_call=2.0, my_stack=200.0)
            assert isinstance(d, BotDecision)


class TestAutosave:
    def test_autosave_after_hand_over(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name
        os.unlink(path)  # ensure it doesn't exist yet
        try:
            api = PokerFateAPI(my_player_id=0, big_blind=2.0, autosave_path=path)
            api.new_hand(
                players=[PlayerInfo(0, "Bot", 200.0), PlayerInfo(1, "Opp", 200.0)],
                dealer_id=0,
            )
            api.deal_hole_cards(["Ac", "Ad"])
            api.notify_action(ActionEvent(1, "raise", 6.0, "preflop"))
            api.hand_over(winner_ids=[0], pot=9.0, final_stacks={0: 207.0, 1: 193.0})

            # File must exist immediately after hand_over
            assert os.path.exists(path)
            with open(path) as f:
                data = json.load(f)
            # Opponent uid=1 should be in the saved file
            assert "1" in data["players"]
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_autoload_on_startup(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name
        try:
            # First session: accumulate data
            api1 = PokerFateAPI(my_player_id=0, big_blind=2.0, autosave_path=path)
            api1.new_hand(
                players=[PlayerInfo(0, "Bot", 200.0), PlayerInfo(1, "Opp", 200.0)],
                dealer_id=0,
            )
            api1.deal_hole_cards(["Ac", "Kd"])
            for _ in range(8):
                api1.notify_action(ActionEvent(1, "fold", 0.0, "preflop"))
            api1.hand_over(winner_ids=[0], pot=3.0)

            saved_folds = api1._bot.opponent_model.get(1).fold_count

            # Second session: data automatically reloaded
            api2 = PokerFateAPI(my_player_id=0, big_blind=2.0, autosave_path=path)
            loaded_folds = api2._bot.opponent_model.get(1).fold_count
            assert loaded_folds == saved_folds
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_no_autosave_when_path_is_none(self):
        api = PokerFateAPI(my_player_id=0, big_blind=2.0, autosave_path=None)
        api.new_hand(
            players=[PlayerInfo(0, "Bot", 200.0), PlayerInfo(1, "Opp", 200.0)],
            dealer_id=0,
        )
        api.deal_hole_cards(["Ac", "Ad"])
        # Should not raise and should not create any file
        api.hand_over(winner_ids=[0], pot=3.0)


class TestStackTracking:
    """Tests for dynamic stack and opponent replacement handling."""

    def test_hand_over_updates_session_stacks(self):
        api = make_api()
        api.new_hand(
            players=[PlayerInfo(0, "Bot", 200.0), PlayerInfo(1, "Opp", 200.0)],
            dealer_id=0,
        )
        # Bot wins 10 chips
        api.hand_over(winner_ids=[0], pot=10.0, final_stacks={0: 210.0, 1: 190.0})
        assert api._session_stacks[0] == 210.0
        assert api._session_stacks[1] == 190.0

    def test_next_hand_uses_updated_stacks(self):
        api = make_api()
        api.new_hand(
            players=[PlayerInfo(0, "Bot", 200.0), PlayerInfo(1, "Opp", 200.0)],
            dealer_id=0,
        )
        api.hand_over(winner_ids=[0], pot=10.0, final_stacks={0: 210.0, 1: 190.0})

        # Next hand: pass stack=None → should use session registry
        api.new_hand(
            players=[PlayerInfo(0, "Bot", None), PlayerInfo(1, "Opp", None)],
            dealer_id=1,
        )
        my_player = api._get_my_player()
        opp_player = api._get_player(1)
        assert my_player.stack == 210.0
        assert opp_player.stack == 190.0

    def test_unknown_stack_defaults_to_100bb(self):
        api = make_api()
        # New player never seen before, stack=None
        api.new_hand(
            players=[PlayerInfo(0, "Bot", 200.0), PlayerInfo(99, "NewGuy", None)],
            dealer_id=0,
        )
        new_guy = api._get_player(99)
        assert new_guy.stack == 100.0 * api.big_blind  # 100 BB default

    def test_opponent_replacement_fresh_model(self):
        api = make_api()
        # Play hand vs opponent id=1
        api.new_hand(
            players=[PlayerInfo(0, "Bot", 200.0), PlayerInfo(1, "Opp1", 200.0)],
            dealer_id=0,
        )
        api.deal_hole_cards(["Ac", "Ad"])
        api.notify_action(ActionEvent(1, "raise", 6.0, "preflop"))
        api.notify_action(ActionEvent(1, "raise", 6.0, "preflop"))  # simulate more actions
        api.hand_over(winner_ids=[0], pot=10.0, final_stacks={0: 210.0, 1: 190.0})

        # Opp1 is replaced by Opp2 (id=2) — new player with unknown stack
        api.notify_player_joined(player_id=2, name="Opp2", stack=300.0)
        assert api._session_stacks[2] == 300.0

        # New hand with replacement
        api.new_hand(
            players=[PlayerInfo(0, "Bot", None), PlayerInfo(2, "Opp2", None)],
            dealer_id=0,
        )
        opp2 = api._get_player(2)
        assert opp2.stack == 300.0
        # Opponent model for id=2 should be fresh (no hands seen)
        stats = api._bot.opponent_model.get(2)
        assert stats.hands_seen <= 1  # at most this hand was just started

    def test_opponent_replacement_unknown_stack(self):
        api = make_api()
        api.new_hand(
            players=[PlayerInfo(0, "Bot", 200.0), PlayerInfo(1, "Opp", 200.0)],
            dealer_id=0,
        )
        api.hand_over(winner_ids=[1], pot=10.0, final_stacks={0: 190.0, 1: 210.0})

        # New opponent arrives with no stack info
        api.notify_player_joined(player_id=5, name="Mystery")
        assert api._session_stacks[5] == 100.0 * api.big_blind

        api.new_hand(
            players=[PlayerInfo(0, "Bot", None), PlayerInfo(5, "Mystery", None)],
            dealer_id=0,
        )
        mystery = api._get_player(5)
        assert mystery.stack == 100.0 * api.big_blind

    def test_stack_update_mid_hand(self):
        api = make_api()
        api.new_hand(
            players=[PlayerInfo(0, "Bot", 200.0), PlayerInfo(1, "Opp", 200.0)],
            dealer_id=0,
        )
        api.notify_stack_update(player_id=1, new_stack=150.0)
        # Should update both in-hand state and session registry
        player = api._get_player(1)
        assert player.stack == 150.0
        assert api._session_stacks[1] == 150.0

    def test_same_name_different_uid_does_not_migrate_model(self):
        """Display name is not identity; only uid/player_id preserves stats."""
        api = make_api()
        api.new_hand(
            players=[PlayerInfo(0, "Bot", 200.0), PlayerInfo(1, "GPT", 200.0)],
            dealer_id=0,
        )
        api.deal_hole_cards(["Ac", "Kd"])
        for _ in range(5):
            api.notify_action(ActionEvent(1, "fold", 0.0, "preflop"))
        old_stats = api._bot.opponent_model.get(1)
        assert old_stats.fold_count > 0

        api.notify_player_joined(player_id=7, name="GPT", stack=200.0)
        stats_new_id = api._bot.opponent_model.get(7)
        assert stats_new_id.fold_count == 0

    def test_session_survives_multiple_hand_cycles(self):
        api = make_api()
        my_stack = 200.0
        opp_stack = 200.0
        for i in range(5):
            api.new_hand(
                players=[
                    PlayerInfo(0, "Bot", None if i > 0 else my_stack),
                    PlayerInfo(1, "Opp", None if i > 0 else opp_stack),
                ],
                dealer_id=i % 2,
            )
            api.deal_hole_cards(["Ac", "Kd"])
            api.request_action("preflop", pot=3.0, current_bet=2.0,
                               to_call=2.0, my_stack=my_stack)
            # Simulate bot winning 5 chips each hand
            my_stack += 5.0
            opp_stack -= 5.0
            api.hand_over(winner_ids=[0], pot=10.0,
                          final_stacks={0: my_stack, 1: opp_stack})

        assert api._session_stacks[0] == 225.0
        assert api._session_stacks[1] == 175.0


class TestBugFixes:
    """Regression tests for the two confirmed bugs."""

    # ------------------------------------------------------------------
    # Bug 1: position_of() used player_id as list index
    # ------------------------------------------------------------------

    def test_position_non_contiguous_player_ids(self):
        """player_id 不连续时，位置判断必须正确。"""
        # player_ids: 0, 5, 99 — dealer_pos=0 → index 0 is BTN
        players = [
            Player(0,  "Bot",  200.0),
            Player(5,  "Opp1", 200.0),
            Player(99, "Opp2", 200.0),
        ]
        gs = GameState(players=players, dealer_pos=0, big_blind=2.0)
        # index 0 = BTN, index 1 = SB, index 2 = BB
        assert gs.position_of(players[0]) == "BTN"
        assert gs.position_of(players[1]) == "SB"
        assert gs.position_of(players[2]) == "BB"

    def test_position_large_player_ids(self):
        """player_id 很大时不能越界。"""
        players = [
            Player(100, "A", 200.0),
            Player(200, "B", 200.0),
        ]
        gs = GameState(players=players, dealer_pos=0, big_blind=2.0)
        # HU: dealer_pos=0 → index 0 is BTN, index 1 is BB
        assert gs.position_of(players[0]) == "BTN"
        assert gs.position_of(players[1]) == "BB"

    def test_position_via_api_non_contiguous(self):
        """通过 API 接入路径验证位置判断正确传递到决策。"""
        api = PokerFateAPI(my_player_id=100, big_blind=2.0, autosave_path=None)
        api.new_hand(
            players=[
                PlayerInfo(100, "PokerFate", 200.0),
                PlayerInfo(200, "Opp",       200.0),
            ],
            dealer_id=100,  # player_id=100 在座位 0，是 BTN
        )
        api.deal_hole_cards(["Ac", "Ad"])
        # BTN 面对 BB（没有开牌动作），应该加注（open raise）
        decision = api.request_action(
            street="preflop", pot=3.0, current_bet=2.0,
            to_call=2.0, my_stack=200.0,
        )
        assert decision.action == "raise"

    def test_api_infers_empty_playerinfo_positions_for_range_tracker(self):
        """Empty PlayerInfo.position should not collapse runtime features to CO."""
        api = PokerFateAPI(my_player_id=100, big_blind=2.0, autosave_path=None)
        api.new_hand(
            players=[
                PlayerInfo(100, "PokerFate", 200.0),
                PlayerInfo(200, "Opp SB", 200.0),
                PlayerInfo(300, "Opp BB", 200.0),
            ],
            dealer_id=100,
        )

        assert api._hand_positions[100] == "BTN"
        assert api._hand_positions[200] == "SB"
        assert api._hand_positions[300] == "BB"
        assert api._bot._range_tracker._action_meta[200]["position"] == "SB"
        assert api._bot._range_tracker._action_meta[300]["position"] == "BB"

    def test_api_uses_playerinfo_position_when_dealer_player_is_missing(self):
        """Dead-button hands must use upstream positions, not dealer_pos=0."""
        hero_id = 1006
        api = PokerFateAPI(my_player_id=hero_id, big_blind=10_000.0, autosave_path=None)
        api.new_hand(
            players=[
                PlayerInfo(1, "CrispyPegion", 1_000_000.0, "BB"),
                PlayerInfo(hero_id, "Royal Police", 1_000_000.0, "UTG"),
                PlayerInfo(2, "miraclerogue", 1_000_000.0, "UTG+1"),
                PlayerInfo(3, "小莫丶", 1_000_000.0, "UTG+2"),
                PlayerInfo(4, "Atoom", 1_000_000.0, "SB"),
            ],
            dealer_id=10454453,
        )

        gs = api._build_game_state(
            street="preflop",
            pot=15_000.0,
            current_bet=10_000.0,
            my_stack=1_000_000.0,
            my_current_bet_this_street=0.0,
        )
        hero = next(p for p in gs.players if p.player_id == hero_id)

        assert gs.position_of(hero) == "UTG"

        for p in api._players:
            p.is_folded = p.player_id not in (1, hero_id)
        postflop = api._build_game_state(
            street="flop",
            pot=105_000.0,
            current_bet=0.0,
            my_stack=970_000.0,
            my_current_bet_this_street=0.0,
        )
        hero = next(p for p in postflop.players if p.player_id == hero_id)
        assert postflop.position_of(hero) == "UTG"
        assert postflop.is_ip(hero) is True

    def test_api_uses_playerinfo_position_when_player_order_is_not_seat_order(self):
        """Runtime position must not depend on arbitrary upstream player order."""
        hero_id = 682
        api = PokerFateAPI(my_player_id=hero_id, big_blind=10_000.0, autosave_path=None)
        api.new_hand(
            players=[
                PlayerInfo(1, "danking123", 1_000_000.0, "UTG+2"),
                PlayerInfo(2, "艾伊西斯", 1_000_000.0, "SB"),
                PlayerInfo(hero_id, "Royal Police", 1_000_000.0, "BB"),
                PlayerInfo(3, "dsfg", 1_000_000.0, "UTG"),
                PlayerInfo(4, "菌军君", 1_000_000.0, "UTG+1"),
                PlayerInfo(5, "虎贲", 1_000_000.0, "BTN"),
            ],
            dealer_id=5,
        )

        gs = api._build_game_state(
            street="preflop",
            pot=15_000.0,
            current_bet=10_000.0,
            my_stack=1_000_000.0,
            my_current_bet_this_street=10_000.0,
        )
        hero = next(p for p in gs.players if p.player_id == hero_id)

        assert gs.position_of(hero) == "BB"

    # ------------------------------------------------------------------
    # Bug 2: is_cbet_spot / is_3bet_spot 永远是 False
    # ------------------------------------------------------------------

    def test_3bet_spot_detected(self):
        """对手回应一次开牌加注时，应记录为 3-bet 机会。"""
        api = PokerFateAPI(my_player_id=0, big_blind=2.0, autosave_path=None)
        api.new_hand(
            players=[PlayerInfo(0, "Bot", 200.0), PlayerInfo(1, "Opp", 200.0)],
            dealer_id=0,
        )
        api.deal_hole_cards(["Ac", "Kd"])

        # Bot 开牌加注（记录到 action_history）
        api._action_history.append((0, Action(ActionType.RAISE, 6.0), "preflop"))

        before = api._bot.opponent_model.get(1).three_bet_opportunities

        # 对手回应（fold）—— 应该被识别为 3-bet spot
        api.notify_action(ActionEvent(1, "fold", 0.0, "preflop"))

        after = api._bot.opponent_model.get(1).three_bet_opportunities
        assert after == before + 1, "3-bet opportunity should be recorded"

    def test_cbet_spot_detected_on_fold(self):
        """对手 fold 回应 bot 的翻牌下注时，fold_to_cbet 应被记录。"""
        api = PokerFateAPI(my_player_id=0, big_blind=2.0, autosave_path=None)
        api.new_hand(
            players=[PlayerInfo(0, "Bot", 200.0), PlayerInfo(1, "Opp", 200.0)],
            dealer_id=0,
        )
        api.deal_hole_cards(["Ac", "Kd"])
        api._action_history.append((0, Action(ActionType.RAISE, 6.0), "preflop"))
        api.deal_board(["As", "7d", "2c"], street="flop")

        # Bot 在翻牌下注（模拟已记录到 history）
        api._action_history.append((0, Action(ActionType.RAISE, 5.0), "flop"))

        before_opps = api._bot.opponent_model.get(1).fold_to_cbet_opps
        before_folds = api._bot.opponent_model.get(1).fold_to_cbet_count

        # 对手 fold
        api.notify_action(ActionEvent(1, "fold", 0.0, "flop"))

        after_opps = api._bot.opponent_model.get(1).fold_to_cbet_opps
        after_folds = api._bot.opponent_model.get(1).fold_to_cbet_count
        assert after_opps == before_opps + 1, "fold_to_cbet opportunity should be recorded"
        assert after_folds == before_folds + 1, "fold_to_cbet count should be recorded"

    def test_cbet_spot_not_triggered_without_bot_bet(self):
        """对手主动下注（非回应 bot 的 c-bet）时，不应记录为 cbet spot。"""
        api = PokerFateAPI(my_player_id=0, big_blind=2.0, autosave_path=None)
        api.new_hand(
            players=[PlayerInfo(0, "Bot", 200.0), PlayerInfo(1, "Opp", 200.0)],
            dealer_id=0,
        )
        api.deal_hole_cards(["Ac", "Kd"])
        api.deal_board(["As", "7d", "2c"], street="flop")
        # 翻牌无人下注，对手主动 donk-bet
        before = api._bot.opponent_model.get(1).fold_to_cbet_opps
        api.notify_action(ActionEvent(1, "raise", 5.0, "flop"))
        assert api._bot.opponent_model.get(1).fold_to_cbet_opps == before

    def test_cbet_spot_not_inherited_from_old_street(self):
        """只有旧街 hero 加注、当前街没有 hero 下注时，不应记录 cbet response。"""
        api = PokerFateAPI(my_player_id=0, big_blind=2.0, autosave_path=None)
        api.new_hand(
            players=[PlayerInfo(0, "Bot", 200.0), PlayerInfo(1, "Opp", 200.0)],
            dealer_id=0,
        )
        api.deal_hole_cards(["Ac", "Kd"])
        api._action_history.append((0, Action(ActionType.RAISE, 6.0), "preflop"))
        api.deal_board(["As", "7d", "2c"], street="flop")
        api.deal_board(["2h"], street="turn")
        before = api._bot.opponent_model.get(1).fold_to_cbet_opps
        api.notify_action(ActionEvent(1, "fold", 0.0, "turn"))
        assert api._bot.opponent_model.get(1).fold_to_cbet_opps == before

    def test_3bet_spot_not_triggered_on_open(self):
        """第一个开牌动作不是 3-bet 机会。"""
        api = PokerFateAPI(my_player_id=0, big_blind=2.0, autosave_path=None)
        api.new_hand(
            players=[PlayerInfo(0, "Bot", 200.0), PlayerInfo(1, "Opp", 200.0)],
            dealer_id=0,
        )
        api.deal_hole_cards(["Ac", "Kd"])
        before = api._bot.opponent_model.get(1).three_bet_opportunities
        # 对手第一个动作（open raise），没有前置加注，不是 3-bet spot
        api.notify_action(ActionEvent(1, "raise", 6.0, "preflop"))
        assert api._bot.opponent_model.get(1).three_bet_opportunities == before

    def test_fold_to_3bet_records_opener_response(self):
        api = PokerFateAPI(my_player_id=0, big_blind=2.0, autosave_path=None)
        api.new_hand(
            players=[PlayerInfo(0, "Bot", 200.0), PlayerInfo(1, "Opp", 200.0)],
            dealer_id=0,
        )
        api.deal_hole_cards(["Ac", "Kd"])
        api._action_history.append((1, Action(ActionType.RAISE, 6.0), "preflop"))
        api._action_history.append((0, Action(ActionType.RAISE, 20.0), "preflop"))
        before = api._bot.opponent_model.get(1).fold_to_3bet_opps
        three_bet_before = api._bot.opponent_model.get(1).three_bet_opportunities
        api.notify_action(ActionEvent(1, "fold", 0.0, "preflop"))
        stats = api._bot.opponent_model.get(1)
        assert stats.fold_to_3bet_opps == before + 1
        assert stats.fold_to_3bet_count == 1
        assert stats.three_bet_opportunities == three_bet_before

    def test_river_fold_rate_uses_facing_bet_opportunities(self):
        api = PokerFateAPI(my_player_id=0, big_blind=2.0, autosave_path=None)
        api.new_hand(
            players=[PlayerInfo(0, "Bot", 200.0), PlayerInfo(1, "Opp", 200.0)],
            dealer_id=0,
        )
        api.deal_hole_cards(["Ac", "Kd"])
        api.deal_board(["As", "7d", "2c"], street="flop")
        api.deal_board(["3h"], street="turn")
        api.deal_board(["4s"], street="river")
        api.notify_action(ActionEvent(1, "check", 0.0, "river"))
        stats = api._bot.opponent_model.get(1)
        assert stats.river_facing_bet_opps == 0

        api._action_history.append((0, Action(ActionType.RAISE, 10.0), "river"))
        api.notify_action(ActionEvent(1, "fold", 0.0, "river"))
        assert stats.river_facing_bet_opps == 1
        assert stats.river_fold_rate == pytest.approx(1.0)


class TestSeatManagement:
    """Tests for notify_player_left and seat-change opponent model isolation."""

    def test_notify_player_left_clears_session_data(self):
        """notify_player_left removes player from session stacks and players list."""
        api = make_api()
        api.new_hand(
            players=[PlayerInfo(0, "Bot", 200.0), PlayerInfo(1, "Opp", 200.0)],
            dealer_id=0,
        )
        api.hand_over(winner_ids=[0], pot=3.0, final_stacks={0: 202.0, 1: 198.0})

        api.notify_player_left(player_id=1)

        assert 1 not in api._session_stacks

    def test_new_player_after_left_gets_fresh_opponent_model(self):
        """After notify_player_left, a new player at same physical seat gets clean stats."""
        api = make_api()
        api.new_hand(
            players=[PlayerInfo(0, "Bot", 200.0), PlayerInfo(1, "OldPlayer", 200.0)],
            dealer_id=0,
        )
        # Accumulate stats for OldPlayer
        api.deal_hole_cards(["Ac", "Kd"])
        for _ in range(5):
            api.notify_action(ActionEvent(1, "fold", 0.0, "preflop"))
        api.hand_over(winner_ids=[0], pot=3.0)

        old_fold_count = api._bot.opponent_model.get(1).fold_count
        assert old_fold_count > 0

        # OldPlayer leaves; NewPlayer sits in same seat (but different id)
        api.notify_player_left(player_id=1)
        api.notify_player_joined(player_id=2, name="NewPlayer", stack=200.0)

        # NewPlayer's stats should be fresh
        new_stats = api._bot.opponent_model.get(2)
        assert new_stats.hands_seen == 0
        assert new_stats.fold_count == 0

    def test_returning_player_with_different_uid_starts_fresh(self):
        """Different player_id/uid with same name does not inherit history."""
        api = make_api()
        api.new_hand(
            players=[PlayerInfo(0, "Bot", 200.0), PlayerInfo(1, "Veteran", 200.0)],
            dealer_id=0,
        )
        api.deal_hole_cards(["Ac", "Kd"])
        for _ in range(10):
            api.notify_action(ActionEvent(1, "fold", 0.0, "preflop"))
        api.hand_over(winner_ids=[0], pot=3.0)

        saved_folds = api._bot.opponent_model.get(1).fold_count
        assert saved_folds > 0

        api.notify_player_left(player_id=1)
        api.notify_player_joined(player_id=9, name="Veteran", stack=200.0)

        restored = api._bot.opponent_model.get(9)
        assert restored.fold_count == 0

    def test_notify_player_left_then_rejoin_same_id(self):
        """Player leaves and rejoins at same id — stats are preserved via archive restore."""
        api = make_api()
        api.new_hand(
            players=[PlayerInfo(0, "Bot", 200.0), PlayerInfo(3, "Player3", 200.0)],
            dealer_id=0,
        )
        api.deal_hole_cards(["7c", "2d"])
        api.notify_action(ActionEvent(3, "raise", 6.0, "preflop"))
        api.hand_over(winner_ids=[3], pot=5.0)

        raise_count_before = api._bot.opponent_model.get(3).raise_count

        api.notify_player_left(player_id=3)
        # Same player rejoins at same id and name
        api.notify_player_joined(player_id=3, name="Player3", stack=200.0)

        # Stats should be restored (not zero)
        assert api._bot.opponent_model.get(3).raise_count == raise_count_before


class TestExternalDecisionEngine:
    class FakeG5Engine:
        def __init__(self):
            self.actions = []
            self.finished = []
            self.decide_calls = 0
            self.last_result = {
                "action": "Raise",
                "byAmount": 10,
                "checkCallEV": 1.2,
                "betRaiseEV": 3.4,
                "message": "fake g5",
            }

        def start_hand(self, **kwargs):
            self.started = kwargs

        def deal_hole_cards(self, cards):
            self.hole_cards = cards

        def deal_board(self, cards, street):
            self.board = (cards, street)

        def notify_action(self, **kwargs):
            self.actions.append(kwargs)

        def decide(self, gs, *, hero_player_id, my_current_bet_this_street):
            self.decide_calls += 1
            return Action(ActionType.RAISE, 12.0)

        def finish_hand(self, **kwargs):
            self.finished.append(kwargs)

        def disable_current_hand(self, reason):
            self.disabled_reason = reason

    def _enable_fake_g5(self, api, engine):
        api._external_decision_engine = engine
        api._external_decision_engine_enabled = True
        api._external_decision_engine_active = True
        api._external_decision_engine_shadow = False
        api._external_decision_engine_mode = "g5_all"
        api._external_decision_engine_name = "g5"

    def _enable_shadow_g5(self, api, engine):
        api._external_decision_engine = engine
        api._external_decision_engine_enabled = True
        api._external_decision_engine_active = False
        api._external_decision_engine_shadow = True
        api._external_decision_engine_mode = "local"
        api._external_decision_engine_name = "g5"

    def _enable_hybrid_g5(self, api, engine):
        api._external_decision_engine = engine
        api._external_decision_engine_enabled = True
        api._external_decision_engine_active = True
        api._external_decision_engine_shadow = True
        api._external_decision_engine_mode = "postflop"
        api._external_decision_engine_name = "g5"

    def test_runtime_set_decision_engine_reconfigures_engine(self, monkeypatch):
        api = make_api()
        calls = []

        class OldEngine:
            def __init__(self):
                self.closed = False

            def close(self):
                self.closed = True

        old = OldEngine()
        api._external_decision_engine = old
        api._external_decision_engine_enabled = True

        def fake_configure(**kwargs):
            calls.append(kwargs)
            api._external_decision_engine_name = "g5"
            api._external_decision_engine_mode = kwargs["decision_engine"]

        monkeypatch.setattr(api, "_configure_decision_engine", fake_configure)

        status = api.set_decision_engine("g5_all")

        assert old.closed is True
        assert calls[-1]["decision_engine"] == "g5_all"
        assert status["requested"] == "g5_all"
        assert status["engine"] == "g5"
        assert status["mode"] == "g5_all"

    def test_realtime_cfr_decision_engine_status(self):
        api = PokerFateAPI(
            my_player_id=0,
            big_blind=2.0,
            small_blind=1.0,
            autosave_path=None,
            decision_engine="realtime-cfr",
        )

        status = api.decision_engine_status()

        assert status["requested"] == "realtime_cfr"
        assert status["engine"] == "realtime_cfr"
        assert status["mode"] == "turn_river"
        assert status["enabled"] is True
        assert status["active"] is True
        assert status["shadow"] is False
        assert status["realtime_cfr"] is True

    def test_cfr_decision_engine_status(self):
        api = PokerFateAPI(
            my_player_id=0,
            big_blind=2.0,
            small_blind=1.0,
            autosave_path=None,
            decision_engine="cfr",
        )

        status = api.decision_engine_status()

        assert status["requested"] == "cfr"
        assert status["engine"] == "cfr"
        assert status["mode"] == "flop_book_turn_river"
        assert status["enabled"] is True
        assert status["active"] is True
        assert status["shadow"] is False
        assert status["realtime_cfr"] is True
        assert status["flop_book"] is True

    def test_realtime_cfr_hero_range_provider_is_public_reach_range(self):
        from pokerfate.strategy.range_v2 import hand_combo_map as hcm

        def combo_index(combo: str) -> int:
            c1 = hcm.card_to_int(Card.from_str(combo[:2]))
            c2 = hcm.card_to_int(Card.from_str(combo[2:]))
            return hcm.COMBO_TO_IDX[tuple(sorted((c1, c2)))]

        api = PokerFateAPI(
            my_player_id=0,
            big_blind=2.0,
            small_blind=1.0,
            autosave_path=None,
            decision_engine="realtime_cfr",
        )
        start_hand(api)
        api.deal_hole_cards(["As", "Ah"])
        api.deal_board(["Kh", "7d", "2c"], street="flop", pot=20.0)
        api.deal_board(["9s"], street="turn", pot=60.0)
        api._bot._my_street_actions["preflop"] = "raise"
        api._bot._my_street_actions["flop"] = "check"

        gs = api._build_game_state(
            street="turn",
            pot=60.0,
            current_bet=0.0,
            my_stack=200.0,
            my_current_bet_this_street=0.0,
        )
        weights = api._realtime_cfr_hero_range_weights(gs, "turn")

        assert sum(weights) == pytest.approx(1.0)
        assert weights[combo_index("AsAh")] > 0.0
        assert weights[combo_index("AsKs")] > 0.0
        assert weights[combo_index("KhKd")] == 0.0

    def test_invalid_decision_engine_is_pure_local(self):
        api = PokerFateAPI(
            my_player_id=0,
            big_blind=2.0,
            small_blind=1.0,
            autosave_path=None,
            decision_engine="unknown-engine",
        )

        status = api.decision_engine_status()

        assert status["requested"] == "unknown_engine"
        assert status["engine"] == "local"
        assert status["enabled"] is False
        assert status["active"] is False
        assert status["shadow"] is False
        assert status["realtime_cfr"] is False
        assert status["flop_book"] is False

    def test_external_engine_decision_is_used_and_recorded(self):
        api = make_api()
        fake = self.FakeG5Engine()
        self._enable_fake_g5(api, fake)

        start_hand(api)
        api.deal_hole_cards(["Ac", "Kd"])
        decision = api.request_action(
            "preflop",
            pot=5.0,
            current_bet=2.0,
            to_call=0.0,
            my_stack=198.0,
            my_current_bet_this_street=2.0,
            is_bb_option=True,
        )

        assert decision == BotDecision("raise", 12.0)
        assert api.last_decision_diagnostics()["decision_source"] == "g5"
        assert fake.actions[-1]["player_id"] == 0
        assert fake.actions[-1]["amount_added"] == 10.0
        assert fake.actions[-1]["total_bet_after"] == 12.0

    def test_hybrid_g5_uses_local_preflop_then_g5_postflop(self):
        api = make_api()
        fake = self.FakeG5Engine()
        self._enable_hybrid_g5(api, fake)
        api._bot.decide = lambda gs, pid, is_bb_option=False: Action(ActionType.CHECK, 0.0)

        start_hand(api)
        api.deal_hole_cards(["Ac", "Kd"])
        preflop = api.request_action(
            "preflop",
            pot=3.0,
            current_bet=0.0,
            to_call=0.0,
            my_stack=200.0,
        )

        assert preflop == BotDecision("check", 0.0)
        assert api.last_decision_diagnostics()["decision_source"] == "pokerfate"
        assert api.last_decision_diagnostics()["g5_shadow"]["action"] == "raise"
        assert fake.actions[-1]["action"] == "raise"

        api.deal_board(["As", "7d", "2c"], "flop")
        flop = api.request_action(
            "flop",
            pot=13.0,
            current_bet=0.0,
            to_call=0.0,
            my_stack=200.0,
        )

        assert flop == BotDecision("raise", 12.0)
        diag = api.last_decision_diagnostics()
        assert diag["decision_source"] == "g5"
        assert diag["local_shadow"]["status"] == "ok"
        assert fake.decide_calls == 2

    def test_hybrid_g5_preflop_fold_keeps_local_postflop(self):
        class FoldingG5(self.FakeG5Engine):
            def decide(self, gs, *, hero_player_id, my_current_bet_this_street):
                self.decide_calls += 1
                self.last_result = {
                    "action": "Fold",
                    "byAmount": 0,
                    "checkCallEV": -1.0,
                    "betRaiseEV": -2.0,
                    "message": "fake fold",
                }
                return Action(ActionType.FOLD, 0.0)

        api = make_api()
        fake = FoldingG5()
        self._enable_hybrid_g5(api, fake)
        api._bot.decide = lambda gs, pid, is_bb_option=False: Action(ActionType.CALL, 0.0)

        start_hand(api)
        api.deal_hole_cards(["Ac", "Kd"])
        preflop = api.request_action(
            "preflop",
            pot=5.0,
            current_bet=2.0,
            to_call=2.0,
            my_stack=200.0,
        )
        assert preflop == BotDecision("call", 0.0)
        assert api.last_decision_diagnostics()["g5_shadow"]["action"] == "fold"

        api.deal_board(["As", "7d", "2c"], "flop")
        flop = api.request_action(
            "flop",
            pot=7.0,
            current_bet=0.0,
            to_call=0.0,
            my_stack=198.0,
        )
        assert flop == BotDecision("call", 0.0)
        assert api.last_decision_diagnostics()["decision_source"] == "pokerfate"
        assert api.last_decision_diagnostics()["g5_shadow"]["status"] == "folded"
        assert fake.decide_calls == 1

    def test_shadow_g5_decision_is_recorded_but_not_used(self):
        api = make_api()
        fake = self.FakeG5Engine()
        self._enable_shadow_g5(api, fake)
        api._bot.decide = lambda gs, pid, is_bb_option=False: Action(ActionType.CHECK, 0.0)

        start_hand(api)
        api.deal_hole_cards(["Ac", "Kd"])
        decision = api.request_action(
            "preflop",
            pot=3.0,
            current_bet=0.0,
            to_call=0.0,
            my_stack=200.0,
        )

        diag = api.last_decision_diagnostics()
        assert decision == BotDecision("check", 0.0)
        assert diag["decision_source"] == "pokerfate"
        assert diag["g5_shadow"]["status"] == "ok"
        assert diag["g5_shadow"]["action"] == "raise"
        assert fake.decide_calls == 1
        assert fake.actions[-1]["player_id"] == 0
        assert fake.actions[-1]["action"] == "raise"
        assert fake.actions[-1]["amount_added"] == 10.0
        assert fake.actions[-1]["total_bet_after"] == 10.0

    def test_shadow_g5_raise_uses_current_street_bet_not_total_hand_money(self):
        api = make_api()
        fake = self.FakeG5Engine()
        self._enable_shadow_g5(api, fake)

        shadow = {
            "status": "ok",
            "result": {
                "action": "Raise",
                "byAmount": 30,
                "heroMoneyInPot": 105,
            },
        }
        api._notify_external_engine_shadow_action(
            shadow,
            street="flop",
            my_current_bet_this_street=5,
        )

        assert fake.actions[-1]["player_id"] == 0
        assert fake.actions[-1]["action"] == "raise"
        assert fake.actions[-1]["amount_added"] == 30.0
        assert fake.actions[-1]["total_bet_after"] == 35.0

    def test_shadow_g5_follows_g5_line_after_local_fold(self):
        class ShadowLineG5(self.FakeG5Engine):
            def __init__(self):
                super().__init__()
                self.player_to_act_id = 0
                self._results = [
                    {
                        "action": "Call",
                        "byAmount": 2,
                        "amountToCall": 2,
                        "heroMoneyInPot": 0,
                        "checkCallEV": 1.0,
                        "betRaiseEV": -1.0,
                        "message": "g5 calls",
                    },
                    {
                        "action": "Check",
                        "byAmount": 0,
                        "amountToCall": 0,
                        "heroMoneyInPot": 2,
                        "checkCallEV": 0.0,
                        "betRaiseEV": -1.0,
                        "message": "g5 checks",
                    },
                ]

            def decide(self, gs, *, hero_player_id, my_current_bet_this_street):
                self.last_result = self._results[self.decide_calls]
                self.decide_calls += 1
                if self.last_result["action"] == "Call":
                    return Action(ActionType.CALL, 0.0)
                return Action(ActionType.CHECK, 0.0)

            def notify_action(self, **kwargs):
                super().notify_action(**kwargs)
                self.player_to_act_id = 1 if kwargs["player_id"] == 0 else 0

        api = make_api()
        fake = ShadowLineG5()
        self._enable_shadow_g5(api, fake)
        api._bot.decide = lambda gs, pid, is_bb_option=False: Action(ActionType.FOLD, 0.0)

        start_hand(api)
        api.deal_hole_cards(["Ac", "Kd"])
        decision = api.request_action(
            "preflop",
            pot=5.0,
            current_bet=2.0,
            to_call=2.0,
            my_stack=200.0,
        )

        assert decision == BotDecision("fold", 0.0)
        assert fake.actions[-1]["player_id"] == 0
        assert fake.actions[-1]["action"] == "call"

        api.notify_action(ActionEvent(1, "check", 0.0, "preflop"))

        assert fake.decide_calls == 2
        assert fake.actions[-1]["player_id"] == 0
        assert fake.actions[-1]["action"] == "check"

    def test_shadow_g5_fold_stops_future_shadow_decisions_this_hand(self):
        class FoldingG5(self.FakeG5Engine):
            def __init__(self):
                super().__init__()
                self.last_result = {
                    "action": "Fold",
                    "byAmount": 0,
                    "checkCallEV": -1.0,
                    "betRaiseEV": -2.0,
                    "message": "fake fold",
                }

            def decide(self, gs, *, hero_player_id, my_current_bet_this_street):
                self.decide_calls += 1
                return Action(ActionType.FOLD, 0.0)

        api = make_api()
        fake = FoldingG5()
        self._enable_shadow_g5(api, fake)
        api._bot.decide = lambda gs, pid, is_bb_option=False: Action(ActionType.CALL, 0.0)

        start_hand(api)
        api.deal_hole_cards(["Ac", "Kd"])
        first = api.request_action(
            "preflop",
            pot=5.0,
            current_bet=2.0,
            to_call=2.0,
            my_stack=200.0,
        )
        assert first == BotDecision("call", 0.0)
        assert api.last_decision_diagnostics()["g5_shadow"]["action"] == "fold"
        assert fake.decide_calls == 1
        assert fake.actions == []

        second = api.request_action(
            "flop",
            pot=7.0,
            current_bet=0.0,
            to_call=0.0,
            my_stack=198.0,
        )
        assert second == BotDecision("call", 0.0)
        assert api.last_decision_diagnostics()["g5_shadow"]["status"] == "folded"
        assert fake.decide_calls == 1

    def test_shadow_g5_ignores_forced_post_disable_quietly(self):
        api = make_api()
        fake = self.FakeG5Engine()
        self._enable_shadow_g5(api, fake)
        api._bot.decide = lambda gs, pid, is_bb_option=False: Action(ActionType.CHECK, 0.0)

        start_hand(api)
        api.deal_hole_cards(["Ac", "Kd"])
        api.disable_external_decision_current_hand(
            "unsupported forced post: seat=1 action_type=11 chips=10000"
        )
        decision = api.request_action(
            "preflop",
            pot=3.0,
            current_bet=0.0,
            to_call=0.0,
            my_stack=200.0,
        )

        diag = api.last_decision_diagnostics()["g5_shadow"]
        assert decision == BotDecision("check", 0.0)
        assert diag["status"] == "ok"
        assert diag["action"] == "raise"
        assert not diag.get("warning")
        assert "强制补盲" not in diag["reasoning"]
        assert fake.decide_calls == 1
        assert not hasattr(fake, "disabled_reason")

    def test_external_engine_failure_falls_back_to_local_bot(self):
        class FailingG5(self.FakeG5Engine):
            def decide(self, gs, *, hero_player_id, my_current_bet_this_street):
                raise RuntimeError("g5 out of sync")

        api = make_api()
        fake = FailingG5()
        self._enable_fake_g5(api, fake)
        api._bot.decide = lambda gs, pid, is_bb_option=False: Action(ActionType.CHECK, 0.0)

        start_hand(api)
        api.deal_hole_cards(["Ac", "Kd"])
        decision = api.request_action(
            "preflop",
            pot=3.0,
            current_bet=0.0,
            to_call=0.0,
            my_stack=200.0,
        )

        assert decision == BotDecision("check", 0.0)
        assert api.last_decision_diagnostics()["decision_source"] == "pokerfate"
        assert "g5 out of sync" in api._external_decision_engine_error

    def test_shadow_disabled_does_not_report_stale_g5_unavailable(self):
        api = make_api()
        api._external_decision_engine_shadow = False
        api._external_decision_engine_error = "solver_failed_or_timeout"
        gs = GameState(
            players=[
                Player(0, "PokerFate", 200.0, hole_cards=[Card.from_str("Ac"), Card.from_str("Kd")]),
                Player(1, "Opponent", 200.0),
            ],
            big_blind=2.0,
        )

        shadow = api._shadow_decide_with_external_engine(
            gs,
            street="preflop",
            my_current_bet_this_street=0.0,
        )

        assert shadow is None

    def test_new_hand_clears_transient_external_engine_error(self):
        api = make_api()
        fake = self.FakeG5Engine()
        self._enable_fake_g5(api, fake)
        api._external_decision_engine_error = "g5 out of sync"

        start_hand(api)

        assert api._external_decision_engine_error == ""

    def test_new_hand_clears_realtime_cfr_error(self):
        api = PokerFateAPI(
            my_player_id=0,
            big_blind=2.0,
            small_blind=1.0,
            autosave_path=None,
            decision_engine="realtime_cfr",
        )
        api._realtime_cfr_error = "solver_worker_error"
        api._external_decision_engine_error = "solver_worker_error"
        assert api.decision_engine_status()["error"] == "solver_worker_error"

        start_hand(api)

        assert api._realtime_cfr_error == ""
        assert api._external_decision_engine_error == ""
        assert api.decision_engine_status()["error"] == ""

    def test_external_engine_hand_disable_skips_g5_until_next_hand(self):
        class DisabledG5(self.FakeG5Engine):
            def __init__(self):
                super().__init__()
                self.decide_calls = 0

            def decide(self, gs, *, hero_player_id, my_current_bet_this_street):
                self.decide_calls += 1
                return Action(ActionType.RAISE, 12.0)

        api = make_api()
        fake = DisabledG5()
        self._enable_fake_g5(api, fake)
        api._bot.decide = lambda gs, pid, is_bb_option=False: Action(ActionType.CHECK, 0.0)

        start_hand(api)
        api.disable_external_decision_current_hand("manual_test_disable")
        decision = api.request_action(
            "preflop",
            pot=3.0,
            current_bet=0.0,
            to_call=0.0,
            my_stack=200.0,
        )

        assert decision == BotDecision("check", 0.0)
        assert fake.decide_calls == 0
        assert fake.actions == []
        assert fake.disabled_reason == "manual_test_disable"

        start_hand(api)
        assert api._external_decision_hand_disabled_reason == ""

    def test_active_g5_ignores_forced_post_disable(self):
        api = make_api()
        fake = self.FakeG5Engine()
        self._enable_fake_g5(api, fake)
        api._bot.decide = lambda gs, pid, is_bb_option=False: Action(ActionType.CHECK, 0.0)

        start_hand(api)
        api.disable_external_decision_current_hand("unsupported forced post")
        decision = api.request_action(
            "preflop",
            pot=3.0,
            current_bet=0.0,
            to_call=0.0,
            my_stack=200.0,
        )

        assert decision == BotDecision("raise", 12.0)
        assert fake.decide_calls == 1
        assert not hasattr(fake, "disabled_reason")

    def test_hand_over_sends_gross_winner_payouts_to_external_engine(self):
        api = make_api()
        fake = self.FakeG5Engine()
        self._enable_fake_g5(api, fake)

        start_hand(api)
        api.hand_over(
            winner_ids=[1],
            pot=57.0,
            winner_payouts={1: 57.0},
            final_stacks={0: 170.0, 1: 230.0},
            showdown_hands={1: ["As", "Ah"]},
        )

        assert fake.finished[-1]["winner_payouts"] == {1: 57.0}
        assert "showdown_hands" not in fake.finished[-1]
