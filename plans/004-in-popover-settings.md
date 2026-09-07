# Plan 004: Move Settings into the popover

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, do **not** update `plans/README.md`.
>
> **Drift check (run first)**: `git diff --stat 5e4ffde..HEAD -- src/openswap/menubar.py src/openswap/menubar_panel.py tests/test_menubar.py docs/menubar.md docs/testing.md`
> Expect 001–003 changes. STOP if `_more` / `_settings_menu` / `AUTO_STRATEGY_CHOICES`
> are gone.

## Status

- **Priority**: P2
- **Effort**: M
- **Risk**: MED
- **Depends on**: plans/001-org-names-on-extra.md, plans/003-live-claude-sessions.md
- **Category**: direction
- **Planned at**: commit `5e4ffde`, 2026-09-05

## Why this matters

More opens an `NSMenu`. Transient vs ApplicationDefined, `_menu_open`, and
the 12s leave-delay exist so that menu does not kill the popover. Settings
(strategy, kickoff, title, asterisk) still live in nested rumps menus.
After this plan, a Settings **page inside the popover** toggles those
knobs with the same AppKit controls as Auto-switch. More keeps Add /
Remove / Disable / History / Refresh / Quit only.

## Current state

- `menubar_panel.py` `_build`: header Auto-switch NSSwitch; footer
  Rotate, Best, More. `_more` sets `_menu_open` and calls `_on_more`.
- `menubar.py` `_settings_menu`: Show account name, Title percentage,
  model limits, Refresh interval, Auto-switch, threshold, strategy,
  kickoff, Advanced asterisk.
- `AUTO_STRATEGY_CHOICES`, `AUTO_THRESHOLD_CHOICES`, `TITLE_PCT_CHOICES`,
  `REFRESH_CHOICES` already exist.
- Tests cannot import AppKit. Put page model in `menubar.py`.

Do not move Add-account (needs text prompt / rumps.alert) into the
popover.

## Commands you will need

| Purpose | Command | Expected on success |
|---------|---------|---------------------|
| Tests | `uv run pytest tests/test_menubar.py -n auto` | all pass |

## Suggested executor toolkit

- TDD for the pure page model.
- Keep `NSPopoverBehaviorApplicationDefined` and leave-delay; Settings page
  must not open an NSMenu.

## Scope

**In scope**:
- `src/openswap/menubar.py`
- `src/openswap/menubar_panel.py`
- `tests/test_menubar.py`
- `docs/menubar.md`
- `docs/testing.md` (exercise Settings page instead of More → Settings)

**Out of scope**:
- Add / remove / disable / token UI in the popover
- Replacing rumps entirely
- Kickoff custom-time prompt may still use `rumps.alert` (already does)
- Widget
- Push / wiki

## Git workflow

- Branch: `advisor/004-in-popover-settings`
- Commit: `feat(menubar): put settings on a popover page`
- Do NOT push.

## Steps

### Step 1: Drift check

001 subtitle, 003 running line, 002 hold line (if present) must be preserved
in `_build` height math.

### Step 2: Pure settings-page model (TDD)

In `menubar.py`:

```python
SETTINGS_PAGE = "settings"
MAIN_PAGE = "main"

def settings_page_rows(settings: MenuBarSettings, *, strategy: str, threshold: float) -> list[dict]:
    """Rows for the in-popover settings page. No AppKit.

    Each dict: {"kind": "toggle"|"choice"|"group", "id": str, "label": str, ...}
    Required ids:
      show_account_name (toggle, bool)
      title_pct (choice, TITLE_PCT_CHOICES, labels already used in _settings_menu)
      title_scoped (toggle)
      refresh_interval (choice, REFRESH_CHOICES)
      auto_switch_enabled (toggle)  # duplicate of header switch is OK; keep both in sync
      threshold (choice, AUTO_THRESHOLD_CHOICES)
      strategy (choice, AUTO_STRATEGY_CHOICES)
      kickoff_enabled (toggle)
      kickoff_time (label-only + id 'kickoff_custom' for the existing Custom… alert)
      show_icon (toggle)
    """
```

Tests: ids present; strategy values match `AUTO_STRATEGY_CHOICES`;
kickoff_time label uses `format_kickoff_time`.

**Verify**: RED then GREEN for this helper only.

### Step 3: Panel page switch

`MenuBarPanel`:
- `self._page = "main"`
- Footer on main: Rotate, Best, **Settings**, More (More stays).
- Settings button sets `_page = "settings"` and `_reload()` (this is a
  button action, not a live timer rebuild — allowed; do not reload on
  the 1s usage timer while Settings is showing, same rule as “do not
  reload an open popover mid-click”).
- Settings page: Back button (`_page = "main"`), then render rows:
  - toggles: NSSwitch like Auto-switch
  - choices: small NSButton radio or a row of labeled buttons; checked
    state from current settings
  - kickoff time: display current time + button “Change…” that calls
    existing `on_kickoff_custom`
- Height: compute from row count; keep PANEL_WIDTH = 312.
- Click-outside and leave-delay still apply. Settings page is still
  inside the popover (`_pointer_over_ui` unchanged).
- Do **not** set `_menu_open` for the Settings page.

Wire callbacks to existing extra methods (`on_toggle_autoswitch`,
`_make_strategy`, `_make_threshold`, `on_toggle_kickoff`,
`on_toggle_icon`, `on_toggle_name`, `_make_title_pct`,
`on_toggle_scoped`, `_make_interval`). Add a panel constructor/getter
bag if the panel cannot reach those methods; follow the existing
`_on_toggle_auto` / `_on_switch` pattern.

`_settings_menu` in rumps: remove the knobs that moved, **or** leave them
as a hidden duplicate. Prefer **remove** from the rumps Settings submenu
so there is one UI. If the rumps Settings menu becomes empty, delete it
from More.

Keep More: Add account, Disable/enable, Remove, Refresh credentials,
History, Refresh now, Quit.

**Verify**: `uv run pytest tests/test_menubar.py -n auto` passes. Add a
wiring test that `rebuild_menu` still does not `_panel.reload()` while
shown (existing test). Add a test that settings_page_rows ids are the
ones the panel will look up (string ids).

### Step 4: Docs

`docs/menubar.md`: Settings is an in-popover page; More is overflow only.
Leave-delay / ApplicationDefined / first-click cards unchanged.

`docs/testing.md`: exercise Settings page (strategy, kickoff, asterisk)
without expecting More to dismiss the box.

### Step 5: Commit

**Verify**: in-scope only.

## Test plan

- `settings_page_rows` complete ids + choice values
- existing first-click / no-reload / trailing header tests still pass
- Pattern: `tests/test_menubar.py` trailing_header_frames and panel wiring

## Done criteria

- [ ] Menubar tests pass
- [ ] Settings knobs available without NSMenu
- [ ] More still opens the overflow menu for Add/Remove/Quit
- [ ] Auto-switch header switch still works
- [ ] 001 subtitle, 002 hold line (if any), 003 running line still laid out
- [ ] No files outside scope

## STOP conditions

- 001/003 missing from HEAD.
- You would reload the popover on the usage timer while Settings is open
  (that swallows clicks; existing rule).
- You move Add-account into the popover.
- AppKit required in `tests/test_menubar.py`.

## Maintenance notes

- Reviewer: click-outside while Settings is open must close the popover
  (same as main). Back must not close the popover.
- Kickoff custom time stays `rumps.alert` on purpose (YAGNI date picker).
