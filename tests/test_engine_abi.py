"""Characterization tests for the Extra-facing account-engine ABI.

These tests freeze the surface the menu bar, widget-command path, autoswitch,
and idle-slot kickoff call. Later engine slices must keep them green.

They do not assert Keychain-read counts (Phase 1 changes those).
"""

from __future__ import annotations

import json
from pathlib import Path

from openswap.engine import Engine, SENTINEL_NOTES
from openswap.json_output import USAGE_API_KEY, USAGE_NO_CREDENTIALS, USAGE_RELOGIN_REQUIRED
from openswap.models import AccountSnapshot, AccountsSnapshot, Platform
from openswap.usage_store import FetchRecord

API_KEY = "sk-ant-api03-" + "a1b2c3d4e5" * 4
PERSONAL_ORG = ""
ADS_ORG = "f801c949-0000-0000-0000-000000000002"
EMAIL = "gomryo@example.com"


def _linux_engine() -> Engine:
    s = Engine()
    s.platform = Platform.LINUX
    s._setup_directories()
    s._init_sequence_file()
    return s


def _seed_oauth(
    s: Engine,
    num: int,
    email: str,
    *,
    org_uuid: str,
    org_name: str,
    alias: str = "",
) -> None:
    s._write_account_credentials(
        str(num),
        email,
        json.dumps({
            "claudeAiOauth": {
                "accessToken": f"at-{num}",
                "refreshToken": f"rt-{num}",
            }
        }),
    )
    s._write_account_config(
        str(num),
        email,
        json.dumps({
            "oauthAccount": {
                "emailAddress": email,
                "accountUuid": f"uuid-{num}",
                "organizationUuid": org_uuid,
                "organizationName": org_name,
            }
        }),
    )
    data = s._get_sequence_data() or {}
    data.setdefault("accounts", {})
    data.setdefault("sequence", [])
    data["accounts"][str(num)] = {
        "email": email,
        "uuid": f"uuid-{num}",
        "organizationUuid": org_uuid,
        "organizationName": org_name,
        "added": "2026-01-01T00:00:00Z",
        "alias": alias,
        "kind": "oauth",
    }
    if num not in data["sequence"]:
        data["sequence"].append(num)
        data["sequence"].sort()
    s._write_json(s.sequence_file, data)


def _make_live(
    temp_home: Path,
    email: str,
    *,
    org_uuid: str,
    account_uuid: str,
) -> None:
    (temp_home / ".claude.json").write_text(
        json.dumps({
            "oauthAccount": {
                "emailAddress": email,
                "accountUuid": account_uuid,
                "organizationUuid": org_uuid,
            }
        }),
        encoding="utf-8",
    )
    (temp_home / ".claude" / ".credentials.json").write_text(
        json.dumps({
            "claudeAiOauth": {
                "accessToken": "at-live",
                "refreshToken": "rt-live",
            }
        }),
        encoding="utf-8",
    )


def _two_org_engine(temp_home: Path) -> Engine:
    s = _linux_engine()
    _seed_oauth(
        s, 1, EMAIL, org_uuid=PERSONAL_ORG, org_name="", alias="personal",
    )
    _seed_oauth(
        s, 2, EMAIL, org_uuid=ADS_ORG, org_name="Ads Online", alias="ads",
    )
    _make_live(temp_home, EMAIL, org_uuid=PERSONAL_ORG, account_uuid="uuid-1")
    return s


def test_snapshot_types_and_extra_fields(temp_home: Path) -> None:
    s = _two_org_engine(temp_home)
    snap = s.accounts_snapshot(fetch=set())

    assert isinstance(snap, AccountsSnapshot)
    assert snap.active_number == "1"
    assert len(snap.accounts) == 2
    assert all(isinstance(a, AccountSnapshot) for a in snap.accounts)

    by_num = {a.number: a for a in snap.accounts}
    personal = by_num["1"]
    ads = by_num["2"]

    assert personal.email == EMAIL
    assert personal.org_uuid == PERSONAL_ORG
    assert personal.org_name == ""
    assert personal.display_tag == "personal"
    assert personal.is_active is True
    assert personal.kind == "oauth"
    assert personal.switchable is True
    assert personal.alias == "personal"
    assert personal.disabled is False

    assert ads.email == EMAIL
    assert ads.org_uuid == ADS_ORG
    assert ads.org_name == "Ads Online"
    assert ads.display_tag == "Ads Online"
    assert ads.is_active is False
    assert ads.kind == "oauth"
    assert ads.alias == "ads"


def test_current_slot_is_live_org_not_email_alone(temp_home: Path) -> None:
    s = _two_org_engine(temp_home)
    assert s.current_account_number() == "1"
    assert s.live_identity() == (EMAIL, PERSONAL_ORG)

    _make_live(temp_home, EMAIL, org_uuid=ADS_ORG, account_uuid="uuid-2")
    assert s.current_account_number() == "2"
    assert s.live_identity() == (EMAIL, ADS_ORG)


def test_unmanaged_live_login_is_not_a_slot(temp_home: Path) -> None:
    s = _two_org_engine(temp_home)
    _make_live(
        temp_home,
        "other@example.com",
        org_uuid=PERSONAL_ORG,
        account_uuid="uuid-x",
    )
    assert s.has_live_login() is True
    assert s.current_account_number() is None


def test_disable_shows_on_snapshot_and_stays_switch_target(temp_home: Path) -> None:
    s = _two_org_engine(temp_home)
    s.set_account_disabled("2", True)
    snap = s.accounts_snapshot(fetch=set())
    ads = next(a for a in snap.accounts if a.number == "2")
    assert ads.disabled is True
    assert "2" not in s.switchable_account_numbers()
    assert s.account_kind_for("2") == "oauth"
    assert s.account_email("2") == EMAIL


def test_api_key_slot_kind_and_usage_sentinel(temp_home: Path) -> None:
    s = _linux_engine()
    s.add_account_from_token(API_KEY, email="key@example.com")
    snap = s.accounts_snapshot(fetch=set())
    acc = snap.accounts[0]
    assert acc.kind == "api_key"
    assert acc.usage.sentinel == USAGE_API_KEY
    assert s.account_kind_for("1") == "api_key"


def test_switch_to_already_active_json_is_not_switched(temp_home: Path) -> None:
    s = _two_org_engine(temp_home)
    result = s.switch_to("1", json_output=True)
    assert result is not None
    assert result["switched"] is False
    assert result.get("reason") == "already-active"


def test_extra_sentinel_notes_cover_relogin_and_api_key() -> None:
    assert USAGE_RELOGIN_REQUIRED in SENTINEL_NOTES
    assert USAGE_API_KEY in SENTINEL_NOTES
    assert SENTINEL_NOTES[USAGE_RELOGIN_REQUIRED]
    assert SENTINEL_NOTES[USAGE_API_KEY]


def test_store_only_snapshot_keeps_seeded_last_good(temp_home: Path) -> None:
    s = _two_org_engine(temp_home)
    usage = {
        "five_hour": {"pct": 12.0, "resets_at": "2099-01-01T00:00:00Z"},
        "seven_day": {"pct": 4.0, "resets_at": "2099-01-08T00:00:00Z"},
    }
    s._usage_store.record(
        {"1": FetchRecord(usage=usage)},
        identities={"1": (EMAIL, PERSONAL_ORG)},
    )
    snap = s.accounts_snapshot(fetch=set())
    personal = next(a for a in snap.accounts if a.number == "1")
    assert personal.usage.sentinel is None
    assert personal.usage.last_good is not None
    assert personal.usage.last_good["five_hour"]["pct"] == 12.0


def test_store_only_snapshot_does_not_read_idle_backup(temp_home: Path) -> None:
    s = _two_org_engine(temp_home)
    backup_reads: list[tuple[str, str]] = []
    live_reads: list[int] = []
    orig_backup = s._read_account_credentials
    orig_ex = s._read_account_credentials_ex
    orig_live = s._read_active_credentials

    def spy_backup(num, email, *a, **k):
        backup_reads.append((str(num), email))
        return orig_backup(num, email, *a, **k)

    def spy_ex(num, email, *a, **k):
        backup_reads.append((str(num), email))
        return orig_ex(num, email, *a, **k)

    def spy_live():
        live_reads.append(1)
        return orig_live()

    s._read_account_credentials = spy_backup
    s._read_account_credentials_ex = spy_ex
    s._read_active_credentials = spy_live

    snap = s.accounts_snapshot(fetch=set())
    ads = next(a for a in snap.accounts if a.number == "2")
    personal = next(a for a in snap.accounts if a.number == "1")
    assert ads.email == EMAIL
    assert ads.org_uuid == ADS_ORG
    assert ads.kind == "oauth"
    assert ads.switchable is True
    assert personal.switchable is True
    assert ads.usage.sentinel != USAGE_NO_CREDENTIALS
    assert backup_reads == []
    assert len(live_reads) <= 1


def test_unread_idle_is_not_no_credentials(temp_home: Path) -> None:
    s = _two_org_engine(temp_home)
    snap = s.accounts_snapshot(fetch=set())
    ads = next(a for a in snap.accounts if a.number == "2")
    assert ads.usage.sentinel is None or ads.usage.sentinel != USAGE_NO_CREDENTIALS
