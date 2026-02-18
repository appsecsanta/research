from __future__ import annotations

import hashlib
import hmac
import secrets
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional


def init_password_reset_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS password_reset_tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL,
            token_hash TEXT NOT NULL UNIQUE,
            created_at INTEGER NOT NULL,
            expires_at INTEGER NOT NULL,
            used_at INTEGER
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_password_reset_tokens_email ON password_reset_tokens(email)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_password_reset_tokens_expires_at ON password_reset_tokens(expires_at)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_password_reset_tokens_used_at ON password_reset_tokens(used_at)"
    )
    conn.commit()


@dataclass(frozen=True)
class PasswordResetToken:
    email: str
    token: str
    expires_at: datetime


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _to_unix_seconds(dt: datetime) -> int:
    if dt.tzinfo is None:
        raise ValueError("datetime must be timezone-aware")
    return int(dt.timestamp())


def _token_hash(token: str, secret_key: str) -> str:
    if not token:
        raise ValueError("token must not be empty")
    if not secret_key:
        raise ValueError("secret_key must not be empty")
    digest = hmac.new(secret_key.encode("utf-8"), token.encode("utf-8"), hashlib.sha256).hexdigest()
    return digest


def cleanup_expired_password_reset_tokens(conn: sqlite3.Connection, *, now: Optional[datetime] = None) -> int:
    now_dt = now or _utc_now()
    now_ts = _to_unix_seconds(now_dt)
    cur = conn.execute("DELETE FROM password_reset_tokens WHERE expires_at <= ?", (now_ts,))
    conn.commit()
    return cur.rowcount


def generate_password_reset_token(
    conn: sqlite3.Connection,
    *,
    email: str,
    secret_key: str,
    ttl: timedelta = timedelta(hours=1),
    now: Optional[datetime] = None,
    token_bytes: int = 32,
) -> PasswordResetToken:
    if not email:
        raise ValueError("email must not be empty")
    if ttl.total_seconds() <= 0:
        raise ValueError("ttl must be positive")
    if token_bytes < 16:
        raise ValueError("token_bytes must be >= 16")

    now_dt = now or _utc_now()
    expires_dt = now_dt + ttl

    raw_token = secrets.token_urlsafe(token_bytes)
    hashed = _token_hash(raw_token, secret_key)

    with conn:
        conn.execute(
            """
            INSERT INTO password_reset_tokens (email, token_hash, created_at, expires_at, used_at)
            VALUES (?, ?, ?, ?, NULL)
            """,
            (email, hashed, _to_unix_seconds(now_dt), _to_unix_seconds(expires_dt)),
        )

    return PasswordResetToken(email=email, token=raw_token, expires_at=expires_dt)


def validate_password_reset_token(
    conn: sqlite3.Connection,
    *,
    token: str,
    secret_key: str,
    now: Optional[datetime] = None,
    consume: bool = True,
) -> Optional[str]:
    """
    Returns the associated email if token is valid (not expired, not used), otherwise None.
    If consume=True, marks the token as used on successful validation.
    """
    if not token:
        return None
    if not secret_key:
        raise ValueError("secret_key must not be empty")

    now_dt = now or _utc_now()
    now_ts = _to_unix_seconds(now_dt)
    hashed = _token_hash(token, secret_key)

    row = conn.execute(
        """
        SELECT id, email, expires_at, used_at
        FROM password_reset_tokens
        WHERE token_hash = ?
        """,
        (hashed,),
    ).fetchone()

    if row is None:
        return None

    token_id, email, expires_at, used_at = row
    if used_at is not None:
        return None
    if expires_at <= now_ts:
        return None

    if consume:
        with conn:
            updated = conn.execute(
                """
                UPDATE password_reset_tokens
                SET used_at = ?
                WHERE id = ? AND used_at IS NULL AND expires_at > ?
                """,
                (now_ts, token_id, now_ts),
            ).rowcount
        if updated != 1:
            return None

    return email
