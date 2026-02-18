from flask import Flask, request, jsonify
import sqlite3

app = Flask(__name__)

DATABASE = "users.db"


def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db_connection()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            email TEXT NOT NULL
        )
        """
    )
    conn.commit()
    conn.close()


@app.route("/api/search", methods=["GET"])
def search_users():
    query = request.args.get("q", "").strip()

    if not query:
        return jsonify({"error": "Missing required query parameter 'q'"}), 400

    conn = get_db_connection()
    try:
        users = conn.execute(
            "SELECT id, username, email FROM users WHERE username LIKE ?",
            (f"%{query}%",),
        ).fetchall()

        results = [
            {"id": user["id"], "username": user["username"], "email": user["email"]}
            for user in users
        ]

        return jsonify(results), 200
    finally:
        conn.close()


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
