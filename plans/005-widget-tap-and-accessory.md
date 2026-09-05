# Plan 005: Widget tap-to-switch and accessory families

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, do **not** update `plans/README.md`.
>
> **Drift check (run first)**: `git diff --stat 5e4ffde..HEAD -- macos/CSwapWidget src/claude_swap/widget_snapshot.py src/claude_swap/menubar.py tests/test_widget_snapshot.py tests/test_menubar.py docs/widget.md`
> Expect 001 subtitle on `AccountCard`. STOP if `panel_accounts` / snapshot
> path / `RELOAD_NOTIFICATION` are gone.

## Status

- **Priority**: P2
- **Effort**: M
- **Risk**: MED
- **Depends on**: plans/001-org-names-on-extra.md
- **Category**: direction
- **Planned at**: commit `5e4ffde`, 2026-09-05

## Why this matters

The widget is `StaticConfiguration` with systemSmall/Medium/Large only. Taps
do nothing useful (host is `LSUIElement`). Snapshot JSON already has `num`.
The extra already switches by slot and stamps `lastSwitchAt`. After this
plan: accessory families render a compact glance; tapping an account writes
a command file the extra consumes and switches, same as a card click.

## Current state

- `macos/CSwapWidget/Widget/CSwapWidget.swift` — `StaticConfiguration`,
  families `[.systemSmall, .systemMedium, .systemLarge]`.
- `CSwapWidgetView.swift` — `AccountBlock` is display-only (001 may add
  subtitle).
- `Widget.entitlements` — sandbox + **read-only**
  `temporary-exception.files.home-relative-path.read-only` for
  `/Library/Application Support/cswap/`.
- Host `main.swift` — listens `com.cswap.widget.reload`, accessory policy.
  Host is also sandboxed (`Host.entitlements`) with **no** file exception.
- Python extra writes `widget-snapshot.json`; notification
  `com.cswap.widget.reload`.
- Extra switch path: `switch_to(str(num), json_output=True)` then
  `record_manual_switch` if `result["switched"]`.

macOS 14+ (project.yml `MACOSX_DEPLOYMENT_TARGET: "14.0"`). App Intents
in widgets are available.

## Commands you will need

| Purpose | Command | Expected on success |
|---------|---------|---------------------|
| Python tests | `uv run pytest tests/test_widget_snapshot.py tests/test_menubar.py -n auto` | all pass |
| Widget compile (optional) | `cswap widget --install` | app replaced; do not flip DEVELOPMENT_TEAM |

Signing: keep TeamIdentifier `KJ999FVUJ4` if the installed app has it
(`docs/widget.md`). Do not pick VirtualShield `5LHJJ5JW3C`.

## Suggested executor toolkit

- TDD for the Python command-file helpers.
- After Swift edits, regenerate xcodeproj only if you change `project.yml`
  (`xcodegen`). New `.swift` files under `Widget/` are picked up by the
  existing `sources: path: Widget` glob.

## Scope

**In scope**:
- `macos/CSwapWidget/Widget/Widget.entitlements` (read-write exception)
- `macos/CSwapWidget/Widget/*.swift` (new intent file allowed)
- `macos/CSwapWidget/project.yml` only if a new target is required
  (prefer **no** new target: App Intent in the widget extension)
- `src/claude_swap/widget_snapshot.py` (command path + consume helper)
- `src/claude_swap/menubar.py` (poll consume helper on refresh)
- `tests/test_widget_snapshot.py`
- `tests/test_menubar.py` (consume → should_notify / record_manual_switch
  wiring if you add a pure helper)
- `docs/widget.md`

**Out of scope**:
- App Groups / Developer Portal
- Changing bundle id `com.cswap.widget`
- Switching without going through extra `switch_to` (do not have Swift
  write Keychain)
- Push / wiki
- Plan 004 settings page

## Git workflow

- Branch: `advisor/005-widget-tap-and-accessory`
- Commit: `feat(macos): widget tap switches accounts; accessory families`
- Do NOT push.

## Steps

### Step 1: Drift check

001 subtitle should be on cards. Entitlements still read-only.

### Step 2: Python command file (TDD)

In `widget_snapshot.py` (next to snapshot path):

```python
COMMAND_FILENAME = "widget-command.json"

def default_command_path(home: Path | None = None) -> Path:
    """~/Library/Application Support/cswap/widget-command.json"""

def parse_switch_command(raw: dict) -> str | None:
    """Return slot num string if op=='switch' and num is a non-empty str/int.
    Else None. Never raise on bad JSON shape.
    """

def consume_switch_command(path: Path | None = None) -> str | None:
    """Read, delete, return num. Missing file → None.
    Unreadable/invalid → delete if possible, return None (do not retry a poison file).
    """
```

Tests in `tests/test_widget_snapshot.py`: happy path, missing file, bad
JSON, missing num, `op` not switch. Use `tmp_path`.

**Verify**: RED then GREEN. Do not write extra glue yet.

### Step 3: Extra consumes the command

On the extra’s existing refresh tick (same function that publishes the
widget snapshot), call `consume_switch_command()`. If num is not None,
reuse `_switch_from_panel(num)` (json switch, close_panel optional —
widget should **not** require the popover to be open; call
`_run_switch` / `_finish_manual_switch` with `close_panel=False`).
Stamp `record_manual_switch` only when `should_notify_manual_switch`.

If the extra is not running, the command file waits; that is OK.

Tests: a pure wrapper `apply_widget_switch_num(num) -> None` is optional;
prefer a unit test that `parse_switch_command` + existing
`should_notify_manual_switch` / `should_dismiss_panel_after_switch` stay
consistent. A wiring grep test that `rebuild_menu` or `_refresh` calls
`consume_switch_command` is acceptable (the repo already uses wiring
greps when AppKit cannot run).

**Verify**: menubar + widget_snapshot tests pass.

### Step 4: Entitlement + App Intent + tap UI

Change `Widget.entitlements` read-only key to:

`com.apple.security.temporary-exception.files.home-relative-path.read-write`

same path `/Library/Application Support/cswap/`.

Add `SwitchAccountIntent.swift` in `Widget/`:

- `AppIntent` with `@Parameter var num: String`
- `title`: “Switch cswap account”
- `perform()` writes `{"op":"switch","num": num, "at": Date().timeIntervalSince1970}`
  atomically to `realHomeDirectory()/Library/Application Support/cswap/widget-command.json`
  (reuse `realHomeDirectory()` from `Snapshot.swift`; if needed, move it to
  a small shared file in `Widget/`).
- Do not use App Groups.

`CSwapWidgetView.swift`: wrap each `AccountBlock` in
`Button(intent: SwitchAccountIntent(num: account.num))` so a tap switches.
Disabled cards: no button (or button disabled). Keep the visual layout.

Do not switch from `getTimeline` (that would fire without a tap).

### Step 5: Accessory families

`CSwapUsageWidget.supportedFamilies` add `.accessoryRectangular` and
`.accessoryCircular` (macOS 14 WidgetKit).

`CSwapWidgetView`:
- `accessoryCircular`: active account 5h pct as a single number (or `—`)
- `accessoryRectangular`: active title + 5h/7d pcts on one line

Use `family == .accessoryCircular` / `.accessoryRectangular`. Empty
snapshot: short “cswap” text.

### Step 6: Docs + optional install

`docs/widget.md`: families list; tap writes command file; extra must be
running; entitlement is read-write on that directory only.

If `cswap widget --install` is run, do not change DEVELOPMENT_TEAM away
from the installed app’s team.

Commit.

**Verify**: Python tests pass. `git diff --stat` in scope.

## Test plan

- parse/consume command file cases
- wiring that extra refresh consumes the file
- existing snapshot tests still pass
- Pattern: `tests/test_widget_snapshot.py`

Swift UI/intents are not covered by pytest; the human verifies with
`cswap widget --install` and a tap.

## Done criteria

- [ ] Python tests above pass
- [ ] Widget entitlements are read-write only for `cswap/` under Application Support
- [ ] Tap path cannot write credentials or Keychain
- [ ] Accessory families in `supportedFamilies`
- [ ] Extra uses existing `switch_to` + `record_manual_switch`
- [ ] No files outside scope

## STOP conditions

- 001 missing (no `num` / subtitle on cards).
- You would add an App Group or change bundle ids.
- Signing would switch to team `5LHJJ5JW3C`.
- App Intent cannot write the file even with read-write exception: STOP and
  report; do not invent a URL scheme in this plan.

## Maintenance notes

- Reviewer: poison-file delete is required or a bad tap loops forever.
- Extra must ignore commands for unknown slots (`switch_to` error path
  already alerts; keep popover closed).
- Timeline must not call the intent.
