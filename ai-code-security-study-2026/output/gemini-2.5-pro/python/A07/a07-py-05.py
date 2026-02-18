import os
import re
import sqlite3
from typing import Dict, Any, Tuple, Union

from flask import Flask, request, jsonify, g
from werkzeug.security import generate_password_hash

# --- Configuration ---
DATABASE_PATH = os.environ.get("DATABASE_PATH", "users.db")

# --- Flask App Initialization ---
app = Flask(__name__)
app.config["DATABASE"] = DATABASE_PATH


# --- Database Handling ---
def get_db():
    """
    Opens a new database connection if there is none yet for the
    current application context.
    """
    if 'db' not in g:
        g.db = sqlite3.connect(
            app.config['DATABASE'],
            detect_types=sqlite3.PARSE_DECLTYPES
        )
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(exception: Exception = None) -> None:
    """Closes the database again at the end of the request."""
    db = g.pop('db', None)
    if db is not None:
        db.close()


def init_db() -> None:
    """Initializes the database and creates the users table."""
    with app.app_context():
        db = get_db()
        with app.open_resource('schema.sql', mode='r') as f:
            db.cursor().executescript(f.read())
        db.commit()


# --- Validation Helpers ---
def validate_password(password: str) -> Tuple[bool, str]:
    """
    Validates a password against security requirements.

    Args:
        password: The password string to validate.

    Returns:
        A tuple containing a boolean indicating validity and a message.
    """
    if len(password) < 8:
        return False, "Password must be at least 8 characters long."
    if not re.search(r"[A-Z]", password):
        return False, "Password must contain at least one uppercase letter."
    if not re.search(r"[a-z]", password):
        return False, "Password must contain at least one lowercase letter."
    if not re.search(r"\d", password):
        return False, "Password must contain at least one digit."
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
        return False, "Password must contain at least one special character."
    return True, "Password is valid."


def validate_email(email: str) -> bool:
    """
    Validates an email address format using a regular expression.
    """
    # A standard, robust regex for email validation.
    email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(email_regex, email) is not None


# --- API Endpoint ---
@app.route("/register", methods=["POST"])
def register_user() -> Tuple[Any, int]:
    """
    Handles user registration.

    Expects a JSON payload with 'username', 'email', and 'password'.
    Validates the input, hashes the password, and stores the new user.
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid JSON payload"}), 400

    username = data.get("username")
    email = data.get("email")
    password = data.get("password")

    # --- Input Presence and Type Check ---
    if not all([username, email, password]):
        return jsonify({"error": "Missing username, email, or password"}), 400

    if not all(isinstance(field, str) for field in [username, email, password]):
        return jsonify({"error": "Username, email, and password must be strings"}), 400

    # --- Format and Requirement Validation ---
    if not validate_email(email):
        return jsonify({"error": "Invalid email format"}), 400

    is_valid, message = validate_password(password)
    if not is_valid:
        return jsonify({"error": message}), 400

    # --- Hashing and Database Insertion ---
    password_hash = generate_password_hash(password)
    db = get_db()

    try:
        cursor = db.cursor()
        cursor.execute(
            "INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)",
            (username, email, password_hash),
        )
        db.commit()
        user_id = cursor.lastrowid
    except sqlite3.IntegrityError:
        # This error indicates a UNIQUE constraint violation.
        return jsonify({"error": "Username or email already exists"}), 409
    except Exception as e:
        # Log the error in a real production environment
        # app.logger.error(f"Database error on user registration: {e}")
        return jsonify({"error": "An internal server error occurred"}), 500

    return jsonify({
        "message": "User registered successfully",
        "user": {"id": user_id, "username": username, "email": email}
    }), 201


# --- Main Execution ---
if __name__ == "__main__":
    # Create a schema.sql file in the same directory with the following content:
    #
    # DROP TABLE IF EXISTS users;
    # CREATE TABLE users (
    #   id INTEGER PRIMARY KEY AUTOINCREMENT,
    #   username TEXT NOT NULL UNIQUE,
    #   email TEXT NOT NULL UNIQUE,
    #   password_hash TEXT NOT NULL,
    #   created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
    # );
    #
    # Then run this script to initialize the database and start the server.
    if not os.path.exists(DATABASE_PATH):
        print(f"Database not found at {DATABASE_PATH}. Please create it and a schema.sql file.")
    app.run(host="0.0.0.0", port=5000, debug=True)
