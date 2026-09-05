"""Usage snapshot the macOS WidgetKit extension reads.

The menu bar extra is a Python LaunchAgent; WidgetKit extensions are a
separate signed Swift .appex and cannot import this package. The extra
writes a JSON file to a stable path under Application Support and pokes
the widget host via a distributed notification so timelines reload.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from claude_swap.fsutil import replace_with_retry
from claude_swap.menubar import panel_accounts

SCHEMA_VERSION = 1
SNAPSHOT_FILENAME = "widget-snapshot.json"
COMMAND_FILENAME = "widget-command.json"
RELOAD_NOTIFICATION = "com.cswap.widget.reload"
WIDGET_APP_NAME = "cswap Widget.app"


def _support_dir(home: Path | None = None) -> Path:
    root = home if home is not None else Path.home()
    return root / "Library" / "Application Support" / "cswap"


def default_snapshot_path(home: Path | None = None) -> Path:
    """``~/Library/Application Support/cswap/widget-snapshot.json``."""
    return _support_dir(home) / SNAPSHOT_FILENAME


def default_command_path(home: Path | None = None) -> Path:
    """``~/Library/Application Support/cswap/widget-command.json``."""
    return _support_dir(home) / COMMAND_FILENAME


def parse_switch_command(raw: dict) -> str | None:
    """Return slot num if ``op=='switch'`` and ``num`` is a non-empty str/int.

    Never raises on a bad JSON shape.
    """
    if not isinstance(raw, dict):
        return None
    if raw.get("op") != "switch":
        return None
    num = raw.get("num")
    if isinstance(num, bool):
        return None
    if isinstance(num, int):
        return str(num)
    if isinstance(num, str) and num:
        return num
    return None


def consume_switch_command(path: Path | None = None) -> str | None:
    """Read, delete, and return a switch slot num.

    Missing file → ``None``. Unreadable or invalid → delete if possible,
    return ``None`` (do not retry a poison file).
    """
    dest = path if path is not None else default_command_path()
    try:
        text = dest.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    except OSError:
        _unlink_quiet(dest)
        return None
    _unlink_quiet(dest)
    try:
        raw = json.loads(text)
    except (json.JSONDecodeError, TypeError, ValueError):
        return None
    return parse_switch_command(raw)


def _unlink_quiet(path: Path) -> None:
    try:
        path.unlink()
    except OSError:
        pass


def widget_app_path(home: Path | None = None) -> Path:
    """Installed host app the WidgetKit extension is embedded in."""
    root = home if home is not None else Path.home()
    return root / "Applications" / WIDGET_APP_NAME


def build_widget_payload(snapshot: dict, now: float | None = None) -> dict:
    """JSON-friendly cards from a menubar snapshot dict."""
    if now is None:
        now = time.time()
    accounts = []
    for card in panel_accounts(snapshot, now=now):
        item = dict(card)
        item["num"] = str(card["num"])
        accounts.append(item)
    return {
        "schema": SCHEMA_VERSION,
        "updated_at": now,
        "accounts": accounts,
    }


def write_widget_snapshot(
    snapshot: dict,
    *,
    now: float | None = None,
    dest: Path | None = None,
) -> Path:
    """Atomically write the widget JSON. Parent dirs are created as needed."""
    dest = dest if dest is not None else default_snapshot_path()
    dest.parent.mkdir(parents=True, exist_ok=True)
    payload = build_widget_payload(snapshot, now=now)
    fd, tmp_name = tempfile.mkstemp(
        suffix=".json", prefix="widget-snapshot.", dir=str(dest.parent)
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, separators=(",", ":"))
        replace_with_retry(tmp_name, dest)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise
    return dest


def notify_widget_reload() -> None:
    """Ask the widget host to reload timelines. No-op off macOS or on failure."""
    if sys.platform != "darwin":
        return
    try:
        from Foundation import NSDistributedNotificationCenter

        NSDistributedNotificationCenter.defaultCenter().postNotificationName_object_userInfo_deliverImmediately_(
            RELOAD_NOTIFICATION, None, None, True
        )
    except Exception:
        pass


def wake_widget_host(home: Path | None = None) -> None:
    """Launch the widget host if it is installed, so it can relay reloads."""
    if sys.platform != "darwin":
        return
    app = widget_app_path(home)
    if not app.is_dir():
        return
    try:
        subprocess.Popen(
            ["/usr/bin/open", "-ga", str(app)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except OSError:
        pass


def publish_widget_snapshot(
    snapshot: dict,
    *,
    now: float | None = None,
    dest: Path | None = None,
) -> Path | None:
    """Write the snapshot and poke the host. Never raises (display path)."""
    try:
        path = write_widget_snapshot(snapshot, now=now, dest=dest)
        notify_widget_reload()
        return path
    except Exception:
        return None
