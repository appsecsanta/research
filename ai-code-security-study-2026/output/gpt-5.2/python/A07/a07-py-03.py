import os
import hmac
import hashlib
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone

from flask import (
    Flask,
    g,
    redirect,
    render_template_string,
    request,
    session,
    make_response,
    url_for,
)
from werkzeug.security import generate_password_hash, check_password_hash


UTC = timezone.utc


def utcnow() -> datetime:
    return datetime.now(tz=UTC)


def to_iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC).isoformat(timespec="seconds")


def from_iso(s: str) -> datetime:
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def sha256_hex(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def constant_time_equals(a: str, b: str) -> bool:
    return hmac.compare_digest(a, b)


def create_app() -> Flask:
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY=os.environ.get("FLASK_SECRET_KEY", secrets.token_hex(32)),
        DATABASE=os.environ.get("APP_DATABASE", os.path.join(app.root_path, "app.db")),
        REMEMBER_ME_COOKIE_NAME="remember_me",
        REMEMBER_ME_DAYS=int(os.environ.get("REMEMBER_ME_DAYS", "30")),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE=os.environ.get("SESSION_COOKIE_SAMESITE", "Lax"),
        SESSION_COOKIE_SECURE=os.environ.get("SESSION_COOKIE_SECURE", "0") == "1",
        REMEMBER_COOKIE_HTTPONLY=True,
        REMEMBER_COOKIE_SAMESITE=os.environ.get("REMEMBER_COOKIE_SAMESITE", "Lax"),
        REMEMBER_COOKIE_SECURE=os.environ.get("REMEMBER_COOKIE_SECURE", "0") == "1",
    )

    def get_db() -> sqlite3.Connection:
        if "db" not in g:
            conn = sqlite3.connect(app.config["DATABASE"])
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON;")
            g.db = conn
        return g.db

    @app.teardown_appcontext
    def close_db(_exc):
        db = g.pop("db", None)
        if db is not None:
            db.close()

    def init_db():
        db = get_db()
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS remember_tokens (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                selector TEXT NOT NULL UNIQUE,
                validator_hash TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                created_at TEXT NOT NULL,
                last_used_at TEXT,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_remember_tokens_user_id ON remember_tokens(user_id);
            CREATE INDEX IF NOT EXISTS idx_remember_tokens_expires_at ON remember_tokens(expires_at);
            """
        )
        db.commit()

    @app.before_request
    def ensure_db():
        init_db()

    def get_current_user():
        user_id = session.get("user_id")
        if not user_id:
            return None
        db = get_db()
        return db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()

    def set_session_user(user_row):
        session["user_id"] = int(user_row["id"])

    def clear_session():
        session.pop("user_id", None)

    def make_remember_cookie_value(selector: str, validator: str) -> str:
        return f"{selector}:{validator}"

    def parse_remember_cookie_value(value: str):
        if not value or ":" not in value:
            return None, None
        selector, validator = value.split(":", 1)
        if not selector or not validator:
            return None, None
        if len(selector) < 12 or len(validator) < 20:
            return None, None
        return selector, validator

    def delete_remember_token_by_selector(selector: str):
        db = get_db()
        db.execute("DELETE FROM remember_tokens WHERE selector = ?", (selector,))
        db.commit()

    def delete_all_remember_tokens_for_user(user_id: int):
        db = get_db()
        db.execute("DELETE FROM remember_tokens WHERE user_id = ?", (user_id,))
        db.commit()

    def set_remember_cookie(resp, selector: str, validator: str, expires: datetime):
        resp.set_cookie(
            app.config["REMEMBER_ME_COOKIE_NAME"],
            make_remember_cookie_value(selector, validator),
            expires=expires,
            max_age=int((expires - utcnow()).total_seconds()),
            httponly=app.config["REMEMBER_COOKIE_HTTPONLY"],
            secure=app.config["REMEMBER_COOKIE_SECURE"],
            samesite=app.config["REMEMBER_COOKIE_SAMESITE"],
            path="/",
        )

    def clear_remember_cookie(resp):
        resp.set_cookie(
            app.config["REMEMBER_ME_COOKIE_NAME"],
            "",
            expires=0,
            max_age=0,
            httponly=app.config["REMEMBER_COOKIE_HTTPONLY"],
            secure=app.config["REMEMBER_COOKIE_SECURE"],
            samesite=app.config["REMEMBER_COOKIE_SAMESITE"],
            path="/",
        )

    def issue_remember_token(user_id: int):
        selector = secrets.token_urlsafe(16)
        validator = secrets.token_urlsafe(32)
        validator_hash = sha256_hex(validator)
        expires = utcnow() + timedelta(days=app.config["REMEMBER_ME_DAYS"])

        db = get_db()
        db.execute(
            """
            INSERT INTO remember_tokens (user_id, selector, validator_hash, expires_at, created_at, last_used_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (user_id, selector, validator_hash, to_iso(expires), to_iso(utcnow()), None),
        )
        db.commit()
        return selector, validator, expires

    def rotate_remember_token(old_selector: str, user_id: int):
        # Delete old token and issue a fresh one (rotation on use).
        delete_remember_token_by_selector(old_selector)
        return issue_remember_token(user_id)

    def prune_expired_tokens():
        db = get_db()
        db.execute("DELETE FROM remember_tokens WHERE expires_at <= ?", (to_iso(utcnow()),))
        db.commit()

    @app.before_request
    def auto_login_from_remember_me():
        if session.get("user_id"):
            return

        prune_expired_tokens()

        cookie_val = request.cookies.get(app.config["REMEMBER_ME_COOKIE_NAME"])
        selector, validator = parse_remember_cookie_value(cookie_val)
        if not selector or not validator:
            return

        db = get_db()
        token_row = db.execute(
            "SELECT * FROM remember_tokens WHERE selector = ?",
            (selector,),
        ).fetchone()

        if token_row is None:
            return

        if from_iso(token_row["expires_at"]) <= utcnow():
            delete_remember_token_by_selector(selector)
            return

        expected_hash = token_row["validator_hash"]
        provided_hash = sha256_hex(validator)

        if not constant_time_equals(expected_hash, provided_hash):
            # Possible stolen/guessed cookie. Revoke this selector.
            delete_remember_token_by_selector(selector)
            return

        user_row = db.execute("SELECT * FROM users WHERE id = ?", (token_row["user_id"],)).fetchone()
        if user_row is None:
            delete_remember_token_by_selector(selector)
            return

        set_session_user(user_row)

        # Rotate token after successful login via cookie to reduce replay risk.
        new_selector, new_validator, new_expires = rotate_remember_token(selector, int(user_row["id"]))
        db.execute(
            "UPDATE remember_tokens SET last_used_at = ? WHERE selector = ?",
            (to_iso(utcnow()), new_selector),
        )
        db.commit()

        # Attach rotated cookie to the response by stashing data in g.
        g._remember_cookie_rotation = (new_selector, new_validator, new_expires)

    @app.after_request
    def apply_remember_cookie_rotation(resp):
        rotation = getattr(g, "_remember_cookie_rotation", None)
        if rotation:
            selector, validator, expires = rotation
            set_remember_cookie(resp, selector, validator, expires)
        return resp

    INDEX_TEMPLATE = """
    <!doctype html>
    <title>Home</title>
    {% if user %}
      <p>Logged in as <strong>{{ user['email'] }}</strong></p>
      <p><a href="{{ url_for('logout') }}">Logout</a></p>
    {% else %}
      <p>You are not logged in.</p>
      <p><a href="{{ url_for('login') }}">Login</a> | <a href="{{ url_for('register') }}">Register</a></p>
    {% endif %}
    """

    LOGIN_TEMPLATE = """
    <!doctype html>
    <title>Login</title>
    <h1>Login</h1>
    {% if error %}<p style="color: #b00">{{ error }}</p>{% endif %}
    <form method="post" autocomplete="on">
      <label>Email <input type="email" name="email" required></label><br>
      <label>Password <input type="password" name="password" required></label><br>
      <label><input type="checkbox" name="remember" value="1"> Remember me</label><br>
      <button type="submit">Login</button>
    </form>
    <p><a href="{{ url_for('index') }}">Home</a></p>
    """

    REGISTER_TEMPLATE = """
    <!doctype html>
    <title>Register</title>
    <h1>Register</h1>
    {% if error %}<p style="color: #b00">{{ error }}</p>{% endif %}
    <form method="post" autocomplete="on">
      <label>Email <input type="email" name="email" required></label><br>
      <label>Password <input type="password" name="password" required></label><br>
      <button type="submit">Create account</button>
    </form>
    <p><a href="{{ url_for('index') }}">Home</a></p>
    """

    @app.get("/")
    def index():
        user = get_current_user()
        return render_template_string(INDEX_TEMPLATE, user=user)

    @app.route("/register", methods=["GET", "POST"])
    def register():
        if request.method == "GET":
            return render_template_string(REGISTER_TEMPLATE, error=None)

        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        if not email or not password:
            return render_template_string(REGISTER_TEMPLATE, error="Email and password are required."), 400

        db = get_db()
        try:
            db.execute(
                "INSERT INTO users (email, password_hash, created_at) VALUES (?, ?, ?)",
                (email, generate_password_hash(password), to_iso(utcnow())),
            )
            db.commit()
        except sqlite3.IntegrityError:
            return render_template_string(REGISTER_TEMPLATE, error="Email already registered."), 400

        return redirect(url_for("login"))

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "GET":
            return render_template_string(LOGIN_TEMPLATE, error=None)

        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        remember = request.form.get("remember") == "1"

        db = get_db()
        user = db.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        if user is None or not check_password_hash(user["password_hash"], password):
            return render_template_string(LOGIN_TEMPLATE, error="Invalid email or password."), 401

        set_session_user(user)

        resp = make_response(redirect(url_for("index")))

        # Optional: revoke existing remember tokens for this user on login, to keep one device-token at a time.
        # Comment out if you prefer allowing multiple devices.
        delete_all_remember_tokens_for_user(int(user["id"]))

        if remember:
            selector, validator, expires = issue_remember_token(int(user["id"]))
            set_remember_cookie(resp, selector, validator, expires)
        else:
            clear_remember_cookie(resp)

        return resp

    @app.get("/logout")
    def logout():
        # Revoke remember token for the current cookie selector (if present).
        cookie_val = request.cookies.get(app.config["REMEMBER_ME_COOKIE_NAME"])
        selector, _validator = parse_remember_cookie_value(cookie_val)
        if selector:
            delete_remember_token_by_selector(selector)

        clear_session()
        resp = make_response(redirect(url_for("index")))
        clear_remember_cookie(resp)
        return resp

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
