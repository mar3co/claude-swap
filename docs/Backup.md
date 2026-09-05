# Backup and migration

Move accounts between machines, or keep a file you can restore.

```bash
cswap export backup.cswap                 # all accounts
cswap export backup.cswap --account 2     # one slot
cswap export backup.cswap --full          # include full ~/.claude.json (same Mac)
cswap import backup.cswap                 # skip slots that already exist
cswap import backup.cswap --force         # overwrite
```

The export is plaintext JSON. By default it carries each account’s own login only. Machine-shared MCP/plugin OAuth and the device token stay on the source Mac. `--full` keeps everything, for same-machine backups.

Encrypt if you need to: `cswap export - | gpg -c > backup.gpg`.

If you import the account you are currently logged in as, activate it with `cswap switch N --force`. A plain `cswap switch` to the current account is a no-op and will not apply the import.

A plain `cswap import backup.cswap` replaces slots whose refresh token is already dead. `--force` is still required to replace healthy existing accounts. A stale export can carry a token that has already been superseded.

## Uninstall

```bash
cswap widget --uninstall
cswap menubar --uninstall-service
cswap purge
uv tool uninstall claude-swap
```

`cswap purge` removes all claude-swap data (backups, settings, sessions). It does not log you out of Claude Code.
