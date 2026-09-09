#!/usr/bin/env bash
# CI-only: import an application signing .p12 into an ephemeral keychain and
# optionally store notarytool credentials. Used by .github/workflows/macos-app.yml.
#
# Required:
#   SIGNING_APPLICATION_P12_BASE64     base64-encoded application .p12
#   SIGNING_APPLICATION_P12_PASSWORD   export password (or SIGNING_P12_PASSWORD)
#
# Optional:
#   SIGNING_IDENTITY                   pin the codesigning identity (quoted name)
#   NOTARY_KEY_ID / NOTARY_ISSUER_ID / NOTARY_KEY_BASE64
#     when all three are set, stores keychain profile openswap-notary
#
# Writes OPENSWAP_SIGN_IDENTITY and OPENSWAP_NOTARY_PROFILE to GITHUB_ENV.
set -euo pipefail

: "${SIGNING_APPLICATION_P12_BASE64:?SIGNING_APPLICATION_P12_BASE64 is required}"

password="${SIGNING_APPLICATION_P12_PASSWORD:-${SIGNING_P12_PASSWORD:-}}"
if [[ -z "$password" ]]; then
  echo "ci-import-signing-keychain: SIGNING_APPLICATION_P12_PASSWORD or SIGNING_P12_PASSWORD is required" >&2
  exit 1
fi

NOTARY_PROFILE_NAME="${OPENSWAP_NOTARY_PROFILE:-openswap-notary}"
TMP="${RUNNER_TEMP:-${TMPDIR:-/tmp}}"
KEYCHAIN="${CI_KEYCHAIN_PATH:-$TMP/openswap-signing.keychain-db}"
KEYCHAIN_PASSWORD="${CI_KEYCHAIN_PASSWORD:-$(openssl rand -base64 32)}"
P12_PATH="$TMP/openswap-application.p12"

printf '%s' "$SIGNING_APPLICATION_P12_BASE64" | base64 -d > "$P12_PATH"

security create-keychain -p "$KEYCHAIN_PASSWORD" "$KEYCHAIN"
security default-keychain -s "$KEYCHAIN"
security list-keychains -d user -s "$KEYCHAIN"
security unlock-keychain -p "$KEYCHAIN_PASSWORD" "$KEYCHAIN"
security set-keychain-settings -lut 21600 "$KEYCHAIN"
security import "$P12_PATH" -k "$KEYCHAIN" -P "$password" \
  -T /usr/bin/codesign -T /usr/bin/security
rm -f "$P12_PATH"
security set-key-partition-list -S apple-tool:,apple:,codesign: -s -k "$KEYCHAIN_PASSWORD" "$KEYCHAIN"

if [[ -n "${SIGNING_IDENTITY:-}" ]]; then
  IDENTITY="$SIGNING_IDENTITY"
else
  IDENTITY="$(security find-identity -v -p codesigning "$KEYCHAIN" \
    | awk -F'"' '/Developer ID Application/{print $2; exit}')"
fi
if [[ -z "$IDENTITY" ]]; then
  echo "ci-import-signing-keychain: no application signing identity in the imported keychain" >&2
  security find-identity -v -p codesigning "$KEYCHAIN" >&2 || true
  exit 1
fi

notary_configured=0
if [[ -n "${NOTARY_KEY_ID:-}" && -n "${NOTARY_ISSUER_ID:-}" && -n "${NOTARY_KEY_BASE64:-}" ]]; then
  notary_key_path="$TMP/openswap-AuthKey.p8"
  printf '%s' "$NOTARY_KEY_BASE64" | base64 -d > "$notary_key_path"
  xcrun notarytool store-credentials "$NOTARY_PROFILE_NAME" \
    --key "$notary_key_path" \
    --key-id "$NOTARY_KEY_ID" \
    --issuer "$NOTARY_ISSUER_ID" \
    --keychain "$KEYCHAIN"
  rm -f "$notary_key_path"
  notary_configured=1
  echo "Notary credentials stored as keychain profile: $NOTARY_PROFILE_NAME"
else
  echo "Notary secrets not fully configured; build.sh will sign and skip notarization."
fi

if [[ -n "${GITHUB_ENV:-}" ]]; then
  {
    echo "OPENSWAP_SIGN_IDENTITY=$IDENTITY"
    echo "CI_KEYCHAIN_PATH=$KEYCHAIN"
    echo "CI_KEYCHAIN_PASSWORD=$KEYCHAIN_PASSWORD"
    if [[ "$notary_configured" == "1" ]]; then
      echo "OPENSWAP_NOTARY_PROFILE=$NOTARY_PROFILE_NAME"
    fi
  } >> "$GITHUB_ENV"
fi

echo "Signing keychain ready."
security find-identity -v -p codesigning "$KEYCHAIN" || true
