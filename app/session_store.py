"""Opaque, server-side session primitives.

This module is groundwork only: no HTTP login routes call it yet. The browser
would receive the random token once in a Secure/HttpOnly cookie; only its hash
is stored here. OIDC validation and authorization must happen before creating
a session.
"""
from __future__ import annotations

from hashlib import sha256
import secrets
import time

from app import db


def _digest(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


def create_session(subject: str, ttl_seconds: int = 3600) -> dict[str, str | int]:
    """Create a session for an already-validated and allowlisted subject."""
    if not subject or not subject.strip():
        raise ValueError("subject must be non-empty")
    if isinstance(ttl_seconds, bool) or not isinstance(ttl_seconds, int) or not 1 <= ttl_seconds <= 86400:
        raise ValueError("ttl_seconds must be between 1 and 86400")

    token = secrets.token_urlsafe(32)
    csrf_token = secrets.token_urlsafe(32)
    now = int(time.time())
    expires_at = now + ttl_seconds
    with db.connect() as connection:
        connection.execute(
            """INSERT INTO auth_sessions
               (token_hash, subject, csrf_hash, created_at, expires_at, revoked_at)
               VALUES (?, ?, ?, ?, ?, NULL)""",
            (_digest(token), subject, _digest(csrf_token), now, expires_at),
        )
    return {"token": token, "csrf_token": csrf_token, "expires_at": expires_at}


def get_session(token: str | None, now: int | None = None) -> dict[str, str | int] | None:
    """Return non-secret session metadata for a live token, never the raw token."""
    if not token:
        return None
    current = int(time.time()) if now is None else now
    with db.connect() as connection:
        row = connection.execute(
            """SELECT subject, csrf_hash, created_at, expires_at
               FROM auth_sessions
               WHERE token_hash = ? AND revoked_at IS NULL AND expires_at > ?""",
            (_digest(token), current),
        ).fetchone()
    if row is None:
        return None
    return {
        "subject": row["subject"],
        "csrf_hash": row["csrf_hash"],
        "created_at": row["created_at"],
        "expires_at": row["expires_at"],
    }


def verify_csrf(session: dict[str, str | int], csrf_token: str | None) -> bool:
    """Constant-time comparison of the supplied CSRF token with stored hash."""
    import hmac

    if not csrf_token:
        return False
    return hmac.compare_digest(str(session["csrf_hash"]), _digest(csrf_token))


def revoke_session(token: str | None, now: int | None = None) -> bool:
    """Revoke a session by opaque token; raw tokens are never persisted."""
    if not token:
        return False
    current = int(time.time()) if now is None else now
    with db.connect() as connection:
        cursor = connection.execute(
            """UPDATE auth_sessions SET revoked_at = ?
               WHERE token_hash = ? AND revoked_at IS NULL""",
            (current, _digest(token)),
        )
    return cursor.rowcount == 1
