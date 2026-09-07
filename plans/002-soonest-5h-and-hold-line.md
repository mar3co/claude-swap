# Plan 002: Add soonest-5h strategy and a hold-reason line

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, do **not** update `plans/README.md`.
>
> **Drift check (run first)**: `git diff --stat 5e4ffde..HEAD -- src/openswap/autoswitch.py src/openswap/settings.py src/openswap/menubar.py src/openswap/menubar_panel.py src/openswap/cli.py tests/test_autoswitch.py tests/test_settings.py tests/test_menubar.py docs/menubar.md README.md`
> After plan 001 is merged, HEAD will differ from `5e4ffde` in `menubar.py`
> (9-tuples, org titles). That is expected — use the **post-001** tuple
> shape. STOP only if ranking / strategy code in `autoswitch.py` no longer
> matches the excerpts below.

## Status

- **Priority**: P1
- **Effort**: M
- **Risk**: MED
- **Depends on**: plans/001-org-names-on-extra.md
- **Category**: direction
- **Planned at**: commit `5e4ffde`, 2026-09-05

## Why this matters

`consume-first` ranks the **weekly** `seven_day` reset. Users who watch the
extra’s 5h bars (Ads Online resets in 4 hours) think the engine should move
there. Changing weekly consume-first in place would surprise anyone who set
it for 7d. Add a third strategy `soonest-5h` that reuses the consume-first
trigger path but ranks `five_hour.resets_at`. Also show a one-line hold
reason in the popover so “staying on personal” is visible.

## Current state

- `src/openswap/settings.py` `AutoSwitchSettings.strategy` default `"best"`;
  `SETTING_SPECS["autoswitch.strategy"].choices = ("best", "consume-first")`.
- `src/openswap/autoswitch.py`:
  - `_seven_day_reset_ts` ranks weekly only (lines 538–557).
  - `if settings.strategy != "consume-first":` below-threshold hold (1004).
  - `consume_first = settings.strategy == "consume-first"` (1124).
  - `_rank_candidates` uses `_seven_day_reset_ts` when `consume_first`.
  - Trigger string stays `"consume-first"` for events.
- `src/openswap/cli.py` `_auto_command` `--strategy` choices
  `("best", "consume-first")`.
- `src/openswap/menubar.py` `AUTO_STRATEGY_CHOICES = (("best", "Most quota left"), ("consume-first", "Soonest weekly reset"))`.
  `test_auto_strategy_choices_match_core_settings` requires extra choices ==
  `SETTING_SPECS` choices.
- Tests: `tests/test_autoswitch.py` `TestConsumeFirstStrategy` (~2819)
  uses `_usage7`. `tests/test_settings.py` persist/load consume-first.

Do **not** change existing consume-first weekly behavior. Reuse the same
trigger name `"consume-first"` for both consume strategies so the 20
`trigger == "consume-first"` branches stay valid.

## Commands you will need

| Purpose | Command | Expected on success |
|---------|---------|---------------------|
| Engine + settings + extra | `uv run pytest tests/test_autoswitch.py tests/test_settings.py tests/test_menubar.py tests/test_config_cli.py -n auto` | all pass |

## Suggested executor toolkit

- TDD. Model consume-first tests after `TestConsumeFirstStrategy`.
- Do not import AppKit in menubar tests.

## Scope

**In scope**:
- `src/openswap/autoswitch.py`
- `src/openswap/settings.py`
- `src/openswap/cli.py` (the `--strategy` choices/help on `openswap auto` only)
- `src/openswap/menubar.py`
- `src/openswap/menubar_panel.py` (one muted status line under the header)
- `tests/test_autoswitch.py`
- `tests/test_settings.py`
- `tests/test_menubar.py`
- `tests/test_config_cli.py` if it asserts strategy choices
- `docs/menubar.md`
- `README.md` (the extra line that mentions consume-first)

**Out of scope**:
- Per-window thresholds (upstream #303) — do not add `threshold5h` /
  `threshold7d`.
- Changing weekly consume-first ranking.
- Settings page rewrite (plan 004) — only add the third menu item to the
  existing rumps Settings submenu and the popover hold line.
- Push / wiki.

## Git workflow

- Branch: `advisor/002-soonest-5h-and-hold-line`
- Commits: `feat(autoswitch): rank 5h resets with soonest-5h` then
  `feat(menubar): show why auto-switch is holding` if you split.
- Do NOT push.

## Steps

### Step 1: Drift check

Confirm 001 is in HEAD (`org_name` in `_adapt_snapshot`). If not, STOP
(dependency). Confirm `settings.strategy` choices are still two-valued.

### Step 2: Failing engine tests (TDD)

Add `_usage5(pct5, reset5, pct7=10, reset7=_R_LATEST)` helper next to
`_usage7`.

New class `TestSoonest5hStrategy` modeled on `TestConsumeFirstStrategy`:
- harness `strategy="soonest-5h"`
- below threshold, account with sooner **5h** reset wins even if its weekly
  reset is later
- stays when active already has the soonest 5h reset (`already-consuming-soonest`)
- weekly-soonest but 5h-later account is **not** chosen
- existing `TestConsumeFirstStrategy` cases still pass unchanged (weekly)

Add `test_window_reset_ts_five_hour_and_seven_day` for a new helper
`_window_reset_ts(usage, key, now)` used by ranking: past reset → None;
future 5h vs 7d keys independent.

**Verify**: RED.

### Step 3: Engine + settings

- `SETTING_SPECS` strategy choices: `("best", "consume-first", "soonest-5h")`.
- Help text: consume-first = soonest weekly reset; soonest-5h = soonest
  5-hour session reset.
- `autoswitch.py`:
  - `CONSUME_STRATEGIES = frozenset({"consume-first", "soonest-5h"})`
  - Replace `settings.strategy == "consume-first"` / `!= "consume-first"`
    **that mean “use consume ranking”** with `in CONSUME_STRATEGIES`.
    Do not rename the event `trigger` string; keep `"consume-first"`.
  - `_window_reset_ts(usage, key, now)` where `key` is `"five_hour"` or
    `"seven_day"`. Same past==unknown rule as `_seven_day_reset_ts`.
  - `_seven_day_reset_ts` becomes a one-liner calling `_window_reset_ts(..., "seven_day")`.
  - `_rank_candidates`: when consume ranking, use
    `"five_hour"` if `settings.strategy == "soonest-5h"` else `"seven_day"`.
    Pass `settings` (already passed) to pick the key.
- `cli.py` auto `--strategy` choices include `soonest-5h`; help mentions 5h.

Grep `consume-first` in `autoswitch.py` and `cli.py` so no choice list is
missed.

**Verify**: `uv run pytest tests/test_autoswitch.py tests/test_settings.py tests/test_config_cli.py -n auto` passes.

### Step 4: Extra strategy menu + hold line (TDD then code)

`AUTO_STRATEGY_CHOICES` add `("soonest-5h", "Soonest 5-hour reset")`.
`test_auto_strategy_choices_match_core_settings` will require the spec
update from step 3.

Pure helper in `menubar.py` (no AppKit):

```python
def auto_hold_line(strategy: str, accounts: list[dict], *, now: float) -> str | None:
    """One glanceable sentence, or None for strategy 'best' or empty cards.

    accounts items: {"num", "title", "active", "windows": [{"label","resets_at_ts",...}]}
    For consume-first use 7d window; for soonest-5h use 5h.
    If active already soonest: "Holding on {title}: {5h|weekly} reset is soonest."
    If another title would win: "Would pick {title} ({5h|weekly} resets sooner)."
    Disabled / missing reset ts: skip that card.
    """
```

Tests in `test_menubar.py` with two cards (titles `personal` / `Ads Online`),
synthetic `resets_at_ts`. Do not call the engine.

`menubar_panel.py`: if snapshot/callback provides a non-empty hold line,
draw it muted under the header (`font_small`) and add `HOLD_LINE_H = 16.0`
to total height. Wire from extra: compute `auto_hold_line` from
`panel_accounts` + current strategy during snapshot refresh; stash on the
snapshot dict as `"hold_line"` **or** pass a getter into the panel. Prefer
snapshot key so tests stay pure.

Do not change consume-first default.

**Verify**: `uv run pytest tests/test_menubar.py tests/test_autoswitch.py tests/test_settings.py -n auto` passes.

### Step 5: Docs + commit

`docs/menubar.md`: strategy list includes soonest-5h; hold line described.
`README.md` extra sentence: More → Settings also has “Soonest 5-hour reset”.

**Verify**: in-scope only.

## Test plan

- `TestSoonest5hStrategy` (switch, hold, does not use weekly)
- `TestConsumeFirstStrategy` unchanged
- settings parse/persist `soonest-5h`
- `test_auto_strategy_choices_match_core_settings`
- `auto_hold_line` cases
- Pattern: `tests/test_autoswitch.py` `TestConsumeFirstStrategy`

## Done criteria

- [ ] Tests listed above pass
- [ ] `best` and `consume-first` behavior unchanged
- [ ] `soonest-5h` ranks `five_hour.resets_at`
- [ ] Extra strategy menu has three items; choices match SETTING_SPECS
- [ ] Popover shows hold_line when strategy is a consume strategy
- [ ] No files outside scope

## STOP conditions

- 001 not in HEAD (no `org_name` / 9-tuples).
- You believe you must change weekly consume-first ranking to make tests pass.
- You would add per-window thresholds.
- Ranking tests fail because `trigger` was renamed; keep trigger
  `"consume-first"`.

## Maintenance notes

- Reviewer: grep `strategy == "consume-first"` in `autoswitch.py` — remaining
  equals should only be “pick the 7d window key”, not “is this consume mode”.
- Plan 004 will re-home the strategy picker into the popover; keep
  `AUTO_STRATEGY_CHOICES` as the single extra-side list.
