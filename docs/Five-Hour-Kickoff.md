# 5-hour kickoff

Anthropic’s 5-hour session window only starts when the account is used. If you want that window to open at a set local time (for example 4:00 AM so a 9:00 AM “reset” is already running), the extra can ping idle accounts once per local day.

This is a **start** time, not “subtract 5 hours from 9:00.” If you care about a 9:00 AM window, schedule 4:00 AM.

## Turn it on

More → Settings → **Start 5-hour window** → Enabled, then pick a time (or Custom…).

Default time is 7:00 AM local. It will not fire before that clock on the day you enable it.

## What it does

- At most **once per local day**
- Sends `claude -p ok` for each **idle OAuth** account
- Skips API-key accounts
- Skips accounts whose 5-hour window is still open (`resets_at` in the future)
- Idle accounts with a stale yesterday row (percent over 0, reset already passed) **are** pinged
- Does **not** change your default `~/.claude` login
- The live default login is pinged in place; other slots use a session profile (`CLAUDE_CONFIG_DIR`)
- A failed day stays due and retries after 5 minutes

The ping spends a little 5-hour and 7-day quota. That is inherent: opening the window is usage.

## Notifications

You get a notification with how many windows started, and which accounts failed.

## Off by default

Kickoff is extra-only (`menubar_settings.json`). There is no `cswap kickoff` CLI command.
