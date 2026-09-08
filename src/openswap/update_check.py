"""Upgrade this git checkout. OpenSwap is not on PyPI."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote, urlparse


def _looks_like_openswap_checkout(root: Path) -> bool:
    """True when ``root`` is this project's tree, not some other git repo."""
    return (root / "src" / "openswap" / "__init__.py").is_file()


def _checkout_root(package_file: Path | None = None) -> Path | None:
    """Directory of the git checkout this install points at, if any."""
    if package_file is None:
        import openswap

        raw = getattr(openswap, "__file__", None)
        if not raw:
            return _checkout_from_direct_url(None)
        package_file = Path(raw)
    path = Path(package_file)
    for candidate in (path, *path.parents):
        if (candidate / ".git").exists() and _looks_like_openswap_checkout(candidate):
            return candidate
    return _checkout_from_direct_url(path)


def _checkout_from_direct_url(package_file: Path | None) -> Path | None:
    if package_file is None:
        import openswap

        raw = getattr(openswap, "__file__", None)
        if not raw:
            return None
        package_file = Path(raw)
    candidates: list[Path] = []
    for ancestor in (package_file, *package_file.parents):
        if ancestor.name.endswith(".dist-info"):
            candidates.append(ancestor)
        if ancestor.name == "site-packages":
            candidates.extend(sorted(ancestor.glob("openswap-*.dist-info")))
    seen: set[Path] = set()
    for dist in candidates:
        if dist in seen:
            continue
        seen.add(dist)
        direct = dist / "direct_url.json"
        if not direct.is_file():
            continue
        try:
            data = json.loads(direct.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        url = data.get("url") or ""
        if not str(url).startswith("file:"):
            return None
        parsed = urlparse(str(url))
        local = unquote(parsed.path)
        return Path(local) if local else None
    return None


def _package_is_git_checkout(package_file: Path | None = None) -> bool:
    """True when openswap is loaded from a directory that has a .git ancestor."""
    root = _checkout_root(package_file)
    return root is not None and (root / ".git").exists()


def _detect_install_method() -> str | None:
    """Return 'uv', 'pipx', or None if we can't tell."""
    prefix = Path(sys.prefix)
    parts = tuple(p.lower() for p in prefix.parts)
    pairs = list(zip(parts, parts[1:]))

    if ("uv", "tools") in pairs:
        return "uv"
    if ("pipx", "venvs") in pairs:
        return "pipx"

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
    """OpenSwap is not on PyPI; never nag about a wheel there."""
    return None


def _refresh_launch_agents() -> None:
    """Re-point installed LaunchAgents at the upgraded tool. macOS only."""
    if sys.platform != "darwin":
        return
    from openswap import launch_agent
    from openswap import widget_install

    if launch_agent.plist_path().exists():
        launch_agent.install()
    widget_plist = widget_install.plist_path(widget_install.LABEL)
    if widget_plist.exists() and launch_agent.is_loaded(widget_install.LABEL):
        launch_agent._launchctl(
            "kickstart", "-k", launch_agent.service_target(widget_install.LABEL)
        )


def run_self_upgrade() -> int:
    """git pull this checkout, reinstall the editable tool, refresh agents."""
    from openswap.printer import error

    root = _checkout_root()
    if root is None:
        error(
            "OpenSwap is not published to PyPI.\n"
            "Clone https://github.com/mar3co/openswap.git then "
            "`uv tool install --force --editable '.[menubar]'`."
        )
        return 1
    if not root.exists():
        error(
            f"The git checkout at {root} is gone (moved?).\n"
            "From the new location run "
            "`uv tool install --force --editable '.[menubar]'`, "
            "then `openswap menubar --install-service`."
        )
        return 1

    pull = subprocess.run(["git", "-C", str(root), "pull"], check=False)
    if pull.returncode != 0:
        return pull.returncode
    inst = subprocess.run(
        ["uv", "tool", "install", "--force", "--editable", ".[menubar]"],
        cwd=str(root),
        check=False,
    )
    if inst.returncode != 0:
        return inst.returncode
    _refresh_launch_agents()
    return 0
