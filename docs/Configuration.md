# Configuration

Two JSON files in the backup directory. You rarely need to edit them by hand.

| File | Who uses it | What it holds |
| --- | --- | --- |
| `settings.json` | CLI, TUI, extra | `autoswitch.*` and `ui.theme` |
| `menubar_settings.json` | Extra only | Title, refresh, auto on/off, kickoff, asterisk |

Backup directory: `~/.claude-swap-backup/` on macOS and Windows. On Linux/WSL: `${XDG_DATA_HOME:-~/.local/share}/claude-swap/`.

```bash
cswap config                 # effective values (`(default)` = not set)
cswap config get autoswitch.threshold
cswap config set autoswitch.threshold 80
cswap config set autoswitch.strategy consume-first
cswap config unset autoswitch.threshold
cswap config path
cswap config --help          # every key, range, default
```

Flags on `cswap auto` override `settings.json` for that process.

## `autoswitch.*`

| Key | Default | Notes |
| --- | --- | --- |
| `autoswitch.threshold` | 90 | Binding 5h/7d percent that triggers a look for a better account |
| `autoswitch.strategy` | `best` | `best` or `consume-first` (soonest weekly reset) |
| `autoswitch.intervalSeconds` | 60 | CLI `cswap auto` poll interval |
| `autoswitch.cooldownSeconds` | 300 | Minimum gap between proactive switches |
| `autoswitch.hysteresisPct` | 10 | Target must beat the active account by this many percent |
| `autoswitch.model` | (unset) | `Fable`, `Fable,Opus`, or `all` |
| `autoswitch.includeApiKeyAccounts` | false | Allow rotating onto `sk-ant-api…` slots |
| `autoswitch.unhealthyTicks` | 3 | Consecutive failed polls before unhealthy |

See [Auto-switch](Auto-Switch.md).

## `ui.theme`

`dark`, `light`, or `auto` (follow the terminal). This is the TUI/CLI theme, not the extra’s Dark Mode (the extra follows System Settings → Appearance).

```bash
cswap config set ui.theme dark
```

## Extra display (`menubar_settings.json`)

Changed from More → Settings (and Advanced):

- Account name in the title
- Title percentages (`off` / 5h / 7d / both)
- Model limits in the title
- Refresh interval (30s / 60s / 5 min)
- Auto-switch on/off (policy still comes from `settings.json`)
- 5-hour kickoff on/off and time
- Optional `✻` in the title (off by default)

## Other files in the backup directory

| File | Role |
| --- | --- |
| `autoswitch_state.json` | Last switch, cooldown, quarantines; delete to reset |
| `sequence.json` | Slot order |
| `claude-swap.log` | Switch history (More → Switch history) |
| `sessions/` | Session-mode profiles (`cswap run`) |
| `credentials/` | File-based credentials on Linux/Windows |

macOS credentials live in the Keychain, not in that folder.
