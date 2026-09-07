"""Shared color constants for the extra, widget, and CLI.

A subtle modern dark theme: neutral charcoal in the VS Code register, one warm
terracotta accent (the same xterm-173 tone printer.py has always used for the
CLI), and desaturated severity colors so usage bars read calmly. Light
companions are tuned for a warm near-white base.

Severity bands match auto-switch: WARN at 70%, CRIT at 90% (the default
threshold). Hex values here are the source of truth; Swift copies them for
WidgetKit.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

ACCENT = "#d7875f"  # warm terracotta (xterm 173)
FOREGROUND = "#e8e4de"  # soft, slightly warm off-white
MUTED = "#8a8a8a"  # secondary text
BACKGROUND = "#141414"
SURFACE = "#1e1e1e"
PANEL = "#262626"

# Usage severity ramp (desaturated for dark backgrounds).
SEV_OK = "#87af87"  # calm green: plenty of headroom
SEV_WARN = "#d7af5f"  # amber: climbing (>= 70%)
SEV_CRIT = "#d75f5f"  # soft red: near the limit (>= 90%)
TRACK = "#3a3a3a"  # unfilled bar track

# Severity band edges. WARN mirrors where a user starts caring; CRIT mirrors
# the auto-switch default threshold so bar color and switch behavior agree.
WARN_PCT = 70.0
CRIT_PCT = 90.0

# Light companion palette (same intent, tuned for a warm near-white base).
ACCENT_LIGHT = "#954c2a"  # burnt sienna — deepened for AA on panel
FOREGROUND_LIGHT = "#2b2723"
MUTED_LIGHT = "#635d55"
BACKGROUND_LIGHT = "#faf7f2"
SURFACE_LIGHT = "#efeae1"
PANEL_LIGHT = "#e2dbcf"  # most-elevated = darkest (inverted from dark)
SEV_OK_LIGHT = "#3d6b3d"  # forest green — deepened for AA on panel
SEV_WARN_LIGHT = "#795911"  # deep ochre — deepened for AA on panel
SEV_CRIT_LIGHT = "#ad3128"  # brick red — deepened for AA on panel
TRACK_LIGHT = "#cec7ba"


@dataclass(frozen=True)
class Palette:
    """Resolved colors for one appearance (dark or light)."""

    accent: str
    foreground: str
    muted: str
    sev_ok: str
    sev_warn: str
    sev_crit: str
    track: str

    DARK: ClassVar["Palette"]
    LIGHT: ClassVar["Palette"]

    def severity(self, pct: float | None) -> str:
        if pct is None:
            return self.muted
        if pct >= CRIT_PCT:
            return self.sev_crit
        if pct >= WARN_PCT:
            return self.sev_warn
        return self.sev_ok


Palette.DARK = Palette(
    accent=ACCENT,
    foreground=FOREGROUND,
    muted=MUTED,
    sev_ok=SEV_OK,
    sev_warn=SEV_WARN,
    sev_crit=SEV_CRIT,
    track=TRACK,
)
Palette.LIGHT = Palette(
    accent=ACCENT_LIGHT,
    foreground=FOREGROUND_LIGHT,
    muted=MUTED_LIGHT,
    sev_ok=SEV_OK_LIGHT,
    sev_warn=SEV_WARN_LIGHT,
    sev_crit=SEV_CRIT_LIGHT,
    track=TRACK_LIGHT,
)
