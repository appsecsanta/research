import hashlib
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Optional


def init_db(db_path: str = "password_reset.db") -> sqlite3.Connection:
    """Initialize the database and create the password_reset_tokens table."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS password_reset_tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL,
            token_hash TEXT NOT NULL UNIQUE,
            expires_at TEXT NOT NULL,
            used INTEGER DEFAULT 0,
            created_at TEXT NOT NULL
        )
    """)
    conn.commit()
    return conn


def _hash_token(token: str) -> str:
    """Hash a token using SHA-256 for secure storage."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def generate_reset_token(
    conn: sqlite3.Connection,
    email: str,
    expiration_minutes: int = 30,
) -> str:
    """
    Generate a unique password reset token for the given email.

    The token is stored as a SHA-256 hash in the database alongside the user's
    email and an expiration timestamp. The raw token is returned so it can be
    included in the reset link sent to the user.

    Args:
        conn: Active SQLite database connection.
        email: The user's email address.
        expiration_minutes: How many minutes until the token expires.

    Returns:
        The raw token string to be embedded in the reset link.
    """
    email = email.strip().lower()

    # Invalidate any existing unused tokens for this email
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE password_reset_tokens SET used = 1 WHERE email = ? AND used = 0",
        (email,),
    )

    # Generate a cryptographically secure token
    raw_token = secrets.token_urlsafe(48)
    token_hash = _hash_token(raw_token)

    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(minutes=expiration_minutes)

    cursor.execute(
        """
        INSERT INTO password_reset_tokens (email, token_hash, expires_at, created_at)
        VALUES (?, ?, ?, ?)
        """,
        (
            email,
            token_hash,
            expires_at.isoformat(),
            now.isoformat(),
        ),
    )
    conn.commit()

    return raw_token


def validate_reset_token(
    conn: sqlite3.Connection,
    token: str,
) -> Optional[str]:
    """
    Validate a password reset token.

    Checks that the token exists, has not been used, and has not expired.
    If valid, marks the token as used and returns the associated email.

    Args:
        conn: Active SQLite database connection.
        token: The raw token string from the reset link.

    Returns:
        The email associated with the token if valid, or None if invalid/expired.
    """
    token_hash = _hash_token(token)

    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id, email, expires_at, used
        FROM password_reset_tokens
        WHERE token_hash = ?
        """,
        (token_hash,),
    )
    row = cursor.fetchone()

    if row is None:
        return None

    token_id, email, expires_at_str, used = row

    if used:
        return None

    expires_at = datetime.fromisoformat(expires_at_str)
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    if datetime.now(timezone.utc) > expires_at:
        # Mark expired token as used to keep the table clean
        cursor.execute(
            "UPDATE password_reset_tokens SET used = 1 WHERE id = ?",
            (token_id,),
        )
        conn.commit()
        return None

    # Mark token as used (single-use)
    cursor.execute(
        "UPDATE password_reset_tokens SET used = 1 WHERE id = ?",
        (token_id,),
    )
    conn.commit()

    return email


def cleanup_expired_tokens(conn: sqlite3.Connection) -> int:
    """
    Remove expired and used tokens from the database.

    Returns:
        The number of rows deleted.
    """
    cursor = conn.cursor()
    now = datetime.now(timezone.utc).isoformat()
    cursor.execute(
        """
        DELETE FROM password_reset_tokens
        WHERE used = 1 OR expires_at < ?
        """,
        (now,),
    )
    deleted = cursor.rowcount
    conn.commit()
    return deleted


# ---------------------------------------------------------------------------
# Demo / manual test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import time

    db_conn = init_db(":memory:")

    user_email = "user@example.com"

    # Generate a token
    token = generate_reset_token(db_conn, user_email, expiration_minutes=1)
    print(f"Generated token for {user_email}: {token}")

    # Validate the token
    result_email = validate_reset_token(db_conn, token)
    if result_email:
        print(f"Token is valid for: {result_email}")
    else:
        print("Token is invalid or expired.")

    # Try to reuse the same token (should fail — single use)
    result_email = validate_reset_token(db_conn, token)
    if result_email:
        print(f"Token is valid for: {result_email}")
    else:
        print("Token reuse rejected (already used).")

    # Generate another token and let it expire
    short_token = generate_reset_token(db_conn, user_email, expiration_minutes=0)
    print(f"\nGenerated short-lived token: {short_token}")
    time.sleep(1)
    result_email = validate_reset_token(db_conn, short_token)
    if result_email:
        print(f"Token is valid for: {result_email}")
    else:
        print("Token correctly identified as expired.")

    # Cleanup
    deleted = cleanup_expired_tokens(db_conn)
    print(f"\nCleaned up {deleted} expired/used token(s).")

    db_conn.close()
