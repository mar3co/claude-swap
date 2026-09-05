# cswap documentation

Welcome. This is the user guide for **claude-swap** (`cswap`): a multi-account switcher for [Claude Code](https://docs.anthropic.com/en/docs/claude-code). The same pages are published on the [GitHub wiki](https://github.com/mar3co/claude-swap/wiki).

This wiki covers the [mar3co fork](https://github.com/mar3co/claude-swap), which includes the CLI and TUI from [upstream](https://github.com/realiti4/claude-swap) plus a native macOS menu bar extra, Desktop widget, and scheduled 5-hour window kickoff.

## Start here

| I want to… | Go to |
| --- | --- |
| Install and save my first accounts | [Getting started](Getting-Started) |
| Switch, alias, disable, or remove accounts | [Accounts](Accounts) |
| Rotate before I hit a rate limit | [Auto-switch](Auto-Switch) |
| Run two accounts at the same time | [Sessions](Sessions) |
| Use the macOS extra | [Menu bar](Menu-Bar) |
| Put usage on the Desktop | [Desktop widget](Desktop-Widget) |
| Open idle 5-hour windows on a schedule | [5-hour kickoff](Five-Hour-Kickoff) |
| Change threshold, strategy, theme | [Configuration](Configuration) |
| Move accounts between machines | [Backup](Backup) |
| Fix a stuck extra, token, or widget | [Troubleshooting](Troubleshooting) |
| Look up a command | [CLI reference](CLI-Reference) |

## How the pieces fit

```
Claude Code  ←  default login (~/.claude)
                 │
                 ├── cswap switch / auto     change the default login
                 ├── cswap run N             this terminal only (session)
                 ├── menu bar extra          popover + notifications + auto
                 └── Desktop widget          reads a snapshot the extra writes
```

Usage numbers come from Anthropic’s 5-hour session window and 7-day weekly window (plus per-model weekly limits such as Fable, when present). Auto-switch and the extra share the same `autoswitch.*` settings.

## Install (short)

```bash
git clone https://github.com/mar3co/claude-swap.git
cd claude-swap
uv tool install --editable '.[menubar]'
cswap add
```

Details, including Linux/Windows and upgrades, are in [Getting started](Getting-Started).
