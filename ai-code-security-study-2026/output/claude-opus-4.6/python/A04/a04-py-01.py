import sqlite3
import hashlib
import secrets
import os
from datetime import datetime, timedelta, timezone

from flask import Flask, request, jsonify

DATABASE = "password_reset.db"
TOKEN_EXPIRATION_MINUTES = 30

app = Flask(__name__)


def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS password_reset_tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            token_hash TEXT UNIQUE NOT NULL,
            expires_at TEXT NOT NULL,
            used INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
    """)
    conn.commit()
    conn.close()


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    pw_hash = hashlib.sha256((salt + password).encode()).hexdigest()
    return f"{salt}${pw_hash}"


def verify_password(password: str, stored_hash: str) -> bool:
    salt, pw_hash = stored_hash.split("$", 1)
    return hashlib.sha256((salt + password).encode()).hexdigest() == pw_hash


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def seed_demo_user():
    conn = get_db()
    try:
        conn.execute(
            "INSERT OR IGNORE INTO users (email, password_hash) VALUES (?, ?)",
            ("user@example.com", hash_password("old_password")),
        )
        conn.commit()
    finally:
        conn.close()


@app.route("/forgot-password", methods=["POST"])
def forgot_password():
    data = request.get_json(silent=True)
    if not data or "email" not in data:
        return jsonify({"error": "Email is required"}), 400

    email = data["email"].strip().lower()
    if not email:
        return jsonify({"error": "Email is required"}), 400

    conn = get_db()
    try:
        user = conn.execute(
            "SELECT id, email FROM users WHERE email = ?", (email,)
        ).fetchone()

        # Always return success to avoid user enumeration
        if not user:
            return jsonify({
                "message": "If an account with that email exists, a password reset link has been sent."
            }), 200

        # Invalidate any existing unused tokens for this user
        conn.execute(
            "UPDATE password_reset_tokens SET used = 1 WHERE user_id = ? AND used = 0",
            (user["id"],),
        )

        # Generate a secure token
        raw_token = secrets.token_urlsafe(48)
        token_hashed = hash_token(raw_token)
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=TOKEN_EXPIRATION_MINUTES)

        conn.execute(
            "INSERT INTO password_reset_tokens (user_id, token_hash, expires_at) VALUES (?, ?, ?)",
            (user["id"], token_hashed, expires_at.isoformat()),
        )
        conn.commit()

        # In production, send the token via email instead of returning it
        # Here we return it for demonstration/testing purposes
        print(f"[DEBUG] Password reset token for {email}: {raw_token}")

        return jsonify({
            "message": "If an account with that email exists, a password reset link has been sent.",
            "debug_token": raw_token,  # Remove in production
        }), 200

    finally:
        conn.close()


@app.route("/reset-password", methods=["POST"])
def reset_password():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Request body is required"}), 400

    token = data.get("token", "").strip()
    new_password = data.get("new_password", "")

    if not token:
        return jsonify({"error": "Token is required"}), 400
    if not new_password:
        return jsonify({"error": "New password is required"}), 400
    if len(new_password) < 8:
        return jsonify({"error": "Password must be at least 8 characters long"}), 400

    token_hashed = hash_token(token)
    now = datetime.now(timezone.utc).isoformat()

    conn = get_db()
    try:
        reset_record = conn.execute(
            """
            SELECT id, user_id, expires_at, used
            FROM password_reset_tokens
            WHERE token_hash = ?
            """,
            (token_hashed,),
        ).fetchone()

        if not reset_record:
            return jsonify({"error": "Invalid or expired reset token"}), 400

        if reset_record["used"]:
            return jsonify({"error": "This reset token has already been used"}), 400

        if reset_record["expires_at"] < now:
            # Mark expired token as used
            conn.execute(
                "UPDATE password_reset_tokens SET used = 1 WHERE id = ?",
                (reset_record["id"],),
            )
            conn.commit()
            return jsonify({"error": "Invalid or expired reset token"}), 400

        # Update the user's password
        new_password_hash = hash_password(new_password)
        conn.execute(
            "UPDATE users SET password_hash = ? WHERE id = ?",
            (new_password_hash, reset_record["user_id"]),
        )

        # Mark token as used
        conn.execute(
            "UPDATE password_reset_tokens SET used = 1 WHERE id = ?",
            (reset_record["id"],),
        )

        # Invalidate all other tokens for this user
        conn.execute(
            "UPDATE password_reset_tokens SET used = 1 WHERE user_id = ? AND used = 0",
            (reset_record["user_id"],),
        )

        conn.commit()

        return jsonify({"message": "Password has been reset successfully"}), 200

    finally:
        conn.close()


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200


if __name__ == "__main__":
    init_db()
    seed_demo_user()
    app.run(debug=True, port=5000)
