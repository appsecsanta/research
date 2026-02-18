import sqlite3
import os
from flask import Flask, request, jsonify, session
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-production")

DATABASE = "users.db"


def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            name TEXT NOT NULL
        )
        """
    )
    conn.commit()

    # Insert a sample user for testing
    try:
        conn.execute(
            "INSERT INTO users (username, password_hash, name) VALUES (?, ?, ?)",
            ("johndoe", generate_password_hash("password123"), "John Doe"),
        )
        conn.commit()
    except sqlite3.IntegrityError:
        pass  # User already exists

    conn.close()


@app.route("/login", methods=["POST"])
def login():
    data = request.get_json()

    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400

    username = data.get("username")
    password = data.get("password")

    if not username or not password:
        return jsonify({"error": "Username and password are required"}), 400

    conn = get_db()
    try:
        user = conn.execute(
            "SELECT id, username, password_hash, name FROM users WHERE username = ?",
            (username,),
        ).fetchone()

        if user is None:
            return jsonify({"error": "Invalid username or password"}), 401

        if not check_password_hash(user["password_hash"], password):
            return jsonify({"error": "Invalid username or password"}), 401

        session["user_id"] = user["id"]
        session["username"] = user["username"]
        session["name"] = user["name"]

        return jsonify({
            "message": f"Login successful. Welcome, {user['name']}!",
            "user": {
                "id": user["id"],
                "username": user["username"],
                "name": user["name"],
            },
        }), 200

    finally:
        conn.close()


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"message": "Logged out successfully"}), 200


@app.route("/profile", methods=["GET"])
def profile():
    if "user_id" not in session:
        return jsonify({"error": "Authentication required"}), 401

    return jsonify({
        "user": {
            "id": session["user_id"],
            "username": session["username"],
            "name": session["name"],
        }
    }), 200


if __name__ == "__main__":
    init_db()
    app.run(debug=True, port=5000)
