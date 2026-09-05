"""macOS menu bar app for claude-swap (``cswap --menubar``).

A thin GUI shell over ``ClaudeAccountSwitcher`` and the core auto-switch engine
(``claude_swap.autoswitch``) — it never re-implements account, usage, or
auto-switch logic. Usage for display comes from ``switcher.accounts_snapshot()``
(backed by the shared usage store); auto-switching, when enabled, runs the same
``AutoSwitchEngine`` the CLI's ``cswap auto`` drives, sharing
``autoswitch_state.json`` and the ``autoswitch.*`` settings. The menu bar keeps
only its own display preferences.

Built on ``rumps`` (an optional extra, macOS only). The pure helpers below
(settings, formatting, log parsing) are import-safe without rumps so they can be
unit-tested in CI; ``rumps`` is imported lazily inside the app glue.
"""

from __future__ import annotations

import json
import logging
import math
import os
import plistlib
import re
import sys
import threading
import time
from dataclasses import asdict, dataclass, fields
from datetime import datetime, timezone
from pathlib import Path

from claude_swap import pace
from claude_swap.exceptions import ClaudeSwitchError, CredentialReadError
from claude_swap.kickoff import (
    KICKOFF_RETRY_BACKOFF_S,
    format_kickoff_time,
    invoke_kickoff,
    kickoff_account_eligible,
    kickoff_backoff_active,
    kickoff_is_due,
    kickoff_pass_complete,
    kickoff_uses_default_login,
    parse_kickoff_time,
)
from claude_swap.autoswitch import record_manual_switch
from claude_swap.switcher import SENTINEL_NOTES, USAGE_API_KEY

REFRESH_CHOICES: tuple[int, ...] = (30, 60, 300)
AUTO_THRESHOLD_CHOICES: tuple[int, ...] = (80, 90, 95, 98)
AUTO_STRATEGY_CHOICES: tuple[tuple[str, str], ...] = (
    ("best", "Most quota left"),
    ("consume-first", "Soonest weekly reset"),
)
TITLE_PCT_CHOICES: tuple[str, ...] = ("off", "5h", "7d", "both")
SWITCH_HISTORY_LIMIT = 10
NOTIFICATION_BUNDLE_ID = "com.claude-swap.menubar"


def ensure_notification_identity(
    executable: Path | None = None,
    *,
    platform: str = sys.platform,
) -> Path | None:
    """Ensure rumps can resolve a bundle identifier for notifications.

    Command-line Python tools have no app bundle, so rumps looks for an
    ``Info.plist`` beside the interpreter. uv/pipx reinstalls can recreate that
    environment; repair the tiny plist on every launch when needed.
    """
    if platform != "darwin":
        return None
    path = (executable or Path(sys.executable)).parent / "Info.plist"
    data: dict = {}
    try:
        if path.exists():
            try:
                loaded = plistlib.loads(path.read_bytes())
            except Exception:
                loaded = None  # unreadable/corrupt — rebuild from scratch
            if isinstance(loaded, dict):
                data = loaded
        changed = False
        if not data.get("CFBundleIdentifier"):
            data["CFBundleIdentifier"] = NOTIFICATION_BUNDLE_ID
            changed = True
        if not data.get("CFBundleName"):
            data["CFBundleName"] = "claude-swap"
            changed = True
        if changed or not path.exists():
            # atomic: an interrupted write must not leave a half-written plist
            tmp = path.with_name(path.name + ".tmp")
            tmp.write_bytes(plistlib.dumps(data))
            os.replace(tmp, path)
    except (OSError, plistlib.InvalidFileException, ValueError) as exc:
        logging.getLogger("claude-swap").warning(
            "Could not prepare menu-bar notification identity: %s", exc
        )
        return None
    return path


@dataclass
class MenuBarSettings:
    """User-configurable menu bar display behavior, persisted as JSON.

    Only display preferences and the auto-switch on/off toggle live here.
    Auto-switch *policy* (threshold, cooldown, hysteresis, …) is core config,
    read/written through ``claude_swap.settings`` (the ``autoswitch.*`` keys),
    so the CLI and the menu bar share one source of truth.
    """

    show_account_name: bool = True
    title_pct: str = "both"  # one of TITLE_PCT_CHOICES
    title_scoped: bool = False  # append per-model weekly limits (e.g. Fable) to the title
    refresh_interval: int = 60
    auto_switch_enabled: bool = False
    show_icon: bool = False  # optional ✻ in the status-item title; off by default
    kickoff_enabled: bool = False
    kickoff_hour: int = 7
    kickoff_minute: int = 0
    kickoff_last_date: str = ""  # local YYYY-MM-DD of the last kickoff run

    @classmethod
    def load(cls, path: Path) -> "MenuBarSettings":
        """Load settings, falling back to defaults on any problem.

        Unknown keys are ignored; a value whose type doesn't match the field
        default is dropped (that field keeps its default). A missing or
        unparseable file yields all-defaults.
        """
        defaults = cls()
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return defaults
        if not isinstance(raw, dict):
            return defaults
        kwargs = {}
        for f in fields(cls):
            if f.name in raw and isinstance(raw[f.name], type(getattr(defaults, f.name))):
                kwargs[f.name] = raw[f.name]
        return cls(**kwargs)

    def save(self, path: Path) -> None:
        """Write settings as pretty JSON, creating parent directories."""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")


STATUS_ICON = "✻"
# AppKit's default title extra is ~10pt per side. With no leading icon that
# empty inset is just gap; compact width keeps ~3pt per side so the hover
# pill still clears the first glyph.
STATUS_ITEM_COMPACT_PAD = 6.0
NS_VARIABLE_STATUS_ITEM_LENGTH = -1.0
# After the pointer leaves the popover (not on open). Click-outside still
# dismisses immediately.
POPOVER_AUTO_CLOSE_S = 12.0
HEADER_TITLE_H = 20.0
HEADER_CONTROL_GAP = 6.0


@dataclass(frozen=True)
class NotificationCopy:
    """Title / subtitle / body for ``rumps.notification``, in that order."""

    title: str
    subtitle: str = ""
    body: str = ""

    def rumps_args(self) -> tuple[str, str, str]:
        return (self.title, self.subtitle, self.body)


def account_short_name(
    email: str | None = None,
    alias: str | None = None,
    number=None,
) -> str:
    """Glanceable account identity: alias, else email local-part, never ``Account-N (email)``."""
    if alias:
        return str(alias)
    if email:
        return _local_part(str(email))
    if number is not None and str(number) != "":
        return f"account {number}"
    return "unknown"


def account_card_names(email, alias, org_name) -> tuple[str, str]:
    """(title, subtitle) for extra/widget cards.

    Alias wins as title. Otherwise the TUI display tag (org name or
    'personal'). Email is always the subtitle when it differs from title.
    """
    title = alias or (org_name.strip() if org_name else "personal")
    email = email or ""
    subtitle = email if email != title else ""
    return title, subtitle


def _alias_lookup(number, email: str | None, aliases: dict[str, str] | None) -> str | None:
    if not aliases:
        return None
    if number is not None:
        found = aliases.get(str(number))
        if found:
            return found
    if email:
        return aliases.get(email) or None
    return None


def _name_from_ref(ref: dict | None, aliases: dict[str, str] | None) -> str:
    if not isinstance(ref, dict):
        return "unknown"
    email = ref.get("email")
    number = ref.get("number")
    alias = ref.get("alias") or _alias_lookup(number, email, aliases)
    return account_short_name(email, alias, number)


def format_local_reset(value: str | None, *, now: datetime | None = None) -> str | None:
    """Turn an ISO-Z / ISO-offset timestamp into a local clock like ``3:42 PM``.

    Adds a weekday when the reset is not today. Returns None when unparseable.
    """
    if not value or not isinstance(value, str):
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    local = dt.astimezone()
    clock = f"{local.hour % 12 or 12}:{local.minute:02d} {'AM' if local.hour < 12 else 'PM'}"
    now_local = (now or datetime.now().astimezone()).astimezone()
    if local.date() != now_local.date():
        return f"{local.strftime('%a')} {clock}"
    return clock


def notification_copy_for_event(
    event, aliases: dict[str, str] | None = None
) -> NotificationCopy | None:
    """Glanceable copy for menu-bar notifications, or None when the event is silent.

    Poll / no-switch / sleep / dry-run ticks do not notify. Account identity is
    alias-or-short-name, never ``Account-N (email)``. Trigger jargon is not the
    headline. Exhausted reset times are local-clock, not ISO-Z. Recovery is not
    a CLI command.
    """
    kind = getattr(event, "kind", None)
    if kind == "switch":
        if getattr(event, "dry_run", False):
            return None
        dest = _name_from_ref(getattr(event, "to_ref", None), aliases)
        src_ref = getattr(event, "from_ref", None)
        src = _name_from_ref(src_ref, aliases) if src_ref else None
        parts = []
        if src:
            parts.append(f"Was {src}.")
        parts.append("Restart Claude Code to apply now, or wait about 30 seconds.")
        return NotificationCopy(title=f"Switched to {dest}", body=" ".join(parts))
    if kind == "account-quarantined":
        name = account_short_name(
            getattr(event, "email", None),
            _alias_lookup(getattr(event, "number", None), getattr(event, "email", None), aliases),
            getattr(event, "number", None),
        )
        return NotificationCopy(
            title=f"{name} was paused",
            body="Sign in with this account in Claude Code, then add it back in claude-swap.",
        )
    if kind == "all-exhausted":
        reset = format_local_reset(getattr(event, "earliest_reset_at", None))
        body = f"Earliest reset at {reset}." if reset else "No reset time is known yet."
        return NotificationCopy(title="All accounts are out of usage", body=body)
    if kind == "config-warning":
        message = str(getattr(event, "message", "") or "A setting is not doing anything.")
        return NotificationCopy(title="Settings need a look", body=message)
    return None


def notification_copy_for_manual_switch(dest_name: str) -> NotificationCopy:
    """Copy after a user-initiated switch; the title names the destination."""
    return NotificationCopy(
        title=f"Switched to {dest_name}",
        body="Restart Claude Code to apply now, or wait about 30 seconds.",
    )


def notification_copy_for_engine_start_failure(message: str) -> NotificationCopy:
    return NotificationCopy(
        title="Auto-switch didn't start",
        body=str(message) or "The auto-switch engine failed to start.",
    )


def notification_copy_for_kickoff(
    results: list[tuple[str, bool, str]],
) -> NotificationCopy | None:
    """Copy after a scheduled 5h kickoff pass. None when nothing was attempted."""
    if not results:
        return None
    ok = [name for name, success, _err in results if success]
    bad = [(name, err) for name, success, err in results if not success]
    if ok and not bad:
        if len(ok) == 1:
            title = f"Started {ok[0]}'s 5-hour window"
        else:
            title = "Started 5-hour windows"
        body = "Pinged " + ", ".join(ok) + "."
    elif ok and bad:
        title = "Started some 5-hour windows"
        failed = ", ".join(name for name, _err in bad)
        body = f"Started {', '.join(ok)}. Couldn't reach {failed}."
    else:
        title = "Couldn't start 5-hour windows"
        body = "; ".join(
            f"{name}: {err}" if err else name for name, err in bad
        )[:240]
    return NotificationCopy(title=title, body=body)


# ---- pure display helpers (operate on the usage-window dict shape produced by
# ---- oauth.build_usage_result / stored in UsageEntry.last_good) --------------

def tightest_pct(usage: dict | str | None) -> float | None:
    """Highest 5h/7d utilization percentage, or None if unknown.

    Surfaces the binding window's utilization for display. Spend is excluded —
    it isn't a rate-limit window.
    """
    if not isinstance(usage, dict):
        return None
    pcts = [
        window["pct"]
        for window in (usage.get("five_hour"), usage.get("seven_day"))
        if isinstance(window, dict) and isinstance(window.get("pct"), (int, float))
    ]
    return max(pcts) if pcts else None


def _window_pct(usage: dict | str | None, key: str) -> float | None:
    """Utilization pct for a usage window (``five_hour``/``seven_day``), or None."""
    if isinstance(usage, dict):
        window = usage.get(key)
        if isinstance(window, dict) and isinstance(window.get("pct"), (int, float)):
            return float(window["pct"])
    return None


def _resets_at_ts(window: dict | str | None) -> float:
    """POSIX timestamp of a usage window's ``resets_at``; inf if missing/bad."""
    if isinstance(window, dict):
        ra = window.get("resets_at")
        if isinstance(ra, str):
            try:
                return datetime.fromisoformat(ra).timestamp()
            except ValueError:
                pass
    return float("inf")


def _live_countdown(window: dict | str | None, now: float) -> str | None:
    """Time until a usage window resets, computed live from ``resets_at``.

    The cached usage dict's ``countdown`` string is frozen at fetch time, so a
    stale (e.g. last-known-good) entry would show a wrong remaining time. Deriving
    it from the absolute ``resets_at`` keeps it correct between/without refetches.
    Returns ``None`` when there's no ``resets_at`` or it has already passed.
    """
    ts = _resets_at_ts(window)
    if ts == float("inf"):
        return None
    remaining = int(ts - now)
    if remaining <= 0:
        return None
    days, rem = divmod(remaining, 86400)
    hours, rem = divmod(rem, 3600)
    minutes = rem // 60
    if days > 0:
        return f"{days}d {hours}h"
    if hours > 0:
        return f"{hours}h {minutes}m"
    return f"{minutes}m"


_WEEKLY_PERIOD_S = 7 * 86400  # weekly limits reset on a fixed 7-day cadence


def _rolled_weekly_window(window: dict | None, now: float) -> dict | None:
    """A weekly window with a passed reset advanced to its next 7-day boundary.

    Weekly limits reset on a fixed weekly cadence, so once the stored
    ``resets_at`` is in the past we know the window rolled over — the stored pct
    belongs to a window that no longer exists. Return a copy reflecting the reset
    state (``pct`` 0, ``resets_at`` advanced to the next future boundary) so the
    menu bar shows the reset from the static schedule alone, without waiting to
    spend tokens on a fresh fetch. Missing/future/unparseable windows are
    returned unchanged.
    """
    if not isinstance(window, dict):
        return window
    ts = _resets_at_ts(window)
    if ts == float("inf") or ts > now:
        return window
    missed = int((now - ts) // _WEEKLY_PERIOD_S) + 1
    new_ts = ts + missed * _WEEKLY_PERIOD_S
    rolled = dict(window)
    rolled["pct"] = 0.0
    rolled["resets_at"] = datetime.fromtimestamp(new_ts, tz=timezone.utc).isoformat()
    rolled.pop("countdown", None)  # recomputed live from the rolled resets_at
    rolled.pop("clock", None)
    return rolled


def usage_summary(
    usage: dict | str | None, now: float | None = None, fetched_at: float | None = None
) -> str:
    """One-line usage summary for an account row (reset countdown computed live).

    ``fetched_at`` is the underlying measurement's fetch time (may be older
    than ``now`` when serving last-good data) — used only to flag a weekly
    window that's meaningfully ahead of pace (issue #125), never the 5h one.
    """
    if isinstance(usage, str):
        return usage
    if usage is None:
        return "usage unavailable"
    if now is None:
        now = time.time()
    parts: list[str] = []
    for key, label in (("five_hour", "5h"), ("seven_day", "7d")):
        window = usage.get(key)
        pace_result = None
        if key == "seven_day":
            window = _rolled_weekly_window(window, now)  # reflect a passed weekly reset
            # Pace against the rolled window, not the raw one: a stale window
            # rolled to 0% has no current-cycle data to compare against, so
            # its (correctly zeroed) pct naturally never reads as "ahead" —
            # computing pace pre-roll would otherwise pair last cycle's high
            # pct with this cycle's freshly-reset 0% display.
            pace_result = pace.compute_pace(window, fetched_at=fetched_at)
        if isinstance(window, dict) and isinstance(window.get("pct"), (int, float)):
            seg = f"{label} {window['pct']:.0f}%"
            if key == "seven_day" and pace_result and pace_result.ahead:
                seg += " (ahead)"
            countdown = _live_countdown(window, now)
            if countdown:
                seg += f" ({countdown})"  # time until this window resets
            parts.append(seg)
    # Per-model weekly limits (e.g. Fable), from the usage API's ``limits`` array.
    for window in usage.get("scoped") or []:
        window = _rolled_weekly_window(window, now)  # weekly cadence, same roll-forward
        pace_result = pace.compute_pace(window, fetched_at=fetched_at)  # against the rolled window, see above
        if isinstance(window, dict) and isinstance(window.get("pct"), (int, float)) and window.get("name"):
            seg = f"{window['name']} {window['pct']:.0f}%"
            if window["pct"] >= 100:
                seg += " (!)"  # maxed model — the usual reason to switch
            elif pace_result and pace_result.ahead:
                seg += " (ahead)"
            countdown = _live_countdown(window, now)
            if countdown:
                seg += f" ({countdown})"
            parts.append(seg)
    spend = usage.get("spend")
    if isinstance(spend, dict) and isinstance(spend.get("pct"), (int, float)):
        parts.append(f"$ {spend['pct']:.0f}%")
    return " · ".join(parts) if parts else "usage unavailable"


def format_account_label(
    num,
    email: str,
    usage: dict | str | None,
    now: float | None = None,
    alias: str | None = None,
    disabled: bool = False,
    fetched_at: float | None = None,
) -> str:
    """Build one account row's menu label."""
    label = f"{alias}  ({email})" if alias else email
    marker = "  (disabled)" if disabled else ""
    return f"{num}  {label}{marker}  {usage_summary(usage, now, fetched_at)}"


def panel_windows(
    usage: dict | str | None,
    now: float | None = None,
    fetched_at: float | None = None,
) -> list[dict]:
    """Usage windows for the popover (drawn bars, not the status-item title).

    Each item is ``{label, pct, countdown, resets_at_ts, ahead, maxed}``.
    Sentinel strings and missing usage produce an empty list — the popover
    shows ``note`` instead. ``resets_at_ts`` is a POSIX timestamp so the
    macOS widget can recompute the countdown between extra refreshes.
    """
    if not isinstance(usage, dict):
        return []
    if now is None:
        now = time.time()
    rows: list[dict] = []
    for key, label in (("five_hour", "5h"), ("seven_day", "7d")):
        window = usage.get(key)
        ahead = False
        if key == "seven_day":
            window = _rolled_weekly_window(window, now)
            result = pace.compute_pace(window, fetched_at=fetched_at)
            ahead = bool(result and result.ahead)
        if isinstance(window, dict) and isinstance(window.get("pct"), (int, float)):
            rows.append(_window_row(label, window, ahead=ahead, maxed=False, now=now))
    for window in usage.get("scoped") or []:
        window = _rolled_weekly_window(window, now)
        if not (
            isinstance(window, dict)
            and isinstance(window.get("pct"), (int, float))
            and window.get("name")
        ):
            continue
        result = pace.compute_pace(window, fetched_at=fetched_at)
        pct = float(window["pct"])
        rows.append(
            _window_row(
                str(window["name"]),
                window,
                ahead=bool(result and result.ahead) and pct < 100,
                maxed=pct >= 100,
                now=now,
            )
        )
    return rows


def _window_row(
    label: str, window: dict, *, ahead: bool, maxed: bool, now: float
) -> dict:
    ts = _resets_at_ts(window)
    return {
        "label": label,
        "pct": float(window["pct"]),
        "countdown": _live_countdown(window, now),
        "resets_at_ts": None if ts == float("inf") else ts,
        "ahead": ahead,
        "maxed": maxed,
    }


def resolve_popover_theme(
    *,
    app_appearance_name: str | None,
    interface_style: str | None,
) -> str:
    """Dark vs light for the menu-bar popover.

    Status items follow the menu bar, which tints with the wallpaper and can
    stay Aqua while System Settings → Appearance is Dark. The popover should
    follow Dark Mode instead. ``AppleInterfaceStyle`` is the live system
    value (unset in Light, ``Dark`` in Dark, including while auto-switching).
    The app appearance is the fallback when that default is missing.
    """
    if (interface_style or "").lower() == "dark":
        return "dark"
    name = str(app_appearance_name or "")
    if "Dark" in name:
        return "dark"
    return "light"


def panel_accounts(snapshot: dict, now: float | None = None) -> list[dict]:
    """Account cards for the popover, from the menubar snapshot dict."""
    if now is None:
        now = time.time()
    cards = []
    for row in snapshot.get("accounts") or []:
        num, email, is_active, display, _last_good, alias, org_name, disabled, fetched_at = row
        note = display if isinstance(display, str) else None
        title, subtitle = account_card_names(email, alias, org_name)
        cards.append(
            {
                "num": num,
                "title": title,
                "subtitle": subtitle,
                "active": bool(is_active),
                "disabled": bool(disabled),
                "note": note,
                "windows": panel_windows(
                    display if isinstance(display, dict) else None, now, fetched_at
                ),
            }
        )
    return cards


def _local_part(email: str, limit: int = 12) -> str:
    """Email text before '@', truncated with a trailing '*' marker."""
    local = email.split("@", 1)[0]
    if len(local) > limit:
        return local[: limit - 1] + "*"
    return local


def format_title(
    active_email: str | None,
    active_usage: dict | str | None,
    settings: MenuBarSettings,
    now: float | None = None,
    alias: str | None = None,
    org_name: str | None = None,
) -> str:
    """Build the menu-bar title from the active account and settings."""
    if active_email is None:
        return STATUS_ICON if settings.show_icon else ""
    if now is None:
        now = time.time()
    segments: list[str] = []
    if settings.show_account_name:
        org = org_name.strip() if org_name else ""
        segments.append(alias or org or _local_part(active_email))
    if settings.title_pct in ("5h", "both"):
        p = _window_pct(active_usage, "five_hour")
        if p is not None:
            segments.append(f"{p:.0f}%")
    if settings.title_pct in ("7d", "both"):
        seven = active_usage.get("seven_day") if isinstance(active_usage, dict) else None
        seven = _rolled_weekly_window(seven, now)  # reflect a passed weekly reset
        p = seven["pct"] if isinstance(seven, dict) and isinstance(seven.get("pct"), (int, float)) else None
        if p is not None:
            segments.append(f"{p:.0f}%")
    if settings.title_scoped and isinstance(active_usage, dict):
        # Per-model weekly limits (e.g. Fable), same shape/roll-forward as the
        # dropdown rows; named so multiple scoped models stay distinguishable.
        for window in active_usage.get("scoped") or []:
            window = _rolled_weekly_window(window, now)
            if isinstance(window, dict) and isinstance(window.get("pct"), (int, float)) and window.get("name"):
                segments.append(f"{window['name']} {window['pct']:.0f}%")
    text = " · ".join(segments)
    if settings.show_icon:
        return f"{STATUS_ICON} {text}" if text else STATUS_ICON
    return text


def status_item_length(title_width: float, *, compact: bool) -> float:
    """Width for the status extra. Compact (icon off) drops the ~10pt insets."""
    if not compact or title_width <= 0:
        return NS_VARIABLE_STATUS_ITEM_LENGTH
    return float(math.ceil(title_width + STATUS_ITEM_COMPACT_PAD))


def trailing_header_frames(
    panel_width: float,
    pad: float,
    label_wh: tuple[float, float],
    control_wh: tuple[float, float],
    *,
    title_h: float = HEADER_TITLE_H,
    gap: float = HEADER_CONTROL_GAP,
) -> tuple[tuple[float, float, float, float], tuple[float, float, float, float]]:
    """Pin a label+control pair to the top-right of the popover header.

    Sizes are ``(width, height)``. Returns ``(label_frame, control_frame)``
    as ``(x, y, w, h)`` in a flipped view (origin at the top-left). The
    control's trailing edge sits ``pad`` from the panel's right edge; both
    are vertically centered on the title row.
    """
    lw, lh = label_wh
    cw, ch = control_wh
    x = panel_width - pad - (lw + gap + cw)
    mid_y = pad + title_h / 2.0
    ly = max(pad, mid_y - lh / 2.0)
    cy = max(pad, mid_y - ch / 2.0)
    return (x, ly, lw, lh), (x + lw + gap, cy, cw, ch)


def format_usage_log(email: str, usage: dict | str | None) -> str | None:
    """A log line of an account's session (5h) and weekly (7d) limits.

    Uses each window's absolute reset ``clock`` rather than a live countdown,
    since log lines are already timestamped. Returns ``None`` when no numeric
    window is available (sentinels, ``None``, or spend-only) so callers can skip
    logging nothing.
    """
    parts: list[str] = []
    for key, label in (("five_hour", "5h"), ("seven_day", "7d")):
        pct = _window_pct(usage, key)
        if pct is None:
            continue
        window = usage.get(key)  # a dict — _window_pct found a numeric pct in it
        clock = window.get("clock") if isinstance(window, dict) else None
        seg = f"{label} {pct:.0f}%"
        if clock:
            seg += f" (resets {clock})"
        parts.append(seg)
    if not parts:
        return None
    return f"usage {email}: " + " · ".join(parts)


def _usage_log_key(usage: dict | str | None) -> tuple[float | None, float | None]:
    """De-dupe key for usage logging: the (5h, 7d) percentages only.

    Reset clocks change every refresh; keying on the percentages means an idle
    account isn't re-logged every cycle.
    """
    return (_window_pct(usage, "five_hour"), _window_pct(usage, "seven_day"))


_SWITCH_LOG_RE = re.compile(r"Switched from account (\d+) to (\d+)")


def parse_switch_history(log_text: str, limit: int = SWITCH_HISTORY_LIMIT) -> list[str]:
    """Recent account switches from the log, most-recent first.

    Reads the ``Switched from account X to Y`` lines the switcher logs and pairs
    each with its timestamp (trimmed to the minute). Returns at most ``limit``
    entries like ``"3 → 1   2026-06-27 02:06"``. Any unparseable line is skipped.
    """
    out: list[str] = []
    for line in log_text.splitlines():
        m = _SWITCH_LOG_RE.search(line)
        if not m:
            continue
        stamp = line.split(" - ", 1)[0].strip()[:16]  # "YYYY-MM-DD HH:MM"
        out.append(f"{m.group(1)} → {m.group(2)}   {stamp}")
    return out[-limit:][::-1]


def _account_display_usage(entry) -> dict | str | None:
    """Menu-display usage for a ``UsageEntry``.

    A human-readable note for a sentinel state (token expired / API key /
    keychain unavailable), otherwise the last-good measurement dict, otherwise
    ``None``.
    """
    if entry.sentinel:
        return SENTINEL_NOTES.get(entry.sentinel, entry.sentinel)
    return entry.last_good


EMPTY_SNAPSHOT: dict = {
    "accounts": [],
    "active_email": None,
    "active_num": None,
    "active_usage": None,
    "active_alias": None,
    "active_org": None,
}


def _adapt_snapshot(snap) -> dict:
    """Adapt an ``AccountsSnapshot`` to the menu bar's render dict.

    Shape: ``{"accounts": [(num, email, is_active, display_usage, last_good, alias, org_name, disabled, fetched_at), ...],
    "active_email": str | None, "active_num": str | None,
    "active_usage": dict | str | None, "active_alias": str | None,
    "active_org": str | None}``. The snapshot itself is produced by
    ``SnapshotSource`` (the paced read path), so this is a pure transform — no
    fetching, no I/O. Per-account ``fetched_at`` is the underlying
    measurement's fetch time, used only for the pace marker (issue #125).
    """
    accounts = []
    active_email = None
    active_num = None
    active_usage = None
    active_alias = None
    active_org = None
    for acc in snap.accounts:
        display = _account_display_usage(acc.usage)
        org_name = getattr(acc, "org_name", "") or ""
        accounts.append(
            (
                acc.number, acc.email, acc.is_active, display, acc.usage.last_good,
                acc.alias, org_name, acc.disabled, acc.usage.fetched_at,
            )
        )
        if acc.is_active:
            active_email, active_usage, active_alias = acc.email, display, acc.alias
            active_org = org_name
            active_num = str(acc.number)
    return {
        "accounts": accounts,
        "active_email": active_email,
        "active_num": active_num,
        "active_usage": active_usage,
        "active_alias": active_alias,
        "active_org": active_org,
    }


def should_notify_manual_switch(result: dict | None) -> bool:
    """Toast only when credentials actually moved, not on already-active."""
    return bool(result and result.get("switched"))


def should_dismiss_panel_after_switch(result: dict | None) -> bool:
    """Close the popover after a handled click; keep it open on error."""
    return result is not None


def live_slot_changed(snapshot: dict, live_num: str | int | None) -> bool:
    """True when the live slot differs from the snapshot, even if emails match."""
    snap = snapshot.get("active_num")
    snap_s = str(snap) if snap is not None else None
    live_s = str(live_num) if live_num is not None else None
    return snap_s != live_s


def run(switcher) -> int:
    """Entry point for ``cswap --menubar``. Blocks until the user quits."""
    ensure_notification_identity()
    try:
        import rumps  # lazy: optional dependency, imported only when launching
        import AppKit  # ships with rumps (pyobjc-framework-Cocoa), never fails alone
    except ImportError as e:
        # This module is import-safe without rumps by design, so the CLI's
        # guard around ``from claude_swap.menubar import run`` can never see a
        # missing extra — the failure lands here at call time. Raise the
        # error type the CLI already renders cleanly instead of a traceback.
        raise ClaudeSwitchError(
            "Menu bar mode requires 'rumps'. "
            "Install with: pip install 'claude-swap[menubar]'"
        ) from e

    # rumps never sets an activation policy, so under a framework Python the
    # process launches as a regular app and parks a "Python" icon in the Dock
    # for as long as the menu bar runs. Accessory keeps the status item and
    # dialog windows but stays out of the Dock and the Cmd-Tab switcher.
    nsapp = AppKit.NSApplication.sharedApplication()
    nsapp.setActivationPolicy_(AppKit.NSApplicationActivationPolicyAccessory)
    # Inherit System Settings → Appearance. A pinned Aqua appearance would
    # keep the popover light after Dark Mode turns on.
    nsapp.setAppearance_(None)

    from claude_swap.autoswitch import AutoSwitchEngine
    from claude_swap.settings import load_settings, set_setting
    from claude_swap.snapshot_source import SnapshotSource

    settings_path = switcher.backup_dir / "menubar_settings.json"
    log_path = switcher.backup_dir / "claude-swap.log"

    class MenuBarApp(rumps.App):
        def __init__(self):
            super().__init__("claude-swap", quit_button=None)
            self.switcher = switcher
            self.settings = MenuBarSettings.load(settings_path)
            # The supported paced read path: per refresh it fetches only the
            # active account plus (at most once per freshness window) one stale
            # alternate, so an open menu costs O(1) requests per window instead
            # of a full pass per tick — which kept every token at its per-account
            # rate-limit edge. Reused across refreshes to hold its pacing state.
            self._snapshot_source = SnapshotSource(switcher)
            self.snapshot = dict(EMPTY_SNAPSHOT)
            self._dirty = False
            self._snapshot_at = 0.0
            self._refreshing = False
            self._config_path = switcher._get_claude_config_path()
            self._config_mtime = 0.0
            self._last_usage_log: dict = {}  # account num -> last-logged (5h, 7d) key
            # Auto-switch engine (the same one `cswap auto` runs), hosted in a
            # background thread while enabled.
            self._engine = None
            self._engine_events: list = []
            self._event_lock = threading.Lock()
            self._panel = None
            self._kickoff_running = False
            self._kickoff_results = None
            self._kickoff_retry_after: float | None = None
            self._kickoff_succeeded_nums: set[str] = set()
            self._kickoff_success_date = ""
            self.rebuild_menu()
            # Background display refresh on the user's interval, plus a fast
            # UI-sync tick that applies snapshots + engine events on the main thread.
            self.refresh_timer = rumps.Timer(self.on_refresh_tick, self.settings.refresh_interval)
            self.refresh_timer.start()
            self.sync_timer = rumps.Timer(self.on_sync_tick, 1)
            self.sync_timer.start()
            # rumps attaches an NSMenu in initializeStatusBar (after __init__).
            # Steal the click for the popover once the status item exists.
            self._attach_timer = rumps.Timer(self._attach_panel_once, 0.15)
            self._attach_timer.start()
            self.refresh_async()  # first display fetch
            from claude_swap.widget_snapshot import wake_widget_host
            wake_widget_host()
            if self.settings.auto_switch_enabled:
                self._start_engine()

        # ---- display refresh plumbing ----------------------------------------
        def refresh_async(self, full=False):
            if self._refreshing:
                return  # in-flight guard: one worker at a time (SnapshotSource
                        # pacing state is only touched by this single worker)
            self._refreshing = True
            threading.Thread(target=self._worker, args=(full,), daemon=True).start()

        def _worker(self, full):
            # Lock-free handoff: worker only rebinds plain attributes (atomic in
            # CPython); the main-thread sync tick reads them. While the engine
            # runs it already paces all fetching, so the display reads store-only.
            try:
                try:
                    raw = self._snapshot_source.take(
                        full=full, store_only=self._engine is not None
                    )
                except Exception:
                    # Keep the last good snapshot rather than blanking the menu.
                    self.switcher._logger.debug("menubar snapshot failed", exc_info=True)
                    return
                snap = _adapt_snapshot(raw)
                self._log_usage(snap)
                self.snapshot = snap
                self._snapshot_at = time.time()
                self._dirty = True  # picked up by on_sync_tick on the main thread
                from claude_swap.widget_snapshot import publish_widget_snapshot
                publish_widget_snapshot(snap, now=self._snapshot_at)
            finally:
                self._refreshing = False

        def _log_usage(self, snap):
            """Log each account's session/weekly limits when they change.

            Runs on every refresh (background thread; the logger is thread-safe)
            but de-dupes per account on the (5h, 7d) percentages so an idle
            machine doesn't churn the rotating log with identical lines.
            """
            for num, email, _is_active, _display, last_good, _alias, _org, _disabled, _fetched_at in snap["accounts"]:
                key = _usage_log_key(last_good)
                if key == (None, None) or self._last_usage_log.get(num) == key:
                    continue
                line = format_usage_log(email, last_good)
                if line:
                    self.switcher._logger.info(line)
                    self._last_usage_log[num] = key

        def on_refresh_tick(self, _timer):
            self.refresh_async()

        def on_sync_tick(self, _timer):
            if self._dirty:
                self._dirty = False
                self.rebuild_menu()
            self._detect_active_change()
            self._drain_engine_events()
            self._drain_kickoff_results()
            self._maybe_kickoff()

        def _detect_active_change(self):
            # Reflect account switches from any source (menu, CLI, auto engine)
            # within ~1s. Detecting *which* account is active is a cheap local
            # read of ~/.claude.json -- no Keychain or usage API -- so we can do
            # it on every tick. We gate the read on the file's mtime (a cheap
            # stat) so a large config isn't parsed each second, and only kick a
            # refresh when the active *slot* changed (Claude Code rewrites this
            # file often for unrelated reasons). Slot, not email: two orgs can
            # share an address.
            if self._refreshing:
                return  # a worker is already in-flight; it refreshes the marker
            try:
                mtime = self._config_path.stat().st_mtime
            except OSError:
                return
            if mtime == self._config_mtime:
                return
            self._config_mtime = mtime
            if live_slot_changed(
                self.snapshot, self.switcher.current_account_number()
            ):
                self.refresh_async()

        # ---- auto-switch engine ----------------------------------------------
        def _start_engine(self):
            """Run the core AutoSwitchEngine (live) in a background thread."""
            if self._engine is not None:
                return
            try:
                engine = AutoSwitchEngine(
                    self.switcher,
                    load_settings(self.switcher.backup_dir),
                    self._on_engine_event,
                    dry_run=False,
                )
            except Exception as e:  # never let a bad start crash the menu bar
                self.switcher._logger.warning("auto-switch engine failed to start: %s", e)
                self._notify(notification_copy_for_engine_start_failure(str(e)))
                return
            self._engine = engine
            threading.Thread(target=self._run_engine, args=(engine,), daemon=True).start()

        def _run_engine(self, engine):
            try:
                engine.run_loop()
            except Exception:
                self.switcher._logger.debug("auto-switch engine crashed", exc_info=True)

        def _stop_engine(self):
            if self._engine is not None:
                self._engine.stop()
                self._engine = None

        def _restart_engine(self):
            """Apply changed core settings by restarting the running engine."""
            if self._engine is not None:
                self._stop_engine()
                self._start_engine()

        def _on_engine_event(self, event):
            # Runs on the engine thread; must not raise. Queue for the main
            # thread, which surfaces notifications and reacts on the sync tick.
            with self._event_lock:
                self._engine_events.append(event)

        def _drain_engine_events(self):
            with self._event_lock:
                events, self._engine_events = self._engine_events, []
            aliases = self._alias_map()
            for ev in events:
                copy = notification_copy_for_event(ev, aliases)
                if copy is not None:
                    self._notify(copy)
                if ev.kind == "switch" and not getattr(ev, "dry_run", False):
                    self.refresh_async()  # reflect the switch promptly

        def _threshold(self) -> int:
            """Current auto-switch threshold from core settings (for the menu)."""
            try:
                return int(load_settings(self.switcher.backup_dir).threshold)
            except Exception:
                return 0

        def _strategy(self) -> str:
            """Current auto-switch strategy from core settings (for the menu)."""
            try:
                return load_settings(self.switcher.backup_dir).strategy
            except Exception:
                return "best"

        # ---- menu construction -----------------------------------------------
        def _attach_panel_once(self, timer):
            timer.stop()
            try:
                from claude_swap.menubar_panel import (
                    MenuBarPanel,
                    fit_status_item,
                    pin_status_item,
                )
                nsitem = self._nsapp.nsstatusitem
            except Exception:
                self.switcher._logger.debug("popover attach failed", exc_info=True)
                return
            try:
                pin_status_item(nsitem)
            except Exception:
                self.switcher._logger.debug("status item autosave failed", exc_info=True)
            try:
                fit_status_item(nsitem, compact=not self.settings.show_icon)
            except Exception:
                self.switcher._logger.debug("status item fit failed", exc_info=True)
            self._panel = MenuBarPanel(
                on_switch=self._switch_from_panel,
                on_rotate=lambda *_a: self._switch(None)(None),
                on_best=lambda *_a: self._switch("best")(None),
                on_toggle_auto=lambda *_a: self.on_toggle_autoswitch(None),
                on_more=self._popup_overflow,
                auto_enabled=lambda: self.settings.auto_switch_enabled,
                snapshot=lambda: self.snapshot,
                threshold=self._threshold,
            )
            self._panel.attach(nsitem)

        def _popup_overflow(self, sender=None):
            menu = self.menu._menu
            view = sender if sender is not None else self._nsapp.nsstatusitem.button()
            if view is None:
                return
            loc = (0, 0)
            try:
                loc = (0, view.bounds().size.height)
            except Exception:
                pass
            menu.popUpMenuPositioningItem_atLocation_inView_(None, loc, view)

        def _fit_status_item(self):
            nsapp = getattr(self, "_nsapp", None)
            nsitem = getattr(nsapp, "nsstatusitem", None) if nsapp is not None else None
            if nsitem is None:
                return
            try:
                from claude_swap.menubar_panel import fit_status_item

                fit_status_item(nsitem, compact=not self.settings.show_icon)
            except Exception:
                self.switcher._logger.debug("status item fit failed", exc_info=True)

        def rebuild_menu(self):
            self.title = format_title(
                self.snapshot["active_email"],
                self.snapshot["active_usage"],
                self.settings,
                alias=self.snapshot.get("active_alias"),
                org_name=self.snapshot.get("active_org"),
            )
            self._fit_status_item()
            # Stop a rumps memory leak: rumps registers each menu item's callback
            # in the process-global NSApp._ns_to_py_and_callback, but Menu.clear()
            # never removes them, so rebuilding the whole menu on every refresh
            # leaks every item forever (~1GB after days on a busy machine). Purge
            # this menu's entries before we tear it down. We walk the *native*
            # NSMenu tree (itemArray, recursing into submenus) rather than the
            # rumps Python dict: that dict is keyed by title and silently drops
            # same-title items, which would leave leaked entries behind.
            # Guard the private rumps attribute: if a future rumps release renames
            # it, degrade to "leaks again" rather than crashing on every rebuild.
            _reg = getattr(rumps.rumps.NSApp, "_ns_to_py_and_callback", None)
            if _reg is not None:
                def _purge(nsmenu):
                    for _it in nsmenu.itemArray():
                        _reg.pop(_it, None)
                        _sub = _it.submenu()
                        if _sub is not None:
                            _purge(_sub)
                _purge(self.menu._menu)
            self.menu.clear()
            # Overflow menu (popover More…): account switching lives in the
            # popover, so this list is management + settings only.
            self.menu = [
                rumps.MenuItem("Rotate to next", callback=self._switch(None)),
                rumps.MenuItem("Switch to best", callback=self._switch("best")),
                rumps.MenuItem("Next available", callback=self._switch("next-available")),
                None,
                self._add_menu(rumps),
                self._disable_menu(rumps),
                self._remove_menu(rumps),
                rumps.MenuItem("Refresh current credentials", callback=self.on_refresh_creds),
                self._history_menu(rumps),
                None,
                self._settings_menu(rumps),
                rumps.MenuItem("Refresh now", callback=self.on_refresh_now),
                rumps.MenuItem("Quit", callback=self.on_quit),
            ]
            if self._panel is not None:
                try:
                    self._nsapp.nsstatusitem.setMenu_(None)
                except AttributeError:
                    pass
                # Do not reload an open popover: replacing the view tree
                # between mouseDown and mouseUp swallows the account-row click.

        def _add_menu(self, rumps):
            menu = rumps.MenuItem("Add account")
            menu.add(rumps.MenuItem("From current login", callback=self.on_add_login))
            if hasattr(self.switcher, "add_account_from_token"):
                menu.add(rumps.MenuItem("From setup-token…", callback=self.on_add_token))
            return menu

        def _remove_menu(self, rumps):
            menu = rumps.MenuItem("Remove account")
            accounts = self.snapshot["accounts"]
            if not accounts:
                menu.add(rumps.MenuItem("No managed accounts", callback=None))
            for num, email, _is_active, _display, _last_good, alias, _org, _disabled, _fetched_at in accounts:
                label = f"{num}  {alias}  ({email})" if alias else f"{num}  {email}"
                menu.add(rumps.MenuItem(label, callback=self._make_remove(num)))
            return menu

        def _disable_menu(self, rumps):
            menu = rumps.MenuItem("Disable / enable account")
            accounts = self.snapshot["accounts"]
            if not accounts:
                menu.add(rumps.MenuItem("No managed accounts", callback=None))
            for num, email, _is_active, _display, _last_good, alias, _org, disabled, _fetched_at in accounts:
                name = f"{alias}  ({email})" if alias else email
                item = rumps.MenuItem(
                    f"{num}  {name}", callback=self._make_toggle_disabled(num, disabled)
                )
                # A check-mark reads as "held out of rotation" — same glyph the
                # active row uses, but here it means disabled, not selected.
                item.state = 1 if disabled else 0
                menu.add(item)
            return menu

        def _history_menu(self, rumps):
            menu = rumps.MenuItem("Switch history")
            try:
                text = log_path.read_text(encoding="utf-8")
            except OSError:
                text = ""
            entries = parse_switch_history(text)
            if entries:
                for line in entries:
                    menu.add(rumps.MenuItem(line, callback=None))
            else:
                menu.add(rumps.MenuItem("No switches logged yet", callback=None))
            menu.add(None)
            menu.add(rumps.MenuItem("Open full log…", callback=self.on_open_log))
            return menu

        def _settings_menu(self, rumps):
            menu = rumps.MenuItem("Settings")
            name_item = rumps.MenuItem("Show account name in menu bar", callback=self.on_toggle_name)
            name_item.state = 1 if self.settings.show_account_name else 0
            menu.add(name_item)

            title_pct = rumps.MenuItem("Title percentage")
            tp_labels = {"off": "None", "5h": "Session (5h)",
                         "7d": "Weekly (7d)", "both": "Both (5h · 7d)"}
            for mode in TITLE_PCT_CHOICES:
                ch = rumps.MenuItem(tp_labels[mode], callback=self._make_title_pct(mode))
                ch.state = 1 if self.settings.title_pct == mode else 0
                title_pct.add(ch)
            menu.add(title_pct)

            scoped_item = rumps.MenuItem(
                "Show model limits in title", callback=self.on_toggle_scoped
            )
            scoped_item.state = 1 if self.settings.title_scoped else 0
            menu.add(scoped_item)

            interval = rumps.MenuItem("Refresh interval")
            labels = {30: "30 seconds", 60: "60 seconds", 300: "5 minutes"}
            for secs in REFRESH_CHOICES:
                choice = rumps.MenuItem(labels[secs], callback=self._make_interval(secs))
                choice.state = 1 if self.settings.refresh_interval == secs else 0
                interval.add(choice)
            menu.add(interval)

            auto_item = rumps.MenuItem("Auto-switch accounts", callback=self.on_toggle_autoswitch)
            auto_item.state = 1 if self.settings.auto_switch_enabled else 0
            menu.add(auto_item)

            threshold_menu = rumps.MenuItem("Auto-switch threshold")
            current = self._threshold()
            for pct in AUTO_THRESHOLD_CHOICES:
                ch = rumps.MenuItem(f"{pct}%", callback=self._make_threshold(pct))
                ch.state = 1 if current == pct else 0
                threshold_menu.add(ch)
            menu.add(threshold_menu)

            strategy_menu = rumps.MenuItem("Auto-switch strategy")
            current_strategy = self._strategy()
            for value, label in AUTO_STRATEGY_CHOICES:
                ch = rumps.MenuItem(label, callback=self._make_strategy(value))
                ch.state = 1 if current_strategy == value else 0
                strategy_menu.add(ch)
            menu.add(strategy_menu)

            kickoff = rumps.MenuItem("Start 5-hour window")
            kickoff_on = rumps.MenuItem("Enabled", callback=self.on_toggle_kickoff)
            kickoff_on.state = 1 if self.settings.kickoff_enabled else 0
            kickoff.add(kickoff_on)
            kickoff_time = rumps.MenuItem("Time")
            for hour in range(24):
                ch = rumps.MenuItem(
                    format_kickoff_time(hour, 0),
                    callback=self._make_kickoff_hour(hour),
                )
                ch.state = (
                    1
                    if self.settings.kickoff_hour == hour
                    and self.settings.kickoff_minute == 0
                    else 0
                )
                kickoff_time.add(ch)
            kickoff_time.add(None)
            kickoff_time.add(rumps.MenuItem("Custom…", callback=self.on_kickoff_custom))
            kickoff.add(kickoff_time)
            menu.add(kickoff)

            advanced = rumps.MenuItem("Advanced")
            icon_item = rumps.MenuItem(
                "Show asterisk in menu bar", callback=self.on_toggle_icon
            )
            icon_item.state = 1 if self.settings.show_icon else 0
            advanced.add(icon_item)
            menu.add(advanced)

            return menu

        # ---- callbacks --------------------------------------------------------
        def _save_and_rebuild(self):
            self.settings.save(settings_path)
            self.rebuild_menu()

        def _show_error(self, message: str):
            import AppKit
            AppKit.NSApplication.sharedApplication().activateIgnoringOtherApps_(True)
            rumps.alert(title="claude-swap", message=message)

        def _guard(self, fn):
            """Run a switcher action, surfacing ClaudeSwitchError via an alert."""
            try:
                fn()
                return True
            except ClaudeSwitchError as e:
                self._show_error(str(e))
                return False

        def _run_switch(self, fn):
            try:
                return fn()
            except ClaudeSwitchError as e:
                self._show_error(str(e))
                return None

        def _finish_manual_switch(self, result, dest_name, *, close_panel):
            if result is None:
                return
            if should_notify_manual_switch(result):
                record_manual_switch(self.switcher.backup_dir)
                self._notify_switched(dest_name)
                self.refresh_async()
            if (
                close_panel
                and should_dismiss_panel_after_switch(result)
                and self._panel is not None
            ):
                self._panel.close()

        def _notify(self, copy: NotificationCopy | None):
            if copy is None:
                return
            rumps.notification(*copy.rumps_args())

        def _alias_map(self) -> dict[str, str]:
            aliases: dict[str, str] = {}
            for num, email, _a, _d, _lg, alias, _org, _dis, _fa in self.snapshot["accounts"]:
                if alias:
                    aliases[str(num)] = alias
                    aliases[email] = alias
            return aliases

        def _name_for_num(self, num) -> str:
            for row in self.snapshot["accounts"]:
                if str(row[0]) == str(num):
                    return account_short_name(row[1], row[5] or None, num)
            return account_short_name(None, None, num)

        def _current_dest_name(self) -> str:
            current = self.switcher._get_current_account()
            email = current[0] if current else None
            alias = None
            if email:
                for row in self.snapshot["accounts"]:
                    if row[1] == email:
                        alias = row[5] or None
                        break
            return account_short_name(email, alias)

        def _notify_switched(self, dest_name: str):
            self._notify(notification_copy_for_manual_switch(dest_name))

        def _switch_from_panel(self, num):
            result = self._run_switch(
                lambda: self.switcher.switch_to(str(num), json_output=True)
            )
            self._finish_manual_switch(
                result, self._name_for_num(num), close_panel=True
            )

        def _switch(self, strategy):
            def cb(_sender):
                result = self._run_switch(
                    lambda: self.switcher.switch(strategy=strategy, json_output=True)
                )
                self._finish_manual_switch(
                    result, self._current_dest_name(), close_panel=False
                )
            return cb

        def _make_remove(self, num):
            def cb(_sender):
                if rumps.alert(
                    title="Remove account",
                    message=f"Remove account {num}?",
                    ok="Remove",
                    cancel="Cancel",
                ) == 1:  # 1 == OK
                    if self._guard(lambda: self.switcher.remove_account(str(num), assume_yes=True)):
                        self.refresh_async()
            return cb

        def _make_toggle_disabled(self, num, disabled):
            # `disabled` is this row's current state; selecting it flips it.
            target = not disabled
            def cb(_sender):
                if self._guard(
                    lambda: self.switcher.set_account_disabled(str(num), target)
                ):
                    self.refresh_async()
            return cb

        def on_add_login(self, _sender):
            if self._guard(self.switcher.add_account):
                self.refresh_async()

        def on_add_token(self, _sender):
            # A menu-bar (accessory) app isn't the active app, so a modal
            # rumps.Window can render black/blank until we bring the app
            # forward. Activate before showing the input dialogs.
            import AppKit
            AppKit.NSApplication.sharedApplication().activateIgnoringOtherApps_(True)
            email_win = rumps.Window(
                title="Add account from setup-token",
                message="Email for this token:",
                ok="Next", cancel="Cancel", dimensions=(320, 24),
            )
            email_resp = email_win.run()
            if email_resp.clicked != 1 or not email_resp.text.strip():
                return
            token_win = rumps.Window(
                title="Add account from setup-token",
                message="Setup token (sk-ant-oat01-…):",
                ok="Add", cancel="Cancel", dimensions=(320, 24),
            )
            token_resp = token_win.run()
            if token_resp.clicked != 1 or not token_resp.text.strip():
                return
            if self._guard(lambda: self.switcher.add_account_from_token(
                token=token_resp.text.strip(), email=email_resp.text.strip(), slot=None,
            )):
                self.refresh_async()

        def on_open_log(self, _sender):
            import subprocess
            # Reveal the log in Finder (-R); if it doesn't exist yet, open the dir.
            target = log_path if log_path.exists() else log_path.parent
            subprocess.run(["open", "-R", str(target)], check=False)

        def on_refresh_creds(self, _sender):
            if self.switcher._get_current_account() is None:
                rumps.alert(title="claude-swap",
                            message="No active Claude Code login detected. Log in first.")
                return
            try:
                self.switcher.add_account(slot=None)
            except CredentialReadError:
                # Almost always a launchd/login-agent Keychain block: the active
                # credential lives in the macOS Keychain, which a background agent
                # can't read (the security call times out). Point at the fix.
                rumps.alert(
                    title="claude-swap",
                    message="Couldn't read the active credential. If the menu bar is running "
                            "as a background/login agent, macOS blocks its Keychain access — "
                            "quit and relaunch it from a Terminal with: cswap --menubar",
                )
                return
            except ClaudeSwitchError as e:
                rumps.alert(title="claude-swap", message=str(e))
                return
            self.refresh_async()

        def on_refresh_now(self, _sender):
            self.refresh_async(full=True)  # explicit user refresh → full pass

        def on_quit(self, _sender):
            self._stop_engine()
            rumps.quit_application()

        def on_toggle_name(self, _sender):
            self.settings.show_account_name = not self.settings.show_account_name
            self._save_and_rebuild()

        def on_toggle_scoped(self, _sender):
            self.settings.title_scoped = not self.settings.title_scoped
            self._save_and_rebuild()

        def _make_title_pct(self, mode):
            def cb(_sender):
                self.settings.title_pct = mode
                self._save_and_rebuild()
            return cb

        def _make_interval(self, secs):
            def cb(_sender):
                self.settings.refresh_interval = secs
                # rumps 0.4.0's Timer.interval setter is a no-op while running
                # unless a full interval has elapsed; stop/start forces the new
                # cadence to take effect immediately.
                self.refresh_timer.stop()
                self.refresh_timer.interval = secs
                self.refresh_timer.start()
                self._save_and_rebuild()
            return cb

        def on_toggle_autoswitch(self, _sender):
            self.settings.auto_switch_enabled = not self.settings.auto_switch_enabled
            self.settings.save(settings_path)
            if self.settings.auto_switch_enabled:
                self._start_engine()
            else:
                self._stop_engine()
            self.rebuild_menu()

        def on_toggle_icon(self, _sender):
            self.settings.show_icon = not self.settings.show_icon
            self._save_and_rebuild()

        def on_toggle_kickoff(self, _sender):
            self.settings.kickoff_enabled = not self.settings.kickoff_enabled
            self._save_and_rebuild()

        def _make_kickoff_hour(self, hour):
            def cb(_sender):
                self.settings.kickoff_hour = hour
                self.settings.kickoff_minute = 0
                self._save_and_rebuild()
            return cb

        def on_kickoff_custom(self, _sender):
            import AppKit
            AppKit.NSApplication.sharedApplication().activateIgnoringOtherApps_(True)
            win = rumps.Window(
                title="Start 5-hour window",
                message="Local time (for example 7:00 or 7:30 AM):",
                ok="Set",
                cancel="Cancel",
                dimensions=(320, 24),
                default_text=format_kickoff_time(
                    self.settings.kickoff_hour, self.settings.kickoff_minute
                ),
            )
            resp = win.run()
            if resp.clicked != 1:
                return
            parsed = parse_kickoff_time(resp.text)
            if parsed is None:
                rumps.alert(
                    title="claude-swap",
                    message="Use a time like 7:00 or 7:30 AM.",
                )
                return
            self.settings.kickoff_hour, self.settings.kickoff_minute = parsed
            self._save_and_rebuild()

        def _maybe_kickoff(self):
            if self._kickoff_running or self._kickoff_results is not None:
                return
            now = datetime.now()
            today = now.date().isoformat()
            if self._kickoff_success_date != today:
                self._kickoff_succeeded_nums.clear()
                self._kickoff_success_date = today
            if kickoff_backoff_active(
                now=time.time(), retry_after=self._kickoff_retry_after
            ):
                return
            s = self.settings
            if not kickoff_is_due(
                s.kickoff_enabled,
                s.kickoff_hour,
                s.kickoff_minute,
                s.kickoff_last_date,
                now,
            ):
                return
            # Don't start before the first snapshot has arrived.
            if not self.snapshot.get("accounts") and self._snapshot_at == 0.0:
                return
            self._kickoff_running = True
            threading.Thread(target=self._run_kickoff, daemon=True).start()

        def _run_kickoff(self):
            results: list[tuple[str, bool, str]] = []
            try:
                from claude_swap.session import SessionManager

                mgr = SessionManager(self.switcher)
                for (
                    num, email, is_active, display, last_good, alias, _org, _dis, _fa
                ) in self.snapshot["accounts"]:
                    if str(num) in self._kickoff_succeeded_nums:
                        continue
                    try:
                        is_api = self.switcher._account_kind(str(num)) == "api_key"
                    except Exception:
                        is_api = display in (
                            SENTINEL_NOTES.get(USAGE_API_KEY),
                            USAGE_API_KEY,
                        )
                    if not kickoff_account_eligible(
                        is_api_key=is_api,
                        usage=last_good if isinstance(last_good, dict) else None,
                    ):
                        continue
                    name = account_short_name(email, alias or None, num)
                    try:
                        if kickoff_uses_default_login(is_active=bool(is_active)):
                            proc = invoke_kickoff()
                        else:
                            session_dir, _, _ = mgr.setup_session(
                                str(num), share=True, share_history=False
                            )
                            proc = invoke_kickoff(session_dir)
                        if proc.returncode == 0:
                            results.append((name, True, ""))
                            self._kickoff_succeeded_nums.add(str(num))
                        else:
                            err = (
                                proc.stderr or proc.stdout or "claude exited with an error"
                            ).strip()
                            results.append((name, False, err[:200]))
                    except Exception as e:
                        results.append((name, False, str(e)))
            except Exception as e:
                results.append(("kickoff", False, str(e)))
            finally:
                with self._event_lock:
                    self._kickoff_results = results
                    self._kickoff_running = False

        def _drain_kickoff_results(self):
            with self._event_lock:
                results = self._kickoff_results
                self._kickoff_results = None
            if results is None:
                return
            if kickoff_pass_complete(results):
                self.settings.kickoff_last_date = datetime.now().date().isoformat()
                self.settings.save(settings_path)
                self._kickoff_retry_after = None
                self._kickoff_succeeded_nums.clear()
            else:
                self._kickoff_retry_after = time.time() + KICKOFF_RETRY_BACKOFF_S
            self._notify(notification_copy_for_kickoff(results))
            self.refresh_async()

        def _make_threshold(self, pct):
            def cb(_sender):
                try:
                    set_setting(self.switcher.backup_dir, "autoswitch.threshold", str(pct))
                except Exception as e:
                    rumps.alert(title="claude-swap", message=f"Couldn't set threshold: {e}")
                    return
                self._restart_engine()  # apply immediately if running
                self.rebuild_menu()
            return cb

        def _make_strategy(self, strategy):
            def cb(_sender):
                try:
                    set_setting(
                        self.switcher.backup_dir, "autoswitch.strategy", strategy
                    )
                except Exception as e:
                    rumps.alert(title="claude-swap", message=f"Couldn't set strategy: {e}")
                    return
                self._restart_engine()
                self.rebuild_menu()
            return cb

    MenuBarApp().run()
    return 0
