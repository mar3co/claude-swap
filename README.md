# claude-swap

Switch between multiple Claude Code accounts without logging out. Track 5-hour and 7-day usage, auto-rotate before you hit a limit, and run two accounts at once.

This is the [mar3co](https://github.com/mar3co/claude-swap) fork of [realiti4/claude-swap](https://github.com/realiti4/claude-swap). It keeps the CLI and TUI, and adds a native macOS menu bar extra, Desktop widget, and a scheduled 5-hour window kickoff.

**User guide:** [docs/](docs/README.md) · [Wiki](https://github.com/mar3co/claude-swap/wiki) · [site](https://mar3co.github.io/claude-swap/)

## Install

Needs Python 3.12+ and [Claude Code](https://docs.anthropic.com/en/docs/claude-code) already logged in.

```bash
# macOS (menu bar extra)
uv tool install 'claude-swap[menubar]'

# Linux / Windows, or CLI only
uv tool install claude-swap
```

From this fork (menu bar, widget, kickoff):

```bash
git clone https://github.com/mar3co/claude-swap.git
cd claude-swap
uv tool install --editable '.[menubar]'
```

`pipx install claude-swap` works too. Upgrade with `cswap upgrade`.

## Quick start

```bash
cswap add              # save the account you are logged into
# log into another Claude account, then:
cswap add
cswap list             # 5h / 7d usage for every account
cswap switch           # rotate
cswap switch 2         # jump to a slot, email, or alias
cswap auto             # switch for you before a window hits 90%
```

Do not run `/logout` before `cswap add`: current Claude Code may revoke the refresh token you are about to save.

Full walkthrough: [Getting started](docs/Getting-Started.md).

## macOS extras

Keep the extra running after you close the terminal:

```bash
cswap menubar --install-service
```

Click the extra for a usage popover (bars, percents, time until reset). More → Settings turns on auto-switch, consume-first (soonest weekly reset), and the 5-hour kickoff.

Desktop / Notification Center widget (needs this git checkout and Xcode):

```bash
cswap widget --install
```

Then Edit Widgets and add **cswap**. The extra must be running so the widget has live numbers.

Guides: [Menu bar](docs/Menu-Bar.md) · [Desktop widget](docs/Desktop-Widget.md) · [5-hour kickoff](docs/Five-Hour-Kickoff.md)

## Commands

| Command | What it does |
| --- | --- |
| `cswap` / `cswap tui` | Full-screen dashboard |
| `cswap watch` | Dashboard, live monitor |
| `cswap list` | Accounts with 5h / 7d usage |
| `cswap switch` / `cswap switch 2` | Rotate, or jump to a slot |
| `cswap auto` | Background rotation near rate limits |
| `cswap run 2` | Claude Code as that account, this terminal only |
| `cswap config` | Shared settings (`autoswitch.*`) |
| `cswap menubar` | macOS extra |
| `cswap widget --install` | macOS widget |

`cswap help` lists everything. Details: [CLI reference](docs/CLI-Reference.md).

<img src="assets/tui-watch.png" width="760" alt="cswap watch: live 5h and 7d usage bars for every account">

## Documentation

The [user guide](docs/README.md) (also on the [wiki](https://github.com/mar3co/claude-swap/wiki) and [GitHub Pages](https://mar3co.github.io/claude-swap/)):

- [Getting started](docs/Getting-Started.md)
- [Accounts](docs/Accounts.md)
- [Auto-switch](docs/Auto-Switch.md)
- [Sessions and directory maps](docs/Sessions.md)
- [Menu bar](docs/Menu-Bar.md)
- [Desktop widget](docs/Desktop-Widget.md)
- [5-hour kickoff](docs/Five-Hour-Kickoff.md)
- [Configuration](docs/Configuration.md)
- [Backup](docs/Backup.md)
- [Troubleshooting](docs/Troubleshooting.md)

## License

MIT. Upstream: [realiti4/claude-swap](https://github.com/realiti4/claude-swap).
