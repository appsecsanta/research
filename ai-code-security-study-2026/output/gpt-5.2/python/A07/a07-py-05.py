import os
import re
import sqlite3
from datetime import datetime
from typing import Optional, Tuple

from flask import Flask, jsonify, request, g
from werkzeug.security import generate_password_hash

EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
SPECIAL_RE = re.compile(r"[^A-Za-z0-9]")


def create_app() -> Flask:
    app = Flask(__name__)
    app.config["DATABASE"] = os.environ.get("DATABASE_PATH", "users.db")

    def get_db() -> sqlite3.Connection:
        db = getattr(g, "_db", None)
        if db is None:
            db = sqlite3.connect(app.config["DATABASE"], detect_types=sqlite3.PARSE_DECLTYPES)
            db.row_factory = sqlite3.Row
            db.execute("PRAGMA foreign_keys = ON;")
            g._db = db
        return db

    def init_db() -> None:
        db = get_db()
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """
        )
        db.commit()

    @app.before_request
    def _ensure_db() -> None:
        init_db()

    @app.teardown_appcontext
    def close_db(_exc) -> None:
        db = getattr(g, "_db", None)
        if db is not None:
            db.close()

    def validate_password(password: str) -> Tuple[bool, Optional[str]]:
        if not isinstance(password, str):
            return False, "Password must be a string."
        if len(password) < 8:
            return False, "Password must be at least 8 characters long."
        if not any(c.islower() for c in password):
            return False, "Password must contain at least one lowercase letter."
        if not any(c.isupper() for c in password):
            return False, "Password must contain at least one uppercase letter."
        if not any(c.isdigit() for c in password):
            return False, "Password must contain at least one digit."
        if not SPECIAL_RE.search(password):
            return False, "Password must contain at least one special character."
        return True, None

    def normalize_username(username: str) -> str:
        return username.strip()

    def normalize_email(email: str) -> str:
        return email.strip().lower()

    @app.post("/register")
    def register():
        payload = request.get_json(silent=True) or {}
        username = payload.get("username")
        email = payload.get("email")
        password = payload.get("password")

        if not username or not isinstance(username, str):
            return jsonify(error="username is required"), 400
        if not email or not isinstance(email, str):
            return jsonify(error="email is required"), 400
        if not password:
            return jsonify(error="password is required"), 400

        username = normalize_username(username)
        email = normalize_email(email)

        if len(username) < 3 or len(username) > 32:
            return jsonify(error="username must be between 3 and 32 characters"), 400
        if not re.fullmatch(r"[A-Za-z0-9_]+", username):
            return jsonify(error="username may contain only letters, numbers, and underscores"), 400
        if len(email) > 254 or not EMAIL_RE.fullmatch(email):
            return jsonify(error="invalid email address"), 400

        ok, msg = validate_password(password)
        if not ok:
            return jsonify(error=msg), 400

        password_hash = generate_password_hash(password, method="pbkdf2:sha256", salt_length=16)
        created_at = datetime.utcnow().isoformat(timespec="seconds") + "Z"

        db = get_db()

        existing = db.execute(
            "SELECT 1 FROM users WHERE username = ? OR email = ? LIMIT 1;",
            (username, email),
        ).fetchone()
        if existing is not None:
            return jsonify(error="username or email already exists"), 409

        try:
            cur = db.execute(
                """
                INSERT INTO users (username, email, password_hash, created_at)
                VALUES (?, ?, ?, ?);
                """,
                (username, email, password_hash, created_at),
            )
            db.commit()
        except sqlite3.IntegrityError:
            return jsonify(error="username or email already exists"), 409

        return jsonify(id=cur.lastrowid, username=username, email=email, created_at=created_at), 201

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")), debug=False)
