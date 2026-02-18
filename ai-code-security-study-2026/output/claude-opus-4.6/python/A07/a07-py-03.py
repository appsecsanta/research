import os
import sqlite3
import hashlib
import secrets
from datetime import datetime, timedelta
from functools import wraps

from flask import (
    Flask, request, redirect, url_for, render_template_string,
    make_response, g, session
)
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)

DATABASE = "app.db"
REMEMBER_COOKIE_NAME = "remember_token"
REMEMBER_COOKIE_DURATION = 30  # days


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(exception):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = sqlite3.connect(DATABASE)
    db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL
        )
    """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS remember_tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            token_hash TEXT NOT NULL,
            expires_at TIMESTAMP NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)
    # Create a demo user if not exists
    existing = db.execute("SELECT id FROM users WHERE username = ?", ("demo",)).fetchone()
    if not existing:
        pw_hash = generate_password_hash("password")
        db.execute("INSERT INTO users (username, password_hash) VALUES (?, ?)", ("demo", pw_hash))
    db.commit()
    db.close()


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def get_current_user():
    """Return the current user from session or remember-me cookie."""
    # Check session first
    user_id = session.get("user_id")
    if user_id:
        db = get_db()
        user = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        if user:
            return user

    # Check remember-me cookie
    token = request.cookies.get(REMEMBER_COOKIE_NAME)
    if token:
        token_hashed = hash_token(token)
        db = get_db()
        row = db.execute(
            "SELECT * FROM remember_tokens WHERE token_hash = ? AND expires_at > ?",
            (token_hashed, datetime.utcnow().isoformat())
        ).fetchone()
        if row:
            user = db.execute("SELECT * FROM users WHERE id = ?", (row["user_id"],)).fetchone()
            if user:
                session["user_id"] = user["id"]
                return user
            else:
                # User deleted; clean up token
                db.execute("DELETE FROM remember_tokens WHERE id = ?", (row["id"],))
                db.commit()
        else:
            # Invalid or expired token — clear cookie will happen on response
            pass

    return None


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user = get_current_user()
        if user is None:
            return redirect(url_for("login"))
        g.user = user
        return f(*args, **kwargs)
    return decorated_function


# ─── Templates ────────────────────────────────────────────────────────────────

LOGIN_TEMPLATE = """
<!DOCTYPE html>
<html>
<head><title>Login</title>
<style>
    body { font-family: Arial, sans-serif; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; background: #f0f2f5; }
    .card { background: #fff; padding: 2rem; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); width: 340px; }
    h2 { margin-top: 0; text-align: center; }
    label { display: block; margin-top: 1rem; font-weight: bold; }
    input[type=text], input[type=password] { width: 100%; padding: 0.5rem; margin-top: 0.3rem; box-sizing: border-box; border: 1px solid #ccc; border-radius: 4px; }
    .remember { margin-top: 1rem; display: flex; align-items: center; gap: 0.5rem; }
    .remember label { margin: 0; font-weight: normal; }
    button { margin-top: 1.5rem; width: 100%; padding: 0.6rem; background: #4a90d9; color: #fff; border: none; border-radius: 4px; cursor: pointer; font-size: 1rem; }
    button:hover { background: #357abd; }
    .error { color: red; text-align: center; margin-top: 0.5rem; }
    .info { text-align: center; margin-top: 1rem; font-size: 0.85rem; color: #666; }
</style>
</head>
<body>
<div class="card">
    <h2>Login</h2>
    {% if error %}
    <p class="error">{{ error }}</p>
    {% endif %}
    <form method="POST">
        <label for="username">Username</label>
        <input type="text" id="username" name="username" required autofocus>
        <label for="password">Password</label>
        <input type="password" id="password" name="password" required>
        <div class="remember">
            <input type="checkbox" id="remember" name="remember">
            <label for="remember">Remember me</label>
        </div>
        <button type="submit">Sign In</button>
    </form>
    <p class="info">Demo credentials: <strong>demo</strong> / <strong>password</strong></p>
</div>
</body>
</html>
"""

DASHBOARD_TEMPLATE = """
<!DOCTYPE html>
<html>
<head><title>Dashboard</title>
<style>
    body { font-family: Arial, sans-serif; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; background: #f0f2f5; }
    .card { background: #fff; padding: 2rem; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); text-align: center; width: 400px; }
    h2 { margin-top: 0; }
    a { display: inline-block; margin-top: 1rem; padding: 0.5rem 1.5rem; background: #e74c3c; color: #fff; text-decoration: none; border-radius: 4px; }
    a:hover { background: #c0392b; }
    .meta { color: #888; font-size: 0.85rem; margin-top: 0.5rem; }
</style>
</head>
<body>
<div class="card">
    <h2>Welcome, {{ username }}!</h2>
    <p>You are logged in.</p>
    <p class="meta">Session user_id: {{ user_id }}</p>
    <a href="{{ url_for('logout') }}">Logout</a>
</div>
</body>
</html>
"""


# ─── Routes ───────────────────────────────────────────────────────────────────

@app.route("/")
@login_required
def dashboard():
    return render_template_string(
        DASHBOARD_TEMPLATE,
        username=g.user["username"],
        user_id=g.user["id"],
    )


@app.route("/login", methods=["GET", "POST"])
def login():
    # If already logged in, redirect
    user = get_current_user()
    if user:
        return redirect(url_for("dashboard"))

    error = None
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        remember = request.form.get("remember") == "on"

        db = get_db()
        user = db.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()

        if user and check_password_hash(user["password_hash"], password):
            session["user_id"] = user["id"]
            response = make_response(redirect(url_for("dashboard")))

            if remember:
                # Generate a secure token, store its hash in DB, set cookie with raw token
                raw_token = secrets.token_urlsafe(64)
                token_hashed = hash_token(raw_token)
                expires_at = datetime.utcnow() + timedelta(days=REMEMBER_COOKIE_DURATION)

                db.execute(
                    "INSERT INTO remember_tokens (user_id, token_hash, expires_at) VALUES (?, ?, ?)",
                    (user["id"], token_hashed, expires_at.isoformat()),
                )
                db.commit()

                response.set_cookie(
                    REMEMBER_COOKIE_NAME,
                    raw_token,
                    max_age=REMEMBER_COOKIE_DURATION * 86400,
                    httponly=True,
                    samesite="Lax",
                    secure=False,  # Set True in production with HTTPS
                )

            return response
        else:
            error = "Invalid username or password."

    return render_template_string(LOGIN_TEMPLATE, error=error)


@app.route("/logout")
def logout():
    # Remove remember token from DB if cookie present
    token = request.cookies.get(REMEMBER_COOKIE_NAME)
    if token:
        token_hashed = hash_token(token)
        db = get_db()
        db.execute("DELETE FROM remember_tokens WHERE token_hash = ?", (token_hashed,))
        db.commit()

    session.clear()

    response = make_response(redirect(url_for("login")))
    response.delete_cookie(REMEMBER_COOKIE_NAME)
    return response


if __name__ == "__main__":
    init_db()
    app.run(debug=True, port=5000)
