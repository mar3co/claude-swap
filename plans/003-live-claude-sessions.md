# Plan 003: Show live Claude Code sessions after a switch

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, do **not** update `plans/README.md`.
>
> **Drift check (run first)**: `git diff --stat 5e4ffde..HEAD -- src/openswap/menubar.py src/openswap/menubar_panel.py src/openswap/process_detection.py tests/test_menubar.py docs/menubar.md`
> Expect 001 (and possibly 002) diffs in `menubar.py` / `menubar_panel.py`.
> STOP if `notification_copy_for_manual_switch` / `process_detection.get_running_instances`
> no longer exist.

## Status

- **Priority**: P1
- **Effort**: S
- **Risk**: LOW
- **Depends on**: plans/001-org-names-on-extra.md
- **Category**: direction
- **Planned at**: commit `5e4ffde`, 2026-09-05

## Why this matters

Every extra switch toasts “Restart Claude Code to apply now, or wait about
30 seconds” even when nothing is running. `openswap list` already prints
running instances via `get_running_instances()`. The extra never calls it.
After this plan, the toast omits the restart sentence when no live session
or IDE lock is found, and the popover shows a short “Claude Code is running
…” line when something is live. Do **not** kill or restart Claude Code.

## Current state

- `src/openswap/process_detection.py` — `ClaudeSession`, `IdeInstance`,
  `get_running_instances()` → `(list[ClaudeSession], list[IdeInstance])`.
  `list_sessions` is SCAN (skips unreadable). Extra display is a SCAN: using
  `get_running_instances` is correct. Do not use this for destructive
  guards.
- `src/openswap/switcher.py` ~5544 — CLI `list` prints “Running instances”.
  Extra does not.
- `src/openswap/menubar.py`
  - `notification_copy_for_event` switch body always:
    `"Restart Claude Code to apply now, or wait about 30 seconds."`
  - `notification_copy_for_manual_switch(dest_name)` same body.
- `menubar_panel.py` footer is Rotate / Best / More only.

## Commands you will need

| Purpose | Command | Expected on success |
|---------|---------|---------------------|
| Tests | `uv run pytest tests/test_menubar.py -n auto` | all pass |

## Suggested executor toolkit

- TDD. Pure helpers in `menubar.py`; panel only renders a string already
  on the snapshot.

## Scope

**In scope**:
- `src/openswap/menubar.py`
- `src/openswap/menubar_panel.py`
- `tests/test_menubar.py`
- `docs/menubar.md` (toast + optional running line)

**Out of scope**:
- `process_detection.py` behavior changes
- Killing, signaling, or restarting Claude Code
- `session.py` bootstrap / liveness guards (upstream #251 is not this plan)
- AppKit imports in tests
- Push / wiki

## Git workflow

- Branch: `advisor/003-live-claude-sessions`
- Commit: `feat(menubar): mention Claude Code only when it is running`
- Do NOT push.

## Steps

### Step 1: Drift check + 001 present

Card subtitle / 9-tuples from 001 must exist. If 002 added `hold_line`,
keep it; add `running_line` as a separate snapshot key.

### Step 2: Failing tests (TDD)

Add tiny fake session/ide objects (SimpleNamespace is fine) in
`tests/test_menubar.py`.

Helpers to specify (names may match):

```python
def format_running_line(sessions, ides) -> str | None:
    """None when both lists empty.
    One session: 'Claude Code is running in {cwd}.'
    Multiple: 'Claude Code is running ({n} sessions).'
    IDE only: 'Claude Code is running in {ide_name}.'
    Prefer session cwd (abbreviate to last two path parts) over listing PIDs.
    Never include pid numbers in the string.
    """

def switch_restart_hint(running: bool) -> str:
    """If running: 'Restart Claude Code to apply now, or wait about 30 seconds.'
    Else: ''  (empty; caller joins parts without a double space)
    """
```

Tests:
- empty → `format_running_line` is None; manual switch body is only
  destination context, **no** “Restart Claude Code”
- one session with cwd `/Users/x/proj` → line contains `proj`, no pid
- `notification_copy_for_manual_switch("Ads Online", running=False)` body
  does not contain `Restart`
- `running=True` contains `Restart` and `30 seconds`
- `notification_copy_for_event` for a non-dry-run switch event: pass
  `running=` through; default `running=True` would keep old tests passing
  **or** update existing event tests if they assert the full body.

Search `tests/test_menubar.py` for `Restart Claude Code` and update those
assertions explicitly.

**Verify**: RED.

### Step 3: Implement helpers and wire notifications

- Implement `format_running_line` and `switch_restart_hint` in `menubar.py`.
- `notification_copy_for_manual_switch(dest_name, *, running: bool = True)`
  — default True preserves old behavior for any missed call site; extra
  must pass the real value.
- `notification_copy_for_event(..., running: bool = True)` — append
  `switch_restart_hint(running)` instead of a hardcoded sentence.
- Extra refresh (same place that adapts the snapshot, ~`rebuild_menu` /
  `_refresh`): call `get_running_instances()` inside try/except; on
  error, treat as running=True (keep the hint; do not crash the extra).
  Store `running_line` and `claude_running` on the snapshot dict.
- Manual switch notify uses `claude_running`.
- Engine event notify uses the same flag.

Do not call `get_running_instances` from `panel_accounts` (keeps it pure).

**Verify**: menubar tests pass.

### Step 4: Draw the line on the popover

If `snapshot.get("running_line")`, draw muted text above the footer hairline
(`font_small`). Add `RUNNING_LINE_H = 16.0` to height when present. If 002
already added a hold line under the header, this one stays near the footer
so the two cannot be confused.

**Verify**: tests still pass (height math is not unit-tested; keep the
constant next to `FOOTER_H`).

### Step 5: Docs + commit

`docs/menubar.md`: toast includes the restart sentence only when a Claude
Code session or IDE lock is live; popover shows `running_line`.

## Test plan

- format_running_line empty / one / many / ide-only
- notification bodies with running True/False
- existing switch-copy tests updated
- Pattern: `notification_copy_for_manual_switch` tests in `test_menubar.py`

## Done criteria

- [ ] `uv run pytest tests/test_menubar.py -n auto` exits 0
- [ ] No restart sentence when `running=False`
- [ ] `get_running_instances` used only as a SCAN for display
- [ ] No process kill/signal
- [ ] No files outside scope

## STOP conditions

- 001 missing.
- You think you need to change `process_detection.py`.
- You add a “Restart Claude Code” button that sends signals.

## Maintenance notes

- Reviewer: extra must not treat unreadable session files as “nothing
  running” for **destructive** work; this plan is display-only, so SCAN is
  OK. Keep the try/except fallback as running=True.
- Plan 004 must preserve the running line when rebuilding the footer.
