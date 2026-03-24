"""Tests for OpponentModel persistence and name-based ID migration."""

import json
import os
import tempfile
import pytest
from pokerfate.bot.opponent_model import OpponentModel, OpponentStats


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
            assert "42" in data["stats"]
            assert data["stats"]["42"]["hands_seen"] == 10
        finally:
            os.unlink(path)


class TestNameMigration:
    def test_same_name_different_id_migrates_stats(self):
        model = OpponentModel()
        # First encounter: id=1, name="Villain"
        model.register_name(1, "Villain")
        model.get(1).hands_seen = 100
        model.get(1).fold_count = 30

        # Reconnects with id=5
        model.register_name(5, "Villain")
        # Stats should be on id=5 now
        assert model.get(5).hands_seen == 100
        assert model.get(5).fold_count == 30
        # id=1 should be gone
        assert 1 not in model._stats

    def test_different_names_dont_interfere(self):
        model = OpponentModel()
        model.register_name(1, "Alice")
        model.register_name(2, "Bob")
        model.get(1).hands_seen = 50
        model.get(2).hands_seen = 75

        model.register_name(3, "Alice")  # Alice reconnects as id=3
        assert model.get(3).hands_seen == 50  # Alice's stats migrated
        assert model.get(2).hands_seen == 75  # Bob untouched

    def test_new_name_no_migration(self):
        model = OpponentModel()
        model.register_name(1, "OldBot")
        model.get(1).hands_seen = 30

        model.register_name(2, "NewBot")  # completely new name
        assert model.get(2).hands_seen == 0  # fresh stats


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
