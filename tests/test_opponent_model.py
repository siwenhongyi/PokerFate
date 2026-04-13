"""Tests for OpponentModel persistence and name-based ID migration."""

import json
import os
import tempfile

import pytest

from pokerfate.bot.opponent_model import OpponentModel, OpponentStats


class TestPlayerTypePriority:
    """player_type() uses VPIP/PFR/gap/AF/WTSD/flop AFq; see opponent_model module docstring."""

    def _stats(self, hands, vpip_c, pfr_c, bet, ra, ca, ch):
        s = OpponentStats()
        s.hands_seen = hands
        s.vpip_count = vpip_c
        s.pfr_count = pfr_c
        s.bet_count = bet
        s.raise_count = ra
        s.call_count = ca
        s.check_count = ch
        return s

    def test_loose_passive_low_pfr_is_fish_not_calling_station(self):
        s = self._stats(50, 22, 6, 5, 5, 80, 40)  # VPIP 44%, PFR 12%, AF low
        assert s.player_type() == "fish"

    def test_maniac_before_loose_passive_buckets(self):
        s = self._stats(50, 25, 10, 40, 40, 10, 10)  # ~50% VPIP, AF > 2.5
        assert s.player_type() == "maniac"

    def test_whale_super_loose_passive_before_fish(self):
        s = self._stats(50, 35, 3, 2, 2, 100, 50)  # ~70% VPIP, ~6% PFR, AF < 1.2
        assert s.player_type() == "whale"

    def test_reg_excludes_large_vpip_pfr_gap(self):
        s = self._stats(40, 12, 3, 2, 2, 20, 15)  # 30% VPIP, 7.5% PFR → gap too large for reg
        assert s.player_type() != "reg"

    def test_calling_station_moderate_pfr(self):
        s = self._stats(50, 22, 11, 5, 5, 60, 30)  # 44% VPIP, 22% PFR, AF low
        assert s.player_type() == "calling_station"


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


class TestSeatReuse:
    """Tests for seat-reuse detection and name_archive pattern."""

    def test_unregister_seat_archives_stats(self):
        """unregister_seat moves stats to name_archive, clears active mappings."""
        model = OpponentModel()
        model.register_name(1, "Alice")
        model.get(1).hands_seen = 42
        model.unregister_seat(1)

        # Active mappings cleared
        assert 1 not in model._id_to_name
        assert "Alice" not in model._name_to_id
        assert 1 not in model._stats
        # Stats preserved in archive
        assert "Alice" in model._name_archive
        assert model._name_archive["Alice"].hands_seen == 42

    def test_new_player_at_vacated_seat_starts_fresh(self):
        """After unregister_seat, a different player at same ID gets clean stats."""
        model = OpponentModel()
        model.register_name(1, "OldPlayer")
        model.get(1).hands_seen = 99
        model.unregister_seat(1)

        # New player sits in the same seat/ID
        model.register_name(1, "NewPlayer")
        assert model.get(1).hands_seen == 0  # fresh start

    def test_returning_player_after_unregister_restores_stats(self):
        """Player who left and rejoins (same or different ID) gets their stats back."""
        model = OpponentModel()
        model.register_name(1, "Alice")
        model.get(1).hands_seen = 50
        model.get(1).fold_count = 20
        model.unregister_seat(1)

        # Alice rejoins at a different seat ID
        model.register_name(3, "Alice")
        assert model.get(3).hands_seen == 50
        assert model.get(3).fold_count == 20
        # Archive should be cleared (stats restored to active)
        assert "Alice" not in model._name_archive

    def test_seat_reuse_without_explicit_unregister(self):
        """register_name with a new name at existing ID detects seat reuse inline."""
        model = OpponentModel()
        model.register_name(2, "OldPlayer")
        model.get(2).hands_seen = 77

        # Same seat (ID=2) now has a different player — no explicit unregister called
        model.register_name(2, "NewPlayer")
        assert model.get(2).hands_seen == 0  # NewPlayer starts fresh

        # OldPlayer's stats should be archived, not lost
        assert "OldPlayer" in model._name_archive
        assert model._name_archive["OldPlayer"].hands_seen == 77

    def test_archive_persisted_in_save_load(self):
        """name_archive survives save/load roundtrip."""
        model = OpponentModel()
        model.register_name(1, "ArchiveMe")
        model.get(1).hands_seen = 35
        model.unregister_seat(1)

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name
        try:
            model.save(path)
            loaded = OpponentModel.load(path)
            assert "ArchiveMe" in loaded._name_archive
            assert loaded._name_archive["ArchiveMe"].hands_seen == 35
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
