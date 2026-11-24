"""Tests for the external API interface (PokerFateAPI)."""

import json
import os
import tempfile
import pytest
from pokerfate.api import PokerFateAPI, PlayerInfo, ActionEvent, BotDecision
from pokerfate.core.card import Card
from pokerfate.core.game_state import Action, ActionType, GameState, Player


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

    @pytest.mark.parametrize("bet_street, showdown, expected", [
        # (bet_win_count, bluff_win_count, showdown_count) of a weak-handed winner
        ("turn", None, (0, 0, 0)),
        ("turn", ["Jh", "Th"], (0, 0, 1)),
        ("river", None, (1, 1, 0)),
    ])
    def test_weak_winner_counts_as_a_bluff_win_only_after_a_river_bet_without_showdown(
            self, bet_street, showdown, expected):
        api = make_api()
        start_hand(api)
        api.deal_hole_cards(["As", "Qh"])
        api.deal_board(["Kd", "7d", "2c"], street="flop", pot=20)
        api.deal_board(["9h"], street="turn", pot=60)
        if bet_street == "river":
            api.deal_board(["3s"], street="river", pot=90)
        api.notify_action(ActionEvent(1, "raise", 30.0, bet_street))
        api.hand_over(
            winner_ids=[1], pot=120 if bet_street == "river" else 90,
            final_stacks={0: 170, 1: 230}, winner_hand_types={1: 1}, my_profit_delta=-30,
            **({"showdown_hands": {1: showdown}} if showdown else {}),
        )
        stats = api._bot.opponent_model.get(1)
        assert (stats.bet_win_count, stats.bluff_win_count, stats.showdown_count) == expected

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


class TestPositionsAndStatOpportunities:
    """Seat positions, and the opportunities the opponent model counts."""

    @pytest.mark.parametrize("player_ids, expected", [
        ([0, 5, 99], ["BTN", "SB", "BB"]),
        ([100, 200], ["BTN", "BB"]),
    ])
    def test_game_state_position_follows_the_dealer_index(self, player_ids, expected):
        players = [Player(pid, f"P{pid}", 200.0) for pid in player_ids]
        gs = GameState(players=players, dealer_pos=0, big_blind=2.0)
        assert [gs.position_of(p) for p in players] == expected

    @pytest.mark.parametrize("seats, dealer_id, hero_id, expected", [
        # no labels: derived from the dealer
        ([(100, ""), (200, "")], 100, 100, {100: "BTN", 200: "BB"}),
        ([(100, ""), (200, ""), (300, "")], 100, 100, {100: "BTN", 200: "SB", 300: "BB"}),
        # labels given: used whatever the dealer id or the list order, 9-max names mapped to 6-max
        ([(1, "BB"), (1006, "UTG"), (2, "UTG+1"), (3, "UTG+2"), (4, "SB")], 10454453, 1006,
         {1: "BB", 1006: "UTG", 2: "MP", 3: "CO", 4: "SB"}),
        ([(1, "UTG+2"), (2, "SB"), (682, "BB"), (3, "UTG"), (4, "UTG+1"), (5, "BTN")], 5, 682,
         {1: "CO", 2: "SB", 682: "BB", 3: "UTG", 4: "MP", 5: "BTN"}),
    ])
    def test_api_hand_positions(self, seats, dealer_id, hero_id, expected):
        api = PokerFateAPI(my_player_id=hero_id, big_blind=2.0, autosave_path=None)
        api.new_hand(players=[PlayerInfo(pid, f"P{pid}", 200.0, label) for pid, label in seats],
                     dealer_id=dealer_id)
        gs = api._build_game_state(street="preflop", pot=3.0, current_bet=2.0,
                                   my_stack=200.0, my_current_bet_this_street=0.0)
        assert {p.player_id: gs.position_of(p) for p in gs.players} == expected
        tracker_meta = api._bot._range_tracker._action_meta
        opponents = {pid: pos for pid, pos in expected.items() if pid != hero_id}
        assert {pid: tracker_meta[pid]["position"] for pid in opponents} == opponents

    _FLOP = ("flop", ["As", "7d", "2c"])
    _TURN = ("turn", ["2h"])

    @pytest.mark.parametrize("players, raises, boards, events, player, stat, added", [
        # 3-bet chances: answering an open raise
        (2, [(0, 6.0, "preflop")], [], [(1, "fold", 0.0, "preflop")], 1, "three_bet_opportunities", 1),
        (2, [], [], [(1, "raise", 6.0, "preflop")], 1, "three_bet_opportunities", 0),
        # fold-to-3bet: the opener answering a 3-bet
        (2, [(1, 6.0, "preflop"), (0, 20.0, "preflop")], [], [(1, "fold", 0.0, "preflop")], 1, "fold_to_3bet_opps", 1),
        (2, [(1, 6.0, "preflop"), (0, 20.0, "preflop")], [], [(1, "fold", 0.0, "preflop")], 1, "fold_to_3bet_count", 1),
        (2, [(1, 6.0, "preflop"), (0, 20.0, "preflop")], [], [(1, "fold", 0.0, "preflop")], 1, "three_bet_opportunities", 0),
        # fold-to-cbet: answering the first bet of the flop, whoever made it
        (2, [(0, 6.0, "preflop"), (0, 5.0, "flop")], [_FLOP], [(1, "fold", 0.0, "flop")], 1, "fold_to_cbet_opps", 1),
        (2, [(0, 6.0, "preflop"), (0, 5.0, "flop")], [_FLOP], [(1, "fold", 0.0, "flop")], 1, "fold_to_cbet_count", 1),
        (3, [], [_FLOP], [(1, "raise", 5.0, "flop"), (2, "fold", 0.0, "flop")], 2, "fold_to_cbet_opps", 1),
        (3, [], [_FLOP], [(1, "raise", 5.0, "flop"), (2, "fold", 0.0, "flop")], 1, "fold_to_cbet_opps", 0),
        (2, [], [_FLOP], [(1, "raise", 5.0, "flop")], 1, "fold_to_cbet_opps", 0),
        (3, [], [_FLOP], [(1, "raise", 5.0, "flop"), (2, "raise", 15.0, "flop"), (1, "fold", 0.0, "flop")],
         1, "fold_to_cbet_opps", 0),
        (2, [(0, 6.0, "preflop")], [_FLOP, _TURN], [(1, "fold", 0.0, "turn")], 1, "fold_to_cbet_opps", 0),
    ])
    def test_stat_opportunities(self, players, raises, boards, events, player, stat, added):
        api = PokerFateAPI(my_player_id=0, big_blind=2.0, autosave_path=None)
        api.new_hand(players=[PlayerInfo(i, f"P{i}", 200.0) for i in range(players)], dealer_id=0)
        api.deal_hole_cards(["Ac", "Kd"])
        dealt = dict(boards)
        for street in ("preflop", "flop", "turn"):
            if street in dealt:
                api.deal_board(dealt[street], street=street)
            for pid, amount, raise_street in raises:
                if raise_street == street:
                    api._action_history.append((pid, Action(ActionType.RAISE, amount), street))
        before = getattr(api._bot.opponent_model.get(player), stat)
        for pid, action, amount, street in events:
            api.notify_action(ActionEvent(pid, action, amount, street))
        assert getattr(api._bot.opponent_model.get(player), stat) - before == added

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
    """Seat changes keep opponent models isolated by player_id."""

    def test_new_player_after_left_gets_fresh_opponent_model(self):
        """A new player at the same physical seat (different id) gets clean stats."""
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

        api.notify_player_joined(player_id=9, name="Veteran", stack=200.0)

        restored = api._bot.opponent_model.get(9)
        assert restored.fold_count == 0

    def test_rejoin_same_id_keeps_stats(self):
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

        # Same player rejoins at same id and name
        api.notify_player_joined(player_id=3, name="Player3", stack=200.0)

        # Stats should be restored (not zero)
        assert api._bot.opponent_model.get(3).raise_count == raise_count_before


class TestDecisionEngine:

    def test_cfr_without_flop_book_decision_engine_status(self, monkeypatch):
        monkeypatch.setenv("PF_CFR_FLOP_BOOK_ENABLED", "0")

        def unexpected_book(*args, **kwargs):
            pytest.fail("disabled flop book must not be constructed")

        monkeypatch.setattr("pokerfate.api.FlopBookDecisionEngine", unexpected_book)
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
        assert status["mode"] == "turn_river"
        assert status["enabled"] is True
        assert status["active"] is True
        assert status["realtime_cfr"] is True
        assert status["flop_book"] is False
        assert status["flop_book_requested"] is False

        # Changing the main engine must preserve the independent book switch.
        api.set_decision_engine("rule_engine")
        status = api.set_decision_engine("cfr")
        assert status["mode"] == "turn_river"
        assert status["realtime_cfr"] is True
        assert status["flop_book"] is False

    def test_cfr_decision_engine_status(self, monkeypatch):
        monkeypatch.delenv("PF_CFR_FLOP_BOOK_ENABLED", raising=False)
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
        assert status["realtime_cfr"] is True
        assert status["flop_book"] is True
        assert status["flop_book_requested"] is True

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
            decision_engine="cfr",
            cfr_flop_book_enabled=False,
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

    @pytest.mark.parametrize("engine", ["", "unknown-engine", "pokerfate"])
    def test_missing_or_unknown_decision_engine_runs_cfr(self, engine):
        def status_of(name):
            api = PokerFateAPI(
                my_player_id=0,
                big_blind=2.0,
                small_blind=1.0,
                autosave_path=None,
                decision_engine=name,
            )
            return api.decision_engine_status()

        status, cfr = status_of(engine), status_of("cfr")

        assert status.pop("requested") == (engine.replace("-", "_") or "cfr")
        assert cfr.pop("requested") == "cfr"
        assert status == cfr

    def test_new_hand_clears_realtime_cfr_error(self):
        api = PokerFateAPI(
            my_player_id=0,
            big_blind=2.0,
            small_blind=1.0,
            autosave_path=None,
            decision_engine="cfr",
            cfr_flop_book_enabled=False,
        )
        api._realtime_cfr_error = "solver_worker_error"
        api._external_decision_engine_error = "solver_worker_error"
        assert api.decision_engine_status()["error"] == "solver_worker_error"

        start_hand(api)

        assert api._realtime_cfr_error == ""
        assert api._external_decision_engine_error == ""
        assert api.decision_engine_status()["error"] == ""


def test_record_hero_execution_logs_the_server_amounts(monkeypatch):
    api = PokerFateAPI(my_player_id=0, big_blind=2.0, autosave_path=None)
    start_hand(api)
    events = []
    monkeypatch.setattr(api._log, "raw", events.append)
    api.record_hero_execution(action="raise", amount_added=90.0, total_bet_after=100.0, street="Flop")
    assert events == [{"event": "hero_execution", "hand": api._hand_number, "street": "flop",
                       "action": "raise", "amount_added": 90.0, "total_bet_after": 100.0}]


def test_session_config_event_is_logged(monkeypatch):
    monkeypatch.setenv("PF_V3_EV_VETO", "1")
    events = []
    api = PokerFateAPI(my_player_id=0, big_blind=2.0, autosave_path=None)
    # Re-emit through the public hook so the payload can be inspected.
    monkeypatch.setattr(api._log, "raw", lambda ev: events.append(ev))
    api._log_session_config()
    assert events and events[-1]["event"] == "session_config"
    assert events[-1]["env"].get("PF_V3_EV_VETO") == "1"
    assert "PF_V3_EV_VETO" in events[-1]["resolved"]
    assert "RAKE_RATE" in events[-1]["resolved"]


class TestSyncBoard:
    """sync_board takes the server's complete board and is idempotent."""

    @staticmethod
    def _board(api):
        return [str(c) for c in api._board]

    def test_streets_and_repeats_never_duplicate_cards(self):
        api = make_api()
        start_hand(api)
        api.sync_board(["Ks", "7d", "2c"], street="flop", pot=20)
        api.sync_board(["Ks", "7d", "2c"], street="flop", pot=20)  # repeated message
        api.sync_board(["Ks", "7d", "2c", "9h"], street="turn", pot=60)
        api.sync_board(["Ks", "7d", "2c", "9h"], street="turn", pot=60)
        api.sync_board(["Ks", "7d", "2c", "9h", "3c"], street="river", pot=120)
        assert self._board(api) == ["Ks", "7d", "2c", "9h", "3c"]

    def test_missed_street_is_filled_from_the_full_board(self):
        api = make_api()
        start_hand(api)
        api.sync_board(["Ks", "7d", "2c"], street="flop", pot=20)
        # the turn message never arrived; the river carries all five cards
        api.sync_board(["Ks", "7d", "2c", "9h", "3c"], street="river", pot=120)
        assert self._board(api) == ["Ks", "7d", "2c", "9h", "3c"]

    def test_unrelated_board_is_replaced_silently(self):
        api = make_api()
        start_hand(api)
        api.sync_board(["Ks", "7d", "2c"], street="flop", pot=20)
        api.sync_board(["As", "Ad", "5c", "6h"], street="turn", pot=60)
        assert self._board(api) == ["As", "Ad", "5c", "6h"]
