import os
import sqlite3
from typing import Optional

from flask import Flask, jsonify, request, session, g
from werkzeug.security import check_password_hash

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "change-me-in-production")
app.config["DATABASE"] = os.environ.get("DATABASE_PATH", os.path.join(app.root_path, "app.db"))


def get_db() -> sqlite3.Connection:
    db: Optional[sqlite3.Connection] = getattr(g, "_db", None)
    if db is None:
        db = sqlite3.connect(app.config["DATABASE"])
        db.row_factory = sqlite3.Row
        g._db = db
    return db


@app.teardown_appcontext
def close_db(exception: Exception | None) -> None:
    db: Optional[sqlite3.Connection] = getattr(g, "_db", None)
    if db is not None:
        db.close()


@app.post("/login")
def login():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""

    if not username or not password:
        return jsonify({"error": "username and password are required"}), 400

    db = get_db()
    user = db.execute(
        "SELECT id, username, name, password_hash FROM users WHERE username = ?",
        (username,),
    ).fetchone()

    if user is None or not check_password_hash(user["password_hash"], password):
        return jsonify({"error": "invalid credentials"}), 401

    session.clear()
    session["user_id"] = int(user["id"])
    session["username"] = user["username"]
    session["name"] = user["name"]

    return jsonify({"message": f"Welcome, {user['name']}!"}), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")))
