# CLI reference

```text
cswap list                       list managed accounts
cswap status                     show current account
cswap switch                     rotate to the next account
cswap switch <num|email|alias>   switch to a specific account
cswap add                        add the current account
cswap add-token [TOKEN|-]        register a setup-token or API key
cswap remove <num|email>         remove an account
cswap disable <num|email>        hold an account out of auto-rotation
cswap enable <num|email>         return a disabled account to rotation
cswap run <num|email> [-- ...]   run as an account, this terminal only
cswap run                        run the current dir's mapped account
cswap map <num|email> [path]     map a directory to an account
cswap map                        list directory mappings
cswap unmap [path]               remove a directory mapping
cswap alias <num|email> <name>   set a short alias
cswap alias <num|email> --unset  remove an alias
cswap alias                      list aliases
cswap swap <a> <b>               exchange two slots
cswap move <a> <slot>            assign an account to a slot
cswap auto                       auto-switch near rate limits
cswap config [set KEY VALUE]     show or change settings
cswap unclaimed [--purge ID]     list or drop stashed credentials
cswap export <path>              export accounts
cswap import <path>              import accounts
cswap tui                        interactive dashboard (also: bare cswap)
cswap watch                      dashboard, live watch page
cswap menubar                    macOS extra (foreground)
cswap menubar --install-service  keep the extra running via launchd
cswap widget --install           macOS Desktop / Notification Center widget
cswap upgrade                    self-upgrade
cswap purge                      remove all claude-swap data
cswap help
```

Aliases: `ls` = `list`, `rm` = `remove`, `update` = `upgrade`.

Original flag spellings (`cswap --switch`, `cswap --list`, …) still work.

## Useful flags

```bash
cswap switch --strategy best
cswap switch --strategy next-available
cswap list --token-status
cswap list --json
cswap add --slot 3
cswap add --alias work
cswap add-token sk-ant-oat01-... --email you@example.com
cswap run 2 -- --resume
cswap auto --once --json
cswap auto --strategy consume-first
cswap auto --model Fable
cswap config set autoswitch.threshold 80
cswap menubar --service-status
cswap widget --status
cswap widget --uninstall
```

## JSON

`list`, `status`, and `switch` take `--json` (one object on stdout; notices on stderr). `cswap auto --json` is an event stream.

```json
{
  "schemaVersion": 1,
  "activeAccountNumber": 2,
  "accounts": [
    {
      "number": 2,
      "email": "you@example.com",
      "active": true,
      "usageStatus": "ok",
      "usage": {
        "fiveHour": { "pct": 25.0, "resetsAt": "2026-06-22T23:29:59Z" },
        "sevenDay": { "pct": 16.0, "resetsAt": "2026-06-26T17:59:59Z" }
      }
    }
  ]
}
```

Handled errors: `{"schemaVersion":1,"error":{...}}` and a non-zero exit. New fields may appear; ignore ones you do not know.

Weekly windows may include pace fields (`expectedPct`, `aheadOfPace`, `projectedExhaustionAt`) once the week is about a day old. Disabled rows carry `"disabled": true`. Aliases appear as `"alias": "work"` when set.

## After a switch, do I restart?

Usually no. Linux and Windows re-read the credential file on the next message. macOS Keychain is cached ~30 seconds. Restart Claude Code only if you want the new account instantly.

You can keep the same conversation after switching. The first message on the new account may use extra usage while the conversation cache rebuilds.
