"""Refresh a backup credential so it outlives Claude Code's 5-min buffer."""

from __future__ import annotations

import time

from openswap import oauth

# Systemic freshen refusals, MOST ACTIONABLE FIRST. Deterministic conditions
# that every candidate hits identically, so the tick reports one of them —
# and the order decides which, because reporting the wrong one is how a cause
# needing a human hides behind one that clears itself. store-unmirrored and
# invalid_client stay until somebody unsets an env var or fixes a client
# registration, and stash-unreadable until they unlock a keychain, fix a mode,
# or purge the row; consume-busy is gone by the next pass. stash-unreadable is
# the one that is per-SLOT rather than global, which costs nothing here: this
# message is only ever emitted when NO candidate freshened, so naming the real
# cause of the only slot that had one beats "(network?)".
_SYSTEMIC_MESSAGES = {
    "store-unmirrored": "CLAUDE_SECURESTORAGE_CONFIG_DIR is set — unset it or "
                        "run openswap from a normal shell",
    "invalid_client": "openswap's OAuth client was rejected — systemic, not this "
                      "account",
    "stash-unreadable": "a stashed successor is unreadable — unlock the "
                        "keychain or fix the file, then retry; "
                        "`openswap unclaimed` inspects it",
    "consume-busy": "another openswap surface holds the slot — retries next pass",
}
# Insertion order IS the precedence order, so the remedy and its rank cannot
# drift apart.
_SYSTEMIC_STATUSES = tuple(_SYSTEMIC_MESSAGES)

# Freshen targets whose access token expires within this window: twice Claude
# Code's own 5-minute refresh buffer, so its post-lock "abort refresh if not
# expired" re-read holds with margin after our swap.
FRESHEN_BUFFER_MS = 10 * 60 * 1000


class FreshenMixin:
    """Backup-store token refresh used before auto-activating a Claude slot."""

    def freshen_backup(self, number: str, email: str) -> str:
        """Ensure a candidate's stored token outlives Claude Code's 5-min
        refresh buffer before it gets activated.

        Returns ``"ok"``, ``"invalid_grant"`` (dead lineage — quarantine),
        ``"identity-conflict"`` (alive but authenticates as a different
        account — quarantine, do not activate), ``"transient"`` (network
        trouble — try again next tick) or ``"skip-live-session"``. Only ever
        touches the slot's *backup* store; the active credential belongs to
        Claude Code.
        """
        if self.account_kind_for(number) == "api_key":
            return "ok"  # API keys don't expire/refresh
        if self.live_session_pids_for(number, email):
            # A live isolated-profile Claude (kickoff or leftover session) owns
            # this account's token in its own profile. Auto-activating it as
            # the default login too would put one rotating refresh token in two
            # config dirs (the stale-copy failure class) with nobody reading
            # the warning — and its quota is already being consumed by that
            # session anyway. Manual switch_to keeps its warn-and-proceed
            # behavior; auto skips.
            return "skip-live-session"
        creds = self.read_account_credentials(number, email)
        if not creds:
            return "transient"
        data = oauth.extract_oauth_data(creds)
        if not data:
            return "invalid_grant"
        expires_at = data.get("expiresAt")
        clock = getattr(self, "clock", time.time)
        now_ms = clock() * 1000
        near_expiry = (
            isinstance(expires_at, (int, float))
            and now_ms + FRESHEN_BUFFER_MS >= expires_at
        )
        if not near_expiry:
            return "ok"
        # The consume gate serializes every backup-rt POST (the recovery
        # branch in `_fetch_active_usage` is a second call site, under the
        # same per-slot consume lock):
        # it re-reads under the slot lock (our snapshot may be superseded),
        # consults the session profile for a newer generation, and persists
        # via fingerprint CAS — so a freshen racing the collector (or a
        # sibling surface) can no longer double-consume one grant.
        outcome = self.consume_backup_grant(number, email, creds)
        if outcome.error is None and outcome.credentials:
            # The gate already persisted the successor (or adopted a racing
            # writer's newer lineage) under its own lock.
            if self._note_token_identity(number, outcome.token_account):
                # The slot's stored credential authenticates as a *different*
                # account — activating it would put the user on the wrong
                # account with every gauge reading normal. Not a viable
                # target; the caller quarantines it (released automatically
                # once the credential is replaced by a re-add).
                return "identity-conflict"
            return "ok"
        if outcome.error in ("invalid_grant", "no_refresh_token"):
            return "invalid_grant"
        if outcome.error in _SYSTEMIC_STATUSES:
            # Deterministic conditions, not network trouble: every candidate
            # refuses identically and keeps refusing until something outside
            # this process changes — the shell for store-unmirrored (an
            # inherited CLAUDE_SECURESTORAGE_CONFIG_DIR), our OAuth client
            # registration for invalid_client. Reported distinctly so the tick
            # error names the real cause instead of "(network?)", which would
            # send the user to check a connection that is fine.
            return outcome.error
        return "transient"

    def _note_token_identity(
        self, number: str, token_account: dict | None
    ) -> bool:
        """Use the token endpoint's free identity to verify/backfill a slot.

        The refresh grant just ran against the slot's own stored credential,
        so ``token_account`` (when the server includes it) names who that
        credential really is. Returns True on a *conflict*: the credential
        authenticates under a different organization than the slot records
        (org compared first, whenever both sides record one), or as a
        different account uuid. An empty slot uuid (blank-uuid records from
        older versions, add-token placeholders) is backfilled — but only
        when no org conflict exists: a wrong-org credential is evidence the
        slot holds the wrong account, and backfilling *its* uuid would
        poison the slot's identity record (backfill never rewrites a
        non-empty uuid, so that corruption would be sticky).

        ``_parse_token_account`` already enforces a strict boundary, but this
        identity is opportunistic — re-check types here so malformed data can
        never break the freshen that carried it (the successor credential is
        already persisted by the time this runs).
        """
        if not isinstance(token_account, dict):
            return False
        ta_uuid = token_account.get("uuid")
        if not isinstance(ta_uuid, str) or not ta_uuid.strip():
            return False
        ta_uuid = ta_uuid.strip()
        slot_identity = self.account_identity(number)
        ta_org = token_account.get("organizationUuid")
        slot_org = slot_identity.get("organizationUuid") or ""
        if isinstance(ta_org, str) and ta_org and slot_org and ta_org != slot_org:
            return True
        if not slot_identity.get("uuid"):
            try:
                self.backfill_account_uuid(number, ta_uuid)
            except Exception as e:  # never let bookkeeping break a freshen
                self._logger.debug("uuid backfill failed for account %s: %r", number, e)
            return False
        return slot_identity["uuid"] != ta_uuid
