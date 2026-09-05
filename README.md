# claude-swap

Switch between multiple Claude Code accounts without logging out. Track 5-hour and 7-day usage, auto-rotate before you hit a limit, and run two accounts at once.

This is the [mar3co](https://github.com/mar3co/claude-swap) fork of [realiti4/claude-swap](https://github.com/realiti4/claude-swap). It keeps the CLI and TUI, and adds a native macOS menu bar extra, Desktop widget, and a scheduled 5-hour window kickoff.

**Users:** [Wiki](https://github.com/mar3co/claude-swap/wiki) (features, install, extra, widget, kickoff)  
**Developers:** [docs/](docs/README.md) (architecture, hacking, tests)

## Install

Needs Python 3.12+ and [Claude Code](https://docs.anthropic.com/en/docs/claude-code) already logged in.

This fork (menu bar extra, widget, kickoff):

```bash
git clone https://github.com/mar3co/claude-swap.git
cd claude-swap
uv tool install --editable '.[menubar]'
```

`cswap upgrade` on this editable checkout refuses PyPI (that wheel would drop the extra, widget, and kickoff). Update with `git pull`, then `uv tool install --editable '.[menubar]'`.

Upstream PyPI (no extra widget/kickoff from this fork):

```bash
# macOS (menu bar extra from upstream)
uv tool install 'claude-swap[menubar]'

# Linux / Windows, or CLI only
uv tool install claude-swap
```

`pipx install claude-swap` works too for the upstream wheel.

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

Walkthrough: [Getting started](https://github.com/mar3co/claude-swap/wiki/Getting-Started). Every feature: [Features](https://github.com/mar3co/claude-swap/wiki/Features).

## macOS extras

```bash
cswap menubar --install-service    # extra at login
cswap widget --install             # Desktop / Notification Center (this checkout + Xcode)
```

Click the extra for usage bars, then a card to switch. Auto-switch waits five minutes before it can move you again. More → Settings: auto-switch, consume-first (soonest weekly reset), 5-hour kickoff. Add the widget from Edit Widgets (search **cswap**).

[Menu bar](https://github.com/mar3co/claude-swap/wiki/Menu-Bar) · [Widget](https://github.com/mar3co/claude-swap/wiki/Desktop-Widget) · [Kickoff](https://github.com/mar3co/claude-swap/wiki/Five-Hour-Kickoff)

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

`cswap help` lists everything. [CLI reference](https://github.com/mar3co/claude-swap/wiki/CLI-Reference).

<img src="assets/tui-watch.png" width="760" alt="cswap watch: live 5h and 7d usage bars for every account">

## License

MIT. Upstream: [realiti4/claude-swap](https://github.com/realiti4/claude-swap).
