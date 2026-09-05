"""Tests for the scheduled 5-hour-window kickoff helpers."""

from __future__ import annotations

import inspect
import subprocess
from datetime import datetime
from pathlib import Path

import pytest

from claude_swap.exceptions import SessionError
from claude_swap.kickoff import (
    KICKOFF_PROMPT,
    build_kickoff_argv,
    build_kickoff_env,
    format_kickoff_time,
    invoke_kickoff,
    kickoff_account_eligible,
    kickoff_is_due,
    parse_kickoff_time,
)
from claude_swap.session import AUTH_OVERRIDE_ENV_VARS


# --- due-once-per-local-day ----------------------------------------------------

def test_kickoff_due_at_or_after_scheduled_time_if_not_yet_run_today():
    now = datetime(2026, 9, 5, 7, 0, 0)
    assert kickoff_is_due(True, 7, 0, last_date="", now=now)
    later = datetime(2026, 9, 5, 8, 15, 0)
    assert kickoff_is_due(True, 7, 0, last_date="", now=later)


def test_kickoff_does_not_fire_twice_the_same_local_day():
    now = datetime(2026, 9, 5, 9, 0, 0)
    assert not kickoff_is_due(True, 7, 0, last_date="2026-09-05", now=now)


def test_kickoff_does_not_fire_on_first_enable_before_scheduled_time():
    early = datetime(2026, 9, 5, 6, 59, 0)
    assert not kickoff_is_due(True, 7, 0, last_date="", now=early)


def test_kickoff_fires_next_day_after_a_recorded_run():
    nxt = datetime(2026, 9, 6, 7, 0, 0)
    assert kickoff_is_due(True, 7, 0, last_date="2026-09-05", now=nxt)


def test_kickoff_disabled_never_due():
    now = datetime(2026, 9, 5, 7, 0, 0)
    assert not kickoff_is_due(False, 7, 0, last_date="", now=now)


def test_kickoff_custom_minute_is_respected():
    before = datetime(2026, 9, 5, 7, 29, 0)
    at = datetime(2026, 9, 5, 7, 30, 0)
    assert not kickoff_is_due(True, 7, 30, last_date="", now=before)
    assert kickoff_is_due(True, 7, 30, last_date="", now=at)


# --- eligibility ---------------------------------------------------------------

def test_eligibility_skips_api_key_and_open_five_hour_includes_idle_oauth():
    assert not kickoff_account_eligible(is_api_key=True, five_hour_pct=0.0)
    assert not kickoff_account_eligible(is_api_key=True, five_hour_pct=None)
    assert not kickoff_account_eligible(is_api_key=False, five_hour_pct=12.0)
    assert not kickoff_account_eligible(is_api_key=False, five_hour_pct=0.1)
    assert kickoff_account_eligible(is_api_key=False, five_hour_pct=0.0)
    assert kickoff_account_eligible(is_api_key=False, five_hour_pct=None)


# --- invoke path ---------------------------------------------------------------

def test_invoke_kickoff_print_argv_session_dir_and_returning_subprocess(tmp_path: Path):
    session_dir = tmp_path / "sessions" / "1-a_x.com"
    session_dir.mkdir(parents=True)
    captured: dict = {}

    def fake_which(name: str):
        return "/opt/fake/claude" if name == "claude" else None

    def fake_run(argv, **kwargs):
        captured["argv"] = list(argv)
        captured["kwargs"] = kwargs
        return subprocess.CompletedProcess(argv, 0, stdout="ok", stderr="")

    result = invoke_kickoff(
        session_dir,
        which=fake_which,
        run=fake_run,
        environ={"PATH": "/usr/bin", "ANTHROPIC_API_KEY": "sk-test"},
    )

    argv = captured["argv"]
    assert argv[0] == "/opt/fake/claude"
    assert "-p" in argv or "--print" in argv
    assert KICKOFF_PROMPT in argv
    env = captured["kwargs"]["env"]
    assert env["CLAUDE_CONFIG_DIR"] == str(session_dir)
    assert "ANTHROPIC_API_KEY" not in env
    for var in AUTH_OVERRIDE_ENV_VARS:
        assert var not in env
    assert captured["kwargs"].get("check") is False
    assert result.returncode == 0
    assert result.stdout == "ok"


def test_invoke_kickoff_source_uses_subprocess_not_exec():
    src = inspect.getsource(invoke_kickoff)
    assert "os.execvpe(" not in src
    assert "os.execvp(" not in src
    assert "os.exec(" not in src
    assert "run_fn(" in src


def test_invoke_kickoff_missing_claude_raises(tmp_path: Path):
    with pytest.raises(SessionError, match="claude"):
        invoke_kickoff(tmp_path, which=lambda _name: None, run=lambda *_a, **_k: None)


def test_build_kickoff_argv_is_print_mode():
    argv = build_kickoff_argv("/usr/bin/claude")
    assert argv[0] == "/usr/bin/claude"
    assert "-p" in argv or "--print" in argv
    assert KICKOFF_PROMPT in argv


def test_build_kickoff_env_sets_config_dir_and_scrubs_auth_overrides():
    env = build_kickoff_env(
        "/tmp/session-1",
        environ={
            "PATH": "/usr/bin",
            "ANTHROPIC_API_KEY": "sk-secret",
            "HOME": "/Users/demo",
        },
    )
    assert env["CLAUDE_CONFIG_DIR"] == "/tmp/session-1"
    assert "ANTHROPIC_API_KEY" not in env
    assert env["PATH"] == "/usr/bin"


def test_parse_and_format_kickoff_time():
    assert parse_kickoff_time("7:00") == (7, 0)
    assert parse_kickoff_time("7:30 AM") == (7, 30)
    assert parse_kickoff_time("7 PM") == (19, 0)
    assert parse_kickoff_time("12:00 AM") == (0, 0)
    assert parse_kickoff_time("12:15 PM") == (12, 15)
    assert parse_kickoff_time("nope") is None
    assert format_kickoff_time(7, 0) == "7:00 AM"
    assert format_kickoff_time(19, 30) == "7:30 PM"
