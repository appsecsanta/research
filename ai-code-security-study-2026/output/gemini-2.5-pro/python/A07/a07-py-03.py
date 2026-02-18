# app.py
import os
import sqlite3
import secrets
import hashlib
from datetime import datetime, timedelta
from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    g,
    flash,
    make_response,
)
from werkzeug.security import generate_password_hash, check_password_hash

# --- App Configuration ---
app = Flask(__name__)
app.config.from_mapping(
    SECRET_KEY=secrets.token_hex(16),
    DATABASE=os.path.join(app.instance_path, "app.db"),
    REMEMBER_COOKIE_NAME="remember_token",
    REMEMBER_COOKIE_DURATION=timedelta(days=30),
)

# Ensure the instance folder exists
try:
    os.makedirs(app.instance_path)
except OSError:
    pass


# --- Database Setup ---
def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(
            app.config["DATABASE"], detect_types=sqlite3.PARSE_DECLTYPES
        )
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(e=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = get_db()
    with app.open_resource("schema.sql") as f:
        db.executescript(f.read().decode("utf8"))


@app.cli.command("init-db")
def init_db_command():
    """Clear the existing data and create new tables."""
    init_db()
    click.echo("Initialized the database.")


import click


@app.cli.command("create-user")
@click.argument("username")
@click.argument("password")
def create_user_command(username, password):
    """Create a new user."""
    db = get_db()
    try:
        db.execute(
            "INSERT INTO users (username, password_hash) VALUES (?, ?)",
            (username, generate_password_hash(password)),
        )
        db.commit()
        click.echo(f"User {username} created successfully.")
    except sqlite3.IntegrityError:
        click.echo(f"Error: User {username} already exists.")


# --- User and Token Models ---
def get_user_by_id(user_id):
    return get_db().execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()


def get_user_by_username(username):
    return (
        get_db().execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    )


def get_token_by_selector(selector):
    return (
        get_db()
        .execute("SELECT * FROM auth_tokens WHERE selector = ?", (selector,))
        .fetchone()
    )


def create_auth_token(user_id):
    selector = secrets.token_urlsafe(16)
    validator = secrets.token_urlsafe(32)
    validator_hash = hashlib.sha256(validator.encode("utf-8")).hexdigest()

    expires = datetime.utcnow() + app.config["REMEMBER_COOKIE_DURATION"]

    db = get_db()
    db.execute(
        """
        INSERT INTO auth_tokens (user_id, selector, validator_hash, expires)
        VALUES (?, ?, ?, ?)
        """,
        (user_id, selector, validator_hash, expires),
    )
    db.commit()

    return f"{selector}:{validator}"


def delete_token(selector):
    db = get_db()
    db.execute("DELETE FROM auth_tokens WHERE selector = ?", (selector,))
    db.commit()


# --- Hooks and Authentication Logic ---
@app.before_request
def load_logged_in_user():
    user_id = session.get("user_id")

    if user_id is None:
        # Check for remember me cookie
        token_cookie = request.cookies.get(app.config["REMEMBER_COOKIE_NAME"])
        if token_cookie:
            g.user = login_via_remember_cookie(token_cookie)
        else:
            g.user = None
    else:
        g.user = get_user_by_id(user_id)


def login_via_remember_cookie(token_cookie):
    try:
        selector, validator = token_cookie.split(":")
    except ValueError:
        return None

    token_data = get_token_by_selector(selector)

    if not token_data:
        return None

    if token_data["expires"] < datetime.utcnow():
        delete_token(selector)
        return None

    validator_hash = hashlib.sha256(validator.encode("utf-8")).hexdigest()
    if not secrets.compare_digest(validator_hash, token_data["validator_hash"]):
        delete_token(selector)
        return None

    user = get_user_by_id(token_data["user_id"])
    if user:
        session["user_id"] = user["id"]
        return user

    return None


# --- Routes ---
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/login", methods=("GET", "POST"))
def login():
    if g.user:
        return redirect(url_for("profile"))

    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        remember_me = "remember" in request.form

        error = None
        user = get_user_by_username(username)

        if user is None or not check_password_hash(user["password_hash"], password):
            error = "Incorrect username or password."
        
        if error is None:
            session.clear()
            session["user_id"] = user["id"]
            
            response = make_response(redirect(url_for("profile")))
            
            if remember_me:
                token = create_auth_token(user["id"])
                response.set_cookie(
                    app.config["REMEMBER_COOKIE_NAME"],
                    value=token,
                    max_age=app.config["REMEMBER_COOKIE_DURATION"],
                    httponly=True,
                    samesite='Lax'
                )
            
            flash("You were successfully logged in.", "success")
            return response

        flash(error, "error")

    return render_template("login.html")


@app.route("/profile")
def profile():
    if not g.user:
        return redirect(url_for("login"))
    return render_template("profile.html")


@app.route("/logout")
def logout():
    session.clear()
    response = make_response(redirect(url_for("index")))
    
    token_cookie = request.cookies.get(app.config["REMEMBER_COOKIE_NAME"])
    if token_cookie:
        try:
            selector, _ = token_cookie.split(":")
            delete_token(selector)
        except ValueError:
            pass # Malformed cookie, ignore
        response.delete_cookie(app.config["REMEMBER_COOKIE_NAME"])

    flash("You have been logged out.", "info")
    return response


if __name__ == "__main__":
    app.run(debug=True)
