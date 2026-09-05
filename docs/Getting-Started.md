# Getting started

## Requirements

- Python 3.12 or newer
- [Claude Code](https://docs.anthropic.com/en/docs/claude-code) installed and logged in
- macOS extras: the `menubar` extra (`rumps`), and for the widget Xcode plus an Apple Development signing identity

## Install

### From this fork (recommended on macOS)

The menu bar extra, Desktop widget, and 5-hour kickoff live in this checkout:

```bash
git clone https://github.com/mar3co/claude-swap.git
cd claude-swap
uv tool install --editable '.[menubar]'
```

An editable install keeps `cswap` pointed at the clone, so `cswap widget --install` can find `macos/CSwapWidget`.

### From PyPI (CLI / TUI, or upstream menu bar)

```bash
uv tool install 'claude-swap[menubar]'   # macOS extra
uv tool install claude-swap              # CLI only
```

`pipx install claude-swap` works the same way.

### Upgrade

```bash
cswap upgrade
# or
uv tool upgrade claude-swap
```

After an upgrade, restart the extra so it loads the new code:

```bash
launchctl kickstart -k "gui/$(id -u)/com.cswap.menubar"
```

## Save your accounts

1. Log into Claude Code with the first account.
2. Run `cswap add`.
3. Log into Claude Code with the next account. Do **not** run `/logout` first: current Claude Code may revoke the refresh token you still need.
4. Run `cswap add` again.
5. Repeat for each account.

Give a slot a short name if you want:

```bash
cswap add --alias work
cswap alias 2 personal
```

Check what you have:

```bash
cswap list
cswap status
```

`cswap list` is the dashboard: 5-hour and 7-day usage and reset times for every slot.

## Switch

```bash
cswap switch                 # next account
cswap switch 2               # slot number
cswap switch user@example.com
cswap switch work            # alias
cswap switch --strategy best # most quota left
```

You usually do not need to restart Claude Code. On Linux and Windows the next message picks up the new login. On macOS, Keychain is cached for about 30 seconds; restart Claude Code (or the VS Code extension tab) only if you want it instantly.

## Auto-rotate

```bash
cswap auto
```

When the active account’s 5-hour or 7-day window reaches 90%, cswap moves you to the account with the most quota left. Turn this on from the extra instead if you prefer: More → Settings → Auto-switch accounts.

See [Auto-switch](Auto-Switch.md).

## macOS extra

```bash
cswap menubar --install-service
```

That starts the extra now and at every login. Click it for usage bars. See [Menu bar](Menu-Bar.md).

## Next

- [Accounts](Accounts.md)
- [Sessions](Sessions.md) if you want two accounts working at once
- [Desktop widget](Desktop-Widget.md)
- [Troubleshooting](Troubleshooting.md) if `cswap add` or a switch fails
