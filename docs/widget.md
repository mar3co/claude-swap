# Widget companion

Python cannot host WidgetKit. Split:

1. Extra writes `~/Library/Application Support/cswap/widget-snapshot.json` (`widget_snapshot.py`).
2. Extra posts Darwin notification `com.cswap.widget.reload`.
3. `cswap Widget.app` (LSUIElement) listens and calls `WidgetCenter.shared.reloadAllTimelines()`.
4. The appex reads the JSON (sandbox: home-relative read-write exception on `Library/Application Support/cswap/` only + `getpwuid` for the real home; container `NSHomeDirectory()` is wrong).
5. A tap writes `~/Library/Application Support/cswap/widget-command.json` (`{"op":"switch","num":…}`). The extra consumes it on the 1s sync tick and switches like a popover card click. The extra must be running; the widget cannot switch on its own. Disabled cards are not tappable.

Sources: `macos/CSwapWidget/`. Install: `cswap widget --install` (`widget_install.py`).

## Build

`xcodebuild` scheme `CSwapWidget`, Release, `DEVELOPMENT_TEAM=…`, copy to `~/Applications/cswap Widget.app`, bootstrap LaunchAgent `com.cswap.widget`.

`project_dir()` walks from `widget_install.py` until it finds `macos/CSwapWidget/CSwapWidget.xcodeproj`. That only works from this git checkout (or if sources are vendored next to the package as `macos_widget`). A PyPI wheel does not include `macos/`.

Regenerate the Xcode project with xcodegen from `macos/CSwapWidget/project.yml` if you change that file. `cswap widget --install` runs `xcodebuild` only.

## Signing

`detect_development_team()` order:

1. `DEVELOPMENT_TEAM` env
2. TeamIdentifier on the already-installed app (so rebuilds do not flip bundle ids)
3. Xcode last-selected team, if it has a local Apple Development cert
4. Any local cert OU

Last Xcode team on a machine that also has VirtualShield can be `5LHJJ5JW3C`. Prefer the installed app’s team (`KJ999FVUJ4` on this Mac) so `com.cswap.widget` does not change and already-placed widgets do not go blank.

No App Group: that needs the Developer Portal. The home-relative sandbox exception is enough (read-write on that directory only, so the appex can write the command file).

## Families

`systemSmall` (active account), `systemMedium` (up to 3), `systemLarge` (up to 6). Timeline: 30 one-minute entries, then `.after(30m)`. Countdown uses `resets_at_ts` from the snapshot, not a frozen string.

`accessoryCircular` / `accessoryRectangular` are iOS Lock Screen and watchOS complications only (`@available(macOS, unavailable)`). This companion is a macOS widget, so those families are not declared.

Colors match the TUI (`SEV_OK` / `WARN` / `CRIT`, 70 / 90). Use `NSColor` dynamic providers, not a one-shot `@Environment(\.colorScheme)`.

## Caches

xcodebuild derived data: `~/Library/Caches/cswap-widget`. Safe to delete.
