import json
from pathlib import Path
import pytest
from openswap.codex.engine import CodexEngine, CodexAuthError, CodexSwitchError
from openswap.engine.protocol import AccountEngine
from openswap.json_output import USAGE_API_KEY, USAGE_NO_CREDENTIALS
from tests.test_codex_auth import _auth

def _engine(tmp_path, limits=None, codex_bin="/opt/codex"):
    calls = []
    def read_limits(home, *, codex_bin, **kw):
        calls.append(Path(home))
        if isinstance(limits, Exception):
            raise limits
        return limits or {"primary": {"usedPercent": 10, "windowDurationMins": 300, "resetsAt": 1788265323},
                          "secondary": {"usedPercent": 20, "windowDurationMins": 10080, "resetsAt": 1788765541}}
    home = tmp_path / "codex-home"
    eng = CodexEngine(backup_dir=tmp_path / "backup", home=home,
                      codex_bin=lambda: codex_bin, read_limits=read_limits, clock=lambda: 1_788_000_000.0)
    eng._test_calls = calls
    return eng, home

def _login(home: Path, **kw) -> None:
    home.mkdir(parents=True, exist_ok=True)
    (home / "auth.json").write_text(_auth(**kw))

def test_satisfies_protocol(tmp_path):
    eng, _ = _engine(tmp_path)
    assert isinstance(eng, AccountEngine) and eng.provider == "codex"

def test_add_captures_live_login_into_slot_dir(tmp_path):
    eng, home = _engine(tmp_path)
    _login(home, email="a@x.com", account_id="acc-a")
    num = eng.add_account()
    assert num == "1"
    slot = eng.slots_dir / "1" / "auth.json"
    assert slot.read_text() == (home / "auth.json").read_text()
    assert oct(slot.stat().st_mode & 0o777) == "0o600"
    assert eng.current_account_number() == "1"
    assert eng.live_identity() == ("a@x.com", "acc-a")
    assert eng.slot_identity("1") == ("a@x.com", "acc-a")

def test_add_refuses_missing_and_duplicate(tmp_path):
    eng, home = _engine(tmp_path)
    with pytest.raises(CodexAuthError, match="codex login"):
        eng.add_account()
    _login(home)
    eng.add_account()
    with pytest.raises(CodexAuthError, match="already"):
        eng.add_account()

def test_switch_to_writes_live_and_captures_outgoing(tmp_path):
    eng, home = _engine(tmp_path)
    _login(home, email="a@x.com", account_id="acc-a", refresh="rt-a1")
    eng.add_account()
    _login(home, email="b@x.com", account_id="acc-b")
    eng.add_account()
    # Codex refreshed the live (b) token since we captured it:
    _login(home, email="b@x.com", account_id="acc-b", refresh="rt-b2")
    result = eng.switch_to("1", json_output=True)
    assert result["switched"] is True
    assert result["to"] == {"number": "1", "email": "a@x.com"}
    assert result["from"] == {"number": "2", "email": "b@x.com"}
    assert "rt-a1" in (home / "auth.json").read_text()
    assert "rt-b2" in (eng.slots_dir / "2" / "auth.json").read_text()   # newest generation kept
    assert eng.current_account_number() == "1"

def test_switch_to_same_slot_is_already_active(tmp_path):
    eng, home = _engine(tmp_path)
    _login(home); eng.add_account()
    assert eng.switch_to("1", json_output=True)["reason"] == "already-active"

def test_switch_refuses_unmanaged_live_login_unless_forced(tmp_path):
    eng, home = _engine(tmp_path)
    _login(home, email="a@x.com", account_id="acc-a"); eng.add_account()
    _login(home, email="stranger@x.com", account_id="acc-s")
    with pytest.raises(CodexSwitchError, match="not managed"):
        eng.switch_to("1", json_output=True)
    assert eng.switch_to("1", json_output=True, force=True)["switched"] is True

def test_rotate_skips_disabled_and_wraps(tmp_path):
    eng, home = _engine(tmp_path)
    for e in ("a", "b", "c"):
        _login(home, email=f"{e}@x.com", account_id=f"acc-{e}"); eng.add_account()
    eng.switch_to("1", json_output=True)
    eng.set_account_disabled("2", True)
    assert eng.switch(json_output=True)["to"]["number"] == "3"
    assert eng.switch(json_output=True)["to"]["number"] == "1"
    assert eng.switchable_account_numbers() == ["1", "3"]

def test_snapshot_reads_idle_slot_from_its_own_home(tmp_path):
    eng, home = _engine(tmp_path)
    _login(home, email="a@x.com", account_id="acc-a"); eng.add_account()
    _login(home, email="b@x.com", account_id="acc-b"); eng.add_account()
    snap = eng.accounts_snapshot(fetch=None)
    assert [a.number for a in snap.accounts] == ["1", "2"]
    assert snap.active_number == "2"
    assert all(a.provider == "codex" for a in snap.accounts)
    assert snap.accounts[0].usage.last_good["five_hour"]["pct"] == 10.0
    assert snap.accounts[0].org_name == "plus" and snap.accounts[0].org_uuid == "acc-a"
    assert set(eng._test_calls) == {eng.slots_dir / "1", home}

def test_snapshot_store_only_never_calls_codex(tmp_path):
    eng, home = _engine(tmp_path)
    _login(home); eng.add_account()
    eng.accounts_snapshot(fetch=set())
    assert eng._test_calls == []

def test_api_key_slot_is_switchable_but_has_no_bars(tmp_path):
    eng, home = _engine(tmp_path)
    home.mkdir()
    (home / "auth.json").write_text(json.dumps({"auth_mode": "apiKey", "OPENAI_API_KEY": "sk"}))
    eng.add_account()
    snap = eng.accounts_snapshot()
    assert eng.account_kind_for("1") == "api_key"
    assert snap.accounts[0].usage.sentinel == USAGE_API_KEY
    assert snap.accounts[0].switchable is True
    assert eng._test_calls == []          # never asks app-server for an API key

def test_missing_slot_file_is_no_credentials(tmp_path):
    eng, home = _engine(tmp_path)
    _login(home); eng.add_account()
    (eng.slots_dir / "1" / "auth.json").unlink()
    snap = eng.accounts_snapshot()
    assert snap.accounts[0].usage.sentinel == USAGE_NO_CREDENTIALS
    assert snap.accounts[0].switchable is False
    assert eng.switchable_account_numbers() == []

def test_snapshot_records_failure_and_keeps_last_good(tmp_path):
    eng, home = _engine(tmp_path)
    _login(home); eng.add_account()
    good = eng.accounts_snapshot().accounts[0].usage.last_good
    eng._read_limits = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom"))
    eng._usage_store.clock = lambda: 1_788_001_000.0   # past SERVE_TTL_S
    snap = eng.accounts_snapshot()
    assert snap.accounts[0].usage.last_good == good
    assert snap.accounts[0].usage.last_error

def test_codex_not_installed_is_reported_not_raised(tmp_path):
    eng, home = _engine(tmp_path, codex_bin=None)
    _login(home); eng.add_account()
    snap = eng.accounts_snapshot()
    assert snap.accounts[0].usage.last_error == "codex-not-installed"

def test_freshen_backup_is_ok(tmp_path):
    eng, home = _engine(tmp_path)
    _login(home); eng.add_account()
    assert eng.freshen_backup("1", "a@x.com") == "ok"

def test_alias_and_remove(tmp_path):
    eng, home = _engine(tmp_path)
    _login(home, email="a@x.com"); eng.add_account()
    eng.set_alias("1", "work")
    assert eng.list_aliases() == [("1", "work", "a@x.com")]
    assert eng.resolve_account("work")[0] == "1"
    eng.remove_account("work", assume_yes=True)
    assert eng.accounts_snapshot(fetch=set()).accounts == ()
    assert not (eng.slots_dir / "1").exists()
