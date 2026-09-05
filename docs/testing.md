# Testing

```bash
uv run pytest
```

`pyproject.toml` sets `-n auto`. About 2200 tests; CI runs the same command on Ubuntu, Windows, and macOS.

## Boundaries

| File | May import rumps / AppKit? |
| --- | --- |
| `tests/test_menubar.py` | No. Pure helpers only. |
| `tests/test_kickoff.py` | No. |
| `tests/test_widget_snapshot.py` | No. |
| `tests/test_widget_install.py` | No (paths, team parsing, plist). |
| `tests/test_autoswitch.py` | No. |

Live AppKit probes (status item padding, appearance) are one-off scripts, not CI.

## Conventions already in the suite

- Do not hit the real account store or Keychain. `conftest.py` isolates HOME / backup dirs.
- `no_keychain_fake` / `no_oauth_profile_fake` markers opt out of autouse stubs when a test mocks `subprocess` itself.
- Prefer asserting behavior (format strings, length formula, eligibility) over scraping source, except for wiring checks that cannot run AppKit (`fit_status_item` called from `rebuild_menu`).

## After UI changes

Restart the extra and exercise the popover (first click on a card, More without dismissing, leave-delay close, Dark/Light, icon on/off, strategy). Widget: `cswap widget --install`, then Edit Widgets. Browser tools do not apply.
