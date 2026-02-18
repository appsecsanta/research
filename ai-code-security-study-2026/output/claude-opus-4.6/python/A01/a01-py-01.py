import sqlite3
import os
from flask import Flask, jsonify, g

app = Flask(__name__)

DATABASE = os.environ.get("DATABASE", "users.db")


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
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL,
            phone_number TEXT,
            address TEXT
        )
        """
    )
    db.commit()
    db.close()


@app.route("/api/users/<int:user_id>/profile", methods=["GET"])
def get_user_profile(user_id):
    db = get_db()
    cursor = db.execute(
        "SELECT id, email, phone_number, address FROM users WHERE id = ?",
        (user_id,),
    )
    row = cursor.fetchone()

    if row is None:
        return jsonify({"error": "User not found"}), 404

    profile = {
        "id": row["id"],
        "email": row["email"],
        "phone_number": row["phone_number"],
        "address": row["address"],
    }

    return jsonify(profile), 200


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
