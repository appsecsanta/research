import os
import secrets
import sqlite3
import time
from datetime import datetime, timezone
from functools import wraps
from pathlib import Path
from typing import Optional, Tuple

import click
from flask import (
    Flask,
    abort,
    flash,
    g,
    redirect,
    render_template_string,
    request,
    session,
    url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash


BASE_DIR = Path(__file__).resolve().parent
DB_PATH = os.environ.get("AUTH_DB_PATH", str(BASE_DIR / "auth.sqlite3"))

MAX_FAILED_ATTEMPTS = int(os.environ.get("AUTH_MAX_FAILED_ATTEMPTS", "5"))
FAIL_WINDOW_SECONDS = int(os.environ.get("AUTH_FAIL_WINDOW_SECONDS", str(10 * 60)))
BLOCK_SECONDS = int(os.environ.get("AUTH_BLOCK_SECONDS", str(15 * 60)))


LOGIN_TEMPLATE = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>Login</title>
  <style>
    body { font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif; margin: 40px; }
    .box { max-width: 420px; padding: 20px; border: 1px solid #ddd; border-radius: 8px; }
    label { display: block; margin-top: 12px; }
    input { width: 100%; padding: 10px; margin-top: 6px; box-sizing: border-box; }
    button { margin-top: 16px; padding: 10px 14px; }
    .msg { margin: 12px 0; padding: 10px; border-radius: 6px; }
    .err { background: #ffecec; border: 1px solid #f5b5b5; }
    .ok  { background: #ecfff0; border: 1px solid #b5f5c0; }
    .warn { background: #fff8e6; border: 1px solid #f1d28a; }
  </style>
</head>
<body>
  <div class="box">
    <h1>Login</h1>

    {% with messages = get_flashed_messages(with_categories=true) %}
      {% if messages %}
        {% for category, message in messages %}
          <div class="msg {{ category|e }}">{{ message|e }}</div>
        {% endfor %}
      {% endif %}
    {% endwith %}

    <form method="post" action="{{ url_for('login') }}" autocomplete="off">
      <input type="hidden" name="csrf_token" value="{{ csrf_token|e }}" />
      <label for="username">Username</label>
      <input id="username" name="username" required />

      <label for="password">Password</label>
      <input id="password" name="password" type="password" required />

      <button type="submit">Sign in</button>
    </form>

    {% if session.get('user') %}
      <p>Signed in as <strong>{{ session.get('user')|e }}</strong></p>
      <p><a href="{{ url_for('protected') }}">Go to protected page</a></p>
      <p><a href="{{ url_for('logout') }}">Logout</a></p>
    {% endif %}
  </div>
</body>
</html>
"""

PROTECTED_TEMPLATE = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>Protected</title>
</head>
<body>
  <h1>Protected</h1>
  <p>Hello, <strong>{{ user|e }}</strong>.</p>
  <p><a href="{{ url_for('logout') }}">Logout</a></p>
</body>
</html>
"""


def utc_now_ts() -> int:
    return int(time.time())


def utc_dt_from_ts(ts: int) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


def create_app() -> Flask:
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY=os.environ.get("FLASK_SECRET_KEY", secrets.token_urlsafe(32)),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=bool(int(os.environ.get("SESSION_COOKIE_SECURE", "0"))),
        MAX_CONTENT_LENGTH=1024 * 32,
    )

    def get_db() -> sqlite3.Connection:
        if "db" not in g:
            conn = sqlite3.connect(DB_PATH, detect_types=sqlite3.PARSE_DECLTYPES)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON;")
            conn.execute("PRAGMA journal_mode = WAL;")
            conn.execute("PRAGMA synchronous = NORMAL;")
            g.db = conn
        return g.db

    @app.teardown_appcontext
    def close_db(_exc: Optional[BaseException]) -> None:
        conn = g.pop("db", None)
        if conn is not None:
            conn.close()

    def init_db() -> None:
        Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(DB_PATH)
        try:
            conn.execute("PRAGMA foreign_keys = ON;")
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL,
                    created_at INTEGER NOT NULL
                );

                -- State table for throttling / blocking
                CREATE TABLE IF NOT EXISTS login_attempts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL,
                    ip TEXT NOT NULL,
                    failed_count INTEGER NOT NULL DEFAULT 0,
                    first_failed_at INTEGER,
                    last_failed_at INTEGER,
                    blocked_until INTEGER,
                    updated_at INTEGER NOT NULL,
                    UNIQUE(username, ip)
                );

                -- Optional audit log
                CREATE TABLE IF NOT EXISTS login_attempt_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT,
                    ip TEXT NOT NULL,
                    success INTEGER NOT NULL,
                    reason TEXT,
                    created_at INTEGER NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_login_attempts_blocked_until
                    ON login_attempts(blocked_until);

                CREATE INDEX IF NOT EXISTS idx_login_attempt_log_created_at
                    ON login_attempt_log(created_at);
                """
            )
            conn.commit()
        finally:
            conn.close()

    def client_ip() -> str:
        # Prefer a proxy-set header only if you trust your proxy setup.
        # Keep conservative default: use remote_addr.
        return request.remote_addr or "unknown"

    def csrf_token_get() -> str:
        token = session.get("csrf_token")
        if not token:
            token = secrets.token_urlsafe(32)
            session["csrf_token"] = token
        return token

    def csrf_validate(form_token: str) -> None:
        token = session.get("csrf_token")
        if not token or not form_token or not secrets.compare_digest(token, form_token):
            abort(400, description="Invalid CSRF token")

    def user_lookup(username: str) -> Optional[sqlite3.Row]:
        db = get_db()
        return db.execute(
            "SELECT id, username, password_hash FROM users WHERE username = ?",
            (username,),
        ).fetchone()

    def attempts_get(username: str, ip: str) -> Optional[sqlite3.Row]:
        db = get_db()
        return db.execute(
            """
            SELECT username, ip, failed_count, first_failed_at, last_failed_at, blocked_until
            FROM login_attempts
            WHERE username = ? AND ip = ?
            """,
            (username, ip),
        ).fetchone()

    def attempts_upsert(
        username: str,
        ip: str,
        failed_count: int,
        first_failed_at: Optional[int],
        last_failed_at: Optional[int],
        blocked_until: Optional[int],
    ) -> None:
        db = get_db()
        now = utc_now_ts()
        db.execute(
            """
            INSERT INTO login_attempts (username, ip, failed_count, first_failed_at, last_failed_at, blocked_until, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(username, ip) DO UPDATE SET
                failed_count = excluded.failed_count,
                first_failed_at = excluded.first_failed_at,
                last_failed_at = excluded.last_failed_at,
                blocked_until = excluded.blocked_until,
                updated_at = excluded.updated_at
            """,
            (username, ip, failed_count, first_failed_at, last_failed_at, blocked_until, now),
        )
        db.commit()

    def attempts_clear(username: str, ip: str) -> None:
        db = get_db()
        db.execute("DELETE FROM login_attempts WHERE username = ? AND ip = ?", (username, ip))
        db.commit()

    def attempt_log(username: Optional[str], ip: str, success: bool, reason: Optional[str]) -> None:
        db = get_db()
        db.execute(
            """
            INSERT INTO login_attempt_log (username, ip, success, reason, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (username, ip, 1 if success else 0, reason, utc_now_ts()),
        )
        db.commit()

    def is_blocked(username: str, ip: str) -> Tuple[bool, Optional[int]]:
        row = attempts_get(username, ip)
        if not row:
            return False, None
        blocked_until = row["blocked_until"]
        if blocked_until and blocked_until > utc_now_ts():
            return True, int(blocked_until)
        return False, None

    def register_failure(username: str, ip: str) -> Tuple[bool, Optional[int]]:
        now = utc_now_ts()
        row = attempts_get(username, ip)
        if row:
            failed_count = int(row["failed_count"] or 0)
            first_failed_at = row["first_failed_at"]
            last_failed_at = row["last_failed_at"]
            blocked_until = row["blocked_until"]

            if blocked_until and int(blocked_until) > now:
                return True, int(blocked_until)

            if first_failed_at is None or (now - int(first_failed_at)) > FAIL_WINDOW_SECONDS:
                failed_count = 1
                first_failed_at = now
            else:
                failed_count += 1

            last_failed_at = now
            blocked_until = None
            if failed_count >= MAX_FAILED_ATTEMPTS:
                blocked_until = now + BLOCK_SECONDS

            attempts_upsert(
                username=username,
                ip=ip,
                failed_count=failed_count,
                first_failed_at=int(first_failed_at) if first_failed_at is not None else None,
                last_failed_at=int(last_failed_at) if last_failed_at is not None else None,
                blocked_until=int(blocked_until) if blocked_until is not None else None,
            )
            return bool(blocked_until and blocked_until > now), int(blocked_until) if blocked_until else None

        failed_count = 1
        first_failed_at = now
        last_failed_at = now
        blocked_until = None
        if failed_count >= MAX_FAILED_ATTEMPTS:
            blocked_until = now + BLOCK_SECONDS

        attempts_upsert(
            username=username,
            ip=ip,
            failed_count=failed_count,
            first_failed_at=first_failed_at,
            last_failed_at=last_failed_at,
            blocked_until=blocked_until,
        )
        return bool(blocked_until and blocked_until > now), int(blocked_until) if blocked_until else None

    def login_required(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if not session.get("user"):
                return redirect(url_for("login"))
            return fn(*args, **kwargs)

        return wrapper

    @app.get("/login")
    def login() -> str:
        return render_template_string(LOGIN_TEMPLATE, csrf_token=csrf_token_get())

    @app.post("/login")
    def login_post():
        csrf_validate(request.form.get("csrf_token", ""))

        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        ip = client_ip()

        if not username or not password:
            flash("err", "Missing username or password.")
            attempt_log(username or None, ip, success=False, reason="missing_credentials")
            return render_template_string(LOGIN_TEMPLATE, csrf_token=csrf_token_get()), 400

        blocked, blocked_until = is_blocked(username, ip)
        if blocked:
            until_str = utc_dt_from_ts(blocked_until) if blocked_until else "later"
            flash("warn", f"Too many failed attempts. Try again after {until_str}.")
            attempt_log(username, ip, success=False, reason="blocked")
            return render_template_string(LOGIN_TEMPLATE, csrf_token=csrf_token_get()), 429

        user = user_lookup(username)
        if not user or not check_password_hash(user["password_hash"], password):
            newly_blocked, until = register_failure(username, ip)
            attempt_log(username, ip, success=False, reason="invalid_credentials")
            if newly_blocked and until:
                flash("warn", f"Too many failed attempts. Try again after {utc_dt_from_ts(until)}.")
                return render_template_string(LOGIN_TEMPLATE, csrf_token=csrf_token_get()), 429
            flash("err", "Invalid username or password.")
            return render_template_string(LOGIN_TEMPLATE, csrf_token=csrf_token_get()), 401

        attempts_clear(username, ip)
        attempt_log(username, ip, success=True, reason=None)
        session["user"] = username
        flash("ok", "Signed in successfully.")
        return redirect(url_for("protected"))

    @app.get("/logout")
    def logout():
        session.pop("user", None)
        flash("ok", "Signed out.")
        return redirect(url_for("login"))

    @app.get("/protected")
    @login_required
    def protected():
        return render_template_string(PROTECTED_TEMPLATE, user=session.get("user"))

    @app.get("/")
    def index():
        return redirect(url_for("protected") if session.get("user") else url_for("login"))

    @app.cli.command("init-db")
    def init_db_command():
        init_db()
        click.echo(f"Initialized DB at {DB_PATH}")

    @app.cli.command("create-user")
    @click.option("--username", prompt=True)
    @click.option("--password", prompt=True, hide_input=True, confirmation_prompt=True)
    def create_user_command(username: str, password: str):
        init_db()
        db = sqlite3.connect(DB_PATH)
        try:
            db.execute("PRAGMA foreign_keys = ON;")
            db.execute(
                """
                INSERT INTO users (username, password_hash, created_at)
                VALUES (?, ?, ?)
                """,
                (username.strip(), generate_password_hash(password), utc_now_ts()),
            )
            db.commit()
            click.echo("User created.")
        except sqlite3.IntegrityError:
            click.echo("Username already exists.", err=True)
            raise SystemExit(1)
        finally:
            db.close()

    # Ensure DB exists on startup (safe no-op if already created)
    init_db()

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host=os.environ.get("FLASK_HOST", "127.0.0.1"), port=int(os.environ.get("FLASK_PORT", "5000")), debug=False)
