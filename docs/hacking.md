# Hacking

## Clone and install

The extra and widget expect an **editable** install so Python loads `src/claude_swap` from this tree (the widget builder also walks parents looking for `macos/CSwapWidget`).

```bash
git clone https://github.com/mar3co/claude-swap.git
cd claude-swap
uv tool install --editable '.[menubar]'
uv sync   # dev extras: pytest, etc.
```

`uv tool install claude-swap` from PyPI is the upstream wheel. It will not see this checkout’s widget sources. `cswap upgrade` refuses PyPI when running from this tree; use `git pull` then `uv tool install --editable '.[menubar]'`.

## Run tests

```bash
uv run pytest
```

CI is `.github/workflows/ci.yml` (Ubuntu, Windows, macOS). See [Testing](testing.md).

## Restart the extra after a Python change

The LaunchAgent pins the `cswap` script; an editable install means that script already imports this tree. Restart the process:

```bash
launchctl kickstart -k "gui/$(id -u)/com.cswap.menubar"
```

Logs: `~/Library/Logs/com.cswap.menubar.{log,err}`.

The widget host is a compiled Swift app. After Swift or `project.yml` changes:

```bash
cswap widget --install
```

Derived data: `~/Library/Caches/cswap-widget`.

## Remotes and branches

| Remote | Repo |
| --- | --- |
| `origin` | `mar3co/claude-swap` (this fork) |
| `upstream` | `realiti4/claude-swap` |

Work lives on `feat/menubar-usage-bars` and is fast-forwarded to `origin/main` when we want the GitHub landing page updated. Default branch on the fork is `main`.

## Workspace

The parent `GitHub/` directory is **not** a git repo. Run git from `claude-swap/`.
