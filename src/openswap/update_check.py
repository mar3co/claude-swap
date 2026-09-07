"""Check PyPI for newer versions of openswap."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import urllib.request
from pathlib import Path

from openswap.cache import CACHE_DIR, MISSING, read_cache, write_cache

CACHE_PATH = CACHE_DIR / "update_check.json"
CACHE_TTL = 24 * 3600  # 24 hours
PYPI_URL = "https://pypi.org/pypi/openswap/json"


def _parse_version(v: str) -> tuple[int, ...]:
    return tuple(int(x) for x in v.split("."))


def _package_is_git_checkout(package_file: Path | None = None) -> bool:
    """True when openswap is loaded from a directory that has a .git ancestor.

    Walk parents of package_file (default: openswap.__file__). Stop at
    filesystem root. A `.git` file (gitdir for worktrees) or directory both
    count. Never follow the path into uv/tools or pipx as a positive: those
    copies have no `.git`.
    """
    if package_file is None:
        import openswap

        raw = getattr(openswap, "__file__", None)
        if not raw:
            return False
        package_file = Path(raw)
    path = Path(package_file)
    for candidate in (path, *path.parents):
        if (candidate / ".git").exists():
            return True
    return False


def _detect_install_method() -> str | None:
    """Return 'uv', 'pipx', or None if we can't tell."""
    prefix = Path(sys.prefix)
    parts = tuple(p.lower() for p in prefix.parts)
    pairs = list(zip(parts, parts[1:]))

    if ("uv", "tools") in pairs:
        return "uv"
    if ("pipx", "venvs") in pairs:
        return "pipx"

    # Env-var override: only trust if sys.prefix is actually under it.
    for env_var, name in (("UV_TOOL_DIR", "uv"), ("PIPX_HOME", "pipx")):
        root = os.environ.get(env_var)
        if root:
            try:
                if prefix.is_relative_to(Path(root)):
                    return name
            except (ValueError, OSError):
                pass
    return None


def check_for_update(current_version: str) -> str | None:
    """Return a notification string if a newer version exists, else None."""
    if _package_is_git_checkout():
        return None
    try:
        latest_version = None

        # Try reading cache
        cached_data = read_cache(CACHE_PATH, CACHE_TTL)
        if cached_data is not MISSING:
            latest_version = cached_data
        else:
            # Fetch from PyPI
            try:
                req = urllib.request.Request(PYPI_URL)
                with urllib.request.urlopen(req, timeout=2) as resp:
                    data = json.loads(resp.read().decode())
                latest_version = data["info"]["version"]
            except Exception:
                latest_version = None

            # Write cache regardless of success/failure
            write_cache(CACHE_PATH, latest_version)

        if latest_version and _parse_version(latest_version) > _parse_version(current_version):
            method = _detect_install_method()
            direct = {
                "uv": "uv tool upgrade openswap",
                "pipx": "pipx upgrade openswap",
            }.get(method or "")
            if direct and sys.platform != "win32":
                # openswap upgrade actually performs the upgrade here.
                hint = "Run `openswap upgrade` to update."
            elif direct:
                # Windows: openswap upgrade only prints, so point at the real command.
                hint = f"Run `{direct}` to update."
            else:
                # Unknown install method: openswap upgrade shows manual instructions.
                hint = "Run `openswap upgrade` for upgrade instructions."
            return (
                f"A newer version of openswap is available ({latest_version}). "
                f"You are using {current_version}. {hint}"
            )
        return None
    except Exception:
        return None


def run_self_upgrade() -> int:
    """Run the appropriate upgrade command for the current install method.

    Returns the subprocess exit code, or 1 if detection failed or the package
    manager is missing from PATH.
    """
    from openswap.printer import accent, error

    if _package_is_git_checkout():
        error(
            "This is a git checkout; OpenSwap is not published to PyPI.\n"
            "Upgrade with `git pull` then `uv tool install --editable '.[menubar]'`."
        )
        return 1

    method = _detect_install_method()
    commands = {
        "uv": ["uv", "tool", "upgrade", "openswap"],
        "pipx": ["pipx", "upgrade", "openswap"],
    }
    cmd = commands.get(method or "")
    if cmd is None:
        error(
            "Could not detect install method (looked for uv tool / pipx).\n"
            f"  sys.prefix:     {sys.prefix}\n"
            f"  sys.executable: {sys.executable}\n"
            "To upgrade manually, run one of:\n"
            "  uv tool upgrade openswap\n"
            "  pipx upgrade openswap\n"
            f"  {sys.executable} -m pip install --upgrade openswap\n"
            "If you installed with `pip install -e .`, use `git pull` instead."
        )
        return 1

    # Windows: the running openswap.exe launcher is locked, so an in-process
    # uv/pipx upgrade fails when it tries to replace the executable even
    # though the package itself updates. openswap exits right after this, which
    # releases the lock, so the user can just run the command themselves.
    if sys.platform == "win32":
        print(f"To upgrade openswap on Windows, run:\n  {accent(' '.join(cmd))}")
        return 1

    try:
        result = subprocess.run(cmd, check=False)
        return result.returncode
    except FileNotFoundError:
        error(
            f"Detected {method} install but `{cmd[0]}` is not on PATH. "
            "Run the upgrade manually from a shell where it is available."
        )
        return 1
