"""Approval token generation and verification for schema changes."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import time

_USED_TOKENS: set[str] = set()


def reset_used_tokens() -> None:
    _USED_TOKENS.clear()


def _secret_value(secret: str | None = None) -> str:
    value = secret if secret is not None else os.getenv("APPROVAL_SECRET", "dev-secret")
    if not value:
        raise ValueError("APPROVAL_SECRET must not be empty.")
    return str(value)


def _hash_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _build_signing_input(proposal_id: str, ddl_hash: str, nonce: str, expires_at: int) -> str:
    return f"{proposal_id}|{ddl_hash}|{nonce}|{expires_at}"


def issue_token(
    proposal_id: str,
    ddl: str,
    *,
    secret: str | None = None,
    expires_in: int = 600,
    now: int | None = None,
) -> str:
    """Create an HMAC-based approval token for one DDL proposal."""

    if not proposal_id:
        raise ValueError("proposal_id is required.")
    if not ddl or not ddl.strip():
        raise ValueError("ddl is required.")

    current_time = int(time.time()) if now is None else int(now)
    nonce = secrets.token_hex(16)
    ddl_hash = _hash_text(ddl)
    expires_at = current_time + int(expires_in)
    signing_input = _build_signing_input(str(proposal_id), ddl_hash, nonce, expires_at)
    signature = hmac.new(
        _secret_value(secret).encode("utf-8"),
        signing_input.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    payload = {
        "proposal_id": str(proposal_id),
        "ddl_hash": ddl_hash,
        "nonce": nonce,
        "expires_at": expires_at,
        "signature": signature,
    }
    return json.dumps(payload, separators=(",", ":"), sort_keys=True)


def verify_token(
    token: str,
    proposal_id: str,
    ddl: str,
    *,
    secret: str | None = None,
    now: int | None = None,
) -> bool:
    """Verify a token is valid, unexpired, and unused for the given proposal and DDL."""

    if not token:
        return False

    try:
        payload = json.loads(token)
    except (TypeError, ValueError):
        return False

    required_keys = {"proposal_id", "ddl_hash", "nonce", "expires_at", "signature"}
    if not isinstance(payload, dict) or not required_keys.issubset(payload):
        return False

    if str(payload.get("proposal_id")) != str(proposal_id):
        return False

    ddl_hash = _hash_text(ddl)
    if str(payload.get("ddl_hash")) != ddl_hash:
        return False

    current_time = int(time.time()) if now is None else int(now)
    expires_at = int(payload.get("expires_at", 0))
    if current_time > expires_at:
        return False

    signing_input = _build_signing_input(
        str(payload.get("proposal_id")),
        str(payload.get("ddl_hash")),
        str(payload.get("nonce")),
        expires_at,
    )
    expected = hmac.new(
        _secret_value(secret).encode("utf-8"),
        signing_input.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(str(payload.get("signature", "")), expected):
        return False

    token_key = json.dumps(payload, separators=(",", ":"), sort_keys=True)
    if token_key in _USED_TOKENS:
        return False

    _USED_TOKENS.add(token_key)
    return True


generate_approval_token = issue_token
validate_approval_token = verify_token
__all__ = [
    "issue_token",
    "verify_token",
    "generate_approval_token",
    "validate_approval_token",
    "reset_used_tokens",
]

