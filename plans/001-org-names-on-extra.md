# Plan 001: Show org names on extra cards, status item, and widget

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, do **not** update `plans/README.md`
> (the reviewer maintains the index).
>
> **Drift check (run first)**: `git diff --stat 5e4ffde..HEAD -- src/openswap/menubar.py src/openswap/menubar_panel.py src/openswap/widget_snapshot.py tests/test_menubar.py tests/test_widget_snapshot.py macos/OpenSwapWidget/Widget/OpenSwapWidgetView.swift docs/menubar.md`
> If any in-scope file changed since this plan was written, compare the
> "Current state" excerpts against the live code before proceeding; on a
> mismatch, treat it as a STOP condition.

## Status

- **Priority**: P1
- **Effort**: S
- **Risk**: LOW
- **Depends on**: none
- **Category**: direction
- **Planned at**: commit `5e4ffde`, 2026-09-05

## Why this matters

Two Claude orgs can share one email (personal vs Ads Online). The TUI already
labels them `[personal]` / `[Ads Online]` via `AccountSnapshot.display_tag`.
The extra drops `org_name` in `_adapt_snapshot`, so both cards title as the
same email and the status item shows the same local-part. Users cannot tell
which card they are clicking. After this plan, extra cards, the status item,
and the widget use org name (or alias) the same way the TUI does.

## Current state

- `src/openswap/models.py` — `AccountSnapshot.org_name` and `display_tag`
  (`org_name if org_name else "personal"`). Do not change this file.
- `src/openswap/switcher.py` — `accounts_snapshot()` already passes
  `org_name=org_name` into `AccountSnapshot` (~1751–1760). Do not change.
- `src/openswap/menubar.py` — extra snapshot adapter **drops** org:
  `_adapt_snapshot` appends
  `(acc.number, acc.email, acc.is_active, display, acc.usage.last_good, acc.alias, acc.disabled, acc.usage.fetched_at)`
  with no `org_name`. `EMPTY_SNAPSHOT` has no `active_org`.
  `panel_accounts` titles `"title": alias or email` and
  `"subtitle": email if alias else ""`.
  `format_title` uses `alias if alias else _local_part(active_email)`.
- `src/openswap/menubar_panel.py` — draws `card["title"]` only; no subtitle
  line. Card height: `CARD_PAD * 2 + TITLE_H + 6 + n * ROW_H`. `TITLE_H = 18.0`.
- `src/openswap/widget_snapshot.py` — copies `panel_accounts` dicts as-is.
  No code change required if `panel_accounts` grows `subtitle`.
- `macos/OpenSwapWidget/Widget/OpenSwapWidgetView.swift` — `AccountBlock` draws
  `account.title` only; `AccountCard.subtitle` exists in `Snapshot.swift` and
  is unused.
- Tests: `tests/test_menubar.py` `test_panel_accounts_prefers_alias_and_keeps_note`
  and `test_adapt_snapshot_shape_and_active_selection`. `_FakeAcct` has no
  `org_name`. `tests/test_widget_snapshot.py` `_snap()` uses 8-tuples.

Conventions: `tests/test_menubar.py` must not import AppKit/rumps. Prefer
behavior assertions. TDD: write the failing test first. Commit style:
`feat(menubar): show org names on cards and the extra`.

Constraints from `docs/architecture.md`: extra is a thin shell; do not
re-implement quota math. Display-only change.

## Commands you will need

| Purpose | Command | Expected on success |
|---------|---------|---------------------|
| Tests (this plan) | `uv run pytest tests/test_menubar.py tests/test_widget_snapshot.py -n auto` | all pass |
| Broader extra | `uv run pytest tests/test_menubar.py tests/test_widget_snapshot.py tests/test_appearance.py -n auto` | all pass |

Working directory: the git worktree root (the `openswap` checkout).

## Suggested executor toolkit

- Use test-driven development: failing test first, then minimal production code.
- Do not import AppKit in `tests/test_menubar.py`.

## Scope

**In scope**:
- `src/openswap/menubar.py`
- `src/openswap/menubar_panel.py`
- `macos/OpenSwapWidget/Widget/OpenSwapWidgetView.swift`
- `tests/test_menubar.py`
- `tests/test_widget_snapshot.py`
- `docs/menubar.md` (one short sentence: cards use alias or org tag, email as subtitle)

**Out of scope**:
- `src/openswap/models.py`, `switcher.py`, `autoswitch.py`
- Wiki repo
- Widget entitlements, App Intents, accessory families (plan 005)
- Settings UI (plan 004)
- Changing `AccountSnapshot` itself
- Push / PR / `upstream`

## Git workflow

- Branch: `advisor/001-org-names-on-extra` from the worktree’s HEAD
- Commits: conventional, e.g. `feat(menubar): show org names on cards and the extra`
- Do NOT push or open a PR.

## Steps

### Step 1: Drift check

Run the drift-check command in the executor instructions.

**Verify**: empty diff, or only unrelated files. If `menubar.py` / `menubar_panel.py`
excerpts above do not match live code, STOP.

### Step 2: Failing tests for snapshot + cards + title (TDD)

In `tests/test_menubar.py`:

1. Give `_FakeAcct` `org_name=""` default. `_adapt_snapshot` must copy it.
2. Extend `test_adapt_snapshot_shape_and_active_selection`:
   - row tuple is 9 elements: add `org_name` after `alias`
     `(num, email, is_active, display, last_good, alias, org_name, disabled, fetched_at)`
   - snapshot has `active_org` (string, `""` when missing)
3. Replace/extend `test_panel_accounts_prefers_alias_and_keeps_note`:
   - alias set: `title == alias`, `subtitle` contains the email
   - no alias, `org_name="Ads Online"`: `title == "Ads Online"`, `subtitle` is the email
   - no alias, empty org: `title == "personal"`, `subtitle` is the email
4. Add `test_format_title_prefers_alias_then_org_then_local_part`:
   - `format_title(..., alias="dev", org_name="Ads Online")` → starts with `dev`
   - `format_title(..., org_name="Ads Online")` with `show_account_name=True`,
     `title_pct="off"` → `"Ads Online"`
   - `format_title(...)` with no alias/org, `title_pct="off"` → still `"loc"`
     (existing local-part behavior; do not break `test_format_title_name_only_when_pct_off`)

In `tests/test_widget_snapshot.py` update `_snap()` 8-tuples to 9-tuples
(insert `""` org after alias). Existing assertions on `title` will fail until
`panel_accounts` is updated: the aliased row titled `"personal"` stays
`"personal"`; the no-alias row becomes title `"personal"` not `"b@x.com"`.
Update `test_build_payload_stringifies_num_and_keeps_windows` so the second
account expects `title == "personal"` and `subtitle == "b@x.com"`.

Run pytest; confirm RED (failures are assertion/AttributeError on `org_name`,
not import errors).

**Verify**: `uv run pytest tests/test_menubar.py::test_adapt_snapshot_shape_and_active_selection tests/test_menubar.py::test_panel_accounts_prefers_alias_and_keeps_note tests/test_widget_snapshot.py::test_build_payload_stringifies_num_and_keeps_windows -n0` fails for the new expectations.

### Step 3: Implement adapter + `panel_accounts` + `format_title`

In `menubar.py`:

- `_adapt_snapshot`: append `getattr(acc, "org_name", "") or ""` in the tuple
  after `alias`. Set `active_org` when `acc.is_active`. Add `"active_org": None`
  to `EMPTY_SNAPSHOT`.
- `panel_accounts`: unpack 9-tuple. Helper (keep it tiny, next to
  `account_short_name`):

```python
def account_card_names(email, alias, org_name) -> tuple[str, str]:
    """(title, subtitle) for extra/widget cards.

    Alias wins as title. Otherwise the TUI display tag (org name or
    'personal'). Email is always the subtitle when it differs from title.
    """
```

  `title, subtitle = account_card_names(email, alias, org_name)`
- `format_title(..., alias=None, org_name=None)`: when `show_account_name`,
  append `alias or (org_name if org_name else None) or _local_part(email)` —
  wait: empty org must show `"personal"` on **cards**, but the status item
  for a single personal account should stay the short local-part (existing
  tests). Rule:
  - cards: `alias or (org_name.strip() if org_name else "personal")`
  - title bar: `alias or (org_name.strip() if org_name else "") or _local_part(email)`
    so a nameless personal account stays `"loc"`, and `"Ads Online"` shows
    when `org_name` is set.
- `rebuild_menu` `format_title(..., alias=..., org_name=self.snapshot.get("active_org"))`
- Update every unpack of the 8-tuple in `menubar.py` (search
  `alias, disabled, fetched_at` and the kickoff loop
  `num, email, is_active, display, last_good, alias, _dis, _fa`).
  Insert `org_name` (or `_org`) after `alias`.

**Verify**: the tests from step 2 pass. Then
`uv run pytest tests/test_menubar.py tests/test_widget_snapshot.py -n auto` passes.

### Step 4: Draw subtitle on extra cards and widget

`menubar_panel.py`: if `card.get("subtitle")`, draw a second line under the
title (`font_small`, `pal["muted"]`), and add `SUBTITLE_H = 14.0` to card
height when subtitle is non-empty. Both the empty-state height loop at the
top of `_build` and the per-card loop must use the same formula.

`OpenSwapWidgetView.swift` `AccountBlock`: under the title `HStack`, if
`!account.subtitle.isEmpty`, `Text(account.subtitle)` caption, `Palette.muted`,
`lineLimit(1)`.

No AppKit tests. Do not change snapshot JSON schema number.

**Verify**: `uv run pytest tests/test_menubar.py tests/test_widget_snapshot.py -n auto` still passes. Swift is compile-checked later by the human via
`openswap widget --install`; do not run xcodebuild unless it is already fast and
does not change signing.

### Step 5: Docs + commit

`docs/menubar.md`: in the account-row paragraph, note that card title is
alias or org tag (`personal` when the org name is empty), email as subtitle.

Commit.

**Verify**: `git diff --stat` only in-scope files. `git log -1 --format=%s`
is a conventional `feat(menubar):` subject.

## Test plan

- `test_adapt_snapshot_shape_and_active_selection` — 9-tuple + `active_org`
- `test_panel_accounts_prefers_alias_and_keeps_note` — alias / org / personal
- `test_format_title_prefers_alias_then_org_then_local_part` (new)
- existing `test_format_title_*` still pass (local-part when no org)
- `tests/test_widget_snapshot.py` payload title/subtitle
- Pattern: existing tests in `tests/test_menubar.py` around lines 307–323 and 744–766

## Done criteria

- [ ] `uv run pytest tests/test_menubar.py tests/test_widget_snapshot.py -n auto` exits 0
- [ ] `_adapt_snapshot` includes `org_name` and `active_org`
- [ ] `panel_accounts` titles org tag or alias, not a duplicate email
- [ ] `format_title` uses org_name when set and no alias
- [ ] Extra cards and widget show subtitle when present
- [ ] No files outside the in-scope list
- [ ] One conventional commit on `advisor/001-org-names-on-extra`

## STOP conditions

- Drift: in-scope files no longer match the excerpts.
- A step’s verification fails twice after a reasonable fix.
- You think you need to change `models.py` / `switcher.py` / snapshot schema.
- You would need AppKit in `tests/test_menubar.py`.
- Tuple unpack sites you cannot find by searching `menubar.py` for the
  8-tuple (do not guess a 10th field).

## Maintenance notes

- Later plans (002 hold line, 003 sessions, 004 settings) assume 9-tuples and
  optional `card["subtitle"]` plus `SUBTITLE_H`.
- Reviewer: confirm no leftover 8-tuple unpack in `menubar.py`.
- Wiki Menu-Bar page is deferred to the advisor after merge.
