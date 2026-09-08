# Architecture

```
                    ┌─────────────┐
                    │ Claude Code │  default login in ~/.claude
                    └──────▲──────┘
                           │ engine writes credentials
        ┌──────────────────┼──────────────────┐
        │                  │                  │
   openswap CLI         AutoSwitchEngine    rumps extra
   (cli.py)          (autoswitch.py)     (menubar.py)
        │                  │                  │
        └────────┬─────────┴────────┬─────────┘
                 │                  │
            engine.Engine         settings.json
            (engine/)             autoswitch_state.json
                 │
            usage_store.py
                 │
                 └──── menubar extra writes widget-snapshot.json
                                    │
                                    ▼
                           OpenSwap.app (Swift)
                           WidgetKit extension
```

## Ownership

| Concern | Module | Notes |
| --- | --- | --- |
| Accounts, swap, credentials | `engine/` (`Engine` façade) | Extra, autoswitch, kickoff, and CLI `list`/`status`/`switch` call only the public façade. `switcher.py` is a one-release shim (`ClaudeAccountSwitcher` is `Engine`). |
| Live Claude Code store | `engine/live.py` | Keychain `"Claude Code-credentials"` / `"Claude Code"`; degraded vs empty |
| Roster + backup Keychain | `engine/slots.py` | `sequence.json`; backups service `"openswap"`, account `account-{n}-{email}` |
| Identity | `engine/identity.py` | `(email, organizationUuid)` |
| Consume | `engine/consume.py` | One-time refresh CAS + unclaimed stash |
| Switch / capture | `engine/switch.py` | Classify outgoing live bytes before write |
| Idle-slot kickoff profile | `engine/session_profile.py` | Isolated `CLAUDE_CONFIG_DIR`; live kickoff is `claude -p` in place |
| Snapshot assembler | `engine/snapshot.py` | Store-only (`fetch=set()`) is roster-only: **does not read idle or active-slot backup credentials**. Unread idle is not `USAGE_NO_CREDENTIALS`. At most one live credential read per snapshot. |
| Auto-switch policy | `autoswitch.py` | UI-agnostic events; CLI and extra host it |
| Shared policy knobs | `settings.py` | `autoswitch.*` in `settings.json` |
| Extra display knobs | `menubar.MenuBarSettings` | `menubar_settings.json` only |
| Popover UI | `menubar_panel.py` | AppKit, imported after rumps |
| 5h kickoff policy | `kickoff.py` | Pure; extra decides *when* |
| Session `openswap run` | `session.py` | Must not POSIX-`exec` the extra |
| Widget JSON | `widget_snapshot.py` | Extra writes cards plus combined remaining; extension reads |
| Widget build | `widget_install.py` | `xcodebuild` + LaunchAgent |

The extra is a thin shell. It must not re-implement quota math, ranking, or credential writes. It must not call `_get_current_account`, `_account_kind`, or `_get_sequence_data`; kind and live `(email, orgUuid)` are on the snapshot / `Engine.live_identity`.

Usage fetch stays store-paced (`fetch=set()` while autoswitch is hosted). A leftover `claude-swap` backup Keychain item is copied once into `openswap` at Engine construct (see `migrations.migrate_claude_swap_backup_items`). Windows Credential Manager is not on the macOS hot path; `.enc` is locked-Keychain fallback only.

MIT / Cetinkol remains on `LICENSE` while inherited files (`oauth.py`, parts of `credentials.py`) remain.

## Data on disk (macOS)

| Path | Who |
| --- | --- |
| `~/Library/Application Support/OpenSwap/settings.json` | CLI + extra (policy). First run moves `~/.claude-swap-backup` here |
| `~/Library/Application Support/OpenSwap/menubar_settings.json` | Extra (title, auto on/off, kickoff) |
| `~/Library/Application Support/OpenSwap/autoswitch_state.json` | Engine (cooldown, last switch, quarantine). Extra stamps `lastSwitchAt` after a hand switch |
| `~/Library/Application Support/OpenSwap/widget-snapshot.json` | Extra → widget |
| `~/Library/LaunchAgents/com.opensoft.openswap.menubar.plist` | Extra service |
| `~/Library/LaunchAgents/com.opensoft.openswap.widget.plist` | Widget host |
| `~/Applications/OpenSwap.app` | Signed WidgetKit host |

Credentials on macOS are Keychain, not files in the backup dir.

## Product surface

OpenSwap ships for macOS (extra, widget, kickoff, Keychain). The engine still has Windows/Linux branches from upstream; we do not promise those platforms. API-key slots (`openswap add-token`, extra → Add account) are first-class to switch to. They have no 5h/7d quota, so kickoff and autoswitch skip them unless `autoswitch.includeApiKeyAccounts` is on. `openswap run` is OAuth-only.

## Constraints we keep

- Do not change the user’s default `~/.claude` login except via `switcher` (kickoff pings the live login **in place**).
- Do not `os.exec*` the extra process (`kickoff` uses returning `subprocess.run`).
- Do not put WidgetKit inside the Python extra (impossible); snapshot + Darwin notification + host `.app` is the split.
- Do not default `show_icon` on. Compact the extra when the asterisk is off ([Menu bar](menubar.md)).
