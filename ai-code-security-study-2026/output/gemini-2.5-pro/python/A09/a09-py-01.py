import logging
import os
import sqlite3
from logging.handlers import RotatingFileHandler

from flask import Flask, jsonify, request
from werkzeug.security import check_password_hash, generate_password_hash

# --- Configuration ---
DATABASE_FILE = "auth.db"
LOG_FILE = "login_attempts.log"
DB_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

# --- Application Setup ---
app = Flask(__name__)
app.config["DATABASE"] = DATABASE_FILE


def setup_logging():
    """Configures logging for the application."""
    log_formatter = logging.Formatter(
        "%(asctime)s - %(levelname)s - %(message)s"
    )
    handler = RotatingFileHandler(
        LOG_FILE, maxBytes=1024 * 1024 * 10, backupCount=5  # 10 MB
    )
    handler.setFormatter(log_formatter)
    handler.setLevel(logging.INFO)

    # Get the logger for this module and add the handler
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)
    return logger


logger = setup_logging()


# --- Database Utilities ---
def get_db_connection():
    """Creates and returns a new database connection."""
    conn = sqlite3.connect(app.config["DATABASE"])
    conn.row_factory = sqlite3.Row
    return conn


def init_db(recreate=False):
    """Initializes the database and creates a sample user."""
    if recreate and os.path.exists(app.config["DATABASE"]):
        os.remove(app.config["DATABASE"])

    with get_db_connection() as conn:
        conn.execute(DB_SCHEMA)
        # Check if the sample user already exists
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM users WHERE username = ?", ("admin",))
        if cursor.fetchone() is None:
            # Add a sample user for demonstration purposes
            hashed_password = generate_password_hash("supersecretpassword123")
            cursor.execute(
                "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                ("admin", hashed_password),
            )
            conn.commit()
            print("Database initialized and 'admin' user created.")
        else:
            print("Database already initialized.")


# --- API Endpoints ---
@app.route("/login", methods=["POST"])
def login():
    """
    Authenticates a user based on username and password.
    Logs every login attempt.
    """
    ip_address = request.remote_addr

    if not request.is_json:
        logger.warning(
            f"Failed login attempt from {ip_address}: "
            "Request body was not JSON."
        )
        return jsonify({"error": "Invalid request: body must be JSON"}), 400

    data = request.get_json()
    username = data.get("username")
    password = data.get("password")

    if not username or not password:
        logger.warning(
            f"Failed login attempt from {ip_address}: "
            "Missing username or password in request."
        )
        return jsonify({"error": "Username and password are required"}), 400

    try:
        with get_db_connection() as conn:
            user = conn.execute(
                "SELECT * FROM users WHERE username = ?", (username,)
            ).fetchone()

        if user and check_password_hash(user["password_hash"], password):
            log_message = (
                f"Successful login: username='{username}', ip='{ip_address}'"
            )
            logger.info(log_message)
            return jsonify({"message": "Login successful"}), 200
        else:
            log_message = (
                f"Failed login attempt: username='{username}', ip='{ip_address}'"
            )
            logger.warning(log_message)
            return jsonify({"error": "Invalid username or password"}), 401

    except sqlite3.Error as e:
        logger.error(f"Database error during login for {username}: {e}")
        return jsonify({"error": "An internal server error occurred"}), 500


if __name__ == "__main__":
    # Initialize the database on first run
    init_db()
    # For production, use a proper WSGI server like Gunicorn or uWSGI
    # Example: gunicorn --bind 0.0.0.0:5000 app:app
    app.run(host="0.0.0.0", port=5000, debug=False)
