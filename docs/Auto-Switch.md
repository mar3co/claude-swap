# Auto-switch

cswap can watch usage and change the default Claude Code login before you hit a rate limit. The CLI (`cswap auto`) and the macOS extra share the same engine, state file, and `autoswitch.*` settings.

## Turn it on

```bash
cswap auto                          # foreground, polls every 60s
cswap auto --threshold 80
cswap auto --model Fable            # also honor that model's weekly limit
cswap auto --once                   # one check, for cron
cswap auto --dry-run
cswap auto --strategy consume-first
```

From the extra: More → Settings → **Auto-switch accounts**.

A LaunchAgent extra with auto-switch on is the usual “leave it running” setup on macOS. You do not also need a `cswap auto` terminal.

## Strategies

Set with `cswap auto --strategy …`, `cswap config set autoswitch.strategy …`, or More → Settings → Auto-switch strategy.

| Strategy | When it moves | Who it picks |
| --- | --- | --- |
| **best** (default) | Active account’s binding 5h or 7d window reaches the threshold (90%) | Most remaining quota |
| **consume-first** | Proactive, even below the threshold | Soonest **weekly** (`7d`) reset, with room to spare |

`consume-first` is use-it-or-lose-it. Weekly windows do not recycle as fast as the 5-hour session, so the engine ranks by the **7-day** reset, not the 5-hour countdown you might see in the popover.

Example: personal resets its week in 3 days, Ads Online in 2 hours. `best` stays on personal until it is ~90% used. `consume-first` prefers Ads Online so that weekly quota is spent before it expires.

The popover’s “2 hours” on a 7d / Fable row is that weekly clock. The 5h row is the session window.

## Threshold, cooldown, hysteresis

Defaults:

| Setting | Default | Meaning |
| --- | --- | --- |
| `autoswitch.threshold` | 90 | Switch when the binding window reaches this percent |
| `autoswitch.cooldownSeconds` | 300 | Minimum seconds between proactive switches |
| `autoswitch.hysteresisPct` | 10 | Target must beat the active account by this many percent |
| `autoswitch.intervalSeconds` | 60 | CLI poll interval |

A candidate must itself sit **below** the threshold (never land somewhere that would fire again next tick). Two accounts hovering at the line will not ping-pong.

## Per-model weekly limits

By default only the account-wide 5h / 7d windows drive switching. If you burn a model’s weekly limit first (for example Fable):

```bash
cswap auto --model Fable
cswap config set autoswitch.model Fable
cswap config set autoswitch.model Fable,Opus
cswap config set autoswitch.model all
```

Names are Anthropic `display_name`s, case-insensitive. They appear as extra rows in `cswap list` and in the popover.

## Safety

- Switches take the same credential locks Claude Code uses, so a swap never collides with a token refresh.
- Failed usage fetches keep the last-known numbers and back off. An expired token on an idle machine makes the engine **hold**, not fail over (Claude Code refreshes on your next message).
- A dead refresh token quarantines that slot until you log in and `cswap add --slot N`, or import a known-good backup.
- API-key accounts are skipped unless `autoswitch.includeApiKeyAccounts` is true.
- Disabled accounts (`cswap disable`) are out of rotation.

## Cron / `--once`

Exit codes: `0` switched, `1` error, `2` nothing to do, `3` blocked (no viable target).

```bash
*/5 * * * * cswap auto --once --json >> ~/.cswap-auto.log 2>&1
```

`--json` on `cswap auto` is an event stream (one object per line): `poll`, `switch`, `no-switch`, `account-quarantined`, `all-exhausted`, `error`. Ignore unknown kinds.

## Shared files

| File | Role |
| --- | --- |
| `settings.json` | `autoswitch.*` policy (CLI and extra) |
| `autoswitch_state.json` | cooldown, last switch, quarantines; delete to reset |
| `menubar_settings.json` | extra-only: auto on/off, title, kickoff |

See [Configuration](Configuration).
