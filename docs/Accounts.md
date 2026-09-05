# Accounts

Each saved login is a **slot** (`Account-1`, `Account-2`, …). cswap swaps only that account’s Claude login. Machine-wide MCP / plugin OAuth stays put.

## Add

```bash
cswap add                     # current Claude Code login
cswap add --slot 3            # prompts before overwrite
cswap add --alias work
```

If a token has expired, log back into Claude Code with that account and run `cswap add` again. It updates the stored credentials instead of creating a duplicate.

### From a setup-token or API key

Useful on a headless machine, or when someone hands you a token:

```bash
cswap add-token sk-ant-oat01-...          # OAuth setup-token
cswap add-token sk-ant-api03-...          # managed API key
cswap add-token sk-ant-oat01-... --slot 3
cswap add-token - --slot 3                # stdin
cswap add-token --email you@example.com   # optional label
```

API-key accounts have no subscription quota, so they show no usage. Auto-switch will not rotate onto them unless you set `autoswitch.includeApiKeyAccounts`.

## List and status

```bash
cswap list
cswap list --token-status
cswap list --json
cswap status
```

Rows can show `(disabled)`, `(ahead)` (weekly spend faster than even pace), and an age such as `· 6m ago` when the next usage fetch has not run yet.

## Switch

```bash
cswap switch
cswap switch 2
cswap switch user@example.com
cswap switch work
cswap switch --strategy best
cswap switch --strategy next-available   # skip accounts that are rate-limited
```

Disabled accounts are skipped by rotate / `best` / `next-available`, but `cswap switch 2` still works if you name the slot.

## Alias, disable, move, remove

```bash
cswap alias 2 work
cswap alias 2 --unset
cswap alias

cswap disable 2              # keep the login, leave it out of rotation
cswap enable 2

cswap move 2 1               # reassign slots (swaps if the target is taken)
cswap swap 1 2

cswap remove 2
```

Disable is for a work account you do not want auto-switch to touch, or one you are resting. The TUI and the extra can toggle the same state.

## Two orgs, same email

Claude Code can have two organizations on the same user. cswap tells them apart by org UUID, not by email. Give each slot an alias (`personal`, `adsonline`) so the extra and `cswap list` stay readable.

A warning that two slots “hold the same credential” means the **stored credential fingerprint** matches (one slot’s backup was overwritten). Same email with different orgs is expected and is not that warning.

## Unclaimed credentials

Sometimes a swap leaves a stashed credential that no longer belongs to a slot:

```bash
cswap unclaimed
cswap unclaimed --purge ID
```

Purging deletes the bytes. Recover that login with `/login` and `cswap add`.
