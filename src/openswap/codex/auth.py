"""Codex CLI ``auth.json``: location, identity, fingerprint. Pure; no I/O beyond paths."""

from __future__ import annotations

import base64
import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

CODEX_HOME_ENV = "CODEX_HOME"
AUTH_FILENAME = "auth.json"
OPENAI_AUTH_CLAIM = "https://api.openai.com/auth"


@dataclass(frozen=True)
class CodexIdentity:
    email: str
    account_id: str
    plan_type: str
    kind: str  # "oauth" | "api_key"


def codex_home(environ: Mapping[str, str] | None = None) -> Path:
    env = os.environ if environ is None else environ
    value = env.get(CODEX_HOME_ENV)
    return Path(value) if value else Path.home() / ".codex"


def auth_path(home: Path) -> Path:
    return home / AUTH_FILENAME


def decode_jwt_claims(token: str) -> dict:
    """Payload of a JWT without verifying it; ``{}`` on any malformation."""
    try:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        data = json.loads(base64.urlsafe_b64decode(payload))
    except (IndexError, ValueError, TypeError):
        return {}
    return data if isinstance(data, dict) else {}


def _load(text: str) -> dict | None:
    try:
        data = json.loads(text) if text else None
    except (json.JSONDecodeError, TypeError):
        return None
    return data if isinstance(data, dict) else None


def parse_auth(text: str) -> CodexIdentity | None:
    data = _load(text)
    if not data:
        return None
    tokens = data.get("tokens") if isinstance(data.get("tokens"), dict) else {}
    id_token = tokens.get("id_token") if tokens else None
    if isinstance(id_token, str) and id_token:
        claims = decode_jwt_claims(id_token)
        auth = claims.get(OPENAI_AUTH_CLAIM) or {}
        account_id = tokens.get("account_id") or auth.get("chatgpt_account_id") or ""
        return CodexIdentity(
            email=str(claims.get("email") or ""),
            account_id=str(account_id),
            plan_type=str(auth.get("chatgpt_plan_type") or ""),
            kind="oauth",
        )
    if data.get("auth_mode") == "apiKey" or data.get("OPENAI_API_KEY"):
        return CodexIdentity(email="", account_id="", plan_type="", kind="api_key")
    return None


def auth_fingerprint(text: str) -> str | None:
    """Refresh-token hash when present, full-content hash otherwise, None for empty."""
    if not text:
        return None
    data = _load(text) or {}
    tokens = data.get("tokens") if isinstance(data.get("tokens"), dict) else {}
    refresh = tokens.get("refresh_token") if tokens else None
    if isinstance(refresh, str) and refresh:
        return "sha256:" + hashlib.sha256(refresh.encode()).hexdigest()
    return "sha256-full:" + hashlib.sha256(text.encode()).hexdigest()
