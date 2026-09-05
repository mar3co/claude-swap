# Troubleshooting

## The extra is missing

```bash
cswap menubar --service-status
launchctl kickstart -k "gui/$(id -u)/com.cswap.menubar"
```

If it is not installed: `cswap menubar --install-service`.

Logs: `~/Library/Logs/com.cswap.menubar.{log,err}`.

## Extra is light while the Mac is Dark

The popover follows System Settings → Appearance, not the menu bar wallpaper tint. Restart the extra after changing appearance if it looks stuck.

## Extra has a blank gap on the left

That is the old icon slot. With **Show asterisk in menu bar** off (default), the extra should hug the title. Restart the extra after upgrading.

## Widget is empty or missing

1. Extra must be running (`cswap menubar --service-status`).
2. `cswap widget --status` should show the app present and the host loaded.
3. Add it from Edit Widgets; search for **cswap**. Nothing can place it for you.
4. Snapshot file: `~/Library/Application Support/cswap/widget-snapshot.json`.
5. Rebuild: `cswap widget --install`. Needs this git checkout and Xcode.

If bundle IDs flipped (different Apple team), remove the old widget and add it again.

## `cswap add` / switch errors

- Do not `/logout` before `cswap add`.
- Expired token: log into that account in Claude Code, then `cswap add` again (or `cswap add --slot N`).
- Quarantined account: same as expired token, or `cswap import` a known-good export.
- “Same credential” warning on two slots: one backup may have overwritten the other. Same email with **different orgs** is normal; aliases help.

## Switch did not apply in Claude Code

Wait ~30 seconds on macOS (Keychain cache), or restart Claude Code / reopen the VS Code extension tab.

`cswap run` sessions: exit the session before switching the default login onto that same account if cswap refuses.

## Auto-switch is not picking the account that resets soon

Default strategy is **best**: stay until ~90% of the binding 5h/7d window. The countdown you see (2 hours on a 7d row) is ignored until then.

Use **consume-first** (soonest weekly reset):

```bash
cswap config set autoswitch.strategy consume-first
```

Or More → Settings → Auto-switch strategy → Soonest weekly reset. Restart the extra (or the `cswap auto` process) so it reloads settings.

See [Auto-switch](Auto-Switch.md).

## Kickoff did not run

- Enabled, and local time is at or after the scheduled clock
- At most once per local day
- Skips API-key accounts and accounts whose 5-hour window is still open
- Failed pings retry after 5 minutes

## Need a clean slate

```bash
cswap widget --uninstall
cswap menubar --uninstall-service
cswap purge
```

That deletes backups and settings. Claude Code itself stays logged in.
