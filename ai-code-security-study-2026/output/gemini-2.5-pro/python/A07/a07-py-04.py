# app.py
import sqlite3
import time
from datetime import datetime, timedelta

from flask import Flask, g, render_template, request, flash, redirect, url_for
from werkzeug.security import check_password_hash, generate_password_hash

# --- Configuration ---
DATABASE = 'login_attempts.db'
SECRET_KEY = 'a_very_secret_key_that_should_be_changed'

# Security settings
MAX_FAILED_ATTEMPTS = 5
BLOCK_DURATION_SECONDS = 300  # 5 minutes

# --- Hardcoded User Data (for demonstration) ---
# In a real application, this would come from a secure user database.
VALID_USERNAME = "admin"
VALID_PASSWORD_HASH = generate_password_hash("password123")

# --- Flask Application Setup ---
app = Flask(__name__)
app.config.from_object(__name__)


# --- Database Handling ---
def get_db():
    """Opens a new database connection if there is none yet for the current application context."""
    if 'db' not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(error):
    """Closes the database again at the end of the request."""
    if hasattr(g, 'db'):
        g.db.close()


# --- Login Logic ---
def is_user_blocked(username, ip_address):
    """
    Checks if a user is temporarily blocked due to too many failed login attempts.

    Returns:
        A tuple (is_blocked, time_remaining_seconds).
        is_blocked is True if the user is currently blocked.
        time_remaining_seconds is the number of seconds until the block expires.
    """
    db = get_db()
    # We only care about recent failed attempts from this username or IP
    query = """
        SELECT timestamp FROM login_attempts
        WHERE (username = ? OR ip_address = ?) AND successful = 0
        ORDER BY timestamp DESC
        LIMIT ?
    """
    cursor = db.execute(query, (username, ip_address, MAX_FAILED_ATTEMPTS))
    failed_attempts = cursor.fetchall()

    if len(failed_attempts) < MAX_FAILED_ATTEMPTS:
        return False, 0

    last_attempt_timestamp_str = failed_attempts[0]['timestamp']
    last_attempt_time = datetime.fromisoformat(last_attempt_timestamp_str)

    block_expires_at = last_attempt_time + timedelta(seconds=BLOCK_DURATION_SECONDS)
    now = datetime.utcnow()

    if now < block_expires_at:
        time_remaining = block_expires_at - now
        return True, int(time_remaining.total_seconds())

    return False, 0


def log_login_attempt(username, ip_address, successful):
    """Logs a login attempt to the database."""
    db = get_db()
    timestamp = datetime.utcnow().isoformat()
    db.execute(
        "INSERT INTO login_attempts (username, ip_address, timestamp, successful) VALUES (?, ?, ?, ?)",
        (username, ip_address, timestamp, 1 if successful else 0)
    )
    db.commit()


# --- Routes ---
@app.route('/')
def index():
    """Renders the login page."""
    return render_template('login.html')


@app.route('/login', methods=['POST'])
def login():
    """Handles the login form submission."""
    username = request.form.get('username', '').strip()
    password = request.form.get('password', '')
    ip_address = request.remote_addr

    if not username or not password:
        flash("Username and password are required.", "error")
        return redirect(url_for('index'))

    # 1. Check if the user is currently blocked
    blocked, time_remaining = is_user_blocked(username, ip_address)
    if blocked:
        flash(f"Too many failed login attempts. Please try again in {time_remaining} seconds.", "error")
        return render_template('login.html'), 429  # HTTP 429 Too Many Requests

    # 2. Authenticate the user
    is_authenticated = (username == VALID_USERNAME and check_password_hash(VALID_PASSWORD_HASH, password))

    # 3. Log the attempt
    log_login_attempt(username, ip_address, is_authenticated)

    # 4. Handle success or failure
    if is_authenticated:
        flash("Login successful!", "success")
        # In a real app, you would create a session here
        # session['user_id'] = username
        return render_template('login.html')
    else:
        flash("Invalid username or password.", "error")
        return render_template('login.html'), 401  # HTTP 401 Unauthorized


if __name__ == '__main__':
    # For development:
    # 1. Run `python init_db.py` once to set up the database.
    # 2. Run `python app.py` to start the server.
    app.run(debug=True)
