# Architecture

```
                    ┌─────────────┐
                    │ Claude Code │  default login in ~/.claude
                    └──────▲──────┘
                           │ switcher writes credentials
        ┌──────────────────┼──────────────────┐
        │                  │                  │
   cswap CLI/TUI     AutoSwitchEngine    rumps extra
   (cli.py, tui/)    (autoswitch.py)     (menubar.py)
        │                  │                  │
        └────────┬─────────┴────────┬─────────┘
                 │                  │
         ClaudeAccountSwitcher    settings.json
         (switcher.py)            autoswitch_state.json
                 │
            usage_store.py
                 │
                 └──── menubar extra writes widget-snapshot.json
                                    │
                                    ▼
                           cswap Widget.app (Swift)
                           WidgetKit extension
```

## Ownership

| Concern | Module | Notes |
| --- | --- | --- |
| Accounts, swap, credentials | `switcher.py` | One implementation; CLI and extra call it |
| Auto-switch policy | `autoswitch.py` | UI-agnostic events; CLI and extra host it |
| Shared policy knobs | `settings.py` | `autoswitch.*` in `settings.json` |
| Extra display knobs | `menubar.MenuBarSettings` | `menubar_settings.json` only |
| Popover UI | `menubar_panel.py` | AppKit, imported after rumps |
| 5h kickoff policy | `kickoff.py` | Pure; extra decides *when* |
| Session `cswap run` | `session.py` | Must not POSIX-`exec` the extra |
| Widget JSON | `widget_snapshot.py` | Extra writes; extension reads |
| Widget build | `widget_install.py` | `xcodebuild` + LaunchAgent |

The extra is a thin shell. It must not re-implement quota math, ranking, or credential writes.

## Data on disk (macOS)

| Path | Who |
| --- | --- |
| `~/.claude-swap-backup/settings.json` | CLI + extra (policy) |
| `~/.claude-swap-backup/menubar_settings.json` | Extra (title, auto on/off, kickoff) |
| `~/.claude-swap-backup/autoswitch_state.json` | Engine (cooldown, last switch, quarantine) |
| `~/Library/Application Support/cswap/widget-snapshot.json` | Extra → widget |
| `~/Library/LaunchAgents/com.cswap.menubar.plist` | Extra service |
| `~/Library/LaunchAgents/com.cswap.widget.plist` | Widget host |
| `~/Applications/cswap Widget.app` | Signed WidgetKit host |

Credentials on macOS are Keychain, not files in the backup dir.

## Constraints we keep

- Do not change the user’s default `~/.claude` login except via `switcher` (kickoff pings the live login **in place**).
- Do not `os.exec*` the extra process (`kickoff` uses returning `subprocess.run`).
- Do not put WidgetKit inside the Python extra (impossible); snapshot + Darwin notification + host `.app` is the split.
- Do not default `show_icon` on. Compact the extra when the asterisk is off ([Menu bar](menubar.md)).
