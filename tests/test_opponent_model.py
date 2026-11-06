"""Tests for OpponentModel persistence and uid-based archive migration."""

import json
import os
import tempfile

import pytest

from pokerfate.bot.opponent_model import OpponentModel, OpponentStats


class TestBluffWinClassification:
    def test_board_relative_bluff_win_rules(self):
        model = OpponentModel()
        cases = [
            (1, 1, True),    # board high card, winner high card
            (1, 2, False),   # board high card, winner made a pair
            (2, 2, True),    # board pair, winner one pair
            (2, 3, False),   # board pair, winner improved to two pair
            (3, 3, True),    # board two pair, winner two pair
            (4, 4, True),    # board trips, winner trips
            (3, 5, False),   # winner straight is not counted as bluff
            (7, 7, False),   # board/winner full house is not counted as bluff
        ]

        for idx, (board_type, winner_type, is_bluff) in enumerate(cases, start=1):
            model.record_win_with_hand_type(
                idx,
                winner_type,
                had_aggression=True,
                board_hand_type=board_type,
            )
            stats = model.get(idx)
            assert stats.bet_win_count == 1
            assert stats.bluff_win_count == int(is_bluff)

    def test_missing_board_type_keeps_legacy_fallback(self):
        model = OpponentModel()

        model.record_win_with_hand_type(1, 2, had_aggression=True)

        stats = model.get(1)
        assert stats.bet_win_count == 1
        assert stats.bluff_win_count == 1


class TestPersistence:
    def test_save_and_load_roundtrip(self):
        model = OpponentModel()
        model.register_name(1, "GPT")
        s = model.get(1)
        s.hands_seen = 50
        s.vpip_count = 20
        s.pfr_count = 15
        s.fold_to_cbet_count = 10
        s.fold_to_cbet_opps = 15

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name
        try:
            model.save(path)
            loaded = OpponentModel.load(path)
            ls = loaded.get(1)
            assert ls.hands_seen == 50
            assert ls.vpip_count == 20
            assert ls.fold_to_cbet_opps == 15
            assert loaded._id_to_name[1] == "GPT"
        finally:
            os.unlink(path)

    def test_load_nonexistent_file_is_empty(self):
        model = OpponentModel.load("/tmp/__nonexistent_pokerfate__.json")
        assert model._stats == {}

    def test_save_creates_valid_json(self):
        model = OpponentModel()
        model.register_name(42, "TestBot")
        model.get(42).hands_seen = 10

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
            path = f.name
        try:
            model.save(path)
            with open(path) as f:
                data = json.load(f)
            assert "42" in data["players"]
            assert data["players"]["42"]["name"] == "TestBot"
            assert data["players"]["42"]["stats"]["hands_seen"] == 10
        finally:
            os.unlink(path)


class TestNameMigration:
    def test_same_uid_name_change_keeps_stats(self):
        model = OpponentModel()
        model.register_name(1, "OldName")
        model.get(1).hands_seen = 100
        model.get(1).fold_count = 30

        model.register_name(1, "NewName")

        assert model.get(1).hands_seen == 100
        assert model.get(1).fold_count == 30
        assert model._id_to_name[1] == "NewName"

    def test_same_name_different_uid_does_not_migrate_stats(self):
        model = OpponentModel()
        model.register_name(1, "Villain")
        model.get(1).hands_seen = 100
        model.get(1).fold_count = 30

        model.register_name(5, "Villain")

        assert model.get(5).hands_seen == 0
        assert model.get(1).hands_seen == 100

    def test_different_names_dont_interfere(self):
        model = OpponentModel()
        model.register_name(1, "Alice")
        model.register_name(2, "Bob")
        model.get(1).hands_seen = 50
        model.get(2).hands_seen = 75

        model.register_name(3, "Alice")
        assert model.get(3).hands_seen == 0
        assert model.get(1).hands_seen == 50
        assert model.get(2).hands_seen == 75

    def test_new_name_no_migration(self):
        model = OpponentModel()
        model.register_name(1, "OldBot")
        model.get(1).hands_seen = 30

        model.register_name(2, "NewBot")
        assert model.get(2).hands_seen == 0


class TestMerge:
    def test_merge_adds_stats(self):
        m1 = OpponentModel()
        m1.get(1).hands_seen = 50
        m1.get(1).vpip_count = 20

        m2 = OpponentModel()
        m2.get(1).hands_seen = 30
        m2.get(1).vpip_count = 10

        m1.merge(m2)
        assert m1.get(1).hands_seen == 80
        assert m1.get(1).vpip_count == 30

    def test_merge_new_player(self):
        m1 = OpponentModel()
        m1.get(1).hands_seen = 20

        m2 = OpponentModel()
        m2.get(2).hands_seen = 40

        m1.merge(m2)
        assert m1.get(2).hands_seen == 40


class TestSummary:
    def test_empty_summary(self):
        model = OpponentModel()
        assert "No opponent" in model.summary()

    def test_summary_with_data(self):
        model = OpponentModel()
        model.register_name(1, "GPT")
        model.get(1).hands_seen = 100
        model.get(1).vpip_count = 30
        summary = model.summary()
        assert "GPT" in summary
        assert "hands=100" in summary


class TestSeatReuse:
    """Tests for pure uid archive and legacy name_archive migration."""

    def test_unregister_seat_is_noop_for_uid_model(self):
        model = OpponentModel()
        model.register_name(1, "Alice")
        model.get(1).hands_seen = 42
        model.unregister_seat(1)

        assert model.get(1).hands_seen == 42
        assert model._id_to_name[1] == "Alice"

    def test_same_uid_name_change_keeps_stats(self):
        model = OpponentModel()
        model.register_name(1, "OldPlayer")
        model.get(1).hands_seen = 99

        model.register_name(1, "NewPlayer")
        assert model.get(1).hands_seen == 99
        assert model._id_to_name[1] == "NewPlayer"

    def test_same_name_different_uid_after_unregister_starts_fresh(self):
        model = OpponentModel()
        model.register_name(1, "Alice")
        model.get(1).hands_seen = 50
        model.get(1).fold_count = 20
        model.unregister_seat(1)

        model.register_name(3, "Alice")
        assert model.get(3).hands_seen == 0
        assert model.get(1).hands_seen == 50

    def test_same_uid_without_explicit_unregister_keeps_stats(self):
        model = OpponentModel()
        model.register_name(2, "OldPlayer")
        model.get(2).hands_seen = 77

        model.register_name(2, "NewPlayer")
        assert model.get(2).hands_seen == 77
        assert model._id_to_name[2] == "NewPlayer"
        assert "OldPlayer" not in model._name_archive

    def test_archive_persisted_in_save_load(self):
        """uid archive survives save/load roundtrip."""
        model = OpponentModel()
        model.register_name(1, "ArchiveMe")
        model.get(1).hands_seen = 35

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name
        try:
            model.save(path)
            loaded = OpponentModel.load(path)
            assert loaded.get(1).hands_seen == 35
            assert loaded._id_to_name[1] == "ArchiveMe"
            assert "ArchiveMe" not in loaded._name_archive
        finally:
            os.unlink(path)

    def test_legacy_name_archive_lazy_migrates_to_uid_archive(self):
        data = {
            "stats": {},
            "id_to_name": {},
            "name_to_id": {},
            "name_archive": {"LegacyName": {"hands_seen": 35, "fold_count": 9}},
        }
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
            json.dump(data, f)
            path = f.name
        try:
            model = OpponentModel.load(path)
            model.register_name(7, "LegacyName")

            assert model.get(7).hands_seen == 35
            assert model.get(7).fold_count == 9
            assert "LegacyName" not in model._name_archive
            with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as out:
                out_path = out.name
            try:
                model.save(out_path)
                saved = json.load(open(out_path))
                assert "7" in saved["players"]
                assert "LegacyName" not in saved["name_archive"]
            finally:
                os.unlink(out_path)
        finally:
            os.unlink(path)

    def test_legacy_active_seat_stats_lazy_migrate_by_name_not_seat_key(self):
        data = {
            "stats": {"2": {"hands_seen": 35, "fold_count": 9}},
            "id_to_name": {"2": "LegacySeatName"},
            "name_to_id": {"LegacySeatName": 2},
            "name_archive": {},
        }
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
            json.dump(data, f)
            path = f.name
        try:
            model = OpponentModel.load(path)

            assert 2 not in model._stats
            assert model._name_archive["LegacySeatName"].hands_seen == 35

            model.register_name(1001, "LegacySeatName")

            assert model.get(1001).hands_seen == 35
            assert model.get(1001).fold_count == 9
            assert "LegacySeatName" not in model._name_archive

            with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as out:
                out_path = out.name
            try:
                model.save(out_path)
                saved = json.load(open(out_path))
                assert "1001" in saved["players"]
                assert "2" not in saved["players"]
            finally:
                os.unlink(out_path)
        finally:
            os.unlink(path)

    def test_unregister_unknown_id_is_noop(self):
        """unregister_seat on an unknown player_id must not raise."""
        model = OpponentModel()
        model.unregister_seat(999)  # Should not raise

    def test_same_player_same_id_reregistration_is_stable(self):
        """register_name called twice with same id+name is idempotent."""
        model = OpponentModel()
        model.register_name(5, "Stable")
        model.get(5).hands_seen = 10
        model.register_name(5, "Stable")  # same id, same name
        assert model.get(5).hands_seen == 10  # stats intact


class TestSparseSampleNoFakeAggression:
    """10-19 手稀疏样本（只观察到 preflop fold，零主动行为）不应产生
    伪激进 bluff_ag_scale。见 review-2026-04-22.md E.2。
    """

    def test_only_preflop_folds_returns_baseline(self):
        model = OpponentModel()
        s = model.get(1)
        s.hands_seen = 15
        s.fold_count = 15        # 只 fold 过 preflop，零主动行为
        # AF = (0+0)/max(0+0,1) = 0
        assert s.aggression_factor == 0.0
        adj = model.exploit_adjustments(1)
        # baseline 0.55，不是旧代码算出的 0.85（伪激进）
        assert adj.get('bluff_ag_scale', 0.55) == pytest.approx(0.55, abs=1e-6)
        assert adj.get('value_ag_scale', 0.85) == pytest.approx(0.85, abs=1e-6)

    def test_enough_action_samples_enables_af_fallback(self):
        """action_samples ≥ 10 时 AF 兜底可以启用。"""
        model = OpponentModel()
        s = model.get(1)
        s.hands_seen = 15
        s.call_count = 10        # 有 10 次 postflop call，AF=0 但样本够
        adj = model.exploit_adjustments(1)
        # 此时 af=0（低），AF 兜底启用，但低 AF 代表 check/call 多，
        # 不能反向当成"更好诈唬"。没有 fold_to_cbet 证据时应低于 baseline。
        assert adj.get('bluff_ag_scale', 0.55) < 0.40


class TestOpponentStatsToVillainStats:
    """OpponentStats.to_villain_stats() 应把所有字段原样映射。"""

    def test_river_fold_rate_uses_facing_bet_opportunities(self):
        s = OpponentStats()
        s.river_action_count = 10
        s.river_fold_count = 4
        assert s.river_fold_rate == 0.0
        s.river_facing_bet_opps = 5
        s.river_facing_bet_fold_count = 2
        assert s.river_fold_rate == pytest.approx(0.4)

    def test_full_field_projection(self):
        s = OpponentStats()
        s.hands_seen = 50
        s.vpip_count = 20
        s.pfr_count = 10
        s.fold_to_cbet_count = 5
        s.fold_to_cbet_opps = 10
        s.bet_count = 8
        s.raise_count = 5
        s.call_count = 15
        s.check_count = 12
        s.bet_win_count = 6
        s.bluff_win_count = 3        # bluff_win_rate = 0.5
        s.river_action_count = 10
        s.river_fold_count = 4
        s.river_facing_bet_opps = 10
        s.river_facing_bet_fold_count = 4       # river_fold_rate = 0.4
        s.flop_bet_count = 6
        s.flop_passive_count = 4     # flop_afq = 0.6
        s.turn_bet_count = 3
        s.turn_passive_count = 5     # turn_afq = 0.375
        s.river_bet_count = 2
        s.river_check_count = 3      # river_afq 分母 total=10
        s.flop_seen_count = 20
        s.showdown_count = 10
        s.showdown_win_count = 6     # wmsd = 0.6
        vs = s.to_villain_stats()
        assert vs.hands_seen == 50
        assert vs.fold_to_cbet_opps == 10
        assert vs.bet_win_count == 6
        assert vs.river_action_count == 10
        assert vs.bluff_win_rate == pytest.approx(0.5)
        assert vs.wmsd == pytest.approx(0.6)
        assert vs.flop_afq == pytest.approx(0.6)
        assert vs.river_fold_rate == pytest.approx(0.4)
        # VillainStats 不含 player_type 字段；对手建模不再输出离散标签。
        assert not hasattr(vs, 'player_type')

    def test_opponent_stats_no_discrete_player_type_label(self):
        assert not hasattr(OpponentStats(), 'player_type')
