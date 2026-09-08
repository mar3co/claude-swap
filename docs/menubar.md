# Menu bar extra

Entry: `openswap menubar` → `openswap.menubar.run`. Optional extra: `rumps`.

## Process

LaunchAgent `com.opensoft.openswap.menubar` runs `openswap menubar`. Accessory activation policy (no Dock icon). `NSApp.appearance` is left `None` so the extra inherits System Settings → Appearance.

After `rumps` attaches the status item, a short timer steals the click for the popover (`menubar_panel.MenuBarPanel`) and sets autosave name `com.opensoft.openswap.menubar`.

## Split: pure vs AppKit

`menubar.py` helpers (`format_title`, `status_item_length`, `MenuBarSettings`, notification copy, panel snapshot adapters) must stay import-safe without rumps. Tests in `tests/test_menubar.py` never import AppKit.

`menubar_panel.py` is AppKit-only: popover, bars, Dark Mode colors, `fit_status_item`.

The header pins **openswap** on the left and an **Auto-switch** label plus `NSSwitch` on the trailing edge (`trailing_header_frames`). Behavior is `NSPopoverBehaviorApplicationDefined` so More’s overflow menu does not dismiss the popover (Transient would). Click-outside is a global left-click monitor (skip the popover, the status extra, and while More is open). Leave-delay `POPOVER_AUTO_CLOSE_S` (12s) starts only after the pointer exits the popover, not on open; the status extra counts as still inside. Rotate / Best / Settings / More do not close the popover. Settings is an in-popover page (Back returns to the cards); More is overflow only (Add / Disable / Remove / Refresh creds / History / Refresh now / Quit). The 1s usage tick does not reload the popover while Settings is open.

Card title is the alias or org tag (`personal` when the org name is empty); email is the subtitle. Sentinel notes (signed-out, foreign credential, …) render even when last-good bars are present. Account-row clicks call `switch_to(..., json_output=True)` unless the slot is `USAGE_RELOGIN_REQUIRED`. Signed-out clicks never switch a dead backup: capture only when the live Claude login matches that slot’s email **and** org uuid; otherwise the extra opens `claude auth login --email` in Terminal (after confirming if another managed account is signed in). After a matching login, the extra auto-captures on the 1s tick. A real switch toasts, stamps `autoswitch_state.json` `lastSwitchAt` (engine cooldown, default 5 minutes), and closes. Already-active closes with no toast. A `ClaudeSwitchError` leaves the popover open and brings the extra forward before `rumps.alert`. Cards implement `acceptsFirstMouse_` so the first click on a non-key popover switches. `rebuild_menu` does not reload an open popover (that replaced the view tree mid-click). `_detect_active_change` compares slot number, not email, so two orgs that share an address still refresh.

## Title width

AppKit’s default text extra is ~10pt inset per side. With the asterisk off that left inset is empty. `fit_status_item(..., compact=not show_icon, title=...)` writes the title on the status-item **button** (rumps still uses the deprecated `NSStatusItem.setTitle_`), clears the image, and sets length to measured title plus `STATUS_ITEM_COMPACT_PAD` (6pt total) when compact. Call it after every title rebuild and on popover attach. A sentinel on the active slot still titles from `last_good` (`title_usage`), frozen at `fetched_at` so a passed weekly reset does not paint as a fresh 0%.

## Appearance

An `NSPopover` shown from a status item inherits the **menu bar** appearance (wallpaper tint), which can stay Aqua while System Settings is Dark. `resolve_popover_theme` prefers `AppleInterfaceStyle` (`Dark` or unset), then `NSApp.effectiveAppearance`.

Palette tokens are catalog `NSColor`s with dynamic providers (`_dynamic`). Draw fills in `drawRect_`. Do not set `CALayer` `CGColor` from PyObjC (logs `ObjCPointerWarning` and does not flip with appearance).

Observe `effectiveAppearance` and `AppleInterfaceThemeChangedNotification`; reload the popover if it is shown.

## Auto-switch from the extra

`MenuBarSettings.auto_switch_enabled` is only the on/off toggle. Threshold and strategy are `settings.py` / `openswap config`. Changing strategy from the extra calls `set_setting` then `_restart_engine` so the running engine reloads policy.

Settings-page strategies: **Most quota left** (`best`), **Soonest weekly reset** (`consume-first`, ranks 7d `resets_at`), **Soonest 5-hour reset** (`soonest-5h`, ranks 5h `resets_at`). See `autoswitch._window_reset_ts`. Event trigger string stays `consume-first` for both consume strategies. A muted hold-reason line under the popover header says whether the extra is holding on the soonest account or would pick another (`auto_hold_line`). When a Claude Code session or IDE lock is live, a muted `running_line` sits above the footer. A successful extra switch (card, Rotate, Best) calls `record_manual_switch` so that policy does not undo the pick for `cooldownSeconds`.

## Kickoff

`kickoff.py` is due/eligibility + `claude -p ok`. The extra owns the clock (`kickoff_hour` / `minute`, `kickoff_last_date`). Toggle and time live on the Settings page; time is an hourly `NSPopUpButton` (`kickoff_time_options`). Persist `kickoff_last_date` only after a successful pass. Skip API-key accounts and windows whose `resets_at` is still in the future.

## Notifications

`rumps.notification` needs a bundle id. `ensure_notification_identity` writes a tiny `Info.plist` next to the uv interpreter (`com.opensoft.openswap.menubar`) if missing.

A switch toast includes “Restart Claude Code to apply now, or wait about 30 seconds.” only when a Claude Code session or IDE lock is live (`claude_running`). Otherwise the restart sentence is omitted.

A slot that newly becomes re-login-needed toasts once (`personal signed out`) when auto-switch is off (the engine already emits `account-quarantined` when it is on). Capture success toasts `{name} is signed in again`.
