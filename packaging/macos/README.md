# macOS spike build (plan 007)

One `OpenSwap.app`: PyInstaller-frozen extra + embedded WidgetKit appex +
in-bundle reload helper. Not a product install path (that is plan 008).

## Build

From the repo root:

```bash
export OPENSWAP_SIGN_IDENTITY='the codesigning identity recorded in plan 007 Step 0'
# one-time: xcrun notarytool store-credentials openswap-notary
./packaging/macos/build.sh
```

`OPENSWAP_SIGN_IDENTITY` is required to sign, notarize, and staple. Without
it the script still freezes and assembles, then exits 2 and leaves the
bundle unsigned. Never put the identity string or notary credentials in a
file.

Notary profile name: `openswap-notary` (keychain item, not a repo secret).

Output: `packaging/macos/dist/OpenSwap.app` (gitignored). Bundle size on this
spike Mac: 26M.

## Spike verdict

Recorded 2026-09-09 against `claude/007-single-app-spike`. Step 0 on this Mac:
Apple Development identities only (no Developer ID Application) and no
`openswap-notary` profile. Freeze/assemble ran; sign/notarize/staple did not.
Step 7 did not move `~/Applications/OpenSwap.app` or boot out the live extra.

1. **FAIL** — `open -a` extra/popover not run. Would replace the live extra
   with an unsigned bundle; skipped after Step 0 STOP.
2. **FAIL** — no `open -a` process logs. Unsigned `spctl --assess` on the
   dist app: `invalid Info.plist (plist or signature have been modified)`
   (PlistBuddy sets `CFBundleIconFile` after PyInstaller's ad-hoc sign;
   inside-out Developer ID sign is what would repair that).
3. **PASS** — `packaging/macos/dist/OpenSwap.app/Contents/MacOS/OpenSwap list`
   exit 0, 744-byte table identical to live `openswap list` (same Keychain
   accounts). Same binary with no args on a TTY prints help (`Commands:`)
   and does not leave a second extra running.
4. **FAIL** — Edit Widgets not exercised; live widget host was left in place
   so WidgetKit would not see two parents for one appex id.
5. **FAIL** — in-bundle `openswap-widget-reload` not invoked against a
   registered spike appex (same reason as 4). Helper binary is in
   `Contents/MacOS/openswap-widget-reload`.
6. **OPERATOR** — card click / widget tap / frozen `switch <n>` left for the
   operator; executor must not switch the live Claude login.

Plan 008 is gated on a notarized PASS of 1–5 (and operator 6). Re-run
`build.sh` with `OPENSWAP_SIGN_IDENTITY` and `openswap-notary`, then Step 7.
