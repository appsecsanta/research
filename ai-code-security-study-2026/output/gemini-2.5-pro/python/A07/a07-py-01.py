import os
import sqlite3
from flask import Flask, request, jsonify, session
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import timedelta

# --- Configuration ---
DATABASE_PATH = 'database.db'
# In a production environment, this key should be loaded from a secure source
# (e.g., environment variables, a secrets management service).
SECRET_KEY = os.environ.get('FLASK_SECRET_KEY', os.urandom(24))
SESSION_LIFETIME_MINUTES = 60

# --- Database Setup ---
def initialize_database():
    """
    Initializes the SQLite database and creates the users table if it doesn't exist.
    Adds a sample user for demonstration purposes.
    """
    if os.path.exists(DATABASE_PATH):
        return

    print("Initializing database...")
    try:
        with sqlite3.connect(DATABASE_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL
                );
            """)
            # Add a sample user
            sample_username = 'testuser'
            sample_password = 'StrongPassword123!'
            hashed_password = generate_password_hash(sample_password)
            cursor.execute(
                "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                (sample_username, hashed_password)
            )
            conn.commit()
            print(f"Database initialized at '{DATABASE_PATH}'")
            print(f"Sample user created: username='{sample_username}', password='{sample_password}'")
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        # Clean up the potentially partially created file on error
        if os.path.exists(DATABASE_PATH):
            os.remove(DATABASE_PATH)
        raise

def get_db_connection():
    """Creates a connection to the SQLite database."""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# --- Flask Application ---
app = Flask(__name__)
app.config['SECRET_KEY'] = SECRET_KEY
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=SESSION_LIFETIME_MINUTES)

@app.route('/login', methods=['POST'])
def login():
    """
    Handles user login.
    Expects a JSON body with 'username' and 'password'.
    """
    if not request.is_json:
        return jsonify({"error": "Request must be JSON"}), 415

    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        return jsonify({"error": "Username and password are required"}), 400

    user = None
    try:
        with get_db_connection() as conn:
            user = conn.execute(
                'SELECT * FROM users WHERE username = ?', (username,)
            ).fetchone()
    except sqlite3.Error as e:
        app.logger.error(f"Database error during login for user {username}: {e}")
        return jsonify({"error": "An internal server error occurred"}), 500

    if user and check_password_hash(user['password_hash'], password):
        # Clear any previous session and start a new one
        session.clear()
        session.permanent = True
        session['user_id'] = user['id']
        session['username'] = user['username']
        app.logger.info(f"User '{username}' logged in successfully.")
        return jsonify({"message": f"Login successful. Welcome, {user['username']}!"}), 200
    else:
        app.logger.warning(f"Failed login attempt for username: '{username}'")
        return jsonify({"error": "Invalid username or password"}), 401

if __name__ == '__main__':
    initialize_database()
    # In a production environment, use a production-ready WSGI server
    # like Gunicorn or uWSGI instead of app.run().
    app.run(host='0.0.0.0', port=5000, debug=False)
