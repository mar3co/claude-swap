"""Scheduled headless ping that starts an idle 5-hour usage window.

The menu bar (or any other host) decides *when* to fire; this module is the
pure due/eligibility policy plus a returning ``claude -p`` invoke. It never
replaces the current process (no POSIX ``exec``) and never writes the default
``~/.claude`` login: each ping runs under that account's session profile via
``CLAUDE_CONFIG_DIR``.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from collections.abc import Callable, Mapping
from datetime import datetime
from pathlib import Path

from claude_swap.exceptions import SessionError
from claude_swap.session import AUTH_OVERRIDE_ENV_VARS

KICKOFF_PROMPT = "ok"
KICKOFF_TIMEOUT_S = 90.0


def kickoff_is_due(
    enabled: bool,
    hour: int,
    minute: int,
    last_date: str,
    now: datetime,
) -> bool:
    """True when a local-time kickoff should run (at most once per local day).

    Does not fire before the scheduled time on a given day, even on first
    enable. Fires at or after that time if today has not been recorded yet.
    """
    if not enabled:
        return False
    try:
        hour_i = int(hour)
        minute_i = int(minute)
    except (TypeError, ValueError):
        return False
    if not (0 <= hour_i <= 23 and 0 <= minute_i <= 59):
        return False
    today = now.date().isoformat()
    if last_date == today:
        return False
    scheduled = now.replace(hour=hour_i, minute=minute_i, second=0, microsecond=0)
    return now >= scheduled


def kickoff_account_eligible(*, is_api_key: bool, five_hour_pct: float | None) -> bool:
    """Idle OAuth accounts only: skip API keys and already-open 5h windows."""
    if is_api_key:
        return False
    if five_hour_pct is not None and five_hour_pct > 0:
        return False
    return True


def format_kickoff_time(hour: int, minute: int = 0) -> str:
    """Local-clock label like ``7:00 AM``."""
    h24 = int(hour) % 24
    m = max(0, min(int(minute), 59))
    suffix = "AM" if h24 < 12 else "PM"
    h12 = h24 % 12 or 12
    return f"{h12}:{m:02d} {suffix}"


def parse_kickoff_time(text: str) -> tuple[int, int] | None:
    """Parse ``7:30``, ``07:30``, ``7:30 AM``, or ``7 AM`` into ``(hour, minute)``."""
    raw = (text or "").strip().lower()
    if not raw:
        return None
    ampm = None
    if raw.endswith("am") or raw.endswith("pm"):
        ampm = raw[-2:]
        raw = raw[:-2].strip()
    if not raw:
        return None
    if ":" in raw:
        left, _, right = raw.partition(":")
        if not left.isdigit() or not right.isdigit():
            return None
        hour = int(left)
        minute = int(right)
    elif raw.isdigit():
        hour = int(raw)
        minute = 0
    else:
        return None
    if minute > 59:
        return None
    if ampm is not None:
        if hour < 1 or hour > 12:
            return None
        if ampm == "am":
            hour = 0 if hour == 12 else hour
        else:
            hour = hour if hour == 12 else hour + 12
    elif hour > 23:
        return None
    return hour, minute


def build_kickoff_argv(claude_bin: str) -> list[str]:
    """``claude -p`` plus the trivial prompt that opens a 5h window."""
    return [claude_bin, "-p", KICKOFF_PROMPT]


def build_kickoff_env(
    session_dir: Path | str,
    environ: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Env for a session-profile ping: isolated config dir, no auth overrides."""
    src = os.environ if environ is None else environ
    env = {k: v for k, v in src.items() if k not in AUTH_OVERRIDE_ENV_VARS}
    env["CLAUDE_CONFIG_DIR"] = str(session_dir)
    return env


def invoke_kickoff(
    session_dir: Path | str,
    *,
    which: Callable[[str], str | None] | None = None,
    run: Callable[..., subprocess.CompletedProcess] | None = None,
    timeout: float = KICKOFF_TIMEOUT_S,
    environ: Mapping[str, str] | None = None,
) -> subprocess.CompletedProcess:
    """Headless print-mode ping against one session profile.

    Uses a returning ``subprocess.run`` (or the injected ``run``). Never calls
    ``os.execvpe`` / ``os.execvp`` — the menu-bar process must keep running.
    """
    which_fn = shutil.which if which is None else which
    run_fn = subprocess.run if run is None else run
    claude_bin = which_fn("claude")
    if not claude_bin:
        raise SessionError(
            "'claude' was not found on PATH. Install Claude Code first."
        )
    argv = build_kickoff_argv(claude_bin)
    env = build_kickoff_env(session_dir, environ)
    return run_fn(
        argv,
        env=env,
        cwd=str(session_dir),
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
