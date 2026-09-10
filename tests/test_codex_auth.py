import base64, json
from pathlib import Path
from openswap.codex import split_provider_num
from openswap.codex.auth import (
    CodexIdentity, auth_fingerprint, auth_path, codex_home, decode_jwt_claims,
    parse_auth,
)

def _jwt(claims: dict) -> str:
    def b64(obj):
        raw = json.dumps(obj).encode()
        return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()
    return f"{b64({'alg': 'none'})}.{b64(claims)}.sig"

def _auth(email="a@x.com", account_id="acc-1", plan="plus", refresh="rt-1") -> str:
    claims = {"email": email, "https://api.openai.com/auth": {
        "chatgpt_account_id": account_id, "chatgpt_plan_type": plan}}
    return json.dumps({
        "auth_mode": "chatgpt", "OPENAI_API_KEY": None,
        "tokens": {"id_token": _jwt(claims), "access_token": "at",
                   "refresh_token": refresh, "account_id": account_id},
        "last_refresh": "2026-09-10T00:00:00Z",
    })

def test_codex_home_env_and_default(monkeypatch, tmp_path):
    assert codex_home({"CODEX_HOME": str(tmp_path)}) == tmp_path
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    assert codex_home({}) == tmp_path / ".codex"
    assert auth_path(tmp_path) == tmp_path / "auth.json"

def test_decode_jwt_claims_tolerates_garbage():
    assert decode_jwt_claims("not.a.jwt") == {}
    assert decode_jwt_claims("") == {}
    assert decode_jwt_claims(_jwt({"email": "e"}))["email"] == "e"

def test_parse_auth_oauth_identity():
    ident = parse_auth(_auth())
    assert ident == CodexIdentity(email="a@x.com", account_id="acc-1",
                                  plan_type="plus", kind="oauth")

def test_parse_auth_api_key_identity():
    text = json.dumps({"auth_mode": "apiKey", "OPENAI_API_KEY": "sk-x", "tokens": None})
    ident = parse_auth(text)
    assert ident.kind == "api_key" and ident.email == "" and ident.account_id == ""

def test_parse_auth_returns_none_for_junk():
    assert parse_auth("") is None
    assert parse_auth("{}") is None
    assert parse_auth("{not json") is None

def test_fingerprint_tracks_refresh_token():
    assert auth_fingerprint(_auth(refresh="a")) == auth_fingerprint(_auth(refresh="a", plan="pro"))
    assert auth_fingerprint(_auth(refresh="a")) != auth_fingerprint(_auth(refresh="b"))
    assert auth_fingerprint("") is None

def test_split_provider_num():
    assert split_provider_num("codex:2") == ("codex", "2")
    assert split_provider_num(3) == ("claude", "3")
    assert split_provider_num("3") == ("claude", "3")
