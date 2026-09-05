# Menu bar (macOS)

The extra is a small title in the macOS menu bar. Click it for a popover with usage bars. It can run the same auto-switch engine as `cswap auto`, show notifications, and fire the [5-hour kickoff](Five-Hour-Kickoff).

## Install and keep it running

```bash
uv tool install --editable '.[menubar]'   # from this clone
cswap menubar --install-service           # now, and at every login
cswap menubar --service-status
cswap menubar --uninstall-service
```

`cswap menubar` without `--install-service` runs in the foreground and dies with that terminal.

The agent is `~/Library/LaunchAgents/com.cswap.menubar.plist`. Logs:

- `~/Library/Logs/com.cswap.menubar.log`
- `~/Library/Logs/com.cswap.menubar.err`

After `cswap upgrade` or a `git pull` on an editable install, restart it:

```bash
launchctl kickstart -k "gui/$(id -u)/com.cswap.menubar"
```

## Popover

Click the extra. Each account is a card with 5-hour, 7-day, and per-model (Fable, …) rows: bar, percent, time until reset. Click a card to switch. Footer actions: rotate, best, auto-switch toggle, More…

The popover follows **System Settings → Appearance** (Light, Dark, or Auto). It does not follow the menu bar’s wallpaper tint.

## Title

More → Settings:

| Setting | Default | Effect |
| --- | --- | --- |
| Show account name in menu bar | on | Alias or email local-part |
| Title percentage | both | `off` / 5h / 7d / both |
| Show model limits in title | off | e.g. `Fable 10%` |
| Refresh interval | 60s (service often 5 min) | How often usage is fetched |

With the asterisk **off** (default), the extra shrinks to the title so you do not get a blank gap on the left. Turn the asterisk on under More → Advanced → Show asterisk in menu bar if you want the `✻` prefix.

## Auto-switch from the extra

More → Settings:

- **Auto-switch accounts**: run the engine in the extra (no extra `cswap auto` terminal).
- **Auto-switch threshold**: 80 / 90 / 95 / 98%.
- **Auto-switch strategy**: Most quota left (`best`) or Soonest weekly reset (`consume-first`).

Policy lives in `settings.json` and is shared with the CLI. The on/off toggle lives in `menubar_settings.json`. See [Auto-switch](Auto-Switch).

## Notifications

Switches, quarantines, all-accounts-exhausted, and kickoff results show as macOS notifications. Clicking the extra still opens the popover, not a menu.

## Place it next to Claude’s extra

macOS has no API to pin an extra next to another app. Cmd-drag the extra where you want it. The position is remembered (`com.cswap.menubar`).

## Dark Mode

The popover and the widget follow System Settings → Appearance. If the extra looks light while the rest of the Mac is Dark, restart it (`launchctl kickstart` above) so it picks up the change.
