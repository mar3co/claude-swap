"""Install helpers for the macOS widget companion (no xcodebuild)."""

from __future__ import annotations

from pathlib import Path

import pytest

from openswap import widget_install as wi
from openswap.exceptions import ClaudeSwitchError


def test_detect_development_team_prefers_env(monkeypatch):
    monkeypatch.setenv("DEVELOPMENT_TEAM", "ABCDE12345")
    assert wi.detect_development_team() == "ABCDE12345"


def test_team_from_codesign_output():
    blob = "Identifier=com.opensoft.openswap.widget\nTeamIdentifier=KJ999FVUJ4\nSigned Time=now\n"
    assert wi._team_from_codesign_output(blob) == "KJ999FVUJ4"
    assert wi._team_from_codesign_output("TeamIdentifier=not set\n") is None
    assert wi._team_from_codesign_output("") is None


def test_build_host_plist_points_at_the_binary(tmp_path: Path):
    app = tmp_path / "OpenSwap.app"
    binary = app / "Contents" / "MacOS" / "OpenSwap"
    binary.parent.mkdir(parents=True)
    binary.write_text("", encoding="utf-8")
    data = wi.build_host_plist(app, home=tmp_path)
    import plistlib

    plist = plistlib.loads(data)
    assert plist["Label"] == "com.opensoft.openswap.widget"
    assert plist["ProgramArguments"] == [str(binary)]
    assert plist["RunAtLoad"] is True


def test_project_dir_finds_checkout_sources():
    expected = Path(__file__).resolve().parent.parent / "macos" / "OpenSwapWidget"
    found = wi.project_dir()
    assert found == expected
    assert (found / "OpenSwapWidget.xcodeproj").is_dir()


def test_require_macos_refuses_other_platforms(monkeypatch):
    monkeypatch.setattr(wi.sys, "platform", "linux")
    with pytest.raises(ClaudeSwitchError, match="macOS"):
        wi._require_macos()


def test_widget_app_path_is_under_home_applications(tmp_path: Path):
    from openswap.widget_snapshot import widget_app_path

    assert widget_app_path(tmp_path) == tmp_path / "Applications" / "OpenSwap.app"
