import re
import sqlite3
import os
from flask import Flask, request, jsonify
from werkzeug.security import generate_password_hash

app = Flask(__name__)
DATABASE = os.environ.get("DATABASE", "users.db")


def get_db():
    """Get a database connection with row factory."""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Initialize the database schema."""
    conn = get_db()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.commit()
    conn.close()


def validate_password(password: str) -> list[str]:
    """Validate password meets security requirements. Returns list of errors."""
    errors = []

    if len(password) < 8:
        errors.append("Password must be at least 8 characters long.")
    if len(password) > 128:
        errors.append("Password must not exceed 128 characters.")
    if not re.search(r"[A-Z]", password):
        errors.append("Password must contain at least one uppercase letter.")
    if not re.search(r"[a-z]", password):
        errors.append("Password must contain at least one lowercase letter.")
    if not re.search(r"\d", password):
        errors.append("Password must contain at least one digit.")
    if not re.search(r"[!@#$%^&*()_+\-=\[\]{};':\"\\|,.<>\/?~`]", password):
        errors.append("Password must contain at least one special character.")

    return errors


def validate_email(email: str) -> bool:
    """Basic email format validation."""
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    return bool(re.match(pattern, email))


def validate_username(username: str) -> list[str]:
    """Validate username. Returns list of errors."""
    errors = []

    if len(username) < 3:
        errors.append("Username must be at least 3 characters long.")
    if len(username) > 50:
        errors.append("Username must not exceed 50 characters.")
    if not re.match(r"^[a-zA-Z0-9_]+$", username):
        errors.append("Username must contain only alphanumeric characters and underscores.")

    return errors


@app.route("/register", methods=["POST"])
def register():
    """User registration endpoint."""
    data = request.get_json()

    if not data:
        return jsonify({"error": "Request body must be JSON."}), 400

    username = data.get("username", "").strip()
    email = data.get("email", "").strip()
    password = data.get("password", "")

    # Check required fields
    missing_fields = []
    if not username:
        missing_fields.append("username")
    if not email:
        missing_fields.append("email")
    if not password:
        missing_fields.append("password")

    if missing_fields:
        return jsonify({
            "error": f"Missing required fields: {', '.join(missing_fields)}"
        }), 400

    # Validate username
    username_errors = validate_username(username)
    if username_errors:
        return jsonify({"error": "Invalid username.", "details": username_errors}), 400

    # Validate email
    if not validate_email(email):
        return jsonify({"error": "Invalid email format."}), 400

    # Validate password
    password_errors = validate_password(password)
    if password_errors:
        return jsonify({"error": "Password does not meet requirements.", "details": password_errors}), 400

    # Hash password
    password_hash = generate_password_hash(password, method="pbkdf2:sha256", salt_length=16)

    # Store user in database
    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)",
            (username, email.lower(), password_hash),
        )
        conn.commit()

        # Fetch the created user to return
        cursor = conn.execute(
            "SELECT id, username, email, created_at FROM users WHERE username = ?",
            (username,),
        )
        user = cursor.fetchone()

        return jsonify({
            "message": "User registered successfully.",
            "user": {
                "id": user["id"],
                "username": user["username"],
                "email": user["email"],
                "created_at": user["created_at"],
            },
        }), 201

    except sqlite3.IntegrityError as e:
        error_message = str(e).lower()
        if "username" in error_message:
            return jsonify({"error": "Username already exists."}), 409
        elif "email" in error_message:
            return jsonify({"error": "Email already registered."}), 409
        else:
            return jsonify({"error": "User already exists."}), 409
    except sqlite3.Error as e:
        return jsonify({"error": f"Database error: {str(e)}"}), 500
    finally:
        conn.close()


@app.errorhandler(405)
def method_not_allowed(e):
    return jsonify({"error": "Method not allowed."}), 405


@app.errorhandler(500)
def internal_server_error(e):
    return jsonify({"error": "Internal server error."}), 500


# Initialize database on startup
with app.app_context():
    init_db()


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
