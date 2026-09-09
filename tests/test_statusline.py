"""Opt-in Claude Code status line: wrap the user's line, append the account name."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from openswap import statusline as sl
from openswap.exceptions import ConfigError
from openswap.models import Platform

_SRC_DIR = str(Path(__file__).resolve().parent.parent / "src")


def _backup_root(home: Path) -> Path:
    platform = Platform.detect()
    if platform in (Platform.LINUX, Platform.WSL):
        return home / ".local" / "share" / "openswap"
    if platform is Platform.MACOS:
        return home / "Library" / "Application Support" / "OpenSwap"
    return home / ".claude-swap-backup"


def _env(home: Path) -> dict[str, str]:
    env = {**os.environ, "HOME": str(home), "USERPROFILE": str(home)}
    env["PYTHONPATH"] = _SRC_DIR + os.pathsep + env.get("PYTHONPATH", "")
    env.pop("CLAUDE_CONFIG_DIR", None)
    env.pop("XDG_DATA_HOME", None)
    return env


class TestAppendLabel:
    def test_empty_output_is_just_the_name(self):
        assert sl.append_label("", "work") == "work"

    def test_appends_on_the_line_with_percentages(self):
        assert sl.append_label("Opus  5h 23%\n", "work") == "Opus  5h 23% · work\n"

    def test_picks_the_percentage_row_on_multiline(self):
        text = "Opus  ~/proj\n5h 23%  7d 41%\n"
        assert sl.append_label(text, "Ads Online") == (
            "Opus  ~/proj\n5h 23%  7d 41% · Ads Online\n"
        )

    def test_no_percent_appends_last_nonempty_line(self):
        assert sl.append_label("hello\n", "work") == "hello · work\n"

    def test_blank_label_leaves_text_alone(self):
        assert sl.append_label("5h 23%\n", "") == "5h 23%\n"

    def test_does_not_duplicate_an_existing_name(self):
        assert sl.append_label("5h 23% · work\n", "work") == "5h 23% · work\n"

    def test_path_suffix_is_not_already_labeled(self):
        assert sl.append_label("Opus  ~/work\n", "work") == "Opus  ~/work · work\n"


class TestAccountLabel:
    def test_alias_wins(self):
        assert sl.account_label("user@x.com", alias="work", org_name="Acme") == "work"

    def test_org_name_when_no_alias(self):
        assert sl.account_label("user@x.com", alias="", org_name="Acme Corp") == "Acme Corp"

    def test_personal_when_managed_without_org(self):
        assert sl.account_label("user@x.com", alias="", org_name="") == "personal"

    def test_unmanaged_uses_email_local_part(self):
        assert sl.account_label("user@x.com", alias="", org_name="", managed=False) == "user"


class TestCurrentAccountLabel:
    def test_matches_email_and_org(self, tmp_path: Path):
        config = tmp_path / ".claude.json"
        config.write_text(
            json.dumps(
                {
                    "oauthAccount": {
                        "emailAddress": "user@example.com",
                        "organizationUuid": "org-a",
                    }
                }
            ),
            encoding="utf-8",
        )
        sequence = tmp_path / "sequence.json"
        sequence.write_text(
            json.dumps(
                {
                    "accounts": {
                        "1": {
                            "email": "user@example.com",
                            "organizationUuid": "org-a",
                            "organizationName": "Ads Online",
                            "alias": "",
                        },
                        "2": {
                            "email": "user@example.com",
                            "organizationUuid": "org-b",
                            "organizationName": "personal",
                            "alias": "home",
                        },
                    }
                }
            ),
            encoding="utf-8",
        )
        assert sl.current_account_label(config, sequence) == "Ads Online"

    def test_alias_on_matching_slot(self, tmp_path: Path):
        config = tmp_path / ".claude.json"
        config.write_text(
            json.dumps(
                {
                    "oauthAccount": {
                        "emailAddress": "user@example.com",
                        "organizationUuid": "org-b",
                    }
                }
            ),
            encoding="utf-8",
        )
        sequence = tmp_path / "sequence.json"
        sequence.write_text(
            json.dumps(
                {
                    "accounts": {
                        "1": {
                            "email": "user@example.com",
                            "organizationUuid": "org-a",
                            "organizationName": "Ads Online",
                        },
                        "2": {
                            "email": "user@example.com",
                            "organizationUuid": "org-b",
                            "organizationName": "",
                            "alias": "home",
                        },
                    }
                }
            ),
            encoding="utf-8",
        )
        assert sl.current_account_label(config, sequence) == "home"

    def test_missing_files_are_empty(self, tmp_path: Path):
        assert sl.current_account_label(tmp_path / "nope.json", tmp_path / "seq.json") == ""


class TestInstallWrap:
    def test_install_with_no_statusline_creates_ours(self, tmp_path: Path):
        claude = tmp_path / ".claude"
        claude.mkdir()
        backup = tmp_path / "OpenSwap"
        backup.mkdir()
        result = sl.install(claude, backup, command="openswap statusline")
        settings = json.loads((claude / "settings.json").read_text(encoding="utf-8"))
        assert settings["statusLine"]["type"] == "command"
        assert settings["statusLine"]["command"] == "openswap statusline"
        assert result["created"] is True
        wrap = sl.load_wrap(backup)
        assert wrap["innerCommand"] is None
        assert wrap["created"] is True

    def test_install_wraps_existing_command(self, tmp_path: Path):
        claude = tmp_path / ".claude"
        claude.mkdir()
        (claude / "settings.json").write_text(
            json.dumps(
                {
                    "theme": "dark",
                    "statusLine": {
                        "type": "command",
                        "command": "~/.claude/statusline.sh",
                        "padding": 2,
                    },
                }
            ),
            encoding="utf-8",
        )
        backup = tmp_path / "OpenSwap"
        backup.mkdir()
        sl.install(claude, backup, command="openswap statusline")
        settings = json.loads((claude / "settings.json").read_text(encoding="utf-8"))
        assert settings["theme"] == "dark"
        assert settings["statusLine"]["command"] == "openswap statusline"
        assert settings["statusLine"]["padding"] == 2
        wrap = sl.load_wrap(backup)
        assert wrap["innerCommand"] == "~/.claude/statusline.sh"
        assert wrap["created"] is False

    def test_install_does_not_nest_our_command(self, tmp_path: Path):
        claude = tmp_path / ".claude"
        claude.mkdir()
        (claude / "settings.json").write_text(
            json.dumps(
                {
                    "statusLine": {
                        "type": "command",
                        "command": "openswap statusline",
                    }
                }
            ),
            encoding="utf-8",
        )
        backup = tmp_path / "OpenSwap"
        backup.mkdir()
        sl.save_wrap(backup, inner_command="~/old.sh", created=False)
        result = sl.install(claude, backup, command="openswap statusline")
        assert result["already"] is True
        wrap = sl.load_wrap(backup)
        assert wrap["innerCommand"] == "~/old.sh"

    def test_install_does_not_write_claude_json(self, tmp_path: Path):
        claude = tmp_path / ".claude"
        claude.mkdir()
        login = tmp_path / ".claude.json"
        login.write_text('{"oauthAccount":{"emailAddress":"keep@x.com"}}', encoding="utf-8")
        backup = tmp_path / "OpenSwap"
        backup.mkdir()
        sl.install(claude, backup, command="openswap statusline")
        assert json.loads(login.read_text(encoding="utf-8"))["oauthAccount"]["emailAddress"] == (
            "keep@x.com"
        )

    def test_uninstall_restores_inner(self, tmp_path: Path):
        claude = tmp_path / ".claude"
        claude.mkdir()
        backup = tmp_path / "OpenSwap"
        backup.mkdir()
        (claude / "settings.json").write_text(
            json.dumps(
                {
                    "statusLine": {
                        "type": "command",
                        "command": "jq -r .model.display_name",
                    }
                }
            ),
            encoding="utf-8",
        )
        sl.install(claude, backup, command="openswap statusline")
        sl.uninstall(claude, backup)
        settings = json.loads((claude / "settings.json").read_text(encoding="utf-8"))
        assert settings["statusLine"]["command"] == "jq -r .model.display_name"
        assert sl.load_wrap(backup)["innerCommand"] is None

    def test_uninstall_removes_statusline_we_created(self, tmp_path: Path):
        claude = tmp_path / ".claude"
        claude.mkdir()
        backup = tmp_path / "OpenSwap"
        backup.mkdir()
        sl.install(claude, backup, command="openswap statusline")
        sl.uninstall(claude, backup)
        settings = json.loads((claude / "settings.json").read_text(encoding="utf-8"))
        assert "statusLine" not in settings

    def test_install_refuses_torn_claude_settings(self, tmp_path: Path):
        claude = tmp_path / ".claude"
        claude.mkdir()
        torn = claude / "settings.json"
        torn.write_text("{not json", encoding="utf-8")
        backup = tmp_path / "OpenSwap"
        backup.mkdir()
        with pytest.raises(ConfigError, match="overwrite"):
            sl.install(claude, backup, command="openswap statusline")
        assert torn.read_text(encoding="utf-8") == "{not json"

    def test_install_refuses_torn_openswap_settings(self, tmp_path: Path):
        claude = tmp_path / ".claude"
        claude.mkdir()
        backup = tmp_path / "OpenSwap"
        backup.mkdir()
        (backup / "settings.json").write_text("{nope", encoding="utf-8")
        with pytest.raises(ConfigError, match="overwrite"):
            sl.install(claude, backup, command="openswap statusline")
        assert not (claude / "settings.json").exists()
        assert (backup / "settings.json").read_text(encoding="utf-8") == "{nope"

    def test_uninstall_refuses_torn_claude_settings(self, tmp_path: Path):
        claude = tmp_path / ".claude"
        claude.mkdir()
        backup = tmp_path / "OpenSwap"
        backup.mkdir()
        sl.install(claude, backup, command="openswap statusline")
        torn = claude / "settings.json"
        torn.write_text("{not json", encoding="utf-8")
        with pytest.raises(ConfigError, match="overwrite"):
            sl.uninstall(claude, backup)
        assert torn.read_text(encoding="utf-8") == "{not json"

    def test_install_writes_through_symlink(self, tmp_path: Path):
        repo = tmp_path / "dotfiles"
        repo.mkdir()
        tracked = repo / "claude-settings.json"
        tracked.write_text(json.dumps({"theme": "dark"}), encoding="utf-8")
        claude = tmp_path / ".claude"
        claude.mkdir()
        link = claude / "settings.json"
        link.symlink_to(tracked)
        backup = tmp_path / "OpenSwap"
        backup.mkdir()
        sl.install(claude, backup, command="openswap statusline")
        assert link.is_symlink(), "the dotfiles link must survive the write"
        data = json.loads(tracked.read_text(encoding="utf-8"))
        assert data["theme"] == "dark"
        assert data["statusLine"]["command"] == "openswap statusline"

    def test_save_wrap_refuses_torn_settings(self, tmp_path: Path):
        backup = tmp_path / "OpenSwap"
        backup.mkdir()
        torn = backup / "settings.json"
        torn.write_text("{nope", encoding="utf-8")
        with pytest.raises(ConfigError, match="overwrite"):
            sl.save_wrap(backup, inner_command="~/old.sh", created=False)
        assert torn.read_text(encoding="utf-8") == "{nope"

    def test_install_keeps_inner_if_claude_write_fails(self, tmp_path: Path, monkeypatch):
        claude = tmp_path / ".claude"
        claude.mkdir()
        (claude / "settings.json").write_text(
            json.dumps({"statusLine": {"type": "command", "command": "~/.claude/statusline.sh"}}),
            encoding="utf-8",
        )
        backup = tmp_path / "OpenSwap"
        backup.mkdir()

        def boom(*_a, **_k):
            raise OSError("disk full")

        monkeypatch.setattr(sl, "_write_json", boom)
        with pytest.raises(OSError, match="disk full"):
            sl.install(claude, backup, command="openswap statusline")
        wrap = sl.load_wrap(backup)
        assert wrap["innerCommand"] == "~/.claude/statusline.sh"
        settings = json.loads((claude / "settings.json").read_text(encoding="utf-8"))
        assert settings["statusLine"]["command"] == "~/.claude/statusline.sh"

    def test_install_migrates_legacy_backup_before_write(self, tmp_path: Path):
        from openswap.paths import LEGACY_BACKUP_DIRNAME

        backup = _backup_root(tmp_path)
        legacy = tmp_path / LEGACY_BACKUP_DIRNAME
        if backup.resolve() == legacy.resolve():
            pytest.skip("legacy and new backup roots coincide")
        legacy.mkdir()
        (legacy / "sequence.json").write_text(
            json.dumps({"accounts": {"1": {"email": "a@x.com", "organizationUuid": ""}}}),
            encoding="utf-8",
        )
        (tmp_path / ".claude").mkdir()
        result = subprocess.run(
            [sys.executable, "-m", "openswap", "statusline", "--install"],
            capture_output=True,
            text=True,
            env=_env(tmp_path),
        )
        assert result.returncode == 0, result.stderr
        assert not legacy.exists()
        assert (backup / "sequence.json").exists()
        wrap = sl.load_wrap(backup)
        assert wrap["created"] is True


class TestPaint:
    def test_wraps_inner_stdout_and_appends_name(self, tmp_path: Path):
        config = tmp_path / ".claude.json"
        config.write_text(
            json.dumps(
                {
                    "oauthAccount": {
                        "emailAddress": "user@example.com",
                        "organizationUuid": "org-a",
                    }
                }
            ),
            encoding="utf-8",
        )
        sequence = tmp_path / "sequence.json"
        sequence.write_text(
            json.dumps(
                {
                    "accounts": {
                        "1": {
                            "email": "user@example.com",
                            "organizationUuid": "org-a",
                            "organizationName": "Ads Online",
                            "alias": "work",
                        }
                    }
                }
            ),
            encoding="utf-8",
        )
        script = tmp_path / "inner.py"
        script.write_text(
            "import sys; sys.stdout.write('5h 23%  7d 41%\\n')\n",
            encoding="utf-8",
        )
        inner = subprocess.list2cmdline([sys.executable, str(script)])
        out = sl.paint(
            "{}",
            inner_command=inner,
            config_path=config,
            sequence_path=sequence,
        )
        assert out == "5h 23%  7d 41% · work\n"

    def test_no_inner_prints_just_the_name(self, tmp_path: Path):
        config = tmp_path / ".claude.json"
        config.write_text(
            json.dumps({"oauthAccount": {"emailAddress": "user@example.com"}}),
            encoding="utf-8",
        )
        sequence = tmp_path / "sequence.json"
        sequence.write_text(
            json.dumps(
                {
                    "accounts": {
                        "1": {
                            "email": "user@example.com",
                            "organizationUuid": "",
                            "alias": "home",
                        }
                    }
                }
            ),
            encoding="utf-8",
        )
        assert sl.paint("{}", inner_command=None, config_path=config, sequence_path=sequence) == (
            "home\n"
        )


class TestCLI:
    def test_help_lists_statusline(self, tmp_path: Path):
        result = subprocess.run(
            [sys.executable, "-m", "openswap", "--help"],
            capture_output=True,
            text=True,
            env=_env(tmp_path),
        )
        assert result.returncode == 0
        assert "statusline" in result.stdout

    def test_statusline_help(self, tmp_path: Path):
        result = subprocess.run(
            [sys.executable, "-m", "openswap", "statusline", "--help"],
            capture_output=True,
            text=True,
            env=_env(tmp_path),
        )
        assert result.returncode == 0
        assert "--install" in result.stdout
        assert "--uninstall" in result.stdout

    def test_paint_via_cli(self, tmp_path: Path):
        (tmp_path / ".claude.json").write_text(
            json.dumps(
                {
                    "oauthAccount": {
                        "emailAddress": "user@example.com",
                        "organizationUuid": "",
                    }
                }
            ),
            encoding="utf-8",
        )
        backup = _backup_root(tmp_path)
        backup.mkdir(parents=True)
        (backup / "sequence.json").write_text(
            json.dumps(
                {
                    "accounts": {
                        "1": {
                            "email": "user@example.com",
                            "organizationUuid": "",
                            "alias": "home",
                        }
                    }
                }
            ),
            encoding="utf-8",
        )
        result = subprocess.run(
            [sys.executable, "-m", "openswap", "statusline"],
            input="{}",
            capture_output=True,
            text=True,
            env=_env(tmp_path),
        )
        assert result.returncode == 0
        assert result.stdout == "home\n"
