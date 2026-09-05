"""Widget snapshot JSON the macOS WidgetKit extension reads."""

from __future__ import annotations

import json
from pathlib import Path

from claude_swap import widget_snapshot as ws
from claude_swap.menubar import panel_windows

_NOW = 1_000_000.0
_USAGE = {
    "five_hour": {"pct": 42.0, "resets_at": "2001-09-09T02:46:40+00:00"},
    "seven_day": {"pct": 18.0},
}


def _snap():
    return {
        "accounts": [
            (1, "a@x.com", True, _USAGE, _USAGE, "personal", False, None),
            (2, "b@x.com", False, "no credentials", None, "", True, None),
        ]
    }


def test_build_payload_stringifies_num_and_keeps_windows():
    payload = ws.build_widget_payload(_snap(), now=_NOW)
    assert payload["schema"] == ws.SCHEMA_VERSION
    assert payload["updated_at"] == _NOW
    assert payload["accounts"][0]["num"] == "1"
    assert payload["accounts"][0]["title"] == "personal"
    assert payload["accounts"][0]["active"] is True
    labels = [w["label"] for w in payload["accounts"][0]["windows"]]
    assert labels == ["5h", "7d"]
    assert payload["accounts"][1]["note"] == "no credentials"
    assert payload["accounts"][1]["windows"] == []


def test_panel_windows_exposes_resets_at_ts_for_the_widget():
    rows = panel_windows(_USAGE, now=_NOW)
    assert rows[0]["resets_at_ts"] is not None
    assert rows[1]["resets_at_ts"] is None


def test_write_widget_snapshot_atomic(tmp_path: Path):
    dest = tmp_path / "Library" / "Application Support" / "cswap" / "widget-snapshot.json"
    written = ws.write_widget_snapshot(_snap(), now=_NOW, dest=dest)
    assert written == dest
    data = json.loads(dest.read_text(encoding="utf-8"))
    assert data["accounts"][0]["title"] == "personal"
    assert data["schema"] == 1
    leftovers = list(dest.parent.glob("widget-snapshot.*"))
    assert leftovers == [dest]


def test_default_snapshot_path_under_application_support(tmp_path: Path):
    assert ws.default_snapshot_path(tmp_path) == (
        tmp_path / "Library" / "Application Support" / "cswap" / "widget-snapshot.json"
    )


def test_publish_returns_none_on_write_failure(tmp_path: Path, monkeypatch):
    dest = tmp_path / "widget-snapshot.json"

    def _boom(*a, **k):
        raise OSError("disk full")

    monkeypatch.setattr(ws, "write_widget_snapshot", _boom)
    assert ws.publish_widget_snapshot(_snap(), dest=dest) is None


def test_notify_and_wake_are_noop_off_darwin(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(ws.sys, "platform", "linux")
    ws.notify_widget_reload()  # must not raise
    ws.wake_widget_host(tmp_path)  # must not raise
