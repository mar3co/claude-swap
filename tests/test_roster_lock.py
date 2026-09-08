"""Roster mutators must take lock_file so a batched import cannot clobber them."""

from __future__ import annotations

from pathlib import Path

from openswap.switcher import ClaudeAccountSwitcher

from tests.conftest import patch_engine_filelock


class SpyLock:
    def __init__(self, path, timeout=10.0):
        self.path = path
        self.timeout = timeout

    def __enter__(self):
        entered.append(self.path)
        return self

    def __exit__(self, *exc):
        return False


entered: list[Path] = []


def _switcher_with_roster(temp_home: Path, sample_sequence_data: dict) -> ClaudeAccountSwitcher:
    switcher = ClaudeAccountSwitcher()
    switcher._setup_directories()
    switcher._write_json(switcher.sequence_file, sample_sequence_data)
    return switcher


class TestRosterWritersTakeAccountLock:
    def test_set_alias_holds_account_lock(
        self, temp_home: Path, sample_sequence_data: dict, monkeypatch
    ):
        entered.clear()
        patch_engine_filelock(monkeypatch, SpyLock)
        switcher = _switcher_with_roster(temp_home, sample_sequence_data)

        switcher.set_alias("1", "dev")

        assert entered == [switcher.lock_file]
        data = switcher._get_sequence_data()
        assert data["accounts"]["1"]["alias"] == "dev"

    def test_unset_alias_holds_account_lock(
        self, temp_home: Path, sample_sequence_data: dict, monkeypatch
    ):
        sample_sequence_data["accounts"]["1"]["alias"] = "dev"
        entered.clear()
        patch_engine_filelock(monkeypatch, SpyLock)
        switcher = _switcher_with_roster(temp_home, sample_sequence_data)

        switcher.unset_alias("1")

        assert entered == [switcher.lock_file]
        data = switcher._get_sequence_data()
        assert "alias" not in data["accounts"]["1"]

    def test_remove_account_holds_account_lock(
        self, temp_home: Path, sample_sequence_data: dict, monkeypatch
    ):
        entered.clear()
        patch_engine_filelock(monkeypatch, SpyLock)
        switcher = _switcher_with_roster(temp_home, sample_sequence_data)

        switcher.remove_account("2", assume_yes=True)

        assert entered == [switcher.lock_file]
        data = switcher._get_sequence_data()
        assert "2" not in data["accounts"]

    def test_set_account_disabled_holds_account_lock(
        self, temp_home: Path, sample_sequence_data: dict, monkeypatch
    ):
        entered.clear()
        patch_engine_filelock(monkeypatch, SpyLock)
        switcher = _switcher_with_roster(temp_home, sample_sequence_data)

        switcher.set_account_disabled("2", True)

        assert entered == [switcher.lock_file]
        data = switcher._get_sequence_data()
        assert data["accounts"]["2"]["disabled"] is True
