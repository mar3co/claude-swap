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
RELOAD_NOTIFICATION = "com.cswap.widget.reload"
WIDGET_APP_NAME = "cswap Widget.app"


def default_snapshot_path(home: Path | None = None) -> Path:
    """``~/Library/Application Support/cswap/widget-snapshot.json``."""
    root = home if home is not None else Path.home()
    return root / "Library" / "Application Support" / "cswap" / SNAPSHOT_FILENAME


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
