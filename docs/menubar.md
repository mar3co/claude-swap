# Menu bar extra

Entry: `cswap menubar` → `claude_swap.menubar.run`. Optional extra: `rumps`.

## Process

LaunchAgent `com.cswap.menubar` runs `cswap menubar`. Accessory activation policy (no Dock icon). `NSApp.appearance` is left `None` so the extra inherits System Settings → Appearance.

After `rumps` attaches the status item, a short timer steals the click for the popover (`menubar_panel.MenuBarPanel`) and sets autosave name `com.cswap.menubar`.

## Split: pure vs AppKit

`menubar.py` helpers (`format_title`, `status_item_length`, `MenuBarSettings`, notification copy, panel snapshot adapters) must stay import-safe without rumps. Tests in `tests/test_menubar.py` never import AppKit.

`menubar_panel.py` is AppKit-only: popover, bars, Dark Mode colors, `fit_status_item`.

## Title width

AppKit’s default text extra is ~10pt inset per side. With the asterisk off that left inset is empty. `fit_status_item(..., compact=not show_icon)` sets `NSStatusItem.length` to measured title plus `STATUS_ITEM_COMPACT_PAD` (6pt total). Call it after every `self.title = ...` and on popover attach.

## Appearance

An `NSPopover` shown from a status item inherits the **menu bar** appearance (wallpaper tint), which can stay Aqua while System Settings is Dark. `resolve_popover_theme` prefers `AppleInterfaceStyle` (`Dark` or unset), then `NSApp.effectiveAppearance`.

Palette tokens are catalog `NSColor`s with dynamic providers (`_dynamic`). Draw fills in `drawRect_`. Do not set `CALayer` `CGColor` from PyObjC (logs `ObjCPointerWarning` and does not flip with appearance).

Observe `effectiveAppearance` and `AppleInterfaceThemeChangedNotification`; reload the popover if it is shown.

## Auto-switch from the extra

`MenuBarSettings.auto_switch_enabled` is only the on/off toggle. Threshold and strategy are `settings.py` / `cswap config`. Changing strategy from the extra calls `set_setting` then `_restart_engine` so the running engine reloads policy.

`consume-first` ranks by **weekly** `resets_at`, not the 5h session. See `autoswitch._seven_day_reset_ts`.

## Kickoff

`kickoff.py` is due/eligibility + `claude -p ok`. The extra owns the clock (`kickoff_hour` / `minute`, `kickoff_last_date`). Persist `kickoff_last_date` only after a successful pass. Skip API-key accounts and windows whose `resets_at` is still in the future.

## Notifications

`rumps.notification` needs a bundle id. `ensure_notification_identity` writes a tiny `Info.plist` next to the uv interpreter (`com.claude-swap.menubar`) if missing.
