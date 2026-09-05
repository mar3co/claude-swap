# Desktop widget (macOS)

A WidgetKit widget for Notification Center and the Desktop. Small: the active account. Medium: up to three accounts. Large: up to six.

Python cannot host WidgetKit, so cswap ships a small signed host app (`cswap Widget.app`) plus an extension. The menu bar extra writes `~/Library/Application Support/cswap/widget-snapshot.json` and asks the host to reload.

## Requirements

- This git checkout (the extra looks for `macos/CSwapWidget`)
- Xcode (command-line tools are not enough to build the `.appex`)
- An Apple Development signing identity (Xcode → Settings → Accounts)
- The [menu bar extra](Menu-Bar) running, so numbers stay live

## Install

```bash
cswap widget --install
cswap widget --status
```

That builds with your Development Team, copies `~/Applications/cswap Widget.app`, and starts LaunchAgent `com.cswap.widget`.

Then add it:

1. **Notification Center:** click the date in the menu bar → Edit Widgets
2. **Desktop:** right-click the desktop → Edit Widgets
3. Search for **cswap**

macOS does not let apps place a widget for you.

## Uninstall

```bash
cswap widget --uninstall
```

Removes the app and the LaunchAgent. Remove the widget from the Desktop / Notification Center the same way you added it.

## Signing team

`cswap widget --install` picks a team in this order:

1. `DEVELOPMENT_TEAM` in the environment
2. The team already on `~/Applications/cswap Widget.app` (so rebuilds do not flip bundle IDs)
3. Xcode’s last-selected team, if that team has a local cert
4. Any local Apple Development cert

If identifiers ever flip, widgets you already placed can go blank until you add them again. Prefer leaving `DEVELOPMENT_TEAM` unset after the first successful install so the installed app’s team is reused.

## Dark Mode

The widget uses dynamic colors and follows Light / Dark, including Desktop widgets sitting on a light or dark wallpaper.

## Empty or stale numbers

- Start the extra: `cswap menubar --install-service`
- Confirm the snapshot exists: `~/Library/Application Support/cswap/widget-snapshot.json`
- `cswap widget --status` should show the host loaded
- Rebuild if you moved machines: `cswap widget --install`
