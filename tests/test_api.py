"""Tests for the external API interface (PokerFateAPI)."""

import json
import os
import tempfile
import pytest
from pokerfate.api import PokerFateAPI, PlayerInfo, ActionEvent, BotDecision
from pokerfate.bot.opponent_model import OpponentModel
from pokerfate.core.game_state import GameState, Player, Street


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
    def test_new_hand_and_hole_cards(self):
        api = make_api()
        start_hand(api)
        api.deal_hole_cards(["Ac", "Ad"])
        assert len(api._hole_cards) == 2

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

    def test_notify_action_updates_state(self):
        api = make_api()
        start_hand(api)
        api.deal_hole_cards(["Ac", "Kd"])
        api.notify_action(ActionEvent(
            player_id=1, action="raise", amount=6.0, street="preflop"
        ))
        assert len(api._action_history) == 1

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
            # Opponent (id=1) should be in the saved file
            assert "1" in data["stats"]
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

    def test_name_based_model_migration(self):
        """Same opponent name, different player_id → stats are preserved."""
        api = make_api()
        # Session 1: opponent is id=1 named "GPT"
        api.new_hand(
            players=[PlayerInfo(0, "Bot", 200.0), PlayerInfo(1, "GPT", 200.0)],
            dealer_id=0,
        )
        api.deal_hole_cards(["Ac", "Kd"])
        for _ in range(5):
            api.notify_action(ActionEvent(1, "fold", 0.0, "preflop"))
        hands_after = api._bot.opponent_model.get(1).hands_seen

        # "GPT" reconnects with a new player_id=7
        api.notify_player_joined(player_id=7, name="GPT", stack=200.0)
        # Stats should have migrated to id=7
        stats_new_id = api._bot.opponent_model.get(7)
        assert stats_new_id.fold_count > 0

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
        from pokerfate.core.game_state import Action, ActionType
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
        api.deal_board(["As", "7d", "2c"], street="flop")

        # Bot 在翻牌下注（模拟已记录到 history）
        from pokerfate.core.game_state import Action, ActionType
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

    def test_returning_player_with_different_id_restores_stats(self):
        """Player who left and rejoins under a different player_id gets their history back."""
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

        # Veteran leaves, then rejoins with a new player_id
        api.notify_player_left(player_id=1)
        api.notify_player_joined(player_id=9, name="Veteran", stack=200.0)

        # Stats should be restored on new id
        restored = api._bot.opponent_model.get(9)
        assert restored.fold_count == saved_folds

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
