# Sessions and directory maps

`cswap switch` changes the **default** Claude Code login (every terminal and the VS Code extension). `cswap run` launches Claude Code as one account **in this terminal only**, so two accounts can work at the same time.

## Run

```bash
cswap run 2                        # account 2, here only
cswap run user@example.com
cswap run work                     # alias
cswap run 2 -- --resume            # everything after -- goes to claude
cswap run 2 --share-history        # same chat history as the default login
cswap run 2 --require-session      # refuse if 2 is already the default login
```

Sessions reuse your normal `~/.claude` setup (settings, CLAUDE.md, skills, MCP). Each account keeps its own chat history unless you pass `--share-history`.

If you `cswap run` the account that is already the default login, cswap launches plain `claude` instead of a session (a second copy of the active credential would go stale). Scripts that need isolation can pass `--require-session`.

While a session is running, `cswap switch` will refuse to move the default login onto that account if the stored backup has fallen behind. Exit the session first, or pick another account. When the session exits, its refreshed token is written back into the backup.

## MCP and history

- `--share-history`: a session started under one account shows up in `--resume` under the others.
- User-scope MCP servers (`claude mcp add -s user`) are mirrored from the default profile on every launch. Manage them on the default login. HTTP MCP servers may ask you to authenticate once per profile via `/mcp`.
- `--no-share` turns sharing off and removes the mirrored MCP config.

## Map a directory to an account

Bind a folder to a slot. A bare `cswap run` in that tree launches that account in session mode (work account in work repos, personal elsewhere):

```bash
cswap map 2 ~/work/client-app
cswap map user@example.com         # current directory
cswap map                          # list
cswap unmap ~/work/client-app

cd ~/work/client-app/src
cswap run                          # account 2, session mode
```

Subfolders inherit the nearest mapped ancestor. In an unmapped directory, `cswap run` launches plain `claude` on the default login.

Mappings are per-machine (not part of `cswap export`) and are removed when their account is removed.
